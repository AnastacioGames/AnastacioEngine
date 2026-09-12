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
 * The engine ties all game modules together.
 */

/** \file gameengine/Ketsji/KX_KetsjiEngine.cpp
 *  \ingroup ketsji
 */

#ifdef _MSC_VER
#  pragma warning (disable:4786)
#endif

#include <iostream>
#include <sstream>
#include <cctype>
#include <thread>
#include <algorithm>
#include <cmath>

extern "C" {
	#include "BLI_math_base.h"
}

#include "CM_Message.h"

#include <boost/format.hpp>

#include "BLI_task.h"

#include "KX_DebugMode.h"
#include "KX_KetsjiEngine.h"

#include "EXP_ListValue.h"
#include "EXP_IntValue.h"
#include "EXP_BoolValue.h"
#include "EXP_FloatValue.h"

#include "RAS_BucketManager.h"
#include "RAS_ParticleBuffer.h" // Per-object GPU particle emitters, see KX_GameObject::GetParticleBuffer.
#include "RAS_Rasterizer.h"
#include "RAS_ICanvas.h"
#include "RAS_OffScreen.h"
#include "GPU_texture.h"
#include "RAS_ILightObject.h"
#include "SCA_IInputDevice.h"
#include "KX_Camera.h"
#include "KX_GameObject.h"
#include "KX_LightObject.h"
#include "KX_Globals.h"
#include "KX_PythonJoystick.h"
#include "KX_PyConstraintBinding.h"
#include "PHY_IPhysicsEnvironment.h"
#include "PHY_IVehicle.h"

#include "KX_NetworkMessageScene.h"

#include "DEV_Joystick.h" // for DEV_Joystick::HandleEvents
#include "KX_PythonInit.h" // for updatePythonJoysticks and getPythonJoystick

#include "KX_WorldInfo.h"

#include "BL_Converter.h"
#include "BL_SceneConverter.h"

#include "RAS_FramingManager.h"
#include "DNA_world_types.h"
#include "DNA_scene_types.h"

#include "KX_NavMeshObject.h"
#include "KX_ParticleDebugUI.h"
#include "KX_Scene.h"
#include "KX_2DFilterManager.h"
#include "RAS_2DFilter.h"

#include "KX_Imgui.h"
#include "KX_ShadowRenderer.h"
#include "KX_SimulationPipeline.h"
#include "KX_SceneScheduler.h"
#include "KX_DebugRenderer.h"

#define DEFAULT_LOGIC_TIC_RATE 60.0

static constexpr unsigned int STATIC_SHADOW_SETTLE_FRAMES = 10;

KX_ExitInfo::KX_ExitInfo()
	:m_code(NO_REQUEST)
{
}

const std::string KX_KetsjiEngine::m_profileLabels[tc_numCategories] = {
	"Physics", // tc_physics
	"Logic", // tc_logic
	"Animations", // tc_animations
	"Skinning", // tc_animations_deform
	"CameraCulling", // tc_network
	"UpdateParents", // tc_scenegraph
	"MainRender", // tc_rasterizer
	"Shadows", // tc_shadows
	"ShadowCulling", // tc_shadowculling
	"CollisionDepth", // tc_collisiondepth
	"TextureRenderers", // tc_texturerenderers
	"ParticleUpdate", // tc_particles
	"Actuators", // tc_actuators
	"Input", // tc_input
	"UpdateParents (Logic)", // tc_scenegraph_logic
	"UpdateParents (Actuators)", // tc_scenegraph_actuators
	"UpdateParents (Physics)", // tc_scenegraph_physics
	"LightUpdate", // tc_lightupdate
	"Filters2D", // tc_filters2d
	"ActivityCulling", // tc_services
	"Overhead", // tc_overhead
	"GPU Latency", // tc_latency
	"Sleeping" // tc_outside
};

const std::string KX_KetsjiEngine::m_renderQueriesLabels[QUERY_MAX] = {
	"Samples:", // QUERY_SAMPLES
	"Primitives:", // QUERY_PRIMITIVES
	"Time:" // QUERY_TIME
};

/**
 * Constructor of the Ketsji Engine
 */
KX_KetsjiEngine::KX_KetsjiEngine()
    :m_tottime(0.016f),
    m_rendertimeaverage(0.016f),
    m_animationtimeaverage(0.016f),
    m_CustomMouseCursor(nullptr),
	m_canvas(nullptr),
	m_rasterizer(nullptr),
	m_converter(nullptr),
	m_imgui(nullptr),
	m_debugMode(nullptr),
	m_networkMessageManager(nullptr),
#ifdef WITH_PYTHON
	m_pyprofiledict(PyDict_New()),
