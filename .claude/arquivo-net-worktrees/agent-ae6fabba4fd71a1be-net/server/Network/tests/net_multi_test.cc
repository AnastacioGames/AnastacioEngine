/* Multi-transport tests: events from a WebSocket server and a fake transport share one
 * PeerId space; sends are routed back to the right inner transport. */

#include "net_ws_test_client.h"

#include <gtest/gtest.h>

#include <algorithm>

using namespace net;
using nettest::Frame;
using nettest::TestClient;
using Type = TransportEvent::Type;

namespace {

/* Scripted unreliable transport (stands in for ENet). */
struct FakeState {
	std::vector<TransportEvent> pending;
	std::vector<std::pair<PeerId, std::vector<uint8_t>>> sent;
	std::vector<PeerId> disconnected;
	uint16_t listenPort = 0;
};

class FakeTransport : public ITransport {
public:
	explicit FakeTransport(FakeState &s) : m_s(s)
	{
	}
	bool listen(uint16_t port, int) override
	{
		m_s.listenPort = port;
		return true;
	}
	bool connect(const std::string &, uint16_t) override
	{
		return false;
	}
	void send(PeerId peer, Channel, const uint8_t *data, size_t size) override
	{
		m_s.sent.push_back({peer, std::vector<uint8_t>(data, data + size)});
	}
	void disconnect(PeerId peer) override
	{
		m_s.disconnected.push_back(peer);
		m_s.pending.push_back({Type::Disconnected, peer, Channel::Control, {}});
	}
	void poll(std::vector<TransportEvent> &events) override
	{
		for (auto &e : m_s.pending) {
			events.push_back(e);
		}
		m_s.pending.clear();
	}
	void shutdown() override
	{
	}
	bool reliableAll() const override
	{
		return false;
	}

private:
	FakeState &m_s;
};

} // namespace

TEST(NetMulti, CrossPlayEventsAndRouting)
{
	FakeState fake;
	auto wsOwned = createWebSocketServerTransport();
	WebSocketServerTransport *ws = wsOwned.get();
	auto multi = createMultiTransport();
	multi->add(std::make_unique<FakeTransport>(fake), 0);
	multi->add(std::move(wsOwned), 0); /* Ephemeral port for the test. */
	ASSERT_TRUE(multi->listen(7777, 8));
	EXPECT_EQ(fake.listenPort, 7777);
	EXPECT_FALSE(multi->reliableAll());

	std::vector<TransportEvent> events;

	/* Native peer 5 connects and sends. */
	fake.pending.push_back({Type::Connected, 5, Channel::Control, {}});
	fake.pending.push_back({Type::Received, 5, Channel::Input, {1, 2, 3}});

	/* Browser peer connects through WebSocket and sends. */
	TestClient cl(*multi, events);
	ASSERT_TRUE(cl.connectTo(ws->boundPort()));
	ASSERT_NE(cl.handshake().find(" 101 "), std::string::npos);
	ASSERT_TRUE(cl.sendFrame(0x2, {1, 'w', 's'}));
	ASSERT_TRUE(nettest::pumpUntil(
	    *multi, events, [&] { return nettest::countEvents(events, Type::Received) >= 2; }));
	ASSERT_EQ(nettest::countEvents(events, Type::Connected), 2);

	PeerId native = 0, browser = 0;
	for (const auto &e : events) {
		if (e.type == Type::Received && e.channel == Channel::Input) {
			native = e.peer;
			EXPECT_EQ(e.data, std::vector<uint8_t>({1, 2, 3}));
		}
		else if (e.type == Type::Received && e.channel == Channel::Rpc) {
			browser = e.peer;
			EXPECT_EQ(e.data, std::vector<uint8_t>({'w', 's'}));
		}
	}
	ASSERT_NE(native, 0u);
	ASSERT_NE(browser, 0u);
	EXPECT_NE(native, browser);
	EXPECT_FALSE(multi->reliableFor(native));
	EXPECT_TRUE(multi->reliableFor(browser));

	/* Routing back. */
	const uint8_t msg[2] = {9, 8};
	multi->send(native, Channel::Snapshot, msg, 2);
	ASSERT_EQ(fake.sent.size(), 1u);
	EXPECT_EQ(fake.sent[0].first, 5u);
	multi->send(browser, Channel::Snapshot, msg, 2);
	Frame f;
	ASSERT_TRUE(cl.readFrameOf(0x2, f));
	EXPECT_EQ(f.payload, std::vector<uint8_t>({2, 9, 8}));

	/* Disconnects come back with the outer ids, once each. */
	events.clear();
	multi->disconnect(native);
	EXPECT_EQ(fake.disconnected, std::vector<PeerId>({5}));
	cl.closeSocket();
	ASSERT_TRUE(nettest::pumpUntil(
	    *multi, events, [&] { return nettest::countEvents(events, Type::Disconnected) >= 2; }));
	std::vector<PeerId> gone;
	for (const auto &e : events) {
		if (e.type == Type::Disconnected) {
			gone.push_back(e.peer);
		}
	}
	EXPECT_EQ(gone.size(), 2u);
	EXPECT_NE(std::find(gone.begin(), gone.end(), native), gone.end());
	EXPECT_NE(std::find(gone.begin(), gone.end(), browser), gone.end());
	EXPECT_FALSE(multi->reliableFor(native));
}

TEST(NetMulti, MaxPeersAcrossTransports)
{
	FakeState a, b;
	auto multi = createMultiTransport();
	multi->add(std::make_unique<FakeTransport>(a), 1000);
	multi->add(std::make_unique<FakeTransport>(b), 2000);
	ASSERT_TRUE(multi->listen(0, 2));
	EXPECT_EQ(a.listenPort, 1000);
	EXPECT_EQ(b.listenPort, 2000);

	/* Same inner id on both transports must map to different outer ids. */
	a.pending.push_back({Type::Connected, 1, Channel::Control, {}});
	b.pending.push_back({Type::Connected, 1, Channel::Control, {}});
	b.pending.push_back({Type::Connected, 2, Channel::Control, {}});
	std::vector<TransportEvent> events;
	multi->poll(events);
	ASSERT_EQ(events.size(), 2u);
	EXPECT_NE(events[0].peer, events[1].peer);
	EXPECT_EQ(b.disconnected, std::vector<PeerId>({2}));

	/* The refused peer's Disconnected and stray data stay hidden. */
	events.clear();
	b.pending.push_back({Type::Received, 2, Channel::Rpc, {1}});
	multi->poll(events);
	EXPECT_TRUE(events.empty());
}

TEST(NetMulti, NoTransportsFails)
{
	auto multi = createMultiTransport();
	EXPECT_FALSE(multi->listen(1, 1));
	EXPECT_FALSE(multi->reliableAll());
	EXPECT_FALSE(multi->connect("x", 1));
}
