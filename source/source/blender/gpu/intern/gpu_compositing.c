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
 * The Original Code is Copyright (C) 2006 Blender Foundation.
 * All rights reserved.
 */

/** \file blender/gpu/intern/gpu_compositing.c
 *  \ingroup gpu
 *
 * System that manages framebuffer compositing.
 */

#include "BLI_sys_types.h"
#include "BLI_rect.h"
#include "BLI_math.h"

#include "BLI_rand.h"
#include "BLI_listbase.h"
#include "BLI_utildefines.h"

#include <stddef.h>

#include "DNA_vec_types.h"
#include "DNA_scene_types.h"
#include "DNA_gpu_types.h"
#include "DNA_object_types.h"
#include "DNA_world_types.h"
#include "DNA_lamp_types.h"
#include "DNA_property_types.h"

#include "BKE_property.h"

#include "GPU_material.h"

#include "GPU_compositing.h"
#include "GPU_extensions.h"
#include "GPU_framebuffer.h"
#include "GPU_glew.h"
#include "GPU_shader.h"
#include "GPU_texture.h"

#include "MEM_guardedalloc.h"

#include "PIL_time.h"

#include "BKE_rain_lightning.h"

static const float fullscreencos[4][2] = {{-1.0f, -1.0f}, {1.0f, -1.0f}, {-1.0f, 1.0f}, {1.0f, 1.0f}};
static const float fullscreenuvs[4][2] = {{0.0f, 0.0f}, {1.0f, 0.0f}, {0.0f, 1.0f}, {1.0f, 1.0f}};


/* shader interfaces (legacy GL 2 style, without uniform buffer objects) */

typedef struct {
	int ssao_uniform;
	int ssao_color_uniform;
	int color_uniform;
	int depth_uniform;
	int viewvecs_uniform;
	int ssao_sample_params_uniform;
	int ssao_concentric_tex;
	int ssao_jitter_uniform;
} GPUSSAOShaderInterface;

typedef struct {
  int color_uniform;
  int bloom_uniform;
} GPUBLOOMShaderInterface;

typedef struct {
  int color_uniform;
  int tonemapParams_uniform;
} GPUTONEMAPShaderInterface;

typedef struct {
  int color_uniform;
  int depth_uniform;
  int sunpos_uniform;
  int scatter_params_uniform;
} GPULIGHTSCATTERShaderInterface;

typedef struct {
  int ssr_uniform;
  int color_uniform;
  int depth_uniform;
  int viewvecs_uniform;
  int ssr_jitter_uniform;
} GPUSSRShaderInterface;

typedef struct {
  int color_uniform;
  int viewport_size_uniform;
  int fxaa_params_uniform;
} GPUFXAAShaderInterface;

typedef struct {
  int color_uniform;
  int depth_uniform;
  int sunpos_uniform;
  int flare_params_uniform;
  int viewport_size_uniform;
} GPULENSFLAREShaderInterface;

typedef struct {
  int color_uniform;
  int depth_uniform;
  int rain_params1_uniform;
  int rain_params2_uniform;
  int rain_params3_uniform;
  int rain_color_uniform;
  int rain_style_uniform;
  int rain_fall_phase_uniform;
  int rain_params4_uniform;
  int rain_lightning_uniform;
  int rain_streak_width_uniform;
  int rain_ripple_normal_uniform;
  int rain_params5_uniform;
  int rain_puddle1_uniform;
  int rain_puddle2_uniform;
  int rain_sky_horizon_uniform;
  int rain_sky_zenith_uniform;
} GPURAINShaderInterface;

typedef struct {
  int color_uniform;
  int depth_uniform;
  int clouds_params_uniform;
  int clouds_color_uniform;
  int clouds_mask_uniform;
  int sky_layers_params_uniform;
  int sky_layers_color_uniform;
  int clouds_quality_uniform;
  int vclouds_params1_uniform;
  int vclouds_params2_uniform;
  int vclouds_params3_uniform;
  int vclouds_color_uniform;
  int vclouds_sundir_uniform;
  int history_uniform;
  int history_depth_uniform;
  int history_valid_uniform;
  int history_viewproj_uniform;
  int frame_uniform;
} GPUCLOUDSShaderInterface;

typedef struct {
  int color_uniform;
  int depth_uniform;
  int data_uniform;
  int mats_uniform;
  int shadow0_uniform;
  int shadow1_uniform;
  int shadow2_uniform;
  int frame_uniform;
} GPUVFOGShaderInterface;

typedef struct {
  int color_uniform;
  int grain_params_uniform;
} GPUGRAINShaderInterface;

typedef struct {
	int invrendertargetdim_uniform;
	int color_uniform;
	int dof_uniform;
	int depth_uniform;
	int viewvecs_uniform;
} GPUDOFHQPassOneInterface;

typedef struct {
	int rendertargetdim_uniform;
	int color_uniform;
	int coc_uniform;
	int select_uniform;
	int dof_uniform;
} GPUDOFHQPassTwoInterface;

typedef struct {
	int dof_uniform;
	int invrendertargetdim_uniform;
	int color_uniform;
	int far_uniform;
	int near_uniform;
	int viewvecs_uniform;
	int depth_uniform;
} GPUDOFHQPassThreeInterface;

typedef struct {
	int dof_uniform;
	int invrendertargetdim_uniform;
	int color_uniform;
	int depth_uniform;
	int viewvecs_uniform;
} GPUDOFPassOneInterface;

typedef struct {
	int dof_uniform;
	int invrendertargetdim_uniform;
	int color_uniform;
	int depth_uniform;
	int viewvecs_uniform;
} GPUDOFPassTwoInterface;

typedef struct {
	int near_coc_downsampled;
	int near_coc_blurred;
} GPUDOFPassThreeInterface;

typedef struct {
	int near_coc_downsampled;
	int invrendertargetdim_uniform;
} GPUDOFPassFourInterface;

typedef struct {
	int medium_blurred_uniform;
	int high_blurred_uniform;
	int dof_uniform;
	int invrendertargetdim_uniform;
	int original_uniform;
	int depth_uniform;
	int viewvecs_uniform;
} GPUDOFPassFiveInterface;

typedef struct {
	int depth_uniform;
} GPUDepthResolveInterface;


struct GPUFX {
	/* we borrow the term gbuffer from deferred rendering however this is just a regular
	 * depth/color framebuffer. Could be extended later though */
	GPUFrameBuffer *gbuffer;

	/* dimensions of the gbuffer */
	int gbuffer_dim[2];

	/* texture bound to the first color attachment of the gbuffer */
	GPUTexture *color_buffer;

	/* second texture used for ping-pong compositing */
	GPUTexture *color_buffer_sec;
	/* texture bound to the depth attachment of the gbuffer */
	GPUTexture *depth_buffer;
	GPUTexture *depth_buffer_xray;

	/* texture used for jittering for various effects */
	GPUTexture *jitter_buffer;

	/* all those buffers below have to coexist.
	 * Fortunately they are all quarter sized (1/16th of memory) of original framebuffer */
	int dof_downsampled_w;
	int dof_downsampled_h;

	/* texture used for near coc and color blurring calculation */
	GPUTexture *dof_near_coc_buffer;
	/* blurred near coc buffer. */
	GPUTexture *dof_near_coc_blurred_buffer;
	/* final near coc buffer. */
	GPUTexture *dof_near_coc_final_buffer;

	/* half size blur buffer */
	GPUTexture *dof_half_downsampled_near;
	GPUTexture *dof_half_downsampled_far;
	/* high quality dof texture downsamplers. 6 levels means 64 pixels wide - should be enough */
	GPUTexture *dof_nearfar_coc;
	GPUTexture *dof_near_blur;
	GPUTexture *dof_far_blur;

	/* for high quality we use again a spiral texture with radius adapted */
	bool dof_high_quality;

	/* texture used for ssao */
	int ssao_sample_count_cache;
	GPUTexture *ssao_spiral_samples_tex;

	/* viewport size for fxaa and light scattering */
	int viewsize_w, viewsize_h;

	// Note: We have a separation between GPUFXSettings and SCENEFXSettings,
	// but they still work together, and use GPUFX in the same way.
	GPUFXSettings settings;

	/* or-ed flags of enabled effects */
	int effects, sce_effects;

	/* number of passes, needed to detect if ping pong buffer allocation is needed */
	int num_passes;

	/* we have a stencil, restore the previous state */
	bool restore_stencil;

	/* Volumetric Clouds temporal reuse, same scheme as RAS_2DFilterManager: the clouds pass
	 * output and depth of the last frame, with the view-projection they were drawn with. */
	unsigned int cloud_history;
	unsigned int cloud_history_depth;
	int cloud_history_w, cloud_history_h;
	bool cloud_history_valid;
	int cloud_history_frame;
	float cloud_history_persmat[4][4];

	int vfog_frame;

	unsigned int vbuffer;
};

#if 0
/* concentric mapping, see "A Low Distortion Map Between Disk and Square" and
 * http://psgraphics.blogspot.nl/2011/01/improved-code-for-concentric-map.html */
static GPUTexture * create_concentric_sample_texture(int side)
{
	GPUTexture *tex;
	float midpoint = 0.5f * (side - 1);
	float *texels = (float *)MEM_mallocN(sizeof(float) * 2 * side * side, "concentric_tex");
	int i, j;

	for (i = 0; i < side; i++) {
		for (j = 0; j < side; j++) {
			int index = (i * side + j) * 2;
			float a = 1.0f - i / midpoint;
			float b = 1.0f - j / midpoint;
			float phi, r;
			if (a * a > b * b) {
				r = a;
				phi = (M_PI_4) * (b / a);
			}
			else {
				r = b;
				phi = M_PI_2 - (M_PI_4) * (a / b);
			}
			texels[index] = r * cos(phi);
			texels[index + 1] = r * sin(phi);
		}
	}

	tex = GPU_texture_create_1D_procedural(side * side, texels, NULL);
	MEM_freeN(texels);
	return tex;
}
#endif

static GPUTexture *create_spiral_sample_texture(int numsaples)
{
	GPUTexture *tex;
	float (*texels)[2] = MEM_mallocN(sizeof(float[2]) * numsaples, "concentric_tex");
	const float numsaples_inv = 1.0f / numsaples;
	int i;
	/* arbitrary number to ensure we don't get conciding samples every circle */
	const float spirals = 7.357;

	for (i = 0; i < numsaples; i++) {
		float r = (i + 0.5f) * numsaples_inv;
		float phi = r * spirals * (float)(2.0 * M_PI);
		texels[i][0] = r * cosf(phi);
		texels[i][1] = r * sinf(phi);
	}

	tex = GPU_texture_create_1D_procedural(numsaples, (float *)texels, NULL);
	MEM_freeN(texels);
	return tex;
}

/* generate a new FX compositor */
GPUFX *GPU_fx_compositor_create(void)
{
	GPUFX *fx = MEM_callocN(sizeof(GPUFX), "GPUFX compositor");

	glGenBuffers(1, &fx->vbuffer);
	glBindBuffer(GL_ARRAY_BUFFER, fx->vbuffer);
	glBufferData(GL_ARRAY_BUFFER, 16 * sizeof(float), NULL, GL_STATIC_DRAW);
	glBufferSubData(GL_ARRAY_BUFFER, 0, 8 * sizeof(float), fullscreencos);
	glBufferSubData(GL_ARRAY_BUFFER, 8 * sizeof(float), 8 * sizeof(float), fullscreenuvs);
	glBindBuffer(GL_ARRAY_BUFFER, 0);

	return fx;
}

static void cleanup_fx_dof_buffers(GPUFX *fx)
{
	if (fx->dof_near_coc_blurred_buffer) {
		GPU_texture_free(fx->dof_near_coc_blurred_buffer);
		fx->dof_near_coc_blurred_buffer = NULL;
	}
	if (fx->dof_near_coc_buffer) {
		GPU_texture_free(fx->dof_near_coc_buffer);
		fx->dof_near_coc_buffer = NULL;
	}
	if (fx->dof_near_coc_final_buffer) {
		GPU_texture_free(fx->dof_near_coc_final_buffer);
		fx->dof_near_coc_final_buffer = NULL;
	}

	if (fx->dof_half_downsampled_near) {
		GPU_texture_free(fx->dof_half_downsampled_near);
		fx->dof_half_downsampled_near = NULL;
	}
	if (fx->dof_half_downsampled_far) {
		GPU_texture_free(fx->dof_half_downsampled_far);
		fx->dof_half_downsampled_far = NULL;
	}
	if (fx->dof_nearfar_coc) {
		GPU_texture_free(fx->dof_nearfar_coc);
		fx->dof_nearfar_coc = NULL;
	}
	if (fx->dof_near_blur) {
		GPU_texture_free(fx->dof_near_blur);
		fx->dof_near_blur = NULL;
	}
	if (fx->dof_far_blur) {
		GPU_texture_free(fx->dof_far_blur);
		fx->dof_far_blur = NULL;
	}
}

static void cleanup_fx_gl_data(GPUFX *fx, bool do_fbo)
{
	if (fx->color_buffer) {
		GPU_framebuffer_texture_detach(fx->color_buffer);
		GPU_texture_free(fx->color_buffer);
		fx->color_buffer = NULL;
	}

	if (fx->color_buffer_sec) {
		GPU_framebuffer_texture_detach(fx->color_buffer_sec);
		GPU_texture_free(fx->color_buffer_sec);
		fx->color_buffer_sec = NULL;
	}

	if (fx->depth_buffer) {
		GPU_framebuffer_texture_detach(fx->depth_buffer);
		GPU_texture_free(fx->depth_buffer);
		fx->depth_buffer = NULL;
	}

	if (fx->depth_buffer_xray) {
		GPU_framebuffer_texture_detach(fx->depth_buffer_xray);
		GPU_texture_free(fx->depth_buffer_xray);
		fx->depth_buffer_xray = NULL;
	}

	if (fx->cloud_history) {
		glDeleteTextures(1, &fx->cloud_history);
		glDeleteTextures(1, &fx->cloud_history_depth);
		fx->cloud_history = fx->cloud_history_depth = 0;
		fx->cloud_history_w = fx->cloud_history_h = 0;
	}
	fx->cloud_history_valid = false;

	cleanup_fx_dof_buffers(fx);

	if (fx->ssao_spiral_samples_tex) {
		GPU_texture_free(fx->ssao_spiral_samples_tex);
		fx->ssao_spiral_samples_tex = NULL;
	}

	if (fx->jitter_buffer && do_fbo) {
		GPU_texture_free(fx->jitter_buffer);
		fx->jitter_buffer = NULL;
	}

	if (fx->gbuffer && do_fbo) {
		GPU_framebuffer_free(fx->gbuffer);
		fx->gbuffer = NULL;
	}
}

/* destroy a text compositor */
void GPU_fx_compositor_destroy(GPUFX *fx)
{
	cleanup_fx_gl_data(fx, true);
	glDeleteBuffers(1, &fx->vbuffer);
	MEM_freeN(fx);
}

