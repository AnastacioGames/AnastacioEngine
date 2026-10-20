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

#ifndef __BKE_SCREENCAST_H__
#define __BKE_SCREENCAST_H__

/** \file BKE_screencast.h
 *  \ingroup bke
 *
 * Screen recording core shared by the editor (windowmanager/intern/wm_screencast.c) and the
 * standalone runtime (gameengine/GamePlayer/GPG_Canvas.cpp): asynchronous readback of the
 * default framebuffer and video encoding on its own thread. The caller decides when to
 * capture (right before swapping buffers) and where the cursor is.
 */

#ifdef __cplusplus
extern "C" {
#endif

struct ReportList;

typedef struct Screencast Screencast;

typedef struct ScreencastCursor {
	/* In pixels of the recorded rectangle, origin bottom-left. */
	int x, y;
	bool visible, pressed;
} ScreencastCursor;

/* Needs the GL context of the recorded window to be current. w and h are made even. */
Screencast *BKE_screencast_begin(
        int w, int h, int fps, int crf, bool show_cursor, float cursor_radius,
        const char *filepath, struct ReportList *reports);
/* Reports the result (when reports is not NULL) and frees. Needs the same GL context. */
void BKE_screencast_end(Screencast *sc, struct ReportList *reports);

/* Whether a new frame is due (frame rate limit, not paused, encoder alive). */
bool BKE_screencast_frame_due(const Screencast *sc);
/* Reads the rectangle at x, y (bottom-left, default framebuffer back buffer). */
void BKE_screencast_capture(Screencast *sc, int x, int y, const ScreencastCursor *cursor);
/* The window is smaller than the recording: the last frame stays on screen. */
void BKE_screencast_frame_skipped(Screencast *sc);

/* Paused time is left out of the video (e.g. while the editor waits for the standalone player). */
void BKE_screencast_pause_set(Screencast *sc, bool paused);
bool BKE_screencast_is_paused(const Screencast *sc);

void BKE_screencast_size(const Screencast *sc, int *r_w, int *r_h);
bool BKE_screencast_show_cursor(const Screencast *sc);
float BKE_screencast_cursor_radius(const Screencast *sc);
/* Recorded seconds, without paused time. */
double BKE_screencast_elapsed(const Screencast *sc);
const char *BKE_screencast_filepath(const Screencast *sc);

#ifdef __cplusplus
}
#endif

#endif  /* __BKE_SCREENCAST_H__ */
