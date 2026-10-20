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

#ifndef __SCREENCAST_AUDIO_H__
#define __SCREENCAST_AUDIO_H__

/** \file screencast_audio.h
 *  \ingroup bke
 *
 * Sound of this process (and the processes it starts) for the screen recording, captured on
 * its own thread. Windows only (WASAPI process loopback, Windows 10 2004 or newer); elsewhere
 * begin returns NULL and the video has no sound.
 */

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ScreencastAudio ScreencastAudio;

#define SCREENCAST_AUDIO_RATE 48000
#define SCREENCAST_AUDIO_CHANNELS 2

/* NULL when capture isn't available. Samples are placed on the recording timeline:
 * t = PIL_check_seconds_timer() - start_time. */
ScreencastAudio *screencast_audio_begin(double start_time);
void screencast_audio_end(ScreencastAudio *sa);

/* Same values as the video timeline; captured sound is discarded while paused. */
void screencast_audio_timeline_set(ScreencastAudio *sa, double start_time, bool paused);

/* Interleaved stereo float. False when not enough was captured yet (unless flush, which
 * pads with silence). */
bool screencast_audio_read(ScreencastAudio *sa, float *dst, int samples, int channels, bool flush);

#ifdef __cplusplus
}
#endif

#endif  /* __SCREENCAST_AUDIO_H__ */
