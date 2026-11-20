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
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file blender/editors/space_view3d/view3d_draw_probes.c
 *  \ingroup spview3d
 *
 * Preview of Probe Volume GI (KX_ProbeVolume, docs/plano-previa-viewport.md Fase 4): the saved light
 * of the grids (<scene>.probes next to the .range, written by the game or Bake Probes) is read the way
 * KX_TextureRendererManager::ReadBakedLight does, and its SH9 atlas is bound per object by the
 * material draw (GPU_viewport_probe_volumes_set). A grid without saved light, or saved from another
 * box, is captured live by the game; the viewport shows nothing for it.
 */

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "MEM_guardedalloc.h"

#include "DNA_object_types.h"
#include "DNA_property_types.h"
#include "DNA_scene_types.h"
#include "DNA_screen_types.h"
#include "DNA_view3d_types.h"

#include "BLI_fileops.h"
#include "BLI_listbase.h"
#include "BLI_math.h"
#include "BLI_path_util.h"
#include "BLI_string.h"
#include "BLI_utildefines.h"

#include "BKE_global.h"
#include "BKE_idprop.h"
#include "BKE_main.h"
#include "BKE_property.h"
#include "BKE_scene.h"

#include "GPU_draw.h"
#include "GPU_texture.h"

#include "view3d_intern.h"  /* own include */

#define PROBES_MAX_VOLUMES 32

typedef struct ProbesVolume {
	char name[64];
	int dims[3];
	float min[3], max[3];
	GPUTexture *atlas;
} ProbesVolume;

static struct {
	char path[FILE_MAX];
	double mtime;
	size_t size;
	ProbesVolume volumes[PROBES_MAX_VOLUMES];
	int count;
	GPUViewportProbeVolume bound[PROBES_MAX_VOLUMES];
} probes_cache = {{0}};

static void probes_cache_clear(void)
{
	for (int i = 0; i < probes_cache.count; i++) {
		if (probes_cache.volumes[i].atlas) {
			GPU_texture_free(probes_cache.volumes[i].atlas);
		}
	}
	probes_cache.count = 0;
}

void view3d_probe_volumes_free(void)
{
	GPU_viewport_probe_volumes_set(NULL, 0);
	probes_cache_clear();
	probes_cache.path[0] = '\0';
}

/* Same layout as KX_ProbeVolume::WriteBaked (BakedProbe). */
typedef struct BakedProbe {
	float position[3];
	float sh[9][3];
	int valid;
	int disabled;
} BakedProbe;

static bool probes_read_volume(FILE *file, ProbesVolume *vol)
{
	float box[6];
	int count;
	if (fread(vol->dims, sizeof(int), 3, file) != 3 || fread(box, sizeof(float), 6, file) != 6 ||
	    fread(&count, sizeof(int), 1, file) != 1 || count < 0 || count > (1 << 20))
	{
		return false;
	}
	copy_v3_v3(vol->min, box);
	copy_v3_v3(vol->max, box + 3);
	const int dx = vol->dims[0], dy = vol->dims[1], dz = vol->dims[2];
	if (dx < 2 || dy < 2 || dz < 2 || dx > 1024 || dy > 1024 || dz > 1024 ||
	    (long long)dx * dy * dz != (long long)count)
	{
		return fseek(file, (long)count * (long)sizeof(BakedProbe), SEEK_CUR) == 0;
	}
	BakedProbe *baked = MEM_mallocN(sizeof(BakedProbe) * (size_t)count, __func__);
	if (fread(baked, sizeof(BakedProbe), (size_t)count, file) != (size_t)count) {
		MEM_freeN(baked);
		return false;
	}
	/* KX_ProbeVolume::UpdateAtlas: 9 slabs along z, one per SH9 coefficient; alpha = probe read. */
	float *data = MEM_callocN(sizeof(float) * 4 * (size_t)count * 9, __func__);
	for (int i = 0; i < count; i++) {
		const float read = baked[i].valid ? 1.0f : 0.0f;
		const int x = i % dx, y = (i / dx) % dy, z = i / (dx * dy);
		for (int k = 0; k < 9; k++) {
			float *texel = &data[((((size_t)k * dz + z) * dy + y) * dx + x) * 4];
			mul_v3_v3fl(texel, baked[i].sh[k], read);
			texel[3] = read;
		}
	}
	vol->atlas = GPU_texture_create_3D_half(dx, dy, dz * 9);
	if (vol->atlas) {
		GPU_texture_update_3D_float(vol->atlas, data);
	}
	MEM_freeN(data);
	MEM_freeN(baked);
	return true;
}

