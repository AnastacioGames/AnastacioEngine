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

#ifndef __KX_SCENESCHEDULER_H__
#define __KX_SCENESCHEDULER_H__

#include <string>
#include <vector>
#include <utility>

template <class T> class EXP_ListValue;
class KX_Scene;
class KX_KetsjiEngine;
struct Scene;

/** Owns scene add/remove/replace/suspend/convert scheduling extracted out of KX_KetsjiEngine
 * (Plano 7 of the Ketsji modernization program, see
 * docs/ketsji-engine-modernization-plan.md): the four pending-operation lists (overlay/background
 * adds, removes, replaces) and the code that resolves them once per frame, plus the immediate
 * (non-scheduled) scene operations (AddScene, SuspendScene/ResumeScene, CreateScene,
 * DestructScene/PostProcessScene).
 *
 * This is a pure extraction: behavior, ordering (Replace -> Remove -> Add, see
 * ProcessScheduledScenes) and public call sites on KX_KetsjiEngine are unchanged. It still reaches
 * back into KX_KetsjiEngine for shared engine state (scene list, converter, canvas, network
 * message manager, camera-override settings) rather than owning independent copies. */
class KX_SceneScheduler
{
	KX_KetsjiEngine *m_engine;

	/// Lists of scenes scheduled to be removed at the end of the frame.
	std::vector<std::string> m_removingScenes;
	/// Lists of overlay scenes scheduled to be added at the end of the frame.
	std::vector<std::string> m_addingOverlayScenes;
	/// Lists of background scenes scheduled to be added at the end of the frame.
	std::vector<std::string> m_addingBackgroundScenes;
	/// Lists of scenes scheduled to be replaced at the end of the frame.
	std::vector<std::pair<std::string, std::string> > m_replace_scenes;
	/// Names of scenes scheduled with addScene(..., asynchronous=True), and if overlay.
	std::vector<std::pair<std::string, bool> > m_addingAsyncScenes;

	/** Scene added with addScene(..., asynchronous=True): converted, but kept out of the scene list (no
	 * logic, no drawing) while its shaders compile a few per frame, so a loading screen keeps animating.
	 */
	struct PendingScene {
		KX_Scene *m_scene;
		bool m_overlay;
		/// Next material to compile.
		unsigned int m_material;
		double m_start;
		double m_shaderTime;
	};
	std::vector<PendingScene> m_pendingScenes;

	void StepPendingScenes();
	bool IsPending(const std::string& scenename) const;

	void RemoveScheduledScenes();
	void AddScheduledScenes();
	void ReplaceScheduledScenes();

public:
	explicit KX_SceneScheduler(KX_KetsjiEngine *engine);
	~KX_SceneScheduler() = default;

	EXP_ListValue<KX_Scene> *CurrentScenes();
	KX_Scene *FindScene(const std::string& scenename);

	KX_Scene *CreateScene(Scene *scene);
	KX_Scene *CreateScene(const std::string& scenename);

	void AddScene(KX_Scene *scene);
	void PostProcessScene(KX_Scene *scene);
	void DestructScene(KX_Scene *scene);

	/// asynchronous: see PendingScene.
	void ConvertAndAddScene(const std::string& scenename, bool overlay, bool asynchronous = false);
	/// Free the scenes still compiling their shaders (engine stop).
	void DestructPendingScenes();
	void RemoveScene(const std::string& scenename);
	bool ReplaceScene(const std::string& oldscene, const std::string& newscene);
	void SuspendScene(const std::string& scenename);
	void ResumeScene(const std::string& scenename);

	/**
	 * Processes all scheduled scene activity (replace, then remove, then add), in that fixed
	 * order. Requests engine exit if no scenes remain afterward.
	 */
	void ProcessScheduledScenes();
};

#endif  // __KX_SCENESCHEDULER_H__
