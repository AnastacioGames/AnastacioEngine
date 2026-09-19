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
 */

/** \file KX_Scene.h
 *  \ingroup ketsji
 */

#ifndef __KX_SCENE_H__
#define __KX_SCENE_H__


#include "KX_PhysicsEngineEnums.h"
#include "KX_CutsceneManager.h"
#include "KX_TextureRendererManager.h" // For KX_TextureRendererManager::RendererCategory.
#include "KX_PythonComponentManager.h"
#include "KX_KetsjiEngine.h" // For KX_DebugOption.

#include "SG_Node.h"
#include "SG_Frustum.h"
#include "SCA_IScene.h"

#include "RAS_Rasterizer.h" // For RAS_Rasterizer::DrawType.
#include "RAS_DebugDraw.h"
#include "RAS_FramingManager.h"
#include "RAS_Rect.h"

#include "EXP_PyObjectPlus.h"
#include "EXP_Value.h"

#include <memory>
#include <set>
#include <unordered_map>
#include <vector>

template <class T>
class EXP_ListValue;
class EXP_Value;
class SCA_LogicManager;
class SCA_KeyboardManager;
class SCA_TimeEventManager;
class SCA_MouseManager;
class SCA_IInputDevice;
class SCA_JoystickManager;
class KX_NetworkMessageScene;
class KX_NetworkMessageManager;
class KX_2DFilterManager;
class KX_ObstacleSimulation;
class KX_WorldInfo;
class KX_Camera;
class KX_FontObject;
class KX_Speaker;
class KX_GameObject;
class KX_LightObject;
struct KX_ClientObjectInfo;
class BL_SceneConverter;
class SG_Node;
class PHY_IPhysicsEnvironment;
class RAS_Mesh;
class RAS_BoundingBoxManager;
class RAS_BucketManager;
class RAS_MaterialBucket;
class RAS_IMaterial;
class RAS_Rasterizer;
class RAS_OffScreen;
class RAS_2DFilterManager;

struct Scene;
struct TaskPool;

class KX_Scene : public EXP_Value, public SCA_IScene
{
public:
	enum DrawingCallbackType {
		PRE_DRAW = 0,
		POST_DRAW,
		THREAD_LOGIC_1,
		PRE_DRAW_SETUP,
		MAX_DRAW_CALLBACK
	};

	struct AnimationPoolData
	{
		double curtime;
		KX_Scene *scene;
	};

	static SG_Callbacks m_callbacks;

private:
	Py_Header

#ifdef WITH_PYTHON
	PyObject *m_attrDict;
	PyObject *m_removeCallbacks;
	PyObject *m_drawCallbacks[MAX_DRAW_CALLBACK];
#endif

	struct CullingInfo
	{
		int m_layer;
		std::vector<KX_GameObject *>& m_objects;
		KX_Camera *m_cam;
		// this is to avoid updating the LOD in shadowbuff, if this happens it will get the wrong
		// distance from the camera.
		bool m_is_shadowbuf;

		CullingInfo(int layer, std::vector<KX_GameObject *>& objects, KX_Camera *cam, bool is_shadowbuf)
			:m_layer(layer),
			m_objects(objects),
			m_cam(cam),
			m_is_shadowbuf(is_shadowbuf)
		{
		}
	};

	KX_TextureRendererManager *m_rendererManager;
	RAS_BucketManager *m_bucketmanager;

	/// Fase I.2: objects with a GPU particle emitter (KX_GameObject::m_particleBuffer),
	/// cached so UpdateGpuParticleEmitters/RenderCamera don't need to scan every object
	/// every frame. Not exposed to Python -- mirrors the m_animatedlist pattern.
	std::vector<KX_GameObject *> m_gpuParticleObjects;

	/// Objects flagged use_gpu_particle_collider (Object.gameflag2 & OB_GPU_PARTICLE_COLLIDER),
	/// cached the same way as m_gpuParticleObjects. Drives the Screen-Space collision depth
	/// pass (RAS_COLLISION_DEPTH) -- independent of any material's Depth Transparency flag.
	std::vector<KX_GameObject *> m_gpuParticleColliderObjects;

