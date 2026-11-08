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

/** \file gameengine/Ketsji/KX_MicrophoneSensor.cpp
 *  \ingroup ketsji
 */

#include "KX_MicrophoneSensor.h"
#include "KX_AudioManager.h"
#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "SCA_IObject.h"
#include "EXP_FloatValue.h"
#include "DNA_sensor_types.h"

#include <algorithm>

static KX_AudioManager *microphone_sensor_audio()
{
	KX_KetsjiEngine *engine = KX_GetActiveEngine();
	return engine ? engine->GetAudioManager() : nullptr;
}

KX_MicrophoneSensor::KX_MicrophoneSensor(SCA_EventManager *eventmgr, SCA_IObject *gameobj, int mode,
                                         float threshold, float hold, const std::string& propname)
	:SCA_ISensor(gameobj, eventmgr),
	m_mode(mode),
	m_threshold(threshold),
	m_hold(hold),
	m_propname(propname),
	m_acquired(false)
{
	Init();
}

KX_MicrophoneSensor::~KX_MicrophoneSensor()
{
	if (m_acquired) {
		KX_AudioManager *audio = microphone_sensor_audio();
		if (audio) {
			audio->MicrophoneRelease();
		}
	}
}

void KX_MicrophoneSensor::Init()
{
	m_voiceLevel = m_voicePeak = 0.0f;
	m_quiet = 0.0f;
	m_armed = true;
	m_positive = false;
}

EXP_Value *KX_MicrophoneSensor::GetReplica()
{
	KX_MicrophoneSensor *replica = new KX_MicrophoneSensor(*this);
	replica->m_acquired = false;
	replica->ProcessReplica();
	replica->Init();
	return replica;
}

bool KX_MicrophoneSensor::IsPositiveTrigger()
{
	return m_invert ? !m_positive : m_positive;
}

bool KX_MicrophoneSensor::Evaluate()
{
	const bool reset = m_reset && m_level;

	KX_AudioManager *audio = microphone_sensor_audio();
	if (audio && !m_acquired) {
		// Only sensors that run turn the microphone on (not the ones of hidden layers).
		audio->MicrophoneAcquire();
		m_acquired = true;
	}
	m_voiceLevel = audio ? audio->MicrophoneLevel() : 0.0f;
	m_voicePeak = audio ? audio->MicrophonePeak() : 0.0f;

	if (!m_propname.empty()) {
		EXP_Value *prop = GetParent()->GetProperty(m_propname);
		if (prop) {
			EXP_FloatValue *value = new EXP_FloatValue(m_voiceLevel);
			prop->SetValue(value);
			value->Release();
		}
	}

	KX_KetsjiEngine *engine = KX_GetActiveEngine();
	const float dt = engine ? 1.0f / (float)std::max(engine->GetTicRate(), 1.0) : 1.0f / 60.0f;
	if (m_voiceLevel > m_threshold) {
		m_quiet = 0.0f;
	}
	else {
		m_quiet += dt;
	}

	bool positive = false;
	switch (m_mode) {
		case SENS_MIC_TALKING:
			positive = (m_voiceLevel > m_threshold) || (m_positive && m_quiet < m_hold);
			break;
		case SENS_MIC_PEAK:
			// One tick on: the next Evaluate turns it off (a pulse).
			if (m_armed && m_voicePeak > m_threshold) {
				positive = true;
				m_armed = false;
			}
			else if (m_voicePeak < m_threshold * 0.7f) {
				m_armed = true;
			}
			break;
		case SENS_MIC_SILENCE:
			positive = (m_quiet >= m_hold);
			break;
		default:
			break;
	}

	const bool changed = (positive != m_positive);
	m_positive = positive;
	return changed || reset;
}

#ifdef WITH_PYTHON

PyTypeObject KX_MicrophoneSensor::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_MicrophoneSensor",
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
	&SCA_ISensor::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_MicrophoneSensor::Methods[] = {
	{nullptr, nullptr} // Sentinel
};

PyAttributeDef KX_MicrophoneSensor::Attributes[] = {
	EXP_PYATTRIBUTE_INT_RW("mode", SENS_MIC_TALKING, SENS_MIC_SILENCE, true, KX_MicrophoneSensor, m_mode),
	EXP_PYATTRIBUTE_FLOAT_RW("threshold", 0.0f, 1.0f, KX_MicrophoneSensor, m_threshold),
	EXP_PYATTRIBUTE_FLOAT_RW("hold", 0.0f, 60.0f, KX_MicrophoneSensor, m_hold),
	EXP_PYATTRIBUTE_STRING_RW("propName", 0, 64, false, KX_MicrophoneSensor, m_propname),
	EXP_PYATTRIBUTE_FLOAT_RO("level", KX_MicrophoneSensor, m_voiceLevel),
	EXP_PYATTRIBUTE_FLOAT_RO("peak", KX_MicrophoneSensor, m_voicePeak),
	EXP_PYATTRIBUTE_NULL // Sentinel
};

#endif
