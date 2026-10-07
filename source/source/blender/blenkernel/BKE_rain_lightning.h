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

#ifndef __BKE_RAIN_LIGHTNING_H__
#define __BKE_RAIN_LIGHTNING_H__

/** \file BKE_rain_lightning.h
 *  \ingroup bke
 *
 * World > Rain > Lightning, shared by the game engine and the 3D View so both show the
 * same thing: the automatic strike schedule, the flickering flash of a strike and the
 * branching bolt, all deterministic from a seed.
 */

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RAIN_LIGHTNING_MAX_POINTS 256
#define RAIN_LIGHTNING_MAX_STRIPS 8

typedef struct RainLightningBolt {
	/* Polylines: strip 0 is the main channel, the others are branches. */
	float co[RAIN_LIGHTNING_MAX_POINTS][3];
	/* Brightness along the strip (branches fade toward their tip). */
	float bright[RAIN_LIGHTNING_MAX_POINTS];
	/* Half width of the glow, in meters (the hot core is a fraction of it). */
	float half_width[RAIN_LIGHTNING_MAX_POINTS];
	int strip_start[RAIN_LIGHTNING_MAX_STRIPS];
	int strip_len[RAIN_LIGHTNING_MAX_STRIPS];
	int num_strips;
	float center[3];
} RainLightningBolt;

/* Glow half width divided by core half width: the shaders use it for the profile. */
#define RAIN_LIGHTNING_GLOW_RATIO 7.0f

/**
 * Automatic strikes, rate per minute. Finds the latest strike starting at or before
 * \a time. Returns false when there is none (rate 0). A strike is "big" when it has a
 * visible bolt, otherwise it is a far flash behind the clouds.
 */
bool BKE_rain_lightning_schedule(float rate, double time, double *r_start, unsigned int *r_seed, bool *r_big);
/**
 * Same as #BKE_rain_lightning_schedule for a lightning emitter: \a salt keeps two emitters out
 * of step, \a big_chance is the share of strikes with a visible bolt.
 */
bool BKE_rain_lightning_schedule_ex(
        float rate, unsigned int salt, float big_chance, double time,
        double *r_start, unsigned int *r_seed, bool *r_big);

/**
 * Flash of a strike \a t seconds after it started: 2-4 return strokes, each decaying
 * fast, the last one longer. Returns 0 when it is over (\a r_over set).
 */
float BKE_rain_lightning_flash(unsigned int seed, bool big, float t, bool *r_over);

/**
 * Builds the bolt of a strike in front of the camera (\a cam_fwd is the view direction),
 * about \a distance meters away. \a width scales the thickness. With \a sideways, half of
 * the strikes run across the clouds instead of down to the ground.
 */
void BKE_rain_lightning_bolt(
        unsigned int seed, const float cam_pos[3], const float cam_fwd[3], float distance, float width,
        bool sideways, RainLightningBolt *r_bolt);

/**
 * Camera facing side vector of point \a i of the bolt, already scaled to the glow half
 * width. The ribbon of a strip is co +- side, continuous at the joints.
 */
void BKE_rain_lightning_side(const RainLightningBolt *bolt, int strip, int i, const float cam_pos[3], float r_side[3]);
/* Lightning emitter: schedule salt from the object name, so editor and game agree. */
unsigned int BKE_rain_lightning_salt(const char *name);

/**
 * Lightning emitter: where strike \a seed falls inside the area of an Empty. The area lies in
 * the local XY plane of \a obmat, a circle of radius \a size or a square of half side \a size.
 */
void BKE_rain_lightning_strike_point(
        unsigned int seed, const float obmat[4][4], float size, bool box, float r_point[3]);

/**
 * Lightning emitter: the bolt of strike \a seed from the cloud at height \a cloud_z down to
 * \a ground. Its size follows the height, like the camera bolt follows its distance.
 */
void BKE_rain_lightning_bolt_at(
        unsigned int seed, const float ground[3], float cloud_z, float width, RainLightningBolt *r_bolt);

/* Lightning emitter with a Target: the bolt from  from to  to, any direction. */
void BKE_rain_lightning_bolt_between(
        unsigned int seed, const float from[3], const float to[3], float width, RainLightningBolt *r_bolt);

/* Lightning emitter: how much of the flash reaches a camera \a distance meters away. */
float BKE_rain_lightning_distance_fade(float distance, float flash_distance);

/* Automatic strike at `time` for the 3D View: flash and bolt brightness (0 when none),
 * scaled by the intensity, plus the seed to build the bolt with. False when dark. */
bool BKE_rain_lightning_eval(
        float rate, float intensity, double time, float *r_flash, float *r_bolt_bright, unsigned int *r_seed);
/* The bolt for a 3D View: camera from the inverse view matrix, kept within 60% of `clip_end`. */
void BKE_rain_lightning_view_bolt(
        unsigned int seed, const float viewinv[4][4], float clip_end, float distance, float width,
        bool sideways, RainLightningBolt *r_bolt);

#ifdef __cplusplus
}
#endif

#endif  /* __BKE_RAIN_LIGHTNING_H__ */
