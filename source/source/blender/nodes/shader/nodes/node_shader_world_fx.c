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

/** \file blender/nodes/shader/nodes/node_shader_world_fx.c
 *  \ingroup shdnodes
 *
 * World-only configuration nodes for the screen-space post-processing filters that already
 * exist in the runtime (RAS_2DFilterData::BuildInFilters, KX_2DFilterManager::EnsureBloomFilters/
 * EnsureSSRFilters). These nodes carry no GPU dataflow: they are not linked to the World Output
 * and have no node_type_gpu callback. They only hold input socket default values that are read
 * directly off the World's node tree when the scene is converted (see KX_Scene.cpp), exactly like
 * World.cloud_coverage/World.rain_intensity are read off World DNA for the Weather effects. Scene
 * > Scene FX (scenefx_settings) is still the primary/legacy way to set these values; a Bloom/SSR
 * node in the World tree overrides it when present and enabled, see KX_Scene.cpp.
 */

#include "node_shader_util.h"

/* **************** BLOOM (World FX) ******************** */

static bNodeSocketTemplate sh_node_world_bloom_fx_in[] = {
	{	SOCK_BOOLEAN, 1, N_("Enable"),    0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_NONE},
	{	SOCK_FLOAT,   1, N_("Threshold"), 0.75f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT,   1, N_("Intensity"), 2.0f, 0.0f, 0.0f, 0.0f, 0.0f, 10.0f, PROP_NONE},
	{	-1, 0, ""	}
};

void register_node_type_sh_world_bloom_fx(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_WORLD_BLOOM_FX, "Bloom", NODE_CLASS_OUTPUT, 0);
	node_type_compatibility(&ntype, NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_world_bloom_fx_in, NULL);
	node_type_storage(&ntype, "", NULL, NULL);
	/* No node_type_gpu: this node is never linked to the World Output, it is only read by
	 * KX_Scene when the scene is converted (RAS_2DFilterData::BuildInFilters.useBloom/
	 * bloom_threshold/bloom_intensity). */

	nodeRegisterType(&ntype);
}

/* **************** SCREEN SPACE REFLECTIONS (World FX) ******************** */

static bNodeSocketTemplate sh_node_world_ssr_fx_in[] = {
	{	SOCK_BOOLEAN, 1, N_("Enable"),       0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_NONE},
	{	SOCK_INT,     1, N_("Max Steps"),    16.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1024.0f, PROP_NONE},
	{	SOCK_INT,     1, N_("Lod"),           1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 8.0f, PROP_NONE},
	{	SOCK_FLOAT,   1, N_("Bias"),          3.0f, 0.0f, 0.0f, 0.0f, 0.0f, 10.0f, PROP_NONE},
	{	SOCK_FLOAT,   1, N_("Max Distance"), 100.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1000.0f, PROP_NONE},
	{	-1, 0, ""	}
};

void register_node_type_sh_world_ssr_fx(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_WORLD_SSR_FX, "Screen Space Reflections", NODE_CLASS_OUTPUT, 0);
	node_type_compatibility(&ntype, NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_world_ssr_fx_in, NULL);
	node_type_storage(&ntype, "", NULL, NULL);
	/* No node_type_gpu: see the Bloom node above. Read by KX_Scene into BuildInFilters.useSSR/
	 * ssr_step_max/ssr_lod/ssr_bias/ssr_max_distance. SSR reflects whatever the G-buffer carries
	 * for roughness/metallic, so it works out of the box with Principled/PBR materials; a GLSL
	 * Script material that does not write those G-buffer channels will not reflect correctly
	 * (pre-existing limitation of the SSR filter itself, not of this node). */

	nodeRegisterType(&ntype);
}
