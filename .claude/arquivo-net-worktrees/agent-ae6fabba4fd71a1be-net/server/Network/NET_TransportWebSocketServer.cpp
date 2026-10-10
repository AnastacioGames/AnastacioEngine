/* WebSocket server transport (RFC 6455), plain OS sockets, no external dependencies.
 * TLS is out of scope: put a reverse proxy in front (see NOTES-C.md). */

#include "NET_TransportWebSocket.h"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstring>

#ifdef _WIN32
#  ifndef WIN32_LEAN_AND_MEAN
#    define WIN32_LEAN_AND_MEAN
#  endif
#  ifndef NOMINMAX
#    define NOMINMAX
#  endif
#  include <winsock2.h>
#  include <ws2tcpip.h>
#else
#  include <arpa/inet.h>
#  include <cerrno>
#  include <fcntl.h>
#  include <netinet/in.h>
#  include <netinet/tcp.h>
#  include <sys/socket.h>
#  include <unistd.h>
#endif

namespace net {

/* -------------------------------------------------------------------- */
/* Handshake helpers */

namespace ws {

static inline uint32_t rol32(uint32_t v, int n)
{
	return (v << n) | (v >> (32 - n));
}

void sha1(const uint8_t *data, size_t size, uint8_t out[20])
{
	uint32_t h[5] = {0x67452301u, 0xEFCDAB89u, 0x98BADCFEu, 0x10325476u, 0xC3D2E1F0u};

	std::vector<uint8_t> msg(data, data + size);
	const uint64_t bitLen = uint64_t(size) * 8u;
	msg.push_back(0x80);
	while (msg.size() % 64 != 56) {
		msg.push_back(0);
	}
	for (int i = 7; i >= 0; i--) {
		msg.push_back(uint8_t(bitLen >> (i * 8)));
	}

	for (size_t chunk = 0; chunk < msg.size(); chunk += 64) {
		uint32_t w[80];
		for (int i = 0; i < 16; i++) {
			const uint8_t *p = &msg[chunk + size_t(i) * 4];
			w[i] = (uint32_t(p[0]) << 24) | (uint32_t(p[1]) << 16) | (uint32_t(p[2]) << 8) |
			       uint32_t(p[3]);
		}
		for (int i = 16; i < 80; i++) {
			w[i] = rol32(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
		}
		uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
		for (int i = 0; i < 80; i++) {
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
			const uint32_t t = rol32(a, 5) + f + e + k + w[i];
			e = d;
			d = c;
			c = rol32(b, 30);
			b = a;
			a = t;
		}
		h[0] += a;
		h[1] += b;
		h[2] += c;
		h[3] += d;
		h[4] += e;
	}

	for (int i = 0; i < 5; i++) {
		out[i * 4 + 0] = uint8_t(h[i] >> 24);
		out[i * 4 + 1] = uint8_t(h[i] >> 16);
		out[i * 4 + 2] = uint8_t(h[i] >> 8);
		out[i * 4 + 3] = uint8_t(h[i]);
	}
}

std::string base64Encode(const uint8_t *data, size_t size)
{
	static const char table[] =
	    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
	std::string out;
	out.reserve((size + 2) / 3 * 4);
	size_t i = 0;
	for (; i + 2 < size; i += 3) {
		const uint32_t v = (uint32_t(data[i]) << 16) | (uint32_t(data[i + 1]) << 8) | data[i + 2];
		out += table[(v >> 18) & 63];
		out += table[(v >> 12) & 63];
		out += table[(v >> 6) & 63];
		out += table[v & 63];
	}
	if (i < size) {
		uint32_t v = uint32_t(data[i]) << 16;
		if (i + 1 < size) {
			v |= uint32_t(data[i + 1]) << 8;
		}
		out += table[(v >> 18) & 63];
		out += table[(v >> 12) & 63];
		out += (i + 1 < size) ? table[(v >> 6) & 63] : '=';
		out += '=';
	}
	return out;
}

std::string computeAcceptKey(const std::string &clientKey)
{
	const std::string s = clientKey + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
	uint8_t digest[20];
	sha1(reinterpret_cast<const uint8_t *>(s.data()), s.size(), digest);
	return base64Encode(digest, sizeof(digest));
}

} // namespace ws

/* -------------------------------------------------------------------- */
/* Socket portability */

namespace {

#ifdef _WIN32
using SocketHandle = SOCKET;
const SocketHandle kInvalidSocket = INVALID_SOCKET;
#else
using SocketHandle = int;
const SocketHandle kInvalidSocket = -1;
#endif

using Clock = std::chrono::steady_clock;

bool netInit()
{
#ifdef _WIN32
	/* Never cleaned up: harmless at process exit and avoids refcount bugs. */
	static const bool ok = [] {
		WSADATA wsa;
		return WSAStartup(MAKEWORD(2, 2), &wsa) == 0;
	}();
	return ok;
#else
	return true;
#endif
}

void closeSocket(SocketHandle s)
{
#ifdef _WIN32
	closesocket(s);
#else
	close(s);
#endif
}

bool setNonBlocking(SocketHandle s)
{
#ifdef _WIN32
	u_long mode = 1;
	return ioctlsocket(s, FIONBIO, &mode) == 0;
#else
	const int flags = fcntl(s, F_GETFL, 0);
	return flags >= 0 && fcntl(s, F_SETFL, flags | O_NONBLOCK) == 0;
#endif
}

bool lastErrorWouldBlock()
{
#ifdef _WIN32
	const int err = WSAGetLastError();
	return err == WSAEWOULDBLOCK || err == WSAEINTR;
#else
	return errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR;
#endif
}

/* Returns bytes sent, 0 if it would block, -1 on error. */
long sendSome(SocketHandle s, const uint8_t *data, size_t size)
{
#ifdef _WIN32
	const int n = ::send(s, reinterpret_cast<const char *>(data), int(std::min<size_t>(size, 1 << 30)), 0);
#else
	const ssize_t n = ::send(s, data, size, MSG_NOSIGNAL);
#endif
	if (n < 0) {
		return lastErrorWouldBlock() ? 0 : -1;
	}
	return long(n);
}

/* Returns bytes read, 0 on orderly close, -1 if it would block, -2 on error. */
long recvSome(SocketHandle s, uint8_t *data, size_t size)
{
#ifdef _WIN32
	const int n = ::recv(s, reinterpret_cast<char *>(data), int(size), 0);
#else
	const ssize_t n = ::recv(s, data, size, 0);
#endif
	if (n < 0) {
		return lastErrorWouldBlock() ? -1 : -2;
	}
	return long(n);
}

bool iequalsPrefix(const std::string &s, size_t pos, const char *word)
{
	const size_t n = std::strlen(word);
	if (pos + n > s.size()) {
		return false;
	}
	for (size_t i = 0; i < n; i++) {
		if (std::tolower((unsigned char)s[pos + i]) != std::tolower((unsigned char)word[i])) {
			return false;
		}
	}
	return true;
}

bool icontains(const std::string &s, const char *word)
{
	for (size_t i = 0; i < s.size(); i++) {
		if (iequalsPrefix(s, i, word)) {
			return true;
		}
	}
	return false;
}

std::string trim(const std::string &s)
{
	size_t b = 0, e = s.size();
	while (b < e && (s[b] == ' ' || s[b] == '\t')) {
		b++;
	}
	while (e > b && (s[e - 1] == ' ' || s[e - 1] == '\t' || s[e - 1] == '\r')) {
		e--;
	}
	return s.substr(b, e - b);
}

enum : uint8_t {
	OpContinuation = 0x0,
	OpText = 0x1,
	OpBinary = 0x2,
	OpClose = 0x8,
	OpPing = 0x9,
	OpPong = 0xA,
};

enum : uint16_t {
	CloseNormal = 1000,
	CloseGoingAway = 1001,
	CloseProtocolError = 1002,
	CloseUnsupportedData = 1003,
	ClosePolicyViolation = 1008,
	CloseTooBig = 1009,
};

constexpr size_t kMaxHandshakeBytes = 8192;
constexpr size_t kMaxReadPerPoll = 256 * 1024;

struct Connection {
	enum class State { Handshake, Open, Closing };

