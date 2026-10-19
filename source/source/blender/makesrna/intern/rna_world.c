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

/** \file blender/makesrna/intern/rna_world.c
 *  \ingroup RNA
 */


#include <float.h>
#include <stdlib.h>

#include "RNA_define.h"

#include "rna_internal.h"

#include "DNA_material_types.h"
#include "DNA_property_types.h"
#include "DNA_texture_types.h"
#include "DNA_world_types.h"

#include "WM_types.h"

static const EnumPropertyItem rna_enum_world_sound_module_type_items[] = {
	{WO_SOUND_MODULE_MUSIC, "MUSIC", ICON_PLAY_AUDIO, "Music", "One track at a time, with crossfade and playlist"},
	{WO_SOUND_MODULE_AMBIENT, "AMBIENT", ICON_FORCE_WIND, "Ambient", "Looping layers that play together"},
	{WO_SOUND_MODULE_EFFECTS, "EFFECTS", ICON_MOD_EXPLODE, "Effects",
	 "Sounds the engine plays by itself (explosions, destruction, rain, thunder); every play is a new voice, "
	 "so a sound never cuts the one before"},
	{0, NULL, 0, NULL, NULL}
};

static const EnumPropertyItem rna_enum_world_sound_event_items[] = {
	{WO_SOUND_EVENT_NONE, "NONE", 0, "None", "Played only by name (Range.audio)"},
	{WO_SOUND_EVENT_EXPLOSION_TINY, "EXPLOSION_TINY", 0, "Explosion Tiny", "Explosive with Tiny explosion size"},
	{WO_SOUND_EVENT_EXPLOSION_SMALL, "EXPLOSION_SMALL", 0, "Explosion Small", "Explosive with Small explosion size"},
	{WO_SOUND_EVENT_EXPLOSION_MEDIUM, "EXPLOSION_MEDIUM", 0, "Explosion Medium", "Explosive with Medium explosion size"},
	{WO_SOUND_EVENT_EXPLOSION_LARGE, "EXPLOSION_LARGE", 0, "Explosion Large", "Explosive with Large explosion size"},
	{WO_SOUND_EVENT_EXPLOSION_HUGE, "EXPLOSION_HUGE", 0, "Explosion Huge", "Explosive with Huge explosion size"},
	{WO_SOUND_EVENT_DESTRUCTION_TINY, "DESTRUCTION_TINY", 0, "Destruction Tiny", "Destructible breaking, Tiny Break Effect size"},
	{WO_SOUND_EVENT_DESTRUCTION_SMALL, "DESTRUCTION_SMALL", 0, "Destruction Small", "Destructible breaking, Small Break Effect size"},
	{WO_SOUND_EVENT_DESTRUCTION_MEDIUM, "DESTRUCTION_MEDIUM", 0, "Destruction Medium", "Destructible breaking, Medium Break Effect size"},
	{WO_SOUND_EVENT_DESTRUCTION_LARGE, "DESTRUCTION_LARGE", 0, "Destruction Large", "Destructible breaking, Large Break Effect size"},
	{WO_SOUND_EVENT_DESTRUCTION_HUGE, "DESTRUCTION_HUGE", 0, "Destruction Huge", "Destructible breaking, Huge Break Effect size"},
	{WO_SOUND_EVENT_RAIN, "RAIN", 0, "Rain", "Loops while World > Rain is on"},
	{WO_SOUND_EVENT_THUNDER, "THUNDER", 0, "Thunder", "Each lightning strike; add several Thunder sounds so it doesn't repeat"},
	{0, NULL, 0, NULL, NULL}
};

#ifdef RNA_RUNTIME

#include "MEM_guardedalloc.h"

#include "BLI_listbase.h"
#include "BLI_string.h"

#include "BKE_context.h"
#include "BKE_depsgraph.h"
#include "BKE_main.h"
#include "BKE_report.h"
#include "BKE_texture.h"
#include "BKE_world.h"

#include "RNA_access.h"

#include "ED_node.h"
#include "ED_view3d.h"

#include "WM_api.h"

static PointerRNA rna_World_lighting_get(PointerRNA *ptr)
{
	return rna_pointer_inherit_refine(ptr, &RNA_WorldLighting, ptr->id.data);
}


static PointerRNA rna_World_mist_get(PointerRNA *ptr)
{
	return rna_pointer_inherit_refine(ptr, &RNA_WorldMistSettings, ptr->id.data);
}

static PointerRNA rna_World_weather_get(PointerRNA *ptr)
{
	return rna_pointer_inherit_refine(ptr, &RNA_WorldWeatherSettings, ptr->id.data);
}

static int rna_World_string_properties_skip(CollectionPropertyIterator *UNUSED(iter), void *data)
{
	return ((bProperty *)data)->type != GPROP_STRING;
}

static void rna_World_string_properties_begin(CollectionPropertyIterator *iter, PointerRNA *ptr)
{
	World *wo = (World *)ptr->data;
	rna_iterator_listbase_begin(iter, &wo->prop, rna_World_string_properties_skip);
}

/* World Sound: modules and their sounds are found by name in the game engine, so the setters keep
 * the names unique. */

static WorldSoundModule *rna_World_sound_modules_new(World *wo, const char *name, int type)
{
	WorldSoundModule *module = BKE_world_sound_module_add(wo, name, type);
	WM_main_add_notifier(NC_WORLD, wo);
	return module;
}

static void rna_World_sound_modules_remove(World *wo, ReportList *reports, PointerRNA *module_ptr)
{
	WorldSoundModule *module = module_ptr->data;

	if (BLI_findindex(&wo->sound_modules, module) == -1) {
		BKE_reportf(reports, RPT_ERROR, "Sound module '%s' not in world '%s'", module->name, wo->id.name + 2);
		return;
	}

	BKE_world_sound_module_remove(wo, module);
	RNA_POINTER_INVALIDATE(module_ptr);
	WM_main_add_notifier(NC_WORLD, wo);
}

static void rna_World_sound_modules_move(World *wo, ReportList *reports, int from, int to)
{
	WorldSoundModule *module = BLI_findlink(&wo->sound_modules, from);

	if (module == NULL || to < 0 || to >= BLI_listbase_count(&wo->sound_modules)) {
		BKE_report(reports, RPT_ERROR, "Sound module index out of range");
		return;
	}

	BLI_listbase_link_move(&wo->sound_modules, module, to - from);
	WM_main_add_notifier(NC_WORLD, wo);
}

static WorldSoundEntry *rna_WorldSoundModule_sounds_new(WorldSoundModule *module, const char *name, const char *filepath)
{
	WorldSoundEntry *entry = BKE_world_sound_entry_add(module, name, filepath);
	WM_main_add_notifier(NC_WORLD, NULL);
	return entry;
}

static void rna_WorldSoundModule_sounds_remove(WorldSoundModule *module, ReportList *reports, PointerRNA *entry_ptr)
{
	WorldSoundEntry *entry = entry_ptr->data;

	if (BLI_findindex(&module->sounds, entry) == -1) {
		BKE_reportf(reports, RPT_ERROR, "Sound '%s' not in module '%s'", entry->name, module->name);
		return;
	}

	BKE_world_sound_entry_remove(module, entry);
	RNA_POINTER_INVALIDATE(entry_ptr);
	WM_main_add_notifier(NC_WORLD, NULL);
}

static void rna_WorldSoundModule_sounds_move(WorldSoundModule *module, ReportList *reports, int from, int to)
{
	WorldSoundEntry *entry = BLI_findlink(&module->sounds, from);

	if (entry == NULL || to < 0 || to >= BLI_listbase_count(&module->sounds)) {
		BKE_report(reports, RPT_ERROR, "Sound index out of range");
		return;
	}

	BLI_listbase_link_move(&module->sounds, entry, to - from);
	WM_main_add_notifier(NC_WORLD, NULL);
}

static void rna_WorldSoundModule_name_set(PointerRNA *ptr, const char *value)
{
	World *wo = ptr->id.data;
	WorldSoundModule *module = ptr->data;

	BLI_strncpy_utf8(module->name, value, sizeof(module->name));
	BKE_world_sound_module_unique_name(wo, module);
}

static void rna_WorldSoundEntry_name_set(PointerRNA *ptr, const char *value)
{
	World *wo = ptr->id.data;
	WorldSoundEntry *entry = ptr->data;

	BLI_strncpy_utf8(entry->name, value, sizeof(entry->name));

	for (WorldSoundModule *module = wo->sound_modules.first; module; module = module->next) {
		if (BLI_findindex(&module->sounds, entry) != -1) {
			BKE_world_sound_entry_unique_name(module, entry);
			break;
		}
	}
}

static void rna_World_mtex_begin(CollectionPropertyIterator *iter, PointerRNA *ptr)
{
	World *wo = (World *)ptr->data;
	rna_iterator_array_begin(iter, (void *)wo->mtex, sizeof(MTex *), MAX_MTEX, 0, NULL);
}

static PointerRNA rna_World_active_texture_get(PointerRNA *ptr)
{
	World *wo = (World *)ptr->data;
	Tex *tex;

	tex = give_current_world_texture(wo);
	return rna_pointer_inherit_refine(ptr, &RNA_Texture, tex);
}

static void rna_World_active_texture_set(PointerRNA *ptr, PointerRNA value)
{
	World *wo = (World *)ptr->data;

	set_current_world_texture(wo, value.data);
}

static void rna_World_update(Main *UNUSED(bmain), Scene *UNUSED(scene), PointerRNA *ptr)
{
	World *wo = ptr->id.data;

	DAG_id_tag_update(&wo->id, 0);
	WM_main_add_notifier(NC_WORLD | ND_WORLD, wo);
}

#if 0
static void rna_World_draw_update(Main *UNUSED(bmain), Scene *UNUSED(scene), PointerRNA *ptr)
{
	World *wo = ptr->id.data;

	DAG_id_tag_update(&wo->id, 0);
	WM_main_add_notifier(NC_WORLD | ND_WORLD_DRAW, wo);
}
#endif

static void rna_World_draw_update(Main *bmain, Scene *UNUSED(scene), PointerRNA *ptr)
{
	World *wo = ptr->id.data;

	DAG_id_tag_update(&wo->id, 0);
	WM_main_add_notifier(NC_WORLD | ND_WORLD_DRAW, wo);
	WM_main_add_notifier(NC_OBJECT | ND_DRAW, NULL);

	/* Rain/Clouds speed or the weather toggles themselves may need the
	 * viewport's realtime redraw timer started (or stopped) so the weather
	 * shaders keep animating outside Play/input events. */
	if (bmain->wm.first) {
		ED_view3d_realtime_viewport_update((wmWindowManager *)bmain->wm.first);
	}
}

