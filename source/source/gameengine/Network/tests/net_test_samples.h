/* Fixed sample messages and snapshots shared by the message, fuzz and golden tests. */

#ifndef __NET_TEST_SAMPLES_H__
#define __NET_TEST_SAMPLES_H__

#include "NET_Messages.h"

#include <string>
#include <vector>

namespace net_test {

struct NamedPacket {
	std::string name;
	std::vector<uint8_t> data;
};

inline const std::vector<net::PropertyDesc> &sampleSchema()
{
	static const std::vector<net::PropertyDesc> schema = {
	    {net::PropKind::Bool, 0.0f, 0.0f, 0},
	    {net::PropKind::Int, 0.0f, 0.0f, 0},
	    {net::PropKind::Float, 0.0f, 100.0f, 10},
	    {net::PropKind::Float, 0.0f, 0.0f, 0},
	};
	return schema;
}

/// Objects with an id ending in 0x10 carry the sample property layout.
inline net::SnapshotConfig sampleConfig()
{
	net::SnapshotConfig config;
	config.schema = [](net::NetId id) -> const std::vector<net::PropertyDesc> * {
		return ((id & 0xFF) == 0x10) ? &sampleSchema() : nullptr;
	};
	return config;
}

inline net::ObjectState sampleObject(net::NetId id, float t)
{
	net::ObjectState o;
	o.id = id;
	o.hasTransform = true;
	o.position[0] = 1.5f + t;
	o.position[1] = -20.25f;
	o.position[2] = 3.0f * t;
	o.rotation[0] = 0.0f;
	o.rotation[1] = 0.38268343f;
	o.rotation[2] = 0.0f;
	o.rotation[3] = 0.92387953f;
	if (id % 2 == 0) {
		o.hasVelocity = true;
		o.velocity[0] = 4.0f;
		o.velocity[1] = -1.0f;
		o.velocity[2] = 0.25f * t;
		o.hasAngularVelocity = true;
		o.angularVelocity[2] = 1.5f;
	}
	if ((id & 0xFF) == 0x10) {
		o.props = {net::PropValue::makeBool(true), net::PropValue::makeInt(-42),
		           net::PropValue::makeFloat(37.5f), net::PropValue::makeFloat(0.125f + t)};
		o.hasAnim = true;
		o.anim.action = 3;
		o.anim.frame = 12.0f + t;
		o.anim.speed = 1.0f;
	}
	return o;
}

inline std::vector<net::ObjectState> sampleObjects(float t)
{
	return {sampleObject(1, t), sampleObject(2, t), sampleObject(0x110, t), sampleObject(0x80000001u, t)};
}

/// One packet per message type, each holding a single message.
inline std::vector<NamedPacket> sampleMessagePackets()
{
	using namespace net;
	std::vector<NamedPacket> packets;
	const SnapshotConfig config = sampleConfig();
	auto add = [&packets](const std::string &name, std::vector<uint8_t> data) {
		packets.push_back({name, std::move(data)});
	};

	{
		HelloMsg m;
		m.gameId = "anastacio.demo";
		m.gameVersion = 7;
		m.sceneHash = 0x0123456789ABCDEFull;
		m.playerName = "Jogador";
		m.token = 0xFEDCBA9876543210ull;
		m.password = "segredo";
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("hello", p);
	}
	{
		WelcomeMsg m;
		m.clientId = 3;
		m.tickRate = 60;
		m.snapshotRate = 20;
		m.serverTick = 123456;
		m.maxClients = 16;
		m.sceneName = "Arena";
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("welcome", p);
	}
	{
		RejectMsg m;
		m.reason = RejectReason::ServerFull;
		m.detail = "full";
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("reject", p);
	}
	{
		DisconnectMsg m;
		m.reason = DisconnectReason::Timeout;
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("disconnect", p);
	}
	{
		PingMsg m;
		m.seq = 9;
		m.senderTimeMs = 100000;
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("ping", p);
	}
	{
		PongMsg m;
		m.seq = 9;
		m.echoTimeMs = 100000;
		m.serverTick = 777;
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("pong", p);
	}
	{
		ClientInfoMsg m;
		m.clientId = 2;
		m.name = "Ana";
		m.flags = CLIENT_CONNECTED | CLIENT_READY;
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("client_info", p);
	}
	{
		SceneChangeMsg m;
		m.sceneName = "Arena";
		m.sceneHash = sceneHash("Arena", {5, 1, 9});
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("scene_change", p);
	}
	{
		SceneLoadedMsg m;
		m.sceneHash = sceneHash("Arena", {5, 1, 9});
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("scene_loaded", p);
	}
	{
		SpawnMsg m;
		m.netId = 0x80000010u;
		m.prototypeName = "Player";
		m.owner = 2;
		m.state = sampleObject(m.netId, 0.0f);
		std::vector<uint8_t> p;
		appendMessage(p, m, config);
		add("spawn", p);
	}
	{
		DespawnMsg m;
		m.netId = 0x80000010u;
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("despawn", p);
	}
	{
		OwnershipMsg m;
		m.netId = 0x80000010u;
		m.newOwner = 4;
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("ownership", p);
	}
	{
		std::vector<uint8_t> p;
		encodeSnapshotMessage(p, 100, sampleObjects(0.0f), nullptr, config);
		add("snapshot_full", p);
	}
	{
		Snapshot baseline;
		baseline.tick = 100;
		baseline.objects = sampleObjects(0.0f);
		std::vector<ObjectState> objects = sampleObjects(1.0f);
		// Object 1 unchanged, 2 removed.
		objects[0] = baseline.objects[0];
		objects.erase(objects.begin() + 1);
		std::vector<uint8_t> p;
		encodeSnapshotMessage(p, 103, objects, &baseline, config);
		add("snapshot_delta", p);
	}
	{
		SnapshotAckMsg m;
		m.tick = 100;
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("snapshot_ack", p);
	}
	{
		InputMsg m;
		m.newestTick = 500;
		m.blocks = {{1, 2, 3}, {}, std::vector<uint8_t>(64, 0xAB)};
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("input", p);
	}
	{
		RpcMsg m;
		m.netId = 7;
		m.rpcId = 12;
		m.tick = 501;
		RpcArg a;
		a.type = RpcArgType::Bool;
		a.b = true;
		m.args.push_back(a);
		a = RpcArg();
		a.type = RpcArgType::Int;
		a.i = -300;
		m.args.push_back(a);
		a = RpcArg();
		a.type = RpcArgType::Float;
		a.v[0] = 2.5f;
		m.args.push_back(a);
		a = RpcArg();
		a.type = RpcArgType::Vec3;
		a.v[0] = 1.0f;
		a.v[1] = 2.0f;
		a.v[2] = 3.0f;
		m.args.push_back(a);
		a = RpcArg();
		a.type = RpcArgType::Quat;
		a.v[3] = 1.0f;
		m.args.push_back(a);
		a = RpcArg();
		a.type = RpcArgType::Str;
		a.s = "boom";
		m.args.push_back(a);
		a = RpcArg();
		a.type = RpcArgType::NetId;
		a.id = 0x80000002u;
		m.args.push_back(a);
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("rpc", p);
	}
	{
		std::vector<uint8_t> p;
		appendMessage(p, FullStateRequestMsg());
		add("full_state_request", p);
	}
	{
		ChatMsg m;
		m.fromClient = 1;
		m.text = "ol\xc3\xa1";
		std::vector<uint8_t> p;
		appendMessage(p, m);
		add("chat", p);
	}
	return packets;
}

/// Decodes any message of a packet with the sample config; delta snapshots use the sample
/// baseline at tick 100. Returns false on the first invalid message.
inline bool decodeAnyPacket(const uint8_t *data, size_t size)
{
	using namespace net;
	const SnapshotConfig config = sampleConfig();
	Snapshot baseline;
	baseline.tick = 100;
	baseline.objects = sampleObjects(0.0f);

	PacketReader reader(data, size);
	RawMessage raw;
	while (reader.next(raw)) {
		bool ok = true;
		switch (MessageType(raw.type)) {
#define NET_CASE(TYPE, MSG) \
	case MessageType::TYPE: { \
		MSG m; \
		ok = decodeMessage(raw, m); \
		break; \
	}
			NET_CASE(Hello, HelloMsg)
			NET_CASE(Welcome, WelcomeMsg)
			NET_CASE(Reject, RejectMsg)
			NET_CASE(Disconnect, DisconnectMsg)
			NET_CASE(Ping, PingMsg)
			NET_CASE(Pong, PongMsg)
			NET_CASE(ClientInfo, ClientInfoMsg)
			NET_CASE(SceneChange, SceneChangeMsg)
			NET_CASE(SceneLoaded, SceneLoadedMsg)
			NET_CASE(Despawn, DespawnMsg)
			NET_CASE(Ownership, OwnershipMsg)
			NET_CASE(SnapshotAck, SnapshotAckMsg)
			NET_CASE(Input, InputMsg)
			NET_CASE(Rpc, RpcMsg)
			NET_CASE(FullStateRequest, FullStateRequestMsg)
			NET_CASE(Chat, ChatMsg)
#undef NET_CASE
			case MessageType::Spawn: {
				SpawnMsg m;
				ok = decodeMessage(raw, m, config);
				break;
			}
			case MessageType::Snapshot: {
				Snapshot s;
				ok = decodeSnapshotMessage(raw, &baseline, config, s);
				break;
			}
			default:
				// Unknown type: skipped using its length.
				break;
		}
		if (!ok) {
			return false;
		}
	}
	return reader.ok();
}

}  // namespace net_test

#endif  // __NET_TEST_SAMPLES_H__
