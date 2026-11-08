/*******************************************************************************
 * Anastacio Engine: API C do microfone e dos efeitos de voz.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ******************************************************************************/

#pragma once

#include "AUD_Types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Opaco: ponteiro para std::shared_ptr<aud::Microphone> (o mesmo que
 * Microphone_fromSharedPointer do Python aceita). */
typedef void AUD_Microphone;

/* Iguais a aud::MicrophoneState. */
enum
{
	AUD_MICROPHONE_CLOSED = 0,
	AUD_MICROPHONE_PENDING,
	AUD_MICROPHONE_GRANTED,
	AUD_MICROPHONE_DENIED,
	AUD_MICROPHONE_ERROR
};

/* device/backend NULL ou "" = padrao. O erro de abertura aparece em
 * getState()/getError() depois de start(). */
extern AUD_API AUD_Microphone* AUD_Microphone_create(const char* device, int rate, int channels, const char* backend, float seconds);
extern AUD_API void AUD_Microphone_free(AUD_Microphone* microphone);
extern AUD_API int AUD_Microphone_start(AUD_Microphone* microphone);
extern AUD_API void AUD_Microphone_stop(AUD_Microphone* microphone);
extern AUD_API void AUD_Microphone_poll(AUD_Microphone* microphone);
extern AUD_API int AUD_Microphone_isActive(AUD_Microphone* microphone);
extern AUD_API int AUD_Microphone_getState(AUD_Microphone* microphone);
/* Copia a mensagem de erro (vazia se nao houver). */
extern AUD_API void AUD_Microphone_getError(AUD_Microphone* microphone, char* buffer, int size);
extern AUD_API float AUD_Microphone_getLevel(AUD_Microphone* microphone);
extern AUD_API float AUD_Microphone_getPeak(AUD_Microphone* microphone);
extern AUD_API int AUD_Microphone_getDropped(AUD_Microphone* microphone);
extern AUD_API int AUD_Microphone_getRate(AUD_Microphone* microphone);
extern AUD_API void AUD_Microphone_recordStart(AUD_Microphone* microphone);
/* Novo AUD_Sound (liberar com AUD_Sound_free) ou NULL se nao gravava. */
extern AUD_API AUD_Sound* AUD_Microphone_recordStop(AUD_Microphone* microphone);
extern AUD_API int AUD_Microphone_isRecording(AUD_Microphone* microphone);
extern AUD_API float AUD_Microphone_getRecordingSeconds(AUD_Microphone* microphone);
/* Novo AUD_Sound ao vivo (le da fila e completa com silencio). */
extern AUD_API AUD_Sound* AUD_Microphone_live(AUD_Microphone* microphone);

/* Efeitos de voz (aud::VoiceFX). Novos AUD_Sound ou NULL em erro. */
extern AUD_API AUD_Sound* AUD_Sound_voiceFx(AUD_Sound* sound, const char* preset, float amount);
extern AUD_API int AUD_Sound_voiceFxNeedsRecorded(const char* preset);
extern AUD_API int AUD_Sound_voiceFxIsPreset(const char* preset);
extern AUD_API AUD_Sound* AUD_Sound_edit(AUD_Sound* sound, float start, float end, float fade_in, float fade_out, int normalize);
extern AUD_API float AUD_Sound_peak(AUD_Sound* sound);
extern AUD_API float AUD_Sound_duration(AUD_Sound* sound);
/* WAV PCM 16 bits com o writer proprio (funciona na Web). 1 = ok. */
extern AUD_API int AUD_Sound_saveWAV(AUD_Sound* sound, const char* path, float max_seconds);

#ifdef __cplusplus
}
#endif
