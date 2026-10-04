/*
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
 * The Original Code is Copyright (C) 2012 Blender Foundation.
 * All rights reserved.
 */

#include <iostream>
#include <sstream>
#include <string.h>

#ifdef _MSC_VER
#  pragma warning(push)
#  pragma warning(disable : 4251 4275)
#endif
#include <OpenColorIO/OpenColorIO.h>
#ifdef _MSC_VER
#  pragma warning(pop)
#endif

using namespace OCIO_NAMESPACE;

#include "MEM_guardedalloc.h"

#include "ocio_impl.h"

#if OCIO_VERSION_HEX >= 0x02000000
#  include <set>
#  include "ocio_impl_v2.h"
#endif

#if !defined(WITH_ASSERT_ABORT)
#  define OCIO_abort()
#else
#  include <stdlib.h>
#  define OCIO_abort() abort()
#endif

#if defined(_MSC_VER)
#  define __func__ __FUNCTION__
#endif

/* NOTE: This is because OCIO 1.1.0 has a bug which makes default
 * display to be the one which is first alphabetically.
 *
 * Fix has been submitted as a patch
 *   https://github.com/imageworks/OpenColorIO/pull/638
 *
 * For until then we use first usable display instead. */
#define DEFAULT_DISPLAY_WORKAROUND
#include <mutex>

static void OCIO_reportError(const char *err)
{
	std::cerr << "OpenColorIO Error: " << err << std::endl;

	OCIO_abort();
}

static void OCIO_reportException(Exception &exception)
{
	OCIO_reportError(exception.what());
}

#ifdef OCIO_V2
/* Display transform handles are cast to OCIO_ConstTransformRcPtr by the caller (as in
 * the 1.x API); configGetProcessor() tells them apart from plain transforms here. */
static std::mutex display_transforms_mutex;
static std::set<const void *> display_transforms;

static void registerDisplayTransform(const void *dt, bool add)
{
	std::lock_guard<std::mutex> lock(display_transforms_mutex);
	if (add)
		display_transforms.insert(dt);
	else
		display_transforms.erase(dt);
}

static bool isDisplayTransform(const void *transform)
{
	std::lock_guard<std::mutex> lock(display_transforms_mutex);
	return display_transforms.count(transform) != 0;
}

static OCIO_ConstProcessorRcPtr *wrapProcessor(const ConstProcessorRcPtr &processor)
{
	if (!processor)
		return NULL;

	OCIO_ProcessorV2 *p = OBJECT_GUARDED_NEW(OCIO_ProcessorV2);
	p->processor = processor;
	p->cpu = processor->getDefaultCPUProcessor();
	return (OCIO_ConstProcessorRcPtr *) p;
}
#endif

