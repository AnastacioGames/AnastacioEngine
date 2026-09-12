/*
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
 */

/** \file KX_Speaker.h
 *  \ingroup ketsji
 */

#ifndef __KX_SPEAKER_H__
#define __KX_SPEAKER_H__

#include "KX_GameObject.h"

#ifdef WITH_AUDASPACE
#  include <AUD_Sound.h>
#  include <AUD_Handle.h>
#  include "../../../../extern/audaspace/bindings/python/PyPlaybackManager.h"
#endif

#include "BKE_sound.h"

typedef struct KX_SpeakerSoundSettings {
  /* Sound Settings */
  float start_at;
  bool destroy_after;
  bool cache_sound; // saves the sound in the RAM

  /* 3D Sound Settings */
  float min_gain;
  float max_gain;
  float reference_distance;
  float max_distance;
  float rolloff_factor;
  float cone_inner_angle;
  float cone_outer_angle;
  float cone_outer_gain;

  /* Sound Effect Settings */
  int active_effect_type;
  int active_filter_type;

  /* Sound Reverb Settings */
  float reverb_density;
  float reverb_diffusion;
  float reverb_gain;
  float reverb_gain_hf;
  float reverb_decay_time;
  float reverb_decay_hf_ratio;
  float reverb_reflections_gain;
  float reverb_reflections_delay;
  float reverb_late_reverb_gain;
  float reverb_late_reverb_delay;
  float reverb_air_absorption_gain_hf;
  float reverb_room_rolloff_factor;
  int reverb_decay_limit_hf;

  /* Sound Filter Settings */
  float filter_gain;
  float filter_gainlf; // only for AUDIO_FILTER_BANDPASS
  float filter_gainhf;

} KX_SpeakerSoundSettings;

class KX_Speaker : public KX_GameObject {
  Py_Header
protected:
  friend class KX_Scene;
  bool m_isplaying;
#ifdef WITH_AUDASPACE
  AUD_Sound *m_sound;
  AUD_Handle *m_handle;
#endif  // WITH_AUDASPACE
  float m_volume;
  float m_pitch;
  bool m_startinit;
  bool m_is3d;
  KX_SpeakerSoundSettings m_settings;
  PlaybackManagerP *m_playback; // an playbackManager to play sound
  int m_playback_catkey;

  void startInitPlay();
  void play();

 public:
  enum KX_SPEAKER_TYPE {
    KX_SPEAKER_NODEF = 0,
    KX_SPEAKER_PLAYEND,
    KX_SPEAKER_LOOPEND,
    KX_SPEAKER_LOOPBIDIRECTIONAL,
    KX_SPEAKER_MAX
  };

  KX_SPEAKER_TYPE m_type;

  KX_Speaker(void *sgReplicationInfo,
             SG_Callbacks callbacks,
#ifdef WITH_AUDASPACE
             AUD_Sound *sound,
#endif  // WITH_AUDASPACE
             float volume,
             float pitch,
             bool startinit,
             bool is3d,
             KX_SpeakerSoundSettings settings,
             KX_SPEAKER_TYPE type);

  virtual ~KX_Speaker();

  void Update();
  void UpdateEffect();

  virtual EXP_Value *GetReplica();
  virtual void ProcessReplica();
  virtual int GetGameObjectType() const
  {
    return OBJ_SPEAKER;
  }

#ifdef WITH_PYTHON

  /* -------------------------------------------------------------------- */
  /* Python interface --------------------------------------------------- */
  /* -------------------------------------------------------------------- */

  EXP_PYMETHOD_DOC_NOARGS(KX_Speaker, Play);
  EXP_PYMETHOD_DOC_NOARGS(KX_Speaker, Restart);
  EXP_PYMETHOD_DOC_NOARGS(KX_Speaker, Pause);
  EXP_PYMETHOD_DOC_NOARGS(KX_Speaker, Stop);
  EXP_PYMETHOD_DOC(KX_Speaker, SetSound);
  EXP_PYMETHOD_DOC(KX_Speaker, GetActiveEffect);
  EXP_PYMETHOD_DOC(KX_Speaker, GetActiveEffectFilter);
  EXP_PYMETHOD_DOC(KX_Speaker, SetEffect);
  EXP_PYMETHOD_DOC_NOARGS(KX_Speaker, RemoveEffect);

  static int pyattr_set_3d_property(EXP_PyObjectPlus *self,
                                    const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                    PyObject *value);
  static int pyattr_set_reverb_effect_property(EXP_PyObjectPlus *self,
                                    const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                    PyObject *value);
  static int pyattr_set_effect_filter_property(EXP_PyObjectPlus *self,
                                    const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                    PyObject *value);
  static int pyattr_set_audposition(EXP_PyObjectPlus *self,
                                    const struct EXP_PYATTRIBUTE_DEF *attrdef,
                                    PyObject *value);
  static int pyattr_set_gain(EXP_PyObjectPlus *self,
                             const struct EXP_PYATTRIBUTE_DEF *attrdef,
                             PyObject *value);
  static int pyattr_set_pitch(EXP_PyObjectPlus *self,
                              const struct EXP_PYATTRIBUTE_DEF *attrdef,
                              PyObject *value);
  static int pyattr_set_type(EXP_PyObjectPlus *self,
                             const struct EXP_PYATTRIBUTE_DEF *attrdef,
                             PyObject *value);
  static int pyattr_set_sound(EXP_PyObjectPlus *self,
                              const struct EXP_PYATTRIBUTE_DEF *attrdef,
                              PyObject *value);
  static int pyattr_set_playbackManager(EXP_PyObjectPlus *self,
                              const struct EXP_PYATTRIBUTE_DEF *attrdef,
                              PyObject *value);
  static int pyattr_set_catkey(EXP_PyObjectPlus *self,
                              const struct EXP_PYATTRIBUTE_DEF *attrdef,
                              PyObject *value);

  static PyObject *pyattr_get_3d_property(EXP_PyObjectPlus *self,
                                          const struct EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_reverb_effect_property(EXP_PyObjectPlus *self,
                                          const struct EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_effect_filter_property(EXP_PyObjectPlus *self,
                                          const struct EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_audposition(EXP_PyObjectPlus *self,
                                          const struct EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_gain(EXP_PyObjectPlus *self,
                                   const struct EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_pitch(EXP_PyObjectPlus *self,
                                    const struct EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_type(EXP_PyObjectPlus *self,
                                   const struct EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_sound(EXP_PyObjectPlus *self,
                                    const struct EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_playbackManager(EXP_PyObjectPlus *self,
                                    const struct EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_catkey(EXP_PyObjectPlus *self,
                                    const struct EXP_PYATTRIBUTE_DEF *attrdef);

  

#endif /* WITH_PYTHON */
};

#endif /* __KX_SPEAKER_H__ */
