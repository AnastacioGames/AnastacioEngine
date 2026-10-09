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

/** \file CM_WorkCounters.h
 *  \ingroup common
 *
 * Per-frame counters of "update work": transforms, bounds, matrices and dirty notifications.
 * In a scene where nothing moves they should stay near zero; a counter that stays at the
 * object count points to work redone every frame on unchanged data (e.g. the always-set
 * RAS_MeshBoundingBox modified flag). Read through bge.logic.getRenderStats().
 */

#ifndef __CM_WORK_COUNTERS_H__
#define __CM_WORK_COUNTERS_H__

#include <atomic>

enum CM_WorkCounter {
	CM_WORK_SCENE_NODE_UPDATES = 0,
	CM_WORK_TRANSFORM_SYNCS,
	CM_WORK_BOUNDS_PUSHES,
	CM_WORK_MESH_MATRIX_CHANGES,
	CM_WORK_UPDATE_NOTIFIES,
	/// GL calls (uniforms + shadow texture binds) uploading lights/shadow lamps per draw.
	CM_WORK_LIGHT_UNIFORMS,
	/// glUniform calls of the material's dynamic inputs (GPU_pass_update_uniforms) per bind.
	CM_WORK_PASS_UNIFORMS,
	CM_WORK_COUNTER_MAX
};

/// Counters of the frame in progress; atomic because the culling runs in TBB tasks.
inline std::atomic<int> *CM_WorkCountersCurrent()
{
	static std::atomic<int> counters[CM_WORK_COUNTER_MAX] = {};
	return counters;
}

/// Counters of the last finished frame.
inline int *CM_WorkCountersLast()
{
	static int counters[CM_WORK_COUNTER_MAX] = {};
	return counters;
}

inline void CM_WorkCount(CM_WorkCounter counter, int value = 1)
{
	CM_WorkCountersCurrent()[counter].fetch_add(value, std::memory_order_relaxed);
}

/// Called once at the start of a frame: publish the previous frame and restart.
inline void CM_WorkCountersSwap()
{
	for (int i = 0; i < CM_WORK_COUNTER_MAX; ++i) {
		CM_WorkCountersLast()[i] = CM_WorkCountersCurrent()[i].exchange(0, std::memory_order_relaxed);
	}
}

inline int CM_WorkCountLast(CM_WorkCounter counter)
{
	return CM_WorkCountersLast()[counter];
}

#endif  // __CM_WORK_COUNTERS_H__
