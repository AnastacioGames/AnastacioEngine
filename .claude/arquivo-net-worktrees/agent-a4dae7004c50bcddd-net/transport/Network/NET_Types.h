/* PROVISIONAL (Frente B): minimal version of the Frente A header, following
 * docs/multiplayer-protocol.md sections 2, 3 and 5. On merge, prefer net/core's file. */

#pragma once

#include <cstdint>

namespace net {

using Tick = uint32_t;
using NetId = uint32_t;
using ClientId = uint16_t;

inline bool tickNewer(Tick a, Tick b)
{
	return int32_t(a - b) > 0;
}

constexpr uint16_t kProtocolVersion = 1;
constexpr uint32_t kProtocolMagic = 0x54454E41u; /* 'ANET' read as little-endian u32 */

enum class MessageType : uint8_t {
	Hello = 1,
	Welcome = 2,
	Reject = 3,
	Disconnect = 4,
	Ping = 5,
	Pong = 6,
	ClientInfo = 7,
	SceneChange = 8,
	SceneLoaded = 9,
	Spawn = 10,
	Despawn = 11,
	Ownership = 12,
	Snapshot = 13,
	SnapshotAck = 14,
	Input = 15,
	Rpc = 16,
	FullStateRequest = 17,
	Chat = 18,
};

enum class RejectReason : uint8_t {
	VersionMismatch = 1,
	SceneMismatch = 2,
	ServerFull = 3,
	BadToken = 4,
	Banned = 5,
	GameInProgress = 6,
};

enum class DisconnectReason : uint8_t {
	Quit = 1,
	Timeout = 2,
	Kicked = 3,
	ProtocolViolation = 4,
	ServerShutdown = 5,
};

}  // namespace net
