/*
 * KX_Speaker.cpp
 *
 *
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
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
 *
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 *
 * The Original Code is: all of this file.
 *
 * Contributor(s): none yet.
 *
 * ***** END GPL LICENSE BLOCK *****
 *
 */

/** \file gameengine/Ketsji/KX_Speaker.cpp
 *  \ingroup ketsji
 */

#include "KX_Speaker.h"

#ifdef WITH_AUDASPACE
typedef float sample_t;
#  include <python/PyAPI.h>
#  include <AUD_Sound.h>
#  include <AUD_Special.h>
#  include <AUD_Device.h>
#  include <AUD_Handle.h>
#  include <AUD_PlaybackManager.h>
#  include <GEEffects/AUD_OpenALEffect.h>
#endif

#include "KX_Camera.h"
#include "KX_GameObject.h"
#include "KX_Globals.h"
#include "KX_PyMath.h"  // needed for PyObjectFrom()
#include <iostream>

/* ------------------------------------------------------------------------- */
/* Native functions                                                          */
/* ------------------------------------------------------------------------- */
KX_Speaker::KX_Speaker(void *sgReplicationInfo,
                       SG_Callbacks callbacks,
#ifdef WITH_AUDASPACE
                       AUD_Sound *sound,
#endif  // WITH_AUDASPACE
                       float volume,
                       float pitch,
                       bool startinit,
                       bool is3d,
                       KX_SpeakerSoundSettings settings,
                       KX_SPEAKER_TYPE type)
    : KX_GameObject(sgReplicationInfo, callbacks)
{
#ifdef WITH_AUDASPACE
  m_sound = sound ? AUD_Sound_copy(sound) : nullptr;
  m_handle = nullptr;
#endif  // WITH_AUDASPACE
  m_volume = volume;
  m_pitch = pitch;
  m_startinit = startinit;
  m_is3d = is3d;
  m_settings = settings;
  m_playback = nullptr;
  m_playback_catkey = 0;
  m_type = type;
  m_isplaying = false;
  
  // Cache sound
  if (settings.cache_sound) {
      AUD_Sound *cached = AUD_Sound_cache(m_sound);
      AUD_Sound_free(m_sound);
      m_sound = cached;
  }
}

KX_Speaker::~KX_Speaker()
{
#ifdef WITH_AUDASPACE
  if (m_handle) {
    if (AUD_EFFECT_hasEffect(m_handle)) {
        AUD_EFFECT_removeEffect(m_handle);
    }

    AUD_Handle_stop(m_handle);
  }

  if (m_sound) {
    AUD_Sound_free(m_sound);
  }
#endif  // WITH_AUDASPACE
}

void KX_Speaker::startInitPlay()
{
  if (m_startinit) {
    play();
  }
}

void KX_Speaker::play()
{
#ifdef WITH_AUDASPACE
  if (m_handle) {
    AUD_Handle_stop(m_handle);
    m_handle = nullptr;
  }

  if (!m_sound) {
    return;
  }

  // this is the sound that will be played and not deleted afterwards
  AUD_Sound *sound = m_sound;

  bool loop = false;

  switch (m_type) {
    case KX_SPEAKER_LOOPBIDIRECTIONAL: {
      sound = AUD_Sound_pingpong(sound);
      ATTR_FALLTHROUGH;
    }
    case KX_SPEAKER_LOOPEND: {
      loop = true;
      break;
    }
    case KX_SPEAKER_PLAYEND:
    default: {
      break;
    }
  }

  if (!m_playback) {
    AUD_Device *device = AUD_Device_getCurrent();
    m_handle = AUD_Device_play(device, sound, false);
    AUD_Device_free(device);
  }
  else {
    m_handle = AUD_PlaybackManager_play(m_playback->playbackManager, sound, m_playback_catkey);
  }

  // in case of pingpong, we have to free the sound
  if (sound != m_sound) {
    AUD_Sound_free(sound);
  }

  if (m_handle != nullptr) {
    AUD_Handle_setPosition(m_handle, m_settings.start_at);

    if (m_is3d) {
      AUD_Handle_setRelative(m_handle, true);
      AUD_Handle_setVolumeMaximum(m_handle, m_settings.max_gain);
      AUD_Handle_setVolumeMinimum(m_handle, m_settings.min_gain);
      AUD_Handle_setDistanceReference(m_handle, m_settings.reference_distance);
      AUD_Handle_setDistanceMaximum(m_handle, m_settings.max_distance);
      AUD_Handle_setAttenuation(m_handle, m_settings.rolloff_factor);
      AUD_Handle_setConeAngleInner(m_handle, m_settings.cone_inner_angle);
      AUD_Handle_setConeAngleOuter(m_handle, m_settings.cone_outer_angle);
      AUD_Handle_setConeVolumeOuter(m_handle, m_settings.cone_outer_gain);
    }

    if (loop) {
      AUD_Handle_setLoopCount(m_handle, -1);
    }
    AUD_Handle_setPitch(m_handle, m_pitch);
    AUD_Handle_setVolume(m_handle, m_volume);

    // set active effect
    if (m_settings.active_effect_type > 0) {
      AUD_EFFECT_setEffect(m_handle, m_settings.active_effect_type, m_settings.active_filter_type);
      this->UpdateEffect();
    }
  }

  m_isplaying = true;
#endif  // WITH_AUDASPACE
}

