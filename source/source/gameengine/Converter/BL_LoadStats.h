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

#include <mutex>
#include <string>
#include <vector>

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

/// Recent load events ("[Load]" reports) kept for the Debug Mode profile panel.
/// Written only on load (never per frame); bounded so it never grows during a session.
class BL_LoadLog
{
public:
	struct Entry
	{
		std::string scene;   // Scene or library the event belongs to.
		std::string stage;   // "convert", "shaders", "startup total"...
		double seconds;      // Duration of this stage.
		std::string detail;  // Full console line (tooltip).
		bool total;          // Wall time of a whole load (highlighted).
	};

	static void Add(const std::string& scene, const std::string& stage, double seconds,
	                const std::string& detail = "", bool total = false)
	{
		BL_LoadLog& log = Get();
		std::lock_guard<std::mutex> lock(log.m_mutex);
		if (log.m_entries.size() >= maxEntries) {
			log.m_entries.erase(log.m_entries.begin());
		}
		log.m_entries.push_back({scene, stage, seconds, detail, total});
	}

	/// Copy, since conversion may run on a worker thread.
	static std::vector<Entry> GetEntries()
	{
		BL_LoadLog& log = Get();
		std::lock_guard<std::mutex> lock(log.m_mutex);
		return log.m_entries;
	}

	static void Clear()
	{
		BL_LoadLog& log = Get();
		std::lock_guard<std::mutex> lock(log.m_mutex);
		log.m_entries.clear();
	}

private:
	static const size_t maxEntries = 64;
	std::mutex m_mutex;
	std::vector<Entry> m_entries;

	static BL_LoadLog& Get()
	{
		static BL_LoadLog log;
		return log;
	}
};

#endif  // __BL_LOADSTATS_H__
