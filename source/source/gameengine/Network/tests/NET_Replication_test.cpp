/* Replication: server replicator and replica clients over the simulated transport. */

#include "NET_Messages.h"
#include "NET_ReplicaClient.h"
#include "NET_Replicator.h"

#include "net_test_util.h"

#include "gtest/gtest.h"

#include <cmath>
#include <functional>
#include <map>

using namespace net;

namespace {

const uint64_t kScene = 0x5EED;

/* -------------------------------------------------------------------- */
/** \name Test world
 * \{ */

class MapWorld : public IWorld {
public:
	struct Obj {
		ObjectState s;
		bool sleeping = false;
		ClientId owner = 0;
		std::string prototype;
	};

	Obj &add(NetId id)
	{
		Obj &o = objects[id];
		o.s.id = id;
		return o;
	}

	bool getTransform(NetId id, float position[3], float rotation[4]) const override
	{
		const Obj *o = find(id);
		if (!o) {
			return false;
		}
		std::copy(o->s.position, o->s.position + 3, position);
		std::copy(o->s.rotation, o->s.rotation + 4, rotation);
		return true;
	}
	bool getVelocity(NetId id, float linear[3], float angular[3]) const override
	{
		const Obj *o = find(id);
		if (!o) {
			return false;
		}
		std::copy(o->s.velocity, o->s.velocity + 3, linear);
		std::copy(o->s.angularVelocity, o->s.angularVelocity + 3, angular);
		return true;
	}
	bool getProperties(NetId id, std::vector<PropValue> &props) const override
	{
		const Obj *o = find(id);
		if (!o) {
			return false;
		}
		props = o->s.props;
		return true;
	}
	bool isSleeping(NetId id) const override
	{
		const Obj *o = find(id);
		return o && o->sleeping;
	}
	void setTransform(NetId id, const float position[3], const float rotation[4]) override
	{
		Obj &o = objects.at(id);
		std::copy(position, position + 3, o.s.position);
		std::copy(rotation, rotation + 4, o.s.rotation);
		++writes;
	}
	void setVelocity(NetId id, const float linear[3], const float angular[3]) override
	{
		Obj &o = objects.at(id);
		std::copy(linear, linear + 3, o.s.velocity);
		std::copy(angular, angular + 3, o.s.angularVelocity);
	}
	void setProperties(NetId id, const std::vector<PropValue> &props) override
	{
		objects.at(id).s.props = props;
	}
	bool spawn(NetId id, const std::string &prototype, ClientId owner, const ObjectState &state) override
	{
		Obj &o = objects[id];
		o.s = state;
		o.s.id = id;
		o.owner = owner;
		o.prototype = prototype;
		++spawns;
		return true;
	}
	void despawn(NetId id) override
	{
		objects.erase(id);
		++despawns;
	}
	void setOwner(NetId id, ClientId owner) override
	{
		objects.at(id).owner = owner;
	}
	bool exists(NetId id) const override
	{
		return objects.count(id) != 0;
	}

	const Obj *find(NetId id) const
	{
		const auto it = objects.find(id);
		return it == objects.end() ? nullptr : &it->second;
	}

	std::map<NetId, Obj> objects;
	int spawns = 0;
	int despawns = 0;
	int writes = 0;
};

/** \} */

/* -------------------------------------------------------------------- */
/** \name Harness
 * \{ */

/// Records what the client receives, then passes it on.
class SpyTransport : public ITransport {
public:
	explicit SpyTransport(std::unique_ptr<ITransport> inner)
		:m_inner(std::move(inner))
	{
	}
	bool listen(uint16_t port, int maxPeers) override
	{
		return m_inner->listen(port, maxPeers);
	}
	bool connect(const std::string &host, uint16_t port) override
	{
		return m_inner->connect(host, port);
	}
	void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) override
	{
		m_inner->send(peer, channel, data, size);
	}
	void disconnect(PeerId peer) override
	{
		m_inner->disconnect(peer);
	}
	void poll(std::vector<TransportEvent> &events) override
	{
		const size_t first = events.size();
		m_inner->poll(events);
		for (size_t i = first; i < events.size(); ++i) {
			if (events[i].type == TransportEvent::Type::Received) {
				received.push_back({events[i].channel, events[i].data});
			}
		}
	}
	void shutdown() override
	{
		m_inner->shutdown();
	}
	bool reliableAll() const override
	{
		return m_inner->reliableAll();
	}

	struct Packet {
		Channel channel;
		std::vector<uint8_t> data;
	};
	std::vector<Packet> received;

private:
	std::unique_ptr<ITransport> m_inner;
};

