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
 * Contributor(s): Ulysse Martin, Tristan Porteries, Martins Upitis.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Ketsji/KX_TextureRendererManager.cpp
 *  \ingroup ketsji
 */

#include "KX_TextureRendererManager.h"
#include "KX_Camera.h"
#include "KX_Scene.h"
#include "KX_CubeMap.h"
#include "KX_PlanarMap.h"
#include "KX_PlanarReflector.h"
#include "KX_LightProbe.h"
#include "KX_ProbeVolume.h"
#include "KX_GameObject.h"
#include "KX_LightObject.h"
#include "KX_WorldInfo.h"

#include "RAS_Rasterizer.h"
#include "RAS_OffScreen.h"
#include "RAS_Texture.h"
#include "RAS_ILightObject.h"
#include "RAS_2DFilter.h"

#include "DNA_texture_types.h"
#include "DNA_object_types.h"

#include "GPU_material.h"

#ifdef __EMSCRIPTEN__
#  include "RAS_WebGLCompat.h"
#endif

#include "CM_Message.h"
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <cstring>

namespace {

/// Calls KX_TextureRenderer::EndRender on scope exit, so a future early return added inside
/// RenderRenderer's per-face loop (e.g. an error check alongside the existing SetupCameraFace
/// bail-out) can't skip the matching EndRender for a BeginRender that already happened.
class KX_TextureRendererEndGuard
{
	KX_TextureRenderer *m_renderer;
	RAS_Rasterizer *m_rasty;

public:
	KX_TextureRendererEndGuard(KX_TextureRenderer *renderer, RAS_Rasterizer *rasty)
		:m_renderer(renderer), m_rasty(rasty)
	{
	}
	~KX_TextureRendererEndGuard()
	{
		m_renderer->EndRender(m_rasty);
	}
};

/// Linear capture of the probe volumes for the guard's scope (materials and World skip the display transform).
class VolumeCaptureGuard
{
	bool& m_flag;

public:
	explicit VolumeCaptureGuard(bool& flag)
		:m_flag(flag)
	{
		m_flag = true;
		GPU_material_set_linear_capture(true);
	}
	~VolumeCaptureGuard()
	{
		m_flag = false;
		GPU_material_set_linear_capture(false);
	}
};

}  // namespace

KX_TextureRendererManager::KX_TextureRendererManager(KX_Scene *scene)
	:m_scene(scene),
	m_worldProbe(nullptr),
	m_capturing(false),
	m_capturingVolume(false)
{
	const RAS_CameraData& camdata = RAS_CameraData();
	m_camera = new KX_Camera(m_scene, KX_Scene::m_callbacks, camdata, true);
	m_camera->SetName("__renderer_cam__");
	std::fill_n(m_worldSignature, 16, -1.0f);
}

KX_TextureRendererManager::~KX_TextureRendererManager()
{
	for (unsigned short i = 0; i < CATEGORY_MAX; ++i) {
		for (KX_TextureRenderer *renderer : m_renderers[i]) {
			delete renderer;
		}
	}
	for (KX_ProbeVolume *volume : m_volumes) {
		delete volume;
	}

	m_camera->Release();
}

void KX_TextureRendererManager::InvalidateViewpoint(KX_GameObject *gameobj)
{
	for (unsigned short i = 0; i < CATEGORY_MAX; ++i) {
		for (KX_TextureRenderer *renderer : m_renderers[i]) {
			if (renderer->GetViewpointObject() == gameobj) {
				renderer->SetViewpointObject(nullptr);
			}
		}
	}
	// A removed box Empty takes its grid along (cube, atlas, readbacks); called with the GL context current.
	for (auto it = m_volumes.begin(); it != m_volumes.end();) {
		if ((*it)->GetViewpointObject() == gameobj) {
			delete *it;
			it = m_volumes.erase(it);
		}
		else {
			++it;
		}
	}
}

