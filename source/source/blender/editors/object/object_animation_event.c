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

static int object_animation_event_add_exec(bContext *C, wmOperator *UNUSED(op))
{
	Object *ob = ED_object_context(C);

#ifdef WITH_GAMEENGINE
	BKE_object_animation_event_add(ob);
#else
	(void)ob;
#endif

	return OPERATOR_FINISHED;
}

void OBJECT_OT_animation_event_add(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Add Animation Event";
	ot->description = "Add a Animation Event to this object";
	ot->idname = "OBJECT_OT_animation_event_add";

	/* api callbacks */
	ot->exec = object_animation_event_add_exec;
	ot->poll = ED_operator_object_active;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
}

static int object_animation_event_remove_exec(bContext *C, wmOperator *op)
{
	Object *ob = ED_object_context(C);
	int index = RNA_int_get(op->ptr, "index");

#ifdef WITH_GAMEENGINE
	if (!BKE_object_animation_event_remove(ob, index))
		return OPERATOR_CANCELLED;
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
	ot->description = "Remove a animation event from this object";
	ot->idname = "OBJECT_OT_animation_event_remove";

	/* api callbacks */
	ot->exec = object_animation_event_remove_exec;
	ot->poll = ED_operator_object_active;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	/* properties */
	ot->prop = RNA_def_int(ot->srna, "index", 1, 1, INT_MAX, "Index", "", 1, INT_MAX);
}


/* Triggers */
static int object_animation_event_trigger_add_exec(bContext *C, wmOperator *op)
{
	Object *ob = ED_object_context(C);
	int index = RNA_int_get(op->ptr, "index");

#ifdef WITH_GAMEENGINE
	BKE_object_animation_event_trigger_add(ob, index);
#else
	(void)ob;
#endif

	return OPERATOR_FINISHED;
}

void OBJECT_OT_animation_event_trigger_add(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Add Animation Trigger";
	ot->description = "Add a Animation Event Trigger to this object";
	ot->idname = "OBJECT_OT_animation_event_trigger_add";

	/* api callbacks */
	ot->exec = object_animation_event_trigger_add_exec;
	ot->poll = ED_operator_object_active;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	/* properties */
	ot->prop = RNA_def_int(ot->srna, "index", 1, 1, INT_MAX, "Index", "", 1, INT_MAX);
}

static int object_animation_event_trigger_remove_exec(bContext *C, wmOperator *op)
{
	Object *ob = ED_object_context(C);
	int index = RNA_int_get(op->ptr, "index");
	int eventIndex = RNA_int_get(op->ptr, "eventIndex");

#ifdef WITH_GAMEENGINE
	if (!BKE_object_animation_event_trigger_remove(ob, eventIndex, index))
		return OPERATOR_CANCELLED;
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
	ot->name = "Remove Event Trigger";
	ot->description = "Remove a Animation Event Trigger from this object";
	ot->idname = "OBJECT_OT_animation_event_trigger_remove";

	/* api callbacks */
	ot->exec = object_animation_event_trigger_remove_exec;
	ot->poll = ED_operator_object_active;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	/* properties */
	ot->prop = RNA_def_int(ot->srna, "eventIndex", 1, 1, INT_MAX, "EventIndex", "", 1, INT_MAX);
	ot->prop = RNA_def_int(ot->srna, "index", 1, 1, INT_MAX, "Index", "", 1, INT_MAX);
}

static int object_animation_event_trigger_pick_exec(bContext *C, wmOperator *op)
{
  Object *ob = ED_object_context(C);
  int index = RNA_int_get(op->ptr, "index");
  int eventIndex = RNA_int_get(op->ptr, "eventIndex");

#ifdef WITH_GAMEENGINE
  if (!BKE_object_animation_event_trigger_pick(ob, eventIndex, index))
    return OPERATOR_CANCELLED;
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
  ot->name = "Pick Timeline";
  ot->description = "Pick the current frame of the timeline";
  ot->idname = "OBJECT_OT_animation_event_trigger_pick";

  /* api callbacks */
  ot->exec = object_animation_event_trigger_pick_exec;
  ot->poll = ED_operator_object_active;

  /* flags */
  ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

  /* properties */
  ot->prop = RNA_def_int(ot->srna, "eventIndex", 1, 1, INT_MAX, "EventIndex", "", 1, INT_MAX);
  ot->prop = RNA_def_int(ot->srna, "index", 1, 1, INT_MAX, "Index", "", 1, INT_MAX);
}


