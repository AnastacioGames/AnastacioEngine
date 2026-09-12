/*
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 */

/** \file blender/editors/object/object_cutscene.c
 *  \ingroup edobj
 */

#include "DNA_scene_types.h"

#include "BLI_listbase.h"
#include "BLI_string.h"

#include "BKE_context.h"
#include "BKE_library.h"

#include "MEM_guardedalloc.h"

#include "WM_api.h"
#include "WM_types.h"

#include "RNA_access.h"
#include "RNA_define.h"

#include "object_intern.h"

static bool cutscene_poll(bContext *C)
{
	Scene *scene = CTX_data_scene(C);

	return scene && !ID_IS_LINKED(scene) && scene->cutscene_settings;
}

static CutsceneSequence *cutscene_sequence_from_index(Scene *scene, int index)
{
	return BLI_findlink(&scene->cutscene_settings->sequences, index);
}

static void cutscene_event_id_users_incref(const CutsceneEvent *event)
{
	if (event->template_object) {
		id_us_plus((ID *)event->template_object);
	}
	if (event->spawn_point) {
		id_us_plus((ID *)event->spawn_point);
	}
	if (event->dependent_object) {
		id_us_plus((ID *)event->dependent_object);
	}
}

static void cutscene_event_id_users_decref(const CutsceneEvent *event)
{
	if (event->template_object) {
		id_us_min((ID *)event->template_object);
	}
	if (event->spawn_point) {
		id_us_min((ID *)event->spawn_point);
	}
	if (event->dependent_object) {
		id_us_min((ID *)event->dependent_object);
	}
}

static void cutscene_event_free(CutsceneEvent *event)
{
	cutscene_event_id_users_decref(event);
	MEM_freeN(event);
}

static void cutscene_sequence_free(CutsceneSequence *sequence)
{
	CutsceneEvent *event = sequence->events.first;

	while (event) {
		CutsceneEvent *event_next = event->next;
		cutscene_event_free(event);
		event = event_next;
	}
	MEM_freeN(sequence);
}

static CutsceneEvent *cutscene_event_duplicate(const CutsceneEvent *event)
{
	CutsceneEvent *event_copy = MEM_dupallocN(event);

	event_copy->next = NULL;
	event_copy->prev = NULL;
	cutscene_event_id_users_incref(event_copy);
	return event_copy;
}

static CutsceneSequence *cutscene_sequence_duplicate(const CutsceneSequence *sequence)
{
	CutsceneSequence *sequence_copy = MEM_dupallocN(sequence);

	sequence_copy->next = NULL;
	sequence_copy->prev = NULL;
	BLI_listbase_clear(&sequence_copy->events);
	for (const CutsceneEvent *event = sequence->events.first; event; event = event->next) {
		BLI_addtail(&sequence_copy->events, cutscene_event_duplicate(event));
	}
	return sequence_copy;
}

static const EnumPropertyItem cutscene_move_direction_items[] = {
	{-1, "UP", 0, "Up", "Move the item toward the start of the list"},
	{1, "DOWN", 0, "Down", "Move the item toward the end of the list"},
	{0, NULL, 0, NULL, NULL},
};

static int cutscene_sequence_add_exec(bContext *C, wmOperator *UNUSED(op))
{
	Scene *scene = CTX_data_scene(C);
	CutsceneSequence *sequence = MEM_callocN(sizeof(*sequence), "Cutscene Sequence");

	BLI_strncpy(sequence->name, "Sequence", sizeof(sequence->name));
	BLI_addtail(&scene->cutscene_settings->sequences, sequence);
	scene->cutscene_settings->active_sequence = BLI_listbase_count(&scene->cutscene_settings->sequences) - 1;
	scene->cutscene_settings->active_event = 0;

	WM_event_add_notifier(C, NC_SCENE | NA_EDITED, scene);
	return OPERATOR_FINISHED;
}

void CUTSCENE_OT_sequence_add(wmOperatorType *ot)
{
	ot->name = "Add Cutscene Sequence";
	ot->description = "Add a cutscene sequence to the scene";
	ot->idname = "CUTSCENE_OT_sequence_add";
	ot->exec = cutscene_sequence_add_exec;
	ot->poll = cutscene_poll;
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
}

static int cutscene_sequence_remove_exec(bContext *C, wmOperator *op)
{
	Scene *scene = CTX_data_scene(C);
	CutsceneSettings *settings = scene->cutscene_settings;
	const int index = RNA_int_get(op->ptr, "index");
	CutsceneSequence *sequence = cutscene_sequence_from_index(scene, index);

	if (sequence == NULL) {
		return OPERATOR_CANCELLED;
	}

	BLI_remlink(&settings->sequences, sequence);
	cutscene_sequence_free(sequence);

	settings->active_sequence = MIN2(index, BLI_listbase_count(&settings->sequences) - 1);
	settings->active_event = 0;

	WM_event_add_notifier(C, NC_SCENE | NA_EDITED, scene);
	return OPERATOR_FINISHED;
}

