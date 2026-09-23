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

 /** \file gameengine/Ketsji/KX_DebugMode.cpp
  *  \ingroup ketsji
  */

#ifdef WITH_BULLET
#  include "LinearMath/btIDebugDraw.h"
#endif  // WITH_BULLET

#include "KX_Camera.h"
#include "KX_DebugMode.h"
#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "KX_Scene.h"

#include "RAS_Query.h"
#include "RAS_Rasterizer.h"

#include "SCA_LogicManager.h"

#include "EXP_ListValue.h"

#include "PHY_IPhysicsEnvironment.h"

#include "IconsForkAwesome.h"
#include "KX_Imgui_Impl_Inputs.h"
#include "imgui_impl_opengl3.h"

bool sortProfilingObjects(KX_GameObject *A, KX_GameObject *B)
{
  KX_GameObject::DebugProfilingData dA = A->GetDebugTimeProfiling();
  KX_GameObject::DebugProfilingData dB = B->GetDebugTimeProfiling();

  float totA = dA.m_time_components + dA.m_time_animation;
  float totB = dB.m_time_components + dB.m_time_animation;

  return totA > totB;
}

KX_DebugMode::KX_DebugMode()
    : m_hideDebugMode(false),
      m_autoResize(true),
      m_history(5.0f),
      m_axisCondition(ImGuiCond_Once),
      m_axisLimit(16.0f),
      m_cameraSpeed(0.3f),
      m_profileSize(1.0f),
      m_debugPropertiesSize(1.0),
      m_AdvancedProfiling(false),
      m_ObjectProfiling_PanelSize(1.0f),
      m_sortObjectProfilingDelay(0),
      m_sortObjectProfilingDelay_time(120),
      m_advprofileTime(0.0f),
      m_pickSceneObject(false),
      m_showOnlyFrameRate(false),
	  imgui_showDebugMenuTop(true),
      imgui_showDebugPhys(false),
      imgui_showArmatures(false),
      imgui_showBoundingBox(false),
      imgui_showCameraFrustum(false),
      imgui_showShadowFrustum(false),
      imgui_showVehicleDebug(false),
      imgui_showVehicleLab(false),
      imgui_showRenderQueries(false),
      imgui_controllActiveCamera(false),
      imgui_blockInputEvents(false),
      imgui_suspendedScene(false),
      imgui_KXObSelected(nullptr),
      imgui_cameraSelectedGameObj(nullptr),
      imgui_cameraSelected(0),
      imgui_debugListProp_Index(0),
      imgui_sceneProp_Index(0),
      imgui_showConsole(false)
{

};

KX_DebugMode::~KX_DebugMode()
{
};

/* Render Debug Mode */
void KX_DebugMode::RenderImguiDebugMode() {
	m_vehicleDebugUI.AutoLoadPresets();
	/* Console window is independent from the rest of the debug UI toggle. */
	if (imgui_showConsole) {
		m_consoleWindow.Render();
	}

	/* Don't draw debug mode */
	if (m_hideDebugMode) {
		return;
	}

	// Docking Viewport
	ImGui::DockSpaceOverViewport(ImGui::GetMainViewport(), ImGuiDockNodeFlags_PassthruCentralNode);

	if (imgui_showDebugMenuTop) { RenderImguiDebug_MainMenuTop(); }

	/* Windows */
	if (ImGui::Begin("Options")) {
		RenderOptionsPanel();
	}
	ImGui::End();
	// Check if have a selected object.
	if (imgui_KXObSelected) {
		if (ImGui::Begin("GameObject Panel")) {
			RenderGameObjectPanel();
		}
		ImGui::End();
	}
	if (ImGui::Begin("Profiling")) {
		RenderProfiling();
	}
	ImGui::End();
	if (ImGui::Begin("Scene")) {
		RenderScenePanel();
	}
	ImGui::End();
	if (imgui_showVehicleLab) {
		m_vehicleDebugUI.Render(&imgui_showVehicleLab);
	}


	// Examples
	//ImGui::ShowDemoWindow();
	//ImPlot::ShowDemoWindow();

	// Render Sub-Panel (if necessary)
	if (imgui_controllActiveCamera) {
		RenderCameraControllPanel();
	}
}

