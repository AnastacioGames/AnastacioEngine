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

/** \file blender/blenkernel/intern/screencast_audio.cc
 *  \ingroup bke
 *
 * Sound capture for the screen recording. On Windows the process loopback of WASAPI gives the
 * mix of what this process tree plays, whatever the audio device (OpenAL, SDL...), without the
 * sound of other programs.
 */

#include <string.h>

#include "screencast_audio.h"

#ifdef _WIN32

/* The process loopback API is declared for Windows 10 2004 (NTDDI_WIN10_FE) and newer; on
 * older systems it fails at run time and the recording goes without sound. */
#undef _WIN32_WINNT
#undef NTDDI_VERSION
#define _WIN32_WINNT 0x0A00
#define NTDDI_VERSION 0x0A00000C

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <initguid.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <audioclientactivationparams.h>
#include <mmreg.h>
#include <stdio.h>
#include <math.h>

#include "MEM_guardedalloc.h"
#include "PIL_time.h"

#pragma comment(lib, "mmdevapi.lib")

#define RATE SCREENCAST_AUDIO_RATE
#define CHANNELS SCREENCAST_AUDIO_CHANNELS
/* Ring capacity: the encoder never lags this much behind the capture. */
#define RING_SECONDS 20
/* Sound reaches the loopback a few ms after it is played; the encoder waits this long
 * for it before writing silence. */
#define LATENCY_SECONDS 0.3
/* Gaps longer than this between packets are filled with silence. */
#define GAP_SECONDS 0.04

struct ScreencastAudio {
	CRITICAL_SECTION lock;
	float *ring;
	long long capacity;  /* frames */
	long long written;   /* frames placed on the timeline (silence included) */
	long long read;      /* frames handed to the encoder */
	double start_time;
	bool paused;
	int dropped;

	HANDLE thread;
	HANDLE stop_event;
	HANDLE ready_event;
	bool ok;
	int bytes_per_sample;  /* 4: float, 2: 16 bit */
};

/* -------------------------------------------------------------------- */
/** \name Ring (lock held)
 * \{ */

static void ring_put(ScreencastAudio *sa, const float *src, long long frames)
{
	if (sa->written + frames - sa->read > sa->capacity) {
		sa->dropped += (int)frames;
		return;
	}
	for (long long i = 0; i < frames; i++) {
		float *dst = sa->ring + ((sa->written + i) % sa->capacity) * CHANNELS;
		if (src) {
			dst[0] = src[i * CHANNELS];
			dst[1] = src[i * CHANNELS + 1];
		}
		else {
			dst[0] = dst[1] = 0.0f;
		}
	}
	sa->written += frames;
}

/* Silence up to frame `until` (on the timeline). */
static void ring_pad(ScreencastAudio *sa, long long until)
{
	if (until > sa->written) {
		ring_put(sa, NULL, until - sa->written);
		if (until > sa->written) {
			/* Ring full: keep the timeline anyway. */
			sa->written = until;
			if (sa->read < sa->written - sa->capacity) {
				sa->read = sa->written - sa->capacity;
			}
		}
	}
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Capture thread
 * \{ */

class ActivateHandler : public IActivateAudioInterfaceCompletionHandler, public IAgileObject {
public:
	HANDLE done;
	HRESULT hr = E_FAIL;
	IAudioClient *client = nullptr;
	LONG refs = 1;

	ActivateHandler() { done = CreateEventW(nullptr, TRUE, FALSE, nullptr); }
	virtual ~ActivateHandler() { CloseHandle(done); }

	STDMETHODIMP QueryInterface(REFIID riid, void **ppv) override
	{
		if (riid == __uuidof(IUnknown) || riid == __uuidof(IActivateAudioInterfaceCompletionHandler)) {
			*ppv = static_cast<IActivateAudioInterfaceCompletionHandler *>(this);
		}
		else if (riid == __uuidof(IAgileObject)) {
			*ppv = static_cast<IAgileObject *>(this);
		}
		else {
			*ppv = nullptr;
			return E_NOINTERFACE;
		}
		AddRef();
		return S_OK;
	}
	STDMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&refs); }
	STDMETHODIMP_(ULONG) Release() override
	{
		const LONG r = InterlockedDecrement(&refs);
		if (r == 0) {
			delete this;
		}
		return r;
	}
	STDMETHODIMP ActivateCompleted(IActivateAudioInterfaceAsyncOperation *op) override
	{
		HRESULT hr_activate = E_FAIL;
		IUnknown *unk = nullptr;
		hr = op->GetActivateResult(&hr_activate, &unk);
		if (SUCCEEDED(hr)) {
			hr = hr_activate;
		}
		if (SUCCEEDED(hr) && unk) {
			hr = unk->QueryInterface(__uuidof(IAudioClient), (void **)&client);
		}
		if (unk) {
			unk->Release();
		}
		SetEvent(done);
		return S_OK;
	}
};

