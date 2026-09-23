/*
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
 * The Original Code is Copyright (C) 2005 Blender Foundation.
 * All rights reserved.
 */

#include "MEM_guardedalloc.h"

#include "BLI_blenlib.h"
#include "BLI_utildefines.h"
#include "BLI_math_base.h"

#include "BKE_global.h"

#include "GPU_debug.h"
#include "GPU_glew.h"
#include "GPU_framebuffer.h"
#include "GPU_shader.h"
#include "GPU_texture.h"
#include "GPU_vertex_array.h"

#ifdef __EMSCRIPTEN__
/* GLEW stores the desktop EXT entry points in function pointers. Emscripten's
 * WebGL2 implementation exports the equivalent core GLES3 functions directly,
 * while those GLEW extension pointers remain null. Keep the compatibility names
 * used by this legacy file, but route them to the WebGL2 entry points. */
#  undef glGenFramebuffers
#  undef glBindFramebuffer
#  undef glDeleteFramebuffers
#  undef glCheckFramebufferStatus
#  undef glFramebufferTexture2D
#  undef glGenRenderbuffers
#  undef glBindRenderbuffer
#  undef glDeleteRenderbuffers
#  undef glRenderbufferStorage
#  undef glRenderbufferStorageMultisample
#  undef glFramebufferRenderbuffer
#  undef glBlitFramebuffer
#  undef glReadBuffer
#  undef glDrawBuffers
#  undef glDrawBuffer
extern void glGenFramebuffers(GLsizei n, GLuint *framebuffers);
extern void glBindFramebuffer(GLenum target, GLuint framebuffer);
extern void glDeleteFramebuffers(GLsizei n, const GLuint *framebuffers);
extern GLenum glCheckFramebufferStatus(GLenum target);
extern void glFramebufferTexture2D(
    GLenum target, GLenum attachment, GLenum textarget, GLuint texture, GLint level);
extern void glGenRenderbuffers(GLsizei n, GLuint *renderbuffers);
extern void glBindRenderbuffer(GLenum target, GLuint renderbuffer);
extern void glDeleteRenderbuffers(GLsizei n, const GLuint *renderbuffers);
extern void glRenderbufferStorage(
    GLenum target, GLenum internalformat, GLsizei width, GLsizei height);
extern void glRenderbufferStorageMultisample(
    GLenum target, GLsizei samples, GLenum internalformat, GLsizei width, GLsizei height);
extern void glFramebufferRenderbuffer(
    GLenum target, GLenum attachment, GLenum renderbuffertarget, GLuint renderbuffer);
extern void glBlitFramebuffer(GLint srcX0,
                              GLint srcY0,
                              GLint srcX1,
                              GLint srcY1,
                              GLint dstX0,
                              GLint dstY0,
                              GLint dstX1,
                              GLint dstY1,
                              GLbitfield mask,
                              GLenum filter);
extern void glReadBuffer(GLenum src);
extern void glDrawBuffers(GLsizei n, const GLenum *bufs);

static void web_glDrawBuffer(GLenum buf)
{
	glDrawBuffers(1, &buf);
}

#  define glDrawBuffer web_glDrawBuffer
#  undef glGenFramebuffersEXT
#  undef glBindFramebufferEXT
#  undef glDeleteFramebuffersEXT
#  undef glCheckFramebufferStatusEXT
#  undef glFramebufferTexture2DEXT
#  undef glGenRenderbuffersEXT
#  undef glBindRenderbufferEXT
#  undef glDeleteRenderbuffersEXT
#  undef glRenderbufferStorageEXT
#  undef glRenderbufferStorageMultisampleEXT
#  undef glFramebufferRenderbufferEXT
#  undef glBlitFramebufferEXT
#  define glGenFramebuffersEXT glGenFramebuffers
#  define glBindFramebufferEXT glBindFramebuffer
#  define glDeleteFramebuffersEXT glDeleteFramebuffers
#  define glCheckFramebufferStatusEXT glCheckFramebufferStatus
#  define glFramebufferTexture2DEXT glFramebufferTexture2D
#  define glGenRenderbuffersEXT glGenRenderbuffers
#  define glBindRenderbufferEXT glBindRenderbuffer
#  define glDeleteRenderbuffersEXT glDeleteRenderbuffers
#  define glRenderbufferStorageEXT glRenderbufferStorage
#  define glRenderbufferStorageMultisampleEXT glRenderbufferStorageMultisample
#  define glFramebufferRenderbufferEXT glFramebufferRenderbuffer
#  define glBlitFramebufferEXT glBlitFramebuffer
#endif

static struct GPUFrameBufferGlobal {
	GLuint currentfb;
} GG = {0};

