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
 * The Original Code is Copyright (C) 2026 by Range Engine.
 * All rights reserved.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Ketsji/KX_RainAura.cpp
 *  \ingroup ketsji
 */

#include "KX_RainAura.h"
#include "KX_Scene.h"
#include "KX_Camera.h"
#include "KX_GameObject.h"
#include "KX_Mesh.h"
#include "RAS_DisplayArray.h"
#include "SG_CullingNode.h"
#include "EXP_ListValue.h"
#include "CM_Message.h"

#include "DNA_world_types.h"

#include "GPU_glew.h"
#include "GPU_draw.h"

#include <algorithm>
#include <cmath>
#include <map>
#include <tuple>

/// Hard cap on live strokes (the Python prototype needed ~200 at the default amount).
static const unsigned int kMaxStrokes = 4096;
/// The silhouette must point at least this much up (Z is up).
static const float kUp = 0.25f;
/// Strokes per meter of silhouette per second, at amount 1.
static const float kStrokesPerMeter = 900.0f;
static const float kMaxCarry = 120.0f;
/// The stroke sizes were tuned with the camera this far from the objects.
static const float kReferenceDistance = 3.0f;
/// Animated style: fewer spawns, since each drop lives ~12x longer.
static const float kAnimatedRateScale = 0.12f;
/// Animated style: downward pull (per unit of stroke scale) that bends the path.
static const float kAnimatedGravity = 0.35f;
/// How often the list of objects with the aura property is rebuilt (added objects).
static const double kScanInterval = 0.5;

static const char *kVertexSource =
	"#version 130\n"
	"in vec3 in_pos;\n"
	"in float in_bright;\n"
	"out float v_bright;\n"
	"uniform mat4 u_view;\n"
	"uniform mat4 u_projection;\n"
	"void main() {\n"
	"	v_bright = in_bright;\n"
	"	gl_Position = u_projection * (u_view * vec4(in_pos, 1.0));\n"
	"}\n";

static const char *kFragmentSource =
	"#version 130\n"
	"in float v_bright;\n"
	"out vec4 fragColor;\n"
	"uniform float u_intensity;\n"
	"void main() {\n"
	"	fragColor = vec4(vec3(0.85, 0.9, 1.0) * v_bright * u_intensity, 1.0);\n"
	"}\n";

KX_RainAura::KX_RainAura()
	:m_lastTime(-1.0),
	m_animated(false),
	m_nextScan(0.0),
	m_carry(0.0f),
	m_intensity(1.0f),
	m_seed(0x9E3779B9u),
	m_program(0),
	m_vao(0),
	m_vbo(0),
	m_ibo(0),
	m_viewLoc(-1),
	m_projLoc(-1),
	m_intensityLoc(-1),
	m_glFailed(false)
{
	m_strokes.reserve(kMaxStrokes);
}

KX_RainAura::~KX_RainAura()
{
	if (m_vbo) {
		glDeleteBuffers(1, &m_vbo);
	}
	if (m_ibo) {
		glDeleteBuffers(1, &m_ibo);
	}
	if (m_vao) {
		glDeleteVertexArrays(1, &m_vao);
	}
	if (m_program) {
		glDeleteProgram(m_program);
	}
}

float KX_RainAura::Random()
{
	// xorshift32: cheap and plenty for a visual effect.
	m_seed ^= m_seed << 13;
	m_seed ^= m_seed >> 17;
	m_seed ^= m_seed << 5;
	return (float)(m_seed >> 8) * (1.0f / 16777216.0f);
}

void KX_RainAura::RemoveObject(KX_GameObject *gameobj)
{
	m_targets.erase(std::remove(m_targets.begin(), m_targets.end(), gameobj), m_targets.end());
}

