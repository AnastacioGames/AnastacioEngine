/* SPDX-License-Identifier: GPL-2.0-or-later */

/** \file NET_Messages.cpp
 */

#include "NET_Messages.h"

#include <algorithm>

namespace net {

/* All message bodies are byte aligned: every field is a whole number of bytes. */

void HelloMsg::encode(BitWriter &w) const
{
	w.writeU32(magic);
	w.writeU16(protocolVersion);
	w.writeString(gameId);
	w.writeU32(gameVersion);
	w.writeU64(sceneHash);
	w.writeString(playerName);
	w.writeU64(token);
}

bool HelloMsg::decode(BitReader &r)
{
	magic = r.readU32();
	protocolVersion = r.readU16();
	r.readString(gameId);
	gameVersion = r.readU32();
	sceneHash = r.readU64();
	r.readString(playerName);
	token = r.readU64();
	return r.ok();
}

void WelcomeMsg::encode(BitWriter &w) const
{
	w.writeU16(clientId);
	w.writeU16(tickRate);
	w.writeU16(snapshotRate);
	w.writeU32(serverTick);
	w.writeU16(maxClients);
	w.writeString(sceneName);
}

bool WelcomeMsg::decode(BitReader &r)
{
	clientId = r.readU16();
	tickRate = r.readU16();
	snapshotRate = r.readU16();
	serverTick = r.readU32();
	maxClients = r.readU16();
	r.readString(sceneName);
	return r.ok();
}

void RejectMsg::encode(BitWriter &w) const
{
	w.writeU8(uint8_t(reason));
	w.writeString(detail);
}

bool RejectMsg::decode(BitReader &r)
{
	const uint8_t v = r.readU8();
	r.readString(detail);
	if (!r.ok() || v < uint8_t(RejectReason::VersionMismatch) || v > uint8_t(RejectReason::GameInProgress)) {
		return false;
	}
	reason = RejectReason(v);
	return true;
}

void DisconnectMsg::encode(BitWriter &w) const
{
	w.writeU8(uint8_t(reason));
}

bool DisconnectMsg::decode(BitReader &r)
{
	const uint8_t v = r.readU8();
	if (!r.ok() || v < uint8_t(DisconnectReason::Quit) || v > uint8_t(DisconnectReason::ServerShutdown)) {
		return false;
	}
	reason = DisconnectReason(v);
	return true;
}

void PingMsg::encode(BitWriter &w) const
{
	w.writeU32(seq);
	w.writeU32(senderTimeMs);
}

bool PingMsg::decode(BitReader &r)
{
	seq = r.readU32();
	senderTimeMs = r.readU32();
	return r.ok();
}

void PongMsg::encode(BitWriter &w) const
{
	w.writeU32(seq);
	w.writeU32(echoTimeMs);
	w.writeU32(serverTick);
}

bool PongMsg::decode(BitReader &r)
{
	seq = r.readU32();
	echoTimeMs = r.readU32();
	serverTick = r.readU32();
	return r.ok();
}

void ClientInfoMsg::encode(BitWriter &w) const
{
	w.writeU16(clientId);
	w.writeString(name);
	w.writeU8(flags);
}

bool ClientInfoMsg::decode(BitReader &r)
{
	clientId = r.readU16();
	r.readString(name);
	flags = r.readU8();
	return r.ok();
}

void SceneChangeMsg::encode(BitWriter &w) const
{
	w.writeString(sceneName);
	w.writeU64(sceneHash);
}

bool SceneChangeMsg::decode(BitReader &r)
{
	r.readString(sceneName);
	sceneHash = r.readU64();
	return r.ok();
}

void SceneLoadedMsg::encode(BitWriter &w) const
{
	w.writeU64(sceneHash);
}

bool SceneLoadedMsg::decode(BitReader &r)
{
	sceneHash = r.readU64();
	return r.ok();
}

void SpawnMsg::encode(BitWriter &w) const
{
	w.writeU32(netId);
	w.writeString(prototypeName);
	w.writeU16(owner);
	w.writeBytes(initialState.data(), initialState.size());
}

bool SpawnMsg::decode(BitReader &r)
{
	netId = r.readU32();
	r.readString(prototypeName);
	owner = r.readU16();
	if (!r.ok()) {
		return false;
	}
	initialState.resize(r.bitsRemaining() / 8);
	r.readBytes(initialState.data(), initialState.size());
	return r.ok() && netId != 0;
}

void DespawnMsg::encode(BitWriter &w) const
{
	w.writeU32(netId);
}

bool DespawnMsg::decode(BitReader &r)
{
	netId = r.readU32();
	return r.ok() && netId != 0;
}

void OwnershipMsg::encode(BitWriter &w) const
{
	w.writeU32(netId);
	w.writeU16(newOwner);
}

bool OwnershipMsg::decode(BitReader &r)
{
	netId = r.readU32();
	newOwner = r.readU16();
	return r.ok() && netId != 0;
}

void SnapshotMsg::encode(BitWriter &w) const
{
	w.writeBytes(data.data(), data.size());
}

bool SnapshotMsg::decode(BitReader &r)
{
	data.resize(r.bitsRemaining() / 8);
	r.readBytes(data.data(), data.size());
	return r.ok();
}

void SnapshotAckMsg::encode(BitWriter &w) const
{
	w.writeU32(tick);
}

bool SnapshotAckMsg::decode(BitReader &r)
{
	tick = r.readU32();
	return r.ok();
}

void InputMsg::encode(BitWriter &w) const
{
	if (blocks.empty() || blocks.size() > size_t(kMaxInputTicks)) {
		w.fail();
		return;
	}
	w.writeU32(newestTick);
	w.writeU8(uint8_t(blocks.size()));
	for (const std::vector<uint8_t> &b : blocks) {
		if (b.size() > kMaxInputBlockBytes) {
			w.fail();
			return;
		}
		w.writeVarU(b.size());
		w.writeBytes(b.data(), b.size());
	}
}

bool InputMsg::decode(BitReader &r)
{
	blocks.clear();
	newestTick = r.readU32();
	const uint8_t count = r.readU8();
	if (!r.ok() || count < 1 || count > kMaxInputTicks) {
		return false;
	}
	blocks.resize(count);
	for (std::vector<uint8_t> &b : blocks) {
		const uint64_t len = r.readVarU();
		if (!r.ok() || len > kMaxInputBlockBytes) {
			blocks.clear();
			return false;
		}
		b.resize(size_t(len));
		if (!r.readBytes(b.data(), b.size())) {
			blocks.clear();
			return false;
		}
	}
	return true;
}

/* -------------------------------------------------------------------- */
/* RPC */

RpcArg RpcArg::makeBool(bool v)
{
	RpcArg a;
	a.type = RpcArgType::Bool;
	a.b = v;
	return a;
}

RpcArg RpcArg::makeInt(int64_t v)
{
	RpcArg a;
	a.type = RpcArgType::Int;
	a.i = v;
	return a;
}

RpcArg RpcArg::makeFloat(float v)
{
	RpcArg a;
	a.type = RpcArgType::Float;
	a.f[0] = v;
	return a;
}

RpcArg RpcArg::makeVec3(float x, float y, float z)
{
	RpcArg a;
	a.type = RpcArgType::Vec3;
	a.f[0] = x;
	a.f[1] = y;
	a.f[2] = z;
	return a;
}

RpcArg RpcArg::makeQuat(float x, float y, float z, float w)
{
	RpcArg a;
	a.type = RpcArgType::Quat;
	a.f[0] = x;
	a.f[1] = y;
	a.f[2] = z;
	a.f[3] = w;
	return a;
}

RpcArg RpcArg::makeStr(std::string_view v)
{
	RpcArg a;
	a.type = RpcArgType::Str;
	a.s = std::string(v);
	return a;
}

RpcArg RpcArg::makeNetId(NetId v)
{
	RpcArg a;
	a.type = RpcArgType::NetId;
	a.netId = v;
	return a;
}

static int rpcFloatCount(RpcArgType t)
{
	switch (t) {
		case RpcArgType::Float:
			return 1;
		case RpcArgType::Vec3:
			return 3;
		case RpcArgType::Quat:
			return 4;
		default:
			return 0;
	}
}

bool RpcArg::operator==(const RpcArg &o) const
{
	if (type != o.type) {
		return false;
	}
	switch (type) {
		case RpcArgType::Bool:
			return b == o.b;
		case RpcArgType::Int:
			return i == o.i;
		case RpcArgType::Str:
			return s == o.s;
		case RpcArgType::NetId:
			return netId == o.netId;
		default:
			return std::equal(f, f + rpcFloatCount(type), o.f);
	}
}

/* Argument encoding: u8 type, then bool = u8 0/1, int = varint zigzag, float/vec3/quat = raw
 * IEEE-754 floats (u32 each), str = str, netId = u32. */
static void writeRpcArgs(BitWriter &w, const std::vector<RpcArg> &args)
{
	if (args.size() > 255) {
		w.fail();
		return;
	}
	w.writeU8(uint8_t(args.size()));
	for (const RpcArg &a : args) {
		w.writeU8(uint8_t(a.type));
		switch (a.type) {
			case RpcArgType::Bool:
				w.writeU8(a.b ? 1 : 0);
				break;
			case RpcArgType::Int:
				w.writeVarI(a.i);
				break;
			case RpcArgType::Float:
			case RpcArgType::Vec3:
			case RpcArgType::Quat:
				for (int k = 0; k < rpcFloatCount(a.type); ++k) {
					w.writeFloat(a.f[k]);
				}
				break;
			case RpcArgType::Str:
				w.writeString(a.s);
				break;
			case RpcArgType::NetId:
				w.writeU32(a.netId);
				break;
			default:
				w.fail();
				return;
		}
	}
}

void RpcMsg::encode(BitWriter &w) const
{
	std::vector<uint8_t> argBytes;
	BitWriter aw(argBytes);
	writeRpcArgs(aw, args);
	if (!aw.ok() || argBytes.size() > kMaxRpcArgsBytes) {
		w.fail();
		return;
	}
	w.writeU32(netId);
	w.writeU16(rpcId);
	w.writeU32(tick);
	w.writeBytes(argBytes.data(), argBytes.size());
}

bool RpcMsg::decode(BitReader &r)
{
	args.clear();
	netId = r.readU32();
	rpcId = r.readU16();
	tick = r.readU32();
	const size_t argStart = r.bytePosition();
	const uint8_t count = r.readU8();
	if (!r.ok()) {
		return false;
	}
	args.resize(count);
	for (RpcArg &a : args) {
		const uint8_t t = r.readU8();
		if (!r.ok() || t > uint8_t(RpcArgType::NetId)) {
			args.clear();
			return false;
		}
		a.type = RpcArgType(t);
		switch (a.type) {
			case RpcArgType::Bool: {
				const uint8_t v = r.readU8();
				if (v > 1) {
					r.fail();
				}
				a.b = v != 0;
				break;
			}
			case RpcArgType::Int:
				a.i = r.readVarI();
				break;
			case RpcArgType::Float:
			case RpcArgType::Vec3:
			case RpcArgType::Quat:
				for (int k = 0; k < rpcFloatCount(a.type); ++k) {
					a.f[k] = r.readFloat();
				}
				break;
			case RpcArgType::Str:
				r.readString(a.s);
				break;
			case RpcArgType::NetId:
				a.netId = r.readU32();
				break;
		}
		if (!r.ok() || r.bytePosition() - argStart > kMaxRpcArgsBytes) {
			args.clear();
			return false;
		}
	}
	return true;
}

void FullStateRequestMsg::encode(BitWriter & /*w*/) const
{
}

bool FullStateRequestMsg::decode(BitReader &r)
{
	return r.ok();
}

void ChatMsg::encode(BitWriter &w) const
{
	if (text.size() > kMaxChatBytes) {
		w.fail();
		return;
	}
	w.writeU16(fromClient);
	w.writeString(text);
}

bool ChatMsg::decode(BitReader &r)
{
	fromClient = r.readU16();
	r.readString(text);
	return r.ok() && text.size() <= kMaxChatBytes;
}

/* -------------------------------------------------------------------- */
/* Framing */

bool appendMessage(std::vector<uint8_t> &packet, uint8_t type, const uint8_t *body, size_t size)
{
	if (size > kMaxMessageBody || size > kMaxReliableMessage) {
		return false;
	}
	BitWriter w(packet);
	w.writeU8(type);
	w.writeVarU(size);
	w.writeBytes(body, size);
	return w.ok();
}

MessageReader::MessageReader(const uint8_t *data, size_t size)
	:m_data(data),
	m_size(data ? size : 0),
	m_pos(0),
	m_count(0),
	m_skipped(0),
	m_error(false)
{
}

bool MessageReader::next(MessageView &out)
{
	while (!m_error && m_pos < m_size) {
		if (m_count >= kMaxMessagesPerPacket) {
			m_error = true;
			return false;
		}
		const uint8_t type = m_data[m_pos++];
		/* varu len, at most 3 bytes. */
		uint64_t len = 0;
		bool done = false;
		for (int i = 0; i < 3; ++i) {
			if (m_pos >= m_size) {
				break;
			}
			const uint8_t byte = m_data[m_pos++];
			len |= uint64_t(byte & 0x7Fu) << (7 * i);
			if ((byte & 0x80u) == 0) {
				done = true;
				break;
			}
		}
		if (!done || len > m_size - m_pos) {
			m_error = true;
			return false;
		}
		++m_count;
		const uint8_t *body = m_data + m_pos;
		m_pos += size_t(len);
		if (!isKnownMessageType(type)) {
			++m_skipped;
			continue;
		}
		out.type = type;
		out.body = body;
		out.size = size_t(len);
		return true;
	}
	return false;
}

bool MessageReader::error() const
{
	return m_error;
}

int MessageReader::skippedUnknown() const
{
	return m_skipped;
}

uint64_t computeSceneHash(std::vector<NetId> ids, std::string_view sceneName)
{
	std::sort(ids.begin(), ids.end());
	uint64_t h = kFnvOffset64;
	auto mix = [&h](uint8_t b) {
		h ^= b;
		h *= kFnvPrime64;
	};
	for (NetId id : ids) {
		for (int i = 0; i < 4; ++i) {
			mix(uint8_t(id >> (8 * i)));
		}
	}
	for (char c : sceneName) {
		mix(uint8_t(c));
	}
	return h;
}

} // namespace net
