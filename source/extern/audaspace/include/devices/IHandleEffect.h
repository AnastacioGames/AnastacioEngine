/*******************************************************************************
 * Copyright 2009-2016 Jörg Müller
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

/**
 * @file I3DHandle.h
 * @ingroup devices
 * The I3DHandle interface.
 */

#include "util/Math3D.h"

AUD_NAMESPACE_BEGIN

/**
 * @interface IHandleEffect
 * The IHandleEffect interface represents a playback handle for audio effects.
 *
 * The interface has been modelled after the OpenAL 1.1 API,
 * see the [OpenAL Specification](http://openal.org/) for lots of details.
 */
class AUD_API IHandleEffect
{
public:
	/**
	 * Destroys the handle.
	 */
	virtual ~IHandleEffect() {}

	/*
	* Game Engine function
	*/
	virtual int getEffectType()=0;

	
	/*
	* Game Engine function
	*/
	virtual int getFilterType()=0;

	/*
	* Game Engine function
	*/
	virtual bool hasEffect()=0;

	/*
	* Game Engine function
	*/
	virtual void setEffect(int effectType, int filterType)=0;

	/*
	* Game Engine function
	* remove effect
	*/
	virtual void removeEffect()=0;

	virtual bool setReverbDensity(float density)=0;
	virtual bool setReverbDiffusion(float diffusion)=0;
	virtual bool setReverbGain(float gain)=0;
	virtual bool setReverbGainHF(float gain)=0;
	virtual bool setReverbDecayTime(float decay_time)=0;
	virtual bool setReverbDecayHFRatio(float decay_hf_ratio)=0;
	virtual bool setReverbReflectionsGain(float reflection_gain)=0;
	virtual bool setReverbReflectionsDelay(float reflection_delay)=0;
	virtual bool setReverbLateReverbGain(float late_reverb_gain)=0;
	virtual bool setReverbLateReverbDelay(float late_reverb_delay)=0;
	virtual bool setReverbAirAbsorptionGainHF(float air_absorption)=0;
	virtual bool setReverbRoomRolloffFactor(float rolloff_factor)=0;
	virtual bool setReverbDecayLimitHF(int decay_limit_hf)=0;

	virtual bool setFilterGain(float gain)=0;
	virtual bool setFilterGainLF(float gainLF)=0;
	virtual bool setFilterGainHF(float gainHF)=0;
};

AUD_NAMESPACE_END
