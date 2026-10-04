/* Prediction, server input queues, lag compensation and clock (front F). */

#include "NET_Clock.h"
#include "NET_LagCompensation.h"
#include "NET_Prediction.h"
#include "NET_Session.h"

#include "net_test_util.h"

#include "gtest/gtest.h"

#include <cmath>
#include <memory>

using namespace net;

namespace {

const uint64_t kScene = 0xF00D;

InputBlock block(uint8_t a, uint8_t b = 0)
{
	return InputBlock{a, b};
}

/* -------------------------------------------------------------------- */
/** \name Simple character: velocity from input, position integrated
 * \{ */

struct Character {
	float position[3] = {0.0f, 0.0f, 0.0f};
	float velocity[3] = {0.0f, 0.0f, 0.0f};

	static constexpr float kSpeed = 5.0f;

	void step(const InputBlock &input, float dt)
	{
		const float mx = input.size() > 0 ? float(int8_t(input[0])) / 127.0f : 0.0f;
		const float my = input.size() > 1 ? float(int8_t(input[1])) / 127.0f : 0.0f;
		velocity[0] = mx * kSpeed;
		velocity[1] = my * kSpeed;
		velocity[2] = 0.0f;
		for (int i = 0; i < 3; ++i) {
			position[i] += velocity[i] * dt;
		}
	}

	ObjectState state() const
	{
		ObjectState s;
		s.id = 1;
		s.hasTransform = true;
		std::copy(position, position + 3, s.position);
		s.hasVelocity = true;
		std::copy(velocity, velocity + 3, s.velocity);
		return s;
	}

	void set(const ObjectState &s)
	{
		std::copy(s.position, s.position + 3, position);
		if (s.hasVelocity) {
			std::copy(s.velocity, s.velocity + 3, velocity);
		}
	}
};

float dist(const float a[3], const float b[3])
{
	return std::sqrt((a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1]) + (a[2] - b[2]) * (a[2] - b[2]));
}

/// Scripted input: a few direction changes, then stop.
InputBlock scriptedInput(uint32_t frame)
{
	const uint32_t phase = frame / 40;
	switch (phase % 5) {
		case 0:
			return block(127, 0);
		case 1:
			return block(0, 127);
		case 2:
			return block(uint8_t(-90), 90);
		case 3:
			return block(uint8_t(-127), uint8_t(-60));
		default:
			return block(0, 0);
	}
}

/** \} */

}  // namespace

/* -------------------------------------------------------------------- */
/** \name Server input queue
 * \{ */

TEST(NetPrediction, ClientSendsLastEightBlocksNewestFirst)
{
	PredictionClient client(PredictionCallbacks{});
	InputMsg msg;
	for (Tick t = 10; t < 20; ++t) {
		ASSERT_TRUE(client.recordInput(t, block(uint8_t(t)), msg));
	}
	EXPECT_EQ(msg.newestTick, 19u);
	ASSERT_EQ(msg.blocks.size(), size_t(kMaxInputBlocks));
	for (size_t i = 0; i < msg.blocks.size(); ++i) {
		EXPECT_EQ(msg.blocks[i][0], uint8_t(19 - i));
	}
	// A gap restarts the redundancy window.
	ASSERT_TRUE(client.recordInput(25, block(25), msg));
	EXPECT_EQ(msg.blocks.size(), 1u);
	// Too large blocks are refused.
	EXPECT_FALSE(client.recordInput(26, InputBlock(kMaxInputBlockBytes + 1), msg));
}