#endif
	m_inputDevice(nullptr),
	m_pythonMouse(nullptr),
	m_particleDebugUIVisible(true),
	m_particleDebugUIWasActive(false),
	m_scenes(new EXP_ListValue<KX_Scene>()),
	m_bInitialized(false),
	m_staticSplitSettleFrames(0),
	m_shadowRenderer(new KX_ShadowRenderer(this)),
	m_renderPipeline(new KX_RenderPipeline(this)),
	m_simulationPipeline(new KX_SimulationPipeline(this)),
	m_sceneScheduler(new KX_SceneScheduler(this)),
	m_debugRenderer(new KX_DebugRenderer(this)),
	m_flags(AUTO_ADD_DEBUG_PROPERTIES),
	m_frameTime(0.0f),
	m_clockTime(0.0f),
	m_timescale(1.0f),
	m_previousRealTime(0.0f),
	m_logictimestart(0.0f),
	m_logicframetime(0.0f),
	m_overframetime(0.0f),
	m_rendertime(0.0f),
	m_lastrendertime(0.0f),
	m_rendertimestart(0.0f),
	m_overrendertime(0.0f),
	m_animationtime(0.0f),
	m_lastanimationtime(0.0f),
	m_animationtimestart(0.0f),
	m_overanimationtime(0.0f),
	m_deltatime(0.0f),
	m_framestep(0.0f),
	m_sleeptime(0.0f),
	m_timeUnderRate(0.0f),
	m_maxLogicFrame(5),
	m_useFixedTimestep(false),
	m_simAccumulator(0.0),
	m_accumulatorPreviousRealTime(0.0),
	m_maxPhysicsFrame(true),
	m_shadowCullingEnabled(true),
	m_ticrate(DEFAULT_LOGIC_TIC_RATE),
	m_deltaTime(0.016f),
	m_anim_framerate(25.0),
	m_needsRender(true),
	m_needsAnimation(true),
	m_needsParents(true),
	m_doRender(true),
	m_exitKey(SCA_IInputDevice::ENDKEY),
	m_dynamicResolutionQuery(RAS_Query::TIME),
	m_dynamicResolutionEnabled(false),
	m_dynamicResolutionQueryActive(false),
	m_dynamicResolutionQueryPending(false),
	m_dynamicResolutionTargetFPS(60),
	m_dynamicResolutionMinScale(0.5f),
	m_dynamicResolutionMaxScale(1.0f),
	m_dynamicResolutionStep(0.05f),
	m_dynamicResolutionSmoothedGpuMs(0.0f),
	m_dynamicResolutionCooldown(0),
	m_average_framerate(0.0),
	m_showBoundingBox(KX_DebugOption::DISABLE),
	m_showArmature(KX_DebugOption::DISABLE),
	m_showCameraFrustum(KX_DebugOption::DISABLE),
	m_showShadowFrustum(KX_DebugOption::DISABLE),
	m_showVehicleDebug(KX_DebugOption::DISABLE),
	m_globalsettings({0}),
	m_taskscheduler(BLI_task_scheduler_create(TASK_SCHEDULER_AUTO_THREADS)),
	m_logger(KX_TimeCategoryLogger(m_clock, 25))
{
	for (unsigned short i = tc_first; i < tc_numCategories; i++) {
		m_logger.AddCategory((KX_TimeCategory)i);
	}

	m_renderQueries.emplace_back(RAS_Query::SAMPLES);
	m_renderQueries.emplace_back(RAS_Query::PRIMITIVES);
	m_renderQueries.emplace_back(RAS_Query::TIME);
}

/**
 *	Destructor of the Ketsji Engine, release all memory
 */
KX_KetsjiEngine::~KX_KetsjiEngine()
{
#ifdef WITH_PYTHON
	Py_CLEAR(m_pyprofiledict);
#endif

	if (m_taskscheduler) {
		BLI_task_scheduler_free(m_taskscheduler);
	}

	FreeCustomMouseCursor(m_CustomMouseCursor);
	m_CustomMouseCursor = nullptr;

	m_scenes->Release();
}

void KX_KetsjiEngine::SetInputDevice(SCA_IInputDevice *inputDevice)
{
	BLI_assert(inputDevice);
	m_inputDevice = inputDevice;
}

void KX_KetsjiEngine::SetPythonMouse(KX_PythonMouse *pythonMouse)
{
	BLI_assert(pythonMouse);
	m_pythonMouse = pythonMouse;
}

void KX_KetsjiEngine::SetCanvas(RAS_ICanvas *canvas)
{
	BLI_assert(canvas);
	m_canvas = canvas;
}

void KX_KetsjiEngine::SetRasterizer(RAS_Rasterizer *rasterizer)
{
	BLI_assert(rasterizer);
	m_rasterizer = rasterizer;
}

void KX_KetsjiEngine::SetImgui(KX_Imgui *imgui)
{
	BLI_assert(imgui);
	m_imgui = imgui;
}

void KX_KetsjiEngine::SetDebugMode(KX_DebugMode *debugmode)
{
	BLI_assert(debugmode);
	m_debugMode = debugmode;
}

void KX_KetsjiEngine::SetNetworkMessageManager(KX_NetworkMessageManager *manager)
{
	BLI_assert(manager);
	m_networkMessageManager = manager;
}

void KX_KetsjiEngine::FreeCustomMouseCursor(CustomMouseCursor *cursor)
{
	if (!cursor) {
		return;
	}

	// cursor->m_tex is NOT owned here: GPU_texture_from_blender() caches it on
	// the source Image (ima->gputexture[]) and hands back that same pointer on
	// every call for the same image, without any refcount bump for the loan.
	// Freeing it from here would decrement a count the cursor never
	// incremented and leave the Image's cache holding a dangling pointer,
	// crashing the next time that image's texture is looked up anywhere
	// (confirmed: reproduces EXCEPTION_ACCESS_VIOLATION when the same cursor
	// image is set twice). Only the small CustomMouseCursor struct is ours.
	delete cursor;
}