EXP_Value *KX_Speaker::GetReplica()
{
  KX_Speaker *replica = new KX_Speaker(*this);

  replica->ProcessReplica();
  return replica;
}

void KX_Speaker::ProcessReplica()
{
  KX_GameObject::ProcessReplica();
#ifdef WITH_AUDASPACE
  m_handle = nullptr;
  m_sound = m_sound ? AUD_Sound_copy(m_sound) : nullptr;

  if (m_startinit)
    play();
#endif  // WITH_AUDASPACE
}

void KX_Speaker::Update()
{
#ifdef WITH_AUDASPACE
  if (!m_sound) {
    return;
  }

  // actual audio device playing state
  bool isplaying = m_handle ? (AUD_Handle_getStatus(m_handle) == AUD_STATUS_PLAYING) : false;

  // Remove the speaker from the scene.
  if (m_settings.destroy_after && !isplaying)
    this->PyEndObject();

  // Update camera position for 3D sound.
  if (m_is3d && isplaying) {
    KX_Camera *cam = KX_GetActiveScene()->GetActiveCamera();
    if (cam) {
      mt::vec3 p;
      mt::mat3 Mo;
      float data[4];
      
      Mo = cam->NodeGetWorldOrientation().Inverse();
      p = (NodeGetWorldPosition() - cam->NodeGetWorldPosition());
      p = Mo * p;
      p.Pack(data);
      AUD_Handle_setLocation(m_handle, data);
      p = (GetLinearVelocity() - cam->GetLinearVelocity());
      p = Mo * p;
      p.Pack(data);
      AUD_Handle_setVelocity(m_handle, data);
      mt::quat::FromMatrix(Mo * NodeGetWorldOrientation()).Pack(data);
      AUD_Handle_setOrientation(m_handle, data);
    }
  }
  else {
    m_isplaying = false;
  }
#endif  // WITH_AUDASPACE
}

void KX_Speaker::UpdateEffect()
{
  if (!m_handle)
    return;

  switch (AUD_EFFECT_getEffectType(m_handle)) {
    case 0: // null
      break;

    case 1: // REVERB
      AUD_EFFECT_setReverbDensity(m_handle, m_settings.reverb_density);
      AUD_EFFECT_setReverbDiffusion(m_handle, m_settings.reverb_diffusion);
      AUD_EFFECT_setReverbGain(m_handle, m_settings.reverb_gain);
      AUD_EFFECT_setReverbGainHF(m_handle, m_settings.reverb_gain_hf);
      AUD_EFFECT_setReverbDecayTime(m_handle, m_settings.reverb_decay_time);
      AUD_EFFECT_setReverbDecayHFRatio(m_handle, m_settings.reverb_decay_hf_ratio);
      AUD_EFFECT_setReverbReflectionsGain(m_handle, m_settings.reverb_reflections_gain);
      AUD_EFFECT_setReverbReflectionsDelay(m_handle, m_settings.reverb_reflections_delay);
      AUD_EFFECT_setReverbLateReverbGain(m_handle, m_settings.reverb_late_reverb_gain);
      AUD_EFFECT_setReverbLateReverbDelay(m_handle, m_settings.reverb_late_reverb_delay);
      AUD_EFFECT_setReverbAirAbsorptionGainHF(m_handle, m_settings.reverb_air_absorption_gain_hf);
      AUD_EFFECT_setReverbRoomRolloffFactor(m_handle, m_settings.reverb_room_rolloff_factor);
      AUD_EFFECT_setReverbDecayLimitHF(m_handle, m_settings.reverb_decay_limit_hf);
      break;

    default:
      break;
  }

  // Update Filter
  if (AUD_EFFECT_getFilterType(m_handle)) {
      AUD_EFFECT_setFilterGain(m_handle, m_settings.filter_gain);
      AUD_EFFECT_setFilterGainLF(m_handle, m_settings.filter_gainlf);
      AUD_EFFECT_setFilterGainHF(m_handle, m_settings.filter_gainhf);
  }
}

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python functions                                                          */
/* ------------------------------------------------------------------------- */

