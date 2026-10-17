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

/** \file KX_RenderPipeline.cpp
 *  \ingroup ketsji
 */

#include <cfloat>
#include <cmath>

#include "KX_RenderPipeline.h"
#include "KX_KetsjiEngine.h"

#include "EXP_ListValue.h"

#include "RAS_Rasterizer.h"
#include "RAS_ICanvas.h"
#include "RAS_OffScreen.h"
#include "RAS_FramingManager.h"
#include "DNA_scene_types.h"
#include "DNA_world_types.h"
#include "DNA_lamp_types.h" // LA_SHADMAP_VARIANCE
#include "RAS_ILightObject.h"
#include <algorithm>
#include <vector>
#include "KX_RainAura.h"
#include "KX_RainSurfaceMask.h"
#include "KX_RainLightning.h"
#include "KX_VFogGlow.h"
#include "RAS_ParticleBuffer.h" // Per-object GPU particle emitters, see KX_GameObject::GetParticleBuffer.
#include "GPU_texture.h"

#include "KX_Camera.h"
#include "KX_GameObject.h"
#include "KX_Globals.h"
#include "KX_LightObject.h"
#include "KX_Scene.h"
#include "KX_WorldInfo.h"
#include "KX_2DFilterManager.h"
#include "RAS_2DFilter.h"
#include "KX_ShadowRenderer.h"
#include "KX_DebugRenderer.h"

#include "PHY_IPhysicsEnvironment.h"

#include "CM_RefCount.h"

#include "GPU_glew.h"

#include "KX_EngineProfiler.h"

#include <chrono>
#include <memory>


KX_CameraRenderData::KX_CameraRenderData(KX_Camera *rendercam, KX_Camera *cullingcam, const RAS_Rect& area,
                                          const RAS_Rect& viewport, RAS_Rasterizer::StereoMode stereoMode, RAS_Rasterizer::StereoEye eye)
	:m_renderCamera(rendercam),
	m_cullingCamera(cullingcam),
	m_area(area),
	m_viewport(viewport),
	m_stereoMode(stereoMode),
	m_eye(eye)
{
	m_renderCamera->AddRef();
}

KX_CameraRenderData::KX_CameraRenderData(const KX_CameraRenderData& other)
	:m_renderCamera(CM_AddRef(other.m_renderCamera)),
	m_cullingCamera(other.m_cullingCamera),
	m_area(other.m_area),
	m_viewport(other.m_viewport),
	m_stereoMode(other.m_stereoMode),
	m_eye(other.m_eye)
{
}

KX_CameraRenderData::~KX_CameraRenderData()
{
	m_renderCamera->Release();
}

KX_SceneRenderData::KX_SceneRenderData(KX_Scene *scene)
	:m_scene(scene)
{
}

KX_FrameRenderData::KX_FrameRenderData(RAS_OffScreen::Type ofsType)
	:m_ofsType(ofsType)
{
}

KX_RenderData::KX_RenderData(RAS_Rasterizer::StereoMode stereoMode, bool renderPerEye)
	:m_stereoMode(stereoMode),
	m_renderPerEye(renderPerEye)
{
}

KX_RenderPipeline::KX_RenderPipeline(KX_KetsjiEngine *engine)
	:m_engine(engine)
{
}

/* Volumetric Fog per frame data (layout in gpu_shader_vfog_lib.glsl): World settings, the sun,
 * the strongest Point/Spot lamps around the camera, up to 2 Spot shadow maps for the light
 * shafts and up to 4 Fog Volumes (objects with the game property "fog_volume"). */
