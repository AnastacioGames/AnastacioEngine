/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file NET_BitStream.h
 *  \ingroup network
 *  \brief Bit level writer/reader and transform quantization (contract 6.1 and 9.1).
 *
 * Bits are packed from the least to the most significant bit of each byte, so
 * byte aligned integers come out little-endian.
 */

#ifndef __NET_BITSTREAM_H__
#define __NET_BITSTREAM_H__

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace net {

/// Position quantization: signed integer millimeters, bits per axis in [16, 32].
struct PositionQuant {
	int bits = 22;
};

constexpr int kMinPositionBits = 16;
constexpr int kMaxPositionBits = 32;
constexpr int kDefaultRotationBits = 10;
constexpr int kMinRotationBits = 9;
constexpr int kMaxRotationBits = 15;

class BitWriter {
public:
	/// Appends to out, existing content is kept.
	explicit BitWriter(std::vector<uint8_t> &out);

	void writeBits(uint32_t value, int bits);  // 1..32
	void writeBool(bool v);
	void writeU8(uint8_t v);
	void writeU16(uint16_t v);
	void writeU32(uint32_t v);
	void writeU64(uint64_t v);
	void writeVarU(uint64_t v);  // LEB128
	void writeVarI(int64_t v);  // zigzag + LEB128
	void writeString(std::string_view s);  // sets ok() to false if > 255 bytes
	void writeQuantized(float v, float min, float max, int bits);
	void alignToByte();
	size_t bitsWritten() const;
	bool ok() const;

	/// Marks the stream as failed (used by higher level encoders).
	void fail();

private:
	std::vector<uint8_t> &m_out;
	size_t m_startBit;
	size_t m_bitPos;
	bool m_ok;
};

class BitReader {
public:
	BitReader(const uint8_t *data, size_t size);

	uint32_t readBits(int bits);  // past the end: returns 0 and marks error
	bool readBool();
	uint8_t readU8();
	uint16_t readU16();
	uint32_t readU32();
	uint64_t readU64();
	uint64_t readVarU();
	int64_t readVarI();
	bool readString(std::string &out);
	float readQuantized(float min, float max, int bits);
	void alignToByte();
	size_t bitsRemaining() const;
	bool ok() const;  // false after any invalid read

	/// Marks the stream as failed: every following read returns zero.
	void fail();
	/// Current position in bits from the start of the buffer.
	size_t bitPosition() const;

private:
	const uint8_t *m_data;
	size_t m_size;
	size_t m_bitPos;
	bool m_ok;
};

/// Raw IEEE-754 single precision, 32 bits.
void writeFloat32(BitWriter &w, float v);
float readFloat32(BitReader &r);

/// Deterministic quantization helpers (integer results, round half away from zero, clamped).
uint32_t quantizeRange(float v, float min, float max, int bits);
float dequantizeRange(uint32_t q, float min, float max, int bits);
int32_t quantizePositionAxis(float v, int bits);
float dequantizePositionAxis(int32_t q);

struct QuantizedRotation {
	uint32_t largest = 3;
	uint32_t comps[3] = {0, 0, 0};

	bool operator==(const QuantizedRotation &o) const
	{
		return largest == o.largest && comps[0] == o.comps[0] && comps[1] == o.comps[1] &&
		       comps[2] == o.comps[2];
	}
	bool operator!=(const QuantizedRotation &o) const
	{
		return !(*this == o);
	}
};

/// Smallest three; quat is x,y,z,w and does not need to be normalized. q and -q give the same result.
QuantizedRotation quantizeRotation(const float quat[4], int bitsPerComponent);
void dequantizeRotation(const QuantizedRotation &q, int bitsPerComponent, float quat[4]);

void writePosition(BitWriter &w, const float pos[3], const PositionQuant &quant);
bool readPosition(BitReader &r, float pos[3], const PositionQuant &quant);
void writeRotation(BitWriter &w, const float quat[4], int bitsPerComponent);  // x,y,z,w
bool readRotation(BitReader &r, float quat[4], int bitsPerComponent);

}  // namespace net

#endif  // __NET_BITSTREAM_H__
