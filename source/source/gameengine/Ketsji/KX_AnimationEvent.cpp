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
 * Contributor(s): Range Engine.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Ketsji/KX_AnimationEvent.cpp
 *  \ingroup ketsji
 */

#include "KX_AnimationEvent.h"
#include "EXP_Value.h"
#include "EXP_PythonCallBack.h"

KX_AnimationEvent::KX_AnimationEvent(const char *actionName, std::vector<std::pair<int, const char*>> *triggers, std::vector<int> *alreadyTriggered, const char *pythonEvent)
	:EXP_Value(),
	m_actionName(actionName),
	m_triggers(triggers),
	m_alreadyTriggered(alreadyTriggered),
	m_pythonEvent(pythonEvent),
	m_lastTriggerIndex(-1),
	m_pyEventFunction(nullptr)
{
	/* Get the Python function and store it in m_pyEventFunction, 
	/* so we can call it as many times as we want, but with less performance cost. */
	PyObject *module = nullptr, *function = nullptr;

	if (pythonEvent != nullptr) {

		std::string mod_path = GetPythonEventName(); /* just for storage, use C style string access */
		std::string function_string;

		// Resolve module path, same in SCA_PythonController
		const int pos = mod_path.rfind('.');
		if (pos != std::string::npos) {
			function_string = mod_path.substr(pos + 1);
			mod_path = mod_path.substr(0, pos);
		}

		module = PyImport_ImportModule(mod_path.c_str());
		if (!module) {
			EXP_ReportPythonDiagnostic("animation.event.import", mod_path.c_str());
			PyErr_Print();
			PyErr_Clear();

			return;
		}
		function = PyObject_GetAttrString(module, function_string.c_str());
		if (!function) {
			EXP_ReportPythonDiagnostic("animation.event.function", function_string.c_str());
			PyErr_Print();
			PyErr_Clear();
			Py_DECREF(module);

			return;
		}

		m_pyEventFunction = function;

		Py_DECREF(module);
		Py_DECREF(function);
	}
}

KX_AnimationEvent::~KX_AnimationEvent()
{
}

std::string KX_AnimationEvent::GetName()
{
	return "KX_AnimationEvent";
}

unsigned int KX_AnimationEvent::GetTriggerCount() const
{
	return m_triggers->size();
}

int KX_AnimationEvent::GetTrigger(int index) const
{
	if (index >= 0 && index < GetTriggerCount()) {
		return (*m_triggers)[index].first;
	}
	return -1;
}

const char *KX_AnimationEvent::GetCustomArg(int index) const
{
	return (*m_triggers)[index].second;
}

std::string KX_AnimationEvent::GetActionName()
{
	return m_actionName;
}

std::vector<std::pair<int, const char*>> *KX_AnimationEvent::GetTriggers()
{
	return m_triggers;
}

std::vector<int> *KX_AnimationEvent::GetAlreadyTriggereds()
{
	return m_alreadyTriggered;
}

void KX_AnimationEvent::SetAlreadyTriggereds(std::vector<int> *alreadyTriggered)
{
	m_alreadyTriggered = alreadyTriggered;
}

const char *KX_AnimationEvent::GetPythonEventName()
{
	return m_pythonEvent;
}

const int KX_AnimationEvent::GetLastTriggerIndex()
{
	return m_lastTriggerIndex;
}

void KX_AnimationEvent::SetLastTriggerIndex(const int triggerIndex)
{
	m_lastTriggerIndex = triggerIndex;
}

#ifdef WITH_PYTHON

PyObject *KX_AnimationEvent::GetPyEventFunction() {
	return m_pyEventFunction;
}

PyTypeObject KX_AnimationEvent::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_AnimationEvent",
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
	&EXP_Value::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_AnimationEvent::Methods[] = {
	{nullptr, nullptr} // Sentinel
};

PyAttributeDef KX_AnimationEvent::Attributes[] = {
	EXP_PYATTRIBUTE_RO_FUNCTION("triggers", KX_AnimationEvent, pyattr_get_triggers),
	EXP_PYATTRIBUTE_NULL  // Sentinel
};

PyObject *KX_AnimationEvent::pyattr_get_triggers(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_AnimationEvent *self = static_cast<KX_AnimationEvent *>(self_v);

	int size = self->GetTriggerCount();

	PyObject *list = PyList_New(size);
	
	for (int i = 0; i < self->m_triggers->size(); i++)
		PyList_SetItem(list, i, PyLong_FromLong(self->GetTrigger(i)));
	
	return list;
}
#endif //WITH_PYTHON
