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

/** \file gameengine/Ketsji/KX_RainSurfaceMask.cpp
 *  \ingroup ketsji
 */

#include "KX_RainSurfaceMask.h"
#include "KX_Scene.h"
#include "KX_GameObject.h"
#include "KX_Mesh.h"
#include "RAS_DisplayArray.h"
#include "SG_CullingNode.h"
#include "EXP_ListValue.h"
#include "CM_Message.h"

#include "DNA_world_types.h"

#include "GPU_glew.h"

#include <algorithm>
#include <cmath>

const char *const KX_RainSurfaceMask::RippleProperty = "ripples_effect";
const char *const KX_RainSurfaceMask::SplashProperty = "splash_effect";
const char *const KX_RainSurfaceMask::PuddleProperty = "puddles_effect";

/// How often the lists of marked objects are rebuilt (added objects, changed properties).
static const double kScanInterval = 0.5;

static const char *kVertexSource =
	"#version 130\n"
	"in vec3 in_pos;\n"
	"out float v_depth;\n"
	"uniform mat4 u_model;\n"
	"uniform mat4 u_view;\n"
	"uniform mat4 u_projection;\n"
	"void main() {\n"
	"	vec4 viewPos = u_view * (u_model * vec4(in_pos, 1.0));\n"
	"	v_depth = -viewPos.z;\n"
	"	gl_Position = u_projection * viewPos;\n"
	"}\n";

static const char *kFragmentSource =
	"#version 130\n"
	"in float v_depth;\n"
	"out vec4 fragColor;\n"
	"uniform float u_flags;\n"
	"void main() {\n"
	"	fragColor = vec4(u_flags, v_depth, 0.0, 0.0);\n"
	"}\n";

KX_RainSurfaceMask::KX_RainSurfaceMask()
	:m_flags(0),
	m_nextScan(0.0),
	m_program(0),
	m_vao(0),
	m_fbo(0),
	m_texture(0),
	m_depth(0),
	m_width(0),
	m_height(0),
	m_viewLoc(-1),
	m_projLoc(-1),
	m_modelLoc(-1),
	m_flagsLoc(-1),
	m_glFailed(false)
{
}

KX_RainSurfaceMask::~KX_RainSurfaceMask()
{
	ClearMeshBuffers();
	if (m_fbo) {
		glDeleteFramebuffers(1, &m_fbo);
	}
	if (m_texture) {
		glDeleteTextures(1, &m_texture);
	}
	if (m_depth) {
		glDeleteRenderbuffers(1, &m_depth);
	}
	if (m_vao) {
		glDeleteVertexArrays(1, &m_vao);
	}
	if (m_program) {
		glDeleteProgram(m_program);
	}
}

unsigned int KX_RainSurfaceMask::GetTexture() const
{
	return m_texture;
}

void KX_RainSurfaceMask::RemoveObject(KX_GameObject *gameobj)
{
	m_valid = false;
	m_drawnItems.clear();
	m_targets.erase(std::remove_if(m_targets.begin(), m_targets.end(),
	                               [gameobj](const Target& target) { return target.gameobj == gameobj; }),
	                m_targets.end());
}

void KX_RainSurfaceMask::ClearMeshBuffers()
{
	m_valid = false;
	for (const auto& item : m_meshBuffers) {
		glDeleteBuffers(1, &item.second.vbo);
	}
	m_meshBuffers.clear();
}

void KX_RainSurfaceMask::RefreshTargets(KX_Scene *scene)
{
	std::vector<Target> targets;
	int flags = 0;
	for (KX_GameObject *gameobj : *scene->GetObjectList()) {
		if (gameobj->GetMeshList().empty()) {
			continue;
		}
		int objFlags = 0;
		EXP_Value *ripple = gameobj->GetProperty(RippleProperty);
		if (ripple && ripple->GetNumber() != 0.0) {
			objFlags |= MASK_RIPPLE;
		}
		EXP_Value *splash = gameobj->GetProperty(SplashProperty);
		if (splash && splash->GetNumber() != 0.0) {
			objFlags |= MASK_SPLASH;
		}
		EXP_Value *puddle = gameobj->GetProperty(PuddleProperty);
		if (puddle && puddle->GetNumber() != 0.0) {
			objFlags |= MASK_PUDDLE;
		}
		if (objFlags) {
			targets.push_back({gameobj, objFlags});
			flags |= objFlags;
		}
	}
	m_flags = flags;
	if (targets != m_targets) {
		CM_Message("rain mask: " << targets.size() << " object(s) with \"" << RippleProperty << "\"/\"" << SplashProperty << "\"/\"" << PuddleProperty << "\"");
		m_targets.swap(targets);
		// Meshes of removed objects may have been freed: never keep a stale pointer as key.
		ClearMeshBuffers();
	}
}

