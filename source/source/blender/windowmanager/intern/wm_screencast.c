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

/** \file blender/windowmanager/intern/wm_screencast.c
 *  \ingroup wm
 *
 * Screen recording (screencast) of one window to a video file: picks the window and the
 * rectangle, follows the window across file loads and adds the cursor. Readback and
 * encoding are in blenkernel/intern/screencast.c, shared with the standalone player.
 */

#include <string.h>

#include "MEM_guardedalloc.h"

#include "DNA_userdef_types.h"
#include "DNA_windowmanager_types.h"

#include "BLI_blenlib.h"
#include "BLI_math_base.h"
#include "BLI_utildefines.h"

#include "BKE_context.h"
#include "BKE_global.h"
#include "BKE_main.h"
#include "BKE_report.h"
#include "BKE_screencast.h"

#include "GHOST_C-api.h"

#include "WM_api.h"
#include "WM_types.h"
#include "wm_window.h"

typedef struct WindowScreencast {
	/* The ghost window survives file loads, which replace the wmWindow struct. */
	GHOST_WindowHandle ghostwin;
	wmWindow *win;
	wmTimer *timer;

	/* Captured rectangle; anchored to the window's top-left like the editor layout. */
	int x, top;

	Screencast *core;
} WindowScreencast;

static WindowScreencast *g_screencast = NULL;
/* Current or last recording of this session (for "open folder"/"play"). */
static char g_last_filepath[FILE_MAX] = "";

void wm_screencast_capture(wmWindow *win)
{
	WindowScreencast *ws = g_screencast;

	if (ws == NULL || win->ghostwin != ws->ghostwin) {
		return;
	}

	if (win != ws->win) {
		/* A file load replaced the window struct (and the window manager with its timers). */
		ws->win = win;
		ws->timer = (G_MAIN && G_MAIN->wm.first) ?
		            WM_event_add_timer_notifier(G_MAIN->wm.first, win, NC_WM | ND_JOB, 1.0) : NULL;
	}

	if (!BKE_screencast_frame_due(ws->core)) {
		return;
	}

	int w, h;
	BKE_screencast_size(ws->core, &w, &h);
	const int y = WM_window_pixels_y(win) - ws->top - h;
	if (ws->x + w > WM_window_pixels_x(win) || y < 0) {
		/* Window got smaller than the recording: keep the last frame on screen. */
		BKE_screencast_frame_skipped(ws->core);
		return;
	}

	ScreencastCursor cursor = {0};
	if (BKE_screencast_show_cursor(ws->core) && GHOST_GetCursorVisibility(win->ghostwin)) {
		const float margin = BKE_screencast_cursor_radius(ws->core) * 2.0f;
		int mx, my;
		wm_get_cursor_position(win, &mx, &my);
		cursor.x = mx - ws->x;
		cursor.y = my - y;
		cursor.visible = (cursor.x > -margin && cursor.x < w + margin &&
		                  cursor.y > -margin && cursor.y < h + margin);
		cursor.pressed = wm_cursor_button_pressed();
	}

	BKE_screencast_capture(ws->core, ws->x, y, &cursor);
}

bool WM_screencast_is_running(void)
{
	return g_screencast != NULL;
}

const char *WM_screencast_filepath(void)
{
	return g_last_filepath;
}

double WM_screencast_elapsed(void)
{
	return g_screencast ? BKE_screencast_elapsed(g_screencast->core) : 0.0;
}

bool WM_screencast_is_paused(void)
{
	return g_screencast && BKE_screencast_is_paused(g_screencast->core);
}

void WM_screencast_pause_set(bool paused)
{
	if (g_screencast) {
		BKE_screencast_pause_set(g_screencast->core, paused);
		WM_main_add_notifier(NC_WM | ND_JOB, NULL);
	}
}

/* GL calls outside of drawing need the recorded window's context; the window manager is
 * told so it re-activates its own drawable afterwards. */
static void screencast_activate_context(GHOST_WindowHandle ghostwin)
{
	wmWindowManager *wm = G_MAIN ? G_MAIN->wm.first : NULL;
	GHOST_ActivateWindowDrawingContext(ghostwin);
	if (wm) {
		wm->windrawable = NULL;
	}
}

bool WM_screencast_start(
        bContext *C, wmWindow *win, const rcti *rect, int fps, int crf, bool show_cursor,
        const char *filepath, ReportList *reports)
{
	if (g_screencast) {
		BKE_report(reports, RPT_ERROR, "Screen recording already running");
		return false;
	}

	screencast_activate_context(win->ghostwin);
	Screencast *core = BKE_screencast_begin(
	        BLI_rcti_size_x(rect) + 1, BLI_rcti_size_y(rect) + 1, fps, crf, show_cursor,
	        10.0f * max_ff(U.pixelsize, 1.0f), filepath, reports);
	if (core == NULL) {
		return false;
	}

	int w, h;
	BKE_screencast_size(core, &w, &h);

	WindowScreencast *ws = MEM_callocN(sizeof(*ws), __func__);
	ws->ghostwin = win->ghostwin;
	ws->win = win;
	ws->x = rect->xmin;
	ws->top = WM_window_pixels_y(win) - (rect->ymin + h);
	ws->core = core;
	/* Keeps the "Recording" timer in the Info header ticking. */
	ws->timer = WM_event_add_timer_notifier(CTX_wm_manager(C), win, NC_WM | ND_JOB, 1.0);

	g_screencast = ws;
	BLI_strncpy(g_last_filepath, BKE_screencast_filepath(core), sizeof(g_last_filepath));

	WM_main_add_notifier(NC_WM | ND_JOB, NULL);
	WM_event_add_mousemove(C);  /* redraw now, so the recording starts with a frame */
	return true;
}

bool WM_screencast_stop(ReportList *reports)
{
	WindowScreencast *ws = g_screencast;
	wmWindowManager *wm = G_MAIN ? G_MAIN->wm.first : NULL;

	if (ws == NULL) {
		return false;
	}
	g_screencast = NULL;

	if (wm && ws->timer && BLI_findindex(&wm->timers, ws->timer) != -1) {
		WM_event_remove_timer(wm, NULL, ws->timer);
	}

	screencast_activate_context(ws->ghostwin);
	BKE_screencast_end(ws->core, reports);
	MEM_freeN(ws);

	WM_main_add_notifier(NC_WM | ND_JOB, NULL);
	return true;
}

void wm_screencast_window_destroyed(wmWindow *win)
{
	if (g_screencast && win->ghostwin && win->ghostwin == g_screencast->ghostwin) {
		WM_screencast_stop(NULL);
	}
}
