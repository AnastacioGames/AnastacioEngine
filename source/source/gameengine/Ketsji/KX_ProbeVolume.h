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

/** \file KX_ProbeVolume.h
 *  \ingroup ketsji
 *  \brief Probe Volume GI: a grid of diffuse probes inside a box Empty, captured a few cube faces
 *  per frame into one shared 16 px cube, each probe keeping only its SH9 (docs/plano-probe-volume-gi.md).
 */

#ifndef __KX_PROBEVOLUME_H__
#define __KX_PROBEVOLUME_H__

#include "KX_CubeMap.h"

#include <unordered_map>
#include <vector>

struct GPUTexture;
struct GPUCubeSH9Reader;

class KX_ProbeVolume : public KX_CubeMap
{
public:
	enum Quality {
		QUALITY_LOW = 0,
		QUALITY_MEDIUM,
		QUALITY_HIGH
	};

	struct Probe {
		mt::vec3 position;
		float sh[9][3];
		/// False until the first SH9 readback of this probe is done.
		bool valid;
		/// Frame of the last finished capture, -1 = never.
		int lastFrame;
		/// An object near it moved: goes before the up-to-date probes (after the overdue ones).
		bool dirty;
	};

	/// Counters for RANGE_PROBE_VOLUME_LOG, reset by the manager after printing.
	struct Stats {
		int faces = 0;
		int objects = 0;
		int readerWaits = 0;
		int probesDone = 0;
		double cpuMs = 0.0;
		double readMs = 0.0;
		double readMaxMs = 0.0;
		/// Readback request (copy to the PBO) alone, the rest of readMs is the poll.
		double requestMs = 0.0;
		double lastCycleSeconds = 0.0;
	};

private:
	enum { NUM_READERS = 4 };

	struct Reader {
		GPUCubeSH9Reader *reader = nullptr;
		/// Probe whose SH9 is in flight, -1 = free.
		int probe = -1;
	};

	std::vector<Probe> m_probes;
	int m_dims[3];
	float m_spacing;
	/// Box corners of the grid (first and last probe), fixed at creation.
	mt::vec3 m_min;
	mt::vec3 m_max;
	float m_clipEnd;
	/// SSGI strength factor with the camera inside the volume (the grid already gives the indirect light).
	float m_ssgiWeight;
	/// Position of each captured object at its last check: moving it past 0.25 m marks the probes near it.
	std::unordered_map<KX_GameObject *, mt::vec3> m_objectPos;
	/// Cube shared by every probe of the grid, reused as soon as its readback is requested.
	GPUTexture *m_cube;
	Reader m_readers[NUM_READERS];

	/// Probe being captured (-1 = none), next face to render and its position fixed at start.
	int m_current;
	int m_nextFace;
	mt::vec3 m_capturePos;

	int m_facesPerFrame;
	bool m_freeze;
	/// Set once a full cycle with every SH9 read is done in freeze mode: the scheduler stops.
	bool m_frozen;
	int m_frame;
	/// Probes finished since the cycle start and when it started (seconds), for the log.
	int m_cycleDone;
	double m_cycleStart;

	Stats m_stats;

	int PickNextProbe(const mt::vec3& cameraPos) const;
	Reader *FreeReader();

public:
	/** \param box Empty drawn as Cube: its box (display size * scale) holds the grid.
	 * \param spacing Wanted distance between probes, grows until the grid fits the quality limit.
	 */
	KX_ProbeVolume(KX_GameObject *box, float spacing, Quality quality, float clipEnd, int ignoreLayers, bool freeze,
	               float ssgiWeight);
	virtual ~KX_ProbeVolume();

	virtual std::string GetName();

	const std::vector<Probe>& GetProbes() const;
	const int *GetDims() const;
	Stats& GetStats();
	int GetFacesPerFrame() const;

	/** Scheduler, called once per frame before the captures: applies the finished readbacks and
	 * returns false when nothing is to be captured (frozen or every reader busy). */
	bool BeginFrame(const mt::vec3& cameraPos, double now);
	/** Face range of the next capture step within the remaining budget; false when the budget is
	 * spent or no reader is free to take a finished probe. */
	bool NextFaceRange(int budget, const mt::vec3& cameraPos, int *r_first, int *r_count);
	/// After rendering r_count faces: a probe with its 6 faces done asks its SH9 readback.
	void FacesDone(int count, double now);

	/** Trilinear SH9 of the 8 probes around pos (only the read ones). Returns its weight: 1 inside
	 * the box, fading to 0 half a spacing outside it, and lower while the probes around are not read yet. */
	float SampleSH(const mt::vec3& pos, float r_sh[9][3]) const;
	/// 1 inside the box, 0 from half a spacing outside it.
	float BoxWeight(const mt::vec3& pos) const;
	float GetSSGIWeight() const;
	/** Moved objects: compares the objects the grid captures with their last position and puts the
	 * probes within clip end of one that moved more than 0.25 m first in the queue. */
	void CheckMovedObjects(const std::vector<KX_GameObject *>& objects);

	/// True for objects the grid must not capture (moving physics, deformed mesh, probe_volume_skip).
	static bool SkipObject(KX_GameObject *gameobj);

	virtual bool SetupCamera(KX_Camera *sceneCamera, KX_Camera *camera);
	virtual void BeginRender(RAS_Rasterizer *rasty);
	virtual void EndRender(RAS_Rasterizer *rasty);
};

#endif  // __KX_PROBEVOLUME_H__
