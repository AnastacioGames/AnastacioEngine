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
 */

/** \file blender/imbuf/intern/dds/dds_api.cpp
 *  \ingroup imbdds
 */


extern "C" {
#include "BLI_utildefines.h"
}

#include <stddef.h>
#include <dds_api.h>
#include <Stream.h>
#include <DirectDrawSurface.h>
#include <FlipDXT.h>
#include <BlockDXT.h>
#include <ColorBlock.h>
#include <stdio.h> // printf
#include <fstream>
#include <string.h> // memcpy

#if defined (WIN32)
#include "utfconv.h"
#endif

extern "C" {

#include "imbuf.h"
#include "IMB_imbuf_types.h"
#include "IMB_imbuf.h"
#include "IMB_allocimbuf.h"

#include "IMB_colormanagement.h"
#include "IMB_colormanagement_intern.h"

int imb_save_dds(struct ImBuf *ibuf, const char *name, int /*flags*/)
{
	return(0); /* todo: finish this function */

	/* check image buffer */
	if (ibuf == 0) return (0);
	if (ibuf->rect == 0) return (0);

	/* open file for writing */
	std::ofstream fildes;

#if defined (WIN32)
	wchar_t *wname = alloc_utf16_from_8(name, 0);
	fildes.open(wname);
	free(wname);
#else
	fildes.open(name);
#endif

	/* write header */
	fildes << "DDS ";
	fildes.close();

	return(1);
}

int imb_is_a_dds(const unsigned char *mem) // note: use at most first 32 bytes
{
	/* heuristic check to see if mem contains a DDS file */
	/* header.fourcc == FOURCC_DDS */
	if ((mem[0] != 'D') || (mem[1] != 'D') || (mem[2] != 'S') || (mem[3] != ' ')) return(0);
	/* header.size == 124 */
	if ((mem[4] != 124) || mem[5] || mem[6] || mem[7]) return(0);
	return(1);
}

static bool dds_is_dxt(unsigned int fourcc)
{
	return fourcc == FOURCC_DXT1 || fourcc == FOURCC_DXT3 || fourcc == FOURCC_DXT5;
}

static unsigned int dds_block_size(unsigned int fourcc)
{
	return (fourcc == FOURCC_DXT1) ? 8 : 16;
}

static bool dds_is_pot(unsigned int n)
{
	return n && (n & (n - 1)) == 0;
}

/* How many mipmap levels of the chain are fully inside the data, so a truncated file never
 * makes the GPU upload read past the buffer. */
static unsigned int dds_levels_present(unsigned int width, unsigned int height, unsigned int count,
                                       unsigned int blocksize, unsigned int datasize)
{
	unsigned int offset = 0, levels = 0;
	for (unsigned int i = 0; i < count && (width || height); i++) {
		width = MAX2(width, 1u);
		height = MAX2(height, 1u);
		const unsigned int size = ((width + 3) / 4) * ((height + 3) / 4) * blocksize;
		if (size > datasize - offset || offset > datasize) {
			break;
		}
		offset += size;
		levels++;
		width >>= 1;
		height >>= 1;
	}
	return levels;
}

/* Whether the first level has a texel that is not opaque, read from the blocks without decoding
 * the colors. Matches the alpha the full decode would produce. */
static bool dds_blocks_have_alpha(const unsigned char *data, unsigned int width, unsigned int height,
                                  unsigned int fourcc)
{
	const unsigned int blocks = ((width + 3) / 4) * ((height + 3) / 4);
	for (unsigned int i = 0; i < blocks; i++) {
		if (fourcc == FOURCC_DXT1) {
			BlockDXT1 block;
			memcpy(&block, data + i * 8, sizeof(block));
			if (block.col0.u <= block.col1.u) {
				/* three color mode: index 3 is transparent black */
				for (unsigned int k = 0; k < 16; k++) {
					if (((block.indices >> (2 * k)) & 3) == 3) {
						return true;
					}
				}
			}
		}
		else if (fourcc == FOURCC_DXT3) {
			const unsigned char *alpha = data + i * 16;
			for (unsigned int k = 0; k < 8; k++) {
				if (alpha[k] != 0xff) {
					return true;
				}
			}
		}
		else {
			AlphaBlockDXT5 alpha;
			memcpy(&alpha, data + i * 16, sizeof(alpha));
			uint8 palette[8], index[16];
			alpha.evaluatePalette(palette);
			alpha.indices(index);
			for (unsigned int k = 0; k < 16; k++) {
				if (palette[index[k]] != 0xff) {
					return true;
				}
			}
		}
	}
	return false;
}

/* The blocks are already flipped (FlipDXTCImage), so decoding them in order gives the bottom-up
 * rows ImBuf expects. */
bool imb_dds_decode_rect(struct ImBuf *ibuf)
{
	const unsigned int fourcc = ibuf->dds_data.fourcc;
	if (ibuf->rect) {
		return true;
	}
	if (ibuf->dds_data.data == NULL || !dds_is_dxt(fourcc)) {
		return false;
	}
	const unsigned int width = ibuf->x, height = ibuf->y;
	const unsigned int blocksize = dds_block_size(fourcc);
	if (dds_levels_present(width, height, 1, blocksize, ibuf->dds_data.size) == 0) {
		return false;
	}
	if (!imb_addrectImBuf(ibuf)) {
		return false;
	}

	unsigned char *rect = (unsigned char *)ibuf->rect;
	const unsigned int bw = (width + 3) / 4, bh = (height + 3) / 4;
	const unsigned char *src = ibuf->dds_data.data;
	for (unsigned int by = 0; by < bh; by++) {
		for (unsigned int bx = 0; bx < bw; bx++, src += blocksize) {
			ColorBlock block;
			if (fourcc == FOURCC_DXT1) {
				BlockDXT1 dxt;
				memcpy(&dxt, src, sizeof(dxt));
				dxt.decodeBlock(&block);
			}
			else if (fourcc == FOURCC_DXT3) {
				BlockDXT3 dxt;
				memcpy(&dxt, src, sizeof(dxt));
				dxt.decodeBlock(&block);
			}
			else {
				BlockDXT5 dxt;
				memcpy(&dxt, src, sizeof(dxt));
				dxt.decodeBlock(&block);
			}
			for (unsigned int y = 0; y < MIN2(4u, height - 4 * by); y++) {
				unsigned char *row = rect + 4 * ((size_t)(4 * by + y) * width + 4 * bx);
				for (unsigned int x = 0; x < MIN2(4u, width - 4 * bx); x++) {
					const Color32 c = block.color(x, y);
					row[4 * x + 0] = c.r;
					row[4 * x + 1] = c.g;
					row[4 * x + 2] = c.b;
					row[4 * x + 3] = c.a;
				}
			}
		}
	}
	return true;
}

/* IB_dds_blocks: a DXT1/3/5 2D texture, power of two, keeps only its blocks. Pixels are decoded
 * later by IMB_dds_ensure_rect() if anything asks for them (fallback upload, paint, Python). */
static struct ImBuf *dds_load_blocks_only(DirectDrawSurface &dds)
{
	const unsigned int fourcc = dds.fourCC();
	const unsigned int width = dds.width(), height = dds.height();
	unsigned int datasize = 0;
	unsigned char *data = (unsigned char *)dds.readData(datasize);
	if (data == NULL) {
		return NULL;
	}
	const unsigned int levels = dds_levels_present(width, height, dds.mipmapCount(),
	                                               dds_block_size(fourcc), datasize);
	if (levels == 0) {
		free(data);
		return NULL;
	}
	if (levels < dds.mipmapCount()) {
		printf("DDS: truncated, %u of %u mipmap levels present\n", levels, dds.mipmapCount());
	}

	const unsigned char planes = dds_blocks_have_alpha(data, width, height, fourcc) ? 32 : 24;
	ImBuf *ibuf = IMB_allocImBuf(width, height, planes, 0);
	if (ibuf == NULL) {
		free(data);
		return NULL;
	}
	FlipDXTCImage(width, height, levels, fourcc, data);
	ibuf->ftype = IMB_FTYPE_DDS;
	ibuf->dds_data.fourcc = fourcc;
	ibuf->dds_data.nummipmaps = levels;
	ibuf->dds_data.data = data;
	ibuf->dds_data.size = datasize;
	return ibuf;
}

struct ImBuf *imb_load_dds(const unsigned char *mem, size_t size, int flags, char colorspace[IM_MAX_SPACE])
{
	struct ImBuf *ibuf = NULL;
	DirectDrawSurface dds((unsigned char *)mem, size); /* reads header */
	unsigned char bits_per_pixel;
	unsigned int *rect;
	Image img;
	unsigned int numpixels = 0;
	int col;
	unsigned char *cp = (unsigned char *) &col;
	Color32 pixel;
	Color32 *pixels = 0;

	/* OCIO_TODO: never was able to save DDS, so can't test loading
	 *            but profile used to be set to sRGB and can't see rect_float here, so
	 *            default byte space should work fine
	 */
	colorspace_set_default_role(colorspace, IM_MAX_SPACE, COLOR_ROLE_DEFAULT_BYTE);

	if (!imb_is_a_dds(mem))
		return (0);

	/* check if DDS is valid and supported */
	if (!dds.isValid()) {
		/* no need to print error here, just testing if it is a DDS */
		if (flags & IB_test)
			return (0);

		printf("DDS: not valid; header follows\n");
		dds.printInfo();
		return(0);
	}
	if (!dds.isSupported()) {
		printf("DDS: format not supported\n");
		return(0);
	}
	if ((dds.width() > 65535) || (dds.height() > 65535)) {
		printf("DDS: dimensions too large\n");
		return(0);
	}

	if ((flags & IB_dds_blocks) && !(flags & (IB_test | IB_ignore_alpha | IB_alphamode_premul)) &&
	    dds_is_dxt(dds.fourCC()) && dds.isTexture2D() && dds_is_pot(dds.width()) && dds_is_pot(dds.height()))
	{
		ibuf = dds_load_blocks_only(dds);
		if (ibuf) {
			return ibuf;
		}
		/* truncated or out of memory: the full decode below reports it */
	}

	/* convert DDS into ImBuf */
	dds.mipmap(&img, 0, 0); /* load first face, first mipmap */
	pixels = img.pixels();
	numpixels = dds.width() * dds.height();
	bits_per_pixel = 24;
	if (img.format() == Image::Format_ARGB) {
		/* check that there is effectively an alpha channel */
		for (unsigned int i = 0; i < numpixels; i++) {
			pixel = pixels[i];
			if (pixel.a != 255) {
				bits_per_pixel = 32;
				break;
			}
		}
	}
	ibuf = IMB_allocImBuf(dds.width(), dds.height(), bits_per_pixel, 0);
	if (ibuf == 0) return(0); /* memory allocation failed */

	ibuf->ftype = IMB_FTYPE_DDS;
	ibuf->dds_data.fourcc = dds.fourCC();
	ibuf->dds_data.nummipmaps = dds.mipmapCount();

	if ((flags & IB_test) == 0) {
		if (!imb_addrectImBuf(ibuf)) return(ibuf);
		if (ibuf->rect == 0) return(ibuf);

		rect = ibuf->rect;
		cp[3] = 0xff; /* default alpha if alpha channel is not present */

		for (unsigned int i = 0; i < numpixels; i++) {
			pixel = pixels[i];
			cp[0] = pixel.r; /* set R component of col */
			cp[1] = pixel.g; /* set G component of col */
			cp[2] = pixel.b; /* set B component of col */
			if (dds.hasAlpha())
				cp[3] = pixel.a; /* set A component of col */
			rect[i] = col;
		}

		if (ibuf->dds_data.fourcc != FOURCC_DDS) {
			ibuf->dds_data.data = (unsigned char *)dds.readData(ibuf->dds_data.size);
			ibuf->dds_data.nummipmaps = 0;
			if (ibuf->dds_data.data && dds_is_dxt(dds.fourCC())) {
				/* a truncated chain uploads only the levels it has */
				ibuf->dds_data.nummipmaps = dds_levels_present(
				        dds.width(), dds.height(), dds.mipmapCount(), dds_block_size(dds.fourCC()),
				        ibuf->dds_data.size);
			}

			/* flip compressed texture */
			if (ibuf->dds_data.nummipmaps) {
				FlipDXTCImage(dds.width(), dds.height(), ibuf->dds_data.nummipmaps, dds.fourCC(),
				              ibuf->dds_data.data);
			}
		}
		else {
			ibuf->dds_data.data = NULL;
			ibuf->dds_data.size = 0;
		}

		/* flip uncompressed texture */
		IMB_flipy(ibuf);
	}

	return(ibuf);
}

} // extern "C"
