/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file BL_LoadStats.h
 *  \ingroup bgeconv
 *
 * Load timing per stage (scene conversion and LibLoad), printed to the console as "[Load]" lines.
 * Accumulators are thread_local because asynchronous LibLoad converts in a worker thread: each
 * conversion resets the stats of its own thread, runs, and reports from that same thread.
 */

#ifndef __BL_LOADSTATS_H__
#define __BL_LOADSTATS_H__

#include "PIL_time.h"

struct BL_LoadStats
{
	double mesh = 0.0;      // BL_ConvertMesh total (includes normals and tangents).
	double tangent = 0.0;   // MikkTSpace tangents only.
	double physics = 0.0;   // BL_CreatePhysicsObjectNew.
	double loopHash = 0.0;  // Content hash of meshes for the normal/tangent cache.
	int meshes = 0;         // Meshes actually converted.
	int meshesReused = 0;   // Requests served by an already converted mesh.
	int tangentMeshes = 0;  // Meshes that needed tangents (have UVs).
	int loopDataReused = 0; // Meshes whose normals/tangents came from an identical mesh.

	void Reset()
	{
		*this = BL_LoadStats();
	}

	static BL_LoadStats& Get()
	{
		static thread_local BL_LoadStats stats;
		return stats;
	}
};

/// Adds the elapsed time of its scope to an accumulator.
class BL_LoadTimer
{
private:
	double& m_acc;
	const double m_start;

public:
	explicit BL_LoadTimer(double& acc)
		:m_acc(acc),
		m_start(PIL_check_seconds_timer())
	{
	}

	~BL_LoadTimer()
	{
		m_acc += PIL_check_seconds_timer() - m_start;
	}
};

#endif  // __BL_LOADSTATS_H__
