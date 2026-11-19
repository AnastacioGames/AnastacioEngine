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
 */

/** \file blender/editors/space_view3d/view3d_draw_reflections.c
 *  \ingroup spview3d
 *
 * Realtime reflections in the 3D View, a preview of what the game draws with KX_PlanarMap:
 * an Environment Map texture set to Realtime + Plane gets the scene mirrored through its
 * viewpoint object, drawn into the texture's own image before the main viewport pass. The
 * material shader is the same as in game (mtex_image_refl samples it by window position), so
 * nothing changes on the material side.
 */

#include <string.h>

#include "DNA_camera_types.h"
#include "DNA_image_types.h"
#include "DNA_material_types.h"
#include "DNA_object_types.h"
#include "DNA_scene_types.h"
#include "DNA_screen_types.h"
#include "DNA_texture_types.h"
#include "DNA_view3d_types.h"

#include "BLI_math.h"
#include "BLI_utildefines.h"

#include "BKE_camera.h"
#include "BKE_material.h"

#include "BIF_gl.h"

#include "GPU_draw.h"
#include "GPU_framebuffer.h"
#include "GPU_texture.h"

#include "ED_view3d.h"

#include "view3d_intern.h"  /* own include */

/* Mirrors drawn per viewport redraw: each one draws the whole scene again. */
#define REFLECTION_MAX_PER_REDRAW 4

static GPUOffScreen *refl_ofs = NULL;

void view3d_reflections_free(void)
{
	if (refl_ofs) {
		GPU_offscreen_free(refl_ofs);
		refl_ofs = NULL;
	}
}

static GPUOffScreen *reflection_offscreen(int w, int h)
{
	if (refl_ofs && (GPU_offscreen_width(refl_ofs) != w || GPU_offscreen_height(refl_ofs) != h)) {
		GPU_offscreen_free(refl_ofs);
		refl_ofs = NULL;
	}
	if (!refl_ofs) {
		char err[256];
		refl_ofs = GPU_offscreen_create(w, h, 0, err);
	}
	return refl_ofs;
}

/* Clips what is behind the mirror with an oblique near plane (Lengyel), as KX_PlanarMap::BeginRenderFace.
 * plane_world must have the render camera on its negative side. */
static void reflection_oblique_near(float winmat[4][4], float viewmat[4][4], const float plane_world[4])
{
	float viewinv[4][4], wininv[4][4], plane[4], q[4], corner[4];

	/* Planes go to view space with the inverse transpose of the view matrix. */
	invert_m4_m4(viewinv, viewmat);
	for (int i = 0; i < 4; i++) {
		plane[i] = dot_v4v4(viewinv[i], plane_world);
	}

	corner[0] = plane[0] < 0.0f ? -1.0f : 1.0f;
	corner[1] = plane[1] < 0.0f ? -1.0f : 1.0f;
	corner[2] = 1.0f;
	corner[3] = 1.0f;
	invert_m4_m4(wininv, winmat);
	mul_v4_m4v4(q, wininv, corner);

	const float dot = dot_v4v4(plane, q);
	if (dot == 0.0f) {
		return;
	}
	for (int i = 0; i < 4; i++) {
		winmat[i][2] = plane[i] * (2.0f / dot) - winmat[i][3];
	}
}

/* Window matrix of what the 3D View shows, with the map's clip range: the camera frame in camera
 * view (the material maps window coordinates through the camera border there), else the region. */
