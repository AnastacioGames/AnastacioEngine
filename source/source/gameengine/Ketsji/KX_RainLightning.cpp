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

/** \file gameengine/Ketsji/KX_RainLightning.cpp
 *  \ingroup ketsji
 */

#include "KX_RainLightning.h"
#include "KX_Camera.h"
#include "KX_ClientObjectInfo.h"
#include "KX_GameObject.h"
#include "KX_RayCast.h"
#include "KX_Scene.h"
#include "CM_Message.h"

#include "DNA_object_types.h"
#include "DNA_world_types.h"

#include "GPU_glew.h"

#include <algorithm>
#include <cmath>

static const char *kVertexSource =
	"#version 130\n"
	"in vec3 in_pos;\n"
	"in vec2 in_uv;\n"
	"in float in_bright;\n"
	"out vec2 v_uv;\n"
	"out float v_bright;\n"
	"uniform mat4 u_view;\n"
	"uniform mat4 u_projection;\n"
	"void main() {\n"
	"	v_uv = in_uv;\n"
	"	v_bright = in_bright;\n"
	"	gl_Position = u_projection * (u_view * vec4(in_pos, 1.0));\n"
	"}\n";

// u across the ribbon (-1..1), v past the ends (0..1): the distance to the axis gives a
// gaussian profile with round ends, so the ribbon never shows a hard border.
static const char *kFragmentSource =
	"#version 130\n"
	"in vec2 v_uv;\n"
	"in float v_bright;\n"
	"out vec4 fragColor;\n"
	"uniform float u_bright;\n"
	"uniform float u_glowRatio;\n"
	"uniform vec3 u_color;\n"
	"void main() {\n"
	"	float r = length(v_uv);\n"
	"	float c = r * u_glowRatio;\n"
	"	float core = exp(-c * c * 2.0);\n"
	"	float glow = exp(-r * r * 6.0) * (1.0 - smoothstep(0.8, 1.0, r));\n"
	"	vec3 col = vec3(1.0) * core + u_color * glow * 0.35;\n"
	"	fragColor = vec4(col * v_bright * u_bright, 1.0);\n"
	"}\n";

static const int kFloatsPerVertex = 6;

namespace {

// Hit Ground: the first surface below the cloud, sensors ignored.
struct GroundFilter {
	bool NeedRayCast(KX_ClientObjectInfo *client, void *)
	{
		return client->m_gameobject && !client->isSensor();
	}
	bool RayHit(KX_ClientObjectInfo *, KX_RayCast *, void *)
	{
		return true;
	}
};

} // namespace

KX_RainLightning::KX_RainLightning()
	:m_camPos(mt::zero3),
	m_program(0),
	m_vao(0),
	m_vbo(0),
	m_ibo(0),
	m_viewLoc(-1),
	m_projLoc(-1),
	m_brightLoc(-1),
	m_colorLoc(-1),
	m_glFailed(false)
{
	m_world.bolt.num_strips = 0;
}

KX_RainLightning::~KX_RainLightning()
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

void KX_RainLightning::Manual::Take(double time, unsigned int salt)
{
	if (!pending) {
		return;
	}
	pending = false;
	has = true;
	start = time;
	seed = 0x2545f491u * ++count + (unsigned int)(time * 1000.0) + salt;
	big = pendingBig;
}

void KX_RainLightning::Strike(bool bolt)
{
	m_worldManual.pending = true;
	m_worldManual.pendingBig = bolt;
}

KX_RainLightning::Emitter *KX_RainLightning::FindEmitter(KX_GameObject *gameobj)
{
	for (Emitter& emitter : m_emitters) {
		if (emitter.gameobj == gameobj) {
			return &emitter;
		}
	}
	return nullptr;
}

void KX_RainLightning::AddEmitter(KX_GameObject *gameobj)
{
	if (!FindEmitter(gameobj)) {
		Emitter emitter;
		emitter.gameobj = gameobj;
		emitter.strike.bolt.num_strips = 0;
		m_emitters.push_back(emitter);
	}
}

