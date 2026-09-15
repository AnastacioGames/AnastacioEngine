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

/** \file blender/editors/object/object_vehicle.c
 *  \ingroup edobj
 */

#include "DNA_object_types.h"

#include "BKE_context.h"

#include "WM_api.h"
#include "WM_types.h"

#include "RNA_access.h"
#include "RNA_define.h"

#include "ED_screen.h"
#include "ED_object.h"

#ifdef WITH_GAMEENGINE
#  include "BKE_object.h"

#  include "RNA_enum_types.h"
#endif

#include "object_intern.h"

static int object_vehicle_wheel_add_exec(bContext *C, wmOperator *UNUSED(op))
{
	Object *ob = ED_object_context(C);

#ifdef WITH_GAMEENGINE
	BKE_object_vehicle_wheel_add(ob);
#else
	(void)ob;
#endif

	WM_event_add_notifier(C, NC_OBJECT | ND_DRAW, ob);
	return OPERATOR_FINISHED;
}

void OBJECT_OT_vehicle_wheel_add(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Add Vehicle Wheel";
	ot->description = "Add a wheel slot to this vehicle chassis";
	ot->idname = "OBJECT_OT_vehicle_wheel_add";

	/* api callbacks */
	ot->exec = object_vehicle_wheel_add_exec;
	ot->poll = ED_operator_object_active;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
}

static int object_vehicle_wheel_remove_exec(bContext *C, wmOperator *op)
{
	Object *ob = ED_object_context(C);
	int index = RNA_int_get(op->ptr, "index");

#ifdef WITH_GAMEENGINE
	if (!BKE_object_vehicle_wheel_remove(ob, index))
		return OPERATOR_CANCELLED;
#else
	(void)ob;
	(void)index;
#endif

	WM_event_add_notifier(C, NC_OBJECT | ND_DRAW, ob);
	return OPERATOR_FINISHED;
}

void OBJECT_OT_vehicle_wheel_remove(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Remove Vehicle Wheel";
	ot->description = "Remove a wheel slot from this vehicle chassis";
	ot->idname = "OBJECT_OT_vehicle_wheel_remove";

	/* api callbacks */
	ot->exec = object_vehicle_wheel_remove_exec;
	ot->poll = ED_operator_object_active;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	/* properties */
	ot->prop = RNA_def_int(ot->srna, "index", 0, 0, INT_MAX, "Index", "", 0, INT_MAX);
}

static int object_vehicle_gear_add_exec(bContext *C, wmOperator *UNUSED(op))
{
	Object *ob = ED_object_context(C);

#ifdef WITH_GAMEENGINE
	BKE_object_vehicle_gear_add(ob);
#else
	(void)ob;
#endif

	WM_event_add_notifier(C, NC_OBJECT | ND_DRAW, ob);
	return OPERATOR_FINISHED;
}

void OBJECT_OT_vehicle_gear_add(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Add Vehicle Gear";
	ot->description = "Add a gear ratio slot to this vehicle chassis's gearbox";
	ot->idname = "OBJECT_OT_vehicle_gear_add";

	/* api callbacks */
	ot->exec = object_vehicle_gear_add_exec;
	ot->poll = ED_operator_object_active;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
}

static int object_vehicle_gear_remove_exec(bContext *C, wmOperator *op)
{
	Object *ob = ED_object_context(C);
	int index = RNA_int_get(op->ptr, "index");

#ifdef WITH_GAMEENGINE
	if (!BKE_object_vehicle_gear_remove(ob, index))
		return OPERATOR_CANCELLED;
#else
	(void)ob;
	(void)index;
#endif

	WM_event_add_notifier(C, NC_OBJECT | ND_DRAW, ob);
	return OPERATOR_FINISHED;
}

void OBJECT_OT_vehicle_gear_remove(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Remove Vehicle Gear";
	ot->description = "Remove a gear ratio slot from this vehicle chassis's gearbox";
	ot->idname = "OBJECT_OT_vehicle_gear_remove";

	/* api callbacks */
	ot->exec = object_vehicle_gear_remove_exec;
	ot->poll = ED_operator_object_active;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	/* properties */
	ot->prop = RNA_def_int(ot->srna, "index", 0, 0, INT_MAX, "Index", "", 0, INT_MAX);
}
