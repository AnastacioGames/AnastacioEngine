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

/** \file gameengine/Network/NET_LanDiscovery.cpp
 *  \ingroup network
 */

#include "NET_LanDiscovery.h"

#include "NET_BitStream.h"
#include "NET_ITransport.h"  // steadyClockMs
#include "NET_Socket.h"

#include <algorithm>
#include <tuple>

namespace net {

namespace {

enum : uint8_t { LAN_REQUEST = 1, LAN_RESPONSE = 2 };

enum : uint8_t { LAN_FLAG_PASSWORD = 1 << 0 };

sock::Handle handleOf(intptr_t s)
{
	return sock::Handle(s);
}

intptr_t storeHandle(sock::Handle s)
{
	return intptr_t(s);
}

const intptr_t kNoSocket = intptr_t(sock::kInvalid);

void writeHeader(BitWriter &w, uint8_t kind, uint32_t nonce)
{
	w.writeU32(kLanMagic);
	w.writeU8(kLanVersion);
	w.writeU8(kind);
	w.writeU32(nonce);
}

bool readHeader(BitReader &r, uint8_t kind, uint32_t &nonce)
{
	if (r.readU32() != kLanMagic || r.readU8() != kLanVersion || r.readU8() != kind) {
		return false;
	}
	nonce = r.readU32();
	return r.ok();
}

bool readLimited(BitReader &r, std::string &s)
{
	if (!r.readString(s)) {
		return false;
	}
	if (s.size() > kMaxLanString) {
		r.fail();
		return false;
	}
	return true;
}

bool finishRead(BitReader &r)
{
	return r.ok() && r.bitsRemaining() == 0;
}

bool finishWrite(BitWriter &w, std::vector<uint8_t> &out)
{
	w.alignToByte();
	return w.ok() && out.size() <= kMaxLanPacket;
}

/// Cuts a string to kMaxLanString bytes without splitting a UTF-8 sequence.
std::string cut(const std::string &s)
{
	if (s.size() <= kMaxLanString) {
		return s;
	}
	size_t n = kMaxLanString;
	while (n > 0 && (uint8_t(s[n]) & 0xC0) == 0x80) {
		--n;
	}
	return s.substr(0, n);
}

}  // namespace

/* -------------------------------------------------------------------- */
/** \name Format
 * \{ */

bool encodeLanRequest(const LanRequest &request, std::vector<uint8_t> &out)
{
	out.clear();
	if (request.gameId.size() > kMaxLanString) {
		return false;
	}
	BitWriter w(out);
	writeHeader(w, LAN_REQUEST, request.nonce);
	w.writeString(request.gameId);
	return finishWrite(w, out);
}

bool decodeLanRequest(const uint8_t *data, size_t size, LanRequest &request)
{
	if (!data || size > kMaxLanPacket) {
		return false;
	}
	BitReader r(data, size);
	return readHeader(r, LAN_REQUEST, request.nonce) && readLimited(r, request.gameId) && finishRead(r);
}

bool encodeLanResponse(uint32_t nonce, const LanServerInfo &info, std::vector<uint8_t> &out)
{
	out.clear();
	if (info.gameId.size() > kMaxLanString || info.name.size() > kMaxLanString ||
	    info.sceneName.size() > kMaxLanString)
	{
		return false;
	}
	BitWriter w(out);
	writeHeader(w, LAN_RESPONSE, nonce);
	w.writeString(info.gameId);
	w.writeU32(info.gameVersion);
	w.writeString(info.name);
	w.writeString(info.sceneName);
	w.writeU16(info.players);
	w.writeU16(info.maxPlayers);
	w.writeU16(info.enetPort);
	w.writeU16(info.webSocketPort);
	w.writeU8(info.password ? LAN_FLAG_PASSWORD : 0);
	return finishWrite(w, out);
}

bool decodeLanResponse(const uint8_t *data, size_t size, uint32_t &nonce, LanServerInfo &info)
{
	if (!data || size > kMaxLanPacket) {
		return false;
	}
	BitReader r(data, size);
	if (!readHeader(r, LAN_RESPONSE, nonce) || !readLimited(r, info.gameId)) {
		return false;
	}
	info.gameVersion = r.readU32();
	if (!readLimited(r, info.name) || !readLimited(r, info.sceneName)) {
		return false;
	}
	info.players = r.readU16();
	info.maxPlayers = r.readU16();
	info.enetPort = r.readU16();
	info.webSocketPort = r.readU16();
	const uint8_t flags = r.readU8();
	if (flags & ~LAN_FLAG_PASSWORD) {
		return false;  // unknown flags: a newer format
	}
	info.password = (flags & LAN_FLAG_PASSWORD) != 0;
	return finishRead(r);
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name LanResponder
 * \{ */

LanResponder::LanResponder(const LanResponderConfig &config) : m_config(config), m_socket(kNoSocket)
{
	m_config.requestsPerSecond = std::max<uint32_t>(m_config.requestsPerSecond, 1);
	m_config.maxTrackedAddresses = std::max<size_t>(m_config.maxTrackedAddresses, 1);
}

LanResponder::~LanResponder()
{
	stop();
}

bool LanResponder::start(uint16_t port)
{
	stop();
	if (!sock::acquire()) {
		return false;
	}
	m_socketLib = true;
	// Reuse lets several servers on one host hear the broadcast (only one gets unicasts).
	const sock::Handle s = sock::openUdp(port, false, true);
	if (s == sock::kInvalid) {
		stop();
		return false;
	}
	m_socket = storeHandle(s);
	m_port = sock::localPort(s);
	return true;
}

void LanResponder::stop()
{
	if (m_socket != kNoSocket) {
		sock::close(handleOf(m_socket));
		m_socket = kNoSocket;
	}
	if (m_socketLib) {
		sock::release();
		m_socketLib = false;
	}
	m_port = 0;
	m_buckets.clear();
}

bool LanResponder::running() const
{
	return m_socket != kNoSocket;
}

uint16_t LanResponder::localPort() const
{
	return m_port;
}

void LanResponder::setInfo(const LanServerInfo &info)
{
	m_info = info;
	m_info.gameId = cut(info.gameId);
	m_info.name = cut(info.name);
	m_info.sceneName = cut(info.sceneName);
}

const LanServerInfo &LanResponder::info() const
{
	return m_info;
}

bool LanResponder::allow(uint32_t address, uint64_t nowMs)
{
	auto it = m_buckets.find(address);
	if (it == m_buckets.end()) {
		if (m_buckets.size() >= m_config.maxTrackedAddresses) {
			// Drops the address heard from least recently.
			auto oldest = m_buckets.begin();
			for (auto b = m_buckets.begin(); b != m_buckets.end(); ++b) {
				if (b->second.lastMs < oldest->second.lastMs) {
					oldest = b;
				}
			}
			m_buckets.erase(oldest);
		}
		Bucket bucket;
		bucket.tokens = float(m_config.requestsPerSecond);
		bucket.lastMs = nowMs;
		it = m_buckets.emplace(address, bucket).first;
	}
	Bucket &b = it->second;
	if (nowMs > b.lastMs) {
		b.tokens = std::min(float(m_config.requestsPerSecond),
		                    b.tokens + float(nowMs - b.lastMs) * float(m_config.requestsPerSecond) / 1000.0f);
	}
	b.lastMs = std::max(b.lastMs, nowMs);
	if (b.tokens < 1.0f) {
		return false;
	}
	b.tokens -= 1.0f;
	return true;
}

void LanResponder::update(uint64_t nowMs)
{
	if (m_socket == kNoSocket) {
		return;
	}
	const sock::Handle s = handleOf(m_socket);
	// One byte more than the limit, to tell a long datagram from one at the limit.
	uint8_t buffer[kMaxLanPacket + 1];
	std::vector<uint8_t> reply;
	// Bounded so a flood cannot hold the caller's frame.
	for (int i = 0; i < 256; ++i) {
		uint32_t address = 0;
		uint16_t port = 0;
		const sock::IoResult n = sock::recvFrom(s, buffer, sizeof(buffer), address, port);
		if (n <= 0) {
			break;
		}
		++m_stats.requests;
		LanRequest request;
		if (!decodeLanRequest(buffer, size_t(n), request)) {
			++m_stats.invalid;
			continue;
		}
		if (request.gameId != m_info.gameId) {
			++m_stats.otherGame;
			continue;
		}
		if (!allow(address, nowMs)) {
			++m_stats.rateLimited;
			continue;
		}
		if (encodeLanResponse(request.nonce, m_info, reply) && sock::sendTo(s, address, port, reply.data(), reply.size())) {
			++m_stats.answered;
		}
	}
}

const LanResponderStats &LanResponder::stats() const
{
	return m_stats;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name LanDiscovery
 * \{ */

LanDiscovery::LanDiscovery() : m_socket(kNoSocket)
{
	// Nonces start at a varying value so answers to an earlier run are not taken as current.
	m_nextNonce = uint32_t(steadyClockMs() * 2654435761u) | 1u;
}

LanDiscovery::~LanDiscovery()
{
	stop();
}

bool LanDiscovery::start()
{
	stop();
	if (!sock::acquire()) {
		return false;
	}
	m_socketLib = true;
	const sock::Handle s = sock::openUdp(0, true, false);
	if (s == sock::kInvalid) {
		stop();
		return false;
	}
	m_socket = storeHandle(s);
	return true;
}

void LanDiscovery::stop()
{
	if (m_socket != kNoSocket) {
		sock::close(handleOf(m_socket));
		m_socket = kNoSocket;
	}
	if (m_socketLib) {
		sock::release();
		m_socketLib = false;
	}
	m_sent.clear();
}

uint16_t LanDiscovery::localPort() const
{
	return m_socket == kNoSocket ? 0 : sock::localPort(handleOf(m_socket));
}

bool LanDiscovery::request(const std::string &gameId, uint64_t nowMs, uint16_t port, const std::string &address)
{
	uint32_t ip = 0;
	if (m_socket == kNoSocket || port == 0 || !sock::parseIpv4(address, ip)) {
		return false;
	}
	if (gameId != m_gameId) {
		m_servers.clear();
		m_gameId = gameId;
	}
	LanRequest req;
	req.nonce = m_nextNonce++;
	req.gameId = gameId;
	std::vector<uint8_t> packet;
	if (!encodeLanRequest(req, packet)) {
		return false;
	}
	m_sent[req.nonce] = nowMs;
	while (m_sent.size() > 32) {
		// Forgets the oldest request (smallest send time).
		auto oldest = m_sent.begin();
		for (auto it = m_sent.begin(); it != m_sent.end(); ++it) {
			if (it->second < oldest->second) {
				oldest = it;
			}
		}
		m_sent.erase(oldest);
	}
	if (!sock::sendTo(handleOf(m_socket), ip, port, packet.data(), packet.size())) {
		return false;
	}
	++m_stats.requestsSent;
	return true;
}

void LanDiscovery::update(uint64_t nowMs, uint64_t expireMs)
{
	if (m_socket != kNoSocket) {
		const sock::Handle s = handleOf(m_socket);
		uint8_t buffer[kMaxLanPacket + 1];
		for (int i = 0; i < 256; ++i) {
			uint32_t address = 0;
			uint16_t port = 0;
			const sock::IoResult n = sock::recvFrom(s, buffer, sizeof(buffer), address, port);
			if (n <= 0) {
				break;
			}
			uint32_t nonce = 0;
			LanServerInfo info;
			if (!decodeLanResponse(buffer, size_t(n), nonce, info)) {
				++m_stats.invalid;
				continue;
			}
			if (info.gameId != m_gameId) {
				++m_stats.otherGame;
				continue;
			}
			const auto sent = m_sent.find(nonce);
			if (sent == m_sent.end()) {
				++m_stats.unknownNonce;
				continue;
			}
			++m_stats.responses;
			LanServerEntry entry;
			entry.address = sock::formatIpv4(address);
			entry.info = info;
			entry.pingMs = uint32_t(std::min<uint64_t>(nowMs >= sent->second ? nowMs - sent->second : 0, 60000));
			entry.lastSeenMs = nowMs;
			const auto key = [](const LanServerEntry &e) {
				return std::make_tuple(std::cref(e.address), e.info.enetPort, e.info.webSocketPort);
			};
			auto it = std::lower_bound(m_servers.begin(), m_servers.end(), entry,
			                           [&key](const LanServerEntry &a, const LanServerEntry &b) { return key(a) < key(b); });
			if (it != m_servers.end() && key(*it) == key(entry)) {
				*it = std::move(entry);
			}
			else if (m_servers.size() < 256) {
				m_servers.insert(it, std::move(entry));
			}
		}
	}
	if (expireMs > 0) {
		m_servers.erase(std::remove_if(m_servers.begin(), m_servers.end(),
		                               [&](const LanServerEntry &e) { return nowMs - e.lastSeenMs > expireMs; }),
		                m_servers.end());
	}
}

const std::vector<LanServerEntry> &LanDiscovery::servers() const
{
	return m_servers;
}

void LanDiscovery::clear()
{
	m_servers.clear();
}

const LanDiscoveryStats &LanDiscovery::stats() const
{
	return m_stats;
}

/** \} */

}  // namespace net
