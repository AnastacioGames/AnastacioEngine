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
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_DebugRenderer.cpp
 *  \ingroup ketsji
 */

#include <cmath>

#include "KX_DebugRenderer.h"
#include "KX_KetsjiEngine.h"
#include "KX_RenderPipeline.h"
#include "KX_Camera.h"
#include "KX_Scene.h"
#include "RAS_Rasterizer.h"

#include "PHY_IPhysicsEnvironment.h"
#include "PHY_IVehicle.h"

KX_DebugRenderer::KX_DebugRenderer(KX_KetsjiEngine *engine)
	:m_engine(engine)
{
}

void KX_DebugRenderer::DrawDebugCameraFrustum(KX_Scene *scene, const KX_CameraRenderData& cameraFrameData)
{
	RAS_DebugDraw& debugDraw = scene->GetDebugDraw();
	for (KX_Camera *cam : scene->GetCameraList()) {
		if (cam != cameraFrameData.m_renderCamera && (m_engine->GetShowCameraFrustum() == KX_DebugOption::FORCE || cam->GetShowCameraFrustum())) {

			cam->UpdateView(m_engine->GetRasterizer(), scene, cameraFrameData.m_stereoMode, cameraFrameData.m_eye,
					cameraFrameData.m_viewport, cameraFrameData.m_area);

			debugDraw.DrawCameraFrustum(
				cam->GetProjectionMatrix(cameraFrameData.m_eye) * cam->GetModelviewMatrix(cameraFrameData.m_eye));
		}
	}
}

void KX_DebugRenderer::DrawDebugVehicles(KX_Scene *scene)
{
	if (m_engine->GetShowVehicleDebug() == KX_DebugOption::DISABLE) {
		return;
	}

	PHY_IPhysicsEnvironment *physEnv = scene->GetPhysicsEnvironment();
	if (!physEnv) {
		return;
	}

	static const mt::vec4 contactColor(0.0f, 1.0f, 0.0f, 1.0f);
	static const mt::vec4 airborneColor(1.0f, 0.0f, 0.0f, 1.0f);
	static const mt::vec4 raycastColor(0.6f, 0.6f, 0.6f, 1.0f);
	static const mt::vec4 axleColor(0.2f, 0.4f, 1.0f, 1.0f);
	static const mt::vec4 normalColor(1.0f, 1.0f, 0.0f, 1.0f);

	RAS_DebugDraw& debugDraw = scene->GetDebugDraw();

	const int numVehicles = physEnv->GetNumVehicles();
	for (int v = 0; v < numVehicles; ++v) {
		PHY_IVehicle *vehicle = physEnv->GetVehicleFromIndex(v);
		if (!vehicle) {
			continue;
		}

		const int numWheels = vehicle->GetNumWheels();
		for (int w = 0; w < numWheels; ++w) {
			PHY_VehicleWheelConfig config;
			PHY_VehicleWheelState state;
			if (!vehicle->GetWheelConfig(w, &config) || !vehicle->GetWheelState(w, &state)) {
				continue;
			}

			const mt::vec4& stateColor = state.isInContact ? contactColor : airborneColor;

			// Suspension mount origin -> raycast full extent (rest length + radius).
			const mt::vec3 rayEnd = state.hardPointWS +
			                         state.wheelDirectionWS * (config.suspensionRestLength + config.wheelRadius);
			debugDraw.DrawLine(state.hardPointWS, rayEnd, raycastColor);

			// Suspension mount origin -> current wheel hub (compressed length).
			debugDraw.DrawLine(state.hardPointWS, state.worldPosition, stateColor);

			if (state.isInContact) {
				debugDraw.DrawLine(state.contactPoint, state.contactPoint + state.contactNormal * config.wheelRadius * 0.5f, normalColor);
			}

			// Wheel circle, in the plane perpendicular to the world-space axle.
			const mt::vec3 axleWS = (state.worldOrientation * config.axleDirection).SafeNormalized(mt::axisY3);
			mt::vec3 ref = (std::abs(axleWS.x) < 0.9f) ? mt::vec3(1.0f, 0.0f, 0.0f) : mt::vec3(0.0f, 1.0f, 0.0f);
			const mt::vec3 side1 = mt::cross(axleWS, ref).SafeNormalized(mt::axisZ3);
			const mt::vec3 side2 = mt::cross(axleWS, side1);

			const int segments = 16;
			mt::vec3 prev = state.worldPosition + side1 * config.wheelRadius;
			for (int s = 1; s <= segments; ++s) {
				const float angle = (2.0f * M_PI * s) / segments;
				const mt::vec3 next = state.worldPosition +
				                       (side1 * std::cos(angle) + side2 * std::sin(angle)) * config.wheelRadius;
				debugDraw.DrawLine(prev, next, stateColor);
				prev = next;
			}

			debugDraw.DrawLine(state.worldPosition - axleWS * config.wheelRadius * 0.5f,
			                    state.worldPosition + axleWS * config.wheelRadius * 0.5f, axleColor);
		}
	}
}