// Override the old Debug properties.
void KX_DebugMode::RenderDebugProperties()
{
  ImGuiWindowFlags window_flags = ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoScrollbar |
                                  ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoDocking |
                                  ImGuiWindowFlags_NoSavedSettings |
                                  ImGuiWindowFlags_NoFocusOnAppearing | ImGuiWindowFlags_NoNav;
  const int PAD = 2;
  const ImGuiViewport *viewport = ImGui::GetMainViewport();
  ImVec2 work_pos = viewport->WorkPos;  // Use work area to avoid menu-bar/task-bar, if any!
  ImVec2 window_pos, window_pos_pivot;
  window_pos.x = (work_pos.x + PAD);
  window_pos.y = (work_pos.y + PAD);
  window_pos_pivot.x = 0.0f;
  window_pos_pivot.y = 0.0f;
  // Only pin the initial position/size: once placed, let the user drag/resize it like any other window.
  ImGui::SetNextWindowPos(window_pos, ImGuiCond_FirstUseEver, window_pos_pivot);
  ImGui::SetNextWindowSize(ImVec2(230.0f * m_profileSize, 0.0f), ImGuiCond_FirstUseEver);
  ImGui::SetNextWindowViewport(viewport->ID);

  ImGui::SetNextWindowBgAlpha(0.5f);  // Transparent background
  if (ImGui::Begin("DebugProperties", (bool *)0, window_flags)) {
    ImGui::SetWindowFontScale(m_profileSize * 0.8f);

    double tottime = KX_GetActiveEngine()->m_tottime;
    double rendertime = KX_GetActiveEngine()->m_rendertimeaverage;
    double animationtime = KX_GetActiveEngine()->m_animationtimeaverage;

    // Same thresholds/colors as before, just centralized so each rate row shares the logic.
    auto rateColor = [](double time) -> ImVec4 {
      float fps = (float)(1.0 / time);
      if (fps < 24) {
        return ImVec4(225, 255, 0, 225);  // yellow
      }
      if (fps < 30) {
        return ImVec4(225, 0, 0, 225);  // red
      }
      return ImVec4(0, 255, 0, 225);  // green
    };

    if (ImGui::BeginTable("##DebugRatesTable", 2, ImGuiTableFlags_SizingStretchProp)) {
      ImGui::TableSetupColumn("Label", ImGuiTableColumnFlags_WidthStretch, 0.45f);
      ImGui::TableSetupColumn("Value", ImGuiTableColumnFlags_WidthStretch, 0.55f);

      auto rateRow = [&](const char *label, double time) {
        ImGui::TableNextRow();
        ImGui::TableSetColumnIndex(0);
        ImGui::TextUnformatted(label);
        ImGui::TableSetColumnIndex(1);
        ImVec4 color = rateColor(time);
        ImGui::TextColored(color, "%5.2fms | (%.0fFPS)", (time * 1000.0), (1.0 / time));
      };

      rateRow("LogicRate", tottime);
      rateRow("RenderRate", rendertime);
      rateRow("AnimationRate", animationtime);

      ImGui::EndTable();
    }

	// Show only framerate (no button).
	if (!KX_GetActiveEngine()->GetFlag(KX_KetsjiEngine::SHOW_PROFILE)) {
      ImGui::End();
      return;
    }

    //ImGui::SameLine();
    //if (ImGui::SmallButton(m_showOnlyFrameRate ? ICON_FK_PLUS : ICON_FK_MINUS)) {
    //  m_showOnlyFrameRate = !m_showOnlyFrameRate;
    //}

	// Show Render Queries.
    if (KX_GetActiveEngine()->GetFlag(KX_KetsjiEngine::SHOW_RENDER_QUERIES)) {
      ImGui::Separator();
      ImGui::TextUnformatted("Render Queries");

      std::string debugtxt;

      for (unsigned short i = 0; i < KX_KetsjiEngine::QUERY_MAX; ++i) {

        ImGui::TextUnformatted(KX_GetActiveEngine()->GetRenderQueryLabel(i).c_str());
		// Tooltip.
        if (ImGui::IsItemHovered()) {
          ImGui::SetTooltip("%s", profileQueryTips[i].c_str());
        }
        ImGui::SameLine();
        if (i == KX_KetsjiEngine::QUERY_TIME) {
          ImGui::TextColored(ImVec4(0, 255, 0, 225), "%.2fms", (((float)KX_GetActiveEngine()->GetRenderQueryValue(i)) / 1e6));
        }
        else {
          ImGui::TextColored(ImVec4(0, 255, 0, 225), "%i", KX_GetActiveEngine()->GetRenderQueryValue(i));
        }
      }

      // Show culling object counters (main camera pass only).
      ImGui::Separator();
      ImGui::TextUnformatted("Culling (Objects)");
      for (KX_Scene *scene : KX_GetActiveEngine()->GetScenes()) {
        ImGui::TextColored(ImVec4(0, 255, 0, 225), "%s: %i total | %i tested | %i visible",
          scene->GetName().c_str(), scene->GetLastCullingTotalObjects(),
          scene->GetLastCullingTestedObjects(), scene->GetLastCullingVisibleObjects());
      }

      // Show light/shadow counters (last RenderShadowBuffers() pass).
      ImGui::Separator();
      ImGui::TextUnformatted("Lights / Shadow Passes");
      for (KX_Scene *scene : KX_GetActiveEngine()->GetScenes()) {
        ImGui::TextColored(ImVec4(0, 255, 0, 225), "%s: %i lights | %i updated | %i shadow passes",
          scene->GetName().c_str(), scene->GetLastLightsTotal(),
          scene->GetLastLightsShadowUpdated(), scene->GetLastShadowPasses());
      }

      // Show draw call / material bind counters from the last completed frame
      // (all passes: main, shadow, filters, etc).
      ImGui::Separator();
      ImGui::TextUnformatted("Draw Calls");
      ImGui::TextColored(ImVec4(0, 255, 0, 225), "%i draw calls | %i material binds",
        RAS_Rasterizer::GetLastDrawCalls(), RAS_Rasterizer::GetLastMaterialChanges());

      // Show logic execution counters (last BeginFrame()/UpdateFrame() pass).
      ImGui::Separator();
      ImGui::TextUnformatted("Logic");
      for (KX_Scene *scene : KX_GetActiveEngine()->GetScenes()) {
        SCA_LogicManager *logicmgr = scene->GetLogicManager();
        ImGui::TextColored(ImVec4(0, 255, 0, 225), "%s: %i sensors | %i controllers triggered | %i actuators updated",
          scene->GetName().c_str(), logicmgr->GetTotalRegisteredSensors(),
          logicmgr->GetLastControllersTriggered(), logicmgr->GetLastActuatorsUpdated());
      }
    }
	
	// Show only framerate.
	if (m_showOnlyFrameRate) {
      ImGui::End();
      return;
    }

	ImGui::Separator();
    if (ImGui::BeginTable("##DebugCategoriesTable", 2, ImGuiTableFlags_SizingStretchProp)) {
      ImGui::TableSetupColumn("Label", ImGuiTableColumnFlags_WidthStretch, 0.45f);
      ImGui::TableSetupColumn("Value", ImGuiTableColumnFlags_WidthStretch, 0.55f);

      const ImU32 barCol = ImColor(0.2f, 0.2f, 0.2f, 0.85f);
      for (int j = KX_GetActiveEngine()->tc_first; j < KX_GetActiveEngine()->tc_numCategories; j++) {
        double time = KX_GetActiveEngine()->m_logger.GetAverage((KX_KetsjiEngine::KX_TimeCategory)j);
        int percentage = (int)(time / tottime * 100.f);

        ImVec4 color = ImVec4(0, 255, 0, 225);  // green (Default)
        if (j != KX_GetActiveEngine()->tc_latency) {
          /* Red */
          if (percentage > 50)
            color = ImVec4(225, 0, 0, 225);
          /* Yellow */
          else if (percentage > 25)
            color = ImVec4(225, 255, 0, 225);
        }
        else {
          /* Red */
          if (percentage < 10)
            color = ImVec4(225, 0, 0, 225);
          /* Yellow */
          else if (percentage < 50)
            color = ImVec4(225, 255, 0, 225);
        }

        ImGui::TableNextRow();
        ImGui::TableSetColumnIndex(0);
        ImGui::TextColored(color, "%s", KX_GetActiveEngine()->m_profileLabels[j].c_str());
        if (ImGui::IsItemHovered()) {
          ImGui::SetTooltip("%s", profileTips[j].c_str());
        }

        ImGui::TableSetColumnIndex(1);
        /* Draw the load bar behind the text, sized relative to this column's own width
         * so it never overlaps the label column regardless of font size. */
        const ImVec2 cellPos = ImGui::GetCursorScreenPos();
        const float cellWidth = ImGui::GetContentRegionAvail().x;
        const float rowHeight = ImGui::GetTextLineHeight();
        const float barWidth = cellWidth * (percentage * 0.01f);
        ImGui::GetWindowDrawList()->AddRectFilled(
            cellPos, ImVec2(cellPos.x + barWidth, cellPos.y + rowHeight), barCol);
        ImGui::Text("%5.2fms | %i%%", (time * 1000.f), percentage);
      }

      ImGui::EndTable();
    }

    // Properties
    if (KX_GetActiveEngine()->GetFlag(KX_KetsjiEngine::SHOW_DEBUG_PROPERTIES)) {
      ImGui::Separator();
      if (ImGui::CollapsingHeader("Game Properties", ImGuiTreeNodeFlags_DefaultOpen)) {
        if (ImGui::BeginChild("Properties", ImVec2(0.0f, 95.0f * m_debugPropertiesSize), true)) {
          EXP_ListValue<KX_Scene> *scenes = KX_GetActiveEngine()->GetScenes();

          for (int i = 0; i < scenes->GetCount(); i++) {
            KX_Scene *scene = scenes->GetValue(i);
            scene->RenderDebugPropertiesImGui(i);
          }
        }
        ImGui::EndChild();
      }
    }

    ImGui::End();
  }
}

