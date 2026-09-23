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

/** \file gameengine/Ketsji/KX_VehicleWrapper.cpp
 *  \ingroup ketsji
 */

#include "KX_VehicleWrapper.h"
#include "KX_VehiclePreset.h"
#include "PHY_IVehicle.h"
#include "KX_PyMath.h"
#include "KX_GameObject.h"
#include "KX_MotionState.h"
#include "KX_Globals.h"
#include "PHY_IPhysicsEnvironment.h"

#include <cmath>

#include "DNA_object_types.h" // for OB_MAX_COL_MASKS

KX_VehicleWrapper::KX_VehicleWrapper(PHY_IVehicle *vehicle)
	:m_vehicle(vehicle)
{
	m_vehicle->SetInvalidationCallback(&KX_VehicleWrapper::OnVehicleInvalidated, this);
}

KX_VehicleWrapper::~KX_VehicleWrapper()
{
	if (m_vehicle) {
		m_vehicle->SetInvalidationCallback(nullptr, nullptr);
	}
}

void KX_VehicleWrapper::OnVehicleInvalidated(void *client)
{
	static_cast<KX_VehicleWrapper *>(client)->m_vehicle = nullptr;
}

std::string KX_VehicleWrapper::GetName()
{
	return "KX_VehicleWrapper";
}

#ifdef WITH_PYTHON


static bool raise_exc_invalid(PHY_IVehicle *vehicle, const char *method)
{
	if (!vehicle) {
		PyErr_Format(PyExc_ReferenceError,
		             "%s(...): vehicle no longer exists (chassis or constraint was removed).", method);
		return true;
	}
	return false;
}

static bool raise_exc_wheel(PHY_IVehicle *vehicle, int i, const char *method)
{
	if (i < 0 || i >= vehicle->GetNumWheels()) {
		PyErr_Format(PyExc_ValueError,
		             "%s(...): wheel index %d out of range (0 to %d).", method, i, vehicle->GetNumWheels() - 1);
		return true;
	}
	else {
		return false;
	}
}

#define VEHICLE_VALID_CHECK_OR_RETURN(method) \
	if (raise_exc_invalid(m_vehicle, method)) {return nullptr;} (void)0

#define WHEEL_INDEX_CHECK_OR_RETURN(i, method) \
	VEHICLE_VALID_CHECK_OR_RETURN(method); \
	if (raise_exc_wheel(m_vehicle, i, method)) {return nullptr;} (void)0