static void KX_FillVolumetricFog(BuildInFilters *params, KX_Scene *scene, const World *world, float time,
                                 const mt::vec3& camPos)
{
	float *d = params->vfog_data;
	std::fill(d, d + BuildInFilters::VFOG_DATA_VEC4 * 4, 0.0f);
	std::fill(params->vfog_mats, params->vfog_mats + 16 * BuildInFilters::VFOG_MATS, 0.0f);
	std::fill(params->vfog_shadow_tex, params->vfog_shadow_tex + BuildInFilters::VFOG_SHADOWS, 0u);
	std::fill(params->vfog_shadow_color_tex, params->vfog_shadow_color_tex + BuildInFilters::VFOG_SHADOWS, 0u);

	/* Morning Fog: denser and lower around dawn (World Property sun_hour, peak at 6h). */
	float morning = 0.0f;
	if (world->vfog_flag & WO_VFOG_TIME_OF_DAY) {
		float hour = 12.0f;
		if (KX_WorldInfo *info = scene->GetWorldInfo()) {
			if (EXP_Value *prop = info->GetProperty("sun_hour")) {
				hour = (float)prop->GetNumber();
			}
		}
		hour = std::fmod(hour, 24.0f);
		if (hour < 0.0f) {
			hour += 24.0f;
		}
		const float x = (hour - 6.0f) / 1.5f;
		morning = std::exp(-x * x);
	}

	const int quality = std::max(0, std::min<int>(world->vfog_quality, 2));
	d[0] = world->vfog_density * (1.0f + world->vfog_morning_boost * morning);
	d[1] = world->vfog_base;
	d[2] = std::max(world->vfog_falloff * (1.0f - 0.5f * morning), 0.01f);
	d[3] = std::max(world->vfog_distance, 1.0f);
	d[4] = world->vfog_noise_scale;
	d[5] = world->vfog_noise_amount;
	d[6] = (float)std::fmod((double)time * world->vfog_speed, 10000.0);
	d[7] = world->vfog_anisotropy;
	d[8] = world->vfog_color[0];
	d[9] = world->vfog_color[1];
	d[10] = world->vfog_color[2];
	d[11] = (float)quality;
	if (KX_LightObject *sun = scene->GetWorldSun()) {
		const mt::vec3 sunDir = sun->NodeGetWorldOrientation().GetColumn(2).Normalized();
		const RAS_ILightObject *data = sun->GetLightData();
		const float sunHeight = std::max(0.0f, std::min(1.0f, (sunDir.z + 0.05f) / 0.15f));
		const float sunVisible = sunHeight * sunHeight * (3.0f - 2.0f * sunHeight);
		d[12] = sunDir.x;
		d[13] = sunDir.y;
		d[14] = sunDir.z;
		d[15] = 1.0f;
		for (int i = 0; i < 3; ++i) {
			d[16 + i] = data->m_color[i] * std::min(data->m_energy, 4.0f) * world->vfog_sun_intensity * sunVisible;
		}
	}
	/* Keep a small fog-colored self-illumination floor, independent of the horizon. */
	d[20] = (world->horr + world->vfog_color[0] * 0.06f) * world->vfog_ambient;
	d[21] = (world->horg + world->vfog_color[1] * 0.06f) * world->vfog_ambient;
	d[22] = (world->horb + world->vfog_color[2] * 0.06f) * world->vfog_ambient;
	/* Layer shape and the haze up to the clouds (Volumetric Clouds altitude, else 300 m). */
	d[19] = (world->vfog_flag & WO_VFOG_LAYER) ? 1.0f : 0.0f;
	if (world->vfog_flag & WO_VFOG_REACH_CLOUDS) {
		d[23] = (world->vcloud_flag & WO_VCLOUDS_ENABLE) ? std::max(world->vcloud_altitude, world->vfog_base + 1.0f) :
		                                                  std::max(300.0f, world->vfog_base + 1.0f);
	}
	d[26] = world->vfog_light_intensity;
	d[27] = (world->vfog_flag & WO_VFOG_VOLUMES_ONLY) ? 1.0f : 0.0f;
	d[32] = world->vfog_edge;
	d[33] = world->vfog_shaft_intensity;

	/* Wind: the noise is carried along the heading vfog_wind_dir, at Rain Wind * 20 m/s. */
	if (world->vfog_flag & WO_VFOG_WIND) {
		const float angle = world->vfog_wind_dir * 0.017453292f;
		const float travel = (float)std::fmod((double)time * world->rain_wind * 20.0, 10000.0);
		d[36] = std::cos(angle) * travel;
		d[37] = std::sin(angle) * travel;
	}
	d[38] = std::fmod(time, 10000.0f);

	/* Sun shafts: the Sun's farthest shadow map (Medium/High). */
	if ((world->vfog_flag & WO_VFOG_SUN_SHAFTS) && quality > 0 && d[15] > 0.5f) {
		int code = 0;
		mt::mat4 mat;
		RAS_ILightObject *sunData = scene->GetWorldSun()->GetLightData();
		if (sunData->GetFarShadow(code, mat)) {
			params->vfog_shadow_tex[2] = (unsigned int)code;
			mat.Pack(params->vfog_mats + 16 * 6);
			d[34] = 0.001f;
			d[35] = 1.0f;
			/* Shafts tinted by the Colored Shadows casters (glass, stained glass). */
			const int color = sunData->GetShadowColorBindCode();
			if (color > 0) {
				params->vfog_shadow_color_tex[2] = (unsigned int)color;
				d[35] = 2.0f;
			}
		}
	}

	/* Fog Volumes: unit box (the default cube) or sphere of the object, world -> local; optional
	 * game properties fog_shape ("sphere"), fog_edge, fog_smoke (local rise speed in m/s) and fog_fire
	 * (temperature 0..1), tint from the object color. */
	int volumes = 0;
	for (KX_GameObject *gameobj : *scene->GetObjectList()) {
		if (volumes >= 4) {
			break;
		}
		EXP_Value *prop = gameobj->GetProperty("fog_volume");
		if (!prop) {
			continue;
		}
		const mt::mat4 inv = mt::mat4::FromAffineTransform(gameobj->NodeGetWorldTransform()).Inverse();
		inv.Pack(params->vfog_mats + 16 * volumes);
		d[28 + volumes] = std::max(0.0f, (float)prop->GetNumber());
		EXP_Value *shape = gameobj->GetProperty("fog_shape");
		d[40 + volumes] = (shape && shape->GetText() == "sphere") ? 1.0f : 0.0f;
		EXP_Value *edge = gameobj->GetProperty("fog_edge");
		d[44 + volumes] = edge ? std::max(0.0f, std::min(1.0f, (float)edge->GetNumber())) : world->vfog_edge;
		EXP_Value *smoke = gameobj->GetProperty("fog_smoke");
		d[4 * (48 + volumes)] = smoke ? std::max(0.0f, (float)smoke->GetNumber()) : 0.0f;
		EXP_Value *fire = gameobj->GetProperty("fog_fire");
		d[4 * (48 + volumes) + 1] = fire ? std::max(0.0f, std::min(1.0f, (float)fire->GetNumber())) : 0.0f;
		const mt::vec4& col = gameobj->GetObjectColor();
		float *c = d + 4 * (44 + volumes);
		if (col.x < 0.999f || col.y < 0.999f || col.z < 0.999f) {
			c[0] = col.x;
			c[1] = col.y;
			c[2] = col.z;
			c[3] = 1.0f;
		}
		++volumes;
	}
	d[25] = (float)volumes;

	/* Fog pushers: objects with the game property fog_push (radius in m) open a hole in the fog. */
	int pushers = 0;
	for (KX_GameObject *gameobj : *scene->GetObjectList()) {
		if (pushers >= 4) {
			break;
		}
		EXP_Value *push = gameobj->GetProperty("fog_push");
		const float radius = push ? (float)push->GetNumber() : 0.0f;
		if (radius <= 0.0f) {
			continue;
		}
		const mt::vec3& pos = gameobj->NodeGetWorldPosition();
		float *p = d + 4 * (52 + pushers);
		p[0] = pos.x;
		p[1] = pos.y;
		p[2] = pos.z;
		p[3] = radius;
		++pushers;
	}
	d[39] = (float)pushers;
	d[4 * 56] = (quality > 0) ? world->vfog_dust : 0.0f;

	/* Lamps: strongest at the camera first, only the ones whose reach gets near the fogged part. */
	int lampCount = 0;
	if (world->vfog_flag & WO_VFOG_LAMPS) {
		static const int presetMax[3] = {2, 4, 8};
		const int maxLamps = std::max(1, std::min<int>(std::min<int>(world->vfog_max_lights, 8), presetMax[quality]));
		/* A candidate is a real lamp or a glowing object (fog_glow) seen as a Point lamp. */
		struct Candidate {
			KX_LightObject *light;
			const KX_VFogGlow *glow;
			float score;
		};
		std::vector<Candidate> candidates;
		const float reach = d[3];
		static std::vector<KX_VFogGlow> glows;
		KX_VFogCollectGlows(scene, camPos, reach, glows);
		for (const KX_VFogGlow& glow : glows) {
			candidates.push_back({nullptr, &glow, glow.score});
		}
		for (KX_LightObject *light : *scene->GetLightList()) {
			RAS_ILightObject *data = light->GetLightData();
			if (!light->GetVisible() || data->m_energy <= 0.0f ||
			    (data->m_type != RAS_ILightObject::LIGHT_NORMAL && data->m_type != RAS_ILightObject::LIGHT_SPOT))
			{
				continue;
			}
			const float dist = (light->NodeGetWorldPosition() - camPos).Length();
			if (dist > reach + data->m_distance) {
				continue;
			}
			const float r = std::max(data->m_distance, 0.01f);
			candidates.push_back({light, nullptr, data->m_energy * r * r / (r * r + dist * dist)});
		}
		std::sort(candidates.begin(), candidates.end(),
		          [](const Candidate& a, const Candidate& b) { return a.score > b.score; });
		int shadows = 0;
		for (const Candidate& c : candidates) {
			if (lampCount >= maxLamps) {
				break;
			}
			float *l = d + 4 * (12 + 4 * lampCount);
			if (c.glow) {
				l[0] = c.glow->position.x;
				l[1] = c.glow->position.y;
				l[2] = c.glow->position.z;
				l[3] = c.glow->radius;
				l[4] = c.glow->color.x;
				l[5] = c.glow->color.y;
				l[6] = c.glow->color.z;
				l[7] = -1.0f;
				l[11] = -2.0f;
				++lampCount;
				continue;
			}
			RAS_ILightObject *data = c.light->GetLightData();
			const mt::vec3& pos = c.light->NodeGetWorldPosition();
			l[0] = pos.x;
			l[1] = pos.y;
			l[2] = pos.z;
			l[3] = data->m_distance;
			for (int i = 0; i < 3; ++i) {
				l[4 + i] = data->m_color[i] * data->m_energy;
			}
			l[7] = -1.0f;
			l[11] = -2.0f;
			if (data->m_type == RAS_ILightObject::LIGHT_SPOT) {
				/* Blender spots point down their -Z; same cone/blend as the lamp shading. */
				const mt::vec3 dir = -c.light->NodeGetWorldOrientation().GetColumn(2).Normalized();
				const float cosOuter = std::cos(data->m_spotsize * 0.5f);
				l[8] = dir.x;
				l[9] = dir.y;
				l[10] = dir.z;
				l[11] = cosOuter;
				l[12] = cosOuter + (1.0f - cosOuter) * data->m_spotblend;
				/* Light shafts: shadow map of up to 2 Spot lamps (Variance maps are color textures). */
				if ((world->vfog_flag & WO_VFOG_SHAFTS) && quality > 0 && shadows < 2 && data->HasShadowBuffer() &&
				    data->m_shadowmaptype != LA_SHADMAP_VARIANCE)
				{
					const int code = data->GetShadowBindCode();
					if (code > 0) {
						params->vfog_shadow_tex[shadows] = (unsigned int)code;
						data->GetShadowWorldMatrix().Pack(params->vfog_mats + 16 * (4 + shadows));
						l[7] = (float)shadows;
						l[13] = 0.0005f;
						const int color = data->GetShadowColorBindCode();
						if (color > 0) {
							params->vfog_shadow_color_tex[shadows] = (unsigned int)color;
							l[14] = 1.0f;
						}
						++shadows;
					}
				}
			}
			++lampCount;
		}
	}
	d[24] = (float)lampCount;
}