OCIO_ConstConfigRcPtr *OCIOImpl::getCurrentConfig(void)
{
	ConstConfigRcPtr *config = OBJECT_GUARDED_NEW(ConstConfigRcPtr);

	try {
		*config = GetCurrentConfig();

		if (*config)
			return (OCIO_ConstConfigRcPtr *) config;
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	OBJECT_GUARDED_DELETE(config, ConstConfigRcPtr);

	return NULL;
}

void OCIOImpl::setCurrentConfig(const OCIO_ConstConfigRcPtr *config)
{
	try {
		SetCurrentConfig(*(ConstConfigRcPtr *) config);
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}
}

OCIO_ConstConfigRcPtr *OCIOImpl::configCreateFromEnv(void)
{
	ConstConfigRcPtr *config = OBJECT_GUARDED_NEW(ConstConfigRcPtr);

	try {
		*config = Config::CreateFromEnv();

		if (*config)
			return (OCIO_ConstConfigRcPtr *) config;
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	OBJECT_GUARDED_DELETE(config, ConstConfigRcPtr);

	return NULL;
}


OCIO_ConstConfigRcPtr *OCIOImpl::configCreateFromFile(const char *filename)
{
	ConstConfigRcPtr *config = OBJECT_GUARDED_NEW(ConstConfigRcPtr);

	try {
		*config = Config::CreateFromFile(filename);

		if (*config)
			return (OCIO_ConstConfigRcPtr *) config;
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	OBJECT_GUARDED_DELETE(config, ConstConfigRcPtr);

	return NULL;
}

void OCIOImpl::configRelease(OCIO_ConstConfigRcPtr *config)
{
	OBJECT_GUARDED_DELETE((ConstConfigRcPtr *) config, ConstConfigRcPtr);
}

int OCIOImpl::configGetNumColorSpaces(OCIO_ConstConfigRcPtr *config)
{
	try {
		return (*(ConstConfigRcPtr *) config)->getNumColorSpaces();
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return 0;
}

const char *OCIOImpl::configGetColorSpaceNameByIndex(OCIO_ConstConfigRcPtr *config, int index)
{
	try {
		return (*(ConstConfigRcPtr *) config)->getColorSpaceNameByIndex(index);
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return NULL;
}

OCIO_ConstColorSpaceRcPtr *OCIOImpl::configGetColorSpace(OCIO_ConstConfigRcPtr *config, const char *name)
{
	ConstColorSpaceRcPtr *cs = OBJECT_GUARDED_NEW(ConstColorSpaceRcPtr);

	try {
		*cs = (*(ConstConfigRcPtr *) config)->getColorSpace(name);

		if (*cs)
			return (OCIO_ConstColorSpaceRcPtr *) cs;
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	OBJECT_GUARDED_DELETE(cs, ConstColorSpaceRcPtr);

	return NULL;
}

int OCIOImpl::configGetIndexForColorSpace(OCIO_ConstConfigRcPtr *config, const char *name)
{
	try {
		return (*(ConstConfigRcPtr *) config)->getIndexForColorSpace(name);
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return -1;
}

const char *OCIOImpl::configGetDefaultDisplay(OCIO_ConstConfigRcPtr *config)
{
#ifdef DEFAULT_DISPLAY_WORKAROUND
	if (getenv("OCIO_ACTIVE_DISPLAYS") == NULL) {
		const char *active_displays =
		        (*(ConstConfigRcPtr *) config)->getActiveDisplays();
		const char *separator_pos = strchr(active_displays, ',');
		if (separator_pos == NULL) {
			return active_displays;
		}
		static std::string active_display;
		/* NOTE: Configuration is shared and is never changed during runtime,
		 * so we only guarantee two threads don't initialize at the same. */
		static std::mutex mutex;
		mutex.lock();
		if (active_display.empty()) {
			active_display = active_displays;
			active_display[separator_pos - active_displays] = '\0';
		}
		mutex.unlock();
		return active_display.c_str();
	}
#endif

	try {
		return (*(ConstConfigRcPtr *) config)->getDefaultDisplay();
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return NULL;
}

int OCIOImpl::configGetNumDisplays(OCIO_ConstConfigRcPtr* config)
{
	try {
		return (*(ConstConfigRcPtr *) config)->getNumDisplays();
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return 0;
}

const char *OCIOImpl::configGetDisplay(OCIO_ConstConfigRcPtr *config, int index)
{
	try {
		return (*(ConstConfigRcPtr *) config)->getDisplay(index);
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return NULL;
}

const char *OCIOImpl::configGetDefaultView(OCIO_ConstConfigRcPtr *config, const char *display)
{
#ifdef DEFAULT_DISPLAY_WORKAROUND
	/* NOTE: We assume that first active view always exists for a default
	 * display. */
	if (getenv("OCIO_ACTIVE_VIEWS") == NULL) {
		const char *active_views =
		        (*(ConstConfigRcPtr *) config)->getActiveViews();
		const char *separator_pos = strchr(active_views, ',');
		if (separator_pos == NULL) {
			return active_views;
		}
		static std::string active_view;
		/* NOTE: Configuration is shared and is never changed during runtime,
		 * so we only guarantee two threads don't initialize at the same. */
		static std::mutex mutex;
		mutex.lock();
		if (active_view.empty()) {
			active_view = active_views;
			active_view[separator_pos - active_views] = '\0';
		}
		mutex.unlock();
		return active_view.c_str();
	}
#endif
	try {
		return (*(ConstConfigRcPtr *) config)->getDefaultView(display);
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return NULL;
}

int OCIOImpl::configGetNumViews(OCIO_ConstConfigRcPtr *config, const char *display)
{
	try {
#ifdef OCIO_V2
		/* 2.x filters views by active_views, 1.x listed every view of the display
		 * (active_views only picked the default): keep listing all, so Filmic stays. */
		const ConstConfigRcPtr &cfg = *(ConstConfigRcPtr *) config;
		return cfg->getNumViews(VIEW_DISPLAY_DEFINED, display) + cfg->getNumViews(VIEW_SHARED, display);
#else
		return (*(ConstConfigRcPtr *) config)->getNumViews(display);
#endif
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return 0;
}

const char *OCIOImpl::configGetView(OCIO_ConstConfigRcPtr *config, const char *display, int index)
{
	try {
#ifdef OCIO_V2
		const ConstConfigRcPtr &cfg = *(ConstConfigRcPtr *) config;
		const int num_defined = cfg->getNumViews(VIEW_DISPLAY_DEFINED, display);
		if (index < num_defined)
			return cfg->getView(VIEW_DISPLAY_DEFINED, display, index);
		return cfg->getView(VIEW_SHARED, display, index - num_defined);
#else
		return (*(ConstConfigRcPtr *) config)->getView(display, index);
#endif
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return NULL;
}

const char *OCIOImpl::configGetDisplayColorSpaceName(OCIO_ConstConfigRcPtr *config, const char *display, const char *view)
{
	try {
#ifdef OCIO_V2
		return (*(ConstConfigRcPtr *) config)->getDisplayViewColorSpaceName(display, view);
#else
		return (*(ConstConfigRcPtr *) config)->getDisplayColorSpaceName(display, view);
#endif
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return NULL;
}

void OCIOImpl::configGetDefaultLumaCoefs(OCIO_ConstConfigRcPtr *config, float *rgb)
{
	try {
#ifdef OCIO_V2
		double rgb_d[3];
		(*(ConstConfigRcPtr *) config)->getDefaultLumaCoefs(rgb_d);
		rgb[0] = (float)rgb_d[0];
		rgb[1] = (float)rgb_d[1];
		rgb[2] = (float)rgb_d[2];
#else
		(*(ConstConfigRcPtr *) config)->getDefaultLumaCoefs(rgb);
#endif
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}
}

int OCIOImpl::configGetNumLooks(OCIO_ConstConfigRcPtr *config)
{
	try {
		return (*(ConstConfigRcPtr *) config)->getNumLooks();
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return 0;
}

const char *OCIOImpl::configGetLookNameByIndex(OCIO_ConstConfigRcPtr *config, int index)
{
	try {
		return (*(ConstConfigRcPtr *) config)->getLookNameByIndex(index);
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return NULL;
}

OCIO_ConstLookRcPtr *OCIOImpl::configGetLook(OCIO_ConstConfigRcPtr *config, const char *name)
{
	ConstLookRcPtr *look = OBJECT_GUARDED_NEW(ConstLookRcPtr);

	try {
		*look = (*(ConstConfigRcPtr *) config)->getLook(name);

		if (*look)
			return (OCIO_ConstLookRcPtr *) look;
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	OBJECT_GUARDED_DELETE(look, ConstLookRcPtr);

	return NULL;
}

const char *OCIOImpl::lookGetProcessSpace(OCIO_ConstLookRcPtr *look)
{
	return (*(ConstLookRcPtr *) look)->getProcessSpace();
}

void OCIOImpl::lookRelease(OCIO_ConstLookRcPtr *look)
{
	OBJECT_GUARDED_DELETE((ConstLookRcPtr *) look, ConstLookRcPtr);
}

int OCIOImpl::colorSpaceIsInvertible(OCIO_ConstColorSpaceRcPtr *cs_)
{
	ConstColorSpaceRcPtr *cs = (ConstColorSpaceRcPtr *) cs_;
	const char *family = (*cs)->getFamily();

	if (!strcmp(family, "rrt") || !strcmp(family, "display")) {
		/* assume display and rrt transformations are not invertible
		 * in fact some of them could be, but it doesn't make much sense to allow use them as invertible
		 */
		return false;
	}

	if ((*cs)->isData()) {
		/* data color spaces don't have transformation at all */
		return true;
	}

	if ((*cs)->getTransform(COLORSPACE_DIR_TO_REFERENCE)) {
		/* if there's defined transform to reference space, color space could be converted to scene linear */
		return true;
	}

	return true;
}

int OCIOImpl::colorSpaceIsData(OCIO_ConstColorSpaceRcPtr *cs)
{
	return (*(ConstColorSpaceRcPtr *) cs)->isData();
}

void OCIOImpl::colorSpaceRelease(OCIO_ConstColorSpaceRcPtr *cs)
{
	OBJECT_GUARDED_DELETE((ConstColorSpaceRcPtr *) cs, ConstColorSpaceRcPtr);
}

OCIO_ConstProcessorRcPtr *OCIOImpl::configGetProcessorWithNames(OCIO_ConstConfigRcPtr *config, const char *srcName, const char *dstName)
{
#ifdef OCIO_V2
	try {
		return wrapProcessor((*(ConstConfigRcPtr *) config)->getProcessor(srcName, dstName));
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return 0;
#else
	ConstProcessorRcPtr *p = OBJECT_GUARDED_NEW(ConstProcessorRcPtr);

	try {
		*p = (*(ConstConfigRcPtr *) config)->getProcessor(srcName, dstName);

		if (*p)
			return (OCIO_ConstProcessorRcPtr *) p;
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	OBJECT_GUARDED_DELETE(p, ConstProcessorRcPtr);

	return 0;
#endif
}

OCIO_ConstProcessorRcPtr *OCIOImpl::configGetProcessor(OCIO_ConstConfigRcPtr *config, OCIO_ConstTransformRcPtr *transform)
{
#ifdef OCIO_V2
	try {
		const ConstConfigRcPtr &cfg = *(ConstConfigRcPtr *) config;
		if (isDisplayTransform(transform)) {
			OCIO_DisplayTransformV2 *dt = (OCIO_DisplayTransformV2 *) transform;
			dt->pipeline->setDisplayViewTransform(dt->dvt);
			return wrapProcessor(dt->pipeline->getProcessor(cfg));
		}
		return wrapProcessor(cfg->getProcessor(*(ConstTransformRcPtr *) transform));
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return NULL;
#else
	ConstProcessorRcPtr *p = OBJECT_GUARDED_NEW(ConstProcessorRcPtr);

	try {
		*p = (*(ConstConfigRcPtr *) config)->getProcessor(*(ConstTransformRcPtr *) transform);

		if (*p)
			return (OCIO_ConstProcessorRcPtr *) p;
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	OBJECT_GUARDED_DELETE(p, ConstProcessorRcPtr);

	return NULL;
#endif
}

void OCIOImpl::processorApply(OCIO_ConstProcessorRcPtr *processor, OCIO_PackedImageDesc *img)
{
	try {
#ifdef OCIO_V2
		((OCIO_ProcessorV2 *) processor)->cpu->apply(*(PackedImageDesc *) img);
#else
		(*(ConstProcessorRcPtr *) processor)->apply(*(PackedImageDesc *) img);
#endif
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}
}

void OCIOImpl::processorApply_predivide(OCIO_ConstProcessorRcPtr *processor, OCIO_PackedImageDesc *img_)
{
	try {
		PackedImageDesc *img = (PackedImageDesc *) img_;
		int channels = img->getNumChannels();

		if (channels == 4) {
			float *pixels = (float *) img->getData();

			int width = img->getWidth();
			int height = img->getHeight();

			for (int y = 0; y < height; y++) {
				for (int x = 0; x < width; x++) {
					float *pixel = pixels + 4 * (y * width + x);

					processorApplyRGBA_predivide(processor, pixel);
				}
			}
		}
		else {
#ifdef OCIO_V2
			((OCIO_ProcessorV2 *) processor)->cpu->apply(*img);
#else
			(*(ConstProcessorRcPtr *) processor)->apply(*img);
#endif
		}
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}
}

void OCIOImpl::processorApplyRGB(OCIO_ConstProcessorRcPtr *processor, float *pixel)
{
#ifdef OCIO_V2
	((OCIO_ProcessorV2 *) processor)->cpu->applyRGB(pixel);
#else
	(*(ConstProcessorRcPtr *) processor)->applyRGB(pixel);
#endif
}

void OCIOImpl::processorApplyRGBA(OCIO_ConstProcessorRcPtr *processor, float *pixel)
{
#ifdef OCIO_V2
	((OCIO_ProcessorV2 *) processor)->cpu->applyRGBA(pixel);
#else
	(*(ConstProcessorRcPtr *) processor)->applyRGBA(pixel);
#endif
}

void OCIOImpl::processorApplyRGBA_predivide(OCIO_ConstProcessorRcPtr *processor, float *pixel)
{
	if (pixel[3] == 1.0f || pixel[3] == 0.0f) {
		processorApplyRGBA(processor, pixel);
	}
	else {
		float alpha, inv_alpha;

		alpha = pixel[3];
		inv_alpha = 1.0f / alpha;

		pixel[0] *= inv_alpha;
		pixel[1] *= inv_alpha;
		pixel[2] *= inv_alpha;

		processorApplyRGBA(processor, pixel);

		pixel[0] *= alpha;
		pixel[1] *= alpha;
		pixel[2] *= alpha;
	}
}

void OCIOImpl::processorRelease(OCIO_ConstProcessorRcPtr *p)
{
#ifdef OCIO_V2
	OBJECT_GUARDED_DELETE((OCIO_ProcessorV2 *) p, OCIO_ProcessorV2);
#else
	OBJECT_GUARDED_DELETE(p, ConstProcessorRcPtr);
#endif
}

const char *OCIOImpl::colorSpaceGetName(OCIO_ConstColorSpaceRcPtr *cs)
{
	return (*(ConstColorSpaceRcPtr *) cs)->getName();
}

const char *OCIOImpl::colorSpaceGetDescription(OCIO_ConstColorSpaceRcPtr *cs)
{
	return (*(ConstColorSpaceRcPtr *) cs)->getDescription();
}

const char *OCIOImpl::colorSpaceGetFamily(OCIO_ConstColorSpaceRcPtr *cs)
{
	return (*(ConstColorSpaceRcPtr *)cs)->getFamily();
}

#ifdef OCIO_V2
OCIO_DisplayTransformRcPtr *OCIOImpl::createDisplayTransform(void)
{
	OCIO_DisplayTransformV2 *dt = OBJECT_GUARDED_NEW(OCIO_DisplayTransformV2);

	dt->dvt = DisplayViewTransform::Create();
	dt->pipeline = LegacyViewingPipeline::Create();
	registerDisplayTransform(dt, true);

	return (OCIO_DisplayTransformRcPtr *) dt;
}

void OCIOImpl::displayTransformSetInputColorSpaceName(OCIO_DisplayTransformRcPtr *dt, const char *name)
{
	((OCIO_DisplayTransformV2 *) dt)->dvt->setSrc(name);
}

void OCIOImpl::displayTransformSetDisplay(OCIO_DisplayTransformRcPtr *dt, const char *name)
{
	((OCIO_DisplayTransformV2 *) dt)->dvt->setDisplay(name);
}

void OCIOImpl::displayTransformSetView(OCIO_DisplayTransformRcPtr *dt, const char *name)
{
	((OCIO_DisplayTransformV2 *) dt)->dvt->setView(name);
}

void OCIOImpl::displayTransformSetDisplayCC(OCIO_DisplayTransformRcPtr *dt, OCIO_ConstTransformRcPtr *t)
{
	((OCIO_DisplayTransformV2 *) dt)->pipeline->setDisplayCC(*(ConstTransformRcPtr *) t);
}

void OCIOImpl::displayTransformSetLinearCC(OCIO_DisplayTransformRcPtr *dt, OCIO_ConstTransformRcPtr *t)
{
	((OCIO_DisplayTransformV2 *) dt)->pipeline->setLinearCC(*(ConstTransformRcPtr *) t);
}

void OCIOImpl::displayTransformSetLooksOverride(OCIO_DisplayTransformRcPtr *dt, const char *looks)
{
	((OCIO_DisplayTransformV2 *) dt)->pipeline->setLooksOverride(looks);
}

void OCIOImpl::displayTransformSetLooksOverrideEnabled(OCIO_DisplayTransformRcPtr *dt, bool enabled)
{
	((OCIO_DisplayTransformV2 *) dt)->pipeline->setLooksOverrideEnabled(enabled);
}

void OCIOImpl::displayTransformRelease(OCIO_DisplayTransformRcPtr *dt)
{
	registerDisplayTransform(dt, false);
	OBJECT_GUARDED_DELETE((OCIO_DisplayTransformV2 *) dt, OCIO_DisplayTransformV2);
}

#else
OCIO_DisplayTransformRcPtr *OCIOImpl::createDisplayTransform(void)
{
	DisplayTransformRcPtr *dt = OBJECT_GUARDED_NEW(DisplayTransformRcPtr);

	*dt = DisplayTransform::Create();

	return (OCIO_DisplayTransformRcPtr *) dt;
}

void OCIOImpl::displayTransformSetInputColorSpaceName(OCIO_DisplayTransformRcPtr *dt, const char *name)
{
	(*(DisplayTransformRcPtr *) dt)->setInputColorSpaceName(name);
}

void OCIOImpl::displayTransformSetDisplay(OCIO_DisplayTransformRcPtr *dt, const char *name)
{
	(*(DisplayTransformRcPtr *) dt)->setDisplay(name);
}

void OCIOImpl::displayTransformSetView(OCIO_DisplayTransformRcPtr *dt, const char *name)
{
	(*(DisplayTransformRcPtr *) dt)->setView(name);
}

void OCIOImpl::displayTransformSetDisplayCC(OCIO_DisplayTransformRcPtr *dt, OCIO_ConstTransformRcPtr *t)
{
	(*(DisplayTransformRcPtr *) dt)->setDisplayCC(* (ConstTransformRcPtr *) t);
}

void OCIOImpl::displayTransformSetLinearCC(OCIO_DisplayTransformRcPtr *dt, OCIO_ConstTransformRcPtr *t)
{
	(*(DisplayTransformRcPtr *) dt)->setLinearCC(*(ConstTransformRcPtr *) t);
}

void OCIOImpl::displayTransformSetLooksOverride(OCIO_DisplayTransformRcPtr *dt, const char *looks)
{
	(*(DisplayTransformRcPtr *) dt)->setLooksOverride(looks);
}

void OCIOImpl::displayTransformSetLooksOverrideEnabled(OCIO_DisplayTransformRcPtr *dt, bool enabled)
{
	(*(DisplayTransformRcPtr *) dt)->setLooksOverrideEnabled(enabled);
}

void OCIOImpl::displayTransformRelease(OCIO_DisplayTransformRcPtr *dt)
{
	OBJECT_GUARDED_DELETE((DisplayTransformRcPtr *) dt, DisplayTransformRcPtr);
}

#endif

OCIO_PackedImageDesc *OCIOImpl::createOCIO_PackedImageDesc(float *data, long width, long height, long numChannels,
                                                           long chanStrideBytes, long xStrideBytes, long yStrideBytes)
{
	try {
		void *mem = MEM_mallocN(sizeof(PackedImageDesc), __func__);
#ifdef OCIO_V2
		PackedImageDesc *id = new(mem) PackedImageDesc(data, width, height, numChannels, BIT_DEPTH_F32,
		                                               chanStrideBytes, xStrideBytes, yStrideBytes);
#else
		PackedImageDesc *id = new(mem) PackedImageDesc(data, width, height, numChannels, chanStrideBytes, xStrideBytes, yStrideBytes);
#endif

		return (OCIO_PackedImageDesc *) id;
	}
	catch (Exception &exception) {
		OCIO_reportException(exception);
	}

	return NULL;
}

void OCIOImpl::OCIO_PackedImageDescRelease(OCIO_PackedImageDesc* id)
{
	OBJECT_GUARDED_DELETE((PackedImageDesc *) id, PackedImageDesc);
}

OCIO_ExponentTransformRcPtr *OCIOImpl::createExponentTransform(void)
{
	ExponentTransformRcPtr *et = OBJECT_GUARDED_NEW(ExponentTransformRcPtr);

	*et = ExponentTransform::Create();

	return (OCIO_ExponentTransformRcPtr *) et;
}

void OCIOImpl::exponentTransformSetValue(OCIO_ExponentTransformRcPtr *et, const float *exponent)
{
#ifdef OCIO_V2
	const double exponent_d[4] = {exponent[0], exponent[1], exponent[2], exponent[3]};
	(*(ExponentTransformRcPtr *) et)->setValue(exponent_d);
#else
	(*(ExponentTransformRcPtr *) et)->setValue(exponent);
#endif
}

void OCIOImpl::exponentTransformRelease(OCIO_ExponentTransformRcPtr *et)
{
	OBJECT_GUARDED_DELETE((ExponentTransformRcPtr *) et, ExponentTransformRcPtr);
}

OCIO_MatrixTransformRcPtr *OCIOImpl::createMatrixTransform(void)
{
	MatrixTransformRcPtr *mt = OBJECT_GUARDED_NEW(MatrixTransformRcPtr);

	*mt = MatrixTransform::Create();

	return (OCIO_MatrixTransformRcPtr *) mt;
}

void OCIOImpl::matrixTransformSetValue(OCIO_MatrixTransformRcPtr *mt, const float *m44, const float *offset4)
{
#ifdef OCIO_V2
	double m44_d[16], offset4_d[4];
	for (int i = 0; i < 16; i++)
		m44_d[i] = m44[i];
	for (int i = 0; i < 4; i++)
		offset4_d[i] = offset4[i];
	(*(MatrixTransformRcPtr *) mt)->setMatrix(m44_d);
	(*(MatrixTransformRcPtr *) mt)->setOffset(offset4_d);
#else
	(*(MatrixTransformRcPtr *) mt)->setValue(m44, offset4);
#endif
}

void OCIOImpl::matrixTransformRelease(OCIO_MatrixTransformRcPtr *mt)
{
	OBJECT_GUARDED_DELETE((MatrixTransformRcPtr *) mt, MatrixTransformRcPtr);
}

void OCIOImpl::matrixTransformScale(float *m44, float *offset4, const float *scale4f)
{
#ifdef OCIO_V2
	double m44_d[16], offset4_d[4], scale4_d[4];
	for (int i = 0; i < 4; i++)
		scale4_d[i] = scale4f[i];
	MatrixTransform::Scale(m44_d, offset4_d, scale4_d);
	for (int i = 0; i < 16; i++)
		m44[i] = (float)m44_d[i];
	for (int i = 0; i < 4; i++)
		offset4[i] = (float)offset4_d[i];
#else
	MatrixTransform::Scale(m44, offset4, scale4f);
#endif
}

const char *OCIOImpl::getVersionString(void)
{
	return GetVersion();
}

int OCIOImpl::getVersionHex(void)
{
	return GetVersionHex();
}
