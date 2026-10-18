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

/** \file gameengine/GameLogic/SCA_ActuatorSensor.cpp
 *  \ingroup gamelogic
 */


#include <stddef.h>

#include <iostream>
#include "SCA_ActuatorSensor.h"
#include "SCA_EventManager.h"
#include "SCA_LogicManager.h"

SCA_ActuatorSensor::SCA_ActuatorSensor(SCA_EventManager *eventmgr,
                                       SCA_IObject *gameobj,
                                       const std::string& actname,
                                       int mode)
	:SCA_ISensor(gameobj, eventmgr),
	m_checkactname(actname),
	m_mode(mode),
	m_lastFinishCount(0)
{
	m_actuator = GetParent()->FindActuator(m_checkactname);
	Init();
}

void SCA_ActuatorSensor::Init()
{
	m_lastresult = m_invert ? true : false;
	m_midresult = false;
	m_reset = true;
	/* completions that happened while the sensor was out of the active state are dropped */
	SyncFinishCount();
}

void SCA_ActuatorSensor::SyncFinishCount()
{
	m_lastFinishCount = m_actuator ? m_actuator->GetFinishCount() : 0;
}

EXP_Value *SCA_ActuatorSensor::GetReplica()
{
	SCA_ActuatorSensor *replica = new SCA_ActuatorSensor(*this);
	// m_range_expr must be recalculated on replica!
	replica->ProcessReplica();
	replica->Init();

	return replica;
}

void SCA_ActuatorSensor::ReParent(SCA_IObject *parent)
{
	m_actuator = parent->FindActuator(m_checkactname);
	SyncFinishCount();
	SCA_ISensor::ReParent(parent);
}

bool SCA_ActuatorSensor::IsPositiveTrigger()
{
	bool result = m_lastresult;
	if (m_invert) {
		result = !result;
	}

	return result;
}



SCA_ActuatorSensor::~SCA_ActuatorSensor()
{
}



bool SCA_ActuatorSensor::Evaluate()
{
	if (m_actuator && m_mode == MODE_FINISHED) {
		/* The actuators run after the sensors, so a completion is seen in the next logic tick.
		 * Several completions between two evaluations give a single pulse. */
		const unsigned int count = m_actuator->GetFinishCount();
		const bool finished = (count != m_lastFinishCount);
		bool reset = m_reset && m_level;

		m_lastFinishCount = count;
		m_reset = false;
		if (finished) {
			/* a completion in consecutive ticks triggers the controllers again */
			m_lastresult = true;
			return true;
		}
		if (m_lastresult) {
			m_lastresult = false;
			return true;
		}
		return (reset) ? true : false;
	}
	if (m_actuator) {
		/* m_midresult keeps the activation seen by Update() in the previous frame: one-shot
		 * actuators (Property, Message, Add Object...) are already inactive here and the
		 * sensor would only report the negative edge. */
		bool result = m_actuator->IsActive() || m_midresult;
		bool reset = m_reset && m_level;

		m_reset = false;
		if (m_lastresult != result) {
			m_lastresult = result;
			return true;
		}
		return (reset) ? true : false;
	}
	return false;
}

void SCA_ActuatorSensor::Update()
{
	if (m_actuator && m_mode == MODE_ACTIVE) {
		m_midresult = m_actuator->IsActive() && !m_actuator->IsNegativeEvent();
	}
}

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python functions                                                          */
/* ------------------------------------------------------------------------- */

/* Integration hooks ------------------------------------------------------- */
PyTypeObject SCA_ActuatorSensor::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"SCA_ActuatorSensor",
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

PyMethodDef SCA_ActuatorSensor::Methods[] = {
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef SCA_ActuatorSensor::Attributes[] = {
	EXP_PYATTRIBUTE_STRING_RW_CHECK("actuator", 0, MAX_PROP_NAME, false, SCA_ActuatorSensor, m_checkactname, CheckActuator),
	EXP_PYATTRIBUTE_INT_RW("mode", MODE_ACTIVE, MODE_FINISHED, true, SCA_ActuatorSensor, m_mode),
	EXP_PYATTRIBUTE_NULL    //Sentinel
};

int SCA_ActuatorSensor::CheckActuator(EXP_PyObjectPlus *self, const PyAttributeDef *)
{
	SCA_ActuatorSensor *sensor = reinterpret_cast<SCA_ActuatorSensor *>(self);
	SCA_IActuator *act = sensor->GetParent()->FindActuator(sensor->m_checkactname);
	if (act) {
		sensor->m_actuator = act;
		sensor->SyncFinishCount();
		return 0;
	}
	PyErr_SetString(PyExc_AttributeError, "string does not correspond to an actuator");
	return 1;
}

#endif // WITH_PYTHON

/* eof */
