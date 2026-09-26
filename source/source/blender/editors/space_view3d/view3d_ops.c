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
 * The Original Code is Copyright (C) 2008 Blender Foundation.
 * All rights reserved.
 */

/** \file blender/editors/space_view3d/view3d_ops.c
 *  \ingroup spview3d
 */


#include <stdlib.h>
#include <math.h>

#include "MEM_guardedalloc.h"


#include "DNA_material_types.h"
#include "DNA_object_types.h"
#include "DNA_group_types.h"
#include "DNA_scene_types.h"
#include "DNA_screen_types.h"
#include "DNA_space_types.h"
#include "DNA_view3d_types.h"

#include "BLI_blenlib.h"
#include "BLI_ghash.h"
#include "BLI_math.h"
#include "BLI_utildefines.h"

#include "BLO_readfile.h"

#include "BKE_appdir.h"
#include "BKE_blender_copybuffer.h"
#include "BKE_context.h"
#include "BKE_depsgraph.h"
#include "BKE_group.h"
#include "BKE_idcode.h"
#include "BKE_library.h"
#include "BKE_main.h"
#include "BKE_material.h"
#include "BKE_report.h"
#include "BKE_scene.h"

#include "RNA_access.h"
#include "RNA_define.h"

#include "WM_api.h"
#include "WM_types.h"

#include "ED_object.h"
#include "ED_screen.h"
#include "ED_transform.h"

#include "view3d_intern.h"

#ifdef WIN32
#  include "BLI_math_base.h" /* M_PI */
#endif

/* ************************** copy paste ***************************** */

static int view3d_copybuffer_exec(bContext *C, wmOperator *op)
{
	Main *bmain = CTX_data_main(C);
	char str[FILE_MAX];

	BKE_copybuffer_begin(bmain);

	/* context, selection, could be generalized */
	CTX_DATA_BEGIN (C, Object *, ob, selected_objects)
	{
		BKE_copybuffer_tag_ID(&ob->id);
	}
	CTX_DATA_END;

	for (Group *group = bmain->group.first; group; group = group->id.next) {
		for (GroupObject *go = group->gobject.first; go; go = go->next) {
			if (go->ob && (go->ob->id.tag & LIB_TAG_DOIT)) {
				BKE_copybuffer_tag_ID(&group->id);
				/* don't expand out to all other objects */
				group->id.tag &= ~LIB_TAG_NEED_EXPAND;
				break;
			}
		}
	}

	BLI_make_file_string("/", str, BKE_tempdir_base(), "copybuffer.blend");
	BKE_copybuffer_save(bmain, str, op->reports);

	BKE_report(op->reports, RPT_INFO, "Copied selected objects to buffer");

	return OPERATOR_FINISHED;
}

static void VIEW3D_OT_copybuffer(wmOperatorType *ot)
{

	/* identifiers */
	ot->name = "Copy Selection to Buffer";
	ot->idname = "VIEW3D_OT_copybuffer";
	ot->description = "Selected objects are saved in a temp file";

	/* api callbacks */
	ot->exec = view3d_copybuffer_exec;
	ot->poll = ED_operator_scene;
}

static int view3d_pastebuffer_exec(bContext *C, wmOperator *op)
{
	char str[FILE_MAX];
	short flag = 0;

	if (RNA_boolean_get(op->ptr, "autoselect"))
		flag |= FILE_AUTOSELECT;
	if (RNA_boolean_get(op->ptr, "active_layer"))
		flag |= FILE_ACTIVELAY;

	BLI_make_file_string("/", str, BKE_tempdir_base(), "copybuffer.blend");
	if (BKE_copybuffer_paste(C, str, flag, op->reports)) {
		WM_event_add_notifier(C, NC_WINDOW, NULL);

		BKE_report(op->reports, RPT_INFO, "Objects pasted from buffer");

		return OPERATOR_FINISHED;
	}

	BKE_report(op->reports, RPT_INFO, "No buffer to paste from");

	return OPERATOR_CANCELLED;
}

static void VIEW3D_OT_pastebuffer(wmOperatorType *ot)
{

	/* identifiers */
	ot->name = "Paste Selection from Buffer";
	ot->idname = "VIEW3D_OT_pastebuffer";
	ot->description = "Contents of copy buffer gets pasted";

	/* api callbacks */
	ot->exec = view3d_pastebuffer_exec;
	ot->poll = ED_operator_scene_editable;

	/* flags */
	ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;

	RNA_def_boolean(ot->srna, "autoselect", true, "Select", "Select pasted objects");
	RNA_def_boolean(ot->srna, "active_layer", true, "Active Layer", "Put pasted objects on the active layer");
}

static int view3d_import_obj_drop_exec(bContext *C, wmOperator *op)
{
	char filepath[FILE_MAX];
	wmOperatorType *import_ot = WM_operatortype_find("IMPORT_SCENE_OT_obj", false);
	PointerRNA props;
	int result;

	RNA_string_get(op->ptr, "filepath", filepath);
	if (!BLI_path_extension_check(filepath, ".obj") || !BLI_is_file(filepath)) {
		BKE_report(op->reports, RPT_ERROR, "Dropped OBJ file does not exist");
		return OPERATOR_CANCELLED;
	}

	if (import_ot == NULL) {
		wmOperatorType *enable_ot = WM_operatortype_find("WM_OT_addon_enable", false);
		if (enable_ot != NULL) {
			WM_operator_properties_create_ptr(&props, enable_ot);
			RNA_string_set(&props, "module", "io_scene_obj");
			WM_operator_name_call_ptr(C, enable_ot, WM_OP_EXEC_DEFAULT, &props);
			WM_operator_properties_free(&props);
			import_ot = WM_operatortype_find("IMPORT_SCENE_OT_obj", false);
		}
	}
	if (import_ot == NULL) {
		BKE_report(op->reports, RPT_ERROR, "OBJ importer is unavailable");
		return OPERATOR_CANCELLED;
	}

	WM_operator_properties_create_ptr(&props, import_ot);
	RNA_string_set(&props, "filepath", filepath);
	result = WM_operator_name_call_ptr(C, import_ot, WM_OP_EXEC_DEFAULT, &props);
	WM_operator_properties_free(&props);
	return result;
}

