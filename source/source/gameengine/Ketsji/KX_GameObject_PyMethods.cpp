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
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 *
 * The Original Code is: all of this file.
 *
 * Contributor(s): none yet.
 *
 * ***** END GPL LICENSE BLOCK *****
 * KX_GameObject Python methods (Py* and EXP_PYMETHODDEF_DOC).
 */

/** \file gameengine/Ketsji/KX_GameObject_PyMethods.cpp
 *  \ingroup ketsji
 */

#ifdef _MSC_VER
/* This warning tells us about truncation of __long__ stl-generated names.
 * It can occasionally cause DevStudio to have internal compiler warnings. */
#  pragma warning( disable:4786 )
#endif

#include <cstring>
#include <cmath>
#include <cfloat>

#include "CM_WorkCounters.h"
#include "CM_Trace.h"
#include "KX_GameObject.h"
#include "KX_RuntimePropertyRegistry.h"
#include "KX_PythonComponent.h"
#include "KX_Camera.h" // only for their ::Type
#include "KX_AnimationEventManager.h"
#include "KX_LightObject.h"  // only for their ::Type
#include "KX_FontObject.h"  // only for their ::Type
#include "RAS_Mesh.h"
#include "RAS_MeshUser.h"
#include "RAS_BoundingBoxManager.h"
#include "RAS_Deformer.h"
#include "KX_NavMeshObject.h"
#include "KX_Mesh.h"
#include "KX_PolyProxy.h"
#include "KX_BlenderMaterial.h"
#include "SG_Controller.h"
#include "PHY_IGraphicController.h"
#include "PHY_IPhysicsEnvironment.h"
#include "PHY_IVehicle.h"
#include "KX_VehicleWrapper.h"
#include "SG_Node.h"
#include "SG_Familly.h"
#include "KX_ClientObjectInfo.h"
#include "RAS_BucketManager.h"
#include "KX_RayCast.h"
#include "KX_Globals.h"
#include "KX_PyMath.h"
#include "SCA_IActuator.h"
#include "SCA_ISensor.h"
#include "SCA_AnimationEventSensor.h"
#include "SCA_IController.h"
#include "KX_NetworkMessageScene.h" //Needed for sendMessage()
#include "KX_ObstacleSimulation.h"
#include "KX_Scene.h"
#include "KX_LodLevel.h"
#include "KX_LodManager.h"
#include "KX_ImpostorAtlasDeformer.h"
#include "KX_DentDeformer.h"
#include "KX_BoundingBox.h"
#include "SG_CullingNode.h"
#include "KX_BatchGroup.h"
#include "KX_CollisionContactPoints.h"
#include "RAS_ParticleBuffer.h"
#include "RAS_ParticleShaderCache.h"
#include "DNA_mesh_types.h"
#include "DNA_meshdata_types.h"
#include "KX_ParticleSystem.h"

#include "BKE_object.h"
#include "BKE_global.h"
#include "BKE_main.h"
#include "BLI_listbase.h"
#include "DNA_group_types.h"
#include "DNA_object_types.h"

#include "BL_BlenderDataConversion.h" // For BL_ConvertDeformer.
#include "BL_ConvertObjectInfo.h"
#include "BL_ActionManager.h"
#include "BL_Action.h"

#include "EXP_PyObjectPlus.h" /* python stuff */
#include "EXP_ListWrapper.h"
#include "BLI_utildefines.h"
#include "BLI_math.h"

#ifdef WITH_PYTHON
#  include "EXP_PythonCallBack.h"
#  include "python_utildefines.h"
#  include "KX_PyConstraintBinding.h"
#endif

// Component stuff
#include "DNA_python_component_types.h"

// This file defines relationships between parents and children
// in the game engine.

#include "KX_NodeRelationships.h"

#include "BLI_math.h"

#include "CM_Message.h"

#ifdef WITH_PYTHON

#define PYTHON_CHECK_PHYSICS_CONTROLLER(obj, attr, ret) \
	if (!(obj)->GetPhysicsController()) { \
		PyErr_Format(PyExc_AttributeError, "KX_GameObject.%s, is missing a physics controller", (attr)); \
		return (ret); \
	}


PyObject *KX_GameObject::PyApplyForce(PyObject *args)
{
	int local = 0;
	PyObject *pyvect;

	if (PyArg_ParseTuple(args, "O|i:applyForce", &pyvect, &local)) {
		mt::vec3 force;
		if (PyVecTo(pyvect, force)) {
			ApplyForce(force, (local != 0));
			Py_RETURN_NONE;
		}
	}
	return nullptr;
}

PyObject *KX_GameObject::PyApplyTorque(PyObject *args)
{
	int local = 0;
	PyObject *pyvect;

	if (PyArg_ParseTuple(args, "O|i:applyTorque", &pyvect, &local)) {
		mt::vec3 torque;
		if (PyVecTo(pyvect, torque)) {
			ApplyTorque(torque, (local != 0));
			Py_RETURN_NONE;
		}
	}
	return nullptr;
}

PyObject *KX_GameObject::PyApplyRotation(PyObject *args)
{
	int local = 0;
	PyObject *pyvect;

	if (PyArg_ParseTuple(args, "O|i:applyRotation", &pyvect, &local)) {
		mt::vec3 rotation;
		if (PyVecTo(pyvect, rotation)) {
			ApplyRotation(rotation, (local != 0));
			Py_RETURN_NONE;
		}
	}
	return nullptr;
}

PyObject *KX_GameObject::PyApplyMovement(PyObject *args)
{
	int local = 0;
	PyObject *pyvect;

	if (PyArg_ParseTuple(args, "O|i:applyMovement", &pyvect, &local)) {
		mt::vec3 movement;
		if (PyVecTo(pyvect, movement)) {
			ApplyMovement(movement, (local != 0));
			Py_RETURN_NONE;
		}
	}
	return nullptr;
}

PyObject *KX_GameObject::PyGetLinearVelocity(PyObject *args)
{
	// only can get the velocity if we have a physics object connected to us...
	int local = 0;

	if (PyArg_ParseTuple(args, "|i:getLinearVelocity", &local)) {
		return PyObjectFrom(GetLinearVelocity((local != 0)));
	}
	else {
		return nullptr;
	}
}

PyObject *KX_GameObject::PySetLinearVelocity(PyObject *args)
{
	int local = 0;
	PyObject *pyvect;

	if (PyArg_ParseTuple(args, "O|i:setLinearVelocity", &pyvect, &local)) {
		mt::vec3 velocity;
		if (PyVecTo(pyvect, velocity)) {
			SetLinearVelocity(velocity, (local != 0));
			Py_RETURN_NONE;
		}
	}
	return nullptr;
}

PyObject *KX_GameObject::PyGetAngularVelocity(PyObject *args)
{
	// only can get the velocity if we have a physics object connected to us...
	int local = 0;

	if (PyArg_ParseTuple(args, "|i:getAngularVelocity", &local)) {
		return PyObjectFrom(GetAngularVelocity((local != 0)));
	}
	else {
		return nullptr;
	}
}

PyObject *KX_GameObject::PySetAngularVelocity(PyObject *args)
{
	int local = 0;
	PyObject *pyvect;

	if (PyArg_ParseTuple(args, "O|i:setAngularVelocity", &pyvect, &local)) {
		mt::vec3 velocity;
		if (PyVecTo(pyvect, velocity)) {
			SetAngularVelocity(velocity, (local != 0));
			Py_RETURN_NONE;
		}
	}
	return nullptr;
}

