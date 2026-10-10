/*
 * Cast a ray and feel for objects
 *
 *
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
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 *
 * The Original Code is: all of this file.
 *
 * Contributor(s): none yet.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Ketsji/KX_RaySensor.cpp
 *  \ingroup ketsji
 */


#include "KX_RaySensor.h"
#include "SCA_EventManager.h"
#include "SCA_LogicManager.h"
#include "SCA_IObject.h"
#include "KX_ClientObjectInfo.h"
#include "KX_GameObject.h"
#include "KX_Scene.h"
#include "KX_RayCast.h"
#include "KX_PyMath.h"
#include "KX_Globals.h"
#include "KX_Mesh.h"
#include "KX_Camera.h"
#include "KX_KetsjiEngine.h"
#include "PHY_IPhysicsEnvironment.h"
#include "PHY_IPhysicsController.h"
#include "DNA_sensor_types.h"

#include "CM_Message.h"

#include <algorithm>
#include <cmath>

KX_RaySensor::KX_RaySensor(class SCA_EventManager *eventmgr,
							   SCA_IObject *gameobj,
							   const std::string& propname,
							   bool bFindMaterial,
							   bool bXRay,
							   double distance,
							   int axis,
							   int mask,
							   KX_Scene *ketsjiScene,
							   bool drawDebug,
							   float gazeTime,
							   float gazeAngle,
							   bool gazeReticle,
							   bool gazeSelf,
							   bool gazeHighlight)
	:SCA_ISensor(gameobj, eventmgr),
	m_propertyname(propname),
	m_bFindMaterial(bFindMaterial),
	m_bXRay(bXRay),
	m_distance(distance),
	m_scene(ketsjiScene),
	m_axis(axis),
	m_mask(mask),
	m_drawDebug(drawDebug),
	m_gazeTime(gazeTime),
	m_gazeAccum(0.0f),
	m_gazeAngle(gazeAngle),
	m_gazeReticle(gazeReticle),
	m_gazeSelf(gazeSelf),
	m_gazeObject(nullptr),
	m_gazeHighlight(gazeHighlight),
	m_highlightObject(nullptr),
	m_hitMaterial("")
{
	Init();
}

void KX_RaySensor::Init()
{
	m_bTriggered = (m_invert) ? true : false;
	m_rayHit = false;
	m_hitObject = nullptr;
	m_gazeAccum = 0.0f;
	m_gazeObject = nullptr;
	m_reset = true;
	SetHighlight(nullptr);
}

KX_RaySensor::~KX_RaySensor()
{
	SetHighlight(nullptr);
}

void KX_RaySensor::SetHighlight(KX_GameObject *gameobj)
{
	if (gameobj == m_highlightObject) {
		return;
	}
	if (m_highlightObject) {
		m_highlightObject->NodeSetLocalScale(m_highlightScale);
		m_highlightObject->NodeUpdate();
		m_highlightObject->UnregisterSensor(this);
	}
	m_highlightObject = gameobj;
	if (gameobj) {
		m_highlightScale = gameobj->NodeGetLocalScaling();
		gameobj->NodeSetLocalScale(m_highlightScale * 1.1f);
		gameobj->NodeUpdate();
		gameobj->RegisterSensor(this);
	}
}

bool KX_RaySensor::UnlinkObject(SCA_IObject *clientobj)
{
	if (clientobj == m_highlightObject) {
		m_highlightObject = nullptr;
		return true;
	}
	return false;
}



EXP_Value *KX_RaySensor::GetReplica()
{
	KX_RaySensor *replica = new KX_RaySensor(*this);
	replica->m_highlightObject = nullptr;
	replica->ProcessReplica();
	replica->Init();

	return replica;
}



bool KX_RaySensor::IsPositiveTrigger()
{
	bool result = m_rayHit;

	if (m_invert) {
		result = !result;
	}

	return result;
}