/* Integration hooks ------------------------------------------------------- */
PyTypeObject KX_Speaker::Type = {PyVarObject_HEAD_INIT(nullptr, 0) "KX_Speaker",
                                 sizeof(EXP_PyObjectPlus_Proxy),
                                 0,
                                 py_base_dealloc,
                                 0,
                                 0,
                                 0,
                                 0,
                                 py_base_repr,
                                 0,
                                 &KX_GameObject::Sequence,
                                 &KX_GameObject::Mapping,
                                 0,
                                 0,
                                 0,
                                 nullptr,
                                 nullptr,
                                 0,
                                 Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
                                 0,
                                 0,
                                 0,
                                 0,
                                 0,
                                 0,
                                 0,
                                 Methods,
                                 0,
                                 0,
                                 &KX_GameObject::Type,
                                 0,
                                 0,
                                 0,
                                 0,
                                 0,
                                 0,
                                 py_base_new};

PyMethodDef KX_Speaker::Methods[] = {
    EXP_PYMETHODTABLE_NOARGS(KX_Speaker, Play),
    EXP_PYMETHODTABLE_NOARGS(KX_Speaker, Restart),
    EXP_PYMETHODTABLE_NOARGS(KX_Speaker, Pause),
    EXP_PYMETHODTABLE_NOARGS(KX_Speaker, Stop),
    EXP_PYMETHODTABLE(KX_Speaker, SetSound),
    EXP_PYMETHODTABLE_NOARGS(KX_Speaker, GetActiveEffect),
    EXP_PYMETHODTABLE_NOARGS(KX_Speaker, GetActiveEffectFilter),
    EXP_PYMETHODTABLE(KX_Speaker, SetEffect),
    EXP_PYMETHODTABLE_NOARGS(KX_Speaker, RemoveEffect),
    {nullptr, nullptr}  // Sentinel
};

PyAttributeDef KX_Speaker::Attributes[] = {
    EXP_PYATTRIBUTE_BOOL_RO("is3D", KX_Speaker, m_is3d),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "volume_maximum", KX_Speaker, pyattr_get_3d_property, pyattr_set_3d_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "volume_minimum", KX_Speaker, pyattr_get_3d_property, pyattr_set_3d_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "distance_reference", KX_Speaker, pyattr_get_3d_property, pyattr_set_3d_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "distance_maximum", KX_Speaker, pyattr_get_3d_property, pyattr_set_3d_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "attenuation", KX_Speaker, pyattr_get_3d_property, pyattr_set_3d_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "cone_angle_inner", KX_Speaker, pyattr_get_3d_property, pyattr_set_3d_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "cone_angle_outer", KX_Speaker, pyattr_get_3d_property, pyattr_set_3d_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "cone_volume_outer", KX_Speaker, pyattr_get_3d_property, pyattr_set_3d_property),
    EXP_PYATTRIBUTE_RW_FUNCTION("sound", KX_Speaker, pyattr_get_sound, pyattr_set_sound),
    EXP_PYATTRIBUTE_RW_FUNCTION("playbackManager", KX_Speaker, pyattr_get_playbackManager, pyattr_set_playbackManager),
    EXP_PYATTRIBUTE_RW_FUNCTION("catkey", KX_Speaker, pyattr_get_catkey, pyattr_set_catkey),

    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_density", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_diffusion", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_gain", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_gain_hf", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_decay_time", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_decay_hf_ratio", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_reflections_gain", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_reflections_delay", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_late_reverb_gain", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_late_reverb_delay", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_air_absorption_gain_hf", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_room_rolloff_factor", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "reverb_decay_limit_hf", KX_Speaker, pyattr_get_reverb_effect_property, pyattr_set_reverb_effect_property),

    EXP_PYATTRIBUTE_RW_FUNCTION(
        "filter_gain", KX_Speaker, pyattr_get_effect_filter_property, pyattr_set_effect_filter_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "filter_gainlf", KX_Speaker, pyattr_get_effect_filter_property, pyattr_set_effect_filter_property),
    EXP_PYATTRIBUTE_RW_FUNCTION(
        "filter_gainhf", KX_Speaker, pyattr_get_effect_filter_property, pyattr_set_effect_filter_property),

    EXP_PYATTRIBUTE_RW_FUNCTION(
        "time", KX_Speaker, pyattr_get_audposition, pyattr_set_audposition),
    EXP_PYATTRIBUTE_RW_FUNCTION("volume", KX_Speaker, pyattr_get_gain, pyattr_set_gain),
    EXP_PYATTRIBUTE_RW_FUNCTION("pitch", KX_Speaker, pyattr_get_pitch, pyattr_set_pitch),
    EXP_PYATTRIBUTE_ENUM_RW("mode",
                            KX_Speaker::KX_SPEAKER_NODEF + 1,
                            KX_Speaker::KX_SPEAKER_MAX - 1,
                            false,
                            KX_Speaker,
                            m_type),
    EXP_PYATTRIBUTE_NULL  // Sentinel
};

