/* Bitstream round trips, limits and quantization (contract section 10). */

#include "NET_BitStream.h"
#include "NET_Types.h"

#include "net_test_util.h"

#include "gtest/gtest.h"

#include <cmath>
#include <limits>

using namespace net;

TEST(NetTypes, TickNewerWraps)
{
	EXPECT_TRUE(tickNewer(2, 1));
	EXPECT_FALSE(tickNewer(1, 2));
	EXPECT_FALSE(tickNewer(5, 5));
	EXPECT_TRUE(tickNewer(3, 0xFFFFFFF0u));
	EXPECT_FALSE(tickNewer(0xFFFFFFF0u, 3));
}

TEST(NetTypes, SceneHashSortsIds)
{
	EXPECT_EQ(sceneHash("Scene", {3, 1, 2}), sceneHash("Scene", {1, 2, 3}));
	EXPECT_NE(sceneHash("Scene", {1, 2, 3}), sceneHash("Scene2", {1, 2, 3}));
	// FNV-1a 64 of the empty input is the offset basis.
	EXPECT_EQ(sceneHash("", {}), 0xcbf29ce484222325ull);
	// FNV-1a 64 of "a".
	EXPECT_EQ(sceneHash("a", {}), 0xaf63dc4c8601ec8cull);
}

TEST(NetBitStream, IntegerRoundTrip)
{
	std::vector<uint8_t> buf;
	BitWriter w(buf);
	w.writeBits(0, 1);
	w.writeBits(1, 1);
	w.writeBits(5, 3);
	w.writeBits(0xFFFFFFFFu, 32);
	w.writeBool(true);
	w.writeU8(0);
	w.writeU8(255);
	w.writeU16(0);
	w.writeU16(0xFFFF);
	w.writeU32(0);
	w.writeU32(0xFFFFFFFFu);
	w.writeU64(0);
	w.writeU64(0xFFFFFFFFFFFFFFFFull);
	w.writeVarU(0);
	w.writeVarU(127);
	w.writeVarU(128);
	w.writeVarU(0xFFFFFFFFFFFFFFFFull);
	w.writeVarI(0);
	w.writeVarI(-1);
	w.writeVarI(std::numeric_limits<int64_t>::min());
	w.writeVarI(std::numeric_limits<int64_t>::max());
	w.writeString("");
	w.writeString("hello");
	w.writeString(std::string(255, 'x'));
	ASSERT_TRUE(w.ok());
	const size_t bits = w.bitsWritten();
	w.alignToByte();
	EXPECT_EQ(buf.size(), (bits + 7) / 8);

	BitReader r(buf.data(), buf.size());
	EXPECT_EQ(r.readBits(1), 0u);
	EXPECT_EQ(r.readBits(1), 1u);
	EXPECT_EQ(r.readBits(3), 5u);
	EXPECT_EQ(r.readBits(32), 0xFFFFFFFFu);
	EXPECT_TRUE(r.readBool());
	EXPECT_EQ(r.readU8(), 0);
	EXPECT_EQ(r.readU8(), 255);
	EXPECT_EQ(r.readU16(), 0);
	EXPECT_EQ(r.readU16(), 0xFFFF);
	EXPECT_EQ(r.readU32(), 0u);
	EXPECT_EQ(r.readU32(), 0xFFFFFFFFu);
	EXPECT_EQ(r.readU64(), 0u);
	EXPECT_EQ(r.readU64(), 0xFFFFFFFFFFFFFFFFull);
	EXPECT_EQ(r.readVarU(), 0u);
	EXPECT_EQ(r.readVarU(), 127u);
	EXPECT_EQ(r.readVarU(), 128u);
	EXPECT_EQ(r.readVarU(), 0xFFFFFFFFFFFFFFFFull);
	EXPECT_EQ(r.readVarI(), 0);
	EXPECT_EQ(r.readVarI(), -1);
	EXPECT_EQ(r.readVarI(), std::numeric_limits<int64_t>::min());
	EXPECT_EQ(r.readVarI(), std::numeric_limits<int64_t>::max());
	std::string s;
	EXPECT_TRUE(r.readString(s));
	EXPECT_EQ(s, "");
	EXPECT_TRUE(r.readString(s));
	EXPECT_EQ(s, "hello");
	EXPECT_TRUE(r.readString(s));
	EXPECT_EQ(s, std::string(255, 'x'));
	EXPECT_TRUE(r.ok());
	r.alignToByte();
	EXPECT_EQ(r.bitsRemaining(), 0u);
}

