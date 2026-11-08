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

#ifndef __BKE_MOTION_RECORD_H__
#define __BKE_MOTION_RECORD_H__

/** \file BKE_motion_record.h
 *  \ingroup bke
 *
 * Rec Play buffer, shared by the game engine (writes samples) and the editor (turns them into
 * Actions). It lives outside the game scenes because StopEngine destroys them before the editor
 * gets control back. See docs/gravacao-de-movimento-plan.md.
 */

#ifdef __cplusplus
extern "C" {
#endif

struct Object;

typedef struct MotionSample {
	float t;  /* Seconds of game time since the recording started. */
	float mat[4][4];  /* World matrix. */
	float parent_mat[4][4];  /* World matrix of the parent in the game, it moves with the actor. */
	bool has_parent;
} MotionSample;

/* A stretch of an Action seen playing on an armature: becomes an NLA strip. */
typedef struct MotionClip {
	char action[64];
	int layer;
	float t_start, t_end;
	float frame_start, frame_end;
} MotionClip;

/* fixed_rate: samples per second, 0 = every logic step. max_seconds: 0 = until stopped.
 * countdown: seconds the game waits frozen before recording.
 * walk_speed: quick control, meters per second along +Y of the actor, negative for -Y. */
void BKE_motion_record_begin(struct Object **actors, int actors_num, float fixed_rate, float max_seconds,
                             float countdown, float walk_speed);
/* After begin. layers: actors with a take repeat it. replaced_take: left out of that, -1 = none.
 * collide: repeating actors stay solid. watch: nothing is recorded, the takes only play. */
void BKE_motion_record_set_layers(bool layers, bool collide, int replaced_take, bool watch);
/* Record Voice: the game records the microphone along with the take. */
void BKE_motion_record_set_voice(bool voice);
bool BKE_motion_record_voice(void);
/* Where the game leaves the WAV until the take has a name. */
void BKE_motion_record_voice_temp_path(char *r_path, int maxlen);
/* The WAV of a take: //sounds/take_<name>.wav next to main_path. */
void BKE_motion_record_voice_file(const char *take_name, const char *main_path, char *r_path, int maxlen);
bool BKE_motion_record_layers(void);
bool BKE_motion_record_layers_collide(void);
int BKE_motion_record_replaced_take(void);
bool BKE_motion_record_is_watch(void);
/* Stops accepting samples and keeps them, until BKE_motion_record_free. */
void BKE_motion_record_stop(void);
void BKE_motion_record_free(void);

bool BKE_motion_record_is_active(void);
/* Seconds recorded so far and the limit (0 = none). */
double BKE_motion_record_time(void);
float BKE_motion_record_max_seconds(void);
bool BKE_motion_record_time_up(void);
/* Seconds left before recording starts, 0 once it started. */
double BKE_motion_record_countdown(void);
void BKE_motion_record_countdown_advance(double step);
float BKE_motion_record_walk_speed(void);
bool BKE_motion_record_is_actor(const struct Object *ob);
/* Whether the samples of the current step are to be kept (false between fixed rate samples). */
bool BKE_motion_record_sample_due(void);
/* parent_mat: NULL when the actor has no parent in the game. */
void BKE_motion_record_sample(const struct Object *ob, const float mat[4][4], const float parent_mat[4][4]);
/* Children of the marked actors join when the game starts. */
void BKE_motion_record_add_child(struct Object *ob);
void BKE_motion_record_clip(const struct Object *ob, int layer, const char *action, float frame);
/* The one clock of the recording: call once per step that was not suspended. */
void BKE_motion_record_advance(double step);

int BKE_motion_record_actors_num(void);
struct Object *BKE_motion_record_actor(int index, const MotionSample **r_samples, int *r_samples_num);
const MotionClip *BKE_motion_record_actor_clips(int index, int *r_clips_num);
bool BKE_motion_record_actor_is_child(int index);

#ifdef __cplusplus
}
#endif

#endif  /* __BKE_MOTION_RECORD_H__ */
