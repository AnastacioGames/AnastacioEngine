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

/** \file gameengine/Network/NET_BitStream.cpp
 *  \ingroup network
 */

#include "NET_BitStream.h"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace net {

static const double kSmallestThreeRange = 0.70710678118654752440;  // 1 / sqrt(2)

static inline uint32_t maxQuantized(int bits)
{
	return (bits >= 32) ? 0xFFFFFFFFu : ((1u << bits) - 1u);
}

/* -------------------------------------------------------------------- */
/** \name BitWriter
 * \{ */

BitWriter::BitWriter(std::vector<uint8_t> &out)
	:m_out(out),
	m_startBit(out.size() * 8),
	m_bitPos(out.size() * 8),
	m_ok(true)
{
}

void BitWriter::writeBits(uint32_t value, int bits)
{
	if (!m_ok) {
		return;
	}
	if (bits < 1 || bits > 32) {
		m_ok = false;
		return;
	}
	uint64_t v = uint64_t(value) & maxQuantized(bits);
	int left = bits;
	while (left > 0) {
		const size_t byteIndex = m_bitPos >> 3;
		const int offset = int(m_bitPos & 7);
		if (offset == 0) {
			m_out.push_back(0);
		}
		const int chunk = std::min(8 - offset, left);
		const uint8_t mask = uint8_t((1u << chunk) - 1u);
		m_out[byteIndex] |= uint8_t((uint8_t(v) & mask) << offset);
		v >>= chunk;
		left -= chunk;
		m_bitPos += size_t(chunk);
	}
}

void BitWriter::writeBool(bool v)
{
	writeBits(v ? 1u : 0u, 1);
}

void BitWriter::writeU8(uint8_t v)
{
	writeBits(v, 8);
}

void BitWriter::writeU16(uint16_t v)
{
	writeBits(v, 16);
}

void BitWriter::writeU32(uint32_t v)
{
	writeBits(v, 32);
}

void BitWriter::writeU64(uint64_t v)
{
	writeBits(uint32_t(v), 32);
	writeBits(uint32_t(v >> 32), 32);
}

void BitWriter::writeVarU(uint64_t v)
{
	do {
		uint8_t byte = uint8_t(v & 0x7F);
		v >>= 7;
		if (v != 0) {
			byte |= 0x80;
		}
		writeU8(byte);
	} while (v != 0);
}

void BitWriter::writeVarI(int64_t v)
{
	writeVarU((uint64_t(v) << 1) ^ uint64_t(v >> 63));
}

void BitWriter::writeString(std::string_view s)
{
	if (s.size() > 255) {
		m_ok = false;
		return;
	}
	writeVarU(s.size());
	for (char c : s) {
		writeU8(uint8_t(c));
	}
}

void BitWriter::writeQuantized(float v, float min, float max, int bits)
{
	if (!(min < max) || bits < 1 || bits > 32) {
		m_ok = false;
		return;
	}
	writeBits(quantizeRange(v, min, max, bits), bits);
}

void BitWriter::alignToByte()
{
	const int offset = int(m_bitPos & 7);
	if (offset != 0) {
		m_bitPos += size_t(8 - offset);
	}
}

size_t BitWriter::bitsWritten() const
{
	return m_bitPos - m_startBit;
}

bool BitWriter::ok() const
{
	return m_ok;
}