/* Ripples/Splash > Only in Puddles need the puddles: turning one on turns them on too. */
static void rna_World_ripple_puddle_update(Main *bmain, Scene *scene, PointerRNA *ptr)
{
	World *wo = ptr->id.data;

	if (wo->weather_flag & (WO_WEATHER_RAIN_RIPPLE_PUDDLE | WO_WEATHER_RAIN_SPLASH_PUDDLE)) {
		wo->weather_flag |= WO_WEATHER_RAIN_PUDDLES;
	}
	rna_World_draw_update(bmain, scene, ptr);
}

static bool rna_World_use_sky_moon_get(PointerRNA *ptr)
{
	return ((World *)ptr->data)->moon_enabled > 0.0f;
}

static void rna_World_use_sky_moon_set(PointerRNA *ptr, bool value)
{
	((World *)ptr->data)->moon_enabled = value ? 1.0f : 0.0f;
}

/* Sky Type: one choice over the old Blend/Real/Paper/Atmospheric flag combinations. */
static int rna_World_sky_type_get(PointerRNA *ptr)
{
	short t = ((World *)ptr->data)->skytype;
	if (!(t & WO_SKYBLEND)) return 0;
	if ((t & WO_SKYREAL) && !(t & WO_SKYPAPER)) return (t & WO_SKYATMOSPHERIC) ? 3 : 2;
	return 1;
}

static void rna_World_sky_type_set(PointerRNA *ptr, int value)
{
	World *wo = ptr->data;
	wo->skytype &= ~(WO_SKYBLEND | WO_SKYREAL | WO_SKYATMOSPHERIC);
	if (value >= 2) wo->skytype &= ~WO_SKYPAPER;
	if (value >= 1) wo->skytype |= WO_SKYBLEND;
	if (value >= 2) wo->skytype |= WO_SKYREAL;
	if (value == 3) wo->skytype |= WO_SKYATMOSPHERIC;
}

static void rna_World_use_nodes_update(bContext *C, PointerRNA *ptr)
{
	World *wrld = (World *)ptr->data;

	if (wrld->use_nodes && wrld->nodetree == NULL)
		ED_node_shader_default(C, &wrld->id);

	rna_World_update(CTX_data_main(C), CTX_data_scene(C), ptr);
}

#else

static void rna_def_world_mtex(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	static const EnumPropertyItem texco_items[] = {
		{TEXCO_VIEW, "VIEW", 0, "View", "Use view vector for the texture coordinates"},
		{TEXCO_GLOB, "GLOBAL", 0, "Global", "Use global coordinates for the texture coordinates (interior mist)"},
		{TEXCO_ANGMAP, "ANGMAP", 0, "AngMap", "Use 360 degree angular coordinates, e.g. for spherical light probes"},
		{TEXCO_H_SPHEREMAP, "SPHERE", 0, "Sphere", "For 360 degree panorama sky, spherical mapped, only top half"},
		{TEXCO_EQUIRECTMAP, "EQUIRECT", 0, "Equirectangular", "For 360 degree panorama sky, equirectangular mapping"},
		{TEXCO_H_TUBEMAP, "TUBE", 0, "Tube", "For 360 degree panorama sky, cylindrical mapped, only top half"},
		{TEXCO_OBJECT, "OBJECT", 0, "Object", "Use linked object's coordinates for texture coordinates"},
		{0, NULL, 0, NULL, NULL}
	};

	srna = RNA_def_struct(brna, "WorldTextureSlot", "TextureSlot");
	RNA_def_struct_sdna(srna, "MTex");
	RNA_def_struct_ui_text(srna, "World Texture Slot", "Texture slot for textures in a World data-block");

	/* map to */
	prop = RNA_def_property(srna, "use_map_blend", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "mapto", WOMAP_BLEND);
	RNA_def_property_ui_text(prop, "Blend", "Affect the color progression of the background");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "use_map_horizon", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "mapto", WOMAP_HORIZ);
	RNA_def_property_ui_text(prop, "Horizon", "Affect the color of the horizon");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "use_map_zenith_up", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "mapto", WOMAP_ZENUP);
	RNA_def_property_ui_text(prop, "Zenith Up", "Affect the color of the zenith above");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "use_map_zenith_down", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "mapto", WOMAP_ZENDOWN);
	RNA_def_property_ui_text(prop, "Zenith Down", "Affect the color of the zenith below");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "lod_bias", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "lodbias");
	RNA_def_property_ui_range(prop, -FLT_MAX, FLT_MAX, 10, 3);
	RNA_def_property_ui_text(prop, "Lod Bias", "Amount bias on mipmapping");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "texture_coords", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "texco");
	RNA_def_property_enum_items(prop, texco_items);
	RNA_def_property_ui_text(prop, "Texture Coordinates",
	                         "Texture coordinates used to map the texture onto the background");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "object", PROP_POINTER, PROP_NONE);
	RNA_def_property_pointer_sdna(prop, NULL, "object");
	RNA_def_property_struct_type(prop, "Object");
	RNA_def_property_flag(prop, PROP_EDITABLE);
	RNA_def_property_ui_text(prop, "Object", "Object to use for mapping with Object texture coordinates");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "blend_factor", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "blendfac");
	RNA_def_property_ui_range(prop, 0, 1, 10, 3);
	RNA_def_property_ui_text(prop, "Blend Factor", "Amount texture affects color progression of the background");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "horizon_factor", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "colfac");
	RNA_def_property_ui_range(prop, 0, 1, 10, 3);
	RNA_def_property_ui_text(prop, "Horizon Factor", "Amount texture affects color of the horizon");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "zenith_up_factor", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "zenupfac");
	RNA_def_property_ui_range(prop, 0, 1, 10, 3);
	RNA_def_property_ui_text(prop, "Zenith Up Factor", "Amount texture affects color of the zenith above");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "zenith_down_factor", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "zendownfac");
	RNA_def_property_ui_range(prop, 0, 1, 10, 3);
	RNA_def_property_ui_text(prop, "Zenith Down Factor", "Amount texture affects color of the zenith below");
	RNA_def_property_update(prop, 0, "rna_World_update");
}

static void rna_def_lighting(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	static const EnumPropertyItem blend_mode_items[] = {
		{WO_AOMUL, "MULTIPLY", 0, "Multiply", "Multiply direct lighting with ambient occlusion, darkening the result"},
		{WO_AOADD, "ADD", 0, "Add", "Add light and shadow"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem prop_color_items[] = {
		{WO_AOPLAIN, "PLAIN", 0, "White", "Plain diffuse energy (white.)"},
		{WO_AOSKYCOL, "SKY_COLOR", 0, "Sky Color", "Use horizon and zenith color for diffuse energy"},
		{WO_AOSKYTEX, "SKY_TEXTURE", 0, "Sky Texture", "Does full Sky texture render for diffuse energy"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem prop_sample_method_items[] = {
		{WO_AOSAMP_CONSTANT, "CONSTANT_JITTERED", 0, "Constant Jittered", "Fastest and gives the most noise"},
		{WO_AOSAMP_HALTON, "ADAPTIVE_QMC", 0, "Adaptive QMC", "Fast in high-contrast areas"},
		{WO_AOSAMP_HAMMERSLEY, "CONSTANT_QMC", 0, "Constant QMC", "Best quality"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem prop_gather_method_items[] = {
		{WO_AOGATHER_RAYTRACE, "RAYTRACE", 0, "Raytrace", "Accurate, but slow when noise-free results are required"},
		{WO_AOGATHER_APPROX, "APPROXIMATE", 0, "Approximate", "Inaccurate, but faster and without noise"},
		{0, NULL, 0, NULL, NULL}
	};

	srna = RNA_def_struct(brna, "WorldLighting", NULL);
	RNA_def_struct_sdna(srna, "World");
	RNA_def_struct_nested(brna, srna, "World");
	RNA_def_struct_ui_text(srna, "Lighting", "Lighting for a World data-block");

	/* ambient occlusion */
	prop = RNA_def_property(srna, "use_ambient_occlusion", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "mode", WO_AMB_OCC);
	RNA_def_property_ui_text(prop, "Use Ambient Occlusion",
	                         "Use Ambient Occlusion to add shadowing based on distance between objects");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "ao_factor", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "aoenergy");
	RNA_def_property_range(prop, 0, INT_MAX);
	RNA_def_property_ui_range(prop, 0, 1, 0.1, 2);
	RNA_def_property_ui_text(prop, "Factor", "Factor for ambient occlusion blending");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "ao_blend_type", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "aomix");
	RNA_def_property_enum_items(prop, blend_mode_items);
	RNA_def_property_ui_text(prop, "Blend Mode", "Defines how AO mixes with material shading");
	RNA_def_property_update(prop, 0, "rna_World_update");

	/* environment lighting */
	prop = RNA_def_property(srna, "use_environment_light", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "mode", WO_ENV_LIGHT);
	RNA_def_property_ui_text(prop, "Use Environment Lighting", "Add light coming from the environment");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "environment_energy", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "ao_env_energy");
	RNA_def_property_ui_range(prop, 0, FLT_MAX, 1, 3);
	RNA_def_property_ui_text(prop, "Environment Color", "Defines the strength of environment light");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "environment_color", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "aocolor");
	RNA_def_property_enum_items(prop, prop_color_items);
	RNA_def_property_ui_text(prop, "Environment Color", "Defines where the color of the environment light comes from");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	/* indirect lighting */
	prop = RNA_def_property(srna, "use_indirect_light", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "mode", WO_INDIRECT_LIGHT);
	RNA_def_property_ui_text(prop, "Use Indirect Lighting", "Add indirect light bouncing of surrounding objects");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "indirect_factor", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "ao_indirect_energy");
	RNA_def_property_range(prop, 0, INT_MAX);
	RNA_def_property_ui_range(prop, 0, 1, 0.1, 2);
	RNA_def_property_ui_text(prop, "Indirect Factor", "Factor for how much surrounding objects contribute to light");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "indirect_bounces", PROP_INT, PROP_UNSIGNED);
	RNA_def_property_int_sdna(prop, NULL, "ao_indirect_bounces");
	RNA_def_property_range(prop, 1, SHRT_MAX);
	RNA_def_property_ui_text(prop, "Bounces", "Number of indirect diffuse light bounces");
	RNA_def_property_update(prop, 0, "rna_World_update");

	/* gathering parameters */
	prop = RNA_def_property(srna, "gather_method", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "ao_gather_method");
	RNA_def_property_enum_items(prop, prop_gather_method_items);
	RNA_def_property_ui_text(prop, "Gather Method", "");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "passes", PROP_INT, PROP_NONE);
	RNA_def_property_int_sdna(prop, NULL, "ao_approx_passes");
	RNA_def_property_range(prop, 0, 10);
	RNA_def_property_ui_text(prop, "Passes", "Number of preprocessing passes to reduce over-occlusion");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "distance", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "aodist");
	RNA_def_property_ui_text(prop, "Distance",
	                         "Length of rays, defines how far away other faces give occlusion effect");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "falloff_strength", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "aodistfac");
	RNA_def_property_ui_text(prop, "Strength",
	                         "Attenuation falloff strength, the higher, the less influence distant objects have");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "bias", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "aobias");
	RNA_def_property_range(prop, 0, 0.5);
	RNA_def_property_ui_text(prop, "Bias",
	                         "Bias (in radians) to prevent smoothed faces from showing banding "
	                         "(for Raytrace Constant Jittered)");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "threshold", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "ao_adapt_thresh");
	RNA_def_property_range(prop, 0, 1);
	RNA_def_property_ui_text(prop, "Threshold",
	                         "Samples below this threshold will be considered fully shadowed/unshadowed and skipped "
	                         "(for Raytrace Adaptive QMC)");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "adapt_to_speed", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "ao_adapt_speed_fac");
	RNA_def_property_range(prop, 0, 1);
	RNA_def_property_ui_text(prop, "Adapt To Speed",
	                         "Use the speed vector pass to reduce AO samples in fast moving pixels - "
	                         "higher values result in more aggressive sample reduction "
	                         "(requires Vec pass enabled, for Raytrace Adaptive QMC)");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "error_threshold", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "ao_approx_error");
	RNA_def_property_range(prop, 0.0001, 10);
	RNA_def_property_ui_text(prop, "Error Tolerance", "Low values are slower and higher quality");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "correction", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "ao_approx_correction");
	RNA_def_property_range(prop, 0, 1);
	RNA_def_property_ui_range(prop, 0, 1, 0.1, 2);
	RNA_def_property_ui_text(prop, "Correction", "Ad-hoc correction for over-occlusion due to the approximation");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "use_falloff", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "aomode", WO_AODIST);
	RNA_def_property_ui_text(prop, "Falloff", "Distance will be used to attenuate shadows");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "use_cache", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "aomode", WO_AOCACHE);
	RNA_def_property_ui_text(prop, "Pixel Cache",
	                         "Cache AO results in pixels and interpolate over neighboring pixels for speedup");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "samples", PROP_INT, PROP_NONE);
	RNA_def_property_int_sdna(prop, NULL, "aosamp");
	RNA_def_property_range(prop, 1, 128);
	RNA_def_property_ui_text(prop, "Samples",
	                         "Amount of ray samples. Higher values give smoother results and longer rendering times");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "sample_method", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "ao_samp_method");
	RNA_def_property_enum_items(prop, prop_sample_method_items);
	RNA_def_property_ui_text(prop, "Sample Method", "Method for generating shadow samples (for Raytrace)");
	RNA_def_property_update(prop, 0, "rna_World_update");
}

