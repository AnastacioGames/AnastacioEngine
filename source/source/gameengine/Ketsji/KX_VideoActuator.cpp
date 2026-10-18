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
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Ketsji/KX_VideoActuator.cpp
 *  \ingroup ketsji
 */

#include "KX_VideoActuator.h"
#include "KX_GameObject.h"
#include "KX_PythonComponent.h"
#include "EXP_ListValue.h"
#include "CM_Message.h"

#include <algorithm>

KX_VideoActuator::KX_VideoActuator(SCA_IObject *gameobj, int mode, float seconds, bool relative,
                                   KX_GameObject *target)
	:SCA_IActuator(gameobj, KX_ACT_VIDEO),
	m_mode(mode),
	m_seconds(seconds),
	m_relative(relative),
	m_target(target),
	m_watching(false),
	m_pending(false),
	m_warned(false)
{
	if (m_target) {
		m_target->RegisterActuator(this);
	}
}

KX_VideoActuator::~KX_VideoActuator()
{
	if (m_target) {
		m_target->UnregisterActuator(this);
	}
}

EXP_Value *KX_VideoActuator::GetReplica()
{
	KX_VideoActuator *replica = new KX_VideoActuator(*this);
	replica->ProcessReplica();
	return replica;
}

void KX_VideoActuator::ProcessReplica()
{
	if (m_target) {
		m_target->RegisterActuator(this);
	}
	m_watching = false;
	m_pending = false;
	SCA_IActuator::ProcessReplica();
}

bool KX_VideoActuator::UnlinkObject(SCA_IObject *clientobj)
{
	if (clientobj == m_target) {
		m_target = nullptr;
		return true;
	}
	return false;
}

void KX_VideoActuator::Relink(std::map<SCA_IObject *, SCA_IObject *>& obj_map)
{
	KX_GameObject *obj = static_cast<KX_GameObject *>(obj_map[m_target]);
	if (obj) {
		if (m_target) {
			m_target->UnregisterActuator(this);
		}
		m_target = obj;
		m_target->RegisterActuator(this);
	}
}

void KX_VideoActuator::Deactivate()
{
	if (m_watching || m_pending) {
		m_watching = false;
		m_pending = false;
		SetEndReason(END_CANCELLED);
	}
	SCA_IActuator::Deactivate();
}

#ifdef WITH_PYTHON

PyObject *KX_VideoActuator::FindPlayer()
{
	KX_GameObject *obj = m_target ? m_target : static_cast<KX_GameObject *>(GetParent());
	EXP_ListValue<KX_PythonComponent> *components = obj->GetComponents();
	if (components) {
		for (KX_PythonComponent *component : components) {
			PyObject *proxy = component->GetProxy();
			if (PyObject_HasAttrString(proxy, "anastacio_video")) {
				return proxy;
			}
			Py_DECREF(proxy);
		}
	}
	if (!m_warned) {
		m_warned = true;
		CM_LogicBrickWarning(this, "object \"" << obj->GetName()
		                     << "\" has no Video Player (add it in the Video Player panel of the Object tab)");
	}
	return nullptr;
}

static bool video_call(PyObject *player, const char *method, PyObject *arg = nullptr)
{
	PyObject *ret = arg ? PyObject_CallMethod(player, method, "O", arg) : PyObject_CallMethod(player, method, nullptr);
	if (!ret) {
		PyErr_Print();
		return false;
	}
	Py_DECREF(ret);
	return true;
}

static bool video_get_bool(PyObject *player, const char *name)
{
	PyObject *value = PyObject_GetAttrString(player, name);
	if (!value) {
		PyErr_Clear();
		return false;
	}
	const bool result = PyObject_IsTrue(value) == 1;
	Py_DECREF(value);
	return result;
}

static double video_get_float(PyObject *player, const char *name)
{
	PyObject *value = PyObject_GetAttrString(player, name);
	if (!value) {
		PyErr_Clear();
		return 0.0;
	}
	const double result = PyFloat_AsDouble(value);
	Py_DECREF(value);
	if (PyErr_Occurred()) {
		PyErr_Clear();
		return 0.0;
	}
	return result;
}

#endif  // WITH_PYTHON

