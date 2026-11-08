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

/** \file gameengine/Ketsji/KX_VoiceActuator.cpp
 *  \ingroup ketsji
 */

#include "KX_VoiceActuator.h"
#include "KX_AudioManager.h"
#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "CM_Message.h"

static KX_AudioManager *voice_audio()
{
	KX_KetsjiEngine *engine = KX_GetActiveEngine();
	return engine ? engine->GetAudioManager() : nullptr;
}

KX_VoiceActuator::KX_VoiceActuator(SCA_IObject *gameobj, int mode, const std::string& slot, const std::string& preset,
                                   float amount, float volume, float maxSeconds, bool reverb)
	:SCA_IActuator(gameobj, KX_ACT_VOICE),
	m_mode(mode),
	m_slot(slot.empty() ? "voice" : slot),
	m_preset(preset.empty() ? "NONE" : preset),
	m_amount(amount),
	m_volume(volume),
	m_maxSeconds(maxSeconds),
	m_reverb(reverb),
	m_recording(false),
	m_voice(0),
	m_live(false),
	m_acquired(false)
{
}

KX_VoiceActuator::~KX_VoiceActuator()
{
	KX_AudioManager *audio = voice_audio();
	if (!audio) {
		return;
	}
	if (m_recording) {
		FinishRecording();
	}
	if (m_live) {
		audio->StopLive();
	}
	if (m_acquired) {
		audio->MicrophoneRelease();
	}
}

EXP_Value *KX_VoiceActuator::GetReplica()
{
	KX_VoiceActuator *replica = new KX_VoiceActuator(*this);
	replica->ProcessReplica();
	return replica;
}

void KX_VoiceActuator::ProcessReplica()
{
	m_recording = false;
	m_voice = 0;
	m_live = false;
	m_acquired = false;
	SCA_IActuator::ProcessReplica();
}

void KX_VoiceActuator::Acquire()
{
	KX_AudioManager *audio = voice_audio();
	if (audio && !m_acquired) {
		audio->MicrophoneAcquire();
		m_acquired = true;
	}
}

void KX_VoiceActuator::FinishRecording()
{
	m_recording = false;
	KX_AudioManager *audio = voice_audio();
	if (audio && audio->MicrophoneIsRecording()) {
		audio->MicrophoneRecordStop(m_slot);
	}
}

void KX_VoiceActuator::Deactivate()
{
	// The controllers left the active state: a recording is kept, the live voice stops.
	if (m_recording) {
		FinishRecording();
		SetEndReason(END_CANCELLED);
	}
	if (m_live) {
		KX_AudioManager *audio = voice_audio();
		if (audio) {
			audio->StopLive();
		}
		m_live = false;
	}
	if (m_voice) {
		m_voice = 0;
		SetEndReason(END_CANCELLED);
	}
	SCA_IActuator::Deactivate();
}

bool KX_VoiceActuator::Update()
{
	const bool positive = m_posevent;
	const bool negative = IsNegativeEvent();
	RemoveAllEvents();

	KX_AudioManager *audio = voice_audio();
	if (!audio) {
		return false;
	}

	switch (m_mode) {
		case KX_VOICE_RECORD:
		{
			if (positive && !m_recording) {
				Acquire();
				m_recording = audio->MicrophoneRecordStart();
				if (!m_recording) {
					SetEndReason(END_FAILED);
					return false;
				}
			}
			if (!m_recording) {
				return false;
			}
			const bool timeUp = m_maxSeconds > 0.0f && audio->MicrophoneRecordingSeconds() >= m_maxSeconds;
			// Without Max Seconds it records while the sensor is on (walkie-talkie).
			const bool released = m_maxSeconds <= 0.0f && negative;
			if (timeUp || released || !audio->MicrophoneIsRecording()) {
				const bool mine = audio->MicrophoneIsRecording();
				FinishRecording();
				SetEndReason(mine ? END_FINISHED : END_CANCELLED);
				return false;
			}
			return true;
		}
		case KX_VOICE_PLAY:
		{
			if (positive) {
				if (m_voice) {
					audio->StopVoiceById(m_voice);
				}
				m_voice = audio->PlayRecording(m_slot, m_preset, m_amount, m_volume, m_reverb);
				if (!m_voice) {
					SetEndReason(END_FAILED);
					return false;
				}
			}
			if (!m_voice) {
				return false;
			}
			if (!audio->IsVoicePlaying(m_voice)) {
				m_voice = 0;
				SetEndReason(END_FINISHED);
				return false;
			}
			return true;
		}
		case KX_VOICE_LIVE:
		{
			if (positive) {
				Acquire();
				m_live = audio->PlayLive(m_preset, m_amount, m_volume, m_reverb);
				if (!m_live) {
					SetEndReason(END_FAILED);
					return false;
				}
			}
			if (m_live && (negative || !audio->IsLive())) {
				if (negative) {
					audio->StopLive();
				}
				m_live = false;
				return false;
			}
			return m_live;
		}
		case KX_VOICE_STOP:
		{
			if (positive) {
				audio->StopLive();
			}
			return false;
		}
		case KX_VOICE_SAVE:
		{
			if (positive && !audio->SaveRecording(m_slot, m_slot + ".wav")) {
				CM_LogicBrickWarning(this, "could not save the recording \"" << m_slot << "\"");
				SetEndReason(END_FAILED);
			}
			return false;
		}
		default:
			return false;
	}
}

#ifdef WITH_PYTHON

PyTypeObject KX_VoiceActuator::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_VoiceActuator",
	sizeof(EXP_PyObjectPlus_Proxy),
	0,
	py_base_dealloc,
	0,
	0,
	0,
	0,
	py_base_repr,
	0, 0, 0, 0, 0, 0, 0, 0, 0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	0, 0, 0, 0, 0, 0, 0,
	Methods,
	0,
	0,
	&SCA_IActuator::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_VoiceActuator::Methods[] = {
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_VoiceActuator::Attributes[] = {
	EXP_PYATTRIBUTE_INT_RW("mode", KX_VOICE_RECORD, KX_VOICE_MAX - 1, true, KX_VoiceActuator, m_mode),
	EXP_PYATTRIBUTE_STRING_RW("slot", 1, 64, false, KX_VoiceActuator, m_slot),
	EXP_PYATTRIBUTE_STRING_RW("effect", 1, 32, false, KX_VoiceActuator, m_preset),
	EXP_PYATTRIBUTE_FLOAT_RW("amount", 0.0f, 1.0f, KX_VoiceActuator, m_amount),
	EXP_PYATTRIBUTE_FLOAT_RW("volume", 0.0f, 4.0f, KX_VoiceActuator, m_volume),
	EXP_PYATTRIBUTE_FLOAT_RW("maxSeconds", 0.0f, 600.0f, KX_VoiceActuator, m_maxSeconds),
	EXP_PYATTRIBUTE_BOOL_RW("useReverb", KX_VoiceActuator, m_reverb),
	EXP_PYATTRIBUTE_NULL //Sentinel
};

#endif  // WITH_PYTHON
