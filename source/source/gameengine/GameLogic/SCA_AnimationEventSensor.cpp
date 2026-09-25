/*
 * Actuator sensor
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
 */

/** \file gameengine/GameLogic/SCA_AnimationEventSensor.cpp
 *  \ingroup gamelogic
 */


#include <stddef.h>

#include <iostream>
#include "SCA_AnimationEventSensor.h"
#include "SCA_EventManager.h"
#include "SCA_LogicManager.h"

#include "CM_Message.h"

SCA_AnimationEventSensor::SCA_AnimationEventSensor(class SCA_EventManager *eventmgr,
														 SCA_IObject *gameobj,
														 const int eventIndex,
														 const int triggerIndex,
														 const bool triggerAll,
														 KX_AnimationEvent *event)
	:SCA_ISensor(gameobj, eventmgr),
	m_eventIndex(eventIndex),
	m_triggerIndex(triggerIndex),
	m_triggerAll(triggerAll),
	m_event(event)
{
	Init();
}

void SCA_AnimationEventSensor::Init()
{
	m_lastresult = false;
	m_reset = true;

	if (m_event) {
		m_lastFireCount = m_event->GetFireCount(m_triggerAll ? -1 : m_triggerIndex);
	}
	else {
		m_lastFireCount = 0;
		CM_LogicBrickWarning(this, "sensor " << m_name << " does not have a valid event index!");
	}
}

EXP_Value *SCA_AnimationEventSensor::GetReplica()
{
	SCA_AnimationEventSensor *replica = new SCA_AnimationEventSensor(*this);
	// m_range_expr must be recalculated on replica!
	replica->ProcessReplica();
	replica->Init();

	return replica;
}

void SCA_AnimationEventSensor::ReParent(SCA_IObject *parent)
{
	SCA_ISensor::ReParent(parent);
}

bool SCA_AnimationEventSensor::IsPositiveTrigger()
{
	bool result = m_lastresult;
	if (m_invert) {
		result = !result;
	}

	return result;
}



SCA_AnimationEventSensor::~SCA_AnimationEventSensor()
{
}



bool SCA_AnimationEventSensor::Evaluate()
{
	if (!m_event) {
		return false;
	}

	// Positive for one logic frame each time the watched trigger (or any trigger) fired since the
	// last evaluation, so repeated fires of the same trigger in a loop are all reported.
	const unsigned int fireCount = m_event->GetFireCount(m_triggerAll ? -1 : m_triggerIndex);
	const bool result = (fireCount != m_lastFireCount);
	m_lastFireCount = fireCount;

	const bool reset = m_reset && m_level;
	m_reset = false;

	if (result != m_lastresult) {
		m_lastresult = result;
		return true;
	}
	return reset;
}

void SCA_AnimationEventSensor::Update()
{
	// Nothing
}

int SCA_AnimationEventSensor::GetEventIndex() const
{
	return m_eventIndex;
}

void SCA_AnimationEventSensor::SetEvent(KX_AnimationEvent *event)
{
	m_event = event;
	m_lastFireCount = (m_event) ? m_event->GetFireCount(m_triggerAll ? -1 : m_triggerIndex) : 0;
}

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python functions                                                          */
/* ------------------------------------------------------------------------- */

/* Integration hooks ------------------------------------------------------- */
PyTypeObject SCA_AnimationEventSensor::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"SCA_AnimationEventSensor",
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

PyMethodDef SCA_AnimationEventSensor::Methods[] = {
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef SCA_AnimationEventSensor::Attributes[] = {
	EXP_PYATTRIBUTE_NULL    //Sentinel
};

#endif // WITH_PYTHON

/* eof */