	SocketHandle sock = kInvalidSocket;
	PeerId id = 0;
	State state = State::Handshake;
	std::vector<uint8_t> in;
	std::vector<uint8_t> out;
	size_t outOffset = 0;
	Clock::time_point created;
	Clock::time_point lastRecv;
	Clock::time_point lastPing;
	Clock::time_point closingSince;
	std::vector<uint8_t> fragment;
	bool fragmenting = false;
	bool announced = false; /* Connected event emitted. */
	bool dead = false;
};

class WebSocketServer final : public WebSocketServerTransport {
public:
	explicit WebSocketServer(const WebSocketServerSettings &settings) : m_settings(settings)
	{
	}

	~WebSocketServer() override
	{
		shutdown();
	}

	bool listen(uint16_t port, int maxPeers) override
	{
		if (m_listen != kInvalidSocket || !netInit() || maxPeers <= 0) {
			return false;
		}
		SocketHandle s = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
		if (s == kInvalidSocket) {
			return false;
		}
		int yes = 1;
		setsockopt(s, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char *>(&yes), sizeof(yes));

		sockaddr_in addr;
		std::memset(&addr, 0, sizeof(addr));
		addr.sin_family = AF_INET;
		addr.sin_addr.s_addr = htonl(INADDR_ANY);
		addr.sin_port = htons(port);
		if (::bind(s, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) != 0 ||
		    ::listen(s, 16) != 0 || !setNonBlocking(s))
		{
			closeSocket(s);
			return false;
		}
		socklen_t len = sizeof(addr);
		if (getsockname(s, reinterpret_cast<sockaddr *>(&addr), &len) == 0) {
			m_port = ntohs(addr.sin_port);
		}
		m_listen = s;
		m_maxPeers = maxPeers;
		return true;
	}

