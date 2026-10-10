/* WebSocket server transport tests (RFC 6455 handshake, framing, limits). */

#include "net_ws_test_client.h"

#include <gtest/gtest.h>

using namespace net;
using nettest::Frame;
using nettest::TestClient;
using Type = TransportEvent::Type;

namespace {

std::vector<uint8_t> bytes(const std::string &s)
{
	return std::vector<uint8_t>(s.begin(), s.end());
}

struct Server {
	std::unique_ptr<WebSocketServerTransport> t;
	std::vector<TransportEvent> events;

	explicit Server(const WebSocketServerSettings &s = WebSocketServerSettings(), int maxPeers = 8)
	    : t(createWebSocketServerTransport(s))
	{
		EXPECT_TRUE(t->listen(0, maxPeers));
		EXPECT_NE(t->boundPort(), 0);
	}

	bool waitFor(Type type, int count = 1, int timeoutMs = 2000)
	{
		return nettest::pumpUntil(
		    *t, events, [&] { return nettest::countEvents(events, type) >= count; }, timeoutMs);
	}
};

/* Connects and completes the handshake; returns the server PeerId. */
PeerId openClient(Server &srv, TestClient &cl)
{
	EXPECT_TRUE(cl.connectTo(srv.t->boundPort()));
	const std::string resp = cl.handshake();
	EXPECT_NE(resp.find(" 101 "), std::string::npos) << resp;
	EXPECT_TRUE(srv.waitFor(Type::Connected));
	const TransportEvent *e = nettest::findEvent(srv.events, Type::Connected);
	return e ? e->peer : 0;
}

} // namespace

TEST(NetWebSocket, Sha1Vectors)
{
	uint8_t d[20];
	ws::sha1(reinterpret_cast<const uint8_t *>("abc"), 3, d);
	EXPECT_EQ(ws::base64Encode(d, 20), "qZk+NkcGgWq6PiVxeFDCbJzQ2J0=");
	ws::sha1(nullptr, 0, d);
	EXPECT_EQ(ws::base64Encode(d, 20), "2jmj7l5rSw0yVb/vlWAYkK/YBwk=");
	const std::string big(1000, 'a');
	ws::sha1(reinterpret_cast<const uint8_t *>(big.data()), big.size(), d);
	EXPECT_EQ(ws::base64Encode(d, 20), "KRGBMFBT3HIOYvoeJxJ8h65XK3E=");
}

TEST(NetWebSocket, Base64Padding)
{
	EXPECT_EQ(ws::base64Encode(reinterpret_cast<const uint8_t *>("f"), 1), "Zg==");
	EXPECT_EQ(ws::base64Encode(reinterpret_cast<const uint8_t *>("fo"), 2), "Zm8=");
	EXPECT_EQ(ws::base64Encode(reinterpret_cast<const uint8_t *>("foo"), 3), "Zm9v");
}

