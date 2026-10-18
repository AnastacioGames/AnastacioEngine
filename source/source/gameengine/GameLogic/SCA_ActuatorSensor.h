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

#ifndef __SCA_ACTUATORSENSOR_H__
#define __SCA_ACTUATORSENSOR_H__

/** \file SCA_ActuatorSensor.h
 *  \ingroup gamelogic
 */

#include "SCA_ISensor.h"
#include "SCA_IActuator.h"

class SCA_ActuatorSensor : public SCA_ISensor
{
	Py_Header
	std::string		m_checkactname;
	bool			m_lastresult;
	bool			m_midresult;
	/// MODE_ACTIVE or MODE_FINISHED.
	int				m_mode;
	/// Finish count of the actuator seen by the last evaluation (MODE_FINISHED).
	unsigned int	m_lastFinishCount;
 protected:
	SCA_IActuator*	m_actuator;

	void SyncFinishCount();
public:
	enum {
		/// Positive while the actuator is active (original behavior).
		MODE_ACTIVE = 0,
		/// One tick positive pulse after the actuator finished its job.
		MODE_FINISHED = 1
	};

	SCA_ActuatorSensor(class SCA_EventManager* eventmgr,
					  SCA_IObject* gameobj,
					  const std::string& actname,
					  int mode = MODE_ACTIVE);
	
	virtual ~SCA_ActuatorSensor();
	virtual EXP_Value* GetReplica();
	virtual void Init();
	virtual bool Evaluate();
	virtual bool	IsPositiveTrigger();
	virtual void	ReParent(SCA_IObject* parent);
	void Update();

#ifdef WITH_PYTHON

	/* --------------------------------------------------------------------- */
	/* Python interface ---------------------------------------------------- */
	/* --------------------------------------------------------------------- */

	static int CheckActuator(EXP_PyObjectPlus *self, const PyAttributeDef*);
	
#endif  /* WITH_PYTHON */
};

#endif  /* __SCA_ACTUATORSENSOR_H__ */
