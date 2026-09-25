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
 * The Original Code is Copyright (C) Blender Foundation
 * All rights reserved.
 */

/** \file blender/editors/object/object_animation_event.c
 *  \ingroup edobj
 */

#include "DNA_object_types.h"

#include "BKE_context.h"

#include "WM_api.h"
#include "WM_types.h"

#include "RNA_access.h"
#include "RNA_define.h"

#include "ED_object.h"
#include "ED_screen.h"

#include "BLI_listbase.h"

#ifdef WITH_GAMEENGINE
#  include "BKE_object.h"

#  include "RNA_enum_types.h"
#endif

#include "object_intern.h"

/* Index 0 of Object.animevents (and of each AnimationEvent.triggers) is a hidden base element,
 * so user events and triggers start at index 1. */

static bool object_animation_event_poll(bContext *C)
{
	Object *ob = ED_object_context(C);
	return ob && !ID_IS_LINKED(ob);
}

static void object_animation_event_notify(bContext *C, Object *ob)
{
	WM_event_add_notifier(C, NC_OBJECT | ND_DRAW, ob);
}

static int object_animation_event_add_exec(bContext *C, wmOperator *UNUSED(op))
{
	Object *ob = ED_object_context(C);

#ifdef WITH_GAMEENGINE
	BKE_object_animation_event_add(ob);
	object_animation_event_notify(C, ob);
#else
	(void)ob;
#endif

	return OPERATOR_FINISHED;
}

void OBJECT_OT_animation_event_add(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Add Animation Event";
	ot->description = "Add an animation event to this object";
	ot->idname = "OBJECT_OT_animation_event_add";

	/* api callbacks */
	ot->exec = object_animation_event_add_exec;
	ot->poll = object_animation_event_poll;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
}

static int object_animation_event_remove_exec(bContext *C, wmOperator *op)
{
	Object *ob = ED_object_context(C);
	int index = RNA_int_get(op->ptr, "index");

#ifdef WITH_GAMEENGINE
	if (!BKE_object_animation_event_remove(ob, index)) {
		return OPERATOR_CANCELLED;
	}
	object_animation_event_notify(C, ob);
#else
	(void)ob;
	(void)index;
#endif

	return OPERATOR_FINISHED;
}

void OBJECT_OT_animation_event_remove(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Remove Animation Event";
	ot->description = "Remove an animation event from this object";
	ot->idname = "OBJECT_OT_animation_event_remove";

	/* api callbacks */
	ot->exec = object_animation_event_remove_exec;
	ot->poll = object_animation_event_poll;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	/* properties */
	ot->prop = RNA_def_int(ot->srna, "index", 1, 1, INT_MAX, "Index", "Animation event index", 1, INT_MAX);
}


/* Triggers */
static int object_animation_event_trigger_add_exec(bContext *C, wmOperator *op)
{
	Object *ob = ED_object_context(C);
	int index = RNA_int_get(op->ptr, "index");

#ifdef WITH_GAMEENGINE
	if (!BKE_object_animation_event_trigger_add(ob, CTX_data_scene(C), index)) {
		return OPERATOR_CANCELLED;
	}
	object_animation_event_notify(C, ob);
#else
	(void)ob;
	(void)index;
#endif

	return OPERATOR_FINISHED;
}

void OBJECT_OT_animation_event_trigger_add(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Add Animation Event Trigger";
	ot->description = "Add a frame trigger to this animation event, at the current frame";
	ot->idname = "OBJECT_OT_animation_event_trigger_add";

	/* api callbacks */
	ot->exec = object_animation_event_trigger_add_exec;
	ot->poll = object_animation_event_poll;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	/* properties */
	ot->prop = RNA_def_int(ot->srna, "index", 1, 1, INT_MAX, "Index", "Animation event index", 1, INT_MAX);
}

static int object_animation_event_trigger_remove_exec(bContext *C, wmOperator *op)
{
	Object *ob = ED_object_context(C);
	int index = RNA_int_get(op->ptr, "index");
	int eventIndex = RNA_int_get(op->ptr, "eventIndex");

#ifdef WITH_GAMEENGINE
	if (!BKE_object_animation_event_trigger_remove(ob, eventIndex, index)) {
		return OPERATOR_CANCELLED;
	}
	object_animation_event_notify(C, ob);
#else
	(void)ob;
	(void)index;
	(void)eventIndex;
#endif

	return OPERATOR_FINISHED;
}

