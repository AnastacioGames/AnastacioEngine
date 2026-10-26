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

/** \file gameengine/Rasterizer/RAS_2DFilterManager.cpp
 *  \ingroup bgerast
 */

#include "RAS_ICanvas.h"
#include "RAS_Rasterizer.h"
#include "RAS_OffScreen.h"
#include "RAS_2DFilterManager.h"
#include "RAS_2DFilter.h"
#include "RAS_2DFilterOffScreen.h"

#include "CM_Message.h"

#include "GPU_glew.h"

#include <algorithm>
#include <climits>

extern "C" {
	extern char datatoc_RAS_Blur2DFilter_glsl[];
	extern char datatoc_RAS_Sharpen2DFilter_glsl[];
	extern char datatoc_RAS_Dilation2DFilter_glsl[];
	extern char datatoc_RAS_Erosion2DFilter_glsl[];
	extern char datatoc_RAS_Fxaa2DFilter_glsl[];
	extern char datatoc_RAS_Laplacian2DFilter_glsl[];
	extern char datatoc_RAS_Sobel2DFilter_glsl[];
	extern char datatoc_RAS_Prewitt2DFilter_glsl[];
	extern char datatoc_RAS_GrayScale2DFilter_glsl[];
	extern char datatoc_RAS_Sepia2DFilter_glsl[];
	extern char datatoc_RAS_Invert2DFilter_glsl[];
	extern char datatoc_RAS_OutLine2DFilter_glsl[];

	extern char datatoc_RAS_Tonemaps2DFilter_glsl[];
	extern char datatoc_RAS_SSAO2DFilter_glsl[];
  }

void (*RAS_2DFilterManager::ProfilePassHook)(int pass) = nullptr;

RAS_2DFilterManager::RAS_2DFilterManager(BuildInFilters filters)
{
	if (filters.useTonemap) {
		RAS_2DFilterData tonemapData;
		tonemapData.filterMode = FILTER_MODE::FILTER_TONEMAP;
		tonemapData.filterPassIndex = FILTERPASS_TONEMAP;
		tonemapData.gameObject = nullptr;
		tonemapData.mipmap = false;
		tonemapData.propertyNames = {};
		tonemapData.buildInFilters = filters;
		tonemapData.shaderText = datatoc_RAS_Tonemaps2DFilter_glsl;
		RAS_2DFilter *tonemapFilter = new RAS_2DFilter(tonemapData);
		m_filters[tonemapData.filterPassIndex] = tonemapFilter;
		// By default enable the filter.
		tonemapFilter->SetEnabled(true);
	}
	if (filters.useFxaa) {
		RAS_2DFilterData fxaaData;
		fxaaData.filterMode = FILTER_MODE::FILTER_FXAA;
		fxaaData.filterPassIndex = FILTERPASS_FXAA;
		fxaaData.gameObject = nullptr;
		fxaaData.mipmap = false;
		fxaaData.propertyNames = {};
		fxaaData.buildInFilters = filters;
		fxaaData.shaderText = datatoc_RAS_Fxaa2DFilter_glsl;
		RAS_2DFilter *fxaaFilter = new RAS_2DFilter(fxaaData);
		m_filters[fxaaData.filterPassIndex] = fxaaFilter;
		// By default enable the filter.
		fxaaFilter->SetEnabled(true);
	}
	if (filters.useSSAO) {
		RAS_2DFilterData ssaoData;
		ssaoData.filterMode = FILTER_MODE::FILTER_SSAO;
		ssaoData.filterPassIndex = FILTERPASS_SSAO;
		ssaoData.gameObject = nullptr;
		ssaoData.mipmap = false;
		ssaoData.propertyNames = {};
		ssaoData.buildInFilters = filters;
		ssaoData.shaderText = datatoc_RAS_SSAO2DFilter_glsl;
		RAS_2DFilter *ssrFilter = new RAS_2DFilter(ssaoData);
		m_filters[ssaoData.filterPassIndex] = ssrFilter;
		// By default enable the filter.
		ssrFilter->SetEnabled(true);
	}
}

RAS_2DFilterManager::~RAS_2DFilterManager()
{
	for (const RAS_PassTo2DFilter::value_type& pair : m_filters) {
		RAS_2DFilter *filter = pair.second;
		delete filter;
	}
	if (m_frameInputs.previousTexture) {
		glDeleteTextures(1, &m_frameInputs.previousTexture);
	}
	if (m_frameInputs.cloudHistory) {
		glDeleteTextures(1, &m_frameInputs.cloudHistory);
		glDeleteTextures(1, &m_frameInputs.cloudHistoryDepth);
	}
	for (TemporalHistory &history : m_temporalHistories) {
		glDeleteTextures(1, &history.color);
		glDeleteTextures(1, &history.depth);
	}
}

