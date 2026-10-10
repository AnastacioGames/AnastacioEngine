#include <algorithm>
#include <cstdio>
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

/** \file KX_SceneScheduler.cpp
 *  \ingroup ketsji
 */

#include "KX_SceneScheduler.h"
#include "KX_KetsjiEngine.h"
#include "KX_EngineProfiler.h"
#include "KX_Scene.h"
#include "KX_NetworkManager.h"
#include "BL_Converter.h"
#include "BL_LoadStats.h"
#include "CM_Message.h"
#include "EXP_ListValue.h"
#include "DNA_scene_types.h"
#include "PIL_time.h"

KX_SceneScheduler::KX_SceneScheduler(KX_KetsjiEngine *engine)
	:m_engine(engine)
{
}

EXP_ListValue<KX_Scene> *KX_SceneScheduler::CurrentScenes()
{
	return m_engine->GetScenes();
}

KX_Scene *KX_SceneScheduler::FindScene(const std::string& scenename)
{
	return m_engine->GetScenes()->FindValue(scenename);
}

KX_Scene *KX_SceneScheduler::CreateScene(Scene *scene)
{
	KX_Scene *tmpscene = new KX_Scene(m_engine->GetInputDevice(),
	                                  scene->id.name + 2,
	                                  scene,
	                                  m_engine->GetCanvas(),
	                                  m_engine->GetNetworkMessageManager());

	return tmpscene;
}

KX_Scene *KX_SceneScheduler::CreateScene(const std::string& scenename)
{
	Scene *scene = m_engine->GetConverter()->GetBlenderSceneForName(scenename);
	if (!scene) {
		return nullptr;
	}

	return CreateScene(scene);
}

void KX_SceneScheduler::AddScene(KX_Scene *scene)
{
	m_engine->GetScenes()->Add(CM_AddRef(scene));
	PostProcessScene(scene);
}

void KX_SceneScheduler::PostProcessScene(KX_Scene *scene)
{
	bool override_camera = (((m_engine->GetFlag(KX_KetsjiEngine::CAMERA_OVERRIDE)) != 0) && (scene->GetName() == m_engine->GetOverrideSceneName()));

	// if there is no activecamera, or the camera is being
	// overridden we need to construct a temporary camera
	if (!scene->GetActiveCamera() || override_camera) {
		m_engine->CreateTemporaryCamera(scene, override_camera);
	}

	scene->UpdateParents();
}

void KX_SceneScheduler::DestructScene(KX_Scene *scene)
{
	scene->RunOnRemoveCallbacks();
	// Multiplayer: the session lets go of the scene's objects (and follows a replacement).
	if (KX_NetworkManager *network = m_engine->GetNetworkManager()) {
		network->OnSceneRemoved(scene);
	}
	m_engine->GetConverter()->RemoveScene(scene);
}

/// Names the scene added this frame and its cost in the profiler spike log.
static void ProfileNoteScene(const std::string& name, double start)
{
	if (KX_EngineProfiler::Enabled()) {
		char buf[32];
		snprintf(buf, sizeof(buf), "=%.0fms", (PIL_check_seconds_timer() - start) * 1000.0);
		KX_EngineProfiler::Note(name + buf);
	}
}

void KX_SceneScheduler::ConvertAndAddScene(const std::string& scenename, bool overlay, bool asynchronous)
{
	// only add scene when it doesn't exist!
	if (FindScene(scenename) || IsPending(scenename)) {
		CM_Warning("scene " << scenename << " already exists, not added!");
	}
	else {
		if (asynchronous) {
			m_addingAsyncScenes.emplace_back(scenename, overlay);
		}
		else if (overlay) {
			m_addingOverlayScenes.push_back(scenename);
		}
		else {
			m_addingBackgroundScenes.push_back(scenename);
		}
	}
}

void KX_SceneScheduler::RemoveScene(const std::string& scenename, bool keep)
{
	if (FindScene(scenename)) {
		m_removingScenes.push_back(scenename);
		if (keep) {
			m_removingKeep.push_back(scenename);
		}
	}
	else {
		CM_Warning("scene " << scenename << " does not exist, not removed!");
	}
}

