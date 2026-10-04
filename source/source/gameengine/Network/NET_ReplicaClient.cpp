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

/** \file gameengine/Network/NET_ReplicaClient.cpp
 *  \ingroup network
 */

#include "NET_ReplicaClient.h"

#include "NET_Messages.h"

namespace net {

ReplicaClient::ReplicaClient(ClientSession &session, IWorld &world, const ReplicaClientConfig &config)
	:m_session(session),
	m_world(world),
	m_config(config),
	m_buffer(config.bufferCapacity)
{
	m_config.snapshot.schema = [this](NetId id) -> const std::vector<PropertyDesc> * {
		if (!m_config.schema) {
			return nullptr;
		}
		const auto it = m_prototypes.find(id);
		static const std::string none;
		return m_config.schema(id, it == m_prototypes.end() ? none : it->second);
	};
}

void ReplicaClient::reset()
{
	m_buffer.clear();
	m_lastAccepted = kNoTick;
	m_requestedFull = false;
	m_prototypes.clear();
	m_owners.clear();
}

bool ReplicaClient::handleEvent(const SessionEvent &event, uint64_t nowMs)
{
	switch (event.type) {
		case SessionEvent::Type::Connected:
		case SessionEvent::Type::SceneChange:
		case SessionEvent::Type::Disconnected:
			reset();
			return false;
		case SessionEvent::Type::Message:
			break;
		default:
			return false;
	}

	RawMessage raw;
	raw.type = event.messageType;
	raw.body = event.body.data();
	raw.size = event.body.size();

	switch (MessageType(raw.type)) {
		case MessageType::Snapshot:
			handleSnapshot(raw, nowMs);
			return true;
		case MessageType::Spawn: {
			// The schema depends on the prototype, which comes before the object fields.
			BitReader peek(raw.body, raw.size);
			const NetId id = peek.readU32();
			std::string prototype;
			if (!peek.readString(prototype) || !isRuntimeNetId(id)) {
				++m_stats.snapshotsInvalid;
				return true;
			}
			const auto old = m_prototypes.find(id);
			const bool hadOld = old != m_prototypes.end();
			const std::string oldPrototype = hadOld ? old->second : std::string();
			m_prototypes[id] = prototype;

			SpawnMsg msg;
			if (!decodeMessage(raw, msg, m_config.snapshot)) {
				if (hadOld) {
					m_prototypes[id] = oldPrototype;
				}
				else {
					m_prototypes.erase(id);
				}
				++m_stats.snapshotsInvalid;
				return true;
			}
			m_owners[id] = msg.owner;
			if (m_world.exists(id)) {
				// Spawn again after a reconnect or a relevance change: just refresh it.
				m_world.setOwner(id, msg.owner);
				apply({msg.state});
			}
			else {
				m_world.spawn(id, msg.prototypeName, msg.owner, msg.state);
			}
			++m_stats.spawns;
			return true;
		}
		case MessageType::Despawn: {
			DespawnMsg msg;
			if (decodeMessage(raw, msg) && m_prototypes.erase(msg.netId)) {
				m_owners.erase(msg.netId);
				m_world.despawn(msg.netId);
				++m_stats.despawns;
			}
			return true;
		}
		case MessageType::Ownership: {
			OwnershipMsg msg;
			// Unknown objects are ignored (the Spawn carries the owner).
			if (decodeMessage(raw, msg) && m_world.exists(msg.netId)) {
				m_owners[msg.netId] = msg.newOwner;
				m_world.setOwner(msg.netId, msg.newOwner);
			}
			return true;
		}
		default:
			return false;
	}
}

void ReplicaClient::requestFullState(uint64_t nowMs)
{
	if (m_requestedFull && nowMs - m_lastFullRequestMs < m_config.fullStateRetryMs) {
		return;
	}
	m_requestedFull = true;
	m_lastFullRequestMs = nowMs;
	++m_stats.fullStateRequests;
	m_session.send(Channel::Control, makePacket(FullStateRequestMsg()));
}

void ReplicaClient::handleSnapshot(const RawMessage &raw, uint64_t nowMs)
{
	Tick tick, baselineTick;
	if (!readSnapshotHeader(raw.body, raw.size, tick, baselineTick) || tick == kNoTick) {
		++m_stats.snapshotsInvalid;
		return;
	}
	// Unreliable channels can reorder, and WebSocket delivers everything: drop old ones.
	if (m_lastAccepted != kNoTick && !tickNewer(tick, m_lastAccepted)) {
		++m_stats.snapshotsOld;
		return;
	}
	const Snapshot *baseline = nullptr;
	if (baselineTick != kNoTick) {
		baseline = m_buffer.find(baselineTick);
		if (!baseline) {
			++m_stats.snapshotsNoBaseline;
			requestFullState(nowMs);
			return;
		}
	}
	Snapshot snapshot;
	if (!decodeSnapshotMessage(raw, baseline, m_config.snapshot, snapshot)) {
		// Usually a snapshot citing an object whose Spawn has not arrived yet: not acked, so the
		// server sends that object again later.
		++m_stats.snapshotsInvalid;
		return;
	}
	if (baselineTick == kNoTick) {
		m_requestedFull = false;
	}
	m_buffer.insert(snapshot);
	m_lastAccepted = tick;
	++m_stats.snapshotsAccepted;

	SnapshotAckMsg ack;
	ack.tick = tick;
	m_session.send(Channel::Input, makePacket(ack));
}

void ReplicaClient::apply(const std::vector<ObjectState> &objects)
{
	const ClientId self = m_session.clientId();
	for (const ObjectState &o : objects) {
		if (!m_world.exists(o.id)) {
			continue;
		}
		if (m_config.skipOwned && self != kServerClientId && owner(o.id) == self &&
		    (!m_config.skipFilter || m_config.skipFilter(o.id)))
		{
			continue;
		}
		if (o.hasTransform) {
			m_world.setTransform(o.id, o.position, o.rotation);
		}
		if (o.hasVelocity || o.hasAngularVelocity) {
			m_world.setVelocity(o.id, o.velocity, o.angularVelocity);
		}
		if (!o.props.empty()) {
			m_world.setProperties(o.id, o.props);
		}
	}
}

bool ReplicaClient::applyLatest()
{
	const Snapshot *s = m_buffer.newest();
	if (!s) {
		return false;
	}
	apply(s->objects);
	return true;
}

bool ReplicaClient::applyInterpolated(Tick renderTick, float alpha)
{
	std::vector<ObjectState> objects;
	if (!m_buffer.sample(renderTick, alpha, objects)) {
		return false;
	}
	apply(objects);
	return true;
}

const SnapshotBuffer &ReplicaClient::buffer() const
{
	return m_buffer;
}

Tick ReplicaClient::lastAcceptedTick() const
{
	return m_lastAccepted;
}

const ReplicaClientStats &ReplicaClient::stats() const
{
	return m_stats;
}

ClientId ReplicaClient::owner(NetId id) const
{
	const auto it = m_owners.find(id);
	return it == m_owners.end() ? kServerClientId : it->second;
}

}  // namespace net