void KX_RainAura::RefreshTargets(KX_Scene *scene, const std::string& prop)
{
	std::vector<KX_GameObject *> targets;
	for (KX_GameObject *gameobj : *scene->GetObjectList()) {
		if (gameobj->GetMeshList().empty()) {
			continue;
		}
		EXP_Value *value = gameobj->GetProperty(prop);
		if (value && value->GetNumber() != 0.0) {
			targets.push_back(gameobj);
		}
	}
	if (targets != m_targets) {
		CM_Message("rain aura: " << targets.size() << " object(s) with the game property \"" << prop << "\"");
		m_targets.swap(targets);
		// Meshes of removed objects may have been freed: never keep a stale pointer as key.
		m_edgeCache.clear();
	}
}

const std::vector<KX_RainAura::Edge>& KX_RainAura::GetEdges(RAS_Mesh *mesh)
{
	auto it = m_edgeCache.find(mesh);
	if (it != m_edgeCache.end()) {
		return it->second;
	}

	// Every sharp edge with its two face normals (local space). Vertices are split per
	// material/UV, so edges are matched by quantized position; flat diagonals are skipped.
	typedef std::tuple<int, int, int> Key;
	struct Side {
		mt::vec3 a, b, n;
	};
	std::map<std::pair<Key, Key>, std::vector<Side> > faces;
	const auto key = [](const mt::vec3& v) {
		return Key((int)std::lround(v.x * 10000.0f), (int)std::lround(v.y * 10000.0f), (int)std::lround(v.z * 10000.0f));
	};

	const unsigned int numPolygons = mesh->GetNumPolygons();
	for (unsigned int i = 0; i < numPolygons; ++i) {
		const RAS_Mesh::PolygonInfo poly = mesh->GetPolygon(i);
		mt::vec3 pts[3];
		for (unsigned int j = 0; j < 3; ++j) {
			pts[j] = mt::vec3(poly.array->GetPosition(poly.indices[j]).data);
		}
		mt::vec3 n = mt::cross(pts[1] - pts[0], pts[2] - pts[0]);
		if (n.Length() < 1e-6f) {
			continue;
		}
		n.Normalize();
		for (unsigned int j = 0; j < 3; ++j) {
			const mt::vec3& a = pts[j];
			const mt::vec3& b = pts[(j + 1) % 3];
			Key ka = key(a);
			Key kb = key(b);
			if (kb < ka) {
				std::swap(ka, kb);
			}
			faces[std::make_pair(ka, kb)].push_back({a, b, n});
		}
	}

	std::vector<Edge>& edges = m_edgeCache[mesh];
	for (const auto& item : faces) {
		const std::vector<Side>& sides = item.second;
		if (sides.size() == 2 && mt::dot(sides[0].n, sides[1].n) < 0.9999f) {
			edges.push_back({sides[0].a, sides[0].b, sides[0].n, sides[1].n});
		}
	}
	return edges;
}