void KX_SceneScheduler::RemoveScheduledScenes()
{
	if (!m_removingScenes.empty()) {
		std::vector<std::string>::iterator scenenameit;
		for (scenenameit = m_removingScenes.begin(); scenenameit != m_removingScenes.end(); scenenameit++) {
			std::string scenename = *scenenameit;

			KX_Scene *scene = FindScene(scenename);
			if (!scene) {
				continue;
			}
			const bool keep = std::find(m_removingKeep.begin(), m_removingKeep.end(), scenename) != m_removingKeep.end();
			if (keep && m_preparedScenes.find(scenename) == m_preparedScenes.end()) {
				// Hidden and paused, not destroyed: the prepared map holds the reference the list had.
				CM_AddRef(scene);
				m_engine->GetScenes()->RemoveValue(scene);
				if (!scene->IsSuspended()) {
					scene->Suspend();
					m_keptScenes.push_back(scenename);
				}
				m_preparedScenes[scenename] = scene;
				continue;
			}
			DestructScene(scene);
			m_engine->GetScenes()->RemoveValue(scene);
		}
		m_removingScenes.clear();
		m_removingKeep.clear();
	}
}

void KX_SceneScheduler::AddScheduledScenes()
{
	if (!m_addingOverlayScenes.empty()) {
		for (const std::string& scenename : m_addingOverlayScenes) {
			const double start = PIL_check_seconds_timer();
			KX_Scene *tmpscene = TakeOrConvertScene(scenename);

			if (tmpscene) {
				ResumeIfKept(tmpscene);
				m_engine->GetScenes()->Add(CM_AddRef(tmpscene));
				PostProcessScene(tmpscene);
				BL_LoadLog::Add(scenename, "add scene total (overlay)", PIL_check_seconds_timer() - start, "", true);
				ProfileNoteScene(scenename, start);
				tmpscene->Release();
			}
			else {
				CM_Warning("scene " << scenename << " could not be found, not added!");
			}
		}
		m_addingOverlayScenes.clear();
	}

	if (!m_addingBackgroundScenes.empty()) {
		for (const std::string& scenename : m_addingBackgroundScenes) {
			const double start = PIL_check_seconds_timer();
			KX_Scene *tmpscene = TakeOrConvertScene(scenename);

			if (tmpscene) {
				ResumeIfKept(tmpscene);
				m_engine->GetScenes()->Insert(0, CM_AddRef(tmpscene));
				PostProcessScene(tmpscene);
				BL_LoadLog::Add(scenename, "add scene total (background)", PIL_check_seconds_timer() - start, "", true);
				ProfileNoteScene(scenename, start);
				tmpscene->Release();
			}
			else {
				CM_Warning("scene " << scenename << " could not be found, not added!");
			}
		}
		m_addingBackgroundScenes.clear();
	}
}

bool KX_SceneScheduler::ReplaceScene(const std::string& oldscene, const std::string& newscene)
{
	// Don't allow replacement if the new scene doesn't exist.
	// Allows smarter game design (used to have no check here).
	// Note that it creates a small backward compatbility issue
	// for a game that did a replace followed by a lib load with the
	// new scene in the lib => it won't work anymore, the lib
	// must be loaded before doing the replace.
	if (m_engine->GetConverter()->GetBlenderSceneForName(newscene)) {
		m_replace_scenes.emplace_back(oldscene, newscene);
		return true;
	}

	return false;
}

