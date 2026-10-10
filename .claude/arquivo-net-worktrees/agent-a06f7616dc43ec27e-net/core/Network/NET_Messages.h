/* SPDX-License-Identifier: GPL-2.0-or-later */

/** \file NET_Messages.h
 *  Message bodies (protocol contract v1, section 5) and the per-message header (section 4.3).
 *
 *  Every message struct has:
 *    static constexpr MessageType kType;
 *    void encode(BitWriter &) const;   // check BitWriter::ok() afterwards
 *    bool decode(BitReader &);         // false on invalid body, never reads out of bounds
 */

#pragma once

#include "NET_BitStream.h"
#include "NET_Types.h"

#include <string>
#include <string_view>
#include <vector>

namespace net {

struct HelloMsg {
	static constexpr MessageType kType = MessageType::Hello;
	uint32_t magic = kProtocolMagic;
	uint16_t protocolVersion = kProtocolVersion;
	std::string gameId;
	uint32_t gameVersion = 0;
	uint64_t sceneHash = 0;
	std::string playerName;
	uint64_t token = 0;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct WelcomeMsg {
	static constexpr MessageType kType = MessageType::Welcome;
	ClientId clientId = 0;
	uint16_t tickRate = 0;
	uint16_t snapshotRate = 0;
	Tick serverTick = 0;
	uint16_t maxClients = 0;
	std::string sceneName;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct RejectMsg {
	static constexpr MessageType kType = MessageType::Reject;
	RejectReason reason = RejectReason::VersionMismatch;
	std::string detail;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct DisconnectMsg {
	static constexpr MessageType kType = MessageType::Disconnect;
	DisconnectReason reason = DisconnectReason::Quit;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct PingMsg {
	static constexpr MessageType kType = MessageType::Ping;
	uint32_t seq = 0;
	uint32_t senderTimeMs = 0;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct PongMsg {
	static constexpr MessageType kType = MessageType::Pong;
	uint32_t seq = 0;
	uint32_t echoTimeMs = 0;
	Tick serverTick = 0;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct ClientInfoMsg {
	static constexpr MessageType kType = MessageType::ClientInfo;
	ClientId clientId = 0;
	std::string name;
	uint8_t flags = 0; // ClientInfoFlags
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct SceneChangeMsg {
	static constexpr MessageType kType = MessageType::SceneChange;
	std::string sceneName;
	uint64_t sceneHash = 0;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct SceneLoadedMsg {
	static constexpr MessageType kType = MessageType::SceneLoaded;
	uint64_t sceneHash = 0;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

/** initialState holds one object state block as written by encodeObjectState() (NET_Snapshot.h);
 *  it takes the rest of the body. */
struct SpawnMsg {
	static constexpr MessageType kType = MessageType::Spawn;
	NetId netId = 0;
	std::string prototypeName;
	ClientId owner = 0;
	std::vector<uint8_t> initialState;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct DespawnMsg {
	static constexpr MessageType kType = MessageType::Despawn;
	NetId netId = 0;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct OwnershipMsg {
	static constexpr MessageType kType = MessageType::Ownership;
	NetId netId = 0;
	ClientId newOwner = 0;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

/** Raw snapshot body (section 6); decoded by decodeSnapshot() against a baseline. */
struct SnapshotMsg {
	static constexpr MessageType kType = MessageType::Snapshot;
	std::vector<uint8_t> data;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct SnapshotAckMsg {
	static constexpr MessageType kType = MessageType::SnapshotAck;
	Tick tick = 0;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

/** blocks[0] is the input of newestTick, blocks[i] of newestTick - i. Each block is <= 64 bytes and
 *  is written as varu length + bytes. */
struct InputMsg {
	static constexpr MessageType kType = MessageType::Input;
	Tick newestTick = 0;
	std::vector<std::vector<uint8_t>> blocks; // 1..8
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct RpcArg {
	RpcArgType type = RpcArgType::Bool;
	bool b = false;
	int64_t i = 0;
	float f[4] = {0.0f, 0.0f, 0.0f, 0.0f}; // Float: f[0]; Vec3: f[0..2]; Quat: x,y,z,w
	std::string s;
	NetId netId = 0;

	static RpcArg makeBool(bool v);
	static RpcArg makeInt(int64_t v);
	static RpcArg makeFloat(float v);
	static RpcArg makeVec3(float x, float y, float z);
	static RpcArg makeQuat(float x, float y, float z, float w);
	static RpcArg makeStr(std::string_view v);
	static RpcArg makeNetId(NetId v);
	bool operator==(const RpcArg &o) const;
};

struct RpcMsg {
	static constexpr MessageType kType = MessageType::Rpc;
	NetId netId = 0; // 0 = global
	uint16_t rpcId = 0;
	Tick tick = 0;
	std::vector<RpcArg> args; // <= 255, encoded size <= 1024 bytes
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct FullStateRequestMsg {
	static constexpr MessageType kType = MessageType::FullStateRequest;
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

struct ChatMsg {
	static constexpr MessageType kType = MessageType::Chat;
	ClientId fromClient = 0;
	std::string text; // <= 200 bytes
	void encode(BitWriter &w) const;
	bool decode(BitReader &r);
};

/* -------------------------------------------------------------------- */
/* Framing (section 4.3): u8 type, varu len (<= 3 bytes), body. */

constexpr size_t kMaxMessageBody = (size_t(1) << 21) - 1; // 3-byte LEB128 limit

/** Appends header + body to packet. Returns false (packet untouched) if the body is too big. */
bool appendMessage(std::vector<uint8_t> &packet, uint8_t type, const uint8_t *body, size_t size);

/** Encodes msg and appends it to packet. Returns false (packet untouched) on encode error. */
template<typename T> bool appendMessage(std::vector<uint8_t> &packet, const T &msg)
{
	std::vector<uint8_t> body;
	BitWriter w(body);
	msg.encode(w);
	if (!w.ok()) {
		return false;
	}
	return appendMessage(packet, uint8_t(T::kType), body.data(), body.size());
}

/** View on one message inside a packet. */
struct MessageView {
	uint8_t type = 0;
	const uint8_t *body = nullptr;
	size_t size = 0;

	template<typename T> bool decode(T &msg) const
	{
		if (type != uint8_t(T::kType)) {
			return false;
		}
		BitReader r(body, size);
		return msg.decode(r) && r.ok();
	}
};

/** Iterates the messages of a packet. Unknown types are skipped using len. */
class MessageReader {
public:
	MessageReader(const uint8_t *data, size_t size);

	/** Next known message. Returns false at the end of the packet or on error (see error()). */
	bool next(MessageView &out);
	/** True if the packet is malformed: len past the end, bad varint, or more than 64 messages. */
	bool error() const;
	int skippedUnknown() const;

private:
	const uint8_t *m_data;
	size_t m_size;
	size_t m_pos;
	int m_count;
	int m_skipped;
	bool m_error;
};

/** sceneHash (section 3): FNV-1a 64 over the sorted NetIds (u32 little-endian each), then the
 *  UTF-8 bytes of the scene name. ids does not need to be sorted. */
uint64_t computeSceneHash(std::vector<NetId> ids, std::string_view sceneName);

} // namespace net