TEST(NetPrediction, QueueAppliesEachTickOnceInOrder)
{
	InputQueue q;
	InputMsg msg;
	msg.newestTick = 12;
	for (int i = 0; i < 3; ++i) {
		msg.blocks.push_back(block(uint8_t(12 - i)));  // 12, 11, 10
	}
	q.receive(msg, 10);
	q.receive(msg, 10);  // redundant copy
	EXPECT_EQ(q.stats().received, 3u);
	EXPECT_EQ(q.stats().duplicates, 3u);

	InputBlock out;
	for (Tick t = 10; t <= 12; ++t) {
		ASSERT_TRUE(q.consume(t, out));
		EXPECT_EQ(out[0], uint8_t(t));
	}
	// Already applied ticks are dropped.
	q.receive(msg, 13);
	EXPECT_EQ(q.stats().duplicates, 6u);
	EXPECT_EQ(q.pending(), 0u);
	// Consuming the same tick twice is refused.
	EXPECT_FALSE(q.consume(12, out));
}

TEST(NetPrediction, QueueRepeatsLastInputThenStops)
{
	InputQueueConfig config;
	config.maxRepeatTicks = 3;
	InputQueue q(config);
	InputMsg msg;
	msg.newestTick = 5;
	msg.blocks = {block(7)};
	q.receive(msg, 5);

	InputBlock out;
	bool repeated = false;
	ASSERT_TRUE(q.consume(5, out, &repeated));
	EXPECT_FALSE(repeated);
	for (Tick t = 6; t <= 8; ++t) {
		ASSERT_TRUE(q.consume(t, out, &repeated));
		EXPECT_TRUE(repeated);
		EXPECT_EQ(out[0], 7);
	}
	EXPECT_FALSE(q.consume(9, out, &repeated));
	EXPECT_EQ(q.stats().repeated, 3u);
	EXPECT_EQ(q.stats().missing, 1u);

	// Inputs of 6..9 arriving now are late, counted once per tick.
	msg.newestTick = 10;
	msg.blocks = {block(10), block(9), block(8), block(7), block(6)};
	q.receive(msg, 10);
	q.receive(msg, 10);
	EXPECT_EQ(q.stats().late, 4u);
	ASSERT_TRUE(q.consume(10, out, &repeated));
	EXPECT_FALSE(repeated);
	EXPECT_EQ(out[0], 10);
}

TEST(NetPrediction, QueueDropsInputsTooFarAhead)
{
	InputQueueConfig config;
	config.maxAheadTicks = 10;
	InputQueue q(config);
	InputMsg msg;
	msg.newestTick = 1000;
	msg.blocks = {block(1)};
	q.receive(msg, 5);
	EXPECT_EQ(q.stats().tooFar, 1u);
	EXPECT_EQ(q.pending(), 0u);
	// Ticks the server already simulated are never stored, even before the first consume.
	msg.newestTick = 3;
	msg.blocks = {block(3), block(2)};
	q.receive(msg, 100);
	EXPECT_EQ(q.stats().late, 2u);
	EXPECT_EQ(q.pending(), 0u);
}

TEST(NetPrediction, QueueMeasuresSlack)
{
	InputQueue q;
	float slack;
	EXPECT_FALSE(q.slack(slack));
	InputMsg msg;
	msg.newestTick = 105;
	msg.blocks = {block(1)};
	q.receive(msg, 100);
	ASSERT_TRUE(q.slack(slack));
	EXPECT_FLOAT_EQ(slack, 5.0f);
	// Smoothed: a late input pulls the average down a tenth of the way.
	msg.newestTick = 95;
	q.receive(msg, 100);
	ASSERT_TRUE(q.slack(slack));
	EXPECT_FLOAT_EQ(slack, 4.0f);
}

