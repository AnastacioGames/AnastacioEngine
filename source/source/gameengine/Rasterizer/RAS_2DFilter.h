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

#ifndef __RAS_2DFILTER_H__
#define __RAS_2DFILTER_H__

#include "RAS_2DFilterData.h"
#include "RAS_Shader.h"

#include <memory>
#include <unordered_map>

class RAS_2DFilterManager;
class RAS_Rasterizer;
class RAS_ICanvas;
class RAS_OffScreen;
class RAS_2DFilterOffScreen;
class EXP_Value;

class RAS_2DFilter : public virtual RAS_Shader
{
public:
	enum PredefinedUniformType {
		RENDERED_TEXTURE_UNIFORM = 0,
		DATA_TEXTURES_UNIFORM,
		DEPTH_TEXTURE_UNIFORM,
		RENDERED_TEXTURE_WIDTH_UNIFORM,
		RENDERED_TEXTURE_HEIGHT_UNIFORM,
		TEXTURE_COORDINATE_OFFSETS_UNIFORM,

		GE_BLOOM_PARAMETERS_UNIFORM,
		GE_TONEMAP_PARAMETERS_UNIFORM,
		GE_LIGHTSCATTERING_SUNPOS_UNIFORM,
		GE_LIGHTSCATTERING_PARAMETERS_UNIFORM,
		GE_SSR_PARAMETERS_UNIFORM,
		GE_SSAO_PARAMETERS_UNIFORM,
		GE_VIEW_MATRIX_UNIFORM,
		GE_PROJECTION_MATRIX_UNIFORM,
		GE_INV_VIEW_MATRIX_UNIFORM,
		GE_INV_PROJECTION_MATRIX_UNIFORM,

		GE_RAIN_PARAMS1_UNIFORM,
		GE_RAIN_PARAMS2_UNIFORM,
		GE_RAIN_PARAMS3_UNIFORM,
		GE_RAIN_COLOR_UNIFORM,
		GE_RAIN_STYLE_UNIFORM,
		GE_RAIN_FALL_PHASE_UNIFORM,
		GE_RAIN_PARAMS4_UNIFORM,
		GE_RAIN_STREAK_WIDTH_UNIFORM,
		GE_RAIN_RIPPLE_NORMAL_UNIFORM,
		GE_RAIN_LIGHTNING_UNIFORM,
		GE_RAIN_PARAMS5_UNIFORM,
		GE_RAIN_MASK_UNIFORM,
		GE_RAIN_MASK_FLAGS_UNIFORM,
		GE_RAIN_PUDDLE1_UNIFORM,
		GE_RAIN_PUDDLE2_UNIFORM,
		GE_RAIN_SKY_HORIZON_UNIFORM,
		GE_RAIN_SKY_ZENITH_UNIFORM,
		GE_CLOUDS_PARAMS_UNIFORM,
		GE_CLOUDS_COLOR_UNIFORM,
		GE_CLOUDS_MASK_UNIFORM,
		GE_SKYLAYERS_PARAMS_UNIFORM,
		GE_SKYLAYERS_COLOR_UNIFORM,
		GE_CLOUDS_QUALITY_UNIFORM,
		GE_VCLOUDS_PARAMS1_UNIFORM,
		GE_VCLOUDS_PARAMS2_UNIFORM,
		GE_VCLOUDS_PARAMS3_UNIFORM,
		GE_VCLOUDS_COLOR_UNIFORM,
		GE_VCLOUDS_SUNDIR_UNIFORM,
		GE_LENSFLARE_PARAMS_UNIFORM,
		GE_LENSFLARE_SUNPOS_UNIFORM,
		GE_FXAA_PARAMETERS_UNIFORM,
		GE_CAMERAFX_UNIFORM,
        GE_SSGI_PARAMETERS_UNIFORM,
        GE_SSGI_DISPLAY_UNIFORM,

		/* Stable names for custom filters (SSAO/SSGI/SSR/TAA), see docs/2d-filters.md. */
		BGL_VIEW_MATRIX_UNIFORM,
		BGL_PROJECTION_MATRIX_UNIFORM,
		BGL_INV_VIEW_MATRIX_UNIFORM,
		BGL_INV_PROJECTION_MATRIX_UNIFORM,
		BGL_PREV_VIEW_PROJECTION_MATRIX_UNIFORM,
		BGL_RESOLUTION_UNIFORM,
		BGL_TIME_UNIFORM,
		BGL_FRAME_UNIFORM,
		BGL_PREVIOUS_TEXTURE_UNIFORM,

		/* Volumetric Clouds temporal reuse (history of the clouds filter's own output). */
		GE_CLOUDS_HISTORY_UNIFORM,
		GE_CLOUDS_HISTORY_DEPTH_UNIFORM,
		GE_CLOUDS_HISTORY_VALID_UNIFORM,
		GE_CLOUDS_HISTORY_VIEWPROJ_UNIFORM,

		/* Volumetric Fog (gpu_shader_vfog_lib.glsl): parameters/lamps, volume and shadow
		 * matrices, and the shadow maps of up to 2 Spot lamps casting light shafts. */
		GE_VFOG_DATA_UNIFORM,
		GE_VFOG_MATS_UNIFORM,
		GE_VFOG_SHADOW0_UNIFORM,
		GE_VFOG_SHADOW1_UNIFORM,

		MAX_PREDEFINED_UNIFORM_TYPE
	};

	/// Per frame values shared by every filter of a manager, set before each Render().
	struct FrameInputs {
		float time = 0.0f;
		int frame = 0;
		/// Previous frame final color (bgl_PreviousTexture), 0 while no filter asks for it.
		unsigned int previousTexture = 0;
		int previousTextureUnit = 17;
		mt::mat4 prevViewProjection = mt::mat4::Identity();