void KX_KetsjiEngine::SetCustomMouseCursor(CustomMouseCursor *customCursor)
{
	if (m_CustomMouseCursor && customCursor) {
		customCursor->m_visible = m_CustomMouseCursor->m_visible; // pass visible state.
	}

	FreeCustomMouseCursor(m_CustomMouseCursor);
	m_CustomMouseCursor = customCursor;
}

#ifdef WITH_PYTHON
PyObject *KX_KetsjiEngine::GetPyProfileDict()
{
	Py_INCREF(m_pyprofiledict);
	return m_pyprofiledict;
}
#endif

void KX_KetsjiEngine::SetConverter(BL_Converter *converter)
{
	BLI_assert(converter);
	m_converter = converter;
}

void KX_KetsjiEngine::StartEngine()
{
	// Reset the clock to start at 0.0.
	m_clock.Reset();
	m_staticSplitSettleFrames = 0;
	m_simAccumulator = 0.0;
	m_accumulatorPreviousRealTime = m_clock.GetTimeSecond();

	/* Pure-math self-test for CSM frustum fitting, no OpenGL/scene dependency
	 * (see Plano 3, "testes matematicos do CSM sem depender de OpenGL"). Cheap
	 * and side-effect-free, so it runs once per game start rather than only in
	 * debug builds. */
	KX_ShadowRenderer::SelfTestCascadeShadowMath();

	m_bInitialized = true;

	FrameTiming();

	m_renderrate = 1.0 / m_ticrate;
	m_animationrate = 1.0 / m_ticrate;

	// Initialize Debug Mode (ImGui)
	if (m_flags & (SHOW_DEBUG_MODE)) {
		/* Set the activeCamera by default (DebugM -> Scene -> Cameras) */
		for (int i = 0; i < KX_GetActiveScene()->GetCameraList()->GetCount(); i++) {
			if (KX_GetActiveScene()->GetCameraList()->GetValue(i) == KX_GetActiveScene()->GetActiveCamera()) {
				m_debugMode->imgui_cameraSelected = i;
				break;
			}
		}
		m_debugMode->LoadDebugMode_Values();
	}

	// for each scene, update start init from speakers
	for (KX_Scene *scene : m_scenes) {
		scene->StartInitSpeakers();
	}
}

void KX_KetsjiEngine::BeginFrame()
{
	if (m_flags & SHOW_RENDER_QUERIES) {
		m_logger.StartLog(tc_overhead);

		for (RAS_Query& query : m_renderQueries) {
			query.Begin();
		}
	}

	m_logger.StartLog(tc_rasterizer);

	m_rasterizer->BeginFrame(m_logicTime);

	m_canvas->BeginDraw();
	UpdateDynamicResolution();
}

void KX_KetsjiEngine::EndFrame()
{
	if (m_needsRender) {
		m_logger.StartLog(tc_rasterizer);
		m_rasterizer->MotionBlur();
	}
	/// main frame timings
	UpdateSleepTime();

	if (m_needsRender) {// needed or profile bugs

		if (m_imgui) {
			if (m_flags & SHOW_RENDER_QUERIES) {
				for (RAS_Query& query : m_renderQueries) {
					query.End();
				}
			}
			// Show profiling info
			if (m_flags & (SHOW_PROFILE | SHOW_FRAMERATE | SHOW_RENDER_QUERIES)) {
				m_debugMode->RenderDebugProperties();
			}
			if ((m_flags & SHOW_DEBUG_MODE)) {
				m_debugMode->RenderImguiDebugMode();
			}
			// Fase L: automatic GPU particle debug overlay, one ImGui window per object with
			// gpu_particles.use_debug_ui checked -- see KX_ParticleDebugUI.
			if (m_particleDebugUIVisible) {
				for (KX_Scene *scene : m_scenes) {
					for (KX_GameObject *obj : scene->GetGpuParticleObjects()) {
						RAS_ParticleBuffer *buf = obj->GetParticleBuffer();
						if (buf && buf->GetDebugUI()) {
							if (KX_ParticleDebugUI::Draw(obj, buf)) {
								KX_ParticleDebugUI::ApplyToBlend(obj, buf);
							}
						}
					}
				}
			}
			m_imgui->Render();
		}

		m_logger.StartLog(tc_rasterizer);
		m_rasterizer->EndFrame();

		if (m_dynamicResolutionQueryActive) {
			m_dynamicResolutionQuery.End();
			m_dynamicResolutionQueryActive = false;
			m_dynamicResolutionQueryPending = true;
		}

		m_logger.StartLog(tc_overhead);
		m_canvas->FlushScreenshots(m_rasterizer);

		// swap backbuffer (drawing into this buffer) <-> front/visible buffer
		m_logger.StartLog(tc_latency);
		m_canvas->SwapBuffers();
		m_logger.StartLog(tc_rasterizer);

		m_canvas->EndDraw();
		m_logger.StartLog(tc_overhead);
	}
}

