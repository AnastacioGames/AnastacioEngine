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

#ifndef __AUD_OPENALEFFECT_H__
#define __AUD_OPENALEFFECT_H__

#include "../include/respec/SoundEffect.h"
#include "../bindings/C/AUD_Types.h"

#include "IOpenALEffectParams.h"

class OpenALEffect
{
public:
	void update();
	void setOpenALParameters();

	const ALuint getEffectId();
	const ALuint getFilterId();
	const ALuint getSlot();

	OpenALEffect(IOpenALEffectParams *params, ALuint source, ALuint filterType);
	~OpenALEffect();

	IOpenALEffectParams *GetInterfaceEffectParams();
	void applyFilterParameter(ALenum param, float value);

	// index is the type of the value to get, ex: 0 = *_GAIN, 1 = *_GAINHF, 2 = *_GAINLF
	ALuint GetFilterParameter(aud::SoundFilterType type, int index);

 private:
	ALuint m_source, m_slot, m_effect_id, m_filter_id;
	IOpenALEffectParams *m_effect_params;
};

IOpenALEffectParams *CreateInterfaceEffectParams(aud::SoundEffectType type);

ALuint GetFilterEffectType(aud::SoundFilterType type);

#endif // AUD_OPENALEFFECT_H