static void VIEW3D_OT_import_obj_drop(wmOperatorType *ot)
{
	ot->name = "Import Dropped OBJ";
	ot->idname = "VIEW3D_OT_import_obj_drop";
	ot->description = "Import a dropped Wavefront OBJ file directly into the scene";
	ot->exec = view3d_import_obj_drop_exec;
	ot->poll = ED_operator_scene_editable;

	RNA_def_string_file_path(ot->srna, "filepath", NULL, FILE_MAX, "File Path", "OBJ file to import");
}

/* ************************** asset drop ***************************** */

/* Parse a path dragged from the File Browser pointing inside a .blend
 * ("lib.blend/Object/Cube"). Only data-blocks the 3D View can place are
 * accepted. Cheap text test first: drop polls run on every mouse move. */
bool view3d_asset_drop_path_parse(const char *path, char *r_libpath, short *r_idcode, char *r_name)
{
	char dir[FILE_MAX_LIBEXTRA];
	char *group, *name;
	short idcode;

	if (path == NULL || BLI_strcasestr(path, ".blend") == NULL) {
		return false;
	}
	if (!BLO_library_path_explode(path, dir, &group, &name) || group == NULL || name == NULL) {
		return false;
	}

	idcode = BKE_idcode_from_name(group);
	if (!ELEM(idcode, ID_OB, ID_GR, ID_MA)) {
		return false;
	}

	if (r_libpath) {
		BLI_strncpy(r_libpath, dir, FILE_MAX_LIBEXTRA);
	}
	if (r_idcode) {
		*r_idcode = idcode;
	}
	if (r_name) {
		BLI_strncpy(r_name, name, MAX_ID_NAME - 2);
	}
	return true;
}

static GSet *asset_drop_id_set(ListBase *lb)
{
	GSet *set = BLI_gset_ptr_new(__func__);
	ID *id;

	for (id = lb->first; id; id = id->next) {
		BLI_gset_add(set, id);
	}
	return set;
}

/* Find the data-block brought by the append/link. Appending renames on
 * conflict (Cube -> Cube.001), so prefer a new ID; linking an ID that is
 * already linked returns the existing one from the same library. */
static ID *asset_drop_find_id(ListBase *lb, GSet *existing, const char *libpath, const char *name, bool link)
{
	const size_t name_len = strlen(name);
	ID *id;

	for (id = lb->first; id; id = id->next) {
		if (!BLI_gset_haskey(existing, id) && STREQLEN(id->name + 2, name, name_len) &&
		    ELEM(id->name[2 + name_len], '\0', '.'))
		{
			return id;
		}
	}
	if (link) {
		for (id = lb->first; id; id = id->next) {
			if (id->lib && STREQ(id->name + 2, name) && BLI_path_cmp(id->lib->filepath, libpath) == 0) {
				return id;
			}
		}
	}
	return NULL;
}

/* The Append/Link toggle of an open Asset Browser (any window). */
static bool asset_drop_browser_wants_link(bContext *C)
{
	wmWindowManager *wm = CTX_wm_manager(C);
	wmWindow *win;
	ScrArea *sa;

	for (win = wm->windows.first; win; win = win->next) {
		for (sa = win->screen->areabase.first; sa; sa = sa->next) {
			if (sa->spacetype == SPACE_FILE) {
				SpaceFile *sfile = sa->spacedata.first;
				if (sfile->op == NULL && sfile->browse_mode == FILE_BROWSE_MODE_ASSETS &&
				    sfile->params && (sfile->params->flag & FILE_LINK))
				{
					return true;
				}
			}
		}
	}
	return false;
}

