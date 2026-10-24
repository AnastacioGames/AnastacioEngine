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

/* Layer switch profile/prefetch and hidden-layer shader warm-up (moved from view3d_draw.c). */

/* RANGE_SHADER_LOG on: timings of a layer switch, from the operator to the end of the next viewport draw.
 * The gap between them is the scene update (derived meshes of the objects shown for the first time). */
static struct {
	bool pending;
	unsigned int lay;
	double t_begin, t_exec_end, dag_seconds;
	double buffer_seconds, shader_seconds, image_seconds;
	int shaders, images;
} layer_profile;

void view3d_layer_profile_begin(unsigned int lay, double t_begin, double dag_seconds)
{
	if (!GPU_profile_log_enabled())
		return;
	layer_profile.pending = true;
	layer_profile.lay = lay;
	layer_profile.t_begin = t_begin;
	layer_profile.t_exec_end = PIL_check_seconds_timer();
	layer_profile.dag_seconds = dag_seconds;
	layer_profile.buffer_seconds = GPU_profile_buffer_seconds;
	layer_profile.shader_seconds = GPU_profile_shader_seconds;
	layer_profile.image_seconds = GPU_profile_image_seconds;
	layer_profile.shaders = GPU_profile_counters[GPU_PROFILE_SHADERS];
	layer_profile.images = GPU_profile_counters[GPU_PROFILE_IMAGE_UPLOADS];
}

static void view3d_layer_profile_end(double t_draw_begin)
{
	char text[512];
	const double t_end = PIL_check_seconds_timer();
	layer_profile.pending = false;
	BLI_snprintf(text, sizeof(text),
	             "layer_switch lay=0x%x total_ms=%.1f dag_ms=%.1f update_ms=%.1f draw_ms=%.1f "
	             "shader_ms=%.1f shaders=%d image_ms=%.1f images=%d buffer_ms=%.1f",
	             layer_profile.lay, (t_end - layer_profile.t_begin) * 1000.0, layer_profile.dag_seconds * 1000.0,
	             (t_draw_begin - layer_profile.t_exec_end) * 1000.0, (t_end - t_draw_begin) * 1000.0,
	             (GPU_profile_shader_seconds - layer_profile.shader_seconds) * 1000.0,
	             GPU_profile_counters[GPU_PROFILE_SHADERS] - layer_profile.shaders,
	             (GPU_profile_image_seconds - layer_profile.image_seconds) * 1000.0,
	             GPU_profile_counters[GPU_PROFILE_IMAGE_UPLOADS] - layer_profile.images,
	             (GPU_profile_buffer_seconds - layer_profile.buffer_seconds) * 1000.0);
	GPU_profile_log_line(text);
}

/* Programs sent by view3d_layer_prefetch_materials, dropped after the next draw if nobody took them. */
static bool layer_prefetch_pending = false;

void view3d_layer_prefetch_materials(Main *bmain, Scene *scene, View3D *v3d, unsigned int lay_new)
{
	static int disabled = -1;
	if (disabled == -1) {
		disabled = getenv("RANGE_NO_PARALLEL_SHADERS") != NULL;
	}
	if (disabled || !lay_new || !GPU_shader_prefetch_begin()) {
		return;
	}
	BKE_main_id_tag_idcode(bmain, ID_MA, LIB_TAG_DOIT, false);
	int sent = 0;
	Scene *sce_iter;
	Base *base;
	for (SETLOOPER(scene, sce_iter, base)) {
		Object *ob = base->object;
		if (!(base->lay & lay_new) || !ELEM(ob->type, OB_MESH, OB_CURVE, OB_SURF, OB_FONT, OB_MBALL)) {
			continue;
		}
		/* Same test as the draw (draw_glsl_material), with the object draw type the viewport limits it to. */
		if (!draw_glsl_material(scene, ob, v3d, MIN2(ob->dt, v3d->drawtype))) {
			continue;
		}
		for (int i = 1; i <= ob->totcol; i++) {
			Material *ma = give_current_material(ob, i);
			if (ma && !(ma->id.tag & LIB_TAG_DOIT)) {
				ma->id.tag |= LIB_TAG_DOIT;
				sent += GPU_material_prefetch_viewport(scene, ma) ? 1 : 0;
			}
		}
	}
	GPU_shader_prefetch_end();
	BKE_main_id_tag_idcode(bmain, ID_MA, LIB_TAG_DOIT, false);
	layer_prefetch_pending = sent > 0;
}

