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

/** \file gameengine/Ketsji/KX_ShadowRenderer.cpp
 *  \ingroup ketsji
 */

#include "KX_ShadowRenderer.h"

#include <algorithm>
#include <cfloat>
#include <cmath>
#include <cstdio>
#include <unordered_map>
#include <unordered_set>

#include "KX_KetsjiEngine.h"
#include "KX_DebugMode.h"
#include "KX_Scene.h"
#include "KX_Camera.h"
#include "KX_GameObject.h"
#include "KX_LightObject.h"

#include "RAS_Rasterizer.h"
#include "RAS_ICanvas.h"
#include "RAS_ILightObject.h"
#include "RAS_DebugDraw.h"
#include "RAS_CameraData.h"

KX_ShadowRenderer::KX_ShadowRenderer(KX_KetsjiEngine *engine)
	:m_engine(engine)
{
}

/* Cascaded Shadow Mapping: computes a camera-frustum-fit orthographic view/projection matrix
 * pair, in the light's own local space, for one of the 3 fixed cascades (0=Near, 1=Medium,
 * 2=Low). The near/far split distances come from the light's shadow clip range and cascade
 * proportions -- see RAS_ILightObject::m_shadowclipstart/m_shadowclipend/m_cascadeproportion*.
 * The view matrix is the same for every cascade (the light's own inverted world transform,
 * no per-cascade recentering/texel-snapping); only the ortho projection bounds differ, derived
 * from the 8 corners of the viewing camera's frustum slice [splitNear, splitFar] transformed
 * into light space. Assumes a perspective viewcam; an orthographic viewcam falls back to a
 * depth-independent slice size (same shape as the camera's own near-plane extents). */
void KX_ShadowRenderer::ComputeCascadeFrustumBounds(
        const mt::mat4& proj, bool perspective, float splitNear, float splitFar,
        const mt::mat3x4& camWorldTrans, const mt::mat3x4& lightWorldInv,
        float& r_minX, float& r_maxX, float& r_minY, float& r_maxY, float& r_minZ, float& r_maxZ)
{
	const float p00 = proj(0, 0);
	const float p11 = proj(1, 1);

	/* 8 corners of the camera frustum slice [splitNear, splitFar], in camera view space. */
	mt::vec3 corners[8];
	int idx = 0;
	const float dists[2] = { splitNear, splitFar };
	for (int s = 0; s < 2; ++s) {
		const float d = dists[s];
		float hw, hh;
		if (perspective) {
			hw = d / p00;
			hh = d / p11;
		}
		else {
			/* Orthographic: extents don't scale with depth. */
			hw = 1.0f / p00;
			hh = 1.0f / p11;
		}
		corners[idx++] = mt::vec3(-hw, -hh, -d);
		corners[idx++] = mt::vec3(hw, -hh, -d);
		corners[idx++] = mt::vec3(-hw, hh, -d);
		corners[idx++] = mt::vec3(hw, hh, -d);
	}

	float minX = FLT_MAX, maxX = -FLT_MAX;
	float minY = FLT_MAX, maxY = -FLT_MAX;
	float minZ = FLT_MAX, maxZ = -FLT_MAX;

	for (int i = 0; i < 8; ++i) {
		const mt::vec3 worldCorner = camWorldTrans * corners[i];
		const mt::vec3 lc = lightWorldInv * worldCorner;
		minX = std::min(minX, lc[0]); maxX = std::max(maxX, lc[0]);
		minY = std::min(minY, lc[1]); maxY = std::max(maxY, lc[1]);
		minZ = std::min(minZ, lc[2]); maxZ = std::max(maxZ, lc[2]);
	}

	r_minX = minX; r_maxX = maxX;
	r_minY = minY; r_maxY = maxY;
	r_minZ = minZ; r_maxZ = maxZ;
}

