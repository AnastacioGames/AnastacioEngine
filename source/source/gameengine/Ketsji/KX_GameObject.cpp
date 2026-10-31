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
 * Game object wrapper
 */

/** \file gameengine/Ketsji/KX_GameObject.cpp
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

KX_GameObject::ActivityCullingInfo::ActivityCullingInfo()
	:m_flags(ACTIVITY_NONE),
	m_physicsRadius(0.0f),
	m_logicRadius(0.0f)
{
}

KX_GameObject::KX_GameObject(void *sgReplicationInfo,
                             SG_Callbacks callbacks)
	:m_clientInfo(this, KX_ClientObjectInfo::ACTOR),
	m_netId(0),
	m_layer(0),
	m_passIndex(0),
	m_lodManager(nullptr),
	m_animationEventManager(nullptr),
	m_currentLodLevel(0),
	m_meshUser(nullptr),
	m_wantsImpostorAtlasDeformer(false),
	m_wantsDentDeformer(false),
	m_lodBillboardActive(false),
	m_lodBillboardOrientation(mt::mat3::Identity()),
	m_currentAtlasCell(-1),
	m_convertInfo(nullptr),
	m_objectColor(mt::one4),
	m_distance(0.0f),
	m_lifeTime(0.0f),
	m_bVisible(true),
	m_bRender(true),
	m_bVisibleLOD(true),
	m_bOccluder(false),
	m_halfAnimations(false),
	m_bDoAnimations(true),
	m_autoUpdateBounds(false),
	m_debugProfilingData({false, 0.0f, 0.0f}),
	m_physicsController(nullptr),
	m_graphicController(nullptr),
	m_vehicleConstraintId(-1),
	m_vehicleMaxTorque(0.0f),
	m_vehicleMaxRPM(0.0f),
	m_vehicleGearboxType(0),
	m_sgNode(new SG_Node(this, sgReplicationInfo, callbacks)),
	m_components(nullptr),
	m_instanceObjects(nullptr),
	m_dupliGroupObject(nullptr),
	m_actionManager(nullptr),
	m_particleBuffer(nullptr),
	m_collisionGroundObject(nullptr)
#ifdef WITH_PYTHON
	, m_attr_dict(nullptr),
	m_collisionCallbacks(nullptr),
	m_breakCallbacks(nullptr),
	m_explodeCallbacks(nullptr),
	m_dentCallbacks(nullptr)
#endif
{
	// define the relationship between this node and it's parent.
	KX_NormalParentRelation *parent_relation = new KX_NormalParentRelation();
	m_sgNode->SetParentRelation(parent_relation);
}

KX_GameObject::KX_GameObject(const KX_GameObject& other)
	:SCA_IObject(other),
	m_clientInfo(this, other.m_clientInfo.m_type),
	m_netId(0),
	m_name(other.m_name),
	m_layer(other.m_layer),
	m_passIndex(other.m_passIndex),
	m_meshes(other.m_meshes),
	m_lodManager(other.m_lodManager),
	m_animationEventManager(nullptr),
	m_currentLodLevel(0),
	m_meshUser(nullptr),
	m_wantsImpostorAtlasDeformer(false),
	m_wantsDentDeformer(false),
	m_lodBillboardActive(other.m_lodBillboardActive),
	m_lodBillboardOrientation(other.m_lodBillboardOrientation),
	m_currentAtlasCell(-1),
	m_convertInfo(other.m_convertInfo),
	m_objectColor(other.m_objectColor),
	m_distance(other.m_distance),
	// Not inherited: a replica only dies if its own addObject()/life asks for it.
	m_lifeTime(0.0f),
	m_bVisible(other.m_bVisible),
	m_bRender(other.m_bRender),
	m_bVisibleLOD(other.m_bVisibleLOD),
	m_bOccluder(other.m_bOccluder),
	m_halfAnimations(other.m_halfAnimations),
	m_bDoAnimations(other.m_bDoAnimations),
	m_activityCullingInfo(other.m_activityCullingInfo),
	m_autoUpdateBounds(other.m_autoUpdateBounds),
	m_debugProfilingData(other.m_debugProfilingData),
	m_physicsController(nullptr),
	m_graphicController(nullptr),
	m_vehicleConstraintId(-1),
	m_vehicleMaxTorque(0.0f),
	m_vehicleMaxRPM(0.0f),
	m_vehicleGearboxType(0),
	m_sgNode(nullptr),
	m_components(nullptr),
	m_instanceObjects(nullptr),
	m_dupliGroupObject(nullptr),
	m_actionManager(nullptr),
	m_particleBuffer(nullptr),
	m_collisionGroundObject(nullptr)
#ifdef WITH_PYTHON
	, m_attr_dict(other.m_attr_dict),
	m_collisionCallbacks(other.m_collisionCallbacks),
	m_breakCallbacks(nullptr),
	m_explodeCallbacks(nullptr),
	m_dentCallbacks(nullptr)
#endif  // WITH_PYTHON
{
	if (m_lodManager) {
		m_lodManager->AddRef();
	}

	// Each replica gets its own events, so trigger state and sensors stay per object.
	if (other.m_animationEventManager) {
		m_animationEventManager = new KX_AnimationEventManager(*other.m_animationEventManager);
	}

#ifdef WITH_PYTHON
	if (m_attr_dict) {
		m_attr_dict = PyDict_Copy(m_attr_dict);
	}

	Py_XINCREF(m_collisionCallbacks);

	// Own lists: a callback added to one replica doesn't reach its siblings.
	if (other.m_breakCallbacks) {
		m_breakCallbacks = PyList_GetSlice(other.m_breakCallbacks, 0, PY_SSIZE_T_MAX);
	}
	if (other.m_explodeCallbacks) {
		m_explodeCallbacks = PyList_GetSlice(other.m_explodeCallbacks, 0, PY_SSIZE_T_MAX);
	}
	if (other.m_dentCallbacks) {
		m_dentCallbacks = PyList_GetSlice(other.m_dentCallbacks, 0, PY_SSIZE_T_MAX);
	}

	if (other.m_components) {
		m_components = static_cast<EXP_ListValue<KX_PythonComponent> *>(other.m_components->GetReplica());

		for (KX_PythonComponent *component : m_components) {
			component->SetGameObject(this);
		}
	}
#endif  // WITH_PYTHON
}

int KX_GameObject::s_hiddenFromCameraCount = 0;

void KX_GameObject::SetHiddenFromCamera(KX_Camera *cam)
{
	if ((m_hiddenFromCamera != nullptr) != (cam != nullptr)) {
		s_hiddenFromCameraCount += cam ? 1 : -1;
	}
	m_hiddenFromCamera = cam;
}

void KX_GameObject::ClearHiddenFromCamera(EXP_ListValue<KX_GameObject> *objects, KX_Camera *cam)
{
	if (s_hiddenFromCameraCount == 0 || !objects) {
		return;
	}
	for (KX_GameObject *obj : objects) {
		if (obj->m_hiddenFromCamera == cam) {
			obj->SetHiddenFromCamera(nullptr);
		}
	}
}

KX_GameObject::~KX_GameObject()
{
	SetHiddenFromCamera(nullptr);
#ifdef WITH_PYTHON
	if (m_attr_dict) {
		PyDict_Clear(m_attr_dict); /* in case of circular refs or other weird cases */
		/* Py_CLEAR: Py_DECREF's and nullptr's */
		Py_CLEAR(m_attr_dict);
	}
	// Unregister collision callbacks
	// Do this before we start freeing physics information like m_clientInfo
	if (m_collisionCallbacks) {
		UnregisterCollisionCallbacks();
		Py_CLEAR(m_collisionCallbacks);
	}
	Py_CLEAR(m_breakCallbacks);
	Py_CLEAR(m_explodeCallbacks);
	Py_CLEAR(m_dentCallbacks);

	if (m_components) {
		m_components->Release();
	}
#endif // WITH_PYTHON

	RemoveMeshes();

	if (m_dupliGroupObject) {
		m_dupliGroupObject->Release();
	}

	if (m_instanceObjects) {
		m_instanceObjects->Release();
	}
	if (m_lodManager) {
		m_lodManager->Release();
	}
	if (m_animationEventManager) {
		m_animationEventManager->Release();
	}

#ifdef WITH_PYTHON
	KX_UnregisterPhysicsControllerId(m_physicsController.get());
#endif
}

KX_GameObject *KX_GameObject::GetClientObject(KX_ClientObjectInfo *info)
{
	if (!info) {
		return nullptr;
	}
	return info->m_gameobject;
}

std::string KX_GameObject::GetName()
{
	return m_name;
}

/* Set the name of the value */
void KX_GameObject::SetName(const std::string& name)
{
	m_name = name;
}

RAS_Deformer *KX_GameObject::GetDeformer()
{
	return (m_meshUser) ? m_meshUser->GetDeformer() : nullptr;
}

PHY_IPhysicsController *KX_GameObject::GetPhysicsController()
{
	return m_physicsController.get();
}

void KX_GameObject::SetVehicleConstraintId(int constraintId)
{
	m_vehicleConstraintId = constraintId;
}

int KX_GameObject::GetVehicleConstraintId() const
{
	return m_vehicleConstraintId;
}

void KX_GameObject::SetVehicleSteeringWheelName(const std::string &name)
{
	m_vehicleSteeringWheelName = name;
}

const std::string &KX_GameObject::GetVehicleSteeringWheelName() const
{
	return m_vehicleSteeringWheelName;
}

void KX_GameObject::SetVehicleMaxTorque(float torque)
{
	m_vehicleMaxTorque = torque;
}

float KX_GameObject::GetVehicleMaxTorque() const
{
	return m_vehicleMaxTorque;
}

void KX_GameObject::SetVehicleMaxRPM(float rpm)
{
	m_vehicleMaxRPM = rpm;
}

float KX_GameObject::GetVehicleMaxRPM() const
{
	return m_vehicleMaxRPM;
}

void KX_GameObject::SetVehicleGearRatios(const std::vector<float> &ratios)
{
	m_vehicleGearRatios = ratios;
}

const std::vector<float> &KX_GameObject::GetVehicleGearRatios() const
{
	return m_vehicleGearRatios;
}

void KX_GameObject::SetVehicleGearboxType(short type)
{
	m_vehicleGearboxType = type;
}

short KX_GameObject::GetVehicleGearboxType() const
{
	return m_vehicleGearboxType;
}

bool KX_GameObject::GetRuntimeProperty(const char *identifier,
	                                     SCA_RuntimePropertyValue& value,
	                                     const char **error)
{
	KX_RuntimePropertyValue runtimeValue;
	if (!KX_RuntimePropertyRegistry::Read(this, identifier, runtimeValue, error)) {
		return false;
	}

	value.type = (runtimeValue.type == KX_RUNTIME_PROPERTY_BOOL) ? SCA_RUNTIME_PROPERTY_BOOL :
	             (runtimeValue.type == KX_RUNTIME_PROPERTY_FLOAT) ? SCA_RUNTIME_PROPERTY_FLOAT :
	                                                             SCA_RUNTIME_PROPERTY_VECTOR3;
	value.boolValue = runtimeValue.boolValue;
	value.floatValue = runtimeValue.floatValue;
	value.vectorValue[0] = runtimeValue.vectorValue[0];
	value.vectorValue[1] = runtimeValue.vectorValue[1];
	value.vectorValue[2] = runtimeValue.vectorValue[2];
	return true;
}

