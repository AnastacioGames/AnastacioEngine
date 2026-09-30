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
#include "CM_Message.h"

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
	"void main() {\n"
	"	float r = length(v_uv);\n"
	"	float c = r * u_glowRatio;\n"
	"	float core = exp(-c * c * 2.0);\n"
	"	float glow = exp(-r * r * 6.0) * (1.0 - smoothstep(0.8, 1.0, r));\n"
	"	vec3 col = vec3(1.0) * core + vec3(0.65, 0.72, 1.0) * glow * 0.35;\n"
	"	fragColor = vec4(col * v_bright * u_bright, 1.0);\n"
	"}\n";

static const int kFloatsPerVertex = 6;

KX_RainLightning::KX_RainLightning()
	:m_hasBolt(false),
	m_start(-1.0),
	m_seed(0),
	m_big(false),
	m_pending(false),
	m_pendingBig(true),
	m_hasManual(false),
	m_manualStart(0.0),
	m_manualSeed(0),
	m_manualBig(false),
	m_manualCount(0),
	m_flash(0.0f),
	m_boltBright(0.0f),
	m_camPos(mt::zero3),
	m_program(0),
	m_vao(0),
	m_vbo(0),
	m_ibo(0),
	m_viewLoc(-1),
	m_projLoc(-1),
	m_brightLoc(-1),
	m_glFailed(false)
{
	m_bolt.num_strips = 0;
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

void KX_RainLightning::Strike(bool bolt)
{
	m_pending = true;
	m_pendingBig = bolt;
}

void KX_RainLightning::Update(KX_Camera *camera, const World *world, double time)
{
	m_flash = 0.0f;
	m_boltBright = 0.0f;
	if (!camera || !world || !(world->weather_flag & WO_WEATHER_RAIN)) {
		m_pending = false;
		return;
	}

	if (m_pending) {
		m_pending = false;
		m_hasManual = true;
		m_manualStart = time;
		m_manualSeed = 0x2545f491u * ++m_manualCount + (unsigned int)(time * 1000.0);
		m_manualBig = m_pendingBig;
	}

	// The latest strike wins: automatic (World rate) or requested from Python.
	double start = -1.0;
	unsigned int seed = 0;
	bool big = false;
	if (world->weather_flag & WO_WEATHER_RAIN_LIGHTNING) {
		if (!BKE_rain_lightning_schedule(world->rain_lightning_rate, time, &start, &seed, &big)) {
			start = -1.0;
		}
	}
	if (m_hasManual && m_manualStart >= start) {
		start = m_manualStart;
		seed = m_manualSeed;
		big = m_manualBig;
	}
	if (start < 0.0) {
		return;
	}

	m_camPos = camera->NodeGetWorldPosition();
	if (start != m_start || seed != m_seed) {
		m_start = start;
		m_seed = seed;
		m_big = big;
		m_hasBolt = false;
		if (big) {
			// Keep the whole bolt inside the camera range: a closer bolt is also smaller,
			// so it looks the same.
			const float distance = std::min(world->rain_lightning_distance, camera->GetCameraFar() * 0.6f);
			const mt::vec3 fwd = camera->NodeGetWorldOrientation() * mt::vec3(0.0f, 0.0f, -1.0f);
			const float camPos[3] = {m_camPos.x, m_camPos.y, m_camPos.z};
			const float camFwd[3] = {fwd.x, fwd.y, fwd.z};
			BKE_rain_lightning_bolt(seed, camPos, camFwd, distance, world->rain_lightning_width, &m_bolt);
			m_hasBolt = true;
		}
	}

	bool over;
	const float flash = BKE_rain_lightning_flash(m_seed, m_big, (float)(time - m_start), &over);
	m_flash = flash * world->rain_lightning_intensity;
	m_boltBright = m_hasBolt ? std::min(flash * 1.6f, 1.0f) * world->rain_lightning_intensity : 0.0f;
}

mt::vec4 KX_RainLightning::GetFilterParams(const mt::mat4& view, const mt::mat4& projection) const
{
	if (m_flash <= 0.0f) {
		return mt::zero4;
	}
	float bolt = 0.0f;
	float sx = 0.5f;
	float sy = 0.5f;
	if (m_boltBright > 0.0f) {
		const mt::vec4 clip = projection * (view * mt::vec4(m_bolt.center[0], m_bolt.center[1], m_bolt.center[2], 1.0f));
		// Behind the camera: no halo in the sky, the flash alone.
		if (clip.w > 0.0f) {
			sx = clip.x / clip.w * 0.5f + 0.5f;
			sy = clip.y / clip.w * 0.5f + 0.5f;
			bolt = m_boltBright;
		}
	}
	return mt::vec4(m_flash, bolt, sx, sy);
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

void KX_RainLightning::Draw(const mt::mat4& view, const mt::mat4& projection)
{
	if (!m_hasBolt || m_boltBright <= 0.001f || !EnsureGL()) {
		return;
	}

	// Rebuilt every frame: the ribbon faces the camera, which moves (~300 vertices).
	m_vertices.clear();
	m_indices.clear();
	const float camPos[3] = {m_camPos.x, m_camPos.y, m_camPos.z};
	for (int s = 0; s < m_bolt.num_strips; ++s) {
		const int start = m_bolt.strip_start[s];
		const int n = m_bolt.strip_len[s];
		if (n < 2) {
			continue;
		}
		const unsigned int first = (unsigned int)(m_vertices.size() / kFloatsPerVertex);
		// One extra row past each end: the round caps.
		for (int row = -1; row <= n; ++row) {
			const int i = std::max(0, std::min(row, n - 1));
			const float *p = m_bolt.co[start + i];
			float side[3];
			BKE_rain_lightning_side(&m_bolt, s, i, camPos, side);
			mt::vec3 pos(p[0], p[1], p[2]);
			float v = 0.0f;
			if (row != i) {
				const float *q = m_bolt.co[start + ((row < 0) ? 1 : n - 2)];
				const mt::vec3 out = (pos - mt::vec3(q[0], q[1], q[2])).SafeNormalized(mt::axisZ3);
				pos += out * m_bolt.half_width[start + i];
				v = 1.0f;
			}
			for (int k = -1; k <= 1; k += 2) {
				m_vertices.push_back(pos.x + side[0] * k);
				m_vertices.push_back(pos.y + side[1] * k);
				m_vertices.push_back(pos.z + side[2] * k);
				m_vertices.push_back((float)k);
				m_vertices.push_back(v);
				m_vertices.push_back(m_bolt.bright[start + i]);
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

	glUseProgram(m_program);
	glUniformMatrix4fv(m_viewLoc, 1, GL_FALSE, (const float *)view.Data());
	glUniformMatrix4fv(m_projLoc, 1, GL_FALSE, (const float *)projection.Data());
	glUniform1f(m_brightLoc, m_boltBright);

	glBindVertexArray(m_vao);
	glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
	glBufferData(GL_ARRAY_BUFFER, m_vertices.size() * sizeof(float), m_vertices.data(), GL_STREAM_DRAW);
	glBufferData(GL_ELEMENT_ARRAY_BUFFER, m_indices.size() * sizeof(unsigned int), m_indices.data(), GL_STREAM_DRAW);

	glEnable(GL_BLEND);
	glBlendFunc(GL_ONE, GL_ONE);
	glDepthMask(GL_FALSE);
	glDisable(GL_CULL_FACE);

	glDrawElements(GL_TRIANGLES, (GLsizei)m_indices.size(), GL_UNSIGNED_INT, nullptr);

	glBindVertexArray(0);
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	glDepthMask(GL_TRUE);
	glDisable(GL_BLEND);
	glUseProgram(0);
}
