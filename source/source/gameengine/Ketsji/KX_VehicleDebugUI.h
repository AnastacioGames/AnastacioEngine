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

/** \file KX_VehicleDebugUI.h
 *  \ingroup ketsji
 *
 * Read-only Vehicle Lab panel (roadmap Fase 3). Enumerates vehicles through
 * PHY_IPhysicsEnvironment only (never downcasts to a backend-specific type,
 * never touches CcdPhysicsEnvironment::m_wrapperVehicles), and revalidates
 * its selection every frame instead of caching a PHY_IVehicle* across frames.
 */

#ifndef KX_VEHICLEDEBUGUI_H
#define KX_VEHICLEDEBUGUI_H

#include <set>
#include <string>
#include <vector>

#include "../Physics/Common/PHY_IVehicle.h"

class KX_VehicleDebugUI
{
 public:
  KX_VehicleDebugUI();
  ~KX_VehicleDebugUI();

  /* Draws the "Vehicle Lab" window. Safe to call every frame regardless of
   * whether a vehicle is currently selected/alive; does nothing to physics. */
  void Render(bool *open);
  /* Called every debug frame, even while the Lab window is closed. */
  void AutoLoadPresets();

 private:
  struct TelemetrySample {
    unsigned long long physicsTick;
    float speedKmh;
    int numWheelsInContact;
  };

  /* Selection is a constraint ID only, re-resolved against the active
   * scene's live vehicle list every frame. Never a stored PHY_IVehicle*. */
  int m_selectedConstraintId;

  bool m_telemetryPaused;
  unsigned long long m_lastSampledTick;
  std::vector<TelemetrySample> m_telemetry;
  std::set<int> m_autoLoadAttempted;
  std::string m_presetStatus;
  static const int kTelemetryCapacity = 512;

  /* Live-edit tab (roadmap Fase 4). All edits go through
   * PHY_IVehicle::QueueParameterCommand; this class never writes a wheel
   * field directly. m_pendingLabel/m_pendingUntilTick track, per control,
   * a short "pending" note until the backend's live value catches up. */
  struct PendingEdit {
    bool active = false;
    float value = 0.0f;
  };
  static const int kMaxTrackedWheels = 8;
  PendingEdit m_pendingStiffness[kMaxTrackedWheels];
  PendingEdit m_pendingDampingRelax[kMaxTrackedWheels];
  PendingEdit m_pendingDampingCompression[kMaxTrackedWheels];
  PendingEdit m_pendingFriction[kMaxTrackedWheels];
  PendingEdit m_pendingRollInfluence[kMaxTrackedWheels];
  PendingEdit m_pendingMass;

  void RenderVehicleList();
  void RenderOverviewTab(PHY_IVehicle *vehicle);
  void RenderSuspensionTab(PHY_IVehicle *vehicle);
  void RenderDebugDrawTab();
  void RenderTelemetryTab(PHY_IVehicle *vehicle);
  void RenderEditTab(PHY_IVehicle *vehicle);
  void RenderStructuralTab(PHY_IVehicle *vehicle);
  void RenderPresetsTab(PHY_IVehicle *vehicle);
  std::string GetPresetPath(PHY_IVehicle *vehicle) const;
  void SampleTelemetry(PHY_IVehicle *vehicle);
  void EditFloatField(const char *label,
                       const char *unit,
                       float current,
                       float minVal,
                       float maxVal,
                       PendingEdit *pending,
                       PHY_IVehicle *vehicle,
                       PHY_VehicleParameterId paramId,
                       int wheelIndex);
};

#endif  // KX_VEHICLEDEBUGUI_H