bool KX_GameObject::SetRuntimeProperty(const char *identifier,
	                                     const SCA_RuntimePropertyValue& value,
	                                     const char **error)
{
	if (!identifier) {
		if (error) *error = "Runtime property identifier is unavailable.";
		return false;
	}
	if (!strcmp(identifier, "transform.local_position") && value.type == SCA_RUNTIME_PROPERTY_VECTOR3) {
		NodeSetLocalPosition(mt::vec3(value.vectorValue));
		return true;
	}
	if (!strcmp(identifier, "transform.local_scale") && value.type == SCA_RUNTIME_PROPERTY_VECTOR3) {
		NodeSetLocalScale(mt::vec3(value.vectorValue));
		return true;
	}
	if (!strcmp(identifier, "render.visible") && value.type == SCA_RUNTIME_PROPERTY_BOOL) {
		SetVisible(value.boolValue, false);
		return true;
	}
	if (!strcmp(identifier, "physics.mass") && value.type == SCA_RUNTIME_PROPERTY_FLOAT) {
		PHY_IPhysicsController *controller = GetPhysicsController();
		if (!controller || controller->GetMass() == 0.0f) {
			if (error) *error = "Mass can only be changed on a dynamic physics body.";
			return false;
		}
		if (value.floatValue <= 0.0f) {
			if (error) *error = "Runtime mass must be greater than zero.";
			return false;
		}
		controller->SetMass(value.floatValue);
		return true;
	}
	if (value.type == SCA_RUNTIME_PROPERTY_VECTOR3 && GetPhysicsController()) {
		const mt::vec3 vector(value.vectorValue);
		if (!strcmp(identifier, "physics.linear_velocity")) { SetLinearVelocity(vector, false); return true; }
		if (!strcmp(identifier, "physics.angular_velocity")) { SetAngularVelocity(vector, false); return true; }
		if (!strcmp(identifier, "physics.gravity")) { SetGravity(vector); return true; }
	}
	if (error) *error = "Runtime property is unknown, read-only, or has an incompatible value type.";
	return false;
}

void KX_GameObject::SetPhysicsController(PHY_IPhysicsController *physicscontroller)
{
	if (m_physicsController.get() != physicscontroller) {
#ifdef WITH_PYTHON
		KX_UnregisterPhysicsControllerId(m_physicsController.get());
#endif
	}
	m_physicsController.reset(physicscontroller);
}

PHY_IGraphicController *KX_GameObject::GetGraphicController()
{
	return m_graphicController.get();
}

void KX_GameObject::SetGraphicController(PHY_IGraphicController *graphiccontroller)
{
	m_graphicController.reset(graphiccontroller);
}

KX_GameObject *KX_GameObject::GetDupliGroupObject()
{
	return m_dupliGroupObject;
}

EXP_ListValue<KX_GameObject> *KX_GameObject::GetInstanceObjects()
{
	return m_instanceObjects;
}

void KX_GameObject::AddInstanceObjects(KX_GameObject *obj)
{
	if (!m_instanceObjects) {
		m_instanceObjects = new EXP_ListValue<KX_GameObject>();
	}

	obj->AddRef();
	m_instanceObjects->Add(obj);
}

void KX_GameObject::RemoveInstanceObject(KX_GameObject *obj)
{
	BLI_assert(m_instanceObjects);
	m_instanceObjects->RemoveValue(obj);
	obj->Release();
}

void KX_GameObject::RemoveDupliGroupObject()
{
	if (m_dupliGroupObject) {
		m_dupliGroupObject->Release();
		m_dupliGroupObject = nullptr;
	}
}

void KX_GameObject::SetDupliGroupObject(KX_GameObject *obj)
{
	obj->AddRef();
	m_dupliGroupObject = obj;
}

const std::vector<bRigidBodyJointConstraint *>& KX_GameObject::GetConstraints()
{
	return m_convertInfo->m_constraints;
}

void KX_GameObject::ReplicateConstraints(PHY_IPhysicsEnvironment *physEnv, const std::vector<KX_GameObject *>& constobj)
{
	if (!m_physicsController || m_convertInfo->m_constraints.empty()) {
		return;
	}

	// Object could have some constraints, iterate over all of theme to ensure that every constraint is recreated.
	for (bRigidBodyJointConstraint *dat : m_convertInfo->m_constraints) {
		// Try to find the constraint targets in the list of group objects.
		for (KX_GameObject *member : constobj) {
			// If the group member is the actual target for the constraint.
			if ((dat->tar->id.name + 2) == member->GetName() && member->GetPhysicsController()) {
				physEnv->SetupObjectConstraints(this, member, dat);
			}
		}
	}
}

KX_GameObject *KX_GameObject::GetParent()
{
	KX_GameObject *result = nullptr;
	SG_Node *node = m_sgNode.get();

	while (node && !result)
	{
		node = node->GetParent();
		if (node) {
			result = (KX_GameObject *)node->GetClientObject();
		}
	}

	return result;
}

void KX_GameObject::SetParent(KX_GameObject *obj, bool addToCompound, bool ghost)
{
	// check on valid node in case a python controller holds a reference to a deleted object
	if (!obj) {
		return;
	}

	SG_Node *parentSgNode = obj->GetNode();
	KX_Scene *scene = GetScene();

	// Not already parented to same object, no parenting loop, not the object itself
	if (m_sgNode->GetParent() == parentSgNode || m_sgNode->IsAncessor(parentSgNode) || this == obj) {
		return;
	}

	if (!(scene->GetInactiveList()->SearchValue(obj) != scene->GetObjectList()->SearchValue(this))) {
		CM_FunctionWarning("child and parent are not in the same game objects list (active or inactive). This operation is forbidden.");
		return;
	}

	// Make sure the objects have some scale
	mt::vec3 scale1 = NodeGetWorldScaling();
	mt::vec3 scale2 = obj->NodeGetWorldScaling();
	if (mt::FuzzyZero(scale1) || mt::FuzzyZero(scale2[0]) ||
	    mt::FuzzyZero(scale2[1]) || mt::FuzzyZero(scale2[2])) {
		return;
	}

	// Remove us from our old parent and set our new parent
	RemoveParent();
	parentSgNode->AddChild(m_sgNode.get());

	if (m_physicsController) {
		m_physicsController->SuspendDynamics(ghost);
	}
	
	// Set us to our new scale, position, and orientation
	scale2[0] = 1.0f / scale2[0];
	scale2[1] = 1.0f / scale2[1];
	scale2[2] = 1.0f / scale2[2];
	scale1 = scale1 * scale2;

	const mt::mat3 invori = obj->NodeGetWorldOrientation().Inverse();
	const mt::vec3 newpos = invori * (NodeGetWorldPosition() - obj->NodeGetWorldPosition()) * scale2;

	NodeSetLocalScale(scale1);
	NodeSetLocalPosition(newpos);
	NodeSetLocalOrientation(invori * NodeGetWorldOrientation());
	NodeUpdate();

	// object will now be a child, it must be removed from the parent list
	EXP_ListValue<KX_GameObject> *rootlist = scene->GetRootParentList();
	if (rootlist->RemoveValue(this)) {
		// the object was in parent list, decrement ref count as it's now removed
		Release();
	}

	// if the new parent is a compound object, add this object shape to the compound shape.
	// step 0: verify this object has physical controller
	if (m_physicsController && addToCompound) {
		// step 1: find the top parent (not necessarily obj)
		KX_GameObject *rootobj = (KX_GameObject *)parentSgNode->GetRootSGParent()->GetClientObject();
		// step 2: verify it has a physical controller and compound shape
		if (rootobj != nullptr &&
		    rootobj->m_physicsController != nullptr &&
		    rootobj->m_physicsController->IsCompound()) {
			rootobj->m_physicsController->AddCompoundChild(m_physicsController.get());
		}
	}
	// graphically, the object hasn't change place, no need to update m_graphicController
}

void KX_GameObject::RemoveParent()
{
	if (!m_sgNode->GetParent()) {
		return;
	}

	// get the root object to remove us from compound object if needed
	KX_GameObject *rootobj = (KX_GameObject *)m_sgNode->GetRootSGParent()->GetClientObject();
	// Set us to the right spot
	m_sgNode->SetLocalScale(m_sgNode->GetWorldScaling());
	m_sgNode->SetLocalOrientation(m_sgNode->GetWorldOrientation());
	m_sgNode->SetLocalPosition(m_sgNode->GetWorldPosition());

	// Remove us from our parent
	m_sgNode->DisconnectFromParent();
	NodeUpdate();

	KX_Scene *scene = GetScene();
	// the object is now a root object, add it to the parentlist
	EXP_ListValue<KX_GameObject> *rootlist = scene->GetRootParentList();
	if (!rootlist->SearchValue(this)) {
		// object was not in root list, add it now and increment ref count
		rootlist->Add(CM_AddRef(this));
	}
	if (m_physicsController) {
		// in case this controller was added as a child shape to the parent
		if (rootobj &&
		    rootobj->m_physicsController &&
		    rootobj->m_physicsController->IsCompound()) {
			rootobj->m_physicsController->RemoveCompoundChild(m_physicsController.get());
		}
		m_physicsController->RestoreDynamics();
		if (m_physicsController->IsDynamic() && (rootobj && rootobj->m_physicsController)) {
			// dynamic object should remember the velocity they had while being parented
			const mt::vec3 childPoint = m_sgNode->GetWorldPosition();
			const mt::vec3 rootPoint = rootobj->m_sgNode->GetWorldPosition();
			const mt::vec3 relPoint = (childPoint - rootPoint);
			const mt::vec3 linVel = rootobj->m_physicsController->GetVelocity(relPoint);
			const mt::vec3 angVel = rootobj->m_physicsController->GetAngularVelocity();
			m_physicsController->SetLinearVelocity(linVel, false);
			m_physicsController->SetAngularVelocity(angVel, false);
		}
	}
	// graphically, the object hasn't change place, no need to update m_graphicController
}

BL_ActionManager *KX_GameObject::GetActionManager()
{
	// We only want to create an action manager if we need it
	if (!m_actionManager) {
		m_actionManager.reset(new BL_ActionManager(this));
	}
	return m_actionManager.get();
}

bool KX_GameObject::PlayAction(const std::string& name,
                               float start,
                               float end,
                               short layer,
                               short priority,
                               float blendin,
                               short play_mode,
                               float layer_weight,
                               short ipo_flags,
                               float playback_speed,
                               short blend_mode)
{
	BL_ActionManager *actionManager = GetActionManager();
	if (!actionManager->PlayAction(name, start, end, layer, priority, blendin, play_mode, layer_weight, ipo_flags, playback_speed, blend_mode)) {
		return false;
	}

	// A finished action removes ordinary objects from the scene's update list. Register again only
	// after PlayAction actually started a layer, so queries and failed action names stay idle.
	GetScene()->AddAnimatedObject(this);
	return true;
}