void KX_TextureRendererManager::AddRenderer(RendererType type, RAS_Texture *texture, KX_GameObject *viewpoint)
{
	/* Don't Add renderer several times for the same texture. If the texture is shared by several objects,
	 * we just add a "textureUser" to signal that the renderer texture will be shared by several objects.
	 */
	for (unsigned short i = 0; i < CATEGORY_MAX; ++i) {
		for (KX_TextureRenderer *renderer : m_renderers[i]) {
			if (renderer->EqualTextureUser(texture)) {
				renderer->AddTextureUser(texture);

				KX_GameObject *origviewpoint = renderer->GetViewpointObject();
				if (viewpoint != origviewpoint) {
					CM_Warning("texture renderer (" << texture->GetName() << ") uses different viewpoint objects (" <<
					           (origviewpoint ? origviewpoint->GetName() : "<None>") << " and " << viewpoint->GetName() << ").");
				}
				return;
			}
		}
	}

	EnvMap *env = texture->GetTex()->env;
	KX_TextureRenderer *renderer;
	switch (type) {
		case CUBE:
		{
			renderer = new KX_CubeMap(env, viewpoint);
			m_renderers[VIEWPORT_INDEPENDENT].push_back(renderer);
			break;
		}
		case PLANAR:
		{
			renderer = new KX_PlanarMap(env, viewpoint);
			m_renderers[VIEWPORT_DEPENDENT].push_back(renderer);
			break;
		}
	}

	renderer->AddTextureUser(texture);
}

void KX_TextureRendererManager::AddProbe(KX_GameObject *viewpoint, float radius, int size, float clipEnd, bool realtime)
{
	KX_LightProbe *probe = new KX_LightProbe(viewpoint, radius, size, clipEnd, realtime);
	m_renderers[VIEWPORT_INDEPENDENT].push_back(probe);
	m_probes.push_back(probe);
}

void KX_TextureRendererManager::AddProbeVolume(KX_GameObject *box, float spacing, int quality, float clipEnd,
                                               int ignoreLayers, bool freeze, float ssgiWeight, float bounce)
{
#ifdef __EMSCRIPTEN__
	if (!RAS_FloatRenderTargetSupported()) {
		CM_Warning("probe volume \"" << box->GetName() << "\": off, the browser can't render to half float");
		return;
	}
#endif
	quality = std::min(std::max(quality, 0), 2);
	m_volumes.push_back(new KX_ProbeVolume(box, spacing, (KX_ProbeVolume::Quality)quality, clipEnd, ignoreLayers, freeze,
	                                         ssgiWeight, bounce));
}

KX_PlanarReflector *KX_TextureRendererManager::AddPlanarReflector(KX_GameObject *viewpoint, int size, float clipEnd)
{
	for (KX_PlanarReflector *reflector : m_planarReflectors) {
		if (reflector->GetViewpointObject() == viewpoint) {
			return reflector;
		}
	}

	KX_PlanarReflector *reflector = new KX_PlanarReflector(viewpoint, size, clipEnd);
	m_renderers[VIEWPORT_DEPENDENT].push_back(reflector);
	m_planarReflectors.push_back(reflector);
	return reflector;
}

KX_PlanarReflector *KX_TextureRendererManager::FindPlanarReflector(KX_GameObject *viewpoint) const
{
	for (KX_PlanarReflector *reflector : m_planarReflectors) {
		if (reflector->GetViewpointObject() == viewpoint) {
			return reflector;
		}
	}
	return nullptr;
}

void KX_TextureRendererManager::AddWorldProbe(int size)
{
	if (m_worldProbe) {
		return;
	}
	m_worldProbe = new KX_LightProbe(nullptr, 0.0f, size, 100.0f, false);
	m_renderers[VIEWPORT_INDEPENDENT].push_back(m_worldProbe);
}

static void SetProbeSlot(KX_TextureRendererManager::ProbeSlot& slot, KX_LightProbe *probe, bool parallax)
{
	slot.cube = probe->GetCubeTexture();
	slot.maxLod = probe->GetMaxLod();
	slot.sh = probe->GetSH();
	slot.radius = 0.0f;
	slot.box[0] = slot.box[1] = slot.box[2] = 0.0f;
	if (parallax) {
		const mt::vec3 center = probe->GetViewpointObject()->NodeGetWorldPosition();
		slot.center[0] = center.x;
		slot.center[1] = center.y;
		slot.center[2] = center.z;
		slot.radius = probe->GetRadius();
		/* An Empty drawn as Cube gives a box parallax (world axes): half extents = display size * scale. */
		Object *ob = probe->GetViewpointObject()->GetBlenderObject();
		if (ob && ob->type == OB_EMPTY && ob->empty_drawtype == OB_CUBE) {
			const mt::vec3 scale = probe->GetViewpointObject()->NodeGetWorldScaling();
			for (int i = 0; i < 3; i++) {
				slot.box[i] = std::max(fabsf(scale[i]) * ob->empty_drawsize, 1e-3f);
			}
		}
	}
}

