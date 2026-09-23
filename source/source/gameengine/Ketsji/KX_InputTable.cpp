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

/** \file gameengine/Ketsji/KX_InputTable.cpp
 *  \ingroup gamelogic
 */

#include "KX_InputTable.h"
#include "KX_InputSystem.h"
#include "KX_PythonInit.h"

#include "KX_DebugMode.h"
#include "KX_KetsjiEngine.h"
#include "KX_Globals.h"

#include "EXP_ListWrapper.h"

#include "CM_Message.h"

#include <algorithm>

KX_InputTable::KX_InputTable(const char *name, const char *type, const char *ctrlType, 
	cJSON *bindings, cJSON *processors, SCA_IInputDevice *inputDevice)
    : m_name(""),
	m_inputMap({})
{
	// copy the name because the pointer will be deleted after the inputMap file is closed
	strcpy(m_name, name);

	m_inputMap.type = GetTableType(type);
	m_inputMap.controlType = GetControlType(ctrlType);
	m_inputMap.bindings = GetBindings(bindings, inputDevice);
	m_inputMap.processors = GetProcessors(processors);
}

KX_InputTable::TableType KX_InputTable::GetTableType(const char *type)
{
	TableType tableType = TableType::BUTTON;
	if (strcmp(type, "BUTTON") == 0)
        tableType = TableType::BUTTON;
	else if (strcmp(type, "VALUE") == 0)
		tableType = TableType::VALUE;

	return tableType;
}

KX_InputTable::ControlType KX_InputTable::GetControlType(const char *ctrlType)
{
	ControlType controlType = ControlType::INT;
	if (strcmp(ctrlType, "VECTOR1D") == 0)
        controlType = ControlType::VECTOR1D;
	else if (strcmp(ctrlType, "VECTOR2D") == 0)
		controlType = ControlType::VECTOR2D;
	else if (strcmp(ctrlType, "VECTOR3D") == 0)
		controlType = ControlType::VECTOR3D;

	return controlType;
}

SCA_IInputDevice::SCA_EnumInputs KX_InputTable::GetGameEngineInput(const std::string &value_str)
{
	SCA_IInputDevice::SCA_EnumInputs value = static_cast<SCA_IInputDevice::SCA_EnumInputs>(std::stoi(value_str));
	return value;
}

KX_PythonJoystick::JOYSTICK_EnumInputs *KX_InputTable::AllocateJoystickInput(const std::string& value_str) {
    KX_PythonJoystick::JOYSTICK_EnumInputs value = static_cast<KX_PythonJoystick::JOYSTICK_EnumInputs>(std::stoi(value_str));
    KX_PythonJoystick::JOYSTICK_EnumInputs *enumInput = new KX_PythonJoystick::JOYSTICK_EnumInputs(value);

    return enumInput;
}

