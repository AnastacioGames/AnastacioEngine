/* Server/client sessions over loopback with a fake clock. */

#include "NET_Session.h"

#include "gtest/gtest.h"

#include <chrono>
#include <thread>

using namespace net;

namespace {

const uint64_t kScene = 0xABCDEF;

ServerConfig serverConfig(int maxClients = 4)
{
	ServerConfig c;
	c.gameId = "test";
	c.gameVersion = 2;
	c.sceneName = "Arena";
	c.sceneHash = kScene;
	c.maxClients = maxClients;
	return c;
}

ClientConfig clientConfig(const std::string &name, uint64_t token = 0)
{
	ClientConfig c;
	c.gameId = "test";
	c.gameVersion = 2;
	c.playerName = name;
	c.sceneHash = kScene;
	c.token = token;
	return c;
}

struct Peer {
	std::unique_ptr<ITransport> transport;
	std::unique_ptr<ClientSession> session;
	std::vector<SessionEvent> events;

	bool has(SessionEvent::Type type) const
	{
		for (const SessionEvent &e : events) {
			if (e.type == type) {
				return true;
			}
		}
		return false;
	}
	const SessionEvent *find(SessionEvent::Type type) const
	{
		for (const SessionEvent &e : events) {
			if (e.type == type) {
				return &e;
			}
		}
		return nullptr;
	}
};

struct World {
	uint64_t now = 1000;
	Tick tick = 1;
	std::shared_ptr<LoopbackHub> hub = createLoopbackHub();
	std::unique_ptr<ITransport> serverTransport = createLoopbackTransport(hub);
	std::unique_ptr<ServerSession> server;
	std::vector<SessionEvent> serverEvents;
	std::vector<std::unique_ptr<Peer>> clients;

	explicit World(const ServerConfig &config = serverConfig())
	{
		server = std::make_unique<ServerSession>(*serverTransport, config);
		EXPECT_TRUE(server->start(7777));
	}

	Peer &addClient(const ClientConfig &config)
	{
		auto p = std::make_unique<Peer>();
		p->transport = createLoopbackTransport(hub);
		p->session = std::make_unique<ClientSession>(*p->transport, config);
		EXPECT_TRUE(p->session->connect("loopback", 7777, now));
		clients.push_back(std::move(p));
		return *clients.back();
	}

	/// Advances time in 10 ms steps, updating everybody.
	void step(uint64_t ms = 10, bool updateClients = true)
	{
		for (uint64_t t = 0; t < ms; t += 10) {
			now += 10;
			for (auto &c : clients) {
				if (updateClients) {
					c->session->update(now, c->events);
				}
			}
			server->update(now, tick, serverEvents);
			for (auto &c : clients) {
				if (updateClients) {
					c->session->update(now, c->events);
				}
			}
			++tick;
		}
	}

	void removeClient(Peer &peer)
	{
		for (auto it = clients.begin(); it != clients.end(); ++it) {
			if (it->get() == &peer) {
				clients.erase(it);
				return;
			}
		}
	}

	size_t count(SessionEvent::Type type) const
	{
		size_t n = 0;
		for (const SessionEvent &e : serverEvents) {
			n += e.type == type ? 1 : 0;
		}
		return n;
	}
};

}  // namespace