/// Property layout shared by server and clients.
const std::vector<PropertyDesc> &propSchema()
{
	static const std::vector<PropertyDesc> schema = [] {
		std::vector<PropertyDesc> s(2);
		s[0].kind = PropKind::Int;
		s[1].kind = PropKind::Float;
		s[1].min = 0.0f;
		s[1].max = 100.0f;
		s[1].bits = 10;
		return s;
	}();
	return schema;
}

struct Client {
	SpyTransport *spy = nullptr;
	std::unique_ptr<ITransport> transport;
	std::unique_ptr<ClientSession> session;
	MapWorld world;
	std::unique_ptr<ReplicaClient> replica;
	std::vector<SessionEvent> events;
};

struct Net {
	uint64_t now = 1000;
	Tick tick = 1;
	uint32_t tickMs = 33;
	NetSimSettings sim;
	uint64_t seed = 1;
	std::shared_ptr<LoopbackHub> hub = createLoopbackHub();
	std::unique_ptr<ITransport> serverTransport;
	std::unique_ptr<ServerSession> server;
	MapWorld world;
	std::unique_ptr<Replicator> replicator;
	std::vector<SessionEvent> serverEvents;
	std::vector<std::unique_ptr<Client>> clients;
	/// Scene objects that clients have too (same .range file).
	std::map<NetId, ObjectState> sceneObjects;

	explicit Net(const NetSimSettings &settings = NetSimSettings(), ReplicatorConfig config = ReplicatorConfig())
		:sim(settings)
	{
		serverTransport = wrap();
		ServerConfig sc;
		sc.gameId = "test";
		sc.gameVersion = 1;
		sc.sceneName = "Arena";
		sc.sceneHash = kScene;
		sc.tickRate = 30;
		sc.snapshotRate = 30;
		sc.maxClients = 16;
		server = std::make_unique<ServerSession>(*serverTransport, sc);
		EXPECT_TRUE(server->start(7777));
		config.snapshotIntervalTicks = 1;
		replicator = std::make_unique<Replicator>(*server, world, config);
	}

	std::unique_ptr<ITransport> wrap()
	{
		NetSimSettings s = sim;
		s.seed = sim.seed + 1000 * seed++;
		s.clock = [this] { return now; };
		return createSimulatedTransport(createLoopbackTransport(hub), s);
	}

	void addSceneObject(NetId id, const ReplicatedObjectDesc &desc, const ObjectState &state)
	{
		MapWorld::Obj &o = world.add(id);
		o.s = state;
		o.s.id = id;
		replicator->addSceneObject(id, desc);
		sceneObjects[id] = o.s;
		for (auto &c : clients) {
			c->world.add(id).s = o.s;
		}
	}

	Client &addClient(const std::string &name, uint64_t token = 0,
	                  const std::function<void(ReplicaClientConfig &)> &tweak = nullptr)
	{
		auto c = std::make_unique<Client>();
		auto spy = std::make_unique<SpyTransport>(wrap());
		c->spy = spy.get();
		c->transport = std::move(spy);
		ClientConfig cc;
		cc.gameId = "test";
		cc.gameVersion = 1;
		cc.playerName = name;
		cc.sceneHash = kScene;
		cc.token = token;
		c->session = std::make_unique<ClientSession>(*c->transport, cc);
		ReplicaClientConfig rc;
		rc.schema = [](NetId, const std::string &) { return &propSchema(); };
		if (tweak) {
			tweak(rc);
		}
		c->replica = std::make_unique<ReplicaClient>(*c->session, c->world, rc);
		for (const auto &pair : sceneObjects) {
			c->world.add(pair.first).s = pair.second;
		}
		EXPECT_TRUE(c->session->connect("loopback", 7777, now));
		clients.push_back(std::move(c));
		return *clients.back();
	}

	void removeClient(Client &client)
	{
		for (auto it = clients.begin(); it != clients.end(); ++it) {
			if (it->get() == &client) {
				clients.erase(it);
				return;
			}
		}
	}

	void updateClients()
	{
		for (auto &c : clients) {
			const size_t first = c->events.size();
			c->session->update(now, c->events);
			for (size_t i = first; i < c->events.size(); ++i) {
				const SessionEvent &e = c->events[i];
				c->replica->handleEvent(e, now);
				if (e.type == SessionEvent::Type::SceneChange) {
					c->session->sceneLoaded(e.sceneHash);
				}
			}
			c->replica->applyLatest();
		}
	}

	void step(int ticks = 1)
	{
		for (int i = 0; i < ticks; ++i) {
			now += tickMs;
			updateClients();
			const size_t first = serverEvents.size();
			server->update(now, tick, serverEvents);
			for (size_t j = first; j < serverEvents.size(); ++j) {
				replicator->handleEvent(serverEvents[j]);
			}
			replicator->update(tick, now);
			++tick;
		}
	}

