/* RPC table, server checks and relay (front G). */

#include "NET_RPC.h"
#include "NET_Session.h"

#include "net_test_util.h"

#include "gtest/gtest.h"

#include <algorithm>
#include <map>
#include <memory>

using namespace net;

namespace {

const uint64_t kScene = 0x5EED;

struct Log {
	struct Entry {
		std::string name;
		ClientId caller;
		NetId netId;
		std::vector<RpcArg> args;
	};
	std::vector<Entry> calls;

	size_t count(const std::string &name) const
	{
		size_t n = 0;
		for (const Entry &e : calls) {
			n += e.name == name;
		}
		return n;
	}
};

RpcDesc desc(const std::string &name, RpcTarget target, bool requireOwner = false, bool reliable = true)
{
	RpcDesc d;
	d.name = name;
	d.target = target;
	d.requireOwner = requireOwner;
	d.reliable = reliable;
	return d;
}

/// The same RPCs, registered in the given order, logging to log.
void fillTable(RpcTable &table, Log &log, bool reversed)
{
	std::vector<RpcDesc> descs = {
	    desc("chat", RpcTarget::All),
	    desc("fire", RpcTarget::Server, true),
	    desc("hit", RpcTarget::Owner),
	    desc("jump", RpcTarget::Others),
	    desc("ping", RpcTarget::Server, false, false),
	    desc("say", RpcTarget::Server),
	};
	RpcDesc typed = desc("typed", RpcTarget::Server);
	typed.checkArgs = true;
	typed.argTypes = {RpcArgType::Int, RpcArgType::Str};
	descs.push_back(typed);
	if (reversed) {
		std::reverse(descs.begin(), descs.end());
	}
	for (RpcDesc &d : descs) {
		const std::string name = d.name;
		d.handler = [&log, name](const RpcCall &call) {
			log.calls.push_back({name, call.caller, call.netId, *call.args});
		};
		ASSERT_TRUE(table.add(d));
	}
	table.finalize();
}

RpcArg intArg(int64_t v)
{
	RpcArg a;
	a.type = RpcArgType::Int;
	a.i = v;
	return a;
}

RpcArg strArg(size_t length, char c = 'x')
{
	RpcArg a;
	a.type = RpcArgType::Str;
	a.s.assign(length, c);
	return a;
}

/// Server and two clients over loopback with a fake clock.
struct World {
	uint64_t now = 1000;
	Tick tick = 1;
	std::shared_ptr<LoopbackHub> hub = createLoopbackHub();
	std::unique_ptr<ITransport> serverTransport = createLoopbackTransport(hub);
	std::unique_ptr<ServerSession> server;
	RpcTable serverTable;
	Log serverLog;
	std::map<NetId, ClientId> serverOwners;
	std::unique_ptr<RpcServer> serverRpc;
	std::vector<SessionEvent> serverEvents;

	struct Client {
		std::unique_ptr<ITransport> transport;
		std::unique_ptr<ClientSession> session;
		RpcTable table;
		Log log;
		std::map<NetId, ClientId> owners;
		std::unique_ptr<RpcClient> rpc;
		bool disconnected = false;
	};
	Client clients[2];

	static RpcOwnerLookup lookup(std::map<NetId, ClientId> &owners)
	{
		return [&owners](NetId id, ClientId &owner) {
			const auto it = owners.find(id);
			if (it == owners.end()) {
				return false;
			}
			owner = it->second;
			return true;
		};
	}

	World()
	{
		ServerConfig sc;
		sc.gameId = "rpc";
		sc.sceneName = "Arena";
		sc.sceneHash = kScene;
		server = std::make_unique<ServerSession>(*serverTransport, sc);
		EXPECT_TRUE(server->start(7777));
		fillTable(serverTable, serverLog, false);
		serverRpc = std::make_unique<RpcServer>(*server, serverTable, lookup(serverOwners));
		for (int i = 0; i < 2; ++i) {
			Client &c = clients[i];
			c.transport = createLoopbackTransport(hub);
			ClientConfig cc;
			cc.gameId = "rpc";
			cc.playerName = "p" + std::to_string(i);
			cc.sceneHash = kScene;
			c.session = std::make_unique<ClientSession>(*c.transport, cc);
			fillTable(c.table, c.log, true);
			c.rpc = std::make_unique<RpcClient>(*c.session, c.table, lookup(c.owners));
			EXPECT_TRUE(c.session->connect("loopback", 7777, now));
			pump(5);
		}
		// Object 10 belongs to client 1, object 20 to client 2, object 30 to the server.
		for (std::map<NetId, ClientId> *owners : {&serverOwners, &clients[0].owners, &clients[1].owners}) {
			(*owners)[10] = clients[0].session->clientId();
			(*owners)[20] = clients[1].session->clientId();
			(*owners)[30] = kServerClientId;
		}
	}