PyObject *KX_VehicleWrapper::PyAddWheel(PyObject *args)
{

	PyObject *pylistPos, *pylistDir, *pylistAxleDir;
	PyObject *wheelGameObject;
	float suspensionRestLength, wheelRadius;
	int hasSteering;

	VEHICLE_VALID_CHECK_OR_RETURN("addWheel");

	if (PyArg_ParseTuple(args, "OOOOffi:addWheel", &wheelGameObject, &pylistPos, &pylistDir, &pylistAxleDir, &suspensionRestLength, &wheelRadius, &hasSteering)) {
		KX_GameObject *gameOb;
		if (!ConvertPythonToGameObject(KX_GetActiveScene()->GetLogicManager(), wheelGameObject, &gameOb, false, "vehicle.addWheel(...): KX_VehicleWrapper (first argument)")) {
			return nullptr;
		}

		if (gameOb->GetPhysicsController()) {
			PyErr_SetString(PyExc_AttributeError,
			                "addWheel(...) Unable to add wheel. The wheel object has an active physics/collision "
			                "controller (even if suspended); its raycast can self-collide with the suspension. "
			                "Use a plain Empty with Physics Type = 'No Collision' for wheel objects.");
			return nullptr;
		}

		if (gameOb->GetNode()) {
			mt::vec3 attachPos, attachDir, attachAxle;
			if (!PyVecTo(pylistPos, attachPos)) {
				PyErr_SetString(PyExc_AttributeError,
				                "addWheel(...) Unable to add wheel. attachPos must be a vector with 3 elements.");
				return nullptr;
			}
			if (!PyVecTo(pylistDir, attachDir)) {
				PyErr_SetString(PyExc_AttributeError,
				                "addWheel(...) Unable to add wheel. downDir must be a vector with 3 elements.");
				return nullptr;
			}
			if (!PyVecTo(pylistAxleDir, attachAxle)) {
				PyErr_SetString(PyExc_AttributeError,
				                "addWheel(...) Unable to add wheel. axleDir must be a vector with 3 elements.");
				return nullptr;
			}

			//someone reverse some conventions inside Bullet (axle winding)
			attachAxle = -attachAxle;

			if (!std::isfinite(attachPos.x) || !std::isfinite(attachPos.y) || !std::isfinite(attachPos.z) ||
			    !std::isfinite(attachDir.x) || !std::isfinite(attachDir.y) || !std::isfinite(attachDir.z) ||
			    !std::isfinite(attachAxle.x) || !std::isfinite(attachAxle.y) || !std::isfinite(attachAxle.z) ||
			    !std::isfinite(suspensionRestLength) || !std::isfinite(wheelRadius)) {
				PyErr_SetString(PyExc_AttributeError,
				                "addWheel(...) Unable to add wheel. NaN/infinite value in position, direction, axle, restLength or radius.");
				return nullptr;
			}

			if (wheelRadius <= 0) {
				PyErr_SetString(PyExc_AttributeError,
				                "addWheel(...) Unable to add wheel. wheelRadius must be positive.");
				return nullptr;
			}

			if (suspensionRestLength < 0) {
				PyErr_SetString(PyExc_AttributeError,
				                "addWheel(...) Unable to add wheel. suspensionRestLength must not be negative.");
				return nullptr;
			}

			const float dirLen = attachDir.Length();
			const float axleLen = attachAxle.Length();
			if (dirLen < 1e-6f) {
				PyErr_SetString(PyExc_AttributeError,
				                "addWheel(...) Unable to add wheel. downDir must not be a null vector.");
				return nullptr;
			}
			if (axleLen < 1e-6f) {
				PyErr_SetString(PyExc_AttributeError,
				                "addWheel(...) Unable to add wheel. axleDir must not be a null vector.");
				return nullptr;
			}

			const float collinearity = std::abs(mt::vec3::DotProduct(attachDir.Normalized(), attachAxle.Normalized()));
			if (collinearity > 0.999f) {
				PyErr_SetString(PyExc_AttributeError,
				                "addWheel(...) Unable to add wheel. downDir and axleDir must not be collinear.");
				return nullptr;
			}

			PHY_IMotionState *motionState = new KX_MotionState(gameOb->GetNode());
			m_vehicle->AddWheel(motionState, attachPos, attachDir, attachAxle, suspensionRestLength, wheelRadius, hasSteering);
		}

	}
	else {
		return nullptr;
	}
	Py_RETURN_NONE;
}


PyObject *KX_VehicleWrapper::PyGetWheelPosition(PyObject *args)
{

	int wheelIndex;

	if (PyArg_ParseTuple(args, "i:getWheelPosition", &wheelIndex)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "getWheelPosition");

		return PyObjectFrom(m_vehicle->GetWheelPosition(wheelIndex));
	}
	return nullptr;
}

PyObject *KX_VehicleWrapper::PyGetWheelRotation(PyObject *args)
{
	int wheelIndex;
	if (PyArg_ParseTuple(args, "i:getWheelRotation", &wheelIndex)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "getWheelRotation");

		return PyFloat_FromDouble(m_vehicle->GetWheelRotation(wheelIndex));
	}
	return nullptr;
}

PyObject *KX_VehicleWrapper::PyGetWheelOrientationQuaternion(PyObject *args)
{
	int wheelIndex;
	if (PyArg_ParseTuple(args, "i:getWheelOrientationQuaternion", &wheelIndex)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "getWheelOrientationQuaternion");

		const mt::quat quat = m_vehicle->GetWheelOrientationQuaternion(wheelIndex);
		const mt::mat3 ornmat = quat.ToMatrix();
		return PyObjectFrom(ornmat);
	}
	return nullptr;

}