void CUTSCENE_OT_sequence_remove(wmOperatorType *ot)
{
	ot->name = "Remove Cutscene Sequence";
	ot->description = "Remove a cutscene sequence and its events";
	ot->idname = "CUTSCENE_OT_sequence_remove";
	ot->exec = cutscene_sequence_remove_exec;
	ot->poll = cutscene_poll;
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
	RNA_def_int(ot->srna, "index", 0, 0, INT_MAX, "Index", "Sequence index to remove", 0, INT_MAX);
}

static int cutscene_sequence_duplicate_exec(bContext *C, wmOperator *op)
{
	Scene *scene = CTX_data_scene(C);
	CutsceneSettings *settings = scene->cutscene_settings;
	const int index = RNA_int_get(op->ptr, "index");
	CutsceneSequence *sequence = cutscene_sequence_from_index(scene, index);
	CutsceneSequence *sequence_copy;

	if (sequence == NULL) {
		return OPERATOR_CANCELLED;
	}

	sequence_copy = cutscene_sequence_duplicate(sequence);
	BLI_insertlinkafter(&settings->sequences, sequence, sequence_copy);
	settings->active_sequence = index + 1;
	settings->active_event = MIN2(settings->active_event, BLI_listbase_count(&sequence_copy->events) - 1);

	WM_event_add_notifier(C, NC_SCENE | NA_EDITED, scene);
	return OPERATOR_FINISHED;
}

void CUTSCENE_OT_sequence_duplicate(wmOperatorType *ot)
{
	ot->name = "Duplicate Cutscene Sequence";
	ot->description = "Duplicate a cutscene sequence and its events";
	ot->idname = "CUTSCENE_OT_sequence_duplicate";
	ot->exec = cutscene_sequence_duplicate_exec;
	ot->poll = cutscene_poll;
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
	RNA_def_int(ot->srna, "index", 0, 0, INT_MAX, "Index", "Sequence index to duplicate", 0, INT_MAX);
}

static int cutscene_sequence_move_exec(bContext *C, wmOperator *op)
{
	Scene *scene = CTX_data_scene(C);
	CutsceneSettings *settings = scene->cutscene_settings;
	const int index = RNA_int_get(op->ptr, "index");
	const int direction = RNA_enum_get(op->ptr, "direction");
	CutsceneSequence *sequence = cutscene_sequence_from_index(scene, index);

	if (sequence == NULL || !BLI_listbase_link_move(&settings->sequences, sequence, direction)) {
		return OPERATOR_CANCELLED;
	}

	settings->active_sequence = index + direction;
	settings->active_event = 0;

	WM_event_add_notifier(C, NC_SCENE | NA_EDITED, scene);
	return OPERATOR_FINISHED;
}

void CUTSCENE_OT_sequence_move(wmOperatorType *ot)
{
	ot->name = "Move Cutscene Sequence";
	ot->description = "Move a cutscene sequence in the scene list";
	ot->idname = "CUTSCENE_OT_sequence_move";
	ot->exec = cutscene_sequence_move_exec;
	ot->poll = cutscene_poll;
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
	RNA_def_int(ot->srna, "index", 0, 0, INT_MAX, "Index", "Sequence index to move", 0, INT_MAX);
	RNA_def_enum(ot->srna, "direction", cutscene_move_direction_items, -1, "Direction", "Direction to move the sequence");
}

static int cutscene_event_add_exec(bContext *C, wmOperator *op)
{
	Scene *scene = CTX_data_scene(C);
	CutsceneSettings *settings = scene->cutscene_settings;
	const int sequence_index = RNA_int_get(op->ptr, "sequence_index");
	CutsceneSequence *sequence = cutscene_sequence_from_index(scene, sequence_index);
	CutsceneEvent *event;

	if (sequence == NULL) {
		return OPERATOR_CANCELLED;
	}

	event = MEM_callocN(sizeof(*event), "Cutscene Event");
	BLI_strncpy(event->name, "New Event", sizeof(event->name));
	event->type = CUTSCENE_EVENT_SPAWN_OBJECT;
	BLI_addtail(&sequence->events, event);

	settings->active_sequence = sequence_index;
	settings->active_event = BLI_listbase_count(&sequence->events) - 1;

	WM_event_add_notifier(C, NC_SCENE | NA_EDITED, scene);
	return OPERATOR_FINISHED;
}

void CUTSCENE_OT_event_add(wmOperatorType *ot)
{
	ot->name = "Add Cutscene Event";
	ot->description = "Add an event to a cutscene sequence";
	ot->idname = "CUTSCENE_OT_event_add";
	ot->exec = cutscene_event_add_exec;
	ot->poll = cutscene_poll;
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
	RNA_def_int(ot->srna, "sequence_index", 0, 0, INT_MAX, "Sequence Index", "Sequence that receives the event", 0, INT_MAX);
}