std::vector<KX_InputTable::Binding*> KX_InputTable::GetBindings(cJSON *bindings, SCA_IInputDevice *inputDevice)
{
	std::vector<KX_InputTable::Binding*> binds;

	/* Binding Struct must be initialized with two cJSON_ArrayForEach interactions */
	/* One to define the peripheral type and another for the binds */
	Binding *binding;

	cJSON *inputTable = nullptr;
	cJSON_ArrayForEach(inputTable, bindings) {
		cJSON *bind = nullptr;
		binding = new Binding(); // create a new Binding for the next iteration
		binding->peripheralType = {};
		binding->joystick_index = -1;
		binding->sensitivity = -1;

		cJSON_ArrayForEach(bind, inputTable) {

			// PERIPHERALTYPE Section
			if (strcmp(bind->string, "PERIPHERALTYPE") == 0) {
				// partial initialize Binding struct
				strcpy(binding->name, inputTable->string);

				cJSON *peripheralType = cJSON_GetObjectItem(bind, "TYPE");
				cJSON *joystick_index = cJSON_GetObjectItem(bind, "INDEX");
				cJSON *sensitivity = cJSON_GetObjectItem(bind, "SENSITIVITY");

				// check if the value ​​are OK
				if (!peripheralType || !joystick_index || !sensitivity) {
					CM_Error("InputSystem " << "Peripheral type from '" << inputTable->string << "' not initialized correctly!");
					break;
				}

				binding->peripheralType = GetPeripheralType(peripheralType->valuestring);
				binding->joystick_index = joystick_index->valueint;
				binding->sensitivity = sensitivity->valuedouble;

				// We will finalize the struct in the next iteration
				continue;
			}

			// check if PERIPHERALTYPE has initialized
			if (binding->joystick_index == -1) {
				CM_Error("InputSystem " << "missing PERIPHERALTYPE from '" << inputTable->string << "'!");
				break;
			}

			BindType bindType = GetBindType(bind->string);

			cJSON *up_value;
			cJSON *down_value;
			cJSON *left_value;
			cJSON *right_value;
			cJSON *forward_value;
			cJSON *backward_value;

			// Finalize Binding struct
			binding->type = bindType;

			// To avoid problems, initially all binds are nullptr
			binding->UP = nullptr;
			binding->DOWN = nullptr;
			binding->LEFT = nullptr;
			binding->RIGHT = nullptr;
			binding->FORWARD = nullptr;
			binding->BACKWARD = nullptr;

			binding->JOY_UP = nullptr;
			binding->JOY_DOWN = nullptr;
			binding->JOY_LEFT = nullptr;
			binding->JOY_RIGHT = nullptr;
			binding->JOY_FORWARD = nullptr;
			binding->JOY_BACKWARD = nullptr;

			switch (bindType) 
			{
				case BINDING:
					/* In the case of simple bind, we will use the UP value to validate this input */
					/* we will compare it when checking with the "bindType" */
					up_value = cJSON_GetObjectItem(bind, "BUTTON");

					// check if the values ​​are OK
					if (!up_value) {
						CM_Error("InputSystem " << "missing BINDING value from '" << bind->string << "'!");
						break;
					}
					
					if (binding->peripheralType != PeripheralType::JOYSTICK) {
						binding->UP = &inputDevice->GetInput(GetGameEngineInput(up_value->valuestring));
					}
					else {
						binding->JOY_UP = AllocateJoystickInput(up_value->valuestring);
					}

					break;
				case COMPOSITEPADS:
				case COMPOSITEPADS3D:
					up_value = cJSON_GetObjectItem(bind, "UP");
					down_value = cJSON_GetObjectItem(bind, "DOWN");
					left_value = cJSON_GetObjectItem(bind, "LEFT");
					right_value = cJSON_GetObjectItem(bind, "RIGHT");

					// check if the values ​​are OK
					if (!up_value || !down_value || !left_value || !right_value) {
						CM_Error("InputSystem " << "missing COMPOSITEPADS values from '" << bind->string << "'!");
						break;
					}

					if (binding->peripheralType != PeripheralType::JOYSTICK) {
						binding->UP = &inputDevice->GetInput(GetGameEngineInput(up_value->valuestring));
						binding->DOWN = &inputDevice->GetInput(GetGameEngineInput(down_value->valuestring));
						binding->LEFT = &inputDevice->GetInput(GetGameEngineInput(left_value->valuestring));
						binding->RIGHT = &inputDevice->GetInput(GetGameEngineInput(right_value->valuestring));
					}
					else {
						// We cannot deliver input directly because the joystick depends on whether they are connected/disconnected
						binding->JOY_UP = AllocateJoystickInput(up_value->valuestring);
						binding->JOY_DOWN = AllocateJoystickInput(down_value->valuestring);
						binding->JOY_LEFT = AllocateJoystickInput(left_value->valuestring);
						binding->JOY_RIGHT = AllocateJoystickInput(right_value->valuestring);
					}

					if (bindType == COMPOSITEPADS3D) {
						forward_value = cJSON_GetObjectItem(bind, "FORWARD");
						backward_value = cJSON_GetObjectItem(bind, "BACKWARD");

						// check if the values ​​are OK
						if (!forward_value || !backward_value) {
							CM_Error("InputSystem " << "missing COMPOSITEPADS3D values from '" << bind->string << "'!");
							break;
						}

						if (binding->peripheralType != PeripheralType::JOYSTICK) {
							binding->FORWARD = &inputDevice->GetInput(GetGameEngineInput(forward_value->valuestring));
							binding->BACKWARD = &inputDevice->GetInput(GetGameEngineInput(backward_value->valuestring));
						}
						else {
							binding->JOY_FORWARD = AllocateJoystickInput(forward_value->valuestring);
							binding->JOY_BACKWARD = AllocateJoystickInput(backward_value->valuestring);
						}
					}
					break;
			}

			/* let's allocate memory to reference all SCA_InputEvent to check evaluation time (.released .. etc) */
			/* I think iteration is faster, less memory but more speed */
			binding->iterateEvents = {
				binding->UP, binding->DOWN, binding->LEFT, binding->RIGHT, binding->FORWARD, binding->BACKWARD
			};
			binding->iterateEventsJoystick = {
				binding->JOY_UP, binding->JOY_DOWN, binding->JOY_LEFT, binding->JOY_RIGHT, binding->JOY_FORWARD, binding->JOY_BACKWARD
			};

			binds.push_back(binding);
		}
	}

	return binds;
}

