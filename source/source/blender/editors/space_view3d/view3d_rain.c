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

/** \file blender/editors/space_view3d/view3d_rain.c
 *  \ingroup spview3d
 *
 * World > Rain > Lightning and Aura in the 3D View, matching the game engine
 * (KX_RainLightning, KX_RainAura). The flash itself is applied by the rain
 * compositor pass; here only the geometry is drawn, additive and depth tested.
 * The viewport has no frame history, so the aura is drawn statelessly: every
 * redraw spawns the number of strokes that would be alive in game.
 */

#include <math.h>

#include "MEM_guardedalloc.h"

#include "DNA_mesh_types.h"
#include "DNA_meshdata_types.h"
#include "DNA_object_types.h"
#include "DNA_property_types.h"
#include "DNA_scene_types.h"
#include "DNA_screen_types.h"
#include "DNA_view3d_types.h"
#include "DNA_world_types.h"

#include "BLI_math.h"
#include "BLI_rand.h"
#include "BLI_utildefines.h"

#include "BKE_mesh.h"
#include "BKE_property.h"
#include "BKE_rain_lightning.h"

#include "GPU_glew.h"
#include "GPU_shader.h"

#include "PIL_time.h"

#include "view3d_intern.h"

/* Same constants as KX_RainAura. */
#define AURA_UP 0.25f
#define AURA_STROKES_PER_METER 900.0f
#define AURA_AVERAGE_LIFE 0.0325f
#define AURA_REFERENCE_DISTANCE 3.0f
#define AURA_MAX_STROKES 4096
#define AURA_ANIMATED_RATE_SCALE 0.12f
#define AURA_ANIMATED_GRAVITY 0.35f
/* Mean life of an animated drop (0.25 to 0.55 s). */
#define AURA_ANIMATED_LIFE 0.4f

static const char *bolt_vert =
	"out vec2 v_uv;\n"
	"out float v_bright;\n"
	"void main() {\n"
	"	v_uv = gl_MultiTexCoord0.xy;\n"
	"	v_bright = gl_Color.r;\n"
	"	gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;\n"
	"}\n";

/* Same profile as KX_RainLightning: gaussian core and glow with round ends. */
static const char *bolt_frag =
	"in vec2 v_uv;\n"
	"in float v_bright;\n"
	"uniform float u_bright;\n"
	"uniform float u_glowRatio;\n"
	"uniform vec3 u_color;\n"
	"void main() {\n"
	"	float r = length(v_uv);\n"
	"	float c = r * u_glowRatio;\n"
	"	float core = exp(-c * c * 2.0);\n"
	"	float glow = exp(-r * r * 6.0) * (1.0 - smoothstep(0.8, 1.0, r));\n"
	"	vec3 col = vec3(1.0) * core + u_color * glow * 0.35;\n"
	"	gl_FragColor = vec4(col * v_bright * u_bright, 1.0);\n"
	"}\n";

static GPUShader *bolt_shader = NULL;
static bool bolt_shader_failed = false;

static bool bolt_shader_ensure(void)
{
	if (!bolt_shader && !bolt_shader_failed) {
		bolt_shader = GPU_shader_create(bolt_vert, bolt_frag, NULL, NULL, NULL, 0, 0, 0);
		bolt_shader_failed = (bolt_shader == NULL);
	}
	return bolt_shader != NULL;
}