void KX_RenderPipeline::Render()
{
	if (m_engine->NeedsRender()) {

		// Cleared per frame: cached results are only valid while cullingcam/eye pairs refer to
		// this frame's camera transforms (see GetVisibleMeshes doc comment on the header).
		m_visibleMeshCache.clear();

		m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_rasterizer);

		KX_EngineProfiler::BeginGpuFrame();
		KX_EngineProfiler::Sections prof;
		m_engine->BeginFrame();

		// Advance once before visiting any scene/light so the entire frame sees the same
		// startup state.
		if (!m_engine->IsStaticShadowSettled() && m_engine->GetShadowCulling() &&
		    m_engine->GetRasterizer()->GetDrawingMode() == RAS_Rasterizer::RAS_TEXTURED) {
			m_engine->IncrementStaticSplitSettleFrames();
		}

		RAS_Rasterizer *rasterizer = m_engine->GetRasterizer();
		RAS_ICanvas *canvas = m_engine->GetCanvas();

		// Plano 9, unidade 1: só empurra o valor para o driver (GHOST_SetSwapInterval) quando ele
		// muda desde a última vez que aplicamos, em vez de repetir a chamada todo frame com o
		// mesmo valor.
		RAS_ICanvas::SwapControl requestedSwapControl = canvas->GetSwapControl();
		if (requestedSwapControl != m_lastAppliedSwapControl) {
			canvas->SetSwapControl(requestedSwapControl);
			m_lastAppliedSwapControl = requestedSwapControl;
		}

		EXP_ListValue<KX_Scene> *scenes = m_engine->GetScenes();

		RANGE_PROFILE_MARK_GPU(prof, "render.begin");

		for (KX_Scene *scene : scenes) {
			// shadow buffers
			m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_shadows);
			m_engine->GetShadowRenderer()->Render(scene);
			// GPU particle Screen-Space collision depth pass (objects flagged
			// use_gpu_particle_collider), independent of shadow buffers above.
			m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_collisiondepth);
			RenderCollisionDepthBuffer(scene);
			m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_texturerenderers);
			// Render only independent texture renderers here.
			scene->RenderTextureRenderers(KX_TextureRendererManager::VIEWPORT_INDEPENDENT, rasterizer, nullptr, nullptr, RAS_Rect(), RAS_Rect());
			m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_rasterizer);
		}

		RANGE_PROFILE_MARK_GPU(prof, "render.shadows");

		KX_RenderData renderData = GetRenderData();

		const int width = canvas->GetWidth();
		const int height = canvas->GetHeight();
		// clear the entire game screen with the border color
		// only once per frame
		rasterizer->SetViewport(0, 0, width, height);
		rasterizer->SetScissor(0, 0, width, height);

		KX_Scene *firstscene = scenes->GetFront();
		const RAS_FrameSettings &framesettings = firstscene->GetFramingType();
		// Use the framing bar color set in the Blender scenes
		rasterizer->SetClearColor(framesettings.BarRed(), framesettings.BarGreen(), framesettings.BarBlue(), 1.0f);

		// Used to detect when a camera is the first rendered an then doesn't request a depth clear.
		unsigned short pass = 0;

		for (KX_FrameRenderData& frameData : renderData.m_frameDataList) {
			// Current bound off screen.
			RAS_OffScreen *offScreen = canvas->GetOffScreen(frameData.m_ofsType);
			offScreen->Bind();

			// Clear off screen only before the first scene render.
			rasterizer->Clear(RAS_Rasterizer::RAS_COLOR_BUFFER_BIT | RAS_Rasterizer::RAS_DEPTH_BUFFER_BIT);

			// for each scene, call the proceed functions
			for (unsigned short i = 0, size = frameData.m_sceneDataList.size(); i < size; ++i) {
				const KX_SceneRenderData& sceneFrameData = frameData.m_sceneDataList[i];
				KX_Scene *scene = sceneFrameData.m_scene;

				const bool isfirstscene = (i == 0);
				const bool islastscene = (i == (size - 1));

				// pass the scene's worldsettings to the rasterizer
				scene->GetWorldInfo()->UpdateWorldSettings(rasterizer);

				rasterizer->SetAuxilaryClientInfo(scene);

				// Draw the scene once for each camera with an enabled viewport or an active camera.
				for (const KX_CameraRenderData& cameraFrameData : sceneFrameData.m_cameraDataList) {
					// do the rendering
					RenderCamera(scene, cameraFrameData, offScreen, pass++, isfirstscene);
				}

				RANGE_PROFILE_MARK_GPU(prof, "render.cameras");

				/* Choose final render off screen target. If the current off screen is using multisamples we
				 * are sure that it will be copied to a non-multisamples off screen before render the filters.
				 * In this case the targeted off screen is the same as the current off screen. */
				RAS_OffScreen::Type target;
				if (offScreen->GetSamples() > 0) {
					/* If the last scene is rendered it's useless to specify a multisamples off screen, we use then
					 * a non-multisamples off screen and avoid an extra off screen blit. */
					if (islastscene) {
						target = RAS_OffScreen::NextRenderOffScreen(frameData.m_ofsType);
					}
					else {
						target = frameData.m_ofsType;
					}
				}
				/* In case of non-multisamples a ping pong per scene render is made between a potentially multisamples
				 * off screen and a non-multisamples off screen as the both doesn't use multisamples. */
				else {
					target = RAS_OffScreen::NextRenderOffScreen(frameData.m_ofsType);
				}

				// Render filters and get output off screen.
				offScreen = PostRenderScene(scene, offScreen, canvas->GetOffScreen(target));
				frameData.m_ofsType = offScreen->GetType();

				RANGE_PROFILE_MARK_GPU(prof, "render.filters");
			}
		}

		canvas->SetViewPort(0, 0, width, height);

		/* VR lens distortion: only for side by side, where both eyes share the final off screen. */
		const bool vrLens = (renderData.m_stereoMode == RAS_Rasterizer::RAS_STEREO_SIDEBYSIDE) &&
		                    (firstscene->GetBlenderScene()->gm.flag & GAME_VR_LENS_DISTORTION);
		rasterizer->SetVRLensDistortion(vrLens ? rasterizer->GetVRLensStrength() : 0.0f);
		{
			KX_Camera *cam = firstscene->GetActiveCamera();
			const bool sideBySide = (renderData.m_stereoMode == RAS_Rasterizer::RAS_STEREO_SIDEBYSIDE);
			rasterizer->SetVRVignette((sideBySide && cam) ? cam->GetVRVignette() : 0.0f);
		}

		// Compositing per eye off screens to screen.
		if (renderData.m_renderPerEye) {
			RAS_OffScreen *leftofs = canvas->GetOffScreen(renderData.m_frameDataList[0].m_ofsType);
			RAS_OffScreen *rightofs = canvas->GetOffScreen(renderData.m_frameDataList[1].m_ofsType);
			rasterizer->DrawStereoOffScreen(canvas, leftofs, rightofs, renderData.m_stereoMode);
		}
		// Else simply draw the off screen to screen.
		else {
			rasterizer->DrawOffScreen(canvas, canvas->GetOffScreen(renderData.m_frameDataList[0].m_ofsType));
		}
		RANGE_PROFILE_MARK_GPU(prof, "render.present");
	}

	RANGE_PROFILE_SCOPE("render.endframe");
	m_engine->EndFrame();
}

