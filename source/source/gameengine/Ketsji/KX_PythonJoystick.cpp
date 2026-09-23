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

/** \file gameengine/Ketsji/KX_PythonJoystick.cpp
 *  \ingroup ketsji
 */

#include "KX_PythonJoystick.h"
#include "SCA_IInputDevice.h"

#include "DEV_Joystick.h"

//#include "GHOST_C-api.h"

/* ------------------------------------------------------------------------- */
/* Native functions                                                          */
/* ------------------------------------------------------------------------- */

KX_PythonJoystick::KX_PythonJoystick(DEV_Joystick *joystick, int joyindex)
    : m_joystick(joystick), m_joyindex(joyindex)
{
#ifdef WITH_PYTHON
  m_event_dict = PyDict_New();
#endif
  // Populate Joystick Inputs
  for (int i = 0; i < KX_PythonJoystick::MAX_BUTTONS; ++i) {
    m_joystickInputsTable[i] = SCA_InputEvent(i);
  }
}

KX_PythonJoystick::~KX_PythonJoystick()
{
  for (int i = 0; i < KX_PythonJoystick::MAX_BUTTONS; ++i) {
    m_joystickInputsTable[i].InvalidateProxy();
  }

#ifdef WITH_PYTHON
  PyDict_Clear(m_event_dict);
  Py_DECREF(m_event_dict);
#endif
}

std::string KX_PythonJoystick::GetName()
{
  return m_joystick->GetName();
}

SCA_InputEvent& KX_PythonJoystick::GetJoyStickInput(KX_PythonJoystick::JOYSTICK_EnumInputs inputcode)
{
  return m_joystickInputsTable[inputcode];
}

// Handle this way because we cannot pass the current input method to the joysticks
void KX_PythonJoystick::UpdateJoystickEvents() 
{
  const int button_number = JOYBUT_MAX;
  const int start_joystick_inputs = KX_PythonJoystick::BEGINJOYSTICK + 1;

  for (int i = 0; i < button_number; i++) {
    SCA_InputEvent &event = m_joystickInputsTable[start_joystick_inputs + i];
    
    // ACTIVATED in last frame
    if (event.Find(SCA_InputEvent::JUSTACTIVATED)) {
      event.m_queue.pop_back();
    }

    // Button Pressed
    if (m_joystick->aButtonPressIsPositive(i)) {
      if (!event.Find(SCA_InputEvent::ACTIVE)) {
        if (event.m_status.size() > 0)
          event.m_status.pop_back();
        event.m_status.push_back(SCA_InputEvent::ACTIVE);
        event.m_queue.push_back(SCA_InputEvent::JUSTACTIVATED);
      }
    }
    // Button Released ...
    else if (event.Find(SCA_InputEvent::ACTIVE)) {
      // Set Released
      event.m_queue.push_back(SCA_InputEvent::JUSTRELEASED);
      event.m_status.pop_back();
    }
    // JUSTRELEASED
    else if (event.Find(SCA_InputEvent::JUSTRELEASED)) {
      event.m_queue.pop_back();
      event.m_status.push_back(SCA_InputEvent::NONE);
    }
  }
}

int KX_PythonJoystick::GetAxisValue(int axis_index) {
    return m_joystick->GetAxisPosition(axis_index);
}

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python functions                                                          */
/* ------------------------------------------------------------------------- */

/* Integration hooks ------------------------------------------------------- */
PyTypeObject KX_PythonJoystick::Type = {
    PyVarObject_HEAD_INIT(nullptr, 0)
    "KX_PythonJoystick",
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
    &EXP_PyObjectPlus::Type,
    0, 0, 0, 0, 0, 0,
    py_base_new
};

PyMethodDef KX_PythonJoystick::Methods[] = {
    EXP_PYMETHODTABLE_NOARGS(KX_PythonJoystick, startVibration),
    EXP_PYMETHODTABLE_NOARGS(KX_PythonJoystick, stopVibration),
    {nullptr, nullptr}  // Sentinel
};

PyAttributeDef KX_PythonJoystick::Attributes[] = {
    EXP_PYATTRIBUTE_RO_FUNCTION("numButtons", KX_PythonJoystick, pyattr_get_num_x),
    EXP_PYATTRIBUTE_RO_FUNCTION("numHats", KX_PythonJoystick, pyattr_get_num_x),
    EXP_PYATTRIBUTE_RO_FUNCTION("numAxis", KX_PythonJoystick, pyattr_get_num_x),
    EXP_PYATTRIBUTE_RO_FUNCTION("activeButtons", KX_PythonJoystick, pyattr_get_active_buttons),
    EXP_PYATTRIBUTE_RO_FUNCTION("hatValues", KX_PythonJoystick, pyattr_get_hat_values),
    EXP_PYATTRIBUTE_RO_FUNCTION("axisValues", KX_PythonJoystick, pyattr_get_axis_values),
    EXP_PYATTRIBUTE_RO_FUNCTION("inputs", KX_PythonJoystick, pyattr_get_inputs),
    EXP_PYATTRIBUTE_RO_FUNCTION("name", KX_PythonJoystick, pyattr_get_name),
    EXP_PYATTRIBUTE_INT_RW("duration", 0, INT_MAX, true, KX_PythonJoystick, m_duration),
    EXP_PYATTRIBUTE_FLOAT_RW("strengthLeft", 0.0, 1.0, KX_PythonJoystick, m_strengthLeft),
    EXP_PYATTRIBUTE_FLOAT_RW("strengthRight", 0.0, 1.0, KX_PythonJoystick, m_strengthRight),
    EXP_PYATTRIBUTE_RO_FUNCTION("isVibrating", KX_PythonJoystick, pyattr_get_isVibrating),
    EXP_PYATTRIBUTE_RO_FUNCTION("hasVibration", KX_PythonJoystick, pyattr_get_hasVibration),
    EXP_PYATTRIBUTE_NULL  // Sentinel
};