static void reflection_winmat(Scene *scene, View3D *v3d, ARegion *ar, RegionView3D *rv3d, const EnvMap *env,
                              float r_winmat[4][4], bool *r_is_persp)
{
	CameraParams params;

	BKE_camera_params_init(&params);
	if (rv3d->persp == RV3D_CAMOB && v3d->camera) {
		BKE_camera_params_from_object(&params, v3d->camera);
	}
	else {
		BKE_camera_params_from_view3d(&params, v3d, rv3d);
	}
	if (!params.is_ortho) {
		params.clipsta = max_ff(env->clipsta, 1e-4f);
		params.clipend = max_ff(env->clipend, params.clipsta + 1e-3f);
	}
	if (rv3d->persp == RV3D_CAMOB && v3d->camera) {
		BKE_camera_params_compute_viewplane(&params, scene->r.xsch, scene->r.ysch, scene->r.xasp, scene->r.yasp);
	}
	else {
		BKE_camera_params_compute_viewplane(&params, ar->winx, ar->winy, 1.0f, 1.0f);
	}
	BKE_camera_params_compute_matrix(&params);

	copy_m4_m4(r_winmat, params.winmat);
	*r_is_persp = !params.is_ortho;
}

static bool reflection_draw_planar(struct Main *bmain, Scene *scene, View3D *v3d, ARegion *ar, Object *viewpoint, Tex *tex)
{
	RegionView3D *rv3d = ar->regiondata;
	EnvMap *env = tex->env;
	float normal[3], plane[4], reflect[4][4], viewmat[4][4], winmat[4][4];
	bool is_persp;

	GPUTexture *gputex = GPU_texture_from_blender(tex->ima, &tex->iuser, GL_TEXTURE_2D, false, 0.0, GPU_get_mipmap());
	if (!gputex) {
		return false;
	}
	const int w = GPU_texture_width(gputex), h = GPU_texture_height(gputex);
	if (w <= 0 || h <= 0) {
		return false;
	}

	/* Plane through the viewpoint object, its local Z as normal (KX_PlanarMap::ComputeClipPlane). */
	normalize_v3_v3(normal, viewpoint->obmat[2]);
	copy_v3_v3(plane, normal);
	plane[3] = -dot_v3v3(normal, viewpoint->obmat[3]);

	/* Viewer behind the mirror: the game skips the render too (KX_PlanarMap::SetupCamera). */
	if (dot_v3v3(plane, rv3d->viewinv[3]) + plane[3] < 0.0f) {
		return false;
	}

	/* x' = x - 2 (n.x + d) n */
	unit_m4(reflect);
	for (int i = 0; i < 3; i++) {
		for (int j = 0; j < 3; j++) {
			reflect[j][i] -= 2.0f * normal[i] * normal[j];
		}
		reflect[3][i] = -2.0f * plane[3] * normal[i];
	}
	mul_m4_m4m4(viewmat, rv3d->viewmat, reflect);

	reflection_winmat(scene, v3d, ar, rv3d, env, winmat, &is_persp);
	reflection_oblique_near(winmat, viewmat, plane);
	/* The mirrored view turns the faces around; drawing it mirrored on X as well keeps their
	 * winding (backface culling, per object glFrontFace), and the copy below mirrors it back. */
	for (int i = 0; i < 4; i++) {
		winmat[i][0] = -winmat[i][0];
	}

	GPUOffScreen *ofs = reflection_offscreen(w, h);
	if (!ofs) {
		return false;
	}

	/* Same region, own matrices: the real one keeps the viewport's. */
	RegionView3D fake_rv3d = *rv3d;
	fake_rv3d.clipbb = NULL;
	fake_rv3d.localvd = NULL;
	fake_rv3d.render_engine = NULL;
	fake_rv3d.depths = NULL;
	fake_rv3d.gpuoffscreen = NULL;
	fake_rv3d.sms = NULL;
	fake_rv3d.smooth_timer = NULL;
	fake_rv3d.compositor = NULL;
	fake_rv3d.rflag &= ~RV3D_CLIPPING;
	fake_rv3d.persp = is_persp ? RV3D_PERSP : RV3D_ORTHO;
	fake_rv3d.is_persp = is_persp;

	ARegion fake_ar = {NULL};
	fake_ar.regiondata = &fake_rv3d;
	fake_ar.regiontype = RGN_TYPE_WINDOW;
	fake_ar.winx = w;
	fake_ar.winy = h;

	/* The viewpoint hides (the game does it too) and Ignore Layers stay out. */
	const unsigned int lay = v3d->lay;
	const int flag2 = v3d->flag2;
	const char restrictflag = viewpoint->restrictflag;
	v3d->lay &= ~(unsigned int)env->notlay;
	v3d->flag2 |= V3D_RENDER_OVERRIDE;
	viewpoint->restrictflag |= OB_RESTRICT_VIEW;

	if (v3d->lay) {
		GPU_offscreen_bind(ofs, true);
		ED_view3d_draw_offscreen(
		        bmain, scene, v3d, &fake_ar, w, h, viewmat, winmat,
		        false, true, is_persp,
		        NULL, NULL, NULL, NULL);
		/* The offscreen draw frees animated images' textures: take it again before writing. */
		gputex = GPU_texture_from_blender(tex->ima, &tex->iuser, GL_TEXTURE_2D, false, 0.0, GPU_get_mipmap());
		if (!gputex || GPU_texture_width(gputex) != w || GPU_texture_height(gputex) != h ||
		    !GPU_offscreen_blit_to_texture(ofs, gputex, true))
		{
			gputex = NULL;
		}
		GPU_offscreen_unbind(ofs, true);
	}

	const bool drawn = (v3d->lay != 0);
	if (drawn && gputex) {
		/* Same filtering as RAS_TextureRenderer::GetValidTexture. */
		GPU_texture_bind(gputex, 0);
		if (env->filtering == ENVMAP_MIPMAP_MIPMAP && GPU_get_mipmap()) {
			GPU_texture_generate_mipmap(gputex);
		}
		else {
			GPU_texture_filter_mode(gputex, false, env->filtering == ENVMAP_MIPMAP_LINEAR, false);
		}
		GPU_texture_unbind(gputex);
	}

	viewpoint->restrictflag = restrictflag;
	v3d->flag2 = flag2;
	v3d->lay = lay;
	return drawn;
}

