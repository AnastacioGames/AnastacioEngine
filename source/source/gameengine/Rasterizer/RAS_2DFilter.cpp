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

#include "RAS_2DFilter.h"
#include "RAS_2DFilterManager.h"
#include "RAS_2DFilterOffScreen.h"
#include "RAS_Rasterizer.h"
#include "RAS_ICanvas.h"
#include "RAS_OffScreen.h"
#include "RAS_Rect.h"

#include "EXP_Value.h"

#include "GPU_glew.h"

#include <functional>
#include <memory>

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#endif

extern "C" {
extern char datatoc_RAS_VertexShader2DFilter_glsl[];
#ifdef __EMSCRIPTEN__
extern char datatoc_RAS_Fxaa2DFilter_glsl[];
extern char datatoc_RAS_Rain2DFilter_glsl[];
extern char datatoc_RAS_Clouds2DFilter_glsl[];
extern char datatoc_RAS_LensFlare2DFilter_glsl[];
extern char datatoc_RAS_Tonemaps2DFilter_glsl[];
extern char datatoc_RAS_SSAO2DFilter_glsl[];
extern char datatoc_RAS_Blur2DFilter_glsl[];
extern char datatoc_RAS_Sharpen2DFilter_glsl[];
extern char datatoc_RAS_Dilation2DFilter_glsl[];
extern char datatoc_RAS_Erosion2DFilter_glsl[];
extern char datatoc_RAS_Laplacian2DFilter_glsl[];
extern char datatoc_RAS_Sobel2DFilter_glsl[];
extern char datatoc_RAS_Prewitt2DFilter_glsl[];
extern char datatoc_RAS_GrayScale2DFilter_glsl[];
extern char datatoc_RAS_Sepia2DFilter_glsl[];
extern char datatoc_RAS_Invert2DFilter_glsl[];
extern char datatoc_RAS_OutLine2DFilter_glsl[];
extern char datatoc_RAS_Bloom2DFilter_Image_glsl[];
extern char datatoc_RAS_SSR_Blur2DFilter_glsl[];
extern char datatoc_RAS_LightScaterring_Image2DFilter_glsl[];
extern void emscripten_glDrawBuffers(GLsizei n, const GLenum *bufs);
#endif
}

namespace {
/// Runs a callback on scope exit, so a future early return added inside RAS_2DFilter::Render
/// (between a Bind/BindProg/BindTextures call and its matching Unbind/UnbindProg/UnbindTextures)
/// can't skip the restore and leave the shader program, textures or off screen bound past this
/// filter's draw call.
template<typename Fn>
class RAS_ScopeExit
{
	Fn m_fn;

public:
	explicit RAS_ScopeExit(Fn fn) : m_fn(std::move(fn)) {}
	~RAS_ScopeExit()
	{
		m_fn();
	}
};

template<typename Fn>
RAS_ScopeExit<Fn> MakeScopeExit(Fn fn)
{
	return RAS_ScopeExit<Fn>(std::move(fn));
}
}  // namespace

static std::string predefinedUniformsName[RAS_2DFilter::MAX_PREDEFINED_UNIFORM_TYPE] = {
	"bgl_RenderedTexture", // RENDERED_TEXTURE_UNIFORM
	"bgl_DataTextures[0]", // DATA_TEXTURES_UNIFORM
	"bgl_DepthTexture", // DEPTH_TEXTURE_UNIFORM
	"bgl_RenderedTextureWidth", // RENDERED_TEXTURE_WIDTH_UNIFORM
	"bgl_RenderedTextureHeight", // RENDERED_TEXTURE_HEIGHT_UNIFORM
	"bgl_TextureCoordinateOffset", // TEXTURE_COORDINATE_OFFSETS_UNIFORM

	"ge_BloomParams", // GE_BLOOM_PARAMETERS_UNIFORM
	"ge_TonemapParams", // GE_TONEMAP_PARAMETERS_UNIFORM
	"ge_LightScatterSunPos", // GE_LIGHTSCATTERING_SUNPOS_UNIFORM
	"ge_LightScatterParams", // GE_LIGHTSCATTERING_PARAMETERS_UNIFORM
	"ge_ssrparams", // GE_SSR_PARAMETERS_UNIFORM
	"ge_ssaoparams", // GE_SSAO_PARAMETERS_UNIFORM
	"unfviewmat", // GE_VIEW_MATRIX_UNIFORM
	"unfprojmat", // GE_PROJECTION_MATRIX_UNIFORM
	"unfinvviewmat", // GE_INV_VIEW_MATRIX_UNIFORM
	"unfinvprojmat", // GE_INV_PROJECTION_MATRIX_UNIFORM

	"ge_RainParams1", // GE_RAIN_PARAMS1_UNIFORM
	"ge_RainParams2", // GE_RAIN_PARAMS2_UNIFORM
	"ge_RainParams3", // GE_RAIN_PARAMS3_UNIFORM
	"ge_RainColor", // GE_RAIN_COLOR_UNIFORM
	"ge_RainStyle", // GE_RAIN_STYLE_UNIFORM
	"ge_CloudsParams", // GE_CLOUDS_PARAMS_UNIFORM
	"ge_CloudsColor", // GE_CLOUDS_COLOR_UNIFORM
	"ge_LensFlareParams", // GE_LENSFLARE_PARAMS_UNIFORM
	"ge_LensFlareSunPos" // GE_LENSFLARE_SUNPOS_UNIFORM
};