/* Reads the file again when it changed (a new bake); false = no saved light. */
static bool probes_cache_update(const char *path)
{
	BLI_stat_t st;
	if (BLI_stat(path, &st) != 0) {
		probes_cache_clear();
		probes_cache.path[0] = '\0';
		return false;
	}
	if (STREQ(path, probes_cache.path) && probes_cache.mtime == (double)st.st_mtime &&
	    probes_cache.size == (size_t)st.st_size)
	{
		return probes_cache.count > 0;
	}
	probes_cache_clear();
	BLI_strncpy(probes_cache.path, path, sizeof(probes_cache.path));
	probes_cache.mtime = (double)st.st_mtime;
	probes_cache.size = (size_t)st.st_size;

	FILE *file = BLI_fopen(path, "rb");
	if (!file) {
		return false;
	}
	char magic[4];
	bool ok = fread(magic, 1, 4, file) == 4 && memcmp(magic, "RPV1", 4) == 0;
	while (ok && probes_cache.count < PROBES_MAX_VOLUMES) {
		int length;
		if (fread(&length, sizeof(int), 1, file) != 1) {
			break;
		}
		ok = length > 0 && length < 1024;
		char name[1024];
		ok = ok && fread(name, 1, (size_t)length, file) == (size_t)length;
		if (!ok) {
			break;
		}
		name[length] = '\0';
		ProbesVolume *vol = &probes_cache.volumes[probes_cache.count];
		memset(vol, 0, sizeof(*vol));
		BLI_strncpy(vol->name, name, sizeof(vol->name));
		ok = probes_read_volume(file, vol);
		if (ok && vol->atlas) {
			probes_cache.count++;
		}
	}
	fclose(file);
	return probes_cache.count > 0;
}

static float probes_prop_number(Object *ob, const char *name, float fallback, bool *r_found)
{
	bProperty *prop = BKE_bproperty_object_get(ob, name);
	if (r_found) {
		*r_found = prop != NULL;
	}
	if (!prop) {
		return fallback;
	}
	switch (prop->type) {
		case GPROP_BOOL:
		case GPROP_INT:
			return (float)prop->data;
		case GPROP_FLOAT:
			return *(float *)&prop->data;
		default:
			return fallback;
	}
}

/* Quality of the grid as BL_BlenderDataConversion picks it; -1 = off (preset Very Low). */
static int probes_quality(Scene *scene, Object *ob)
{
	int preset = 2;
	bool has_preset = false;
	IDProperty *idp = scene->id.properties ? IDP_GetPropertyFromGroup(scene->id.properties, "ae_probe_volume_quality") : NULL;
	if (idp && idp->type == IDP_INT) {
		preset = min_ii(IDP_Int(idp), 2);
		has_preset = true;
	}
	if (preset < 0) {
		return -1;
	}
	int quality = has_preset ? preset : 1;
	bProperty *prop = BKE_bproperty_object_get(ob, "probe_volume_quality");
	if (prop) {
		if (prop->type == GPROP_STRING) {
			const char *text = prop->poin ? (const char *)prop->poin : "";
			if (STREQ(text, "Low") || STREQ(text, "low")) {
				quality = 0;
			}
			else if (STREQ(text, "High") || STREQ(text, "high")) {
				quality = 2;
			}
			else if (STREQ(text, "Medium") || STREQ(text, "medium") || STREQ(text, "Med")) {
				quality = 1;
			}
			else {
				quality = atoi(text);
			}
		}
		else {
			quality = (int)probes_prop_number(ob, "probe_volume_quality", 1.0f, NULL);
		}
	}
	return max_ii(min_ii(quality, preset), 0);
}

