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
 * @file SoundEffect.h
 * @ingroup respec
 * Defines all important macros and basic data structures for audio effects.
 */

#include "Audaspace.h"

AUD_NAMESPACE_BEGIN

/**
 * Sound Effect Type. Game Engine use.
 */
enum SoundEffectType {
  AUDIO_EFFECT_INVALID = 0,     /// Invalid.
  AUDIO_EFFECT_REVERB = 1     /// Audio Reveberation.
};

/**
 * Sound Filter Type. Game Engine use.
 */
enum SoundFilterType {
  AUDIO_FILTER_INVALID = 0,  /// Invalid.
  AUDIO_FILTER_LOWPASS = 1,  /// Audio LOWPASS.
  AUDIO_FILTER_HIGHPASS = 2,  /// Audio HIGHPASS.
  AUDIO_FILTER_BANDPASS = 3   /// Audio BANDPASS.
};

AUD_NAMESPACE_END