/* One camera facing ribbon per strip, with round caps (same as KX_RainLightning). */
static void draw_bolt_geometry(const RainLightningBolt *bolt, float bright, const float color[3], const float cam_pos[3])
{
	GPU_shader_bind(bolt_shader);
	GPU_shader_uniform_float(bolt_shader, GPU_shader_get_uniform(bolt_shader, "u_bright"), bright);
	GPU_shader_uniform_float(bolt_shader, GPU_shader_get_uniform(bolt_shader, "u_glowRatio"),
	                         RAIN_LIGHTNING_GLOW_RATIO);
	GPU_shader_uniform_vector(bolt_shader, GPU_shader_get_uniform(bolt_shader, "u_color"), 3, 1, color);

	for (int s = 0; s < bolt->num_strips; s++) {
		const int start = bolt->strip_start[s];
		const int n = bolt->strip_len[s];
		if (n < 2) {
			continue;
		}
		glBegin(GL_TRIANGLE_STRIP);
		/* One extra row past each end: the round caps. */
		for (int row = -1; row <= n; row++) {
			const int i = max_ii(0, min_ii(row, n - 1));
			float pos[3], side[3];
			float v = 0.0f;
			copy_v3_v3(pos, bolt->co[start + i]);
			BKE_rain_lightning_side(bolt, s, i, cam_pos, side);
			if (row != i) {
				float out[3];
				sub_v3_v3v3(out, pos, bolt->co[start + ((row < 0) ? 1 : n - 2)]);
				if (normalize_v3(out) < 1e-6f) {
					out[0] = out[1] = 0.0f;
					out[2] = 1.0f;
				}
				madd_v3_v3fl(pos, out, bolt->half_width[start + i]);
				v = 1.0f;
			}
			glColor3f(bolt->bright[start + i], 0.0f, 0.0f);
			for (int k = -1; k <= 1; k += 2) {
				glTexCoord2f((float)k, v);
				glVertex3f(pos[0] + side[0] * k, pos[1] + side[1] * k, pos[2] + side[2] * k);
			}
		}
		glEnd();
	}

	GPU_shader_unbind();
}

static void draw_bolt(World *world, RegionView3D *rv3d)
{
	static const float color[3] = {0.65f, 0.72f, 1.0f};
	float flash, bright;
	unsigned int seed;
	if (!BKE_rain_lightning_eval(world->rain_lightning_rate, world->rain_lightning_intensity,
	                             PIL_check_seconds_timer(), &flash, &bright, &seed) ||
	    bright <= 0.001f || !bolt_shader_ensure())
	{
		return;
	}

	/* Clip end from the projection, like the compositor does for the halo. */
	const float clip_end = rv3d->is_persp ? rv3d->winmat[3][2] / (rv3d->winmat[2][2] + 1.0f) : 0.0f;
	RainLightningBolt bolt;
	BKE_rain_lightning_view_bolt(seed, rv3d->viewinv, clip_end,
	                             world->rain_lightning_distance, world->rain_lightning_width, &bolt);
	draw_bolt_geometry(&bolt, bright, color, rv3d->viewinv[3]);
}

bool view3d_lightning_emitter_preview(const Object *ob)
{
	return ob->type == OB_EMPTY && (ob->gameflag2 & OB_LIGHTNING) &&
	       (ob->lightning.flags & LIGHTNING_PREVIEW) && ob->lightning.mode == LIGHTNING_MODE_AUTOMATIC;
}

/* Lightning emitters: their automatic strikes on the real clock (the time window is game time,
 * ignored here). No ground ray in the editor: the bolt ends at the Empty's height. */
static void draw_emitter_bolts(Scene *scene, View3D *v3d, RegionView3D *rv3d)
{
	const double now = PIL_check_seconds_timer();
	for (Base *base = scene->base.first; base; base = base->next) {
		Object *ob = base->object;
		if (!(v3d->lay & base->lay) || (ob->restrictflag & OB_RESTRICT_VIEW) || !view3d_lightning_emitter_preview(ob)) {
			continue;
		}
		const RangeLightningSettings *ls = &ob->lightning;
		double start;
		unsigned int seed;
		bool big;
		if (!BKE_rain_lightning_schedule_ex(ls->rate, BKE_rain_lightning_salt(ob->id.name + 2), ls->big_chance,
		                                    now, &start, &seed, &big) || !big)
		{
			continue;
		}
		const float flash = BKE_rain_lightning_flash(seed, big, (float)(now - start), NULL);
		const float bright = min_ff(flash * 1.6f, 1.0f) * ls->intensity;
		if (bright <= 0.001f || !bolt_shader_ensure()) {
			continue;
		}
		float ground[3];
		RainLightningBolt bolt;
		BKE_rain_lightning_strike_point(seed, ob->obmat, ob->empty_drawsize, ls->shape == LIGHTNING_SHAPE_BOX, ground);
		if (ls->target) {
			BKE_rain_lightning_bolt_between(seed, ground, ls->target->obmat[3], ls->width, &bolt);
		}
		else {
			BKE_rain_lightning_bolt_at(seed, ground, ground[2] + ls->height, ls->width, &bolt);
		}
		draw_bolt_geometry(&bolt, bright, ls->color, rv3d->viewinv[3]);
	}
}

