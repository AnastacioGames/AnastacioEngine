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
#include "RAS_ICanvas.h"

#include "CM_Message.h"

extern "C" {
	extern char datatoc_RAS_Bloom2DFilter_buf_glsl[];
	extern char datatoc_RAS_Bloom2DFilter_bufH_glsl[];
	extern char datatoc_RAS_Bloom2DFilter_bufV_glsl[];
	extern char datatoc_RAS_Bloom2DFilter_Image_glsl[];

	extern char datatoc_RAS_SSR2DFilter_glsl[];
	extern char datatoc_RAS_SSR_Blur2DFilter_glsl[];

	extern char datatoc_RAS_LightScaterring_Buffer2DFilter_glsl[];
	extern char datatoc_RAS_LightScaterring_Image2DFilter_glsl[];

	extern char datatoc_RAS_Rain2DFilter_glsl[];
	extern char datatoc_RAS_Clouds2DFilter_glsl[];
	extern char datatoc_RAS_LensFlare2DFilter_glsl[];
}

KX_2DFilterManager::KX_2DFilterManager(RAS_ICanvas *canvas, BuildInFilters filters) :
	RAS_2DFilterManager(filters), m_canvas(canvas)
{
	/* This location doesn't seem very good to me but it works fine here, we need to generate the KX_2DFilter to have offscreen and not RAS_* */
	/* Only for Range legacy, the code can be deprecated after Range 2.0+ */
	EnsureBloomFilters(filters);

	// Need to be done before bloom passes
	EnsureSSRFilters(filters);

	EnsureLightScatterFilters(filters);

	EnsureRainFilters(filters);
	EnsureCloudsFilters(filters);
	EnsureLensFlareFilters(filters);
}


KX_2DFilterManager::~KX_2DFilterManager()
{
}