TEST(NetWebSocket, AcceptKeyRfcExample)
{
	EXPECT_EQ(ws::computeAcceptKey("dGhlIHNhbXBsZSBub25jZQ=="), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=");
}

TEST(NetWebSocket, HandshakeAndBinaryRoundTrip)
{
	Server srv;
	TestClient cl(*srv.t, srv.events);
	ASSERT_TRUE(cl.connectTo(srv.t->boundPort()));
	const std::string resp = cl.handshake();
	EXPECT_EQ(resp.compare(0, 12, "HTTP/1.1 101"), 0) << resp;
	EXPECT_NE(resp.find("Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"), std::string::npos);
	ASSERT_TRUE(srv.waitFor(Type::Connected));
	const PeerId peer = nettest::findEvent(srv.events, Type::Connected)->peer;
	EXPECT_TRUE(srv.t->reliableAll());

	/* Client -> server: channel byte + body. */
	ASSERT_TRUE(cl.sendFrame(0x2, bytes(std::string("\x02") + "snap")));
	ASSERT_TRUE(srv.waitFor(Type::Received));
	const TransportEvent *r = nettest::findEvent(srv.events, Type::Received);
	EXPECT_EQ(r->peer, peer);
	EXPECT_EQ(r->channel, Channel::Snapshot);
	EXPECT_EQ(r->data, bytes("snap"));

	/* Server -> client: unmasked binary frame with channel prefix. */
	const std::vector<uint8_t> body = bytes("hello");
	srv.t->send(peer, Channel::Rpc, body.data(), body.size());
	Frame f;
	ASSERT_TRUE(cl.readFrameOf(0x2, f));
	EXPECT_TRUE(f.fin);
	EXPECT_FALSE(f.masked);
	EXPECT_EQ(f.payload, bytes(std::string("\x01") + "hello"));

	/* Empty body is valid (just the channel byte). */
	srv.t->send(peer, Channel::Input, nullptr, 0);
	ASSERT_TRUE(cl.readFrameOf(0x2, f));
	EXPECT_EQ(f.payload, std::vector<uint8_t>(1, 3));
}

TEST(NetWebSocket, HandshakeSplitAcrossWrites)
{
	Server srv;
	TestClient cl(*srv.t, srv.events);
	ASSERT_TRUE(cl.connectTo(srv.t->boundPort()));
	const std::string req = TestClient::request();
	ASSERT_TRUE(cl.sendRaw(req.substr(0, 20)));
	ASSERT_FALSE(srv.waitFor(Type::Connected, 1, 50));
	const std::string resp = cl.handshake(req.substr(20));
	EXPECT_NE(resp.find(" 101 "), std::string::npos);
	EXPECT_TRUE(srv.waitFor(Type::Connected));
}

TEST(NetWebSocket, BadHandshakeRejected)
{
	Server srv;
	TestClient cl(*srv.t, srv.events);
	ASSERT_TRUE(cl.connectTo(srv.t->boundPort()));
	const std::string resp = cl.handshake(
	    "GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
	    "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 8\r\n\r\n");
	EXPECT_EQ(resp.compare(0, 12, "HTTP/1.1 400"), 0) << resp;
	EXPECT_TRUE(cl.waitEof());
	EXPECT_EQ(nettest::countEvents(srv.events, Type::Connected), 0);
}

TEST(NetWebSocket, ServerFullGets503)
{
	Server srv(WebSocketServerSettings(), 1);
	TestClient a(*srv.t, srv.events), b(*srv.t, srv.events);
	openClient(srv, a);
	ASSERT_TRUE(b.connectTo(srv.t->boundPort()));
	const std::string resp = b.handshake();
	EXPECT_EQ(resp.compare(0, 12, "HTTP/1.1 503"), 0) << resp;
	EXPECT_EQ(nettest::countEvents(srv.events, Type::Connected), 1);
}

TEST(NetWebSocket, FragmentedMessageWithInterleavedPing)
{
	Server srv;
	TestClient cl(*srv.t, srv.events);
	openClient(srv, cl);

	ASSERT_TRUE(cl.sendFrame(0x2, bytes(std::string("\x01") + "ab"), false));
	ASSERT_TRUE(cl.sendFrame(0x9, bytes("pp")));
	Frame pong;
	ASSERT_TRUE(cl.readFrameOf(0xA, pong));
	EXPECT_EQ(pong.payload, bytes("pp"));
	EXPECT_EQ(nettest::countEvents(srv.events, Type::Received), 0);

	ASSERT_TRUE(cl.sendFrame(0x0, bytes("cd"), false));
	ASSERT_TRUE(cl.sendFrame(0x0, bytes("ef"), true));
	ASSERT_TRUE(srv.waitFor(Type::Received));
	const TransportEvent *r = nettest::findEvent(srv.events, Type::Received);
	EXPECT_EQ(r->channel, Channel::Rpc);
	EXPECT_EQ(r->data, bytes("abcdef"));
}

TEST(NetWebSocket, ExtendedLengthsAndMaxMessage)
{
	Server srv;
	TestClient cl(*srv.t, srv.events);
	const PeerId peer = openClient(srv, cl);

	/* 16-bit length. */
	std::vector<uint8_t> mid(1001, 0x5A);
	mid[0] = 0;
	ASSERT_TRUE(cl.sendFrame(0x2, mid));
	/* Exactly at the limit: channel + 65536 bytes needs the 64-bit length. */
	std::vector<uint8_t> max(ws::kMaxMessageSize + 1, 0xA5);
	max[0] = 1;
	ASSERT_TRUE(cl.sendFrame(0x2, max));
	ASSERT_TRUE(srv.waitFor(Type::Received, 2));
	EXPECT_EQ(srv.events[1].data.size(), 1000u);
	EXPECT_EQ(srv.events[2].data.size(), ws::kMaxMessageSize);
	EXPECT_EQ(srv.events[2].channel, Channel::Rpc);

	/* Server side: a max message goes out, an oversize one is dropped. */
	std::vector<uint8_t> out(ws::kMaxMessageSize, 7);
	srv.t->send(peer, Channel::Control, out.data(), out.size());
	std::vector<uint8_t> tooBig(ws::kMaxMessageSize + 1, 7);
	srv.t->send(peer, Channel::Control, tooBig.data(), tooBig.size());
	srv.t->send(peer, Channel::Control, out.data(), 3);
	Frame f;
	ASSERT_TRUE(cl.readFrameOf(0x2, f));
	EXPECT_EQ(f.payload.size(), ws::kMaxMessageSize + 1);
	ASSERT_TRUE(cl.readFrameOf(0x2, f));
	EXPECT_EQ(f.payload.size(), 4u);
}

TEST(NetWebSocket, OversizeFrameRejected)
{
	Server srv;
	TestClient cl(*srv.t, srv.events);
	openClient(srv, cl);

	/* Only the header is sent: the server must refuse before buffering the payload. */
	const std::vector<uint8_t> hdr =
	    TestClient::buildFrame(0x2, {}, true, true, uint64_t(ws::kMaxMessageSize) + 2);
	ASSERT_TRUE(cl.sendRaw(hdr.data(), hdr.size()));
	Frame close;
	ASSERT_TRUE(cl.readFrameOf(0x8, close));
	ASSERT_EQ(close.payload.size(), 2u);
	EXPECT_EQ((close.payload[0] << 8) | close.payload[1], 1009);
	EXPECT_TRUE(srv.waitFor(Type::Disconnected));
	EXPECT_EQ(nettest::countEvents(srv.events, Type::Received), 0);
}

TEST(NetWebSocket, OversizeFragmentedMessageRejected)
{
	Server srv;
	TestClient cl(*srv.t, srv.events);
	openClient(srv, cl);

	std::vector<uint8_t> half(ws::kMaxMessageSize / 2 + 10, 1);
	ASSERT_TRUE(cl.sendFrame(0x2, half, false));
	ASSERT_TRUE(cl.sendFrame(0x0, half, false));
	Frame close;
	ASSERT_TRUE(cl.readFrameOf(0x8, close));
	EXPECT_EQ((close.payload[0] << 8) | close.payload[1], 1009);
	EXPECT_TRUE(srv.waitFor(Type::Disconnected));
}

TEST(NetWebSocket, ProtocolErrors)
{
	struct Case {
		std::vector<uint8_t> frame;
		int code;
	};
	const std::vector<Case> cases = {
	    {TestClient::buildFrame(0x2, {0, 1}, true, false), 1002},          /* unmasked */
	    {TestClient::buildFrame(0x1, bytes("text")), 1003},                /* text frame */
	    {TestClient::buildFrame(0x2, {9, 1}), 1002},                       /* bad channel */
	    {TestClient::buildFrame(0x2, {}), 1002},                           /* no channel byte */
	    {TestClient::buildFrame(0x0, {0, 1}), 1002},                       /* stray continuation */
	    {TestClient::buildFrame(0x9, std::vector<uint8_t>(126, 0)), 1002}, /* big control */
	};
	for (const Case &c : cases) {
		Server srv;
		TestClient cl(*srv.t, srv.events);
		openClient(srv, cl);
		ASSERT_TRUE(cl.sendRaw(c.frame.data(), c.frame.size()));
		Frame close;
		ASSERT_TRUE(cl.readFrameOf(0x8, close));
		ASSERT_EQ(close.payload.size(), 2u);
		EXPECT_EQ((close.payload[0] << 8) | close.payload[1], c.code);
		EXPECT_TRUE(srv.waitFor(Type::Disconnected));
		EXPECT_EQ(nettest::countEvents(srv.events, Type::Received), 0);
	}
}

TEST(NetWebSocket, ClientCloseIsEchoed)
{
	Server srv;
	TestClient cl(*srv.t, srv.events);
	const PeerId peer = openClient(srv, cl);
	ASSERT_TRUE(cl.sendFrame(0x8, {0x03, 0xE8}));
	Frame close;
	ASSERT_TRUE(cl.readFrameOf(0x8, close));
	EXPECT_EQ(close.payload, std::vector<uint8_t>({0x03, 0xE8}));
	ASSERT_TRUE(srv.waitFor(Type::Disconnected));
	EXPECT_EQ(nettest::findEvent(srv.events, Type::Disconnected)->peer, peer);
	EXPECT_TRUE(cl.waitEof());
}

TEST(NetWebSocket, ServerDisconnectSendsClose)
{
	Server srv;
	TestClient cl(*srv.t, srv.events);
	const PeerId peer = openClient(srv, cl);
	srv.t->disconnect(peer);
	Frame close;
	ASSERT_TRUE(cl.readFrameOf(0x8, close));
	EXPECT_EQ((close.payload[0] << 8) | close.payload[1], 1000);
	EXPECT_TRUE(srv.waitFor(Type::Disconnected));
	EXPECT_EQ(nettest::countEvents(srv.events, Type::Disconnected), 1);
	/* Sends after disconnect are ignored. */
	srv.t->send(peer, Channel::Rpc, nullptr, 0);
	EXPECT_TRUE(cl.waitEof());
}

TEST(NetWebSocket, AbruptTcpCloseReported)
{
	Server srv;
	TestClient cl(*srv.t, srv.events);
	openClient(srv, cl);
	cl.closeSocket();
	EXPECT_TRUE(srv.waitFor(Type::Disconnected));
}

TEST(NetWebSocket, PingAndIdleTimeout)
{
	WebSocketServerSettings s;
	s.pingIntervalMs = 30;
	s.idleTimeoutMs = 300;
	Server srv(s);
	TestClient cl(*srv.t, srv.events);
	openClient(srv, cl);
	Frame ping;
	ASSERT_TRUE(cl.readFrameOf(0x9, ping));
	/* Not answering: the server gives up after idleTimeoutMs. */
	EXPECT_TRUE(srv.waitFor(Type::Disconnected, 1, 2000));
}

TEST(NetWebSocket, HandshakeTimeout)
{
	WebSocketServerSettings s;
	s.handshakeTimeoutMs = 50;
	Server srv(s);
	TestClient cl(*srv.t, srv.events);
	ASSERT_TRUE(cl.connectTo(srv.t->boundPort()));
	EXPECT_TRUE(cl.waitEof(2000));
	EXPECT_TRUE(srv.events.empty());
}

TEST(NetWebSocket, ClientRoleUnsupported)
{
	auto t = createWebSocketServerTransport();
	EXPECT_FALSE(t->connect("127.0.0.1", 1));
	std::vector<TransportEvent> ev;
	t->poll(ev); /* Not listening: no-op. */
	EXPECT_TRUE(ev.empty());
}

TEST(NetWebClient, StubOutsideEmscripten)
{
	auto t = createWebClientTransport();
	EXPECT_TRUE(t->reliableAll());
#ifndef __EMSCRIPTEN__
	EXPECT_FALSE(t->connect("127.0.0.1", 1));
	EXPECT_FALSE(t->listen(1, 1));
#endif
}
