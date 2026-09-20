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
 * Ketsji scene. Holds references to all scene data.
 */

/** \file gameengine/Ketsji/KX_Scene.cpp
 *  \ingroup ketsji
 */


#ifdef _MSC_VER
#  pragma warning (disable:4786)
#endif

#include <algorithm>
#include <cmath>

#include "KX_Scene.h"
#include "KX_AnimationEvent.h"
#include "KX_AnimationEventManager.h"
#include "KX_Globals.h"
#include "BLI_utildefines.h"
#include "KX_KetsjiEngine.h"
#include "KX_BlenderMaterial.h"
#include "KX_TextMaterial.h"
#include "KX_FontObject.h"
#include "RAS_IMaterial.h"
#include "EXP_ListValue.h"
#include "SCA_LogicManager.h"
#include "SCA_TimeEventManager.h"
#include "SCA_2DFilterActuator.h"
#include "SCA_PythonController.h"
#include "KX_CollisionEventManager.h"
#include "KX_CutsceneManager.h"
#include "SCA_KeyboardManager.h"
#include "SCA_MouseManager.h"
#include "SCA_ActuatorEventManager.h"
#include "SCA_BasicEventManager.h"
#include "KX_Camera.h"
#include "KX_WorldInfo.h"
#include "KX_Speaker.h"
#include "KX_NavMeshObject.h"
#include "SCA_JoystickManager.h"
#include "KX_PyMath.h"
#include "KX_Mesh.h"
#include "SCA_IScene.h"
#include "KX_LodManager.h"
#include "KX_CullingHandler.h"
#include "KX_PythonComponent.h"

#include "RAS_Rasterizer.h"
#include "RAS_ICanvas.h"
#include "RAS_2DFilterData.h"
#include "KX_2DFilterManager.h"
#include "RAS_BoundingBoxManager.h"
#include "RAS_BucketManager.h"
#include "RAS_Deformer.h"

#include "EXP_FloatValue.h"
#include "EXP_IntValue.h"
#include "EXP_StringValue.h"
#include "SCA_IController.h"
#include "SCA_IActuator.h"
#include "SG_Node.h"
#include "SG_Controller.h"
#include "SG_Node.h"
#include "DNA_group_types.h"
#include "DNA_scene_types.h"
#include "DNA_property_types.h"
#include "DNA_world_types.h"

#include "KX_NodeRelationships.h"

#include "KX_NetworkMessageScene.h"
#include "PHY_IPhysicsEnvironment.h"
#include "PHY_IGraphicController.h"
#include "PHY_IPhysicsController.h"
#include "BL_Converter.h"
#include "KX_LibLoadStatus.h"
#include "BL_ArmatureObject.h"
#include "KX_MotionState.h"
#include "KX_ObstacleSimulation.h"

#include "KX_Imgui.h"
#include "KX_DebugMode.h"

#ifdef WITH_PYTHON
#  include "EXP_PythonCallBack.h"
#endif

#include "KX_LightObject.h"

#include "BLI_task.h"
#include "BLI_path_util.h"
#include "BLI_fileops.h"
#include "BLI_string.h"
#ifdef WIN32
#  include "BLI_winstuff.h"
#endif

#include "CM_Message.h"
#include "CM_List.h"

static void *KX_SceneReplicationFunc(SG_Node *node, void *gameobj, void *scene)
{
	KX_GameObject *replica = ((KX_Scene *)scene)->AddNodeReplicaObject(node, (KX_GameObject *)gameobj);

	if (replica) {
		replica->Release();
	}

	return (void *)replica;
}

static void *KX_SceneDestructionFunc(SG_Node *node, void *gameobj, void *scene)
{
	((KX_Scene *)scene)->RemoveNodeDestructObject((KX_GameObject *)gameobj);

	return nullptr;
}

bool KX_Scene::KX_ScenegraphUpdateFunc(SG_Node *node, void *gameobj, void *scene)
{
	return node->Schedule(((KX_Scene *)scene)->m_sghead);
}

bool KX_Scene::KX_ScenegraphRescheduleFunc(SG_Node *node, void *gameobj, void *scene)
{
	return node->Reschedule(((KX_Scene *)scene)->m_sghead);
}

SG_Callbacks KX_Scene::m_callbacks = SG_Callbacks(
	KX_SceneReplicationFunc,
	KX_SceneDestructionFunc,
	KX_GameObject::UpdateTransformFunc,
	KX_Scene::KX_ScenegraphUpdateFunc,
	KX_Scene::KX_ScenegraphRescheduleFunc);

KX_Scene::KX_Scene(SCA_IInputDevice *inputDevice,
                   const std::string& sceneName,
                   Scene *scene,
                   RAS_ICanvas *canvas,
                   KX_NetworkMessageManager *messageManager) :
	m_keyboardmgr(nullptr),
	m_mousemgr(nullptr),
	m_physicsEnvironment(0),
	m_sceneName(sceneName),
	m_worldSun(nullptr),
	m_autoWorldSun(false),
	m_autoWorldSunMissingCameraWarned(false),
	m_autoWorldSunGroundReferenceInitialized(false),
	m_autoWorldSunInitialCameraHeight(0.0f),
	m_autoWorldSunReferenceCamera(nullptr),
	m_earthquakeBaseGravity(mt::zero3),
	m_earthquakeBaseGravityInitialized(false),
	m_activeCamera(nullptr),
	m_optimizationReferencePosition(mt::zero3),
	m_overrideCullingCamera(nullptr),
	m_lastCullingTotalObjects(0),
	m_lastCullingTestedObjects(0),
	m_lastCullingVisibleObjects(0),
	m_lastLightsTotal(0),
	m_lastLightsShadowUpdated(0),
	m_lastShadowPasses(0),
	m_ueberExecutionPriority(0),
	m_suspend(false),
	m_suspendedDelta(0.0),
	m_activityCulling(false),
	m_dbvtCulling(false),
	m_dbvtOcclusionRes(0),
	m_blenderScene(scene),
	m_previousAnimTime(0.0f),
	m_isActivedHysteresis(false),
	m_lodHysteresisValue(0),
	m_audio3d_frames(0),
	m_staticShadowCasterListDirty(false)
{

	m_objectlist = new EXP_ListValue<KX_GameObject>();
	m_parentlist = new EXP_ListValue<KX_GameObject>();
	m_lightlist = new EXP_ListValue<KX_LightObject>();
	m_inactivelist = new EXP_ListValue<KX_GameObject>();
	m_cameralist = new EXP_ListValue<KX_Camera>();
	m_fontlist = new EXP_ListValue<KX_FontObject>();
	m_speakerlist = new EXP_ListValue<KX_Speaker>();
	m_renderlist = new EXP_ListValue<KX_GameObject>();

	SCENEFXSettings settings = scene->scenefx_settings;
	BuildInFilters filters = {
		(scene->scenefx_settings.scenefx_flag & SCENE_FX_FLAG_FXAA) ? true : false,
	};

	if (settings.bloom) {
		filters.useBloom = (scene->scenefx_settings.scenefx_flag & SCENE_FX_FLAG_BLOOM) ? true : false;
		filters.bloom_intensity = settings.bloom->intensity;
		filters.bloom_threshold = settings.bloom->threshold;
	}
	if (settings.tonemap) {
		filters.useTonemap = (scene->scenefx_settings.scenefx_flag & SCENE_FX_FLAG_TONEMAP) ? true : false;
		filters.tonemap_type = settings.tonemap->shadertype;
		filters.tonemap_exposure = settings.tonemap->exposure;
		filters.tonemap_gamma = settings.tonemap->gamma;
	}

	m_useLightScattering = false;
	if (settings.scatter) {
		m_useLightScattering = (scene->scenefx_settings.scenefx_flag & SCENE_FX_FLAG_LIGHTSCATTER) ? true : false;
		filters.useLightScatter = m_useLightScattering;
		filters.scatter_lod = settings.scatter_lod;
		filters.scatter_intensity = settings.scatter->intensity;
		filters.scatter_threshold = settings.scatter->threshold;
		filters.scatter_step_size = settings.scatter->stepsize;
		filters.scatter_step_max = settings.scatter->stepmax;
	}

	if (settings.ssr) {
		filters.useSSR = (scene->scenefx_settings.scenefx_flag & SCENE_FX_FLAG_SSR) ? true : false;
		filters.ssr_lod = settings.ssr_lod;
		filters.ssr_step_max = settings.ssr->step_max;
		filters.ssr_bias = settings.ssr->bias;
		filters.ssr_max_distance = settings.ssr->max_distance;
	}

	if (settings.ssao) {
		filters.useSSAO = (scene->scenefx_settings.scenefx_flag & SCENE_FX_FLAG_SSAO) ? true : false;
		filters.ssao_samples = settings.ssao->samples;
		filters.ssao_strength = settings.ssao->factor;
		filters.ssao_distance = settings.ssao->distance_max;
		filters.ssao_attenuation = settings.ssao->attenuation;
	}

	// Native World weather (Rain/Clouds/Lens Flare), driven by World DNA/RNA settings.
	if (scene->world) {
		World *world = scene->world;

		if (world->weather_flag & WO_WEATHER_RAIN) {
			filters.useRain = true;
			filters.useRainDroplets = (world->weather_flag & WO_WEATHER_RAIN_DROPLETS) ? true : false;
			filters.useRainRipple = (world->weather_flag & WO_WEATHER_RAIN_RIPPLE) ? true : false;
			filters.rain_style = world->rain_style;
			filters.rain_intensity = world->rain_intensity;
			filters.rain_density = world->rain_density;
			filters.rain_speed = world->rain_speed;
			filters.rain_wind = world->rain_wind;
			filters.rain_darken = world->rain_darken;
			filters.rain_ripple = world->rain_ripple;
			filters.rain_ripple_distance = world->rain_ripple_distance;
			filters.rain_ripple_min_up = world->rain_ripple_min_up;
			filters.rain_color[0] = world->rain_color[0];
			filters.rain_color[1] = world->rain_color[1];
			filters.rain_color[2] = world->rain_color[2];
		}

		if (world->weather_flag & WO_WEATHER_CLOUDS) {
			filters.useClouds = true;
			filters.cloud_coverage = world->cloud_coverage;
			filters.cloud_scale = world->cloud_scale;
			filters.cloud_speed = world->cloud_speed;
			filters.cloud_color[0] = world->cloud_color[0];
			filters.cloud_color[1] = world->cloud_color[1];
			filters.cloud_color[2] = world->cloud_color[2];
		}

		if (world->weather_flag & WO_WEATHER_LENSFLARE) {
			filters.useLensFlare = true;
			filters.flare_scale = world->flare_scale;
			filters.flare_intensity = world->flare_intensity;
		}
	}

	m_filterManager = new KX_2DFilterManager(canvas, filters);
	m_logicmgr = new SCA_LogicManager();

	m_timemgr = new SCA_TimeEventManager(m_logicmgr);
	m_keyboardmgr = new SCA_KeyboardManager(m_logicmgr, inputDevice);
	m_mousemgr = new SCA_MouseManager(m_logicmgr, inputDevice);

	SCA_ActuatorEventManager *actmgr = new SCA_ActuatorEventManager(m_logicmgr);
	SCA_BasicEventManager *basicmgr = new SCA_BasicEventManager(m_logicmgr);

	m_logicmgr->RegisterEventManager(actmgr);
	m_logicmgr->RegisterEventManager(m_keyboardmgr);
	m_logicmgr->RegisterEventManager(m_mousemgr);
	m_logicmgr->RegisterEventManager(m_timemgr);
	m_logicmgr->RegisterEventManager(basicmgr);

	SCA_JoystickManager *joymgr = new SCA_JoystickManager(m_logicmgr);
	m_logicmgr->RegisterEventManager(joymgr);

	m_networkScene = new KX_NetworkMessageScene(messageManager);

	m_rendererManager = new KX_TextureRendererManager(this);
	m_bucketmanager = new RAS_BucketManager(KX_TextMaterial::GetSingleton());
	m_boundingBoxManager = new RAS_BoundingBoxManager();

	m_animationPoolData.scene = this;
	m_animationPool = BLI_task_pool_create(KX_GetActiveEngine()->GetTaskScheduler(), &m_animationPoolData);

	m_audio3d_update = scene->audio.audio3d_update;
#ifdef WITH_PYTHON
	m_attrDict = nullptr;
	m_removeCallbacks = nullptr;

	for (unsigned short i = 0; i < MAX_DRAW_CALLBACK; ++i) {
		m_drawCallbacks[i] = nullptr;
	}
#endif
}

KX_Scene::~KX_Scene()
{
	/* The release of debug properties used to be in SCA_IScene::~SCA_IScene
	 * It's still there but we remove all properties here otherwise some
	 * reference might be hanging and causing late release of objects
	 */
	RemoveAllDebugProperties();
	ClearCutsceneSpawnedObjects();
	m_cutsceneManager.reset();

	while (GetRootParentList()->GetCount() > 0) {
		KX_GameObject *parentobj = GetRootParentList()->GetValue(0);
		this->RemoveObject(parentobj);
	}

	if (m_obstacleSimulation) {
		delete m_obstacleSimulation;
	}

	if (m_animationPool) {
		BLI_task_pool_free(m_animationPool);
	}

	if (m_objectlist) {
		m_objectlist->Release();
	}

	if (m_parentlist) {
		m_parentlist->Release();
	}

	if (m_inactivelist) {
		m_inactivelist->Release();
	}

	if (m_lightlist) {
		m_lightlist->Release();
	}

	if (m_cameralist) {
		m_cameralist->Release();
	}

	if (m_fontlist) {
		m_fontlist->Release();
	}

	if (m_speakerlist) {
		m_speakerlist->Release();
	}

	if (m_renderlist) {
		m_renderlist->Release();
	}

	if (m_filterManager) {
		delete m_filterManager;
	}

	if (m_logicmgr) {
		delete m_logicmgr;
	}

	if (m_physicsEnvironment) {
		delete m_physicsEnvironment;
	}

	if (m_networkScene) {
		delete m_networkScene;
	}

	if (m_rendererManager) {
		delete m_rendererManager;
	}

	if (m_bucketmanager) {
		delete m_bucketmanager;
	}

	if (m_boundingBoxManager) {
		delete m_boundingBoxManager;
	}

	if (m_worldinfo) {
		delete m_worldinfo;
	}

#ifdef WITH_PYTHON
	if (m_attrDict) {
		PyDict_Clear(m_attrDict);
		Py_CLEAR(m_attrDict);
	}

	// These may be nullptr but the macro checks.
	Py_CLEAR(m_removeCallbacks);
	for (unsigned short i = 0; i < MAX_DRAW_CALLBACK; ++i) {
		Py_CLEAR(m_drawCallbacks[i]);
	}
#endif
}

std::string KX_Scene::GetName()
{
	return m_sceneName;
}

void KX_Scene::SetName(const std::string& name)
{
	m_sceneName = name;
}

RAS_BucketManager *KX_Scene::GetBucketManager() const
{
	return m_bucketmanager;
}

KX_TextureRendererManager *KX_Scene::GetTextureRendererManager() const
{
	return m_rendererManager;
}

RAS_BoundingBoxManager *KX_Scene::GetBoundingBoxManager() const
{
	return m_boundingBoxManager;
}

EXP_ListValue<KX_GameObject> *KX_Scene::GetObjectList() const
{
	return m_objectlist;
}

EXP_ListValue<KX_GameObject> *KX_Scene::GetRootParentList() const
{
	return m_parentlist;
}

EXP_ListValue<KX_GameObject> *KX_Scene::GetInactiveList() const
{
	return m_inactivelist;
}

EXP_ListValue<KX_LightObject> *KX_Scene::GetLightList() const
{
	return m_lightlist;
}

EXP_ListValue<KX_Camera> *KX_Scene::GetCameraList() const
{
	return m_cameralist;
}

EXP_ListValue<KX_FontObject> *KX_Scene::GetFontList() const
{
	return m_fontlist;
}

EXP_ListValue<KX_Speaker> *KX_Scene::GetSpeakerList() const
{
	return m_speakerlist;
}

EXP_ListValue<KX_GameObject> *KX_Scene::GetRenderList() const
{
	return m_renderlist;
}

SCA_LogicManager *KX_Scene::GetLogicManager() const
{
	return m_logicmgr;
}

SCA_TimeEventManager *KX_Scene::GetTimeEventManager() const
{
	return m_timemgr;
}

KX_PythonComponentManager& KX_Scene::GetPythonComponentManager()
{
	return m_componentManager;
}