RAS_2DFilter::RAS_2DFilter(RAS_2DFilterData& data)
	:m_properties(data.propertyNames),
	m_gameObject(data.gameObject),
	m_buildInFilters(data.buildInFilters),
	m_uniformInitialized(false),
	m_mipmap(data.mipmap)
{
	for (unsigned int i = 0; i < TEXTURE_OFFSETS_SIZE; i++) {
		m_textureOffsets[i] = 0;
	}

	for (unsigned int i = 0; i < MAX_PREDEFINED_UNIFORM_TYPE; ++i) {
		m_predefinedUniforms[i] = -1;
	}

	if (!data.shaderText.empty()) {
		m_progs[VERTEX_PROGRAM] = std::string(datatoc_RAS_VertexShader2DFilter_glsl);
		m_progs[FRAGMENT_PROGRAM] = data.shaderText;

		LinkProgram();
	}
}

RAS_2DFilter::~RAS_2DFilter()
{
}

bool RAS_2DFilter::GetMipmap() const
{
	return m_mipmap;
}

void RAS_2DFilter::SetMipmap(bool mipmap)
{
	m_mipmap = mipmap;
}

RAS_2DFilterOffScreen *RAS_2DFilter::GetOffScreen() const
{
	return m_offScreen.get();
}

void RAS_2DFilter::SetOffScreen(RAS_2DFilterOffScreen *offScreen)
{
	m_offScreen.reset(offScreen);
}

BuildInFilters *RAS_2DFilter::GetBuildInFilters()
{
	return &m_buildInFilters;
}

void RAS_2DFilter::Initialize(RAS_ICanvas *canvas)
{
	/* The shader must be initialized at the first frame when the canvas is accesible.
	 * to solve this we initialize filter at the frist render frame. */
	if (!m_uniformInitialized) {
		ParseShaderProgram();
		ComputeTextureOffsets(canvas);
		m_uniformInitialized = true;
	}
}

