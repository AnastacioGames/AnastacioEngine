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
 * The Original Code is Copyright (C) 2006 Blender Foundation.
 * All rights reserved.
 */

/** ile blender/gpu/intern/gpu_material_ies.c
 *  \ingroup gpu
 *
 * IES light profiles (moved from gpu_material.c).
 */

#include <math.h>
#include <string.h>

#include "MEM_guardedalloc.h"

#include "DNA_lamp_types.h"
#include "DNA_node_types.h"
#include "DNA_material_types.h"
#include "DNA_object_types.h"
#include "DNA_scene_types.h"
#include "DNA_world_types.h"
#include "DNA_group_types.h"

#include "BLI_math.h"
#include "BLI_blenlib.h"
#include "BLI_utildefines.h"
#include "BLI_hash.h"

#include "BKE_anim.h"
#include "BKE_colorband.h"
#include "BKE_colortools.h"
#include "BKE_global.h"
#include "BKE_idprop.h"
#include "BKE_image.h"
#include "BKE_main.h"
#include "BKE_node.h"
#include "BKE_scene.h"
#include "BKE_group.h"
#include "BKE_text.h"

#include "IMB_imbuf_types.h"

#include "GPU_extensions.h"
#include "GPU_draw.h"
#include "GPU_framebuffer.h"
#include "GPU_material.h"
#include "GPU_shader.h"
#include "GPU_render_profile.h"
#include "GPU_texture.h"

#include "gpu_codegen.h"

#ifdef WITH_OPENSUBDIV
#  include "BKE_DerivedMesh.h"
#endif


#include "gpu_material_intern.h"

/* ---- IES light profiles ----
 * IES Texture node in a lamp node tree (Game PBR). Parsing follows Cycles (intern/cycles/util/util_ies.cpp),
 * photometric type C only. Each profile is resampled to IES_GRID_H x IES_GRID_V (horizontal 0-360, vertical
 * 0-180 degrees, the angle convention of Cycles), normalized to a peak of 1 and stored as one band of a shared
 * atlas, read by scene_light_ies() in gpu_shader_material.glsl. */
#define IES_GRID_H 64
#define IES_GRID_V 32 /* keep in sync with IES_BAND in gpu_shader_material.glsl */
#define IES_MAX_PROFILES 16 /* keep in sync with IES_PROFILES in gpu_shader_material.glsl */

static struct {
	unsigned int hash[IES_MAX_PROFILES];
	int count;
	float pixels[IES_MAX_PROFILES * IES_GRID_V * IES_GRID_H * 2];
	GPUTexture *tex;
	bool dirty;
} GIES;

static bool ies_eof(char **data)
{
	return *data == NULL || (*data)[0] == '\0';
}

static double ies_double(char **data)
{
	if (ies_eof(data)) {
		return 0.0;
	}
	char *old = *data;
	double val = strtod(*data, data);
	if (*data == old) {
		*data = NULL;
		return 0.0;
	}
	return val;
}

/* Lookup in an ascending angle table: index i and fraction f between i and i + 1. */
static bool ies_find(const float *angles, int num, float a, int *r_i, float *r_f)
{
	if (num == 1) {
		*r_i = 0;
		*r_f = 0.0f;
		return a == angles[0];
	}
	if (a < angles[0] || a > angles[num - 1]) {
		return false;
	}
	int i = 0;
	while (i < num - 2 && angles[i + 1] < a) {
		i++;
	}
	float d = angles[i + 1] - angles[i];
	*r_i = i;
	*r_f = (d > 0.0f) ? (a - angles[i]) / d : 0.0f;
	return true;
}

/* Intensity at horizontal angle h and vertical angle v (degrees), unfolding the symmetries of the file
 * like IESFile::process_type_c() in Cycles. intensity is [h][v]. */
