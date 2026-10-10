/* SPDX-License-Identifier: GPL-2.0-or-later */

/** \file NET_SnapshotBuffer.h
 *  Circular buffer of snapshots by tick and interpolation (protocol contract v1, section 9.3).
 *  Implemented in NET_Snapshot.cpp.
 */

#pragma once

#include "NET_Snapshot.h"

#include <vector>

namespace net {

class SnapshotBuffer {
public:
	explicit SnapshotBuffer(size_t capacity = kSnapshotHistory);

	/** Stores snap (replaces a snapshot with the same tick). Snapshots older than the window are dropped. */
	void insert(const Snapshot &snap);
	const Snapshot *find(Tick tick) const;
	/** Newest stored tick, 0 if empty. */
	Tick newestTick() const;
	size_t size() const;
	void clear();

	/** Interpolated states at renderTick + alpha (alpha in [0, 1)). Uses the newest snapshot at or before
	 *  that time and the oldest after it: linear position/velocity, slerp rotation. Objects missing from
	 *  the later snapshot are held. Returns false if no snapshot is at or before that time. */
	bool sample(Tick renderTick, float alpha, std::vector<ObjectState> &out) const;

private:
	std::vector<Snapshot> m_slots;
	std::vector<bool> m_used;
	Tick m_newest;
};

/** Shortest-path spherical interpolation of normalized quaternions (x, y, z, w). */
void slerpQuat(const float a[4], const float b[4], float t, float out[4]);

} // namespace net