	/// Steps until every client is connected and ready.
	void connectAll()
	{
		for (int i = 0; i < 200; ++i) {
			step();
			bool all = true;
			for (auto &c : clients) {
				const ServerSession::ClientState *cs =
				    c->session->clientId() ? server->client(c->session->clientId()) : nullptr;
				all = all && c->session->state() == ClientSession::State::Connected && cs && cs->ready;
			}
			if (all) {
				return;
			}
		}
		ADD_FAILURE() << "clients did not connect";
	}
};

ObjectState stateAt(float x, float y, float z)
{
	ObjectState s;
	s.position[0] = x;
	s.position[1] = y;
	s.position[2] = z;
	s.hasTransform = true;
	return s;
}

bool samePosition(const ObjectState &a, const ObjectState &b, float tolerance = 0.0011f)
{
	for (int i = 0; i < 3; ++i) {
		if (std::fabs(a.position[i] - b.position[i]) > tolerance) {
			return false;
		}
	}
	return true;
}

/// Presence bits of the single entry of a snapshot packet: transform, velocity, angular, props, anim.
bool singleEntryFields(const std::vector<uint8_t> &packet, bool fields[5])
{
	PacketReader reader(packet.data(), packet.size());
	RawMessage raw;
	if (!reader.next(raw) || raw.type != uint8_t(MessageType::Snapshot)) {
		return false;
	}
	BitReader r(raw.body, raw.size);
	r.readU32();
	r.readU32();
	if (r.readVarU() != 1) {
		return false;
	}
	r.readVarU();
	if (r.readBool() || !r.readBool()) {
		return false;  // removed, or unchanged
	}
	// Each presence bit is followed by its data only when set; the test only changes one field.
	for (int i = 0; i < 5; ++i) {
		fields[i] = r.readBool();
		if (fields[i]) {
			for (int j = i + 1; j < 5; ++j) {
				fields[j] = false;
			}
			return r.ok();
		}
	}
	return r.ok();
}

std::vector<uint8_t> lastSnapshot(const Client &c)
{
	for (auto it = c.spy->received.rbegin(); it != c.spy->received.rend(); ++it) {
		if (it->channel == Channel::Snapshot) {
			PacketReader reader(it->data.data(), it->data.size());
			RawMessage raw;
			if (reader.next(raw) && raw.type == uint8_t(MessageType::Snapshot)) {
				return it->data;
			}
		}
	}
	return {};
}

/** \} */

}  // namespace

TEST(NetReplication, DeltaCarriesOnlyChangedFields)
{
	Net net;
	ReplicatedObjectDesc desc;
	desc.syncVelocity = true;
	desc.props = propSchema();
	ObjectState s = stateAt(1.0f, 2.0f, 3.0f);
	s.hasVelocity = true;
	s.velocity[0] = 1.0f;
	s.props = {PropValue::makeInt(5), PropValue::makeFloat(50.0f)};
	net.addSceneObject(42, desc, s);

	Client &a = net.addClient("Ana");
	Client &b = net.addClient("Bia");
	net.connectAll();
	net.step(5);
	ASSERT_EQ(net.replicator->stats(a.session->clientId())->lastSnapshotEntries, 0u);

	// Only a property changes.
	net.world.objects[42].s.props[0] = PropValue::makeInt(6);
	net.step(1);
	net.updateClients();
	bool fields[5];
	ASSERT_TRUE(singleEntryFields(lastSnapshot(a), fields));
	EXPECT_FALSE(fields[0]);
	EXPECT_FALSE(fields[1]);
	EXPECT_FALSE(fields[2]);
	EXPECT_TRUE(fields[3]);
	EXPECT_EQ(a.world.objects[42].s.props[0].i, 6);
	EXPECT_EQ(b.world.objects[42].s.props[0].i, 6);

	// Only the position changes.
	net.step(3);
	net.world.objects[42].s.position[0] = 4.0f;
	net.step(1);
	net.updateClients();
	ASSERT_TRUE(singleEntryFields(lastSnapshot(b), fields));
	EXPECT_TRUE(fields[0]);
	EXPECT_NEAR(b.world.objects[42].s.position[0], 4.0f, 0.001f);

	// Only the velocity changes.
	net.step(3);
	net.world.objects[42].s.velocity[1] = -2.0f;
	net.step(1);
	net.updateClients();
	ASSERT_TRUE(singleEntryFields(lastSnapshot(a), fields));
	EXPECT_FALSE(fields[0]);
	EXPECT_TRUE(fields[1]);
}

