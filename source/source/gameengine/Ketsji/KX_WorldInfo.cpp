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
 */

/** \file gameengine/Ketsji/KX_WorldInfo.cpp
 *  \ingroup ketsji
 */


#include "KX_WorldInfo.h"
#include <algorithm>
#include <cstring>
#include "KX_LightObject.h"
#include "KX_PyMath.h"
#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "KX_Scene.h"
#include "RAS_Rasterizer.h"
#include "GPU_material.h"

#include "RAS_ILightObject.h"

/* This little block needed for linking to Blender... */
#ifdef WIN32
#include "BLI_winstuff.h"
#endif

/* This list includes only data type definitions */
#include "DNA_lamp_types.h"
#include "DNA_scene_types.h"
#include "DNA_world_types.h"

#include "BLI_math.h"

#include "BKE_global.h"
#include "BKE_scene.h"
/* end of blender include block */

KX_WorldInfo::KX_WorldInfo(Scene *blenderscene, World *blenderworld)
	:m_scene(blenderscene),
	m_skyDirty(false),
	m_skyChanged(false)
#ifdef WITH_PYTHON
	, m_attr_dict(nullptr)
#endif
{
	if (blenderworld) {
		m_name = blenderworld->id.name + 2;
		SkySettings& sky = m_savedSky;
		sky.skytype = blenderworld->skytype;
		sky.star_style = blenderworld->star_style;
		sky.aurora_flag = blenderworld->aurora_flag;
		sky.aurora_colors = blenderworld->aurora_colors;
		sky.moon_enabled = blenderworld->moon_enabled;
		sky.moon_size = blenderworld->moon_size;
		sky.moon_brightness = blenderworld->moon_brightness;
		sky.atmo_intensity = blenderworld->atmo_intensity;
		copy_v3_v3(sky.atmo_rayleigh_col, blenderworld->atmo_rayleigh_col);
		sky.atmo_rayleigh_density = blenderworld->atmo_rayleigh_density;
		sky.atmo_mie_density = blenderworld->atmo_mie_density;
		sky.atmo_mie_g = blenderworld->atmo_mie_g;
		sky.atmo_altitude = blenderworld->atmo_altitude;
		m_do_color_management = BKE_scene_check_color_management_enabled(blenderscene);
		m_hasworld = true;
		m_hasmist = ((blenderworld->mode) & WO_MIST ? true : false);
		m_hasEnvLight = ((blenderworld->mode) & WO_ENV_LIGHT ? true : false);
		m_savedData.horizonColor[0] = blenderworld->horr;
		m_savedData.horizonColor[1] = blenderworld->horg;
		m_savedData.horizonColor[2] = blenderworld->horb;
		m_savedData.zenithColor[0] = blenderworld->zenr;
		m_savedData.zenithColor[1] = blenderworld->zeng;
		m_savedData.zenithColor[2] = blenderworld->zenb;
		m_envLightEnergy = blenderworld->ao_env_energy;
		m_envLightColor = blenderworld->aocolor;
		m_sunSize = blenderworld->sun_size;
		m_savedData.sun_size = blenderworld->sun_size;
		m_misttype = blenderworld->mistype;
		m_miststart = blenderworld->miststa;
		m_mistdistance = blenderworld->mistdist;
		m_mistheight = blenderworld->mistheight;
		m_mistdensity = blenderworld->mistdensity;
		m_mistintensity = blenderworld->misi;
		setMistColor(mt::vec3(blenderworld->horr, blenderworld->horg, blenderworld->horb));
		setHorizonColor(mt::vec4(blenderworld->horr, blenderworld->horg, blenderworld->horb, 1.0f));
		setZenithColor(mt::vec4(blenderworld->zenr, blenderworld->zeng, blenderworld->zenb, 1.0f));
		setAmbientColor(mt::vec3(blenderworld->ambr, blenderworld->ambg, blenderworld->ambb));
		setExposure(blenderworld->exp);
		setRange(blenderworld->range);

		// Save world sun values.
		if (m_scene->world_sun) {
			Lamp *blenderSun = static_cast<Lamp *>(m_scene->world_sun->data);

			copy_v3_v3(m_savedData.m_worldsun_rot, m_scene->world_sun->obmat[2]);

			m_savedData.m_worldsun_col[0] = blenderSun->r;
			m_savedData.m_worldsun_col[1] = blenderSun->g;
			m_savedData.m_worldsun_col[2] = blenderSun->b;
			m_savedData.m_worldsun_energy = blenderSun->energy;
		}
	}
	else {
		m_hasworld = false;
	}
}

KX_WorldInfo::~KX_WorldInfo()
{
#ifdef WITH_PYTHON
	if (m_attr_dict) {
		PyDict_Clear(m_attr_dict); /* in case of circular refs or other weird cases */
		Py_CLEAR(m_attr_dict);
	}
#endif

	// Restore saved horizon and zenith colors.
	if (m_hasworld) {
		m_scene->world->horr = m_savedData.horizonColor[0];
		m_scene->world->horg = m_savedData.horizonColor[1];
		m_scene->world->horb = m_savedData.horizonColor[2];
		m_scene->world->zenr = m_savedData.zenithColor[0];
		m_scene->world->zeng = m_savedData.zenithColor[1];
		m_scene->world->zenb = m_savedData.zenithColor[2];

		m_scene->world->sun_size = m_savedData.sun_size;

		// Restore world sun values.
		if (m_scene->world_sun) {
			Lamp *blenderSun = static_cast<Lamp *>(m_scene->world_sun->data);

			copy_v3_v3(m_scene->world_sun->obmat[2], m_savedData.m_worldsun_rot);

			blenderSun->r = m_savedData.m_worldsun_col[0];
			blenderSun->g = m_savedData.m_worldsun_col[1];
			blenderSun->b = m_savedData.m_worldsun_col[2];
			blenderSun->energy = m_savedData.m_worldsun_energy;
		}

		// Restore the sky settings changed from Python, the editor rebuilds its world shader.
		if (m_skyChanged) {
			World *world = m_scene->world;
			const SkySettings& sky = m_savedSky;
			world->skytype = sky.skytype;
			world->star_style = sky.star_style;
			world->aurora_flag = sky.aurora_flag;
			world->aurora_colors = sky.aurora_colors;
			world->moon_enabled = sky.moon_enabled;
			world->moon_size = sky.moon_size;
			world->moon_brightness = sky.moon_brightness;
			world->atmo_intensity = sky.atmo_intensity;
			copy_v3_v3(world->atmo_rayleigh_col, sky.atmo_rayleigh_col);
			world->atmo_rayleigh_density = sky.atmo_rayleigh_density;
			world->atmo_mie_density = sky.atmo_mie_density;
			world->atmo_mie_g = sky.atmo_mie_g;
			world->atmo_altitude = sky.atmo_altitude;
			GPU_material_free(&world->gpumaterial);
		}
	}
}

std::string KX_WorldInfo::GetName()
{
	return m_name;
}

