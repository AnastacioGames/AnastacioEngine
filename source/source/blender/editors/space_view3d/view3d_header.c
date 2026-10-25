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
 * The Original Code is Copyright (C) 2004-2008 Blender Foundation.
 * All rights reserved.
 */

/** \file blender/editors/space_view3d/view3d_header.c
 *  \ingroup spview3d
 */

#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#include "DNA_scene_types.h"
#include "DNA_object_types.h"
#include "DNA_gpencil_types.h"

#include "BLI_utildefines.h"

#include "PIL_time.h"

#include "BLT_translation.h"

#include "BKE_context.h"
#include "BKE_depsgraph.h"
#include "BKE_main.h"
#include "BKE_screen.h"
#include "BKE_editmesh.h"

#include "MEM_guardedalloc.h"

#include "RNA_access.h"
#include "RNA_define.h"
#include "RNA_enum_types.h"

#include "WM_api.h"
#include "WM_types.h"

#include "ED_mesh.h"
#include "ED_undo.h"
#include "ED_screen.h"

#include "UI_interface.h"
#include "UI_resources.h"

#include "view3d_intern.h"

static void do_view3d_header_buttons(bContext *C, void *arg, int event);

#define B_SEL_VERT  110
#define B_SEL_EDGE  111
#define B_SEL_FACE  112

/* XXX quickly ported across */
static void handle_view3d_lock(bContext *C)
{
	Main *bmain = CTX_data_main(C);
	Scene *scene = CTX_data_scene(C);
	ScrArea *sa = CTX_wm_area(C);
	View3D *v3d = CTX_wm_view3d(C);

	if (v3d != NULL && sa != NULL) {
		if (v3d->localvd == NULL && v3d->scenelock && sa->spacetype == SPACE_VIEW3D) {
			/* copy to scene */
			scene->lay = v3d->lay;
			scene->layact = v3d->layact;
			scene->camera = v3d->camera;

			/* not through notifier, listener don't have context
			 * and non-open screens or spaces need to be updated too */
			BKE_screen_view3d_main_sync(&bmain->screen, scene);

			/* notifiers for scene update */
			WM_event_add_notifier(C, NC_SCENE | ND_LAYER, scene);
		}
	}
}

/**
 * layer code is on three levels actually:
 * - here for operator
 * - uiTemplateLayers in interface/ code for buttons
 * - ED_view3d_scene_layer_set for RNA
 */
static void view3d_layers_editmode_ensure(Scene *scene, View3D *v3d)
{
	/* sanity check - when in editmode disallow switching the editmode layer off since its confusing
	 * an alternative would be to always draw the editmode object. */
	if (scene->obedit && (scene->obedit->lay & v3d->lay) == 0) {
		int bit;
		for (bit = 0; bit < 32; bit++) {
			if (scene->obedit->lay & (1u << bit)) {
				v3d->lay |= (1u << bit);
				break;
			}
		}
	}
}

/* Same icons as the RNA pivot_point enum. */
int view3d_pivot_point_icon(const View3D *v3d)
{
	switch (v3d->around) {
		case V3D_AROUND_CENTER_BOUNDS: return ICON_ROTATE;
		case V3D_AROUND_CURSOR: return ICON_CURSOR;
		case V3D_AROUND_CENTER_MEDIAN: return ICON_ROTATECENTER;
		case V3D_AROUND_ACTIVE: return ICON_ROTACTIVE;
		default: return ICON_ROTATECOLLECTION;
	}
}

void ED_view3d_layers_shown(Main *bmain, Scene *scene, View3D *v3d, unsigned int lay_old, double t_begin,
                            double dag_seconds)
{
	/* No parallel prefetch here: programs sent ahead and never used were deleted while the AMD driver still
	 * compiled them, freezing the editor for ~30 s. The hidden layer warmup (view3d_draw.c) covers it. */
	UNUSED_VARS(bmain, scene, lay_old);
	view3d_layer_profile_begin(v3d->lay, t_begin, dag_seconds);
}