	void pump(int steps = 4)
	{
		for (int s = 0; s < steps; ++s) {
			now += 10;
			serverEvents.clear();
			server->update(now, tick++, serverEvents);
			std::vector<SessionEvent> extra;
			for (const SessionEvent &e : serverEvents) {
				serverRpc->handleEvent(e, now, extra);
			}
			serverEvents.insert(serverEvents.end(), extra.begin(), extra.end());
			for (Client &c : clients) {
				if (!c.session) {
					continue;  // still being created
				}
				std::vector<SessionEvent> events;
				c.session->update(now, events);
				for (const SessionEvent &e : events) {
					c.rpc->handleEvent(e);
					if (e.type == SessionEvent::Type::Disconnected) {
						c.disconnected = true;
					}
				}
			}
		}
	}

	ClientId id(int i) const
	{
		return clients[i].session->clientId();
	}

	/// Sends an already encoded Rpc body from a client, bypassing RpcClient checks.
	void sendRaw(int client, const std::vector<uint8_t> &body)
	{
		std::vector<uint8_t> packet;
		ASSERT_TRUE(appendRawMessage(packet, MessageType::Rpc, body));
		clients[client].session->send(Channel::Rpc, packet);
	}

	std::vector<uint8_t> body(const std::string &name, NetId netId, const std::vector<RpcArg> &args = {})
	{
		RpcMsg msg;
		msg.rpcId = uint16_t(serverTable.idOf(name));
		msg.netId = netId;
		msg.args = args;
		std::vector<uint8_t> out;
		BitWriter w(out);
		EXPECT_TRUE(encode(w, msg));
		return out;
	}
};

}  // namespace

TEST(NetRpc, TableSortedTheSameOnBothSides)
{
	RpcTable a, b;
	Log la, lb;
	fillTable(a, la, false);
	fillTable(b, lb, true);
	ASSERT_EQ(a.size(), b.size());
	for (uint16_t id = 0; id < a.size(); ++id) {
		EXPECT_EQ(a.find(id)->name, b.find(id)->name);
	}
	EXPECT_EQ(a.idOf("chat"), 0);
	EXPECT_EQ(a.idOf("typed"), 6);
	EXPECT_EQ(a.idOf("nope"), -1);
	EXPECT_TRUE(a.find(uint16_t(7)) == nullptr);

	RpcTable c;
	EXPECT_TRUE(c.add(desc("b", RpcTarget::Server)));
	EXPECT_FALSE(c.add(desc("b", RpcTarget::All)));  // repeated name
	EXPECT_FALSE(c.add(desc("", RpcTarget::All)));
	EXPECT_TRUE(c.find(uint16_t(0)) == nullptr);  // not finalized
	EXPECT_EQ(c.idOf("b"), -1);
	c.finalize();
	EXPECT_FALSE(c.add(desc("a", RpcTarget::Server)));  // finalized
	EXPECT_EQ(c.idOf("b"), 0);
}

TEST(NetRpc, ServerTargetRunsOnServer)
{
	World w;
	ASSERT_TRUE(w.clients[0].rpc->call("say", 0, {intArg(5)}));
	ASSERT_TRUE(w.clients[0].rpc->call("ping", 0, {}));  // unreliable channel
	w.pump();
	ASSERT_EQ(w.serverLog.count("say"), 1u);
	EXPECT_EQ(w.serverLog.calls[0].caller, w.id(0));
	EXPECT_EQ(w.serverLog.calls[0].args[0].i, 5);
	EXPECT_EQ(w.serverLog.count("ping"), 1u);
	EXPECT_TRUE(w.clients[1].log.calls.empty());
}

