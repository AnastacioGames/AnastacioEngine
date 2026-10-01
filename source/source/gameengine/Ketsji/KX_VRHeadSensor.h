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

/** \file KX_VRHeadSensor.h
 *  \ingroup ketsji
 *  \brief Detect head gestures (look up/down, tilt, nod, shake) of the active camera.
 */

#ifndef __KX_VRHEADSENSOR_H__
#define __KX_VRHEADSENSOR_H__

#include "SCA_ISensor.h"
#include "SCA_IScene.h"

class KX_Scene;

class KX_VRHeadSensor : public SCA_ISensor
{
	Py_Header

	KX_Scene *m_scene;
	int m_mode;
	/// Radians.
	float m_angle;
	/// Seconds for a whole nod/shake.
	float m_time;

	/// Head angles of the active camera, radians (yaw is unwrapped).
	float m_pitch;
	float m_yaw;
	float m_roll;
	bool m_hasHead;

	bool m_positive;

	/// Nod/shake zig-zag detector.
	float m_anchor;
	float m_extreme;
	int m_dir;
	int m_swings;
	float m_elapsed;

public:
	KX_VRHeadSensor(SCA_EventManager *eventmgr, SCA_IObject *gameobj, KX_Scene *scene, int mode, float angle, float time);
	virtual ~KX_VRHeadSensor();
	virtual EXP_Value *GetReplica();

	virtual bool Evaluate();
	virtual bool IsPositiveTrigger();
	virtual void Init();

	virtual void Replace_IScene(SCA_IScene *val);

private:
	void UpdateHead();
	bool DetectGesture(float value, float dt);
};

#endif  // __KX_VRHEADSENSOR_H__