void RAS_2DFilterManager::SetFrameTime(float time)
{
	m_frameInputs.time = time;
}

/* Copy the viewport rectangle of the bound read frame buffer into the same rectangle of the
 * bound texture (same coordinates as bgl_RenderedTexture), clamped to both sizes. With split
 * screen / the game embedded in the editor each camera only refreshes its own area. */
static void CopyViewportRect(const int viewport[4], int texWidth, int texHeight, int readWidth, int readHeight)
{
	const int x = std::max(0, viewport[0]);
	const int y = std::max(0, viewport[1]);
	const int w = std::min(viewport[0] + viewport[2], std::min(texWidth, readWidth)) - x;
	const int h = std::min(viewport[1] + viewport[3], std::min(texHeight, readHeight)) - y;
	if (w > 0 && h > 0) {
		glCopyTexSubImage2D(GL_TEXTURE_2D, 0, x, y, x, y, w, h);
	}
}

unsigned int RAS_2DFilterManager::RenderOrderKey(unsigned int passIndex)
{
	/* HDR effects (rain, clouds, volumetric fog, camera DOF) before Tonemap, FXAA right after
	 * it (it expects LDR/gamma input), then lens flare and lens FX. Indices themselves never
	 * change, so saved files, custom filters and Python passIndex keep working. */
	switch (passIndex) {
		case FILTERPASS_RAIN:         return 15;
		case FILTERPASS_CLOUDS:       return 16;
		case FILTERPASS_VFOG:         return 17;
		case FILTERPASS_VFOG_IMAGE:   return 18;
		/* DOF reduction, then the last bloom slot holding the half resolution DOF gather
		 * (KX_2DFilterManager), right before the DOF pass that blends it. */
		case FILTERPASS_CAMERA_DOF_REDUCE: return 19;
		case FILTERPASS_BLOOM + 7:    return 20;
		case FILTERPASS_CAMERA_DOF:   return 21;
		case FILTERPASS_TONEMAP:      return 22;
		case FILTERPASS_FXAA:         return 23;
		case FILTERPASS_LENSFLARE:    return 24;
		case FILTERPASS_CAMERA_LENS:  return 25;
		/* The compositor tree is the last step of the frame, after the custom filters too. */
		case FILTERPASS_COMPOSITOR:   return UINT_MAX;
		default: // 0..14 unchanged, custom filters (>= 25) after the lens pass
			return (passIndex < FILTERPASS_RAIN) ? passIndex : passIndex + 1;
	}
}

void RAS_2DFilterManager::UpdatePreviousTexture(RAS_Rasterizer *rasty, RAS_ICanvas *canvas, RAS_OffScreen *finalofs,
                                                const int viewport[4])
{
#ifdef __EMSCRIPTEN__
	// WebGL can't copy an RGBA8 frame buffer into a float texture, bgl_PreviousTexture stays unbound.
	(void)rasty;
	(void)canvas;
	(void)finalofs;
	(void)viewport;
#else
	const int width = finalofs->GetWidth();
	const int height = finalofs->GetHeight();
	if (!m_frameInputs.previousTexture) {
		GLint maxUnits = 0;
		glGetIntegerv(GL_MAX_TEXTURE_IMAGE_UNITS, &maxUnits);
		// Unit 17 is past every unit the filters use; on small GPUs share the last custom unit.
		m_frameInputs.previousTextureUnit = (maxUnits > 17) ? 17 : 7;
		glGenTextures(1, &m_frameInputs.previousTexture);
	}
	glBindTexture(GL_TEXTURE_2D, m_frameInputs.previousTexture);
	if (width != m_previousWidth || height != m_previousHeight) {
		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA16F, width, height, 0, GL_RGBA, GL_FLOAT, nullptr);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
		m_previousWidth = width;
		m_previousHeight = height;
	}

	RAS_OffScreen *readofs = finalofs;
	if (finalofs->GetSamples()) {
		// A multisampled frame buffer can't be copied to a texture, resolve it first.
		readofs = canvas->GetOffScreen(RAS_OffScreen::RAS_OFFSCREEN_FILTER0);
		rasty->DrawOffScreen(finalofs, readofs);
	}
	readofs->Bind();
	glBindTexture(GL_TEXTURE_2D, m_frameInputs.previousTexture);
	CopyViewportRect(viewport, width, height, (int)readofs->GetWidth(), (int)readofs->GetHeight());
	glBindTexture(GL_TEXTURE_2D, 0);
	finalofs->Bind();
