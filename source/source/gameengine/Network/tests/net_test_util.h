/* Shared helpers for the network tests. */

#ifndef __NET_TEST_UTIL_H__
#define __NET_TEST_UTIL_H__

#include <cstdint>
#include <string>
#include <vector>

namespace net_test {

/// Deterministic generator (splitmix64), same sequence on every platform.
class Rng {
public:
	explicit Rng(uint64_t seed) : m_state(seed)
	{
	}
	uint64_t next()
	{
		uint64_t z = (m_state += 0x9e3779b97f4a7c15ull);
		z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull;
		z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
		return z ^ (z >> 31);
	}
	uint32_t below(uint32_t n)
	{
		return n ? uint32_t(next() % n) : 0;
	}
	/// Uniform in [lo, hi] with 24 bit resolution.
	float uniform(float lo, float hi)
	{
		return lo + (hi - lo) * float(next() >> 40) / float(1 << 24);
	}

private:
	uint64_t m_state;
};

/// True when golden files must be rewritten (NET_UPDATE_GOLDEN=1 or --update-golden).
bool updateGolden();
void setUpdateGolden(bool update);

}  // namespace net_test

#endif  // __NET_TEST_UTIL_H__
