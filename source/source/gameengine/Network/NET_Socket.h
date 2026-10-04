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
 *  \brief Minimal non-blocking TCP socket helpers (winsock2 / POSIX), internal to the network core.
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

/// Non-blocking IPv4 listener on all interfaces; port 0 picks a free port.
inline Handle listenTcp(uint16_t port, int backlog)
{
	Handle s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
	if (s == kInvalid) {
		return kInvalid;
	}
#ifndef _WIN32
	int on = 1;
	setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
#endif
	sockaddr_in addr = {};
	addr.sin_family = AF_INET;
	addr.sin_addr.s_addr = htonl(INADDR_ANY);
	addr.sin_port = htons(port);
	if (bind(s, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) != 0 || ::listen(s, backlog) != 0 ||
	    !setNonBlocking(s))
	{
		close(s);
		return kInvalid;
	}
	return s;
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
	sockaddr_in addr = {};
	socklen_t len = sizeof(addr);
	if (getsockname(s, reinterpret_cast<sockaddr *>(&addr), &len) != 0) {
		return 0;
	}
	return ntohs(addr.sin_port);
}

/// Blocking IPv4 connect (tests and tools only); the socket is left blocking.
inline Handle connectTcp(const std::string &host, uint16_t port)
{
	addrinfo hints = {};
	hints.ai_family = AF_INET;
	hints.ai_socktype = SOCK_STREAM;
	addrinfo *info = nullptr;
	if (getaddrinfo(host.c_str(), std::to_string(port).c_str(), &hints, &info) != 0 || !info) {
		return kInvalid;
	}
	Handle s = socket(info->ai_family, info->ai_socktype, info->ai_protocol);
	if (s != kInvalid && ::connect(s, info->ai_addr, int(info->ai_addrlen)) != 0) {
		close(s);
		s = kInvalid;
	}
	freeaddrinfo(info);
	if (s != kInvalid) {
		setNoDelay(s);
	}
	return s;
}

}  // namespace sock
}  // namespace net

#endif  // __NET_SOCKET_H__
