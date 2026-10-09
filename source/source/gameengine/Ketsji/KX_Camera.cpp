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
 * Camera in the gameengine. Cameras are also used for views.
 */

/** \file gameengine/Ketsji/KX_Camera.cpp
 *  \ingroup ketsji
 */


#include "KX_Camera.h"
#include "KX_Scene.h"
#include "KX_Globals.h"
#include "KX_PyMath.h"
#include "KX_PythonMotion.h"
#include "KX_RayCast.h"

#include "RAS_ICanvas.h"

#include "DNA_camera_types.h"
#include "DNA_scene_types.h"

#include <cfloat>
#include <cmath>
#include <algorithm>

#include "GPU_glew.h"

#include <BLI_math_rotation.h>

KX_Camera::View::View()
	:projectionDirty(true),
	frustumDirty(true)
{
}

KX_Camera::KX_Camera(void *sgReplicationInfo,
                     SG_Callbacks callbacks,
                     const RAS_CameraData& camdata,
                     bool frustum_culling)
	:
	KX_GameObject(sgReplicationInfo, callbacks),
	m_camdata(camdata),
	m_frustum_culling(frustum_culling),
	m_lodDistanceFactor(1.0f),
	m_activityCulling(false),
	m_showDebugCameraFrustum(false),
	m_csmCacheMaxStaleFrames(1)
{
}


KX_Camera::~KX_Camera()
{
}


EXP_Value *KX_Camera::GetReplica()
{
	KX_Camera *replica = new KX_Camera(*this);

	// this will copy properties and so on...
	replica->ProcessReplica();

	return replica;
}

void KX_Camera::ProcessReplica()
{
	KX_GameObject::ProcessReplica();
}

mt::mat3x4 KX_Camera::GetWorldToCamera() const
{
	return GetCameraToWorld().Inverse();
}



mt::mat3x4 KX_Camera::GetCameraToWorld() const
{
	return mt::mat3x4(GetRenderOrientation(), GetRenderPosition());
}

mt::mat3 KX_Camera::GetRenderOrientation() const
{
	if (!m_trackActive && m_shakeRoll == 0.0f && !m_headActive) {
		return NodeGetWorldOrientation();
	}
	mt::mat3 ori = NodeGetWorldOrientation();
	if (m_headActive) {
		ori = ori * m_headRotation;
	}
	if (m_trackActive) {
		ori = ori * m_trackRotation;
	}
	if (m_shakeRoll != 0.0f) {
		ori = ori * mt::mat3::RotationZ(m_shakeRoll);
	}
	return ori;
}

mt::vec3 KX_Camera::GetRenderPosition() const
{
	if (!m_trackActive) {
		return NodeGetWorldPosition();
	}
	return NodeGetWorldPosition() + m_trackOffset;
}

/**
 * Sets the projection matrix that is used by the rasterizer.
 */
void KX_Camera::SetProjectionMatrix(const mt::mat4 & mat, RAS_Rasterizer::StereoEye eye)
{
	View& view = m_views[eye];
	view.projection = mat;
	view.projectionDirty = false;
	// Ask to rebuild the frustum as the projection changed.
	view.frustumDirty = true;
}



/**
 * Sets the modelview matrix that is used by the rasterizer.
 */
void KX_Camera::SetModelviewMatrix(const mt::mat4 & mat, RAS_Rasterizer::StereoEye eye)
{
	View& view = m_views[eye];
	view.modelview = mat;
	view.frustumDirty = true;
}



/**
 * Gets the projection matrix that is used by the rasterizer.
 */
const mt::mat4& KX_Camera::GetProjectionMatrix(RAS_Rasterizer::StereoEye eye) const
{
	return m_views[eye].projection;
}

/**
 * Gets the modelview matrix that is used by the rasterizer.
 */
const mt::mat4& KX_Camera::GetModelviewMatrix(RAS_Rasterizer::StereoEye eye) const
{
	return m_views[eye].modelview;
}

bool KX_Camera::HasValidProjectionMatrix(RAS_Rasterizer::StereoEye eye) const
{
	return !m_views[eye].projectionDirty;
}

void KX_Camera::InvalidateProjectionMatrix()
{
	for (unsigned short i = 0; i < RAS_Rasterizer::RAS_STEREO_MAXEYE; ++i) {
		m_views[i].projectionDirty = true;
	}
	GetScene()->GetTextureRendererManager()->InvalidateRenderersProjectionMatrix();
}

void KX_Camera::SetShakeShift(float x, float y)
{
	if (x == m_shakeShiftX && y == m_shakeShiftY) {
		return;
	}
	m_shakeShiftX = x;
	m_shakeShiftY = y;
	InvalidateProjectionMatrix();
}

void KX_Camera::SetEarthquakeShift(float x, float y)
{
	m_quakeShiftX = x;
	m_quakeShiftY = y;
	if (m_trauma <= 0.0f) {
		SetShakeShift(x, y);
	}
	// Otherwise UpdateShake() sums both sources this frame.
}

KX_Camera::GameFX& KX_Camera::GetGameFX()
{
	return m_gameFX;
}

void KX_Camera::SetFocusObject(KX_GameObject *object)
{
	m_focusObject = object;
}

KX_GameObject *KX_Camera::GetFocusObject() const
{
	return m_focusObject;
}

void KX_Camera::UnlinkObject(KX_GameObject *object)
{
	if (m_focusObject == object) {
		m_focusObject = nullptr;
	}
	if (m_focusTarget == object) {
		m_focusTarget = nullptr;
	}
	if (m_focusPropTarget == object) {
		m_focusPropTarget = nullptr;
		// Look for another marked object right away.
		m_focusScanTime = -1.0;
	}
}

void KX_Camera::AddShake(float trauma, float duration)
{
	m_trauma = std::min(1.0f, std::max(0.0f, m_trauma + trauma));
	m_traumaRate = (duration > 0.0f) ? m_trauma / duration : 0.0f;
}

const mt::vec3& KX_Camera::GetFocusPosition() const
{
	return m_focusPosition;
}

float KX_Camera::GetFocusDistance() const
{
	return m_focusDistance;
}

const mt::vec2& KX_Camera::GetFocusScreenPosition() const
{
	return m_focusScreen;
}

bool KX_Camera::IsFocusValid() const
{
	return m_focusValid;
}

float KX_Camera::GetCameraSpeed() const
{
	return (m_speedOverride >= 0.0f) ? m_speedOverride : m_speed;
}

const mt::vec2& KX_Camera::GetCameraTurn() const
{
	return m_turn;
}

static bool camera_property_is_true(KX_GameObject *object, const std::string& prop)
{
	EXP_Value *value = object->GetProperty(prop);
	return value && value->GetNumber() != 0.0;
}

KX_GameObject *KX_Camera::FindPropertyFocus(bool rescan, double curtime)
{
	const std::string& prop = m_gameFX.focusProp;
	if (prop.empty()) {
		m_focusPropTarget = nullptr;
		return nullptr;
	}

	// The cached target stays while its property is still true; a full scene scan runs
	// only every half second (to pick up new objects) or when the target went away.
	const bool cachedValid = m_focusPropTarget && camera_property_is_true(m_focusPropTarget, prop);
	if (cachedValid && !rescan && m_focusPropScanned == prop && curtime - m_focusScanTime < 0.5) {
		return m_focusPropTarget;
	}
	if (!cachedValid || rescan || m_focusPropScanned != prop || curtime - m_focusScanTime >= 0.5) {
		m_focusScanTime = curtime;
		m_focusPropScanned = prop;
		const mt::vec3 campos = NodeGetWorldPosition();
		KX_GameObject *best = nullptr;
		float bestDist = FLT_MAX;
		for (KX_GameObject *object : *GetScene()->GetObjectList()) {
			if (object == this || !camera_property_is_true(object, prop)) {
				continue;
			}
			const float dist = (object->NodeGetWorldPosition() - campos).LengthSquared();
			if (dist < bestDist) {
				bestDist = dist;
				best = object;
			}
		}
		m_focusPropTarget = best;
	}
	return m_focusPropTarget;
}

