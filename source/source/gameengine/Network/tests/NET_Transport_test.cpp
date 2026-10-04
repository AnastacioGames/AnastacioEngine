/* Loopback, simulated and ENet transports. */

#include "NET_ITransport.h"

#include "gtest/gtest.h"

#include <chrono>
#include <thread>

using namespace net;

static std::vector<uint8_t> bytes(std::initializer_list<uint8_t> list)
{
	return std::vector<uint8_t>(list);
}

static std::vector<TransportEvent> pollAll(ITransport &t)
{
	std::vector<TransportEvent> events;
	t.poll(events);
	return events;
}

TEST(NetTransportLoopback, ConnectSendDisconnect)
{
	std::unique_ptr<ITransport> client;
	std::unique_ptr<ITransport> server = createLoopbackPair(client);
	EXPECT_FALSE(server->reliableAll());
	ASSERT_TRUE(server->listen(1, 4));
	EXPECT_FALSE(server->connect("x", 1));
	ASSERT_TRUE(client->connect("ignored", 0));

	std::vector<TransportEvent> se = pollAll(*server);
	std::vector<TransportEvent> ce = pollAll(*client);
	ASSERT_EQ(se.size(), 1u);
	ASSERT_EQ(ce.size(), 1u);
	EXPECT_EQ(se[0].type, TransportEvent::Type::Connected);
	const PeerId clientPeer = se[0].peer;
	const PeerId serverPeer = ce[0].peer;

	for (uint8_t i = 0; i < 10; ++i) {
		const std::vector<uint8_t> d = bytes({i, uint8_t(i * 2)});
		client->send(serverPeer, Channel(i % 4), d.data(), d.size());
	}
	se = pollAll(*server);
	ASSERT_EQ(se.size(), 10u);
	for (uint8_t i = 0; i < 10; ++i) {
		EXPECT_EQ(se[i].type, TransportEvent::Type::Received);
		EXPECT_EQ(se[i].peer, clientPeer);
		EXPECT_EQ(se[i].channel, Channel(i % 4));
		EXPECT_EQ(se[i].data, bytes({i, uint8_t(i * 2)}));
	}

	server->disconnect(clientPeer);
	se = pollAll(*server);
	ce = pollAll(*client);
	ASSERT_EQ(ce.size(), 1u);
	EXPECT_EQ(ce[0].type, TransportEvent::Type::Disconnected);
	ASSERT_EQ(se.size(), 1u);
	EXPECT_EQ(se[0].type, TransportEvent::Type::Disconnected);
	// Sending to a gone peer is ignored.
	client->send(serverPeer, Channel::Control, nullptr, 0);
	EXPECT_TRUE(pollAll(*server).empty());
}

TEST(NetTransportLoopback, HubManyClientsAndFull)
{
	std::shared_ptr<LoopbackHub> hub = createLoopbackHub();
	std::unique_ptr<ITransport> server = createLoopbackTransport(hub);
	ASSERT_TRUE(server->listen(7777, 2));
	EXPECT_EQ(server->localPort(), 7777);
	std::unique_ptr<ITransport> a = createLoopbackTransport(hub);
	std::unique_ptr<ITransport> b = createLoopbackTransport(hub);
	std::unique_ptr<ITransport> c = createLoopbackTransport(hub);
	EXPECT_FALSE(a->connect("", 1234));
	ASSERT_TRUE(a->connect("", 7777));
	ASSERT_TRUE(b->connect("", 7777));
	ASSERT_TRUE(c->connect("", 7777));
	EXPECT_EQ(pollAll(*server).size(), 2u);
	const std::vector<TransportEvent> ce = pollAll(*c);
	ASSERT_EQ(ce.size(), 1u);
	EXPECT_EQ(ce[0].type, TransportEvent::Type::Disconnected);

	// Destroying an endpoint disconnects its peers.
	a.reset();
	const std::vector<TransportEvent> se = pollAll(*server);
	ASSERT_EQ(se.size(), 1u);
	EXPECT_EQ(se[0].type, TransportEvent::Type::Disconnected);
}

struct SimFixture {
	uint64_t now = 0;
	std::unique_ptr<ITransport> server;
	std::unique_ptr<ITransport> client;
	PeerId toServer = 0;

	explicit SimFixture(NetSimSettings settings)
	{
		settings.clock = [this]() { return now; };
		std::unique_ptr<ITransport> rawClient;
		std::unique_ptr<ITransport> rawServer = createLoopbackPair(rawClient);
		server = createSimulatedTransport(std::move(rawServer), settings);
		client = std::move(rawClient);
		server->listen(1, 4);
		client->connect("", 1);
		std::vector<TransportEvent> ev;
		client->poll(ev);
		toServer = ev.at(0).peer;
		// Connected event is delayed by the latency too.
		ev.clear();
		server->poll(ev);
		now += 10000;
		server->poll(ev);
	}

	/// Sends n packets on channel, then advances the clock and collects payload indices.
	std::vector<int> run(int n, Channel channel)
	{
		for (int i = 0; i < n; ++i) {
			const uint8_t d[2] = {uint8_t(i & 0xFF), uint8_t(i >> 8)};
			client->send(toServer, channel, d, 2);
		}
		std::vector<int> got;
		std::vector<TransportEvent> ev;
		server->poll(ev);  // schedules
		for (int step = 0; step < 100; ++step) {
			now += 10;
			server->poll(ev);
		}
		for (const TransportEvent &e : ev) {
			if (e.type == TransportEvent::Type::Received) {
				got.push_back(e.data[0] | (e.data[1] << 8));
			}
		}
		return got;
	}
};