bool KX_2DFilterManager::SetBuiltinFilterEnabled(FILTER_MODE mode, bool enabled)
{
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
			firstPass = FILTERPASS_BLOOM;
			lastPass = FILTERPASS_BLOOM + 7;
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

void KX_2DFilterManager::EnsureBloomFilters(BuildInFilters filters)
{
	if (!filters.useBloom) {
		return;
	}
	if (GetFilterPass(FILTERPASS_BLOOM + 7, true)) {
		// Already built.
		return;
	}

	// This bloom shader uses 8 passIndex in negative form. eg [2 ~ 9].
	int filterPassIndex = FILTERPASS_BLOOM;

	// pass buffer
	KX_2DFilter *bloomB0 = BloomPass(filters, 0, filterPassIndex, 2, m_canvas->GetWidth(), m_canvas->GetHeight());

	// pass 0
	KX_2DFilter *bloomH0 = BloomPass(filters, 1, filterPassIndex + 1, 2, m_canvas->GetWidth(), m_canvas->GetHeight());
	KX_2DFilter *bloomV0 = BloomPass(filters, 2, filterPassIndex + 2, 2, m_canvas->GetWidth(), m_canvas->GetHeight());

	bloomH0->SetTexture(0, bloomB0->GetOffScreen()->GetColorBindCode(0), "bgl_RenderedBloomB");
	bloomV0->SetTexture(0, bloomH0->GetOffScreen()->GetColorBindCode(0), "bgl_RenderedBloomH");

	// pass 1
	KX_2DFilter *bloomH1 = BloomPass(filters, 1, filterPassIndex + 3, 4, m_canvas->GetWidth(), m_canvas->GetHeight());
	KX_2DFilter *bloomV1 = BloomPass(filters, 2, filterPassIndex + 4, 4, m_canvas->GetWidth(), m_canvas->GetHeight());

	bloomH1->SetTexture(0, bloomB0->GetOffScreen()->GetColorBindCode(0), "bgl_RenderedBloomB");
	bloomV1->SetTexture(0, bloomH1->GetOffScreen()->GetColorBindCode(0), "bgl_RenderedBloomH");

	// pass 2
	KX_2DFilter *bloomH2 = BloomPass(filters, 1, filterPassIndex + 5, 8, m_canvas->GetWidth(), m_canvas->GetHeight());
	KX_2DFilter *bloomV2 = BloomPass(filters, 2, filterPassIndex + 6, 8, m_canvas->GetWidth(), m_canvas->GetHeight());

	bloomH2->SetTexture(0, bloomB0->GetOffScreen()->GetColorBindCode(0), "bgl_RenderedBloomB");
	bloomV2->SetTexture(0, bloomH2->GetOffScreen()->GetColorBindCode(0), "bgl_RenderedBloomH");

	// pass final
	RAS_2DFilterData bloomData;
	bloomData.filterMode = FILTER_MODE::FILTER_CUSTOMFILTER;
	bloomData.filterPassIndex = filterPassIndex + 7;
	bloomData.gameObject = nullptr;
	bloomData.mipmap = false;
	bloomData.propertyNames = {};
	bloomData.buildInFilters = filters;
	bloomData.shaderText = datatoc_RAS_Bloom2DFilter_Image_glsl;

	KX_2DFilter *bloomI = static_cast<KX_2DFilter *>(AddFilter(bloomData, true));

	bloomI->SetTexture(0, bloomV0->GetOffScreen()->GetColorBindCode(0), "bgl_RenderedBloomI0");
	bloomI->SetTexture(1, bloomV1->GetOffScreen()->GetColorBindCode(0), "bgl_RenderedBloomI1");
	bloomI->SetTexture(2, bloomV2->GetOffScreen()->GetColorBindCode(0), "bgl_RenderedBloomI2");
	bloomI->SetTexture(3, bloomB0->GetOffScreen()->GetColorBindCode(0), "bgl_RenderedBloomB");

	for (int i = 0; i < 7; ++i) {
		RAS_2DFilterOffScreen *offScreen = GetFilterPass(FILTERPASS_BLOOM + i, true)->GetOffScreen();
		offScreen->SetRebuildCallback([this]() { RefreshBloomTextures(); });
	}
}

void KX_2DFilterManager::RefreshBloomTextures()
{
	KX_2DFilter *pass[8];
	for (int i = 0; i < 8; ++i) {
		pass[i] = static_cast<KX_2DFilter *>(GetFilterPass(FILTERPASS_BLOOM + i, true));
		if (!pass[i] || (i < 7 && !pass[i]->GetOffScreen())) {
			return;
		}
	}

	// Same links as EnsureBloomFilters: {filter, texture unit, source off screen}. A missing texture has no bind code.
	const struct { int filter; int unit; int source; } links[] = {
		{1, 0, 0}, {2, 0, 1}, {3, 0, 0}, {4, 0, 3}, {5, 0, 0}, {6, 0, 5},
		{7, 0, 2}, {7, 1, 4}, {7, 2, 6}, {7, 3, 0}
	};
	for (const auto& link : links) {
		const int bindCode = pass[link.source]->GetOffScreen()->GetColorBindCode(0);
		if (bindCode >= 0) {
			pass[link.filter]->UpdateTextureBindCode(link.unit, bindCode);
		}
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
	ssrData.buildInFilters = filters;
	ssrData.shaderText = datatoc_RAS_SSR2DFilter_glsl;

	KX_2DFilter *SSR = static_cast<KX_2DFilter *>(AddFilter(ssrData, true));
	KX_2DFilterOffScreen *offScreen = new KX_2DFilterOffScreen(1, (RAS_2DFilterOffScreen::Flag)0, (m_canvas->GetWidth() / filters.ssr_lod), (m_canvas->GetHeight() / filters.ssr_lod),
															   RAS_Rasterizer::HdrType::RAS_HDR_NONE);
	SSR->SetOffScreen(offScreen);

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

	SSR_Blur->SetTexture(0, SSR->GetOffScreen()->GetColorBindCode(0), "ssr_buffer");
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
	
	if (time == 0)
		bloomData.shaderText = datatoc_RAS_Bloom2DFilter_buf_glsl;
	else if (time == 1)
		bloomData.shaderText = datatoc_RAS_Bloom2DFilter_bufH_glsl;
	else if (time == 2)
		bloomData.shaderText = datatoc_RAS_Bloom2DFilter_bufV_glsl;

	bloom = static_cast<KX_2DFilter *>(AddFilter(bloomData, true));
	// The bloom buffers follow the canvas size divided by lod, so resize/fullscreen do not leave them stale.
	KX_2DFilterOffScreen *offScreen = new KX_2DFilterOffScreen(1, RAS_2DFilterOffScreen::RAS_CANVAS_DIVISOR, (w / lod), (h / lod),
																   RAS_Rasterizer::HdrType::RAS_HDR_NONE, lod);
	bloom->SetOffScreen(offScreen);

	return bloom;
}

RAS_2DFilter *KX_2DFilterManager::NewFilter(RAS_2DFilterData& filterData)
{
	return new KX_2DFilter(filterData);
}

#ifdef WITH_PYTHON
PyMethodDef KX_2DFilterManager::Methods[] = {
	// creation
	EXP_PYMETHODTABLE(KX_2DFilterManager, getFilter),
	EXP_PYMETHODTABLE(KX_2DFilterManager, addFilter),
	EXP_PYMETHODTABLE(KX_2DFilterManager, removeFilter),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeFxaaValues),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeTonemapValues),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeBloomValues),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeLightScatterValues),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeSSRValues),
	EXP_PYMETHODTABLE(KX_2DFilterManager, changeSSAOValues),
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_2DFilterManager::Attributes[] = {
	EXP_PYATTRIBUTE_NULL //Sentinel
};

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

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, addFilter, " addFilter(index, type, fragmentProgram)")
{
	int index = 0;
	int type = 0;
	const char *frag = "";

	if (!PyArg_ParseTuple(args, "ii|s:addFilter", &index, &type, &frag)) {
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

	if (type < FILTER_BLUR || type > FILTER_CUSTOMFILTER) {
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

	KX_2DFilter *filter = static_cast<KX_2DFilter *>(AddFilter(data, false));

	return filter->GetProxy();
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

EXP_PYMETHODDEF_DOC(KX_2DFilterManager, changeBloomValues, "changeBloomValues(enabled, intensity, threshold)")
{
	int enabled;
	float intensity = -1;
	float threshold;

	if (!PyArg_ParseTuple(args, "i|ff:changeBloomValues", &enabled, &intensity, &threshold)) {
		return nullptr;
	}

	RAS_2DFilter *Bloom_Image = GetFilterPass(FILTERPASS_BLOOM + 7, true);

	if (!Bloom_Image) {
		// The scene didn't start with Bloom enabled, so its filter chain was
		// never built. Build it now with the requested (or default) values
		// instead of silently doing nothing.
		BuildInFilters defaultFilters = {};
		defaultFilters.useBloom = true;
		defaultFilters.bloom_intensity = (intensity == -1) ? 2.0f : intensity;
		defaultFilters.bloom_threshold = (intensity == -1) ? 0.75f : threshold;
		EnsureBloomFilters(defaultFilters);
		Bloom_Image = GetFilterPass(FILTERPASS_BLOOM + 7, true);
	}

	RAS_2DFilter *Bloom0 = GetFilterPass(FILTERPASS_BLOOM, true);
	RAS_2DFilter *Bloom1 = GetFilterPass(FILTERPASS_BLOOM + 1, true);
	RAS_2DFilter *Bloom2 = GetFilterPass(FILTERPASS_BLOOM + 2, true);
	RAS_2DFilter *Bloom3 = GetFilterPass(FILTERPASS_BLOOM + 3, true);
	RAS_2DFilter *Bloom4 = GetFilterPass(FILTERPASS_BLOOM + 4, true);
	RAS_2DFilter *Bloom5 = GetFilterPass(FILTERPASS_BLOOM + 5, true);
	RAS_2DFilter *Bloom6 = GetFilterPass(FILTERPASS_BLOOM + 6, true);

	Bloom0->SetEnabled(enabled);
	Bloom1->SetEnabled(enabled);
	Bloom2->SetEnabled(enabled);
	Bloom3->SetEnabled(enabled);
	Bloom4->SetEnabled(enabled);
	Bloom5->SetEnabled(enabled);
	Bloom6->SetEnabled(enabled);
	Bloom_Image->SetEnabled(enabled);

	if (intensity == -1)
		Py_RETURN_NONE;

	BuildInFilters *filterParams = Bloom0->GetBuildInFilters();
	filterParams->bloom_intensity = intensity;
	filterParams->bloom_threshold = threshold;

	filterParams = Bloom1->GetBuildInFilters();
	filterParams->bloom_intensity = intensity;
	filterParams->bloom_threshold = threshold;

	filterParams = Bloom2->GetBuildInFilters();
	filterParams->bloom_intensity = intensity;
	filterParams->bloom_threshold = threshold;

	filterParams = Bloom3->GetBuildInFilters();
	filterParams->bloom_intensity = intensity;
	filterParams->bloom_threshold = threshold;

	filterParams = Bloom4->GetBuildInFilters();
	filterParams->bloom_intensity = intensity;
	filterParams->bloom_threshold = threshold;

	filterParams = Bloom5->GetBuildInFilters();
	filterParams->bloom_intensity = intensity;
	filterParams->bloom_threshold = threshold;

	filterParams = Bloom6->GetBuildInFilters();
	filterParams->bloom_intensity = intensity;
	filterParams->bloom_threshold = threshold;

	filterParams = Bloom_Image->GetBuildInFilters();
	filterParams->bloom_intensity = intensity;
	filterParams->bloom_threshold = threshold;

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
		SSAO = EnsureSSAOFilter(defaultFilters);
	}

	SSAO->SetEnabled(enabled);

	if (samples == -1)
		Py_RETURN_NONE;

	BuildInFilters *filterParams = SSAO->GetBuildInFilters();
	filterParams->ssao_samples = samples;
	filterParams->ssao_strength = strength;
	filterParams->ssao_distance = distance;
	filterParams->ssao_attenuation = attenuation;

	Py_RETURN_NONE;
}

#endif  // WITH_PYTHON