void KX_Camera::UpdateFocus(float dt, double curtime)
{
	m_focusTarget = nullptr;
	m_focusValid = false;

	switch (m_gameFX.focusMode) {
		case CAM_FOCUS_OBJECT:
		{
			if (m_focusObject) {
				m_focusTarget = m_focusObject;
			}
			break;
		}
		case CAM_FOCUS_PROPERTY:
		{
			m_focusTarget = FindPropertyFocus(false, curtime);
			break;
		}
		case CAM_FOCUS_AUTO:
		{
			// Physics ray through the aim point: no depth buffer read, no GPU stall.
			const mt::mat3 ori = GetRenderOrientation();
			const mt::vec3 from = GetRenderPosition();
			float x = m_gameFX.focusScreen[0] * 2.0f - 1.0f;
			float y = (1.0f - m_gameFX.focusScreen[1]) * 2.0f - 1.0f;
			mt::vec3 dir;
			if (m_camdata.m_perspective) {
				const float tanX = 0.5f * m_camdata.m_sensor_x / std::max(m_camdata.m_lens, 0.001f);
				RAS_ICanvas *canvas = KX_GetActiveEngine()->GetCanvas();
				const float aspect = (canvas && canvas->GetHeight() > 0) ?
				                     (float)canvas->GetWidth() / (float)canvas->GetHeight() : 16.0f / 9.0f;
				dir = ori * mt::vec3(x * tanX, y * tanX / aspect, -1.0f);
			}
			else {
				dir = ori * mt::vec3(0.0f, 0.0f, -1.0f);
			}
			const mt::vec3 to = from + dir.SafeNormalized(mt::axisX3) * m_camdata.m_clipend;

			PHY_IPhysicsEnvironment *pe = GetScene()->GetPhysicsEnvironment();
			PHY_IPhysicsController *spc = m_physicsController.get();
			KX_GameObject *parent = GetParent();
			if (!spc && parent) {
				spc = parent->GetPhysicsController();
			}
			RayCastData rayData("", false, (1u << OB_MAX_COL_MASKS) - 1);
			KX_RayCast::Callback<KX_Camera, RayCastData> callback(this, spc, &rayData);
			if (pe && KX_RayCast::RayTest(pe, from, to, callback) && callback.m_hitFound) {
				m_focusTarget = rayData.m_hitObject;
				m_focusPosition = callback.m_hitPoint;
				m_focusValid = true;
			}
			break;
		}
		default:
			break;
	}

	if (m_focusTarget && m_gameFX.focusMode != CAM_FOCUS_AUTO) {
		m_focusPosition = m_focusTarget->NodeGetWorldPosition();
		m_focusValid = true;
	}
	(void)dt;
}

void KX_Camera::UpdateTracking(float dt)
{
	const short mode = m_gameFX.trackMode;
	const bool drone = (mode == CAM_TRACK_DRONE);
	// Only a real target (object or property) is followed; Auto/Manual focus would chase itself.
	const bool follow = (mode != CAM_TRACK_OFF) && m_focusValid && m_focusTarget &&
	                    m_gameFX.focusMode != CAM_FOCUS_AUTO;

	const float blend = (m_gameFX.trackSpeed > 0.0f) ? 1.0f - std::exp(-dt / m_gameFX.trackSpeed) : 1.0f;

	float targetYaw = 0.0f;
	float targetPitch = 0.0f;

	const mt::mat3 base = NodeGetWorldOrientation();
	const mt::vec3 basePos = NodeGetWorldPosition();

	// Drone hover (same shape as Rolima Racer's update_drone_movement), in world space.
	mt::vec3 hover = mt::zero3;
	if (drone) {
		m_droneTime += dt * m_gameFX.droneFrequency;
		hover = mt::vec3(0.0f,
		                 std::cos(m_droneTime * 1.5f) * 0.015f,
		                 std::sin(m_droneTime * 2.5f) * 0.03f) * m_gameFX.droneAmplitude;
	}

	if (follow) {
		const mt::vec3 local = base.Transpose() * (m_focusPosition - (basePos + hover));
		const float horiz = std::sqrt(local.x * local.x + local.z * local.z);
		if (horiz > 1e-5f || std::fabs(local.y) > 1e-5f) {
			targetYaw = std::atan2(local.x, -local.z);
			targetPitch = std::atan2(local.y, horiz);
		}
		else {
			targetYaw = m_trackYaw;
			targetPitch = m_trackPitch;
		}

		// Framing offset and dead zone are screen fractions, turned into angles with the FOV.
		const float fovX = 2.0f * std::atan(0.5f * m_camdata.m_sensor_x / std::max(m_camdata.m_lens, 0.001f));
		RAS_ICanvas *canvas = KX_GetActiveEngine()->GetCanvas();
		const float aspect = (canvas && canvas->GetHeight() > 0) ?
		                     (float)canvas->GetWidth() / (float)canvas->GetHeight() : 16.0f / 9.0f;
		const float fovY = fovX / aspect;
		targetYaw -= m_gameFX.trackScreenOffset[0] * fovX;
		targetPitch -= m_gameFX.trackScreenOffset[1] * fovY;

		const float dead = m_gameFX.trackDeadzone;
		if (dead > 0.0f) {
			const float dy = targetYaw - m_trackYaw;
			const float dp = targetPitch - m_trackPitch;
			const float zoneX = dead * fovX;
			const float zoneY = dead * fovY;
			// Only turn by what exceeds the dead zone, so the camera comes to rest at its edge.
			targetYaw = (std::fabs(dy) <= zoneX) ? m_trackYaw : targetYaw - std::copysign(zoneX, dy);
			targetPitch = (std::fabs(dp) <= zoneY) ? m_trackPitch : targetPitch - std::copysign(zoneY, dp);
		}

		const float limit = m_gameFX.trackLimit;
		if (limit > 0.0f) {
			const float mag = std::sqrt(targetYaw * targetYaw + targetPitch * targetPitch);
			if (mag > limit) {
				targetYaw *= limit / mag;
				targetPitch *= limit / mag;
			}
		}
	}

	// Smoothing on the angles also gives the drone's soft change of target for free.
	const float prevYaw = m_trackYaw;
	m_trackYaw += (targetYaw - m_trackYaw) * blend;
	m_trackPitch += (targetPitch - m_trackPitch) * blend;

	float targetRoll = 0.0f;
	if (drone && dt > 0.0f) {
		const float rate = (m_trackYaw - prevYaw) / dt;
		m_trackYawRate += (rate - m_trackYawRate) * std::min(1.0f, dt * 8.0f);
		targetRoll = std::max(-0.35f, std::min(0.35f, -m_trackYawRate * m_gameFX.trackBank * 0.25f));
	}
	else {
		m_trackYawRate = 0.0f;
	}
	m_trackRoll += (targetRoll - m_trackRoll) * blend;

	const bool nearZero = std::fabs(m_trackYaw) < 1e-5f && std::fabs(m_trackPitch) < 1e-5f &&
	                      std::fabs(m_trackRoll) < 1e-5f && !drone;
	if (mode == CAM_TRACK_OFF && nearZero) {
		m_trackActive = false;
		m_trackRotation = mt::mat3::Identity();
		m_trackOffset = mt::zero3;
		return;
	}

	mt::mat3 rot = mt::mat3::RotationY(-m_trackYaw) * mt::mat3::RotationX(m_trackPitch);
	if (m_gameFX.flag & CAM_GFX_TRACK_UPLOCK) {
		// Keep the horizon: rebuild the frame around the world up axis.
		const mt::vec3 forward = base * rot * mt::vec3(0.0f, 0.0f, -1.0f);
		const mt::vec3 zAxis = -forward;
		mt::vec3 xAxis = mt::vec3::CrossProduct(mt::axisZ3, zAxis);
		if (xAxis.LengthSquared() > 1e-6f) {
			xAxis.Normalize();
			const mt::vec3 yAxis = mt::vec3::CrossProduct(zAxis, xAxis);
			rot = base.Transpose() * mt::mat3(xAxis, yAxis, zAxis);
		}
	}
	if (m_trackRoll != 0.0f) {
		rot = rot * mt::mat3::RotationZ(m_trackRoll);
	}

	m_trackRotation = rot;
	m_trackOffset = hover;
	m_trackActive = true;
}

