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

/** \file KX_VehiclePreset.cpp
 *  \ingroup ketsji
 */

#include "KX_VehiclePreset.h"

#include <cmath>
#include <fstream>
#include <sstream>

#include "BLI_blenlib.h"
#include "cJSON.h"
#include "PHY_IVehicle.h"

namespace {

const float kEpsilon = 1e-6f;
/* Configuration was previously supplied as floats and directions are
 * normalized by Bullet. Keep the structural comparison tolerant enough for a
 * save/edit/load round-trip, but never silently accept a meaningfully
 * different wheel layout that this hot-apply path cannot rebuild. */
const float kStructuralComparisonEpsilon = 1e-5f;
/* Structural sanity cap, not a UI limit (the Vehicle Lab panel caps edit at
 * kMaxTrackedWheels=4, but presets may describe vehicles never opened in
 * that panel). Guards against a corrupt/hostile file claiming millions of
 * wheels. */
const int kMaxWheels = 32;

bool IsFiniteVec3(const mt::vec3 &v)
{
  return std::isfinite(v.x) && std::isfinite(v.y) && std::isfinite(v.z);
}

bool GetVec3(const cJSON *obj, const char *key, mt::vec3 *out, std::string *error)
{
  const cJSON *arr = cJSON_GetObjectItemCaseSensitive(obj, key);
  if (!cJSON_IsArray(arr) || cJSON_GetArraySize(arr) != 3) {
    *error = std::string("field \"") + key + "\" must be an array of 3 numbers";
    return false;
  }
  float comp[3];
  for (int i = 0; i < 3; i++) {
    const cJSON *item = cJSON_GetArrayItem(arr, i);
    if (!cJSON_IsNumber(item)) {
      *error = std::string("field \"") + key + "\" has a non-numeric component";
      return false;
    }
    comp[i] = (float)item->valuedouble;
  }
  mt::vec3 v(comp[0], comp[1], comp[2]);
  if (!IsFiniteVec3(v)) {
    *error = std::string("field \"") + key + "\" contains NaN/infinite";
    return false;
  }
  *out = v;
  return true;
}

bool GetFloat(const cJSON *obj, const char *key, float *out, std::string *error)
{
  const cJSON *item = cJSON_GetObjectItemCaseSensitive(obj, key);
  if (!cJSON_IsNumber(item)) {
    *error = std::string("field \"") + key + "\" must be a number";
    return false;
  }
  float v = (float)item->valuedouble;
  if (!std::isfinite(v)) {
    *error = std::string("field \"") + key + "\" contains NaN/infinite";
    return false;
  }
  *out = v;
  return true;
}

bool GetBool(const cJSON *obj, const char *key, bool *out, std::string *error)
{
  const cJSON *item = cJSON_GetObjectItemCaseSensitive(obj, key);
  if (!cJSON_IsBool(item)) {
    *error = std::string("field \"") + key + "\" must be a boolean";
    return false;
  }
  *out = cJSON_IsTrue(item);
  return true;
}

bool GetIntInRange(const cJSON *obj, const char *key, int minVal, int maxVal, int *out, std::string *error)
{
  const cJSON *item = cJSON_GetObjectItemCaseSensitive(obj, key);
  if (!cJSON_IsNumber(item)) {
    *error = std::string("field \"") + key + "\" must be an integer";
    return false;
  }
  double d = item->valuedouble;
  if (!std::isfinite(d) || d != std::floor(d) || d < minVal || d > maxVal) {
    *error = std::string("field \"") + key + "\" must be an integer in range";
    return false;
  }
  *out = (int)d;
  return true;
}

bool ParseWheel(const cJSON *wheelObj, int index, KX_VehiclePresetWheel *out, std::string *error)
{
  if (!cJSON_IsObject(wheelObj)) {
    *error = "wheels[" + std::to_string(index) + "] is not an object";
    return false;
  }

  KX_VehiclePresetWheel wheel;
  std::string fieldError;

  if (!GetVec3(wheelObj, "connectionPoint", &wheel.connectionPoint, &fieldError) ||
      !GetVec3(wheelObj, "downDirection", &wheel.downDirection, &fieldError) ||
      !GetVec3(wheelObj, "axleDirection", &wheel.axleDirection, &fieldError) ||
      !GetFloat(wheelObj, "suspensionRestLength", &wheel.suspensionRestLength, &fieldError) ||
      !GetFloat(wheelObj, "wheelRadius", &wheel.wheelRadius, &fieldError) ||
      !GetBool(wheelObj, "hasSteering", &wheel.hasSteering, &fieldError) ||
      !GetFloat(wheelObj, "suspensionStiffness", &wheel.suspensionStiffness, &fieldError) ||
      !GetFloat(wheelObj, "suspensionDampingRelaxation", &wheel.suspensionDampingRelaxation, &fieldError) ||
      !GetFloat(wheelObj, "suspensionDampingCompression", &wheel.suspensionDampingCompression, &fieldError) ||
      !GetFloat(wheelObj, "friction", &wheel.friction, &fieldError) ||
      !GetFloat(wheelObj, "rollInfluence", &wheel.rollInfluence, &fieldError)) {
    *error = "wheels[" + std::to_string(index) + "]: " + fieldError;
    return false;
  }

  if (wheel.downDirection.LengthSquared() < kEpsilon || wheel.axleDirection.LengthSquared() < kEpsilon) {
    *error = "wheels[" + std::to_string(index) + "]: downDirection/axleDirection must not be zero-length";
    return false;
  }
  const float collinearity = std::abs(mt::vec3::DotProduct(wheel.downDirection.Normalized(),
                                                            wheel.axleDirection.Normalized()));
  if (collinearity > 0.999f) {
    *error = "wheels[" + std::to_string(index) + "]: downDirection and axleDirection must not be collinear";
    return false;
  }
  if (wheel.wheelRadius <= 0.0f) {
    *error = "wheels[" + std::to_string(index) + "]: wheelRadius must be > 0";
    return false;
  }
  if (wheel.suspensionRestLength < 0.0f) {
    *error = "wheels[" + std::to_string(index) + "]: suspensionRestLength must be >= 0";
    return false;
  }
  if (wheel.suspensionStiffness < 0.0f || wheel.suspensionDampingRelaxation < 0.0f ||
      wheel.suspensionDampingCompression < 0.0f || wheel.friction < 0.0f || wheel.rollInfluence < 0.0f) {
    *error = "wheels[" + std::to_string(index) + "]: tuning fields must be >= 0";
    return false;
  }

  *out = wheel;
  return true;
}

void AddVec3(cJSON *obj, const char *key, const mt::vec3 &v)
{
  cJSON *arr = cJSON_CreateArray();
  cJSON_AddItemToArray(arr, cJSON_CreateNumber(v.x));
  cJSON_AddItemToArray(arr, cJSON_CreateNumber(v.y));
  cJSON_AddItemToArray(arr, cJSON_CreateNumber(v.z));
  cJSON_AddItemToObject(obj, key, arr);
}

bool NearlyEqual(float a, float b)
{
  return std::abs(a - b) <= kStructuralComparisonEpsilon;
}

bool NearlyEqualVec3(const mt::vec3 &a, const mt::vec3 &b)
{
  return (a - b).LengthSquared() <=
         kStructuralComparisonEpsilon * kStructuralComparisonEpsilon;
}

bool MatchesLiveWheelStructure(const PHY_VehicleWheelConfig &live,
                               const KX_VehiclePresetWheel &candidate)
{
  /* PHY stores the Bullet-side sign; presets intentionally use the Python
   * addWheel()/getWheelConfig() convention. */
  return NearlyEqualVec3(live.connectionPoint, candidate.connectionPoint) &&
         NearlyEqualVec3(live.downDirection, candidate.downDirection.Normalized()) &&
         NearlyEqualVec3(-live.axleDirection, candidate.axleDirection.Normalized()) &&
         NearlyEqual(live.suspensionRestLength, candidate.suspensionRestLength) &&
         NearlyEqual(live.wheelRadius, candidate.wheelRadius) &&
         live.hasSteering == candidate.hasSteering;
}

}  // namespace