TEST(NetReplication, ObjectAtRestCostsNothingAfterAck)
{
	Net net;
	for (NetId id = 1; id <= 20; ++id) {
		net.addSceneObject(id, ReplicatedObjectDesc(), stateAt(float(id), 0.0f, 0.0f));
	}
	Client &a = net.addClient("Ana");
	net.connectAll();
	net.step(5);
	const ClientId id = a.session->clientId();
	const ReplicationStats *st = net.replicator->stats(id);
	ASSERT_NE(st->ackedTick, kNoTick);

	// Empty delta: only the snapshot header (message header, two ticks, count).
	const size_t emptyBytes = st->lastSnapshotBytes;
	EXPECT_LE(emptyBytes, 12u);
	for (int i = 0; i < 30; ++i) {
		net.step();
		EXPECT_EQ(st->lastSnapshotEntries, 0u);
		EXPECT_EQ(st->lastSnapshotBytes, emptyBytes);
	}

	// A sleeping object is not read again, even if the world reports small drift.
	net.world.objects[3].sleeping = true;
	net.world.objects[3].s.position[1] = 0.5f;
	net.step(3);
	EXPECT_EQ(st->lastSnapshotEntries, 0u);
	net.world.objects[3].sleeping = false;
	net.step(1);
	EXPECT_EQ(st->lastSnapshotEntries, 1u);
}

TEST(NetReplication, ConvergesWithLoss)
{
	NetSimSettings sim;
	sim.latencyMs = 50;
	sim.jitterMs = 10;
	sim.lossPercent = 10.0f;
	sim.seed = 7;
	Net net(sim);

	ReplicatedObjectDesc desc;
	desc.props = propSchema();
	for (NetId id = 1; id <= 30; ++id) {
		ObjectState s = stateAt(0.0f, float(id), 0.0f);
		s.props = {PropValue::makeInt(0), PropValue::makeFloat(0.0f)};
		net.addSceneObject(id, desc, s);
	}
	Client &a = net.addClient("Ana");
	Client &b = net.addClient("Bia");
	net.connectAll();

	// Runtime objects too.
	std::vector<NetId> spawned;
	for (int i = 0; i < 5; ++i) {
		ReplicatedObjectDesc d = desc;
		d.prototype = "Crate";
		const NetId id = net.replicator->spawn(d);
		ASSERT_NE(id, kInvalidNetId);
		ObjectState s = stateAt(float(i), 0.0f, 5.0f);
		s.props = {PropValue::makeInt(i), PropValue::makeFloat(1.0f)};
		net.world.add(id).s = s;
		net.world.objects[id].s.id = id;
		spawned.push_back(id);
	}

	net_test::Rng rng(3);
	for (int t = 0; t < 90; ++t) {
		for (auto &pair : net.world.objects) {
			ObjectState &s = pair.second.s;
			s.position[0] += rng.uniform(-0.2f, 0.2f);
			s.position[2] += rng.uniform(-0.2f, 0.2f);
			const float angle = rng.uniform(0.0f, 3.0f);
			s.rotation[0] = 0.0f;
			s.rotation[1] = 0.0f;
			s.rotation[2] = std::sin(angle / 2.0f);
			s.rotation[3] = std::cos(angle / 2.0f);
			s.props[0] = PropValue::makeInt(t);
			s.props[1] = PropValue::makeFloat(rng.uniform(0.0f, 100.0f));
		}
		net.step();
	}
	net.step(60);

	for (Client *c : {&a, &b}) {
		EXPECT_EQ(c->world.objects.size(), net.world.objects.size());
		for (const auto &pair : net.world.objects) {
			const MapWorld::Obj *o = c->world.find(pair.first);
			ASSERT_TRUE(o != nullptr) << pair.first;
			EXPECT_TRUE(samePosition(o->s, pair.second.s)) << pair.first;
			float dot = 0.0f;
			for (int i = 0; i < 4; ++i) {
				dot += o->s.rotation[i] * pair.second.s.rotation[i];
			}
			EXPECT_GT(std::fabs(dot), 0.9999f) << pair.first;
			EXPECT_EQ(o->s.props[0].i, 89);
			EXPECT_NEAR(o->s.props[1].f, pair.second.s.props[1].f, 0.1f);
		}
		EXPECT_GT(c->replica->stats().snapshotsAccepted, 30u);
	}
	EXPECT_EQ(a.world.objects.at(spawned[2]).prototype, "Crate");
}

