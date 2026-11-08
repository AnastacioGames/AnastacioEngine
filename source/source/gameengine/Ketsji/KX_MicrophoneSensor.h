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

/** \file KX_MicrophoneSensor.h
 *  \ingroup ketsji
 *  \brief Listens to the microphone: talking, a loud sound (clap/shout) or silence.
 */

#ifndef __KX_MICROPHONESENSOR_H__
#define __KX_MICROPHONESENSOR_H__

#include "SCA_ISensor.h"

#include <string>

class KX_MicrophoneSensor : public SCA_ISensor
{
	Py_Header

	int m_mode;
	float m_threshold;
	/// Seconds: Talking stays on after the voice stops / Silence needs this long quiet.
	float m_hold;
	/// Optional property that receives the level every tick.
	std::string m_propname;

	float m_voiceLevel;
	float m_voicePeak;
	/// Seconds below the threshold.
	float m_quiet;
	/// Peak mode: a new pulse only after the sound fell below 70% of the threshold.
	bool m_armed;
	bool m_positive;
	/// MicrophoneAcquire() was called (the microphone stays on while the sensor exists).
	bool m_acquired;

public:
	KX_MicrophoneSensor(SCA_EventManager *eventmgr, SCA_IObject *gameobj, int mode, float threshold, float hold,
	                    const std::string& propname);
	virtual ~KX_MicrophoneSensor();
	virtual EXP_Value *GetReplica();

	virtual bool Evaluate();
	virtual bool IsPositiveTrigger();
	virtual void Init();
};

#endif  // __KX_MICROPHONESENSOR_H__
