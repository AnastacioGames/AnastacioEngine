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
 *
 */

/** \file KX_KetsjiEngine.h
 *  \ingroup ketsji
 */

#ifndef __KX_KETSJIENGINE_H__
#define __KX_KETSJIENGINE_H__

#include "CM_Clock.h"
#include "EXP_Python.h"
#include "KX_TimeCategoryLogger.h"
#include "KX_WorldInfo.h"
#include "RAS_CameraData.h"
#include "RAS_DebugDraw.h"
#include "RAS_ICanvas.h"
#include "RAS_Query.h"
#include "SCA_IInputDevice.h"  // For SCA_IInputDevice::SCA_EnumInputs.
#include "KX_PythonMouse.h"
#include "KX_RenderPipeline.h"
#include "KX_SimulationPipeline.h"
#include "KX_SceneScheduler.h"
#include "KX_DebugRenderer.h"

#include <memory>
#include <string>
#include <vector>

struct TaskScheduler;
class KX_Scene;
class KX_Camera;
class KX_LightObject;
class RAS_ILightObject;
class BL_Converter;
class KX_GameObject;
class KX_Imgui;
class KX_DebugMode;
class KX_NetworkMessageManager;
class RAS_ICanvas;
class RAS_OffScreen;
class SCA_IInputDevice;
class KX_ShadowRenderer;
template <class T>
class EXP_ListValue;

struct KX_ExitInfo
{
	enum Code {
		NO_REQUEST = 0,
		QUIT_GAME,
		RESTART_GAME,
		START_OTHER_GAME,
		NO_SCENES_LEFT,
		BLENDER_ESC,
		OUTSIDE,
		MAX
	};

	Code m_code;

	/// Extra information on behaviour after exit (e.g starting an other game)
	std::string m_fileName;

	KX_ExitInfo();
};

enum class KX_DebugOption
{
	DISABLE = 0,
	FORCE,
	ALLOW
};

typedef struct {
	int glslflag;
} GlobalSettings;

/**
 * KX_KetsjiEngine is the core game engine class.
 */
class KX_KetsjiEngine : public mt::SimdClassAllocator
{
public:
	enum FlagType
	{
		FLAG_NONE = 0,
		/// Show profiling info on the game display?
		SHOW_PROFILE = (1 << 0),
		/// Show the framerate on the game display?
		SHOW_FRAMERATE = (1 << 1),
		/// Process and show render queries?
		SHOW_RENDER_QUERIES = (1 << 2),
		/// Show debug properties on the game display. (DEPRECATED)
		SHOW_DEBUG_PROPERTIES = (1 << 3),
		/// Whether or not to lock animation updates to the animation framerate?
		RESTRICT_ANIMATION = (1 << 4),
		/// Display of fixed frames?
		FIXED_FRAMERATE = (1 << 5),
		/// BGE relies on a external clock or its own internal clock?
		USE_EXTERNAL_CLOCK = (1 << 6),
		/// Automatic add debug properties to the debug list.
		AUTO_ADD_DEBUG_PROPERTIES = (1 << 7),
		/// Use override camera?
		CAMERA_OVERRIDE = (1 << 8),
		/// Show game debug interface?
		SHOW_DEBUG_MODE = (1 << 9),
		/// Ignore Exit Key by Keyboard?
		IGNORE_EXIT_KEY = (1 << 10),
		/// Show Python-scripted in-game UI (ImGui)?
		SHOW_GAME_UI = (1 << 11)
	};

	enum QueryCategory {
		QUERY_SAMPLES = 0,
		QUERY_PRIMITIVES,
		QUERY_TIME,
		QUERY_MAX
	};

	// Size
	struct CustomMouseCursor {
		/// GPUTexture Containing the custom cursor
		GPUTexture *m_tex;
		int m_size;
		int m_offset_X;
		int m_offset_Y;
		bool m_mipmap;
		bool m_visible;
	};
	/// linked in profiler 
	double m_tottime;
	double m_rendertimeaverage;
	double m_animationtimeaverage;
private:
	/// Struct Containing the custom cursor
	CustomMouseCursor *m_CustomMouseCursor;

	/// Frees the cursor struct itself. Never touches m_tex: it is cached and
	/// owned by the source Image (see the .cpp for why). Safe to call with nullptr.
	static void FreeCustomMouseCursor(CustomMouseCursor *cursor);