TEST(NetReplication, BandwidthBudget)
{
	ReplicatorConfig config;
	config.bytesPerSecond = 8000;
	Net net(NetSimSettings(), config);
	const int count = 200;
	for (NetId id = 1; id <= NetId(count); ++id) {
		net.addSceneObject(id, ReplicatedObjectDesc(), stateAt(float(id), 0.0f, 0.0f));
	}
	Client &a = net.addClient("Ana");
	net.connectAll();
	const ReplicationStats *st = net.replicator->stats(a.session->clientId());
	const uint64_t startBytes = st->snapshotBytes + st->reliableBytes;
	const uint64_t startMs = net.now;

	// Everything moves every tick: far more than 8 KB/s of changes.
	for (int t = 0; t < 150; ++t) {
		for (auto &pair : net.world.objects) {
			pair.second.s.position[1] += 0.01f;
		}
		net.step();
	}
	const double seconds = double(net.now - startMs) / 1000.0;
	const double used = double(st->snapshotBytes + st->reliableBytes - startBytes);
	// Budget plus the token bucket capacity.
	EXPECT_LE(used, 8000.0 * seconds + 2.0 * double(kMaxUnreliablePayload));
	EXPECT_GT(used, 8000.0 * seconds * 0.8);
	EXPECT_GT(st->pendingObjects, 0u);

	for (const SpyTransport::Packet &p : a.spy->received) {
		if (p.channel == Channel::Snapshot) {
			EXPECT_LE(p.data.size(), kMaxUnreliablePayload);
		}
	}
	// The priority accumulator reaches every object: all moved on the client.
	for (NetId id = 1; id <= NetId(count); ++id) {
		EXPECT_GT(a.world.objects.at(id).s.position[1], 0.3f) << id;
	}
}

TEST(NetReplication, RelevanceTogglesSpawn)
{
	ReplicatorConfig config;
	config.cellSize = 16.0f;
	Net net(NetSimSettings(), config);
	net.addSceneObject(7, ReplicatedObjectDesc(), stateAt(500.0f, 0.0f, 0.0f));
	ReplicatedObjectDesc always;
	always.alwaysRelevant = true;
	net.addSceneObject(8, always, stateAt(900.0f, 0.0f, 0.0f));

	Client &near = net.addClient("Near");
	Client &all = net.addClient("All");
	net.connectAll();
	const ClientId nearId = near.session->clientId();
	const float origin[3] = {0.0f, 0.0f, 0.0f};
	net.replicator->setClientView(nearId, origin, 50.0f);

	ReplicatedObjectDesc desc;
	desc.prototype = "Ball";
	desc.props = propSchema();
	const NetId ball = net.replicator->spawn(desc);
	ObjectState s = stateAt(10.0f, 0.0f, 0.0f);
	s.props = {PropValue::makeInt(1), PropValue::makeFloat(2.0f)};
	net.world.add(ball).s = s;
	net.world.objects[ball].s.id = ball;
	net.step(5);

	EXPECT_TRUE(near.world.exists(ball));
	EXPECT_TRUE(all.world.exists(ball));
	EXPECT_FALSE(net.replicator->isRelevant(nearId, 7));
	EXPECT_TRUE(net.replicator->isRelevant(nearId, 8));

	// Out of range (beyond the hysteresis): despawned only for the near client.
	net.world.objects[ball].s.position[0] = 200.0f;
	net.step(5);
	EXPECT_FALSE(near.world.exists(ball));
	EXPECT_TRUE(all.world.exists(ball));
	EXPECT_NEAR(all.world.objects[ball].s.position[0], 200.0f, 0.001f);

	// Just outside the radius but inside the hysteresis: still not spawned.
	net.world.objects[ball].s.position[0] = 52.0f;
	net.step(5);
	EXPECT_FALSE(near.world.exists(ball));

	// Back in range: spawned again with the current state.
	net.world.objects[ball].s.position[0] = 20.0f;
	net.step(5);
	ASSERT_TRUE(near.world.exists(ball));
	EXPECT_NEAR(near.world.objects[ball].s.position[0], 20.0f, 0.001f);
	EXPECT_EQ(near.world.spawns, 2);
	EXPECT_EQ(near.world.despawns, 1);

	// The view follows the client: the scene object comes into range.
	const float far[3] = {490.0f, 0.0f, 0.0f};
	net.replicator->setClientView(nearId, far, 50.0f);
	net.world.objects[7].s.position[1] = 1.0f;
	net.step(5);
	EXPECT_TRUE(net.replicator->isRelevant(nearId, 7));
	EXPECT_NEAR(near.world.objects[7].s.position[1], 1.0f, 0.001f);
	EXPECT_FALSE(near.world.exists(ball));

	// Despawn by the server reaches only clients that have it.
	net.replicator->despawn(ball);
	net.step(3);
	EXPECT_FALSE(all.world.exists(ball));
	EXPECT_EQ(near.world.despawns, 2);
	EXPECT_EQ(near.replica->stats().snapshotsInvalid, 0u);
	EXPECT_EQ(all.replica->stats().snapshotsInvalid, 0u);
}