static void rna_def_world_mist(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	static const EnumPropertyItem falloff_items[] = {
		{0, "QUADRATIC", 0, "Quadratic", "Use quadratic progression"},
		{1, "LINEAR", 0, "Linear", "Use linear progression"},
		{2, "INVERSE_QUADRATIC", 0, "Inverse Quadratic", "Use inverse quadratic progression"},
		{3, "HEIGHT", 0, "Height", "Use height progression"},
		{0, NULL, 0, NULL, NULL}
	};

	static const EnumPropertyItem blend_mist_items[] = {
		{WO_AOMUL, "MIX", 0, "Mix", "Blend mist color and material"},
		{WO_AOADD, "ADD", 0, "Add", "Add mist color to material"},
		{0, NULL, 0, NULL, NULL}
	};

	srna = RNA_def_struct(brna, "WorldMistSettings", NULL);
	RNA_def_struct_sdna(srna, "World");
	RNA_def_struct_nested(brna, srna, "World");
	RNA_def_struct_ui_text(srna, "World Mist", "Mist settings for a World data-block");

	prop = RNA_def_property(srna, "use_mist", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "mode", WO_MIST);
	RNA_def_property_ui_text(prop, "Use Mist", "Occlude objects with the environment color as they are further away");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "intensity", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "misi");
	RNA_def_property_range(prop, 0, 1);
	RNA_def_property_ui_text(prop, "Minimum", "Overall minimum intensity of the mist effect");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "start", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "miststa");
	RNA_def_property_range(prop, -10000, FLT_MAX);
	RNA_def_property_ui_range(prop, -10000, 10000, 10, 2);
	RNA_def_property_ui_text(prop, "Start", "Starting distance of the mist, measured from the camera");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "depth", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "mistdist");
	RNA_def_property_range(prop, 0, FLT_MAX);
	RNA_def_property_ui_range(prop, 0, 10000, 10, 2);
	RNA_def_property_ui_text(prop, "Depth", "Distance over which the mist effect fades in");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "height", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "misthi");
	RNA_def_property_range(prop, 0, 100);
	RNA_def_property_ui_text(prop, "Height", "Control how much mist density decreases with height");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "height_fog", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "mistheight");
	RNA_def_property_range(prop, 0, FLT_MAX);
	RNA_def_property_ui_range(prop, 0, 10000, 10, 2);
	RNA_def_property_ui_text(prop, "Height", "Distance over which the fog effect fades in");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "density_fog", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "mistdensity");
	RNA_def_property_range(prop, 0, FLT_MAX);
	RNA_def_property_ui_range(prop, 0, 10000, 10, 2);
	RNA_def_property_ui_text(prop, "Density", "Distance over which the fog effect fades in");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "falloff", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "mistype");
	RNA_def_property_enum_items(prop, falloff_items);
	RNA_def_property_ui_text(prop, "Falloff", "Type of transition used to fade mist");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "mist_blend_type", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "aomix");
	RNA_def_property_enum_items(prop, blend_mist_items);
	RNA_def_property_ui_text(prop, "Blend Mode", "Defines how mist mixes with material");
	RNA_def_property_update(prop, 0, "rna_World_update");
}