RAS_OffScreen *RAS_2DFilter::Render(RAS_Rasterizer *rasty, RAS_ICanvas *canvas, RAS_OffScreen *depthofs,
                                    RAS_OffScreen *colorofs, RAS_OffScreen *targetofs, const float (&sun_screen_pos)[2])
{
	/* The off screen the filter rendered to. If the filter is invalid or uses a custom
	 * off screen the output off screen is the same as the input off screen. */
	RAS_OffScreen *outputofs = colorofs;
	if (!Ok()) {
		return outputofs;
	}

	/* The target off screen must be not the color input off screen, it can be the same as depth input
	 * screen because depth is unchanged. */
	BLI_assert(targetofs != colorofs);

	std::unique_ptr<RAS_ScopeExit<std::function<void()>>> offScreenRestore;
	if (m_offScreen) {
		if (!m_offScreen->Update(canvas)) {
			return outputofs;
		}

		m_offScreen->Bind(rasty);
		offScreenRestore.reset(new RAS_ScopeExit<std::function<void()>>(
			[this, rasty, canvas]() { m_offScreen->Unbind(rasty, canvas); }));
	}
	else {
		targetofs->Bind();
		outputofs = targetofs;
	}

	Initialize(canvas);

	BindProg();
	auto progRestore = MakeScopeExit([this]() { UnbindProg(); });

	BindTextures(depthofs, colorofs);
	// Destruction order (reverse of declaration) now unbinds textures, then the program, then the
	// off screen -- the original code unbound textures, then the off screen, then the program.
	// The three touch independent GL state (texture units, program object, framebuffer/viewport),
	// so the reordering has no observable effect.
	auto texturesRestore = MakeScopeExit([this, depthofs, colorofs]() { UnbindTextures(depthofs, colorofs); });

	BindUniforms(rasty, canvas, sun_screen_pos);

	Update(rasty, mt::mat4::Identity());

	ApplyShader();

#ifdef __EMSCRIPTEN__
	/* WebGL rejects a draw if an enabled attachment has no fragment output.
	 * Keep the other attachments intact and restore routing before unbinding. */
	GLenum savedDrawBuffers[8];
	GLint drawBufferCount = 0;
	if (m_webSingleColorOutput) {
		GLint framebuffer;
		glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &framebuffer);
		glGetIntegerv(GL_MAX_DRAW_BUFFERS, &drawBufferCount);
		drawBufferCount = framebuffer ? std::min(drawBufferCount, 8) : 1;
		for (int i = 0; i < drawBufferCount; ++i) {
			GLint buffer;
			glGetIntegerv(GL_DRAW_BUFFER0 + i, &buffer);
			savedDrawBuffers[i] = buffer;
		}
		emscripten_glDrawBuffers(1, savedDrawBuffers);
	}
	auto drawBuffersRestore = MakeScopeExit([&]() {
		if (drawBufferCount) {
			emscripten_glDrawBuffers(drawBufferCount, savedDrawBuffers);
		}
	});
#endif

	rasty->DrawOverlayPlane();

#ifdef __EMSCRIPTEN__
	if (EM_ASM_INT({ return (typeof window !== 'undefined' && window.RAS_2DFILTER_DEBUG) ? 1 : 0; })) {
		GLenum err = glGetError();
		GLint framebuffer = 0;
		glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &framebuffer);
		const std::string& frag = m_progs[FRAGMENT_PROGRAM];
		const char *name =
		    frag == datatoc_RAS_Fxaa2DFilter_glsl ? "FXAA" :
		    frag == datatoc_RAS_Rain2DFilter_glsl ? "RAIN" :
		    frag == datatoc_RAS_Clouds2DFilter_glsl ? "CLOUDS" :
		    frag == datatoc_RAS_LensFlare2DFilter_glsl ? "LENSFLARE" :
		    frag == datatoc_RAS_Tonemaps2DFilter_glsl ? "TONEMAPS" :
		    frag == datatoc_RAS_SSAO2DFilter_glsl ? "SSAO" :
		    frag == datatoc_RAS_Blur2DFilter_glsl ? "BLUR" :
		    frag == datatoc_RAS_Sharpen2DFilter_glsl ? "SHARPEN" :
		    frag == datatoc_RAS_Dilation2DFilter_glsl ? "DILATION" :
		    frag == datatoc_RAS_Erosion2DFilter_glsl ? "EROSION" :
		    frag == datatoc_RAS_Laplacian2DFilter_glsl ? "LAPLACIAN" :
		    frag == datatoc_RAS_Sobel2DFilter_glsl ? "SOBEL" :
		    frag == datatoc_RAS_Prewitt2DFilter_glsl ? "PREWITT" :
		    frag == datatoc_RAS_GrayScale2DFilter_glsl ? "GRAYSCALE" :
		    frag == datatoc_RAS_Sepia2DFilter_glsl ? "SEPIA" :
		    frag == datatoc_RAS_Invert2DFilter_glsl ? "INVERT" :
		    frag == datatoc_RAS_OutLine2DFilter_glsl ? "OUTLINE" :
		    frag == datatoc_RAS_Bloom2DFilter_Image_glsl ? "BLOOM_IMAGE" :
		    frag == datatoc_RAS_SSR_Blur2DFilter_glsl ? "SSR" :
		    frag == datatoc_RAS_LightScaterring_Image2DFilter_glsl ? "LIGHTSCATTER" :
		    "OTHER(custom/buffer)";
		printf("[web-filter] name=%s singleColorOutput=%d offScreen=%d framebuffer=%d drawBufferCount=%d "
		       "glError=0x%x\n",
		       name, (int)m_webSingleColorOutput, m_offScreen ? 1 : 0, framebuffer,
		       drawBufferCount, (unsigned int)err);
	}