TEST(NetReplication, OwnershipAndSpawnOrder)
{
	Net net;
	Client &a = net.addClient("Ana");
	net.connectAll();
	const ClientId id = a.session->clientId();

	ReplicatedObjectDesc desc;
	desc.prototype = "Player";
	desc.owner = id;
	const NetId player = net.replicator->spawn(desc);
	net.world.add(player).s = stateAt(1.0f, 1.0f, 1.0f);
	net.world.objects[player].s.id = player;
	net.step(3);
	ASSERT_TRUE(a.world.exists(player));
	EXPECT_EQ(a.world.objects[player].owner, id);

	// Spawn arrives before the first snapshot that cites the object.
	bool spawnSeen = false;
	bool snapshotBeforeSpawn = false;
	for (const SpyTransport::Packet &p : a.spy->received) {
		PacketReader reader(p.data.data(), p.data.size());
		RawMessage raw;
		while (reader.next(raw)) {
			if (raw.type == uint8_t(MessageType::Spawn)) {
				spawnSeen = true;
			}
			if (raw.type == uint8_t(MessageType::Snapshot) && !spawnSeen && raw.size > 9) {
				snapshotBeforeSpawn = true;
			}
		}
	}
	EXPECT_TRUE(spawnSeen);
	EXPECT_FALSE(snapshotBeforeSpawn);

	net.replicator->setOwner(player, kServerClientId);
	net.step(2);
	EXPECT_EQ(a.world.objects[player].owner, kServerClientId);
	EXPECT_EQ(a.replica->owner(player), kServerClientId);
}

TEST(NetReplication, SkipOwnedLeavesPredictedObjectsAlone)
{
	Net net;
	NetId predicted = kInvalidNetId;
	Client &a = net.addClient("Ana", 0, [&predicted](ReplicaClientConfig &rc) {
		rc.skipOwned = true;
		rc.skipFilter = [&predicted](NetId id) { return id == predicted; };
	});
	net.connectAll();
	const ClientId id = a.session->clientId();

	ReplicatedObjectDesc desc;
	desc.prototype = "Player";
	desc.owner = id;
	predicted = net.replicator->spawn(desc);
	const NetId other = net.replicator->spawn(desc);
	for (NetId n : {predicted, other}) {
		net.world.add(n).s = stateAt(1.0f, 0.0f, 0.0f);
		net.world.objects[n].s.id = n;
	}
	net.step(3);
	ASSERT_TRUE(a.world.exists(predicted));
	ASSERT_TRUE(a.world.exists(other));

	// The client moves its predicted object itself; the server moves both.
	a.world.objects[predicted].s.position[0] = 7.0f;
	net.world.objects[predicted].s.position[0] = 3.0f;
	net.world.objects[other].s.position[0] = 3.0f;
	net.step(4);
	EXPECT_NEAR(a.world.objects[predicted].s.position[0], 7.0f, 0.001f);
	EXPECT_NEAR(a.world.objects[other].s.position[0], 3.0f, 0.001f);

	// Given back to the server: the snapshots drive it again.
	net.replicator->setOwner(predicted, kServerClientId);
	net.step(4);
	EXPECT_NEAR(a.world.objects[predicted].s.position[0], 3.0f, 0.001f);
}

TEST(NetReplication, ReconnectGetsFullState)
{
	Net net;
	ReplicatedObjectDesc desc;
	desc.props = propSchema();
	ObjectState s = stateAt(1.0f, 0.0f, 0.0f);
	s.props = {PropValue::makeInt(1), PropValue::makeFloat(1.0f)};
	net.addSceneObject(3, desc, s);

	Client *a = &net.addClient("Ana", 777);
	net.connectAll();
	ReplicatedObjectDesc rt;
	rt.prototype = "Crate";
	const NetId crate = net.replicator->spawn(rt);
	net.world.add(crate).s = stateAt(2.0f, 0.0f, 0.0f);
	net.world.objects[crate].s.id = crate;
	net.step(5);
	ASSERT_TRUE(a->world.exists(crate));

	// Connection lost; the server keeps changing things meanwhile.
	net.removeClient(*a);
	net.step(5);
	net.world.objects[3].s.position[0] = 9.0f;
	net.world.objects[3].s.props[0] = PropValue::makeInt(99);
	net.world.objects[crate].s.position[2] = 4.0f;
	const NetId crate2 = net.replicator->spawn(rt);
	net.world.add(crate2).s = stateAt(0.0f, 7.0f, 0.0f);
	net.world.objects[crate2].s.id = crate2;
	net.step(5);

	// Reconnects with a fresh world (only scene objects from the file).
	a = &net.addClient("Ana", 777);
	net.connectAll();
	net.step(3);
	EXPECT_EQ(a->session->clientId(), 1);
	ASSERT_TRUE(a->world.exists(crate));
	ASSERT_TRUE(a->world.exists(crate2));
	EXPECT_NEAR(a->world.objects[3].s.position[0], 9.0f, 0.001f);
	EXPECT_EQ(a->world.objects[3].s.props[0].i, 99);
	EXPECT_NEAR(a->world.objects[crate].s.position[2], 4.0f, 0.001f);
	EXPECT_NEAR(a->world.objects[crate2].s.position[1], 7.0f, 0.001f);
}

