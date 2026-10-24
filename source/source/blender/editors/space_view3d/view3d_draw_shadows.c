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
 * The Original Code is Copyright (C) 2008 Blender Foundation.
 * All rights reserved.
 */

/** \file blender/editors/space_view3d/view3d_draw.c
 *  \ingroup spview3d
 */

#include <string.h>
#include <stdio.h>
#include <math.h>

#include "PIL_time.h"

#include "DNA_armature_types.h"
#include "DNA_camera_types.h"
#include "DNA_customdata_types.h"
#include "DNA_object_types.h"
#include "DNA_group_types.h"
#include "DNA_mesh_types.h"
#include "DNA_key_types.h"
#include "DNA_lamp_types.h"
#include "DNA_material_types.h"
#include "DNA_scene_types.h"
#include "DNA_world_types.h"
#include "DNA_brush_types.h"

#include "MEM_guardedalloc.h"

#include "BLI_blenlib.h"
#include "BLI_math.h"
#include "BLI_jitter_2d.h"
#include "BLI_utildefines.h"
#include "BLI_endian_switch.h"
#include "BLI_threads.h"
#include "BLI_string.h"

#include "BKE_anim.h"
#include "BKE_camera.h"
#include "BKE_context.h"
#include "BKE_customdata.h"
#include "BKE_DerivedMesh.h"
#include "BKE_image.h"
#include "BKE_key.h"
#include "BKE_library.h"
#include "BKE_main.h"
#include "BKE_material.h"
#include "BKE_object.h"
#include "BKE_global.h"
#include "BKE_paint.h"
#include "BKE_scene.h"
#include "BKE_screen.h"
#include "BKE_unit.h"
#include "BKE_movieclip.h"

#include "RE_engine.h"

#include "IMB_imbuf_types.h"
#include "IMB_imbuf.h"
#include "IMB_colormanagement.h"

#include "BIF_gl.h"
#include "BIF_glutil.h"

#include "WM_api.h"
#include "WM_types.h"

#include "BLF_api.h"
#include "BLT_translation.h"

#include "ED_armature.h"
#include "ED_keyframing.h"
#include "ED_gpencil.h"
#include "ED_screen.h"
#include "ED_space_api.h"
#include "ED_screen_types.h"
#include "ED_transform.h"
#include "ED_view3d.h"

#include "RNA_access.h"
#include "RNA_enum_types.h"

#include "UI_interface.h"
#include "UI_interface_icons.h"
#include "UI_resources.h"

#include "GPU_draw.h"
#include "GPU_framebuffer.h"
#include "GPU_shader.h"
#include "GPU_material.h"
#include "GPU_compositing.h"
#include "GPU_extensions.h"
#include "GPU_select.h"
#include "GPU_init_exit.h"

#include "view3d_intern.h"  /* own include */

/* Lamp shadow buffers and CSM cascades for the viewport (moved from view3d_draw.c). */


typedef struct View3DShadow {
	struct View3DShadow *next, *prev;
	GPULamp *lamp;
	Lamp *la;
	float obmat[4][4];
} View3DShadow;

static void gpu_render_lamp_update(Scene *scene, View3D *v3d,
                                   Object *ob, Object *par,
                                   float obmat[4][4], unsigned int lay,
                                   ListBase *shadows, SceneRenderLayer *srl)
{
	GPULamp *lamp;
	Lamp *la = (Lamp *)ob->data;
	View3DShadow *shadow;
	unsigned int layers;

	lamp = GPU_lamp_from_blender(scene, ob, par);

	if (lamp) {
		GPU_lamp_update(lamp, lay, (ob->restrictflag & OB_RESTRICT_RENDER), obmat);
		GPU_lamp_update_colors(lamp, la->r, la->g, la->b, la->energy);

		layers = lay & v3d->lay;
		if (srl)
			layers &= srl->lay;

		if (layers &&
		    GPU_lamp_has_shadow_buffer(lamp) &&
		    /* keep last, may do string lookup */
		    GPU_lamp_visible(lamp, srl, NULL))
		{
			shadow = MEM_callocN(sizeof(View3DShadow), "View3DShadow");
			shadow->lamp = lamp;
			shadow->la = la;
			copy_m4_m4(shadow->obmat, obmat);
			BLI_addtail(shadows, shadow);
		}
	}
}