void KX_KetsjiEngine::UpdateDynamicResolution()
{
	if (!m_dynamicResolutionEnabled) {
		m_dynamicResolutionQueryPending = false;
		m_canvas->SetRenderScale(1.0f);
		return;
	}

	/* GL_TIME_ELAPSED cannot overlap the query used by SHOW_RENDER_QUERIES. Preserve that
	 * diagnostic path exactly; it temporarily pauses automatic adjustments instead of risking
	 * GL_INVALID_OPERATION or changing the debug measurement's scope. */
	if (m_flags & SHOW_RENDER_QUERIES) {
		return;
	}

	if (m_dynamicResolutionQueryPending && m_dynamicResolutionQuery.Available()) {
		const float gpuMs = (float)m_dynamicResolutionQuery.ResultNoWait() / 1000000.0f;
		m_dynamicResolutionQueryPending = false;
		m_dynamicResolutionSmoothedGpuMs = (m_dynamicResolutionSmoothedGpuMs == 0.0f) ? gpuMs :
		                                  (m_dynamicResolutionSmoothedGpuMs * 0.9f + gpuMs * 0.1f);

		if (m_dynamicResolutionCooldown > 0) {
			--m_dynamicResolutionCooldown;
		}
		else {
			const float targetMs = 1000.0f / (float)m_dynamicResolutionTargetFPS;
			float scale = m_canvas->GetRenderScale();
			if (m_dynamicResolutionSmoothedGpuMs > targetMs * 1.05f) {
				scale = std::max(m_dynamicResolutionMinScale, scale - m_dynamicResolutionStep);
			}
			else if (m_dynamicResolutionSmoothedGpuMs < targetMs * 0.85f) {
				scale = std::min(m_dynamicResolutionMaxScale, scale + m_dynamicResolutionStep);
			}
			else {
				scale = m_canvas->GetRenderScale();
			}

			if (scale != m_canvas->GetRenderScale()) {
				m_canvas->SetRenderScale(scale);
				m_dynamicResolutionCooldown = 10;
			}
		}
	}

	if (!m_dynamicResolutionQueryPending) {
		m_dynamicResolutionQuery.Begin();
		m_dynamicResolutionQueryActive = true;
	}
}

bool KX_KetsjiEngine::NextFrame()
{
	m_logger.StartLog(tc_input);

	if (m_inputDevice) {
		//clear mouse
		m_inputDevice->ReleaseMoveEvent();
	}
	
	if (m_needsRender) {
		if (m_imgui) {
			// Started here (before logic runs) so Python game-logic controllers can safely
			// call into imgui.* this tick; ImGui::Render() still happens later in EndFrame().
			m_imgui->NextFrame();
		}

		// Fase L: GPU particle debug overlay (KX_ParticleDebugUI) -- force SHOW_GAME_UI on
		// while any object has gpu_particles.use_debug_ui checked, same edge-triggered on/off
		// pattern the Python ImGui menus use with imgui.set_game_ui_open(). F9 hides/reshows
		// the windows without needing to uncheck the DNA flag.
		bool particleDebugEnabledSomewhere = false;
		for (KX_Scene *scene : m_scenes) {
			for (KX_GameObject *obj : scene->GetGpuParticleObjects()) {
				RAS_ParticleBuffer *buf = obj->GetParticleBuffer();
				if (buf && buf->GetDebugUI()) {
					particleDebugEnabledSomewhere = true;
					break;
				}
			}
			if (particleDebugEnabledSomewhere) {
				break;
			}
		}
		if (particleDebugEnabledSomewhere &&
		    m_inputDevice->GetInput(SCA_IInputDevice::F9KEY).Find(SCA_InputEvent::JUSTACTIVATED)) {
			m_particleDebugUIVisible = !m_particleDebugUIVisible;
		}
		bool particleDebugActive = particleDebugEnabledSomewhere && m_particleDebugUIVisible;
		if (particleDebugActive) {
			SetFlag(SHOW_GAME_UI, true);
		}
		else if (m_particleDebugUIWasActive) {
			SetFlag(SHOW_GAME_UI, false);
		}
		m_particleDebugUIWasActive = particleDebugActive;

		// process events in debugmode, with show profile, or with the game UI open.
		if ((m_flags & SHOW_DEBUG_MODE) || (m_flags & SHOW_PROFILE) || (m_flags & SHOW_GAME_UI)) {
			m_imgui->ProcessInputEvents();
		}
		if ((m_flags & SHOW_DEBUG_MODE)) {
			m_debugMode->ProcessDebugEvents();

			/* Allow Mouse */
			if (m_inputDevice->GetInput(SCA_IInputDevice::F1KEY).Find(SCA_InputEvent::JUSTRELEASED)) {
				m_canvas->ToggleDebugModeAllowMouse();

				if (m_canvas && m_canvas->GetDebugModeAllowMouse()) {
					m_canvas->SetMouseState(RAS_ICanvas::MOUSE_NORMAL);
				}
				else {
					m_canvas->SetMouseState(RAS_ICanvas::MOUSE_INVISIBLE);
				}
			}
		}

		/* Game UI (ImGui menus scripted from Python) wants the mouse free while open. */
		bool gameUIOpen = (m_flags & SHOW_GAME_UI) != 0;
		if (gameUIOpen != m_prevGameUIOpen) {
			m_canvas->RequestMouseVisible(RAS_ICanvas::MOUSE_REQ_GAME_UI, gameUIOpen);
			m_canvas->SetMouseState(m_canvas->GetMouseVisibleRequested() ? RAS_ICanvas::MOUSE_NORMAL : RAS_ICanvas::MOUSE_INVISIBLE);
			m_prevGameUIOpen = gameUIOpen;
		}
	}
	m_logger.StartLog(tc_overhead);
#ifdef WITH_SDL
	// Handle all SDL Joystick events here to share them for all scenes properly.
	short addrem[JOYINDEX_MAX] = {0};
	if (DEV_Joystick::HandleEvents(addrem)) {
#  ifdef WITH_PYTHON
		updatePythonJoysticks(addrem);
#  endif  // WITH_PYTHON
	}
#endif  // WITH_SDL


	// for each scene, call the proceed functions
	if (m_useFixedTimestep) {
		// Plano 8: fixed-timestep accumulator. m_framestep is the fixed logical step
		// (set by FrameTiming(), already m_timestep * m_timescale); here we measure real
		// elapsed time independently of m_previousRealTime/m_deltatime (owned by the
		// legacy sleep-based catch-up below) and run as many whole steps as are owed,
		// capped at m_maxLogicFrame to avoid a spiral of death under a stall.
		double now = m_clock.GetTimeSecond();
		double realDelta = now - m_accumulatorPreviousRealTime;
		m_accumulatorPreviousRealTime = now;
		m_simAccumulator += realDelta * m_timescale;

		int steps = 0;
		while (m_simAccumulator >= m_framestep && steps < m_maxLogicFrame) {
			m_simulationPipeline->Update();
			m_simAccumulator -= m_framestep;
			++steps;
		}
		double maxBacklog = m_framestep * m_maxLogicFrame;
		if (m_simAccumulator > maxBacklog) {
			m_simAccumulator = maxBacklog;
		}
	}
	else {
		m_simulationPipeline->Update();
	}
	if (m_inputDevice) {
		m_logger.StartLog(tc_overhead);
		// update system devices
		m_inputDevice->ClearInputs();
	}
	// Process PythonJoystick Inputs
	for (unsigned short i = 0; i < JOYINDEX_MAX; ++i) {
		KX_PythonJoystick *joystick = (KX_PythonJoystick*)getPythonJoystick(i);
		if (!joystick) {
			continue;
		}
		
		joystick->UpdateJoystickEvents();
	}
	

	m_logger.StartLog(tc_overhead);
	m_networkMessageManager->ClearMessages();


	m_converter->ProcessScheduledLibraries();

	// scene management
	m_sceneScheduler->ProcessScheduledScenes();

	if (!m_doRender) {
		UpdateSleepTime();
	}


	return m_doRender;
}