// replace scene is not the same as removing and adding because the
// scene must be in exact the same place (to maintain drawingorder)
// (nzc) - should that not be done with a scene-display list? It seems
// stupid to rely on the mem allocation order...
void KX_SceneScheduler::ReplaceScheduledScenes()
{
	if (!m_replace_scenes.empty()) {
		std::vector<std::pair<std::string, std::string> >::iterator scenenameit;

		for (scenenameit = m_replace_scenes.begin();
		     scenenameit != m_replace_scenes.end();
		     scenenameit++)
		{
			std::string oldscenename = (*scenenameit).first;
			std::string newscenename = (*scenenameit).second;
			/* Scenes are not supposed to be included twice... I think */
			for (unsigned int sce_idx = 0; sce_idx < m_engine->GetScenes()->GetCount(); ++sce_idx) {
				KX_Scene *scene = m_engine->GetScenes()->GetValue(sce_idx);
				if (scene->GetName() == oldscenename) {
					// avoid crash if the new scene doesn't exist, just do nothing
					Scene *blScene = m_engine->GetConverter()->GetBlenderSceneForName(newscenename);
					if (blScene) {
						DestructScene(scene);

						const double start = PIL_check_seconds_timer();
						KX_Scene *tmpscene = TakeOrConvertScene(newscenename, blScene);
						ResumeIfKept(tmpscene);

						m_engine->GetScenes()->SetValue(sce_idx, CM_AddRef(tmpscene));
						PostProcessScene(tmpscene);
						BL_LoadLog::Add(newscenename, "replace scene total", PIL_check_seconds_timer() - start, "", true);
						tmpscene->Release();
					}
					else {
						CM_Warning("scene " << newscenename << " could not be found, not replaced!");
					}
				}
			}
		}
		m_replace_scenes.clear();
	}
}

void KX_SceneScheduler::SuspendScene(const std::string& scenename)
{
	KX_Scene *scene = FindScene(scenename);
	if (scene) {
		scene->Suspend();
	}
}

void KX_SceneScheduler::ResumeScene(const std::string& scenename)
{
	KX_Scene *scene = FindScene(scenename);
	if (scene) {
		scene->Resume();
	}
}

bool KX_SceneScheduler::IsPending(const std::string& scenename) const
{
	for (const PendingScene& pending : m_pendingScenes) {
		if (pending.m_scene->GetName() == scenename) {
			return true;
		}
	}
	for (const std::pair<std::string, bool>& item : m_addingAsyncScenes) {
		if (item.first == scenename) {
			return true;
		}
	}
	return false;
}

void KX_SceneScheduler::StepPendingScenes()
{
	for (const std::pair<std::string, bool>& item : m_addingAsyncScenes) {
		const auto prepared = m_preparedScenes.find(item.first);
		if (prepared != m_preparedScenes.end()) {
			KX_Scene *scene = prepared->second;
			m_preparedScenes.erase(prepared);
			ResumeIfKept(scene);
			if (item.second) {
				m_engine->GetScenes()->Add(CM_AddRef(scene));
			}
			else {
				m_engine->GetScenes()->Insert(0, CM_AddRef(scene));
			}
			PostProcessScene(scene);
			scene->Release();
			continue;
		}
		KX_Scene *scene = CreateScene(item.first);
		if (!scene) {
			CM_Warning("scene " << item.first << " could not be found, not added!");
			continue;
		}
		const double start = PIL_check_seconds_timer();
		m_engine->GetConverter()->ConvertScene(scene, false);
		m_pendingScenes.push_back({scene, item.second, 0, start, 0.0});
	}
	m_addingAsyncScenes.clear();

	// One scene at a time, in request order, within the LibLoad frame budget.
	if (m_pendingScenes.empty()) {
		return;
	}
	BL_Converter *converter = m_engine->GetConverter();
	PendingScene& pending = m_pendingScenes.front();
	const double stepStart = PIL_check_seconds_timer();
	const bool done = converter->CompileSceneShaders(pending.m_scene, pending.m_material, pending.m_sent,
	                                                 stepStart + converter->GetMergeFrameBudget());
	pending.m_shaderTime += PIL_check_seconds_timer() - stepStart;
	if (!done) {
		return;
	}

	KX_Scene *scene = pending.m_scene;
	ProfileNoteScene(scene->GetName() + "(async)", stepStart);
	BL_LoadLog::Add(scene->GetName(), "async shaders", pending.m_shaderTime);
	BL_LoadLog::Add(scene->GetName(), "async scene total", PIL_check_seconds_timer() - pending.m_start, "", true);
	CM_Message("[Load] async scene \"" << scene->GetName() << "\": " << pending.m_material << " materials, shaders "
	           << (int)(pending.m_shaderTime * 1000.0) << "ms, ready after "
	           << (int)((PIL_check_seconds_timer() - pending.m_start) * 1000.0) << "ms");
	if (pending.m_overlay) {
		m_engine->GetScenes()->Add(CM_AddRef(scene));
	}
	else {
		m_engine->GetScenes()->Insert(0, CM_AddRef(scene));
	}
	m_pendingScenes.erase(m_pendingScenes.begin());
	PostProcessScene(scene);
	scene->Release();
}

