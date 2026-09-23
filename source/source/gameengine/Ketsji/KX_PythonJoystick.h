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
 * Contributor(s): Mitchell Stokes.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file SCA_PythonJoystick.h
 *  \ingroup ketsji
 */

#pragma once

#include "SCA_InputEvent.h"

#include "EXP_Value.h"

class KX_PythonJoystick : public EXP_Value {
  Py_Header private : class DEV_Joystick *m_joystick;
  int m_joyindex;
  float m_strengthLeft;
  float m_strengthRight;
  int m_duration;

  PyObject *m_event_dict;

 public:
  /* Same structure as SCA_EnumInputs, we cannot use SCA_EnumInputs because of the way it manipulates,
   * controls can have more than one instance. */
  enum JOYSTICK_EnumInputs {
    BEGINJOYSTICK,

    // Keep sync with SDL!
    A,
    B,
    X,
    Y,
    BACK,
    GUIDE,
    START,
    LEFTSTICK,
    RIGHTSTICK,
    LEFTSHOULDER,
    RIGHTSHOUDER,
    DPADUP,
    DPADDOWN,
    DPADLEFT,
    DPADRIGHT,

	ENDJOYSTICK,

    MAX_BUTTONS,

	// Only For Input System, out of MAX_BUTTONS
	JOY_LEFTX = 100,
	JOY_LEFTY = 101,
	JOY_RIGHTX = 102,
	JOY_RIGHTY = 103,

	TRIGGER_LEFT = 104,
	TRIGGER_RIGHT = 105
  };

 protected:
  /// Table of all possible input.
  SCA_InputEvent m_joystickInputsTable[KX_PythonJoystick::MAX_BUTTONS];

 public:

  KX_PythonJoystick(class DEV_Joystick *joystick, int joyindex);
  virtual ~KX_PythonJoystick();

  virtual std::string GetName();
  virtual SCA_InputEvent& GetJoyStickInput(KX_PythonJoystick::JOYSTICK_EnumInputs inputcode);

  /* Manage joystick buttons (released, active .. etc) */
  virtual void UpdateJoystickEvents();

  virtual int GetAxisValue(int axis_index);

#ifdef WITH_PYTHON
  static PyObject *pyattr_get_num_x(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_active_buttons(EXP_PyObjectPlus *self_v,
                                             const EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_hat_values(EXP_PyObjectPlus *self_v,
                                         const EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_axis_values(EXP_PyObjectPlus *self_v,
                                          const EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_inputs(EXP_PyObjectPlus *self_v,
                                          const EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_name(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);

  EXP_PYMETHOD_DOC_NOARGS(KX_PythonJoystick, startVibration);
  EXP_PYMETHOD_DOC_NOARGS(KX_PythonJoystick, stopVibration);

  static PyObject *pyattr_get_isVibrating(EXP_PyObjectPlus *self_v,
                                          const struct EXP_PYATTRIBUTE_DEF *attrdef);
  static PyObject *pyattr_get_hasVibration(EXP_PyObjectPlus *self_v,
                                           const struct EXP_PYATTRIBUTE_DEF *attrdef);
#endif
};