static int view3d_layers_exec(bContext *C, wmOperator *op)
{
	Scene *scene = CTX_data_scene(C);
	ScrArea *sa = CTX_wm_area(C);
	View3D *v3d = sa->spacedata.first;
	int nr = RNA_int_get(op->ptr, "nr");
	const bool toggle = RNA_boolean_get(op->ptr, "toggle");
	const double t_begin = PIL_check_seconds_timer();
	const unsigned int lay_old = v3d->lay;

	if (nr < 0)
		return OPERATOR_CANCELLED;

	if (nr == 0) {
		/* all layers */
		if (!v3d->lay_prev)
			v3d->lay_prev = 1;

		if (toggle && v3d->lay == ((1 << 20) - 1)) {
			/* return to active layer only */
			v3d->lay = v3d->lay_prev;

			view3d_layers_editmode_ensure(scene, v3d);
		}
		else {
			v3d->lay_prev = v3d->lay;
			v3d->lay |= (1 << 20) - 1;
		}
	}
	else {
		int bit;
		nr--;

		if (RNA_boolean_get(op->ptr, "extend")) {
			if (toggle && v3d->lay & (1 << nr) && (v3d->lay & ~(1 << nr)))
				v3d->lay &= ~(1 << nr);
			else
				v3d->lay |= (1 << nr);
		}
		else {
			v3d->lay = (1 << nr);
		}

		view3d_layers_editmode_ensure(scene, v3d);

		/* set active layer, ensure to always have one */
		if (v3d->lay & (1 << nr))
			v3d->layact = 1 << nr;
		else if ((v3d->lay & v3d->layact) == 0) {
			for (bit = 0; bit < 32; bit++) {
				if (v3d->lay & (1u << bit)) {
					v3d->layact = (1u << bit);
					break;
				}
			}
		}
	}

	if (v3d->scenelock) handle_view3d_lock(C);

	const double t_dag = PIL_check_seconds_timer();
	DAG_on_visible_update(CTX_data_main(C), false);
	ED_view3d_layers_shown(CTX_data_main(C), scene, v3d, lay_old, t_begin, PIL_check_seconds_timer() - t_dag);

	ED_area_tag_redraw(sa);

	return OPERATOR_FINISHED;
}

/* applies shift and alt, lazy coding or ok? :) */
/* the local per-keymap-entry keymap will solve it */
static int view3d_layers_invoke(bContext *C, wmOperator *op, const wmEvent *event)
{
	if (event->ctrl || event->oskey)
		return OPERATOR_PASS_THROUGH;

	if (event->shift)
		RNA_boolean_set(op->ptr, "extend", true);
	else
		RNA_boolean_set(op->ptr, "extend", false);

	if (event->alt) {
		const int nr = RNA_int_get(op->ptr, "nr") + 10;
		RNA_int_set(op->ptr, "nr", nr);
	}
	view3d_layers_exec(C, op);

	return OPERATOR_FINISHED;
}

static bool view3d_layers_poll(bContext *C)
{
	return (ED_operator_view3d_active(C) && CTX_wm_view3d(C)->localvd == NULL);
}

void VIEW3D_OT_layers(wmOperatorType *ot)
{
	/* identifiers */
	ot->name = "Layers";
	ot->description = "Toggle layer(s) visibility";
	ot->idname = "VIEW3D_OT_layers";

	/* api callbacks */
	ot->invoke = view3d_layers_invoke;
	ot->exec = view3d_layers_exec;
	ot->poll = view3d_layers_poll;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	RNA_def_int(ot->srna, "nr", 1, 0, 20, "Number", "The layer number to set, zero for all layers", 0, 20);
	RNA_def_boolean(ot->srna, "extend", 0, "Extend", "Add this layer to the current view layers");
	RNA_def_boolean(ot->srna, "toggle", 1, "Toggle", "Toggle the layer");
}

static void do_view3d_header_buttons(bContext *C, void *UNUSED(arg), int event)
{
	wmWindow *win = CTX_wm_window(C);
	const int ctrl = win->eventstate->ctrl, shift = win->eventstate->shift;

	/* watch it: if sa->win does not exist, check that when calling direct drawing routines */

	switch (event) {
		case B_SEL_VERT:
			if (EDBM_selectmode_toggle(C, SCE_SELECT_VERTEX, -1, shift, ctrl)) {
				ED_undo_push(C, "Selectmode Set: Vertex");
			}
			break;
		case B_SEL_EDGE:
			if (EDBM_selectmode_toggle(C, SCE_SELECT_EDGE, -1, shift, ctrl)) {
				ED_undo_push(C, "Selectmode Set: Edge");
			}
			break;
		case B_SEL_FACE:
			if (EDBM_selectmode_toggle(C, SCE_SELECT_FACE, -1, shift, ctrl)) {
				ED_undo_push(C, "Selectmode Set: Face");
			}
			break;
		default:
			break;
	}
}