	bool connect(const std::string &, uint16_t) override
	{
		return false;
	}

	void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) override
	{
		Connection *c = find(peer);
		if (!c || c->state != Connection::State::Open || size > m_settings.maxMessageSize) {
			return;
		}
		const uint8_t ch = uint8_t(channel);
		queueFrame(*c, OpBinary, &ch, 1, data, size);
		if (c->out.size() - c->outOffset > m_settings.maxSendBuffer) {
			fail(*c, ClosePolicyViolation);
			return;
		}
		flush(*c);
	}

	void disconnect(PeerId peer) override
	{
		Connection *c = find(peer);
		if (c) {
			fail(*c, CloseNormal);
		}
	}

	void poll(std::vector<TransportEvent> &events) override
	{
		if (m_listen == kInvalidSocket) {
			return;
		}
		const Clock::time_point now = Clock::now();
		acceptNew(now);

		for (auto &cp : m_conns) {
			Connection &c = *cp;
			if (c.dead) {
				continue;
			}
			readAvailable(c, now);
			if (!c.dead && c.state == Connection::State::Handshake) {
				processHandshake(c);
			}
			if (!c.dead && c.state == Connection::State::Open) {
				processFrames(c);
			}
			if (!c.dead) {
				checkTimers(c, now);
			}
			if (!c.dead) {
				flush(c);
			}
			if (!c.dead && c.state == Connection::State::Closing &&
			    (c.outOffset >= c.out.size() || elapsedMs(c.closingSince, now) > m_settings.closeTimeoutMs))
			{
				c.dead = true;
			}
		}

		for (auto &cp : m_conns) {
			if (cp->dead) {
				announceDisconnect(*cp);
				closeSocket(cp->sock);
			}
		}
		m_conns.erase(std::remove_if(m_conns.begin(),
		                             m_conns.end(),
		                             [](const std::unique_ptr<Connection> &c) { return c->dead; }),
		              m_conns.end());

		for (TransportEvent &e : m_events) {
			events.push_back(std::move(e));
		}
		m_events.clear();
	}

	void shutdown() override
	{
		for (auto &cp : m_conns) {
			if (cp->state == Connection::State::Open) {
				queueClose(*cp, CloseGoingAway);
				flush(*cp);
			}
			closeSocket(cp->sock);
		}
		m_conns.clear();
		m_events.clear();
		if (m_listen != kInvalidSocket) {
			closeSocket(m_listen);
			m_listen = kInvalidSocket;
		}
		m_port = 0;
	}

