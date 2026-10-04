/* Snapshot encode/decode with delta and interpolation buffer. */

#include "NET_Messages.h"
#include "NET_Snapshot.h"

#include "net_test_samples.h"
#include "net_test_util.h"

#include "gtest/gtest.h"

#include <cmath>

using namespace net;

static std::vector<uint8_t> encodeBody(Tick tick, const std::vector<ObjectState> &objects,
                                       const Snapshot *baseline, const SnapshotConfig &config)
{
	std::vector<uint8_t> body;
	BitWriter w(body);
	EXPECT_TRUE(encodeSnapshot(w, tick, objects, baseline, config));
	return body;
}

static Snapshot decodeBody(const std::vector<uint8_t> &body, const Snapshot *baseline,
                           const SnapshotConfig &config)
{
	BitReader r(body.data(), body.size());
	Snapshot out;
	EXPECT_TRUE(decodeSnapshot(r, baseline, config, out));
	return out;
}

static void expectClose(const ObjectState &a, const ObjectState &b)
{
	EXPECT_EQ(a.id, b.id);
	EXPECT_EQ(a.hasTransform, b.hasTransform);
	for (int i = 0; i < 3; ++i) {
		EXPECT_NEAR(a.position[i], b.position[i], 0.001f);
		EXPECT_NEAR(a.velocity[i], b.velocity[i], 0.01f);
		EXPECT_NEAR(a.angularVelocity[i], b.angularVelocity[i], 0.03f);
	}
	for (int i = 0; i < 4; ++i) {
		EXPECT_NEAR(a.rotation[i], b.rotation[i], 0.002f);
	}
	ASSERT_EQ(a.props.size(), b.props.size());
	for (size_t i = 0; i < a.props.size(); ++i) {
		EXPECT_EQ(a.props[i].kind, b.props[i].kind);
		EXPECT_EQ(a.props[i].b, b.props[i].b);
		EXPECT_EQ(a.props[i].i, b.props[i].i);
		EXPECT_NEAR(a.props[i].f, b.props[i].f, 0.1f);
	}
	EXPECT_EQ(a.hasAnim, b.hasAnim);
	EXPECT_EQ(a.anim.action, b.anim.action);
	EXPECT_EQ(a.anim.frame, b.anim.frame);
}

TEST(NetSnapshot, FullRoundTrip)
{
	const SnapshotConfig config = net_test::sampleConfig();
	const std::vector<ObjectState> objects = net_test::sampleObjects(0.0f);
	const Snapshot s = decodeBody(encodeBody(10, objects, nullptr, config), nullptr, config);
	EXPECT_EQ(s.tick, 10u);
	EXPECT_EQ(s.baselineTick, kNoTick);
	ASSERT_EQ(s.objects.size(), objects.size());
	for (size_t i = 0; i < objects.size(); ++i) {
		expectClose(s.objects[i], objects[i]);
	}
	EXPECT_FALSE(s.objects[0].hasVelocity);
	EXPECT_TRUE(s.objects[1].hasVelocity);
}

TEST(NetSnapshot, StationaryObjectCostsNothing)
{
	const SnapshotConfig config = net_test::sampleConfig();
	Snapshot baseline;
	baseline.tick = 10;
	baseline.objects = net_test::sampleObjects(0.0f);
	const std::vector<uint8_t> body = encodeBody(11, baseline.objects, &baseline, config);
	// tick + baselineTick + objectCount = 0.
	EXPECT_EQ(body.size(), 9u);
	const Snapshot s = decodeBody(body, &baseline, config);
	ASSERT_EQ(s.objects.size(), baseline.objects.size());
	EXPECT_EQ(s.baselineTick, 10u);
	for (size_t i = 0; i < s.objects.size(); ++i) {
		expectClose(s.objects[i], baseline.objects[i]);
	}
}

TEST(NetSnapshot, DeltaChangesRemovalsAndAdds)
{
	const SnapshotConfig config = net_test::sampleConfig();
	Snapshot baseline;
	baseline.tick = 10;
	baseline.objects = net_test::sampleObjects(0.0f);

	std::vector<ObjectState> current = baseline.objects;
	current[0].position[0] += 0.5f;                  // transform only
	current[2].props[1] = PropValue::makeInt(7);     // one property
	current.erase(current.begin() + 1);              // id 2 removed
	current.push_back(net_test::sampleObject(0x90000000u, 2.0f));  // new object

	const std::vector<uint8_t> delta = encodeBody(12, current, &baseline, config);
	const std::vector<uint8_t> full = encodeBody(12, current, nullptr, config);
	EXPECT_LT(delta.size(), full.size());

	const Snapshot s = decodeBody(delta, &baseline, config);
	ASSERT_EQ(s.objects.size(), current.size());
	for (size_t i = 0; i < current.size(); ++i) {
		expectClose(s.objects[i], current[i]);
	}
	EXPECT_EQ(s.find(2), nullptr);
	ASSERT_NE(s.find(0x110), nullptr);
	EXPECT_EQ(s.find(0x110)->props[1].i, 7);
}

