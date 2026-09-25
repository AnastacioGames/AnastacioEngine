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

/** \file KX_AnimationEvent.h
 *  \ingroup ketsji
 */

#ifndef __KX_ANIMATION_EVENT_H__
#define __KX_ANIMATION_EVENT_H__

#include "EXP_Value.h"

#include <string>
#include <utility>
#include <vector>

class KX_AnimationEvent : public EXP_Value
{
	Py_Header

private:
	/// Empty when the event has no action assigned.
	std::string m_actionName;
	/// Converted AnimationEventTrigger list: <trigger frame, custom argument>.
	std::vector<std::pair<int, std::string>> m_triggers;
	/// Python function to call, as "module.function". Empty when not set.
	std::string m_pythonEvent;

	/// For logic bricks: last fired trigger and how many times each trigger fired.
	int m_lastTriggerIndex;
	std::vector<unsigned int> m_triggerFireCounts;
	unsigned int m_fireCount;

#ifdef WITH_PYTHON
	/// Strong reference to the resolved Python function, nullptr when unset or not found.
	PyObject *m_pyEventFunction;
#endif // WITH_PYTHON

public:
	KX_AnimationEvent(const std::string& actionName, const std::vector<std::pair<int, std::string>>& triggers,
	                  const std::string& pythonEvent);
	KX_AnimationEvent(const KX_AnimationEvent& other);
	virtual ~KX_AnimationEvent();

	virtual std::string GetName();

	unsigned int GetTriggerCount() const;
	int GetTrigger(int index) const;
	const char *GetCustomArg(int index) const;

	const std::string& GetActionName() const;
	const std::string& GetPythonEventName() const;

	/// Record that a trigger was reached, for the logic bricks.
	void Fire(int triggerIndex);
	int GetLastTriggerIndex() const;
	/// Times the trigger fired, or all triggers together when triggerIndex is -1.
	unsigned int GetFireCount(int triggerIndex) const;

#ifdef WITH_PYTHON
	PyObject *GetPyEventFunction() const;

	static PyObject *pyattr_get_triggers(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);

#endif // WITH_PYTHON
};

#endif  // __KX_ANIMATION_EVENT_H__