static bool reflection_tex_is_planar(const Tex *tex)
{
	return tex && tex->type == TEX_ENVMAP && tex->env && tex->ima &&
	       tex->env->stype == ENV_REALT && tex->env->type == ENV_PLANE;
}

bool view3d_reflections_update(struct Main *bmain, Scene *scene, View3D *v3d, ARegion *ar)
{
	/* Textures already handled this redraw; only the ones actually drawn count toward the cap. */
	Tex *done[64];
	int totdone = 0, totdrawn = 0;

	for (Base *base = scene->base.first; base && totdrawn < REFLECTION_MAX_PER_REDRAW && totdone < ARRAY_SIZE(done); base = base->next) {
		Object *ob = base->object;
		if (!BASE_VISIBLE(v3d, base) || ob->type != OB_MESH) {
			continue;
		}

		for (short a = 1; a <= ob->totcol && totdrawn < REFLECTION_MAX_PER_REDRAW && totdone < ARRAY_SIZE(done); a++) {
			Material *ma = give_current_material(ob, a);
			if (!ma) {
				continue;
			}

			for (int k = 0; k < MAX_MTEX && totdrawn < REFLECTION_MAX_PER_REDRAW && totdone < ARRAY_SIZE(done); k++) {
				MTex *mtex = ma->mtex[k];
				if (!mtex || (ma->septex & (1 << k)) || !reflection_tex_is_planar(mtex->tex)) {
					continue;
				}

				/* A texture shared by several objects renders once, from its first viewpoint (game too). */
				bool seen = false;
				for (int i = 0; i < totdone; i++) {
					seen |= (done[i] == mtex->tex);
				}
				if (seen) {
					continue;
				}
				done[totdone++] = mtex->tex;

				Object *viewpoint = mtex->tex->env->object ? mtex->tex->env->object : ob;
				totdrawn += reflection_draw_planar(bmain, scene, v3d, ar, viewpoint, mtex->tex);
			}
		}
	}
	return totdrawn > 0;
}