typedef struct AuraEdge {
	float a[3], b[3], out[3], view[3];
	float scale;
} AuraEdge;

/* Upper silhouette edges of one object, seen from the camera (same test as KX_RainAura). */
static void aura_collect(Object *ob, const float cam_pos[3], AuraEdge **edges, int *num, int *cap, float *total)
{
	Mesh *me = ob->data;
	if (me->totedge == 0 || me->totpoly == 0) {
		return;
	}

	/* The two faces of every edge. */
	int(*edge_faces)[2] = MEM_mallocN(sizeof(int[2]) * me->totedge, __func__);
	float(*poly_nors)[3] = MEM_mallocN(sizeof(float[3]) * me->totpoly, __func__);
	for (int e = 0; e < me->totedge; e++) {
		edge_faces[e][0] = edge_faces[e][1] = -1;
	}
	for (int p = 0; p < me->totpoly; p++) {
		const MPoly *mp = &me->mpoly[p];
		BKE_mesh_calc_poly_normal(mp, &me->mloop[mp->loopstart], me->mvert, poly_nors[p]);
		for (int l = 0; l < mp->totloop; l++) {
			int *f = edge_faces[me->mloop[mp->loopstart + l].e];
			if (f[0] == -1) {
				f[0] = p;
			}
			else if (f[1] == -1) {
				f[1] = p;
			}
			else {
				f[0] = -2; /* non-manifold */
			}
		}
	}

	float nmat[3][3];
	copy_m3_m4(nmat, ob->obmat);
	invert_m3(nmat);
	transpose_m3(nmat);

	for (int e = 0; e < me->totedge; e++) {
		const int *f = edge_faces[e];
		if (f[0] < 0 || f[1] < 0 || dot_v3v3(poly_nors[f[0]], poly_nors[f[1]]) >= 0.9999f) {
			continue;
		}
		float wa[3], wb[3], mid[3], vn[3], n1[3], n2[3], out[3];
		mul_v3_m4v3(wa, ob->obmat, me->mvert[me->medge[e].v1].co);
		mul_v3_m4v3(wb, ob->obmat, me->mvert[me->medge[e].v2].co);
		mid_v3_v3v3(mid, wa, wb);
		sub_v3_v3v3(vn, cam_pos, mid);
		mul_v3_m3v3(n1, nmat, poly_nors[f[0]]);
		mul_v3_m3v3(n2, nmat, poly_nors[f[1]]);
		/* One face looks at the camera, the other looks away. */
		if (dot_v3v3(n1, vn) * dot_v3v3(n2, vn) >= 0.0f) {
			continue;
		}
		const float dist = normalize_v3(vn);
		normalize_v3(n1);
		normalize_v3(n2);
		add_v3_v3v3(out, n1, n2);
		madd_v3_v3fl(out, vn, -dot_v3v3(out, vn));
		if (normalize_v3(out) < 1e-6f || out[2] < AURA_UP) {
			continue;
		}
		if (*num == *cap) {
			*cap = max_ii(*cap * 2, 256);
			*edges = MEM_reallocN(*edges, sizeof(AuraEdge) * *cap);
		}
		AuraEdge *edge = &(*edges)[(*num)++];
		copy_v3_v3(edge->a, wa);
		copy_v3_v3(edge->b, wb);
		copy_v3_v3(edge->out, out);
		copy_v3_v3(edge->view, vn);
		/* Constant size on screen, like in game. */
		edge->scale = max_ff(0.3f, dist / AURA_REFERENCE_DISTANCE);
		*total += len_v3v3(wa, wb) / edge->scale;
	}

	MEM_freeN(edge_faces);
	MEM_freeN(poly_nors);
}