TEST(NetRpc, OthersDoesNotReturnToTheCaller)
{
	World w;
	ASSERT_TRUE(w.clients[0].rpc->call("jump", 10, {}));
	w.pump();
	EXPECT_EQ(w.serverLog.count("jump"), 1u);
	EXPECT_EQ(w.clients[1].log.count("jump"), 1u);
	EXPECT_EQ(w.clients[0].log.count("jump"), 0u);
	EXPECT_EQ(w.serverRpc->stats().relayed, 1u);

	// All goes back to the caller too.
	ASSERT_TRUE(w.clients[1].rpc->call("chat", 0, {strArg(3)}));
	w.pump();
	EXPECT_EQ(w.serverLog.count("chat"), 1u);
	EXPECT_EQ(w.clients[0].log.count("chat"), 1u);
	EXPECT_EQ(w.clients[1].log.count("chat"), 1u);
	EXPECT_EQ(w.clients[0].log.calls.back().args[0].s, "xxx");
}

TEST(NetRpc, RelayCarriesTheCaller)
{
	World w;
	ASSERT_TRUE(w.clients[0].rpc->call("jump", 10, {}));
	ASSERT_TRUE(w.clients[1].rpc->call("chat", 0, {strArg(2)}));
	w.pump();
	ASSERT_EQ(w.clients[1].log.count("jump"), 1u);
	EXPECT_EQ(w.serverLog.calls[0].caller, w.id(0));
	for (const auto &e : w.clients[1].log.calls) {
		EXPECT_EQ(e.caller, e.name == "jump" ? w.id(0) : w.id(1));
	}
	ASSERT_EQ(w.clients[0].log.count("chat"), 1u);
	EXPECT_EQ(w.clients[0].log.calls.back().caller, w.id(1));

	// Calls made by the server still arrive with caller 0.
	ASSERT_TRUE(w.serverRpc->call("chat", 0, {strArg(1)}));
	w.pump();
	ASSERT_EQ(w.clients[0].log.count("chat"), 2u);
	EXPECT_EQ(w.clients[0].log.calls.back().caller, kServerClientId);
}

TEST(NetRpc, ClientCannotSendRpcFrom)
{
	World w;
	RpcFromMsg from;
	from.fromClient = w.id(1);
	from.rpc.rpcId = uint16_t(w.serverTable.idOf("say"));
	std::vector<uint8_t> packet;
	ASSERT_TRUE(appendMessage(packet, from));
	for (int i = 0; i < 10; ++i) {
		w.clients[0].session->send(Channel::Rpc, packet);
	}
	w.pump();
	EXPECT_EQ(w.serverLog.count("say"), 0u);
	EXPECT_TRUE(w.clients[0].disconnected);
}

TEST(NetRpc, RefusedByTargetAndOwner)
{
	World w;
	// Owner RPCs cannot be called by clients: refused locally...
	EXPECT_FALSE(w.clients[0].rpc->call("hit", 10, {}));
	EXPECT_EQ(w.clients[0].rpc->stats().refusedTarget, 1u);
	// ...and on the server, with a violation.
	w.sendRaw(0, w.body("hit", 10));
	// requireOwner on an object of the other client.
	EXPECT_FALSE(w.clients[0].rpc->call("fire", 20, {}));
	EXPECT_EQ(w.clients[0].rpc->stats().refusedOwner, 1u);
	w.sendRaw(0, w.body("fire", 20));
	w.sendRaw(0, w.body("fire", 0));  // requireOwner with no object
	// Wrong argument types.
	w.sendRaw(0, w.body("typed", 0, {strArg(1), intArg(1)}));
	// Unknown id.
	RpcMsg unknown;
	unknown.rpcId = 99;
	std::vector<uint8_t> body;
	BitWriter bw(body);
	ASSERT_TRUE(encode(bw, unknown));
	w.sendRaw(0, body);
	w.pump();

	const RpcStats &s = w.serverRpc->stats();
	EXPECT_EQ(s.refusedTarget, 1u);
	EXPECT_EQ(s.refusedOwner, 2u);
	EXPECT_EQ(s.refusedArgs, 1u);
	EXPECT_EQ(s.unknownId, 1u);
	EXPECT_TRUE(w.serverLog.calls.empty());
	EXPECT_TRUE(w.clients[1].log.calls.empty());

	// The owner may call it; correct arguments pass.
	ASSERT_TRUE(w.clients[0].rpc->call("fire", 10, {}));
	ASSERT_TRUE(w.clients[0].rpc->call("typed", 0, {intArg(1), strArg(2)}));
	EXPECT_FALSE(w.clients[0].rpc->call("typed", 0, {intArg(1)}));
	w.pump();
	EXPECT_EQ(w.serverLog.count("fire"), 1u);
	EXPECT_EQ(w.serverLog.count("typed"), 1u);

	// Violations add up on the session: 5 so far, 5 more disconnect the client.
	for (int i = 0; i < 5; ++i) {
		w.sendRaw(0, w.body("hit", 10));
	}
	w.pump(10);
	EXPECT_TRUE(w.clients[0].disconnected);
	EXPECT_FALSE(w.clients[1].disconnected);
}