/* Methods ----------------------------------------------------------------- */
EXP_PYMETHODDEF_DOC_NOARGS(KX_Speaker,
                           Play,
                           "Play()\n"
                           "\tStarts the sound.\n")
{
#  ifdef WITH_AUDASPACE
  switch (m_handle ? AUD_Handle_getStatus(m_handle) : AUD_STATUS_INVALID) {
    case AUD_STATUS_PLAYING: {
      break;
    }
    case AUD_STATUS_PAUSED: {
      AUD_Handle_resume(m_handle);
      break;
    }
    default:
      play();
      
      // We need to update the 3D sound camera position at same time we are playing. (KX_Scene.UpdateFrequency may interfere on this)
      if (m_is3d) {
        this->Update();
      }
  }
#  endif  // WITH_AUDASPACE

  Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC_NOARGS(KX_Speaker,
                           Restart,
                           "Restart()\n"
                           "\tRestart the sound to the starting position\n")
{
#  ifdef WITH_AUDASPACE
  switch (m_handle ? AUD_Handle_getStatus(m_handle) : AUD_STATUS_INVALID) {
    case AUD_STATUS_PLAYING: {
      // Reset the position.
      AUD_Handle_setPosition(m_handle, m_settings.start_at);
      break;
    }
    case AUD_STATUS_PAUSED: {
      AUD_Handle_resume(m_handle);
      break;
    }
    default:
      play();

      if (m_is3d) {
        this->Update();
      }
  }

#  endif  // WITH_AUDASPACE

  Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC_NOARGS(KX_Speaker,
                           Pause,
                           "Pause()\n"
                           "\tPauses the sound.\n")
{
#  ifdef WITH_AUDASPACE
  if (m_handle) {
    AUD_Handle_pause(m_handle);
  }
#  endif  // WITH_AUDASPACE

  Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC_NOARGS(KX_Speaker,
                           Stop,
                           "Stop()\n"
                           "\tStops the sound.\n")
{
#  ifdef WITH_AUDASPACE
  if (m_handle) {
    AUD_Handle_stop(m_handle);
    m_handle = nullptr;
  }
#  endif  // WITH_AUDASPACE

  Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_Speaker, SetSound,
                    "SetSound(sound, cache): Change the speaker sound\n")
{
	PyObject *sound = nullptr;
    bool cache_sound = false;

	if (!PyArg_ParseTuple(args, "O|b:SetSound", &sound, &cache_sound)) {
		return nullptr;
	}

#ifdef WITH_AUDASPACE
    AUD_Sound *snd = AUD_getSoundFromPython(sound);

    if (!snd) {
        return nullptr;
    }

    if (cache_sound) {
        AUD_Sound *snd_cache = AUD_Sound_cache(snd);
        AUD_Sound_free(snd);
        snd = snd_cache;
    }

    if (m_handle) {
      AUD_Handle_stop(m_handle);
      m_handle = nullptr;
    }

    AUD_Sound_free(m_sound);
    m_sound = snd;
#endif  // WITH_AUDASPACE

    Py_RETURN_NONE;
}

/******************************************************************************/
/*********************** OpenALHandle PyHandle Effects *************************/
/******************************************************************************/

EXP_PYMETHODDEF_DOC(KX_Speaker, GetActiveEffect, "GetActiveEffect(): Get Active Sound Effect\n")
{
    int effect = m_settings.active_effect_type;
    return PyLong_FromLong(effect);
}

EXP_PYMETHODDEF_DOC(KX_Speaker, GetActiveEffectFilter, "GetActiveEffectFilter(): Get Active Filter Sound Effect\n")
{
  int filter = m_settings.active_filter_type;
  return PyLong_FromLong(filter);
}

EXP_PYMETHODDEF_DOC(KX_Speaker, SetEffect, "SetEffect(effectType): Add Sound Effects\n")
{
    int type; // SoundEffectType enum
    int filterType = 0; // SoundFilterType enum

    if (!PyArg_ParseTuple(args, "i|i:SetEffect", &type, &filterType)) {
        return nullptr;
    }

    m_settings.active_effect_type = type;
    m_settings.active_filter_type = filterType;

    if (!m_handle) {
        Py_RETURN_NONE;
    }

#ifdef WITH_AUDASPACE
    if (AUD_EFFECT_hasEffect(m_handle)) {
        AUD_EFFECT_removeEffect(m_handle);
    }
    
    AUD_EFFECT_setEffect(m_handle, type, filterType);
  
#endif  // WITH_AUDASPACE

    Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC_NOARGS(KX_Speaker,
                           RemoveEffect,
                           "RemoveEffect()\n"
                           "\tRemove the effect.\n")
{
    if (!m_handle) {
        Py_RETURN_NONE;
    }
#ifdef WITH_AUDASPACE
    if (AUD_EFFECT_hasEffect(m_handle)) {
        AUD_EFFECT_removeEffect(m_handle);
    }
    m_settings.active_effect_type = 0; // null
    m_settings.active_filter_type = 0; // null
#endif  // WITH_AUDASPACE

    Py_RETURN_NONE;
}

/* Atribute setting and getting -------------------------------------------- */
PyObject *KX_Speaker::pyattr_get_3d_property(EXP_PyObjectPlus *self,
                                             const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);
  const std::string &prop = attrdef->m_name;
  float result_value = 0.0f;

  if (prop == "volume_maximum") {
    result_value = speaker->m_settings.max_gain;
  }
  else if (prop == "volume_minimum") {
    result_value = speaker->m_settings.min_gain;
  }
  else if (prop == "distance_reference") {
    result_value = speaker->m_settings.reference_distance;
  }
  else if (prop == "distance_maximum") {
    result_value = speaker->m_settings.max_distance;
  }
  else if (prop == "attenuation") {
    result_value = speaker->m_settings.rolloff_factor;
  }
  else if (prop == "cone_angle_inner") {
    result_value = speaker->m_settings.cone_inner_angle;
  }
  else if (prop == "cone_angle_outer") {
    result_value = speaker->m_settings.cone_outer_angle;
  }
  else if (prop == "cone_volume_outer") {
    result_value = speaker->m_settings.cone_outer_gain;
  }
  else {
    Py_RETURN_NONE;
  }

  PyObject *result = PyFloat_FromDouble(result_value);
  return result;
}

PyObject *KX_Speaker::pyattr_get_reverb_effect_property(EXP_PyObjectPlus *self,
                                             const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);
  const std::string &prop = attrdef->m_name;
  float result_value = 0.0f;

  if (prop == "reverb_density") {
    result_value = speaker->m_settings.reverb_density;
  }
  else if (prop == "reverb_diffusion") {
    result_value = speaker->m_settings.reverb_diffusion;
  }
  else if (prop == "reverb_gain") {
    result_value = speaker->m_settings.reverb_gain;
  }
  else if (prop == "reverb_gain_hf") {
    result_value = speaker->m_settings.reverb_gain_hf;
  }
  else if (prop == "reverb_decay_time") {
    result_value = speaker->m_settings.reverb_decay_time;
  }
  else if (prop == "reverb_decay_hf_ratio") {
    result_value = speaker->m_settings.reverb_decay_hf_ratio;
  }
  else if (prop == "reverb_reflections_gain") {
    result_value = speaker->m_settings.reverb_reflections_gain;
  }
  else if (prop == "reverb_reflections_delay") {
    result_value = speaker->m_settings.reverb_reflections_delay;
  }
  else if (prop == "reverb_late_reverb_gain") {
    result_value = speaker->m_settings.reverb_late_reverb_gain;
  }
  else if (prop == "reverb_late_reverb_delay") {
    result_value = speaker->m_settings.reverb_late_reverb_delay;
  }
  else if (prop == "reverb_air_absorption_gain_hf") {
    result_value = speaker->m_settings.reverb_air_absorption_gain_hf;
  }
  else if (prop == "reverb_room_rolloff_factor") {
    result_value = speaker->m_settings.reverb_room_rolloff_factor;
  }
  else if (prop == "reverb_decay_limit_hf") {
    result_value = speaker->m_settings.reverb_decay_limit_hf;
  }
  else {
    Py_RETURN_NONE;
  }

  PyObject *result = PyFloat_FromDouble(result_value);
  return result;
}

PyObject *KX_Speaker::pyattr_get_effect_filter_property(EXP_PyObjectPlus *self,
                                                        const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);
  const std::string &prop = attrdef->m_name;
  float result_value = 0.0f;

  if (prop == "filter_gain") {
    result_value = speaker->m_settings.filter_gain;
  }
  else if (prop == "filter_gainlf") {
    result_value = speaker->m_settings.filter_gainlf;
  }
  else if (prop == "filter_gainhf") {
    result_value = speaker->m_settings.filter_gainhf;
  }
  else {
    Py_RETURN_NONE;
  }

  PyObject *result = PyFloat_FromDouble(result_value);
  return result;
}

PyObject *KX_Speaker::pyattr_get_audposition(EXP_PyObjectPlus *self,
                                             const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
  float position = 0.0f;

#  ifdef WITH_AUDASPACE
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);

  if (speaker->m_handle) {
    position = AUD_Handle_getPosition(speaker->m_handle);
  }
#  endif  // WITH_AUDASPACE

  PyObject *result = PyFloat_FromDouble(position);

  return result;
}

