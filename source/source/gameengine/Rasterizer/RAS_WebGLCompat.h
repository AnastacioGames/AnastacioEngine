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

/** \file RAS_WebGLCompat.h
 *  \ingroup bgerast
 *
 * Helpers for the effects that compile their own GLSL (particles, rain) instead of going
 * through GPU_shader: on the Web build they are written as desktop "#version 130" and must
 * become GLSL ES 3.00, and a few GL entry points are null there (GLEW ARB pointers,
 * glBindFragDataLocation). On desktop every helper is the plain GL call.
 */

#ifndef __RAS_WEBGLCOMPAT_H__
#define __RAS_WEBGLCOMPAT_H__

#include "GPU_glew.h"

#include <string>

/// Rewrites a desktop "#version 130" source for GLSL ES 3.00 on the Web; unchanged on desktop.
std::string RAS_PortableGLSL(const char *source);

/// glShaderSource with RAS_PortableGLSL applied. On the Web it bypasses the legacy GL
/// emulation wrapper, which prepends declarations ahead of the mandatory #version line.
void RAS_ShaderSource(GLuint shader, const char *source);

/// glBindFragDataLocation; a no-op on the Web (GLSL ES 3.00 puts a single output at 0).
void RAS_BindFragDataLocation(GLuint program, GLuint color, const char *name);

/// True when float color targets (GL_R32F/GL_RG32F...) can be rendered to. Always true on desktop.
bool RAS_FloatRenderTargetSupported();

/// Around a draw whose shader writes only output 0 into a framebuffer with several draw buffers:
/// WebGL rejects it, so on the Web only attachment 0 stays active until End. No-ops on desktop.
void RAS_NarrowDrawBuffersBegin();
void RAS_NarrowDrawBuffersEnd();

#ifdef RAS_WEBGL_COMPAT_NO_REMAP
/* Only the helpers above: the including file keeps the GL calls it already uses. */
#elif defined(__EMSCRIPTEN__)
#  define RAS_WEBGL_COMPAT_REMAP
#endif

#ifdef RAS_WEBGL_COMPAT_REMAP
/* GLEW reads the WebGL2 version string as GLES and never loads its GL 3.0/ARB entry points, so
 * these stay null ("null function"). Call the Emscripten symbols they would resolve to instead. */
extern "C" {
void emscripten_glVertexAttribDivisor(GLuint index, GLuint divisor);
void emscripten_glDrawArraysInstanced(GLenum mode, GLint first, GLsizei count, GLsizei instancecount);
void emscripten_glTransformFeedbackVaryings(GLuint program, GLsizei count, const GLchar *const *varyings, GLenum bufferMode);
void emscripten_glBeginTransformFeedback(GLenum primitiveMode);
void emscripten_glEndTransformFeedback(void);
void emscripten_glBindBufferBase(GLenum target, GLuint index, GLuint buffer);
void emscripten_glGenFramebuffers(GLsizei n, GLuint *framebuffers);
void emscripten_glBindFramebuffer(GLenum target, GLuint framebuffer);
void emscripten_glDeleteFramebuffers(GLsizei n, const GLuint *framebuffers);
void emscripten_glFramebufferTexture2D(GLenum target, GLenum attachment, GLenum textarget, GLuint texture, GLint level);
void emscripten_glFramebufferRenderbuffer(GLenum target, GLenum attachment, GLenum renderbuffertarget, GLuint renderbuffer);
GLenum emscripten_glCheckFramebufferStatus(GLenum target);
void emscripten_glGenRenderbuffers(GLsizei n, GLuint *renderbuffers);
void emscripten_glBindRenderbuffer(GLenum target, GLuint renderbuffer);
void emscripten_glDeleteRenderbuffers(GLsizei n, const GLuint *renderbuffers);
void emscripten_glRenderbufferStorage(GLenum target, GLenum internalformat, GLsizei width, GLsizei height);
}
#  undef glTransformFeedbackVaryings
#  undef glBeginTransformFeedback
#  undef glEndTransformFeedback
#  undef glBindBufferBase
#  undef glGenFramebuffers
#  undef glBindFramebuffer
#  undef glDeleteFramebuffers
#  undef glFramebufferTexture2D
#  undef glFramebufferRenderbuffer
#  undef glCheckFramebufferStatus
#  undef glGenRenderbuffers
#  undef glBindRenderbuffer
#  undef glDeleteRenderbuffers
#  undef glRenderbufferStorage
#  define glTransformFeedbackVaryings emscripten_glTransformFeedbackVaryings
#  define glBeginTransformFeedback emscripten_glBeginTransformFeedback
#  define glEndTransformFeedback emscripten_glEndTransformFeedback
#  define glBindBufferBase emscripten_glBindBufferBase
#  define glGenFramebuffers emscripten_glGenFramebuffers
#  define glBindFramebuffer emscripten_glBindFramebuffer
#  define glDeleteFramebuffers emscripten_glDeleteFramebuffers
#  define glFramebufferTexture2D emscripten_glFramebufferTexture2D
#  define glFramebufferRenderbuffer emscripten_glFramebufferRenderbuffer
#  define glCheckFramebufferStatus emscripten_glCheckFramebufferStatus
#  define glGenRenderbuffers emscripten_glGenRenderbuffers
#  define glBindRenderbuffer emscripten_glBindRenderbuffer
#  define glDeleteRenderbuffers emscripten_glDeleteRenderbuffers
#  define glRenderbufferStorage emscripten_glRenderbufferStorage

