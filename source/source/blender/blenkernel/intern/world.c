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
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 */

/** \file blender/blenkernel/intern/world.c
 *  \ingroup bke
 */


#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "MEM_guardedalloc.h"

#include "DNA_world_types.h"
#include "DNA_property_types.h"
#include "DNA_scene_types.h"
#include "DNA_texture_types.h"

#include "BLI_utildefines.h"
#include "BLI_listbase.h"
#include "BLI_string.h"

#include "BKE_animsys.h"
#include "BKE_icons.h"
#include "BKE_library.h"
#include "BKE_library_query.h"
#include "BKE_library_remap.h"
#include "BKE_main.h"
#include "BKE_node.h"
#include "BKE_property.h"
#include "BKE_world.h"

#include "GPU_material.h"

/** Free (or release) any data used by this world (does not free the world itself). */
void BKE_world_free(World *wrld)
{
	int a;

	BKE_animdata_free((ID *)wrld, false);

	for (a = 0; a < MAX_MTEX; a++) {
		MEM_SAFE_FREE(wrld->mtex[a]);
	}

	/* is no lib link block, but world extension */
	if (wrld->nodetree) {
		ntreeFreeTree(wrld->nodetree);
		MEM_freeN(wrld->nodetree);
		wrld->nodetree = NULL;
	}

	GPU_material_free(&wrld->gpumaterial);

	BKE_bproperty_free_list(&wrld->prop);

	BKE_icon_id_delete((struct ID *)wrld);
	BKE_previewimg_free(&wrld->preview);
}

/**
 * World Status: default World Properties, mirroring existing weather/mist state plus placeholders
 * for status not backed by a real effect yet. Only adds the ones missing by name, so it is safe to
 * call on a World that came from the embedded startup.blend (which never goes through BKE_world_init).
 */
void BKE_world_status_props_ensure(World *wrld)
{
	struct { const char *name; int type; float fval; int ival; } wo_status[] = {
		{"rain_enabled",         GPROP_BOOL,  0.0f, 0},
		{"rain_intensity",       GPROP_FLOAT, wrld->rain_intensity, 0},
		{"clouds_enabled",       GPROP_BOOL,  0.0f, 0},
		{"mist_enabled",         GPROP_BOOL,  0.0f, 0},
		{"mist_density",         GPROP_FLOAT, wrld->mistdensity, 0},
		{"sun_hour",             GPROP_FLOAT, 12.0f, 0},
		{"cloud_type",           GPROP_INT,   0.0f, 0},
		{"player_under_cover",   GPROP_BOOL, 0.0f, 0},
	};
	/* Earlier Portuguese names, still stored in the embedded startup.blend. */
	const char *wo_status_legacy[][2] = {
		{"chuva_ligada",        "rain_enabled"},
		{"chuva_densidade",     "rain_intensity"},
		{"nuvens_ligadas",      "clouds_enabled"},
		{"neblina_ligada",      "mist_enabled"},
		{"neblina_densidade",   "mist_density"},
		{"horario_sol",         "sun_hour"},
		{"tipo_nuvem",          "cloud_type"},
		{"player_area_coberta", "player_under_cover"},
	};
	int i;

	/* Rename a legacy property (keeping its value), or drop it when the new name already exists. */
	for (i = 0; i < ARRAY_SIZE(wo_status_legacy); i++) {
		bProperty *legacy = BLI_findstring(&wrld->prop, wo_status_legacy[i][0], offsetof(bProperty, name));
		if (!legacy) {
			continue;
		}

		if (BLI_findstring(&wrld->prop, wo_status_legacy[i][1], offsetof(bProperty, name))) {
			BLI_remlink(&wrld->prop, legacy);
			BKE_bproperty_free(legacy);
		}
		else {
			BLI_strncpy(legacy->name, wo_status_legacy[i][1], sizeof(legacy->name));
		}
	}

	for (i = 0; i < ARRAY_SIZE(wo_status); i++) {
		bProperty *prop;

		if (BLI_findstring(&wrld->prop, wo_status[i].name, offsetof(bProperty, name))) {
			continue;
		}

		prop = BKE_bproperty_new(wo_status[i].type);
		BLI_strncpy(prop->name, wo_status[i].name, sizeof(prop->name));

		if (wo_status[i].type == GPROP_FLOAT) {
			*((float *)prop->poin) = wo_status[i].fval;
		}
		else {
			*((int *)prop->poin) = wo_status[i].ival;
		}

		BLI_addtail(&wrld->prop, prop);
	}
}