namespace {
/// Restores the off screen that was bound before RenderCollisionDepthBuffer ran, on scope
/// exit, so a future early return added between the bind and the end of the function can't
/// leave the wrong off screen bound for the rest of the frame (see RenderShadowBuffers'
/// analogous viewport-restore bug, fixed above, for the kind of symptom this class of bug
/// causes).
class KX_OffScreenRestoreGuard
{
	RAS_OffScreen *m_previous;

public:
	explicit KX_OffScreenRestoreGuard(RAS_OffScreen *previous) : m_previous(previous) {}
	~KX_OffScreenRestoreGuard()
	{
		if (m_previous) {
			m_previous->Bind();
		}
		else {
			RAS_OffScreen::RestoreScreen();
		}
	}
};
}  // namespace

void KX_RenderPipeline::RenderCollisionDepthBuffer(KX_Scene *scene)
{
	const std::vector<KX_GameObject *>& colliders = scene->GetGpuParticleColliderObjects();
	if (colliders.empty()) {
		return;
	}

	KX_Camera *viewcam = scene->GetActiveCamera();
	if (!viewcam) {
		return;
	}

	RAS_Rasterizer *rasterizer = m_engine->GetRasterizer();
	rasterizer->SetAuxilaryClientInfo(scene);

	RAS_OffScreen *previousOffScreen = RAS_OffScreen::GetLastOffScreen();
	KX_OffScreenRestoreGuard restoreGuard(previousOffScreen);
	RAS_OffScreen *offScreen = m_engine->GetCanvas()->GetOffScreen(RAS_OffScreen::RAS_OFFSCREEN_COLLISION_DEPTH);
	offScreen->Bind();

	// RenderShadowBuffers (called right before this) leaves the canvas viewport sized to the
	// last shadow map it bound (e.g. a square 1024x1024) -- UnbindShadowBuffer() never restores
	// it. Without resetting it here, this pass rasterizes into a viewport that doesn't match the
	// offscreen's actual dimensions, which desyncs the screen-space UV the particle collision
	// shader computes from world position against what's actually written in the texture --
	// symptom observed in-game: colliders reading several meters off from their real position.
	rasterizer->SetViewport(0, 0, offScreen->GetWidth(), offScreen->GetHeight());
	rasterizer->SetScissor(0, 0, offScreen->GetWidth(), offScreen->GetHeight());

	rasterizer->Clear(RAS_Rasterizer::RAS_DEPTH_BUFFER_BIT);

	const mt::mat4 projmat = viewcam->GetProjectionMatrix(RAS_Rasterizer::RAS_STEREO_LEFTEYE);
	const mt::mat4 viewmat = viewcam->GetModelviewMatrix(RAS_Rasterizer::RAS_STEREO_LEFTEYE);
	rasterizer->SetProjectionMatrix(projmat);
	rasterizer->SetViewMatrix(viewmat, viewcam->NodeGetWorldScaling());

	scene->RenderBuckets(colliders, RAS_Rasterizer::RAS_COLLISION_DEPTH, viewcam->GetWorldToCamera(), rasterizer, offScreen);

	GPU_texture_set_global_collider_depth(offScreen->GetDepthTexture());
	const mt::mat4 viewproj = projmat * viewmat;
	GPU_texture_set_global_collider_depth_viewproj((const float *)viewproj.Data());
}

KX_CameraRenderData KX_RenderPipeline::GetCameraRenderData(KX_Scene *scene, KX_Camera *camera, KX_Camera *overrideCullingCam,
                                                            const RAS_Rect& displayArea, RAS_Rasterizer::StereoMode stereoMode, RAS_Rasterizer::StereoEye eye)
{
	KX_Camera *rendercam;
	/* In case of stereo we must copy the camera because it is used twice with different settings
	 * (modelview matrix). This copy use the same transform settings that the original camera
	 * and its name is based on with the eye number in addition.
	 */
	const bool usestereo = (stereoMode != RAS_Rasterizer::RAS_STEREO_NOSTEREO);
	if (usestereo) {
		rendercam = new KX_Camera(scene, KX_Scene::m_callbacks, *camera->GetCameraData(), true);
		rendercam->SetName("__stereo_" + camera->GetName() + "_" + std::to_string(eye) + "__");
		rendercam->NodeSetGlobalOrientation(camera->NodeGetWorldOrientation());
		rendercam->NodeSetWorldPosition(camera->NodeGetWorldPosition());
		rendercam->NodeSetWorldScale(camera->NodeGetWorldScaling());
		rendercam->CopyHeadView(camera);
		rendercam->NodeUpdate();
	}
	// Else use the native camera.
	else {
		rendercam = camera;
	}

	KX_Camera *cullingcam = (overrideCullingCam) ? overrideCullingCam : rendercam;

	KX_SetActiveScene(scene);
#ifdef WITH_PYTHON
	scene->RunDrawingCallbacks(KX_Scene::PRE_DRAW_SETUP, rendercam);
#endif

	RAS_Rect area;
	RAS_Rect viewport;
	// Compute the area and the viewport based on the current display area and the optional camera viewport.
	m_engine->GetSceneViewport(scene, rendercam, displayArea, area, viewport);
	// Compute the camera matrices: modelview and projection.
	rendercam->UpdateView(m_engine->GetRasterizer(), scene, stereoMode, eye, viewport, area);

	KX_CameraRenderData cameraData(rendercam, cullingcam, area, viewport, stereoMode, eye);

	if (usestereo) {
		rendercam->Release();
	}

	return cameraData;
}