void KX_DebugMode::RenderScenePanel() {
	//KX_Imgui *imgui = KX_GetActiveEngine()->GetImgui();

	/* Scene Objects */
	if (ImGui::CollapsingHeader("Objects")) {
		if (ImGui::BeginChild("Scene Objects", ImVec2(0, 150), true)) {
			// Make objects scene list.
			int sceneIndex = 0;

			for (KX_Scene *scene : KX_GetActiveEngine()->GetScenes()) {
				char sceneName[64];
				// Scene Index / Name.
				sprintf(sceneName, "%s ##%i", scene->GetName().c_str(), sceneIndex);

				if (ImGui::CollapsingHeader(sceneName)) {
					for (int i = 0; i < scene->GetObjectList()->GetCount(); i++)
					{
						KX_GameObject *gameObj = scene->GetObjectList()->GetValue(i);

						if (ImGui::Selectable(gameObj->GetName().c_str(), false)) {
							imgui_KXObSelected = gameObj;
						}
					}
				}
			sceneIndex++;
			}

			/* Draw Projected Circle in selected object. */
			if (imgui_KXObSelected) {
				DrawCircleProjectedOnObject(imgui_KXObSelected);
			}

			ImGui::EndChild();
		}
		if (ImGui::Button("Pick Object", ImVec2(100, 0))) {
			m_pickSceneObject = !m_pickSceneObject;
		}
		if (m_pickSceneObject) {
			/* Infor Window */
			ImGuiWindowFlags window_flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoFocusOnAppearing | ImGuiWindowFlags_NoNav | ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoDocking;
			ImVec2 center = ImGui::GetMainViewport()->GetCenter();
			center.y -= 100;
			ImGui::SetNextWindowPos(center, ImGuiCond_Always, ImVec2(0.5f, 0.5f));

			ImGui::SetNextWindowBgAlpha(0.5f); // Transparent background
			if (ImGui::Begin("PickGameObject", nullptr, window_flags)) {
				ImGui::TextUnformatted(ICON_FK_MOUSE_POINTER "Select an GameObject");
				ImGui::TextUnformatted("   (Right-click to cancel)");
			}
			ImGui::End();
		}

		ImGui::SameLine();
		if (ImGui::Button("Deselect Object", ImVec2(100, 0))) {
			imgui_KXObSelected = nullptr;
		}
	}

	if (ImGui::CollapsingHeader("Cameras")) {
		/* Camera Change */
		ImGui::TextUnformatted("Scene Cameras");
		ImGui::BulletText("Double click to control the camera");
		ImGui::BeginChild("Scene Cameras", ImVec2(0, 150), true);

		// Always Use Front Scene.
		KX_Scene *scene = KX_GetActiveEngine()->GetScenes()->GetFront();
		for (int i = 0; i < scene->GetCameraList()->GetCount(); i++)
		{
			char label[64] = "Editor Camera";
			KX_Camera *camOb = scene->GetCameraList()->GetValue(i);

			if (camOb->GetName() != "__default__cam__") {
				sprintf(label, "%s", camOb->GetName().c_str());
			}
			
			if (ImGui::Selectable(label, imgui_cameraSelected == i)) {
				// Controll the camera, if selected previously
				if (imgui_cameraSelected == i) {
					// enable camera controller
					this->EnableCameraController(camOb, false);
				}
				// If it wasn't double-clicked, let's just look at the camera
				else {
					scene->SetActiveCamera(camOb);
					imgui_cameraSelected = i;
					
					if (camOb->GetName() == "__default__cam__") {
						sprintf(label, "%s", camOb->GetName().c_str());
						imgui_blockInputEvents = true;
					}
					else {
						imgui_blockInputEvents = false;
					}
				}
			}
		}
		ImGui::EndChild();
	}

	if (ImGui::CollapsingHeader("Inactive Objects")) {
		ImGui::TextUnformatted("Inactive Layer Objects");

		ImGui::BeginChild("Add Objects", ImVec2(0, 150), true);
		for (int i = 0; i < KX_GetActiveScene()->GetInactiveList()->GetCount(); i++)
		{
			KX_GameObject* gameObj = KX_GetActiveScene()->GetInactiveList()->GetValue(i);

			ImGui::TextUnformatted(gameObj->GetName().c_str());

			ImGui::SameLine(150);

			std::string buttonName = "Add##";
			buttonName += std::to_string(i);

			if (ImGui::SmallButton(buttonName.c_str())) {
				KX_GameObject *replica = KX_GetActiveScene()->AddReplicaObject(gameObj, gameObj);
				replica->Release();
			}
		}
		ImGui::EndChild();
	}
}