/* KX_ProbeVolume's constructor: box from the Empty (drawn as Cube) and the spacing the grid ends up
 * with under the quality's probe limit. False when the volume is off. */
static bool probes_volume_shape(Scene *scene, Object *ob, float r_min[3], float r_max[3], int r_dims[3],
                                float *r_spacing)
{
	static const int max_probes[3] = {64, 128, 256};
	bool found;
	float spacing = probes_prop_number(ob, "probe_volume", 0.0f, &found);
	const int quality = found ? probes_quality(scene, ob) : -1;
	if (quality < 0) {
		return false;
	}
	if (spacing <= 0.0f) {
		spacing = 4.0f;
	}
	spacing = max_ff(spacing, 0.25f);
	float scale[3], half[3];
	mat4_to_size(scale, ob->obmat);
	for (int i = 0; i < 3; i++) {
		half[i] = max_ff(fabsf(scale[i]) * ob->empty_drawsize, 0.01f);
	}
	for (;;) {
		int total = 1;
		for (int i = 0; i < 3; i++) {
			r_dims[i] = max_ii(2, (int)ceilf(2.0f * half[i] / spacing) + 1);
			total *= r_dims[i];
		}
		if (total <= max_probes[quality]) {
			break;
		}
		spacing *= 1.1f;
	}
	sub_v3_v3v3(r_min, ob->obmat[3], half);
	add_v3_v3v3(r_max, ob->obmat[3], half);
	*r_spacing = spacing;
	return true;
}

void view3d_probe_volumes_update(Main *bmain, Scene *scene)
{
	int bound = 0;
	if (BKE_scene_use_new_shading_nodes(scene) && bmain->name[0]) {
		bool any = false;
		Scene *sce_iter;
		Base *base;
		for (SETLOOPER(scene, sce_iter, base)) {
			if (base->object->type == OB_EMPTY && BKE_bproperty_object_get(base->object, "probe_volume")) {
				any = true;
				break;
			}
		}
		char dir[FILE_MAX], path[FILE_MAX];
		BLI_split_dir_part(bmain->name, dir, sizeof(dir));
		BLI_snprintf(path, sizeof(path), "%s%s.probes", dir, scene->id.name + 2);
		if (any && probes_cache_update(path)) {
			for (SETLOOPER(scene, sce_iter, base)) {
				Object *ob = base->object;
				float min[3], max[3], spacing;
				int dims[3];
				if (ob->type != OB_EMPTY || !probes_volume_shape(scene, ob, min, max, dims, &spacing)) {
					continue;
				}
				for (int i = 0; i < probes_cache.count && bound < PROBES_MAX_VOLUMES; i++) {
					ProbesVolume *vol = &probes_cache.volumes[i];
					/* KX_ProbeVolume::ReadBaked: light saved from another box is captured again. */
					if (!STREQ(vol->name, ob->id.name + 2) || dims[0] != vol->dims[0] || dims[1] != vol->dims[1] ||
					    dims[2] != vol->dims[2] || !compare_v3v3(min, vol->min, 1e-3f) ||
					    !compare_v3v3(max, vol->max, 1e-3f))
					{
						continue;
					}
					GPUViewportProbeVolume *gv = &probes_cache.bound[bound++];
					gv->atlas = vol->atlas;
					copy_v3_v3(gv->min, vol->min);
					copy_v3_v3(gv->max, vol->max);
					copy_v3_v3_int(gv->dims, vol->dims);
					gv->spacing = spacing;
					break;
				}
			}
		}
	}
	GPU_viewport_probe_volumes_set(bound ? probes_cache.bound : NULL, bound);
}