bool KX_RaySensor::RayHit(KX_ClientObjectInfo *client, KX_RayCast *result, void *UNUSED(data))
{

	KX_GameObject *hitKXObj = client->m_gameobject;
    bool bFound = false;
    std::string hitMaterial = "";

	if (m_propertyname.empty()) {
		bFound = true;
	}
	else {
		if (m_bFindMaterial) {
			for (RAS_Mesh *meshObj : hitKXObj->GetMeshList()) {
				bFound = (meshObj->FindMaterialName(m_propertyname) != nullptr);
				if (bFound) {
                    hitMaterial = m_propertyname;
					break;
				}
			}
		}
		else {
			bFound = hitKXObj->GetProperty(m_propertyname) != nullptr;
		}
	}

	if (bFound) {
		m_rayHit = true;
		m_hitObject = hitKXObj;
		m_hitPosition = result->m_hitPoint;
		m_hitNormal = result->m_hitNormal;
		m_hitMaterial = hitMaterial;
	}
	// no multi-hit search yet
	return true;
}

/* this function is used to pre-filter the object before casting the ray on them.
 * This is useful for "X-Ray" option when we want to see "through" unwanted object.
 */
bool KX_RaySensor::NeedRayCast(KX_ClientObjectInfo *client, void *UNUSED(data))
{
	KX_GameObject *hitKXObj = client->m_gameobject;

	if (client->m_type > KX_ClientObjectInfo::ACTOR) {
		// Unknown type of object, skip it.
		// Should not occur as the sensor objects are filtered in RayTest()
		CM_Error("invalid client type " << client->m_type << " found ray casting");
		return false;
	}

	// The current object is not in the proper layer.
	if (!(hitKXObj->GetCollisionGroup() & m_mask)) {
		return false;
	}

	if (m_bXRay && m_propertyname.size() != 0) {
		if (m_bFindMaterial) {
			bool found = false;
			for (KX_Mesh *meshObj : hitKXObj->GetMeshList()) {
				found = (meshObj->FindMaterialName(m_propertyname) != nullptr);
				if (found) {
					break;
				}
			}
			if (!found) {
				return false;
			}
		}
		else {
			if (hitKXObj->GetProperty(m_propertyname) == nullptr) {
				return false;
			}
		}
	}
	return true;
}

/* The owner itself or one of its children (a button made of a plane and its text). */
bool KX_RaySensor::IsSelf(KX_GameObject *owner, KX_GameObject *gameobj)
{
	for (KX_GameObject *o = gameobj; o; o = o->GetParent()) {
		if (o == owner) {
			return true;
		}
	}
	return false;
}