void KX_Camera::UpdateShake(float dt)
{
	float x = m_quakeShiftX;
	float y = m_quakeShiftY;
	float roll = 0.0f;

	if (m_trauma > 0.0f) {
		const float rate = (m_traumaRate > 0.0f) ? m_traumaRate : m_gameFX.shakeDecay;
		m_trauma = std::max(0.0f, m_trauma - rate * dt);
		m_traumaTime += dt * m_gameFX.shakeFrequency;
		const float t = m_traumaTime;
		const float amount = m_trauma * m_trauma * m_gameFX.shakeAmplitude;
		// Summed sines at unrelated rates read as noise without a noise table.
		x += amount * (std::sin(t * 1.00f) + 0.5f * std::sin(t * 2.31f + 1.3f)) / 1.5f;
		y += amount * (std::sin(t * 1.17f + 0.7f) + 0.5f * std::sin(t * 2.73f + 2.1f)) / 1.5f;
		if (m_gameFX.flag & CAM_GFX_SHAKE_ROLL) {
			roll = amount * 2.0f * std::sin(t * 0.83f + 0.4f);
		}
		if (m_trauma <= 0.0f) {
			m_traumaRate = 0.0f;
		}
	}

	m_shakeRoll = roll;
	SetShakeShift(x, y);
}

void KX_Camera::UpdateMotion(float dt)
{
	const mt::mat3 ori = GetRenderOrientation();
	const mt::vec3 pos = GetRenderPosition();
	const mt::vec3 forward = ori * mt::vec3(0.0f, 0.0f, -1.0f);

	if (!m_motionInitialized || dt <= 0.0f) {
		m_prevRenderPos = pos;
		m_prevRenderForward = forward;
		m_motionInitialized = true;
		return;
	}

	const float speed = (pos - m_prevRenderPos).Length() / dt;
	const float k = std::min(1.0f, dt * 10.0f);
	m_speed += (speed - m_speed) * k;

	// Turn of this frame as a screen fraction (what Directional Blur smears over).
	const mt::vec3 delta = forward - m_prevRenderForward;
	const float tanX = 0.5f * m_camdata.m_sensor_x / std::max(m_camdata.m_lens, 0.001f);
	const mt::vec2 turn(mt::vec3::DotProduct(delta, ori.GetColumn(0)) / (2.0f * tanX),
	                    mt::vec3::DotProduct(delta, ori.GetColumn(1)) / (2.0f * tanX));
	m_turn += (turn - m_turn) * k;

	m_prevRenderPos = pos;
	m_prevRenderForward = forward;
}

void KX_Camera::UpdateHeadTracking(float dt)
{
	m_headActive = false;
	KX_Scene *scene = GetScene();
	if (!scene || !scene->GetBlenderScene() || !(scene->GetBlenderScene()->gm.flag & GAME_VR_HEAD_TRACKING)) {
		return;
	}
	KX_PythonMotion *motion = KX_PythonMotion::GetInstance();
	mt::mat3 head;
	if (motion && motion->GetHeadView(head, dt)) {
		// The object keeps the body direction: its level orientation (looking along +y, z up) is
		// Rx(90) from the camera's own axes, so the head turns the view from there.
		m_headRotation = mt::mat3::RotationX(-(float)M_PI_2) * head;
		m_headActive = true;
	}
}

void KX_Camera::UpdateVRComfort(float dt)
{
	KX_Scene *scene = GetScene();
	const float strength = (m_headActive && scene && scene->GetBlenderScene()) ?
	                       scene->GetBlenderScene()->gm.vr_vignette / 100.0f : 0.0f;
	if (strength <= 0.0f) {
		m_vrVignette = 0.0f;
		m_comfortInitialized = false;
		return;
	}

	// Body motion only (the object, without the head): turning the head never darkens the view.
	const mt::vec3 pos = NodeGetWorldPosition();
	const mt::vec3 forward = NodeGetWorldOrientation() * mt::vec3(0.0f, 0.0f, -1.0f);
	float target = 0.0f;
	if (m_comfortInitialized && dt > 0.0f) {
		const float dot = std::min(1.0f, std::max(-1.0f, mt::vec3::DotProduct(forward, m_comfortPrevForward)));
		const float turnSpeed = std::acos(dot) / dt;           // rad/s
		const float moveSpeed = (pos - m_comfortPrevPos).Length() / dt; // m/s
		// Full vignette from 90 deg/s of turn or 4 m/s of movement.
		target = std::min(1.0f, std::max(turnSpeed / (float)M_PI_2, moveSpeed / 4.0f));
	}
	m_comfortPrevPos = pos;
	m_comfortPrevForward = forward;
	m_comfortInitialized = true;

	// Closes fast and opens slowly, so a snap turn shows as a short dimming instead of a flash.
	const float current = m_vrVignette / strength;
	const float tau = (target > current) ? 0.08f : 0.35f;
	const float k = 1.0f - std::exp(-dt / tau);
	m_vrVignette = (current + (target - current) * k) * strength;
}

void KX_Camera::UpdateGameFX(double curtime)
{
	float dt = (m_fxLastTime < 0.0) ? 0.0f : (float)(curtime - m_fxLastTime);
	m_fxLastTime = curtime;
	dt = std::max(0.0f, std::min(dt, 0.25f));

	UpdateHeadTracking(dt);
	UpdateVRComfort(dt);

	UpdateFocus(dt, curtime);
	UpdateTracking(dt);

	// Distance along the rendered view axis (what the DOF compares against linear depth).
	const mt::mat3 ori = GetRenderOrientation();
	const mt::vec3 pos = GetRenderPosition();
	const mt::vec3 forward = ori * mt::vec3(0.0f, 0.0f, -1.0f);
	float target;
	if (m_focusValid) {
		target = mt::vec3::DotProduct(m_focusPosition - pos, forward);
	}
	else if (m_gameFX.focusMode == CAM_FOCUS_AUTO && m_focusInitialized) {
		target = m_focusDistance;
	}
	else {
		target = m_gameFX.focusDistance;
	}
	target = std::max(target, m_camdata.m_clipstart);

	if (!m_focusInitialized || m_gameFX.focusSmooth <= 0.0f) {
		m_focusDistance = target;
		m_focusInitialized = true;
	}
	else {
		m_focusDistance += (target - m_focusDistance) * (1.0f - std::exp(-dt / m_gameFX.focusSmooth));
	}
	if (!m_focusValid) {
		m_focusPosition = pos + forward * m_focusDistance;
	}

	// Screen position (0..1, top-down like getScreenPosition).
	const mt::vec3 view = ori.Transpose() * (m_focusPosition - pos);
	if (view.z < -1e-4f) {
		const mt::mat4& proj = GetProjectionMatrix(RAS_Rasterizer::RAS_STEREO_LEFTEYE);
		const mt::vec4 clip = proj * mt::vec4(view.x, view.y, view.z, 1.0f);
		if (clip.w != 0.0f) {
			m_focusScreen = mt::vec2(clip.x / clip.w * 0.5f + 0.5f, 1.0f - (clip.y / clip.w * 0.5f + 0.5f));
		}
	}
	else {
		m_focusScreen = mt::vec2(0.5f, 0.5f);
	}

	UpdateShake(dt);
	UpdateMotion(dt);
}

void KX_Camera::UpdateView(RAS_Rasterizer* rasty, KX_Scene* scene, RAS_Rasterizer::StereoMode stereoMode,
		RAS_Rasterizer::StereoEye eye, const RAS_Rect& viewport, const RAS_Rect& area)
{
	View& view = m_views[eye];

	// Update modelview everytime, the frustum is rebuilt only when it changed.
	const mt::mat4 modelview = rasty->GetViewMatrix(stereoMode, eye, GetWorldToCamera(), m_camdata.m_perspective);
	bool changed = false;
	for (int col = 0; col < 4 && !changed; ++col) {
		for (int row = 0; row < 4; ++row) {
			if (modelview(row, col) != view.modelview(row, col)) {
				changed = true;
				break;
			}
		}
	}
	view.modelview = modelview;

	// Update projection when setting changed.
	if (view.projectionDirty) {
		RAS_FrameFrustum frustum{};

		if (m_camdata.m_perspective) {
			RAS_FramingManager::ComputeFrustum(
				scene->GetFramingType(),
				area,
				viewport,
				m_camdata.m_lens,
				m_camdata.m_sensor_x,
				m_camdata.m_sensor_y,
				m_camdata.m_sensor_fit,
				m_camdata.m_shift_x + m_shakeShiftX,
				m_camdata.m_shift_y + m_shakeShiftY,
				m_camdata.m_clipstart,
				m_camdata.m_clipend,
				frustum);

			if (!m_camdata.m_useViewport) {
				frustum.x1 *= m_camdata.m_zoom;
				frustum.x2 *= m_camdata.m_zoom;
				frustum.y1 *= m_camdata.m_zoom;
				frustum.y2 *= m_camdata.m_zoom;
			}
			view.projection = rasty->GetFrustumMatrix(stereoMode, eye, m_camdata.m_focallength,
				frustum.x1, frustum.x2, frustum.y1, frustum.y2, frustum.camnear, frustum.camfar);
		}
		else {
			RAS_FramingManager::ComputeOrtho(
				scene->GetFramingType(),
				area,
				viewport,
				m_camdata.m_scale,
				m_camdata.m_clipstart,
				m_camdata.m_clipend,
				m_camdata.m_sensor_fit,
				m_camdata.m_shift_x + m_shakeShiftX,
				m_camdata.m_shift_y + m_shakeShiftY,
				frustum);

			if (!m_camdata.m_useViewport) {
				frustum.x1 *= m_camdata.m_zoom;
				frustum.x2 *= m_camdata.m_zoom;
				frustum.y1 *= m_camdata.m_zoom;
				frustum.y2 *= m_camdata.m_zoom;
			}
			view.projection = rasty->GetOrthoMatrix(
				frustum.x1, frustum.x2, frustum.y1, frustum.y2, frustum.camnear, frustum.camfar);

		}

		view.projectionDirty = false;
		changed = true;
	}
	// Ask to rebuild the frustum only when the projection and/or modelview changed.
	if (changed) {
		view.frustumDirty = true;
	}
}