/* Full-screen quad used by GPU_framebuffer_blur(), generic-attribute VBO/VAO since
 * core profile has no immediate mode (glBegin/glVertex2f/glEnd). Lazily created on
 * first use, freed in GPU_framebuffer_blur_free() alongside the builtin blur shader. */
static struct {
	GLuint vbo;
	GLuint vao;
	bool initialized;
} g_blur_quad = {0, 0, false};

static void gpu_framebuffer_blur_quad_ensure(void)
{
	if (g_blur_quad.initialized)
		return;

	/* 2f position | 2f UV, matching the old glVertex2f/glTexCoord2d draw order. */
	static const float vertices[] = {
		 1.0f,  1.0f,  0.0f, 0.0f,
		-1.0f,  1.0f,  1.0f, 0.0f,
		-1.0f, -1.0f,  1.0f, 1.0f,
		 1.0f, -1.0f,  0.0f, 1.0f,
	};

	glGenBuffers(1, &g_blur_quad.vbo);
	GPU_create_vertex_arrays(1, &g_blur_quad.vao);

	GPU_bind_vertex_array(g_blur_quad.vao);

	glBindBuffer(GL_ARRAY_BUFFER, g_blur_quad.vbo);
	glBufferData(GL_ARRAY_BUFFER, sizeof(vertices), vertices, GL_STATIC_DRAW);

	/* blender/gpu's CMakeLists.txt adds WITH_GL_PROFILE_CORE on top of the directory's
	 * default WITH_GL_PROFILE_COMPAT for this file (per-source COMPILE_DEFINITIONS is
	 * additive, unlike RAS_OpenGLRasterizer's exclusive define swap) -- so this must
	 * check CORE is absent too, not just that COMPAT is present. */
#if defined(WITH_GL_PROFILE_COMPAT) && !defined(WITH_GL_PROFILE_CORE)
	glEnableClientState(GL_VERTEX_ARRAY);
	glEnableClientState(GL_TEXTURE_COORD_ARRAY);
	glVertexPointer(2, GL_FLOAT, sizeof(float) * 4, 0);
	glTexCoordPointer(2, GL_FLOAT, sizeof(float) * 4, ((char *)NULL) + sizeof(float) * 2);
#endif

	glEnableVertexAttribArray(0);
	glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, sizeof(float) * 4, 0);
	glEnableVertexAttribArray(1);
	glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, sizeof(float) * 4, ((char *)NULL) + sizeof(float) * 2);

	glBindBuffer(GL_ARRAY_BUFFER, 0);
	GPU_unbind_vertex_array();

	g_blur_quad.initialized = true;
}

static void gpu_framebuffer_blur_quad_draw(void)
{
	GPU_bind_vertex_array(g_blur_quad.vao);
	glDrawArrays(GL_TRIANGLE_FAN, 0, 4);
	GPU_unbind_vertex_array();
}

void GPU_framebuffer_blur_free(void)
{
	if (!g_blur_quad.initialized)
		return;

	GPU_delete_vertex_arrays(1, &g_blur_quad.vao);
	glDeleteBuffers(1, &g_blur_quad.vbo);
	g_blur_quad.initialized = false;
}

// Number of maximum output slots.
#define GPU_FB_MAX_SLOTS 8

struct GPUFrameBuffer {
	GLuint object;
	GPUTexture *colortex[GPU_FB_MAX_SLOTS];
	GPUTexture *depthtex;
	GPURenderBuffer *colorrb[GPU_FB_MAX_SLOTS];
	GPURenderBuffer *depthrb;
};

static void gpu_print_framebuffer_error(GLenum status, char err_out[256])
{
	const char *err = "unknown";

	switch (status) {
		case GL_FRAMEBUFFER_COMPLETE_EXT:
			break;
		case GL_INVALID_OPERATION:
			err = "Invalid operation";
			break;
		case GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT_EXT:
			err = "Incomplete attachment";
			break;
		case GL_FRAMEBUFFER_UNSUPPORTED_EXT:
			err = "Unsupported framebuffer format";
			break;
		case GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT_EXT:
			err = "Missing attachment";
			break;
		case GL_FRAMEBUFFER_INCOMPLETE_DIMENSIONS_EXT:
			err = "Attached images must have same dimensions";
			break;
		case GL_FRAMEBUFFER_INCOMPLETE_FORMATS_EXT:
			err = "Attached images must have same format";
			break;
		case GL_FRAMEBUFFER_INCOMPLETE_DRAW_BUFFER_EXT:
			err = "Missing draw buffer";
			break;
		case GL_FRAMEBUFFER_INCOMPLETE_READ_BUFFER_EXT:
			err = "Missing read buffer";
			break;
	}

	if (err_out) {
		BLI_snprintf(err_out, 256, "GPUFrameBuffer: framebuffer incomplete error %d '%s'",
			(int)status, err);
	}
	else {
		fprintf(stderr, "GPUFrameBuffer: framebuffer incomplete error %d '%s'\n",
			(int)status, err);
	}
}