void KX_RainAura::Update(KX_Scene *scene, KX_Camera *camera, const World *world, double time)
{
	const double dt = (m_lastTime < 0.0) ? 0.0 : std::min(time - m_lastTime, 0.1);
	m_lastTime = time;

	const bool active = camera && world && (world->weather_flag & WO_WEATHER_RAIN) &&
	                    (world->weather_flag & WO_WEATHER_RAIN_AURA);

	// Expire first, so a disabled aura empties at once; animated drops move along their path.
	for (unsigned int i = 0; i < m_strokes.size();) {
		Stroke& stroke = m_strokes[i];
		if (!active || time >= stroke.death) {
			stroke = m_strokes.back();
			m_strokes.pop_back();
			continue;
		}
		if (stroke.velocity.LengthSquared() > 0.0f) {
			stroke.velocity.z -= stroke.fall * (float)dt;
			stroke.base += stroke.velocity * (float)dt;
			stroke.dir = stroke.velocity.Normalized();
		}
		++i;
	}

	if (!active) {
		m_carry = 0.0f;
		return;
	}
	m_animated = (world->rain_aura_style == WO_RAIN_AURA_ANIMATED);

	const std::string prop = world->rain_aura_prop;
	if (prop != m_prop || time >= m_nextScan) {
		m_prop = prop;
		m_nextScan = time + kScanInterval;
		RefreshTargets(scene, prop);
	}

	const float size = world->rain_aura_size;
	const float rate = world->rain_aura_rate;
	const float maxDist = world->rain_aura_distance;
	m_intensity = world->rain_aura_intensity;
	const mt::vec3 camPos = camera->NodeGetWorldPosition();

	// Silhouette seen from the camera: one face looks at it, the other looks away.
	m_silhouette.clear();
	m_cumulative.clear();
	float total = 0.0f;
	for (KX_GameObject *gameobj : m_targets) {
		if (!gameobj->GetVisible() || gameobj->GetCullingNode().GetCulled()) {
			continue;
		}
		const mt::vec3& pos = gameobj->NodeGetWorldPosition();
		if ((pos - camPos).Length() > maxDist) {
			continue;
		}
		const mt::mat3& ori = gameobj->NodeGetWorldOrientation();
		const mt::vec3& scale = gameobj->NodeGetWorldScaling();
		if (std::abs(scale.x * scale.y * scale.z) < 1e-12f) {
			continue;
		}
		const mt::vec3 invScale(1.0f / scale.x, 1.0f / scale.y, 1.0f / scale.z);
		// Camera in object space: the side test runs on local data, no per-vertex transform.
		const mt::vec3 camLocal = (ori.Transpose() * (camPos - pos)) * invScale;

		for (RAS_Mesh *mesh : gameobj->GetMeshList()) {
			for (const Edge& edge : GetEdges(mesh)) {
				const mt::vec3 viewLocal = camLocal - (edge.a + edge.b) * 0.5f;
				if (mt::dot(edge.n1, viewLocal) * mt::dot(edge.n2, viewLocal) >= 0.0f) {
					continue;
				}
				// Only the accepted edges go to world space.
				const mt::vec3 wa = pos + ori * (edge.a * scale);
				const mt::vec3 wb = pos + ori * (edge.b * scale);
				const mt::vec3 vn = (camPos - (wa + wb) * 0.5f).Normalized();
				// Outward direction of the outline, flattened against the view.
				mt::vec3 out = (ori * (edge.n1 * invScale)).Normalized() + (ori * (edge.n2 * invScale)).Normalized();
				out -= vn * mt::dot(out, vn);
				const float outLen = out.Length();
				if (outLen < 1e-6f) {
					continue;
				}
				out /= outLen;
				if (out.z < kUp) {
					continue;
				}
				// Spawn by length on screen, so far objects are not flooded with strokes.
				const float strokeScale = std::max(0.3f, (camPos - (wa + wb) * 0.5f).Length() / kReferenceDistance);
				total += (wb - wa).Length() / strokeScale;
				m_cumulative.push_back(total);
				m_silhouette.push_back({wa, wb, out, vn, strokeScale});
			}
		}
	}

	const float rateScale = m_animated ? kAnimatedRateScale : 1.0f;
	m_carry = std::min(m_carry + total * kStrokesPerMeter * rate * rateScale * (float)dt, kMaxCarry);
	while (m_carry >= 1.0f && !m_silhouette.empty() && m_strokes.size() < kMaxStrokes) {
		m_carry -= 1.0f;
		const unsigned int index = std::min<unsigned int>(
			std::upper_bound(m_cumulative.begin(), m_cumulative.end(), Random() * total) - m_cumulative.begin(),
			m_silhouette.size() - 1);
		const Silhouette& sil = m_silhouette[index];

		// Fan: rotate the outward direction around the view axis (most near the normal).
		// Sum of 3 uniforms ~ gauss(0, 0.6), clamped to +-1.2 rad.
		const float ang = std::max(-1.2f, std::min(1.2f, (Random() + Random() + Random() - 1.5f) * 1.2f));
		const mt::vec3 side = mt::cross(sil.view, sil.out);
		const mt::vec3 z = (sil.out * std::cos(ang) + side * std::sin(ang)).Normalized();

		const float scale = size * sil.scale;
		Stroke stroke;
		stroke.dir = z;
		stroke.width = (0.0006f + 0.0012f * Random()) * scale;
		stroke.brightness = 0.6f + 0.4f * Random();
		stroke.birth = time;
		if (m_animated) {
			// A drop born on the outline that flies out over a longer, slightly falling path.
			const float life = 0.25f + 0.3f * Random();
			const float path = (0.04f + 0.08f * Random()) * scale;
			stroke.length = (0.006f + 0.008f * Random()) * scale;
			stroke.base = sil.a + (sil.b - sil.a) * Random() + z * (0.002f * Random() * scale);
			stroke.velocity = z * (path / life);
			stroke.fall = kAnimatedGravity * scale;
			stroke.death = time + life;
		}
		else {
			// Manga style: a still stroke a little outside the outline, no trajectory.
			stroke.length = ((Random() < 0.5f) ? (0.002f + 0.003f * Random()) : (0.006f + 0.01f * Random())) * scale;
			stroke.base = sil.a + (sil.b - sil.a) * Random() + z * ((0.001f + 0.011f * Random()) * scale);
			stroke.velocity = mt::zero3;
			stroke.fall = 0.0f;
			// Lives 1 to 3 frames, then pops up somewhere else.
			stroke.death = time + 0.015 + 0.035 * Random();
		}
		m_strokes.push_back(stroke);
	}
}

