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

/** \file blender/blenkernel/intern/screencast.c
 *  \ingroup bke
 *
 * Screen recording core (see BKE_screencast.h), used by the editor and the standalone player.
 *
 * Replaces the 2.79 screencast (removed from this code base), which read the front
 * buffer synchronously with glFinish() from a timer and appended every frame from a job:
 *
 * - The caller captures right before each buffer swap, so the recording sees exactly what
 *   is presented. The front buffer is not read: its content is undefined under modern
 *   compositors.
 * - Readback is asynchronous: glReadPixels into a ring of pixel buffer objects, mapped a
 *   couple of frames later (fence when available), so the GPU is never stalled.
 * - Encoding (H.264/MP4 through writeffmpeg, fast preset) runs on its own thread, fed by
 *   a queue and a bounded frame pool: if the encoder falls behind frames are dropped and
 *   counted instead of stalling the caller.
 * - Each frame carries its capture time as pts: a window that doesn't redraw produces no
 *   frames and no encoding work, and the video still plays in real time.
 * - The mouse cursor (drawn by the OS, not in the frame) is composited on the encoder
 *   thread, filled while a mouse button is held.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "MEM_guardedalloc.h"

#include "DNA_scene_types.h"

#include "BLI_blenlib.h"
#include "BLI_math_base.h"
#include "BLI_threads.h"
#include "BLI_timecode.h"
#include "BLI_utildefines.h"

#include "BKE_report.h"
#include "BKE_screencast.h"
#include "BKE_writeavi.h"
#ifdef WITH_FFMPEG
#  include "BKE_writeffmpeg.h"
#endif

#include "PIL_time.h"

#include "screencast_audio.h"

#include "GPU_glew.h"

#define SCREENCAST_PBO_COUNT 3
/* Frames waiting for the encoder; more than this means it can't keep up. */
#define SCREENCAST_POOL_MAX 8

typedef struct ScreencastFrame {
	struct ScreencastFrame *next, *prev;
	unsigned int *pixels;
	int pts;
	ScreencastCursor cursor;
} ScreencastFrame;

typedef struct ScreencastPBO {
	GLuint buffer;
	GLsync fence;
	bool pending;
	ScreencastFrame meta;  /* pts and cursor of the pixels being read back */
} ScreencastPBO;

struct Screencast {
	int w, h;
	int fps;
	bool show_cursor;
	float cursor_radius;

	double start_time;  /* moved forward by the paused time */
	double pause_time;
	bool paused;
	int last_pts;

	bool use_pbo, use_fence;
	ScreencastPBO pbo[SCREENCAST_PBO_COUNT];
	int pbo_head, pbo_tail;

	/* Encoder thread. */
	ListBase threads;
	ThreadQueue *queue;
	ThreadMutex pool_lock;
	ListBase pool;
	int pool_total;
	ScreencastFrame *last_frame;  /* owned by the encoder thread while it runs */
#ifndef WITH_FFMPEG
	int avi_next;  /* AVI has no timestamps: next index, frames repeated to fill gaps */
#endif

	bMovieHandle mh;  /* copy: BKE_movie_handle_get() returns a shared static */
	void *mh_context;
	RenderData rd;
	ReportList encoder_reports;
	bool encoder_failed;

	ScreencastAudio *audio;  /* NULL: video without sound */

	int frames_written, frames_dropped, frames_skipped;
	int frames_captured;   /* readbacks started (RANGE_SCREENCAST_STATS) */
	double encode_time;    /* seconds spent in the encoder thread */
	char filepath[FILE_MAX];
};

/* -------------------------------------------------------------------- */
/** \name Frame pool
 * \{ */

static ScreencastFrame *screencast_frame_acquire(Screencast *sc)
{
	ScreencastFrame *frame;

	BLI_mutex_lock(&sc->pool_lock);
	frame = BLI_pophead(&sc->pool);
	if (frame == NULL && sc->pool_total < SCREENCAST_POOL_MAX) {
		frame = MEM_callocN(sizeof(*frame), __func__);
		frame->pixels = MEM_mallocN(sizeof(unsigned int) * sc->w * sc->h, __func__);
		sc->pool_total++;
	}
	BLI_mutex_unlock(&sc->pool_lock);

	return frame;
}

