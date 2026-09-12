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
 * Contributor(s): Tristan Porteries.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Rasterizer/RAS_OpenGLRasterizer/RAS_OpenGLDebugDraw.cpp
 *  \ingroup bgerastogl
 */

#include "RAS_OpenGLDebugDraw.h"
#include "RAS_Rasterizer.h"
#include "RAS_ICanvas.h"
#include "RAS_DebugDraw.h"

#include "GPU_material.h"
#include "GPU_glew.h"
#include "GPU_shader.h"
#include "GPU_vertex_array.h"

extern "C" {
#  include "BLF_api.h"
}

template<class Item>
inline static void updateVbo(unsigned int vbo, const std::vector<Item>& data)
{
	glBindBuffer(GL_ARRAY_BUFFER, vbo);
	glBufferData(GL_ARRAY_BUFFER, sizeof(Item) * data.size(), data.data(), GL_STATIC_DRAW);
}

inline static void attribVector(unsigned short loc, unsigned short stride, intptr_t offset, unsigned short size, unsigned short divisor)
{
	glEnableVertexAttribArray(loc);
	glVertexAttribPointer(loc, size, GL_FLOAT, false, stride, (const void *)offset);
	glVertexAttribDivisorARB(loc, divisor);
}

inline static void attribMatrix(unsigned short loc, unsigned short stride, intptr_t offset, unsigned short size, unsigned short divisor)
{
	for (unsigned short i = 0; i < size; ++i) {
		glEnableVertexAttribArray(loc + i);
		glVertexAttribPointer(loc + i, size, GL_FLOAT, false, stride, (const void *)(offset + size * i * sizeof(float)));
		glVertexAttribDivisorARB(loc + i, divisor);
	}
}