bool KX_TextureRendererManager::FindProbe(const float position[3], ProbeSlot r_slots[2], float *r_weight2) const
{
	*r_weight2 = 0.0f;
	if (m_capturing) {
		return false;
	}

	// Score of a probe: 1 at its center, 0 at its radius.
	const mt::vec3 pos(position[0], position[1], position[2]);
	KX_LightProbe *best = nullptr, *second = nullptr;
	float bestScore = 0.0f, secondScore = 0.0f;
	for (KX_LightProbe *probe : m_probes) {
		KX_GameObject *viewpoint = probe->GetViewpointObject();
		if (!viewpoint || !probe->GetCubeTexture() || probe->GetRadius() <= 0.0f) {
			continue;
		}
		const float score = 1.0f - (viewpoint->NodeGetWorldPosition() - pos).Length() / probe->GetRadius();
		if (score <= 0.0f) {
			continue;
		}
		if (!best || score > bestScore) {
			second = best;
			secondScore = bestScore;
			best = probe;
			bestScore = score;
		}
		else if (!second || score > secondScore) {
			second = probe;
			secondScore = score;
		}
	}

	KX_LightProbe *world = (m_worldProbe && m_worldProbe->GetCubeTexture()) ? m_worldProbe : nullptr;
	if (!best) {
		if (!world) {
			return false;
		}
		SetProbeSlot(r_slots[0], world, false);
		return true;
	}

	SetProbeSlot(r_slots[0], best, true);
	/* Near the edge (outer quarter of the radius) the World capture fades in; a neighbor probe takes
	 * over when it scores higher. Both weights are 0 at the switch, so nothing pops. */
	const float worldScore = world ? std::max(0.25f - bestScore, 0.0f) : 0.0f;
	if (second && secondScore >= worldScore) {
		SetProbeSlot(r_slots[1], second, true);
		*r_weight2 = secondScore / (bestScore + secondScore);
	}
	else if (worldScore > 0.0f) {
		SetProbeSlot(r_slots[1], world, false);
		*r_weight2 = worldScore / (bestScore + worldScore);
	}
	return true;
}

float KX_TextureRendererManager::GetProbeVolumeGain(const KX_ProbeVolume *volume) const
{
	// Each lap adds one more bounce; the gain keeps the sum finite.
	return (m_capturingVolume && volume) ? volume->GetBounce() : 1.0f;
}

KX_ProbeVolume *KX_TextureRendererManager::FindProbeVolume(const mt::vec3& aabbMin, const mt::vec3& aabbMax) const
{
	// The manual probes keep their own light; the grid reads itself (bounces).
	if ((m_capturing && !m_capturingVolume) || m_volumes.empty()) {
		return nullptr;
	}
	const mt::vec3 center = (aabbMin + aabbMax) * 0.5f;
	KX_ProbeVolume *best = nullptr;
	float bestWeight = 0.0f;
	for (KX_ProbeVolume *volume : m_volumes) {
		if (!volume->GetViewpointObject()) {
			continue;
		}
		// A box partly inside wins over the fade of a volume next to it (1 + share inside).
		const float overlap = volume->BoxOverlap(aabbMin, aabbMax);
		const float weight = (overlap > 0.0f) ? 1.0f + overlap : volume->BoxWeight(center);
		if (weight > bestWeight) {
			best = volume;
			bestWeight = weight;
		}
	}
	return best;
}

