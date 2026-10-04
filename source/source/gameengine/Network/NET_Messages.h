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

/** \file NET_Messages.h
 *  \ingroup network
 *  \brief Message header (contract 4.3) and message bodies (contract section 5).
 *
 * encode() writes the body only; appendMessage() adds the header to a packet.
 * decode() expects a reader over exactly one body and returns false for any invalid
 * or trailing data. It never reads past the buffer.
 */

#ifndef __NET_MESSAGES_H__
#define __NET_MESSAGES_H__

#include "NET_BitStream.h"
#include "NET_Snapshot.h"
#include "NET_Types.h"

#include <string>
#include <vector>

namespace net {

/* -------------------------------------------------------------------- */
/** \name Packet framing
 * \{ */

struct RawMessage {
	uint8_t type = 0;
	const uint8_t *body = nullptr;
	size_t size = 0;
};

/// Appends "u8 type, varu len, body" to packet. Fails if the body is above the reliable limit.
bool appendRawMessage(std::vector<uint8_t> &packet, uint8_t type, const uint8_t *body, size_t size);
bool appendRawMessage(std::vector<uint8_t> &packet, MessageType type, const std::vector<uint8_t> &body);

/// Iterates the messages of a packet. Unknown types are returned too, so the caller can skip
/// them; a length past the end of the packet or more than 64 messages is an error.
class PacketReader {
public:
	PacketReader(const uint8_t *data, size_t size);