TEST(NetSnapshot, MissingBaselineFails)
{
	const SnapshotConfig config = net_test::sampleConfig();
	Snapshot baseline;
	baseline.tick = 10;
	baseline.objects = net_test::sampleObjects(0.0f);
	const std::vector<uint8_t> body = encodeBody(11, net_test::sampleObjects(1.0f), &baseline, config);

	Tick tick, base;
	ASSERT_TRUE(readSnapshotHeader(body.data(), body.size(), tick, base));
	EXPECT_EQ(tick, 11u);
	EXPECT_EQ(base, 10u);

	Snapshot wrong = baseline;
	wrong.tick = 9;
	Snapshot out;
	BitReader r(body.data(), body.size());
	EXPECT_FALSE(decodeSnapshot(r, &wrong, config, out));
	BitReader r2(body.data(), body.size());
	EXPECT_FALSE(decodeSnapshot(r2, nullptr, config, out));
}

TEST(NetSnapshot, InvalidInput)
{
	const SnapshotConfig config = net_test::sampleConfig();
	// Unsorted ids.
	std::vector<ObjectState> objects = {net_test::sampleObject(5, 0.0f), net_test::sampleObject(3, 0.0f)};
	std::vector<uint8_t> body;
	BitWriter w(body);
	EXPECT_FALSE(encodeSnapshot(w, 1, objects, nullptr, config));

	// Properties without a schema.
	ObjectState o = net_test::sampleObject(7, 0.0f);
	o.props = {PropValue::makeBool(true)};
	std::vector<uint8_t> body2;
	BitWriter w2(body2);
	EXPECT_FALSE(encodeSnapshot(w2, 1, {o}, nullptr, config));

	// Property kind not matching the schema.
	ObjectState p = net_test::sampleObject(0x10, 0.0f);
	p.props[0] = PropValue::makeInt(1);
	std::vector<uint8_t> body3;
	BitWriter w3(body3);
	EXPECT_FALSE(encodeSnapshot(w3, 1, {p}, nullptr, config));

	// Zero NetId delta in the stream.
	const uint8_t zeroDelta[] = {1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0};
	BitReader r(zeroDelta, sizeof(zeroDelta));
	Snapshot out;
	EXPECT_FALSE(decodeSnapshot(r, nullptr, config, out));

	// Object count larger than the data could hold.
	const uint8_t hugeCount[] = {1, 0, 0, 0, 0, 0, 0, 0, 0xFF, 0x7F};
	BitReader r2(hugeCount, sizeof(hugeCount));
	EXPECT_FALSE(decodeSnapshot(r2, nullptr, config, out));
}

TEST(NetSnapshot, ChangedFlagZeroKeepsBaseline)
{
	const SnapshotConfig config = net_test::sampleConfig();
	Snapshot baseline;
	baseline.tick = 4;
	baseline.objects = {net_test::sampleObject(1, 0.0f)};
	// Hand made: one entry, delta 1, removed 0, changed 0.
	std::vector<uint8_t> body;
	BitWriter w(body);
	w.writeU32(5);
	w.writeU32(4);
	w.writeVarU(1);
	w.writeVarU(1);
	w.writeBool(false);
	w.writeBool(false);
	w.alignToByte();
	const Snapshot s = decodeBody(body, &baseline, config);
	ASSERT_EQ(s.objects.size(), 1u);
	expectClose(s.objects[0], baseline.objects[0]);
}

TEST(NetSnapshot, SnapshotMessageAndFuzz)
{
	const SnapshotConfig config = net_test::sampleConfig();
	std::vector<uint8_t> packet;
	ASSERT_TRUE(encodeSnapshotMessage(packet, 3, net_test::sampleObjects(0.0f), nullptr, config));
	PacketReader reader(packet.data(), packet.size());
	RawMessage raw;
	ASSERT_TRUE(reader.next(raw));
	Snapshot s;
	ASSERT_TRUE(decodeSnapshotMessage(raw, nullptr, config, s));
	EXPECT_EQ(s.objects.size(), 4u);

	Snapshot baseline;
	baseline.tick = 3;
	baseline.objects = s.objects;
	net_test::Rng rng(7);
	for (int n = 0; n < 100000; ++n) {
		std::vector<uint8_t> body(raw.body, raw.body + raw.size);
		const int flips = 1 + int(rng.below(6));
		for (int f = 0; f < flips; ++f) {
			body[rng.below(uint32_t(body.size()))] ^= uint8_t(1u << rng.below(8));
		}
		body.resize(rng.below(uint32_t(body.size()) + 1));
		BitReader r(body.data(), body.size());
		Snapshot out;
		decodeSnapshot(r, &baseline, config, out);
	}
}

