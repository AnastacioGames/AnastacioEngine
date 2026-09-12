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

/** \file KX_PythonMouse.h
 *  \ingroup gamelogic
 */

#ifndef __KX_PythonMouse_H__
#define __KX_PythonMouse_H__

#include "EXP_PyObjectPlus.h"

class KX_PythonMouse : public EXP_PyObjectPlus
{
	Py_Header
private:
	class SCA_IInputDevice *m_mouse;
	class RAS_ICanvas *m_canvas;
#ifdef WITH_PYTHON
	PyObject *m_event_dict;
	mt::vec2 *m_mouseDelta;
#endif
public:
	KX_PythonMouse(class SCA_IInputDevice* mouse, class RAS_ICanvas* canvas);
	virtual ~KX_PythonMouse();

	void Show(bool visible);

	/**
	 * Reset Mouse Position to center
	 */
	void Recenter(bool debugModeCamera);

	/**
	 * Get Delta Mouse Position
	 */
	mathfu::vec2 GetDeltaPosition(bool debugModeCamera);

#ifdef WITH_PYTHON
	EXP_PYMETHOD_DOC(KX_PythonMouse, show);
	EXP_PYMETHOD_NOARGS(KX_PythonMouse, Recenter);

	static PyObject *pyattr_get_events(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_inputs(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_active_events(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_active_inputs(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_position(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int       pyattr_set_position(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_deltaPosition(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_visible(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int       pyattr_set_visible(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
#endif
};

#endif  /* __KX_PythonMouse_H__ */
