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

/** \file blender/editors/space_view3d/view3d_motion_record.c
 *  \ingroup spview3d
 *
 * Rec Play in the editor: picks the actors before the game starts and turns the recording into
 * one Action per actor after it ends. Plan: docs/gravacao-de-movimento-plan.md.
 */

#include <math.h>
#include <string.h>

#include "DNA_action_types.h"
#include "DNA_anim_types.h"
#include "DNA_object_types.h"
#include "DNA_scene_types.h"
#include "DNA_screen_types.h"
#include "DNA_view3d_types.h"
#include "DNA_windowmanager_types.h"

#include "MEM_guardedalloc.h"

#include "BLI_listbase.h"
#include "BLI_math.h"
#include "BLI_string.h"
#include "BLI_utildefines.h"

#include "BKE_action.h"
#include "BKE_animsys.h"
#include "BKE_context.h"
#include "BKE_depsgraph.h"
#include "BKE_fcurve.h"
#include "BKE_library.h"
#include "BKE_main.h"
#include "BKE_motion_record.h"
#include "BKE_nla.h"
#include "BKE_object.h"
#include "BKE_report.h"

#include "ED_keyframing.h"

#include "RNA_access.h"

#include "WM_api.h"
#include "WM_types.h"

#include "view3d_intern.h"  /* own include */

#define MOTION_CHANNELS 9

bool view3d_motion_record_begin(Scene *scene, ReportList *reports)
{
	PointerRNA scene_ptr;
	RNA_id_pointer_create(&scene->id, &scene_ptr);

	const int capacity = BLI_listbase_count(&scene->base) + 2;
	Object **actors = MEM_mallocN(sizeof(*actors) * capacity, __func__);
	int num = 0;

	for (Base *base = scene->base.first; base; base = base->next) {
		PointerRNA ob_ptr;
		RNA_id_pointer_create(&base->object->id, &ob_ptr);
		if (RNA_boolean_get(&ob_ptr, "ae_rec_actor")) {
			actors[num++] = base->object;
		}
	}
	/* None marked: the active object, as the panel says. */
	if (num == 0 && scene->basact) {
		actors[num++] = scene->basact->object;
	}
	if (RNA_boolean_get(&scene_ptr, "ae_rec_record_camera") && scene->camera) {
		bool found = false;
		for (int i = 0; i < num; i++) {
			found |= (actors[i] == scene->camera);
		}
		if (!found) {
			actors[num++] = scene->camera;
		}
	}

	if (num == 0) {
		MEM_freeN(actors);
		BKE_report(reports, RPT_ERROR, "Rec Play: mark a Record Actor or select an object first");
		return false;
	}

	const bool fixed = RNA_enum_get(&scene_ptr, "ae_rec_sample_rate") == 1;
	BKE_motion_record_begin(
	        actors, num, fixed ? (float)RNA_int_get(&scene_ptr, "ae_rec_fixed_rate") : 0.0f,
	        RNA_float_get(&scene_ptr, "ae_rec_max_duration"), (float)RNA_int_get(&scene_ptr, "ae_rec_countdown"),
	        RNA_float_get(&scene_ptr, "ae_rec_walk_speed") * (RNA_boolean_get(&scene_ptr, "ae_rec_walk_negative_y") ? -1.0f : 1.0f));
	MEM_freeN(actors);
	return true;
}

/* Marks in keep[] the samples needed so the straight lines between them stay within the tolerance. */
static void motion_simplify(const float *values, const float *times, int num, float tolerance, bool *keep, int *stack)
{
	int top = 0;
	memset(keep, 0, sizeof(*keep) * num);
	keep[0] = keep[num - 1] = true;
	stack[top++] = 0;
	stack[top++] = num - 1;

	while (top > 0) {
		const int last = stack[--top];
		const int first = stack[--top];
		const float span = times[last] - times[first];
		float worst = tolerance;
		int worst_index = -1;

		for (int i = first + 1; i < last; i++) {
			const float factor = (span > 0.0f) ? (times[i] - times[first]) / span : 0.0f;
			const float error = fabsf(values[i] - (values[first] + (values[last] - values[first]) * factor));
			if (error > worst) {
				worst = error;
				worst_index = i;
			}
		}
		if (worst_index != -1) {
			keep[worst_index] = true;
			stack[top++] = first;
			stack[top++] = worst_index;
			stack[top++] = worst_index;
			stack[top++] = last;
		}
	}
}