bool KX_ShadowRenderer::SelfTestCascadeShadowMath()
{
	bool ok = true;
	auto check = [&](bool cond, const char *msg) {
		if (!cond) {
			ok = false;
			printf("[SelfTestCascadeShadowMath] FAIL: %s\n", msg);
		}
	};

	/* Symmetric perspective projection, fov ~90 deg on both axes (p00 = p11 = 1). */
	mt::mat4 proj = mt::mat4::Identity();
	proj(0, 0) = 1.0f;
	proj(1, 1) = 1.0f;

	/* Camera and light both at the world origin with identity orientation: camera looks
	 * down its local -Z, light-space == camera-space, so the bounds are exactly the
	 * symmetric frustum slice extents (hw = hh = d at p00 = p11 = 1). */
	const mt::mat3x4 identity = mt::mat3x4::Identity();
	const float splitNear = 2.0f;
	const float splitFar = 5.0f;

	float minX, maxX, minY, maxY, minZ, maxZ;
	ComputeCascadeFrustumBounds(proj, true, splitNear, splitFar, identity, identity,
	                             minX, maxX, minY, maxY, minZ, maxZ);

	check(fabsf(minX + splitFar) < 1e-4f, "minX esperado -splitFar (maior extensao XY na distancia mais longe)");
	check(fabsf(maxX - splitFar) < 1e-4f, "maxX esperado +splitFar");
	check(fabsf(minY + splitFar) < 1e-4f, "minY esperado -splitFar");
	check(fabsf(maxY - splitFar) < 1e-4f, "maxY esperado +splitFar");
	/* Local Z: corners are at -splitNear/-splitFar, so minZ = -splitFar, maxZ = -splitNear. */
	check(fabsf(minZ + splitFar) < 1e-4f, "minZ esperado -splitFar");
	check(fabsf(maxZ + splitNear) < 1e-4f, "maxZ esperado -splitNear");

	/* Orthographic camera: extents must not scale with depth (same hw/hh at both splits). */
	ComputeCascadeFrustumBounds(proj, false, splitNear, splitFar, identity, identity,
	                             minX, maxX, minY, maxY, minZ, maxZ);
	check(fabsf(minX + 1.0f) < 1e-4f, "ortho: minX esperado -1 (independente da distancia)");
	check(fabsf(maxX - 1.0f) < 1e-4f, "ortho: maxX esperado +1");

	if (!ok) {
		printf("[SelfTestCascadeShadowMath] RESULTADO: houve FAIL(s), ver mensagens acima\n");
	}
	return ok;
}

