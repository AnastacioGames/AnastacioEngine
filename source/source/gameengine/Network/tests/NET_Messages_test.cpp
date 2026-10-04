/* Message encode/decode, framing, truncation and fuzz (contract section 10). */

#include "NET_Messages.h"

#include "net_test_samples.h"
#include "net_test_util.h"

#include "gtest/gtest.h"

using namespace net;

template <class Msg, class... Extra>
static Msg roundTrip(const Msg &in, const Extra &...extra)
{
	std::vector<uint8_t> packet;
	EXPECT_TRUE(appendMessage(packet, in, extra...));
	PacketReader reader(packet.data(), packet.size());
	RawMessage raw;
	EXPECT_TRUE(reader.next(raw));
	EXPECT_EQ(raw.type, uint8_t(Msg::kType));
	Msg out;
	EXPECT_TRUE(decodeMessage(raw, out, extra...));
	EXPECT_FALSE(reader.next(raw));
	EXPECT_TRUE(reader.ok());
	return out;
}

TEST(NetMessages, RoundTripControl)
{
	HelloMsg hello;
	hello.gameId = "game";
	hello.gameVersion = 3;
	hello.sceneHash = 0x1122334455667788ull;
	hello.playerName = "P1";
	hello.token = 42;
	const HelloMsg h = roundTrip(hello);
	EXPECT_EQ(h.protocolVersion, kProtocolVersion);
	EXPECT_EQ(h.gameId, "game");
	EXPECT_EQ(h.gameVersion, 3u);
	EXPECT_EQ(h.sceneHash, hello.sceneHash);
	EXPECT_EQ(h.playerName, "P1");
	EXPECT_EQ(h.token, 42u);

	WelcomeMsg welcome;
	welcome.clientId = 64;
	welcome.tickRate = 30;
	welcome.snapshotRate = 10;
	welcome.serverTick = 0xFFFFFFFFu;
	welcome.maxClients = 64;
	welcome.sceneName = "S";
	const WelcomeMsg w = roundTrip(welcome);
	EXPECT_EQ(w.clientId, 64);
	EXPECT_EQ(w.tickRate, 30);
	EXPECT_EQ(w.snapshotRate, 10);
	EXPECT_EQ(w.serverTick, 0xFFFFFFFFu);
	EXPECT_EQ(w.maxClients, 64);
	EXPECT_EQ(w.sceneName, "S");

	RejectMsg reject;
	reject.reason = RejectReason::GameInProgress;
	reject.detail = "late";
	EXPECT_EQ(roundTrip(reject).reason, RejectReason::GameInProgress);
	EXPECT_EQ(roundTrip(reject).detail, "late");

	DisconnectMsg disconnect;
	disconnect.reason = DisconnectReason::ServerShutdown;
	EXPECT_EQ(roundTrip(disconnect).reason, DisconnectReason::ServerShutdown);

	PingMsg ping;
	ping.seq = 1;
	ping.senderTimeMs = 2;
	EXPECT_EQ(roundTrip(ping).senderTimeMs, 2u);

	PongMsg pong;
	pong.seq = 1;
	pong.echoTimeMs = 2;
	pong.serverTick = 3;
	EXPECT_EQ(roundTrip(pong).serverTick, 3u);

	ClientInfoMsg info;
	info.clientId = 5;
	info.name = "N";
	info.flags = CLIENT_READY;
	EXPECT_EQ(roundTrip(info).flags, CLIENT_READY);

	SceneChangeMsg change;
	change.sceneName = "Level2";
	change.sceneHash = 99;
	EXPECT_EQ(roundTrip(change).sceneName, "Level2");

	SceneLoadedMsg loaded;
	loaded.sceneHash = 99;
	EXPECT_EQ(roundTrip(loaded).sceneHash, 99u);

	DespawnMsg despawn;
	despawn.netId = 0x80000005u;
	EXPECT_EQ(roundTrip(despawn).netId, 0x80000005u);

	OwnershipMsg own;
	own.netId = 8;
	own.newOwner = 0;
	EXPECT_EQ(roundTrip(own).netId, 8u);

	SnapshotAckMsg ack;
	ack.tick = 77;
	EXPECT_EQ(roundTrip(ack).tick, 77u);

	roundTrip(FullStateRequestMsg());

	ChatMsg chat;
	chat.fromClient = 3;
	chat.text = std::string(200, 'c');
	EXPECT_EQ(roundTrip(chat).text, chat.text);
}