void KX_Scene::SetFramingType(const RAS_FrameSettings& frameSettings)
{
	m_frameSettings = frameSettings;
}

const RAS_FrameSettings& KX_Scene::GetFramingType() const
{
	return m_frameSettings;
}

void KX_Scene::SetWorldInfo(KX_WorldInfo *worldinfo)
{
	m_worldinfo = worldinfo;
}

KX_WorldInfo *KX_Scene::GetWorldInfo() const
{
	return m_worldinfo;
}

void KX_Scene::SetWorldSun(KX_LightObject *light)
{
	m_worldSun = light;
	if (!light) {
		m_autoWorldSun = false;
	}
}

KX_LightObject *KX_Scene::GetWorldSun() const
{
	return m_worldSun;
}

void KX_Scene::SetAutoWorldSun(bool enabled)
{
	m_autoWorldSun = enabled;
	m_autoWorldSunMissingCameraWarned = false;
	m_autoWorldSunGroundReferenceInitialized = false;
	m_autoWorldSunReferenceCamera = nullptr;
}

void KX_Scene::UpdateAutoWorldSun()
{
	if (!m_autoWorldSun || !m_worldSun) {
		return;
	}

	KX_Camera *camera = GetActiveCamera();
	if (!camera) {
		if (!m_autoWorldSunMissingCameraWarned) {
			CM_Warning("automatic World Sun in scene \"" << GetName() << "\" has no active camera; keeping its current position.");
			m_autoWorldSunMissingCameraWarned = true;
		}
		return;
	}

	m_autoWorldSunMissingCameraWarned = false;

	const mt::vec3 cameraPosition = camera->NodeGetWorldPosition();
	if (!m_autoWorldSunGroundReferenceInitialized || m_autoWorldSunReferenceCamera != camera) {
		// A camera normally starts at a fixed height above the player ground.
		// Subtracting that first height makes the reference follow terrain/player
		// elevation without needing a ray cast or a separately tagged floor.
		m_autoWorldSunInitialCameraHeight = cameraPosition.z;
		m_autoWorldSunGroundReferenceInitialized = true;
		m_autoWorldSunReferenceCamera = camera;
	}

	// Keep the shadow focus 5 m in front of the player, projected on the ground
	// plane. Camera pitch must not move this focus up into the air.
	mt::vec3 cameraForward = -camera->NodeGetWorldOrientation().GetColumn(2);
	cameraForward.z = 0.0f;
	cameraForward = cameraForward.SafeNormalized(mt::axisY3);
	mt::vec3 groundReference = cameraPosition + cameraForward * 5.0f;
	groundReference.z -= m_autoWorldSunInitialCameraHeight;

	// `sun_hour` is a World World Property, so a Property Actuator set to
	// World Property can change the time of day without a Python script.
	float hour = 12.0f;
	if (m_worldinfo) {
		if (EXP_Value *hourProperty = m_worldinfo->GetProperty("sun_hour")) {
			hour = static_cast<float>(hourProperty->GetNumber());
		}
	}
	hour = std::fmod(hour, 24.0f);
	if (hour < 0.0f) {
		hour += 24.0f;
	}

	// Orbit around the ground reference instead of spinning the Sun in place.
	// Its local -Z is then always aimed at that reference, keeping shadows over
	// the player area at every hour.
	static const float kHourToRadians = 0.2617993877991494f; // pi / 12
	const float sunAngle = (hour - 12.0f) * kHourToRadians;
	const mt::vec3 sunPosition = groundReference + mt::vec3(0.0f, -std::sin(sunAngle) * 10.0f, std::cos(sunAngle) * 10.0f);
	m_worldSun->NodeSetWorldPosition(sunPosition);
	// Blender lamps illuminate along local -Z, so align local +Z away from the
	// ground reference. This leaves local -Z pointing directly at it.
	m_worldSun->AlignAxisToVect(sunPosition - groundReference, 2);
}

void KX_Scene::UpdateEarthquake(double curtime)
{
	World *world = m_blenderScene->world;
	const bool active = world && (world->weather_flag & WO_WEATHER_EARTHQUAKE) && world->earthquake_level > 0;

	if (!m_earthquakeBaseGravityInitialized) {
		m_earthquakeBaseGravity = GetGravity();
		m_earthquakeBaseGravityInitialized = true;
	}

	if (!active) {
		// Only reset if the effect had actually displaced gravity (avoid
		// clobbering gravity changes made by the user/logic while off).
		const mt::vec3 currentGravity = GetGravity();
		if (currentGravity.x != m_earthquakeBaseGravity.x ||
		    currentGravity.y != m_earthquakeBaseGravity.y ||
		    currentGravity.z != m_earthquakeBaseGravity.z)
		{
			SetGravity(m_earthquakeBaseGravity);
		}
		return;
	}

	// Same two-wave-per-axis shake as the reference implementation: a single
	// sine looks too mechanical/repetitive, two summed at different phases
	// and frequencies read as more chaotic ground motion.
	static const float kLevelStrength[6] = {0.0f, 0.8f, 1.8f, 3.5f, 5.8f, 8.5f};
	static const float kLevelFrequency[6] = {0.0f, 3.0f, 4.0f, 5.5f, 7.0f, 8.5f};

	const int level = std::min(std::max(world->earthquake_level, 0), 5);
	const float strength = kLevelStrength[level];
	const float frequency = kLevelFrequency[level];
	const float t = (float)curtime;

	const float gx = strength * (std::sin(t * frequency * 6.28318f) +
	                              0.45f * std::sin(t * frequency * 11.7f));
	const float gy = strength * (std::sin(t * frequency * 8.1f + 1.4f) +
	                              0.35f * std::sin(t * frequency * 15.9f));
	const float gz = m_earthquakeBaseGravity.z + strength * 0.12f * std::sin(t * frequency * 10.4f);

	SetGravity(mt::vec3(m_earthquakeBaseGravity.x + gx, m_earthquakeBaseGravity.y + gy, gz));
}

void KX_Scene::Suspend()
{
	m_suspend = true;
}

void KX_Scene::Resume()
{
	m_suspend = false;
}

void KX_Scene::SetActivityCulling(bool b)
{
	m_activityCulling = b;
}

bool KX_Scene::IsSuspended() const
{
	return m_suspend;
}

void KX_Scene::SetDbvtCulling(bool b)
{
	m_dbvtCulling = b;
}

bool KX_Scene::GetDbvtCulling() const
{
	return m_dbvtCulling;
}

void KX_Scene::SetDbvtOcclusionRes(int i)
{
	m_dbvtOcclusionRes = i;
}

int KX_Scene::GetDbvtOcclusionRes() const
{
	return m_dbvtOcclusionRes;
}

void KX_Scene::AddObjectDebugProperties(KX_GameObject *gameobj)
{
	Object *blenderobject = gameobj->GetBlenderObject();
	if (!blenderobject) {
		return;
	}

	for (bProperty *prop = (bProperty *)blenderobject->prop.first; prop; prop = prop->next) {
		if (prop->flag & PROP_DEBUG) {
			AddDebugProperty(gameobj, prop->name);
		}
	}

	if (blenderobject->scaflag & OB_DEBUGSTATE) {
		AddDebugProperty(gameobj, "__state__");
	}
}

void KX_Scene::RemoveNodeDestructObject(KX_GameObject *gameobj)
{
	if (NewRemoveObject(gameobj)) {
		/* Object is not yet deleted because a reference is hanging somewhere.
		 * This should not happen anymore since we use proxy object for Python. */
		CM_Error("zombie object! name=" << gameobj->GetName());
		BLI_assert(false);
	}
}

KX_GameObject *KX_Scene::AddNodeReplicaObject(SG_Node *node, KX_GameObject *gameobj)
{
	/* For group duplication, limit the duplication of the hierarchy to the
	 * objects that are part of the group. */
	if (!IsObjectInGroup(gameobj)) {
		return nullptr;
	}

	KX_GameObject *newobj = static_cast<KX_GameObject *>(gameobj->GetReplica());
	m_map_gameobject_to_replica[gameobj] = newobj;

	// Also register 'timers' (time properties) of the replica.
	for (unsigned short i = 0, numprops = newobj->GetPropertyCount(); i < numprops; ++i) {
		EXP_Value *prop = newobj->GetProperty(i);

		if (prop->GetProperty("timer")) {
			m_timemgr->AddTimeProperty(prop);
		}
	}

	if (node) {
		newobj->SetNode(node);
	}
	else {
		SG_Node *rootnode = new SG_Node(newobj, this, KX_Scene::m_callbacks);

		// This fixes part of the scaling-added object bug.
		SG_Node *orgnode = gameobj->GetNode();
		rootnode->SetLocalScale(orgnode->GetLocalScale());
		rootnode->SetLocalPosition(orgnode->GetLocalPosition());
		rootnode->SetLocalOrientation(orgnode->GetLocalOrientation());

		// Define the relationship between this node and it's parent.
		KX_NormalParentRelation *parent_relation = new KX_NormalParentRelation();
		rootnode->SetParentRelation(parent_relation);

		newobj->SetNode(rootnode);
	}

	SG_Node *replicanode = newobj->GetNode();

	// Add the object in the obstacle simulation if needed.
	if (m_obstacleSimulation && gameobj->GetBlenderObject()->gameflag & OB_HASOBSTACLE) {
		m_obstacleSimulation->AddObstacleForObj(newobj);
	}
	// Reconstruct nav mesh.
	if (gameobj->GetGameObjectType() == SCA_IObject::OBJ_NAVMESH) {
		static_cast<KX_NavMeshObject *>(gameobj)->BuildNavMesh();
	}

	// Register object for component update.
	if (gameobj->GetComponents()) {
		m_componentManager.RegisterObject(newobj);
	}

	replicanode->SetClientObject(newobj);

	// This is the list of object that are send to the graphics pipeline.
	m_objectlist->Add(CM_AddRef(newobj));

	if (gameobj->GetVisible()) {
		m_renderlist->Add(CM_AddRef(newobj));
	}

	if (gameobj->GetActivityCullingInfo().m_flags != KX_GameObject::ActivityCullingInfo::ACTIVITY_NONE) {
		AddCullingObject(newobj);
	}

	switch (newobj->GetGameObjectType()) {
		case SCA_IObject::OBJ_LIGHT:
		{
			m_lightlist->Add(CM_AddRef(static_cast<KX_LightObject *>(newobj)));
			break;
		}
		case SCA_IObject::OBJ_TEXT:
		{
			m_fontlist->Add(CM_AddRef(static_cast<KX_FontObject *>(newobj)));
			break;
		}
		case SCA_IObject::OBJ_CAMERA:
		{
			m_cameralist->Add(CM_AddRef(static_cast<KX_Camera *>(newobj)));
			break;
		}
		case SCA_IObject::OBJ_ARMATURE:
		{
			AddAnimatedObject(newobj);
			break;
		}
		case SCA_IObject::OBJ_SPEAKER:
		{
			m_speakerlist->Add(CM_AddRef(static_cast<KX_Speaker *>(newobj)));
			break;
		}
	}

	// Fase I.2: replicas don't copy m_particleBuffer (it's not copyable/shareable GL state),
	// so re-derive it from the replicated object's own DNA settings, same as initial conversion.
	Object *newblenderobj = newobj->GetBlenderObject();
	if (newblenderobj && (newblenderobj->gameflag2 & OB_GPU_PARTICLES)) {
		newobj->SetupGPUParticles(newblenderobj->gpu_particles);
		AddGpuParticleObject(newobj);
	}
	if (newblenderobj && (newblenderobj->gameflag2 & OB_GPU_PARTICLE_COLLIDER)) {
		AddGpuParticleColliderObject(newobj);
	}

	// Logic cannot be replicated, until the whole hierarchy is replicated.
	m_logicHierarchicalGameObjects.push_back(newobj);

	// Replicate graphic controller.
	if (gameobj->GetGraphicController()) {
		PHY_IMotionState *motionstate = new KX_MotionState(newobj->GetNode());
		PHY_IGraphicController *newctrl = gameobj->GetGraphicController()->GetReplica(motionstate);
		newctrl->SetNewClientInfo(&newobj->GetClientInfo());
		newobj->SetGraphicController(newctrl);
	}

	// Replicate physics controller.
	if (gameobj->GetPhysicsController()) {
		PHY_IMotionState *motionstate = new KX_MotionState(newobj->GetNode());
		PHY_IPhysicsController *newctrl = gameobj->GetPhysicsController()->GetReplica();

		KX_GameObject *parent = newobj->GetParent();
		PHY_IPhysicsController *parentctrl = (parent) ? parent->GetPhysicsController() : nullptr;

		newctrl->SetNewClientInfo(&newobj->GetClientInfo());
		newobj->SetPhysicsController(newctrl);
		newctrl->PostProcessReplica(motionstate, parentctrl);

		// Child objects must be static.
		if (parent) {
			newctrl->SuspendDynamics();
		}
	}

	return newobj;
}

void KX_Scene::StartInitSpeakers()
{
  // Start Init from KX_Speakers
  for (KX_Speaker *speaker : m_speakerlist) {
    // Don't start speakers on inactive layer.
    if ((speaker->GetLayer() & GetBlenderScene()->lay) != 0) {
      speaker->startInitPlay();
    }
  }
}

/*
 * Before calling this method KX_Scene::ReplicateLogic(), make sure to
 * have called 'GameObject::ReParentLogic' for each object this
 * hierarchy that's because first ALL bricks must exist in the new
 * replica of the hierarchy in order to make cross-links work properly.
 *
 * It is VERY important that the order of sensors and actuators in
 * the replicated object is preserved: it is used to reconnect the logic.
 * This method is more robust then using the bricks name in case of complex
 * group replication. The replication of logic bricks is done in
 * SCA_IObject::ReParentLogic(), make sure it preserves the order of the bricks.
 */
void KX_Scene::ReplicateLogic(KX_GameObject *newobj)
{
	// Add properties to debug list, for added objects and DupliGroups.
	if (KX_GetActiveEngine()->GetFlag(KX_KetsjiEngine::AUTO_ADD_DEBUG_PROPERTIES)) {
		AddObjectDebugProperties(newobj);
	}
	// Also relink the controller to sensors/actuators.
	const SCA_ControllerList controllers = newobj->GetControllers();

	for (SCA_IController *cont : controllers) {
		cont->SetUeberExecutePriority(m_ueberExecutionPriority);
		const SCA_SensorList linkedsensors = cont->GetLinkedSensors();
		const SCA_ActuatorList linkedactuators = cont->GetLinkedActuators();

		/* Disconnect the sensors and actuators
		 * do it directly on the list at this controller is not connected to anything at this stage. */
		cont->GetLinkedSensors().clear();
		cont->GetLinkedActuators().clear();

		// Now relink each sensor.
		for (SCA_ISensor *oldsensor : linkedsensors) {
			SCA_IObject *oldsensorobj = oldsensor->GetParent();
			// The original owner of the sensor has been replicated?
			SCA_IObject *newsensorobj = m_map_gameobject_to_replica[oldsensorobj];

			if (!newsensorobj) {
				// No, then the sensor points outside the hierarchy, keep it the same.
				if (m_objectlist->SearchValue(static_cast<KX_GameObject *>(oldsensorobj))) {
					// Only replicate links that points to active objects.
					m_logicmgr->RegisterToSensor(cont, oldsensor);
				}
			}
			else {
				// Yes, then the new sensor has the same position.
				SCA_SensorList& sensorlist = oldsensorobj->GetSensors();
				SCA_SensorList::iterator sit;
				SCA_ISensor *newsensor = nullptr;
				int sensorpos;

				for (sensorpos = 0, sit = sensorlist.begin(); sit != sensorlist.end(); sit++, sensorpos++) {
					if ((*sit) == oldsensor) {
						newsensor = newsensorobj->GetSensors().at(sensorpos);
						break;
					}
				}

				BLI_assert(newsensor != nullptr);
				m_logicmgr->RegisterToSensor(cont, newsensor);
			}
		}

		// Now relink each actuator.
		for (SCA_IActuator *oldactuator : linkedactuators) {
			SCA_IObject *oldactuatorobj = oldactuator->GetParent();
			SCA_IObject *newactuatorobj = m_map_gameobject_to_replica[oldactuatorobj];

			if (!newactuatorobj) {
				// No, then the sensor points outside the hierarchy, keep it the same.
				if (m_objectlist->SearchValue(static_cast<KX_GameObject *>(oldactuatorobj))) {
					// Only replicate links that points to active objects
					m_logicmgr->RegisterToActuator(cont, oldactuator);
				}
			}
			else {
				// Yes, then the new sensor has the same position
				SCA_ActuatorList& actuatorlist = oldactuatorobj->GetActuators();
				SCA_ActuatorList::iterator ait;
				SCA_IActuator *newactuator = nullptr;
				int actuatorpos;

				for (actuatorpos = 0, ait = actuatorlist.begin(); ait != actuatorlist.end(); ait++, actuatorpos++) {
					if ((*ait) == oldactuator) {
						newactuator = newactuatorobj->GetActuators().at(actuatorpos);
						break;
					}
				}
				BLI_assert(newactuator != nullptr);
				m_logicmgr->RegisterToActuator(cont, newactuator);
				newactuator->SetUeberExecutePriority(m_ueberExecutionPriority);
			}
		}
	}
	// Ready to set initial state.
	newobj->ResetState();
}