bool KX_ParseVehiclePreset(const std::string &jsonText, KX_VehiclePreset *out, std::string *error)
{
  if (jsonText.empty()) {
    *error = "empty preset file";
    return false;
  }

  cJSON *root = cJSON_ParseWithOpts(jsonText.c_str(), nullptr, 1);
  if (!root) {
    *error = "malformed/truncated JSON";
    return false;
  }
  if (!cJSON_IsObject(root)) {
    *error = "root is not a JSON object";
    cJSON_Delete(root);
    return false;
  }

  bool ok = true;
  std::string localError;
  KX_VehiclePreset preset;

  int version = -1;
  if (!GetIntInRange(root, "version", 1, 1, &version, &localError)) {
    localError = "unsupported/missing \"version\" (expected " + std::to_string(KX_VehiclePreset::kVersion) + ")";
    ok = false;
  }

  if (ok && !GetFloat(root, "chassisMass", &preset.chassisMass, &localError)) {
    ok = false;
  }
  if (ok && preset.chassisMass <= 0.0f) {
    localError = "chassisMass must be > 0";
    ok = false;
  }

  const cJSON *coordSys = ok ? cJSON_GetObjectItemCaseSensitive(root, "coordinateSystem") : nullptr;
  if (ok && !cJSON_IsObject(coordSys)) {
    localError = "field \"coordinateSystem\" must be an object";
    ok = false;
  }
  if (ok && (!GetIntInRange(coordSys, "right", 0, 2, &preset.rightIndex, &localError) ||
             !GetIntInRange(coordSys, "up", 0, 2, &preset.upIndex, &localError) ||
             !GetIntInRange(coordSys, "forward", 0, 2, &preset.forwardIndex, &localError))) {
    ok = false;
  }
  if (ok && !(preset.rightIndex != preset.upIndex && preset.upIndex != preset.forwardIndex &&
              preset.rightIndex != preset.forwardIndex)) {
    localError = "coordinateSystem right/up/forward must be a permutation of {0,1,2}";
    ok = false;
  }

  int rayCastMask = 1;
  if (ok && !GetIntInRange(root, "rayCastMask", 0, 32767, &rayCastMask, &localError)) {
    ok = false;
  }
  else if (ok) {
    preset.rayCastMask = (short)rayCastMask;
  }

  const cJSON *wheelsArr = ok ? cJSON_GetObjectItemCaseSensitive(root, "wheels") : nullptr;
  if (ok && !cJSON_IsArray(wheelsArr)) {
    localError = "field \"wheels\" must be an array";
    ok = false;
  }
  int numWheels = ok ? cJSON_GetArraySize(wheelsArr) : 0;
  if (ok && (numWheels < 1 || numWheels > kMaxWheels)) {
    localError = "\"wheels\" must contain between 1 and " + std::to_string(kMaxWheels) + " entries";
    ok = false;
  }

  if (ok) {
    preset.wheels.reserve(numWheels);
    for (int i = 0; i < numWheels && ok; i++) {
      KX_VehiclePresetWheel wheel;
      if (!ParseWheel(cJSON_GetArrayItem(wheelsArr, i), i, &wheel, &localError)) {
        ok = false;
        break;
      }
      for (const KX_VehiclePresetWheel &existing : preset.wheels) {
        if ((existing.connectionPoint - wheel.connectionPoint).LengthSquared() < kEpsilon) {
          localError = "wheels[" + std::to_string(i) + "]: duplicated connectionPoint";
          ok = false;
          break;
        }
      }
      if (!ok) {
        break;
      }
      preset.wheels.push_back(wheel);
    }
  }

  cJSON_Delete(root);

  if (!ok) {
    *error = localError;
    return false;
  }

  *out = preset;
  return true;
}