PyObject *KX_VehicleWrapper::PyGetNumWheels(PyObject *args)
{
	VEHICLE_VALID_CHECK_OR_RETURN("getNumWheels");
	return PyLong_FromLong(m_vehicle->GetNumWheels());
}


PyObject *KX_VehicleWrapper::PyGetConstraintId(PyObject *args)
{
	VEHICLE_VALID_CHECK_OR_RETURN("getConstraintId");
	return PyLong_FromLong(m_vehicle->GetUserConstraintId());
}


PyObject *KX_VehicleWrapper::PyApplyEngineForce(PyObject *args)
{
	float force;
	int wheelIndex;

	if (PyArg_ParseTuple(args, "fi:applyEngineForce", &force, &wheelIndex)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "applyEngineForce");

		force *= -1.f;//someone reverse some conventions inside Bullet (axle winding)
		m_vehicle->ApplyEngineForce(force, wheelIndex);
	}
	else {
		return nullptr;
	}
	Py_RETURN_NONE;
}

PyObject *KX_VehicleWrapper::PySetTyreFriction(PyObject *args)
{
	float wheelFriction;
	int wheelIndex;

	if (PyArg_ParseTuple(args, "fi:setTyreFriction", &wheelFriction, &wheelIndex)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "setTyreFriction");

		m_vehicle->SetWheelFriction(wheelFriction, wheelIndex);
	}
	else {
		return nullptr;
	}
	Py_RETURN_NONE;
}

PyObject *KX_VehicleWrapper::PySetWheelIsDriveWheel(PyObject *args)
{
	int wheelIndex;
	int isDriveWheel;

	if (PyArg_ParseTuple(args, "ii:setWheelIsDriveWheel", &wheelIndex, &isDriveWheel)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "setWheelIsDriveWheel");

		m_vehicle->SetWheelIsDriveWheel(wheelIndex, isDriveWheel != 0);
	}
	else {
		return nullptr;
	}
	Py_RETURN_NONE;
}

PyObject *KX_VehicleWrapper::PySetSuspensionStiffness(PyObject *args)
{
	float suspensionStiffness;
	int wheelIndex;

	if (PyArg_ParseTuple(args, "fi:setSuspensionStiffness", &suspensionStiffness, &wheelIndex)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "setSuspensionStiffness");

		m_vehicle->SetSuspensionStiffness(suspensionStiffness, wheelIndex);
	}
	else {
		return nullptr;
	}
	Py_RETURN_NONE;
}

PyObject *KX_VehicleWrapper::PySetSuspensionDamping(PyObject *args)
{
	float suspensionDamping;
	int wheelIndex;

	if (PyArg_ParseTuple(args, "fi:setSuspensionDamping", &suspensionDamping, &wheelIndex)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "setSuspensionDamping");

		m_vehicle->SetSuspensionDamping(suspensionDamping, wheelIndex);
	}
	else {
		return nullptr;
	}
	Py_RETURN_NONE;
}

PyObject *KX_VehicleWrapper::PySetSuspensionCompression(PyObject *args)
{
	float suspensionCompression;
	int wheelIndex;

	if (PyArg_ParseTuple(args, "fi:setSuspensionCompression", &suspensionCompression, &wheelIndex)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "setSuspensionCompression");

		m_vehicle->SetSuspensionCompression(suspensionCompression, wheelIndex);
	}
	else {
		return nullptr;
	}
	Py_RETURN_NONE;
}

PyObject *KX_VehicleWrapper::PySetRollInfluence(PyObject *args)
{
	float rollInfluence;
	int wheelIndex;

	if (PyArg_ParseTuple(args, "fi:setRollInfluence", &rollInfluence, &wheelIndex)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "setRollInfluence");

		m_vehicle->SetRollInfluence(rollInfluence, wheelIndex);
	}
	else {
		return nullptr;
	}
	Py_RETURN_NONE;
}