std::vector<KX_InputTable::Processor> KX_InputTable::GetProcessors(cJSON *processors)
{
	std::vector<KX_InputTable::Processor> processors_list;

	cJSON *process = nullptr;
	cJSON_ArrayForEach(process, processors) {
		ProcessorType processorType = GetProcessorType(process->string);

		cJSON *value;

		Processor processor;
		processor.processorType	= processorType;

		switch (processorType) 
		{
			case INVERT:
				value = cJSON_GetObjectItem(process, "X"); // X
				processor.value_X = value->valuedouble;
				break;
			case INVERT2D:
				value = cJSON_GetObjectItem(process, "X"); // X
				processor.value_X = value->valuedouble;

				value = cJSON_GetObjectItem(process, "Y"); // Y
				processor.value_Y = value->valuedouble;
				break;
			case INVERT3D:
				value = cJSON_GetObjectItem(process, "X"); // X
				processor.value_X = value->valuedouble;

				value = cJSON_GetObjectItem(process, "Y"); // Y
				processor.value_Y = value->valuedouble;

				value = cJSON_GetObjectItem(process, "Z"); // Z
				processor.value_Z = value->valuedouble;
				break;

			case SCALE:
				value = cJSON_GetObjectItem(process, "X"); // X
				processor.value_X = value->valuedouble;
				break;
			case SCALE2D:
				value = cJSON_GetObjectItem(process, "X"); // X
				processor.value_X = value->valuedouble;

				value = cJSON_GetObjectItem(process, "Y"); // Y
				processor.value_Y = value->valuedouble;
				break;
			case SCALE3D:
				value = cJSON_GetObjectItem(process, "X"); // X
				processor.value_X = value->valuedouble;

				value = cJSON_GetObjectItem(process, "Y"); // Y
				processor.value_Y = value->valuedouble;

				value = cJSON_GetObjectItem(process, "Z"); // Z
				processor.value_Z = value->valuedouble;
				break;

			case LERP:
				value = cJSON_GetObjectItem(process, "X"); // X
				processor.value_X = value->valuedouble;
				break;

			case DEADZONE:
				value = cJSON_GetObjectItem(process, "X"); // X
				processor.value_X = value->valuedouble;

				value = cJSON_GetObjectItem(process, "Y"); // Y
				processor.value_Y = value->valuedouble;
				break;
		}

		processors_list.push_back(processor);
	}


	return processors_list;
}

KX_InputTable::PeripheralType KX_InputTable::GetPeripheralType(const char *peripheralType)
{
  PeripheralType peripheral = PeripheralType::KEYBOARD;
  if (strcmp(peripheralType, "KEYBOARD") == 0)
		peripheral = PeripheralType::KEYBOARD;
  else if (strcmp(peripheralType, "MOUSE") == 0)
		peripheral = PeripheralType::MOUSE;
  else if (strcmp(peripheralType, "JOYSTICK") == 0)
		peripheral = PeripheralType::JOYSTICK;

  return peripheral;
}

KX_InputTable::BindType KX_InputTable::GetBindType(const char *bindType)
{
	BindType bind = BindType::BINDING;
	if (strcmp(bindType, "BINDING") == 0)
        bind = BindType::BINDING;
	else if (strcmp(bindType, "COMPOSITEPADS") == 0)
		bind = BindType::COMPOSITEPADS;
	else if (strcmp(bindType, "COMPOSITEPADS3D") == 0)
		bind = BindType::COMPOSITEPADS3D;

	return bind;
}