static int view3d_asset_drop_exec(bContext *C, wmOperator *op)
{
	Main *bmain = CTX_data_main(C);
	Scene *scene = CTX_data_scene(C);
	wmWindow *win = CTX_wm_window(C);
	ARegion *ar = CTX_wm_region(C);
	const wmEvent *event = win ? win->eventstate : NULL;
	wmOperatorType *append_ot;
	PropertyRNA *prop;
	PointerRNA props;
	char path[FILE_MAX_LIBEXTRA], libpath[FILE_MAX_LIBEXTRA], name[MAX_ID_NAME - 2];
	char directory[FILE_MAX_LIBEXTRA];
	int mval[2] = {0, 0};
	Base *target = NULL;
	ListBase *lb;
	GSet *existing;
	ID *id;
	short idcode;
	bool link, has_mouse;
	int result;

	RNA_string_get(op->ptr, "filepath", path);
	if (!view3d_asset_drop_path_parse(path, libpath, &idcode, name)) {
		BKE_reportf(op->reports, RPT_ERROR, "'%s' is not an object, group or material inside a .blend", path);
		return OPERATOR_CANCELLED;
	}
	if (BLI_path_cmp(BKE_main_blendfile_path(bmain), libpath) == 0) {
		BKE_report(op->reports, RPT_ERROR, "Cannot drop assets from the file being edited");
		return OPERATOR_CANCELLED;
	}

	/* Ctrl while dropping (or the Link toggle of the Asset Browser) links instead of appending. */
	prop = RNA_struct_find_property(op->ptr, "link");
	if (RNA_property_is_set(op->ptr, prop)) {
		link = RNA_property_boolean_get(op->ptr, prop);
	}
	else {
		link = (event && event->ctrl);
		/* The browser toggle is a preference: objects, which can not be linked, are still appended. */
		if (!link && idcode != ID_OB) {
			link = asset_drop_browser_wants_link(C);
		}
	}
	if (link && idcode == ID_OB) {
		/* A linked object cannot be moved to the drop point. */
		BKE_report(op->reports, RPT_ERROR, "Objects can only be appended; link a Group instead");
		return OPERATOR_CANCELLED;
	}

	/* Called from a script or another editor there is no drop point:
	 * objects go to the 3D cursor. */
	has_mouse = event && ar && ar->regiontype == RGN_TYPE_WINDOW && CTX_wm_region_view3d(C);
	if (has_mouse) {
		mval[0] = event->x - ar->winrct.xmin;
		mval[1] = event->y - ar->winrct.ymin;
	}

	if (idcode == ID_MA) {
		/* Check the target before bringing anything into the file. */
		/* Without drop point (double-click in the Asset Browser, scripts): the active object. */
		target = has_mouse ? ED_view3d_give_base_under_cursor(C, mval) : BASACT;
		if (target && !OB_TYPE_SUPPORT_MATERIAL(target->object->type)) {
			target = NULL;
		}
		if (target == NULL) {
			BKE_report(op->reports, RPT_ERROR, "Drop the material on an object");
			return OPERATOR_CANCELLED;
		}
	}

	append_ot = WM_operatortype_find(link ? "WM_OT_link" : "WM_OT_append", false);
	if (append_ot == NULL) {
		return OPERATOR_CANCELLED;
	}

	lb = which_libbase(bmain, idcode);
	existing = asset_drop_id_set(lb);

	BLI_join_dirfile(directory, sizeof(directory), libpath, BKE_idcode_to_name(idcode));
	BLI_add_slash(directory);

	WM_operator_properties_create_ptr(&props, append_ot);
	RNA_string_set(&props, "directory", directory);
	RNA_string_set(&props, "filename", name);
	RNA_boolean_set(&props, "autoselect", idcode != ID_MA);
	RNA_boolean_set(&props, "active_layer", true);
	RNA_boolean_set(&props, "instance_groups", idcode == ID_GR);
	result = WM_operator_name_call_ptr(C, append_ot, WM_OP_EXEC_DEFAULT, &props);
	WM_operator_properties_free(&props);

	id = (result & OPERATOR_FINISHED) ? asset_drop_find_id(lb, existing, libpath, name, link) : NULL;
	BLI_gset_free(existing, NULL);

	if (id == NULL) {
		BKE_reportf(op->reports, RPT_ERROR, "Could not load '%s' from '%s'", name, libpath);
		return OPERATOR_CANCELLED;
	}

	if (idcode == ID_MA) {
		assign_material(bmain, target->object, (Material *)id, 1, BKE_MAT_ASSIGN_USERPREF);
		DAG_id_tag_update(&target->object->id, OB_RECALC_OB);
		WM_event_add_notifier(C, NC_OBJECT | ND_OB_SHADING, target->object);
		WM_event_add_notifier(C, NC_MATERIAL | ND_SHADING_LINKS, id);
	}
	else {
		/* Append/link selected exactly what arrived: for a Group that is the
		 * instancing Empty (made active, at the 3D cursor), for an Object the
		 * object plus parents/children brought with it. Move the hierarchy
		 * roots so the dropped item lands under the mouse. */
		Object *ref = (Object *)id;
		float loc[3], offset[3];
		Base *base, *base_next;

		if (idcode == ID_GR) {
			Group *group = (Group *)id;
			Object *inst = NULL;

			for (base = scene->base.first; base; base = base_next) {
				base_next = base->next;
				if ((base->flag & SELECT) == 0) {
					continue;
				}
				if (base->object->dup_group == group) {
					inst = base->object;
				}
				else if (BKE_group_object_exists(group, base->object)) {
					/* Appending also gives bases to the group's objects (T27437);
					 * keep only the instance, like the modern Asset Browser. The
					 * object must survive: the group still uses it. */
					Object *ob = base->object;
					BKE_scene_base_unlink(scene, base);
					MEM_freeN(base);
					id_us_min(&ob->id);
					id_us_ensure_real(&ob->id);
					DAG_id_type_tag(bmain, ID_OB);
				}
			}
			if (inst == NULL) {
				BKE_report(op->reports, RPT_ERROR, "Group was loaded but no instance was created");
				return OPERATOR_CANCELLED;
			}
			ref = inst;
		}

		while (ref->parent) {
			ref = ref->parent;
		}

		ED_object_location_from_view(C, loc);
		if (has_mouse) {
			ED_view3d_cursor3d_position(C, mval, loc);
		}
		sub_v3_v3v3(offset, loc, ref->loc);

		for (base = scene->base.first; base; base = base->next) {
			Object *ob = base->object;
			if ((base->flag & SELECT) && ob->id.lib == NULL &&
			    (ob->parent == NULL || (ob->parent->flag & SELECT) == 0))
			{
				add_v3_v3(ob->loc, offset);
				DAG_id_tag_update(&ob->id, OB_RECALC_OB);
			}
		}

		DAG_relations_tag_update(bmain);
		base = BKE_scene_base_find(scene, (idcode == ID_GR) ? ref : (Object *)id);
		if (base) {
			ED_base_object_activate(C, base);
		}
		WM_event_add_notifier(C, NC_SCENE | ND_OB_ACTIVE, scene);
		WM_event_add_notifier(C, NC_SCENE | ND_TRANSFORM, scene);
	}

	return OPERATOR_FINISHED;
}

static void VIEW3D_OT_asset_drop(wmOperatorType *ot)
{
	PropertyRNA *prop;

	ot->name = "Drop Asset";
	ot->idname = "VIEW3D_OT_asset_drop";
	ot->description = "Append (or link with Ctrl) an object, group or material dragged from a .blend "
	                  "and place it where it was dropped";
	ot->exec = view3d_asset_drop_exec;
	ot->poll = ED_operator_objectmode;

	ot->flag = OPTYPE_UNDO | OPTYPE_INTERNAL;

	prop = RNA_def_string(ot->srna, "filepath", NULL, FILE_MAX_LIBEXTRA, "File Path",
	                      "Data-block inside a .blend (lib.blend/Object/Name)");
	RNA_def_property_flag(prop, PROP_SKIP_SAVE);
	prop = RNA_def_boolean(ot->srna, "link", false, "Link", "Link instead of appending (default: Ctrl held)");
	RNA_def_property_flag(prop, PROP_SKIP_SAVE);
}

/* ************************** registration **********************************/

