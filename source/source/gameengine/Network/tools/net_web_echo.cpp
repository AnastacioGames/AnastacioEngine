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

/** \file gameengine/Network/tools/net_web_echo.cpp
 *  \ingroup network
 *  \brief Minimal wasm client for net_echo over WebSocket (Emscripten only).
 *
 *   node net_web_echo.js [host=127.0.0.1] [port=7778]
 *
 * Connects with Hello, sends 3 Chat messages and exits with 0 once the three echoes are back
 * (1 on rejection, disconnection or after 10 s). In a browser it runs with the default host/port.
 */

#include "NET_Session.h"
#include "NET_TransportWeb.h"

#include <emscripten.h>

#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>

using namespace net;

namespace {

const char *kGameId = "anastacio.net_echo";
const uint64_t kSceneHash = 0x4543484F;  // "ECHO", same as net_echo
const int kMessages = 3;
const uint64_t kTimeoutMs = 10000;

struct App {
	std::unique_ptr<ITransport> transport;
	std::unique_ptr<ClientSession> client;
	uint64_t startMs = 0;
	int sent = 0;
	int echoed = 0;
};

void finish(App &app, int code)
{
	std::printf("net_web_echo: %d/%d echoes, %s\n", app.echoed, kMessages, code == 0 ? "OK" : "FAILED");
	std::fflush(stdout);
	if (app.client) {
		app.client->disconnect();
	}
	emscripten_cancel_main_loop();
	emscripten_force_exit(code);
}

void frame(void *arg)
{
	App &app = *static_cast<App *>(arg);
	const uint64_t now = steadyClockMs();
	std::vector<SessionEvent> events;
	app.client->update(now, events);
	for (const SessionEvent &ev : events) {
		switch (ev.type) {
			case SessionEvent::Type::Connected:
				std::printf("connected as client %u\n", unsigned(ev.client));
				app.client->sceneLoaded(kSceneHash);
				for (; app.sent < kMessages; ++app.sent) {
					ChatMsg chat;
					chat.fromClient = app.client->clientId();
					chat.text = "web #" + std::to_string(app.sent + 1);
					app.client->send(Channel::Rpc, makePacket(chat));
				}
				break;
			case SessionEvent::Type::Rejected:
				std::printf("rejected, reason %u\n", unsigned(ev.rejectReason));
				finish(app, 1);
				return;
			case SessionEvent::Type::Disconnected:
				std::printf("disconnected, reason %u\n", unsigned(ev.disconnectReason));
				finish(app, 1);
				return;
			case SessionEvent::Type::Message:
				if (ev.messageType == uint8_t(MessageType::Chat)) {
					ChatMsg chat;
					BitReader r(ev.body.data(), ev.body.size());
					if (decode(r, chat) && chat.fromClient == app.client->clientId()) {
						std::printf("echo: %s\n", chat.text.c_str());
						++app.echoed;
					}
				}
				break;
			default:
				break;
		}
	}
	std::fflush(stdout);
	if (app.echoed >= kMessages) {
		finish(app, 0);
	}
	else if (now - app.startMs > kTimeoutMs) {
		finish(app, 1);
	}
}

}  // namespace

int main(int argc, char **argv)
{
	static App app;
	const std::string host = argc > 1 ? argv[1] : "127.0.0.1";
	const uint16_t port = uint16_t(argc > 2 ? std::atoi(argv[2]) : 7778);
	app.transport = createWebClientTransport();
	if (!app.transport) {
		std::fprintf(stderr, "net_web_echo: no WebSocket transport\n");
		return 1;
	}
	ClientConfig config;
	config.gameId = kGameId;
	config.sceneHash = kSceneHash;
	config.playerName = "web";
	app.client = std::make_unique<ClientSession>(*app.transport, config);
	app.startMs = steadyClockMs();
	if (!app.client->connect(host, port, app.startMs)) {
		std::fprintf(stderr, "net_web_echo: cannot connect to ws://%s:%u/\n", host.c_str(), unsigned(port));
		return 1;
	}
	std::printf("net_web_echo: connecting to ws://%s:%u/\n", host.c_str(), unsigned(port));
	// Returns to the JavaScript event loop between frames so the WebSocket callbacks run.
	emscripten_set_main_loop_arg(frame, &app, 60, 1);
	return 0;
}