	/// 2D Canvas (2D Rendering Device Context)
	RAS_ICanvas *m_canvas;
	/// 3D Rasterizer (3D Rendering)
	RAS_Rasterizer *m_rasterizer;
	/// Global debug draw, mainly used for profiling texts.
	RAS_DebugDraw m_debugDraw;
	BL_Converter *m_converter;
	KX_Imgui	 *m_imgui;
	KX_DebugMode *m_debugMode;
	KX_NetworkMessageManager *m_networkMessageManager;
#ifdef WITH_PYTHON
	PyObject *m_pyprofiledict;
#endif
	SCA_IInputDevice *m_inputDevice;
	KX_PythonMouse *m_pythonMouse;

	/// Fase L: whether the automatic GPU particle debug overlay windows (KX_ParticleDebugUI) are
	/// currently shown; F9 toggles it. Tracked separately from "wasActive last frame" so
	/// SHOW_GAME_UI is only ever force-cleared on the frame debug UI actually stops being used,
	/// same edge-triggered pattern the Python ImGui menus already use with imgui.set_game_ui_open.
	bool m_particleDebugUIVisible;
	bool m_particleDebugUIWasActive;

	CM_Clock m_clock;
	
	/// The current list of scenes.
	EXP_ListValue<KX_Scene> *m_scenes;

	bool m_bInitialized;

	/// Startup render frames before enabling the CSM static/dynamic cache split.
	unsigned int m_staticSplitSettleFrames;

	/// Owns the shadow rendering pipeline (CSM, static/dynamic split, shadow buffers). See
	/// KX_ShadowRenderer and Plano 5 in docs/ketsji-engine-modernization-plan.md.
	std::unique_ptr<KX_ShadowRenderer> m_shadowRenderer;

	/// Owns the per-frame render pipeline (render plan, off-screen composition, per-camera
	/// render, 2D filters). See KX_RenderPipeline and Plano 6 in
	/// docs/ketsji-engine-modernization-plan.md.
	std::unique_ptr<KX_RenderPipeline> m_renderPipeline;
	std::unique_ptr<KX_SimulationPipeline> m_simulationPipeline;

	/// Owns scene add/remove/replace/suspend/convert scheduling. See KX_SceneScheduler and Plano 7
	/// in docs/ketsji-engine-modernization-plan.md.
	std::unique_ptr<KX_SceneScheduler> m_sceneScheduler;

	/// Owns the native debug-draw overlays (camera frustum, vehicle debug). See KX_DebugRenderer
	/// and Plano 7 in docs/ketsji-engine-modernization-plan.md.
	std::unique_ptr<KX_DebugRenderer> m_debugRenderer;

	FlagType m_flags;

	/// SHOW_GAME_UI value on the previous frame, to edge-trigger mouse cursor requests.
	bool m_prevGameUIOpen = false;

	/// current logic game time
	double m_frameTime;
	double m_logicTime;
	double m_physicsTime;
	double m_animationsTime;
	/// game time for the next rendering step
	double m_clockTime;
	/// time scaling parameter. if > 1.0, time goes faster than real-time. If < 1.0, times goes slower than real-time.
	double m_timescale;
	double m_previousRealTime;

	double m_logictimestart;

	double m_logicframetime;

	double m_overframetime;

	double m_rendertime;
	double m_lastrendertime;
	
	double m_rendertimestart;
	double m_overrendertime;
	double m_animationtime;
	double m_lastanimationtime;
	double m_animationtimestart;
	double m_overanimationtime;

	double m_timestep;

	double m_deltatime;

	double m_framestep;

	double m_sleeptime;

	long m_timeUnderRate;

	/// maximum number of consecutive logic frame
	int m_maxLogicFrame;

