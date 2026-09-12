/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This file is part of AudaSpace.
 *
 * Audaspace is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * AudaSpace is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Audaspace; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file audaspace/OpenAL/OpenALReverbEffect.cpp
 *  \ingroup audopenal
 */

#include "../include/fx/GEEffects/OpenALReverbEffect.h"

#define AL_ALEXT_PROTOTYPES
#include <al.h>
#include <alc.h>
#include <efx.h>

OpenALReverbEffect::OpenALReverbEffect()
{
	m_slot = 0;
	m_effect_id = 0;

	m_density = AL_REVERB_DEFAULT_DENSITY;
	m_diffusion = AL_REVERB_DEFAULT_DIFFUSION;
	m_gain = AL_REVERB_DEFAULT_GAIN;
	m_gain_hf = AL_REVERB_DEFAULT_GAINHF;
	m_decay_time = AL_REVERB_DEFAULT_DECAY_TIME;
	m_decay_hf_ratio = AL_REVERB_DEFAULT_DECAY_HFRATIO;
	m_reflections_gain = AL_REVERB_DEFAULT_REFLECTIONS_GAIN;
	m_reflections_delay = AL_REVERB_DEFAULT_REFLECTIONS_DELAY;
	m_late_reverb_delay = AL_REVERB_DEFAULT_LATE_REVERB_DELAY;
	m_late_reverb_gain = AL_REVERB_DEFAULT_LATE_REVERB_GAIN;
	m_air_absorption_gain_hf = AL_REVERB_DEFAULT_AIR_ABSORPTION_GAINHF;
	m_room_rolloff_factor = AL_REVERB_DEFAULT_ROOM_ROLLOFF_FACTOR;
	m_decay_limit_hf = AL_REVERB_DEFAULT_DECAY_HFLIMIT;
}

void OpenALReverbEffect::setOpenALParameters(ALuint slot, ALuint effect_id)
{
	m_slot = slot;
	m_effect_id = effect_id;
}

void OpenALReverbEffect::applyParams(ALuint effect)
{
	alEffecti(effect, AL_EFFECT_TYPE, AL_EFFECT_REVERB);

	alEffectf(effect, AL_REVERB_DENSITY, m_density);
	alEffectf(effect, AL_REVERB_DIFFUSION, m_diffusion);
	alEffectf(effect, AL_REVERB_GAIN, m_gain);
	alEffectf(effect, AL_REVERB_GAINHF, m_gain_hf);
	alEffectf(effect, AL_REVERB_DECAY_TIME, m_decay_time);
	alEffectf(effect, AL_REVERB_DECAY_HFRATIO, m_decay_hf_ratio);
	alEffectf(effect, AL_REVERB_REFLECTIONS_GAIN, m_reflections_gain);
	alEffectf(effect, AL_REVERB_REFLECTIONS_DELAY, m_reflections_delay);
	alEffectf(effect, AL_REVERB_LATE_REVERB_GAIN, m_late_reverb_gain);
	alEffectf(effect, AL_REVERB_LATE_REVERB_DELAY, m_late_reverb_delay);
	alEffectf(effect, AL_REVERB_AIR_ABSORPTION_GAINHF, m_air_absorption_gain_hf);
	alEffectf(effect, AL_REVERB_ROOM_ROLLOFF_FACTOR, m_room_rolloff_factor);
	alEffecti(effect, AL_REVERB_DECAY_HFLIMIT, m_decay_limit_hf);
}

void OpenALReverbEffect::applyParameter(ALenum param, float value)
{
	switch (param) {
		case AL_REVERB_DENSITY:
		case AL_REVERB_DIFFUSION:
		case AL_REVERB_GAIN:
		case AL_REVERB_GAINHF:
		case AL_REVERB_DECAY_TIME:
		case AL_REVERB_DECAY_HFRATIO:
		case AL_REVERB_REFLECTIONS_GAIN:
		case AL_REVERB_REFLECTIONS_DELAY:
		case AL_REVERB_LATE_REVERB_GAIN:
		case AL_REVERB_LATE_REVERB_DELAY:
		case AL_REVERB_AIR_ABSORPTION_GAINHF:
		case AL_REVERB_ROOM_ROLLOFF_FACTOR:
			alEffectf(m_effect_id, param, value);
			break;
		case AL_REVERB_DECAY_HFLIMIT:
			alEffecti(m_effect_id, AL_REVERB_DECAY_HFLIMIT, (ALint)value);
			break;
		default:
			break;
	}
	
	alAuxiliaryEffectSloti(m_slot, AL_EFFECTSLOT_EFFECT, m_effect_id);
}

float OpenALReverbEffect::getDensity() const
{
	return m_density;
}

void OpenALReverbEffect::setDensity(float density)
{
	if (m_density == density)
		return;

	m_density = density;
	this->applyParameter(AL_REVERB_DENSITY, m_density);
}