void RAS_WebGLGenVertexArrays(GLsizei n, GLuint *arrays);
void RAS_WebGLDeleteVertexArrays(GLsizei n, const GLuint *arrays);
void RAS_WebGLBindVertexArray(GLuint array);
void RAS_WebGLBindBuffer(GLenum target, GLuint buffer);
void RAS_WebGLEnableVertexAttribArray(GLuint index);
void RAS_WebGLDisableVertexAttribArray(GLuint index);
void RAS_WebGLVertexAttribPointer(GLuint index, GLint size, GLenum type, GLboolean normalized, GLsizei stride,
                                  const void *pointer);
void RAS_WebGLDrawArrays(GLenum mode, GLint first, GLsizei count);
void RAS_WebGLDrawElements(GLenum mode, GLsizei count, GLenum type, const void *indices);
void RAS_WebGLDrawArraysInstanced(GLenum mode, GLint first, GLsizei count, GLsizei instancecount);

/* Vertex arrays, buffer bindings, attributes and draws go straight to WebGL2 (see the .cpp). */
#  undef glGenVertexArrays
#  undef glDeleteVertexArrays
#  undef glBindVertexArray
#  undef glBindBuffer
#  undef glEnableVertexAttribArray
#  undef glDisableVertexAttribArray
#  undef glVertexAttribPointer
#  undef glDrawArrays
#  undef glDrawElements
#  define glGenVertexArrays RAS_WebGLGenVertexArrays
#  define glDeleteVertexArrays RAS_WebGLDeleteVertexArrays
#  define glBindVertexArray RAS_WebGLBindVertexArray
#  define glBindBuffer RAS_WebGLBindBuffer
#  define glEnableVertexAttribArray RAS_WebGLEnableVertexAttribArray
#  define glDisableVertexAttribArray RAS_WebGLDisableVertexAttribArray
#  define glVertexAttribPointer RAS_WebGLVertexAttribPointer
#  define glDrawArrays RAS_WebGLDrawArrays
#  define glDrawElements RAS_WebGLDrawElements
#  define RAS_VertexAttribDivisor emscripten_glVertexAttribDivisor
#  define RAS_DrawArraysInstanced RAS_WebGLDrawArraysInstanced
#else
#  define RAS_VertexAttribDivisor glVertexAttribDivisorARB
#  define RAS_DrawArraysInstanced glDrawArraysInstancedARB
#endif

#endif  // __RAS_WEBGLCOMPAT_H__