static void rna_def_world_weather(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	static const EnumPropertyItem rain_style_items[] = {
		{WO_RAIN_STYLE_CLASSIC, "CLASSIC", 0, "Classic", "Screen-space rain streaks (cheap, stable look)"},
		{WO_RAIN_STYLE_VOLUMETRIC, "VOLUMETRIC", 0, "Volumetric", "World-space rain streaks marched along the view ray (more depth, costlier)"},
		{0, NULL, 0, NULL, NULL}
	};

	srna = RNA_def_struct(brna, "WorldWeatherSettings", NULL);
	RNA_def_struct_sdna(srna, "World");
	RNA_def_struct_nested(brna, srna, "World");
	RNA_def_struct_ui_text(srna, "World Weather", "Weather settings for a World data-block");

	/* rain */
	prop = RNA_def_property(srna, "use_rain", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_RAIN);
	RNA_def_property_ui_text(prop, "Use Rain", "Render procedural rain streaks and ground ripples");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "show_viewport_rain", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_negative_sdna(prop, NULL, "weather_editor_hide", WO_WEATHER_RAIN);
	RNA_def_property_ui_text(prop, "Render Rain", "Render Rain in Viewport");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "show_viewport_clouds", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_negative_sdna(prop, NULL, "weather_editor_hide", WO_WEATHER_CLOUDS);
	RNA_def_property_ui_text(prop, "Render Clouds", "Render Clouds in Viewport");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	/* sky layers */
	prop = RNA_def_property(srna, "use_sky_layers", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "sky_layer_flag", WO_SKY_LAYERS_ENABLE);
	RNA_def_property_ui_text(prop, "Use Sky Layers",
	                         "Two drifting cloud layers projected on a sky plane, shaded with relief; works together with Clouds");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "show_expanded_sky_layers", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "sky_layer_flag", WO_SKY_LAYERS_EXPANDED);
	RNA_def_property_ui_text(prop, "Expanded", "Set weather effect expanded in the user interface");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "show_viewport_sky_layers", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_negative_sdna(prop, NULL, "sky_layer_flag", WO_SKY_LAYERS_EDITOR_HIDE);
	RNA_def_property_ui_text(prop, "Render Sky Layers", "Render Sky Layers in Viewport");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "sky_layer_coverage", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0, 1.0);
	RNA_def_property_ui_text(prop, "Coverage", "Amount of sky covered by the cloud layers");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "sky_layer_scale", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0001, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.01, 10.0, 1, 3);
	RNA_def_property_ui_text(prop, "Scale", "Scale of the cloud layers on the sky plane");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "sky_layer_speed", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, -FLT_MAX, FLT_MAX);
	RNA_def_property_ui_range(prop, -1.0, 1.0, 1, 3);
	RNA_def_property_ui_text(prop, "Speed", "Speed at which the cloud layers drift");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "sky_layer_color", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_float_sdna(prop, NULL, "sky_layer_color");
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Color", "Color tint of the cloud layers");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "sky_layer_detail", PROP_INT, PROP_NONE);
	RNA_def_property_range(prop, 1, 8);
	RNA_def_property_ui_text(prop, "Detail",
	                         "Noise octaves of the cloud layers: more octaves give finer edges and cost more on the GPU");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "sky_layer_relief", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 3.0f);
	RNA_def_property_ui_range(prop, 0.0f, 2.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Relief",
	                         "Strength of the light and shadow on the cloud layers; 0 turns it off and skips one noise pass");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	/* volumetric clouds (Stage 1 scaffolding: shading achatado, mesmo FBM; raymarch real na Stage 2) */
	{
		static const EnumPropertyItem vcloud_quality_items[] = {
			{0, "LOW", 0, "Low", "Fewer raymarch steps, lower internal resolution"},
			{1, "MEDIUM", 0, "Medium", "Balanced raymarch steps and resolution"},
			{2, "HIGH", 0, "High", "Full raymarch steps and resolution (costly on iGPU)"},
			{0, NULL, 0, NULL, NULL}
		};

		prop = RNA_def_property(srna, "use_volumetric_clouds", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vcloud_flag", WO_VCLOUDS_ENABLE);
		RNA_def_property_ui_text(prop, "Use Volumetric Clouds",
		                         "Third cloud mode (RDR2-style volumetric look); works together with Clouds and Sky Layers");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "show_expanded_vclouds", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vcloud_flag", WO_VCLOUDS_EXPANDED);
		RNA_def_property_ui_text(prop, "Expanded", "Set weather effect expanded in the user interface");
		RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
		RNA_def_property_update(prop, 0, NULL);

		prop = RNA_def_property(srna, "show_viewport_vclouds", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_negative_sdna(prop, NULL, "vcloud_flag", WO_VCLOUDS_EDITOR_HIDE);
		RNA_def_property_ui_text(prop, "Render Volumetric Clouds", "Render Volumetric Clouds in Viewport");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_coverage", PROP_FLOAT, PROP_FACTOR);
		RNA_def_property_range(prop, 0.0, 1.0);
		RNA_def_property_ui_text(prop, "Coverage", "Amount of sky covered by the volumetric cloud layer");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_scale", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, 0.0001, FLT_MAX);
		RNA_def_property_ui_range(prop, 0.01, 10.0, 1, 3);
		RNA_def_property_ui_text(prop, "Scale", "Scale of the base cloud noise");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_speed", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, -FLT_MAX, FLT_MAX);
		RNA_def_property_ui_range(prop, -1.0, 1.0, 1, 3);
		RNA_def_property_ui_text(prop, "Speed", "Speed at which the volumetric cloud layer drifts");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_color", PROP_FLOAT, PROP_COLOR);
		RNA_def_property_float_sdna(prop, NULL, "vcloud_color");
		RNA_def_property_array(prop, 3);
		RNA_def_property_ui_text(prop, "Color", "Color tint of the volumetric clouds");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_altitude", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, -FLT_MAX, FLT_MAX);
		RNA_def_property_ui_range(prop, 0.0, 10000.0, 10, 1);
		RNA_def_property_ui_text(prop, "Altitude", "Base altitude of the volumetric cloud layer");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_thickness", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, 0.0001, FLT_MAX);
		RNA_def_property_ui_range(prop, 1.0, 5000.0, 10, 1);
		RNA_def_property_ui_text(prop, "Thickness", "Vertical thickness of the volumetric cloud layer");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_density", PROP_FLOAT, PROP_FACTOR);
		RNA_def_property_range(prop, 0.0, 1.0);
		RNA_def_property_ui_text(prop, "Density", "Overall density of the volumetric clouds");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_detail_scale", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, 0.0001, FLT_MAX);
		RNA_def_property_ui_range(prop, 0.01, 10.0, 1, 3);
		RNA_def_property_ui_text(prop, "Detail Scale", "Scale of the fine detail noise layered on top of the base shape");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_silver_intensity", PROP_FLOAT, PROP_FACTOR);
		RNA_def_property_range(prop, 0.0, 1.0);
		RNA_def_property_ui_text(prop, "Silver Intensity", "Intensity of the silver lining seen around the sun (Stage 2 will add real light scattering)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_quality", PROP_ENUM, PROP_NONE);
		RNA_def_property_enum_sdna(prop, NULL, "vcloud_quality");
		RNA_def_property_enum_items(prop, vcloud_quality_items);
		RNA_def_property_ui_text(prop, "Quality", "Raymarch step count and internal resolution preset (Stage 2)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_shadow_enable", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vcloud_flag", WO_VCLOUDS_SHADOW_ENABLE);
		RNA_def_property_ui_text(prop, "Cast Shadow on Terrain", "Project an approximate shadow from the volumetric clouds onto the terrain (Stage 2)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vcloud_shadow_strength", PROP_FLOAT, PROP_FACTOR);
		RNA_def_property_range(prop, 0.0, 1.0);
		RNA_def_property_ui_text(prop, "Shadow Strength", "Strength of the volumetric cloud shadow on the terrain (Stage 2)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");
	}

	/* Volumetric Fog */
	{
		static const EnumPropertyItem vfog_quality_items[] = {
			{0, "LOW", 0, "Low", "Analytic fog without raymarch, 2 lamps, no light shafts (cheapest, iGPU)"},
			{1, "MEDIUM", 0, "Medium", "12 raymarch steps, 4 lamps, Spot light shafts"},
			{2, "HIGH", 0, "High", "24 raymarch steps, 8 lamps, Spot light shafts"},
			{0, NULL, 0, NULL, NULL}
		};

		prop = RNA_def_property(srna, "use_volumetric_fog", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vfog_flag", WO_VFOG_ENABLE);
		RNA_def_property_ui_text(prop, "Use Volumetric Fog", "Height fog with noise, lit by the sun and tinted by nearby Point/Spot lamps");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "show_expanded_vfog", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vfog_flag", WO_VFOG_EXPANDED);
		RNA_def_property_ui_text(prop, "Expanded", "Set weather effect expanded in the user interface");
		RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
		RNA_def_property_update(prop, 0, NULL);

		prop = RNA_def_property(srna, "show_viewport_vfog", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_negative_sdna(prop, NULL, "vfog_flag", WO_VFOG_EDITOR_HIDE);
		RNA_def_property_ui_text(prop, "Render Volumetric Fog", "Render Volumetric Fog in Viewport");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_use_lamps", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vfog_flag", WO_VFOG_LAMPS);
		RNA_def_property_ui_text(prop, "Lamps", "Nearby Point and Spot lamps light and tint the fog with their color");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_use_shafts", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vfog_flag", WO_VFOG_SHAFTS);
		RNA_def_property_ui_text(prop, "Light Shafts", "Spot lamps with shadow cast light shafts in the fog (Medium/High)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_volumes_only", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vfog_flag", WO_VFOG_VOLUMES_ONLY);
		RNA_def_property_ui_text(prop, "Only Fog Volumes", "Fog exists only inside objects with the game property fog_volume (box of the object, like the default cube)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_density", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, 0.0f, FLT_MAX);
		RNA_def_property_ui_range(prop, 0.0f, 1.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Density", "Fog density at the base height");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_base", PROP_FLOAT, PROP_DISTANCE);
		RNA_def_property_range(prop, -FLT_MAX, FLT_MAX);
		RNA_def_property_ui_range(prop, -100.0f, 1000.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Base Height", "Height where the fog starts thinning out");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_falloff", PROP_FLOAT, PROP_DISTANCE);
		RNA_def_property_range(prop, 0.01f, FLT_MAX);
		RNA_def_property_ui_range(prop, 0.1f, 500.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Height Falloff", "Height over which the fog thins out above the base");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_distance", PROP_FLOAT, PROP_DISTANCE);
		RNA_def_property_range(prop, 1.0f, FLT_MAX);
		RNA_def_property_ui_range(prop, 10.0f, 5000.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Max Distance", "Fog is only computed up to this distance from the camera (also the sky)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_noise_scale", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, 0.0001f, FLT_MAX);
		RNA_def_property_ui_range(prop, 0.01f, 2.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Noise Scale", "Size of the fog puffs (smaller value = bigger puffs)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_noise_amount", PROP_FLOAT, PROP_FACTOR);
		RNA_def_property_range(prop, 0.0f, 1.0f);
		RNA_def_property_ui_range(prop, 0.0f, 1.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Noise", "How patchy the fog is; 0 is uniform and cheaper");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_speed", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, -FLT_MAX, FLT_MAX);
		RNA_def_property_ui_range(prop, -2.0f, 2.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Speed", "Speed at which the fog drifts");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_anisotropy", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, -0.9f, 0.9f);
		RNA_def_property_ui_range(prop, 0.0f, 0.9f, 10, 3);
		RNA_def_property_ui_text(prop, "Anisotropy", "How much brighter the fog is when looking toward a light (0 = same in every direction)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_color", PROP_FLOAT, PROP_COLOR);
		RNA_def_property_float_sdna(prop, NULL, "vfog_color");
		RNA_def_property_array(prop, 3);
		RNA_def_property_ui_text(prop, "Color", "Color of the fog");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_light_intensity", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, 0.0f, FLT_MAX);
		RNA_def_property_ui_range(prop, 0.0f, 10.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Lamp Intensity", "How strongly the Point/Spot lamps light the fog");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_sun_intensity", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, 0.0f, FLT_MAX);
		RNA_def_property_ui_range(prop, 0.0f, 5.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Sun Intensity", "How strongly the sun lights the fog");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_ambient", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, 0.0f, FLT_MAX);
		RNA_def_property_ui_range(prop, 0.0f, 2.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Ambient", "Light from the sky (horizon color) on the fog, keeps it from going black");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_edge", PROP_FLOAT, PROP_FACTOR);
		RNA_def_property_range(prop, 0.0f, 1.0f);
		RNA_def_property_ui_range(prop, 0.0f, 1.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Volume Edge", "Softness of the Fog Volume edges");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_shaft_intensity", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, 0.0f, FLT_MAX);
		RNA_def_property_ui_range(prop, 0.0f, 4.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Shaft Intensity", "Strength of the shadowed Spot light shafts");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_dust", PROP_FLOAT, PROP_FACTOR);
		RNA_def_property_range(prop, 0.0f, 1.0f);
		RNA_def_property_ui_text(prop, "Dust",
		                         "Dust motes floating in the light beams, seen only where the sun or a lamp reaches "
		                         "(0 = none)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_quality", PROP_ENUM, PROP_NONE);
		RNA_def_property_enum_sdna(prop, NULL, "vfog_quality");
		RNA_def_property_enum_items(prop, vfog_quality_items);
		RNA_def_property_ui_text(prop, "Quality", "Raymarch steps, lamp count and light shafts preset");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_max_lights", PROP_INT, PROP_NONE);
		RNA_def_property_range(prop, 1, 8);
		RNA_def_property_ui_text(prop, "Max Lamps", "Most lamps that tint the fog at once (the strongest near the camera); the quality preset can lower it");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		static EnumPropertyItem vfog_lod_items[] = {
			{1, "FULL", 0, "Full", "The fog is computed for every pixel (best edges, slowest)"},
			{0, "HALF", 0, "Half", "The fog is computed at half resolution and upscaled following the depth (about 4x faster)"},
			{2, "QUARTER", 0, "Quarter", "The fog is computed at a quarter of the resolution (fastest, softer edges)"},
			{0, NULL, 0, NULL, NULL}
		};
		prop = RNA_def_property(srna, "vfog_resolution", PROP_ENUM, PROP_NONE);
		RNA_def_property_enum_sdna(prop, NULL, "vfog_lod");
		RNA_def_property_enum_items(prop, vfog_lod_items);
		RNA_def_property_ui_text(prop, "Resolution", "Resolution of the fog computation in the game; restart the game to apply");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_use_sun_shafts", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vfog_flag", WO_VFOG_SUN_SHAFTS);
		RNA_def_property_ui_text(prop, "Sun Shafts", "A Sun with shadow casts light shafts (god rays) in the fog (Medium/High)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_use_layer", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vfog_flag", WO_VFOG_LAYER);
		RNA_def_property_ui_text(prop, "Layer", "Dense fog up to Base Height that fills the valleys, its top waving by Falloff");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_use_reach_clouds", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vfog_flag", WO_VFOG_REACH_CLOUDS);
		RNA_def_property_ui_text(prop, "Reach Clouds", "A thin haze rises from the fog up to the base of the clouds (Volumetric Clouds altitude, else 300 m)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_use_wind", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vfog_flag", WO_VFOG_WIND);
		RNA_def_property_ui_text(prop, "Wind", "The fog is carried by the wind (strength from Rain Wind)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_wind_direction", PROP_FLOAT, PROP_NONE);
		RNA_def_property_float_sdna(prop, NULL, "vfog_wind_dir");
		RNA_def_property_range(prop, -360.0f, 360.0f);
		RNA_def_property_ui_text(prop, "Wind Direction", "Heading the wind blows toward, in degrees around Z (0 = +X)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_use_time_of_day", PROP_BOOLEAN, PROP_NONE);
		RNA_def_property_boolean_sdna(prop, NULL, "vfog_flag", WO_VFOG_TIME_OF_DAY);
		RNA_def_property_ui_text(prop, "Morning Fog", "Thicker, lower fog at dawn following the World Property sun_hour (peak at 6h)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");

		prop = RNA_def_property(srna, "vfog_morning_boost", PROP_FLOAT, PROP_NONE);
		RNA_def_property_range(prop, 0.001f, FLT_MAX);
		RNA_def_property_ui_range(prop, 0.0f, 10.0f, 10, 3);
		RNA_def_property_ui_text(prop, "Morning Boost", "How much denser the fog gets at dawn (2 = three times the density at 6h)");
		RNA_def_property_update(prop, 0, "rna_World_draw_update");
	}

	prop = RNA_def_property(srna, "show_viewport_lensflare", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_negative_sdna(prop, NULL, "weather_editor_hide", WO_WEATHER_LENSFLARE);
	RNA_def_property_ui_text(prop, "Render Lens Flare", "Render Lens Flare in Viewport");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "show_viewport_fog", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_negative_sdna(prop, NULL, "weather_editor_hide", WO_WEATHER_FOG);
	RNA_def_property_ui_text(prop, "Render Fog", "Render Fog in Viewport");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "show_expanded_fog", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_expand_flag", WO_WEATHER_FOG);
	RNA_def_property_ui_text(prop, "Expanded", "Set weather effect expanded in the user interface");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "show_expanded_rain", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_expand_flag", WO_WEATHER_RAIN);
	RNA_def_property_ui_text(prop, "Expanded", "Set weather effect expanded in the user interface");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "show_expanded_rain_droplets", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_expand_flag", WO_WEATHER_RAIN_DROPLETS);
	RNA_def_property_ui_text(prop, "Expanded", "Show the Droplets rain settings");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "show_expanded_rain_ripples", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_expand_flag", WO_WEATHER_RAIN_RIPPLE);
	RNA_def_property_ui_text(prop, "Expanded", "Show the Ripples rain settings");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "show_expanded_rain_splash", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_expand_flag", WO_WEATHER_RAIN_SPLASH);
	RNA_def_property_ui_text(prop, "Expanded", "Show the Splash rain settings");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "show_expanded_rain_puddles", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_expand_flag", WO_WEATHER_RAIN_PUDDLES);
	RNA_def_property_ui_text(prop, "Expanded", "Show the Puddles rain settings");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "show_expanded_rain_aura", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_expand_flag", WO_WEATHER_RAIN_AURA);
	RNA_def_property_ui_text(prop, "Expanded", "Show the Aura rain settings");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "show_expanded_rain_lightning", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_expand_flag", WO_WEATHER_RAIN_LIGHTNING);
	RNA_def_property_ui_text(prop, "Expanded", "Show the Lightning rain settings");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "rain_style", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "rain_style");
	RNA_def_property_enum_items(prop, rain_style_items);
	RNA_def_property_ui_text(prop, "Rain Style", "Rendering technique used for the falling rain streaks");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_intensity", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0, 1.0);
	RNA_def_property_ui_range(prop, 0.0, 1.0, 1, 3);
	RNA_def_property_ui_text(prop, "Rain Intensity", "Overall brightness/strength of the rain effect");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_density", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.1f, 10.0f);
	RNA_def_property_ui_range(prop, 0.25f, 10.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Rain Density", "Number of falling rain streaks (1.0 is the classic default)");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "use_rain_droplets", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_RAIN_DROPLETS);
	RNA_def_property_ui_text(prop, "Droplets", "Render the falling rain streaks/droplets layer");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "use_rain_ripple", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_RAIN_RIPPLE);
	RNA_def_property_ui_text(prop, "Ripples", "Render rain ripples on ground puddles; only on objects with the game property ripples_effect when any object has it");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_speed", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "rain_speed");
	RNA_def_property_range(prop, 0.0, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.0, 20.0, 1, 2);
	RNA_def_property_ui_text(prop, "Fall Speed", "Speed of falling rain streaks");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_wind", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, -1.0, 1.0);
	RNA_def_property_ui_text(prop, "Wind", "Horizontal wind offset applied to rain streaks");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_darken", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0, 1.0);
	RNA_def_property_ui_text(prop, "Darken", "Darken the scene to simulate overcast rainy lighting");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_ripple_intensity", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "rain_ripple");
	RNA_def_property_range(prop, 0.0, 1.0);
	RNA_def_property_ui_text(prop, "Ripple Intensity", "Intensity of rain ripples on ground puddles");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_ripple_distance", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.0f, 1000.0f);
	RNA_def_property_ui_range(prop, 1.0f, 100.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Ripple Radius", "Maximum distance from the active camera where ripples are drawn");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_ripple_min_up", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Ripple Upward Surface", "Minimum upward-facing normal for ripples; 0.5 accepts slopes up to 60 degrees and rejects vertical sides");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_ripple_normal", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.01f, 10.0f);
	RNA_def_property_ui_range(prop, 0.1f, 4.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Ripple Normal", "Strength of the ripple normal: surface bending, refraction and highlights of the waves");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "use_rain_ripple_puddle_only", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_RAIN_RIPPLE_PUDDLE);
	RNA_def_property_ui_text(prop, "Only in Puddles", "Ripples only inside the puddle water (turns Puddles on)");
	RNA_def_property_update(prop, 0, "rna_World_ripple_puddle_update");

	prop = RNA_def_property(srna, "rain_ripple_size", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.3f, 6.0f);
	RNA_def_property_ui_range(prop, 0.3f, 6.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Ripple Size", "Size of the ripple rings");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_ripple_rate", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.1f, 6.0f);
	RNA_def_property_ui_range(prop, 0.1f, 6.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Ripple Rate", "Ripples per surface cell per second");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_color", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_float_sdna(prop, NULL, "rain_color");
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Rain Color", "Color tint of the rain streaks");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_streak_width", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.1f, 2.0f);
	RNA_def_property_ui_range(prop, 0.1f, 2.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Streak Width", "Width of the Classic rain streaks in pixels (1.0 = 2 px at 1080p, lower is thinner)");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_velocity", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 2.0f);
	RNA_def_property_ui_range(prop, 0.0f, 2.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Velocity Influence", "How much the camera motion bends the rain: the drops come at the camera as it moves, like a car driving into the rain (0 = off)");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_velocity_stretch", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 3.0f);
	RNA_def_property_ui_range(prop, 0.0f, 3.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Velocity Stretch", "How much the streaks stretch with the speed (1 = default)");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_velocity_max", PROP_FLOAT, PROP_VELOCITY);
	RNA_def_property_range(prop, 1.0f, 500.0f);
	RNA_def_property_ui_range(prop, 1.0f, 200.0f, 100, 1);
	RNA_def_property_ui_text(prop, "Max Speed", "Camera speed (m/s) where the rain reaches the full speed effect (Classic style)");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "use_rain_splash", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_RAIN_SPLASH);
	RNA_def_property_ui_text(prop, "Splash", "Drops bouncing up when the rain hits upward-facing surfaces and edges; only on objects with the game property splash_effect when any object has it");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_splash_size", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.3f, 6.0f);
	RNA_def_property_ui_range(prop, 0.3f, 6.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Splash Size", "Size of the splash drops");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_splash_rate", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.1f, 6.0f);
	RNA_def_property_ui_range(prop, 0.1f, 6.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Splash Rate", "Splashes per surface cell per second");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_splash_intensity", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 4.0f);
	RNA_def_property_ui_range(prop, 0.0f, 2.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Splash Intensity", "Brightness of the splash drops");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "use_rain_splash_puddle_only", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_RAIN_SPLASH_PUDDLE);
	RNA_def_property_ui_text(prop, "Only in Puddles", "Splash drops only inside the puddle water (turns Puddles on)");
	RNA_def_property_update(prop, 0, "rna_World_ripple_puddle_update");

	prop = RNA_def_property(srna, "rain_splash_normal", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 10.0f);
	RNA_def_property_ui_range(prop, 0.0f, 4.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Splash Normal", "Strength of the splash drops normal: refraction of what is behind and sky highlights");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_splash_distance", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.0f, 1000.0f);
	RNA_def_property_ui_range(prop, 1.0f, 100.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Splash Distance", "Maximum distance from the active camera where splashes are drawn");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_splash_min_up", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Splash Upward Surface", "Minimum upward-facing normal for splashes; 0.7 accepts slopes up to about 45 degrees");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "use_rain_puddles", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_RAIN_PUDDLES);
	RNA_def_property_ui_text(prop, "Puddles", "Water puddles on upward-facing surfaces, reflecting the sky; only on objects with the game property puddles_effect when any object has it");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "use_rain_puddle_ssr", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_RAIN_PUDDLE_SSR);
	RNA_def_property_ui_text(prop, "Puddle SSR", "Puddles reflect the visible scene (screen-space reflection), falling back to the sky where the ray leaves the screen; costs more GPU");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_puddle_amount", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Puddle Amount", "How much of the ground is covered by puddles (0 = dry, 1 = flooded); animate it to make the puddles grow or dry");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_puddle_size", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.1f, 100.0f);
	RNA_def_property_ui_range(prop, 0.5f, 20.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Puddle Size", "Typical size of the puddles in meters");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_puddle_darkness", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Puddle Darkness", "How much the wet ground around and under the puddles gets darker");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_puddle_reflection", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Puddle Reflection", "Strength of the sky reflection on the puddles (stronger at grazing angles)");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_puddle_distance", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.0f, 1000.0f);
	RNA_def_property_ui_range(prop, 1.0f, 200.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Puddle Distance", "Maximum distance from the active camera where puddles are drawn");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_puddle_min_up", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Puddle Upward Surface", "Minimum upward-facing normal for puddles; 0.9 keeps them on nearly flat ground");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "use_rain_aura", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_RAIN_AURA);
	RNA_def_property_ui_text(prop, "Aura", "Manga-style short spray strokes on the upper silhouette of the objects with the aura property (every nearby object when none has it)");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_aura_property", PROP_STRING, PROP_NONE);
	RNA_def_property_string_sdna(prop, NULL, "rain_aura_prop");
	RNA_def_property_ui_text(prop, "Aura Property", "Game property (True) that marks the objects receiving the aura; when no object has it, every nearby object gets the aura");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	static const EnumPropertyItem rain_aura_style_items[] = {
		{WO_RAIN_AURA_STATIC, "STATIC", 0, "Static", "Still manga strokes that pop in and out"},
		{WO_RAIN_AURA_ANIMATED, "ANIMATED", 0, "Animated", "Drops that leave the outline and travel a longer path"},
		{0, NULL, 0, NULL, NULL}
	};
	prop = RNA_def_property(srna, "rain_aura_style", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "rain_aura_style");
	RNA_def_property_enum_items(prop, rain_aura_style_items);
	RNA_def_property_ui_text(prop, "Aura Style", "How the aura strokes move");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_aura_size", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.3f, 5.0f);
	RNA_def_property_ui_range(prop, 0.3f, 5.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Aura Size", "Size of the aura strokes");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_aura_rate", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.1f, 3.0f);
	RNA_def_property_ui_range(prop, 0.1f, 3.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Aura Amount", "Amount of aura strokes");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_aura_intensity", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 4.0f);
	RNA_def_property_ui_range(prop, 0.0f, 2.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Aura Intensity", "Brightness of the aura strokes");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_aura_distance", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 0.0f, 1000.0f);
	RNA_def_property_ui_range(prop, 1.0f, 100.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Aura Distance", "Maximum distance from the active camera for objects with aura");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "use_rain_lightning", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_RAIN_LIGHTNING);
	RNA_def_property_ui_text(prop, "Lightning", "Branching lightning bolts far in front of the camera with a flickering flash");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "use_rain_sound", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_negative_sdna(prop, NULL, "weather_sound_mute", WO_WEATHER_RAIN);
	RNA_def_property_ui_text(prop, "Rain Sound", "Loop the Rain sound of World Sound > Effects while it rains");

	prop = RNA_def_property(srna, "use_rain_lightning_sound", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_negative_sdna(prop, NULL, "weather_sound_mute", WO_WEATHER_RAIN_LIGHTNING);
	RNA_def_property_ui_text(prop, "Thunder Sound", "Play a Thunder sound of World Sound > Effects after each strike");

	prop = RNA_def_property(srna, "use_rain_lightning_side", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_RAIN_LIGHTNING_SIDE);
	RNA_def_property_ui_text(prop, "Sideways Bolts", "Some bolts run sideways from cloud to cloud instead of only down to the ground");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_lightning_rate", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 60.0f);
	RNA_def_property_ui_range(prop, 0.0f, 30.0f, 10, 1);
	RNA_def_property_ui_text(prop, "Lightning Rate", "Automatic strikes per minute (0 = only from Python, world.strikeLightning())");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_lightning_intensity", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 4.0f);
	RNA_def_property_ui_range(prop, 0.0f, 2.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Lightning Intensity", "Brightness of the flash and of the bolt");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_lightning_distance", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_range(prop, 5.0f, 2000.0f);
	RNA_def_property_ui_range(prop, 20.0f, 300.0f, 10, 1);
	RNA_def_property_ui_text(prop, "Lightning Distance", "Average distance of the bolts from the camera (their height follows it)");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "rain_lightning_width", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.1f, 5.0f);
	RNA_def_property_ui_range(prop, 0.2f, 3.0f, 1, 2);
	RNA_def_property_ui_text(prop, "Bolt Width", "Thickness of the bolt and of its glow");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	/* clouds */
	prop = RNA_def_property(srna, "use_clouds", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_CLOUDS);
	RNA_def_property_ui_text(prop, "Use Clouds", "Render procedural clouds in the sky");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "show_expanded_clouds", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_expand_flag", WO_WEATHER_CLOUDS);
	RNA_def_property_ui_text(prop, "Expanded", "Set weather effect expanded in the user interface");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "cloud_coverage", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0, 1.0);
	RNA_def_property_ui_text(prop, "Coverage", "Amount of sky covered by clouds");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "cloud_scale", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0001, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.01, 10.0, 1, 3);
	RNA_def_property_ui_text(prop, "Scale", "Scale of the cloud noise pattern");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "cloud_speed", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, -FLT_MAX, FLT_MAX);
	RNA_def_property_ui_range(prop, -1.0, 1.0, 1, 3);
	RNA_def_property_ui_text(prop, "Speed", "Speed at which clouds drift across the sky");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "cloud_color", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_float_sdna(prop, NULL, "cloud_color");
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Cloud Color", "Color tint of the clouds");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "cloud_detail", PROP_INT, PROP_NONE);
	RNA_def_property_range(prop, 1, 8);
	RNA_def_property_ui_text(prop, "Detail",
	                         "Noise octaves of the clouds: more octaves give finer edges and cost more on the GPU");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	/* earthquake */
	prop = RNA_def_property(srna, "use_earthquake", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_EARTHQUAKE);
	RNA_def_property_ui_text(prop, "Use Earthquake", "Shake the scene gravity to simulate an earthquake while playing");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "show_expanded_earthquake", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_expand_flag", WO_WEATHER_EARTHQUAKE);
	RNA_def_property_ui_text(prop, "Expanded", "Set weather effect expanded in the user interface");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "earthquake_level", PROP_INT, PROP_NONE);
	RNA_def_property_range(prop, 0, 5);
	RNA_def_property_ui_text(prop, "Level", "Earthquake intensity, from 0 (off) to 5 (extreme); drives the gravity shake while playing");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	static const EnumPropertyItem earthquake_mode_items[] = {
		{WO_EARTHQUAKE_HORIZONTAL, "HORIZONTAL", 0, "Horizontal", "Shake the ground sideways (X/Y)"},
		{WO_EARTHQUAKE_VERTICAL, "VERTICAL", 0, "Vertical", "Shake the ground up and down (Z)"},
		{WO_EARTHQUAKE_BOTH, "BOTH", 0, "Both", "Shake the ground sideways and vertically"},
		{0, NULL, 0, NULL, NULL}
	};

	prop = RNA_def_property(srna, "earthquake_mode", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "earthquake_mode");
	RNA_def_property_enum_items(prop, earthquake_mode_items);
	RNA_def_property_ui_text(prop, "Direction", "Direction of the earthquake ground shake");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "earthquake_scale", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.1f, 5.0f);
	RNA_def_property_ui_range(prop, 0.1f, 5.0f, 0.05, 2);
	RNA_def_property_ui_text(prop, "Scale", "Multiplier of the earthquake ground shake strength (1 = default for the chosen Level)");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "earthquake_camera", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 2.0f);
	RNA_def_property_ui_range(prop, 0.0f, 2.0f, 0.05, 2);
	RNA_def_property_ui_text(prop, "Camera Shake Scale", "Camera tremor during the earthquake, from 0 (off) to 2 (strong); scales with Level");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	/* lens flare */
	prop = RNA_def_property(srna, "use_lens_flare", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_flag", WO_WEATHER_LENSFLARE);
	RNA_def_property_ui_text(prop, "Use Lens Flare", "Render a procedural lens flare from a sun object");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "show_expanded_lensflare", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "weather_expand_flag", WO_WEATHER_LENSFLARE);
	RNA_def_property_ui_text(prop, "Expanded", "Set weather effect expanded in the user interface");
	RNA_def_property_ui_icon(prop, ICON_RIGHTARROW, 1);
	RNA_def_property_update(prop, 0, NULL);

	prop = RNA_def_property(srna, "sun_object_name", PROP_STRING, PROP_NONE);
	RNA_def_property_string_sdna(prop, NULL, "sun_object_name");
	RNA_def_property_ui_text(prop, "Sun Object", "Name of the object used as the lens flare's sun source");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "flare_scale", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.0, 5.0, 1, 2);
	RNA_def_property_ui_text(prop, "Scale", "Scale of the lens flare");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "flare_intensity", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0, FLT_MAX);
	RNA_def_property_ui_range(prop, 0.0, 2.0, 1, 2);
	RNA_def_property_ui_text(prop, "Intensity", "Intensity of the lens flare");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");
}