void BitWriter::fail()
{
	m_ok = false;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name BitReader
 * \{ */

BitReader::BitReader(const uint8_t *data, size_t size)
	:m_data(data),
	m_size(data ? size : 0),
	m_bitPos(0),
	m_ok(true)
{
}

uint32_t BitReader::readBits(int bits)
{
	if (!m_ok) {
		return 0;
	}
	if (bits < 1 || bits > 32 || size_t(bits) > bitsRemaining()) {
		m_ok = false;
		return 0;
	}
	uint64_t value = 0;
	int done = 0;
	while (done < bits) {
		const size_t byteIndex = m_bitPos >> 3;
		const int offset = int(m_bitPos & 7);
		const int chunk = std::min(8 - offset, bits - done);
		const uint32_t part = (uint32_t(m_data[byteIndex]) >> offset) & ((1u << chunk) - 1u);
		value |= uint64_t(part) << done;
		done += chunk;
		m_bitPos += size_t(chunk);
	}
	return uint32_t(value);
}

bool BitReader::readBool()
{
	return readBits(1) != 0;
}

uint8_t BitReader::readU8()
{
	return uint8_t(readBits(8));
}

uint16_t BitReader::readU16()
{
	return uint16_t(readBits(16));
}

uint32_t BitReader::readU32()
{
	return readBits(32);
}

uint64_t BitReader::readU64()
{
	const uint64_t lo = readBits(32);
	const uint64_t hi = readBits(32);
	return m_ok ? (lo | (hi << 32)) : 0;
}

uint64_t BitReader::readVarU()
{
	uint64_t value = 0;
	for (int i = 0; i < 10; ++i) {
		const uint8_t byte = readU8();
		if (!m_ok) {
			return 0;
		}
		// The 10th byte may only carry the last bit of a 64 bit value.
		if (i == 9 && byte > 1) {
			m_ok = false;
			return 0;
		}
		value |= uint64_t(byte & 0x7F) << (7 * i);
		if ((byte & 0x80) == 0) {
			return value;
		}
	}
	m_ok = false;
	return 0;
}

int64_t BitReader::readVarI()
{
	const uint64_t v = readVarU();
	return int64_t(v >> 1) ^ -int64_t(v & 1);
}

bool BitReader::readString(std::string &out)
{
	out.clear();
	const uint64_t len = readVarU();
	if (!m_ok || len > 255 || len * 8 > bitsRemaining()) {
		m_ok = false;
		return false;
	}
	out.resize(size_t(len));
	for (size_t i = 0; i < len; ++i) {
		out[i] = char(readU8());
	}
	return m_ok;
}

float BitReader::readQuantized(float min, float max, int bits)
{
	if (!(min < max) || bits < 1 || bits > 32) {
		m_ok = false;
		return 0.0f;
	}
	const uint32_t q = readBits(bits);
	return m_ok ? dequantizeRange(q, min, max, bits) : 0.0f;
}

void BitReader::alignToByte()
{
	if (!m_ok) {
		return;
	}
	const int offset = int(m_bitPos & 7);
	if (offset != 0) {
		m_bitPos += size_t(8 - offset);
	}
}

size_t BitReader::bitsRemaining() const
{
	return m_ok ? (m_size * 8 - m_bitPos) : 0;
}

bool BitReader::ok() const
{
	return m_ok;
}

void BitReader::fail()
{
	m_ok = false;
}

size_t BitReader::bitPosition() const
{
	return m_bitPos;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Quantization
 * \{ */

void writeFloat32(BitWriter &w, float v)
{
	uint32_t bits;
	std::memcpy(&bits, &v, sizeof(bits));
	w.writeU32(bits);
}

float readFloat32(BitReader &r)
{
	const uint32_t bits = r.readU32();
	float v;
	std::memcpy(&v, &bits, sizeof(v));
	return v;
}

uint32_t quantizeRange(float v, float min, float max, int bits)
{
	if (!(min < max) || bits < 1 || bits > 32) {
		return 0;
	}
	const double maxq = double(maxQuantized(bits));
	const double t = (double(v) - double(min)) / (double(max) - double(min)) * maxq;
	// Also catches NaN.
	if (!(t > 0.0)) {
		return 0;
	}
	if (t >= maxq) {
		return maxQuantized(bits);
	}
	return uint32_t(std::round(t));
}

float dequantizeRange(uint32_t q, float min, float max, int bits)
{
	if (!(min < max) || bits < 1 || bits > 32) {
		return 0.0f;
	}
	const uint32_t maxq = maxQuantized(bits);
	if (q > maxq) {
		q = maxq;
	}
	return float(double(min) + (double(max) - double(min)) * double(q) / double(maxq));
}

int32_t quantizePositionAxis(float v, int bits)
{
	if (bits < kMinPositionBits || bits > kMaxPositionBits) {
		return 0;
	}
	const double lo = -std::ldexp(1.0, bits - 1);
	const double hi = std::ldexp(1.0, bits - 1) - 1.0;
	const double mm = double(v) * 1000.0;
	if (std::isnan(mm)) {
		return 0;
	}
	if (mm <= lo) {
		return int32_t(int64_t(lo));
	}
	if (mm >= hi) {
		return int32_t(int64_t(hi));
	}
	return int32_t(std::round(mm));
}

float dequantizePositionAxis(int32_t q)
{
	return float(double(q) / 1000.0);
}

QuantizedRotation quantizeRotation(const float quat[4], int bitsPerComponent)
{
	double q[4] = {double(quat[0]), double(quat[1]), double(quat[2]), double(quat[3])};
	const double len = std::sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
	if (!(len > 1e-12) || std::isinf(len)) {
		// Degenerate input: identity.
		q[0] = q[1] = q[2] = 0.0;
		q[3] = 1.0;
	}
	else {
		for (double &c : q) {
			c /= len;
		}
	}

	// Lowest index wins on ties so q and -q pick the same component.
	uint32_t largest = 0;
	for (uint32_t i = 1; i < 4; ++i) {
		if (std::fabs(q[i]) > std::fabs(q[largest])) {
			largest = i;
		}
	}
	const double sign = (q[largest] < 0.0) ? -1.0 : 1.0;

	QuantizedRotation result;
	result.largest = largest;
	const float range = float(kSmallestThreeRange);
	for (uint32_t i = 0, j = 0; i < 4; ++i) {
		if (i == largest) {
			continue;
		}
		result.comps[j++] = quantizeRange(float(q[i] * sign), -range, range, bitsPerComponent);
	}
	return result;
}

void dequantizeRotation(const QuantizedRotation &rot, int bitsPerComponent, float quat[4])
{
	const float range = float(kSmallestThreeRange);
	double q[4];
	double sum = 0.0;
	for (uint32_t i = 0, j = 0; i < 4; ++i) {
		if (i == (rot.largest & 3)) {
			continue;
		}
		q[i] = double(dequantizeRange(rot.comps[j++], -range, range, bitsPerComponent));
		sum += q[i] * q[i];
	}
	q[rot.largest & 3] = std::sqrt(std::max(0.0, 1.0 - sum));
	const double len = std::sqrt(sum + q[rot.largest & 3] * q[rot.largest & 3]);
	for (int i = 0; i < 4; ++i) {
		quat[i] = float(q[i] / len);
	}
}

void writePosition(BitWriter &w, const float pos[3], const PositionQuant &quant)
{
	if (quant.bits < kMinPositionBits || quant.bits > kMaxPositionBits) {
		w.fail();
		return;
	}
	const int64_t offset = int64_t(1) << (quant.bits - 1);
	for (int i = 0; i < 3; ++i) {
		const int32_t q = quantizePositionAxis(pos[i], quant.bits);
		w.writeBits(uint32_t(int64_t(q) + offset), quant.bits);
	}
}

bool readPosition(BitReader &r, float pos[3], const PositionQuant &quant)
{
	if (quant.bits < kMinPositionBits || quant.bits > kMaxPositionBits) {
		r.fail();
	}
	const int64_t offset = int64_t(1) << (std::max(quant.bits, 1) - 1);
	for (int i = 0; i < 3; ++i) {
		const uint32_t u = r.readBits(quant.bits);
		pos[i] = r.ok() ? dequantizePositionAxis(int32_t(int64_t(u) - offset)) : 0.0f;
	}
	return r.ok();
}

void writeRotation(BitWriter &w, const float quat[4], int bitsPerComponent)
{
	if (bitsPerComponent < kMinRotationBits || bitsPerComponent > kMaxRotationBits) {
		w.fail();
		return;
	}
	const QuantizedRotation q = quantizeRotation(quat, bitsPerComponent);
	w.writeBits(q.largest, 2);
	for (uint32_t c : q.comps) {
		w.writeBits(c, bitsPerComponent);
	}
}

bool readRotation(BitReader &r, float quat[4], int bitsPerComponent)
{
	if (bitsPerComponent < kMinRotationBits || bitsPerComponent > kMaxRotationBits) {
		r.fail();
	}
	QuantizedRotation q;
	q.largest = r.readBits(2);
	for (uint32_t &c : q.comps) {
		c = r.readBits(bitsPerComponent);
	}
	if (!r.ok()) {
		quat[0] = quat[1] = quat[2] = 0.0f;
		quat[3] = 1.0f;
		return false;
	}
	dequantizeRotation(q, bitsPerComponent, quat);
	return true;
}

/** \} */

}  // namespace net