PyObject *KX_Speaker::pyattr_get_gain(EXP_PyObjectPlus *self,
                                      const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);
  float gain = speaker->m_volume;

  PyObject *result = PyFloat_FromDouble(gain);

  return result;
}

PyObject *KX_Speaker::pyattr_get_pitch(EXP_PyObjectPlus *self,
                                       const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);
  float pitch = speaker->m_pitch;

  PyObject *result = PyFloat_FromDouble(pitch);

  return result;
}

PyObject *KX_Speaker::pyattr_get_sound(EXP_PyObjectPlus *self,
                                       const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
#  ifdef WITH_AUDASPACE
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);

  if (speaker->m_sound) {
    return (PyObject *)AUD_getPythonSound(speaker->m_sound);
  }
#  endif  // WITH_AUDASPACE

  Py_RETURN_NONE;
}

PyObject *KX_Speaker::pyattr_get_playbackManager(EXP_PyObjectPlus *self,
                                       const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
#  ifdef WITH_AUDASPACE
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);

  if (speaker->m_playback) {
      return (PyObject*)speaker->m_playback;
  }
#  endif  // WITH_AUDASPACE

  Py_RETURN_NONE;
}

PyObject *KX_Speaker::pyattr_get_catkey(EXP_PyObjectPlus *self,
                                                 const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
#  ifdef WITH_AUDASPACE
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);

  if (speaker->m_playback_catkey) {
      return PyLong_FromLong(speaker->m_playback_catkey);
  }
