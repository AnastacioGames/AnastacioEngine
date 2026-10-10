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

/** \file GPU_shader.h
 *  \ingroup gpu
 */

#ifndef __GPU_SHADER_H__
#define __GPU_SHADER_H__

#ifdef __cplusplus
extern "C" {
#endif

typedef struct GPUShader GPUShader;
struct GPUTexture;

/* GPU Shader
 * - only for fragment shaders now
 * - must call texture bind before setting a texture as uniform! */

enum {
	GPU_SHADER_FLAGS_NONE = 0,
	GPU_SHADER_FLAGS_SPECIAL_OPENSUBDIV = (1 << 0),
	GPU_SHADER_FLAGS_NEW_SHADING        = (1 << 1),
	GPU_SHADER_FLAGS_SPECIAL_INSTANCING = (1 << 2),
	GPU_SHADER_FLAGS_FOLIAGE			= (1 << 3),
	GPU_SHADER_FLAGS_USER_CODE			= (1 << 4),
	GPU_SHADER_FLAGS_SPECIAL_SKINNING	= (1 << 5),
	/* Program binary may come from / go to the cooked file (only for programs never relinked later). */
	GPU_SHADER_FLAGS_BINARY_CACHE		= (1 << 6),
};

/* Cooked program binaries: set by the game engine while a game runs, NULL otherwise.
 * find returns the binary of the key (valid until the hooks are cleared) or NULL. */
typedef const void *(*GPUShaderBinaryFind)(unsigned long long key, unsigned int *format, int *size);
typedef void (*GPUShaderBinaryAdd)(unsigned long long key, unsigned int format, const void *data, int size);
void GPU_shader_binary_cache_set(GPUShaderBinaryFind find, GPUShaderBinaryAdd add);
/* Hash of the GPU and driver (binaries of another one are useless), 0 when program binaries are unsupported. */
unsigned long long GPU_shader_binary_device_key(void);

/* Parallel compile (GL_ARB_parallel_shader_compile): between begin and end, material programs (BINARY_CACHE flag)
 * are only sent to the driver and kept pending, create returns NULL. The next create of the same sources takes
 * the pending program. begin returns false (nothing changes) when the driver lacks the extension. */
bool GPU_shader_prefetch_begin(void);
void GPU_shader_prefetch_end(void);
bool GPU_shader_prefetching(void);
/* Deletes the pending programs nobody took. */
void GPU_shader_prefetch_clear(void);

GPUShader *GPU_shader_create(
        const char *vertexcode,
        const char *fragcode,
        const char *geocode,
        const char *libcode,
        const char *defines,
        int input, int output, int number);
GPUShader *GPU_shader_create_ex(
        const char *vertexcode,
        const char *fragcode,
        const char *geocode,
        const char *libcode,
        const char *defines,
        int input, int output, int number,
        const int flags);
/* `name` identifies the owner in diagnostics only. It is not retained by the shader. */
GPUShader *GPU_shader_create_ex_named(
        const char *vertexcode,
        const char *fragcode,
        const char *geocode,
        const char *libcode,
        const char *defines,
        int input, int output, int number,
        const int flags,
        const char *name);
char *GPU_shader_validate(GPUShader *shader);
void GPU_shader_free(GPUShader *shader);

void GPU_shader_bind(GPUShader *shader);
void GPU_shader_unbind(void);

int GPU_shader_program(GPUShader *shader);

typedef struct GPUUniformInfo
{
	unsigned int size;
	unsigned int type;
	char name[255];
} GPUUniformInfo;

int GPU_shader_get_uniform_infos(GPUShader *shader, GPUUniformInfo **infos);

void *GPU_shader_get_interface(GPUShader *shader);
void GPU_shader_set_interface(GPUShader *shader, void *interface);
int GPU_shader_get_uniform(GPUShader *shader, const char *name);
void GPU_shader_uniform_vector(GPUShader *shader, int location, int length,
	int arraysize, const float *value);
void GPU_shader_uniform_vector_int(GPUShader *shader, int location, int length,
	int arraysize, const int *value);

void GPU_shader_uniform_texture(GPUShader *shader, int location, struct GPUTexture *tex);
void GPU_shader_uniform_int(GPUShader *shader, int location, int value);
void GPU_shader_uniform_float(GPUShader *shader, int location, float value);
bool GPU_shader_uniform_vector_cached(GPUShader *shader, int location, int length, const float *value);
bool GPU_shader_uniform_int_cached(GPUShader *shader, int location, int value);
void GPU_shader_geometry_stage_primitive_io(GPUShader *shader, int input, int output, int number);

int GPU_shader_get_attribute(GPUShader *shader, const char *name);
void GPU_shader_bind_attribute(GPUShader *shader, int location, const char *name);

void GPU_shader_bind_instancing_attrib(GPUShader *shader, void *matrixoffset, void *positionoffset);

/* Builtin/Non-generated shaders */
typedef enum GPUBuiltinShader {
	GPU_SHADER_VSM_STORE            = 0,
	GPU_SHADER_VSM_STORE_INSTANCING = 1,
	GPU_SHADER_SEP_GAUSSIAN_BLUR    = 2,
	GPU_SHADER_SMOKE                = 3,
	GPU_SHADER_SMOKE_FIRE           = 4,
	GPU_SHADER_SMOKE_COBA           = 5,
	GPU_SHADER_BLACK                = 6,
	GPU_SHADER_BLACK_INSTANCING     = 7,
	GPU_SHADER_DRAW_FRAME_BUFFER	= 8,
	GPU_SHADER_STEREO_STIPPLE       = 9,
	GPU_SHADER_STEREO_ANAGLYPH      = 10,
	GPU_SHADER_FRUSTUM_LINE         = 11,
	GPU_SHADER_FRUSTUM_SOLID        = 12,
	GPU_SHADER_FLAT_COLOR           = 13,
	GPU_SHADER_2D_BOX               = 14,
	/* Camera-facing radial glow billboard used as a distant-light impostor when a lamp is
	 * culled out by KX_LightObject's distance culling (RAS_DebugDraw::DrawLightGlow /
	 * RAS_OpenGLDebugDraw). Instanced quad expanded in the vertex shader using camera
	 * right/up vectors, radial falloff computed in the fragment shader. */
	GPU_SHADER_LIGHT_GLOW           = 15,
	/* Frame buffer draw with per-eye barrel distortion for side by side VR (Cardboard lenses). */
	GPU_SHADER_VR_LENS              = 16,
} GPUBuiltinShader;

GPUShader *GPU_shader_get_builtin_shader(GPUBuiltinShader shader);
GPUShader *GPU_shader_get_builtin_fx_shader(int effects, bool persp);

void GPU_shader_free_builtin_shaders(void);

/* Vertex attributes for shaders */

#define GPU_MAX_ATTRIB 32

typedef struct GPUVertexAttribs {
	struct {
		int type;
		int glindex;
		int glinfoindoex;
		int gltexco;
		int attribid;
		char name[64];	/* MAX_CUSTOMDATA_LAYER_NAME */
	} layer[GPU_MAX_ATTRIB];

	int totlayer;
	/* Wireframe node in the viewport: GL location + 1 of the per-loop triangle corner attribute
	 * (attbary), 0 when unused. The Game unshares vertices and uses gl_VertexID instead. */
	int barycentric;
} GPUVertexAttribs;

/* Per-frame counters read and cleared by the game engine profiler (KX_EngineProfiler). */
enum {
	GPU_PROFILE_SHADERS = 0,
	GPU_PROFILE_TEXTURES,
	GPU_PROFILE_IMAGE_UPLOADS,
	GPU_PROFILE_TOT
};
extern int GPU_profile_counters[GPU_PROFILE_TOT];
/* RANGE_SHADER_LOG on: shaders bound for the first time since the profiler last cleared it. */
extern char GPU_profile_first_binds[1024];
/* RANGE_SHADER_LOG on: profiler frame number written with each line, and a line per GPU texture created. */
extern long GPU_profile_frame;
void GPU_profile_log_texture(int w, int h, bool depth, int samples);

#ifdef __cplusplus
}
#endif

#endif  /* __GPU_SHADER_H__ */