void view3d_operatortypes(void)
{
	WM_operatortype_append(VIEW3D_OT_import_obj_drop);
	WM_operatortype_append(VIEW3D_OT_asset_drop);
	WM_operatortype_append(VIEW3D_OT_rotate);
	WM_operatortype_append(VIEW3D_OT_move);
	WM_operatortype_append(VIEW3D_OT_zoom);
	WM_operatortype_append(VIEW3D_OT_zoom_camera_1_to_1);
	WM_operatortype_append(VIEW3D_OT_dolly);
#ifdef WITH_INPUT_NDOF
	WM_operatortype_append(VIEW3D_OT_ndof_orbit_zoom);
	WM_operatortype_append(VIEW3D_OT_ndof_orbit);
	WM_operatortype_append(VIEW3D_OT_ndof_pan);
	WM_operatortype_append(VIEW3D_OT_ndof_all);
#endif /* WITH_INPUT_NDOF */
	WM_operatortype_append(VIEW3D_OT_view_all);
	WM_operatortype_append(VIEW3D_OT_viewnumpad);
	WM_operatortype_append(VIEW3D_OT_view_orbit);
	WM_operatortype_append(VIEW3D_OT_view_roll);
	WM_operatortype_append(VIEW3D_OT_view_pan);
	WM_operatortype_append(VIEW3D_OT_view_persportho);
	WM_operatortype_append(VIEW3D_OT_background_image_add);
	WM_operatortype_append(VIEW3D_OT_background_image_remove);
	WM_operatortype_append(VIEW3D_OT_view_selected);
	WM_operatortype_append(VIEW3D_OT_view_lock_clear);
	WM_operatortype_append(VIEW3D_OT_view_lock_to_active);
	WM_operatortype_append(VIEW3D_OT_view_center_cursor);
	WM_operatortype_append(VIEW3D_OT_view_center_pick);
	WM_operatortype_append(VIEW3D_OT_view_center_camera);
	WM_operatortype_append(VIEW3D_OT_view_center_lock);
	WM_operatortype_append(VIEW3D_OT_select);
	WM_operatortype_append(VIEW3D_OT_select_border);
	WM_operatortype_append(VIEW3D_OT_clip_border);
	WM_operatortype_append(VIEW3D_OT_select_circle);
	WM_operatortype_append(VIEW3D_OT_smoothview);
	WM_operatortype_append(VIEW3D_OT_render_border);
	WM_operatortype_append(VIEW3D_OT_clear_render_border);
	WM_operatortype_append(VIEW3D_OT_zoom_border);
	WM_operatortype_append(VIEW3D_OT_manipulator);
	WM_operatortype_append(VIEW3D_OT_enable_manipulator);
	WM_operatortype_append(VIEW3D_OT_cursor3d);
	WM_operatortype_append(VIEW3D_OT_select_lasso);
	WM_operatortype_append(VIEW3D_OT_select_menu);
	WM_operatortype_append(VIEW3D_OT_camera_to_view);
	WM_operatortype_append(VIEW3D_OT_camera_to_view_selected);
	WM_operatortype_append(VIEW3D_OT_object_as_camera);
	WM_operatortype_append(VIEW3D_OT_localview);
	WM_operatortype_append(VIEW3D_OT_game_start);
	WM_operatortype_append(VIEW3D_OT_fly);
	WM_operatortype_append(VIEW3D_OT_walk);
	WM_operatortype_append(VIEW3D_OT_navigate);
	WM_operatortype_append(VIEW3D_OT_ruler);
	WM_operatortype_append(VIEW3D_OT_layers);
	WM_operatortype_append(VIEW3D_OT_copybuffer);
	WM_operatortype_append(VIEW3D_OT_pastebuffer);

	WM_operatortype_append(VIEW3D_OT_properties);
	WM_operatortype_append(VIEW3D_OT_toolshelf);

	WM_operatortype_append(VIEW3D_OT_snap_selected_to_grid);
	WM_operatortype_append(VIEW3D_OT_snap_selected_to_cursor);
	WM_operatortype_append(VIEW3D_OT_snap_selected_to_active);
	WM_operatortype_append(VIEW3D_OT_snap_cursor_to_grid);
	WM_operatortype_append(VIEW3D_OT_snap_cursor_to_center);
	WM_operatortype_append(VIEW3D_OT_snap_cursor_to_selected);
	WM_operatortype_append(VIEW3D_OT_snap_cursor_to_active);

	WM_operatortype_append(VIEW3D_OT_toggle_render);

	transform_operatortypes();
}

