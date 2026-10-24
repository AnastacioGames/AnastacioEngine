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
 * Ketsji scene: cutscene playback, cutscene paths and Trace Rail.
 */

/** \file gameengine/Ketsji/KX_SceneCutscene.cpp
 *  \ingroup ketsji
 */

#ifdef _MSC_VER
#  pragma warning (disable:4786)
#endif

#include <algorithm>
#include <cfloat>
#include <cmath>

#include "CM_WorkCounters.h"
#include "KX_Scene.h"
#include "KX_RainAura.h"
#include "KX_RainSurfaceMask.h"
#include "KX_RainShelterMap.h"
#include "KX_RainLightning.h"
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
#include "KX_NetworkManager.h"
#include "SCA_KeyboardManager.h"
#include "SCA_MouseManager.h"
#include "SCA_ActuatorEventManager.h"
#include "SCA_BasicEventManager.h"
#include "KX_Camera.h"
#include "KX_WorldInfo.h"
#include "KX_Speaker.h"
#include "KX_AudioManager.h"
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
#include "RAS_2DFilter.h"
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
#include "DNA_python_component_types.h"
#include "BLI_listbase.h"
#include "DNA_world_types.h"
#include "DNA_object_types.h"
#include "DNA_node_types.h"
#include "BKE_scene.h" // SETLOOPER
#include "BKE_node.h" // SH_NODE_WORLD_BLOOM_FX, SH_NODE_WORLD_SSR_FX
extern "C" {
#include "BKE_idprop.h"
}
#include "GPU_material.h"

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
#include "RAS_ILightObject.h"

#include "BLI_task.h"
#include "BLI_path_util.h"
#include "BLI_fileops.h"
#include "BLI_string.h"
#ifdef WIN32
#  include "BLI_winstuff.h"
#endif

#include "CM_Message.h"
#include "CM_Trace.h"

#include <chrono>
#include <mutex>
#include <unordered_set>
#include "CM_List.h"
#include "RAS_ParticleBuffer.h"


void KX_Scene::SetCutsceneManager(std::unique_ptr<KX_CutsceneManager> cutsceneManager)
{
	ClearCutsceneSpawnedObjects();
	if (m_cutsceneManager) {
		m_cutsceneManager->Stop();
	}
	m_cutsceneManager = std::move(cutsceneManager);
	m_pendingCutsceneEvents.clear();
	m_cutscenePaths.clear();
}

void KX_Scene::StopCutscene()
{
	ClearCutsceneSpawnedObjects();
	if (m_cutsceneManager) {
		m_cutsceneManager->Stop();
	}
	m_pendingCutsceneEvents.clear();
	m_cutscenePaths.clear();
}

bool KX_Scene::RestartCutscene()
{
	if (!m_cutsceneManager) {
		return false;
	}
	ClearCutsceneSpawnedObjects();
	m_pendingCutsceneEvents.clear();
	m_cutscenePaths.clear();
	return m_cutsceneManager->Restart();
}

void KX_Scene::UpdateCutscene(double time)
{
	if (!m_cutsceneManager) {
		return;
	}

	/* Wait Trigger is released by a message sent with the trigger name as subject
	 * (Send Message actuator or Python), or by scene.release_cutscene_trigger(). */
	if (m_cutsceneManager->GetWaitType() == KX_CutsceneManager::WAIT_TRIGGER && m_networkScene) {
		const std::string triggerName = m_cutsceneManager->GetWaitTriggerName();
		if (!m_networkScene->FindMessages("", triggerName).empty()) {
			m_cutsceneManager->ReleaseTrigger(triggerName);
		}
	}

	KX_CutsceneManager::DispatchedEvents dispatchedEvents = m_cutsceneManager->Update(time);
	m_pendingCutsceneEvents.insert(
		m_pendingCutsceneEvents.end(), dispatchedEvents.begin(), dispatchedEvents.end());

	if (!m_cutscenePaths.empty()) {
		UpdateCutscenePaths(m_cutsceneManager->GetTime());
		if (m_cutscenePaths.empty() &&
		    m_cutsceneManager->GetWaitType() == KX_CutsceneManager::WAIT_CAMERA_END) {
			m_cutsceneManager->ClearWait();
		}
	}
}

