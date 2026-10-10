/* Minimal WebSocket test client (raw sockets) that pumps the server while it waits. */

#pragma once

#include "NET_TransportWebSocket.h"

#include <chrono>
#include <cstring>
#include <functional>
#include <string>
#include <thread>
#include <vector>

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
#  include <fcntl.h>
#  include <netinet/in.h>
#  include <sys/select.h>
#  include <sys/socket.h>
#  include <unistd.h>
#endif

namespace nettest {

#ifdef _WIN32
using Sock = SOCKET;
static const Sock kBad = INVALID_SOCKET;
inline void closeSock(Sock s)
{
	closesocket(s);
}
#else
using Sock = int;
static const Sock kBad = -1;
inline void closeSock(Sock s)
{
	close(s);
}
#endif

struct Frame {
	bool fin = false;
	uint8_t opcode = 0;
	bool masked = false;
	std::vector<uint8_t> payload;
};

class TestClient {
public:
	/* pump() is called while waiting so the single-threaded server makes progress. */
	TestClient(net::ITransport &server, std::vector<net::TransportEvent> &events)
	    : m_server(server), m_events(events)
	{
	}

	~TestClient()
	{
		if (m_sock != kBad) {
			closeSock(m_sock);
		}
	}

	void pump()
	{
		m_server.poll(m_events);
	}

	bool connectTo(uint16_t port)
	{
		m_sock = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
		if (m_sock == kBad) {
			return false;
		}
		sockaddr_in addr;
		std::memset(&addr, 0, sizeof(addr));
		addr.sin_family = AF_INET;
		addr.sin_port = htons(port);
		addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
		/* Loopback connect completes against the listen backlog without accept(). */
		return ::connect(m_sock, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) == 0;
	}

	bool sendRaw(const void *data, size_t size)
	{
		const char *p = static_cast<const char *>(data);
		while (size > 0) {
			const int n = int(::send(m_sock, p, int(size), 0));
			if (n <= 0) {
				return false;
			}
			p += n;
			size -= size_t(n);
		}
		return true;
	}

	bool sendRaw(const std::string &s)
	{
		return sendRaw(s.data(), s.size());
	}

	static std::string request(const std::string &key = "dGhlIHNhbXBsZSBub25jZQ==")
	{
		return "GET /chat HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
		       "Connection: keep-alive, Upgrade\r\nSec-WebSocket-Key: " +
		       key + "\r\nSec-WebSocket-Version: 13\r\n\r\n";
	}

	/* Sends the upgrade request and returns the HTTP response header (empty on timeout). */
	std::string handshake(const std::string &req = request())
	{
		if (!sendRaw(req)) {
			return std::string();
		}
		std::string resp;
		while (resp.find("\r\n\r\n") == std::string::npos) {
			uint8_t c;
			if (!readExact(&c, 1)) {
				break;
			}
			resp += char(c);
		}
		return resp;
	}

	static std::vector<uint8_t> buildFrame(uint8_t opcode,
	                                       const std::vector<uint8_t> &payload,
	                                       bool fin = true,
	                                       bool mask = true,
	                                       uint64_t fakeLen = 0)
	{
		std::vector<uint8_t> f;
		f.push_back(uint8_t((fin ? 0x80 : 0) | opcode));
		const uint64_t len = fakeLen ? fakeLen : payload.size();
		const uint8_t m = mask ? 0x80 : 0;
		if (len < 126) {
			f.push_back(uint8_t(m | len));
		}
		else if (len <= 0xFFFF) {
			f.push_back(uint8_t(m | 126));
			f.push_back(uint8_t(len >> 8));
			f.push_back(uint8_t(len));
		}
		else {
			f.push_back(uint8_t(m | 127));
			for (int i = 7; i >= 0; i--) {
				f.push_back(uint8_t(len >> (i * 8)));
			}
		}
		const uint8_t key[4] = {0x12, 0x34, 0x56, 0x78};
		if (mask) {
			f.insert(f.end(), key, key + 4);
		}
		for (size_t i = 0; i < payload.size(); i++) {
			f.push_back(mask ? uint8_t(payload[i] ^ key[i & 3]) : payload[i]);
		}
		return f;
	}