KX_InputTable::ProcessorType KX_InputTable::GetProcessorType(const char *processorType)
{
	ProcessorType processor = ProcessorType::LERP;
	if (strcmp(processorType, "INVERTVALUES") == 0)
        processor = ProcessorType::INVERT;
	else if (strcmp(processorType, "INVERTVALUES2D") == 0)
        processor = ProcessorType::INVERT2D;
	else if (strcmp(processorType, "INVERTVALUES3D") == 0)
        processor = ProcessorType::INVERT3D;

	else if (strcmp(processorType, "SCALEVALUES") == 0)
        processor = ProcessorType::SCALE;
	else if (strcmp(processorType, "SCALEVALUES2D") == 0)
        processor = ProcessorType::SCALE2D;
	else if (strcmp(processorType, "SCALEVALUES3D") == 0)
        processor = ProcessorType::SCALE3D;

	else if (strcmp(processorType, "LERP") == 0)
        processor = ProcessorType::LERP;
	else if (strcmp(processorType, "DEADZONE") == 0)
        processor = ProcessorType::DEADZONE;

	return processor;
}

std::string KX_InputTable::GetName()
{
	return "KX_InputTable";
}

void KX_InputTable::process_invert(float result[3], int size, float x, float y, float z) {
    for (int i = 0; i < size; ++i) {
		switch (i) {
			case 0: // X
				if (x == 1.0f && result[i] != 0.0f) // for some reason X returns -0.0f if 0.0f.
					result[i] = -result[i];
				break;
			case 1: // Y
				if (y == 1.0f) result[i] = -result[i];
				break;
			case 2: // Z
				if (z == 1.0f) result[i] = -result[i];
				break;
		}
        
    }
}

void KX_InputTable::process_scale(float result[3], int size, float factor_x, float factor_y, float factor_z) {
    for (int i = 0; i < size; ++i) {
        result[i] *= result[i] * i == 0 ? factor_x : i == 1 ? factor_y : factor_z;
    }
}

void KX_InputTable::process_lerp(float result[3], float target[3], float t)
{
	for (int i = 0; i < 3; ++i) {
		result[i] += (target[i] - result[i]) * t;
		result[i] = std::round(result[i] * 1000.0f) / 1000.0f;  // Round

		// check if it is very close to zero
		if (std::fabs(result[i]) < 0.01f) {
		  result[i] = 0.0f;
		}
	}
}

void KX_InputTable::process_dead_zone(float result[3], float min, float max) {
	for (int i = 0; i < 3; ++i) {
		float value = result[i];
		if (std::abs(value) < min) {
			result[i] = 0.0f;
		}
		else if (value > max) {
			result[i] = (value - max) / (1.0f - max);
		}
		else if (value < -max) {
			result[i] = (value + max) / (1.0f - max);
		}
		else {
			if (value > 0) {
				result[i] = (value - min) / (max - min);
			} else {
				result[i] = (value + min) / (max - min);
			}
		}
	}
}

bool KX_InputTable::EvaluateInputEvent(Binding *bind, SCA_InputEvent::SCA_EnumInputs type)
{
	bool result = false;

	if (bind->peripheralType != PeripheralType::JOYSTICK) {
		for (SCA_InputEvent *input : bind->iterateEvents) {

			if (!input) continue;

			result = input->Find(type);
			// True, break
			if (result) {
				break;
			}
		}
	} else {
		// Joystick
		for (int i = 0; i < bind->iterateEventsJoystick.size(); i++) {
			KX_PythonJoystick::JOYSTICK_EnumInputs *enumInput = bind->iterateEventsJoystick[i];
			KX_PythonJoystick *joystick = (KX_PythonJoystick *)getPythonJoystick(bind->joystick_index);

			if (!enumInput) continue;
			if (!joystick) continue;

			SCA_InputEvent *input = &joystick->GetJoyStickInput(*enumInput);

			if (!input) continue;

			// Evaluate
			if (*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_LEFTX &&
				*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_LEFTY &&
				*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_RIGHTX &&
				*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_RIGHTY &&
				*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::TRIGGER_LEFT &&
				*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::TRIGGER_RIGHT) {

				result = input->Find(type);
			}

			// True, break
			if (result) {
				break;
			}
		}
	}

	return result;
}

#ifdef WITH_PYTHON

