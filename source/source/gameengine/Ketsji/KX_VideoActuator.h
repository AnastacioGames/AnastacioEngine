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

/** \file KX_VideoActuator.h
 *  \ingroup ketsji
 *  \brief Controls the Video Player component (anastacio_video.VideoPlayer) of an object.
 */

#ifndef __KX_VIDEOACTUATOR_H__
#define __KX_VIDEOACTUATOR_H__

#include "SCA_IActuator.h"

class KX_GameObject;

class KX_VideoActuator : public SCA_IActuator
{
	Py_Header

public:
	/// Same values as ACT_VIDEO_* in DNA_actuator_types.h.
	enum Mode {
		KX_VIDEO_PLAY = 0,
		KX_VIDEO_PAUSE,
		KX_VIDEO_TOGGLE,
		KX_VIDEO_STOP,
		KX_VIDEO_RESTART,
		KX_VIDEO_SEEK,
		KX_VIDEO_MAX
	};

private:
	int m_mode;
	float m_seconds;
	bool m_relative;
	/// Object with the Video Player, nullptr: the actuator's own object.
	KX_GameObject *m_target;
	/// Play/Restart: waiting for the end of the video to report Finished.
	bool m_watching;
	/// The command waits for the component's start() (first tick of the scene).
	bool m_pending;
	/// The "no Video Player" warning is printed once.
	bool m_warned;

#ifdef WITH_PYTHON
	/// New reference to the Video Player component, or nullptr.
	PyObject *FindPlayer();
#endif

public:
	KX_VideoActuator(SCA_IObject *gameobj, int mode, float seconds, bool relative, KX_GameObject *target);
	virtual ~KX_VideoActuator();

	virtual EXP_Value *GetReplica();
	virtual void ProcessReplica();
	virtual bool UnlinkObject(SCA_IObject *clientobj);
	virtual void Relink(std::map<SCA_IObject *, SCA_IObject *>& obj_map);
	virtual bool Update();
	virtual void Deactivate();

#ifdef WITH_PYTHON
	static PyObject *pyattr_get_object(EXP_PyObjectPlus *self, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_object(EXP_PyObjectPlus *self, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
#endif
};

#endif  // __KX_VIDEOACTUATOR_H__
