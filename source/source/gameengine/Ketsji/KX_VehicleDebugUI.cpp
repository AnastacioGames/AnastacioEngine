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

/** \file gameengine/Ketsji/KX_VehicleDebugUI.cpp
 *  \ingroup ketsji
 */

#include "KX_VehicleDebugUI.h"

#include <cmath>
#include <cctype>
#include <fstream>
#include <string>

#include "KX_Globals.h"
#include "KX_ClientObjectInfo.h"
#include "KX_GameObject.h"
#include "KX_KetsjiEngine.h"
#include "KX_Scene.h"
#include "KX_VehiclePreset.h"

#include "BLI_fileops.h"
#include "BLI_path_util.h"
#include "BLI_string.h"
#include "PHY_IPhysicsEnvironment.h"
#include "PHY_IPhysicsController.h"
#include "PHY_IVehicle.h"

#include "KX_Imgui.h"

KX_VehicleDebugUI::KX_VehicleDebugUI()
    : m_selectedConstraintId(-1), m_telemetryPaused(false), m_lastSampledTick((unsigned long long)-1)
{
  m_telemetry.reserve(kTelemetryCapacity);
}

KX_VehicleDebugUI::~KX_VehicleDebugUI()
{
}

std::string KX_VehicleDebugUI::GetPresetPath(PHY_IVehicle *vehicle) const
{
  std::string name = "constraint_" + std::to_string(vehicle->GetUserConstraintId());
  PHY_IPhysicsController *controller = vehicle->GetChassisController();
  KX_ClientObjectInfo *info = controller ? static_cast<KX_ClientObjectInfo *>(controller->GetNewClientInfo()) : nullptr;
  if (info && info->m_gameobject) {
    name = info->m_gameobject->GetName();
  }
  for (char &c : name) {
    if (!(std::isalnum((unsigned char)c) || c == '_' || c == '-')) c = '_';
  }
  char path[FILE_MAX];
  BLI_snprintf(path, sizeof(path), "//vehicle_presets/%s.json", name.c_str());
  BLI_path_abs(path, KX_GetMainPath().c_str());
  return path;
}

void KX_VehicleDebugUI::AutoLoadPresets()
{
  KX_Scene *scene = KX_GetActiveScene();
  PHY_IPhysicsEnvironment *env = scene ? scene->GetPhysicsEnvironment() : nullptr;
  if (!env) return;
  for (int i = 0; i < env->GetNumVehicles(); ++i) {
    PHY_IVehicle *vehicle = env->GetVehicleFromIndex(i);
    if (!vehicle || !m_autoLoadAttempted.insert(vehicle->GetUserConstraintId()).second) continue;
    const std::string path = GetPresetPath(vehicle);
    if (!BLI_exists(path.c_str())) continue;
    KX_VehiclePreset preset;
    std::string error;
    if (KX_LoadVehiclePreset(path, &preset, &error) && KX_ApplyVehiclePreset(vehicle, preset, &error)) {
      m_presetStatus = "Auto-loaded: " + path;
      printf("Vehicle Lab: %s\n", m_presetStatus.c_str());
    } else {
      m_presetStatus = "Auto-load refused: " + error;
      printf("Vehicle Lab: %s (%s)\n", m_presetStatus.c_str(), path.c_str());
    }
  }
}

