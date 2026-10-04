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

/** \file gameengine/Network/tools/net_echo.cpp
 *  \ingroup network
 *  \brief Manual test tool: chat echo server (ENet + WebSocket) and ENet client.
 *
 *   net_echo server [udpPort] [wsPort]   (wsPort 0 = no WebSocket)
 *   net_echo client <host> <port> [name] [messages]
 */

#include "NET_ITransport.h"
#include "NET_Session.h"
#include "NET_TransportWeb.h"

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <thread>

using namespace net;

static std::atomic<bool> g_quit(false);

static void onSignal(int)
{
	g_quit = true;
}

static const char *kGameId = "anastacio.net_echo";
static const uint64_t kSceneHash = 0x4543484F;  // "ECHO"

static int runServer(uint16_t port, uint16_t wsPort)
{
	std::vector<MultiTransportEntry> entries(1);
	entries[0].transport = createENetTransport();
	entries[0].port = port;
	ITransport *ws = nullptr;
	if (wsPort) {
		entries.emplace_back();
		entries.back().transport = createWebSocketServerTransport();
		entries.back().port = wsPort;
		ws = entries.back().transport.get();
	}
	std::unique_ptr<ITransport> transport = createMultiTransport(std::move(entries));
	ServerConfig config;
	config.gameId = kGameId;
	config.sceneName = "Echo";
	config.sceneHash = kSceneHash;
	config.maxClients = kMaxClients;
	ServerSession server(*transport, config);
	if (!server.start(port)) {
		std::fprintf(stderr, "net_echo: cannot listen on UDP port %u / TCP port %u\n", unsigned(port),
		             unsigned(wsPort));
		return 1;
	}
	std::printf("net_echo: server on UDP port %u", unsigned(transport->localPort()));
	if (ws) {
		std::printf(", WebSocket on TCP port %u", unsigned(ws->localPort()));
	}
	std::printf("\n");
	std::fflush(stdout);

	const uint64_t start = steadyClockMs();
	while (!g_quit) {
		const uint64_t now = steadyClockMs();
		const Tick tick = Tick(1 + (now - start) * config.tickRate / 1000);
		std::vector<SessionEvent> events;
		server.update(now, tick, events);
		for (const SessionEvent &ev : events) {
			switch (ev.type) {
				case SessionEvent::Type::ClientJoined:
					std::printf("join  %u %s%s\n", unsigned(ev.client), ev.text.c_str(),
					            ev.reconnected ? " (reconnected)" : "");
					break;
				case SessionEvent::Type::ClientLeft:
					std::printf("leave %u reason %u\n", unsigned(ev.client), unsigned(ev.disconnectReason));
					break;
				case SessionEvent::Type::Message:
					if (ev.messageType == uint8_t(MessageType::Chat)) {
						ChatMsg chat;
						BitReader r(ev.body.data(), ev.body.size());
						if (decode(r, chat)) {
							chat.fromClient = ev.client;
							std::printf("chat  %u: %s\n", unsigned(ev.client), chat.text.c_str());
							server.broadcast(Channel::Rpc, makePacket(chat));
						}
					}
					break;
				default:
					break;
			}
		}
		std::fflush(stdout);
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
	}
	server.stop();
	return 0;
}

static int runClient(const std::string &host, uint16_t port, const std::string &name, int count)
{
	std::unique_ptr<ITransport> transport = createENetTransport();
	ClientConfig config;
	config.gameId = kGameId;
	config.sceneHash = kSceneHash;
	config.playerName = name;
	ClientSession client(*transport, config);
	if (!client.connect(host, port, steadyClockMs())) {
		std::fprintf(stderr, "net_echo: cannot connect to %s:%u\n", host.c_str(), unsigned(port));
		return 1;
	}

	int sent = 0, received = 0;
	uint64_t nextSend = 0;
	while (!g_quit) {
		const uint64_t now = steadyClockMs();
		std::vector<SessionEvent> events;
		client.update(now, events);
		for (const SessionEvent &ev : events) {
			switch (ev.type) {
				case SessionEvent::Type::Connected:
					std::printf("connected as client %u, scene %s\n", unsigned(ev.client), ev.text.c_str());
					client.sceneLoaded(kSceneHash);
					nextSend = now + 200;
					break;
				case SessionEvent::Type::Rejected:
					std::printf("rejected, reason %u\n", unsigned(ev.rejectReason));
					return 2;
				case SessionEvent::Type::Disconnected:
					std::printf("disconnected, reason %u\n", unsigned(ev.disconnectReason));
					return 3;
				case SessionEvent::Type::PlayerInfo:
					std::printf("player %u %s flags %u\n", unsigned(ev.client), ev.text.c_str(), unsigned(ev.flags));
					break;
				case SessionEvent::Type::Message:
					if (ev.messageType == uint8_t(MessageType::Chat)) {
						ChatMsg chat;
						BitReader r(ev.body.data(), ev.body.size());
						if (decode(r, chat)) {
							std::printf("echo from %u: %s (rtt %.1f ms)\n", unsigned(chat.fromClient), chat.text.c_str(),
							            double(client.rttMs()));
							if (chat.fromClient == client.clientId()) {
								++received;
							}
						}
					}
					break;
				default:
					break;
			}
		}
		std::fflush(stdout);
		if (client.state() == ClientSession::State::Connected) {
			if (sent < count && now >= nextSend) {
				ChatMsg chat;
				chat.fromClient = client.clientId();
				chat.text = name + " #" + std::to_string(++sent);
				client.send(Channel::Rpc, makePacket(chat));
				nextSend = now + 1000;
			}
			if (received >= count) {
				break;
			}
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
	}
	client.disconnect();
	// Let ENet deliver the Disconnect.
	std::vector<TransportEvent> drain;
	for (int i = 0; i < 20; ++i) {
		transport->poll(drain);
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
	}
	return received >= count ? 0 : 4;
}

int main(int argc, char **argv)
{
	std::signal(SIGINT, onSignal);
	std::signal(SIGTERM, onSignal);
	const std::string mode = argc > 1 ? argv[1] : "";
	if (mode == "server") {
		return runServer(uint16_t(argc > 2 ? std::atoi(argv[2]) : 7777),
		                 uint16_t(argc > 3 ? std::atoi(argv[3]) : 7778));
	}
	if (mode == "client" && argc > 3) {
		return runClient(argv[2], uint16_t(std::atoi(argv[3])), argc > 4 ? argv[4] : "player",
		                 argc > 5 ? std::atoi(argv[5]) : 3);
	}
	std::fprintf(stderr,
	             "usage:\n"
	             "  net_echo server [udpPort=7777] [wsPort=7778, 0 = off]\n"
	             "  net_echo client <host> <port> [name] [messages]\n");
	return 1;
}