PyObject *KX_VehicleWrapper::PyApplyBraking(PyObject *args)
{
	float braking;
	int wheelIndex;

	if (PyArg_ParseTuple(args, "fi:applyBraking", &braking, &wheelIndex)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "applyBraking");

		m_vehicle->ApplyBraking(braking, wheelIndex);
	}
	else {
		return nullptr;
	}
	Py_RETURN_NONE;
}


PyObject *KX_VehicleWrapper::PySetSteeringValue(PyObject *args)
{
	float steeringValue;
	int wheelIndex;

	if (PyArg_ParseTuple(args, "fi:setSteeringValue", &steeringValue, &wheelIndex)) {
		WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "setSteeringValue");

		m_vehicle->SetSteeringValue(steeringValue, wheelIndex);
	}
	else {
		return nullptr;
	}
	Py_RETURN_NONE;
}


PyObject *KX_VehicleWrapper::PyGetConstraintType(PyObject *args)
{
	VEHICLE_VALID_CHECK_OR_RETURN("getConstraintType");
	return PyLong_FromLong(m_vehicle->GetUserConstraintType());
}


PyObject *KX_VehicleWrapper::PyGetCurrentSpeedKmh(PyObject *args)
{
	VEHICLE_VALID_CHECK_OR_RETURN("getCurrentSpeedKmh");
	return PyFloat_FromDouble(m_vehicle->GetCurrentSpeedKmHour());
}

PyObject *KX_VehicleWrapper::PyGetCurrentSpeedMps(PyObject *args)
{
	VEHICLE_VALID_CHECK_OR_RETURN("getCurrentSpeedMps");
	return PyFloat_FromDouble(m_vehicle->GetCurrentSpeedMps());
}

PyObject *KX_VehicleWrapper::PyGetForwardVector(PyObject *args)
{
	VEHICLE_VALID_CHECK_OR_RETURN("getForwardVector");
	return PyObjectFrom(m_vehicle->GetForwardVector());
}

PyObject *KX_VehicleWrapper::PyGetCoordinateSystem(PyObject *args)
{
	VEHICLE_VALID_CHECK_OR_RETURN("getCoordinateSystem");
	int rightIndex, upIndex, forwardIndex;
	m_vehicle->GetCoordinateSystem(&rightIndex, &upIndex, &forwardIndex);
	return Py_BuildValue("(iii)", rightIndex, upIndex, forwardIndex);
}

PyObject *KX_VehicleWrapper::PySetCoordinateSystem(PyObject *args)
{
	int rightIndex, upIndex, forwardIndex;

	VEHICLE_VALID_CHECK_OR_RETURN("setCoordinateSystem");

	if (!PyArg_ParseTuple(args, "iii:setCoordinateSystem", &rightIndex, &upIndex, &forwardIndex)) {
		return nullptr;
	}

	const bool inRange = (rightIndex >= 0 && rightIndex <= 2) &&
	                      (upIndex >= 0 && upIndex <= 2) &&
	                      (forwardIndex >= 0 && forwardIndex <= 2);
	const bool isPermutation = inRange && (rightIndex != upIndex) &&
	                           (rightIndex != forwardIndex) && (upIndex != forwardIndex);
	if (!isPermutation) {
		PyErr_SetString(PyExc_AttributeError,
		                "setCoordinateSystem(...): rightIndex, upIndex and forwardIndex must be a permutation of (0, 1, 2).");
		return nullptr;
	}

	m_vehicle->SetCoordinateSystem(rightIndex, upIndex, forwardIndex);
	Py_RETURN_NONE;
}

PyObject *KX_VehicleWrapper::PyResetSuspension(PyObject *args)
{
	VEHICLE_VALID_CHECK_OR_RETURN("resetSuspension");
	m_vehicle->ResetSuspension();
	Py_RETURN_NONE;
}