std::string KX_SerializeVehiclePreset(const KX_VehiclePreset &preset)
{
  cJSON *root = cJSON_CreateObject();
  cJSON_AddNumberToObject(root, "version", KX_VehiclePreset::kVersion);
  cJSON_AddNumberToObject(root, "chassisMass", preset.chassisMass);

  cJSON *coordSys = cJSON_CreateObject();
  cJSON_AddNumberToObject(coordSys, "right", preset.rightIndex);
  cJSON_AddNumberToObject(coordSys, "up", preset.upIndex);
  cJSON_AddNumberToObject(coordSys, "forward", preset.forwardIndex);
  cJSON_AddItemToObject(root, "coordinateSystem", coordSys);

  cJSON_AddNumberToObject(root, "rayCastMask", preset.rayCastMask);

  cJSON *wheelsArr = cJSON_CreateArray();
  for (const KX_VehiclePresetWheel &wheel : preset.wheels) {
    cJSON *w = cJSON_CreateObject();
    AddVec3(w, "connectionPoint", wheel.connectionPoint);
    AddVec3(w, "downDirection", wheel.downDirection);
    AddVec3(w, "axleDirection", wheel.axleDirection);
    cJSON_AddNumberToObject(w, "suspensionRestLength", wheel.suspensionRestLength);
    cJSON_AddNumberToObject(w, "wheelRadius", wheel.wheelRadius);
    cJSON_AddBoolToObject(w, "hasSteering", wheel.hasSteering);
    cJSON_AddNumberToObject(w, "suspensionStiffness", wheel.suspensionStiffness);
    cJSON_AddNumberToObject(w, "suspensionDampingRelaxation", wheel.suspensionDampingRelaxation);
    cJSON_AddNumberToObject(w, "suspensionDampingCompression", wheel.suspensionDampingCompression);
    cJSON_AddNumberToObject(w, "friction", wheel.friction);
    cJSON_AddNumberToObject(w, "rollInfluence", wheel.rollInfluence);
    cJSON_AddItemToArray(wheelsArr, w);
  }
  cJSON_AddItemToObject(root, "wheels", wheelsArr);

  char *outStr = cJSON_Print(root);
  std::string result(outStr);
  free(outStr);
  cJSON_Delete(root);
  return result;
}