TEST(NetSession, ServerAndTwoClients)
{
	World w;
	Peer &a = w.addClient(clientConfig("Ana"));
	Peer &b = w.addClient(clientConfig("Bruno"));
	w.step(50);

	ASSERT_EQ(a.session->state(), ClientSession::State::Connected);
	ASSERT_EQ(b.session->state(), ClientSession::State::Connected);
	EXPECT_EQ(a.session->clientId(), 1);
	EXPECT_EQ(b.session->clientId(), 2);
	EXPECT_EQ(a.session->tickRate(), 60);
	EXPECT_EQ(a.session->sceneName(), "Arena");
	EXPECT_EQ(w.count(SessionEvent::Type::ClientJoined), 2u);

	// Player lists on both sides.
	ASSERT_EQ(a.session->players().size(), 2u);
	ASSERT_EQ(b.session->players().size(), 2u);
	EXPECT_EQ(a.session->players().at(2).name, "Bruno");
	EXPECT_EQ(b.session->players().at(1).name, "Ana");

	// Scene handshake.
	const SessionEvent *scene = a.find(SessionEvent::Type::SceneChange);
	ASSERT_TRUE(scene != nullptr);
	EXPECT_EQ(scene->sceneHash, kScene);
	a.session->sceneLoaded(kScene);
	b.session->sceneLoaded(kScene + 1);  // stale scene: ignored
	w.step(20);
	EXPECT_EQ(w.count(SessionEvent::Type::ClientReady), 1u);
	EXPECT_TRUE(w.server->client(1)->ready);
	EXPECT_FALSE(w.server->client(2)->ready);

	// Game messages pass through as Message events.
	ChatMsg chat;
	chat.text = "oi";
	a.session->send(Channel::Rpc, makePacket(chat));
	w.step(10);
	bool gotChat = false;
	for (const SessionEvent &e : w.serverEvents) {
		gotChat = gotChat || (e.type == SessionEvent::Type::Message && e.client == 1 &&
		                      e.messageType == uint8_t(MessageType::Chat) && e.channel == Channel::Rpc);
	}
	EXPECT_TRUE(gotChat);
	w.server->broadcast(Channel::Rpc, makePacket(chat));
	w.step(10);
	EXPECT_TRUE(b.has(SessionEvent::Type::Message));

	// Server tick estimate follows the clock.
	const Tick est = a.session->estimatedServerTick(w.now);
	EXPECT_GT(est, 0u);

	// Quit.
	a.session->disconnect();
	w.step(20);
	EXPECT_EQ(w.server->clients().size(), 1u);
	const SessionEvent *left = nullptr;
	for (const SessionEvent &e : w.serverEvents) {
		if (e.type == SessionEvent::Type::ClientLeft) {
			left = &e;
		}
	}
	ASSERT_TRUE(left != nullptr);
	EXPECT_EQ(left->disconnectReason, DisconnectReason::Quit);
	EXPECT_EQ(b.session->players().size(), 1u);
}

TEST(NetSession, PingPongRtt)
{
	World w;
	Peer &a = w.addClient(clientConfig("Ana"));
	w.step(3000);
	// Loopback with 10 ms steps: about one step of round trip.
	EXPECT_GE(a.session->rttMs(), 0.0f);
	EXPECT_LT(a.session->rttMs(), 30.0f);
	ASSERT_TRUE(w.server->client(1) != nullptr);
	EXPECT_TRUE(w.server->client(1)->rtt.hasSample());
}

TEST(NetSession, RttEstimatorEma)
{
	RttEstimator rtt;
	EXPECT_FALSE(rtt.hasSample());
	rtt.addSample(100.0f);
	EXPECT_FLOAT_EQ(rtt.rttMs(), 100.0f);
	rtt.addSample(200.0f);
	EXPECT_FLOAT_EQ(rtt.rttMs(), 110.0f);
}

TEST(NetSession, RejectVersion)
{
	World w;
	ClientConfig c = clientConfig("Old");
	c.gameVersion = 1;
	Peer &a = w.addClient(c);
	w.step(30);
	const SessionEvent *ev = a.find(SessionEvent::Type::Rejected);
	ASSERT_TRUE(ev != nullptr);
	EXPECT_EQ(ev->rejectReason, RejectReason::VersionMismatch);
	EXPECT_EQ(a.session->state(), ClientSession::State::Disconnected);
	EXPECT_TRUE(w.server->clients().empty());

	ClientConfig s = clientConfig("Other scene");
	s.sceneHash = 1;
	Peer &b = w.addClient(s);
	w.step(30);
	ASSERT_TRUE(b.find(SessionEvent::Type::Rejected) != nullptr);
	EXPECT_EQ(b.find(SessionEvent::Type::Rejected)->rejectReason, RejectReason::SceneMismatch);
	EXPECT_EQ(b.find(SessionEvent::Type::Rejected)->text, "Arena");
}

TEST(NetSession, RejectWrongPassword)
{
	ServerConfig config = serverConfig();
	config.password = "segredo";
	World w(config);

	ClientConfig bad = clientConfig("Bad");
	bad.password = "errada";
	Peer &a = w.addClient(bad);
	w.step(30);
	const SessionEvent *ev = a.find(SessionEvent::Type::Rejected);
	ASSERT_TRUE(ev != nullptr);
	EXPECT_EQ(ev->rejectReason, RejectReason::WrongPassword);
	EXPECT_EQ(a.session->state(), ClientSession::State::Disconnected);

	ClientConfig good = clientConfig("Good");
	good.password = "segredo";
	Peer &b = w.addClient(good);
	w.step(50);
	EXPECT_EQ(b.session->state(), ClientSession::State::Connected);
	EXPECT_TRUE(b.find(SessionEvent::Type::Rejected) == nullptr);
}