TEST(NetReplication, ClientDropsOldSnapshotsAndRequestsFullState)
{
	// Feed the replica client directly, without a server.
	std::unique_ptr<ITransport> other;
	auto transport = createLoopbackPair(other);
	ClientConfig cc;
	ClientSession session(*transport, cc);
	MapWorld world;
	world.add(5).s = stateAt(0.0f, 0.0f, 0.0f);
	ReplicaClient replica(session, world);
	SnapshotConfig config;

	const auto feed = [&](Tick tick, const Snapshot *baseline, float x) {
		std::vector<ObjectState> objects = {stateAt(x, 0.0f, 0.0f)};
		objects[0].id = 5;
		std::vector<uint8_t> packet;
		EXPECT_TRUE(encodeSnapshotMessage(packet, tick, objects, baseline, config));
		PacketReader reader(packet.data(), packet.size());
		RawMessage raw;
		EXPECT_TRUE(reader.next(raw));
		SessionEvent e;
		e.type = SessionEvent::Type::Message;
		e.messageType = raw.type;
		e.channel = Channel::Snapshot;
		e.body.assign(raw.body, raw.body + raw.size);
		replica.handleEvent(e, 1000);
	};

	feed(10, nullptr, 1.0f);
	feed(5, nullptr, 2.0f);  // older: dropped
	EXPECT_EQ(replica.lastAcceptedTick(), 10u);
	EXPECT_EQ(replica.stats().snapshotsOld, 1u);
	replica.applyLatest();
	EXPECT_NEAR(world.objects[5].s.position[0], 1.0f, 0.001f);

	// Delta against a baseline the client never had: asks for full state.
	Snapshot missing;
	missing.tick = 8;
	missing.objects = {stateAt(0.0f, 0.0f, 0.0f)};
	missing.objects[0].id = 5;
	feed(12, &missing, 3.0f);
	EXPECT_EQ(replica.stats().snapshotsNoBaseline, 1u);
	EXPECT_EQ(replica.stats().fullStateRequests, 1u);
	EXPECT_EQ(replica.lastAcceptedTick(), 10u);

	// Delta against the accepted one works.
	feed(13, replica.buffer().find(10), 3.0f);
	EXPECT_EQ(replica.lastAcceptedTick(), 13u);
	replica.applyLatest();
	EXPECT_NEAR(world.objects[5].s.position[0], 3.0f, 0.001f);
}

/* -------------------------------------------------------------------- */
/** \name Fuzz
 * \{ */

namespace {

/// Message bodies seen by a client in a short session with spawns, props and movement.
std::vector<std::pair<uint8_t, std::vector<uint8_t>>> collectBodies()
{
	Net net;
	ReplicatedObjectDesc desc;
	desc.props = propSchema();
	desc.syncVelocity = true;
	for (NetId id = 1; id <= 5; ++id) {
		ObjectState s = stateAt(float(id), 0.0f, 0.0f);
		s.props = {PropValue::makeInt(id), PropValue::makeFloat(1.0f)};
		net.addSceneObject(id * 1000, desc, s);
	}
	Client &a = net.addClient("Ana");
	net.connectAll();
	desc.prototype = "Crate";
	for (int i = 0; i < 4; ++i) {
		const NetId id = net.replicator->spawn(desc);
		ObjectState s = stateAt(0.0f, float(i), 0.0f);
		s.id = id;
		s.props = {PropValue::makeInt(i), PropValue::makeFloat(2.0f)};
		net.world.add(id).s = s;
	}
	for (int t = 0; t < 20; ++t) {
		for (auto &pair : net.world.objects) {
			pair.second.s.position[0] += 0.1f;
			pair.second.s.props[0] = PropValue::makeInt(t);
		}
		if (t == 10) {
			net.replicator->setOwner(kFirstRuntimeNetId, 1);
			net.replicator->despawn(kFirstRuntimeNetId + 1);
		}
		net.step();
	}
	std::vector<std::pair<uint8_t, std::vector<uint8_t>>> bodies;
	for (const SpyTransport::Packet &p : a.spy->received) {
		PacketReader reader(p.data.data(), p.data.size());
		RawMessage raw;
		while (reader.next(raw)) {
			bodies.push_back({raw.type, std::vector<uint8_t>(raw.body, raw.body + raw.size)});
		}
	}
	return bodies;
}

SessionEvent messageEvent(ClientId client, uint8_t type, const std::vector<uint8_t> &body)
{
	SessionEvent e;
	e.type = SessionEvent::Type::Message;
	e.client = client;
	e.messageType = type;
	e.body = body;
	return e;
}

/// Random bytes, or a valid body with flipped bits, truncated or extended.
std::vector<uint8_t> mutate(net_test::Rng &rng, const std::vector<uint8_t> &valid)
{
	std::vector<uint8_t> body;
	switch (rng.below(4)) {
		case 0:
			body.resize(rng.below(80));
			for (uint8_t &b : body) {
				b = uint8_t(rng.below(256));
			}
			break;
		case 1:
			body = valid;
			for (uint32_t n = rng.below(4) + 1; n > 0 && !body.empty(); --n) {
				body[rng.below(uint32_t(body.size()))] ^= uint8_t(1u << rng.below(8));
			}
			break;
		case 2:
			body.assign(valid.begin(), valid.begin() + rng.below(uint32_t(valid.size()) + 1));
			break;
		default:
			body = valid;
			for (uint32_t n = rng.below(8) + 1; n > 0; --n) {
				body.push_back(uint8_t(rng.below(256)));
			}
			break;
	}
	return body;
}

}  // namespace