#endif
}

void RAS_2DFilterManager::UpdateCloudHistory(RAS_Rasterizer *rasty, RAS_OffScreen *cloudofs, RAS_OffScreen *depthofs,
                                             const int viewport[4])
{
#ifdef __EMSCRIPTEN__
	// No depth texture copy on WebGL: the clouds filter keeps marching every pixel.
	(void)rasty;
	(void)cloudofs;
	(void)depthofs;
	(void)viewport;
#else
	// A multisampled frame buffer can't be copied to a texture; the filter chain targets
	// resolved off screens, so this only skips an unusual setup (full march every frame).
	if (cloudofs->GetSamples() || depthofs->GetSamples()) {
		m_frameInputs.cloudHistoryValid = false;
		return;
	}
	const int width = cloudofs->GetWidth();
	const int height = cloudofs->GetHeight();
	if (!m_frameInputs.cloudHistory) {
		GLint maxUnits = 0;
		glGetIntegerv(GL_MAX_TEXTURE_IMAGE_UNITS, &maxUnits);
		if (maxUnits <= 19) {
			// Not enough texture units for units 18/19: no reuse, every pixel marches.
			m_frameInputs.cloudHistoryValid = false;
			return;
		}
		glGenTextures(1, &m_frameInputs.cloudHistory);
		glGenTextures(1, &m_frameInputs.cloudHistoryDepth);
	}
	const bool resized = (width != m_cloudHistoryWidth || height != m_cloudHistoryHeight);
	if (resized) {
		// The old contents don't match the new size; only the copy below makes it valid again.
		m_frameInputs.cloudHistoryValid = false;
		glBindTexture(GL_TEXTURE_2D, m_frameInputs.cloudHistory);
		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA16F, width, height, 0, GL_RGBA, GL_FLOAT, nullptr);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
		glBindTexture(GL_TEXTURE_2D, m_frameInputs.cloudHistoryDepth);
		glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT24, width, height, 0, GL_DEPTH_COMPONENT, GL_FLOAT, nullptr);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_MODE, GL_NONE);
		m_cloudHistoryWidth = width;
		m_cloudHistoryHeight = height;
	}

	cloudofs->Bind();
	glBindTexture(GL_TEXTURE_2D, m_frameInputs.cloudHistory);
	CopyViewportRect(viewport, width, height, width, height);
	depthofs->Bind();
	glBindTexture(GL_TEXTURE_2D, m_frameInputs.cloudHistoryDepth);
	CopyViewportRect(viewport, width, height, (int)depthofs->GetWidth(), (int)depthofs->GetHeight());
	glBindTexture(GL_TEXTURE_2D, 0);
	cloudofs->Bind();

	m_frameInputs.cloudHistoryViewProjection = rasty->GetProjectionMatrix() * rasty->GetViewMatrix();
	for (int i = 0; i < 4; ++i) {
		m_cloudHistoryViewport[i] = viewport[i];
	}
	m_frameInputs.cloudHistoryValid = true;
#endif
}

static void InitHistoryTexture(unsigned int tex, bool depth, int width, int height)
{
	glBindTexture(GL_TEXTURE_2D, tex);
	if (depth) {
		glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT24, width, height, 0, GL_DEPTH_COMPONENT, GL_FLOAT, nullptr);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_MODE, GL_NONE);
	}
	else {
		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA16F, width, height, 0, GL_RGBA, GL_FLOAT, nullptr);
	}
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, depth ? GL_NEAREST : GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, depth ? GL_NEAREST : GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
}

/// Camera cut / teleport: the history is thrown away instead of being reprojected.
static bool ViewProjectionJumped(const mt::mat4 &current, const float previous[16])
{
	float cur[16];
	current.Pack(cur);
	float diff = 0.0f, norm = 0.0f;
	for (int i = 0; i < 16; ++i) {
		diff += (cur[i] - previous[i]) * (cur[i] - previous[i]);
		norm += cur[i] * cur[i];
	}
	return diff > 0.09f * norm; // more than 30% relative change (Frobenius)
}