bool KX_SaveVehiclePresetAtomic(const std::string &path, const KX_VehiclePreset &preset, std::string *error)
{
  if (path.empty() || path.find("..") != std::string::npos) {
    *error = "invalid preset path";
    return false;
  }

  /* This is public C++ API, so do not rely on callers having come through
   * KX_ParseVehiclePreset. Never atomically publish a document we would
   * refuse to load later. */
  KX_VehiclePreset checked;
  if (!KX_ParseVehiclePreset(KX_SerializeVehiclePreset(preset), &checked, error)) {
    return false;
  }
  std::string json = KX_SerializeVehiclePreset(checked);

  char tempname[FILE_MAX];
  BLI_snprintf(tempname, sizeof(tempname), "%s@", path.c_str());

  std::ofstream outFile(tempname, std::ios::binary);
  if (!outFile.is_open()) {
    *error = "could not open temp file for write: " + std::string(tempname);
    return false;
  }
  outFile << json;
  outFile.close();
  if (outFile.fail()) {
    *error = "write failed: " + std::string(tempname);
    BLI_delete(tempname, false, false);
    return false;
  }

  if (BLI_rename(tempname, path.c_str()) != 0) {
    *error = "rename failed: " + std::string(tempname) + " -> " + path;
    BLI_delete(tempname, false, false);
    return false;
  }

  return true;
}

bool KX_LoadVehiclePreset(const std::string &path, KX_VehiclePreset *out, std::string *error)
{
  std::ifstream inFile(path, std::ios::binary);
  if (!inFile.is_open()) {
    *error = "could not open preset file: " + path;
    return false;
  }
  std::stringstream buf;
  buf << inFile.rdbuf();

  return KX_ParseVehiclePreset(buf.str(), out, error);
}

bool KX_CaptureVehiclePreset(const PHY_IVehicle *vehicle, KX_VehiclePreset *out, std::string *error)
{
  if (!vehicle) {
    *error = "no vehicle to capture";
    return false;
  }

  const int numWheels = vehicle->GetNumWheels();
  if (numWheels < 1 || numWheels > kMaxWheels) {
    *error = "vehicle has an unsupported wheel count";
    return false;
  }

  KX_VehiclePreset preset;
  preset.chassisMass = vehicle->GetChassisMass();
  vehicle->GetCoordinateSystem(&preset.rightIndex, &preset.upIndex, &preset.forwardIndex);
  preset.rayCastMask = vehicle->GetRayCastMask();
  preset.wheels.reserve(numWheels);

  for (int i = 0; i < numWheels; ++i) {
    PHY_VehicleWheelConfig config;
    if (!vehicle->GetWheelConfig(i, &config)) {
      *error = "could not capture wheel " + std::to_string(i) + " configuration";
      return false;
    }
    KX_VehiclePresetWheel wheel;
    wheel.connectionPoint = config.connectionPoint;
    wheel.downDirection = config.downDirection;
    /* PHY stores Bullet's internal axle winding; expose the documented public
     * convention so an exported preset agrees with getWheelConfig(). */
    wheel.axleDirection = -config.axleDirection;
    wheel.suspensionRestLength = config.suspensionRestLength;
    wheel.wheelRadius = config.wheelRadius;
    wheel.hasSteering = config.hasSteering;
    wheel.suspensionStiffness = vehicle->GetSuspensionStiffness(i);
    wheel.suspensionDampingRelaxation = vehicle->GetSuspensionDamping(i);
    wheel.suspensionDampingCompression = vehicle->GetSuspensionCompression(i);
    wheel.friction = vehicle->GetWheelFriction(i);
    wheel.rollInfluence = vehicle->GetRollInfluence(i);
    preset.wheels.push_back(wheel);
  }

  /* Use the parser as one canonical validation path before returning a
   * capture. This also protects callers if a backend ever returns invalid
   * data rather than emitting a preset that cannot later be reloaded. */
  KX_VehiclePreset checked;
  if (!KX_ParseVehiclePreset(KX_SerializeVehiclePreset(preset), &checked, error)) {
    return false;
  }
  *out = checked;
  return true;
}