TEST(NetMessages, RoundTripSpawn)
{
	const SnapshotConfig config = net_test::sampleConfig();
	SpawnMsg spawn;
	spawn.netId = 0x80000110u;
	spawn.prototypeName = "Crate";
	spawn.owner = 1;
	spawn.state = net_test::sampleObject(spawn.netId, 0.0f);
	const SpawnMsg s = roundTrip(spawn, config);
	EXPECT_EQ(s.netId, spawn.netId);
	EXPECT_EQ(s.state.id, spawn.netId);
	EXPECT_EQ(s.prototypeName, "Crate");
	EXPECT_TRUE(s.state.hasTransform);
	EXPECT_NEAR(s.state.position[0], 1.5f, 1e-3f);
	ASSERT_EQ(s.state.props.size(), 4u);
	EXPECT_EQ(s.state.props[1].i, -42);
	EXPECT_EQ(s.state.anim.action, 3u);

	SpawnMsg zero;
	std::vector<uint8_t> body;
	BitWriter w(body);
	EXPECT_FALSE(encode(w, zero, config));
}

TEST(NetMessages, RoundTripInputAndRpc)
{
	InputMsg input;
	input.newestTick = 10;
	input.blocks = {{1}, {2, 3}};
	const InputMsg in = roundTrip(input);
	EXPECT_EQ(in.newestTick, 10u);
	EXPECT_EQ(in.blocks, input.blocks);

	InputMsg empty;
	std::vector<uint8_t> body;
	BitWriter w(body);
	EXPECT_FALSE(encode(w, empty));

	InputMsg tooMany;
	tooMany.blocks.resize(9);
	std::vector<uint8_t> body2;
	BitWriter w2(body2);
	EXPECT_FALSE(encode(w2, tooMany));

	InputMsg tooBig;
	tooBig.blocks = {std::vector<uint8_t>(65)};
	std::vector<uint8_t> body3;
	BitWriter w3(body3);
	EXPECT_FALSE(encode(w3, tooBig));

	RpcMsg rpc;
	rpc.netId = 0;
	rpc.rpcId = 65535;
	rpc.tick = 9;
	RpcArg a;
	a.type = RpcArgType::Str;
	a.s = "abc";
	rpc.args.push_back(a);
	a = RpcArg();
	a.type = RpcArgType::Int;
	a.i = -5;
	rpc.args.push_back(a);
	const RpcMsg r = roundTrip(rpc);
	ASSERT_EQ(r.args.size(), 2u);
	EXPECT_EQ(r.args[0].s, "abc");
	EXPECT_EQ(r.args[1].i, -5);
	EXPECT_EQ(r.rpcId, 65535);

	// Arguments above 1024 bytes.
	RpcMsg big;
	a = RpcArg();
	a.type = RpcArgType::Str;
	a.s = std::string(255, 'x');
	big.args.assign(5, a);
	std::vector<uint8_t> body4;
	BitWriter w4(body4);
	EXPECT_FALSE(encode(w4, big));
}

TEST(NetMessages, ChatLimit)
{
	ChatMsg chat;
	chat.text = std::string(201, 'c');
	std::vector<uint8_t> body;
	BitWriter w(body);
	EXPECT_FALSE(encode(w, chat));

	// Hand made chat body with 201 bytes is rejected on decode.
	std::vector<uint8_t> raw = {1, 0, 201, 1};
	raw.resize(4 + 200, 'c');
	BitReader r(raw.data(), raw.size());
	ChatMsg out;
	EXPECT_FALSE(decode(r, out));
}