	bool reliableAll() const override
	{
		return true;
	}

	uint16_t boundPort() const override
	{
		return m_port;
	}

private:
	static uint32_t elapsedMs(Clock::time_point from, Clock::time_point to)
	{
		const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(to - from).count();
		return ms < 0 ? 0u : uint32_t(std::min<long long>(ms, 0xFFFFFFFFll));
	}

	Connection *find(PeerId peer)
	{
		for (auto &c : m_conns) {
			if (c->id == peer && !c->dead) {
				return c.get();
			}
		}
		return nullptr;
	}

	int countState(Connection::State state) const
	{
		int n = 0;
		for (const auto &c : m_conns) {
			if (!c->dead && c->state == state) {
				n++;
			}
		}
		return n;
	}

	void acceptNew(Clock::time_point now)
	{
		for (;;) {
			SocketHandle s = ::accept(m_listen, nullptr, nullptr);
			if (s == kInvalidSocket) {
				return;
			}
			if (countState(Connection::State::Handshake) >= m_settings.maxPending || !setNonBlocking(s)) {
				closeSocket(s);
				continue;
			}
			int yes = 1;
			setsockopt(s, IPPROTO_TCP, TCP_NODELAY, reinterpret_cast<const char *>(&yes), sizeof(yes));
			auto c = std::make_unique<Connection>();
			c->sock = s;
			c->id = m_nextId++;
			if (m_nextId == 0) {
				m_nextId = 1;
			}
			c->created = c->lastRecv = c->lastPing = now;
			m_conns.push_back(std::move(c));
		}
	}

	void readAvailable(Connection &c, Clock::time_point now)
	{
		uint8_t buf[4096];
		size_t total = 0;
		while (total < kMaxReadPerPoll) {
			const long n = recvSome(c.sock, buf, sizeof(buf));
			if (n == -1) {
				break;
			}
			if (n <= 0) {
				/* Peer closed or socket error. */
				c.dead = true;
				return;
			}
			total += size_t(n);
			c.lastRecv = now;
			if (c.state != Connection::State::Closing) {
				c.in.insert(c.in.end(), buf, buf + n);
			}
			if (c.state == Connection::State::Handshake && c.in.size() > kMaxHandshakeBytes) {
				rejectHttp(c, "431 Request Header Fields Too Large");
				return;
			}
		}
	}

	void rejectHttp(Connection &c, const char *status)
	{
		const std::string resp = std::string("HTTP/1.1 ") + status +
		                         "\r\nSec-WebSocket-Version: 13\r\nContent-Length: 0\r\n"
		                         "Connection: close\r\n\r\n";
		c.out.insert(c.out.end(), resp.begin(), resp.end());
		c.in.clear();
		enterClosing(c);
	}

	void processHandshake(Connection &c)
	{
		static const char kEnd[] = "\r\n\r\n";
		auto it = std::search(c.in.begin(), c.in.end(), kEnd, kEnd + 4);
		if (it == c.in.end()) {
			return;
		}
		const size_t headerLen = size_t(it - c.in.begin()) + 4;
		const std::string req(c.in.begin(), c.in.begin() + std::ptrdiff_t(headerLen));
		c.in.erase(c.in.begin(), c.in.begin() + std::ptrdiff_t(headerLen));

		if (req.compare(0, 4, "GET ") != 0) {
			rejectHttp(c, "405 Method Not Allowed");
			return;
		}
		std::string upgrade, connection, version, key;
		size_t pos = req.find("\r\n");
		while (pos != std::string::npos && pos + 2 < req.size()) {
			const size_t start = pos + 2;
			const size_t end = req.find("\r\n", start);
			if (end == std::string::npos || end == start) {
				break;
			}
			const std::string line = req.substr(start, end - start);
			const size_t colon = line.find(':');
			if (colon != std::string::npos) {
				const std::string value = trim(line.substr(colon + 1));
				if (iequalsPrefix(line, 0, "upgrade:")) {
					upgrade = value;
				}
				else if (iequalsPrefix(line, 0, "connection:")) {
					connection = value;
				}
				else if (iequalsPrefix(line, 0, "sec-websocket-version:")) {
					version = value;
				}
				else if (iequalsPrefix(line, 0, "sec-websocket-key:")) {
					key = value;
				}
			}
			pos = end;
		}

		if (!icontains(upgrade, "websocket") || !icontains(connection, "upgrade") || version != "13" ||
		    key.size() != 24)
		{
			rejectHttp(c, "400 Bad Request");
			return;
		}
		if (countState(Connection::State::Open) >= m_maxPeers) {
			rejectHttp(c, "503 Service Unavailable");
			return;
		}

		const std::string resp =
		    "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
		    "Sec-WebSocket-Accept: " +
		    ws::computeAcceptKey(key) + "\r\n\r\n";
		c.out.insert(c.out.end(), resp.begin(), resp.end());
		c.state = Connection::State::Open;
		c.announced = true;
		m_events.push_back({TransportEvent::Type::Connected, c.id, Channel::Control, {}});
	}

