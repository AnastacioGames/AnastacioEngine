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

/** \file KX_ShadowRenderer.h
 *  \ingroup ketsji
 */

#pragma once

#include "mathfu.h"

class KX_KetsjiEngine;
class KX_Scene;
class KX_Camera;
class KX_LightObject;
class RAS_ILightObject;

/** Owns the shadow rendering pipeline extracted out of KX_KetsjiEngine (Plano 5 of the Ketsji
 * modernization program, see docs/ketsji-engine-modernization-plan.md): light update/culling,
 * CSM cascade matrix computation, static/dynamic shadow-caster split, shadow buffer bind/
 * composite/restore, and the shadow debug frustum draw.
 *
 * This is a pure extraction: behavior and call order are unchanged from the previous
 * KX_KetsjiEngine methods. It still reaches back into KX_KetsjiEngine for shared engine state
 * (rasterizer, canvas, profiling logger, viewport computation, settle-frame counter) rather than
 * owning independent copies -- optimization/decoupling is deferred to a later pass once visual
 * equivalence with the pre-extraction behavior is confirmed in-game. */
class KX_ShadowRenderer
{
	KX_KetsjiEngine *m_engine;

public:
	explicit KX_ShadowRenderer(KX_KetsjiEngine *engine);
	~KX_ShadowRenderer() = default;

	/// Update lights, compute/cache CSM matrices and render all shadow buffers for the scene.
	void Render(KX_Scene *scene);

	/// Debug draw of each light's shadow frustum, if enabled (m_showShadowFrustum).
	void DrawDebugFrustum(KX_Scene *scene);

	/** Computes a camera-frustum-fit orthographic view/projection matrix pair for one Cascaded
	 * Shadow Mapping split, in the given light's local space. `cascadeIndex` is 0=Near, 1=Medium,
	 * 2=Low; the near/far distances for that split come from the light's clip range and cascade
	 * proportions. Assumes a perspective viewcam (orthographic viewcams fall back to a
	 * depth-independent frustum size, a known simplification). */
	static void ComputeCascadeShadowMatrices(
	        KX_Scene *scene, KX_Camera *viewcam, KX_LightObject *light, RAS_ILightObject *raslight, short cascadeIndex,
	        mt::mat4& r_viewmat, mt::mat4& r_winmat, float& r_splitFar);

	/** Pure math core of CSM frustum fitting: projects the 8 corners of the camera frustum
	 * slice [splitNear, splitFar] into light-local space and returns their axis-aligned bounds.
	 * Takes only plain matrices/scalars -- no KX_Scene/KX_Camera/RAS_ILightObject, no OpenGL,
	 * no live game state -- so it can be exercised by a fixed-input self-test (see
	 * SelfTestCascadeShadowMath) independently of a running game. Extracted from
	 * ComputeCascadeShadowMatrices, which adds the scene-dependent shadow-caster depth fit
	 * on top of this before building the final ortho matrix (see Plano 3, "testes matemáticos
	 * do CSM sem depender de OpenGL"). */
	static void ComputeCascadeFrustumBounds(
	        const mt::mat4& proj, bool perspective, float splitNear, float splitFar,
	        const mt::mat3x4& camWorldTrans, const mt::mat3x4& lightWorldInv,
	        float& r_minX, float& r_maxX, float& r_minY, float& r_maxY, float& r_minZ, float& r_maxZ);

	/** Runs ComputeCascadeFrustumBounds with fixed, hand-computed inputs/expected outputs and
	 * prints PASS/FAIL to console. No OpenGL context, scene, or gtest required -- callable at
	 * any point (e.g. once at startup in a debug build) to validate the CSM math in isolation. */
	static bool SelfTestCascadeShadowMath();
};
