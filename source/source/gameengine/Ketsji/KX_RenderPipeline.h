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

/** \file KX_RenderPipeline.h
 *  \ingroup ketsji
 *
 * Plano 6, unidade 1: extração pura (sem mudança de comportamento) dos tipos de
 * dados de uma passada de render, antes definidos como structs privados dentro
 * de KX_KetsjiEngine.
 *
 * Plano 6, unidade 2: extração pura dos métodos que constroem e consomem essa
 * árvore (GetCameraRenderData, GetRenderData, Render, RenderCollisionDepthBuffer,
 * RenderCamera, PostRenderScene, DrawDebugCameraFrustum, DrawDebugVehicles) para
 * a classe KX_RenderPipeline abaixo, no mesmo padrão do KX_ShadowRenderer
 * (Plano 5): reaproveita getters existentes de KX_KetsjiEngine e usa
 * friend class para o restante do estado compartilhado ainda sem getter.
 *
 * Plano 7, unidade 3: DrawDebugCameraFrustum e DrawDebugVehicles foram movidos
 * daqui para KX_DebugRenderer; RenderCamera agora delega a
 * m_engine->GetDebugRenderer().
 */

#ifndef __KX_RENDERPIPELINE_H__
#define __KX_RENDERPIPELINE_H__

#include "RAS_Rect.h"
#include "RAS_Rasterizer.h"
#include "RAS_OffScreen.h"
#include "RAS_ICanvas.h"

#include <vector>
#include <utility>

class KX_Scene;
class KX_Camera;
class KX_GameObject;

struct KX_CameraRenderData
{
	KX_CameraRenderData(KX_Camera *rendercam,
	                     KX_Camera *cullingcam,
	                     const RAS_Rect& area, const RAS_Rect& viewport,
	                     RAS_Rasterizer::StereoMode stereoMode, RAS_Rasterizer::StereoEye eye);
	KX_CameraRenderData(const KX_CameraRenderData& other);
	~KX_CameraRenderData();

	/// Rendered camera, could be a temporary camera in case of stereo.
	KX_Camera *m_renderCamera;
	KX_Camera *m_cullingCamera;
	RAS_Rect m_area;
	RAS_Rect m_viewport;
	RAS_Rasterizer::StereoMode m_stereoMode;
	RAS_Rasterizer::StereoEye m_eye;
};

struct KX_SceneRenderData
{
	KX_SceneRenderData(KX_Scene *scene);

	KX_Scene *m_scene;
	std::vector<KX_CameraRenderData> m_cameraDataList;
};

/// Data used to render a frame.
struct KX_FrameRenderData
{
	KX_FrameRenderData(RAS_OffScreen::Type ofsType);

	RAS_OffScreen::Type m_ofsType;
	std::vector<KX_SceneRenderData> m_sceneDataList;
};

struct KX_RenderData
{
	KX_RenderData(RAS_Rasterizer::StereoMode stereoMode, bool renderPerEye);

	RAS_Rasterizer::StereoMode m_stereoMode;
	bool m_renderPerEye;
	std::vector<KX_FrameRenderData> m_frameDataList;
};

class KX_KetsjiEngine;

/** Owns the per-frame render pipeline extracted out of KX_KetsjiEngine (Plano 6 of the Ketsji
 * modernization program, see docs/ketsji-engine-modernization-plan.md): building the render plan
 * for the frame (scenes/cameras/eyes), driving off-screen composition, rendering each camera
 * (culling, LOD, debug, buckets, particles), texture renderers/collision-depth and 2D
 * post-processing.
 *
 * This is a pure extraction: behavior and call order are unchanged from the previous
 * KX_KetsjiEngine methods. It still reaches back into KX_KetsjiEngine for shared engine state
 * (rasterizer, canvas, scene list, profiling logger, shadow renderer, debug flags) rather than
 * owning independent copies -- optimization/decoupling is deferred to a later pass once visual
 * equivalence with the pre-extraction behavior is confirmed in-game.
 *
 * Plano 6, unidade 3: caches CalculateVisibleMeshes()/UpdateObjectLods() results per
 * (cullingcam, eye) for the lifetime of a single Render() call. This only ever produces a hit
 * when a scene has an override culling camera (KX_Scene::GetOverrideCullingCamera) and more than
 * one viewport camera is rendered for it in the same frame, since that is the only case where two
 * KX_CameraRenderData entries share the same cullingcam/eye pair -- otherwise cullingcam is the
 * render camera itself, unique per entry, so the cache is always a miss and behavior is
 * unchanged. */
class KX_RenderPipeline
{
	KX_KetsjiEngine *m_engine;

	/// Per-frame cache of visible objects already culled+LOD'd for a given (cullingcam, eye),
	/// cleared at the start of every Render() call.
	std::vector<std::pair<std::pair<KX_Camera *, RAS_Rasterizer::StereoEye>, std::vector<KX_GameObject *> > > m_visibleMeshCache;

	/// Last swap control value actually pushed to the OS/driver (RAS_ICanvas::SWAP_CONTROL_MAX
	/// means "never applied yet"). Plano 9, unidade 1: SetSwapControl() ends up in a real driver
	/// call (GHOST_SetSwapInterval) each time, so this avoids repeating it every frame when the
	/// requested value hasn't changed since the last one we applied.
	RAS_ICanvas::SwapControl m_lastAppliedSwapControl = RAS_ICanvas::SWAP_CONTROL_MAX;

	/// Returns the cached visible object list for (cullingcam, eye), computing and caching it
	/// first if this is the first camera of the frame to request that pair.
	const std::vector<KX_GameObject *>& GetVisibleMeshes(KX_Scene *scene, KX_Camera *cullingcam, RAS_Rasterizer::StereoEye eye);

public:
	explicit KX_RenderPipeline(KX_KetsjiEngine *engine);
	~KX_RenderPipeline() = default;

	/// Render every scene/camera of the frame to the screen, if a render was requested.
	void Render();

	/// Depth-only pass for objects flagged use_gpu_particle_collider, feeding GPU particle
	/// Screen-Space collision. No-op if the scene has no such objects.
	void RenderCollisionDepthBuffer(KX_Scene *scene);

private:
	/// Compute frame render data per eyes (in case of stereo), scenes and camera.
	KX_RenderData GetRenderData();
	KX_CameraRenderData GetCameraRenderData(KX_Scene *scene, KX_Camera *camera, KX_Camera *overrideCullingCam,
	                                         const RAS_Rect& displayArea, RAS_Rasterizer::StereoMode stereoMode,
	                                         RAS_Rasterizer::StereoEye eye);

	/// Render one camera: culling, LOD, debug, buckets and particles.
	void RenderCamera(KX_Scene *scene, const KX_CameraRenderData& cameraFrameData, RAS_OffScreen *offScreen,
	                   unsigned short pass, bool isFirstScene);
	/// 2D post-processing filters, run once per scene.
	RAS_OffScreen *PostRenderScene(KX_Scene *scene, RAS_OffScreen *inputofs, RAS_OffScreen *targetofs);
};

#endif  // __KX_RENDERPIPELINE_H__