void KX_RainLightning::RemoveObject(KX_GameObject *gameobj)
{
	m_emitters.erase(std::remove_if(m_emitters.begin(), m_emitters.end(),
	                                [gameobj](const Emitter& emitter) { return emitter.gameobj == gameobj; }),
	                 m_emitters.end());
}

bool KX_RainLightning::HasEmitter(KX_GameObject *gameobj) const
{
	return const_cast<KX_RainLightning *>(this)->FindEmitter(gameobj) != nullptr;
}

void KX_RainLightning::StrikeAt(KX_GameObject *gameobj, bool bolt)
{
	if (Emitter *emitter = FindEmitter(gameobj)) {
		emitter->manual.pending = true;
		emitter->manual.pendingBig = bolt;
	}
}

void KX_RainLightning::TakeEmitters(KX_RainLightning& other)
{
	for (const Emitter& emitter : other.m_emitters) {
		if (!FindEmitter(emitter.gameobj)) {
			m_emitters.push_back(emitter);
		}
	}
	other.m_emitters.clear();
}

void KX_RainLightning::Update(KX_Scene *scene, KX_Camera *camera, const World *world, double time)
{
	m_world.flash = 0.0f;
	m_world.boltBright = 0.0f;
	for (Emitter& emitter : m_emitters) {
		emitter.strike.flash = 0.0f;
		emitter.strike.boltBright = 0.0f;
	}
	if (!camera) {
		m_worldManual.pending = false;
		return;
	}
	m_camPos = camera->NodeGetWorldPosition();

	for (Emitter& emitter : m_emitters) {
		UpdateEmitter(scene, emitter, time);
	}

	// World > Rain > Lightning, in front of the camera.
	if (!world || !(world->weather_flag & WO_WEATHER_RAIN)) {
		m_worldManual.pending = false;
		return;
	}
	m_worldManual.Take(time, 0u);

	// The latest strike wins: automatic (World rate) or requested from Python.
	double start = -1.0;
	unsigned int seed = 0;
	bool big = false;
	if (world->weather_flag & WO_WEATHER_RAIN_LIGHTNING) {
		if (!BKE_rain_lightning_schedule(world->rain_lightning_rate, time, &start, &seed, &big)) {
			start = -1.0;
		}
	}
	if (m_worldManual.has && m_worldManual.start >= start) {
		start = m_worldManual.start;
		seed = m_worldManual.seed;
		big = m_worldManual.big;
	}
	if (start < 0.0) {
		return;
	}

	StrikeState& strike = m_world;
	if (start != strike.start || seed != strike.seed) {
		strike.start = start;
		strike.seed = seed;
		strike.big = big;
		strike.hasBolt = false;
		if (big) {
			// Keep the whole bolt inside the camera range: a closer bolt is also smaller,
			// so it looks the same.
			const float distance = std::min(world->rain_lightning_distance, camera->GetCameraFar() * 0.6f);
			const mt::vec3 fwd = camera->NodeGetWorldOrientation() * mt::vec3(0.0f, 0.0f, -1.0f);
			const float camPos[3] = {m_camPos.x, m_camPos.y, m_camPos.z};
			const float camFwd[3] = {fwd.x, fwd.y, fwd.z};
			BKE_rain_lightning_bolt(seed, camPos, camFwd, distance, world->rain_lightning_width, &strike.bolt);
			strike.center = mt::vec3(strike.bolt.center);
			strike.hasBolt = true;
		}
	}

	bool over;
	const float flash = BKE_rain_lightning_flash(strike.seed, strike.big, (float)(time - strike.start), &over);
	strike.flash = flash * world->rain_lightning_intensity;
	strike.boltBright = strike.hasBolt ? std::min(flash * 1.6f, 1.0f) * world->rain_lightning_intensity : 0.0f;
}