	/// Sun/CSM static shadow cache: objects auto-classified as static (body_type STATIC or
	/// NO_COLLISION, unless use_force_dynamic_shadow is set) go here. Rendered into the
	/// cached static shadow buffer, only re-rendered when this list changes or an explicit
	/// update is requested -- never scanned per frame for classification.
	std::vector<KX_GameObject *> m_staticShadowCasterObjects;

	/// Sun/CSM static shadow cache: everything else (dynamic/rigid body/character/soft body,
	/// or use_force_dynamic_shadow objects). Redrawn on top of the cached static buffer every
	/// frame the light updates.
	std::vector<KX_GameObject *> m_dynamicShadowCasterObjects;

	/// Set whenever m_staticShadowCasterObjects changes (object added/removed at runtime,
	/// e.g. destroyed and replaced by another object) so Sun lights with the static/dynamic
	/// shadow split can invalidate their cached static buffer without per-frame polling.
	bool m_staticShadowCasterListDirty;

	/// Manager used to update all the mesh bounding box.
	RAS_BoundingBoxManager *m_boundingBoxManager;

	std::vector<KX_GameObject *> m_tempObjectList;

	/**
	 * The list of objects which have been removed during the
	 * course of one frame. They are actually destroyed in
	 * LogicEndFrame() via a call to RemoveObject().
	 */
	std::vector<KX_GameObject *> m_euthanasyobjects;

	EXP_ListValue<KX_GameObject> *m_objectlist;
	/// All 'root' parents.
	EXP_ListValue<KX_GameObject> *m_parentlist;
	EXP_ListValue<KX_LightObject> *m_lightlist;
	/// All objects that are not in the active layer.
	EXP_ListValue<KX_GameObject> *m_inactivelist;
	/// All animated objects, no need of EXP_ListValue because the list isn't exposed in python.
	std::vector<KX_GameObject *> m_animatedlist;

	/// The list of cameras for this scene.
	EXP_ListValue<KX_Camera> *m_cameralist;
	/// The list of fonts for this scene.
	EXP_ListValue<KX_FontObject> *m_fontlist;
	/// The list of speakers for this scene.
	EXP_ListValue<KX_Speaker> *m_speakerlist;
	/// The list of culling objects for this scene.
	std::vector<KX_GameObject *> m_cullinglist;
	/// The list of render objects for this scene.
	EXP_ListValue<KX_GameObject> *m_renderlist;

	/**
	 * List of nodes that needs scenegraph update
	 * the Dlist is not object that must be updated
	 * the Qlist is for objects that needs to be rescheduled
	 * for updates after udpate is over (slow parent, bone parent).
	 */
	SG_QList m_sghead;

	/// Various SCA managers used by the scene
	SCA_LogicManager *m_logicmgr;
	SCA_KeyboardManager *m_keyboardmgr;
	SCA_MouseManager *m_mousemgr;
	SCA_TimeEventManager *m_timemgr;

	KX_PythonComponentManager m_componentManager;

	/// Physics engine abstraction.
	PHY_IPhysicsEnvironment *m_physicsEnvironment;

	/// The name of the scene.
	std::string m_sceneName;

	/// Stores the world-settings for a scene.
	KX_WorldInfo *m_worldinfo;

	/// Stores Object used to calculate sun direction in world background.
	KX_LightObject *m_worldSun;
	/// True only when World Sun was created through Scene > Automatic Sun.
	bool m_autoWorldSun;
	/// Avoid warning every frame when an automatic Sun has no active camera.
	bool m_autoWorldSunMissingCameraWarned;
	/// The active camera height on the first valid automatic-Sun update. It
	/// establishes the ground reference without requiring a ground object.
	bool m_autoWorldSunGroundReferenceInitialized;
	float m_autoWorldSunInitialCameraHeight;
	KX_Camera *m_autoWorldSunReferenceCamera;

