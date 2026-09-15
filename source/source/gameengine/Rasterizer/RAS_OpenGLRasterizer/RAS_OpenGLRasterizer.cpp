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
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 *
 * The Original Code is: all of this file.
 *
 * Contributor(s): none yet.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Rasterizer/RAS_OpenGLRasterizer/RAS_OpenGLRasterizer.cpp
 *  \ingroup bgerastogl
 */

#include "RAS_OpenGLRasterizer.h"
#include "RAS_IMaterial.h"

#include "GPU_glew.h"

#include "RAS_MeshUser.h"

#include "GPU_draw.h"
#include "GPU_extensions.h"
#include "GPU_material.h"
#include "GPU_shader.h"
#include "GPU_vertex_array.h"

extern "C" {
#  include "BLF_api.h"
#ifdef __EMSCRIPTEN__
extern void emscripten_glGetVertexAttribiv(GLuint index, GLenum pname, GLint *params);
extern void emscripten_glVertexAttribDivisor(GLuint index, GLuint divisor);
#endif
}

#include "MEM_guardedalloc.h"

#include "CM_Message.h"
#include "termcolor.hpp"

#include <cstring> // For memcpy.

// WARNING: Always respect the order from RAS_Rasterizer::EnableBit.
static const int openGLEnableBitEnums[] = {
	GL_DEPTH_TEST, // RAS_DEPTH_TEST
	GL_ALPHA_TEST, // RAS_ALPHA_TEST
	GL_SCISSOR_TEST, // RAS_SCISSOR_TEST
	GL_TEXTURE_2D, // RAS_TEXTURE_2D
	GL_TEXTURE_CUBE_MAP_ARB, // RAS_TEXTURE_CUBE_MAP
	GL_BLEND, // RAS_BLEND
	GL_COLOR_MATERIAL, // RAS_COLOR_MATERIAL
	GL_CULL_FACE, // RAS_CULL_FACE
	GL_LIGHTING, // RAS_LIGHTING
	GL_MULTISAMPLE_ARB, // RAS_MULTISAMPLE
	GL_POLYGON_STIPPLE, // RAS_POLYGON_STIPPLE
	GL_POLYGON_OFFSET_FILL, // RAS_POLYGON_OFFSET_FILL
	GL_POLYGON_OFFSET_LINE, // RAS_POLYGON_OFFSET_LINE
	GL_TEXTURE_GEN_S, // RAS_TEXTURE_GEN_S
	GL_TEXTURE_GEN_T, // RAS_TEXTURE_GEN_T
	GL_TEXTURE_GEN_R, // RAS_TEXTURE_GEN_R
	GL_TEXTURE_GEN_Q // RAS_TEXTURE_GEN_Q
};

// WARNING: Always respect the order from RAS_Rasterizer::DepthFunc.
static const int openGLDepthFuncEnums[] = {
	GL_NEVER, // RAS_NEVER
	GL_LEQUAL, // RAS_LEQUAL
	GL_LESS, // RAS_LESS
	GL_ALWAYS, // RAS_ALWAYS
	GL_GEQUAL, // RAS_GEQUAL
	GL_GREATER, // RAS_GREATER
	GL_NOTEQUAL, // RAS_NOTEQUAL
	GL_EQUAL // RAS_EQUAL
};

// WARNING: Always respect the order from RAS_Rasterizer::MatrixMode.
static const int openGLMatrixModeEnums[] = {
	GL_PROJECTION, // RAS_PROJECTION
	GL_MODELVIEW, // RAS_MODELVIEW
	GL_TEXTURE // RAS_TEXTURE
};

// WARNING: Always respect the order from RAS_Rasterizer::BlendFunc.
static const int openGLBlendFuncEnums[] = {
	GL_ZERO, // RAS_ZERO,
	GL_ONE, // RAS_ONE,
	GL_SRC_COLOR, // RAS_SRC_COLOR,
	GL_ONE_MINUS_SRC_COLOR, // RAS_ONE_MINUS_SRC_COLOR,
	GL_DST_COLOR, // RAS_DST_COLOR,
	GL_ONE_MINUS_DST_COLOR, // RAS_ONE_MINUS_DST_COLOR,
	GL_SRC_ALPHA, // RAS_SRC_ALPHA,
	GL_ONE_MINUS_SRC_ALPHA, // RAS_ONE_MINUS_SRC_ALPHA,
	GL_DST_ALPHA, // RAS_DST_ALPHA,
	GL_ONE_MINUS_DST_ALPHA, // RAS_ONE_MINUS_DST_ALPHA,
	GL_SRC_ALPHA_SATURATE // RAS_SRC_ALPHA_SATURATE
};

