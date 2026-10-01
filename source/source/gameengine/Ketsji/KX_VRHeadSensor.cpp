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

/** \file gameengine/Ketsji/KX_VRHeadSensor.cpp
 *  \ingroup ketsji
 */

#include "KX_VRHeadSensor.h"
#include "KX_Scene.h"
#include "KX_Camera.h"
#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "DNA_sensor_types.h"

#include <algorithm>
#include <cmath>

KX_VRHeadSensor::KX_VRHeadSensor(SCA_EventManager *eventmgr, SCA_IObject *gameobj, KX_Scene *scene,
                                 int mode, float angle, float time)
	:SCA_ISensor(gameobj, eventmgr),
	m_scene(scene),
	m_mode(mode),
	m_angle(angle),
	m_time(time)
{
	Init();
}

KX_VRHeadSensor::~KX_VRHeadSensor()
{
}

void KX_VRHeadSensor::Init()
{
	m_pitch = m_yaw = m_roll = 0.0f;
	m_hasHead = false;
	m_positive = false;
	m_anchor = m_extreme = 0.0f;
	m_dir = 0;
	m_swings = 0;
	m_elapsed = 0.0f;
}

EXP_Value *KX_VRHeadSensor::GetReplica()
{
	KX_VRHeadSensor *replica = new KX_VRHeadSensor(*this);
	replica->ProcessReplica();
	replica->Init();
	return replica;
}

void KX_VRHeadSensor::Replace_IScene(SCA_IScene *val)
{
	m_scene = static_cast<KX_Scene *>(val);
}

bool KX_VRHeadSensor::IsPositiveTrigger()
{
	return m_invert ? !m_positive : m_positive;
}

void KX_VRHeadSensor::UpdateHead()
{
	KX_Camera *cam = m_scene ? m_scene->GetActiveCamera() : nullptr;
	if (!cam) {
		m_hasHead = false;
		return;
	}

	const mt::mat3 rot = cam->GetRenderOrientation();
	const mt::vec3 fwd = rot * mt::vec3(0.0f, 0.0f, -1.0f);
	const mt::vec3 right = rot * mt::vec3(1.0f, 0.0f, 0.0f);

	m_pitch = std::asin(std::max(-1.0f, std::min(1.0f, fwd.z)));
	// Positive roll = head tilted to the left (right ear up).
	m_roll = std::asin(std::max(-1.0f, std::min(1.0f, right.z)));

	// Unwrapped yaw so a shake across +-180 degrees doesn't jump.
	const float yaw = std::atan2(fwd.y, fwd.x);
	if (!m_hasHead) {
		m_yaw = yaw;
	}
	else {
		float delta = yaw - std::atan2(std::sin(m_yaw), std::cos(m_yaw));
		if (delta > (float)M_PI) {
			delta -= 2.0f * (float)M_PI;
		}
		else if (delta < -(float)M_PI) {
			delta += 2.0f * (float)M_PI;
		}
		m_yaw += delta;
	}

	if (!m_hasHead) {
		m_anchor = (m_mode == SENS_VRHEAD_SHAKE) ? m_yaw : m_pitch;
	}
	m_hasHead = true;
}

/* Zig-zag detector: away from the rest value by the angle, then back by the angle, inside the time. */
bool KX_VRHeadSensor::DetectGesture(float value, float dt)
{
	m_elapsed += dt;

	if (m_dir == 0) {
		const float d = value - m_anchor;
		if (std::fabs(d) >= m_angle) {
			m_dir = (d > 0.0f) ? 1 : -1;
			m_extreme = value;
			m_swings = 1;
			m_elapsed = 0.0f;
		}
		else if (m_elapsed > m_time) {
			// Slow drift: the head rests in a new place.
			m_anchor = value;
			m_elapsed = 0.0f;
		}
		return false;
	}

	if ((value - m_extreme) * m_dir > 0.0f) {
		m_extreme = value;
	}
	else if (std::fabs(value - m_extreme) >= m_angle) {
		++m_swings;
		m_dir = -m_dir;
		m_extreme = value;
	}

	const bool done = (m_swings >= 2);
	if (done || m_elapsed > m_time) {
		m_anchor = value;
		m_dir = 0;
		m_swings = 0;
		m_elapsed = 0.0f;
	}
	return done;
}

bool KX_VRHeadSensor::Evaluate()
{
	const bool reset = m_reset && m_level;

	UpdateHead();

	bool positive = false;
	if (m_hasHead) {
		switch (m_mode) {
			case SENS_VRHEAD_LOOK_UP:
				positive = (m_pitch >= m_angle);
				break;
			case SENS_VRHEAD_LOOK_DOWN:
				positive = (m_pitch <= -m_angle);
				break;
			case SENS_VRHEAD_TILT_LEFT:
				positive = (m_roll >= m_angle);
				break;
			case SENS_VRHEAD_TILT_RIGHT:
				positive = (m_roll <= -m_angle);
				break;
			case SENS_VRHEAD_NOD:
			case SENS_VRHEAD_SHAKE:
			{
				const float dt = 1.0f / (float)std::max(KX_GetActiveEngine()->GetTicRate(), 1.0);
				positive = DetectGesture((m_mode == SENS_VRHEAD_SHAKE) ? m_yaw : m_pitch, dt);
				break;
			}
		}
	}

	const bool changed = (positive != m_positive);
	m_positive = positive;
	return changed || reset;
}

#ifdef WITH_PYTHON

PyTypeObject KX_VRHeadSensor::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_VRHeadSensor",
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
	&SCA_ISensor::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_VRHeadSensor::Methods[] = {
	{nullptr, nullptr} // Sentinel
};

PyAttributeDef KX_VRHeadSensor::Attributes[] = {
	EXP_PYATTRIBUTE_INT_RW("mode", SENS_VRHEAD_LOOK_UP, SENS_VRHEAD_SHAKE, true, KX_VRHeadSensor, m_mode),
	EXP_PYATTRIBUTE_FLOAT_RW("angle", 0.0f, 1.6f, KX_VRHeadSensor, m_angle),
	EXP_PYATTRIBUTE_FLOAT_RW("time", 0.05f, 10.0f, KX_VRHeadSensor, m_time),
	EXP_PYATTRIBUTE_FLOAT_RO("pitch", KX_VRHeadSensor, m_pitch),
	EXP_PYATTRIBUTE_FLOAT_RO("yaw", KX_VRHeadSensor, m_yaw),
	EXP_PYATTRIBUTE_FLOAT_RO("roll", KX_VRHeadSensor, m_roll),
	EXP_PYATTRIBUTE_NULL // Sentinel
};

#endif
