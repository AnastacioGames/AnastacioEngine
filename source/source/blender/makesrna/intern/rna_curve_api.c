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
 * The Original Code is Copyright (C) 2009 Blender Foundation.
 * All rights reserved.
 */

/** \file blender/makesrna/intern/rna_curve_api.c
 *  \ingroup RNA
 */


#include <stdlib.h>
#include <stdio.h>

#include "RNA_define.h"

#include "BLI_sys_types.h"

#include "BLI_utildefines.h"

#include "BKE_curve.h"

#include "MEM_guardedalloc.h"

#include "DNA_curve_types.h"
#include "DNA_image_types.h"
#include "DNA_packedFile_types.h"
#include "DNA_vfont_types.h"

#include "rna_internal.h"  /* own include */

#ifdef RNA_RUNTIME
static void rna_Curve_transform(Curve *cu, float *mat, bool shape_keys)
{
	BKE_curve_transform(cu, (float (*)[4])mat, shape_keys, true);

	DAG_id_tag_update(&cu->id, 0);
}
static void rna_Curve_atlas_glyphs_resize(Curve *cu, int count)
{
	MEM_SAFE_FREE(cu->atlas_glyphs);
	cu->atlas_count = 0;
	if (count > 0) {
		cu->atlas_glyphs = MEM_calloc_arrayN(count, sizeof(TextAtlasGlyph), "atlas_glyphs");
		cu->atlas_count = count;
	}
	DAG_id_tag_update(&cu->id, 0);
}


#include "BLF_api.h"
#include "BLI_path_util.h"
#include "BLI_math_base.h"
#include "BLI_rect.h"
#include "BLI_string.h"
#include "BLI_string_utf8.h"
#include "BKE_font.h"
#include "BKE_image.h"
#include "BKE_library.h"
#include "BKE_main.h"
#include "BKE_report.h"
#include "IMB_imbuf.h"
#include "IMB_imbuf_types.h"

static int atlas_font_load(Main *bmain, VFont *vf)
{
	if (vf && vf->packedfile) {
		return BLF_load_mem_unique(vf->name, (const unsigned char *)vf->packedfile->data, vf->packedfile->size);
	}
	if (vf && !BKE_vfont_is_builtin(vf)) {
		char path[FILE_MAX];
		BLI_strncpy(path, vf->name, sizeof(path));
		BLI_path_abs(path, vf->id.lib ? vf->id.lib->filepath : bmain->name);
		int id = BLF_load_unique(path);
		if (id != -1) {
			return id;
		}
	}
	int size;
	const void *mem = BKE_vfont_builtin_data(&size);
	return mem ? BLF_load_mem_unique("atlas_builtin", mem, size) : -1;
}