/* Position along a polyline at a fraction of its total length (constant speed). */
static void EvaluateCutscenePath(const std::vector<mt::vec3> &points, float fraction,
                                 mt::vec3 &position, mt::vec3 &direction)
{
	float total = 0.0f;
	for (std::size_t i = 1; i < points.size(); ++i) {
		total += (points[i] - points[i - 1]).Length();
	}

	float remaining = total * fraction;
	for (std::size_t i = 1; i < points.size(); ++i) {
		const mt::vec3 segment = points[i] - points[i - 1];
		const float length = segment.Length();
		if (length <= 0.0f) {
			continue;
		}
		if (remaining <= length || i == points.size() - 1) {
			const float t = std::min(remaining / length, 1.0f);
			position = points[i - 1] + segment * t;
			direction = segment / length;
			return;
		}
		remaining -= length;
	}
	position = points.back();
	direction = mt::zero3;
}

void KX_Scene::StartTraceRail(KX_GameObject *camera, KX_GameObject *curve, std::vector<mt::vec3> points, double seconds,
                              bool reverse, const std::string& start, const std::string& wait)
{
	TraceRail& rail = m_traceRail;
	rail = TraceRail();
	for (std::size_t i = 1; i < points.size(); ++i) {
		rail.m_length += (points[i] - points[i - 1]).Length();
	}
	rail.m_camera = camera;
	rail.m_curve = curve;
	rail.m_points = std::move(points);
	rail.m_seconds = std::max(seconds, 1.0);
	rail.m_reverse = reverse;
	// Wait: "KEY", "seconds" or "KEY+seconds".
	const std::size_t plus = wait.find('+');
	const std::string key = wait.substr(0, plus);
	const bool number = !key.empty() && key.find_first_not_of("0123456789.,") == std::string::npos;
	if (number) {
		rail.m_waitSeconds = atof(key.c_str());
	}
	else {
		rail.m_waitKey = key;
		if (plus != std::string::npos) {
			rail.m_waitSeconds = atof(wait.c_str() + plus + 1);
		}
	}
	rail.m_startRule = start;
	// VSync would show every sector at the refresh period; measure the real frame cost instead.
	KX_GetActiveEngine()->GetCanvas()->SetSwapControl(RAS_ICanvas::VSYNC_OFF);
	CM_TraceEvent("rail_start", "\"scene\":" + CM_TraceStr(GetName()) + ",\"camera\":" + CM_TraceStr(camera->GetName()) +
	              ",\"curve\":" + CM_TraceStr(curve->GetName()) + ",\"seconds\":" + std::to_string(rail.m_seconds) +
	              ",\"length\":" + std::to_string(rail.m_length));
}

/// The object of a CheckPoint component with "Finish Line" on (group instances carry the original's components).
static bool IsFinishLine(KX_GameObject *gameobj)
{
	const Object *ob = gameobj->GetBlenderObject();
	if (!ob) {
		return false;
	}
	LISTBASE_FOREACH (const PythonComponent *, component, &ob->components) {
		if (!STREQ(component->name, "CheckPoint")) {
			continue;
		}
		LISTBASE_FOREACH (const PythonComponentProperty *, prop, &component->properties) {
			if (STREQ(prop->name, "Finish Line") && prop->type == CPROP_TYPE_BOOLEAN && prop->boolval) {
				return true;
			}
		}
	}
	return false;
}

void KX_Scene::StartTraceRailOrigin()
{
	TraceRail& rail = m_traceRail;
	KX_GameObject *start = nullptr;
	if (rail.m_startRule != "none") {
		for (KX_GameObject *gameobj : *m_objectlist) {
			if ((rail.m_startRule == "auto") ? IsFinishLine(gameobj) : gameobj->GetName() == rail.m_startRule) {
				start = gameobj;
				break;
			}
		}
	}
	std::vector<mt::vec3>& points = rail.m_points;
	const bool closed = (points.front() - points.back()).LengthSquared() < 1e-6f;
	if (start && closed) {
		// Rotate the loop so it begins at the sample nearest to the start object.
		const mt::mat3x4 curveTransform = rail.m_curve->NodeGetWorldTransform();
		const mt::vec3 target = start->NodeGetWorldPosition();
		points.pop_back();
		std::size_t nearest = 0;
		float best = FLT_MAX;
		for (std::size_t i = 0; i < points.size(); ++i) {
			const float d = (curveTransform * points[i] - target).LengthSquared();
			if (d < best) {
				best = d;
				nearest = i;
			}
		}
		std::rotate(points.begin(), points.begin() + nearest, points.end());
		points.push_back(points.front());
	}
	// Reversing a closed loop keeps its starting point.
	if (rail.m_reverse) {
		std::reverse(points.begin(), points.end());
	}
	CM_TraceEvent("rail_origin", "\"start\":" + CM_TraceStr(start ? start->GetName() : "") + ",\"rule\":" +
	              CM_TraceStr(rail.m_startRule) + ",\"closed\":" + (closed ? "true" : "false") + ",\"reverse\":" +
	              (rail.m_reverse ? "true" : "false"));
}

