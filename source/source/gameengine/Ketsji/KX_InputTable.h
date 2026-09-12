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
 * Contributor(s): Range Engine
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_InputTable.h
 *  \ingroup ketsji
 */

#ifndef __KX_INPUTTABLE_H__
#define __KX_INPUTTABLE_H__

#include "EXP_Value.h"

#include "SCA_IInputDevice.h"
#include "KX_PythonJoystick.h"

#include <vector>
#include <array>

#include "cJSON.h"

class KX_InputTable : public EXP_Value
{
Py_Header
public:
	enum TableType {
		BUTTON,
		VALUE,
	};
	enum ControlType {
		INT,
		VECTOR1D,
		VECTOR2D,
		VECTOR3D
	};

	enum PeripheralType {
		KEYBOARD,
		MOUSE,
		JOYSTICK
	};
	enum BindType {
		BINDING,
		COMPOSITEPADS,
		COMPOSITEPADS3D
	};

	struct Binding {
		char name[64];

		PeripheralType peripheralType;
		int joystick_index;
		float sensitivity;
		BindType type;

		SCA_InputEvent *UP;
		SCA_InputEvent *DOWN;
		SCA_InputEvent *LEFT;
		SCA_InputEvent *RIGHT;
		SCA_InputEvent *FORWARD;
		SCA_InputEvent *BACKWARD;

		KX_PythonJoystick::JOYSTICK_EnumInputs *JOY_UP;
		KX_PythonJoystick::JOYSTICK_EnumInputs *JOY_DOWN;
		KX_PythonJoystick::JOYSTICK_EnumInputs *JOY_LEFT;
		KX_PythonJoystick::JOYSTICK_EnumInputs *JOY_RIGHT;
		KX_PythonJoystick::JOYSTICK_EnumInputs *JOY_FORWARD;
		KX_PythonJoystick::JOYSTICK_EnumInputs *JOY_BACKWARD;

		// for loop (faster than alloc/dealloc all time i think)
		std::array<SCA_InputEvent *, 6> iterateEvents; 
		std::array<KX_PythonJoystick::JOYSTICK_EnumInputs *, 6> iterateEventsJoystick;
	};

	enum ProcessorType {
		INVERT,
		INVERT2D,
		INVERT3D,

		SCALE,
		SCALE2D,
		SCALE3D,

		LERP,
		/* For Joysticks */
		DEADZONE
	};

	struct Processor {
		ProcessorType processorType;
		float value_X;
		float value_Y;
		float value_Z;
	};

	struct InputMap {
		TableType type;
		ControlType controlType;
		std::vector<Binding*> bindings;
		std::vector<Processor> processors;
	};

	KX_InputTable(const char *name, const char *type, const char *ctrlType,
		cJSON *bindings, cJSON *processors, SCA_IInputDevice *inputDevice);

	TableType GetTableType(const char *type);
	ControlType GetControlType(const char *ctrlType);

	SCA_IInputDevice::SCA_EnumInputs GetGameEngineInput(const std::string& value_str);
	KX_PythonJoystick::JOYSTICK_EnumInputs *AllocateJoystickInput(const std::string& value_str);
	std::vector<Binding*> GetBindings(cJSON *bindings, SCA_IInputDevice *inputDevice);

	std::vector<Processor> GetProcessors(cJSON *processors);
	PeripheralType GetPeripheralType(const char *peripheralType);
	BindType GetBindType(const char *bindType);
	ProcessorType GetProcessorType(const char *processorType);

	virtual std::string GetName();

	/// Clear status, values and queue but keep status and value from before.
	//void Clear();

	char m_name[64]; // InputTable name
	InputMap m_inputMap;

	float m_lastValues[3] = {0.0f, 0.0f, 0.0f};  // get_values previous values, used in processors.

	/// Processors
	void process_invert(float result[3], int size, float x, float y, float z);
	void process_scale(float result[3], int size, float factor_x, float factor_y, float factor_z);
	void process_lerp(float result[3], float target[3], float t);
	void process_dead_zone(float result[3], float min, float max);

	// This check the button values, whether they were triggered or not
	inline void evaluate_values(float result[3], int i, int value)
	{
		// X
		if (i == 2 || i == 3) {
			result[0] = i == 3 ? value : -value; // LEFT || RIGHT
		}
		// Y
		else if (i < 2) {
			result[1] = i == 0 ? value : -value; // UP || DOWN
		}
		// Z
		else {
			result[2] = i == 4 ? value : -value; // FORWARD || BACKWARD
		}
	};

	// It checks if the key was pressed, released ...
	bool EvaluateInputEvent(Binding *bind, SCA_InputEvent::SCA_EnumInputs type);

#ifdef WITH_PYTHON
	static PyObject *pyattr_get_released(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_active(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_activated(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_values(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
#endif
};

#endif  // __KX_INPUTTABLE_H__