TEST(NetTransportSimulated, LatencyDelaysDelivery)
{
	NetSimSettings settings;
	settings.latencyMs = 100;
	SimFixture f(settings);
	const uint8_t d[1] = {7};
	f.client->send(f.toServer, Channel::Control, d, 1);
	std::vector<TransportEvent> ev;
	f.server->poll(ev);
	EXPECT_TRUE(ev.empty());
	f.now += 99;
	f.server->poll(ev);
	EXPECT_TRUE(ev.empty());
	f.now += 1;
	f.server->poll(ev);
	ASSERT_EQ(ev.size(), 1u);
	EXPECT_EQ(ev[0].data[0], 7);
}

TEST(NetTransportSimulated, LossOnlyOnUnreliable)
{
	NetSimSettings settings;
	settings.lossPercent = 30.0f;
	settings.seed = 1234;
	SimFixture f(settings);
	const std::vector<int> unreliable = f.run(2000, Channel::Snapshot);
	EXPECT_GT(unreliable.size(), 1300u);
	EXPECT_LT(unreliable.size(), 1500u);
	const std::vector<int> reliable = f.run(500, Channel::Control);
	ASSERT_EQ(reliable.size(), 500u);
	for (int i = 0; i < 500; ++i) {
		EXPECT_EQ(reliable[i], i);
	}
}

TEST(NetTransportSimulated, SameSeedSameResult)
{
	NetSimSettings settings;
	settings.lossPercent = 20.0f;
	settings.duplicatePercent = 10.0f;
	settings.latencyMs = 30;
	settings.jitterMs = 40;
	settings.seed = 42;
	SimFixture a(settings);
	SimFixture b(settings);
	const std::vector<int> ra = a.run(500, Channel::Input);
	const std::vector<int> rb = b.run(500, Channel::Input);
	EXPECT_EQ(ra, rb);
	settings.seed = 43;
	SimFixture c(settings);
	EXPECT_NE(c.run(500, Channel::Input), ra);
}

TEST(NetTransportSimulated, JitterKeepsReliableOrderAndDuplicates)
{
	NetSimSettings settings;
	settings.latencyMs = 20;
	settings.jitterMs = 200;
	settings.duplicatePercent = 50.0f;
	settings.seed = 9;
	SimFixture f(settings);
	const std::vector<int> reliable = f.run(300, Channel::Rpc);
	ASSERT_EQ(reliable.size(), 300u);
	for (int i = 0; i < 300; ++i) {
		EXPECT_EQ(reliable[i], i);
	}
	const std::vector<int> unreliable = f.run(1000, Channel::Snapshot);
	EXPECT_GT(unreliable.size(), 1400u);
	bool reordered = false;
	for (size_t i = 1; i < unreliable.size(); ++i) {
		reordered = reordered || unreliable[i] < unreliable[i - 1];
	}
	EXPECT_TRUE(reordered);
}

static bool pumpUntil(ITransport &a, ITransport &b, std::vector<TransportEvent> &ea, std::vector<TransportEvent> &eb,
                      const std::function<bool()> &done)
{
	for (int i = 0; i < 400; ++i) {
		a.poll(ea);
		b.poll(eb);
		if (done()) {
			return true;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
	}
	return false;
}

TEST(NetTransportENet, LocalhostEphemeralPort)
{
	std::unique_ptr<ITransport> server = createENetTransport();
	std::unique_ptr<ITransport> client = createENetTransport();
	EXPECT_FALSE(server->reliableAll());
	ASSERT_TRUE(server->listen(0, 4));
	const uint16_t port = server->localPort();
	ASSERT_NE(port, 0);
	ASSERT_TRUE(client->connect("127.0.0.1", port));

	std::vector<TransportEvent> se, ce;
	auto has = [](const std::vector<TransportEvent> &v, TransportEvent::Type t) {
		for (const TransportEvent &e : v) {
			if (e.type == t) {
				return true;
			}
		}
		return false;
	};
	ASSERT_TRUE(pumpUntil(*server, *client, se, ce, [&]() {
		return has(se, TransportEvent::Type::Connected) && has(ce, TransportEvent::Type::Connected);
	}));
	const PeerId toServer = ce[0].peer;
	const PeerId toClient = se[0].peer;
	se.clear();
	ce.clear();

	const std::vector<uint8_t> big(5000, 0x5A);
	client->send(toServer, Channel::Control, big.data(), big.size());
	const uint8_t small[3] = {1, 2, 3};
	client->send(toServer, Channel::Snapshot, small, sizeof(small));
	server->send(toClient, Channel::Rpc, small, sizeof(small));
	// Unreliable above 1200 bytes is dropped by the transport.
	server->send(toClient, Channel::Input, big.data(), 1201);

	ASSERT_TRUE(pumpUntil(*server, *client, se, ce, [&]() { return se.size() >= 2 && ce.size() >= 1; }));
	bool gotBig = false, gotSmall = false;
	for (const TransportEvent &e : se) {
		gotBig = gotBig || (e.channel == Channel::Control && e.data == big);
		gotSmall = gotSmall || (e.channel == Channel::Snapshot && e.data.size() == 3);
	}
	EXPECT_TRUE(gotBig);
	EXPECT_TRUE(gotSmall);
	ASSERT_EQ(ce.size(), 1u);
	EXPECT_EQ(ce[0].channel, Channel::Rpc);

	se.clear();
	ce.clear();
	client->disconnect(toServer);
	ASSERT_TRUE(pumpUntil(*server, *client, se, ce, [&]() { return has(se, TransportEvent::Type::Disconnected); }));
	ASSERT_EQ(ce.size(), 1u);
	EXPECT_EQ(ce[0].type, TransportEvent::Type::Disconnected);
	server->shutdown();
	client->shutdown();
}