void KX_Scene::DupliGroupRecurse(KX_GameObject *groupobj, int level)
{
	Object *blgroupobj = groupobj->GetBlenderObject();
	std::vector<KX_GameObject *> duplilist;

	if (!groupobj->GetNode() || !groupobj->IsDupliGroup() || level > MAX_DUPLI_RECUR) {
		return;
	}

	// We will add one group at a time.
	m_logicHierarchicalGameObjects.clear();
	m_map_gameobject_to_replica.clear();
	m_ueberExecutionPriority++;

	/* For groups will do something special:
	 * we will force the creation of objects to those in the group only
	 * Again, this is match what Blender is doing (it doesn't care of parent relationship)
	 */
	m_groupGameObjects.clear();

	Group *group = blgroupobj->dup_group;
	for (GroupObject *go = (GroupObject *)group->gobject.first; go; go = (GroupObject *)go->next) {
		Object *blenderobj = go->ob;
		if (blgroupobj == blenderobj) {
			// This check is also in group_duplilist().
			continue;
		}

		KX_GameObject *gameobj = (KX_GameObject *)m_logicmgr->FindGameObjByBlendObj(blenderobj);
		if (gameobj == nullptr) {
			/* This object has not been converted.
			 * Should not happen as dupli group are created automatically */
			continue;
		}

		if ((blenderobj->lay & group->layer) == 0) {
			// Object is not visible in the 3D view, will not be instantiated.
			continue;
		}
		m_groupGameObjects.insert(gameobj);
	}

	for (KX_GameObject *gameobj : m_groupGameObjects) {
		KX_GameObject *parent = gameobj->GetParent();
		if (parent != nullptr) {
			/* This object is not a top parent. Either it is the child of another
			 * object in the group and it will be added automatically when the parent
			 * is added. Or it is the child of an object outside the group and the group
			 * is inconsistent, skip it anyway.
			 */
			continue;
		}
		KX_GameObject *replica = AddNodeReplicaObject(nullptr, gameobj);
		// Add to 'rootparent' list (this is the list of top hierarchy objects, updated each frame).
		m_parentlist->Add(CM_AddRef(replica));

		// Recurse replication into children nodes.
		const NodeList& children = gameobj->GetNode()->GetChildren();

		replica->GetNode()->ClearSGChildren();
		for (SG_Node *orgnode : children) {
			SG_Node *childreplicanode = orgnode->GetReplica();
			if (childreplicanode) {
				replica->GetNode()->AddChild(childreplicanode);
			}
		}
		/* Don't replicate logic now: we assume that the objects in the group can have
		 * logic relationship, even outside parent relationship
		 * In order to match 3D view, the position of groupobj is used as a
		 * transformation matrix instead of the new position. This means that
		 * the group reference point is 0,0,0.
		 */

		// Get the rootnode's scale.
		const mt::vec3& newscale = groupobj->NodeGetWorldScaling();
		// Set the replica's relative scale with the rootnode's scale.
		replica->NodeSetRelativeScale(newscale);

		const mt::vec3 offset(group->dupli_ofs);
		const mt::vec3 newpos = groupobj->NodeGetWorldPosition() +
		                        newscale * (groupobj->NodeGetWorldOrientation() * (gameobj->NodeGetWorldPosition() - offset));
		replica->NodeSetLocalPosition(newpos);
		// Set the orientation after position for softbody.
		const mt::mat3 newori = groupobj->NodeGetWorldOrientation() * gameobj->NodeGetWorldOrientation();
		replica->NodeSetLocalOrientation(newori);
		// Update scenegraph for entire tree of children.
		replica->GetNode()->UpdateWorldData();
		// We can now add the graphic controller to the physic engine.
		replica->ActivateGraphicController(true);

		// Done with replica.
		replica->Release();
	}

	// Do the linking of member objects to group object for every objects.
	for (KX_GameObject *gameobj : m_logicHierarchicalGameObjects) {
		/* Set references for dupli-group
		 * groupobj holds a list of all objects, that belongs to this group. */
		groupobj->AddInstanceObjects(gameobj);
		// Every object gets the reference to its dupli-group object.
		gameobj->SetDupliGroupObject(groupobj);
	}

	/* The logic must be replicated first because we need
	 * the new logic bricks before relinking. */
	for (KX_GameObject *gameobj : m_logicHierarchicalGameObjects) {
		gameobj->ReParentLogic();
	}

	// Relink any pointers as necessary, sort of a temporary solution.
	for (KX_GameObject *gameobj : m_logicHierarchicalGameObjects) {
		// This will also relink the actuator to objects within the hierarchy.
		gameobj->Relink(m_map_gameobject_to_replica);
		gameobj->AddMeshUser();
		// Always make sure that the bounding box is valid.
		gameobj->UpdateBounds(true);
		// Add the object in the layer of the parent.
		gameobj->SetLayer(groupobj->GetLayer());
	}

	// Replicate crosslinks etc. between logic bricks.
	for (KX_GameObject *gameobj : m_logicHierarchicalGameObjects) {
		ReplicateLogic(gameobj);
	}

	// Now look if object in the hierarchy have dupli group and recurse.
	for (KX_GameObject *gameobj : m_logicHierarchicalGameObjects) {
		// Replicate all constraints.
		gameobj->ReplicateConstraints(m_physicsEnvironment, m_logicHierarchicalGameObjects);

		if (gameobj != groupobj && gameobj->IsDupliGroup()) {
			// Can't instantiate group immediately as it destroys m_logicHierarchicalGameObjects.
			duplilist.push_back(gameobj);
		}
	}

	for (KX_GameObject *gameobj : duplilist) {
		DupliGroupRecurse(gameobj, level + 1);
	}
}

bool KX_Scene::IsObjectInGroup(KX_GameObject *gameobj) const
{
	return (m_groupGameObjects.empty() || m_groupGameObjects.find(gameobj) != m_groupGameObjects.end());
}

KX_GameObject *KX_Scene::FindInactiveObjectAcrossScenes(const std::string& name)
{
	if (KX_GameObject *ob = m_inactivelist->FindValue(name)) {
		return ob;
	}
	for (KX_Scene *scene : KX_GetActiveEngine()->CurrentScenes()) {
		if (scene == this) {
			continue;
		}
		if (KX_GameObject *ob = scene->GetInactiveList()->FindValue(name)) {
			return ob;
		}
	}
	return nullptr;
}

KX_GameObject *KX_Scene::AddReplicaObject(KX_GameObject *originalobj, KX_GameObject *referenceobj, float lifespan)
{
	m_logicHierarchicalGameObjects.clear();
	m_map_gameobject_to_replica.clear();
	m_groupGameObjects.clear();

	m_ueberExecutionPriority++;

	// Lets create a replica.
	KX_GameObject *replica = AddNodeReplicaObject(nullptr, originalobj);

	/* Add a timebomb to this object
	 * lifespan of zero means 'this object lives forever'. */
	if (lifespan > 0.0f) {
		// For now, convert between so called frames and realtime.
		m_tempObjectList.push_back(replica);
		/* This convert the life from frames to sort-of seconds, hard coded 0.02 that assumes we have 50 frames per second
		 * if you change this value, make sure you change it in KX_GameObject::pyattr_get_life property too. */
		EXP_Value *fval = new EXP_FloatValue(lifespan * 0.02f);
		replica->SetProperty("::timebomb", fval);
		fval->Release();
	}

	// Add to 'rootparent' list (this is the list of top hierarchy objects, updated each frame).
	m_parentlist->Add(CM_AddRef(replica));

	// Recurse replication into children nodes.

	const NodeList& children = originalobj->GetNode()->GetChildren();

	replica->GetNode()->ClearSGChildren();
	for (SG_Node *orgnode : children) {
		SG_Node *childreplicanode = orgnode->GetReplica();
		if (childreplicanode) {
			replica->GetNode()->AddChild(childreplicanode);
		}
	}

	if (referenceobj) {
		/* At this stage all the objects in the hierarchy have been duplicated,
		 * we can update the scenegraph, we need it for the duplication of logic. */
		const mt::vec3& newpos = referenceobj->NodeGetWorldPosition();
		replica->NodeSetLocalPosition(newpos);

		const mt::mat3& newori = referenceobj->NodeGetWorldOrientation();
		replica->NodeSetLocalOrientation(newori);

		// Get the rootnode's scale.
		const mt::vec3& newscale = referenceobj->GetNode()->GetRootSGParent()->GetLocalScale();
		// Set the replica's relative scale with the rootnode's scale.
		replica->NodeSetRelativeScale(newscale);
	}

	replica->GetNode()->UpdateWorldData();
	// The size is correct, we can add the graphic controller to the physic engine.
	replica->ActivateGraphicController(true);

	// Now replicate logic.
	for (KX_GameObject *gameobj : m_logicHierarchicalGameObjects) {
		gameobj->ReParentLogic();
	}

	// Relink any pointers as necessary, sort of a temporary solution.
	for (KX_GameObject *gameobj : m_logicHierarchicalGameObjects) {
		// This will also relink the actuators in the hierarchy.
		gameobj->Relink(m_map_gameobject_to_replica);
		gameobj->AddMeshUser();
		// Always make sure that the bounding box is valid.
		gameobj->UpdateBounds(true);

		if (referenceobj) {
			// Add the object in the layer of the reference object.
			gameobj->SetLayer(referenceobj->GetLayer());
		}
		else {
			// We don't know what layer set, so we set all visible layers in the blender scene.
			gameobj->SetLayer(m_blenderScene->lay);
		}
	}

	// Replicate crosslinks etc. between logic bricks.
	for (KX_GameObject *gameobj : m_logicHierarchicalGameObjects) {
		ReplicateLogic(gameobj);
	}

	// Check if there are objects with dupligroup in the hierarchy.
	std::vector<KX_GameObject *> duplilist;
	for (KX_GameObject *gameobj : m_logicHierarchicalGameObjects) {
		if (gameobj->IsDupliGroup()) {
			// Separate list as m_logicHierarchicalGameObjects is also used by DupliGroupRecurse().
			duplilist.push_back(gameobj);
		}
	}
	for (KX_GameObject *gameobj : duplilist) {
		DupliGroupRecurse(gameobj, 0);
	}

	// Don't release replica here because we are returning it, not done with it...
	return replica;
}

void KX_Scene::RemoveObject(KX_GameObject *gameobj)
{
	// Disconnect child from parent.
	SG_Node *node = gameobj->GetNode();

	if (node) {
		node->DisconnectFromParent();

		// Recursively destruct.
		node->Destruct();
	}
}

void KX_Scene::RemoveDupliGroup(KX_GameObject *gameobj)
{
	if (gameobj->GetInstanceObjects()) {
		for (KX_GameObject *instance : gameobj->GetInstanceObjects()) {
			DelayedRemoveObject(instance);
		}
	}
}

void KX_Scene::DelayedRemoveObject(KX_GameObject *gameobj)
{
	RemoveDupliGroup(gameobj);

	CM_ListAddIfNotFound(m_euthanasyobjects, gameobj);
}

void KX_Scene::RemoveEuthanasyObjects()
{
	bool empty = m_euthanasyobjects.empty();

	/* Don't remove the objects from the euthanasy list here as the child objects of a deleted
	 * parent object are destructed directly from the sgnode in the same time the parent
	 * object is destructed. These child objects must be removed automatically from the
	 * euthanasy list to avoid double deletion in case the user ask to delete the child object
	 * explicitly. NewRemoveObject is the place to do it.
	 */
	while (!m_euthanasyobjects.empty()) {
		RemoveObject(m_euthanasyobjects.front());
	}

	// Check that it was not empty, if so, the profiling process may have invalid objects. Update
	if (!empty) {
		KX_GetActiveEngine()->GetDebugMode()->ForceProfilingUpdate();
	}
}

bool KX_Scene::NewRemoveObject(KX_GameObject *gameobj)
{
	// Remove property from debug list.
	RemoveObjectDebugProperties(gameobj);

	/* Invalidate the python reference, since the object may exist in script lists
	 * its possible that it wont be automatically invalidated, so do it manually here,
	 *
	 * if for some reason the object is added back into the scene python can always get a new Proxy
	 */
	gameobj->InvalidateProxy();

	/* Keep the blender->game object association up to date
	 * note that all the replicas of an object will have the same
	 * blender object, that's why we need to check the game object
	 * as only the deletion of the original object must be recorded.
	 */
	if (gameobj->GetBlenderObject()) {
		// In some case the game object can contains a nullptr blender object e.g default camera.
		m_logicmgr->UnregisterGameObj(gameobj->GetBlenderObject(), gameobj);
	}

	// Remove all sensors/controllers/actuators from logicsystem.

	SCA_SensorList& sensors = gameobj->GetSensors();
	for (SCA_ISensor *sensor : sensors) {
		m_logicmgr->RemoveSensor(sensor);
	}

	SCA_ControllerList& controllers = gameobj->GetControllers();
	for (SCA_IController *controller : controllers) {
		m_logicmgr->RemoveController(controller);
		controller->ReParent(nullptr);
	}

	SCA_ActuatorList& actuators = gameobj->GetActuators();
	for (SCA_IActuator *actuator : actuators) {
		m_logicmgr->RemoveActuator(actuator);
	}
	// The sensors/controllers/actuators must also be released, this is done in ~SCA_IObject.

	// Now remove the timer properties from the time manager.
	for (unsigned short i = 0, numprops = gameobj->GetPropertyCount(); i < numprops; ++i) {
		EXP_Value *propval = gameobj->GetProperty(i);
		if (propval->GetProperty("timer")) {
			m_timemgr->RemoveTimeProperty(propval);
		}
	}

	/* If the object is the dupligroup proxy, you have to cleanup all m_dupliGroupObject's in all
	 * instances refering to this group. */
	if (gameobj->GetInstanceObjects()) {
		for (KX_GameObject *instance : gameobj->GetInstanceObjects()) {
			instance->RemoveDupliGroupObject();
		}
	}

	// If this object was part of a group, make sure to remove it from that group's instance list.
	KX_GameObject *group = gameobj->GetDupliGroupObject();
	if (group) {
		group->RemoveInstanceObject(gameobj);
	}

	if (m_obstacleSimulation) {
		m_obstacleSimulation->DestroyObstacleForObj(gameobj);
	}

	m_componentManager.UnregisterObject(gameobj);

	gameobj->RemoveMeshes();

	m_rendererManager->InvalidateViewpoint(gameobj);

	bool ret = true;
	if (m_lightlist->RemoveValue(gameobj)) {
		ret = (gameobj->Release() != nullptr);
	}
	if (m_objectlist->RemoveValue(gameobj)) {
		ret = (gameobj->Release() != nullptr);
	}
	if (m_parentlist->RemoveValue(gameobj)) {
		ret = (gameobj->Release() != nullptr);
	}
	if (m_inactivelist->RemoveValue(gameobj)) {
		ret = (gameobj->Release() != nullptr);
	}
	if (m_fontlist->RemoveValue(gameobj)) {
		ret = (gameobj->Release() != nullptr);
	}
	if (m_speakerlist->RemoveValue(gameobj)) {
		ret = (gameobj->Release() != nullptr);
	}
	if (m_cameralist->RemoveValue(gameobj)) {
		ret = (gameobj->Release() != nullptr);
	}
	if (m_renderlist->RemoveValue(gameobj)) {
		ret = (gameobj->Release() != nullptr);
	}

	// WARNING: 'gameobj' maybe be freed now, only compare, don't access.
	CM_ListRemoveIfFound(m_cullinglist, gameobj);
	CM_ListRemoveIfFound(m_animatedlist, gameobj);
	CM_ListRemoveIfFound(m_euthanasyobjects, gameobj);
	CM_ListRemoveIfFound(m_tempObjectList, gameobj);
	CM_ListRemoveIfFound(m_gpuParticleObjects, gameobj);
	CM_ListRemoveIfFound(m_gpuParticleColliderObjects, gameobj);
	if (CM_ListRemoveIfFound(m_staticShadowCasterObjects, gameobj)) {
		m_staticShadowCasterListDirty = true;
	}
	CM_ListRemoveIfFound(m_dynamicShadowCasterObjects, gameobj);

	if (gameobj == m_activeCamera) {
		m_activeCamera = nullptr;
	}

	if (gameobj == m_overrideCullingCamera) {
		m_overrideCullingCamera = nullptr;
	}

	// Return value will be nullptr if the object is actually deleted (all reference gone)
	return ret;
}