	/// Scene gravity as authored (World > Weather > Earthquake shakes around
	/// this instead of replacing it), captured on first earthquake update.
	mt::vec3 m_earthquakeBaseGravity;
	bool m_earthquakeBaseGravityInitialized;

	/// Network scene.
	KX_NetworkMessageScene *m_networkScene;

	/// The active camera for the scene.
	KX_Camera *m_activeCamera;
	/// One per-frame reference point for distance-based runtime optimizations.
	/// Until a Player reference exists, it is the active camera world position.
	mt::vec3 m_optimizationReferencePosition;
	/// The active camera for scene culling.
	KX_Camera *m_overrideCullingCamera;

	/** Object counters from the last non-shadow CalculateVisibleMeshes() call
	 * (main camera visibility pass): total objects in the scene's render
	 * list, objects actually tested against the frustum/DBVT, and objects
	 * that came out visible. Used only for the Debug Mode "Culling" counters.
	 */
	int m_lastCullingTotalObjects;
	int m_lastCullingTestedObjects;
	int m_lastCullingVisibleObjects;

	/** Light/shadow counters from the last KX_ShadowRenderer::Render() call for
	 * this scene: total lights in the scene, and how many shadow passes (cascade splits
	 * count as one pass each) were actually rendered this frame. Used only for the Debug
	 * Mode "Lights" counters.
	 */
	int m_lastLightsTotal;
	int m_lastLightsShadowUpdated;
	int m_lastShadowPasses;

	/**
	 * Another temporary variable outstaying its welcome
	 * used in AddReplicaObject to map game objects to their
	 * replicas so pointers can be updated.
	 */
	std::map<SCA_IObject *, SCA_IObject *> m_map_gameobject_to_replica;

	/**
	 * Another temporary variable outstaying its welcome
	 * used in AddReplicaObject to keep a record of all added
	 * objects. Logic can only be updated when all objects
	 * have been updated. This stores a list of the new objects.
	 */
	std::vector<KX_GameObject *> m_logicHierarchicalGameObjects;

	/**
	 * This temporary variable will contain the list of
	 * object that can be added during group instantiation.
	 * objects outside this list will not be added (can
	 * happen with children that are outside the group).
	 * Used in AddReplicaObject. If the list is empty, it
	 * means don't care.
	 */
	std::set<KX_GameObject *> m_groupGameObjects;

	/// The execution priority of replicated object actuators.
	int m_ueberExecutionPriority;

	/**
	 * Activity 'bubble' settings :
	 * Suspend (freeze) the entire scene.
	 */
	bool m_suspend;
	double m_suspendedDelta;

	/// Toggle to enable or disable object activity culling.
	bool m_activityCulling;

	/// Toggle to enable or disable culling via DBVT broadphase of Bullet.
	bool m_dbvtCulling;

	/// Occlusion culling resolution.
	int m_dbvtOcclusionRes;

	/// The framing settings used by this scene
	RAS_FrameSettings m_frameSettings;

	/**
	 * This scenes viewport into the game engine
	 * canvas.Maintained externally, initially [0,0] -> [0,0]
	 */
	RAS_Rect m_viewport;

	/// Debug drawing registering.
	RAS_DebugDraw m_debugDraw;

	/// Visibility testing functions.
	static void PhysicsCullingCallback(KX_ClientObjectInfo *objectInfo, void *cullingInfo);

	Scene *m_blenderScene;

	/// light scatter need a screen sun position, so we need to calculate before render 2DFilters
	bool m_useLightScattering;
	KX_2DFilterManager *m_filterManager;

	KX_ObstacleSimulation *m_obstacleSimulation;
	std::unique_ptr<KX_CutsceneManager> m_cutsceneManager;
	/** Events crossed by the Cutscene clock, retained until the native action
	 * dispatcher consumes them. Keeping this queue on the owning scene prevents
	 * a frame update from silently losing an authored event. */
	KX_CutsceneManager::DispatchedEvents m_pendingCutsceneEvents;