bool GPU_fx_compositor_initialize_passes(
        Scene *scene, GPUFX *fx, const rcti *rect, const rcti *scissor_rect,
        const GPUFXSettings *fx_settings)
{
	int w = BLI_rcti_size_x(rect), h = BLI_rcti_size_y(rect);
	char err_out[256];
	int num_passes = 0;
	char fx_flag;
	int scenefx_flag; /* int: bits derivados do World (ex. CLOUDS = 1 << 8) nao cabem em char */

	const SCENEFXSettings *scenefx_settings = &scene->scenefx_settings;

	fx->effects = 0;

	if (!GLEW_EXT_framebuffer_object)
		return false;

	if (!fx_settings && !scenefx_settings) {
		cleanup_fx_gl_data(fx, true);
		return false;
	}

	fx_flag = fx_settings->fx_flag;
	scenefx_flag = scene->scenefx_settings.scenefx_flag;

	/* disable effects if no options passed for them */
	if (!fx_settings->dof) {
		fx_flag &= ~GPU_FX_FLAG_DOF;
	}

	if (!scenefx_settings->bloom || !(scene->scenefx_settings.editor_render_flag & SCENE_FX_FLAG_BLOOM)) {
		scenefx_flag &= ~SCENE_FX_FLAG_BLOOM;
	}
	if (!scenefx_settings->tonemap || !(scene->scenefx_settings.editor_render_flag & SCENE_FX_FLAG_TONEMAP)) {
		scenefx_flag &= ~SCENE_FX_FLAG_TONEMAP;
	}
	if (!scenefx_settings->scatter || !(scene->scenefx_settings.editor_render_flag & SCENE_FX_FLAG_LIGHTSCATTER)) {
		scenefx_flag &= ~SCENE_FX_FLAG_LIGHTSCATTER;
	}
	if (!scenefx_settings->ssr || !(scene->scenefx_settings.editor_render_flag & SCENE_FX_FLAG_SSR)) {
		scenefx_flag &= ~SCENE_FX_FLAG_SSR;
	}
	if (!scenefx_settings->ssao || scenefx_settings->ssao->samples < 1 || !(scene->scenefx_settings.editor_render_flag & SCENE_FX_FLAG_SSAO)) {
		scenefx_flag &= ~SCENE_FX_FLAG_SSAO;
	}
	if (!(scene->scenefx_settings.editor_render_flag & SCENE_FX_FLAG_FXAA)) {
		scenefx_flag &= ~SCENE_FX_FLAG_FXAA;
	}

	/* Files saved by older engine versions can carry stray bits in
	 * scenefx_flag/editor_render_flag outside the currently defined
	 * eSCENEFXFlags range (e.g. a removed/repurposed effect slot). Such a bit
	 * is never cleared by the per-effect checks above, so scenefx_flag would
	 * stay non-zero forever even after every real filter is disabled -
	 * keeping the compositor stuck attaching buffers for zero actual passes,
	 * which hangs the GL driver. Mask down to the known bits so "no effects
	 * enabled" is reliably detected regardless of legacy file contents. */
	scenefx_flag &= (SCENE_FX_FLAG_BLOOM | SCENE_FX_FLAG_TONEMAP | SCENE_FX_FLAG_LIGHTSCATTER |
	                  SCENE_FX_FLAG_SSR | SCENE_FX_FLAG_SSAO | SCENE_FX_FLAG_FXAA);

	/* Lens Flare/Rain/Clouds mirror World > Weather directly (same World data used by
	 * the in-game filters); World.weather_editor_hide only hides them in the viewport. */
	if (scene->world && (scene->world->weather_flag & ~scene->world->weather_editor_hide & WO_WEATHER_LENSFLARE)) {
		scenefx_flag |= SCENE_FX_FLAG_LENSFLARE;
	}
	else {
		scenefx_flag &= ~SCENE_FX_FLAG_LENSFLARE;
	}

	if (scene->world && (scene->world->weather_flag & ~scene->world->weather_editor_hide & WO_WEATHER_RAIN)) {
		scenefx_flag |= SCENE_FX_FLAG_RAIN;
	}
	else {
		scenefx_flag &= ~SCENE_FX_FLAG_RAIN;
	}

	if (scene->world && ((scene->world->weather_flag & ~scene->world->weather_editor_hide & WO_WEATHER_CLOUDS) ||
	                     (scene->world->sky_layer_flag & (WO_SKY_LAYERS_ENABLE | WO_SKY_LAYERS_EDITOR_HIDE)) ==
	                         WO_SKY_LAYERS_ENABLE ||
	                     (scene->world->vcloud_flag & (WO_VCLOUDS_ENABLE | WO_VCLOUDS_EDITOR_HIDE)) ==
	                         WO_VCLOUDS_ENABLE)) {
		scenefx_flag |= SCENE_FX_FLAG_CLOUDS;
	}
	else {
		scenefx_flag &= ~SCENE_FX_FLAG_CLOUDS;
	}

	if (scene->world && (scene->world->vfog_flag & (WO_VFOG_ENABLE | WO_VFOG_EDITOR_HIDE)) == WO_VFOG_ENABLE) {
		scenefx_flag |= SCENE_FX_FLAG_VFOG;
	}
	else {
		scenefx_flag &= ~SCENE_FX_FLAG_VFOG;
	}

	if (scene->scenefx_settings.use_grain && scene->scenefx_settings.grain_strength > 0.0f &&
	    (scene->scenefx_settings.editor_render_flag & SCENE_FX_UI_GRAIN))
	{
		scenefx_flag |= SCENE_FX_FLAG_GRAIN;
	}

	/* The ping-pong textures are laid out according to the active pass chain.
	 * Recreate them when a scene effect is toggled so removing the final FXAA
	 * pass cannot reuse targets from the previous chain. */
	if (fx->sce_effects != scenefx_flag) {
		cleanup_fx_gl_data(fx, false);
	}

	if (!fx_flag && !scenefx_flag) {
		cleanup_fx_gl_data(fx, true);
		/* A compositor may survive after its final scene effect is disabled.
		 * Do not leave its previous frame state around: in particular,
		 * restore_stencil refers to an attribute stack push that was consumed by
		 * the preceding composite pass. */
		fx->effects = 0;
		fx->sce_effects = 0;
		fx->num_passes = 0;
		fx->restore_stencil = false;
		fx->gbuffer_dim[0] = 0;
		fx->gbuffer_dim[1] = 0;
		fx->viewsize_w = 0;
		fx->viewsize_h = 0;
		return false;
	}

	/* scissor is missing when drawing offscreen, in that case, dimensions match exactly. In opposite case
	 * add one to match viewport dimensions */
	if (scissor_rect) {
		w++;
		h++;
	}

	fx->num_passes = 0;
	/* dof really needs a ping-pong buffer to work */
	if (fx_flag & GPU_FX_FLAG_DOF)
		num_passes++;

	/* scenefx */
	if (scenefx_flag & SCENE_FX_FLAG_BLOOM)
		num_passes++;

	if (scenefx_flag & SCENE_FX_FLAG_TONEMAP)
		num_passes++;

	if (scenefx_flag & SCENE_FX_FLAG_LIGHTSCATTER)
		num_passes++;

	if (scenefx_flag & SCENE_FX_FLAG_SSR)
		num_passes++;

	if (scenefx_flag & SCENE_FX_FLAG_SSAO)
		num_passes++;

	if (scenefx_flag & SCENE_FX_FLAG_FXAA)
		num_passes++;

	if (scenefx_flag & SCENE_FX_FLAG_LENSFLARE)
		num_passes++;

	if (scenefx_flag & SCENE_FX_FLAG_RAIN)
		num_passes++;

	if (scenefx_flag & SCENE_FX_FLAG_CLOUDS)
		num_passes++;

	if (scenefx_flag & SCENE_FX_FLAG_VFOG)
		num_passes++;

	if (scenefx_flag & SCENE_FX_FLAG_GRAIN)
		num_passes++;

	if (!fx->gbuffer) {
		fx->gbuffer = GPU_framebuffer_create();

		if (!fx->gbuffer) {
			return false;
		}
	}

	/* try creating the jitter texture */
	if (!fx->jitter_buffer)
		fx->jitter_buffer = GPU_texture_create_jitter(64);

	/* check if color buffers need recreation */
	if (!fx->color_buffer || !fx->depth_buffer || w != fx->gbuffer_dim[0] || h != fx->gbuffer_dim[1]) {
		cleanup_fx_gl_data(fx, false);

		if (!(fx->color_buffer = GPU_texture_create_2D(w, h, NULL, GPU_HDR_NONE, err_out))) {
			printf(".256%s\n", err_out);
			cleanup_fx_gl_data(fx, true);
			return false;
		}

		if (!(fx->depth_buffer = GPU_texture_create_depth(w, h, true, err_out))) {
			printf("%.256s\n", err_out);
			cleanup_fx_gl_data(fx, true);
			return false;
		}
	}

	if (scenefx_flag & SCENE_FX_FLAG_SSAO) {
		if (scenefx_settings->ssao->samples != fx->ssao_sample_count_cache || !fx->ssao_spiral_samples_tex) {
			if (scenefx_settings->ssao->samples < 1)
				scenefx_settings->ssao->samples = 1;

			fx->ssao_sample_count_cache = scenefx_settings->ssao->samples;

			if (fx->ssao_spiral_samples_tex) {
				GPU_texture_free(fx->ssao_spiral_samples_tex);
			}

			fx->ssao_spiral_samples_tex = create_spiral_sample_texture(scenefx_settings->ssao->samples);
		}
	}
	else {
		if (fx->ssao_spiral_samples_tex) {
			GPU_texture_free(fx->ssao_spiral_samples_tex);
			fx->ssao_spiral_samples_tex = NULL;
		}
	}

	if (scenefx_flag & SCENE_FX_FLAG_FXAA || scenefx_flag & SCENE_FX_FLAG_LIGHTSCATTER ||
	    scenefx_flag & SCENE_FX_FLAG_LENSFLARE || scenefx_flag & SCENE_FX_FLAG_RAIN ||
	    scenefx_flag & SCENE_FX_FLAG_CLOUDS || scenefx_flag & SCENE_FX_FLAG_VFOG)
	{
		fx->viewsize_w = w;
		fx->viewsize_h = h;
	}

	/* create textures for dof effect */
	if (fx_flag & GPU_FX_FLAG_DOF) {
		bool dof_high_quality = (fx_settings->dof->high_quality != 0) &&
		                        GPU_geometry_shader_support() && GPU_instanced_drawing_support();

		/* cleanup buffers if quality setting has changed (no need to keep more buffers around than necessary ) */
		if (dof_high_quality != fx->dof_high_quality)
			cleanup_fx_dof_buffers(fx);

		if (dof_high_quality) {
			fx->dof_downsampled_w = w / 2;
			fx->dof_downsampled_h = h / 2;

			if (!fx->dof_half_downsampled_near || !fx->dof_nearfar_coc || !fx->dof_near_blur ||
			    !fx->dof_far_blur || !fx->dof_half_downsampled_far)
			{

				if (!(fx->dof_half_downsampled_near = GPU_texture_create_2D(
				      fx->dof_downsampled_w, fx->dof_downsampled_h, NULL, GPU_HDR_NONE, err_out)))
				{
					printf("%.256s\n", err_out);
					cleanup_fx_gl_data(fx, true);
					return false;
				}
				if (!(fx->dof_half_downsampled_far = GPU_texture_create_2D(
				      fx->dof_downsampled_w, fx->dof_downsampled_h, NULL, GPU_HDR_NONE, err_out)))
				{
					printf("%.256s\n", err_out);
					cleanup_fx_gl_data(fx, true);
					return false;
				}
				if (!(fx->dof_nearfar_coc = GPU_texture_create_2D_procedural(
				      fx->dof_downsampled_w, fx->dof_downsampled_h, NULL, false, false, err_out)))
				{
					printf("%.256s\n", err_out);
					cleanup_fx_gl_data(fx, true);
					return false;
				}


				if (!(fx->dof_near_blur = GPU_texture_create_2D(
				    fx->dof_downsampled_w, fx->dof_downsampled_h, NULL, GPU_HDR_HALF_FLOAT, err_out)))
				{
					printf("%.256s\n", err_out);
					cleanup_fx_gl_data(fx, true);
					return false;
				}

				if (!(fx->dof_far_blur = GPU_texture_create_2D(
				    fx->dof_downsampled_w, fx->dof_downsampled_h, NULL, GPU_HDR_HALF_FLOAT, err_out)))
				{
					printf("%.256s\n", err_out);
					cleanup_fx_gl_data(fx, true);
					return false;
				}
			}
		}
		else {
			fx->dof_downsampled_w = w / 4;
			fx->dof_downsampled_h = h / 4;

			if (!fx->dof_near_coc_buffer || !fx->dof_near_coc_blurred_buffer || !fx->dof_near_coc_final_buffer) {

				if (!(fx->dof_near_coc_buffer = GPU_texture_create_2D(
				          fx->dof_downsampled_w, fx->dof_downsampled_h, NULL, GPU_HDR_NONE, err_out)))
				{
					printf("%.256s\n", err_out);
					cleanup_fx_gl_data(fx, true);
					return false;
				}
				if (!(fx->dof_near_coc_blurred_buffer = GPU_texture_create_2D(
				          fx->dof_downsampled_w, fx->dof_downsampled_h, NULL, GPU_HDR_NONE, err_out)))
				{
					printf("%.256s\n", err_out);
					cleanup_fx_gl_data(fx, true);
					return false;
				}
				if (!(fx->dof_near_coc_final_buffer = GPU_texture_create_2D(
				          fx->dof_downsampled_w, fx->dof_downsampled_h, NULL, GPU_HDR_NONE, err_out)))
				{
					printf("%.256s\n", err_out);
					cleanup_fx_gl_data(fx, true);
					return false;
				}
			}
		}

		fx->dof_high_quality = dof_high_quality;
	}
	else {
		/* cleanup unnecessary buffers */
		cleanup_fx_dof_buffers(fx);
	}

	/* we need to pass data between shader stages, allocate an extra color buffer */
	if (num_passes > 1) {
		if (!fx->color_buffer_sec) {
			if (!(fx->color_buffer_sec = GPU_texture_create_2D(w, h, NULL, GPU_HDR_NONE, err_out))) {
				printf(".256%s\n", err_out);
				cleanup_fx_gl_data(fx, true);
				return false;
			}
		}
	}
	else {
		if (fx->color_buffer_sec) {
			GPU_framebuffer_texture_detach(fx->color_buffer_sec);
			GPU_texture_free(fx->color_buffer_sec);
			fx->color_buffer_sec = NULL;
		}
	}

	/* bind the buffers */

	/* first depth buffer, because system assumes read/write buffers */
	if (!GPU_framebuffer_texture_attach(fx->gbuffer, fx->depth_buffer, 0, err_out))
		printf("%.256s\n", err_out);

	if (!GPU_framebuffer_texture_attach(fx->gbuffer, fx->color_buffer, 0, err_out))
		printf("%.256s\n", err_out);

	if (!GPU_framebuffer_check_valid(fx->gbuffer, err_out))
		printf("%.256s\n", err_out);

	GPU_texture_bind_as_framebuffer(fx->color_buffer);

	/* enable scissor test. It's needed to ensure sculpting works correctly */
	if (scissor_rect) {
		int w_sc = BLI_rcti_size_x(scissor_rect) + 1;
		int h_sc = BLI_rcti_size_y(scissor_rect) + 1;
		glPushAttrib(GL_SCISSOR_BIT);
		glEnable(GL_SCISSOR_TEST);
		glScissor(scissor_rect->xmin - rect->xmin, scissor_rect->ymin - rect->ymin,
		          w_sc, h_sc);
		fx->restore_stencil = true;
	}
	else {
		fx->restore_stencil = false;
	}

	fx->effects = fx_flag;
	fx->sce_effects = scenefx_flag;

	if (fx_settings)
		fx->settings = *fx_settings;
	fx->gbuffer_dim[0] = w;
	fx->gbuffer_dim[1] = h;

	fx->num_passes = num_passes;

	return true;
}