const KX_RainSurfaceMask::MeshBuffer& KX_RainSurfaceMask::GetMeshBuffer(RAS_Mesh *mesh)
{
	auto it = m_meshBuffers.find(mesh);
	if (it != m_meshBuffers.end()) {
		return it->second;
	}

	// Local positions of every triangle, drawn with the object matrix.
	std::vector<float> positions;
	const unsigned int numPolygons = mesh->GetNumPolygons();
	positions.reserve(numPolygons * 9);
	for (unsigned int i = 0; i < numPolygons; ++i) {
		const RAS_Mesh::PolygonInfo poly = mesh->GetPolygon(i);
		for (unsigned int j = 0; j < 3; ++j) {
			const float *co = poly.array->GetPosition(poly.indices[j]).data;
			positions.insert(positions.end(), co, co + 3);
		}
	}

	MeshBuffer buffer = {0, (int)(positions.size() / 3)};
	glGenBuffers(1, &buffer.vbo);
	glBindBuffer(GL_ARRAY_BUFFER, buffer.vbo);
	glBufferData(GL_ARRAY_BUFFER, positions.size() * sizeof(float), positions.data(), GL_STATIC_DRAW);
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	return m_meshBuffers.emplace(mesh, buffer).first->second;
}

bool KX_RainSurfaceMask::EnsureGL(int width, int height)
{
	if (m_glFailed) {
		return false;
	}

	if (!m_program) {
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
			CM_Error("rain mask shader compile failed:\n" << log);
			glDeleteShader(vert);
			glDeleteShader(frag);
			m_glFailed = true;
			return false;
		}

		m_program = glCreateProgram();
		glAttachShader(m_program, vert);
		glAttachShader(m_program, frag);
		glBindAttribLocation(m_program, 0, "in_pos");
		glBindFragDataLocation(m_program, 0, "fragColor");
		glLinkProgram(m_program);
		glDeleteShader(vert);
		glDeleteShader(frag);
		glGetProgramiv(m_program, GL_LINK_STATUS, &status);
		if (!status) {
			glGetProgramInfoLog(m_program, sizeof(log), &length, log);
			CM_Error("rain mask shader link failed:\n" << log);
			glDeleteProgram(m_program);
			m_program = 0;
			m_glFailed = true;
			return false;
		}
		m_viewLoc = glGetUniformLocation(m_program, "u_view");
		m_projLoc = glGetUniformLocation(m_program, "u_projection");
		m_modelLoc = glGetUniformLocation(m_program, "u_model");
		m_flagsLoc = glGetUniformLocation(m_program, "u_flags");
		glGenVertexArrays(1, &m_vao);
	}

	if (m_fbo && width == m_width && height == m_height) {
		return true;
	}

	if (!m_fbo) {
		glGenFramebuffers(1, &m_fbo);
		glGenTextures(1, &m_texture);
		glGenRenderbuffers(1, &m_depth);
	}
	m_width = width;
	m_height = height;

	glBindTexture(GL_TEXTURE_2D, m_texture);
	glTexImage2D(GL_TEXTURE_2D, 0, GL_RG32F, width, height, 0, GL_RG, GL_FLOAT, nullptr);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	glBindTexture(GL_TEXTURE_2D, 0);

	glBindRenderbuffer(GL_RENDERBUFFER, m_depth);
	glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, width, height);
	glBindRenderbuffer(GL_RENDERBUFFER, 0);

	GLint previous = 0;
	glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &previous);
	glBindFramebuffer(GL_FRAMEBUFFER, m_fbo);
	glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, m_texture, 0);
	glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, m_depth);
	const GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
	glBindFramebuffer(GL_FRAMEBUFFER, previous);
	if (status != GL_FRAMEBUFFER_COMPLETE) {
		CM_Error("rain mask framebuffer incomplete (0x" << std::hex << status << std::dec << "), ripples/splash stay on every object");
		m_glFailed = true;
		return false;
	}
	return true;
}