bool KX_VideoActuator::Update()
{
	const bool positiveEvent = m_posevent;
	RemoveAllEvents();

	if ((m_watching || m_pending) && IsNoLink()) {
		// the controllers left the active state: the video goes on, the actuator stops watching it
		m_watching = false;
		m_pending = false;
		SetEndReason(END_CANCELLED);
		return false;
	}

	if (positiveEvent) {
		m_pending = true;
		m_watching = false;
	}
	if (!m_pending && !m_watching) {
		return false;
	}

#ifdef WITH_PYTHON
	PyObject *player = FindPlayer();
	if (!player) {
		m_watching = false;
		m_pending = false;
		SetEndReason(END_FAILED);
		return false;
	}

	if (m_pending) {
		// "finished" is set by the component's start(): before that the command waits a tick
		if (!PyObject_HasAttrString(player, "finished")) {
			Py_DECREF(player);
			return true;
		}
		m_pending = false;

		bool ok = true;
		bool watch = false;
		switch (m_mode) {
			case KX_VIDEO_PLAY:
				ok = video_call(player, "play");
				watch = true;
				break;
			case KX_VIDEO_PAUSE:
				ok = video_call(player, "pause");
				break;
			case KX_VIDEO_TOGGLE:
				if (video_get_bool(player, "playing")) {
					ok = video_call(player, "pause");
				}
				else {
					ok = video_call(player, "play");
					watch = true;
				}
				break;
			case KX_VIDEO_STOP:
				ok = video_call(player, "stop");
				break;
			case KX_VIDEO_RESTART:
			{
				PyObject *zero = PyFloat_FromDouble(0.0);
				ok = video_call(player, "seek", zero) && video_call(player, "play");
				Py_DECREF(zero);
				watch = true;
				break;
			}
			case KX_VIDEO_SEEK:
			{
				double time = m_seconds;
				if (m_relative) {
					time += video_get_float(player, "time");
				}
				const double duration = video_get_float(player, "duration");
				time = std::max(0.0, (duration > 0.0) ? std::min(time, duration) : time);
				PyObject *seconds = PyFloat_FromDouble(time);
				ok = video_call(player, "seek", seconds);
				Py_DECREF(seconds);
				break;
			}
		}

		if (!ok) {
			Py_DECREF(player);
			SetEndReason(END_FAILED);
			return false;
		}
		if (!watch) {
			Py_DECREF(player);
			SetEndReason(END_FINISHED);
			return false;
		}
		m_watching = true;
	}

	// Play/Restart: finished when the video reaches its end (a looping video never does)
	if (video_get_bool(player, "finished")) {
		m_watching = false;
		SetEndReason(END_FINISHED);
	}
	else if (!video_get_bool(player, "playing")) {
		// paused or stopped by someone else, or the video could not be opened
		m_watching = false;
		PyObject *error = PyObject_GetAttrString(player, "error");
		const bool failed = error && PyObject_IsTrue(error) == 1;
		Py_XDECREF(error);
		PyErr_Clear();
		SetEndReason(failed ? END_FAILED : END_CANCELLED);
	}
	Py_DECREF(player);
	return m_watching;
#else
	m_pending = false;
	SetEndReason(END_FAILED);
	return false;
#endif  // WITH_PYTHON
}

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python functions                                                          */
/* ------------------------------------------------------------------------- */

/* Integration hooks ------------------------------------------------------- */
PyTypeObject KX_VideoActuator::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_VideoActuator",
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
	&SCA_IActuator::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_VideoActuator::Methods[] = {
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_VideoActuator::Attributes[] = {
	EXP_PYATTRIBUTE_INT_RW("mode", KX_VIDEO_PLAY, KX_VIDEO_MAX - 1, true, KX_VideoActuator, m_mode),
	EXP_PYATTRIBUTE_FLOAT_RW("seconds", -100000.0f, 100000.0f, KX_VideoActuator, m_seconds),
	EXP_PYATTRIBUTE_BOOL_RW("useRelative", KX_VideoActuator, m_relative),
	EXP_PYATTRIBUTE_RW_FUNCTION("object", KX_VideoActuator, pyattr_get_object, pyattr_set_object),
	EXP_PYATTRIBUTE_NULL //Sentinel
};

PyObject *KX_VideoActuator::pyattr_get_object(EXP_PyObjectPlus *self, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_VideoActuator *actuator = static_cast<KX_VideoActuator *>(self);
	if (!actuator->m_target) {
		Py_RETURN_NONE;
	}
	return actuator->m_target->GetProxy();
}

int KX_VideoActuator::pyattr_set_object(EXP_PyObjectPlus *self, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_VideoActuator *actuator = static_cast<KX_VideoActuator *>(self);
	KX_GameObject *gameobj;

	if (!ConvertPythonToGameObject(actuator->GetLogicManager(), value, &gameobj, true, "actuator.object = value: KX_VideoActuator")) {
		return PY_SET_ATTR_FAIL; // ConvertPythonToGameObject sets the error
	}
	if (actuator->m_target) {
		actuator->m_target->UnregisterActuator(actuator);
	}
	actuator->m_target = gameobj;
	if (actuator->m_target) {
		actuator->m_target->RegisterActuator(actuator);
	}
	return PY_SET_ATTR_SUCCESS;
}

#endif // WITH_PYTHON
