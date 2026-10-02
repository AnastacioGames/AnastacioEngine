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
 * The Original Code is Copyright (C) 2018 Blender Foundation.
 * All rights reserved.
 */

#include "../node_shader_util.h"

/* **************** OUTPUT ******************** */

/* Color, melanin and absorption coefficient default to approximately same brownish hair. */
static bNodeSocketTemplate sh_node_bsdf_hair_principled_in[] = {
	{	SOCK_RGBA,		1, N_("Color"),						0.017513f, 0.005763f, 0.002059f, 1.0f, 0.0f, 1.0f},
	{	SOCK_FLOAT,		1, N_("Melanin"),					0.8f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT,		1, N_("Melanin Redness"),			1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_RGBA,		1, N_("Tint"),						1.0f, 1.0f, 1.0f, 1.0f, 0.0f, 1.0f},
	{	SOCK_VECTOR,	1, N_("Absorption Coefficient"),	0.245531f, 0.52f, 1.365f, 0.0f, 0.0f, 1000.0f},
	{	SOCK_FLOAT,		1, N_("Roughness"),					0.3f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT,		1, N_("Radial Roughness"),			0.3f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT,		1, N_("Coat"),						0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT,		1, N_("IOR"),						1.55f, 0.0f, 0.0f, 0.0f, 0.0f, 1000.0f},
	{	SOCK_FLOAT,		1, N_("Offset"),					2.0f * ((float)M_PI) / 180.f, 0.0f, 0.0f, 0.0f, -M_PI_2, M_PI_2, PROP_ANGLE},
	{	SOCK_FLOAT, 	1, N_("Random Color"),				0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 	1, N_("Random Roughness"),			0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT,		1, N_("Random"),					0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_NONE, SOCK_HIDE_VALUE},
	{	-1, 0, ""	},
};

static bNodeSocketTemplate sh_node_bsdf_hair_principled_out[] = {
	{	SOCK_SHADER, 0, N_("BSDF")},
	{	-1, 0, ""	}
};

/* Initialize the custom Parametrization property to Color. */
static void node_shader_init_hair_principled(bNodeTree *UNUSED(ntree), bNode *node)
{
	node->custom1 = SHD_PRINCIPLED_HAIR_REFLECTANCE;
}

/* Triggers (in)visibility of some sockets when changing Parametrization. */
static void node_shader_update_hair_principled(bNodeTree *UNUSED(ntree), bNode *node)
{
	bNodeSocket *sock;
	int parametrization = node->custom1;

	for (sock = node->inputs.first; sock; sock = sock->next) {
		if (STREQ(sock->name, "Color")) {
			if (parametrization == SHD_PRINCIPLED_HAIR_REFLECTANCE) {
				sock->flag &= ~SOCK_UNAVAIL;
			}
			else {
				sock->flag |= SOCK_UNAVAIL;
			}
		}
		else if (STREQ(sock->name, "Melanin")) {
			if (parametrization == SHD_PRINCIPLED_HAIR_PIGMENT_CONCENTRATION) {
				sock->flag &= ~SOCK_UNAVAIL;
			}
			else {
				sock->flag |= SOCK_UNAVAIL;
			}
		}
		else if (STREQ(sock->name, "Melanin Redness")) {
			if (parametrization == SHD_PRINCIPLED_HAIR_PIGMENT_CONCENTRATION) {
				sock->flag &= ~SOCK_UNAVAIL;
			}
			else {
				sock->flag |= SOCK_UNAVAIL;
			}
		}
		else if (STREQ(sock->name, "Tint")) {
			if (parametrization == SHD_PRINCIPLED_HAIR_PIGMENT_CONCENTRATION) {
				sock->flag &= ~SOCK_UNAVAIL;
			}
			else {
				sock->flag |= SOCK_UNAVAIL;
			}
		}
		else if (STREQ(sock->name, "Absorption Coefficient")) {
			if (parametrization == SHD_PRINCIPLED_HAIR_DIRECT_ABSORPTION) {
				sock->flag &= ~SOCK_UNAVAIL;
			}
			else {
				sock->flag |= SOCK_UNAVAIL;
			}
		}
		else if (STREQ(sock->name, "Random Color")) {
			if (parametrization == SHD_PRINCIPLED_HAIR_PIGMENT_CONCENTRATION) {
				sock->flag &= ~SOCK_UNAVAIL;
			}
			else {
				sock->flag |= SOCK_UNAVAIL;
			}
		}
	}
}

static int node_shader_gpu_bsdf_hair_principled(GPUMaterial *mat, bNode *node, bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	/* No Tangent input: strands radial around the object Z axis, like the Hair and Anisotropic BSDF. */
	GPUNodeLink *tangent;
	float axis = (float)SHD_TANGENT_AXIS_Z;
	GPU_link(mat, "node_tangent", GPU_material_builtin(mat, GPU_VIEW_NORMAL), GPU_attribute(CD_ORCO, ""),
	         GPU_uniform(&axis), GPU_material_builtin(mat, GPU_OBJECT_MATRIX),
	         GPU_material_builtin(mat, GPU_INVERSE_VIEW_MATRIX), &tangent);
	GPU_link(mat, "direction_transform_m4v3", tangent, GPU_material_builtin(mat, GPU_VIEW_MATRIX), &tangent);

	float parametrization = (float)node->custom1;
	float rough = 1.0f;
	GPUNodeLink *env_mirror, *env_diffuse, *env_flag;
	node_shader_gpu_world_env(mat, GPU_uniform(&rough), &env_mirror, &env_diffuse, &env_flag);

	return GPU_stack_link(mat, "node_bsdf_hair_principled", in, out, tangent, GPU_material_builtin(mat, GPU_VIEW_NORMAL),
	                      GPU_material_builtin(mat, GPU_VIEW_POSITION), GPU_uniform(&parametrization),
	                      GPU_material_world_color(mat), env_diffuse, env_flag);
}

/* node type definition */
void register_node_type_sh_bsdf_hair_principled(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_BSDF_HAIR_PRINCIPLED, "Principled Hair BSDF", NODE_CLASS_SHADER, 0);
	node_type_compatibility(&ntype, NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_bsdf_hair_principled_in, sh_node_bsdf_hair_principled_out);
	node_type_size_preset(&ntype, NODE_SIZE_LARGE);
	node_type_init(&ntype, node_shader_init_hair_principled);
	node_type_storage(&ntype, "", NULL, NULL);
	node_type_update(&ntype, node_shader_update_hair_principled, NULL);
	node_type_gpu(&ntype, node_shader_gpu_bsdf_hair_principled);

	nodeRegisterType(&ntype);
}
