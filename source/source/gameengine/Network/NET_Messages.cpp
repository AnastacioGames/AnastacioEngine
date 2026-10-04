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

/** \file gameengine/Network/NET_Messages.cpp
 *  \ingroup network
 */

#include "NET_Messages.h"

namespace net {

/* -------------------------------------------------------------------- */
/** \name Packet framing
 * \{ */

bool appendRawMessage(std::vector<uint8_t> &packet, uint8_t type, const uint8_t *body, size_t size)
{
	if (size > kMaxReliableMessage) {
		return false;
	}
	BitWriter w(packet);
	w.writeU8(type);
	w.writeVarU(size);
	packet.insert(packet.end(), body, body + size);
	return w.ok();
}

bool appendRawMessage(std::vector<uint8_t> &packet, MessageType type, const std::vector<uint8_t> &body)
{
	return appendRawMessage(packet, uint8_t(type), body.data(), body.size());
}

PacketReader::PacketReader(const uint8_t *data, size_t size)
	:m_data(data),
	m_size(data ? size : 0),
	m_pos(0),
	m_count(0),
	m_ok(true)
{
}

bool PacketReader::next(RawMessage &msg)
{
	msg = RawMessage();
	if (!m_ok || m_pos >= m_size) {
		return false;
	}
	if (m_count >= kMaxMessagesPerPacket) {
		m_ok = false;
		return false;
	}
	const uint8_t type = m_data[m_pos++];
	uint32_t len = 0;
	bool done = false;
	for (int i = 0; i < kMaxMessageLengthBytes && m_pos < m_size; ++i) {
		const uint8_t byte = m_data[m_pos++];
		len |= uint32_t(byte & 0x7F) << (7 * i);
		if ((byte & 0x80) == 0) {
			done = true;
			break;
		}
	}
	if (!done || len > m_size - m_pos) {
		m_ok = false;
		return false;
	}
	msg.type = type;
	msg.body = m_data + m_pos;
	msg.size = len;
	m_pos += len;
	++m_count;
	return true;
}

bool PacketReader::ok() const
{
	return m_ok;
}

size_t PacketReader::count() const
{
	return m_count;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Helpers
 * \{ */

/// Body must end here, only padding bits may remain.
static bool finish(BitReader &r)
{
	r.alignToByte();
	if (r.ok() && r.bitsRemaining() != 0) {
		r.fail();
	}
	return r.ok();
}

static bool done(BitWriter &w)
{
	w.alignToByte();
	return w.ok();
}

static void writeLimitedString(BitWriter &w, const std::string &s, size_t limit)
{
	if (s.size() > limit) {
		w.fail();
		return;
	}
	w.writeString(s);
}

static void readLimitedString(BitReader &r, std::string &s, size_t limit)
{
	if (r.readString(s) && s.size() > limit) {
		r.fail();
	}
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Encode
 * \{ */

bool encode(BitWriter &w, const HelloMsg &m)
{
	w.writeU32(kProtocolMagic);
	w.writeU16(m.protocolVersion);
	w.writeString(m.gameId);
	w.writeU32(m.gameVersion);
	w.writeU64(m.sceneHash);
	w.writeString(m.playerName);
	w.writeU64(m.token);
	return done(w);
}

bool encode(BitWriter &w, const WelcomeMsg &m)
{
	w.writeU16(m.clientId);
	w.writeU16(m.tickRate);
	w.writeU16(m.snapshotRate);
	w.writeU32(m.serverTick);
	w.writeU16(m.maxClients);
	w.writeString(m.sceneName);
	return done(w);
}

bool encode(BitWriter &w, const RejectMsg &m)
{
	w.writeU8(uint8_t(m.reason));
	w.writeString(m.detail);
	return done(w);
}

bool encode(BitWriter &w, const DisconnectMsg &m)
{
	w.writeU8(uint8_t(m.reason));
	return done(w);
}

bool encode(BitWriter &w, const PingMsg &m)
{
	w.writeU32(m.seq);
	w.writeU32(m.senderTimeMs);
	return done(w);
}

bool encode(BitWriter &w, const PongMsg &m)
{
	w.writeU32(m.seq);
	w.writeU32(m.echoTimeMs);
	w.writeU32(m.serverTick);
	return done(w);
}

bool encode(BitWriter &w, const ClientInfoMsg &m)
{
	w.writeU16(m.clientId);
	w.writeString(m.name);
	w.writeU8(m.flags);
	return done(w);
}

bool encode(BitWriter &w, const SceneChangeMsg &m)
{
	w.writeString(m.sceneName);
	w.writeU64(m.sceneHash);
	return done(w);
}

bool encode(BitWriter &w, const SceneLoadedMsg &m)
{
	w.writeU64(m.sceneHash);
	return done(w);
}

bool encode(BitWriter &w, const SpawnMsg &m, const SnapshotConfig &config)
{
	if (m.netId == kInvalidNetId) {
		w.fail();
		return false;
	}
	w.writeU32(m.netId);
	w.writeString(m.prototypeName);
	w.writeU16(m.owner);
	ObjectState state = m.state;
	state.id = m.netId;
	encodeObjectFields(w, state, nullptr, config);
	return done(w);
}

bool encode(BitWriter &w, const DespawnMsg &m)
{
	w.writeU32(m.netId);
	return done(w);
}

bool encode(BitWriter &w, const OwnershipMsg &m)
{
	w.writeU32(m.netId);
	w.writeU16(m.newOwner);
	return done(w);
}

bool encode(BitWriter &w, const SnapshotAckMsg &m)
{
	w.writeU32(m.tick);
	return done(w);
}

bool encode(BitWriter &w, const InputMsg &m)
{
	if (m.blocks.empty() || m.blocks.size() > size_t(kMaxInputBlocks)) {
		w.fail();
		return false;
	}
	w.writeU32(m.newestTick);
	w.writeU8(uint8_t(m.blocks.size()));
	for (const std::vector<uint8_t> &block : m.blocks) {
		if (block.size() > kMaxInputBlockBytes) {
			w.fail();
			return false;
		}
		w.writeVarU(block.size());
		for (uint8_t byte : block) {
			w.writeU8(byte);
		}
	}
	return done(w);
}

bool encode(BitWriter &w, const RpcMsg &m)
{
	if (m.args.size() > 255) {
		w.fail();
		return false;
	}
	w.writeU32(m.netId);
	w.writeU16(m.rpcId);
	w.writeU32(m.tick);
	const size_t argsStart = w.bitsWritten();
	w.writeU8(uint8_t(m.args.size()));
	for (const RpcArg &a : m.args) {
		w.writeU8(uint8_t(a.type));
		switch (a.type) {
			case RpcArgType::Bool:
				w.writeU8(a.b ? 1 : 0);
				break;
			case RpcArgType::Int:
				w.writeVarI(a.i);
				break;
			case RpcArgType::Float:
				writeFloat32(w, a.v[0]);
				break;
			case RpcArgType::Vec3:
				for (int i = 0; i < 3; ++i) {
					writeFloat32(w, a.v[i]);
				}
				break;
			case RpcArgType::Quat:
				for (int i = 0; i < 4; ++i) {
					writeFloat32(w, a.v[i]);
				}
				break;
			case RpcArgType::Str:
				w.writeString(a.s);
				break;
			case RpcArgType::NetId:
				w.writeU32(a.id);
				break;
			default:
				w.fail();
				return false;
		}
	}
	if (w.bitsWritten() - argsStart > kMaxRpcArgsBytes * 8) {
		w.fail();
	}
	return done(w);
}

bool encode(BitWriter &w, const FullStateRequestMsg &)
{
	return done(w);
}

bool encode(BitWriter &w, const RpcFromMsg &m)
{
	w.writeU16(m.fromClient);
	return encode(w, m.rpc);
}

bool encode(BitWriter &w, const InputTimingMsg &m)
{
	w.writeU32(m.tick);
	w.writeU16(uint16_t(m.slackQ4));
	return done(w);
}

bool encode(BitWriter &w, const ChatMsg &m)
{
	w.writeU16(m.fromClient);
	writeLimitedString(w, m.text, kMaxChatBytes);
	return done(w);
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Decode
 * \{ */

bool decode(BitReader &r, HelloMsg &m)
{
	if (r.readU32() != kProtocolMagic) {
		r.fail();
	}
	m.protocolVersion = r.readU16();
	r.readString(m.gameId);
	m.gameVersion = r.readU32();
	m.sceneHash = r.readU64();
	r.readString(m.playerName);
	m.token = r.readU64();
	return finish(r);
}

bool decode(BitReader &r, WelcomeMsg &m)
{
	m.clientId = r.readU16();
	m.tickRate = r.readU16();
	m.snapshotRate = r.readU16();
	m.serverTick = r.readU32();
	m.maxClients = r.readU16();
	r.readString(m.sceneName);
	return finish(r);
}

bool decode(BitReader &r, RejectMsg &m)
{
	const uint8_t reason = r.readU8();
	if (reason < uint8_t(RejectReason::VersionMismatch) || reason > uint8_t(RejectReason::GameInProgress)) {
		r.fail();
	}
	m.reason = RejectReason(reason);
	r.readString(m.detail);
	return finish(r);
}

bool decode(BitReader &r, DisconnectMsg &m)
{
	const uint8_t reason = r.readU8();
	if (reason < uint8_t(DisconnectReason::Quit) || reason > uint8_t(DisconnectReason::ServerShutdown)) {
		r.fail();
	}
	m.reason = DisconnectReason(reason);
	return finish(r);
}

bool decode(BitReader &r, PingMsg &m)
{
	m.seq = r.readU32();
	m.senderTimeMs = r.readU32();
	return finish(r);
}

bool decode(BitReader &r, PongMsg &m)
{
	m.seq = r.readU32();
	m.echoTimeMs = r.readU32();
	m.serverTick = r.readU32();
	return finish(r);
}

bool decode(BitReader &r, ClientInfoMsg &m)
{
	m.clientId = r.readU16();
	r.readString(m.name);
	m.flags = r.readU8();
	return finish(r);
}

bool decode(BitReader &r, SceneChangeMsg &m)
{
	r.readString(m.sceneName);
	m.sceneHash = r.readU64();
	return finish(r);
}

bool decode(BitReader &r, SceneLoadedMsg &m)
{
	m.sceneHash = r.readU64();
	return finish(r);
}

bool decode(BitReader &r, SpawnMsg &m, const SnapshotConfig &config)
{
	m.netId = r.readU32();
	if (r.ok() && m.netId == kInvalidNetId) {
		r.fail();
	}
	r.readString(m.prototypeName);
	m.owner = r.readU16();
	m.state = ObjectState();
	m.state.id = m.netId;
	if (r.ok()) {
		decodeObjectFields(r, m.state, false, config);
	}
	return finish(r);
}

bool decode(BitReader &r, DespawnMsg &m)
{
	m.netId = r.readU32();
	return finish(r);
}

bool decode(BitReader &r, OwnershipMsg &m)
{
	m.netId = r.readU32();
	m.newOwner = r.readU16();
	return finish(r);
}

bool decode(BitReader &r, SnapshotAckMsg &m)
{
	m.tick = r.readU32();
	return finish(r);
}

bool decode(BitReader &r, InputMsg &m)
{
	m.blocks.clear();
	m.newestTick = r.readU32();
	const uint8_t count = r.readU8();
	if (r.ok() && (count < 1 || count > kMaxInputBlocks)) {
		r.fail();
	}
	for (uint8_t i = 0; i < count && r.ok(); ++i) {
		const uint64_t len = r.readVarU();
		if (!r.ok() || len > kMaxInputBlockBytes || len * 8 > r.bitsRemaining()) {
			r.fail();
			break;
		}
		std::vector<uint8_t> block(static_cast<size_t>(len));
		for (uint8_t &byte : block) {
			byte = r.readU8();
		}
		m.blocks.push_back(std::move(block));
	}
	return finish(r);
}

bool decode(BitReader &r, RpcMsg &m)
{
	m.args.clear();
	m.netId = r.readU32();
	m.rpcId = r.readU16();
	m.tick = r.readU32();
	const size_t argsStart = r.bitPosition();
	const uint8_t count = r.readU8();
	for (uint8_t n = 0; n < count && r.ok(); ++n) {
		RpcArg a;
		a.type = RpcArgType(r.readU8());
		switch (a.type) {
			case RpcArgType::Bool: {
				const uint8_t v = r.readU8();
				if (v > 1) {
					r.fail();
				}
				a.b = (v == 1);
				break;
			}
			case RpcArgType::Int:
				a.i = r.readVarI();
				break;
			case RpcArgType::Float:
				a.v[0] = readFloat32(r);
				break;
			case RpcArgType::Vec3:
				for (int i = 0; i < 3; ++i) {
					a.v[i] = readFloat32(r);
				}
				break;
			case RpcArgType::Quat:
				for (int i = 0; i < 4; ++i) {
					a.v[i] = readFloat32(r);
				}
				break;
			case RpcArgType::Str:
				r.readString(a.s);
				break;
			case RpcArgType::NetId:
				a.id = r.readU32();
				break;
			default:
				r.fail();
				break;
		}
		if (r.ok()) {
			m.args.push_back(std::move(a));
		}
	}
	if (r.ok() && r.bitPosition() - argsStart > kMaxRpcArgsBytes * 8) {
		r.fail();
	}
	return finish(r);
}

bool decode(BitReader &r, FullStateRequestMsg &)
{
	return finish(r);
}

bool decode(BitReader &r, RpcFromMsg &m)
{
	m.fromClient = r.readU16();
	return decode(r, m.rpc);
}

bool decode(BitReader &r, InputTimingMsg &m)
{
	m.tick = r.readU32();
	m.slackQ4 = int16_t(r.readU16());
	return finish(r);
}

bool decode(BitReader &r, ChatMsg &m)
{
	m.fromClient = r.readU16();
	readLimitedString(r, m.text, kMaxChatBytes);
	return finish(r);
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Snapshot
 * \{ */

bool encodeSnapshotMessage(std::vector<uint8_t> &packet, Tick tick, const std::vector<ObjectState> &objects,
                           const Snapshot *baseline, const SnapshotConfig &config)
{
	std::vector<uint8_t> body;
	BitWriter w(body);
	if (!encodeSnapshot(w, tick, objects, baseline, config)) {
		return false;
	}
	return appendRawMessage(packet, MessageType::Snapshot, body);
}

bool decodeSnapshotMessage(const RawMessage &msg, const Snapshot *baseline, const SnapshotConfig &config,
                           Snapshot &out)
{
	if (msg.type != uint8_t(MessageType::Snapshot)) {
		return false;
	}
	BitReader r(msg.body, msg.size);
	if (!decodeSnapshot(r, baseline, config, out) || !finish(r)) {
		out.objects.clear();
		return false;
	}
	return true;
}

/** \} */

}  // namespace net
