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

/** \file KX_ProbeVolume.cpp
 *  \ingroup ketsji
 */

#include "KX_ProbeVolume.h"

#include "KX_Camera.h"
#include "KX_GameObject.h"
#include "KX_ClientObjectInfo.h"
#include "KX_RayCast.h"
#include "KX_Scene.h"

#include "GPU_texture.h"

#include "DNA_object_types.h"
#include "DNA_texture_types.h"

#include "CM_Message.h"

#include <algorithm>
#include <cfloat>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cstring>

static const int qualityFaces[3] = {2, 4, 8};
static const int qualityMaxProbes[3] = {64, 128, 256};
/// Face size of the shared capture cube: the SH9 reader reads at most 16 px anyway.
static const int CAPTURE_SIZE = 16;

static EnvMap *volume_env(float clipEnd, int ignoreLayers)
{
	static EnvMap env;
	memset(&env, 0, sizeof(env));
	env.clipsta = 0.1f;
	env.clipend = clipEnd;
	// Coarser LODs: the capture is 16 px and only its average light is kept.
	env.lodfactor = 2.0f;
	env.notlay = ignoreLayers;
	return &env;
}

static double ms_since(std::chrono::steady_clock::time_point start)
{
	return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
}

KX_ProbeVolume::KX_ProbeVolume(KX_GameObject *box, float spacing, Quality quality, float clipEnd, int ignoreLayers, bool freeze,
                               float ssgiWeight, float bounce)
	:KX_CubeMap(volume_env(clipEnd, ignoreLayers), box),
	m_spacing(spacing),
	m_clipEnd(clipEnd),
	m_ssgiWeight(ssgiWeight),
	m_bounce(bounce),
	m_atlas(nullptr),
	m_atlasDirty(false),
	m_cube(nullptr),
	m_current(-1),
	m_nextFace(0),
	m_capturePos(mt::zero3),
	m_facesPerFrame(qualityFaces[quality]),
	m_freeze(freeze),
	m_stopCapture(false),
	m_frozen(false),
	m_classified(false),
	m_activeProbes(0),
	m_frame(0),
	m_cycleDone(0),
	m_cycleStart(-1.0)
{
	// Box half extents: the Empty drawn as Cube (display size * scale), like the probe box parallax.
	mt::vec3 half(1.0f, 1.0f, 1.0f);
	Object *ob = box->GetBlenderObject();
	const mt::vec3 scale = box->NodeGetWorldScaling();
	const float drawSize = (ob && ob->type == OB_EMPTY) ? ob->empty_drawsize : 1.0f;
	for (int i = 0; i < 3; i++) {
		half[i] = std::max(fabsf(scale[i]) * drawSize, 0.01f);
	}

	const int maxProbes = qualityMaxProbes[quality];
	const float wanted = m_spacing;
	for (;;) {
		int total = 1;
		for (int i = 0; i < 3; i++) {
			m_dims[i] = std::max(2, (int)std::ceil(2.0f * half[i] / m_spacing) + 1);
			total *= m_dims[i];
		}
		if (total <= maxProbes) {
			break;
		}
		m_spacing *= 1.1f;
	}
	if (m_spacing > wanted * 1.01f) {
		CM_Warning("probe volume \"" << box->GetName() << "\": spacing " << wanted << " m gives more than " <<
		           maxProbes << " probes, using " << m_spacing << " m");
	}

	// The grid is axis aligned: a rotated Empty would show a box the probes don't follow.
	const mt::mat3 rot = box->NodeGetWorldOrientation();
	for (int i = 0; i < 3; i++) {
		if (fabsf(rot(i, i) - 1.0f) > 1e-3f) {
			CM_Warning("probe volume \"" << box->GetName() << "\": the Empty is rotated, the grid ignores the rotation "
			           "(it stays aligned to the world axes)");
			break;
		}
	}

	const mt::vec3 center = box->NodeGetWorldPosition();
	m_min = center - half;
	m_max = center + half;
	for (int z = 0; z < m_dims[2]; z++) {
		for (int y = 0; y < m_dims[1]; y++) {
			for (int x = 0; x < m_dims[0]; x++) {
				const int idx[3] = {x, y, z};
				Probe probe;
				for (int i = 0; i < 3; i++) {
					probe.position[i] = center[i] - half[i] + 2.0f * half[i] * (float)idx[i] / (float)(m_dims[i] - 1);
				}
				memset(probe.sh, 0, sizeof(probe.sh));
				probe.valid = false;
				probe.lastFrame = -1;
				probe.dirty = false;
				probe.disabled = false;
				m_probes.push_back(probe);
			}
		}
	}

	CM_Message("probe volume \"" << box->GetName() << "\": " << m_dims[0] << "x" << m_dims[1] << "x" << m_dims[2] <<
	           " probes, " << m_facesPerFrame << " faces per frame" << (m_freeze ? ", freeze" : ""));
}