void view3d_keymap(wmKeyConfig *keyconf)
{
	wmKeyMap *keymap;
	wmKeyMapItem *kmi;

	keymap = WM_keymap_ensure(keyconf, "3D View Generic", SPACE_VIEW3D, 0);

	WM_keymap_add_item(keymap, "VIEW3D_OT_properties", NKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_toolshelf", TKEY, KM_PRESS, 0, 0);

	/* only for region 3D window */
	keymap = WM_keymap_ensure(keyconf, "3D View", SPACE_VIEW3D, 0);

	/* Shift+LMB behavior first, so it has priority over KM_ANY item below. */
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_manipulator", LEFTMOUSE, KM_PRESS, KM_SHIFT, 0);
	RNA_boolean_set(kmi->ptr, "release_confirm", true);
	RNA_boolean_set(kmi->ptr, "use_planar_constraint", true);
	RNA_boolean_set(kmi->ptr, "use_accurate", false);

	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_manipulator", LEFTMOUSE, KM_PRESS, KM_SHIFT, 0);
	RNA_boolean_set(kmi->ptr, "release_confirm", true);
	RNA_boolean_set(kmi->ptr, "use_planar_constraint", false);
	RNA_boolean_set(kmi->ptr, "use_accurate", true);

	/* Using KM_ANY here to allow holding modifiers before starting to transform. */
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_manipulator", LEFTMOUSE, KM_PRESS, KM_ANY, 0);
	RNA_boolean_set(kmi->ptr, "release_confirm", true);
	RNA_boolean_set(kmi->ptr, "use_planar_constraint", false);
	RNA_boolean_set(kmi->ptr, "use_accurate", false);

	WM_keymap_verify_item(keymap, "VIEW3D_OT_cursor3d", ACTIONMOUSE, KM_PRESS, 0, 0);

	WM_keymap_verify_item(keymap, "VIEW3D_OT_rotate", MIDDLEMOUSE, KM_PRESS, 0, 0);
	WM_keymap_verify_item(keymap, "VIEW3D_OT_move", MIDDLEMOUSE, KM_PRESS, KM_SHIFT, 0);
	WM_keymap_verify_item(keymap, "VIEW3D_OT_zoom", MIDDLEMOUSE, KM_PRESS, KM_CTRL, 0);
	WM_keymap_verify_item(keymap, "VIEW3D_OT_dolly", MIDDLEMOUSE, KM_PRESS, KM_CTRL | KM_SHIFT, 0);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_view_selected", PADPERIOD, KM_PRESS, KM_CTRL, 0);
	RNA_boolean_set(kmi->ptr, "use_all_regions", true);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_view_selected", PADPERIOD, KM_PRESS, 0, 0);
	RNA_boolean_set(kmi->ptr, "use_all_regions", false);

	WM_keymap_verify_item(keymap, "VIEW3D_OT_view_lock_to_active", PADPERIOD, KM_PRESS, KM_SHIFT, 0);
	WM_keymap_verify_item(keymap, "VIEW3D_OT_view_lock_clear", PADPERIOD, KM_PRESS, KM_ALT, 0);

	WM_keymap_verify_item(keymap, "VIEW3D_OT_navigate", FKEY, KM_PRESS, KM_SHIFT, 0);

	WM_keymap_verify_item(keymap, "VIEW3D_OT_smoothview", TIMER1, KM_ANY, KM_ANY, 0);

	WM_keymap_add_item(keymap, "VIEW3D_OT_rotate", MOUSEPAN, 0, 0, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_rotate", MOUSEROTATE, 0, 0, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_move", MOUSEPAN, 0, KM_SHIFT, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_zoom", MOUSEZOOM, 0, 0, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_zoom", MOUSEPAN, 0, KM_CTRL, 0);

	/*numpad +/-*/
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_zoom", PADPLUSKEY, KM_PRESS, 0, 0)->ptr, "delta", 1);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_zoom", PADMINUS, KM_PRESS, 0, 0)->ptr, "delta", -1);
	/*ctrl +/-*/
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_zoom", EQUALKEY, KM_PRESS, KM_CTRL, 0)->ptr, "delta", 1);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_zoom", MINUSKEY, KM_PRESS, KM_CTRL, 0)->ptr, "delta", -1);

	/*wheel mouse forward/back*/
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_zoom", WHEELINMOUSE, KM_PRESS, 0, 0)->ptr, "delta", 1);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_zoom", WHEELOUTMOUSE, KM_PRESS, 0, 0)->ptr, "delta", -1);

	/* ... and for dolly */
	/*numpad +/-*/
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_dolly", PADPLUSKEY, KM_PRESS, KM_SHIFT, 0)->ptr, "delta", 1);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_dolly", PADMINUS, KM_PRESS, KM_SHIFT, 0)->ptr, "delta", -1);
	/*ctrl +/-*/
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_dolly", EQUALKEY, KM_PRESS, KM_CTRL | KM_SHIFT, 0)->ptr, "delta", 1);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_dolly", MINUSKEY, KM_PRESS, KM_CTRL | KM_SHIFT, 0)->ptr, "delta", -1);

	WM_keymap_add_item(keymap, "VIEW3D_OT_zoom_camera_1_to_1", PADENTER, KM_PRESS, KM_SHIFT, 0);

	WM_keymap_add_item(keymap, "VIEW3D_OT_view_center_camera", HOMEKEY, KM_PRESS, 0, 0); /* only with camera view */
	WM_keymap_add_item(keymap, "VIEW3D_OT_view_center_lock", HOMEKEY, KM_PRESS, 0, 0); /* only with lock view */

	WM_keymap_add_item(keymap, "VIEW3D_OT_view_center_cursor", HOMEKEY, KM_PRESS, KM_ALT, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_view_center_pick", FKEY, KM_PRESS, KM_ALT, 0);

	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_view_all", HOMEKEY, KM_PRESS, 0, 0);
	RNA_boolean_set(kmi->ptr, "center", false); /* only without camera view */
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_view_all", HOMEKEY, KM_PRESS, KM_CTRL, 0);
	RNA_boolean_set(kmi->ptr, "use_all_regions", true);
	RNA_boolean_set(kmi->ptr, "center", false); /* only without camera view */
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_view_all", CKEY, KM_PRESS, KM_SHIFT, 0);
	RNA_boolean_set(kmi->ptr, "center", true);

	/* numpad view hotkeys*/
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD0, KM_PRESS, 0, 0)->ptr, "type", RV3D_VIEW_CAMERA);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD1, KM_PRESS, 0, 0)->ptr, "type", RV3D_VIEW_FRONT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_orbit", PAD2, KM_PRESS, 0, 0)->ptr, "type", V3D_VIEW_STEPDOWN);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD3, KM_PRESS, 0, 0)->ptr, "type", RV3D_VIEW_RIGHT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_orbit", PAD4, KM_PRESS, 0, 0)->ptr, "type", V3D_VIEW_STEPLEFT);
	WM_keymap_add_item(keymap, "VIEW3D_OT_view_persportho", PAD5, KM_PRESS, 0, 0);

	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_orbit", PAD6, KM_PRESS, 0, 0)->ptr, "type", V3D_VIEW_STEPRIGHT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD7, KM_PRESS, 0, 0)->ptr, "type", RV3D_VIEW_TOP);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_orbit", PAD8, KM_PRESS, 0, 0)->ptr, "type", V3D_VIEW_STEPUP);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD1, KM_PRESS, KM_CTRL, 0)->ptr, "type", RV3D_VIEW_BACK);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD3, KM_PRESS, KM_CTRL, 0)->ptr, "type", RV3D_VIEW_LEFT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD7, KM_PRESS, KM_CTRL, 0)->ptr, "type", RV3D_VIEW_BOTTOM);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_pan", PAD2, KM_PRESS, KM_CTRL, 0)->ptr, "type", V3D_VIEW_PANDOWN);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_pan", PAD4, KM_PRESS, KM_CTRL, 0)->ptr, "type", V3D_VIEW_PANLEFT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_pan", PAD6, KM_PRESS, KM_CTRL, 0)->ptr, "type", V3D_VIEW_PANRIGHT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_pan", PAD8, KM_PRESS, KM_CTRL, 0)->ptr, "type", V3D_VIEW_PANUP);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_roll", PAD4, KM_PRESS, KM_SHIFT, 0)->ptr, "type", V3D_VIEW_STEPLEFT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_roll", PAD6, KM_PRESS, KM_SHIFT, 0)->ptr, "type", V3D_VIEW_STEPRIGHT);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_view_orbit", PAD9, KM_PRESS, 0, 0);
	RNA_enum_set(kmi->ptr, "type", V3D_VIEW_STEPRIGHT);
	RNA_float_set(kmi->ptr, "angle", (float)M_PI);

	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_pan", WHEELUPMOUSE, KM_PRESS, KM_CTRL, 0)->ptr, "type", V3D_VIEW_PANRIGHT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_pan", WHEELDOWNMOUSE, KM_PRESS, KM_CTRL, 0)->ptr, "type", V3D_VIEW_PANLEFT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_pan", WHEELUPMOUSE, KM_PRESS, KM_SHIFT, 0)->ptr, "type", V3D_VIEW_PANUP);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_pan", WHEELDOWNMOUSE, KM_PRESS, KM_SHIFT, 0)->ptr, "type", V3D_VIEW_PANDOWN);

	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_orbit", WHEELUPMOUSE, KM_PRESS, KM_CTRL | KM_ALT, 0)->ptr, "type", V3D_VIEW_STEPLEFT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_orbit", WHEELDOWNMOUSE, KM_PRESS, KM_CTRL | KM_ALT, 0)->ptr, "type", V3D_VIEW_STEPRIGHT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_orbit", WHEELUPMOUSE, KM_PRESS, KM_SHIFT | KM_ALT, 0)->ptr, "type", V3D_VIEW_STEPUP);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_orbit", WHEELDOWNMOUSE, KM_PRESS, KM_SHIFT | KM_ALT, 0)->ptr, "type", V3D_VIEW_STEPDOWN);

	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_roll", WHEELUPMOUSE, KM_PRESS, KM_CTRL | KM_SHIFT, 0)->ptr, "type", V3D_VIEW_STEPLEFT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_roll", WHEELDOWNMOUSE, KM_PRESS, KM_CTRL | KM_SHIFT, 0)->ptr, "type", V3D_VIEW_STEPRIGHT);

	/* active aligned, replaces '*' key in 2.4x */
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD1, KM_PRESS, KM_SHIFT, 0);
	RNA_enum_set(kmi->ptr, "type", RV3D_VIEW_FRONT);
	RNA_boolean_set(kmi->ptr, "align_active", true);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD3, KM_PRESS, KM_SHIFT, 0);
	RNA_enum_set(kmi->ptr, "type", RV3D_VIEW_RIGHT);
	RNA_boolean_set(kmi->ptr, "align_active", true);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD7, KM_PRESS, KM_SHIFT, 0);
	RNA_enum_set(kmi->ptr, "type", RV3D_VIEW_TOP);
	RNA_boolean_set(kmi->ptr, "align_active", true);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD1, KM_PRESS, KM_SHIFT | KM_CTRL, 0);
	RNA_enum_set(kmi->ptr, "type", RV3D_VIEW_BACK);
	RNA_boolean_set(kmi->ptr, "align_active", true);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD3, KM_PRESS, KM_SHIFT | KM_CTRL, 0);
	RNA_enum_set(kmi->ptr, "type", RV3D_VIEW_LEFT);
	RNA_boolean_set(kmi->ptr, "align_active", true);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", PAD7, KM_PRESS, KM_SHIFT | KM_CTRL, 0);
	RNA_enum_set(kmi->ptr, "type", RV3D_VIEW_BOTTOM);
	RNA_boolean_set(kmi->ptr, "align_active", true);

	WM_keymap_add_item(keymap, "VIEW3D_OT_localview", PADSLASHKEY, KM_PRESS, 0, 0);