void KX_ShadowRenderer::ComputeCascadeShadowMatrices(
        KX_Scene *scene, KX_Camera *viewcam, KX_LightObject *light, RAS_ILightObject *raslight, short cascadeIndex,
        mt::mat4& r_viewmat, mt::mat4& r_winmat, float& r_splitFar)
{
	const float clipstart = raslight->m_shadowclipstart;
	const float cliprange = raslight->m_shadowclipend - raslight->m_shadowclipstart;
	const float propNear = raslight->m_cascadeproportionnear;
	const float propMiddle = raslight->m_cascadeproportionmiddle;

	float splitNear, splitFar;
	switch (cascadeIndex) {
		case 0: /* Near */
		{
			splitNear = clipstart;
			splitFar = clipstart + propNear * cliprange;
			break;
		}
		case 1: /* Medium */
		{
			splitNear = clipstart + propNear * cliprange;
			splitFar = splitNear + propMiddle * cliprange;
			break;
		}
		default: /* Low */
		{
			splitNear = clipstart + (propNear + propMiddle) * cliprange;
			splitFar = raslight->m_shadowclipend;
			break;
		}
	}
	r_splitFar = splitFar;

	const RAS_CameraData *camdata = viewcam->GetCameraData();
	const mt::mat4& proj = viewcam->GetProjectionMatrix(RAS_Rasterizer::RAS_STEREO_LEFTEYE);
	const mt::mat3x4 camWorldTrans = viewcam->NodeGetWorldTransform();
	const mt::mat3x4 lightWorldInv = light->NodeGetWorldTransform().Inverse();

	float minX, maxX, minY, maxY, minZ, maxZ;
	ComputeCascadeFrustumBounds(proj, camdata->m_perspective, splitNear, splitFar,
	                             camWorldTrans, lightWorldInv,
	                             minX, maxX, minY, maxY, minZ, maxZ);

	/* The camera slice bounds receivers, but its shadow map must also contain scene
	 * geometry which overlaps the slice in light-space X/Y.  Fit Z to those caster
	 * bounds instead of adding the entire shadow clip range: this prevents pitch-
	 * dependent clipping without sacrificing depth precision and shadow bias quality. */
	auto includeCasterDepth = [&](KX_GameObject *obj) {
		if (obj->GetMeshList().empty()) {
			return;
		}

		const SG_BBox& box = obj->GetCullingNode().GetAabb();
		const mt::vec3& boxMin = box.GetMin();
		const mt::vec3& boxMax = box.GetMax();
		const mt::mat3x4 worldTransform = obj->NodeGetWorldTransform();
		float objectMinX = FLT_MAX, objectMaxX = -FLT_MAX;
		float objectMinY = FLT_MAX, objectMaxY = -FLT_MAX;
		float objectMinZ = FLT_MAX, objectMaxZ = -FLT_MAX;

		for (int corner = 0; corner < 8; ++corner) {
			const mt::vec3 local((corner & 1) ? boxMax[0] : boxMin[0],
			                     (corner & 2) ? boxMax[1] : boxMin[1],
			                     (corner & 4) ? boxMax[2] : boxMin[2]);
			const mt::vec3 lc = lightWorldInv * (worldTransform * local);
			objectMinX = std::min(objectMinX, lc[0]); objectMaxX = std::max(objectMaxX, lc[0]);
			objectMinY = std::min(objectMinY, lc[1]); objectMaxY = std::max(objectMaxY, lc[1]);
			objectMinZ = std::min(objectMinZ, lc[2]); objectMaxZ = std::max(objectMaxZ, lc[2]);
		}

		if (objectMaxX >= minX && objectMinX <= maxX &&
		    objectMaxY >= minY && objectMinY <= maxY) {
			minZ = std::min(minZ, objectMinZ - 0.5f);
			maxZ = std::max(maxZ, objectMaxZ + 0.5f);
		}
	};
	for (KX_GameObject *obj : scene->GetStaticShadowCasterObjects()) {
		includeCasterDepth(obj);
	}
	for (KX_GameObject *obj : scene->GetDynamicShadowCasterObjects()) {
		includeCasterDepth(obj);
	}

	/* Light shines down its local -Z axis (Blender convention), so distance-from-light
	 * increases as local Z decreases: near = -maxZ (closest), far = -minZ (farthest). */
	const float lightNear = -maxZ;
	const float lightFar = -minZ;

	r_winmat = mt::mat4::Ortho(minX, maxX, minY, maxY, lightNear, lightFar);

	float viewmat4x4[4][4];
	lightWorldInv.PackFromAffineTransform(viewmat4x4);
	r_viewmat = mt::mat4((float *)viewmat4x4);
}