	void processFrames(Connection &c)
	{
		size_t pos = 0;
		while (c.state == Connection::State::Open && c.in.size() - pos >= 2) {
			const uint8_t *p = c.in.data() + pos;
			const size_t avail = c.in.size() - pos;
			const bool fin = (p[0] & 0x80) != 0;
			const uint8_t opcode = p[0] & 0x0F;
			const bool masked = (p[1] & 0x80) != 0;
			uint64_t len = p[1] & 0x7F;
			size_t header = 2;

			if ((p[0] & 0x70) != 0 || !masked) {
				/* No extensions negotiated; client frames must be masked. */
				fail(c, CloseProtocolError);
				return;
			}
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
				for (int i = 0; i < 8; i++) {
					len = (len << 8) | p[2 + i];
				}
				header = 10;
			}

			const bool control = (opcode & 0x08) != 0;
			if (control && (!fin || len > 125)) {
				fail(c, CloseProtocolError);
				return;
			}
			/* Section 4.2 limit, checked before buffering the payload. */
			const uint64_t maxWire = uint64_t(m_settings.maxMessageSize) + 1;
			if (!control && (len > maxWire || uint64_t(c.fragment.size()) + len > maxWire)) {
				fail(c, CloseTooBig);
				return;
			}
			if (avail < header + 4 + len) {
				break;
			}

			const uint8_t *mask = p + header;
			std::vector<uint8_t> payload(p + header + 4, p + header + 4 + size_t(len));
			for (size_t i = 0; i < payload.size(); i++) {
				payload[i] ^= mask[i & 3];
			}
			pos += header + 4 + size_t(len);

			switch (opcode) {
				case OpContinuation:
					if (!c.fragmenting) {
						fail(c, CloseProtocolError);
						return;
					}
					c.fragment.insert(c.fragment.end(), payload.begin(), payload.end());
					if (fin) {
						c.fragmenting = false;
						std::vector<uint8_t> msg;
						msg.swap(c.fragment);
						deliver(c, msg);
					}
					break;
				case OpBinary:
					if (c.fragmenting) {
						fail(c, CloseProtocolError);
						return;
					}
					if (fin) {
						deliver(c, payload);
					}
					else {
						c.fragmenting = true;
						c.fragment = std::move(payload);
					}
					break;
				case OpText:
					fail(c, CloseUnsupportedData);
					return;
				case OpClose: {
					uint16_t code = CloseNormal;
					if (payload.size() >= 2) {
						code = uint16_t((payload[0] << 8) | payload[1]);
					}
					fail(c, code);
					return;
				}
				case OpPing:
					queueFrame(c, OpPong, payload.data(), payload.size(), nullptr, 0);
					break;
				case OpPong:
					break;
				default:
					fail(c, CloseProtocolError);
					return;
			}
		}
		if (c.state == Connection::State::Open) {
			c.in.erase(c.in.begin(), c.in.begin() + std::ptrdiff_t(pos));
		}
	}

	void deliver(Connection &c, const std::vector<uint8_t> &msg)
	{
		if (msg.empty() || msg[0] > uint8_t(Channel::Input)) {
			fail(c, CloseProtocolError);
			return;
		}
		m_events.push_back({TransportEvent::Type::Received,
		                    c.id,
		                    Channel(msg[0]),
		                    std::vector<uint8_t>(msg.begin() + 1, msg.end())});
	}

