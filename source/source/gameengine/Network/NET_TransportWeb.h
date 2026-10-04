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

/** \file NET_TransportWeb.h
 *  \ingroup network
 *  \brief WebSocket transports (server, Emscripten client) and the cross-play multi transport.
 *
 * WebSocket has no channels: every binary message starts with one channel byte (contract 4.1) and
 * everything arrives reliable and ordered.
 */

#ifndef __NET_TRANSPORTWEB_H__
#define __NET_TRANSPORTWEB_H__

#include "NET_ITransport.h"
#include "NET_Types.h"

#include <string>
#include <string_view>

namespace net {

/// Largest WebSocket message accepted: channel byte + reliable message limit (contract 4.2).
constexpr size_t kMaxWebSocketMessage = kMaxReliableMessage + 1;

/// RFC 6455 server over plain TCP (no TLS, see NOTES-C.md). reliableAll() is true.
std::unique_ptr<ITransport> createWebSocketServerTransport();

/// Sec-WebSocket-Accept value for a client key (SHA-1 + base64, RFC 6455 4.2.2).
std::string webSocketAcceptKey(std::string_view clientKey);

struct MultiTransportEntry {
	std::unique_ptr<ITransport> transport;
	uint16_t port = 0;  // 0 = use the port given to listen()
};

/// Server-only transport joining several transports (e.g. ENet + WebSocket) for cross-play.
/// Peer ids are remapped so they never collide; connect() fails.
std::unique_ptr<ITransport> createMultiTransport(std::vector<MultiTransportEntry> entries);

/// Browser client over emscripten/websocket.h; nullptr when not built with Emscripten.
/// connect() takes a host and port (ws://host:port/) or a full ws:// / wss:// URL as host.
std::unique_ptr<ITransport> createWebClientTransport();

}  // namespace net

#endif  // __NET_TRANSPORTWEB_H__
