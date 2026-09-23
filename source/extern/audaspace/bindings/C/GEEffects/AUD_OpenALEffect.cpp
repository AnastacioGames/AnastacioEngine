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

#define AUD_CAPI_IMPLEMENTATION
#include "devices/IHandleEffect.h"

#include "AUD_OpenALEffect.h"
#include "fx/GEEffects/OpenALEffect.h"
#include "fx/GEEffects/IOpenALEffectParams.h"

#include <cassert>

AUD_API int AUD_EFFECT_getEffectType(AUD_Handle *handle)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
	return h->getEffectType();
  return false;
}

AUD_API int AUD_EFFECT_getFilterType(AUD_Handle *handle)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->getFilterType();
  return false;
}

AUD_API bool AUD_EFFECT_hasEffect(AUD_Handle *handle)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
	return h->hasEffect();
  return false;
}

AUD_API void AUD_EFFECT_setEffect(AUD_Handle *handle, int effectType, int filterType)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
	h->setEffect(effectType, filterType);
}

AUD_API void AUD_EFFECT_removeEffect(AUD_Handle *handle)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
	h->removeEffect();
}

/****************** Reverb bindings ******************/
AUD_API bool AUD_EFFECT_setReverbDensity(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
	return h->setReverbDensity(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbDiffusion(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
	return h->setReverbDiffusion(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbGain(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setReverbGain(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbGainHF(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setReverbGainHF(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbDecayTime(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setReverbDecayTime(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbDecayHFRatio(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setReverbDecayHFRatio(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbReflectionsGain(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setReverbReflectionsGain(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbReflectionsDelay(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setReverbReflectionsDelay(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbLateReverbGain(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setReverbLateReverbGain(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbLateReverbDelay(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setReverbLateReverbDelay(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbAirAbsorptionGainHF(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setReverbAirAbsorptionGainHF(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbRoomRolloffFactor(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setReverbRoomRolloffFactor(value);
  return false;
}

AUD_API bool AUD_EFFECT_setReverbDecayLimitHF(AUD_Handle *handle, int value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setReverbDecayLimitHF(value);
  return false;
}

/****************** Filter bindings ******************/
AUD_API bool AUD_EFFECT_setFilterGain(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setFilterGain(value);
  return false;
}

AUD_API bool AUD_EFFECT_setFilterGainLF(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setFilterGainLF(value);
  return false;
}

AUD_API bool AUD_EFFECT_setFilterGainHF(AUD_Handle *handle, float value)
{
  assert(handle);
  std::shared_ptr<IHandleEffect> h = std::dynamic_pointer_cast<IHandleEffect>(*handle);

  if (h.get())
    return h->setFilterGainHF(value);
  return false;
}