	/// Plano 8: fixed-timestep accumulator, off by default so behavior is unchanged
	/// until a caller opts in. See docs/ketsji-engine-modernization-plan.md, Plano 8.
	/// When false, NextFrame() keeps the legacy single Update() call per frame with
	/// catch-up handled by sleeping in UpdateSleepTime(), exactly as before this flag
	/// existed. When true, NextFrame() accumulates real elapsed time (scaled by
	/// m_timescale) and calls m_simulationPipeline->Update() once per whole m_framestep
	/// owed, capped at m_maxLogicFrame steps per frame; leftover time above that cap is
	/// dropped to avoid a spiral of death instead of growing unboundedly.
	bool m_useFixedTimestep;
	/// Real time (m_clock seconds) accumulated but not yet consumed by a simulation
	/// step, only meaningful while m_useFixedTimestep is true.
	double m_simAccumulator;
	/// Real time (m_clock seconds) at the previous NextFrame() call, used to measure
	/// the elapsed real time fed into m_simAccumulator. Independent of m_previousRealTime,
	/// which belongs to the legacy sleep-based catch-up in UpdateSleepTime()/FrameOver().
	double m_accumulatorPreviousRealTime;
	/// Deprecated: legacy Python-facing catch-up limit (getMaxPhysicsFrame/setMaxPhysicsFrame).
	/// No longer consumed anywhere; kept only for that API's backward compatibility. Shadow
	/// culling has its own state, m_shadowCullingEnabled, below.
	bool m_maxPhysicsFrame;
	/// Recalculate which objects cast visible shadows every frame (GameData.shadowCulling).
	/// Split out of m_maxPhysicsFrame, which used to double as this flag despite promising an
	/// unrelated physics frame limit.
	bool m_shadowCullingEnabled;
	double m_ticrate;
	double m_renderrate;
	double m_animationrate;
	/// DeltaTime
	double m_deltaTime;
	/// for animation playback only - ipo and action
	double m_anim_framerate;
	bool m_needsRender;
	bool m_needsAnimation;
	bool m_needsParents;

	bool m_doRender;  /* whether or not the scene should be rendered after the logic frame */

	/// Key used to exit the BGE
	SCA_IInputDevice::SCA_EnumInputs m_exitKey;

	KX_ExitInfo m_exitInfo;

	std::string m_overrideSceneName;
	RAS_CameraData m_overrideCamData;
	mt::mat3 m_overrideCamOrientation;
	mt::vec3 m_overrideCamPosition;

	std::vector<RAS_Query> m_renderQueries;
	static const std::string m_renderQueriesLabels[QUERY_MAX];

	/// Opt-in GPU-time controller for the internal render-target scale. It deliberately uses a
	/// separate query from the debug render queries because OpenGL permits only one active
	/// GL_TIME_ELAPSED query at a time.
	RAS_Query m_dynamicResolutionQuery;
	bool m_dynamicResolutionEnabled;
	bool m_dynamicResolutionQueryActive;
	bool m_dynamicResolutionQueryPending;
	int m_dynamicResolutionTargetFPS;
	float m_dynamicResolutionMinScale;
	float m_dynamicResolutionMaxScale;
	float m_dynamicResolutionStep;
	float m_dynamicResolutionSmoothedGpuMs;
	unsigned short m_dynamicResolutionCooldown;

	/// Last estimated framerate
	double m_average_framerate;

	/// Enable debug draw of culling bounding boxes.
	KX_DebugOption m_showBoundingBox;
	/// Enable debug draw armatures.
	KX_DebugOption m_showArmature;
	/// Enable debug draw of camera frustum.
	KX_DebugOption m_showCameraFrustum;
	/// Enable debug light shadow frustum.
	KX_DebugOption m_showShadowFrustum;
	/// Enable native vehicle suspension debug draw.
	KX_DebugOption m_showVehicleDebug;

	/// Settings that doesn't go away with Game Actuator
	GlobalSettings m_globalsettings;

	/// Task scheduler for multi-threading
	TaskScheduler *m_taskscheduler;

	/** Set scene's total pause duration for animations process.
	 * This is done in a separate loop to get the proper state of each scenes.
	 * eg: There's 2 scenes, the first is suspended and the second is active.
	 * If the second scene resume the first, the first scene will be not proceed
	 * in 'NextFrame' for one frame, but set as active.
	 * The render functions, called after and which update animations,
	 * will see the first scene as active and will proceed to it,
	 * but it will cause some negative current frame on actions because of the
	 * total pause duration not set.
	 */
	void UpdateSleepTime();

	/// Update and return the projection matrix of a camera depending on the viewport.
	mt::mat4 GetCameraProjectionMatrix(KX_Scene *scene, KX_Camera *cam, RAS_Rasterizer::StereoMode stereoMode,
			RAS_Rasterizer::StereoEye eye, const RAS_Rect& viewport, const RAS_Rect& area) const;

	void ClockTiming();
	void FrameOver();
	void FrameTiming();
	void UpdateDynamicResolution();
public:
	/// It is necessary to make the function public so that the debug mode can use it
	void CreateTemporaryCamera(KX_Scene *scene, bool override_camera);