void KX_GameObject::StopAction(short layer)
{
	GetActionManager()->StopAction(layer);
}

bool KX_GameObject::IsActionDone(short layer)
{
	return GetActionManager()->IsActionDone(layer);
}

bool KX_GameObject::HasActiveActions()
{
	return m_actionManager && m_actionManager->HasActiveActions();
}

bool KX_GameObject::IsActionsSuspended()
{
	return GetActionManager()->IsSuspended();
}

void KX_GameObject::UpdateActionManager(float curtime, bool applyToObject)
{
	GetActionManager()->Update(curtime, applyToObject);
}

float KX_GameObject::GetActionFrame(short layer)
{
	return GetActionManager()->GetActionFrame(layer);
}

const std::string KX_GameObject::GetActionName(short layer)
{
	return GetActionManager()->GetActionName(layer);
}

void KX_GameObject::SetActionLayerWeight(short layer, float layer_weight)
{
	GetActionManager()->SetActionLayerWeight(layer, layer_weight);
}

void KX_GameObject::ApplyGPUParticleParams(RAS_ParticleBuffer *buffer, const RangeGPUParticleSettings &settings)
{
	buffer->SetGravity(settings.gravity);
	buffer->SetLifetime(settings.lifetime);
	buffer->SetEmitterPos(settings.emitter_position);
	buffer->SetEmitterRadius(settings.emitter_radius);
	buffer->SetVelocityBase(settings.velocity);
	buffer->SetVelocityRandomness(settings.velocity_randomness);
	buffer->SetBillboardSize(settings.size);
	buffer->SetColor(settings.color);
	buffer->SetEndColor(settings.end_color);
	buffer->SetEndSize(settings.end_size);
	buffer->SetEmissionDirection(settings.emission_direction);
	buffer->SetEmissionAngle(settings.emission_angle);
	buffer->SetDebugUI(settings.use_debug_ui != 0);
	buffer->SetBlendMode(settings.blend_mode);
	buffer->SetBillboardMode(settings.billboard_mode);
	buffer->SetBackfaceCulling(settings.use_backface_culling != 0);
	buffer->SetEnabled(settings.disable_emission == 0);
	buffer->SetCollisionMode(settings.collision_mode);
	buffer->SetCollisionHeight(settings.collision_height);
	buffer->SetCollisionBounce(settings.collision_bounce);
	buffer->SetCollisionFriction(settings.collision_friction);
	buffer->SetUseVortex(settings.use_vortex != 0);
	buffer->SetVortexRotationSpeed(settings.vortex_rotation_speed);
	buffer->SetVortexRadiusTop(settings.vortex_radius_top);
	buffer->SetVortexHeight(settings.vortex_height);
	buffer->SetBurstMode(settings.emission_mode == GPU_PARTICLE_EMISSION_BURST);
	buffer->SetBurstInterval(settings.burst_interval);
	buffer->SetDrag(settings.drag);
	/* 0 cycles only makes sense with a random start (still variant per sprite): otherwise play once. */
	const float cycles = (settings.flipbook_cycles > 0.0f || settings.flipbook_random) ? settings.flipbook_cycles : 1.0f;
	buffer->SetFlipbook(settings.flipbook_cols, settings.flipbook_rows, cycles, settings.flipbook_random != 0);
}

void KX_GameObject::ApplyGPUParticlesLive(const RangeGPUParticleSettings &oldSettings, const RangeGPUParticleSettings &settings, bool mix)
{
	std::unique_ptr<RAS_ParticleBuffer> &bufferSlot = mix ? m_particleBufferMix : m_particleBuffer;
	if (!bufferSlot) {
		return;
	}

	const bool rebuild = oldSettings.particle_count != settings.particle_count ||
	                     oldSettings.emit_from != settings.emit_from ||
	                     oldSettings.particle_look != settings.particle_look ||
	                     oldSettings.use_custom_frag_shader != settings.use_custom_frag_shader ||
	                     oldSettings.use_size_curve != settings.use_size_curve ||
	                     oldSettings.use_color_curve != settings.use_color_curve ||
	                     strcmp(oldSettings.texture_path, settings.texture_path) != 0 ||
	                     strcmp(oldSettings.frag_shader_path, settings.frag_shader_path) != 0;
	if (rebuild) {
		SetupGPUParticlesBuffer(bufferSlot, settings);
	}
	else {
		ApplyGPUParticleParams(bufferSlot.get(), settings);
	}
}

void KX_GameObject::SetupGPUParticlesBuffer(std::unique_ptr<RAS_ParticleBuffer> &bufferSlot, const RangeGPUParticleSettings &settings)
{
	bufferSlot.reset(new RAS_ParticleBuffer(settings.particle_count > 0 ? settings.particle_count : 1));
	if (!bufferSlot->Create()) {
		CM_Error("KX_GameObject::SetupGPUParticles: RAS_ParticleBuffer::Create() failed, particle emitter disabled for object \"" << m_name << "\"");
		bufferSlot.reset();
		return;
	}

	ApplyGPUParticleParams(bufferSlot.get(), settings);

	// One static particle per vertex of the object's own mesh (base mesh, modifiers not applied),
	// in local space -- UpdateParticles feeds the world transform every frame.
	if (settings.emit_from == GPU_PARTICLE_EMIT_VERTICES) {
		Object *blenderobj = GetBlenderObject();
		Mesh *me = (blenderobj && blenderobj->type == OB_MESH) ? (Mesh *)blenderobj->data : nullptr;
		if (me && me->mvert && me->totvert > 0) {
			std::vector<float> positions(me->totvert * 3);
			for (int i = 0; i < me->totvert; ++i) {
				positions[i * 3 + 0] = me->mvert[i].co[0];
				positions[i * 3 + 1] = me->mvert[i].co[1];
				positions[i * 3 + 2] = me->mvert[i].co[2];
			}
			bufferSlot->SetStaticPositions(positions);
			const mt::mat4 model = mt::mat4::FromAffineTransform(NodeGetWorldTransform());
			bufferSlot->SetModelMatrix((const float *)model.Data());
		}
		else {
			CM_Warning("GPU particles on object \"" << m_name << "\": Emit From Mesh Vertices needs a mesh object with vertices, using Emitter Volume");
		}
	}

	if (settings.use_custom_frag_shader && settings.frag_shader_path[0] != '\0') {
		if (!bufferSlot->LoadFragShaderFromPath(settings.frag_shader_path)) {
			CM_Error("KX_GameObject::SetupGPUParticles: custom fragment shader failed to load/compile for object \"" << m_name << "\", using default look (see log above)");
		}
	}

	// Fase Q: built-in look, baked into the engine -- takes priority over the file-based custom
	// shader above if both are somehow set, since it's the one exposed by the Mix panel.
	if (settings.particle_look != GPU_PARTICLE_LOOK_DEFAULT) {
		bufferSlot->SetCustomFragShader(RAS_GetBuiltinParticleLookSource(settings.particle_look));
	}
	// Smoke and fire should already be burning when the scene starts.
	bufferSlot->SetPrewarm(settings.particle_look == GPU_PARTICLE_LOOK_SMOKE ||
	                       settings.particle_look == GPU_PARTICLE_LOOK_FIRE);
	if (settings.emission_mode == GPU_PARTICLE_EMISSION_BURST && (settings.burst_flags & GPU_PARTICLE_BURST_ON_START)) {
		bufferSlot->Burst();
	}

	if (settings.texture_path[0] != '\0') {
		bufferSlot->LoadTextureFromPath(settings.texture_path);
	}

	if (settings.use_size_curve && settings.size_curve) {
		bufferSlot->BakeSizeCurve(settings.size_curve);
	} else {
		bufferSlot->ClearSizeCurve();
	}
	if (settings.use_color_curve && settings.color_curve) {
		bufferSlot->BakeColorCurve(settings.color_curve);
	} else {
		bufferSlot->ClearColorCurve();
	}
}

void KX_GameObject::SetupGPUParticles(const RangeGPUParticleSettings &settings)
{
	SetupGPUParticlesBuffer(m_particleBuffer, settings);
}

void KX_GameObject::SetupGPUParticlesMix(const RangeGPUParticleSettings &settings)
{
	SetupGPUParticlesBuffer(m_particleBufferMix, settings);
}

void KX_GameObject::UpdateParticles(float deltaTime)
{
	if ((m_particleBuffer && m_particleBuffer->IsStatic()) || (m_particleBufferMix && m_particleBufferMix->IsStatic())) {
		const mt::mat4 model = mt::mat4::FromAffineTransform(NodeGetWorldTransform());
		if (m_particleBuffer && m_particleBuffer->IsStatic()) {
			m_particleBuffer->SetModelMatrix((const float *)model.Data());
		}
		if (m_particleBufferMix && m_particleBufferMix->IsStatic()) {
			m_particleBufferMix->SetModelMatrix((const float *)model.Data());
		}
	}
	if (m_particleBuffer) {
		const bool enabled = (GetPropertyNumber("GPU_Particles_Enabled", 1.0f) != 0.0f);
		m_particleBuffer->SetEnabled(enabled);
		if (m_collisionGroundObject) {
			m_particleBuffer->SetCollisionHeight(m_collisionGroundObject->NodeGetWorldPosition().z);
		}
		m_particleBuffer->Update(deltaTime, NodeGetWorldPosition());
	}
	if (m_particleBufferMix) {
		const bool enabled = (GetPropertyNumber("GPU_Particles_Enabled", 1.0f) != 0.0f);
		m_particleBufferMix->SetEnabled(enabled);
		m_particleBufferMix->Update(deltaTime, NodeGetWorldPosition());
	}
}

RAS_ParticleBuffer *KX_GameObject::GetParticleBuffer() const
{
	return m_particleBuffer.get();
}

RAS_ParticleBuffer *KX_GameObject::GetParticleBufferMix() const
{
	return m_particleBufferMix.get();
}

bool KX_GameObject::HasStaticParticles() const
{
	return (m_particleBuffer && m_particleBuffer->IsStatic()) || (m_particleBufferMix && m_particleBufferMix->IsStatic());
}

void KX_GameObject::SetActionLayerSpeed(short layer, float speed)
{
	GetActionManager()->SetActionLayerSpeed(layer, speed);
}

void KX_GameObject::SetActionFrame(short layer, float frame)
{
	GetActionManager()->SetActionFrame(layer, frame);
}

std::string KX_GameObject::GetCurrentActionName(short layer)
{
	return GetActionManager()->GetCurrentActionName(layer);
}

BL_ActionData *KX_GameObject::GetCurrentActionData(short layer)
{
	return GetActionManager()->GetCurrentActionData(layer);
}

void KX_GameObject::SetPlayMode(short layer, short mode)
{
	GetActionManager()->SetPlayMode(layer, mode);
}

