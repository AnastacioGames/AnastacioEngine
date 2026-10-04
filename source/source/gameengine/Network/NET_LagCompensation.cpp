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

/** \file gameengine/Network/NET_LagCompensation.cpp
 *  \ingroup network
 */

#include "NET_LagCompensation.h"

#include "NET_Snapshot.h"  // slerp

#include <algorithm>
#include <cmath>
#include <limits>

namespace net {

namespace {

/// v rotated by the inverse of the x,y,z,w quaternion q.
void rotateInverse(const float q[4], const float v[3], float out[3])
{
	float x = -q[0], y = -q[1], z = -q[2], w = q[3];
	const float len = std::sqrt(x * x + y * y + z * z + w * w);
	if (len > 0.0f) {
		x /= len;
		y /= len;
		z /= len;
		w /= len;
	}
	else {
		x = y = z = 0.0f;
		w = 1.0f;
	}
	// t = 2 * cross(q.xyz, v); out = v + w * t + cross(q.xyz, t)
	const float tx = 2.0f * (y * v[2] - z * v[1]);
	const float ty = 2.0f * (z * v[0] - x * v[2]);
	const float tz = 2.0f * (x * v[1] - y * v[0]);
	out[0] = v[0] + w * tx + (y * tz - z * ty);
	out[1] = v[1] + w * ty + (z * tx - x * tz);
	out[2] = v[2] + w * tz + (x * ty - y * tx);
}

float dot3(const float a[3], const float b[3])
{
	return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

/// Entry distance of a ray into a sphere at c; 0 when the origin is inside.
bool raySphere(const float o[3], const float d[3], const float c[3], float r, float &t)
{
	const float m[3] = {o[0] - c[0], o[1] - c[1], o[2] - c[2]};
	const float cc = dot3(m, m) - r * r;
	if (cc <= 0.0f) {
		t = 0.0f;
		return true;
	}
	const float b = dot3(m, d);
	if (b > 0.0f) {
		return false;
	}
	const float disc = b * b - cc;
	if (disc < 0.0f) {
		return false;
	}
	t = -b - std::sqrt(disc);
	return t >= 0.0f;
}

bool rayBox(const float o[3], const float d[3], const float half[3], float &t)
{
	float tmin = 0.0f;
	float tmax = std::numeric_limits<float>::max();
	for (int i = 0; i < 3; ++i) {
		const float h = std::fabs(half[i]);
		if (std::fabs(d[i]) < 1e-9f) {
			if (o[i] < -h || o[i] > h) {
				return false;
			}
			continue;
		}
		float t1 = (-h - o[i]) / d[i];
		float t2 = (h - o[i]) / d[i];
		if (t1 > t2) {
			std::swap(t1, t2);
		}
		tmin = std::max(tmin, t1);
		tmax = std::min(tmax, t2);
		if (tmin > tmax) {
			return false;
		}
	}
	t = tmin;
	return true;
}

bool rayCapsule(const float o[3], const float d[3], float r, float h, float &t)
{
	h = std::fabs(h);
	r = std::fabs(r);
	bool hit = false;
	float best = std::numeric_limits<float>::max();
	// Side of the cylinder around the Z segment.
	const float a = d[0] * d[0] + d[1] * d[1];
	const float c = o[0] * o[0] + o[1] * o[1] - r * r;
	if (c <= 0.0f && std::fabs(o[2]) <= h) {
		t = 0.0f;
		return true;
	}
	if (a > 1e-12f) {
		const float b = o[0] * d[0] + o[1] * d[1];
		const float disc = b * b - a * c;
		if (disc >= 0.0f) {
			const float tc = (-b - std::sqrt(disc)) / a;
			const float z = o[2] + tc * d[2];
			if (tc >= 0.0f && z >= -h && z <= h) {
				best = tc;
				hit = true;
			}
		}
	}
	// End caps.
	for (int s = -1; s <= 1; s += 2) {
		const float cap[3] = {0.0f, 0.0f, float(s) * h};
		float ts;
		if (raySphere(o, d, cap, r, ts) && ts < best) {
			best = ts;
			hit = true;
		}
	}
	if (hit) {
		t = best;
	}
	return hit;
}

bool hitboxLess(const Hitbox &a, const Hitbox &b)
{
	return a.id != b.id ? a.id < b.id : a.part < b.part;
}

}  // namespace

bool rayHitbox(const float origin[3], const float dir[3], float maxDistance, const Hitbox &box, float &distance)
{
	if (!(maxDistance >= 0.0f)) {
		return false;
	}
	const float rel[3] = {origin[0] - box.center[0], origin[1] - box.center[1], origin[2] - box.center[2]};
	float o[3], d[3];
	rotateInverse(box.rotation, rel, o);
	rotateInverse(box.rotation, dir, d);
	const float zero[3] = {0.0f, 0.0f, 0.0f};
	float t = 0.0f;
	bool hit = false;
	switch (box.shape) {
		case HitShape::Sphere:
			hit = raySphere(o, d, zero, std::fabs(box.radius), t);
			break;
		case HitShape::Capsule:
			hit = rayCapsule(o, d, box.radius, box.halfHeight, t);
			break;
		case HitShape::Box:
			hit = rayBox(o, d, box.halfExtents, t);
			break;
	}
	if (!hit || !(t <= maxDistance)) {
		return false;
	}
	distance = t;
	return true;
}

LagCompensation::LagCompensation(const LagCompensationConfig &config) : m_config(config)
{
	if (m_config.tickRate == 0) {
		m_config.tickRate = 60;
	}
}

uint32_t LagCompensation::maxRewindTicks() const
{
	return uint32_t(uint64_t(m_config.maxRewindMs) * m_config.tickRate / 1000);
}

void LagCompensation::record(Tick tick, const std::vector<Hitbox> &hitboxes)
{
	if (tick == kNoTick) {
		return;
	}
	if (!m_frames.empty()) {
		if (m_frames.back().tick == tick) {
			m_frames.pop_back();
		}
		else if (!tickNewer(tick, m_frames.back().tick)) {
			return;
		}
	}
	Frame frame{tick, hitboxes};
	std::sort(frame.hitboxes.begin(), frame.hitboxes.end(), hitboxLess);
	m_frames.push_back(std::move(frame));

	const uint32_t keep = uint32_t(uint64_t(m_config.historyMs) * m_config.tickRate / 1000) + 1;
	while (m_frames.size() > 1 && tick - m_frames.front().tick > keep) {
		m_frames.pop_front();
	}
}

void LagCompensation::clear()
{
	m_frames.clear();
}

Tick LagCompensation::oldestTick() const
{
	return m_frames.empty() ? kNoTick : m_frames.front().tick;
}

Tick LagCompensation::newestTick() const
{
	return m_frames.empty() ? kNoTick : m_frames.back().tick;
}

size_t LagCompensation::findAtOrBefore(Tick tick) const
{
	// Frames are in tick order; binary search on the distance to the newest one.
	const Tick newest = m_frames.back().tick;
	const auto it = std::upper_bound(m_frames.begin(), m_frames.end(), tick, [newest](Tick t, const Frame &f) {
		return int32_t(t - newest) < int32_t(f.tick - newest);
	});
	return it == m_frames.begin() ? 0 : size_t(std::prev(it) - m_frames.begin());
}

bool LagCompensation::sample(Tick tick, float alpha, Tick nowTick, std::vector<Hitbox> &out, Tick *usedTick,
                             float *usedAlpha) const
{
	out.clear();
	if (m_frames.empty()) {
		return false;
	}
	const Tick newest = m_frames.back().tick;
	if (!(alpha >= 0.0f)) {
		alpha = 0.0f;
	}
	alpha = std::min(alpha, 1.0f);

	// Everything relative to the newest frame, in ticks.
	double rewind = double(int32_t(nowTick - tick)) - double(alpha);
	rewind = std::min(std::max(rewind, 0.0), double(maxRewindTicks()));
	double target = double(int32_t(nowTick - newest)) - rewind;
	target = std::min(target, 0.0);
	target = std::max(target, double(int32_t(m_frames.front().tick - newest)));

	const double whole = std::floor(target);
	const Tick baseTick = newest + Tick(int32_t(whole));
	const float frac = float(target - whole);

	const size_t index = findAtOrBefore(baseTick);
	const Frame *a = &m_frames[index];
	const Frame *b = index + 1 < m_frames.size() ? &m_frames[index + 1] : a;

	float u = 0.0f;
	if (b != a) {
		const double span = double(b->tick - a->tick);
		u = float((double(int32_t(baseTick - a->tick)) + frac) / span);
		u = std::min(std::max(u, 0.0f), 1.0f);
	}
	if (usedTick) {
		*usedTick = baseTick;
	}
	if (usedAlpha) {
		*usedAlpha = frac;
	}

	out = a->hitboxes;
	if (b == a || u == 0.0f) {
		return true;
	}
	for (Hitbox &h : out) {
		const auto it = std::lower_bound(b->hitboxes.begin(), b->hitboxes.end(), h, hitboxLess);
		if (it == b->hitboxes.end() || it->id != h.id || it->part != h.part) {
			continue;
		}
		for (int i = 0; i < 3; ++i) {
			h.center[i] += (it->center[i] - h.center[i]) * u;
		}
		float rot[4];
		slerp(h.rotation, it->rotation, u, rot);
		std::copy(rot, rot + 4, h.rotation);
	}
	return true;
}

bool LagCompensation::raycast(const float origin[3], const float dir[3], float maxDistance, Tick tick, float alpha,
                              Tick nowTick, RayHit &hit, NetId ignore) const
{
	std::vector<Hitbox> boxes;
	Tick usedTick = kNoTick;
	float usedAlpha = 0.0f;
	if (!sample(tick, alpha, nowTick, boxes, &usedTick, &usedAlpha)) {
		return false;
	}
	float d[3] = {dir[0], dir[1], dir[2]};
	const float len = std::sqrt(dot3(d, d));
	if (!(len > 0.0f)) {
		return false;
	}
	for (float &c : d) {
		c /= len;
	}
	bool found = false;
	float best = maxDistance;
	for (const Hitbox &box : boxes) {
		if (box.id == ignore && ignore != kInvalidNetId) {
			continue;
		}
		float t;
		if (rayHitbox(origin, d, best, box, t) && (!found || t < best)) {
			found = true;
			best = t;
			hit.id = box.id;
			hit.part = box.part;
		}
	}
	if (found) {
		hit.distance = best;
		for (int i = 0; i < 3; ++i) {
			hit.point[i] = origin[i] + d[i] * best;
		}
		hit.tick = usedTick;
		hit.alpha = usedAlpha;
	}
	return found;
}

}  // namespace net