KX_ProbeVolume::~KX_ProbeVolume()
{
	if (m_cube) {
		for (Face& face : m_faces) {
			face.DetachTexture(m_cube);
		}
		GPU_texture_free(m_cube);
	}
	if (m_atlas) {
		GPU_texture_free(m_atlas);
	}
	for (Reader& reader : m_readers) {
		if (reader.reader) {
			GPU_cube_sh9_reader_free(reader.reader);
		}
	}
}

std::string KX_ProbeVolume::GetName()
{
	return "KX_ProbeVolume";
}

const std::vector<KX_ProbeVolume::Probe>& KX_ProbeVolume::GetProbes() const
{
	return m_probes;
}

const int *KX_ProbeVolume::GetDims() const
{
	return m_dims;
}

KX_ProbeVolume::Stats& KX_ProbeVolume::GetStats()
{
	return m_stats;
}

int KX_ProbeVolume::GetFaceBudget() const
{
	/* Warm up: until the bounces settle the first time the budget is big (the readers cap it), so
	 * the light is ready soon after the start instead of fading in over many seconds. */
	return m_warmup ? std::max(m_facesPerFrame, 24) : m_facesPerFrame;
}

bool KX_ProbeVolume::IsIdle() const
{
	return m_idle;
}

void KX_ProbeVolume::Wake()
{
	if (m_idle) {
		CM_Message("probe volume \"" << GetViewpointObject()->GetName() << "\": light changed, capturing again");
	}
	m_idle = false;
	m_stableCycles = 0;
	m_cycleDelta = 0.0f;
}

int KX_ProbeVolume::GetFacesPerFrame() const
{
	return m_facesPerFrame;
}

KX_ProbeVolume::Reader *KX_ProbeVolume::FreeReader()
{
	for (Reader& reader : m_readers) {
		if (reader.probe == -1) {
			return &reader;
		}
	}
	return nullptr;
}

int KX_ProbeVolume::PickNextProbe(const mt::vec3& cameraPos) const
{
	/* Near the camera first, but every probe has a deadline of 2 cycles: an overdue (or never
	 * captured) probe goes before the others, so the far ones don't stall. */
	const int cycleFrames = std::max(1, m_activeProbes * 6 / m_facesPerFrame);
	const float maxDist = m_spacing * (float)(m_dims[0] + m_dims[1] + m_dims[2]);
	int best = -1;
	float bestKey = 0.0f;
	for (int i = 0; i < (int)m_probes.size(); i++) {
		const Probe& probe = m_probes[i];
		bool inFlight = false;
		for (const Reader& reader : m_readers) {
			inFlight |= (reader.probe == i);
		}
		if (inFlight || probe.disabled) {
			continue;
		}
		const int age = (probe.lastFrame < 0) ? (1 << 30) : (m_frame - probe.lastFrame);
		const float dist = (probe.position - cameraPos).Length() / maxDist;
		float key = dist - (float)std::min(age, 2 * cycleFrames) / (float)cycleFrames;
		if (age >= 2 * cycleFrames) {
			key = dist - 1000.0f;
		}
		else if (probe.dirty) {
			key = dist - 500.0f;
		}
		if (best == -1 || key < bestKey) {
			best = i;
			bestKey = key;
		}
	}
	return best;
}

namespace {

/// Static collision meshes, the ones the grid captures.
struct SurfaceFilter
{
	/// Same layers the capture skips (probe_volume_ignore_layers).
	int m_ignoreLayers = 0;
	bool m_hit;
	mt::vec3 m_point;
	mt::vec3 m_normal;

	bool NeedRayCast(KX_ClientObjectInfo *client, void *UNUSED(data))
	{
		KX_GameObject *gameobj = client->m_gameobject;
		return gameobj && !client->isSensor() && !gameobj->GetMeshList().empty() && gameobj->GetVisible() &&
		       !(gameobj->GetLayer() & m_ignoreLayers) && !KX_ProbeVolume::SkipObject(gameobj);
	}

