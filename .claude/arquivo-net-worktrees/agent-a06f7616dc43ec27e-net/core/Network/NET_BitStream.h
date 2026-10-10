/* SPDX-License-Identifier: GPL-2.0-or-later */

/** \file NET_BitStream.h
 *  Bit level writer/reader and quantization (protocol contract v1, sections 1, 6.1 and 9.1).
 *  Little-endian; bits are written from the least to the most significant bit of each byte.
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace net {

class BitWriter {
public:
	/** Appends to out (existing content is kept). */
	explicit BitWriter(std::vector<uint8_t> &out);

	void writeBits(uint32_t value, int bits); // 1..32
	void writeBool(bool v);
	void writeU8(uint8_t v);
	void writeU16(uint16_t v);
	void writeU32(uint32_t v);
	void writeU64(uint64_t v);
	void writeVarU(uint64_t v); // LEB128
	void writeVarI(int64_t v);  // zigzag + LEB128
	void writeString(std::string_view s); // ok() becomes false if > 255 bytes
	void writeFloat(float v);   // raw IEEE-754 bits
	void writeQuantized(float v, float min, float max, int bits);
	void writeBytes(const uint8_t *data, size_t size);
	void alignToByte();
	size_t bitsWritten() const;
	bool ok() const;
	/** Marks the stream as failed (used by higher level encoders). */
	void fail();

private:
	std::vector<uint8_t> &m_out;
	size_t m_startBit;
	size_t m_bit;
	bool m_ok;
};

class BitReader {
public:
	BitReader(const uint8_t *data, size_t size);

	uint32_t readBits(int bits); // past the end: returns 0 and flags the error
	bool readBool();
	uint8_t readU8();
	uint16_t readU16();
	uint32_t readU32();
	uint64_t readU64();
	uint64_t readVarU();
	int64_t readVarI();
	bool readString(std::string &out);
	float readFloat();
	float readQuantized(float min, float max, int bits);
	bool readBytes(uint8_t *out, size_t size);
	void alignToByte();
	size_t bitsRemaining() const;
	/** Byte offset of the read position, rounded up. */
	size_t bytePosition() const;
	bool ok() const; // false after any invalid read
	void fail();

private:
	const uint8_t *m_data;
	size_t m_sizeBits;
	size_t m_pos;
	bool m_ok;
};

/** Position quantization (section 6.1): 1 mm step, signed, bitsPerAxis in 16..32. */
struct PositionQuant {
	int bitsPerAxis = 22;
};

constexpr int kDefaultRotationBits = 10;
constexpr int kMinRotationBits = 9;
constexpr int kMaxRotationBits = 15;
constexpr float kDefaultMaxSpeed = 100.0f;
constexpr float kDefaultMaxAngSpeed = 50.0f;
constexpr int kVelocityBits = 16;
constexpr int kAngVelocityBits = 12;

/** Deterministic integer quantization helpers (exposed for tests and delta comparison). */
int64_t quantizePositionAxis(float v, int bits);
float dequantizePositionAxis(int64_t q);
uint32_t quantizeRange(float v, float min, float max, int bits);
float dequantizeRange(uint32_t q, float min, float max, int bits);

struct QuantizedRotation {
	uint32_t largest;  // 0..3 (x, y, z, w)
	uint32_t comp[3];
	bool operator==(const QuantizedRotation &o) const
	{
		return largest == o.largest && comp[0] == o.comp[0] && comp[1] == o.comp[1] && comp[2] == o.comp[2];
	}
};
QuantizedRotation quantizeRotation(const float quat[4], int bitsPerComponent);
void dequantizeRotation(const QuantizedRotation &q, float quat[4], int bitsPerComponent);

// quantization of transform (section 6.1)
void writePosition(BitWriter &w, const float pos[3], const PositionQuant &quant);
bool readPosition(BitReader &r, float pos[3], const PositionQuant &quant);
void writeRotation(BitWriter &w, const float quat[4], int bitsPerComponent); // x,y,z,w normalized
bool readRotation(BitReader &r, float quat[4], int bitsPerComponent);

} // namespace net