static float ies_sample(const float *h_angles, int h_num, const float *v_angles, int v_num, const float *intensity,
                        bool v_flip, float h, float v)
{
	float h_last = h_angles[h_num - 1];
	if (h_num == 1) {
		h = h_angles[0];
	}
	else if (h_last <= 90.0f) {
		if (h > 180.0f) h = 360.0f - h;
		if (h > 90.0f) h = 180.0f - h;
	}
	else if (h_last <= 180.0f) {
		if (h > 180.0f) h = 360.0f - h;
	}
	if (v_flip) {
		v = 180.0f - v;
	}

	int vi;
	float vf;
	if (!ies_find(v_angles, v_num, v, &vi, &vf)) {
		return 0.0f;
	}
	int vi2 = MIN2(vi + 1, v_num - 1);

	int hi, hi2;
	float hf;
	if (h > h_last) {
		/* full circle without the 360 entry: wrap to the 0 entry */
		hi = h_num - 1;
		hi2 = 0;
		hf = (h - h_last) / max_ff(360.0f - h_last, 1e-6f);
	}
	else if (ies_find(h_angles, h_num, h, &hi, &hf)) {
		hi2 = MIN2(hi + 1, h_num - 1);
	}
	else {
		return 0.0f;
	}

#define IES_AT(_h, _v) intensity[(_h) * v_num + (_v)]
	float a = IES_AT(hi, vi) + (IES_AT(hi, vi2) - IES_AT(hi, vi)) * vf;
	float b = IES_AT(hi2, vi) + (IES_AT(hi2, vi2) - IES_AT(hi2, vi)) * vf;
#undef IES_AT
	return a + (b - a) * hf;
}

/* Parses an IES file into a normalized IES_GRID_V x IES_GRID_H grid. text is modified. */
static bool ies_parse(char *text, float *r_grid)
{
	for (char *c = text; *c; c++) {
		if (*c == ',') {
			*c = ' ';
		}
	}
	char *data = strstr(text, "\nTILT=");
	if (ies_eof(&data)) {
		return false;
	}
	if (STREQLEN(data, "\nTILT=INCLUDE", 13)) {
		data += 13;
		ies_double(&data); /* lamp to luminaire geometry */
		long num_tilt = (long)ies_double(&data);
		if (num_tilt < 0 || num_tilt > 4096) {
			return false;
		}
		for (long i = 0; i < 2 * num_tilt; i++) {
			ies_double(&data);
		}
	}
	else {
		data = strstr(data + 1, "\n");
	}
	if (ies_eof(&data)) {
		return false;
	}
	data++;

	ies_double(&data); /* number of lamps */
	ies_double(&data); /* lumens per lamp */
	ies_double(&data); /* candela multiplier: irrelevant once normalized */
	long v_num = (long)ies_double(&data);
	long h_num = (long)ies_double(&data);
	long type = (long)ies_double(&data);
	if (v_num <= 0 || h_num <= 0 || v_num > 4096 || h_num > 4096 || v_num > (1024 * 1024) / h_num) {
		return false;
	}
	if (type != 1) {
		/* type C only (the usual one); Cycles also reads type B */
		return false;
	}
	for (int i = 0; i < 7; i++) {
		ies_double(&data); /* unit, width, length, height, ballast factor, photometric factor, input watts */
	}

	float *v_angles = MEM_mallocN(sizeof(float) * v_num, __func__);
	float *h_angles = MEM_mallocN(sizeof(float) * h_num, __func__);
	float *intensity = MEM_mallocN(sizeof(float) * v_num * h_num, __func__);
	for (int i = 0; i < v_num; i++) {
		v_angles[i] = (float)ies_double(&data);
	}
	for (int i = 0; i < h_num; i++) {
		h_angles[i] = (float)ies_double(&data);
	}
	for (int i = 0; i < v_num * h_num; i++) {
		intensity[i] = (float)ies_double(&data);
	}

	/* a number failed to parse (or the file ended early) */
	bool ok = (data != NULL);
	if (ok && h_angles[0] == 90.0f) {
		/* some files go from 90 to 270 */
		for (int i = 0; i < h_num; i++) {
			h_angles[i] -= 90.0f;
		}
	}
	ok = ok && h_angles[0] == 0.0f;
	bool v_flip = false;
	if (ok && v_angles[0] == 90.0f) {
		/* 90 to 180: an uplight */
		ok = (v_angles[v_num - 1] == 180.0f);
		v_flip = true;
	}
	else if (ok) {
		ok = (v_angles[0] == 0.0f);
	}

	float peak = 0.0f;
	if (ok) {
		for (int k = 0; k < IES_GRID_V; k++) {
			float v = (k + 0.5f) * (180.0f / IES_GRID_V);
			for (int j = 0; j < IES_GRID_H; j++) {
				float h = (j + 0.5f) * (360.0f / IES_GRID_H);
				float val = max_ff(ies_sample(h_angles, h_num, v_angles, v_num, intensity, v_flip, h, v), 0.0f);
				r_grid[k * IES_GRID_H + j] = val;
				peak = max_ff(peak, val);
			}
		}
	}

	MEM_freeN(v_angles);
	MEM_freeN(h_angles);
	MEM_freeN(intensity);

	if (!ok || peak <= 0.0f) {
		return false;
	}
	for (int i = 0; i < IES_GRID_V * IES_GRID_H; i++) {
		r_grid[i] /= peak;
	}
	return true;
}