namespace {
/// Releases a temporary shadow-pass camera on scope exit, so a future early return/continue
/// added inside KX_ShadowRenderer::Render's per-pass loop (between `new KX_Camera` and the
/// matching `->Release()`) can't leak it.
class KX_TempCameraGuard
{
	KX_Camera *m_cam;

public:
	explicit KX_TempCameraGuard(KX_Camera *cam) : m_cam(cam) {}
	~KX_TempCameraGuard()
	{
		m_cam->Release();
	}
};

/// Unbinds the static shadow sub-pass framebuffer on scope exit, so a future early return
/// added between BindStaticShadowBuffer and the matching UnbindStaticShadowBuffer (e.g. an
/// empty-visible-list bail-out) can't leave that framebuffer bound for the rest of the frame.
class KX_StaticShadowBufferGuard
{
	RAS_ILightObject *m_raslight;
	short m_pass;
	mt::mat4 m_cascadeView;
	mt::mat4 m_cascadeWin;

public:
	KX_StaticShadowBufferGuard(RAS_ILightObject *raslight, short pass, const mt::mat4& cascadeView, const mt::mat4& cascadeWin)
		:m_raslight(raslight), m_pass(pass), m_cascadeView(cascadeView), m_cascadeWin(cascadeWin)
	{
	}
	~KX_StaticShadowBufferGuard()
	{
		m_raslight->UnbindStaticShadowBuffer(m_pass, m_cascadeView, m_cascadeWin);
	}
};

/// Unbinds the main shadow-pass framebuffer on scope exit (cascade or simple, matching
/// whichever Bind*ShadowBuffer variant was used), for the same reason as
/// KX_StaticShadowBufferGuard above.
class KX_ShadowBufferGuard
{
	RAS_ILightObject *m_raslight;
	short m_pass;
	bool m_useCascade;

public:
	KX_ShadowBufferGuard(RAS_ILightObject *raslight, short pass, bool useCascade)
		:m_raslight(raslight), m_pass(pass), m_useCascade(useCascade)
	{
	}
	~KX_ShadowBufferGuard()
	{
		if (m_useCascade) {
			m_raslight->UnbindCascadeShadowBuffer(m_pass);
		}
		else {
			m_raslight->UnbindShadowBuffer();
		}
	}
};

/* Cascade-invalidation cache (Plano 5, 3a unidade de otimizacao): skips recomputing the 3 CSM
 * matrices for a light when the camera hasn't moved since the last time they were computed for
 * it. Conservative on purpose -- also requires the scene to have zero dynamic shadow casters,
 * since ComputeCascadeShadowMatrices' Z-bounds fit walks caster AABBs and a moving dynamic
 * caster can change those bounds independently of the camera. Keyed by light pointer in a
 * file-scope cache (KX_ShadowRenderer itself is otherwise stateless, see class comment); a
 * light destroyed and a new one reallocated at the same address would at worst reuse a stale
 * cascade for one frame (self-corrects on the next camera move), not a memory-safety issue,
 * since the pointer is only ever used as a map key, never dereferenced here. */
bool Mat3x4NearlyEqual(const mt::mat3x4& a, const mt::mat3x4& b, float epsilon = 1e-5f)
{
	for (int row = 0; row < 3; ++row) {
		for (int col = 0; col < 4; ++col) {
			if (fabsf(a(row, col) - b(row, col)) > epsilon) {
				return false;
			}
		}
	}
	return true;
}

/* Loose threshold used only by the "Tolerant" (2) cache setting below, to decide whether a
 * small camera/light movement is still worth reusing last frame's cascade matrices for one
 * extra frame. Deliberately coarser than the exact-match epsilon above -- picked as "visibly
 * near-stationary", not derived from any error bound on the resulting shadow. */
const float kCSMCacheToleranceEpsilon = 1e-3f;

struct CascadeMatrixCache
{
	bool valid = false;
	/// Consecutive frames reused under the "Tolerant" setting despite a small movement; capped
	/// at 1 so a slowly panning camera never drifts the cascade indefinitely.
	int staleFrames = 0;
	mt::mat3x4 camWorldTrans = mt::mat3x4::Identity();
	mt::mat3x4 lightWorldInv = mt::mat3x4::Identity();
	mt::mat4 viewmat[3];
	mt::mat4 winmat[3];
	float splitFar[3] = { 0.0f, 0.0f, 0.0f };
};
}  // namespace