	/// Plano 11: made public (was private+friend) so KX_RenderPipeline, which owns the
	/// frame's Render() call, doesn't need friend access just for these two lifecycle calls.
	void BeginFrame();
	void EndFrame();


	KX_KetsjiEngine();
	virtual ~KX_KetsjiEngine();

	/// Categories for profiling display.
	typedef enum {
		tc_first = 0,
		tc_physics = 0,
		tc_logic,
		tc_animations,
		tc_animations_deform,
		tc_network, // culling + LOD update (KX_RenderPipeline::RenderFrame), labeled "CameraCulling" via GetPyProfileDict()
		tc_scenegraph, // unused: never StartLog()'d (superseded by tc_scenegraph_logic/actuators/physics below); still exposed (always 0) via GetPyProfileDict() as "UpdateParents"
		tc_rasterizer,
		tc_shadows,
		tc_shadowculling,
		tc_collisiondepth, // GPU particle screen-space collision depth pass
		tc_texturerenderers, // KX_TextureRendererManager (planar/mirror probes) draw
		tc_particles, // KX_Scene::UpdateGpuParticleEmitters
		tc_actuators, // SCA_LogicManager::UpdateFrame (actuators), via KX_Scene::LogicUpdateFrame
		tc_input, // input polling + ImGui NextFrame/ProcessInputEvents, in NextFrame()
		tc_scenegraph_logic, // UpdateParents() after LogicBeginFrame, before actuators
		tc_scenegraph_actuators, // UpdateParents() after actuators, before physics
		tc_scenegraph_physics, // UpdateParents() after physics, before particle update
		tc_lightupdate, // light distance culling + KX_LightObject::Update(), in RenderShadowBuffers()
		tc_filters2d, // KX_KetsjiEngine::PostRenderScene() up to and including Render2DFilters()
		tc_services, // time spent in miscelaneous activities
		tc_overhead, // catch-all bucket: time between StartLog(tc_overhead) and the next named category's StartLog()
		tc_latency, // time spent waiting on the gpu
		tc_outside, // time spent outside main loop
		tc_numCategories
	} KX_TimeCategory;

	/// Time logger.
	KX_TimeCategoryLogger m_logger;

	/// Labels for profiling display.
	static const std::string m_profileLabels[tc_numCategories];

	/// set the devices and stuff. the client must take care of creating these
	void SetInputDevice(SCA_IInputDevice *inputDevice);
	void SetPythonMouse(KX_PythonMouse *pythonMouse);
	void SetCanvas(RAS_ICanvas *canvas);
	void SetRasterizer(RAS_Rasterizer *rasterizer);
	void SetImgui(KX_Imgui *imgui);
	void SetDebugMode(KX_DebugMode *debugmode);
	void SetNetworkMessageManager(KX_NetworkMessageManager *manager);
	void SetCustomMouseCursor(CustomMouseCursor *customCursor);
#ifdef WITH_PYTHON
	PyObject *GetPyProfileDict();
#endif
	void SetConverter(BL_Converter *converter);
	BL_Converter *GetConverter()
	{
		return m_converter;
	}

	RAS_Rasterizer *GetRasterizer()
	{
		return m_rasterizer;
	}

	RAS_ICanvas *GetCanvas()
	{
		return m_canvas;
	}

	KX_ShadowRenderer *GetShadowRenderer()
	{
		return m_shadowRenderer.get();
	}

	KX_RenderPipeline *GetRenderPipeline()
	{
		return m_renderPipeline.get();
	}

	KX_SimulationPipeline *GetSimulationPipeline()
	{
		return m_simulationPipeline.get();
	}

	KX_SceneScheduler *GetSceneScheduler()
	{
		return m_sceneScheduler.get();
	}

	KX_DebugRenderer *GetDebugRenderer()
	{
		return m_debugRenderer.get();
	}

	EXP_ListValue<KX_Scene> *GetScenes()
	{
		return m_scenes;
	}

	FlagType GetFlags()
	{
		return m_flags;
	}

	/// Plano 11: getters added so KX_RenderPipeline/KX_SimulationPipeline (and other
	/// friend classes) can stop reaching into private state directly, matching the
	/// getter-based access already used for the rest of KX_KetsjiEngine since Plano 4.
	KX_TimeCategoryLogger& GetLogger()
	{
		return m_logger;
	}

	bool NeedsRender() const
	{
		return m_needsRender;
	}

