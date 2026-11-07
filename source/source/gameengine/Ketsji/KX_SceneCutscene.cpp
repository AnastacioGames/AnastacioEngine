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
#include "BLI_listbase.h"
#include "BL_Action.h"
#include "DNA_property_types.h"
#include "DNA_python_component_types.h"
#include "BLI_listbase.h"
#include "DNA_world_types.h"
#include "DNA_object_types.h"
#include "DNA_anim_types.h"
#include "DNA_node_types.h"
#include "BKE_scene.h" // SETLOOPER
#include "BKE_node.h" // SH_NODE_WORLD_BLOOM_FX, SH_NODE_WORLD_SSR_FX
extern "C" {
#include "BKE_idprop.h"
#include "BKE_motion_record.h"
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


/* Call range_cutscene_runtime.<func>(args). Returns the result truthiness. Steals `args`. */
static bool CallCutsceneRuntime(const char *func, PyObject *args)
{
#ifdef WITH_PYTHON
	bool result = false;
	PyObject *module = PyImport_ImportModule("range_cutscene_runtime");
	if (module && args) {
		PyObject *callable = PyObject_GetAttrString(module, func);
		if (callable) {
			PyObject *ret = PyObject_CallObject(callable, args);
			if (ret) {
				result = PyObject_IsTrue(ret) == 1;
				Py_DECREF(ret);
			}
			Py_DECREF(callable);
		}
	}
	if (PyErr_Occurred()) {
		CM_Error("cutscene: range_cutscene_runtime." << func << "() failed");
		PyErr_Print();
	}
	Py_XDECREF(args);
	Py_XDECREF(module);
	return result;
#else
	(void)func;
	(void)args;
	return false;
#endif
}

void KX_Scene::RestoreCutsceneGameplayCamera()
{
	KX_Camera *camera = m_cutsceneGameplayCamera;
	m_cutsceneGameplayCamera = nullptr;
	if (camera && GetCameraList()->SearchValue(camera)) {
		SetActiveCamera(camera);
	}
}

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
	EndCutsceneTakes(false);
	ClearCutsceneSpawnedObjects();
	if (m_cutsceneManager) {
		m_cutsceneManager->Stop();
	}
	m_pendingCutsceneEvents.clear();
	m_cutscenePaths.clear();
	CallCutsceneRuntime("stop", PyTuple_New(0));
	RestoreCutsceneGameplayCamera();
	m_cutsceneOverlayActive = false;
}

bool KX_Scene::SkipCutscene()
{
	if (!m_cutsceneManager) {
		return false;
	}
	if (!m_cutsceneManager->IsInProgress()) {
		/* The sequence ends at its last event, the take it started may still be playing. */
		const bool playing = std::any_of(m_motionReplays.begin(), m_motionReplays.end(),
		                                 [](const MotionReplay& replay) { return replay.m_fromCutscene; });
		EndCutsceneTakes(true);
		return playing;
	}
	const KX_CutsceneManager::DispatchedEvents remaining = m_cutsceneManager->Skip();
	m_pendingCutsceneEvents.insert(m_pendingCutsceneEvents.end(), remaining.begin(), remaining.end());
	m_cutsceneSkipping = true;
	DispatchCutsceneEvents();
	m_cutsceneSkipping = false;
	EndCutsceneTakes(true);
	m_cutscenePaths.clear();
	/* Drop the dialog and any fade/bars: the game continues in its normal view. */
	CallCutsceneRuntime("skip_cleanup", PyTuple_New(0));
	m_cutsceneOverlayActive = false;
	return true;
}

bool KX_Scene::RestartCutscene()
{
	if (!m_cutsceneManager) {
		return false;
	}
	EndCutsceneTakes(false);
	ClearCutsceneSpawnedObjects();
	m_pendingCutsceneEvents.clear();
	m_cutscenePaths.clear();
	CallCutsceneRuntime("stop", PyTuple_New(0));
	RestoreCutsceneGameplayCamera();
	return m_cutsceneManager->Restart();
}

