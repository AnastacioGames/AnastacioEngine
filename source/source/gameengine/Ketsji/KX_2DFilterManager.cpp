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
 * Contributor(s): Ulysse Martin, Tristan Porteries.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_2DFilterManager.cpp
 *  \ingroup ketsji
 */

#include "KX_2DFilterManager.h"

#include <cmath>
#include "RAS_ICanvas.h"
#include "RAS_WebGLCompat.h"

#include "CM_Message.h"

#include "KX_Camera.h"
#include "KX_Scene.h"
#include "KX_WorldInfo.h"
#include "KX_GameObject.h"
#include "KX_Globals.h"
#include "KX_EngineProfiler.h"
#include "KX_CompositorFilter.h"
#include "DNA_camera_types.h"
#include "DNA_scene_types.h" // SCENE_FX_FXAA_* defaults
#include "BLI_utildefines.h"
#include "BLI_fileops.h"
#include "MEM_guardedalloc.h"
#include "PIL_time.h"

#include <algorithm>
#include <cmath>

extern "C" {
    extern char datatoc_RAS_SSGI2DFilter_glsl[];
    extern char datatoc_RAS_SSGIImage2DFilter_glsl[];
	extern char datatoc_RAS_Bloom2DFilter_Down_glsl[];
	extern char datatoc_RAS_Bloom2DFilter_Up_glsl[];
	extern char datatoc_RAS_Bloom2DFilter_Image_glsl[];
	extern char datatoc_RAS_SSAO2DFilter_glsl[];
	extern char datatoc_RAS_SSAO_Image2DFilter_glsl[];

	extern char datatoc_RAS_SSR2DFilter_glsl[];
	extern char datatoc_RAS_SSR_Blur2DFilter_glsl[];

	extern char datatoc_RAS_LightScaterring_Buffer2DFilter_glsl[];
	extern char datatoc_RAS_LightScaterring_Image2DFilter_glsl[];

	extern char datatoc_RAS_Rain2DFilter_glsl[];
	extern char datatoc_RAS_Clouds2DFilter_glsl[];
	extern char datatoc_RAS_VolumetricFog2DFilter_glsl[];
	extern char datatoc_RAS_VolumetricFogImage2DFilter_glsl[];
	extern char datatoc_gpu_shader_vfog_lib_glsl[];
	extern char datatoc_RAS_Temporal2DFilter_glsl[];
	extern char datatoc_RAS_LensFlare2DFilter_glsl[];
	extern char datatoc_RAS_CameraDof2DFilter_glsl[];
	extern char datatoc_RAS_CameraLens2DFilter_glsl[];
}

/* The 8 reserved slots FILTERPASS_BLOOM .. +7 (5..12) are shared since the dual filter bloom only
 * needs 6: 5 is the SSAO composite (runs right after the SSAO trace at 4), 6..11 the bloom and 12
 * the half resolution DOF gather (RenderOrderKey() runs it just before FILTERPASS_CAMERA_DOF). */
enum {
	PASS_SSAO_IMAGE = RAS_2DFilterManager::FILTERPASS_BLOOM,
	PASS_BLOOM_FIRST = RAS_2DFilterManager::FILTERPASS_BLOOM + 1,
	PASS_BLOOM_COUNT = 6,
	PASS_BLOOM_IMAGE = PASS_BLOOM_FIRST + PASS_BLOOM_COUNT - 1,
	PASS_CAMERA_DOF_HALF = RAS_2DFilterManager::FILTERPASS_BLOOM + 7
};

/// RANGE_PROFILE: GPU time of every filter pass ("filter.rain", "filter.vfog"...);
/// "filter.prepare" is what runs before the first pass (rain masks, Camera FX update), "filter.resolve"
/// the multisample blit into the filter input (pass -2).
static void kx_profile_filter_pass(int pass)
{
	if (!KX_EngineProfiler::Enabled()) {
		return;
	}
	static int ids[258] = {0};
	const int slot = (pass == -2) ? 257 : (pass < 0) ? 256 : std::min(pass, 255);
	if (!ids[slot]) {
		static const char *const names[] = {
			/* 5 is the SSAO composite and 12 the half resolution DOF (see the slot constants below). */
			"ssgi", "ssgi_image", "ssr", "ssr_blur", "ssao", "ssao_image", "bloom_down0", "bloom_down1",
			"bloom_down2", "bloom_down3", "bloom_up", "bloom_image", "camera_dof_half", "lightscatter", "lightscatter_image", "fxaa", "tonemap", "rain", "clouds",
			"vfog", "vfog_image", "lensflare", "camera_dof", "camera_lens", "camera_dof_reduce", "compositor"};
		static std::string storage[258];
		if (pass == -2) {
			storage[slot] = "filter.resolve";
		}
		else if (pass < 0) {
			storage[slot] = "filter.prepare";
		}
		else if (pass < (int)(sizeof(names) / sizeof(names[0]))) {
			storage[slot] = std::string("filter.") + names[pass];
		}
		else {
			storage[slot] = "filter.custom" + std::to_string(pass);
		}
		ids[slot] = KX_EngineProfiler::Register(storage[slot].c_str());
	}
	KX_EngineProfiler::GpuStamp(ids[slot]);
}

KX_2DFilterManager::KX_2DFilterManager(RAS_ICanvas *canvas, BuildInFilters filters) :
	RAS_2DFilterManager(filters), m_canvas(canvas),
	m_useGrain(filters.useGrain), m_grainStrength(filters.grain_strength), m_sceneFilters(filters)
{
	ProfilePassHook = kx_profile_filter_pass;
	/* This location doesn't seem very good to me but it works fine here, we need to generate the KX_2DFilter to have offscreen and not RAS_* */
	/* Only for Range legacy, the code can be deprecated after Range 2.0+ */
	EnsureSSAOFilters(filters);
	EnsureBloomFilters(filters);
    EnsureSSGIFilters(filters);

	// Need to be done before bloom passes
	EnsureSSRFilters(filters);

	EnsureLightScatterFilters(filters);

	EnsureRainFilters(filters);
	EnsureCloudsFilters(filters);
	EnsureVFogFilters(filters);
	EnsureLensFlareFilters(filters);
}


KX_2DFilterManager::~KX_2DFilterManager()
{
}

bool KX_2DFilterManager::SetBuiltinFilterEnabled(FILTER_MODE mode, bool enabled)
{
#ifndef __EMSCRIPTEN__
	if (mode == FILTER_SSAO) {
		// Half resolution trace + composite (the base class would add the single full resolution pass).
		BuildInFilters filters = {};
		filters.useSSAO = true;
		filters.ssao_samples = 16;
		filters.ssao_strength = 4.0f;
		filters.ssao_distance = 1.0f;
		filters.ssao_attenuation = 1.0f;
		EnsureSSAOFilters(filters);
		for (int pass : {(int)FILTERPASS_SSAO, (int)PASS_SSAO_IMAGE}) {
			if (RAS_2DFilter *filter = GetFilterPass(pass, true)) {
				filter->SetEnabled(enabled);
			}
		}
		return true;
	}
#endif
	if (RAS_2DFilterManager::SetBuiltinFilterEnabled(mode, enabled)) {
		return true;
	}

	BuildInFilters filters = {};
	int firstPass = 0;
	int lastPass = 0;

	switch (mode) {
		case FILTER_BLOOM:
			filters.useBloom = true;
			filters.bloom_intensity = 2.0f;
			filters.bloom_threshold = 0.75f;
			EnsureBloomFilters(filters);
			firstPass = PASS_BLOOM_FIRST;
			lastPass = PASS_BLOOM_IMAGE;
			break;
		case FILTER_LIGHTSCATTER:
			filters.useLightScatter = true;
			filters.scatter_lod = 4;
			filters.scatter_step_max = 32;
			filters.scatter_step_size = 0.15f;
			filters.scatter_threshold = 0.75f;
			filters.scatter_intensity = 0.2f;
			EnsureLightScatterFilters(filters);
			firstPass = FILTERPASS_LIGHTSCATTER;
			lastPass = FILTERPASS_LIGHTSCATTER + 1;
			break;
		case FILTER_SSR:
			filters.useSSR = true;
			filters.ssr_lod = 2;
			filters.ssr_step_max = 16;
			filters.ssr_bias = 3.0f;
			filters.ssr_max_distance = 100.0f;
			EnsureSSRFilters(filters);
			firstPass = FILTERPASS_SSR;
			lastPass = FILTERPASS_SSR_BLUR;
			break;
		default:
			return false;
	}

	for (int pass = firstPass; pass <= lastPass; ++pass) {
		RAS_2DFilter *filter = GetFilterPass(pass, true);
		if (filter) {
			filter->SetEnabled(enabled);
		}
	}
	return true;
}

