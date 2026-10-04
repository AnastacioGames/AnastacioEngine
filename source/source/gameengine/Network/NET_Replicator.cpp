/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Network/NET_Replicator.cpp
 *  \ingroup network
 */

#include "NET_Replicator.h"

#include "NET_Messages.h"

#include <algorithm>
#include <cmath>

namespace net {

namespace {

/// Reliable messages grouped into packets of at most 64 messages and kMaxReliableMessage bytes.
struct ReliableBatch {
	std::vector<std::vector<uint8_t>> packets;
	std::vector<uint8_t> current;
	size_t count = 0;

	template <class Msg, class... Extra>
	void add(const Msg &msg, const Extra &...extra)
	{
		std::vector<uint8_t> tmp;
		if (!appendMessage(tmp, msg, extra...)) {
			return;
		}
		if (count == kMaxMessagesPerPacket || current.size() + tmp.size() > kMaxReliableMessage) {
			flush();
		}
		current.insert(current.end(), tmp.begin(), tmp.end());
		++count;
	}

	void flush()
	{
		if (count > 0) {
			packets.push_back(std::move(current));
			current.clear();
			count = 0;
		}
	}
};

/// Removed entries in one snapshot (at most ~5.25 bytes each); more are deferred to the next ones.
constexpr size_t kMaxRemovalsPerSnapshot = 128;
/// Below this many budget bytes no snapshot is sent.
constexpr double kMinSnapshotBudget = 32.0;
/// Snapshot packet overhead: message header (<= 4), two ticks, object count (<= 3).
constexpr size_t kSnapshotOverhead = 4 + 8 + 3;
/// Estimated bits per entry besides its fields: NetId delta (2 bytes) and two flags.
constexpr size_t kEntryBits = 16 + 2;

uint64_t cellKey(int64_t x, int64_t y, int64_t z)
{
	const uint64_t mask = (1ull << 21) - 1;
	return ((uint64_t(x) & mask) << 42) | ((uint64_t(y) & mask) << 21) | (uint64_t(z) & mask);
}

float distanceSq(const float a[3], const float b[3])
{
	float d = 0.0f;
	for (int i = 0; i < 3; ++i) {
		d += (a[i] - b[i]) * (a[i] - b[i]);
	}
	return d;
}

uint64_t hashBytes(const std::vector<uint8_t> &bytes)
{
	uint64_t hash = 0xcbf29ce484222325ull;
	for (uint8_t b : bytes) {
		hash ^= b;
		hash *= 0x100000001b3ull;
	}
	return hash ^ bytes.size();
}

bool contains(const std::vector<NetId> &sorted, NetId id)
{
	return std::binary_search(sorted.begin(), sorted.end(), id);
}

}  // namespace

Replicator::Replicator(ServerSession &session, IWorld &world, const ReplicatorConfig &config)
	:m_session(session),
	m_world(world),
	m_config(config)
{
	if (m_config.snapshotIntervalTicks == 0) {
		m_config.snapshotIntervalTicks = 1;
	}
	if (!(m_config.cellSize > 0.0f)) {
		m_config.cellSize = 32.0f;
	}
	if (m_config.hysteresis < 1.0f) {
		m_config.hysteresis = 1.0f;
	}
	m_config.snapshot.schema = [this](NetId id) -> const std::vector<PropertyDesc> * {
		const auto it = m_objects.find(id);
		if (it == m_objects.end() || it->second.desc.props.empty()) {
			return nullptr;
		}
		return &it->second.desc.props;
	};
}

/* -------------------------------------------------------------------- */
/** \name Objects
 * \{ */

bool Replicator::addSceneObject(NetId id, const ReplicatedObjectDesc &desc)
{
	if (id == kInvalidNetId || isRuntimeNetId(id) || m_objects.count(id)) {
		return false;
	}
	m_objects[id].desc = desc;
	return true;
}

NetId Replicator::spawn(const ReplicatedObjectDesc &desc)
{
	if (desc.prototype.empty() || desc.prototype.size() > kMaxStringBytes) {
		return kInvalidNetId;
	}
	// Sequential ids, skipping ones still in use after a wrap.
	for (uint32_t tries = 0; tries < 0x80000000u; ++tries) {
		const NetId id = m_nextRuntimeId;
		m_nextRuntimeId = (m_nextRuntimeId == 0xFFFFFFFFu) ? kFirstRuntimeNetId : m_nextRuntimeId + 1;
		if (!m_objects.count(id)) {
			m_objects[id].desc = desc;
			return id;
		}
	}
	return kInvalidNetId;
}

bool Replicator::despawn(NetId id)
{
	if (!m_objects.erase(id)) {
		return false;
	}
	for (auto &pair : m_clients) {
		ClientRep &rep = pair.second;
		rep.relevant.erase(std::remove(rep.relevant.begin(), rep.relevant.end(), id), rep.relevant.end());
		rep.priority.erase(id);
		if (rep.spawned.erase(id)) {
			ReliableBatch batch;
			DespawnMsg msg;
			msg.netId = id;
			batch.add(msg);
			batch.flush();
			for (const std::vector<uint8_t> &packet : batch.packets) {
				m_session.send(pair.first, Channel::Control, packet);
				rep.tokens -= double(packet.size());
				rep.stats.reliableBytes += packet.size();
			}
		}
	}
	return true;
}

bool Replicator::setOwner(NetId id, ClientId owner)
{
	const auto it = m_objects.find(id);
	if (it == m_objects.end()) {
		return false;
	}
	if (it->second.desc.owner == owner) {
		return true;
	}
	it->second.desc.owner = owner;
	// Clients without the Spawn yet get the new owner inside it.
	for (auto &pair : m_clients) {
		ClientRep &rep = pair.second;
		if (!rep.active || (isRuntimeNetId(id) && !rep.spawned.count(id))) {
			continue;
		}
		OwnershipMsg msg;
		msg.netId = id;
		msg.newOwner = owner;
		const std::vector<uint8_t> packet = makePacket(msg);
		m_session.send(pair.first, Channel::Control, packet);
		rep.tokens -= double(packet.size());
		rep.stats.reliableBytes += packet.size();
	}
	return true;
}

ClientId Replicator::owner(NetId id) const
{
	const auto it = m_objects.find(id);
	return it == m_objects.end() ? kServerClientId : it->second.desc.owner;
}

bool Replicator::hasObject(NetId id) const
{
	return m_objects.count(id) != 0;
}

size_t Replicator::objectCount() const
{
	return m_objects.size();
}

void Replicator::setClientView(ClientId client, const float position[3], float radius)
{
	ClientRep &rep = m_clients[client];
	rep.hasView = true;
	for (int i = 0; i < 3; ++i) {
		rep.view[i] = position[i];
	}
	rep.radius = radius;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Session events
 * \{ */

bool Replicator::handleEvent(const SessionEvent &event)
{
	switch (event.type) {
		case SessionEvent::Type::ClientJoined: {
			// A (re)joining client starts from scratch: spawns and a full snapshot.
			const auto it = m_clients.find(event.client);
			if (it != m_clients.end()) {
				it->second.active = false;
			}
			return false;
		}
		case SessionEvent::Type::ClientLeft:
			m_clients.erase(event.client);
			return false;
		case SessionEvent::Type::ClientExpired: {
			std::vector<NetId> owned;
			for (const auto &pair : m_objects) {
				if (pair.second.desc.owner == event.client) {
					owned.push_back(pair.first);
				}
			}
			for (NetId id : owned) {
				if (isRuntimeNetId(id) && m_config.despawnOnExpire) {
					despawn(id);
				}
				else {
					setOwner(id, kServerClientId);
				}
			}
			return false;
		}
		case SessionEvent::Type::Message:
			break;
		default:
			return false;
	}

	RawMessage raw;
	raw.type = event.messageType;
	raw.body = event.body.data();
	raw.size = event.body.size();
	const auto it = m_clients.find(event.client);

	if (raw.type == uint8_t(MessageType::SnapshotAck)) {
		SnapshotAckMsg ack;
		if (!decodeMessage(raw, ack) || it == m_clients.end()) {
			return true;
		}
		ClientRep &rep = it->second;
		// Acks of unknown or older ticks are ignored (reordered or duplicated packets).
		if (rep.history.count(ack.tick) && (rep.acked == kNoTick || tickNewer(ack.tick, rep.acked))) {
			rep.acked = ack.tick;
			rep.stats.ackedTick = ack.tick;
			rep.history.erase(rep.history.begin(), rep.history.find(ack.tick));
		}
		return true;
	}
	if (raw.type == uint8_t(MessageType::FullStateRequest)) {
		FullStateRequestMsg msg;
		if (decodeMessage(raw, msg) && it != m_clients.end()) {
			it->second.acked = kNoTick;
			it->second.history.clear();
		}
		return true;
	}
	return false;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Update
 * \{ */

void Replicator::capture()
{
	for (auto &pair : m_objects) {
		const NetId id = pair.first;
		Object &obj = pair.second;
		if (obj.hasState && m_world.isSleeping(id)) {
			continue;
		}
		ObjectState s = obj.state;
		s.id = id;
		bool ok = true;
		if (obj.desc.syncTransform) {
			ok = m_world.getTransform(id, s.position, s.rotation);
			s.hasTransform = ok;
		}
		if (ok && (obj.desc.syncVelocity || obj.desc.syncAngularVelocity)) {
			float lin[3], ang[3];
			ok = m_world.getVelocity(id, lin, ang);
			if (ok) {
				if (obj.desc.syncVelocity) {
					std::copy(lin, lin + 3, s.velocity);
					s.hasVelocity = true;
				}
				if (obj.desc.syncAngularVelocity) {
					std::copy(ang, ang + 3, s.angularVelocity);
					s.hasAngularVelocity = true;
				}
			}
		}
		if (ok && !obj.desc.props.empty()) {
			std::vector<PropValue> props;
			ok = m_world.getProperties(id, props) && props.size() == obj.desc.props.size();
			for (size_t i = 0; ok && i < props.size(); ++i) {
				ok = props[i].kind == obj.desc.props[i].kind;
			}
			if (ok) {
				s.props = std::move(props);
			}
		}
		// Missing objects or bad data keep the last good state.
		if (ok) {
			obj.state = std::move(s);
			obj.hasState = true;
			m_scratch.clear();
			BitWriter w(m_scratch);
			encodeObjectFields(w, obj.state, nullptr, m_config.snapshot);
			w.alignToByte();
			obj.fullBits = w.bitsWritten();
			obj.fullHash = hashBytes(m_scratch);
		}
	}
}

int64_t Replicator::cellCoord(float v) const
{
	const double c = std::floor(double(v) / double(m_config.cellSize));
	return int64_t(std::max(-1e15, std::min(1e15, c)));
}

void Replicator::rebuildGrid()
{
	m_grid.clear();
	m_ungridded.clear();
	for (auto &pair : m_objects) {
		Object &obj = pair.second;
		if (!obj.hasState) {
			continue;
		}
		if (obj.desc.alwaysRelevant || !obj.state.hasTransform) {
			m_ungridded.push_back(pair.first);
			continue;
		}
		for (int i = 0; i < 3; ++i) {
			obj.cell[i] = cellCoord(obj.state.position[i]);
		}
		m_grid[cellKey(obj.cell[0], obj.cell[1], obj.cell[2])].push_back(pair.first);
	}
}

void Replicator::computeRelevant(ClientId id, const ClientRep &rep, std::vector<NetId> &out) const
{
	out.clear();
	if (!rep.hasView || !(rep.radius > 0.0f)) {
		for (const auto &pair : m_objects) {
			if (pair.second.hasState) {
				out.push_back(pair.first);
			}
		}
		return;
	}

	out.insert(out.end(), m_ungridded.begin(), m_ungridded.end());
	const float radiusSq = rep.radius * rep.radius;
	const float outer = rep.radius * m_config.hysteresis;
	const float outerSq = outer * outer;
	const auto test = [&](NetId nid, const Object &obj) {
		if (obj.desc.owner == id && id != kServerClientId) {
			out.push_back(nid);
			return;
		}
		const float d = distanceSq(obj.state.position, rep.view);
		if (d <= radiusSq || (d <= outerSq && contains(rep.relevant, nid))) {
			out.push_back(nid);
		}
	};

	int64_t lo[3], hi[3];
	double cells = 1.0;
	for (int i = 0; i < 3; ++i) {
		lo[i] = cellCoord(rep.view[i] - outer);
		hi[i] = cellCoord(rep.view[i] + outer);
		cells *= double(hi[i] - lo[i] + 1);
	}

	if (cells > double(m_grid.size()) || cells > 4096.0) {
		// Query box bigger than the grid itself: scan every object.
		for (const auto &pair : m_objects) {
			const Object &obj = pair.second;
			if (obj.hasState && obj.state.hasTransform && !obj.desc.alwaysRelevant) {
				test(pair.first, obj);
			}
		}
		std::sort(out.begin(), out.end());
		return;
	}
	for (int64_t x = lo[0]; x <= hi[0]; ++x) {
		for (int64_t y = lo[1]; y <= hi[1]; ++y) {
			for (int64_t z = lo[2]; z <= hi[2]; ++z) {
				const auto cell = m_grid.find(cellKey(x, y, z));
				if (cell == m_grid.end()) {
					continue;
				}
				for (NetId nid : cell->second) {
					const Object &obj = m_objects.at(nid);
					// Keys wrap: skip objects of another cell with the same key.
					if (obj.cell[0] == x && obj.cell[1] == y && obj.cell[2] == z) {
						test(nid, obj);
					}
				}
			}
		}
	}
	// Owned objects are always relevant to their owner.
	if (id != kServerClientId) {
		for (const auto &pair : m_objects) {
			if (pair.second.hasState && pair.second.desc.owner == id) {
				out.push_back(pair.first);
			}
		}
	}
	std::sort(out.begin(), out.end());
	out.erase(std::unique(out.begin(), out.end()), out.end());
}

void Replicator::activate(ClientRep &rep)
{
	rep.active = true;
	rep.history.clear();
	rep.acked = kNoTick;
	rep.relevant.clear();
	rep.spawned.clear();
	rep.priority.clear();
	rep.ticksSinceSnapshot = m_config.snapshotIntervalTicks - 1;  // first snapshot right away
	rep.tokens = double(kMaxUnreliablePayload);
	rep.hasLastMs = false;
	rep.stats.ackedTick = kNoTick;
}

void Replicator::updateSpawns(ClientId id, ClientRep &rep, const std::vector<NetId> &relevant)
{
	ReliableBatch batch;
	// Runtime objects that left the client's view.
	for (auto it = rep.spawned.begin(); it != rep.spawned.end();) {
		if (!contains(relevant, *it)) {
			DespawnMsg msg;
			msg.netId = *it;
			batch.add(msg);
			rep.priority.erase(*it);
			it = rep.spawned.erase(it);
		}
		else {
			++it;
		}
	}
	// Runtime objects that entered it: the Spawn goes out before any snapshot citing them.
	for (NetId nid : relevant) {
		if (!isRuntimeNetId(nid) || rep.spawned.count(nid)) {
			continue;
		}
		const Object &obj = m_objects.at(nid);
		SpawnMsg msg;
		msg.netId = nid;
		msg.prototypeName = obj.desc.prototype;
		msg.owner = obj.desc.owner;
		msg.state = obj.state;
		batch.add(msg, m_config.snapshot);
		rep.spawned.insert(nid);
	}
	batch.flush();
	for (const std::vector<uint8_t> &packet : batch.packets) {
		m_session.send(id, Channel::Control, packet);
		rep.tokens -= double(packet.size());
		rep.stats.reliableBytes += packet.size();
	}
}

void Replicator::sendSnapshot(ClientId id, ClientRep &rep, Tick tick)
{
	if (rep.tokens < kMinSnapshotBudget) {
		++rep.stats.snapshotsSkipped;
		return;
	}
	const size_t limit = size_t(std::min(double(kMaxUnreliablePayload), rep.tokens));
	const SnapshotConfig &cfg = m_config.snapshot;

	const auto baseIt = rep.acked != kNoTick ? rep.history.find(rep.acked) : rep.history.end();
	const SentSnapshot *base = baseIt != rep.history.end() ? &baseIt->second : nullptr;
	static const std::vector<ObjectState> noObjects;
	const std::vector<ObjectState> &baseObjs = base ? base->snapshot.objects : noObjects;

	// Merge walk of the relevant objects and the baseline (both sorted by NetId): baseline
	// index of each relevant object, changed ones (field hash differs) and removals.
	struct Candidate {
		NetId id;
		float priority;
		size_t bits;
		size_t relevantIndex;
	};
	std::vector<Candidate> candidates;
	std::vector<int> baseOf(rep.relevant.size(), -1);
	std::vector<NetId> removals;
	std::vector<int> deferred;
	size_t j = 0;
	const auto removeBase = [&](size_t index) {
		if (removals.size() < kMaxRemovalsPerSnapshot) {
			removals.push_back(baseObjs[index].id);
		}
		else {
			deferred.push_back(int(index));  // stays as in the baseline for now
		}
	};
	for (size_t i = 0; i < rep.relevant.size(); ++i) {
		const NetId nid = rep.relevant[i];
		while (j < baseObjs.size() && baseObjs[j].id < nid) {
			removeBase(j++);
		}
		const Object &obj = m_objects.at(nid);
		if (j < baseObjs.size() && baseObjs[j].id == nid) {
			baseOf[i] = int(j);
			const bool same = base->hashes[j] == obj.fullHash;
			++j;
			if (same) {
				continue;
			}
		}
		float &acc = rep.priority[nid];
		acc += std::max(obj.desc.priority, 1e-3f);
		candidates.push_back({nid, acc, obj.fullBits, i});
	}
	while (j < baseObjs.size()) {
		removeBase(j++);
	}
	std::sort(candidates.begin(), candidates.end(), [](const Candidate &a, const Candidate &b) {
		return a.priority != b.priority ? a.priority > b.priority : a.id < b.id;
	});

	// Greedy pick by size (full size bounds the delta), then trim until the packet fits.
	const size_t budgetBits = limit > kSnapshotOverhead ? (limit - kSnapshotOverhead) * 8 : 0;
	size_t usedBits = removals.size() * kEntryBits;
	std::vector<const Candidate *> selected;
	for (const Candidate &c : candidates) {
		if (usedBits + c.bits + kEntryBits <= budgetBits) {
			usedBits += c.bits + kEntryBits;
			selected.push_back(&c);
		}
	}

	std::vector<uint8_t> packet;
	std::vector<uint8_t> body;
	for (;;) {
		// Entries: selected (changed) and removed objects, sorted by NetId.
		struct Entry {
			NetId id;
			const Candidate *c;
		};
		std::vector<Entry> entries;
		entries.reserve(selected.size() + removals.size());
		for (const Candidate *c : selected) {
			entries.push_back({c->id, c});
		}
		for (NetId nid : removals) {
			entries.push_back({nid, nullptr});
		}
		std::sort(entries.begin(), entries.end(), [](const Entry &a, const Entry &b) { return a.id < b.id; });

		body.clear();
		BitWriter w(body);
		w.writeU32(tick);
		w.writeU32(base ? base->snapshot.tick : kNoTick);
		w.writeVarU(entries.size());
		NetId prev = 0;
		for (const Entry &e : entries) {
			w.writeVarU(e.id - prev);
			prev = e.id;
			w.writeBool(e.c == nullptr);
			if (e.c) {
				w.writeBool(true);
				const int bi = baseOf[e.c->relevantIndex];
				const ObjectState *b = bi >= 0 ? &baseObjs[size_t(bi)] : nullptr;
				encodeObjectFields(w, m_objects.at(e.id).state, b, cfg);
			}
		}
		w.alignToByte();
		packet.clear();
		if (!w.ok() || !appendRawMessage(packet, MessageType::Snapshot, body)) {
			return;
		}
		if (packet.size() <= limit || selected.empty()) {
			break;
		}
		selected.pop_back();
	}
	if (packet.size() > kMaxUnreliablePayload) {
		++rep.stats.snapshotsSkipped;
		return;
	}

	m_session.send(id, Channel::Snapshot, packet);
	rep.tokens -= double(packet.size());

	// What the client holds after applying it: baseline + selected changes - removals.
	std::vector<char> chosen(rep.relevant.size(), 0);
	for (const Candidate *c : selected) {
		chosen[c->relevantIndex] = 1;
		rep.priority[c->id] = 0.0f;
	}
	SentSnapshot sent;
	sent.snapshot.tick = tick;
	sent.snapshot.baselineTick = base ? base->snapshot.tick : kNoTick;
	sent.snapshot.objects.reserve(rep.relevant.size() + deferred.size());
	sent.hashes.reserve(rep.relevant.size() + deferred.size());
	size_t d = 0;
	const auto pushDeferredBefore = [&](NetId limitId) {
		while (d < deferred.size() && baseObjs[size_t(deferred[d])].id < limitId) {
			sent.snapshot.objects.push_back(baseObjs[size_t(deferred[d])]);
			sent.hashes.push_back(base->hashes[size_t(deferred[d])]);
			++d;
		}
	};
	for (size_t i = 0; i < rep.relevant.size(); ++i) {
		const NetId nid = rep.relevant[i];
		pushDeferredBefore(nid);
		if (chosen[i]) {
			const Object &obj = m_objects.at(nid);
			sent.snapshot.objects.push_back(obj.state);
			sent.hashes.push_back(obj.fullHash);
		}
		else if (baseOf[i] >= 0) {
			sent.snapshot.objects.push_back(baseObjs[size_t(baseOf[i])]);
			sent.hashes.push_back(base->hashes[size_t(baseOf[i])]);
		}
	}
	pushDeferredBefore(0xFFFFFFFFu);
	if (d < deferred.size()) {
		sent.snapshot.objects.push_back(baseObjs[size_t(deferred[d])]);
		sent.hashes.push_back(base->hashes[size_t(deferred[d])]);
	}
	rep.history[tick] = std::move(sent);
	while (rep.history.size() > size_t(kSnapshotHistory)) {
		rep.history.erase(rep.history.begin());
	}

	ReplicationStats &st = rep.stats;
	st.snapshotBytes += packet.size();
	++st.snapshotsSent;
	st.lastSnapshotBytes = packet.size();
	st.lastSnapshotEntries = selected.size() + removals.size();
	st.pendingObjects = candidates.size() - selected.size();
}

void Replicator::update(Tick tick, uint64_t nowMs)
{
	capture();
	rebuildGrid();

	const std::vector<ClientId> ids = m_session.clients();
	for (auto it = m_clients.begin(); it != m_clients.end();) {
		if (std::find(ids.begin(), ids.end(), it->first) == ids.end()) {
			it = m_clients.erase(it);
		}
		else {
			++it;
		}
	}

	const double capTokens = std::max(2.0 * double(kMaxUnreliablePayload), double(m_config.bytesPerSecond) / 4.0);
	for (ClientId id : ids) {
		const ServerSession::ClientState *cs = m_session.client(id);
		ClientRep &rep = m_clients[id];
		if (!cs || !cs->ready) {
			rep.active = false;  // scene change: everything restarts once it is loaded
			continue;
		}
		if (!rep.active) {
			activate(rep);
		}
		if (rep.hasLastMs && nowMs > rep.lastMs) {
			rep.tokens = std::min(capTokens,
			                      rep.tokens + double(m_config.bytesPerSecond) * double(nowMs - rep.lastMs) / 1000.0);
		}
		rep.lastMs = nowMs;
		rep.hasLastMs = true;

		if (++rep.ticksSinceSnapshot < m_config.snapshotIntervalTicks) {
			continue;
		}
		rep.ticksSinceSnapshot = 0;

		std::vector<NetId> relevant;
		computeRelevant(id, rep, relevant);
		updateSpawns(id, rep, relevant);
		rep.relevant = std::move(relevant);
		sendSnapshot(id, rep, tick);
	}
}

/** \} */

const ReplicationStats *Replicator::stats(ClientId client) const
{
	const auto it = m_clients.find(client);
	return it == m_clients.end() ? nullptr : &it->second.stats;
}

bool Replicator::isRelevant(ClientId client, NetId id) const
{
	const auto it = m_clients.find(client);
	return it != m_clients.end() && contains(it->second.relevant, id);
}

const SnapshotConfig &Replicator::snapshotConfig() const
{
	return m_config.snapshot;
}

}  // namespace net