static void motion_fcurve_add(
        bAction *act, PointerRNA *ob_ptr, const char *path, int index, const float *values, const float *times,
        int num, float tolerance, bool *keep, int *stack)
{
	FCurve *fcu = verify_fcurve(act, "Object Transforms", ob_ptr, path, index, 1);

	if (tolerance > 0.0f) {
		motion_simplify(values, times, num, tolerance, keep, stack);
	}
	for (int i = 0; i < num; i++) {
		if (tolerance <= 0.0f || keep[i]) {
			insert_vert_fcurve(fcu, times[i], values[i], BEZT_KEYTYPE_KEYFRAME, INSERTKEY_FAST | INSERTKEY_NO_USERPREF);
		}
	}
	for (unsigned int i = 0; i < fcu->totvert; i++) {
		fcu->bezt[i].ipo = BEZT_IPO_LIN;
	}
	calchandles_fcurve(fcu);
}

static bAction *motion_action_create(
        Main *bmain, Scene *scene, Object *ob, const MotionSample *samples, int num, float tolerance)
{
	static const struct { const char *path; int index; } channels[MOTION_CHANNELS] = {
		{"location", 0}, {"location", 1}, {"location", 2},
		{"rotation_euler", 0}, {"rotation_euler", 1}, {"rotation_euler", 2},
		{"scale", 0}, {"scale", 1}, {"scale", 2},
	};
	/* The game reads object rotation curves as XYZ Euler, whatever the mode of the object. */
	ob->rotmode = ROT_MODE_EUL;

	float *times = MEM_mallocN(sizeof(float) * num, __func__);
	float *values = MEM_mallocN(sizeof(float) * num * MOTION_CHANNELS, __func__);
	bool *keep = MEM_mallocN(sizeof(bool) * num, __func__);
	int *stack = MEM_mallocN(sizeof(int) * (num + 2) * 2, __func__);
	const float fps = (float)FPS;

	/* A copy, so the object keeps its pose; rot carries over and keeps the Euler angles continuous. */
	Object pose = *ob;
	for (int i = 0; i < num; i++) {
		float mat[4][4];
		memcpy(mat, samples[i].mat, sizeof(mat));
		if (samples[i].has_parent && ob->parent && ob->partype == PAROBJECT) {
			/* ob->parent is still where the editor left it, the sample has where it was in the game. */
			float parent_mat[4][4], diff[4][4], inverse[4][4], local[4][4];
			memcpy(parent_mat, samples[i].parent_mat, sizeof(parent_mat));
			mul_m4_m4m4(diff, parent_mat, ob->parentinv);
			invert_m4_m4(inverse, diff);
			mul_m4_m4m4(local, inverse, mat);
			BKE_object_apply_mat4(&pose, local, true, false);
		}
		else {
			BKE_object_apply_mat4(&pose, mat, true, true);
		}
		times[i] = (float)scene->r.sfra + samples[i].t * fps;
		for (int axis = 0; axis < 3; axis++) {
			values[(0 + axis) * num + i] = pose.loc[axis];
			values[(3 + axis) * num + i] = pose.rot[axis];
			values[(6 + axis) * num + i] = pose.size[axis];
		}
	}

	char name[MAX_ID_NAME - 2];
	BLI_snprintf(name, sizeof(name), "Rec_%s", ob->id.name + 2);
	bAction *act = BKE_action_add(bmain, name);
	act->idroot = ID_OB;
	/* Earlier recordings stay in the file. */
	id_fake_user_set(&act->id);

	PointerRNA ob_ptr;
	RNA_id_pointer_create(&ob->id, &ob_ptr);
	for (int c = 0; c < MOTION_CHANNELS; c++) {
		motion_fcurve_add(
		        act, &ob_ptr, channels[c].path, channels[c].index, &values[c * num], times, num, tolerance, keep, stack);
	}

	AnimData *adt = BKE_animdata_add_id(&ob->id);
	if (adt->action) {
		id_fake_user_set(&adt->action->id);
		id_us_min(&adt->action->id);
	}
	adt->action = act;  /* Takes the user the new Action was born with. */
	DAG_id_tag_update(&ob->id, OB_RECALC_OB | OB_RECALC_TIME);

	MEM_freeN(times);
	MEM_freeN(values);
	MEM_freeN(keep);
	MEM_freeN(stack);
	return act;
}

