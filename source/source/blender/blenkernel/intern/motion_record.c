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

/** \file blender/blenkernel/intern/motion_record.c
 *  \ingroup bke
 *
 * Rec Play buffer (see BKE_motion_record.h). Used from the game loop thread only.
 */

#include <string.h>

#include "MEM_guardedalloc.h"

#include "BLI_math.h"
#include "BLI_utildefines.h"

#include "BKE_motion_record.h"

typedef struct MotionTrack {
	struct Object *ob;
	MotionSample *samples;
	int num, capacity;
} MotionTrack;

static struct {
	MotionTrack *tracks;
	int tracks_num;
	bool active;
	double time, next_sample, interval;
	float max_seconds;
} rec = {NULL};

void BKE_motion_record_free(void)
{
	for (int i = 0; i < rec.tracks_num; i++) {
		MEM_SAFE_FREE(rec.tracks[i].samples);
	}
	MEM_SAFE_FREE(rec.tracks);
	memset(&rec, 0, sizeof(rec));
}

void BKE_motion_record_begin(struct Object **actors, int actors_num, float fixed_rate, float max_seconds)
{
	BKE_motion_record_free();
	rec.tracks = MEM_callocN(sizeof(MotionTrack) * actors_num, __func__);
	rec.tracks_num = actors_num;
	for (int i = 0; i < actors_num; i++) {
		rec.tracks[i].ob = actors[i];
	}
	rec.interval = (fixed_rate > 0.0f) ? 1.0 / fixed_rate : 0.0;
	rec.max_seconds = max_seconds;
	rec.active = true;
}

void BKE_motion_record_stop(void)
{
	rec.active = false;
}

bool BKE_motion_record_is_active(void)
{
	return rec.active;
}

double BKE_motion_record_time(void)
{
	return rec.time;
}

float BKE_motion_record_max_seconds(void)
{
	return rec.max_seconds;
}

bool BKE_motion_record_time_up(void)
{
	return rec.active && rec.max_seconds > 0.0f && rec.time >= rec.max_seconds;
}

static MotionTrack *motion_track_find(const struct Object *ob)
{
	for (int i = 0; i < rec.tracks_num; i++) {
		if (rec.tracks[i].ob == ob) {
			return &rec.tracks[i];
		}
	}
	return NULL;
}

bool BKE_motion_record_is_actor(const struct Object *ob)
{
	return motion_track_find(ob) != NULL;
}

bool BKE_motion_record_sample_due(void)
{
	return rec.active && rec.time >= rec.next_sample;
}

void BKE_motion_record_sample(const struct Object *ob, const float mat[4][4], const float parent_mat[4][4])
{
	MotionTrack *track = motion_track_find(ob);
	if (!rec.active || !track) {
		return;
	}
	const float t = (float)rec.time;
	/* An object shared by two running scenes is sampled once. */
	if (track->num > 0 && track->samples[track->num - 1].t == t) {
		return;
	}
	if (track->num == track->capacity) {
		track->capacity = max_ii(256, track->capacity * 2);
		track->samples = track->samples ?
		        MEM_reallocN(track->samples, sizeof(MotionSample) * track->capacity) :
		        MEM_mallocN(sizeof(MotionSample) * track->capacity, __func__);
	}
	MotionSample *sample = &track->samples[track->num++];
	sample->t = t;
	memcpy(sample->mat, mat, sizeof(sample->mat));
	sample->has_parent = parent_mat != NULL;
	if (parent_mat) {
		memcpy(sample->parent_mat, parent_mat, sizeof(sample->parent_mat));
	}
}

void BKE_motion_record_advance(double step)
{
	if (!rec.active) {
		return;
	}
	if (rec.time >= rec.next_sample) {
		rec.next_sample += rec.interval;
	}
	rec.time += step;
}

int BKE_motion_record_actors_num(void)
{
	return rec.tracks_num;
}

struct Object *BKE_motion_record_actor(int index, const MotionSample **r_samples, int *r_samples_num)
{
	*r_samples = rec.tracks[index].samples;
	*r_samples_num = rec.tracks[index].num;
	return rec.tracks[index].ob;
}