static void setGraphicController_recursive(SG_Node *node)
{
	const NodeList& children = node->GetChildren();

	for (SG_Node *childnode : children) {
		KX_GameObject *clientgameobj = static_cast<KX_GameObject *>(childnode->GetClientObject());
		if (clientgameobj != nullptr) { // This is a GameObject
			clientgameobj->ActivateGraphicController(false);
		}

		// if the childobj is nullptr then this may be an inverse parent link
		// so a non recursive search should still look down this node.
		setGraphicController_recursive(childnode);
	}
}


void KX_GameObject::ActivateGraphicController(bool recurse)
{
	if (m_graphicController) {
		m_graphicController->Activate(m_bVisible || m_bOccluder);
	}
	if (recurse) {
		setGraphicController_recursive(m_sgNode.get());
	}
}

void KX_GameObject::SetCollisionGroup(unsigned short group)
{
	if (m_physicsController) {
		m_physicsController->SetCollisionGroup(group);
		m_physicsController->RefreshCollisions();
	}
}
void KX_GameObject::SetCollisionMask(unsigned short mask)
{
	if (m_physicsController) {
		m_physicsController->SetCollisionMask(mask);
		m_physicsController->RefreshCollisions();
	}
}

unsigned short KX_GameObject::GetCollisionGroup() const
{
	return m_physicsController ? m_physicsController->GetCollisionGroup() : 0;
}
unsigned short KX_GameObject::GetCollisionMask() const
{
	return m_physicsController ? m_physicsController->GetCollisionMask() : 0;
}

EXP_Value *KX_GameObject::GetReplica()
{
	KX_GameObject *replica = new KX_GameObject(*this);

	// this will copy properties and so on...
	replica->ProcessReplica();

	return replica;
}

void KX_GameObject::RemoveRessources(const BL_Resource::Library& libraryId)
{
	// If the object is using actions, try remove actions from this library.
	if (m_actionManager) {
		m_actionManager->RemoveActions(libraryId);
	}

	for (KX_Mesh *mesh : m_meshes) {
		// If the mesh comes from this lirbary, remove all meshes.
		// RemoveMeshes() clears m_meshes, so return right away instead of continuing the loop.
		if (mesh->Belong(libraryId)) {
			RemoveMeshes();
			return;
		}
		// If one of the material used by the mesh comes from this library, remove all meshes too.
		for (RAS_MeshMaterial *meshmat : mesh->GetMeshMaterialList()) {
			if (static_cast<KX_BlenderMaterial *>(meshmat->GetBucket()->GetMaterial())->Belong(libraryId)) {
				RemoveMeshes();
				return;
			}
		}
	}
}

bool KX_GameObject::IsDynamic() const
{
	if (m_physicsController) {
		return m_physicsController->IsDynamic();
	}
	return false;
}

bool KX_GameObject::IsDynamicsSuspended() const
{
	if (m_physicsController) {
		return m_physicsController->IsDynamicsSuspended();
	}
	return false;
}

float KX_GameObject::GetLinearDamping() const
{
	if (m_physicsController) {
		return m_physicsController->GetLinearDamping();
	}
	return 0.0f;
}

float KX_GameObject::GetAngularDamping() const
{
	if (m_physicsController) {
		return m_physicsController->GetAngularDamping();
	}
	return 0.0f;
}

void KX_GameObject::SetLinearDamping(float damping)
{
	if (m_physicsController) {
		m_physicsController->SetLinearDamping(damping);
	}
}


void KX_GameObject::SetAngularDamping(float damping)
{
	if (m_physicsController) {
		m_physicsController->SetAngularDamping(damping);
	}
}

void KX_GameObject::SetDamping(float linear, float angular)
{
	if (m_physicsController) {
		m_physicsController->SetDamping(linear, angular);
	}
}


void KX_GameObject::setCcdMotionThreshold(float motion_threshold)
{
	if (m_physicsController)
		m_physicsController->SetCcdMotionThreshold(motion_threshold);
}

void KX_GameObject::setCcdSweptSphereRadius(float swept_sphere_radius)
{
	if (m_physicsController)
		m_physicsController->SetCcdSweptSphereRadius(swept_sphere_radius);
}






void KX_GameObject::SetSoftLinStiff(float lin_stiff)
{	// Sets linear stiffness for soft body.
	if (m_physicsController)
		m_physicsController->SetSoftLinStiff(lin_stiff);
}

void KX_GameObject::SetSoftAngStiff(float ang_stiff)
{	// Sets angular stiffness for soft body.
	if (m_physicsController)
		m_physicsController->SetSoftAngStiff(ang_stiff);
}

void KX_GameObject::SetSoftVolume(float volume)
{	// Sets volume for soft body.
	if (m_physicsController)
		m_physicsController->SetSoftVolume(volume);
}

void KX_GameObject::SetSoftVsRigidHardness(float hardness)
{	// sets soft vs rigid hardness
	if (m_physicsController)
		m_physicsController->SetSoftVsRigidHardness(hardness);
}

void KX_GameObject::SetSoftVsKineticHardness(float hardness)
{	// sets soft vs kinetic hardness
	if (m_physicsController)
		m_physicsController->SetSoftVsKineticHardness(hardness);
}

void KX_GameObject::SetSoftVsSoftHardness(float hardness)
{
    // sets soft vs soft hardness
    if (m_physicsController)
        m_physicsController->SetSoftVsSoftHardness(hardness);
}

void KX_GameObject::SetSoftVsRigidImpulseSplitCluster(float val)
{
    // sets soft vs rigid impulse split cluster
    if (m_physicsController)
        m_physicsController->SetSoftVsRigidImpulseSplitCluster(val);
}

void KX_GameObject::SetSoftVsKineticImpulseSplitCluster(float val)
{
    // sets soft vs kinetic impulse split cluster
    if (m_physicsController)
        m_physicsController->SetSoftVsKineticImpulseSplitCluster(val);
}

void KX_GameObject::SetSoftVsSoftImpulseSplitCluster(float val)
{
    // sets soft vs soft impulse split cluster
    if (m_physicsController)
        m_physicsController->SetSoftVsSoftImpulseSplitCluster(val);
}

void KX_GameObject::SetVelocitiesCorrectionFactor(float val)
{
    // sets velocities correction factor
    if (m_physicsController)
        m_physicsController->SetVelocitiesCorrectionFactor(val);
}

void KX_GameObject::SetDampingCoefficient(float val)
{
    // sets damping coefficient
    if (m_physicsController)
        m_physicsController->SetDampingCoefficient(val);
}

void KX_GameObject::SetDragCoefficient(float val)
{
    // sets drag coefficient
    if (m_physicsController)
        m_physicsController->SetDragCoefficient(val);
}

void KX_GameObject::SetLiftCoefficient(float val)
{
    // sets lift coefficient
    if (m_physicsController)
        m_physicsController->SetLiftCoefficient(val);
}

void KX_GameObject::SetPressureCoefficient(float val)
{
    // sets pressure coefficient
    if (m_physicsController)
        m_physicsController->SetPressureCoefficient(val);
}

void KX_GameObject::SetVolumeConversationCoefficient(float val)
{
    // sets volume conversation coefficient
    if (m_physicsController)
        m_physicsController->SetVolumeConversationCoefficient(val);
}

void KX_GameObject::SetDynamicFrictionCoefficient(float val)
{
    // sets dynamic friction coefficient
    if (m_physicsController)
        m_physicsController->SetDynamicFrictionCoefficient(val);
}

void KX_GameObject::SetPoseMatchingCoefficient(float val)
{
    // sets pose matching coefficient
    if (m_physicsController)
        m_physicsController->SetPoseMatchingCoefficient(val);
}

void KX_GameObject::SetRigidContactsHardness(float val)
{
    // sets rigid contacts hardness
    if (m_physicsController)
        m_physicsController->SetRigidContactsHardness(val);
}

void KX_GameObject::SetKineticContactsHardness(float val)
{
    // sets kinetic contacts hardness
    if (m_physicsController)
        m_physicsController->SetKineticContactsHardness(val);
}

void KX_GameObject::SetSoftContactsHardness(float val)
{
    // sets soft contacts hardness
    if (m_physicsController)
        m_physicsController->SetSoftContactsHardness(val);
}

void KX_GameObject::SetAnchorsHardness(float val)
{
    // sets anchors hardness
    if (m_physicsController)
        m_physicsController->SetAnchorsHardness(val);
}



void KX_GameObject::SetVelocitySolverIterations(int iterations)
{
    // sets velocity solver iterations
    if (m_physicsController)
        m_physicsController->SetVelocitySolverIterations(iterations);
}

void KX_GameObject::SetPositionSolverIterations(int iterations)
{
    // sets position solver iterations
    if (m_physicsController)
        m_physicsController->SetPositionSolverIterations(iterations);
}

void KX_GameObject::SetDriftSolverIterations(int iterations)
{
    // sets drift solver iterations
    if (m_physicsController)
        m_physicsController->SetDriftSolverIterations(iterations);
}

void KX_GameObject::SetClusterSolverIterations(int iterations)
{
    // sets cluster solver iterations
    if (m_physicsController)
        m_physicsController->SetClusterSolverIterations(iterations);
}


void KX_GameObject::SetSoftPoseMatching(bool enableShapeMatching)
{
    // Shape matching enabled: disable pose update, relative pose.
    if (m_physicsController)
        m_physicsController->SetSoftPoseMatching(enableShapeMatching);
}






void KX_GameObject::ApplyForce(const mt::vec3& force, bool local)
{
	if (m_physicsController) {
		m_physicsController->ApplyForce(force, local);
	}
}

void KX_GameObject::ApplyTorque(const mt::vec3& torque, bool local)
{
	if (m_physicsController) {
		m_physicsController->ApplyTorque(torque, local);
	}
}

void KX_GameObject::ApplyMovement(const mt::vec3& dloc, bool local)
{
	if (m_physicsController) { // (IsDynamic())
		m_physicsController->RelativeTranslate(dloc, local);
	}
	m_sgNode->RelativeTranslate(dloc, m_sgNode->GetParent(), local);
	NodeUpdate();
}

void KX_GameObject::ApplyRotation(const mt::vec3& drot, bool local)
{
	mt::mat3 rotmat(drot);

	m_sgNode->RelativeRotate(rotmat, local);

	if (m_physicsController) { // (IsDynamic())
		m_physicsController->RelativeRotate(rotmat, local);
	}
	NodeUpdate();
}

void KX_GameObject::UpdateBlenderObjectMatrix(Object *blendobj)
{
	if (!blendobj) {
		blendobj = m_convertInfo->m_blenderObject;
	}
	if (blendobj) {
		const mt::mat3x4 trans = NodeGetWorldTransform();
		trans.PackFromAffineTransform(blendobj->obmat);
	}
}