bool KX_WorldInfo::SetWeatherRuntimeProperty(const char *identifier, float value, bool boolValue, bool useBool)
{
	if (!m_scene || !m_scene->world || !identifier) return false;
	World *world = m_scene->world;
	if (std::strcmp(identifier, "weather.rain_intensity") == 0) world->rain_intensity = value;
	else if (std::strcmp(identifier, "weather.rain_density") == 0) world->rain_density = value;
	else if (std::strcmp(identifier, "weather.rain_speed") == 0) world->rain_speed = value;
	else if (std::strcmp(identifier, "weather.rain_wind") == 0) world->rain_wind = value;
	else if (std::strcmp(identifier, "weather.rain_darken") == 0) world->rain_darken = value;
	else if (std::strcmp(identifier, "weather.ripple_intensity") == 0) world->rain_ripple = value;
	else if (std::strcmp(identifier, "weather.ripple_normal") == 0) world->rain_ripple_normal = value;
	else if (std::strcmp(identifier, "weather.ripple_size") == 0) world->rain_ripple_size = value;
	else if (std::strcmp(identifier, "weather.ripple_rate") == 0) world->rain_ripple_rate = value;
	else if (std::strcmp(identifier, "weather.splash_normal") == 0) world->rain_splash_normal = value;
	else if (std::strcmp(identifier, "weather.splash_min_up") == 0) world->rain_splash_min_up = value;
	else if (std::strcmp(identifier, "weather.rain") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_RAIN; else world->weather_flag &= ~WO_WEATHER_RAIN;
	}
	else if (std::strcmp(identifier, "weather.ripples") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_RAIN_RIPPLE; else world->weather_flag &= ~WO_WEATHER_RAIN_RIPPLE;
	}
	else if (std::strcmp(identifier, "weather.droplets") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_RAIN_DROPLETS; else world->weather_flag &= ~WO_WEATHER_RAIN_DROPLETS;
	}
	else if (std::strcmp(identifier, "weather.earthquake") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_EARTHQUAKE; else world->weather_flag &= ~WO_WEATHER_EARTHQUAKE;
	}
	else if (std::strcmp(identifier, "weather.earthquake_level") == 0) world->earthquake_level = (std::max)(0, (std::min)(5, (int)(value + 0.5f)));
	else if (std::strcmp(identifier, "weather.earthquake_scale") == 0) world->earthquake_scale = value;
	else if (std::strcmp(identifier, "weather.earthquake_camera") == 0) world->earthquake_camera = value;
	else if (std::strcmp(identifier, "weather.rain_streak_width") == 0) world->rain_streak_width = value;
	else if (std::strcmp(identifier, "weather.splash") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_RAIN_SPLASH; else world->weather_flag &= ~WO_WEATHER_RAIN_SPLASH;
	}
	else if (std::strcmp(identifier, "weather.splash_size") == 0) world->rain_splash_size = value;
	else if (std::strcmp(identifier, "weather.splash_rate") == 0) world->rain_splash_rate = value;
	else if (std::strcmp(identifier, "weather.splash_intensity") == 0) world->rain_splash_intensity = value;
	else if (std::strcmp(identifier, "weather.splash_distance") == 0) world->rain_splash_distance = value;
	else if (std::strcmp(identifier, "weather.puddles") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_RAIN_PUDDLES; else world->weather_flag &= ~WO_WEATHER_RAIN_PUDDLES;
	}
	else if (std::strcmp(identifier, "weather.ripple_puddle_only") == 0 && useBool) {
		// Needs the puddles, like the checkbox.
		if (boolValue) world->weather_flag |= WO_WEATHER_RAIN_RIPPLE_PUDDLE | WO_WEATHER_RAIN_PUDDLES; else world->weather_flag &= ~WO_WEATHER_RAIN_RIPPLE_PUDDLE;
	}
	else if (std::strcmp(identifier, "weather.splash_puddle_only") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_RAIN_SPLASH_PUDDLE | WO_WEATHER_RAIN_PUDDLES; else world->weather_flag &= ~WO_WEATHER_RAIN_SPLASH_PUDDLE;
	}
	else if (std::strcmp(identifier, "weather.puddle_ssr") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_RAIN_PUDDLE_SSR; else world->weather_flag &= ~WO_WEATHER_RAIN_PUDDLE_SSR;
	}
	else if (std::strcmp(identifier, "weather.puddle_amount") == 0) world->rain_puddle_amount = (std::max)(0.0f, (std::min)(1.0f, value));
	else if (std::strcmp(identifier, "weather.puddle_size") == 0) world->rain_puddle_size = value;
	else if (std::strcmp(identifier, "weather.puddle_darkness") == 0) world->rain_puddle_darkness = value;
	else if (std::strcmp(identifier, "weather.puddle_reflection") == 0) world->rain_puddle_reflection = value;
	else if (std::strcmp(identifier, "weather.puddle_distance") == 0) world->rain_puddle_distance = value;
	else if (std::strcmp(identifier, "weather.puddle_min_up") == 0) world->rain_puddle_min_up = value;
	else if (std::strcmp(identifier, "weather.aura") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_RAIN_AURA; else world->weather_flag &= ~WO_WEATHER_RAIN_AURA;
	}
	else if (std::strcmp(identifier, "weather.aura_style") == 0) world->rain_aura_style = (value >= 0.5f) ? WO_RAIN_AURA_ANIMATED : WO_RAIN_AURA_STATIC;
	else if (std::strcmp(identifier, "weather.aura_size") == 0) world->rain_aura_size = value;
	else if (std::strcmp(identifier, "weather.aura_rate") == 0) world->rain_aura_rate = value;
	else if (std::strcmp(identifier, "weather.aura_intensity") == 0) world->rain_aura_intensity = value;
	else if (std::strcmp(identifier, "weather.aura_distance") == 0) world->rain_aura_distance = value;
	else if (std::strcmp(identifier, "weather.lightning") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_RAIN_LIGHTNING; else world->weather_flag &= ~WO_WEATHER_RAIN_LIGHTNING;
	}
	else if (std::strcmp(identifier, "weather.lightning_side") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_RAIN_LIGHTNING_SIDE; else world->weather_flag &= ~WO_WEATHER_RAIN_LIGHTNING_SIDE;
	}
	else if (std::strcmp(identifier, "weather.lightning_rate") == 0) world->rain_lightning_rate = value;
	else if (std::strcmp(identifier, "weather.lightning_intensity") == 0) world->rain_lightning_intensity = value;
	else if (std::strcmp(identifier, "weather.lightning_distance") == 0) world->rain_lightning_distance = value;
	else if (std::strcmp(identifier, "weather.lightning_width") == 0) world->rain_lightning_width = value;
	else if (std::strcmp(identifier, "weather.clouds") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_CLOUDS; else world->weather_flag &= ~WO_WEATHER_CLOUDS;
	}
	else if (std::strcmp(identifier, "weather.cloud_coverage") == 0) world->cloud_coverage = value;
	else if (std::strcmp(identifier, "weather.cloud_scale") == 0) world->cloud_scale = value;
	else if (std::strcmp(identifier, "weather.cloud_speed") == 0) world->cloud_speed = value;
	else if (std::strcmp(identifier, "weather.lens_flare") == 0 && useBool) {
		if (boolValue) world->weather_flag |= WO_WEATHER_LENSFLARE; else world->weather_flag &= ~WO_WEATHER_LENSFLARE;
	}
	else if (std::strcmp(identifier, "weather.flare_scale") == 0) world->flare_scale = value;
	else if (std::strcmp(identifier, "weather.flare_intensity") == 0) world->flare_intensity = value;
	else if (std::strcmp(identifier, "weather.mist") == 0 && useBool) {
		m_hasmist = boolValue;
		if (boolValue) world->mode |= WO_MIST; else world->mode &= ~WO_MIST;
	}
	else if (std::strcmp(identifier, "weather.mist_intensity") == 0) { world->misi = value; m_mistintensity = value; }
	else if (std::strcmp(identifier, "weather.mist_start") == 0) { world->miststa = value; m_miststart = value; }
	else if (std::strcmp(identifier, "weather.mist_depth") == 0) { world->mistdist = value; m_mistdistance = value; }
	else if (std::strcmp(identifier, "weather.mist_height") == 0) { world->mistheight = value; m_mistheight = value; }
	else if (std::strcmp(identifier, "weather.mist_density") == 0) { world->mistdensity = value; m_mistdensity = value; }
	else return false;
	return true;
}