static void draw_aura(Scene *scene, View3D *v3d, World *world, RegionView3D *rv3d)
{
	if (world->rain_aura_prop[0] == '\0') {
		return;
	}
	const float *cam_pos = rv3d->viewinv[3];
	AuraEdge *edges = NULL;
	int num = 0, cap = 0;
	float total = 0.0f;

	for (Base *base = scene->base.first; base; base = base->next) {
		Object *ob = base->object;
		if (!(v3d->lay & base->lay) || ob->type != OB_MESH || ob == scene->obedit || (ob->restrictflag & OB_RESTRICT_VIEW)) {
			continue;
		}
		bProperty *prop = BKE_bproperty_object_get(ob, world->rain_aura_prop);
		if (!prop || prop->data == 0) {
			continue;
		}
		if (len_v3v3(ob->obmat[3], cam_pos) > world->rain_aura_distance) {
			continue;
		}
		aura_collect(ob, cam_pos, &edges, &num, &cap, &total);
	}
	if (num == 0) {
		MEM_SAFE_FREE(edges);
		return;
	}

	/* The strokes alive at any moment in game: spawn rate times their mean life. */
	const bool animated = (world->rain_aura_style == WO_RAIN_AURA_ANIMATED);
	const float alive = animated ? AURA_ANIMATED_RATE_SCALE * AURA_ANIMATED_LIFE : AURA_AVERAGE_LIFE;
	const int count = min_ii((int)(total * AURA_STROKES_PER_METER * world->rain_aura_rate * alive), AURA_MAX_STROKES);
	const double now = PIL_check_seconds_timer();
	float *cumulative = MEM_mallocN(sizeof(float) * num, __func__);
	float sum = 0.0f;
	for (int i = 0; i < num; i++) {
		sum += len_v3v3(edges[i].a, edges[i].b) / edges[i].scale;
		cumulative[i] = sum;
	}

	RNG *rng = BLI_rng_new((unsigned int)(PIL_check_seconds_timer() * 1000.0));
	const float size = world->rain_aura_size;
	const float intensity = world->rain_aura_intensity;

	glBegin(GL_QUADS);
	for (int c = 0; c < count; c++) {
		/* Animated: no state between redraws, so each slot c replays a drop cycle by the clock and
		 * reseeds per cycle, keeping the same drop (edge, direction) for its whole flight. */
		float age = 0.0f, life = 1.0f;
		if (animated) {
			BLI_rng_seed(rng, (unsigned int)c * 2654435761u);
			life = 0.25f + 0.3f * BLI_rng_get_float(rng);
			const double cycle = now / life + BLI_rng_get_float(rng);
			const double gen = floor(cycle);
			age = (float)(cycle - gen) * life;
			BLI_rng_seed(rng, ((unsigned int)c * 2654435761u) ^ ((unsigned int)(gen) * 40503u + 0x9E3779B9u));
		}
		/* Pick an edge by its length on screen. */
		const float r = BLI_rng_get_float(rng) * sum;
		int lo = 0, hi = num - 1;
		while (lo < hi) {
			const int mid = (lo + hi) / 2;
			if (cumulative[mid] < r) {
				lo = mid + 1;
			}
			else {
				hi = mid;
			}
		}
		const AuraEdge *edge = &edges[lo];

		/* Fan around the outward direction, sum of 3 uniforms ~ gauss(0, 0.6). */
		const float g = BLI_rng_get_float(rng) + BLI_rng_get_float(rng) + BLI_rng_get_float(rng) - 1.5f;
		const float ang = CLAMPIS(g * 1.2f, -1.2f, 1.2f);
		float side[3], z[3], base[3], y[3], x[3];
		cross_v3_v3v3(side, edge->view, edge->out);
		mul_v3_v3fl(z, edge->out, cosf(ang));
		madd_v3_v3fl(z, side, sinf(ang));
		normalize_v3(z);

		const float scale = size * edge->scale;
		const float width = (0.0006f + 0.0012f * BLI_rng_get_float(rng)) * scale;
		float length, fade = 1.0f;
		if (animated) {
			/* Same flight as KX_RainAura: out along z, bent down by a light gravity. */
			const float path = (0.04f + 0.08f * BLI_rng_get_float(rng)) * scale;
			length = (0.006f + 0.008f * BLI_rng_get_float(rng)) * scale;
			interp_v3_v3v3(base, edge->a, edge->b, BLI_rng_get_float(rng));
			madd_v3_v3fl(base, z, 0.002f * BLI_rng_get_float(rng) * scale);
			const float speed = path / life;
			const float fall = AURA_ANIMATED_GRAVITY * scale;
			float vel[3];
			mul_v3_v3fl(vel, z, speed);
			madd_v3_v3fl(base, z, speed * age);
			base[2] -= 0.5f * fall * age * age;
			vel[2] -= fall * age;
			normalize_v3_v3(z, vel);
			const float t = age / life;
			fade = min_ff(1.0f, t * 8.0f) * max_ff(0.0f, 1.0f - t);
		}
		else {
			length = ((BLI_rng_get_float(rng) < 0.5f) ?
			          (0.002f + 0.003f * BLI_rng_get_float(rng)) :
			          (0.006f + 0.01f * BLI_rng_get_float(rng))) * scale;
			interp_v3_v3v3(base, edge->a, edge->b, BLI_rng_get_float(rng));
			madd_v3_v3fl(base, z, (0.001f + 0.011f * BLI_rng_get_float(rng)) * scale);
		}

		sub_v3_v3v3(y, cam_pos, base);
		madd_v3_v3fl(y, z, -dot_v3v3(y, z));
		if (normalize_v3(y) < 1e-6f) {
			copy_v3_v3(y, edge->view);
		}
		cross_v3_v3v3(x, y, z);
		mul_v3_fl(x, width * 0.5f);

		const float b = (0.6f + 0.4f * BLI_rng_get_float(rng)) * intensity * fade;
		glColor3f(0.85f * b, 0.9f * b, 1.0f * b);
		glVertex3f(base[0] - x[0], base[1] - x[1], base[2] - x[2]);
		glVertex3f(base[0] + x[0], base[1] + x[1], base[2] + x[2]);
		glVertex3f(base[0] + x[0] + z[0] * length, base[1] + x[1] + z[1] * length, base[2] + x[2] + z[2] * length);
		glVertex3f(base[0] - x[0] + z[0] * length, base[1] - x[1] + z[1] * length, base[2] - x[2] + z[2] * length);
	}
	glEnd();

	BLI_rng_free(rng);
	MEM_freeN(cumulative);
	MEM_freeN(edges);
}