#endif

	return outputofs;
}

bool RAS_2DFilter::LinkProgram()
{
	if (!RAS_Shader::LinkProgram()) {
		return false;
	}

	m_uniformInitialized = false;

#ifdef __EMSCRIPTEN__
	/* Compare complete sources on each link, including Python-triggered relinks.
	 * Weather uses CUSTOMFILTER too, so filterMode cannot identify native shaders.
	 * Covers every native 2D filter that draws straight onto the shared scene off
	 * screen (single "fragColor" output) instead of a private single-attachment
	 * off screen of its own (Bloom buf/bufH/bufV, SSR buffer and Light Scattering
	 * buffer already bind their own off screen via SetOffScreen(), so they never
	 * see the scene's extra draw buffers and don't need this list). */
	const std::string& fragment = m_progs[FRAGMENT_PROGRAM];
	m_webSingleColorOutput = fragment == datatoc_RAS_Fxaa2DFilter_glsl ||
	                        fragment == datatoc_RAS_Rain2DFilter_glsl ||
	                        fragment == datatoc_RAS_Clouds2DFilter_glsl ||
	                        fragment == datatoc_RAS_LensFlare2DFilter_glsl ||
	                        fragment == datatoc_RAS_Tonemaps2DFilter_glsl ||
	                        fragment == datatoc_RAS_SSAO2DFilter_glsl ||
	                        fragment == datatoc_RAS_Blur2DFilter_glsl ||
	                        fragment == datatoc_RAS_Sharpen2DFilter_glsl ||
	                        fragment == datatoc_RAS_Dilation2DFilter_glsl ||
	                        fragment == datatoc_RAS_Erosion2DFilter_glsl ||
	                        fragment == datatoc_RAS_Laplacian2DFilter_glsl ||
	                        fragment == datatoc_RAS_Sobel2DFilter_glsl ||
	                        fragment == datatoc_RAS_Prewitt2DFilter_glsl ||
	                        fragment == datatoc_RAS_GrayScale2DFilter_glsl ||
	                        fragment == datatoc_RAS_Sepia2DFilter_glsl ||
	                        fragment == datatoc_RAS_Invert2DFilter_glsl ||
	                        fragment == datatoc_RAS_OutLine2DFilter_glsl ||
	                        fragment == datatoc_RAS_Bloom2DFilter_Image_glsl ||
	                        fragment == datatoc_RAS_SSR_Blur2DFilter_glsl ||
	                        fragment == datatoc_RAS_LightScaterring_Image2DFilter_glsl;
#endif

	return true;
}

void RAS_2DFilter::ParseShaderProgram()
{
	// Parse shader to found used uniforms.
	for (unsigned int i = 0; i < MAX_PREDEFINED_UNIFORM_TYPE; ++i) {
		m_predefinedUniforms[i] = GetUniformLocation(predefinedUniformsName[i], false);
	}

	if (m_gameObject) {
		std::vector<std::string> foundProperties;
		for (const std::string& prop : m_properties) {
			const unsigned int loc = GetUniformLocation(prop, false);
			if (loc != -1) {
				m_propertiesLoc.push_back(loc);
				foundProperties.push_back(prop);
			}
		}
		m_properties = foundProperties;
	}
}

/* Fill the textureOffsets array with values used by the shaders to get texture samples
   of nearby fragments. Or vertices or whatever.*/
void RAS_2DFilter::ComputeTextureOffsets(RAS_ICanvas *canvas)
{
	const GLfloat texturewidth = (GLfloat)canvas->GetWidth();
	const GLfloat textureheight = (GLfloat)canvas->GetHeight();
	const GLfloat xInc = 1.0f / texturewidth;
	const GLfloat yInc = 1.0f / textureheight;

	for (int i = 0; i < 3; i++) {
		for (int j = 0; j < 3; j++) {
			m_textureOffsets[(((i * 3) + j) * 2) + 0] = (-1.0f * xInc) + ((GLfloat)i * xInc);
			m_textureOffsets[(((i * 3) + j) * 2) + 1] = (-1.0f * yInc) + ((GLfloat)j * yInc);
		}
	}
}