TEST(NetReplicationFuzz, ReplicaClientDecode)
{
	const auto bodies = collectBodies();
	ASSERT_FALSE(bodies.empty());
	const uint8_t types[] = {uint8_t(MessageType::Snapshot), uint8_t(MessageType::Spawn),
	                         uint8_t(MessageType::Despawn), uint8_t(MessageType::Ownership)};

	std::unique_ptr<ITransport> other;
	auto transport = createLoopbackPair(other);
	ClientSession session(*transport, ClientConfig());
	MapWorld world;
	for (NetId id = 1; id <= 5; ++id) {
		world.add(id * 1000).s = stateAt(0.0f, 0.0f, 0.0f);
	}
	ReplicaClientConfig rc;
	rc.schema = [](NetId, const std::string &) { return &propSchema(); };
	ReplicaClient replica(session, world, rc);

	net_test::Rng rng(12345);
	for (int i = 0; i < 100000; ++i) {
		const auto &valid = bodies[rng.below(uint32_t(bodies.size()))];
		// Mostly the real type of the body, sometimes another replication type.
		const uint8_t type = rng.below(4) == 0 ? types[rng.below(4)] : valid.first;
		replica.handleEvent(messageEvent(0, type, mutate(rng, valid.second)), uint64_t(i));
		if (i % 64 == 0) {
			replica.applyLatest();
			replica.applyInterpolated(replica.lastAcceptedTick(), 0.5f);
		}
		if (i % 20000 == 0) {
			replica.reset();
		}
	}
	// Still works with valid input after the noise.
	replica.reset();
	for (const auto &b : bodies) {
		replica.handleEvent(messageEvent(0, b.first, b.second), 0);
	}
	EXPECT_NE(replica.lastAcceptedTick(), kNoTick);
	EXPECT_TRUE(replica.applyLatest());
}

TEST(NetReplicationFuzz, ReplicatorAckDecode)
{
	Net net;
	net.addSceneObject(1, ReplicatedObjectDesc(), stateAt(0.0f, 0.0f, 0.0f));
	Client &a = net.addClient("Ana");
	net.connectAll();
	net.step(3);
	const ClientId id = a.session->clientId();

	SnapshotAckMsg ack;
	ack.tick = net.tick - 1;
	std::vector<uint8_t> validAck;
	BitWriter w(validAck);
	encode(w, ack);
	const uint8_t types[] = {uint8_t(MessageType::SnapshotAck), uint8_t(MessageType::FullStateRequest),
	                         uint8_t(MessageType::Input), uint8_t(MessageType::Rpc)};

	net_test::Rng rng(777);
	for (int i = 0; i < 100000; ++i) {
		const uint8_t type = types[rng.below(4)];
		const ClientId client = rng.below(4) == 0 ? ClientId(rng.below(70)) : id;
		net.replicator->handleEvent(messageEvent(client, type, mutate(rng, validAck)));
		if (i % 5000 == 0) {
			net.step();
		}
	}
	// Replication recovers: the object moves on the client.
	net.world.objects[1].s.position[0] = 3.0f;
	net.step(10);
	EXPECT_NEAR(a.world.objects[1].s.position[0], 3.0f, 0.001f);
}

/** \} */