bool KX_RaySensor::Evaluate()
{
	bool result = false;
	bool reset = m_reset && m_level;
	m_rayHit = false;
	m_hitObject = nullptr;
	m_hitPosition = mt::zero3;
	m_hitNormal = mt::axisX3;

	KX_GameObject *owner = (KX_GameObject *)GetParent();
	KX_GameObject *obj = owner;
	/* Self: a VR button looks for the gaze of the active camera and only fires when it hits the owner itself. */
	const bool gazeSelf = (m_axis == SENS_RAY_GAZE && m_gazeSelf && !dynamic_cast<KX_Camera *>(owner));
	if (gazeSelf) {
		obj = m_scene->GetActiveCamera();
		if (!obj) {
			return false;
		}
	}
	mt::vec3 frompoint = obj->NodeGetWorldPosition();
	mt::mat3 mat = obj->NodeGetWorldOrientation();

	mt::vec3 todir;
	m_reset = false;
	switch (m_axis) {
		case SENS_RAY_X_AXIS: // X
		{
			todir = mat.GetColumn(0);
			break;
		}
		case SENS_RAY_Y_AXIS: // Y
		{
			todir = mat.GetColumn(1);
			break;
		}
		case SENS_RAY_Z_AXIS: // Z
		{
			todir = mat.GetColumn(2);
			break;
		}
		case SENS_RAY_NEG_X_AXIS: // -X
		{
			todir = -mat.GetColumn(0);
			break;
		}
		case SENS_RAY_NEG_Y_AXIS: // -Y
		{
			todir = -mat.GetColumn(1);
			break;
		}
		case SENS_RAY_NEG_Z_AXIS: // -Z
		{
			todir = -mat.GetColumn(2);
			break;
		}
		case SENS_RAY_GAZE: // VR head view of the camera
		{
			KX_Camera *cam = dynamic_cast<KX_Camera *>(obj);
			todir = cam ? cam->GetRenderOrientation() * mt::vec3(0.0f, 0.0f, -1.0f) : -mat.GetColumn(2);
			break;
		}
		default:
		{
			todir = mat.GetColumn(1);
			break;
		}
	}
	todir.Normalize();
	m_rayDirection = todir;

	mt::vec3 topoint = frompoint + (m_distance) * todir;
	PHY_IPhysicsEnvironment *pe = m_scene->GetPhysicsEnvironment();

	if (!pe) {
		CM_LogicBrickWarning(this, "there is no physics environment! Check universe for malfunction.");
		return false;
	}

	PHY_IPhysicsController *spc = obj->GetPhysicsController();
	KX_GameObject *parent = obj->GetParent();
	if (!spc && parent) {
		spc = parent->GetPhysicsController();
	}


	PHY_IPhysicsEnvironment *physics_environment = this->m_scene->GetPhysicsEnvironment();


	KX_RayCast::Callback<KX_RaySensor, void> callback(this, spc);
	KX_RayCast::RayTest(physics_environment, frompoint, topoint, callback);
	if (m_drawDebug) {
		const mt::vec4 rayColor(1.0f, 0.2f, 0.2f, 1.0f);
		const mt::vec4 hitColor(0.1f, 1.0f, 0.2f, 1.0f);
		KX_RasterizerDrawDebugLine(frompoint, topoint, rayColor);
		if (m_rayHit) {
			KX_RasterizerDrawDebugLine(frompoint, m_hitPosition, hitColor);
		}
	}

	if (m_axis == SENS_RAY_GAZE && m_gazeAngle > 0.0f && !m_rayHit) {
		/* Gaze cone: the thin ray missed, take the visible target closest to the view center inside the cone.
		 * The object already being looked at keeps a wider cone so small head shakes don't reset the gaze time. */
		KX_GameObject *best = nullptr;
		/* Compare cosines instead of angles (no acos per object): angle <= limit <=> cos(angle) >= cos(limit)
		 * on [0, pi]. Limits are clamped to pi, where acos always passed. */
		const float coneCos = std::cos(std::min(m_gazeAngle, (float)M_PI));
		const float stickyCos = std::cos(std::min(m_gazeAngle * 1.5f, (float)M_PI));
		const float maxDistSq = m_distance * m_distance;
		float bestCos = coneCos;
		for (KX_GameObject *gameobj : m_scene->GetObjectList()) {
			if (gameobj == obj || !gameobj->GetVisible() || !(gameobj->GetCollisionGroup() & m_mask)) {
				continue;
			}
			/* Cheap geometric rejection before the property/material lookups. */
			const mt::vec3 to = gameobj->NodeGetWorldPosition() - frompoint;
			const float distSq = to.LengthSquared();
			if (distSq < 1e-8f || distSq > maxDistSq) {
				continue;
			}
			const float cosAngle = mt::Clamp(mt::dot(to, todir) / std::sqrt(distSq), -1.0f, 1.0f);
			const float limitCos = (gameobj == m_gazeObject) ? stickyCos : coneCos;
			if (!(cosAngle >= limitCos && (!best || cosAngle > bestCos))) {
				continue;
			}
			if (gazeSelf && !IsSelf(owner, gameobj)) {
				continue;
			}
			if (!gazeSelf && !m_propertyname.empty()) {
				bool found = false;
				if (m_bFindMaterial) {
					for (KX_Mesh *meshObj : gameobj->GetMeshList()) {
						if (meshObj->FindMaterialName(m_propertyname)) {
							found = true;
							break;
						}
					}
				}
				else {
					found = gameobj->GetProperty(m_propertyname) != nullptr;
				}
				if (!found) {
					continue;
				}
			}
			best = gameobj;
			bestCos = cosAngle;
		}
		if (best) {
			/* Line of sight: the ray toward the target must hit it first. */
			const mt::vec3 to = (best->NodeGetWorldPosition() - frompoint).Normalized();
			KX_RayCast::RayTest(physics_environment, frompoint, frompoint + m_distance * to, callback);
			if (!(m_rayHit && m_hitObject == best)) {
				m_rayHit = false;
				m_hitObject = nullptr;
			}
		}
		if (m_drawDebug) {
			/* Cone outline: ring of lines at the end of the range. */
			const mt::vec3 up = (std::fabs(todir.z) < 0.99f) ? mt::axisZ3 : mt::axisX3;
			const mt::vec3 u = mt::cross(todir, up).Normalized();
			const mt::vec3 v = mt::cross(u, todir);
			const float radius = std::tan(m_gazeAngle) * m_distance;
			const mt::vec4 coneColor = m_rayHit ? mt::vec4(0.1f, 1.0f, 0.2f, 1.0f) : mt::vec4(1.0f, 0.8f, 0.1f, 1.0f);
			mt::vec3 prev;
			for (int i = 0; i <= 16; ++i) {
				const float a = (float)i * (2.0f * (float)M_PI / 16.0f);
				const mt::vec3 p = topoint + radius * (std::cos(a) * u + std::sin(a) * v);
				if (i > 0) {
					KX_RasterizerDrawDebugLine(prev, p, coneColor);
				}
				if (i % 4 == 0) {
					KX_RasterizerDrawDebugLine(frompoint, p, coneColor);
				}
				prev = p;
			}
		}
	}

	if (gazeSelf && m_rayHit && !IsSelf(owner, static_cast<KX_GameObject *>(m_hitObject))) {
		m_rayHit = false;
		m_hitObject = nullptr;
	}

	if (m_axis == SENS_RAY_GAZE) {
		/* The gaze only counts after staying on the same object for the gaze time. */
		if (m_rayHit && m_hitObject == m_gazeObject) {
			m_gazeAccum += 1.0f / (float)std::max(KX_GetActiveEngine()->GetTicRate(), 1.0);
		}
		else {
			m_gazeAccum = 0.0f;
			m_gazeObject = m_rayHit ? m_hitObject : nullptr;
		}
		if (m_gazeHighlight) {
			SetHighlight(!m_rayHit ? nullptr : (gazeSelf ? owner : static_cast<KX_GameObject *>(m_hitObject)));
		}
		if (m_gazeReticle) {
			/* Ring facing the eye at the gaze point (2 m ahead when nothing is hit), about 1 degree wide;
			 * an inner ring grows with the gaze time and everything turns green when the sensor fires. */
			const mt::vec3 point = m_rayHit ? m_hitPosition : frompoint + std::min(2.0f, m_distance) * todir;
			const float dist = std::max((point - frompoint).Length(), 0.05f);
			const mt::vec3 center = frompoint + (dist * 0.98f) * todir;
			const mt::vec3 up = (std::fabs(todir.z) < 0.99f) ? mt::axisZ3 : mt::axisX3;
			const mt::vec3 u = mt::cross(todir, up).Normalized();
			const mt::vec3 v = mt::cross(u, todir);
			const float radius = dist * 0.009f;
			const float progress = !m_rayHit ? 0.0f : (m_gazeTime > 0.0f ? std::min(m_gazeAccum / m_gazeTime, 1.0f) : 1.0f);
			const mt::vec4 color = (progress >= 1.0f) ? mt::vec4(0.2f, 1.0f, 0.3f, 1.0f) : mt::vec4(1.0f, 1.0f, 1.0f, 1.0f);
			const int segments = 20;
			for (int ring = 0; ring < 2; ++ring) {
				const float r = (ring == 0) ? radius : radius * progress;
				if (r <= 0.0f) {
					continue;
				}
				for (int i = 0; i < segments; ++i) {
					const float a0 = (float)i * (2.0f * (float)M_PI / segments);
					const float a1 = (float)(i + 1) * (2.0f * (float)M_PI / segments);
					KX_RasterizerDrawDebugLine(center + r * (std::cos(a0) * u + std::sin(a0) * v),
					                           center + r * (std::cos(a1) * u + std::sin(a1) * v), color);
				}
			}
		}
		if (m_rayHit && m_gazeAccum < m_gazeTime) {
			m_rayHit = false;
		}
	}

	/* now pass this result to some controller */

	if (m_rayHit) {
		if (!m_bTriggered) {
			// notify logicsystem that ray is now hitting
			result = true;
			m_bTriggered = true;
		}
		else {
			// notify logicsystem that ray is STILL hitting ...
			result = false;

		}
	}
	else {
		if (m_bTriggered) {
			m_bTriggered = false;
			// notify logicsystem that ray JUST left the Object
			result = true;
		}
		else {
			result = false;
		}

	}
	if (reset) {
		// force an event
		result = true;
	}

	return result;
}

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python functions                                                          */
/* ------------------------------------------------------------------------- */

