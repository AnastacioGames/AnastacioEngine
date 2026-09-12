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
 * The Original Code is Copyright (C) 2026 by Range Engine.
 * All rights reserved.
 *
 * The Original Code is: all of this file.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_VehiclePreset.h
 *  \ingroup ketsji
 *
 * Parser/validator and atomic save/load for the versioned vehicle preset
 * format (`vehicle_preset_v1.json`, roadmap Fase 5, item 5). Covers only the
 * physical fields already exposed by PHY_IVehicle (structural wheel setup
 * from AddWheel() plus the Fase-4 live-editable tuning fields and chassis
 * mass/coordinate system/ray mask). No UI, legacy adapter or undo here.
 */

#ifndef __KX_VEHICLEPRESET_H__
#define __KX_VEHICLEPRESET_H__

#include <string>
#include <vector>

#include "mathfu.h"

class PHY_IVehicle;

struct KX_VehiclePresetWheel {
  mt::vec3 connectionPoint = mt::zero3;
  mt::vec3 downDirection = mt::vec3(0.0f, 0.0f, -1.0f);
  mt::vec3 axleDirection = mt::vec3(-1.0f, 0.0f, 0.0f);
  float suspensionRestLength = 0.3f;
  float wheelRadius = 0.3f;
  bool hasSteering = false;

  float suspensionStiffness = 20.0f;
  float suspensionDampingRelaxation = 2.3f;
  float suspensionDampingCompression = 4.4f;
  float friction = 1000.0f;
  float rollInfluence = 0.1f;
};

struct KX_VehiclePreset {
  /* Only version 1 is understood; a mismatched version is a hard parse
   * error, not a silent best-effort read. */
  static const int kVersion = 1;

  float chassisMass = 800.0f;
  int rightIndex = 0;
  int upIndex = 2;
  int forwardIndex = 1;
  short rayCastMask = 1;

  std::vector<KX_VehiclePresetWheel> wheels;
};

/* Parses and fully validates `jsonText` as a vehicle_preset_v1 document.
 * Returns false and fills *error (never empty) on any structural problem:
 * truncated/malformed JSON, wrong version, wrong field type, NaN/infinite
 * number, duplicated wheel (same connectionPoint within epsilon), a
 * zero-length direction vector, or a partially-specified wheel (missing
 * required field). On success *out is fully populated and *error is
 * untouched. Unknown object keys are ignored (forward-compatible), unknown
 * top-level "version" values are not. */
bool KX_ParseVehiclePreset(const std::string &jsonText, KX_VehiclePreset *out, std::string *error);

/* Serializes `preset` back to a vehicle_preset_v1 JSON document (pretty
 * printed, stable key order). */
std::string KX_SerializeVehiclePreset(const KX_VehiclePreset &preset);

/* Atomic save: writes to "<path>@" in the same directory then renames onto
 * `path` (the temp+rename technique also used by KX_ParticleDebugUI's sidecar
 * write, though that one merges into a shared keyed file without validation;
 * this save writes one standalone, pre-validated document), so a crash or
 * power loss mid-write can never leave a truncated/corrupt preset. The preset
 * is validated before the temporary file is created, so callers cannot write
 * an invalid document through this C++ API. The temp file is removed if the
 * write or the rename fails, so a failed save leaves no "<path>@" litter
 * behind. Returns false and fills *error on validation/I/O failure; `path`
 * must not contain ".." or be empty (caller is responsible for resolving any
 * "//"-relative UI name to an absolute path and rejecting traversal before
 * calling this). */
bool KX_SaveVehiclePresetAtomic(const std::string &path, const KX_VehiclePreset &preset, std::string *error);

/* Reads and validates the preset at `path`. Returns false and fills *error
 * (I/O failure or validation failure, see KX_ParseVehiclePreset) otherwise. */
bool KX_LoadVehiclePreset(const std::string &path, KX_VehiclePreset *out, std::string *error);

/* Captures the complete physical configuration currently supported by a live
 * vehicle. The returned wheel geometry follows the public Python convention
 * for axleDirection (the same direction accepted by addWheel()). */
bool KX_CaptureVehiclePreset(const PHY_IVehicle *vehicle, KX_VehiclePreset *out, std::string *error);

/* Transactional hot-apply: pushes `preset`'s chassis mass, coordinate system,
 * ray mask and per-wheel tuning fields (suspensionStiffness/
 * DampingRelaxation/DampingCompression, friction, rollInfluence) onto an
 * already-live `vehicle` via QueueParameterCommand/SetCoordinateSystem/
 * SetRayCastMask, applied by the backend at the next safe simulation
 * boundary. Per-wheel *structural* fields (connectionPoint, downDirection,
 * axleDirection, suspensionRestLength, wheelRadius, hasSteering) have no
 * live-parameter equivalent in PHY_IVehicle. They must match the current
 * vehicle (within a small float tolerance) or apply fails before any
 * mutation; this avoids silently accepting geometry this path cannot rebuild.
 * Actually changing wheel count/structure requires destroying and recreating
 * the vehicle with new wheel visual objects, which this slice does not wire
 * up (no UI/game-object plumbing yet); callers needing that must treat it as
 * a failed rebuild and keep the original vehicle, per the roadmap's "falha
 * mantém o veículo original" rule. Returns true if every field was
 * queued/applied. */
bool KX_ApplyVehiclePreset(PHY_IVehicle *vehicle, const KX_VehiclePreset &preset, std::string *error);

#endif /* __KX_VEHICLEPRESET_H__ */