void KX_KetsjiEngine::UpdateSleepTime()
{
	m_logger.StartLog(tc_outside);
	ClockTiming();
	m_sleeptime = 2.0;
	if (m_timestep > m_deltatime - m_overframetime + 6e-6) {
		while (m_timestep > m_deltatime - m_overframetime + 6e-6) {
			if (m_timestep > (m_deltatime * 1.5)) {
				m_sleeptime += 2.0;
				m_timeUnderRate = (((m_timestep - m_deltatime) * m_maxLogicFrame) / m_sleeptime);
				if (m_timeUnderRate < 1e-6) {
					m_timeUnderRate = 1e-6;
				}
				std::this_thread::sleep_for(std::chrono::milliseconds((long)(m_timeUnderRate)));
				ClockTiming();
			}
			else if (m_timestep > (m_deltatime * 1.2)) {
				m_sleeptime += 4.0;
				m_timeUnderRate = (((m_timestep - m_deltatime) * m_maxLogicFrame) / m_sleeptime);
				if (m_timeUnderRate < 1e-6) {
					m_timeUnderRate = 1e-6;
				}
				std::this_thread::sleep_for(std::chrono::milliseconds((long)(m_timeUnderRate)));
				ClockTiming();
			}
			else {
				m_sleeptime += 40.0;
				m_timeUnderRate = (((m_timestep - m_deltatime) * m_maxLogicFrame) / m_sleeptime);
				if (m_timeUnderRate < 1e-6) {
					m_timeUnderRate = 1e-6;
				}
				std::this_thread::sleep_for(std::chrono::milliseconds((long)(m_timeUnderRate)));
				ClockTiming();
			}
		}
		// Caught up: clear the accumulated logic-frame overtime.
		m_overframetime = 0.0;
	}
	else {
		m_overframetime = m_overframetime * 0.5;
	}

	// Go to next profiling measurement, time spent after this call is shown in the next frame.
	m_logger.NextMeasurement();
	m_logger.StartLog(tc_overhead);

	// Get logic frame time.
	m_logicframetime = m_clock.GetTimeSecond();
	m_tottime = m_logicframetime - m_logictimestart;
	m_logictimestart = m_logicframetime;
	m_animationtime = m_logicframetime;
	m_rendertime = m_logicframetime;
	m_lastrendertime = m_rendertime - m_rendertimestart;
	FrameOver(); // update m_overframetime (accumulated drift vs. m_timestep) for the legacy sleep-based catch-up above
	// If we do not need render yet pass it.
	if (m_doRender && m_lastrendertime + m_overrendertime > m_renderrate) {
		m_needsRender = true;
		// get the render time for next time
		m_rendertimestart = m_rendertime;
		m_overrendertime = (m_lastrendertime - m_renderrate + m_overrendertime);
		if (m_flags & (SHOW_FRAMERATE)) {
			m_rendertimeaverage = ((m_rendertimeaverage * (m_ticrate - 1.0)) + m_lastrendertime) / m_ticrate;
		}
		if (m_overrendertime > (1.5 / m_renderrate)) {
			m_overrendertime = 1.5 / m_renderrate;
		}
	}
	else {
		// no render this time run endframe for timings
		m_needsRender = false;
	}

	// Get last Animation start time.
	m_lastanimationtime = m_animationtime - m_animationtimestart;
	// If we do not need render yet pass it.
	if (m_doRender && m_lastanimationtime + m_overanimationtime > m_animationrate) {
		m_needsAnimation = true;
		// get the render time for next time
		m_animationtimestart = m_animationtime;
		m_overanimationtime = ((m_lastanimationtime - m_animationrate) + m_overanimationtime);
		if (m_flags & (SHOW_FRAMERATE)) {
			m_animationtimeaverage = ((m_animationtimeaverage * (m_ticrate - 1.0)) + m_lastanimationtime) / m_ticrate;
		}
		if (m_overanimationtime > (1.5 / m_animationrate)) {
			m_overanimationtime = 1.5 / m_animationrate;
		}
	}
	else {
		m_needsAnimation = false;
	}

	if (m_tottime < 1e-3) {
		m_tottime = 1e-3;
	}
#ifdef WITH_PYTHON
	for (unsigned short i = tc_first; i < tc_numCategories; ++i) {
		double time = m_logger.GetAverage((KX_TimeCategory)i);
		PyObject *val = PyTuple_New(2);
		PyTuple_SetItem(val, 0, PyFloat_FromDouble(time * 1000.0));
		PyTuple_SetItem(val, 1, PyFloat_FromDouble(time / m_tottime * 100.0));

		PyDict_SetItemString(m_pyprofiledict, m_profileLabels[i].c_str(), val);
		Py_DECREF(val);
	}
#endif

	FrameTiming();
}

