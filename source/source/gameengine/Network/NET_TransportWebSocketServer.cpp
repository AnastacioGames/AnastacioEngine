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

/** \file gameengine/Network/NET_TransportWebSocketServer.cpp
 *  \ingroup network
 *  \brief RFC 6455 WebSocket server over plain TCP sockets (winsock2 / POSIX).
 */

#include "NET_Socket.h"
#include "NET_TransportWeb.h"

#include <algorithm>
#include <cctype>
#include <cstring>
#include <map>

namespace net {

namespace {

const size_t kMaxHandshakeBytes = 8192;
const uint64_t kHandshakeTimeoutMs = uint64_t(kPendingTimeoutMs);
const uint64_t kCloseTimeoutMs = 2000;
const size_t kMaxOutBuffer = 4 * 1024 * 1024;
const size_t kRecvChunk = 16384;
const size_t kMaxRecvPerPoll = 256 * 1024;

enum : uint8_t {
	OP_CONTINUATION = 0x0,
	OP_TEXT = 0x1,
	OP_BINARY = 0x2,
	OP_CLOSE = 0x8,
	OP_PING = 0x9,
	OP_PONG = 0xA,
};

enum : uint16_t {
	CLOSE_NORMAL = 1000,
	CLOSE_GOING_AWAY = 1001,
	CLOSE_PROTOCOL_ERROR = 1002,
	CLOSE_UNSUPPORTED = 1003,
	CLOSE_TOO_BIG = 1009,
};

/* SHA-1 (FIPS 180-1), only used for the handshake. */
void sha1(const uint8_t *data, size_t size, uint8_t out[20])
{
	uint32_t h[5] = {0x67452301u, 0xEFCDAB89u, 0x98BADCFEu, 0x10325476u, 0xC3D2E1F0u};
	std::vector<uint8_t> msg(data, data + size);
	const uint64_t bitLen = uint64_t(size) * 8;
	msg.push_back(0x80);
	while (msg.size() % 64 != 56) {
		msg.push_back(0);
	}
	for (int i = 7; i >= 0; --i) {
		msg.push_back(uint8_t(bitLen >> (i * 8)));
	}
	auto rol = [](uint32_t v, int n) { return (v << n) | (v >> (32 - n)); };
	for (size_t block = 0; block < msg.size(); block += 64) {
		uint32_t w[80];
		for (int i = 0; i < 16; ++i) {
			const uint8_t *p = &msg[block + size_t(i) * 4];
			w[i] = (uint32_t(p[0]) << 24) | (uint32_t(p[1]) << 16) | (uint32_t(p[2]) << 8) | uint32_t(p[3]);
		}
		for (int i = 16; i < 80; ++i) {
			w[i] = rol(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
		}
		uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
		for (int i = 0; i < 80; ++i) {
			uint32_t f, k;
			if (i < 20) {
				f = (b & c) | (~b & d);
				k = 0x5A827999u;
			}
			else if (i < 40) {
				f = b ^ c ^ d;
				k = 0x6ED9EBA1u;
			}
			else if (i < 60) {
				f = (b & c) | (b & d) | (c & d);
				k = 0x8F1BBCDCu;
			}
			else {
				f = b ^ c ^ d;
				k = 0xCA62C1D6u;
			}
			const uint32_t t = rol(a, 5) + f + e + k + w[i];
			e = d;
			d = c;
			c = rol(b, 30);
			b = a;
			a = t;
		}
		h[0] += a;
		h[1] += b;
		h[2] += c;
		h[3] += d;
		h[4] += e;
	}
	for (int i = 0; i < 5; ++i) {
		out[i * 4 + 0] = uint8_t(h[i] >> 24);
		out[i * 4 + 1] = uint8_t(h[i] >> 16);
		out[i * 4 + 2] = uint8_t(h[i] >> 8);
		out[i * 4 + 3] = uint8_t(h[i]);
	}
}

std::string base64(const uint8_t *data, size_t size)
{
	static const char *kTable = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
	std::string out;
	for (size_t i = 0; i < size; i += 3) {
		const uint32_t n = (uint32_t(data[i]) << 16) | (i + 1 < size ? uint32_t(data[i + 1]) << 8 : 0) |
		                   (i + 2 < size ? uint32_t(data[i + 2]) : 0);
		out += kTable[(n >> 18) & 63];
		out += kTable[(n >> 12) & 63];
		out += i + 1 < size ? kTable[(n >> 6) & 63] : '=';
		out += i + 2 < size ? kTable[n & 63] : '=';
	}
	return out;
}

std::string lower(std::string s)
{
	for (char &c : s) {
		c = char(std::tolower(static_cast<unsigned char>(c)));
	}
	return s;
}

std::string trim(const std::string &s)
{
	size_t b = 0, e = s.size();
	while (b < e && (s[b] == ' ' || s[b] == '\t')) {
		++b;
	}
	while (e > b && (s[e - 1] == ' ' || s[e - 1] == '\t')) {
		--e;
	}
	return s.substr(b, e - b);
}

/// True if the comma separated header value contains token (case-insensitive).
bool hasToken(const std::string &value, const char *token)
{
	size_t start = 0;
	const std::string v = lower(value);
	while (start <= v.size()) {
		size_t end = v.find(',', start);
		if (end == std::string::npos) {
			end = v.size();
		}
		if (trim(v.substr(start, end - start)) == token) {
			return true;
		}
		start = end + 1;
	}
	return false;
}

class WebSocketServerTransport : public ITransport {
public:
	~WebSocketServerTransport() override
	{
		shutdown();
	}

	bool listen(uint16_t port, int maxPeers) override
	{
		shutdown();
		if (maxPeers <= 0) {
			return false;
		}
		if (!sock::acquire()) {
			return false;
		}
		m_acquired = true;
		m_listener = sock::listenTcp(port, 64);
		if (m_listener == sock::kInvalid) {
			shutdown();
			return false;
		}
		m_maxPeers = maxPeers;
		return true;
	}

	bool connect(const std::string &, uint16_t) override
	{
		return false;  // server only
	}

	void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) override
	{
		auto it = m_conns.find(peer);
		if (it == m_conns.end() || it->second.state != State::Open || size + 1 > kMaxWebSocketMessage) {
			return;
		}
		Conn &conn = it->second;
		const uint8_t channelByte = uint8_t(channel);
		writeFrame(conn, OP_BINARY, &channelByte, 1, data, size);
		flush(conn);
	}

	void disconnect(PeerId peer) override
	{
		auto it = m_conns.find(peer);
		if (it == m_conns.end()) {
			return;
		}
		Conn &conn = it->second;
		if (conn.state == State::Open) {
			pushDisconnected(conn);  // reported now, like the ENet transport
			startClose(conn, CLOSE_NORMAL);
			flush(conn);
		}
		else if (conn.state == State::Handshake) {
			conn.state = State::Dead;
		}
	}

	void poll(std::vector<TransportEvent> &events) override
	{
		for (TransportEvent &ev : m_pending) {
			events.push_back(std::move(ev));
		}
		m_pending.clear();
		if (m_listener == sock::kInvalid) {
			return;
		}
		const uint64_t now = steadyClockMs();
		acceptAll(now);
		for (auto &item : m_conns) {
			Conn &conn = item.second;
			receive(conn);
			if (conn.state == State::Handshake) {
				handshake(conn);
			}
			if (conn.state == State::Open || conn.state == State::Closing) {
				processFrames(conn);
			}
			if (conn.eof) {
				drop(conn);
			}
			flush(conn);
			if (conn.state == State::Closing && (conn.outBuf.size() == conn.outPos || now >= conn.deadline) &&
			    (conn.peerClosed || now >= conn.deadline))
			{
				conn.state = State::Dead;
			}
			if (conn.state == State::Handshake && now >= conn.deadline) {
				conn.state = State::Dead;
			}
		}
		for (auto it = m_conns.begin(); it != m_conns.end();) {
			if (it->second.state == State::Dead) {
				sock::close(it->second.socket);
				it = m_conns.erase(it);
			}
			else {
				++it;
			}
		}
		for (TransportEvent &ev : m_pending) {
			events.push_back(std::move(ev));
		}
		m_pending.clear();
	}

	void shutdown() override
	{
		for (auto &item : m_conns) {
			Conn &conn = item.second;
			if (conn.state == State::Open) {
				sendClose(conn, CLOSE_GOING_AWAY);
				flush(conn);
			}
			sock::close(conn.socket);
		}
		m_conns.clear();
		m_pending.clear();
		sock::close(m_listener);
		m_listener = sock::kInvalid;
		if (m_acquired) {
			sock::release();
			m_acquired = false;
		}
	}

	bool reliableAll() const override
	{
		return true;
	}

	uint16_t localPort() const override
	{
		return m_listener == sock::kInvalid ? 0 : sock::localPort(m_listener);
	}

private:
	enum class State { Handshake, Open, Closing, Dead };

	struct Conn {
		sock::Handle socket = sock::kInvalid;
		PeerId id = 0;
		State state = State::Handshake;
		uint64_t deadline = 0;  // handshake or close timeout
		bool peerClosed = false;  // close frame or EOF received
		std::vector<uint8_t> inBuf;
		std::vector<uint8_t> outBuf;
		size_t outPos = 0;
		std::vector<uint8_t> message;  // fragments being assembled
		bool assembling = false;
		bool discardInput = false;
		bool eof = false;  // TCP stream closed or failed  // stream unusable after a protocol error
	};

	void acceptAll(uint64_t now)
	{
		for (;;) {
			sock::Handle s = sock::accept(m_listener);
			if (s == sock::kInvalid) {
				return;
			}
			if (int(m_conns.size()) >= m_maxPeers) {
				sock::close(s);
				continue;
			}
			Conn conn;
			conn.socket = s;
			conn.id = m_nextId++;
			if (m_nextId == 0) {
				m_nextId = 1;
			}
			conn.deadline = now + kHandshakeTimeoutMs;
			m_conns.emplace(conn.id, std::move(conn));
		}
	}

	void receive(Conn &conn)
	{
		if (conn.state == State::Dead || conn.peerClosed || conn.eof) {
			return;
		}
		size_t total = 0;
		uint8_t chunk[kRecvChunk];
		while (total < kMaxRecvPerPoll) {
			const sock::IoResult n = sock::recv(conn.socket, chunk, sizeof(chunk));
			if (n == 0) {
				return;
			}
			if (n < 0) {
				conn.eof = true;  // frames already buffered are still processed
				return;
			}
			conn.inBuf.insert(conn.inBuf.end(), chunk, chunk + n);
			total += size_t(n);
			if (conn.state == State::Handshake && conn.inBuf.size() > kMaxHandshakeBytes) {
				return;  // handshake() rejects it
			}
		}
	}

	/// Connection lost without a closing handshake.
	void drop(Conn &conn)
	{
		if (conn.state == State::Open) {
			pushDisconnected(conn);
		}
		conn.state = State::Dead;
	}

	void pushDisconnected(Conn &conn)
	{
		TransportEvent ev;
		ev.type = TransportEvent::Type::Disconnected;
		ev.peer = conn.id;
		m_pending.push_back(std::move(ev));
	}

	void httpError(Conn &conn, const char *status, const char *extraHeaders = "")
	{
		const std::string resp = std::string("HTTP/1.1 ") + status + "\r\n" + extraHeaders +
		                         "Content-Length: 0\r\nConnection: close\r\n\r\n";
		conn.outBuf.assign(resp.begin(), resp.end());
		conn.outPos = 0;
		flush(conn);
		conn.state = State::Dead;
	}

	void handshake(Conn &conn)
	{
		static const char kEnd[] = "\r\n\r\n";
		auto end = std::search(conn.inBuf.begin(), conn.inBuf.end(), kEnd, kEnd + 4);
		if (end == conn.inBuf.end()) {
			if (conn.inBuf.size() > kMaxHandshakeBytes) {
				httpError(conn, "431 Request Header Fields Too Large");
			}
			return;
		}
		const size_t headerSize = size_t(end - conn.inBuf.begin()) + 4;
		if (headerSize > kMaxHandshakeBytes) {
			httpError(conn, "431 Request Header Fields Too Large");
			return;
		}
		const std::string request(conn.inBuf.begin(), conn.inBuf.begin() + std::ptrdiff_t(headerSize));
		conn.inBuf.erase(conn.inBuf.begin(), conn.inBuf.begin() + std::ptrdiff_t(headerSize));

		std::map<std::string, std::string> headers;
		size_t pos = request.find("\r\n");
		const std::string requestLine = request.substr(0, pos);
		while (pos != std::string::npos && pos + 2 < request.size()) {
			const size_t next = request.find("\r\n", pos + 2);
			const std::string line = request.substr(pos + 2, next - pos - 2);
			pos = next;
			const size_t colon = line.find(':');
			if (line.empty() || colon == std::string::npos) {
				continue;
			}
			std::string &value = headers[lower(trim(line.substr(0, colon)))];
			value += (value.empty() ? "" : ",") + trim(line.substr(colon + 1));
		}

		if (requestLine.compare(0, 4, "GET ") != 0 ||
		    requestLine.size() < 9 || requestLine.compare(requestLine.size() - 9, 9, " HTTP/1.1") != 0)
		{
			httpError(conn, "400 Bad Request");
			return;
		}
		if (!hasToken(headers["upgrade"], "websocket") || !hasToken(headers["connection"], "upgrade")) {
			httpError(conn, "400 Bad Request");
			return;
		}
		if (headers["sec-websocket-version"] != "13") {
			httpError(conn, "426 Upgrade Required", "Sec-WebSocket-Version: 13\r\n");
			return;
		}
		const std::string key = headers["sec-websocket-key"];
		if (key.size() != 24) {  // base64 of 16 bytes
			httpError(conn, "400 Bad Request");
			return;
		}
		const std::string resp = "HTTP/1.1 101 Switching Protocols\r\n"
		                         "Upgrade: websocket\r\n"
		                         "Connection: Upgrade\r\n"
		                         "Sec-WebSocket-Accept: " +
		                         webSocketAcceptKey(key) + "\r\n\r\n";
		conn.outBuf.insert(conn.outBuf.end(), resp.begin(), resp.end());
		conn.state = State::Open;

		TransportEvent ev;
		ev.type = TransportEvent::Type::Connected;
		ev.peer = conn.id;
		m_pending.push_back(std::move(ev));
	}

	void processFrames(Conn &conn)
	{
		size_t pos = 0;
		while (!conn.discardInput &&
		       (conn.state == State::Open || (conn.state == State::Closing && !conn.peerClosed)))
		{
			const uint8_t *p = conn.inBuf.data() + pos;
			const size_t avail = conn.inBuf.size() - pos;
			if (avail < 2) {
				break;
			}
			const bool fin = (p[0] & 0x80) != 0;
			const uint8_t rsv = p[0] & 0x70;
			const uint8_t op = p[0] & 0x0F;
			const bool masked = (p[1] & 0x80) != 0;
			uint64_t len = p[1] & 0x7F;
			size_t header = 2;
			if (len == 126) {
				if (avail < 4) {
					break;
				}
				len = (uint64_t(p[2]) << 8) | p[3];
				header = 4;
			}
			else if (len == 127) {
				if (avail < 10) {
					break;
				}
				len = 0;
				for (int i = 0; i < 8; ++i) {
					len = (len << 8) | p[2 + i];
				}
				header = 10;
				if (len >> 63) {
					fail(conn, CLOSE_PROTOCOL_ERROR);
					break;
				}
			}
			if (rsv != 0 || !masked) {
				fail(conn, CLOSE_PROTOCOL_ERROR);
				break;
			}
			const bool control = (op & 0x8) != 0;
			if (control && (!fin || len > 125)) {
				fail(conn, CLOSE_PROTOCOL_ERROR);
				break;
			}
			if (!control && (len > kMaxWebSocketMessage || conn.message.size() + len > kMaxWebSocketMessage)) {
				fail(conn, CLOSE_TOO_BIG);  // checked before the payload arrives
				break;
			}
			header += 4;
			if (avail < header + len) {
				break;
			}
			const uint8_t *maskKey = p + header - 4;
			std::vector<uint8_t> payload(p + header, p + header + len);
			for (size_t i = 0; i < payload.size(); ++i) {
				payload[i] ^= maskKey[i & 3];
			}
			pos += header + size_t(len);

			if (conn.state == State::Closing) {
				if (op == OP_CLOSE) {
					conn.peerClosed = true;
				}
				continue;  // ignore data after our close
			}
			switch (op) {
				case OP_CONTINUATION:
					if (!conn.assembling) {
						fail(conn, CLOSE_PROTOCOL_ERROR);
						break;
					}
					conn.message.insert(conn.message.end(), payload.begin(), payload.end());
					if (fin) {
						deliver(conn);
					}
					break;
				case OP_BINARY:
					if (conn.assembling) {
						fail(conn, CLOSE_PROTOCOL_ERROR);
						break;
					}
					conn.message = std::move(payload);
					conn.assembling = true;
					if (fin) {
						deliver(conn);
					}
					break;
				case OP_TEXT:
					fail(conn, CLOSE_UNSUPPORTED);
					break;
				case OP_CLOSE:
					if (payload.size() == 1) {
						fail(conn, CLOSE_PROTOCOL_ERROR);
						break;
					}
					conn.peerClosed = true;
					pushDisconnected(conn);
					// Echo the status code (RFC 6455 5.5.1).
					writeFrame(conn, OP_CLOSE, payload.data(), std::min<size_t>(payload.size(), 2), nullptr, 0);
					conn.state = State::Closing;
					conn.deadline = steadyClockMs() + kCloseTimeoutMs;
					break;
				case OP_PING:
					writeFrame(conn, OP_PONG, payload.data(), payload.size(), nullptr, 0);
					break;
				case OP_PONG:
					break;
				default:
					fail(conn, CLOSE_PROTOCOL_ERROR);
					break;
			}
		}
		if (conn.discardInput || conn.peerClosed) {
			conn.inBuf.clear();
		}
		else {
			conn.inBuf.erase(conn.inBuf.begin(), conn.inBuf.begin() + std::ptrdiff_t(pos));
		}
	}

	void deliver(Conn &conn)
	{
		std::vector<uint8_t> message = std::move(conn.message);
		conn.message.clear();
		conn.assembling = false;
		if (message.empty() || message[0] >= kChannelCount) {
			fail(conn, CLOSE_PROTOCOL_ERROR);
			return;
		}
		TransportEvent ev;
		ev.type = TransportEvent::Type::Received;
		ev.peer = conn.id;
		ev.channel = Channel(message[0]);
		ev.data.assign(message.begin() + 1, message.end());
		m_pending.push_back(std::move(ev));
	}

	/// Protocol error from the client: close with code, report the disconnect and drop the TCP
	/// connection once the close frame is sent (RFC 6455 7.1.7).
	void fail(Conn &conn, uint16_t code)
	{
		if (conn.state == State::Open) {
			pushDisconnected(conn);
			startClose(conn, code);
		}
		conn.discardInput = true;
		conn.peerClosed = true;  // do not wait for the client's close
	}

	void startClose(Conn &conn, uint16_t code)
	{
		sendClose(conn, code);
		conn.state = State::Closing;
		conn.deadline = steadyClockMs() + kCloseTimeoutMs;
		conn.message.clear();
		conn.assembling = false;
	}

	void sendClose(Conn &conn, uint16_t code)
	{
		const uint8_t status[2] = {uint8_t(code >> 8), uint8_t(code)};
		writeFrame(conn, OP_CLOSE, status, 2, nullptr, 0);
	}

	/// Server frames are never masked and never fragmented.
	void writeFrame(Conn &conn, uint8_t op, const uint8_t *a, size_t aSize, const uint8_t *b, size_t bSize)
	{
		const size_t len = aSize + bSize;
		std::vector<uint8_t> &out = conn.outBuf;
		if (out.size() - conn.outPos + len + 10 > kMaxOutBuffer) {
			// Peer not reading: give up on it.
			if (conn.state == State::Open) {
				pushDisconnected(conn);
			}
			conn.state = State::Dead;
			return;
		}
		out.push_back(uint8_t(0x80 | op));
		if (len < 126) {
			out.push_back(uint8_t(len));
		}
		else if (len <= 0xFFFF) {
			out.push_back(126);
			out.push_back(uint8_t(len >> 8));
			out.push_back(uint8_t(len));
		}
		else {
			out.push_back(127);
			for (int i = 7; i >= 0; --i) {
				out.push_back(uint8_t(uint64_t(len) >> (i * 8)));
			}
		}
		out.insert(out.end(), a, a + aSize);
		if (bSize) {
			out.insert(out.end(), b, b + bSize);
		}
	}

	void flush(Conn &conn)
	{
		while (conn.state != State::Dead && conn.outPos < conn.outBuf.size()) {
			const sock::IoResult n =
			    sock::send(conn.socket, conn.outBuf.data() + conn.outPos, conn.outBuf.size() - conn.outPos);
			if (n == 0) {
				break;
			}
			if (n < 0) {
				drop(conn);
				break;
			}
			conn.outPos += size_t(n);
		}
		if (conn.outPos == conn.outBuf.size()) {
			conn.outBuf.clear();
			conn.outPos = 0;
		}
		else if (conn.outPos > 65536) {
			conn.outBuf.erase(conn.outBuf.begin(), conn.outBuf.begin() + std::ptrdiff_t(conn.outPos));
			conn.outPos = 0;
		}
	}

	sock::Handle m_listener = sock::kInvalid;
	bool m_acquired = false;
	int m_maxPeers = 0;
	PeerId m_nextId = 1;
	std::map<PeerId, Conn> m_conns;
	std::vector<TransportEvent> m_pending;
};

}  // namespace

std::string webSocketAcceptKey(std::string_view clientKey)
{
	const std::string input = std::string(clientKey) + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
	uint8_t digest[20];
	sha1(reinterpret_cast<const uint8_t *>(input.data()), input.size(), digest);
	return base64(digest, sizeof(digest));
}

std::unique_ptr<ITransport> createWebSocketServerTransport()
{
	return std::unique_ptr<ITransport>(new WebSocketServerTransport());
}

}  // namespace net