#ifdef WITH_INPUT_NDOF
	/* note: positioned here so keymaps show keyboard keys if assigned */
	/* 3D mouse */
	WM_keymap_add_item(keymap, "VIEW3D_OT_ndof_orbit_zoom", NDOF_MOTION, 0, 0, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_ndof_orbit", NDOF_MOTION, 0, KM_CTRL, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_ndof_pan", NDOF_MOTION, 0, KM_SHIFT, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_ndof_all", NDOF_MOTION, 0, KM_CTRL | KM_SHIFT, 0);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_view_selected", NDOF_BUTTON_FIT, KM_PRESS, 0, 0);
	RNA_boolean_set(kmi->ptr, "use_all_regions", false);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_roll", NDOF_BUTTON_ROLL_CCW, KM_PRESS, 0, 0)->ptr, "type", V3D_VIEW_STEPLEFT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_view_roll", NDOF_BUTTON_ROLL_CCW, KM_PRESS, 0, 0)->ptr, "type", V3D_VIEW_STEPRIGHT);

	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", NDOF_BUTTON_FRONT, KM_PRESS, 0, 0)->ptr, "type", RV3D_VIEW_FRONT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", NDOF_BUTTON_BACK, KM_PRESS, 0, 0)->ptr, "type", RV3D_VIEW_BACK);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", NDOF_BUTTON_LEFT, KM_PRESS, 0, 0)->ptr, "type", RV3D_VIEW_LEFT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", NDOF_BUTTON_RIGHT, KM_PRESS, 0, 0)->ptr, "type", RV3D_VIEW_RIGHT);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", NDOF_BUTTON_TOP, KM_PRESS, 0, 0)->ptr, "type", RV3D_VIEW_TOP);
	RNA_enum_set(WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", NDOF_BUTTON_BOTTOM, KM_PRESS, 0, 0)->ptr, "type", RV3D_VIEW_BOTTOM);

	/* 3D mouse align */
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", NDOF_BUTTON_FRONT, KM_PRESS, KM_SHIFT, 0);
	RNA_enum_set(kmi->ptr, "type", RV3D_VIEW_FRONT);
	RNA_boolean_set(kmi->ptr, "align_active", true);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", NDOF_BUTTON_RIGHT, KM_PRESS, KM_SHIFT, 0);
	RNA_enum_set(kmi->ptr, "type", RV3D_VIEW_RIGHT);
	RNA_boolean_set(kmi->ptr, "align_active", true);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_viewnumpad", NDOF_BUTTON_TOP, KM_PRESS, KM_SHIFT, 0);
	RNA_enum_set(kmi->ptr, "type", RV3D_VIEW_TOP);
	RNA_boolean_set(kmi->ptr, "align_active", true);
#endif /* WITH_INPUT_NDOF */

	/* layers, shift + alt are properties set in invoke() */
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_layers", ACCENTGRAVEKEY, KM_PRESS, 0, 0)->ptr, "nr", 0);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_layers", ONEKEY, KM_PRESS, KM_ANY, 0)->ptr, "nr", 1);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_layers", TWOKEY, KM_PRESS, KM_ANY, 0)->ptr, "nr", 2);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_layers", THREEKEY, KM_PRESS, KM_ANY, 0)->ptr, "nr", 3);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_layers", FOURKEY, KM_PRESS, KM_ANY, 0)->ptr, "nr", 4);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_layers", FIVEKEY, KM_PRESS, KM_ANY, 0)->ptr, "nr", 5);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_layers", SIXKEY, KM_PRESS, KM_ANY, 0)->ptr, "nr", 6);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_layers", SEVENKEY, KM_PRESS, KM_ANY, 0)->ptr, "nr", 7);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_layers", EIGHTKEY, KM_PRESS, KM_ANY, 0)->ptr, "nr", 8);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_layers", NINEKEY, KM_PRESS, KM_ANY, 0)->ptr, "nr", 9);
	RNA_int_set(WM_keymap_add_item(keymap, "VIEW3D_OT_layers", ZEROKEY, KM_PRESS, KM_ANY, 0)->ptr, "nr", 10);

	/* drawtype */

	kmi = WM_keymap_add_item(keymap, "WM_OT_context_toggle_enum", ZKEY, KM_PRESS, 0, 0);
	RNA_string_set(kmi->ptr, "data_path", "space_data.viewport_shade");
	RNA_string_set(kmi->ptr, "value_1", "SOLID");
	RNA_string_set(kmi->ptr, "value_2", "WIREFRAME");

	kmi = WM_keymap_add_item(keymap, "WM_OT_context_toggle_enum", ZKEY, KM_PRESS, KM_ALT, 0);
	RNA_string_set(kmi->ptr, "data_path", "space_data.viewport_shade");
	RNA_string_set(kmi->ptr, "value_1", "SOLID");
	RNA_string_set(kmi->ptr, "value_2", "TEXTURED");

	WM_keymap_add_item(keymap, "VIEW3D_OT_toggle_render", ZKEY, KM_PRESS, KM_SHIFT, 0);

	/* selection*/
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_select", SELECTMOUSE, KM_PRESS, 0, 0);
	RNA_boolean_set(kmi->ptr, "extend", false);
	RNA_boolean_set(kmi->ptr, "deselect", false);
	RNA_boolean_set(kmi->ptr, "toggle", false);
	RNA_boolean_set(kmi->ptr, "center", false);
	RNA_boolean_set(kmi->ptr, "object", false);
	RNA_boolean_set(kmi->ptr, "enumerate", false);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_select", SELECTMOUSE, KM_PRESS, KM_SHIFT, 0);
	RNA_boolean_set(kmi->ptr, "extend", false);
	RNA_boolean_set(kmi->ptr, "deselect", false);
	RNA_boolean_set(kmi->ptr, "toggle", true);
	RNA_boolean_set(kmi->ptr, "center", false);
	RNA_boolean_set(kmi->ptr, "object", false);
	RNA_boolean_set(kmi->ptr, "enumerate", false);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_select", SELECTMOUSE, KM_PRESS, KM_CTRL, 0);
	RNA_boolean_set(kmi->ptr, "extend", false);
	RNA_boolean_set(kmi->ptr, "deselect", false);
	RNA_boolean_set(kmi->ptr, "toggle", false);
	RNA_boolean_set(kmi->ptr, "center", true);
	RNA_boolean_set(kmi->ptr, "object", true); /* use Ctrl+Select for 2 purposes */
	RNA_boolean_set(kmi->ptr, "enumerate", false);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_select", SELECTMOUSE, KM_PRESS, KM_ALT, 0);
	RNA_boolean_set(kmi->ptr, "extend", false);
	RNA_boolean_set(kmi->ptr, "deselect", false);
	RNA_boolean_set(kmi->ptr, "toggle", false);
	RNA_boolean_set(kmi->ptr, "center", false);
	RNA_boolean_set(kmi->ptr, "object", false);
	RNA_boolean_set(kmi->ptr, "enumerate", true);

	/* selection key-combinations */
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_select", SELECTMOUSE, KM_PRESS, KM_SHIFT | KM_CTRL, 0);
	RNA_boolean_set(kmi->ptr, "extend", true);
	RNA_boolean_set(kmi->ptr, "deselect", false);
	RNA_boolean_set(kmi->ptr, "toggle", true);
	RNA_boolean_set(kmi->ptr, "center", true);
	RNA_boolean_set(kmi->ptr, "object", false);
	RNA_boolean_set(kmi->ptr, "enumerate", false);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_select", SELECTMOUSE, KM_PRESS, KM_CTRL | KM_ALT, 0);
	RNA_boolean_set(kmi->ptr, "extend", false);
	RNA_boolean_set(kmi->ptr, "deselect", false);
	RNA_boolean_set(kmi->ptr, "toggle", false);
	RNA_boolean_set(kmi->ptr, "center", true);
	RNA_boolean_set(kmi->ptr, "object", false);
	RNA_boolean_set(kmi->ptr, "enumerate", true);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_select", SELECTMOUSE, KM_PRESS, KM_SHIFT | KM_ALT, 0);
	RNA_boolean_set(kmi->ptr, "extend", false);
	RNA_boolean_set(kmi->ptr, "deselect", false);
	RNA_boolean_set(kmi->ptr, "toggle", true);
	RNA_boolean_set(kmi->ptr, "center", false);
	RNA_boolean_set(kmi->ptr, "object", false);
	RNA_boolean_set(kmi->ptr, "enumerate", true);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_select", SELECTMOUSE, KM_PRESS, KM_SHIFT | KM_CTRL | KM_ALT, 0);
	RNA_boolean_set(kmi->ptr, "extend", false);
	RNA_boolean_set(kmi->ptr, "deselect", false);
	RNA_boolean_set(kmi->ptr, "toggle", true);
	RNA_boolean_set(kmi->ptr, "center", true);
	RNA_boolean_set(kmi->ptr, "object", false);
	RNA_boolean_set(kmi->ptr, "enumerate", true);

	WM_keymap_add_item(keymap, "VIEW3D_OT_select_border", BKEY, KM_PRESS, 0, 0);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_select_lasso", EVT_TWEAK_A, KM_ANY, KM_CTRL, 0);
	RNA_boolean_set(kmi->ptr, "deselect", false);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_select_lasso", EVT_TWEAK_A, KM_ANY, KM_SHIFT | KM_CTRL, 0);
	RNA_boolean_set(kmi->ptr, "deselect", true);
	WM_keymap_add_item(keymap, "VIEW3D_OT_select_circle", CKEY, KM_PRESS, 0, 0);

	WM_keymap_add_item(keymap, "VIEW3D_OT_clip_border", BKEY, KM_PRESS, KM_ALT, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_zoom_border", BKEY, KM_PRESS, KM_SHIFT, 0);

	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_render_border", BKEY, KM_PRESS, KM_SHIFT, 0);
	RNA_boolean_set(kmi->ptr, "camera_only", true);
	kmi = WM_keymap_add_item(keymap, "VIEW3D_OT_render_border", BKEY, KM_PRESS, KM_CTRL, 0);
	RNA_boolean_set(kmi->ptr, "camera_only", false);

	WM_keymap_add_item(keymap, "VIEW3D_OT_clear_render_border", BKEY, KM_PRESS, KM_CTRL | KM_ALT, 0);

	WM_keymap_add_item(keymap, "VIEW3D_OT_camera_to_view", PAD0, KM_PRESS, KM_ALT | KM_CTRL, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_object_as_camera", PAD0, KM_PRESS, KM_CTRL, 0);

	WM_keymap_add_menu(keymap, "VIEW3D_MT_snap", SKEY, KM_PRESS, KM_SHIFT, 0);

#ifdef __APPLE__
	WM_keymap_add_item(keymap, "VIEW3D_OT_copybuffer", CKEY, KM_PRESS, KM_OSKEY, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_pastebuffer", VKEY, KM_PRESS, KM_OSKEY, 0);
#endif
	WM_keymap_add_item(keymap, "VIEW3D_OT_copybuffer", CKEY, KM_PRESS, KM_CTRL, 0);
	WM_keymap_add_item(keymap, "VIEW3D_OT_pastebuffer", VKEY, KM_PRESS, KM_CTRL, 0);

	/* context ops */
	kmi = WM_keymap_add_item(keymap, "WM_OT_context_set_enum", COMMAKEY, KM_PRESS, 0, 0);
	RNA_string_set(kmi->ptr, "data_path", "space_data.pivot_point");
	RNA_string_set(kmi->ptr, "value", "BOUNDING_BOX_CENTER");

	kmi = WM_keymap_add_item(keymap, "WM_OT_context_set_enum", COMMAKEY, KM_PRESS, KM_CTRL, 0); /* 2.4x allowed Comma+Shift too, rather not use both */
	RNA_string_set(kmi->ptr, "data_path", "space_data.pivot_point");
	RNA_string_set(kmi->ptr, "value", "MEDIAN_POINT");

	kmi = WM_keymap_add_item(keymap, "WM_OT_context_toggle", COMMAKEY, KM_PRESS, KM_ALT, 0); /* new in 2.5 */
	RNA_string_set(kmi->ptr, "data_path", "space_data.use_pivot_point_align");

	kmi = WM_keymap_add_item(keymap, "WM_OT_context_toggle", SPACEKEY, KM_PRESS, KM_CTRL, 0); /* new in 2.5 */
	RNA_string_set(kmi->ptr, "data_path", "space_data.show_manipulator");

	kmi = WM_keymap_add_item(keymap, "WM_OT_context_set_enum", PERIODKEY, KM_PRESS, 0, 0);
	RNA_string_set(kmi->ptr, "data_path", "space_data.pivot_point");
	RNA_string_set(kmi->ptr, "value", "CURSOR");

	kmi = WM_keymap_add_item(keymap, "WM_OT_context_set_enum", PERIODKEY, KM_PRESS, KM_CTRL, 0);
	RNA_string_set(kmi->ptr, "data_path", "space_data.pivot_point");
	RNA_string_set(kmi->ptr, "value", "INDIVIDUAL_ORIGINS");

	kmi = WM_keymap_add_item(keymap, "WM_OT_context_set_enum", PERIODKEY, KM_PRESS, KM_ALT, 0);
	RNA_string_set(kmi->ptr, "data_path", "space_data.pivot_point");
	RNA_string_set(kmi->ptr, "value", "ACTIVE_ELEMENT");

	transform_keymap_for_space(keyconf, keymap, SPACE_VIEW3D);

	fly_modal_keymap(keyconf);
	walk_modal_keymap(keyconf);
	viewrotate_modal_keymap(keyconf);
	viewmove_modal_keymap(keyconf);
	viewzoom_modal_keymap(keyconf);
	viewdolly_modal_keymap(keyconf);
}