void KX_GameObject::AddMeshUser()
{
	for (size_t i = 0; i < m_meshes.size(); ++i) {
		RAS_Deformer *deformer = BL_ConvertDeformer(this, m_meshes[i]);
		if (!deformer && m_wantsImpostorAtlasDeformer) {
			// Give this instance's billboard quad a private display array so its UVs
			// can be rewritten per-frame to pick an atlas cell (see UpdateLod) without
			// affecting other instances sharing the same KX_Mesh.
			deformer = new KX_ImpostorAtlasDeformer(m_meshes[i], GetScene()->GetBoundingBoxManager());
		}
		else if (!deformer && m_wantsDentDeformer) {
			deformer = new KX_DentDeformer(m_meshes[i], GetScene()->GetBoundingBoxManager());
		}
		m_meshUser = m_meshes[i]->AddMeshUser(&m_clientInfo, deformer);

		m_meshUser->SetMatrix(mt::mat4::FromAffineTransform(NodeGetWorldTransform()));
		m_meshUser->SetFrontFace(!IsNegativeScaling());
	}
}

KX_DentDeformer *KX_GameObject::GetDentDeformer(bool create)
{
	RAS_Deformer *deformer = GetDeformer();
	if (deformer || !create || m_wantsDentDeformer || !m_meshUser || m_meshes.empty()) {
		return m_wantsDentDeformer ? dynamic_cast<KX_DentDeformer *>(deformer) : nullptr;
	}

	// Same as ReplaceMesh() with the current mesh, the new mesh user owns a private copy.
	m_wantsDentDeformer = true;
	delete m_meshUser;
	m_meshUser = nullptr;
	AddMeshUser();
	UpdateBounds(true);

	return dynamic_cast<KX_DentDeformer *>(GetDeformer());
}

void KX_GameObject::DuplicateBitmapTextMeshes()
{
	for (KX_Mesh *&mesh : m_meshes) {
		if (mesh->HasBitmapText()) {
			mesh = mesh->Duplicate();
			m_bitmapTextMeshes.push_back(mesh);
		}
	}
}

const std::vector<KX_Mesh *>& KX_GameObject::GetBitmapTextMeshes() const
{
	return m_bitmapTextMeshes;
}

void KX_GameObject::UpdateBuckets()
{
	// Update datas and add mesh slot to be rendered only if the object is not culled.
	if (m_sgNode->IsDirty(SG_Node::DIRTY_RENDER)) {
		m_meshUser->SetMatrix(mt::mat4::FromAffineTransform(NodeGetWorldTransform()));
		m_meshUser->SetFrontFace(!IsNegativeScaling());
		m_sgNode->ClearDirty(SG_Node::DIRTY_RENDER);
	}

	for (KX_Mesh *mesh : m_meshes) {
		if (mesh->HasBitmapText()) {
			// 2.4x bitmap text shows the "Text" property.
			EXP_Value *prop = GetProperty("Text");
			mesh->UpdateBitmapText(prop ? prop->GetText() : std::string());
		}
	}

	m_meshUser->SetPassIndex(m_passIndex);
	m_meshUser->SetLayer(m_layer);
	m_meshUser->SetColor(m_objectColor);
	m_meshUser->ActivateMeshSlots();
}

void KX_GameObject::ReplaceMesh(KX_Mesh *mesh, bool use_gfx, bool use_phys)
{
	// Same single mesh already assigned and no physics rebuild requested: nothing changes.
	if (use_gfx && !use_phys && mesh && m_meshes.size() == 1 && m_meshes[0] == mesh && m_meshUser) {
		return;
	}

	if (use_gfx && mesh) {
		RemoveMeshes();
		AddMesh(mesh);
		AddMeshUser();
		// The new deformer starts in bind pose (T-pose) until the next animation pass, and LOD switches run
		// after that pass, right before drawing: apply the current pose now so the swap frame is not undeformed.
		if (RAS_Deformer *deformer = GetDeformer()) {
			deformer->Update();
		}
	}

	// Update the new assigned mesh with the physics mesh.
	if (use_phys) {
		if (m_physicsController) {
			// dupli: replicas share the shape info, give this object its own so siblings keep their collision.
			m_physicsController->ReinstancePhysicsShape(nullptr, use_gfx ? nullptr : mesh, true);
		}
	}
	// Always make sure that the bounding box is updated to the new mesh.
	UpdateBounds(true);
}


void KX_GameObject::RemoveMeshes()
{
	// Remove all mesh slots.
	if (m_meshUser) {
		KX_BatchGroup *batchGroup = static_cast<KX_BatchGroup *>(m_meshUser->GetBatchGroup());
		if (batchGroup) {
			batchGroup->RemoveObject(this);
		}
		delete m_meshUser;
		m_meshUser = nullptr;
	}

	//note: meshes can be shared, and are deleted by BL_SceneConverter

	m_meshes.clear();
}

const std::vector<KX_Mesh *>& KX_GameObject::GetMeshList() const
{
	return m_meshes;
}

RAS_MeshUser *KX_GameObject::GetMeshUser() const
{
	return m_meshUser;
}

bool KX_GameObject::Renderable(int layer) const
{
	return (m_meshUser != nullptr) && m_bVisible && (layer == 0 || m_layer & layer);
}

void KX_GameObject::SetLodManager(KX_LodManager *lodManager)
{
	if (lodManager == m_lodManager) {
		return;
	}

	// Reset lod level to avoid overflow index in KX_LodManager::GetLevel.
	m_currentLodLevel = 0;

	// Restore object original mesh.
	if (!lodManager && m_lodManager && m_lodManager->GetLevelCount() > 0) {
		KX_Mesh *origmesh = m_lodManager->GetLevel(0).GetMesh();
		ReplaceMesh(origmesh, true, false);
	}

	if (m_lodManager) {
		m_lodManager->Release();
	}

	m_lodManager = lodManager;

	if (m_lodManager) {
		m_lodManager->AddRef();
	}
}

KX_LodManager *KX_GameObject::GetLodManager() const
{
	return m_lodManager;
}

void KX_GameObject::ShowLodLevel(int level)
{
	if (!m_lodManager || m_lodManager->GetLevelCount() == 0) {
		return;
	}
	const unsigned int index = std::min((unsigned int)level, m_lodManager->GetLevelCount() - 1);
	const KX_LodLevel& lodLevel = m_lodManager->GetLevel(index);
	KX_Mesh *mesh = lodLevel.GetMesh();
	if ((lodLevel.GetFlag() & KX_LodLevel::USE_INVISIBLE) || !mesh || mesh == m_meshes.front()) {
		return;
	}
	m_wantsImpostorAtlasDeformer = (lodLevel.GetFlag() & KX_LodLevel::USE_ATLAS) != 0;
	ReplaceMesh(mesh, true, false);
	m_currentAtlasCell = -1;
}

void KX_GameObject::UpdateLod(KX_Scene *scene, const mt::vec3& cam_pos, float lodfactor)
{
	if (!m_lodManager) {
		return;
	}

	/* Deformed mesh (skinning, ragdoll): the object origin stays with its parent (the car) while the
	 * bones take the body away. The auto-updated bounds follow the deformed vertices, so measure from
	 * their center. Static objects keep the origin, which their LOD distances were tuned on. */
	const mt::vec3 lodPos = m_lodManager->HasDistanceOrigin() ? m_lodManager->GetDistanceOrigin() :
	                        (m_autoUpdateBounds && GetDeformer()) ?
	                        NodeGetWorldTransform() * m_cullingNode.GetAabb().GetCenter() : NodeGetWorldPosition();
	const float distance2 = (lodPos - cam_pos).LengthSquared() * (lodfactor * lodfactor);
	const KX_LodLevel& lodLevel = m_lodManager->GetLevel(scene, m_currentLodLevel, distance2);

	if (lodLevel.GetFlag() & KX_LodLevel::USE_INVISIBLE) {
		m_bVisibleLOD = false;
	}
	else {
		// Update mesh
		KX_Mesh *mesh = lodLevel.GetMesh();
		if (mesh != m_meshes.front()) {
			m_wantsImpostorAtlasDeformer = (lodLevel.GetFlag() & KX_LodLevel::USE_ATLAS) != 0;
			this->ReplaceMesh(mesh, true, (m_lodManager->GetUpdatePhysics() ? true : false));
			// The new mesh (and, if USE_ATLAS, its private atlas deformer) is unrelated to
			// whatever cell was selected for the previous LOD level's mesh.
			m_currentAtlasCell = -1;
		}

		if (!(lodLevel.GetFlag() & KX_LodLevel::USE_BILLBOARD) && m_lodBillboardActive) {
			this->NodeSetLocalOrientation(m_lodBillboardOrientation);
			// LODs update right before render, after the scene graph pass: refresh the
			// world matrix now or the real mesh draws one frame with the billboard turn.
			this->NodeUpdate();
			m_lodBillboardActive = false;
		}

		if (lodLevel.GetFlag() & KX_LodLevel::USE_BILLBOARD) {
			if (!m_lodBillboardActive) {
				m_lodBillboardOrientation = this->NodeGetLocalOrientation();
				m_lodBillboardActive = true;
			}
			// Cylindrical billboard: rotate only around Z so the local +Y (forward)
			// axis faces the camera, keeping the object upright (tree/foliage impostor).
			// Set in world space: a rotated parent (e.g. an imported model's root empty)
			// would otherwise turn the quad away from the camera and mirror the atlas.
			mt::vec3 toCam = cam_pos - this->NodeGetWorldPosition();
			toCam[2] = 0.0f;
			const float lenSq = toCam.LengthSquared();
			if (lenSq > 1e-8f) {
				toCam /= sqrtf(lenSq);
				const float heading = atan2f(-toCam[0], toCam[1]);
				const float ch = cosf(heading);
				const float sh = sinf(heading);
				mt::mat3 rot;
				rot(0, 0) = ch;    rot(0, 1) = -sh;   rot(0, 2) = 0.0f;
				rot(1, 0) = sh;    rot(1, 1) = ch;    rot(1, 2) = 0.0f;
				rot(2, 0) = 0.0f;  rot(2, 1) = 0.0f;  rot(2, 2) = 1.0f;
				// Skip the scene graph update when the world turn is already right:
				// rewriting it every frame adds float noise that splits batches.
				const mt::mat3& cur = this->NodeGetWorldOrientation();
				bool same = true;
				for (unsigned short i = 0; i < 3 && same; ++i) {
					for (unsigned short j = 0; j < 3; ++j) {
						if (fabsf(cur(i, j) - rot(i, j)) > 1e-5f) {
							same = false;
							break;
						}
					}
				}
				if (!same) {
					this->NodeSetGlobalOrientation(rot);
					this->NodeUpdate();
				}

				if (lodLevel.GetFlag() & KX_LodLevel::USE_ATLAS) {
					const int cols = lodLevel.GetAtlasColumns();
					const int rows = lodLevel.GetAtlasRows();
					const int cellCount = cols * rows;
					if (cellCount > 0) {
						float normalized = heading / (2.0f * 3.14159265358979323846f);
						if (normalized < 0.0f) {
							normalized += 1.0f;
						}
						// Cell i was baked exactly at heading i / cellCount: round to the nearest
						// view instead of flooring, which ran up to a whole cell ahead.
						const int cellIndex = int(normalized * cellCount + 0.5f) % cellCount;
						if (cellIndex != m_currentAtlasCell) {
							KX_ImpostorAtlasDeformer *atlasDeformer =
								static_cast<KX_ImpostorAtlasDeformer *>(m_meshUser->GetDeformer());
							if (atlasDeformer) {
								atlasDeformer->SetAtlasCell(cellIndex % cols, cellIndex / cols, cols, rows);
								m_currentAtlasCell = cellIndex;
							}
						}
					}
				}
			}
		}
	}

	m_currentLodLevel = lodLevel.GetLevel();
}

