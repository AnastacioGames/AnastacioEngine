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

/** \file RAS_WebGLCompat.cpp
 *  \ingroup bgerast
 */

#include "RAS_WebGLCompat.h"

#include <cstdint>

#ifdef __EMSCRIPTEN__
#include <emscripten.h>

/* Same bypass as gpu_shader_source in gpu_shader.c: hand the source straight to WebGL2. */
EM_JS(void, ras_shader_source_webgl, (GLuint shader, const char *source), {
	WebGL2RenderingContext.prototype.shaderSource.call(GLctx, GL.shaders[shader], UTF8ToString(source));
});

/* Native WebGL2 vertex arrays for the effects. The legacy emulation fakes VAOs with a single
 * array buffer and replays them on the default VAO, and its draw calls fall into immediate mode
 * when its tracked state disagrees; these effects bypass all of it. Unbinding (VAO 0, buffer 0)
 * puts back the bindings the emulation believes are current. */
EM_JS(void, ras_webgl_restore_emulated_bindings, (), {
	GLctx.bindBuffer(GLctx.ARRAY_BUFFER, GL.buffers[GLctx.currentArrayBufferBinding] || null);
	GLctx.bindBuffer(GLctx.ELEMENT_ARRAY_BUFFER, GL.buffers[GLctx.currentElementArrayBufferBinding] || null);
});

EM_JS(void, ras_webgl_gen_vertex_arrays, (GLsizei n, GLuint *arrays), {
	if (!Module.rasVaos) Module.rasVaos = [null];
	for (var i = 0; i < n; ++i) {
		Module.rasVaos.push(GLctx.createVertexArray());
		HEAPU32[(arrays >> 2) + i] = Module.rasVaos.length - 1;
	}
});

EM_JS(void, ras_webgl_delete_vertex_arrays, (GLsizei n, const GLuint *arrays), {
	for (var i = 0; i < n; ++i) {
		var id = HEAPU32[(arrays >> 2) + i];
		if (Module.rasVaos && Module.rasVaos[id]) {
			GLctx.deleteVertexArray(Module.rasVaos[id]);
			Module.rasVaos[id] = null;
		}
	}
});

EM_JS(void, ras_webgl_bind_vertex_array_native, (GLuint array), {
	GLctx.bindVertexArray(array && Module.rasVaos ? Module.rasVaos[array] : null);
});

EM_JS(void, ras_webgl_bind_buffer_native, (GLenum target, GLuint buffer), {
	GLctx.bindBuffer(target, buffer ? GL.buffers[buffer] : null);
});

EM_JS(int, ras_webgl_vertex_array_bound, (), {
	return GLctx.getParameter(GLctx.VERTEX_ARRAY_BINDING) ? 1 : 0;
});

EM_JS(void, ras_webgl_enable_vertex_attrib_array, (GLuint index), {
	GLctx.enableVertexAttribArray(index);
});

EM_JS(void, ras_webgl_disable_vertex_attrib_array, (GLuint index), {
	GLctx.disableVertexAttribArray(index);
});

EM_JS(void, ras_webgl_vertex_attrib_pointer,
      (GLuint index, GLint size, GLenum type, GLboolean normalized, GLsizei stride, const void *pointer), {
	GLctx.vertexAttribPointer(index, size, type, !!normalized, stride, pointer);
});

/* The scene framebuffer can have several draw buffers (MRT) while these shaders only write
 * location 0; WebGL rejects that draw, desktop GL ignores the missing outputs. Narrow the draw
 * buffers to attachment 0 around the draw and restore them. */
EM_JS(void, ras_webgl_narrow_draw_buffers, (), {
	var g = GLctx;
	Module.rasSavedDrawBuffers = null;
	if (!g.getParameter(g.DRAW_FRAMEBUFFER_BINDING)) return;
	if (!Module.rasMaxDrawBuffers) Module.rasMaxDrawBuffers = g.getParameter(g.MAX_DRAW_BUFFERS);
	var bufs = [];
	var multiple = false;
	for (var i = 0; i < Module.rasMaxDrawBuffers; ++i) {
		bufs.push(g.getParameter(g.DRAW_BUFFER0 + i));
		if (i > 0 && bufs[i] != g.NONE) multiple = true;
	}
	if (multiple) {
		Module.rasSavedDrawBuffers = bufs;
		g.drawBuffers(bufs.map(function(b, i) { return i == 0 ? b : g.NONE; }));
	}
});

EM_JS(void, ras_webgl_restore_draw_buffers, (), {
	if (Module.rasSavedDrawBuffers) GLctx.drawBuffers(Module.rasSavedDrawBuffers);
	Module.rasSavedDrawBuffers = null;
});

EM_JS(void, ras_webgl_draw_native, (int kind, GLenum mode, GLint first, GLsizei count, GLenum type, GLsizei instances), {
	var g = GLctx;
	if (kind == 0) g.drawArrays(mode, first, count);
	else if (kind == 1) g.drawElements(mode, count, type, first);
	else g.drawArraysInstanced(mode, first, count, instances);
});

