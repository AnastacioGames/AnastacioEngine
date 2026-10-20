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
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 * Making screendumps.
 */

/** \file blender/editors/screen/screendump.c
 *  \ingroup edscr
 */


#include <string.h>
#include <errno.h>
#include <time.h>

#include "MEM_guardedalloc.h"

#include "BLI_blenlib.h"
#include "BLI_utildefines.h"

#include "IMB_imbuf_types.h"
#include "IMB_imbuf.h"

#include "DNA_scene_types.h"
#include "DNA_screen_types.h"
#include "DNA_space_types.h"

#include "BKE_appdir.h"
#include "BKE_context.h"
#include "BKE_global.h"
#include "BKE_main.h"
#include "BKE_image.h"
#include "BKE_report.h"

#include "BIF_gl.h"

#include "RNA_access.h"
#include "RNA_define.h"

#include "UI_interface.h"

#include "WM_types.h"
#include "WM_api.h"

#include "screen_intern.h"

typedef struct ScreenshotData {
	unsigned int *dumprect;
	int dumpsx, dumpsy;
	rcti crop;

	ImageFormatData im_format;
} ScreenshotData;

static void screenshot_read_pixels(int x, int y, int w, int h, unsigned char *rect)
{
	int i;

	/* glReadPixels into client memory is synchronous already. */
	glReadPixels(x, y, w, h, GL_RGBA, GL_UNSIGNED_BYTE, rect);

	/* clear alpha, it is not set to a meaningful value in opengl */
	for (i = 0, rect += 3; i < w * h; i++, rect += 4)
		*rect = 255;
}

/* get shot from frontbuffer */
static unsigned int *screenshot(bContext *C, int *dumpsx, int *dumpsy)
{
	wmWindow *win = CTX_wm_window(C);
	int x = 0, y = 0;
	unsigned int *dumprect = NULL;

	x = 0;
	y = 0;
	*dumpsx = WM_window_pixels_x(win);
	*dumpsy = WM_window_pixels_y(win);

	if (*dumpsx && *dumpsy) {

		dumprect = MEM_mallocN(sizeof(int) * (*dumpsx) * (*dumpsy), "dumprect");
		glReadBuffer(GL_FRONT);
		screenshot_read_pixels(x, y, *dumpsx, *dumpsy, (unsigned char *)dumprect);
		glReadBuffer(GL_BACK);
	}

	return dumprect;
}

/* call from both exec and invoke */
static int screenshot_data_create(bContext *C, wmOperator *op)
{
	unsigned int *dumprect;
	int dumpsx, dumpsy;

	/* do redraw so we don't show popups/menus */
	WM_redraw_windows(C);

	dumprect = screenshot(C, &dumpsx, &dumpsy);

	if (dumprect) {
		ScreenshotData *scd = MEM_callocN(sizeof(ScreenshotData), "screenshot");
		ScrArea *sa = CTX_wm_area(C);

		scd->dumpsx = dumpsx;
		scd->dumpsy = dumpsy;
		scd->dumprect = dumprect;
		if (sa) {
			scd->crop = sa->totrct;
		}

		BKE_imformat_defaults(&scd->im_format);

		op->customdata = scd;

		return true;
	}
	else {
		op->customdata = NULL;
		return false;
	}
}

static void screenshot_data_free(wmOperator *op)
{
	ScreenshotData *scd = op->customdata;

	if (scd) {
		if (scd->dumprect)
			MEM_freeN(scd->dumprect);
		MEM_freeN(scd);
		op->customdata = NULL;
	}
}

static int screenshot_exec(bContext *C, wmOperator *op)
{
	ScreenshotData *scd = op->customdata;
	bool ok = false;

	if (scd == NULL) {
		/* when running exec directly */
		screenshot_data_create(C, op);
		scd = op->customdata;
	}

	if (scd) {
		if (scd->dumprect) {
			ImBuf *ibuf;
			char path[FILE_MAX];

			RNA_string_get(op->ptr, "filepath", path);
			BLI_path_abs(path, BKE_main_blendfile_path_from_global());

			/* operator ensures the extension */
			ibuf = IMB_allocImBuf(scd->dumpsx, scd->dumpsy, 24, 0);
			ibuf->rect = scd->dumprect;

			/* crop to show only single editor (reallocates the rect) */
			if (!RNA_boolean_get(op->ptr, "full")) {
				IMB_rect_crop(ibuf, &scd->crop);
			}
			scd->dumprect = ibuf->rect;

			if (scd->im_format.planes == R_IMF_PLANES_BW) {
				/* bw screenshot? - users will notice if it fails! */
				IMB_color_to_bw(ibuf);
			}
			if (BKE_imbuf_write(ibuf, path, &scd->im_format)) {
				ok = true;
			}
			else {
				BKE_reportf(op->reports, RPT_ERROR, "Could not write image: %s", strerror(errno));
			}

			IMB_freeImBuf(ibuf);
		}
	}

	screenshot_data_free(op);

	return ok ? OPERATOR_FINISHED : OPERATOR_CANCELLED;
}

