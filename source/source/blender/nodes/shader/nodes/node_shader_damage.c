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

/** \file blender/nodes/shader/nodes/node_shader_damage.c
 *  \ingroup shdnodes
 */

#include "node_shader_util.h"

/* **************** DAMAGE ******************** */
/* Mask around the points where the object was hit (game Deformation), in object space. */
static bNodeSocketTemplate sh_node_damage_in[] = {
	{	SOCK_FLOAT, 1, N_("Softness"),  0.5f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	-1, 0, ""	}
};

static bNodeSocketTemplate sh_node_damage_out[] = {
	{	SOCK_FLOAT, 0, N_("Mask"),      0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 0, N_("Strength"),  0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	-1, 0, ""	}
};

static int node_shader_gpu_damage(GPUMaterial *mat, bNode *UNUSED(node), bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	if (GPU_Material_get_type(mat) != GPU_MATERIAL_TYPE_MESH) {
		return 0;
	}
	return GPU_stack_link(mat, "node_damage", in, out,
	                      GPU_material_builtin(mat, GPU_VIEW_POSITION),
	                      GPU_material_builtin(mat, GPU_INVERSE_VIEW_MATRIX),
	                      GPU_material_builtin(mat, GPU_INVERSE_OBJECT_MATRIX));
}

void register_node_type_sh_damage(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_DAMAGE, "Damage", NODE_CLASS_INPUT, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_damage_in, sh_node_damage_out);
	node_type_storage(&ntype, "", NULL, NULL);
	node_type_gpu(&ntype, node_shader_gpu_damage);

	nodeRegisterType(&ntype);
}