void KX_ShadowRenderer::Render(KX_Scene *scene)
{
	static std::unordered_map<KX_LightObject *, CascadeMatrixCache> cascadeCache;

	RAS_Rasterizer *rasty = m_engine->GetRasterizer();
	RAS_ICanvas *canvas = m_engine->GetCanvas();

	EXP_ListValue<KX_LightObject> *lightlist = scene->GetLightList();

	rasty->SetAuxilaryClientInfo(scene);

	KX_Camera *cullCam = scene->GetActiveCamera();
	if (cullCam) {
		/* Shadow rendering precedes GetRenderData(), but CSM needs the active camera's
		 * projection for its frustum slices. Prepare the same left-eye view here so the
		 * first shadow pass uses the current frame's valid projection instead of either
		 * dividing by the camera's zero-initialized matrix or waiting one frame. */
		const RAS_Rasterizer::StereoMode stereoMode = rasty->GetStereoMode();
		const RAS_Rasterizer::StereoEye eye = RAS_Rasterizer::RAS_STEREO_LEFTEYE;
		const RAS_Rect displayArea = rasty->GetRenderArea(canvas, stereoMode, eye);
		RAS_Rect area;
		RAS_Rect viewport;
		m_engine->GetSceneViewport(scene, cullCam, displayArea, area, viewport);
		cullCam->UpdateView(rasty, scene, stereoMode, eye, viewport, area);
	}

	RAS_DebugDraw& lightDebugDraw = scene->GetDebugDraw();

	m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_lightupdate);

	for (KX_LightObject *light : lightlist) {
		// Distance-based light culling ("light LOD"): decide before Update() so that a culled
		// light is also reported as hidden to the GPU lamp (skips shading), not just shadows.
		light->UpdateDistanceCulling(cullCam);
		light->Update();

		// Distant-light billboard impostor: fades in as the light itself fades out/gets culled
		// by distance, so it never just pops. See KX_LightObject::UpdateDistanceCulling for the
		// fade formula and RAS_DebugDraw::DrawLightGlow / gpu_shader_light_glow_*.glsl for the
		// "always face camera" billboard draw.
		const float fadeAlpha = light->GetCullFadeAlpha();
		if (light->GetVisible() && fadeAlpha > 0.0f) {
			RAS_ILightObject *raslight = light->GetLightData();
			const mt::vec4 glowColor(raslight->m_color.x, raslight->m_color.y, raslight->m_color.z, fadeAlpha);
			lightDebugDraw.DrawLightGlow(light->NodeGetWorldPosition(), raslight->m_distance * 0.05f * raslight->m_glowScale, glowColor);
		}
	}

	m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_shadows);

	int shadowUpdatedLights = 0;
	int shadowPasses = 0;

	if (rasty->GetDrawingMode() == RAS_Rasterizer::RAS_TEXTURED) {
		KX_Camera *viewcam = cullCam;

		// Temporary shadow-pass cameras, reused across every light/cascade/pass of this
		// Render() call instead of newed and released per pass: Bind*ShadowBuffer below
		// fully overwrites the camera's modelview/projection matrices each time it's used,
		// so no per-pass state survives reuse -- only the allocation itself was wasted work.
		RAS_CameraData camdata = RAS_CameraData();
		KX_Camera *cam = new KX_Camera(scene, KX_Scene::m_callbacks, camdata, true);
		KX_TempCameraGuard camGuard(cam);
		cam->SetName("__shadow__cam__");

		RAS_CameraData staticCamdata = RAS_CameraData();
		KX_Camera *staticCam = new KX_Camera(scene, KX_Scene::m_callbacks, staticCamdata, true);
		KX_TempCameraGuard staticCamGuard(staticCam);
		staticCam->SetName("__shadow__static__cam__");

		// Automatic static shadow cache invalidation: a static caster was added/removed since
		// last frame (e.g. destroyed/replaced at runtime), so any cached static depth may show
		// a "ghost" of an object that's gone. Invalidate once per scene per frame, not per pass.
		const bool staticCasterListDirty = scene->IsStaticShadowCasterListDirty();

		for (KX_LightObject *light : lightlist) {
			RAS_ILightObject *raslight = light->GetLightData();
			if (staticCasterListDirty && raslight->m_staticShadow && raslight->HasCascadedShadow()) {
				raslight->InvalidateStaticShadow();
			}
			const bool hasCascade = viewcam && raslight->HasCascadedShadow();
			const bool useCascade = light->GetVisible() && !light->GetDistanceCulled() && raslight->HasShadowBuffer() && hasCascade;
			// Static/dynamic shadow cache split (Sun + CSM only, see gentle-wobbling-reef plan):
			// only worth the extra bind/blit when the scene actually has casters in both lists.
			// Held off during the engine's startup render frames: the camera may be in a transient
			// startup pose (e.g. before a Python/game-logic controller places it at its resting
			// transform), and the first static bake locks onto whatever matrix it sees -- once the
			// camera settles and stops moving, nothing ever drifts past the epsilon to force a
			// re-bake, permanently freezing shadow geometry captured from the wrong pose.
			const bool useStaticSplit = useCascade && raslight->m_staticShadow &&
			                             !scene->GetStaticShadowCasterObjects().empty() &&
			                             !scene->GetDynamicShadowCasterObjects().empty() &&
			                             m_engine->IsStaticShadowSettled();

			// The whole-light m_requestShadowUpdate gate is for the old all-or-nothing cache
			// (entire light frozen until a manual update request). With the static/dynamic split,
			// the dynamic sub-pass must redraw every frame and the static sub-pass already
			// self-gates per cascade (NeedStaticShadowUpdate), so this coarse gate is bypassed --
			// otherwise, since nothing sets m_requestShadowUpdate automatically as the camera moves,
			// the whole cascade block (both sub-passes) would simply stop running.
			if (light->GetVisible() && !light->GetDistanceCulled() && raslight->HasShadowBuffer() &&
			    (useStaticSplit || raslight->NeedShadowUpdate())) {
				const short numPasses = useCascade ? 3 : 1;
				++shadowUpdatedLights;
				shadowPasses += numPasses;

// Computed once per cascade here (not re-derived per pass below): each call walks
				// every static/dynamic shadow caster to fit the Z bounds, so recomputing it a
				// second time per pass would repeat that full scan for no new result.
				mt::mat4 cascadeViews[3], cascadeWins[3];
				float cascadeSplitFars[3];
				if (useCascade) {
					// Cascade-invalidation cache: reuse last frame's cascade matrices verbatim
					// when the camera hasn't moved and the scene has no dynamic shadow casters
					// (see CascadeMatrixCache comment above) -- otherwise the caster-Z-bounds
					// fit inside ComputeCascadeShadowMatrices could silently go stale. Gated by
					// the active camera's "Shadow Cascade Cache Tolerance" (0 Off / 1 Exact /
					// 2 Tolerant, see KX_Camera::GetCSMCacheMaxStaleFrames): Off always
					// recomputes below; Tolerant additionally allows one frame of small
					// movement, which is the knob for camera-motion shadow "shimmer" reports.
					const short cacheTolerance = viewcam->GetCSMCacheMaxStaleFrames();
					const mt::mat3x4 camWorldTrans = viewcam->NodeGetWorldTransform();
					const mt::mat3x4 lightWorldInv = light->NodeGetWorldTransform().Inverse();
					CascadeMatrixCache& cc = cascadeCache[light];
					const bool cacheEligible = cacheTolerance >= 1 && cc.valid && !staticCasterListDirty &&
					                            scene->GetDynamicShadowCasterObjects().empty();
					bool canReuse = false;
					if (cacheEligible) {
						if (Mat3x4NearlyEqual(camWorldTrans, cc.camWorldTrans) &&
						    Mat3x4NearlyEqual(lightWorldInv, cc.lightWorldInv)) {
							canReuse = true;
							cc.staleFrames = 0;
						}
						else if (cacheTolerance >= 2 && cc.staleFrames < 1 &&
						         Mat3x4NearlyEqual(camWorldTrans, cc.camWorldTrans, kCSMCacheToleranceEpsilon) &&
						         Mat3x4NearlyEqual(lightWorldInv, cc.lightWorldInv, kCSMCacheToleranceEpsilon)) {
							canReuse = true;
							cc.staleFrames += 1;
						}
					}
					if (canReuse) {
						for (short p = 0; p < 3; ++p) {
							cascadeViews[p] = cc.viewmat[p];
							cascadeWins[p] = cc.winmat[p];
							cascadeSplitFars[p] = cc.splitFar[p];
						}
					}
					else {
						for (short p = 0; p < 3; ++p) {
							ComputeCascadeShadowMatrices(scene, viewcam, light, raslight, p, cascadeViews[p], cascadeWins[p], cascadeSplitFars[p]);
						}
						cc.camWorldTrans = camWorldTrans;
						cc.lightWorldInv = lightWorldInv;
						for (short p = 0; p < 3; ++p) {
							cc.viewmat[p] = cascadeViews[p];
							cc.winmat[p] = cascadeWins[p];
							cc.splitFar[p] = cascadeSplitFars[p];
						}
						cc.valid = true;
						cc.staleFrames = 0;
					}
					raslight->SetCascadeSplits(cascadeSplitFars[0], cascadeSplitFars[1]);
				}

				std::unordered_set<KX_GameObject *> dynamicCasterSet;
				if (useStaticSplit) {
					const std::vector<KX_GameObject *>& dynamicCasters = scene->GetDynamicShadowCasterObjects();
					dynamicCasterSet.insert(dynamicCasters.begin(), dynamicCasters.end());
				}

				for (short pass = 0; pass < numPasses; ++pass) {
					mt::mat4 cascadeView, cascadeWin;
					if (useCascade) {
						cascadeView = cascadeViews[pass];
						cascadeWin = cascadeWins[pass];
					}

					// (a) Static sub-pass: only re-rendered when the cache is stale (first frame,
					// explicit dirty, or the cascade's view/win matrix drifted -- see
					// NeedStaticShadowUpdate / GPU_lamp_shadow_static_matches).
					if (useStaticSplit && m_engine->GetShadowCulling() &&
					    raslight->NeedStaticShadowUpdate(pass, cascadeView, cascadeWin)) {
						mt::mat3x4 staticCamtrans;
						raslight->BindStaticShadowBuffer(canvas, pass, staticCam, staticCamtrans, cascadeView, cascadeWin);
						KX_StaticShadowBufferGuard staticShadowBufferGuard(raslight, pass, cascadeView, cascadeWin);

						m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_shadowculling);

						const std::vector<KX_GameObject *> visible = scene->CalculateVisibleMeshes(
						    staticCam, staticCam->GetFrustum(RAS_Rasterizer::RAS_STEREO_LEFTEYE), raslight->GetShadowLayer(), true);

						std::vector<KX_GameObject *> staticVisible;
						staticVisible.reserve(visible.size());
						for (KX_GameObject *obj : visible) {
							if (dynamicCasterSet.find(obj) == dynamicCasterSet.end()) {
								staticVisible.push_back(obj);
							}
						}
						m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_shadows);

						rasty->Clear(RAS_Rasterizer::RAS_DEPTH_BUFFER_BIT | RAS_Rasterizer::RAS_COLOR_BUFFER_BIT);
						scene->RenderBuckets(staticVisible, RAS_Rasterizer::RAS_SHADOW, staticCamtrans, rasty, nullptr);
					}

					mt::mat3x4 camtrans;

					/* binds framebuffer object, sets up camera .. */
					if (useCascade) {
						raslight->BindCascadeShadowBuffer(canvas, pass, cam, camtrans, cascadeView, cascadeWin);
					}
					else {
						raslight->BindShadowBuffer(canvas, cam, camtrans);
					}
					KX_ShadowBufferGuard shadowBufferGuard(raslight, pass, useCascade);

					// (b) Composite the cached static depth into the buffer we just bound, then
					// only draw the dynamic casters on top -- the static geometry is already there.
					if (useStaticSplit) {
						raslight->CompositeStaticShadow(pass);
					}

					if (m_engine->GetShadowCulling()) {
						m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_shadowculling);

						const std::vector<KX_GameObject *> objects = scene->CalculateVisibleMeshes(cam, cam->GetFrustum(RAS_Rasterizer::RAS_STEREO_LEFTEYE), raslight->GetShadowLayer(), true);

						m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_shadows);

						/* render */
						if (!useStaticSplit) {
							rasty->Clear(RAS_Rasterizer::RAS_DEPTH_BUFFER_BIT | RAS_Rasterizer::RAS_COLOR_BUFFER_BIT);
						}
						// Send a nullptr off screen because the viewport is binding it's using its own private one.
						if (useStaticSplit) {
							std::vector<KX_GameObject *> dynamicVisible;
							dynamicVisible.reserve(objects.size());
							for (KX_GameObject *obj : objects) {
								if (dynamicCasterSet.find(obj) != dynamicCasterSet.end()) {
									dynamicVisible.push_back(obj);
								}
							}
							scene->RenderBuckets(dynamicVisible, RAS_Rasterizer::RAS_SHADOW, camtrans, rasty, nullptr);
						}
						else {
							scene->RenderBuckets(objects, RAS_Rasterizer::RAS_SHADOW, camtrans, rasty, nullptr);
						}
					}
					else {
						m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_shadows);

						/* render */
						if (!useStaticSplit) {
							rasty->Clear(RAS_Rasterizer::RAS_DEPTH_BUFFER_BIT | RAS_Rasterizer::RAS_COLOR_BUFFER_BIT);
						}
					}
				}
			}
		}

		if (staticCasterListDirty) {
			scene->ClearStaticShadowCasterListDirty();
		}
	}

	scene->SetLastLightsCounters(lightlist->GetCount(), shadowUpdatedLights, shadowPasses);
}

void KX_ShadowRenderer::DrawDebugFrustum(KX_Scene *scene)
{
	if (m_engine->GetShowShadowFrustum() == KX_DebugOption::DISABLE) {
		return;
	}

	RAS_DebugDraw& debugDraw = scene->GetDebugDraw();
	for (KX_LightObject *light : scene->GetLightList()) {
		RAS_ILightObject *raslight = light->GetLightData();
		if (m_engine->GetShowShadowFrustum() == KX_DebugOption::FORCE || light->GetShowShadowFrustum()) {
			const mt::mat4 projmat(raslight->GetWinMat());
			const mt::mat4 viewmat(raslight->GetViewMat());

			debugDraw.DrawCameraFrustum(projmat * viewmat);
		}
	}
}