void KX_VehicleDebugUI::RenderVehicleList()
{
  KX_Scene *scene = KX_GetActiveScene();
  if (!scene) {
    ImGui::TextDisabled("No active scene.");
    return;
  }

  PHY_IPhysicsEnvironment *env = scene->GetPhysicsEnvironment();
  if (!env) {
    ImGui::TextDisabled("No physics environment.");
    return;
  }

  int numVehicles = env->GetNumVehicles();
  if (numVehicles == 0) {
    ImGui::TextDisabled("No vehicles in the active scene.");
    m_selectedConstraintId = -1;
    return;
  }

  if (ImGui::BeginCombo(
          "Vehicle", m_selectedConstraintId >= 0 ?
                         (std::string("Constraint ") + std::to_string(m_selectedConstraintId)).c_str() :
                         "(none)")) {
    for (int i = 0; i < numVehicles; i++) {
      PHY_IVehicle *vehicle = env->GetVehicleFromIndex(i);
      if (!vehicle) {
        continue;
      }
      int constraintId = vehicle->GetUserConstraintId();
      std::string label = "Constraint " + std::to_string(constraintId) + " (" +
                           std::to_string(vehicle->GetNumWheels()) + " wheels)";
      bool selected = (constraintId == m_selectedConstraintId);
      if (ImGui::Selectable(label.c_str(), selected)) {
        m_selectedConstraintId = constraintId;
      }
    }
    ImGui::EndCombo();
  }
}

void KX_VehicleDebugUI::RenderOverviewTab(PHY_IVehicle *vehicle)
{
  mt::vec3 forward = vehicle->GetForwardVector();
  int right, up, fwd;
  vehicle->GetCoordinateSystem(&right, &up, &fwd);

  ImGui::Text("Speed: %.2f km/h  (%.2f m/s)", vehicle->GetCurrentSpeedKmHour(), vehicle->GetCurrentSpeedMps());
  ImGui::Text("Forward axis (world): %.3f, %.3f, %.3f", forward.x, forward.y, forward.z);
  ImGui::Text("Coordinate system: right=%d up=%d forward=%d", right, up, fwd);
  ImGui::Text("Wheels: %d", vehicle->GetNumWheels());
  ImGui::Text("Physics tick: %llu", vehicle->GetPhysicsTick());

  int contactCount = 0;
  for (int i = 0; i < vehicle->GetNumWheels(); i++) {
    PHY_VehicleWheelState state;
    if (vehicle->GetWheelState(i, &state) && state.isInContact) {
      contactCount++;
    }
  }
  ImGui::Text("Wheels in contact: %d / %d", contactCount, vehicle->GetNumWheels());

  /* Gearbox state lives in Python (vehicle_player_component); it is only
   * visible here when the component publishes it as game properties. */
  ImGui::Separator();
  PHY_IPhysicsController *controller = vehicle->GetChassisController();
  KX_ClientObjectInfo *info = controller ? static_cast<KX_ClientObjectInfo *>(controller->GetNewClientInfo()) : nullptr;
  KX_GameObject *chassis = info ? info->m_gameobject : nullptr;
  EXP_Value *gear = chassis ? chassis->GetProperty("vehicle_gear") : nullptr;
  if (!gear) {
    ImGui::TextDisabled("Gear/RPM: enable \"Publish Telemetry\" or \"Show HUD\" in the vehicle component.");
    return;
  }
  EXP_Value *gearbox = chassis->GetProperty("vehicle_gearbox");
  EXP_Value *rpm = chassis->GetProperty("vehicle_rpm");
  if (gearbox) {
    ImGui::Text("Gearbox: %s", gearbox->GetText().c_str());
  }
  ImGui::Text("Gear: %s", gear->GetText().c_str());
  if (rpm) {
    ImGui::Text("Engine RPM: %s", rpm->GetText().c_str());
  }
}

