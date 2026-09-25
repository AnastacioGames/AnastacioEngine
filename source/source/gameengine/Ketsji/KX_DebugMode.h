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
 * The Original Code is Copyright (C) 2022-2024 by Range Engine.
 *
 * The Original Code is: all of this file.
 *
 * ***** END GPL LICENSE BLOCK *****
 *
 */

 /** \file KX_DebugMode.h
  *  \ingroup ketsji
  */

#ifndef KX_DEBUGMODE_H
#  define KX_DEBUGMODE_H

#include <string>
#include "KX_ConsoleWindow.h"
#include "KX_Imgui.h"
#include "KX_VehicleDebugUI.h"

class KX_GameObject;

/* Profile tips. */
/* Must match KX_KetsjiEngine::m_profileLabels order (tc_* enum). */
const std::string profileTips[] = {
    "Time spent on physics calculations.",                                         // tc_physics
    "Time spent on logic bricks and Python code.",                                 // tc_logic
    "Time spent on animation calculations.",                                       // tc_animations
    "Time spent deforming meshes (skinning / armature deform).",                   // tc_animations_deform
    "Time spent on camera culling and LOD update.",                                // tc_network
    "Time spent on parent update (legacy, always 0).",                             // tc_scenegraph
    "Time spent actually rendering the game.",                                     // tc_rasterizer
    "Time spent rendering the shadows.",                                           // tc_shadows
    "Time spent on culling shadows.",                                              // tc_shadowculling
    "Time spent on the GPU particle screen-space collision depth pass.",           // tc_collisiondepth
    "Time spent rendering texture renderers (planar / mirror probes).",            // tc_texturerenderers
    "Time spent updating GPU particle emitters.",                                  // tc_particles
    "Time spent updating actuators.",                                              // tc_actuators
    "Time spent polling input devices and processing UI input.",                   // tc_input
    "Time spent on parent update after logic.",                                    // tc_scenegraph_logic
    "Time spent on parent update after actuators.",                                // tc_scenegraph_actuators
    "Time spent on parent update after physics.",                                  // tc_scenegraph_physics
    "Time spent on light culling and light updates.",                              // tc_lightupdate
    "Time spent on post-render and 2D filters.",                                   // tc_filters2d
    "Time spent on activity culling and system devices.",                          // tc_services
    "Time not attributed to any other category.",                                  // tc_overhead
    "Time spent waiting on the GPU.",                                              // tc_latency
    "Time spent sleeping to cap the logic rate."};                                 // tc_outside

/* RenderQueries tips. */
const std::string profileQueryTips[3] = {
    "Displays how many pixel samples passed through a given stage of the rendering pipeline. It "
    "is useful for evaluating the sampling rate for antialiasing purposes and post-processing "
    "effects.",
    "Counts the number of graphics primitives (such as triangles) that were processed during "
    "rendering. This can be valuable for understanding the workload on the GPU.",
    "Measures the time it takes to render a certain part of the scene or the entire scene.",
};

// utility structure for realtime plot
struct ScrollingBuffer {
  int MaxSize;
  int Offset;
  ImVector<ImVec2> Data;
  ScrollingBuffer(int max_size = 5000)
  {
    MaxSize = max_size;
    Offset = 0;
    Data.reserve(MaxSize);
  }
  void AddPoint(float x, float y)
  {
    if (Data.size() < MaxSize)
      Data.push_back(ImVec2(x, y));
    else {
      Data[Offset] = ImVec2(x, y);
      Offset = (Offset + 1) % MaxSize;
    }
  }
  ImVec2 GetLastPointY()
  {
    if (Data.size() < MaxSize) {
      return Data.back();
    }
    return Data[(Offset - 1 + MaxSize) % MaxSize];
  }
  void Erase()
  {
    if (Data.size() > 0) {
      Data.shrink(0);
      Offset = 0;
    }
  }
};

bool sortProfilingObjects(KX_GameObject *A, KX_GameObject *B);

class KX_DebugMode
{
 public:
  KX_DebugMode();
  ~KX_DebugMode();

