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

/** \file NET_LanDiscovery.h
 *  \ingroup network
 *  \brief LAN server discovery over UDP broadcast, IPv4 only (format proposed in NOTES-H.md).
 *
 * The server side (LanResponder) answers requests on its own port (7779 by default) with name,
 * game, players and the ENet/WebSocket ports. The client side (LanDiscovery) broadcasts a request
 * and collects the answers with the measured ping. Neither blocks; time comes from the caller.
 */

#ifndef __NET_LAN_DISCOVERY_H__
#define __NET_LAN_DISCOVERY_H__

#include "NET_Types.h"

#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace net {

constexpr uint16_t kLanDiscoveryPort = 7779;
/// 'ALAN' on the wire (bytes 'A','L','A','N').
constexpr uint32_t kLanMagic = 0x4E414C41u;
constexpr uint8_t kLanVersion = 1;
constexpr size_t kMaxLanPacket = 512;
/// Longest gameId, server name and scene name in a LAN packet.
constexpr size_t kMaxLanString = 64;

struct LanRequest {
	uint32_t nonce = 0;
	std::string gameId;
};

struct LanServerInfo {
	std::string gameId;
	uint32_t gameVersion = 0;
	std::string name;
	std::string sceneName;
	uint16_t players = 0;
	uint16_t maxPlayers = 0;
	uint16_t enetPort = 0;  // 0 = none
	uint16_t webSocketPort = 0;  // 0 = none
	bool password = false;
};

/// Encoders fail on strings above kMaxLanString; decoders fail on anything malformed, truncated,
/// with trailing bytes or above kMaxLanPacket. They never read past the buffer.
bool encodeLanRequest(const LanRequest &request, std::vector<uint8_t> &out);
bool decodeLanRequest(const uint8_t *data, size_t size, LanRequest &request);
bool encodeLanResponse(uint32_t nonce, const LanServerInfo &info, std::vector<uint8_t> &out);
bool decodeLanResponse(const uint8_t *data, size_t size, uint32_t &nonce, LanServerInfo &info);

/* -------------------------------------------------------------------- */
/** \name Server side
 * \{ */

struct LanResponderConfig {
	/// Requests answered per second per IPv4 address (burst of the same size).
	uint32_t requestsPerSecond = 4;
	/// Addresses tracked by the rate limit; the least recent one is dropped past this.
	size_t maxTrackedAddresses = 256;
};

struct LanResponderStats {
	uint32_t requests = 0;
	uint32_t answered = 0;
	uint32_t otherGame = 0;
	uint32_t rateLimited = 0;
	uint32_t invalid = 0;
};

class LanResponder {
public:
	explicit LanResponder(const LanResponderConfig &config = LanResponderConfig());
	~LanResponder();
	LanResponder(const LanResponder &) = delete;
	LanResponder &operator=(const LanResponder &) = delete;

	/// Binds the UDP port (0 = any free port, for tests). Strings in info are cut to kMaxLanString.
	bool start(uint16_t port = kLanDiscoveryPort);
	void stop();
	bool running() const;
	uint16_t localPort() const;

	void setInfo(const LanServerInfo &info);
	const LanServerInfo &info() const;

	/// Answers the pending requests.
	void update(uint64_t nowMs);

	const LanResponderStats &stats() const;

private:
	struct Bucket {
		float tokens = 0.0f;
		uint64_t lastMs = 0;
	};

	bool allow(uint32_t address, uint64_t nowMs);

	LanResponderConfig m_config;
	intptr_t m_socket;
	bool m_socketLib = false;
	uint16_t m_port = 0;
	LanServerInfo m_info;
	std::map<uint32_t, Bucket> m_buckets;
	LanResponderStats m_stats;
};

/** \} */

/* -------------------------------------------------------------------- */
/** \name Client side
 * \{ */

struct LanServerEntry {
	/// Dotted IPv4 address the answer came from; connect to it with info.enetPort/webSocketPort.
	std::string address;
	LanServerInfo info;
	/// Round trip of the last answered request, in ms.
	uint32_t pingMs = 0;
	uint64_t lastSeenMs = 0;
};

struct LanDiscoveryStats {
	uint32_t requestsSent = 0;
	uint32_t responses = 0;
	uint32_t otherGame = 0;
	uint32_t unknownNonce = 0;
	uint32_t invalid = 0;
};

class LanDiscovery {
public:
	LanDiscovery();
	~LanDiscovery();
	LanDiscovery(const LanDiscovery &) = delete;
	LanDiscovery &operator=(const LanDiscovery &) = delete;

	/// Opens the client socket (any free port, broadcast enabled).
	bool start();
	void stop();
	uint16_t localPort() const;

	/// Sends a request for gameId. address = "255.255.255.255" broadcasts; a unicast address
	/// (e.g. "127.0.0.1") asks one host. False when the socket is closed or the send failed.
	bool request(const std::string &gameId, uint64_t nowMs, uint16_t port = kLanDiscoveryPort,
	             const std::string &address = "255.255.255.255");
	/// Collects answers. Servers not seen for expireMs (0 = never) are removed.
	void update(uint64_t nowMs, uint64_t expireMs = 0);

	/// Servers found, sorted by address and port.
	const std::vector<LanServerEntry> &servers() const;
	void clear();
	const LanDiscoveryStats &stats() const;

private:
	intptr_t m_socket;
	bool m_socketLib = false;
	std::string m_gameId;
	uint32_t m_nextNonce;
	/// Requests waiting for answers: nonce -> send time (the last 32).
	std::map<uint32_t, uint64_t> m_sent;
	std::vector<LanServerEntry> m_servers;
	LanDiscoveryStats m_stats;
};

/** \} */

}  // namespace net

#endif  // __NET_LAN_DISCOVERY_H__