/* Whether a child that joined by itself moves apart from its parent, and so needs an Action. */
static bool motion_child_moves(const MotionSample *samples, int num, float tolerance)
{
	const float limit = max_ff(tolerance, 1e-4f);
	float first[4][4];
	for (int i = 0; i < num; i++) {
		float parent[4][4], mat[4][4], inverse[4][4], local[4][4];
		memcpy(mat, samples[i].mat, sizeof(mat));
		if (samples[i].has_parent) {
			memcpy(parent, samples[i].parent_mat, sizeof(parent));
			invert_m4_m4(inverse, parent);
			mul_m4_m4m4(local, inverse, mat);
		}
		else {
			copy_m4_m4(local, mat);
		}
		if (i == 0) {
			copy_m4_m4(first, local);
		}
		else if (!compare_m4m4(first, local, limit)) {
			return true;
		}
	}
	return false;
}

/* One NLA track per action layer, named after the take so a take can be chosen by muting the others. */
static void motion_nla_create(
        Main *bmain, Scene *scene, Object *ob, const MotionClip *clips, int num, const char *prefix)
{
	AnimData *adt = BKE_animdata_add_id(&ob->id);
	const float fps = (float)FPS;

	for (NlaTrack *nlt = adt->nla_tracks.first; nlt; nlt = nlt->next) {
		if (STRPREFIX(nlt->name, "Rec_")) {
			nlt->flag |= NLATRACK_MUTED;
		}
	}
	for (int i = 0; i < num; i++) {
		bool seen = false;
		for (int j = 0; j < i; j++) {
			seen |= (clips[j].layer == clips[i].layer);
		}
		if (seen) {
			continue;
		}
		NlaTrack *nlt = BKE_nlatrack_add(adt, NULL);
		BLI_snprintf(nlt->name, sizeof(nlt->name), "%s%d", prefix, clips[i].layer);
		for (int j = i; j < num; j++) {
			const MotionClip *clip = &clips[j];
			bAction *act = BLI_findstring(&bmain->action, clip->action, offsetof(ID, name) + 2);
			if (clip->layer != clips[i].layer || !act) {
				continue;
			}
			NlaStrip *strip = BKE_nlastrip_new(act);
			if (!strip) {
				continue;
			}
			strip->start = (float)scene->r.sfra + clip->t_start * fps;
			strip->end = max_ff((float)scene->r.sfra + clip->t_end * fps, strip->start + 1.0f);
			strip->actstart = min_ff(clip->frame_start, clip->frame_end);
			strip->actend = max_ff(max_ff(clip->frame_start, clip->frame_end), strip->actstart + 0.01f);
			strip->scale = (strip->end - strip->start) / (strip->actend - strip->actstart);
			strip->repeat = 1.0f;
			strip->extendmode = NLASTRIP_EXTEND_HOLD_FORWARD;
			if (clip->frame_end < clip->frame_start) {
				strip->flag |= NLASTRIP_FLAG_REVERSE;
			}
			if (BKE_nlatrack_add_strip(nlt, strip)) {
				BKE_nlastrip_validate_name(adt, strip);
			}
			else {
				BKE_nlastrip_free(NULL, strip);
			}
		}
	}
	DAG_id_tag_update(&ob->id, OB_RECALC_OB | OB_RECALC_DATA | OB_RECALC_TIME);
}

/* A take is the one name that groups the Actions of a recording. */
static void motion_take_add(PointerRNA *scene_ptr, PointerRNA *r_take, int replaced)
{
	const int takes_num = RNA_collection_length(scene_ptr, "ae_rec_takes");
	char name[64];
	if (replaced >= 0) {
		PointerRNA old;
		RNA_property_collection_lookup_int(
		        scene_ptr, RNA_struct_find_property(scene_ptr, "ae_rec_takes"), replaced, &old);
		RNA_string_get(&old, "name", name);
	}
	else {
		const int counter = RNA_int_get(scene_ptr, "ae_rec_take_counter") + 1;
		RNA_int_set(scene_ptr, "ae_rec_take_counter", counter);
		BLI_snprintf(name, sizeof(name), "Take %d", counter);
	}
	RNA_collection_add(scene_ptr, "ae_rec_takes", r_take);
	RNA_string_set(r_take, "name", name);
	RNA_int_set(scene_ptr, "ae_rec_take_index", takes_num);
}