void KX_KetsjiEngine::Render()
{
	m_renderPipeline->Render();
}

void KX_KetsjiEngine::RequestExit(KX_ExitInfo::Code code)
{
	RequestExit(code, "");
}

void KX_KetsjiEngine::RequestExit(KX_ExitInfo::Code code, const std::string& fileName)
{
	m_exitInfo.m_code = code;
	m_exitInfo.m_fileName = fileName;
}

const KX_ExitInfo& KX_KetsjiEngine::GetExitInfo() const
{
	return m_exitInfo;
}

void KX_KetsjiEngine::EnableCameraOverride(const std::string& forscene, const mt::mat3& orientation,
		const mt::vec3& position, const RAS_CameraData& camdata)
{
	SetFlag(CAMERA_OVERRIDE, true);

	m_overrideSceneName = forscene;
	m_overrideCamOrientation = orientation;
	m_overrideCamPosition = position;
	m_overrideCamData = camdata;
}


void KX_KetsjiEngine::GetSceneViewport(KX_Scene *scene, KX_Camera *cam, const RAS_Rect& displayArea, RAS_Rect& area, RAS_Rect& viewport)
{
	// In this function we make sure the rasterizer settings are up-to-date.
	// We compute the viewport so that logic using this information is up-to-date.

	// Note we postpone computation of the projection matrix
	// so that we are using the latest camera position.

	if (cam->UseViewport()) {
		area = cam->GetViewport();
	}
	else {
		area = displayArea;
	}

	RAS_FramingManager::ComputeViewport(scene->GetFramingType(), area, viewport);
}

bool KX_KetsjiEngine::UpdateAnimations(KX_Scene *scene)
{
	if (scene->IsSuspended()) {
		return false;
	}

	return scene->UpdateAnimations(m_animationsTime, (m_flags & RESTRICT_ANIMATION) != 0);
}

bool KX_KetsjiEngine::IsStaticShadowSettled() const
{
	return m_staticSplitSettleFrames >= STATIC_SHADOW_SETTLE_FRAMES;
}

void KX_KetsjiEngine::StopEngine()
{
	if (m_bInitialized) {
		m_converter->FinalizeAsyncLoads();

		while (m_scenes->GetCount() > 0) {
			KX_Scene *scene = m_scenes->GetFront();
			m_sceneScheduler->DestructScene(scene);
			// WARNING: here the scene is a dangling pointer.
			m_scenes->Remove(0);
		}

		// cleanup all the stuff
		m_rasterizer->Exit();
	}

	// Shutdown KX_Imgui
	if (m_imgui) {
		m_imgui->Stop();

		// Save variables from KX_DebugMode.
		if (m_flags & (SHOW_DEBUG_MODE)) {
			m_debugMode->SaveDebugMode_Values();
		}
	}
}

// Scene Management is able to switch between scenes
// and have several scenes running in parallel
void KX_KetsjiEngine::AddScene(KX_Scene *scene)
{
	m_sceneScheduler->AddScene(scene);
}


void KX_KetsjiEngine::ClockTiming()
{
	m_clockTime = m_clock.GetTimeSecond();
	m_deltatime = m_clockTime - m_previousRealTime;
}


void KX_KetsjiEngine::FrameOver()
{
	m_previousRealTime = m_clockTime;
	if (m_overframetime < 0.0) {
		if (m_timestep < (m_deltatime - m_overframetime)) {
			m_overframetime = (m_timestep - m_deltaTime + m_overframetime + 6e-6);
		}
		else {
			m_overframetime = 0.0;
		}
	}
	else {
		if (m_timestep < (m_deltatime)) {
			m_overframetime = (m_timestep - m_deltatime + 6e-6);
		}
	}
}

void KX_KetsjiEngine::FrameTiming()
{
	m_average_framerate = 1.0 / m_tottime;
	m_timestep = 1.0 / m_ticrate;
	m_framestep = m_timestep * m_timescale;
	m_deltaTime = m_framestep;
	m_frameTime += m_timestep;
	m_logicTime += m_timestep;
	m_physicsTime = m_framestep;
	m_animationsTime += m_timestep;
}


