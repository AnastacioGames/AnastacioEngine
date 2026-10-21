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

/** \file gameengine/Ketsji/KX_RainShelterMap.cpp
 *  \ingroup ketsji
 */

#include "KX_RainShelterMap.h"

#include <cfloat>

#include "KX_Scene.h"
#include "KX_GameObject.h"
#include "KX_Mesh.h"
#include "RAS_DisplayArray.h"
#include "SG_CullingNode.h"
#include "EXP_ListValue.h"
#include "CM_Message.h"

#include "GPU_glew.h"
#include "RAS_WebGLCompat.h"

#include <algorithm>
#include <cmath>
#include <cstring>

const char *const KX_RainShelterMap::ShelterProperty = "rain_shelter";

/// How often the list of shelter objects is rebuilt (added objects, changed properties).
static const double kScanInterval = 0.5;
/// Map side in texels and half its size in meters: 128 m around the camera, 25 cm per texel.
static const int kSize = 512;
static const float kHalfExtent = 64.0f;
/// The map looks down from this far above the camera, and sees this deep.
static const float kAbove = 1000.0f;
static const float kDepthRange = 2000.0f;

static const char *kVertexSource =
	"#version 130\n"
	"in vec3 in_pos;\n"
	"out float v_height;\n"
	"uniform mat4 u_model;\n"
	"uniform mat4 u_viewproj;\n"
	"void main() {\n"
	"	vec4 world = u_model * vec4(in_pos, 1.0);\n"
	"	v_height = world.z;\n"
	"	gl_Position = u_viewproj * world;\n"
	"}\n";

static const char *kFragmentSource =
	"#version 130\n"
	"in float v_height;\n"
	"out vec4 fragColor;\n"
	"void main() {\n"
	"	fragColor = vec4(v_height, 0.0, 0.0, 0.0);\n"
	"}\n";

static bool same_matrix(const mt::mat4& a, const mt::mat4& b)
{
	return std::memcmp(a.Data(), b.Data(), sizeof(float) * 16) == 0;
}

bool KX_RainShelterMap::Draw::operator==(const Draw& other) const
{
	return gameobj == other.gameobj && same_matrix(model, other.model) && meshes == other.meshes;
}

KX_RainShelterMap::KX_RainShelterMap()
	:m_drawnCenter{0.0f, 0.0f},
	m_valid(false),
	m_nextScan(0.0),
	m_cameraCovered(false),
	m_program(0),
	m_vao(0),
	m_fbo(0),
	m_texture(0),
	m_depth(0),
	m_viewProjLoc(-1),
	m_modelLoc(-1),
	m_glFailed(false)
{
}

KX_RainShelterMap::~KX_RainShelterMap()
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

bool KX_RainShelterMap::IsCameraCovered() const
{
	return m_cameraCovered;
}

unsigned int KX_RainShelterMap::GetTexture() const
{
	return m_texture;
}

void KX_RainShelterMap::RemoveObject(KX_GameObject *gameobj)
{
	m_valid = false;
	m_drawnItems.clear();
	m_targets.erase(std::remove(m_targets.begin(), m_targets.end(), gameobj), m_targets.end());
}

void KX_RainShelterMap::ClearMeshBuffers()
{
	m_valid = false;
	for (const auto& item : m_meshBuffers) {
		glDeleteBuffers(1, &item.second.vbo);
	}
	m_meshBuffers.clear();
}

void KX_RainShelterMap::RefreshTargets(KX_Scene *scene)
{
	std::vector<KX_GameObject *> targets;
	for (KX_GameObject *gameobj : *scene->GetObjectList()) {
		if (gameobj->GetMeshList().empty()) {
			continue;
		}
		EXP_Value *shelter = gameobj->GetProperty(ShelterProperty);
		if (shelter && shelter->GetNumber() != 0.0) {
			targets.push_back(gameobj);
		}
	}
	if (targets != m_targets) {
		CM_Message("rain shelter: " << targets.size() << " object(s) with \"" << ShelterProperty << "\"");
		m_targets.swap(targets);
		// Meshes of removed objects may have been freed: never keep a stale pointer as key.
		ClearMeshBuffers();
	}
}