bool KX_ApplyVehiclePreset(PHY_IVehicle *vehicle, const KX_VehiclePreset &preset, std::string *error)
{
  if (!vehicle) {
    *error = "no vehicle to apply the preset to";
    return false;
  }
  /* KX_VehiclePreset is a public C++ struct, so callers are not necessarily
   * coming through the JSON parser. Validate the entire candidate before the
   * first mutation/command is issued. */
  KX_VehiclePreset checked;
  if (!KX_ParseVehiclePreset(KX_SerializeVehiclePreset(preset), &checked, error)) {
    return false;
  }
  if (vehicle->GetNumWheels() != (int)checked.wheels.size()) {
    *error = "preset has " + std::to_string(checked.wheels.size()) + " wheel(s) but the vehicle has " +
             std::to_string(vehicle->GetNumWheels()) +
             "; changing wheel count/structure is not supported by this apply path";
    return false;
  }

  /* This path owns no wheel visual-object/motion-state references, therefore
   * it cannot rebuild a wheel safely. Reject an edited structural field
   * before touching coordinate system, mask or queued tuning rather than
   * accepting the file and silently leaving the old geometry in place. */
  for (int i = 0; i < (int)checked.wheels.size(); ++i) {
    PHY_VehicleWheelConfig live;
    if (!vehicle->GetWheelConfig(i, &live)) {
      *error = "could not inspect live wheel " + std::to_string(i) + " structure";
      return false;
    }
    if (!MatchesLiveWheelStructure(live, checked.wheels[i])) {
      *error = "preset changes structural fields of wheel " + std::to_string(i) +
               "; structural rebuild is not supported by this apply path";
      return false;
    }
  }

  vehicle->SetCoordinateSystem(checked.rightIndex, checked.upIndex, checked.forwardIndex);
  vehicle->SetRayCastMask(checked.rayCastMask);

  PHY_VehicleParameterCommand cmd;
  cmd.id = PHY_VEHICLE_PARAM_CHASSIS_MASS;
  cmd.wheelIndex = -1;
  cmd.value = checked.chassisMass;
  vehicle->QueueParameterCommand(cmd);

  for (int i = 0; i < (int)checked.wheels.size(); i++) {
    const KX_VehiclePresetWheel &wheel = checked.wheels[i];

    cmd.wheelIndex = i;
    cmd.id = PHY_VEHICLE_PARAM_SUSPENSION_STIFFNESS;
    cmd.value = wheel.suspensionStiffness;
    vehicle->QueueParameterCommand(cmd);

    cmd.id = PHY_VEHICLE_PARAM_SUSPENSION_DAMPING_RELAXATION;
    cmd.value = wheel.suspensionDampingRelaxation;
    vehicle->QueueParameterCommand(cmd);

    cmd.id = PHY_VEHICLE_PARAM_SUSPENSION_DAMPING_COMPRESSION;
    cmd.value = wheel.suspensionDampingCompression;
    vehicle->QueueParameterCommand(cmd);

    cmd.id = PHY_VEHICLE_PARAM_WHEEL_FRICTION;
    cmd.value = wheel.friction;
    vehicle->QueueParameterCommand(cmd);

    cmd.id = PHY_VEHICLE_PARAM_ROLL_INFLUENCE;
    cmd.value = wheel.rollInfluence;
    vehicle->QueueParameterCommand(cmd);
  }

  return true;
}