KX_RenderData KX_RenderPipeline::GetRenderData()
{
	RAS_Rasterizer *rasterizer = m_engine->GetRasterizer();

	const RAS_Rasterizer::StereoMode stereomode = rasterizer->GetStereoMode();
	const bool usestereo = (stereomode != RAS_Rasterizer::RAS_STEREO_NOSTEREO);
	// Set to true when each eye needs to be rendered in a separated off screen.
	const bool renderpereye = stereomode == RAS_Rasterizer::RAS_STEREO_INTERLACED ||
	                          stereomode == RAS_Rasterizer::RAS_STEREO_VINTERLACE ||
	                          stereomode == RAS_Rasterizer::RAS_STEREO_ANAGLYPH;

	KX_RenderData renderData(stereomode, renderpereye);

	// The number of eyes to manage in case of stereo.
	const unsigned short numeyes = (usestereo) ? 2 : 1;
	// The number of frames in case of stereo, could be multiple for interlaced or anaglyph stereo.
	const unsigned short numframes = (renderpereye) ? 2 : 1;

	// The off screen corresponding to the frame.
	static const RAS_OffScreen::Type ofsType[] = {
		RAS_OffScreen::RAS_OFFSCREEN_EYE_LEFT0,
		RAS_OffScreen::RAS_OFFSCREEN_EYE_RIGHT0
	};

	// Pre-compute the display area used for stereo or normal rendering.
	// Fixed-size arrays: at most 2 eyes, avoids per-frame heap allocations.
	RAS_Rect displayAreas[2];
	for (unsigned short eye = 0; eye < numeyes; ++eye) {
		displayAreas[eye] = rasterizer->GetRenderArea(m_engine->GetCanvas(), stereomode, (RAS_Rasterizer::StereoEye)eye);
	}

	EXP_ListValue<KX_Scene> *scenes = m_engine->GetScenes();

	// Prepare override culling camera of each scenes, we don't manage stereo currently.
	for (KX_Scene *scene : scenes) {
		KX_Camera *overrideCullingCam = scene->GetOverrideCullingCamera();

		if (overrideCullingCam) {
			RAS_Rect area;
			RAS_Rect viewport;
			// Compute the area and the viewport based on the current display area and the optional camera viewport.
			m_engine->GetSceneViewport(scene, overrideCullingCam, displayAreas[RAS_Rasterizer::RAS_STEREO_LEFTEYE], area, viewport);
			// Compute the camera matrices: modelview and projection.
			overrideCullingCam->UpdateView(rasterizer, scene, stereomode, RAS_Rasterizer::RAS_STEREO_LEFTEYE, viewport, area);
		}
	}

	for (unsigned short frame = 0; frame < numframes; ++frame) {
		renderData.m_frameDataList.emplace_back(ofsType[frame]);
		KX_FrameRenderData& frameData = renderData.m_frameDataList.back();

		// Get the eyes managed per frame.
		RAS_Rasterizer::StereoEye eyes[2];
		unsigned short numframeeyes;
		// One eye per frame but different.
		if (renderpereye) {
			eyes[0] = (RAS_Rasterizer::StereoEye)frame;
			numframeeyes = 1;
		}
		// Two eyes for unique frame.
		else if (usestereo) {
			eyes[0] = RAS_Rasterizer::RAS_STEREO_LEFTEYE;
			eyes[1] = RAS_Rasterizer::RAS_STEREO_RIGHTEYE;
			numframeeyes = 2;
		}
		// Only one eye for unique frame.
		else {
			eyes[0] = RAS_Rasterizer::RAS_STEREO_LEFTEYE;
			numframeeyes = 1;
		}

		for (KX_Scene *scene : scenes) {
			frameData.m_sceneDataList.emplace_back(scene);
			KX_SceneRenderData& sceneFrameData = frameData.m_sceneDataList.back();

			KX_Camera *activecam = scene->GetActiveCamera();
			KX_Camera *overrideCullingCam = scene->GetOverrideCullingCamera();
			for (KX_Camera *cam : scene->GetCameraList()) {
				if (cam != activecam && !cam->UseViewport()) {
					continue;
				}

				for (unsigned short i = 0; i < numframeeyes; ++i) {
					const RAS_Rasterizer::StereoEye eye = eyes[i];
					sceneFrameData.m_cameraDataList.push_back(GetCameraRenderData(scene, cam, overrideCullingCam, displayAreas[eye],
					                                                              stereomode, eye));
				}
			}
		}
	}

	return renderData;
}

const std::vector<KX_GameObject *>& KX_RenderPipeline::GetVisibleMeshes(KX_Scene *scene, KX_Camera *cullingcam, RAS_Rasterizer::StereoEye eye)
{
	for (const auto& entry : m_visibleMeshCache) {
		if (entry.first.first == cullingcam && entry.first.second == eye) {
			return entry.second;
		}
	}

	std::vector<KX_GameObject *> objects = scene->CalculateVisibleMeshes(cullingcam, eye, 0, false);
	scene->UpdateObjectLods(cullingcam, objects);

	m_visibleMeshCache.emplace_back(std::make_pair(cullingcam, eye), std::move(objects));
	return m_visibleMeshCache.back().second;
}

// update graphics
namespace {
/// Profiler on: names a camera render phase slow enough to be a hitch, in the spike log.
struct SlowPhaseNote
{
	const char *phase;
	KX_Scene *scene;
	const bool on = KX_EngineProfiler::Enabled();
	std::chrono::steady_clock::time_point start;
	SlowPhaseNote(const char *p, KX_Scene *s) : phase(p), scene(s)
	{
		if (on) {
			start = std::chrono::steady_clock::now();
		}
	}
	~SlowPhaseNote()
	{
		if (!on) {
			return;
		}
		const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
		if (ms >= 3.0) {
			char buf[32];
			snprintf(buf, sizeof(buf), "=%.0fms", ms);
			KX_EngineProfiler::Note(std::string(phase) + "(" + scene->GetName() + ")" + buf);
		}
	}
};
}