RAS_OpenGLRasterizer::ScreenPlane::ScreenPlane()
{
	// Generate the VBO and IBO for screen overlay plane.
	glGenBuffers(1, &m_vbo);
	glGenBuffers(1, &m_ibo);
	GPU_create_vertex_arrays(1, &m_vao);

	// Vertexes for screen plane, it contains the vertex position (3 floats) and the vertex uv after (2 floats, total size = 5 floats).
	static const float vertices[] = {
		//   3f position   |   2f UV
		-1.0f, -1.0f, 1.0f, 0.0f, 0.0f,
		-1.0f,  1.0f, 1.0f, 0.0f, 1.0f,
		1.0f,  1.0f, 1.0f, 1.0f, 1.0f,
		1.0f, -1.0f, 1.0f, 1.0f, 0.0f
	};
	// Indices for screen plane.
	static const GLubyte indices[] = {3, 2, 1, 0};

	GPU_bind_vertex_array(m_vao);

	// Send indices in the sreen plane IBO.
	glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, m_ibo);
	glBufferData(GL_ELEMENT_ARRAY_BUFFER, sizeof(indices), indices, GL_STATIC_DRAW);

	// Send vertexes in the screen plane VBO.
	glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
	glBufferData(GL_ARRAY_BUFFER, sizeof(vertices), vertices, GL_STATIC_DRAW);

#ifdef WITH_GL_PROFILE_COMPAT
	// Enable vertex/uv pointer.
	glEnableClientState(GL_VERTEX_ARRAY);
	glEnableClientState(GL_TEXTURE_COORD_ARRAY);

	// Bind vertex/uv pointer with VBO offset. (position = 0, uv = 3 * float, stride = 5 * float).
	glVertexPointer(3, GL_FLOAT, sizeof(float) * 5, 0);
	glTexCoordPointer(2, GL_FLOAT, sizeof(float) * 5, ((char *)nullptr) + sizeof(float) * 3);
#endif

	// Also expose the same data via generic vertex attributes (locations 0/1), additive to
	// the fixed-function client-state above (not a replacement): core-profile-safe shaders
	// migrated to layout(location=N) in/out syntax read these, while shaders not yet migrated
	// (e.g. gpu_shader_frame_buffer_vert.glsl, used every frame for the final framebuffer
	// blit) keep working unchanged off gl_Vertex/gl_MultiTexCoord0 via the calls above.
	glEnableVertexAttribArray(0);
	glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(float) * 5, 0);
	glEnableVertexAttribArray(1);
	glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, sizeof(float) * 5, ((char *)nullptr) + sizeof(float) * 3);

	// Unbind the VAO before the VBO: under Emscripten's legacy GL emulation, an
	// ARRAY_BUFFER unbind performed while a VAO is still bound is recorded as that
	// VAO's own vertex-buffer reference, erasing the pointer/offset state above.
	GPU_unbind_vertex_array();
	glBindBuffer(GL_ARRAY_BUFFER, 0);
}

RAS_OpenGLRasterizer::ScreenPlane::~ScreenPlane()
{
	// Delete screen overlay plane VBO/IBO/VAO
	GPU_delete_vertex_arrays(1, &m_vao);
	glDeleteBuffers(1, &m_vbo);
	glDeleteBuffers(1, &m_ibo);
}