static void rna_def_world_sound_entries(BlenderRNA *brna, PropertyRNA *cprop)
{
	StructRNA *srna;
	FunctionRNA *func;
	PropertyRNA *parm;

	RNA_def_property_srna(cprop, "WorldSoundEntries");
	srna = RNA_def_struct(brna, "WorldSoundEntries", NULL);
	RNA_def_struct_sdna(srna, "WorldSoundModule");
	RNA_def_struct_ui_text(srna, "World Sound Entries", "Sounds of a World Sound module");

	func = RNA_def_function(srna, "new", "rna_WorldSoundModule_sounds_new");
	RNA_def_function_ui_description(func, "Add a sound to the module");
	parm = RNA_def_string(func, "name", "Sound", 64, "Name", "Name the game plays the sound by");
	RNA_def_parameter_flags(parm, 0, PARM_REQUIRED);
	RNA_def_string_file_path(func, "filepath", NULL, 1024, "File Path", "Audio file");
	parm = RNA_def_pointer(func, "sound", "WorldSoundEntry", "", "The newly created sound");
	RNA_def_function_return(func, parm);

	func = RNA_def_function(srna, "remove", "rna_WorldSoundModule_sounds_remove");
	RNA_def_function_ui_description(func, "Remove a sound from the module");
	RNA_def_function_flag(func, FUNC_USE_REPORTS);
	parm = RNA_def_pointer(func, "sound", "WorldSoundEntry", "", "The sound to remove");
	RNA_def_parameter_flags(parm, PROP_NEVER_NULL, PARM_REQUIRED | PARM_RNAPTR);
	RNA_def_parameter_clear_flags(parm, PROP_THICK_WRAP, 0);

	func = RNA_def_function(srna, "move", "rna_WorldSoundModule_sounds_move");
	RNA_def_function_ui_description(func, "Move a sound to another position of the playlist");
	RNA_def_function_flag(func, FUNC_USE_REPORTS);
	parm = RNA_def_int(func, "from_index", 0, 0, INT_MAX, "From", "Index of the sound to move", 0, 10000);
	RNA_def_parameter_flags(parm, 0, PARM_REQUIRED);
	parm = RNA_def_int(func, "to_index", 0, 0, INT_MAX, "To", "Target index", 0, 10000);
	RNA_def_parameter_flags(parm, 0, PARM_REQUIRED);
}