void KX_VehicleDebugUI::RenderSuspensionTab(PHY_IVehicle *vehicle)
{
  if (ImGui::BeginTable(
          "SuspensionTable", 8, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_ScrollY)) {
    ImGui::TableSetupColumn("Wheel");
    ImGui::TableSetupColumn("Contact");
    ImGui::TableSetupColumn("Position");
    ImGui::TableSetupColumn("Rotation");
    ImGui::TableSetupColumn("Contact Normal");
    ImGui::TableSetupColumn("Contact Point");
    ImGui::TableSetupColumn("Suspension Force");
    ImGui::TableSetupColumn("Hard Point WS");
    ImGui::TableHeadersRow();

    for (int i = 0; i < vehicle->GetNumWheels(); i++) {
      PHY_VehicleWheelState state;
      if (!vehicle->GetWheelState(i, &state)) {
        continue;
      }
      ImGui::TableNextRow();
      ImGui::TableSetColumnIndex(0);
      ImGui::Text("%d", i);
      ImGui::TableSetColumnIndex(1);
      ImGui::TextColored(state.isInContact ? ImVec4(0.2f, 1.0f, 0.2f, 1.0f) : ImVec4(1.0f, 0.3f, 0.3f, 1.0f),
                          state.isInContact ? "yes" : "no");
      ImGui::TableSetColumnIndex(2);
      ImGui::Text("%.3f, %.3f, %.3f", state.worldPosition.x, state.worldPosition.y, state.worldPosition.z);
      ImGui::TableSetColumnIndex(3);
      ImGui::Text("%.3f", state.rotation);
      ImGui::TableSetColumnIndex(4);
      if (state.isInContact) {
        ImGui::Text("%.3f, %.3f, %.3f", state.contactNormal.x, state.contactNormal.y, state.contactNormal.z);
      }
      else {
        ImGui::TextDisabled("-");
      }
      ImGui::TableSetColumnIndex(5);
      if (state.isInContact) {
        ImGui::Text("%.3f, %.3f, %.3f", state.contactPoint.x, state.contactPoint.y, state.contactPoint.z);
      }
      else {
        ImGui::TextDisabled("-");
      }
      ImGui::TableSetColumnIndex(6);
      ImGui::Text("%.2f N", state.suspensionForce);
      ImGui::TableSetColumnIndex(7);
      ImGui::Text("%.3f, %.3f, %.3f", state.hardPointWS.x, state.hardPointWS.y, state.hardPointWS.z);
    }
    ImGui::EndTable();
  }

  ImGui::TextDisabled(
      "Only the fields currently exposed by PHY_VehicleWheelState are shown. "
      "skidInfo, applied/limit suspension force and compression are not yet published (roadmap Fase 1B/4).");
}

void KX_VehicleDebugUI::EditFloatField(const char *label,
                                        const char *unit,
                                        float current,
                                        float minVal,
                                        float maxVal,
                                        PendingEdit *pending,
                                        PHY_IVehicle *vehicle,
                                        PHY_VehicleParameterId paramId,
                                        int wheelIndex)
{
  /* Once the backend's live value matches what we last queued, the edit is
   * confirmed applied and stops showing as pending. */
  if (pending->active && std::fabs(current - pending->value) < 1e-4f) {
    pending->active = false;
  }

  float value = pending->active ? pending->value : current;
  std::string sliderLabel = std::string(label) + " (" + unit + ")";
  if (ImGui::SliderFloat(sliderLabel.c_str(), &value, minVal, maxVal)) {
    if (std::isfinite(value)) {
      PHY_VehicleParameterCommand cmd;
      cmd.id = paramId;
      cmd.wheelIndex = wheelIndex;
      cmd.value = value;
      vehicle->QueueParameterCommand(cmd);
      pending->active = true;
      pending->value = value;
    }
  }
  if (pending->active) {
    ImGui::SameLine();
    ImGui::TextDisabled("(pending)");
  }
}