TEST(NetSession, RejectServerFullAndLateJoin)
{
	World w(serverConfig(2));
	w.addClient(clientConfig("1"));
	w.addClient(clientConfig("2"));
	Peer &c = w.addClient(clientConfig("3"));
	w.step(30);
	ASSERT_TRUE(c.find(SessionEvent::Type::Rejected) != nullptr);
	EXPECT_EQ(c.find(SessionEvent::Type::Rejected)->rejectReason, RejectReason::ServerFull);

	ServerConfig config = serverConfig(4);
	config.allowLateJoin = false;
	World w2(config);
	w2.server->setGameStarted(true);
	Peer &d = w2.addClient(clientConfig("late"));
	w2.step(30);
	ASSERT_TRUE(d.find(SessionEvent::Type::Rejected) != nullptr);
	EXPECT_EQ(d.find(SessionEvent::Type::Rejected)->rejectReason, RejectReason::GameInProgress);

	World w3;
	w3.server->ban(77);
	Peer &e = w3.addClient(clientConfig("banned", 77));
	w3.step(30);
	ASSERT_TRUE(e.find(SessionEvent::Type::Rejected) != nullptr);
	EXPECT_EQ(e.find(SessionEvent::Type::Rejected)->rejectReason, RejectReason::Banned);
}

TEST(NetSession, TimeoutBothSides)
{
	World w;
	Peer &a = w.addClient(clientConfig("Ana", 5));
	w.step(30);
	ASSERT_EQ(a.session->state(), ClientSession::State::Connected);

	// Client goes silent: server drops it after 10 s.
	w.step(uint64_t(kConnectionTimeoutMs) - 500, false);
	EXPECT_EQ(w.server->clients().size(), 1u);
	w.step(1000, false);
	EXPECT_TRUE(w.server->clients().empty());
	bool timedOut = false;
	for (const SessionEvent &e : w.serverEvents) {
		timedOut = timedOut ||
		           (e.type == SessionEvent::Type::ClientLeft && e.disconnectReason == DisconnectReason::Timeout);
	}
	EXPECT_TRUE(timedOut);

	// Without a reconnect, the slot expires after 30 s.
	EXPECT_EQ(w.count(SessionEvent::Type::ClientExpired), 0u);
	w.step(uint64_t(kReconnectWindowMs) + 100, false);
	EXPECT_EQ(w.count(SessionEvent::Type::ClientExpired), 1u);
}

TEST(NetSession, ClientHandshakeTimeout)
{
	World w;
	// Server never updates: no Welcome.
	auto transport = createLoopbackTransport(w.hub);
	ClientSession client(*transport, clientConfig("x"));
	ASSERT_TRUE(client.connect("", 7777, 0));
	std::vector<SessionEvent> events;
	client.update(1000, events);
	EXPECT_EQ(client.state(), ClientSession::State::Handshaking);
	client.update(uint64_t(kPendingTimeoutMs), events);
	EXPECT_EQ(client.state(), ClientSession::State::Disconnected);
	ASSERT_EQ(events.size(), 1u);
	EXPECT_EQ(events[0].disconnectReason, DisconnectReason::Timeout);
}

TEST(NetSession, PendingHandshakeTimeout)
{
	World w;
	// Transport connects but never says Hello.
	auto transport = createLoopbackTransport(w.hub);
	ASSERT_TRUE(transport->connect("", 7777));
	w.step(10);
	EXPECT_EQ(w.server->pendingCount(), 1u);
	w.step(uint64_t(kPendingTimeoutMs));
	EXPECT_EQ(w.server->pendingCount(), 0u);
}

TEST(NetSession, ReconnectByToken)
{
	World w;
	Peer &a = w.addClient(clientConfig("Ana", 1111));
	Peer &b = w.addClient(clientConfig("Bruno", 2222));
	w.step(30);
	ASSERT_EQ(a.session->clientId(), 1);

	// Same token while still connected: BadToken.
	Peer &dup = w.addClient(clientConfig("Ana2", 1111));
	w.step(30);
	ASSERT_TRUE(dup.find(SessionEvent::Type::Rejected) != nullptr);
	EXPECT_EQ(dup.find(SessionEvent::Type::Rejected)->rejectReason, RejectReason::BadToken);

	// Ana loses the connection (session dropped without Quit).
	w.removeClient(a);
	w.step(20);
	EXPECT_EQ(w.server->clients().size(), 1u);

	// A new player does not get id 1 while it is reserved.
	Peer &c = w.addClient(clientConfig("Caio", 3333));
	w.step(30);
	EXPECT_EQ(c.session->clientId(), 3);

	// Back within 30 s: same id.
	Peer &again = w.addClient(clientConfig("Ana", 1111));
	w.step(30);
	ASSERT_EQ(again.session->state(), ClientSession::State::Connected);
	EXPECT_EQ(again.session->clientId(), 1);
	bool reconnected = false;
	for (const SessionEvent &e : w.serverEvents) {
		reconnected = reconnected || (e.type == SessionEvent::Type::ClientJoined && e.reconnected && e.client == 1);
	}
	EXPECT_TRUE(reconnected);
	EXPECT_EQ(b.session->players().size(), 3u);
	EXPECT_EQ(w.count(SessionEvent::Type::ClientExpired), 0u);
}

