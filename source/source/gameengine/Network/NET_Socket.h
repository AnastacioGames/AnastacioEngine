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

/** \file NET_Socket.h
 *  \ingroup network
 *  \brief Minimal non-blocking TCP and UDP socket helpers (winsock2 / POSIX), internal to the network core.
 */

#ifndef __NET_SOCKET_H__
#define __NET_SOCKET_H__

#include <cstddef>
#include <cstdint>
#include <string>

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
#  include <netdb.h>
#  include <netinet/in.h>
#  include <netinet/tcp.h>
#  include <sys/socket.h>
#  include <unistd.h>
#endif

namespace net {
namespace sock {

#ifdef _WIN32
using Handle = SOCKET;
const Handle kInvalid = INVALID_SOCKET;
#else
using Handle = int;
const Handle kInvalid = -1;
#endif

/// Result of a non-blocking recv/send: bytes moved, 0 = would block, -1 = closed or error.
using IoResult = long;

/// Process-wide socket library init (WSAStartup on Windows); call once per user, pairs with release().
inline bool acquire()
{
#ifdef _WIN32
	WSADATA data;
	return WSAStartup(MAKEWORD(2, 2), &data) == 0;
#else
	return true;
#endif
}

inline void release()
{
#ifdef _WIN32
	WSACleanup();
#endif
}

inline void close(Handle s)
{
	if (s == kInvalid) {
		return;
	}
#ifdef _WIN32
	closesocket(s);
#else
	::close(s);
#endif
}

inline bool setNonBlocking(Handle s)
{
#ifdef _WIN32
	u_long on = 1;
	return ioctlsocket(s, FIONBIO, &on) == 0;
#else
	const int flags = fcntl(s, F_GETFL, 0);
	return flags >= 0 && fcntl(s, F_SETFL, flags | O_NONBLOCK) == 0;
#endif
}

inline void setNoDelay(Handle s)
{
	int on = 1;
	setsockopt(s, IPPROTO_TCP, TCP_NODELAY, reinterpret_cast<const char *>(&on), sizeof(on));
}

inline bool wouldBlock()
{
#ifdef _WIN32
	const int err = WSAGetLastError();
	return err == WSAEWOULDBLOCK || err == WSAEINTR;
#else
	return errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR;
#endif
}

/// Binds and listens; family is AF_INET or AF_INET6 (dual-stack, IPV6_V6ONLY off).
inline Handle listenTcpFamily(int family, uint16_t port, int backlog)
{
	Handle s = socket(family, SOCK_STREAM, IPPROTO_TCP);
	if (s == kInvalid) {
		return kInvalid;
	}
	int on = 1;
#ifndef _WIN32
	setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
#endif
	int ok;
	if (family == AF_INET6) {
		int off = 0;
		setsockopt(s, IPPROTO_IPV6, IPV6_V6ONLY, reinterpret_cast<const char *>(&off), sizeof(off));
		sockaddr_in6 addr = {};
		addr.sin6_family = AF_INET6;
		addr.sin6_addr = in6addr_any;
		addr.sin6_port = htons(port);
		ok = bind(s, reinterpret_cast<sockaddr *>(&addr), sizeof(addr));
	}
	else {
		sockaddr_in addr = {};
		addr.sin_family = AF_INET;
		addr.sin_addr.s_addr = htonl(INADDR_ANY);
		addr.sin_port = htons(port);
		ok = bind(s, reinterpret_cast<sockaddr *>(&addr), sizeof(addr));
	}
	(void)on;
	if (ok != 0 || ::listen(s, backlog) != 0 || !setNonBlocking(s)) {
		close(s);
		return kInvalid;
	}
	return s;
}

/// Non-blocking listener on all interfaces; port 0 picks a free port. Tries a dual-stack
/// IPv6 socket first (accepts IPv4 and IPv6 clients) and falls back to IPv4 only when the
/// host has no IPv6.
inline Handle listenTcp(uint16_t port, int backlog)
{
	Handle s = listenTcpFamily(AF_INET6, port, backlog);
	return s != kInvalid ? s : listenTcpFamily(AF_INET, port, backlog);
}

/// Returns kInvalid when nothing is pending. The accepted socket is non-blocking.
inline Handle accept(Handle listener)
{
	Handle s = ::accept(listener, nullptr, nullptr);
	if (s == kInvalid) {
		return kInvalid;
	}
	if (!setNonBlocking(s)) {
		close(s);
		return kInvalid;
	}
	setNoDelay(s);
#ifdef SO_NOSIGPIPE
	int on = 1;
	setsockopt(s, SOL_SOCKET, SO_NOSIGPIPE, &on, sizeof(on));
#endif
	return s;
}

inline IoResult recv(Handle s, uint8_t *data, size_t size)
{
#ifdef _WIN32
	const int n = ::recv(s, reinterpret_cast<char *>(data), int(size), 0);
#else
	const ssize_t n = ::recv(s, data, size, 0);
#endif
	if (n > 0) {
		return IoResult(n);
	}
	if (n < 0 && wouldBlock()) {
		return 0;
	}
	return -1;  // orderly close or error
}

inline IoResult send(Handle s, const uint8_t *data, size_t size)
{
#if defined(_WIN32)
	const int n = ::send(s, reinterpret_cast<const char *>(data), int(size), 0);
#elif defined(MSG_NOSIGNAL)
	const ssize_t n = ::send(s, data, size, MSG_NOSIGNAL);
#else
	const ssize_t n = ::send(s, data, size, 0);
#endif
	if (n >= 0) {
		return IoResult(n);
	}
	return wouldBlock() ? 0 : -1;
}

inline uint16_t localPort(Handle s)
{
	sockaddr_storage addr = {};
	socklen_t len = sizeof(addr);
	if (getsockname(s, reinterpret_cast<sockaddr *>(&addr), &len) != 0) {
		return 0;
	}
	if (addr.ss_family == AF_INET6) {
		return ntohs(reinterpret_cast<const sockaddr_in6 *>(&addr)->sin6_port);
	}
	return ntohs(reinterpret_cast<const sockaddr_in *>(&addr)->sin_port);
}

/// True when text is a literal IPv6 address (brackets allowed: "[::1]").
inline bool isIpv6Literal(const std::string &text)
{
	std::string t = text;
	if (t.size() >= 2 && t.front() == '[' && t.back() == ']') {
		t = t.substr(1, t.size() - 2);
	}
	in6_addr a = {};
	return inet_pton(AF_INET6, t.c_str(), &a) == 1;
}

/// True when the host can open an IPv6 loopback socket (used by tests to skip).
inline bool hasIpv6Loopback()
{
	Handle s = socket(AF_INET6, SOCK_STREAM, IPPROTO_TCP);
	if (s == kInvalid) {
		return false;
	}
	sockaddr_in6 addr = {};
	addr.sin6_family = AF_INET6;
	addr.sin6_addr = in6addr_loopback;
	const bool ok = bind(s, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) == 0;
	close(s);
	return ok;
}

/// Blocking connect (tests and tools only); the socket is left blocking. Resolves host with
/// AF_UNSPEC (IPv4 or IPv6, literal or name; "[::1]" brackets accepted) and tries each
/// address in resolver order.
inline Handle connectTcp(const std::string &host, uint16_t port)
{
	std::string name = host;
	if (name.size() >= 2 && name.front() == '[' && name.back() == ']') {
		name = name.substr(1, name.size() - 2);
	}
	addrinfo hints = {};
	hints.ai_family = AF_UNSPEC;
	hints.ai_socktype = SOCK_STREAM;
	addrinfo *info = nullptr;
	if (getaddrinfo(name.c_str(), std::to_string(port).c_str(), &hints, &info) != 0 || !info) {
		return kInvalid;
	}
	Handle s = kInvalid;
	for (addrinfo *it = info; it && s == kInvalid; it = it->ai_next) {
		s = socket(it->ai_family, it->ai_socktype, it->ai_protocol);
		if (s != kInvalid && ::connect(s, it->ai_addr, int(it->ai_addrlen)) != 0) {
			close(s);
			s = kInvalid;
		}
	}
	freeaddrinfo(info);
	if (s != kInvalid) {
		setNoDelay(s);
	}
	return s;
}

/* UDP (IPv4 only), used by LAN discovery. Addresses are in host byte order. */

/// Non-blocking UDP socket bound to port on all interfaces (0 = any free port).
inline Handle openUdp(uint16_t port, bool broadcast, bool reuseAddress)
{
	Handle s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
	if (s == kInvalid) {
		return kInvalid;
	}
	int on = 1;
	if (reuseAddress) {
		setsockopt(s, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char *>(&on), sizeof(on));
	}
	if (broadcast) {
		setsockopt(s, SOL_SOCKET, SO_BROADCAST, reinterpret_cast<const char *>(&on), sizeof(on));
	}
	sockaddr_in addr = {};
	addr.sin_family = AF_INET;
	addr.sin_addr.s_addr = htonl(INADDR_ANY);
	addr.sin_port = htons(port);
	if (bind(s, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) != 0 || !setNonBlocking(s)) {
		close(s);
		return kInvalid;
	}
	return s;
}

/// Parses a dotted IPv4 address ("255.255.255.255" included). False when invalid.
inline bool parseIpv4(const std::string &text, uint32_t &address)
{
	in_addr a = {};
	if (inet_pton(AF_INET, text.c_str(), &a) != 1) {
		return false;
	}
	address = ntohl(a.s_addr);
	return true;
}

inline std::string formatIpv4(uint32_t address)
{
	return std::to_string((address >> 24) & 0xFF) + "." + std::to_string((address >> 16) & 0xFF) + "." +
	       std::to_string((address >> 8) & 0xFF) + "." + std::to_string(address & 0xFF);
}

/// True when the whole datagram was handed to the system.
inline bool sendTo(Handle s, uint32_t address, uint16_t port, const uint8_t *data, size_t size)
{
	sockaddr_in addr = {};
	addr.sin_family = AF_INET;
	addr.sin_addr.s_addr = htonl(address);
	addr.sin_port = htons(port);
#ifdef _WIN32
	const int n = ::sendto(s, reinterpret_cast<const char *>(data), int(size), 0,
	                       reinterpret_cast<const sockaddr *>(&addr), sizeof(addr));
#else
	const ssize_t n = ::sendto(s, data, size, 0, reinterpret_cast<const sockaddr *>(&addr), sizeof(addr));
#endif
	return n >= 0 && size_t(n) == size;
}

/// One datagram: bytes read (a longer datagram is cut at size), 0 = nothing pending, -1 = error.
inline IoResult recvFrom(Handle s, uint8_t *data, size_t size, uint32_t &address, uint16_t &port)
{
	sockaddr_in addr = {};
	socklen_t len = sizeof(addr);
#ifdef _WIN32
	const int n = ::recvfrom(s, reinterpret_cast<char *>(data), int(size), 0, reinterpret_cast<sockaddr *>(&addr), &len);
	if (n < 0 && WSAGetLastError() == WSAEMSGSIZE) {
		address = ntohl(addr.sin_addr.s_addr);
		port = ntohs(addr.sin_port);
		return IoResult(size);
	}
	if (n < 0 && WSAGetLastError() == WSAECONNRESET) {
		return 0;  // ICMP port unreachable from an earlier send: not an error for UDP
	}
#else
	const ssize_t n = ::recvfrom(s, data, size, 0, reinterpret_cast<sockaddr *>(&addr), &len);
#endif
	if (n < 0) {
		return wouldBlock() ? 0 : -1;
	}
	address = ntohl(addr.sin_addr.s_addr);
	port = ntohs(addr.sin_port);
	return IoResult(n);
}

}  // namespace sock
}  // namespace net

#endif  // __NET_SOCKET_H__