/* Start of a viewport draw: timestamp only when a layer switch is being profiled. */
double view3d_layer_profile_draw_begin(void)
{
	return layer_profile.pending ? PIL_check_seconds_timer() : 0.0;
}

/* End of a viewport draw: closes the layer switch profile and drops unused prefetched programs. */
void view3d_layer_profile_draw_end(double t_draw_begin)
{
	if (layer_profile.pending)
		view3d_layer_profile_end(t_draw_begin);
	if (layer_prefetch_pending) {
		layer_prefetch_pending = false;
		GPU_shader_prefetch_clear();
	}
}


/* -------------------------------------------------------------------- */
/* Warmup of hidden layers: after a file opens or the scene changes, the objects of the layers this view doesn't
 * show are drawn a few per frame with color and depth writes off. Their materials, buffers and images get built
 * and drivers that compile on the first real draw (AMD) do it now, so showing those layers later doesn't freeze.
 * A job only shows the progress bar (and cancel button) in the Info header. RANGE_NO_SHADER_WARMUP=1 turns it off. */

static struct {
	Main *bmain;
	Scene *scene;
	unsigned int lay;   /* layers visible when it started: the others are warmed */
	int index, done, total;
	bool active;
	double start_time;  /* draws begin WARMUP_DELAY_SECONDS after this, so the interface shows up first */
	short *stop;
} warmup = {NULL};

#define WARMUP_DELAY_SECONDS 3.0

/* Time per frame spent drawing hidden objects (one slow driver compile can still take longer). */
#define WARMUP_FRAME_SECONDS 0.03

void ED_view3d_shader_warmup_reset(void)
{
	GPU_profile_log_line("warmup_reset");
	warmup.bmain = NULL;
	warmup.scene = NULL;
	warmup.active = false;
}

static bool warmup_candidate(Scene *scene, View3D *v3d, Base *base)
{
	Object *ob = base->object;
	return !(base->lay & warmup.lay) && (ob->restrictflag & OB_RESTRICT_VIEW) == 0 &&
	       ELEM(ob->type, OB_MESH, OB_CURVE, OB_SURF, OB_FONT, OB_MBALL) &&
	       draw_glsl_material(scene, ob, v3d, MIN2(ob->dt, v3d->drawtype));
}

static void warmup_job_free(void *customdata)
{
	MEM_freeN(customdata);
}

/* Thread: only mirrors the progress made by the draws until they finish or the job is canceled. */
static void warmup_job_start(void *UNUSED(customdata), short *stop, short *do_update, float *progress)
{
	warmup.stop = stop;
	while (!*stop && warmup.active) {
		*progress = warmup.total ? (float)warmup.done / (float)warmup.total : 1.0f;
		/* The job timer then sends the 3D View redraw note that runs the next step. */
		*do_update = true;
		PIL_sleep_ms(30);
	}
	warmup.stop = NULL;
	*progress = 1.0f;
}

