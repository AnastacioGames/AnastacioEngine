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

/** \file KX_DebugRenderer.h
 *  \ingroup ketsji
 *
 * Plano 7, terceira unidade: extração pura (sem mudança de comportamento) dos
 * overlays de debug nativos do motor -- frustum de câmeras e suspensão/rodas de
 * veículos -- que antes viviam como métodos privados de KX_RenderPipeline
 * (movidos para lá no Plano 6). Mesmo padrão do KX_ShadowRenderer/KX_RenderPipeline/
 * KX_SimulationPipeline/KX_SceneScheduler: reaproveita getters existentes de
 * KX_KetsjiEngine (GetShowCameraFrustum, GetShowVehicleDebug, GetRasterizer) e não
 * possui estado próprio.
 */

#ifndef __KX_DEBUGRENDERER_H__
#define __KX_DEBUGRENDERER_H__

class KX_Scene;
class KX_KetsjiEngine;
struct KX_CameraRenderData;

/** Owns the native debug-draw overlays extracted out of KX_RenderPipeline (Plano 7 of the
 * Ketsji modernization program, see docs/ketsji-engine-modernization-plan.md): camera-frustum
 * wireframes and vehicle suspension/wheel debug lines.
 *
 * This is a pure extraction: behavior and call sites are unchanged. It still reaches back into
 * KX_KetsjiEngine for shared engine state (rasterizer, debug-option flags) rather than owning
 * independent copies. */
class KX_DebugRenderer
{
	KX_KetsjiEngine *m_engine;

public:
	explicit KX_DebugRenderer(KX_KetsjiEngine *engine);
	~KX_DebugRenderer() = default;

	/// Debug draw cameras frustum of a scene.
	void DrawDebugCameraFrustum(KX_Scene *scene, const KX_CameraRenderData& cameraFrameData);
	/// Debug draw vehicle suspension/wheels of a scene, from the last completed physics snapshot.
	void DrawDebugVehicles(KX_Scene *scene);
};

#endif  // __KX_DEBUGRENDERER_H__