PyObject *KX_VehicleWrapper::PyGetWheelConfig(PyObject *args)
{
	int wheelIndex;
	if (!PyArg_ParseTuple(args, "i:getWheelConfig", &wheelIndex)) {
		return nullptr;
	}
	WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "getWheelConfig");

	PHY_VehicleWheelConfig config;
	if (!m_vehicle->GetWheelConfig(wheelIndex, &config)) {
		PyErr_Format(PyExc_ValueError, "getWheelConfig(...): wheel index %d has no config.", wheelIndex);
		return nullptr;
	}

	//axleDir round-trips the public sign convention passed to addWheel(), not Bullet's internal one.
	mt::vec3 publicAxleDir = -config.axleDirection;

	return Py_BuildValue("{s:i,s:N,s:N,s:N,s:f,s:f,s:O,s:O}",
	                      "index", wheelIndex,
	                      "connectionPoint", PyObjectFrom(config.connectionPoint),
	                      "downDirection", PyObjectFrom(config.downDirection),
	                      "axleDirection", PyObjectFrom(publicAxleDir),
	                      "suspensionRestLength", config.suspensionRestLength,
	                      "wheelRadius", config.wheelRadius,
	                      "hasSteering", config.hasSteering ? Py_True : Py_False,
	                      "isDriveWheel", config.isDriveWheel ? Py_True : Py_False);
}

PyObject *KX_VehicleWrapper::PyGetWheelState(PyObject *args)
{
	int wheelIndex;
	if (!PyArg_ParseTuple(args, "i:getWheelState", &wheelIndex)) {
		return nullptr;
	}
	WHEEL_INDEX_CHECK_OR_RETURN(wheelIndex, "getWheelState");

	PHY_VehicleWheelState state;
	if (!m_vehicle->GetWheelState(wheelIndex, &state)) {
		PyErr_Format(PyExc_ValueError, "getWheelState(...): wheel index %d has no state.", wheelIndex);
		return nullptr;
	}

	return Py_BuildValue("{s:i,s:K,s:N,s:N,s:f,s:O,s:N,s:N,s:f,s:N,s:N}",
	                      "index", wheelIndex,
	                      "physicsTick", state.physicsTick,
	                      "worldPosition", PyObjectFrom(state.worldPosition),
	                      "worldOrientation", PyObjectFrom(state.worldOrientation.ToMatrix()),
	                      "rotation", state.rotation,
	                      "isInContact", state.isInContact ? Py_True : Py_False,
	                      "contactNormal", PyObjectFrom(state.contactNormal),
	                      "contactPoint", PyObjectFrom(state.contactPoint),
	                      "suspensionForce", state.suspensionForce,
	                      "hardPointWorld", PyObjectFrom(state.hardPointWS),
	                      "wheelDirectionWorld", PyObjectFrom(state.wheelDirectionWS));
}

PyObject *KX_VehicleWrapper::PySavePreset(PyObject *args)
{
	const char *path;
	VEHICLE_VALID_CHECK_OR_RETURN("savePreset");
	if (!PyArg_ParseTuple(args, "s:savePreset", &path)) {
		return nullptr;
	}
	KX_VehiclePreset preset;
	std::string error;
	if (!KX_CaptureVehiclePreset(m_vehicle, &preset, &error) ||
	    !KX_SaveVehiclePresetAtomic(path, preset, &error)) {
		PyErr_SetString(PyExc_ValueError, error.c_str());
		return nullptr;
	}
	Py_RETURN_NONE;
}

PyObject *KX_VehicleWrapper::PyLoadPreset(PyObject *args)
{
	const char *path;
	VEHICLE_VALID_CHECK_OR_RETURN("loadPreset");
	if (!PyArg_ParseTuple(args, "s:loadPreset", &path)) {
		return nullptr;
	}
	KX_VehiclePreset preset;
	std::string error;
	if (!KX_LoadVehiclePreset(path, &preset, &error) ||
	    !KX_ApplyVehiclePreset(m_vehicle, preset, &error)) {
		PyErr_SetString(PyExc_ValueError, error.c_str());
		return nullptr;
	}
	Py_RETURN_NONE;
}