/* GPUFrameBuffer */

GPUFrameBuffer *GPU_framebuffer_create(void)
{
	GPUFrameBuffer *fb;

#ifndef __EMSCRIPTEN__
	if (!(GLEW_VERSION_3_0 || GLEW_ARB_framebuffer_object ||
	      (GLEW_EXT_framebuffer_object && GLEW_EXT_framebuffer_blit)))
	{
		return NULL;
	}
#endif

	fb = MEM_callocN(sizeof(GPUFrameBuffer), "GPUFrameBuffer");
	glGenFramebuffersEXT(1, &fb->object);

	if (!fb->object) {
		fprintf(stderr, "GPUFFrameBuffer: framebuffer gen failed. %d\n",
			(int)glGetError());
		GPU_framebuffer_free(fb);
		return NULL;
	}

	/* make sure no read buffer is enabled, so completeness check will not fail. We set those at binding time */
	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);
	glReadBuffer(GL_NONE);
	glDrawBuffer(GL_NONE);
	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, 0);

	return fb;
}

int GPU_framebuffer_texture_attach(GPUFrameBuffer *fb, GPUTexture *tex, int slot, char err_out[256])
{
	return GPU_framebuffer_texture_attach_target(fb, tex, GPU_texture_target(tex), slot, err_out);
}

int GPU_framebuffer_texture_attach_target(GPUFrameBuffer *fb, GPUTexture *tex, int target, int slot, char err_out[256])
{
	GLenum attachment;
	GLenum error;

	if (slot >= GPU_FB_MAX_SLOTS) {
		fprintf(stderr,
		        "Attaching to index %d framebuffer slot unsupported. "
		        "Use at most %d\n", slot, GPU_FB_MAX_SLOTS);
		return 0;
	}

	if ((G.debug & G_DEBUG)) {
		if (GPU_texture_bound_number(tex) != -1) {
			fprintf(stderr,
			        "Feedback loop warning!: "
			        "Attempting to attach texture to framebuffer while still bound to texture unit for drawing!\n");
		}
	}

	if (GPU_texture_depth(tex))
		attachment = GL_DEPTH_ATTACHMENT_EXT;
	else
		attachment = GL_COLOR_ATTACHMENT0_EXT + slot;

	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);
	GG.currentfb = fb->object;

	/* Clean glError buffer. */
	while (glGetError() != GL_NO_ERROR) {}

	glFramebufferTexture2DEXT(GL_FRAMEBUFFER_EXT, attachment,
		target, GPU_texture_opengl_bindcode(tex), 0);

	error = glGetError();

	if (error == GL_INVALID_OPERATION) {
		GPU_framebuffer_restore();
		gpu_print_framebuffer_error(error, err_out);
		return 0;
	}

	if (GPU_texture_depth(tex))
		fb->depthtex = tex;
	else
		fb->colortex[slot] = tex;

	GPU_texture_framebuffer_set(tex, fb, slot);

	return 1;
}

void GPU_framebuffer_texture_detach(GPUTexture *tex)
{
	GPU_framebuffer_texture_detach_target(tex, GPU_texture_target(tex));
}

void GPU_framebuffer_texture_detach_target(GPUTexture *tex, int target)
{
	GLenum attachment;
	GPUFrameBuffer *fb = GPU_texture_framebuffer(tex);
	int fb_attachment = GPU_texture_framebuffer_attachment(tex);

	if (!fb)
		return;

	if (GG.currentfb != fb->object) {
		glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);
		GG.currentfb = fb->object;
	}

	if (GPU_texture_depth(tex)) {
		fb->depthtex = NULL;
		attachment = GL_DEPTH_ATTACHMENT_EXT;
	}
	else {
		BLI_assert(fb->colortex[fb_attachment] == tex);
		fb->colortex[fb_attachment] = NULL;
		attachment = GL_COLOR_ATTACHMENT0_EXT + fb_attachment;
	}

	glFramebufferTexture2DEXT(GL_FRAMEBUFFER_EXT, attachment, target, 0, 0);

	GPU_texture_framebuffer_set(tex, NULL, -1);
}

