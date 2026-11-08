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
#include "BLI_path_util.h"
#include "BLI_string.h"
#include "BLI_utildefines.h"

#include "BKE_appdir.h"
#include "BKE_motion_record.h"

typedef struct MotionTrack {
	struct Object *ob;
	MotionSample *samples;
	int num, capacity;
	MotionClip *clips;
	int clips_num, clips_capacity;
	bool is_child;
} MotionTrack;

/* Longer than this, or two sample intervals, without seeing an Action means it stopped and started again. */
#define MOTION_CLIP_MAX_GAP 0.5f

static struct {
	MotionTrack *tracks;
	int tracks_num;
	bool active;
	double time, next_sample, interval;
	float max_seconds;
	double countdown;
	float walk_speed;
	bool layers, layers_collide, watch;
	int replaced_take;
	bool voice;
} rec = {NULL};

void BKE_motion_record_free(void)
{
	for (int i = 0; i < rec.tracks_num; i++) {
		MEM_SAFE_FREE(rec.tracks[i].samples);
		MEM_SAFE_FREE(rec.tracks[i].clips);
	}
	MEM_SAFE_FREE(rec.tracks);
	memset(&rec, 0, sizeof(rec));
}

void BKE_motion_record_begin(struct Object **actors, int actors_num, float fixed_rate, float max_seconds,
                             float countdown, float walk_speed)
{
	BKE_motion_record_free();
	/* Watching has no actors. */
	rec.tracks = MEM_callocN(sizeof(MotionTrack) * max_ii(actors_num, 1), __func__);
	rec.tracks_num = actors_num;
	for (int i = 0; i < actors_num; i++) {
		rec.tracks[i].ob = actors[i];
	}
	rec.interval = (fixed_rate > 0.0f) ? 1.0 / fixed_rate : 0.0;
	rec.max_seconds = max_seconds;
	rec.countdown = countdown;
	rec.walk_speed = walk_speed;
	rec.replaced_take = -1;
	rec.active = true;
	rec.voice = false;
}

void BKE_motion_record_set_layers(bool layers, bool collide, int replaced_take, bool watch)
{
	rec.layers = layers;
	rec.layers_collide = collide;
	rec.replaced_take = replaced_take;
	rec.watch = watch;
}

void BKE_motion_record_set_voice(bool voice)
{
	rec.voice = voice;
}

bool BKE_motion_record_voice(void)
{
	return rec.voice;
}

void BKE_motion_record_voice_temp_path(char *r_path, int maxlen)
{
	BLI_join_dirfile(r_path, maxlen, BKE_tempdir_session(), "recplay_voice.wav");
}

void BKE_motion_record_voice_file(const char *take_name, const char *main_path, char *r_path, int maxlen)
{
	char safe[128];
	BLI_strncpy(safe, take_name, sizeof(safe));
	BLI_filename_make_safe(safe);
	BLI_snprintf(r_path, maxlen, "//sounds/take_%s.wav", safe);
	BLI_path_abs(r_path, main_path);
}

bool BKE_motion_record_layers(void)
{
	return rec.layers;
}

bool BKE_motion_record_layers_collide(void)
{
	return rec.layers_collide;
}

int BKE_motion_record_replaced_take(void)
{
	return rec.replaced_take;
}

bool BKE_motion_record_is_watch(void)
{
	return rec.watch;
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

double BKE_motion_record_countdown(void)
{
	return rec.countdown;
}

void BKE_motion_record_countdown_advance(double step)
{
	rec.countdown = (rec.countdown > step) ? rec.countdown - step : 0.0;
}

float BKE_motion_record_walk_speed(void)
{
	return rec.walk_speed;
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

void BKE_motion_record_add_child(struct Object *ob)
{
	if (!rec.active || motion_track_find(ob)) {
		return;
	}
	rec.tracks = MEM_reallocN(rec.tracks, sizeof(MotionTrack) * (rec.tracks_num + 1));
	MotionTrack *track = &rec.tracks[rec.tracks_num++];
	memset(track, 0, sizeof(*track));
	track->ob = ob;
	track->is_child = true;
}

void BKE_motion_record_clip(const struct Object *ob, int layer, const char *action, float frame)
{
	MotionTrack *track = motion_track_find(ob);
	if (!rec.active || !track) {
		return;
	}
	const float t = (float)rec.time;
	MotionClip *last = NULL;
	for (int i = track->clips_num - 1; i >= 0 && !last; i--) {
		if (track->clips[i].layer == layer) {
			last = &track->clips[i];
		}
	}
	if (last && STREQ(last->action, action) && t - last->t_end < max_ff(MOTION_CLIP_MAX_GAP, 2.0f * (float)rec.interval)) {
		/* Same direction: a loop that jumps back to the start is a new clip. */
		if ((frame - last->frame_end) * (last->frame_end - last->frame_start) >= 0.0f) {
			last->t_end = t;
			last->frame_end = frame;
			return;
		}
	}
	if (track->clips_num == track->clips_capacity) {
		track->clips_capacity = max_ii(16, track->clips_capacity * 2);
		track->clips = track->clips ?
		        MEM_reallocN(track->clips, sizeof(MotionClip) * track->clips_capacity) :
		        MEM_mallocN(sizeof(MotionClip) * track->clips_capacity, __func__);
	}
	MotionClip *clip = &track->clips[track->clips_num++];
	BLI_strncpy(clip->action, action, sizeof(clip->action));
	clip->layer = layer;
	clip->t_start = clip->t_end = t;
	clip->frame_start = clip->frame_end = frame;
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

const MotionClip *BKE_motion_record_actor_clips(int index, int *r_clips_num)
{
	*r_clips_num = rec.tracks[index].clips_num;
	return rec.tracks[index].clips;
}

bool BKE_motion_record_actor_is_child(int index)
{
	return rec.tracks[index].is_child;
}

struct Object *BKE_motion_record_actor(int index, const MotionSample **r_samples, int *r_samples_num)
{
	*r_samples = rec.tracks[index].samples;
	*r_samples_num = rec.tracks[index].num;
	return rec.tracks[index].ob;
}
