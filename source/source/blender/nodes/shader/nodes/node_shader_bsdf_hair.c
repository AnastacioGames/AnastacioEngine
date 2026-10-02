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
 * The Original Code is Copyright (C) 2005 Blender Foundation.
 * All rights reserved.
 */

#include "../node_shader_util.h"

/* **************** OUTPUT ******************** */

static bNodeSocketTemplate sh_node_bsdf_hair_in[] = {
	{	SOCK_RGBA,  1, N_("Color"),			0.8f, 0.8f, 0.8f, 1.0f, 0.0f, 1.0f},
	{	SOCK_FLOAT, 1, N_("Offset"),		0.0f, 0.0f, 0.0f, 0.0f, -M_PI_2, M_PI_2, PROP_ANGLE},
	{	SOCK_FLOAT, 1, N_("RoughnessU"),	0.1f, 0.1f, 0.1f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("RoughnessV"),	1.0f, 1.0f, 1.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_VECTOR, 1, N_("Tangent"),		0.0f, 0.0f, 0.0f, 1.0f, -1.0f, 1.0f, PROP_NONE, SOCK_HIDE_VALUE},
	{	-1, 0, ""	},
};

static bNodeSocketTemplate sh_node_bsdf_hair_out[] = {
	{	SOCK_SHADER, 0, N_("BSDF")},
	{	-1, 0, ""	}
};

static int node_shader_gpu_bsdf_hair(GPUMaterial *mat, bNode *node, bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	/* Unlinked tangent: radial around the object Z axis, like the Anisotropic BSDF. */
	if (!in[4].link) {
		float axis = (float)SHD_TANGENT_AXIS_Z;
		GPU_link(mat, "node_tangent", GPU_material_builtin(mat, GPU_VIEW_NORMAL), GPU_attribute(CD_ORCO, ""),
		         GPU_uniform(&axis), GPU_material_builtin(mat, GPU_OBJECT_MATRIX),
		         GPU_material_builtin(mat, GPU_INVERSE_VIEW_MATRIX), &in[4].link);
	}
	GPU_link(mat, "direction_transform_m4v3", in[4].link, GPU_material_builtin(mat, GPU_VIEW_MATRIX), &in[4].link);

	float transmission = (node->custom1 == SHD_HAIR_TRANSMISSION) ? 1.0f : 0.0f;
	float rough = 1.0f;
	GPUNodeLink *env_mirror, *env_diffuse, *env_flag;
	node_shader_gpu_world_env(mat, GPU_uniform(&rough), &env_mirror, &env_diffuse, &env_flag);

	return GPU_stack_link(mat, "node_bsdf_hair", in, out, GPU_material_builtin(mat, GPU_VIEW_NORMAL),
	                      GPU_material_builtin(mat, GPU_VIEW_POSITION), GPU_uniform(&transmission),
	                      GPU_material_world_color(mat), env_diffuse, env_flag);
}

/* node type definition */
void register_node_type_sh_bsdf_hair(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_BSDF_HAIR, "Hair BSDF", NODE_CLASS_SHADER, 0);
	node_type_compatibility(&ntype, NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_bsdf_hair_in, sh_node_bsdf_hair_out);
	node_type_size(&ntype, 150, 60, 200);
	node_type_init(&ntype, NULL);
	node_type_storage(&ntype, "", NULL, NULL);
	node_type_gpu(&ntype, node_shader_gpu_bsdf_hair);

	nodeRegisterType(&ntype);
}