/// True when there is no key, or range.logic.globalDict[key] is truthy.
static bool TraceRailKeyTrue(const std::string& key)
{
	if (key.empty()) {
		return true;
	}
#ifdef WITH_PYTHON
	PyObject *gameLogic = PyImport_ImportModule("GameLogic");
	if (!gameLogic) {
		PyErr_Clear();
		return false;
	}
	bool result = false;
	PyObject *globalDict = PyDict_GetItemString(PyModule_GetDict(gameLogic), "globalDict");
	if (globalDict && PyDict_Check(globalDict)) {
		PyObject *value = PyDict_GetItemString(globalDict, key.c_str());
		result = value && PyObject_IsTrue(value) == 1;
	}
	Py_DECREF(gameLogic);
	PyErr_Clear();
	return result;
#else
	return true;
#endif
}

void KX_Scene::UpdateTraceRail()
{
	TraceRail& rail = m_traceRail;
	if (!rail.m_camera || rail.m_done) {
		return;
	}
	if (!m_objectlist->SearchValue(rail.m_camera) || !m_objectlist->SearchValue(rail.m_curve) ||
	    rail.m_points.size() < 2 || rail.m_length <= 0.0f)
	{
		rail.m_done = true;
		CM_TraceEvent("rail_end", "\"scene\":" + CM_TraceStr(GetName()) + ",\"reason\":\"lost\"");
		return;
	}
	if (!rail.m_started) {
		rail.m_started = true;
		StartTraceRailOrigin();
	}

	// Real time, not logic time: the camera keeps a constant speed even when frames are slow.
	const double now = std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
	// Hold at the start until the globalDict key is true (e.g. CONTAGEM_321 at the race GO) and the extra
	// seconds pass, so the rail skips the load and countdown hitches.
	if (!rail.m_moving) {
		if (rail.m_waitFrom < 0.0 && TraceRailKeyTrue(rail.m_waitKey)) {
			rail.m_waitFrom = now;
		}
		if (rail.m_waitFrom >= 0.0 && now - rail.m_waitFrom >= rail.m_waitSeconds) {
			rail.m_moving = true;
			rail.m_start = now;
			CM_TraceEvent("rail_go", "\"scene\":" + CM_TraceStr(GetName()));
		}
	}
	if (rail.m_start < 0.0 || !rail.m_moving) {
		rail.m_start = now;
	}
	const float fraction = std::min(float((now - rail.m_start) / rail.m_seconds), 1.0f);

	mt::vec3 local, direction;
	EvaluateCutscenePath(rail.m_points, fraction, local, direction);
	const mt::mat3x4 curveTransform = rail.m_curve->NodeGetWorldTransform();
	const mt::vec3 position = curveTransform * local;

	// Target look: average direction to points 4 to 16 m ahead, so the corners of the sampled
	// polyline do not turn the camera in steps.
	mt::vec3 target = mt::zero3;
	for (const float meters : {4.0f, 8.0f, 12.0f, 16.0f}) {
		mt::vec3 aheadLocal, aheadDirection;
		EvaluateCutscenePath(rail.m_points, std::min(fraction + meters / rail.m_length, 1.0f), aheadLocal, aheadDirection);
		const mt::vec3 toAhead = curveTransform * aheadLocal - position;
		if (toAhead.LengthSquared() > 1e-6f) {
			target += toAhead.Normalized();
		}
	}
	if (target.LengthSquared() < 1e-6f) {
		target = rail.m_curve->NodeGetWorldOrientation() * direction;
	}

	// Ease the look toward the target (time constant 0.15 s), independent of the frame rate.
	const double dt = (rail.m_last < 0.0) ? 0.0 : now - rail.m_last;
	rail.m_last = now;
	if (rail.m_forward.LengthSquared() < 1e-6f || dt <= 0.0) {
		rail.m_forward = target;
	}
	else if (target.LengthSquared() > 1e-6f) {
		const float blend = 1.0f - (float)std::exp(-dt / 0.15);
		rail.m_forward = rail.m_forward.Normalized() + (target.Normalized() - rail.m_forward.Normalized()) * blend;
	}
	const mt::vec3 forward = rail.m_forward;

	rail.m_camera->NodeSetWorldPosition(position);
	if (forward.LengthSquared() > 1e-8f) {
		const mt::vec3 zAxis = -forward.Normalized();
		mt::vec3 xAxis = mt::cross(mt::axisZ3, zAxis);
		if (xAxis.LengthSquared() > 1e-6f) {
			xAxis.Normalize();
			rail.m_camera->NodeSetGlobalOrientation(mt::mat3(xAxis, mt::cross(zAxis, xAxis), zAxis));
		}
	}
	rail.m_camera->NodeUpdate();
	if (rail.m_camera->GetGameObjectType() == SCA_IObject::OBJ_CAMERA && GetActiveCamera() != rail.m_camera) {
		SetActiveCamera(static_cast<KX_Camera *>(rail.m_camera));
	}
	// Split screen: cameras with a viewport are drawn instead of the active one; keep only the rail's.
	for (KX_Camera *cam : *GetCameraList()) {
		if (cam != rail.m_camera && cam->UseViewport()) {
			cam->EnableViewport(false);
		}
	}

	// Where the camera looks (its -Z), to check it faces the way it moves.
	const mt::vec3 look = -rail.m_camera->NodeGetWorldOrientation().GetColumn(2);
	char fields[200];
	snprintf(fields, sizeof(fields),
	         "\"p\":%.5f,\"x\":%.2f,\"y\":%.2f,\"z\":%.2f,\"lx\":%.3f,\"ly\":%.3f,\"lz\":%.3f", fraction,
	         position.x, position.y, position.z, look.x, look.y, look.z);
	if (rail.m_moving) {
		CM_TraceEvent("rail", "\"scene\":" + CM_TraceStr(GetName()) + "," + fields);
	}

	if (fraction >= 1.0f) {
		rail.m_done = true;
		CM_TraceEvent("rail_end", "\"scene\":" + CM_TraceStr(GetName()) + ",\"reason\":\"finished\"");
		KX_GetActiveEngine()->RequestExit(KX_ExitInfo::QUIT_GAME);
	}
}