TEST(NetBitStream, LittleEndianLsbFirst)
{
	std::vector<uint8_t> buf;
	BitWriter w(buf);
	w.writeU32(0x04030201u);
	w.writeBits(1, 1);
	w.writeBits(3, 2);
	ASSERT_EQ(buf.size(), 5u);
	EXPECT_EQ(buf[0], 1);
	EXPECT_EQ(buf[3], 4);
	EXPECT_EQ(buf[4], 0x07);
}

TEST(NetBitStream, WriterAppends)
{
	std::vector<uint8_t> buf = {0xAA};
	BitWriter w(buf);
	w.writeU8(0x55);
	EXPECT_EQ(w.bitsWritten(), 8u);
	ASSERT_EQ(buf.size(), 2u);
	EXPECT_EQ(buf[0], 0xAA);
	EXPECT_EQ(buf[1], 0x55);
}

TEST(NetBitStream, WriterErrors)
{
	std::vector<uint8_t> buf;
	BitWriter w(buf);
	w.writeString(std::string(256, 'x'));
	EXPECT_FALSE(w.ok());

	std::vector<uint8_t> buf2;
	BitWriter w2(buf2);
	w2.writeBits(1, 0);
	EXPECT_FALSE(w2.ok());

	std::vector<uint8_t> buf3;
	BitWriter w3(buf3);
	w3.writeQuantized(1.0f, 2.0f, 1.0f, 8);
	EXPECT_FALSE(w3.ok());
}

TEST(NetBitStream, ReadPastEndReturnsZero)
{
	const uint8_t data[2] = {0xFF, 0xFF};
	BitReader r(data, sizeof(data));
	EXPECT_EQ(r.readU8(), 0xFF);
	EXPECT_EQ(r.readU16(), 0u);
	EXPECT_FALSE(r.ok());
	// Once failed, everything reads as zero, even data that is still there.
	EXPECT_EQ(r.readBits(1), 0u);
	EXPECT_EQ(r.bitsRemaining(), 0u);

	BitReader empty(nullptr, 10);
	EXPECT_EQ(empty.readU8(), 0);
	EXPECT_FALSE(empty.ok());
}

TEST(NetBitStream, BadVarAndString)
{
	// 11 continuation bytes.
	std::vector<uint8_t> longVar(11, 0x80);
	BitReader r(longVar.data(), longVar.size());
	r.readVarU();
	EXPECT_FALSE(r.ok());

	// 10th byte with more than one bit set overflows 64 bits.
	std::vector<uint8_t> overflow(9, 0xFF);
	overflow.push_back(0x02);
	BitReader r2(overflow.data(), overflow.size());
	r2.readVarU();
	EXPECT_FALSE(r2.ok());

	// String longer than the data.
	const uint8_t shortStr[3] = {5, 'a', 'b'};
	BitReader r3(shortStr, sizeof(shortStr));
	std::string s;
	EXPECT_FALSE(r3.readString(s));
	EXPECT_FALSE(r3.ok());

	// Length above 255.
	std::vector<uint8_t> big = {0x80, 0x02};
	big.resize(300, 'a');
	BitReader r4(big.data(), big.size());
	EXPECT_FALSE(r4.readString(s));
}