void RAS_2DFilter::BindTextures(RAS_OffScreen *depthofs, RAS_OffScreen *colorofs)
{
	if (m_predefinedUniforms[RENDERED_TEXTURE_UNIFORM] != -1) {
		colorofs->BindColorTexture(0, 9);
		if (m_mipmap) {
			colorofs->MipmapTextures();
		}
	}

	if (m_predefinedUniforms[DATA_TEXTURES_UNIFORM] != -1) {
		for (unsigned short i = 1, slots = colorofs->GetNumColorSlot(); i < slots; ++i) {
			colorofs->BindColorTexture(i, 9 + i);
		}
		if (m_mipmap) {
			colorofs->MipmapTextures();
		}
	}

	if (m_predefinedUniforms[DEPTH_TEXTURE_UNIFORM] != -1) {
		depthofs->BindDepthTexture(8);
	}

	// Bind custom textures.
	for (const auto& pair : m_textures) {
		glActiveTexture(GL_TEXTURE0 + pair.first);
		glBindTexture(pair.second.first, pair.second.second);
	}
}

void RAS_2DFilter::UnbindTextures(RAS_OffScreen *depthofs, RAS_OffScreen *colorofs)
{
	if (m_predefinedUniforms[RENDERED_TEXTURE_UNIFORM] != -1) {
		colorofs->UnbindColorTexture(0);
		if (m_mipmap) {
			colorofs->UnmipmapTextures();
		}
	}

	if (m_predefinedUniforms[DATA_TEXTURES_UNIFORM] != -1) {
		for (unsigned short i = 1, slots = colorofs->GetNumColorSlot(); i < slots; ++i) {
			colorofs->UnbindColorTexture(i);
		}
		if (m_mipmap) {
			colorofs->UnmipmapTextures();
		}
	}

	if (m_predefinedUniforms[DEPTH_TEXTURE_UNIFORM] != -1) {
		depthofs->UnbindDepthTexture();
	}

	// Unbind custom textures.
	for (const auto& pair : m_textures) {
		glActiveTexture(GL_TEXTURE0 + pair.first);
		glBindTexture(pair.second.first, 0);
	}

	glActiveTextureARB(GL_TEXTURE0);
}

