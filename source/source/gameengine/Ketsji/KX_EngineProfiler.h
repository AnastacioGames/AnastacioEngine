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

/** \file KX_EngineProfiler.h
 *  \ingroup ketsji
 *  \brief Engine-side profiler: named CPU/GPU stages and a spike log (docs/engine-profiling.md).
 *
 * RANGE_PROFILE=<file> turns it on at startup; the debug overlay (Profile) toggles it while
 * running. Off, every measurement point costs one branch.
 */

#ifndef __KX_ENGINEPROFILER_H__
#define __KX_ENGINEPROFILER_H__

#include <string>

namespace KX_EngineProfiler {

/// Starts from RANGE_PROFILE; changed by SetEnabled at the end of a frame.
extern bool g_enabled;
inline bool Enabled()
{
	return g_enabled;
}
/// Takes effect at the next frame end. Without RANGE_PROFILE the file is range_profile.txt
/// in the working directory.
void SetEnabled(bool enabled);
/// Requested state (what the overlay checkbox shows).
bool IsRequested();
/// Absolute path of the log file.
const std::string& GetPath();
/// RANGE_PROFILE_SYNC=1 or the overlay: glFinish at the end of the frame so GPU time is
/// attributed to its frame.
bool SyncGpu();
void SetSyncGpu(bool sync);

/// Registers a stage name once (call from a function-local static) and returns its id.
int Register(const char *name);
double NowMs();
void AddCpu(int id, double ms);
/// Opens this frame's GPU timestamps (first stamp) and collects the oldest frame in flight.
void BeginGpuFrame();
/// GL timestamp marking the end of stage id on the GPU; read back a few frames later.
void GpuStamp(int id);
/// Free text attached to this frame's spike line (e.g. scenes added).
void Note(const std::string& text);

/// Called by KX_KetsjiEngine once per frame with its profile categories (ms).
void EndFrame(double nowSec, const double *categoryMs, const std::string *labels, int numCategories);

/// Adds the time of the enclosing block to a named stage.
class Scope
{
public:
	explicit Scope(int id)
		:m_id(id),
		m_start(g_enabled ? NowMs() : 0.0)
	{
	}
	~Scope()
	{
		// m_start == 0: turned on inside the scope, nothing to add.
		if (g_enabled && m_start != 0.0) {
			AddCpu(m_id, NowMs() - m_start);
		}
	}

private:
	int m_id;
	double m_start;
};

/// Splits a sequence of statements into named stages: each Mark ends the stage started at the
/// previous Mark (or at construction), on the CPU and, with gpu=true, on the GPU.
class Sections
{
public:
	Sections()
		:m_last(g_enabled ? NowMs() : 0.0)
	{
	}
	void Mark(int id, bool gpu)
	{
		if (g_enabled) {
			const double now = NowMs();
			if (m_last == 0.0) {
				// Turned on after construction: start from here.
				m_last = now;
				return;
			}
			AddCpu(id, now - m_last);
			m_last = now;
			if (gpu) {
				GpuStamp(id);
			}
		}
	}

private:
	double m_last;
};

}  // namespace KX_EngineProfiler

#define RANGE_PROFILE_CAT2(a, b) a##b
#define RANGE_PROFILE_CAT(a, b) RANGE_PROFILE_CAT2(a, b)

/// Times the rest of the enclosing block as stage `name`.
#define RANGE_PROFILE_SCOPE(name) \
	static const int RANGE_PROFILE_CAT(rangeProfId, __LINE__) = KX_EngineProfiler::Register(name); \
	KX_EngineProfiler::Scope RANGE_PROFILE_CAT(rangeProfScope, __LINE__)(RANGE_PROFILE_CAT(rangeProfId, __LINE__))

/// Ends the current stage of a Sections object as `name` (CPU only, or CPU + GPU).
#define RANGE_PROFILE_MARK(sections, name) \
	do { static const int rangeProfId = KX_EngineProfiler::Register(name); (sections).Mark(rangeProfId, false); } while (0)
#define RANGE_PROFILE_MARK_GPU(sections, name) \
	do { static const int rangeProfId = KX_EngineProfiler::Register(name); (sections).Mark(rangeProfId, true); } while (0)

/// Adds ms measured by hand to stage `name`.
#define RANGE_PROFILE_ADD(name, ms) \
	do { if (KX_EngineProfiler::Enabled()) { static const int rangeProfId = KX_EngineProfiler::Register(name); KX_EngineProfiler::AddCpu(rangeProfId, (ms)); } } while (0)

#endif  // __KX_ENGINEPROFILER_H__