	bool RayHit(KX_ClientObjectInfo *UNUSED(client), KX_RayCast *result, void *UNUSED(data))
	{
		m_hit = true;
		m_point = result->m_hitPoint;
		m_normal = result->m_hitNormal;
		return true;
	}
};

bool surface_ray(PHY_IPhysicsEnvironment *env, const mt::vec3& from, const mt::vec3& to, SurfaceFilter& filter)
{
	filter.m_hit = false;
	// Face normal: Bullet turns the normal toward the ray, a back hit would look like a front one.
	KX_RayCast::Callback<SurfaceFilter, void> callback(&filter, nullptr, nullptr, true);
	KX_RayCast::RayTest(env, from, to, callback);
	return filter.m_hit;
}

}

void KX_ProbeVolume::ClassifyProbes()
{
	m_classified = true;
	m_activeProbes = (int)m_probes.size();
	KX_GameObject *box = GetViewpointObject();
	KX_Scene *scene = box ? box->GetScene() : nullptr;
	PHY_IPhysicsEnvironment *env = scene ? scene->GetPhysicsEnvironment() : nullptr;
	if (!env) {
		return;
	}
	static const mt::vec3 axes[6] = {mt::axisX3, -mt::axisX3, mt::axisY3, -mt::axisY3, mt::axisZ3, -mt::axisZ3};
	// Room the probe keeps from a surface it faces, and how far a buried probe looks for the back.
	const float keep = std::min(0.3f * m_spacing, 0.5f);
	const float reach = 0.5f * m_spacing;
	const float start = 0.05f;
	int pushed = 0, disabled = 0;
	// Containment test reach: a ray from outside back to the probe finds the solid it is in.
	const float inside = std::min(4.0f * m_spacing, m_clipEnd);
	SurfaceFilter filter;
	filter.m_ignoreLayers = GetIgnoreLayers();
	auto inBox = [&](const mt::vec3& p) {
		for (int i = 0; i < 3; i++) {
			if (p[i] < m_min[i] - 1e-3f || p[i] > m_max[i] + 1e-3f) {
				return false;
			}
		}
		return true;
	};
	/* Buried test at p. Returns true when p is behind a surface or inside a solid, with in r_free the
	 * nearest free point along the axes inside the grid box (p when there is none). */
	auto buried = [&](const mt::vec3& p, mt::vec3 *r_free) {
		bool hidden = false;
		float bestMove = FLT_MAX;
		for (const mt::vec3& dir : axes) {
			// The back of a surface within reach: the free side is right past it.
			if (surface_ray(env, p, p + dir * reach, filter) && mt::dot(filter.m_normal, dir) > 0.0f) {
				hidden = true;
				const float move = mt::dot(filter.m_point - p, dir) + keep;
				// Only toward the grid box: a probe in the middle of a wall has the outside as close.
				if (move < bestMove && inBox(p + dir * move)) {
					bestMove = move;
					*r_free = p + dir * move;
				}
				continue;
			}
			/* Inside a convex collider (Box, Convex Hull): a ray starting inside it hits nothing, so
			 * the back face test misses. A ray from outside back to p hits the solid's face while
			 * the ray from p out hits nothing, only at its start, or only beyond that face (it went
			 * through the solid it started in, e.g. to the room wall behind). */
			const mt::vec3 outside = p + dir * inside;
			if (!surface_ray(env, outside, p, filter) || mt::dot(filter.m_normal, dir) <= 0.0f) {
				continue;
			}
			const float face = mt::dot(filter.m_point - p, dir);
			bool out = false;
			if (surface_ray(env, p, outside, filter)) {
				const float hit = mt::dot(filter.m_point - p, dir);
				out = hit > 1e-3f && hit <= face + 1e-3f && filter.m_normal.LengthSquared() > 0.25f;
			}
			if (!out) {
				hidden = true;
				if (face + keep < bestMove && inBox(p + dir * (face + keep))) {
					bestMove = face + keep;
					*r_free = p + dir * (face + keep);
				}
			}
		}
		if (bestMove == FLT_MAX) {
			*r_free = p;
		}
		return hidden;
	};
	int moved = 0;
	for (Probe& probe : m_probes) {
		/* Buried (inside a wall, under the floor, in a box): first moved to the free side when that
		 * stays in the grid box, then off the surfaces; still buried after that = disabled (filled
		 * from its neighbors, see Dilate). */
		mt::vec3 free;
		// Up to once per axis: a probe in a corner is inside a wall and the floor at once.
		for (int step = 0; step < 3; step++) {
			if (!buried(probe.position, &free) || !inBox(free) || (free - probe.position).LengthSquared() < 1e-8f) {
				break;
			}
			probe.position = free;
			moved += (step == 0);
		}
		/* Push out: a ray that starts a little behind the probe catches the surface it sits on. The
		 * push never goes through a surface (a probe on the floor's edge would leave the room). */
		for (int pass = 0; pass < 2; pass++) {
			mt::vec3 push = mt::zero3;
			for (const mt::vec3& dir : axes) {
				const mt::vec3 from = probe.position - dir * start;
				if (!surface_ray(env, from, probe.position + dir * keep, filter)) {
					continue;
				}
				const float dist = mt::dot(filter.m_point - probe.position, dir);
				if (mt::dot(filter.m_normal, dir) < 0.0f && dist < keep) {
					push -= dir * (keep - std::max(dist, 0.0f));
				}
			}
			/* Never out of the grid box: a probe on its edge sits in the room's wall, not past it. The
			 * crossing ray starts a little ahead: the probe touches the surface it sits on. */
			if (push.LengthSquared() < 1e-8f || !inBox(probe.position + push) ||
			    surface_ray(env, probe.position + push * (start / std::max(push.Length(), start)), probe.position + push, filter)) {
				break;
			}
			probe.position += push;
			pushed += (pass == 0);
		}
		if (buried(probe.position, &free)) {
			probe.disabled = true;
		}
		if (probe.disabled) {
			disabled++;
			m_activeProbes--;
		}
	}
	CM_Message("probe volume \"" << box->GetName() << "\": " << pushed << " probes moved out of a surface, " <<
	           moved << " out of a wall or solid, " << disabled << " inside or behind one disabled");
}