bool KX_WorldInfo::GetWeatherRuntimeProperty(const char *identifier, float &value, bool &isBool)
{
	if (!m_scene || !m_scene->world || !identifier) return false;
	World *world = m_scene->world;
	if (std::strncmp(identifier, "weather.", 8) == 0) identifier += 8;

	static const struct { const char *name; int flag; } flags[] = {
		{"rain", WO_WEATHER_RAIN}, {"ripples", WO_WEATHER_RAIN_RIPPLE}, {"droplets", WO_WEATHER_RAIN_DROPLETS},
		{"splash", WO_WEATHER_RAIN_SPLASH}, {"puddles", WO_WEATHER_RAIN_PUDDLES}, {"puddle_ssr", WO_WEATHER_RAIN_PUDDLE_SSR}, {"ripple_puddle_only", WO_WEATHER_RAIN_RIPPLE_PUDDLE}, {"splash_puddle_only", WO_WEATHER_RAIN_SPLASH_PUDDLE}, {"aura", WO_WEATHER_RAIN_AURA}, {"lightning", WO_WEATHER_RAIN_LIGHTNING},
		{"lightning_side", WO_WEATHER_RAIN_LIGHTNING_SIDE},
		{"clouds", WO_WEATHER_CLOUDS}, {"lens_flare", WO_WEATHER_LENSFLARE}, {"earthquake", WO_WEATHER_EARTHQUAKE},
	};
	for (const auto &f : flags) {
		if (std::strcmp(identifier, f.name) == 0) {
			isBool = true;
			value = (world->weather_flag & f.flag) ? 1.0f : 0.0f;
			return true;
		}
	}
	if (std::strcmp(identifier, "mist") == 0) {
		isBool = true;
		value = (world->mode & WO_MIST) ? 1.0f : 0.0f;
		return true;
	}
	if (std::strcmp(identifier, "earthquake_level") == 0) {
		isBool = false;
		value = (float)world->earthquake_level;
		return true;
	}
	if (std::strcmp(identifier, "aura_style") == 0) {
		isBool = false;
		value = (world->rain_aura_style == WO_RAIN_AURA_ANIMATED) ? 1.0f : 0.0f;
		return true;
	}

	const struct { const char *name; const float *ptr; } floats[] = {
		{"rain_intensity", &world->rain_intensity}, {"rain_density", &world->rain_density},
		{"rain_speed", &world->rain_speed}, {"rain_wind", &world->rain_wind},
		{"rain_darken", &world->rain_darken}, {"ripple_intensity", &world->rain_ripple},
		{"ripple_normal", &world->rain_ripple_normal},
		{"ripple_size", &world->rain_ripple_size}, {"ripple_rate", &world->rain_ripple_rate},
		{"splash_normal", &world->rain_splash_normal}, {"splash_min_up", &world->rain_splash_min_up}, {"rain_streak_width", &world->rain_streak_width},
		{"splash_size", &world->rain_splash_size}, {"splash_rate", &world->rain_splash_rate},
		{"splash_intensity", &world->rain_splash_intensity}, {"splash_distance", &world->rain_splash_distance},
		{"puddle_amount", &world->rain_puddle_amount}, {"puddle_size", &world->rain_puddle_size},
		{"puddle_darkness", &world->rain_puddle_darkness}, {"puddle_reflection", &world->rain_puddle_reflection},
		{"puddle_distance", &world->rain_puddle_distance}, {"puddle_min_up", &world->rain_puddle_min_up},
		{"aura_size", &world->rain_aura_size}, {"aura_rate", &world->rain_aura_rate},
		{"aura_intensity", &world->rain_aura_intensity}, {"aura_distance", &world->rain_aura_distance},
		{"lightning_rate", &world->rain_lightning_rate}, {"lightning_intensity", &world->rain_lightning_intensity},
		{"lightning_distance", &world->rain_lightning_distance}, {"lightning_width", &world->rain_lightning_width},
		{"cloud_coverage", &world->cloud_coverage}, {"cloud_scale", &world->cloud_scale},
		{"cloud_speed", &world->cloud_speed}, {"flare_scale", &world->flare_scale},
		{"flare_intensity", &world->flare_intensity}, {"mist_intensity", &world->misi},
		{"mist_start", &world->miststa}, {"mist_depth", &world->mistdist},
		{"mist_height", &world->mistheight}, {"mist_density", &world->mistdensity},
		{"earthquake_scale", &world->earthquake_scale}, {"earthquake_camera", &world->earthquake_camera},
	};
	for (const auto &f : floats) {
		if (std::strcmp(identifier, f.name) == 0) {
			isBool = false;
			value = *f.ptr;
			return true;
		}
	}
	return false;
}

bool KX_WorldInfo::hasWorld()
{
	return m_hasworld;
}

void KX_WorldInfo::setHorizonColor(const mt::vec4& horizoncolor)
{
	m_horizoncolor = horizoncolor;
}

void KX_WorldInfo::setZenithColor(const mt::vec4& zenithcolor)
{
	m_zenithcolor = zenithcolor;
}

void KX_WorldInfo::setMistStart(float d)
{
	m_miststart = d;
}

void KX_WorldInfo::setMistDistance(float d)
{
	m_mistdistance = d;
}

void KX_WorldInfo::setMistIntensity(float intensity)
{
	m_mistintensity = intensity;
}