const KX_RainShelterMap::MeshBuffer& KX_RainShelterMap::GetMeshBuffer(RAS_Mesh *mesh)
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

bool KX_RainShelterMap::EnsureGL()
{
	if (m_glFailed) {
		return false;
	}
	if (m_fbo) {
		return true;
	}

	GLuint vert = glCreateShader(GL_VERTEX_SHADER);
	RAS_ShaderSource(vert, kVertexSource);
	glCompileShader(vert);
	GLuint frag = glCreateShader(GL_FRAGMENT_SHADER);
	RAS_ShaderSource(frag, kFragmentSource);
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
		CM_Error("rain shelter shader compile failed:\n" << log);
		glDeleteShader(vert);
		glDeleteShader(frag);
		m_glFailed = true;
		return false;
	}

	m_program = glCreateProgram();
	glAttachShader(m_program, vert);
	glAttachShader(m_program, frag);
	glBindAttribLocation(m_program, 0, "in_pos");
	RAS_BindFragDataLocation(m_program, 0, "fragColor");
	glLinkProgram(m_program);
	glDeleteShader(vert);
	glDeleteShader(frag);
	glGetProgramiv(m_program, GL_LINK_STATUS, &status);
	if (!status) {
		glGetProgramInfoLog(m_program, sizeof(log), &length, log);
		CM_Error("rain shelter shader link failed:\n" << log);
		glDeleteProgram(m_program);
		m_program = 0;
		m_glFailed = true;
		return false;
	}
	m_viewProjLoc = glGetUniformLocation(m_program, "u_viewproj");
	m_modelLoc = glGetUniformLocation(m_program, "u_model");
	glGenVertexArrays(1, &m_vao);

	// The R32F target needs EXT_color_buffer_float on WebGL2.
	if (!RAS_FloatRenderTargetSupported()) {
		CM_Warning("rain shelter: no float render target, it rains under the shelters");
		m_glFailed = true;
		return false;
	}
	glGenFramebuffers(1, &m_fbo);
	glGenTextures(1, &m_texture);
	glGenRenderbuffers(1, &m_depth);

	glBindTexture(GL_TEXTURE_2D, m_texture);
	glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, kSize, kSize, 0, GL_RED, GL_FLOAT, nullptr);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	glBindTexture(GL_TEXTURE_2D, 0);

	glBindRenderbuffer(GL_RENDERBUFFER, m_depth);
	glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, kSize, kSize);
	glBindRenderbuffer(GL_RENDERBUFFER, 0);

	GLint previous = 0;
	glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &previous);
	glBindFramebuffer(GL_FRAMEBUFFER, m_fbo);
	glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, m_texture, 0);
	glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, m_depth);
	const GLenum fbStatus = glCheckFramebufferStatus(GL_FRAMEBUFFER);
	glBindFramebuffer(GL_FRAMEBUFFER, previous);
	if (fbStatus != GL_FRAMEBUFFER_COMPLETE) {
		CM_Error("rain shelter framebuffer incomplete (0x" << std::hex << fbStatus << std::dec << "), it rains under the shelters");
		m_glFailed = true;
		return false;
	}
	return true;
}

