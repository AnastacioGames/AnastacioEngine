/* LAN discovery: format, filters, rate limit and discovery on 127.0.0.1 (front H). */

#include "NET_ITransport.h"
#include "NET_LanDiscovery.h"
#include "NET_Socket.h"

#include "net_test_util.h"

#include "gtest/gtest.h"

#include <chrono>
#include <cstdio>
#include <functional>
#include <thread>

using namespace net;

namespace {

LanServerInfo sampleInfo(const std::string &gameId = "anastacio.test")
{
	LanServerInfo info;
	info.gameId = gameId;
	info.gameVersion = 7;
	info.name = "Sala do Fábio";
	info.sceneName = "Arena";
	info.players = 3;
	info.maxPlayers = 16;
	info.enetPort = 7777;
	info.webSocketPort = 7778;
	info.password = true;
	return info;
}

/// Runs both sides with the real clock until done() or timeoutMs.
void pumpUntil(LanResponder *a, LanResponder *b, LanDiscovery &client, const std::function<bool()> &done,
               uint64_t timeoutMs = 500)
{
	const uint64_t end = steadyClockMs() + timeoutMs;
	while (steadyClockMs() < end) {
		const uint64_t now = steadyClockMs();
		if (a) {
			a->update(now);
		}
		if (b) {
			b->update(now);
		}
		client.update(now);
		if (done()) {
			return;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(2));
	}
}

}  // namespace

TEST(NetLan, FormatRoundTrip)
{
	std::vector<uint8_t> packet;
	LanRequest req;
	req.nonce = 0xDEADBEEF;
	req.gameId = "anastacio.test";
	ASSERT_TRUE(encodeLanRequest(req, packet));
	EXPECT_EQ(packet[0], 'A');
	EXPECT_EQ(packet[3], 'N');
	LanRequest req2;
	ASSERT_TRUE(decodeLanRequest(packet.data(), packet.size(), req2));
	EXPECT_EQ(req2.nonce, req.nonce);
	EXPECT_EQ(req2.gameId, req.gameId);

	const LanServerInfo info = sampleInfo();
	ASSERT_TRUE(encodeLanResponse(42, info, packet));
	EXPECT_LE(packet.size(), kMaxLanPacket);
	uint32_t nonce = 0;
	LanServerInfo out;
	ASSERT_TRUE(decodeLanResponse(packet.data(), packet.size(), nonce, out));
	EXPECT_EQ(nonce, 42u);
	EXPECT_EQ(out.gameId, info.gameId);
	EXPECT_EQ(out.gameVersion, 7u);
	EXPECT_EQ(out.name, info.name);
	EXPECT_EQ(out.sceneName, "Arena");
	EXPECT_EQ(out.players, 3);
	EXPECT_EQ(out.maxPlayers, 16);
	EXPECT_EQ(out.enetPort, 7777);
	EXPECT_EQ(out.webSocketPort, 7778);
	EXPECT_TRUE(out.password);

	// A request is not a response and the other way around.
	EXPECT_FALSE(decodeLanRequest(packet.data(), packet.size(), req2));

	// Strings are limited to 64 bytes: the largest response stays far below 512.
	LanServerInfo big = info;
	big.name.assign(kMaxLanString + 1, 'n');
	EXPECT_FALSE(encodeLanResponse(1, big, packet));
	big.name.assign(kMaxLanString, 'n');
	big.gameId.assign(kMaxLanString, 'g');
	big.sceneName.assign(kMaxLanString, 's');
	ASSERT_TRUE(encodeLanResponse(1, big, packet));
	EXPECT_LE(packet.size(), kMaxLanPacket);
}