	bool NeedsAnimation() const
	{
		return m_needsAnimation;
	}

	bool NeedsParents() const
	{
		return m_needsParents;
	}

	double GetLogicTime() const
	{
		return m_logicTime;
	}

	double GetPhysicsTime() const
	{
		return m_physicsTime;
	}

	double GetFrameStep() const
	{
		return m_framestep;
	}

	unsigned int GetStaticSplitSettleFrames() const
	{
		return m_staticSplitSettleFrames;
	}

	void IncrementStaticSplitSettleFrames()
	{
		++m_staticSplitSettleFrames;
	}

	const std::string& GetOverrideSceneName() const
	{
		return m_overrideSceneName;
	}

	SCA_IInputDevice *GetInputDevice()
	{
		return m_inputDevice;
	}

	KX_PythonMouse *GetPythonMouse()
	{
		return m_pythonMouse; 
	}

	KX_Imgui *GetImgui()
	{
		return m_imgui;
	}

	KX_DebugMode *GetDebugMode()
	{
		return m_debugMode;
	}

	KX_NetworkMessageManager *GetNetworkMessageManager() const
	{
		return m_networkMessageManager;
	}

	CustomMouseCursor *GetCustomMouseCursor()
	{
		return m_CustomMouseCursor;
	}

	bool HasCustomMouseCursor()
	{
		return (m_CustomMouseCursor != nullptr);
	}

	int GetRenderQueryValue(int value)
	{
		return m_renderQueries[value].Result();
	}

	std::string GetRenderQueryLabel(int value)
	{
		return m_renderQueriesLabels[value];
	}

	TaskScheduler *GetTaskScheduler()
	{
		return m_taskscheduler;
	}

	float GetTimeSecondClock()
	{
		return m_clock.GetTimeSecond();
	}

	/// returns true if an update happened to indicate -> Render
	bool NextFrame();
	/// Render every scene/camera of the frame. See KX_RenderPipeline (Plano 6).
	void Render();

	void StartEngine();
	void StopEngine();

	void RequestExit(KX_ExitInfo::Code code);
	void RequestExit(KX_ExitInfo::Code code, const std::string& fileName);

	const KX_ExitInfo& GetExitInfo() const;

	EXP_ListValue<KX_Scene> *CurrentScenes();
	KX_Scene *FindScene(const std::string& scenename);
	void AddScene(KX_Scene *scene);
	void ConvertAndAddScene(const std::string& scenename, bool overlay);

	void RemoveScene(const std::string& scenename);
	bool ReplaceScene(const std::string& oldscene, const std::string& newscene);
	void SuspendScene(const std::string& scenename);
	void ResumeScene(const std::string& scenename);

	void GetSceneViewport(KX_Scene *scene, KX_Camera *cam, const RAS_Rect& displayArea, RAS_Rect& area, RAS_Rect& viewport);

	void EnableCameraOverride(const std::string& forscene, const mt::mat3& orientation,
			const mt::vec3& position, const RAS_CameraData& camdata);

	// Update animations for object in this scene
	bool UpdateAnimations(KX_Scene *scene);

	bool GetFlag(FlagType flag) const;
	/// Enable or disable a set of flags.
	void SetFlag(FlagType flag, bool enable);
	/// Toggle the flags.
	void ToggleFlag(FlagType flag);

	/*
	 * Returns next render frame game time
	 */
	double GetClockTime(void) const;

	/**
	 * Set the next render frame game time. It will impact also frame time, as
	 * this one is derived from clocktime
	 */
	void SetClockTime(double externalClockTime);

	/**
	 * Returns current logic frame game time
	 */
	double GetFrameTime(void) const;

	/**
	 * Returns the real (system) time
	 */
	double GetRealTime(void) const;