KX_Camera *KX_Scene::GetActiveCamera()
{
	// nullptr if not defined.
	return m_activeCamera;
}

const mt::vec3& KX_Scene::GetOptimizationReferencePosition() const
{
	return m_optimizationReferencePosition;
}

void KX_Scene::UpdateOptimizationReference()
{
	if (m_activeCamera) {
		m_optimizationReferencePosition = m_activeCamera->NodeGetWorldPosition();
	}
}

void KX_Scene::SetActiveCamera(KX_Camera *cam)
{
	m_activeCamera = cam;
	UpdateOptimizationReference();
}

int KX_Scene::GetLastCullingTotalObjects() const
{
	return m_lastCullingTotalObjects;
}

int KX_Scene::GetLastCullingTestedObjects() const
{
	return m_lastCullingTestedObjects;
}

int KX_Scene::GetLastCullingVisibleObjects() const
{
	return m_lastCullingVisibleObjects;
}

int KX_Scene::GetLastLightsTotal() const
{
	return m_lastLightsTotal;
}

int KX_Scene::GetLastLightsShadowUpdated() const
{
	return m_lastLightsShadowUpdated;
}

int KX_Scene::GetLastShadowPasses() const
{
	return m_lastShadowPasses;
}

void KX_Scene::SetLastLightsCounters(int total, int shadowUpdated, int shadowPasses)
{
	m_lastLightsTotal = total;
	m_lastLightsShadowUpdated = shadowUpdated;
	m_lastShadowPasses = shadowPasses;
}

KX_Camera *KX_Scene::GetOverrideCullingCamera() const
{
	return m_overrideCullingCamera;
}

void KX_Scene::SetOverrideCullingCamera(KX_Camera *cam)
{
	m_overrideCullingCamera = cam;
}

void KX_Scene::SetCameraOnTop(KX_Camera *cam)
{
	// No release and addref just change camera place.
	m_cameralist->RemoveValue(cam);
	m_cameralist->Add(cam);
}

void KX_Scene::PhysicsCullingCallback(KX_ClientObjectInfo *objectInfo, void *cullingInfo)
{
	CullingInfo *info = static_cast<CullingInfo *>(cullingInfo);
	KX_GameObject *gameobj = objectInfo->m_gameobject;

	if (!gameobj->Renderable(info->m_layer)) {
		return;
	}

	if (!info->m_is_shadowbuf && !gameobj->GetVisibleLOD()) {
		gameobj->UpdateVisibleLOD(info->m_cam);
		return;
	}

	// Make object visible.
	gameobj->GetCullingNode().SetCulled(false);
	info->m_objects.push_back(gameobj);
}

std::vector<KX_GameObject *> KX_Scene::CalculateVisibleMeshes(KX_Camera *cam, RAS_Rasterizer::StereoEye eye, int layer, bool is_shadowbuf)
{
	std::vector<KX_GameObject *> objects;
	objects.reserve(m_renderlist->GetCount());
	if (!cam->GetFrustumCulling()) {
		for (KX_GameObject *gameobj : m_renderlist) {
			if (!gameobj->Renderable(layer)) {
				continue;
			}
			gameobj->GetCullingNode().SetCulled(false);
			objects.push_back(gameobj);
		}
		if (!is_shadowbuf) {
			m_lastCullingTotalObjects = m_renderlist->GetCount();
			m_lastCullingTestedObjects = (int)objects.size();
			m_lastCullingVisibleObjects = (int)objects.size();
		}
		return objects;
	}

	return CalculateVisibleMeshes(cam, cam->GetFrustum(eye), layer, is_shadowbuf);
}

std::vector<KX_GameObject *> KX_Scene::CalculateVisibleMeshes(KX_Camera *cam, const SG_Frustum& frustum, int layer, bool is_shadowbuf)
{
	std::vector<KX_GameObject *> objects;
	objects.reserve(m_renderlist->GetCount());
	m_boundingBoxManager->Update(false);

	bool dbvt_culling = false;
	if (m_dbvtCulling) {
		for (KX_GameObject *gameobj : m_renderlist) {
			/* Reset KX_GameObject m_culled to true before doing culling
			 * since DBVT culling will only set it to false.
			 */
			gameobj->GetCullingNode().SetCulled(true);
			// Update the object bounding volume box.
			gameobj->UpdateBounds(false);
		}

		// Test culling through Bullet, get the clip planes.
		const std::array<mt::vec4, 6>& planes = frustum.GetPlanes();
		const mt::mat4& matrix = frustum.GetMatrix();
		const int *viewport = KX_GetActiveEngine()->GetCanvas()->GetViewPort();
		CullingInfo info(layer, objects, cam, is_shadowbuf);

		dbvt_culling = m_physicsEnvironment->CullingTest(PhysicsCullingCallback, &info, planes, m_dbvtOcclusionRes, viewport, matrix);
	}

	int testedCount;
	if (!dbvt_culling) {
		KX_CullingHandler handler(m_renderlist, frustum, layer);
		objects = handler.Process();
		testedCount = handler.GetLastTestedCount();
	}
	else {
		// Bullet's DBVT culling tests the whole render list through its own tree
		// query, not a per-object linear pass, so there is no exact "tested"
		// subset to report separately from the full list.
		testedCount = m_renderlist->GetCount();
	}

	if (!is_shadowbuf) {
		m_lastCullingTotalObjects = m_renderlist->GetCount();
		m_lastCullingTestedObjects = testedCount;
		m_lastCullingVisibleObjects = (int)objects.size();
	}

	m_boundingBoxManager->ClearModified();

	return objects;
}

RAS_DebugDraw& KX_Scene::GetDebugDraw()
{
	return m_debugDraw;
}

void KX_Scene::DrawDebug(const std::vector<KX_GameObject *>& objects,
                         KX_DebugOption showBoundingBox, KX_DebugOption showArmatures)
{
	if (showBoundingBox != KX_DebugOption::DISABLE) {
		for (KX_GameObject *gameobj : objects) {
			const mt::vec3& scale = gameobj->NodeGetWorldScaling();
			const mt::vec3& position = gameobj->NodeGetWorldPosition();
			const mt::mat3& orientation = gameobj->NodeGetWorldOrientation();
			const SG_BBox& box = gameobj->GetCullingNode().GetAabb();
			const mt::vec3& center = box.GetCenter();

			m_debugDraw.DrawAabb(position, orientation, box.GetMin() * scale, box.GetMax() * scale,
				mt::vec4(1.0f, 0.0f, 1.0f, 1.0f));
		
			static const mt::vec3 axes[] = {mt::axisX3, mt::axisY3, mt::axisZ3};
			static const mt::vec4 colors[] = {mt::vec4(1.0f, 0.0f, 0.0f, 1.0f), mt::vec4(0.0f, 1.0f, 0.0f, 1.0f), mt::vec4(0.0f, 0.0f, 1.0f, 1.0f)};
			// Render center in red, green and blue.
			for (unsigned short i = 0; i < 3; ++i) {
				m_debugDraw.DrawLine(orientation * (center * scale) + position,
					orientation * ((center + axes[i]) * scale) + position, colors[i]);
			}
		}
	}

	if (showArmatures != KX_DebugOption::DISABLE) {
		// The side effect of a armature is that it was added in the animated object list.
		for (KX_GameObject *gameobj : m_animatedlist) {
			if (gameobj->GetGameObjectType() == SCA_IObject::OBJ_ARMATURE) {
				BL_ArmatureObject *armature = static_cast<BL_ArmatureObject *>(gameobj);
				if (showArmatures == KX_DebugOption::FORCE || armature->GetDrawDebug()) {
					armature->DrawDebug(m_debugDraw);
				}
			}
		}
	}
}

void KX_Scene::RenderDebugProperties(RAS_DebugDraw& debugDraw, int xindent, int ysize, int& xcoord, int& ycoord, unsigned short propsMax)
{
	static const mt::vec4 white(1.0f, 1.0f, 1.0f, 1.0f);
	static const mt::vec4 valuec(0.0f, 0.8f, 0.4f, 1.0f);
	static const mt::vec4 framec(0.3f, 0.3f, 0.3f, 0.7f);

	// The 'normal' debug props.
	const std::vector<SCA_DebugProp>& debugproplist = GetDebugProperties();

	unsigned short numprop = debugproplist.size();
	if (numprop > propsMax) {
		numprop = propsMax;
	}

	for (unsigned short i = 0; i < numprop; ++i) {
		const SCA_DebugProp& debugProp = debugproplist[i];
		SCA_IObject *gameobj = debugProp.m_obj;
		const std::string objname = gameobj->GetName();
		const std::string& propname = debugProp.m_name;
		if (propname == "__state__") {
			// reserve name for object state
			unsigned int state = gameobj->GetState();
			std::string debugtxt = objname + "." + propname + " = ";
			bool first = true;
			for (int statenum = 1; state; state >>= 1, statenum++) {
				if (state & 1) {
					if (!first) {
						debugtxt += ",";
					}
					debugtxt += std::to_string(statenum);
					first = false;
				}
			}
			debugDraw.RenderText2d(debugtxt, mt::vec2(xcoord + xindent, ycoord), valuec);
			debugDraw.RenderBox2d(mt::vec2((xcoord + xindent) - 1, (ycoord + 2)), mt::vec2(6.1f * debugtxt.length(), 14), framec);
			ycoord += ysize;
		}
		else {
			EXP_Value *propval = gameobj->GetProperty(propname);
			if (propval) {
				const std::string text = propval->GetText();
				const std::string textspace(propname.length(),' ');
				const std::string debugtxt = objname + ": '" + textspace + "' = "; //+ text;
				debugDraw.RenderText2d(debugtxt, mt::vec2(xcoord + xindent, ycoord), white);
				debugDraw.RenderText2d(propname, mt::vec2(xcoord + 6.1f * (objname.length() + 3.5f), ycoord), valuec);
				debugDraw.RenderText2d(text, mt::vec2(xcoord + 6.1f * debugtxt.length() , ycoord), valuec);
				debugDraw.RenderBox2d(mt::vec2((xcoord + xindent)-1, (ycoord+2)),mt::vec2(6.1f * (debugtxt.length() + text.length()),14), framec);
				ycoord += ysize;
			}
		}
	}
}

void KX_Scene::RenderDebugPropertiesImGui(int sceneIndex) {
	KX_DebugMode *debugMode = KX_GetActiveEngine()->GetDebugMode();

	// The 'normal' debug props.
	const std::vector<SCA_DebugProp>& debugproplist = GetDebugProperties();

	for (unsigned short i = 0; i < debugproplist.size(); ++i) {
		const SCA_DebugProp& debugProp = debugproplist[i];
		SCA_IObject *gameobj = debugProp.m_obj;
		const std::string objname = gameobj->GetName();
		const std::string& propname = debugProp.m_name;

		if (propname == "__state__") {
			// reserve name for object state
			unsigned int state = gameobj->GetState();
			std::string debugtxt = "";
			bool first = true;
			for (int statenum = 1; state; state >>= 1, statenum++) {
				if (state & 1) {
					if (!first) {
						debugtxt += ",";
					}
					debugtxt += std::to_string(statenum);
					first = false;
				}
			}
			ImGui::Text("%s.__state__ = ", objname.c_str());
			if (ImGui::IsItemHovered()) {
				ImGui::SetTooltip("__state__ Property: Represents which logic state is active in the object.");
			}
			ImGui::SameLine();
			ImGui::TextColored(ImVec4(0, 180, 40, 255), "%s", debugtxt.c_str());

		}
		/* Draw Property */
		else {
			// Ugly code.. 
			EXP_Value *propval = gameobj->GetProperty(propname);
			if (propval) {
				std::string proptext = propval->GetText();
				// Draw prop.
				ImGui::Text("%s:", objname.c_str());
				ImGui::SameLine(0, 0); ImGui::Text("'"); ImGui::SameLine(0, 0);
				ImGui::TextColored(ImVec4(0, 180, 40, 255), "%s", propname.c_str());
				ImGui::SameLine(0, 0); ImGui::Text("'"); ImGui::SameLine();
				ImGui::Text("="); ImGui::SameLine();

				// Avoid >20 letters on string type ...
				if (propval->GetValueType() == VALUE_DATA_TYPE::VALUE_STRING_TYPE && (proptext.length() > 20)) {
					proptext = proptext.substr(0, 20);
					proptext.append("...");
				}

				ImGui::TextColored(ImVec4(0, 180, 40, 255), "'%s'", proptext.c_str());
				
				if (ImGui::IsItemHovered()) {
					// hint
					ImGui::SetTooltip("Edit value (Left-click)");

					// Open Popup, edit value.
					if (ImGui::IsMouseClicked(0)) {
						//printf("For loop: %i Scene Index: %i ID: %s \n", (i + 1), sceneIndex + i, id.c_str());
						std::string popup = "EditValue##" + objname + propname + std::to_string(sceneIndex);
						debugMode->imgui_debugPropID = popup;
						debugMode->imgui_debugListProp_Index = i;
						debugMode->imgui_sceneProp_Index = sceneIndex;

						ImGui::OpenPopup(popup.c_str());

						// hint
						if (ImGui::IsItemHovered()) {
							ImGui::SetTooltip("Property value = %s", proptext.c_str());
						}
					}
				}
			}	
		}
	}

	/* Here we check if the rendering is done in the right scene, */
	/* invalid if you try to get the value in the wrong scene.    */
	if (sceneIndex != debugMode->imgui_sceneProp_Index) {
		return;
	}

	// Render Popup
	std::string popup = debugMode->imgui_debugPropID;
	if (ImGui::BeginPopup(popup.c_str())) {
		const SCA_DebugProp& debugProp = debugproplist[debugMode->imgui_debugListProp_Index];
		
		SCA_IObject *gameobj = debugProp.m_obj;
		const std::string& propname = debugProp.m_name;

		EXP_Value *propval = gameobj->GetProperty(propname);
		const std::string proptext = propval->GetText();

		// Now we can edit the value.
		std::string id = "Value##" + popup;

		switch (propval->GetValueType()) {
			case VALUE_DATA_TYPE::VALUE_BOOL_TYPE: {
				bool oldprop = (propval->GetNumber() == 1) ? true : false;

				if (ImGui::Checkbox(id.c_str(), &oldprop)) {
					EXP_Value *newval = new EXP_BoolValue(oldprop);
					gameobj->SetProperty(propname, newval);
				}
				break;
			}
			case VALUE_DATA_TYPE::VALUE_FLOAT_TYPE: {
				float oldprop = (float)propval->GetNumber();

				if (ImGui::InputFloat(id.c_str(), &oldprop, 0.01f, 1.0f, "%.3f")) {
					EXP_Value *newval = new EXP_FloatValue(oldprop);
					gameobj->SetProperty(propname, newval);
				}
				break;
			}
			case VALUE_DATA_TYPE::VALUE_INT_TYPE: {
				int oldprop = (int)propval->GetNumber();

				if (ImGui::InputInt(id.c_str(), &oldprop, 1, 10)) {
					EXP_Value *newval = new EXP_IntValue(oldprop);
					gameobj->SetProperty(propname, newval);
				}
				break;
			}
			case VALUE_DATA_TYPE::VALUE_STRING_TYPE: {
				const std::string proptext = propval->GetText();
				char oldprop[1000];
				strncpy(oldprop, proptext.c_str(), sizeof(oldprop) - 1);
				oldprop[sizeof(oldprop) - 1] = '\0';

				ImGui::Text("String: %s", proptext.c_str());

				if (ImGui::InputText(id.c_str(), oldprop, sizeof(oldprop))) {
					EXP_Value *newval = new EXP_StringValue(oldprop, oldprop);
					gameobj->SetProperty(propname, newval);
				}
				break;
			}
		}
		ImGui::EndPopup();
	}
}