static void gpu_fx_bind_render_target(int *passes_left, GPUFX *fx, struct GPUOffScreen *ofs, GPUTexture *target)
{
	if ((*passes_left)-- == 1) {
		GPU_framebuffer_texture_unbind(fx->gbuffer, NULL);
		if (ofs) {
			GPU_offscreen_bind(ofs, false);
		}
		else
			GPU_framebuffer_restore();
	}
	else {
		/* bind the ping buffer to the color buffer */
		GPU_framebuffer_texture_attach(fx->gbuffer, target, 0, NULL);
	}
}

void GPU_fx_compositor_setup_XRay_pass(GPUFX *fx, bool do_xray)
{
	char err_out[256];

	if (do_xray) {
		if (!fx->depth_buffer_xray &&
		    !(fx->depth_buffer_xray = GPU_texture_create_depth(fx->gbuffer_dim[0], fx->gbuffer_dim[1], true, err_out)))
		{
			printf("%.256s\n", err_out);
			cleanup_fx_gl_data(fx, true);
			return;
		}
	}
	else {
		if (fx->depth_buffer_xray) {
			GPU_framebuffer_texture_detach(fx->depth_buffer_xray);
			GPU_texture_free(fx->depth_buffer_xray);
			fx->depth_buffer_xray = NULL;
		}
		return;
	}

	GPU_framebuffer_texture_detach(fx->depth_buffer);

	/* first depth buffer, because system assumes read/write buffers */
	if (!GPU_framebuffer_texture_attach(fx->gbuffer, fx->depth_buffer_xray, 0, err_out))
		printf("%.256s\n", err_out);
}


void GPU_fx_compositor_XRay_resolve(GPUFX *fx)
{
	GPUShader *depth_resolve_shader;
	GPU_framebuffer_texture_detach(fx->depth_buffer_xray);

	/* attach regular framebuffer */
	GPU_framebuffer_texture_attach(fx->gbuffer, fx->depth_buffer, 0, NULL);

	/* full screen quad where we will always write to depth buffer */
	glPushAttrib(GL_DEPTH_BUFFER_BIT | GL_SCISSOR_BIT);
	glDepthFunc(GL_ALWAYS);
	/* disable scissor from sculpt if any */
	glDisable(GL_SCISSOR_TEST);
	/* disable writing to color buffer, it's depth only pass */
	glColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE);

	/* set up quad buffer */
	glBindBuffer(GL_ARRAY_BUFFER, fx->vbuffer);
	glVertexPointer(2, GL_FLOAT, 0, NULL);
	glTexCoordPointer(2, GL_FLOAT, 0, ((GLubyte *)NULL + 8 * sizeof(float)));
	glEnableClientState(GL_VERTEX_ARRAY);
	glEnableClientState(GL_TEXTURE_COORD_ARRAY);

	depth_resolve_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_DEPTH_RESOLVE, false);

	if (depth_resolve_shader) {
		GPUDepthResolveInterface *interface = GPU_shader_get_interface(depth_resolve_shader);

		GPU_shader_bind(depth_resolve_shader);

		GPU_texture_bind(fx->depth_buffer_xray, 0);
		GPU_texture_filter_mode(fx->depth_buffer_xray, false, true, false);
		GPU_shader_uniform_texture(depth_resolve_shader, interface->depth_uniform, fx->depth_buffer_xray);

		/* draw */
		glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

		/* disable bindings */
		GPU_texture_filter_mode(fx->depth_buffer_xray, true, false, false);
		GPU_texture_unbind(fx->depth_buffer_xray);

		GPU_shader_unbind();
	}

	glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);

	glBindBuffer(GL_ARRAY_BUFFER, 0);
	glDisableClientState(GL_VERTEX_ARRAY);
	glDisableClientState(GL_TEXTURE_COORD_ARRAY);

	glPopAttrib();
}

/* Volumetric Fog data for the 3D View, mirrors KX_FillVolumetricFog (KX_RenderPipeline.cpp):
 * layout in gpu_shader_vfog_lib.glsl. Fills shadow_tex 0-1 (Spots) and 2 (Sun). */
#define GPU_VFOG_DATA_VEC4 56
static void gpu_vfog_fill(Scene *scene, World *world, const float campos[3], float data[GPU_VFOG_DATA_VEC4][4],
                          float mats[7][4][4], unsigned int shadow_tex[3])
{
	static const int preset_max[3] = {2, 4, 8};
	const int quality = max_ii(0, min_ii(world->vfog_quality, 2));
	int volumes = 0, lamps = 0, shadows = 0, pushers = 0;
	float morning = 0.0f;

	memset(data, 0, sizeof(float) * GPU_VFOG_DATA_VEC4 * 4);
	memset(mats, 0, sizeof(float) * 7 * 16);
	shadow_tex[0] = shadow_tex[1] = shadow_tex[2] = 0;

	/* Morning Fog: denser and lower around dawn (World Property sun_hour, peak at 6h). */
	if (world->vfog_flag & WO_VFOG_TIME_OF_DAY) {
		bProperty *prop = BLI_findstring(&world->prop, "sun_hour", offsetof(bProperty, name));
		float hour = 12.0f, x;
		if (prop && prop->type == GPROP_FLOAT) {
			hour = *((float *)&prop->data);
		}
		else if (prop && prop->type == GPROP_INT) {
			hour = (float)prop->data;
		}
		hour = fmodf(hour, 24.0f);
		if (hour < 0.0f) {
			hour += 24.0f;
		}
		x = (hour - 6.0f) / 1.5f;
		morning = expf(-x * x);
	}

	data[0][0] = world->vfog_density * (1.0f + world->vfog_morning_boost * morning);
	data[0][1] = world->vfog_base;
	data[0][2] = max_ff(world->vfog_falloff * (1.0f - 0.5f * morning), 0.01f);
	data[0][3] = max_ff(world->vfog_distance, 1.0f);
	data[1][0] = world->vfog_noise_scale;
	data[1][1] = world->vfog_noise_amount;
	data[1][2] = (float)fmod(PIL_check_seconds_timer() * world->vfog_speed, 10000.0);
	data[1][3] = world->vfog_anisotropy;
	copy_v3_v3(data[2], world->vfog_color);
	data[2][3] = (float)quality;
	if (scene->world_sun && scene->world_sun->type == OB_LAMP) {
		Lamp *la = scene->world_sun->data;
		normalize_v3_v3(data[3], scene->world_sun->obmat[2]);
		data[3][3] = 1.0f;
		data[4][0] = la->r * min_ff(la->energy, 4.0f) * world->vfog_sun_intensity;
		data[4][1] = la->g * min_ff(la->energy, 4.0f) * world->vfog_sun_intensity;
		data[4][2] = la->b * min_ff(la->energy, 4.0f) * world->vfog_sun_intensity;
	}
	data[5][0] = world->horr * world->vfog_ambient;
	data[5][1] = world->horg * world->vfog_ambient;
	data[5][2] = world->horb * world->vfog_ambient;
	data[6][2] = world->vfog_light_intensity;
	data[6][3] = (world->vfog_flag & WO_VFOG_VOLUMES_ONLY) ? 1.0f : 0.0f;
	data[8][0] = world->vfog_edge;
	data[8][1] = world->vfog_shaft_intensity;

	/* Wind: the noise is carried along the heading vfog_wind_dir, at Rain Wind * 20 m/s. */
	if (world->vfog_flag & WO_VFOG_WIND) {
		const float angle = DEG2RADF(world->vfog_wind_dir);
		const float travel = (float)fmod(PIL_check_seconds_timer() * world->rain_wind * 20.0, 10000.0);
		data[9][0] = cosf(angle) * travel;
		data[9][1] = sinf(angle) * travel;
	}
	data[9][2] = (float)fmod(PIL_check_seconds_timer(), 10000.0);

	/* Sun shafts: the Sun's farthest shadow map (last cascade). */
	if ((world->vfog_flag & WO_VFOG_SUN_SHAFTS) && quality > 0 && data[3][3] > 0.5f) {
		Lamp *la = scene->world_sun->data;
		if ((la->mode & LA_SHAD_BUF) && la->shadowmap_type != LA_SHADMAP_VARIANCE) {
			GPULamp *lamp = GPU_lamp_from_blender(scene, scene->world_sun, NULL);
			if (lamp && GPU_lamp_has_shadow_buffer(lamp)) {
				if (GPU_lamp_has_cascaded_shadow(lamp)) {
					lamp = GPU_lamp_get_cascade(lamp, 1);
				}
				const int code = GPU_lamp_shadow_bind_code(lamp);
				if (code > 0) {
					shadow_tex[2] = (unsigned int)code;
					memcpy(mats[6], GPU_lamp_get_persmat(lamp), sizeof(float) * 16);
					data[8][2] = 0.001f;
					data[8][3] = 1.0f;
				}
			}
		}
	}

	/* Fog Volumes and lamps; lamps sorted by strength at the camera (insertion, at most 8 kept). */
	{
		Object *cand[8];
		float score[8];
		int ncand = 0;
		const int max_lamps = max_ii(1, min_ii(min_ii(world->vfog_max_lights, 8), preset_max[quality]));
		for (Base *base = scene->base.first; base; base = base->next) {
			Object *ob = base->object;
			if (!(base->lay & scene->lay) || (ob->restrictflag & OB_RESTRICT_VIEW)) {
				continue;
			}
			if (volumes < 4) {
				bProperty *prop = BKE_bproperty_object_get(ob, "fog_volume");
				if (prop) {
					float value = 1.0f;
					if (prop->type == GPROP_FLOAT) {
						value = *((float *)&prop->data);
					}
					else if (prop->type == GPROP_INT) {
						value = (float)prop->data;
					}
					bProperty *shape = BKE_bproperty_object_get(ob, "fog_shape");
					bProperty *edge = BKE_bproperty_object_get(ob, "fog_edge");
					bProperty *smoke = BKE_bproperty_object_get(ob, "fog_smoke");
					invert_m4_m4(mats[volumes], ob->obmat);
					data[7][volumes] = max_ff(0.0f, value);
					data[10][volumes] = (shape && shape->type == GPROP_STRING && STREQ((char *)shape->poin, "sphere")) ?
					                    1.0f : 0.0f;
					data[11][volumes] = world->vfog_edge;
					if (edge && edge->type == GPROP_FLOAT) {
						data[11][volumes] = clamp_f(*((float *)&edge->data), 0.0f, 1.0f);
					}
					if (smoke && smoke->type == GPROP_FLOAT) {
						data[48 + volumes][0] = max_ff(0.0f, *((float *)&smoke->data));
					}
					else if (smoke && smoke->type == GPROP_INT) {
						data[48 + volumes][0] = max_ff(0.0f, (float)smoke->data);
					}
					if (ob->col[0] < 0.999f || ob->col[1] < 0.999f || ob->col[2] < 0.999f) {
						copy_v3_v3(data[44 + volumes], ob->col);
						data[44 + volumes][3] = 1.0f;
					}
					volumes++;
				}
			}
			if (pushers < 4) {
				bProperty *push = BKE_bproperty_object_get(ob, "fog_push");
				float radius = 0.0f;
				if (push && push->type == GPROP_FLOAT) {
					radius = *((float *)&push->data);
				}
				else if (push && push->type == GPROP_INT) {
					radius = (float)push->data;
				}
				if (radius > 0.0f) {
					copy_v3_v3(data[52 + pushers], ob->obmat[3]);
					data[52 + pushers][3] = radius;
					pushers++;
				}
			}
			if (ob->type == OB_LAMP && (world->vfog_flag & WO_VFOG_LAMPS)) {
				Lamp *la = ob->data;
				if ((la->type != LA_LOCAL && la->type != LA_SPOT) || la->energy <= 0.0f) {
					continue;
				}
				const float dist = len_v3v3(ob->obmat[3], campos);
				if (dist > data[0][3] + la->dist) {
					continue;
				}
				const float r = max_ff(la->dist, 0.01f);
				const float s = la->energy * r * r / (r * r + dist * dist);
				int pos = ncand;
				while (pos > 0 && score[pos - 1] < s) {
					if (pos < max_lamps) {
						cand[pos] = cand[pos - 1];
						score[pos] = score[pos - 1];
					}
					pos--;
				}
				if (pos < max_lamps) {
					cand[pos] = ob;
					score[pos] = s;
					if (ncand < max_lamps) {
						ncand++;
					}
				}
			}
		}
		for (int i = 0; i < ncand; i++) {
			Object *ob = cand[i];
			Lamp *la = ob->data;
			float *pos = data[12 + 4 * i];
			float *col = data[13 + 4 * i];
			float *spot = data[14 + 4 * i];
			copy_v3_v3(pos, ob->obmat[3]);
			pos[3] = la->dist;
			col[0] = la->r * la->energy;
			col[1] = la->g * la->energy;
			col[2] = la->b * la->energy;
			col[3] = -1.0f;
			spot[3] = -2.0f;
			if (la->type == LA_SPOT) {
				const float cos_outer = cosf(la->spotsize * 0.5f);
				normalize_v3_v3(spot, ob->obmat[2]);
				negate_v3(spot);
				spot[3] = cos_outer;
				data[15 + 4 * i][0] = cos_outer + (1.0f - cos_outer) * la->spotblend;
				if ((world->vfog_flag & WO_VFOG_SHAFTS) && quality > 0 && shadows < 2 &&
				    (la->mode & LA_SHAD_BUF) && la->shadowmap_type != LA_SHADMAP_VARIANCE)
				{
					GPULamp *lamp = GPU_lamp_from_blender(scene, ob, NULL);
					const int code = lamp && GPU_lamp_has_shadow_buffer(lamp) ? GPU_lamp_shadow_bind_code(lamp) : -1;
					if (code > 0) {
						shadow_tex[shadows] = (unsigned int)code;
						memcpy(mats[4 + shadows], GPU_lamp_get_persmat(lamp), sizeof(float) * 16);
						col[3] = (float)shadows;
						data[15 + 4 * i][1] = 0.0005f;
						shadows++;
					}
				}
			}
			lamps++;
		}
	}
	data[6][0] = (float)lamps;
	data[6][1] = (float)volumes;
	data[9][3] = (float)pushers;
}