void GPU_texture_bind_as_framebuffer(GPUTexture *tex)
{
	GPUFrameBuffer *fb = GPU_texture_framebuffer(tex);
	int fb_attachment = GPU_texture_framebuffer_attachment(tex);

	if (!fb) {
		fprintf(stderr, "Error, texture not bound to framebuffer!\n");
		return;
	}

	/* push attributes */
	glPushAttrib(GL_ENABLE_BIT | GL_VIEWPORT_BIT);
	glDisable(GL_SCISSOR_TEST);

	/* bind framebuffer */
	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);

	if (GPU_texture_depth(tex)) {
		glDrawBuffer(GL_NONE);
		glReadBuffer(GL_NONE);
	}
	else {
		/* last bound prevails here, better allow explicit control here too */
		glDrawBuffer(GL_COLOR_ATTACHMENT0_EXT + fb_attachment);
		glReadBuffer(GL_COLOR_ATTACHMENT0_EXT + fb_attachment);
	}

	if (GPU_texture_target(tex) == GL_TEXTURE_2D_MULTISAMPLE) {
		glEnable(GL_MULTISAMPLE);
	}

	/* push matrices and set default viewport and matrix */
	glViewport(0, 0, GPU_texture_width(tex), GPU_texture_height(tex));
	GG.currentfb = fb->object;

	glMatrixMode(GL_PROJECTION);
	glPushMatrix();
	glMatrixMode(GL_MODELVIEW);
	glPushMatrix();
}

void GPU_framebuffer_slots_bind(GPUFrameBuffer *fb, int slot)
{
	int numslots = 0, i;
	GLenum attachments[4];

	if (!fb->colortex[slot]) {
		fprintf(stderr, "Error, framebuffer slot empty!\n");
		return;
	}

	for (i = 0; i < 4; i++) {
		if (fb->colortex[i]) {
			attachments[numslots] = GL_COLOR_ATTACHMENT0_EXT + i;
			numslots++;
		}
	}

	/* push attributes */
	glPushAttrib(GL_ENABLE_BIT | GL_VIEWPORT_BIT);
	glDisable(GL_SCISSOR_TEST);

	/* bind framebuffer */
	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);

	/* last bound prevails here, better allow explicit control here too */
	glDrawBuffers(numslots, attachments);
	glReadBuffer(GL_COLOR_ATTACHMENT0_EXT + slot);

	/* push matrices and set default viewport and matrix */
	glViewport(0, 0, GPU_texture_width(fb->colortex[slot]), GPU_texture_height(fb->colortex[slot]));
	GG.currentfb = fb->object;

	glMatrixMode(GL_PROJECTION);
	glPushMatrix();
	glMatrixMode(GL_MODELVIEW);
	glPushMatrix();
}


void GPU_framebuffer_texture_unbind(GPUFrameBuffer *UNUSED(fb), GPUTexture *UNUSED(tex))
{
	/* restore matrix */
	glMatrixMode(GL_PROJECTION);
	glPopMatrix();
	glMatrixMode(GL_MODELVIEW);
	glPopMatrix();

	/* restore attributes */
	glPopAttrib();
}

void GPU_framebuffer_bind_no_save(GPUFrameBuffer *fb, int slot)
{
	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);
	/* last bound prevails here, better allow explicit control here too */
	glDrawBuffer(GL_COLOR_ATTACHMENT0_EXT + slot);
	glReadBuffer(GL_COLOR_ATTACHMENT0_EXT + slot);

	/* push matrices and set default viewport and matrix */
	glViewport(0, 0, GPU_texture_width(fb->colortex[slot]), GPU_texture_height(fb->colortex[slot]));
	GG.currentfb = fb->object;
}

void GPU_framebuffer_bind_simple(GPUFrameBuffer *fb)
{
	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);
	/* last bound prevails here, better allow explicit control here too */
	glDrawBuffer(GL_COLOR_ATTACHMENT0_EXT);
	glReadBuffer(GL_COLOR_ATTACHMENT0_EXT);

	GG.currentfb = fb->object;
}

static const GLenum attachments[GPU_FB_MAX_SLOTS] = {
	GL_COLOR_ATTACHMENT0_EXT,
	GL_COLOR_ATTACHMENT1_EXT,
	GL_COLOR_ATTACHMENT2_EXT,
	GL_COLOR_ATTACHMENT3_EXT,
	GL_COLOR_ATTACHMENT4_EXT,
	GL_COLOR_ATTACHMENT5_EXT,
	GL_COLOR_ATTACHMENT6_EXT,
	GL_COLOR_ATTACHMENT7_EXT
};

void GPU_framebuffer_bind_all_attachments(GPUFrameBuffer *fb, int numAttachment)
{
	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);
	glDrawBuffers(numAttachment, attachments);
	glReadBuffer(GL_COLOR_ATTACHMENT0_EXT);

	GG.currentfb = fb->object;
}

bool GPU_framebuffer_bound(GPUFrameBuffer *fb)
{
	return fb->object == GG.currentfb;
}