/* Computes a camera-frustum-fit orthographic view/projection matrix pair for one CSM cascade,
 * mirroring KX_ShadowRenderer::ComputeCascadeShadowMatrices (used by the game engine) but using
 * Blender's float[4][4]/BLI_math types and the viewport's RegionView3D as the stand-in "viewer
 * camera" instead of a KX_Camera. cascadeIndex: 0=Near, 1=Medium, 2=Low -- this matches the game
 * engine's numbering, NOT GPU_lamp_get_cascade()'s 0=Medium/1=Low. */
static void view3d_compute_cascade_shadow_matrix(
        RegionView3D *rv3d, float light_obmat[4][4],
        float clipsta, float clipend, float propNear, float propMiddle,
        short cascadeIndex,
        float r_viewmat[4][4], float r_winmat[4][4], float *r_splitFar)
{
	const float cliprange = clipend - clipsta;
	float splitNear, splitFar;

	switch (cascadeIndex) {
		case 0: /* Near */
			splitNear = clipsta;
			splitFar = clipsta + propNear * cliprange;
			break;
		case 1: /* Medium */
			splitNear = clipsta + propNear * cliprange;
			splitFar = splitNear + propMiddle * cliprange;
			break;
		default: /* Low */
			splitNear = clipsta + (propNear + propMiddle) * cliprange;
			splitFar = clipend;
			break;
	}
	*r_splitFar = splitFar;

	const float p00 = rv3d->winmat[0][0];
	const float p11 = rv3d->winmat[1][1];

	/* 8 corners of the viewport camera's frustum slice [splitNear, splitFar], in view space. */
	float corners[8][3];
	int idx = 0;
	const float dists[2] = {splitNear, splitFar};
	for (int s = 0; s < 2; s++) {
		const float d = dists[s];
		float hw, hh;
		if (rv3d->is_persp) {
			hw = d / p00;
			hh = d / p11;
		}
		else {
			/* Orthographic: extents don't scale with depth. */
			hw = 1.0f / p00;
			hh = 1.0f / p11;
		}
		corners[idx][0] = -hw; corners[idx][1] = -hh; corners[idx][2] = -d; idx++;
		corners[idx][0] =  hw; corners[idx][1] = -hh; corners[idx][2] = -d; idx++;
		corners[idx][0] = -hw; corners[idx][1] =  hh; corners[idx][2] = -d; idx++;
		corners[idx][0] =  hw; corners[idx][1] =  hh; corners[idx][2] = -d; idx++;
	}

	float lightWorldInv[4][4];
	invert_m4_m4(lightWorldInv, light_obmat);

	float minX = FLT_MAX, maxX = -FLT_MAX;
	float minY = FLT_MAX, maxY = -FLT_MAX;
	float minZ = FLT_MAX, maxZ = -FLT_MAX;

	for (int i = 0; i < 8; i++) {
		float world_co[3], light_co[3];
		mul_v3_m4v3(world_co, rv3d->viewinv, corners[i]);
		mul_v3_m4v3(light_co, lightWorldInv, world_co);
		minX = min_ff(minX, light_co[0]); maxX = max_ff(maxX, light_co[0]);
		minY = min_ff(minY, light_co[1]); maxY = max_ff(maxY, light_co[1]);
		minZ = min_ff(minZ, light_co[2]); maxZ = max_ff(maxZ, light_co[2]);
	}

	/* Light shines down its local -Z axis (Blender convention), so distance-from-light
	 * increases as local Z decreases: near = -maxZ (closest), far = -minZ (farthest). */
	const float lightNear = -maxZ;
	const float lightFar = -minZ;

	orthographic_m4(r_winmat, minX, maxX, minY, maxY, lightNear, lightFar);

	/* Strip any lamp object scale, matching what GPU_lamp_update_buffer_mats does for the
	 * non-CSM path so the Near cascade's own buffer stays consistent with Medium/Low. */
	copy_m4_m4(r_viewmat, lightWorldInv);
	normalize_v3(r_viewmat[0]);
	normalize_v3(r_viewmat[1]);
	normalize_v3(r_viewmat[2]);
}