void RAS_2DFilterManager::RenderTemporalResolve(RAS_2DFilter *filter, RAS_Rasterizer *rasty, RAS_ICanvas *canvas,
                                                RAS_OffScreen *depthofs, RAS_OffScreen *colorofs, RAS_OffScreen *targetofs,
                                                const float (&sun_screen_pos)[2], const int viewport[4])
{
	RAS_2DFilter *resolve = filter->GetTemporalResolve();
	RAS_2DFilterOffScreen *resolveofs = resolve->GetOffScreen();
	if (!resolve->Ok() || !resolveofs) {
		return;
	}

	m_frameInputs.temporalHistory = 0;
	m_frameInputs.temporalHistoryDepth = 0;
	m_frameInputs.temporalHistoryValid = false;

#ifndef __EMSCRIPTEN__
	if (m_temporalSupported == -1) {
		GLint maxUnits = 0;
		glGetIntegerv(GL_MAX_TEXTURE_IMAGE_UNITS, &maxUnits);
		// Units 20/21 are past the clouds history (18/19) and bgl_PreviousTexture (17).
		m_temporalSupported = (maxUnits > 21) ? 1 : 0;
		// A/B comparison and perf: RANGE_TEMPORAL_OFF=1 keeps the resolve as a pass through.
		const char *off = getenv("RANGE_TEMPORAL_OFF");
		if (off && off[0] == '1') {
			m_temporalSupported = 0;
		}
	}
	const bool supported = (m_temporalSupported == 1) && depthofs->GetSamples() == 0;
	{
		static int debugLeft = -1;
		if (debugLeft == -1) {
			const char *dbg = getenv("RANGE_TEMPORAL_DEBUG");
			debugLeft = (dbg && dbg[0] == '1') ? 8 : 0;
		}
		if (debugLeft > 0) {
			debugLeft--;
			GLint maxUnits = 0;
			glGetIntegerv(GL_MAX_TEXTURE_IMAGE_UNITS, &maxUnits);
			if (FILE *f = fopen("range_temporal_debug.log", "a")) {
				fprintf(f, "TEMPORAL effect=%d maxUnits=%d samples=%d supported=%d\n", filter->GetTemporalEffect(),
				        (int)maxUnits, (int)depthofs->GetSamples(), supported ? 1 : 0);
				fclose(f);
			}
		}
	}
#else
	// WebGL can't copy a float frame buffer into a texture: no accumulation, the resolve passes through.
	const bool supported = false;
#endif

	TemporalHistory *history = nullptr;
	const mt::mat4 viewProjection = rasty->GetProjectionMatrix() * rasty->GetViewMatrix();
	if (supported) {
		const int effect = filter->GetTemporalEffect();
		for (TemporalHistory &entry : m_temporalHistories) {
			if (entry.effect == effect && std::equal(viewport, viewport + 4, entry.viewport)) {
				history = &entry;
				break;
			}
		}
		if (!history) {
			// Bounded like the previous view-projections: a few split screen viewports per effect.
			if (m_temporalHistories.size() >= 8) {
				glDeleteTextures(1, &m_temporalHistories.front().color);
				glDeleteTextures(1, &m_temporalHistories.front().depth);
				m_temporalHistories.erase(m_temporalHistories.begin());
			}
			m_temporalHistories.push_back(TemporalHistory());
			history = &m_temporalHistories.back();
			history->effect = effect;
			std::copy(viewport, viewport + 4, history->viewport);
			glGenTextures(1, &history->color);
			glGenTextures(1, &history->depth);
		}

		/* The resolve off screen follows the canvas; Update() here so a resize is seen before
		 * comparing sizes (Render() calls it again, no rebuild then). */
		resolveofs->Update(canvas);
		const int width = (int)resolveofs->GetWidth();
		const int height = (int)resolveofs->GetHeight();
		const int dwidth = (int)depthofs->GetWidth();
		const int dheight = (int)depthofs->GetHeight();
		if (width != history->width || height != history->height) {
			InitHistoryTexture(history->color, false, width, height);
			history->width = width;
			history->height = height;
			history->valid = false;
		}
		if (dwidth != history->depthWidth || dheight != history->depthHeight) {
			InitHistoryTexture(history->depth, true, dwidth, dheight);
			history->depthWidth = dwidth;
			history->depthHeight = dheight;
			history->valid = false;
		}
		glBindTexture(GL_TEXTURE_2D, 0);
		// Not resolved for a while (effect off, other scene): the old buffer is stale.
		if (m_frameInputs.frame - history->lastFrame > 8 || ViewProjectionJumped(viewProjection, history->viewProjection)) {
			history->valid = false;
		}

		m_frameInputs.temporalHistory = history->color;
		m_frameInputs.temporalHistoryDepth = history->depth;
		m_frameInputs.temporalHistoryValid = history->valid;
		if (history->valid) {
			m_frameInputs.temporalHistoryViewProjection = mt::mat4(history->viewProjection);
		}
	}

	resolve->SetFrameInputs(&m_frameInputs);
	resolve->Render(rasty, canvas, depthofs, colorofs, targetofs, sun_screen_pos);

	if (history) {
		// Commit: the resolved buffer and the depth it was resolved against.
		resolveofs->Bind(rasty);
		glReadBuffer(GL_COLOR_ATTACHMENT0);
		glBindTexture(GL_TEXTURE_2D, history->color);
		glCopyTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 0, 0, history->width, history->height);
		resolveofs->Unbind(rasty, canvas);
		depthofs->Bind();
		glBindTexture(GL_TEXTURE_2D, history->depth);
		CopyViewportRect(viewport, history->depthWidth, history->depthHeight, history->depthWidth, history->depthHeight);
		glBindTexture(GL_TEXTURE_2D, 0);

		viewProjection.Pack(history->viewProjection);
		history->lastFrame = m_frameInputs.frame;
		history->valid = true;
	}
	m_frameInputs.temporalHistory = 0;
	m_frameInputs.temporalHistoryDepth = 0;
	m_frameInputs.temporalHistoryValid = false;
}