bool KX_RainShelterMap::Render(KX_Scene *scene, double time, const mt::vec3& camPos, float area[4])
{
	area[0] = area[1] = area[2] = area[3] = 0.0f;
	m_cameraCovered = false;
	if (time >= m_nextScan || time + kScanInterval < m_nextScan) {
		m_nextScan = time + kScanInterval;
		RefreshTargets(scene);
	}
	if (m_targets.empty() || !EnsureGL()) {
		return false;
	}

	// Center snapped to whole texels, so the map does not shimmer as the camera moves.
	const float texel = 2.0f * kHalfExtent / (float)kSize;
	const float cx = std::floor(camPos.x / texel) * texel;
	const float cy = std::floor(camPos.y / texel) * texel;
	area[0] = cx;
	area[1] = cy;
	area[2] = 1.0f / (2.0f * kHalfExtent);
	area[3] = 1.0f;

	// Shelters out of the map are skipped. Culling and visibility do not matter: a roof out
	// of view still keeps the rain off, and a shelter may be an invisible helper object.
	m_draws.clear();
	for (KX_GameObject *gameobj : m_targets) {
		const SG_BBox& box = gameobj->GetCullingNode().GetAabb();
		const mt::vec3 scale = gameobj->NodeGetWorldScaling();
		const float radius = box.GetRadius() * std::max(std::fabs(scale.x), std::max(std::fabs(scale.y), std::fabs(scale.z)));
		const mt::vec3 center = gameobj->NodeGetWorldTransform() * box.GetCenter();
		if (std::fabs(center.x - cx) - radius > kHalfExtent || std::fabs(center.y - cy) - radius > kHalfExtent) {
			continue;
		}
		// Camera under this shelter: inside its world box seen from above, below its top.
		if (!m_cameraCovered) {
			const mt::mat3x4 trans = gameobj->NodeGetWorldTransform();
			const mt::vec3& bmin = box.GetMin();
			const mt::vec3& bmax = box.GetMax();
			mt::vec3 wmin(FLT_MAX, FLT_MAX, FLT_MAX);
			mt::vec3 wmax(-FLT_MAX, -FLT_MAX, -FLT_MAX);
			for (int i = 0; i < 8; ++i) {
				const mt::vec3 corner((i & 1) ? bmax.x : bmin.x, (i & 2) ? bmax.y : bmin.y, (i & 4) ? bmax.z : bmin.z);
				const mt::vec3 p = trans * corner;
				for (int k = 0; k < 3; ++k) {
					wmin[k] = std::min(wmin[k], p[k]);
					wmax[k] = std::max(wmax[k], p[k]);
				}
			}
			m_cameraCovered = camPos.x >= wmin.x && camPos.x <= wmax.x &&
			                  camPos.y >= wmin.y && camPos.y <= wmax.y && camPos.z <= wmax.z;
		}
		Draw item;
		item.gameobj = gameobj;
		item.model = mt::mat4::FromAffineTransform(gameobj->NodeGetWorldTransform());
		item.meshes = gameobj->GetMeshList();
		m_draws.push_back(item);
	}

	// Same place and nothing moved: the texture still holds the right map.
	if (m_valid && cx == m_drawnCenter[0] && cy == m_drawnCenter[1] && m_draws == m_drawnItems) {
		return true;
	}
	m_valid = true;
	m_drawnCenter[0] = cx;
	m_drawnCenter[1] = cy;
	m_drawnItems = m_draws;

	// Orthographic view straight down (-Z), +Y up on the map: x, y map to [-1, 1] around the
	// center, and z maps kAbove above the camera to depth -1 (the highest surface wins).
	const float top = camPos.z + kAbove;
	mt::mat4 viewProj = mt::mat4::Identity();
	viewProj(0, 0) = 1.0f / kHalfExtent;
	viewProj(0, 3) = -cx / kHalfExtent;
	viewProj(1, 1) = 1.0f / kHalfExtent;
	viewProj(1, 3) = -cy / kHalfExtent;
	viewProj(2, 2) = -2.0f / kDepthRange;
	viewProj(2, 3) = 2.0f * top / kDepthRange - 1.0f;

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
	glViewport(0, 0, kSize, kSize);
	glDisable(GL_SCISSOR_TEST);
	glDisable(GL_BLEND);
	glDisable(GL_CULL_FACE);
	glEnable(GL_DEPTH_TEST);
	glDepthFunc(GL_LEQUAL);
	glDepthMask(GL_TRUE);
	// No shelter: a height far below anything, so nothing is under it.
	glClearColor(-1.0e9f, 0.0f, 0.0f, 0.0f);
	glClearDepth(1.0);
	glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

	glUseProgram(m_program);
	glUniformMatrix4fv(m_viewProjLoc, 1, GL_FALSE, (const float *)viewProj.Data());
	glBindVertexArray(m_vao);
	glEnableVertexAttribArray(0);

	for (const Draw& item : m_draws) {
		glUniformMatrix4fv(m_modelLoc, 1, GL_FALSE, (const float *)item.model.Data());
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
	return true;
}
