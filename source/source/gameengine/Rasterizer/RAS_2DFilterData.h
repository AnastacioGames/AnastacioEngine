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
* Contributor(s): Pierluigi Grassi, Porteries Tristan.
*
* ***** END GPL LICENSE BLOCK *****
*/

#ifndef __RAS_2DFILTERDATA__
#define __RAS_2DFILTERDATA__

#include <vector>
#include <string>

class EXP_Value;

typedef struct BuildInFilters {
	/* Fxaa */
	bool useFxaa;
	float fxaa_edge_threshold;
	float fxaa_edge_threshold_min;
	float fxaa_subpix;
	int fxaa_search_steps;

	/* Film Grain (camera lens pass) */
	bool useGrain;
	float grain_strength;

	/* Bloom */
	bool useBloom;
	float bloom_threshold;
	float bloom_intensity;

	/* Tonemap */
	bool useTonemap;
	float tonemap_type;
	float tonemap_exposure;
	float tonemap_gamma;

	/* Light Scaterring */
	bool useLightScatter;
	int scatter_lod;
	float scatter_intensity;
	float scatter_threshold;
	float scatter_step_size;
	int scatter_step_max;

	/* SSR */
    /* Native SSGI: source slots are reserved at scene load, never inferred from display color. */
    bool useSSGI;
    int ssgi_slot;
    int ssgi_rays;
    int ssgi_steps;
    int ssgi_divisor;
    float ssgi_radius;
    float ssgi_strength;
    float ssgi_thickness;
    float ssgi_display[4]; /* exposure, gamma, Filmic contrast (0 = Standard), color management */

	bool useSSR;
	int ssr_step_max;
	int ssr_lod;
	float ssr_bias;
	float ssr_max_distance;

	/* SSAO */
	bool useSSAO;
	int ssao_samples;
	float ssao_strength;
	float ssao_distance;
	float ssao_attenuation;

	/* Rain (native World weather) */
	bool useRain;
	bool useRainDroplets;
	bool useRainRipple;
	bool useRainSplash;
	int rain_style;
	float rain_time;
	/* Volumetric fall offset (time * speed * 500), wrapped in double on the CPU. */
	float rain_fall_phase;
	float rain_intensity;
	float rain_density;
	float rain_speed;
	float rain_wind;
	float rain_darken;
	float rain_ripple;
	float rain_ripple_distance;
	float rain_ripple_min_up;
	float rain_ripple_normal;
	float rain_color[3];
	float rain_streak_width;
	float rain_splash_size;
	float rain_splash_rate;
	float rain_splash_intensity;
	float rain_splash_distance;
	float rain_ripple_size;
	float rain_ripple_rate;
	float rain_splash_normal;
	float rain_splash_min_up;
	/* Puddles: amount, size (m), darkness, reflection, distance, minimum upward normal */
	bool useRainPuddles;
	bool useRainPuddleSSR;
	/* Ripples only inside the puddle water (adds 1 to Puddle1.x) */
	bool useRainRipplePuddle;
	/* Splash only inside the puddle water (adds 2 to Puddle1.x) */
	bool useRainSplashPuddle;
	float rain_puddle_amount;
	float rain_puddle_size;
	float rain_puddle_darkness;
	float rain_puddle_reflection;
	float rain_puddle_distance;
	float rain_puddle_min_up;
	/* World horizon/zenith colors: what the puddles reflect */
	float rain_sky_horizon[3];
	float rain_sky_zenith[3];
	/* Ripples/Splash only on marked objects: mask texture (KX_RainSurfaceMask) and which
	 * effects use it (bit 1 ripples, bit 2 splash, bit 4 puddles; 0 = every surface). Refreshed every frame. */
	unsigned int rain_mask_texture;
	int rain_mask_flags;
	/* Lightning: flash, bolt brightness, bolt screen position (refreshed every frame) */
	float rain_lightning[4];

	/* Clouds (native World weather) */
	bool useClouds;
	float cloud_time;
	float cloud_coverage;
	float cloud_scale;
	float cloud_speed;
	float cloud_color[3];
	int cloud_mask; /* 1: Clouds, 2: Sky Layers, 4: Volumetric Clouds */
	float sky_layer_coverage, sky_layer_scale, sky_layer_speed;
	float sky_layer_color[3];
	/* Quality of Clouds and Sky Layers: noise octaves (1-8) and Sky Layers relief (0 = off) */
	int cloud_detail, sky_layer_detail;
	float sky_layer_relief;
	/* Volumetric Clouds (Stage 1 scaffolding: flat shading reusing the same FBM; real
	 * raymarch comes in Stage 2) */
	float vcloud_coverage, vcloud_scale, vcloud_speed;
	float vcloud_color[3];
	float vcloud_altitude, vcloud_thickness;
	float vcloud_density, vcloud_detail_scale;
	float vcloud_silver_intensity;
	float vcloud_shadow_strength;
	int vcloud_quality;
	bool vcloud_shadow_enable;
	/* World-space direction toward the sun (lamp's +Z), for the Stage 2 raymarch's self-shadow
	 * mini-march and Henyey-Greenstein silver lining; same source as the Light Scattering/Lens
	 * Flare sun position (KX_RenderPipeline::RenderFilters). */
	float vcloud_sundir[3];

	/* Volumetric Fog (native World weather), filled every frame by KX_RenderPipeline: layout in
	 * gpu_shader_vfog_lib.glsl. Shadow maps of up to 2 Spot lamps and the Sun (0 = none). */
	bool useVFog;
	enum { VFOG_DATA_VEC4 = 12 + 4 * 8 + 4, VFOG_MATS = 7, VFOG_SHADOWS = 3 };
	float vfog_data[VFOG_DATA_VEC4 * 4];
	float vfog_mats[16 * VFOG_MATS];
	unsigned int vfog_shadow_tex[VFOG_SHADOWS];

	/* Lens Flare (native World weather) */
	bool useLensFlare;
	float flare_time;
	float flare_scale;
	float flare_intensity;
	float flare_sun_x;
	float flare_sun_y;

	/* Camera FX (active camera game_fx): 6 vec4 of ge_CameraFX, see RAS_CameraDof2DFilter.glsl */
	float camera_fx[24];

} BuildInFilters;

/** This type is used to pack data received from a 2D Filter actuator and send it to
the RAS_2DFilterManager::AddFilter method, because the number of parameters needed by
a custom filter may become quite large and a function with a thousands paramters doesn't look
very good. So it's purely for readability.
*/
class RAS_2DFilterData
{
public:
	RAS_2DFilterData();
	virtual ~RAS_2DFilterData();

	/// The names of the properties of the game object that the shader may want to use as uniforms.
	std::vector<std::string> propertyNames;
	/// The KX_GameObject (or something else?) that provides the values for the uniforms named above.
	EXP_Value *gameObject;
	/// BuildInFilters, pass values to shader uniforms in gameengine.
	BuildInFilters buildInFilters;
	/// Enable/Disable mipmap in for rendered texture.
	bool mipmap;
	/// Should be a SCA_2DFilterActuator.FILTER_MODE value.
	int filterMode;
	/// In the original design this was bot the pass index and the unique identifier of the filter in the filter manager.
	unsigned int filterPassIndex;
	/// This is the shader program source code IF the filter is not a predefined one.
	std::string shaderText;
	/// Name of the Text datablock the custom shader came from, only used in error messages.
	std::string sourceName;
	/// Absolute path of the external file behind that Text, empty if the Text is internal.
	std::string sourcePath;
};

#endif // __RAS_2DFILTERDATA__