void KX_2DFilterManager::EnsureSSAOFilters(BuildInFilters filters)
{
#ifdef __EMSCRIPTEN__
	// Web/GLSL ES keeps the single full resolution pass the base class built (spiral SSAO).
	(void)filters;
#else
	if (!filters.useSSAO || GetFilterPass(PASS_SSAO_IMAGE, true)) {
		return;
	}
	/* GTAO traced at half resolution (only .r is used: visibility before the multi-bounce), averaged
	 * over frames by the temporal resolve when float targets exist (16 bit: the 8 bit buffer showed
	 * grain), then RAS_SSAO_Image2DFilter.glsl blurs it (bilateral, depth aware) and darkens the
	 * image. Replaces the single full resolution pass of RAS_2DFilterManager. */
	const bool temporal = RAS_FloatRenderTargetSupported();
	RemoveReservedFilterPass(FILTERPASS_SSAO);

	RAS_2DFilterData data;
	data.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	data.filterPassIndex = FILTERPASS_SSAO;
	data.gameObject = nullptr;
	data.mipmap = false;
	data.propertyNames = {};
	data.buildInFilters = filters;
	data.shaderText = std::string(temporal ? "#define SSAO_TRACE\n#define SSAO_TEMPORAL\n" : "#define SSAO_TRACE\n") +
	        datatoc_RAS_SSAO2DFilter_glsl;
	KX_2DFilter *trace = static_cast<KX_2DFilter *>(AddFilter(data, true));
	trace->SetOffScreen(new KX_2DFilterOffScreen(1, RAS_2DFilterOffScreen::RAS_CANVAS_DIVISOR,
	        std::max(1, m_canvas->GetRenderWidth() / 2), std::max(1, m_canvas->GetRenderHeight() / 2),
	        temporal ? RAS_Rasterizer::RAS_HDR_HALF_FLOAT : RAS_Rasterizer::RAS_HDR_NONE, 2.0f));

	data.filterPassIndex = PASS_SSAO_IMAGE;
	data.shaderText = datatoc_RAS_SSAO_Image2DFilter_glsl;
	KX_2DFilter *image = static_cast<KX_2DFilter *>(AddFilter(data, true));
	KX_2DFilter *resolve = temporal ? AttachTemporalResolve(trace, TEMPORAL_SSAO, 2.0f, "#define TEMPORAL_ALPHA 0.1\n") : nullptr;
	RAS_2DFilterOffScreen *composited = resolve ? resolve->GetOffScreen() : trace->GetOffScreen();
	image->SetTexture(0, composited->GetColorBindCode(0), "ssao_buffer");
	composited->SetRebuildCallback([this]() {
		RAS_2DFilter *t = GetFilterPass(FILTERPASS_SSAO, true);
		KX_2DFilter *img = static_cast<KX_2DFilter *>(GetFilterPass(PASS_SSAO_IMAGE, true));
		if (!t || !img) {
			return;
		}
		RAS_2DFilter *src = t->GetTemporalResolve() ? t->GetTemporalResolve() : t;
		if (src->GetOffScreen()) {
			img->UpdateTextureBindCode(0, src->GetOffScreen()->GetColorBindCode(0));
		}
	});
	if (!trace->Ok() || !image->Ok() || !trace->GetOffScreen()->GetValid()) {
		trace->SetEnabled(false);
		image->SetEnabled(false);
		CM_Error("SSAO disabled: shader or framebuffer creation failed");
	}
#endif
}

KX_2DFilter *KX_2DFilterManager::EnsureDofHalf()
{
#ifdef __EMSCRIPTEN__
	// WebGL: the DOF pass gathers at full resolution (no extra off screen).
	return nullptr;
#else
	if (RAS_2DFilter *half = GetFilterPass(PASS_CAMERA_DOF_HALF, true)) {
		return static_cast<KX_2DFilter *>(half);
	}
	KX_2DFilter *dof = static_cast<KX_2DFilter *>(GetFilterPass(FILTERPASS_CAMERA_DOF, true));
	if (!dof) {
		return nullptr;
	}
	/* Bokeh gather at half resolution (rgb blurred, a = blur radius); the full resolution DOF pass
	 * blends it over the sharp image. Built once with the DOF pass and toggled with it. */
	RAS_2DFilterData data = CameraFXData(FILTERPASS_CAMERA_DOF);
	data.filterPassIndex = PASS_CAMERA_DOF_HALF;
	data.shaderText = std::string("#define DOF_HALF_RES\n") + datatoc_RAS_CameraDof2DFilter_glsl;
	KX_2DFilter *half = static_cast<KX_2DFilter *>(AddFilter(data, true));
	half->SetOffScreen(new KX_2DFilterOffScreen(1, RAS_2DFilterOffScreen::RAS_CANVAS_DIVISOR,
	        std::max(1, m_canvas->GetRenderWidth() / 2), std::max(1, m_canvas->GetRenderHeight() / 2),
	        RAS_FloatRenderTargetSupported() ? RAS_Rasterizer::RAS_HDR_HALF_FLOAT : RAS_Rasterizer::RAS_HDR_NONE, 2.0f));
	dof->SetTexture(0, half->GetOffScreen()->GetColorBindCode(0), "dof_half");
	half->GetOffScreen()->SetRebuildCallback([this]() {
		RAS_2DFilter *h = GetFilterPass(PASS_CAMERA_DOF_HALF, true);
		KX_2DFilter *d = static_cast<KX_2DFilter *>(GetFilterPass(FILTERPASS_CAMERA_DOF, true));
		if (h && d && h->GetOffScreen()) {
			d->UpdateTextureBindCode(0, h->GetOffScreen()->GetColorBindCode(0));
		}
	});
	/* Reduction: the gather used to read color and depth at full resolution for every sample; now it
	 * reads this half resolution color + CoC (a in 0..1, so an RGBA8 fallback still holds it). */
	data.filterPassIndex = FILTERPASS_CAMERA_DOF_REDUCE;
	data.shaderText = std::string("#define DOF_REDUCE\n") + datatoc_RAS_CameraDof2DFilter_glsl;
	KX_2DFilter *reduce = static_cast<KX_2DFilter *>(AddFilter(data, true));
	reduce->SetOffScreen(new KX_2DFilterOffScreen(1, RAS_2DFilterOffScreen::RAS_CANVAS_DIVISOR,
	        std::max(1, m_canvas->GetRenderWidth() / 2), std::max(1, m_canvas->GetRenderHeight() / 2),
	        RAS_FloatRenderTargetSupported() ? RAS_Rasterizer::RAS_HDR_HALF_FLOAT : RAS_Rasterizer::RAS_HDR_NONE, 2.0f));
	half->SetTexture(0, reduce->GetOffScreen()->GetColorBindCode(0), "dof_reduce");
	reduce->GetOffScreen()->SetRebuildCallback([this]() {
		RAS_2DFilter *r = GetFilterPass(FILTERPASS_CAMERA_DOF_REDUCE, true);
		KX_2DFilter *h = static_cast<KX_2DFilter *>(GetFilterPass(PASS_CAMERA_DOF_HALF, true));
		if (r && h && r->GetOffScreen()) {
			h->UpdateTextureBindCode(0, r->GetOffScreen()->GetColorBindCode(0));
		}
	});
	if (half->GetError() || reduce->GetError()) {
		reduce->SetEnabled(false);
		// UpdateCameraFX sees it and keeps the full resolution gather.
		half->SetEnabled(false);
		CM_Warning("Camera DOF: half resolution pass unavailable, using the full resolution gather");
	}
	return half;
#endif
}

void KX_2DFilterManager::EnsureBloomFilters(BuildInFilters filters)
{
	if (!filters.useBloom) {
		return;
	}
	if (GetFilterPass(PASS_BLOOM_IMAGE, true)) {
		// Already built.
		return;
	}

	/* Dual filter (Kawase/Bjorge): 4 downsamples (1/2 with the threshold, 1/4, 1/8, 1/16), one
	 * upsample 1/16 -> 1/8 that adds the 1/8 level, then the image pass upsamples that and adds the
	 * 1/4 and 1/2 levels. 6 passes of 5-8 taps each instead of 8 passes of 11-tap gaussians. */
	const int w = m_canvas->GetWidth();
	const int h = m_canvas->GetHeight();
	/* Half quality shifts the whole chain one level down (1/4 .. 1/32). */
	const int lodShift = (filters.bloom_quality == 1) ? 1 : 0;
	KX_2DFilter *down[4];
	for (int i = 0; i < 4; ++i) {
		down[i] = BloomPass(filters, (i == 0) ? 0 : 1, PASS_BLOOM_FIRST + i, (float)(2 << (i + lodShift)), w, h);
		if (i > 0) {
			down[i]->SetTexture(0, down[i - 1]->GetOffScreen()->GetColorBindCode(0), "bgl_BloomSource");
		}
	}
	KX_2DFilter *up = BloomPass(filters, 2, PASS_BLOOM_FIRST + 4, (float)(8 << lodShift), w, h);
	up->SetTexture(0, down[3]->GetOffScreen()->GetColorBindCode(0), "bgl_BloomSource");
	up->SetTexture(1, down[2]->GetOffScreen()->GetColorBindCode(0), "bgl_BloomAdd");

	RAS_2DFilterData bloomData;
	bloomData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	bloomData.filterPassIndex = PASS_BLOOM_IMAGE;
	bloomData.gameObject = nullptr;
	bloomData.mipmap = false;
	bloomData.propertyNames = {};
	bloomData.buildInFilters = filters;
	bloomData.shaderText = datatoc_RAS_Bloom2DFilter_Image_glsl;

	KX_2DFilter *bloomI = static_cast<KX_2DFilter *>(AddFilter(bloomData, true));

	bloomI->SetTexture(0, up->GetOffScreen()->GetColorBindCode(0), "bgl_BloomUp");
	bloomI->SetTexture(1, down[1]->GetOffScreen()->GetColorBindCode(0), "bgl_BloomI1");
	bloomI->SetTexture(2, down[0]->GetOffScreen()->GetColorBindCode(0), "bgl_BloomI0");

	for (int i = 0; i < PASS_BLOOM_COUNT - 1; ++i) {
		RAS_2DFilterOffScreen *offScreen = GetFilterPass(PASS_BLOOM_FIRST + i, true)->GetOffScreen();
		offScreen->SetRebuildCallback([this]() { RefreshBloomTextures(); });
	}
}

