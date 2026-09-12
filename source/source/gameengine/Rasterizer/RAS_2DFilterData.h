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
	int rain_style;
	float rain_time;
	float rain_intensity;
	float rain_speed;
	float rain_wind;
	float rain_darken;
	float rain_ripple;
	float rain_color[3];

	/* Clouds (native World weather) */
	bool useClouds;
	float cloud_time;
	float cloud_coverage;
	float cloud_scale;
	float cloud_speed;
	float cloud_color[3];

	/* Lens Flare (native World weather) */
	bool useLensFlare;
	float flare_time;
	float flare_scale;
	float flare_intensity;
	float flare_sun_x;
	float flare_sun_y;

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
};

#endif // __RAS_2DFILTERDATA__