static int screenshot_invoke(bContext *C, wmOperator *op, const wmEvent *UNUSED(event))
{
	if (screenshot_data_create(C, op)) {
		if (RNA_struct_property_is_set(op->ptr, "filepath"))
			return screenshot_exec(C, op);

		/* extension is added by 'screenshot_check' after */
		char filepath[FILE_MAX] = "//screen";
		if (G.relbase_valid) {
			BLI_strncpy(filepath, BKE_main_blendfile_path_from_global(), sizeof(filepath));
			BLI_path_extension_replace(filepath, sizeof(filepath), "");  /* strip '.blend' */
		}
		RNA_string_set(op->ptr, "filepath", filepath);

		WM_event_add_fileselect(C, op);

		return OPERATOR_RUNNING_MODAL;
	}
	return OPERATOR_CANCELLED;
}

static bool screenshot_check(bContext *UNUSED(C), wmOperator *op)
{
	ScreenshotData *scd = op->customdata;
	return WM_operator_filesel_ensure_ext_imtype(op, &scd->im_format);
}

static void screenshot_cancel(bContext *UNUSED(C), wmOperator *op)
{
	screenshot_data_free(op);
}

static bool screenshot_draw_check_prop(PointerRNA *UNUSED(ptr), PropertyRNA *prop, void *UNUSED(user_data))
{
	const char *prop_id = RNA_property_identifier(prop);

	return !(STREQ(prop_id, "filepath"));
}

static void screenshot_draw(bContext *UNUSED(C), wmOperator *op)
{
	uiLayout *layout = op->layout;
	ScreenshotData *scd = op->customdata;
	PointerRNA ptr;

	/* image template */
	RNA_pointer_create(NULL, &RNA_ImageFormatSettings, &scd->im_format, &ptr);
	uiTemplateImageSettings(layout, &ptr, false);

	/* main draw call */
	RNA_pointer_create(NULL, op->type->srna, op->properties, &ptr);
	uiDefAutoButsRNA(layout, &ptr, screenshot_draw_check_prop, NULL, '\0');
}

static bool screenshot_poll(bContext *C)
{
	if (G.background)
		return false;

	return WM_operator_winactive(C);
}

void SCREEN_OT_screenshot(wmOperatorType *ot)
{
	/* weak: opname starting with 'save' makes filewindow give save-over */
	ot->name = "Save Screenshot";
	ot->idname = "SCREEN_OT_screenshot";
	ot->description = "Capture a picture of the active area or whole Blender window";

	ot->invoke = screenshot_invoke;
	ot->check = screenshot_check;
	ot->exec = screenshot_exec;
	ot->cancel = screenshot_cancel;
	ot->ui = screenshot_draw;
	ot->poll = screenshot_poll;

	ot->flag = 0;

	WM_operator_properties_filesel(
	        ot, FILE_TYPE_FOLDER | FILE_TYPE_IMAGE, FILE_SPECIAL, FILE_SAVE,
	        WM_FILESEL_FILEPATH, FILE_DEFAULTDISPLAY, FILE_SORT_ALPHA);
	RNA_def_boolean(ot->srna, "full", 1, "Full Screen",
	                "Capture the whole window (otherwise only capture the active area)");
}

/* *************************** screencast ************************* */

enum {
	SCREENCAST_QUALITY_LOW = 0,
	SCREENCAST_QUALITY_MEDIUM,
	SCREENCAST_QUALITY_HIGH,
	SCREENCAST_QUALITY_VERY_HIGH,
};

/* x264 constant rate factor per quality (lower is better). */
static int screencast_quality_crf(int quality)
{
	switch (quality) {
		case SCREENCAST_QUALITY_LOW: return 28;
		case SCREENCAST_QUALITY_HIGH: return 18;
		case SCREENCAST_QUALITY_VERY_HIGH: return 14;
		default: return 23;
	}
}