#  endif  // WITH_AUDASPACE

  Py_RETURN_NONE;
}

int KX_Speaker::pyattr_set_3d_property(EXP_PyObjectPlus *self,
                                       const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                       PyObject *value)
{
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);
  const std::string &prop = attrdef->m_name;
  float prop_value = 0.0f;

  if (!PyArg_Parse(value, "f", &prop_value)) {
    return PY_SET_ATTR_FAIL;
  }

  // if sound is working and 3D, set the new setting
  if (!speaker->m_is3d) {
    return PY_SET_ATTR_FAIL;
  }

  if (prop == "volume_maximum") {
    speaker->m_settings.max_gain = prop_value;
#  ifdef WITH_AUDASPACE
    if (speaker->m_handle) {
      AUD_Handle_setVolumeMaximum(speaker->m_handle, prop_value);
    }
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "volume_minimum") {
    speaker->m_settings.min_gain = prop_value;
#  ifdef WITH_AUDASPACE
    if (speaker->m_handle) {
      AUD_Handle_setVolumeMinimum(speaker->m_handle, prop_value);
    }
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "distance_reference") {
    speaker->m_settings.reference_distance = prop_value;
#  ifdef WITH_AUDASPACE
    if (speaker->m_handle) {
      AUD_Handle_setDistanceReference(speaker->m_handle, prop_value);
    }
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "distance_maximum") {
    speaker->m_settings.max_distance = prop_value;
#  ifdef WITH_AUDASPACE
    if (speaker->m_handle) {
      AUD_Handle_setDistanceMaximum(speaker->m_handle, prop_value);
    }
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "attenuation") {
    speaker->m_settings.rolloff_factor = prop_value;
#  ifdef WITH_AUDASPACE
    if (speaker->m_handle) {
      AUD_Handle_setAttenuation(speaker->m_handle, prop_value);
    }
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "cone_angle_inner") {
    speaker->m_settings.cone_inner_angle = prop_value;
#  ifdef WITH_AUDASPACE
    if (speaker->m_handle) {
      AUD_Handle_setConeAngleInner(speaker->m_handle, prop_value);
    }
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "cone_angle_outer") {
    speaker->m_settings.cone_outer_angle = prop_value;
#  ifdef WITH_AUDASPACE
    if (speaker->m_handle) {
      AUD_Handle_setConeAngleOuter(speaker->m_handle, prop_value);
    }
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "cone_volume_outer") {
    speaker->m_settings.cone_outer_gain = prop_value;
#  ifdef WITH_AUDASPACE
    if (speaker->m_handle) {
      AUD_Handle_setConeVolumeOuter(speaker->m_handle, prop_value);
    }
#  endif  // WITH_AUDASPACE
  }
  else {
    return PY_SET_ATTR_FAIL;
  }

  return PY_SET_ATTR_SUCCESS;
}