void KX_TextureRendererManager::CheckWorldChanged()
{
	KX_WorldInfo *info = m_scene->GetWorldInfo();
	// The World capture and the probe volumes (idle until the light changes) both follow it.
	if ((!m_worldProbe && m_volumes.empty()) || !info) {
		return;
	}

	// Read from the World info: the Blender World only gets these values later in the frame.
	const mt::vec4& hor = info->getHorizonColor();
	const mt::vec4& zen = info->getZenithColor();
	float sig[16] = {hor[0], hor[1], hor[2], zen[0], zen[1], zen[2],
	                 info->getSunSize(), info->getExposure(), info->getRange()};
	if (KX_LightObject *sun = m_scene->GetWorldSun()) {
		const mt::vec3 dir = sun->NodeGetWorldOrientation().GetColumn(2);
		const RAS_ILightObject *data = sun->GetLightData();
		sig[9] = dir[0];
		sig[10] = dir[1];
		sig[11] = dir[2];
		sig[12] = data->m_color[0];
		sig[13] = data->m_color[1];
		sig[14] = data->m_color[2];
		sig[15] = data->m_energy;
	}

	if (!std::equal(sig, sig + 16, m_worldSignature)) {
		std::copy_n(sig, 16, m_worldSignature);
		if (m_worldProbe) {
			m_worldProbe->ForceUpdate();
		}
		for (KX_ProbeVolume *volume : m_volumes) {
			volume->Wake();
		}
	}
}

bool KX_TextureRendererManager::RenderRenderer(RAS_Rasterizer *rasty, KX_TextureRenderer *renderer,
                                               KX_Camera *sceneCamera, const RAS_Rect& viewport, const RAS_Rect& area,
                                               int firstFace, int numFaces)
{
	KX_GameObject *viewpoint = renderer->GetViewpointObject();
	// The World capture has no viewpoint and draws only the background.
	const bool worldOnly = (renderer == m_worldProbe);
	// A partial capture is scheduled by its probe volume, not by NeedUpdate.
	const bool partial = (numFaces >= 0);
	// Doesn't need (or can) update.
	if ((!partial && !renderer->NeedUpdate()) || !renderer->GetEnabled() || (!viewpoint && !worldOnly)) {
		return false;
	}

	// Set camera setting shared by all the renderer's faces.
	if (!renderer->SetupCamera(sceneCamera, m_camera)) {
		return false;
	}

	if (worldOnly) {
		m_scene->GetWorldInfo()->UpdateBackGround(rasty, m_scene->GetWorldSun());
	}

	const bool visible = viewpoint ? viewpoint->GetVisible() : false;
	/* We hide the viewpoint object in the case backface culling is disabled -> we can't see through
	 * the object faces if the camera is inside the gameobject.
	 */
	if (viewpoint) {
		viewpoint->SetVisible(false, false);
	}

	// Set camera lod distance factor from renderer value.
	m_camera->SetLodDistanceFactor(renderer->GetLodDistanceFactor());

	/* When we update clipstart or clipend values,
	 * or if the projection matrix is not computed yet,
	 * we have to compute projection matrix.
	 */
	const mt::mat4& projmat = renderer->GetProjectionMatrix(rasty, m_scene, sceneCamera, viewport, area);
	m_camera->SetProjectionMatrix(projmat, RAS_Rasterizer::RAS_STEREO_LEFTEYE);
	rasty->SetProjectionMatrix(projmat);

	// Begin rendering stuff
	renderer->BeginRender(rasty);
	KX_TextureRendererEndGuard endRenderGuard(renderer, rasty);

	const int endFace = partial ? std::min(firstFace + numFaces, (int)renderer->GetNumFaces()) : renderer->GetNumFaces();
	for (unsigned short i = firstFace; i < endFace; ++i) {
		// Set camera settings unique per faces.
		if (!renderer->SetupCameraFace(m_camera, i)) {
			continue;
		}

		m_camera->NodeUpdate();

		renderer->BindFace(i);

		const mt::mat3x4 camtrans(m_camera->GetWorldToCamera());
		const mt::mat4 viewmat = mt::mat4::FromAffineTransform(camtrans);

		rasty->SetViewMatrix(viewmat);
		rasty->InvalidateLights();
		m_camera->SetModelviewMatrix(viewmat, RAS_Rasterizer::RAS_STEREO_LEFTEYE);

		// No-op for every renderer except KX_PlanarReflector, which caches it for the material node.
		renderer->SetFrameViewProjection(viewmat, projmat);

		if (worldOnly) {
			renderer->BeginRenderFace(rasty);
			m_scene->GetWorldInfo()->RenderBackground(rasty);
			renderer->EndRenderFace(rasty);
			continue;
		}

		std::vector<KX_GameObject *> objects = m_scene->CalculateVisibleMeshes(m_camera, RAS_Rasterizer::RAS_STEREO_LEFTEYE, ~renderer->GetIgnoreLayers(), false);
		if (partial) {
			// The grid keeps static light: moving physics and deformed meshes stay out.
			objects.erase(std::remove_if(objects.begin(), objects.end(), KX_ProbeVolume::SkipObject), objects.end());
			static_cast<KX_ProbeVolume *>(renderer)->GetStats().objects += (int)objects.size();
		}

		/* Updating the lod per face is normally not expensive because a cube map normally show every objects
		 * but here we update only visible object of a face including the clip end and start.
		 */
		m_scene->UpdateObjectLods(m_camera, objects);

		renderer->BeginRenderFace(rasty);

		// Now the objects are culled and we can render the scene.
		m_scene->GetWorldInfo()->RenderBackground(rasty);
		// Send a nullptr off screen because we use a set of FBO with shared textures, not an off screen.
		m_scene->RenderBuckets(objects, RAS_Rasterizer::RAS_RENDERER, camtrans, rasty, nullptr);

		renderer->EndRenderFace(rasty);
	}

	if (viewpoint) {
		viewpoint->SetVisible(visible, false);
	}
	// The scene camera draws next: its lights must be loaded again in its own view.
	rasty->InvalidateLights();

	return true;
}