void KX_WorldInfo::setExposure(float exposure)
{
	m_exposure = exposure;
}

void KX_WorldInfo::setRange(float range)
{
	m_range = range;
}

void KX_WorldInfo::setMistColor(const mt::vec3& mistcolor)
{
	m_mistcolor = mistcolor;

	if (m_do_color_management) {
		float col[3];
		linearrgb_to_srgb_v3_v3(col, m_mistcolor.Data());
		m_con_mistcolor = mt::vec3(col);
	}
	else {
		m_con_mistcolor = m_mistcolor;
	}
}

void KX_WorldInfo::setAmbientColor(const mt::vec3& ambientcolor)
{
	m_ambientcolor = ambientcolor;

	if (m_do_color_management) {
		float col[3];
		linearrgb_to_srgb_v3_v3(col, m_ambientcolor.Data());
		m_con_ambientcolor = mt::vec3(col);
	}
	else {
		m_con_ambientcolor = m_ambientcolor;
	}
}

void KX_WorldInfo::UpdateBackGround(RAS_Rasterizer *rasty, KX_LightObject *light)
{
	if (m_hasworld) {
		// Update World values for world material created in GPU_material_world/GPU_material_old_world.
		m_scene->world->zenr = m_zenithcolor[0];
		m_scene->world->zeng = m_zenithcolor[1];
		m_scene->world->zenb = m_zenithcolor[2];
		m_scene->world->horr = m_horizoncolor[0];
		m_scene->world->horg = m_horizoncolor[1];
		m_scene->world->horb = m_horizoncolor[2];

		m_scene->world->sun_size = m_sunSize;

		// Update GPUWorld values for regular materials.
		GPU_horizon_update_color(m_horizoncolor.Data());
		GPU_zenith_update_color(m_zenithcolor.Data());

		// Update World Background sun.
		if (!light) {
			return;
		}

		KX_GameObject *gameobj = static_cast<KX_GameObject *>(light);
		if (gameobj) {
			Lamp *blenderLight = static_cast<Lamp *>(m_scene->world_sun->data);

			mathfu::vec3 sunDir = light->NodeGetWorldOrientation().GetColumn(2);
			copy_v3_v3(m_scene->world_sun->obmat[2], sunDir.Data());
			// Sky Texture nodes (Game PBR) follow the sun lamp.
			GPU_sky_texture_follow_sun(sunDir.Data());

			blenderLight->r = light->GetLightData()->m_color[0];
			blenderLight->g = light->GetLightData()->m_color[1];
			blenderLight->b = light->GetLightData()->m_color[2];
			blenderLight->energy = light->GetLightData()->m_energy;
		}
	}
}

void KX_WorldInfo::UpdateWorldSettings(RAS_Rasterizer *rasty)
{
	if (m_hasworld) {
		rasty->SetAmbientColor(m_con_ambientcolor);
		GPU_ambient_update_color(m_ambientcolor.Data());
		GPU_update_exposure_range(m_exposure, m_range);
		GPU_update_envlight_energy(m_envLightEnergy);

		if (m_hasmist) {
			rasty->SetFog(m_misttype, m_miststart, m_mistdistance, m_mistintensity, m_con_mistcolor);
			GPU_mist_update_values(m_misttype, m_miststart, m_mistdistance, m_mistheight, m_mistdensity, m_mistintensity, m_mistcolor.Data());
			GPU_mist_update_enable(true);
		}
		else {
			GPU_mist_update_enable(false);
		}
	}
}

void KX_WorldInfo::RenderBackground(RAS_Rasterizer *rasty)
{
	if (m_hasworld) {
		/* A node World (Sky Texture, Environment...) only shows through the world material. */
		const bool node_world = BKE_scene_use_new_shading_nodes(m_scene) && m_scene->world->nodetree &&
		                        m_scene->world->use_nodes;
		if (m_skyDirty) {
			// Sky type, stars, aurora and atmosphere are compiled into the world shader.
			GPU_material_free(&m_scene->world->gpumaterial);
			m_skyDirty = false;
		}
		if (node_world || (m_scene->world->skytype & (WO_SKYBLEND | WO_SKYPAPER | WO_SKYREAL))) {
			GPUMaterial *gpumat = GPU_material_world(m_scene, m_scene->world);

			static float texcofac[4] = { 0.0f, 0.0f, 1.0f, 1.0f };
			GPU_material_bind(gpumat, m_scene->lay, fmod(KX_GetActiveEngine()->GetFrameTime(), 3600.0), true, rasty->GetViewMatrix().Data(),
			                  rasty->GetViewInvMatrix().Data(), texcofac, false,
			                  rasty->GetProjectionMatrix().Data());

			/* Disable cull face instead of setting front face as it could be
			 * inversed in planar rendering.
			 */
			rasty->SetCullFace(false);
			rasty->Enable(RAS_Rasterizer::RAS_DEPTH_TEST);
			rasty->SetDepthFunc(RAS_Rasterizer::RAS_ALWAYS);

			rasty->DrawOverlayPlane();

			rasty->SetDepthFunc(RAS_Rasterizer::RAS_LEQUAL);

			GPU_material_unbind(gpumat);
		}
		else {
			if (m_do_color_management) {
				float srgbcolor[4];
				linearrgb_to_srgb_v4(srgbcolor, m_horizoncolor.Data());
				rasty->SetClearColor(srgbcolor[0], srgbcolor[1], srgbcolor[2], srgbcolor[3]);
			}
			else {
				rasty->SetClearColor(m_horizoncolor[0], m_horizoncolor[1], m_horizoncolor[2], m_horizoncolor[3]);
			}
			rasty->Clear(RAS_Rasterizer::RAS_COLOR_BUFFER_BIT);
		}
	}
	// Else render a dummy gray background.
	else {
		/* Grey color computed by linearrgb_to_srgb_v3_v3 with a color of
		 * 0.050, 0.050, 0.050 (the default world horizon color).
		 */
		rasty->SetClearColor(0.247784f, 0.247784f, 0.247784f, 1.0f);
		rasty->Clear(RAS_Rasterizer::RAS_COLOR_BUFFER_BIT);
	}
}

#ifdef WITH_PYTHON

/* -------------------------------------------------------------------------
 * Python functions
 * ------------------------------------------------------------------------- */

/* -------------------------------------------------------------------------
 * World Properties mapping protocol (own.scene.world["key"])
 * ------------------------------------------------------------------------- */
