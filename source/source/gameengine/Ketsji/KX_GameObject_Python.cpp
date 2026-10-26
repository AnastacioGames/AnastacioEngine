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
 * KX_GameObject Python bindings: mathutils callbacks, method/attribute tables, type and attributes.
 */

/** \file gameengine/Ketsji/KX_GameObject_Python.cpp
 *  \ingroup ketsji
 */

#ifdef _MSC_VER
/* This warning tells us about truncation of __long__ stl-generated names.
 * It can occasionally cause DevStudio to have internal compiler warnings. */
#  pragma warning( disable:4786 )
#endif

#include <cstring>
#include <cmath>

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

#endif

#ifdef USE_MATHUTILS

/* These require an SGNode */
#define MATHUTILS_VEC_CB_POS_LOCAL 1
#define MATHUTILS_VEC_CB_POS_GLOBAL 2
#define MATHUTILS_VEC_CB_SCALE_LOCAL 3
#define MATHUTILS_VEC_CB_SCALE_GLOBAL 4
#define MATHUTILS_VEC_CB_INERTIA_LOCAL 5
#define MATHUTILS_VEC_CB_OBJECT_COLOR 6
#define MATHUTILS_VEC_CB_LINVEL_LOCAL 7
#define MATHUTILS_VEC_CB_LINVEL_GLOBAL 8
#define MATHUTILS_VEC_CB_ANGVEL_LOCAL 9
#define MATHUTILS_VEC_CB_ANGVEL_GLOBAL 10
#define MATHUTILS_VEC_CB_GRAVITY 11

static unsigned char mathutils_kxgameob_vector_cb_index = -1; /* index for our callbacks */

static int mathutils_kxgameob_generic_check(BaseMathObject *bmo)
{
	KX_GameObject *self = static_cast<KX_GameObject *>EXP_PROXY_REF(bmo->cb_user);
	if (self == nullptr) {
		return -1;
	}

	return 0;
}

static int mathutils_kxgameob_vector_get(BaseMathObject *bmo, int subtype)
{
	KX_GameObject *self = static_cast<KX_GameObject *>EXP_PROXY_REF(bmo->cb_user);
	if (self == nullptr) {
		return -1;
	}

	switch (subtype) {
		case MATHUTILS_VEC_CB_POS_LOCAL:
		{
			self->NodeGetLocalPosition().Pack(bmo->data);
			break;
		}
		case MATHUTILS_VEC_CB_POS_GLOBAL:
		{
			self->NodeGetWorldPosition().Pack(bmo->data);
			break;
		}
		case MATHUTILS_VEC_CB_SCALE_LOCAL:
		{
			self->NodeGetLocalScaling().Pack(bmo->data);
			break;
		}
		case MATHUTILS_VEC_CB_SCALE_GLOBAL:
		{
			self->NodeGetWorldScaling().Pack(bmo->data);
			break;
		}
		case MATHUTILS_VEC_CB_INERTIA_LOCAL:
		{
			PYTHON_CHECK_PHYSICS_CONTROLLER(self, "localInertia", -1);
			self->GetLocalInertia().Pack(bmo->data);
			break;
		}
		case MATHUTILS_VEC_CB_OBJECT_COLOR:
		{
			self->GetObjectColor().Pack(bmo->data);
			break;
		}
		case MATHUTILS_VEC_CB_LINVEL_LOCAL:
		{
			PYTHON_CHECK_PHYSICS_CONTROLLER(self, "localLinearVelocity", -1);
			self->GetLinearVelocity(true).Pack(bmo->data);
			break;
		}
		case MATHUTILS_VEC_CB_LINVEL_GLOBAL:
		{
			PYTHON_CHECK_PHYSICS_CONTROLLER(self, "worldLinearVelocity", -1);
			self->GetLinearVelocity(false).Pack(bmo->data);
			break;
		}
		case MATHUTILS_VEC_CB_ANGVEL_LOCAL:
		{
			PYTHON_CHECK_PHYSICS_CONTROLLER(self, "localLinearVelocity", -1);
			self->GetAngularVelocity(true).Pack(bmo->data);
			break;
		}
		case MATHUTILS_VEC_CB_ANGVEL_GLOBAL:
		{
			PYTHON_CHECK_PHYSICS_CONTROLLER(self, "worldLinearVelocity", -1);
			self->GetAngularVelocity(false).Pack(bmo->data);
			break;
		}
		case MATHUTILS_VEC_CB_GRAVITY:
		{
			PYTHON_CHECK_PHYSICS_CONTROLLER(self, "gravity", -1);
			self->GetGravity().Pack(bmo->data);
			break;
		}

	}

#undef PHYS_ERR

	return 0;
}

static int mathutils_kxgameob_vector_set(BaseMathObject *bmo, int subtype)
{
	KX_GameObject *self = static_cast<KX_GameObject *>EXP_PROXY_REF(bmo->cb_user);
	if (self == nullptr) {
		return -1;
	}

	switch (subtype) {
		case MATHUTILS_VEC_CB_POS_LOCAL:
		{
			self->NodeSetLocalPosition(mt::vec3(bmo->data));
			self->NodeUpdate();
			break;
		}
		case MATHUTILS_VEC_CB_POS_GLOBAL:
		{
			self->NodeSetWorldPosition(mt::vec3(bmo->data));
			self->NodeUpdate();
			break;
		}
		case MATHUTILS_VEC_CB_SCALE_LOCAL:
		{
			self->NodeSetLocalScale(mt::vec3(bmo->data));
			self->NodeUpdate();
			break;
		}
		case MATHUTILS_VEC_CB_SCALE_GLOBAL:
		{
			self->NodeSetWorldScale(mt::vec3(bmo->data));
			self->NodeUpdate();
			break;
		}
		case MATHUTILS_VEC_CB_INERTIA_LOCAL:
		{
			/* read only */
			break;
		}
		case MATHUTILS_VEC_CB_OBJECT_COLOR:
		{
			self->SetObjectColor(mt::vec4(bmo->data));
			break;
		}
		case MATHUTILS_VEC_CB_LINVEL_LOCAL:
		{
			self->SetLinearVelocity(mt::vec3(bmo->data), true);
			break;
		}
		case MATHUTILS_VEC_CB_LINVEL_GLOBAL:
		{
			self->SetLinearVelocity(mt::vec3(bmo->data), false);
			break;
		}
		case MATHUTILS_VEC_CB_ANGVEL_LOCAL:
		{
			self->SetAngularVelocity(mt::vec3(bmo->data), true);
			break;
		}
		case MATHUTILS_VEC_CB_ANGVEL_GLOBAL:
		{
			self->SetAngularVelocity(mt::vec3(bmo->data), false);
			break;
		}
		case MATHUTILS_VEC_CB_GRAVITY:
		{
			self->SetGravity(mt::vec3(bmo->data));
			break;
		}
	}

	return 0;
}

static int mathutils_kxgameob_vector_get_index(BaseMathObject *bmo, int subtype, int index)
{
	/* lazy, avoid repeteing the case statement */
	if (mathutils_kxgameob_vector_get(bmo, subtype) == -1) {
		return -1;
	}
	return 0;
}

static int mathutils_kxgameob_vector_set_index(BaseMathObject *bmo, int subtype, int index)
{
	float f = bmo->data[index];

	/* lazy, avoid repeteing the case statement */
	if (mathutils_kxgameob_vector_get(bmo, subtype) == -1) {
		return -1;
	}

	bmo->data[index] = f;
	return mathutils_kxgameob_vector_set(bmo, subtype);
}

static Mathutils_Callback mathutils_kxgameob_vector_cb = {
	mathutils_kxgameob_generic_check,
	mathutils_kxgameob_vector_get,
	mathutils_kxgameob_vector_set,
	mathutils_kxgameob_vector_get_index,
	mathutils_kxgameob_vector_set_index
};

/* Matrix */
#define MATHUTILS_MAT_CB_ORI_LOCAL 1
#define MATHUTILS_MAT_CB_ORI_GLOBAL 2

static unsigned char mathutils_kxgameob_matrix_cb_index = -1; /* index for our callbacks */

static int mathutils_kxgameob_matrix_get(BaseMathObject *bmo, int subtype)
{
	KX_GameObject *self = static_cast<KX_GameObject *>EXP_PROXY_REF(bmo->cb_user);
	if (self == nullptr) {
		return -1;
	}

	switch (subtype) {
		case MATHUTILS_MAT_CB_ORI_LOCAL:
		{
			self->NodeGetLocalOrientation().Pack(bmo->data);
			break;
		}
		case MATHUTILS_MAT_CB_ORI_GLOBAL:
		{
			self->NodeGetWorldOrientation().Pack(bmo->data);
			break;
		}
	}

	return 0;
}


static int mathutils_kxgameob_matrix_set(BaseMathObject *bmo, int subtype)
{
	KX_GameObject *self = static_cast<KX_GameObject *>EXP_PROXY_REF(bmo->cb_user);
	if (self == nullptr) {
		return -1;
	}

	mt::mat3 mat3x3;
	switch (subtype) {
		case MATHUTILS_MAT_CB_ORI_LOCAL:
		{
			mat3x3 = mt::mat3(bmo->data);
			self->NodeSetLocalOrientation(mat3x3);
			self->NodeUpdate();
			break;
		}
		case MATHUTILS_MAT_CB_ORI_GLOBAL:
		{
			mat3x3 = mt::mat3(bmo->data);
			self->NodeSetGlobalOrientation(mat3x3);
			self->NodeUpdate();
			break;
		}
	}

	return 0;
}

static Mathutils_Callback mathutils_kxgameob_matrix_cb = {
	mathutils_kxgameob_generic_check,
	mathutils_kxgameob_matrix_get,
	mathutils_kxgameob_matrix_set,
	nullptr,
	nullptr
};


void KX_GameObject_Mathutils_Callback_Init(void)
{
	// register mathutils callbacks, ok to run more than once.
	mathutils_kxgameob_vector_cb_index = Mathutils_RegisterCallback(&mathutils_kxgameob_vector_cb);
	mathutils_kxgameob_matrix_cb_index = Mathutils_RegisterCallback(&mathutils_kxgameob_matrix_cb);
}

#endif // USE_MATHUTILS