	bool sendFrame(uint8_t opcode, const std::vector<uint8_t> &payload, bool fin = true, bool mask = true)
	{
		const std::vector<uint8_t> f = buildFrame(opcode, payload, fin, mask);
		return sendRaw(f.data(), f.size());
	}

	bool readFrame(Frame &out)
	{
		uint8_t h[2];
		if (!readExact(h, 2)) {
			return false;
		}
		out.fin = (h[0] & 0x80) != 0;
		out.opcode = h[0] & 0x0F;
		out.masked = (h[1] & 0x80) != 0;
		uint64_t len = h[1] & 0x7F;
		if (len == 126) {
			uint8_t e[2];
			if (!readExact(e, 2)) {
				return false;
			}
			len = (uint64_t(e[0]) << 8) | e[1];
		}
		else if (len == 127) {
			uint8_t e[8];
			if (!readExact(e, 8)) {
				return false;
			}
			len = 0;
			for (int i = 0; i < 8; i++) {
				len = (len << 8) | e[i];
			}
		}
		out.payload.resize(size_t(len));
		return len == 0 || readExact(out.payload.data(), size_t(len));
	}

	/* Reads frames until one with this opcode arrives. */
	bool readFrameOf(uint8_t opcode, Frame &out)
	{
		while (readFrame(out)) {
			if (out.opcode == opcode) {
				return true;
			}
		}
		return false;
	}

	/* True if the server closed the TCP connection (EOF) before the timeout. */
	bool waitEof(int timeoutMs = 2000)
	{
		const auto end = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeoutMs);
		while (std::chrono::steady_clock::now() < end) {
			pump();
			if (readable()) {
				char buf[512];
				const int n = int(::recv(m_sock, buf, sizeof(buf), 0));
				if (n <= 0) {
					return true;
				}
			}
		}
		return false;
	}

	bool readExact(uint8_t *data, size_t size, int timeoutMs = 2000)
	{
		const auto end = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeoutMs);
		while (size > 0) {
			if (std::chrono::steady_clock::now() > end) {
				return false;
			}
			pump();
			if (!readable()) {
				continue;
			}
			const int n = int(::recv(m_sock, reinterpret_cast<char *>(data), int(size), 0));
			if (n <= 0) {
				return false;
			}
			data += n;
			size -= size_t(n);
		}
		return true;
	}

	void closeSocket()
	{
		if (m_sock != kBad) {
			closeSock(m_sock);
			m_sock = kBad;
		}
	}

private:
	bool readable()
	{
		fd_set set;
		FD_ZERO(&set);
		FD_SET(m_sock, &set);
		timeval tv;
		tv.tv_sec = 0;
		tv.tv_usec = 1000;
		return ::select(int(m_sock + 1), &set, nullptr, nullptr, &tv) > 0;
	}

	net::ITransport &m_server;
	std::vector<net::TransportEvent> &m_events;
	Sock m_sock = kBad;
};

/* Polls the transport until pred() is true or the timeout expires. */
inline bool pumpUntil(net::ITransport &t,
                      std::vector<net::TransportEvent> &events,
                      const std::function<bool()> &pred,
                      int timeoutMs = 2000)
{
	const auto end = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeoutMs);
	while (std::chrono::steady_clock::now() < end) {
		t.poll(events);
		if (pred()) {
			return true;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	return false;
}

inline int countEvents(const std::vector<net::TransportEvent> &events, net::TransportEvent::Type type)
{
	int n = 0;
	for (const auto &e : events) {
		if (e.type == type) {
			n++;
		}
	}
	return n;
}

inline const net::TransportEvent *findEvent(const std::vector<net::TransportEvent> &events,
                                            net::TransportEvent::Type type)
{
	for (const auto &e : events) {
		if (e.type == type) {
			return &e;
		}
	}
	return nullptr;
}

} // namespace nettest