void KX_RainLightning::UpdateEmitter(KX_Scene *scene, Emitter& emitter, double time)
{
	KX_GameObject *gameobj = emitter.gameobj;
	const Object *blenderobj = gameobj->GetBlenderObject();
	if (!blenderobj) {
		return;
	}
	const RangeLightningSettings& settings = blenderobj->lightning;
	const unsigned int salt = BKE_rain_lightning_salt(blenderobj->id.name + 2);
	emitter.manual.Take(time, salt);

	double start = -1.0;
	unsigned int seed = 0;
	bool big = false;
	if (settings.mode == LIGHTNING_MODE_AUTOMATIC && time >= settings.start_time &&
	    (settings.end_time <= 0.0f || time <= settings.end_time))
	{
		if (!BKE_rain_lightning_schedule_ex(settings.rate, salt, settings.big_chance, time, &start, &seed, &big) ||
		    start < settings.start_time)
		{
			start = -1.0;
		}
	}
	if (emitter.manual.has && emitter.manual.start >= start) {
		start = emitter.manual.start;
		seed = emitter.manual.seed;
		big = emitter.manual.big;
	}
	if (start < 0.0) {
		return;
	}

	StrikeState& strike = emitter.strike;
	strike.color = mt::vec3(settings.color);
	if (start != strike.start || seed != strike.seed) {
		strike.start = start;
		strike.seed = seed;
		strike.big = big;

		// The Empty's world matrix: the area follows its position, rotation and scale (and a parent).
		const mt::vec3& pos = gameobj->NodeGetWorldPosition();
		const mt::mat3& rot = gameobj->NodeGetWorldOrientation();
		const mt::vec3& scale = gameobj->NodeGetWorldScaling();
		float obmat[4][4];
		for (int col = 0; col < 3; ++col) {
			for (int row = 0; row < 3; ++row) {
				obmat[col][row] = rot(row, col) * scale[col];
			}
			obmat[col][3] = 0.0f;
		}
		obmat[3][0] = pos.x;
		obmat[3][1] = pos.y;
		obmat[3][2] = pos.z;
		obmat[3][3] = 1.0f;

		float ground[3];
		BKE_rain_lightning_strike_point(seed, obmat, blenderobj->empty_drawsize,
		                                settings.shape == LIGHTNING_SHAPE_BOX, ground);

		// Target: from the area to the object, whatever the direction.
		KX_GameObject *target = settings.target ? scene->GetObjectList()->FindValue(settings.target->id.name + 2) : nullptr;
		if (target) {
			const mt::vec3& to = target->NodeGetWorldPosition();
			const float toCo[3] = {to.x, to.y, to.z};
			strike.hasBolt = big;
			if (big) {
				BKE_rain_lightning_bolt_between(seed, ground, toCo, settings.width, &strike.bolt);
			}
			strike.center = (mt::vec3(ground) + to) * 0.5f;
		}
		else {
			const float cloudZ = ground[2] + settings.height;
			if (settings.flags & LIGHTNING_HIT_GROUND) {
				// From the cloud down, as deep below the Empty as the cloud is above it.
				GroundFilter filter;
				KX_RayCast::Callback<GroundFilter, void> callback(&filter);
				const mt::vec3 from(ground[0], ground[1], cloudZ);
				const mt::vec3 to(ground[0], ground[1], ground[2] - settings.height);
				if (KX_RayCast::RayTest(scene->GetPhysicsEnvironment(), from, to, callback)) {
					ground[2] = callback.m_hitPoint.z;
				}
			}
	
			strike.hasBolt = big;
			if (big) {
				BKE_rain_lightning_bolt_at(seed, ground, cloudZ, settings.width, &strike.bolt);
				strike.center = mt::vec3(strike.bolt.center);
			}
			else {
				// A flash in the cloud.
				strike.center = mt::vec3(ground[0], ground[1], cloudZ);
			}
		}
	}

	bool over;
	const float flash = BKE_rain_lightning_flash(strike.seed, strike.big, (float)(time - strike.start), &over);
	const float fade = BKE_rain_lightning_distance_fade((strike.center - m_camPos).Length(), settings.flash_distance);
	strike.flash = flash * settings.intensity * fade;
	strike.boltBright = strike.hasBolt ? std::min(flash * 1.6f, 1.0f) * settings.intensity : 0.0f;
}