bool KX_RainAura::EnsureGL()
{
	if (m_program) {
		return true;
	}
	if (m_glFailed) {
		return false;
	}

	GLuint vert = glCreateShader(GL_VERTEX_SHADER);
	glShaderSource(vert, 1, &kVertexSource, nullptr);
	glCompileShader(vert);
	GLuint frag = glCreateShader(GL_FRAGMENT_SHADER);
	glShaderSource(frag, 1, &kFragmentSource, nullptr);
	glCompileShader(frag);

	GLint status;
	GLchar log[1024];
	GLsizei length = 0;
	glGetShaderiv(vert, GL_COMPILE_STATUS, &status);
	if (status) {
		glGetShaderiv(frag, GL_COMPILE_STATUS, &status);
		if (!status) {
			glGetShaderInfoLog(frag, sizeof(log), &length, log);
		}
	}
	else {
		glGetShaderInfoLog(vert, sizeof(log), &length, log);
	}
	if (!status) {
		CM_Error("rain aura shader compile failed:\n" << log);
		glDeleteShader(vert);
		glDeleteShader(frag);
		m_glFailed = true;
		return false;
	}

	m_program = glCreateProgram();
	glAttachShader(m_program, vert);
	glAttachShader(m_program, frag);
	glBindAttribLocation(m_program, 0, "in_pos");
	glBindAttribLocation(m_program, 1, "in_bright");
	glBindFragDataLocation(m_program, 0, "fragColor");
	glLinkProgram(m_program);
	glDeleteShader(vert);
	glDeleteShader(frag);
	glGetProgramiv(m_program, GL_LINK_STATUS, &status);
	if (!status) {
		glGetProgramInfoLog(m_program, sizeof(log), &length, log);
		CM_Error("rain aura shader link failed:\n" << log);
		glDeleteProgram(m_program);
		m_program = 0;
		m_glFailed = true;
		return false;
	}
	m_viewLoc = glGetUniformLocation(m_program, "u_view");
	m_projLoc = glGetUniformLocation(m_program, "u_projection");
	m_intensityLoc = glGetUniformLocation(m_program, "u_intensity");

	// Static index buffer: two triangles per stroke, for the whole capacity.
	std::vector<unsigned int> indices(kMaxStrokes * 6);
	for (unsigned int i = 0; i < kMaxStrokes; ++i) {
		const unsigned int v = i * 4;
		const unsigned int quad[6] = {v, v + 1, v + 2, v, v + 2, v + 3};
		std::copy(quad, quad + 6, indices.begin() + i * 6);
	}

	glGenVertexArrays(1, &m_vao);
	glGenBuffers(1, &m_vbo);
	glGenBuffers(1, &m_ibo);
	glBindVertexArray(m_vao);
	glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
	glBufferData(GL_ARRAY_BUFFER, kMaxStrokes * 4 * 4 * sizeof(float), nullptr, GL_STREAM_DRAW);
	glEnableVertexAttribArray(0);
	glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void *)0);
	glEnableVertexAttribArray(1);
	glVertexAttribPointer(1, 1, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void *)(3 * sizeof(float)));
	glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, m_ibo);
	glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.size() * sizeof(unsigned int), indices.data(), GL_STATIC_DRAW);
	glBindVertexArray(0);
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	return true;
}