static void rna_def_world_sound_modules(BlenderRNA *brna, PropertyRNA *cprop)
{
	StructRNA *srna;
	FunctionRNA *func;
	PropertyRNA *parm;

	RNA_def_property_srna(cprop, "WorldSoundModules");
	srna = RNA_def_struct(brna, "WorldSoundModules", NULL);
	RNA_def_struct_sdna(srna, "World");
	RNA_def_struct_ui_text(srna, "World Sound Modules", "World Sound modules of a World");

	func = RNA_def_function(srna, "new", "rna_World_sound_modules_new");
	RNA_def_function_ui_description(func, "Add a World Sound module");
	parm = RNA_def_string(func, "name", "Module", 64, "Name", "Name the game controls the module by");
	RNA_def_parameter_flags(parm, 0, PARM_REQUIRED);
	RNA_def_enum(func, "type", rna_enum_world_sound_module_type_items, WO_SOUND_MODULE_MUSIC, "Type", "");
	parm = RNA_def_pointer(func, "module", "WorldSoundModule", "", "The newly created module");
	RNA_def_function_return(func, parm);

	func = RNA_def_function(srna, "remove", "rna_World_sound_modules_remove");
	RNA_def_function_ui_description(func, "Remove a World Sound module and its sounds");
	RNA_def_function_flag(func, FUNC_USE_REPORTS);
	parm = RNA_def_pointer(func, "module", "WorldSoundModule", "", "The module to remove");
	RNA_def_parameter_flags(parm, PROP_NEVER_NULL, PARM_REQUIRED | PARM_RNAPTR);
	RNA_def_parameter_clear_flags(parm, PROP_THICK_WRAP, 0);

	func = RNA_def_function(srna, "move", "rna_World_sound_modules_move");
	RNA_def_function_ui_description(func, "Move a module to another position");
	RNA_def_function_flag(func, FUNC_USE_REPORTS);
	parm = RNA_def_int(func, "from_index", 0, 0, INT_MAX, "From", "Index of the module to move", 0, 10000);
	RNA_def_parameter_flags(parm, 0, PARM_REQUIRED);
	parm = RNA_def_int(func, "to_index", 0, 0, INT_MAX, "To", "Target index", 0, 10000);
	RNA_def_parameter_flags(parm, 0, PARM_REQUIRED);
}