 private:
  /// Variables, They are saved with Custom Save/Load.
  /* Hide Debug Mode */
  bool m_hideDebugMode;

  /* Advanced Profilling */
  bool m_autoResize;
  // Used for slider history
  float m_history;
  // Condition for plot MainProfile
  ImPlotCond m_axisCondition;
  // Used for plot MainProfile
  float m_axisLimit;

  // for the camera controll
  float m_cameraSpeed;
  
  // Options
  float m_profileSize;
  float m_debugPropertiesSize;

  // Enable/Disable AdvancedProfiling
  bool m_AdvancedProfiling;
  float m_ObjectProfiling_PanelSize;
  int m_sortObjectProfilingDelay;
  int m_sortObjectProfilingDelay_time; // time to trigger

  /***************** No save variables ****************/

  // s_physics, s_logic, s_animations, s_scenegraph, s_rasterizer, s_overhead. Note: Jump the
  // s_network
  ScrollingBuffer m_profileBuffer[8];
  float m_advprofileTime;

  // used for pick an GameObject by mouse position.
  bool m_pickSceneObject;

  // Options
  bool m_showOnlyFrameRate;

 public:
  /// Variables, No save.

  // for DebugObjectProfiling.
  std::vector<KX_GameObject *> m_ObjectsProfiling;

  /// Game Engine (Debug Mode) Variables, Previously on KX_Imgui.
  bool imgui_showDebugMenuTop;
  bool imgui_showDebugPhys;
  bool imgui_showArmatures;
  bool imgui_showBoundingBox;
  bool imgui_showCameraFrustum;
  bool imgui_showShadowFrustum;
  bool imgui_showVehicleDebug;
  bool imgui_showVehicleLab;
  KX_VehicleDebugUI m_vehicleDebugUI;
  bool imgui_showRenderQueries;
  bool imgui_controllActiveCamera;
  // used to block the return of SCA_InputEvents to the player.
  bool imgui_blockInputEvents;

  // to know if a scene is suspended by debug mode
  bool imgui_suspendedScene;

  // KX_GameObject index selected in the Debug Mode.
  KX_GameObject *imgui_KXObSelected;

  // KX_Camera index selected in the Debug Mode.
  KX_GameObject *imgui_cameraSelectedGameObj;
  int imgui_cameraSelected;

  // debugPropertyID, for popup label in KX_Scene RenderDebugPropertiesImGui()
  std::string imgui_debugPropID;
  int imgui_debugListProp_Index;
  int imgui_sceneProp_Index;

  // Shows the in-game console window (log mirror). Set once at launch from
  // the "Console" toggle next to Play/Standalone in the 3D View header.
  bool imgui_showConsole;
  KX_ConsoleWindow m_consoleWindow;

  void SetShowConsole(bool show)
  {
	  imgui_showConsole = show;
  }

  bool UseAdvancedProfiling()
  {
    return m_AdvancedProfiling;
  }

  void ForceProfilingUpdate()
  {
	  m_sortObjectProfilingDelay = m_sortObjectProfilingDelay_time;
  }

  /// Main Render
  void RenderImguiDebugMode();

  /// Panels
  void RenderDebugProperties();
  void RenderScenePanel();
  void RenderOptionsPanel();
  void RenderProfiling();

  /// Sub-Panels (Called on Panels)
  void RenderCameraControllPanel();
  void RenderGameObjectPanel();
  void RenderObjectProfiling();

  /// Menus
  void RenderImguiDebug_MainMenuTop();

  /// Process
  void ProcessDebugEvents();

  /// Misc
  ImVec2 GetGameObjectProjectedOnScreen(KX_GameObject *gameObj);
  void DrawCircleProjectedOnObject(KX_GameObject *gameObj);
  void GetGameObjectOnTheScreen();
  void EnableCameraController(class KX_Camera *camera, bool use_active);

  /// Save/Load variables
  void SaveDebugMode_Values();
  void LoadDebugMode_Values();
};

#endif  // KX_DEBUGMODE_H