void KX_KetsjiEngine::CreateTemporaryCamera(KX_Scene *scene, bool override_camera) {
	KX_Camera *activecam = nullptr;

	activecam = new KX_Camera(scene, KX_Scene::m_callbacks, override_camera ? m_overrideCamData : RAS_CameraData());
	activecam->SetName("__default__cam__");

	// set transformation
	if (override_camera) {
		activecam->NodeSetLocalPosition(m_overrideCamPosition);
		activecam->NodeSetLocalOrientation(m_overrideCamOrientation);
	}
	else {
		activecam->NodeSetLocalPosition(mt::zero3);
		activecam->NodeSetLocalOrientation(mt::mat3::Identity());
	}

	activecam->NodeUpdate();

	scene->GetCameraList()->Add(CM_AddRef(activecam));
	scene->SetActiveCamera(activecam);
	scene->GetObjectList()->Add(CM_AddRef(activecam));
	scene->GetRootParentList()->Add(CM_AddRef(activecam));
	// done with activecam
	activecam->Release();
}

EXP_ListValue<KX_Scene> *KX_KetsjiEngine::CurrentScenes()
{
	return m_sceneScheduler->CurrentScenes();
}

KX_Scene *KX_KetsjiEngine::FindScene(const std::string& scenename)
{
	return m_sceneScheduler->FindScene(scenename);
}

void KX_KetsjiEngine::ConvertAndAddScene(const std::string& scenename, bool overlay)
{
	m_sceneScheduler->ConvertAndAddScene(scenename, overlay);
}

void KX_KetsjiEngine::RemoveScene(const std::string& scenename)
{
	m_sceneScheduler->RemoveScene(scenename);
}

KX_Scene *KX_KetsjiEngine::CreateScene(Scene *scene)
{
	return m_sceneScheduler->CreateScene(scene);
}

KX_Scene *KX_KetsjiEngine::CreateScene(const std::string& scenename)
{
	return m_sceneScheduler->CreateScene(scenename);
}

bool KX_KetsjiEngine::ReplaceScene(const std::string& oldscene, const std::string& newscene)
{
	return m_sceneScheduler->ReplaceScene(oldscene, newscene);
}

void KX_KetsjiEngine::SuspendScene(const std::string& scenename)
{
	m_sceneScheduler->SuspendScene(scenename);
}

void KX_KetsjiEngine::ResumeScene(const std::string& scenename)
{
	m_sceneScheduler->ResumeScene(scenename);
}

/* A rate must be a finite, strictly positive number: zero or negative values
 * would make downstream code divide by zero or invert the rate's sign, and
 * NaN/infinity propagate silently through every timestep computation. */
static bool KX_IsValidRate(double rate)
{
	return std::isfinite(rate) && rate > 0.0;
}

double KX_KetsjiEngine::GetTicRate()
{
	return m_ticrate;
}

void KX_KetsjiEngine::SetTicRate(double ticrate)
{
	if (!KX_IsValidRate(ticrate)) {
		CM_Warning("invalid logic tic rate (" << ticrate << "), keeping previous value " << m_ticrate);
		return;
	}
	m_ticrate = ticrate;
}


double KX_KetsjiEngine::GetRenderRate()
{
	return 1.0 / m_renderrate;
}

void KX_KetsjiEngine::SetRenderRate(double renderrate)
{
	if (!KX_IsValidRate(renderrate)) {
		CM_Warning("invalid render rate (" << renderrate << "), keeping previous value " << GetRenderRate());
		return;
	}
	m_renderrate = 1.0 / renderrate;
}

double KX_KetsjiEngine::GetAnimationRate()
{
	return 1.0 / m_animationrate;
}

void KX_KetsjiEngine::SetAnimationRate(double animationrate)
{
	if (!KX_IsValidRate(animationrate)) {
		CM_Warning("invalid animation rate (" << animationrate << "), keeping previous value " << GetAnimationRate());
		return;
	}
	m_animationrate = 1.0 / animationrate;
}


double KX_KetsjiEngine::GetTimeScale() const
{
	return m_timescale;
}

void KX_KetsjiEngine::SetTimeScale(double timeScale)
{
	m_timescale = timeScale;
}

int KX_KetsjiEngine::GetMaxLogicFrame()
{
	return m_maxLogicFrame;
}

void KX_KetsjiEngine::SetMaxLogicFrame(int frame)
{
	m_maxLogicFrame = frame;
}

bool KX_KetsjiEngine::GetUseFixedTimestep() const
{
	return m_useFixedTimestep;
}

void KX_KetsjiEngine::SetUseFixedTimestep(bool useFixedTimestep)
{
	if (useFixedTimestep && !m_useFixedTimestep) {
		// Entering the accumulator path: start it from zero backlog and re-sync its real
		// time reference, instead of consuming whatever wall-clock gap piled up while the
		// legacy sleep-based path (not this accumulator) owned catch-up.
		m_simAccumulator = 0.0;
		m_accumulatorPreviousRealTime = m_clock.GetTimeSecond();
	}
	m_useFixedTimestep = useFixedTimestep;
}

bool KX_KetsjiEngine::GetMaxPhysicsFrame()
{
	return m_maxPhysicsFrame;
}

void KX_KetsjiEngine::SetMaxPhysicsFrame(bool frame)
{
	m_maxPhysicsFrame = frame;
}