#ifdef WITH_PYTHON
/* ------- python stuff ---------------------------------------------------*/
PyMethodDef KX_GameObject::Methods[] = {
	{"applyForce", (PyCFunction)KX_GameObject::sPyApplyForce, METH_VARARGS},
	{"applyTorque", (PyCFunction)KX_GameObject::sPyApplyTorque, METH_VARARGS},
	{"applyRotation", (PyCFunction)KX_GameObject::sPyApplyRotation, METH_VARARGS},
	{"applyMovement", (PyCFunction)KX_GameObject::sPyApplyMovement, METH_VARARGS},
	{"getLinearVelocity", (PyCFunction)KX_GameObject::sPyGetLinearVelocity, METH_VARARGS},
	{"setLinearVelocity", (PyCFunction)KX_GameObject::sPySetLinearVelocity, METH_VARARGS},
	{"getAngularVelocity", (PyCFunction)KX_GameObject::sPyGetAngularVelocity, METH_VARARGS},
	{"setAngularVelocity", (PyCFunction)KX_GameObject::sPySetAngularVelocity, METH_VARARGS},
	{"getVelocity", (PyCFunction)KX_GameObject::sPyGetVelocity, METH_VARARGS},
	{"setDamping", (PyCFunction)KX_GameObject::sPySetDamping, METH_VARARGS},

	{"setCcdMotionThreshold", (PyCFunction)KX_GameObject::sPySetCcdMotionThreshold, METH_VARARGS},
	{"setCcdSweptSphereRadius", (PyCFunction)KX_GameObject::sPySetCcdSweptSphereRadius, METH_VARARGS},

	{"setSoftLinearStiffness", (PyCFunction)KX_GameObject::sPySetSoftLinStiff, METH_VARARGS},
	{"setSoftAngularStiffness", (PyCFunction)KX_GameObject::sPySetSoftAngStiff, METH_VARARGS},
	{"setSoftVolume", (PyCFunction)KX_GameObject::sPySetSoftVolume, METH_VARARGS},
	{"setSoftVsRigidHardness", (PyCFunction)KX_GameObject::sPySetSoftVsRigidHardness, METH_VARARGS},
	{"setSoftVsKineticHardness", (PyCFunction)KX_GameObject::sPySetSoftVsKineticHardness, METH_VARARGS},
	{"setSoftVsSoftHardness", (PyCFunction)KX_GameObject::sPySetSoftVsSoftHardness, METH_VARARGS },
	{"setSoftVsRigidImpulseSplitCluster", (PyCFunction)KX_GameObject::sPySetSoftVsRigidImpulseSplitCluster, METH_VARARGS },
	{"setSoftVsKineticImpulseSplitCluster", (PyCFunction)KX_GameObject::sPySetSoftVsKineticImpulseSplitCluster, METH_VARARGS },
	{"setSoftVsSoftImpulseSplitCluster", (PyCFunction)KX_GameObject::sPySetSoftVsSoftImpulseSplitCluster, METH_VARARGS },
	{"setSoftVelocitiesCorrectionFactor", (PyCFunction)KX_GameObject::sPySetVelocitiesCorrectionFactor, METH_VARARGS },
	{"setSoftDampingCoefficient", (PyCFunction)KX_GameObject::sPySetDampingCoefficient, METH_VARARGS },
	{"setSoftDragCoefficient", (PyCFunction)KX_GameObject::sPySetDragCoefficient, METH_VARARGS },
	{"setSoftLiftCoefficient", (PyCFunction)KX_GameObject::sPySetLiftCoefficient, METH_VARARGS },
	{"setSoftPressureCoefficient", (PyCFunction)KX_GameObject::sPySetPressureCoefficient, METH_VARARGS },
	{"setSoftVolumeConversationCoefficient", (PyCFunction)KX_GameObject::sPySetVolumeConversationCoefficient, METH_VARARGS },
	{"setSoftDynamicFrictionCoefficient", (PyCFunction)KX_GameObject::sPySetDynamicFrictionCoefficient, METH_VARARGS },
	{"setSoftPoseMatchingCoefficient", (PyCFunction)KX_GameObject::sPySetPoseMatchingCoefficient, METH_VARARGS },
	{"setSoftRigidContactsHardness", (PyCFunction)KX_GameObject::sPySetRigidContactsHardness, METH_VARARGS },
	{"setSoftKineticContactsHardness", (PyCFunction)KX_GameObject::sPySetKineticContactsHardness, METH_VARARGS },
	{"setSoftContactsHardness", (PyCFunction)KX_GameObject::sPySetSoftContactsHardness, METH_VARARGS },
	{"setSoftAnchorsHardness", (PyCFunction)KX_GameObject::sPySetAnchorsHardness, METH_VARARGS },
	{"setSoftVelocitySolverIterations", (PyCFunction)KX_GameObject::sPySetVelocitySolverIterations, METH_VARARGS },
    {"setSoftPositionSolverIterations", (PyCFunction)KX_GameObject::sPySetPositionSolverIterations, METH_VARARGS },
    {"setSoftDriftSolverIterations", (PyCFunction)KX_GameObject::sPySetDriftSolverIterations, METH_VARARGS },
    {"setSoftClusterSolverIterations", (PyCFunction)KX_GameObject::sPySetClusterSolverIterations, METH_VARARGS },
    {"setSoftPoseMatching", (PyCFunction)KX_GameObject::sPySetSoftPoseMatching, METH_VARARGS },

	{"getReactionForce", (PyCFunction)KX_GameObject::sPyGetReactionForce, METH_NOARGS},
	{"alignAxisToVect", (PyCFunction)KX_GameObject::sPyAlignAxisToVect, METH_VARARGS | METH_KEYWORDS},
	{"lookAt", (PyCFunction)KX_GameObject::sPyLookAt, METH_VARARGS | METH_KEYWORDS},
	{"getAxisVect", (PyCFunction)KX_GameObject::sPyGetAxisVect, METH_O},
	{"suspendPhysics", (PyCFunction)KX_GameObject::sPySuspendPhysics, METH_VARARGS},
	{"restorePhysics", (PyCFunction)KX_GameObject::sPyRestorePhysics, METH_NOARGS},
	{"suspendDynamics", (PyCFunction)KX_GameObject::sPySuspendDynamics, METH_VARARGS},
	{"restoreDynamics", (PyCFunction)KX_GameObject::sPyRestoreDynamics, METH_NOARGS},
	{"enableRigidBody", (PyCFunction)KX_GameObject::sPyEnableRigidBody, METH_NOARGS},
	{"disableRigidBody", (PyCFunction)KX_GameObject::sPyDisableRigidBody, METH_NOARGS},
	{"applyImpulse", (PyCFunction)KX_GameObject::sPyApplyImpulse, METH_VARARGS},
	{"setCollisionMargin", (PyCFunction)KX_GameObject::sPySetCollisionMargin, METH_O},
	{"collide", (PyCFunction)KX_GameObject::sPyCollide, METH_O},
	{"setParent", (PyCFunction)KX_GameObject::sPySetParent, METH_VARARGS | METH_KEYWORDS},
	{"setVisible", (PyCFunction)KX_GameObject::sPySetVisible, METH_VARARGS},
	{"setHalfAnimations", (PyCFunction)KX_GameObject::sPySetHalfAnimations, METH_VARARGS},
	{"suspendAnimations", (PyCFunction)KX_GameObject::sPySuspendAnimations, METH_NOARGS},
	{"resumeAnimations", (PyCFunction)KX_GameObject::sPyResumeAnimations, METH_NOARGS},
	{"setOcclusion", (PyCFunction)KX_GameObject::sPySetOcclusion, METH_VARARGS},
	{"removeParent", (PyCFunction)KX_GameObject::sPyRemoveParent, METH_NOARGS},

	{"getPhysicsId", (PyCFunction)KX_GameObject::sPyGetPhysicsId, METH_NOARGS},
	{"getVehicle", (PyCFunction)KX_GameObject::sPyGetVehicle, METH_NOARGS},
	{"getVehicleSteeringWheel", (PyCFunction)KX_GameObject::sPyGetVehicleSteeringWheel, METH_NOARGS},
	{"getVehicleMaxTorque", (PyCFunction)KX_GameObject::sPyGetVehicleMaxTorque, METH_NOARGS},
	{"getVehicleMaxRPM", (PyCFunction)KX_GameObject::sPyGetVehicleMaxRPM, METH_NOARGS},
	{"getVehicleGearRatios", (PyCFunction)KX_GameObject::sPyGetVehicleGearRatios, METH_NOARGS},
	{"getVehicleGearboxType", (PyCFunction)KX_GameObject::sPyGetVehicleGearboxType, METH_NOARGS},
	{"setVehicleMaxTorque", (PyCFunction)KX_GameObject::sPySetVehicleMaxTorque, METH_O},
	{"setVehicleMaxRPM", (PyCFunction)KX_GameObject::sPySetVehicleMaxRPM, METH_O},
	{"setVehicleGearRatios", (PyCFunction)KX_GameObject::sPySetVehicleGearRatios, METH_O},
	{"getPropertyNames", (PyCFunction)KX_GameObject::sPyGetPropertyNames, METH_NOARGS},
	{"replaceMesh", (PyCFunction)KX_GameObject::sPyReplaceMesh, METH_VARARGS | METH_KEYWORDS},
	{"endObject", (PyCFunction)KX_GameObject::sPyEndObject, METH_NOARGS},
	{"shatter", (PyCFunction)KX_GameObject::sPyShatter, METH_VARARGS | METH_KEYWORDS},
	{"detonate", (PyCFunction)KX_GameObject::sPyDetonate, METH_NOARGS},
	{"dent", (PyCFunction)KX_GameObject::sPyDent, METH_VARARGS | METH_KEYWORDS},
	{"resetDent", (PyCFunction)KX_GameObject::sPyResetDent, METH_NOARGS},
	{"reinstancePhysicsMesh", (PyCFunction)KX_GameObject::sPyReinstancePhysicsMesh, METH_VARARGS | METH_KEYWORDS},
	{"replacePhysicsShape", (PyCFunction)KX_GameObject::sPyReplacePhysicsShape, METH_O},

	EXP_PYMETHODTABLE_KEYWORDS(KX_GameObject, rayCastTo),
	EXP_PYMETHODTABLE_KEYWORDS(KX_GameObject, rayCast),
	EXP_PYMETHODTABLE_O(KX_GameObject, getDistanceTo),
	EXP_PYMETHODTABLE_O(KX_GameObject, getVectTo),
	EXP_PYMETHODTABLE_KEYWORDS(KX_GameObject, getCurvePoints),
	EXP_PYMETHODTABLE_O(KX_GameObject, getTurnTo),

	EXP_PYMETHODTABLE_KEYWORDS(KX_GameObject, sendMessage),
	EXP_PYMETHODTABLE(KX_GameObject, addDebugProperty),
	EXP_PYMETHODTABLE(KX_GameObject, strikeLightning),

	EXP_PYMETHODTABLE_KEYWORDS(KX_GameObject, playAction),
	EXP_PYMETHODTABLE(KX_GameObject, stopAction),
	EXP_PYMETHODTABLE(KX_GameObject, getActionFrame),
	EXP_PYMETHODTABLE(KX_GameObject, getActionName),
	EXP_PYMETHODTABLE_KEYWORDS(KX_GameObject, setActionLayerWeight),
	EXP_PYMETHODTABLE_KEYWORDS(KX_GameObject, setActionLayerSpeed),
	EXP_PYMETHODTABLE(KX_GameObject, setActionFrame),
	EXP_PYMETHODTABLE(KX_GameObject, isPlayingAction),

	// dict style access for props
	{"get", (PyCFunction)(void (*)(void))KX_GameObject::sPyget, METH_FASTCALL},

	{nullptr, nullptr} //Sentinel
};

/// obj.net: built by Range.network (_object_net), so the object class needs no network code.
static PyObject *KX_GameObject_pyattr_get_net(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	PyObject *module = PyImport_ImportModule("Range.network");
	if (!module) {
		return nullptr;
	}
	PyObject *result = PyObject_CallMethod(module, "_object_net", "N",
	                                       static_cast<KX_GameObject *>(self_v)->GetProxy());
	Py_DECREF(module);
	return result;
}

/* Destruction, Explosive and Deformation settings (Physics panels), per instance: they start from
 * the panels and only change this object. Writing needs an object that is destructible / explosive /
 * deformable in the panels (the type itself is fixed, see isDestructible). */
namespace {
enum DestructionGroup { DESTRUCTION_SETTINGS, EXPLOSIVE_SETTINGS, DEFORM_SETTINGS };

struct DestructionAttribute {
	const char *name;
	DestructionGroup group;
	/// 'f' float, 'i' int, 'b' flag bit, 'F' float of the Particle Explosion (see explosive_particles_init).
	char kind;
	size_t offset;
	int flag;
	float min, max;
};
}

static const DestructionAttribute destruction_attributes[] = {
	{"burstSpeed", DESTRUCTION_SETTINGS, 'f', offsetof(RangeDestructionSettings, burst_speed), 0, 0.0f, 1000.0f},
	{"debrisLifetime", DESTRUCTION_SETTINGS, 'f', offsetof(RangeDestructionSettings, debris_lifetime), 0, 0.0f, 3600.0f},
	{"useBreakOnCollision", DESTRUCTION_SETTINGS, 'b', offsetof(RangeDestructionSettings, flags), DESTRUCTION_BREAK_ON_COLLISION, 0, 0},
	{"useInheritVelocity", DESTRUCTION_SETTINGS, 'b', offsetof(RangeDestructionSettings, flags), DESTRUCTION_INHERIT_VELOCITY, 0, 0},
	{"impactImpulse", EXPLOSIVE_SETTINGS, 'f', offsetof(RangeExplosiveSettings, impact_impulse), 0, 0.0f, 100000.0f},
	{"useExplodeOnImpact", EXPLOSIVE_SETTINGS, 'b', offsetof(RangeExplosiveSettings, flags), EXPLOSIVE_ON_IMPACT, 0, 0},
	{"useChainReaction", EXPLOSIVE_SETTINGS, 'b', offsetof(RangeExplosiveSettings, flags), EXPLOSIVE_CHAIN_REACTION, 0, 0},
	{"explosionRadius", EXPLOSIVE_SETTINGS, 'f', offsetof(RangeExplosiveSettings, radius), 0, 0.01f, 10000.0f},
	{"explosionForce", EXPLOSIVE_SETTINGS, 'f', offsetof(RangeExplosiveSettings, force), 0, 0.0f, 100000.0f},
	{"upBias", EXPLOSIVE_SETTINGS, 'f', offsetof(RangeExplosiveSettings, up_bias), 0, 0.0f, 5.0f},
	{"effectLife", EXPLOSIVE_SETTINGS, 'f', offsetof(RangeExplosiveSettings, effect_life), 0, 0.0f, 3600.0f},
	{"useOcclusion", EXPLOSIVE_SETTINGS, 'b', offsetof(RangeExplosiveSettings, flags), EXPLOSIVE_OCCLUSION, 0, 0},
	{"useParticleExplosion", EXPLOSIVE_SETTINGS, 'b', offsetof(RangeExplosiveSettings, flags), EXPLOSIVE_PARTICLES, 0, 0},
	{"fireAmount", EXPLOSIVE_SETTINGS, 'F', offsetof(RangeExplosiveSettings, fire_amount), 0, 0.0f, 4.0f},
	{"smokeAmount", EXPLOSIVE_SETTINGS, 'F', offsetof(RangeExplosiveSettings, smoke_amount), 0, 0.0f, 4.0f},
	{"sparkAmount", EXPLOSIVE_SETTINGS, 'F', offsetof(RangeExplosiveSettings, spark_amount), 0, 0.0f, 4.0f},
	{"smokeDuration", EXPLOSIVE_SETTINGS, 'F', offsetof(RangeExplosiveSettings, smoke_duration), 0, 0.2f, 4.0f},
	{"blastSpeed", EXPLOSIVE_SETTINGS, 'F', offsetof(RangeExplosiveSettings, blast_speed), 0, 0.2f, 4.0f},
	{"useGroundMark", EXPLOSIVE_SETTINGS, 'b', offsetof(RangeExplosiveSettings, flags), EXPLOSIVE_GROUND_MARK, 0, 0},
	{"useLightFlash", EXPLOSIVE_SETTINGS, 'b', offsetof(RangeExplosiveSettings, flags), EXPLOSIVE_LIGHT_FLASH, 0, 0},
	{"flashStrength", EXPLOSIVE_SETTINGS, 'f', offsetof(RangeExplosiveSettings, flash_strength), 0, 0.0f, 10.0f},
	{"flashDuration", EXPLOSIVE_SETTINGS, 'f', offsetof(RangeExplosiveSettings, flash_duration), 0, 0.1f, 10.0f},
	{"useMarkNearby", EXPLOSIVE_SETTINGS, 'b', offsetof(RangeExplosiveSettings, flags), EXPLOSIVE_MARK_NEARBY, 0, 0},
	{"markSize", EXPLOSIVE_SETTINGS, 'f', offsetof(RangeExplosiveSettings, mark_size), 0, 0.1f, 4.0f},
	{"markLife", EXPLOSIVE_SETTINGS, 'f', offsetof(RangeExplosiveSettings, mark_life), 0, 0.0f, 3600.0f},
	{"dentImpulse", DEFORM_SETTINGS, 'f', offsetof(RangeDeformSettings, dent_impulse), 0, 0.0f, 100000.0f},
	{"useDentOnCollision", DEFORM_SETTINGS, 'b', offsetof(RangeDeformSettings, flags), DEFORM_ON_COLLISION, 0, 0},
	{"bendAngle", DEFORM_SETTINGS, 'f', offsetof(RangeDeformSettings, bend_angle), 0, 0.0f, (float)M_PI},
	{"bendMaxAngle", DEFORM_SETTINGS, 'f', offsetof(RangeDeformSettings, bend_max_angle), 0, 0.0f, (float)M_PI},
	{"decalSize", DEFORM_SETTINGS, 'f', offsetof(RangeDeformSettings, decal_size), 0, 0.001f, 1000.0f},
	{"decalLife", DEFORM_SETTINGS, 'f', offsetof(RangeDeformSettings, decal_life), 0, 0.0f, 100000.0f},
	{"maxDecals", DEFORM_SETTINGS, 'i', offsetof(RangeDeformSettings, max_decals), 0, 1.0f, 1000.0f},
};