void KX_VehicleDebugUI::RenderEditTab(PHY_IVehicle *vehicle)
{
  ImGui::TextDisabled(
      "Edits are queued and applied at the next safe simulation boundary "
      "(never written directly from this panel). Structural fields (wheel "
      "count/points/axes, radius, rest length, coordinate system) are not "
      "editable here (roadmap Fase 5).");
  ImGui::Separator();

  float mass = vehicle->GetChassisMass();
  if (m_pendingMass.active && std::fabs(mass - m_pendingMass.value) < 1e-4f) {
    m_pendingMass.active = false;
  }
  float massValue = m_pendingMass.active ? m_pendingMass.value : mass;
  if (ImGui::SliderFloat("Chassis mass (kg)", &massValue, 1.0f, 5000.0f)) {
    if (std::isfinite(massValue) && massValue > 0.0f) {
      PHY_VehicleParameterCommand cmd;
      cmd.id = PHY_VEHICLE_PARAM_CHASSIS_MASS;
      cmd.wheelIndex = -1;
      cmd.value = massValue;
      vehicle->QueueParameterCommand(cmd);
      m_pendingMass.active = true;
      m_pendingMass.value = massValue;
    }
  }
  if (m_pendingMass.active) {
    ImGui::SameLine();
    ImGui::TextDisabled("(pending)");
  }

  if (ImGui::Button("Reset suspension")) {
    PHY_VehicleParameterCommand cmd;
    cmd.id = PHY_VEHICLE_PARAM_RESET_SUSPENSION;
    cmd.wheelIndex = -1;
    cmd.value = 0.0f;
    vehicle->QueueParameterCommand(cmd);
  }
  ImGui::TextDisabled("Command, not a persistent property: reapplies rest suspension length.");
  ImGui::Separator();

  int numWheels = vehicle->GetNumWheels();
  for (int i = 0; i < numWheels && i < kMaxTrackedWheels; i++) {
    ImGui::PushID(i);
    if (ImGui::CollapsingHeader((std::string("Wheel ") + std::to_string(i)).c_str())) {
      EditFloatField("Suspension stiffness",
                      "N/m",
                      vehicle->GetSuspensionStiffness(i),
                      0.0f,
                      200.0f,
                      &m_pendingStiffness[i],
                      vehicle,
                      PHY_VEHICLE_PARAM_SUSPENSION_STIFFNESS,
                      i);
      EditFloatField("Damping relaxation",
                      "",
                      vehicle->GetSuspensionDamping(i),
                      0.0f,
                      10.0f,
                      &m_pendingDampingRelax[i],
                      vehicle,
                      PHY_VEHICLE_PARAM_SUSPENSION_DAMPING_RELAXATION,
                      i);
      EditFloatField("Damping compression",
                      "",
                      vehicle->GetSuspensionCompression(i),
                      0.0f,
                      10.0f,
                      &m_pendingDampingCompression[i],
                      vehicle,
                      PHY_VEHICLE_PARAM_SUSPENSION_DAMPING_COMPRESSION,
                      i);
      EditFloatField("Friction slip",
                      "",
                      vehicle->GetWheelFriction(i),
                      0.0f,
                      10.0f,
                      &m_pendingFriction[i],
                      vehicle,
                      PHY_VEHICLE_PARAM_WHEEL_FRICTION,
                      i);
      EditFloatField("Roll influence",
                      "",
                      vehicle->GetRollInfluence(i),
                      0.0f,
                      2.0f,
                      &m_pendingRollInfluence[i],
                      vehicle,
                      PHY_VEHICLE_PARAM_ROLL_INFLUENCE,
                      i);
    }
    ImGui::PopID();
  }
  if (numWheels > kMaxTrackedWheels) {
    ImGui::TextDisabled("Only the first %d wheels are editable in this panel.", kMaxTrackedWheels);
  }
}

void KX_VehicleDebugUI::RenderStructuralTab(PHY_IVehicle *vehicle)
{
  ImGui::TextColored(ImVec4(1.0f, 0.25f, 0.25f, 1.0f), "LOCKED: structural fields require rebuildPreset().");
  ImGui::TextDisabled("Wheel count, connection points, directions, axle, radius, rest length and coordinate system cannot change live.");
  int right, up, forward;
  vehicle->GetCoordinateSystem(&right, &up, &forward);
  ImGui::Text("Coordinate system: right=%d up=%d forward=%d", right, up, forward);
  for (int i = 0; i < vehicle->GetNumWheels(); ++i) {
    PHY_VehicleWheelConfig c;
    if (!vehicle->GetWheelConfig(i, &c)) continue;
    ImGui::Separator();
    ImGui::TextColored(ImVec4(1.0f, 0.4f, 0.4f, 1.0f), "Wheel %d", i);
    ImGui::Text("Point: %.3f, %.3f, %.3f | radius %.3f m | rest %.3f m", c.connectionPoint.x, c.connectionPoint.y, c.connectionPoint.z, c.wheelRadius, c.suspensionRestLength);
    ImGui::Text("Down: %.2f, %.2f, %.2f | axle: %.2f, %.2f, %.2f | steering: %s", c.downDirection.x, c.downDirection.y, c.downDirection.z, c.axleDirection.x, c.axleDirection.y, c.axleDirection.z, c.hasSteering ? "yes" : "no");
  }
}