void KX_RainAura::Draw(const mt::mat4& view, const mt::mat4& projection)
{
	if (m_strokes.empty() || !EnsureGL()) {
		return;
	}

	// Billboard each stroke around its direction, facing the camera.
	const mt::vec3 camPos = view.Inverse().TranslationVector3D();
	m_vertices.resize(m_strokes.size() * 16);
	float *v = m_vertices.data();
	for (const Stroke& stroke : m_strokes) {
		const mt::vec3& z = stroke.dir;
		mt::vec3 y = camPos - stroke.base;
		y -= z * mt::dot(y, z);
		if (y.Length() < 1e-6f) {
			y = mt::cross(z, mt::axisX3);
		}
		const mt::vec3 x = mt::cross(y.Normalized(), z) * (stroke.width * 0.5f);
		const mt::vec3 head = stroke.base + z * stroke.length;
		const mt::vec3 corner[4] = {stroke.base - x, stroke.base + x, head + x, head - x};

		float bright = stroke.brightness;
		if (stroke.velocity.LengthSquared() > 0.0f) {
			// Quick fade in, long fade out over the path.
			const float t = (float)((m_lastTime - stroke.birth) / (stroke.death - stroke.birth));
			bright *= std::min(1.0f, t * 8.0f) * std::max(0.0f, 1.0f - t);
		}
		for (unsigned int i = 0; i < 4; ++i) {
			*v++ = corner[i].x;
			*v++ = corner[i].y;
			*v++ = corner[i].z;
			*v++ = bright;
		}
	}

	glUseProgram(m_program);
	glUniformMatrix4fv(m_viewLoc, 1, GL_FALSE, (const float *)view.Data());
	glUniformMatrix4fv(m_projLoc, 1, GL_FALSE, (const float *)projection.Data());
	glUniform1f(m_intensityLoc, m_intensity);

	glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
	// Orphan the previous frame's storage so the upload never waits on the GPU.
	glBufferData(GL_ARRAY_BUFFER, kMaxStrokes * 4 * 4 * sizeof(float), nullptr, GL_STREAM_DRAW);
	glBufferSubData(GL_ARRAY_BUFFER, 0, m_vertices.size() * sizeof(float), m_vertices.data());
	glBindBuffer(GL_ARRAY_BUFFER, 0);

	glEnable(GL_BLEND);
	glBlendFunc(GL_ONE, GL_ONE);
	glDepthMask(GL_FALSE);
	glDisable(GL_CULL_FACE);

	glBindVertexArray(m_vao);
	glDrawElements(GL_TRIANGLES, (GLsizei)(m_strokes.size() * 6), GL_UNSIGNED_INT, nullptr);
	glBindVertexArray(0);

	glDepthMask(GL_TRUE);
	glDisable(GL_BLEND);
	// Blend mexido direto no GL: invalida o cache de GPU_set_material_alpha_blend(),
	// senão o próximo material com o mesmo modo pula a chamada e sai sem blend.
	GPU_set_material_alpha_blend(-1);
	glUseProgram(0);
}