/* Text of the first IES Texture node in the lamp node tree (MEM_mallocN), NULL when none. */
static char *ies_lamp_text(Lamp *la, float *r_strength)
{
	if (!la || !la->use_nodes || !la->nodetree) {
		return NULL;
	}
	for (bNode *node = la->nodetree->nodes.first; node; node = node->next) {
		if (node->type != SH_NODE_TEX_IES || (node->flag & NODE_MUTED) || !node->storage) {
			continue;
		}
		NodeShaderTexIES *ies = node->storage;
		bNodeSocket *sock = BLI_findlink(&node->inputs, 1);
		*r_strength = (sock && sock->default_value) ? ((bNodeSocketValueFloat *)sock->default_value)->value : 1.0f;

		if (ies->mode == NODE_IES_INTERNAL) {
			return node->id ? txt_to_buf((struct Text *)node->id) : NULL;
		}
		char path[FILE_MAX];
		size_t size;
		BLI_strncpy(path, ies->filepath, sizeof(path));
		BLI_path_abs(path, ID_BLEND_PATH_FROM_GLOBAL(&la->id));
		char *buf = BLI_file_read_text_as_mem(path, 1, &size);
		if (buf) {
			buf[size] = '\0';
		}
		else {
			printf("Warning: lamp \"%s\": IES file \"%s\" not found\n", la->id.name + 2, path);
		}
		return buf;
	}
	return NULL;
}

int GPU_lamp_ies_slot(GPULamp *lamp, float *r_strength)
{
	*r_strength = 1.0f;
	char *text = ies_lamp_text(lamp ? lamp->la : NULL, r_strength);
	if (!text) {
		return -1;
	}

	unsigned int hash = BLI_hash_string(text);
	for (int i = 0; i < GIES.count; i++) {
		if (GIES.hash[i] == hash) {
			MEM_freeN(text);
			return i;
		}
	}

	float *grid = MEM_mallocN(sizeof(float) * IES_GRID_V * IES_GRID_H, __func__);
	int slot = -1;
	if (ies_parse(text, grid)) {
		/* atlas full: reuse a band (rare: 16 different profiles across the game runs of one session) */
		slot = (GIES.count < IES_MAX_PROFILES) ? GIES.count++ : (int)(hash % IES_MAX_PROFILES);
		GIES.hash[slot] = hash;
		float *band = &GIES.pixels[slot * IES_GRID_V * IES_GRID_H * 2];
		for (int i = 0; i < IES_GRID_V * IES_GRID_H; i++) {
			band[i * 2] = band[i * 2 + 1] = grid[i];
		}
		GIES.dirty = true;
	}
	else {
		printf("Warning: lamp \"%s\": IES profile not readable in the game (photometric type C only)\n",
		       lamp->la->id.name + 2);
	}
	MEM_freeN(grid);
	MEM_freeN(text);
	return slot;
}

GPUTexture *gpu_ies_atlas(void)
{
	if (GIES.dirty) {
		if (GIES.tex) {
			GPU_texture_free(GIES.tex);
		}
		/* repeat: the horizontal angle wraps; the vertical one is clamped inside its band by the shader */
		GIES.tex = GPU_texture_create_2D_procedural(IES_GRID_H, IES_GRID_V * IES_MAX_PROFILES, GIES.pixels, true, true, NULL);
		GIES.dirty = false;
	}
	return GIES.tex;
}

void GPU_lamp_ies_exit(void)
{
	if (GIES.tex) {
		GPU_texture_free(GIES.tex);
	}
	memset(&GIES, 0, sizeof(GIES));
}