void BKE_world_init(World *wrld)
{
	BLI_assert(MEMCMP_STRUCT_OFS_IS_ZERO(wrld, id));

	wrld->horr = 0.05f;
	wrld->horg = 0.05f;
	wrld->horb = 0.05f;
	wrld->zenr = 0.01f;
	wrld->zeng = 0.01f;
	wrld->zenb = 0.01f;
	wrld->nadr = 0.01f;
	wrld->nadg = 0.01f;
	wrld->nadb = 0.01f;
	wrld->skytype = 0;

	wrld->exp = 0.0f;
	wrld->exposure = wrld->range = 1.0f;

	wrld->sun_size = 0.2f;
	wrld->turbidity = 0.2f;
	wrld->ground = 1.0f;
	wrld->moon_enabled = 0.0f;
	wrld->moon_size = 0.01f;
	wrld->moon_brightness = 0.25f;

	wrld->aodist = 10.0f;
	wrld->aosamp = 5;
	wrld->aoenergy = 1.0f;
	wrld->ao_env_energy = 1.0f;
	wrld->ao_indirect_energy = 1.0f;
	wrld->ao_indirect_bounces = 1;
	wrld->aobias = 0.05f;
	wrld->ao_samp_method = WO_AOSAMP_HAMMERSLEY;
	wrld->ao_approx_error = 0.25f;

	wrld->preview = NULL;
	wrld->miststa = 5.0f;
	wrld->mistdist = 25.0f;
	wrld->mistheight = 5.0f;
	wrld->mistdensity = 1.0f;

	/* weather (rain/clouds/lens flare) */
	wrld->weather_flag |= (WO_WEATHER_RAIN_DROPLETS | WO_WEATHER_RAIN_RIPPLE);
	wrld->rain_intensity = 0.5f;
	wrld->rain_density = 1.0f;
	wrld->rain_speed = 1.0f;
	wrld->rain_wind = 0.1f;
	wrld->rain_darken = 0.3f;
	wrld->rain_ripple = 0.4f;
	wrld->rain_ripple_distance = 20.0f;
	wrld->rain_ripple_min_up = 0.5f;
	wrld->rain_color[0] = 0.8f;
	wrld->rain_color[1] = 0.8f;
	wrld->rain_color[2] = 0.8f;

	wrld->cloud_coverage = 0.5f;
	wrld->cloud_scale = 1.0f;
	wrld->cloud_speed = 0.3f;
	wrld->cloud_color[0] = 1.0f;
	wrld->cloud_color[1] = 1.0f;
	wrld->cloud_color[2] = 1.0f;

	wrld->flare_scale = 1.0f;
	wrld->flare_intensity = 1.0f;

	wrld->earthquake_level = 0;
	wrld->earthquake_mode = WO_EARTHQUAKE_HORIZONTAL;
	wrld->earthquake_camera = 1.0f;
	wrld->earthquake_scale = 1.0f;

	BKE_world_status_props_ensure(wrld);
}

World *BKE_world_add(Main *bmain, const char *name)
{
	World *wrld;

	wrld = BKE_libblock_alloc(bmain, ID_WO, name, 0);

	BKE_world_init(wrld);

	return wrld;
}

/**
 * Only copy internal data of World ID from source to already allocated/initialized destination.
 * You probably nerver want to use that directly, use id_copy or BKE_id_copy_ex for typical needs.
 *
 * WARNING! This function will not handle ID user count!
 *
 * \param flag: Copying options (see BKE_library.h's LIB_ID_COPY_... flags for more).
 */
void BKE_world_copy_data(Main *bmain, World *wrld_dst, const World *wrld_src, const int flag)
{
	for (int a = 0; a < MAX_MTEX; a++) {
		if (wrld_src->mtex[a]) {
			wrld_dst->mtex[a] = MEM_dupallocN(wrld_src->mtex[a]);
		}
	}

	if (wrld_src->nodetree) {
		/* Note: nodetree is *not* in bmain, however this specific case is handled at lower level
		 *       (see BKE_libblock_copy_ex()). */
		BKE_id_copy_ex(bmain, (ID *)wrld_src->nodetree, (ID **)&wrld_dst->nodetree, flag, false);
	}

	BLI_listbase_clear(&wrld_dst->gpumaterial);

	BLI_listbase_clear(&wrld_dst->prop);
	BKE_bproperty_copy_list(&wrld_dst->prop, &wrld_src->prop);

	if ((flag & LIB_ID_COPY_NO_PREVIEW) == 0) {
		BKE_previewimg_id_copy(&wrld_dst->id, &wrld_src->id);
	}
	else {
		wrld_dst->preview = NULL;
	}
}

World *BKE_world_copy(Main *bmain, const World *wrld)
{
	World *wrld_copy;
	BKE_id_copy_ex(bmain, &wrld->id, (ID **)&wrld_copy, 0, false);
	return wrld_copy;
}

World *BKE_world_localize(World *wrld)
{
	/* TODO(bastien): Replace with something like:
	 *
	 *   World *wrld_copy;
	 *   BKE_id_copy_ex(bmain, &wrld->id, (ID **)&wrld_copy,
	 *                  LIB_ID_COPY_NO_MAIN | LIB_ID_COPY_NO_PREVIEW | LIB_ID_COPY_NO_USER_REFCOUNT,
	 *                  false);
	 *   return wrld_copy;
	 *
	 * NOTE: Only possible once nested node trees are fully converted to that too. */

	World *wrldn;
	int a;

	wrldn = BKE_libblock_copy_nolib(&wrld->id, false);

	for (a = 0; a < MAX_MTEX; a++) {
		if (wrld->mtex[a]) {
			wrldn->mtex[a] = MEM_mallocN(sizeof(MTex), __func__);
			memcpy(wrldn->mtex[a], wrld->mtex[a], sizeof(MTex));
		}
	}

	if (wrld->nodetree)
		wrldn->nodetree = ntreeLocalize(wrld->nodetree);

	wrldn->preview = NULL;

	BLI_listbase_clear(&wrldn->gpumaterial);

	BLI_listbase_clear(&wrldn->prop);
	BKE_bproperty_copy_list(&wrldn->prop, &wrld->prop);

	return wrldn;
}

void BKE_world_make_local(Main *bmain, World *wrld, const bool lib_local)
{
	BKE_id_make_local_generic(bmain, &wrld->id, true, lib_local);
}