/* Render the text's font into a new white RGBA atlas image (fixed grid cells) and fill the glyph table. */
static Image *rna_Curve_atlas_bake_font(Curve *cu, Main *bmain, ReportList *reports, int size, int padding, const char *chars)
{
	int codes[1024], count = 0;
	const size_t chars_len = strlen(chars);
	for (size_t index = 0; index < chars_len && count < 1024;) {
		unsigned int c = BLI_str_utf8_as_unicode_step(chars, &index);
		bool seen = false;
		for (int i = 0; i < count; i++) {
			seen |= (codes[i] == (int)c);
		}
		if (!seen && c >= 32 && c < 0x110000) {
			codes[count++] = (int)c;
		}
	}
	if (count == 0) {
		BKE_report(reports, RPT_ERROR, "No characters to bake");
		return NULL;
	}
	int font = atlas_font_load(bmain, cu->vfont);
	if (font == -1) {
		BKE_report(reports, RPT_ERROR, "Could not load the text font");
		return NULL;
	}
	/* letters the text font lacks (Japanese kana, Cyrillic...) come from the bundled international font */
	int fallback = -1;
	int fonts[1024], kept = 0, missing = 0;
	for (int i = 0; i < count; i++) {
		int fid = font;
		if (codes[i] != ' ' && !BLF_has_glyph(font, (unsigned int)codes[i])) {
			if (fallback == -1) {
				int uni_size;
				unsigned char *uni = BLF_get_unifont(&uni_size);
				fallback = uni ? BLF_load_mem_unique("atlas_unifont", uni, uni_size) : -2;
			}
			fid = (fallback >= 0 && BLF_has_glyph(fallback, (unsigned int)codes[i])) ? fallback : -1;
		}
		if (fid == -1) {
			missing++;
			continue;
		}
		codes[kept] = codes[i];
		fonts[kept++] = fid;
	}
	count = kept;
	if (count == 0) {
		BLF_unload_id(font);
		if (fallback >= 0) {
			BLF_unload_id(fallback);
		}
		BKE_report(reports, RPT_ERROR, "None of the characters are in the font");
		return NULL;
	}
	if (missing) {
		BKE_reportf(reports, RPT_WARNING, "%d characters are not in the font and were skipped", missing);
	}
	BLF_size(font, size, 72);
	if (fallback >= 0) {
		BLF_size(fallback, size, 72);
	}
	/* real ink box of all glyphs: some reach below the descender or above the ascender */
	const float line_height = BLF_ascender(font) - BLF_descender(font);
	float top = BLF_ascender(font), bottom = -BLF_descender(font), left = 0.0f, right = (float)size;
	for (int i = 0; i < count; i++) {
		char utf8[8];
		size_t len = BLI_str_utf8_from_unicode((unsigned int)codes[i], utf8);
		rctf box;
		BLF_boundbox(fonts[i], utf8, len, &box);
		if (box.xmax > box.xmin) {
			top = max_ff(top, box.ymax);
			bottom = max_ff(bottom, -box.ymin);
			left = min_ff(left, box.xmin);
			right = max_ff(right, box.xmax);
		}
	}
	padding += (int)ceilf(-left);  /* the pen sits at cell x + padding */
	const int ascent = (int)ceilf(top) + 1;
	const int descent = (int)ceilf(bottom) + 1;
	const int cell = max_ii(ascent + descent, (int)ceilf(right) + 1) + padding * 2;
	const int cols = max_ii(1, (int)ceilf(sqrtf((float)count)));
	const int rows = (count + cols - 1) / cols;
	const int w = cols * cell, h = rows * cell;  /* no power of two: less to paint and process */

	const float white[4] = {1.0f, 1.0f, 1.0f, 0.0f};
	Image *ima = BKE_image_add_generated(bmain, w, h, "TextAtlas", 32, false, IMA_GENTYPE_BLANK, white, false);
	ImBuf *ibuf = BKE_image_acquire_ibuf(ima, NULL, NULL);
	if (!ibuf || !ibuf->rect) {
		BKE_image_release_ibuf(ima, ibuf, NULL);
		BLF_unload_id(font);
		if (fallback >= 0) {
			BLF_unload_id(fallback);
		}
		BKE_report(reports, RPT_ERROR, "Could not create the atlas image");
		return NULL;
	}
	unsigned int *px = ibuf->rect;
	for (int i = 0; i < w * h; i++) {
		px[i] = 0x00FFFFFF;  /* white, alpha 0: edges blend toward white, not black */
	}

	const float col[4] = {1.0f, 1.0f, 1.0f, 1.0f};
	BLF_buffer(font, NULL, (unsigned char *)ibuf->rect, w, h, 4, NULL);
	BLF_buffer_col(font, col);
	if (fallback >= 0) {
		BLF_buffer(fallback, NULL, (unsigned char *)ibuf->rect, w, h, 4, NULL);
		BLF_buffer_col(fallback, col);
	}

	MEM_SAFE_FREE(cu->atlas_glyphs);
	cu->atlas_glyphs = MEM_calloc_arrayN(count, sizeof(TextAtlasGlyph), "atlas_glyphs");
	cu->atlas_count = count;
	for (int i = 0; i < count; i++) {
		char utf8[8];
		size_t len = BLI_str_utf8_from_unicode((unsigned int)codes[i], utf8);
		utf8[len] = '\0';
		const int x = (i % cols) * cell;
		const int y_bottom = h - (i / cols + 1) * cell;  /* ImBuf rows start at the bottom */
		BLF_position(fonts[i], (float)(x + padding), (float)(y_bottom + cell - padding - ascent), 0.0f);
		BLF_draw_buffer(fonts[i], utf8, len);
		TextAtlasGlyph *g = &cu->atlas_glyphs[i];
		g->code = codes[i];
		g->u0 = (float)x / w;
		g->u1 = (float)(x + cell) / w;
		g->v0 = (float)y_bottom / h;
		g->v1 = (float)(y_bottom + cell) / h;
		g->advance = BLF_width(fonts[i], utf8, len);
	}
	BLF_buffer(font, NULL, NULL, 0, 0, 0, NULL);
	BLF_unload_id(font);
	if (fallback >= 0) {
		BLF_buffer(fallback, NULL, NULL, 0, 0, 0, NULL);
		BLF_unload_id(fallback);
	}

	ibuf->userflags |= IB_BITMAPDIRTY;
	BKE_image_release_ibuf(ima, ibuf, NULL);

	if (cu->atlas_image) {
		id_us_min(&cu->atlas_image->id);
	}
	cu->atlas_image = ima;  /* takes the user created by BKE_image_add_generated */
	cu->atlas_size = (float)size;
	cu->atlas_pad = padding;
	cu->atlas_cell = (float)cell;
	cu->atlas_baseline = (float)(padding + ascent);
	cu->atlas_line_height = line_height;
	cu->flag |= CU_BITMAP_ATLAS;
	DAG_id_tag_update(&cu->id, 0);
	return ima;
}