bool GPU_framebuffer_check_valid(GPUFrameBuffer *fb, char err_out[256])
{
	GLenum status;

	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);
	GG.currentfb = fb->object;

	/* Clean glError buffer. */
	while (glGetError() != GL_NO_ERROR) {}

	status = glCheckFramebufferStatusEXT(GL_FRAMEBUFFER_EXT);

	if (status != GL_FRAMEBUFFER_COMPLETE_EXT) {
		GPU_framebuffer_restore();
		gpu_print_framebuffer_error(status, err_out);
		return false;
	}

	return true;
}

int GPU_framebuffer_renderbuffer_attach(GPUFrameBuffer *fb, GPURenderBuffer *rb, int slot, char err_out[256])
{
	GLenum attachement;
	GLenum error;

	if (slot >= GPU_FB_MAX_SLOTS) {
		fprintf(stderr,
		        "Attaching to index %d framebuffer slot unsupported. "
		        "Use at most %d\n", slot, GPU_FB_MAX_SLOTS);
		return 0;
	}

	if (GPU_renderbuffer_depth(rb)) {
		attachement = GL_DEPTH_ATTACHMENT_EXT;
	}
	else {
		attachement = GL_COLOR_ATTACHMENT0_EXT + slot;
	}

	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);
	GG.currentfb = fb->object;

	/* Clean glError buffer. */
	while (glGetError() != GL_NO_ERROR) {}

	glFramebufferRenderbufferEXT(GL_FRAMEBUFFER_EXT, attachement, GL_RENDERBUFFER_EXT, GPU_renderbuffer_bindcode(rb));

	error = glGetError();

	if (error == GL_INVALID_OPERATION) {
		GPU_framebuffer_restore();
		gpu_print_framebuffer_error(error, err_out);
		return 0;
	}

	if (GPU_renderbuffer_depth(rb))
		fb->depthrb = rb;
	else
		fb->colorrb[slot] = rb;

	GPU_renderbuffer_framebuffer_set(rb, fb, slot);

	return 1;
}

void GPU_framebuffer_renderbuffer_detach(GPURenderBuffer *rb)
{
	GLenum attachment;
	GPUFrameBuffer *fb = GPU_renderbuffer_framebuffer(rb);
	int fb_attachment = GPU_renderbuffer_framebuffer_attachment(rb);

	if (!fb)
		return;

	if (GG.currentfb != fb->object) {
		glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);
		GG.currentfb = fb->object;
	}

	if (GPU_renderbuffer_depth(rb)) {
		fb->depthrb = NULL;
		attachment = GL_DEPTH_ATTACHMENT_EXT;
	}
	else {
		BLI_assert(fb->colorrb[fb_attachment] == rb);
		fb->colorrb[fb_attachment] = NULL;
		attachment = GL_COLOR_ATTACHMENT0_EXT + fb_attachment;
	}

	glFramebufferRenderbufferEXT(GL_FRAMEBUFFER_EXT, attachment, GL_RENDERBUFFER_EXT, 0);

	GPU_renderbuffer_framebuffer_set(rb, NULL, -1);
}

void GPU_framebuffer_free(GPUFrameBuffer *fb)
{
	int i;
	if (fb->depthtex)
		GPU_framebuffer_texture_detach(fb->depthtex);

	for (i = 0; i < GPU_FB_MAX_SLOTS; i++) {
		if (fb->colortex[i]) {
			GPU_framebuffer_texture_detach(fb->colortex[i]);
		}
	}

	if (fb->depthrb)
		GPU_framebuffer_renderbuffer_detach(fb->depthrb);

	for (i = 0; i < GPU_FB_MAX_SLOTS; i++) {
		if (fb->colorrb[i]) {
			GPU_framebuffer_renderbuffer_detach(fb->colorrb[i]);
		}
	}

	if (fb->object) {
		glDeleteFramebuffersEXT(1, &fb->object);

		if (GG.currentfb == fb->object) {
			glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, 0);
			GG.currentfb = 0;
		}
	}

	MEM_freeN(fb);
}

void GPU_framebuffer_restore(void)
{
	if (GG.currentfb != 0) {
		glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, 0);
		GG.currentfb = 0;
	}
}

