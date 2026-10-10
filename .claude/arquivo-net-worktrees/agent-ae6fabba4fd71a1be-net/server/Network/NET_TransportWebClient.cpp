/* Browser WebSocket client (Emscripten websocket.h). Outside __EMSCRIPTEN__ this is a stub
 * so the core still builds on desktop. One channel byte prefixes every binary message. */

#include "NET_TransportWebSocket.h"

#ifdef __EMSCRIPTEN__
#  include <cstring>
#  include <emscripten/websocket.h>
#endif

namespace net {

namespace {

#ifdef __EMSCRIPTEN__

/* Single server connection; its PeerId is always 1. */
class WebClient final : public ITransport {
public:
	~WebClient() override
	{
		shutdown();
	}

	bool listen(uint16_t, int) override
	{
		return false;
	}

	bool connect(const std::string &host, uint16_t port) override
	{
		if (m_socket > 0 || !emscripten_websocket_is_supported()) {
			return false;
		}
		std::string url = host;
		if (url.compare(0, 5, "ws://") != 0 && url.compare(0, 6, "wss://") != 0) {
			url = "ws://" + host + ":" + std::to_string(port) + "/";
		}
		EmscriptenWebSocketCreateAttributes attr;
		emscripten_websocket_init_create_attributes(&attr);
		attr.url = url.c_str();
		attr.protocols = nullptr;
		attr.createOnMainThread = EM_TRUE;
		const EMSCRIPTEN_WEBSOCKET_T sock = emscripten_websocket_new(&attr);
		if (sock <= 0) {
			return false;
		}
		m_socket = sock;
		m_open = false;
		emscripten_websocket_set_onopen_callback(sock, this, onOpen);
		emscripten_websocket_set_onmessage_callback(sock, this, onMessage);
		emscripten_websocket_set_onclose_callback(sock, this, onClose);
		emscripten_websocket_set_onerror_callback(sock, this, onError);
		return true;
	}

	void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) override
	{
		if (peer != kServerPeer || !m_open || size > ws::kMaxMessageSize) {
			return;
		}
		m_sendBuf.resize(size + 1);
		m_sendBuf[0] = uint8_t(channel);
		if (size) {
			std::memcpy(m_sendBuf.data() + 1, data, size);
		}
		emscripten_websocket_send_binary(m_socket, m_sendBuf.data(), uint32_t(m_sendBuf.size()));
	}

	void disconnect(PeerId peer) override
	{
		if (peer == kServerPeer && m_socket > 0) {
			close(true);
		}
	}

	void poll(std::vector<TransportEvent> &events) override
	{
		/* Callbacks run on the browser event loop between frames; just hand them over. */
		for (TransportEvent &e : m_events) {
			events.push_back(std::move(e));
		}
		m_events.clear();
	}

	void shutdown() override
	{
		if (m_socket > 0) {
			close(false);
		}
		m_events.clear();
	}

	bool reliableAll() const override
	{
		return true;
	}

private:
	static constexpr PeerId kServerPeer = 1;

	void close(bool announce)
	{
		emscripten_websocket_close(m_socket, 1000, "");
		emscripten_websocket_delete(m_socket);
		m_socket = 0;
		if (announce && m_open) {
			m_events.push_back({TransportEvent::Type::Disconnected, kServerPeer, Channel::Control, {}});
		}
		m_open = false;
	}

	static EM_BOOL onOpen(int, const EmscriptenWebSocketOpenEvent *, void *user)
	{
		WebClient *self = static_cast<WebClient *>(user);
		self->m_open = true;
		self->m_events.push_back({TransportEvent::Type::Connected, kServerPeer, Channel::Control, {}});
		return EM_TRUE;
	}

	static EM_BOOL onMessage(int, const EmscriptenWebSocketMessageEvent *e, void *user)
	{
		WebClient *self = static_cast<WebClient *>(user);
		if (e->isText || e->numBytes == 0 || e->data[0] > uint8_t(Channel::Input)) {
			return EM_TRUE; /* Not part of the protocol: ignore. */
		}
		self->m_events.push_back({TransportEvent::Type::Received,
		                          kServerPeer,
		                          Channel(e->data[0]),
		                          std::vector<uint8_t>(e->data + 1, e->data + e->numBytes)});
		return EM_TRUE;
	}

	static EM_BOOL onClose(int, const EmscriptenWebSocketCloseEvent *, void *user)
	{
		WebClient *self = static_cast<WebClient *>(user);
		/* Also reported for a failed connect, so the session can show an error. */
		self->m_events.push_back({TransportEvent::Type::Disconnected, kServerPeer, Channel::Control, {}});
		self->m_open = false;
		if (self->m_socket > 0) {
			emscripten_websocket_delete(self->m_socket);
			self->m_socket = 0;
		}
		return EM_TRUE;
	}

	static EM_BOOL onError(int, const EmscriptenWebSocketErrorEvent *, void *)
	{
		return EM_TRUE; /* onclose always follows. */
	}

	EMSCRIPTEN_WEBSOCKET_T m_socket = 0;
	bool m_open = false;
	std::vector<uint8_t> m_sendBuf;
	std::vector<TransportEvent> m_events;
};

#else

/* Desktop stub: browser-only transport. */
class WebClient final : public ITransport {
public:
	bool listen(uint16_t, int) override
	{
		return false;
	}
	bool connect(const std::string &, uint16_t) override
	{
		return false;
	}
	void send(PeerId, Channel, const uint8_t *, size_t) override
	{
	}
	void disconnect(PeerId) override
	{
	}
	void poll(std::vector<TransportEvent> &) override
	{
	}
	void shutdown() override
	{
	}
	bool reliableAll() const override
	{
		return true;
	}
};

#endif

} // namespace

std::unique_ptr<ITransport> createWebClientTransport()
{
	return std::make_unique<WebClient>();
}

} // namespace net