	void checkTimers(Connection &c, Clock::time_point now)
	{
		if (c.state == Connection::State::Handshake) {
			if (elapsedMs(c.created, now) > m_settings.handshakeTimeoutMs) {
				c.dead = true;
			}
			return;
		}
		if (c.state != Connection::State::Open) {
			return;
		}
		if (elapsedMs(c.lastRecv, now) > m_settings.idleTimeoutMs) {
			fail(c, CloseGoingAway);
			return;
		}
		if (elapsedMs(c.lastRecv, now) > m_settings.pingIntervalMs &&
		    elapsedMs(c.lastPing, now) > m_settings.pingIntervalMs)
		{
			c.lastPing = now;
			queueFrame(c, OpPing, nullptr, 0, nullptr, 0);
		}
	}

	static void queueFrame(Connection &c,
	                       uint8_t opcode,
	                       const uint8_t *a,
	                       size_t aSize,
	                       const uint8_t *b,
	                       size_t bSize)
	{
		const uint64_t len = uint64_t(aSize) + bSize;
		c.out.push_back(uint8_t(0x80 | opcode));
		if (len < 126) {
			c.out.push_back(uint8_t(len));
		}
		else if (len <= 0xFFFF) {
			c.out.push_back(126);
			c.out.push_back(uint8_t(len >> 8));
			c.out.push_back(uint8_t(len));
		}
		else {
			c.out.push_back(127);
			for (int i = 7; i >= 0; i--) {
				c.out.push_back(uint8_t(len >> (i * 8)));
			}
		}
		if (aSize) {
			c.out.insert(c.out.end(), a, a + aSize);
		}
		if (bSize) {
			c.out.insert(c.out.end(), b, b + bSize);
		}
	}

	static void queueClose(Connection &c, uint16_t code)
	{
		/* 1005/1006/1015 must not be sent on the wire. */
		if (code == 1005 || code == 1006 || code == 1015 || code < 1000) {
			code = CloseNormal;
		}
		const uint8_t payload[2] = {uint8_t(code >> 8), uint8_t(code)};
		queueFrame(c, OpClose, payload, 2, nullptr, 0);
	}

	void enterClosing(Connection &c)
	{
		c.state = Connection::State::Closing;
		c.closingSince = Clock::now();
		announceDisconnect(c);
	}

	/* Sends a close frame (if open) and drops the connection once it is flushed. */
	void fail(Connection &c, uint16_t code)
	{
		if (c.state == Connection::State::Open) {
			queueClose(c, code);
			enterClosing(c);
		}
		else if (c.state == Connection::State::Handshake) {
			c.dead = true;
		}
	}

	void announceDisconnect(Connection &c)
	{
		if (c.announced) {
			c.announced = false;
			m_events.push_back({TransportEvent::Type::Disconnected, c.id, Channel::Control, {}});
		}
	}

	void flush(Connection &c)
	{
		while (c.outOffset < c.out.size()) {
			const long n = sendSome(c.sock, c.out.data() + c.outOffset, c.out.size() - c.outOffset);
			if (n < 0) {
				c.dead = true;
				return;
			}
			if (n == 0) {
				break;
			}
			c.outOffset += size_t(n);
		}
		if (c.outOffset == c.out.size()) {
			c.out.clear();
			c.outOffset = 0;
		}
		else if (c.outOffset > 64 * 1024) {
			c.out.erase(c.out.begin(), c.out.begin() + std::ptrdiff_t(c.outOffset));
			c.outOffset = 0;
		}
	}

	WebSocketServerSettings m_settings;
	SocketHandle m_listen = kInvalidSocket;
	uint16_t m_port = 0;
	int m_maxPeers = 0;
	PeerId m_nextId = 1;
	std::vector<std::unique_ptr<Connection>> m_conns;
	std::vector<TransportEvent> m_events;
};

} // namespace

std::unique_ptr<WebSocketServerTransport> createWebSocketServerTransport(
    const WebSocketServerSettings &settings)
{
	return std::make_unique<WebSocketServer>(settings);
}

} // namespace net