static PyObject *Map_GetItem(PyObject *self_v, PyObject *item)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>EXP_PROXY_REF(self_v);
	const char *attr_str = _PyUnicode_AsString(item);
	EXP_Value *resultattr;
	PyObject *pyconvert;

	if (self == nullptr) {
		PyErr_SetString(PyExc_SystemError, "val = world[key]: KX_WorldInfo, " EXP_PROXY_ERROR_MSG);
		return nullptr;
	}

	if (attr_str && (resultattr = self->GetProperty(attr_str))) {
		pyconvert = resultattr->ConvertValueToPython();
		return pyconvert ? pyconvert : resultattr->GetProxy();
	}
	else if (self->m_attr_dict && (pyconvert = PyDict_GetItem(self->m_attr_dict, item))) {
		if (attr_str) {
			PyErr_Clear();
		}
		Py_INCREF(pyconvert);
		return pyconvert;
	}
	else {
		if (attr_str) {
			PyErr_Format(PyExc_KeyError, "value = world[key]: KX_WorldInfo, key \"%s\" does not exist", attr_str);
		}
		else {
			PyErr_SetString(PyExc_KeyError, "value = world[key]: KX_WorldInfo, key does not exist");
		}
		return nullptr;
	}
}

static int Map_SetItem(PyObject *self_v, PyObject *key, PyObject *val)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>EXP_PROXY_REF(self_v);
	const char *attr_str = _PyUnicode_AsString(key);
	if (attr_str == nullptr) {
		PyErr_Clear();
	}

	if (self == nullptr) {
		PyErr_SetString(PyExc_SystemError, "world[key] = value: KX_WorldInfo, " EXP_PROXY_ERROR_MSG);
		return -1;
	}

	if (val == nullptr) { /* del world["key"] */
		int del = 0;

		if (attr_str) {
			del |= (self->RemoveProperty(attr_str) == true) ? 1 : 0;
		}

		if (self->m_attr_dict) {
			del |= (PyDict_DelItem(self->m_attr_dict, key) == 0) ? 1 : 0;
		}

		if (del == 0) {
			if (attr_str) {
				PyErr_Format(PyExc_KeyError, "world[key] = value: KX_WorldInfo, key \"%s\" could not be set", attr_str);
			}
			else {
				PyErr_SetString(PyExc_KeyError, "del world[key]: KX_WorldInfo, key could not be deleted");
			}
			return -1;
		}
		else if (self->m_attr_dict) {
			PyErr_Clear(); /* PyDict_DelItem sets an error when it fails */
		}
	}
	else { /* world["key"] = value */
		bool set = false;

		if (attr_str && PyObject_TypeCheck(val, &EXP_PyObjectPlus::Type) == 0) {
			EXP_Value *vallie = self->ConvertPythonToValue(val, false, "world[key] = value: ");

			if (vallie) {
				EXP_Value *oldprop = self->GetProperty(attr_str);

				if (oldprop) {
					oldprop->SetValue(vallie);
				}
				else {
					self->SetProperty(attr_str, vallie);
				}

				vallie->Release();
				set = true;

				if (self->m_attr_dict) {
					if (PyDict_DelItem(self->m_attr_dict, key) != 0) {
						PyErr_Clear();
					}
				}
			}
			else if (PyErr_Occurred()) {
				return -1;
			}
		}

		if (set == false) {
			if (self->m_attr_dict == nullptr) { /* lazy init */
				self->m_attr_dict = PyDict_New();
			}

			if (PyDict_SetItem(self->m_attr_dict, key, val) == 0) {
				if (attr_str) {
					self->RemoveProperty(attr_str); /* overwrite the EXP_Value if it exists */
				}
				set = true;
			}
			else {
				if (attr_str) {
					PyErr_Format(PyExc_KeyError, "world[key] = value: KX_WorldInfo, key \"%s\" not be added to internal dictionary", attr_str);
				}
				else {
					PyErr_SetString(PyExc_KeyError, "world[key] = value: KX_WorldInfo, key not be added to internal dictionary");
				}
			}
		}

		if (set == false) {
			return -1;
		}
	}

	return 0;
}

PyMappingMethods KX_WorldInfo::Mapping = {
	(lenfunc)nullptr,                 /*inquiry mp_length */
	(binaryfunc)Map_GetItem,          /*binaryfunc mp_subscript */
	(objobjargproc)Map_SetItem,       /*objobjargproc mp_ass_subscript */
};

/* -------------------------------------------------------------------------
 * Python Integration Hooks
 * ------------------------------------------------------------------------- */
PyTypeObject KX_WorldInfo::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_WorldInfo",
	sizeof(EXP_PyObjectPlus_Proxy),
	0,
	py_base_dealloc,
	0,
	0,
	0,
	0,
	py_base_repr,
	0, 0, &Mapping, 0, 0, 0, 0, 0, 0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	0, 0, 0, 0, 0, 0, 0,
	Methods,
	0,
	0,
	&EXP_PyObjectPlus::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_WorldInfo::Methods[] = {
	{"setWeather", (PyCFunction)KX_WorldInfo::sPysetWeather, METH_VARARGS, "setWeather(name, value): change a World weather setting at runtime"},
	{"getWeather", (PyCFunction)KX_WorldInfo::sPygetWeather, METH_VARARGS, "getWeather(name): current value of a World weather setting (bool or float)"},
	{"strikeLightning", (PyCFunction)KX_WorldInfo::sPystrikeLightning, METH_VARARGS, "strikeLightning(bolt=True): a lightning strike now (rain must be on)"},
	{nullptr, nullptr} /* Sentinel */
};

PyObject *KX_WorldInfo::PysetWeather(PyObject *args)
{
	const char *name;
	PyObject *value;
	if (!PyArg_ParseTuple(args, "sO:setWeather", &name, &value)) {
		return nullptr;
	}
	const bool isBool = PyBool_Check(value);
	const float number = isBool ? (value == Py_True ? 1.0f : 0.0f) : (float)PyFloat_AsDouble(value);
	if (!isBool && PyErr_Occurred()) {
		return nullptr;
	}
	std::string identifier = name;
	if (identifier.compare(0, 8, "weather.") != 0) {
		identifier = "weather." + identifier;
	}
	if (!SetWeatherRuntimeProperty(identifier.c_str(), number, value == Py_True, isBool)) {
		PyErr_Format(PyExc_ValueError, "world.setWeather(): unknown setting \"%s\"", name);
		return nullptr;
	}
	Py_RETURN_NONE;
}

PyObject *KX_WorldInfo::PygetWeather(PyObject *args)
{
	const char *name;
	if (!PyArg_ParseTuple(args, "s:getWeather", &name)) {
		return nullptr;
	}
	float value = 0.0f;
	bool isBool = false;
	if (!GetWeatherRuntimeProperty(name, value, isBool)) {
		PyErr_Format(PyExc_ValueError, "world.getWeather(): unknown setting \"%s\"", name);
		return nullptr;
	}
	if (isBool) {
		return PyBool_FromLong(value != 0.0f);
	}
	return PyFloat_FromDouble(value);
}

PyObject *KX_WorldInfo::PystrikeLightning(PyObject *args)
{
	int bolt = 1;
	if (!PyArg_ParseTuple(args, "|p:strikeLightning", &bolt)) {
		return nullptr;
	}
	// Every running scene that uses this World (overlay scenes may share it).
	for (KX_Scene *scene : *KX_GetActiveEngine()->CurrentScenes()) {
		if (scene->GetBlenderScene() == m_scene) {
			scene->StrikeLightning(bolt != 0);
		}
	}
	Py_RETURN_NONE;
}