PyObject *KX_GameObject::PySetDamping(PyObject *args)
{
	float linear;
	float angular;

	if (!PyArg_ParseTuple(args, "ff:setDamping", &linear, &angular)) {
		return nullptr;
	}

	SetDamping(linear, angular);
	Py_RETURN_NONE;
}





PyObject *KX_GameObject::PySetCcdMotionThreshold(PyObject *args)
{
  float motion_threshold;

  if (!PyArg_ParseTuple(args, "f:setCcdMotionThreshold", &motion_threshold)) {
    return nullptr;
  }

  if ((motion_threshold < 0.0f) || (motion_threshold > 200.0f)) {
    PyErr_SetString(PyExc_TypeError,
                    "gameOb.setCcdMotionThreshold: KX_GameObject, "
                    "expected a float in range 0.0 - 200.0");
    return nullptr;
  }

  setCcdMotionThreshold(motion_threshold);
  Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetCcdSweptSphereRadius(PyObject *args)
{
  float swept_sphere_radius;

  if (!PyArg_ParseTuple(args, "f:setCcdSweptSphereRadius", &swept_sphere_radius)) {
    return nullptr;
  }

  if ((swept_sphere_radius < 0.0f) || (swept_sphere_radius > 200.0f)) {
    PyErr_SetString(PyExc_TypeError,
                    "gameOb.setCcdSweptSphereRadius: KX_GameObject, "
                    "expected a float in range 0.0 - 200.0");
    return nullptr;
  }

  setCcdSweptSphereRadius(swept_sphere_radius);
  Py_RETURN_NONE;
}




PyObject *KX_GameObject::PySetSoftLinStiff(PyObject *args)
{
  float linstiff;

  if (!PyArg_ParseTuple(args, "f:setSoftLinearStiffness", &linstiff)) {
    return nullptr;
  }

  if ((linstiff < 0.0f) || (linstiff > 1.0f)) {
    PyErr_SetString(PyExc_TypeError,
                    "gameOb.setSoftLinearStiffness: KX_GameObject, "
                    "expected a float in range 0.0 - 1.0");
    return nullptr;
  }

  SetSoftLinStiff(linstiff);
  Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetSoftAngStiff(PyObject *args)
{
  float angstiff;

  if (!PyArg_ParseTuple(args, "f:setSoftAngularStiffness", &angstiff)) {
    return nullptr;
  }

  if ((angstiff < 0.0f) || (angstiff > 1.0f)) {
    PyErr_SetString(PyExc_TypeError,
                    "gameOb.setSoftAngularStiffness: KX_GameObject, "
                    "expected a float in range 0.0 - 1.0");
    return nullptr;
  }

  SetSoftAngStiff(angstiff);
  Py_RETURN_NONE;
}


PyObject *KX_GameObject::PySetSoftVolume(PyObject *args)
{
  float volume;

  if (!PyArg_ParseTuple(args, "f:setSoftVolume", &volume)) {
    return nullptr;
  }

  if ((volume < 0.0f) || (volume > 1.0f)) {
    PyErr_SetString(PyExc_TypeError,
                    "gameOb.setSoftVolume: KX_GameObject, "
                    "expected a float in range 0.0 - 1.0");
    return nullptr;
  }

  SetSoftVolume(volume);
  Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetSoftVsRigidHardness(PyObject *args)
{
  float hardness;

  if (!PyArg_ParseTuple(args, "f:setSoftVsRigidHardness", &hardness)) {
    return nullptr;
  }

  if ((hardness < 0.0f) || (hardness > 1.0f)) {
    PyErr_SetString(PyExc_TypeError,
                    "gameOb.setSoftVsRigidHardness: KX_GameObject, "
                    "expected a float in range 0.0 - 1.0");
    return nullptr;
  }

  SetSoftVsRigidHardness(hardness);
  Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetSoftVsKineticHardness(PyObject *args)
{
  float hardness;

  if (!PyArg_ParseTuple(args, "f:setSoftVsKineticHardness", &hardness)) {
    return nullptr;
  }

  if ((hardness < 0.0f) || (hardness > 1.0f)) {
    PyErr_SetString(PyExc_TypeError,
                    "gameOb.setSoftVsKineticHardness: KX_GameObject, "
                    "expected a float in range 0.0 - 1.0");
    return nullptr;
  }

  SetSoftVsKineticHardness(hardness);
  Py_RETURN_NONE;
}






PyObject *KX_GameObject::PySetSoftVsSoftHardness(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftVsSoftHardness", &val)) {
        return nullptr;
    }
    if ((val < 0.0f) || (val > 1.0f)) {
        PyErr_SetString(PyExc_TypeError,
                            "gameOb.setSoftVsSoftHardness: KX_GameObject, "
                            "expected a float in range 0.0 - 1.0");
        return nullptr;
    }
    SetSoftVsSoftHardness(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetSoftVsRigidImpulseSplitCluster(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftVsRigidImpulseSplitCluster", &val)) {
        return nullptr;
    }
    if ((val < 0.0f) || (val > 1.0f)) {
        PyErr_SetString(PyExc_TypeError,
                            "gameOb.setSoftVsRigidImpulseSplitCluster: KX_GameObject, "
                            "expected a float in range 0.0 - 1.0");
        return nullptr;
    }
    SetSoftVsRigidImpulseSplitCluster(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetSoftVsKineticImpulseSplitCluster(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftVsKineticImpulseSplitCluster", &val)) {
        return nullptr;
    }
    if ((val < 0.0f) || (val > 1.0f)) {
        PyErr_SetString(PyExc_TypeError,
                            "gameOb.setSoftVsKineticImpulseSplitCluster: KX_GameObject, "
                            "expected a float in range 0.0 - 1.0");
        return nullptr;
    }
    SetSoftVsKineticImpulseSplitCluster(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetSoftVsSoftImpulseSplitCluster(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftVsSoftImpulseSplitCluster", &val)) {
        return nullptr;
    }
    if ((val < 0.0f) || (val > 1.0f)) {
        PyErr_SetString(PyExc_TypeError,
                            "gameOb.setSoftVsSoftImpulseSplitCluster: KX_GameObject, "
                            "expected a float in range 0.0 - 1.0");
        return nullptr;
    }
    SetSoftVsSoftImpulseSplitCluster(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetVelocitiesCorrectionFactor(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftVelocitiesCorrectionFactor", &val)) {
        return nullptr;
    }
    SetVelocitiesCorrectionFactor(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetDampingCoefficient(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftDampingCoefficient", &val)) {
        return nullptr;
    }
    SetDampingCoefficient(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetDragCoefficient(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftDragCoefficient", &val)) {
        return nullptr;
    }
    SetDragCoefficient(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetLiftCoefficient(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftLiftCoefficient", &val)) {
        return nullptr;
    }
    SetLiftCoefficient(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetPressureCoefficient(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftPressureCoefficient", &val)) {
        return nullptr;
    }
    SetPressureCoefficient(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetVolumeConversationCoefficient(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftVolumeConversationCoefficient", &val)) {
        return nullptr;
    }
    SetVolumeConversationCoefficient(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetDynamicFrictionCoefficient(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftDynamicFrictionCoefficient", &val)) {
        return nullptr;
    }
    SetDynamicFrictionCoefficient(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetPoseMatchingCoefficient(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftPoseMatchingCoefficient", &val)) {
        return nullptr;
    }
    SetPoseMatchingCoefficient(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetRigidContactsHardness(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftRigidContactsHardness", &val)) {
        return nullptr;
    }
    SetRigidContactsHardness(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetKineticContactsHardness(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftKineticContactsHardness", &val)) {
        return nullptr;
    }
    SetKineticContactsHardness(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetSoftContactsHardness(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftContactsHardness", &val)) {
        return nullptr;
    }
    SetSoftContactsHardness(val);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetAnchorsHardness(PyObject *args)
{
    float val;
    if (!PyArg_ParseTuple(args, "f:setSoftAnchorsHardness", &val)) {
        return nullptr;
    }
    SetAnchorsHardness(val);
    Py_RETURN_NONE;
}






PyObject *KX_GameObject::PySetVelocitySolverIterations(PyObject *args)
{
    int iterations;
    if (!PyArg_ParseTuple(args, "i:setSoftVelocitySolverIterations", &iterations)) {
        return nullptr;
    }
    SetVelocitySolverIterations(iterations);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetPositionSolverIterations(PyObject *args)
{
    int iterations;
    if (!PyArg_ParseTuple(args, "i:setSoftPositionSolverIterations", &iterations)) {
        return nullptr;
    }
    SetPositionSolverIterations(iterations);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetDriftSolverIterations(PyObject *args)
{
    int iterations;
    if (!PyArg_ParseTuple(args, "i:setSoftDriftSolverIterations", &iterations)) {
        return nullptr;
    }
    SetDriftSolverIterations(iterations);
    Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetClusterSolverIterations(PyObject *args)
{
    int iterations;
    if (!PyArg_ParseTuple(args, "i:setSoftClusterSolverIterations", &iterations)) {
        return nullptr;
    }
    SetClusterSolverIterations(iterations);
    Py_RETURN_NONE;
}





PyObject *KX_GameObject::PySetSoftPoseMatching(PyObject *args)
{
    int enableShapeMatching;
    if (!PyArg_ParseTuple(args, "p:setSoftPoseMatching", &enableShapeMatching)) {
        return nullptr;
    }
    SetSoftPoseMatching(enableShapeMatching != 0);
    Py_RETURN_NONE;
}




PyObject *KX_GameObject::PySetVisible(PyObject *args)
{
	int visible, recursive = 0;
	if (!PyArg_ParseTuple(args, "i|i:setVisible", &visible, &recursive)) {
		return nullptr;
	}

	SetVisible(visible ? true : false, recursive ? true : false);
	Py_RETURN_NONE;

}



PyObject *KX_GameObject::PySetHalfAnimations(PyObject *args)
{
	int halfanimations = 0;
	if (!PyArg_ParseTuple(args, "i:setHalfAnimations", &halfanimations)) {
		return nullptr;
	}

	SetHalfAnimations(halfanimations ? true : false);
	Py_RETURN_NONE;

}


PyObject *KX_GameObject::PySetOcclusion(PyObject *args)
{
	int occlusion, recursive = 0;

	if (!PyArg_ParseTuple(args, "i|i:setOcclusion", &occlusion, &recursive)) {
		return nullptr;
	}

	SetOccluder(occlusion ? true : false, recursive ? true : false);
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PyGetVelocity(PyObject *args)
{
	// only can get the velocity if we have a physics object connected to us...
	mt::vec3 point = mt::zero3;
	PyObject *pypos = nullptr;

	if (!PyArg_ParseTuple(args, "|O:getVelocity", &pypos) || (pypos && !PyVecTo(pypos, point))) {
		return nullptr;
	}

	return PyObjectFrom(GetVelocity(point));
}

PyObject *KX_GameObject::PyGetReactionForce()
{
	// only can get the velocity if we have a physics object connected to us...

	// XXX - Currently not working with bullet intergration, see KX_BulletPhysicsController.cpp's getReactionForce
#if 0
	if (GetPhysicsController1()) {
		return PyObjectFrom(GetPhysicsController1()->getReactionForce());
	}
	return PyObjectFrom(mt::zero3);
#endif

	return PyObjectFrom(mt::zero3);
}



PyObject *KX_GameObject::PyEnableRigidBody()
{
	if (m_physicsController) {
		m_physicsController->SetRigidBody(true);
	}

	Py_RETURN_NONE;
}



PyObject *KX_GameObject::PyDisableRigidBody()
{
	if (m_physicsController) {
		m_physicsController->SetRigidBody(false);
	}

	Py_RETURN_NONE;
}


PyObject *KX_GameObject::PySetParent(PyObject *args, PyObject *kwds)
{
	SCA_LogicManager *logicmgr = GetScene()->GetLogicManager();
	PyObject *pyobj;
	KX_GameObject *obj;
	int addToCompound = 1, ghost = 1;

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "O|ii:setParent", {"parent", "compound", "ghost", 0},
	                                   &pyobj, &addToCompound, &ghost)) {
		return nullptr; // Python sets a simple error
	}
	if (!ConvertPythonToGameObject(logicmgr, pyobj, &obj, true, "gameOb.setParent(obj): KX_GameObject")) {
		return nullptr;
	}

	if (obj) {
		SetParent(obj, addToCompound, ghost);
	}
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PyRemoveParent()
{
	RemoveParent();
	Py_RETURN_NONE;
}


PyObject *KX_GameObject::PySetCollisionMargin(PyObject *value)
{
	float collisionMargin = PyFloat_AsDouble(value);

	if (collisionMargin == -1 && PyErr_Occurred()) {
		PyErr_SetString(PyExc_TypeError, "expected a float");
		return nullptr;
	}

	PYTHON_CHECK_PHYSICS_CONTROLLER(this, "setCollisionMargin", nullptr);

	m_physicsController->SetMargin(collisionMargin);
	Py_RETURN_NONE;
}


PyObject *KX_GameObject::PyCollide(PyObject *value)
{
	KX_Scene *scene = GetScene();
	KX_GameObject *other;

	if (!ConvertPythonToGameObject(scene->GetLogicManager(), value, &other, false, "gameOb.collide(obj): KX_GameObject")) {
		return nullptr;
	}

	if (!m_physicsController || !other->GetPhysicsController()) {
		PyErr_SetString(PyExc_TypeError, "expected objects with physics controller");
		return nullptr;
	}

	PHY_IPhysicsEnvironment *env = scene->GetPhysicsEnvironment();
	PHY_CollisionTestResult testResult = env->CheckCollision(m_physicsController.get(), other->GetPhysicsController());

	PyObject *result = PyTuple_New(2);
	if (!testResult.collide) {
		PyTuple_SET_ITEM(result, 0, Py_False);
		PyTuple_SET_ITEM(result, 1, Py_None);

		Py_INCREF(Py_False);
		Py_INCREF(Py_None);
	}
	else {
		PyTuple_SET_ITEM(result, 0, Py_True);
		Py_INCREF(Py_True);

		if (testResult.collData) {
			KX_CollisionContactPointList *contactPointList = new KX_CollisionContactPointList(testResult.collData, testResult.isFirst, true);
			PyTuple_SET_ITEM(result, 1, contactPointList->NewProxy(true));
		}
		else {
			PyTuple_SET_ITEM(result, 1, Py_None);
			Py_INCREF(Py_None);
		}
	}

	return result;
}


PyObject *KX_GameObject::PyApplyImpulse(PyObject *args)
{
	PyObject *pyattach;
	PyObject *pyimpulse;
	int local = 0;

	PYTHON_CHECK_PHYSICS_CONTROLLER(this, "applyImpulse", nullptr);
	if (PyArg_ParseTuple(args, "OO|i:applyImpulse", &pyattach, &pyimpulse, &local)) {
		mt::vec3 attach;
		mt::vec3 impulse;
		if (PyVecTo(pyattach, attach) && PyVecTo(pyimpulse, impulse)) {
			m_physicsController->ApplyImpulse(attach, impulse, (local != 0));
			Py_RETURN_NONE;
		}

	}

	return nullptr;
}

PyObject *KX_GameObject::PySuspendPhysics(PyObject *args)
{
	int freeConstraints = false;

	if (!PyArg_ParseTuple(args, "|i:suspendPhysics", &freeConstraints)) {
		return nullptr;
	}

	SuspendPhysics(freeConstraints);

	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PyRestorePhysics()
{
	RestorePhysics();

	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySuspendAnimations()
{
	SuspendAnimations();

	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PyResumeAnimations()
{
	ResumeAnimations();

	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySuspendDynamics(PyObject *args)
{
	bool ghost = false;

	if (!PyArg_ParseTuple(args, "|b", &ghost)) {
		return nullptr;
	}

	if (m_physicsController) {
		m_physicsController->SuspendDynamics(ghost);
	}

	Py_RETURN_NONE;
}



PyObject *KX_GameObject::PyRestoreDynamics()
{
	// Child objects must be static, so we block changing to dynamic
	if (m_physicsController && !GetParent()) {
		m_physicsController->RestoreDynamics();
	}
	Py_RETURN_NONE;
}

//PyObject *KX_GameObject::PyAlignAxisToVect(PyObject *args, PyObject *kwds)
//{
//	ShowDeprecationWarning_func("alignAxisToVect", "lookAt");
//	Py_RETURN_NONE;
//}

PyObject *KX_GameObject::PyAlignAxisToVect(PyObject *args, PyObject *kwds)
{
	PyObject *pyvect;
	int axis = 2; //z axis is the default
	float fac = 1.0f;

	if (EXP_ParseTupleArgsAndKeywords(args, kwds, "O|if:alignAxisToVect", {"vect", "axis", "factor", 0},
	                                  &pyvect, &axis, &fac)) {
		mt::vec3 vect;
		if (PyVecTo(pyvect, vect)) {
			if (fac > 0.0f) {
				if (fac > 1.0f) {
					fac = 1.0f;
				}

				AlignAxisToVect(vect, axis, fac);
				NodeUpdate();
			}
			Py_RETURN_NONE;
		}
	}
	return nullptr;
}


PyObject *KX_GameObject::PyLookAt(PyObject *args, PyObject *kwds)
{
	PyObject *pyvect;
	int axis = 2; //z axis is the default
	float fac = 1.0f;

	if (EXP_ParseTupleArgsAndKeywords(args, kwds, "O|if:alignAxisToVect", {"vect", "axis", "factor", 0},
	                                  &pyvect, &axis, &fac)) {
		mt::vec3 vect;
		if (PyVecTo(pyvect, vect)) {
			if (fac > 0.0f) {
				if (fac > 1.0f) {
					fac = 1.0f;
				}

				AlignAxisToVect(vect, axis, fac);
				NodeUpdate();
			}
			Py_RETURN_NONE;
		}
	}
	return nullptr;
}

PyObject *KX_GameObject::PyGetAxisVect(PyObject *value)
{
	mt::vec3 vect;
	if (PyVecTo(value, vect)) {
		return PyObjectFrom(NodeGetWorldOrientation() * vect);
	}
	return nullptr;
}

PyObject *KX_GameObject::PyGetPhysicsId()
{
	return PyLong_FromUnsignedLongLong(KX_GetPhysicsControllerId(m_physicsController.get()));
}

PyObject *KX_GameObject::PyGetVehicle()
{
	if (m_vehicleConstraintId >= 0) {
		PHY_IPhysicsEnvironment *pe = GetScene()->GetPhysicsEnvironment();
		if (pe) {
			PHY_IVehicle *vehicle = pe->GetVehicleConstraint(m_vehicleConstraintId);
			if (vehicle) {
				KX_VehicleWrapper *pyWrapper = new KX_VehicleWrapper(vehicle);
				return pyWrapper->NewProxy(true);
			}
		}
	}
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PyGetVehicleSteeringWheel()
{
	if (!m_vehicleSteeringWheelName.empty() && GetScene()) {
		KX_GameObject *wheelObj = GetScene()->GetObjectList()->FindValue(m_vehicleSteeringWheelName);
		if (wheelObj) {
			return wheelObj->GetProxy();
		}
	}
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PyGetVehicleMaxTorque()
{
	return PyFloat_FromDouble(m_vehicleMaxTorque);
}

PyObject *KX_GameObject::PyGetVehicleMaxRPM()
{
	return PyFloat_FromDouble(m_vehicleMaxRPM);
}

PyObject *KX_GameObject::PyGetVehicleGearRatios()
{
	PyObject *tuple = PyTuple_New(m_vehicleGearRatios.size());
	for (size_t i = 0; i < m_vehicleGearRatios.size(); i++) {
		PyTuple_SET_ITEM(tuple, i, PyFloat_FromDouble(m_vehicleGearRatios[i]));
	}
	return tuple;
}

PyObject *KX_GameObject::PyGetVehicleGearboxType()
{
	return PyLong_FromLong(m_vehicleGearboxType);
}

static bool py_vehicle_float(PyObject *value, const char *name, float *out)
{
	const double v = PyFloat_AsDouble(value);
	if (PyErr_Occurred()) {
		return false;
	}
	if (!std::isfinite(v) || v < 0.0) {
		PyErr_Format(PyExc_ValueError, "gameOb.%s(value): value must be a finite number >= 0", name);
		return false;
	}
	if (v > FLT_MAX) {
		PyErr_Format(PyExc_OverflowError, "gameOb.%s(value): value exceeds the float range", name);
		return false;
	}
	*out = (float)v;
	return true;
}

PyObject *KX_GameObject::PySetVehicleMaxTorque(PyObject *value)
{
	float v;
	if (!py_vehicle_float(value, "setVehicleMaxTorque", &v)) {
		return nullptr;
	}
	SetVehicleMaxTorque(v);
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetVehicleMaxRPM(PyObject *value)
{
	float v;
	if (!py_vehicle_float(value, "setVehicleMaxRPM", &v)) {
		return nullptr;
	}
	SetVehicleMaxRPM(v);
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PySetVehicleGearRatios(PyObject *value)
{
	PyObject *seq = PySequence_Fast(value, "gameOb.setVehicleGearRatios(ratios): expected a list of numbers");
	if (!seq) {
		return nullptr;
	}
	std::vector<float> ratios;
	const Py_ssize_t n = PySequence_Fast_GET_SIZE(seq);
	for (Py_ssize_t i = 0; i < n; i++) {
		const double r = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(seq, i));
		if (PyErr_Occurred() || !std::isfinite(r)) {
			Py_DECREF(seq);
			if (!PyErr_Occurred()) {
				PyErr_SetString(PyExc_ValueError, "gameOb.setVehicleGearRatios(ratios): ratios must be finite numbers");
			}
			return nullptr;
		}
		if (r < -FLT_MAX || r > FLT_MAX) {
			Py_DECREF(seq);
			PyErr_SetString(PyExc_OverflowError, "gameOb.setVehicleGearRatios(ratios): ratio exceeds the float range");
			return nullptr;
		}
		ratios.push_back((float)r);
	}
	Py_DECREF(seq);
	SetVehicleGearRatios(ratios);
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PyGetPropertyNames()
{
	PyObject *list = ConvertKeysToPython();

	if (m_attr_dict) {
		PyObject *key, *value;
		Py_ssize_t pos = 0;

		while (PyDict_Next(m_attr_dict, &pos, &key, &value)) {
			PyList_Append(list, key);
		}
	}
	return list;
}

EXP_PYMETHODDEF_DOC_O(KX_GameObject, getDistanceTo,
                      "getDistanceTo(other): get distance to another point/KX_GameObject")
{
	mt::vec3 b;
	if (PyVecTo(value, b)) {
		return PyFloat_FromDouble((NodeGetWorldPosition() - b).Length());
	}
	PyErr_Clear();

	SCA_LogicManager *logicmgr = GetScene()->GetLogicManager();
	KX_GameObject *other;
	if (ConvertPythonToGameObject(logicmgr, value, &other, false, "gameOb.getDistanceTo(value): KX_GameObject")) {
		return PyFloat_FromDouble((NodeGetWorldPosition() - other->NodeGetWorldPosition()).Length());
	}

	return nullptr;
}

EXP_PYMETHODDEF_DOC(KX_GameObject, getCurvePoints,
                    "getCurvePoints(world=True): sample the first spline of a curve object\n"
                    "Returns a list of Vectors (world space by default, local space with world=False); empty if not a curve\n")
{
	int world = 1;
	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "|p:getCurvePoints", {"world", 0}, &world)) {
		return nullptr;
	}

	const std::vector<mt::vec3> points = BL_SampleCutscenePath(GetBlenderObject());
	const mt::mat3x4 trans = NodeGetWorldTransform();
	PyObject *list = PyList_New(points.size());
	for (unsigned int i = 0; i < points.size(); ++i) {
		PyList_SET_ITEM(list, i, PyObjectFrom(world ? (trans * points[i]) : points[i]));
	}
	return list;
}

EXP_PYMETHODDEF_DOC_O(KX_GameObject, getVectTo,
                      "getVectTo(other): get vector and the distance to another point/KX_GameObject\n"
                      "Returns a 3-tuple with (distance,worldVector,localVector)\n")
{
	mt::vec3 toPoint, fromPoint;
	mt::vec3 toDir, locToDir;
	float distance;

	SCA_LogicManager *logicmgr = GetScene()->GetLogicManager();
	PyObject *returnValue;

	if (!PyVecTo(value, toPoint)) {
		PyErr_Clear();

		KX_GameObject *other;
		if (ConvertPythonToGameObject(logicmgr, value, &other, false, "")) { /* error will be overwritten */
			toPoint = other->NodeGetWorldPosition();
		}
		else {
			PyErr_SetString(PyExc_TypeError, "gameOb.getVectTo(other): KX_GameObject, expected a 3D Vector or KX_GameObject type");
			return nullptr;
		}
	}

	fromPoint = NodeGetWorldPosition();
	toDir = toPoint - fromPoint;
	distance = toDir.Length();

	if (mt::FuzzyZero(distance)) {
		locToDir = toDir = mt::zero3;
		distance = 0.0f;
	}
	else {
		toDir.Normalize();
		locToDir = toDir * NodeGetWorldOrientation();
	}

	returnValue = PyTuple_New(3);
	if (returnValue) { // very unlikely to fail, python sets a memory error here.
		PyTuple_SET_ITEM(returnValue, 0, PyFloat_FromDouble(distance));
		PyTuple_SET_ITEM(returnValue, 1, PyObjectFrom(toDir));
		PyTuple_SET_ITEM(returnValue, 2, PyObjectFrom(locToDir));
	}
	return returnValue;
}


EXP_PYMETHODDEF_DOC_O(KX_GameObject, getTurnTo,
                      "getTurnTo(other): get local Vector to another point/KX_GameObject\n"
                      "Returns (localVector)\n")
{
	mt::vec3 toPoint, fromPoint;
	mt::vec3 toDir, locToDir;
	float distance;

	SCA_LogicManager *logicmgr = GetScene()->GetLogicManager();

	if (!PyVecTo(value, toPoint)) {
		PyErr_Clear();

		KX_GameObject *other;
		if (ConvertPythonToGameObject(logicmgr, value, &other, false, "")) { /* error will be overwritten */
			toPoint = other->NodeGetWorldPosition();
		}
		else {
			PyErr_SetString(PyExc_TypeError, "gameOb.getTurnTo(other): KX_GameObject, expected a 3D Vector or KX_GameObject type");
			return nullptr;
		}
	}

	fromPoint = NodeGetWorldPosition();
	toDir = toPoint - fromPoint;
	distance = toDir.Length();

	if (mt::FuzzyZero(distance)) {
		locToDir = toDir = mt::zero3;
		//distance = 0.0f;
	}
	else {
		toDir.Normalize();
		locToDir = toDir * NodeGetWorldOrientation();
	}

	return PyObjectFrom(locToDir);
}


KX_GameObject::RayCastData::RayCastData(const std::string& prop, bool xray, unsigned int mask)
	:m_prop(prop),
	m_xray(xray),
	m_mask(mask),
	m_hitObject(nullptr)
{
}

static bool CheckRayCastObject(KX_GameObject *obj, KX_GameObject::RayCastData *rayData)
{
	const std::string& prop = rayData->m_prop;
	const unsigned int mask = rayData->m_mask;
	// Check if the object had a given property (if this one is non empty) and have the correct group mask (if this one is different from 0xFFFF).
	return ((prop.empty() || obj->GetProperty(prop)) && (mask == ((1u << OB_MAX_COL_MASKS) - 1) || obj->GetCollisionGroup() & mask));
}

bool KX_GameObject::RayHit(KX_ClientObjectInfo *client, KX_RayCast *result, RayCastData *rayData)
{
	KX_GameObject *obj = client->m_gameobject;

	// if X-ray option is selected, the unwanted objects were not tested, so get here only with true hit
	// if not, all objects were tested and the front one may not be the correct one.
	if (rayData->m_xray || CheckRayCastObject(obj, rayData)) {
		rayData->m_hitObject = obj;
	}
	// return true to stop RayCast::RayTest from looping, the above test was decisive
	// We would want to loop only if we want to get more than one hit point
	return true;
}

/* this function is used to pre-filter the object before casting the ray on them.
 * This is useful for "X-Ray" option when we want to see "through" unwanted object.
 */
bool KX_GameObject::NeedRayCast(KX_ClientObjectInfo *client, RayCastData *rayData)
{
	KX_GameObject *obj = client->m_gameobject;

	// if X-Ray option is selected, skip object that don't match the criteria as we see through them
	// if not, test all objects because we don't know yet which one will be on front
	return (!rayData->m_xray || CheckRayCastObject(obj, rayData));
}

EXP_PYMETHODDEF_DOC(KX_GameObject, rayCastTo,
                    "rayCastTo(other,dist,prop): look towards another point/KX_GameObject and return first object hit within dist that matches prop\n"
                    " prop = property name that object must have; can be omitted => detect any object\n"
                    " dist = max distance to look (can be negative => look behind); 0 or omitted => detect up to other\n"
                    " other = 3-tuple or object reference")
{
	mt::vec3 toPoint;
	PyObject *pyarg;
	float dist = 0.0f;
	const char *propName = "";
	SCA_LogicManager *logicmgr = GetScene()->GetLogicManager();

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "O|fs:rayCastTo", {"other", "dist", "prop", 0},
	                                   &pyarg, &dist, &propName)) {
		return nullptr; // python sets simple error
	}

	if (!PyVecTo(pyarg, toPoint)) {
		KX_GameObject *other;
		PyErr_Clear();

		if (ConvertPythonToGameObject(logicmgr, pyarg, &other, false, "")) { /* error will be overwritten */
			toPoint = other->NodeGetWorldPosition();
		}
		else {
			PyErr_SetString(PyExc_TypeError, "gameOb.rayCastTo(other,dist,prop): KX_GameObject, the first argument to rayCastTo must be a vector or a KX_GameObject");
			return nullptr;
		}
	}
	mt::vec3 fromPoint = NodeGetWorldPosition();

	if (dist != 0.0f) {
		toPoint = fromPoint + dist * (toPoint - fromPoint).SafeNormalized(mt::axisX3);
	}

	PHY_IPhysicsEnvironment *pe = GetScene()->GetPhysicsEnvironment();
	PHY_IPhysicsController *spc = m_physicsController.get();
	KX_GameObject *parent = GetParent();
	if (!spc && parent) {
		spc = parent->GetPhysicsController();
	}

	RayCastData rayData(propName, false, (1u << OB_MAX_COL_MASKS) - 1);
	KX_RayCast::Callback<KX_GameObject, RayCastData> callback(this, spc, &rayData);
	if (KX_RayCast::RayTest(pe, fromPoint, toPoint, callback) && rayData.m_hitObject) {
		return rayData.m_hitObject->GetProxy();
	}

	Py_RETURN_NONE;
}

/* faster then Py_BuildValue since some scripts call raycast a lot */
static PyObject *none_tuple_3()
{
	PyObject *ret = PyTuple_New(3);
	PyTuple_SET_ITEM(ret, 0, Py_None);
	PyTuple_SET_ITEM(ret, 1, Py_None);
	PyTuple_SET_ITEM(ret, 2, Py_None);

	Py_INCREF(Py_None);
	Py_INCREF(Py_None);
	Py_INCREF(Py_None);
	return ret;
}
static PyObject *none_tuple_4()
{
	PyObject *ret = PyTuple_New(4);
	PyTuple_SET_ITEM(ret, 0, Py_None);
	PyTuple_SET_ITEM(ret, 1, Py_None);
	PyTuple_SET_ITEM(ret, 2, Py_None);
	PyTuple_SET_ITEM(ret, 3, Py_None);

	Py_INCREF(Py_None);
	Py_INCREF(Py_None);
	Py_INCREF(Py_None);
	Py_INCREF(Py_None);
	return ret;
}

static PyObject *none_tuple_5()
{
	PyObject *ret = PyTuple_New(5);
	PyTuple_SET_ITEM(ret, 0, Py_None);
	PyTuple_SET_ITEM(ret, 1, Py_None);
	PyTuple_SET_ITEM(ret, 2, Py_None);
	PyTuple_SET_ITEM(ret, 3, Py_None);
	PyTuple_SET_ITEM(ret, 4, Py_None);

	Py_INCREF(Py_None);
	Py_INCREF(Py_None);
	Py_INCREF(Py_None);
	Py_INCREF(Py_None);
	Py_INCREF(Py_None);
	return ret;
}

static PyObject *raycast_no_hit(int poly)
{
	return (poly == 2) ? none_tuple_5() : poly ? none_tuple_4() : none_tuple_3();
}

EXP_PYMETHODDEF_DOC(KX_GameObject, rayCast,
                    "rayCast(to,from,dist,prop,face,xray,poly,mask): cast a ray and return 3-tuple (object,hit,normal) or 4-tuple (object,hit,normal,polygon) or 4-tuple (object,hit,normal,polygon,hituv) of contact point with object within dist that matches prop.\n"
                    " If no hit, return (None,None,None) or (None,None,None,None) or (None,None,None,None,None).\n"
                    " to   = 3-tuple or object reference for destination of ray (if object, use center of object)\n"
                    " from = 3-tuple or object reference for origin of ray (if object, use center of object)\n"
                    "        Can be None or omitted => start from self object center\n"
                    " dist = max distance to look (can be negative => look behind); 0 or omitted => detect up to to\n"
                    " prop = property name that object must have; can be omitted => detect any object\n"
                    " face = normal option: 1=>return face normal; 0 or omitted => normal is oriented towards origin\n"
                    " xray = X-ray option: 1=>skip objects that don't match prop; 0 or omitted => stop on first object\n"
                    " poly = polygon option: 1=>return value is a 4-tuple and the 4th element is a KX_PolyProxy object\n"
                    "                           which can be None if hit object has no mesh or if there is no hit\n"
                    "                        2=>return value is a 5-tuple, the 4th element is the KX_PolyProxy object\n"
                    "                           and the 5th element is the vector of UV coordinates at the hit point of the None if there is no UV mapping\n"
                    "        If 0 or omitted, return value is a 3-tuple\n"
                    " mask = collision mask: the collision mask that ray can hit, 0 < mask < 65536\n"
					" debug = draw line to debug raycast\n"
                    "Note: The object on which you call this method matters: the ray will ignore it.\n"
                    "      prop and xray option interact as follow:\n"
                    "        prop off, xray off: return closest hit or no hit if there is no object on the full extend of the ray\n"
                    "        prop off, xray on : idem\n"
                    "        prop on,  xray off: return closest hit if it matches prop, no hit otherwise\n"
                    "        prop on,  xray on : return closest hit matching prop or no hit if there is no object matching prop on the full extend of the ray\n")
{
	mt::vec3 toPoint;
	mt::vec3 fromPoint;
	PyObject *pyto;
	PyObject *pyfrom = Py_None;
	float dist = 0.0f;
	const char *propName = "";
	KX_GameObject *other;
	int face = 0, xray = 0, poly = 0;
	int mask = (1 << OB_MAX_COL_MASKS) - 1;
	int debug = 0;
	SCA_LogicManager *logicmgr = GetScene()->GetLogicManager();

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "O|Ofsiiiii:rayCast",
	                                   {"objto", "objfrom", "dist", "prop", "face", "xray", "poly", "mask", "debug", 0},
	                                   &pyto, &pyfrom, &dist, &propName, &face, &xray, &poly, &mask, &debug)) {
		return nullptr; // Python sets a simple error
	}

	if (!PyVecTo(pyto, toPoint)) {
		PyErr_Clear();

		if (ConvertPythonToGameObject(logicmgr, pyto, &other, false, "")) { /* error will be overwritten */
			toPoint = other->NodeGetWorldPosition();
		}
		else {
			PyErr_SetString(PyExc_TypeError, "the first argument to rayCast must be a vector or a KX_GameObject");
			return nullptr;
		}
	}
	if (pyfrom == Py_None) {
		fromPoint = NodeGetWorldPosition();
	}
	else if (!PyVecTo(pyfrom, fromPoint)) {
		PyErr_Clear();

		if (ConvertPythonToGameObject(logicmgr, pyfrom, &other, false, "")) { /* error will be overwritten */
			fromPoint = other->NodeGetWorldPosition();
		}
		else {
			PyErr_SetString(PyExc_TypeError, "gameOb.rayCast(to,from,dist,prop,face,xray,poly,mask,debug): KX_GameObject, the second optional argument to rayCast must be a vector or a KX_GameObject");
			return nullptr;
		}
	}

	if (mask == 0 || mask & ~((1 << OB_MAX_COL_MASKS) - 1)) {
		PyErr_Format(PyExc_TypeError, "gameOb.rayCast(to,from,dist,prop,face,xray,poly,mask,debug): KX_GameObject, mask argument to rayCast must be a int bitfield, 0 < mask < %i", (1 << OB_MAX_COL_MASKS));
		return nullptr;
	}

	if (dist != 0.0f) {
		mt::vec3 toDir = toPoint - fromPoint;
		if (mt::FuzzyZero(toDir)) {
			//return Py_BuildValue("OOO", Py_None, Py_None, Py_None);
			return raycast_no_hit(poly);
		}
		toDir.Normalize();
		toPoint = fromPoint + (dist) * toDir;
	}
	else if (mt::FuzzyZero(toPoint - fromPoint)) {
		//return Py_BuildValue("OOO", Py_None, Py_None, Py_None);
		return raycast_no_hit(poly);
	}

	PHY_IPhysicsEnvironment *pe = GetScene()->GetPhysicsEnvironment();
	PHY_IPhysicsController *spc = m_physicsController.get();
	KX_GameObject *parent = GetParent();
	if (!spc && parent) {
		spc = parent->GetPhysicsController();
	}

	// to get the hit results
	RayCastData rayData(propName, xray, mask);
	KX_RayCast::Callback<KX_GameObject, RayCastData> callback(this, spc, &rayData, face, (poly == 2));

	if (KX_RayCast::RayTest(pe, fromPoint, toPoint, callback) && rayData.m_hitObject) {
		PyObject *returnValue = (poly == 2) ? PyTuple_New(5) : (poly) ? PyTuple_New(4) : PyTuple_New(3);
		if (returnValue) { // unlikely this would ever fail, if it does python sets an error
			PyTuple_SET_ITEM(returnValue, 0, rayData.m_hitObject->GetProxy());
			PyTuple_SET_ITEM(returnValue, 1, PyObjectFrom(callback.m_hitPoint));
			PyTuple_SET_ITEM(returnValue, 2, PyObjectFrom(callback.m_hitNormal));
			if (poly) {
				if (callback.m_hitMesh) {
					KX_Mesh *mesh = static_cast<KX_Mesh *>(callback.m_hitMesh);
					// if this field is set, then we can trust that m_hitPolygon is a valid polygon
					const RAS_Mesh::PolygonInfo polygon = mesh->GetPolygon(callback.m_hitPolygon);
					KX_PolyProxy *polyproxy = new KX_PolyProxy(mesh, polygon);
					PyTuple_SET_ITEM(returnValue, 3, polyproxy->NewProxy(true));
					if (poly == 2) {
						if (callback.m_hitUVOK) {
							PyTuple_SET_ITEM(returnValue, 4, PyObjectFrom(callback.m_hitUV));
						}
						else {
							Py_INCREF(Py_None);
							PyTuple_SET_ITEM(returnValue, 4, Py_None);
						}
					}
				}
				else {
					Py_INCREF(Py_None);
					PyTuple_SET_ITEM(returnValue, 3, Py_None);
					if (poly == 2) {
						Py_INCREF(Py_None);
						PyTuple_SET_ITEM(returnValue, 4, Py_None);
					}
				}
			}
		// Debug Hit (hit)
		if (debug) {
			KX_RasterizerDrawDebugLine(fromPoint, callback.m_hitPoint, mt::vec4(0.0f, 1.0f, 0.0f, 1.0f));
			}
		}
		return returnValue;
	}
	// Debug Hit (no hit)
	if (debug) {
		KX_RasterizerDrawDebugLine(fromPoint, toPoint, mt::vec4(1.0f, 0.0f, 0.0f, 1.0f));
	}
	// no hit
	return raycast_no_hit(poly);
}

EXP_PYMETHODDEF_DOC(KX_GameObject, sendMessage,
                    "sendMessage(subject, [body, to])\n"
                    "sends a message in same manner as a message actuator"
                    "subject = Subject of the message (string)"
                    "body = Message body (string)"
                    "to = Name of object to send the message to")
{
	char *subject;
	char *body = (char *)"";
	char *to = (char *)"";

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "s|ss:sendMessage", {"subject", "body", "to", 0},
	                                   &subject, &body, &to)) {
		return nullptr;
	}

	GetScene()->GetNetworkMessageScene()->SendMessage(to, this, subject, body);
	Py_RETURN_NONE;
}

static void layer_check(short &layer, const char *method_name)
{
	if (layer < 0 || layer >= MAX_ACTION_LAYERS) {
		CM_PythonFunctionWarning("KX_GameObject", method_name, "given layer (" << layer
		                                                                       << ") is out of range (0 - " << (MAX_ACTION_LAYERS - 1) << "), setting to 0.");
		layer = 0;
	}
}

EXP_PYMETHODDEF_DOC(KX_GameObject, playAction,
                    "playAction(name, start_frame, end_frame, layer=0, priority=0 blendin=0, play_mode=ACT_MODE_PLAY, layer_weight=0.0, ipo_flags=0, speed=1.0)\n"
                    "Plays an action\n")
{
	const char *name;
	float start, end, blendin = 0.0f, speed = 1.0f, layer_weight = 0.0f;
	short layer = 0, priority = 0;
	short ipo_flags = 0;
	short play_mode = 0;
	short blend_mode = 0;

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "sff|hhfhfhfh:playAction", {"name", "start_frame", "end_frame", "layer",
	                                                                           "priority", "blendin", "play_mode", "layer_weight", "ipo_flags", "speed", "blend_mode", 0},
	                                   &name, &start, &end, &layer, &priority, &blendin, &play_mode, &layer_weight, &ipo_flags, &speed, &blend_mode)) {
		return nullptr;
	}

	layer_check(layer, "playAction");

	if (play_mode < 0 || play_mode > BL_Action::ACT_MODE_MAX) {
		CM_PythonFunctionWarning("KX_GameObject", "playAction", "given play_mode (" << play_mode << ") is out of range (0 - "
		                                                                            << (BL_Action::ACT_MODE_MAX - 1) << "), setting to ACT_MODE_PLAY");
		play_mode = BL_Action::ACT_MODE_PLAY;
	}

	if (blend_mode < 0 || blend_mode > BL_Action::ACT_BLEND_MAX) {
		CM_PythonFunctionWarning("KX_GameObject", "playAction", "given blend_mode (" << blend_mode << ") is out of range (0 - "
		                                                                             << (BL_Action::ACT_BLEND_MAX - 1) << "), setting to ACT_BLEND_BLEND");
		blend_mode = BL_Action::ACT_BLEND_BLEND;
	}

	if (layer_weight < 0.0f || layer_weight > 2.0f) {
		CM_PythonFunctionWarning("KX_GameObject", "playAction", "given layer_weight (" << layer_weight
		                                                                               << ") is out of range (0.0 - 2.0), setting to 0.0");
		layer_weight = 0.0f;
	}

	PlayAction(name, start, end, layer, priority, blendin, play_mode, layer_weight, ipo_flags, speed, blend_mode);

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_GameObject, stopAction,
                    "stopAction(layer=0)\n"
                    "Stop playing the action on the given layer\n")
{
	short layer = 0;

	if (!PyArg_ParseTuple(args, "|h:stopAction", &layer)) {
		return nullptr;
	}

	layer_check(layer, "stopAction");

	StopAction(layer);

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_GameObject, getActionFrame,
                    "getActionFrame(layer=0)\n"
                    "Gets the current frame of the action playing in the supplied layer\n")
{
	short layer = 0;

	if (!PyArg_ParseTuple(args, "|h:getActionFrame", &layer)) {
		return nullptr;
	}

	layer_check(layer, "getActionFrame");

	return PyFloat_FromDouble(GetActionFrame(layer));
}

EXP_PYMETHODDEF_DOC(KX_GameObject, getActionName,
                    "getActionName(layer=0)\n"
                    "Gets the name of the current action playing in the supplied layer\n")
{
	short layer = 0;

	if (!PyArg_ParseTuple(args, "|h:getActionName", &layer)) {
		return nullptr;
	}

	layer_check(layer, "getActionName");

	return PyUnicode_FromStdString(GetActionName(layer));
}

EXP_PYMETHODDEF_DOC(KX_GameObject, setActionLayerWeight,
	"setActionLayerWeight(layer, layerWeight=0.0)\n"
	"Change layerWeight of a layer\n")
{
	short layer = 0;
	float layerWeight = 0.0f;

	static const char *keywords[] = {"layer", "layerWeight", nullptr};
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "h|f:setActionLayerWeight",
	                                const_cast<char **>(keywords), &layer, &layerWeight)) {
		return nullptr;
	}

	if (layerWeight < 0.0f || layerWeight > 2.0f) {
		layerWeight = 0.0f;
	}

	layer_check(layer, "setActionLayerWeight");

	SetActionLayerWeight(layer, layerWeight);

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_GameObject, setActionLayerSpeed,
	"setActionLayerSpeed(layer, speed=0.0)\n"
	"Change speed of a layer\n")
{
	short layer = 0;
	float speed = 0.0f;

	static const char *keywords[] = {"layer", "speed", nullptr};
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "h|f:setActionLayerSpeed",
	                                const_cast<char **>(keywords), &layer, &speed)) {
		return nullptr;
	}

	if (speed < 0.0f) {
		speed = 0.0f;
	}

	layer_check(layer, "setActionLayerSpeed");

	SetActionLayerSpeed(layer, speed);

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_GameObject, setActionFrame,
                    "setActionFrame(frame, layer=0)\n"
                    "Set the current frame of the action playing in the supplied layer\n")
{
	short layer = 0;
	float frame;

	if (!PyArg_ParseTuple(args, "f|h:setActionFrame", &frame, &layer)) {
		return nullptr;
	}

	layer_check(layer, "setActionFrame");

	SetActionFrame(layer, frame);

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_GameObject, isPlayingAction,
                    "isPlayingAction(layer=0)\n"
                    "Checks to see if there is an action playing in the given layer\n")
{
	short layer = 0;

	if (!PyArg_ParseTuple(args, "|h:isPlayingAction", &layer)) {
		return nullptr;
	}

	layer_check(layer, "isPlayingAction");

	return PyBool_FromLong(!IsActionDone(layer));
}


EXP_PYMETHODDEF_DOC(KX_GameObject, addDebugProperty,
                    "addDebugProperty(name, visible=1)\n"
                    "Added or remove a debug property to the debug list.\n")
{
	KX_Scene *scene = GetScene();
	char *name;
	int visible = 1;

	if (!PyArg_ParseTuple(args, "s|i:debugProperty", &name, &visible)) {
		return nullptr;
	}

	if (visible) {
		if (!scene->PropertyInDebugList(this, name)) {
			scene->AddDebugProperty(this, name);
		}
	}
	else {
		scene->RemoveDebugProperty(this, name);
	}

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_GameObject, strikeLightning,
                    "strikeLightning(bolt=True)\n"
                    "A lightning strike now inside the area of this Empty (Object Data > Lightning).\n"
                    "bolt=False gives a flash in the cloud only.\n")
{
	int bolt = 1;
	if (!PyArg_ParseTuple(args, "|p:strikeLightning", &bolt)) {
		return nullptr;
	}
	if (!GetScene()->StrikeLightningAt(this, bolt != 0)) {
		PyErr_Format(PyExc_TypeError, "gameOb.strikeLightning(): \"%s\" is not a lightning emitter (Empty with Lightning enabled)", GetName().c_str());
		return nullptr;
	}
	Py_RETURN_NONE;
}


/* dict style access */


/* Matches python dict.get(key, [default]) */
PyObject *KX_GameObject::Pyget(PyObject *const *args, Py_ssize_t nargs)
{
	if (nargs < 1 || nargs > 2) {
		PyErr_Format(PyExc_TypeError, "get expected 1 or 2 arguments, got %zd", nargs);
		return nullptr;
	}
	PyObject *key = args[0];
	PyObject *def = (nargs == 2) ? args[1] : Py_None;
	PyObject *ret;

	if (PyUnicode_Check(key)) {
		Py_ssize_t len;
		const char *name = PyUnicode_AsUTF8AndSize(key, &len);
		if (!name) {
			return nullptr;
		}
		EXP_Value *item = FindProperty(std::string_view(name, len));
		if (item) {
			ret = item->ConvertValueToPython();
			if (ret) {
				return ret;
			}
			else {
				return item->GetProxy();
			}
		}
	}

	if (m_attr_dict && (ret = PyDict_GetItem(m_attr_dict, key))) {
		Py_INCREF(ret);
		return ret;
	}

	Py_INCREF(def);
	return def;
}

bool ConvertPythonToGameObject(SCA_LogicManager *manager, PyObject *value, KX_GameObject **object, bool py_none_ok, const char *error_prefix)
{
	if (value == nullptr) {
		PyErr_Format(PyExc_TypeError, "%s, python pointer nullptr, should never happen", error_prefix);
		*object = nullptr;
		return false;
	}

	if (value == Py_None) {
		*object = nullptr;

		if (py_none_ok) {
			return true;
		}
		else {
			PyErr_Format(PyExc_TypeError, "%s, expected KX_GameObject or a KX_GameObject name, None is invalid", error_prefix);
			return false;
		}
	}

	if (PyUnicode_Check(value)) {
		*object = (KX_GameObject *)manager->GetGameObjectByName(std::string(_PyUnicode_AsString(value)));

		if (*object) {
			return true;
		}
		else {
			PyErr_Format(PyExc_ValueError, "%s, requested name \"%s\" did not match any KX_GameObject in this scene", error_prefix, _PyUnicode_AsString(value));
			return false;
		}
	}

	if (PyObject_TypeCheck(value, &KX_GameObject::Type) ||
	    PyObject_TypeCheck(value, &KX_LightObject::Type)    ||
	    PyObject_TypeCheck(value, &KX_Camera::Type)         ||
	    PyObject_TypeCheck(value, &KX_FontObject::Type) ||
	    PyObject_TypeCheck(value, &KX_NavMeshObject::Type)) {
		*object = static_cast<KX_GameObject *>EXP_PROXY_REF(value);

		/* sets the error */
		if (*object == nullptr) {
			PyErr_Format(PyExc_SystemError, "%s, " EXP_PROXY_ERROR_MSG, error_prefix);
			return false;
		}

		return true;
	}

	*object = nullptr;

	if (py_none_ok) {
		PyErr_Format(PyExc_TypeError, "%s, expect a KX_GameObject, a string or None", error_prefix);
	}
	else {
		PyErr_Format(PyExc_TypeError, "%s, expect a KX_GameObject or a string", error_prefix);
	}

	return false;
}
#endif // WITH_PYTHON