void KX_2DFilterManager::RefreshBloomTextures()
{
	KX_2DFilter *pass[PASS_BLOOM_COUNT];
	for (int i = 0; i < PASS_BLOOM_COUNT; ++i) {
		pass[i] = static_cast<KX_2DFilter *>(GetFilterPass(PASS_BLOOM_FIRST + i, true));
		if (!pass[i] || (i < PASS_BLOOM_COUNT - 1 && !pass[i]->GetOffScreen())) {
			return;
		}
	}

	// Same links as EnsureBloomFilters: {filter, texture unit, source off screen}. A missing texture has no bind code.
	const struct { int filter; int unit; int source; } links[] = {
		{1, 0, 0}, {2, 0, 1}, {3, 0, 2}, {4, 0, 3}, {4, 1, 2},
		{5, 0, 4}, {5, 1, 1}, {5, 2, 0}
	};
	for (const auto& link : links) {
		const int bindCode = pass[link.source]->GetOffScreen()->GetColorBindCode(0);
		if (bindCode >= 0) {
			pass[link.filter]->UpdateTextureBindCode(link.unit, bindCode);
		}
	}
}

void KX_2DFilterManager::EnsureSSGIFilters(BuildInFilters filters)
{
    if (!filters.useSSGI || GetFilterPass(FILTERPASS_SSGI, true)) return;
    RAS_2DFilterData data;
    data.filterMode = FILTER_CUSTOMFILTER;
    data.filterPassIndex = FILTERPASS_SSGI;
    data.gameObject = nullptr;
    data.mipmap = false;
    data.buildInFilters = filters;
    const std::string define = "#define SSGI_SLOT " + std::to_string(filters.ssgi_slot - 1) + "\n";
#ifdef __EMSCRIPTEN__
    const std::string temporalDefine;
#else
    // Per frame ray rotation only when the temporal resolve can average it (float targets).
    const std::string temporalDefine = RAS_FloatRenderTargetSupported() ? "#define SSGI_TEMPORAL" : "";
#endif
    data.shaderText = define + (temporalDefine.empty() ? std::string() : temporalDefine + "\n") + datatoc_RAS_SSGI2DFilter_glsl;
    KX_2DFilter *trace = static_cast<KX_2DFilter *>(AddFilter(data, true));
    trace->SetOffScreen(new KX_2DFilterOffScreen(1, RAS_2DFilterOffScreen::RAS_CANVAS_DIVISOR,
        std::max(1, m_canvas->GetRenderWidth() / filters.ssgi_divisor),
        std::max(1, m_canvas->GetRenderHeight() / filters.ssgi_divisor),
        RAS_FloatRenderTargetSupported() ? RAS_Rasterizer::RAS_HDR_HALF_FLOAT : RAS_Rasterizer::RAS_HDR_NONE,
        (float)filters.ssgi_divisor));
    if (!RAS_FloatRenderTargetSupported()) {
        CM_Warning("Native SSGI: no float render targets, using an 8 bit buffer (lower quality)");
    }
    data.filterPassIndex = FILTERPASS_SSGI_IMAGE;
    data.shaderText = define + datatoc_RAS_SSGIImage2DFilter_glsl;
    KX_2DFilter *image = static_cast<KX_2DFilter *>(AddFilter(data, true));
    KX_2DFilter *resolve = AttachTemporalResolve(trace, TEMPORAL_SSGI, (float)filters.ssgi_divisor, "#define TEMPORAL_ALPHA 0.1\n");
    RAS_2DFilterOffScreen *composited = resolve ? resolve->GetOffScreen() : trace->GetOffScreen();
    image->SetTexture(0, composited->GetColorBindCode(0), "ge_SSGIBuffer");
    composited->SetRebuildCallback([this]() { RefreshSSGITexture(); });
    if (!trace->Ok() || !image->Ok() || !trace->GetOffScreen()->GetValid()) {
        trace->SetEnabled(false);
        image->SetEnabled(false);
        CM_Error("Native SSGI disabled: shader or framebuffer creation failed");
    }
}

void KX_2DFilterManager::RefreshSSGITexture()
{
    RAS_2DFilter *trace = GetFilterPass(FILTERPASS_SSGI, true);
    KX_2DFilter *image = static_cast<KX_2DFilter *>(GetFilterPass(FILTERPASS_SSGI_IMAGE, true));
    RAS_2DFilter *src = (trace && trace->GetTemporalResolve()) ? trace->GetTemporalResolve() : trace;
    if (src && image && src->GetOffScreen()) {
        image->UpdateTextureBindCode(0, src->GetOffScreen()->GetColorBindCode(0));
    }
}

void KX_2DFilterManager::EnsureSSRFilters(BuildInFilters filters)
{
	if (!filters.useSSR) {
		return;
	}
	if (GetFilterPass(FILTERPASS_SSR, true)) {
		// Already built.
		return;
	}

	// Buffer
	RAS_2DFilterData ssrData;
	ssrData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	ssrData.filterPassIndex = FILTERPASS_SSR;
	ssrData.gameObject = nullptr;
	ssrData.mipmap = false;
	ssrData.propertyNames = {};
	/* World colors for the rays without a hit come from KX_Scene (rain_sky_*): the active scene
	 * may still be the one being replaced while this scene is constructed. */
	ssrData.buildInFilters = filters;
	ssrData.shaderText = datatoc_RAS_SSR2DFilter_glsl;

	KX_2DFilter *SSR = static_cast<KX_2DFilter *>(AddFilter(ssrData, true));
	/* RGBA16F when float targets exist (HDR reflections + hit distance in alpha), else RGBA8. */
	const float ssrLod = (float)std::max(1, filters.ssr_lod);
	KX_2DFilterOffScreen *offScreen = new KX_2DFilterOffScreen(1, RAS_2DFilterOffScreen::RAS_CANVAS_DIVISOR,
	        std::max(1, (int)(m_canvas->GetRenderWidth() / ssrLod)), std::max(1, (int)(m_canvas->GetRenderHeight() / ssrLod)),
	        RAS_FloatRenderTargetSupported() ? RAS_Rasterizer::RAS_HDR_HALF_FLOAT : RAS_Rasterizer::RAS_HDR_NONE, ssrLod);
	SSR->SetOffScreen(offScreen);
	/* Temporal accumulation reprojected by the hit point (alpha of the trace). */
	KX_2DFilter *ssrResolve = AttachTemporalResolve(SSR, TEMPORAL_SSR, ssrLod,
	        "#define TEMPORAL_ALPHA 0.2\n#define TEMPORAL_HIT_REPROJECT\n");
	RAS_2DFilterOffScreen *ssrComposited = ssrResolve ? ssrResolve->GetOffScreen() : SSR->GetOffScreen();
	if (const char *dbg = getenv("RANGE_TEMPORAL_DEBUG")) {
		if (dbg[0] == '1') {
			if (FILE *f = fopen("range_temporal_debug.log", "a")) {
				fprintf(f, "TEMPORAL SSR resolve=%s float=%d trace_ok=%d\n", ssrResolve ? "yes" : "no",
				        RAS_FloatRenderTargetSupported() ? 1 : 0, SSR->Ok() ? 1 : 0);
				fclose(f);
			}
		}
	}

	// Image
	RAS_2DFilterData ssrblurData;
	ssrblurData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	ssrblurData.filterPassIndex = FILTERPASS_SSR_BLUR;
	ssrblurData.gameObject = nullptr;
	ssrblurData.mipmap = false;
	ssrblurData.propertyNames = {};
	ssrblurData.buildInFilters = filters;
	ssrblurData.shaderText = datatoc_RAS_SSR_Blur2DFilter_glsl;

	KX_2DFilter *SSR_Blur = static_cast<KX_2DFilter *>(AddFilter(ssrblurData, true));

	SSR_Blur->SetTexture(0, ssrComposited->GetColorBindCode(0), "ssr_buffer");
	ssrComposited->SetRebuildCallback([this]() {
		RAS_2DFilter *trace = GetFilterPass(FILTERPASS_SSR, true);
		KX_2DFilter *blur = static_cast<KX_2DFilter *>(GetFilterPass(FILTERPASS_SSR_BLUR, true));
		if (!trace || !blur) {
			return;
		}
		RAS_2DFilter *src = trace->GetTemporalResolve() ? trace->GetTemporalResolve() : trace;
		if (src->GetOffScreen()) {
			blur->UpdateTextureBindCode(0, src->GetOffScreen()->GetColorBindCode(0));
		}
	});
}