static void screencast_frame_release(Screencast *sc, ScreencastFrame *frame)
{
	BLI_mutex_lock(&sc->pool_lock);
	BLI_addtail(&sc->pool, frame);
	BLI_mutex_unlock(&sc->pool_lock);
}

static void screencast_pool_free(Screencast *sc)
{
	ScreencastFrame *frame;
	while ((frame = BLI_pophead(&sc->pool))) {
		MEM_freeN(frame->pixels);
		MEM_freeN(frame);
	}
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Encoder thread
 * \{ */

BLI_INLINE void screencast_blend(unsigned char *px, const unsigned char col[3], float alpha)
{
	if (alpha <= 0.0f) {
		return;
	}
	if (alpha > 1.0f) {
		alpha = 1.0f;
	}
	px[0] = (unsigned char)(px[0] + (col[0] - px[0]) * alpha);
	px[1] = (unsigned char)(px[1] + (col[1] - px[1]) * alpha);
	px[2] = (unsigned char)(px[2] + (col[2] - px[2]) * alpha);
}

/* Anti-aliased ring with a dark outline, readable on light and dark UI. */
static void screencast_draw_cursor(const Screencast *sc, ScreencastFrame *frame)
{
	static const unsigned char white[3] = {255, 255, 255};
	static const unsigned char dark[3] = {20, 20, 20};
	static const unsigned char press[3] = {255, 180, 30};
	const ScreencastCursor *cursor = &frame->cursor;
	const float r = sc->cursor_radius;
	const float line = max_ff(1.0f, r * 0.18f);
	const int ext = (int)ceilf(r + line * 2.0f) + 1;
	const int x0 = max_ii(0, cursor->x - ext), x1 = min_ii(sc->w - 1, cursor->x + ext);
	const int y0 = max_ii(0, cursor->y - ext), y1 = min_ii(sc->h - 1, cursor->y + ext);

	for (int y = y0; y <= y1; y++) {
		unsigned char *row = (unsigned char *)(frame->pixels + (size_t)y * sc->w);
		for (int x = x0; x <= x1; x++) {
			unsigned char *px = row + x * 4;
			const float dx = (float)(x - cursor->x), dy = (float)(y - cursor->y);
			const float d = sqrtf(dx * dx + dy * dy);

			if (cursor->pressed) {
				screencast_blend(px, press, 0.5f * (r - d + 0.5f));
			}
			/* outline, then the white ring on top */
			screencast_blend(px, dark, 0.7f * (line * 1.5f + 0.5f - fabsf(d - r)));
			screencast_blend(px, white, line * 0.5f + 0.5f - fabsf(d - r));
			/* hotspot */
			if (!cursor->pressed) {
				screencast_blend(px, dark, 0.7f * (2.0f - d));
				screencast_blend(px, white, 1.2f - d);
			}
		}
	}
}

static void screencast_encode(Screencast *sc, ScreencastFrame *frame)
{
	if (sc->encoder_failed) {
		return;
	}
#ifdef WITH_FFMPEG
	if (!sc->mh.append_movie(sc->mh_context, &sc->rd, 0, frame->pts, (int *)frame->pixels,
	                          sc->w, sc->h, "", &sc->encoder_reports))
	{
		sc->encoder_failed = true;
		return;
	}
	sc->frames_written++;
#else
	/* AVI plays one index entry per tick: repeat the frame up to its timestamp (capped, the
	 * JPEG is encoded again each time) so the index has no holes. */
	if (frame->pts < sc->avi_next) {
		return;
	}
	const int first = max_ii(sc->avi_next, frame->pts - sc->fps * 2);
	for (int i = first; i <= frame->pts; i++) {
		if (!sc->mh.append_movie(sc->mh_context, &sc->rd, 0, sc->avi_next, (int *)frame->pixels,
		                          sc->w, sc->h, "", &sc->encoder_reports))
		{
			sc->encoder_failed = true;
			return;
		}
		sc->avi_next++;
		sc->frames_written++;
	}
	/* Classic AVI uses 32-bit sizes: stop before 2 GB or the file is lost. */
	if (sc->frames_written % (sc->fps * 2) == 0 &&
	    BLI_file_size(sc->filepath) > (size_t)1900 * 1024 * 1024)
	{
		BKE_report(&sc->encoder_reports, RPT_WARNING, "Recording stopped at the 2 GB AVI limit");
		sc->encoder_failed = true;
	}
#endif
}

static void *screencast_thread(void *data)
{
	Screencast *sc = data;
	ScreencastFrame *frame;

	/* Returns NULL once the queue is drained after BLI_thread_queue_nowait(). */
	while ((frame = BLI_thread_queue_pop(sc->queue))) {
		if (sc->show_cursor && frame->cursor.visible) {
			screencast_draw_cursor(sc, frame);
		}
		const double t0 = PIL_check_seconds_timer();
		screencast_encode(sc, frame);
		sc->encode_time += PIL_check_seconds_timer() - t0;

		/* Kept to close the video at the stop time (the last frame may be long). */
		if (sc->last_frame) {
			screencast_frame_release(sc, sc->last_frame);
		}
		sc->last_frame = frame;
	}

	return NULL;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Readback (caller thread, GL context of the recorded window)
 * \{ */

static void screencast_collect_slot(Screencast *sc, ScreencastPBO *slot)
{
	ScreencastFrame *frame = screencast_frame_acquire(sc);

	glBindBuffer(GL_PIXEL_PACK_BUFFER, slot->buffer);
	if (frame) {
		const void *src = glMapBuffer(GL_PIXEL_PACK_BUFFER, GL_READ_ONLY);
		if (src) {
			memcpy(frame->pixels, src, sizeof(unsigned int) * sc->w * sc->h);
			glUnmapBuffer(GL_PIXEL_PACK_BUFFER);

			frame->pts = slot->meta.pts;
			frame->cursor = slot->meta.cursor;
			BLI_thread_queue_push(sc->queue, frame);
		}
		else {
			screencast_frame_release(sc, frame);
			sc->frames_dropped++;
		}
	}
	else {
		sc->frames_dropped++;
	}

	if (slot->fence) {
		glDeleteSync(slot->fence);
		slot->fence = NULL;
	}
	slot->pending = false;
}

static bool screencast_slot_ready(const Screencast *sc, const ScreencastPBO *slot)
{
	if (sc->use_fence && slot->fence) {
		const GLenum status = glClientWaitSync(slot->fence, 0, 0);
		return ELEM(status, GL_ALREADY_SIGNALED, GL_CONDITION_SATISFIED);
	}
	/* No fence: only collect when the ring is full (two frames of latency). */
	return false;
}

/* Hands finished readbacks to the encoder in capture order. Caller binds/restores PBO state. */
static void screencast_collect(Screencast *sc, bool force)
{
	while (sc->pbo[sc->pbo_tail].pending) {
		ScreencastPBO *slot = &sc->pbo[sc->pbo_tail];
		if (!force && !screencast_slot_ready(sc, slot)) {
			break;
		}
		screencast_collect_slot(sc, slot);
		sc->pbo_tail = (sc->pbo_tail + 1) % SCREENCAST_PBO_COUNT;
	}
}

static int screencast_current_pts(const Screencast *sc)
{
	return (int)((PIL_check_seconds_timer() - sc->start_time) * sc->fps);
}

bool BKE_screencast_frame_due(const Screencast *sc)
{
	return !sc->paused && !sc->encoder_failed && screencast_current_pts(sc) > sc->last_pts;
}

void BKE_screencast_frame_skipped(Screencast *sc)
{
	sc->frames_skipped++;
}

void BKE_screencast_capture(Screencast *sc, int x, int y, const ScreencastCursor *cursor)
{
	if (!BKE_screencast_frame_due(sc)) {
		return;
	}

	ScreencastFrame meta = {NULL};
	meta.pts = sc->last_pts = screencast_current_pts(sc);
	if (cursor) {
		meta.cursor = *cursor;
	}

	/* The game leaves its own read framebuffer and pack state bound. */
	GLint prev_read_fbo = 0, prev_read_buffer = GL_BACK, prev_pack_buffer = 0;
	GLint prev_align = 4, prev_row_length = 0, prev_skip_pixels = 0, prev_skip_rows = 0;
	glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &prev_read_fbo);
	glGetIntegerv(GL_PACK_ALIGNMENT, &prev_align);
	glGetIntegerv(GL_PACK_ROW_LENGTH, &prev_row_length);
	glGetIntegerv(GL_PACK_SKIP_PIXELS, &prev_skip_pixels);
	glGetIntegerv(GL_PACK_SKIP_ROWS, &prev_skip_rows);
	if (sc->use_pbo) {
		glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING, &prev_pack_buffer);
	}

	glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
	glGetIntegerv(GL_READ_BUFFER, &prev_read_buffer);
	glReadBuffer(GL_BACK);
	glPixelStorei(GL_PACK_ALIGNMENT, 4);
	glPixelStorei(GL_PACK_ROW_LENGTH, 0);
	glPixelStorei(GL_PACK_SKIP_PIXELS, 0);
	glPixelStorei(GL_PACK_SKIP_ROWS, 0);

	sc->frames_captured++;
	if (sc->use_pbo) {
		screencast_collect(sc, false);

		ScreencastPBO *slot = &sc->pbo[sc->pbo_head];
		if (slot->pending) {
			/* Ring full: the oldest readback has had two frames to finish. */
			screencast_collect(sc, true);
		}

		glBindBuffer(GL_PIXEL_PACK_BUFFER, slot->buffer);
		glReadPixels(x, y, sc->w, sc->h, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
		if (sc->use_fence) {
			slot->fence = glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE, 0);
		}
		slot->meta = meta;
		slot->pending = true;
		sc->pbo_head = (sc->pbo_head + 1) % SCREENCAST_PBO_COUNT;

		glBindBuffer(GL_PIXEL_PACK_BUFFER, prev_pack_buffer);
	}
	else {
		ScreencastFrame *frame = screencast_frame_acquire(sc);
		if (frame) {
			glReadPixels(x, y, sc->w, sc->h, GL_RGBA, GL_UNSIGNED_BYTE, frame->pixels);
			meta.pixels = frame->pixels;
			*frame = meta;
			BLI_thread_queue_push(sc->queue, frame);
		}
		else {
			sc->frames_dropped++;
		}
	}

	glReadBuffer(prev_read_buffer);
	glBindFramebuffer(GL_READ_FRAMEBUFFER, prev_read_fbo);
	glPixelStorei(GL_PACK_ALIGNMENT, prev_align);
	glPixelStorei(GL_PACK_ROW_LENGTH, prev_row_length);
	glPixelStorei(GL_PACK_SKIP_PIXELS, prev_skip_pixels);
	glPixelStorei(GL_PACK_SKIP_ROWS, prev_skip_rows);
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Start/stop and state
 * \{ */

void BKE_screencast_pause_set(Screencast *sc, bool paused)
{
	if (paused == sc->paused) {
		return;
	}
	if (paused) {
		sc->pause_time = PIL_check_seconds_timer();
	}
	else {
		sc->start_time += PIL_check_seconds_timer() - sc->pause_time;
	}
	sc->paused = paused;
	if (sc->audio) {
		screencast_audio_timeline_set(sc->audio, sc->start_time, paused);
	}
}

bool BKE_screencast_is_paused(const Screencast *sc)
{
	return sc->paused;
}

double BKE_screencast_elapsed(const Screencast *sc)
{
	return (sc->paused ? sc->pause_time : PIL_check_seconds_timer()) - sc->start_time;
}

void BKE_screencast_size(const Screencast *sc, int *r_w, int *r_h)
{
	*r_w = sc->w;
	*r_h = sc->h;
}

bool BKE_screencast_show_cursor(const Screencast *sc)
{
	return sc->show_cursor;
}

float BKE_screencast_cursor_radius(const Screencast *sc)
{
	return sc->cursor_radius;
}

const char *BKE_screencast_filepath(const Screencast *sc)
{
	return sc->filepath;
}

#ifdef WITH_FFMPEG
static bool screencast_audio_read_cb(void *data, float *dst, int samples, int channels, bool flush)
{
	return screencast_audio_read(data, dst, samples, channels, flush);
}
#endif

static void screencast_free(Screencast *sc)
{
	if (sc->audio) {
		screencast_audio_end(sc->audio);
	}
	if (sc->mh_context) {
		sc->mh.context_free(sc->mh_context);
	}
	if (sc->queue) {
		BLI_thread_queue_free(sc->queue);
	}
	screencast_pool_free(sc);
	BLI_mutex_end(&sc->pool_lock);
	BKE_reports_clear(&sc->encoder_reports);
	MEM_freeN(sc);
}

Screencast *BKE_screencast_begin(
        int w, int h, int fps, int crf, bool show_cursor, float cursor_radius, bool audio,
        const char *filepath, ReportList *reports)
{
	/* H.264 with 4:2:0 chroma needs even dimensions. */
	/* Round down: rounding up made full-window captures of odd size skip every frame. */
	w &= ~1;
	h &= ~1;
	if (w < 16 || h < 16) {
		BKE_report(reports, RPT_ERROR, "Area too small to record");
		return NULL;
	}

	Screencast *sc = MEM_callocN(sizeof(*sc), __func__);
	sc->w = w;
	sc->h = h;
	sc->fps = CLAMPIS(fps, 1, 120);
	sc->show_cursor = show_cursor;
	sc->cursor_radius = cursor_radius;
	sc->last_pts = -1;
	BLI_strncpy(sc->filepath, filepath, sizeof(sc->filepath));
	BLI_mutex_init(&sc->pool_lock);
	BKE_reports_init(&sc->encoder_reports, RPT_STORE);

	/* Output: H.264/MP4 when built with FFmpeg, AVI JPEG otherwise. */
	BLI_strncpy(sc->rd.pic, filepath, sizeof(sc->rd.pic));
#ifdef WITH_FFMPEG
	if (audio) {
		sc->audio = screencast_audio_begin(PIL_check_seconds_timer());
		if (sc->audio == NULL) {
#ifdef _WIN32
			BKE_report(reports, RPT_WARNING, "Recording without sound: sound capture needs Windows 10 (2004) or newer");
#else
			BKE_report(reports, RPT_WARNING, "Recording without sound: sound capture is only available on Windows");
#endif
		}
	}
	BKE_ffmpeg_screencast_settings(&sc->rd, sc->fps, crf, sc->audio ? SCREENCAST_AUDIO_RATE : 0);
#else
	UNUSED_VARS(crf);
	if (audio) {
		BKE_report(reports, RPT_WARNING, "Recording without sound: this build records AVI video only");
	}
	/* .avi name: otherwise the AVI writer appends a frame range to the .mp4 name. */
	BLI_path_extension_replace(sc->rd.pic, sizeof(sc->rd.pic), ".avi");
	sc->rd.im_format.imtype = R_IMF_IMTYPE_AVIJPEG;
	sc->rd.im_format.quality = 90;
	sc->rd.frs_sec = (short)sc->fps;
	sc->rd.frs_sec_base = 1.0f;
	sc->rd.scemode |= R_EXTENSION;
#endif
	sc->rd.xsch = w;
	sc->rd.ysch = h;
	sc->rd.size = 100;
	sc->rd.sfra = sc->rd.efra = 1;

	/* NULL when the build has no movie writer (e.g. no FFmpeg and no AVI). */
	const bMovieHandle *mh = BKE_movie_handle_get(sc->rd.im_format.imtype);
	if (mh == NULL || mh->start_movie == NULL) {
		BKE_report(reports, RPT_ERROR, "No video writer available for screen recording");
		screencast_free(sc);
		return NULL;
	}
	sc->mh = *mh;
	if (sc->mh.context_create) {
		sc->mh_context = sc->mh.context_create();
	}
#ifdef WITH_FFMPEG
	BKE_ffmpeg_context_realtime_set(sc->mh_context, true);
	if (sc->audio) {
		BKE_ffmpeg_context_audio_source_set(sc->mh_context, screencast_audio_read_cb, sc->audio);
	}
#endif
	/* No scene: sound comes from the live capture, no stamp metadata. */
	if (!sc->mh.start_movie(sc->mh_context, NULL, &sc->rd, w, h, reports, false, "")) {
		BKE_report(reports, RPT_ERROR, "Could not start the screen recording video");
		screencast_free(sc);
		return NULL;
	}
	if (sc->mh.get_movie_path) {
		sc->mh.get_movie_path(sc->filepath, &sc->rd, false, "");
	}

	/* Asynchronous readback: PBOs are core since GL 2.1, fences since 3.2. */
	sc->use_pbo = (GLEW_VERSION_2_1 || GLEW_ARB_pixel_buffer_object);
	sc->use_fence = (GLEW_VERSION_3_2 || GLEW_ARB_sync);
	if (sc->use_pbo) {
		GLint prev_pack_buffer = 0;
		glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING, &prev_pack_buffer);
		for (int i = 0; i < SCREENCAST_PBO_COUNT; i++) {
			glGenBuffers(1, &sc->pbo[i].buffer);
			glBindBuffer(GL_PIXEL_PACK_BUFFER, sc->pbo[i].buffer);
			glBufferData(GL_PIXEL_PACK_BUFFER, sizeof(unsigned int) * w * h, NULL, GL_STREAM_READ);
		}
		glBindBuffer(GL_PIXEL_PACK_BUFFER, prev_pack_buffer);
	}

	sc->queue = BLI_thread_queue_init();
	BLI_threadpool_init(&sc->threads, screencast_thread, 1);
	BLI_threadpool_insert(&sc->threads, sc);

	sc->start_time = PIL_check_seconds_timer();
	if (sc->audio) {
		screencast_audio_timeline_set(sc->audio, sc->start_time, false);
	}
	return sc;
}

void BKE_screencast_end(Screencast *sc, ReportList *reports)
{
	const double duration = BKE_screencast_elapsed(sc);
	const int stop_pts = (int)(duration * sc->fps);

	if (sc->use_pbo) {
		GLint prev_pack_buffer = 0;
		glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING, &prev_pack_buffer);
		screencast_collect(sc, true);
		for (int i = 0; i < SCREENCAST_PBO_COUNT; i++) {
			if (sc->pbo[i].fence) {
				glDeleteSync(sc->pbo[i].fence);
			}
			glDeleteBuffers(1, &sc->pbo[i].buffer);
		}
		glBindBuffer(GL_PIXEL_PACK_BUFFER, prev_pack_buffer);
	}

	/* Let the encoder drain the queue, then join it. */
	BLI_thread_queue_nowait(sc->queue);
	BLI_threadpool_end(&sc->threads);

	/* Hold the last image until the moment recording stopped. */
	if (sc->last_frame) {
		if (stop_pts > sc->last_frame->pts) {
			sc->last_frame->pts = stop_pts;
			screencast_encode(sc, sc->last_frame);
		}
		screencast_frame_release(sc, sc->last_frame);
		sc->last_frame = NULL;
	}
#ifdef WITH_FFMPEG
	if (sc->audio && !sc->encoder_failed) {
		BKE_ffmpeg_audio_flush(sc->mh_context, duration);
	}
#endif
	sc->mh.end_movie(sc->mh_context);

	if (reports) {
		char time_str[32];
		BLI_timecode_string_from_time_simple(time_str, sizeof(time_str), duration);

		if (sc->encoder_failed) {
			Report *report = sc->encoder_reports.list.last;
			BKE_reportf(reports, RPT_ERROR, "Screen recording failed: %s",
			            report ? report->message : "error writing video");
		}
		else if (sc->frames_written == 0) {
			BKE_report(reports, RPT_WARNING, "Screen recording stopped without frames");
		}
		else {
			BKE_reportf(reports, RPT_INFO, "Screen recording saved: %s (%s)", sc->filepath, time_str);
		}
		if (sc->frames_dropped) {
			BKE_reportf(reports, RPT_WARNING, "Screen recording: %d frames dropped, the encoder couldn't keep up "
			            "(lower the frame rate or record a single area)", sc->frames_dropped);
		}
	}
	printf("Screencast: %s, %.1f s, %d frames written, %d dropped, %d skipped (window smaller than recording), %s%s\n",
	       sc->filepath, duration, sc->frames_written, sc->frames_dropped, sc->frames_skipped,
	       sc->audio ? "with sound" : "no sound",
	       sc->encoder_failed ? ", encoder failed" : "");
	/* RANGE_SCREENCAST_STATS=<file>: the same line plus encoder cost, for the standalone player
	 * (its stdout is not visible). */
	const char *stats = getenv("RANGE_SCREENCAST_STATS");
	if (stats && stats[0]) {
		FILE *f = BLI_fopen(stats, "a");
		if (f) {
			fprintf(f, "%s: %.1f s, %d captured, %d written, %d dropped, %d skipped, encode %.1f ms/frame\n",
			        sc->filepath, duration, sc->frames_captured, sc->frames_written, sc->frames_dropped,
			        sc->frames_skipped, sc->frames_written ? sc->encode_time * 1000.0 / sc->frames_written : 0.0);
			fclose(f);
		}
	}

	screencast_free(sc);
}

/** \} */
