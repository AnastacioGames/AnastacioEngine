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

/** \file KX_ParticleDebugUI.cpp
 *  \ingroup ketsji
 */

#include "KX_ParticleDebugUI.h"

#include "KX_GameObject.h"
#include "KX_Globals.h"
#include "RAS_ParticleBuffer.h"

#include "implot.h"  // already has imgui.h, same include KX_Imgui.h/KX_DebugMode.h use

#include "BLI_blenlib.h"
#include "cJSON.h"

#ifdef WITH_PYTHON
#  include "EXP_Python.h"
#endif

#include <cstring>
#include <fstream>
#include <sstream>

namespace KX_ParticleDebugUI {

/// Matches rna_enum_gpu_particle_billboard_mode_items identifiers in rna_object.c.
static const char *BillboardModeIdentifier(short mode)
{
	switch (mode) {
		case 1: return "VERTICAL";
		case 2: return "HORIZONTAL";
		default: return "CAMERA_FACING";
	}
}

/// Matches rna_enum_gpu_particle_collision_mode_items identifiers in rna_object.c.
static const char *CollisionModeIdentifier(short mode)
{
	switch (mode) {
		case 1: return "GROUND";
		case 2: return "DEPTH";
		default: return "NONE";
	}
}

bool Draw(KX_GameObject *gameobj, RAS_ParticleBuffer *buffer)
{
	bool applyClicked = false;

	std::string title = "Particle Debug - " + gameobj->GetName();
	ImGui::SetNextWindowSize(ImVec2(340.0f, 0.0f), ImGuiCond_FirstUseEver);
	if (!ImGui::Begin(title.c_str())) {
		ImGui::End();
		return false;
	}

	float lifetime = buffer->GetLifetime();
	if (ImGui::SliderFloat("Lifetime", &lifetime, 0.1f, 20.0f)) {
		buffer->SetLifetime(lifetime);
	}

	int particleCount = static_cast<int>(buffer->GetParticleCount());
	if (ImGui::SliderInt("Particle Count", &particleCount, 1, 20000)) {
		buffer->Resize(static_cast<unsigned int>(particleCount));
	}

	ImGui::Separator();
	ImGui::Text("Emitter");
	float emitterRadius = buffer->GetEmitterRadius();
	if (ImGui::SliderFloat("Emitter Radius", &emitterRadius, 0.0f, 20.0f)) {
		buffer->SetEmitterRadius(emitterRadius);
	}

	ImGui::Separator();
	ImGui::Text("Motion");
	float gravity[3];
	memcpy(gravity, buffer->GetGravity(), sizeof(gravity));
	if (ImGui::SliderFloat3("Gravity", gravity, -50.0f, 50.0f)) {
		buffer->SetGravity(gravity);
	}
	float velocity[3];
	memcpy(velocity, buffer->GetVelocityBase(), sizeof(velocity));
	if (ImGui::SliderFloat3("Velocity", velocity, -50.0f, 50.0f)) {
		buffer->SetVelocityBase(velocity);
	}
	float velocityRandomness = buffer->GetVelocityRandomness();
	if (ImGui::SliderFloat("Velocity Randomness", &velocityRandomness, 0.0f, 20.0f)) {
		buffer->SetVelocityRandomness(velocityRandomness);
	}

	ImGui::Separator();
	ImGui::Text("Vortex / Cone (Tornado)");
	bool useVortex = buffer->GetUseVortex();
	if (ImGui::Checkbox("Use Vortex", &useVortex)) {
		buffer->SetUseVortex(useVortex);
	}
	if (useVortex) {
		float vortexRotationSpeed = buffer->GetVortexRotationSpeed();
		if (ImGui::SliderFloat("Rotation Speed", &vortexRotationSpeed, -720.0f, 720.0f)) {
			buffer->SetVortexRotationSpeed(vortexRotationSpeed);
		}
		float vortexRadiusTop = buffer->GetVortexRadiusTop();
		if (ImGui::SliderFloat("Top Radius", &vortexRadiusTop, 0.0f, 20.0f)) {
			buffer->SetVortexRadiusTop(vortexRadiusTop);
		}
		float vortexHeight = buffer->GetVortexHeight();
		if (ImGui::SliderFloat("Height", &vortexHeight, 0.01f, 50.0f)) {
			buffer->SetVortexHeight(vortexHeight);
		}
	}

	ImGui::Separator();
	ImGui::Text("Emission Cone");
	float emissionDir[3];
	memcpy(emissionDir, buffer->GetEmissionDirection(), sizeof(emissionDir));
	if (ImGui::SliderFloat3("Emission Direction", emissionDir, -1.0f, 1.0f)) {
		buffer->SetEmissionDirection(emissionDir);
	}
	float emissionAngle = buffer->GetEmissionAngle();
	if (ImGui::SliderFloat("Emission Angle", &emissionAngle, 0.0f, 180.0f)) {
		buffer->SetEmissionAngle(emissionAngle);
	}

	ImGui::Separator();
	ImGui::Text("Appearance");
	float size = buffer->GetBillboardSize();
	if (ImGui::SliderFloat("Size", &size, 0.0f, 10.0f)) {
		buffer->SetBillboardSize(size);
	}
	float endSize = buffer->GetEndSize();
	if (ImGui::SliderFloat("End Size", &endSize, 0.0f, 10.0f)) {
		buffer->SetEndSize(endSize);
	}
	float color[4];
	memcpy(color, buffer->GetColor(), sizeof(color));
	if (ImGui::ColorEdit4("Color", color)) {
		buffer->SetColor(color);
	}
	float endColor[4];
	memcpy(endColor, buffer->GetEndColor(), sizeof(endColor));
	if (ImGui::ColorEdit4("End Color", endColor)) {
		buffer->SetEndColor(endColor);
	}
	static const char *billboardModeItems[] = {"Camera Facing", "Vertical", "Horizontal (Facing Down)"};
	int billboardMode = static_cast<int>(buffer->GetBillboardMode());
	if (ImGui::Combo("Billboard Mode", &billboardMode, billboardModeItems, IM_ARRAYSIZE(billboardModeItems))) {
		buffer->SetBillboardMode(static_cast<short>(billboardMode));
	}
	bool backfaceCulling = buffer->GetBackfaceCulling();
	if (ImGui::Checkbox("Backface Culling", &backfaceCulling)) {
		buffer->SetBackfaceCulling(backfaceCulling);
	}

	ImGui::Separator();
	ImGui::Text("Collision");
	static const char *collisionModeItems[] = {"None", "Ground Plane", "Screen-Space"};
	int collisionMode = static_cast<int>(buffer->GetCollisionMode());
	if (ImGui::Combo("Collision Mode", &collisionMode, collisionModeItems, IM_ARRAYSIZE(collisionModeItems))) {
		buffer->SetCollisionMode(static_cast<short>(collisionMode));
	}
	if (collisionMode != 0) {
		if (collisionMode == 1) {
			float collisionHeight = buffer->GetCollisionHeight();
			if (ImGui::DragFloat("Ground Height", &collisionHeight, 0.05f)) {
				buffer->SetCollisionHeight(collisionHeight);
			}
		}
		float collisionBounce = buffer->GetCollisionBounce();
		if (ImGui::SliderFloat("Bounce", &collisionBounce, 0.0f, 1.0f)) {
			buffer->SetCollisionBounce(collisionBounce);
		}
		float collisionFriction = buffer->GetCollisionFriction();
		if (ImGui::SliderFloat("Friction", &collisionFriction, 0.0f, 1.0f)) {
			buffer->SetCollisionFriction(collisionFriction);
		}
	}

	ImGui::Separator();
	if (ImGui::Button("Apply to .blend")) {
		applyClicked = true;
	}

	ImGui::End();
	return applyClicked;
}

#ifdef WITH_PYTHON

/// Steals no reference to value; clears any Python exception on failure (missing/renamed
/// property on an older .blend) instead of letting it propagate into the game loop.
static void TrySetAttr(PyObject *obj, const char *attr, PyObject *value)
{
	if (!value) {
		PyErr_Clear();
		return;
	}
	if (PyObject_SetAttrString(obj, attr, value) != 0) {
		PyErr_Clear();
	}
	Py_DECREF(value);
}

static bool ApplyToBpy(const std::string &objectName, RAS_ParticleBuffer *buffer)
{
	PyObject *bpyModule = PyImport_ImportModule("bpy");
	if (!bpyModule) {
		PyErr_Clear();
		return false;
	}

	bool applied = false;
	PyObject *data = PyObject_GetAttrString(bpyModule, "data");
	if (data) {
		PyObject *objects = PyObject_GetAttrString(data, "objects");
		if (objects) {
			PyObject *obj = PyObject_CallMethod(objects, "get", "s", objectName.c_str());
			if (obj && obj != Py_None) {
				PyObject *gp = PyObject_GetAttrString(obj, "gpu_particles");
				if (gp) {
					const float *gravity = buffer->GetGravity();
					const float *velocity = buffer->GetVelocityBase();
					const float *color = buffer->GetColor();
					const float *endColor = buffer->GetEndColor();
					const float *emissionDir = buffer->GetEmissionDirection();

					TrySetAttr(gp, "gravity", Py_BuildValue("(fff)", gravity[0], gravity[1], gravity[2]));
					TrySetAttr(gp, "lifetime", PyFloat_FromDouble(buffer->GetLifetime()));
					TrySetAttr(gp, "emitter_radius", PyFloat_FromDouble(buffer->GetEmitterRadius()));
					TrySetAttr(gp, "velocity", Py_BuildValue("(fff)", velocity[0], velocity[1], velocity[2]));
					TrySetAttr(gp, "velocity_randomness", PyFloat_FromDouble(buffer->GetVelocityRandomness()));
					TrySetAttr(gp, "size", PyFloat_FromDouble(buffer->GetBillboardSize()));
					TrySetAttr(gp, "color", Py_BuildValue("(ffff)", color[0], color[1], color[2], color[3]));
					TrySetAttr(gp, "end_color", Py_BuildValue("(ffff)", endColor[0], endColor[1], endColor[2], endColor[3]));
					TrySetAttr(gp, "end_size", PyFloat_FromDouble(buffer->GetEndSize()));
					TrySetAttr(gp, "particle_count", PyLong_FromLong(static_cast<long>(buffer->GetParticleCount())));
					TrySetAttr(gp, "emission_direction", Py_BuildValue("(fff)", emissionDir[0], emissionDir[1], emissionDir[2]));
					TrySetAttr(gp, "emission_angle", PyFloat_FromDouble(buffer->GetEmissionAngle()));
					TrySetAttr(gp, "billboard_mode", PyUnicode_FromString(
						BillboardModeIdentifier(buffer->GetBillboardMode())));
					TrySetAttr(gp, "use_backface_culling", PyBool_FromLong(buffer->GetBackfaceCulling() ? 1 : 0));
					TrySetAttr(gp, "collision_mode", PyUnicode_FromString(
						CollisionModeIdentifier(buffer->GetCollisionMode())));
					TrySetAttr(gp, "collision_height", PyFloat_FromDouble(buffer->GetCollisionHeight()));
					TrySetAttr(gp, "collision_bounce", PyFloat_FromDouble(buffer->GetCollisionBounce()));
					TrySetAttr(gp, "collision_friction", PyFloat_FromDouble(buffer->GetCollisionFriction()));
					TrySetAttr(gp, "use_vortex", PyBool_FromLong(buffer->GetUseVortex() ? 1 : 0));
					TrySetAttr(gp, "vortex_rotation_speed", PyFloat_FromDouble(buffer->GetVortexRotationSpeed()));
					TrySetAttr(gp, "vortex_radius_top", PyFloat_FromDouble(buffer->GetVortexRadiusTop()));
					TrySetAttr(gp, "vortex_height", PyFloat_FromDouble(buffer->GetVortexHeight()));

					applied = true;
					Py_DECREF(gp);
				}
			}
			Py_XDECREF(obj);
			Py_DECREF(objects);
		}
		Py_DECREF(data);
	}
	Py_DECREF(bpyModule);
	return applied;
}

#endif  // WITH_PYTHON

static void AddVec3(cJSON *entry, const char *key, const float *v)
{
	cJSON *arr = cJSON_CreateArray();
	cJSON_AddItemToArray(arr, cJSON_CreateNumber(v[0]));
	cJSON_AddItemToArray(arr, cJSON_CreateNumber(v[1]));
	cJSON_AddItemToArray(arr, cJSON_CreateNumber(v[2]));
	cJSON_AddItemToObject(entry, key, arr);
}

static void AddVec4(cJSON *entry, const char *key, const float *v)
{
	cJSON *arr = cJSON_CreateArray();
	cJSON_AddItemToArray(arr, cJSON_CreateNumber(v[0]));
	cJSON_AddItemToArray(arr, cJSON_CreateNumber(v[1]));
	cJSON_AddItemToArray(arr, cJSON_CreateNumber(v[2]));
	cJSON_AddItemToArray(arr, cJSON_CreateNumber(v[3]));
	cJSON_AddItemToObject(entry, key, arr);
}

/// Same sidecar contract as properties_particle.py's _gpu_debug_sidecar_path()/
/// _apply_gpu_debug_values(): one JSON next to the .blend, keyed by object name.
static void WriteJsonSidecar(const std::string &objectName, RAS_ParticleBuffer *buffer)
{
	char expanded[FILE_MAX];
	BLI_strncpy(expanded, "//gpu_particles_debug.json", FILE_MAX);
	BLI_path_abs(expanded, KX_GetMainPath().c_str());

	cJSON *root = nullptr;
	std::ifstream inFile(expanded);
	if (inFile.is_open()) {
		std::stringstream buf;
		buf << inFile.rdbuf();
		root = cJSON_Parse(buf.str().c_str());
	}
	if (!root) {
		root = cJSON_CreateObject();
	}

	cJSON_DeleteItemFromObject(root, objectName.c_str());
	cJSON *entry = cJSON_CreateObject();

	AddVec3(entry, "gravity", buffer->GetGravity());
	cJSON_AddNumberToObject(entry, "lifetime", buffer->GetLifetime());
	cJSON_AddNumberToObject(entry, "emitter_radius", buffer->GetEmitterRadius());
	AddVec3(entry, "velocity", buffer->GetVelocityBase());
	cJSON_AddNumberToObject(entry, "velocity_randomness", buffer->GetVelocityRandomness());
	cJSON_AddNumberToObject(entry, "size", buffer->GetBillboardSize());
	AddVec4(entry, "color", buffer->GetColor());
	AddVec4(entry, "end_color", buffer->GetEndColor());
	cJSON_AddNumberToObject(entry, "end_size", buffer->GetEndSize());
	cJSON_AddNumberToObject(entry, "particle_count", static_cast<double>(buffer->GetParticleCount()));
	AddVec3(entry, "emission_direction", buffer->GetEmissionDirection());
	cJSON_AddNumberToObject(entry, "emission_angle", buffer->GetEmissionAngle());
	cJSON_AddStringToObject(entry, "billboard_mode", BillboardModeIdentifier(buffer->GetBillboardMode()));
	cJSON_AddBoolToObject(entry, "use_backface_culling", buffer->GetBackfaceCulling());
	cJSON_AddStringToObject(entry, "collision_mode", CollisionModeIdentifier(buffer->GetCollisionMode()));
	cJSON_AddNumberToObject(entry, "collision_height", buffer->GetCollisionHeight());
	cJSON_AddNumberToObject(entry, "collision_bounce", buffer->GetCollisionBounce());
	cJSON_AddNumberToObject(entry, "collision_friction", buffer->GetCollisionFriction());
	cJSON_AddBoolToObject(entry, "use_vortex", buffer->GetUseVortex());
	cJSON_AddNumberToObject(entry, "vortex_rotation_speed", buffer->GetVortexRotationSpeed());
	cJSON_AddNumberToObject(entry, "vortex_radius_top", buffer->GetVortexRadiusTop());
	cJSON_AddNumberToObject(entry, "vortex_height", buffer->GetVortexHeight());

	cJSON_AddItemToObject(root, objectName.c_str(), entry);

	char *outStr = cJSON_Print(root);

	// Write to a temp file and rename onto the real path so a crash mid-write can't
	// leave a truncated/corrupt sidecar (same pattern as BLO_write_file/autosave).
	char tempname[FILE_MAX];
	BLI_snprintf(tempname, sizeof(tempname), "%s@", expanded);
	std::ofstream outFile(tempname);
	if (outFile.is_open()) {
		outFile << outStr;
		outFile.close();
		BLI_rename(tempname, expanded);
	}
	free(outStr);
	cJSON_Delete(root);
}

void ApplyToBlend(KX_GameObject *gameobj, RAS_ParticleBuffer *buffer)
{
#ifdef WITH_PYTHON
	if (ApplyToBpy(gameobj->GetName(), buffer)) {
		return;
	}
#endif
	WriteJsonSidecar(gameobj->GetName(), buffer);
}

}  // namespace KX_ParticleDebugUI