static int cutscene_event_remove_exec(bContext *C, wmOperator *op)
{
	Scene *scene = CTX_data_scene(C);
	CutsceneSettings *settings = scene->cutscene_settings;
	const int sequence_index = RNA_int_get(op->ptr, "sequence_index");
	const int event_index = RNA_int_get(op->ptr, "event_index");
	CutsceneSequence *sequence = cutscene_sequence_from_index(scene, sequence_index);
	CutsceneEvent *event;

	if (sequence == NULL) {
		return OPERATOR_CANCELLED;
	}

	event = BLI_findlink(&sequence->events, event_index);
	if (event == NULL) {
		return OPERATOR_CANCELLED;
	}

	BLI_remlink(&sequence->events, event);
	cutscene_event_free(event);

	settings->active_sequence = sequence_index;
	settings->active_event = MIN2(event_index, BLI_listbase_count(&sequence->events) - 1);

	WM_event_add_notifier(C, NC_SCENE | NA_EDITED, scene);
	return OPERATOR_FINISHED;
}

void CUTSCENE_OT_event_remove(wmOperatorType *ot)
{
	ot->name = "Remove Cutscene Event";
	ot->description = "Remove an event from a cutscene sequence";
	ot->idname = "CUTSCENE_OT_event_remove";
	ot->exec = cutscene_event_remove_exec;
	ot->poll = cutscene_poll;
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
	RNA_def_int(ot->srna, "sequence_index", 0, 0, INT_MAX, "Sequence Index", "Sequence that owns the event", 0, INT_MAX);
	RNA_def_int(ot->srna, "event_index", 0, 0, INT_MAX, "Event Index", "Event index to remove", 0, INT_MAX);
}

static int cutscene_event_duplicate_exec(bContext *C, wmOperator *op)
{
	Scene *scene = CTX_data_scene(C);
	CutsceneSettings *settings = scene->cutscene_settings;
	const int sequence_index = RNA_int_get(op->ptr, "sequence_index");
	const int event_index = RNA_int_get(op->ptr, "event_index");
	CutsceneSequence *sequence = cutscene_sequence_from_index(scene, sequence_index);
	CutsceneEvent *event;

	if (sequence == NULL) {
		return OPERATOR_CANCELLED;
	}

	event = BLI_findlink(&sequence->events, event_index);
	if (event == NULL) {
		return OPERATOR_CANCELLED;
	}

	BLI_insertlinkafter(&sequence->events, event, cutscene_event_duplicate(event));
	settings->active_sequence = sequence_index;
	settings->active_event = event_index + 1;

	WM_event_add_notifier(C, NC_SCENE | NA_EDITED, scene);
	return OPERATOR_FINISHED;
}

void CUTSCENE_OT_event_duplicate(wmOperatorType *ot)
{
	ot->name = "Duplicate Cutscene Event";
	ot->description = "Duplicate an event in a cutscene sequence";
	ot->idname = "CUTSCENE_OT_event_duplicate";
	ot->exec = cutscene_event_duplicate_exec;
	ot->poll = cutscene_poll;
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
	RNA_def_int(ot->srna, "sequence_index", 0, 0, INT_MAX, "Sequence Index", "Sequence that owns the event", 0, INT_MAX);
	RNA_def_int(ot->srna, "event_index", 0, 0, INT_MAX, "Event Index", "Event index to duplicate", 0, INT_MAX);
}

static int cutscene_event_move_exec(bContext *C, wmOperator *op)
{
	Scene *scene = CTX_data_scene(C);
	CutsceneSettings *settings = scene->cutscene_settings;
	const int sequence_index = RNA_int_get(op->ptr, "sequence_index");
	const int event_index = RNA_int_get(op->ptr, "event_index");
	const int direction = RNA_enum_get(op->ptr, "direction");
	CutsceneSequence *sequence = cutscene_sequence_from_index(scene, sequence_index);
	CutsceneEvent *event;

	if (sequence == NULL) {
		return OPERATOR_CANCELLED;
	}

	event = BLI_findlink(&sequence->events, event_index);
	if (event == NULL || !BLI_listbase_link_move(&sequence->events, event, direction)) {
		return OPERATOR_CANCELLED;
	}

	settings->active_sequence = sequence_index;
	settings->active_event = event_index + direction;

	WM_event_add_notifier(C, NC_SCENE | NA_EDITED, scene);
	return OPERATOR_FINISHED;
}

void CUTSCENE_OT_event_move(wmOperatorType *ot)
{
	ot->name = "Move Cutscene Event";
	ot->description = "Move an event in a cutscene sequence";
	ot->idname = "CUTSCENE_OT_event_move";
	ot->exec = cutscene_event_move_exec;
	ot->poll = cutscene_poll;
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
	RNA_def_int(ot->srna, "sequence_index", 0, 0, INT_MAX, "Sequence Index", "Sequence that owns the event", 0, INT_MAX);
	RNA_def_int(ot->srna, "event_index", 0, 0, INT_MAX, "Event Index", "Event index to move", 0, INT_MAX);
	RNA_def_enum(ot->srna, "direction", cutscene_move_direction_items, -1, "Direction", "Direction to move the event");
}