PyAttributeDef KX_WorldInfo::Attributes[] = {
	EXP_PYATTRIBUTE_BOOL_RW("mistEnable", KX_WorldInfo, m_hasmist),
	EXP_PYATTRIBUTE_FLOAT_RW("mistStart", 0.0f, 10000.0f, KX_WorldInfo, m_miststart),
	EXP_PYATTRIBUTE_FLOAT_RW("mistDistance", 0.001f, 10000.0f, KX_WorldInfo, m_mistdistance),
	EXP_PYATTRIBUTE_FLOAT_RW("mistIntensity", 0.0f, 1.0f, KX_WorldInfo, m_mistintensity),
	EXP_PYATTRIBUTE_SHORT_RW("mistType", 0, 2, true, KX_WorldInfo, m_misttype),
	EXP_PYATTRIBUTE_RO_FUNCTION("KX_MIST_QUADRATIC", KX_WorldInfo, pyattr_get_mist_typeconst),
	EXP_PYATTRIBUTE_RO_FUNCTION("KX_MIST_LINEAR", KX_WorldInfo, pyattr_get_mist_typeconst),
	EXP_PYATTRIBUTE_RO_FUNCTION("KX_MIST_INV_QUADRATIC", KX_WorldInfo, pyattr_get_mist_typeconst),
	EXP_PYATTRIBUTE_RW_FUNCTION("mistColor", KX_WorldInfo, pyattr_get_mist_color, pyattr_set_mist_color),
	EXP_PYATTRIBUTE_RW_FUNCTION("horizonColor", KX_WorldInfo, pyattr_get_horizon_color, pyattr_set_horizon_color),
	EXP_PYATTRIBUTE_RW_FUNCTION("backgroundColor", KX_WorldInfo, pyattr_get_background_color, pyattr_set_background_color),
	EXP_PYATTRIBUTE_RW_FUNCTION("zenithColor", KX_WorldInfo, pyattr_get_zenith_color, pyattr_set_zenith_color),
	EXP_PYATTRIBUTE_RW_FUNCTION("ambientColor", KX_WorldInfo, pyattr_get_ambient_color, pyattr_set_ambient_color),
	EXP_PYATTRIBUTE_FLOAT_RW("exposure", 0.0f, 1.0f, KX_WorldInfo, m_exposure),
	EXP_PYATTRIBUTE_FLOAT_RW("range", 0.2f, 5.0f, KX_WorldInfo, m_range),
	EXP_PYATTRIBUTE_FLOAT_RW("envLightEnergy", 0.0f, FLT_MAX, KX_WorldInfo, m_envLightEnergy),
	EXP_PYATTRIBUTE_BOOL_RO("envLightEnabled", KX_WorldInfo, m_hasEnvLight),
	EXP_PYATTRIBUTE_SHORT_RO("envLightColor", KX_WorldInfo, m_envLightColor),
	EXP_PYATTRIBUTE_FLOAT_RW("sunSize", 0.0f, 1.0f, KX_WorldInfo, m_sunSize),
	EXP_PYATTRIBUTE_RW_FUNCTION("skyType", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("useSkyStars", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("starStyle", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("useSkyMoon", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("moonSize", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("moonBrightness", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("useSkyAurora", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("auroraColors", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("atmosphereIntensity", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("atmosphereRayleighColor", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("atmosphereRayleighDensity", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("atmosphereMieDensity", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("atmosphereMieDirection", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_RW_FUNCTION("atmosphereAltitude", KX_WorldInfo, pyattr_get_sky, pyattr_set_sky),
	EXP_PYATTRIBUTE_NULL /* Sentinel */
};

/* Attribute get/set functions */

/* Sky settings: same names and ranges as the World > Sky panel (rna_world.c), enums by their RNA
 * identifier. The moon is a live uniform; the other settings rebuild the world shader (one compile,
 * next frame). Object materials keep the sky type they were compiled with (atmospheric mist). */
static const char *sky_type_names[] = {"FLAT", "GRADIENT", "PROCEDURAL", "ATMOSPHERIC", nullptr};
static const char *star_style_names[] = {"SIMPLE", "REALISTIC", "CONSTELLATIONS", nullptr};
static const char *aurora_colors_names[] = {"GREEN", "CLASSIC", "SHIFTING", nullptr};

namespace {
struct SkyFloat {
	const char *name;
	size_t offset;
	float min, max;
	/// Compiled into the world shader (not a live uniform).
	bool compiled;
};
}

static const SkyFloat sky_floats[] = {
	{"moonSize", offsetof(World, moon_size), 0.001f, 0.1f, false},
	{"moonBrightness", offsetof(World, moon_brightness), 0.0f, 1.0f, false},
	{"atmosphereIntensity", offsetof(World, atmo_intensity), 0.0f, 1000.0f, true},
	{"atmosphereRayleighDensity", offsetof(World, atmo_rayleigh_density), 0.0f, 20.0f, true},
	{"atmosphereMieDensity", offsetof(World, atmo_mie_density), 0.0f, 50.0f, true},
	{"atmosphereMieDirection", offsetof(World, atmo_mie_g), 0.0f, 0.99f, true},
	{"atmosphereAltitude", offsetof(World, atmo_altitude), 1.0f, 60000.0f, true},
};

/// Same mapping as rna_World_sky_type_get.
static int sky_type_index(short skytype)
{
	if (!(skytype & WO_SKYBLEND)) return 0;
	if ((skytype & WO_SKYREAL) && !(skytype & WO_SKYPAPER)) return (skytype & WO_SKYATMOSPHERIC) ? 3 : 2;
	return 1;
}

static int sky_enum_index(const char *const *names, PyObject *value, const char *attr)
{
	const char *str = PyUnicode_Check(value) ? PyUnicode_AsUTF8(value) : nullptr;
	if (str) {
		for (int i = 0; names[i]; ++i) {
			if (std::strcmp(str, names[i]) == 0) {
				return i;
			}
		}
	}
	std::string choices;
	for (int i = 0; names[i]; ++i) {
		choices += (i ? ", " : "") + std::string(names[i]);
	}
	PyErr_Format(PyExc_ValueError, "world.%s = str: KX_WorldInfo, expected one of %s", attr, choices.c_str());
	return -1;
}

PyObject *KX_WorldInfo::pyattr_get_sky(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);
	if (!self->m_hasworld) {
		Py_RETURN_NONE;
	}
	const World *world = self->m_scene->world;
	const std::string& name = attrdef->m_name;

	if (name == "skyType") return PyUnicode_FromString(sky_type_names[sky_type_index(world->skytype)]);
	if (name == "useSkyStars") return PyBool_FromLong((world->skytype & WO_SKYATMOSPHERIC_STARS) != 0);
	if (name == "starStyle") return PyUnicode_FromString(star_style_names[CLAMPIS(world->star_style, 0, 2)]);
	if (name == "useSkyMoon") return PyBool_FromLong(world->moon_enabled > 0.0f);
	if (name == "useSkyAurora") return PyBool_FromLong((world->aurora_flag & WO_AURORA_ENABLE) != 0);
	if (name == "auroraColors") return PyUnicode_FromString(aurora_colors_names[CLAMPIS(world->aurora_colors, 0, 2)]);
	if (name == "atmosphereRayleighColor") return PyColorFromVector(mt::vec3(world->atmo_rayleigh_col));
	for (const SkyFloat& f : sky_floats) {
		if (name == f.name) {
			return PyFloat_FromDouble(*(const float *)((const char *)world + f.offset));
		}
	}
	Py_RETURN_NONE;
}

int KX_WorldInfo::pyattr_set_sky(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);
	const std::string& name = attrdef->m_name;
	if (!self->m_hasworld) {
		PyErr_Format(PyExc_AttributeError, "world.%s: KX_WorldInfo, the scene has no World", name.c_str());
		return PY_SET_ATTR_FAIL;
	}
	World *world = self->m_scene->world;
	bool compiled = true;

	if (name == "skyType") {
		const int index = sky_enum_index(sky_type_names, value, name.c_str());
		if (index < 0) {
			return PY_SET_ATTR_FAIL;
		}
		// Same as rna_World_sky_type_set.
		world->skytype &= ~(WO_SKYBLEND | WO_SKYREAL | WO_SKYATMOSPHERIC);
		if (index >= 2) world->skytype &= ~WO_SKYPAPER;
		if (index >= 1) world->skytype |= WO_SKYBLEND;
		if (index >= 2) world->skytype |= WO_SKYREAL;
		if (index == 3) world->skytype |= WO_SKYATMOSPHERIC;
	}
	else if (name == "starStyle" || name == "auroraColors") {
		const bool stars = (name == "starStyle");
		const int index = sky_enum_index(stars ? star_style_names : aurora_colors_names, value, name.c_str());
		if (index < 0) {
			return PY_SET_ATTR_FAIL;
		}
		(stars ? world->star_style : world->aurora_colors) = index;
	}
	else if (name == "useSkyStars" || name == "useSkyMoon" || name == "useSkyAurora") {
		const int param = PyObject_IsTrue(value);
		if (param == -1) {
			PyErr_Format(PyExc_TypeError, "world.%s = bool: KX_WorldInfo, expected True or False", name.c_str());
			return PY_SET_ATTR_FAIL;
		}
		if (name == "useSkyMoon") {
			world->moon_enabled = param ? 1.0f : 0.0f;
			compiled = false;
		}
		else if (name == "useSkyStars") {
			SET_FLAG_FROM_TEST(world->skytype, param, WO_SKYATMOSPHERIC_STARS);
		}
		else {
			SET_FLAG_FROM_TEST(world->aurora_flag, param, WO_AURORA_ENABLE);
		}
	}
	else if (name == "atmosphereRayleighColor") {
		mt::vec3 color;
		if (!PyVecTo(value, color)) {
			return PY_SET_ATTR_FAIL;
		}
		for (int i = 0; i < 3; ++i) {
			world->atmo_rayleigh_col[i] = (std::max)(color[i], 0.0f);
		}
	}
	else {
		const SkyFloat *found = nullptr;
		for (const SkyFloat& f : sky_floats) {
			if (name == f.name) {
				found = &f;
				break;
			}
		}
		if (!found) {
			return PY_SET_ATTR_FAIL;
		}
		const float number = PyFloat_AsDouble(value);
		if (number == -1.0f && PyErr_Occurred()) {
			PyErr_Format(PyExc_TypeError, "world.%s = float: KX_WorldInfo, expected a float", name.c_str());
			return PY_SET_ATTR_FAIL;
		}
		*(float *)((char *)world + found->offset) = CLAMPIS(number, found->min, found->max);
		compiled = found->compiled;
	}

	self->m_skyChanged = true;
	if (compiled) {
		self->m_skyDirty = true;
	}
	return PY_SET_ATTR_SUCCESS;
}

#ifdef USE_MATHUTILS

/*----------------------mathutils callbacks ----------------------------*/

/* subtype */
#define MATHUTILS_COL_CB_MIST_COLOR 1
#define MATHUTILS_COL_CB_HOR_COLOR 2
#define MATHUTILS_COL_CB_BACK_COLOR 3
#define MATHUTILS_COL_CB_AMBIENT_COLOR 4
#define MATHUTILS_COL_CB_ZEN_COLOR 5

static unsigned char mathutils_world_color_cb_index = -1; /* index for our callbacks */

static int mathutils_world_generic_check(BaseMathObject *bmo)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>EXP_PROXY_REF(bmo->cb_user);
	if (self == nullptr) {
		return -1;
	}

	return 0;
}

static int mathutils_world_color_get(BaseMathObject *bmo, int subtype)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>EXP_PROXY_REF(bmo->cb_user);
	if (self == nullptr) {
		return -1;
	}

	switch (subtype) {
		case MATHUTILS_COL_CB_MIST_COLOR:
		{
			self->m_mistcolor.Pack(bmo->data);
			break;
		}
		case MATHUTILS_COL_CB_HOR_COLOR:
		case MATHUTILS_COL_CB_BACK_COLOR:
		{
			self->m_horizoncolor.Pack(bmo->data);
			break;
		}
		case MATHUTILS_COL_CB_ZEN_COLOR:
		{
			self->m_zenithcolor.Pack(bmo->data);
			break;
		}
		case MATHUTILS_COL_CB_AMBIENT_COLOR:
		{
			self->m_ambientcolor.Pack(bmo->data);
			break;
		}
		default:
			return -1;
	}
	return 0;
}

static int mathutils_world_color_set(BaseMathObject *bmo, int subtype)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>EXP_PROXY_REF(bmo->cb_user);

	if (self == nullptr) {
		return -1;
	}

	switch (subtype) {
		case MATHUTILS_COL_CB_MIST_COLOR:
		{
			self->setMistColor(mt::vec3(bmo->data));
			break;
		}
		case MATHUTILS_COL_CB_HOR_COLOR:
		{
			self->setHorizonColor(mt::vec4(bmo->data));
			break;
		}
		case MATHUTILS_COL_CB_BACK_COLOR:
		{
			self->setHorizonColor(mt::vec4(bmo->data[0], bmo->data[1], bmo->data[2], 1.0f));
			break;
		}
		case MATHUTILS_COL_CB_ZEN_COLOR:
		{
			self->setZenithColor(mt::vec4(bmo->data));
			break;
		}
		case MATHUTILS_COL_CB_AMBIENT_COLOR:
		{
			self->setAmbientColor(mt::vec3(bmo->data));
			break;
		}
		default:
			return -1;
	}
	return 0;
}

static int mathutils_world_color_get_index(BaseMathObject *bmo, int subtype, int index)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>EXP_PROXY_REF(bmo->cb_user);

	if (self == nullptr) {
		return -1;
	}

	switch (subtype) {
		case MATHUTILS_COL_CB_MIST_COLOR:
		{
			bmo->data[index] = self->m_mistcolor[index];
			break;
		}
		case MATHUTILS_COL_CB_HOR_COLOR:
		case MATHUTILS_COL_CB_BACK_COLOR:
		{
			bmo->data[index] = self->m_horizoncolor[index];
			break;
		}
		case MATHUTILS_COL_CB_ZEN_COLOR:
		{
			bmo->data[index] = self->m_zenithcolor[index];
			break;
		}
		case MATHUTILS_COL_CB_AMBIENT_COLOR:
		{
			bmo->data[index] = self->m_ambientcolor[index];
			break;
		}
		default:
			return -1;
	}
	return 0;
}

static int mathutils_world_color_set_index(BaseMathObject *bmo, int subtype, int index)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>EXP_PROXY_REF(bmo->cb_user);

	if (self == nullptr) {
		return -1;
	}

	switch (subtype) {
		case MATHUTILS_COL_CB_MIST_COLOR:
		{
			mt::vec3 color = self->m_mistcolor;
			color[index] = bmo->data[index];
			self->setMistColor(color);
			break;
		}
		case MATHUTILS_COL_CB_HOR_COLOR:
		case MATHUTILS_COL_CB_BACK_COLOR:
		{
			mt::vec4 color = self->m_horizoncolor;
			color[index] = bmo->data[index];
			CLAMP(color[0], 0.0f, 1.0f);
			CLAMP(color[1], 0.0f, 1.0f);
			CLAMP(color[2], 0.0f, 1.0f);
			CLAMP(color[3], 0.0f, 1.0f);
			self->setHorizonColor(color);
			break;
		}
		case MATHUTILS_COL_CB_ZEN_COLOR:
		{
			mt::vec4 color = self->m_zenithcolor;
			color[index] = bmo->data[index];
			CLAMP(color[0], 0.0f, 1.0f);
			CLAMP(color[1], 0.0f, 1.0f);
			CLAMP(color[2], 0.0f, 1.0f);
			CLAMP(color[3], 0.0f, 1.0f);
			self->setZenithColor(color);
			break;
		}
		case MATHUTILS_COL_CB_AMBIENT_COLOR:
		{
			mt::vec3 color = self->m_ambientcolor;
			color[index] = bmo->data[index];
			self->setAmbientColor(color);
			break;
		}
		default:
			return -1;
	}
	return 0;
}

static Mathutils_Callback mathutils_world_color_cb = {
	mathutils_world_generic_check,
	mathutils_world_color_get,
	mathutils_world_color_set,
	mathutils_world_color_get_index,
	mathutils_world_color_set_index
};

void KX_WorldInfo_Mathutils_Callback_Init()
{
	// register mathutils callbacks, ok to run more than once.
	mathutils_world_color_cb_index = Mathutils_RegisterCallback(&mathutils_world_color_cb);
}
#endif // USE_MATHUTILS

PyObject *KX_WorldInfo::pyattr_get_mist_typeconst(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	PyObject *retvalue;

	const std::string& type = attrdef->m_name;

	if (type == "KX_MIST_QUADRATIC") {
		retvalue = PyLong_FromLong(KX_MIST_QUADRATIC);
	}
	else if (type == "KX_MIST_LINEAR") {
		retvalue = PyLong_FromLong(KX_MIST_LINEAR);
	}
	else if (type == "KX_MIST_INV_QUADRATIC") {
		retvalue = PyLong_FromLong(KX_MIST_INV_QUADRATIC);
	}
	else {
		/* should never happen */
		PyErr_SetString(PyExc_TypeError, "invalid mist type");
		retvalue = nullptr;
	}

	return retvalue;
}

PyObject *KX_WorldInfo::pyattr_get_mist_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Color_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_world_color_cb_index, MATHUTILS_COL_CB_MIST_COLOR);
#else
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);
	return PyObjectFrom(self->m_mistcolor);
#endif
}

int KX_WorldInfo::pyattr_set_mist_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);

	mt::vec3 color;
	if (PyVecTo(value, color)) {
		self->setMistColor(color);
		return PY_SET_ATTR_SUCCESS;
	}
	return PY_SET_ATTR_FAIL;
}

PyObject *KX_WorldInfo::pyattr_get_horizon_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{

#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 4,
		mathutils_world_color_cb_index, MATHUTILS_COL_CB_HOR_COLOR);
#else
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);
	return PyObjectFrom(self->m_horizoncolor);