void KX_GameObject::SetAnimationEventManager(KX_AnimationEventManager *AnimationEventManager)
{
	if (m_animationEventManager) {
		m_animationEventManager->Release();
	}

	m_animationEventManager = AnimationEventManager;

	if (m_animationEventManager) {
		m_animationEventManager->AddRef();
	}
}

KX_AnimationEventManager *KX_GameObject::GetAnimationEventManager() const
{
	return m_animationEventManager;
}

void KX_GameObject::ReParentLogic()
{
	SCA_IObject::ReParentLogic();

	// The replicated sensors still point to the events of the original object.
	for (SCA_ISensor *sensor : GetSensors()) {
		SCA_AnimationEventSensor *eventSensor = dynamic_cast<SCA_AnimationEventSensor *>(sensor);
		if (eventSensor) {
			eventSensor->SetEvent(m_animationEventManager ?
			                      m_animationEventManager->GetEvent(eventSensor->GetEventIndex()) : nullptr);
		}
	}
}

void KX_GameObject::UpdateActivity(float distance)
{
	// Manage logic/physics culling.
	KX_Scene *scene = GetScene();
	m_distance = distance;

	const bool hasLogic = (m_activityCullingInfo.m_flags & ActivityCullingInfo::ACTIVITY_LOGIC) != 0;
	const bool hasPhysics = (m_activityCullingInfo.m_flags & ActivityCullingInfo::ACTIVITY_PHYSICS) != 0;

	if (!hasLogic && !hasPhysics) {
		return;
	}

	// Culled as soon as any active check (logic or physics) says the object is out of range,
	// so enabling both at once on the same object works instead of physics being ignored.
	const bool logicOutOfRange = hasLogic && (distance > m_activityCullingInfo.m_logicRadius);
	const bool physicsOutOfRange = hasPhysics && (distance > m_activityCullingInfo.m_physicsRadius);
	const bool shouldCull = logicOutOfRange || physicsOutOfRange;

	if (shouldCull) {
		if (!m_bRender) {
			return;
		}
		SuspendLogic();
		if (hasLogic && m_actionManager) {
			m_actionManager->Suspend();
		}
		if (hasPhysics) {
			SuspendPhysics(false);
		}
		m_bRender = false;
		m_cullingNode.SetCulled(true);
		if (m_bVisible) {
			if (scene->GetRenderList()->RemoveValue(this)) {
				Release();
			}
		}
	}
	else {
		if (m_bRender) {
			return;
		}
		ResumeLogic();
		if (hasLogic && m_actionManager) {
			m_actionManager->Resume();
		}
		if (hasPhysics) {
			RestorePhysics();
		}
		m_bRender = true;
		if (m_bVisible) {
			scene->GetRenderList()->Add(CM_AddRef(this));
		}
	}
}

void KX_GameObject::UpdateTransform()
{
	CM_WorkCount(CM_WORK_TRANSFORM_SYNCS);
	if (CM_WorkAuditGet()) {
		CM_WorkAuditCount(false, GetName());
	}
	// HACK: saves function call for dynamic object, they are handled differently
	if (m_physicsController && !m_physicsController->IsDynamic()) {
		m_physicsController->SetTransform();
	}
	if (m_graphicController) {
		// update the culling tree
		m_graphicController->SetGraphicTransform();
	}

}

void KX_GameObject::UpdateTransformFunc(SG_Node *node, void *gameobj, void *scene)
{
	((KX_GameObject *)gameobj)->UpdateTransform();
}

void KX_GameObject::SynchronizeTransform()
{
	// only used for sensor object, do full synchronization as bullet doesn't do it
	if (m_physicsController) {
		m_physicsController->SetTransform();
	}
	if (m_graphicController) {
		m_graphicController->SetGraphicTransform();
	}
}

void KX_GameObject::SynchronizeTransformFunc(SG_Node *node, void *gameobj, void *scene)
{
	((KX_GameObject *)gameobj)->SynchronizeTransform();
}

bool KX_GameObject::GetVisible(void)
{
	return m_bVisible;
}


bool KX_GameObject::GetDoAnimations(void)
{
	// so we can half objects animations.
	if (!m_bDoAnimations) {
		m_bDoAnimations = true;
	}
	else if (m_halfAnimations) {
		m_bDoAnimations = false;
	}
	return m_bDoAnimations;
}

void KX_GameObject::SetHalfAnimations(bool a)
{
	m_halfAnimations = a;
}


bool KX_GameObject::GetVisibleLOD(void)
{
	return m_bVisibleLOD;
}

void KX_GameObject::UpdateVisibleLOD(KX_Camera *cam)
{
	if (!m_lodManager) {
		return;
	}

	const KX_LodLevel& lodLevel = m_lodManager->GetLevel(m_currentLodLevel);

	if (!(lodLevel.GetFlag() & KX_LodLevel::USE_INVISIBLE)) {
		// reset LOD visible update.
		m_bVisibleLOD = true;
		return;
	}

	// Update LoD
	const mt::vec3& cam_pos = cam->NodeGetWorldPosition();
	const float lodfactor = cam->GetLodDistanceFactor();
	this->UpdateLod(GetScene(), cam_pos, lodfactor);
}

static void setVisible_recursive(SG_Node *node, bool v)
{
	const NodeList& children = node->GetChildren();

	for (SG_Node *childnode : children) {
		KX_GameObject *clientgameobj = static_cast<KX_GameObject *>(childnode->GetClientObject());
		if (clientgameobj != nullptr) { // This is a GameObject
			clientgameobj->SetVisible(v, 0);
		}

		// if the childobj is nullptr then this may be an inverse parent link
		// so a non recursive search should still look down this node.
		setVisible_recursive(childnode, v);
	}
}


void KX_GameObject::SetVisible(bool v,
                               bool recursive)
{
	m_bVisible = v;
	if (m_graphicController) {
		m_graphicController->Activate(m_bVisible || m_bOccluder);
	}
	if (recursive) {
		setVisible_recursive(m_sgNode.get(), v);
	}
}

static void setOccluder_recursive(SG_Node *node, bool v)
{
	const NodeList& children = node->GetChildren();

	for (SG_Node *childnode : children) {
		KX_GameObject *clientgameobj = static_cast<KX_GameObject *>(childnode->GetClientObject());
		if (clientgameobj != nullptr) { // This is a GameObject
			clientgameobj->SetOccluder(v, false);
		}

		// if the childobj is nullptr then this may be an inverse parent link
		// so a non recursive search should still look down this node.
		setOccluder_recursive(childnode, v);
	}
}

void KX_GameObject::SetOccluder(bool v,
                                bool recursive)
{
	m_bOccluder = v;
	if (m_graphicController) {
		m_graphicController->Activate(m_bVisible || m_bOccluder);
	}
	if (recursive) {
		setOccluder_recursive(m_sgNode.get(), v);
	}
}

static void setDebug_recursive(KX_Scene *scene, SG_Node *node, bool debug)
{
	const NodeList& children = node->GetChildren();

	for (SG_Node *childnode : children) {
		KX_GameObject *clientgameobj = static_cast<KX_GameObject *>(childnode->GetClientObject());
		if (clientgameobj != nullptr) {
			if (debug) {
				if (!scene->ObjectInDebugList(clientgameobj)) {
					scene->AddObjectDebugProperties(clientgameobj);
				}
			}
			else {
				scene->RemoveObjectDebugProperties(clientgameobj);
			}
		}

		/* if the childobj is nullptr then this may be an inverse parent link
		 * so a non recursive search should still look down this node. */
		setDebug_recursive(scene, childnode, debug);
	}
}

void KX_GameObject::SetUseDebugProperties(bool debug, bool recursive)
{
	KX_Scene *scene = GetScene();

	if (debug) {
		if (!scene->ObjectInDebugList(this)) {
			scene->AddObjectDebugProperties(this);
		}
	}
	else {
		scene->RemoveObjectDebugProperties(this);
	}

	if (recursive) {
		setDebug_recursive(scene, m_sgNode.get(), debug);
	}
}

void KX_GameObject::SetLayer(int l)
{
	m_layer = l;
}

int KX_GameObject::GetLayer(void)
{
	return m_layer;
}

void KX_GameObject::SetPassIndex(short index)
{
	m_passIndex = index;
}

short KX_GameObject::GetPassIndex() const
{
	return m_passIndex;
}

void KX_GameObject::AddLinearVelocity(const mt::vec3& lin_vel, bool local)
{
	if (m_physicsController) {
		const mt::vec3 lv = local ? NodeGetWorldOrientation() * lin_vel : lin_vel;
		m_physicsController->SetLinearVelocity(lv + m_physicsController->GetLinearVelocity(), 0);
	}
}

void KX_GameObject::SetLinearVelocity(const mt::vec3& lin_vel, bool local)
{
	if (m_physicsController) {
		m_physicsController->SetLinearVelocity(lin_vel, local);
	}
}

void KX_GameObject::SetAngularVelocity(const mt::vec3& ang_vel, bool local)
{
	if (m_physicsController) {
		m_physicsController->SetAngularVelocity(ang_vel, local);
	}
}

void KX_GameObject::SetObjectColor(const mt::vec4& rgbavec)
{
	m_objectColor = rgbavec;
}

const mt::vec4& KX_GameObject::GetObjectColor()
{
	return m_objectColor;
}