TEST(NetPrediction, ServerRoutesSessionEvents)
{
	PredictionServer server;
	SessionEvent joined;
	joined.type = SessionEvent::Type::ClientJoined;
	joined.client = 3;
	EXPECT_FALSE(server.handleEvent(joined, 1));
	EXPECT_TRUE(server.queue(3) != nullptr);

	InputMsg msg;
	msg.newestTick = 2;
	msg.blocks = {block(4)};
	SessionEvent input;
	input.type = SessionEvent::Type::Message;
	input.client = 3;
	input.messageType = uint8_t(MessageType::Input);
	BitWriter w(input.body);
	ASSERT_TRUE(encode(w, msg));
	EXPECT_TRUE(server.handleEvent(input, 1));

	InputBlock out;
	EXPECT_TRUE(server.consume(3, 2, out));
	EXPECT_EQ(out[0], 4);

	input.body = {0xFF};
	EXPECT_TRUE(server.handleEvent(input, 3));
	EXPECT_EQ(server.queue(3)->stats().invalid, 1u);

	SessionEvent left;
	left.type = SessionEvent::Type::ClientLeft;
	left.client = 3;
	server.handleEvent(left, 3);
	EXPECT_TRUE(server.queue(3) == nullptr);
	EXPECT_FALSE(server.consume(3, 3, out));
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Prediction and reconciliation
 * \{ */

TEST(NetPrediction, ReconcileReplaysAndSmooths)
{
	Character ch;
	PredictionCallbacks cb;
	const float dt = 0.02f;
	cb.setState = [&](const ObjectState &s) { ch.set(s); };
	cb.replay = [&](Tick, const InputBlock &in) { ch.step(in, dt); };
	cb.getState = [&](ObjectState &s) {
		s = ch.state();
		return true;
	};
	PredictionConfig config;
	config.smoothingMs = 100.0f;
	PredictionClient pred(cb, config);

	InputMsg msg;
	for (Tick t = 1; t <= 10; ++t) {
		pred.recordInput(t, block(127), msg);
		ch.step(block(127), dt);
		pred.recordState(t, ch.state());
	}
	// Matching server state: nothing happens.
	Character server;
	for (int i = 0; i < 4; ++i) {
		server.step(block(127), dt);
	}
	EXPECT_FALSE(pred.reconcile(4, server.state()));

	// The server was pushed 0.5 m sideways at tick 6.
	for (int i = 0; i < 2; ++i) {
		server.step(block(127), dt);
	}
	server.position[1] += 0.5f;
	const float before = ch.position[1];
	EXPECT_TRUE(pred.reconcile(6, server.state()));
	EXPECT_NEAR(ch.position[1], before + 0.5f, 1e-4f);
	float offset[3];
	pred.visualOffset(offset);
	EXPECT_NEAR(offset[1], -0.5f, 1e-4f);  // the rendered position has not jumped yet
	pred.update(100.0f);
	pred.visualOffset(offset);
	EXPECT_NEAR(offset[1], -0.5f * std::exp(-1.0f), 1e-3f);
	for (int i = 0; i < 20; ++i) {
		pred.update(50.0f);
	}
	pred.visualOffset(offset);
	EXPECT_EQ(offset[1], 0.0f);

	// A correction past the limit teleports.
	server.position[0] += 10.0f;
	EXPECT_TRUE(pred.reconcile(7, [&] {
		Character s = server;
		s.step(block(127), dt);
		return s.state();
	}()));
	pred.visualOffset(offset);
	EXPECT_EQ(offset[0], 0.0f);
	EXPECT_EQ(pred.stats().teleports, 1u);
}

/// Character predicted over the simulated network: 150 ms round trip and 2% loss.
TEST(NetPrediction, CharacterOverLossyNetwork)
{
	uint64_t now = 1000;
	const uint16_t tickRate = 50;
	const uint64_t tickMs = 1000 / tickRate;
	const float dt = 1.0f / float(tickRate);

	NetSimSettings sim;
	sim.latencyMs = 75;
	sim.lossPercent = 2.0f;
	sim.clock = [&now] { return now; };
	auto hub = createLoopbackHub();
	sim.seed = 11;
	auto serverTransport = createSimulatedTransport(createLoopbackTransport(hub), sim);
	sim.seed = 12;
	auto clientTransport = createSimulatedTransport(createLoopbackTransport(hub), sim);

	ServerConfig sc;
	sc.gameId = "pred";
	sc.sceneName = "Arena";
	sc.sceneHash = kScene;
	sc.tickRate = tickRate;
	sc.snapshotRate = tickRate / 2;
	ServerSession server(*serverTransport, sc);
	ASSERT_TRUE(server.start(7777));

	ClientConfig cc;
	cc.gameId = "pred";
	cc.playerName = "p";
	cc.sceneHash = kScene;
	cc.pingIntervalMs = 200;
	ClientSession client(*clientTransport, cc);
	ASSERT_TRUE(client.connect("loopback", 7777, now));

	SnapshotConfig snapConfig;
	PredictionServer predServer;
	Character serverChar;

	Character clientChar;
	PredictionCallbacks cb;
	cb.setState = [&](const ObjectState &s) { clientChar.set(s); };
	cb.replay = [&](Tick, const InputBlock &in) { clientChar.step(in, dt); };
	cb.getState = [&](ObjectState &s) {
		s = clientChar.state();
		return true;
	};
	PredictionClient pred(cb);
	ClockConfig clockConfig;
	clockConfig.tickRate = tickRate;
	clockConfig.snapshotRate = tickRate / 2;
	NetClock clock(clockConfig);

	ClientId clientId = 0;
	Tick clientTick = kNoTick;
	uint32_t pongCount = 0;
	uint32_t frame = 0;
	float rendered[3] = {0.0f, 0.0f, 0.0f};
	bool hasRendered = false;
	float maxStep = 0.0f;
	std::vector<SessionEvent> events;

	for (Tick tick = 1; tick <= 600; ++tick) {
		now += tickMs;

		// Server: receive, apply this tick's input, send the state every other tick.
		events.clear();
		server.update(now, tick, events);
		for (const SessionEvent &e : events) {
			if (e.type == SessionEvent::Type::ClientJoined) {
				clientId = e.client;
			}
			predServer.handleEvent(e, tick);
		}
		if (clientId != 0) {
			InputBlock in;
			if (tick == 300) {
				// Knockback the client cannot predict: forces a smoothed correction.
				serverChar.position[1] += 0.3f;
			}
			if (predServer.consume(clientId, tick, in)) {
				serverChar.step(in, dt);
			}
			else {
				serverChar.step(block(0), dt);
			}
			if (tick % 2 == 0) {
				ObjectState s = serverChar.state();
				std::vector<uint8_t> packet;
				ASSERT_TRUE(encodeSnapshotMessage(packet, tick, {s}, nullptr, snapConfig));
				server.send(clientId, Channel::Snapshot, packet);
			}
		}

		// Client.
		events.clear();
		client.update(now, events);
		if (client.lastPong().count != pongCount) {
			pongCount = client.lastPong().count;
			clock.addPong(client.lastPong().rttMs, client.lastPong().serverTick, now);
		}
		for (const SessionEvent &e : events) {
			if (e.type != SessionEvent::Type::Message || e.messageType != uint8_t(MessageType::Snapshot)) {
				continue;
			}
			RawMessage raw{e.messageType, e.body.data(), e.body.size()};
			Snapshot snap;
			if (decodeSnapshotMessage(raw, nullptr, snapConfig, snap)) {
				clock.addSnapshot(snap.tick, now);
				const ObjectState *s = snap.find(1);
				ASSERT_TRUE(s != nullptr);
				pred.reconcile(snap.tick, *s);
			}
		}
		if (client.state() != ClientSession::State::Connected || !clock.synced()) {
			continue;
		}
		clientTick = clientTick == kNoTick ? clock.predictionTick(now) : clientTick + 1;
		const InputBlock in = frame < 400 ? scriptedInput(frame) : block(0);
		++frame;
		InputMsg msg;
		ASSERT_TRUE(pred.recordInput(clientTick, in, msg));
		client.send(Channel::Input, makePacket(msg));
		clientChar.step(in, dt);
		pred.recordState(clientTick, clientChar.state());
		pred.update(float(tickMs));

		float offset[3];
		pred.visualOffset(offset);
		float r[3];
		for (int i = 0; i < 3; ++i) {
			r[i] = clientChar.position[i] + offset[i];
		}
		if (hasRendered) {
			maxStep = std::max(maxStep, dist(r, rendered));
		}
		std::copy(r, r + 3, rendered);
		hasRendered = true;
	}

	ASSERT_TRUE(clientId != 0);
	const InputQueueStats &qs = predServer.queue(clientId)->stats();
	EXPECT_GT(qs.applied, 350u);
	EXPECT_GE(pred.stats().corrections, 1u);
	EXPECT_EQ(pred.stats().teleports, 0u);
	// One frame moves 0.1 m at full speed; the 0.3 m correction is spread over several frames.
	EXPECT_LT(maxStep, Character::kSpeed * dt + 0.06f);
	// Both stopped: the rendered position matches the server within 1 cm.
	EXPECT_LT(dist(rendered, serverChar.position), 0.01f);
	EXPECT_LT(dist(clientChar.position, serverChar.position), 0.01f);
	EXPECT_GT(dist(serverChar.position, Character().position), 1.0f);
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Lag compensation
 * \{ */

TEST(NetLagCompensation, Shapes)
{
	const float down[3] = {0.0f, 0.0f, -1.0f};
	float t = 0.0f;

	Hitbox sphere;
	sphere.radius = 0.5f;
	const float above[3] = {0.0f, 0.0f, 3.0f};
	ASSERT_TRUE(rayHitbox(above, down, 10.0f, sphere, t));
	EXPECT_NEAR(t, 2.5f, 1e-5f);
	EXPECT_FALSE(rayHitbox(above, down, 2.0f, sphere, t));  // too short
	const float inside[3] = {0.1f, 0.0f, 0.0f};
	ASSERT_TRUE(rayHitbox(inside, down, 1.0f, sphere, t));
	EXPECT_EQ(t, 0.0f);
	const float up[3] = {0.0f, 0.0f, 1.0f};
	EXPECT_FALSE(rayHitbox(above, up, 10.0f, sphere, t));  // behind the origin

	// Capsule lying along Y (90 degrees around X): radius 0.3, segment +-0.8.
	Hitbox capsule;
	capsule.shape = HitShape::Capsule;
	capsule.radius = 0.3f;
	capsule.halfHeight = 0.8f;
	const float s = std::sqrt(0.5f);
	const float rotX[4] = {s, 0.0f, 0.0f, s};
	std::copy(rotX, rotX + 4, capsule.rotation);
	const float onSegment[3] = {0.0f, 0.7f, 3.0f};
	ASSERT_TRUE(rayHitbox(onSegment, down, 10.0f, capsule, t));
	EXPECT_NEAR(t, 2.7f, 1e-4f);
	const float onCap[3] = {0.0f, 1.0f, 3.0f};
	ASSERT_TRUE(rayHitbox(onCap, down, 10.0f, capsule, t));
	EXPECT_GT(t, 2.7f);
	const float past[3] = {0.0f, 1.2f, 3.0f};
	EXPECT_FALSE(rayHitbox(past, down, 10.0f, capsule, t));

	// Box turned 45 degrees around Z: its corner reaches 0.707 on Y.
	Hitbox box;
	box.shape = HitShape::Box;
	const float sz = std::sin(3.14159265f / 8.0f), cz = std::cos(3.14159265f / 8.0f);
	const float rotZ[4] = {0.0f, 0.0f, sz, cz};
	std::copy(rotZ, rotZ + 4, box.rotation);
	const float side[3] = {-5.0f, 0.65f, 0.0f};
	const float right[3] = {1.0f, 0.0f, 0.0f};
	ASSERT_TRUE(rayHitbox(side, right, 10.0f, box, t));
	box.rotation[2] = 0.0f;
	box.rotation[3] = 1.0f;
	EXPECT_FALSE(rayHitbox(side, right, 10.0f, box, t));
}

TEST(NetLagCompensation, HitsWhereTheClientSawTheTarget)
{
	LagCompensationConfig config;
	config.tickRate = 50;
	config.maxRewindMs = 400;  // 20 ticks
	LagCompensation lag(config);
	// Target moves 0.2 m per tick along X.
	for (Tick t = 1; t <= 60; ++t) {
		Hitbox h;
		h.id = 42;
		h.radius = 0.3f;
		h.center[0] = 0.2f * float(t);
		lag.record(t, {h});
	}
	EXPECT_EQ(lag.newestTick(), 60u);
	EXPECT_EQ(lag.oldestTick(), 9u);  // 1 s of history at 50 Hz, plus one

	// The client rendered tick 45 + 0.5: the target was at x = 9.1.
	const float origin[3] = {9.1f, -10.0f, 0.0f};
	const float dir[3] = {0.0f, 1.0f, 0.0f};
	RayHit hit;
	ASSERT_TRUE(lag.raycast(origin, dir, 100.0f, 45, 0.5f, 60, hit));
	EXPECT_EQ(hit.id, 42u);
	EXPECT_NEAR(hit.distance, 9.7f, 1e-3f);
	EXPECT_EQ(hit.tick, 45u);

	// Without rewinding the shot misses (the target is at x = 12 now).
	EXPECT_FALSE(lag.raycast(origin, dir, 100.0f, 60, 0.0f, 60, hit));
	// The shooter's own object is ignored.
	EXPECT_FALSE(lag.raycast(origin, dir, 100.0f, 45, 0.5f, 60, hit, 42));

	// Rewinding further than maxRewind is clamped: aiming at tick 30 tests tick 40.
	const float old[3] = {6.0f, -10.0f, 0.0f};
	EXPECT_FALSE(lag.raycast(old, dir, 100.0f, 30, 0.0f, 60, hit));
	const float clamped[3] = {8.0f, -10.0f, 0.0f};
	ASSERT_TRUE(lag.raycast(clamped, dir, 100.0f, 30, 0.0f, 60, hit));
	EXPECT_EQ(hit.tick, 40u);
}

TEST(NetLagCompensation, InterpolatesAndHandlesGaps)
{
	LagCompensation lag;
	std::vector<Hitbox> out;
	EXPECT_FALSE(lag.sample(1, 0.0f, 1, out));

	Hitbox a;
	a.id = 1;
	lag.record(10, {a});
	a.center[2] = 3.0f;
	lag.record(13, {a});  // ticks 11 and 12 missing
	Hitbox b;
	b.id = 2;
	lag.record(14, {a, b});
	lag.record(12, {b});  // older than the newest: ignored
	ASSERT_TRUE(lag.sample(11, 0.5f, 14, out));
	ASSERT_EQ(out.size(), 1u);
	EXPECT_NEAR(out[0].center[2], 1.5f, 1e-5f);
	// Future times are clamped to the newest frame.
	ASSERT_TRUE(lag.sample(100, 0.0f, 14, out));
	EXPECT_EQ(out.size(), 2u);
	// Times before the history are clamped to the oldest frame.
	ASSERT_TRUE(lag.sample(1, 0.0f, 14, out));
	EXPECT_EQ(out[0].center[2], 0.0f);
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Clock
 * \{ */

TEST(NetClock, OffsetFromPongs)
{
	ClockConfig config;
	config.tickRate = 60;
	NetClock clock(config);
	EXPECT_FALSE(clock.synced());
	// Server tick 600 (10 s) read 50 ms before the Pong arrived at local time 5000.
	clock.addPong(100.0f, 600, 5000);
	EXPECT_TRUE(clock.synced());
	EXPECT_NEAR(clock.serverTime(5000), 603.0, 0.01);
	EXPECT_NEAR(clock.serverTime(6000), 663.0, 0.01);
	// Prediction runs half a round trip plus two ticks ahead.
	EXPECT_EQ(clock.predictionTick(5000), 608u);
	Tick tick;
	float alpha;
	clock.renderTime(5000, tick, alpha);
	EXPECT_EQ(tick, 597u);  // 100 ms (2 snapshots at 20 Hz) behind
}

TEST(NetClock, InputSlackMovesPredictionLead)
{
	ClockConfig config;
	config.tickRate = 60;
	config.targetInputSlack = 3.0f;
	config.inputSlackGain = 0.5f;
	NetClock clock(config);
	clock.addPong(100.0f, 600, 5000);
	EXPECT_EQ(clock.predictionTick(5000), 608u);
	// Inputs arrive 1 tick late: the lead grows by half of the 4 missing ticks.
	clock.addInputSlack(-1.0f);
	EXPECT_FLOAT_EQ(clock.leadAdjustTicks(), 2.0f);
	EXPECT_EQ(clock.predictionTick(5000), 610u);
	// Far too early: the lead shrinks, bounded by one second.
	for (int i = 0; i < 100; ++i) {
		clock.addInputSlack(500.0f);
	}
	EXPECT_FLOAT_EQ(clock.leadAdjustTicks(), -60.0f);
	clock.reset();
	EXPECT_FLOAT_EQ(clock.leadAdjustTicks(), 0.0f);
}

TEST(NetClock, InterpDelayFollowsJitter)
{
	ClockConfig config;
	config.tickRate = 60;
	config.snapshotRate = 20;
	NetClock clock(config);
	net_test::Rng rng(7);
	const float base = clock.interpDelayMs();
	EXPECT_NEAR(base, 100.0f, 0.01f);

	Tick tick = 3;
	const auto feed = [&](int seconds, uint32_t jitter) {
		for (int i = 0; i < seconds * 20; ++i, tick += 3) {
			const uint64_t sent = uint64_t(tick) * 1000 / 60;
			clock.addSnapshot(tick, 1000 + sent + 50 + rng.below(jitter + 1));
		}
	};
	feed(2, 0);
	EXPECT_NEAR(clock.interpDelayMs(), base, 1.0f);
	feed(10, 60);
	const float noisy = clock.interpDelayMs();
	EXPECT_GT(clock.jitterMs(), 10.0f);
	EXPECT_GT(noisy, base + 30.0f);
	EXPECT_LE(noisy, config.maxDelayMs);
	feed(20, 0);
	EXPECT_LT(clock.interpDelayMs(), base + 5.0f);
	EXPECT_LT(clock.interpDelayMs(), noisy);

	// Old or repeated snapshots are ignored.
	const float before = clock.jitterMs();
	clock.addSnapshot(3, 999999);
	EXPECT_EQ(clock.jitterMs(), before);
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Fuzz: Input bodies on the server
 * \{ */

TEST(NetPredictionFuzz, ServerInputDecode)
{
	PredictionServer server;
	net_test::Rng rng(0xF1F1);
	SessionEvent e;
	e.type = SessionEvent::Type::Message;
	e.client = 1;
	e.messageType = uint8_t(MessageType::Input);
	InputBlock out;
	Tick tick = 1;
	for (int i = 0; i < 100000; ++i) {
		e.body.resize(rng.below(80));
		for (uint8_t &b : e.body) {
			b = uint8_t(rng.next());
		}
		// Half of the inputs start like a valid header to reach the block decoding.
		if (!e.body.empty() && (i & 1)) {
			const Tick newest = tick + rng.below(80);
			for (size_t k = 0; k < 4 && k < e.body.size(); ++k) {
				e.body[k] = uint8_t(newest >> (8 * k));
			}
			if (e.body.size() > 4) {
				e.body[4] = uint8_t(1 + rng.below(kMaxInputBlocks));
			}
		}
		server.handleEvent(e, tick);
		server.consume(1, tick, out);
		++tick;
	}
	const InputQueue *q = server.queue(1);
	ASSERT_TRUE(q != nullptr);
	EXPECT_GT(q->stats().invalid, 0u);
	EXPECT_LE(q->pending(), size_t(InputQueueConfig().maxAheadTicks) + 1);
}

/** \} */