void KX_TextureRendererManager::RenderVolumes(RAS_Rasterizer *rasty, KX_Camera *sceneCamera,
                                              const RAS_Rect& viewport, const RAS_Rect& area)
{
	static const bool log = getenv("RANGE_PROBE_VOLUME_LOG") != nullptr;
	static std::chrono::steady_clock::time_point lastLog = std::chrono::steady_clock::now();
	static int logFrames = 0;

	const auto start = std::chrono::steady_clock::now();
	const double now = std::chrono::duration<double>(start.time_since_epoch()).count();
	KX_Camera *activeCam = m_scene->GetActiveCamera();
	const mt::vec3 cameraPos = activeCam ? activeCam->NodeGetWorldPosition() : mt::zero3;

	{
		// The grid stores linear light: the materials skip the display transform while it captures.
		VolumeCaptureGuard captureGuard(m_capturingVolume);
		for (KX_ProbeVolume *volume : m_volumes) {
			if (!volume->GetViewpointObject() || !volume->BeginFrame(cameraPos, now)) {
				continue;
			}
			int left = volume->GetFaceBudget();
			int first, count;
			while (volume->NextFaceRange(left, cameraPos, &first, &count)) {
				RenderRenderer(rasty, volume, sceneCamera, viewport, area, first, count);
				volume->FacesDone(count, now);
				left -= count;
			}
		}
	}

	// The per pixel atlas takes the SH9 read this frame.
	for (KX_ProbeVolume *volume : m_volumes) {
		volume->UpdateAtlas();
	}

	/* Moved objects (doors, lifts, scripted props), checked twice a second: the probes near one that
	 * moved go first. Same filter as the capture, without the camera culling. */
	if (++m_moveCheck >= 30) {
		m_moveCheck = 0;
		for (KX_ProbeVolume *volume : m_volumes) {
			if (!volume->GetViewpointObject()) {
				continue;
			}
			std::vector<KX_GameObject *> objects;
			for (KX_GameObject *gameobj : m_scene->GetObjectList()) {
				if (gameobj->GetMeshList().empty() || !gameobj->GetVisible() ||
				    (gameobj->GetLayer() & volume->GetIgnoreLayers()) || KX_ProbeVolume::SkipObject(gameobj)) {
					continue;
				}
				objects.push_back(gameobj);
			}
			volume->CheckMovedObjects(objects);
		}
	}

	/* The SSGI adds its light over the grid's: weaker with the camera inside a volume, so it doesn't
	 * count twice near the camera. */
	float ssgiScale = 1.0f;
	for (KX_ProbeVolume *volume : m_volumes) {
		if (volume->GetViewpointObject()) {
			const float w = volume->BoxWeight(cameraPos);
			ssgiScale = std::min(ssgiScale, 1.0f + (volume->GetSSGIWeight() - 1.0f) * w);
		}
	}
	m_ssgiScale = ssgiScale;

	const double cpuMs = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
	if (!log) {
		return;
	}
	for (KX_ProbeVolume *volume : m_volumes) {
		volume->GetStats().cpuMs += cpuMs / m_volumes.size();
	}
	logFrames++;
	const double sinceLog = std::chrono::duration<double>(std::chrono::steady_clock::now() - lastLog).count();
	if (sinceLog < 1.0) {
		return;
	}
	for (KX_ProbeVolume *volume : m_volumes) {
		KX_ProbeVolume::Stats& st = volume->GetStats();
		CM_Message("probe volume: " << logFrames << " frames, " << st.faces << " faces, " << st.probesDone <<
		           " probes, cpu " << st.cpuMs / logFrames << " ms/frame, read " << st.readMs / logFrames <<
		           " ms/frame (max " << st.readMaxMs << ", request " << st.requestMs / logFrames << "), objects/face " <<
		           (st.faces ? st.objects / st.faces : 0) << ", reader waits " << st.readerWaits <<
		           ", last cycle " << st.lastCycleSeconds << " s, light " << volume->AverageLight() <<
		           (volume->IsIdle() ? ", idle" : ""));
		const double lastCycle = st.lastCycleSeconds;
		st = KX_ProbeVolume::Stats();
		st.lastCycleSeconds = lastCycle;
	}
	logFrames = 0;
	lastLog = std::chrono::steady_clock::now();
}