mt::vec4 KX_RainLightning::GetFilterParams(const mt::mat4& view, const mt::mat4& projection) const
{
	// The flashes add up; the halo goes around the brightest bolt on screen.
	float flash = m_world.flash;
	const StrikeState *halo = (m_world.boltBright > 0.0f) ? &m_world : nullptr;
	for (const Emitter& emitter : m_emitters) {
		const StrikeState& strike = emitter.strike;
		flash += strike.flash;
		if (strike.boltBright > 0.0f && strike.flash > 0.0f &&
		    (!halo || strike.boltBright * strike.flash > halo->boltBright * halo->flash))
		{
			halo = &strike;
		}
	}
	if (flash <= 0.0f) {
		return mt::zero4;
	}
	flash = std::min(flash, 2.0f);

	float bolt = 0.0f;
	float sx = 0.5f;
	float sy = 0.5f;
	if (halo) {
		const mt::vec4 clip = projection * (view * mt::vec4(halo->center.x, halo->center.y, halo->center.z, 1.0f));
		// Behind the camera: no halo in the sky, the flash alone.
		if (clip.w > 0.0f) {
			sx = clip.x / clip.w * 0.5f + 0.5f;
			sy = clip.y / clip.w * 0.5f + 0.5f;
			bolt = halo->boltBright;
		}
	}
	return mt::vec4(flash, bolt, sx, sy);
}

bool KX_RainLightning::EnsureGL()
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
		CM_Error("rain lightning shader compile failed:\n" << log);
		glDeleteShader(vert);
		glDeleteShader(frag);
		m_glFailed = true;
		return false;
	}

	m_program = glCreateProgram();
	glAttachShader(m_program, vert);
	glAttachShader(m_program, frag);
	glBindAttribLocation(m_program, 0, "in_pos");
	glBindAttribLocation(m_program, 1, "in_uv");
	glBindAttribLocation(m_program, 2, "in_bright");
	glBindFragDataLocation(m_program, 0, "fragColor");
	glLinkProgram(m_program);
	glDeleteShader(vert);
	glDeleteShader(frag);
	glGetProgramiv(m_program, GL_LINK_STATUS, &status);
	if (!status) {
		glGetProgramInfoLog(m_program, sizeof(log), &length, log);
		CM_Error("rain lightning shader link failed:\n" << log);
		glDeleteProgram(m_program);
		m_program = 0;
		m_glFailed = true;
		return false;
	}
	m_viewLoc = glGetUniformLocation(m_program, "u_view");
	m_projLoc = glGetUniformLocation(m_program, "u_projection");
	m_brightLoc = glGetUniformLocation(m_program, "u_bright");
	m_colorLoc = glGetUniformLocation(m_program, "u_color");
	glUseProgram(m_program);
	glUniform1f(glGetUniformLocation(m_program, "u_glowRatio"), RAIN_LIGHTNING_GLOW_RATIO);
	glUseProgram(0);

	glGenVertexArrays(1, &m_vao);
	glGenBuffers(1, &m_vbo);
	glGenBuffers(1, &m_ibo);
	glBindVertexArray(m_vao);
	glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
	const GLsizei stride = kFloatsPerVertex * sizeof(float);
	glEnableVertexAttribArray(0);
	glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, (void *)0);
	glEnableVertexAttribArray(1);
	glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, (void *)(3 * sizeof(float)));
	glEnableVertexAttribArray(2);
	glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, stride, (void *)(5 * sizeof(float)));
	glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, m_ibo);
	glBindVertexArray(0);
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	return true;
}