/* Integration hooks ------------------------------------------------------- */
PyTypeObject KX_RaySensor::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_RaySensor",
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

PyMethodDef KX_RaySensor::Methods[] = {
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_RaySensor::Attributes[] = {
	EXP_PYATTRIBUTE_BOOL_RW("useMaterial", KX_RaySensor, m_bFindMaterial),
	EXP_PYATTRIBUTE_BOOL_RW("useXRay", KX_RaySensor, m_bXRay),
	EXP_PYATTRIBUTE_FLOAT_RW("range", 0, 10000, KX_RaySensor, m_distance),
	EXP_PYATTRIBUTE_STRING_RW("propName", 0, MAX_PROP_NAME, false, KX_RaySensor, m_propertyname),
	EXP_PYATTRIBUTE_INT_RW("axis", 0, 6, true, KX_RaySensor, m_axis),
	EXP_PYATTRIBUTE_INT_RW("mask", 1, (1 << OB_MAX_COL_MASKS) - 1, true, KX_RaySensor, m_mask),
	EXP_PYATTRIBUTE_FLOAT_RW("gazeTime", 0, 30, KX_RaySensor, m_gazeTime),
	EXP_PYATTRIBUTE_FLOAT_RW("gazeAngle", 0, 1.0f, KX_RaySensor, m_gazeAngle),
	EXP_PYATTRIBUTE_RO_FUNCTION("gazeProgress", KX_RaySensor, pyattr_get_gazeprogress),
	EXP_PYATTRIBUTE_VECTOR_RO("hitPosition", KX_RaySensor, m_hitPosition, 3),
	EXP_PYATTRIBUTE_VECTOR_RO("rayDirection", KX_RaySensor, m_rayDirection, 3),
	EXP_PYATTRIBUTE_VECTOR_RO("hitNormal", KX_RaySensor, m_hitNormal, 3),
	EXP_PYATTRIBUTE_STRING_RO("hitMaterial", KX_RaySensor, m_hitMaterial),
	EXP_PYATTRIBUTE_RO_FUNCTION("hitObject", KX_RaySensor, pyattr_get_hitobject),
	EXP_PYATTRIBUTE_NULL    //Sentinel
};

PyObject *KX_RaySensor::pyattr_get_gazeprogress(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_RaySensor *self = static_cast<KX_RaySensor *>(self_v);
	if (!self->m_gazeObject) {
		return PyFloat_FromDouble(0.0);
	}
	return PyFloat_FromDouble(self->m_gazeTime > 0.0f ? std::min(self->m_gazeAccum / self->m_gazeTime, 1.0f) : 1.0f);
}

PyObject *KX_RaySensor::pyattr_get_hitobject(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_RaySensor *self = static_cast<KX_RaySensor *>(self_v);
	if (self->m_hitObject) {
		return self->m_hitObject->GetProxy();
	}

	Py_RETURN_NONE;
}

#endif // WITH_PYTHON