/**
 * These getters retrieve the clip data and the focal length
 */
float KX_Camera::GetLens() const
{
	return m_camdata.m_lens;
}

/* These set the clip data and the focal length */
void KX_Camera::SetLens(float lens)
{
	m_camdata.m_lens = lens;
	this->InvalidateProjectionMatrix();
}

float KX_Camera::GetScale() const
{
	return m_camdata.m_scale;
}

/**
 * Gets the horizontal size of the sensor - for camera matching.
 */
float KX_Camera::GetSensorWidth() const
{
	return m_camdata.m_sensor_x;
}

/**
 * Gets the vertical size of the sensor - for camera matching.
 */
float KX_Camera::GetSensorHeight() const
{
	return m_camdata.m_sensor_y;
}
/** Gets the mode FOV is calculating from sensor dimensions */
short KX_Camera::GetSensorFit() const
{
	return m_camdata.m_sensor_fit;
}

/**
 * Gets the horizontal shift of the sensor - for camera matching.
 */
float KX_Camera::GetShiftHorizontal() const
{
	return m_camdata.m_shift_x;
}

/**
 * Gets the vertical shift of the sensor - for camera matching.
 */
float KX_Camera::GetShiftVertical() const
{
	return m_camdata.m_shift_y;
}

float KX_Camera::GetCameraNear() const
{
	return m_camdata.m_clipstart;
}



float KX_Camera::GetCameraFar() const
{
	return m_camdata.m_clipend;
}

float KX_Camera::GetFocalLength() const
{
	return m_camdata.m_focallength;
}

float KX_Camera::GetZoom() const
{
	return m_camdata.m_zoom;
}

RAS_CameraData *KX_Camera::GetCameraData()
{
	return &m_camdata;
}

void KX_Camera::SetShowCameraFrustum(bool show)
{
	m_showDebugCameraFrustum = show;
}

bool KX_Camera::GetShowCameraFrustum() const
{
	return m_showDebugCameraFrustum;
}

float KX_Camera::GetLodDistanceFactor() const
{
	return m_lodDistanceFactor;
}

void KX_Camera::SetLodDistanceFactor(float lodfactor)
{
	m_lodDistanceFactor = lodfactor;
}

short KX_Camera::GetCSMCacheMaxStaleFrames() const
{
	return m_csmCacheMaxStaleFrames;
}

void KX_Camera::SetCSMCacheMaxStaleFrames(short maxStaleFrames)
{
	m_csmCacheMaxStaleFrames = maxStaleFrames;
}

bool KX_Camera::GetActivityCulling() const
{
	return m_activityCulling;
}

void KX_Camera::SetActivityCulling(bool enable)
{
	m_activityCulling = enable;
}

void KX_Camera::ExtractFrustum(RAS_Rasterizer::StereoEye eye)
{
	View& view = m_views[eye];
	if (view.frustumDirty) {
		view.frustum = SG_Frustum(view.projection * view.modelview);
		view.frustumDirty = false;
	}
}

const SG_Frustum& KX_Camera::GetFrustum(RAS_Rasterizer::StereoEye eye)
{
	ExtractFrustum(eye);
	return m_views[eye].frustum;
}

bool KX_Camera::GetFrustumCulling() const
{
	return m_frustum_culling;
}

void KX_Camera::EnableViewport(bool viewport)
{
	InvalidateProjectionMatrix(); // We need to reset projection matrix
	m_camdata.m_useViewport = viewport;
}

void KX_Camera::SetViewport(int left, int bottom, int right, int top)
{
	InvalidateProjectionMatrix();
	m_camdata.m_viewport = RAS_Rect(left, right, bottom, top);
	// Explicit pixels from Python replace the ratios set in the editor.
	m_camdata.m_useViewportRatios = false;
}

void KX_Camera::SetViewportRatios(float left, float bottom, float right, float top)
{
	InvalidateProjectionMatrix();
	m_camdata.m_useViewportRatios = true;
	m_camdata.m_viewportRatios[0] = left;
	m_camdata.m_viewportRatios[1] = bottom;
	m_camdata.m_viewportRatios[2] = right;
	m_camdata.m_viewportRatios[3] = top;
}

const RAS_Rect& KX_Camera::UpdateViewport(const RAS_Rect& displayArea)
{
	if (m_camdata.m_useViewportRatios) {
		/* Resolved against the render area of this frame so the viewport follows window resizes,
		 * the dynamic render scale and the per-eye area of stereo modes. */
		const float *ratios = m_camdata.m_viewportRatios;
		const int maxx = displayArea.GetMaxX();
		const int maxy = displayArea.GetMaxY();
		const RAS_Rect viewport(displayArea.GetLeft() + (int)(maxx * ratios[0]), displayArea.GetLeft() + (int)(maxx * ratios[2]),
		                        displayArea.GetBottom() + (int)(maxy * ratios[1]), displayArea.GetBottom() + (int)(maxy * ratios[3]));
		const RAS_Rect& current = m_camdata.m_viewport;
		if (viewport.GetLeft() != current.GetLeft() || viewport.GetRight() != current.GetRight() ||
		    viewport.GetBottom() != current.GetBottom() || viewport.GetTop() != current.GetTop())
		{
			m_camdata.m_viewport = viewport;
			InvalidateProjectionMatrix();
		}
	}

	return m_camdata.m_viewport;
}

bool KX_Camera::UseViewport() const
{
	return m_camdata.m_useViewport;
}

const RAS_Rect& KX_Camera::GetViewport() const
{
	return m_camdata.m_viewport;
}

mathfu::vec3 KX_Camera::GetObjectProjectedOnScreenSpace(mathfu::vec3 gameObjWorldSpace) {

	const GLint *viewport;
	GLdouble win[3];
	GLdouble dmodelmatrix[16];
	GLdouble dprojmatrix[16];

	// Get the camera's model and projection matrices
	const mt::mat4 modelmatrix = mt::mat4::FromAffineTransform(GetWorldToCamera());
	const mt::mat4& projmatrix = this->GetProjectionMatrix(RAS_Rasterizer::RAS_STEREO_LEFTEYE);

	// Convert the matrices to double precision arrays
	for (unsigned short i = 0; i < 16; ++i) {
		dmodelmatrix[i] = modelmatrix[i];
		dprojmatrix[i] = projmatrix[i];
	}
	
	// Get the viewport
	viewport = KX_GetActiveEngine()->GetCanvas()->GetViewPort();

	gluProject(gameObjWorldSpace[0], gameObjWorldSpace[1], gameObjWorldSpace[2], dmodelmatrix, dprojmatrix, viewport, &win[0], &win[1], &win[2]);

	// Check if the object is behind the camera
	if (win[2] > 1.0) {
		return mathfu::vec3(INFINITY, INFINITY, 0);
	}

	gameObjWorldSpace[0] =  (win[0] - viewport[0]) / viewport[2];
	gameObjWorldSpace[1] =  (win[1] - viewport[1]) / viewport[3];

	gameObjWorldSpace[1] = 1.0f - gameObjWorldSpace[1]; //to follow Blender window coordinate system (Top-Down)

	return gameObjWorldSpace;
}