static const char *bend_axis_names[] = {"X", "Y", "Z"};
// Indexed by EXPLOSIVE_PARTICLES_* and EXPLOSIVE_STYLE_*.
static const char *explosion_size_names[] = {"SMALL", "MEDIUM", "LARGE", "HUGE", "TINY"};
static const char *explosion_style_names[] = {"FIRE", "ELECTRIC", "CONCRETE", "WATER"};

struct ExplosionColor {
	const char *name;
	size_t offset;
};
static const ExplosionColor explosion_colors[] = {
	{"fireColor", offsetof(RangeExplosiveSettings, fire_color)},
	{"smokeColor", offsetof(RangeExplosiveSettings, smoke_color)},
	{"sparkColor", offsetof(RangeExplosiveSettings, spark_color)},
};

/// The colors and amounts of the Particle Explosion only count once they are initialized (the panel
/// does it when the option is first enabled): the style colors and every multiplier at 1.
static void explosive_particles_init(RangeExplosiveSettings *settings)
{
	if (settings->flags & EXPLOSIVE_PARTICLE_COLORS) {
		return;
	}
	KX_Scene::GetExplosionStyleColors(settings->particle_style, settings->fire_color, settings->smoke_color,
	                                  settings->spark_color);
	settings->fire_amount = settings->smoke_amount = settings->spark_amount = 1.0f;
	settings->smoke_duration = settings->blast_speed = 1.0f;
	settings->flags |= EXPLOSIVE_PARTICLE_COLORS;
}

/// The game object of a template of the scene file, None when it isn't in this scene.
static PyObject *template_proxy(KX_GameObject *self, Object *ob)
{
	KX_GameObject *gameobj = ob ? static_cast<KX_GameObject *>(
		self->GetScene()->GetLogicManager()->FindGameObjByBlendObj(ob)) : nullptr;
	if (!gameobj) {
		Py_RETURN_NONE;
	}
	return gameobj->GetProxy();
}

static const char *destruction_group_names[] = {"destructible", "explosive", "deformable"};

/// Settings of the group, from the instance (or the panels for an unregistered object).
static const char *destruction_settings_read(KX_GameObject *gameobj, DestructionGroup group)
{
	const KX_DestructionManager& manager = gameobj->GetScene()->GetDestructionManager();
	switch (group) {
		case DESTRUCTION_SETTINGS: return (const char *)&manager.GetDestructionSettings(gameobj);
		case EXPLOSIVE_SETTINGS: return (const char *)&manager.GetExplosiveSettings(gameobj);
		default: return (const char *)&manager.GetDeformSettings(gameobj);
	}
}

static char *destruction_settings_edit(KX_GameObject *gameobj, DestructionGroup group, const char *attr)
{
	KX_DestructionManager& manager = gameobj->GetScene()->GetDestructionManager();
	char *settings = (group == DESTRUCTION_SETTINGS) ? (char *)manager.EditDestructionSettings(gameobj) :
	                 (group == EXPLOSIVE_SETTINGS) ? (char *)manager.EditExplosiveSettings(gameobj) :
	                 (char *)manager.EditDeformSettings(gameobj);
	if (!settings) {
		PyErr_Format(PyExc_AttributeError, "gameOb.%s: KX_GameObject, \"%s\" is not %s", attr,
		             gameobj->GetName().c_str(), destruction_group_names[group]);
	}
	return settings;
}

static PyObject *KX_GameObject_pyattr_get_destruction(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	const std::string& name = attrdef->m_name;
	KX_DestructionManager& manager = self->GetScene()->GetDestructionManager();

	if (name == "isDeformable") {
		return PyBool_FromLong(manager.IsDeformable(self));
	}
	if (name == "fragments") {
		const Group *group = manager.GetDestructionSettings(self).fragments;
		if (!group) {
			Py_RETURN_NONE;
		}
		return PyUnicode_FromString(group->id.name + 2);
	}
	if (name == "decal") {
		Object *decal = manager.GetDeformSettings(self).decal;
		KX_GameObject *decalobj = decal ? static_cast<KX_GameObject *>(
			self->GetScene()->GetLogicManager()->FindGameObjByBlendObj(decal)) : nullptr;
		if (!decalobj) {
			Py_RETURN_NONE;
		}
		return decalobj->GetProxy();
	}
	if (name == "bendAxis") {
		return PyUnicode_FromString(bend_axis_names[CLAMPIS(manager.GetDeformSettings(self).bend_axis, 0, 2)]);
	}
	if (name == "explosionEffect") {
		return template_proxy(self, manager.GetExplosiveSettings(self).effect);
	}
	if (name == "groundMark") {
		return template_proxy(self, manager.GetExplosiveSettings(self).mark);
	}
	if (name == "particleSize") {
		return PyUnicode_FromString(explosion_size_names[CLAMPIS(manager.GetExplosiveSettings(self).particle_size, 0, 4)]);
	}
	if (name == "particleStyle") {
		return PyUnicode_FromString(explosion_style_names[CLAMPIS(manager.GetExplosiveSettings(self).particle_style, 0, 3)]);
	}
	for (const ExplosionColor& color : explosion_colors) {
		if (name == color.name) {
			RangeExplosiveSettings settings = manager.GetExplosiveSettings(self);
			explosive_particles_init(&settings);
			const float *rgb = (const float *)((const char *)&settings + color.offset);
			return PyObjectFrom(mt::vec3(rgb[0], rgb[1], rgb[2]));
		}
	}
	for (const DestructionAttribute& attr : destruction_attributes) {
		if (name == attr.name) {
			const char *field = destruction_settings_read(self, attr.group) + attr.offset;
			switch (attr.kind) {
				case 'F': {
					// Not initialized yet: every multiplier counts as 1.
					const bool custom = (manager.GetExplosiveSettings(self).flags & EXPLOSIVE_PARTICLE_COLORS) != 0;
					return PyFloat_FromDouble(custom ? *(const float *)field : 1.0f);
				}
				case 'f': return PyFloat_FromDouble(*(const float *)field);
				case 'i': return PyLong_FromLong(*(const int *)field);
				default: return PyBool_FromLong((*(const int *)field & attr.flag) != 0);
			}
		}
	}
	Py_RETURN_NONE;
}

static int KX_GameObject_pyattr_set_destruction(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	const std::string& name = attrdef->m_name;
	const char *attrname = name.c_str();
	KX_DestructionManager& manager = self->GetScene()->GetDestructionManager();
	const bool wanted = manager.WantsCollisions(self);

	if (name == "fragments") {
		RangeDestructionSettings *settings = (RangeDestructionSettings *)destruction_settings_edit(self, DESTRUCTION_SETTINGS, attrname);
		if (!settings) {
			return PY_SET_ATTR_FAIL;
		}
		if (value == Py_None) {
			settings->fragments = nullptr;
			return PY_SET_ATTR_SUCCESS;
		}
		const char *groupname = PyUnicode_Check(value) ? PyUnicode_AsUTF8(value) : nullptr;
		Group *group = groupname ? (Group *)BLI_findstring(&G.main->group, groupname, offsetof(ID, name) + 2) : nullptr;
		if (!group) {
			PyErr_Format(PyExc_ValueError, "gameOb.fragments = str: KX_GameObject, expected the name of a group or None");
			return PY_SET_ATTR_FAIL;
		}
		settings->fragments = group;
		return PY_SET_ATTR_SUCCESS;
	}
	if (name == "decal") {
		KX_GameObject *decalobj;
		if (!ConvertPythonToGameObject(self->GetScene()->GetLogicManager(), value, &decalobj, true,
		                               "gameOb.decal = KX_GameObject or None: KX_GameObject")) {
			return PY_SET_ATTR_FAIL;
		}
		if (decalobj && !decalobj->GetBlenderObject()) {
			PyErr_SetString(PyExc_ValueError, "gameOb.decal = KX_GameObject: KX_GameObject, the decal must be an object of the scene file");
			return PY_SET_ATTR_FAIL;
		}
		RangeDeformSettings *settings = (RangeDeformSettings *)destruction_settings_edit(self, DEFORM_SETTINGS, attrname);
		if (!settings) {
			return PY_SET_ATTR_FAIL;
		}
		settings->decal = decalobj ? decalobj->GetBlenderObject() : nullptr;
		manager.SettingsChanged(self, wanted);
		return PY_SET_ATTR_SUCCESS;
	}
	if (name == "bendAxis") {
		const char *axis = PyUnicode_Check(value) ? PyUnicode_AsUTF8(value) : nullptr;
		int index = -1;
		for (int i = 0; axis && i < 3; ++i) {
			if (std::strcmp(axis, bend_axis_names[i]) == 0) {
				index = i;
			}
		}
		if (index < 0) {
			PyErr_SetString(PyExc_ValueError, "gameOb.bendAxis = str: KX_GameObject, expected 'X', 'Y' or 'Z'");
			return PY_SET_ATTR_FAIL;
		}
		RangeDeformSettings *settings = (RangeDeformSettings *)destruction_settings_edit(self, DEFORM_SETTINGS, attrname);
		if (!settings) {
			return PY_SET_ATTR_FAIL;
		}
		settings->bend_axis = index;
		return PY_SET_ATTR_SUCCESS;
	}

	if (name == "explosionEffect" || name == "groundMark") {
		KX_GameObject *templateobj;
		if (!ConvertPythonToGameObject(self->GetScene()->GetLogicManager(), value, &templateobj, true,
		                               "gameOb.explosionEffect/groundMark = KX_GameObject or None: KX_GameObject")) {
			return PY_SET_ATTR_FAIL;
		}
		if (templateobj && !templateobj->GetBlenderObject()) {
			PyErr_Format(PyExc_ValueError, "gameOb.%s = KX_GameObject: KX_GameObject, it must be an object of the scene file", attrname);
			return PY_SET_ATTR_FAIL;
		}
		RangeExplosiveSettings *settings = (RangeExplosiveSettings *)destruction_settings_edit(self, EXPLOSIVE_SETTINGS, attrname);
		if (!settings) {
			return PY_SET_ATTR_FAIL;
		}
		((name == "groundMark") ? settings->mark : settings->effect) = templateobj ? templateobj->GetBlenderObject() : nullptr;
		return PY_SET_ATTR_SUCCESS;
	}
	if (name == "particleSize" || name == "particleStyle") {
		const bool size = (name == "particleSize");
		const char **names = size ? explosion_size_names : explosion_style_names;
		const int count = size ? 5 : 4;
		const char *text = PyUnicode_Check(value) ? PyUnicode_AsUTF8(value) : nullptr;
		int index = -1;
		for (int i = 0; text && i < count; ++i) {
			if (std::strcmp(text, names[i]) == 0) {
				index = i;
			}
		}
		if (index < 0) {
			PyErr_Format(PyExc_ValueError, "gameOb.%s = str: KX_GameObject, expected %s", attrname,
			             size ? "'TINY', 'SMALL', 'MEDIUM', 'LARGE' or 'HUGE'" : "'FIRE', 'ELECTRIC', 'CONCRETE' or 'WATER'");
			return PY_SET_ATTR_FAIL;
		}
		RangeExplosiveSettings *settings = (RangeExplosiveSettings *)destruction_settings_edit(self, EXPLOSIVE_SETTINGS, attrname);
		if (!settings) {
			return PY_SET_ATTR_FAIL;
		}
		if (size) {
			settings->particle_size = index;
		}
		else {
			// Like the panel: a new style brings its own colors.
			explosive_particles_init(settings);
			settings->particle_style = index;
			KX_Scene::GetExplosionStyleColors(index, settings->fire_color, settings->smoke_color, settings->spark_color);
		}
		return PY_SET_ATTR_SUCCESS;
	}
	for (const ExplosionColor& color : explosion_colors) {
		if (name != color.name) {
			continue;
		}
		mt::vec3 rgb;
		if (!PyVecTo(value, rgb)) {
			return PY_SET_ATTR_FAIL;
		}
		RangeExplosiveSettings *settings = (RangeExplosiveSettings *)destruction_settings_edit(self, EXPLOSIVE_SETTINGS, attrname);
		if (!settings) {
			return PY_SET_ATTR_FAIL;
		}
		explosive_particles_init(settings);
		float *field = (float *)((char *)settings + color.offset);
		for (int i = 0; i < 3; ++i) {
			field[i] = CLAMPIS(rgb[i], 0.0f, 1.0f);
		}
		return PY_SET_ATTR_SUCCESS;
	}
	for (const DestructionAttribute& attr : destruction_attributes) {
		if (name != attr.name) {
			continue;
		}
		double number = 0.0;
		int flag = 0;
		if (attr.kind == 'b') {
			flag = PyObject_IsTrue(value);
			if (flag == -1) {
				PyErr_Format(PyExc_TypeError, "gameOb.%s = bool: KX_GameObject, expected True or False", attrname);
				return PY_SET_ATTR_FAIL;
			}
		}
		else {
			number = PyFloat_AsDouble(value);
			if (number == -1.0 && PyErr_Occurred()) {
				PyErr_Format(PyExc_TypeError, "gameOb.%s = %s: KX_GameObject, expected a number", attrname,
				             (attr.kind == 'i') ? "int" : "float");
				return PY_SET_ATTR_FAIL;
			}
			number = CLAMPIS(number, (double)attr.min, (double)attr.max);
		}
		char *settings = destruction_settings_edit(self, attr.group, attrname);
		if (!settings) {
			return PY_SET_ATTR_FAIL;
		}
		void *field = settings + attr.offset;
		switch (attr.kind) {
			case 'F':
				explosive_particles_init((RangeExplosiveSettings *)settings);
				*(float *)field = (float)number;
				break;
			case 'f': *(float *)field = (float)number; break;
			case 'i': *(int *)field = (int)number; break;
			default: SET_FLAG_FROM_TEST(*(int *)field, flag, attr.flag); break;
		}
		manager.SettingsChanged(self, wanted);
		return PY_SET_ATTR_SUCCESS;
	}
	return PY_SET_ATTR_FAIL;
}