static void rna_def_world_sound(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	srna = RNA_def_struct(brna, "WorldSoundEntry", NULL);
	RNA_def_struct_sdna(srna, "WorldSoundEntry");
	RNA_def_struct_ui_text(srna, "World Sound Entry", "One audio file of a World Sound module");
	RNA_def_struct_ui_icon(srna, ICON_SOUND);

	prop = RNA_def_property(srna, "name", PROP_STRING, PROP_NONE);
	RNA_def_property_string_funcs(prop, NULL, NULL, "rna_WorldSoundEntry_name_set");
	RNA_def_property_ui_text(prop, "Name", "Name the game plays the sound by");
	RNA_def_struct_name_property(srna, prop);
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "filepath", PROP_STRING, PROP_FILEPATH);
	RNA_def_property_ui_text(prop, "File Path", "Audio file, relative to the .range when it starts with //");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "volume", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Volume", "Volume of this sound, multiplied by the volume of its module");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "pitch", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.1f, 4.0f);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Pitch", "Playback speed of this sound (1 is the original)");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "show_expanded", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", WO_SOUND_EXPANDED);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Expanded", "Show the settings of this sound");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "event", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_items(prop, rna_enum_world_sound_event_items);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Event",
	                         "What makes the engine play this sound (Effects modules). Sounds with the same event "
	                         "are variations picked at random");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	srna = RNA_def_struct(brna, "WorldSoundModule", NULL);
	RNA_def_struct_sdna(srna, "WorldSoundModule");
	RNA_def_struct_ui_text(srna, "World Sound Module",
	                       "One kind of game sound (music, ambient) with its own volume and sound list");
	RNA_def_struct_ui_icon(srna, ICON_SOUND);

	prop = RNA_def_property(srna, "name", PROP_STRING, PROP_NONE);
	RNA_def_property_string_funcs(prop, NULL, NULL, "rna_WorldSoundModule_name_set");
	RNA_def_property_ui_text(prop, "Name", "Name the game controls the module by");
	RNA_def_struct_name_property(srna, prop);
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "type", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_items(prop, rna_enum_world_sound_module_type_items);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Type", "How the module plays its sounds");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "volume", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Volume", "Volume of every sound of the module");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "fade_time", PROP_FLOAT, PROP_NONE);
	RNA_def_property_range(prop, 0.0f, 60.0f);
	RNA_def_property_ui_range(prop, 0.0f, 10.0f, 10, 2);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Fade Time", "Seconds a sound takes to fade in and out, and to cross to the next track");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "use_autoplay", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", WO_SOUND_AUTOPLAY);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Play on Start", "Start playing as soon as a scene using this World is loaded");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "use_shuffle", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", WO_SOUND_SHUFFLE);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Shuffle", "Play the tracks in random order");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "use_loop", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", WO_SOUND_LOOP);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Loop", "Start over after the last track");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "mute", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", WO_SOUND_MUTE);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Mute", "Silence the module");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "use_reverb_areas", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", WO_SOUND_USE_REVERB);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Use Reverb Areas",
	                         "Give the sounds of the module the echo of the Reverb Area the camera is in");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "show_expanded", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "flag", WO_SOUND_EXPANDED);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Expanded", "Show the settings and the sounds of the module");
	RNA_def_property_update(prop, NC_WORLD, NULL);

	prop = RNA_def_property(srna, "sounds", PROP_COLLECTION, PROP_NONE);
	RNA_def_property_collection_sdna(prop, NULL, "sounds", NULL);
	RNA_def_property_struct_type(prop, "WorldSoundEntry");
	RNA_def_property_ui_text(prop, "Sounds", "Audio files of the module");
	rna_def_world_sound_entries(brna, prop);

	prop = RNA_def_property(srna, "active_sound_index", PROP_INT, PROP_UNSIGNED);
	RNA_def_property_int_sdna(prop, NULL, "active_sound");
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Active Sound Index", "");
}