	/**
	 * Gets the number of logic updates per second.
	 */
	double GetTicRate();
	/**
	 * Sets the number of logic updates per second.
	 * Ignores non-finite or non-positive values and keeps the previous rate.
	 */
	void SetTicRate(double ticrate);
	/**
	 * Gets the number of render updates per second.
	 */
	double GetRenderRate();
	/**
	 * Sets the number of render updates per second.
	 * Ignores non-finite or non-positive values and keeps the previous rate.
	 */
	void SetRenderRate(double renderrate);
	/**
	 * Gets the number of render updates per second.
	 */
	double GetAnimationRate();
	/**
	 * Sets the number of render updates per second.
	 * Ignores non-finite or non-positive values and keeps the previous rate.
	 */
	void SetAnimationRate(double animationrate);
	/**
	 * Gets the maximum number of logic frame before render frame
	 */
	int GetMaxLogicFrame();
	/**
	 * Sets the maximum number of logic frame before render frame
	 */
	void SetMaxLogicFrame(int frame);
	/**
	 * Plano 8: whether NextFrame() uses the fixed-timestep accumulator instead of the
	 * legacy single-Update-per-frame path. Off by default; no caller sets this true yet
	 * (no Python/DNA exposure), so this getter/setter pair is currently inert.
	 */
	bool GetUseFixedTimestep() const;
	void SetUseFixedTimestep(bool useFixedTimestep);
	/**
	 * Deprecated: no longer consumed by the engine. Kept only for the legacy
	 * logic.getMaxPhysicsFrame() Python API.
	 */
	bool GetMaxPhysicsFrame();

	void SetNeedsParents(bool parents);
	/**
	 * Deprecated: no longer consumed by the engine. Kept only for the legacy
	 * logic.setMaxPhysicsFrame() Python API. Use SetShadowCulling() for shadow culling.
	 */
	void SetMaxPhysicsFrame(bool frame);
	/**
	 * Gets whether shadow culling (recalculating visible shadow casters every frame) is enabled
	 */
	bool GetShadowCulling();
	/**
	 * Sets whether shadow culling is enabled
	 */
	void SetShadowCulling(bool enabled);
	void SetDynamicResolution(bool enabled, int targetFPS, int minScale, int maxScale, int step);
	/**
	 * Whether enough startup render frames have elapsed to enable the CSM static/dynamic
	 * shadow cache split (see m_staticSplitSettleFrames). Used by KX_ShadowRenderer.
	 */
	bool IsStaticShadowSettled() const;
	/**
	 * Gets deltatime from engine calculation
	 */
	double GetEngineDeltaTime();

	/**
	 * Gets the framerate for playing animations. (actions and ipos)
	 */
	double GetAnimFrameRate();
	/**
	 * Sets the framerate for playing animations. (actions and ipos)
	 */
	void SetAnimFrameRate(double framerate);

	/**
	 * Gets the last estimated average framerate
	 */
	double GetAverageFrameRate();

	/**
	 * Gets the time scale multiplier
	 */
	double GetTimeScale() const;

	/**
	 * Sets the time scale multiplier
	 */
	void SetTimeScale(double timeScale);

	void SetExitKey(SCA_IInputDevice::SCA_EnumInputs key);
	SCA_IInputDevice::SCA_EnumInputs GetExitKey() const;

	/**
	 * Activate or deactivates the render of the scene after the logic frame
	 * \param render	true (render) or false (do not render)
	 */
	void SetRender(bool render);
	/**
	 * Get the current render flag value
	 */
	bool GetRender();

	/// Allow debug bounding box debug.
	void SetShowBoundingBox(KX_DebugOption mode);
	/// Returns the current setting for bounding box debug.
	KX_DebugOption GetShowBoundingBox() const;

	/// Allow debug armatures.
	void SetShowArmatures(KX_DebugOption mode);
	/// Returns the current setting for armatures debug.
	KX_DebugOption GetShowArmatures() const;

	/// Allow debug camera frustum.
	void SetShowCameraFrustum(KX_DebugOption mode);
	/// Returns the current setting for camera frustum debug.
	KX_DebugOption GetShowCameraFrustum() const;

	/// Allow debug light shadow frustum.
	void SetShowShadowFrustum(KX_DebugOption mode);
	/// Returns the current setting for light shadow frustum debug.
	KX_DebugOption GetShowShadowFrustum() const;

	/// Allow native vehicle suspension debug draw.
	void SetShowVehicleDebug(KX_DebugOption mode);
	/// Returns the current setting for vehicle suspension debug draw.
	KX_DebugOption GetShowVehicleDebug() const;

	KX_Scene *CreateScene(const std::string& scenename);
	KX_Scene *CreateScene(Scene *scene);

	GlobalSettings *GetGlobalSettings(void);
	void SetGlobalSettings(GlobalSettings *gs);

	/**
	 * Invalidate all the camera matrices and handle other
	 * needed changes when resized.
	 * It's only called from Blenderplayer.
	 */
	void Resize();
};

#endif  /* __KX_KETSJIENGINE_H__ */