RAS_2DFilter *RAS_2DFilterManager::EnsureTonemapFilter(const BuildInFilters& filters)
{
	RAS_2DFilter *filter = GetFilterPass(FILTERPASS_TONEMAP, true);
	if (filter) {
		return filter;
	}

	RAS_2DFilterData tonemapData;
	tonemapData.filterMode = FILTER_MODE::FILTER_TONEMAP;
	tonemapData.filterPassIndex = FILTERPASS_TONEMAP;
	tonemapData.gameObject = nullptr;
	tonemapData.mipmap = false;
	tonemapData.propertyNames = {};
	tonemapData.buildInFilters = filters;
	tonemapData.shaderText = datatoc_RAS_Tonemaps2DFilter_glsl;

	filter = new RAS_2DFilter(tonemapData);
	m_filters[FILTERPASS_TONEMAP] = filter;

	return filter;
}

RAS_2DFilter *RAS_2DFilterManager::EnsureSSAOFilter(const BuildInFilters& filters)
{
	RAS_2DFilter *filter = GetFilterPass(FILTERPASS_SSAO, true);
	if (filter) {
		return filter;
	}

	RAS_2DFilterData ssaoData;
	ssaoData.filterMode = FILTER_MODE::FILTER_SSAO;
	ssaoData.filterPassIndex = FILTERPASS_SSAO;
	ssaoData.gameObject = nullptr;
	ssaoData.mipmap = false;
	ssaoData.propertyNames = {};
	ssaoData.buildInFilters = filters;
	ssaoData.shaderText = datatoc_RAS_SSAO2DFilter_glsl;

	filter = new RAS_2DFilter(ssaoData);
	m_filters[FILTERPASS_SSAO] = filter;

	return filter;
}

RAS_2DFilter *RAS_2DFilterManager::EnsureFxaaFilter(const BuildInFilters& filters)
{
	RAS_2DFilter *filter = GetFilterPass(FILTERPASS_FXAA, true);
	if (filter) {
		return filter;
	}

	RAS_2DFilterData fxaaData;
	fxaaData.filterMode = FILTER_MODE::FILTER_FXAA;
	fxaaData.filterPassIndex = FILTERPASS_FXAA;
	fxaaData.gameObject = nullptr;
	fxaaData.mipmap = false;
	fxaaData.propertyNames = {};
	fxaaData.buildInFilters = filters;
	fxaaData.shaderText = datatoc_RAS_Fxaa2DFilter_glsl;

	filter = new RAS_2DFilter(fxaaData);
	m_filters[FILTERPASS_FXAA] = filter;

	return filter;
}