void KX_Scene::FlushDebugDraw(RAS_Rasterizer *rasty, RAS_ICanvas *canvas)
{
	m_debugDraw.Flush(rasty, canvas);
}

void KX_Scene::LogicBeginFrame(double curtime, double framestep)
{
	// Have a look at temp objects.
	for (KX_GameObject *gameobj : m_tempObjectList) {
		EXP_FloatValue *propval = static_cast<EXP_FloatValue *>(gameobj->GetProperty("::timebomb"));

		if (propval) {
			const float timeleft = propval->GetNumber() - framestep;

			if (timeleft > 0) {
				propval->SetFloat(timeleft);
			}
			else {
				// Remove obj, remove the object from tempObjectList in NewRemoveObject only.
				DelayedRemoveObject(gameobj);
			}
		}
		else {
			// All object is the tempObjectList should have a clock.
			BLI_assert(false);
		}
	}
	m_logicmgr->BeginFrame(curtime, framestep);
}

void KX_Scene::AddAnimatedObject(KX_GameObject *gameobj)
{
	CM_ListAddIfNotFound(m_animatedlist, gameobj);
}

void KX_Scene::AddCullingObject(KX_GameObject *gameobj)
{
	CM_ListAddIfNotFound(m_cullinglist, gameobj);
}

void KX_Scene::RemoveCullingObject(KX_GameObject *gameobj)
{
	CM_ListRemoveIfFound(m_cullinglist, gameobj);
}

// Shared by both passes: decide whether this object's pose is worth resolving in full this frame
// (culled armatures with all children culled only need their animation time/events tracked).
static bool anim_needs_update(KX_GameObject *gameobj)
{
	// Non-armature updates are fast enough, so just update them
	bool needs_update = gameobj->GetGameObjectType() != SCA_IObject::OBJ_ARMATURE;

	if (!needs_update) {
		// In this case, we'll check to see if the culling method makes an exception to allow need_update.
		BL_ArmatureObject *armobj = static_cast<BL_ArmatureObject*>(gameobj);
		if (armobj && armobj->GetCullingMethod() == 1) {
			// GetCullingMethod() == 1 is NONE Culling. Throw the exception ( needs_update = true ).
			needs_update = true;
		}
	}

	if (!needs_update) {
		// If we got here, we're looking to update an armature, so check its children meshes
		// to see if we need to bother with a more expensive pose update
		const std::vector<KX_GameObject *> children = gameobj->GetChildren();

		bool has_mesh = false;
		//, has_non_mesh = false

		// Check for meshes that haven't been culled
		for (KX_GameObject *child : children) {
			if (!child->GetCullingNode().GetCulled()) {
				needs_update = true;
				break;
			}

			if (!child->GetMeshList().empty()) {
				has_mesh = true;
				//has_non_mesh = true;
			}
			//else {
			//	has_mesh = true;
			//}
		}

		// If we didn't find a non-culled mesh, check to see
		// if we even have any meshes, and update if this
		// armature has only non-mesh children.
		//if (!needs_update && !has_mesh && has_non_mesh) {
		//	needs_update = true;
		//}
	}

	return needs_update;
}

// Pass 1 (profiler category "Animations"): action/fcurve evaluation and pose blending only.
// Writes needs_update into a pre-populated cache entry (never inserts - see UpdateAnimations()),
// which is safe to update concurrently from multiple threads since no rehash can happen.
void KX_Scene::UpdateAnimPoseTask(TaskPool *pool, void *taskdata, int UNUSED(threadid))
{
	KX_Scene::AnimationPoolData *data = (KX_Scene::AnimationPoolData *)BLI_task_pool_userdata(pool);
	double curtime = data->curtime;

	KX_GameObject *gameobj = (KX_GameObject *)taskdata;

	const bool needs_update = anim_needs_update(gameobj);
	data->scene->m_animNeedsUpdateCache[gameobj] = needs_update;

	// If the object is a culled armature, then we manage only the animation time and end of its animations.
	gameobj->UpdateActionManager(curtime, needs_update);
}

// Pass 2 (profiler category "Skinning"): deformer update (CPU skinning) for objects that pass 1
// marked as needing it. Only depends on this object's own already-resolved pose from pass 1.
void KX_Scene::UpdateAnimDeformTask(TaskPool *UNUSED(pool), void *taskdata, int UNUSED(threadid))
{
	// Calculate how much time was spent on this
	const bool doProfiling = KX_GetActiveEngine()->GetDebugMode()->UseAdvancedProfiling();
	float timeProfiling = doProfiling ? (float)KX_GetActiveEngine()->GetTimeSecondClock() : 0.f;

	KX_GameObject *gameobj = (KX_GameObject *)taskdata;

	const std::vector<KX_GameObject *> children = gameobj->GetChildren();
	KX_GameObject *parent = gameobj->GetParent();

	// Only do deformers here if they are not parented to an armature, otherwise the armature will
	// handle updating its children
	if (gameobj->GetDeformer() && (!parent || parent->GetGameObjectType() != SCA_IObject::OBJ_ARMATURE)) {
		gameobj->GetDeformer()->Update();
	}

	for (KX_GameObject *child : children) {
		if (child->GetDeformer()) {
			child->GetDeformer()->Update();
		}
	}

	if (doProfiling) {
		// set time elapsed.
		gameobj->SetDebugTimeProfiling(KX_GameObject::DebugProfilingType::TIME_ANIMATION, timeProfiling);
	}
}

bool KX_Scene::UpdateAnimations(double curtime, bool restrict)
{
	if (restrict) {
		const double animTimeStep = 1.0 / m_blenderScene->r.frs_sec;

		/* Don't update if the time step is too small and if we are not asking for redundant
		 * updates like for different culling passes. */
		if ((curtime - m_previousAnimTime) < animTimeStep && curtime != m_previousAnimTime) {
			return false;
		}

		// Sanity/debug print to make sure we're actually going at the fps we want (should be close to animTimeStep)
		// CM_Debug("Anim fps: " << 1.0 / (curtime - m_previousAnimTime));
		m_previousAnimTime = curtime;
	}

	m_animationPoolData.curtime = curtime;

	// Pre-populate the needs_update cache on the main thread before dispatching: pass 1 (below) only
	// ever assigns to existing keys from multiple threads, never inserts, so no rehash can race.
	m_animNeedsUpdateCache.clear();
	for (KX_GameObject *gameobj : m_animatedlist) {
		if (!gameobj->IsActionsSuspended() && gameobj->GetDoAnimations()) {
			m_animNeedsUpdateCache[gameobj] = false;
		}
	}

	// Animation Events: Process triggers captured in executed actions
	for (KX_GameObject *gameobj : m_animatedlist) {
		if (!gameobj->IsActionsSuspended()) {
			if (gameobj->GetDoAnimations()) {
				BLI_task_pool_push(m_animationPool, UpdateAnimPoseTask, gameobj, false, TASK_PRIORITY_LOW);

				KX_AnimationEventManager *eventManager = gameobj->GetAnimationEventManager();
				if (eventManager) {
					
					std::vector<std::pair<KX_AnimationEvent*, const char*>> *eventsPtr = eventManager->GetEventsToCall();

					if (!eventsPtr->empty()) {
						for (const auto event : *eventsPtr) {
							// We make sure it's thread safe. So we can make the call safely.
							PyGILState_STATE gilstate = PyGILState_Ensure();

							PyObject *args = PyTuple_New(2);
							PyObject *custom_arg = PyUnicode_FromString(event.second);
							PyTuple_SET_ITEM(args, 0, gameobj->GetProxy());
							PyTuple_SET_ITEM(args, 1, custom_arg);

							PyObject *function = event.first->GetPyEventFunction();

							if (PyCallable_Check(function)) {
								// Run Function
								PyObject *ret = PyObject_Call(function, args, nullptr);

								if (!ret) {
									EXP_ReportPythonDiagnostic("scene.animation.event", gameobj->GetName().c_str());
									PyErr_Print();
									PyErr_Clear();
								}
								else {
									Py_DECREF(args);
									Py_DECREF(ret);
								}
							}
							else {
								EXP_ReportPythonDiagnostic("scene.animation.event.callable", gameobj->GetName().c_str());
								PyErr_Print();
								PyErr_Clear();
								Py_DECREF(args);
							}

							// Release the GIL
							PyGILState_Release(gilstate);
						}
						eventsPtr->clear();
					}
				}
			}
		}
	}

	BLI_task_pool_work_and_wait(m_animationPool);

	return true;
}

void KX_Scene::UpdateAnimationDeformers()
{
	for (const auto &entry : m_animNeedsUpdateCache) {
		if (entry.second) {
			BLI_task_pool_push(m_animationPool, UpdateAnimDeformTask, entry.first, false, TASK_PRIORITY_LOW);
		}
	}

	BLI_task_pool_work_and_wait(m_animationPool);
}

void KX_Scene::LogicUpdateFrame(double curtime)
{
	m_componentManager.UpdateComponents();

	m_logicmgr->UpdateFrame(curtime);

	// 3D Audio Update. (only for speakers)
	if (m_audio3d_frames >= m_audio3d_update) {
		for (KX_Speaker *speaker : m_speakerlist) {
			// Don't update speakers on inactive layer.
			if ((speaker->GetLayer() & GetBlenderScene()->lay) != 0) {
				speaker->Update();
			}
		}
		m_audio3d_frames = 0;
	}
  else {
    m_audio3d_frames++;
  }
}

void KX_Scene::LogicEndFrame()
{
	m_logicmgr->EndFrame();

	RemoveEuthanasyObjects();

	//prepare obstacle simulation for new frame
	if (m_obstacleSimulation) {
		m_obstacleSimulation->UpdateObstacles();
	}

	for (KX_FontObject *font : m_fontlist) {
		font->UpdateTextFromProperty();
	}
}

void KX_Scene::UpdateParents()
{
	// We use the SG dynamic list
	SG_Node *node;

	while ((node = SG_Node::GetNextScheduled(m_sghead))) {
		node->UpdateWorldData();
	}

	// The list must be empty here
	BLI_assert(m_sghead.Empty());
	// Some nodes may be ready for reschedule, move them to schedule list for next time.
	while ((node = SG_Node::GetNextRescheduled(m_sghead))) {
		node->Schedule(m_sghead);
	}
}

void KX_Scene::RenderBuckets(const std::vector<KX_GameObject *>& objects, RAS_Rasterizer::DrawType drawingMode, const mt::mat3x4& cameratransform,
                             RAS_Rasterizer *rasty, RAS_OffScreen *offScreen)
{
	for (KX_GameObject *gameobj : objects) {
		/* This function update all mesh slot info (e.g culling, color, matrix) from the game object.
		 * It's done just before the render to be sure of the object color and visibility. */
		gameobj->UpdateBuckets();
	}

	m_bucketmanager->Renderbuckets(drawingMode, cameratransform, rasty, offScreen);
	KX_BlenderMaterial::EndFrame(rasty);
}

void KX_Scene::RenderTextureRenderers(KX_TextureRendererManager::RendererCategory category, RAS_Rasterizer *rasty,
                                      RAS_OffScreen *offScreen, KX_Camera *camera, const RAS_Rect& viewport, const RAS_Rect& area)
{
	m_rendererManager->Render(category, rasty, offScreen, camera, viewport, area);
}

void KX_Scene::UpdateObjectLods(KX_Camera *cam, const std::vector<KX_GameObject *>& objects)
{
	const mt::vec3& cam_pos = cam->NodeGetWorldPosition();
	const float lodfactor = cam->GetLodDistanceFactor();

	for (KX_GameObject *gameobj : objects) {
		gameobj->UpdateLod(this, cam_pos, lodfactor);
	}
}

void KX_Scene::SetLodHysteresis(bool active)
{
	m_isActivedHysteresis = active;
}

bool KX_Scene::IsActivedLodHysteresis() const
{
	return m_isActivedHysteresis;
}

void KX_Scene::SetLodHysteresisValue(int hysteresisvalue)
{
	m_lodHysteresisValue = hysteresisvalue;
}

int KX_Scene::GetLodHysteresisValue() const
{
	return m_lodHysteresisValue;
}

void KX_Scene::UpdateGpuParticleEmitters(float deltaTime)
{
	for (KX_GameObject *gameobj : m_gpuParticleObjects) {
		// Fase N: simulating an invisible emitter is wasted work with nothing to show for it --
		// skip the whole update, not just the draw. Independent from gpu_particles.enabled,
		// which the object stays visible under (e.g. a wheel that keeps spinning without dust).
		// Also honor frustum culling (Override Culling included) so emitters outside the
		// active camera's view don't keep spawning particles unseen.
		if (gameobj->GetVisible() && !gameobj->GetCullingNode().GetCulled()) {
			gameobj->UpdateParticles(deltaTime);
		}
	}
}

void KX_Scene::AddGpuParticleObject(KX_GameObject *gameobj)
{
	if (std::find(m_gpuParticleObjects.begin(), m_gpuParticleObjects.end(), gameobj) == m_gpuParticleObjects.end()) {
		m_gpuParticleObjects.push_back(gameobj);
	}
}

void KX_Scene::RemoveGpuParticleObject(KX_GameObject *gameobj)
{
	m_gpuParticleObjects.erase(std::remove(m_gpuParticleObjects.begin(), m_gpuParticleObjects.end(), gameobj),
	                            m_gpuParticleObjects.end());
}

const std::vector<KX_GameObject *> &KX_Scene::GetGpuParticleObjects() const
{
	return m_gpuParticleObjects;
}

void KX_Scene::AddGpuParticleColliderObject(KX_GameObject *gameobj)
{
	if (std::find(m_gpuParticleColliderObjects.begin(), m_gpuParticleColliderObjects.end(), gameobj) == m_gpuParticleColliderObjects.end()) {
		m_gpuParticleColliderObjects.push_back(gameobj);
	}
}

void KX_Scene::RemoveGpuParticleColliderObject(KX_GameObject *gameobj)
{
	m_gpuParticleColliderObjects.erase(std::remove(m_gpuParticleColliderObjects.begin(), m_gpuParticleColliderObjects.end(), gameobj),
	                                    m_gpuParticleColliderObjects.end());
}

const std::vector<KX_GameObject *> &KX_Scene::GetGpuParticleColliderObjects() const
{
	return m_gpuParticleColliderObjects;
}

void KX_Scene::AddStaticShadowCasterObject(KX_GameObject *gameobj)
{
	if (std::find(m_staticShadowCasterObjects.begin(), m_staticShadowCasterObjects.end(), gameobj) == m_staticShadowCasterObjects.end()) {
		m_staticShadowCasterObjects.push_back(gameobj);
		m_staticShadowCasterListDirty = true;
	}
}

void KX_Scene::RemoveStaticShadowCasterObject(KX_GameObject *gameobj)
{
	m_staticShadowCasterObjects.erase(std::remove(m_staticShadowCasterObjects.begin(), m_staticShadowCasterObjects.end(), gameobj),
	                                   m_staticShadowCasterObjects.end());
	m_staticShadowCasterListDirty = true;
}

const std::vector<KX_GameObject *> &KX_Scene::GetStaticShadowCasterObjects() const
{
	return m_staticShadowCasterObjects;
}

void KX_Scene::AddDynamicShadowCasterObject(KX_GameObject *gameobj)
{
	if (std::find(m_dynamicShadowCasterObjects.begin(), m_dynamicShadowCasterObjects.end(), gameobj) == m_dynamicShadowCasterObjects.end()) {
		m_dynamicShadowCasterObjects.push_back(gameobj);
	}
}

void KX_Scene::RemoveDynamicShadowCasterObject(KX_GameObject *gameobj)
{
	m_dynamicShadowCasterObjects.erase(std::remove(m_dynamicShadowCasterObjects.begin(), m_dynamicShadowCasterObjects.end(), gameobj),
	                                    m_dynamicShadowCasterObjects.end());
}

const std::vector<KX_GameObject *> &KX_Scene::GetDynamicShadowCasterObjects() const
{
	return m_dynamicShadowCasterObjects;
}

bool KX_Scene::IsStaticShadowCasterListDirty() const
{
	return m_staticShadowCasterListDirty;
}

void KX_Scene::ClearStaticShadowCasterListDirty()
{
	m_staticShadowCasterListDirty = false;
}