bool KX_ProbeVolume::BeginFrame(const mt::vec3& cameraPos, double now)
{
	if (!m_classified) {
		ClassifyProbes();
	}
	m_frame++;
	if (m_cycleStart < 0.0) {
		m_cycleStart = now;
	}

	const auto start = std::chrono::steady_clock::now();
	bool allValid = true;
	for (Reader& reader : m_readers) {
		if (reader.probe == -1) {
			continue;
		}
		float sh[9][3];
		if (GPU_cube_sh9_reader_poll(reader.reader, sh)) {
			Probe& probe = m_probes[reader.probe];
			// Temporal mix: no flicker when the sun turns slowly (none in the warm up, it only slows it).
			const float a = (probe.valid && !m_warmup) ? 0.5f : 1.0f;
			if (probe.valid) {
				// How much the light still changes (idle mode once it settles).
				for (int c = 0; c < 3; c++) {
					const float change = fabsf(sh[0][c] - probe.sh[0][c]) / std::max(fabsf(probe.sh[0][c]), 0.05f);
					m_cycleDelta = std::max(m_cycleDelta, change);
				}
			}
			else {
				m_cycleDelta = 1.0f;
			}
			for (int k = 0; k < 9; k++) {
				for (int c = 0; c < 3; c++) {
					probe.sh[k][c] += (sh[k][c] - probe.sh[k][c]) * a;
				}
			}
			probe.valid = true;
			reader.probe = -1;
			m_atlasDirty = true;
		}
	}
	const double readMs = ms_since(start);
	m_stats.readMs += readMs;
	m_stats.readMaxMs = std::max(m_stats.readMaxMs, readMs);
	if (m_atlasDirty) {
		Dilate();
	}

	for (const Probe& probe : m_probes) {
		allValid &= (probe.valid || probe.disabled);
	}
	/* Freeze: after one full cycle no new capture starts; the readbacks still in flight land over
	 * the next frames, then the grid stays as it is. */
	if (m_freeze && !m_stopCapture && allValid && m_cycleDone >= m_activeProbes) {
		m_stopCapture = true;
		m_current = -1;
	}
	if (m_stopCapture && !m_frozen) {
		bool idle = true;
		for (const Reader& reader : m_readers) {
			idle &= (reader.probe == -1);
		}
		if (idle) {
			m_frozen = true;
			CM_Message("probe volume \"" << GetViewpointObject()->GetName() << "\": frozen after the first cycle");
		}
	}
	if (m_idle) {
		// A moved object marked probes near it: capture them (and settle again).
		for (const Probe& probe : m_probes) {
			if (probe.dirty) {
				Wake();
				break;
			}
		}
	}
	return !m_stopCapture && !m_idle;
}