void KX_2DFilterManager::EnsureLightScatterFilters(BuildInFilters filters)
{
	if (!filters.useLightScatter) {
		return;
	}
	if (GetFilterPass(FILTERPASS_LIGHTSCATTER, true)) {
		// Already built.
		return;
	}

	// Buffer
	RAS_2DFilterData scatterData;
	scatterData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	scatterData.filterPassIndex = FILTERPASS_LIGHTSCATTER;
	scatterData.gameObject = nullptr;
	scatterData.mipmap = false;
	scatterData.propertyNames = {};
	scatterData.buildInFilters = filters;
	scatterData.shaderText = datatoc_RAS_LightScaterring_Buffer2DFilter_glsl;

	KX_2DFilter *Scatter = static_cast<KX_2DFilter *>(AddFilter(scatterData, true));
	KX_2DFilterOffScreen *offScreen = new KX_2DFilterOffScreen(1, (RAS_2DFilterOffScreen::Flag)0, (m_canvas->GetWidth() / filters.scatter_lod), (m_canvas->GetHeight() / filters.scatter_lod),
															   RAS_Rasterizer::HdrType::RAS_HDR_HALF_FLOAT);
	Scatter->SetOffScreen(offScreen);

	// Image
	RAS_2DFilterData scatterImageData;
	scatterImageData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	scatterImageData.filterPassIndex = FILTERPASS_LIGHTSCATTER + 1;
	scatterImageData.gameObject = nullptr;
	scatterImageData.mipmap = false;
	scatterImageData.propertyNames = {};
	scatterImageData.buildInFilters = filters;
	scatterImageData.shaderText = datatoc_RAS_LightScaterring_Image2DFilter_glsl;

	KX_2DFilter *Scatter_Image = static_cast<KX_2DFilter *>(AddFilter(scatterImageData, true));

	Scatter_Image->SetTexture(0, Scatter->GetOffScreen()->GetColorBindCode(0), "bgl_LightScatter");
}

void KX_2DFilterManager::EnsureRainFilters(BuildInFilters filters)
{
	if (!filters.useRain) {
		return;
	}
	if (GetFilterPass(FILTERPASS_RAIN, true)) {
		// Already built.
		return;
	}

	RAS_2DFilterData rainData;
	rainData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	rainData.filterPassIndex = FILTERPASS_RAIN;
	rainData.gameObject = nullptr;
	rainData.mipmap = false;
	rainData.propertyNames = {};
	rainData.buildInFilters = filters;
	rainData.shaderText = datatoc_RAS_Rain2DFilter_glsl;

	AddFilter(rainData, true);
}

void KX_2DFilterManager::EnsureCompositorFilter(Scene *scene)
{
	if (GetFilterPass(FILTERPASS_COMPOSITOR, true)) {
		return;
	}
	std::vector<std::string> skipped;
	const std::string shader = KX_BuildCompositorShader(scene, skipped);
	if (shader.empty()) {
		return;
	}
	for (const std::string& name : skipped) {
		CM_Warning("Compositing in the game: node \"" << name << "\" is not supported, its input passes through");
	}
	// Debug: RANGE_COMPOSITOR_DUMP=file writes the generated shader (checked without a window).
	if (const char *dump = getenv("RANGE_COMPOSITOR_DUMP")) {
		if (FILE *f = BLI_fopen(dump, "wb")) {
			fwrite(shader.data(), 1, shader.size(), f);
			fclose(f);
		}
	}

	RAS_2DFilterData data;
	data.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	data.filterPassIndex = FILTERPASS_COMPOSITOR;
	data.gameObject = nullptr;
	data.mipmap = false;
	data.propertyNames = {};
	data.buildInFilters = m_sceneFilters;
	data.shaderText = shader;
	data.sourceName = "Compositing";
	AddFilter(data, true);
}

void KX_2DFilterManager::EnsureCloudsFilters(BuildInFilters filters)
{
	if (!filters.useClouds) {
		return;
	}
	if (GetFilterPass(FILTERPASS_CLOUDS, true)) {
		// Already built.
		return;
	}

	RAS_2DFilterData cloudsData;
	cloudsData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	cloudsData.filterPassIndex = FILTERPASS_CLOUDS;
	cloudsData.gameObject = nullptr;
	cloudsData.mipmap = false;
	cloudsData.propertyNames = {};
	cloudsData.buildInFilters = filters;
	cloudsData.shaderText = datatoc_RAS_Clouds2DFilter_glsl;

	AddFilter(cloudsData, true);
}

void KX_2DFilterManager::EnsureVFogFilters(BuildInFilters filters)
{
	if (!filters.useVFog) {
		return;
	}
	if (GetFilterPass(FILTERPASS_VFOG, true)) {
		// Already built.
		return;
	}

	RAS_2DFilterData fogData;
	fogData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	fogData.filterPassIndex = FILTERPASS_VFOG;
	fogData.gameObject = nullptr;
	fogData.mipmap = false;
	fogData.propertyNames = {};
	fogData.buildInFilters = filters;
	/* The fog is shared with the 3D View pass (gpu_shader_vfog_lib.glsl). */
	fogData.shaderText = std::string(datatoc_gpu_shader_vfog_lib_glsl) + datatoc_RAS_VolumetricFog2DFilter_glsl;

	const int lod = std::max(1, filters.vfog_lod);

	/* Full/Half/Quarter: like the Light Scattering, the fog (in-scatter rgb, transmittance a) goes to a
	 * offscreen and the image pass upscales it following the depth. Full resolution goes through it too:
	 * the image pass also blurs the fog a little (depth aware), hiding the raymarch jitter stipple. */
	fogData.shaderText = "#define VFOG_LOW_RES\n" + fogData.shaderText;
	KX_2DFilter *fog = static_cast<KX_2DFilter *>(AddFilter(fogData, true));
	fog->SetOffScreen(new KX_2DFilterOffScreen(1, RAS_2DFilterOffScreen::RAS_CANVAS_DIVISOR,
	        std::max(1, m_canvas->GetRenderWidth() / lod), std::max(1, m_canvas->GetRenderHeight() / lod),
	        RAS_FloatRenderTargetSupported() ? RAS_Rasterizer::RAS_HDR_HALF_FLOAT : RAS_Rasterizer::RAS_HDR_NONE, (float)lod));
	if (!RAS_FloatRenderTargetSupported()) {
		CM_Warning("Volumetric fog: no float render targets, using an 8 bit buffer (lower quality)");
	}

	RAS_2DFilterData imageData;
	imageData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	imageData.filterPassIndex = FILTERPASS_VFOG_IMAGE;
	imageData.gameObject = nullptr;
	imageData.mipmap = false;
	imageData.propertyNames = {};
	imageData.buildInFilters = filters;
	imageData.shaderText = datatoc_RAS_VolumetricFogImage2DFilter_glsl;
	KX_2DFilter *image = static_cast<KX_2DFilter *>(AddFilter(imageData, true));
	/* Temporal accumulation of the fog buffer (stipple of the shadowed fog averaged over frames);
	 * the image pass then composites the resolved buffer. */
	KX_2DFilter *resolve = AttachTemporalResolve(fog, TEMPORAL_VFOG, (float)lod, "#define TEMPORAL_ALPHA 0.1\n");
	RAS_2DFilterOffScreen *composited = resolve ? resolve->GetOffScreen() : fog->GetOffScreen();
	image->SetTexture(0, composited->GetColorBindCode(0), "vfog_buffer");
	composited->SetRebuildCallback([this]() {
		RAS_2DFilter *f = GetFilterPass(FILTERPASS_VFOG, true);
		KX_2DFilter *img = static_cast<KX_2DFilter *>(GetFilterPass(FILTERPASS_VFOG_IMAGE, true));
		if (!f || !img) {
			return;
		}
		RAS_2DFilter *src = f->GetTemporalResolve() ? f->GetTemporalResolve() : f;
		if (src->GetOffScreen()) {
			img->UpdateTextureBindCode(0, src->GetOffScreen()->GetColorBindCode(0));
		}
	});
	if (!fog->Ok() || !image->Ok() || !fog->GetOffScreen()->GetValid()) {
		fog->SetEnabled(false);
		image->SetEnabled(false);
		CM_Error("Volumetric Fog disabled: shader or framebuffer creation failed");
	}
}

KX_2DFilter *KX_2DFilterManager::AttachTemporalResolve(KX_2DFilter *trace, int effect, float lod, const std::string& defines)
{
#ifdef __EMSCRIPTEN__
	// No float copy to a texture on WebGL: no history, the image pass reads the trace buffer.
	(void)trace;
	(void)effect;
	(void)lod;
	(void)defines;
	return nullptr;
#else
	if (!trace->GetOffScreen() || !RAS_FloatRenderTargetSupported()) {
		return nullptr;
	}
	RAS_2DFilterData data;
	data.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	data.filterPassIndex = 0xFFFF; // not in the pass map, rendered by the manager after trace
	data.gameObject = nullptr;
	data.mipmap = false;
	data.propertyNames = {};
	data.buildInFilters = *trace->GetBuildInFilters();
	data.shaderText = defines + datatoc_RAS_Temporal2DFilter_glsl;
	KX_2DFilter *resolve = static_cast<KX_2DFilter *>(NewFilter(data));
	resolve->SetEnabled(true);
	resolve->SetOffScreen(new KX_2DFilterOffScreen(1, RAS_2DFilterOffScreen::RAS_CANVAS_DIVISOR,
	        std::max(1, (int)(m_canvas->GetRenderWidth() / lod)), std::max(1, (int)(m_canvas->GetRenderHeight() / lod)),
	        RAS_Rasterizer::RAS_HDR_HALF_FLOAT, lod));
	if (!resolve->Ok() || !resolve->GetOffScreen()->GetValid()) {
		CM_Warning("Temporal resolve unavailable (shader or framebuffer creation failed), effect " << effect);
		delete resolve;
		return nullptr;
	}
	resolve->SetTexture(0, trace->GetOffScreen()->GetColorBindCode(0), (char *)"ge_TemporalCurrent");
	trace->SetTemporalResolve(resolve, effect);
	trace->GetOffScreen()->SetRebuildCallback([trace]() {
		KX_2DFilter *r = static_cast<KX_2DFilter *>(trace->GetTemporalResolve());
		if (r && trace->GetOffScreen()) {
			r->UpdateTextureBindCode(0, trace->GetOffScreen()->GetColorBindCode(0));
		}
	});
	return resolve;
#endif
}