	AnimationPoolData m_animationPoolData;
	TaskPool *m_animationPool;
	double m_previousAnimTime;
	/// Which animated objects need a deformer (skinning) update this frame, filled by UpdateAnimations()
	/// on the main thread before dispatching, then read (never inserted into) by the parallel pose pass
	/// and consumed by UpdateAnimationDeformers(). See KX_Scene.cpp for why this split is thread-safe.
	std::unordered_map<KX_GameObject *, bool> m_animNeedsUpdateCache;

	/// Animation task-pool callbacks. Static members (not free functions) because they need access to
	/// m_animNeedsUpdateCache above. See KX_Scene.cpp for the pose/deform split this implements.
	static void UpdateAnimPoseTask(TaskPool *pool, void *taskdata, int threadid);
	static void UpdateAnimDeformTask(TaskPool *pool, void *taskdata, int threadid);

	/// LOD Hysteresis settings.
	bool m_isActivedHysteresis;
	int m_lodHysteresisValue;

	/// Sound settings.
	int m_audio3d_update; /* Audio 3D update frequency. */

	int m_audio3d_frames; /* only used to calculate time in frames for 3D Audio. */

	void RemoveNodeDestructObject(KX_GameObject *gameobj);
	void RemoveObject(KX_GameObject *gameobj);
	void RemoveDupliGroup(KX_GameObject *gameobj);
	bool NewRemoveObject(KX_GameObject *gameobj);

	/** Look up an inactive-layer object by name, first in this scene then in every
	 * other currently running scene's inactive list (covers objects merged in via LibLoad,
	 * whose names are never registered in this scene's own m_logicmgr). */
	KX_GameObject *FindInactiveObjectAcrossScenes(const std::string& name);

public:
	KX_Scene(SCA_IInputDevice *inputDevice,
	         const std::string& scenename,
	         Scene *scene,
			 RAS_ICanvas *canvas,
			 KX_NetworkMessageManager *messageManager);
	virtual ~KX_Scene();

	RAS_BucketManager *GetBucketManager() const;
	KX_TextureRendererManager *GetTextureRendererManager() const;
	RAS_BoundingBoxManager *GetBoundingBoxManager() const;
	void RenderBuckets(const std::vector<KX_GameObject *>& objects, RAS_Rasterizer::DrawType drawingMode,
	                   const mt::mat3x4& cameratransform, RAS_Rasterizer *rasty, RAS_OffScreen *offScreen);
	void RenderTextureRenderers(KX_TextureRendererManager::RendererCategory category, RAS_Rasterizer *rasty, RAS_OffScreen *offScreen,
	                            KX_Camera *sceneCamera, const RAS_Rect& viewport, const RAS_Rect& area);

	/// Update all transforms according to the scenegraph.
	static bool KX_ScenegraphUpdateFunc(SG_Node *node, void *gameobj, void *scene);
	static bool KX_ScenegraphRescheduleFunc(SG_Node *node, void *gameobj, void *scene);
	/// SceneGraph transformation update.
	void UpdateParents();

	void DupliGroupRecurse(KX_GameObject *groupobj, int level);
	bool IsObjectInGroup(KX_GameObject *gameobj) const;
	void AddObjectDebugProperties(KX_GameObject *gameobj);
	KX_GameObject *AddReplicaObject(KX_GameObject *gameobj, KX_GameObject *locationobj, float lifespan = 0.0f);
	KX_GameObject *AddNodeReplicaObject(SG_Node *node, KX_GameObject *gameobj);

	/// Initialize KX_Speakers with start init enabled
	void StartInitSpeakers();

	/// Add an object to remove.
	void DelayedRemoveObject(KX_GameObject *gameobj);
	/// Effectivly remove object added with DelayedRemoveObject
	void RemoveEuthanasyObjects();