void uiTemplateEditModeSelection(uiLayout *layout, struct bContext *C)
{
	Object *obedit = CTX_data_edit_object(C);
	uiBlock *block = uiLayoutGetBlock(layout);

	UI_block_func_handle_set(block, do_view3d_header_buttons, NULL);

	if (obedit && (obedit->type == OB_MESH)) {
		BMEditMesh *em = BKE_editmesh_from_object(obedit);
		uiLayout *row;

		row = uiLayoutRow(layout, true);
		block = uiLayoutGetBlock(row);
		uiDefIconButBitS(block, UI_BTYPE_TOGGLE, SCE_SELECT_VERTEX, B_SEL_VERT, ICON_VERTEXSEL,
		                 0, 0, UI_UNIT_X, UI_UNIT_Y, &em->selectmode, 1.0, 0.0, 0, 0,
		                 TIP_("Vertex select - Shift-Click for multiple modes, Ctrl-Click contracts selection"));
		uiDefIconButBitS(block, UI_BTYPE_TOGGLE, SCE_SELECT_EDGE, B_SEL_EDGE, ICON_EDGESEL,
		                 0, 0, UI_UNIT_X, UI_UNIT_Y, &em->selectmode, 1.0, 0.0, 0, 0,
		                 TIP_("Edge select - Shift-Click for multiple modes, Ctrl-Click expands/contracts selection"));
		uiDefIconButBitS(block, UI_BTYPE_TOGGLE, SCE_SELECT_FACE, B_SEL_FACE, ICON_FACESEL,
		                 0, 0, UI_UNIT_X, UI_UNIT_Y, &em->selectmode, 1.0, 0.0, 0, 0,
		                 TIP_("Face select - Shift-Click for multiple modes, Ctrl-Click expands selection"));
	}
}

static void uiTemplatePaintModeSelection(uiLayout *layout, struct bContext *C)
{
	Scene *scene = CTX_data_scene(C);
	Object *ob = OBACT;

	/* Manipulators aren't used in paint modes */
	if (!ELEM(ob->mode, OB_MODE_SCULPT, OB_MODE_PARTICLE_EDIT)) {
		/* masks aren't used for sculpt and particle painting */
		PointerRNA meshptr;

		RNA_pointer_create(ob->data, &RNA_Mesh, ob->data, &meshptr);
		if (ob->mode & (OB_MODE_TEXTURE_PAINT)) {
			uiItemR(layout, &meshptr, "use_paint_mask", UI_ITEM_R_ICON_ONLY, "", ICON_NONE);
		}
		else {
			uiLayout *row = uiLayoutRow(layout, true);
			uiItemR(row, &meshptr, "use_paint_mask", UI_ITEM_R_ICON_ONLY, "", ICON_NONE);
			uiItemR(row, &meshptr, "use_paint_mask_vertex", UI_ITEM_R_ICON_ONLY, "", ICON_NONE);
		}
	}
}

void uiTemplateHeader3D_mode(uiLayout *layout, struct bContext *C)
{
	/* Extracted from: uiTemplateHeader3D */
	Scene *scene = CTX_data_scene(C);
	Object *ob = OBACT;
	Object *obedit = CTX_data_edit_object(C);
	bGPdata *gpd = CTX_data_gpencil_data(C);

	bool is_paint = (
	        ob && !(gpd && (gpd->flag & GP_DATA_STROKE_EDITMODE)) &&
	        ELEM(ob->mode,
	             OB_MODE_SCULPT, OB_MODE_VERTEX_PAINT, OB_MODE_WEIGHT_PAINT, OB_MODE_TEXTURE_PAINT));

	uiTemplateEditModeSelection(layout, C);
	if ((obedit == NULL) && is_paint) {
		uiTemplatePaintModeSelection(layout, C);
	}
}