TEST(NetLan, TruncatedOrLyingPacketsAreRejected)
{
	std::vector<uint8_t> packet;
	ASSERT_TRUE(encodeLanResponse(9, sampleInfo(), packet));
	uint32_t nonce;
	LanServerInfo out;
	for (size_t n = 0; n < packet.size(); ++n) {
		EXPECT_FALSE(decodeLanResponse(packet.data(), n, nonce, out)) << n;
	}
	// String length larger than what is left.
	std::vector<uint8_t> lying = packet;
	lying[10] = 200;
	EXPECT_FALSE(decodeLanResponse(lying.data(), lying.size(), nonce, out));
	// String length above 64 even if the bytes are there.
	LanRequest req;
	req.gameId = "x";
	ASSERT_TRUE(encodeLanRequest(req, lying));
	lying[10] = 65;
	lying.resize(11 + 65, 'x');
	LanRequest reqOut;
	EXPECT_FALSE(decodeLanRequest(lying.data(), lying.size(), reqOut));
	// Trailing byte, unknown flag, wrong version, more than 512 bytes, null data.
	lying = packet;
	lying.push_back(0);
	EXPECT_FALSE(decodeLanResponse(lying.data(), lying.size(), nonce, out));
	lying = packet;
	lying.back() |= 0x80;
	EXPECT_FALSE(decodeLanResponse(lying.data(), lying.size(), nonce, out));
	lying = packet;
	lying[4] = 2;
	EXPECT_FALSE(decodeLanResponse(lying.data(), lying.size(), nonce, out));
	lying.assign(kMaxLanPacket + 1, 0);
	EXPECT_FALSE(decodeLanResponse(lying.data(), lying.size(), nonce, out));
	EXPECT_FALSE(decodeLanResponse(nullptr, 10, nonce, out));
}

TEST(NetLan, DiscoverOnLocalhost)
{
	LanResponder server;
	ASSERT_TRUE(server.start(0));
	ASSERT_TRUE(server.localPort() != 0);
	server.setInfo(sampleInfo());
	LanDiscovery client;
	ASSERT_TRUE(client.start());

	const auto found = [&] { return !client.servers().empty(); };
	// Broadcast when the system allows it, then unicast with the same API.
	const char *method = "none";
	for (const char *address : {"255.255.255.255", "127.255.255.255", "127.0.0.1"}) {
		if (client.request("anastacio.test", steadyClockMs(), server.localPort(), address)) {
			pumpUntil(&server, nullptr, client, found, 300);
		}
		if (found()) {
			method = address;
			break;
		}
	}
	std::printf("[          ] LAN discovery reached the server via %s\n", method);
	ASSERT_EQ(client.servers().size(), 1u);
	const LanServerEntry &e = client.servers()[0];
	EXPECT_EQ(e.info.name, "Sala do Fábio");
	EXPECT_EQ(e.info.players, 3);
	EXPECT_EQ(e.info.maxPlayers, 16);
	EXPECT_EQ(e.info.enetPort, 7777);
	EXPECT_TRUE(e.info.password);
	EXPECT_LT(e.pingMs, 300u);
	// The answer comes from the address of the interface the request arrived on.
	const std::string address = e.address;
	uint32_t ip = 0;
	EXPECT_TRUE(sock::parseIpv4(address, ip));

	// A second answer from the same address updates the entry; an old entry expires.
	ASSERT_TRUE(client.request("anastacio.test", steadyClockMs(), server.localPort(), address));
	const uint32_t before = client.stats().responses;
	pumpUntil(&server, nullptr, client, [&] { return client.stats().responses > before; });
	EXPECT_EQ(client.servers().size(), 1u);
	client.update(steadyClockMs() + 10000, 5000);
	EXPECT_TRUE(client.servers().empty());
}

TEST(NetLan, FiltersByGameId)
{
	LanResponder mine, other;
	ASSERT_TRUE(mine.start(0));
	ASSERT_TRUE(other.start(0));
	mine.setInfo(sampleInfo("game.a"));
	other.setInfo(sampleInfo("game.b"));
	LanDiscovery client;
	ASSERT_TRUE(client.start());
	ASSERT_TRUE(client.request("game.a", steadyClockMs(), mine.localPort(), "127.0.0.1"));
	ASSERT_TRUE(client.request("game.a", steadyClockMs(), other.localPort(), "127.0.0.1"));
	pumpUntil(&mine, &other, client, [&] { return other.stats().otherGame > 0 && !client.servers().empty(); });
	ASSERT_EQ(client.servers().size(), 1u);
	EXPECT_EQ(client.servers()[0].info.gameId, "game.a");
	EXPECT_EQ(other.stats().otherGame, 1u);
	EXPECT_EQ(other.stats().answered, 0u);

	// The client also drops answers of another game, even with a known nonce.
	sock::acquire();
	const sock::Handle s = sock::openUdp(0, false, false);
	ASSERT_TRUE(s != sock::kInvalid);
	std::vector<uint8_t> packet;
	ASSERT_TRUE(encodeLanResponse(0, sampleInfo("game.b"), packet));
	ASSERT_TRUE(sock::sendTo(s, 0x7F000001u, client.localPort(), packet.data(), packet.size()));
	const uint8_t garbage[3] = {1, 2, 3};
	ASSERT_TRUE(sock::sendTo(s, 0x7F000001u, client.localPort(), garbage, sizeof(garbage)));
	pumpUntil(nullptr, nullptr, client, [&] { return client.stats().otherGame > 0 && client.stats().invalid > 0; });
	EXPECT_EQ(client.stats().otherGame, 1u);
	EXPECT_EQ(client.stats().invalid, 1u);
	EXPECT_EQ(client.servers().size(), 1u);
	sock::close(s);
	sock::release();
}