bool RAS_2DFilterManager::SetBuiltinFilterEnabled(FILTER_MODE mode, bool enabled)
{
	BuildInFilters filters = {};
	RAS_2DFilter *filter = nullptr;

	switch (mode) {
		case FILTER_FXAA:
			filter = EnsureFxaaFilter(filters);
			break;
		case FILTER_TONEMAP:
			filters.tonemap_exposure = 2.2f;
			filters.tonemap_gamma = 1.0f;
			filter = EnsureTonemapFilter(filters);
			break;
		case FILTER_SSAO:
			filters.ssao_samples = 16;
			filters.ssao_strength = 4.0f;
			filters.ssao_distance = 1.0f;
			filters.ssao_attenuation = 1.0f;
			filter = EnsureSSAOFilter(filters);
			break;
		default:
			return false;
	}

	filter->SetEnabled(enabled);
	return true;
}

RAS_2DFilter *RAS_2DFilterManager::AddFilter(RAS_2DFilterData& filterData, bool use_reserved)
{
	RAS_2DFilter *filter = CreateFilter(filterData);
	int index = use_reserved ? filterData.filterPassIndex : filterData.filterPassIndex + reservedPassIndex;
	m_filters[index] = filter;
	// By default enable the filter.
	filter->SetEnabled(true);

	return filter;
}

void RAS_2DFilterManager::RemoveFilterPass(unsigned int passIndex)
{
	RAS_PassTo2DFilter::iterator it = m_filters.find(passIndex + reservedPassIndex);
	if (it != m_filters.end()) {
		delete it->second;
		m_filters.erase(it);
	}
}

void RAS_2DFilterManager::RemoveReservedFilterPass(unsigned int passIndex)
{
	RAS_PassTo2DFilter::iterator it = m_filters.find(passIndex);
	if (it != m_filters.end()) {
		delete it->second;
		m_filters.erase(it);
	}
}

RAS_2DFilter *RAS_2DFilterManager::GetFilterPass(unsigned int passIndex, bool use_reserved)
{
	unsigned int index = use_reserved ? passIndex : passIndex + reservedPassIndex;
	RAS_PassTo2DFilter::iterator it = m_filters.find(index);
	return (it != m_filters.end()) ? it->second : nullptr;
}

