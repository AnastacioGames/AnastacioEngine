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

#include "BLI_fileops.h"
#include "BLI_listbase.h"
#include "BLI_math.h"
#include "BLI_string.h"
#include "BLI_utildefines.h"

#include "BKE_action.h"
#include "BKE_animsys.h"
#include "BKE_context.h"
#include "BKE_depsgraph.h"
#include "BKE_fcurve.h"
#include "BKE_global.h"
#include "BKE_scene.h"
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

static MotionTake *motion_take_active(Scene *scene, PointerRNA *scene_ptr)
{
	return BLI_findlink(&scene->motion_takes, RNA_int_get(scene_ptr, "ae_rec_take_index"));
}

/* Takes run from the first frame, so what was recorded on top of them has to start there too. */
static void motion_scene_rewind(Scene *scene)
{
	scene->r.cfra = scene->r.sfra;
	scene->r.subframe = 0.0f;
	BKE_scene_update_for_newframe(G.main->eval_ctx, G.main, scene, scene->lay);
}

static bool motion_watch_begin(Scene *scene, PointerRNA *scene_ptr, ReportList *reports)
{
	float seconds = 0.0f;
	for (MotionTake *take = scene->motion_takes.first; take; take = take->next) {
		seconds = max_ff(seconds, take->duration);
	}
	if (seconds <= 0.0f) {
		BKE_report(reports, RPT_ERROR, "Rec Play: record a take first");
		return false;
	}
	motion_scene_rewind(scene);
	BKE_motion_record_begin(NULL, 0, 0.0f, seconds, 0.0f, 0.0f);
	BKE_motion_record_set_layers(true, RNA_boolean_get(scene_ptr, "ae_rec_playback_collision"), -1, true);
	return true;
}

/* The actors of the take, without what they carry: children join by themselves. */
static int motion_take_actors(const MotionTake *take, Object **actors, int capacity)
{
	int num = 0;
	for (MotionTakeActor *actor = take->actors.first; actor; actor = actor->next) {
		if (actor->ob && num < capacity) {
			actors[num++] = actor->ob;
		}
	}
	int kept = 0;
	for (int i = 0; i < num; i++) {
		bool carried = false;
		for (Object *parent = actors[i]->parent; parent && !carried; parent = parent->parent) {
			for (int j = 0; j < num; j++) {
				carried |= (actors[j] == parent);
			}
		}
		if (!carried) {
			actors[kept++] = actors[i];
		}
	}
	return kept;
}