void KX_DebugMode::RenderOptionsPanel() {
	ImGui::Checkbox("Show debug menu topbar", &imgui_showDebugMenuTop);

	ImGui::Separator();

	ImGui::TextUnformatted("Profile settings");
	if (ImGui::Button("Show Framerate")) {
		KX_GetActiveEngine()->ToggleFlag(KX_KetsjiEngine::SHOW_FRAMERATE);
	}
	ImGui::SameLine();
	if (ImGui::Button("Show Profile")) {
		KX_GetActiveEngine()->ToggleFlag(KX_KetsjiEngine::SHOW_PROFILE);
	}
	ImGui::SameLine();
	if (ImGui::Button("Show Debug Properties")) {
		KX_GetActiveEngine()->ToggleFlag(KX_KetsjiEngine::SHOW_DEBUG_PROPERTIES);
	}

	ImGui::SliderFloat("Profile Size", &m_profileSize, 0.9f, 4.0f);
	ImGui::SliderFloat("Debug Properties Size", &m_debugPropertiesSize, 1.0f, 10.0f);
}

void KX_DebugMode::RenderProfiling() {
	ImGui::SetWindowFontScale(0.8f);

	if (ImGui::CollapsingHeader("Graph Profiler")) {
		//ImGui::SetWindowSize(ImVec2(0, 20.0f));
		if (!KX_GetActiveScene()->m_suspend) {
			m_advprofileTime += ImGui::GetIO().DeltaTime;

			// Physics, Logic, Animations, Scenegraph, Rasterizer, Overhead 
			for (int i = 7; i >= 0; i--) {
				KX_KetsjiEngine::KX_TimeCategory tc = (KX_KetsjiEngine::KX_TimeCategory)i;
				if (i == KX_KetsjiEngine::tc_network) { tc = KX_KetsjiEngine::tc_scenegraph; }
				if (i == KX_KetsjiEngine::tc_services) { tc = KX_KetsjiEngine::tc_overhead; }

				float time = KX_GetActiveEngine()->m_logger.GetAverage(tc) * 1000.f;

				/* We need to stack all the values.
				/* I tried to do a for loop but in this case i really couldn't do it.. if someone, be careful. */
				float stime = 0;
				if (i == KX_KetsjiEngine::tc_rasterizer) {
					stime = KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_overhead) * 1000.f;
				}
				else if (i == KX_KetsjiEngine::tc_scenegraph) {
					stime = KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_overhead) * 1000.f;
					stime += KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_rasterizer) * 1000.f;
				}
				else if (i == KX_KetsjiEngine::tc_animations) {
					stime = KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_overhead) * 1000.f;
					stime += KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_rasterizer) * 1000.f;
					stime += KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_scenegraph) * 1000.f;
				}
				else if (i == KX_KetsjiEngine::tc_logic) {
					stime = KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_overhead) * 1000.f;
					stime += KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_rasterizer) * 1000.f;
					stime += KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_scenegraph) * 1000.f;
					stime += KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_animations) * 1000.f;
				}
				else if (i == KX_KetsjiEngine::tc_physics) {
					stime = KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_overhead) * 1000.f;
					stime += KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_rasterizer) * 1000.f;
					stime += KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_scenegraph) * 1000.f;
					stime += KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_animations) * 1000.f;
					stime += KX_GetActiveEngine()->m_logger.GetAverage(KX_KetsjiEngine::tc_logic) * 1000.f;
				}

				if (stime != 0) {
					time += stime;
				}

				// Debugging
				/*using namespace std;
				if (i == KX_KetsjiEngine::tc_physics) { cout << time << "\n";  }*/

				m_profileBuffer[i].AddPoint(m_advprofileTime, time);
			}
		}

		ImGui::SliderFloat("History", &m_history, 1.0f, 15.0f, "%.1f s");
		ImGui::SameLine();
		ImGui::Checkbox("AutoResize", &m_autoResize);

		if (ImPlot::BeginPlot("##MainProfile", ImVec2(0, 175))) {

			ImPlot::SetupAxes("Time (Seconds)", "Ms(milliseconds)");
			ImPlot::SetupAxisLimits(ImAxis_X1, m_advprofileTime - m_history, m_advprofileTime, ImGuiCond_Always);
			ImPlot::SetupAxisLimits(ImAxis_Y1, 0, m_axisLimit, m_axisCondition);

			if (ImPlot::IsPlotHovered()) {
				m_axisCondition = ImGuiCond_Once;
			}
			else if (m_autoResize){
				m_axisLimit = m_profileBuffer[0].GetLastPointY().y + 5;
				m_axisCondition = ImGuiCond_Always;
			}
		
			for (int i = 0; i < 8; i++) {
				int tc = i;
				if (i == KX_KetsjiEngine::tc_network) { tc = KX_KetsjiEngine::tc_scenegraph; }
				else if (i == KX_KetsjiEngine::tc_services) { tc = KX_KetsjiEngine::tc_overhead; }

				ImPlot::PlotShaded(KX_GetActiveEngine()->m_profileLabels[tc].c_str(), &m_profileBuffer[tc].Data[0].x, &m_profileBuffer[tc].Data[0].y, m_profileBuffer[tc].Data.size(), 0, 0, m_profileBuffer[tc].Offset, 2 * sizeof(float));
			}

			double linePos = 16.0;
			ImPlot::DragLineY(0, &linePos, ImVec4(1, 1, 0, 1), 1, ImPlotDragToolFlags_NoInputs);
			ImPlot::TagY(16.f, ImVec4(1, 1, 0, 1), "60FPS");

			linePos = 33.0;
			ImPlot::DragLineY(0, &linePos, ImVec4(1, 1, 0, 1), 1, ImPlotDragToolFlags_NoInputs);
			ImPlot::TagY(33.f, ImVec4(1, 1, 0, 1), "30FPS");

			linePos = 66.0;
			ImPlot::DragLineY(0, &linePos, ImVec4(1, 1, 0, 1), 1, ImPlotDragToolFlags_NoInputs);
			ImPlot::TagY(66.f, ImVec4(1, 1, 0, 1), "15FPS");

			// FPS Line
			linePos = m_profileBuffer[0].GetLastPointY().y;
			ImPlot::DragLineY(0, &linePos, ImVec4(0, 1, 0, 0.5f), 1, ImPlotDragToolFlags_NoInputs);
			ImPlot::TagY(m_profileBuffer[0].GetLastPointY().y, ImVec4(0, 1, 0, 1), "FPS %.1f", (1.0f / KX_GetActiveEngine()->m_logger.GetAverage()));

			ImPlot::EndPlot();
		}
	}

	if (ImGui::IsItemHovered(ImGuiHoveredFlags_DelayNormal | ImGuiHoveredFlags_NoSharedDelay)) {
          ImGui::SetTooltip("Activate Graph Profiler (WARNING: This has a high impact on performance).");
    }

	// Toggle Advanced Profiling.
	m_AdvancedProfiling = ImGui::CollapsingHeader("Advanced Profiling");
    if (m_AdvancedProfiling) {
		ImGui::PushStyleColor(ImGuiCol_ChildBg, ImVec4(0.3f, 0.3f, 0.3f, 0.7f)); // Change Background color.
		if (ImGui::BeginChild("Advanced Profiling Panel")) {

			// Draw Advanced Profiling Panel.
			ImGui::SliderFloat("Object Panel Size", &m_ObjectProfiling_PanelSize, 0.1f, 2.0f, "%.1f");

			// Change Font scale.
			ImGui::SetWindowFontScale(m_ObjectProfiling_PanelSize);

			RenderObjectProfiling();

			// Restore Original Font Scale.
			ImGui::SetWindowFontScale(1.0f);

			ImGui::BulletText("Organized list of objects, major/minor performance impact");
			// List of objects, Order of more/less impact on performance.
			if (ImGui::BeginChild("Profiling Objects List", ImVec2(0, 150), true)) {

				// Update Vector List and sort.
				if (m_sortObjectProfilingDelay >= m_sortObjectProfilingDelay_time) {
					EXP_ListValue<KX_GameObject> *objects = KX_GetActiveEngine()->GetScenes()->GetFront()->GetObjectList();

					m_ObjectsProfiling.clear(); // clear

					for (KX_GameObject *gameobj : objects) {
						m_ObjectsProfiling.push_back(gameobj);
					}
					std::sort(m_ObjectsProfiling.begin(), m_ObjectsProfiling.end(), sortProfilingObjects);
					m_sortObjectProfilingDelay = 0;
				}

				// Draw list.
				int index = 0;
				for (KX_GameObject *gameObj : m_ObjectsProfiling) {

					char name[128];
					sprintf(name, "%i - %s", (index + 1), gameObj->GetName().c_str());
					if (ImGui::Selectable(name, false)) { // ToDo
						imgui_KXObSelected = gameObj;
					}
					index++;
				}

				m_sortObjectProfilingDelay++;
			}
			ImGui::EndChild();
		}
		ImGui::EndChild();
		ImGui::PopStyleColor();
	}

	if (ImGui::IsItemHovered(ImGuiHoveredFlags_DelayNormal | ImGuiHoveredFlags_NoSharedDelay)) {
          ImGui::SetTooltip("Activate Advanced Profiling (WARNING: This has a high impact on performance).");
    }
}