	void AddAnimatedObject(KX_GameObject *gameobj);
	void AddCullingObject(KX_GameObject *gameobj);
	void RemoveCullingObject(KX_GameObject *gameobj);

	/**
	 * \section Logic stuff
	 * Initiate an update of the logic system.
	 */
	void LogicBeginFrame(double curtime, double framestep);
	void LogicUpdateFrame(double curtime);
	bool UpdateAnimations(double curtime, bool restrict);
	void UpdateAnimationDeformers();

	void LogicEndFrame();

	EXP_ListValue<KX_GameObject> *GetObjectList() const;
	EXP_ListValue<KX_GameObject> *GetInactiveList() const;
	EXP_ListValue<KX_GameObject> *GetRootParentList() const;
	EXP_ListValue<KX_LightObject> *GetLightList() const;
	EXP_ListValue<KX_Camera> *GetCameraList() const;
	EXP_ListValue<KX_FontObject> *GetFontList() const;
	EXP_ListValue<KX_Speaker> *GetSpeakerList() const;
	EXP_ListValue<KX_GameObject> *GetRenderList() const;

	SCA_LogicManager *GetLogicManager() const;
	SCA_TimeEventManager *GetTimeEventManager() const;
	KX_PythonComponentManager& GetPythonComponentManager();

	/// Return the currently active camera.
	KX_Camera *GetActiveCamera();
	/// Position shared by runtime systems that optimize relative to the player.
	const mt::vec3& GetOptimizationReferencePosition() const;
	/// Refresh the reference after physics/camera movement. Uses the active camera for now.
	void UpdateOptimizationReference();

	/// Object counters from the last main-camera (non-shadow) culling pass. See m_lastCullingTotalObjects.
	int GetLastCullingTotalObjects() const;
	int GetLastCullingTestedObjects() const;
	int GetLastCullingVisibleObjects() const;

	/// Light/shadow counters from the last KX_ShadowRenderer::Render() call. See m_lastLightsTotal.
	int GetLastLightsTotal() const;
	int GetLastLightsShadowUpdated() const;
	int GetLastShadowPasses() const;
	void SetLastLightsCounters(int total, int shadowUpdated, int shadowPasses);

	/**
	 * Set this camera to be the active camera in the scene. If the
	 * camera is not present in the camera list, it will be added
	 */
	void SetActiveCamera(KX_Camera *camera);

	KX_Camera *GetOverrideCullingCamera() const;
	void SetOverrideCullingCamera(KX_Camera *cam);

	/**
	 * Move this camera to the end of the list so that it is rendered last.
	 * If the camera is not on the list, it will be added
	 */
	void SetCameraOnTop(KX_Camera *camera);

	/// Set the framing options for this scene.
	void SetFramingType(const RAS_FrameSettings& frameSettings);

	/**
	 * Return a const reference to the framing
	 * type set by the above call.
	 * The contents are not guaranteed to be sensible
	 * if you don't call the above function.
	 */
	const RAS_FrameSettings &GetFramingType() const;

	/**
	 * \section Accessors to different scenes of this scene
	 */
	void SetNetworkMessageScene(KX_NetworkMessageScene *netScene);
	KX_NetworkMessageScene *GetNetworkMessageScene() const;

	void SetWorldInfo(KX_WorldInfo *wi);
	KX_WorldInfo *GetWorldInfo() const;

	void SetWorldSun(KX_LightObject *light);
	KX_LightObject *GetWorldSun() const;
	void SetAutoWorldSun(bool enabled);
	/// Place and orient the generated World Sun from the active camera and World sun_hour.
	void UpdateAutoWorldSun();

	/// Shake scene gravity from World > Weather > Earthquake (curtime in seconds).
	void UpdateEarthquake(double curtime);

	std::vector<KX_GameObject *> CalculateVisibleMeshes(KX_Camera *cam, RAS_Rasterizer::StereoEye eye, int layer, bool is_shadowbuf);
	std::vector<KX_GameObject *> CalculateVisibleMeshes(KX_Camera *cam, const SG_Frustum& frustum, int layer, bool is_shadowbuf);