bool view3d_motion_record_begin(Scene *scene, ReportList *reports, bool watch, bool rerecord)
{
	PointerRNA scene_ptr;
	RNA_id_pointer_create(&scene->id, &scene_ptr);

	if (watch) {
		return motion_watch_begin(scene, &scene_ptr, reports);
	}

	const int capacity = BLI_listbase_count(&scene->base) + 2;
	Object **actors = MEM_mallocN(sizeof(*actors) * capacity, __func__);
	int num = 0;
	const MotionTake *active_take = motion_take_active(scene, &scene_ptr);

	if (rerecord) {
		if (active_take) {
			num = motion_take_actors(active_take, actors, capacity - 1);
		}
	}
	else {
		for (Base *base = scene->base.first; base; base = base->next) {
			PointerRNA ob_ptr;
			RNA_id_pointer_create(&base->object->id, &ob_ptr);
			if (RNA_boolean_get(&ob_ptr, "ae_rec_actor")) {
				actors[num++] = base->object;
			}
		}
	}
	/* None marked: the active object, as the panel says. */
	if (num == 0 && !rerecord && scene->basact) {
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

	if (scene->motion_takes.first) {
		motion_scene_rewind(scene);
	}

	const bool fixed = RNA_enum_get(&scene_ptr, "ae_rec_sample_rate") == 1;
	BKE_motion_record_begin(
	        actors, num, fixed ? (float)RNA_int_get(&scene_ptr, "ae_rec_fixed_rate") : 0.0f,
	        RNA_float_get(&scene_ptr, "ae_rec_max_duration"), (float)RNA_int_get(&scene_ptr, "ae_rec_countdown"),
	        RNA_float_get(&scene_ptr, "ae_rec_walk_speed") * (RNA_boolean_get(&scene_ptr, "ae_rec_walk_negative_y") ? -1.0f : 1.0f));
	MEM_freeN(actors);
	const bool replace = active_take && (rerecord || RNA_boolean_get(&scene_ptr, "ae_rec_replace_take"));
	BKE_motion_record_set_layers(
	        RNA_boolean_get(&scene_ptr, "ae_rec_playback_layers"), RNA_boolean_get(&scene_ptr, "ae_rec_playback_collision"),
	        replace ? RNA_int_get(&scene_ptr, "ae_rec_take_index") : -1, false);
	BKE_motion_record_set_voice(RNA_boolean_get(&scene_ptr, "ae_rec_voice"));
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

/* A take is the one name that groups what a recording made. */
static MotionTake *motion_take_add(Scene *scene, PointerRNA *scene_ptr, int replaced)
{
	MotionTake *take = MEM_callocN(sizeof(*take), __func__);
	const MotionTake *old = (replaced >= 0) ? BLI_findlink(&scene->motion_takes, replaced) : NULL;
	take->version = MOTION_TAKE_VERSION;
	if (old) {
		BLI_strncpy(take->name, old->name, sizeof(take->name));
	}
	else {
		const int counter = RNA_int_get(scene_ptr, "ae_rec_take_counter") + 1;
		RNA_int_set(scene_ptr, "ae_rec_take_counter", counter);
		BLI_snprintf(take->name, sizeof(take->name), "Take %d", counter);
	}
	BLI_addtail(&scene->motion_takes, take);
	RNA_int_set(scene_ptr, "ae_rec_take_index", BLI_listbase_count(&scene->motion_takes) - 1);
	return take;
}

/* The poses of the take as local transforms of the game: the converter puts a node with the parent
 * inverse between an object and its parent, so that is the space they are relative to. */
static void motion_take_store(MotionTakeActor *actor, const Object *ob, const MotionSample *samples, int num)
{
	/* The take replays under the parent of the editor, whatever the game did to the hierarchy. */
	float parentinv_inverse[4][4], parent[4][4];
	if (ob->parent) {
		invert_m4_m4(parentinv_inverse, (float (*)[4])ob->parentinv);
		copy_m4_m4(parent, ob->parent->obmat);
	}
	actor->samples = MEM_mallocN(sizeof(float) * MOTION_TAKE_SAMPLE_FLOATS * num, __func__);
	actor->samples_num = num;
	for (int i = 0; i < num; i++) {
		float *out = &actor->samples[i * MOTION_TAKE_SAMPLE_FLOATS];
		float mat[4][4], inverse[4][4], local[4][4];
		memcpy(mat, samples[i].mat, sizeof(mat));
		if (ob->parent) {
			/* After removeParent the last place the parent was seen stands in for it. */
			if (samples[i].has_parent) {
				memcpy(parent, samples[i].parent_mat, sizeof(parent));
			}
			invert_m4_m4(inverse, parent);
			mul_m4_m4m4(local, inverse, mat);
			mul_m4_m4m4(inverse, parentinv_inverse, local);
			copy_m4_m4(local, inverse);
		}
		else {
			copy_m4_m4(local, mat);
		}
		out[0] = samples[i].t;
		mat4_decompose(out + 1, out + 4, out + 8, local);
		/* The short way between two samples. */
		if (i > 0 && dot_qtqt(out + 4, out + 4 - MOTION_TAKE_SAMPLE_FLOATS) < 0.0f) {
			mul_qt_fl(out + 4, -1.0f);
		}
	}
}

static void motion_take_store_clips(MotionTakeActor *actor, const MotionClip *clips, int num)
{
	actor->clips = MEM_callocN(sizeof(MotionTakeClip) * num, __func__);
	actor->clips_num = num;
	for (int i = 0; i < num; i++) {
		BLI_strncpy(actor->clips[i].action, clips[i].action, sizeof(actor->clips[i].action));
		actor->clips[i].layer = clips[i].layer;
		actor->clips[i].t_start = clips[i].t_start;
		actor->clips[i].t_end = clips[i].t_end;
		actor->clips[i].frame_start = clips[i].frame_start;
		actor->clips[i].frame_end = clips[i].frame_end;
	}
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

	if (BKE_motion_record_is_watch()) {
		BKE_motion_record_free();
		return false;
	}

	/* Left before the countdown ended: nothing was recorded. */
	if (BKE_motion_record_countdown() > 0.0) {
		BKE_motion_record_free();
		BKE_report(reports, RPT_INFO, "Rec Play: cancelled");
		return false;
	}

	BKE_motion_record_stop();

	const bool keyframes = RNA_boolean_get(&scene_ptr, "ae_rec_make_keyframes");
	const float tolerance = RNA_float_get(&scene_ptr, "ae_rec_keyframe_tolerance");
	const int replaced = BKE_motion_record_replaced_take();
	MotionTake *take = NULL;
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
			const bool moves = !BKE_motion_record_actor_is_child(i) || motion_child_moves(samples, num, tolerance);
			if (!moves && clips_num == 0) {
				continue;
			}
			if (created++ == 0) {
				take = motion_take_add(scene, &scene_ptr, replaced);
			}
			MotionTakeActor *actor = MEM_callocN(sizeof(*actor), __func__);
			actor->ob = ob;
			BLI_addtail(&take->actors, actor);
			/* The space of a bone is not the one of the parent object: that child rides along. */
			const bool own_space = !ob->parent || ob->partype == PAROBJECT;
			/* Clips start from the replay, so a child that only animates needs samples too. */
			if ((moves || clips_num) && own_space) {
				motion_take_store(actor, ob, samples, num);
			}
			if (clips_num) {
				motion_take_store_clips(actor, clips, clips_num);
			}
			if (keyframes) {
				if (moves && own_space) {
					bAction *act = motion_action_create(bmain, scene, ob, samples, num, tolerance);
					BLI_strncpy(actor->action_name, act->id.name + 2, sizeof(actor->action_name));
				}
				if (clips_num) {
					motion_nla_create(bmain, scene, ob, clips, clips_num, track_prefix);
					BLI_strncpy(actor->track_prefix, track_prefix, sizeof(actor->track_prefix));
				}
			}
			take->duration = max_ff(take->duration, samples[num - 1].t);
		}
	}
	if (created && replaced >= 0) {
		motion_take_remove(C, replaced);
	}
	{
		/* Voz gravada junto: o jogo deixou no temporario, aqui o Take ja tem nome. */
		char temp[FILE_MAX];
		BKE_motion_record_voice_temp_path(temp, sizeof(temp));
		if (BLI_exists(temp)) {
			if (created && bmain->name[0]) {
				char dest[FILE_MAX];
				BKE_motion_record_voice_file(take->name, bmain->name, dest, sizeof(dest));
				BLI_make_existing_file(dest);
				if (BLI_exists(dest)) {
					BLI_delete(dest, false, false);
				}
				if (BLI_copy(temp, dest) != 0) {
					BKE_report(reports, RPT_WARNING, "Rec Play: could not save the voice file");
				}
			}
			else if (created) {
				BKE_report(reports, RPT_WARNING, "Rec Play: save the file first to keep the voice");
			}
			BLI_delete(temp, false, false);
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
