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

/** \file gameengine/Network/NET_TransportWebClient.cpp
 *  \ingroup network
 *  \brief Browser WebSocket client (Emscripten). Empty stub on other platforms.
 */

#include "NET_TransportWeb.h"

#ifdef __EMSCRIPTEN__

#  include <emscripten/websocket.h>

#  include <cstring>

namespace net {

namespace {

const PeerId kServerPeer = 1;

/// Events come from browser callbacks on the main thread and are queued until poll().
class WebClientTransport : public ITransport {
public:
	~WebClientTransport() override
	{
		shutdown();
	}

	bool listen(uint16_t, int) override
	{
		return false;  // client only
	}

	bool connect(const std::string &host, uint16_t port) override
	{
		shutdown();
		if (!emscripten_websocket_is_supported()) {
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
		const EMSCRIPTEN_WEBSOCKET_T socket = emscripten_websocket_new(&attr);
		if (socket <= 0) {
			return false;
		}
		m_socket = socket;
		m_connecting = true;
		emscripten_websocket_set_onopen_callback(socket, this, onOpen);
		emscripten_websocket_set_onmessage_callback(socket, this, onMessage);
		emscripten_websocket_set_onerror_callback(socket, this, onError);
		emscripten_websocket_set_onclose_callback(socket, this, onClose);
		return true;
	}

	void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) override
	{
		if (peer != kServerPeer || !m_open || size + 1 > kMaxWebSocketMessage) {
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
		if (peer != kServerPeer || m_socket <= 0) {
			return;
		}
		emscripten_websocket_close(m_socket, 1000, "");
		closed();
	}

	void poll(std::vector<TransportEvent> &events) override
	{
		for (TransportEvent &ev : m_pending) {
			events.push_back(std::move(ev));
		}
		m_pending.clear();
	}

	void shutdown() override
	{
		if (m_socket > 0) {
			emscripten_websocket_close(m_socket, 1001, "");
			emscripten_websocket_delete(m_socket);
			m_socket = 0;
		}
		m_open = false;
		m_connecting = false;
		m_pending.clear();
	}

	bool reliableAll() const override
	{
		return true;
	}

private:
	/// Reports the disconnect once (also a failed connect) and detaches the callbacks.
	void closed()
	{
		if (m_socket <= 0) {
			return;
		}
		if (m_open || m_connecting) {
			TransportEvent ev;
			ev.type = TransportEvent::Type::Disconnected;
			ev.peer = kServerPeer;
			m_pending.push_back(std::move(ev));
		}
		m_open = false;
		m_connecting = false;
		emscripten_websocket_delete(m_socket);
		m_socket = 0;
	}

	static EM_BOOL onOpen(int, const EmscriptenWebSocketOpenEvent *, void *user)
	{
		WebClientTransport *self = static_cast<WebClientTransport *>(user);
		self->m_open = true;
		self->m_connecting = false;
		TransportEvent ev;
		ev.type = TransportEvent::Type::Connected;
		ev.peer = kServerPeer;
		self->m_pending.push_back(std::move(ev));
		return EM_TRUE;
	}

	static EM_BOOL onMessage(int, const EmscriptenWebSocketMessageEvent *event, void *user)
	{
		WebClientTransport *self = static_cast<WebClientTransport *>(user);
		if (event->isText || event->numBytes < 1 || event->numBytes > kMaxWebSocketMessage ||
		    event->data[0] >= kChannelCount)
		{
			// Same rule as the server: drop the connection on a malformed message.
			emscripten_websocket_close(self->m_socket, 1002, "");
			self->closed();
			return EM_TRUE;
		}
		TransportEvent ev;
		ev.type = TransportEvent::Type::Received;
		ev.peer = kServerPeer;
		ev.channel = Channel(event->data[0]);
		ev.data.assign(event->data + 1, event->data + event->numBytes);
		self->m_pending.push_back(std::move(ev));
		return EM_TRUE;
	}

	static EM_BOOL onError(int, const EmscriptenWebSocketErrorEvent *, void *user)
	{
		static_cast<WebClientTransport *>(user)->closed();
		return EM_TRUE;
	}

	static EM_BOOL onClose(int, const EmscriptenWebSocketCloseEvent *, void *user)
	{
		static_cast<WebClientTransport *>(user)->closed();
		return EM_TRUE;
	}

	EMSCRIPTEN_WEBSOCKET_T m_socket = 0;
	bool m_open = false;
	bool m_connecting = false;
	std::vector<uint8_t> m_sendBuf;
	std::vector<TransportEvent> m_pending;
};

}  // namespace

std::unique_ptr<ITransport> createWebClientTransport()
{
	return std::unique_ptr<ITransport>(new WebClientTransport());
}

}  // namespace net

#else  // __EMSCRIPTEN__

namespace net {

std::unique_ptr<ITransport> createWebClientTransport()
{
	return nullptr;
}

}  // namespace net

#endif  // __EMSCRIPTEN__
