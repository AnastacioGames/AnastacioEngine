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

/** \file gameengine/Ketsji/KX_AnimationEventManager.cpp
 *  \ingroup ketsji
 */

#include "KX_AnimationEventManager.h"
#include "KX_AnimationEvent.h"
#include "KX_Scene.h"
#include "KX_GameObject.h"

#include "EXP_ListWrapper.h"

#include "BL_BlenderDataConversion.h"
#include "DNA_action_types.h"
#include "DNA_object_types.h"
#include "BLI_listbase.h"

KX_AnimationEventManager::KX_AnimationEventManager(Object *ob)
{
	/* Index 0 of ob->animevents (and of each event->triggers) is a hidden base element
	 * created by the editor, user data starts at index 1. */
	AnimationEvent *base = (AnimationEvent *)ob->animevents.first;
	for (AnimationEvent *event = base; event; event = event->next) {
		if (event == base) {
			continue;
		}

		// Events without an action are kept so the sensor event indices stay valid.
		const std::string actionName = (event->action) ? event->action->id.name + 2 : "";

		std::vector<std::pair<int, std::string>> triggers;
		AnimationEventTrigger *baseTrigger = (AnimationEventTrigger *)event->triggers.first;
		for (AnimationEventTrigger *trigger = baseTrigger; trigger; trigger = trigger->next) {
			if (trigger == baseTrigger) {
				continue;
			}
			triggers.emplace_back(trigger->frame, trigger->custom_arg);
		}

		m_events.push_back(new KX_AnimationEvent(actionName, triggers, event->eventcall));
	}
}

KX_AnimationEventManager::KX_AnimationEventManager(const KX_AnimationEventManager& other)
	:EXP_Value(other)
{
	// Don't share the Python proxy of the original manager.
	ProcessReplica();

	for (KX_AnimationEvent *event : other.m_events) {
		m_events.push_back(new KX_AnimationEvent(*event));
	}
}

KX_AnimationEventManager::~KX_AnimationEventManager()
{
	for (KX_AnimationEvent *event : m_events) {
		event->Release();
	}
}

std::string KX_AnimationEventManager::GetName()
{
	return "KX_AnimationEventManager";
}

unsigned int KX_AnimationEventManager::GetEventCount() const
{
	return m_events.size();
}

const std::vector<KX_AnimationEvent *>& KX_AnimationEventManager::GetEvents() const
{
	return m_events;
}

KX_AnimationEvent *KX_AnimationEventManager::GetEvent(int index) const
{
	if (index >= 0 && index < (int)m_events.size()) {
		return m_events[index];
	}
	return nullptr;
}

void KX_AnimationEventManager::AddEventToCall(KX_AnimationEvent *event, int triggerIndex)
{
	m_eventsToCall.emplace_back(event, event->GetCustomArg(triggerIndex));
}

void KX_AnimationEventManager::TakeEventsToCall(std::vector<EventCall>& calls)
{
	calls.insert(calls.end(), m_eventsToCall.begin(), m_eventsToCall.end());
	m_eventsToCall.clear();
}

#ifdef WITH_PYTHON

PyTypeObject KX_AnimationEventManager::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_AnimationEventManager",
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

PyMethodDef KX_AnimationEventManager::Methods[] = {
	{nullptr, nullptr} // Sentinel
};

PyAttributeDef KX_AnimationEventManager::Attributes[] = {
	EXP_PYATTRIBUTE_RO_FUNCTION("events", KX_AnimationEventManager, pyattr_get_events),
	EXP_PYATTRIBUTE_NULL
};

unsigned int KX_AnimationEventManager::py_get_events_size()
{
	return m_events.size();
}

PyObject *KX_AnimationEventManager::py_get_events_item(unsigned int index)
{
	return m_events[index]->GetProxy();
}

PyObject *KX_AnimationEventManager::pyattr_get_events(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	return (new EXP_ListWrapper<KX_AnimationEventManager, &KX_AnimationEventManager::py_get_events_size, &KX_AnimationEventManager::py_get_events_item>(self_v))->NewProxy(true);
}
#endif //WITH_PYTHON
