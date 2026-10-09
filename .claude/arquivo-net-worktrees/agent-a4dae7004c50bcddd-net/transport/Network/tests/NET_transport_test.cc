/* Loopback and simulated transport tests (protocol section 10). */

#include "NET_ITransport.h"
#include "NET_TransportLoopback.h"

#include "gtest/gtest.h"

using namespace net;

namespace {

std::vector<uint8_t> bytes(uint32_t v)
{
	return {uint8_t(v), uint8_t(v >> 8), uint8_t(v >> 16), uint8_t(v >> 24)};
}

uint32_t value(const std::vector<uint8_t> &b)
{
	return uint32_t(b[0]) | uint32_t(b[1]) << 8 | uint32_t(b[2]) << 16 | uint32_t(b[3]) << 24;
}

void sendValue(ITransport &t, PeerId peer, Channel ch, uint32_t v)
{
	std::vector<uint8_t> b = bytes(v);
	t.send(peer, ch, b.data(), b.size());
}

/* Connects client to server and returns the peer id each side sees. */
void connectPair(ITransport &server, ITransport &client, PeerId &serverSide, PeerId &clientSide)
{
	ASSERT_TRUE(server.listen(7777, 4));
	ASSERT_TRUE(client.connect("loopback", 7777));
	std::vector<TransportEvent> ev;
	server.poll(ev);
	ASSERT_EQ(ev.size(), 1u);
	ASSERT_EQ(ev[0].type, TransportEvent::Type::Connected);
	serverSide = ev[0].peer;
	ev.clear();
	client.poll(ev);
	ASSERT_EQ(ev.size(), 1u);
	ASSERT_EQ(ev[0].type, TransportEvent::Type::Connected);
	clientSide = ev[0].peer;
}

}  // namespace

TEST(NetLoopback, DeliversInOrderOnEachChannel)
{
	std::unique_ptr<ITransport> client;
	std::unique_ptr<ITransport> server = createLoopbackPair(client);
	PeerId sp = 0, cp = 0;
	connectPair(*server, *client, sp, cp);
	EXPECT_TRUE(server->reliableAll());

	for (uint32_t i = 0; i < 100; i++) {
		sendValue(*client, cp, Channel(i % kChannelCount), i);
	}
	std::vector<TransportEvent> ev;
	server->poll(ev);
	ASSERT_EQ(ev.size(), 100u);
	for (uint32_t i = 0; i < 100; i++) {
		EXPECT_EQ(ev[i].type, TransportEvent::Type::Received);
		EXPECT_EQ(ev[i].peer, sp);
		EXPECT_EQ(ev[i].channel, Channel(i % kChannelCount));
		EXPECT_EQ(value(ev[i].data), i);
	}
}

TEST(NetLoopback, DisconnectNotifiesBothSides)
{
	std::unique_ptr<ITransport> client;
	std::unique_ptr<ITransport> server = createLoopbackPair(client);
	PeerId sp = 0, cp = 0;
	connectPair(*server, *client, sp, cp);
	sendValue(*client, cp, Channel::Control, 42);
	client->disconnect(cp);
	std::vector<TransportEvent> ev;
	server->poll(ev);
	ASSERT_EQ(ev.size(), 2u);
	EXPECT_EQ(ev[0].type, TransportEvent::Type::Received); /* data sent before the close arrives first */
	EXPECT_EQ(ev[1].type, TransportEvent::Type::Disconnected);
	ev.clear();
	client->poll(ev);
	ASSERT_EQ(ev.size(), 1u);
	EXPECT_EQ(ev[0].type, TransportEvent::Type::Disconnected);
	/* Sending to a closed peer is a no-op. */
	sendValue(*client, cp, Channel::Control, 1);
	ev.clear();
	server->poll(ev);
	EXPECT_TRUE(ev.empty());
}

TEST(NetLoopback, HubRefusesOverMaxPeers)
{
	LoopbackHub hub;
	auto server = hub.createEndpoint();
	ASSERT_TRUE(server->listen(1, 2));
	std::vector<std::unique_ptr<ITransport>> clients;
	for (int i = 0; i < 3; i++) {
		clients.push_back(hub.createEndpoint());
		ASSERT_TRUE(clients.back()->connect("x", 1));
	}
	std::vector<TransportEvent> ev;
	clients[2]->poll(ev);
	ASSERT_EQ(ev.size(), 1u);
	EXPECT_EQ(ev[0].type, TransportEvent::Type::Disconnected);
	ev.clear();
	server->poll(ev);
	EXPECT_EQ(ev.size(), 2u);
	EXPECT_FALSE(hub.createEndpoint()->connect("x", 2)); /* nobody listening */
}