void uiTemplateHeader3D(uiLayout *layout, struct bContext *C)
{
	bScreen *screen = CTX_wm_screen(C);
	ScrArea *sa = CTX_wm_area(C);
	View3D *v3d = sa->spacedata.first;
	Scene *scene = CTX_data_scene(C);
	PointerRNA v3dptr, sceneptr;
	Object *ob = OBACT;
	Object *obedit = CTX_data_edit_object(C);
	uiBlock *block;

	RNA_pointer_create(&screen->id, &RNA_SpaceView3D, v3d, &v3dptr);
	RNA_pointer_create(&scene->id, &RNA_Scene, scene, &sceneptr);

	block = uiLayoutGetBlock(layout);
	UI_block_func_handle_set(block, do_view3d_header_buttons, NULL);

	/* other buttons: */
	UI_block_emboss_set(block, UI_EMBOSS);

	/* Mode dropdown, viewport shading, pivot point and the transform
	 * manipulator toggles are already drawn once in the Python header
	 * (mode) and in the floating 3D View controls (shading/manipulators) —
	 * keeping them here too just duplicated the same buttons side by side. */

	if (obedit == NULL && v3d->localvd == NULL) {
		unsigned int ob_lay = ob ? ob->lay : 0;

		/* Layers */
		uiTemplateLayers_ex(layout, v3d->scenelock ? &sceneptr : &v3dptr, "layers", &v3dptr, "layers_used", ob_lay,
		                    (unsigned int)scene->gm.start_lay);

		/* Pinned game layers: popover with a second grid choosing the layers Play starts with. */
		uiItemPopoverPanel(layout, C, "VIEW3D_PT_game_layers", "",
		                   scene->gm.start_lay ? ICON_PINNED : ICON_UNPINNED);

		/* Scene lock button removed from the header; it already lives in the
		 * floating 3D View controls next to the layers popover. */
	}

	/* Currently Python calls this directly. */
#if 0
	uiTemplateEditModeSelection(layout, C);
#endif
}

/* Botões de transformação/exibição da 3D View, na ordem do Blender 5:
 * seleção do Edit | orientação, pivot, snap, proporcional | extras do Edit |
 * layers | gizmo | render/overlay | shading. Usado pelo cabeçalho e pela barra flutuante. */
void view3d_header_tool_controls(uiLayout *row, bContext *C)
{
	bScreen *screen = CTX_wm_screen(C);
	ScrArea *sa = CTX_wm_area(C);
	View3D *v3d = sa->spacedata.first;
	Scene *scene = CTX_data_scene(C);
	const Object *ob = CTX_data_active_object(C);
	const bool edit_mode = (ob != NULL) && ((ob->mode & OB_MODE_EDIT) != 0);
	PointerRNA v3dptr, sceneptr, toolptr;
	PropertyRNA *prop;
	const char *orient_name = NULL;
	int snap_icon = ICON_DOWNARROW_HLT;

	RNA_pointer_create(&screen->id, &RNA_SpaceView3D, v3d, &v3dptr);
	RNA_pointer_create(&scene->id, &RNA_Scene, scene, &sceneptr);
	RNA_pointer_create(&scene->id, &RNA_ToolSettings, scene->toolsettings, &toolptr);

	uiTemplateHeader3D_mode(row, C);
	uiItemS(row);

	/* Orientação: ícone + nome do modo atual ("Global"), como no Blender 5. */
	prop = RNA_struct_find_property(&sceneptr, "transform_orientation");
	if (prop) {
		RNA_property_enum_name_gettexted(C, &sceneptr, prop, RNA_property_enum_get(&sceneptr, prop), &orient_name);
	}
	uiItemPopoverPanel(row, C, "VIEW3D_PT_transform_orientations", orient_name ? orient_name : "", ICON_AXIS_TOP);
	uiItemPopoverPanel(row, C, "VIEW3D_PT_pivot_point", "", view3d_pivot_point_icon(v3d));
	uiItemS(row);

	/* Snap: a seta do popover mostra o alvo atual (vértice, incremento...). */
	prop = RNA_struct_find_property(&toolptr, "snap_element");
	if (prop) {
		const EnumPropertyItem *items;
		bool free;
		RNA_property_enum_items(C, &toolptr, prop, &items, NULL, &free);
		RNA_enum_icon_from_value(items, RNA_property_enum_get(&toolptr, prop), &snap_icon);
		if (free) {
			MEM_freeN((void *)items);
		}
	}
	uiItemR(row, &toolptr, "use_snap", UI_ITEM_R_TOGGLE, "", ICON_SNAP_ON);
	uiItemPopoverPanel(row, C, "VIEW3D_PT_snapping", "", snap_icon);
	uiItemR(row, &toolptr, "proportional_edit", UI_ITEM_R_ICON_ONLY, "", ICON_PROP_OFF);
	uiItemR(row, &toolptr, "proportional_edit_falloff", UI_ITEM_R_ICON_ONLY, "", ICON_NONE);

	if (edit_mode) {
		uiItemS(row);
		uiItemR(row, &toolptr, "use_mesh_automerge", UI_ITEM_R_TOGGLE, "", ICON_AUTOMERGE_ON);
		uiItemR(row, &v3dptr, "use_occlude_geometry", UI_ITEM_R_TOGGLE, "", ICON_RESTRICT_VIEW_ON);
		uiItemPopoverPanel(row, C, "VIEW3D_PT_meshdisplay", "", ICON_IMAGE_COL);
	}
	uiItemS(row);

	uiItemR(row, &v3dptr, "lock_camera_and_layers", UI_ITEM_R_TOGGLE, "", ICON_NONE);
	uiItemPopoverPanel(row, C, "VIEW3D_PT_layer", "", ICON_RENDERLAYERS);
	uiItemS(row);

	/* Gizmo: toggle + popover com mover/girar/escala (antes eram 3 ícones soltos). */
	uiItemR(row, &v3dptr, "show_manipulator", UI_ITEM_R_TOGGLE, "", ICON_MANIPUL);
	uiItemPopoverPanel(row, C, "VIEW3D_PT_gizmo", "", ICON_DOWNARROW_HLT);
	uiItemS(row);

	uiItemR(row, &v3dptr, "realtime_viewport_shading", UI_ITEM_R_TOGGLE, "", ICON_RESTRICT_RENDER_OFF);
	uiItemR(row, &v3dptr, "show_only_render", UI_ITEM_R_TOGGLE, "",
	        (v3d->flag2 & V3D_RENDER_OVERRIDE) ? ICON_RESTRICT_VIEW_ON : ICON_RESTRICT_VIEW_OFF);
	uiItemPopoverPanel(row, C, "VIEW3D_PT_overlay", "", ICON_DOWNARROW_HLT);
	uiItemS(row);

	/* Shading: 4 botões lado a lado + popover, como no Blender 5. */
	/* Só desenha os modos que o enum oferece agora (ex.: Rendered depende do motor). */
	prop = RNA_struct_find_property(&v3dptr, "viewport_shade");
	if (prop) {
		const EnumPropertyItem *items, *it;
		bool free;
		RNA_property_enum_items(C, &v3dptr, prop, &items, NULL, &free);
		for (it = items; it->identifier; it++) {
			if (ELEM(it->value, OB_WIRE, OB_SOLID, OB_MATERIAL, OB_RENDER)) {
				uiItemEnumR_string(row, &v3dptr, "viewport_shade", it->identifier, "", it->icon);
			}
		}
		if (free) {
			MEM_freeN((void *)items);
		}
	}
	uiItemPopoverPanel(row, C, "VIEW3D_PT_shading", "", ICON_DOWNARROW_HLT);
}

