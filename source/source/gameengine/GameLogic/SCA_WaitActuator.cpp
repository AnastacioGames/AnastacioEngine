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

/** \file gameengine/GameLogic/SCA_WaitActuator.cpp
 *  \ingroup gamelogic
 */

#include "SCA_WaitActuator.h"

SCA_WaitActuator::SCA_WaitActuator(SCA_IObject *gameobj, float duration, bool restart)
	:SCA_IActuator(gameobj, KX_ACT_WAIT),
	m_duration(duration),
	m_restart(restart),
	m_waiting(false),
	m_startTime(0.0),
	m_lastTime(0.0)
{
}

SCA_WaitActuator::~SCA_WaitActuator()
{
}

EXP_Value *SCA_WaitActuator::GetReplica()
{
	SCA_WaitActuator *replica = new SCA_WaitActuator(*this);
	replica->ProcessReplica();
	return replica;
}

void SCA_WaitActuator::ProcessReplica()
{
	SCA_IActuator::ProcessReplica();
	m_waiting = false;
}

bool SCA_WaitActuator::Update(double curtime)
{
	const bool positiveEvent = m_posevent;
	RemoveAllEvents();
	m_lastTime = curtime;

	if (m_waiting && IsNoLink()) {
		// the controllers left the active state: the wait is cancelled
		m_waiting = false;
		SetEndReason(END_CANCELLED);
		return false;
	}

	if (!m_waiting) {
		// negative pulses never start (nor stop) the wait
		if (!positiveEvent) {
			return false;
		}
		m_waiting = true;
		m_startTime = curtime;
	}
	else if (positiveEvent && m_restart) {
		m_startTime = curtime;
	}

	// small tolerance: the logic time advances by a fixed step that is not exact in binary
	if (curtime - m_startTime >= (double)m_duration - 1e-6) {
		m_waiting = false;
		SetEndReason(END_FINISHED);
		return false;
	}

	return true;
}

void SCA_WaitActuator::Deactivate()
{
	// the object is removed (or the actuator is removed from the logic)
	if (m_waiting) {
		m_waiting = false;
		SetEndReason(END_CANCELLED);
	}
	SCA_IActuator::Deactivate();
}

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python functions                                                          */
/* ------------------------------------------------------------------------- */

/* Integration hooks ------------------------------------------------------- */
PyTypeObject SCA_WaitActuator::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"SCA_WaitActuator",
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

PyMethodDef SCA_WaitActuator::Methods[] = {
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef SCA_WaitActuator::Attributes[] = {
	EXP_PYATTRIBUTE_FLOAT_RW("duration", 0.0f, 100000.0f, SCA_WaitActuator, m_duration),
	EXP_PYATTRIBUTE_BOOL_RW("useRestart", SCA_WaitActuator, m_restart),
	EXP_PYATTRIBUTE_BOOL_RO("waiting", SCA_WaitActuator, m_waiting),
	EXP_PYATTRIBUTE_RO_FUNCTION("elapsed", SCA_WaitActuator, pyattr_get_elapsed),
	EXP_PYATTRIBUTE_NULL //Sentinel
};

PyObject *SCA_WaitActuator::pyattr_get_elapsed(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	SCA_WaitActuator *self = static_cast<SCA_WaitActuator *>(self_v);
	return PyFloat_FromDouble(self->m_waiting ? self->m_lastTime - self->m_startTime : 0.0);
}

#endif // WITH_PYTHON
