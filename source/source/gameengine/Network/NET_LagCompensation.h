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

/** \file NET_LagCompensation.h
 *  \ingroup network
 *  \brief Server history of hitbox transforms and raycasts against the past (plan section 5.4).
 *
 * The server records the hitboxes of every tick. A client shot carries the time the client was
 * rendering (tick + alpha, see NetClock::renderTime); the server rewinds to it, clamped to
 * maxRewindMs, and tests the ray against the interpolated hitboxes.
 */

#ifndef __NET_LAG_COMPENSATION_H__
#define __NET_LAG_COMPENSATION_H__

#include "NET_Types.h"

#include <deque>
#include <vector>

namespace net {

enum class HitShape : uint8_t {
	Sphere = 0,
	Capsule = 1,  // segment along the local Z axis
	Box = 2,  // oriented box
};

struct Hitbox {
	NetId id = kInvalidNetId;
	/// Part of the object (head, body...); id + part identifies the hitbox between ticks.
	uint16_t part = 0;
	HitShape shape = HitShape::Sphere;
	float center[3] = {0.0f, 0.0f, 0.0f};
	float rotation[4] = {0.0f, 0.0f, 0.0f, 1.0f};  // x,y,z,w
	/// Sphere and capsule radius.
	float radius = 0.5f;
	/// Capsule: half length of the inner segment. Box: half extents.
	float halfHeight = 0.0f;
	float halfExtents[3] = {0.5f, 0.5f, 0.5f};
};

struct RayHit {
	NetId id = kInvalidNetId;
	uint16_t part = 0;
	float distance = 0.0f;
	float point[3] = {0.0f, 0.0f, 0.0f};
	/// Time actually tested (after clamping).
	Tick tick = kNoTick;
	float alpha = 0.0f;
};

struct LagCompensationConfig {
	uint16_t tickRate = 60;
	/// History kept (plan: about 1 s).
	uint32_t historyMs = 1000;
	/// Furthest a client may rewind; older requests are clamped to it (anti-abuse).
	uint32_t maxRewindMs = 400;
};

/// Ray against one hitbox; dir must be normalized. Returns the entry distance in [0, maxDistance].
bool rayHitbox(const float origin[3], const float dir[3], float maxDistance, const Hitbox &box, float &distance);

class LagCompensation {
public:
	explicit LagCompensation(const LagCompensationConfig &config = LagCompensationConfig());

	/// Stores the hitboxes of tick; ticks must grow. Older entries past historyMs are dropped.
	void record(Tick tick, const std::vector<Hitbox> &hitboxes);
	void clear();

	/// Hitboxes at tick + alpha, interpolated between the two recorded ticks around it.
	/// The time is clamped to [now - maxRewind, newest] and to the history. False when empty.
	bool sample(Tick tick, float alpha, Tick nowTick, std::vector<Hitbox> &out, Tick *usedTick = nullptr,
	            float *usedAlpha = nullptr) const;
	/// Nearest hit at tick + alpha. ignore = shooter's own object.
	bool raycast(const float origin[3], const float dir[3], float maxDistance, Tick tick, float alpha, Tick nowTick,
	             RayHit &hit, NetId ignore = kInvalidNetId) const;

	Tick oldestTick() const;
	Tick newestTick() const;
	uint32_t maxRewindTicks() const;

private:
	struct Frame {
		Tick tick;
		std::vector<Hitbox> hitboxes;  // sorted by id, part
	};

	/// Index of the last frame at or before tick (0 when all are newer).
	size_t findAtOrBefore(Tick tick) const;

	LagCompensationConfig m_config;
	std::deque<Frame> m_frames;
};

}  // namespace net

#endif  // __NET_LAG_COMPENSATION_H__
