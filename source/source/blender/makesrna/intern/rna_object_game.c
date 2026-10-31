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

/** \file blender/makesrna/intern/rna_object_game.c
 *  \ingroup RNA
 */

/* Engine systems of the Object (GPU particles, reverb area, lightning, network, destruction,
 * explosive, deform), split from rna_object.c. makesrna runs RNA_def_object_game right after
 * RNA_def_object, so these structs (and their generated code) live in rna_object_game_gen.c. */


#include <stdio.h>
#include <stdlib.h>

#include "DNA_action_types.h"
#include "DNA_customdata_types.h"
#include "DNA_controller_types.h"
#include "DNA_sensor_types.h"
#include "DNA_actuator_types.h"
#include "DNA_group_types.h"
#include "DNA_material_types.h"
#include "DNA_mesh_types.h"
#include "DNA_object_force_types.h"
#include "DNA_object_types.h"
#include "DNA_property_types.h"
#include "DNA_scene_types.h"
#include "DNA_meta_types.h"

#include "BLI_utildefines.h"
#include "BLI_listbase.h"
#include "BLI_string.h"
#include "BLI_string_utils.h"
#include "BLI_path_util.h"

//#include "BKE_action.h"
#include "BKE_camera.h"
#include "BKE_paint.h"
#include "BKE_editlattice.h"
#include "BKE_editmesh.h"
#include "BKE_group.h" /* needed for BKE_group_object_exists() */
#include "BKE_property.h"
#include "BKE_object_deform.h"

#include "RNA_access.h"
#include "RNA_define.h"
#include "RNA_enum_types.h"

#include "rna_internal.h"

#include "BLI_sys_types.h" /* needed for intptr_t used in ED_mesh.h */
#include "BLI_math_base.h"
#include "ED_mesh.h"

#include "WM_api.h"
#include "WM_types.h"

#ifdef RNA_RUNTIME

#include "BLI_math.h"

#include "DNA_key_types.h"
#include "DNA_constraint_types.h"
#include "DNA_lattice_types.h"
#include "DNA_node_types.h"

#include "BKE_armature.h"
#include "BKE_bullet.h"
#include "BKE_colortools.h"
#include "BKE_constraint.h"
#include "BKE_context.h"
#include "BKE_curve.h"
#include "BKE_depsgraph.h"
#include "BKE_effect.h"
#include "BKE_global.h"
#include "BKE_key.h"
#include "BKE_object.h"
#include "BKE_material.h"
#include "BKE_mesh.h"
#include "BKE_particle.h"
#include "BKE_scene.h"
#include "BKE_deform.h"
#include "BKE_python_component.h"
#include "BKE_report.h"

#include "DNA_python_component_types.h"

#include "ED_object.h"
#include "ED_particle.h"
#include "ED_view3d.h"
#include "ED_curve.h"
#include "ED_lattice.h"

static void rna_Object_internal_update(Main *UNUSED(bmain), Scene *UNUSED(scene), PointerRNA *ptr)
{
	DAG_id_tag_update(ptr->id.data, OB_RECALC_OB);
}

/* Multiplayer: the first enable seeds the sync flags and generates the id saved in the .range file. */
static void rna_RangeNetObjectSettings_replicate_set(PointerRNA *ptr, bool value)
{
	Object *ob = ptr->id.data;

	if (value) {
		ob->net.flags |= NET_OBJ_REPLICATE;
		if (ob->net.net_id == 0) {
			BKE_object_net_defaults(ob);
			BKE_object_net_id_generate(G_MAIN, ob);
		}
	}
	else {
		ob->net.flags &= ~NET_OBJ_REPLICATE;
	}
}

/* Default colors of each Particle Explosion style; same values as kBlastStyles in KX_Scene.cpp. */
static void rna_explosive_style_colors(RangeExplosiveSettings *es)
{
	switch (es->particle_style) {
		case EXPLOSIVE_STYLE_ELECTRIC:
			copy_v3_fl3(es->fire_color, 0.45f, 0.7f, 1.0f);
			copy_v3_fl3(es->smoke_color, 0.35f, 0.38f, 0.45f);
			copy_v3_fl3(es->spark_color, 0.6f, 0.85f, 1.0f);
			break;
		case EXPLOSIVE_STYLE_WATER:
			copy_v3_fl3(es->fire_color, 0.85f, 0.92f, 1.0f);
			copy_v3_fl3(es->smoke_color, 0.8f, 0.88f, 0.95f);
			copy_v3_fl3(es->spark_color, 0.7f, 0.85f, 1.0f);
			break;
		case EXPLOSIVE_STYLE_CONCRETE:
			copy_v3_fl3(es->fire_color, 0.6f, 0.56f, 0.5f);
			copy_v3_fl3(es->smoke_color, 0.55f, 0.52f, 0.48f);
			copy_v3_fl3(es->spark_color, 0.35f, 0.33f, 0.3f);
			break;
		default:
			copy_v3_fl3(es->fire_color, 1.0f, 1.0f, 1.0f);
			copy_v3_fl3(es->smoke_color, 0.18f, 0.16f, 0.15f);
			copy_v3_fl3(es->spark_color, 1.0f, 0.75f, 0.3f);
			break;
	}
}

static void rna_RangeExplosiveSettings_particle_style_update(Main *UNUSED(bmain), Scene *UNUSED(scene), PointerRNA *ptr)
{
	RangeExplosiveSettings *es = ptr->data;
	rna_explosive_style_colors(es);
	es->flags |= EXPLOSIVE_PARTICLE_COLORS;
}

static void rna_RangeExplosiveSettings_use_particle_explosion_set(PointerRNA *ptr, bool value)
{
	RangeExplosiveSettings *es = ptr->data;

	if (value) {
		es->flags |= EXPLOSIVE_PARTICLES;
		if (!(es->flags & EXPLOSIVE_PARTICLE_COLORS)) {
			rna_explosive_style_colors(es);
			es->fire_amount = es->smoke_amount = es->spark_amount = 1.0f;
			es->smoke_duration = es->blast_speed = 1.0f;
			es->flags |= EXPLOSIVE_PARTICLE_COLORS;
		}
	}
	else {
		es->flags &= ~EXPLOSIVE_PARTICLES;
	}
}

static void rna_RangeDeformSettings_mode_set(PointerRNA *ptr, int value)
{
	RangeDeformSettings *ds = ptr->data;

	ds->mode = value;
	/* Files saved before Bend existed. */
	if (value == DEFORM_MODE_BEND && ds->bend_max_angle == 0.0f) {
		ds->bend_axis = 2;
		ds->bend_angle = DEG2RADF(2.0f);
		ds->bend_max_angle = DEG2RADF(75.0f);
	}
}

static void rna_RangeDeformSettings_decal_set(PointerRNA *ptr, PointerRNA value)
{
	RangeDeformSettings *ds = ptr->data;

	id_us_min((ID *)ds->decal);
	ds->decal = value.data;
	id_us_plus((ID *)ds->decal);
	/* Files saved before decals existed. */
	if (ds->decal && ds->decal_size == 0.0f) {
		ds->decal_size = 0.5f;
		ds->max_decals = 20;
	}
	if (ds->decal && ds->scrape_spacing == 0.0f) {
		ds->scrape_speed = 2.0f;
		ds->scrape_spacing = 0.15f;
	}
}

/* Group e Object nao tem STRUCT_ID_REFCOUNT: conta o usuario aqui, como em dupli_group */
static void rna_RangeDestructionSettings_fragments_set(PointerRNA *ptr, PointerRNA value)
{
	RangeDestructionSettings *ds = ptr->data;

	id_us_min((ID *)ds->fragments);
	ds->fragments = value.data;
	id_us_plus((ID *)ds->fragments);
}

static void rna_RangeExplosiveSettings_effect_set(PointerRNA *ptr, PointerRNA value)
{
	RangeExplosiveSettings *es = ptr->data;

	id_us_min((ID *)es->effect);
	es->effect = value.data;
	id_us_plus((ID *)es->effect);
}

static void rna_RangeExplosiveSettings_mark_set(PointerRNA *ptr, PointerRNA value)
{
	RangeExplosiveSettings *es = ptr->data;

	id_us_min((ID *)es->mark);
	es->mark = value.data;
	id_us_plus((ID *)es->mark);
}

/* Light of each EXPLOSIVE_STYLE_* (Fire, Electric, Concrete, Water) and its strength; same table as
 * KX_Scene::FlashExplosionLight uses for files where flash_strength is still 0. */
static const float rna_explosive_flash_style[4][4] = {
	{1.0f, 0.5f, 0.18f, 1.0f}, {0.45f, 0.7f, 1.0f, 1.0f}, {1.0f, 0.62f, 0.32f, 0.45f}, {0.7f, 0.85f, 1.0f, 0.25f}};

static void rna_RangeExplosiveSettings_use_light_flash_set(PointerRNA *ptr, bool value)
{
	RangeExplosiveSettings *es = ptr->data;

	if (value) {
		es->flags |= EXPLOSIVE_LIGHT_FLASH;
		if (es->flash_strength == 0.0f) {
			const float *style = rna_explosive_flash_style[CLAMPIS(es->particle_style, 0, 3)];
			copy_v3_v3(es->flash_color, style);
			es->flash_strength = style[3];
			es->flash_duration = 1.0f;
		}
	}
	else {
		es->flags &= ~EXPLOSIVE_LIGHT_FLASH;
	}
}

static void rna_RangeExplosiveSettings_use_ground_mark_set(PointerRNA *ptr, bool value)
{
	RangeExplosiveSettings *es = ptr->data;

	if (value) {
		es->flags |= EXPLOSIVE_GROUND_MARK;
		if (es->mark_size == 0.0f) {
			es->mark_size = 1.0f;
			es->mark_life = 30.0f;
		}
	}
	else {
		es->flags &= ~EXPLOSIVE_GROUND_MARK;
	}
}