TEST(NetRpc, ServerCallsOwnerAndAll)
{
	World w;
	ASSERT_TRUE(w.serverRpc->call("hit", 20, {intArg(3)}));
	ASSERT_TRUE(w.serverRpc->call("hit", 30, {}));  // owned by the server: runs here
	EXPECT_FALSE(w.serverRpc->call("hit", 0, {}));
	ASSERT_TRUE(w.serverRpc->call("chat", 0, {}));
	ASSERT_TRUE(w.serverRpc->call("jump", 0, {}));  // Others from the server: every client
	EXPECT_FALSE(w.serverRpc->call("typed", 0, {}));  // wrong arguments
	w.pump();
	EXPECT_EQ(w.clients[1].log.count("hit"), 1u);
	EXPECT_EQ(w.clients[0].log.count("hit"), 0u);
	EXPECT_EQ(w.serverLog.count("hit"), 1u);
	EXPECT_EQ(w.serverLog.count("chat"), 1u);
	EXPECT_EQ(w.serverLog.count("jump"), 0u);
	for (auto &c : w.clients) {
		EXPECT_EQ(c.log.count("chat"), 1u);
		EXPECT_EQ(c.log.count("jump"), 1u);
	}
	// A Server RPC sent to a client is not run there.
	ASSERT_TRUE(w.serverRpc->callClient(w.id(0), uint16_t(w.serverTable.idOf("say")), 0, {}));
	w.pump();
	EXPECT_EQ(w.clients[0].log.count("say"), 0u);
	EXPECT_EQ(w.clients[0].rpc->stats().refusedTarget, 1u);
}

TEST(NetRpc, ArgumentsAtTheLimit)
{
	World w;
	// count (1) + 3 strings of 255 (1 + 2 + 255 each) + one of 246 (1 + 2 + 246) = 1024 bytes.
	std::vector<RpcArg> args = {strArg(255, 'a'), strArg(255, 'b'), strArg(255, 'c'), strArg(246, 'd')};
	std::vector<uint8_t> packet;
	ASSERT_TRUE(makeRpcPacket(0, 0, 0, args, packet));
	ASSERT_TRUE(w.clients[0].rpc->call("say", 0, args));
	w.pump();
	ASSERT_EQ(w.serverLog.count("say"), 1u);
	EXPECT_EQ(w.serverLog.calls[0].args.size(), 4u);
	EXPECT_EQ(w.serverLog.calls[0].args[3].s, std::string(246, 'd'));

	// One byte more is refused by the encoder...
	args.back().s.push_back('d');
	EXPECT_FALSE(makeRpcPacket(0, 0, 0, args, packet));
	EXPECT_FALSE(w.clients[0].rpc->call("say", 0, args));

	// ...and by the server when written by hand.
	std::vector<uint8_t> body;
	BitWriter bw(body);
	bw.writeU32(0);
	bw.writeU16(uint16_t(w.serverTable.idOf("say")));
	bw.writeU32(0);
	bw.writeU8(uint8_t(args.size()));
	for (const RpcArg &a : args) {
		bw.writeU8(uint8_t(RpcArgType::Str));
		bw.writeString(a.s);
	}
	bw.alignToByte();
	ASSERT_EQ(body.size(), 10u + 1025u);
	w.sendRaw(0, body);
	w.pump();
	EXPECT_EQ(w.serverRpc->stats().invalid, 1u);
	EXPECT_EQ(w.serverLog.count("say"), 1u);
}

