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

/** \file blender/blenkernel/intern/rain_lightning.c
 *  \ingroup bke
 */

#include <math.h>
#include <string.h>

#include "BLI_math.h"
#include "BLI_utildefines.h"

#include "BKE_rain_lightning.h"

/* Share of automatic strikes that show a bolt; the others are a far flash only. */
#define BIG_CHANCE 0.65f
/* The bolt was designed 80 m away; everything scales with the distance. */
#define REFERENCE_DISTANCE 80.0f

static unsigned int hash_uint(unsigned int x)
{
	x ^= x >> 16;
	x *= 0x7feb352dU;
	x ^= x >> 15;
	x *= 0x846ca68bU;
	x ^= x >> 16;
	return x;
}

typedef struct Rng {
	unsigned int state;
} Rng;

static float rng_float(Rng *rng)
{
	/* xorshift32: cheap and plenty for a visual effect. */
	rng->state ^= rng->state << 13;
	rng->state ^= rng->state >> 17;
	rng->state ^= rng->state << 5;
	return (float)(rng->state >> 8) * (1.0f / 16777216.0f);
}

static float rng_range(Rng *rng, float a, float b)
{
	return a + (b - a) * rng_float(rng);
}

static int rng_int(Rng *rng, int a, int b)
{
	return min_ii(a + (int)(rng_float(rng) * (float)(b - a + 1)), b);
}

/* Sum of 3 uniforms: close enough to a unit gaussian. */
static float rng_gauss(Rng *rng)
{
	return (rng_float(rng) + rng_float(rng) + rng_float(rng) - 1.5f) * 2.0f;
}

static Rng rng_seed(unsigned int seed)
{
	Rng rng = {hash_uint(seed) | 1u};
	return rng;
}

bool BKE_rain_lightning_schedule_ex(
        float rate, unsigned int salt, float big_chance, double time,
        double *r_start, unsigned int *r_seed, bool *r_big)
{
	if (rate <= 0.0f) {
		return false;
	}
	/* One strike somewhere in each period, so the gaps vary from 0.2 to 1.8 periods. */
	const double period = 60.0 / (double)rate;
	const long long slot = (long long)floor(time / period);
	for (long long s = slot; s >= slot - 1; s--) {
		const unsigned int h = hash_uint((unsigned int)s * 2654435761u + 0x51ed27u + salt * 0x9e3779b9u);
		const double start = ((double)s + 0.8 * (double)(h >> 8) / 16777216.0) * period;
		if (start <= time) {
			*r_start = start;
			*r_seed = hash_uint(h + 1u);
			*r_big = (float)(hash_uint(h + 2u) >> 8) / 16777216.0f < big_chance;
			return true;
		}
	}
	return false;
}

bool BKE_rain_lightning_schedule(float rate, double time, double *r_start, unsigned int *r_seed, bool *r_big)
{
	return BKE_rain_lightning_schedule_ex(rate, 0u, BIG_CHANCE, time, r_start, r_seed, r_big);
}

float BKE_rain_lightning_flash(unsigned int seed, bool big, float t, bool *r_over)
{
	/* Real strikes flicker: 2 to 4 return strokes, the last one lasting a bit longer. */
	Rng rng = rng_seed(seed ^ 0xa511e9b3u);
	const int n = big ? rng_int(&rng, 2, 4) : rng_int(&rng, 1, 2);
	float start = 0.0f, flash = 0.0f, end = 0.0f;
	for (int k = 0; k < n; k++) {
		const float peak = big ? rng_range(&rng, 0.7f, 1.0f) : rng_range(&rng, 0.2f, 0.4f);
		const float tau = (k < n - 1) ? rng_range(&rng, 0.05f, 0.1f) : rng_range(&rng, 0.18f, 0.3f);
		if (t >= start) {
			flash = max_ff(flash, peak * expf(-(t - start) / tau));
		}
		end = start + tau * 6.0f;
		start += tau * 1.5f + rng_range(&rng, 0.03f, 0.09f);
	}
	if (r_over) {
		*r_over = (t < 0.0f) || (t > end);
	}
	return (t < 0.0f || t > end) ? 0.0f : flash;
}

/* Midpoint displacement: every level splits each segment and pushes the middle sideways. */
static int jitter(Rng *rng, const float a[3], const float b[3], float disp, int levels, float (*r_co)[3], int max_points)
{
	float tmp[RAIN_LIGHTNING_MAX_POINTS][3];
	int n = 2;
	copy_v3_v3(r_co[0], a);
	copy_v3_v3(r_co[1], b);
	for (int level = 0; level < levels && n * 2 - 1 <= max_points; level++) {
		int m = 0;
		for (int i = 0; i < n - 1; i++) {
			float d[3], off[3], mid[3];
			sub_v3_v3v3(d, r_co[i + 1], r_co[i]);
			normalize_v3(d);
			off[0] = rng_gauss(rng);
			off[1] = rng_gauss(rng);
			off[2] = rng_gauss(rng) * 0.3f;
			madd_v3_v3fl(off, d, -dot_v3v3(off, d));
			mid_v3_v3v3(mid, r_co[i], r_co[i + 1]);
			madd_v3_v3fl(mid, off, disp);
			copy_v3_v3(tmp[m++], r_co[i]);
			copy_v3_v3(tmp[m++], mid);
		}
		copy_v3_v3(tmp[m++], r_co[n - 1]);
		memcpy(r_co, tmp, sizeof(float[3]) * m);
		n = m;
		disp *= 0.55f;
	}
	return n;
}