TEST(NetBitStream, QuantizedRangeAndClamp)
{
	EXPECT_EQ(quantizeRange(-1.0f, -1.0f, 1.0f, 8), 0u);
	EXPECT_EQ(quantizeRange(1.0f, -1.0f, 1.0f, 8), 255u);
	EXPECT_EQ(quantizeRange(-5.0f, -1.0f, 1.0f, 8), 0u);
	EXPECT_EQ(quantizeRange(5.0f, -1.0f, 1.0f, 8), 255u);
	EXPECT_EQ(quantizeRange(std::numeric_limits<float>::infinity(), -1.0f, 1.0f, 8), 255u);
	EXPECT_EQ(quantizeRange(std::nanf(""), -1.0f, 1.0f, 8), 0u);
	EXPECT_EQ(quantizeRange(1e30f, -1.0f, 1.0f, 32), 0xFFFFFFFFu);

	std::vector<uint8_t> buf;
	BitWriter w(buf);
	w.writeQuantized(0.5f, 0.0f, 1.0f, 16);
	w.writeQuantized(100.0f, 0.0f, 1.0f, 16);
	w.writeQuantized(-3.0f, -10.0f, 10.0f, 12);
	BitReader r(buf.data(), buf.size());
	EXPECT_NEAR(r.readQuantized(0.0f, 1.0f, 16), 0.5f, 1.0f / 65535.0f);
	EXPECT_EQ(r.readQuantized(0.0f, 1.0f, 16), 1.0f);
	EXPECT_NEAR(r.readQuantized(-10.0f, 10.0f, 12), -3.0f, 20.0f / 4095.0f);
	EXPECT_TRUE(r.ok());
}

TEST(NetBitStream, RoundHalfAwayFromZero)
{
	// 0.0625 m = 62.5 mm exactly: halves round away from zero in both directions.
	EXPECT_EQ(quantizePositionAxis(0.0625f, 22), 63);
	EXPECT_EQ(quantizePositionAxis(-0.0625f, 22), -63);
	// 0.5 / 255 of the range lands exactly on a half step.
	EXPECT_EQ(quantizeRange(0.5f, 0.0f, 255.0f, 8), 1u);
	EXPECT_EQ(quantizePositionAxis(0.0f, 22), 0);
}

TEST(NetBitStream, PositionRoundTripAndClamp)
{
	PositionQuant quant;
	const float pos[3] = {1.2345f, -987.654f, 0.0f};
	std::vector<uint8_t> buf;
	BitWriter w(buf);
	writePosition(w, pos, quant);
	EXPECT_EQ(w.bitsWritten(), 66u);
	// Out of range: ±2097.152 m with 22 bits.
	const float far[3] = {5000.0f, -5000.0f, std::nanf("")};
	writePosition(w, far, quant);
	ASSERT_TRUE(w.ok());

	BitReader r(buf.data(), buf.size());
	float out[3];
	ASSERT_TRUE(readPosition(r, out, quant));
	for (int i = 0; i < 3; ++i) {
		EXPECT_NEAR(out[i], pos[i], 0.0005f + 1e-4f);
	}
	ASSERT_TRUE(readPosition(r, out, quant));
	EXPECT_FLOAT_EQ(out[0], 2097.151f);
	EXPECT_FLOAT_EQ(out[1], -2097.152f);
	EXPECT_EQ(out[2], 0.0f);

	for (int bits : {16, 32}) {
		PositionQuant q;
		q.bits = bits;
		const float limits[3] = {1e9f, -1e9f, -0.001f};
		std::vector<uint8_t> b;
		BitWriter bw(b);
		writePosition(bw, limits, q);
		BitReader br(b.data(), b.size());
		float o[3];
		ASSERT_TRUE(readPosition(br, o, q));
		const double hi = (std::ldexp(1.0, bits - 1) - 1.0) / 1000.0;
		const double lo = -std::ldexp(1.0, bits - 1) / 1000.0;
		EXPECT_FLOAT_EQ(o[0], float(hi));
		EXPECT_FLOAT_EQ(o[1], float(lo));
		EXPECT_FLOAT_EQ(o[2], -0.001f);
	}

	PositionQuant bad;
	bad.bits = 15;
	std::vector<uint8_t> b;
	BitWriter bw(b);
	writePosition(bw, pos, bad);
	EXPECT_FALSE(bw.ok());
}