PyObject *KX_VehicleWrapper::PyRebuildPreset(PyObject *args)
{
	const char *path;
	PyObject *wheelObjects;
	VEHICLE_VALID_CHECK_OR_RETURN("rebuildPreset");
	if (!PyArg_ParseTuple(args, "sO:rebuildPreset", &path, &wheelObjects)) {
		return nullptr;
	}

	KX_VehiclePreset preset;
	std::string error;
	if (!KX_LoadVehiclePreset(path, &preset, &error)) {
		PyErr_SetString(PyExc_ValueError, ("rebuildPreset(...): " + error).c_str());
		return nullptr;
	}
	PyObject *sequence = PySequence_Fast(wheelObjects,
	                                     "rebuildPreset(...): wheelObjects must be a sequence of game objects");
	if (!sequence) {
		return nullptr;
	}
	const Py_ssize_t numObjects = PySequence_Fast_GET_SIZE(sequence);
	if (numObjects != (Py_ssize_t)preset.wheels.size()) {
		Py_DECREF(sequence);
		PyErr_Format(PyExc_ValueError,
		             "rebuildPreset(...): preset has %d wheel(s), but wheelObjects has %d object(s)",
		             (int)preset.wheels.size(), (int)numObjects);
		return nullptr;
	}

	std::vector<KX_GameObject *> gameObjects;
	gameObjects.reserve(numObjects);
	for (Py_ssize_t i = 0; i < numObjects; ++i) {
		KX_GameObject *gameOb;
		if (!ConvertPythonToGameObject(KX_GetActiveScene()->GetLogicManager(),
		                               PySequence_Fast_GET_ITEM(sequence, i), &gameOb, false,
		                               "vehicle.rebuildPreset(...): wheelObjects item")) {
			Py_DECREF(sequence);
			return nullptr;
		}
		if (!gameOb->GetNode()) {
			Py_DECREF(sequence);
			PyErr_Format(PyExc_ValueError,
			             "rebuildPreset(...): wheelObjects[%d] has no scene node", (int)i);
			return nullptr;
		}
		if (gameOb->GetPhysicsController()) {
			Py_DECREF(sequence);
			PyErr_Format(PyExc_ValueError,
			             "rebuildPreset(...): wheelObjects[%d] has an active physics/collision controller "
			             "(even if suspended); its raycast can self-collide with the suspension. Use a "
			             "plain Empty with Physics Type = 'No Collision' for wheel objects.",
			             (int)i);
			return nullptr;
		}
		gameObjects.push_back(gameOb);
	}
	Py_DECREF(sequence);

	for (size_t i = 0; i < gameObjects.size(); ++i) {
		for (size_t j = i + 1; j < gameObjects.size(); ++j) {
			if (gameObjects[i] == gameObjects[j]) {
				PyErr_Format(PyExc_ValueError,
				             "rebuildPreset(...): wheelObjects[%d] and wheelObjects[%d] are the same object",
				             (int)i, (int)j);
				return nullptr;
			}
		}
	}

	PHY_IPhysicsEnvironment *physicsEnvironment = KX_GetPhysicsEnvironment();
	PHY_IPhysicsController *chassis = m_vehicle->GetChassisController();
	if (!physicsEnvironment || !chassis) {
		PyErr_SetString(PyExc_RuntimeError,
		                "rebuildPreset(...): physics environment or vehicle chassis is no longer available");
		return nullptr;
	}

	/* All fallible Python/file/scene work happened above. The candidate is built
	 * before the wrapper releases the old vehicle, then swapped before the next
	 * physics tick can run. */
	PHY_IVehicle *candidate = physicsEnvironment->CreateVehicle(chassis);
	if (!candidate) {
		PyErr_SetString(PyExc_RuntimeError, "rebuildPreset(...): could not create replacement vehicle");
		return nullptr;
	}
	for (int i = 0; i < (int)preset.wheels.size(); ++i) {
		const KX_VehiclePresetWheel &wheel = preset.wheels[i];
		candidate->AddWheel(new KX_MotionState(gameObjects[i]->GetNode()),
		                    wheel.connectionPoint, wheel.downDirection, -wheel.axleDirection,
		                    wheel.suspensionRestLength, wheel.wheelRadius, wheel.hasSteering);
	}
	if (!KX_ApplyVehiclePreset(candidate, preset, &error)) {
		physicsEnvironment->DestroyVehicle(candidate);
		PyErr_SetString(PyExc_RuntimeError, ("rebuildPreset(...): candidate validation failed: " + error).c_str());
		return nullptr;
	}

	PHY_IVehicle *oldVehicle = m_vehicle;
	oldVehicle->SetInvalidationCallback(nullptr, nullptr);
	m_vehicle = candidate;
	candidate->SetInvalidationCallback(&KX_VehicleWrapper::OnVehicleInvalidated, this);
	physicsEnvironment->DestroyVehicle(oldVehicle);
	Py_RETURN_NONE;
}





