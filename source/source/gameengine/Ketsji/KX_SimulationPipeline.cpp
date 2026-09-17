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

/** \file KX_SimulationPipeline.cpp
 *  \ingroup ketsji
 */

#include "KX_SimulationPipeline.h"
#include "KX_KetsjiEngine.h"
#include "KX_Scene.h"
#include "KX_Globals.h"
#include "EXP_ListValue.h"
#include "PHY_IPhysicsEnvironment.h"

KX_SimulationPipeline::KX_SimulationPipeline(KX_KetsjiEngine *engine)
	:m_engine(engine)
{
}

void KX_SimulationPipeline::Update()
{
	// for each scene, call the proceed functions
	for (KX_Scene *scene : m_engine->GetScenes()) {
		m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_overhead);
		KX_SetActiveScene(scene);
		/* Suspension holds the physics and logic processing for an
		 * entire scene. Objects can be suspended individually, and
		 * the settings for that precede the logic and physics
		 * update. */
		m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_services);

		scene->UpdateObjectActivity();

		// If we do not need Animations yet pass them.
		if (m_engine->NeedsAnimation()) {

			if (!scene->IsSuspended()) {
				m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_animations);
				const bool animationsRan = m_engine->UpdateAnimations(scene);
				m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_animations_deform);
				if (animationsRan) {
					scene->UpdateAnimationDeformers();
				}
			}
		}

		if (!scene->IsSuspended()) {
			// Cutscene time is game logic time, so pause/suspend and fixed-timestep
			// behavior match the rest of the scene simulation. The scene retains
			// crossed events until the native action dispatcher consumes them.
			scene->UpdateCutscene(m_engine->GetLogicTime());
			scene->DispatchCutsceneEvents();

			// Process sensors, and controllers
			m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_logic);
			scene->LogicBeginFrame(m_engine->GetLogicTime(), m_engine->GetFrameStep());
		}
		else {
			m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_overhead);
			scene->SetSuspendedDelta(scene->GetSuspendedDelta() + m_engine->GetFrameStep());
		}

		if (!scene->IsSuspended()) {
			scene->RunDrawingCallbacks(KX_Scene::THREAD_LOGIC_1, nullptr);
		}

		if (m_engine->NeedsParents()) {
			if (!scene->IsSuspended()) {
				// Scenegraph needs to be updated again, because Logic Controllers
				// can affect the local matrices.
				m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_scenegraph_logic);
				scene->UpdateParents();
			}
		}

		if (!scene->IsSuspended()) {
			// Process actuators
			// Do some cleanup work for this logic frame
			m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_actuators);
			scene->LogicUpdateFrame(m_engine->GetLogicTime());
		}

		if (!scene->IsSuspended()) {
			m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_logic);
			scene->LogicEndFrame();
		}

		// Actuators can affect the scenegraph
		if (m_engine->NeedsParents()) {
			if (!scene->IsSuspended()) {
				m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_scenegraph_actuators);
				scene->UpdateParents();
			}
		}

		if (!scene->IsSuspended()) {
			m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_physics);
			// Perform physics calculations on the scene. This can involve
			// many iterations of the physics solver.
			if (m_engine->GetFlags() & KX_KetsjiEngine::FIXED_FRAMERATE) {
				scene->GetPhysicsEnvironment()->ProceedDeltaTimeCar(m_engine->GetPhysicsTime(), m_engine->GetPhysicsTime());
			} else {
				//this mode is softer physics
				scene->GetPhysicsEnvironment()->ProceedDeltaTime(m_engine->GetPhysicsTime(), m_engine->GetPhysicsTime());
			}
		}
		if (!scene->IsSuspended()) {

			// Publish one shared player/camera reference after physics. Distance-based
			// systems (currently foliage wind) all consume this same frame position.
			scene->UpdateOptimizationReference();

			// Run after physics so the active camera has its final frame position;
			// the scenegraph pass below publishes the light transform for rendering.
			scene->UpdateAutoWorldSun();

			m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_scenegraph_physics);
			scene->UpdateParents();

			// Fase I.2: step every object's GPU particle emitter once per frame (not once
			// per camera -- see RenderCamera). Placed last, after UpdateParents(), so each
			// emitter reads its owning object's freshest world transform.
			m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_particles);
			scene->UpdateGpuParticleEmitters(m_engine->GetPhysicsTime());
		}
	}
}