/* Fase Q: filling in "vem tudo zerado" -- picking a built-in Look seeds sensible emitter/motion/
 * appearance values for that look, the same way choosing a preset from the file-based preset menu
 * does. Only fires from an actual UI/Python change to particle_look (RNA update callback), so it
 * never fights a value the user tweaked afterward. */
static void rna_GPUParticleSettings_particle_look_update(Main *bmain, Scene *scene, PointerRNA *ptr)
{
	RangeGPUParticleSettings *gp = (RangeGPUParticleSettings *)ptr->data;

	switch (gp->particle_look) {
		case GPU_PARTICLE_LOOK_SMOKE:
			gp->use_vortex = 0;
			gp->gravity[0] = 0.0f; gp->gravity[1] = 0.0f; gp->gravity[2] = 0.3f;
			gp->lifetime = 3.0f;
			gp->emitter_radius = 0.3f;
			gp->velocity[0] = 0.0f; gp->velocity[1] = 0.0f; gp->velocity[2] = 0.6f;
			gp->velocity_randomness = 0.4f;
			gp->size = 0.5f; gp->end_size = 1.5f;
			gp->color[0] = 0.6f; gp->color[1] = 0.6f; gp->color[2] = 0.6f; gp->color[3] = 0.5f;
			gp->end_color[0] = 0.3f; gp->end_color[1] = 0.3f; gp->end_color[2] = 0.3f; gp->end_color[3] = 0.0f;
			gp->particle_count = 60;
			gp->emission_angle = 25.0f;
			gp->blend_mode = GPU_PARTICLE_BLEND_ALPHA;
			gp->billboard_mode = GPU_PARTICLE_BILLBOARD_VERTICAL;
			break;
		case GPU_PARTICLE_LOOK_FIRE:
			gp->use_vortex = 0;
			gp->gravity[0] = 0.0f; gp->gravity[1] = 0.0f; gp->gravity[2] = 1.2f;
			gp->lifetime = 1.1f;
			gp->emitter_radius = 0.35f;
			gp->velocity[0] = 0.0f; gp->velocity[1] = 0.0f; gp->velocity[2] = 1.4f;
			gp->velocity_randomness = 0.5f;
			gp->size = 0.9f; gp->end_size = 0.35f;
			gp->color[0] = 1.0f; gp->color[1] = 1.0f; gp->color[2] = 1.0f; gp->color[3] = 0.5f;
			gp->end_color[0] = 1.0f; gp->end_color[1] = 1.0f; gp->end_color[2] = 1.0f; gp->end_color[3] = 0.0f;
			gp->particle_count = 110;
			gp->emission_angle = 20.0f;
			gp->blend_mode = GPU_PARTICLE_BLEND_ADDITIVE;
			gp->billboard_mode = GPU_PARTICLE_BILLBOARD_VERTICAL;
			break;
		case GPU_PARTICLE_LOOK_SPARKLE:
			gp->use_vortex = 0;
			gp->gravity[0] = 0.0f; gp->gravity[1] = 0.0f; gp->gravity[2] = -1.0f;
			gp->lifetime = 1.0f;
			gp->emitter_radius = 0.2f;
			gp->velocity[0] = 0.0f; gp->velocity[1] = 0.0f; gp->velocity[2] = 1.5f;
			gp->velocity_randomness = 2.0f;
			gp->size = 0.08f; gp->end_size = 0.02f;
			gp->color[0] = 1.0f; gp->color[1] = 1.0f; gp->color[2] = 0.6f; gp->color[3] = 1.0f;
			gp->end_color[0] = 1.0f; gp->end_color[1] = 0.6f; gp->end_color[2] = 0.1f; gp->end_color[3] = 0.0f;
			gp->particle_count = 150;
			gp->emission_angle = 180.0f;
			gp->blend_mode = GPU_PARTICLE_BLEND_ADDITIVE;
			gp->billboard_mode = GPU_PARTICLE_BILLBOARD_CAMERA_FACING;
			break;
		case GPU_PARTICLE_LOOK_DISSOLVE:
			gp->use_vortex = 0;
			gp->gravity[0] = 0.0f; gp->gravity[1] = 0.0f; gp->gravity[2] = 0.0f;
			gp->lifetime = 2.0f;
			gp->emitter_radius = 0.3f;
			gp->velocity[0] = 0.0f; gp->velocity[1] = 0.0f; gp->velocity[2] = 0.2f;
			gp->velocity_randomness = 0.3f;
			gp->size = 0.4f; gp->end_size = 0.4f;
			gp->color[0] = 1.0f; gp->color[1] = 1.0f; gp->color[2] = 1.0f; gp->color[3] = 1.0f;
			gp->end_color[0] = 1.0f; gp->end_color[1] = 1.0f; gp->end_color[2] = 1.0f; gp->end_color[3] = 0.0f;
			gp->particle_count = 40;
			gp->emission_angle = 60.0f;
			gp->blend_mode = GPU_PARTICLE_BLEND_ALPHA;
			gp->billboard_mode = GPU_PARTICLE_BILLBOARD_CAMERA_FACING;
			break;
		case GPU_PARTICLE_LOOK_RAINBOW_TRAIL:
			gp->use_vortex = 0;
			gp->gravity[0] = 0.0f; gp->gravity[1] = 0.0f; gp->gravity[2] = 0.0f;
			gp->lifetime = 1.2f;
			gp->emitter_radius = 0.1f;
			gp->velocity[0] = 0.0f; gp->velocity[1] = 0.0f; gp->velocity[2] = 2.0f;
			gp->velocity_randomness = 0.5f;
			gp->size = 0.15f; gp->end_size = 0.05f;
			gp->color[0] = 1.0f; gp->color[1] = 1.0f; gp->color[2] = 1.0f; gp->color[3] = 1.0f;
			gp->end_color[0] = 1.0f; gp->end_color[1] = 1.0f; gp->end_color[2] = 1.0f; gp->end_color[3] = 0.0f;
			gp->particle_count = 80;
			gp->emission_angle = 15.0f;
			gp->blend_mode = GPU_PARTICLE_BLEND_ADDITIVE;
			gp->billboard_mode = GPU_PARTICLE_BILLBOARD_CAMERA_FACING;
			break;
		case GPU_PARTICLE_LOOK_TORNADO:
			gp->gravity[0] = 0.0f; gp->gravity[1] = 0.0f; gp->gravity[2] = 0.1f;
			gp->lifetime = 2.5f;
			gp->emitter_radius = 0.2f;
			gp->velocity[0] = 0.0f; gp->velocity[1] = 0.0f; gp->velocity[2] = 1.5f;
			gp->velocity_randomness = 0.15f;
			gp->size = 0.6f; gp->end_size = 0.2f;
			gp->color[0] = 0.6f; gp->color[1] = 0.5f; gp->color[2] = 0.4f; gp->color[3] = 0.6f;
			gp->end_color[0] = 0.5f; gp->end_color[1] = 0.45f; gp->end_color[2] = 0.4f; gp->end_color[3] = 0.0f;
			gp->particle_count = 100;
			gp->emission_angle = 180.0f;
			gp->blend_mode = GPU_PARTICLE_BLEND_ALPHA;
			gp->billboard_mode = GPU_PARTICLE_BILLBOARD_VERTICAL;
			/* Cone/vortex motion: narrow funnel at the emitter widening into the supercell as
			 * particles rise, spinning around the vertical axis -- this is what actually gives
			 * the tornado its cone silhouette instead of a straight-up puff. */
			gp->use_vortex = 1;
			gp->vortex_rotation_speed = 260.0f;
			gp->vortex_radius_top = 1.8f;
			gp->vortex_height = 2.5f;
			break;
		case GPU_PARTICLE_LOOK_WIND:
			gp->use_vortex = 0;
			gp->gravity[0] = 0.0f; gp->gravity[1] = 0.0f; gp->gravity[2] = 0.0f;
			gp->lifetime = 1.0f;
			gp->emitter_radius = 0.2f;
			gp->velocity[0] = 2.0f; gp->velocity[1] = 0.0f; gp->velocity[2] = 0.0f;
			gp->velocity_randomness = 0.3f;
			gp->size = 1.0f; gp->end_size = 1.0f;
			gp->color[0] = 1.0f; gp->color[1] = 1.0f; gp->color[2] = 1.0f; gp->color[3] = 0.3f;
			gp->end_color[0] = 1.0f; gp->end_color[1] = 1.0f; gp->end_color[2] = 1.0f; gp->end_color[3] = 0.0f;
			gp->particle_count = 40;
			gp->emission_angle = 10.0f;
			gp->blend_mode = GPU_PARTICLE_BLEND_ALPHA;
			gp->billboard_mode = GPU_PARTICLE_BILLBOARD_CAMERA_FACING;
			break;
		case GPU_PARTICLE_LOOK_AURORA:
			gp->use_vortex = 0;
			gp->gravity[0] = 0.0f; gp->gravity[1] = 0.0f; gp->gravity[2] = 0.0f;
			gp->lifetime = 4.0f;
			gp->emitter_radius = 0.5f;
			gp->velocity[0] = 0.0f; gp->velocity[1] = 0.0f; gp->velocity[2] = 0.05f;
			gp->velocity_randomness = 0.1f;
			gp->size = 1.5f; gp->end_size = 1.5f;
			gp->color[0] = 0.2f; gp->color[1] = 1.0f; gp->color[2] = 0.5f; gp->color[3] = 0.5f;
			gp->end_color[0] = 0.6f; gp->end_color[1] = 0.2f; gp->end_color[2] = 1.0f; gp->end_color[3] = 0.0f;
			gp->particle_count = 30;
			gp->emission_angle = 20.0f;
			gp->blend_mode = GPU_PARTICLE_BLEND_ADDITIVE;
			gp->billboard_mode = GPU_PARTICLE_BILLBOARD_VERTICAL;
			break;
		case GPU_PARTICLE_LOOK_REFLECTOR:
			/* Static sprites on the mesh vertices; Color = lit glow, End Color = faint unlit dot. */
			gp->use_vortex = 0;
			gp->emit_from = GPU_PARTICLE_EMIT_VERTICES;
			gp->size = 0.25f; gp->end_size = 0.25f;
			gp->color[0] = 1.0f; gp->color[1] = 0.75f; gp->color[2] = 0.2f; gp->color[3] = 1.0f;
			gp->end_color[0] = 0.4f; gp->end_color[1] = 0.3f; gp->end_color[2] = 0.1f; gp->end_color[3] = 0.15f;
			gp->blend_mode = GPU_PARTICLE_BLEND_ADDITIVE;
			gp->billboard_mode = GPU_PARTICLE_BILLBOARD_CAMERA_FACING;
			break;
		case GPU_PARTICLE_LOOK_DEFAULT:
		default:
			/* No preset -- leave whatever values the emitter already had. */
			break;
	}

	rna_Object_internal_update(bmain, scene, ptr);
}

