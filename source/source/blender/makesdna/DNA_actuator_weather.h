/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file DNA_actuator_weather.h
 *  \ingroup DNA
 *
 * Tabela dos ACT_RUNTIME_PROP_WEATHER_* do Property actuator (modo Weather
 * Effects): caminho runtime ("weather.*", ver KX_WorldInfo::SetWeatherRuntimeProperty),
 * se o valor e Bool e a categoria mostrada na UI. Fora da lista de makesdna.
 */

#ifndef __DNA_ACTUATOR_WEATHER_H__
#define __DNA_ACTUATOR_WEATHER_H__

#include "DNA_actuator_types.h"

/* bPropertyActuator.runtime_enabled no modo Weather Effects */
#define ACT_WEATHER_CAT_RAIN       0
#define ACT_WEATHER_CAT_CLOUDS     1
#define ACT_WEATHER_CAT_LENS_FLARE 2
#define ACT_WEATHER_CAT_MIST       3
#define ACT_WEATHER_CAT_SPLASH     4
#define ACT_WEATHER_CAT_AURA       5
#define ACT_WEATHER_CAT_LIGHTNING  6
#define ACT_WEATHER_CAT_EARTHQUAKE 7
#define ACT_WEATHER_CAT_VFOG       8
#define ACT_WEATHER_CAT_VCLOUDS    9
#define ACT_WEATHER_CAT_MAX        ACT_WEATHER_CAT_VCLOUDS

typedef struct ActWeatherRuntimeInfo {
	int prop;
	const char *path;
	int is_bool;
	int category;
} ActWeatherRuntimeInfo;

