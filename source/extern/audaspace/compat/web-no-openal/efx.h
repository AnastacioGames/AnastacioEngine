/*
 * Cabecalhos minimos para compilar os efeitos EFX do Audaspace (fx/GEEffects) sem OpenAL nativo.
 *
 * O OpenAL do Emscripten nao traz efx.h nem as funcoes EFX. Este diretorio so entra no include
 * quando EMSCRIPTEN e WITH_OPENAL=OFF (dispositivo SDL). As funcoes abaixo sao stubs: nenhum
 * dispositivo SDL cria OpenALEffect, entao nunca sao chamadas em execucao. Os efeitos de reverb
 * e filtros EFX ficam indisponiveis na Web (ver docs/web-audio-analysis.md).
 */
#ifndef AUD_WEB_NO_OPENAL_EFX_H
#define AUD_WEB_NO_OPENAL_EFX_H

#include <AL/al.h>

#define AL_FILTER_NULL 0x0000
#define AL_FILTER_TYPE 0x8001
#define AL_FILTER_LOWPASS 0x0001
#define AL_FILTER_HIGHPASS 0x0002
#define AL_FILTER_BANDPASS 0x0003
#define AL_LOWPASS_GAIN 0x0001
#define AL_LOWPASS_GAINHF 0x0002
#define AL_HIGHPASS_GAIN 0x0001
#define AL_HIGHPASS_GAINLF 0x0002
#define AL_BANDPASS_GAIN 0x0001
#define AL_BANDPASS_GAINLF 0x0002
#define AL_BANDPASS_GAINHF 0x0003

#define AL_EFFECT_NULL 0x0000
#define AL_EFFECT_TYPE 0x8001
#define AL_EFFECT_REVERB 0x0001
#define AL_EFFECTSLOT_EFFECT 0x0001
#define AL_DIRECT_FILTER 0x20005

#define AL_REVERB_DENSITY 0x0001
#define AL_REVERB_DIFFUSION 0x0002
#define AL_REVERB_GAIN 0x0003
#define AL_REVERB_GAINHF 0x0004
#define AL_REVERB_DECAY_TIME 0x0005
#define AL_REVERB_DECAY_HFRATIO 0x0006
#define AL_REVERB_REFLECTIONS_GAIN 0x0007
#define AL_REVERB_REFLECTIONS_DELAY 0x0008
#define AL_REVERB_LATE_REVERB_GAIN 0x0009
#define AL_REVERB_LATE_REVERB_DELAY 0x000A
#define AL_REVERB_AIR_ABSORPTION_GAINHF 0x000B
#define AL_REVERB_ROOM_ROLLOFF_FACTOR 0x000C
#define AL_REVERB_DECAY_HFLIMIT 0x000D

#define AL_REVERB_DEFAULT_DENSITY 1.0f
#define AL_REVERB_DEFAULT_DIFFUSION 1.0f
#define AL_REVERB_DEFAULT_GAIN 0.32f
#define AL_REVERB_DEFAULT_GAINHF 0.89f
#define AL_REVERB_DEFAULT_DECAY_TIME 1.49f
#define AL_REVERB_DEFAULT_DECAY_HFRATIO 0.83f
#define AL_REVERB_DEFAULT_REFLECTIONS_GAIN 0.05f
#define AL_REVERB_DEFAULT_REFLECTIONS_DELAY 0.007f
#define AL_REVERB_DEFAULT_LATE_REVERB_GAIN 1.26f
#define AL_REVERB_DEFAULT_LATE_REVERB_DELAY 0.011f
#define AL_REVERB_DEFAULT_AIR_ABSORPTION_GAINHF 0.994f
#define AL_REVERB_DEFAULT_ROOM_ROLLOFF_FACTOR 0.0f
#define AL_REVERB_DEFAULT_DECAY_HFLIMIT AL_TRUE

static inline void alGenEffects(ALsizei n, ALuint *effects) { for (ALsizei i = 0; i < n; i++) effects[i] = 0; }
static inline void alDeleteEffects(ALsizei, const ALuint *) {}
static inline void alEffecti(ALuint, ALenum, ALint) {}
static inline void alEffectf(ALuint, ALenum, ALfloat) {}
static inline void alGenFilters(ALsizei n, ALuint *filters) { for (ALsizei i = 0; i < n; i++) filters[i] = 0; }
static inline void alDeleteFilters(ALsizei, const ALuint *) {}
static inline void alFilteri(ALuint, ALenum, ALint) {}
static inline void alFilterf(ALuint, ALenum, ALfloat) {}
static inline void alGenAuxiliaryEffectSlots(ALsizei n, ALuint *slots) { for (ALsizei i = 0; i < n; i++) slots[i] = 0; }
static inline void alDeleteAuxiliaryEffectSlots(ALsizei, const ALuint *) {}
static inline void alAuxiliaryEffectSloti(ALuint, ALenum, ALint) {}

#endif