bool KX_ProbeVolume::NextFaceRange(int budget, const mt::vec3& cameraPos, int *r_first, int *r_count)
{
	if (budget <= 0 || m_probes.empty()) {
		return false;
	}
	if (m_current == -1) {
		/* A probe starts only with a reader free for its SH9: the shared cube is reused by the next
		 * probe right after the readback request. */
		if (!FreeReader()) {
			m_stats.readerWaits++;
			return false;
		}
		m_current = PickNextProbe(cameraPos);
		if (m_current == -1) {
			return false;
		}
		m_nextFace = 0;
		// Fixed at start: the box may move between the frames of one capture.
		m_capturePos = m_probes[m_current].position;
	}
	*r_first = m_nextFace;
	*r_count = std::min(6 - m_nextFace, budget);
	return true;
}

void KX_ProbeVolume::FacesDone(int count, double now)
{
	m_stats.faces += count;
	m_nextFace += count;
	if (m_nextFace < 6) {
		return;
	}

	Reader *reader = FreeReader();
	// NextFaceRange only starts a probe with a free reader, and nothing else takes one.
	if (!reader) {
		m_current = -1;
		return;
	}
	if (!reader->reader) {
		reader->reader = GPU_cube_sh9_reader_create();
	}
	const auto start = std::chrono::steady_clock::now();
	const bool accepted = GPU_cube_sh9_reader_request(reader->reader, m_cube);
	const double readMs = ms_since(start);
	m_stats.readMs += readMs;
	m_stats.requestMs += readMs;
	m_stats.readMaxMs = std::max(m_stats.readMaxMs, readMs);
	if (!accepted) {
		// Recapture the probe later; the cube content is lost once the next probe renders.
		m_current = -1;
		return;
	}

	reader->probe = m_current;
	m_probes[m_current].lastFrame = m_frame;
	m_probes[m_current].dirty = false;
	m_current = -1;
	m_stats.probesDone++;
	if (++m_cycleDone % std::max(1, m_activeProbes) == 0) {
		m_stats.lastCycleSeconds = now - m_cycleStart;
		m_cycleStart = now;
		// Below 2 % change for 2 cycles in a row: the light is settled, stop capturing.
		bool dirty = false;
		for (const Probe& probe : m_probes) {
			dirty |= probe.dirty;
		}
		m_stableCycles = (m_cycleDelta < 0.02f && !dirty) ? m_stableCycles + 1 : 0;
		m_cycleDelta = 0.0f;
		if (m_stableCycles >= 2 && !m_freeze) {
			m_idle = true;
			m_warmup = false;
			m_current = -1;
			CM_Message("probe volume \"" << GetViewpointObject()->GetName() << "\": light settled, idle until something changes");
		}
	}
}

void KX_ProbeVolume::Dilate()
{
	/* A disabled probe (in a wall, under the floor) takes the mean of its captured neighbors: with
	 * weight 0 the lookups next to walls would fall back to the old diffuse (a dark band). A second
	 * pass also reads the probes filled by the first (corners). */
	const int dx = m_dims[0], dy = m_dims[1], dz = m_dims[2];
	for (int pass = 0; pass < 2; pass++) {
		for (int z = 0; z < dz; z++) {
			for (int y = 0; y < dy; y++) {
				for (int x = 0; x < dx; x++) {
					Probe& probe = m_probes[(z * dy + y) * dx + x];
					if (!probe.disabled) {
						continue;
					}
					float sum[9][3] = {};
					int count = 0;
					for (int nz = std::max(z - 1, 0); nz <= std::min(z + 1, dz - 1); nz++) {
						for (int ny = std::max(y - 1, 0); ny <= std::min(y + 1, dy - 1); ny++) {
							for (int nx = std::max(x - 1, 0); nx <= std::min(x + 1, dx - 1); nx++) {
								const Probe& other = m_probes[(nz * dy + ny) * dx + nx];
								if (!other.valid || (other.disabled && pass == 0) || &other == &probe) {
									continue;
								}
								for (int k = 0; k < 9; k++) {
									for (int c = 0; c < 3; c++) {
										sum[k][c] += other.sh[k][c];
									}
								}
								count++;
							}
						}
					}
					if (count == 0 || (pass == 1 && probe.valid)) {
						continue;
					}
					for (int k = 0; k < 9; k++) {
						for (int c = 0; c < 3; c++) {
							probe.sh[k][c] = sum[k][c] / count;
						}
					}
					probe.valid = true;
				}
			}
		}
	}
}