void KX_SceneScheduler::DestructPendingScenes()
{
	for (PendingScene& pending : m_pendingScenes) {
		// Releases the creation reference, the scene never joined the list.
		DestructScene(pending.m_scene);
	}
	m_pendingScenes.clear();
	m_addingAsyncScenes.clear();
	for (const auto& item : m_preparedScenes) {
		DestructScene(item.second);
	}
	m_preparedScenes.clear();
	m_keptScenes.clear();
	m_preloadingScenes.clear();
}

void KX_SceneScheduler::ResumeIfKept(KX_Scene *scene)
{
	const auto it = std::find(m_keptScenes.begin(), m_keptScenes.end(), scene->GetName());
	if (it != m_keptScenes.end()) {
		m_keptScenes.erase(it);
		scene->Resume();
	}
}

bool KX_SceneScheduler::PreloadScene(const std::string& scenename)
{
	if (!m_engine->GetConverter()->GetBlenderSceneForName(scenename)) {
		return false;
	}
	std::lock_guard<std::mutex> lock(m_preloadingMutex);
	if (std::find(m_preloadingScenes.begin(), m_preloadingScenes.end(), scenename) == m_preloadingScenes.end()) {
		m_preloadingScenes.push_back(scenename);
	}
	return true;
}

void KX_SceneScheduler::PreloadScheduledScenes()
{
	// Converting a scene can queue more (its Scene actuators with Preload): those wait for the next frame.
	std::vector<std::string> names;
	{
		std::lock_guard<std::mutex> lock(m_preloadingMutex);
		names.swap(m_preloadingScenes);
	}
	for (const std::string& scenename : names) {
		// Running, compiling or prepared already: nothing to do.
		if (FindScene(scenename) || IsPending(scenename) || m_preparedScenes.find(scenename) != m_preparedScenes.end()) {
			continue;
		}
		const double start = PIL_check_seconds_timer();
		KX_Scene *scene = CreateScene(scenename);
		if (!scene) {
			continue;
		}
		m_engine->GetConverter()->ConvertScene(scene);
		m_preparedScenes[scenename] = scene;
		BL_LoadLog::Add(scenename, "preload scene total", PIL_check_seconds_timer() - start, "", true);
		ProfileNoteScene(scenename + "(preload)", start);
	}
}

KX_Scene *KX_SceneScheduler::TakeOrConvertScene(const std::string& scenename, Scene *blScene)
{
	const auto prepared = m_preparedScenes.find(scenename);
	if (prepared != m_preparedScenes.end()) {
		KX_Scene *scene = prepared->second;
		m_preparedScenes.erase(prepared);
		return scene;
	}
	KX_Scene *scene = blScene ? CreateScene(blScene) : CreateScene(scenename);
	if (scene) {
		m_engine->GetConverter()->ConvertScene(scene);
	}
	return scene;
}

void KX_SceneScheduler::ProcessScheduledScenes()
{
	// Check whether there will be changes to the list of scenes
	if (!(m_addingOverlayScenes.empty() && m_addingBackgroundScenes.empty() &&
	      m_replace_scenes.empty() && m_removingScenes.empty())) {
		// Change the scene list
		ReplaceScheduledScenes();
		RemoveScheduledScenes();
		AddScheduledScenes();
	}
	StepPendingScenes();
	PreloadScheduledScenes();

	if (m_engine->GetScenes()->Empty()) {
		m_engine->RequestExit(KX_ExitInfo::NO_SCENES_LEFT);
	}
}
