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
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_VoiceActuator.h
 *  \ingroup ketsji
 *  \brief Records the microphone and plays voices with effects (Range.audio recordings).
 */

#ifndef __KX_VOICEACTUATOR_H__
#define __KX_VOICEACTUATOR_H__

#include "SCA_IActuator.h"

#include <string>

class KX_VoiceActuator : public SCA_IActuator
{
	Py_Header

public:
	/// Same values as ACT_VOICE_* in DNA_actuator_types.h.
	enum Mode {
		KX_VOICE_RECORD = 0,
		KX_VOICE_PLAY,
		KX_VOICE_LIVE,
		KX_VOICE_STOP,
		KX_VOICE_SAVE,
		KX_VOICE_MAX
	};

private:
	int m_mode;
	std::string m_slot;
	std::string m_preset;
	float m_amount;
	float m_volume;
	float m_maxSeconds;
	bool m_reverb;

	/// Record: this actuator started the recording in progress.
	bool m_recording;
	/// Play: voice being watched to report Finished (0: none).
	unsigned int m_voice;
	/// Live: this actuator turned the live voice on.
	bool m_live;
	/// MicrophoneAcquire() was called.
	bool m_acquired;

	void Acquire();
	void FinishRecording();

public:
	KX_VoiceActuator(SCA_IObject *gameobj, int mode, const std::string& slot, const std::string& preset,
	                 float amount, float volume, float maxSeconds, bool reverb);
	virtual ~KX_VoiceActuator();

	virtual EXP_Value *GetReplica();
	virtual void ProcessReplica();
	virtual bool Update();
	virtual void Deactivate();
};

#endif  // __KX_VOICEACTUATOR_H__