void view3d_warmup_step(const bContext *C, Main *bmain, Scene *scene, ARegion *ar, View3D *v3d)
{
	static int disabled = -1;
	if (disabled == -1) {
		disabled = getenv("RANGE_NO_SHADER_WARMUP") != NULL;
	}
	if (disabled || G.f & G_PICKSEL) {
		return;
	}
	wmWindowManager *wm = CTX_wm_manager(C);

	if (bmain != warmup.bmain || scene != warmup.scene) {
		/* New file or scene: count what the other layers would draw. */
		warmup.bmain = bmain;
		warmup.scene = scene;
		warmup.lay = v3d->lay;
		warmup.index = warmup.done = warmup.total = 0;
		Scene *sce_iter;
		Base *base;
		for (SETLOOPER(scene, sce_iter, base)) {
			warmup.total += warmup_candidate(scene, v3d, base) ? 1 : 0;
		}
		warmup.active = warmup.total > 0 && !WM_jobs_test(wm, scene, WM_JOB_TYPE_ANY);
		warmup.start_time = PIL_check_seconds_timer();
		if (GPU_profile_log_enabled()) {
			char text[200];
			BLI_snprintf(text, sizeof(text), "warmup_start file=%s scene=%s objects=%d drawtype=%d lay=0x%x",
			             BLI_path_basename(bmain->name), scene->id.name + 2, warmup.total, v3d->drawtype, v3d->lay);
			GPU_profile_log_line(text);
		}
		if (warmup.active) {
			wmJob *wm_job = WM_jobs_get(wm, CTX_wm_window(C), scene, "Preparing Layers", WM_JOB_PROGRESS,
			                            WM_JOB_TYPE_SHADER_WARMUP);
			WM_jobs_customdata_set(wm_job, MEM_callocN(sizeof(int), "warmup job"), warmup_job_free);
			WM_jobs_timer(wm_job, 0.05, NC_SPACE | ND_SPACE_VIEW3D, NC_SPACE | ND_SPACE_VIEW3D);
			WM_jobs_callbacks(wm_job, warmup_job_start, NULL, NULL, NULL);
			WM_jobs_start(wm, wm_job);
		}
	}
	if (!warmup.active) {
		return;
	}
	if (warmup.stop && *warmup.stop) {
		warmup.active = false;
		return;
	}
	if (PIL_check_seconds_timer() - warmup.start_time < WARMUP_DELAY_SECONDS) {
		return;
	}

	const double t_begin = PIL_check_seconds_timer();
	RegionView3D *rv3d = ar->regiondata;
	GLboolean color_mask[4], depth_mask;
	glGetBooleanv(GL_COLOR_WRITEMASK, color_mask);
	glGetBooleanv(GL_DEPTH_WRITEMASK, &depth_mask);
	glColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE);
	glDepthMask(GL_FALSE);
	glMatrixMode(GL_PROJECTION);
	glLoadMatrixf(rv3d->winmat);
	glMatrixMode(GL_MODELVIEW);
	glLoadMatrixf(rv3d->viewmat);

	int index = 0;
	Scene *sce_iter;
	Base *base;
	for (SETLOOPER(scene, sce_iter, base)) {
		if (index++ < warmup.index) {
			continue;
		}
		warmup.index = index;
		if (!warmup_candidate(scene, v3d, base)) {
			continue;
		}
		const double t0 = PIL_check_seconds_timer();
		draw_object(bmain, scene, ar, v3d, base, 0);
		warmup.done++;
		if (GPU_profile_log_enabled() && PIL_check_seconds_timer() - t0 >= 0.01) {
			char text[160];
			BLI_snprintf(text, sizeof(text), "warmup %s ms=%.1f", base->object->id.name + 2,
			             (PIL_check_seconds_timer() - t0) * 1000.0);
			GPU_profile_log_line(text);
		}
		if (PIL_check_seconds_timer() - t_begin >= WARMUP_FRAME_SECONDS) {
			break;
		}
	}
	if (base == NULL || warmup.done >= warmup.total) {
		warmup.active = false;
		/* Kept even if the editor closes badly later. */
		GPU_shader_editor_cache_save();
	}

	/* Transparent / x-ray objects queue themselves for a later pass: the hidden ones must not be drawn by it. */
	BLI_freelistN(&v3d->afterdraw_transp);
	BLI_freelistN(&v3d->afterdraw_xray);
	BLI_freelistN(&v3d->afterdraw_xraytransp);
	glColorMask(color_mask[0], color_mask[1], color_mask[2], color_mask[3]);
	glDepthMask(depth_mask);
}