void KX_RenderPipeline::RenderCamera(KX_Scene *scene, const KX_CameraRenderData& cameraFrameData, RAS_OffScreen *offScreen,
                                      unsigned short pass, bool isFirstScene)
{
	KX_Camera *rendercam = cameraFrameData.m_renderCamera;
	KX_Camera *cullingcam = cameraFrameData.m_cullingCamera;
	const RAS_Rect &area = cameraFrameData.m_area;
	const RAS_Rect &viewport = cameraFrameData.m_viewport;

	RAS_Rasterizer *rasterizer = m_engine->GetRasterizer();

	KX_SetActiveScene(scene);

	/* Render texture probes depending of the the current viewport and area, these texture probes are commonly the planar map
	 * which need to be recomputed by each view in case of multi-viewport or stereo.
	 */
	m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_texturerenderers);
	{ SlowPhaseNote note("cam.texrenderers", scene); scene->RenderTextureRenderers(KX_TextureRendererManager::VIEWPORT_DEPENDENT, rasterizer, offScreen, rendercam, viewport, area); }
	m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_rasterizer);

	// set the viewport for this frame and scene
	const int left = viewport.GetLeft();
	const int bottom = viewport.GetBottom();
	const int width = viewport.GetWidth();
	const int height = viewport.GetHeight();
	rasterizer->SetViewport(left, bottom, width, height);
	rasterizer->SetScissor(left, bottom, width, height);

	/* Clear the depth after setting the scene viewport/scissor
	 * if it's not the first render pass. */
	if (pass > 0) {
		rasterizer->Clear(RAS_Rasterizer::RAS_DEPTH_BUFFER_BIT);
	}

	RAS_Rasterizer::StereoEye eye = cameraFrameData.m_eye;
	rasterizer->SetEye(eye);

	rasterizer->SetProjectionMatrix(rendercam->GetProjectionMatrix(eye));
	rasterizer->SetViewMatrix(rendercam->GetModelviewMatrix(eye), rendercam->NodeGetWorldScaling());

	if (isFirstScene) {
		KX_WorldInfo *worldInfo = scene->GetWorldInfo();
		// Update background and render it.
		worldInfo->UpdateBackGround(rasterizer, scene->GetWorldSun());
		{ SlowPhaseNote note("cam.background", scene); worldInfo->RenderBackground(rasterizer); }
	}

	// The following actually reschedules all vertices to be
	// redrawn. There is a cache between the actual rescheduling
	// and this call though. Visibility is imparted when this call
	// runs through the individual objects.

	m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_network);

	// Culling + LOD update, reused across cameras of this scene/frame that share the same
	// cullingcam/eye pair (see GetVisibleMeshes doc comment on the header).
	std::unique_ptr<SlowPhaseNote> cullingNote(new SlowPhaseNote("cam.culling", scene));
	const std::vector<KX_GameObject *>& culledObjects = GetVisibleMeshes(scene, cullingcam, eye);
	cullingNote.reset();

	// gameOb.hiddenFromCamera: drop the objects this camera must not draw. The cached culling result
	// is shared by cameras with the same cullingcam, so filter a copy, and only when some object asks.
	std::vector<KX_GameObject *> cameraObjects;
	if (KX_GameObject::s_hiddenFromCameraCount > 0) {
		cameraObjects.reserve(culledObjects.size());
		for (KX_GameObject *gameobj : culledObjects) {
			if (gameobj->GetHiddenFromCamera() != rendercam) {
				cameraObjects.push_back(gameobj);
			}
		}
	}
	const std::vector<KX_GameObject *>& objects =
	    (KX_GameObject::s_hiddenFromCameraCount > 0) ? cameraObjects : culledObjects;

	m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_rasterizer);

	// Draw debug infos like bouding box, armature ect.. if enabled.
	scene->DrawDebug(objects, m_engine->GetShowBoundingBox(), m_engine->GetShowArmatures());
	// Draw debug camera frustum.
	m_engine->GetDebugRenderer()->DrawDebugCameraFrustum(scene, cameraFrameData);
	m_engine->GetShadowRenderer()->DrawDebugFrustum(scene);
	m_engine->GetDebugRenderer()->DrawDebugVehicles(scene);

#ifdef WITH_PYTHON
	// Run any pre-drawing python callbacks
	{ SlowPhaseNote note("cam.predraw", scene); scene->RunDrawingCallbacks(KX_Scene::PRE_DRAW, rendercam); }
#endif

	{ SlowPhaseNote note("cam.buckets", scene); scene->RenderBuckets(objects, rasterizer->GetDrawingMode(), rendercam->GetWorldToCamera(), rasterizer, offScreen); }

	// GPU particle emitters (simulated once per frame in KX_Scene::UpdateGpuParticleEmitters,
	// called from NextFrame -- not here, since RenderCamera runs once per camera and would
	// otherwise step the simulation multiple times per frame). Drawn as camera-facing
	// billboards, one buffer per opted-in object (Fase I.2).
	// Soft particles: snapshot the solid depth once for every emitter of this camera (the same
	// blit Depth Transparency uses), so sprites fade where they meet the geometry.
	unsigned int softDepthTex = 0;
	if ((!scene->GetGpuParticleObjects().empty() || scene->HasParticleBlasts()) && offScreen && rasterizer->GetDrawingMode() == RAS_Rasterizer::RAS_TEXTURED) {
		rasterizer->UpdateGlobalDepthTexture(offScreen, m_engine->GetCanvas());
		softDepthTex = GPU_texture_opengl_bindcode(*GPU_texture_global_depth_ptr());
	}
	for (KX_GameObject *particleObj : scene->GetGpuParticleObjects()) {
		// Fase N: mirrors the visibility gate in KX_Scene::UpdateGpuParticleEmitters -- an
		// invisible emitter isn't simulated this frame, so its buffer holds stale positions.
		// Also mirrors the frustum-culling gate (Override Culling included) so particles from
		// an emitter outside this camera's view aren't drawn.
		if (!particleObj->GetVisible() || (particleObj->GetCullingNode().GetCulled() && !particleObj->HasStaticParticles() &&
		                                   !particleObj->GetMeshList().empty())) {
			continue;
		}
		RAS_ParticleBuffer *particleBuffer = particleObj->GetParticleBuffer();
		if (particleBuffer) {
			particleBuffer->Draw(rasterizer->GetViewMatrix(), rasterizer->GetProjectionMatrix(), softDepthTex);
		}
		// Fase Q: second "Mix" emitter, drawn right after the first so the two looks blend on
		// the same object instead of one replacing the other.
		RAS_ParticleBuffer *particleBufferMix = particleObj->GetParticleBufferMix();
		if (particleBufferMix) {
			particleBufferMix->Draw(rasterizer->GetViewMatrix(), rasterizer->GetProjectionMatrix(), softDepthTex);
		}
	}

	// Explosive > Particle Explosion bursts.
	scene->DrawParticleBlasts(rasterizer->GetViewMatrix(), rasterizer->GetProjectionMatrix(), softDepthTex);

	// World > Rain > Aura: every live stroke of the scene in one draw call.
	if (KX_RainAura *rainAura = scene->GetRainAura()) {
		rainAura->Draw(rasterizer->GetViewMatrix(), rasterizer->GetProjectionMatrix());
	}
	// World > Rain > Lightning: the bolt ribbons, one draw call (the flash is in the rain filter).
	if (KX_RainLightning *rainLightning = scene->GetRainLightning()) {
		rainLightning->Draw(rasterizer->GetViewMatrix(), rasterizer->GetProjectionMatrix());
	}

	// Plano 9, unidade 2: DebugDrawWorld() desce até btDiscreteDynamicsWorld::debugDrawWorld(),
	// que varre todos os corpos/constraints do mundo físico mesmo quando nenhum modo de debug
	// está ligado. GetDebugMode() == 0 é o caso comum (fora do editor de física), então só
	// chamamos quando há algo de fato para desenhar.
	PHY_IPhysicsEnvironment *physicsEnv = scene->GetPhysicsEnvironment();
	if (physicsEnv && physicsEnv->GetDebugMode() != 0) {
		physicsEnv->DebugDrawWorld();
	}
}