void RNA_def_world(BlenderRNA *brna)
{
	StructRNA *srna;
	PropertyRNA *prop;

	srna = RNA_def_struct(brna, "World", "ID");
	RNA_def_struct_ui_text(srna, "World",
	                       "World data-block describing the environment and ambient lighting of a scene");
	RNA_def_struct_ui_icon(srna, ICON_WORLD_DATA);

	rna_def_animdata_common(srna);
	rna_def_mtex_common(brna, srna, "rna_World_mtex_begin", "rna_World_active_texture_get",
	                    "rna_World_active_texture_set", NULL, "WorldTextureSlot", "WorldTextureSlots",
	                    "rna_World_update", "rna_World_update");

	/* colors */
	prop = RNA_def_property(srna, "horizon_color", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_float_sdna(prop, NULL, "horr");
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Horizon Color", "Color at the horizon");
	/* RNA_def_property_update(prop, 0, "rna_World_update"); */
	/* render-only uses this */
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "zenith_color", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_float_sdna(prop, NULL, "zenr");
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Zenith Color", "Color at the zenith");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "nadir_color", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_float_sdna(prop, NULL, "nadr");
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Nadir Color", "Color at the nadir");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	prop = RNA_def_property(srna, "ambient_color", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_float_sdna(prop, NULL, "ambr");
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Ambient Color", "Ambient color of the world");
	RNA_def_property_update(prop, 0, "rna_World_draw_update");

	/* exp, range */
	prop = RNA_def_property(srna, "exposure", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "exp");
	RNA_def_property_range(prop, 0.0, 1.0);
	RNA_def_property_ui_text(prop, "Exposure", "Amount of exponential color correction for light");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "color_range", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "range");
	RNA_def_property_range(prop, 0.2, 5.0);
	RNA_def_property_ui_text(prop, "Range", "The color range that will be mapped to 0-1");
	RNA_def_property_update(prop, 0, "rna_World_update");

	/* sun_size, turbidity, ground */
	prop = RNA_def_property(srna, "sun_size", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_range(prop, 0.0, 0.08);
	RNA_def_property_ui_range(prop, 0.0, 0.08, 0.001, 4);
	RNA_def_property_ui_text(prop, "Sun Size", "Sun Size");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "use_sky_moon", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_funcs(prop, "rna_World_use_sky_moon_get", "rna_World_use_sky_moon_set");
	RNA_def_property_ui_text(prop, "Moon", "Render a visual moon opposite the World Sun without lighting the scene");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "moon_size", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "moon_size");
	RNA_def_property_range(prop, 0.001f, 0.1f);
	RNA_def_property_ui_text(prop, "Moon Size", "Angular size of the visual moon");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "moon_brightness", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "moon_brightness");
	RNA_def_property_range(prop, 0.0f, 1.0f);
	RNA_def_property_ui_text(prop, "Moon Brightness", "Brightness of the moon disc and its short halo");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "ground_color", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "ground");
	RNA_def_property_range(prop, 0.0, 1.0);
	RNA_def_property_ui_text(prop, "Ground Color", "Distance to ground");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "sky_turbidity", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "turbidity");
	RNA_def_property_range(prop, 0.0, 1.0);
	RNA_def_property_ui_text(prop, "Turbidity", "Atmospheric turbidity");
	RNA_def_property_update(prop, 0, "rna_World_update");

	/* sky type */
	prop = RNA_def_property(srna, "use_sky_blend", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "skytype", WO_SKYBLEND);
	RNA_def_property_ui_text(prop, "Blend Sky", "Render background with natural progression from horizon to zenith");
	RNA_def_property_update(prop, NC_WORLD | ND_WORLD_DRAW, "rna_World_update");

	prop = RNA_def_property(srna, "use_sky_paper", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "skytype", WO_SKYPAPER);
	RNA_def_property_ui_text(prop, "Paper Sky", "Flatten blend or texture coordinates");
	RNA_def_property_update(prop, NC_WORLD | ND_WORLD_DRAW, "rna_World_update");

	prop = RNA_def_property(srna, "use_sky_real", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "skytype", WO_SKYREAL);
	RNA_def_property_ui_text(prop, "Real Sky", "Render background with a real horizon, relative to the camera angle");
	RNA_def_property_update(prop, NC_WORLD | ND_WORLD_DRAW, "rna_World_update");

	prop = RNA_def_property(srna, "use_sky_stars", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "skytype", WO_SKYATMOSPHERIC_STARS);
	RNA_def_property_ui_text(prop, "Render Stars", "Render stars");
	RNA_def_property_update(prop, NC_WORLD | ND_WORLD_DRAW, "rna_World_update");

	static EnumPropertyItem star_style_items[] = {
		{WO_STARS_SIMPLE, "SIMPLE", 0, "Simple", "Uniform field of small stars"},
		{WO_STARS_REALISTIC, "REALISTIC", 0, "Realistic",
		 "Stars with varied brightness and color, the Milky Way and the real constellations"},
		{WO_STARS_CONSTELLATIONS, "CONSTELLATIONS", 0, "Constellations",
		 "Realistic sky with a brighter Milky Way and the constellation stars highlighted"},
		{0, NULL, 0, NULL, NULL}
	};
	prop = RNA_def_property(srna, "star_style", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "star_style");
	RNA_def_property_enum_items(prop, star_style_items);
	RNA_def_property_ui_text(prop, "Star Style", "How the night sky stars are drawn");
	RNA_def_property_update(prop, NC_WORLD | ND_WORLD_DRAW, "rna_World_update");

	prop = RNA_def_property(srna, "use_sky_aurora", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "aurora_flag", WO_AURORA_ENABLE);
	RNA_def_property_ui_text(prop, "Aurora", "Draw an animated aurora in the night sky");
	RNA_def_property_update(prop, NC_WORLD | ND_WORLD_DRAW, "rna_World_draw_update");

	static EnumPropertyItem aurora_colors_items[] = {
		{WO_AURORA_GREEN, "GREEN", 0, "Green", "Green curtains, the most common aurora"},
		{WO_AURORA_CLASSIC, "CLASSIC", 0, "Green and Purple", "Green base fading to purple and red at the top"},
		{WO_AURORA_RAINBOW, "SHIFTING", 0, "Shifting", "Colors slowly shift over time and along the curtains"},
		{0, NULL, 0, NULL, NULL}
	};
	prop = RNA_def_property(srna, "aurora_colors", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_sdna(prop, NULL, "aurora_colors");
	RNA_def_property_enum_items(prop, aurora_colors_items);
	RNA_def_property_ui_text(prop, "Aurora Colors", "Color scheme of the aurora");
	RNA_def_property_update(prop, NC_WORLD | ND_WORLD_DRAW, "rna_World_update");

	prop = RNA_def_property(srna, "use_sky_atmospheric", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "skytype", WO_SKYATMOSPHERIC);
	RNA_def_property_ui_text(prop, "Atmospheric Sky", "Render background with a realistic sky");
	RNA_def_property_update(prop, NC_WORLD | ND_WORLD_DRAW, "rna_World_update");

	static const EnumPropertyItem sky_type_items[] = {
		{0, "FLAT", 0, "Flat", "Horizon color only"},
		{1, "GRADIENT", 0, "Gradient", "Blend from horizon to zenith color"},
		{2, "PROCEDURAL", 0, "Procedural", "Simple sky lit by the World Sun, with turbidity and ground"},
		{3, "ATMOSPHERIC", 0, "Atmospheric", "Physical sky: Rayleigh and Mie scattering of the World Sun light"},
		{0, NULL, 0, NULL, NULL}
	};
	prop = RNA_def_property(srna, "sky_type", PROP_ENUM, PROP_NONE);
	RNA_def_property_enum_items(prop, sky_type_items);
	RNA_def_property_enum_funcs(prop, "rna_World_sky_type_get", "rna_World_sky_type_set", NULL);
	RNA_def_property_ui_text(prop, "Sky Type", "How the game draws the World background");
	RNA_def_property_update(prop, NC_WORLD | ND_WORLD_DRAW, "rna_World_update");

	prop = RNA_def_property(srna, "atmosphere_intensity", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "atmo_intensity");
	RNA_def_property_range(prop, 0.0f, 1000.0f);
	RNA_def_property_ui_range(prop, 0.0f, 100.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Intensity", "Brightness of the atmospheric sky; the sun lamp energy does not change it");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "atmosphere_rayleigh_color", PROP_FLOAT, PROP_COLOR);
	RNA_def_property_float_sdna(prop, NULL, "atmo_rayleigh_col");
	RNA_def_property_array(prop, 3);
	RNA_def_property_ui_text(prop, "Air Color", "Color scattered by the air (Rayleigh): blue on Earth; the sunset gets the opposite color");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "atmosphere_rayleigh_density", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "atmo_rayleigh_density");
	RNA_def_property_range(prop, 0.0f, 20.0f);
	RNA_def_property_ui_range(prop, 0.0f, 5.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Air Density", "Amount of air (1 = Earth); more air gives a deeper blue and a redder sunset");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "atmosphere_mie_density", PROP_FLOAT, PROP_NONE);
	RNA_def_property_float_sdna(prop, NULL, "atmo_mie_density");
	RNA_def_property_range(prop, 0.0f, 50.0f);
	RNA_def_property_ui_range(prop, 0.0f, 10.0f, 10, 2);
	RNA_def_property_ui_text(prop, "Haze", "Dust and humidity (Mie, 1 = Earth); more haze gives a whiter sky and a bigger glow around the sun");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "atmosphere_mie_direction", PROP_FLOAT, PROP_FACTOR);
	RNA_def_property_float_sdna(prop, NULL, "atmo_mie_g");
	RNA_def_property_range(prop, 0.0f, 0.99f);
	RNA_def_property_ui_text(prop, "Sun Glow", "How much the haze concentrates the light around the sun");
	RNA_def_property_update(prop, 0, "rna_World_update");

	prop = RNA_def_property(srna, "atmosphere_altitude", PROP_FLOAT, PROP_DISTANCE);
	RNA_def_property_float_sdna(prop, NULL, "atmo_altitude");
	RNA_def_property_range(prop, 1.0f, 60000.0f);
	RNA_def_property_ui_range(prop, 1.0f, 20000.0f, 100, 0);
	RNA_def_property_ui_text(prop, "Altitude", "Height of the viewer in the atmosphere, in meters; high up the sky gets darker");
	RNA_def_property_update(prop, 0, "rna_World_update");

	/* nested structs */
	prop = RNA_def_property(srna, "light_settings", PROP_POINTER, PROP_NONE);
	RNA_def_property_flag(prop, PROP_NEVER_NULL);
	RNA_def_property_struct_type(prop, "WorldLighting");
	RNA_def_property_pointer_funcs(prop, "rna_World_lighting_get", NULL, NULL, NULL);
	RNA_def_property_ui_text(prop, "Lighting", "World lighting settings");

	prop = RNA_def_property(srna, "mist_settings", PROP_POINTER, PROP_NONE);
	RNA_def_property_flag(prop, PROP_NEVER_NULL);
	RNA_def_property_struct_type(prop, "WorldMistSettings");
	RNA_def_property_pointer_funcs(prop, "rna_World_mist_get", NULL, NULL, NULL);
	RNA_def_property_ui_text(prop, "Mist", "World mist settings");

	prop = RNA_def_property(srna, "weather_settings", PROP_POINTER, PROP_NONE);
	RNA_def_property_flag(prop, PROP_NEVER_NULL);
	RNA_def_property_struct_type(prop, "WorldWeatherSettings");
	RNA_def_property_pointer_funcs(prop, "rna_World_weather_get", NULL, NULL, NULL);
	RNA_def_property_ui_text(prop, "Weather", "World weather settings");

	/* nodes */
	prop = RNA_def_property(srna, "node_tree", PROP_POINTER, PROP_NONE);
	RNA_def_property_pointer_sdna(prop, NULL, "nodetree");
	RNA_def_property_ui_text(prop, "Node Tree", "Node tree for node based worlds");

	prop = RNA_def_property(srna, "use_nodes", PROP_BOOLEAN, PROP_NONE);
	RNA_def_property_boolean_sdna(prop, NULL, "use_nodes", 1);
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_flag(prop, PROP_CONTEXT_UPDATE);
	RNA_def_property_ui_text(prop, "Use Nodes", "Use shader nodes to render the world");
	RNA_def_property_update(prop, 0, "rna_World_use_nodes_update");

	/* game engine: properties shared by all objects through the World */
	prop = RNA_def_property(srna, "properties", PROP_COLLECTION, PROP_NONE);
	RNA_def_property_collection_sdna(prop, NULL, "prop", NULL);
	RNA_def_property_struct_type(prop, "GameProperty"); /* rna_property.c */
	RNA_def_property_ui_text(prop, "Properties", "Game engine properties shared by all objects through the World");

	prop = RNA_def_property(srna, "string_properties", PROP_COLLECTION, PROP_NONE);
	RNA_def_property_collection_funcs(prop, "rna_World_string_properties_begin", "rna_iterator_listbase_next",
	                                  "rna_iterator_listbase_end", "rna_iterator_listbase_get", NULL, NULL, NULL, NULL);
	RNA_def_property_struct_type(prop, "GameProperty");
	RNA_def_property_ui_text(prop, "String Properties", "Game engine string properties shared through the World");

	/* game engine: World Sound */
	prop = RNA_def_property(srna, "sound_modules", PROP_COLLECTION, PROP_NONE);
	RNA_def_property_collection_sdna(prop, NULL, "sound_modules", NULL);
	RNA_def_property_struct_type(prop, "WorldSoundModule");
	RNA_def_property_ui_text(prop, "Sound Modules", "World Sound modules: music and ambient sounds of the game");
	rna_def_world_sound_modules(brna, prop);

	prop = RNA_def_property(srna, "active_sound_module_index", PROP_INT, PROP_UNSIGNED);
	RNA_def_property_int_sdna(prop, NULL, "active_sound_module");
	RNA_def_property_clear_flag(prop, PROP_ANIMATABLE);
	RNA_def_property_ui_text(prop, "Active Sound Module Index", "");

	rna_def_world_sound(brna);
	rna_def_lighting(brna);
	rna_def_world_mist(brna);
	rna_def_world_weather(brna);
	rna_def_world_mtex(brna);
}

#endif