float KX_ProbeVolume::BoxWeight(const mt::vec3& pos) const
{
	float outside = 0.0f;
	for (int i = 0; i < 3; i++) {
		outside = std::max(outside, std::max(m_min[i] - pos[i], pos[i] - m_max[i]));
	}
	return std::min(std::max(1.0f - outside / (0.5f * m_spacing), 0.0f), 1.0f);
}

float KX_ProbeVolume::BoxOverlap(const mt::vec3& aabbMin, const mt::vec3& aabbMax) const
{
	float inter = 1.0f;
	for (int i = 0; i < 3; i++) {
		const float ext = aabbMax[i] - aabbMin[i];
		if (ext < 1e-3f) {
			// Flat axis (a floor plane): inside or not.
			const float mid = 0.5f * (aabbMin[i] + aabbMax[i]);
			inter *= (mid >= m_min[i] && mid <= m_max[i]) ? 1.0f : 0.0f;
			continue;
		}
		inter *= std::min(std::max(std::min(aabbMax[i], m_max[i]) - std::max(aabbMin[i], m_min[i]), 0.0f) / ext, 1.0f);
	}
	return inter;
}

float KX_ProbeVolume::SampleSH(const mt::vec3& pos, float r_sh[9][3]) const
{
	const float weight = BoxWeight(pos);
	if (weight <= 0.0f) {
		return 0.0f;
	}

	int i0[3];
	float f[3];
	for (int i = 0; i < 3; i++) {
		const float size = std::max(m_max[i] - m_min[i], 1e-4f);
		const float t = std::min(std::max((pos[i] - m_min[i]) / size, 0.0f), 1.0f) * (float)(m_dims[i] - 1);
		i0[i] = std::min((int)t, m_dims[i] - 2);
		f[i] = t - (float)i0[i];
	}

	memset(r_sh, 0, sizeof(float) * 27);
	float sum = 0.0f;
	for (int c = 0; c < 8; c++) {
		const int x = i0[0] + (c & 1), y = i0[1] + ((c >> 1) & 1), z = i0[2] + ((c >> 2) & 1);
		const Probe& probe = m_probes[(z * m_dims[1] + y) * m_dims[0] + x];
		if (!probe.valid) {
			continue;
		}
		const float w = ((c & 1) ? f[0] : 1.0f - f[0]) * (((c >> 1) & 1) ? f[1] : 1.0f - f[1]) *
		                (((c >> 2) & 1) ? f[2] : 1.0f - f[2]);
		if (w <= 0.0f) {
			continue;
		}
		for (int k = 0; k < 9; k++) {
			for (int ch = 0; ch < 3; ch++) {
				r_sh[k][ch] += probe.sh[k][ch] * w;
			}
		}
		sum += w;
	}
	if (sum < 1e-4f) {
		return 0.0f;
	}
	for (int k = 0; k < 9; k++) {
		for (int ch = 0; ch < 3; ch++) {
			r_sh[k][ch] /= sum;
		}
	}
	// While some of the 8 are not read yet the grid fades in over the old diffuse.
	return weight * std::min(sum, 1.0f);
}

float KX_ProbeVolume::AverageLight() const
{
	float sum = 0.0f;
	int count = 0;
	for (const Probe& probe : m_probes) {
		if (probe.valid) {
			sum += (probe.sh[0][0] + probe.sh[0][1] + probe.sh[0][2]) / 3.0f;
			count++;
		}
	}
	return count ? sum / count : 0.0f;
}

float KX_ProbeVolume::GetBounce() const
{
	return m_bounce;
}

float KX_ProbeVolume::GetSSGIWeight() const
{
	return m_ssgiWeight;
}

const mt::vec3& KX_ProbeVolume::GetMin() const
{
	return m_min;
}

const mt::vec3& KX_ProbeVolume::GetMax() const
{
	return m_max;
}