static void ras_webgl_draw(int kind, GLenum mode, GLint first, GLsizei count, GLenum type, GLsizei instances)
{
	ras_webgl_narrow_draw_buffers();
	ras_webgl_draw_native(kind, mode, first, count, type, instances);
	ras_webgl_restore_draw_buffers();
}

EM_JS(int, ras_float_render_target_webgl, (), {
	return GLctx.getExtension('EXT_color_buffer_float') ? 1 : 0;
});

namespace {

void ReplaceAll(std::string &str, const std::string &from, const std::string &to)
{
	for (size_t pos = str.find(from); pos != std::string::npos; pos = str.find(from, pos + to.size())) {
		str.replace(pos, from.size(), to);
	}
}

void EraseLine(std::string &str, const std::string &start)
{
	const size_t pos = str.find(start);
	if (pos != std::string::npos) {
		const size_t end = str.find('\n', pos);
		str.erase(pos, (end == std::string::npos) ? std::string::npos : end + 1 - pos);
	}
}

} // namespace
#endif

std::string RAS_PortableGLSL(const char *source)
{
	std::string str(source);
#ifdef __EMSCRIPTEN__
	EraseLine(str, "#version");
	// Instancing is core in GLSL ES 3.00: keep the instanced branch, under its core name.
	EraseLine(str, "#extension GL_ARB_draw_instanced");
	ReplaceAll(str, "#ifdef GL_ARB_draw_instanced", "#if 1");
	ReplaceAll(str, "gl_InstanceIDARB", "gl_InstanceID");
	// texture2D is gone in GLSL ES 3.00; the define also covers user particle scripts.
	str = "#version 300 es\n"
	      "precision highp float;\n"
	      "precision highp int;\n"
	      "precision highp sampler2D;\n"
	      "#define texture2D texture\n" + str;
#endif
	return str;
}

void RAS_ShaderSource(GLuint shader, const char *source)
{
	const std::string str = RAS_PortableGLSL(source);
#ifdef __EMSCRIPTEN__
	ras_shader_source_webgl(shader, str.c_str());
#else
	const char *src = str.c_str();
	glShaderSource(shader, 1, &src, nullptr);
#endif
}

void RAS_BindFragDataLocation(GLuint program, GLuint color, const char *name)
{
#ifdef __EMSCRIPTEN__
	(void)program;
	(void)color;
	(void)name;
#else
	glBindFragDataLocation(program, color, name);
#endif
}

#ifdef __EMSCRIPTEN__
void RAS_WebGLGenVertexArrays(GLsizei n, GLuint *arrays)
{
	ras_webgl_gen_vertex_arrays(n, arrays);
}

void RAS_WebGLDeleteVertexArrays(GLsizei n, const GLuint *arrays)
{
	ras_webgl_delete_vertex_arrays(n, arrays);
}

void RAS_WebGLBindVertexArray(GLuint array)
{
	ras_webgl_bind_vertex_array_native(array);
	if (!array) {
		ras_webgl_restore_emulated_bindings();
	}
}

void RAS_WebGLBindBuffer(GLenum target, GLuint buffer)
{
	// Buffer 0 outside an effect VAO means "done": give the emulation its bindings back.
	if (!buffer && (target == GL_ARRAY_BUFFER || (target == GL_ELEMENT_ARRAY_BUFFER && !ras_webgl_vertex_array_bound()))) {
		ras_webgl_restore_emulated_bindings();
		return;
	}
	ras_webgl_bind_buffer_native(target, buffer);
}

void RAS_WebGLEnableVertexAttribArray(GLuint index)
{
	ras_webgl_enable_vertex_attrib_array(index);
}

void RAS_WebGLDisableVertexAttribArray(GLuint index)
{
	ras_webgl_disable_vertex_attrib_array(index);
}

void RAS_WebGLVertexAttribPointer(GLuint index, GLint size, GLenum type, GLboolean normalized, GLsizei stride,
                                  const void *pointer)
{
	ras_webgl_vertex_attrib_pointer(index, size, type, normalized, stride, pointer);
}

void RAS_WebGLDrawArrays(GLenum mode, GLint first, GLsizei count)
{
	ras_webgl_draw(0, mode, first, count, 0, 0);
}

void RAS_WebGLDrawElements(GLenum mode, GLsizei count, GLenum type, const void *indices)
{
	ras_webgl_draw(1, mode, (GLint)(intptr_t)indices, count, type, 0);
}

void RAS_WebGLDrawArraysInstanced(GLenum mode, GLint first, GLsizei count, GLsizei instancecount)
{
	ras_webgl_draw(2, mode, first, count, 0, instancecount);
}
#endif

void RAS_NarrowDrawBuffersBegin()
{
#ifdef __EMSCRIPTEN__
	ras_webgl_narrow_draw_buffers();
#endif
}

void RAS_NarrowDrawBuffersEnd()
{
#ifdef __EMSCRIPTEN__
	ras_webgl_restore_draw_buffers();
#endif
}

bool RAS_FloatRenderTargetSupported()
{
#ifdef __EMSCRIPTEN__
	static const bool supported = ras_float_render_target_webgl() != 0;
	return supported;
#else
	return true;
#endif
}