void gpu_update_lamps_shadows_world(Main *bmain, Scene *scene, View3D *v3d, RegionView3D *viewer_rv3d)
{
	ListBase shadows;
	View3DShadow *shadow;
	Scene *sce_iter;
	Base *base;
	Object *ob;
	World *world = scene->world;
	SceneRenderLayer *srl = v3d->scenelock ? BLI_findlink(&scene->r.layers, scene->r.actlay) : NULL;

	BLI_listbase_clear(&shadows);

	/* update lamp transform and gather shadow lamps */
	for (SETLOOPER(scene, sce_iter, base)) {
		ob = base->object;

		if (ob->type == OB_LAMP)
			gpu_render_lamp_update(scene, v3d, ob, NULL, ob->obmat, ob->lay, &shadows, srl);

		if (ob->transflag & OB_DUPLI) {
			DupliObject *dob;
			ListBase *lb = object_duplilist(bmain, bmain->eval_ctx, scene, ob);

			for (dob = lb->first; dob; dob = dob->next)
				if (dob->ob->type == OB_LAMP)
					gpu_render_lamp_update(scene, v3d, dob->ob, ob, dob->mat, ob->lay, &shadows, srl);

			free_object_duplilist(lb);
		}
	}

	/* render shadows after updating all lamps, nested object_duplilist
	 * don't work correct since it's replacing object matrices */
	for (shadow = shadows.first; shadow; shadow = shadow->next) {
		/* this needs to be done better .. */
		float viewmat[4][4], winmat[4][4];
		int drawtype, lay, winsize, flag2 = v3d->flag2;
		ARegion ar = {NULL};
		RegionView3D rv3d = {{{0}}};
		bool vsm = GPU_lamp_shadow_buffer_type(shadow->lamp) == LA_SHADMAP_VARIANCE;

		drawtype = v3d->drawtype;
		lay = v3d->lay;

		v3d->drawtype = OB_SOLID;
		v3d->lay &= GPU_lamp_shadow_layer(shadow->lamp);
		v3d->flag2 &= ~(V3D_SOLID_TEX | V3D_SHOW_SOLID_MATCAP);
		v3d->flag2 |= V3D_RENDER_OVERRIDE | V3D_RENDER_SHADOW;

		if (GPU_lamp_has_point_shadow(shadow->lamp)) {
			/* Point: the 6 cube faces, each into its tile of the 3x2 atlas. */
			for (int face = 0; face < 6; face++) {
				int viewport[4];
				GPU_lamp_shadow_point_face_bind(shadow->lamp, face, viewmat, winmat, viewport);

				ar.regiondata = &rv3d;
				ar.regiontype = RGN_TYPE_WINDOW;
				rv3d.persp = RV3D_CAMOB;
				copy_m4_m4(rv3d.winmat, winmat);
				copy_m4_m4(rv3d.viewmat, viewmat);
				invert_m4_m4(rv3d.viewinv, rv3d.viewmat);
				mul_m4_m4m4(rv3d.persmat, rv3d.winmat, rv3d.viewmat);
				invert_m4_m4(rv3d.persinv, rv3d.viewinv);

				ED_view3d_draw_offscreen(
				            bmain, scene, v3d, &ar, viewport[2], viewport[3], viewmat, winmat,
				            false, false, true,
				            NULL, NULL, NULL, NULL);
				GPU_lamp_shadow_buffer_unbind(shadow->lamp);
			}

			v3d->drawtype = drawtype;
			v3d->lay = lay;
			v3d->flag2 = flag2;
			continue;
		}

		if (vsm) {
			GPU_shader_bind(GPU_shader_get_builtin_shader(GPU_SHADER_VSM_STORE));
		}
		GPU_lamp_shadow_buffer_bind(shadow->lamp, viewmat, &winsize, winmat);

		ar.regiondata = &rv3d;
		ar.regiontype = RGN_TYPE_WINDOW;
		rv3d.persp = RV3D_CAMOB;
		copy_m4_m4(rv3d.winmat, winmat);
		copy_m4_m4(rv3d.viewmat, viewmat);
		invert_m4_m4(rv3d.viewinv, rv3d.viewmat);
		mul_m4_m4m4(rv3d.persmat, rv3d.winmat, rv3d.viewmat);
		invert_m4_m4(rv3d.persinv, rv3d.viewinv);

		/* no need to call ED_view3d_draw_offscreen_init since shadow buffers were already updated */
		GPU_shadow_depth_pass_set(!vsm);
		ED_view3d_draw_offscreen(
		            bmain, scene, v3d, &ar, winsize, winsize, viewmat, winmat,
		            false, false, true,
		            NULL, NULL, NULL, NULL);
		GPU_shadow_depth_pass_set(false);

		if (vsm) {
			GPU_shader_unbind();
		}
		GPU_lamp_shadow_buffer_unbind(shadow->lamp);

		if (viewer_rv3d != NULL && GPU_lamp_has_cascaded_shadow(shadow->lamp)) {
			float split0, split1;
			/* Two cascades: Medium reaches the clip end and the Low map is never drawn. */
			const bool twoCascades = (shadow->la->csm_flag & LA_CSM_TWO_CASCADES) != 0;
			const float propMiddle = twoCascades ? max_ff(1.0f - shadow->la->shadow_cascade_proportion_near, 0.01f) :
			                                       shadow->la->shadow_cascade_proportion_middle;
			float dummyView[4][4], dummyWin[4][4];

			view3d_compute_cascade_shadow_matrix(
			        viewer_rv3d, shadow->obmat, shadow->la->clipsta, shadow->la->clipend,
			        shadow->la->shadow_cascade_proportion_near, propMiddle,
			        0, dummyView, dummyWin, &split0);
			view3d_compute_cascade_shadow_matrix(
			        viewer_rv3d, shadow->obmat, shadow->la->clipsta, shadow->la->clipend,
			        shadow->la->shadow_cascade_proportion_near, propMiddle,
			        1, dummyView, dummyWin, &split1);
			GPU_lamp_set_cascade_splits(shadow->lamp, split0, twoCascades ? 1.0e30f : split1);

			/* Medium = game cascade index 1 -> GPU_lamp_get_cascade(.., 0).
			 * Low    = game cascade index 2 -> GPU_lamp_get_cascade(.., 1). */
			const short gameCascadeIdx[2] = {1, 2};
			for (int c = 0; c < 2; c++) {
				GPULamp *cascadeLamp = GPU_lamp_get_cascade(shadow->lamp, c);
				if (cascadeLamp == NULL)
					continue;

				float cViewIn[4][4], cWinIn[4][4], cViewOut[4][4], cWinOut[4][4];
				float splitFarUnused;
				int cWinsize;

				view3d_compute_cascade_shadow_matrix(
				        viewer_rv3d, shadow->obmat, shadow->la->clipsta, shadow->la->clipend,
				        shadow->la->shadow_cascade_proportion_near, propMiddle,
				        (twoCascades && c == 1) ? 1 : gameCascadeIdx[c], cViewIn, cWinIn, &splitFarUnused);

				if (twoCascades && c == 1) {
					/* Low mirrors Medium's matrices (outer coverage) without a draw. */
					GPU_lamp_shadow_set_matrices(cascadeLamp, cViewIn, cWinIn);
					continue;
				}

				bool cvsm = GPU_lamp_shadow_buffer_type(cascadeLamp) == LA_SHADMAP_VARIANCE;
				if (cvsm) {
					GPU_shader_bind(GPU_shader_get_builtin_shader(GPU_SHADER_VSM_STORE));
				}

				GPU_lamp_shadow_buffer_bind_matrices(cascadeLamp, cViewIn, cWinIn, &cWinsize, cViewOut, cWinOut);

				ARegion car = {NULL};
				RegionView3D crv3d = {{{0}}};
				car.regiondata = &crv3d;
				car.regiontype = RGN_TYPE_WINDOW;
				crv3d.persp = RV3D_CAMOB;
				copy_m4_m4(crv3d.winmat, cWinOut);
				copy_m4_m4(crv3d.viewmat, cViewOut);
				invert_m4_m4(crv3d.viewinv, crv3d.viewmat);
				mul_m4_m4m4(crv3d.persmat, crv3d.winmat, crv3d.viewmat);
				invert_m4_m4(crv3d.persinv, crv3d.viewinv);

				GPU_shadow_depth_pass_set(!cvsm);
				ED_view3d_draw_offscreen(
				            bmain, scene, v3d, &car, cWinsize, cWinsize, cViewOut, cWinOut,
				            false, false, true,
				            NULL, NULL, NULL, NULL);
				GPU_shadow_depth_pass_set(false);

				if (cvsm) {
					GPU_shader_unbind();
				}
				GPU_lamp_shadow_buffer_unbind(cascadeLamp);
			}
		}

		v3d->drawtype = drawtype;
		v3d->lay = lay;
		v3d->flag2 = flag2;
	}

	BLI_freelistN(&shadows);

	/* update world values */
	if (world) {
		GPU_mist_update_enable(world->mode & WO_MIST && v3d->flag2 & V3D_SHOW_MIST &&
		                       !(world->weather_editor_hide & WO_WEATHER_FOG));
		GPU_mist_update_values(world->mistype, world->miststa, world->mistdist, world->mistheight, world->mistdensity, world->misi, &world->horr);
		GPU_horizon_update_color(&world->horr);
		GPU_ambient_update_color(&world->ambr);
		GPU_zenith_update_color(&world->zenr);
		GPU_update_exposure_range(world->exp, world->range);
		GPU_update_envlight_energy(world->ao_env_energy);
	}
}