bool GPU_fx_do_composite_pass(
        GPUFX *fx, float viewmat[4][4], float projmat[4][4], bool is_persp,
        struct Scene *scene, struct GPUOffScreen *ofs)
{
	GPUTexture *src, *target;
	int numslots = 0;
	float invproj[4][4];
	int i;
	float dfdyfac[2];
	/* number of passes left. when there are no more passes, the result is passed to the frambuffer */
	int passes_left = fx->num_passes;
	/* view vectors for the corners of the view frustum. Can be used to recreate the world space position easily */
	float viewvecs[3][4] = {
	    {-1.0f, -1.0f, -1.0f, 1.0f},
	    {1.0f, -1.0f, -1.0f, 1.0f},
	    {-1.0f, 1.0f, -1.0f, 1.0f}
	};

	if (fx->effects == 0 && fx->sce_effects	== 0)
		return false;

	GPU_get_dfdy_factors(dfdyfac);
	/* first, unbind the render-to-texture framebuffer */
	GPU_framebuffer_texture_detach(fx->color_buffer);
	GPU_framebuffer_texture_detach(fx->depth_buffer);

	if (fx->restore_stencil) {
		glPopAttrib();
		fx->restore_stencil = false;
	}

	src = fx->color_buffer;
	target = fx->color_buffer_sec;

	/* set up quad buffer */
	glBindBuffer(GL_ARRAY_BUFFER, fx->vbuffer);
	glVertexPointer(2, GL_FLOAT, 0, NULL);
	glTexCoordPointer(2, GL_FLOAT, 0, ((GLubyte *)NULL + 8 * sizeof(float)));
	glEnableClientState(GL_VERTEX_ARRAY);
	glEnableClientState(GL_TEXTURE_COORD_ARRAY);

	/* full screen FX pass */

	/* invert the view matrix */
	invert_m4_m4(invproj, projmat);

	/* convert the view vectors to view space */
	for (i = 0; i < 3; i++) {
		mul_m4_v4(invproj, viewvecs[i]);
		/* normalized trick see http://www.derschmale.com/2014/01/26/reconstructing-positions-from-the-depth-buffer */
		mul_v3_fl(viewvecs[i], 1.0f / viewvecs[i][3]);
		if (is_persp)
			mul_v3_fl(viewvecs[i], 1.0f / viewvecs[i][2]);
		viewvecs[i][3] = 1.0;
	}

	/* we need to store the differences */
	viewvecs[1][0] -= viewvecs[0][0];
	viewvecs[1][1] = viewvecs[2][1] - viewvecs[0][1];

	/* calculate a depth offset as well */
	if (!is_persp) {
		float vec_far[] = {-1.0f, -1.0f, 1.0f, 1.0f};
		mul_m4_v4(invproj, vec_far);
		mul_v3_fl(vec_far, 1.0f / vec_far[3]);
		viewvecs[1][2] = vec_far[2] - viewvecs[0][2];
	}

	/* set invalid color in case shader fails */
	glColor3f(1.0, 0.0, 1.0);
	glDisable(GL_DEPTH_TEST);

	/* SCENE FX Passes */
	SCENEFXSettings scenefx = scene->scenefx_settings;