void KX_GameObject::AlignAxisToVect(const mt::vec3& dir, int axis, float fac)
{
	mt::mat3 orimat;
	mt::vec3 vect, ori, z, x, y;
	float len;

	vect = dir;
	len = vect.Length();
	if (mt::FuzzyZero(len)) {
		CM_FunctionError("null vector!");
		return;
	}

	if (fac <= 0.0f) {
		return;
	}

	// normalize
	vect /= len;
	orimat = NodeGetWorldOrientation();
	switch (axis) {
		case 0: // align x axis of new coord system to vect
		{ori = orimat.GetColumn(2);    // pivot axis
		 if (mt::FuzzyZero(1.0f - std::abs(mt::dot(vect, ori)))) {     // vect parallel to pivot?
			 ori = orimat.GetColumn(1);    // change the pivot!
		 }

		 if (fac == 1.0f) {
			 x = vect;
		 }
		 else {
			 x = (vect * fac) + ((orimat *mt::axisX3)*(1.0f - fac));
			 len = x.Length();
			 if (mt::FuzzyZero(len)) {
				 x = vect;
			 }
			 else {
				 x /= len;
			 }
		 }
		 y = mt::cross(ori, x);
		 z = mt::cross(x, y);
		 break;}
		case 1: // y axis
		{ori = orimat.GetColumn(0);
		 if (mt::FuzzyZero(1.0f - std::abs(mt::dot(vect, ori)))) {
			 ori = orimat.GetColumn(2);
		 }

		 if (fac == 1.0f) {
			 y = vect;
		 }
		 else {
			 y = (vect * fac) + ((orimat *mt::axisY3)*(1.0f - fac));
			 len = y.Length();
			 if (mt::FuzzyZero(len)) {
				 y = vect;
			 }
			 else {
				 y /= len;
			 }
		 }
		 z = mt::cross(ori, y);
		 x = mt::cross(y, z);
		 break;}
		case 2: // z axis
		{ori = orimat.GetColumn(1);
		 if (mt::FuzzyZero(1.0f - std::abs(mt::dot(vect, ori)))) {
			 ori = orimat.GetColumn(0);
		 }

		 if (fac == 1.0f) {
			 z = vect;
		 }
		 else {
			 z = (vect * fac) + ((orimat *mt::axisZ3)*(1.0f - fac));
			 len = z.Length();
			 if (mt::FuzzyZero(len)) {
				 z = vect;
			 }
			 else {
				 z /= len;
			 }
		 }
		 x = mt::cross(ori, z);
		 y = mt::cross(z, x);
		 break;}
		default: // invalid axis specified
			CM_FunctionWarning("invalid axis '" << axis << "'");
			return;
	}
	x.Normalize(); // normalize the new base vectors
	y.Normalize();
	z.Normalize();
	orimat = mt::mat3(x, y, z);

	if (m_sgNode->GetParent() != nullptr) {
		// the object is a child, adapt its local orientation so that
		// the global orientation is aligned as we want (cancelling out the parent orientation)
		mt::mat3 invori = m_sgNode->GetParent()->GetWorldOrientation().Inverse();
		NodeSetLocalOrientation(invori * orimat);
	}
	else {
		NodeSetLocalOrientation(orimat);
	}
}

float KX_GameObject::GetMass()
{
	if (m_physicsController) {
		return m_physicsController->GetMass();
	}
	return 0.0f;
}

mt::vec3 KX_GameObject::GetLocalInertia()
{
	mt::vec3 local_inertia = mt::zero3;
	if (m_physicsController) {
		local_inertia = m_physicsController->GetLocalInertia();
	}
	return local_inertia;
}

mt::vec3 KX_GameObject::GetLinearVelocity(bool local)
{
	mt::vec3 velocity = mt::zero3, locvel;
	mt::mat3 ori;
	if (m_physicsController) {
		velocity = m_physicsController->GetLinearVelocity();

		if (local) {
			ori = NodeGetWorldOrientation();

			locvel = velocity * ori;
			return locvel;
		}
	}
	return velocity;
}

mt::vec3 KX_GameObject::GetAngularVelocity(bool local)
{
	mt::vec3 velocity = mt::zero3, locvel;
	mt::mat3 ori;
	if (m_physicsController) {
		velocity = m_physicsController->GetAngularVelocity();

		if (local) {
			ori = NodeGetWorldOrientation();

			locvel = velocity * ori;
			return locvel;
		}
	}
	return velocity;
}

mt::vec3 KX_GameObject::GetGravity() const
{
	if (!m_physicsController) {
		return mt::zero3;
	}

	return m_physicsController->GetGravity();
}

void KX_GameObject::SetGravity(const mt::vec3 &gravity)
{
	if (m_physicsController) {
		m_physicsController->SetGravity(gravity);
	}
}

mt::vec3 KX_GameObject::GetVelocity(const mt::vec3& point)
{
	if (m_physicsController) {
		return m_physicsController->GetVelocity(point);
	}
	return mt::zero3;
}

void KX_GameObject::NodeSetLocalPosition(const mt::vec3& trans)
{
	if (m_physicsController && !m_sgNode->GetParent()) {
		// don't update physic controller if the object is a child:
		// 1) the transformation will not be right
		// 2) in this case, the physic controller is necessarily a static object
		//    that is updated from the normal kinematic synchronization
		m_physicsController->SetPosition(trans);
	}

	m_sgNode->SetLocalPosition(trans);
}

void KX_GameObject::NodeSetLocalOrientation(const mt::mat3& rot)
{
	if (m_physicsController && !m_sgNode->GetParent()) {
		// see note above
		m_physicsController->SetOrientation(rot);
	}
	m_sgNode->SetLocalOrientation(rot);
}

void KX_GameObject::NodeSetGlobalOrientation(const mt::mat3& rot)
{
	SG_Node *parentSgNode = m_sgNode->GetParent();
	if (parentSgNode) {
		NodeSetLocalOrientation(parentSgNode->GetWorldOrientation().Inverse() * rot);
	}
	else {
		NodeSetLocalOrientation(rot);
	}
}

void KX_GameObject::NodeSetLocalScale(const mt::vec3& scale)
{
	if (m_physicsController && !m_sgNode->GetParent()) {
		m_physicsController->SetScaling(scale);
	}
	m_sgNode->SetLocalScale(scale);
}

void KX_GameObject::NodeSetRelativeScale(const mt::vec3& scale)
{
	m_sgNode->RelativeScale(scale);
	if (m_physicsController && (!m_sgNode->GetParent())) {
		// see note above
		// we can use the local scale: it's the same thing for a root object
		// and the world scale is not yet updated
		const mt::vec3& newscale = NodeGetLocalScaling();
		m_physicsController->SetScaling(newscale);
	}
}

void KX_GameObject::NodeSetWorldScale(const mt::vec3& scale)
{
	SG_Node *parent = m_sgNode->GetParent();
	if (parent) {
		// Make sure the objects have some scale
		mt::vec3 p_scale = parent->GetWorldScaling();
		if (mt::FuzzyZero(p_scale[0]) || mt::FuzzyZero(p_scale[1]) || mt::FuzzyZero(p_scale[2])) {
			return;
		}

		p_scale[0] = 1.0f / p_scale[0];
		p_scale[1] = 1.0f / p_scale[1];
		p_scale[2] = 1.0f / p_scale[2];

		NodeSetLocalScale(scale * p_scale);
	}
	else {
		NodeSetLocalScale(scale);
	}
}

void KX_GameObject::NodeSetWorldPosition(const mt::vec3& trans)
{
	SG_Node *parent = m_sgNode->GetParent();
	if (parent != nullptr) {
		// Make sure the objects have some scale
		mt::vec3 scale = parent->GetWorldScaling();
		if (mt::FuzzyZero(scale[0]) || mt::FuzzyZero(scale[1]) || mt::FuzzyZero(scale[2])) {
			return;
		}

		scale[0] = 1.0f / scale[0];
		scale[1] = 1.0f / scale[1];
		scale[2] = 1.0f / scale[2];

		const mt::mat3 invori = parent->GetWorldOrientation().Inverse();
		const mt::vec3 newpos = invori * (trans - parent->GetWorldPosition()) * scale;
		NodeSetLocalPosition(newpos);
	}
	else {
		NodeSetLocalPosition(trans);
	}
}

void KX_GameObject::NodeUpdate()
{
	m_sgNode->UpdateWorldData();
}

const mt::mat3& KX_GameObject::NodeGetWorldOrientation() const
{
	return m_sgNode->GetWorldOrientation();
}

const mt::mat3& KX_GameObject::NodeGetLocalOrientation() const
{
	return m_sgNode->GetLocalOrientation();
}

const mt::vec3& KX_GameObject::NodeGetWorldScaling() const
{
	return m_sgNode->GetWorldScaling();
}

const mt::vec3& KX_GameObject::NodeGetLocalScaling() const
{
	return m_sgNode->GetLocalScale();
}

const mt::vec3& KX_GameObject::NodeGetWorldPosition() const
{
	return m_sgNode->GetWorldPosition();
}

const mt::vec3& KX_GameObject::NodeGetLocalPosition() const
{
	return m_sgNode->GetLocalPosition();
}

mt::mat3x4 KX_GameObject::NodeGetWorldTransform() const
{
	return m_sgNode->GetWorldTransform();
}

mt::mat3x4 KX_GameObject::NodeGetLocalTransform() const
{
	return m_sgNode->GetLocalTransform();
}

Object *KX_GameObject::GetBlenderObject() const
{
	// Non converted objects has default camera doesn't have convert info.
	return (m_convertInfo) ? m_convertInfo->m_blenderObject : nullptr;
}

unsigned int KX_GameObject::GetNetId() const
{
	return m_netId;
}

void KX_GameObject::SetNetId(unsigned int netId)
{
	m_netId = netId;
}

BL_ConvertObjectInfo *KX_GameObject::GetConvertObjectInfo() const
{
	return m_convertInfo;
}

void KX_GameObject::SetConvertObjectInfo(BL_ConvertObjectInfo *info)
{
	m_convertInfo = info;
}

void KX_GameObject::SetNode(SG_Node *node)
{
	m_sgNode.reset(node);
}

void KX_GameObject::UpdateBounds(bool force)
{
	if ((!m_autoUpdateBounds && !force) || !m_meshUser) {
		return;
	}

	RAS_BoundingBox *boundingBox = m_meshUser->GetBoundingBox();
	if (!boundingBox || (!boundingBox->GetModified() && !force)) {
		return;
	}

	RAS_Deformer *deformer = GetDeformer();
	if (deformer) {
		/** Update all the deformer, not only per material.
		 * One of the side effect is to clear some flags about AABB calculation.
		 * like in KX_SoftBodyDeformer.
		 */
		deformer->UpdateBuckets();
	}

	// AABB Box : min/max.
	mt::vec3 aabbMin;
	mt::vec3 aabbMax;

	boundingBox->GetAabb(aabbMin, aabbMax);

	SetBoundsAabb(aabbMin, aabbMax);
}

void KX_GameObject::SetBoundsAabb(const mt::vec3 &aabbMin, const mt::vec3 &aabbMax)
{
	CM_WorkCount(CM_WORK_BOUNDS_PUSHES);
	// Set the AABB in culling node box.
	m_cullingNode.GetAabb().Set(aabbMin, aabbMax);

	// Synchronize the AABB with the graphic controller.
	if (m_graphicController) {
		m_graphicController->SetLocalAabb(aabbMin, aabbMax);
	}
}

void KX_GameObject::GetBoundsAabb(mt::vec3 &aabbMin, mt::vec3 &aabbMax) const
{
	// Get the culling node box AABB
	m_cullingNode.GetAabb().Get(aabbMin, aabbMax);
}

SG_CullingNode& KX_GameObject::GetCullingNode()
{
	return m_cullingNode;
}

KX_GameObject::ActivityCullingInfo& KX_GameObject::GetActivityCullingInfo()
{
	return m_activityCullingInfo;
}

void KX_GameObject::SetActivityCullingInfo(const ActivityCullingInfo& cullingInfo)
{
	m_activityCullingInfo = cullingInfo;
}

