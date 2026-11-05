/* SPDX-License-Identifier: GPL-2.0-or-later */
/** \file blender/imbuf/intern/dds/ktx2_api.cpp
 *  \ingroup imbdds
 *
 * KTX2 / Basis Universal: one file that becomes BC (desktop), ETC2 or ASTC (phones) at load.
 * The loader transcodes into the same DDSData blocks the DDS path uses, so the GPU upload is shared.
 *
 * Files from imb_ktx2_write() keep ImBuf rows in memory order (bottom row first) and say so with
 * KTXorientation "ru"; without that key a file is top first, the KTX2 default, and gets flipped here.
 * Colour textures are ETC1S; tangent-space normal maps are UASTC with X in RGB and Y in alpha,
 * the layout Basis needs to produce BC5 / EAC RG11 (the shader rebuilds Z when blue is 0). Only the
 * AnastacioNormalXY key means that layout: any other UASTC file is a plain colour texture.
 */

#include <cstdlib>
#include <cstring>
#include <cmath>
#include <mutex>
#include <vector>

#include "basisu_transcoder.h"
#include "FlipDXT.h"

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

/* the one rule for both load paths */
bool is_normal_xy(const basist::ktx2_transcoder &tr)
{
	const basisu::uint8_vec *mark = tr.find_key("AnastacioNormalXY");
	return mark && mark->size() && (*mark)[0] == '1';
}

/* KTXorientation is "rd" (the default) or "ru" for 2D: the second letter is the row direction */
bool rows_top_first(const basist::ktx2_transcoder &tr)
{
	const basisu::uint8_vec *orientation = tr.find_key("KTXorientation");
	return !(orientation && orientation->size() >= 2 && (*orientation)[1] == 'u');
}

void flip_rows(ImBuf *ibuf)
{
	const size_t row = (size_t)ibuf->x;
	std::vector<unsigned int> line(row);
	for (int y = 0; y < ibuf->y / 2; y++) {
		unsigned int *a = ibuf->rect + y * row, *b = ibuf->rect + (ibuf->y - 1 - y) * row;
		memcpy(line.data(), a, row * 4);
		memcpy(a, b, row * 4);
		memcpy(b, line.data(), row * 4);
	}
}

/* Prepare Textures files from before the mark are read as colour; a small mip is enough to warn
 * about one, since X/X/X/Y has grey RGB and a varying alpha. */
void warn_old_normal(basist::ktx2_transcoder &tr)
{
	const uint32_t levels = tr.get_levels() ? tr.get_levels() : 1;
	const uint32_t level = levels > 4 ? levels - 4 : levels - 1;
	basist::ktx2_image_level_info info;
	if (!tr.get_image_level_info(info, level, 0, 0)) {
		return;
	}
	const uint32_t pixels = info.m_orig_width * info.m_orig_height;
	std::vector<unsigned char> p((size_t)pixels * 4);
	if (!tr.transcode_image_level(level, 0, 0, p.data(), pixels, basist::transcoder_texture_format::cTFRGBA32)) {
		return;
	}
	bool varying = false;
	for (uint32_t i = 0; i < pixels; i++) {
		const unsigned char *c = &p[(size_t)i * 4];
		if (c[0] != c[1] || c[0] != c[2]) {
			return;
		}
		varying = varying || c[3] != p[3];
	}
	if (varying) {
		printf("KTX2: UASTC file without the normal map mark looks like an old normal map; "
		       "run Prepare Textures or export again\n");
	}
}

/* level 0 as RGBA8 into ibuf->rect, bottom row first; normal maps go from (X, X, X, Y) back to
 * (X, Y, Z, 255) */
bool decode_rgba(basist::ktx2_transcoder &tr, ImBuf *ibuf)
{
	const bool normal = is_normal_xy(tr);
	if (!ibuf->rect && !imb_addrectImBuf(ibuf)) {
		return false;
	}
	const uint32_t pixels = (uint32_t)ibuf->x * (uint32_t)ibuf->y;
	if (!tr.transcode_image_level(0, 0, 0, ibuf->rect, pixels, basist::transcoder_texture_format::cTFRGBA32)) {
		imb_freerectImBuf(ibuf);
		return false;
	}
	if (rows_top_first(tr)) {
		flip_rows(ibuf);
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
	return decode_rgba(tr, ibuf);
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
	const bool normal = is_normal_xy(tr);
	const bool flip = rows_top_first(tr);
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

	if (tr.is_uastc() && !normal) {
		warn_old_normal(tr);
	}

	Target t;
	bool blocks = pot(width) && pot(height) && !(flags & (IB_ignore_alpha | IB_alphamode_premul)) &&
	              pick_target(normal, alpha, t);
	if (blocks && flip && t.fourcc != FOURCC_DXT1 && t.fourcc != FOURCC_DXT5 && t.fourcc != FOURCC_ATI2) {
		/* FlipDXTCImage has no ETC2/ASTC: pixels can be flipped, these blocks cannot */
		printf("KTX2: top-first file on ETC2/ASTC, decoding to RGBA\n");
		blocks = false;
	}
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
			if (flip) {
				FlipDXTCImage(width, height, done, t.fourcc, data);
			}
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
	if (!decode_rgba(tr, ibuf)) {
		printf("KTX2: RGBA decode failed\n");
		IMB_freeImBuf(ibuf);
		return NULL;
	}
	return ibuf;
}

}  /* extern "C" */