bool KX_KetsjiEngine::GetShadowCulling()
{
	return m_shadowCullingEnabled;
}

void KX_KetsjiEngine::SetShadowCulling(bool enabled)
{
	m_shadowCullingEnabled = enabled;
}

void KX_KetsjiEngine::SetDynamicResolution(bool enabled,
                                            int targetFPS,
                                            int minScale,
                                            int maxScale,
                                            int step)
{
	m_dynamicResolutionEnabled = enabled;
	m_dynamicResolutionTargetFPS = std::max(1, targetFPS);

	const float minScaleFactor = std::max(0.25f, std::min((float)minScale * 0.01f, 1.0f));
	const float maxScaleFactor = std::max(0.25f, std::min((float)maxScale * 0.01f, 1.0f));
	m_dynamicResolutionMinScale = std::min(minScaleFactor, maxScaleFactor);
	m_dynamicResolutionMaxScale = std::max(minScaleFactor, maxScaleFactor);
	m_dynamicResolutionStep = std::max(0.01f, std::min((float)step * 0.01f, 0.25f));
	m_dynamicResolutionSmoothedGpuMs = 0.0f;
	m_dynamicResolutionCooldown = 0;

	if (!enabled) {
		m_dynamicResolutionQueryPending = false;
	}
}

void KX_KetsjiEngine::SetNeedsParents(bool parents)
{
	m_needsParents = parents;
}

double KX_KetsjiEngine::GetEngineDeltaTime()
{
	return m_deltaTime;
}

double KX_KetsjiEngine::GetAnimFrameRate()
{
	return m_anim_framerate;
}

bool KX_KetsjiEngine::GetFlag(FlagType flag) const
{
	return (m_flags & flag) != 0;
}

void KX_KetsjiEngine::SetFlag(FlagType flag, bool enable)
{
	if (enable) {
		m_flags = (FlagType)(m_flags | flag);
	}
	else {
		m_flags = (FlagType)(m_flags & ~flag);
	}
}

void KX_KetsjiEngine::ToggleFlag(FlagType flag)
{
  if ((m_flags & flag) != 0) {
    m_flags = (FlagType)(m_flags & ~flag);
  }
  else {
    m_flags = (FlagType)(m_flags | flag);
  }
}

double KX_KetsjiEngine::GetClockTime() const
{
	return m_clockTime;
}

void KX_KetsjiEngine::SetClockTime(double externalClockTime)
{
	m_clockTime = externalClockTime;
}

double KX_KetsjiEngine::GetFrameTime() const
{
	return m_frameTime;
}

double KX_KetsjiEngine::GetRealTime() const
{
	return m_clock.GetTimeSecond();
}

void KX_KetsjiEngine::SetAnimFrameRate(double framerate)
{
	m_anim_framerate = framerate;
}

double KX_KetsjiEngine::GetAverageFrameRate()
{
	return m_average_framerate;
}

void KX_KetsjiEngine::SetExitKey(SCA_IInputDevice::SCA_EnumInputs key)
{
	m_exitKey = key;
}

SCA_IInputDevice::SCA_EnumInputs KX_KetsjiEngine::GetExitKey() const
{
	return m_exitKey;
}

void KX_KetsjiEngine::SetRender(bool render)
{
	m_doRender = render;
}

bool KX_KetsjiEngine::GetRender()
{
	return m_doRender;
}

void KX_KetsjiEngine::SetShowBoundingBox(KX_DebugOption mode)
{
	m_showBoundingBox = mode;
}

KX_DebugOption KX_KetsjiEngine::GetShowBoundingBox() const
{
	return m_showBoundingBox;
}

void KX_KetsjiEngine::SetShowArmatures(KX_DebugOption mode)
{
	m_showArmature = mode;
}

KX_DebugOption KX_KetsjiEngine::GetShowArmatures() const
{
	return m_showArmature;
}

void KX_KetsjiEngine::SetShowCameraFrustum(KX_DebugOption mode)
{
	m_showCameraFrustum = mode;
}

KX_DebugOption KX_KetsjiEngine::GetShowCameraFrustum() const
{
	return m_showCameraFrustum;
}

void KX_KetsjiEngine::SetShowShadowFrustum(KX_DebugOption mode)
{
	m_showShadowFrustum = mode;
}

KX_DebugOption KX_KetsjiEngine::GetShowShadowFrustum() const
{
	return m_showShadowFrustum;
}

void KX_KetsjiEngine::SetShowVehicleDebug(KX_DebugOption mode)
{
	m_showVehicleDebug = mode;
}

KX_DebugOption KX_KetsjiEngine::GetShowVehicleDebug() const
{
	return m_showVehicleDebug;
}

void KX_KetsjiEngine::Resize()
{
	/* extended mode needs to recalculate camera frusta when */
	KX_Scene *firstscene = m_scenes->GetFront();
	const RAS_FrameSettings &framesettings = firstscene->GetFramingType();

	if (framesettings.FrameType() == RAS_FrameSettings::e_frame_extend) {
		for (KX_Scene *scene : m_scenes) {
			KX_Camera *cam = scene->GetActiveCamera();
			cam->InvalidateProjectionMatrix();
		}
	}
}

void KX_KetsjiEngine::SetGlobalSettings(GlobalSettings *gs)
{
	m_globalsettings.glslflag = gs->glslflag;
}

GlobalSettings *KX_KetsjiEngine::GetGlobalSettings()
{
	return &m_globalsettings;
}