void KX_VehicleDebugUI::RenderPresetsTab(PHY_IVehicle *vehicle)
{
  const std::string path = GetPresetPath(vehicle);
  ImGui::TextWrapped("Preset: %s", path.c_str());
  if (ImGui::Button("Save preset")) {
    char directory[FILE_MAX];
    BLI_split_dir_part(path.c_str(), directory, sizeof(directory));
    BLI_dir_create_recursive(directory);
    KX_VehiclePreset preset;
    std::string error;
    if (KX_CaptureVehiclePreset(vehicle, &preset, &error) && KX_SaveVehiclePresetAtomic(path, preset, &error)) m_presetStatus = "Saved: " + path;
    else m_presetStatus = "Save failed: " + error;
  }
  ImGui::SameLine();
  if (ImGui::Button("Load preset")) {
    KX_VehiclePreset preset;
    std::string error;
    if (KX_LoadVehiclePreset(path, &preset, &error) && KX_ApplyVehiclePreset(vehicle, preset, &error)) m_presetStatus = "Loaded: " + path;
    else m_presetStatus = "Load refused: " + error;
  }
  ImGui::TextDisabled("Auto-load runs once when this vehicle appears. Incompatible structural files are refused without changing the car.");
  if (!m_presetStatus.empty()) ImGui::TextWrapped("%s", m_presetStatus.c_str());
}

void KX_VehicleDebugUI::RenderDebugDrawTab()
{
  KX_KetsjiEngine *engine = KX_GetActiveEngine();
  if (!engine) {
    return;
  }

  bool enabled = (engine->GetShowVehicleDebug() == KX_DebugOption::FORCE);
  if (ImGui::Checkbox("Enabled", &enabled)) {
    engine->SetShowVehicleDebug(enabled ? KX_DebugOption::FORCE : KX_DebugOption::DISABLE);
  }
  ImGui::TextDisabled(
      "Draws origin, raycast, wheel circle, axle and contact normal for every "
      "live vehicle from the last completed snapshot (Fase 2). "
      "Per-vehicle/per-wheel filtering, scales and a frozen snapshot copy are "
      "deferred to a future iteration of this panel.");
}

void KX_VehicleDebugUI::SampleTelemetry(PHY_IVehicle *vehicle)
{
  if (m_telemetryPaused) {
    return;
  }

  unsigned long long tick = vehicle->GetPhysicsTick();
  if (tick == m_lastSampledTick) {
    return;
  }
  m_lastSampledTick = tick;

  int contactCount = 0;
  for (int i = 0; i < vehicle->GetNumWheels(); i++) {
    PHY_VehicleWheelState state;
    if (vehicle->GetWheelState(i, &state) && state.isInContact) {
      contactCount++;
    }
  }

  TelemetrySample sample;
  sample.physicsTick = tick;
  sample.speedKmh = vehicle->GetCurrentSpeedKmHour();
  sample.numWheelsInContact = contactCount;

  if ((int)m_telemetry.size() >= kTelemetryCapacity) {
    m_telemetry.erase(m_telemetry.begin());
  }
  m_telemetry.push_back(sample);
}