TEST(NetLan, RateLimitPerAddressAndGarbage)
{
	LanResponderConfig config;
	config.requestsPerSecond = 2;
	LanResponder server(config);
	ASSERT_TRUE(server.start(0));
	server.setInfo(sampleInfo());
	LanDiscovery client;
	ASSERT_TRUE(client.start());
	for (int i = 0; i < 5; ++i) {
		ASSERT_TRUE(client.request("anastacio.test", 1000, server.localPort(), "127.0.0.1"));
	}
	// Garbage and a datagram above 512 bytes do not crash the responder.
	sock::acquire();
	const sock::Handle s = sock::openUdp(0, false, false);
	ASSERT_TRUE(s != sock::kInvalid);
	std::vector<uint8_t> big(1400, 0x41);
	ASSERT_TRUE(sock::sendTo(s, 0x7F000001u, server.localPort(), big.data(), big.size()));
	ASSERT_TRUE(sock::sendTo(s, 0x7F000001u, server.localPort(), big.data(), 7));

	const uint64_t end = steadyClockMs() + 500;
	while (server.stats().requests < 7 && steadyClockMs() < end) {
		server.update(1000);  // fixed time: no refill
		std::this_thread::sleep_for(std::chrono::milliseconds(2));
	}
	EXPECT_EQ(server.stats().requests, 7u);
	EXPECT_EQ(server.stats().answered, 2u);
	EXPECT_EQ(server.stats().rateLimited, 3u);
	EXPECT_EQ(server.stats().invalid, 2u);
	sock::close(s);
	sock::release();

	// One second later the address gets answers again.
	ASSERT_TRUE(client.request("anastacio.test", 2000, server.localPort(), "127.0.0.1"));
	const uint64_t end2 = steadyClockMs() + 500;
	while (server.stats().answered < 3 && steadyClockMs() < end2) {
		server.update(2000);
		std::this_thread::sleep_for(std::chrono::milliseconds(2));
	}
	EXPECT_EQ(server.stats().answered, 3u);
}

TEST(NetLanFuzz, Decode)
{
	net_test::Rng rng(0x1A4);
	std::vector<uint8_t> valid;
	ASSERT_TRUE(encodeLanResponse(5, sampleInfo(), valid));
	std::vector<uint8_t> validReq;
	LanRequest req;
	req.gameId = "anastacio.test";
	ASSERT_TRUE(encodeLanRequest(req, validReq));
	std::vector<uint8_t> data;
	int accepted = 0;
	for (int i = 0; i < 100000; ++i) {
		// Random bytes, or a valid packet with a few bytes changed and a random length.
		const std::vector<uint8_t> &base = (i & 2) ? valid : validReq;
		if (i & 1) {
			data = base;
			for (uint32_t k = rng.below(4); k-- > 0;) {
				data[rng.below(uint32_t(data.size()))] = uint8_t(rng.next());
			}
			data.resize(rng.below(uint32_t(base.size()) + 4), uint8_t(rng.next()));
		}
		else {
			data.resize(rng.below(600));
			for (uint8_t &b : data) {
				b = uint8_t(rng.next());
			}
		}
		uint32_t nonce;
		LanServerInfo info;
		LanRequest r;
		accepted += decodeLanResponse(data.data(), data.size(), nonce, info);
		accepted += decodeLanRequest(data.data(), data.size(), r);
		EXPECT_LE(info.name.size(), kMaxLanString);
	}
	EXPECT_GT(accepted, 0);
}