inline void RAS_OpenGLRasterizer::ScreenPlane::Render()
{
	GPU_bind_vertex_array(m_vao);
#ifdef __EMSCRIPTEN__
	/* Legacy GL emulation replays vertex pointers on VAO bind, but does not
	 * isolate attribute divisors. Instanced debug geometry can leave UVs at
	 * divisor 1, making every screen vertex sample the texture's first corner. */
	GLint divisors[2];
	for (GLuint i = 0; i < 2; ++i) {
		emscripten_glGetVertexAttribiv(i, GL_VERTEX_ATTRIB_ARRAY_DIVISOR, &divisors[i]);
		emscripten_glVertexAttribDivisor(i, 0);
	}
#endif
	// Draw in triangle fan mode to reduce IBO size.
	glDrawElements(GL_TRIANGLE_FAN, 4, GL_UNSIGNED_BYTE, 0);

#ifdef __EMSCRIPTEN__
	for (GLuint i = 0; i < 2; ++i) {
		emscripten_glVertexAttribDivisor(i, divisors[i]);
	}
#endif
	GPU_unbind_vertex_array();
}

RAS_OpenGLRasterizer::RAS_OpenGLRasterizer(RAS_Rasterizer *rasterizer)
	:m_rasterizer(rasterizer)
{
}

RAS_OpenGLRasterizer::~RAS_OpenGLRasterizer()
{
}

unsigned short RAS_OpenGLRasterizer::GetNumLights() const
{
#ifdef __EMSCRIPTEN__
	/* GL_MAX_LIGHTS is a fixed-function lighting enum removed from
	 * GLES3/WebGL2's getParameter; the legacy emulation path supports 8. */
	return 8;
#else
	int numlights = 0;
	glGetIntegerv(GL_MAX_LIGHTS, (GLint *)&numlights);

	if (numlights > 8) {
		return 8;
	}
	return numlights;
#endif
}

void RAS_OpenGLRasterizer::Enable(RAS_Rasterizer::EnableBit bit)
{
	glEnable(openGLEnableBitEnums[bit]);
}

void RAS_OpenGLRasterizer::Disable(RAS_Rasterizer::EnableBit bit)
{
	glDisable(openGLEnableBitEnums[bit]);
}

void RAS_OpenGLRasterizer::EnableLight(unsigned short count)
{
	glDisable((GLenum)(GL_LIGHT0 + count));
}

void RAS_OpenGLRasterizer::DisableLight(unsigned short count)
{
	glDisable((GLenum)(GL_LIGHT0 + count));
}

void RAS_OpenGLRasterizer::SetDepthFunc(RAS_Rasterizer::DepthFunc func)
{
	glDepthFunc(openGLDepthFuncEnums[func]);
}

void RAS_OpenGLRasterizer::SetBlendFunc(RAS_Rasterizer::BlendFunc src, RAS_Rasterizer::BlendFunc dst)
{
	glBlendFunc(openGLBlendFuncEnums[src], openGLBlendFuncEnums[dst]);
}

void RAS_OpenGLRasterizer::Init()
{
#ifdef WITH_GL_PROFILE_COMPAT
	glShadeModel(GL_SMOOTH);
#endif
}

void RAS_OpenGLRasterizer::SetAmbient(const mt::vec3& amb, float factor)
{
#ifdef WITH_GL_PROFILE_COMPAT
	float ambient[] = {amb.x * factor, amb.y * factor, amb.z * factor, 1.0f};
	glLightModelfv(GL_LIGHT_MODEL_AMBIENT, ambient);
#endif
}

void RAS_OpenGLRasterizer::SetFog(short type, float start, float dist, float intensity, const mt::vec3& color)
{
#ifdef WITH_GL_PROFILE_COMPAT
	float params[4] = {color[0], color[1], color[2], 1.0f};
	glFogi(GL_FOG_MODE, GL_LINEAR);
	glFogf(GL_FOG_DENSITY, intensity / 10.0f);
	glFogf(GL_FOG_START, start);
	glFogf(GL_FOG_END, start + dist);
	glFogfv(GL_FOG_COLOR, params);
#endif
}

void RAS_OpenGLRasterizer::Exit()
{
#ifdef WITH_GL_PROFILE_COMPAT
	if (GLEW_EXT_separate_specular_color || GLEW_VERSION_1_2) {
		glLightModeli(GL_LIGHT_MODEL_COLOR_CONTROL, GL_SINGLE_COLOR);
	}
#endif
}

