/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Writes externo.ktx2 the way toktx/basisu would: colour UASTC, top row first, no Anastacio keys.
 * Then checks the block path of ktx2_api.cpp without a GPU: BC1/BC3 transcode + FlipDXTCImage must
 * put red in the first block row and blue in the last, in every level above 4 rows.
 * See testar_ktx2_marca.py. Build against build/lib/extern_basisu.lib, FlipDXT.cpp and the dds folder. */
#include <cstdio>
#include <vector>
#include "basisu_comp.h"
#include "basisu_transcoder.h"
#define FOURCC_DXT1 0x31545844
#define FOURCC_DXT5 0x35545844
#include "FlipDXT.h"

static void color0(const unsigned char *block, int &r, int &b)
{
	const int c = block[0] | (block[1] << 8);
	r = (c >> 11) * 255 / 31;
	b = (c & 31) * 255 / 31;
}

int main(int argc, char **argv)
{
	if (argc < 2) return 2;
	basisu::basisu_encoder_init();
	basist::basisu_transcoder_init();
	const int S = 64;
	basisu::image img(S, S);
	for (int y = 0; y < S; y++) for (int x = 0; x < S; x++) {
		const float v = 1.0f - y / float(S - 1), u = x / float(S - 1); /* row 0 is the top: blue */
		basisu::color_rgba &d = img(x, y);
		d.r = (uint8_t)((1.0f - v) * 255); d.g = (uint8_t)(u * 255); d.b = (uint8_t)(v * 255); d.a = 255;
	}
	basisu::vector<basisu::image> src;
	src.push_back(img);
	size_t size = 0;
	void *data = basisu::basis_compress2(basist::basis_tex_format::cUASTC_LDR_4x4, src,
	                                     basisu::cFlagKTX2 | basisu::cFlagThreaded | basisu::cFlagGenMipsClamp,
	                                     75, 4, &size);
	if (!data) return 1;
	FILE *f = fopen(argv[1], "wb");
	fwrite(data, 1, size, f);
	fclose(f);

	basist::ktx2_transcoder tr;
	if (!tr.init(data, (uint32_t)size) || !tr.start_transcoding()) return 1;
	printf("levels %u orientation key %s mark %s\n", tr.get_levels(), tr.find_key("KTXorientation") ? "yes" : "no",
	       tr.find_key("AnastacioNormalXY") ? "yes" : "no");
	int fails = 0;
	const struct { basist::transcoder_texture_format fmt; int fourcc, bytes, colour_at; const char *name; } targets[] = {
		{basist::transcoder_texture_format::cTFBC1_RGB, FOURCC_DXT1, 8, 0, "BC1"},
		{basist::transcoder_texture_format::cTFBC3_RGBA, FOURCC_DXT5, 16, 8, "BC3"},
	};
	for (const auto &t : targets) {
		std::vector<unsigned char> blocks;
		std::vector<size_t> offset;
		for (unsigned l = 0, w = S; l < tr.get_levels(); l++, w = w > 1 ? w / 2 : 1) {
			const uint32_t per = (w + 3) / 4, count = per * per;
			offset.push_back(blocks.size());
			blocks.resize(blocks.size() + (size_t)count * t.bytes);
			if (!tr.transcode_image_level(l, 0, 0, blocks.data() + offset[l], count, t.fmt)) return 1;
		}
		FlipDXTCImage(S, S, tr.get_levels(), t.fourcc, blocks.data());
		for (unsigned l = 0, w = S; w >= 8; l++, w /= 2) {
			const uint32_t per = w / 4;
			int r0, b0, r1, b1;
			color0(blocks.data() + offset[l] + t.colour_at, r0, b0);
			color0(blocks.data() + offset[l] + (size_t)(per - 1) * per * t.bytes + t.colour_at, r1, b1);
			const bool ok = r0 > b0 && b1 > r1;
			printf("%s level %u first row r%d b%d, last row r%d b%d %s\n", t.name, l, r0, b0, r1, b1, ok ? "ok" : "FAIL");
			fails += !ok;
		}
	}
	basisu::basis_free_data(data);
	printf("KTX2_EXTERNO %s\n", fails ? "FAIL" : "OK");
	return fails != 0;
}