	/* ssao pass */
	if (fx->sce_effects & SCENE_FX_FLAG_SSAO) {
		GPUShader *ssao_shader;
		ssao_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_SSAO, is_persp);
		if (ssao_shader) {
			const GPUSSAOSettings *fx_ssao = scenefx.ssao;
			/* adjust attenuation to be scale invariant */
			float attenuation = fx_ssao->attenuation / (fx_ssao->distance_max * fx_ssao->distance_max);
			float ssao_params[4] = {fx_ssao->distance_max, fx_ssao->factor, attenuation, 0.0f};
			float sample_params[3];

			sample_params[0] = fx->ssao_sample_count_cache;
			/* multiplier so we tile the random texture on screen */
			sample_params[1] = fx->gbuffer_dim[0] / 64.0;
			sample_params[2] = fx->gbuffer_dim[1] / 64.0;

			ssao_params[3] = (passes_left == 1 && !ofs) ? dfdyfac[0] : dfdyfac[1];

			GPUSSAOShaderInterface *interface = GPU_shader_get_interface(ssao_shader);

			GPU_shader_bind(ssao_shader);

			GPU_shader_uniform_vector(ssao_shader, interface->ssao_uniform, 4, 1, ssao_params);
			GPU_shader_uniform_vector(ssao_shader, interface->ssao_color_uniform, 4, 1, fx_ssao->color);
			GPU_shader_uniform_vector(ssao_shader, interface->viewvecs_uniform, 4, 3, viewvecs[0]);
			GPU_shader_uniform_vector(ssao_shader, interface->ssao_sample_params_uniform, 3, 1, sample_params);

			GPU_texture_bind(src, numslots++);
			GPU_shader_uniform_texture(ssao_shader, interface->color_uniform, src);

			GPU_texture_bind(fx->depth_buffer, numslots++);
			GPU_texture_filter_mode(fx->depth_buffer, false, true, false);
			GPU_shader_uniform_texture(ssao_shader, interface->depth_uniform, fx->depth_buffer);

			GPU_texture_bind(fx->jitter_buffer, numslots++);
			GPU_shader_uniform_texture(ssao_shader, interface->ssao_jitter_uniform, fx->jitter_buffer);

			GPU_texture_bind(fx->ssao_spiral_samples_tex, numslots++);
			GPU_shader_uniform_texture(ssao_shader, interface->ssao_concentric_tex, fx->ssao_spiral_samples_tex);

			/* draw */
			gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

			glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

			/* disable bindings */
			GPU_texture_unbind(src);
			GPU_texture_filter_mode(fx->depth_buffer, true, false, false);
			GPU_texture_unbind(fx->depth_buffer);
			GPU_texture_unbind(fx->jitter_buffer);
			GPU_texture_unbind(fx->ssao_spiral_samples_tex);

			/* may not be attached, in that case this just returns */
			if (target) {
				GPU_framebuffer_texture_detach(target);
				if (ofs) {
					GPU_offscreen_bind(ofs, false);
				}
				else {
					GPU_framebuffer_restore();
				}
			}

			/* swap here, after src/target have been unbound */
			SWAP(GPUTexture *, target, src);
			numslots = 0;
		}
	}

	/* bloom pass */
	if (fx->sce_effects & SCENE_FX_FLAG_BLOOM) {
		GPUShader *bloom_shader;
		bloom_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_BLOOM, is_persp);
		if (bloom_shader) {
			const GPUBLOOMSettings *fx_bloom = scenefx.bloom;
			/* adjust attenuation to be scale invariant */
			float bloom_params[4] = {fx_bloom->intensity, fx_bloom->threshold};

			GPUBLOOMShaderInterface *interface = GPU_shader_get_interface(bloom_shader);

			GPU_shader_bind(bloom_shader);

			GPU_texture_bind(src, numslots++);
			GPU_shader_uniform_texture(bloom_shader, interface->color_uniform, src);

			GPU_shader_uniform_vector(bloom_shader, interface->bloom_uniform, 4, 1, bloom_params);

			/* draw */
			gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

			glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

			/* disable bindings */
			GPU_texture_unbind(src);

			/* may not be attached, in that case this just returns */
			if (target) {
				GPU_framebuffer_texture_detach(target);
				if (ofs) {
					GPU_offscreen_bind(ofs, false);
				}
				else {
					GPU_framebuffer_restore();
				}
			}

			/* swap here, after src/target have been unbound */
			SWAP(GPUTexture *, target, src);
			numslots = 0;
		}
	}

	/* tonemap pass */
	if (fx->sce_effects & SCENE_FX_FLAG_TONEMAP) {
		GPUShader *tonemap_shader;
		tonemap_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_TONEMAP, is_persp);
		if (tonemap_shader) {
			const GPUTONEMAPSettings *fx_tonemap = scenefx.tonemap;
			float params[3] = {fx_tonemap->shadertype, fx_tonemap->exposure, fx_tonemap->gamma};

			GPUTONEMAPShaderInterface *interface = GPU_shader_get_interface(tonemap_shader);

			GPU_shader_bind(tonemap_shader);

			GPU_texture_bind(src, numslots++);
			GPU_shader_uniform_texture(tonemap_shader, interface->color_uniform, src);

			GPU_shader_uniform_vector(tonemap_shader, interface->tonemapParams_uniform, 3, 1, params);

			/* draw */
			gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

			glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

			/* disable bindings */
			GPU_texture_unbind(src);

			/* may not be attached, in that case this just returns */
			if (target) {
				GPU_framebuffer_texture_detach(target);
				if (ofs) {
					GPU_offscreen_bind(ofs, false);
				}
				else {
					GPU_framebuffer_restore();
				}
			}

			/* swap here, after src/target have been unbound */
			SWAP(GPUTexture *, target, src);
			numslots = 0;
		}
	}

	/* light scatter pass */
	if (fx->sce_effects & SCENE_FX_FLAG_LIGHTSCATTER) {
		GPUShader *scatter_shader;
		scatter_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_LIGHTSCATTER, is_persp);
		if (scatter_shader) {
			const GPULIGHTSCATTERSettings *fx_scatter = scenefx.scatter;
			float sunpos[3] = {0.5f, 0.0f, 0.0f};

			// Calculate Sun Position Based on the screen
			if (scene->world_sun) {
				Object *sun = scene->world_sun;
				
				copy_v3_v3(sunpos, sun->obmat[2]);

				//printf("X: %f Y: %f \n", sunpos[0], sunpos[1]);
			}

			float params[4] = {fx_scatter->intensity, fx_scatter->threshold, fx_scatter->stepsize, fx_scatter->stepmax};

			GPULIGHTSCATTERShaderInterface *interface = GPU_shader_get_interface(scatter_shader);

			GPU_shader_bind(scatter_shader);

			GPU_texture_bind(src, numslots++);
			GPU_shader_uniform_texture(scatter_shader, interface->color_uniform, src);

			GPU_texture_bind(fx->depth_buffer, numslots++);
			GPU_texture_filter_mode(fx->depth_buffer, false, true, false);
			GPU_shader_uniform_texture(scatter_shader, interface->depth_uniform, fx->depth_buffer);

			GPU_shader_uniform_vector(scatter_shader, interface->sunpos_uniform, 3, 1, sunpos);
			GPU_shader_uniform_vector(scatter_shader, interface->scatter_params_uniform, 4, 1, params);

			/* draw */
			gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

			glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

			/* disable bindings */
			GPU_texture_unbind(src);

			/* may not be attached, in that case this just returns */
			if (target) {
				GPU_framebuffer_texture_detach(target);
				if (ofs) {
					GPU_offscreen_bind(ofs, false);
				}
				else {
					GPU_framebuffer_restore();
				}
			}

			/* swap here, after src/target have been unbound */
			SWAP(GPUTexture *, target, src);
			numslots = 0;
		}
	}

	/* ssr pass */
	if (fx->sce_effects & SCENE_FX_FLAG_SSR) {
		GPUShader *ssr_shader;
		ssr_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_SSR, is_persp);
		if (ssr_shader) {
			const GPUSSRSettings *fx_ssr = scenefx.ssr;
			float ssr_params[4] = {fx_ssr->step_max, fx_ssr->max_distance, fx_ssr->roughness, fx_ssr->bias};
			float ssr_extra_params[2];

			ssr_extra_params[0] = fx_ssr->max_distance;
			ssr_extra_params[1] = (passes_left == 1 && !ofs) ? dfdyfac[0] : dfdyfac[1];

			GPUSSRShaderInterface *interface = GPU_shader_get_interface(ssr_shader);

			GPU_shader_bind(ssr_shader);

			GPU_shader_uniform_vector(ssr_shader, interface->ssr_uniform, 4, 1, ssr_params);
			GPU_shader_uniform_vector(ssr_shader, interface->viewvecs_uniform, 4, 3, viewvecs[0]);

			GPU_texture_bind(src, numslots++);
			GPU_shader_uniform_texture(ssr_shader, interface->color_uniform, src);

			GPU_texture_bind(fx->depth_buffer, numslots++);
			GPU_texture_filter_mode(fx->depth_buffer, false, true, false);
			GPU_shader_uniform_texture(ssr_shader, interface->depth_uniform, fx->depth_buffer);

			GPU_texture_bind(fx->jitter_buffer, numslots++);
			GPU_shader_uniform_texture(ssr_shader, interface->ssr_jitter_uniform, fx->jitter_buffer);

			/* draw */
			gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

			glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

			/* disable bindings */
			GPU_texture_unbind(src);
			GPU_texture_filter_mode(fx->depth_buffer, true, false, false);
			GPU_texture_unbind(fx->depth_buffer);
			GPU_texture_unbind(fx->jitter_buffer);

			/* may not be attached, in that case this just returns */
			if (target) {
				GPU_framebuffer_texture_detach(target);
				if (ofs) {
					GPU_offscreen_bind(ofs, false);
				}
				else {
					GPU_framebuffer_restore();
				}
			}

			/* swap here, after src/target have been unbound */
			SWAP(GPUTexture *, target, src);
			numslots = 0;
		}
	}

	/* fxaa pass */
	if (fx->sce_effects & SCENE_FX_FLAG_FXAA) {
		GPUShader *fxaa_shader;
		fxaa_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_FXAA, is_persp);
		if (fxaa_shader) {
			GPUFXAAShaderInterface *interface = GPU_shader_get_interface(fxaa_shader);
			float viewport_size[2] = {fx->viewsize_w, fx->viewsize_h};
			float fxaa_params[4] = {scenefx.fxaa_edge_threshold, scenefx.fxaa_edge_threshold_min,
			                        scenefx.fxaa_subpix, (float)scenefx.fxaa_search_steps};

			/* A scene that never got the settings has zeros; use the defaults. */
			if (scenefx.fxaa_search_steps <= 0) {
				fxaa_params[0] = SCENE_FX_FXAA_EDGE_THRESHOLD;
				fxaa_params[1] = SCENE_FX_FXAA_EDGE_THRESHOLD_MIN;
				fxaa_params[2] = SCENE_FX_FXAA_SUBPIX;
				fxaa_params[3] = SCENE_FX_FXAA_SEARCH_STEPS;
			}

			GPU_shader_bind(fxaa_shader);

			GPU_texture_bind(src, numslots++);
			GPU_shader_uniform_texture(fxaa_shader, interface->color_uniform, src);
			GPU_shader_uniform_vector(fxaa_shader, interface->viewport_size_uniform, 2, 1, viewport_size);
			GPU_shader_uniform_vector(fxaa_shader, interface->fxaa_params_uniform, 4, 1, fxaa_params);

			/* draw */
			gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

			glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

			/* disable bindings */
			GPU_texture_unbind(src);

			/* may not be attached, in that case this just returns */
			if (target) {
				GPU_framebuffer_texture_detach(target);
				if (ofs) {
					GPU_offscreen_bind(ofs, false);
				}
				else {
					GPU_framebuffer_restore();
				}
			}

			/* swap here, after src/target have been unbound */
			SWAP(GPUTexture *, target, src);
			numslots = 0;
		}
	}

	/* lens flare pass, mirrors World > Weather > Lens Flare from the in-game filter */
	if (fx->sce_effects & SCENE_FX_FLAG_LENSFLARE) {
		GPUShader *lensflare_shader;
		lensflare_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_LENSFLARE, is_persp);
		if (lensflare_shader && scene->world) {
			float sunpos[3] = {0.5f, 0.0f, 0.0f};

			/* Same convention as the light scatter pass above: world-space direction
			 * of the World Sun object, projected to screen space in the shader. */
			if (scene->world_sun) {
				Object *sun = scene->world_sun;
				copy_v3_v3(sunpos, sun->obmat[2]);
			}

			/* Not animated (timer = 0): the 3D View isn't redrawn every frame outside
			 * Play/animation playback, so a moving flicker would just look stuck between
			 * redraws. Position, scale and sun occlusion still update live. */
			float flare_params[4] = {scene->world->flare_scale, scene->world->flare_intensity, 0.0f, 0.0f};
			float viewport_size[2] = {fx->viewsize_w, fx->viewsize_h};

			GPULENSFLAREShaderInterface *interface = GPU_shader_get_interface(lensflare_shader);

			GPU_shader_bind(lensflare_shader);

			GPU_texture_bind(src, numslots++);
			GPU_shader_uniform_texture(lensflare_shader, interface->color_uniform, src);

			GPU_texture_bind(fx->depth_buffer, numslots++);
			GPU_texture_filter_mode(fx->depth_buffer, false, true, false);
			GPU_shader_uniform_texture(lensflare_shader, interface->depth_uniform, fx->depth_buffer);

			GPU_shader_uniform_vector(lensflare_shader, interface->sunpos_uniform, 3, 1, sunpos);
			GPU_shader_uniform_vector(lensflare_shader, interface->flare_params_uniform, 4, 1, flare_params);
			GPU_shader_uniform_vector(lensflare_shader, interface->viewport_size_uniform, 2, 1, viewport_size);

			/* draw */
			gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

			glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

			/* disable bindings */
			GPU_texture_unbind(src);
			GPU_texture_filter_mode(fx->depth_buffer, true, false, false);
			GPU_texture_unbind(fx->depth_buffer);

			/* may not be attached, in that case this just returns */
			if (target) {
				GPU_framebuffer_texture_detach(target);
				if (ofs) {
					GPU_offscreen_bind(ofs, false);
				}
				else {
					GPU_framebuffer_restore();
				}
			}

			/* swap here, after src/target have been unbound */
			SWAP(GPUTexture *, target, src);
			numslots = 0;
		}
	}

	/* rain pass, mirrors World > Weather > Rain from the in-game filter (RAS_Rain2DFilter.glsl) */
	if (fx->sce_effects & SCENE_FX_FLAG_RAIN) {
		GPUShader *rain_shader;
		rain_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_RAIN, is_persp);
		if (rain_shader && scene->world) {
			World *world = scene->world;

			/* Real elapsed time, not frame time: the viewport isn't redrawn every
			 * frame outside Play/animation playback, so scene->r.cfra-based time
			 * would look frozen. ED_view3d_realtime_viewport_update() (triggered
			 * from rna_World_draw_update) keeps a timer redrawing the viewport
			 * while rain/clouds speed is non-zero, so this keeps advancing. */
			float rain_params1[4] = {world->rain_intensity, world->rain_speed, world->rain_wind, world->rain_darken};
			float rain_params2[4] = {
			    world->rain_ripple, (float)fmod(PIL_check_seconds_timer(), 10000.0),
			    (world->weather_flag & WO_WEATHER_RAIN_DROPLETS) ? 1.0f : 0.0f,
			    (world->weather_flag & WO_WEATHER_RAIN_RIPPLE) ? 1.0f : 0.0f};
			float rain_params3[4] = {world->rain_density, world->rain_ripple_distance, world->rain_ripple_min_up, world->rain_splash_distance};
			float rain_params4[4] = {
			    (world->weather_flag & WO_WEATHER_RAIN_SPLASH) ? 1.0f : 0.0f,
			    world->rain_splash_size, world->rain_splash_rate, world->rain_splash_intensity};
			float rain_streak_width = (world->rain_streak_width > 0.0f) ? world->rain_streak_width : 1.0f;
			float rain_ripple_normal = (world->rain_ripple_normal > 0.0f) ? world->rain_ripple_normal : 1.0f;
			float rain_params5[4] = {world->rain_ripple_size, world->rain_ripple_rate,
			                         world->rain_splash_normal, world->rain_splash_min_up};
			float rain_lightning[4] = {0.0f, 0.0f, 0.5f, 0.5f};
			unsigned int lightning_seed;
			if ((world->weather_flag & WO_WEATHER_RAIN_LIGHTNING) &&
			    BKE_rain_lightning_eval(world->rain_lightning_rate, world->rain_lightning_intensity,
			                            PIL_check_seconds_timer(), &rain_lightning[0], &rain_lightning[1],
			                            &lightning_seed) &&
			    rain_lightning[1] > 0.0f)
			{
				/* Bolt center on screen, for the halo in the sky (same bolt as view3d_rain.c). */
				RainLightningBolt bolt;
				float viewinv[4][4], persmat[4][4], co[4];
				const float clip_end = is_persp ? projmat[3][2] / (projmat[2][2] + 1.0f) : 0.0f;
				invert_m4_m4(viewinv, viewmat);
				BKE_rain_lightning_view_bolt(lightning_seed, viewinv, clip_end, world->rain_lightning_distance,
				                             world->rain_lightning_width,
				                             (world->weather_flag & WO_WEATHER_RAIN_LIGHTNING_SIDE) != 0, &bolt);
				mul_m4_m4m4(persmat, projmat, viewmat);
				copy_v3_v3(co, bolt.center);
				co[3] = 1.0f;
				mul_m4_v4(persmat, co);
				if (co[3] > 0.0f) {
					rain_lightning[2] = co[0] / co[3] * 0.5f + 0.5f;
					rain_lightning[3] = co[1] / co[3] * 0.5f + 0.5f;
				}
				else {
					rain_lightning[1] = 0.0f;
				}
			}
			else {
				rain_lightning[1] = 0.0f;
			}
			float rain_style = (world->rain_style == WO_RAIN_STYLE_VOLUMETRIC) ? 1.0f : 0.0f;
			/* Volumetric fall offset, wrapped in double: the timer is the PC uptime, and
			 * time * speed * 500 in the shader's float lost every fraction after a few hours,
			 * so the streaks' fract() stayed at 0 and the rain vanished. */
			float rain_fall_phase = (float)fmod(PIL_check_seconds_timer() * world->rain_speed * 500.0, 20480.0);
			float rain_puddle1[4] = {(world->weather_flag & WO_WEATHER_RAIN_PUDDLES) ?
			                         1.0f + ((world->weather_flag & WO_WEATHER_RAIN_RIPPLE_PUDDLE) ? 1.0f : 0.0f) +
			                         ((world->weather_flag & WO_WEATHER_RAIN_SPLASH_PUDDLE) ? 2.0f : 0.0f) : 0.0f,
			                         world->rain_puddle_amount, world->rain_puddle_size, world->rain_puddle_darkness};
			float rain_puddle2[4] = {world->rain_puddle_reflection, world->rain_puddle_distance,
			                         world->rain_puddle_min_up, (world->weather_flag & WO_WEATHER_RAIN_PUDDLE_SSR) ? 1.0f : 0.0f};
			float rain_sky_horizon[3] = {world->horr, world->horg, world->horb};
			float rain_sky_zenith[3] = {world->zenr, world->zeng, world->zenb};

			GPURAINShaderInterface *interface = GPU_shader_get_interface(rain_shader);

			GPU_shader_bind(rain_shader);

			GPU_texture_bind(src, numslots++);
			GPU_shader_uniform_texture(rain_shader, interface->color_uniform, src);

			GPU_texture_bind(fx->depth_buffer, numslots++);
			GPU_texture_filter_mode(fx->depth_buffer, false, true, false);
			GPU_shader_uniform_texture(rain_shader, interface->depth_uniform, fx->depth_buffer);

			GPU_shader_uniform_vector(rain_shader, interface->rain_params1_uniform, 4, 1, rain_params1);
			GPU_shader_uniform_vector(rain_shader, interface->rain_params2_uniform, 4, 1, rain_params2);
			GPU_shader_uniform_vector(rain_shader, interface->rain_params3_uniform, 4, 1, rain_params3);
			GPU_shader_uniform_vector(rain_shader, interface->rain_color_uniform, 3, 1, world->rain_color);
			GPU_shader_uniform_vector(rain_shader, interface->rain_style_uniform, 1, 1, &rain_style);
			GPU_shader_uniform_vector(rain_shader, interface->rain_fall_phase_uniform, 1, 1, &rain_fall_phase);
			GPU_shader_uniform_vector(rain_shader, interface->rain_params4_uniform, 4, 1, rain_params4);
			GPU_shader_uniform_vector(rain_shader, interface->rain_lightning_uniform, 4, 1, rain_lightning);
			GPU_shader_uniform_vector(rain_shader, interface->rain_streak_width_uniform, 1, 1, &rain_streak_width);
			GPU_shader_uniform_vector(rain_shader, interface->rain_ripple_normal_uniform, 1, 1, &rain_ripple_normal);
			GPU_shader_uniform_vector(rain_shader, interface->rain_params5_uniform, 4, 1, rain_params5);
			GPU_shader_uniform_vector(rain_shader, interface->rain_puddle1_uniform, 4, 1, rain_puddle1);
			GPU_shader_uniform_vector(rain_shader, interface->rain_puddle2_uniform, 4, 1, rain_puddle2);
			GPU_shader_uniform_vector(rain_shader, interface->rain_sky_horizon_uniform, 3, 1, rain_sky_horizon);
			GPU_shader_uniform_vector(rain_shader, interface->rain_sky_zenith_uniform, 3, 1, rain_sky_zenith);

			/* draw */
			gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

			glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

			/* disable bindings */
			GPU_texture_unbind(src);
			GPU_texture_filter_mode(fx->depth_buffer, true, false, false);
			GPU_texture_unbind(fx->depth_buffer);

			/* may not be attached, in that case this just returns */
			if (target) {
				GPU_framebuffer_texture_detach(target);
				if (ofs) {
					GPU_offscreen_bind(ofs, false);
				}
				else {
					GPU_framebuffer_restore();
				}
			}

			/* swap here, after src/target have been unbound */
			SWAP(GPUTexture *, target, src);
			numslots = 0;
		}
	}

	/* clouds pass, mirrors World > Weather > Clouds from the in-game filter (RAS_Clouds2DFilter.glsl) */
	if (fx->sce_effects & SCENE_FX_FLAG_CLOUDS) {
		GPUShader *clouds_shader;
		clouds_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_CLOUDS, is_persp);
		if (clouds_shader && scene->world) {
			World *world = scene->world;

			/* Real elapsed time, same reasoning as the rain pass above. */
			float clouds_params[4] = {
			    world->cloud_coverage, world->cloud_scale, world->cloud_speed,
			    (float)fmod(PIL_check_seconds_timer(), 10000.0)};

			GPUCLOUDSShaderInterface *interface = GPU_shader_get_interface(clouds_shader);

			GPU_shader_bind(clouds_shader);

			GPU_texture_bind(src, numslots++);
			GPU_shader_uniform_texture(clouds_shader, interface->color_uniform, src);

			GPU_texture_bind(fx->depth_buffer, numslots++);
			GPU_texture_filter_mode(fx->depth_buffer, false, true, false);
			GPU_shader_uniform_texture(clouds_shader, interface->depth_uniform, fx->depth_buffer);

			GPU_shader_uniform_vector(clouds_shader, interface->clouds_params_uniform, 4, 1, clouds_params);
			GPU_shader_uniform_vector(clouds_shader, interface->clouds_color_uniform, 3, 1, world->cloud_color);
			/* 1: Clouds, 2: Sky Layers (each only when not hidden in the viewport) */
			const float clouds_mask =
			        (float)(((world->weather_flag & ~world->weather_editor_hide & WO_WEATHER_CLOUDS) ? 1 : 0) +
			                (((world->sky_layer_flag & (WO_SKY_LAYERS_ENABLE | WO_SKY_LAYERS_EDITOR_HIDE)) ==
			                  WO_SKY_LAYERS_ENABLE) ? 2 : 0) +
			                (((world->vcloud_flag & (WO_VCLOUDS_ENABLE | WO_VCLOUDS_EDITOR_HIDE)) ==
			                  WO_VCLOUDS_ENABLE) ? 4 : 0));
			const float sky_layers_params[4] = {
			    world->sky_layer_coverage, world->sky_layer_scale, world->sky_layer_speed, clouds_params[3]};
			GPU_shader_uniform_vector(clouds_shader, interface->clouds_mask_uniform, 1, 1, &clouds_mask);
			GPU_shader_uniform_vector(clouds_shader, interface->sky_layers_params_uniform, 4, 1, sky_layers_params);
			GPU_shader_uniform_vector(clouds_shader, interface->sky_layers_color_uniform, 3, 1, world->sky_layer_color);
			const float clouds_quality[3] = {
			    (float)world->cloud_detail, (float)world->sky_layer_detail, world->sky_layer_relief};
			GPU_shader_uniform_vector(clouds_shader, interface->clouds_quality_uniform, 3, 1, clouds_quality);

			/* Volumetric Clouds (Stage 1 scaffolding): flat shading reusing the same FBM. */
			const float vclouds_params1[4] = {
			    world->vcloud_coverage, world->vcloud_scale, world->vcloud_speed, clouds_params[3]};
			const float vclouds_params2[4] = {
			    world->vcloud_altitude, world->vcloud_thickness, world->vcloud_density, world->vcloud_detail_scale};
			const float vclouds_params3[4] = {
			    world->vcloud_silver_intensity, (float)world->vcloud_quality,
			    (world->vcloud_flag & WO_VCLOUDS_SHADOW_ENABLE) ? 1.0f : 0.0f, world->vcloud_shadow_strength};
			GPU_shader_uniform_vector(clouds_shader, interface->vclouds_params1_uniform, 4, 1, vclouds_params1);
			GPU_shader_uniform_vector(clouds_shader, interface->vclouds_params2_uniform, 4, 1, vclouds_params2);
			GPU_shader_uniform_vector(clouds_shader, interface->vclouds_params3_uniform, 4, 1, vclouds_params3);
			GPU_shader_uniform_vector(clouds_shader, interface->vclouds_color_uniform, 3, 1, world->vcloud_color);

			/* Sun direction for the volumetric raymarch (self-shadow/silver lining), same
			 * source object used by the light scattering/lens flare passes above. */
			{
				float vclouds_sundir[3] = {0.0f, 0.0f, 1.0f};
				if (scene->world_sun) {
					copy_v3_v3(vclouds_sundir, scene->world_sun->obmat[2]);
				}
				GPU_shader_uniform_vector(clouds_shader, interface->vclouds_sundir_uniform, 3, 1, vclouds_sundir);
			}

			/* Temporal reuse (Volumetric Clouds only): needs glCopyImageSubData for the depth copy. */
			const bool use_history = (world->vcloud_flag & (WO_VCLOUDS_ENABLE | WO_VCLOUDS_EDITOR_HIDE)) ==
			                         WO_VCLOUDS_ENABLE &&
			                         (GLEW_VERSION_4_3 || GLEW_ARB_copy_image);
			float cur_persmat[4][4];
			mul_m4_m4m4(cur_persmat, projmat, viewmat);
			{
				/* In the 3D View the grid, outlines and gizmos are drawn into the color buffer without
				 * depth, so the history holds them as "sky": reprojecting it while the view moves
				 * smears them into trails. Only reuse while the view is still (clouds still animate). */
				const bool valid = use_history && fx->cloud_history_valid &&
				                   equals_m4m4(cur_persmat, fx->cloud_history_persmat);
				const float valid_f = valid ? 1.0f : 0.0f;
				const float frame_f = (float)(fx->cloud_history_frame & 3);
				if (valid) {
					glActiveTexture(GL_TEXTURE6);
					glBindTexture(GL_TEXTURE_2D, fx->cloud_history);
					glActiveTexture(GL_TEXTURE7);
					glBindTexture(GL_TEXTURE_2D, fx->cloud_history_depth);
					glActiveTexture(GL_TEXTURE0);
					glUniform1i(interface->history_uniform, 6);
					glUniform1i(interface->history_depth_uniform, 7);
				}
				GPU_shader_uniform_vector(clouds_shader, interface->history_valid_uniform, 1, 1, &valid_f);
				GPU_shader_uniform_vector(clouds_shader, interface->frame_uniform, 1, 1, &frame_f);
				GPU_shader_uniform_vector(clouds_shader, interface->history_viewproj_uniform, 16, 1,
				                          valid ? (float *)fx->cloud_history_persmat : (float *)cur_persmat);
			}

			/* draw */
			gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

			glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

			if (use_history) {
				/* Copy the pass output (fx buffer or the window/offscreen, whichever is bound)
				 * and the depth for the next redraw. */
				int vp[4];
				glGetIntegerv(GL_VIEWPORT, vp);
				const int depth_w = GPU_texture_width(fx->depth_buffer);
				const int depth_h = GPU_texture_height(fx->depth_buffer);
				if (vp[2] != depth_w || vp[3] != depth_h) {
					fx->cloud_history_valid = false;
				}
				else {
					if (!fx->cloud_history || fx->cloud_history_w != vp[2] || fx->cloud_history_h != vp[3]) {
						if (!fx->cloud_history) {
							glGenTextures(1, &fx->cloud_history);
							glGenTextures(1, &fx->cloud_history_depth);
						}
						glBindTexture(GL_TEXTURE_2D, fx->cloud_history);
						glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA16F, vp[2], vp[3], 0, GL_RGBA, GL_FLOAT, NULL);
						glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
						glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
						glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
						glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
						/* glCopyImageSubData needs the exact same internal format as the source. */
						GLint depth_format = GL_DEPTH_COMPONENT24;
						glBindTexture(GL_TEXTURE_2D, GPU_texture_opengl_bindcode(fx->depth_buffer));
						glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_INTERNAL_FORMAT, &depth_format);
						glBindTexture(GL_TEXTURE_2D, fx->cloud_history_depth);
						glTexImage2D(GL_TEXTURE_2D, 0, depth_format, vp[2], vp[3], 0, GL_DEPTH_COMPONENT, GL_FLOAT, NULL);
						glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
						glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
						glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
						glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
						glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_MODE, GL_NONE);
						fx->cloud_history_w = vp[2];
						fx->cloud_history_h = vp[3];
					}
					glBindTexture(GL_TEXTURE_2D, fx->cloud_history);
					glCopyTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, vp[0], vp[1], vp[2], vp[3]);
					glBindTexture(GL_TEXTURE_2D, 0);
					glCopyImageSubData(GPU_texture_opengl_bindcode(fx->depth_buffer), GL_TEXTURE_2D, 0, 0, 0, 0,
					                   fx->cloud_history_depth, GL_TEXTURE_2D, 0, 0, 0, 0, vp[2], vp[3], 1);
					copy_m4_m4(fx->cloud_history_persmat, cur_persmat);
					fx->cloud_history_valid = true;
					fx->cloud_history_frame++;
				}
			}
			else {
				fx->cloud_history_valid = false;
			}
			if (use_history) {
				glActiveTexture(GL_TEXTURE6);
				glBindTexture(GL_TEXTURE_2D, 0);
				glActiveTexture(GL_TEXTURE7);
				glBindTexture(GL_TEXTURE_2D, 0);
				glActiveTexture(GL_TEXTURE0);
			}

			/* disable bindings */
			GPU_texture_unbind(src);
			GPU_texture_filter_mode(fx->depth_buffer, true, false, false);
			GPU_texture_unbind(fx->depth_buffer);

			/* may not be attached, in that case this just returns */
			if (target) {
				GPU_framebuffer_texture_detach(target);
				if (ofs) {
					GPU_offscreen_bind(ofs, false);
				}
				else {
					GPU_framebuffer_restore();
				}
			}

			/* swap here, after src/target have been unbound */
			SWAP(GPUTexture *, target, src);
			numslots = 0;
		}
	}

	/* Volumetric Fog pass, mirrors the in-game filter (RAS_VolumetricFog2DFilter.glsl) */
	if (fx->sce_effects & SCENE_FX_FLAG_VFOG) {
		GPUShader *vfog_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_VFOG, is_persp);
		if (vfog_shader && scene->world) {
			GPUVFOGShaderInterface *interface = GPU_shader_get_interface(vfog_shader);
			float data[GPU_VFOG_DATA_VEC4][4], mats[7][4][4], viewinv[4][4];
			unsigned int shadow_tex[3];
			invert_m4_m4(viewinv, viewmat);
			gpu_vfog_fill(scene, scene->world, viewinv[3], data, mats, shadow_tex);
			const float frame_f = (float)(fx->vfog_frame++ & 63);

			GPU_shader_bind(vfog_shader);

			GPU_texture_bind(src, numslots++);
			GPU_shader_uniform_texture(vfog_shader, interface->color_uniform, src);

			GPU_texture_bind(fx->depth_buffer, numslots++);
			GPU_texture_filter_mode(fx->depth_buffer, false, true, false);
			GPU_shader_uniform_texture(vfog_shader, interface->depth_uniform, fx->depth_buffer);

			GPU_shader_uniform_vector(vfog_shader, interface->data_uniform, 4, GPU_VFOG_DATA_VEC4, (float *)data);
			glUniformMatrix4fv(interface->mats_uniform, 7, GL_FALSE, (float *)mats);
			GPU_shader_uniform_vector(vfog_shader, interface->frame_uniform, 1, 1, &frame_f);
			/* Spot shadow maps on units 6/7, Sun on 8 (free: the clouds history is unbound after its pass). */
			for (int i = 0; i < 3; i++) {
				glActiveTexture(GL_TEXTURE6 + i);
				glBindTexture(GL_TEXTURE_2D, shadow_tex[i]);
			}
			glActiveTexture(GL_TEXTURE0);
			glUniform1i(interface->shadow0_uniform, 6);
			glUniform1i(interface->shadow1_uniform, 7);
			glUniform1i(interface->shadow2_uniform, 8);

			/* draw */
			gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

			glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

			for (int i = 0; i < 3; i++) {
				glActiveTexture(GL_TEXTURE6 + i);
				glBindTexture(GL_TEXTURE_2D, 0);
			}
			glActiveTexture(GL_TEXTURE0);

			/* disable bindings */
			GPU_texture_unbind(src);
			GPU_texture_filter_mode(fx->depth_buffer, true, false, false);
			GPU_texture_unbind(fx->depth_buffer);

			/* may not be attached, in that case this just returns */
			if (target) {
				GPU_framebuffer_texture_detach(target);
				if (ofs) {
					GPU_offscreen_bind(ofs, false);
				}
				else {
					GPU_framebuffer_restore();
				}
			}

			/* swap here, after src/target have been unbound */
			SWAP(GPUTexture *, target, src);
			numslots = 0;
		}
	}

	/* film grain pass, same noise as the in-game camera lens pass */
	if (fx->sce_effects & SCENE_FX_FLAG_GRAIN) {
		GPUShader *grain_shader;
		grain_shader = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_GRAIN, is_persp);
		if (grain_shader) {
			GPUGRAINShaderInterface *interface = GPU_shader_get_interface(grain_shader);
			/* Seed from real time: the viewport isn't redrawn every frame, so the grain
			 * just changes on each redraw. Kept small for float precision. */
			float grain_params[4] = {scenefx.grain_strength,
			                         (float)((int)(PIL_check_seconds_timer() * 60.0) % 1000) * 0.05f,
			                         0.0f, 0.0f};

			GPU_shader_bind(grain_shader);

			GPU_texture_bind(src, numslots++);
			GPU_shader_uniform_texture(grain_shader, interface->color_uniform, src);
			GPU_shader_uniform_vector(grain_shader, interface->grain_params_uniform, 4, 1, grain_params);

			/* draw */
			gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

			glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

			/* disable bindings */
			GPU_texture_unbind(src);

			/* may not be attached, in that case this just returns */
			if (target) {
				GPU_framebuffer_texture_detach(target);
				if (ofs) {
					GPU_offscreen_bind(ofs, false);
				}
				else {
					GPU_framebuffer_restore();
				}
			}

			/* swap here, after src/target have been unbound */
			SWAP(GPUTexture *, target, src);
			numslots = 0;
		}
	}

	/* second pass, dof */
	if (fx->effects & GPU_FX_FLAG_DOF) {
		const GPUDOFSettings *fx_dof = fx->settings.dof;
		float dof_params[4];
		float scale = scene->unit.system ? scene->unit.scale_length : 1.0f;
		/* this is factor that converts to the scene scale. focal length and sensor are expressed in mm
		 * unit.scale_length is how many meters per blender unit we have. We want to convert to blender units though
		 * because the shader reads coordinates in world space, which is in blender units.
		 * Note however that focus_distance is already in blender units and shall not be scaled here (see T48157). */
		float scale_camera = 0.001f / scale;
		/* we want radius here for the aperture number  */
		float aperture = 0.5f * scale_camera * fx_dof->focal_length / fx_dof->fstop;

		dof_params[0] = aperture * fabsf(scale_camera * fx_dof->focal_length /
		                                 (fx_dof->focus_distance - scale_camera * fx_dof->focal_length));
		dof_params[1] = fx_dof->focus_distance;
		dof_params[2] = fx->gbuffer_dim[0] / (scale_camera * fx_dof->sensor);
		dof_params[3] = fx_dof->num_blades;

		if (fx->dof_high_quality) {
			GPUShader *dof_shader_pass1, *dof_shader_pass2, *dof_shader_pass3;

			/* custom shaders close to the effect described in CryEngine 3 Graphics Gems */
			dof_shader_pass1 = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_DEPTH_OF_FIELD_HQ_PASS_ONE, is_persp);
			dof_shader_pass2 = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_DEPTH_OF_FIELD_HQ_PASS_TWO, is_persp);
			dof_shader_pass3 = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_DEPTH_OF_FIELD_HQ_PASS_THREE, is_persp);

			/* error occured, restore framebuffers and return */
			if (!(dof_shader_pass1 && dof_shader_pass2 && dof_shader_pass3)) {
				GPU_framebuffer_texture_unbind(fx->gbuffer, NULL);
				GPU_framebuffer_restore();
				glDisableClientState(GL_VERTEX_ARRAY);
				glDisableClientState(GL_TEXTURE_COORD_ARRAY);

				GPU_shader_unbind();
				glBindBuffer(GL_ARRAY_BUFFER, 0);
				return false;
			}

			/* pass first, downsample the color buffer to near/far targets and calculate coc texture */
			{
				float invrendertargetdim[2] = {1.0f / fx->dof_downsampled_w, 1.0f / fx->dof_downsampled_h};

				GPUDOFHQPassOneInterface *interface = GPU_shader_get_interface(dof_shader_pass1);

				GPU_shader_bind(dof_shader_pass1);

				GPU_shader_uniform_vector(dof_shader_pass1, interface->dof_uniform, 4, 1, dof_params);
				GPU_shader_uniform_vector(dof_shader_pass1, interface->invrendertargetdim_uniform, 2, 1, invrendertargetdim);
				GPU_shader_uniform_vector(dof_shader_pass1, interface->viewvecs_uniform, 4, 3, viewvecs[0]);

				GPU_shader_uniform_vector(dof_shader_pass1, interface->invrendertargetdim_uniform, 2, 1, invrendertargetdim);

				GPU_texture_bind(fx->depth_buffer, numslots++);
				GPU_texture_filter_mode(fx->depth_buffer, false, false, false);
				GPU_shader_uniform_texture(dof_shader_pass1, interface->depth_uniform, fx->depth_buffer);

				GPU_texture_bind(src, numslots++);
				/* disable filtering for the texture so custom downsample can do the right thing */
				GPU_texture_filter_mode(src, false, false, false);
				GPU_shader_uniform_texture(dof_shader_pass2, interface->color_uniform, src);

				/* target is the downsampled coc buffer */
				GPU_framebuffer_texture_attach(fx->gbuffer, fx->dof_half_downsampled_near, 0, NULL);
				GPU_framebuffer_texture_attach(fx->gbuffer, fx->dof_half_downsampled_far, 1, NULL);
				GPU_framebuffer_texture_attach(fx->gbuffer, fx->dof_nearfar_coc, 2, NULL);
				/* binding takes care of setting the viewport to the downsampled size */
				GPU_framebuffer_slots_bind(fx->gbuffer, 0);

				GPU_framebuffer_check_valid(fx->gbuffer, NULL);

				glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
				/* disable bindings */
				GPU_texture_filter_mode(src, false, true, false);
				GPU_texture_unbind(src);
				GPU_texture_filter_mode(fx->depth_buffer, true, false, false);
				GPU_texture_unbind(fx->depth_buffer);

				GPU_framebuffer_texture_detach(fx->dof_half_downsampled_near);
				GPU_framebuffer_texture_detach(fx->dof_half_downsampled_far);
				GPU_framebuffer_texture_detach(fx->dof_nearfar_coc);
				GPU_framebuffer_texture_unbind(fx->gbuffer, fx->dof_half_downsampled_near);

				numslots = 0;
			}

			/* second pass, shoot quads for every pixel in the downsampled buffers, scaling according
			 * to circle of confusion */
			{
				int rendertargetdim[2] = {fx->dof_downsampled_w, fx->dof_downsampled_h};
				float selection[2] = {0.0f, 1.0f};

				GPUDOFHQPassTwoInterface *interface = GPU_shader_get_interface(dof_shader_pass2);

				GPU_shader_bind(dof_shader_pass2);

				GPU_shader_uniform_vector(dof_shader_pass2, interface->dof_uniform, 4, 1, dof_params);
				GPU_shader_uniform_vector_int(dof_shader_pass2, interface->rendertargetdim_uniform, 2, 1, rendertargetdim);
				GPU_shader_uniform_vector(dof_shader_pass2, interface->select_uniform, 2, 1, selection);

				GPU_texture_bind(fx->dof_nearfar_coc, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass2, interface->coc_uniform, fx->dof_nearfar_coc);

				GPU_texture_bind(fx->dof_half_downsampled_far, numslots++);
				GPU_texture_bind(fx->dof_half_downsampled_near, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass2, interface->color_uniform, fx->dof_half_downsampled_far);
				GPU_texture_filter_mode(fx->dof_half_downsampled_far, false, false, false);

				/* target is the downsampled coc buffer */
				GPU_framebuffer_texture_attach(fx->gbuffer, fx->dof_far_blur, 0, NULL);
				GPU_texture_bind_as_framebuffer(fx->dof_far_blur);

				glDisable(GL_DEPTH_TEST);
				glEnable(GL_BLEND);
				glBlendFunc(GL_ONE, GL_ONE);
				glPointSize(1.0f);
				/* have to clear the buffer unfortunately */
				glClearColor(0.0, 0.0, 0.0, 0.0);
				glClear(GL_COLOR_BUFFER_BIT);
				/* the draw call we all waited for, draw a point per pixel, scaled per circle of confusion */
				glDrawArraysInstancedARB(GL_POINTS, 0, 1, fx->dof_downsampled_w * fx->dof_downsampled_h);

				GPU_texture_unbind(fx->dof_half_downsampled_far);
				GPU_framebuffer_texture_detach(fx->dof_far_blur);

				GPU_shader_uniform_texture(dof_shader_pass2, interface->color_uniform, fx->dof_half_downsampled_near);
				GPU_texture_filter_mode(fx->dof_half_downsampled_near, false, false, false);

				selection[0] = 1.0f;
				selection[1] = 0.0f;

				GPU_shader_uniform_vector(dof_shader_pass2, interface->select_uniform, 2, 1, selection);

				GPU_framebuffer_texture_attach(fx->gbuffer, fx->dof_near_blur, 0, NULL);
				/* have to clear the buffer unfortunately */
				glClear(GL_COLOR_BUFFER_BIT);
				/* the draw call we all waited for, draw a point per pixel, scaled per circle of confusion */
				glDrawArraysInstancedARB(GL_POINTS, 0, 1, fx->dof_downsampled_w * fx->dof_downsampled_h);

				/* disable bindings */
				glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
				glDisable(GL_BLEND);

				GPU_framebuffer_texture_detach(fx->dof_near_blur);

				GPU_texture_unbind(fx->dof_half_downsampled_near);
				GPU_texture_unbind(fx->dof_nearfar_coc);

				GPU_framebuffer_texture_unbind(fx->gbuffer, fx->dof_far_blur);
			}

			/* third pass, accumulate the near/far blur fields */
			{
				float invrendertargetdim[2] = {1.0f / fx->dof_downsampled_w, 1.0f / fx->dof_downsampled_h};

				GPUDOFHQPassThreeInterface *interface = GPU_shader_get_interface(dof_shader_pass3);

				GPU_shader_bind(dof_shader_pass3);

				GPU_shader_uniform_vector(dof_shader_pass3, interface->dof_uniform, 4, 1, dof_params);

				GPU_shader_uniform_vector(dof_shader_pass3, interface->invrendertargetdim_uniform, 2, 1, invrendertargetdim);
				GPU_shader_uniform_vector(dof_shader_pass3, interface->viewvecs_uniform, 4, 3, viewvecs[0]);

				GPU_texture_bind(fx->dof_near_blur, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass3, interface->near_uniform, fx->dof_near_blur);
				GPU_texture_filter_mode(fx->dof_near_blur, false, true, false);

				GPU_texture_bind(fx->dof_far_blur, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass3, interface->far_uniform, fx->dof_far_blur);
				GPU_texture_filter_mode(fx->dof_far_blur, false, true, false);

				GPU_texture_bind(fx->depth_buffer, numslots++);
				GPU_texture_filter_mode(fx->depth_buffer, false, false, false);
				GPU_shader_uniform_texture(dof_shader_pass3, interface->depth_uniform, fx->depth_buffer);

				GPU_texture_bind(src, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass3, interface->color_uniform, src);

				/* if this is the last pass, prepare for rendering on the frambuffer */
				gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

				glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

				/* disable bindings */
				GPU_texture_unbind(fx->dof_near_blur);
				GPU_texture_unbind(fx->dof_far_blur);
				GPU_texture_unbind(src);
				GPU_texture_filter_mode(fx->depth_buffer, true, false, false);
				GPU_texture_unbind(fx->depth_buffer);

				/* may not be attached, in that case this just returns */
				if (target) {
					GPU_framebuffer_texture_detach(target);
					if (ofs) {
						GPU_offscreen_bind(ofs, false);
					}
					else {
						GPU_framebuffer_restore();
					}
				}

				numslots = 0;
			}
		}
		else {
			GPUShader *dof_shader_pass1, *dof_shader_pass2, *dof_shader_pass3, *dof_shader_pass4, *dof_shader_pass5;

			/* DOF effect has many passes but most of them are performed
			 * on a texture whose dimensions are 4 times less than the original
			 * (16 times lower than original screen resolution).
			 * Technique used is not very exact but should be fast enough and is based
			 * on "Practical Post-Process Depth of Field"
			 * see http://http.developer.nvidia.com/GPUGems3/gpugems3_ch28.html */
			dof_shader_pass1 = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_DEPTH_OF_FIELD_PASS_ONE, is_persp);
			dof_shader_pass2 = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_DEPTH_OF_FIELD_PASS_TWO, is_persp);
			dof_shader_pass3 = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_DEPTH_OF_FIELD_PASS_THREE, is_persp);
			dof_shader_pass4 = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_DEPTH_OF_FIELD_PASS_FOUR, is_persp);
			dof_shader_pass5 = GPU_shader_get_builtin_fx_shader(GPU_SHADER_FX_DEPTH_OF_FIELD_PASS_FIVE, is_persp);

			/* error occured, restore framebuffers and return */
			if (!(dof_shader_pass1 && dof_shader_pass2 && dof_shader_pass3 && dof_shader_pass4 && dof_shader_pass5)) {
				GPU_framebuffer_texture_unbind(fx->gbuffer, NULL);
				GPU_framebuffer_restore();
				glDisableClientState(GL_VERTEX_ARRAY);
				glDisableClientState(GL_TEXTURE_COORD_ARRAY);

				GPU_shader_unbind();
				glBindBuffer(GL_ARRAY_BUFFER, 0);
				return false;
			}

			/* pass first, first level of blur in low res buffer */
			{
				float invrendertargetdim[2] = {1.0f / fx->gbuffer_dim[0], 1.0f / fx->gbuffer_dim[1]};

				GPUDOFPassOneInterface *interface = GPU_shader_get_interface(dof_shader_pass1);

				GPU_shader_bind(dof_shader_pass1);

				GPU_shader_uniform_vector(dof_shader_pass1, interface->dof_uniform, 4, 1, dof_params);
				GPU_shader_uniform_vector(dof_shader_pass1, interface->invrendertargetdim_uniform, 2, 1, invrendertargetdim);
				GPU_shader_uniform_vector(dof_shader_pass1, interface->viewvecs_uniform, 4, 3, viewvecs[0]);

				GPU_texture_bind(src, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass1, interface->color_uniform, src);

				GPU_texture_bind(fx->depth_buffer, numslots++);
				GPU_texture_filter_mode(fx->depth_buffer, false, true, false);
				GPU_shader_uniform_texture(dof_shader_pass1, interface->depth_uniform, fx->depth_buffer);

				/* target is the downsampled coc buffer */
				GPU_framebuffer_texture_attach(fx->gbuffer, fx->dof_near_coc_buffer, 0, NULL);
				/* binding takes care of setting the viewport to the downsampled size */
				GPU_texture_bind_as_framebuffer(fx->dof_near_coc_buffer);

				glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
				/* disable bindings */
				GPU_texture_unbind(src);
				GPU_texture_filter_mode(fx->depth_buffer, true, false, false);
				GPU_texture_unbind(fx->depth_buffer);

				GPU_framebuffer_texture_detach(fx->dof_near_coc_buffer);
				numslots = 0;
			}

			/* second pass, gaussian blur the downsampled image */
			{
				float invrendertargetdim[2] = {1.0f / GPU_texture_width(fx->dof_near_coc_blurred_buffer),
				                               1.0f / GPU_texture_height(fx->dof_near_coc_blurred_buffer)};
				float tmp = invrendertargetdim[0];
				invrendertargetdim[0] = 0.0f;

				GPUDOFPassTwoInterface *interface = GPU_shader_get_interface(dof_shader_pass2);

				dof_params[2] = GPU_texture_width(fx->dof_near_coc_blurred_buffer) / (scale_camera * fx_dof->sensor);

				/* Blurring vertically */
				GPU_shader_bind(dof_shader_pass2);

				GPU_shader_uniform_vector(dof_shader_pass2, interface->dof_uniform, 4, 1, dof_params);
				GPU_shader_uniform_vector(dof_shader_pass2, interface->invrendertargetdim_uniform, 2, 1, invrendertargetdim);
				GPU_shader_uniform_vector(dof_shader_pass2, interface->viewvecs_uniform, 4, 3, viewvecs[0]);

				GPU_texture_bind(fx->depth_buffer, numslots++);
				GPU_texture_filter_mode(fx->depth_buffer, false, true, false);
				GPU_shader_uniform_texture(dof_shader_pass2, interface->depth_uniform, fx->depth_buffer);

				GPU_texture_bind(fx->dof_near_coc_buffer, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass2, interface->color_uniform, fx->dof_near_coc_buffer);

				/* use final buffer as a temp here */
				GPU_framebuffer_texture_attach(fx->gbuffer, fx->dof_near_coc_final_buffer, 0, NULL);

				/* Drawing quad */
				glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

				/* *unbind/detach */
				GPU_texture_unbind(fx->dof_near_coc_buffer);
				GPU_framebuffer_texture_detach(fx->dof_near_coc_final_buffer);

				/* Blurring horizontally */
				invrendertargetdim[0] = tmp;
				invrendertargetdim[1] = 0.0f;
				GPU_shader_uniform_vector(dof_shader_pass2, interface->invrendertargetdim_uniform, 2, 1, invrendertargetdim);

				GPU_texture_bind(fx->dof_near_coc_final_buffer, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass2, interface->color_uniform, fx->dof_near_coc_final_buffer);

				GPU_framebuffer_texture_attach(fx->gbuffer, fx->dof_near_coc_blurred_buffer, 0, NULL);
				glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

				/* *unbind/detach */
				GPU_texture_filter_mode(fx->depth_buffer, true, false, false);
				GPU_texture_unbind(fx->depth_buffer);

				GPU_texture_unbind(fx->dof_near_coc_final_buffer);
				GPU_framebuffer_texture_detach(fx->dof_near_coc_blurred_buffer);

				dof_params[2] = fx->gbuffer_dim[0] / (scale_camera * fx_dof->sensor);

				numslots = 0;
			}

			/* third pass, calculate near coc */
			{
				GPUDOFPassThreeInterface *interface = GPU_shader_get_interface(dof_shader_pass3);

				GPU_shader_bind(dof_shader_pass3);

				GPU_texture_bind(fx->dof_near_coc_buffer, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass3, interface->near_coc_downsampled, fx->dof_near_coc_buffer);

				GPU_texture_bind(fx->dof_near_coc_blurred_buffer, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass3, interface->near_coc_blurred, fx->dof_near_coc_blurred_buffer);

				GPU_framebuffer_texture_attach(fx->gbuffer, fx->dof_near_coc_final_buffer, 0, NULL);

				glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
				/* disable bindings */
				GPU_texture_unbind(fx->dof_near_coc_buffer);
				GPU_texture_unbind(fx->dof_near_coc_blurred_buffer);

				/* unbinding here restores the size to the original */
				GPU_framebuffer_texture_detach(fx->dof_near_coc_final_buffer);

				numslots = 0;
			}

			/* fourth pass blur final coc once to eliminate discontinuities */
			{
				float invrendertargetdim[2] = {1.0f / GPU_texture_width(fx->dof_near_coc_blurred_buffer),
				                               1.0f / GPU_texture_height(fx->dof_near_coc_blurred_buffer)};

				GPUDOFPassFourInterface *interface = GPU_shader_get_interface(dof_shader_pass4);

				GPU_shader_bind(dof_shader_pass4);

				GPU_texture_bind(fx->dof_near_coc_final_buffer, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass4, interface->near_coc_downsampled, fx->dof_near_coc_final_buffer);
				GPU_shader_uniform_vector(dof_shader_pass4, interface->invrendertargetdim_uniform, 2, 1, invrendertargetdim);

				GPU_framebuffer_texture_attach(fx->gbuffer, fx->dof_near_coc_buffer, 0, NULL);

				glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
				/* disable bindings */
				GPU_texture_unbind(fx->dof_near_coc_final_buffer);

				/* unbinding here restores the size to the original */
				GPU_framebuffer_texture_unbind(fx->gbuffer, fx->dof_near_coc_buffer);
				GPU_framebuffer_texture_detach(fx->dof_near_coc_buffer);

				numslots = 0;
			}

			/* final pass, merge blurred layers according to final calculated coc */
			{
				float invrendertargetdim[2] = {1.0f / fx->gbuffer_dim[0], 1.0f / fx->gbuffer_dim[1]};

				GPUDOFPassFiveInterface *interface = GPU_shader_get_interface(dof_shader_pass5);

				GPU_shader_bind(dof_shader_pass5);

				GPU_shader_uniform_vector(dof_shader_pass5, interface->dof_uniform, 4, 1, dof_params);
				GPU_shader_uniform_vector(dof_shader_pass5, interface->invrendertargetdim_uniform, 2, 1, invrendertargetdim);
				GPU_shader_uniform_vector(dof_shader_pass5, interface->viewvecs_uniform, 4, 3, viewvecs[0]);

				GPU_texture_bind(src, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass5, interface->original_uniform, src);

				GPU_texture_bind(fx->dof_near_coc_blurred_buffer, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass5, interface->high_blurred_uniform, fx->dof_near_coc_blurred_buffer);

				GPU_texture_bind(fx->dof_near_coc_buffer, numslots++);
				GPU_shader_uniform_texture(dof_shader_pass5, interface->medium_blurred_uniform, fx->dof_near_coc_buffer);

				GPU_texture_bind(fx->depth_buffer, numslots++);
				GPU_texture_filter_mode(fx->depth_buffer, false, true, false);
				GPU_shader_uniform_texture(dof_shader_pass5, interface->depth_uniform, fx->depth_buffer);

				/* if this is the last pass, prepare for rendering on the frambuffer */
				gpu_fx_bind_render_target(&passes_left, fx, ofs, target);

				glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
				/* disable bindings */
				GPU_texture_unbind(fx->dof_near_coc_buffer);
				GPU_texture_unbind(fx->dof_near_coc_blurred_buffer);
				GPU_texture_unbind(src);
				GPU_texture_filter_mode(fx->depth_buffer, true, false, false);
				GPU_texture_unbind(fx->depth_buffer);

				/* may not be attached, in that case this just returns */
				if (target) {
					GPU_framebuffer_texture_detach(target);
					if (ofs) {
						GPU_offscreen_bind(ofs, false);
					}
					else {
						GPU_framebuffer_restore();
					}
				}

				SWAP(GPUTexture *, target, src);
				numslots = 0;
			}
		}
	}

	glDisableClientState(GL_VERTEX_ARRAY);
	glDisableClientState(GL_TEXTURE_COORD_ARRAY);
	glBindBuffer(GL_ARRAY_BUFFER, 0);

	GPU_shader_unbind();

	return true;
}