void RAS_OpenGLRasterizer::BeginFrame()
{
#ifdef WITH_GL_PROFILE_COMPAT
	glShadeModel(GL_SMOOTH);
#endif
}

void RAS_OpenGLRasterizer::SetDepthMask(RAS_Rasterizer::DepthMask depthmask)
{
	glDepthMask(depthmask == RAS_Rasterizer::RAS_DEPTHMASK_DISABLED ? GL_FALSE : GL_TRUE);
}

unsigned int *RAS_OpenGLRasterizer::MakeScreenshot(int x, int y, int width, int height)
{
	unsigned int *pixeldata = nullptr;

	if (width && height) {
		pixeldata = (unsigned int *)malloc(sizeof(unsigned int) * width * height);
		glReadPixels(x, y, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixeldata);
	}

	return pixeldata;
}

void RAS_OpenGLRasterizer::Clear(int clearbit)
{
	GLbitfield glclearbit = 0;

	if (clearbit & RAS_Rasterizer::RAS_COLOR_BUFFER_BIT) {
		glclearbit |= GL_COLOR_BUFFER_BIT;
	}
	if (clearbit & RAS_Rasterizer::RAS_DEPTH_BUFFER_BIT) {
		glclearbit |= GL_DEPTH_BUFFER_BIT;
	}
	if (clearbit & RAS_Rasterizer::RAS_STENCIL_BUFFER_BIT) {
		glclearbit |= GL_STENCIL_BUFFER_BIT;
	}

	glClear(glclearbit);
}

void RAS_OpenGLRasterizer::SetClearColor(float r, float g, float b, float a)
{
	glClearColor(r, g, b, a);
}

void RAS_OpenGLRasterizer::SetClearDepth(float d)
{
	glClearDepth(d);
}

void RAS_OpenGLRasterizer::SetColorMask(bool r, bool g, bool b, bool a)
{
	glColorMask(r ? GL_TRUE : GL_FALSE, g ? GL_TRUE : GL_FALSE, b ? GL_TRUE : GL_FALSE, a ? GL_TRUE : GL_FALSE);
}

void RAS_OpenGLRasterizer::DrawOverlayPlane()
{
	m_screenPlane.Render();
}

void RAS_OpenGLRasterizer::SetViewport(int x, int y, int width, int height)
{
	glViewport(x, y, width, height);
}

void RAS_OpenGLRasterizer::GetViewport(int *rect)
{
	glGetIntegerv(GL_VIEWPORT, rect);
}

void RAS_OpenGLRasterizer::SetScissor(int x, int y, int width, int height)
{
	glScissor(x, y, width, height);
}

void RAS_OpenGLRasterizer::SetLines(bool enable)
{
#ifdef __EMSCRIPTEN__
	/* glPolygonMode is desktop-fixed-function-pipeline only; WebGL/GLES2 have
	 * no wireframe fill mode and no equivalent entry point. Skip it here
	 * instead of calling a null function pointer. */
	(void)enable;
	return;
#endif
	if (enable) {
		glPolygonMode(GL_FRONT_AND_BACK, GL_LINE);
	}
	else {
		glPolygonMode(GL_FRONT_AND_BACK, GL_FILL);
	}
}

void RAS_OpenGLRasterizer::SetLinesWidth(float size)
{
	glLineWidth(size);
}

void RAS_OpenGLRasterizer::SetSpecularity(float specX,
                                          float specY,
                                          float specZ,
                                          float specval)
{
#ifdef WITH_GL_PROFILE_COMPAT
	GLfloat mat_specular[] = {specX, specY, specZ, specval};
	glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, mat_specular);
#endif
}

void RAS_OpenGLRasterizer::SetShinyness(float shiny)
{
#ifdef WITH_GL_PROFILE_COMPAT
	GLfloat mat_shininess[] = { shiny };
	glMaterialfv(GL_FRONT_AND_BACK, GL_SHININESS, mat_shininess);
#endif
}

void RAS_OpenGLRasterizer::SetDiffuse(float difX, float difY, float difZ, float diffuse)
{
#ifdef WITH_GL_PROFILE_COMPAT
	GLfloat mat_diffuse[] = {difX, difY, difZ, diffuse};
	glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, mat_diffuse);