static const ActWeatherRuntimeInfo act_weather_runtime_info[] = {
	{ACT_RUNTIME_PROP_WEATHER_RAIN_INTENSITY, "weather.rain_intensity", 0, ACT_WEATHER_CAT_RAIN},
	{ACT_RUNTIME_PROP_WEATHER_RAIN_DENSITY, "weather.rain_density", 0, ACT_WEATHER_CAT_RAIN},
	{ACT_RUNTIME_PROP_WEATHER_RAIN_SPEED, "weather.rain_speed", 0, ACT_WEATHER_CAT_RAIN},
	{ACT_RUNTIME_PROP_WEATHER_RAIN_WIND, "weather.rain_wind", 0, ACT_WEATHER_CAT_RAIN},
	{ACT_RUNTIME_PROP_WEATHER_RAIN_DARKEN, "weather.rain_darken", 0, ACT_WEATHER_CAT_RAIN},
	{ACT_RUNTIME_PROP_WEATHER_RIPPLE_INTENSITY, "weather.ripple_intensity", 0, ACT_WEATHER_CAT_RAIN},
	{ACT_RUNTIME_PROP_WEATHER_RAIN, "weather.rain", 1, ACT_WEATHER_CAT_RAIN},
	{ACT_RUNTIME_PROP_WEATHER_RIPPLES, "weather.ripples", 1, ACT_WEATHER_CAT_RAIN},
	{ACT_RUNTIME_PROP_WEATHER_CLOUDS, "weather.clouds", 1, ACT_WEATHER_CAT_CLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_CLOUD_COVERAGE, "weather.cloud_coverage", 0, ACT_WEATHER_CAT_CLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_CLOUD_SCALE, "weather.cloud_scale", 0, ACT_WEATHER_CAT_CLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_CLOUD_SPEED, "weather.cloud_speed", 0, ACT_WEATHER_CAT_CLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_LENS_FLARE, "weather.lens_flare", 1, ACT_WEATHER_CAT_LENS_FLARE},
	{ACT_RUNTIME_PROP_WEATHER_FLARE_SCALE, "weather.flare_scale", 0, ACT_WEATHER_CAT_LENS_FLARE},
	{ACT_RUNTIME_PROP_WEATHER_FLARE_INTENSITY, "weather.flare_intensity", 0, ACT_WEATHER_CAT_LENS_FLARE},
	{ACT_RUNTIME_PROP_WEATHER_MIST, "weather.mist", 1, ACT_WEATHER_CAT_MIST},
	{ACT_RUNTIME_PROP_WEATHER_MIST_INTENSITY, "weather.mist_intensity", 0, ACT_WEATHER_CAT_MIST},
	{ACT_RUNTIME_PROP_WEATHER_MIST_START, "weather.mist_start", 0, ACT_WEATHER_CAT_MIST},
	{ACT_RUNTIME_PROP_WEATHER_MIST_DEPTH, "weather.mist_depth", 0, ACT_WEATHER_CAT_MIST},
	{ACT_RUNTIME_PROP_WEATHER_MIST_HEIGHT, "weather.mist_height", 0, ACT_WEATHER_CAT_MIST},
	{ACT_RUNTIME_PROP_WEATHER_MIST_DENSITY, "weather.mist_density", 0, ACT_WEATHER_CAT_MIST},
	{ACT_RUNTIME_PROP_WEATHER_RAIN_STREAK_WIDTH, "weather.rain_streak_width", 0, ACT_WEATHER_CAT_RAIN},
	{ACT_RUNTIME_PROP_WEATHER_RIPPLE_NORMAL, "weather.ripple_normal", 0, ACT_WEATHER_CAT_RAIN},
	{ACT_RUNTIME_PROP_WEATHER_SPLASH, "weather.splash", 1, ACT_WEATHER_CAT_SPLASH},
	{ACT_RUNTIME_PROP_WEATHER_SPLASH_SIZE, "weather.splash_size", 0, ACT_WEATHER_CAT_SPLASH},
	{ACT_RUNTIME_PROP_WEATHER_SPLASH_RATE, "weather.splash_rate", 0, ACT_WEATHER_CAT_SPLASH},
	{ACT_RUNTIME_PROP_WEATHER_SPLASH_INTENSITY, "weather.splash_intensity", 0, ACT_WEATHER_CAT_SPLASH},
	{ACT_RUNTIME_PROP_WEATHER_SPLASH_DISTANCE, "weather.splash_distance", 0, ACT_WEATHER_CAT_SPLASH},
	{ACT_RUNTIME_PROP_WEATHER_AURA, "weather.aura", 1, ACT_WEATHER_CAT_AURA},
	{ACT_RUNTIME_PROP_WEATHER_AURA_SIZE, "weather.aura_size", 0, ACT_WEATHER_CAT_AURA},
	{ACT_RUNTIME_PROP_WEATHER_AURA_RATE, "weather.aura_rate", 0, ACT_WEATHER_CAT_AURA},
	{ACT_RUNTIME_PROP_WEATHER_AURA_INTENSITY, "weather.aura_intensity", 0, ACT_WEATHER_CAT_AURA},
	{ACT_RUNTIME_PROP_WEATHER_AURA_DISTANCE, "weather.aura_distance", 0, ACT_WEATHER_CAT_AURA},
	{ACT_RUNTIME_PROP_WEATHER_LIGHTNING, "weather.lightning", 1, ACT_WEATHER_CAT_LIGHTNING},
	{ACT_RUNTIME_PROP_WEATHER_LIGHTNING_RATE, "weather.lightning_rate", 0, ACT_WEATHER_CAT_LIGHTNING},
	{ACT_RUNTIME_PROP_WEATHER_LIGHTNING_INTENSITY, "weather.lightning_intensity", 0, ACT_WEATHER_CAT_LIGHTNING},
	{ACT_RUNTIME_PROP_WEATHER_LIGHTNING_DISTANCE, "weather.lightning_distance", 0, ACT_WEATHER_CAT_LIGHTNING},
	{ACT_RUNTIME_PROP_WEATHER_LIGHTNING_WIDTH, "weather.lightning_width", 0, ACT_WEATHER_CAT_LIGHTNING},
	{ACT_RUNTIME_PROP_WEATHER_EARTHQUAKE, "weather.earthquake", 1, ACT_WEATHER_CAT_EARTHQUAKE},
	{ACT_RUNTIME_PROP_WEATHER_EARTHQUAKE_LEVEL, "weather.earthquake_level", 0, ACT_WEATHER_CAT_EARTHQUAKE},
	{ACT_RUNTIME_PROP_WEATHER_EARTHQUAKE_SCALE, "weather.earthquake_scale", 0, ACT_WEATHER_CAT_EARTHQUAKE},
	{ACT_RUNTIME_PROP_WEATHER_EARTHQUAKE_CAMERA, "weather.earthquake_camera", 0, ACT_WEATHER_CAT_EARTHQUAKE},
	{ACT_RUNTIME_PROP_WEATHER_DROPLETS, "weather.droplets", 1, ACT_WEATHER_CAT_RAIN},
	{ACT_RUNTIME_PROP_WEATHER_USE_SKY_LAYERS, "weather.use_sky_layers", 1, ACT_WEATHER_CAT_CLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_CLOUD_COLOR_R, "weather.cloud_color_r", 0, ACT_WEATHER_CAT_CLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_CLOUD_COLOR_G, "weather.cloud_color_g", 0, ACT_WEATHER_CAT_CLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_CLOUD_COLOR_B, "weather.cloud_color_b", 0, ACT_WEATHER_CAT_CLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_VFOG, "weather.vfog", 1, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_USE_LAMPS, "weather.vfog_use_lamps", 1, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_USE_SHAFTS, "weather.vfog_use_shafts", 1, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_USE_SUN_SHAFTS, "weather.vfog_use_sun_shafts", 1, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_VOLUMES_ONLY, "weather.vfog_volumes_only", 1, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_USE_WIND, "weather.vfog_use_wind", 1, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_USE_TIME_OF_DAY, "weather.vfog_use_time_of_day", 1, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_USE_LAYER, "weather.vfog_use_layer", 1, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_USE_REACH_CLOUDS, "weather.vfog_use_reach_clouds", 1, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_DENSITY, "weather.vfog_density", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_BASE, "weather.vfog_base", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_FALLOFF, "weather.vfog_falloff", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_DISTANCE, "weather.vfog_distance", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_NOISE_SCALE, "weather.vfog_noise_scale", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_NOISE_AMOUNT, "weather.vfog_noise_amount", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_SPEED, "weather.vfog_speed", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_ANISOTROPY, "weather.vfog_anisotropy", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_EDGE, "weather.vfog_edge", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_LIGHT_INTENSITY, "weather.vfog_light_intensity", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_SUN_INTENSITY, "weather.vfog_sun_intensity", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_SHAFT_INTENSITY, "weather.vfog_shaft_intensity", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_AMBIENT, "weather.vfog_ambient", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_MORNING_BOOST, "weather.vfog_morning_boost", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_WIND_DIRECTION, "weather.vfog_wind_direction", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_COLOR_R, "weather.vfog_color_r", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_COLOR_G, "weather.vfog_color_g", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_VFOG_COLOR_B, "weather.vfog_color_b", 0, ACT_WEATHER_CAT_VFOG},
	{ACT_RUNTIME_PROP_WEATHER_USE_VOLUMETRIC_CLOUDS, "weather.use_volumetric_clouds", 1, ACT_WEATHER_CAT_VCLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_VCLOUD_SHADOW_ENABLE, "weather.vcloud_shadow_enable", 1, ACT_WEATHER_CAT_VCLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_VCLOUD_COVERAGE, "weather.vcloud_coverage", 0, ACT_WEATHER_CAT_VCLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_VCLOUD_SCALE, "weather.vcloud_scale", 0, ACT_WEATHER_CAT_VCLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_VCLOUD_SPEED, "weather.vcloud_speed", 0, ACT_WEATHER_CAT_VCLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_VCLOUD_ALTITUDE, "weather.vcloud_altitude", 0, ACT_WEATHER_CAT_VCLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_VCLOUD_THICKNESS, "weather.vcloud_thickness", 0, ACT_WEATHER_CAT_VCLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_VCLOUD_DENSITY, "weather.vcloud_density", 0, ACT_WEATHER_CAT_VCLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_VCLOUD_DETAIL_SCALE, "weather.vcloud_detail_scale", 0, ACT_WEATHER_CAT_VCLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_VCLOUD_SILVER_INTENSITY, "weather.vcloud_silver_intensity", 0, ACT_WEATHER_CAT_VCLOUDS},
	{ACT_RUNTIME_PROP_WEATHER_VCLOUD_SHADOW_STRENGTH, "weather.vcloud_shadow_strength", 0, ACT_WEATHER_CAT_VCLOUDS},
	{-1, 0, 0, 0},
};

