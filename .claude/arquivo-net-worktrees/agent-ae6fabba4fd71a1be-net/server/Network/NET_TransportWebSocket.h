/* WebSocket transports (server, browser client) and the multi-transport used for cross-play.
 * Contract: docs/multiplayer-protocol.md sections 4.1, 4.2 and 9.2. */

#pragma once

#include "NET_ITransport.h"

namespace net {

namespace ws {

/* Reliable message limit (section 4.2). A WebSocket message carries one extra channel byte. */
constexpr size_t kMaxMessageSize = 65536;

/* Handshake helpers (RFC 6455 section 4.2.2), exposed for tests. */
void sha1(const uint8_t *data, size_t size, uint8_t out[20]);
std::string base64Encode(const uint8_t *data, size_t size);
std::string computeAcceptKey(const std::string &clientKey);

} // namespace ws

struct WebSocketServerSettings {
	int maxPending = 16;                 /* Connections still in handshake (4.2). */
	uint32_t handshakeTimeoutMs = 5000;  /* 4.2. */
	uint32_t idleTimeoutMs = 10000;      /* No bytes received (4.2). */
	uint32_t pingIntervalMs = 2000;      /* Server ping when the peer is quiet. */
	uint32_t closeTimeoutMs = 1000;      /* Wait for the close frame to flush. */
	size_t maxMessageSize = ws::kMaxMessageSize;
	size_t maxSendBuffer = 4u * 1024u * 1024u; /* Slow reader is dropped past this. */
};

/* Server side of RFC 6455. Binary frames only; the first payload byte is the Channel.
 * connect() is not supported (returns false). Disconnected is reported once per peer,
 * also after a local disconnect(), on the next poll(). */
class WebSocketServerTransport : public ITransport {
public:
	/* Port actually bound by listen() (useful with port 0). 0 if not listening. */
	virtual uint16_t boundPort() const = 0;
};

std::unique_ptr<WebSocketServerTransport> createWebSocketServerTransport(
    const WebSocketServerSettings &settings = WebSocketServerSettings());

/* Joins several server transports (e.g. ENet + WebSocket) behind one PeerId space. */
class MultiTransport : public ITransport {
public:
	/* port 0 = use the port given to listen(). Must be called before listen(). */
	virtual void add(std::unique_ptr<ITransport> transport, uint16_t port) = 0;
	/* Whether the inner transport of this peer is reliable for every channel. */
	virtual bool reliableFor(PeerId peer) const = 0;
};

std::unique_ptr<MultiTransport> createMultiTransport();

/* Browser client (Emscripten websocket.h). Outside __EMSCRIPTEN__ it is a stub whose
 * connect() fails. host may be a full ws:// or wss:// URL, then port is ignored. */
std::unique_ptr<ITransport> createWebClientTransport();

} // namespace net