/* In the chosen folder, else next to the saved .blend, else in the user's default folder;
 * time stamped so recordings never overwrite each other. */
static void screencast_default_filepath(char *filepath, size_t maxlen, const char *directory)
{
	char stamp[32], name[FILE_MAXFILE];
	const time_t now = time(NULL);
	strftime(stamp, sizeof(stamp), "%Y%m%d-%H%M%S", localtime(&now));

	if (G.relbase_valid) {
		char blendname[FILE_MAXFILE];
		BLI_strncpy(blendname, BLI_path_basename(BKE_main_blendfile_path_from_global()), sizeof(blendname));
		BLI_path_extension_replace(blendname, sizeof(blendname), "");
		BLI_snprintf(name, sizeof(name), "%s_screencast_%s.mp4", blendname, stamp);
	}
	else {
		BLI_snprintf(name, sizeof(name), "screencast_%s.mp4", stamp);
	}

	if (directory[0]) {
		BLI_strncpy(filepath, directory, maxlen);
		BLI_path_abs(filepath, BKE_main_blendfile_path_from_global());
	}
	else if (G.relbase_valid) {
		BLI_split_dir_part(BKE_main_blendfile_path_from_global(), filepath, maxlen);
	}
	else {
		const char *folder = BKE_appdir_folder_default();
		BLI_strncpy(filepath, folder ? folder : BKE_tempdir_base(), maxlen);
	}
	BLI_path_append(filepath, maxlen, name);
}

/* The recorder in the Info header keeps its settings on the window manager
 * (screencast_* in bl_ui/space_info.py); the shortcut uses them too, unless the
 * caller sets the operator property. */
static void screencast_props_from_wm(bContext *C, wmOperator *op)
{
	static const char *names[][2] = {
		{"fps", "screencast_fps"},
		{"quality", "screencast_quality"},
		{"full", "screencast_full"},
		{"show_cursor", "screencast_show_cursor"},
		{"directory", "screencast_directory"},
	};
	wmWindowManager *wm = CTX_wm_manager(C);
	PointerRNA wm_ptr;

	RNA_id_pointer_create(&wm->id, &wm_ptr);

	for (int i = 0; i < ARRAY_SIZE(names); i++) {
		PropertyRNA *dst = RNA_struct_find_property(op->ptr, names[i][0]);
		PropertyRNA *src = RNA_struct_find_property(&wm_ptr, names[i][1]);

		if (!dst || !src || RNA_property_is_set(op->ptr, dst) || RNA_property_type(src) != RNA_property_type(dst)) {
			continue;
		}
		switch (RNA_property_type(dst)) {
			case PROP_INT:
				RNA_property_int_set(op->ptr, dst, RNA_property_int_get(&wm_ptr, src));
				break;
			case PROP_BOOLEAN:
				RNA_property_boolean_set(op->ptr, dst, RNA_property_boolean_get(&wm_ptr, src));
				break;
			case PROP_ENUM:
			{
				/* by identifier: the Python enum numbers its items on its own */
				const char *id;
				int value;
				if (RNA_property_enum_identifier(C, &wm_ptr, src, RNA_property_enum_get(&wm_ptr, src), &id) &&
				    RNA_property_enum_value(C, op->ptr, dst, id, &value))
				{
					RNA_property_enum_set(op->ptr, dst, value);
				}
				break;
			}
			case PROP_STRING:
			{
				char buf[FILE_MAX];
				RNA_property_string_get(&wm_ptr, src, buf);
				RNA_property_string_set(op->ptr, dst, buf);
				break;
			}
			default:
				break;
		}
	}
}

/* Area recorded when "Full Window" is off: the active 3D View, else the largest one
 * on the screen (the operator usually runs from the Info header or a shortcut). */
static ScrArea *screencast_view3d_area(bContext *C)
{
	ScrArea *sa = CTX_wm_area(C);
	bScreen *sc = CTX_wm_screen(C);
	ScrArea *best = NULL;
	int best_size = 0;

	if (sa && sa->spacetype == SPACE_VIEW3D) {
		return sa;
	}
	if (sc == NULL) {
		return NULL;
	}
	for (sa = sc->areabase.first; sa; sa = sa->next) {
		if (sa->spacetype == SPACE_VIEW3D) {
			const int size = BLI_rcti_size_x(&sa->totrct) * BLI_rcti_size_y(&sa->totrct);
			if (size > best_size) {
				best_size = size;
				best = sa;
			}
		}
	}
	return best;
}

