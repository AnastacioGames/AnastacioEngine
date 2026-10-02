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
#include "KX_Globals.h"
#include "KX_CubeMap.h"
#include "KX_PlanarMap.h"
#include "KX_LightProbe.h"
#include "KX_GameObject.h"
#include "KX_LightObject.h"
#include "KX_WorldInfo.h"

#include "RAS_Rasterizer.h"
#include "RAS_OffScreen.h"
#include "RAS_Texture.h"
#include "RAS_ILightObject.h"

#include "DNA_texture_types.h"
#include "DNA_object_types.h"

#include "CM_Message.h"
#include <algorithm>

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

}  // namespace

KX_TextureRendererManager::KX_TextureRendererManager(KX_Scene *scene)
	:m_scene(scene),
	m_worldProbe(nullptr),
	m_capturing(false)
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

void KX_TextureRendererManager::CheckWorldChanged()
{
	KX_WorldInfo *info = m_scene->GetWorldInfo();
	if (!m_worldProbe || !info) {
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
		m_worldProbe->ForceUpdate();
	}
}

bool KX_TextureRendererManager::RenderRenderer(RAS_Rasterizer *rasty, KX_TextureRenderer *renderer,
                                               KX_Camera *sceneCamera, const RAS_Rect& viewport, const RAS_Rect& area)
{
	KX_GameObject *viewpoint = renderer->GetViewpointObject();
	// The World capture has no viewpoint and draws only the background.
	const bool worldOnly = (renderer == m_worldProbe);
	// Doesn't need (or can) update.
	if (!renderer->NeedUpdate() || !renderer->GetEnabled() || (!viewpoint && !worldOnly)) {
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

	for (unsigned short i = 0; i < renderer->GetNumFaces(); ++i) {
		// Set camera settings unique per faces.
		if (!renderer->SetupCameraFace(m_camera, i)) {
			continue;
		}

		m_camera->NodeUpdate();

		renderer->BindFace(i);

		const mt::mat3x4 camtrans(m_camera->GetWorldToCamera());
		const mt::mat4 viewmat = mt::mat4::FromAffineTransform(camtrans);

		rasty->SetViewMatrix(viewmat);
		m_camera->SetModelviewMatrix(viewmat, RAS_Rasterizer::RAS_STEREO_LEFTEYE);

		if (worldOnly) {
			renderer->BeginRenderFace(rasty);
			m_scene->GetWorldInfo()->RenderBackground(rasty);
			renderer->EndRenderFace(rasty);
			continue;
		}

		const std::vector<KX_GameObject *> objects = m_scene->CalculateVisibleMeshes(m_camera, RAS_Rasterizer::RAS_STEREO_LEFTEYE, ~renderer->GetIgnoreLayers(), false);

		/* Updating the lod per face is normally not expensive because a cube map normally show every objects
		 * but here we update only visible object of a face including the clip end and start.
		 */
		m_scene->UpdateObjectLods(m_camera, objects);

		/* Update animations to use the culling of each faces, BL_ActionManager avoid redundants
		 * updates internally. */
		if (KX_GetActiveEngine()->UpdateAnimations(m_scene)) {
			m_scene->UpdateAnimationDeformers();
		}

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

	return true;
}

void KX_TextureRendererManager::Render(RendererCategory category, RAS_Rasterizer *rasty, RAS_OffScreen *offScreen,
                                       KX_Camera *sceneCamera, const RAS_Rect& viewport, const RAS_Rect& area)
{
	const std::vector<KX_TextureRenderer *>& renderers = m_renderers[category];
	if (renderers.empty() || rasty->GetDrawingMode() != RAS_Rasterizer::RAS_TEXTURED) {
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
}