void KX_DebugMode::RenderImguiDebug_MainMenuTop() {
	//KX_Imgui *imgui = KX_GetActiveEngine()->GetImgui();

	if (ImGui::BeginMainMenuBar())
	{
		ImGui::TextColored(ImVec4(0, 255, 0, 255), "Debug Mode");
		ImGui::Spacing();
		ImGui::TextUnformatted("GameEngine Options:");

		if (ImGui::Checkbox("Debug Physics", &imgui_showDebugPhys)) {
#ifdef WITH_BULLET
			if (imgui_showDebugPhys) {
				KX_GetActiveScene()->GetPhysicsEnvironment()->SetDebugMode(btIDebugDraw::DBG_DrawWireframe | btIDebugDraw::DBG_DrawAabb | btIDebugDraw::DBG_DrawContactPoints |
																		   btIDebugDraw::DBG_DrawText | btIDebugDraw::DBG_DrawConstraintLimits | btIDebugDraw::DBG_DrawConstraints);
			}
			/* Disable */
			else { KX_GetActiveScene()->GetPhysicsEnvironment()->SetDebugMode(0); }
#endif // WITH_BULLET
		}
		if (ImGui::Checkbox("Show Armatures", &imgui_showArmatures)) {
			KX_GetActiveEngine()->SetShowArmatures(imgui_showArmatures == 1 ? KX_DebugOption::FORCE : KX_DebugOption::DISABLE);
		}
		if (ImGui::Checkbox("Show Bounding Box", &imgui_showBoundingBox)) {
			KX_GetActiveEngine()->SetShowBoundingBox(imgui_showBoundingBox == 1 ? KX_DebugOption::FORCE : KX_DebugOption::DISABLE);
		}
		if (ImGui::Checkbox("Show Camera Frustum", &imgui_showCameraFrustum)) {
			KX_GetActiveEngine()->SetShowCameraFrustum(imgui_showCameraFrustum == 1 ? KX_DebugOption::FORCE : KX_DebugOption::DISABLE);
		}
		if (ImGui::Checkbox("Show Shadow Frustum", &imgui_showShadowFrustum)) {
			KX_GetActiveEngine()->SetShowShadowFrustum(imgui_showShadowFrustum == 1 ? KX_DebugOption::FORCE : KX_DebugOption::DISABLE);
		}
		if (ImGui::Checkbox("Show Vehicle Debug", &imgui_showVehicleDebug)) {
			KX_GetActiveEngine()->SetShowVehicleDebug(imgui_showVehicleDebug == 1 ? KX_DebugOption::FORCE : KX_DebugOption::DISABLE);
		}
		ImGui::Checkbox("Vehicle Lab", &imgui_showVehicleLab);
		if (ImGui::Checkbox("Show Render Queries", &imgui_showRenderQueries)) {
			KX_GetActiveEngine()->SetFlag(KX_KetsjiEngine::SHOW_RENDER_QUERIES, imgui_showRenderQueries);
		}

		// Center Align Text
		float posX = ((ImGui::GetWindowWidth() / 2) 
					 - ImGui::GetScrollX() - 2 * ImGui::GetStyle().ItemSpacing.x);

		if (posX > ImGui::GetCursorPosX()) {
			ImGui::SetCursorPosX(posX);
		}
		
		// Exit Game Button
		ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(123, 0, 0, 255));
		if (ImGui::Button(ICON_FK_STOP "")) {
			KX_GetActiveEngine()->RequestExit(KX_ExitInfo::QUIT_GAME);
		}
		ImGui::PopStyleColor();

		//  Pause Scene Button
		bool paused = KX_GetActiveScene()->IsSuspended();
		if (paused) {
			ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(123, 0, 0, 255));
		}

		if (ImGui::Button(ICON_FK_PAUSE "")) {
			if (KX_GetActiveScene()->IsSuspended()) {
				for (KX_Scene *scene : KX_GetActiveEngine()->GetScenes()) {
					scene->Resume();
				}
				imgui_suspendedScene = false;
			}
			else {
				for (KX_Scene *scene : KX_GetActiveEngine()->GetScenes()) {
					scene->Suspend();
				}
				imgui_suspendedScene = true;
			}
		}

		if (paused) {
			ImGui::PopStyleColor();
		}

		/* Hacky: Extremely garbage code below, I thought it best to do a trick for the frame advance button because */
		/* I would have to make several scene update calls here, or to avoid code replication from KetsjiEngine create a - */
		/* special function for updating the whole scene at KetsjiEngine. */
		/* */
		/* The trick is simple, right after pressing the button it will Resume() the scene, */
		/* in the next frame it will go back and check if the scene was suspended to know if the scene was suspended before by debug mode, if so it suspends the scene again. */
		if (imgui_suspendedScene && !KX_GetActiveScene()->m_suspend) {
			for (KX_Scene *scene : KX_GetActiveEngine()->GetScenes()) {
				scene->Suspend();
			}
		}

		// Resume Scene Button
		if (ImGui::Button(ICON_FK_FORWARD "")) {
			for (KX_Scene *scene : KX_GetActiveEngine()->GetScenes()) {
				scene->Resume();
			}
		}

		// Camera Controller Button
		if (ImGui::Button(ICON_FK_CAMERA "")) {
			SCA_IInputDevice *inputDevice = KX_GetActiveEngine()->GetInputDevice();
			bool use_active = inputDevice->GetInput(SCA_IInputDevice::LEFTSHIFTKEY).Find(SCA_InputEvent::ACTIVE);
			this->EnableCameraController(KX_GetActiveEngine()->GetScenes()->GetFront()->GetActiveCamera(), use_active);
		}

		if (ImGui::IsItemHovered()) {
			ImGui::SetTooltip("Take control of the dev cam from the active camera. Hold LEFTSHIFT to take control of the active camera.");
		}
		
		// Right Align Text
		bool allowMouse = KX_GetActiveEngine()->GetCanvas()->GetDebugModeAllowMouse();
		std::string text = ICON_FK_MOUSE_POINTER "Press [F1] to %s mouse rights    ";
		std::string textHideDM = ICON_FK_GNU_SOCIAL "[F2] to hide Debug Mode    ";

		const float textSize = (ImGui::CalcTextSize(text.c_str()).x + ImGui::CalcTextSize(textHideDM.c_str()).x);
		posX = (ImGui::GetCursorPosX() + ImGui::GetColumnWidth() - textSize
				- ImGui::GetScrollX() - 2 * ImGui::GetStyle().ItemSpacing.x);

		if (posX > ImGui::GetCursorPosX()) {
			ImGui::SetCursorPosX(posX);
		}
		
		ImGui::TextColored(allowMouse ? ImVec4(1.0f, 1.0f, 1.0f, 1.0f) : ImVec4(0.5f, 0.5f, 0.5f, 1.0f), 
						   text.c_str(), allowMouse ? "release" : "get");

		ImGui::TextColored(ImVec4(1.0f, 1.0f, 1.0f, 1.0f), textHideDM.c_str());

		ImGui::EndMainMenuBar();
	}
}