void KX_Scene::UpdateObjectActivity()
{
	if (!m_activityCulling) {
		return;
	}

	// Activity culling follows the same reference as the other distance-based
	// optimizations: the active game camera today, and the Player reference when
	// it is introduced. This avoids treating an inactive editor/cutscene camera
	// as a reason to keep objects active.
	KX_Camera *activeCamera = GetActiveCamera();
	if (!activeCamera || !activeCamera->GetActivityCulling()) {
		return;
	}

	// Refresh here because activity is evaluated at the beginning of the
	// simulation frame, before the post-physics refresh used by rendering.
	UpdateOptimizationReference();
	const mt::vec3& referencePosition = GetOptimizationReferencePosition();

	for (KX_GameObject *gameobj : m_cullinglist) {
		const mt::vec3& obpos = gameobj->NodeGetWorldPosition();
		gameobj->UpdateActivity((obpos - referencePosition).LengthSquared());
	}
}

KX_NetworkMessageScene *KX_Scene::GetNetworkMessageScene() const
{
	return m_networkScene;
}

void KX_Scene::SetNetworkMessageScene(KX_NetworkMessageScene *netScene)
{
	m_networkScene = netScene;
}

PHY_IPhysicsEnvironment *KX_Scene::GetPhysicsEnvironment() const
{
	return m_physicsEnvironment;
}

void KX_Scene::SetPhysicsEnvironment(PHY_IPhysicsEnvironment *physEnv)
{
	m_physicsEnvironment = physEnv;
	if (m_physicsEnvironment) {
		KX_CollisionEventManager *collisionmgr = new KX_CollisionEventManager(m_logicmgr, physEnv);
		m_logicmgr->RegisterEventManager(collisionmgr);
	}
}

void KX_Scene::SetGravity(const mt::vec3& gravity)
{
	m_physicsEnvironment->SetGravity(gravity[0], gravity[1], gravity[2]);
}

mt::vec3 KX_Scene::GetGravity() const
{
	return m_physicsEnvironment->GetGravity();
}

void KX_Scene::SetSuspendedDelta(double suspendeddelta)
{
	m_suspendedDelta = suspendeddelta;
}

double KX_Scene::GetSuspendedDelta() const
{
	return m_suspendedDelta;
}

Scene *KX_Scene::GetBlenderScene() const
{
	return m_blenderScene;
}

static void MergeScene_LogicBrick(SCA_ILogicBrick *brick, KX_Scene *from, KX_Scene *to)
{
	SCA_LogicManager *logicmgr = to->GetLogicManager();

	brick->Replace_IScene(to);
	brick->Replace_NetworkScene(to->GetNetworkMessageScene());
	brick->SetLogicManager(to->GetLogicManager());

	/* If we end up replacing a KX_CollisionEventManager, we need to make sure
	 * physics controllers are properly in place. In other words, do this
	 * after merging physics controllers.
	 */
	SCA_ISensor *sensor = dynamic_cast<SCA_ISensor *>(brick);
	if (sensor) {
		sensor->Replace_EventManager(logicmgr);
	}

	SCA_2DFilterActuator *filter_actuator = dynamic_cast<SCA_2DFilterActuator *>(brick);
	if (filter_actuator) {
		filter_actuator->SetScene(to, to->Get2DFilterManager());
	}
}

static void MergeScene_GameObject(KX_GameObject *gameobj, KX_Scene *to, KX_Scene *from)
{
	const SCA_ActuatorList& actuators = gameobj->GetActuators();
	for (SCA_IActuator *actuator : actuators) {
		MergeScene_LogicBrick(actuator, from, to);
	}

	const SCA_SensorList& sensors = gameobj->GetSensors();
	for (SCA_ISensor *sensor : sensors) {
		MergeScene_LogicBrick(sensor, from, to);
	}

	const SCA_ControllerList& controllers = gameobj->GetControllers();
	for (SCA_IController *controller : controllers) {
		MergeScene_LogicBrick(controller, from, to);
	}

	// Graphics controller.
	PHY_IGraphicController *graphicCtrl = gameobj->GetGraphicController();
	if (graphicCtrl) {
		// Should update the m_cullingTree.
		graphicCtrl->SetPhysicsEnvironment(to->GetPhysicsEnvironment());
	}

	PHY_IPhysicsController *physicsCtrl = gameobj->GetPhysicsController();
	if (physicsCtrl) {
		physicsCtrl->SetPhysicsEnvironment(to->GetPhysicsEnvironment());
	}

	// SG_Node can hold a scene reference.
	SG_Node *sg = gameobj->GetNode();
	if (sg) {
		if (sg->GetClientInfo() == from) {
			sg->SetClientInfo(to);

			// Make sure to grab the children too since they might not be tied to a game object.
			const NodeList& children = sg->GetChildren();
			for (SG_Node *child : children) {
				child->SetClientInfo(to);
			}
		}
	}
	switch (gameobj->GetGameObjectType()) {
		// If the object is a light, update it's scene.
		case SCA_IObject::OBJ_LIGHT:
		{
			static_cast<KX_LightObject *>(gameobj)->UpdateScene(to);
			break;
		}
		// All armatures should be in the animated object list to be umpdated.
		case SCA_IObject::OBJ_ARMATURE:
		{
			to->AddAnimatedObject(gameobj);
			break;
		}
		// Force recreation of text users to link them to the merged scene text material.
		case SCA_IObject::OBJ_TEXT:
		{
			gameobj->RemoveMeshes();
			gameobj->AddMeshUser();
			break;
		}
	}

	// Add the object to the scene's logic manager.
	to->GetLogicManager()->RegisterGameObjectName(gameobj->GetName(), gameobj);
	to->GetLogicManager()->RegisterGameObj(gameobj->GetBlenderObject(), gameobj);

	for (KX_Mesh *meshobj : gameobj->GetMeshList()) {
		// Register the mesh object by name and blender object.
		to->GetLogicManager()->RegisterGameMeshName(meshobj->GetName(), gameobj->GetBlenderObject());
		to->GetLogicManager()->RegisterMeshName(meshobj->GetName(), meshobj);
	}
}

bool KX_Scene::MergeScene(KX_Scene *other)
{
	PHY_IPhysicsEnvironment *env = this->GetPhysicsEnvironment();
	PHY_IPhysicsEnvironment *env_other = other->GetPhysicsEnvironment();

	if ((env == nullptr) != (env_other == nullptr)) {
		// TODO - even when both scenes have NONE physics, the other is loaded with bullet enabled, ???
		CM_FunctionError("physics scenes type differ, aborting\n\tsource " << (int)(env != nullptr) << ", target " << (int)(env_other != nullptr));
		return false;
	}

	m_bucketmanager->Merge(other->GetBucketManager(), this);
	m_boundingBoxManager->Merge(other->GetBoundingBoxManager());
	m_rendererManager->Merge(other->GetTextureRendererManager());
	m_componentManager.Merge(other->GetPythonComponentManager());

	bool occlusion = false;
	for (KX_GameObject *gameobj : *other->GetObjectList()) {
		MergeScene_GameObject(gameobj, this, other);

		// Add properties to debug list for LibLoad objects.
		if (KX_GetActiveEngine()->GetFlag(KX_KetsjiEngine::AUTO_ADD_DEBUG_PROPERTIES)) {
			AddObjectDebugProperties(gameobj);
		}

		if (gameobj->GetOccluder()) {
			occlusion = true;
		}
	}

	// Libload objects also need to activate DbvtOcclusion if have one.
	if (occlusion) {
		this->SetDbvtOcclusionRes(this->GetBlenderScene()->gm.occlusionRes);
	}

	for (KX_GameObject *gameobj : *other->GetInactiveList()) {
		MergeScene_GameObject(gameobj, this, other);
	}

	if (env) {
		env->MergeEnvironment(env_other);
		EXP_ListValue<KX_GameObject> *otherObjects = other->GetObjectList();

		// List of all physics objects to merge (needed by ReplicateConstraints).
		std::vector<KX_GameObject *> physicsObjects;
		for (KX_GameObject *gameobj : otherObjects) {
			if (gameobj->GetPhysicsController()) {
				physicsObjects.push_back(gameobj);
			}
		}

		for (KX_GameObject *gameobj : physicsObjects) {
			// Replicate all constraints in the right physics environment.
			gameobj->ReplicateConstraints(m_physicsEnvironment, physicsObjects);
		}
	}

	m_objectlist->MergeList(other->GetObjectList());
	other->GetObjectList()->ReleaseAndRemoveAll();

	m_inactivelist->MergeList(other->GetInactiveList());
	other->GetInactiveList()->ReleaseAndRemoveAll();

	m_parentlist->MergeList(other->GetRootParentList());
	other->GetRootParentList()->ReleaseAndRemoveAll();

	m_lightlist->MergeList(other->GetLightList());
	other->GetLightList()->ReleaseAndRemoveAll();

	m_cameralist->MergeList(other->GetCameraList());
	other->GetCameraList()->ReleaseAndRemoveAll();

	m_fontlist->MergeList(other->GetFontList());
	other->GetFontList()->ReleaseAndRemoveAll();

	m_speakerlist->MergeList(other->GetSpeakerList());
	other->GetSpeakerList()->ReleaseAndRemoveAll();

	m_renderlist->MergeList(other->GetRenderList());
	other->GetRenderList()->ReleaseAndRemoveAll();

	m_gpuParticleObjects.insert(m_gpuParticleObjects.end(), other->m_gpuParticleObjects.begin(), other->m_gpuParticleObjects.end());
	other->m_gpuParticleObjects.clear();

	m_gpuParticleColliderObjects.insert(m_gpuParticleColliderObjects.end(), other->m_gpuParticleColliderObjects.begin(), other->m_gpuParticleColliderObjects.end());
	other->m_gpuParticleColliderObjects.clear();

	if (!other->m_staticShadowCasterObjects.empty()) {
		m_staticShadowCasterObjects.insert(m_staticShadowCasterObjects.end(), other->m_staticShadowCasterObjects.begin(), other->m_staticShadowCasterObjects.end());
		other->m_staticShadowCasterObjects.clear();
		m_staticShadowCasterListDirty = true;
	}
	m_dynamicShadowCasterObjects.insert(m_dynamicShadowCasterObjects.end(), other->m_dynamicShadowCasterObjects.begin(), other->m_dynamicShadowCasterObjects.end());
	other->m_dynamicShadowCasterObjects.clear();

	// Grab any timer properties from the other scene.
	SCA_TimeEventManager *timemgr_other = other->GetTimeEventManager();
	std::vector<EXP_Value *> times = timemgr_other->GetTimeValues();

	for (EXP_Value *time : times) {
		m_timemgr->AddTimeProperty(time);
	}

	return true;
}

bool KX_Scene::GetUseLightScatter() const
{
	return m_useLightScattering;
}

void KX_Scene::SetUseLightScatter(bool enable)
{
	m_useLightScattering = enable;
}

KX_2DFilterManager *KX_Scene::Get2DFilterManager() const
{
	return m_filterManager;
}

RAS_OffScreen *KX_Scene::Render2DFilters(RAS_Rasterizer *rasty, RAS_ICanvas *canvas, RAS_OffScreen *inputofs, RAS_OffScreen *targetofs, const float (&sun_screen_pos)[2])
{
	return m_filterManager->RenderFilters(rasty, canvas, inputofs, targetofs, sun_screen_pos);
}

KX_ObstacleSimulation *KX_Scene::GetObstacleSimulation()
{
	return m_obstacleSimulation;
}

void KX_Scene::SetCutsceneManager(std::unique_ptr<KX_CutsceneManager> cutsceneManager)
{
	ClearCutsceneSpawnedObjects();
	if (m_cutsceneManager) {
		m_cutsceneManager->Stop();
	}
	m_cutsceneManager = std::move(cutsceneManager);
	m_pendingCutsceneEvents.clear();
}

void KX_Scene::StopCutscene()
{
	ClearCutsceneSpawnedObjects();
	if (m_cutsceneManager) {
		m_cutsceneManager->Stop();
	}
	m_pendingCutsceneEvents.clear();
}

bool KX_Scene::RestartCutscene()
{
	if (!m_cutsceneManager) {
		return false;
	}
	ClearCutsceneSpawnedObjects();
	m_pendingCutsceneEvents.clear();
	return m_cutsceneManager->Restart();
}

void KX_Scene::UpdateCutscene(double time)
{
	if (!m_cutsceneManager) {
		return;
	}

	KX_CutsceneManager::DispatchedEvents dispatchedEvents = m_cutsceneManager->Update(time);
	m_pendingCutsceneEvents.insert(
		m_pendingCutsceneEvents.end(), dispatchedEvents.begin(), dispatchedEvents.end());
}

KX_CutsceneManager::DispatchedEvents KX_Scene::TakePendingCutsceneEvents()
{
	KX_CutsceneManager::DispatchedEvents dispatchedEvents;
	dispatchedEvents.swap(m_pendingCutsceneEvents);
	return dispatchedEvents;
}

/* Helper: find first object with matching component name */
static KX_GameObject *FindObjectWithComponent(EXP_ListValue<KX_GameObject> *objectlist, const std::string &componentName)
{
	if (!objectlist) {
		return nullptr;
	}
	for (int i = 0; i < objectlist->GetCount(); ++i) {
		KX_GameObject *obj = objectlist->GetValue(i);
		if (!obj) continue;
		EXP_ListValue<KX_PythonComponent> *components = obj->GetComponents();
		if (components && components->GetCount() > 0) {
			for (int j = 0; j < components->GetCount(); ++j) {
				KX_PythonComponent *comp = components->GetValue(j);
				if (comp && comp->GetName() == componentName) {
					return obj;
				}
			}
		}
	}
	return nullptr;
}

/* Helper: find first object matching name exactly or fallback to component search */
static KX_GameObject *FindGameObject(EXP_ListValue<KX_GameObject> *objectlist,
                                      const std::string &nameOrComponent)
{
	if (!objectlist || nameOrComponent.empty()) {
		return nullptr;
	}
	/* First pass: exact name match */
	for (int i = 0; i < objectlist->GetCount(); ++i) {
		KX_GameObject *obj = objectlist->GetValue(i);
		if (obj && obj->GetName() == nameOrComponent) {
			return obj;
		}
	}
	/* Second pass: component match */
	return FindObjectWithComponent(objectlist, nameOrComponent);
}

/* Helper: get text by language */
static const std::string &GetLocalizedText(const KX_CutsceneManager::Event *event, const std::string &lang)
{
	if (lang == "pt") return event->m_textPt;
	if (lang == "es") return event->m_textEs;
	if (lang == "ru") return event->m_textRu;
	return event->m_textEn; /* Default to English */
}