void KX_2DFilterManager::EnsureLensFlareFilters(BuildInFilters filters)
{
	if (!filters.useLensFlare) {
		return;
	}
	if (GetFilterPass(FILTERPASS_LENSFLARE, true)) {
		// Already built.
		return;
	}

	RAS_2DFilterData flareData;
	flareData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	flareData.filterPassIndex = FILTERPASS_LENSFLARE;
	flareData.gameObject = nullptr;
	flareData.mipmap = false;
	flareData.propertyNames = {};
	flareData.buildInFilters = filters;
	flareData.shaderText = datatoc_RAS_LensFlare2DFilter_glsl;

	AddFilter(flareData, true);
}

RAS_2DFilterData KX_2DFilterManager::CameraFXData(int pass)
{
	RAS_2DFilterData data;
	data.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	data.filterPassIndex = pass;
	data.gameObject = nullptr;
	data.mipmap = false;
	data.propertyNames = {};
	data.buildInFilters = {};
	data.shaderText = (pass == FILTERPASS_CAMERA_DOF) ? datatoc_RAS_CameraDof2DFilter_glsl :
	                                                    datatoc_RAS_CameraLens2DFilter_glsl;
	return data;
}

void KX_2DFilterManager::CameraFXUsed(KX_Scene *scene, bool& dof, bool& lens) const
{
	/* Any camera: the effects are often turned on from Python only during the game (nitro, countdown), so the
	 * flags at load say nothing. Disabled passes cost no draw. Inactive layers too: a camera spawned later (the
	 * player's car) is there. */
	dof = lens = false;
	for (EXP_ListValue<KX_GameObject> *list : {scene->GetObjectList(), scene->GetInactiveList()}) {
		for (KX_GameObject *gameobj : list) {
			if (dynamic_cast<KX_Camera *>(gameobj)) {
				dof = lens = true;
				return;
			}
		}
	}
}

void KX_2DFilterManager::PrefetchCameraFX(KX_Scene *scene)
{
	bool use[2];
	CameraFXUsed(scene, use[0], use[1]);
	const int passes[2] = {FILTERPASS_CAMERA_DOF, FILTERPASS_CAMERA_LENS};
	for (int i = 0; i < 2; ++i) {
		if (use[i] && !GetFilterPass(passes[i], true)) {
			// Inside a prefetch pass the link only sends the program to the driver; the filter itself is dropped.
			RAS_2DFilterData data = CameraFXData(passes[i]);
			delete NewFilter(data);
#ifndef __EMSCRIPTEN__
			if (passes[i] == FILTERPASS_CAMERA_DOF) {
				data.shaderText = std::string("#define DOF_HALF_RES\n") + datatoc_RAS_CameraDof2DFilter_glsl;
				delete NewFilter(data);
				data.shaderText = std::string("#define DOF_REDUCE\n") + datatoc_RAS_CameraDof2DFilter_glsl;
				delete NewFilter(data);
			}
#endif
		}
	}
}

void KX_2DFilterManager::PrepareCameraFX(KX_Scene *scene)
{
	bool use[2];
	CameraFXUsed(scene, use[0], use[1]);
	const int passes[2] = {FILTERPASS_CAMERA_DOF, FILTERPASS_CAMERA_LENS};
	for (int i = 0; i < 2; ++i) {
		if (use[i] && !GetFilterPass(passes[i], true)) {
			RAS_2DFilterData data = CameraFXData(passes[i]);
			if (RAS_2DFilter *filter = AddFilter(data, true)) {
				// UpdateCameraFX turns it on when the active camera uses it.
				filter->SetEnabled(false);
				if (passes[i] == FILTERPASS_CAMERA_DOF) {
					if (RAS_2DFilter *half = EnsureDofHalf()) {
						half->SetEnabled(false);
						if (RAS_2DFilter *reduce = GetFilterPass(FILTERPASS_CAMERA_DOF_REDUCE, true)) {
							reduce->SetEnabled(false);
						}
					}
				}
			}
		}
	}
}

void KX_2DFilterManager::UpdateCameraFX(KX_Camera *camera, double time)
{
	bool useDof = false;
	bool useLens = false;
	float fx[40] = {0.0f};

	const bool grain = m_useGrain && m_grainStrength > 0.0f;
	if (grain) {
		// Grain seed; changes every frame, kept small for float precision.
		// Derived from this manager's own frame time (no global shared between scenes/managers).
		const unsigned int grainFrame = (unsigned int)std::fmod(std::max(time, 0.0) * 60.0, 1000.0);
		fx[21] = m_grainStrength;
		fx[22] = (float)grainFrame * 0.05f;
		useLens = true;
	}

	if (camera) {
		const KX_Camera::GameFX& gfx = camera->GetGameFX();
		const float speed = camera->GetCameraSpeed();
		const float speedFactor = std::min(speed / std::max(gfx.speedBlurMaxSpeed, 0.1f), 1.0f);
		const mt::vec2& screen = camera->GetFocusScreenPosition();

		/* Camera motion blur: reprojection from this frame's view-projection to the last one, so the
		 * shader gets each pixel's real screen motion from its depth (turn and travel alike, one-sided
		 * trail). A new camera or the first frame has no history and draws no blur. */
		const RAS_Rasterizer::StereoEye eye = RAS_Rasterizer::RAS_STEREO_LEFTEYE;
		const mt::mat4 viewProj = camera->GetProjectionMatrix(eye) * camera->GetModelviewMatrix(eye);
		const bool history = (m_prevFXCamera == camera);
		bool moved = false;
		if (history) {
			for (int c = 0; c < 4 && !moved; ++c) {
				for (int r = 0; r < 4; ++r) {
					if (std::abs(viewProj(r, c) - m_prevViewProj(r, c)) > 1e-6f) {
						moved = true;
						break;
					}
				}
			}
		}
		const mt::mat4 reproject = history ? m_prevViewProj * viewProj.Inverse() : mt::mat4::Identity();
		// One frame's motion scaled to a 60 fps frame, so the trail length does not follow the frame rate.
		const double frameDelta = time - m_prevFXTime;
		const float fpsScale = (history && frameDelta > 0.0) ?
			std::min(std::max((float)((1.0 / 60.0) / frameDelta), 0.25f), 2.0f) : 1.0f;
		m_prevViewProj = viewProj;
		m_prevFXCamera = camera;
		m_prevFXTime = time;

		useDof = (gfx.flag & CAM_GFX_DOF) && gfx.dofBlur > 0.0f;
		const bool speedBlur = (gfx.flag & CAM_GFX_SPEEDBLUR) && gfx.speedBlurStrength > 0.0f;
		// Only while the camera moves: a still camera would run a full screen pass that just copies the screen.
		const bool dirBlur = (gfx.flag & CAM_GFX_DIRBLUR) && gfx.dirBlurStrength > 0.0f && moved;
		const bool chroma = (gfx.flag & CAM_GFX_CHROMA) && gfx.chromaStrength > 0.0f;
		const bool vignette = (gfx.flag & CAM_GFX_VIGNETTE) &&
		                      (gfx.vignetteStrength > 0.0f || gfx.fisheyeStrength != 0.0f);
		useLens = useLens || speedBlur || dirBlur || chroma || vignette;

		static const float rings[3] = {2.0f, 3.0f, 5.0f};
		const RAS_CameraData *data = camera->GetCameraData();

		fx[0] = camera->GetFocusDistance();
		fx[1] = gfx.focusRange;
		fx[2] = data->m_clipstart;
		fx[3] = data->m_clipend;
		fx[4] = gfx.dofBlur;
		fx[5] = rings[std::min(std::max((int)gfx.dofQuality, 0), 2)];
		fx[6] = (gfx.flag & CAM_GFX_CATEYE_BOKEH) ? gfx.catEyeStrength : 0.0f;
		fx[7] = data->m_perspective ? 1.0f : 0.0f;
		fx[8] = speedBlur ? gfx.speedBlurStrength * speedFactor : 0.0f;
		fx[9] = screen.x;
		fx[10] = 1.0f - screen.y;
		fx[11] = (gfx.flag & CAM_GFX_BLUR_PROTECT) ? 1.0f : 0.0f;
		if (dirBlur) {
			// Trail length as a multiple of one frame's motion, capped as a screen fraction.
			fx[12] = gfx.dirBlurStrength * 2.0f * fpsScale;
			fx[13] = gfx.dirBlurMax;
			for (int c = 0; c < 4; ++c) {
				for (int r = 0; r < 4; ++r) {
					fx[24 + c * 4 + r] = reproject(r, c);
				}
			}
		}
		float chromaAmount = chroma ? gfx.chromaStrength : 0.0f;
		if (chroma && (gfx.flag & CAM_GFX_CHROMA_SPEED)) {
			chromaAmount *= 0.25f + speedFactor;
		}
		fx[16] = chromaAmount;
		fx[17] = vignette ? gfx.vignetteStrength : 0.0f;
		fx[18] = gfx.vignetteRadius;
		fx[19] = vignette ? gfx.fisheyeStrength : 0.0f;
		fx[20] = (float)gfx.numBlades;
	}

	RAS_2DFilter *dof = GetFilterPass(FILTERPASS_CAMERA_DOF, true);
	if (useDof && !dof) {
		RAS_2DFilterData data = CameraFXData(FILTERPASS_CAMERA_DOF);
		dof = AddFilter(data, true);
		EnsureDofHalf();
	}
	else if (dof) {
		/* Keep the pass built and only toggle it: removing it here meant the shader was compiled
		 * again every time the effect came back (nitro, camera switch), a visible hitch. */
		dof->SetEnabled(useDof);
	}
	/* Half resolution bokeh gather (desktop), blended by the DOF pass where ge_CameraFX[5].w is 1. */
	RAS_2DFilter *dofHalf = GetFilterPass(PASS_CAMERA_DOF_HALF, true);
	/* The program links on the first render, so a pass never enabled is not Ok() yet: only a link
	 * error (GetError) keeps the full resolution gather. */
	RAS_2DFilter *dofReduce = GetFilterPass(FILTERPASS_CAMERA_DOF_REDUCE, true);
	const bool halfOk = dof && dofHalf && !dofHalf->GetError() && dofHalf->GetOffScreen() &&
	                    dofReduce && !dofReduce->GetError() && dofReduce->GetOffScreen();
	for (RAS_2DFilter *filter : {dofHalf, dofReduce}) {
		if (filter) {
			filter->SetEnabled(useDof && halfOk);
		}
	}
	fx[23] = (useDof && halfOk) ? 1.0f : 0.0f;
	if (useDof && halfOk) {
		std::copy(fx, fx + 40, dofHalf->GetBuildInFilters()->camera_fx);
		std::copy(fx, fx + 40, dofReduce->GetBuildInFilters()->camera_fx);
	}

	RAS_2DFilter *lens = GetFilterPass(FILTERPASS_CAMERA_LENS, true);
	if (useLens && !lens) {
		RAS_2DFilterData data = CameraFXData(FILTERPASS_CAMERA_LENS);
		lens = AddFilter(data, true);
	}
	else if (lens) {
		/* Keep the pass built and only toggle it: removing it here meant the shader was compiled
		 * again every time the effect came back (nitro, camera switch), a visible hitch. */
		lens->SetEnabled(useLens);
	}

	for (RAS_2DFilter *filter : {dof, lens}) {
		if (filter && filter->GetEnabled()) {
			std::copy(fx, fx + 40, filter->GetBuildInFilters()->camera_fx);
		}
	}
}