TEST(NetSession, ViolationsDisconnect)
{
	World w;
	Peer &a = w.addClient(clientConfig("Bad"));
	w.step(30);
	ASSERT_EQ(a.session->state(), ClientSession::State::Connected);

	// Server-only messages from a client are violations.
	DespawnMsg bad;
	bad.netId = 1;
	for (int i = 0; i < kMaxViolations - 1; ++i) {
		a.session->send(Channel::Control, makePacket(bad));
	}
	w.step(10);
	EXPECT_EQ(w.server->clients().size(), 1u);
	// Garbage packet: lying length.
	const std::vector<uint8_t> garbage = {uint8_t(MessageType::Chat), 50, 1};
	a.session->send(Channel::Control, garbage);
	w.step(20);
	EXPECT_TRUE(w.server->clients().empty());
	const SessionEvent *ev = a.find(SessionEvent::Type::Disconnected);
	ASSERT_TRUE(ev != nullptr);
	EXPECT_EQ(ev->disconnectReason, DisconnectReason::ProtocolViolation);
}

TEST(NetSession, RpcRateLimit)
{
	World w;
	Peer &a = w.addClient(clientConfig("Spam"));
	w.step(30);
	RpcMsg rpc;
	const std::vector<uint8_t> packet = makePacket(rpc);
	for (int i = 0; i < kMaxRpcPerSecond + 5; ++i) {
		a.session->send(Channel::Rpc, packet);
	}
	w.step(10);
	size_t rpcs = 0;
	for (const SessionEvent &e : w.serverEvents) {
		rpcs += (e.type == SessionEvent::Type::Message && e.messageType == uint8_t(MessageType::Rpc)) ? 1 : 0;
	}
	EXPECT_EQ(rpcs, size_t(kMaxRpcPerSecond));
	// 5 violations: still connected.
	EXPECT_EQ(w.server->clients().size(), 1u);
}

TEST(NetSession, KickAndShutdown)
{
	World w;
	Peer &a = w.addClient(clientConfig("A"));
	Peer &b = w.addClient(clientConfig("B"));
	w.step(30);
	w.server->kick(1);
	w.step(20);
	ASSERT_TRUE(a.find(SessionEvent::Type::Disconnected) != nullptr);
	EXPECT_EQ(a.find(SessionEvent::Type::Disconnected)->disconnectReason, DisconnectReason::Kicked);
	w.server->stop();
	w.step(20);
	ASSERT_TRUE(b.find(SessionEvent::Type::Disconnected) != nullptr);
	EXPECT_EQ(b.find(SessionEvent::Type::Disconnected)->disconnectReason, DisconnectReason::ServerShutdown);
}

TEST(NetSession, ChangeScene)
{
	World w;
	Peer &a = w.addClient(clientConfig("A"));
	w.step(30);
	a.session->sceneLoaded(kScene);
	w.step(20);
	EXPECT_TRUE(w.server->client(1)->ready);
	w.server->changeScene("Level2", 99);
	w.step(20);
	EXPECT_FALSE(w.server->client(1)->ready);
	EXPECT_EQ(a.session->sceneName(), "Level2");
	a.session->sceneLoaded(99);
	w.step(20);
	EXPECT_TRUE(w.server->client(1)->ready);
}

TEST(NetSession, OverENet)
{
	std::unique_ptr<ITransport> st = createENetTransport();
	std::unique_ptr<ITransport> ct = createENetTransport();
	ServerSession server(*st, serverConfig());
	ASSERT_TRUE(server.start(0));
	ClientSession client(*ct, clientConfig("udp"));
	const uint64_t start = steadyClockMs();
	ASSERT_TRUE(client.connect("127.0.0.1", st->localPort(), start));
	std::vector<SessionEvent> se, ce;
	bool connected = false;
	for (int i = 0; i < 400 && !connected; ++i) {
		const uint64_t now = steadyClockMs();
		server.update(now, 1, se);
		client.update(now, ce);
		connected = client.state() == ClientSession::State::Connected;
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
	}
	ASSERT_TRUE(connected);
	EXPECT_EQ(client.clientId(), 1);
	client.disconnect();
	for (int i = 0; i < 200 && !server.clients().empty(); ++i) {
		server.update(steadyClockMs(), 1, se);
		std::vector<TransportEvent> drain;
		ct->poll(drain);
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
	}
	EXPECT_TRUE(server.clients().empty());
}