/* Reverb area presets, ported from the RanGE-SoundReverb 1.6 Python component (OpenAL EFX
 * reverb values plus the filter it overlaid). Picking one copies its values into the settings;
 * the runtime (KX_Scene) only ever reads the resolved values. */
void rna_reverb_area_apply_preset(RangeReverbAreaSettings *ra, int preset)
{
	/* density, diffusion, gain, gain_hf, decay_time, decay_hf_ratio, reflections_gain,
	 * reflections_delay, late_reverb_gain, late_reverb_delay, air_absorption_gain_hf,
	 * room_rolloff_factor, decay_limit_hf, filter_type, filter_gain, filter_gain_lf, filter_gain_hf */
	static const struct {
		float density, diffusion, gain, gain_hf, decay_time, decay_hf_ratio;
		float refl_gain, refl_delay, late_gain, late_delay, air_abs_hf, room_rolloff;
		int decay_limit_hf, filter_type;
		float filter_gain, filter_gain_lf, filter_gain_hf;
	} presets[] = {
		[REVERB_AREA_PRESET_GENERIC] = {1.0f, 1.0f, 0.32f, 0.89f, 1.49f, 0.83f, 0.05f, 0.007f, 1.26f, 0.011f, 0.994f, 0.0f, 1,
		                                REVERB_AREA_FILTER_LOWPASS, 1.0f, 1.0f, 0.8f},
		[REVERB_AREA_PRESET_UNDERWATER] = {0.3f, 0.5f, 0.26f, 0.05f, 0.8f, 0.1f, 0.01f, 0.002f, 0.25f, 0.01f, 0.3f, 1.0f, 0,
		                                   REVERB_AREA_FILTER_LOWPASS, 0.5f, 1.0f, 0.1f},
		[REVERB_AREA_PRESET_CAVERN] = {1.0f, 1.0f, 0.5f, 0.7f, 2.31f, 0.59f, 0.25f, 0.01f, 1.26f, 0.022f, 0.994f, 0.0f, 1,
		                               REVERB_AREA_FILTER_BANDPASS, 1.0f, 0.8f, 0.8f},
		[REVERB_AREA_PRESET_HALL] = {1.0f, 1.0f, 0.316f, 0.708f, 3.92f, 0.7f, 0.05f, 0.02f, 1.23f, 0.03f, 0.994f, 0.0f, 1,
		                             REVERB_AREA_FILTER_LOWPASS, 0.9f, 1.0f, 0.7f},
		[REVERB_AREA_PRESET_FOREST] = {1.0f, 1.0f, 0.3f, 0.5f, 1.49f, 0.54f, 0.05f, 0.01f, 1.26f, 0.03f, 0.994f, 0.0f, 1,
		                               REVERB_AREA_FILTER_HIGHPASS, 0.7f, 0.4f, 1.0f},
	};

	if (preset <= REVERB_AREA_PRESET_CUSTOM || preset > REVERB_AREA_PRESET_FOREST) {
		/* Custom: keep whatever the user set. */
		return;
	}

	ra->density = presets[preset].density;
	ra->diffusion = presets[preset].diffusion;
	ra->gain = presets[preset].gain;
	ra->gain_hf = presets[preset].gain_hf;
	ra->decay_time = presets[preset].decay_time;
	ra->decay_hf_ratio = presets[preset].decay_hf_ratio;
	ra->reflections_gain = presets[preset].refl_gain;
	ra->reflections_delay = presets[preset].refl_delay;
	ra->late_reverb_gain = presets[preset].late_gain;
	ra->late_reverb_delay = presets[preset].late_delay;
	ra->air_absorption_gain_hf = presets[preset].air_abs_hf;
	ra->room_rolloff_factor = presets[preset].room_rolloff;
	ra->decay_limit_hf = presets[preset].decay_limit_hf;
	ra->filter_type = presets[preset].filter_type;
	ra->filter_gain = presets[preset].filter_gain;
	ra->filter_gain_lf = presets[preset].filter_gain_lf;
	ra->filter_gain_hf = presets[preset].filter_gain_hf;
}

/* Keeps the Empty's viewport display matching the area shape, so what is drawn is the area. */
void rna_reverb_area_sync_empty_draw(Object *ob)
{
	if (ob->type == OB_EMPTY) {
		ob->empty_drawtype = (ob->reverb_area.shape == REVERB_AREA_SHAPE_BOX) ? OB_CUBE : OB_EMPTY_SPHERE;
	}
}

static void rna_ReverbAreaSettings_preset_update(Main *bmain, Scene *scene, PointerRNA *ptr)
{
	RangeReverbAreaSettings *ra = (RangeReverbAreaSettings *)ptr->data;
	rna_reverb_area_apply_preset(ra, ra->preset);
	rna_Object_internal_update(bmain, scene, ptr);
}

/* Any hand-edited reverb/filter value means the area no longer matches its preset. */
static void rna_ReverbAreaSettings_param_update(Main *bmain, Scene *scene, PointerRNA *ptr)
{
	RangeReverbAreaSettings *ra = (RangeReverbAreaSettings *)ptr->data;
	ra->preset = REVERB_AREA_PRESET_CUSTOM;
	rna_Object_internal_update(bmain, scene, ptr);
}

static void rna_ReverbAreaSettings_shape_update(Main *bmain, Scene *scene, PointerRNA *ptr)
{
	rna_reverb_area_sync_empty_draw((Object *)ptr->id.data);
	rna_Object_internal_update(bmain, scene, ptr);
}

/* The 3D View preview needs the realtime redraw timer to animate the strikes. */
void rna_Object_lightning_preview_update(Main *bmain, Scene *UNUSED(scene), PointerRNA *UNUSED(ptr))
{
	WM_main_add_notifier(NC_OBJECT | ND_DRAW, NULL);
	if (bmain->wm.first) {
		ED_view3d_realtime_viewport_update((wmWindowManager *)bmain->wm.first);
	}
}

static void rna_GPUParticles_use_size_curve_update(Main *UNUSED(bmain), Scene *UNUSED(scene), PointerRNA *ptr)
{
	RangeGPUParticleSettings *gp = (RangeGPUParticleSettings *)ptr->data;

	if (gp->use_size_curve && !gp->size_curve) {
		gp->size_curve = curvemapping_add(1, 0.0f, 0.0f, 1.0f, 1.0f);
		curvemapping_initialize(gp->size_curve);
	}
}

static void rna_GPUParticles_use_color_curve_update(Main *UNUSED(bmain), Scene *UNUSED(scene), PointerRNA *ptr)
{
	RangeGPUParticleSettings *gp = (RangeGPUParticleSettings *)ptr->data;

	if (gp->use_color_curve && !gp->color_curve) {
		gp->color_curve = curvemapping_add(4, 0.0f, 0.0f, 1.0f, 1.0f);
		curvemapping_initialize(gp->color_curve);
	}
}

#else