KX_GameObject::RayCastData KX_Camera::GetScreenRayCast(float x, float y, float dist, char *propName) {
	y = 1.0 - y; //to follow Blender window coordinate system (Top-Down)

	const mt::mat4 modelmatrix = mt::mat4::FromAffineTransform(this->GetWorldToCamera());

	RAS_ICanvas *canvas = KX_GetActiveEngine()->GetCanvas();
	const int width = canvas->GetWidth();
	const int height = canvas->GetHeight();

	mt::vec3 fromPoint;
	mt::vec3 toPoint;

	// Unproject a point in near plane.
	const mt::vec3 point(x * width, y * height, 0.0f);
	const mt::vec3 screenpos = mt::mat4::UnProject(point, modelmatrix, this->GetProjectionMatrix(RAS_Rasterizer::RAS_STEREO_LEFTEYE), width, height);

	// For perpspective the vector is from camera center to unprojected point.
	if (m_camdata.m_perspective) {
		fromPoint = this->NodeGetWorldPosition();
		toPoint = screenpos;
	}
	// For orthographic the vector is the same as the -Z rotation axis but start from unprojected point.
	else {
		fromPoint = screenpos;
		toPoint = fromPoint - this->NodeGetWorldOrientation().GetColumn(2);
	}

	if (dist != 0.0f) {
		toPoint = fromPoint + dist * (toPoint - fromPoint).SafeNormalized(mt::axisX3);
	}

	PHY_IPhysicsEnvironment *pe = this->GetScene()->GetPhysicsEnvironment();
	PHY_IPhysicsController *spc = m_physicsController.get();
	KX_GameObject *parent = this->GetParent();
	if (!spc && parent) {
		spc = parent->GetPhysicsController();
	}

	// RayCastData rayData("", false, (1u << OB_MAX_COL_MASKS) - 1);
	std::string prop = propName ? (std::string)propName : "";
	RayCastData rayData(prop, false, (1u << OB_MAX_COL_MASKS) - 1);

	KX_RayCast::Callback<KX_Camera, RayCastData> callback(this, spc, &rayData);

	KX_RayCast::RayTest(pe, fromPoint, toPoint, callback);

	return rayData;
}

#ifdef WITH_PYTHON
//----------------------------------------------------------------------------
//Python