KX_2DFilter *KX_2DFilterManager::BloomPass(BuildInFilters filters, int time, int index, float lod, int w, int h)
{
	KX_2DFilter *bloom;

	RAS_2DFilterData bloomData;
	bloomData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	bloomData.filterPassIndex = index;
	bloomData.gameObject = nullptr;
	bloomData.mipmap = false;
	bloomData.propertyNames = {};
	bloomData.buildInFilters = filters;
	
	// time: 0 first downsample (threshold), 1 downsample, 2 upsample.
	if (time == 0)
		bloomData.shaderText = std::string("#define BLOOM_PREFILTER\n") + datatoc_RAS_Bloom2DFilter_Down_glsl;
	else if (time == 1)
		bloomData.shaderText = datatoc_RAS_Bloom2DFilter_Down_glsl;
	else
		bloomData.shaderText = datatoc_RAS_Bloom2DFilter_Up_glsl;

	bloom = static_cast<KX_2DFilter *>(AddFilter(bloomData, true));
	// The bloom buffers follow the canvas size divided by lod, so resize/fullscreen do not leave them stale.
	KX_2DFilterOffScreen *offScreen = new KX_2DFilterOffScreen(1, RAS_2DFilterOffScreen::RAS_CANVAS_DIVISOR, (w / lod), (h / lod),
																   RAS_FloatRenderTargetSupported() ? RAS_Rasterizer::HdrType::RAS_HDR_HALF_FLOAT : RAS_Rasterizer::HdrType::RAS_HDR_NONE, lod);
	bloom->SetOffScreen(offScreen);

	return bloom;
}

RAS_2DFilter *KX_2DFilterManager::EnsureFxaaPass()
{
	RAS_2DFilter *fxaa = GetFilterPass(FILTERPASS_FXAA, true);
	if (!fxaa) {
		fxaa = EnsureFxaaFilter(m_sceneFilters);
		fxaa->SetEnabled(false);
	}
	BuildInFilters *params = fxaa->GetBuildInFilters();
	// A pass without scene values (search steps 0) draws with the defaults: write them, so a
	// single parameter can change.
	if (params->fxaa_search_steps <= 0) {
		params->fxaa_edge_threshold = SCENE_FX_FXAA_EDGE_THRESHOLD;
		params->fxaa_edge_threshold_min = SCENE_FX_FXAA_EDGE_THRESHOLD_MIN;
		params->fxaa_subpix = SCENE_FX_FXAA_SUBPIX;
		params->fxaa_search_steps = SCENE_FX_FXAA_SEARCH_STEPS;
	}
	return fxaa;
}

RAS_2DFilter *KX_2DFilterManager::NewFilter(RAS_2DFilterData& filterData)
{
	return new KX_2DFilter(filterData);
}

static bool source_file_time(const std::string& path, int64_t& time)
{
	BLI_stat_t st;
	if (BLI_stat(path.c_str(), &st) != 0) {
		return false;
	}
	time = (int64_t)st.st_mtime;
	return true;
}

bool KX_2DFilterManager::ReloadSource(RAS_2DFilter *filter)
{
	const std::string& path = filter->GetSourcePath();
	if (path.empty()) {
		return false;
	}
	size_t size = 0;
	char *buf = (char *)BLI_file_read_text_as_mem(path.c_str(), 1, &size);
	if (!buf) {
		CM_Error("2D filter \"" << filter->GetSourceName() << "\": can't read " << path);
		return false;
	}
	buf[size] = '\0';
	const bool ok = filter->Recompile(std::string(buf));
	MEM_freeN(buf);
	return ok;
}

void KX_2DFilterManager::ReloadChangedSources()
{
	const double now = PIL_check_seconds_timer();
	if (now - m_lastSourceCheck < 0.5) {
		return;
	}
	m_lastSourceCheck = now;

	std::map<RAS_2DFilter *, int64_t> times;
	for (const auto& pair : m_filters) {
		RAS_2DFilter *filter = pair.second;
		int64_t time;
		if (filter->GetSourcePath().empty() || !source_file_time(filter->GetSourcePath(), time)) {
			continue;
		}
		const auto it = m_sourceTimes.find(filter);
		if (it != m_sourceTimes.end() && it->second != time) {
			ReloadSource(filter);
		}
		times[filter] = time;
	}
	// Drops the removed filters.
	m_sourceTimes.swap(times);
}

#ifdef WITH_PYTHON
PyMethodDef KX_2DFilterManager::Methods[] = {
	// creation
	EXP_PYMETHODTABLE(KX_2DFilterManager, getFilter),
	EXP_PYMETHODTABLE(KX_2DFilterManager, addFilter),
	EXP_PYMETHODTABLE(KX_2DFilterManager, removeFilter),
	EXP_PYMETHODTABLE(KX_2DFilterManager, setBuiltinFilterEnabled),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeFxaaValues),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeTonemapValues),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeBloomValues),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeGrainValues),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeLightScatterValues),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeSSRValues),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeSSAOValues),
    EXP_PYMETHODTABLE(KX_2DFilterManager, changeSSGIValues),
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_2DFilterManager::Attributes[] = {
	EXP_PYATTRIBUTE_RW_FUNCTION("fxaaEnabled", KX_2DFilterManager, pyattr_get_post, pyattr_set_post),
	EXP_PYATTRIBUTE_RW_FUNCTION("fxaaEdgeThreshold", KX_2DFilterManager, pyattr_get_post, pyattr_set_post),
	EXP_PYATTRIBUTE_RW_FUNCTION("fxaaEdgeThresholdMin", KX_2DFilterManager, pyattr_get_post, pyattr_set_post),
	EXP_PYATTRIBUTE_RW_FUNCTION("fxaaSubpix", KX_2DFilterManager, pyattr_get_post, pyattr_set_post),
	EXP_PYATTRIBUTE_RW_FUNCTION("fxaaSearchSteps", KX_2DFilterManager, pyattr_get_post, pyattr_set_post),
	EXP_PYATTRIBUTE_RW_FUNCTION("grainEnabled", KX_2DFilterManager, pyattr_get_post, pyattr_set_post),
	EXP_PYATTRIBUTE_RW_FUNCTION("grainStrength", KX_2DFilterManager, pyattr_get_post, pyattr_set_post),
	EXP_PYATTRIBUTE_NULL //Sentinel
};

/* Scene > Post-process: FXAA and Film Grain, same names and ranges as the panel (rna_scene.c). */
PyObject *KX_2DFilterManager::pyattr_get_post(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_2DFilterManager *self = static_cast<KX_2DFilterManager *>(self_v);
	const std::string& name = attrdef->m_name;
	if (name == "grainEnabled") {
		return PyBool_FromLong(self->m_useGrain);
	}
	if (name == "grainStrength") {
		return PyFloat_FromDouble(self->m_grainStrength);
	}

	RAS_2DFilter *fxaa = self->GetFilterPass(FILTERPASS_FXAA, true);
	if (name == "fxaaEnabled") {
		return PyBool_FromLong(fxaa && fxaa->GetEnabled());
	}
	BuildInFilters params = fxaa ? *fxaa->GetBuildInFilters() : self->m_sceneFilters;
	if (params.fxaa_search_steps <= 0) {
		params.fxaa_edge_threshold = SCENE_FX_FXAA_EDGE_THRESHOLD;
		params.fxaa_edge_threshold_min = SCENE_FX_FXAA_EDGE_THRESHOLD_MIN;
		params.fxaa_subpix = SCENE_FX_FXAA_SUBPIX;
		params.fxaa_search_steps = SCENE_FX_FXAA_SEARCH_STEPS;
	}
	if (name == "fxaaEdgeThreshold") return PyFloat_FromDouble(params.fxaa_edge_threshold);
	if (name == "fxaaEdgeThresholdMin") return PyFloat_FromDouble(params.fxaa_edge_threshold_min);
	if (name == "fxaaSubpix") return PyFloat_FromDouble(params.fxaa_subpix);
	return PyLong_FromLong(params.fxaa_search_steps);
}

