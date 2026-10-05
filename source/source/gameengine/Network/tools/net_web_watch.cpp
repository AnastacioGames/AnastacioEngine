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

/** \file gameengine/Network/tools/net_web_watch.cpp
 *  \ingroup network
 *  \brief Wasm client that joins a RangeRuntime server over WebSocket and watches the replication (Emscripten only).
 *
 *   net_web_watch.html?host=127.0.0.1&port=7778&game=anastacio-game&version=1&hash=<hex>  (node: same keys as args)
 *
 * The scene hash is the one the server prints in "network: hosting ... scene hash <hex>". Joins with Hello, answers
 * SceneLoaded and counts Spawn and Snapshot messages. Passes after at least one Spawn and kSnapshots snapshots that
 * are not all the same bytes (the server moves something). Prints "NETWEB PASS"/"NETWEB FAIL" and, in a browser,
 * puts the same text in document.title so a headless browser can read it.
 */

#include "NET_Session.h"
#include "NET_TransportWeb.h"

#include <emscripten.h>

#include <cstdio>
#include <cstdlib>
#include <memory>
#include <set>
#include <string>
#include <vector>

using namespace net;

namespace {

const int kSnapshots = 40;
const uint64_t kTimeoutMs = 20000;

struct App {
	std::unique_ptr<ITransport> transport;
	std::unique_ptr<ClientSession> client;
	uint64_t sceneHash = 0;
	uint64_t startMs = 0;
	int spawns = 0;
	int snapshots = 0;
	std::set<std::vector<uint8_t>> distinct;
	bool done = false;
};

void report(const char *text)
{
	std::printf("%s\n", text);
	std::fflush(stdout);
	EM_ASM({ if (typeof document !== 'undefined') { document.title = UTF8ToString($0); } }, text);
}

void finish(App &app, bool ok)
{
	char line[160];
	std::snprintf(line, sizeof(line), "NETWEB %s spawns=%d snapshots=%d distinct=%d", ok ? "PASS" : "FAIL",
	              app.spawns, app.snapshots, int(app.distinct.size()));
	report(line);
	app.done = true;
	if (app.client) {
		app.client->disconnect();
	}
	emscripten_cancel_main_loop();
	// node exits with the code; a browser page just stays with the result in its title.
	EM_ASM({ if (typeof document === 'undefined') { process.exitCode = $0; } }, ok ? 0 : 1);
}

void frame(void *arg)
{
	App &app = *static_cast<App *>(arg);
	if (app.done) {
		return;
	}
	const uint64_t now = steadyClockMs();
	std::vector<SessionEvent> events;
	app.client->update(now, events);
	for (const SessionEvent &ev : events) {
		switch (ev.type) {
			case SessionEvent::Type::Connected:
				std::printf("connected as client %u\n", unsigned(ev.client));
				break;
			case SessionEvent::Type::SceneChange:
				std::printf("scene '%s'\n", ev.text.c_str());
				app.client->sceneLoaded(app.sceneHash);
				break;
			case SessionEvent::Type::Rejected:
				std::printf("rejected, reason %u\n", unsigned(ev.rejectReason));
				finish(app, false);
				return;
			case SessionEvent::Type::Disconnected:
				std::printf("disconnected, reason %u\n", unsigned(ev.disconnectReason));
				finish(app, false);
				return;
			case SessionEvent::Type::Message:
				if (ev.messageType == uint8_t(MessageType::Spawn)) {
					++app.spawns;
				}
				else if (ev.messageType == uint8_t(MessageType::Snapshot)) {
					++app.snapshots;
					if (app.distinct.size() < 8) {
						app.distinct.insert(ev.body);
					}
				}
				break;
			default:
				break;
		}
	}
	std::fflush(stdout);
	if (app.spawns > 0 && app.snapshots >= kSnapshots && app.distinct.size() > 1) {
		finish(app, true);
	}
	else if (now - app.startMs > kTimeoutMs) {
		finish(app, false);
	}
}

/// "key=value" from argv (node) or from the page's query string (browser).
std::string option(int argc, char **argv, const char *key, const char *fallback)
{
	const std::string prefix = std::string(key) + "=";
	for (int i = 1; i < argc; ++i) {
		if (std::string(argv[i]).rfind(prefix, 0) == 0) {
			return argv[i] + prefix.size();
		}
	}
	char *value = (char *)EM_ASM_PTR({
		if (typeof location === 'undefined') { return 0; }
		const v = new URLSearchParams(location.search).get(UTF8ToString($0));
		return v === null ? 0 : stringToNewUTF8(v);
	}, key);
	if (value) {
		std::string out = value;
		std::free(value);
		return out;
	}
	return fallback;
}

}  // namespace

int main(int argc, char **argv)
{
	static App app;
	const std::string host = option(argc, argv, "host", "127.0.0.1");
	const uint16_t port = uint16_t(std::atoi(option(argc, argv, "port", "7778").c_str()));
	app.sceneHash = std::strtoull(option(argc, argv, "hash", "0").c_str(), nullptr, 16);
	app.transport = createWebClientTransport();
	if (!app.transport) {
		report("NETWEB FAIL no WebSocket transport");
		return 1;
	}
	ClientConfig config;
	config.gameId = option(argc, argv, "game", "anastacio-game");
	config.gameVersion = uint32_t(std::atoi(option(argc, argv, "version", "1").c_str()));  // engine default: 1
	config.sceneHash = app.sceneHash;
	config.playerName = "browser";
	app.client = std::make_unique<ClientSession>(*app.transport, config);
	app.startMs = steadyClockMs();
	if (!app.client->connect(host, port, app.startMs)) {
		report("NETWEB FAIL cannot connect");
		return 1;
	}
	std::printf("net_web_watch: connecting to ws://%s:%u/ with scene hash %llx\n", host.c_str(), unsigned(port),
	            (unsigned long long)app.sceneHash);
	emscripten_set_main_loop_arg(frame, &app, 60, 1);
	return 0;
}
