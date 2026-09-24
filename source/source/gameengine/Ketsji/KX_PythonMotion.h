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
 * Contributor(s): none yet.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_PythonMotion.h
 *  \ingroup gamelogic
 */

#ifndef __KX_PythonMotion_H__
#define __KX_PythonMotion_H__

#include "EXP_PyObjectPlus.h"

/**
 * Device motion sensors (gyroscope, accelerometer, orientation) exposed as bge.logic.motion.
 *
 * The Web runtime reads DeviceMotionEvent/DeviceOrientationEvent in the page (see package-web.py),
 * already rotated to screen axes: x to the right of the screen, y to the top, z out of the screen.
 * Other platforms have no sensor source yet and report available = False with zero values.
 */
class KX_PythonMotion : public EXP_PyObjectPlus
{
	Py_Header
public:
	/// Layout of the buffer filled by the platform source.
	enum {
		AVAILABLE = 0,
		GYRO = 1,        // rad/s, 3 floats
		ACCEL = 4,       // m/s^2 including gravity, 3 floats
		GRAVITY = 7,     // m/s^2, 3 floats
		ORIENTATION = 10, // alpha, beta, gamma in degrees, 3 floats
		DATA_SIZE = 13
	};

private:
	float m_data[DATA_SIZE];
	/// Gravity direction (normalized, screen x/y) taken as neutral by calibrate().
	float m_neutral[2];

	void Refresh();

public:
	KX_PythonMotion();
	virtual ~KX_PythonMotion();

#ifdef WITH_PYTHON
	EXP_PYMETHOD_NOARGS(KX_PythonMotion, Calibrate);

	static PyObject *pyattr_get_available(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_gyroscope(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_accelerometer(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_orientation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_tilt(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
#endif
};

#endif  /* __KX_PythonMotion_H__ */