int KX_2DFilterManager::pyattr_set_post(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_2DFilterManager *self = static_cast<KX_2DFilterManager *>(self_v);
	const std::string& name = attrdef->m_name;

	if (name == "fxaaEnabled" || name == "grainEnabled") {
		const int enabled = PyObject_IsTrue(value);
		if (enabled == -1) {
			PyErr_Format(PyExc_TypeError, "filterManager.%s = bool: KX_2DFilterManager, expected True or False", name.c_str());
			return PY_SET_ATTR_FAIL;
		}
		if (name == "grainEnabled") {
			self->m_useGrain = enabled;
		}
		else {
			self->EnsureFxaaPass()->SetEnabled(enabled);
		}
		return PY_SET_ATTR_SUCCESS;
	}

	const double number = PyFloat_AsDouble(value);
	if (number == -1.0 && PyErr_Occurred()) {
		PyErr_Format(PyExc_TypeError, "filterManager.%s = number: KX_2DFilterManager, expected a number", name.c_str());
		return PY_SET_ATTR_FAIL;
	}
	const float factor = (float)CLAMPIS(number, 0.0, 1.0);
	if (name == "grainStrength") {
		self->m_grainStrength = factor;
		return PY_SET_ATTR_SUCCESS;
	}

	BuildInFilters *params = self->EnsureFxaaPass()->GetBuildInFilters();
	if (name == "fxaaEdgeThreshold") params->fxaa_edge_threshold = factor;
	else if (name == "fxaaEdgeThresholdMin") params->fxaa_edge_threshold_min = factor;
	else if (name == "fxaaSubpix") params->fxaa_subpix = factor;
	else params->fxaa_search_steps = (int)CLAMPIS(number, 2.0, (double)SCENE_FX_FXAA_SEARCH_STEPS_MAX);
	return PY_SET_ATTR_SUCCESS;
}

PyTypeObject KX_2DFilterManager::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_2DFilterManager",
	sizeof(EXP_PyObjectPlus_Proxy),
	0,
	py_base_dealloc,
	0,
	0,
	0,
	0,
	py_base_repr,
	0, 0, 0, 0, 0, 0, 0, 0, 0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	0, 0, 0, 0, 0, 0, 0,
	Methods,
	0,
	0,
	&EXP_PyObjectPlus::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};