static IAudioClient *activate_process_loopback(void)
{
	AUDIOCLIENT_ACTIVATION_PARAMS params = {};
	params.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK;
	params.ProcessLoopbackParams.TargetProcessId = GetCurrentProcessId();
	params.ProcessLoopbackParams.ProcessLoopbackMode = PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE;

	PROPVARIANT pv = {};
	pv.vt = VT_BLOB;
	pv.blob.cbSize = sizeof(params);
	pv.blob.pBlobData = (BYTE *)&params;

	ActivateHandler *handler = new ActivateHandler();
	IActivateAudioInterfaceAsyncOperation *op = nullptr;
	IAudioClient *client = nullptr;

	/* Missing before Windows 10 2004: fails here or in the result. */
	if (SUCCEEDED(ActivateAudioInterfaceAsync(VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK, __uuidof(IAudioClient),
	                                          &pv, handler, &op)))
	{
		if (WaitForSingleObject(handler->done, 3000) == WAIT_OBJECT_0 && SUCCEEDED(handler->hr)) {
			client = handler->client;
			handler->client = nullptr;
		}
		op->Release();
	}
	if (handler->client) {
		handler->client->Release();
		handler->client = nullptr;
	}
	handler->Release();
	return client;
}

static bool init_client(IAudioClient *client, HANDLE event, int *r_bytes_per_sample)
{
	/* The process loopback has no mix format to ask for: it converts to the one given. */
	const WORD tags[2] = {WAVE_FORMAT_IEEE_FLOAT, WAVE_FORMAT_PCM};
	const WORD bits[2] = {32, 16};
	for (int i = 0; i < 2; i++) {
		WAVEFORMATEX wfx = {};
		wfx.wFormatTag = tags[i];
		wfx.nChannels = CHANNELS;
		wfx.nSamplesPerSec = RATE;
		wfx.wBitsPerSample = bits[i];
		wfx.nBlockAlign = wfx.nChannels * wfx.wBitsPerSample / 8;
		wfx.nAvgBytesPerSec = wfx.nSamplesPerSec * wfx.nBlockAlign;

		const HRESULT hr = client->Initialize(
		        AUDCLNT_SHAREMODE_SHARED,
		        AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK |
		        AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM | AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY,
		        2000000 /* 200 ms in 100 ns units */, 0, &wfx, nullptr);
		if (SUCCEEDED(hr)) {
			*r_bytes_per_sample = bits[i] / 8;
			return SUCCEEDED(client->SetEventHandle(event));
		}
	}
	return false;
}

/* Puts a packet that started playing at time t (seconds, PIL timer clock). */
static void place_packet(ScreencastAudio *sa, const float *frames, long long count, double t)
{
	EnterCriticalSection(&sa->lock);
	if (!sa->paused) {
		long long pos = llround((t - sa->start_time) * RATE);
		const long long gap = (long long)(GAP_SECONDS * RATE);

		if (pos < 0) {
			/* Started before the recording. */
			const long long skip = (-pos < count) ? -pos : count;
			frames += skip * CHANNELS;
			count -= skip;
			pos = 0;
		}
		if (pos > sa->written + gap) {
			ring_pad(sa, pos);
		}
		else if (pos + count < sa->written - 4 * gap) {
			/* Late beyond what the encoder may already have taken as silence. */
			count = 0;
		}
		if (count > 0) {
			ring_put(sa, frames, count);
		}
	}
	LeaveCriticalSection(&sa->lock);
}