void uiTemplateHeader3D_controls(uiLayout *layout, struct bContext *C)
{
	bScreen *screen = CTX_wm_screen(C);
	ScrArea *sa = CTX_wm_area(C);
	View3D *v3d = sa->spacedata.first;
	Scene *scene = CTX_data_scene(C);
	PointerRNA v3dptr;
	PointerRNA gameptr;
	PointerRNA toolptr;
	uiLayout *row;

	RNA_pointer_create(&screen->id, &RNA_SpaceView3D, v3d, &v3dptr);
	RNA_pointer_create(&scene->id, &RNA_SceneGameData, &scene->gm, &gameptr);
	RNA_pointer_create(&scene->id, &RNA_ToolSettings, scene->toolsettings, &toolptr);

	row = uiLayoutRow(layout, true);

	{
		const bool game_ok = (CTX_data_mode_enum(C) == CTX_MODE_OBJECT);
		uiLayout *game_row = uiLayoutRow(row, true);

		uiLayoutSetEnabled(game_row, game_ok);
		/* Cook (convert everything once into the .cooked file) right before Play; Clear Cooked lives in the Cook panel. */
		uiItemO(game_row, "Cook", ICON_COOK, "GAME_OT_cook");
		uiItemO(game_row, "Play", ICON_PLAY, "VIEW3D_OT_game_start");
		uiItemO(game_row, "Standalone", ICON_GHOST_ENABLED, "wm.blenderplayer_start");
		uiItemR(game_row, &gameptr, "use_live_ui", UI_ITEM_R_TOGGLE, "",
		        (scene->gm.flag & GAME_LIVE_UI) ? ICON_UNLOCKED : ICON_LOCKED);
		uiItemR(game_row, &gameptr, "show_console", UI_ITEM_R_TOGGLE, "", ICON_CONSOLE);
	}

	uiItemS(row);
	view3d_header_tool_controls(row, C);
}