PyMethodDef KX_Camera::Methods[] = {
	EXP_PYMETHODTABLE_VARARGS(KX_Camera, sphereInsideFrustum),
	EXP_PYMETHODTABLE_O(KX_Camera, boxInsideFrustum),
	EXP_PYMETHODTABLE_O(KX_Camera, pointInsideFrustum),
	EXP_PYMETHODTABLE_NOARGS(KX_Camera, getCameraToWorld),
	EXP_PYMETHODTABLE_NOARGS(KX_Camera, getWorldToCamera),
	EXP_PYMETHODTABLE_VARARGS(KX_Camera, setViewport),
	EXP_PYMETHODTABLE_NOARGS(KX_Camera, setOnTop),
	EXP_PYMETHODTABLE_O(KX_Camera, getScreenPosition),
	EXP_PYMETHODTABLE_VARARGS(KX_Camera, getScreenVect),
	EXP_PYMETHODTABLE_VARARGS(KX_Camera, getScreenRay),
	EXP_PYMETHODTABLE_VARARGS(KX_Camera, shake),
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_Camera::Attributes[] = {

	EXP_PYATTRIBUTE_BOOL_RW("frustum_culling", KX_Camera, m_frustum_culling),
	EXP_PYATTRIBUTE_BOOL_RW("activityCulling", KX_Camera, m_activityCulling),
	EXP_PYATTRIBUTE_RW_FUNCTION("perspective", KX_Camera, pyattr_get_perspective, pyattr_set_perspective),

	EXP_PYATTRIBUTE_RW_FUNCTION("lens", KX_Camera,  pyattr_get_lens, pyattr_set_lens),
	EXP_PYATTRIBUTE_RW_FUNCTION("fov",  KX_Camera,  pyattr_get_fov,  pyattr_set_fov),
	EXP_PYATTRIBUTE_RW_FUNCTION("ortho_scale",  KX_Camera,  pyattr_get_ortho_scale, pyattr_set_ortho_scale),
	EXP_PYATTRIBUTE_RW_FUNCTION("near", KX_Camera,  pyattr_get_near, pyattr_set_near),
	EXP_PYATTRIBUTE_RW_FUNCTION("far",  KX_Camera,  pyattr_get_far,  pyattr_set_far),
	EXP_PYATTRIBUTE_RW_FUNCTION("shift_x",  KX_Camera,  pyattr_get_shift_x, pyattr_set_shift_x),
	EXP_PYATTRIBUTE_RW_FUNCTION("shift_y",  KX_Camera,  pyattr_get_shift_y,  pyattr_set_shift_y),
	EXP_PYATTRIBUTE_FLOAT_RW("lodDistanceFactor", 0.0f, FLT_MAX, KX_Camera, m_lodDistanceFactor),

	EXP_PYATTRIBUTE_RW_FUNCTION("useViewport",  KX_Camera,  pyattr_get_use_viewport,  pyattr_set_use_viewport),

	EXP_PYATTRIBUTE_RW_FUNCTION("projection_matrix", KX_Camera, pyattr_get_projectionMatrixLeft, pyattr_set_projectionMatrixLeft),
	EXP_PYATTRIBUTE_RW_FUNCTION("projectionMatrixLeft", KX_Camera, pyattr_get_projectionMatrixLeft, pyattr_set_projectionMatrixLeft),
	EXP_PYATTRIBUTE_RW_FUNCTION("projectionMatrixRight", KX_Camera, pyattr_get_projectionMatrixRight, pyattr_set_projectionMatrixRight),
	EXP_PYATTRIBUTE_RO_FUNCTION("modelview_matrix", KX_Camera,  pyattr_get_modelview_matrix),
	EXP_PYATTRIBUTE_RO_FUNCTION("camera_to_world",  KX_Camera,  pyattr_get_camera_to_world),
	EXP_PYATTRIBUTE_RO_FUNCTION("world_to_camera",  KX_Camera,  pyattr_get_world_to_camera),

	/* Grrr, functions for constants? */
	EXP_PYATTRIBUTE_SHORT_RW("focusMode", 0, 3, true, KX_Camera, m_gameFX.focusMode),
	EXP_PYATTRIBUTE_RW_FUNCTION("focusObject", KX_Camera, pyattr_get_focus_object, pyattr_set_focus_object),
	EXP_PYATTRIBUTE_STRING_RW("focusProperty", 0, 63, false, KX_Camera, m_gameFX.focusProp),
	EXP_PYATTRIBUTE_RO_FUNCTION("focusTarget", KX_Camera, pyattr_get_focus_target),
	EXP_PYATTRIBUTE_RO_FUNCTION("focusPosition", KX_Camera, pyattr_get_focus_position),
	EXP_PYATTRIBUTE_FLOAT_RO("focusDistance", KX_Camera, m_focusDistance),
	EXP_PYATTRIBUTE_RO_FUNCTION("focusScreenPosition", KX_Camera, pyattr_get_focus_screen_position),
	EXP_PYATTRIBUTE_BOOL_RO("focusValid", KX_Camera, m_focusValid),
	EXP_PYATTRIBUTE_FLOAT_RW("focusManualDistance", 0.0f, FLT_MAX, KX_Camera, m_gameFX.focusDistance),
	EXP_PYATTRIBUTE_FLOAT_RW("focusRange", 0.0f, FLT_MAX, KX_Camera, m_gameFX.focusRange),
	EXP_PYATTRIBUTE_FLOAT_RW("focusSmooth", 0.0f, 10.0f, KX_Camera, m_gameFX.focusSmooth),

	EXP_PYATTRIBUTE_SHORT_RW("trackMode", 0, 2, true, KX_Camera, m_gameFX.trackMode),
	EXP_PYATTRIBUTE_FLOAT_RW("trackSpeed", 0.0f, 10.0f, KX_Camera, m_gameFX.trackSpeed),
	EXP_PYATTRIBUTE_FLOAT_RW("trackLimit", 0.0f, 3.1416f, KX_Camera, m_gameFX.trackLimit),
	EXP_PYATTRIBUTE_FLOAT_RW("trackDeadzone", 0.0f, 0.5f, KX_Camera, m_gameFX.trackDeadzone),
	EXP_PYATTRIBUTE_FLOAT_ARRAY_RW("trackScreenOffset", -0.5f, 0.5f, KX_Camera, m_gameFX.trackScreenOffset, 2),
	EXP_PYATTRIBUTE_FLOAT_RW("droneAmplitude", 0.0f, 20.0f, KX_Camera, m_gameFX.droneAmplitude),
	EXP_PYATTRIBUTE_FLOAT_RW("droneFrequency", 0.0f, 20.0f, KX_Camera, m_gameFX.droneFrequency),
	EXP_PYATTRIBUTE_FLOAT_RW("trackBank", 0.0f, 5.0f, KX_Camera, m_gameFX.trackBank),
	EXP_PYATTRIBUTE_RO_FUNCTION("trackOrientation", KX_Camera, pyattr_get_track_orientation),
	EXP_PYATTRIBUTE_RO_FUNCTION("gazeDirection", KX_Camera, pyattr_get_gaze_direction),

	EXP_PYATTRIBUTE_FLAG_RW("useDof", KX_Camera, m_gameFX.flag, CAM_GFX_DOF),
	EXP_PYATTRIBUTE_FLAG_RW("useSpeedBlur", KX_Camera, m_gameFX.flag, CAM_GFX_SPEEDBLUR),
	EXP_PYATTRIBUTE_FLAG_RW("useDirectionalBlur", KX_Camera, m_gameFX.flag, CAM_GFX_DIRBLUR),
	EXP_PYATTRIBUTE_FLAG_RW("useBlurProtect", KX_Camera, m_gameFX.flag, CAM_GFX_BLUR_PROTECT),
	EXP_PYATTRIBUTE_FLAG_RW("useCatEye", KX_Camera, m_gameFX.flag, CAM_GFX_CATEYE_BOKEH),
	EXP_PYATTRIBUTE_FLAG_RW("useChromatic", KX_Camera, m_gameFX.flag, CAM_GFX_CHROMA),
	EXP_PYATTRIBUTE_FLAG_RW("useChromaticSpeed", KX_Camera, m_gameFX.flag, CAM_GFX_CHROMA_SPEED),
	EXP_PYATTRIBUTE_FLAG_RW("useVignette", KX_Camera, m_gameFX.flag, CAM_GFX_VIGNETTE),
	EXP_PYATTRIBUTE_FLAG_RW("useShakeRoll", KX_Camera, m_gameFX.flag, CAM_GFX_SHAKE_ROLL),
	EXP_PYATTRIBUTE_FLAG_RW("useTrackUpLock", KX_Camera, m_gameFX.flag, CAM_GFX_TRACK_UPLOCK),
	EXP_PYATTRIBUTE_SHORT_RW("dofQuality", 0, 2, true, KX_Camera, m_gameFX.dofQuality),
	EXP_PYATTRIBUTE_FLOAT_RW("dofBlur", 0.0f, 32.0f, KX_Camera, m_gameFX.dofBlur),
	EXP_PYATTRIBUTE_FLOAT_RW("speedBlurStrength", 0.0f, 2.0f, KX_Camera, m_gameFX.speedBlurStrength),
	EXP_PYATTRIBUTE_FLOAT_RW("speedBlurMaxSpeed", 0.1f, 1000.0f, KX_Camera, m_gameFX.speedBlurMaxSpeed),
	EXP_PYATTRIBUTE_FLOAT_RW("speedOverride", -1.0f, FLT_MAX, KX_Camera, m_speedOverride),
	EXP_PYATTRIBUTE_FLOAT_RO("cameraSpeed", KX_Camera, m_speed),
	EXP_PYATTRIBUTE_FLOAT_RW("directionalBlurStrength", 0.0f, 2.0f, KX_Camera, m_gameFX.dirBlurStrength),
	EXP_PYATTRIBUTE_FLOAT_RW("directionalBlurMax", 0.0f, 0.2f, KX_Camera, m_gameFX.dirBlurMax),
	EXP_PYATTRIBUTE_FLOAT_RW("catEyeStrength", 0.0f, 1.0f, KX_Camera, m_gameFX.catEyeStrength),
	EXP_PYATTRIBUTE_FLOAT_RW("chromaticStrength", 0.0f, 5.0f, KX_Camera, m_gameFX.chromaStrength),
	EXP_PYATTRIBUTE_FLOAT_RW("vignetteStrength", 0.0f, 1.0f, KX_Camera, m_gameFX.vignetteStrength),
	EXP_PYATTRIBUTE_FLOAT_RW("vignetteRadius", 0.0f, 2.0f, KX_Camera, m_gameFX.vignetteRadius),
	EXP_PYATTRIBUTE_FLOAT_RW("fisheyeStrength", -1.0f, 1.0f, KX_Camera, m_gameFX.fisheyeStrength),
	EXP_PYATTRIBUTE_FLOAT_RW("shakeAmplitude", 0.0f, 0.5f, KX_Camera, m_gameFX.shakeAmplitude),
	EXP_PYATTRIBUTE_FLOAT_RW("shakeFrequency", 0.0f, 60.0f, KX_Camera, m_gameFX.shakeFrequency),
	EXP_PYATTRIBUTE_FLOAT_RW("shakeDecay", 0.0f, 20.0f, KX_Camera, m_gameFX.shakeDecay),
	EXP_PYATTRIBUTE_FLOAT_RO("shakeTrauma", KX_Camera, m_trauma),

	EXP_PYATTRIBUTE_RO_FUNCTION("INSIDE",   KX_Camera, pyattr_get_INSIDE),
	EXP_PYATTRIBUTE_RO_FUNCTION("OUTSIDE",  KX_Camera, pyattr_get_OUTSIDE),
	EXP_PYATTRIBUTE_RO_FUNCTION("INTERSECT",    KX_Camera, pyattr_get_INTERSECT),

	EXP_PYATTRIBUTE_NULL    //Sentinel
};

PyTypeObject KX_Camera::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_Camera",
	sizeof(EXP_PyObjectPlus_Proxy),
	0,
	py_base_dealloc,
	0,
	0,
	0,
	0,
	py_base_repr,
	0,
	&KX_GameObject::Sequence,
	&KX_GameObject::Mapping,
	0, 0, 0,
	nullptr,
	nullptr,
	0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	0, 0, 0, 0, 0, 0, 0,
	Methods,
	0,
	0,
	&KX_GameObject::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

EXP_PYMETHODDEF_DOC_VARARGS(KX_Camera, sphereInsideFrustum,
                            "sphereInsideFrustum(center, radius) -> Integer\n"
                            "\treturns INSIDE, OUTSIDE or INTERSECT if the given sphere is\n"
                            "\tinside/outside/intersects this camera's viewing frustum.\n\n"
                            "\tcenter = the center of the sphere (in world coordinates.)\n"
                            "\tradius = the radius of the sphere\n\n"
                            "\tExample:\n"
                            "\timport bge.logic\n\n"
                            "\tco = bge.logic.getCurrentController()\n"
                            "\tcam = co.GetOwner()\n\n"
                            "\t# A sphere of radius 4.0 located at [x, y, z] = [1.0, 1.0, 1.0]\n"
                            "\tif (cam.sphereInsideFrustum([1.0, 1.0, 1.0], 4) != cam.OUTSIDE):\n"
                            "\t\t# Sphere is inside frustum !\n"
                            "\t\t# Do something useful !\n"
                            "\telse:\n"
                            "\t\t# Sphere is outside frustum\n"
                            )
{
	PyObject *pycenter;
	float radius;
	if (PyArg_ParseTuple(args, "Of:sphereInsideFrustum", &pycenter, &radius)) {
		mt::vec3 center;
		if (PyVecTo(pycenter, center)) {
			return PyLong_FromLong(GetFrustum(RAS_Rasterizer::RAS_STEREO_LEFTEYE).SphereInsideFrustum(center, radius)); /* new ref */
		}
	}

	PyErr_SetString(PyExc_TypeError, "camera.sphereInsideFrustum(center, radius): KX_Camera, expected arguments: (center, radius)");

	return nullptr;
}

EXP_PYMETHODDEF_DOC_O(KX_Camera, boxInsideFrustum,
                      "boxInsideFrustum(box) -> Integer\n"
                      "\treturns INSIDE, OUTSIDE or INTERSECT if the given box is\n"
                      "\tinside/outside/intersects this camera's viewing frustum.\n\n"
                      "\tbox = a list of the eight (8) corners of the box (in world coordinates.)\n\n"
                      "\tExample:\n"
                      "\timport bge.logic\n\n"
                      "\tco = bge.logic.getCurrentController()\n"
                      "\tcam = co.GetOwner()\n\n"
                      "\tbox = []\n"
                      "\tbox.append([-1.0, -1.0, -1.0])\n"
                      "\tbox.append([-1.0, -1.0,  1.0])\n"
                      "\tbox.append([-1.0,  1.0, -1.0])\n"
                      "\tbox.append([-1.0,  1.0,  1.0])\n"
                      "\tbox.append([ 1.0, -1.0, -1.0])\n"
                      "\tbox.append([ 1.0, -1.0,  1.0])\n"
                      "\tbox.append([ 1.0,  1.0, -1.0])\n"
                      "\tbox.append([ 1.0,  1.0,  1.0])\n\n"
                      "\tif (cam.boxInsideFrustum(box) != cam.OUTSIDE):\n"
                      "\t\t# Box is inside/intersects frustum !\n"
                      "\t\t# Do something useful !\n"
                      "\telse:\n"
                      "\t\t# Box is outside the frustum !\n"
                      )
{
	unsigned int num_points = PySequence_Size(value);
	if (num_points != 8) {
		PyErr_Format(PyExc_TypeError, "camera.boxInsideFrustum(box): KX_Camera, expected eight (8) points, got %d", num_points);
		return nullptr;
	}

	std::array<mt::vec3, 8> box;
	for (unsigned int p = 0; p < 8; p++)
	{
		PyObject *item = PySequence_GetItem(value, p); /* new ref */
		bool error = !PyVecTo(item, box[p]);
		Py_DECREF(item);
		if (error) {
			return nullptr;
		}
	}

	return PyLong_FromLong(GetFrustum(RAS_Rasterizer::RAS_STEREO_LEFTEYE).BoxInsideFrustum(box)); /* new ref */
}

EXP_PYMETHODDEF_DOC_O(KX_Camera, pointInsideFrustum,
                      "pointInsideFrustum(point) -> Bool\n"
                      "\treturns 1 if the given point is inside this camera's viewing frustum.\n\n"
                      "\tpoint = The point to test (in world coordinates.)\n\n"
                      "\tExample:\n"
                      "\timport bge.logic\n\n"
                      "\tco = bge.logic.getCurrentController()\n"
                      "\tcam = co.GetOwner()\n\n"
                      "\t# Test point [0.0, 0.0, 0.0]"
                      "\tif (cam.pointInsideFrustum([0.0, 0.0, 0.0])):\n"
                      "\t\t# Point is inside frustum !\n"
                      "\t\t# Do something useful !\n"
                      "\telse:\n"
                      "\t\t# Box is outside the frustum !\n"
                      )
{
	mt::vec3 point;
	if (PyVecTo(value, point)) {
		return PyLong_FromLong(GetFrustum(RAS_Rasterizer::RAS_STEREO_LEFTEYE).PointInsideFrustum(point)); /* new ref */
	}

	PyErr_SetString(PyExc_TypeError, "camera.pointInsideFrustum(point): KX_Camera, expected point argument.");
	return nullptr;
}

EXP_PYMETHODDEF_DOC_NOARGS(KX_Camera, getCameraToWorld,
                           "getCameraToWorld() -> Matrix4x4\n"
                           "\treturns the camera to world transformation matrix, as a list of four lists of four values.\n\n"
                           "\tie: [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]])\n"
                           )
{
	return PyObjectFrom(mt::mat4::FromAffineTransform(GetCameraToWorld())); /* new ref */
}

EXP_PYMETHODDEF_DOC_NOARGS(KX_Camera, getWorldToCamera,
                           "getWorldToCamera() -> Matrix4x4\n"
                           "\treturns the world to camera transformation matrix, as a list of four lists of four values.\n\n"
                           "\tie: [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]])\n"
                           )
{
	return PyObjectFrom(mt::mat4::FromAffineTransform(GetWorldToCamera())); /* new ref */
}

EXP_PYMETHODDEF_DOC_VARARGS(KX_Camera, setViewport,
                            "setViewport(left, bottom, right, top)\n"
                            "Sets this camera's viewport\n")
{
	int left, bottom, right, top;
	if (!PyArg_ParseTuple(args, "iiii:setViewport", &left, &bottom, &right, &top)) {
		return nullptr;
	}

	SetViewport(left, bottom, right, top);
	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC_VARARGS(KX_Camera, shake,
                            "shake(trauma, duration=0.0)\n"
                            "Adds camera shake (0..1), summed with the World earthquake.\n"
                            "With a duration the shake fades out over that time, else at shakeDecay per second.\n")
{
	float trauma, duration = 0.0f;
	if (!PyArg_ParseTuple(args, "f|f:shake", &trauma, &duration)) {
		return nullptr;
	}

	AddShake(trauma, duration);
	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC_NOARGS(KX_Camera, setOnTop,
                           "setOnTop()\n"
                           "Sets this camera's viewport on top\n")
{
	GetScene()->SetCameraOnTop(this);
	Py_RETURN_NONE;
}

PyObject *KX_Camera::pyattr_get_perspective(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyBool_FromLong(self->m_camdata.m_perspective);
}

int KX_Camera::pyattr_set_perspective(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	int param = PyObject_IsTrue(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "camera.perspective = bool: KX_Camera, expected True/False or 0/1");
		return PY_SET_ATTR_FAIL;
	}

	self->m_camdata.m_perspective = param;
	self->InvalidateProjectionMatrix();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_lens(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyFloat_FromDouble(self->m_camdata.m_lens);
}

int KX_Camera::pyattr_set_lens(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	float param = PyFloat_AsDouble(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "camera.lens = float: KX_Camera, expected a float greater than zero");
		return PY_SET_ATTR_FAIL;
	}

	if (self->m_camdata.m_lens == param) {
		return PY_SET_ATTR_SUCCESS;
	}
	self->m_camdata.m_lens = param;
	self->InvalidateProjectionMatrix();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_fov(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);

	float lens = self->m_camdata.m_lens;
	float width = self->m_camdata.m_sensor_x;
	float fov = 2.0f * atanf(0.5f * width / lens);

	return PyFloat_FromDouble(RAD2DEGF(fov));
}

int KX_Camera::pyattr_set_fov(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	float fov = PyFloat_AsDouble(value);
	if (fov <= 0.0f) {
		PyErr_SetString(PyExc_AttributeError, "camera.fov = float: KX_Camera, expected a float greater than zero");
		return PY_SET_ATTR_FAIL;
	}

	float width = self->m_camdata.m_sensor_x;
	float lens = width / (2.0f * tanf(0.5f * DEG2RADF(fov)));

	if (self->m_camdata.m_lens == lens) {
		return PY_SET_ATTR_SUCCESS;
	}
	self->m_camdata.m_lens = lens;
	self->InvalidateProjectionMatrix();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_ortho_scale(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyFloat_FromDouble(self->m_camdata.m_scale);
}

int KX_Camera::pyattr_set_ortho_scale(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	float param = PyFloat_AsDouble(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "camera.ortho_scale = float: KX_Camera, expected a float greater than zero");
		return PY_SET_ATTR_FAIL;
	}

	self->m_camdata.m_scale = param;
	self->InvalidateProjectionMatrix();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_near(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyFloat_FromDouble(self->m_camdata.m_clipstart);
}

int KX_Camera::pyattr_set_near(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	float param = PyFloat_AsDouble(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "camera.near = float: KX_Camera, expected a float greater than zero");
		return PY_SET_ATTR_FAIL;
	}

	self->m_camdata.m_clipstart = param;
	self->InvalidateProjectionMatrix();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_far(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyFloat_FromDouble(self->m_camdata.m_clipend);
}

int KX_Camera::pyattr_set_far(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	float param = PyFloat_AsDouble(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "camera.far = float: KX_Camera, expected a float greater than zero");
		return PY_SET_ATTR_FAIL;
	}

	self->m_camdata.m_clipend = param;
	self->InvalidateProjectionMatrix();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_shift_x(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyFloat_FromDouble(self->m_camdata.m_shift_x);
}

int KX_Camera::pyattr_set_shift_x(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	float param = PyFloat_AsDouble(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "camera.shift_x = float: KX_Camera, expected a float greater than zero");
		return PY_SET_ATTR_FAIL;
	}

	self->m_camdata.m_shift_x = param;
	self->InvalidateProjectionMatrix();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_shift_y(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyFloat_FromDouble(self->m_camdata.m_shift_y);
}

int KX_Camera::pyattr_set_shift_y(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	float param = PyFloat_AsDouble(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "camera.shift_y = float: KX_Camera, expected a float greater than zero");
		return PY_SET_ATTR_FAIL;
	}

	self->m_camdata.m_shift_y = param;
	self->InvalidateProjectionMatrix();
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_use_viewport(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyBool_FromLong(self->UseViewport());
}

int KX_Camera::pyattr_set_use_viewport(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	int param = PyObject_IsTrue(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "camera.useViewport = bool: KX_Camera, expected True or False");
		return PY_SET_ATTR_FAIL;
	}
	self->EnableViewport((bool)param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_projectionMatrixLeft(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyObjectFrom(self->GetProjectionMatrix(RAS_Rasterizer::RAS_STEREO_LEFTEYE));
}

int KX_Camera::pyattr_set_projectionMatrixLeft(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	mt::mat4 mat;
	if (!PyMatTo(value, mat)) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetProjectionMatrix(mat, RAS_Rasterizer::RAS_STEREO_LEFTEYE);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_projectionMatrixRight(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyObjectFrom(self->GetProjectionMatrix(RAS_Rasterizer::RAS_STEREO_RIGHTEYE));
}

int KX_Camera::pyattr_set_projectionMatrixRight(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	mt::mat4 mat;
	if (!PyMatTo(value, mat)) {
		return PY_SET_ATTR_FAIL;
	}

	self->SetProjectionMatrix(mat, RAS_Rasterizer::RAS_STEREO_RIGHTEYE);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_modelview_matrix(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyObjectFrom(mt::mat4::FromAffineTransform(self->GetWorldToCamera()));
}

PyObject *KX_Camera::pyattr_get_camera_to_world(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyObjectFrom(mt::mat4::FromAffineTransform(self->GetCameraToWorld()));
}

PyObject *KX_Camera::pyattr_get_world_to_camera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyObjectFrom(mt::mat4::FromAffineTransform(self->GetWorldToCamera()));
}


PyObject *KX_Camera::pyattr_get_focus_object(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	KX_GameObject *object = self->GetFocusObject();
	if (!object) {
		Py_RETURN_NONE;
	}
	return object->GetProxy();
}

int KX_Camera::pyattr_set_focus_object(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	KX_GameObject *object;
	if (!ConvertPythonToGameObject(self->GetScene()->GetLogicManager(), value, &object, true, "camera.focusObject = obj: KX_Camera")) {
		return PY_SET_ATTR_FAIL;
	}
	self->SetFocusObject(object);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_Camera::pyattr_get_focus_target(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	if (!self->m_focusTarget) {
		Py_RETURN_NONE;
	}
	return self->m_focusTarget->GetProxy();
}

PyObject *KX_Camera::pyattr_get_focus_position(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyObjectFrom(self->GetFocusPosition());
}

PyObject *KX_Camera::pyattr_get_focus_screen_position(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyObjectFrom(self->GetFocusScreenPosition());
}

PyObject *KX_Camera::pyattr_get_track_orientation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyObjectFrom(self->GetRenderOrientation());
}

PyObject *KX_Camera::pyattr_get_gaze_direction(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	/* World direction the player looks at, including the head tracking: use it with rayCast for gaze aiming. */
	KX_Camera *self = static_cast<KX_Camera *>(self_v);
	return PyObjectFrom(self->GetRenderOrientation() * mt::vec3(0.0f, 0.0f, -1.0f));
}

PyObject *KX_Camera::pyattr_get_INSIDE(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	return PyLong_FromLong(INSIDE);
}
PyObject *KX_Camera::pyattr_get_OUTSIDE(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	return PyLong_FromLong(OUTSIDE);
}
PyObject *KX_Camera::pyattr_get_INTERSECT(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	return PyLong_FromLong(INTERSECT);
}


bool ConvertPythonToCamera(KX_Scene *scene, PyObject *value, KX_Camera **object, bool py_none_ok, const char *error_prefix)
{
	if (value == nullptr) {
		PyErr_Format(PyExc_TypeError, "%s, python pointer nullptr, should never happen", error_prefix);
		*object = nullptr;
		return false;
	}

	if (value == Py_None) {
		*object = nullptr;

		if (py_none_ok) {
			return true;
		}
		else {
			PyErr_Format(PyExc_TypeError, "%s, expected KX_Camera or a KX_Camera name, None is invalid", error_prefix);
			return false;
		}
	}

	if (PyUnicode_Check(value)) {
		std::string value_str = _PyUnicode_AsString(value);
		*object = scene->GetCameraList()->FindValue(value_str);

		if (*object) {
			return true;
		}
		else {
			PyErr_Format(PyExc_ValueError,
			             "%s, requested name \"%s\" did not match any KX_Camera in this scene",
			             error_prefix, _PyUnicode_AsString(value));
			return false;
		}
	}

	if (PyObject_TypeCheck(value, &KX_Camera::Type)) {
		*object = static_cast<KX_Camera *>EXP_PROXY_REF(value);

		/* sets the error */
		if (*object == nullptr) {
			PyErr_Format(PyExc_SystemError, "%s, " EXP_PROXY_ERROR_MSG, error_prefix);
			return false;
		}

		return true;
	}

	*object = nullptr;

	if (py_none_ok) {
		PyErr_Format(PyExc_TypeError, "%s, expect a KX_Camera, a string or None", error_prefix);
	}
	else {
		PyErr_Format(PyExc_TypeError, "%s, expect a KX_Camera or a string", error_prefix);
	}

	return false;
}

EXP_PYMETHODDEF_DOC_O(KX_Camera, getScreenPosition,
                      "getScreenPosition()\n"
                      )

{
	mt::vec3 vect;
	KX_GameObject *obj = nullptr;

	if (!PyVecTo(value, vect)) {
		PyErr_Clear();

		if (ConvertPythonToGameObject(GetScene()->GetLogicManager(), value, &obj, false, "")) {
			PyErr_Clear();
			vect = mt::vec3(obj->NodeGetWorldPosition());
		}
		else {
			PyErr_SetString(PyExc_TypeError, "Error in getScreenPosition. Expected a Vector3 or a KX_GameObject or a string for a name of a KX_GameObject");
			return nullptr;
		}
	}

	vect = GetObjectProjectedOnScreenSpace(vect);

	PyObject *ret = PyTuple_New(2);
	if (ret) {
		PyTuple_SET_ITEM(ret, 0, PyFloat_FromDouble(vect[0]));
		PyTuple_SET_ITEM(ret, 1, PyFloat_FromDouble(vect[1]));
		return ret;
	}

	return nullptr;
}

EXP_PYMETHODDEF_DOC_VARARGS(KX_Camera, getScreenVect,
                            "getScreenVect()\n"
                            )
{
	float x, y;
	if (!PyArg_ParseTuple(args, "ff:getScreenVect", &x, &y)) {
		return nullptr;
	}

	y = 1.0 - y; //to follow Blender window coordinate system (Top-Down)

	const mt::mat4 modelmatrix = mt::mat4::FromAffineTransform(GetWorldToCamera());

	RAS_ICanvas *canvas = KX_GetActiveEngine()->GetCanvas();
	const int width = canvas->GetWidth();
	const int height = canvas->GetHeight();

	const mt::vec3 vect(x * width, y * height, 0.0f);
	const mt::vec3 screenpos = mt::mat4::UnProject(vect, modelmatrix, GetProjectionMatrix(RAS_Rasterizer::RAS_STEREO_LEFTEYE), width, height);
	const mt::vec3 ret = (NodeGetLocalPosition() - screenpos).Normalized();

	return PyObjectFrom(ret);
}

EXP_PYMETHODDEF_DOC_VARARGS(KX_Camera, getScreenRay,
                            "getScreenRay()\n"
                            )
{
	float x, y, dist;
	char *propName = nullptr;

	if (!PyArg_ParseTuple(args, "fff|s:getScreenRay", &x, &y, &dist, &propName)) {
		return nullptr;
	}

	RayCastData rayData = GetScreenRayCast(x, y, dist, propName);

	if (rayData.m_hitObject) {
		return rayData.m_hitObject->GetProxy();
	}

	Py_RETURN_NONE;
}
#endif
