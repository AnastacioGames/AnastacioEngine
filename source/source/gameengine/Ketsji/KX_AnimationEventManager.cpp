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
#include "DNA_object_types.h"
#include "BLI_listbase.h"

KX_AnimationEventManager::KX_AnimationEventManager(Object *ob)
	:m_refcount(1)
{
	this->m_events = new std::vector<KX_AnimationEvent*>();
	this->m_events_toCall = new std::vector<std::pair<KX_AnimationEvent*, const char*>>();

	/* XXX Converter XXX */
	AnimationEvent *base = (AnimationEvent*)ob->animevents.first;
	for (AnimationEvent *event = (AnimationEvent *)ob->animevents.first; event; event = event->next) {
		if (event == base) continue;

		char *pythonEvent = new char[64];
		if (strlen(event->eventcall) != 0) {
			strcpy(pythonEvent, event->eventcall);
		}
		else {
			pythonEvent = nullptr;
		}

		char *actionName = new char[64];
		// Check if have an action.
		if (event->action) {
			strcpy(actionName, event->action->id.name + 2);
		}
		else {
			// we need to keep the animation event empty and not remove it, to avoid problems with the animation event sensor, so dummy the name.
			actionName = "nullptr";
		}

		AnimationEventTrigger *trigger;

		std::vector<std::pair<int, const char*>> *triggers = new std::vector<std::pair<int, const char*>>();
		std::vector<int> *alreadyTriggered = new std::vector<int>();
		bool first = true;
		for (trigger = (AnimationEventTrigger*)event->triggers.first; trigger; trigger = trigger->next) {
			if (first) {
				first = false;
				continue;
			}

			char *custom_arg = new char[64];
			strcpy(custom_arg, trigger->custom_arg);

			triggers->push_back(std::make_pair(trigger->frame, custom_arg));
		}

		this->m_events->emplace_back(new KX_AnimationEvent(actionName, triggers, alreadyTriggered, pythonEvent));
	}
}

KX_AnimationEventManager::KX_AnimationEventManager(std::vector<KX_AnimationEvent*> *other_events)
	:m_refcount(1)
{
	std::vector<KX_AnimationEvent*> *events = new std::vector<KX_AnimationEvent*>();

	// Copy KX_AnimationEvents from other.
	for (KX_AnimationEvent *event : *other_events) {
		KX_AnimationEvent *event_new = new KX_AnimationEvent(*event);
		event_new->SetAlreadyTriggereds(new std::vector<int>());
		events->push_back(event_new);
	}

	m_events = events;
	m_events_toCall = new std::vector<std::pair<KX_AnimationEvent*, const char*>>();
}

KX_AnimationEventManager::~KX_AnimationEventManager()
{
	for (KX_AnimationEvent *event : *m_events) {
		delete event;
	}

	delete m_events;
	delete m_events_toCall;
}

std::string KX_AnimationEventManager::GetName()
{
	return "KX_AnimationEventManager";
}

unsigned int KX_AnimationEventManager::GetEventCount() const
{
	return m_events->size();
}

std::vector<KX_AnimationEvent*> *KX_AnimationEventManager::GetEvents() const
{
	return m_events;
}

KX_AnimationEvent *KX_AnimationEventManager::GetEvent(int index)
{
	if (this && (index >= 0 && index < m_events->size())) {
		return m_events->at(index);
	}
	return nullptr;
}

std::vector<std::pair<KX_AnimationEvent*, const char*>> *KX_AnimationEventManager::GetEventsToCall()
{
	return m_events_toCall;
}

void KX_AnimationEventManager::ClearEventsToCall()
{
	m_events_toCall->clear();
}


void KX_AnimationEventManager::ResetTriggers() {
	for (unsigned int i = 0; i < m_events->size(); i++) {
		KX_AnimationEvent *event = (*m_events)[i];
		event->GetAlreadyTriggereds()->clear();
	}
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
	return m_events->size();
}

PyObject *KX_AnimationEventManager::py_get_events_item(unsigned int index)
{
	return (*m_events)[index]->GetProxy();
}

PyObject *KX_AnimationEventManager::pyattr_get_events(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	return (new EXP_ListWrapper<KX_AnimationEventManager, &KX_AnimationEventManager::py_get_events_size, &KX_AnimationEventManager::py_get_events_item>(self_v))->NewProxy(true);
}
#endif //WITH_PYTHON