#endif
}

void RAS_OpenGLRasterizer::SetEmissive(float eX, float eY, float eZ, float e)
{
#ifdef WITH_GL_PROFILE_COMPAT
	GLfloat mat_emit[] = {eX, eY, eZ, e};
	glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, mat_emit);
#endif
}

void RAS_OpenGLRasterizer::SetPolygonOffset(float mult, float add)
{
	glPolygonOffset(mult, add);
}

/* NOTE: legacy glClipPlane/GL_CLIP_PLANE0 has no core-profile equivalent as a fixed
 * pipeline stage -- core profile uses gl_ClipDistance[] written by the vertex shader
 * instead (see gl-deprecated.h's GL_CLIP_PLANE0 -> USE_GL_CLIP_DISTANCE0 poison). That
 * requires vertex shader changes not yet made (Phase 3 of the core profile plan), so
 * clip planes are a no-op under CORE for now -- known gap, not a silent regression. */
void RAS_OpenGLRasterizer::EnableClipPlane(unsigned short index, const mt::vec4& plane)
{
#ifdef WITH_GL_PROFILE_COMPAT
	double planev[4] = {plane.x, plane.y, plane.z, plane.w};
	glClipPlane(GL_CLIP_PLANE0 + index, planev);
	glEnable(GL_CLIP_PLANE0 + index);
#endif
}

void RAS_OpenGLRasterizer::DisableClipPlane(unsigned short index)
{
#ifdef WITH_GL_PROFILE_COMPAT
	glDisable(GL_CLIP_PLANE0 + index);
#endif
}

void RAS_OpenGLRasterizer::SetFrontFace(bool ccw)
{
	if (ccw) {
		glFrontFace(GL_CCW);
	}
	else {
		glFrontFace(GL_CW);
	}
}

void RAS_OpenGLRasterizer::EnableLights()
{
#ifdef WITH_GL_PROFILE_COMPAT
	glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE);
	glLightModeli(GL_LIGHT_MODEL_TWO_SIDE, GL_TRUE);
	glLightModeli(GL_LIGHT_MODEL_LOCAL_VIEWER, (m_rasterizer->GetCameraOrtho()) ? GL_FALSE : GL_TRUE);
#endif
}

void RAS_OpenGLRasterizer::DisableForText()
{
	for (int i = 0; i < RAS_Texture::MaxUnits; i++) {
		glActiveTextureARB(GL_TEXTURE0_ARB + i);

		if (GLEW_ARB_texture_cube_map) {
			Disable(RAS_Rasterizer::RAS_TEXTURE_CUBE_MAP);
		}
		Disable(RAS_Rasterizer::RAS_TEXTURE_2D);
	}

	glActiveTextureARB(GL_TEXTURE0_ARB);
}

void RAS_OpenGLRasterizer::RenderText3D(int fontid, const std::string& text, int size, int dpi,
                                        const float color[4], const float mat[16], float aspect, bool useShadow, const float shadowOffset[2], const float shadow_color[4])
{
	/* enable/disable flags */
	int flags = BLF_MATRIX | BLF_ASPECT;

	/* use shadows */
	if (useShadow) {
		flags |= BLF_SHADOW;
		BLF_shadow(fontid, 1, shadow_color);
		BLF_shadow_offset(fontid, shadowOffset[0], shadowOffset[1]);
	}

	/* gl prepping */
	m_rasterizer->DisableForText();
	SetFrontFace(true);

	/* the actual drawing */
	/* NOTE: same BLF core-profile gap as RAS_OpenGLDebugDraw.cpp -- BLF itself is
	 * fixed-function internally, so this text won't render correctly under CORE yet. */
#ifdef WITH_GL_PROFILE_COMPAT
	glColor4fv(color);
#endif

	/* multiply the text matrix by the object matrix */
	BLF_enable(fontid, flags);
	BLF_matrix(fontid, mat);
	
	/* aspect is the inverse scale that allows you to increase
	 * your resolution without sizing the final text size
	 * the bigger the size, the smaller the aspect */
	BLF_aspect(fontid, aspect, aspect, aspect);

	BLF_size(fontid, size, dpi);
	BLF_position(fontid, 0, 0, 0);
	BLF_draw(fontid, text.c_str(), text.size());

	BLF_disable(fontid, flags);

	m_rasterizer->SetAlphaBlend(GPU_BLEND_SOLID);
}