static void add_strip(RainLightningBolt *bolt, Rng *rng, const float a[3], const float b[3], float disp, int levels,
                      float half_width, float bright, float tip_bright)
{
	if (bolt->num_strips >= RAIN_LIGHTNING_MAX_STRIPS) {
		return;
	}
	const int start = (bolt->num_strips == 0) ? 0 : bolt->strip_start[bolt->num_strips - 1] + bolt->strip_len[bolt->num_strips - 1];
	const int room = RAIN_LIGHTNING_MAX_POINTS - start;
	if (room < 2) {
		return;
	}
	const int n = jitter(rng, a, b, disp, levels, &bolt->co[start], room);
	for (int i = 0; i < n; i++) {
		const float f = (float)i / (float)(n - 1);
		bolt->bright[start + i] = bright * (1.0f - f) + tip_bright * f;
		/* Branches get thinner toward the tip too. */
		bolt->half_width[start + i] = half_width * (1.0f - (1.0f - tip_bright / bright) * 0.5f * f);
	}
	bolt->strip_start[bolt->num_strips] = start;
	bolt->strip_len[bolt->num_strips] = n;
	bolt->num_strips++;
}

/* The main channel from top to ground, then 2-5 branches leaving its upper part. */
static void build_bolt(Rng *rng, const float top[3], const float ground[3], float k, float width,
                       RainLightningBolt *r_bolt)
{
	r_bolt->num_strips = 0;
	const float core = 0.25f * width * k;
	add_strip(r_bolt, rng, top, ground, 9.0f * k, 6, core * RAIN_LIGHTNING_GLOW_RATIO, 1.0f, 1.0f);

	/* Branches: shorter, thinner and dimmer, leaving the upper part of the main channel. */
	const int main_len = r_bolt->strip_len[0];
	const int branches = rng_int(rng, 2, 5);
	for (int b = 0; b < branches; b++) {
		const int i = rng_int(rng, main_len / 8, (int)(main_len * 0.6f));
		const float *start = r_bolt->co[i];
		float down[3], out[3], dir[3], end[3];
		sub_v3_v3v3(down, r_bolt->co[min_ii(i + 4, main_len - 1)], start);
		normalize_v3(down);
		out[0] = rng_gauss(rng);
		out[1] = rng_gauss(rng);
		out[2] = 0.0f;
		normalize_v3(out);
		mul_v3_v3fl(dir, down, 0.6f);
		madd_v3_v3fl(dir, out, 0.8f);
		normalize_v3(dir);
		copy_v3_v3(end, start);
		madd_v3_v3fl(end, dir, rng_range(rng, 8.0f, 22.0f) * k);
		add_strip(r_bolt, rng, start, end, 3.5f * k, 4, core * 0.55f * RAIN_LIGHTNING_GLOW_RATIO, 0.6f, 0.15f);
	}

	mid_v3_v3v3(r_bolt->center, top, ground);
}

void BKE_rain_lightning_bolt(
        unsigned int seed, const float cam_pos[3], const float cam_fwd[3], float distance, float width,
        bool sideways, RainLightningBolt *r_bolt)
{
	Rng rng = rng_seed(seed);
	const float k = max_ff(distance, 1.0f) / REFERENCE_DISTANCE;
	float fwd[3] = {cam_fwd[0], cam_fwd[1], 0.0f};
	if (normalize_v3(fwd) < 1e-3f) {
		fwd[0] = 0.0f;
		fwd[1] = 1.0f;
	}
	const float side[3] = {-fwd[1], fwd[0], 0.0f};

	/* Somewhere in front of the camera, from the clouds down to about the camera's ground. */
	const float dist = distance * rng_range(&rng, 0.65f, 1.35f);
	float ground[3], top[3];
	copy_v3_v3(ground, cam_pos);
	madd_v3_v3fl(ground, fwd, dist);
	madd_v3_v3fl(ground, side, rng_range(&rng, -0.45f, 0.45f) * dist);
	ground[2] = cam_pos[2] - 2.0f;
	copy_v3_v3(top, ground);
	madd_v3_v3fl(top, side, rng_range(&rng, -15.0f, 15.0f) * k);
	madd_v3_v3fl(top, fwd, rng_range(&rng, -10.0f, 10.0f) * k);
	top[2] = ground[2] + rng_range(&rng, 55.0f, 75.0f) * k;

	/* Sideways: half of the strikes run across the clouds instead of down to the ground. Its
	 * own hash keeps the choice out of the rng stream, so the downward bolts stay the same. */
	if (sideways && (hash_uint(seed ^ 0x5bd1e995u) & 1u)) {
		float end[3];
		const float span = rng_range(&rng, 45.0f, 90.0f) * k;
		const float dir = (rng_float(&rng) < 0.5f) ? -1.0f : 1.0f;
		top[2] -= rng_range(&rng, 5.0f, 20.0f) * k;
		copy_v3_v3(end, top);
		madd_v3_v3fl(end, side, dir * span);
		madd_v3_v3fl(end, fwd, rng_range(&rng, -0.25f, 0.25f) * span);
		end[2] += rng_range(&rng, -12.0f, 6.0f) * k;
		build_bolt(&rng, top, end, k, width, r_bolt);
		return;
	}

	build_bolt(&rng, top, ground, k, width, r_bolt);
}