namespace {

struct SimFixture {
	uint32_t now = 1000;
	std::unique_ptr<ITransport> server;
	std::unique_ptr<ITransport> client; /* simulated, wraps a loopback endpoint */
	PeerId sp = 0, cp = 0;

	explicit SimFixture(NetSimSettings s)
	{
		s.clockMs = [this]() { return now; };
		std::unique_ptr<ITransport> inner;
		server = createLoopbackPair(inner);
		client = createSimulatedTransport(std::move(inner), s);
		connectPair(*server, *client, sp, cp);
	}

	std::vector<TransportEvent> advance(uint32_t ms)
	{
		now += ms;
		std::vector<TransportEvent> ignored, ev;
		client->poll(ignored); /* flushes due packets */
		server->poll(ev);
		return ev;
	}
};

}  // namespace

TEST(NetSimulated, LatencyDelaysDelivery)
{
	NetSimSettings s;
	s.latencyMs = 50;
	SimFixture f(s);
	EXPECT_FALSE(f.client->reliableAll());
	sendValue(*f.client, f.cp, Channel::Control, 7);
	EXPECT_TRUE(f.advance(49).empty());
	auto ev = f.advance(1);
	ASSERT_EQ(ev.size(), 1u);
	EXPECT_EQ(value(ev[0].data), 7u);
}

TEST(NetSimulated, ReliableChannelsLoseNothingAndKeepOrder)
{
	NetSimSettings s;
	s.latencyMs = 30;
	s.jitterMs = 40;
	s.lossPercent = 50.0f;
	s.duplicatePercent = 50.0f;
	s.seed = 1234;
	SimFixture f(s);
	for (uint32_t i = 0; i < 500; i++) {
		sendValue(*f.client, f.cp, Channel::Rpc, i);
		f.now += 1;
	}
	auto ev = f.advance(200);
	ASSERT_EQ(ev.size(), 500u);
	for (uint32_t i = 0; i < 500; i++) {
		EXPECT_EQ(value(ev[i].data), i);
	}
}

namespace {

std::vector<uint32_t> runUnreliable(uint32_t seed, float loss, float dup, uint32_t jitter = 20)
{
	NetSimSettings s;
	s.latencyMs = 10;
	s.jitterMs = jitter;
	s.lossPercent = loss;
	s.duplicatePercent = dup;
	s.seed = seed;
	SimFixture f(s);
	for (uint32_t i = 0; i < 1000; i++) {
		sendValue(*f.client, f.cp, Channel::Snapshot, i);
	}
	std::vector<uint32_t> out;
	for (const TransportEvent &e : f.advance(100)) {
		out.push_back(value(e.data));
	}
	return out;
}

}  // namespace

TEST(NetSimulated, LossIsRepeatableWithFixedSeed)
{
	const std::vector<uint32_t> a = runUnreliable(42, 20.0f, 0.0f);
	const std::vector<uint32_t> b = runUnreliable(42, 20.0f, 0.0f);
	const std::vector<uint32_t> c = runUnreliable(43, 20.0f, 0.0f);
	EXPECT_EQ(a, b);
	EXPECT_NE(a, c);
	/* ~20% loss over 1000 packets. */
	EXPECT_GT(a.size(), 720u);
	EXPECT_LT(a.size(), 880u);
}

TEST(NetSimulated, DuplicationAndJitterReorder)
{
	const std::vector<uint32_t> a = runUnreliable(7, 0.0f, 10.0f);
	EXPECT_GT(a.size(), 1050u);
	EXPECT_LT(a.size(), 1150u);
	bool reordered = false;
	for (size_t i = 1; i < a.size(); i++) {
		reordered |= a[i] < a[i - 1];
	}
	EXPECT_TRUE(reordered);
}

TEST(NetSimulated, NoSettingsIsTransparent)
{
	const std::vector<uint32_t> a = runUnreliable(1, 0.0f, 0.0f, 0);
	ASSERT_EQ(a.size(), 1000u);
	for (uint32_t i = 0; i < 1000; i++) {
		EXPECT_EQ(a[i], i);
	}
}