void KX_Scene::DispatchCutsceneEvents()
{
	const KX_CutsceneManager::DispatchedEvents dispatchedEvents = TakePendingCutsceneEvents();
	for (const KX_CutsceneManager::Event *event : dispatchedEvents) {
		switch (event->m_type) {
		case CUTSCENE_EVENT_SPAWN_OBJECT:
			if (!event->m_templateObject || !event->m_spawnPoint) {
				CM_Error("Cutscene Spawn Object event '" << event->m_name
				         << "' requires Template Object and Spawn Point");
				continue;
			}
			{
				KX_GameObject *replica = AddReplicaObject(event->m_templateObject, event->m_spawnPoint);
				if (!replica) {
					CM_Error("Cutscene Spawn Object event '" << event->m_name
					         << "' could not create the Template Object replica");
					continue;
				}
				KX_GameObject *dependent = nullptr;
				if (event->m_dependentObject) {
					dependent = AddReplicaObject(event->m_dependentObject, event->m_spawnPoint);
					if (dependent) {
						dependent->SetParent(replica);
					}
				}
				m_cutsceneManager->RegisterSpawnedObjects(replica, dependent);
				if (dependent) {
					dependent->Release();
				}
				replica->Release();
			}
			break;

		case CUTSCENE_EVENT_DIALOG:
			{
				/* Get language from globalDict */
				PyObject *gameLogicModule = PyImport_ImportModule("bge.logic");
				std::string lang = "en";
				if (gameLogicModule) {
					PyObject *globalDict = PyObject_GetAttrString(gameLogicModule, "globalDict");
					if (globalDict) {
						PyObject *langObj = PyDict_GetItemString(globalDict, "Language");
						if (langObj && PyUnicode_Check(langObj)) {
							lang = PyUnicode_AsUTF8(langObj);
						}
						Py_DECREF(globalDict);
					}
					Py_DECREF(gameLogicModule);
				}
				PyErr_Clear();

				const std::string &text = GetLocalizedText(event, lang);
				const std::string &overlayScene = event->m_paramBool ? "_dialogue_live" : "_dialogue";
				KX_GetActiveEngine()->ConvertAndAddScene(overlayScene, true);

				if (!event->m_audioPath.empty()) {
					/* TODO: integrate audio playback */
				}
			}
			break;

		case CUTSCENE_EVENT_HIDE_DIALOG:
			KX_GetActiveEngine()->RemoveScene("_dialogue_live");
			KX_GetActiveEngine()->RemoveScene("_dialogue");
			break;

		case CUTSCENE_EVENT_CAMERA_SHOT:
			{
				KX_GameObject *cameraMgr = FindGameObject(m_objectlist, "CutsceneCameraManager");
				if (cameraMgr) {
					EXP_ListValue<KX_PythonComponent> *components = cameraMgr->GetComponents();
					if (components && components->GetCount() > 0) {
						KX_PythonComponent *cameraComp = components->GetValue(0);
						if (cameraComp) {
							PyObject *proxy = cameraComp->GetProxy();
							if (proxy) {
								PyObject_CallMethod(proxy, "start_shot", "i", event->m_paramInt);
								PyErr_Clear();
							}
						}
					}
				}
			}
			break;

		case CUTSCENE_EVENT_LOOK_AT:
			{
				if (event->m_templateObject) {
					KX_GameObject *cameraPivot = FindGameObject(m_objectlist, "PlayerCameraPivot");
					if (cameraPivot) {
						const mt::vec3 &targetPos = event->m_templateObject->NodeGetWorldPosition();
						PyObject *proxy = cameraPivot->GetProxy();
						if (proxy) {
							PyObject *pos = Py_BuildValue("(fff)", targetPos.x, targetPos.y, targetPos.z);
							PyObject_CallMethod(proxy, "lookAt", "O", pos);
							Py_XDECREF(pos);
							PyErr_Clear();
						}
					}
				}
			}
			break;

		case CUTSCENE_EVENT_RESTORE_GAMEPLAY_CAMERA:
			{
				KX_GameObject *cameraMgr = FindGameObject(m_objectlist, "CutsceneCameraManager");
				if (cameraMgr) {
					EXP_ListValue<KX_PythonComponent> *components = cameraMgr->GetComponents();
					if (components && components->GetCount() > 0) {
						KX_PythonComponent *cameraComp = components->GetValue(0);
						if (cameraComp) {
							PyObject *proxy = cameraComp->GetProxy();
							if (proxy) {
								PyObject_CallMethod(proxy, "restore_gameplay_camera", "");
								PyErr_Clear();
							}
						}
					}
				}
			}
			break;

		case CUTSCENE_EVENT_CAMERA_START:
			{
				KX_GameObject *cameraMgr = FindGameObject(m_objectlist, "CutsceneCameraManager");
				if (cameraMgr) {
					EXP_ListValue<KX_PythonComponent> *components = cameraMgr->GetComponents();
					if (components && components->GetCount() > 0) {
						KX_PythonComponent *cameraComp = components->GetValue(0);
						if (cameraComp) {
							PyObject *proxy = cameraComp->GetProxy();
							if (proxy) {
								PyObject_CallMethod(proxy, "start_cutscene", "");
								PyErr_Clear();
							}
						}
					}
				}
			}
			break;

		case CUTSCENE_EVENT_CAMERA_STOP:
			{
				KX_GameObject *cameraMgr = FindGameObject(m_objectlist, "CutsceneCameraManager");
				if (cameraMgr) {
					EXP_ListValue<KX_PythonComponent> *components = cameraMgr->GetComponents();
					if (components && components->GetCount() > 0) {
						KX_PythonComponent *cameraComp = components->GetValue(0);
						if (cameraComp) {
							PyObject *proxy = cameraComp->GetProxy();
							if (proxy) {
								PyObject_CallMethod(proxy, "stop_cutscene", "");
								PyErr_Clear();
							}
						}
					}
				}
			}
			break;

		case CUTSCENE_EVENT_LOCK_PLAYER:
			{
				KX_GameObject *player = FindGameObject(m_objectlist, "Player");
				if (!player) {
					player = FindGameObject(m_objectlist, "PlayerCapsule");
				}
				if (player) {
					EXP_ListValue<KX_PythonComponent> *components = player->GetComponents();
					if (components && components->GetCount() > 0) {
						KX_PythonComponent *playerComp = components->GetValue(0);
						if (playerComp) {
							PyObject *proxy = playerComp->GetProxy();
							if (proxy) {
								PyObject_SetAttrString(proxy, "in_cutscene", Py_True);
								if (!event->m_paramStrA.empty()) {
									PyObject_SetAttrString(proxy, "cutscene_anim",
										PyUnicode_FromString(event->m_paramStrA.c_str()));
								}
								if (event->m_paramBool) {
									KX_GetActiveEngine()->GetCanvas()->SetMouseState(RAS_ICanvas::MOUSE_INVISIBLE);
								}
								PyErr_Clear();
							}
						}
					}
				}
			}
			break;

		case CUTSCENE_EVENT_UNLOCK_PLAYER:
			{
				KX_GameObject *player = FindGameObject(m_objectlist, "Player");
				if (!player) {
					player = FindGameObject(m_objectlist, "PlayerCapsule");
				}
				if (player) {
					EXP_ListValue<KX_PythonComponent> *components = player->GetComponents();
					if (components && components->GetCount() > 0) {
						KX_PythonComponent *playerComp = components->GetValue(0);
						if (playerComp) {
							PyObject *proxy = playerComp->GetProxy();
							if (proxy) {
								PyObject_SetAttrString(proxy, "in_cutscene", Py_False);
								if (event->m_paramBool) {
									KX_GetActiveEngine()->GetCanvas()->SetMouseState(RAS_ICanvas::MOUSE_NORMAL);
								}
								PyErr_Clear();
							}
						}
					}
				}
			}
			break;

		case CUTSCENE_EVENT_PLAYER_ANIM:
			{
				KX_GameObject *player = FindGameObject(m_objectlist, "Player");
				if (!player) {
					player = FindGameObject(m_objectlist, "PlayerCapsule");
				}
				if (player) {
					EXP_ListValue<KX_PythonComponent> *components = player->GetComponents();
					if (components && components->GetCount() > 0) {
						KX_PythonComponent *playerComp = components->GetValue(0);
						if (playerComp) {
							PyObject *proxy = playerComp->GetProxy();
							if (proxy) {
								PyObject_CallMethod(proxy, "Action", "sff",
									event->m_paramStrA.c_str(),
									event->m_paramFloat,
									0.0f);
								PyErr_Clear();
							}
						}
					}
				}
			}
			break;

		case CUTSCENE_EVENT_SHOW_MOUSE:
			KX_GetActiveEngine()->GetCanvas()->SetMouseState(RAS_ICanvas::MOUSE_NORMAL);
			break;

		case CUTSCENE_EVENT_HIDE_MOUSE:
			KX_GetActiveEngine()->GetCanvas()->SetMouseState(RAS_ICanvas::MOUSE_INVISIBLE);
			break;

		case CUTSCENE_EVENT_CHANGE_SCENE:
			if (!event->m_paramStrA.empty()) {
				KX_KetsjiEngine *engine = KX_GetActiveEngine();
				engine->ConvertAndAddScene(event->m_paramStrA, false);
				engine->RemoveScene(GetName());
			}
			break;

		case CUTSCENE_EVENT_WAIT_TIME:
			if (m_cutsceneManager && event->m_paramFloat > 0.0f) {
				m_cutsceneManager->StartWaitTime(m_cutsceneManager->GetTime() + event->m_paramFloat);
			}
			break;

		case CUTSCENE_EVENT_WAIT_TRIGGER:
			if (m_cutsceneManager && !event->m_paramStrA.empty()) {
				m_cutsceneManager->StartWaitTrigger(event->m_paramStrA);
			}
			break;

		case CUTSCENE_EVENT_WAIT_CAMERA_END:
			if (m_cutsceneManager) {
				m_cutsceneManager->StartWaitCameraEnd();
			}
			break;

		default:
			CM_Error("Cutscene event '" << event->m_name << "' has an unknown type");
			break;
		}
	}
}

void KX_Scene::ClearCutsceneSpawnedObjects()
{
	if (!m_cutsceneManager) {
		return;
	}

	const KX_CutsceneManager::SpawnedObjectList spawnedObjects =
		m_cutsceneManager->TakeSpawnedObjects();
	for (const KX_CutsceneManager::SpawnedObjects &spawned : spawnedObjects) {
		if (spawned.m_primary) {
			DelayedRemoveObject(spawned.m_primary);
		}
	}
	RemoveEuthanasyObjects();
}

KX_CutsceneManager *KX_Scene::GetCutsceneManager()
{
	return m_cutsceneManager.get();
}

const KX_CutsceneManager *KX_Scene::GetCutsceneManager() const
{
	return m_cutsceneManager.get();
}

void KX_Scene::SetObstacleSimulation(KX_ObstacleSimulation *obstacleSimulation)
{
	m_obstacleSimulation = obstacleSimulation;
}

#ifdef WITH_PYTHON

void KX_Scene::RunDrawingCallbacks(DrawingCallbackType callbackType, KX_Camera *camera)
{
	PyObject *list = m_drawCallbacks[callbackType];
	if (!list || PyList_GET_SIZE(list) == 0) {
		return;
	}

	if (camera) {
		PyObject *args[1] = {camera->GetProxy()};
		EXP_RunPythonCallBackList(list, args, 0, 1);
	}
	else {
		EXP_RunPythonCallBackList(list, nullptr, 0, 0);
	}
}

void KX_Scene::RunOnRemoveCallbacks()
{
	PyObject *list = m_removeCallbacks;
	if (!list || PyList_GET_SIZE(list) == 0) {
		return;
	}

	PyObject *args[1] = { GetProxy() };
	EXP_RunPythonCallBackList(list, args, 0, 1);
}

PyTypeObject KX_Scene::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_Scene",
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
	0, 0, 0, 0, 0, 0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	0, 0, 0, 0, 0, 0, 0,
	Methods,
	0,
	0,
	&EXP_Value::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_Scene::Methods[] = {
	EXP_PYMETHODTABLE_KEYWORDS(KX_Scene, addObject),
	EXP_PYMETHODTABLE(KX_Scene, end),
	EXP_PYMETHODTABLE(KX_Scene, restart),
	EXP_PYMETHODTABLE(KX_Scene, replace),
	EXP_PYMETHODTABLE(KX_Scene, suspend),
	EXP_PYMETHODTABLE(KX_Scene, resume),
	EXP_PYMETHODTABLE(KX_Scene, play_cutscene),
	EXP_PYMETHODTABLE(KX_Scene, stop_cutscene),
	EXP_PYMETHODTABLE(KX_Scene, restart_cutscene),
	EXP_PYMETHODTABLE(KX_Scene, drawObstacleSimulation),

	// Sict style access.
	EXP_PYMETHODTABLE(KX_Scene, get),

	{nullptr, nullptr} // Sentinel
};
static PyObject *Map_GetItem(PyObject *self_v, PyObject *item)
{
	KX_Scene *self = static_cast<KX_Scene *>EXP_PROXY_REF(self_v);
	const char *attr_str = _PyUnicode_AsString(item);
	PyObject *pyconvert;

	if (!self) {
		PyErr_SetString(PyExc_SystemError, "val = scene[key]: KX_Scene, " EXP_PROXY_ERROR_MSG);
		return nullptr;
	}

	if (!self->m_attrDict) {
		self->m_attrDict = PyDict_New();
	}

	if (self->m_attrDict && (pyconvert = PyDict_GetItem(self->m_attrDict, item))) {

		if (attr_str) {
			PyErr_Clear();
		}
		Py_INCREF(pyconvert);
		return pyconvert;
	}
	else {
		if (attr_str) {
			PyErr_Format(PyExc_KeyError, "value = scene[key]: KX_Scene, key \"%s\" does not exist", attr_str);
		}
		else {
			PyErr_SetString(PyExc_KeyError, "value = scene[key]: KX_Scene, key does not exist");
		}
		return nullptr;
	}

}

static int Map_SetItem(PyObject *self_v, PyObject *key, PyObject *val)
{
	KX_Scene *self = static_cast<KX_Scene *>EXP_PROXY_REF(self_v);
	const char *attr_str = _PyUnicode_AsString(key);
	if (!attr_str) {
		PyErr_Clear();
	}

	if (!self) {
		PyErr_SetString(PyExc_SystemError, "scene[key] = value: KX_Scene, " EXP_PROXY_ERROR_MSG);
		return -1;
	}

	if (!self->m_attrDict) {
		self->m_attrDict = PyDict_New();
	}

	if (!val) {
		// del ob["key"]
		int del = 0;

		if (self->m_attrDict) {
			del |= (PyDict_DelItem(self->m_attrDict, key) == 0) ? 1 : 0;
		}

		if (del == 0) {
			if (attr_str) {
				PyErr_Format(PyExc_KeyError, "scene[key] = value: KX_Scene, key \"%s\" could not be set", attr_str);
			}
			else {
				PyErr_SetString(PyExc_KeyError, "del scene[key]: KX_Scene, key could not be deleted");
			}
			return -1;
		}
		else if (self->m_attrDict) {
			// PyDict_DelItem sets an error when it fails.
			PyErr_Clear();
		}
	}
	else {
		// ob["key"] = value
		int set = 0;

		// Lazy init.
		if (!self->m_attrDict) {
			self->m_attrDict = PyDict_New();
		}

		if (PyDict_SetItem(self->m_attrDict, key, val) == 0) {
			set = 1;
		}
		else {
			PyErr_SetString(PyExc_KeyError, "scene[key] = value: KX_Scene, key not be added to internal dictionary");
		}

		if (set == 0) {
			// Pythons error value.
			return -1;

		}
	}

	// Success.
	return 0;
}

static int Seq_Contains(PyObject *self_v, PyObject *value)
{
	KX_Scene *self = static_cast<KX_Scene *>EXP_PROXY_REF(self_v);

	if (!self) {
		PyErr_SetString(PyExc_SystemError, "val in scene: KX_Scene, " EXP_PROXY_ERROR_MSG);
		return -1;
	}

	if (!self->m_attrDict) {
		self->m_attrDict = PyDict_New();
	}

	if (self->m_attrDict && PyDict_GetItem(self->m_attrDict, value)) {
		return 1;
	}

	return 0;
}

PyMappingMethods KX_Scene::Mapping = {
	(lenfunc)nullptr, // inquiry mp_length
	(binaryfunc)Map_GetItem, // binaryfunc mp_subscript
	(objobjargproc)Map_SetItem, // objobjargproc mp_ass_subscript
};

PySequenceMethods KX_Scene::Sequence = {
	nullptr, // Cant set the len otherwise it can evaluate as false.
	nullptr, // sq_concat
	nullptr, // sq_repeat
	nullptr, // sq_item
	nullptr, // sq_slice
	nullptr, // sq_ass_item
	nullptr, // sq_ass_slice
	(objobjproc)Seq_Contains, // sq_contains
	(binaryfunc)nullptr, // sq_inplace_concat
	(ssizeargfunc)nullptr, // sq_inplace_repeat
};

PyObject *KX_Scene::pyattr_get_name(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	return PyUnicode_FromStdString(self->GetName());
}

PyObject *KX_Scene::pyattr_get_objects(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	return self->GetObjectList()->GetProxy();
}

PyObject *KX_Scene::pyattr_get_objects_inactive(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	return self->GetInactiveList()->GetProxy();
}

PyObject *KX_Scene::pyattr_get_lights(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	return self->GetLightList()->GetProxy();
}

PyObject *KX_Scene::pyattr_get_filter_manager(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	KX_2DFilterManager *filterManager = self->Get2DFilterManager();

	return filterManager->GetProxy();
}

PyObject *KX_Scene::pyattr_get_world(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	KX_WorldInfo *world = self->GetWorldInfo();

	if (world->GetName().empty()) {
		Py_RETURN_NONE;
	}
	else {
		return world->GetProxy();
	}
}

PyObject *KX_Scene::pyattr_get_world_sun(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	KX_GameObject *gameobj = static_cast<KX_GameObject *>(self->GetWorldSun());

	if (gameobj) {
		return gameobj->GetProxy();
	}
	else {
		Py_RETURN_NONE;
	}
}

PyObject *KX_Scene::pyattr_get_texts(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	return self->GetFontList()->GetProxy();
}

PyObject *KX_Scene::pyattr_get_speakers(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
  KX_Scene *self = static_cast<KX_Scene *>(self_v);
  return self->GetSpeakerList()->GetProxy();
}

