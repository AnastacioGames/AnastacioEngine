/* SPDX-License-Identifier: GPL-2.0-or-later */
/** \file blender/imbuf/intern/dds/ktx2_api.cpp
 *  \ingroup imbdds
 *
 * KTX2 / Basis Universal: one file that becomes BC (desktop), ETC2 or ASTC (phones) at load.
 * The loader transcodes into the same DDSData blocks the DDS path uses, so the GPU upload is shared.
 *
 * Files are written by imb_ktx2_write() with ImBuf rows in memory order (bottom row first), so the
 * transcoded blocks and RGBA pixels already have the orientation ImBuf and OpenGL expect.
 * Colour textures are ETC1S; tangent-space normal maps are UASTC with X in RGB and Y in alpha,
 * the layout Basis needs to produce BC5 / EAC RG11 (the shader rebuilds Z when blue is 0).
 */

#include <cstdlib>
#include <cstring>
#include <cmath>
#include <mutex>

#include "basisu_transcoder.h"

extern "C" {
#include "BLI_utildefines.h"
#include "IMB_imbuf_types.h"
#include "IMB_imbuf.h"
#include "IMB_allocimbuf.h"
#include "IMB_colormanagement.h"
#include "IMB_colormanagement_intern.h"
#include "dds_api.h"
}

static int g_gpu_formats = 0;

namespace {

const unsigned char ktx2_id[12] = {0xAB, 'K', 'T', 'X', ' ', '2', '0', 0xBB, '\r', '\n', 0x1A, '\n'};

void transcoder_init()
{
	static std::once_flag once;
	std::call_once(once, []() { basist::basisu_transcoder_init(); });
}

bool pot(unsigned int v) { return v && (v & (v - 1)) == 0; }

struct Target {
	basist::transcoder_texture_format fmt;
	unsigned int fourcc;
	unsigned int blocksize;
};

/* Desktop BC first; ETC2 is lossless from ETC1S and half the size of ASTC 4x4 for opaque colour.
 * Normal maps need a two-channel target: BC5 or EAC RG11, otherwise RGBA pixels. */
bool pick_target(bool normal, bool alpha, Target &t)
{
	const int f = g_gpu_formats;
	if (normal) {
		if (f & IMB_KTX2_GPU_BC5) { t = {basist::transcoder_texture_format::cTFBC5_RG, FOURCC_ATI2, 16}; return true; }
		if (f & IMB_KTX2_GPU_ETC2) { t = {basist::transcoder_texture_format::cTFETC2_EAC_RG11, FOURCC_EAC2, 16}; return true; }
		return false;
	}
	if (f & IMB_KTX2_GPU_BC) {
		t = alpha ? Target{basist::transcoder_texture_format::cTFBC3_RGBA, FOURCC_DXT5, 16} :
		            Target{basist::transcoder_texture_format::cTFBC1_RGB, FOURCC_DXT1, 8};
		return true;
	}
	if (f & IMB_KTX2_GPU_ETC2) {
		t = alpha ? Target{basist::transcoder_texture_format::cTFETC2_RGBA, FOURCC_ETCA, 16} :
		            Target{basist::transcoder_texture_format::cTFETC1_RGB, FOURCC_ETC2, 8};
		return true;
	}
	if (f & IMB_KTX2_GPU_ASTC) {
		t = {basist::transcoder_texture_format::cTFASTC_4x4_RGBA, FOURCC_AST4, 16};
		return true;
	}
	return false;
}

/* level 0 as RGBA8 into ibuf->rect; normal maps go from (X, X, X, Y) back to (X, Y, Z, 255) */
bool decode_rgba(basist::ktx2_transcoder &tr, ImBuf *ibuf, bool normal)
{
	if (!ibuf->rect && !imb_addrectImBuf(ibuf)) {
		return false;
	}
	const uint32_t pixels = (uint32_t)ibuf->x * (uint32_t)ibuf->y;
	if (!tr.transcode_image_level(0, 0, 0, ibuf->rect, pixels, basist::transcoder_texture_format::cTFRGBA32)) {
		imb_freerectImBuf(ibuf);
		return false;
	}
	if (normal) {
		unsigned char *p = (unsigned char *)ibuf->rect;
		for (uint32_t i = 0; i < pixels; i++, p += 4) {
			const float x = p[0] / 127.5f - 1.0f, y = p[3] / 127.5f - 1.0f;
			const float z = sqrtf(MAX2(0.0f, 1.0f - x * x - y * y));
			p[1] = p[3];
			p[2] = (unsigned char)MIN2(255.0f, z * 127.5f + 128.0f);
			p[3] = 255;
		}
	}
	return true;
}

}  /* namespace */

