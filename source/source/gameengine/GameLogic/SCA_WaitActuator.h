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

/** \file SCA_WaitActuator.h
 *  \ingroup gamelogic
 *  \brief Actuator that counts a time and finishes, to chain bricks with the Actuator sensor in Finished mode.
 */

#ifndef __SCA_WAITACTUATOR_H__
#define __SCA_WAITACTUATOR_H__

#include "SCA_IActuator.h"

class SCA_WaitActuator : public SCA_IActuator
{
	Py_Header

	/// Seconds of simulation time.
	float m_duration;
	/// A positive pulse while waiting starts the count again.
	bool m_restart;

	bool m_waiting;
	double m_startTime;

public:
	SCA_WaitActuator(SCA_IObject *gameobj, float duration, bool restart);
	virtual ~SCA_WaitActuator();

	virtual EXP_Value *GetReplica();
	virtual void ProcessReplica();
	virtual bool Update(double curtime);
	virtual void Deactivate();

#ifdef WITH_PYTHON
	static PyObject *pyattr_get_elapsed(EXP_PyObjectPlus *self, const EXP_PYATTRIBUTE_DEF *attrdef);
#endif

private:
	double m_lastTime;
};

#endif  // __SCA_WAITACTUATOR_H__