PyObject *KX_Scene::pyattr_get_cameras(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	return self->GetCameraList()->GetProxy();
}

PyObject *KX_Scene::pyattr_get_active_camera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	KX_Camera *cam = self->GetActiveCamera();
	if (cam) {
		return cam->GetProxy();
	}
	else {
		Py_RETURN_NONE;
	}
}

int KX_Scene::pyattr_set_active_camera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	KX_Camera *camOb;

	if (!ConvertPythonToCamera(self, value, &camOb, false, "scene.active_camera = value: KX_Scene")) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetActiveCamera(camOb);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Scene::pyattr_get_overrideCullingCamera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	KX_Camera *cam = self->GetOverrideCullingCamera();
	if (cam) {
		return cam->GetProxy();
	}
	else {
		Py_RETURN_NONE;
	}
}

int KX_Scene::pyattr_set_overrideCullingCamera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);
	KX_Camera *cam;

	if (!ConvertPythonToCamera(self, value, &cam, true, "scene.active_camera = value: KX_Scene")) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetOverrideCullingCamera(cam);
	return PY_SET_ATTR_SUCCESS;
}

static std::map<const std::string, KX_Scene::DrawingCallbackType> callbacksTable = {
	{"pre_draw", KX_Scene::PRE_DRAW},
	{"pre_draw_setup", KX_Scene::PRE_DRAW_SETUP},
	{"post_draw", KX_Scene::POST_DRAW},
	{"thread_logic_1", KX_Scene::THREAD_LOGIC_1}
};

PyObject *KX_Scene::pyattr_get_drawing_callback(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);

	const DrawingCallbackType type = callbacksTable[attrdef->m_name];
	if (!self->m_drawCallbacks[type]) {
		self->m_drawCallbacks[type] = PyList_New(0);
	}

	Py_INCREF(self->m_drawCallbacks[type]);

	return self->m_drawCallbacks[type];
}

int KX_Scene::pyattr_set_drawing_callback(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);

	if (!PyList_CheckExact(value)) {
		PyErr_SetString(PyExc_ValueError, "Expected a list");
		return PY_SET_ATTR_FAIL;
	}

	const DrawingCallbackType type = callbacksTable[attrdef->m_name];

	Py_XDECREF(self->m_drawCallbacks[type]);

	Py_INCREF(value);
	self->m_drawCallbacks[type] = value;

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Scene::pyattr_get_remove_callback(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);

	if (!self->m_removeCallbacks) {
		self->m_removeCallbacks = PyList_New(0);
	}

	Py_INCREF(self->m_removeCallbacks);

	return self->m_removeCallbacks;
}

int KX_Scene::pyattr_set_remove_callback(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);

	if (!PyList_CheckExact(value)) {
		PyErr_SetString(PyExc_ValueError, "Expected a list");
		return PY_SET_ATTR_FAIL;
	}

	Py_XDECREF(self->m_removeCallbacks);

	Py_INCREF(value);
	self->m_removeCallbacks = value;

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Scene::pyattr_get_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);

	return PyObjectFrom(self->GetGravity());
}

int KX_Scene::pyattr_set_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Scene *self = static_cast<KX_Scene *>(self_v);

	mt::vec3 vec;
	if (!PyVecTo(value, vec)) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetGravity(vec);
	return PY_SET_ATTR_SUCCESS;
}

PyAttributeDef KX_Scene::Attributes[] = {
	EXP_PYATTRIBUTE_RO_FUNCTION("name", KX_Scene, pyattr_get_name),
	EXP_PYATTRIBUTE_RO_FUNCTION("objects", KX_Scene, pyattr_get_objects),
	EXP_PYATTRIBUTE_RO_FUNCTION("objectsInactive", KX_Scene, pyattr_get_objects_inactive),
	EXP_PYATTRIBUTE_RO_FUNCTION("lights", KX_Scene, pyattr_get_lights),
	EXP_PYATTRIBUTE_RO_FUNCTION("texts", KX_Scene, pyattr_get_texts),
    EXP_PYATTRIBUTE_RO_FUNCTION("speakers", KX_Scene, pyattr_get_speakers),
	EXP_PYATTRIBUTE_RO_FUNCTION("cameras", KX_Scene, pyattr_get_cameras),
	EXP_PYATTRIBUTE_RO_FUNCTION("filterManager", KX_Scene, pyattr_get_filter_manager),
	EXP_PYATTRIBUTE_RO_FUNCTION("world", KX_Scene, pyattr_get_world),
	EXP_PYATTRIBUTE_RO_FUNCTION("worldSun", KX_Scene, pyattr_get_world_sun),
	EXP_PYATTRIBUTE_RW_FUNCTION("active_camera", KX_Scene, pyattr_get_active_camera, pyattr_set_active_camera),
	EXP_PYATTRIBUTE_RW_FUNCTION("overrideCullingCamera", KX_Scene, pyattr_get_overrideCullingCamera, pyattr_set_overrideCullingCamera),
	EXP_PYATTRIBUTE_RW_FUNCTION("pre_draw", KX_Scene, pyattr_get_drawing_callback, pyattr_set_drawing_callback),
	EXP_PYATTRIBUTE_RW_FUNCTION("post_draw", KX_Scene, pyattr_get_drawing_callback, pyattr_set_drawing_callback),
	EXP_PYATTRIBUTE_RW_FUNCTION("thread_logic_1", KX_Scene, pyattr_get_drawing_callback, pyattr_set_drawing_callback),
	EXP_PYATTRIBUTE_RW_FUNCTION("pre_draw_setup", KX_Scene, pyattr_get_drawing_callback, pyattr_set_drawing_callback),
	EXP_PYATTRIBUTE_RW_FUNCTION("onRemove", KX_Scene, pyattr_get_remove_callback, pyattr_set_remove_callback),
	EXP_PYATTRIBUTE_RW_FUNCTION("gravity", KX_Scene, pyattr_get_gravity, pyattr_set_gravity),
	EXP_PYATTRIBUTE_BOOL_RO("suspended", KX_Scene, m_suspend),
	EXP_PYATTRIBUTE_BOOL_RO("activityCulling", KX_Scene, m_activityCulling),
	EXP_PYATTRIBUTE_BOOL_RO("dbvt_culling", KX_Scene, m_dbvtCulling),
	EXP_PYATTRIBUTE_NULL // Sentinel
};

EXP_PYMETHODDEF_DOC(KX_Scene, addObject,
                    "addObject(object, other=None, time=0, libpath=None, group=\"Scene\",\n"
                    "          asynchronous=False, load_actions=False, load_scripts=True, verbose=False)\n"
                    "Returns the added object, unless asynchronous LibLoad is triggered (see below).\n"
                    "If object is given by name, it is searched first in this scene's own\n"
                    "inactive layer, then in every other currently running scene's inactive\n"
                    "layer (this also covers objects merged in via LibLoad).\n"
                    "If it still isn't found and libpath is given, that .blend/.range file is\n"
                    "linked (using group/load_actions/load_scripts/verbose the same way as\n"
                    "LibLoad()) and the search is retried before giving up.\n"
                    "By default linking is synchronous and addObject returns the object once\n"
                    "found. If asynchronous=True, addObject instead returns the KX_LibLoadStatus\n"
                    "proxy immediately (like LibLoad()); once loading finishes, call addObject()\n"
                    "again with the same arguments (e.g. from status.onFinish) to get the object.\n")
{
	PyObject *pyob, *pyreference = Py_None;
	KX_GameObject *ob, *reference;

	float time = 0.0f;
	char *libpath = nullptr;
	char *group = (char *)"Scene";
	int asynchronous = 0, load_actions = 0, load_scripts = 1, verbose = 0;

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "O|Ofssiiii:addObject",
	                                   {"object", "other", "time", "libpath", "group", "asynchronous", "load_actions", "load_scripts", "verbose", 0},
	                                   &pyob, &pyreference, &time, &libpath, &group, &asynchronous, &load_actions, &load_scripts, &verbose)) {
		return nullptr;
	}

	if (PyUnicode_Check(pyob)) {
		const std::string name = _PyUnicode_AsString(pyob);
		ob = FindInactiveObjectAcrossScenes(name);

		if (!ob) {
			/* Not converted anywhere yet: maybe it was registered in bmain without being
			 * instantiated in any scene (WM_OT_link_to_libload), in which case it can be
			 * converted straight from there, no libpath/disk read needed. */
			ob = KX_GetActiveEngine()->GetConverter()->FindOrConvertMainObject(name, this);
		}

		if (!ob && libpath) {
			char abs_path[FILE_MAX];
			BLI_strncpy(abs_path, libpath, sizeof(abs_path));
			BLI_path_abs(abs_path, KX_GetMainPath().c_str());

			if (!(BLI_access(abs_path, R_OK) == 0) && BLI_path_extension_check(abs_path, ".range")) {
				BLI_path_extension_replace(abs_path, FILE_MAX, ".rasec");
			}

			BL_Converter *converter = KX_GetActiveEngine()->GetConverter();

			if (!asynchronous && converter->ExistLibrary(abs_path)) {
				PyErr_Format(PyExc_ValueError, "scene.addObject(object, reference, time, libpath): KX_Scene (first argument): library \"%s\" is already loaded but does not contain an inactive object named \"%s\"", abs_path, name.c_str());
				return nullptr;
			}

			short options = 0;
			if (asynchronous) {
				options |= BL_Converter::LIB_LOAD_ASYNC;
			}
			if (load_actions) {
				options |= BL_Converter::LIB_LOAD_LOAD_ACTIONS;
			}
			if (verbose) {
				options |= BL_Converter::LIB_LOAD_VERBOSE;
			}
			if (load_scripts) {
				options |= BL_Converter::LIB_LOAD_LOAD_SCRIPTS;
			}

			char *err_str = nullptr;
			KX_LibLoadStatus *status = converter->LinkBlendFilePath(abs_path, group, this, &err_str, options);
			if (status) {
				if (asynchronous) {
					return status->GetProxy();
				}
				ob = FindInactiveObjectAcrossScenes(name);
			}
			else if (err_str) {
				PyErr_SetString(PyExc_ValueError, err_str);
				return nullptr;
			}
		}

		if (!ob) {
			PyErr_Format(PyExc_ValueError, "scene.addObject(object, reference, time): KX_Scene (first argument): requested name \"%s\" did not match any inactive KX_GameObject in this or any other running scene%s", name.c_str(), libpath ? ", nor in the linked libpath" : "");
			return nullptr;
		}
	}
	else if (!ConvertPythonToGameObject(m_logicmgr, pyob, &ob, false, "scene.addObject(object, reference, time): KX_Scene (first argument)")) {
		return nullptr;
	}
	else if (!m_inactivelist->SearchValue(ob)) {
		PyErr_Format(PyExc_ValueError, "scene.addObject(object, reference, time): KX_Scene (first argument): object must be in an inactive layer");
		return nullptr;
	}

	if (!ConvertPythonToGameObject(m_logicmgr, pyreference, &reference, true, "scene.addObject(object, reference, time): KX_Scene (second argument)")) {
		return nullptr;
	}

	KX_GameObject *replica = AddReplicaObject(ob, reference, time);

	/* Release here because AddReplicaObject AddRef's
	 * the object is added to the scene so we don't want python to own a reference. */
	replica->Release();
	return replica->GetProxy();
}

EXP_PYMETHODDEF_DOC(KX_Scene, end,
                    "end()\n"
                    "Removes this scene from the game.\n")
{

	KX_GetActiveEngine()->RemoveScene(m_sceneName);

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_Scene, restart,
                    "restart()\n"
                    "Restarts this scene.\n")
{
	KX_GetActiveEngine()->ReplaceScene(m_sceneName, m_sceneName);

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_Scene, replace,
                    "replace(newScene)\n"
                    "Replaces this scene with another one.\n"
                    "Return True if the new scene exists and scheduled for replacement, False otherwise.\n")
{
	char *name;

	if (!PyArg_ParseTuple(args, "s:replace", &name)) {
		return nullptr;
	}

	if (KX_GetActiveEngine()->ReplaceScene(m_sceneName, name)) {
		Py_RETURN_TRUE;
	}

	Py_RETURN_FALSE;
}

EXP_PYMETHODDEF_DOC(KX_Scene, suspend,
                    "suspend()\n"
                    "Suspends this scene.\n")
{
	Suspend();

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_Scene, resume,
                    "resume()\n"
                    "Resumes this scene.\n")
{
	Resume();

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_Scene, play_cutscene,
                    "play_cutscene(sequence=0)\n"
                    "Starts the converted native Cutscene sequence and returns True on success.\n")
{
	int sequenceIndex = 0;
	if (!PyArg_ParseTuple(args, "|i:play_cutscene", &sequenceIndex)) {
		return nullptr;
	}

	KX_CutsceneManager *manager = GetCutsceneManager();
	if (!manager) {
		PyErr_SetString(PyExc_RuntimeError, "scene.play_cutscene(): this scene has no converted Cutscene");
		return nullptr;
	}

	if (manager->Start(sequenceIndex)) {
		Py_RETURN_TRUE;
	}

	PyErr_Format(PyExc_ValueError,
	             "scene.play_cutscene(): sequence index %d is out of range",
	             sequenceIndex);
	return nullptr;
}

EXP_PYMETHODDEF_DOC(KX_Scene, stop_cutscene,
                    "stop_cutscene()\n"
                    "Stops the native Cutscene and removes its spawned objects.\n")
{
	if (!GetCutsceneManager()) {
		PyErr_SetString(PyExc_RuntimeError, "scene.stop_cutscene(): this scene has no converted Cutscene");
		return nullptr;
	}

	StopCutscene();
	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_Scene, restart_cutscene,
                    "restart_cutscene()\n"
                    "Restarts the active native Cutscene and removes its spawned objects.\n")
{
	if (!RestartCutscene()) {
		PyErr_SetString(PyExc_RuntimeError,
		                "scene.restart_cutscene(): this scene has no active converted Cutscene");
		return nullptr;
	}

	Py_RETURN_TRUE;
}

EXP_PYMETHODDEF_DOC(KX_Scene, drawObstacleSimulation,
                    "drawObstacleSimulation()\n"
                    "Draw debug visualization of obstacle simulation.\n")
{
	if (GetObstacleSimulation()) {
		GetObstacleSimulation()->DrawObstacles();
	}

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_Scene, get, "")
{
	PyObject *key;
	PyObject *def = Py_None;
	PyObject *ret;

	if (!PyArg_ParseTuple(args, "O|O:get", &key, &def)) {
		return nullptr;
	}

	if (m_attrDict && (ret = PyDict_GetItem(m_attrDict, key))) {
		Py_INCREF(ret);
		return ret;
	}

	Py_INCREF(def);
	return def;
}

bool ConvertPythonToScene(PyObject *value, KX_Scene **scene, bool py_none_ok, const char *error_prefix)
{
	if (value == nullptr) {
		PyErr_Format(PyExc_TypeError, "%s, python pointer nullptr, should never happen", error_prefix);
		*scene = nullptr;
		return false;
	}

	if (value == Py_None) {
		*scene = nullptr;

		if (py_none_ok) {
			return true;
		}
		else {
			PyErr_Format(PyExc_TypeError, "%s, expected KX_Scene or a KX_Scene name, None is invalid", error_prefix);
			return false;
		}
	}

	if (PyUnicode_Check(value)) {
		*scene = KX_GetActiveEngine()->CurrentScenes()->FindValue(std::string(_PyUnicode_AsString(value)));

		if (*scene) {
			return true;
		}
		else {
			PyErr_Format(PyExc_ValueError, "%s, requested name \"%s\" did not match any in game", error_prefix, _PyUnicode_AsString(value));
			return false;
		}
	}

	if (PyObject_TypeCheck(value, &KX_Scene::Type)) {
		*scene = static_cast<KX_Scene *>EXP_PROXY_REF(value);

		// Sets the error.
		if (*scene == nullptr) {
			PyErr_Format(PyExc_SystemError, "%s, " EXP_PROXY_ERROR_MSG, error_prefix);
			return false;
		}

		return true;
	}

	*scene = nullptr;

	if (py_none_ok) {
		PyErr_Format(PyExc_TypeError, "%s, expect a KX_Scene, a string or None", error_prefix);
	}
	else {
		PyErr_Format(PyExc_TypeError, "%s, expect a KX_Scene or a string", error_prefix);
	}

	return false;
}

#endif  // WITH_PYTHON