void KX_VehicleDebugUI::RenderTelemetryTab(PHY_IVehicle *vehicle)
{
  SampleTelemetry(vehicle);

  ImGui::Checkbox("Pause sampling", &m_telemetryPaused);
  ImGui::SameLine();
  if (ImGui::Button("Clear")) {
    m_telemetry.clear();
  }
  ImGui::Text("Samples: %d / %d (one per physicsTick)", (int)m_telemetry.size(), kTelemetryCapacity);

  if (ImGui::BeginTable("TelemetryTable",
                         3,
                         ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_ScrollY,
                         ImVec2(0, 200))) {
    ImGui::TableSetupColumn("Tick");
    ImGui::TableSetupColumn("Speed (km/h)");
    ImGui::TableSetupColumn("Wheels in contact");
    ImGui::TableHeadersRow();

    int start = m_telemetry.size() > 64 ? (int)m_telemetry.size() - 64 : 0;
    for (int i = start; i < (int)m_telemetry.size(); i++) {
      const TelemetrySample &s = m_telemetry[i];
      ImGui::TableNextRow();
      ImGui::TableSetColumnIndex(0);
      ImGui::Text("%llu", s.physicsTick);
      ImGui::TableSetColumnIndex(1);
      ImGui::Text("%.2f", s.speedKmh);
      ImGui::TableSetColumnIndex(2);
      ImGui::Text("%d", s.numWheelsInContact);
    }
    ImGui::EndTable();
  }
}

void KX_VehicleDebugUI::Render(bool *open)
{
  if (!ImGui::Begin("Vehicle Lab", open)) {
    ImGui::End();
    return;
  }

  RenderVehicleList();
  ImGui::Separator();

  /* Re-resolve the selection every frame; never keep a PHY_IVehicle* alive
   * across frames. A stale/reused constraint ID just fails to match here. */
  PHY_IVehicle *vehicle = nullptr;
  KX_Scene *scene = KX_GetActiveScene();
  if (scene && m_selectedConstraintId >= 0) {
    PHY_IPhysicsEnvironment *env = scene->GetPhysicsEnvironment();
    if (env) {
      int numVehicles = env->GetNumVehicles();
      for (int i = 0; i < numVehicles; i++) {
        PHY_IVehicle *candidate = env->GetVehicleFromIndex(i);
        if (candidate && candidate->GetUserConstraintId() == m_selectedConstraintId) {
          vehicle = candidate;
          break;
        }
      }
    }
  }

  if (!vehicle) {
    ImGui::TextDisabled("Select a vehicle above.");
    m_telemetry.clear();
    m_lastSampledTick = (unsigned long long)-1;
    for (int i = 0; i < kMaxTrackedWheels; i++) {
      m_pendingStiffness[i].active = false;
      m_pendingDampingRelax[i].active = false;
      m_pendingDampingCompression[i].active = false;
      m_pendingFriction[i].active = false;
      m_pendingRollInfluence[i].active = false;
    }
    m_pendingMass.active = false;
    ImGui::End();
    return;
  }

  if (ImGui::BeginTabBar("VehicleLabTabs")) {
    if (ImGui::BeginTabItem("Overview")) {
      RenderOverviewTab(vehicle);
      ImGui::EndTabItem();
    }
    if (ImGui::BeginTabItem("Suspension")) {
      RenderSuspensionTab(vehicle);
      ImGui::EndTabItem();
    }
    if (ImGui::BeginTabItem("Debug Draw")) {
      RenderDebugDrawTab();
      ImGui::EndTabItem();
    }
    if (ImGui::BeginTabItem("Telemetry")) {
      RenderTelemetryTab(vehicle);
      ImGui::EndTabItem();
    }
    if (ImGui::BeginTabItem("Edit")) {
      RenderEditTab(vehicle);
      ImGui::EndTabItem();
    }
    if (ImGui::BeginTabItem("Structure (locked)")) {
      RenderStructuralTab(vehicle);
      ImGui::EndTabItem();
    }
    if (ImGui::BeginTabItem("Presets")) {
      RenderPresetsTab(vehicle);
      ImGui::EndTabItem();
    }
    ImGui::EndTabBar();
  }

  ImGui::End();
}
