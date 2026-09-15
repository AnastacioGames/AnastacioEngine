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

/** \file audaspace/OpenAL/OpenALEffect.h
 *  \ingroup audopenal
 */

#define AUD_CAPI_IMPLEMENTATION
#include "devices/I3DHandle.h"

#include "fx/GEEffects/OpenALEffect.h"
#include "fx/GEEffects/OpenALReverbEffect.h"

#define AL_ALEXT_PROTOTYPES
#include <al.h>
#include <alc.h>
#include <efx.h>

OpenALEffect::OpenALEffect(IOpenALEffectParams *params, ALuint source, ALuint filterType)
{
	m_source = source; // Audio Source

	alGenEffects(1, &m_effect_id);
	
	m_effect_params = params;
	this->update(); // apply effect params

	alGenAuxiliaryEffectSlots(1, &m_slot);
	alAuxiliaryEffectSloti(m_slot, AL_EFFECTSLOT_EFFECT, m_effect_id);

	this->setOpenALParameters();

	// Filter Handle
	m_filter_id = AL_FILTER_NULL;
	if (filterType != AL_FILTER_NULL) {
		alGenFilters(1, &m_filter_id);

		alFilteri(m_filter_id, AL_FILTER_TYPE, filterType);
	}
}

OpenALEffect::~OpenALEffect()
{
	if (m_slot) {
		alAuxiliaryEffectSloti(m_slot, AL_EFFECTSLOT_EFFECT, AL_EFFECT_NULL);
		alSourcei(m_source, AL_DIRECT_FILTER, AL_FILTER_NULL);
		alDeleteAuxiliaryEffectSlots(1, &m_slot);
	}
	if (m_effect_id) {
		alDeleteEffects(1, &m_effect_id);
	}
	if (m_filter_id) {
		alDeleteFilters(1, &m_filter_id);
	}
	if (m_effect_params) {
		delete m_effect_params;
		m_effect_params = nullptr;
	}
	m_source = NULL;
}

void OpenALEffect::update()
{
	if (m_effect_params) {
		m_effect_params->applyParams(m_effect_id);
	}
}

void OpenALEffect::setOpenALParameters()
{
	if (m_effect_params) {
		m_effect_params->setOpenALParameters(m_slot, m_effect_id);
	}
}

const ALuint OpenALEffect::getEffectId()
{
	return m_effect_id;
}

const ALuint OpenALEffect::getFilterId()
{
	return m_filter_id;
}

const ALuint OpenALEffect::getSlot()
{
	return m_slot;
}

IOpenALEffectParams *OpenALEffect::GetInterfaceEffectParams()
{
	return m_effect_params;
}

IOpenALEffectParams *CreateInterfaceEffectParams(aud::SoundEffectType type)
{
	IOpenALEffectParams *effectParams = nullptr;
	switch (type) {
		case aud::AUDIO_EFFECT_INVALID:
			break;

		case aud::AUDIO_EFFECT_REVERB:
			effectParams = new OpenALReverbEffect();
			break;

		default:
			break;
	}

	return effectParams;
}

/*******************************************************************************/
/********************************* Filter Handle *******************************/
/*******************************************************************************/
ALuint GetFilterEffectType(aud::SoundFilterType type)
{
  ALuint filter = AL_FILTER_NULL;
  switch (type) {
    case aud::AUDIO_FILTER_INVALID:
      break;

    case aud::AUDIO_FILTER_LOWPASS:
      filter = AL_FILTER_LOWPASS;
      break;

	case aud::AUDIO_FILTER_HIGHPASS:
      filter = AL_FILTER_HIGHPASS;
      break;

	case aud::AUDIO_FILTER_BANDPASS:
      filter = AL_FILTER_BANDPASS;
      break;

    default:
      break;
  }

  return filter;
}

ALuint OpenALEffect::GetFilterParameter(aud::SoundFilterType type, int index)
{
  ALuint param = AL_FILTER_NULL;
  switch (type) {
    case aud::AUDIO_FILTER_INVALID:
      break;

    case aud::AUDIO_FILTER_LOWPASS:
      param = index == 0 ? AL_LOWPASS_GAIN : AL_LOWPASS_GAINHF;
      break;

    case aud::AUDIO_FILTER_HIGHPASS:
      param = index == 0 ? AL_HIGHPASS_GAIN : AL_HIGHPASS_GAINLF;
      break;

    case aud::AUDIO_FILTER_BANDPASS:
      param = index == 0 ? AL_BANDPASS_GAIN : 
			  index == 1 ? AL_BANDPASS_GAINHF : AL_BANDPASS_GAINLF;
      break;

    default:
      break;
  }

  return param;
}

void OpenALEffect::applyFilterParameter(ALenum param, float value)
{
  if (m_filter_id) {
    alFilterf(m_filter_id, param, value);

    alSourcei(m_source, AL_DIRECT_FILTER, m_filter_id);
  }
}