void KX_Scene::UpdateCutscenePaths(double time)
{
	for (auto it = m_cutscenePaths.begin(); it != m_cutscenePaths.end();) {
		const KX_CutsceneManager::Event *event = it->m_event;
		KX_GameObject *object = event->m_templateObject;
		KX_GameObject *curve = event->m_spawnPoint;
		if (!m_objectlist->SearchValue(object) || !m_objectlist->SearchValue(curve)) {
			it = m_cutscenePaths.erase(it);
			continue;
		}

		const float duration = event->m_paramFloat;
		const float fraction = (duration > 0.0f) ?
			std::min(float((time - it->m_startTime) / duration), 1.0f) : 1.0f;

		mt::vec3 localPosition, localDirection;
		EvaluateCutscenePath(event->m_pathPoints, fraction, localPosition, localDirection);

		const mt::mat3x4 curveTransform = curve->NodeGetWorldTransform();
		const mt::vec3 position = curveTransform * localPosition;
		object->NodeSetWorldPosition(position);

		/* Cameras look down -Z; keep the horizon level with world +Z as up. */
		mt::vec3 forward = mt::zero3;
		KX_GameObject *target = event->m_dependentObject;
		if (target && m_objectlist->SearchValue(target)) {
			forward = target->NodeGetWorldPosition() - position;
		}
		else if (event->m_paramBool) {
			forward = curve->NodeGetWorldOrientation() * localDirection;
		}
		if (forward.LengthSquared() > 1e-8f) {
			const mt::vec3 zAxis = -forward.Normalized();
			mt::vec3 xAxis = mt::cross(mt::axisZ3, zAxis);
			if (xAxis.LengthSquared() > 1e-6f) {
				xAxis.Normalize();
				const mt::vec3 yAxis = mt::cross(zAxis, xAxis);
				object->NodeSetGlobalOrientation(mt::mat3(xAxis, yAxis, zAxis));
			}
		}
		object->NodeUpdate();

		if (fraction >= 1.0f) {
			it = m_cutscenePaths.erase(it);
		}
		else {
			++it;
		}
	}
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

		case CUTSCENE_EVENT_CAMERA_PATH:
			if (!event->m_templateObject || !event->m_spawnPoint || event->m_pathPoints.size() < 2) {
				CM_Error("Cutscene Camera Path event '" << event->m_name
				         << "' requires an Object and a Curve with at least two points");
				continue;
			}
			{
				/* A new path on the same object replaces the one it was following. */
				for (auto it = m_cutscenePaths.begin(); it != m_cutscenePaths.end(); ++it) {
					if (it->m_event->m_templateObject == event->m_templateObject) {
						m_cutscenePaths.erase(it);
						break;
					}
				}
				m_cutscenePaths.push_back({event, m_cutsceneManager->GetTime()});

				if (event->m_paramInt && event->m_templateObject->GetGameObjectType() == SCA_IObject::OBJ_CAMERA) {
					SetActiveCamera(static_cast<KX_Camera *>(event->m_templateObject));
				}
				UpdateCutscenePaths(m_cutsceneManager->GetTime());
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