/* Sub-Menus */
void KX_DebugMode::RenderCameraControllPanel() {
	ImGuiWindowFlags window_flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoFocusOnAppearing | ImGuiWindowFlags_NoNav | ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoDocking;
	ImVec2 center = ImGui::GetMainViewport()->GetCenter();
	center.y += 150;
	ImGui::SetNextWindowPos(center, ImGuiCond_Always, ImVec2(0.5f, 0.5f));

	ImGui::PushStyleColor(ImGuiCol_Border, ImVec4(0, 0, 0, 0));
	ImGui::SetNextWindowBgAlpha(0.5f); // Transparent background
	if (ImGui::Begin("CameraControllPanel", nullptr, window_flags)) {
		ImGui::TextUnformatted("(left-click to stop)");
		ImGui::Text("Speed: %.2f", m_cameraSpeed);
		ImGui::Separator();
		//ImGui::Text("Potato");
	}
	ImGui::End();
	ImGui::PopStyleColor();

	/// Camera Speed
	SCA_IInputDevice *inputDevice = KX_GetActiveEngine()->GetInputDevice();
	int mouseWheelUp = inputDevice->GetInput(SCA_IInputDevice::WHEELUPMOUSE).Find(SCA_InputEvent::ACTIVE);
	int mouseWheelDown = inputDevice->GetInput(SCA_IInputDevice::WHEELDOWNMOUSE).Find(SCA_InputEvent::ACTIVE);

	if ((mouseWheelUp && m_cameraSpeed <= 9.8f) || (mouseWheelDown && m_cameraSpeed > 0.01f)) {
		int wheeldir = (mouseWheelUp - mouseWheelDown);
		float add = m_cameraSpeed < 0.2f ? 0.01f : 
		            m_cameraSpeed < 2.0f ? 0.1f : 0.5f;

		m_cameraSpeed += add * wheeldir;
	}
}

