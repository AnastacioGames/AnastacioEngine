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

/** \file NET_Types.h
 *  \ingroup network
 *  \brief Basic network types (protocol contract, sections 2, 3 and 5).
 */

#ifndef __NET_TYPES_H__
#define __NET_TYPES_H__

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <string_view>
#include <vector>

namespace net {

/// Fixed logic step counter, starts at 1 when the session opens. 0 = no tick.
using Tick = uint32_t;
/// Replicated object id. 0 = invalid; high bit set = spawned at runtime by the server.
using NetId = uint32_t;
/// 0 = server/host, clients are 1..maxClients.
using ClientId = uint16_t;

constexpr Tick kNoTick = 0;
constexpr NetId kInvalidNetId = 0;
constexpr NetId kFirstRuntimeNetId = 0x80000000u;
constexpr ClientId kServerClientId = 0;

constexpr uint16_t kProtocolVersion = 1;
/// 'ANET' as it appears on the wire (bytes 'A','N','E','T', little-endian u32).
constexpr uint32_t kProtocolMagic = 0x54454E41u;

/// Section 4.2 limits.
constexpr size_t kMaxUnreliablePayload = 1200;
constexpr size_t kMaxReliableMessage = 65536;
constexpr size_t kMaxMessagesPerPacket = 64;
constexpr int kMaxRpcPerSecond = 120;
constexpr size_t kMaxBytesPerSecond = 64 * 1024;
constexpr int kMaxPendingConnections = 16;
constexpr int kPendingTimeoutMs = 5000;
constexpr int kConnectionTimeoutMs = 10000;
constexpr int kMaxClients = 64;
constexpr int kMaxViolations = 10;
constexpr int kViolationWindowMs = 10000;
constexpr int kReconnectWindowMs = 30000;

/// Section 4.3: message length varint is at most 3 bytes.
constexpr int kMaxMessageLengthBytes = 3;
constexpr size_t kMaxStringBytes = 255;
constexpr size_t kMaxChatBytes = 200;
constexpr size_t kMaxInputBlockBytes = 64;
constexpr int kMaxInputBlocks = 8;
constexpr size_t kMaxRpcArgsBytes = 1024;
/// Snapshots kept per client for delta baselines (section 6).
constexpr int kSnapshotHistory = 64;

/// Tick comparison with wrap-around: true when a is newer than b.
inline bool tickNewer(Tick a, Tick b)
{
	return int32_t(a - b) > 0;
}

inline bool isRuntimeNetId(NetId id)
{
	return id >= kFirstRuntimeNetId;
}

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

inline bool isKnownMessageType(uint8_t type)
{
	return type >= kFirstMessageType && type <= kLastMessageType;
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

/// ClientInfo flags.
enum ClientInfoFlags : uint8_t {
	CLIENT_CONNECTED = 1 << 0,
	CLIENT_READY = 1 << 1,
};

/// Logical channel index of each message (section 4.1 / 5). Ping and Pong use the
/// control channel by default but may be sent unreliably on 2/3.
inline uint8_t messageChannel(MessageType type)
{
	switch (type) {
		case MessageType::Rpc:
		case MessageType::Chat:
			return 1;
		case MessageType::Snapshot:
			return 2;
		case MessageType::SnapshotAck:
		case MessageType::Input:
			return 3;
		default:
			return 0;
	}
}

/// FNV-1a 64 over the sorted scene NetIds (4 bytes little-endian each) followed by
/// the scene name bytes (section 3).
inline uint64_t sceneHash(std::string_view sceneName, std::vector<NetId> ids)
{
	uint64_t hash = 0xcbf29ce484222325ull;
	const auto mix = [&hash](uint8_t byte) {
		hash ^= byte;
		hash *= 0x100000001b3ull;
	};
	std::sort(ids.begin(), ids.end());
	for (NetId id : ids) {
		for (int i = 0; i < 4; ++i) {
			mix(uint8_t(id >> (8 * i)));
		}
	}
	for (char c : sceneName) {
		mix(uint8_t(c));
	}
	return hash;
}

}  // namespace net

#endif  // __NET_TYPES_H__