/* NOTE: the legacy fixed-function matrix stack (PushMatrix/PopMatrix/SetMatrixMode/
 * MultMatrix/LoadMatrix/LoadIdentity below) has no meaning in core profile -- there is no
 * gl_ModelViewMatrix/gl_ProjectionMatrix for a shader to read back. The per-object/view/
 * projection matrices RAS_Rasterizer tracks on the CPU side (m_viewmatrix, m_projmatrix,
 * etc., added in Phase 0/1 of the core profile migration) are threaded directly into
 * GPU_material_bind()/GPU_material_bind_uniforms() as real uniforms instead, independent
 * of this stack. So under CORE these become safe no-ops -- push/pop stay balanced (both
 * no-op), and nothing else consumes the GL-side matrix stack state. */
void RAS_OpenGLRasterizer::PushMatrix()
{
#ifdef WITH_GL_PROFILE_COMPAT
	glPushMatrix();
#endif
}

void RAS_OpenGLRasterizer::PopMatrix()
{
#ifdef WITH_GL_PROFILE_COMPAT
	glPopMatrix();
#endif
}

void RAS_OpenGLRasterizer::SetMatrixMode(RAS_Rasterizer::MatrixMode mode)
{
#ifdef WITH_GL_PROFILE_COMPAT
	glMatrixMode(openGLMatrixModeEnums[mode]);
#endif
}

void RAS_OpenGLRasterizer::MultMatrix(const float mat[16])
{
#ifdef WITH_GL_PROFILE_COMPAT
	glMultMatrixf(mat);
#endif
}

void RAS_OpenGLRasterizer::LoadMatrix(const float mat[16])
{
#ifdef WITH_GL_PROFILE_COMPAT
	glLoadMatrixf(mat);
#endif
}

void RAS_OpenGLRasterizer::LoadIdentity()
{
#ifdef WITH_GL_PROFILE_COMPAT
	glLoadIdentity();
#endif
}

/* NOTE: the accumulation buffer (GL_ACCUM etc.) was removed entirely from core profile,
 * not just deprecated -- there is no direct replacement. A working core-profile motion
 * blur would need a velocity-buffer post-process pass instead (same family as the
 * existing SSAO/SSR screen-space filters), which is out of scope here. No-op under
 * CORE for now -- known gap, motion blur simply won't apply visually. */
void RAS_OpenGLRasterizer::MotionBlur(unsigned short state, float value)
{
#ifdef WITH_GL_PROFILE_COMPAT
	if (state) {
		if (state == 1) {
			// bugfix:load color buffer into accum buffer for the first time(state=1)
			glAccum(GL_LOAD, 1.0f);
			m_rasterizer->SetMotionBlur(2);
		}
		else if (value >= 0.0f && value <= 1.0f) {
			glAccum(GL_MULT, value);
			glAccum(GL_ACCUM, 1.0f - value);
			glAccum(GL_RETURN, 1.0f);
			glFlush();
		}
	}
#endif
}

const unsigned char *RAS_OpenGLRasterizer::GetGraphicsCardVendor()
{
  return (unsigned char *)glGetString(GL_VENDOR);
}

const unsigned char *RAS_OpenGLRasterizer::GetGraphicsCardRenderer()
{
  return (unsigned char *)glGetString(GL_RENDERER);
}