void KX_DebugMode::RenderGameObjectPanel() {
	/** Frame ImVec2(250, 150) **/
	ImGui::BeginChild("KX_GameObjectValues", ImVec2(0, 0), true);

	KX_GameObject *gameObj = imgui_KXObSelected;
	
	ImGui::TextUnformatted("Transforms:");

	ImGui::SameLine();
	ImGui::TextUnformatted("Delete GameObject");
	ImGui::SameLine();

	ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(255, 0, 0, 255));
	if (ImGui::Button("X")) {
		// Delete the KX_GameObject
		gameObj->GetScene()->DelayedRemoveObject(gameObj);
		imgui_KXObSelected = nullptr;

		ImGui::PopStyleColor();
		ImGui::EndChild();
		return;
	}
	ImGui::PopStyleColor();

	/* Position */
	float worldPos[3] = { gameObj->NodeGetWorldPosition().x,
						  gameObj->NodeGetWorldPosition().y,
						  gameObj->NodeGetWorldPosition().z
	};

	if (ImGui::DragFloat3("Position", worldPos, 0.1f)) {
		gameObj->NodeSetWorldPosition(mathfu::vec3(worldPos[0], worldPos[1], worldPos[2]));
		gameObj->NodeUpdate();
	}

	/* Rotation */
	mathfu::vec3 rotEuler = gameObj->NodeGetWorldOrientation().GetEuler();
	float worldRot[3] = { rotEuler.x,
						  rotEuler.y,
						  rotEuler.z
	};

	if (ImGui::DragFloat3("Rotation", worldRot, 0.1f)) {
		gameObj->NodeSetGlobalOrientation(mathfu::vec3(worldRot[0], worldRot[1], worldRot[2]));
	}

	/* Scaling */
	float worldScaling[3] = { gameObj->NodeGetWorldScaling().x,
							  gameObj->NodeGetWorldScaling().y,
							  gameObj->NodeGetWorldScaling().z
	};

	if (ImGui::DragFloat3("Scaling", worldScaling, 0.1f)) {
		gameObj->NodeSetWorldScale(mathfu::vec3(worldScaling[0], worldScaling[1], worldScaling[2]));
	}

	if (gameObj->IsDynamic()) {
		ImGui::NewLine();
		ImGui::TextUnformatted("Physics");

		/* Suspend/Restore Physics */
		if (ImGui::Button("Suspend Physics")) {
			gameObj->SuspendPhysics(false);
		}
		ImGui::SameLine();
		if (ImGui::Button("RestorePhysics")) {
			gameObj->RestorePhysics();
		}

		/* Rigid Body */
		if (ImGui::Button("Disable RigidBody")) {
			gameObj->PyDisableRigidBody();
		}
		ImGui::SameLine();
		if (ImGui::Button("Enable RigidBody")) {
			gameObj->PyEnableRigidBody();
		}
	}

	ImGui::EndChild();
}

void KX_DebugMode::RenderObjectProfiling() {
  KX_Scene *scene = KX_GetActiveEngine()->GetScenes()->GetFront();
  EXP_ListValue<KX_GameObject> *objects = scene->GetObjectList();

  int index = 0;
  for (KX_GameObject *gameobj : objects) {
    bool isCamera = (gameobj == scene->GetActiveCamera());

	// get profiling.
    KX_GameObject::DebugProfilingData debugData = gameobj->GetDebugTimeProfiling();
    float logicTime = debugData.m_time_components * 1000.0f;
    float animTime = debugData.m_time_animation * 1000.0f;

	if (!debugData.m_render) {
		continue;
	}

	const char *profilingBase = R"(%s%s Object Name: %s
 Logic: %.4fms
 Animation: %.4fms)";

	// Format Text.
    char profilingText[128];
    sprintf(profilingText, profilingBase, 
		isCamera ? R"( Active Camera Profile
)" : "",
		ICON_FK_INFO_CIRCLE, 
		gameobj->GetName().c_str(), 
		logicTime, animTime);

	
    ImVec2 window_size = ImGui::GetWindowViewport()->WorkSize;
    ImVec2 toScreenProj = !isCamera ? GetGameObjectProjectedOnScreen(gameobj) : ImVec2(window_size.x * 0.5f, window_size.y * 0.8f);

	// Render Quad. for better view.
	ImVec2 textSize = ImGui::CalcTextSize(profilingText);
	ImVec2 rectMax = ImVec2(toScreenProj.x + textSize.x, toScreenProj.y + textSize.y);
    ImGui::GetBackgroundDrawList()->AddRectFilled(toScreenProj, rectMax, ImColor(0.2f, 0.2f, 0.2f, 0.85f));

	// Render Text.
    ImGui::GetBackgroundDrawList()->AddText(toScreenProj, IM_COL32(255, 255, 255, 255), profilingText);
    index++;
  }
}

/* Events Process */
void KX_DebugMode::ProcessDebugEvents() {
	SCA_IInputDevice *inputDevice = KX_GetActiveEngine()->GetInputDevice();

	/* Debug Mode Camera Controll */
	if (imgui_controllActiveCamera) {
		KX_Scene *scene = KX_GetActiveEngine()->GetScenes()->GetFront();
		float dt = KX_GetActiveEngine()->GetEngineDeltaTime();
		mathfu::vec3 dloc(0, 0, 0);

		/// Movement
		if (inputDevice->GetInput(SCA_IInputDevice::WKEY).Find(SCA_InputEvent::ACTIVE)) { dloc.z = -m_cameraSpeed; }
		else if (inputDevice->GetInput(SCA_IInputDevice::SKEY).Find(SCA_InputEvent::ACTIVE)) { dloc.z = m_cameraSpeed; }
		if (inputDevice->GetInput(SCA_IInputDevice::AKEY).Find(SCA_InputEvent::ACTIVE)) { dloc.x = -m_cameraSpeed; }
		else if (inputDevice->GetInput(SCA_IInputDevice::DKEY).Find(SCA_InputEvent::ACTIVE)) { dloc.x = m_cameraSpeed; }

		if (inputDevice->GetInput(SCA_IInputDevice::QKEY).Find(SCA_InputEvent::ACTIVE)) { dloc.y = -m_cameraSpeed; }
		else if (inputDevice->GetInput(SCA_IInputDevice::EKEY).Find(SCA_InputEvent::ACTIVE)) { dloc.y = m_cameraSpeed; }

		// Camera Run
		if (inputDevice->GetInput(SCA_IInputDevice::LEFTSHIFTKEY).Find(SCA_InputEvent::ACTIVE)) {
			dloc *= 2;
		}

		// ApplyMovement
		scene->GetActiveCamera()->ApplyMovement((dloc * 60) * dt, true);

		/// MouseLook
		KX_GetActiveEngine()->GetPythonMouse()->Recenter(true);
		mathfu::vec2 mouseDelta = KX_GetActiveEngine()->GetPythonMouse()->GetDeltaPosition(true);
		
		// ApplyRotation
		scene->GetActiveCamera()->ApplyRotation(mathfu::vec3(0, 0, (mouseDelta.x * 60) * dt), false);
		scene->GetActiveCamera()->ApplyRotation(mathfu::vec3((mouseDelta.y * 60) * dt, 0, 0), true);

		/// DeActivate Controll
		if (inputDevice->GetInput(SCA_IInputDevice::LEFTMOUSE).Find(SCA_InputEvent::JUSTRELEASED)) {
			imgui_controllActiveCamera = false;
			KX_GetActiveEngine()->GetCanvas()->SetMouseState(RAS_ICanvas::MOUSE_NORMAL);
		}
	}
	if (m_pickSceneObject) {
		GetGameObjectOnTheScreen();
	}

	/* Hide DebugMode */
	if (inputDevice->GetInput(SCA_IInputDevice::F2KEY).Find(SCA_InputEvent::JUSTRELEASED)) {
		m_hideDebugMode = !m_hideDebugMode; // Switch
	}
}