//python specific stuff
PyTypeObject KX_VehicleWrapper::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_VehicleWrapper",
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
	&EXP_PyObjectPlus::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_VehicleWrapper::Methods[] = {
	{"addWheel", (PyCFunction)KX_VehicleWrapper::sPyAddWheel, METH_VARARGS},
	{"getNumWheels", (PyCFunction)KX_VehicleWrapper::sPyGetNumWheels, METH_VARARGS},
	{"getWheelOrientationQuaternion", (PyCFunction)KX_VehicleWrapper::sPyGetWheelOrientationQuaternion, METH_VARARGS},
	{"getWheelRotation", (PyCFunction)KX_VehicleWrapper::sPyGetWheelRotation, METH_VARARGS},
	{"getWheelPosition", (PyCFunction)KX_VehicleWrapper::sPyGetWheelPosition, METH_VARARGS},
	{"getConstraintId", (PyCFunction)KX_VehicleWrapper::sPyGetConstraintId, METH_VARARGS},
	{"getConstraintType", (PyCFunction)KX_VehicleWrapper::sPyGetConstraintType, METH_VARARGS},
	{"setSteeringValue", (PyCFunction)KX_VehicleWrapper::sPySetSteeringValue, METH_VARARGS},
	{"applyEngineForce", (PyCFunction)KX_VehicleWrapper::sPyApplyEngineForce, METH_VARARGS},
	{"applyBraking", (PyCFunction)KX_VehicleWrapper::sPyApplyBraking, METH_VARARGS},
	{"setTyreFriction", (PyCFunction)KX_VehicleWrapper::sPySetTyreFriction, METH_VARARGS},
	{"setWheelIsDriveWheel", (PyCFunction)KX_VehicleWrapper::sPySetWheelIsDriveWheel, METH_VARARGS},
	{"setSuspensionStiffness", (PyCFunction)KX_VehicleWrapper::sPySetSuspensionStiffness, METH_VARARGS},
	{"setSuspensionDamping", (PyCFunction)KX_VehicleWrapper::sPySetSuspensionDamping, METH_VARARGS},
	{"setSuspensionCompression", (PyCFunction)KX_VehicleWrapper::sPySetSuspensionCompression, METH_VARARGS},
	{"setRollInfluence", (PyCFunction)KX_VehicleWrapper::sPySetRollInfluence, METH_VARARGS},
	{"getCurrentSpeedKmh", (PyCFunction)KX_VehicleWrapper::sPyGetCurrentSpeedKmh, METH_VARARGS},
	{"getCurrentSpeedMps", (PyCFunction)KX_VehicleWrapper::sPyGetCurrentSpeedMps, METH_VARARGS},
	{"getForwardVector", (PyCFunction)KX_VehicleWrapper::sPyGetForwardVector, METH_VARARGS},
	{"getCoordinateSystem", (PyCFunction)KX_VehicleWrapper::sPyGetCoordinateSystem, METH_VARARGS},
	{"setCoordinateSystem", (PyCFunction)KX_VehicleWrapper::sPySetCoordinateSystem, METH_VARARGS},
	{"resetSuspension", (PyCFunction)KX_VehicleWrapper::sPyResetSuspension, METH_VARARGS},
	{"getWheelConfig", (PyCFunction)KX_VehicleWrapper::sPyGetWheelConfig, METH_VARARGS},
	{"getWheelState", (PyCFunction)KX_VehicleWrapper::sPyGetWheelState, METH_VARARGS},
	{"savePreset", (PyCFunction)KX_VehicleWrapper::sPySavePreset, METH_VARARGS},
	{"loadPreset", (PyCFunction)KX_VehicleWrapper::sPyLoadPreset, METH_VARARGS},
	{"rebuildPreset", (PyCFunction)KX_VehicleWrapper::sPyRebuildPreset, METH_VARARGS},
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_VehicleWrapper::Attributes[] = {
	EXP_PYATTRIBUTE_RW_FUNCTION("rayMask", KX_VehicleWrapper, pyattr_get_ray_mask, pyattr_set_ray_mask),
	EXP_PYATTRIBUTE_RO_FUNCTION("constraint_id", KX_VehicleWrapper, pyattr_get_constraintId),
	EXP_PYATTRIBUTE_RO_FUNCTION("constraint_type", KX_VehicleWrapper, pyattr_get_constraintType),
	EXP_PYATTRIBUTE_NULL    //Sentinel
};

PyObject *KX_VehicleWrapper::pyattr_get_constraintId(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_VehicleWrapper *self = static_cast<KX_VehicleWrapper *>(self_v);
	if (raise_exc_invalid(self->m_vehicle, "constraint_id")) {
		return nullptr;
	}
	return PyLong_FromLong(self->m_vehicle->GetUserConstraintId());
}

PyObject *KX_VehicleWrapper::pyattr_get_constraintType(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	return PyLong_FromLong(PHY_VEHICLE_CONSTRAINT);
}

PyObject *KX_VehicleWrapper::pyattr_get_ray_mask(EXP_PyObjectPlus *self, const struct EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_VehicleWrapper *wrapper = static_cast<KX_VehicleWrapper *>(self);
	if (raise_exc_invalid(wrapper->m_vehicle, "rayMask")) {
		return nullptr;
	}
	/* PHY_IVehicle exposes a signed short, but ray masks are a 16-bit bit
	 * field.  The default 0xffff must round-trip to Python as 65535, not -1. */
	return PyLong_FromUnsignedLong((unsigned short)wrapper->m_vehicle->GetRayCastMask());
}

int KX_VehicleWrapper::pyattr_set_ray_mask(EXP_PyObjectPlus *self, const struct EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_VehicleWrapper *wrapper = static_cast<KX_VehicleWrapper *>(self);

	if (!wrapper->m_vehicle) {
		PyErr_SetString(PyExc_ReferenceError,
		                "rayMask = int: KX_VehicleWrapper, vehicle no longer exists (chassis or constraint was removed).");
		return PY_SET_ATTR_FAIL;
	}

	int mask = PyLong_AsLong(value);

	if (mask == -1 && PyErr_Occurred()) {
		PyErr_SetString(PyExc_TypeError, "rayMask = int: KX_VehicleWrapper, expected an int bit field");
		return PY_SET_ATTR_FAIL;
	}

	if (mask == 0 || mask & ~((1 << OB_MAX_COL_MASKS) - 1)) {
		PyErr_Format(PyExc_AttributeError, "rayMask = int: KX_VehicleWrapper, expected a int bit field, 0 < rayMask < %i", (1 << OB_MAX_COL_MASKS));
		return PY_SET_ATTR_FAIL;
	}

	wrapper->m_vehicle->SetRayCastMask(mask);

	return PY_SET_ATTR_SUCCESS;
}

#endif // WITH_PYTHON