void KX_Scene::UpdateCutscene(double deltaTime)
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

	KX_CutsceneManager::DispatchedEvents dispatchedEvents = m_cutsceneManager->Advance(deltaTime);
	m_pendingCutsceneEvents.insert(
		m_pendingCutsceneEvents.end(), dispatchedEvents.begin(), dispatchedEvents.end());

	if (!m_cutscenePaths.empty()) {
		UpdateCutscenePaths(m_cutsceneManager->GetPlayTime());
		if (m_cutscenePaths.empty() &&
		    m_cutsceneManager->GetWaitType() == KX_CutsceneManager::WAIT_CAMERA_END) {
			m_cutsceneManager->ClearWait();
		}
	}

	/* After the paths moved the camera: screen and camera effects animate and the skip key is
	 * read while a cutscene runs or an overlay is visible. */
	const bool inProgress = m_cutsceneManager->IsInProgress();
	if (inProgress || m_cutsceneOverlayActive) {
#ifdef WITH_PYTHON
		int flags = 0;
		PyObject *module = PyImport_ImportModule("range_cutscene_runtime");
		if (module) {
			PyObject *ret = PyObject_CallMethod(module, "update", "di", deltaTime, inProgress ? 1 : 0);
			if (ret) {
				flags = PyLong_Check(ret) ? (int)PyLong_AsLong(ret) : 0;
				Py_DECREF(ret);
			}
			Py_DECREF(module);
		}
		if (PyErr_Occurred()) {
			CM_Error("cutscene: range_cutscene_runtime.update() failed");
			PyErr_Print();
		}
		m_cutsceneOverlayActive = (flags & 1) != 0;
		if ((flags & 2) && inProgress) {
			SkipCutscene();
		}
#endif
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

		const float elapsed = float(time - it->m_startTime);
		const float duration = it->m_duration;
		float fraction = (duration > 0.0f) ? std::min(elapsed / duration, 1.0f) : 1.0f;
		switch (it->m_ease) {
			case 1: fraction = fraction * fraction; break;
			case 2: fraction = 1.0f - (1.0f - fraction) * (1.0f - fraction); break;
			case 3: fraction = fraction * fraction * (3.0f - 2.0f * fraction); break;
			default: break;
		}
		const float rawFraction = (duration > 0.0f) ? std::min(elapsed / duration, 1.0f) : 1.0f;
		/* transition SMOOTH: blend from where the object was into the path (smoothstep). */
		float blend = 1.0f;
		if (it->m_blendTime > 0.0f && elapsed < it->m_blendTime) {
			blend = elapsed / it->m_blendTime;
			blend = blend * blend * (3.0f - 2.0f * blend);
		}

		mt::vec3 localPosition, localDirection;
		EvaluateCutscenePath(event->m_pathPoints, fraction, localPosition, localDirection);

		const mt::mat3x4 curveTransform = curve->NodeGetWorldTransform();
		const mt::vec3 pathPosition = curveTransform * localPosition;
		const mt::vec3 position = it->m_startPosition + (pathPosition - it->m_startPosition) * blend;
		object->NodeSetWorldPosition(position);

		/* Cameras look down -Z; keep the horizon level with world +Z as up. */
		mt::vec3 forward = mt::zero3;
		KX_GameObject *target = it->m_target;
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
				const mt::mat3 pathOrientation(xAxis, yAxis, zAxis);
				if (blend < 1.0f) {
					const mt::quat from = mt::quat::FromMatrix(it->m_startOrientation).Normalized();
					const mt::quat to = mt::quat::FromMatrix(pathOrientation).Normalized();
					object->NodeSetGlobalOrientation(mt::quat::Slerp(from, to, blend).ToMatrix());
				}
				else {
					object->NodeSetGlobalOrientation(pathOrientation);
				}
			}
		}
		object->NodeUpdate();

		if (rawFraction >= 1.0f && blend >= 1.0f) {
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

/* The NLA player takes every track that is not muted, so the tracks of other takes are muted. */
static void PlayMotionTakeTracks(KX_GameObject *gameobj, const char *prefix, float start)
{
	Object *object = gameobj->GetBlenderObject();
	if (!object || !object->adt) {
		return;
	}
	for (NlaTrack *track = (NlaTrack *)object->adt->nla_tracks.first; track; track = track->next) {
		if (strncmp(track->name, "Rec_", 4) == 0) {
			if (strncmp(track->name, prefix, strlen(prefix)) == 0) {
				track->flag &= ~NLATRACK_MUTED;
			}
			else {
				track->flag |= NLATRACK_MUTED;
			}
		}
	}
	gameobj->StopNla();
	/* The actor may stand still before its first strip: the clock starts with the take. */
	if (gameobj->PlayNla(1.0f, false, start)) {
		gameobj->SetNlaFrame(start);
	}
}

/* Away from the layers a character uses for its own animation. */
static const short MOTION_TAKE_LAYER = 7;

/* The frame a take ends on, from the start of the scene. */
static float MotionTakeEnd(Scene *scene, const MotionTake *take)
{
	return (float)scene->r.sfra + take->duration * ((float)scene->r.frs_sec / scene->r.frs_sec_base);
}

/* Hands the object back to its own logic and physics, the opposite of PlayMotionTakeActor. */
static void EndMotionHold(KX_GameObject *gameobj, PHY_IPhysicsEnvironment *environment)
{
	gameobj->EndMotionReplay();
	if (!gameobj->GetPhysicsController()) {
		return;
	}
	if (environment->GetCharacterController(gameobj)) {
		gameobj->RestorePhysics();
	}
	else {
		gameobj->GetPhysicsController()->RestoreDynamics();
	}
}

/* Sets the pose of the replay's time and starts the clips it reached. */
static void ApplyMotionReplay(KX_Scene::MotionReplay& replay)
{
	const MotionTakeActor *actor = replay.m_actor;
	KX_GameObject *gameobj = replay.m_object;
	if (actor->samples_num >= 2) {
		float loc[3], quat[4], scale[3];
		BKE_motion_take_pose(actor, (float)replay.m_time, &replay.m_sample, loc, quat, scale);
		gameobj->NodeSetLocalPosition(mt::vec3(loc[0], loc[1], loc[2]));
		gameobj->NodeSetLocalOrientation(mt::quat(quat[0], quat[1], quat[2], quat[3]).ToMatrix());
		gameobj->NodeSetLocalScale(mt::vec3(scale[0], scale[1], scale[2]));
	}

	/* The NLA tracks already play them when there are keyframes. */
	while (!actor->track_prefix[0] && replay.m_clip < actor->clips_num &&
	       actor->clips[replay.m_clip].t_start <= replay.m_time)
	{
		const MotionTakeClip& clip = actor->clips[replay.m_clip++];
		const float seconds = clip.t_end - clip.t_start;
		if (seconds > 0.0f) {
			const float frames = std::abs(clip.frame_end - clip.frame_start);
			gameobj->PlayAction(clip.action, clip.frame_start, clip.frame_end, clip.layer, 0, 0.0f, BL_Action::ACT_MODE_PLAY,
			                    0.0f, 0, frames / seconds / (float)KX_GetActiveEngine()->GetAnimFrameRate());
		}
	}
}

void KX_Scene::UpdateMotionReplays(double step)
{
	for (unsigned int i = 0; i < m_motionReplays.size();) {
		MotionReplay& replay = m_motionReplays[i];
		replay.m_time += step;
		ApplyMotionReplay(replay);
		if (replay.m_time >= replay.m_end) {
			if (replay.m_endsLogicHold) {
				EndMotionHold(replay.m_object, m_physicsEnvironment);
			}
			m_motionReplays.erase(m_motionReplays.begin() + i);
		}
		else {
			++i;
		}
	}
}

void KX_Scene::EndCutsceneTakes(bool finish)
{
	for (unsigned int i = 0; i < m_motionReplays.size();) {
		MotionReplay& replay = m_motionReplays[i];
		if (!replay.m_fromCutscene) {
			++i;
			continue;
		}
		if (finish) {
			/* Only the pose: the clips left would all start at once. */
			replay.m_clip = replay.m_actor->clips_num;
			replay.m_time = replay.m_end;
			ApplyMotionReplay(replay);
			/* The body turns dynamic below, before the scene graph would place it. */
			replay.m_object->NodeUpdate();
			replay.m_object->SynchronizeTransform();
		}
		if (replay.m_endsLogicHold) {
			EndMotionHold(replay.m_object, m_physicsEnvironment);
		}
		m_motionReplays.erase(m_motionReplays.begin() + i);
	}
}

void KX_Scene::RemoveMotionReplay(KX_GameObject *gameobj)
{
	m_motionReplays.erase(std::remove_if(m_motionReplays.begin(), m_motionReplays.end(),
	                                     [gameobj](const MotionReplay& replay) { return replay.m_object == gameobj; }),
	                      m_motionReplays.end());
}

/* ghost: the actor stops touching the world. A Character has no dynamics to hold, it always leaves. */
void KX_Scene::PlayMotionTakeActor(KX_GameObject *gameobj, const MotionTakeActor *actor, float start, float end, bool ghost, bool cutscene)
{
	/* Nothing to play: the object must not be held by a replay that never ends it. */
	if (actor->samples_num < 2 && actor->clips_num == 0 && !actor->action_name[0] && !actor->track_prefix[0]) {
		return;
	}
	/* Takes layered under a recording hold their actors until the game ends. */
	bool hold = !gameobj->IsMotionReplay();
	for (const MotionReplay& replay : m_motionReplays) {
		hold |= (replay.m_object == gameobj && replay.m_endsLogicHold);
	}
	/* Before the physics below: it may bring a culled object back. */
	gameobj->SetMotionReplay();
	/* Otherwise physics pulls a rigid body away from the recorded path. */
	if (gameobj->GetPhysicsController()) {
		if (ghost || m_physicsEnvironment->GetCharacterController(gameobj)) {
			gameobj->SuspendPhysics(false);
		}
		else {
			gameobj->GetPhysicsController()->SuspendDynamics(false);
		}
	}
	/* A take that ends as this one starts may still hold the object. */
	RemoveMotionReplay(gameobj);
	Scene *scene = GetBlenderScene();
	const double seconds = actor->samples_num >= 2 ? actor->samples[(actor->samples_num - 1) * MOTION_TAKE_SAMPLE_FLOATS] :
	                       (end - start) * scene->r.frs_sec_base / scene->r.frs_sec;
	m_motionReplays.push_back({gameobj, actor, 0.0, 0, 0, hold, seconds, cutscene});
	ApplyMotionReplay(m_motionReplays.back());
	if (actor->samples_num < 2 && actor->action_name[0]) {
		/* A take from before the samples existed. */
		gameobj->StopAction(MOTION_TAKE_LAYER);
		gameobj->PlayAction(actor->action_name, start, end, MOTION_TAKE_LAYER);
	}
	if (actor->track_prefix[0]) {
		PlayMotionTakeTracks(gameobj, actor->track_prefix, start);
	}
}

void KX_Scene::PlayMotionTakeLayers()
{
	Scene *scene = GetBlenderScene();
	const bool ghost = !BKE_motion_record_layers_collide();
	std::vector<KX_GameObject *> taken = m_motionRecordActors;
	int index = BLI_listbase_count(&scene->motion_takes);
	for (const MotionTake *take = (MotionTake *)scene->motion_takes.last; take; take = take->prev) {
		if (--index == BKE_motion_record_replaced_take()) {
			continue;
		}
		for (const MotionTakeActor *actor = (MotionTakeActor *)take->actors.first; actor; actor = actor->next) {
			KX_GameObject *gameobj = actor->ob ? FindGameObject(m_objectlist, actor->ob->id.name + 2) : nullptr;
			if (!gameobj || std::find(taken.begin(), taken.end(), gameobj) != taken.end()) {
				continue;
			}
			taken.push_back(gameobj);
			/* Set first, so the replay knows the logic does not come back. */
			gameobj->SetMotionReplay();
			PlayMotionTakeActor(gameobj, actor, (float)scene->r.sfra, MotionTakeEnd(scene, take), ghost);
		}
	}
}

bool KX_Scene::PlayMotionTake(const std::string& name, bool cutscene)
{
	Scene *scene = GetBlenderScene();
	for (const MotionTake *take = (MotionTake *)scene->motion_takes.first; take; take = take->next) {
		if (name != take->name) {
			continue;
		}
		const float start = (float)scene->r.sfra;
		const float end = MotionTakeEnd(scene, take);
		for (const MotionTakeActor *actor = (MotionTakeActor *)take->actors.first; actor; actor = actor->next) {
			KX_GameObject *gameobj = actor->ob ? FindGameObject(m_objectlist, actor->ob->id.name + 2) : nullptr;
			if (!gameobj) {
				CM_Error("Play Take '" << name << "': an actor is missing from the scene");
				continue;
			}
			PlayMotionTakeActor(gameobj, actor, start, end, false, cutscene);
		}
		return true;
	}
	CM_Error("Play Take: no take named '" << name << "'");
	return false;
}

bool KX_Scene::PlayMotionTakeObject(KX_GameObject *gameobj, const std::string& name)
{
	Scene *scene = GetBlenderScene();
	for (const MotionTake *take = (MotionTake *)scene->motion_takes.first; take; take = take->next) {
		if (name != take->name) {
			continue;
		}
		for (const MotionTakeActor *actor = (MotionTakeActor *)take->actors.first; actor; actor = actor->next) {
			if (actor->ob == gameobj->GetBlenderObject()) {
				PlayMotionTakeActor(gameobj, actor, (float)scene->r.sfra, MotionTakeEnd(scene, take), false);
				return true;
			}
		}
	}
	return false;
}

void KX_Scene::StopMotionTake(KX_GameObject *gameobj)
{
	for (const MotionReplay& replay : m_motionReplays) {
		if (replay.m_object == gameobj) {
			if (replay.m_endsLogicHold) {
				EndMotionHold(gameobj, m_physicsEnvironment);
			}
			break;
		}
	}
	RemoveMotionReplay(gameobj);
}

bool KX_Scene::IsMotionTakePlaying(KX_GameObject *gameobj) const
{
	return std::any_of(m_motionReplays.begin(), m_motionReplays.end(),
	                   [gameobj](const MotionReplay& replay) { return replay.m_object == gameobj; });
}

void KX_Scene::DispatchCutsceneEvents()
{
	const KX_CutsceneManager::DispatchedEvents dispatchedEvents = TakePendingCutsceneEvents();
	for (const KX_CutsceneManager::Event *event : dispatchedEvents) {
		if (m_cutsceneSkipping) {
			switch (event->m_type) {
				case CUTSCENE_EVENT_DIALOG:
				case CUTSCENE_EVENT_HIDE_DIALOG:
				case CUTSCENE_EVENT_WAIT_TIME:
				case CUTSCENE_EVENT_WAIT_TRIGGER:
				case CUTSCENE_EVENT_WAIT_CAMERA_END:
				case CUTSCENE_EVENT_CAMERA_PATH:
				case CUTSCENE_EVENT_FADE:
				case CUTSCENE_EVENT_LETTERBOX:
				case CUTSCENE_EVENT_PLAYER_ANIM:
					continue;
				default:
					break;
			}
		}
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
				KX_GameObject *textObject = event->m_templateObject;
				if (textObject && !m_objectlist->SearchValue(textObject)) {
					textObject = nullptr;
				}
				if (!textObject) {
					/* Legacy: the game provides an overlay scene that reads globalDict["cutscene_dialog"]. */
					const std::string &overlayScene = event->m_paramBool ? "_dialogue_live" : "_dialogue";
					KX_GetActiveEngine()->ConvertAndAddScene(overlayScene, true);
				}
#ifdef WITH_PYTHON
				PyObject *objArg = Py_None;
				if (textObject) {
					objArg = textObject->GetProxy();
				}
				else {
					Py_INCREF(Py_None);
				}
				PyObject *args = Py_BuildValue("(NsssO)", objArg, text.c_str(), event->m_paramStrA.c_str(),
				                               event->m_audioPath.c_str(), event->m_paramInt ? Py_True : Py_False);
				const bool canWait = CallCutsceneRuntime("show_dialog", args);
				if (event->m_paramInt && m_cutsceneManager) {
					if (canWait) {
						m_cutsceneManager->StartWaitTrigger("cutscene_dialog");
					}
					else {
						CM_Warning("cutscene Dialog '" << event->m_name << "': Wait for Advance needs a Text object "
						           "prepared with Setup Dialogue; not waiting");
					}
				}
#endif
			}
			break;

		case CUTSCENE_EVENT_HIDE_DIALOG:
			KX_GetActiveEngine()->RemoveScene("_dialogue_live");
			KX_GetActiveEngine()->RemoveScene("_dialogue");
			CallCutsceneRuntime("hide_dialog", PyTuple_New(0));
			break;

		case CUTSCENE_EVENT_CAMERA_SHOT:
			if (event->m_templateObject && m_objectlist->SearchValue(event->m_templateObject)) {
				/* Native cut: switch to the chosen camera, remembering the gameplay camera once. */
				if (event->m_templateObject->GetGameObjectType() != SCA_IObject::OBJ_CAMERA) {
					/* Shot Empty (Cutscene Shot Tool): the active camera travels to it, following its properties. */
					PyObject *args = Py_BuildValue("(N)", event->m_templateObject->GetProxy());
					CallCutsceneRuntime("shot_to", args);
					m_cutsceneOverlayActive = true;
					continue;
				}
				KX_Camera *shotCamera = static_cast<KX_Camera *>(event->m_templateObject);
				if (!m_cutsceneGameplayCamera && GetActiveCamera() != shotCamera) {
					m_cutsceneGameplayCamera = GetActiveCamera();
				}
				SetActiveCamera(shotCamera);
				CallCutsceneRuntime("camera_cut", PyTuple_New(0));
			}
			else {
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
			CallCutsceneRuntime("restore_shot_camera", PyTuple_New(0));
			RestoreCutsceneGameplayCamera();
			CallCutsceneRuntime("camera_cut", PyTuple_New(0));
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
				if (!cameraMgr) {
					/* No game component: the engine plays the Shot Empties itself. */
					CallCutsceneRuntime("start_shots", PyTuple_New(0));
					m_cutsceneOverlayActive = true;
				}
				else {
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
				if (!cameraMgr) {
					/* No game component: the engine plays the Shot Empties itself. */
					CallCutsceneRuntime("restore_shot_camera", PyTuple_New(0));
					m_cutsceneOverlayActive = true;
				}
				else {
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
								// GetProxy e o retorno da chamada sao referencias novas.
								PyObject *ret = PyObject_CallMethod(proxy, "Action", "sff",
									event->m_paramStrA.c_str(),
									event->m_paramFloat,
									0.0f);
								if (ret) {
									Py_DECREF(ret);
								}
								else {
									CM_Error("cutscene Player Anim: Action() failed on " << player->GetName());
									PyErr_Print();
								}
								Py_DECREF(proxy);
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
				m_cutsceneManager->StartWaitTime(m_cutsceneManager->GetWaitStartPlayTime() + event->m_paramFloat);
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
				CutscenePathPlayback playback;
				playback.m_event = event;
				playback.m_startTime = m_cutsceneManager->GetPlayTime();
				playback.m_duration = event->m_paramFloat;
				playback.m_target = event->m_dependentObject;
				playback.m_startPosition = event->m_templateObject->NodeGetWorldPosition();
				playback.m_startOrientation = event->m_templateObject->NodeGetWorldOrientation();
				KX_GameObject *curve = event->m_spawnPoint;
				if (EXP_Value *value = curve->GetProperty("duration")) {
					if (playback.m_duration <= 0.0f) {
						playback.m_duration = (float)value->GetNumber();
					}
				}
				EXP_Value *transition = curve->GetProperty("transition");
				if (transition && transition->GetText() == "SMOOTH") {
					EXP_Value *speed = curve->GetProperty("transition_speed");
					playback.m_blendTime = speed ? std::max(0.0f, (float)speed->GetNumber()) : 1.0f;
				}
				if (EXP_Value *ease = curve->GetProperty("ease")) {
					const std::string text = ease->GetText();
					playback.m_ease = (text == "IN") ? 1 : (text == "OUT") ? 2 : (text == "IN_OUT") ? 3 : 0;
				}
				if (!playback.m_target) {
					if (EXP_Value *target = curve->GetProperty("target")) {
						const std::string name = target->GetText();
						playback.m_target = name.empty() ? nullptr : m_objectlist->FindValue(name);
					}
				}
				m_cutscenePaths.push_back(playback);
				/* FOV, shake, noise, slow motion and filter messages of the curve (Python side). */
				CallCutsceneRuntime("path_start", Py_BuildValue("(NN)", event->m_templateObject->GetProxy(),
				                                                curve->GetProxy()));
				m_cutsceneOverlayActive = true;

				if (event->m_paramInt && event->m_templateObject->GetGameObjectType() == SCA_IObject::OBJ_CAMERA) {
					SetActiveCamera(static_cast<KX_Camera *>(event->m_templateObject));
				}
				UpdateCutscenePaths(m_cutsceneManager->GetPlayTime());
			}
			break;

		case CUTSCENE_EVENT_FADE:
			{
				PyObject *args = Py_BuildValue("(if)", event->m_paramInt, event->m_paramFloat);
				CallCutsceneRuntime("fade", args);
				m_cutsceneOverlayActive = true;
			}
			break;

		case CUTSCENE_EVENT_PLAY_TAKE:
			/* Also on a skip: SkipCutscene jumps it to its last pose. */
			PlayMotionTake(event->m_paramStrA, true);
			break;

		case CUTSCENE_EVENT_LETTERBOX:
			{
				PyObject *args = Py_BuildValue("(if)", event->m_paramBool ? 1 : 0, event->m_paramFloat);
				CallCutsceneRuntime("letterbox", args);
				m_cutsceneOverlayActive = true;
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
