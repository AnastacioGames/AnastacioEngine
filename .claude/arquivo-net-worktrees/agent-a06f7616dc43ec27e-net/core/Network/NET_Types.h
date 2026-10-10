/* SPDX-License-Identifier: GPL-2.0-or-later */

/** \file NET_Types.h
 *  Basic network types (protocol contract v1, sections 2, 3 and 5).
 */

#pragma once

#include <cstddef>
#include <cstdint>

namespace net {

using Tick = uint32_t;     // 0 = no tick, starts at 1
using NetId = uint32_t;    // 0 = invalid
using ClientId = uint16_t; // 0 = server/host

/** Wrap-aware tick comparison: true if a is newer than b. */
inline bool tickNewer(Tick a, Tick b)
{
	return int32_t(a - b) > 0;
}

constexpr NetId kFirstSceneNetId = 0x00000001u;
constexpr NetId kLastSceneNetId = 0x7FFFFFFFu;
constexpr NetId kFirstRuntimeNetId = 0x80000000u;

inline bool isSceneNetId(NetId id)
{
	return id >= kFirstSceneNetId && id <= kLastSceneNetId;
}

inline bool isRuntimeNetId(NetId id)
{
	return id >= kFirstRuntimeNetId;
}

constexpr uint32_t kProtocolMagic = 0x54454E41u; // 'A','N','E','T' as bytes on the wire
constexpr uint16_t kProtocolVersion = 1;

/* Limits (section 4.2). */
constexpr size_t kMaxUnreliablePayload = 1200;
constexpr size_t kMaxReliableMessage = 65536;
constexpr int kMaxMessagesPerPacket = 64;
constexpr int kMaxRpcPerSecond = 120;
constexpr size_t kMaxBytesPerSecond = 64 * 1024;
constexpr int kMaxPendingConnections = 16;
constexpr int kPendingTimeoutMs = 5000;
constexpr int kConnectionTimeoutMs = 10000;
constexpr int kMaxClients = 64;
constexpr int kViolationLimit = 10;
constexpr int kViolationWindowMs = 10000;
constexpr int kReconnectWindowMs = 30000;

/* Field size limits (sections 5, 7, 8). */
constexpr size_t kMaxStringBytes = 255;
constexpr size_t kMaxChatBytes = 200;
constexpr int kMaxInputTicks = 8;
constexpr size_t kMaxInputBlockBytes = 64;
constexpr size_t kMaxRpcArgsBytes = 1024;
constexpr int kSnapshotHistory = 64;

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

constexpr uint8_t kFirstMessageType = 1;
constexpr uint8_t kLastMessageType = 18;

inline bool isKnownMessageType(uint8_t t)
{
	return t >= kFirstMessageType && t <= kLastMessageType;
}

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

/** ClientInfo flags. */
enum ClientInfoFlags : uint8_t {
	CLIENT_CONNECTED = 1 << 0,
	CLIENT_READY = 1 << 1,
};

/** RPC argument types (section 8), in contract order. */
enum class RpcArgType : uint8_t {
	Bool = 0,
	Int = 1,
	Float = 2,
	Vec3 = 3,
	Quat = 4,
	Str = 5,
	NetId = 6,
};

/** FNV-1a 64 bits helpers used by sceneHash (section 3). */
constexpr uint64_t kFnvOffset64 = 0xcbf29ce484222325ull;
constexpr uint64_t kFnvPrime64 = 0x100000001b3ull;

} // namespace net