#endif
}

int KX_WorldInfo::pyattr_set_horizon_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);

	mt::vec4 color;
	if (PyVecTo(value, color)) {
		self->setHorizonColor(color);
		return PY_SET_ATTR_SUCCESS;
	}
	return PY_SET_ATTR_FAIL;
}

PyObject *KX_WorldInfo::pyattr_get_background_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Color_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_world_color_cb_index, MATHUTILS_COL_CB_BACK_COLOR);
#else
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);
	return PyObjectFrom(self->m_horizoncolor.xyz());
#endif
}

int KX_WorldInfo::pyattr_set_background_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);

	mt::vec3 color;
	if (PyVecTo(value, color)) {
		self->setHorizonColor(mt::vec4(color[0], color[1], color[2], 1.0f));
		return PY_SET_ATTR_SUCCESS;
	}
	return PY_SET_ATTR_FAIL;
}

PyObject *KX_WorldInfo::pyattr_get_zenith_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{

#ifdef USE_MATHUTILS
	return Vector_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 4,
		mathutils_world_color_cb_index, MATHUTILS_COL_CB_ZEN_COLOR);
#else
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);
	return PyObjectFrom(self->m_zenithcolor);
#endif
}

int KX_WorldInfo::pyattr_set_zenith_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);

	mt::vec4 color;
	if (PyVecTo(value, color)) {
		self->setZenithColor(color);
		return PY_SET_ATTR_SUCCESS;
	}
	return PY_SET_ATTR_FAIL;
}

PyObject *KX_WorldInfo::pyattr_get_ambient_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
#ifdef USE_MATHUTILS
	return Color_CreatePyObject_cb(
		EXP_PROXY_FROM_REF_BORROW(self_v), 3,
		mathutils_world_color_cb_index, MATHUTILS_COL_CB_AMBIENT_COLOR);
#else
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);
	return PyObjectFrom(self->m_ambientcolor);
#endif
}

int KX_WorldInfo::pyattr_set_ambient_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_WorldInfo *self = static_cast<KX_WorldInfo *>(self_v);

	mt::vec3 color;
	if (PyVecTo(value, color)) {
		self->setAmbientColor(color);
		return PY_SET_ATTR_SUCCESS;
	}
	return PY_SET_ATTR_FAIL;
}

#endif /* WITH_PYTHON */
