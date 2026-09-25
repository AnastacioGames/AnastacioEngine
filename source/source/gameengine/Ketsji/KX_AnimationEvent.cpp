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

KX_AnimationEvent::KX_AnimationEvent(const std::string& actionName, const std::vector<std::pair<int, std::string>>& triggers,
                                     const std::string& pythonEvent)
	:EXP_Value(),
	m_actionName(actionName),
	m_triggers(triggers),
	m_pythonEvent(pythonEvent),
	m_lastTriggerIndex(-1),
	m_triggerFireCounts(triggers.size(), 0),
	m_fireCount(0)
#ifdef WITH_PYTHON
	,
	m_pyEventFunction(nullptr)
#endif  // WITH_PYTHON
{
#ifdef WITH_PYTHON
	/* Resolve the Python function once and keep a reference to it,
	 * so it can be called many times with less performance cost. */
	if (m_pythonEvent.empty()) {
		return;
	}

	std::string mod_path = m_pythonEvent;
	std::string function_string;

	// Resolve module path, same in SCA_PythonController
	const size_t pos = mod_path.rfind('.');
	if (pos != std::string::npos) {
		function_string = mod_path.substr(pos + 1);
		mod_path = mod_path.substr(0, pos);
	}

	PyObject *module = PyImport_ImportModule(mod_path.c_str());
	if (!module) {
		EXP_ReportPythonDiagnostic("animation.event.import", mod_path.c_str());
		PyErr_Print();
		PyErr_Clear();
		return;
	}

	PyObject *function = PyObject_GetAttrString(module, function_string.c_str());
	Py_DECREF(module);
	if (!function) {
		EXP_ReportPythonDiagnostic("animation.event.function", function_string.c_str());
		PyErr_Print();
		PyErr_Clear();
		return;
	}

	if (!PyCallable_Check(function)) {
		EXP_ReportPythonDiagnostic("animation.event.callable", m_pythonEvent.c_str());
		Py_DECREF(function);
		return;
	}

	// Keep the new reference from PyObject_GetAttrString, released in the destructor.
	m_pyEventFunction = function;
#endif  // WITH_PYTHON
}

KX_AnimationEvent::KX_AnimationEvent(const KX_AnimationEvent& other)
	:EXP_Value(other),
	m_actionName(other.m_actionName),
	m_triggers(other.m_triggers),
	m_pythonEvent(other.m_pythonEvent),
	m_lastTriggerIndex(-1),
	m_triggerFireCounts(other.m_triggers.size(), 0),
	m_fireCount(0)
#ifdef WITH_PYTHON
	,
	m_pyEventFunction(other.m_pyEventFunction)
#endif  // WITH_PYTHON
{
	// Don't share the Python proxy of the original event.
	ProcessReplica();

#ifdef WITH_PYTHON
	Py_XINCREF(m_pyEventFunction);
#endif  // WITH_PYTHON
}

KX_AnimationEvent::~KX_AnimationEvent()
{
#ifdef WITH_PYTHON
	Py_XDECREF(m_pyEventFunction);
#endif  // WITH_PYTHON
}

std::string KX_AnimationEvent::GetName()
{
	return "KX_AnimationEvent";
}

unsigned int KX_AnimationEvent::GetTriggerCount() const
{
	return m_triggers.size();
}

int KX_AnimationEvent::GetTrigger(int index) const
{
	if (index >= 0 && index < (int)m_triggers.size()) {
		return m_triggers[index].first;
	}
	return -1;
}

const char *KX_AnimationEvent::GetCustomArg(int index) const
{
	if (index >= 0 && index < (int)m_triggers.size()) {
		return m_triggers[index].second.c_str();
	}
	return "";
}

const std::string& KX_AnimationEvent::GetActionName() const
{
	return m_actionName;
}

const std::string& KX_AnimationEvent::GetPythonEventName() const
{
	return m_pythonEvent;
}

void KX_AnimationEvent::Fire(int triggerIndex)
{
	if (triggerIndex < 0 || triggerIndex >= (int)m_triggerFireCounts.size()) {
		return;
	}

	m_lastTriggerIndex = triggerIndex;
	++m_triggerFireCounts[triggerIndex];
	++m_fireCount;
}

int KX_AnimationEvent::GetLastTriggerIndex() const
{
	return m_lastTriggerIndex;
}

unsigned int KX_AnimationEvent::GetFireCount(int triggerIndex) const
{
	if (triggerIndex == -1) {
		return m_fireCount;
	}
	if (triggerIndex >= 0 && triggerIndex < (int)m_triggerFireCounts.size()) {
		return m_triggerFireCounts[triggerIndex];
	}
	return 0;
}

#ifdef WITH_PYTHON

PyObject *KX_AnimationEvent::GetPyEventFunction() const
{
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

	const unsigned int size = self->GetTriggerCount();
	PyObject *list = PyList_New(size);

	for (unsigned int i = 0; i < size; i++) {
		PyList_SET_ITEM(list, i, PyLong_FromLong(self->GetTrigger(i)));
	}

	return list;
}
#endif //WITH_PYTHON