void KX_GameObject::SetActivityCulling(ActivityCullingInfo::Flag flag, bool enable)
{
	if (enable) {
		m_activityCullingInfo.m_flags = (ActivityCullingInfo::Flag)(m_activityCullingInfo.m_flags | flag);
		KX_Scene *scene = GetScene();
		scene->AddCullingObject(this);
	}
	else {
		m_activityCullingInfo.m_flags = (ActivityCullingInfo::Flag)(m_activityCullingInfo.m_flags & ~flag);

		// Restore physics or logic when disabling activity culling.
		if (flag & ActivityCullingInfo::ACTIVITY_PHYSICS) {
			RestorePhysics();
		}
		if (flag & ActivityCullingInfo::ACTIVITY_LOGIC) {
			ResumeLogic();
			if (m_actionManager) {
				m_actionManager->Resume();
			}
		}

		// Only stop tracking the object when no activity flag is left: the other flag
		// still needs UpdateActivity() to run on it.
		const ActivityCullingInfo::Flag activityFlags = (ActivityCullingInfo::Flag)(ActivityCullingInfo::ACTIVITY_PHYSICS | ActivityCullingInfo::ACTIVITY_LOGIC);
		if (!(m_activityCullingInfo.m_flags & activityFlags)) {
			KX_Scene *scene = GetScene();
			scene->RemoveCullingObject(this);

			// The object may have been culled while it was tracked; nothing else restores it now.
			if (!m_bRender) {
				// Physics culling suspends logic too, even without ACTIVITY_LOGIC.
				ResumeLogic();
				m_bRender = true;
				m_cullingNode.SetCulled(false);
				if (m_bVisible) {
					scene->GetRenderList()->Add(CM_AddRef(this));
				}
			}
		}
	}
}

void KX_GameObject::SuspendPhysics(bool freeConstraints)
{
	if (m_physicsController) {
		m_physicsController->SuspendPhysics((bool)freeConstraints);
	}
}

void KX_GameObject::RestorePhysics()
{
	if (m_physicsController) {
		m_physicsController->RestorePhysics();
	}
}

void KX_GameObject::SuspendAnimations()
{
	// Don't lazily create an action manager (and register in m_animatedlist via
	// GetActionManager()) just to suspend it -- if it never played an action, there's
	// nothing to suspend and nothing being iterated in KX_Scene::UpdateAnimations either.
	if (m_actionManager) {
		m_actionManager->Suspend();
	}
}

void KX_GameObject::ResumeAnimations()
{
	if (m_actionManager) {
		m_actionManager->Resume();
	}
}

void KX_GameObject::UnregisterCollisionCallbacks()
{
	if (!m_physicsController) {
		CM_Warning("trying to unregister collision callbacks for object without collisions: " << GetName());
		return;
	}

	// Unregister from callbacks
	KX_Scene *scene = GetScene();
	PHY_IPhysicsEnvironment *pe = scene->GetPhysicsEnvironment();
	PHY_IPhysicsController *spc = m_physicsController.get();
	// If we are the last to unregister on this physics controller
	if (pe->RemoveCollisionCallback(spc)) {
		// If we are a sensor object
		if (m_clientInfo.isSensor()) {
			// Remove sensor body from physics world
			pe->RemoveSensor(spc);
		}
	}
}

void KX_GameObject::RegisterCollisionCallbacks()
{
	if (!m_physicsController) {
		CM_Warning("trying to register collision callbacks for object without collisions: " << GetName());
		return;
	}

	// Register from callbacks
	KX_Scene *scene = GetScene();
	PHY_IPhysicsEnvironment *pe = scene->GetPhysicsEnvironment();
	PHY_IPhysicsController *spc = m_physicsController.get();
	// If we are the first to register on this physics controller
	if (pe->RequestCollisionCallback(spc)) {
		// If we are a sensor object
		if (m_clientInfo.isSensor()) {
			// Add sensor body to physics world
			pe->AddSensor(spc);
		}
	}
}
void KX_GameObject::RunCollisionCallbacks(KX_GameObject *collider, KX_CollisionContactPointList& contactPointList)
{
#ifdef WITH_PYTHON
	if (!m_collisionCallbacks || PyList_GET_SIZE(m_collisionCallbacks) == 0) {
		return;
	}

	const PHY_ICollData *collData = contactPointList.GetCollData();
	const bool isFirstObject = contactPointList.GetFirstObject();

	PyObject *args[] = {collider->GetProxy(),
		                PyObjectFrom(collData->GetWorldPoint(0, isFirstObject)),
		                PyObjectFrom(collData->GetNormal(0, isFirstObject)),
		                contactPointList.GetProxy()};
	EXP_RunPythonCallBackList(m_collisionCallbacks, args, 1, ARRAY_SIZE(args));

	for (unsigned int i = 0; i < ARRAY_SIZE(args); ++i) {
		Py_DECREF(args[i]);
	}

	// Invalidate the collison contact point to avoid access to it in next frame
	contactPointList.InvalidateProxy();
#endif
}

void KX_GameObject::RunBreakCallbacks(const std::vector<KX_GameObject *>& fragments)
{
#ifdef WITH_PYTHON
	if (!m_breakCallbacks || PyList_GET_SIZE(m_breakCallbacks) == 0) {
		return;
	}

	PyObject *pyfragments = PyList_New(fragments.size());
	for (unsigned int i = 0, size = fragments.size(); i < size; ++i) {
		PyList_SET_ITEM(pyfragments, i, fragments[i]->GetProxy());
	}

	PyObject *args[] = {GetProxy(), pyfragments};
	EXP_RunPythonCallBackList(m_breakCallbacks, args, 0, ARRAY_SIZE(args));

	for (unsigned int i = 0; i < ARRAY_SIZE(args); ++i) {
		Py_DECREF(args[i]);
	}
#endif
}

void KX_GameObject::RunExplodeCallbacks(const mt::vec3& position)
{
#ifdef WITH_PYTHON
	if (!m_explodeCallbacks || PyList_GET_SIZE(m_explodeCallbacks) == 0) {
		return;
	}

	PyObject *args[] = {GetProxy(), PyObjectFrom(position)};
	EXP_RunPythonCallBackList(m_explodeCallbacks, args, 0, ARRAY_SIZE(args));

	for (unsigned int i = 0; i < ARRAY_SIZE(args); ++i) {
		Py_DECREF(args[i]);
	}
#endif
}

void KX_GameObject::RunDentCallbacks(const mt::vec3& point, float impulse)
{
#ifdef WITH_PYTHON
	if (!m_dentCallbacks || PyList_GET_SIZE(m_dentCallbacks) == 0) {
		return;
	}

	PyObject *args[] = {GetProxy(), PyObjectFrom(point), PyFloat_FromDouble(impulse)};
	EXP_RunPythonCallBackList(m_dentCallbacks, args, 0, ARRAY_SIZE(args));

	for (unsigned int i = 0; i < ARRAY_SIZE(args); ++i) {
		Py_DECREF(args[i]);
	}
#endif
}

template <bool recursive>
static void walk_children(const SG_Node *node, std::vector<KX_GameObject *>& list)
{
	if (!node) {
		return;
	}

	const NodeList& children = node->GetChildren();

	for (SG_Node *childnode : children) {
		KX_GameObject *childobj = static_cast<KX_GameObject *>(childnode->GetClientObject());
		if (childobj) {
			list.push_back(childobj);
		}

		/* If the childobj is nullptr then this may be an inverse parent link
		 * so a non recursive search should still look down this node. */
		if (recursive || !childobj) {
			walk_children<recursive>(childnode, list);
		}
	}
}

static void walk_parent(KX_GameObject *gameobj, std::vector<KX_GameObject *> &list)
{
	KX_GameObject *parent = gameobj->GetParent();

	if (parent) {
		KX_GameObject *parentRecursive = parent->GetParent();
		list.push_back(parent);

		if (parentRecursive) {
			list.push_back(parentRecursive);
			walk_parent(parentRecursive, list);
		}
	}
}

std::vector<KX_GameObject *> KX_GameObject::GetChildren() const
{
	std::vector<KX_GameObject *> list;
	walk_children<false>(m_sgNode.get(), list);
	return list;
}

std::vector<KX_GameObject *> KX_GameObject::GetChildrenRecursive() const
{
	std::vector<KX_GameObject *> list;
	walk_children<true>(m_sgNode.get(), list);
	return list;
}

std::vector<KX_GameObject *> KX_GameObject::GetParentRecursive() const
{
	std::vector<KX_GameObject *> list;
	walk_parent((KX_GameObject *)this, list);
	return list;
}

EXP_ListValue<KX_PythonComponent> *KX_GameObject::GetComponents() const
{
	return m_components;
}

void KX_GameObject::SetComponents(EXP_ListValue<KX_PythonComponent> *components)
{
	m_components = components;
}

void KX_GameObject::UpdateComponents()
{
#ifdef WITH_PYTHON
	if (m_components) {
		/* Activity culling suspends the logic (m_suspended) and clears m_bRender. Components only
		 * follow that suspension when component culling is enabled; any other suspension stops them. */
		const bool cullComponents = (m_activityCullingInfo.m_flags & ActivityCullingInfo::ACTIVITY_LOGIC_COMPONENTS) != 0;
		const bool suspendedByCulling = m_suspended && !m_bRender;
		if (m_suspended && (cullComponents || !suspendedByCulling)) {
			return;
		}
		for (KX_PythonComponent *comp : m_components) {
			if (comp->GetActiveState()) {
				if (CM_TraceOn(CM_TRACE_SCRIPTS)) {
					const std::string name = "component " + comp->GetName();
					CM_TraceScriptScope scope(name);
					comp->Update();
				}
				else {
					comp->Update();
				}
			}
		}
	}

#endif // WITH_PYTHON
}

void KX_GameObject::SetDebugTimeProfiling(int type, float time)
{
	time = KX_GetActiveEngine()->GetTimeSecondClock() - time; // Calculate spend time
	switch (type) {
		case DebugProfilingType::TIME_COMPONENTS:
			m_debugProfilingData.m_time_components = time;
			break;
		case DebugProfilingType::TIME_ANIMATION:
			m_debugProfilingData.m_time_animation = time;
			break;
		default:
			break;
	}

	// Do Render
	if (!m_debugProfilingData.m_render && time > 0.00001f)
		m_debugProfilingData.m_render = true;
}

KX_Scene *KX_GameObject::GetScene()
{
	BLI_assert(m_sgNode);
	return static_cast<KX_Scene *>(m_sgNode->GetClientInfo());
}

/* ---------------------------------------------------------------------
 * Some stuff taken from the header
 * --------------------------------------------------------------------- */
void KX_GameObject::Relink(std::map<SCA_IObject *, SCA_IObject *>& map_parameter)
{
	// we will relink the sensors and actuators that use object references
	// if the object is part of the replicated hierarchy, use the new
	// object reference instead
	SCA_SensorList& sensorlist = GetSensors();
	SCA_SensorList::iterator sit;
	for (sit = sensorlist.begin(); sit != sensorlist.end(); sit++)
	{
		(*sit)->Relink(map_parameter);
	}
	SCA_ActuatorList& actuatorlist = GetActuators();
	SCA_ActuatorList::iterator ait;
	for (ait = actuatorlist.begin(); ait != actuatorlist.end(); ait++)
	{
		(*ait)->Relink(map_parameter);
	}
}