void KX_RainLightning::DrawStrike(const StrikeState& strike)
{
	if (!strike.hasBolt || strike.boltBright <= 0.001f) {
		return;
	}

	// Rebuilt every frame: the ribbon faces the camera, which moves (~300 vertices).
	const RainLightningBolt& bolt = strike.bolt;
	m_vertices.clear();
	m_indices.clear();
	const float camPos[3] = {m_camPos.x, m_camPos.y, m_camPos.z};
	for (int s = 0; s < bolt.num_strips; ++s) {
		const int start = bolt.strip_start[s];
		const int n = bolt.strip_len[s];
		if (n < 2) {
			continue;
		}
		const unsigned int first = (unsigned int)(m_vertices.size() / kFloatsPerVertex);
		// One extra row past each end: the round caps.
		for (int row = -1; row <= n; ++row) {
			const int i = std::max(0, std::min(row, n - 1));
			const float *p = bolt.co[start + i];
			float side[3];
			BKE_rain_lightning_side(&bolt, s, i, camPos, side);
			mt::vec3 pos(p[0], p[1], p[2]);
			float v = 0.0f;
			if (row != i) {
				const float *q = bolt.co[start + ((row < 0) ? 1 : n - 2)];
				const mt::vec3 out = (pos - mt::vec3(q[0], q[1], q[2])).SafeNormalized(mt::axisZ3);
				pos += out * bolt.half_width[start + i];
				v = 1.0f;
			}
			for (int k = -1; k <= 1; k += 2) {
				m_vertices.push_back(pos.x + side[0] * k);
				m_vertices.push_back(pos.y + side[1] * k);
				m_vertices.push_back(pos.z + side[2] * k);
				m_vertices.push_back((float)k);
				m_vertices.push_back(v);
				m_vertices.push_back(bolt.bright[start + i]);
			}
		}
		for (int row = 0; row < n + 1; ++row) {
			const unsigned int a = first + row * 2;
			const unsigned int quad[6] = {a, a + 1, a + 3, a, a + 3, a + 2};
			m_indices.insert(m_indices.end(), quad, quad + 6);
		}
	}
	if (m_indices.empty()) {
		return;
	}

	glUniform1f(m_brightLoc, strike.boltBright);
	glUniform3f(m_colorLoc, strike.color.x, strike.color.y, strike.color.z);
	glBufferData(GL_ARRAY_BUFFER, m_vertices.size() * sizeof(float), m_vertices.data(), GL_STREAM_DRAW);
	glBufferData(GL_ELEMENT_ARRAY_BUFFER, m_indices.size() * sizeof(unsigned int), m_indices.data(), GL_STREAM_DRAW);
	glDrawElements(GL_TRIANGLES, (GLsizei)m_indices.size(), GL_UNSIGNED_INT, nullptr);
}

void KX_RainLightning::Draw(const mt::mat4& view, const mt::mat4& projection)
{
	bool any = m_world.hasBolt && m_world.boltBright > 0.001f;
	for (const Emitter& emitter : m_emitters) {
		any = any || (emitter.strike.hasBolt && emitter.strike.boltBright > 0.001f);
	}
	if (!any || !EnsureGL()) {
		return;
	}

	glUseProgram(m_program);
	glUniformMatrix4fv(m_viewLoc, 1, GL_FALSE, (const float *)view.Data());
	glUniformMatrix4fv(m_projLoc, 1, GL_FALSE, (const float *)projection.Data());

	glBindVertexArray(m_vao);
	glBindBuffer(GL_ARRAY_BUFFER, m_vbo);

	glEnable(GL_BLEND);
	glBlendFunc(GL_ONE, GL_ONE);
	glDepthMask(GL_FALSE);
	glDisable(GL_CULL_FACE);

	DrawStrike(m_world);
	for (const Emitter& emitter : m_emitters) {
		DrawStrike(emitter.strike);
	}

	glBindVertexArray(0);
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	glDepthMask(GL_TRUE);
	glDisable(GL_BLEND);
	glUseProgram(0);
}