void RAS_2DFilter::BindUniforms(RAS_Rasterizer *rasty, RAS_ICanvas *canvas, const float (&sun_screen_pos)[2])
{
	if (m_predefinedUniforms[GE_VIEW_MATRIX_UNIFORM] != -1) {
		SetUniform(m_predefinedUniforms[GE_VIEW_MATRIX_UNIFORM], rasty->GetViewMatrix());
	}
	if (m_predefinedUniforms[GE_PROJECTION_MATRIX_UNIFORM] != -1) {
		SetUniform(m_predefinedUniforms[GE_PROJECTION_MATRIX_UNIFORM], rasty->GetProjectionMatrix());
	}
	/* Precomputed once per draw here instead of via inverse() inside the Rain/Clouds
	 * fragment shaders, which were inverting these matrices on every single pixel. */
	if (m_predefinedUniforms[GE_INV_VIEW_MATRIX_UNIFORM] != -1) {
		SetUniform(m_predefinedUniforms[GE_INV_VIEW_MATRIX_UNIFORM], rasty->GetViewMatrix().Inverse());
	}
	if (m_predefinedUniforms[GE_INV_PROJECTION_MATRIX_UNIFORM] != -1) {
		SetUniform(m_predefinedUniforms[GE_INV_PROJECTION_MATRIX_UNIFORM], rasty->GetProjectionMatrix().Inverse());
	}
	if (m_predefinedUniforms[RENDERED_TEXTURE_UNIFORM] != -1) {
		SetUniform(m_predefinedUniforms[RENDERED_TEXTURE_UNIFORM], 9);
	}
	if (m_predefinedUniforms[DATA_TEXTURES_UNIFORM] != -1) {
		static const int units[] = {10, 11, 12, 13, 14, 15, 16};
		SetUniformiv(m_predefinedUniforms[DATA_TEXTURES_UNIFORM], RAS_Uniform::UNI_INT, units, sizeof(int) * 7, 7);
	}
	if (m_predefinedUniforms[DEPTH_TEXTURE_UNIFORM] != -1) {
		SetUniform(m_predefinedUniforms[DEPTH_TEXTURE_UNIFORM], 8);
	}
	if (m_predefinedUniforms[RENDERED_TEXTURE_WIDTH_UNIFORM] != -1) {
		// Bind rendered texture width.
		const unsigned int texturewidth = canvas->GetWidth();
		SetUniform(m_predefinedUniforms[RENDERED_TEXTURE_WIDTH_UNIFORM], (float)texturewidth);
	}
	if (m_predefinedUniforms[RENDERED_TEXTURE_HEIGHT_UNIFORM] != -1) {
		// Bind rendered texture height.
		const unsigned int textureheight = canvas->GetHeight();
		SetUniform(m_predefinedUniforms[RENDERED_TEXTURE_HEIGHT_UNIFORM], (float)textureheight);
	}
	if (m_predefinedUniforms[TEXTURE_COORDINATE_OFFSETS_UNIFORM] != -1) {
		// Bind texture offsets.
		SetUniformfv(m_predefinedUniforms[TEXTURE_COORDINATE_OFFSETS_UNIFORM], RAS_Uniform::UNI_FLOAT2, m_textureOffsets,
		             sizeof(float) * TEXTURE_OFFSETS_SIZE, TEXTURE_OFFSETS_SIZE / 2);
	}

	/* BuildIn Uniforms */
	if (m_predefinedUniforms[GE_BLOOM_PARAMETERS_UNIFORM] != -1) {
		float params[4] = {m_buildInFilters.bloom_intensity, m_buildInFilters.bloom_threshold,
						   (float)canvas->GetWidth(), (float)canvas->GetHeight()};
		SetUniformfv(m_predefinedUniforms[GE_BLOOM_PARAMETERS_UNIFORM], RAS_Uniform::UNI_FLOAT4, params, sizeof(float) * 4, 1);
	}

	if (m_predefinedUniforms[GE_TONEMAP_PARAMETERS_UNIFORM] != -1) {
		float params[3] = {m_buildInFilters.tonemap_type, m_buildInFilters.tonemap_exposure, m_buildInFilters.tonemap_gamma};
		SetUniformfv(m_predefinedUniforms[GE_TONEMAP_PARAMETERS_UNIFORM], RAS_Uniform::UNI_FLOAT3, params, sizeof(float) * 3, 1);
	}

	if (m_predefinedUniforms[GE_LIGHTSCATTERING_SUNPOS_UNIFORM] != -1) {
		float params[2] = {sun_screen_pos[0], sun_screen_pos[1]};
		SetUniformfv(m_predefinedUniforms[GE_LIGHTSCATTERING_SUNPOS_UNIFORM], RAS_Uniform::UNI_FLOAT2, params, sizeof(float) * 2, 1);
	}
	if (m_predefinedUniforms[GE_LIGHTSCATTERING_PARAMETERS_UNIFORM] != -1) {
		float params[4] = {(float)m_buildInFilters.scatter_step_max, m_buildInFilters.scatter_step_size, 
						   m_buildInFilters.scatter_threshold, m_buildInFilters.scatter_intensity};
		SetUniformfv(m_predefinedUniforms[GE_LIGHTSCATTERING_PARAMETERS_UNIFORM], RAS_Uniform::UNI_FLOAT4, params, sizeof(float) * 4, 1);
	}

	if (m_predefinedUniforms[GE_SSR_PARAMETERS_UNIFORM] != -1) {
		float params[3] = {(float)m_buildInFilters.ssr_step_max,
						   m_buildInFilters.ssr_bias, m_buildInFilters.ssr_max_distance};
		SetUniformfv(m_predefinedUniforms[GE_SSR_PARAMETERS_UNIFORM], RAS_Uniform::UNI_FLOAT3, params, sizeof(float) * 3, 1);
	}

	if (m_predefinedUniforms[GE_SSAO_PARAMETERS_UNIFORM] != -1) {
		float params[4] = {(float)m_buildInFilters.ssao_samples,
						   m_buildInFilters.ssao_strength, m_buildInFilters.ssao_distance, m_buildInFilters.ssao_attenuation};
		SetUniformfv(m_predefinedUniforms[GE_SSAO_PARAMETERS_UNIFORM], RAS_Uniform::UNI_FLOAT4, params, sizeof(float) * 4, 1);
	}

	if (m_predefinedUniforms[GE_RAIN_PARAMS1_UNIFORM] != -1) {
		float params[4] = {m_buildInFilters.rain_intensity, m_buildInFilters.rain_speed,
						   m_buildInFilters.rain_wind, m_buildInFilters.rain_darken};
		SetUniformfv(m_predefinedUniforms[GE_RAIN_PARAMS1_UNIFORM], RAS_Uniform::UNI_FLOAT4, params, sizeof(float) * 4, 1);
	}
	if (m_predefinedUniforms[GE_RAIN_PARAMS2_UNIFORM] != -1) {
		float params[4] = {m_buildInFilters.rain_ripple, m_buildInFilters.rain_time,
						   m_buildInFilters.useRainDroplets ? 1.0f : 0.0f, m_buildInFilters.useRainRipple ? 1.0f : 0.0f};
		SetUniformfv(m_predefinedUniforms[GE_RAIN_PARAMS2_UNIFORM], RAS_Uniform::UNI_FLOAT4, params, sizeof(float) * 4, 1);
	}
	if (m_predefinedUniforms[GE_RAIN_PARAMS3_UNIFORM] != -1) {
		float params[4] = {m_buildInFilters.rain_density, m_buildInFilters.rain_ripple_distance,
						   m_buildInFilters.rain_ripple_min_up, 0.0f};
		SetUniformfv(m_predefinedUniforms[GE_RAIN_PARAMS3_UNIFORM], RAS_Uniform::UNI_FLOAT4, params, sizeof(float) * 4, 1);
	}
	if (m_predefinedUniforms[GE_RAIN_COLOR_UNIFORM] != -1) {
		SetUniformfv(m_predefinedUniforms[GE_RAIN_COLOR_UNIFORM], RAS_Uniform::UNI_FLOAT3, m_buildInFilters.rain_color, sizeof(float) * 3, 1);
	}
	if (m_predefinedUniforms[GE_RAIN_STYLE_UNIFORM] != -1) {
		float style = (float)m_buildInFilters.rain_style;
		SetUniformfv(m_predefinedUniforms[GE_RAIN_STYLE_UNIFORM], RAS_Uniform::UNI_FLOAT, &style, sizeof(float), 1);
	}

	if (m_predefinedUniforms[GE_CLOUDS_PARAMS_UNIFORM] != -1) {
		float params[4] = {m_buildInFilters.cloud_coverage, m_buildInFilters.cloud_scale,
						   m_buildInFilters.cloud_speed, m_buildInFilters.cloud_time};
		SetUniformfv(m_predefinedUniforms[GE_CLOUDS_PARAMS_UNIFORM], RAS_Uniform::UNI_FLOAT4, params, sizeof(float) * 4, 1);
	}
	if (m_predefinedUniforms[GE_CLOUDS_COLOR_UNIFORM] != -1) {
		SetUniformfv(m_predefinedUniforms[GE_CLOUDS_COLOR_UNIFORM], RAS_Uniform::UNI_FLOAT3, m_buildInFilters.cloud_color, sizeof(float) * 3, 1);
	}

	if (m_predefinedUniforms[GE_LENSFLARE_PARAMS_UNIFORM] != -1) {
		float params[4] = {m_buildInFilters.flare_scale, m_buildInFilters.flare_intensity, m_buildInFilters.flare_time, 0.0f};
		SetUniformfv(m_predefinedUniforms[GE_LENSFLARE_PARAMS_UNIFORM], RAS_Uniform::UNI_FLOAT4, params, sizeof(float) * 4, 1);
	}
	if (m_predefinedUniforms[GE_LENSFLARE_SUNPOS_UNIFORM] != -1) {
		float params[2] = {m_buildInFilters.flare_sun_x, m_buildInFilters.flare_sun_y};
		SetUniformfv(m_predefinedUniforms[GE_LENSFLARE_SUNPOS_UNIFORM], RAS_Uniform::UNI_FLOAT2, params, sizeof(float) * 2, 1);
	}

	/* GameObject Uniforms */
	for (unsigned int i = 0, size = m_properties.size(); i < size; ++i) {
		const std::string& prop = m_properties[i];
		unsigned int uniformLoc = m_propertiesLoc[i];

		EXP_Value *property = m_gameObject->GetProperty(prop);

		if (!property) {
			continue;
		}

		switch (property->GetValueType()) {
			case VALUE_INT_TYPE:
			{
				SetUniform(uniformLoc, (int)property->GetNumber());
				break;
			}
			case VALUE_FLOAT_TYPE:
			{
				SetUniform(uniformLoc, (float)property->GetNumber());
				break;
			}
			default:
			{
				break;
			}
		}
	}
}