RAS_OffScreen *RAS_2DFilterManager::RenderFilters(RAS_Rasterizer *rasty, RAS_ICanvas *canvas, RAS_OffScreen *inputofs, RAS_OffScreen *targetofs, const float (&sun_screen_pos)[2])
{
	/* Camera FX passes stay built and are only toggled off, so the map is rarely empty.
	 * When no pass would draw, skip the chain instead of copying the full screen every frame. */
	bool anyActive = false;
	for (const auto &pair : m_filters) {
		if (pair.second->Ok()) {
			anyActive = true;
			break;
		}
	}
	if (!anyActive) {
		// No active filters, discard.
		return inputofs;
	}

	rasty->Disable(RAS_Rasterizer::RAS_DEPTH_TEST);
	rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_DISABLED);
	rasty->Disable(RAS_Rasterizer::RAS_BLEND);
	rasty->Disable(RAS_Rasterizer::RAS_ALPHA_TEST);

	rasty->SetLines(false);

	RAS_OffScreen *previousofs = inputofs;

	/* Set source off screen to RAS_OFFSCREEN_FILTER0 in case of multisample and blit,
	 * else keep the original source off screen. */
	if (inputofs->GetSamples()) {
		previousofs = canvas->GetOffScreen(RAS_OffScreen::RAS_OFFSCREEN_FILTER0);
		if (ProfilePassHook) {
			ProfilePassHook(-1);
		}
		/* Resolve the extra attachments (SSGI/SSR G-buffer, user attachments) only when an active
		 * filter samples bgl_DataTextures: each one is a full screen multisample resolve. */
		bool needData = false;
		for (const auto &pair : m_filters) {
			if (pair.second->Ok()) {
				pair.second->Initialize(canvas);
				if (pair.second->UsesDataTextures()) {
					needData = true;
					break;
				}
			}
		}
		inputofs->Blit(previousofs, true, needData ? -1 : 1);
		previousofs->Bind();
		if (ProfilePassHook) {
			ProfilePassHook(-2);
		}
	}

	// The filter color input off screen, changed for each filters.
	RAS_OffScreen *colorofs;
	// The filter depth input off scree, unchanged for each filters.
	RAS_OffScreen *depthofs = previousofs;

	/* Render order: the map is keyed by pass index, RenderOrderKey() remaps the reserved
	 * passes (see the header). Small list, rebuilt per call. */
	std::vector<std::pair<unsigned int, RAS_2DFilter *> > ordered(m_filters.begin(), m_filters.end());
	std::stable_sort(ordered.begin(), ordered.end(),
	                 [](const std::pair<unsigned int, RAS_2DFilter *> &a, const std::pair<unsigned int, RAS_2DFilter *> &b) {
		                 return RenderOrderKey(a.first) < RenderOrderKey(b.first);
	                 });
	// Used to know if a filter is the last of the chain.
	const auto pend = std::prev(ordered.end());

	++m_frameInputs.frame;
	bool usesPrevious = false;

	/* The clouds history only matches this render if it came from the same viewport (split
	 * screen cameras share this manager) at the same size. */
	int viewport[4];
	glGetIntegerv(GL_VIEWPORT, viewport);
	const bool historyValid = m_frameInputs.cloudHistoryValid;
	m_frameInputs.cloudHistoryValid = historyValid && m_cloudHistoryWidth == (int)previousofs->GetWidth() &&
	                                  m_cloudHistoryHeight == (int)previousofs->GetHeight() &&
	                                  std::equal(viewport, viewport + 4, m_cloudHistoryViewport);

	/* Previous view-projection of this viewport (cameras sharing the manager don't get each
	 * other's); not valid on its first frame, so filters see zero motion instead of Identity. */
	PrevViewProjection *prevVP = nullptr;
	for (PrevViewProjection &entry : m_prevViewProjections) {
		if (std::equal(viewport, viewport + 4, entry.viewport)) {
			prevVP = &entry;
			break;
		}
	}
	m_frameInputs.prevViewProjectionValid = (prevVP != nullptr);
	if (prevVP) {
		m_frameInputs.prevViewProjection = mt::mat4(prevVP->matrix);
	}

	if (ProfilePassHook) {
		ProfilePassHook(-1);
	}
	for (auto it = ordered.begin(), end = ordered.end(); it != end; ++it) {
		RAS_2DFilter *filter = it->second;
		filter->SetFrameInputs(&m_frameInputs);

		/* Assign the previous off screen to the input off screen. At the first render it's the
		 * input off screen sent to RenderFilters. */
		colorofs = previousofs;

		/* Computing the filter targeted off screen: the targeted off screen for the last filter,
		 * else the next filter off screen compared to the input off screen. The target must never
		 * be an off screen the filter reads: drawing into the color input gives tile shaped garbage
		 * (rows shifted in blocks), and drawing into the depth owner is a feedback loop rejected
		 * by WebGL. With multisamples the depth lives in FILTER0, so the FILTER0/FILTER1 ping pong
		 * can run out of free off screens; then the eye off screen targeted by the last filter
		 * serves as the third one (the copy below reaches targetofs if needed). */
		/* The uniforms a filter samples are only known after its first Initialize(). Without this
		 * the first frame saw usesDepth == false and could target the depth owner. */
		if (filter->Ok()) {
			filter->Initialize(canvas);
		}
		const bool usesDepth = filter->UsesDepthTexture() || filter->UsesDataTextures();
		auto isFree = [colorofs, depthofs, usesDepth](RAS_OffScreen *ofs) {
			return ofs != colorofs && !(usesDepth && ofs == depthofs);
		};
		RAS_OffScreen *candidates[4] = {
			(it == pend) ? targetofs : canvas->GetOffScreen(RAS_OffScreen::NextFilterOffScreen(colorofs->GetType())),
			canvas->GetOffScreen(RAS_OffScreen::RAS_OFFSCREEN_FILTER0),
			canvas->GetOffScreen(RAS_OffScreen::RAS_OFFSCREEN_FILTER1),
			(targetofs->GetSamples() == 0) ? targetofs : nullptr
		};
		RAS_OffScreen *ftargetofs = candidates[0];
		for (RAS_OffScreen *ofs : candidates) {
			if (ofs && isFree(ofs)) {
				ftargetofs = ofs;
				break;
			}
		}

		/* Get the output off screen of the filter, could be the same as the input off screen
		 * if no modifications were made to the targeted off screen.
		 * This output off screen is used for the next filter as input off screen */
		previousofs = filter->Render(rasty, canvas, depthofs, colorofs, ftargetofs, sun_screen_pos);
		if (ProfilePassHook) {
			ProfilePassHook(it->first);
		}
		if (filter->Ok() && filter->GetTemporalResolve() && filter->GetOffScreen()) {
			RenderTemporalResolve(filter, rasty, canvas, depthofs, colorofs, ftargetofs, sun_screen_pos, viewport);
		}
		usesPrevious = usesPrevious || (filter->Ok() && filter->UsesPreviousTexture());
		// Only Volumetric Clouds (mask bit 4) reuses frames; Clouds/Sky Layers alone don't pay the copy.
		if (filter->Ok() && filter->UsesCloudHistory() && (filter->GetBuildInFilters()->cloud_mask & 4) &&
		    previousofs != colorofs)
		{
			UpdateCloudHistory(rasty, previousofs, depthofs, viewport);
		}
	}

	// The last filter doesn't use its own off screen and didn't render to the targeted off screen ?
	if (previousofs != targetofs) {
		// Render manually to the targeted off screen as the last filter didn't do it for us.
		targetofs->Bind();
		rasty->DrawOffScreen(previousofs, targetofs);
	}

	// Opt-in: nothing is allocated or copied until a filter samples bgl_PreviousTexture.
	if (usesPrevious) {
		UpdatePreviousTexture(rasty, canvas, targetofs, viewport);
	}
	if (!prevVP) {
		// Bounded: a handful of split screen viewports; a resized window adds a new rect.
		if (m_prevViewProjections.size() >= 8) {
			m_prevViewProjections.erase(m_prevViewProjections.begin());
		}
		m_prevViewProjections.push_back(PrevViewProjection());
		prevVP = &m_prevViewProjections.back();
		std::copy(viewport, viewport + 4, prevVP->viewport);
	}
	(rasty->GetProjectionMatrix() * rasty->GetViewMatrix()).Pack(prevVP->matrix);

	rasty->Enable(RAS_Rasterizer::RAS_DEPTH_TEST);
	rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_ENABLED);

	return targetofs;
}