	RAS_DebugDraw& GetDebugDraw();
	/// \section Debug draw.
	void DrawDebug(const std::vector<KX_GameObject *>& objects,
			KX_DebugOption showBoundingBox, KX_DebugOption showArmatures);
	void RenderDebugProperties(RAS_DebugDraw& debugDraw, int xindent, int ysize, int& xcoord, int& ycoord, unsigned short propsMax);
	void RenderDebugPropertiesImGui(int sceneIndex);
	void FlushDebugDraw(RAS_Rasterizer *rasty, RAS_ICanvas *canvas);

	/// Replicate the logic bricks associated to this object.
	void ReplicateLogic(KX_GameObject *newobj);

	// Suspend the entire scene.
	void Suspend();

	// Resume a suspended scene.
	void Resume();

	/// Update the mesh for objects based on level of detail settings
	void UpdateObjectLods(KX_Camera *cam, const std::vector<KX_GameObject *>& objects);

	// LoD Hysteresis functions
	void SetLodHysteresis(bool active);
	bool IsActivedLodHysteresis() const;
	void SetLodHysteresisValue(int hysteresisvalue);
	int GetLodHysteresisValue() const;

	/// Fase I.2: steps every registered object's GPU particle emitter by one frame. Called
	/// once per frame from KX_KetsjiEngine::NextFrame, after UpdateParents() so emitters read
	/// a fresh world transform -- not per camera, see GetGpuParticleObjects() for the draw side.
	void UpdateGpuParticleEmitters(float deltaTime);
	/// Registers/unregisters an object with GetParticleBuffer() != nullptr for per-frame
	/// update/draw. Called from scene conversion, object duplication and object removal.
	void AddGpuParticleObject(KX_GameObject *gameobj);
	void RemoveGpuParticleObject(KX_GameObject *gameobj);
	const std::vector<KX_GameObject *> &GetGpuParticleObjects() const;

	/// Same as AddGpuParticleObject/RemoveGpuParticleObject/GetGpuParticleObjects, but for
	/// objects flagged use_gpu_particle_collider (Screen-Space collision depth pass).
	void AddGpuParticleColliderObject(KX_GameObject *gameobj);
	void RemoveGpuParticleColliderObject(KX_GameObject *gameobj);
	const std::vector<KX_GameObject *> &GetGpuParticleColliderObjects() const;

	/// Sun/CSM static shadow cache lists. Add/Remove set m_staticShadowCasterListDirty on the
	/// static list so Sun lights know to invalidate their cached static shadow buffer.
	void AddStaticShadowCasterObject(KX_GameObject *gameobj);
	void RemoveStaticShadowCasterObject(KX_GameObject *gameobj);
	const std::vector<KX_GameObject *> &GetStaticShadowCasterObjects() const;
	void AddDynamicShadowCasterObject(KX_GameObject *gameobj);
	void RemoveDynamicShadowCasterObject(KX_GameObject *gameobj);
	const std::vector<KX_GameObject *> &GetDynamicShadowCasterObjects() const;

	/// True if the static shadow caster list changed since the last ClearStaticShadowCasterListDirty().
	bool IsStaticShadowCasterListDirty() const;
	void ClearStaticShadowCasterListDirty();

	/// Update the activity culling of objects in this scene, if needed.
	void UpdateObjectActivity();
	/// Enable/disable activity culling.
	void SetActivityCulling(bool b);

	bool IsSuspended() const;

	/// Use of DBVT tree for camera culling
	void SetDbvtCulling(bool b);
	bool GetDbvtCulling() const;
	void SetDbvtOcclusionRes(int i);
	int GetDbvtOcclusionRes() const;

	void SetSceneConverter(BL_SceneConverter *sceneConverter);