float OpenALReverbEffect::getDiffusion() const
{
	return m_diffusion;
}

void OpenALReverbEffect::setDiffusion(float diffusion)
{
	if (m_diffusion == diffusion)
		return;

	m_diffusion = diffusion;
	this->applyParameter(AL_REVERB_DIFFUSION, m_diffusion);
}

float OpenALReverbEffect::getGain() const
{
	return m_gain;
}

void OpenALReverbEffect::setGain(float gain)
{
	if (m_gain == gain)
		return;

	m_gain = gain;
	this->applyParameter(AL_REVERB_GAIN, m_gain);
}

float OpenALReverbEffect::getGainHF() const
{
	return m_gain_hf;
}

void OpenALReverbEffect::setGainHF(float gain_hf)
{
	if (m_gain_hf == gain_hf)
		return;

	m_gain_hf = gain_hf;
	this->applyParameter(AL_REVERB_GAINHF, m_gain_hf);
}

float OpenALReverbEffect::getDecayTime() const
{
	return m_decay_time;
}

void OpenALReverbEffect::setDecayTime(float decayTime)
{
	if (m_decay_time == decayTime)
		return;

	m_decay_time = decayTime;
	this->applyParameter(AL_REVERB_DECAY_TIME, m_decay_time);
}

float OpenALReverbEffect::getDecayHFRatio() const
{
	return m_decay_hf_ratio;
}

void OpenALReverbEffect::setDecayHFRatio(float decay_hf_ratio)
{
	if (m_decay_hf_ratio == decay_hf_ratio)
		return;

	m_decay_hf_ratio = decay_hf_ratio;
	this->applyParameter(AL_REVERB_DECAY_HFRATIO, m_decay_hf_ratio);
}

float OpenALReverbEffect::getReflectionsGain() const
{
	return m_reflections_gain;
}

void OpenALReverbEffect::setReflectionsGain(float reflections_gain)
{
	if (m_reflections_gain == reflections_gain)
		return;

	m_reflections_gain = reflections_gain;
	this->applyParameter(AL_REVERB_REFLECTIONS_GAIN, m_reflections_gain);
}

float OpenALReverbEffect::getReflectionsDelay() const
{
	return m_reflections_delay;
}

void OpenALReverbEffect::setReflectionsDelay(float reflections_delay)
{
	if (m_reflections_delay == reflections_delay)
		return;

	m_reflections_delay = reflections_delay;
	this->applyParameter(AL_REVERB_REFLECTIONS_DELAY, m_reflections_delay);
}

float OpenALReverbEffect::getLateReverbGain() const
{
	return m_late_reverb_gain;
}

void OpenALReverbEffect::setLateReverbGain(float late_reverb_gain)
{
	if (m_late_reverb_gain == late_reverb_gain)
		return;

	m_late_reverb_gain = late_reverb_gain;
	this->applyParameter(AL_REVERB_LATE_REVERB_GAIN, m_late_reverb_gain);
}

float OpenALReverbEffect::getLateReverbDelay() const
{
	return m_late_reverb_delay;
}

void OpenALReverbEffect::setLateReverbDelay(float late_reverb_delay)
{
	if (m_late_reverb_delay == late_reverb_delay)
		return;

	m_late_reverb_delay = late_reverb_delay;
	this->applyParameter(AL_REVERB_LATE_REVERB_DELAY, m_late_reverb_delay);
}

float OpenALReverbEffect::getAirAbsorptionGainHF() const
{
	return m_air_absorption_gain_hf;
}

void OpenALReverbEffect::setAirAbsorptionGainHF(float air_absorption_gain_hf)
{
	if (m_air_absorption_gain_hf == air_absorption_gain_hf)
		return;

	m_air_absorption_gain_hf = air_absorption_gain_hf;
	this->applyParameter(AL_REVERB_AIR_ABSORPTION_GAINHF, m_air_absorption_gain_hf);
}

float OpenALReverbEffect::getRoomRolloffFactor() const
{
	return m_room_rolloff_factor;
}

void OpenALReverbEffect::setRoomRolloffFactor(float room_rolloff_factor)
{
	if (m_room_rolloff_factor == room_rolloff_factor)
		return;

	m_room_rolloff_factor = room_rolloff_factor;
	this->applyParameter(AL_REVERB_ROOM_ROLLOFF_FACTOR, m_room_rolloff_factor);
}

int OpenALReverbEffect::getDecayLimitHF() const
{
	return m_decay_limit_hf;
}

void OpenALReverbEffect::setDecayLimitHF(int decay_limit_hf)
{
	if (m_decay_limit_hf == decay_limit_hf)
		return;

	m_decay_limit_hf = decay_limit_hf;
	this->applyParameter(AL_REVERB_DECAY_HFLIMIT, m_decay_limit_hf);
}