unsigned int BKE_rain_lightning_salt(const char *name)
{
	/* FNV-1a */
	unsigned int h = 2166136261u;
	for (; *name; name++) {
		h = (h ^ (unsigned char)*name) * 16777619u;
	}
	return h;
}

void BKE_rain_lightning_strike_point(
        unsigned int seed, const float obmat[4][4], float size, bool box, float r_point[3])
{
	Rng rng = rng_seed(seed ^ 0x6c8e9cf5u);
	float local[3] = {0.0f, 0.0f, 0.0f};
	if (box) {
		local[0] = rng_range(&rng, -1.0f, 1.0f) * size;
		local[1] = rng_range(&rng, -1.0f, 1.0f) * size;
	}
	else {
		/* sqrt: uniform over the disk, not packed at the center. */
		const float r = sqrtf(rng_float(&rng)) * size;
		const float a = rng_float(&rng) * 2.0f * (float)M_PI;
		local[0] = cosf(a) * r;
		local[1] = sinf(a) * r;
	}
	mul_v3_m4v3(r_point, obmat, local);
}

void BKE_rain_lightning_bolt_at(
        unsigned int seed, const float ground[3], float cloud_z, float width, RainLightningBolt *r_bolt)
{
	Rng rng = rng_seed(seed);
	/* The camera bolt is 55-75 m tall at k = 1. */
	const float k = max_ff(cloud_z - ground[2], 1.0f) / 65.0f;
	float top[3];
	copy_v3_v3(top, ground);
	top[0] += rng_range(&rng, -15.0f, 15.0f) * k;
	top[1] += rng_range(&rng, -15.0f, 15.0f) * k;
	top[2] = max_ff(cloud_z, ground[2] + 1.0f);
	build_bolt(&rng, top, ground, k, width, r_bolt);
}

void BKE_rain_lightning_bolt_between(
        unsigned int seed, const float from[3], const float to[3], float width, RainLightningBolt *r_bolt)
{
	Rng rng = rng_seed(seed);
	const float k = max_ff(len_v3v3(from, to), 1.0f) / 65.0f;
	build_bolt(&rng, from, to, k, width, r_bolt);
}

float BKE_rain_lightning_distance_fade(float distance, float flash_distance)
{
	const float d2 = flash_distance * flash_distance;
	return d2 / (d2 + distance * distance);
}

void BKE_rain_lightning_side(const RainLightningBolt *bolt, int strip, int i, const float cam_pos[3], float r_side[3])
{
	const int start = bolt->strip_start[strip];
	const int n = bolt->strip_len[strip];
	const int i0 = max_ii(i - 1, 0), i1 = min_ii(i + 1, n - 1);
	const float *p = bolt->co[start + i];
	float tangent[3], view[3];
	/* Averaged tangent: the ribbon bends at the joints instead of overlapping. */
	sub_v3_v3v3(tangent, bolt->co[start + i1], bolt->co[start + i0]);
	sub_v3_v3v3(view, cam_pos, p);
	cross_v3_v3v3(r_side, tangent, view);
	if (normalize_v3(r_side) < 1e-8f) {
		zero_v3(r_side);
		return;
	}
	mul_v3_fl(r_side, bolt->half_width[start + i]);
}

bool BKE_rain_lightning_eval(
        float rate, float intensity, double time, float *r_flash, float *r_bolt_bright, unsigned int *r_seed)
{
	double start;
	bool big;
	*r_flash = *r_bolt_bright = 0.0f;
	if (!BKE_rain_lightning_schedule(rate, time, &start, r_seed, &big)) {
		return false;
	}
	/* Same curves as KX_RainLightning::Update(). */
	const float flash = BKE_rain_lightning_flash(*r_seed, big, (float)(time - start), NULL);
	*r_flash = flash * intensity;
	*r_bolt_bright = big ? min_ff(flash * 1.6f, 1.0f) * intensity : 0.0f;
	return *r_flash > 0.0f;
}

void BKE_rain_lightning_view_bolt(
        unsigned int seed, const float viewinv[4][4], float clip_end, float distance, float width,
        bool sideways, RainLightningBolt *r_bolt)
{
	const float fwd[3] = {-viewinv[2][0], -viewinv[2][1], -viewinv[2][2]};
	if (clip_end > 0.0f) {
		distance = min_ff(distance, clip_end * 0.6f);
	}
	BKE_rain_lightning_bolt(seed, viewinv[3], fwd, distance, width, sideways, r_bolt);
}