RAS_2DFilter *RAS_2DFilterManager::CreateFilter(RAS_2DFilterData& filterData)
{
	RAS_2DFilter *result = nullptr;
	std::string shaderSource;
	switch (filterData.filterMode) {
		case RAS_2DFilterManager::FILTER_MOTIONBLUR:
		{
			break;
		}
		case RAS_2DFilterManager::FILTER_BLUR:
		{
			shaderSource = datatoc_RAS_Blur2DFilter_glsl;
			break;
		}
		case RAS_2DFilterManager::FILTER_SHARPEN:
		{
			shaderSource = datatoc_RAS_Sharpen2DFilter_glsl;
			break;
		}
		case RAS_2DFilterManager::FILTER_DILATION:
		{
			shaderSource = datatoc_RAS_Dilation2DFilter_glsl;
			break;
		}
		case RAS_2DFilterManager::FILTER_EROSION:
		{
			shaderSource = datatoc_RAS_Erosion2DFilter_glsl;
			break;
		}
		case RAS_2DFilterManager::FILTER_LAPLACIAN:
		{
			shaderSource = datatoc_RAS_Laplacian2DFilter_glsl;
			break;
		}
		case RAS_2DFilterManager::FILTER_SOBEL:
		{
			shaderSource = datatoc_RAS_Sobel2DFilter_glsl;
			break;
		}
		case RAS_2DFilterManager::FILTER_PREWITT:
		{
			shaderSource = datatoc_RAS_Prewitt2DFilter_glsl;
			break;
		}
		case RAS_2DFilterManager::FILTER_GRAYSCALE:
		{
			shaderSource = datatoc_RAS_GrayScale2DFilter_glsl;
			break;
		}
		case RAS_2DFilterManager::FILTER_SEPIA:
		{
			shaderSource = datatoc_RAS_Sepia2DFilter_glsl;
			break;
		}
		case RAS_2DFilterManager::FILTER_INVERT:
		{
			shaderSource = datatoc_RAS_Invert2DFilter_glsl;
			break;
        }
        case RAS_2DFilterManager::FILTER_OUTLINE:
        {
            shaderSource = datatoc_RAS_OutLine2DFilter_glsl;
            break;
        }
	}
	if (shaderSource.empty()) {
		if (filterData.filterMode == RAS_2DFilterManager::FILTER_CUSTOMFILTER) {
			result = NewFilter(filterData);
		}
		else {
			CM_Error("cannot create filter for mode: " << filterData.filterMode << ".");
		}
	}
	else {
		filterData.shaderText = shaderSource;
		result = NewFilter(filterData);
	}
	return result;
}