static DWORD WINAPI capture_thread(LPVOID data)
{
	ScreencastAudio *sa = (ScreencastAudio *)data;
	const bool com = SUCCEEDED(CoInitializeEx(nullptr, COINIT_MULTITHREADED));
	HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
	IAudioClient *client = activate_process_loopback();
	IAudioCaptureClient *capture = nullptr;
	float *convert = nullptr;
	UINT32 convert_frames = 0;

	if (client && init_client(client, event, &sa->bytes_per_sample) &&
	    SUCCEEDED(client->GetService(__uuidof(IAudioCaptureClient), (void **)&capture)) &&
	    SUCCEEDED(client->Start()))
	{
		sa->ok = true;
	}
	SetEvent(sa->ready_event);

	if (sa->ok) {
		HANDLE waits[2] = {sa->stop_event, event};
		LARGE_INTEGER freq;
		QueryPerformanceFrequency(&freq);

		while (WaitForMultipleObjects(2, waits, FALSE, 100) != WAIT_OBJECT_0) {
			UINT32 packet = 0;
			while (SUCCEEDED(capture->GetNextPacketSize(&packet)) && packet > 0) {
				BYTE *bytes = nullptr;
				UINT32 frames = 0;
				DWORD flags = 0;
				UINT64 qpc = 0;
				if (FAILED(capture->GetBuffer(&bytes, &frames, &flags, nullptr, &qpc))) {
					break;
				}

				/* qpc is the performance counter in 100 ns units, the clock of PIL_check_seconds_timer(). */
				double t;
				if (qpc != 0 && !(flags & AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR)) {
					t = (double)qpc * 1e-7;
				}
				else {
					t = PIL_check_seconds_timer() - (double)frames / RATE;
				}

				const float *src = nullptr;
				if (!(flags & AUDCLNT_BUFFERFLAGS_SILENT) && sa->bytes_per_sample == 4) {
					src = (const float *)bytes;
				}
				else {
					if (frames > convert_frames) {
						MEM_SAFE_FREE(convert);
						convert = (float *)MEM_mallocN(sizeof(float) * frames * CHANNELS, __func__);
						convert_frames = frames;
					}
					if (flags & AUDCLNT_BUFFERFLAGS_SILENT) {
						memset(convert, 0, sizeof(float) * frames * CHANNELS);
					}
					else {
						const short *s16 = (const short *)bytes;
						for (UINT32 i = 0; i < frames * CHANNELS; i++) {
							convert[i] = s16[i] / 32768.0f;
						}
					}
					src = convert;
				}

				place_packet(sa, src, frames, t);
				capture->ReleaseBuffer(frames);
			}
		}
		client->Stop();
	}

	MEM_SAFE_FREE(convert);
	if (capture) {
		capture->Release();
	}
	if (client) {
		client->Release();
	}
	CloseHandle(event);
	if (com) {
		CoUninitialize();
	}
	return 0;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name API
 * \{ */

ScreencastAudio *screencast_audio_begin(double start_time)
{
	ScreencastAudio *sa = (ScreencastAudio *)MEM_callocN(sizeof(*sa), __func__);
	InitializeCriticalSection(&sa->lock);
	sa->capacity = (long long)RING_SECONDS * RATE;
	sa->ring = (float *)MEM_mallocN(sizeof(float) * sa->capacity * CHANNELS, __func__);
	sa->start_time = start_time;
	sa->stop_event = CreateEventW(nullptr, TRUE, FALSE, nullptr);
	sa->ready_event = CreateEventW(nullptr, TRUE, FALSE, nullptr);
	sa->thread = CreateThread(nullptr, 0, capture_thread, sa, 0, nullptr);

	if (sa->thread) {
		WaitForSingleObject(sa->ready_event, 5000);
	}
	if (!sa->ok) {
		printf("Screencast: sound capture unavailable (needs Windows 10 2004 or newer), recording without sound\n");
		screencast_audio_end(sa);
		return nullptr;
	}
	return sa;
}

void screencast_audio_end(ScreencastAudio *sa)
{
	if (sa->thread) {
		SetEvent(sa->stop_event);
		WaitForSingleObject(sa->thread, INFINITE);
		CloseHandle(sa->thread);
	}
	if (sa->dropped) {
		printf("Screencast: %d sound frames dropped\n", sa->dropped);
	}
	CloseHandle(sa->stop_event);
	CloseHandle(sa->ready_event);
	DeleteCriticalSection(&sa->lock);
	MEM_freeN(sa->ring);
	MEM_freeN(sa);
}

void screencast_audio_timeline_set(ScreencastAudio *sa, double start_time, bool paused)
{
	EnterCriticalSection(&sa->lock);
	sa->start_time = start_time;
	sa->paused = paused;
	LeaveCriticalSection(&sa->lock);
}

bool screencast_audio_read(ScreencastAudio *sa, float *dst, int samples, int channels, bool flush)
{
	EnterCriticalSection(&sa->lock);

	/* Nothing arrives while the process is quiet: past the latency that is silence. */
	if (!sa->paused) {
		const long long now = llround((PIL_check_seconds_timer() - sa->start_time - LATENCY_SECONDS) * RATE);
		ring_pad(sa, now);
	}

	const long long available = sa->written - sa->read;
	if (available < samples && !flush) {
		LeaveCriticalSection(&sa->lock);
		return false;
	}

	for (int i = 0; i < samples; i++) {
		float l = 0.0f, r = 0.0f;
		if (i < available) {
			const float *src = sa->ring + ((sa->read + i) % sa->capacity) * CHANNELS;
			l = src[0];
			r = src[1];
		}
		if (channels == 1) {
			dst[i] = 0.5f * (l + r);
		}
		else {
			dst[i * channels] = l;
			dst[i * channels + 1] = r;
			for (int c = 2; c < channels; c++) {
				dst[i * channels + c] = 0.0f;
			}
		}
	}
	sa->read += samples;
	if (sa->read > sa->written) {
		sa->written = sa->read;
	}

	LeaveCriticalSection(&sa->lock);
	return true;
}

/** \} */

#else  /* _WIN32 */

ScreencastAudio *screencast_audio_begin(double UNUSED_start_time)
{
	(void)UNUSED_start_time;
	return NULL;
}

void screencast_audio_end(ScreencastAudio *UNUSED_sa)
{
	(void)UNUSED_sa;
}

void screencast_audio_timeline_set(ScreencastAudio *sa, double start_time, bool paused)
{
	(void)sa;
	(void)start_time;
	(void)paused;
}

bool screencast_audio_read(ScreencastAudio *sa, float *dst, int samples, int channels, bool flush)
{
	(void)sa;
	(void)flush;
	memset(dst, 0, sizeof(float) * samples * channels);
	return true;
}

#endif  /* _WIN32 */