static float rna_Nurb_calc_length(Nurb *nu, int resolution_u)
{
	return BKE_nurb_calc_length(nu, resolution_u);
}

#else

void RNA_api_curve(StructRNA *srna)
{
	FunctionRNA *func;
	PropertyRNA *parm;

	func = RNA_def_function(srna, "transform", "rna_Curve_transform");
	RNA_def_function_ui_description(func, "Transform curve by a matrix");
	parm = RNA_def_float_matrix(func, "matrix", 4, 4, NULL, 0.0f, 0.0f, "", "Matrix", 0.0f, 0.0f);
	RNA_def_parameter_flags(parm, 0, PARM_REQUIRED);
	RNA_def_boolean(func, "shape_keys", 0, "", "Transform Shape Keys");

	func = RNA_def_function(srna, "validate_material_indices", "BKE_curve_material_index_validate");
	RNA_def_function_ui_description(func, "Validate material indices of splines or letters, return True when the curve "
	                                "has had invalid indices corrected (to default 0)");
	parm = RNA_def_boolean(func, "result", 0, "Result", "");
	RNA_def_function_return(func, parm);

	func = RNA_def_function(srna, "atlas_glyphs_resize", "rna_Curve_atlas_glyphs_resize");
	RNA_def_function_ui_description(func, "Clear the bitmap atlas glyph table and allocate count empty glyphs");
	parm = RNA_def_int(func, "count", 0, 0, 0x10000, "Count", "", 0, 0x10000);
	RNA_def_parameter_flags(parm, 0, PARM_REQUIRED);

	func = RNA_def_function(srna, "atlas_bake_font", "rna_Curve_atlas_bake_font");
	RNA_def_function_ui_description(func, "Render this text's font into a new white bitmap atlas image and glyph table");
	RNA_def_function_flag(func, FUNC_USE_MAIN | FUNC_USE_REPORTS);
	parm = RNA_def_int(func, "size", 64, 8, 512, "Size", "Glyph size in pixels", 8, 512);
	RNA_def_parameter_flags(parm, 0, PARM_REQUIRED);
	RNA_def_int(func, "padding", 8, 0, 64, "Padding", "Free pixels around each glyph (room for outlines)", 0, 64);
	parm = RNA_def_string(func, "chars", NULL, 0, "Characters", "Characters to bake");
	RNA_def_parameter_flags(parm, 0, PARM_REQUIRED);
	parm = RNA_def_pointer(func, "image", "Image", "", "The new atlas image");
	RNA_def_function_return(func, parm);
}

void RNA_api_curve_nurb(StructRNA *srna)
{
	FunctionRNA *func;
	PropertyRNA *parm;

	func = RNA_def_function(srna, "calc_length", "rna_Nurb_calc_length");
	RNA_def_function_ui_description(func, "Calculate spline length");
	RNA_def_int(
	        func, "resolution", 0, 0, 1024, "Resolution",
	        "Spline resolution to be used, 0 defaults to the resolution_u", 0, 64);
	parm = RNA_def_float_distance(
	        func, "length", 0.0f, 0.0f, FLT_MAX, "Length",
	        "Length of the polygonaly approximated spline", 0.0f, FLT_MAX);
	RNA_def_function_return(func, parm);
}

#endif