static void rna_def_object_gpu_particles(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	static const EnumPropertyItem rna_enum_gpu_particle_billboard_mode_items[] = {
		{GPU_PARTICLE_BILLBOARD_CAMERA_FACING, "CAMERA_FACING", 0, "Camera Facing", "Quad always faces the camera fully (default)"},
		{GPU_PARTICLE_BILLBOARD_VERTICAL, "VERTICAL", 0, "Vertical", "Quad stays locked to world Z, only rotates horizontally to face the camera (smoke, fire, grass)"},
		{GPU_PARTICLE_BILLBOARD_HORIZONTAL, "HORIZONTAL", 0, "Horizontal (Facing Down)", "Quad lies flat in world space, always facing down -- clouds seen from below"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem rna_enum_gpu_particle_blend_mode_items[] = {
		{GPU_PARTICLE_BLEND_ALPHA, "ALPHA", 0, "Alpha", "Standard alpha blending (opaque smoke/dust)"},
		{GPU_PARTICLE_BLEND_ADDITIVE, "ADDITIVE", 0, "Additive", "Add particle color to the scene (glowing fire/sparks/electricity)"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem rna_enum_gpu_particle_collision_mode_items[] = {
		{GPU_PARTICLE_COLLISION_NONE, "NONE", 0, "None", "Particles ignore collision, passing through geometry (default)"},
		{GPU_PARTICLE_COLLISION_GROUND, "GROUND", 0, "Ground Plane", "Bounce/stop against an analytic flat ground at a fixed height"},
		{GPU_PARTICLE_COLLISION_DEPTH, "DEPTH", 0, "Screen-Space", "Bounce/stop against visible scene geometry using the depth buffer (1 frame delayed, needs Depth Transparency active in the scene)"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem rna_enum_gpu_particle_look_items[] = {
		{GPU_PARTICLE_LOOK_DEFAULT, "DEFAULT", 0, "Default", "Normal texture/round-sprite look"},
		{GPU_PARTICLE_LOOK_SMOKE, "SMOKE", 0, "Smoke", "Soft diffuse mask with slow drifting noise, fading out over its lifetime"},
		{GPU_PARTICLE_LOOK_SPARKLE, "SPARKLE", 0, "Sparkle", "Glitter/spark look that blinks at a random phase per particle"},
		{GPU_PARTICLE_LOOK_DISSOLVE, "DISSOLVE", 0, "Dissolve", "Texture dissolving into a noisy burnt edge as the particle ages"},
		{GPU_PARTICLE_LOOK_RAINBOW_TRAIL, "RAINBOW_TRAIL", 0, "Rainbow Trail", "Hue shifting over time and age, ignoring Color/End Color"},
		{GPU_PARTICLE_LOOK_TORNADO, "TORNADO", 0, "Tornado", "Rotating radial dust stripes, spinning faster near the center"},
		{GPU_PARTICLE_LOOK_WIND, "WIND", 0, "Wind", "Thin translucent horizontal streak with a subtle wobble"},
		{GPU_PARTICLE_LOOK_AURORA, "AURORA", 0, "Aurora", "Wavy vertical light curtain, best on tall stretched sprites"},
		{GPU_PARTICLE_LOOK_REFLECTOR, "REFLECTOR", 0, "Reflector",
		 "Fake road reflector (cat's eye): glows in Color when the camera looks at it, End Color when unlit. "
		 "No real light, use with Emit From: Mesh Vertices"},
		{GPU_PARTICLE_LOOK_FIRE, "FIRE", 0, "Fire",
		 "Flickering flame tongues, white-yellow when born, then orange, red and gone; Color tints it. "
		 "Put Smoke on the Mix emitter for smoke above"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem rna_enum_gpu_particle_emit_from_items[] = {
		{GPU_PARTICLE_EMIT_VOLUME, "VOLUME", 0, "Emitter Volume", "Particles spawn around Emitter Position and die after Lifetime"},
		{GPU_PARTICLE_EMIT_VERTICES, "VERTICES", 0, "Mesh Vertices",
		 "One static particle pinned on each vertex of this object's mesh (no motion, never dies)"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem rna_enum_gpu_particle_emission_mode_items[] = {
		{GPU_PARTICLE_EMISSION_CONTINUOUS, "CONTINUOUS", 0, "Continuous", "Each particle is born again as soon as it dies"},
		{GPU_PARTICLE_EMISSION_BURST, "BURST", 0, "Burst",
		 "The whole pool is born at once and stays dead until the next burst (explosions)"},
		{0, NULL, 0, NULL, NULL}
	};

	srna = RNA_def_struct(brna, "RangeGPUParticleSettings", NULL);
	RNA_def_struct_sdna(srna, "RangeGPUParticleSettings");
	RNA_def_struct_nested(brna, srna, "Object");
	RNA_def_struct_ui_text(srna, "GPU Particle Settings",
	                        "Settings used to seed this object's GPU particle emitter at game start");

	prop = RNA_def_property(srna, "gravity", PROP_FLOAT, PROP_XYZ);
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Gravity", "Acceleration applied to particles every frame");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "lifetime", PROP_FLOAT, PROP_TIME);
	RNA_def_property_range(prop, 0.01f, 1000.0f);
	RNA_def_property_ui_text(prop, "Lifetime", "Time in seconds a particle lives before respawning");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "emitter_position", PROP_FLOAT, PROP_XYZ);
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Emitter Position", "Local-space offset of the particle emitter from the object");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "emitter_radius", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.0f, 1000.0f);
	RNA_def_property_ui_text(prop, "Emitter Radius", "Radius of the spherical emission volume");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "velocity", PROP_FLOAT, PROP_VELOCITY);
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Velocity", "Base emission velocity of new particles");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "velocity_randomness", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 100.0f);
	RNA_def_property_ui_text(prop, "Velocity Randomness", "Random variation added to the base velocity");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "size", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.001f, 1000.0f);
	RNA_def_property_ui_text(prop, "Size", "Billboard size of a particle at birth");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "color", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_array(prop, 4);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Color", "Particle color at birth");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "end_color", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_array(prop, 4);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "End Color", "Particle color at end of life");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "end_size", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.0f, 1000.0f);
	RNA_def_property_ui_text(prop, "End Size", "Billboard size of a particle at end of life");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "particle_count", PROP_INT, PROP_NONE);
	RNA_def_property_range(prop, 1, 100000);
	RNA_def_property_ui_text(prop, "Particle Count", "Number of particles in the pool");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "texture", PROP_STRING, PROP_FILEPATH);
	RNA_def_property_string_sdna(prop, NULL, "texture_path");
	RNA_def_property_ui_text(prop, "Texture", "Sprite texture used for each particle (empty for the default round mask)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "emission_direction", PROP_FLOAT, PROP_XYZ);
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Emission Direction", "Central axis of the emission cone");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "emission_angle", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 180.0f);
	RNA_def_property_ui_text(prop, "Emission Angle",
	                          "Full cone angle in degrees around the emission direction (180 = uniform sphere)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "emit_from", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "emit_from");
	RNA_def_property_enum_items(prop, rna_enum_gpu_particle_emit_from_items);
	RNA_def_property_ui_text(prop, "Emit From", "Where the particles come from");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "emission_mode", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "emission_mode");
	RNA_def_property_enum_items(prop, rna_enum_gpu_particle_emission_mode_items);
	RNA_def_property_ui_text(prop, "Emission Mode", "Steady stream or the whole pool at once");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_burst_on_start", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "burst_flags", GPU_PARTICLE_BURST_ON_START);
	RNA_def_property_ui_text(prop, "Burst on Start",
	                          "Fire one burst as soon as the object enters the game "
	                          "(e.g. an explosion effect added by an Explosive)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "burst_interval", PROP_FLOAT, PROP_TIME);
	RNA_def_property_range(prop, 0.0f, 3600.0f);
	RNA_def_property_ui_range(prop, 0.0f, 30.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Repeat Every",
	                          "Seconds between automatic bursts, 0 = only on start or from Python "
	                          "(object.particles.burst())");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "drag", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 100.0f);
	RNA_def_property_ui_range(prop, 0.0f, 10.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Drag",
	                          "Air resistance: how fast particles lose their speed (0 = none); "
	                          "a fast burst with drag slows down like a fireball");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "flipbook_columns", PROP_INT, PROP_NONE);
	RNA_def_property_int_sdna(prop, NULL, "flipbook_cols");
	RNA_def_property_range(prop, 0, 64);
	RNA_def_property_ui_text(prop, "Columns",
	                          "Flipbook: frames across the texture atlas (1 = plain texture)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "flipbook_rows", PROP_INT, PROP_NONE);
	RNA_def_property_range(prop, 0, 64);
	RNA_def_property_ui_text(prop, "Rows",
	                          "Flipbook: frames down the texture atlas, frame 0 is the top left one");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "flipbook_cycles", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 100.0f);
	RNA_def_property_ui_range(prop, 0.0f, 10.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Cycles",
	                          "Flipbook: times the animation plays over each particle's life "
	                          "(0 = still frame, picked at random with Random Start)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_flipbook_random", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flipbook_random", 1);
	RNA_def_property_ui_text(prop, "Random Start", "Flipbook: each particle starts on a random frame");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_object_rotation", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "use_object_rotation", 1);
	RNA_def_property_ui_text(prop, "Use Object Rotation",
	                         "Gravity, velocity, emission direction, emitter position and the vortex axis "
	                         "follow the object's rotation (local space) instead of the world axes");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_vortex", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "use_vortex", 1);
	RNA_def_property_ui_text(prop, "Vortex / Cone",
	                          "Reshape particle motion into a rotating cone around the emitter's vertical axis "
	                          "(tornado/hurricane funnel), instead of the plain gravity/velocity path");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "vortex_rotation_speed", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, -3600.0f, 3600.0f);
	RNA_def_property_ui_text(prop, "Vortex Rotation Speed", "Spin speed around the vertical axis, in degrees per second");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "vortex_radius_top", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.0f, 1000.0f);
	RNA_def_property_ui_text(prop, "Vortex Top Radius",
	                          "Cone radius once a particle has risen vortex_height above the emitter "
	                          "(Emitter Radius is the radius at the base)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "vortex_height", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.01f, 1000.0f);
	RNA_def_property_ui_text(prop, "Vortex Height", "Height over which the cone widens from Emitter Radius to Vortex Top Radius");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "size_curve", PROP_POINTER, PROP_NONE);
	RNA_def_property_pointer_sdna(prop, NULL, "size_curve");
	RNA_def_property_struct_type(prop, "CurveMapping");
	RNA_def_property_ui_text(prop, "Size Curve", "Size over lifetime curve");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_size_curve", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "use_size_curve", 1);
	RNA_def_property_ui_text(prop, "Size Curve", "Enable size-over-lifetime curve");
	RNA_def_property_update(prop, NC_OBJECT, "rna_GPUParticles_use_size_curve_update");

	prop = RNA_def_property(srna, "color_curve", PROP_POINTER, PROP_NONE);
	RNA_def_property_pointer_sdna(prop, NULL, "color_curve");
	RNA_def_property_struct_type(prop, "CurveMapping");
	RNA_def_property_ui_text(prop, "Color Curve", "Color over lifetime curve (RGB channels)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_color_curve", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "use_color_curve", 1);
	RNA_def_property_ui_text(prop, "Color Curve", "Enable color-over-lifetime curve");
	RNA_def_property_update(prop, NC_OBJECT, "rna_GPUParticles_use_color_curve_update");

	prop = RNA_def_property(srna, "use_debug_ui", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "use_debug_ui", 1);
	RNA_def_property_ui_text(prop, "Live Debug UI", "Show an in-game ImGui panel to tweak these parameters live while playing");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "enabled", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_negative_sdna(prop, NULL, "disable_emission", 1);
	RNA_def_property_ui_text(prop, "Enabled",
	                          "Emit particles when the game starts. Independent of object visibility -- "
	                          "an invisible emitter with this on still simulates and draws its particles, "
	                          "and a visible object with this off shows no particles from it");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "blend_mode", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "blend_mode");
	RNA_def_property_enum_items(prop, rna_enum_gpu_particle_blend_mode_items);
	RNA_def_property_ui_text(prop, "Blend Mode", "How particle color blends with the scene behind it");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "billboard_mode", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "billboard_mode");
	RNA_def_property_enum_items(prop, rna_enum_gpu_particle_billboard_mode_items);
	RNA_def_property_ui_text(prop, "Billboard Mode", "How particle quads orient toward the camera");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_backface_culling", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "use_backface_culling", 1);
	RNA_def_property_ui_text(prop, "Backface Culling", "Hide the particle quad's back face instead of drawing it double-sided");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "collision_mode", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "collision_mode");
	RNA_def_property_enum_items(prop, rna_enum_gpu_particle_collision_mode_items);
	RNA_def_property_ui_text(prop, "Collision Mode", "How particles collide with the scene");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "collision_height", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_ui_text(prop, "Ground Height", "World-space Z height of the analytic ground plane (Ground Plane mode only, ignored when Ground Object is set)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "collision_ground_object", PROP_POINTER, PROP_NONE);
	RNA_def_property_struct_type(prop, "Object");
	RNA_def_property_pointer_sdna(prop, NULL, "collision_ground_object");
	RNA_def_property_flag(prop, PROP_EDITABLE);
	RNA_def_property_ui_text(prop, "Ground Object", "Optional object whose world-space Z height overrides Ground Height every frame (Ground Plane mode only)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "collision_bounce", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Bounce", "Restitution on collision (0 = particle sticks, 1 = bounces at equal speed)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "collision_friction", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Friction", "Velocity damping applied tangentially to the surface on collision");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	/* Fase P: custom GLSL fragment shader file, see frag_shader_path in DNA_object_types.h. */
	prop = RNA_def_property(srna, "fragment_shader_path", PROP_STRING, PROP_FILEPATH);
	RNA_def_property_string_sdna(prop, NULL, "frag_shader_path");
	RNA_def_property_ui_text(prop, "Fragment Shader File",
	                          "External .glsl file replacing the default sprite color/mask logic, hot-reloaded "
	                          "while the game runs. Must define its own void main() writing fragColor; "
	                          "available inputs: v_uv (-0.5..0.5 quad corner), v_lifeFrac, v_alpha, u_color, "
	                          "u_endColor, u_texture, u_useTexture, u_time. Empty = default look");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_fragment_shader", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "use_custom_frag_shader", 1);
	RNA_def_property_ui_text(prop, "Custom Fragment Shader", "Use the Fragment Shader File instead of the default sprite look");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	/* Fase Q: built-in look, baked into the engine (no external file), used by the Mix GPU
	 * Particle System panel. */
	prop = RNA_def_property(srna, "particle_look", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "particle_look");
	RNA_def_property_enum_items(prop, rna_enum_gpu_particle_look_items);
	RNA_def_property_ui_text(prop, "Look", "Built-in particle appearance. Picking one also seeds Emitter/Motion/Appearance below with values tuned for that look (like a preset) -- change them afterward freely, this only fires when the Look itself changes");
	RNA_def_property_update(prop, NC_OBJECT, "rna_GPUParticleSettings_particle_look_update");
}

/* One hand-tunable reverb/filter value: editing it switches the area preset to Custom. */
static void rna_def_reverb_area_param(StructRNA *srna, const char *identifier, float min, float max,
                                      const char *name, const char *description)
{
	PropertyRNA *prop = RNA_def_property(srna, identifier, PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, min, max);
	RNA_def_property_ui_range(prop, min, max, 1, 3);
	RNA_def_property_ui_text(prop, name, description);
	RNA_def_property_update(prop, NC_OBJECT, "rna_ReverbAreaSettings_param_update");
}

static void rna_def_object_lightning(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	static const EnumPropertyItem mode_items[] = {
		{LIGHTNING_MODE_AUTOMATIC, "AUTOMATIC", 0, "Automatic", "Strikes on their own, at the rate below, inside the time window"},
		{LIGHTNING_MODE_MANUAL, "MANUAL", 0, "Manual", "Strikes only when the logic asks (obj.strikeLightning() or Edit Object > Lightning Strike)"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem shape_items[] = {
		{LIGHTNING_SHAPE_CIRCLE, "CIRCLE", 0, "Circle", "Strikes fall inside a circle of radius = Empty size (follows its scale and rotation)"},
		{LIGHTNING_SHAPE_BOX, "BOX", 0, "Box", "Strikes fall inside a square of half side = Empty size (follows its scale and rotation)"},
		{0, NULL, 0, NULL, NULL}
	};

	srna = RNA_def_struct(brna, "RangeLightningSettings", NULL);
	RNA_def_struct_sdna(srna, "RangeLightningSettings");
	RNA_def_struct_nested(brna, srna, "Object");
	RNA_def_struct_ui_text(srna, "Lightning Settings", "Where and when lightning strikes fall around this Empty");

	prop = RNA_def_property(srna, "mode", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "mode");
	RNA_def_property_enum_items(prop, mode_items);
	RNA_def_property_ui_text(prop, "Mode", "When the strikes fall");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Object_lightning_preview_update");

	prop = RNA_def_property(srna, "shape", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "shape");
	RNA_def_property_enum_items(prop, shape_items);
	RNA_def_property_ui_text(prop, "Area", "Shape of the area where the strikes fall");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "rate", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "rate");
	RNA_def_property_range(prop, 0.0f, 600.0f);
	RNA_def_property_ui_range(prop, 0.0f, 60.0f, 10, 1);
	RNA_def_property_ui_text(prop, "Rate", "Automatic strikes per minute");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "big_chance", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "big_chance");
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Bolt Chance", "Share of automatic strikes with a visible bolt; the others are a flash only");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "start_time", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "start_time");
	RNA_def_property_range(prop, 0.0f, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.0f, 3600.0f, 100, 1);
	RNA_def_property_ui_text(prop, "Start", "Seconds of game time before the first automatic strike");

	prop = RNA_def_property(srna, "end_time", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "end_time");
	RNA_def_property_range(prop, 0.0f, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.0f, 3600.0f, 100, 1);
	RNA_def_property_ui_text(prop, "End", "Seconds of game time after which the automatic strikes stop (0 = never)");

	prop = RNA_def_property(srna, "height", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "height");
	RNA_def_property_range(prop, 1.0f, 2000.0f);
	RNA_def_property_ui_range(prop, 5.0f, 300.0f, 100, 1);
	RNA_def_property_ui_text(prop, "Cloud Height", "Height above the Empty where the bolts start");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "target", PROP_POINTER, PROP_NONE);
	RNA_def_property_pointer_sdna(prop, NULL, "target");
	RNA_def_property_struct_type(prop, "Object");
	RNA_def_property_flag(prop, PROP_EDITABLE | PROP_ID_SELF_CHECK);
	RNA_def_property_ui_text(prop, "Target", "Optional: the bolts go from the area of this Empty to this object (sideways, upward...) instead of from the cloud down to the ground");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "use_hit_ground", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", LIGHTNING_HIT_GROUND);
	RNA_def_property_ui_text(prop, "Hit Ground", "In game, the bolt ends on the first surface below the cloud (else at the Empty's height)");

	prop = RNA_def_property(srna, "use_sound", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_negative_sdna(prop, NULL, "flags", LIGHTNING_NO_SOUND);
	RNA_def_property_ui_text(prop, "Sound", "Play a Thunder sound of World Sound > Effects after each strike");

	prop = RNA_def_property(srna, "use_preview", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", LIGHTNING_PREVIEW);
	RNA_def_property_ui_text(prop, "Preview", "Show the automatic strikes in the 3D View");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_Object_lightning_preview_update");

	prop = RNA_def_property(srna, "intensity", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "intensity");
	RNA_def_property_range(prop, 0.0f, 10.0f);
	RNA_def_property_ui_range(prop, 0.0f, 3.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Intensity", "Brightness of the bolt and of the flash");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "width", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "width");
	RNA_def_property_range(prop, 0.05f, 20.0f);
	RNA_def_property_ui_range(prop, 0.1f, 5.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Width", "Thickness of the bolt");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "color", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_float_sdna(prop, NULL, "color");
	RNA_def_property_array(prop, 3);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Color", "Tint of the glow around the bolt (the core stays white)");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, NULL);

	prop = RNA_def_property(srna, "flash_distance", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "flash_distance");
	RNA_def_property_range(prop, 1.0f, 100000.0f);
	RNA_def_property_ui_range(prop, 10.0f, 2000.0f, 100, 0);
	RNA_def_property_ui_text(prop, "Flash Distance", "The flash on screen fades as the camera gets farther than this from the strike");
}

static void rna_def_object_reverb_area(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	static const EnumPropertyItem shape_items[] = {
		{REVERB_AREA_SHAPE_SPHERE, "SPHERE", 0, "Sphere", "Spherical area, radius = Empty size x X scale"},
		{REVERB_AREA_SHAPE_BOX, "BOX", 0, "Box", "Box area, follows the Empty's size, scale and rotation"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem preset_items[] = {
		{REVERB_AREA_PRESET_GENERIC, "GENERIC", 0, "Generic", "Neutral room reverb"},
		{REVERB_AREA_PRESET_UNDERWATER, "UNDERWATER", 0, "Underwater", "Muffled, dense sound with most highs removed"},
		{REVERB_AREA_PRESET_CAVERN, "CAVERN", 0, "Cavern", "Long, strong echoes of a cave"},
		{REVERB_AREA_PRESET_HALL, "HALL", 0, "Hall", "Long decay of a large hall"},
		{REVERB_AREA_PRESET_FOREST, "FOREST", 0, "Forest", "Short, open reverb with the lows thinned out"},
		{REVERB_AREA_PRESET_CUSTOM, "CUSTOM", 0, "Custom", "Values set by hand below"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem filter_items[] = {
		{REVERB_AREA_FILTER_LOWPASS, "LOWPASS", 0, "Low Pass", "Cut high frequencies (muffled)"},
		{REVERB_AREA_FILTER_HIGHPASS, "HIGHPASS", 0, "High Pass", "Cut low frequencies (thin)"},
		{REVERB_AREA_FILTER_BANDPASS, "BANDPASS", 0, "Band Pass", "Cut both ends"},
		{0, NULL, 0, NULL, NULL}
	};

	srna = RNA_def_struct(brna, "RangeReverbAreaSettings", NULL);
	RNA_def_struct_sdna(srna, "RangeReverbAreaSettings");
	RNA_def_struct_nested(brna, srna, "Object");
	RNA_def_struct_ui_text(srna, "Reverb Area Settings",
	                       "Reverb applied to 3D speakers while the active camera is inside this area");

	prop = RNA_def_property(srna, "shape", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "shape");
	RNA_def_property_enum_items(prop, shape_items);
	RNA_def_property_ui_text(prop, "Shape", "Shape of the area (also sets how the Empty is drawn)");
	RNA_def_property_update(prop, NC_OBJECT | ND_DRAW, "rna_ReverbAreaSettings_shape_update");

	prop = RNA_def_property(srna, "preset", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "preset");
	RNA_def_property_enum_items(prop, preset_items);
	RNA_def_property_ui_text(prop, "Behavior", "Sound behavior inside the area. Picking one fills the values below; editing any of them switches to Custom");
	RNA_def_property_update(prop, NC_OBJECT, "rna_ReverbAreaSettings_preset_update");

	prop = RNA_def_property(srna, "inner_factor", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "inner_factor");
	RNA_def_property_range(prop, 0.4f, 0.99f);
	RNA_def_property_ui_text(prop, "Full Effect Zone", "Fraction of the area size where the effect is at full strength; it fades out between here and the edge");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "priority", PROP_INT, PROP_NONE);
	RNA_def_property_int_sdna(prop, NULL, "priority");
	RNA_def_property_range(prop, -100, 100);
	RNA_def_property_ui_text(prop, "Priority", "When areas overlap and both are at full strength, the higher priority wins (e.g. a room inside a cave)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_filter", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "use_filter", 1);
	RNA_def_property_ui_text(prop, "Filter", "Also filter the direct sound (EQ) while inside the area");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "filter_type", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "filter_type");
	RNA_def_property_enum_items(prop, filter_items);
	RNA_def_property_ui_text(prop, "Filter Type", "");
	RNA_def_property_update(prop, NC_OBJECT, "rna_ReverbAreaSettings_param_update");

	rna_def_reverb_area_param(srna, "density", 0.0f, 1.0f, "Density", "Modal density of the late reverb (lower = more colored)");
	rna_def_reverb_area_param(srna, "diffusion", 0.0f, 1.0f, "Diffusion", "Echo density of the late reverb");
	rna_def_reverb_area_param(srna, "gain", 0.0f, 1.0f, "Gain", "Overall reverb level at full strength");
	rna_def_reverb_area_param(srna, "gain_hf", 0.0f, 1.0f, "Gain HF", "Reverb attenuation of high frequencies");
	rna_def_reverb_area_param(srna, "decay_time", 0.1f, 20.0f, "Decay Time", "Seconds the reverb takes to fade (60 dB)");
	rna_def_reverb_area_param(srna, "decay_hf_ratio", 0.1f, 2.0f, "Decay HF Ratio", "High frequency decay time relative to Decay Time");
	rna_def_reverb_area_param(srna, "reflections_gain", 0.0f, 3.16f, "Reflections Gain", "Level of the early reflections");
	rna_def_reverb_area_param(srna, "reflections_delay", 0.0f, 0.3f, "Reflections Delay", "Seconds until the first reflection");
	rna_def_reverb_area_param(srna, "late_reverb_gain", 0.0f, 10.0f, "Late Reverb Gain", "Level of the late reverb tail");
	rna_def_reverb_area_param(srna, "late_reverb_delay", 0.0f, 0.1f, "Late Reverb Delay", "Seconds between the first reflection and the late reverb");
	rna_def_reverb_area_param(srna, "air_absorption_gain_hf", 0.892f, 1.0f, "Air Absorption HF", "High frequency loss through air per meter");
	rna_def_reverb_area_param(srna, "room_rolloff_factor", 0.0f, 10.0f, "Room Rolloff", "Distance attenuation of the reverb");
	rna_def_reverb_area_param(srna, "filter_gain", 0.0f, 1.0f, "Filter Gain", "Direct sound level at full strength");
	rna_def_reverb_area_param(srna, "filter_gain_lf", 0.0f, 1.0f, "Filter Gain LF", "Low frequency level at full strength (Band Pass/High Pass)");
	rna_def_reverb_area_param(srna, "filter_gain_hf", 0.0f, 1.0f, "Filter Gain HF", "High frequency level at full strength (Band Pass/Low Pass)");

	prop = RNA_def_property(srna, "decay_limit_hf", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "decay_limit_hf", 1);
	RNA_def_property_ui_text(prop, "Decay HF Limit", "Limit high frequency decay by air absorption");
	RNA_def_property_update(prop, NC_OBJECT, "rna_ReverbAreaSettings_param_update");
}

static void rna_def_object_network(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	srna = RNA_def_struct(brna, "RangeNetObjectSettings", NULL);
	RNA_def_struct_sdna(srna, "RangeNetObjectSettings");
	RNA_def_struct_nested(brna, srna, "Object");
	RNA_def_struct_ui_text(srna, "Network Settings", "Multiplayer replication of the object");

	prop = RNA_def_property(srna, "use_replicate", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", NET_OBJ_REPLICATE);
	RNA_def_property_boolean_funcs(prop, NULL, "rna_RangeNetObjectSettings_replicate_set");
	RNA_def_property_ui_text(prop, "Replicate",
	                         "The server sends this object to the players. Everyone must run the same .range file");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "net_id", PROP_INT, PROP_UNSIGNED);
	RNA_def_property_int_sdna(prop, NULL, "net_id");
	RNA_def_property_clear_flag(prop, PROP_EDITABLE);
	RNA_def_property_ui_text(prop, "Network ID",
	                         "Identifier saved in the file (random, does not change when the object is renamed)");

	prop = RNA_def_property(srna, "sync_transform", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", NET_OBJ_SYNC_TRANSFORM);
	RNA_def_property_ui_text(prop, "Transform", "Replicate position and rotation");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "sync_velocity", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", NET_OBJ_SYNC_VELOCITY);
	RNA_def_property_ui_text(prop, "Velocity", "Replicate the linear velocity (smoother physics objects on the players)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "sync_angular_velocity", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", NET_OBJ_SYNC_ANGULAR);
	RNA_def_property_ui_text(prop, "Angular Velocity", "Replicate the angular velocity");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_always_relevant", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", NET_OBJ_ALWAYS_RELEVANT);
	RNA_def_property_ui_text(prop, "Always Relevant", "Send to every player whatever the distance");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_interpolate", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", NET_OBJ_INTERPOLATE);
	RNA_def_property_ui_text(prop, "Interpolate",
	                         "Players draw the object between two snapshots (smooth) instead of jumping to the last one");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "priority", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "priority");
	RNA_def_property_range(prop, 0.01f, 100.0f);
	RNA_def_property_ui_range(prop, 0.1f, 10.0f, 10, 2);
	RNA_def_property_float_default(prop, 1.0f);
	RNA_def_property_ui_text(prop, "Priority",
	                         "Objects with more priority get the bandwidth first when the connection is busy");
	RNA_def_property_update(prop, NC_OBJECT, NULL);
}

static void rna_def_object_destruction(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	srna = RNA_def_struct(brna, "RangeDestructionSettings", NULL);
	RNA_def_struct_sdna(srna, "RangeDestructionSettings");
	RNA_def_struct_nested(brna, srna, "Object");
	RNA_def_struct_ui_text(srna, "Destruction Settings",
	                       "Replaces the object in game by its pre-fractured fragments on a strong hit");

	prop = RNA_def_property(srna, "fragments", PROP_POINTER, PROP_NONE);
	RNA_def_property_pointer_sdna(prop, NULL, "fragments");
	RNA_def_property_struct_type(prop, "Group");
	RNA_def_property_flag(prop, PROP_EDITABLE);
	RNA_def_property_pointer_funcs(prop, NULL, "rna_RangeDestructionSettings_fragments_set", NULL, NULL);
	RNA_def_property_ui_text(prop, "Fragments",
	                         "Group with the pieces, fractured around the origin and kept in an inactive layer. "
	                         "Empty: the object just disappears when it breaks");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "break_impulse", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "break_impulse");
	RNA_def_property_range(prop, 0.001f, 100000.0f);
	RNA_def_property_ui_range(prop, 0.1f, 1000.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Break Impulse",
	                         "Impact strength (summed contact impulse, N*s) that breaks the object. "
	                         "Explosions compare their impulse at the object against it too");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_break_on_collision", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", DESTRUCTION_BREAK_ON_COLLISION);
	RNA_def_property_ui_text(prop, "Break on Collision",
	                         "Break on strong collisions. Off: only explosions and Python (shatter()) break it");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "burst_speed", PROP_FLOAT, PROP_VELOCITY);
	RNA_def_property_float_sdna(prop, NULL, "burst_speed");
	RNA_def_property_range(prop, 0.0f, 1000.0f);
	RNA_def_property_ui_range(prop, 0.0f, 50.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Burst Speed", "Speed the fragments fly apart from the impact point");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_inherit_velocity", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", DESTRUCTION_INHERIT_VELOCITY);
	RNA_def_property_ui_text(prop, "Inherit Velocity", "Fragments keep the velocity the object had when it broke");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "debris_lifetime", PROP_FLOAT, PROP_TIME);
	RNA_def_property_float_sdna(prop, NULL, "debris_lifetime");
	RNA_def_property_range(prop, 0.0f, 3600.0f);
	RNA_def_property_ui_range(prop, 0.0f, 120.0f, 100, 1);
	RNA_def_property_ui_text(prop, "Debris Lifetime",
	                         "Seconds before the fragments disappear (0 = permanent, still limited by the "
	                         "scene's Max Debris)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "fx", PROP_POINTER, PROP_NONE);
	RNA_def_property_flag(prop, PROP_NEVER_NULL);
	RNA_def_property_pointer_sdna(prop, NULL, "fx");
	RNA_def_property_struct_type(prop, "RangeExplosiveSettings");
	RNA_def_property_ui_text(prop, "Break Effect",
	                         "Effect object, Particle Explosion and Ground Mark when the object breaks "
	                         "(only the effect settings are used)");
}

static void rna_def_object_explosive(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	srna = RNA_def_struct(brna, "RangeExplosiveSettings", NULL);
	RNA_def_struct_sdna(srna, "RangeExplosiveSettings");
	RNA_def_struct_nested(brna, srna, "Object");
	RNA_def_struct_ui_text(srna, "Explosive Settings",
	                       "Radial impulse that pushes objects, breaks destructibles and detonates explosives");

	prop = RNA_def_property(srna, "radius", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "radius");
	RNA_def_property_range(prop, 0.01f, 1000.0f);
	RNA_def_property_ui_range(prop, 0.1f, 50.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Radius", "Distance the explosion reaches");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "force", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "force");
	RNA_def_property_range(prop, 0.0f, 100000.0f);
	RNA_def_property_ui_range(prop, 0.0f, 500.0f, 10, 1);
	RNA_def_property_ui_text(prop, "Force",
	                         "Impulse (N*s) at the center of the explosion, falling linearly to 0 at the radius");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "up_bias", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "up_bias");
	RNA_def_property_range(prop, 0.0f, 5.0f);
	RNA_def_property_ui_range(prop, 0.0f, 1.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Up Bias", "Extra upward push, so objects fly up instead of sliding on the floor");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_occlusion", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", EXPLOSIVE_OCCLUSION);
	RNA_def_property_ui_text(prop, "Occlusion", "Static geometry (walls, floor) between the blast and an object shields it");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "fuse", PROP_FLOAT, PROP_TIME);
	RNA_def_property_float_sdna(prop, NULL, "fuse");
	RNA_def_property_range(prop, 0.0f, 3600.0f);
	RNA_def_property_ui_range(prop, 0.0f, 30.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Fuse",
	                         "Seconds after the object enters the game until it explodes, e.g. a grenade "
	                         "added with Add Object (0 = no fuse)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_explode_on_impact", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", EXPLOSIVE_ON_IMPACT);
	RNA_def_property_ui_text(prop, "Explode on Impact", "Explode on collisions stronger than Impact Impulse");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "impact_impulse", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "impact_impulse");
	RNA_def_property_range(prop, 0.0f, 100000.0f);
	RNA_def_property_ui_range(prop, 0.1f, 1000.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Impact Impulse",
	                         "Hit strength (summed contact impulse, N*s) that detonates it, by collision or "
	                         "by another explosion");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_chain_reaction", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", EXPLOSIVE_CHAIN_REACTION);
	RNA_def_property_ui_text(prop, "Chain Reaction",
	                         "Other explosions stronger than Impact Impulse here detonate it (next frame)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "effect", PROP_POINTER, PROP_NONE);
	RNA_def_property_pointer_sdna(prop, NULL, "effect");
	RNA_def_property_struct_type(prop, "Object");
	RNA_def_property_flag(prop, PROP_EDITABLE | PROP_ID_SELF_CHECK);
	RNA_def_property_pointer_funcs(prop, NULL, "rna_RangeExplosiveSettings_effect_set", NULL, NULL);
	RNA_def_property_ui_text(prop, "Effect",
	                         "Object (in an inactive layer) added at the blast, e.g. fire/smoke or a sound");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "effect_life", PROP_FLOAT, PROP_TIME);
	RNA_def_property_float_sdna(prop, NULL, "effect_life");
	RNA_def_property_range(prop, 0.0f, 3600.0f);
	RNA_def_property_ui_range(prop, 0.0f, 30.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Effect Life", "Seconds the effect object lives (0 = until removed by its own logic)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	static const EnumPropertyItem particle_size_items[] = {
		{EXPLOSIVE_PARTICLES_TINY, "TINY", 0, "Tiny", "Firecracker or small charge, about 1 m wide"},
		{EXPLOSIVE_PARTICLES_SMALL, "SMALL", 0, "Small", "Grenade or small barrel, about 2 m wide"},
		{EXPLOSIVE_PARTICLES_MEDIUM, "MEDIUM", 0, "Medium", "Gas cylinder or crate, about 4 m wide"},
		{EXPLOSIVE_PARTICLES_LARGE, "LARGE", 0, "Large", "Car or fuel tank, about 8 m wide"},
		{EXPLOSIVE_PARTICLES_HUGE, "HUGE", 0, "Huge", "Truck or building, about 14 m wide"},
		{0, NULL, 0, NULL, NULL}
	};

	prop = RNA_def_property(srna, "use_particle_explosion", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", EXPLOSIVE_PARTICLES);
	RNA_def_property_boolean_funcs(prop, NULL, "rna_RangeExplosiveSettings_use_particle_explosion_set");
	RNA_def_property_ui_text(prop, "Particle Explosion",
	                         "Built-in fireball, smoke and debris (GPU particles) at the blast, no Effect object needed");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "particle_size", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "particle_size");
	RNA_def_property_enum_items(prop, particle_size_items);
	RNA_def_property_ui_text(prop, "Explosion Size", "Preset size of the built-in particle explosion");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	static const EnumPropertyItem particle_style_items[] = {
		{EXPLOSIVE_STYLE_FIRE, "FIRE", 0, "Fire", "Fireball, dark smoke and sparks (gas, fuel, grenade)"},
		{EXPLOSIVE_STYLE_ELECTRIC, "ELECTRIC", 0, "Electric", "Plasma flash, thin smoke and fast electric sparks (transformer, battery)"},
		{EXPLOSIVE_STYLE_CONCRETE, "CONCRETE", 0, "Concrete", "No fire: dust ring, big dust cloud and falling debris (wall, rock)"},
		{EXPLOSIVE_STYLE_WATER, "WATER", 0, "Water",
		 "Foam splash thrown up, mist and falling droplets (depth charge, water tank, mine in a lake)"},
		{0, NULL, 0, NULL, NULL}
	};

	prop = RNA_def_property(srna, "particle_style", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "particle_style");
	RNA_def_property_enum_items(prop, particle_style_items);
	RNA_def_property_ui_text(prop, "Explosion Style", "What the explosion is made of; picking one resets its colors");
	RNA_def_property_update(prop, NC_OBJECT, "rna_RangeExplosiveSettings_particle_style_update");

	prop = RNA_def_property(srna, "fire_color", PROP_FLOAT, PROP_COLOR_GAMMA);
	RNA_def_property_array(prop, 3);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Fire Color", "Tint of the fireball (white = natural fire colors)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "smoke_color", PROP_FLOAT, PROP_COLOR_GAMMA);
	RNA_def_property_array(prop, 3);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Smoke Color", "Color of the smoke when born; it gets lighter as it rises");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "spark_color", PROP_FLOAT, PROP_COLOR_GAMMA);
	RNA_def_property_array(prop, 3);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Particle Color", "Color of the flying debris sparks; they darken as they cool");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "fire_amount", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 4.0f);
	RNA_def_property_ui_text(prop, "Fire Amount", "How many fire puffs, relative to the size preset (0 = no fireball)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "smoke_amount", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 4.0f);
	RNA_def_property_ui_text(prop, "Smoke Amount", "How much smoke, relative to the size preset (0 = no smoke)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "spark_amount", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 4.0f);
	RNA_def_property_ui_text(prop, "Particle Amount", "How many debris sparks, relative to the size preset (0 = none)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "smoke_duration", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.2f, 4.0f);
	RNA_def_property_ui_text(prop, "Smoke Duration", "How long the smoke lasts, relative to the size preset");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "blast_speed", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.2f, 4.0f);
	RNA_def_property_ui_text(prop, "Blast Speed", "How hard fire, smoke and sparks are thrown out, relative to the size preset");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_sound", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_negative_sdna(prop, NULL, "flags", EXPLOSIVE_NO_SOUND);
	RNA_def_property_ui_text(prop, "Sound", "Play the Explosion or Destruction sound of World Sound > Effects for this size");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_light_flash", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", EXPLOSIVE_LIGHT_FLASH);
	RNA_def_property_boolean_funcs(prop, NULL, "rna_RangeExplosiveSettings_use_light_flash_set");
	RNA_def_property_ui_text(prop, "Light Flash",
	                         "A point light flashes at the blast, lighting the ground and walls around it "
	                         "(the scene gets one extra light while it runs)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "flash_color", PROP_FLOAT, PROP_COLOR_GAMMA);
	RNA_def_property_float_sdna(prop, NULL, "flash_color");
	RNA_def_property_array(prop, 3);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Flash Color", "Color of the Light Flash");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "flash_strength", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "flash_strength");
	RNA_def_property_range(prop, 0.0f, 10.0f);
	RNA_def_property_ui_range(prop, 0.05f, 4.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Flash Strength", "How bright the Light Flash is, relative to the size preset");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "flash_duration", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "flash_duration");
	RNA_def_property_range(prop, 0.1f, 10.0f);
	RNA_def_property_ui_range(prop, 0.2f, 4.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Flash Duration", "How long the Light Flash lasts, relative to the size preset");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_ground_mark", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", EXPLOSIVE_GROUND_MARK);
	RNA_def_property_boolean_funcs(prop, NULL, "rna_RangeExplosiveSettings_use_ground_mark_set");
	RNA_def_property_ui_text(prop, "Ground Mark",
	                         "Paint the material of the Mark object on the ground under the blast (like an Impact Decal)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "mark", PROP_POINTER, PROP_NONE);
	RNA_def_property_pointer_sdna(prop, NULL, "mark");
	RNA_def_property_struct_type(prop, "Object");
	RNA_def_property_flag(prop, PROP_EDITABLE | PROP_ID_SELF_CHECK);
	RNA_def_property_pointer_funcs(prop, NULL, "rna_RangeExplosiveSettings_mark_set", NULL, NULL);
	RNA_def_property_ui_text(prop, "Mark",
	                         "Mesh object (in an inactive layer) whose material is painted on the ground, "
	                         "e.g. a scorch with alpha");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_mark_nearby", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", EXPLOSIVE_MARK_NEARBY);
	RNA_def_property_ui_text(prop, "Mark Nearby Objects",
	                         "Also paint a smaller mark on the side facing the blast of the objects around it "
	                         "(12 closest at most)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "mark_size", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.1f, 4.0f);
	RNA_def_property_ui_text(prop, "Mark Size", "Size of the ground mark, relative to the explosion size");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "mark_life", PROP_FLOAT, PROP_TIME);
	RNA_def_property_range(prop, 0.0f, 3600.0f);
	RNA_def_property_ui_range(prop, 0.0f, 120.0f, 100, 1);
	RNA_def_property_ui_text(prop, "Mark Life", "Seconds the ground mark stays (0 = forever)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);
}

static void rna_def_object_deform(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	srna = RNA_def_struct(brna, "RangeDeformSettings", NULL);
	RNA_def_struct_sdna(srna, "RangeDeformSettings");
	RNA_def_struct_nested(brna, srna, "Object");
	RNA_def_struct_ui_text(srna, "Deformation Settings",
	                       "Dents the mesh around the contact point on strong hits and explosions");

	static const EnumPropertyItem mode_items[] = {
		{DEFORM_MODE_DENT, "DENT", ICON_MOD_SHRINKWRAP, "Dent", "Push the surface in around the contact point (car body, barrel, plate)"},
		{DEFORM_MODE_BEND, "BEND", ICON_MOD_SIMPLEDEFORM, "Bend", "Fold the whole piece into a V at the contact point (bar, pole, sign, fence post)"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem axis_items[] = {
		{0, "X", 0, "X", ""},
		{1, "Y", 0, "Y", ""},
		{2, "Z", 0, "Z", ""},
		{0, NULL, 0, NULL, NULL}
	};

	prop = RNA_def_property(srna, "mode", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "mode");
	RNA_def_property_enum_items(prop, mode_items);
	RNA_def_property_enum_funcs(prop, NULL, "rna_RangeDeformSettings_mode_set", NULL);
	RNA_def_property_ui_text(prop, "Mode", "How a hit deforms the mesh");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "bend_axis", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "bend_axis");
	RNA_def_property_enum_items(prop, axis_items);
	RNA_def_property_ui_text(prop, "Bend Axis",
	                         "Local long axis of the object. The part further along it than the hit bends, "
	                         "the base (lowest end) stays");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "bend_angle", PROP_FLOAT, PROP_ANGLE);
	RNA_def_property_float_sdna(prop, NULL, "bend_angle");
	RNA_def_property_range(prop, 0.0f, M_PI);
	RNA_def_property_ui_text(prop, "Bend Angle", "Bend per N*s of impulse above Dent Impulse. Lower = stiffer");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "bend_max_angle", PROP_FLOAT, PROP_ANGLE);
	RNA_def_property_float_sdna(prop, NULL, "bend_max_angle");
	RNA_def_property_range(prop, 0.0f, M_PI);
	RNA_def_property_ui_text(prop, "Max Bend", "Most the object bends, summing all hits");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "decal", PROP_POINTER, PROP_NONE);
	RNA_def_property_pointer_sdna(prop, NULL, "decal");
	RNA_def_property_struct_type(prop, "Object");
	RNA_def_property_flag(prop, PROP_EDITABLE | PROP_ID_SELF_CHECK);
	RNA_def_property_pointer_funcs(prop, NULL, "rna_RangeDeformSettings_decal_set", NULL, NULL);
	RNA_def_property_ui_text(prop, "Decal",
	                         "Mesh object (in an inactive layer) whose material is projected on the surface at each "
	                         "hit: scratch, bullet hole, burn. UV 0..1 covers the mark");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "decal_size", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "decal_size");
	RNA_def_property_range(prop, 0.001f, 1000.0f);
	RNA_def_property_ui_range(prop, 0.01f, 10.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Decal Size", "Width of the mark projected at the hit");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "decal_life", PROP_FLOAT, PROP_TIME);
	RNA_def_property_float_sdna(prop, NULL, "decal_life");
	RNA_def_property_range(prop, 0.0f, 100000.0f);
	RNA_def_property_ui_range(prop, 0.0f, 600.0f, 10, 1);
	RNA_def_property_ui_text(prop, "Decal Life", "Seconds a mark lives, 0 = permanent");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_scrape", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", DEFORM_SCRAPE);
	RNA_def_property_ui_text(prop, "Scrape Marks",
	                         "Leave a trail of Decal marks where an object slides on this one (dragging, skidding). "
	                         "Heavy: every mark is a new mesh and the object gets a private mesh copy");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	static const EnumPropertyItem scrape_style_items[] = {
		{0, "STAMPS", 0, "Stamps", "A Decal mark every Spacing, projected on the surface (follows any shape, heavy)"},
		{DEFORM_SCRAPE_STRIP, "STRIP", 0, "Strip",
		 "One continuous flat strip along the slide, like a tire mark (light, best on flat ground)"},
		{0, NULL, 0, NULL, NULL}
	};
	prop = RNA_def_property(srna, "scrape_style", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_bitflag_sdna(prop, NULL, "flags");
	RNA_def_property_enum_items(prop, scrape_style_items);
	RNA_def_property_ui_text(prop, "Scrape Style", "How the scrape trail is drawn");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "scrape_speed", PROP_FLOAT, PROP_VELOCITY);
	RNA_def_property_float_sdna(prop, NULL, "scrape_speed");
	RNA_def_property_range(prop, 0.0f, 1000.0f);
	RNA_def_property_ui_range(prop, 0.1f, 50.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Scrape Speed", "Sliding speed of a contact that starts leaving marks");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "scrape_spacing", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "scrape_spacing");
	RNA_def_property_range(prop, 0.01f, 100.0f);
	RNA_def_property_ui_range(prop, 0.02f, 2.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Scrape Spacing",
	                         "Distance slid between two marks. Smaller = continuous trail, more meshes");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "max_decals", PROP_INT, PROP_NONE);
	RNA_def_property_int_sdna(prop, NULL, "max_decals");
	RNA_def_property_range(prop, 1, 1000);
	RNA_def_property_ui_text(prop, "Max Decals", "Most marks on the object, past it the oldest one goes");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "dent_impulse", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "dent_impulse");
	RNA_def_property_range(prop, 0.0f, 100000.0f);
	RNA_def_property_ui_range(prop, 0.1f, 1000.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Dent Impulse",
	                         "Impact strength (summed contact impulse, N*s) that starts denting the mesh. "
	                         "On a destructible object, hits below Break Impulse dent and stronger ones break");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_dent_on_collision", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", DEFORM_ON_COLLISION);
	RNA_def_property_ui_text(prop, "Dent on Collision",
	                         "Dent on strong collisions. Off: only explosions and Python (dent()) dent it");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "radius", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "radius");
	RNA_def_property_range(prop, 0.001f, 1000.0f);
	RNA_def_property_ui_range(prop, 0.01f, 10.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Radius", "Distance from the contact point reached by a dent");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "depth", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "depth");
	RNA_def_property_range(prop, 0.0f, 10.0f);
	RNA_def_property_ui_range(prop, 0.0f, 0.1f, 0.1, 4);
	RNA_def_property_ui_text(prop, "Depth",
	                         "Dent depth at the contact point (m) per N*s of impulse above Dent Impulse. "
	                         "Lower = stiffer material");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "max_depth", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "max_depth");
	RNA_def_property_range(prop, 0.0f, 1000.0f);
	RNA_def_property_ui_range(prop, 0.0f, 2.0f, 1, 3);
	RNA_def_property_ui_text(prop, "Max Depth", "Most a vertex can move away from its rest position, summing all hits");
	RNA_def_property_update(prop, NC_OBJECT, NULL);

	prop = RNA_def_property(srna, "use_update_physics", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flags", DEFORM_UPDATE_PHYSICS);
	RNA_def_property_ui_text(prop, "Update Physics",
	                         "Rebuild the collision shape from the dented mesh (Triangle Mesh bounds only, costly)");
	RNA_def_property_update(prop, NC_OBJECT, NULL);
}

void RNA_def_object_game(BlenderRNA *brna)
{
	rna_def_object_gpu_particles(brna);
	rna_def_object_reverb_area(brna);
	rna_def_object_lightning(brna);
	rna_def_object_network(brna);
	rna_def_object_destruction(brna);
	rna_def_object_deform(brna);
	rna_def_object_explosive(brna);
}

#endif