void view3d_draw_rain_effects(Scene *scene, View3D *v3d, RegionView3D *rv3d)
{
	World *world = scene->world;
	const bool world_fx = world && (world->weather_flag & WO_WEATHER_RAIN) &&
	                      (world->weather_flag & (WO_WEATHER_RAIN_AURA | WO_WEATHER_RAIN_LIGHTNING));
	bool emitters = false;
	for (Base *base = scene->base.first; base && !emitters; base = base->next) {
		emitters = view3d_lightning_emitter_preview(base->object);
	}
	if (!world_fx && !emitters) {
		return;
	}

	glPushAttrib(GL_ENABLE_BIT | GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT | GL_CURRENT_BIT);
	glEnable(GL_DEPTH_TEST);
	glDepthMask(GL_FALSE);
	glDisable(GL_CULL_FACE);
	glDisable(GL_LIGHTING);
	glEnable(GL_BLEND);
	glBlendFunc(GL_ONE, GL_ONE);

	if (world_fx && (world->weather_flag & WO_WEATHER_RAIN_AURA)) {
		draw_aura(scene, v3d, world, rv3d);
	}
	if (world_fx && (world->weather_flag & WO_WEATHER_RAIN_LIGHTNING)) {
		draw_bolt(world, rv3d);
	}
	if (emitters) {
		draw_emitter_bolts(scene, v3d, rv3d);
	}

	glPopAttrib();
}