TEST(NetMessages, InvalidBodies)
{
	// Wrong magic.
	std::vector<uint8_t> packets;
	HelloMsg hello;
	std::vector<uint8_t> body;
	BitWriter w(body);
	encode(w, hello);
	body[0] ^= 1;
	BitReader r(body.data(), body.size());
	HelloMsg out;
	EXPECT_FALSE(decode(r, out));

	// Unknown reasons.
	const uint8_t badReject[2] = {0, 0};
	BitReader rr(badReject, sizeof(badReject));
	RejectMsg reject;
	EXPECT_FALSE(decode(rr, reject));
	const uint8_t badDisconnect[1] = {6};
	BitReader rd(badDisconnect, sizeof(badDisconnect));
	DisconnectMsg disconnect;
	EXPECT_FALSE(decode(rd, disconnect));

	// Trailing byte.
	const uint8_t trailing[5] = {1, 0, 0, 0, 0};
	BitReader rt(trailing, sizeof(trailing));
	SnapshotAckMsg ack;
	EXPECT_FALSE(decode(rt, ack));

	// Unknown rpc argument type.
	const uint8_t badRpc[] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 99};
	BitReader rp(badRpc, sizeof(badRpc));
	RpcMsg rpc;
	EXPECT_FALSE(decode(rp, rpc));

	// Wrong type for decodeMessage.
	RawMessage raw;
	raw.type = uint8_t(MessageType::Ping);
	EXPECT_FALSE(decodeMessage(raw, ack));
}

TEST(NetMessages, HeaderAndPacketFraming)
{
	std::vector<uint8_t> packet;
	PingMsg ping;
	ping.seq = 5;
	ASSERT_TRUE(appendMessage(packet, ping));
	// type, len (1 byte), 8 byte body.
	ASSERT_EQ(packet.size(), 10u);
	EXPECT_EQ(packet[0], uint8_t(MessageType::Ping));
	EXPECT_EQ(packet[1], 8);

	// Unknown type in the middle is skipped by its length.
	const uint8_t unknown[3] = {0xAA, 0xBB, 0xCC};
	ASSERT_TRUE(appendRawMessage(packet, 200, unknown, sizeof(unknown)));
	ASSERT_TRUE(appendMessage(packet, ping));

	PacketReader reader(packet.data(), packet.size());
	RawMessage raw;
	ASSERT_TRUE(reader.next(raw));
	EXPECT_EQ(raw.type, uint8_t(MessageType::Ping));
	ASSERT_TRUE(reader.next(raw));
	EXPECT_EQ(raw.type, 200);
	EXPECT_FALSE(isKnownMessageType(raw.type));
	EXPECT_EQ(raw.size, 3u);
	ASSERT_TRUE(reader.next(raw));
	PingMsg out;
	EXPECT_TRUE(decodeMessage(raw, out));
	EXPECT_EQ(out.seq, 5u);
	EXPECT_FALSE(reader.next(raw));
	EXPECT_TRUE(reader.ok());
	EXPECT_EQ(reader.count(), 3u);

	// Large reliable body uses a 3 byte length.
	std::vector<uint8_t> big(kMaxReliableMessage, 1);
	std::vector<uint8_t> bigPacket;
	ASSERT_TRUE(appendRawMessage(bigPacket, MessageType::Rpc, big));
	EXPECT_EQ(bigPacket.size(), big.size() + 4);
	big.push_back(1);
	EXPECT_FALSE(appendRawMessage(bigPacket, MessageType::Rpc, big));
}