PyTypeObject KX_InputTable::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_InputTable",
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
	0, 0, 0,
	0,
	0, 0, 0,
	Methods,
	0,
	0,
	&EXP_PyObjectPlus::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_InputTable::Methods[] = {
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_InputTable::Attributes[] = {
	EXP_PYATTRIBUTE_RO_FUNCTION("released", KX_InputTable, pyattr_get_released),
	EXP_PYATTRIBUTE_RO_FUNCTION("active", KX_InputTable, pyattr_get_active),
	EXP_PYATTRIBUTE_RO_FUNCTION("activated", KX_InputTable, pyattr_get_activated),
	EXP_PYATTRIBUTE_RO_FUNCTION("values", KX_InputTable, pyattr_get_values),
	EXP_PYATTRIBUTE_NULL //Sentinel
};


PyObject *KX_InputTable::pyattr_get_released(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_InputTable *self = static_cast<KX_InputTable *>(self_v);

	if (KX_GetActiveEngine()->GetDebugMode()->imgui_blockInputEvents) {
		return PyBool_FromLong(false);
	}

	bool result = false;

	for (Binding *bind : self->m_inputMap.bindings) {
		result = self->EvaluateInputEvent(bind, SCA_InputEvent::JUSTRELEASED);

		if (result)
		  break;
	}
	
	return PyBool_FromLong(result);
}

PyObject *KX_InputTable::pyattr_get_active(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_InputTable *self = static_cast<KX_InputTable *>(self_v);

	if (KX_GetActiveEngine()->GetDebugMode()->imgui_blockInputEvents) {
		return PyBool_FromLong(false);
	}

	bool result = false;

	for (Binding *bind : self->m_inputMap.bindings) {
		result = self->EvaluateInputEvent(bind, SCA_InputEvent::ACTIVE);

		if (result) break;
	}
	
	return PyBool_FromLong(result);
}

PyObject *KX_InputTable::pyattr_get_activated(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_InputTable *self = static_cast<KX_InputTable *>(self_v);

	if (KX_GetActiveEngine()->GetDebugMode()->imgui_blockInputEvents) {
		return PyBool_FromLong(false);
	}

	bool result = false;

	for (Binding *bind : self->m_inputMap.bindings) {
		result = self->EvaluateInputEvent(bind, SCA_InputEvent::JUSTACTIVATED);

		if (result) break;
	}
	
	return PyBool_FromLong(result);
}

PyObject *KX_InputTable::pyattr_get_values(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_InputTable *self = static_cast<KX_InputTable *>(self_v);
	
	if (KX_GetActiveEngine()->GetDebugMode()->imgui_blockInputEvents) {
		PyObject *ret = PyTuple_New(self->m_inputMap.controlType);

		if (self->m_inputMap.controlType == ControlType::VECTOR2D) {
			PyTuple_SET_ITEM(ret, 0, PyFloat_FromDouble(0.0f));
			PyTuple_SET_ITEM(ret, 1, PyFloat_FromDouble(0.0f));
		}
		if (self->m_inputMap.controlType == ControlType::VECTOR3D) {
			PyTuple_SET_ITEM(ret, 0, PyFloat_FromDouble(0.0f));
			PyTuple_SET_ITEM(ret, 1, PyFloat_FromDouble(0.0f));
			PyTuple_SET_ITEM(ret, 2, PyFloat_FromDouble(0.0f));
		}
		return ret;
	}

	// Only VALUE type for now.
	if (self->m_inputMap.type != TableType::VALUE) {
		return PyBool_FromLong(false);
	}

	float result[3] = {0.0f, 0.0f, 0.0f};
	bool allowDEADZONE = true; // Only used in DEADZONE processor

	for (Binding *bind : self->m_inputMap.bindings) {
		if (bind->peripheralType != PeripheralType::JOYSTICK) {
			for (int i = 0; i < bind->iterateEvents.size(); i++) {
				SCA_InputEvent *input = bind->iterateEvents[i];
				if (!input) continue;

				int value = input->Find(SCA_InputEvent::ACTIVE) ? 1.0f : 0.0f;

				if (!value) continue;

				// Only keyboard, mouse input needs to be treated as position (X or Y)
				if (input->m_type != SCA_IInputDevice::MOUSEX && input->m_type != SCA_IInputDevice::MOUSEY) {
					self->evaluate_values(result, i, value);
				}
				else {
					KX_PythonMouse *mouse = KX_GetActiveEngine()->GetPythonMouse();

					int index = input->m_type == SCA_IInputDevice::MOUSEX ? 0 : 1;
					
					float value = mouse->GetDeltaPosition(false)[index] * bind->sensitivity;
					result[index] = index == 1 ? value : -value; // invert X value

					mouse->Recenter(false);

					allowDEADZONE = false; // Do not allow the use of DEADZONE with mouse position inputs
				}
			}
		}
		else {
			// Joystick
			for (int i = 0; i < bind->iterateEvents.size(); i++) {
				KX_PythonJoystick::JOYSTICK_EnumInputs *enumInput = bind->iterateEventsJoystick[i];
				KX_PythonJoystick *joystick = (KX_PythonJoystick *)getPythonJoystick(bind->joystick_index);

				if (!enumInput) continue;
				if (!joystick) continue;

				SCA_InputEvent *input = &joystick->GetJoyStickInput(*enumInput);

				if (!input) continue;

				// Evaluate
				if (*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_LEFTX &&
					*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_LEFTY &&
					*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_RIGHTX &&
					*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_RIGHTY &&
					*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::TRIGGER_LEFT &&
					*enumInput != KX_PythonJoystick::JOYSTICK_EnumInputs::TRIGGER_RIGHT) {

					int value = input->Find(SCA_InputEvent::ACTIVE) ? 1.0f : 0.0f;

					if (!value) continue;

					self->evaluate_values(result, i, value);
				}
				else {
					int index = *enumInput == KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_LEFTX ? 0 : 
								*enumInput == KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_LEFTY ? 1 : 
								*enumInput == KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_RIGHTX ? 2 :
								*enumInput == KX_PythonJoystick::JOYSTICK_EnumInputs::JOY_RIGHTY ? 3 :
								*enumInput == KX_PythonJoystick::JOYSTICK_EnumInputs::TRIGGER_LEFT ? 4 : 5;
					bool pass;

					int index_result = (i == 2 || i == 3) ? 0 : (i < 2) ? 1 : 2;

					float position = joystick->GetAxisValue(index);
					position = (position < 0) ? position / ((double)-SHRT_MIN) : position / ((double)SHRT_MAX);
					position *= bind->sensitivity; // apply sensitivity

					// This checks whether the axis is theoretically stopped, if no, the result must be in addition
					// so as not to disturb other types of inputs, but it must not interfere with the final result!
					pass = std::abs(position) >= 0.05f;

					if (!pass) {
						result[index_result] += (index == 0 || index == 2 || index == 4 || index == 5) ? position : -position;
					}
					else {
						result[index_result] = (index == 0 || index == 2 || index == 4 || index == 5) ? position : -position;
					}
				}
				
			}
		}
	}

	/* Evaluate Processors */
	for (Processor process : self->m_inputMap.processors) {
		switch(process.processorType) {
			case INVERT:
				self->process_invert(result, 1, process.value_X, 0.0f, 0.0f);
				break;
			case INVERT2D:
				self->process_invert(result, 2, process.value_X, process.value_Y, 0.0f);
				break;
			case INVERT3D:
				self->process_invert(result, 3, process.value_X, process.value_Y, process.value_Z);
				break;

			case SCALE:
				self->process_scale(result, 1, process.value_X, 1.0f, 1.0f);
				break;
			case SCALE2D:
				self->process_scale(result, 2, process.value_X, process.value_Y, 1.0f);
				break;
			case SCALE3D:
				self->process_scale(result, 3, process.value_X, process.value_Y, process.value_Z);
				break;

			case LERP:
				self->process_lerp(result, self->m_lastValues, process.value_X);
				break;
			case DEADZONE:
				if (allowDEADZONE) {
					self->process_dead_zone(result, process.value_X, process.value_Y);
				}
				break;
		}
	}

	// set last values
	self->m_lastValues[0] = result[0];
	self->m_lastValues[1] = result[1];
	self->m_lastValues[2] = result[2];

	/* Python return */

	// ControlType VECTOR1D format
	if (self->m_inputMap.controlType == ControlType::VECTOR1D) {
		return PyFloat_FromDouble(result[0] + result[1] + result[2]);
	}
	
	// ControlType VECTOR format 
	PyObject *ret = PyTuple_New(self->m_inputMap.controlType);

	if (self->m_inputMap.controlType == ControlType::VECTOR2D) {
		PyTuple_SET_ITEM(ret, 0, PyFloat_FromDouble(result[0]));
		PyTuple_SET_ITEM(ret, 1, PyFloat_FromDouble(result[1] + result[2]));
	}
	if (self->m_inputMap.controlType == ControlType::VECTOR3D) {
		PyTuple_SET_ITEM(ret, 0, PyFloat_FromDouble(result[0]));
		PyTuple_SET_ITEM(ret, 1, PyFloat_FromDouble(result[1]));
		PyTuple_SET_ITEM(ret, 2, PyFloat_FromDouble(result[2]));
	}
	return ret;
}

#endif  // WITH_PYTHON