/* The old take goes only after the new one exists, so a failed recording loses nothing. */
static void motion_take_remove(bContext *C, int index)
{
	wmOperatorType *ot = WM_operatortype_find("SCENE_OT_rec_take_remove", false);
	if (ot) {
		PointerRNA props;
		WM_operator_properties_create_ptr(&props, ot);
		RNA_int_set(&props, "index", index);
		WM_operator_name_call_ptr(C, ot, WM_OP_EXEC_DEFAULT, &props);
		WM_operator_properties_free(&props);
	}
}

bool view3d_motion_record_finish(bContext *C, Scene *scene, ReportList *reports)
{
	Main *bmain = CTX_data_main(C);
	PointerRNA scene_ptr;
	RNA_id_pointer_create(&scene->id, &scene_ptr);
	int created = 0;

	/* Left before the countdown ended: nothing was recorded. */
	if (BKE_motion_record_countdown() > 0.0) {
		BKE_motion_record_free();
		BKE_report(reports, RPT_INFO, "Rec Play: cancelled");
		return false;
	}

	BKE_motion_record_stop();

	if (RNA_boolean_get(&scene_ptr, "ae_rec_make_keyframes")) {
		const float tolerance = RNA_float_get(&scene_ptr, "ae_rec_keyframe_tolerance");
		const int active_take = RNA_int_get(&scene_ptr, "ae_rec_take_index");
		const int replaced = (RNA_boolean_get(&scene_ptr, "ae_rec_replace_take") &&
		                      active_take < RNA_collection_length(&scene_ptr, "ae_rec_takes")) ? active_take : -1;
		float duration = 0.0f;
		PointerRNA take;
		/* Never reused, not even by a take that replaces another: old tracks are found by this name. */
		const int track_counter = RNA_int_get(&scene_ptr, "ae_rec_track_counter") + 1;
		char track_prefix[32];
		BLI_snprintf(track_prefix, sizeof(track_prefix), "Rec_%d_", track_counter);
		RNA_int_set(&scene_ptr, "ae_rec_track_counter", track_counter);
		for (int i = 0; i < BKE_motion_record_actors_num(); i++) {
			const MotionSample *samples;
			int num;
			Object *ob = BKE_motion_record_actor(i, &samples, &num);
			/* A single sample is an actor that never ran (e.g. removed on the first frame). */
			if (num >= 2 && !ID_IS_LINKED(ob)) {
				int clips_num;
				const MotionClip *clips = BKE_motion_record_actor_clips(i, &clips_num);
				const bool make_action = !BKE_motion_record_actor_is_child(i) ||
				                         motion_child_moves(samples, num, tolerance);
				if (!make_action && clips_num == 0) {
					continue;
				}
				if (created++ == 0) {
					motion_take_add(&scene_ptr, &take, replaced);
				}
				PointerRNA actor;
				RNA_collection_add(&take, "actors", &actor);
				RNA_string_set(&actor, "object_name", ob->id.name + 2);
				if (make_action) {
					bAction *act = motion_action_create(bmain, scene, ob, samples, num, tolerance);
					RNA_string_set(&actor, "action_name", act->id.name + 2);
				}
				if (clips_num) {
					motion_nla_create(bmain, scene, ob, clips, clips_num, track_prefix);
					RNA_string_set(&actor, "track_prefix", track_prefix);
				}
				duration = max_ff(duration, samples[num - 1].t);
				RNA_float_set(&take, "duration", duration);
			}
		}
		if (created && replaced >= 0) {
			motion_take_remove(C, replaced);
		}
	}
	BKE_motion_record_free();

	if (created) {
		BKE_reportf(reports, RPT_INFO, "Rec Play: take saved with %d actor(s)", created);
		WM_event_add_notifier(C, NC_ANIMATION | ND_KEYFRAME | NA_ADDED, NULL);
	}
	else {
		BKE_report(reports, RPT_WARNING, "Rec Play: nothing was recorded");
	}
	return created != 0;
}