// Use one function for numAxis, numButtons, and numHats
PyObject *KX_PythonJoystick::pyattr_get_num_x(EXP_PyObjectPlus *self_v,
                                               const EXP_PYATTRIBUTE_DEF *attrdef)
{
  if (attrdef->m_name == "numButtons") {
    return PyLong_FromLong(JOYBUT_MAX);
  }
  else if (attrdef->m_name == "numAxis") {
    return PyLong_FromLong(JOYAXIS_MAX);
  }
  else if (attrdef->m_name == "numHats") {
    EXP_ShowDeprecationWarning("KX_PythonJoystick.numHats", "KX_PythonJoystick.numButtons");
    return PyLong_FromLong(0);
  }

  // If we got here, we have a problem...
  PyErr_SetString(PyExc_AttributeError, "invalid attribute");
  return nullptr;
}

PyObject *KX_PythonJoystick::pyattr_get_active_buttons(EXP_PyObjectPlus *self_v,
                                                        const EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_PythonJoystick *self = static_cast<KX_PythonJoystick *>(self_v);

  const int button_number = JOYBUT_MAX;

  PyObject *list = PyList_New(0);
  PyObject *value;

  for (int i = 0; i < button_number; i++) {
    if (self->m_joystick->aButtonPressIsPositive(i)) {
      value = PyLong_FromLong(i);
      PyList_Append(list, value);
      Py_DECREF(value);
    }
  }

  /* XXX return list adapted to new names (A, B, X, Y, START, etc) */
  return list;
}

PyObject *KX_PythonJoystick::pyattr_get_hat_values(EXP_PyObjectPlus *self_v,
                                                    const EXP_PYATTRIBUTE_DEF *attrdef)
{
  EXP_ShowDeprecationWarning("KX_PythonJoystick.hatValues", "KX_PythonJoystick.activeButtons");
  return PyList_New(0);
}

PyObject *KX_PythonJoystick::pyattr_get_axis_values(EXP_PyObjectPlus *self_v,
                                                     const EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_PythonJoystick *self = static_cast<KX_PythonJoystick *>(self_v);

  int axis_index = JOYAXIS_MAX;
  PyObject *list = PyList_New(axis_index);
  int position;

  while (axis_index--) {
    position = self->GetAxisValue(axis_index);

    // We get back a range from -32768 to 32767, so we use an if here to
    // get a perfect -1.0 to 1.0 mapping. Some oddball system might have an
    // actual min of -32767 for shorts, so we use SHRT_MIN/MAX to be safe.
    if (position < 0) {
      PyList_SET_ITEM(list, axis_index, PyFloat_FromDouble(position / ((double)-SHRT_MIN)));
    }
    else {
      PyList_SET_ITEM(list, axis_index, PyFloat_FromDouble(position / (double)SHRT_MAX));
    }
  }

  return list;
}

PyObject *KX_PythonJoystick::pyattr_get_inputs(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_PythonJoystick *self = static_cast<KX_PythonJoystick *>(self_v);

  for (int i = KX_PythonJoystick::BEGINJOYSTICK; i <= KX_PythonJoystick::ENDJOYSTICK; i++) {
    SCA_InputEvent &input = self->GetJoyStickInput((KX_PythonJoystick::JOYSTICK_EnumInputs)i);

    PyObject *key = PyLong_FromLong(i);

    PyDict_SetItem(self->m_event_dict, key, input.GetProxy());

    Py_DECREF(key);
  }

  Py_INCREF(self->m_event_dict);

  return self->m_event_dict;
}

PyObject *KX_PythonJoystick::pyattr_get_name(EXP_PyObjectPlus *self_v,
                                              const EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_PythonJoystick *self = static_cast<KX_PythonJoystick *>(self_v);

  return PyUnicode_FromStdString(self->m_joystick->GetName());
}

EXP_PYMETHODDEF_DOC_NOARGS(KX_PythonJoystick,
                           startVibration,
                           "startVibration()\n"
                           "\tStarts the joystick vibration.\n")
{
  if (m_joystick && m_joystick->GetRumbleSupport()) {
    m_joystick->RumblePlay(m_strengthLeft, m_strengthRight, m_duration);
  }

  Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC_NOARGS(KX_PythonJoystick,
                           stopVibration,
                           "StopVibration()\n"
                           "\tStops the joystick vibration.\n")
{
  if (m_joystick && m_joystick->GetRumbleSupport()) {
    m_joystick->RumbleStop();
  }

  Py_RETURN_NONE;
}

PyObject *KX_PythonJoystick::pyattr_get_isVibrating(EXP_PyObjectPlus *self_v,
                                                     const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_PythonJoystick *self = static_cast<KX_PythonJoystick *>(self_v);

  if (!(self->m_joystick) && !(self->m_joystick->GetRumbleSupport())) {
    return Py_False;
  }

  return PyBool_FromLong(self->m_joystick->GetRumbleStatus());
}

PyObject *KX_PythonJoystick::pyattr_get_hasVibration(EXP_PyObjectPlus *self_v,
                                                      const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_PythonJoystick *self = static_cast<KX_PythonJoystick *>(self_v);

  if (!(self->m_joystick)) {
    return Py_False;
  }

  return PyBool_FromLong(self->m_joystick->GetRumbleSupport());
}

#endif  // WITH_PYTHON