RAS_OpenGLDebugDraw::RAS_OpenGLDebugDraw()
{
	static const GLubyte boxIndices[] = {
		0, 1, 1, 2, 2, 3, 3, 0, 0, 4, 4, 5, 5, 6, 6, 7, 7, 4, 1, 5, 2, 6, 3, 7, // Wire (24).
		0, 1, 2, 2, 3, 0, 1, 5, 6, 6, 2, 1, 7, 6, 5, 5, 4, 7, 4, 0, 3, 3, 7, 4, 4, 5, 1, 1, 0, 4, 3, 2, 6, 6, 7, 3 // Solid (36).
	};

	static const float unitBoxVertices[24] = {
		-1.0f, -1.0f, -1.0f,
		1.0f, -1.0f, -1.0f,
		1.0f, 1.0f, -1.0f,
		-1.0f, 1.0f, -1.0f,
		-1.0f, -1.0f, 1.0f,
		1.0f, -1.0f, 1.0f,
		1.0f, 1.0f, 1.0f,
		-1.0f, 1.0f, 1.0f
	};

	static const float unitBox2DVertices[8] = {
		0.0f, 0.0f,
		1.0f, 0.0f,
		1.0f, 1.0f,
		0.0f, 1.0f
	};

	/* Centered unit quad used to expand light-glow billboards around their world-space center
	 * (see gpu_shader_light_glow_vert.glsl), as opposed to unitBox2DVertices' [0,1] corner-anchored
	 * quad used for 2D screen boxes. */
	static const float unitGlowVertices[8] = {
		-0.5f, -0.5f,
		0.5f, -0.5f,
		0.5f, 0.5f,
		-0.5f, 0.5f
	};

	glGenBuffers(MAX_IBO, m_ibos);
	glGenBuffers(MAX_VBO, m_vbos);

	// Initialize static IBOs and VBOs.
	glBindBuffer(GL_ARRAY_BUFFER, m_ibos[BOX_IBO]);
	glBufferData(GL_ARRAY_BUFFER, sizeof(boxIndices), (void *)boxIndices, GL_STATIC_DRAW);

	glBindBuffer(GL_ARRAY_BUFFER, m_vbos[BOX_UNIT_VBO]);
	glBufferData(GL_ARRAY_BUFFER, sizeof(unitBoxVertices), (void *)unitBoxVertices, GL_STATIC_DRAW);

	glBindBuffer(GL_ARRAY_BUFFER, m_vbos[BOX_2D_UNIT_VBO]);
	glBufferData(GL_ARRAY_BUFFER, sizeof(unitBox2DVertices), (void *)unitBox2DVertices, GL_STATIC_DRAW);

	glBindBuffer(GL_ARRAY_BUFFER, m_vbos[GLOW_UNIT_VBO]);
	glBufferData(GL_ARRAY_BUFFER, sizeof(unitGlowVertices), (void *)unitGlowVertices, GL_STATIC_DRAW);

	glBindBuffer(GL_ARRAY_BUFFER, 0);

	m_colorShader = GPU_shader_get_builtin_shader(GPU_SHADER_FLAT_COLOR);
	m_frustumLineShader = GPU_shader_get_builtin_shader(GPU_SHADER_FRUSTUM_LINE);
	m_frustumSolidShader = GPU_shader_get_builtin_shader(GPU_SHADER_FRUSTUM_SOLID);
	m_box2dShader = GPU_shader_get_builtin_shader(GPU_SHADER_2D_BOX);
	m_lightGlowShader = GPU_shader_get_builtin_shader(GPU_SHADER_LIGHT_GLOW);

	m_colorViewProjUniform = GPU_shader_get_uniform(m_colorShader, "unfviewprojmat");
	m_frustumLineViewProjUniform = GPU_shader_get_uniform(m_frustumLineShader, "unfviewprojmat");
	m_frustumSolidViewProjUniform = GPU_shader_get_uniform(m_frustumSolidShader, "unfviewprojmat");
	m_box2dOrthoUniform = GPU_shader_get_uniform(m_box2dShader, "unforthomat");
	m_lightGlowViewProjUniform = GPU_shader_get_uniform(m_lightGlowShader, "unfviewprojmat");
	m_lightGlowCamRightUniform = GPU_shader_get_uniform(m_lightGlowShader, "unfcamright");
	m_lightGlowCamUpUniform = GPU_shader_get_uniform(m_lightGlowShader, "unfcamup");

	GPU_create_vertex_arrays(MAX_VAO, m_vaos);
	GPU_bind_vertex_array(m_vaos[LINES_VAO]);
	{
		static const unsigned short stride = sizeof(RAS_DebugDraw::Line) / 2;
		const unsigned int pos = GPU_shader_get_attribute(m_colorShader, "pos");
		const unsigned int color = GPU_shader_get_attribute(m_colorShader, "color");

		glBindBuffer(GL_ARRAY_BUFFER, m_vbos[LINES_VBO]);
		attribVector(pos, stride, offsetof(RAS_DebugDraw::Line, m_from), 3, 0);
		attribVector(color, stride, offsetof(RAS_DebugDraw::Line, m_color), 4, 0);
	}

	static const unsigned short frustumStride = sizeof(RAS_DebugDraw::Frustum);

	GPU_bind_vertex_array(m_vaos[FRUSTUMS_LINE_VAO]);
	{
		const unsigned short pos = GPU_shader_get_attribute(m_frustumLineShader, "pos");
		const unsigned short mat = GPU_shader_get_attribute(m_frustumLineShader, "mat");
		const unsigned short color = GPU_shader_get_attribute(m_frustumLineShader, "color");

		glBindBuffer(GL_ARRAY_BUFFER, m_vbos[BOX_UNIT_VBO]);
		attribVector(pos, 0, 0, 3, 0);

		glBindBuffer(GL_ARRAY_BUFFER, m_vbos[FRUSTUMS_VBO]);
		attribVector(color, frustumStride, offsetof(RAS_DebugDraw::Frustum, m_wireColor), 4, 1);
		attribMatrix(mat, frustumStride, offsetof(RAS_DebugDraw::Frustum, m_persMat), 4, 1);

		glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, m_ibos[BOX_IBO]);
	}

	GPU_bind_vertex_array(m_vaos[FRUSTUMS_SOLID_VAO]);
	{
		const unsigned short pos = GPU_shader_get_attribute(m_frustumSolidShader, "pos");
		const unsigned short mat = GPU_shader_get_attribute(m_frustumSolidShader, "mat");
		const unsigned short insideColor = GPU_shader_get_attribute(m_frustumSolidShader, "insideColor");
		const unsigned short outsideColor = GPU_shader_get_attribute(m_frustumSolidShader, "outsideColor");

		glBindBuffer(GL_ARRAY_BUFFER, m_vbos[BOX_UNIT_VBO]);
		attribVector(pos, 0, 0, 3, 0);

		glBindBuffer(GL_ARRAY_BUFFER, m_vbos[FRUSTUMS_VBO]);
		attribVector(insideColor, frustumStride, offsetof(RAS_DebugDraw::Frustum, m_insideColor), 4, 1);
		attribVector(outsideColor, frustumStride, offsetof(RAS_DebugDraw::Frustum, m_outsideColor), 4, 1);
		attribMatrix(mat, frustumStride, offsetof(RAS_DebugDraw::Frustum, m_persMat), 4, 1);

		glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, m_ibos[BOX_IBO]);
	}

	GPU_bind_vertex_array(m_vaos[AABB_VAO]);
	{
		static const unsigned short stride = sizeof(RAS_DebugDraw::Aabb);
		const unsigned short pos = GPU_shader_get_attribute(m_frustumLineShader, "pos");
		const unsigned short mat = GPU_shader_get_attribute(m_frustumLineShader, "mat");
		const unsigned short color = GPU_shader_get_attribute(m_frustumLineShader, "color");

		glBindBuffer(GL_ARRAY_BUFFER, m_vbos[BOX_UNIT_VBO]);
		attribVector(pos, 0, 0, 3, 0);

		glBindBuffer(GL_ARRAY_BUFFER, m_vbos[AABB_VBO]);
		attribVector(color, stride, offsetof(RAS_DebugDraw::Aabb, m_color), 4, 1);
		attribMatrix(mat, stride, offsetof(RAS_DebugDraw::Aabb, m_mat), 4, 1);

		glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, m_ibos[BOX_IBO]);
	}

	GPU_bind_vertex_array(m_vaos[BOX_2D_VAO]);
	{
		static const unsigned short stride = sizeof(RAS_DebugDraw::Box2d);
		const unsigned short pos = GPU_shader_get_attribute(m_box2dShader, "pos");
		const unsigned short trans = GPU_shader_get_attribute(m_box2dShader, "trans");
		const unsigned short color = GPU_shader_get_attribute(m_box2dShader, "color");

		glBindBuffer(GL_ARRAY_BUFFER, m_vbos[BOX_2D_UNIT_VBO]);
		attribVector(pos, 0, 0, 2, 0);

		glBindBuffer(GL_ARRAY_BUFFER, m_vbos[BOX_2D_VBO]);
		attribVector(color, stride, offsetof(RAS_DebugDraw::Box2d, m_color), 4, 1);
		attribVector(trans, stride, offsetof(RAS_DebugDraw::Box2d, m_trans), 4, 1);
	}

	GPU_bind_vertex_array(m_vaos[LIGHT_GLOW_VAO]);
	{
		static const unsigned short stride = sizeof(RAS_DebugDraw::LightGlow);
		const unsigned short pos = GPU_shader_get_attribute(m_lightGlowShader, "pos");
		const unsigned short center = GPU_shader_get_attribute(m_lightGlowShader, "center");
		const unsigned short size = GPU_shader_get_attribute(m_lightGlowShader, "size");
		const unsigned short color = GPU_shader_get_attribute(m_lightGlowShader, "color");

		glBindBuffer(GL_ARRAY_BUFFER, m_vbos[GLOW_UNIT_VBO]);
		attribVector(pos, 0, 0, 2, 0);

		glBindBuffer(GL_ARRAY_BUFFER, m_vbos[LIGHT_GLOWS_VBO]);
		attribVector(color, stride, offsetof(RAS_DebugDraw::LightGlow, m_color), 4, 1);
		attribVector(center, stride, offsetof(RAS_DebugDraw::LightGlow, m_pos), 3, 1);
		attribVector(size, stride, offsetof(RAS_DebugDraw::LightGlow, m_size), 1, 1);
	}

	GPU_unbind_vertex_array();
	glBindBuffer(GL_ARRAY_BUFFER, 0);
}