TEST(NetMessages, LyingLength)
{
	std::vector<uint8_t> packet;
	PingMsg ping;
	appendMessage(packet, ping);
	// Length past the end of the packet.
	packet[1] = 9;
	PacketReader reader(packet.data(), packet.size());
	RawMessage raw;
	EXPECT_FALSE(reader.next(raw));
	EXPECT_FALSE(reader.ok());

	// Length shorter than the body: the body decode fails.
	packet[1] = 4;
	PacketReader reader2(packet.data(), packet.size());
	ASSERT_TRUE(reader2.next(raw));
	PingMsg out;
	EXPECT_FALSE(decodeMessage(raw, out));

	// Length varint above 3 bytes.
	const uint8_t longLen[] = {5, 0x80, 0x80, 0x80, 0x01};
	PacketReader reader3(longLen, sizeof(longLen));
	EXPECT_FALSE(reader3.next(raw));
	EXPECT_FALSE(reader3.ok());
}

TEST(NetMessages, TooManyMessages)
{
	std::vector<uint8_t> packet;
	for (int i = 0; i < 65; ++i) {
		appendMessage(packet, FullStateRequestMsg());
	}
	PacketReader reader(packet.data(), packet.size());
	RawMessage raw;
	int n = 0;
	while (reader.next(raw)) {
		++n;
	}
	EXPECT_EQ(n, 64);
	EXPECT_FALSE(reader.ok());
}

TEST(NetMessages, EverySampleDecodes)
{
	for (const net_test::NamedPacket &p : net_test::sampleMessagePackets()) {
		EXPECT_TRUE(net_test::decodeAnyPacket(p.data.data(), p.data.size())) << p.name;
	}
}

TEST(NetMessages, TruncatedAtEveryPosition)
{
	for (const net_test::NamedPacket &p : net_test::sampleMessagePackets()) {
		for (size_t len = 0; len < p.data.size(); ++len) {
			std::vector<uint8_t> cut(p.data.begin(), p.data.begin() + len);
			// Empty packet is valid (no messages); every other prefix must fail.
			if (len == 0) {
				EXPECT_TRUE(net_test::decodeAnyPacket(cut.data(), cut.size()));
				continue;
			}
			EXPECT_FALSE(net_test::decodeAnyPacket(cut.data(), cut.size())) << p.name << " len " << len;

			// Body cut with a consistent header: the body decode itself must fail.
			if (len > 2) {
				std::vector<uint8_t> body(p.data.begin() + 2, p.data.begin() + len);
				if (p.data[1] & 0x80) {
					continue;
				}
				std::vector<uint8_t> packet;
				appendRawMessage(packet, p.data[0], body.data(), body.size());
				EXPECT_FALSE(net_test::decodeAnyPacket(packet.data(), packet.size()))
				    << p.name << " body " << body.size();
			}
		}
	}
}

TEST(NetMessages, FuzzDecode)
{
	net_test::Rng rng(20261004);
	const std::vector<net_test::NamedPacket> samples = net_test::sampleMessagePackets();
	int accepted = 0;
	for (int n = 0; n < 100000; ++n) {
		std::vector<uint8_t> data;
		if (n % 2 == 0) {
			// Random bytes with a plausible header.
			const size_t size = rng.below(64);
			data.resize(size);
			for (uint8_t &b : data) {
				b = uint8_t(rng.next());
			}
			if (size > 2) {
				data[0] = uint8_t(1 + rng.below(19));
				data[1] = uint8_t(size - 2);
			}
		}
		else {
			// Mutated valid packet.
			data = samples[rng.below(uint32_t(samples.size()))].data;
			const int flips = 1 + int(rng.below(4));
			for (int f = 0; f < flips; ++f) {
				data[rng.below(uint32_t(data.size()))] ^= uint8_t(1u << rng.below(8));
			}
		}
		if (net_test::decodeAnyPacket(data.data(), data.size())) {
			++accepted;
		}
	}
	// Just has to finish without crashing or reading out of bounds (run under ASan to verify).
	SUCCEED() << accepted;
}
