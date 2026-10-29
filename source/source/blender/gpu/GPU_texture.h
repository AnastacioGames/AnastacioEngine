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

/** \file GPU_texture.h
 *  \ingroup gpu
 */

#ifndef __GPU_TEXTURE_H__
#define __GPU_TEXTURE_H__

#ifdef __cplusplus
extern "C" {
#endif

struct Image;
struct ImageUser;
struct PreviewImage;

struct GPUFrameBuffer;
typedef struct GPUTexture GPUTexture;

/* GPU Texture
 * - always returns unsigned char RGBA textures
 * - if texture with non square dimensions is created, depending on the
 *   graphics card capabilities the texture may actually be stored in a
 *   larger texture with power of two dimensions.
 * - can use reference counting:
 *   - reference counter after GPU_texture_create is 1
 *   - GPU_texture_ref increases by one
 *   - GPU_texture_free decreases by one, and frees if 0
 * - if created with from_blender, will not free the texture
 */

typedef enum GPUHDRType {
	GPU_HDR_NONE =       0,
	GPU_HDR_HALF_FLOAT = 1,
	GPU_HDR_FULL_FLOAT = (1 << 1),
} GPUHDRType;

typedef enum GPUTextureMode {
	GPU_TEXTURE_MODE_NONE = 0,
	GPU_TEXTURE_DEPTH = 1 << 0,
	GPU_TEXTURE_DEPTH_COMPARE = 1 << 1,
} GPUTextureMode;

GPUTexture *GPU_texture_create_1D(int w, const float *pixels, char err_out[256]);
GPUTexture *GPU_texture_create_2D(int w, int h, const float *pixels, GPUHDRType hdr, char err_out[256]);
GPUTexture *GPU_texture_create_cube(int size, GPUHDRType hdr, char err_out[256]);
GPUTexture *GPU_texture_create_3D(int w, int h, int depth, int channels, const float *fpixels);
GPUTexture *GPU_texture_create_depth(int w, int h, bool compare, char err_out[256]);
GPUTexture *GPU_texture_create_vsm_shadow_map(int size, char err_out[256]);
bool GPU_texture_resize_2D(GPUTexture *tex, int w, int h);
GPUTexture *GPU_texture_create_2D_procedural(int w, int h, const float *pixels, bool repeat, bool filter, char err_out[256]);
GPUTexture *GPU_texture_create_1D_procedural(int w, const float *pixels, char err_out[256]);
GPUTexture *GPU_texture_create_2D_multisample(
        int w, int h, const float *pixels, GPUHDRType hdr, int samples, char err_out[256]);
GPUTexture *GPU_texture_create_depth_multisample(int w, int h, int samples, bool compare, char err_out[256]);
GPUTexture *GPU_texture_from_blender(
        struct Image *ima, struct ImageUser *iuser, int textarget, bool is_data, double time, int mipmap);
GPUTexture *GPU_texture_from_preview(struct PreviewImage *prv, int mipmap);
GPUTexture *GPU_texture_create_jitter(int w);
GPUTexture *GPU_texture_global_jitter_64(void);
/* Principled BSDF environment table (gpu_brdf_lut.h): split-sum (A, B), clearcoat albedo and
 * the lights' lobe energy for the Multiscatter GGX compensation. NULL when it could not be
 * created; the node then keeps the analytic env_brdf_approx path. */
GPUTexture *GPU_texture_global_brdf_lut(void);
GPUTexture **GPU_texture_global_depth_ptr(void);
void GPU_texture_set_global_depth(GPUTexture *depthtex);
/* Game PBR screen-space refraction: copy of the scene color after the solid pass (mipmapped),
 * read by Glass / Refraction in the alpha pass. NULL resets it to the 1x1 placeholder, which the
 * shader takes as "no copy" (World fallback). A material that needs it calls request, and the
 * game only makes the copy once one has. */
GPUTexture **GPU_texture_global_scene_color_ptr(void);
void GPU_texture_set_global_scene_color(GPUTexture *colortex);
void GPU_texture_scene_color_request(void);
int GPU_texture_scene_color_requested(void);
/* GPU particle screen-space collision: view*projection matrix used to render the global
 * depth texture, cached alongside it (see gpu_texture.c). Returns 0 (r_viewproj untouched)
 * if no valid depth has been cached this session/since the last ResetGlobalDepthTexture. */
void GPU_texture_set_global_depth_viewproj(const float viewproj[16]);
int GPU_texture_get_global_depth_viewproj(float r_viewproj[16]);
/* GPU particle screen-space collision, "GPU Particle Collider" flavor: separate from the
 * global depth texture above (which stays tied to Depth Transparency / soft particles) --
 * populated by KX_KetsjiEngine::RenderCollisionDepthBuffer from objects flagged
 * use_gpu_particle_collider, independent of any material flag. */
GPUTexture **GPU_texture_global_collider_depth_ptr(void);
void GPU_texture_set_global_collider_depth(GPUTexture *depthtex);
void GPU_texture_set_global_collider_depth_viewproj(const float viewproj[16]);
int GPU_texture_get_global_collider_depth_viewproj(float r_viewproj[16]);
void GPU_invalid_tex_init(void);
void GPU_invalid_tex_bind(int mode);
void GPU_invalid_tex_free(void);

void GPU_texture_free(GPUTexture *tex);

void GPU_texture_ref(GPUTexture *tex);
int GPU_texture_ref_count(GPUTexture *tex);

void GPU_texture_bind(GPUTexture *tex, int number);
void GPU_texture_unbind(GPUTexture *tex);
bool GPU_texture_bind_cached(GPUTexture *tex, int number);
bool GPU_texture_unit_clear_cached(int number);
void GPU_texture_unit_cache_note(int number, unsigned int bindcode);
void GPU_texture_unit_cache_reset(void);
int GPU_texture_bound_number(GPUTexture *tex);
bool GPU_texture_unit_fixed_function(int number);

void GPU_texture_filter_mode(GPUTexture *tex, bool compare, bool use_filter, bool mipmap);
void GPU_texture_generate_mipmap(GPUTexture *tex);

struct GPUFrameBuffer *GPU_texture_framebuffer(GPUTexture *tex);
int GPU_texture_framebuffer_attachment(GPUTexture *tex);
void GPU_texture_framebuffer_set(GPUTexture *tex, struct GPUFrameBuffer *fb, int attachment);

int GPU_texture_target(const GPUTexture *tex);
typedef struct GPUCubeSH9Reader GPUCubeSH9Reader;
GPUCubeSH9Reader *GPU_cube_sh9_reader_create(void);
void GPU_cube_sh9_reader_free(GPUCubeSH9Reader *reader);
/* Starts copying the cube's low mip (<= 16 px); false if one is still pending or tex is no cube. */
bool GPU_cube_sh9_reader_request(GPUCubeSH9Reader *reader, GPUTexture *tex);
/* True once the copy is done, with the diffuse SH9 (cosine lobe / pi folded in) in r_coef. */
bool GPU_cube_sh9_reader_poll(GPUCubeSH9Reader *reader, float r_coef[9][3]);
int GPU_texture_width(const GPUTexture *tex);
int GPU_texture_height(const GPUTexture *tex);
int GPU_texture_depth(const GPUTexture *tex);
int GPU_texture_opengl_bindcode(const GPUTexture *tex);

void GPU_texture_set_opengl_bindcode(GPUTexture *tex, int bindcode);


#ifdef __cplusplus
}
#endif

#endif  /* __GPU_TEXTURE_H__ */
