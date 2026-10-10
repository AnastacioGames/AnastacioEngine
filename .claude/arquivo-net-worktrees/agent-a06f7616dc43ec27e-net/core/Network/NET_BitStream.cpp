/* SPDX-License-Identifier: GPL-2.0-or-later */

/** \file NET_BitStream.cpp
 */

#include "NET_BitStream.h"

#include <cmath>
#include <cstring>

namespace net {

/* -------------------------------------------------------------------- */
/* BitWriter */

BitWriter::BitWriter(std::vector<uint8_t> &out)
	:m_out(out),
	m_startBit(out.size() * 8),
	m_bit(out.size() * 8),
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
	if (bits < 32) {
		value &= (uint32_t(1) << bits) - 1u;
	}
	int done = 0;
	while (done < bits) {
		const size_t byte = m_bit >> 3;
		const int offset = int(m_bit & 7);
		if (offset == 0) {
			m_out.push_back(0);
		}
		const int n = (8 - offset < bits - done) ? (8 - offset) : (bits - done);
		const uint32_t chunk = (value >> done) & ((uint32_t(1) << n) - 1u);
		m_out[byte] = uint8_t(m_out[byte] | (chunk << offset));
		done += n;
		m_bit += size_t(n);
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
	writeBits(uint32_t(v & 0xFFFFFFFFu), 32);
	writeBits(uint32_t(v >> 32), 32);
}

void BitWriter::writeVarU(uint64_t v)
{
	do {
		uint8_t byte = uint8_t(v & 0x7Fu);
		v >>= 7;
		if (v != 0) {
			byte |= 0x80u;
		}
		writeU8(byte);
	} while (v != 0);
}

void BitWriter::writeVarI(int64_t v)
{
	const uint64_t zz = (uint64_t(v) << 1) ^ uint64_t(v >> 63);
	writeVarU(zz);
}

void BitWriter::writeString(std::string_view s)
{
	if (s.size() > 255) {
		m_ok = false;
		return;
	}
	writeVarU(s.size());
	writeBytes(reinterpret_cast<const uint8_t *>(s.data()), s.size());
}

void BitWriter::writeFloat(float v)
{
	uint32_t u;
	std::memcpy(&u, &v, sizeof(u));
	writeU32(u);
}

void BitWriter::writeQuantized(float v, float min, float max, int bits)
{
	if (bits < 1 || bits > 32) {
		m_ok = false;
		return;
	}
	writeBits(quantizeRange(v, min, max, bits), bits);
}

void BitWriter::writeBytes(const uint8_t *data, size_t size)
{
	for (size_t i = 0; i < size; ++i) {
		writeU8(data[i]);
	}
}

void BitWriter::alignToByte()
{
	if (!m_ok) {
		return;
	}
	/* Bytes are pushed whole, so aligning only moves the cursor. */
	m_bit = (m_bit + 7) & ~size_t(7);
}

size_t BitWriter::bitsWritten() const
{
	return m_bit - m_startBit;
}

bool BitWriter::ok() const
{
	return m_ok;
}

void BitWriter::fail()
{
	m_ok = false;
}

/* -------------------------------------------------------------------- */
/* BitReader */

BitReader::BitReader(const uint8_t *data, size_t size)
	:m_data(data),
	m_sizeBits(data ? size * 8 : 0),
	m_pos(0),
	m_ok(true)
{
}

uint32_t BitReader::readBits(int bits)
{
	if (!m_ok) {
		return 0;
	}
	if (bits < 1 || bits > 32 || size_t(bits) > m_sizeBits - m_pos) {
		m_ok = false;
		return 0;
	}
	uint32_t value = 0;
	int done = 0;
	while (done < bits) {
		const size_t byte = m_pos >> 3;
		const int offset = int(m_pos & 7);
		const int n = (8 - offset < bits - done) ? (8 - offset) : (bits - done);
		const uint32_t chunk = (uint32_t(m_data[byte]) >> offset) & ((uint32_t(1) << n) - 1u);
		value |= chunk << done;
		done += n;
		m_pos += size_t(n);
	}
	return value;
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
	if (!m_ok) {
		return 0;
	}
	return lo | (hi << 32);
}

uint64_t BitReader::readVarU()
{
	uint64_t value = 0;
	for (int i = 0; i < 10; ++i) {
		const uint8_t byte = readU8();
		if (!m_ok) {
			return 0;
		}
		const uint64_t payload = byte & 0x7Fu;
		/* 10th byte may only carry the top bit of a 64-bit value. */
		if (i == 9 && payload > 1) {
			m_ok = false;
			return 0;
		}
		value |= payload << (7 * i);
		if ((byte & 0x80u) == 0) {
			return value;
		}
	}
	m_ok = false;
	return 0;
}

int64_t BitReader::readVarI()
{
	const uint64_t zz = readVarU();
	return int64_t((zz >> 1) ^ (~(zz & 1) + 1));
}

bool BitReader::readString(std::string &out)
{
	out.clear();
	const uint64_t len = readVarU();
	if (!m_ok) {
		return false;
	}
	if (len > 255 || len * 8 > bitsRemaining()) {
		m_ok = false;
		return false;
	}
	out.resize(size_t(len));
	for (size_t i = 0; i < size_t(len); ++i) {
		out[i] = char(readU8());
	}
	if (!m_ok) {
		out.clear();
	}
	return m_ok;
}

float BitReader::readFloat()
{
	const uint32_t u = readU32();
	float v;
	std::memcpy(&v, &u, sizeof(v));
	return v;
}

float BitReader::readQuantized(float min, float max, int bits)
{
	if (bits < 1 || bits > 32) {
		m_ok = false;
		return 0.0f;
	}
	const uint32_t q = readBits(bits);
	if (!m_ok) {
		return 0.0f;
	}
	return dequantizeRange(q, min, max, bits);
}

bool BitReader::readBytes(uint8_t *out, size_t size)
{
	if (!m_ok || size * 8 > bitsRemaining()) {
		m_ok = false;
		return false;
	}
	for (size_t i = 0; i < size; ++i) {
		out[i] = readU8();
	}
	return m_ok;
}

void BitReader::alignToByte()
{
	if (!m_ok) {
		return;
	}
	const size_t aligned = (m_pos + 7) & ~size_t(7);
	if (aligned > m_sizeBits) {
		m_ok = false;
		return;
	}
	m_pos = aligned;
}

size_t BitReader::bitsRemaining() const
{
	return m_ok ? m_sizeBits - m_pos : 0;
}

size_t BitReader::bytePosition() const
{
	return (m_pos + 7) >> 3;
}

bool BitReader::ok() const
{
	return m_ok;
}

void BitReader::fail()
{
	m_ok = false;
}

/* -------------------------------------------------------------------- */
/* Quantization */

int64_t quantizePositionAxis(float v, int bits)
{
	if (bits < 16) {
		bits = 16;
	}
	else if (bits > 32) {
		bits = 32;
	}
	const int64_t lo = -(int64_t(1) << (bits - 1));
	const int64_t hi = (int64_t(1) << (bits - 1)) - 1;
	const double mm = double(v) * 1000.0;
	if (std::isnan(mm)) {
		return 0;
	}
	/* Clamp in double first so llround can never overflow. */
	if (mm <= double(lo)) {
		return lo;
	}
	if (mm >= double(hi)) {
		return hi;
	}
	const int64_t q = std::llround(mm); // round half away from zero
	return q < lo ? lo : (q > hi ? hi : q);
}

float dequantizePositionAxis(int64_t q)
{
	return float(double(q) / 1000.0);
}

uint32_t quantizeRange(float v, float min, float max, int bits)
{
	if (bits < 1 || bits > 32) {
		return 0;
	}
	const double maxq = double((uint64_t(1) << bits) - 1u);
	const double range = double(max) - double(min);
	if (!(range > 0.0) || std::isnan(v)) {
		return 0;
	}
	double norm = (double(v) - double(min)) / range;
	if (norm <= 0.0) {
		return 0;
	}
	if (norm >= 1.0) {
		return uint32_t(maxq);
	}
	const int64_t q = std::llround(norm * maxq);
	return uint32_t(q < 0 ? 0 : (double(q) > maxq ? int64_t(maxq) : q));
}

float dequantizeRange(uint32_t q, float min, float max, int bits)
{
	if (bits < 1 || bits > 32) {
		return min;
	}
	const double maxq = double((uint64_t(1) << bits) - 1u);
	const double range = double(max) - double(min);
	if (!(range > 0.0)) {
		return min;
	}
	return float(double(min) + (double(q) / maxq) * range);
}

static const double kInvSqrt2 = 0.70710678118654752440;

static int clampRotationBits(int bits)
{
	return bits < kMinRotationBits ? kMinRotationBits : (bits > kMaxRotationBits ? kMaxRotationBits : bits);
}

QuantizedRotation quantizeRotation(const float quat[4], int bitsPerComponent)
{
	const int bits = clampRotationBits(bitsPerComponent);
	double q[4] = {quat[0], quat[1], quat[2], quat[3]};
	double len2 = 0.0;
	for (int i = 0; i < 4; ++i) {
		if (std::isnan(q[i])) {
			len2 = 0.0;
			break;
		}
		len2 += q[i] * q[i];
	}
	if (!(len2 > 0.0) || std::isinf(len2)) {
		q[0] = q[1] = q[2] = 0.0;
		q[3] = 1.0;
	}
	else {
		const double inv = 1.0 / std::sqrt(len2);
		for (int i = 0; i < 4; ++i) {
			q[i] *= inv;
		}
	}

	int largest = 0;
	for (int i = 1; i < 4; ++i) {
		if (std::fabs(q[i]) > std::fabs(q[largest])) {
			largest = i;
		}
	}
	/* q and -q are the same rotation: make the largest component positive. */
	const double sign = q[largest] < 0.0 ? -1.0 : 1.0;

	QuantizedRotation r;
	r.largest = uint32_t(largest);
	const double maxq = double((1u << bits) - 1u);
	int j = 0;
	for (int i = 0; i < 4; ++i) {
		if (i == largest) {
			continue;
		}
		double norm = (q[i] * sign + kInvSqrt2) / (2.0 * kInvSqrt2);
		norm = norm < 0.0 ? 0.0 : (norm > 1.0 ? 1.0 : norm);
		r.comp[j++] = uint32_t(std::llround(norm * maxq));
	}
	return r;
}

void dequantizeRotation(const QuantizedRotation &r, float quat[4], int bitsPerComponent)
{
	const int bits = clampRotationBits(bitsPerComponent);
	const double maxq = double((1u << bits) - 1u);
	double q[4];
	double sum = 0.0;
	int j = 0;
	const uint32_t largest = r.largest & 3u;
	for (uint32_t i = 0; i < 4; ++i) {
		if (i == largest) {
			continue;
		}
		const double c = (double(r.comp[j++]) / maxq) * (2.0 * kInvSqrt2) - kInvSqrt2;
		q[i] = c;
		sum += c * c;
	}
	q[largest] = std::sqrt(sum < 1.0 ? 1.0 - sum : 0.0);
	for (int i = 0; i < 4; ++i) {
		quat[i] = float(q[i]);
	}
}

void writePosition(BitWriter &w, const float pos[3], const PositionQuant &quant)
{
	const int bits = quant.bitsPerAxis;
	if (bits < 16 || bits > 32) {
		w.fail();
		return;
	}
	const int64_t bias = int64_t(1) << (bits - 1);
	for (int i = 0; i < 3; ++i) {
		const int64_t q = quantizePositionAxis(pos[i], bits);
		w.writeBits(uint32_t(uint64_t(q + bias)), bits); // offset binary
	}
}

bool readPosition(BitReader &r, float pos[3], const PositionQuant &quant)
{
	const int bits = quant.bitsPerAxis;
	if (bits < 16 || bits > 32) {
		r.fail();
	}
	const int64_t bias = (bits >= 16 && bits <= 32) ? (int64_t(1) << (bits - 1)) : 0;
	for (int i = 0; i < 3; ++i) {
		const int64_t u = int64_t(r.readBits(bits));
		pos[i] = r.ok() ? dequantizePositionAxis(u - bias) : 0.0f;
	}
	if (!r.ok()) {
		pos[0] = pos[1] = pos[2] = 0.0f;
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
	for (int i = 0; i < 3; ++i) {
		w.writeBits(q.comp[i], bitsPerComponent);
	}
}

bool readRotation(BitReader &r, float quat[4], int bitsPerComponent)
{
	if (bitsPerComponent < kMinRotationBits || bitsPerComponent > kMaxRotationBits) {
		r.fail();
	}
	QuantizedRotation q;
	q.largest = r.readBits(2);
	for (int i = 0; i < 3; ++i) {
		q.comp[i] = r.readBits(bitsPerComponent);
	}
	if (!r.ok()) {
		quat[0] = quat[1] = quat[2] = 0.0f;
		quat[3] = 1.0f;
		return false;
	}
	dequantizeRotation(q, quat, bitsPerComponent);
	return true;
}

} // namespace net