void GPU_framebuffer_blur(
        GPUFrameBuffer *fb, GPUTexture *tex,
        GPUFrameBuffer *blurfb, GPUTexture *blurtex, float sharpness)
{
	const float scaleh[2] = {(1.0f - sharpness) / GPU_texture_width(blurtex), 0.0f};
	const float scalev[2] = {0.0f, (1.0f - sharpness) / GPU_texture_height(tex)};

	GPUShader *blur_shader = GPU_shader_get_builtin_shader(GPU_SHADER_SEP_GAUSSIAN_BLUR);
	int scale_uniform, texture_source_uniform;

	if (!blur_shader)
		return;

	scale_uniform = GPU_shader_get_uniform(blur_shader, "ScaleU");
	texture_source_uniform = GPU_shader_get_uniform(blur_shader, "textureSource");

	gpu_framebuffer_blur_quad_ensure();

	/* Blurring horizontally */

	/* We do the bind ourselves rather than using GPU_framebuffer_texture_bind() to avoid
	 * pushing unnecessary matrices onto the OpenGL stack. */
	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, blurfb->object);
	glDrawBuffer(GL_COLOR_ATTACHMENT0_EXT);

	/* avoid warnings from texture binding */
	GG.currentfb = blurfb->object;

	GPU_shader_bind(blur_shader);
	GPU_shader_uniform_vector(blur_shader, scale_uniform, 2, 1, scaleh);
	GPU_texture_bind(tex, 0);
	GPU_shader_uniform_texture(blur_shader, texture_source_uniform, tex);
	glViewport(0, 0, GPU_texture_width(blurtex), GPU_texture_height(blurtex));

	glDisable(GL_DEPTH_TEST);

	/* Drawing quad */
	gpu_framebuffer_blur_quad_draw();

	/* Blurring vertically */

	glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fb->object);
	glDrawBuffer(GL_COLOR_ATTACHMENT0_EXT);

	GG.currentfb = fb->object;

	GPU_shader_uniform_vector(blur_shader, scale_uniform, 2, 1, scalev);
	GPU_texture_bind(blurtex, 0);
	GPU_shader_uniform_texture(blur_shader, texture_source_uniform, blurtex);
	glViewport(0, 0, GPU_texture_width(tex), GPU_texture_height(tex));

	gpu_framebuffer_blur_quad_draw();

	GPU_texture_unbind(blurtex);
	GPU_shader_unbind();

	glEnable(GL_DEPTH_TEST);
}

void GPU_framebuffer_blit(GPUFrameBuffer *srcfb, GPUFrameBuffer *dstfb, int width, int height,
		int numAttachment, bool depth)
{
	glBindFramebufferEXT(GL_READ_FRAMEBUFFER_EXT, srcfb->object);
	glBindFramebufferEXT(GL_DRAW_FRAMEBUFFER_EXT, dstfb->object);

	if (numAttachment == 0) {
		/* Depth-only framebuffer (e.g. shadow buffers): no color attachments to iterate,
		 * but the depth blit below still needs to run once. */
		if (depth) {
			glBlitFramebufferEXT(0, 0, width, height, 0, 0, width, height, GL_DEPTH_BUFFER_BIT, GL_NEAREST);
		}
		return;
	}

	int mask = GL_COLOR_BUFFER_BIT;
	if (depth) {
		mask |= GL_DEPTH_BUFFER_BIT;
	}

	for (unsigned short i = 0; i < numAttachment; ++i) {
#ifdef __EMSCRIPTEN__
		/* WebGL2: o anexo i so pode ficar na posicao i do array de drawBuffers; as demais NONE. */
		GLenum bufs[16];
		const int nbufs = (i < 15) ? i + 1 : 16;
		for (int j = 0; j < nbufs; ++j) {
			bufs[j] = (j == i) ? (GLenum)(GL_COLOR_ATTACHMENT0 + i) : GL_NONE;
		}
		glDrawBuffers(nbufs, bufs);
#else
		glDrawBuffer(GL_COLOR_ATTACHMENT0 + i);
#endif
		glReadBuffer(GL_COLOR_ATTACHMENT0 + i);

		glBlitFramebufferEXT(0, 0, width, height, 0, 0, width, height, mask, GL_NEAREST);
	}
}

/* GPURenderBuffer */

struct GPURenderBuffer {
	int width;
	int height;
	int samples;

	GPUFrameBuffer *fb; /* GPUFramebuffer this render buffer is attached to */
	int fb_attachment;  /* slot the render buffer is attached to */
	bool depth;
	unsigned int bindcode;
};