extern "C" {

void IMB_ktx2_set_gpu_formats(int formats)
{
	g_gpu_formats = formats;
}

int IMB_ktx2_gpu_formats(void)
{
	return g_gpu_formats;
}

int imb_is_a_ktx2(const unsigned char *mem)
{
	return memcmp(mem, ktx2_id, sizeof(ktx2_id)) == 0;
}

bool imb_ktx2_decode_rect(struct ImBuf *ibuf)
{
	if (ibuf->rect) {
		return true;
	}
	if (!ibuf->dds_data.ktx2) {
		return false;
	}
	transcoder_init();
	basist::ktx2_transcoder tr;
	if (!tr.init(ibuf->dds_data.ktx2, ibuf->dds_data.ktx2_size) || !tr.start_transcoding()) {
		return false;
	}
	return decode_rgba(tr, ibuf, tr.is_uastc());
}

struct ImBuf *imb_load_ktx2(const unsigned char *mem, size_t size, int flags, char colorspace[IM_MAX_SPACE])
{
	colorspace_set_default_role(colorspace, IM_MAX_SPACE, COLOR_ROLE_DEFAULT_BYTE);
	if (size < sizeof(ktx2_id) || !imb_is_a_ktx2(mem)) {
		return NULL;
	}
	transcoder_init();
	basist::ktx2_transcoder tr;
	if (!tr.init(mem, (uint32_t)size)) {
		printf("KTX2: not valid\n");
		return NULL;
	}
	const unsigned int width = tr.get_width(), height = tr.get_height();
	if (tr.is_hdr() || tr.get_layers() > 1 || tr.get_faces() > 1 || width == 0 || height == 0 ||
	    width > 16384 || height > 16384 || !(tr.is_etc1s() || tr.is_uastc()))
	{
		printf("KTX2: only 2D LDR ETC1S/UASTC textures are supported\n");
		return NULL;
	}
	const bool normal = tr.is_uastc();
	const bool alpha = !normal && tr.get_has_alpha();
	ImBuf *ibuf = IMB_allocImBuf(width, height, alpha ? 32 : 24, 0);
	if (!ibuf) {
		return NULL;
	}
	/* shares the DDS type: the compressed upload and pixel-on-demand paths are the same */
	ibuf->ftype = IMB_FTYPE_DDS;
	if (flags & IB_test) {
		return ibuf;
	}
	if (!tr.start_transcoding()) {
		printf("KTX2: transcoding failed to start\n");
		IMB_freeImBuf(ibuf);
		return NULL;
	}

	Target t;
	const bool blocks = pot(width) && pot(height) && !(flags & (IB_ignore_alpha | IB_alphamode_premul)) &&
	                    pick_target(normal, alpha, t);
	if (blocks) {
		const unsigned int levels = tr.get_levels() ? tr.get_levels() : 1;
		size_t total = 0;
		for (unsigned int l = 0, w = width, h = height; l < levels; l++, w = MAX2(1u, w / 2), h = MAX2(1u, h / 2)) {
			total += (size_t)((w + 3) / 4) * ((h + 3) / 4) * t.blocksize;
		}
		unsigned char *data = (unsigned char *)malloc(total);
		size_t offset = 0;
		unsigned int done = 0;
		for (unsigned int l = 0, w = width, h = height; data && l < levels; l++, w = MAX2(1u, w / 2), h = MAX2(1u, h / 2)) {
			const uint32_t count = ((w + 3) / 4) * ((h + 3) / 4);
			if (!tr.transcode_image_level(l, 0, 0, data + offset, count, t.fmt)) {
				break;
			}
			offset += (size_t)count * t.blocksize;
			done++;
		}
		if (data && done) {
			ibuf->dds_data.fourcc = t.fourcc;
			ibuf->dds_data.nummipmaps = done;
			ibuf->dds_data.data = data;
			ibuf->dds_data.size = (unsigned int)offset;
			if (flags & IB_dds_blocks) {
				/* pixels only if something asks: keep the (small) source to transcode them then */
				ibuf->dds_data.ktx2 = (unsigned char *)malloc(size);
				if (ibuf->dds_data.ktx2) {
					memcpy(ibuf->dds_data.ktx2, mem, size);
					ibuf->dds_data.ktx2_size = (unsigned int)size;
					return ibuf;
				}
			}
		}
		else {
			free(data);
			printf("KTX2: block transcode failed, decoding to RGBA\n");
		}
	}
	if (!decode_rgba(tr, ibuf, normal)) {
		printf("KTX2: RGBA decode failed\n");
		IMB_freeImBuf(ibuf);
		return NULL;
	}
	return ibuf;
}

}  /* extern "C" */
