/* SPDX-License-Identifier: GPL-2.0-or-later */

/** \file net_test_util.h
 *  Shared helpers for the network core tests.
 */

#pragma once

#include "NET_Messages.h"
#include "NET_Snapshot.h"

#include <cstdint>
#include <vector>

namespace net_test {

/** Small deterministic PRNG (xorshift64*), same sequence on every platform. */
class Rng {
public:
	explicit Rng(uint64_t seed) : m_state(seed ? seed : 0x9E3779B97F4A7C15ull) {}
	uint64_t next()
	{
		m_state ^= m_state >> 12;
		m_state ^= m_state << 25;
		m_state ^= m_state >> 27;
		return m_state * 0x2545F4914F6CDD1Dull;
	}
	uint32_t below(uint32_t n)
	{
		return n ? uint32_t(next() % n) : 0;
	}

private:
	uint64_t m_state;
};

/** Config with one quantized float property range (index 2 of every object). */
inline net::SnapshotConfig testConfig()
{
	net::SnapshotConfig cfg;
	cfg.floatRange = [](net::NetId, uint16_t index, net::FloatRange &r) {
		if (index != 2) {
			return false;
		}
		r.min = -10.0f;
		r.max = 10.0f;
		r.bits = 12;
		return true;
	};
	return cfg;
}

inline net::ObjectState makeObject(net::NetId id, float x, float y, float z)
{
	net::ObjectState o;
	o.netId = id;
	o.fields = net::FIELD_TRANSFORM | net::FIELD_VELOCITY;
	o.position[0] = x;
	o.position[1] = y;
	o.position[2] = z;
	o.rotation[0] = 0.0f;
	o.rotation[1] = 0.0f;
	o.rotation[2] = 0.38268343f;
	o.rotation[3] = 0.92387953f;
	o.velocity[0] = 1.5f;
	o.velocity[1] = -2.25f;
	o.velocity[2] = 0.0f;
	return o;
}

inline net::Snapshot makeSampleSnapshot(net::Tick tick)
{
	net::Snapshot s;
	s.tick = tick;
	s.objects.push_back(makeObject(3, 1.0f, 2.0f, 3.0f));
	net::ObjectState b = makeObject(17, -100.5f, 0.001f, 42.0f);
	b.fields |= net::FIELD_ANGULAR_VELOCITY | net::FIELD_PROPS | net::FIELD_ANIM;
	b.angularVelocity[0] = 0.5f;
	b.angularVelocity[1] = -3.0f;
	b.angularVelocity[2] = 10.0f;
	b.props.push_back(net::PropValue::makeBool(0, true));
	b.props.push_back(net::PropValue::makeInt(1, -12345));
	b.props.push_back(net::PropValue::makeFloat(2, 3.25f));
	b.props.push_back(net::PropValue::makeFloat(5, 0.1f));
	b.anim.action = 4;
	b.anim.frame = 12.5f;
	s.objects.push_back(b);
	s.objects.push_back(makeObject(0x80000001u, 0.0f, 0.0f, -5.0f));
	return s;
}

inline std::vector<uint8_t> encodeSnap(const net::Snapshot &cur, const net::Snapshot *base,
                                       const net::SnapshotConfig &cfg)
{
	std::vector<uint8_t> out;
	net::BitWriter w(out);
	net::encodeSnapshot(w, cur, base, cfg);
	return w.ok() ? out : std::vector<uint8_t>();
}

} // namespace net_test
