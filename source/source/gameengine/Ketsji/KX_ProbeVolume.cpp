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

#include "GPU_texture.h"

#include "DNA_object_types.h"
#include "DNA_texture_types.h"

#include "CM_Message.h"

#include <algorithm>
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
                               float ssgiWeight)
	:KX_CubeMap(volume_env(clipEnd, ignoreLayers), box),
	m_spacing(spacing),
	m_clipEnd(clipEnd),
	m_ssgiWeight(ssgiWeight),
	m_cube(nullptr),
	m_atlas(nullptr),
	m_atlasDirty(false),
	m_current(-1),
	m_nextFace(0),
	m_capturePos(mt::zero3),
	m_facesPerFrame(qualityFaces[quality]),
	m_freeze(freeze),
	m_frozen(false),
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
	const int cycleFrames = std::max(1, (int)m_probes.size() * 6 / m_facesPerFrame);
	const float maxDist = m_spacing * (float)(m_dims[0] + m_dims[1] + m_dims[2]);
	int best = -1;
	float bestKey = 0.0f;
	for (int i = 0; i < (int)m_probes.size(); i++) {
		const Probe& probe = m_probes[i];
		bool inFlight = false;
		for (const Reader& reader : m_readers) {
			inFlight |= (reader.probe == i);
		}
		if (inFlight) {
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

bool KX_ProbeVolume::BeginFrame(const mt::vec3& cameraPos, double now)
{
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
			// Temporal mix: no flicker when the sun turns slowly.
			const float a = probe.valid ? 0.5f : 1.0f;
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

	for (const Probe& probe : m_probes) {
		allValid &= probe.valid;
	}
	if (m_freeze && allValid && m_cycleDone >= (int)m_probes.size()) {
		bool idle = true;
		for (const Reader& reader : m_readers) {
			idle &= (reader.probe == -1);
		}
		if (idle && !m_frozen) {
			m_frozen = true;
			CM_Message("probe volume \"" << GetViewpointObject()->GetName() << "\": frozen after the first cycle");
		}
	}
	return !m_frozen;
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
	if (++m_cycleDone % (int)m_probes.size() == 0) {
		m_stats.lastCycleSeconds = now - m_cycleStart;
		m_cycleStart = now;
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
	std::unordered_map<KX_GameObject *, mt::vec3> positions;
	positions.reserve(objects.size());
	for (KX_GameObject *gameobj : objects) {
		const mt::vec3 pos = gameobj->NodeGetWorldPosition();
		const auto it = m_objectPos.find(gameobj);
		if (it == m_objectPos.end()) {
			positions[gameobj] = pos;
			continue;
		}
		if ((pos - it->second).Length() <= 0.25f) {
			positions[gameobj] = it->second;
			continue;
		}
		positions[gameobj] = pos;
		/* The probes that see it (old or new place) are recaptured first; frozen grids stay as
		 * they are. */
		for (Probe& probe : m_probes) {
			if ((probe.position - pos).Length() <= m_clipEnd || (probe.position - it->second).Length() <= m_clipEnd) {
				probe.dirty = true;
			}
		}
	}
	// Objects gone (or out of reach) drop out; a new object at a reused address only marks too much.
	m_objectPos.swap(positions);
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