GPURenderBuffer *GPU_renderbuffer_create(int width, int height, int samples, GPUHDRType hdrtype, GPURenderBufferType type, char err_out[256])
{
	GPURenderBuffer *rb = MEM_callocN(sizeof(GPURenderBuffer), "GPURenderBuffer");

	glGenRenderbuffers(1, &rb->bindcode);

	if (!rb->bindcode) {
		if (err_out) {
			BLI_snprintf(err_out, 256, "GPURenderBuffer: render buffer creation failed: %d",
				(int)glGetError());
		}
		else {
			fprintf(stderr, "GPURenderBuffer: render buffer creation failed: %d\n",
				(int)glGetError());
		}
		GPU_renderbuffer_free(rb);
		return NULL;
	}

	rb->width = width;
	rb->height = height;
	rb->samples = samples;

	glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, rb->bindcode);

	if (type == GPU_RENDERBUFFER_DEPTH) {
#ifdef __EMSCRIPTEN__
		/* WebGL2/GLES3 rejeita o formato de profundidade sem tamanho em renderbuffers. */
		const GLenum depthformat = GL_DEPTH_COMPONENT24;
#else
		const GLenum depthformat = GL_DEPTH_COMPONENT;
#endif
		if (samples > 0) {
			glRenderbufferStorageMultisampleEXT(GL_RENDERBUFFER_EXT, samples, depthformat, width, height);
		}
		else {
			glRenderbufferStorageEXT(GL_RENDERBUFFER_EXT, depthformat, width, height);
		}
		rb->depth = true;
	}
	else {
		GLenum internalformat = GL_RGBA8;
		switch (hdrtype) {
			case GPU_HDR_NONE:
			{
				internalformat = GL_RGBA8;
				break;
			}
			/* the following formats rely on ARB_texture_float or OpenGL 3.0 */
			case GPU_HDR_HALF_FLOAT:
			{
				internalformat = GL_RGBA16F_ARB;
				break;
			}
			case GPU_HDR_FULL_FLOAT:
			{
				internalformat = GL_RGBA32F_ARB;
				break;
			}
		}
		if (samples > 0) {
			glRenderbufferStorageMultisampleEXT(GL_RENDERBUFFER_EXT, samples, internalformat, width, height);
		}
		else {
			glRenderbufferStorageEXT(GL_RENDERBUFFER_EXT, internalformat, width, height);
		}
	}

	glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, 0);

	return rb;
}

void GPU_renderbuffer_free(GPURenderBuffer *rb)
{
	if (rb->bindcode) {
		glDeleteRenderbuffersEXT(1, &rb->bindcode);
	}

	MEM_freeN(rb);
}

GPUFrameBuffer *GPU_renderbuffer_framebuffer(GPURenderBuffer *rb)
{
	return rb->fb;
}

int GPU_renderbuffer_framebuffer_attachment(GPURenderBuffer *rb)
{
	return rb->fb_attachment;
}

void GPU_renderbuffer_framebuffer_set(GPURenderBuffer *rb, GPUFrameBuffer *fb, int attachement)
{
	rb->fb = fb;
	rb->fb_attachment = attachement;
}

int GPU_renderbuffer_bindcode(const GPURenderBuffer *rb)
{
	return rb->bindcode;
}

bool GPU_renderbuffer_depth(const GPURenderBuffer *rb)
{
	return rb->depth;
}

int GPU_renderbuffer_width(const GPURenderBuffer *rb)
{
	return rb->width;
}

int GPU_renderbuffer_height(const GPURenderBuffer *rb)
{
	return rb->height;
}

/* GPUOffScreen */

struct GPUOffScreen {
	GPUFrameBuffer *fb;
	GPUTexture *color;
	GPUTexture *depth;
};

GPUOffScreen *GPU_offscreen_create(int width, int height, int samples, char err_out[256])
{
	GPUOffScreen *ofs;

	ofs = MEM_callocN(sizeof(GPUOffScreen), "GPUOffScreen");

	ofs->fb = GPU_framebuffer_create();
	if (!ofs->fb) {
		GPU_offscreen_free(ofs);
		return NULL;
	}

	if (samples) {
		if (!GLEW_EXT_framebuffer_multisample ||
		    !GLEW_ARB_texture_multisample ||
		    /* Only needed for GPU_offscreen_read_pixels.
		     * We could add an arg if we intend to use multi-sample
		     * offscreen buffers w/o reading their pixels */
		    !GLEW_EXT_framebuffer_blit ||
		    /* This is required when blitting from a multi-sampled buffers,
		     * even though we're not scaling. */
		    !GLEW_EXT_framebuffer_multisample_blit_scaled)
		{
			samples = 0;
		}
	}

	ofs->depth = GPU_texture_create_depth_multisample(width, height, samples, true, err_out);
	if (!ofs->depth) {
		GPU_offscreen_free(ofs);
		return NULL;
	}

	if (!GPU_framebuffer_texture_attach(ofs->fb, ofs->depth, 0, err_out)) {
		GPU_offscreen_free(ofs);
		return NULL;
	}

	ofs->color = GPU_texture_create_2D_multisample(width, height, NULL, GPU_HDR_NONE, samples, err_out);
	if (!ofs->color) {
		GPU_offscreen_free(ofs);
		return NULL;
	}

	if (!GPU_framebuffer_texture_attach(ofs->fb, ofs->color, 0, err_out)) {
		GPU_offscreen_free(ofs);
		return NULL;
	}

	/* check validity at the very end! */
	if (!GPU_framebuffer_check_valid(ofs->fb, err_out)) {
		GPU_offscreen_free(ofs);
		return NULL;
	}

	GPU_framebuffer_restore();

	return ofs;
}