void KX_TextureRendererManager::Render(RendererCategory category, RAS_Rasterizer *rasty, RAS_OffScreen *offScreen,
                                       KX_Camera *sceneCamera, const RAS_Rect& viewport, const RAS_Rect& area)
{
	const std::vector<KX_TextureRenderer *>& renderers = m_renderers[category];
	const bool volumes = (category == VIEWPORT_INDEPENDENT && !m_volumes.empty());
	if ((renderers.empty() && !volumes) || rasty->GetDrawingMode() != RAS_Rasterizer::RAS_TEXTURED) {
		return;
	}

	if (category == VIEWPORT_INDEPENDENT) {
		CheckWorldChanged();
	}

	// Disable scissor to not bother with scissor box.
	rasty->Disable(RAS_Rasterizer::RAS_SCISSOR_TEST);

	// Check if at least one renderer was rendered.
	bool rendered = false;
	m_capturing = true;
	for (KX_TextureRenderer *renderer : renderers) {
		rendered |= RenderRenderer(rasty, renderer, sceneCamera, viewport, area);
	}
	if (volumes) {
		RenderVolumes(rasty, sceneCamera, viewport, area);
		// The volume faces unbind the off screen like any capture.
		rendered = true;
	}
	m_capturing = false;

	rasty->Enable(RAS_Rasterizer::RAS_SCISSOR_TEST);

	if (offScreen && rendered) {
		// Restore the off screen bound before rendering the texture renderers.
		offScreen->Bind();
	}
}

void KX_TextureRendererManager::Merge(KX_TextureRendererManager *other)
{
	for (unsigned short i = 0; i < CATEGORY_MAX; ++i) {
		m_renderers[i].insert(m_renderers[i].end(), other->m_renderers[i].begin(), other->m_renderers[i].end());
		other->m_renderers[i].clear();
	}

	m_probes.insert(m_probes.end(), other->m_probes.begin(), other->m_probes.end());
	other->m_probes.clear();
	m_planarReflectors.insert(m_planarReflectors.end(), other->m_planarReflectors.begin(), other->m_planarReflectors.end());
	other->m_planarReflectors.clear();
	m_volumes.insert(m_volumes.end(), other->m_volumes.begin(), other->m_volumes.end());
	other->m_volumes.clear();
	// The merged scene's World capture stays in the renderers list (owned there) but isn't used.
	other->m_worldProbe = nullptr;
}

void KX_TextureRendererManager::InvalidateRenderersProjectionMatrix()
{
	for (unsigned short i = 0; i < CATEGORY_MAX; ++i) {
		for (KX_TextureRenderer* renderer : m_renderers[i]) {
			renderer->InvalidateProjectionMatrix();
		}
	}
	for (KX_ProbeVolume *volume : m_volumes) {
		volume->InvalidateProjectionMatrix();
	}
}