static int object_animation_event_move_up_exec(bContext *C, wmOperator *op)
{
  Object *ob = CTX_data_active_object(C);
  AnimationEvent *p1, *p2 = NULL;
  int index = RNA_int_get(op->ptr, "index");

  if (!ob) {
    return OPERATOR_CANCELLED;
  }

  p1 = BLI_findlink(&ob->animevents, index);

  if (!p1 || index < 1) {
    return OPERATOR_CANCELLED;
  }

  p2 = BLI_findlink(&ob->animevents, index - 1);

  if (!p2) {
    return OPERATOR_CANCELLED;
  }

  BLI_listbase_swaplinks(&ob->animevents, p1, p2);

  WM_event_add_notifier(C, NC_OBJECT, NULL);

  return OPERATOR_FINISHED;
}

static bool object_animation_event_move_up_poll(bContext *C)
{
  PointerRNA ptr = CTX_data_pointer_get_type(C, "animevents", &RNA_Object);
  Object *ob = CTX_data_active_object(C);

  if (!ob || ID_IS_LINKED(ob)) {
    return false;
  }

  int count = BLI_listbase_count(&ob->animevents);
  int index = BLI_findindex(&ob->animevents, ptr.data);

  return index < count - 1;
}

void OBJECT_OT_animation_event_move_up(wmOperatorType *ot)
{
  /* identifiers */
  ot->name = "Move Component Up";
  ot->description = "Move Component Up";
  ot->idname = "OBJECT_OT_animation_event_move_up";

  /* api callbacks */
  ot->exec = object_animation_event_move_up_exec;
  ot->poll = object_animation_event_move_up_poll;

  /* flags */
  ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

  /* properties */
  RNA_def_int(ot->srna, "index", 0, 0, INT_MAX, "Index", "Animation Event index to move", 0, INT_MAX);
}

static bool object_animation_event_move_down_poll(bContext *C)
{
  PointerRNA ptr = CTX_data_pointer_get_type(C, "animevents", &RNA_Object);
  Object *ob = CTX_data_active_object(C);

  if (!ob || ID_IS_LINKED(ob)) {
    return false;
  }

  int count = BLI_listbase_count(&ob->animevents);
  int index = BLI_findindex(&ob->animevents, ptr.data);

  return index < count - 1;
}

static int object_animation_event_move_down_exec(bContext *C, wmOperator *op)
{
  Object *ob = CTX_data_active_object(C);
  AnimationEvent *p1, *p2 = NULL;
  int index = RNA_int_get(op->ptr, "index");

  if (!ob) {
    return OPERATOR_CANCELLED;
  }

  p1 = BLI_findlink(&ob->animevents, index);

  if (!p1) {
    return OPERATOR_CANCELLED;
  }

  int count = BLI_listbase_count(&ob->animevents);

  if (index >= count - 1) {
    return OPERATOR_CANCELLED;
  }

  p2 = BLI_findlink(&ob->animevents, index + 1);

  if (!p2) {
    return OPERATOR_CANCELLED;
  }

  BLI_listbase_swaplinks(&ob->animevents, p1, p2);

  WM_event_add_notifier(C, NC_OBJECT, NULL);

  return OPERATOR_FINISHED;
}

void OBJECT_OT_animation_event_move_down(wmOperatorType *ot)
{
  /* identifiers */
  ot->name = "Move Animation Event Down";
  ot->description = "Move Animation Event Down";
  ot->idname = "OBJECT_OT_animation_event_move_down";

  /* api callbacks */
  ot->exec = object_animation_event_move_down_exec;
  ot->poll = object_animation_event_move_down_poll;

  /* flags */
  ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

  /* properties */
  RNA_def_int(ot->srna, "index", 0, 0, INT_MAX, "Index", "Animation Event index to move", 0, INT_MAX);
}