float KX_ProbeVolume::GetSpacing() const
{
	return m_spacing;
}

GPUTexture *KX_ProbeVolume::GetAtlas() const
{
	return m_atlas;
}

GPUTexture *KX_ProbeVolume::UpdateAtlas()
{
	if (!m_atlasDirty) {
		return m_atlas;
	}
	m_atlasDirty = false;
	const int dx = m_dims[0], dy = m_dims[1], dz = m_dims[2];
	if (!m_atlas) {
		// 9 slabs along z, one per SH9 coefficient (see probe_grid_sample in the material GLSL).
		m_atlas = GPU_texture_create_3D_half(dx, dy, dz * 9);
		if (!m_atlas) {
			return nullptr;
		}
		m_atlasData.assign((size_t)dx * dy * dz * 9 * 4, 0.0f);
	}
	for (int z = 0; z < dz; z++) {
		for (int y = 0; y < dy; y++) {
			for (int x = 0; x < dx; x++) {
				const Probe& probe = m_probes[(z * dy + y) * dx + x];
				const float read = probe.valid ? 1.0f : 0.0f;
				for (int k = 0; k < 9; k++) {
					float *texel = &m_atlasData[((((size_t)k * dz + z) * dy + y) * dx + x) * 4];
					for (int c = 0; c < 3; c++) {
						texel[c] = probe.sh[k][c] * read;
					}
					texel[3] = read;
				}
			}
		}
	}
	GPU_texture_update_3D_float(m_atlas, m_atlasData.data());
	return m_atlas;
}

void KX_ProbeVolume::CheckMovedObjects(const std::vector<KX_GameObject *>& objects)
{
	// Updated in place: each entry keeps the check number that last saw its object.
	const int check = ++m_moveCheck;
	for (KX_GameObject *gameobj : objects) {
		const mt::vec3 pos = gameobj->NodeGetWorldPosition();
		auto it = m_objectPos.find(gameobj);
		if (it == m_objectPos.end()) {
			m_objectPos.emplace(gameobj, ObjectPos{pos, check});
			// Added after the start (Add Object, made visible): the probes that see it update.
			if (check > 1) {
				for (Probe& probe : m_probes) {
					if ((probe.position - pos).Length() <= m_clipEnd) {
						probe.dirty = true;
					}
				}
			}
			continue;
		}
		it->second.check = check;
		const mt::vec3 old = it->second.pos;
		if ((pos - old).Length() <= 0.25f) {
			continue;
		}
		it->second.pos = pos;
		/* The probes that see it (old or new place) are recaptured first; frozen grids stay as
		 * they are. */
		for (Probe& probe : m_probes) {
			if ((probe.position - pos).Length() <= m_clipEnd || (probe.position - old).Length() <= m_clipEnd) {
				probe.dirty = true;
			}
		}
	}
	// Objects gone (or out of reach) drop out; a new object at a reused address only marks too much.
	for (auto it = m_objectPos.begin(); it != m_objectPos.end();) {
		if (it->second.check == check) {
			++it;
			continue;
		}
		// Gone (ended, hidden): the probes that saw it update.
		for (Probe& probe : m_probes) {
			if ((probe.position - it->second.pos).Length() <= m_clipEnd) {
				probe.dirty = true;
			}
		}
		it = m_objectPos.erase(it);
	}
}

bool KX_ProbeVolume::SkipObject(KX_GameObject *gameobj)
{
	return gameobj->IsDynamic() || gameobj->GetDeformer() || gameobj->GetProperty("probe_volume_skip");
}

bool KX_ProbeVolume::SetupCamera(KX_Camera *sceneCamera, KX_Camera *camera)
{
	if (!m_cube) {
		char err[256] = "";
		m_cube = GPU_texture_create_cube(CAPTURE_SIZE, GPU_HDR_HALF_FLOAT, err);
		if (!m_cube) {
			CM_Error("probe volume: " << err);
			return false;
		}
		for (Face& face : m_faces) {
			face.AttachTexture(m_cube);
		}
	}
	camera->NodeSetWorldPosition(m_capturePos);
	return true;
}

void KX_ProbeVolume::BeginRender(RAS_Rasterizer *)
{
	// The cube is owned here, not taken from a material texture.
}

void KX_ProbeVolume::EndRender(RAS_Rasterizer *)
{
	// 16 px cube read at mip 0: no mipmaps. The SH9 request is made by FacesDone.
}