TEST(NetRpc, DespawnedObjectIsDropped)
{
	World w;
	// The server already despawned object 10; the client has not heard yet.
	w.serverOwners.erase(10);
	ASSERT_TRUE(w.clients[0].rpc->call("fire", 10, {}));
	w.pump();
	EXPECT_EQ(w.serverLog.count("fire"), 0u);
	EXPECT_EQ(w.serverRpc->stats().droppedNoObject, 1u);
	EXPECT_FALSE(w.clients[0].disconnected);
	EXPECT_FALSE(w.serverRpc->call("chat", 10, {}));

	// A client that already despawned 20 drops RPCs on it.
	w.clients[1].owners.erase(20);
	ASSERT_TRUE(w.serverRpc->call("hit", 20, {}));
	w.pump();
	EXPECT_EQ(w.clients[1].log.count("hit"), 0u);
	EXPECT_EQ(w.clients[1].rpc->stats().droppedNoObject, 1u);
}

TEST(NetRpc, SessionRateLimitStillApplies)
{
	World w;
	for (int i = 0; i < kMaxRpcPerSecond + 5; ++i) {
		ASSERT_TRUE(w.clients[0].rpc->call("say", 0, {intArg(i)}));
	}
	w.pump();
	EXPECT_EQ(w.serverLog.count("say"), size_t(kMaxRpcPerSecond));
	EXPECT_FALSE(w.clients[0].disconnected);
}

/* -------------------------------------------------------------------- */
/** \name Fuzz: Rpc bodies on both sides
 * \{ */

namespace {

void fuzzBody(net_test::Rng &rng, std::vector<uint8_t> &body, int i, size_t tableSize)
{
	body.resize(rng.below(64));
	for (uint8_t &b : body) {
		b = uint8_t(rng.next());
	}
	// Half of them get a known rpcId and a small argument count to reach the argument decoding.
	if ((i & 1) && body.size() >= 11) {
		body[4] = uint8_t(rng.below(uint32_t(tableSize) + 1));
		body[5] = 0;
		body[10] = uint8_t(rng.below(4));
	}
}

}  // namespace

TEST(NetRpcFuzz, ServerDecode)
{
	uint64_t now = 0;
	auto transport = createLoopbackTransport(createLoopbackHub());
	ServerSession session(*transport, ServerConfig());
	RpcTable table;
	Log log;
	fillTable(table, log, false);
	std::map<NetId, ClientId> owners;
	RpcServer server(session, table, World::lookup(owners));
	net_test::Rng rng(0xC0FFEE);
	SessionEvent e;
	e.type = SessionEvent::Type::Message;
	e.client = 1;
	e.messageType = uint8_t(MessageType::Rpc);
	std::vector<SessionEvent> events;
	for (int i = 0; i < 100000; ++i) {
		fuzzBody(rng, e.body, i, table.size());
		events.clear();
		EXPECT_TRUE(server.handleEvent(e, ++now, events));
	}
	EXPECT_EQ(server.stats().received, 100000u);
	EXPECT_GT(server.stats().invalid, 0u);
}

TEST(NetRpcFuzz, ClientDecode)
{
	auto transport = createLoopbackTransport(createLoopbackHub());
	ClientSession session(*transport, ClientConfig());
	RpcTable table;
	Log log;
	fillTable(table, log, false);
	std::map<NetId, ClientId> owners;
	RpcClient client(session, table, World::lookup(owners));
	net_test::Rng rng(0xBEEF);
	SessionEvent e;
	e.type = SessionEvent::Type::Message;
	e.messageType = uint8_t(MessageType::Rpc);
	for (int i = 0; i < 100000; ++i) {
		// Half as relayed calls, with a leading caller id.
		e.messageType = uint8_t((i & 2) ? MessageType::RpcFrom : MessageType::Rpc);
		fuzzBody(rng, e.body, i, table.size());
		EXPECT_TRUE(client.handleEvent(e));
	}
	EXPECT_EQ(client.stats().received, 100000u);
	EXPECT_GT(client.stats().invalid, 0u);
}

/** \} */