	/// False at the end of the packet or on error (check ok()).
	bool next(RawMessage &msg);
	bool ok() const;
	size_t count() const;

private:
	const uint8_t *m_data;
	size_t m_size;
	size_t m_pos;
	size_t m_count;
	bool m_ok;
};

/** \} */

/* -------------------------------------------------------------------- */
/** \name Messages
 * \{ */

struct HelloMsg {
	static constexpr MessageType kType = MessageType::Hello;
	uint16_t protocolVersion = kProtocolVersion;
	std::string gameId;
	uint32_t gameVersion = 0;
	uint64_t sceneHash = 0;
	std::string playerName;
	uint64_t token = 0;
};

struct WelcomeMsg {
	static constexpr MessageType kType = MessageType::Welcome;
	ClientId clientId = 0;
	uint16_t tickRate = 60;
	uint16_t snapshotRate = 20;
	Tick serverTick = kNoTick;
	uint16_t maxClients = 0;
	std::string sceneName;
};

struct RejectMsg {
	static constexpr MessageType kType = MessageType::Reject;
	RejectReason reason = RejectReason::VersionMismatch;
	std::string detail;
};

struct DisconnectMsg {
	static constexpr MessageType kType = MessageType::Disconnect;
	DisconnectReason reason = DisconnectReason::Quit;
};

struct PingMsg {
	static constexpr MessageType kType = MessageType::Ping;
	uint32_t seq = 0;
	uint32_t senderTimeMs = 0;
};

struct PongMsg {
	static constexpr MessageType kType = MessageType::Pong;
	uint32_t seq = 0;
	uint32_t echoTimeMs = 0;
	Tick serverTick = kNoTick;
};

struct ClientInfoMsg {
	static constexpr MessageType kType = MessageType::ClientInfo;
	ClientId clientId = 0;
	std::string name;
	uint8_t flags = 0;  // ClientInfoFlags
};

struct SceneChangeMsg {
	static constexpr MessageType kType = MessageType::SceneChange;
	std::string sceneName;
	uint64_t sceneHash = 0;
};

struct SceneLoadedMsg {
	static constexpr MessageType kType = MessageType::SceneLoaded;
	uint64_t sceneHash = 0;
};

/// state.id is ignored on encode and set to netId on decode.
struct SpawnMsg {
	static constexpr MessageType kType = MessageType::Spawn;
	NetId netId = kInvalidNetId;
	std::string prototypeName;
	ClientId owner = 0;
	ObjectState state;
};

struct DespawnMsg {
	static constexpr MessageType kType = MessageType::Despawn;
	NetId netId = kInvalidNetId;
};

struct OwnershipMsg {
	static constexpr MessageType kType = MessageType::Ownership;
	NetId netId = kInvalidNetId;
	ClientId newOwner = 0;
};

struct SnapshotAckMsg {
	static constexpr MessageType kType = MessageType::SnapshotAck;
	Tick tick = kNoTick;
};

/// Blocks go from the newest tick (newestTick) to the oldest, each up to 64 bytes.
struct InputMsg {
	static constexpr MessageType kType = MessageType::Input;
	Tick newestTick = kNoTick;
	std::vector<std::vector<uint8_t>> blocks;
};

enum class RpcArgType : uint8_t {
	Bool = 1,
	Int = 2,
	Float = 3,
	Vec3 = 4,
	Quat = 5,
	Str = 6,
	NetId = 7,
};

struct RpcArg {
	RpcArgType type = RpcArgType::Bool;
	bool b = false;
	int64_t i = 0;
	float v[4] = {0.0f, 0.0f, 0.0f, 0.0f};  // Float uses v[0], Vec3 v[0..2], Quat x,y,z,w
	std::string s;
	net::NetId id = kInvalidNetId;
};

struct RpcMsg {
	static constexpr MessageType kType = MessageType::Rpc;
	NetId netId = kInvalidNetId;  // 0 = global
	uint16_t rpcId = 0;
	Tick tick = kNoTick;
	std::vector<RpcArg> args;
};

/// Rpc relayed by the server with the client that made the call (provisional message 200).
struct RpcFromMsg {
	static constexpr MessageType kType = MessageType::RpcFrom;
	ClientId fromClient = 0;
	RpcMsg rpc;
};

/// Input slack measured by the server (provisional message 201): newest input tick received minus the next tick
/// to simulate, smoothed, in 1/16 tick. Negative: the inputs arrive after their tick was simulated.
struct InputTimingMsg {
	static constexpr MessageType kType = MessageType::InputTiming;
	Tick tick = kNoTick;  // server tick of the measurement
	int16_t slackQ4 = 0;
};

struct FullStateRequestMsg {
	static constexpr MessageType kType = MessageType::FullStateRequest;
};

struct ChatMsg {
	static constexpr MessageType kType = MessageType::Chat;
	ClientId fromClient = 0;
	std::string text;
};

bool encode(BitWriter &w, const HelloMsg &m);
bool encode(BitWriter &w, const WelcomeMsg &m);
bool encode(BitWriter &w, const RejectMsg &m);
bool encode(BitWriter &w, const DisconnectMsg &m);
bool encode(BitWriter &w, const PingMsg &m);
bool encode(BitWriter &w, const PongMsg &m);
bool encode(BitWriter &w, const ClientInfoMsg &m);
bool encode(BitWriter &w, const SceneChangeMsg &m);
bool encode(BitWriter &w, const SceneLoadedMsg &m);
bool encode(BitWriter &w, const SpawnMsg &m, const SnapshotConfig &config);
bool encode(BitWriter &w, const DespawnMsg &m);
bool encode(BitWriter &w, const OwnershipMsg &m);
bool encode(BitWriter &w, const SnapshotAckMsg &m);
bool encode(BitWriter &w, const InputMsg &m);
bool encode(BitWriter &w, const RpcMsg &m);
bool encode(BitWriter &w, const RpcFromMsg &m);
bool encode(BitWriter &w, const InputTimingMsg &m);
bool encode(BitWriter &w, const FullStateRequestMsg &m);
bool encode(BitWriter &w, const ChatMsg &m);

bool decode(BitReader &r, HelloMsg &m);
bool decode(BitReader &r, WelcomeMsg &m);
bool decode(BitReader &r, RejectMsg &m);
bool decode(BitReader &r, DisconnectMsg &m);
bool decode(BitReader &r, PingMsg &m);
bool decode(BitReader &r, PongMsg &m);
bool decode(BitReader &r, ClientInfoMsg &m);
bool decode(BitReader &r, SceneChangeMsg &m);
bool decode(BitReader &r, SceneLoadedMsg &m);
bool decode(BitReader &r, SpawnMsg &m, const SnapshotConfig &config);
bool decode(BitReader &r, DespawnMsg &m);
bool decode(BitReader &r, OwnershipMsg &m);
bool decode(BitReader &r, SnapshotAckMsg &m);
bool decode(BitReader &r, InputMsg &m);
bool decode(BitReader &r, RpcMsg &m);
bool decode(BitReader &r, RpcFromMsg &m);
bool decode(BitReader &r, InputTimingMsg &m);
bool decode(BitReader &r, FullStateRequestMsg &m);
bool decode(BitReader &r, ChatMsg &m);

/// Snapshot message body (section 6), see encodeSnapshot/decodeSnapshot.
bool encodeSnapshotMessage(std::vector<uint8_t> &packet, Tick tick, const std::vector<ObjectState> &objects,
                           const Snapshot *baseline, const SnapshotConfig &config);
bool decodeSnapshotMessage(const RawMessage &msg, const Snapshot *baseline, const SnapshotConfig &config,
                           Snapshot &out);

/// Encodes a message and appends it with its header to packet.
template <class Msg, class... Extra>
bool appendMessage(std::vector<uint8_t> &packet, const Msg &msg, const Extra &...extra)
{
	std::vector<uint8_t> body;
	BitWriter w(body);
	if (!encode(w, msg, extra...)) {
		return false;
	}
	return appendRawMessage(packet, Msg::kType, body);
}

/// Decodes a message returned by PacketReader; fails if the type does not match.
template <class Msg, class... Extra>
bool decodeMessage(const RawMessage &raw, Msg &msg, const Extra &...extra)
{
	if (raw.type != uint8_t(Msg::kType)) {
		return false;
	}
	BitReader r(raw.body, raw.size);
	return decode(r, msg, extra...);
}

/** \} */

}  // namespace net

#endif  // __NET_MESSAGES_H__