/* NULL se prop nao for um efeito de clima. */
static inline const ActWeatherRuntimeInfo *act_weather_runtime_find(int prop)
{
	const ActWeatherRuntimeInfo *info;
	for (info = act_weather_runtime_info; info->prop != -1; info++) {
		if (info->prop == prop) {
			return info;
		}
	}
	return 0;
}

/* Liga/desliga de cada categoria, escolhido ao trocar a categoria. */
static inline int act_weather_category_default(int category)
{
	switch (category) {
		case ACT_WEATHER_CAT_CLOUDS: return ACT_RUNTIME_PROP_WEATHER_CLOUDS;
		case ACT_WEATHER_CAT_LENS_FLARE: return ACT_RUNTIME_PROP_WEATHER_LENS_FLARE;
		case ACT_WEATHER_CAT_MIST: return ACT_RUNTIME_PROP_WEATHER_MIST;
		case ACT_WEATHER_CAT_SPLASH: return ACT_RUNTIME_PROP_WEATHER_SPLASH;
		case ACT_WEATHER_CAT_AURA: return ACT_RUNTIME_PROP_WEATHER_AURA;
		case ACT_WEATHER_CAT_LIGHTNING: return ACT_RUNTIME_PROP_WEATHER_LIGHTNING;
		case ACT_WEATHER_CAT_EARTHQUAKE: return ACT_RUNTIME_PROP_WEATHER_EARTHQUAKE;
		case ACT_WEATHER_CAT_VFOG: return ACT_RUNTIME_PROP_WEATHER_VFOG;
		case ACT_WEATHER_CAT_VCLOUDS: return ACT_RUNTIME_PROP_WEATHER_USE_VOLUMETRIC_CLOUDS;
		default: return ACT_RUNTIME_PROP_WEATHER_RAIN;
	}
}

#endif  /* __DNA_ACTUATOR_WEATHER_H__ */