EXP_PYMETHODDEF_DOC(KX_2DFilterManager, getFilter, " getFilter(index)")
{
	int index = 0;

	if (!PyArg_ParseTuple(args, "i:getFilter", &index)) {
		return nullptr;
	}

	if (index < 0) {
		PyErr_SetString(PyExc_ValueError, "The index cannot be negative.");
		return nullptr;
	}

	KX_2DFilter *filter = (KX_2DFilter *)GetFilterPass(index, false);

	if (filter) {
		return filter->GetProxy();
	}

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, addFilter,
                    " addFilter(index, type, fragmentProgram=\"\", owner=None, mipmap=False)\n"
                    "owner: object whose game properties feed the uniforms of the same name, like the Filter 2D actuator.")
{
	int index = 0;
	int type = 0;
	const char *frag = "";
	PyObject *pyowner = Py_None;
	int mipmap = 0;

	if (!PyArg_ParseTuple(args, "ii|sOi:addFilter", &index, &type, &frag, &pyowner, &mipmap)) {
		return nullptr;
	}

	KX_GameObject *owner = nullptr;
	if (!ConvertPythonToGameObject(KX_GetActiveScene()->GetLogicManager(), pyowner, &owner, true,
	                               "filterManager.addFilter(index, type, fragmentProgram, owner, mipmap)")) {
		return nullptr;
	}

	if (index < 0) {
		PyErr_SetString(PyExc_ValueError, "The index cannot be negative.");
		return nullptr;
	}

	if (GetFilterPass(index, false)) {
		PyErr_Format(PyExc_ValueError, "filterManager.addFilter(index, type, fragmentProgram): KX_2DFilterManager, found existing filter in index (%i)", index);
		return nullptr;
	}

	if ((type < FILTER_BLUR || type > FILTER_CUSTOMFILTER) && type != FILTER_OUTLINE) {
		PyErr_SetString(PyExc_ValueError, "filterManager.addFilter(index, type, fragmentProgram): KX_2DFilterManager, type invalid");
		return nullptr;
	}

	if (strlen(frag) > 0 && type != FILTER_CUSTOMFILTER) {
		CM_PythonFunctionWarning("KX_2DFilterManager", "addFilter", "non-empty fragment program with non-custom filter type");
	}

	RAS_2DFilterData data;
	data.filterPassIndex = index;
	data.filterMode = type;
	data.shaderText = std::string(frag);
	data.mipmap = (mipmap != 0);
	if (owner) {
		data.gameObject = owner;
		data.propertyNames = owner->GetPropertyNames();
	}
	if (type == FILTER_CUSTOMFILTER) {
		// Turns on the error lines relative to the string and the named error messages.
		data.sourceName = "addFilter(" + std::to_string(index) + ")";
	}

	KX_2DFilter *filter = static_cast<KX_2DFilter *>(AddFilter(data, false));

	return filter->GetProxy();
}

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, setBuiltinFilterEnabled,
                    " setBuiltinFilterEnabled(type, enabled=True)\n"
                    "Turns a built-in filter on or off with its current values, like the Filter 2D actuator.\n"
                    "type: RAS_2DFILTER_FXAA, _BLOOM, _TONEMAP, _SSAO, _LIGHTSCATTER or _SSR. Returns False when unavailable.")
{
	int type = 0;
	int enabled = 1;

	if (!PyArg_ParseTuple(args, "i|i:setBuiltinFilterEnabled", &type, &enabled)) {
		return nullptr;
	}

	if (type != FILTER_FXAA && type != FILTER_BLOOM && type != FILTER_TONEMAP && type != FILTER_SSAO &&
	    type != FILTER_LIGHTSCATTER && type != FILTER_SSR) {
		PyErr_SetString(PyExc_ValueError, "filterManager.setBuiltinFilterEnabled(type, enabled): type is not a built-in filter");
		return nullptr;
	}

	return PyBool_FromLong(SetBuiltinFilterEnabled(static_cast<FILTER_MODE>(type), enabled != 0));
}

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, removeFilter, " removeFilter(index)")
{
	int index = 0;

	if (!PyArg_ParseTuple(args, "i:removeFilter", &index)) {
		return nullptr;
	}

	// RemoveFilterPass takes an unsigned index: a negative value would wrap onto a built-in filter.
	if (index < 0) {
		PyErr_SetString(PyExc_ValueError, "The index cannot be negative.");
		return nullptr;
	}

	RemoveFilterPass(index);

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, changeFxaaValues, "changeFxaaValues(enabled)")
{
	int enabled;

	if (!PyArg_ParseTuple(args, "i:changeFxaaValues", &enabled)) {
		return nullptr;
	}

	RAS_2DFilter *Fxaa = GetFilterPass(FILTERPASS_FXAA, true);

	if (!Fxaa) {
		BuildInFilters defaultFilters = {};
		Fxaa = EnsureFxaaFilter(defaultFilters);
	}

	Fxaa->SetEnabled(enabled);

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, changeTonemapValues, "changeTonemapValues(enabled, exposure, gamma)")
{
	int enabled;
	float exposure = -1;
	float gamma;

	if (!PyArg_ParseTuple(args, "i|ff:changeTonemapValues", &enabled, &exposure, &gamma)) {
		return nullptr;
	}

	RAS_2DFilter *Tonemap = GetFilterPass(FILTERPASS_TONEMAP, true);

	if (!Tonemap) {
		// The scene didn't start with Tonemap enabled, so it was never built.
		// Create it now with the requested (or default) parameters instead of
		// silently doing nothing.
		BuildInFilters defaultFilters = {};
		defaultFilters.tonemap_exposure = (exposure == -1) ? 2.2f : exposure;
		defaultFilters.tonemap_gamma = (exposure == -1) ? 1.0f : gamma;
		Tonemap = EnsureTonemapFilter(defaultFilters);
	}

	Tonemap->SetEnabled(enabled);

	if (exposure == -1)
		Py_RETURN_NONE;

	BuildInFilters *filterParams = Tonemap->GetBuildInFilters();
	filterParams->tonemap_exposure = exposure;
	filterParams->tonemap_gamma = gamma;

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, changeGrainValues, "changeGrainValues(enabled, strength)")
{
	int enabled;
	float strength = -1.0f;

	if (!PyArg_ParseTuple(args, "i|f:changeGrainValues", &enabled, &strength)) {
		return nullptr;
	}

	m_useGrain = (enabled != 0);
	if (strength >= 0.0f) {
		m_grainStrength = std::min(strength, 1.0f);
	}

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, changeBloomValues, "changeBloomValues(enabled, intensity, threshold)")
{
	int enabled;
	float intensity = -1;
	float threshold;

	if (!PyArg_ParseTuple(args, "i|ff:changeBloomValues", &enabled, &intensity, &threshold)) {
		return nullptr;
	}

	if (!GetFilterPass(PASS_BLOOM_IMAGE, true)) {
		// The scene didn't start with Bloom enabled, so its filter chain was
		// never built. Build it now with the requested (or default) values
		// instead of silently doing nothing.
		BuildInFilters defaultFilters = {};
		defaultFilters.useBloom = true;
		defaultFilters.bloom_intensity = (intensity == -1) ? 2.0f : intensity;
		defaultFilters.bloom_threshold = (intensity == -1) ? 0.75f : threshold;
		EnsureBloomFilters(defaultFilters);
	}

	for (int i = 0; i < PASS_BLOOM_COUNT; ++i) {
		RAS_2DFilter *pass = GetFilterPass(PASS_BLOOM_FIRST + i, true);
		if (!pass) {
			continue;
		}
		pass->SetEnabled(enabled);
		if (intensity != -1) {
			BuildInFilters *filterParams = pass->GetBuildInFilters();
			filterParams->bloom_intensity = intensity;
			filterParams->bloom_threshold = threshold;
		}
	}

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, changeLightScatterValues, "changeLightScatterValues(enabled, step_max, step_size, threshold, intensity)")
{
	int enabled;
	float step_max = -1;
	float step_size, threshold, intensity;

	if (!PyArg_ParseTuple(args, "i|ffff:changeLightScatterValues", &enabled, &step_max, &step_size, &threshold, &intensity)) {
		return nullptr;
	}

	RAS_2DFilter *Scatter = GetFilterPass(FILTERPASS_LIGHTSCATTER, true);

	if (!Scatter) {
		BuildInFilters defaultFilters = {};
		defaultFilters.useLightScatter = true;
		defaultFilters.scatter_lod = 4;
		defaultFilters.scatter_step_max = (step_max == -1) ? 32 : (int)step_max;
		defaultFilters.scatter_step_size = (step_max == -1) ? 0.15f : step_size;
		defaultFilters.scatter_threshold = (step_max == -1) ? 0.75f : threshold;
		defaultFilters.scatter_intensity = (step_max == -1) ? 0.2f : intensity;
		EnsureLightScatterFilters(defaultFilters);
		Scatter = GetFilterPass(FILTERPASS_LIGHTSCATTER, true);
	}

	RAS_2DFilter *Scatter_Image = GetFilterPass(FILTERPASS_LIGHTSCATTER + 1, true);

	Scatter->SetEnabled(enabled);
	if (Scatter_Image) {
		// The composite pass that actually blends the scatter buffer onto the
		// screen - must follow the buffer pass, otherwise disabling only the
		// buffer leaves this pass compositing a frozen, stale texture forever.
		Scatter_Image->SetEnabled(enabled);
	}

	if (step_max == -1)
		Py_RETURN_NONE;

	BuildInFilters *filterParams = Scatter->GetBuildInFilters();
	filterParams->scatter_step_max = step_max;
	filterParams->scatter_step_size = step_size;
	filterParams->scatter_threshold = threshold;
	filterParams->scatter_intensity = intensity;

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, changeSSRValues, "changeSSRValues(enabled, step_max, bias, max_distance)")
{
	int enabled;
	float step_max = -1;
	float bias, max_distance;

	if (!PyArg_ParseTuple(args, "i|fff:changeSSRValues", &enabled, &step_max, &bias, &max_distance)) {
		return nullptr;
	}

	RAS_2DFilter *SSR = GetFilterPass(FILTERPASS_SSR, true);

	if (!SSR) {
		BuildInFilters defaultFilters = {};
		defaultFilters.useSSR = true;
		defaultFilters.ssr_lod = 2;
		defaultFilters.ssr_step_max = (step_max == -1) ? 16 : (int)step_max;
		defaultFilters.ssr_bias = (step_max == -1) ? 3.0f : bias;
		defaultFilters.ssr_max_distance = (step_max == -1) ? 100.0f : max_distance;
		EnsureSSRFilters(defaultFilters);
		SSR = GetFilterPass(FILTERPASS_SSR, true);
	}

	RAS_2DFilter *SSR_Blur = GetFilterPass(FILTERPASS_SSR_BLUR, true);

	SSR->SetEnabled(enabled);
	if (SSR_Blur) {
		// The composite/blur pass that blends the SSR buffer onto the screen
		// - must follow the buffer pass, otherwise disabling only the buffer
		// leaves this pass compositing a frozen, stale texture forever.
		SSR_Blur->SetEnabled(enabled);
	}

	if (step_max == -1)
		Py_RETURN_NONE;

	BuildInFilters *filterParams = SSR->GetBuildInFilters();
	filterParams->ssr_step_max = step_max;
	filterParams->ssr_bias = bias;
	filterParams->ssr_max_distance = max_distance;

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, changeSSGIValues,
    "changeSSGIValues(enabled, radius=3.0, strength=1.0, rays=4, steps=8, thickness=0.1, divisor=0). "
    "divisor 1/2/4 changes trace resolution; 0 keeps it. Requires Scene SSGI enabled before Play.")
{
    int enabled, rays = 4, steps = 8;
    int divisor = 0;
    float radius = 3.0f, strength = 1.0f, thickness = 0.1f;
    if (!PyArg_ParseTuple(args, "i|ffiifi:changeSSGIValues", &enabled, &radius, &strength, &rays, &steps, &thickness, &divisor)) return nullptr;
    if (!std::isfinite(radius) || !std::isfinite(strength) || !std::isfinite(thickness) ||
        radius <= 0 || radius > 100 || strength < 0 || strength > 4 || rays < 1 || rays > 16 ||
        steps < 2 || steps > 32 || thickness <= 0 || thickness > 10 ||
        (divisor && divisor != 1 && divisor != 2 && divisor != 4)) {
        PyErr_SetString(PyExc_ValueError, "SSGI: radius (0,100], strength [0,4], rays [1,16], steps [2,32], thickness (0,10], divisor 0/1/2/4");
        return nullptr;
    }
    RAS_2DFilter *trace = GetFilterPass(FILTERPASS_SSGI, true);
    RAS_2DFilter *image = GetFilterPass(FILTERPASS_SSGI_IMAGE, true);
    if (!trace || !image) {
        PyErr_SetString(PyExc_RuntimeError, "Enable Scene > Native SSGI before Play; its material buffers are allocated at scene load.");
        return nullptr;
    }
    const int currentDivisor = trace->GetBuildInFilters()->ssgi_divisor;
    const int selectedDivisor = divisor ? divisor : currentDivisor;
    if (selectedDivisor != currentDivisor) {
        trace->SetOffScreen(new KX_2DFilterOffScreen(1, RAS_2DFilterOffScreen::RAS_CANVAS_DIVISOR,
            std::max(1, m_canvas->GetRenderWidth() / selectedDivisor),
            std::max(1, m_canvas->GetRenderHeight() / selectedDivisor),
            RAS_Rasterizer::RAS_HDR_HALF_FLOAT, (float)selectedDivisor));
        trace->GetOffScreen()->SetRebuildCallback([this]() { RefreshSSGITexture(); });
        RefreshSSGITexture();
    }
    for (RAS_2DFilter *pass : {trace, image}) {
        pass->SetEnabled(enabled != 0);
        BuildInFilters *params = pass->GetBuildInFilters();
        params->ssgi_radius = radius;
        params->ssgi_strength = strength;
        params->ssgi_rays = rays;
        params->ssgi_steps = steps;
        params->ssgi_thickness = thickness;
        params->ssgi_divisor = selectedDivisor;
    }
    Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, changeSSAOValues, "changeSSAOValues(enabled, samples, strength, distance, attenuation)")
{
	int enabled;
	float samples = -1;
	float strength, distance, attenuation;

	if (!PyArg_ParseTuple(args, "i|ffff:changeSSAOValues", &enabled, &samples, &strength, &distance, &attenuation)) {
		return nullptr;
	}

	RAS_2DFilter *SSAO = GetFilterPass(FILTERPASS_SSAO, true);

	if (!SSAO) {
		BuildInFilters defaultFilters = {};
		defaultFilters.ssao_samples = (samples == -1) ? 16 : (int)samples;
		defaultFilters.ssao_strength = (samples == -1) ? 4.0f : strength;
		defaultFilters.ssao_distance = (samples == -1) ? 1.0f : distance;
		defaultFilters.ssao_attenuation = (samples == -1) ? 1.0f : attenuation;
#ifdef __EMSCRIPTEN__
		SSAO = EnsureSSAOFilter(defaultFilters);
#else
		defaultFilters.useSSAO = true;
		EnsureSSAOFilters(defaultFilters);
		SSAO = GetFilterPass(FILTERPASS_SSAO, true);
#endif
	}

	// The trace and, on desktop, its composite (which reads the strength).
	for (RAS_2DFilter *pass : {SSAO, GetFilterPass(PASS_SSAO_IMAGE, true)}) {
		if (!pass) {
			continue;
		}
		pass->SetEnabled(enabled);
		if (samples != -1) {
			BuildInFilters *filterParams = pass->GetBuildInFilters();
			filterParams->ssao_samples = samples;
			filterParams->ssao_strength = strength;
			filterParams->ssao_distance = distance;
			filterParams->ssao_attenuation = attenuation;
		}
	}

	Py_RETURN_NONE;
}

#endif  // WITH_PYTHON