void OBJECT_OT_animation_event_trigger_remove(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Remove Animation Event Trigger";
	ot->description = "Remove a frame trigger from this animation event";
	ot->idname = "OBJECT_OT_animation_event_trigger_remove";

	/* api callbacks */
	ot->exec = object_animation_event_trigger_remove_exec;
	ot->poll = object_animation_event_poll;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	/* properties */
	RNA_def_int(ot->srna, "eventIndex", 1, 1, INT_MAX, "Event Index", "Animation event index", 1, INT_MAX);
	ot->prop = RNA_def_int(ot->srna, "index", 1, 1, INT_MAX, "Index", "Trigger index", 1, INT_MAX);
}

static int object_animation_event_trigger_pick_exec(bContext *C, wmOperator *op)
{
	Object *ob = ED_object_context(C);
	int index = RNA_int_get(op->ptr, "index");
	int eventIndex = RNA_int_get(op->ptr, "eventIndex");

#ifdef WITH_GAMEENGINE
	if (!BKE_object_animation_event_trigger_pick(ob, CTX_data_scene(C), eventIndex, index)) {
		return OPERATOR_CANCELLED;
	}
	object_animation_event_notify(C, ob);
#else
	(void)ob;
	(void)index;
	(void)eventIndex;
#endif

	return OPERATOR_FINISHED;
}

void OBJECT_OT_animation_event_trigger_pick(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Pick Current Frame";
	ot->description = "Set this trigger to the current frame of the timeline";
	ot->idname = "OBJECT_OT_animation_event_trigger_pick";

	/* api callbacks */
	ot->exec = object_animation_event_trigger_pick_exec;
	ot->poll = object_animation_event_poll;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	/* properties */
	RNA_def_int(ot->srna, "eventIndex", 1, 1, INT_MAX, "Event Index", "Animation event index", 1, INT_MAX);
	ot->prop = RNA_def_int(ot->srna, "index", 1, 1, INT_MAX, "Index", "Trigger index", 1, INT_MAX);
}


static int object_animation_event_move_up_exec(bContext *C, wmOperator *op)
{
	Object *ob = ED_object_context(C);
	AnimationEvent *p1, *p2;
	int index = RNA_int_get(op->ptr, "index");

	/* Index 1 is the first user event, it can't swap with the hidden base at index 0 */
	if (index < 2) {
		return OPERATOR_CANCELLED;
	}

	p1 = BLI_findlink(&ob->animevents, index);
	p2 = BLI_findlink(&ob->animevents, index - 1);

	if (!p1 || !p2) {
		return OPERATOR_CANCELLED;
	}

	BLI_listbase_swaplinks(&ob->animevents, p1, p2);

	object_animation_event_notify(C, ob);

	return OPERATOR_FINISHED;
}

void OBJECT_OT_animation_event_move_up(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Move Animation Event Up";
	ot->description = "Move this animation event up in the list";
	ot->idname = "OBJECT_OT_animation_event_move_up";

	/* api callbacks */
	ot->exec = object_animation_event_move_up_exec;
	ot->poll = object_animation_event_poll;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	/* properties */
	RNA_def_int(ot->srna, "index", 1, 1, INT_MAX, "Index", "Animation event index to move", 1, INT_MAX);
}

static int object_animation_event_move_down_exec(bContext *C, wmOperator *op)
{
	Object *ob = ED_object_context(C);
	AnimationEvent *p1, *p2;
	int index = RNA_int_get(op->ptr, "index");

	if (index < 1) {
		return OPERATOR_CANCELLED;
	}

	p1 = BLI_findlink(&ob->animevents, index);
	p2 = BLI_findlink(&ob->animevents, index + 1);

	if (!p1 || !p2) {
		return OPERATOR_CANCELLED;
	}

	BLI_listbase_swaplinks(&ob->animevents, p1, p2);

	object_animation_event_notify(C, ob);

	return OPERATOR_FINISHED;
}

void OBJECT_OT_animation_event_move_down(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Move Animation Event Down";
	ot->description = "Move this animation event down in the list";
	ot->idname = "OBJECT_OT_animation_event_move_down";

	/* api callbacks */
	ot->exec = object_animation_event_move_down_exec;
	ot->poll = object_animation_event_poll;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	/* properties */
	RNA_def_int(ot->srna, "index", 1, 1, INT_MAX, "Index", "Animation event index to move", 1, INT_MAX);
}
