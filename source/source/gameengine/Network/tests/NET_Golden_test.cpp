/* Golden vectors: encoder output compared byte by byte with the .bin files in tests/golden, so every
 * platform (MSVC, GCC/Clang, Emscripten) is held to the same wire format.
 * Regenerate only on an intended format change: net_tests --update-golden */

#include "NET_BitStream.h"
#include "NET_Messages.h"

#include "net_test_samples.h"
#include "net_test_util.h"

#include "gtest/gtest.h"

#include <fstream>
#include <iterator>

using namespace net;

static std::string goldenPath(const std::string &name)
{
	return std::string(NET_GOLDEN_DIR) + "/" + name + ".bin";
}

static void checkGolden(const std::string &name, const std::vector<uint8_t> &data)
{
	const std::string path = goldenPath(name);
	if (net_test::updateGolden()) {
		std::ofstream out(path, std::ios::binary);
		out.write(reinterpret_cast<const char *>(data.data()), std::streamsize(data.size()));
		ASSERT_TRUE(bool(out)) << path;
		return;
	}
	std::ifstream in(path, std::ios::binary);
	ASSERT_TRUE(bool(in)) << "missing golden file " << path;
	const std::vector<uint8_t> expected((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
	ASSERT_EQ(data.size(), expected.size()) << name;
	for (size_t i = 0; i < data.size(); ++i) {
		ASSERT_EQ(data[i], expected[i]) << name << " differs at byte " << i;
	}
}

TEST(NetGolden, BitStreamPrimitives)
{
	std::vector<uint8_t> buf;
	BitWriter w(buf);
	w.writeBits(5, 3);
	w.writeBool(true);
	w.writeBits(0x1234, 13);
	w.writeU8(0xA5);
	w.writeU16(0xBEEF);
	w.writeU32(0xDEADBEEFu);
	w.writeU64(0x0102030405060708ull);
	w.writeVarU(300);
	w.writeVarU(0xFFFFFFFFFFFFFFFFull);
	w.writeVarI(-1);
	w.writeVarI(-123456789);
	w.writeString("Anastacio");
	w.writeQuantized(0.3f, -1.0f, 1.0f, 11);
	w.writeQuantized(1e9f, -1.0f, 1.0f, 7);
	writeFloat32(w, -2.75f);
	w.alignToByte();
	ASSERT_TRUE(w.ok());
	checkGolden("bitstream_primitives", buf);
}

TEST(NetGolden, Quantization)
{
	std::vector<uint8_t> buf;
	BitWriter w(buf);
	net_test::Rng rng(42);
	for (int bits : {16, 22, 32}) {
		PositionQuant q;
		q.bits = bits;
		for (int n = 0; n < 16; ++n) {
			const float pos[3] = {rng.uniform(-3000.0f, 3000.0f), rng.uniform(-50.0f, 50.0f),
			                      rng.uniform(-0.01f, 0.01f)};
			writePosition(w, pos, q);
		}
	}
	for (int bits : {9, 10, 15}) {
		for (int n = 0; n < 16; ++n) {
			const float quat[4] = {rng.uniform(-1.0f, 1.0f), rng.uniform(-1.0f, 1.0f), rng.uniform(-1.0f, 1.0f),
			                       rng.uniform(-1.0f, 1.0f)};
			writeRotation(w, quat, bits);
		}
	}
	w.alignToByte();
	ASSERT_TRUE(w.ok());
	checkGolden("quantization", buf);
}

TEST(NetGolden, Messages)
{
	for (const net_test::NamedPacket &p : net_test::sampleMessagePackets()) {
		checkGolden("msg_" + p.name, p.data);
	}
}