int KX_RainSurfaceMask::Render(KX_Scene *scene, const World *world, double time, const mt::mat4& view,
                               const mt::mat4& projection, int width, int height)
{
	if (time >= m_nextScan || time + kScanInterval < m_nextScan) {
		m_nextScan = time + kScanInterval;
		RefreshTargets(scene);
	}

	// Only the effects that are on and have marked objects need the mask.
	int flags = m_flags;
	if (!(world->weather_flag & WO_WEATHER_RAIN_RIPPLE)) {
		flags &= ~MASK_RIPPLE;
	}
	if (!(world->weather_flag & WO_WEATHER_RAIN_SPLASH)) {
		flags &= ~MASK_SPLASH;
	}
	if (!(world->weather_flag & WO_WEATHER_RAIN_PUDDLES)) {
		flags &= ~MASK_PUDDLE;
	}
	if (!flags || width <= 0 || height <= 0 || !EnsureGL(width, height)) {
		return 0;
	}

	// Effects reach only Distance meters from the camera: skip objects whose bounds are farther.
	const mt::mat4 viewInv = view.Inverse();
	const mt::vec3 camPos(viewInv(0, 3), viewInv(1, 3), viewInv(2, 3));
	const float rippleDist = world->rain_ripple_distance;
	const float splashDist = world->rain_splash_distance;
	const float puddleDist = world->rain_puddle_distance;

	m_draws.clear();
	for (const Target& target : m_targets) {
		KX_GameObject *gameobj = target.gameobj;
		if (!(target.flags & flags) || !gameobj->GetVisible() || gameobj->GetCullingNode().GetCulled()) {
			continue;
		}
		float maxDist = 0.0f;
		if (target.flags & flags & MASK_RIPPLE) {
			maxDist = std::max(maxDist, rippleDist);
		}
		if (target.flags & flags & MASK_SPLASH) {
			maxDist = std::max(maxDist, splashDist);
		}
		if (target.flags & flags & MASK_PUDDLE) {
			maxDist = std::max(maxDist, puddleDist);
		}
		const SG_BBox& box = gameobj->GetCullingNode().GetAabb();
		const mt::vec3 scale = gameobj->NodeGetWorldScaling();
		const float radius = box.GetRadius() * std::max(std::fabs(scale.x), std::max(std::fabs(scale.y), std::fabs(scale.z)));
		const mt::vec3 center = gameobj->NodeGetWorldTransform() * box.GetCenter();
		if ((center - camPos).Length() - radius > maxDist) {
			continue;
		}
		Draw item;
		item.gameobj = gameobj;
		item.flags = target.flags;
		item.model = mt::mat4::FromAffineTransform(gameobj->NodeGetWorldTransform());
		item.meshes = gameobj->GetMeshList();
		m_draws.push_back(item);
	}

	// Nothing moved since the last frame: the texture still holds the right mask.
	if (m_valid && width == m_drawnWidth && height == m_drawnHeight && SameMatrix(view, m_drawnView) &&
	    SameMatrix(projection, m_drawnProjection) && m_draws == m_drawnItems)
	{
		return flags;
	}
	m_valid = true;
	m_drawnWidth = width;
	m_drawnHeight = height;
	m_drawnView = view;
	m_drawnProjection = projection;
	m_drawnItems = m_draws;

	GLint previousFbo = 0;
	GLint viewport[4];
	glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &previousFbo);
	glGetIntegerv(GL_VIEWPORT, viewport);
	const GLboolean depthTest = glIsEnabled(GL_DEPTH_TEST);
	const GLboolean cullFace = glIsEnabled(GL_CULL_FACE);
	const GLboolean blend = glIsEnabled(GL_BLEND);
	const GLboolean scissor = glIsEnabled(GL_SCISSOR_TEST);
	GLfloat clearColor[4];
	GLint depthFunc;
	GLboolean depthMask;
	glGetFloatv(GL_COLOR_CLEAR_VALUE, clearColor);
	glGetIntegerv(GL_DEPTH_FUNC, &depthFunc);
	glGetBooleanv(GL_DEPTH_WRITEMASK, &depthMask);

	glBindFramebuffer(GL_FRAMEBUFFER, m_fbo);
	glViewport(0, 0, width, height);
	glDisable(GL_SCISSOR_TEST);
	glDisable(GL_BLEND);
	glDisable(GL_CULL_FACE);
	glEnable(GL_DEPTH_TEST);
	glDepthFunc(GL_LEQUAL);
	glDepthMask(GL_TRUE);
	glClearColor(0.0f, 0.0f, 0.0f, 0.0f);
	glClearDepth(1.0);
	glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

	glUseProgram(m_program);
	glUniformMatrix4fv(m_viewLoc, 1, GL_FALSE, (const float *)view.Data());
	glUniformMatrix4fv(m_projLoc, 1, GL_FALSE, (const float *)projection.Data());
	glBindVertexArray(m_vao);
	glEnableVertexAttribArray(0);

	for (const Draw& item : m_draws) {
		glUniformMatrix4fv(m_modelLoc, 1, GL_FALSE, (const float *)item.model.Data());
		glUniform1f(m_flagsLoc, (float)item.flags);
		for (RAS_Mesh *mesh : item.meshes) {
			const MeshBuffer& buffer = GetMeshBuffer(mesh);
			if (buffer.count == 0) {
				continue;
			}
			glBindBuffer(GL_ARRAY_BUFFER, buffer.vbo);
			glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * sizeof(float), (void *)0);
			glDrawArrays(GL_TRIANGLES, 0, buffer.count);
		}
	}

	glDisableVertexAttribArray(0);
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	glBindVertexArray(0);
	glUseProgram(0);

	glBindFramebuffer(GL_FRAMEBUFFER, previousFbo);
	glViewport(viewport[0], viewport[1], viewport[2], viewport[3]);
	glClearColor(clearColor[0], clearColor[1], clearColor[2], clearColor[3]);
	glDepthFunc(depthFunc);
	glDepthMask(depthMask);
	if (!depthTest) {
		glDisable(GL_DEPTH_TEST);
	}
	if (cullFace) {
		glEnable(GL_CULL_FACE);
	}
	if (blend) {
		glEnable(GL_BLEND);
	}
	if (scissor) {
		glEnable(GL_SCISSOR_TEST);
	}
	return flags;
}
