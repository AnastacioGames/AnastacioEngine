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

/** \file gameengine/Ketsji/KX_WeakGpu.cpp
 *  \ingroup ketsji
 */

#include "KX_WeakGpu.h"

#include "RAS_Rasterizer.h"

#include "GPU_glew.h"
#include "GPU_shader.h"

#include "CM_Message.h"

#include <algorithm>
#include <cstdlib>

namespace {

const char *vertexCode =
	"#if __VERSION__ >= 130\n"
	"layout(location = 0) in vec3 pos;\n"
	"void main() { gl_Position = vec4(pos, 1.0); }\n"
	"#else\n"
	"void main() { gl_Position = gl_Vertex; }\n"
	"#endif\n";

/* Fixed cost per pixel and iteration. The result goes out through a blend that keeps the
 * destination, so nothing changes on screen but the compiler cannot drop the loop. */
const char *fragmentCode =
	"uniform int iterations;\n"
	"void main()\n"
	"{\n"
	"	float a = fract(gl_FragCoord.x * 0.0137 + gl_FragCoord.y * 0.0071);\n"
	"	for (int i = 0; i < iterations; i++) {\n"
	"		a = fract(sin(a * 12.9898 + float(i) * 0.731) * 43758.5453);\n"
	"	}\n"
	"	gl_FragColor = vec4(a);\n"
	"}\n";

/* One draw stays short (a long one can trip the driver watchdog); several passes reach the target. */
const int maxIterationsPerPass = 512;
const int maxPasses = 32;

}  // namespace

float KX_WeakGpu::EnvFactor()
{
#ifdef __EMSCRIPTEN__
	return 0.0f;
#else
	const char *env = getenv("RANGE_WEAK_GPU");
	if (!env || !env[0]) {
		return 0.0f;
	}
	const float factor = (float)atof(env);
	return (factor >= 1.01f) ? std::min(factor, 50.0f) : 0.0f;
#endif
}

KX_WeakGpu::KX_WeakGpu(float factor)
	:m_factor(factor),
	m_init(false),
	m_supported(false),
	m_shader(nullptr),
	m_iterationsLoc(-1),
	m_queries(),
	m_pending(),
	m_current(0),
	m_started(false),
	m_iterations(64.0f)
{
}

KX_WeakGpu::~KX_WeakGpu()
{
#ifndef __EMSCRIPTEN__
	if (m_supported) {
		glDeleteQueries(frames * 3, &m_queries[0][0]);
	}
	if (m_shader) {
		GPU_shader_free(m_shader);
	}
#endif
}

void KX_WeakGpu::Init()
{
	m_init = true;
#ifndef __EMSCRIPTEN__
	if (!GLEW_ARB_timer_query) {
		CM_Warning("weak GPU simulator: no GPU timer here, RANGE_WEAK_GPU ignored");
		return;
	}
	m_shader = GPU_shader_create(vertexCode, fragmentCode, nullptr, nullptr, nullptr, 0, 0, 0);
	if (!m_shader) {
		CM_Warning("weak GPU simulator: shader failed, RANGE_WEAK_GPU ignored");
		return;
	}
	m_iterationsLoc = GPU_shader_get_uniform(m_shader, "iterations");
	glGenQueries(frames * 3, &m_queries[0][0]);
	m_supported = true;
	CM_Message("weak GPU simulator: GPU about " << m_factor << "x slower (RANGE_WEAK_GPU)");
#endif
}

void KX_WeakGpu::FrameStart()
{
#ifndef __EMSCRIPTEN__
	if (!m_init) {
		Init();
	}
	if (!m_supported) {
		return;
	}
	m_current = (m_current + 1) % frames;
	unsigned int *q = m_queries[m_current];
	// Oldest frame in the ring, normally finished by now; if not, skip it instead of stalling.
	if (m_pending[m_current]) {
		m_pending[m_current] = false;
		GLint available = 0;
		glGetQueryObjectiv(q[2], GL_QUERY_RESULT_AVAILABLE, &available);
		if (available) {
			GLuint64 t0 = 0, t1 = 0, t2 = 0;
			glGetQueryObjectui64v(q[0], GL_QUERY_RESULT, &t0);
			glGetQueryObjectui64v(q[1], GL_QUERY_RESULT, &t1);
			glGetQueryObjectui64v(q[2], GL_QUERY_RESULT, &t2);
			const double frameMs = (double)(t1 - t0) * 1e-6;
			const double burnMs = (double)(t2 - t1) * 1e-6;
			const double targetMs = frameMs * (m_factor - 1.0);
			if (burnMs > 0.02 && m_iterations >= 1.0f) {
				// Cost of one iteration over the screen, then smooth toward the needed count.
				const double wanted = targetMs / (burnMs / m_iterations);
				m_iterations = (float)(m_iterations * 0.8 + wanted * 0.2);
			}
			else {
				m_iterations *= 2.0f;
			}
			m_iterations = std::max(1.0f, std::min(m_iterations, (float)(maxIterationsPerPass * maxPasses)));
		}
	}
	glQueryCounter(q[0], GL_TIMESTAMP);
	m_started = true;
#endif
}

void KX_WeakGpu::Burn(RAS_Rasterizer *rasterizer)
{
#ifndef __EMSCRIPTEN__
	if (!m_supported || !m_started) {
		return;
	}
	m_started = false;
	unsigned int *q = m_queries[m_current];
	glQueryCounter(q[1], GL_TIMESTAMP);

	const GLboolean blend = glIsEnabled(GL_BLEND);
	const GLboolean depthTest = glIsEnabled(GL_DEPTH_TEST);
	const GLboolean scissor = glIsEnabled(GL_SCISSOR_TEST);
	GLboolean depthMask = GL_TRUE;
	glGetBooleanv(GL_DEPTH_WRITEMASK, &depthMask);
	GLint src = GL_ONE, dst = GL_ZERO, srcA = GL_ONE, dstA = GL_ZERO;
	glGetIntegerv(GL_BLEND_SRC_RGB, &src);
	glGetIntegerv(GL_BLEND_DST_RGB, &dst);
	glGetIntegerv(GL_BLEND_SRC_ALPHA, &srcA);
	glGetIntegerv(GL_BLEND_DST_ALPHA, &dstA);

	glEnable(GL_BLEND);
	glBlendFunc(GL_ZERO, GL_ONE);
	glDisable(GL_DEPTH_TEST);
	glDisable(GL_SCISSOR_TEST);
	glDepthMask(GL_FALSE);

	GPU_shader_bind(m_shader);
	int left = (int)m_iterations;
	for (int pass = 0; pass < maxPasses && left > 0; ++pass) {
		const int n = std::min(left, maxIterationsPerPass);
		GPU_shader_uniform_int(m_shader, m_iterationsLoc, n);
		rasterizer->DrawOverlayPlane();
		left -= n;
	}
	GPU_shader_unbind();

	glBlendFuncSeparate(src, dst, srcA, dstA);
	if (!blend) glDisable(GL_BLEND);
	if (depthTest) glEnable(GL_DEPTH_TEST);
	if (scissor) glEnable(GL_SCISSOR_TEST);
	glDepthMask(depthMask);

	glQueryCounter(q[2], GL_TIMESTAMP);
	m_pending[m_current] = true;
#endif
}