static Snapshot makeTimed(Tick tick, float x, float angle)
{
	Snapshot s;
	s.tick = tick;
	ObjectState o;
	o.id = 1;
	o.hasTransform = true;
	o.position[0] = x;
	o.rotation[2] = std::sin(angle / 2.0f);
	o.rotation[3] = std::cos(angle / 2.0f);
	s.objects.push_back(o);
	ObjectState only;
	only.id = 2;
	only.hasTransform = true;
	only.position[1] = x;
	if (tick == 10) {
		s.objects.push_back(only);
	}
	return s;
}

TEST(NetSnapshotBuffer, InterpolatesPositionAndRotation)
{
	SnapshotBuffer buffer(4);
	EXPECT_TRUE(buffer.insert(makeTimed(14, 4.0f, 1.0f)));
	EXPECT_TRUE(buffer.insert(makeTimed(10, 0.0f, 0.0f)));
	ASSERT_EQ(buffer.size(), 2u);
	EXPECT_EQ(buffer.oldest()->tick, 10u);
	EXPECT_EQ(buffer.newest()->tick, 14u);

	std::vector<ObjectState> out;
	EXPECT_FALSE(buffer.sample(9, 0.5f, out));

	ASSERT_TRUE(buffer.sample(11, 0.0f, out));
	ASSERT_EQ(out.size(), 2u);
	EXPECT_NEAR(out[0].position[0], 1.0f, 1e-5f);
	// Slerp: a quarter of 1 rad around Z.
	EXPECT_NEAR(out[0].rotation[2], std::sin(0.125f), 1e-5f);
	EXPECT_NEAR(out[0].rotation[3], std::cos(0.125f), 1e-5f);
	// Object only in the older snapshot is kept as is.
	EXPECT_EQ(out[1].id, 2u);
	EXPECT_EQ(out[1].position[1], 0.0f);

	ASSERT_TRUE(buffer.sample(12, 0.5f, out));
	EXPECT_NEAR(out[0].position[0], 2.5f, 1e-5f);

	// Past the newest: no extrapolation.
	ASSERT_TRUE(buffer.sample(20, 0.0f, out));
	ASSERT_EQ(out.size(), 1u);
	EXPECT_EQ(out[0].position[0], 4.0f);
}

TEST(NetSnapshotBuffer, CapacityOrderAndWrap)
{
	SnapshotBuffer buffer(3);
	const Tick base = 0xFFFFFFFEu;
	for (Tick i = 0; i < 5; ++i) {
		EXPECT_TRUE(buffer.insert(makeTimed(base + i, float(i), 0.0f)));
	}
	ASSERT_EQ(buffer.size(), 3u);
	EXPECT_EQ(buffer.oldest()->tick, base + 2);
	EXPECT_EQ(buffer.newest()->tick, base + 4);
	// Older than everything in a full buffer.
	EXPECT_FALSE(buffer.insert(makeTimed(base, 0.0f, 0.0f)));
	// Same tick replaces.
	EXPECT_TRUE(buffer.insert(makeTimed(base + 3, 100.0f, 0.0f)));
	EXPECT_EQ(buffer.size(), 3u);
	EXPECT_EQ(buffer.find(base + 3)->objects[0].position[0], 100.0f);

	std::vector<ObjectState> out;
	// Interpolation across the wrap (ticks 0 -> 1).
	ASSERT_TRUE(buffer.sample(base + 2, 0.5f, out));
	EXPECT_NEAR(out[0].position[0], 51.0f, 1e-4f);
	buffer.clear();
	EXPECT_EQ(buffer.newest(), nullptr);
	EXPECT_FALSE(buffer.sample(1, 0.0f, out));
}

TEST(NetSnapshotBuffer, SlerpShortestPath)
{
	const float a[4] = {0.0f, 0.0f, 0.0f, 1.0f};
	const float b[4] = {0.0f, 0.0f, 0.0f, -1.0f};
	float out[4];
	slerp(a, b, 0.5f, out);
	EXPECT_NEAR(std::fabs(out[3]), 1.0f, 1e-6f);
}