void GPU_fx_compositor_init_dof_settings(GPUDOFSettings *fx_dof)
{
	fx_dof->fstop = 128.0f;
	fx_dof->focal_length = 1.0f;
	fx_dof->focus_distance = 1.0f;
	fx_dof->sensor = 1.0f;
	fx_dof->num_blades = 6;
}

void GPU_fx_shader_init_interface(struct GPUShader *shader, GPUFXShaderEffect effect)
{
	if (!shader)
		return;

	switch (effect) {
		case GPU_SHADER_FX_SSAO:
		{
			GPUSSAOShaderInterface *interface = MEM_mallocN(sizeof(GPUSSAOShaderInterface), "GPUSSAOShaderInterface");

			interface->ssao_uniform = GPU_shader_get_uniform(shader, "ssao_params");
			interface->ssao_color_uniform = GPU_shader_get_uniform(shader, "ssao_color");
			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");
			interface->viewvecs_uniform = GPU_shader_get_uniform(shader, "viewvecs");
			interface->ssao_sample_params_uniform = GPU_shader_get_uniform(shader, "ssao_sample_params");
			interface->ssao_concentric_tex = GPU_shader_get_uniform(shader, "ssao_concentric_tex");
			interface->ssao_jitter_uniform = GPU_shader_get_uniform(shader, "jitter_tex");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_DEPTH_OF_FIELD_HQ_PASS_ONE:
		{
			GPUDOFHQPassOneInterface *interface = MEM_mallocN(sizeof(GPUDOFHQPassOneInterface), "GPUDOFHQPassOneInterface");

			interface->invrendertargetdim_uniform = GPU_shader_get_uniform(shader, "invrendertargetdim");
			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->dof_uniform = GPU_shader_get_uniform(shader, "dof_params");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");
			interface->viewvecs_uniform = GPU_shader_get_uniform(shader, "viewvecs");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_DEPTH_OF_FIELD_HQ_PASS_TWO:
		{
			GPUDOFHQPassTwoInterface *interface = MEM_mallocN(sizeof(GPUDOFHQPassTwoInterface), "GPUDOFHQPassTwoInterface");

			interface->rendertargetdim_uniform = GPU_shader_get_uniform(shader, "rendertargetdim");
			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->coc_uniform = GPU_shader_get_uniform(shader, "cocbuffer");
			interface->select_uniform = GPU_shader_get_uniform(shader, "layerselection");
			interface->dof_uniform = GPU_shader_get_uniform(shader, "dof_params");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_DEPTH_OF_FIELD_HQ_PASS_THREE:
		{
			GPUDOFHQPassThreeInterface *interface = MEM_mallocN(sizeof(GPUDOFHQPassThreeInterface), "GPUDOFHQPassThreeInterface");

			interface->dof_uniform = GPU_shader_get_uniform(shader, "dof_params");
			interface->invrendertargetdim_uniform = GPU_shader_get_uniform(shader, "invrendertargetdim");
			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->far_uniform = GPU_shader_get_uniform(shader, "farbuffer");
			interface->near_uniform = GPU_shader_get_uniform(shader, "nearbuffer");
			interface->viewvecs_uniform = GPU_shader_get_uniform(shader, "viewvecs");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_DEPTH_OF_FIELD_PASS_ONE:
		{
			GPUDOFPassOneInterface *interface = MEM_mallocN(sizeof(GPUDOFPassOneInterface), "GPUDOFPassOneInterface");

			interface->dof_uniform = GPU_shader_get_uniform(shader, "dof_params");
			interface->invrendertargetdim_uniform = GPU_shader_get_uniform(shader, "invrendertargetdim");
			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");
			interface->viewvecs_uniform = GPU_shader_get_uniform(shader, "viewvecs");

			GPU_shader_set_interface(shader, interface);
			break;
		}
		case GPU_SHADER_FX_DEPTH_OF_FIELD_PASS_TWO:
		{
			GPUDOFPassTwoInterface *interface = MEM_mallocN(sizeof(GPUDOFPassTwoInterface), "GPUDOFPassTwoInterface");

			interface->dof_uniform = GPU_shader_get_uniform(shader, "dof_params");
			interface->invrendertargetdim_uniform = GPU_shader_get_uniform(shader, "invrendertargetdim");
			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");
			interface->viewvecs_uniform = GPU_shader_get_uniform(shader, "viewvecs");

			GPU_shader_set_interface(shader, interface);
			break;
		}
		case GPU_SHADER_FX_DEPTH_OF_FIELD_PASS_THREE:
		{
			GPUDOFPassThreeInterface *interface = MEM_mallocN(sizeof(GPUDOFPassThreeInterface), "GPUDOFPassThreeInterface");

			interface->near_coc_downsampled = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->near_coc_blurred = GPU_shader_get_uniform(shader, "blurredcolorbuffer");

			GPU_shader_set_interface(shader, interface);
			break;
		}
		case GPU_SHADER_FX_DEPTH_OF_FIELD_PASS_FOUR:
		{
			GPUDOFPassFourInterface *interface = MEM_mallocN(sizeof(GPUDOFPassFourInterface), "GPUDOFPassFourInterface");

			interface->near_coc_downsampled = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->invrendertargetdim_uniform = GPU_shader_get_uniform(shader, "invrendertargetdim");

			GPU_shader_set_interface(shader, interface);
			break;
		}
		case GPU_SHADER_FX_DEPTH_OF_FIELD_PASS_FIVE:
		{
			GPUDOFPassFiveInterface *interface = MEM_mallocN(sizeof(GPUDOFPassFiveInterface), "GPUDOFPassFiveInterface");

			interface->medium_blurred_uniform = GPU_shader_get_uniform(shader, "mblurredcolorbuffer");
			interface->high_blurred_uniform = GPU_shader_get_uniform(shader, "blurredcolorbuffer");
			interface->dof_uniform = GPU_shader_get_uniform(shader, "dof_params");
			interface->invrendertargetdim_uniform = GPU_shader_get_uniform(shader, "invrendertargetdim");
			interface->original_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");
			interface->viewvecs_uniform = GPU_shader_get_uniform(shader, "viewvecs");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_DEPTH_RESOLVE:
		{
			GPUDepthResolveInterface *interface = MEM_mallocN(sizeof(GPUDepthResolveInterface), "GPUDepthResolveInterface");

			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		/* SCENE_SHADER_FX */
		case GPU_SHADER_FX_BLOOM:
		{
			GPUBLOOMShaderInterface *interface = MEM_mallocN(sizeof(GPUBLOOMShaderInterface), "GPUBLOOMShaderInterface");

			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->bloom_uniform = GPU_shader_get_uniform(shader, "bloom_params");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_TONEMAP:
		{
			GPUTONEMAPShaderInterface *interface = MEM_mallocN(sizeof(GPUTONEMAPShaderInterface), "GPUTONEMAPShaderInterface");

			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->tonemapParams_uniform = GPU_shader_get_uniform(shader, "tonemapParams");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_LIGHTSCATTER:
		{
			GPULIGHTSCATTERShaderInterface *interface = MEM_mallocN(sizeof(GPULIGHTSCATTERShaderInterface), "GPULIGHTSCATTERShaderInterface");

			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");
			interface->sunpos_uniform = GPU_shader_get_uniform(shader, "sunpos");
			interface->scatter_params_uniform = GPU_shader_get_uniform(shader, "scatter_params");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_SSR:
		{
			GPUSSRShaderInterface *interface = MEM_mallocN(sizeof(GPUSSRShaderInterface), "GPUSSRShaderInterface");

			interface->ssr_uniform = GPU_shader_get_uniform(shader, "ssr_params");
			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");
			interface->viewvecs_uniform = GPU_shader_get_uniform(shader, "viewvecs");
			interface->ssr_jitter_uniform = GPU_shader_get_uniform(shader, "jitter_tex");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_FXAA:
		{
			GPUFXAAShaderInterface *interface = MEM_mallocN(sizeof(GPUFXAAShaderInterface), "GPUFXAAShaderInterface");

			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->viewport_size_uniform = GPU_shader_get_uniform(shader, "viewport_size");
			interface->fxaa_params_uniform = GPU_shader_get_uniform(shader, "fxaa_params");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_LENSFLARE:
		{
			GPULENSFLAREShaderInterface *interface = MEM_mallocN(sizeof(GPULENSFLAREShaderInterface), "GPULENSFLAREShaderInterface");

			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");
			interface->sunpos_uniform = GPU_shader_get_uniform(shader, "sunpos");
			interface->flare_params_uniform = GPU_shader_get_uniform(shader, "flare_params");
			interface->viewport_size_uniform = GPU_shader_get_uniform(shader, "viewport_size");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_RAIN:
		{
			GPURAINShaderInterface *interface = MEM_mallocN(sizeof(GPURAINShaderInterface), "GPURAINShaderInterface");

			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");
			interface->rain_params1_uniform = GPU_shader_get_uniform(shader, "rain_params1");
			interface->rain_params2_uniform = GPU_shader_get_uniform(shader, "rain_params2");
			interface->rain_params3_uniform = GPU_shader_get_uniform(shader, "rain_params3");
			interface->rain_color_uniform = GPU_shader_get_uniform(shader, "rain_color");
			interface->rain_style_uniform = GPU_shader_get_uniform(shader, "rain_style");
			interface->rain_fall_phase_uniform = GPU_shader_get_uniform(shader, "rain_fall_phase");
			interface->rain_params4_uniform = GPU_shader_get_uniform(shader, "rain_params4");
			interface->rain_lightning_uniform = GPU_shader_get_uniform(shader, "rain_lightning");
			interface->rain_streak_width_uniform = GPU_shader_get_uniform(shader, "rain_streak_width");
			interface->rain_ripple_normal_uniform = GPU_shader_get_uniform(shader, "rain_ripple_normal");
			interface->rain_params5_uniform = GPU_shader_get_uniform(shader, "rain_params5");
			interface->rain_puddle1_uniform = GPU_shader_get_uniform(shader, "rain_puddle1");
			interface->rain_puddle2_uniform = GPU_shader_get_uniform(shader, "rain_puddle2");
			interface->rain_sky_horizon_uniform = GPU_shader_get_uniform(shader, "rain_sky_horizon");
			interface->rain_sky_zenith_uniform = GPU_shader_get_uniform(shader, "rain_sky_zenith");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_CLOUDS:
		{
			GPUCLOUDSShaderInterface *interface = MEM_mallocN(sizeof(GPUCLOUDSShaderInterface), "GPUCLOUDSShaderInterface");

			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");
			interface->clouds_params_uniform = GPU_shader_get_uniform(shader, "clouds_params");
			interface->clouds_color_uniform = GPU_shader_get_uniform(shader, "clouds_color");
			interface->clouds_mask_uniform = GPU_shader_get_uniform(shader, "clouds_mask");
			interface->sky_layers_params_uniform = GPU_shader_get_uniform(shader, "sky_layers_params");
			interface->sky_layers_color_uniform = GPU_shader_get_uniform(shader, "sky_layers_color");
			interface->clouds_quality_uniform = GPU_shader_get_uniform(shader, "clouds_quality");
			interface->vclouds_params1_uniform = GPU_shader_get_uniform(shader, "vclouds_params1");
			interface->vclouds_params2_uniform = GPU_shader_get_uniform(shader, "vclouds_params2");
			interface->vclouds_params3_uniform = GPU_shader_get_uniform(shader, "vclouds_params3");
			interface->vclouds_color_uniform = GPU_shader_get_uniform(shader, "vclouds_color");
			interface->vclouds_sundir_uniform = GPU_shader_get_uniform(shader, "vclouds_sundir");
			interface->history_uniform = GPU_shader_get_uniform(shader, "clouds_history");
			interface->history_depth_uniform = GPU_shader_get_uniform(shader, "clouds_history_depth");
			interface->history_valid_uniform = GPU_shader_get_uniform(shader, "clouds_history_valid");
			interface->history_viewproj_uniform = GPU_shader_get_uniform(shader, "clouds_history_viewproj");
			interface->frame_uniform = GPU_shader_get_uniform(shader, "clouds_frame");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		case GPU_SHADER_FX_VFOG:
		{
			GPUVFOGShaderInterface *interface = MEM_mallocN(sizeof(GPUVFOGShaderInterface), "GPUVFOGShaderInterface");

			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->depth_uniform = GPU_shader_get_uniform(shader, "depthbuffer");
			interface->data_uniform = GPU_shader_get_uniform(shader, "vfog_data");
			interface->mats_uniform = GPU_shader_get_uniform(shader, "vfog_mats");
			interface->shadow0_uniform = GPU_shader_get_uniform(shader, "vfog_shadow0");
			interface->shadow1_uniform = GPU_shader_get_uniform(shader, "vfog_shadow1");
			interface->shadow2_uniform = GPU_shader_get_uniform(shader, "vfog_shadow2");
			interface->frame_uniform = GPU_shader_get_uniform(shader, "vfog_frame");

			GPU_shader_set_interface(shader, interface);
			break;
		}
		case GPU_SHADER_FX_GRAIN:
		{
			GPUGRAINShaderInterface *interface = MEM_mallocN(sizeof(GPUGRAINShaderInterface), "GPUGRAINShaderInterface");

			interface->color_uniform = GPU_shader_get_uniform(shader, "colorbuffer");
			interface->grain_params_uniform = GPU_shader_get_uniform(shader, "grain_params");

			GPU_shader_set_interface(shader, interface);
			break;
		}

		default:
			break;
	}
}