	PHY_IPhysicsEnvironment *GetPhysicsEnvironment() const;
	void SetPhysicsEnvironment(PHY_IPhysicsEnvironment *physEnv);

	void SetGravity(const mt::vec3& gravity);
	mt::vec3 GetGravity() const;

	/**
	 * Sets the difference between the local time of the scene (when it
	 * was running and not suspended) and the "curtime"
	 */
	void SetSuspendedDelta(double suspendeddelta);
	/**
	 * Returns the difference between the local time of the scene (when it
	 * was running and not suspended) and the "curtime"
	 */
	double GetSuspendedDelta() const;

	/// Returns the Blender scene this was made from.
	Scene *GetBlenderScene() const;

	bool MergeScene(KX_Scene *other);

	/// 2D Filters.
	bool GetUseLightScatter() const;
	void SetUseLightScatter(bool enable);
	KX_2DFilterManager *Get2DFilterManager() const;
	RAS_OffScreen *Render2DFilters(RAS_Rasterizer *rasty, RAS_ICanvas *canvas, RAS_OffScreen *inputofs, RAS_OffScreen *targetofs, const float (&sun_screen_pos)[2]);

	KX_ObstacleSimulation *GetObstacleSimulation();
	void SetObstacleSimulation(KX_ObstacleSimulation *obstacleSimulation);

	void SetCutsceneManager(std::unique_ptr<KX_CutsceneManager> cutsceneManager);
	void StopCutscene();
	bool RestartCutscene();
	/** Advance the scene-owned Cutscene clock and retain crossed events. */
	void UpdateCutscene(double time);
	/** Transfer events accumulated by UpdateCutscene() to the native dispatcher. */
	KX_CutsceneManager::DispatchedEvents TakePendingCutsceneEvents();
	/** Instantiate the currently pending native Cutscene events. */
	void DispatchCutsceneEvents();
	KX_CutsceneManager *GetCutsceneManager();
	const KX_CutsceneManager *GetCutsceneManager() const;

	/** Remove runtime objects created by Cutscene before changing playback state. */
	void ClearCutsceneSpawnedObjects();

	virtual std::string GetName();
	virtual void SetName(const std::string& name);

#ifdef WITH_PYTHON

	EXP_PYMETHOD_DOC(KX_Scene, addObject);
	EXP_PYMETHOD_DOC(KX_Scene, end);
	EXP_PYMETHOD_DOC(KX_Scene, restart);
	EXP_PYMETHOD_DOC(KX_Scene, replace);
	EXP_PYMETHOD_DOC(KX_Scene, suspend);
	EXP_PYMETHOD_DOC(KX_Scene, resume);
	EXP_PYMETHOD_DOC(KX_Scene, play_cutscene);
	EXP_PYMETHOD_DOC(KX_Scene, stop_cutscene);
	EXP_PYMETHOD_DOC(KX_Scene, restart_cutscene);
	EXP_PYMETHOD_DOC(KX_Scene, get);
	EXP_PYMETHOD_DOC(KX_Scene, drawObstacleSimulation);

	// Attributes.
	static PyObject *pyattr_get_name(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_objects(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_objects_inactive(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_lights(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_texts(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_speakers(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_cameras(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_filter_manager(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_world(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_world_sun(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_active_camera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_active_camera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_overrideCullingCamera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_overrideCullingCamera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_drawing_callback(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_drawing_callback(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_remove_callback(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_remove_callback(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);

	// getitem/setitem
	static PyMappingMethods Mapping;
	static PySequenceMethods Sequence;

	/// Run the registered python drawing functions.
	void RunDrawingCallbacks(DrawingCallbackType callbackType, KX_Camera *camera);

	// Run the registered python callbacks when the scene is removed.
	void RunOnRemoveCallbacks();
#endif
};

#ifdef WITH_PYTHON
bool ConvertPythonToScene(PyObject *value, KX_Scene **scene, bool py_none_ok, const char *error_prefix);
#endif

#endif  // __KX_SCENE_H__
