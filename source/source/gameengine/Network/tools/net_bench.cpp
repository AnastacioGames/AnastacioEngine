/* Replication benchmark: 16 clients, 300 dynamic objects, 30 Hz, simulated network with
 * 150 ms latency and 2% loss. Prints server CPU per tick and KB/s per client against the
 * targets of docs/multiplayer-plan.md, section 4.
 *
 * Usage: net_bench [seconds=10] [clients=16] [objects=300] [radius=0]
 */

#include "NET_ReplicaClient.h"
#include "NET_Replicator.h"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <memory>

using namespace net;

namespace {

const uint64_t kScene = 0xBE7C4;

/// Minimal world: transforms only.
class BenchWorld : public IWorld {
public:
	bool getTransform(NetId id, float position[3], float rotation[4]) const override
	{
		const auto it = objects.find(id);
		if (it == objects.end()) {
			return false;
		}
		std::copy(it->second.position, it->second.position + 3, position);
		std::copy(it->second.rotation, it->second.rotation + 4, rotation);
		return true;
	}
	bool getVelocity(NetId, float linear[3], float angular[3]) const override
	{
		for (int i = 0; i < 3; ++i) {
			linear[i] = angular[i] = 0.0f;
		}
		return true;
	}
	bool getProperties(NetId, std::vector<PropValue> &props) const override
	{
		props.clear();
		return true;
	}
	bool isSleeping(NetId) const override
	{
		return false;
	}
	void setTransform(NetId id, const float position[3], const float rotation[4]) override
	{
		ObjectState &s = objects[id];
		std::copy(position, position + 3, s.position);
		std::copy(rotation, rotation + 4, s.rotation);
	}
	void setVelocity(NetId, const float *, const float *) override
	{
	}
	void setProperties(NetId, const std::vector<PropValue> &) override
	{
	}
	bool spawn(NetId id, const std::string &, ClientId, const ObjectState &state) override
	{
		objects[id] = state;
		return true;
	}
	void despawn(NetId id) override
	{
		objects.erase(id);
	}
	void setOwner(NetId, ClientId) override
	{
	}
	bool exists(NetId id) const override
	{
		return objects.count(id) != 0;
	}

	std::map<NetId, ObjectState> objects;
};

struct BenchClient {
	std::unique_ptr<ITransport> transport;
	std::unique_ptr<ClientSession> session;
	BenchWorld world;
	std::unique_ptr<ReplicaClient> replica;
	std::vector<SessionEvent> events;
};

}  // namespace

