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
#include "KX_Scene.h"
#include "BL_Converter.h"
#include "CM_Message.h"
#include "EXP_ListValue.h"
#include "DNA_scene_types.h"

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
	m_engine->GetConverter()->RemoveScene(scene);
}

void KX_SceneScheduler::ConvertAndAddScene(const std::string& scenename, bool overlay)
{
	// only add scene when it doesn't exist!
	if (FindScene(scenename)) {
		CM_Warning("scene " << scenename << " already exists, not added!");
	}
	else {
		if (overlay) {
			m_addingOverlayScenes.push_back(scenename);
		}
		else {
			m_addingBackgroundScenes.push_back(scenename);
		}
	}
}

void KX_SceneScheduler::RemoveScene(const std::string& scenename)
{
	if (FindScene(scenename)) {
		m_removingScenes.push_back(scenename);
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
			if (scene) {
				DestructScene(scene);
				m_engine->GetScenes()->RemoveValue(scene);
			}
		}
		m_removingScenes.clear();
	}
}

void KX_SceneScheduler::AddScheduledScenes()
{
	if (!m_addingOverlayScenes.empty()) {
		for (const std::string& scenename : m_addingOverlayScenes) {
			KX_Scene *tmpscene = CreateScene(scenename);

			if (tmpscene) {
				m_engine->GetConverter()->ConvertScene(tmpscene);
				m_engine->GetScenes()->Add(CM_AddRef(tmpscene));
				PostProcessScene(tmpscene);
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
			KX_Scene *tmpscene = CreateScene(scenename);

			if (tmpscene) {
				m_engine->GetConverter()->ConvertScene(tmpscene);
				m_engine->GetScenes()->Insert(0, CM_AddRef(tmpscene));
				PostProcessScene(tmpscene);
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

						KX_Scene *tmpscene = CreateScene(blScene);
						m_engine->GetConverter()->ConvertScene(tmpscene);

						m_engine->GetScenes()->SetValue(sce_idx, CM_AddRef(tmpscene));
						PostProcessScene(tmpscene);
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

	if (m_engine->GetScenes()->Empty()) {
		m_engine->RequestExit(KX_ExitInfo::NO_SCENES_LEFT);
	}
}