void RAS_OpenGLRasterizer::PrintHardwareInfo(bool fullInfo)
{
	CM_Message("Range Engine - Hardware Info");
	CM_Message(termcolor::yellow << "Using Device: " << glGetString(GL_VENDOR) << " - " << glGetString(GL_RENDERER));
	CM_Message(termcolor::green << "OpenGL Supported: " << glGetString(GL_VERSION) 
			<< termcolor::white << " - " << "Shading language: " << glGetString(GL_SHADING_LANGUAGE_VERSION));
	// Note: this used to print "GLEW_VERSION_MAJOR"/"GLEW_VERSION", which are the GLEW
	// *library's* own version macros, not the OpenGL context version (already printed
	// correctly above via glGetString(GL_VERSION)). Report the compiled GL profile instead,
	// since that information wasn't shown anywhere else.
#if defined(WITH_GL_PROFILE_CORE)
	CM_Message(termcolor::cyan << "Compiled GL Profile: Core");
#elif defined(WITH_GL_PROFILE_ES20)
	CM_Message(termcolor::cyan << "Compiled GL Profile: ES2");
#elif defined(WITH_GL_PROFILE_COMPAT)
	CM_Message(termcolor::cyan << "Compiled GL Profile: Compatibility");
#endif

	if (!fullInfo) {
		CM_Message(termcolor::white << "Range Engine - Hardware Info End");
		return;
	}

	bool support = 0;
	CM_Message(termcolor::white << "Supported Extensions...");
	CM_Message("- GL_ARB_shader_objects supported?       " << (GLEW_ARB_shader_objects ? "yes." : "no."));
	CM_Message("- GL_ARB_geometry_shader4 supported?     " << (GLEW_ARB_geometry_shader4 ? "yes." : "no."));
	
	support = GLEW_ARB_vertex_shader;
	CM_Message("- GL_ARB_vertex_shader supported?        " << (support ? "yes." : "no."));
	if (support) {
		CM_Message(" ----------Details----------");
		int max = 0;
		glGetIntegerv(GL_MAX_VERTEX_UNIFORM_COMPONENTS_ARB, (GLint *)&max);
		CM_Message("-  Max uniform components: " << max);

		glGetIntegerv(GL_MAX_VARYING_FLOATS_ARB, (GLint *)&max);
		CM_Message("-  Max varying floats: " << max);

		glGetIntegerv(GL_MAX_VERTEX_TEXTURE_IMAGE_UNITS_ARB, (GLint *)&max);
		CM_Message("-  Max vertex texture units: " << max);

		glGetIntegerv(GL_MAX_VERTEX_ATTRIBS_ARB, (GLint *)&max);
		CM_Message("-  Max vertex attribs: " << max);

		glGetIntegerv(GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS_ARB, (GLint *)&max);
		CM_Message("-  Max combined texture units: " << max);
		CM_Message("");
	}

	support = GLEW_ARB_fragment_shader;
	CM_Message("- GL_ARB_fragment_shader supported?      " << (support ? "yes." : "no."));
	if (support) {
		CM_Message(" ----------Details----------");
		int max = 0;
		glGetIntegerv(GL_MAX_FRAGMENT_UNIFORM_COMPONENTS_ARB, (GLint *)&max);
		CM_Message("-  Max uniform components." << max);
		CM_Message("");
	}

	support = GLEW_ARB_texture_cube_map;
	CM_Message("- GL_ARB_texture_cube_map supported?     " << (support ? "yes." : "no."));
	if (support) {
		CM_Message(" ----------Details----------");
		int size = 0;
		glGetIntegerv(GL_MAX_CUBE_MAP_TEXTURE_SIZE_ARB, (GLint *)&size);
		CM_Message("-  Max cubemap size." << size);
		CM_Message("");
	}

	support = GLEW_ARB_multitexture;
	CM_Message("- GL_ARB_multitexture supported?         " << (support ? "yes." : "no."));
	if (support) {
		CM_Message(" ----------Details----------");
		int units = 0;
		glGetIntegerv(GL_MAX_TEXTURE_UNITS_ARB, (GLint *)&units);
		CM_Message("-  Max texture units available.  " << units);
		CM_Message("");
	}

	CM_Message("- GL_ARB_texture_env_combine supported?       " << (GLEW_ARB_texture_env_combine ? "yes." : "no."));

	CM_Message("- GL_ARB_texture_non_power_of_two supported?  " << (GPU_full_non_power_of_two_support() ? "yes." : "no."));

	CM_Message("- GL_ARB_draw_instanced supported?            " << (GLEW_ARB_draw_instanced ? "yes." : "no."));

	CM_Message(termcolor::white << "Range Engine - Hardware Info End");
}