		/// Volumetric Clouds temporal reuse: color/depth the clouds filter output last time,
		/// with the view-projection it was drawn with (per history, not per manager call, so
		/// split screen cameras sharing the manager don't reuse each other's frames).
		unsigned int cloudHistory = 0;
		unsigned int cloudHistoryDepth = 0;
		int cloudHistoryUnit = 18;
		int cloudHistoryDepthUnit = 19;
		bool cloudHistoryValid = false;
		mt::mat4 cloudHistoryViewProjection = mt::mat4::Identity();
	};

protected:
	const FrameInputs *m_frameInputs = nullptr;
	/// Text name, external file path and last compile log of a custom filter.
	std::string m_sourceName;
	std::string m_sourcePath;
	std::string m_compileLog;
	/// Property names given at creation, kept to search them again after a recompile.
	std::vector<std::string> m_allProperties;

	int m_predefinedUniforms[MAX_PREDEFINED_UNIFORM_TYPE];

	std::vector<std::string> m_properties;
	std::vector<unsigned int> m_propertiesLoc;
	EXP_Value *m_gameObject;

	/// BuildIn Filters Params
	BuildInFilters m_buildInFilters;

	/// True if the uniform locations are updated with the current shader program/script.
	bool m_uniformInitialized;
	/// True if generate mipmap of input color texture.
	bool m_mipmap;
#ifdef __EMSCRIPTEN__
	/// Known native shaders with one color output; custom MRT shaders keep their routing.
	bool m_webSingleColorOutput = false;
#endif

	/** A set of vec2 coordinates that the shaders use to sample nearby pixels from incoming textures.
	The computation should be left to the glsl shader, I keep it for backward compatibility. */
	static const int TEXTURE_OFFSETS_SIZE = 18; //9 vec2 entries
	float m_textureOffsets[TEXTURE_OFFSETS_SIZE];
	/// Canvas size the offsets were computed for, recomputed on resize.
	int m_offsetsWidth;
	int m_offsetsHeight;

	std::unordered_map<unsigned short, std::pair<unsigned int, int> > m_textures;

	/// Custom off screen for special datas.
	std::unique_ptr<RAS_2DFilterOffScreen> m_offScreen;

	virtual bool LinkProgram();
	void ParseShaderProgram();
	void BindUniforms(RAS_Rasterizer *rasty, RAS_ICanvas *canvas, const float (&sun_screen_pos)[2]);
	void BindBuildInUniforms(RAS_ICanvas *canvas);
	void BindTextures(RAS_OffScreen *detphofs, RAS_OffScreen *colorofs);
	void UnbindTextures(RAS_OffScreen *detphofs, RAS_OffScreen *colorofs);
	void ComputeTextureOffsets(RAS_ICanvas *canvas);

public:
	RAS_2DFilter(RAS_2DFilterData& data);
	virtual ~RAS_2DFilter();

	bool GetMipmap() const;
	void SetMipmap(bool mipmap);

	/// True when the shader samples the depth texture (bgl_DepthTexture).
    bool UsesDataTextures() const { return m_predefinedUniforms[DATA_TEXTURES_UNIFORM] != -1; }
	bool UsesDepthTexture() const
	{
		return m_predefinedUniforms[DEPTH_TEXTURE_UNIFORM] != -1;
	}

	RAS_2DFilterOffScreen *GetOffScreen() const;
	void SetOffScreen(RAS_2DFilterOffScreen *offScreen);

	BuildInFilters *GetBuildInFilters();

	void SetFrameInputs(const FrameInputs *inputs)
	{
		m_frameInputs = inputs;
	}
	/// True when the shader samples the previous frame (bgl_PreviousTexture).
	bool UsesPreviousTexture() const
	{
		return m_predefinedUniforms[BGL_PREVIOUS_TEXTURE_UNIFORM] != -1;
	}
	/// True for the clouds filter when it reuses its previous output (ge_CloudsHistory).
	bool UsesCloudHistory() const
	{
		return m_predefinedUniforms[GE_CLOUDS_HISTORY_UNIFORM] != -1;
	}

	const std::string& GetSourceName() const
	{
		return m_sourceName;
	}
	const std::string& GetSourcePath() const
	{
		return m_sourcePath;
	}
	/// Driver info log of the last failed compile, empty after a successful one.
	const std::string& GetCompileLog() const
	{
		return m_compileLog;
	}

	/** Compile a new fragment source. On failure the previous program keeps running and the
	 * error is in GetCompileLog(). Uniforms set from Python must be set again on success.
	 */
	virtual bool Recompile(const std::string& fragment);

	/// Called by the filter manager when it has informations like the display size, a gl context...
	void Initialize(RAS_ICanvas *canvas);

	/** Render the filter.
	 * \param rasty The used rasterizer to call draw commands.
	 * \param canvas The canvas containing screen viewport.
	 * \param detphofs The off screen used only for the depth texture input,
	 * the same for all filters of a scene.
	 * \param colorofs The off screen used only for the color texture input, unique per filters.
	 * \param targetofs The off screen used to draw the filter to.
	 * \return The off screen to use as input for the next filter.
	 */
	RAS_OffScreen *Render(RAS_Rasterizer *rasty, RAS_ICanvas *canvas, RAS_OffScreen *detphofs,
			   RAS_OffScreen *colorofs, RAS_OffScreen *targetofs, const float (&sun_screen_pos)[2]);
};

#endif // __RAS_2DFILTER_H__