static double angleBetween(const float a[4], const float b[4])
{
	double dot = 0.0, la = 0.0, lb = 0.0;
	for (int i = 0; i < 4; ++i) {
		dot += double(a[i]) * b[i];
		la += double(a[i]) * a[i];
		lb += double(b[i]) * b[i];
	}
	dot = std::fabs(dot) / std::sqrt(la * lb);
	return 2.0 * std::acos(std::min(dot, 1.0)) * 180.0 / 3.14159265358979323846;
}

TEST(NetBitStream, RotationErrorBelowQuarterDegree)
{
	net_test::Rng rng(1234);
	double maxError = 0.0;
	for (int n = 0; n < 20000; ++n) {
		float q[4];
		for (float &c : q) {
			c = rng.uniform(-1.0f, 1.0f);
		}
		std::vector<uint8_t> buf;
		BitWriter w(buf);
		writeRotation(w, q, 10);
		ASSERT_EQ(w.bitsWritten(), 32u);
		BitReader r(buf.data(), buf.size());
		float out[4];
		ASSERT_TRUE(readRotation(r, out, 10));
		maxError = std::max(maxError, angleBetween(q, out));
	}
	EXPECT_LT(maxError, 0.25);
}

TEST(NetBitStream, RotationSignInvariant)
{
	net_test::Rng rng(99);
	for (int n = 0; n < 2000; ++n) {
		float q[4], neg[4];
		for (int i = 0; i < 4; ++i) {
			q[i] = rng.uniform(-1.0f, 1.0f);
			neg[i] = -q[i];
		}
		EXPECT_TRUE(quantizeRotation(q, 10) == quantizeRotation(neg, 10));
	}
	// Ties between components.
	const float tie[4] = {0.5f, -0.5f, 0.5f, -0.5f};
	const float tieNeg[4] = {-0.5f, 0.5f, -0.5f, 0.5f};
	EXPECT_TRUE(quantizeRotation(tie, 10) == quantizeRotation(tieNeg, 10));
}

TEST(NetBitStream, RotationDegenerateAndAxes)
{
	const float zero[4] = {0.0f, 0.0f, 0.0f, 0.0f};
	std::vector<uint8_t> buf;
	BitWriter w(buf);
	writeRotation(w, zero, 10);
	const float axes[4][4] = {{1, 0, 0, 0}, {0, 1, 0, 0}, {0, 0, -1, 0}, {0, 0, 0, 1}};
	for (const auto &a : axes) {
		writeRotation(w, a, 15);
	}
	BitReader r(buf.data(), buf.size());
	float out[4];
	ASSERT_TRUE(readRotation(r, out, 10));
	EXPECT_NEAR(out[3], 1.0f, 1e-3f);
	for (const auto &a : axes) {
		ASSERT_TRUE(readRotation(r, out, 15));
		EXPECT_LT(angleBetween(a, out), 0.05);
	}

	std::vector<uint8_t> b;
	BitWriter bw(b);
	writeRotation(bw, zero, 8);
	EXPECT_FALSE(bw.ok());
}

TEST(NetBitStream, Float32Raw)
{
	std::vector<uint8_t> buf;
	BitWriter w(buf);
	writeFloat32(w, 1.0f);
	writeFloat32(w, -0.0f);
	ASSERT_EQ(buf.size(), 8u);
	EXPECT_EQ(buf[3], 0x3F);
	EXPECT_EQ(buf[2], 0x80);
	BitReader r(buf.data(), buf.size());
	EXPECT_EQ(readFloat32(r), 1.0f);
	EXPECT_TRUE(std::signbit(readFloat32(r)));
}
