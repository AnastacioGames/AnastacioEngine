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

/** \file KX_AnimationEventManager.h
 *  \ingroup ketsji
 */

#ifndef __KX_ANIMATION_EVENT_MANAGER_H__
#define __KX_ANIMATION_EVENT_MANAGER_H__

#include "EXP_Value.h"
#include <vector>

class KX_Scene;
class BL_SceneConverter;
class KX_AnimationEvent;
struct Object;

class KX_AnimationEventManager : public EXP_Value
{
	Py_Header

private:
	std::vector<KX_AnimationEvent*> *m_events;
	/// is used to call the events in KX_Scene->UpdateAnimations, it is safe to do the python calls there.
	std::vector<std::pair<KX_AnimationEvent*, const char*>> *m_events_toCall;

	int m_refcount;

public:
	KX_AnimationEventManager(Object *ob);
	KX_AnimationEventManager(std::vector<KX_AnimationEvent*> *other_events);
	virtual ~KX_AnimationEventManager();

	virtual std::string GetName();

	/// Return number of events
	unsigned int GetEventCount() const;
	
	std::vector<KX_AnimationEvent*> *GetEvents() const;
	KX_AnimationEvent *GetEvent(int index);

	/// get the events iterate through KX_Scene->UpdateAnimations, then clean up the vector.
	std::vector<std::pair<KX_AnimationEvent*, const char*>> *GetEventsToCall();
	void ClearEventsToCall();

	/// Reset all triggers
	void ResetTriggers();

#ifdef WITH_PYTHON

	static PyObject *pyattr_get_events(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);

	unsigned int py_get_events_size();
	PyObject *py_get_events_item(unsigned int index);

#endif //WITH_PYTHON
};

#endif  // __KX_ANIMATION_EVENT_MANAGER_H__