int KX_Speaker::pyattr_set_reverb_effect_property(EXP_PyObjectPlus *self,
                                       const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                       PyObject *value)
{
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);
  const std::string &prop = attrdef->m_name;
  float prop_value = 0.0f;

  if (!PyArg_Parse(value, "f", &prop_value)) {
    return PY_SET_ATTR_FAIL;
  }

  // if sound is working and has reverb effect, set the new setting
  if (!speaker->m_handle) {
    return 0;
  }
  if (!AUD_EFFECT_hasEffect(speaker->m_handle)) {
    return 0;
  }
  if (AUD_EFFECT_getEffectType(speaker->m_handle) != 1) { // 1 = REVERB, see aud::SoundEffectType
    return 0;
  }
  
  if (prop == "reverb_density") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.0f, 1.0f);

      speaker->m_settings.reverb_density = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbDensity(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_diffusion") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.0f, 1.0f);

      speaker->m_settings.reverb_diffusion = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbDiffusion(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_gain") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.0f, 1.0f);

      speaker->m_settings.reverb_gain = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbGain(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_gain_hf") {
     // set value limit, avoid problems
     prop_value = mt::Clamp(prop_value, 0.0f, 1.0f);

     speaker->m_settings.reverb_gain_hf = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbGainHF(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_decay_time") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.1f, 20.0f);

      speaker->m_settings.reverb_decay_time = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbDecayTime(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_decay_hf_ratio") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.1f, 2.0f);

      speaker->m_settings.reverb_decay_hf_ratio = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbDecayHFRatio(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_reflections_gain") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.0f, 3.16f);

      speaker->m_settings.reverb_reflections_gain = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbReflectionsGain(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_reflections_delay") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.0f, 0.3f);

      speaker->m_settings.reverb_reflections_delay = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbReflectionsDelay(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_late_reverb_gain") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.0f, 10.0f);

      speaker->m_settings.reverb_late_reverb_gain = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbLateReverbGain(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_late_reverb_delay") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.0f, 0.1f);

      speaker->m_settings.reverb_late_reverb_delay = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbLateReverbDelay(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_air_absorption_gain_hf") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.892f, 1.0f);

      speaker->m_settings.reverb_air_absorption_gain_hf = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbAirAbsorptionGainHF(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_room_rolloff_factor") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.0f, 10.0f);

      speaker->m_settings.reverb_room_rolloff_factor = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbRoomRolloffFactor(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "reverb_decay_limit_hf") {
      // set value limit, avoid problems
      prop_value = mt::Clamp((int)prop_value, 0, 1);

      speaker->m_settings.reverb_decay_limit_hf = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setReverbDecayLimitHF(speaker->m_handle, (int)prop_value);
#  endif  // WITH_AUDASPACE
  }
  else {
    return PY_SET_ATTR_FAIL;
  }

  return PY_SET_ATTR_SUCCESS;
}

int KX_Speaker::pyattr_set_effect_filter_property(EXP_PyObjectPlus *self,
                                       const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                       PyObject *value)
{
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);
  const std::string &prop = attrdef->m_name;
  float prop_value = 0.0f;

  if (!PyArg_Parse(value, "f", &prop_value)) {
    return PY_SET_ATTR_FAIL;
  }

  // if sound is working and has reverb effect, set the new setting
  if (!speaker->m_handle) {
    return 0;
  }
  if (!AUD_EFFECT_hasEffect(speaker->m_handle)) {
    return 0;
  }
  if (!AUD_EFFECT_getFilterType(speaker->m_handle)) {
    return 0;
  }
  
  if (prop == "filter_gain") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.0f, 1.0f);

      speaker->m_settings.filter_gain = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setFilterGain(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "filter_gainlf") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.0f, 1.0f);

      speaker->m_settings.filter_gainlf = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setFilterGainLF(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else if (prop == "filter_gainhf") {
      // set value limit, avoid problems
      prop_value = mt::Clamp(prop_value, 0.0f, 1.0f);

      speaker->m_settings.filter_gainhf = prop_value;
#  ifdef WITH_AUDASPACE
      AUD_EFFECT_setFilterGainHF(speaker->m_handle, prop_value);
#  endif  // WITH_AUDASPACE
  }
  else {
    return PY_SET_ATTR_FAIL;
  }

  return PY_SET_ATTR_SUCCESS;
}

int KX_Speaker::pyattr_set_audposition(EXP_PyObjectPlus *self,
                                       const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                       PyObject *value)
{
  float position = 1.0f;
  if (!PyArg_Parse(value, "f", &position)) {
    return PY_SET_ATTR_FAIL;
  }

#  ifdef WITH_AUDASPACE
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);

  if (speaker->m_handle) {
    AUD_Handle_setPosition(speaker->m_handle, position);
  }
#  endif  // WITH_AUDASPACE

  return PY_SET_ATTR_SUCCESS;
}

int KX_Speaker::pyattr_set_gain(EXP_PyObjectPlus *self,
                                const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                PyObject *value)
{
  float gain = 1.0f;
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);
  if (!PyArg_Parse(value, "f", &gain)) {
    return PY_SET_ATTR_FAIL;
  }

  speaker->m_volume = gain;

#  ifdef WITH_AUDASPACE
  if (speaker->m_handle) {
    AUD_Handle_setVolume(speaker->m_handle, gain);
  }
#  endif  // WITH_AUDASPACE

  return PY_SET_ATTR_SUCCESS;
}

int KX_Speaker::pyattr_set_pitch(EXP_PyObjectPlus *self,
                                 const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                 PyObject *value)
{
  float pitch = 1.0f;
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);
  if (!PyArg_Parse(value, "f", &pitch)) {
    return PY_SET_ATTR_FAIL;
  }

  speaker->m_pitch = pitch;

#  ifdef WITH_AUDASPACE
  if (speaker->m_handle) {
    AUD_Handle_setPitch(speaker->m_handle, pitch);
  }
#  endif  // WITH_AUDASPACE

  return PY_SET_ATTR_SUCCESS;
}

int KX_Speaker::pyattr_set_sound(EXP_PyObjectPlus *self,
                                 const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                 PyObject *value)
{
  PyObject *sound = nullptr;
  if (!PyArg_Parse(value, "O", &sound)) {
    return PY_SET_ATTR_FAIL;
  }

#  ifdef WITH_AUDASPACE
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);

  AUD_Sound *snd = AUD_getSoundFromPython(sound);

  if (!snd) {
    return PY_SET_ATTR_FAIL;
  }

  AUD_Sound_free(speaker->m_sound);
  speaker->m_sound = snd;
#  endif  // WITH_AUDASPACE

  return PY_SET_ATTR_SUCCESS;
}

int KX_Speaker::pyattr_set_catkey(EXP_PyObjectPlus *self,
                                 const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                 PyObject *value)
{
  int catkey;
  if (!PyArg_Parse(value, "i", &catkey)) {
    return PY_SET_ATTR_FAIL;
  }

#  ifdef WITH_AUDASPACE
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);

  // XXX
  speaker->m_playback_catkey = catkey;

#  endif  // WITH_AUDASPACE

  return PY_SET_ATTR_SUCCESS;
}

int KX_Speaker::pyattr_set_playbackManager(EXP_PyObjectPlus *self,
                                           const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                           PyObject *value)
{
  PyObject *object = nullptr;
  if (!PyArg_Parse(value, "O", &object)) {
    return PY_SET_ATTR_FAIL;
  }

#  ifdef WITH_AUDASPACE
  KX_Speaker *speaker = static_cast<KX_Speaker *>(self);

  PlaybackManagerP *playback = checkPlaybackManager(object);  

  if (playback) {
    Py_INCREF(object);
    speaker->m_playback = playback;
  }

#  endif  // WITH_AUDASPACE

  return PY_SET_ATTR_SUCCESS;
}
#endif  // WITH_PYTHON