static int screencast_exec(bContext *C, wmOperator *op)
{
	/* Toggle: the same shortcut/menu entry stops the recording. */
	if (WM_screencast_is_running()) {
		WM_screencast_stop(op->reports);
		return OPERATOR_FINISHED;
	}

	wmWindow *win = CTX_wm_window(C);
	ScrArea *sa = screencast_view3d_area(C);
	rcti rect;
	char filepath[FILE_MAX], directory[FILE_MAX];

	screencast_props_from_wm(C, op);

	if (RNA_boolean_get(op->ptr, "full") || sa == NULL) {
		BLI_rcti_init(&rect, 0, WM_window_pixels_x(win) - 1, 0, WM_window_pixels_y(win) - 1);
	}
	else {
		rect = sa->totrct;
	}

	RNA_string_get(op->ptr, "filepath", filepath);
	if (filepath[0] == '\0') {
		RNA_string_get(op->ptr, "directory", directory);
		screencast_default_filepath(filepath, sizeof(filepath), directory);
	}
	else {
		BLI_path_abs(filepath, BKE_main_blendfile_path_from_global());
	}

	if (!WM_screencast_start(C, win, &rect, RNA_int_get(op->ptr, "fps"),
	                         screencast_quality_crf(RNA_enum_get(op->ptr, "quality")),
	                         RNA_boolean_get(op->ptr, "show_cursor"), filepath, op->reports))
	{
		return OPERATOR_CANCELLED;
	}

	BKE_report(op->reports, RPT_INFO, "Recording screen, run again (Ctrl+Alt+F3) to stop");
	return OPERATOR_FINISHED;
}

void SCREEN_OT_screencast(wmOperatorType *ot)
{
	static const EnumPropertyItem quality_items[] = {
		{SCREENCAST_QUALITY_LOW, "LOW", 0, "Low", "Smallest files"},
		{SCREENCAST_QUALITY_MEDIUM, "MEDIUM", 0, "Medium", "Balanced size and quality"},
		{SCREENCAST_QUALITY_HIGH, "HIGH", 0, "High", "Sharp text and UI, larger files"},
		{SCREENCAST_QUALITY_VERY_HIGH, "VERY_HIGH", 0, "Very High", "Nearly lossless, large files"},
		{0, NULL, 0, NULL, NULL}
	};
	PropertyRNA *prop;

	ot->name = "Record Screen";
	ot->idname = "SCREEN_OT_screencast";
	ot->description = "Start or stop recording the window or the 3D View to a video (MP4), "
	                  "including the game running in the editor";

	ot->exec = screencast_exec;
	ot->poll = screenshot_poll;

	ot->flag = 0;

	prop = RNA_def_string_file_path(ot->srna, "filepath", NULL, FILE_MAX, "File Path",
	                                "Video file to write (empty: next to the .blend, time stamped)");
	RNA_def_property_flag(prop, PROP_SKIP_SAVE);
	prop = RNA_def_string_dir_path(ot->srna, "directory", NULL, FILE_MAX, "Folder",
	                               "Folder for the time stamped videos (empty: next to the .blend)");
	RNA_def_property_flag(prop, PROP_SKIP_SAVE);
	/* Not remembered between runs: unset properties come from the Info header recorder settings. */
	prop = RNA_def_int(ot->srna, "fps", 30, 1, 120, "Frame Rate", "Frames per second to capture", 10, 60);
	RNA_def_property_flag(prop, PROP_SKIP_SAVE);
	prop = RNA_def_enum(ot->srna, "quality", quality_items, SCREENCAST_QUALITY_HIGH, "Quality", "Video quality");
	RNA_def_property_flag(prop, PROP_SKIP_SAVE);
	prop = RNA_def_boolean(ot->srna, "full", true, "Full Window",
	                       "Record the whole window (otherwise only the 3D View)");
	RNA_def_property_flag(prop, PROP_SKIP_SAVE);
	prop = RNA_def_boolean(ot->srna, "show_cursor", true, "Show Cursor",
	                       "Draw the mouse cursor in the video, highlighted while a button is held");
	RNA_def_property_flag(prop, PROP_SKIP_SAVE);
}