int main(int argc, char **argv)
{
	const int seconds = argc > 1 ? std::atoi(argv[1]) : 10;
	const int clientCount = argc > 2 ? std::atoi(argv[2]) : 16;
	const int objectCount = argc > 3 ? std::atoi(argv[3]) : 300;
	const float radius = argc > 4 ? float(std::atof(argv[4])) : 0.0f;
	const uint32_t tickRate = 30;
	const uint64_t tickMs = 1000 / tickRate;

	uint64_t now = 1000;
	NetSimSettings sim;
	// 150 ms round trip: 75 ms on each side.
	sim.latencyMs = 75;
	sim.lossPercent = 2.0f;
	sim.clock = [&now] { return now; };
	uint64_t seed = 1;
	auto hub = createLoopbackHub();
	const auto wrap = [&] {
		NetSimSettings s = sim;
		s.seed = seed++;
		return createSimulatedTransport(createLoopbackTransport(hub), s);
	};

	auto serverTransport = wrap();
	ServerConfig sc;
	sc.gameId = "bench";
	sc.sceneName = "Bench";
	sc.sceneHash = kScene;
	sc.tickRate = uint16_t(tickRate);
	sc.snapshotRate = uint16_t(tickRate);
	sc.maxClients = clientCount;
	ServerSession server(*serverTransport, sc);
	if (!server.start(7777)) {
		std::fprintf(stderr, "listen failed\n");
		return 1;
	}
	BenchWorld world;
	ReplicatorConfig rc;
	rc.snapshotIntervalTicks = 1;
	Replicator replicator(server, world, rc);

	// Objects move in circles over a 200 m area.
	for (int i = 0; i < objectCount; ++i) {
		const NetId id = NetId(i + 1);
		ObjectState &s = world.objects[id];
		s.id = id;
		s.hasTransform = true;
		replicator.addSceneObject(id, ReplicatedObjectDesc());
	}

	std::vector<std::unique_ptr<BenchClient>> clients;
	for (int i = 0; i < clientCount; ++i) {
		auto c = std::make_unique<BenchClient>();
		c->transport = wrap();
		ClientConfig cc;
		cc.gameId = "bench";
		cc.playerName = "p" + std::to_string(i);
		cc.sceneHash = kScene;
		c->session = std::make_unique<ClientSession>(*c->transport, cc);
		c->world.objects = world.objects;
		c->replica = std::make_unique<ReplicaClient>(*c->session, c->world);
		c->session->connect("loopback", 7777, now);
		clients.push_back(std::move(c));
	}

	std::vector<SessionEvent> serverEvents;
	const auto clientUpdate = [&] {
		for (auto &c : clients) {
			c->events.clear();
			c->session->update(now, c->events);
			for (const SessionEvent &e : c->events) {
				c->replica->handleEvent(e, now);
				if (e.type == SessionEvent::Type::SceneChange) {
					c->session->sceneLoaded(e.sceneHash);
				}
			}
			c->replica->applyLatest();
		}
	};

	const int warmupTicks = int(tickRate) * 2;
	const int totalTicks = warmupTicks + seconds * int(tickRate);
	double cpuMs = 0.0;
	double worstMs = 0.0;
	std::vector<uint64_t> startBytes(size_t(clientCount) + 1, 0);
	for (Tick tick = 1; int(tick) <= totalTicks; ++tick) {
		now += tickMs;
		for (auto &pair : world.objects) {
			ObjectState &s = pair.second;
			const float t = float(tick) / float(tickRate) * 0.5f + float(pair.first);
			s.position[0] = 100.0f * std::cos(float(pair.first) * 0.7f) + 5.0f * std::cos(t);
			s.position[1] = 100.0f * std::sin(float(pair.first) * 1.3f) + 5.0f * std::sin(t);
			s.position[2] = 1.0f;
			s.rotation[2] = std::sin(t / 2.0f);
			s.rotation[3] = std::cos(t / 2.0f);
		}
		clientUpdate();

		const auto t0 = std::chrono::steady_clock::now();
		serverEvents.clear();
		server.update(now, tick, serverEvents);
		for (const SessionEvent &e : serverEvents) {
			replicator.handleEvent(e);
		}
		if (radius > 0.0f) {
			for (ClientId id : server.clients()) {
				const ObjectState &s = world.objects[NetId(id)];
				replicator.setClientView(id, s.position, radius);
			}
		}
		replicator.update(tick, now);
		const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();

		if (int(tick) == warmupTicks) {
			for (ClientId id : server.clients()) {
				const ReplicationStats *st = replicator.stats(id);
				if (st && id < startBytes.size()) {
					startBytes[id] = st->snapshotBytes + st->reliableBytes;
				}
			}
		}
		else if (int(tick) > warmupTicks) {
			cpuMs += ms;
			worstMs = std::max(worstMs, ms);
		}
	}

	const int measured = totalTicks - warmupTicks;
	double totalKbps = 0.0, maxKbps = 0.0;
	int counted = 0;
	uint32_t accepted = 0;
	for (ClientId id : server.clients()) {
		const ReplicationStats *st = replicator.stats(id);
		if (!st || id >= startBytes.size()) {
			continue;
		}
		const double kbps = double(st->snapshotBytes + st->reliableBytes - startBytes[id]) / 1024.0 / double(seconds);
		totalKbps += kbps;
		maxKbps = std::max(maxKbps, kbps);
		++counted;
	}
	for (auto &c : clients) {
		accepted += c->replica->stats().snapshotsAccepted;
	}
	const double avgMs = cpuMs / double(measured);
	const double avgKbps = counted ? totalKbps / counted : 0.0;

	std::printf("net_bench: %d clients, %d objects, %u Hz, 150 ms RTT, 2%% loss, %d s, radius %.0f\n",
	            clientCount, objectCount, tickRate, seconds, double(radius));
	std::printf("  connected clients      %d\n", counted);
	std::printf("  server CPU per tick    avg %.3f ms, worst %.3f ms (target < 1 ms)\n", avgMs, worstMs);
	std::printf("  bandwidth per client   avg %.1f KB/s, max %.1f KB/s (target < 40 KB/s)\n", avgKbps, maxKbps);
	std::printf("  snapshots accepted     %u (all clients)\n", accepted);
	std::printf("  result                 CPU %s, bandwidth %s\n", avgMs < 1.0 ? "OK" : "ABOVE TARGET",
	            maxKbps < 40.0 ? "OK" : "ABOVE TARGET");
	return 0;
}