RAS_OpenGLDebugDraw::~RAS_OpenGLDebugDraw()
{
	glDeleteBuffers(MAX_IBO, m_ibos);
	glDeleteBuffers(MAX_VBO, m_vbos);
	GPU_delete_vertex_arrays(MAX_VAO, m_vaos);
}

void RAS_OpenGLDebugDraw::Flush(RAS_Rasterizer *rasty, RAS_ICanvas *canvas, RAS_DebugDraw *debugDraw)
{
	rasty->SetFrontFace(true);
	rasty->SetAlphaBlend(GPU_BLEND_ALPHA);
	rasty->DisableLights();

	/* Core profile has no fixed-function matrix stack for these builtin shaders to read
	 * gl_ProjectionMatrix/gl_ModelViewMatrix from -- computed once here and uploaded
	 * explicitly below (see gpu_shader_flat_color_vert.glsl/gpu_shader_frustum_*_vert.glsl). */
	const mt::mat4 viewProjMat = rasty->GetProjectionMatrix() * rasty->GetViewMatrix();

	// draw lines
	const std::vector<RAS_DebugDraw::Line>& lines = debugDraw->m_lines;
	const unsigned int numlines = lines.size();
	if (numlines > 0) {
		updateVbo(m_vbos[LINES_VBO], lines);

		GPU_bind_vertex_array(m_vaos[LINES_VAO]);
		GPU_shader_bind(m_colorShader);
		if (m_colorViewProjUniform != -1) {
			GPU_shader_uniform_vector(m_colorShader, m_colorViewProjUniform, 16, 1, (const float *)viewProjMat.Data());
		}
		glDrawArrays(GL_LINES, 0, numlines * 2);
	}

	const std::vector<RAS_DebugDraw::Frustum>& frustums = debugDraw->m_frustums;
	const unsigned int numfrustums = frustums.size();
	if (numfrustums > 0) {
		updateVbo(m_vbos[FRUSTUMS_VBO], frustums);

		GPU_bind_vertex_array(m_vaos[FRUSTUMS_LINE_VAO]);
		GPU_shader_bind(m_frustumLineShader);
		if (m_frustumLineViewProjUniform != -1) {
			GPU_shader_uniform_vector(m_frustumLineShader, m_frustumLineViewProjUniform, 16, 1, (const float *)viewProjMat.Data());
		}
		glDrawElementsInstancedARB(GL_LINES, 24, GL_UNSIGNED_BYTE, nullptr, numfrustums);

		GPU_bind_vertex_array(m_vaos[FRUSTUMS_SOLID_VAO]);
		GPU_shader_bind(m_frustumSolidShader);
		if (m_frustumSolidViewProjUniform != -1) {
			GPU_shader_uniform_vector(m_frustumSolidShader, m_frustumSolidViewProjUniform, 16, 1, (const float *)viewProjMat.Data());
		}
		glDrawElementsInstancedARB(GL_TRIANGLES, 36, GL_UNSIGNED_BYTE, (const void *)(sizeof(GLubyte) * 24), numfrustums);
	}

	const std::vector<RAS_DebugDraw::Aabb>& aabbs = debugDraw->m_aabbs;
	const unsigned int numaabbs = aabbs.size();
	if (numaabbs > 0) {
		updateVbo(m_vbos[AABB_VBO], aabbs);

		GPU_bind_vertex_array(m_vaos[AABB_VAO]);
		GPU_shader_bind(m_frustumLineShader);
		if (m_frustumLineViewProjUniform != -1) {
			GPU_shader_uniform_vector(m_frustumLineShader, m_frustumLineViewProjUniform, 16, 1, (const float *)viewProjMat.Data());
		}
		glDrawElementsInstancedARB(GL_LINES, 24, GL_UNSIGNED_BYTE, nullptr, numaabbs);
	}

	const std::vector<RAS_DebugDraw::LightGlow>& lightGlows = debugDraw->m_lightGlows;
	const unsigned int numLightGlows = lightGlows.size();
	if (numLightGlows > 0) {
		updateVbo(m_vbos[LIGHT_GLOWS_VBO], lightGlows);

		/* True screen-facing billboard ("always face camera"): the camera's world-space right/up
		 * vectors are the first two rows of the view matrix (its rotation part is the camera's
		 * world orientation transposed, so its rows are that orientation's columns -- the camera's
		 * own right/up/back axes expressed in world space). See gpu_shader_light_glow_vert.glsl. */
		const mt::mat4& viewMat = rasty->GetViewMatrix();
		const mt::vec3 camRight = viewMat.GetRow(0).xyz();
		const mt::vec3 camUp = viewMat.GetRow(1).xyz();

		GPU_bind_vertex_array(m_vaos[LIGHT_GLOW_VAO]);
		GPU_shader_bind(m_lightGlowShader);
		if (m_lightGlowViewProjUniform != -1) {
			GPU_shader_uniform_vector(m_lightGlowShader, m_lightGlowViewProjUniform, 16, 1, (const float *)viewProjMat.Data());
		}
		if (m_lightGlowCamRightUniform != -1) {
			GPU_shader_uniform_vector(m_lightGlowShader, m_lightGlowCamRightUniform, 3, 1, (const float *)camRight.Data());
		}
		if (m_lightGlowCamUpUniform != -1) {
			GPU_shader_uniform_vector(m_lightGlowShader, m_lightGlowCamUpUniform, 3, 1, (const float *)camUp.Data());
		}
		glDrawArraysInstancedARB(GL_TRIANGLE_FAN, 0, 4, numLightGlows);
	}

	const unsigned int width = canvas->GetWidth();
	const unsigned int height = canvas->GetHeight();

	rasty->Disable(RAS_Rasterizer::RAS_DEPTH_TEST);
	rasty->DisableForText();

	rasty->PushMatrix();
	rasty->LoadIdentity();

	rasty->SetMatrixMode(RAS_Rasterizer::RAS_PROJECTION);
	rasty->PushMatrix();
	rasty->LoadIdentity();

#ifdef WITH_GL_PROFILE_COMPAT
	glOrtho(0, width, height, 0, -100, 100);
#endif

	const std::vector<RAS_DebugDraw::Box2d>& boxes2d = debugDraw->m_boxes2d;
	const unsigned int numboxes = boxes2d.size();
	if (numboxes > 0) {
		updateVbo(m_vbos[BOX_2D_VBO], boxes2d);

		GPU_bind_vertex_array(m_vaos[BOX_2D_VAO]);
		GPU_shader_bind(m_box2dShader);
		if (m_box2dOrthoUniform != -1) {
			/* Matches the glOrtho(0, width, height, 0, -100, 100) call above, which is a
			 * no-op under core profile -- see gpu_shader_2d_box_vert.glsl. */
			const mt::mat4 orthoMat = rasty->GetOrthoMatrix(0.0f, (float)width, (float)height, 0.0f, -100.0f, 100.0f);
			GPU_shader_uniform_vector(m_box2dShader, m_box2dOrthoUniform, 16, 1, (const float *)orthoMat.Data());
		}
		glDrawArraysInstancedARB(GL_TRIANGLE_FAN, 0, 4, numboxes);
	}

	GPU_unbind_vertex_array();
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	GPU_shader_unbind();

	rasty->LoadIdentity();

#ifdef WITH_GL_PROFILE_COMPAT
	glOrtho(0, width, 0, height, -100, 100);
#endif

	/* NOTE: BLF (source/blender/blenfont/) is fixed-function throughout internally
	 * (glMatrixMode/glPushMatrix/glGetFloatv(GL_CURRENT_COLOR)/etc. in blf_draw_gl__start),
	 * so debug text drawn via BLF_draw below does not actually render correctly under
	 * WITH_GL_PROFILE_CORE yet -- that needs its own separate migration, out of scope here.
	 * This block is only guarded to unblock compilation of this file. */
	BLF_size(blf_mono_font, 11, 72);

	//BLF_enable(blf_mono_font, BLF_SHADOW);
	//static float black[4] = {0.0f, 0.0f, 0.0f, 1.0f};
	//BLF_shadow(blf_mono_font, 1, black);
	//BLF_shadow_offset(blf_mono_font, 0, -1);

	for (const RAS_DebugDraw::Text2d& text2d : debugDraw->m_texts2d) {
		const std::string& text = text2d.m_text;
		const float xco = text2d.m_pos[0];
		const float yco = height - text2d.m_pos[1];

#ifdef WITH_GL_PROFILE_COMPAT
		glColor4fv(text2d.m_color);
#endif
		BLF_position(blf_mono_font, xco, yco, 0.0f);
		BLF_draw(blf_mono_font, text.c_str(), text.size());
	}
	BLF_disable(blf_mono_font, BLF_SHADOW);

	rasty->PopMatrix();
	rasty->SetMatrixMode(RAS_Rasterizer::RAS_MODELVIEW);

	rasty->PopMatrix();
}