/*
 * To run once per scene
 */
RAS_OffScreen *KX_RenderPipeline::PostRenderScene(KX_Scene *scene, RAS_OffScreen *inputofs, RAS_OffScreen *targetofs)
{
	m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_filters2d);

	KX_SetActiveScene(scene);

	RAS_Rasterizer *rasterizer = m_engine->GetRasterizer();
	RAS_ICanvas *canvas = m_engine->GetCanvas();

	scene->FlushDebugDraw(rasterizer, canvas);

	// We need to first make sure our viewport is correct (enabling multiple viewports can mess this up), only for filters.
	const int width = canvas->GetRenderWidth();
	const int height = canvas->GetRenderHeight();
	rasterizer->SetViewport(0, 0, width, height);
	rasterizer->SetScissor(0, 0, width, height);

	// Calculate sun screen position for the Light Scattering and Lens Flare filters.
	KX_2DFilterManager *filterManager = scene->Get2DFilterManager();
	if (filterManager) {
		// Camera FX (focus DOF, speed/directional blur, cat eye lens) of the active camera.
		filterManager->UpdateCameraFX(scene->GetActiveCamera(), m_engine->GetClockTime());
	}
	RAS_2DFilter *flareFilter = filterManager ? filterManager->GetFilterPass(RAS_2DFilterManager::FILTERPASS_LENSFLARE, true) : nullptr;

	float sunPos[2] = {0.5f, 0.0f};
	if (scene->GetUseLightScatter() || flareFilter) {
		KX_LightObject *world_sun = scene->GetWorldSun();
		KX_Camera *cam = scene->GetActiveCamera();
		// No active camera (scene still loading or camera removed): skip the sun position.
		if (world_sun && cam) {

			// Direction toward the sun: the lamp's +Z, the same axis the sky shader draws the sun disc on
			// (KX_WorldInfo copies it to world_sun->obmat[2]). -Z is where the light travels, away from it.
			mt::vec3 sunDir = world_sun->NodeGetWorldOrientation().GetColumn(2);
			mt::vec3 viewDir = cam->NodeGetWorldOrientation().Inverse() * sunDir.Normalized();

			mt::vec4 screenPos = cam->GetProjectionMatrix(RAS_Rasterizer::RAS_STEREO_LEFTEYE) * mt::vec4(viewDir.x, viewDir.y, viewDir.z, 1.0f);

			// screenPos.w is the projected depth: zero or negative means the sun is behind the
			// camera or parallel to the view plane, which would divide by (near) zero below and
			// feed NaN/Inf into the Light Scattering/Lens Flare shader uniforms. In that case push
			// sunPos off the [0,1] screen range instead of leaving it at a default in-range value,
			// so the Lens Flare shader's own off-screen check (which only tests [0,1]) hides it
			// instead of drawing a stray flare at that default position; no warning, since this is
			// a normal camera angle, not a data error.
			if (std::isfinite(screenPos.w) && screenPos.w > FLT_EPSILON) {
				mt::vec2 sunScreenPos = mt::vec2(screenPos.x / screenPos.w, screenPos.y / screenPos.w);
				sunScreenPos = (sunScreenPos + mt::one2) * 0.5f;

				sunPos[0] = sunScreenPos.x;
				sunPos[1] = sunScreenPos.y;
			}
			else {
				sunPos[0] = -1.0f;
				sunPos[1] = -1.0f;
			}
		}
	}

	// Animate the native World weather filters (Rain/Clouds/Lens Flare) -- their shaders
	// scroll/flicker using a time uniform that nothing was updating after Fase 5 wired the
	// filters on, so they rendered as a frozen frame. Driven off the engine's frame time,
	// which advances one unscaled m_timestep per frame (FrameTiming()), so the weather
	// shaders keep their speed under Time Scale; they do not slow down in slow motion.
	if (filterManager) {
		const float time = (float)m_engine->GetFrameTime();
		filterManager->SetFrameTime(time);

		if (RAS_2DFilter *rain = filterManager->GetFilterPass(RAS_2DFilterManager::FILTERPASS_RAIN, true)) {
			BuildInFilters *rainParams = rain->GetBuildInFilters();
			rainParams->rain_time = time;
			// Every rain value is a uniform and can change at runtime (world.setWeather, or the
			// Live UI during Play), so read them back from the World every frame -- a handful
			// of floats, no recompile.
			if (const World *world = scene->GetBlenderScene()->world) {
				rainParams->useRainDroplets = (world->weather_flag & WO_WEATHER_RAIN_DROPLETS) != 0;
				rainParams->useRainRipple = (world->weather_flag & WO_WEATHER_RAIN_RIPPLE) != 0;
				rainParams->rain_style = world->rain_style;
				rainParams->rain_intensity = world->rain_intensity;
				rainParams->rain_density = world->rain_density;
				rainParams->rain_speed = world->rain_speed;
				// Volumetric streaks scroll 500 cells per second: in the shader's float, time * speed * 500
				// drops every fraction after a few minutes of play and the rain vanishes. Wrap it in double.
				rainParams->rain_fall_phase = (float)std::fmod(m_engine->GetFrameTime() * world->rain_speed * 500.0, 20480.0);
				rainParams->rain_wind = world->rain_wind;
				rainParams->rain_darken = world->rain_darken;
				rainParams->rain_ripple_distance = world->rain_ripple_distance;
				rainParams->rain_ripple_min_up = world->rain_ripple_min_up;
				for (int i = 0; i < 3; ++i) {
					rainParams->rain_color[i] = world->rain_color[i];
				}
				rainParams->useRainSplash = (world->weather_flag & WO_WEATHER_RAIN_SPLASH) != 0;
				rainParams->rain_streak_width = world->rain_streak_width;
				rainParams->rain_ripple = world->rain_ripple;
				rainParams->rain_ripple_normal = world->rain_ripple_normal;
				rainParams->rain_splash_size = world->rain_splash_size;
				rainParams->rain_splash_rate = world->rain_splash_rate;
				rainParams->rain_splash_intensity = world->rain_splash_intensity;
				rainParams->rain_splash_distance = world->rain_splash_distance;
				rainParams->rain_ripple_size = world->rain_ripple_size;
				rainParams->rain_ripple_rate = world->rain_ripple_rate;
				rainParams->rain_splash_normal = world->rain_splash_normal;
				rainParams->rain_splash_min_up = world->rain_splash_min_up;
				rainParams->useRainPuddles = (world->weather_flag & WO_WEATHER_RAIN_PUDDLES) != 0;
				rainParams->useRainPuddleSSR = (world->weather_flag & WO_WEATHER_RAIN_PUDDLE_SSR) != 0;
				rainParams->useRainRipplePuddle = (world->weather_flag & WO_WEATHER_RAIN_RIPPLE_PUDDLE) != 0;
				rainParams->useRainSplashPuddle = (world->weather_flag & WO_WEATHER_RAIN_SPLASH_PUDDLE) != 0;
				rainParams->rain_puddle_amount = world->rain_puddle_amount;
				rainParams->rain_puddle_size = world->rain_puddle_size;
				rainParams->rain_puddle_darkness = world->rain_puddle_darkness;
				rainParams->rain_puddle_reflection = world->rain_puddle_reflection;
				rainParams->rain_puddle_distance = world->rain_puddle_distance;
				rainParams->rain_puddle_min_up = world->rain_puddle_min_up;
				rainParams->rain_sky_horizon[0] = world->horr;
				rainParams->rain_sky_horizon[1] = world->horg;
				rainParams->rain_sky_horizon[2] = world->horb;
				rainParams->rain_sky_zenith[0] = world->zenr;
				rainParams->rain_sky_zenith[1] = world->zeng;
				rainParams->rain_sky_zenith[2] = world->zenb;

				// Ripples/Splash only on the objects with ripples_effect/splash_effect, when any
				// object has them: those objects go into a mask with this camera's matrices.
				rainParams->rain_mask_flags = 0;
				if ((world->weather_flag & WO_WEATHER_RAIN) &&
				    (world->weather_flag & (WO_WEATHER_RAIN_RIPPLE | WO_WEATHER_RAIN_SPLASH | WO_WEATHER_RAIN_PUDDLES)))
				{
					KX_RainSurfaceMask *mask = scene->GetRainSurfaceMask();
					rainParams->rain_mask_flags = mask->Render(scene, world, m_engine->GetFrameTime(),
					                                           rasterizer->GetViewMatrix(), rasterizer->GetProjectionMatrix(),
					                                           width, height);
					rainParams->rain_mask_texture = mask->GetTexture();
				}
			}
			// Lightning flash: flash, bolt brightness and where the bolt is on screen.
			const mt::vec4 lightning = scene->GetRainLightning() ?
				scene->GetRainLightning()->GetFilterParams(rasterizer->GetViewMatrix(), rasterizer->GetProjectionMatrix()) : mt::zero4;
			for (int i = 0; i < 4; ++i) {
				rainParams->rain_lightning[i] = lightning[i];
			}
		}
		if (RAS_2DFilter *clouds = filterManager->GetFilterPass(RAS_2DFilterManager::FILTERPASS_CLOUDS, true)) {
			BuildInFilters *cloudParams = clouds->GetBuildInFilters();
			cloudParams->cloud_time = time;
			if (const World *world = scene->GetBlenderScene()->world) {
				cloudParams->cloud_coverage = world->cloud_coverage;
				cloudParams->cloud_scale = world->cloud_scale;
				cloudParams->cloud_speed = world->cloud_speed;
				cloudParams->cloud_mask = ((world->weather_flag & WO_WEATHER_CLOUDS) ? 1 : 0) +
				                          ((world->sky_layer_flag & WO_SKY_LAYERS_ENABLE) ? 2 : 0) +
				                          ((world->vcloud_flag & WO_VCLOUDS_ENABLE) ? 4 : 0);
				cloudParams->sky_layer_coverage = world->sky_layer_coverage;
				cloudParams->sky_layer_scale = world->sky_layer_scale;
				cloudParams->sky_layer_speed = world->sky_layer_speed;
				for (int i = 0; i < 3; ++i) {
					cloudParams->sky_layer_color[i] = world->sky_layer_color[i];
				}
				cloudParams->cloud_detail = world->cloud_detail;
				cloudParams->sky_layer_detail = world->sky_layer_detail;
				cloudParams->sky_layer_relief = world->sky_layer_relief;
				for (int i = 0; i < 3; ++i) {
					cloudParams->cloud_color[i] = world->cloud_color[i];
				}
				cloudParams->vcloud_coverage = world->vcloud_coverage;
				cloudParams->vcloud_scale = world->vcloud_scale;
				cloudParams->vcloud_speed = world->vcloud_speed;
				cloudParams->vcloud_altitude = world->vcloud_altitude;
				cloudParams->vcloud_thickness = world->vcloud_thickness;
				cloudParams->vcloud_density = world->vcloud_density;
				cloudParams->vcloud_detail_scale = world->vcloud_detail_scale;
				cloudParams->vcloud_silver_intensity = world->vcloud_silver_intensity;
				cloudParams->vcloud_quality = world->vcloud_quality;
				cloudParams->vcloud_shadow_enable = (world->vcloud_flag & WO_VCLOUDS_SHADOW_ENABLE) != 0;
				cloudParams->vcloud_shadow_strength = world->vcloud_shadow_strength;
				for (int i = 0; i < 3; ++i) {
					cloudParams->vcloud_color[i] = world->vcloud_color[i];
				}
				/* World-space sun direction for the Stage 2 raymarch (self-shadow mini-march,
				 * Henyey-Greenstein silver lining) and the terrain shadow approximation --
				 * same lamp/axis as the Light Scattering/Lens Flare sun position above. */
				cloudParams->vcloud_sundir[0] = 0.0f;
				cloudParams->vcloud_sundir[1] = 0.0f;
				cloudParams->vcloud_sundir[2] = 1.0f;
				if (KX_LightObject *vcloud_sun = scene->GetWorldSun()) {
					mt::vec3 sunDir = vcloud_sun->NodeGetWorldOrientation().GetColumn(2).Normalized();
					cloudParams->vcloud_sundir[0] = sunDir.x;
					cloudParams->vcloud_sundir[1] = sunDir.y;
					cloudParams->vcloud_sundir[2] = sunDir.z;
				}
			}
		}
		if (RAS_2DFilter *vfog = filterManager->GetFilterPass(RAS_2DFilterManager::FILTERPASS_VFOG, true)) {
			if (const World *world = scene->GetBlenderScene()->world) {
				KX_FillVolumetricFog(vfog->GetBuildInFilters(), scene, world, time,
				                     rasterizer->GetViewMatrix().Inverse().TranslationVector3D());
			}
		}
		if (flareFilter) {
			BuildInFilters *flareParams = flareFilter->GetBuildInFilters();
			flareParams->flare_time = time;
			if (const World *world = scene->GetBlenderScene()->world) {
				flareParams->flare_scale = world->flare_scale;
				flareParams->flare_intensity = world->flare_intensity;
			}
			flareParams->flare_sun_x = sunPos[0];
			flareParams->flare_sun_y = sunPos[1];
		}
	}

	RAS_OffScreen *offScreen = scene->Render2DFilters(rasterizer, canvas, inputofs, targetofs, sunPos);

	m_engine->GetLogger().StartLog(KX_KetsjiEngine::tc_rasterizer);

#ifdef WITH_PYTHON
	/* We can't deduce what camera should be passed to the python callbacks
	 * because the post draw callbacks are per scenes and not per cameras.
	 */
	scene->RunDrawingCallbacks(KX_Scene::POST_DRAW, nullptr);

	// Python draw callback can also call debug draw functions, so we have to clear debug shapes.
	scene->FlushDebugDraw(rasterizer, canvas);
#endif

	return offScreen;
}