ImVec2 KX_DebugMode::GetGameObjectProjectedOnScreen(KX_GameObject *gameObj)
{
  mathfu::vec3 gameObjScreenSpace = mt::vec3(gameObj->NodeGetWorldPosition());
  gameObjScreenSpace = gameObj->GetScene()->GetActiveCamera()->GetObjectProjectedOnScreenSpace(
      gameObjScreenSpace);

  ImVec2 window_size = ImGui::GetWindowViewport()->WorkSize;
  ImVec2 ObjectScreen = ImVec2(gameObjScreenSpace.x, gameObjScreenSpace.y);

  // Convert game object screen space to ImGui screen space
  return ImVec2(ObjectScreen.x * window_size.x, ObjectScreen.y * window_size.y);
}

void KX_DebugMode::DrawCircleProjectedOnObject(KX_GameObject *gameObj)
{
  /* Render Custom Circle */
  // Convert game object screen space to ImGui screen space
  ImVec2 ImGuiScreenSpace = GetGameObjectProjectedOnScreen(gameObj);

  // std::cout << window_size.x << "//" << ImGuiScreenSpace.x << "\n";
  ImGui::GetBackgroundDrawList()->AddCircle(ImGuiScreenSpace, 50, IM_COL32(0, 255, 0, 200), 0, 10);
}

void KX_DebugMode::GetGameObjectOnTheScreen() {
	SCA_IInputDevice *inputDevice = KX_GetActiveEngine()->GetInputDevice();
	bool mouseLeftPressed = inputDevice->GetInput(SCA_IInputDevice::LEFTMOUSE).Find(SCA_InputEvent::JUSTRELEASED);
	bool mouseRightPressed = inputDevice->GetInput(SCA_IInputDevice::RIGHTMOUSE).Find(SCA_InputEvent::JUSTRELEASED);

	if (mouseLeftPressed) {

		// Mouse Position Normalized
		float x_coord, y_coord;
		x_coord = KX_GetActiveEngine()->GetCanvas()->GetMouseNormalizedX(inputDevice->GetInput(SCA_IInputDevice::MOUSEX).m_values[0]);
		y_coord = KX_GetActiveEngine()->GetCanvas()->GetMouseNormalizedY(inputDevice->GetInput(SCA_IInputDevice::MOUSEY).m_values[0]);

		// Raycast to Front Scene.
		KX_GameObject::RayCastData rayData = KX_GetActiveEngine()->GetScenes()->GetFront()->GetActiveCamera()->GetScreenRayCast(
        x_coord, y_coord, 100, nullptr);
		if (rayData.m_hitObject) {
			imgui_KXObSelected = rayData.m_hitObject;
			m_pickSceneObject = false;
		}
	}

	if (mouseRightPressed) {
		imgui_KXObSelected = nullptr;
		m_pickSceneObject = false;
	}
}

void KX_DebugMode::EnableCameraController(KX_Camera *camera, bool use_active)
{
  KX_Scene *scene = KX_GetActiveEngine()->GetScenes()->GetFront();

  imgui_controllActiveCamera = true;
  imgui_blockInputEvents = true;

  if (!use_active) {
	  /* Here we will check if the selected camera is the devCam, if it is not,         */
	  /* we will create a new camera and place it in the position of the active camera, */
	  /* then we will make it the active camera and control it.                         */
	  KX_Camera *devCam = scene->GetCameraList()->FindValue("__default__cam__");

	  if (!devCam) {
		KX_GetActiveEngine()->CreateTemporaryCamera(scene, false);
		devCam = scene->GetCameraList()->FindValue("__default__cam__");
	  }
	  if (camera) {
		devCam->SetLens(camera->GetLens());
		devCam->NodeSetWorldPosition(camera->NodeGetWorldPosition());
		devCam->NodeSetGlobalOrientation(camera->NodeGetWorldOrientation());
	  }
	  scene->SetActiveCamera(devCam);
  }

  imgui_cameraSelected = (scene->GetCameraList()->GetCount() - 1);

  KX_GetActiveEngine()->GetCanvas()->SetMouseState(RAS_ICanvas::MOUSE_INVISIBLE);
  KX_GetActiveEngine()->GetPythonMouse()->Recenter(true);
}

void KX_DebugMode::SaveDebugMode_Values() {
	KX_Imgui *imgui = KX_GetActiveEngine()->GetImgui();

	imgui->OpenImgui_Config_ToSave("KX_DebugMode");

	imgui->WriteBoolValue("m_hideDebugMode", m_hideDebugMode);
	imgui->WriteBoolValue("m_autoResize", m_autoResize);
	imgui->WriteFloatValue("m_history", m_history);
	imgui->WriteIntValue("m_axisCondition", (int)m_axisCondition);
	imgui->WriteFloatValue("m_axisLimit", m_axisLimit);
	imgui->WriteFloatValue("m_cameraSpeed", m_cameraSpeed);
	imgui->WriteFloatValue("m_profileSize", m_profileSize);
	imgui->WriteFloatValue("m_debugPropertiesSize", m_debugPropertiesSize);

	imgui->SaveAndCloseImgui_Config();
}

void KX_DebugMode::LoadDebugMode_Values() {
  KX_Imgui *imgui = KX_GetActiveEngine()->GetImgui();

  imgui->OpenImgui_Config_ToLoad();

  bool found = imgui->LoadSection_Config("KX_DebugMode");

  if (!found) {
    return;
  }

  // Load vars ... Keep in sync with SaveDebugMode_Values!!
  m_hideDebugMode = imgui->LoadBoolValue(m_hideDebugMode);
  m_autoResize = imgui->LoadBoolValue(m_autoResize);
  m_history = imgui->LoadFloatValue(m_history);
  m_axisCondition = imgui->LoadIntValue(m_axisCondition);
  m_axisLimit = imgui->LoadFloatValue(m_axisLimit);
  m_cameraSpeed = imgui->LoadFloatValue(m_cameraSpeed);
  m_profileSize = imgui->LoadFloatValue(m_profileSize);
  m_debugPropertiesSize = imgui->LoadFloatValue(m_debugPropertiesSize);

  imgui->CloseImgui_Config();
}