void GPU_offscreen_free(GPUOffScreen *ofs)
{
	if (ofs->fb)
		GPU_framebuffer_free(ofs->fb);
	if (ofs->color)
		GPU_texture_free(ofs->color);
	if (ofs->depth)
		GPU_texture_free(ofs->depth);

	MEM_freeN(ofs);
}

void GPU_offscreen_bind(GPUOffScreen *ofs, bool save)
{
	glDisable(GL_SCISSOR_TEST);
	if (save)
		GPU_texture_bind_as_framebuffer(ofs->color);
	else {
		GPU_framebuffer_bind_no_save(ofs->fb, 0);
	}
}

void GPU_offscreen_unbind(GPUOffScreen *ofs, bool restore)
{
	if (restore)
		GPU_framebuffer_texture_unbind(ofs->fb, ofs->color);
	GPU_framebuffer_restore();
	glEnable(GL_SCISSOR_TEST);
}

void GPU_offscreen_read_pixels(GPUOffScreen *ofs, int type, void *pixels)
{
	const int w = GPU_texture_width(ofs->color);
	const int h = GPU_texture_height(ofs->color);

	if (GPU_texture_target(ofs->color) == GL_TEXTURE_2D_MULTISAMPLE) {
		/* For a multi-sample texture,
		 * we need to create an intermediate buffer to blit to,
		 * before its copied using 'glReadPixels' */

		/* not needed since 'ofs' needs to be bound to the framebuffer already */
// #define USE_FBO_CTX_SWITCH

		GLuint fbo_blit = 0;
		GLuint tex_blit = 0;
		GLenum status;

		/* create texture for new 'fbo_blit' */
		glGenTextures(1, &tex_blit);
		if (!tex_blit) {
			goto finally;
		}

		glBindTexture(GL_TEXTURE_2D, tex_blit);
		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_RGBA, type, 0);

#ifdef USE_FBO_CTX_SWITCH
		/* read from multi-sample buffer */
		glBindFramebufferEXT(GL_READ_FRAMEBUFFER_EXT, ofs->color->fb->object);
		glFramebufferTexture2DEXT(
		        GL_READ_FRAMEBUFFER_EXT, GL_COLOR_ATTACHMENT0_EXT + ofs->color->fb_attachment,
		        GL_TEXTURE_2D_MULTISAMPLE, ofs->color->bindcode, 0);
		status = glCheckFramebufferStatusEXT(GL_READ_FRAMEBUFFER_EXT);
		if (status != GL_FRAMEBUFFER_COMPLETE_EXT) {
			goto finally;
		}
#endif

		/* write into new single-sample buffer */
		glGenFramebuffersEXT(1, &fbo_blit);
		glBindFramebufferEXT(GL_DRAW_FRAMEBUFFER_EXT, fbo_blit);
		glFramebufferTexture2DEXT(
		        GL_DRAW_FRAMEBUFFER_EXT, GL_COLOR_ATTACHMENT0_EXT,
		        GL_TEXTURE_2D, tex_blit, 0);
		status = glCheckFramebufferStatusEXT(GL_DRAW_FRAMEBUFFER_EXT);
		if (status != GL_FRAMEBUFFER_COMPLETE_EXT) {
			goto finally;
		}

		/* perform the copy */
		glBlitFramebufferEXT(0, 0, w, h, 0, 0, w, h, GL_COLOR_BUFFER_BIT, GL_NEAREST);

		/* read the results */
		glBindFramebufferEXT(GL_READ_FRAMEBUFFER_EXT, fbo_blit);
		glReadPixels(0, 0, w, h, GL_RGBA, type, pixels);

#ifdef USE_FBO_CTX_SWITCH
		/* restore the original frame-bufer */
		glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, ofs->color->fb->object);
#undef USE_FBO_CTX_SWITCH
#endif


finally:
		/* cleanup */
		if (tex_blit) {
			glDeleteTextures(1, &tex_blit);
		}
		if (fbo_blit) {
			glDeleteFramebuffersEXT(1, &fbo_blit);
		}

		GPU_ASSERT_NO_GL_ERRORS("Read Multi-Sample Pixels");
	}
	else {
		glReadPixels(0, 0, w, h, GL_RGBA, type, pixels);
	}
}

int GPU_offscreen_width(const GPUOffScreen *ofs)
{
	return GPU_texture_width(ofs->color);
}

int GPU_offscreen_height(const GPUOffScreen *ofs)
{
	return GPU_texture_height(ofs->color);
}

int GPU_offscreen_color_texture(const GPUOffScreen *ofs)
{
	return GPU_texture_opengl_bindcode(ofs->color);
}

GPUTexture *GPU_offscreen_texture(const GPUOffScreen *ofs)
{
	return ofs->color;
}

GPUTexture *GPU_offscreen_depth_texture(const GPUOffScreen *ofs)
{
	return ofs->depth;
}

