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
 * The Original Code is Copyright (C) 2012 Blender Foundation.
 * All rights reserved.
 */

/** \file blender/editors/space_node/node_toolbar.c
 *  \ingroup nodes
 */

#include "MEM_guardedalloc.h"

#include "BLI_utildefines.h"
#include "BLI_listbase.h"

#include "DNA_node_types.h"
#include "DNA_screen_types.h"
#include "DNA_space_types.h"

#include "BKE_context.h"
#include "BKE_screen.h"

#include "WM_api.h"
#include "WM_types.h"

#include "ED_screen.h"

#include "node_intern.h"  /* own include */


/* ******************* node toolbar registration ************** */

void node_toolbar_register(ARegionType *UNUSED(art))
{
}

/* ********** operator to open/close toolshelf region */

static int node_toolbar_toggle_exec(bContext *C, wmOperator *UNUSED(op))
{
	ScrArea *sa = CTX_wm_area(C);
	ARegion *ar = node_has_tools_region(sa);

	if (ar)
		ED_region_toggle_hidden(C, ar);

	return OPERATOR_FINISHED;
}

/* non-standard poll operator which doesn't care if there are any nodes */
static bool node_toolbar_poll(bContext *C)
{
	ScrArea *sa = CTX_wm_area(C);
	return (sa && (sa->spacetype == SPACE_NODE));
}

void NODE_OT_toolbar(wmOperatorType *ot)
{
	ot->name = "Tool Shelf";
	ot->description = "Toggles tool shelf display";
	ot->idname = "NODE_OT_toolbar";

	ot->exec = node_toolbar_toggle_exec;
	ot->poll = node_toolbar_poll;

	/* flags */
	ot->flag = 0;
}

/* ********** effects shelf: strip of ready-made effects at the bottom (Python panels) */

ARegion *node_has_effects_region(ScrArea *sa)
{
	ARegion *ar = BKE_area_find_region_type(sa, RGN_TYPE_TOOL_PROPS);
	if (ar) {
		return ar;
	}
	/* after the main region, so it takes the bottom of the whole area */
	ar = BKE_area_find_region_type(sa, RGN_TYPE_WINDOW);
	if (ar == NULL) {
		return NULL;
	}
	ARegion *arnew = MEM_callocN(sizeof(ARegion), "node effects shelf");
	BLI_insertlinkbefore(&sa->regionbase, ar, arnew);
	arnew->regiontype = RGN_TYPE_TOOL_PROPS;
	arnew->alignment = RGN_ALIGN_BOTTOM;
	/* on by default: every tree shows its ready-made presets */
	return arnew;
}

static int node_effects_toggle_exec(bContext *C, wmOperator *UNUSED(op))
{
	ARegion *ar = node_has_effects_region(CTX_wm_area(C));
	if (ar) {
		ED_region_toggle_hidden(C, ar);
	}
	return OPERATOR_FINISHED;
}

void NODE_OT_effects_shelf(wmOperatorType *ot)
{
	ot->name = "Effects Shelf";
	ot->description = "Toggles the strip of ready-made effects";
	ot->idname = "NODE_OT_effects_shelf";

	ot->exec = node_effects_toggle_exec;
	ot->poll = node_toolbar_poll;

	ot->flag = 0;
}