/* EXP_PYATTRIBUTE_RW_FUNCTION spelled out: the getter and setter are free functions. */
#define EXP_PYATTRIBUTE_RW_DESTRUCTION(name) \
	{name, EXP_PYATTRIBUTE_TYPE_FUNCTION, EXP_PYATTRIBUTE_RW, 0, 0, 0.f, 0.f, false, false, 0, 0, 1, nullptr, \
	 &KX_GameObject_pyattr_set_destruction, &KX_GameObject_pyattr_get_destruction}
#define EXP_PYATTRIBUTE_RO_DESTRUCTION(name) \
	{name, EXP_PYATTRIBUTE_TYPE_FUNCTION, EXP_PYATTRIBUTE_RO, 0, 0, 0.f, 0.f, false, false, 0, 0, 1, nullptr, \
	 nullptr, &KX_GameObject_pyattr_get_destruction}

PyAttributeDef KX_GameObject::Attributes[] = {
	EXP_PYATTRIBUTE_SHORT_RO("currentLodLevel", KX_GameObject, m_currentLodLevel),
	EXP_PYATTRIBUTE_RW_FUNCTION("lodManager", KX_GameObject, pyattr_get_lodManager, pyattr_set_lodManager),
	EXP_PYATTRIBUTE_RO_FUNCTION("animationEventManager", KX_GameObject, pyattr_get_animationEventsManager),
	EXP_PYATTRIBUTE_RW_FUNCTION("name",     KX_GameObject, pyattr_get_name, pyattr_set_name),
	EXP_PYATTRIBUTE_RO_FUNCTION("parent",   KX_GameObject, pyattr_get_parent),
	EXP_PYATTRIBUTE_RO_FUNCTION("parentRecursive", KX_GameObject, pyattr_get_parent_recursive),
	EXP_PYATTRIBUTE_RO_FUNCTION("groupMembers", KX_GameObject, pyattr_get_group_members),
	EXP_PYATTRIBUTE_RO_FUNCTION("groupObject",  KX_GameObject, pyattr_get_group_object),
	EXP_PYATTRIBUTE_RO_FUNCTION("scene",        KX_GameObject, pyattr_get_scene),
	EXP_PYATTRIBUTE_RW_FUNCTION("life",     KX_GameObject, pyattr_get_life, pyattr_set_life),
	EXP_PYATTRIBUTE_RW_FUNCTION("mass",     KX_GameObject, pyattr_get_mass,     pyattr_set_mass),
	EXP_PYATTRIBUTE_RW_FUNCTION("friction", KX_GameObject, pyattr_get_friction, pyattr_set_friction),
	EXP_PYATTRIBUTE_RW_FUNCTION("anisotropicFriction", KX_GameObject, pyattr_get_anisotropicFriction, pyattr_set_anisotropicFriction),
	EXP_PYATTRIBUTE_RW_FUNCTION("anisotropicFrictionCoefficients", KX_GameObject, pyattr_get_anisotropicFrictionCoefficients, pyattr_set_anisotropicFrictionCoefficients),
	EXP_PYATTRIBUTE_RO_FUNCTION("isSuspendDynamics",        KX_GameObject, pyattr_get_is_suspend_dynamics),
	EXP_PYATTRIBUTE_RO_FUNCTION("isDestructible", KX_GameObject, pyattr_get_is_destructible),
	EXP_PYATTRIBUTE_RO_FUNCTION("isExplosive", KX_GameObject, pyattr_get_is_explosive),
	EXP_PYATTRIBUTE_RW_FUNCTION("onBreak", KX_GameObject, pyattr_get_destruction_callbacks, pyattr_set_destruction_callbacks),
	EXP_PYATTRIBUTE_RW_FUNCTION("onExplode", KX_GameObject, pyattr_get_destruction_callbacks, pyattr_set_destruction_callbacks),
	EXP_PYATTRIBUTE_RW_FUNCTION("onDent", KX_GameObject, pyattr_get_destruction_callbacks, pyattr_set_destruction_callbacks),
	EXP_PYATTRIBUTE_RW_FUNCTION("breakImpulse", KX_GameObject, pyattr_get_break_impulse, pyattr_set_break_impulse),
	EXP_PYATTRIBUTE_RW_FUNCTION("fuse", KX_GameObject, pyattr_get_fuse, pyattr_set_fuse),
	EXP_PYATTRIBUTE_RO_DESTRUCTION("isDeformable"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("fragments"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("burstSpeed"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("debrisLifetime"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("useBreakOnCollision"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("useInheritVelocity"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("impactImpulse"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("useExplodeOnImpact"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("useChainReaction"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("dentImpulse"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("useDentOnCollision"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("bendAxis"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("bendAngle"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("bendMaxAngle"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("decal"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("decalSize"),
	/* Explosive panel (explosive objects only, AttributeError otherwise). */
	EXP_PYATTRIBUTE_RW_DESTRUCTION("explosionRadius"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("explosionForce"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("upBias"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("useOcclusion"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("explosionEffect"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("effectLife"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("useParticleExplosion"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("particleSize"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("particleStyle"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("fireColor"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("smokeColor"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("sparkColor"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("fireAmount"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("smokeAmount"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("sparkAmount"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("smokeDuration"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("blastSpeed"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("useGroundMark"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("useMarkNearby"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("groundMark"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("markSize"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("markLife"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("decalLife"),
	EXP_PYATTRIBUTE_RW_DESTRUCTION("maxDecals"),
	EXP_PYATTRIBUTE_RW_FUNCTION("linVelocityMin",       KX_GameObject, pyattr_get_lin_vel_min, pyattr_set_lin_vel_min),
	EXP_PYATTRIBUTE_RW_FUNCTION("linVelocityMax",       KX_GameObject, pyattr_get_lin_vel_max, pyattr_set_lin_vel_max),
	EXP_PYATTRIBUTE_RW_FUNCTION("angularVelocityMin", KX_GameObject, pyattr_get_ang_vel_min, pyattr_set_ang_vel_min),
	EXP_PYATTRIBUTE_RW_FUNCTION("angularVelocityMax", KX_GameObject, pyattr_get_ang_vel_max, pyattr_set_ang_vel_max),
	EXP_PYATTRIBUTE_RW_FUNCTION("layer", KX_GameObject, pyattr_get_layer, pyattr_set_layer),
	EXP_PYATTRIBUTE_SHORT_RW("passIndex", 0, SHRT_MAX, false, KX_GameObject, m_passIndex),
	EXP_PYATTRIBUTE_RW_FUNCTION("visible",  KX_GameObject, pyattr_get_visible,  pyattr_set_visible),
	EXP_PYATTRIBUTE_RW_FUNCTION("hiddenFromCamera", KX_GameObject, pyattr_get_hidden_from_camera, pyattr_set_hidden_from_camera),
	EXP_PYATTRIBUTE_RO_FUNCTION("culled", KX_GameObject, pyattr_get_culled),
	EXP_PYATTRIBUTE_RO_FUNCTION("cullingBox",   KX_GameObject, pyattr_get_cullingBox),
	EXP_PYATTRIBUTE_BOOL_RW("occlusion", KX_GameObject, m_bOccluder),
	EXP_PYATTRIBUTE_RW_FUNCTION("physicsCullingRadius", KX_GameObject, pyattr_get_physicsCullingRadius, pyattr_set_physicsCullingRadius),
	EXP_PYATTRIBUTE_RW_FUNCTION("logicCullingRadius", KX_GameObject, pyattr_get_logicCullingRadius, pyattr_set_logicCullingRadius),
	EXP_PYATTRIBUTE_RW_FUNCTION("physicsCulling", KX_GameObject, pyattr_get_physicsCulling, pyattr_set_physicsCulling),
	EXP_PYATTRIBUTE_RW_FUNCTION("physicsCullingVelocity", KX_GameObject, pyattr_get_physicsSleepVelocityCulling, pyattr_set_physicsSleepVelocityCulling),
	EXP_PYATTRIBUTE_RW_FUNCTION("logicCulling", KX_GameObject, pyattr_get_logicCulling, pyattr_set_logicCulling),
	EXP_PYATTRIBUTE_RW_FUNCTION("logicCullingComponents", KX_GameObject, pyattr_get_logicComponentsCulling, pyattr_set_logicComponentsCulling),
	EXP_PYATTRIBUTE_RW_FUNCTION("position", KX_GameObject, pyattr_get_worldPosition,    pyattr_set_localPosition),
	EXP_PYATTRIBUTE_RO_FUNCTION("localInertia", KX_GameObject, pyattr_get_localInertia),
	EXP_PYATTRIBUTE_RW_FUNCTION("orientation", KX_GameObject, pyattr_get_worldOrientation, pyattr_set_localOrientation),
	EXP_PYATTRIBUTE_RW_FUNCTION("scaling",  KX_GameObject, pyattr_get_worldScaling, pyattr_set_localScaling),
	EXP_PYATTRIBUTE_RW_FUNCTION("timeOffset", KX_GameObject, pyattr_get_timeOffset, pyattr_set_timeOffset),
	EXP_PYATTRIBUTE_RW_FUNCTION("collisionCallbacks",       KX_GameObject, pyattr_get_collisionCallbacks,   pyattr_set_collisionCallbacks),
	EXP_PYATTRIBUTE_RW_FUNCTION("collisionGroup",           KX_GameObject, pyattr_get_collisionGroup, pyattr_set_collisionGroup),
	EXP_PYATTRIBUTE_RW_FUNCTION("collisionMask",                KX_GameObject, pyattr_get_collisionMask, pyattr_set_collisionMask),
	EXP_PYATTRIBUTE_RW_FUNCTION("state",        KX_GameObject, pyattr_get_state,    pyattr_set_state),
	EXP_PYATTRIBUTE_RO_FUNCTION("meshes",   KX_GameObject, pyattr_get_meshes),
	EXP_PYATTRIBUTE_RO_FUNCTION("batchGroup", KX_GameObject, pyattr_get_batchGroup),
	EXP_PYATTRIBUTE_RW_FUNCTION("localOrientation", KX_GameObject, pyattr_get_localOrientation, pyattr_set_localOrientation),
	EXP_PYATTRIBUTE_RW_FUNCTION("worldOrientation", KX_GameObject, pyattr_get_worldOrientation, pyattr_set_worldOrientation),
	EXP_PYATTRIBUTE_RW_FUNCTION("localPosition",    KX_GameObject, pyattr_get_localPosition,    pyattr_set_localPosition),
	EXP_PYATTRIBUTE_RW_FUNCTION("worldPosition",    KX_GameObject, pyattr_get_worldPosition,    pyattr_set_worldPosition),
	EXP_PYATTRIBUTE_RW_FUNCTION("localScale",   KX_GameObject, pyattr_get_localScaling, pyattr_set_localScaling),
	EXP_PYATTRIBUTE_RW_FUNCTION("worldScale",   KX_GameObject, pyattr_get_worldScaling, pyattr_set_worldScaling),
	EXP_PYATTRIBUTE_RW_FUNCTION("localTransform",       KX_GameObject, pyattr_get_localTransform, pyattr_set_localTransform),
	EXP_PYATTRIBUTE_RW_FUNCTION("worldTransform",       KX_GameObject, pyattr_get_worldTransform, pyattr_set_worldTransform),
	EXP_PYATTRIBUTE_RW_FUNCTION("linearVelocity", KX_GameObject, pyattr_get_localLinearVelocity, pyattr_set_worldLinearVelocity),
	EXP_PYATTRIBUTE_RW_FUNCTION("localLinearVelocity", KX_GameObject, pyattr_get_localLinearVelocity, pyattr_set_localLinearVelocity),
	EXP_PYATTRIBUTE_RW_FUNCTION("worldLinearVelocity", KX_GameObject, pyattr_get_worldLinearVelocity, pyattr_set_worldLinearVelocity),
	EXP_PYATTRIBUTE_RW_FUNCTION("angularVelocity", KX_GameObject, pyattr_get_localAngularVelocity, pyattr_set_worldAngularVelocity),
	EXP_PYATTRIBUTE_RW_FUNCTION("localAngularVelocity", KX_GameObject, pyattr_get_localAngularVelocity, pyattr_set_localAngularVelocity),
	EXP_PYATTRIBUTE_RW_FUNCTION("worldAngularVelocity", KX_GameObject, pyattr_get_worldAngularVelocity, pyattr_set_worldAngularVelocity),
	EXP_PYATTRIBUTE_RW_FUNCTION("linearDamping", KX_GameObject, pyattr_get_linearDamping, pyattr_set_linearDamping),
	EXP_PYATTRIBUTE_RW_FUNCTION("angularDamping", KX_GameObject, pyattr_get_angularDamping, pyattr_set_angularDamping),
	EXP_PYATTRIBUTE_RO_FUNCTION("children", KX_GameObject, pyattr_get_children),
	EXP_PYATTRIBUTE_RO_FUNCTION("childrenRecursive",    KX_GameObject, pyattr_get_children_recursive),
	EXP_PYATTRIBUTE_RO_FUNCTION("attrDict", KX_GameObject, pyattr_get_attrDict),
	EXP_PYATTRIBUTE_RW_FUNCTION("color", KX_GameObject, pyattr_get_obcolor, pyattr_set_obcolor),
	EXP_PYATTRIBUTE_RO_FUNCTION("activitycullingdistance", KX_GameObject, pyattr_get_activitycullingdistance),
	EXP_PYATTRIBUTE_RW_FUNCTION("debug",    KX_GameObject, pyattr_get_debug, pyattr_set_debug),
	EXP_PYATTRIBUTE_RO_FUNCTION("components", KX_GameObject, pyattr_get_components),
	EXP_PYATTRIBUTE_RW_FUNCTION("debugRecursive",   KX_GameObject, pyattr_get_debugRecursive, pyattr_set_debugRecursive),
	EXP_PYATTRIBUTE_RW_FUNCTION("gravity", KX_GameObject, pyattr_get_gravity, pyattr_set_gravity),
	/* EXP_PYATTRIBUTE_RO_FUNCTION spelled out: the getter is a free function. */
	{"net", EXP_PYATTRIBUTE_TYPE_FUNCTION, EXP_PYATTRIBUTE_RO, 0, 0, 0.f, 0.f, false, false, 0, 0, 1, nullptr, nullptr,
	 &KX_GameObject_pyattr_get_net},

	/* experimental, don't rely on these yet */
	EXP_PYATTRIBUTE_RO_FUNCTION("sensors",      KX_GameObject, pyattr_get_sensors),
	EXP_PYATTRIBUTE_RO_FUNCTION("controllers",  KX_GameObject, pyattr_get_controllers),
	EXP_PYATTRIBUTE_RO_FUNCTION("actuators",        KX_GameObject, pyattr_get_actuators),
	EXP_PYATTRIBUTE_RO_FUNCTION("particles", KX_GameObject, pyattr_get_particles),
	EXP_PYATTRIBUTE_RO_FUNCTION("particlesMix", KX_GameObject, pyattr_get_particles_mix),
	EXP_PYATTRIBUTE_NULL //Sentinel
};

PyObject *KX_GameObject::PyReplaceMesh(PyObject *args, PyObject *kwds)
{
	SCA_LogicManager *logicmgr = GetScene()->GetLogicManager();

	PyObject *value;
	int use_gfx = 1, use_phys = 0;
	KX_Mesh *new_mesh;

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "O|ii:replaceMesh",
	                                   {"mesh", "useDisplayMesh", "usePhysicsMesh", 0}, &value, &use_gfx, &use_phys)) {
		return nullptr;
	}

	if (!ConvertPythonToMesh(logicmgr, value, &new_mesh, false, "gameOb.replaceMesh(value): KX_GameObject")) {
		return nullptr;
	}

	ReplaceMesh(new_mesh, (bool)use_gfx, (bool)use_phys);
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PyEndObject()
{
	GetScene()->DelayedRemoveObject(this);

	Py_RETURN_NONE;
}

PyObject *KX_GameObject::PyShatter(PyObject *args, PyObject *kwds)
{
	PyObject *pyorigin = Py_None;
	PyObject *pyburst = Py_None;

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "|OO:shatter", {"origin", "burst", 0}, &pyorigin, &pyburst)) {
		return nullptr;
	}

	mt::vec3 origin;
	const mt::vec3 *originptr = nullptr;
	if (pyorigin != Py_None) {
		if (!PyVecTo(pyorigin, origin)) {
			return nullptr;
		}
		originptr = &origin;
	}

	float burst;
	const float *burstptr = nullptr;
	if (pyburst != Py_None) {
		burst = PyFloat_AsDouble(pyburst);
		if (burst == -1.0f && PyErr_Occurred()) {
			PyErr_SetString(PyExc_TypeError, "gameOb.shatter(origin, burst): KX_GameObject, burst must be a float or None");
			return nullptr;
		}
		burstptr = &burst;
	}

	const std::vector<KX_GameObject *> pieces = GetScene()->GetDestructionManager().Shatter(this, originptr, burstptr);

	PyObject *list = PyList_New(pieces.size());
	for (unsigned int i = 0, size = pieces.size(); i < size; ++i) {
		PyList_SET_ITEM(list, i, pieces[i]->GetProxy());
	}
	return list;
}

PyObject *KX_GameObject::PyDetonate()
{
	return PyBool_FromLong(GetScene()->GetDestructionManager().Detonate(this));
}

PyObject *KX_GameObject::PyDent(PyObject *args, PyObject *kwds)
{
	PyObject *pypoint;
	PyObject *pydirection;
	float impulse;

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "OOf:dent", {"point", "direction", "impulse", 0},
	                                   &pypoint, &pydirection, &impulse)) {
		return nullptr;
	}

	mt::vec3 point;
	mt::vec3 direction;
	if (!PyVecTo(pypoint, point) || !PyVecTo(pydirection, direction)) {
		return nullptr;
	}

	return PyBool_FromLong(GetScene()->GetDestructionManager().Dent(this, point, direction, impulse));
}

PyObject *KX_GameObject::PyResetDent()
{
	return PyBool_FromLong(GetScene()->GetDestructionManager().ResetDent(this));
}

PyObject *KX_GameObject::PyReinstancePhysicsMesh(PyObject *args, PyObject *kwds)
{
	KX_GameObject *gameobj = nullptr;
	KX_Mesh *mesh = nullptr;
	SCA_LogicManager *logicmgr = GetScene()->GetLogicManager();
	int dupli = 0;

	PyObject *gameobj_py = nullptr;
	PyObject *mesh_py = nullptr;

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "|OOi:reinstancePhysicsMesh",
	                                   {"gameObject", "meshObject", "dupli", 0}, &gameobj_py, &mesh_py, &dupli) ||
	    (gameobj_py && !ConvertPythonToGameObject(logicmgr, gameobj_py, &gameobj, true, "gameOb.reinstancePhysicsMesh(obj, mesh, dupli): KX_GameObject")) ||
	    (mesh_py && !ConvertPythonToMesh(logicmgr, mesh_py, &mesh, true, "gameOb.reinstancePhysicsMesh(obj, mesh, dupli): KX_GameObject"))) {
		return nullptr;
	}

	/* gameobj and mesh can be nullptr */
	if (m_physicsController && m_physicsController->ReinstancePhysicsShape(gameobj, mesh, dupli)) {
		Py_RETURN_TRUE;
	}

	Py_RETURN_FALSE;
}

PyObject *KX_GameObject::PyReplacePhysicsShape(PyObject *value)
{
	KX_GameObject *gameobj;
	SCA_LogicManager *logicmgr = GetScene()->GetLogicManager();

	if (!ConvertPythonToGameObject(logicmgr, value, &gameobj, false, "gameOb.replacePhysicsShape(obj): KX_GameObject")) {
		return nullptr;
	}

	if (!m_physicsController || !gameobj->GetPhysicsController()) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.replacePhysicsShape(obj): function only available for objects with collisions enabled");
		return nullptr;
	}

	if (m_physicsController->ReplacePhysicsShape(gameobj->GetPhysicsController())) {
		Py_RETURN_TRUE;
	}
	Py_RETURN_FALSE;
}

static PyObject *Map_GetItem(PyObject *self_v, PyObject *item)
{
	KX_GameObject *self = static_cast<KX_GameObject *>EXP_PROXY_REF(self_v);
	const char *attr_str = _PyUnicode_AsString(item);
	EXP_Value *resultattr;
	PyObject *pyconvert;

	if (self == nullptr) {
		PyErr_SetString(PyExc_SystemError, "val = gameOb[key]: KX_GameObject, " EXP_PROXY_ERROR_MSG);
		return nullptr;
	}

	/* first see if the attributes a string and try get the cvalue attribute */
	if (attr_str && (resultattr = self->FindProperty(attr_str))) {
		pyconvert = resultattr->ConvertValueToPython();
		return pyconvert ? pyconvert : resultattr->GetProxy();
	}
	/* no EXP_Value attribute, try get the python only m_attr_dict attribute */
	else if (self->m_attr_dict && (pyconvert = PyDict_GetItem(self->m_attr_dict, item))) {

		if (attr_str) {
			PyErr_Clear();
		}
		Py_INCREF(pyconvert);
		return pyconvert;
	}
	else {
		if (attr_str) {
			PyErr_Format(PyExc_KeyError, "value = gameOb[key]: KX_GameObject, key \"%s\" does not exist", attr_str);
		}
		else {
			PyErr_SetString(PyExc_KeyError, "value = gameOb[key]: KX_GameObject, key does not exist");
		}
		return nullptr;
	}

}


static int Map_SetItem(PyObject *self_v, PyObject *key, PyObject *val)
{
	KX_GameObject *self = static_cast<KX_GameObject *>EXP_PROXY_REF(self_v);
	const char *attr_str = _PyUnicode_AsString(key);
	if (attr_str == nullptr) {
		PyErr_Clear();
	}

	if (self == nullptr) {
		PyErr_SetString(PyExc_SystemError, "gameOb[key] = value: KX_GameObject, " EXP_PROXY_ERROR_MSG);
		return -1;
	}

	if (val == nullptr) { /* del ob["key"] */
		int del = 0;

		/* try remove both just in case */
		if (attr_str) {
			del |= (self->RemoveProperty(attr_str) == true) ? 1 : 0;
		}

		if (self->m_attr_dict) {
			del |= (PyDict_DelItem(self->m_attr_dict, key) == 0) ? 1 : 0;
		}

		if (del == 0) {
			if (attr_str) {
				PyErr_Format(PyExc_KeyError, "gameOb[key] = value: KX_GameObject, key \"%s\" could not be set", attr_str);
			}
			else {
				PyErr_SetString(PyExc_KeyError, "del gameOb[key]: KX_GameObject, key could not be deleted");
			}
			return -1;
		}
		else if (self->m_attr_dict) {
			PyErr_Clear(); /* PyDict_DelItem sets an error when it fails */
		}
	}
	else { /* ob["key"] = value */
		bool set = false;

		/* as EXP_Value */
		if (attr_str && PyObject_TypeCheck(val, &EXP_PyObjectPlus::Type) == 0) { /* don't allow GameObjects for eg to be assigned to EXP_Value props */
			EXP_Value *vallie = self->ConvertPythonToValue(val, false, "gameOb[key] = value: ");

			if (vallie) {
				EXP_Value *oldprop = self->GetProperty(attr_str);

				if (oldprop) {
					oldprop->SetValue(vallie);
				}
				else {
					self->SetProperty(attr_str, vallie);
				}

				vallie->Release();
				set = true;

				/* try remove dict value to avoid double ups */
				if (self->m_attr_dict) {
					if (PyDict_DelItem(self->m_attr_dict, key) != 0) {
						PyErr_Clear();
					}
				}
			}
			else if (PyErr_Occurred()) {
				return -1;
			}
		}

		if (set == false) {
			if (self->m_attr_dict == nullptr) { /* lazy init */
				self->m_attr_dict = PyDict_New();
			}


			if (PyDict_SetItem(self->m_attr_dict, key, val) == 0) {
				if (attr_str) {
					self->RemoveProperty(attr_str); /* overwrite the EXP_Value if it exists */
				}
				set = true;
			}
			else {
				if (attr_str) {
					PyErr_Format(PyExc_KeyError, "gameOb[key] = value: KX_GameObject, key \"%s\" not be added to internal dictionary", attr_str);
				}
				else {
					PyErr_SetString(PyExc_KeyError, "gameOb[key] = value: KX_GameObject, key not be added to internal dictionary");
				}
			}
		}

		if (set == false) {
			return -1; /* pythons error value */
		}

	}

	return 0; /* success */
}

static int Seq_Contains(PyObject *self_v, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>EXP_PROXY_REF(self_v);

	if (self == nullptr) {
		PyErr_SetString(PyExc_SystemError, "val in gameOb: KX_GameObject, " EXP_PROXY_ERROR_MSG);
		return -1;
	}

	if (PyUnicode_Check(value) && self->FindProperty(_PyUnicode_AsString(value))) {
		return 1;
	}

	if (self->m_attr_dict && PyDict_GetItem(self->m_attr_dict, value)) {
		return 1;
	}

	return 0;
}


PyMappingMethods KX_GameObject::Mapping = {
	(lenfunc)nullptr,                               /*inquiry mp_length */
	(binaryfunc)Map_GetItem,        /*binaryfunc mp_subscript */
	(objobjargproc)Map_SetItem, /*objobjargproc mp_ass_subscript */
};

PySequenceMethods KX_GameObject::Sequence = {
	nullptr,        /* Cant set the len otherwise it can evaluate as false */
	nullptr,        /* sq_concat */
	nullptr,        /* sq_repeat */
	nullptr,        /* sq_item */
	nullptr,        /* sq_slice */
	nullptr,        /* sq_ass_item */
	nullptr,        /* sq_ass_slice */
	(objobjproc)Seq_Contains,   /* sq_contains */
	(binaryfunc)nullptr,  /* sq_inplace_concat */
	(ssizeargfunc)nullptr,  /* sq_inplace_repeat */
};

PyTypeObject KX_GameObject::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_GameObject",
	sizeof(EXP_PyObjectPlus_Proxy),
	0,
	py_base_dealloc,
	0,
	0,
	0,
	0,
	py_base_repr,
	0,
	&Sequence,
	&Mapping,
	0, 0, 0,
	nullptr,
	nullptr,
	0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	0, 0, 0, 0, 0, 0, 0,
	Methods,
	0,
	0,
	&SCA_IObject::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyObject *KX_GameObject::pyattr_get_name(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyUnicode_FromStdString(self->GetName());
}

int KX_GameObject::pyattr_set_name(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	if (!PyUnicode_Check(value)) {
		PyErr_SetString(PyExc_TypeError, "gameOb.name = str: KX_GameObject, expected a string");
		return PY_SET_ATTR_FAIL;
	}

	std::string newname = std::string(_PyUnicode_AsString(value));
	std::string oldname = self->GetName();

	SCA_LogicManager *manager = self->GetScene()->GetLogicManager();

	// If true, it mean that's this game object is not a replica and was added at conversion time.
	if (manager->GetGameObjectByName(oldname) == self) {
		/* Two non-replica objects can have the same name bacause these objects are register in the
		 * logic manager and that the result of GetGameObjectByName will be undefined. */
		if (manager->GetGameObjectByName(newname)) {
			PyErr_Format(PyExc_TypeError, "gameOb.name = str: name %s is already used by an other non-replica game object", oldname.c_str());
			return PY_SET_ATTR_FAIL;
		}
		// Unregister the old name.
		manager->UnregisterGameObjectName(oldname);
		// Register the object under the new name.
		manager->RegisterGameObjectName(newname, self);
	}

	// Change the name
	self->SetName(newname);

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_parent(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	KX_GameObject *parent = self->GetParent();
	if (parent) {
		return parent->GetProxy();
	}
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::pyattr_get_parent_recursive(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	EXP_ListValue<KX_GameObject> *list = new EXP_ListValue<KX_GameObject>(self->GetParentRecursive());
	/* The list must not own any data because is temporary and we can't
	 * ensure that it will freed before item's in it (e.g python owner). */
	list->SetReleaseOnDestruct(false);
	return list->NewProxy(true);
}

PyObject *KX_GameObject::pyattr_get_group_members(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	EXP_ListValue<KX_GameObject> *instances = self->GetInstanceObjects();
	if (instances) {
		return instances->GetProxy();
	}
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::pyattr_get_collisionCallbacks(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	// Only objects with a physics controller should have collision callbacks
	PYTHON_CHECK_PHYSICS_CONTROLLER(self, "collisionCallbacks", nullptr);

	// Return the existing callbacks
	if (!self->m_collisionCallbacks) {
		self->m_collisionCallbacks = PyList_New(0);
		// Subscribe to collision update from KX_CollisionEventManager
		self->RegisterCollisionCallbacks();
	}
	Py_INCREF(self->m_collisionCallbacks);
	return self->m_collisionCallbacks;
}

int KX_GameObject::pyattr_set_collisionCallbacks(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	// Only objects with a physics controller should have collision callbacks
	PYTHON_CHECK_PHYSICS_CONTROLLER(self, "collisionCallbacks", PY_SET_ATTR_FAIL);

	if (!PyList_CheckExact(value)) {
		PyErr_SetString(PyExc_ValueError, "Expected a list");
		return PY_SET_ATTR_FAIL;
	}

	if (!self->m_collisionCallbacks) {
		self->RegisterCollisionCallbacks();
	}
	else {
		Py_DECREF(self->m_collisionCallbacks);
	}

	Py_INCREF(value);


	self->m_collisionCallbacks = value;

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_collisionGroup(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyLong_FromLong(self->GetCollisionGroup());
}

int KX_GameObject::pyattr_set_collisionGroup(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	int val = PyLong_AsLong(value);

	if (val == -1 && PyErr_Occurred()) {
		PyErr_SetString(PyExc_TypeError, "gameOb.collisionGroup = int: KX_GameObject, expected an int bit field");
		return PY_SET_ATTR_FAIL;
	}

	if (val == 0 || val & ~((1 << OB_MAX_COL_MASKS) - 1)) {
		PyErr_Format(PyExc_AttributeError, "gameOb.collisionGroup = int: KX_GameObject, expected a int bit field, 0 < group < %i", (1 << OB_MAX_COL_MASKS));
		return PY_SET_ATTR_FAIL;
	}

	self->SetCollisionGroup(val);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_collisionMask(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyLong_FromLong(self->GetCollisionMask());
}

int KX_GameObject::pyattr_set_collisionMask(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	int val = PyLong_AsLong(value);

	if (val == -1 && PyErr_Occurred()) {
		PyErr_SetString(PyExc_TypeError, "gameOb.collisionMask = int: KX_GameObject, expected an int bit field");
		return PY_SET_ATTR_FAIL;
	}

	if (val == 0 || val & ~((1 << OB_MAX_COL_MASKS) - 1)) {
		PyErr_Format(PyExc_AttributeError, "gameOb.collisionMask = int: KX_GameObject, expected a int bit field, 0 < mask < %i", (1 << OB_MAX_COL_MASKS));
		return PY_SET_ATTR_FAIL;
	}

	self->SetCollisionMask(val);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_scene(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	KX_Scene *scene = self->GetScene();
	if (scene) {
		return scene->GetProxy();
	}
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::pyattr_get_group_object(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	KX_GameObject *pivot = self->GetDupliGroupObject();
	if (pivot) {
		return pivot->GetProxy();
	}
	Py_RETURN_NONE;
}

PyObject *KX_GameObject::pyattr_get_life(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	// None (not 0.0) for objects without lifetime keeps the historical API.
	if (self->m_lifeTime > 0.0f) {
		return PyFloat_FromDouble(self->m_lifeTime * LifeFramesPerSecond);
	}
	Py_RETURN_NONE;
}

int KX_GameObject::pyattr_set_life(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	float frames = 0.0f;
	if (value != Py_None) {
		frames = PyFloat_AsDouble(value);
		if (frames == -1.0f && PyErr_Occurred()) {
			PyErr_SetString(PyExc_TypeError, "gameOb.life = float or None: KX_GameObject, expected a number (frames) or None");
			return PY_SET_ATTR_FAIL;
		}
		if (!(frames >= 0.0f)) {
			PyErr_SetString(PyExc_ValueError, "gameOb.life = float: KX_GameObject, expected zero or above (0/None = lives forever)");
			return PY_SET_ATTR_FAIL;
		}
	}

	KX_Scene *scene = self->GetScene();
	if (!scene->SetObjectLifeTime(self, frames / LifeFramesPerSecond)) {
		PyErr_SetString(PyExc_ValueError, "gameOb.life: KX_GameObject, can't set life on an inactive (template) object");
		return PY_SET_ATTR_FAIL;
	}
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_mass(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	return PyFloat_FromDouble(spc ? spc->GetMass() : 0.0f);
}

int KX_GameObject::pyattr_set_mass(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	float val = PyFloat_AsDouble(value);
	if (val < 0.0f) { /* also accounts for non float */
		PyErr_SetString(PyExc_AttributeError, "gameOb.mass = float: KX_GameObject, expected a float zero or above");
		return PY_SET_ATTR_FAIL;
	}

	if (spc) {
		spc->SetMass(val);
	}

	return PY_SET_ATTR_SUCCESS;
}

PyObject* KX_GameObject::pyattr_get_friction(EXP_PyObjectPlus* self_v,
	const EXP_PYATTRIBUTE_DEF* attrdef)
{
	KX_GameObject* self = static_cast<KX_GameObject*>(self_v);
	PHY_IPhysicsController* spc = self->GetPhysicsController();
	return PyFloat_FromDouble(spc ? spc->GetFriction() : 0.0f);
}

int KX_GameObject::pyattr_set_friction(EXP_PyObjectPlus* self_v,
	const EXP_PYATTRIBUTE_DEF* attrdef,
	PyObject* value)
{
	KX_GameObject* self = static_cast<KX_GameObject*>(self_v);
	PHY_IPhysicsController* spc = self->GetPhysicsController();
	float val = PyFloat_AsDouble(value);
	if (val < 0.0f) { /* also accounts for non float */
		PyErr_SetString(PyExc_AttributeError,
			"gameOb.friction = float: KX_GameObject, expected a float zero or above");
		return PY_SET_ATTR_FAIL;
	}

	if (spc)
		spc->SetFriction(val);

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_anisotropicFriction(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	return PyBool_FromLong(spc ? spc->GetAnisotropicFrictionEnabled() : false);
}

int KX_GameObject::pyattr_set_anisotropicFriction(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	const int enabled = PyObject_IsTrue(value);
	if (enabled == -1) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.anisotropicFriction = bool: KX_GameObject, expected True or False");
		return PY_SET_ATTR_FAIL;
	}
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	if (spc) {
		spc->SetAnisotropicFrictionEnabled(enabled);
	}
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_anisotropicFrictionCoefficients(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	return PyObjectFrom(spc ? spc->GetAnisotropicFriction() : mt::one3);
}

int KX_GameObject::pyattr_set_anisotropicFrictionCoefficients(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	mt::vec3 friction;
	if (!PyVecTo(value, friction)) {
		return PY_SET_ATTR_FAIL;
	}
	if (friction.x < 0.0f || friction.y < 0.0f || friction.z < 0.0f) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.anisotropicFrictionCoefficients = [x, y, z]: KX_GameObject, expected values zero or above");
		return PY_SET_ATTR_FAIL;
	}
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	if (spc) {
		spc->SetAnisotropicFriction(friction);
	}
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_is_suspend_dynamics(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	// Only objects with a physics controller can be suspended
	PYTHON_CHECK_PHYSICS_CONTROLLER(self, attrdef->m_name.c_str(), nullptr);

	return PyBool_FromLong(self->IsDynamicsSuspended());
}

PyObject *KX_GameObject::pyattr_get_is_destructible(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyBool_FromLong(self->GetScene()->GetDestructionManager().IsDestructible(self));
}

PyObject *KX_GameObject::pyattr_get_is_explosive(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyBool_FromLong(self->GetScene()->GetDestructionManager().IsExplosive(self));
}

PyObject *KX_GameObject::pyattr_get_break_impulse(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyFloat_FromDouble(self->GetScene()->GetDestructionManager().GetBreakImpulse(self));
}

int KX_GameObject::pyattr_set_break_impulse(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	const float impulse = PyFloat_AsDouble(value);
	if (impulse == -1.0f && PyErr_Occurred()) {
		PyErr_SetString(PyExc_TypeError, "gameOb.breakImpulse = float: KX_GameObject, expected a float");
		return PY_SET_ATTR_FAIL;
	}
	if (!self->GetScene()->GetDestructionManager().SetBreakImpulse(self, impulse)) {
		PyErr_Format(PyExc_AttributeError, "gameOb.breakImpulse = float: KX_GameObject, \"%s\" is not destructible",
		             self->GetName().c_str());
		return PY_SET_ATTR_FAIL;
	}
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_destruction_callbacks(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PyObject *&list = (attrdef->m_name == "onBreak") ? self->m_breakCallbacks :
	                  (attrdef->m_name == "onDent") ? self->m_dentCallbacks : self->m_explodeCallbacks;
	if (!list) {
		list = PyList_New(0);
	}
	Py_INCREF(list);
	return list;
}

int KX_GameObject::pyattr_set_destruction_callbacks(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	if (!PyList_CheckExact(value)) {
		PyErr_Format(PyExc_ValueError, "gameOb.%s = list: KX_GameObject, expected a list", attrdef->m_name.c_str());
		return PY_SET_ATTR_FAIL;
	}
	PyObject *&list = (attrdef->m_name == "onBreak") ? self->m_breakCallbacks :
	                  (attrdef->m_name == "onDent") ? self->m_dentCallbacks : self->m_explodeCallbacks;
	Py_INCREF(value);
	Py_XDECREF(list);
	list = value;
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_fuse(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyFloat_FromDouble(self->GetScene()->GetDestructionManager().GetFuse(self));
}

int KX_GameObject::pyattr_set_fuse(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	const float seconds = PyFloat_AsDouble(value);
	if (seconds == -1.0f && PyErr_Occurred()) {
		PyErr_SetString(PyExc_TypeError, "gameOb.fuse = float: KX_GameObject, expected a float");
		return PY_SET_ATTR_FAIL;
	}
	if (!self->GetScene()->GetDestructionManager().SetFuse(self, seconds)) {
		PyErr_Format(PyExc_AttributeError, "gameOb.fuse = float: KX_GameObject, \"%s\" is not explosive",
		             self->GetName().c_str());
		return PY_SET_ATTR_FAIL;
	}
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_lin_vel_min(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	return PyFloat_FromDouble(spc ? spc->GetLinVelocityMin() : 0.0f);
}

int KX_GameObject::pyattr_set_lin_vel_min(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	float val = PyFloat_AsDouble(value);
	if (val < 0.0f) { /* also accounts for non float */
		PyErr_SetString(PyExc_AttributeError, "gameOb.linVelocityMin = float: KX_GameObject, expected a float zero or above");
		return PY_SET_ATTR_FAIL;
	}

	if (spc) {
		spc->SetLinVelocityMin(val);
	}

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_lin_vel_max(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	return PyFloat_FromDouble(spc ? spc->GetLinVelocityMax() : 0.0f);
}

int KX_GameObject::pyattr_set_lin_vel_max(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	float val = PyFloat_AsDouble(value);
	if (val < 0.0f) { /* also accounts for non float */
		PyErr_SetString(PyExc_AttributeError, "gameOb.linVelocityMax = float: KX_GameObject, expected a float zero or above");
		return PY_SET_ATTR_FAIL;
	}

	if (spc) {
		spc->SetLinVelocityMax(val);
	}

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_ang_vel_min(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	return PyFloat_FromDouble(spc ? spc->GetAngularVelocityMin() : 0.0f);
}

int KX_GameObject::pyattr_set_ang_vel_min(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	float val = PyFloat_AsDouble(value);
	if (val < 0.0f) { /* also accounts for non float */
		PyErr_SetString(PyExc_AttributeError,
		                "gameOb.angularVelocityMin = float: KX_GameObject, expected a nonnegative float");
		return PY_SET_ATTR_FAIL;
	}

	if (spc) {
		spc->SetAngularVelocityMin(val);
	}

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_ang_vel_max(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	return PyFloat_FromDouble(spc ? spc->GetAngularVelocityMax() : 0.0f);
}

int KX_GameObject::pyattr_set_ang_vel_max(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PHY_IPhysicsController *spc = self->GetPhysicsController();
	float val = PyFloat_AsDouble(value);
	if (val < 0.0f) { /* also accounts for non float */
		PyErr_SetString(PyExc_AttributeError,
		                "gameOb.angularVelocityMax = float: KX_GameObject, expected a nonnegative float");
		return PY_SET_ATTR_FAIL;
	}

	if (spc) {
		spc->SetAngularVelocityMax(val);
	}

	return PY_SET_ATTR_SUCCESS;
}


PyObject *KX_GameObject::pyattr_get_layer(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyLong_FromLong(self->GetLayer());
}

#define MAX_LAYERS ((1 << 20) - 1)
int KX_GameObject::pyattr_set_layer(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	int layer = PyLong_AsLong(value);

	if (layer == -1 && PyErr_Occurred()) {
		PyErr_Format(PyExc_TypeError, "expected an integer for attribute \"%s\"", attrdef->m_name.c_str());
		return PY_SET_ATTR_FAIL;
	}

	if (layer < 1) {
		PyErr_Format(PyExc_TypeError, "expected an integer greater than 1 for attribute \"%s\"", attrdef->m_name.c_str());
		return PY_SET_ATTR_FAIL;
	}
	else if (layer > MAX_LAYERS) {
		PyErr_Format(PyExc_TypeError, "expected an integer less than %i for attribute \"%s\"", MAX_LAYERS, attrdef->m_name.c_str());
		return PY_SET_ATTR_FAIL;
	}

	self->SetLayer(layer);
	return PY_SET_ATTR_SUCCESS;
}
#undef MAX_LAYERS

PyObject *KX_GameObject::pyattr_get_visible(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyBool_FromLong(self->GetVisible());
}

PyObject *KX_GameObject::pyattr_get_hidden_from_camera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	KX_Camera *cam = self->m_hiddenFromCamera;
	if (!cam) {
		Py_RETURN_NONE;
	}
	return cam->GetProxy();
}

int KX_GameObject::pyattr_set_hidden_from_camera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	KX_Camera *cam = nullptr;
	if (!ConvertPythonToCamera(self->GetScene(), value, &cam, true, "gameOb.hiddenFromCamera = camera: KX_GameObject")) {
		return PY_SET_ATTR_FAIL;
	}
	self->SetHiddenFromCamera(cam);
	return PY_SET_ATTR_SUCCESS;
}

int KX_GameObject::pyattr_set_visible(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	int param = PyObject_IsTrue(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.visible = bool: KX_GameObject, expected True or False");
		return PY_SET_ATTR_FAIL;
	}

	self->SetVisible(param, false);
	return PY_SET_ATTR_SUCCESS;
}


int KX_GameObject::pyattr_set_halfanimations(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	int param = PyObject_IsTrue(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.setHalfAnimations = bool: KX_GameObject, expected True or False");
		return PY_SET_ATTR_FAIL;
	}

	self->SetHalfAnimations(param);
	return PY_SET_ATTR_SUCCESS;
}


PyObject *KX_GameObject::pyattr_get_culled(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyBool_FromLong(self->GetCullingNode().GetCulled());
}

PyObject *KX_GameObject::pyattr_get_cullingBox(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return (new KX_BoundingBox(self))->NewProxy(true);
}

PyObject *KX_GameObject::pyattr_get_physicsCulling(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyBool_FromLong(self->GetActivityCullingInfo().m_flags & ActivityCullingInfo::ACTIVITY_PHYSICS);
}

int KX_GameObject::pyattr_set_physicsCulling(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	int param = PyObject_IsTrue(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.physicsCulling = bool: KX_GameObject, expected True or False");
		return PY_SET_ATTR_FAIL;
	}

	self->SetActivityCulling(ActivityCullingInfo::ACTIVITY_PHYSICS, param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject* KX_GameObject::pyattr_get_physicsSleepVelocityCulling(EXP_PyObjectPlus* self_v, const EXP_PYATTRIBUTE_DEF* attrdef)
{
	KX_GameObject* self = static_cast<KX_GameObject*>(self_v);
	return PyBool_FromLong(self->GetActivityCullingInfo().m_flags & ActivityCullingInfo::ACTIVITY_PHYSICS_SLEEPVELOCITY);
}

int KX_GameObject::pyattr_set_physicsSleepVelocityCulling(EXP_PyObjectPlus* self_v, const EXP_PYATTRIBUTE_DEF* attrdef, PyObject* value)
{
	KX_GameObject* self = static_cast<KX_GameObject*>(self_v);
	int param = PyObject_IsTrue(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.physicsSleepVelocityCulling = bool: KX_GameObject, expected True or False");
		return PY_SET_ATTR_FAIL;
	}

	self->SetActivityCulling(ActivityCullingInfo::ACTIVITY_PHYSICS_SLEEPVELOCITY, param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_logicCulling(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyBool_FromLong(self->GetActivityCullingInfo().m_flags & ActivityCullingInfo::ACTIVITY_LOGIC);
} 

int KX_GameObject::pyattr_set_logicCulling(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	int param = PyObject_IsTrue(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.logicCulling = bool: KX_GameObject, expected True or False");
		return PY_SET_ATTR_FAIL;
	}

	self->SetActivityCulling(ActivityCullingInfo::ACTIVITY_LOGIC, param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject* KX_GameObject::pyattr_get_logicComponentsCulling(EXP_PyObjectPlus* self_v, const EXP_PYATTRIBUTE_DEF* attrdef)
{
	KX_GameObject* self = static_cast<KX_GameObject*>(self_v);
	return PyBool_FromLong(self->GetActivityCullingInfo().m_flags & ActivityCullingInfo::ACTIVITY_LOGIC_COMPONENTS);
}

int KX_GameObject::pyattr_set_logicComponentsCulling(EXP_PyObjectPlus* self_v, const EXP_PYATTRIBUTE_DEF* attrdef, PyObject* value)
{
	KX_GameObject* self = static_cast<KX_GameObject*>(self_v);
	int param = PyObject_IsTrue(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.logicComponentsCulling = bool: KX_GameObject, expected True or False");
		return PY_SET_ATTR_FAIL;
	}

	self->SetActivityCulling(ActivityCullingInfo::ACTIVITY_LOGIC_COMPONENTS, param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_physicsCullingRadius(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyFloat_FromDouble(std::sqrt(self->GetActivityCullingInfo().m_physicsRadius));
}

int KX_GameObject::pyattr_set_physicsCullingRadius(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	const float val = PyFloat_AsDouble(value);
	if (val < 0.0f) { // Also accounts for non float.
		PyErr_SetString(PyExc_AttributeError, "gameOb.physicsCullingRadius = float: KX_GameObject, expected a float zero or above");
		return PY_SET_ATTR_FAIL;
	}

	self->GetActivityCullingInfo().m_physicsRadius = val * val;

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_logicCullingRadius(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyFloat_FromDouble(std::sqrt(self->GetActivityCullingInfo().m_logicRadius));
}

int KX_GameObject::pyattr_set_logicCullingRadius(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	const float val = PyFloat_AsDouble(value);
	if (val < 0.0f) { // Also accounts for non float.
		PyErr_SetString(PyExc_AttributeError, "gameOb.logicCullingRadius = float: KX_GameObject, expected a float zero or above");
		return PY_SET_ATTR_FAIL;
	}

	self->GetActivityCullingInfo().m_logicRadius = val * val;

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_worldPosition(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_kxgameob_vector_cb_index, MATHUTILS_VEC_CB_POS_GLOBAL);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(self->NodeGetWorldPosition());
#endif
}

int KX_GameObject::pyattr_set_worldPosition(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	mt::vec3 pos;
	if (!PyVecTo(value, pos)) {
		return PY_SET_ATTR_FAIL;
	}

	self->NodeSetWorldPosition(pos);
	self->NodeUpdate();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_localPosition(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_kxgameob_vector_cb_index, MATHUTILS_VEC_CB_POS_LOCAL);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(self->NodeGetLocalPosition());
#endif
}

int KX_GameObject::pyattr_set_localPosition(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	mt::vec3 pos;
	if (!PyVecTo(value, pos)) {
		return PY_SET_ATTR_FAIL;
	}

	self->NodeSetLocalPosition(pos);
	self->NodeUpdate();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_localInertia(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_kxgameob_vector_cb_index, MATHUTILS_VEC_CB_INERTIA_LOCAL);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	if (self->GetPhysicsController1()) {
		return PyObjectFrom(self->GetPhysicsController1()->GetLocalInertia());
	}
	return PyObjectFrom(mt::zero3);
#endif
}

PyObject *KX_GameObject::pyattr_get_worldOrientation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Matrix_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3, 3,
		mathutils_kxgameob_matrix_cb_index, MATHUTILS_MAT_CB_ORI_GLOBAL);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(self->NodeGetWorldOrientation());
#endif
}

int KX_GameObject::pyattr_set_worldOrientation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	/* if value is not a sequence PyOrientationTo makes an error */
	mt::mat3 rot;
	if (!PyOrientationTo(value, rot, "gameOb.worldOrientation = sequence: KX_GameObject, ")) {
		return PY_SET_ATTR_FAIL;
	}

	self->NodeSetGlobalOrientation(rot);

	self->NodeUpdate();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_localOrientation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Matrix_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3, 3,
		mathutils_kxgameob_matrix_cb_index, MATHUTILS_MAT_CB_ORI_LOCAL);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(self->NodeGetLocalOrientation());
#endif
}

int KX_GameObject::pyattr_set_localOrientation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	/* if value is not a sequence PyOrientationTo makes an error */
	mt::mat3 rot;
	if (!PyOrientationTo(value, rot, "gameOb.localOrientation = sequence: KX_GameObject, ")) {
		return PY_SET_ATTR_FAIL;
	}

	self->NodeSetLocalOrientation(rot);
	self->NodeUpdate();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_worldScaling(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_kxgameob_vector_cb_index, MATHUTILS_VEC_CB_SCALE_GLOBAL);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(self->NodeGetWorldScaling());
#endif
}

int KX_GameObject::pyattr_set_worldScaling(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	mt::vec3 scale;
	if (!PyVecTo(value, scale)) {
		return PY_SET_ATTR_FAIL;
	}

	self->NodeSetWorldScale(scale);
	self->NodeUpdate();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_localScaling(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_kxgameob_vector_cb_index, MATHUTILS_VEC_CB_SCALE_LOCAL);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(self->NodeGetLocalScaling());
#endif
}

int KX_GameObject::pyattr_set_localScaling(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	mt::vec3 scale;
	if (!PyVecTo(value, scale)) {
		return PY_SET_ATTR_FAIL;
	}

	self->NodeSetLocalScale(scale);
	self->NodeUpdate();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_localTransform(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	return PyObjectFrom(mt::mat4::FromAffineTransform(self->NodeGetLocalTransform()));
}

int KX_GameObject::pyattr_set_localTransform(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
  mt::mat4 temp;
  float position[3], rotation[3][3], size[3];

	if (!PyMatTo(value, temp)) {
		return PY_SET_ATTR_FAIL;
	}

	float transform[4][4] = {temp(0, 0), temp(1, 0), temp(2, 0), temp(3, 0),
							 temp(0, 1), temp(1, 1), temp(2, 1), temp(3, 1),
							 temp(0, 2), temp(1, 2), temp(2, 2), temp(3, 2),
							 temp(0, 3), temp(1, 3), temp(2, 3), temp(3, 3)};

  mat4_to_loc_rot_size(position, rotation, size, transform);

  self->NodeSetLocalPosition(mt::vec3(position));
  self->NodeSetLocalOrientation(mt::mat3(rotation));
  self->NodeSetLocalScale(mt::vec3(size));

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_worldTransform(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	return PyObjectFrom(mt::mat4::FromAffineTransform(self->NodeGetWorldTransform()));
}

int KX_GameObject::pyattr_set_worldTransform(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
  mt::mat4 temp;
  float position[3], rotation[3][3], size[3];

  if (!PyMatTo(value, temp)) {
    return PY_SET_ATTR_FAIL;
  }

  float transform[4][4] = {temp(0, 0), temp(1, 0), temp(2, 0), temp(3, 0),
						   temp(0, 1), temp(1, 1), temp(2, 1), temp(3, 1),
						   temp(0, 2), temp(1, 2), temp(2, 2), temp(3, 2),
						   temp(0, 3), temp(1, 3), temp(2, 3), temp(3, 3)};

  mat4_to_loc_rot_size(position, rotation, size, transform);

  self->NodeSetWorldPosition(mt::vec3(position));
  self->NodeSetGlobalOrientation(mt::mat3(rotation));
  self->NodeSetWorldScale(mt::vec3(size));

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_worldLinearVelocity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_kxgameob_vector_cb_index, MATHUTILS_VEC_CB_LINVEL_GLOBAL);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(GetLinearVelocity(false));
#endif
}

int KX_GameObject::pyattr_set_worldLinearVelocity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	mt::vec3 velocity;
	if (!PyVecTo(value, velocity)) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetLinearVelocity(velocity, false);

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_localLinearVelocity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_kxgameob_vector_cb_index, MATHUTILS_VEC_CB_LINVEL_LOCAL);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(GetLinearVelocity(true));
#endif
}

int KX_GameObject::pyattr_set_localLinearVelocity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	mt::vec3 velocity;
	if (!PyVecTo(value, velocity)) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetLinearVelocity(velocity, true);

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_worldAngularVelocity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_kxgameob_vector_cb_index, MATHUTILS_VEC_CB_ANGVEL_GLOBAL);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(GetAngularVelocity(false));
#endif
}

int KX_GameObject::pyattr_set_worldAngularVelocity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	mt::vec3 velocity;
	if (!PyVecTo(value, velocity)) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetAngularVelocity(velocity, false);

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_localAngularVelocity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_kxgameob_vector_cb_index, MATHUTILS_VEC_CB_ANGVEL_LOCAL);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(GetAngularVelocity(true));
#endif
}

int KX_GameObject::pyattr_set_localAngularVelocity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	mt::vec3 velocity;
	if (!PyVecTo(value, velocity)) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetAngularVelocity(velocity, true);

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_kxgameob_vector_cb_index, MATHUTILS_VEC_CB_GRAVITY);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(GetGravity());
#endif
}

int KX_GameObject::pyattr_set_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	mt::vec3 gravity;
	if (!PyVecTo(value, gravity)) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetGravity(gravity);

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_linearDamping(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyFloat_FromDouble(self->GetLinearDamping());
}

int KX_GameObject::pyattr_set_linearDamping(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	float val = PyFloat_AsDouble(value);
	self->SetLinearDamping(val);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_angularDamping(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyFloat_FromDouble(self->GetAngularDamping());
}

int KX_GameObject::pyattr_set_angularDamping(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	float val = PyFloat_AsDouble(value);
	self->SetAngularDamping(val);
	return PY_SET_ATTR_SUCCESS;
}


PyObject *KX_GameObject::pyattr_get_timeOffset(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	SG_Node *sg_parent;
	if ((sg_parent = self->m_sgNode->GetParent()) != nullptr && sg_parent->IsSlowParent()) {
		return PyFloat_FromDouble(static_cast<KX_SlowParentRelation *>(sg_parent->GetParentRelation())->GetTimeOffset());
	}
	else {
		return PyFloat_FromDouble(0.0f);
	}
}

int KX_GameObject::pyattr_set_timeOffset(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	float val = PyFloat_AsDouble(value);
	SG_Node *sg_parent = self->m_sgNode->GetParent();
	if (val < 0.0f) { /* also accounts for non float */
		PyErr_SetString(PyExc_AttributeError, "gameOb.timeOffset = float: KX_GameObject, expected a float zero or above");
		return PY_SET_ATTR_FAIL;
	}
	if (sg_parent && sg_parent->IsSlowParent()) {
		static_cast<KX_SlowParentRelation *>(sg_parent->GetParentRelation())->SetTimeOffset(val);
	}
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_state(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	int state = 0;
	state |= self->GetState();
	return PyLong_FromLong(state);
}

int KX_GameObject::pyattr_set_state(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	int state_i = PyLong_AsLong(value);
	unsigned int state = 0;

	if (state_i == -1 && PyErr_Occurred()) {
		PyErr_SetString(PyExc_TypeError, "gameOb.state = int: KX_GameObject, expected an int bit field");
		return PY_SET_ATTR_FAIL;
	}

	state |= state_i;
	if ((state & ((1 << 30) - 1)) == 0) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.state = int: KX_GameObject, state bitfield was not between 0 and 30 (1<<0 and 1<<29)");
		return PY_SET_ATTR_FAIL;
	}
	self->SetState(state);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_meshes(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	PyObject *meshes = PyList_New(self->m_meshes.size());
	int i;

	for (i = 0; i < (int)self->m_meshes.size(); i++)
	{
		PyObject *item = self->m_meshes[i]->GetProxy();
		Py_INCREF(item);
		PyList_SET_ITEM(meshes, i, item);
	}

	return meshes;
}

PyObject *KX_GameObject::pyattr_get_batchGroup(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	RAS_MeshUser *meshUser = self->GetMeshUser();
	if (!meshUser) {
		Py_RETURN_NONE;
	}

	KX_BatchGroup *batchGroup = (KX_BatchGroup *)meshUser->GetBatchGroup();
	if (!batchGroup) {
		Py_RETURN_NONE;
	}

	return batchGroup->GetProxy();
}

PyObject *KX_GameObject::pyattr_get_obcolor(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 4,
		mathutils_kxgameob_vector_cb_index, MATHUTILS_VEC_CB_OBJECT_COLOR);
#else
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyObjectFrom(self->GetObjectColor());
#endif
}

int KX_GameObject::pyattr_set_obcolor(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	mt::vec4 obcolor;
	if (!PyVecTo(value, obcolor)) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetObjectColor(obcolor);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_activitycullingdistance(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	return PyFloat_FromDouble(self->m_distance);
}

PyObject *KX_GameObject::pyattr_get_components(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	EXP_ListValue<KX_PythonComponent> *components = self->GetComponents();
	return components ? components->GetProxy() : (new EXP_ListValue<KX_PythonComponent>())->NewProxy(true);
}

unsigned int KX_GameObject::py_get_sensors_size()
{
	return m_sensors.size();
}

PyObject *KX_GameObject::py_get_sensors_item(unsigned int index)
{
	return m_sensors[index]->GetProxy();
}

std::string KX_GameObject::py_get_sensors_item_name(unsigned int index)
{
	return m_sensors[index]->GetName();
}

PyObject *KX_GameObject::pyattr_get_sensors(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	return (new EXP_ListWrapper<KX_GameObject, &KX_GameObject::py_get_sensors_size, &KX_GameObject::py_get_sensors_item,
				nullptr, &KX_GameObject::py_get_sensors_item_name>(self_v))->NewProxy(true);
}

unsigned int KX_GameObject::py_get_controllers_size()
{
	return m_controllers.size();
}

PyObject *KX_GameObject::py_get_controllers_item(unsigned int index)
{
	return m_controllers[index]->GetProxy();
}

std::string KX_GameObject::py_get_controllers_item_name(unsigned int index)
{
	return m_controllers[index]->GetName();
}

PyObject *KX_GameObject::pyattr_get_controllers(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	return (new EXP_ListWrapper<KX_GameObject, &KX_GameObject::py_get_controllers_size, &KX_GameObject::py_get_controllers_item,
				nullptr, &KX_GameObject::py_get_controllers_item_name>(self_v))->NewProxy(true);
}

unsigned int KX_GameObject::py_get_actuators_size()
{
	return m_actuators.size();
}

PyObject *KX_GameObject::py_get_actuators_item(unsigned int index)
{
	return m_actuators[index]->GetProxy();
}

std::string KX_GameObject::py_get_actuators_item_name(unsigned int index)
{
	return m_actuators[index]->GetName();
}

PyObject *KX_GameObject::pyattr_get_actuators(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	return (new EXP_ListWrapper<KX_GameObject, &KX_GameObject::py_get_actuators_size, &KX_GameObject::py_get_actuators_item,
				nullptr, &KX_GameObject::py_get_actuators_item_name>(self_v))->NewProxy(true);
}

PyObject *KX_GameObject::pyattr_get_children(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	EXP_ListValue<KX_GameObject> *list = new EXP_ListValue<KX_GameObject>(self->GetChildren());
	/* The list must not own any data because is temporary and we can't
	 * ensure that it will freed before item's in it (e.g python owner). */
	list->SetReleaseOnDestruct(false);
	return list->NewProxy(true);
}

PyObject *KX_GameObject::pyattr_get_children_recursive(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	EXP_ListValue<KX_GameObject> *list = new EXP_ListValue<KX_GameObject>(self->GetChildrenRecursive());
	/* The list must not own any data because is temporary and we can't
	 * ensure that it will freed before item's in it (e.g python owner). */
	list->SetReleaseOnDestruct(false);
	return list->NewProxy(true);
}

PyObject *KX_GameObject::pyattr_get_attrDict(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	if (self->m_attr_dict == nullptr) {
		self->m_attr_dict = PyDict_New();
	}

	Py_INCREF(self->m_attr_dict);
	return self->m_attr_dict;
}

PyObject *KX_GameObject::pyattr_get_debug(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	return PyBool_FromLong(self->GetScene()->ObjectInDebugList(self));
}

int KX_GameObject::pyattr_set_debug(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	int param = PyObject_IsTrue(value);

	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.debug = bool: KX_GameObject, expected True or False");
		return PY_SET_ATTR_FAIL;
	}

	self->SetUseDebugProperties(param, false);

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_debugRecursive(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	return PyBool_FromLong(self->GetScene()->ObjectInDebugList(self));
}

int KX_GameObject::pyattr_set_debugRecursive(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	int param = PyObject_IsTrue(value);

	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "gameOb.debugRecursive = bool: KX_GameObject, expected True or False");
		return PY_SET_ATTR_FAIL;
	}

	self->SetUseDebugProperties(param, true);

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_lodManager(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	return (self->m_lodManager) ? self->m_lodManager->GetProxy() : Py_None;
}

int KX_GameObject::pyattr_set_lodManager(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	KX_LodManager *lodManager = nullptr;
	if (!ConvertPythonToLodManager(value, &lodManager, true, "gameobj.lodManager: KX_GameObject")) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetLodManager(lodManager);

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_GameObject::pyattr_get_animationEventsManager(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);

	if (!self->m_animationEventManager) {
		Py_RETURN_NONE;
	}

	return self->m_animationEventManager->GetProxy();
}

PyObject *KX_GameObject::pyattr_get_particles(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	RAS_ParticleBuffer *buffer = self->GetParticleBuffer();

	if (!buffer) {
		Py_RETURN_NONE;
	}

	return (new KX_ParticleSystem(buffer))->NewProxy(true);
}

PyObject *KX_GameObject::pyattr_get_particles_mix(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_GameObject *self = static_cast<KX_GameObject *>(self_v);
	RAS_ParticleBuffer *buffer = self->GetParticleBufferMix();

	if (!buffer) {
		Py_RETURN_NONE;
	}

	return (new KX_ParticleSystem(buffer))->NewProxy(true);
}

#endif // WITH_PYTHON
