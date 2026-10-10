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

/** \file blender/nodes/shader/nodes/node_shader_mapping.c
 *  \ingroup shdnodes
 */

#include "node_shader_util.h"

/* **************** MAPPING  ******************** */
static bNodeSocketTemplate sh_node_mapping_in[] = {
	{SOCK_VECTOR, 1, N_("Vector"), 0.0f, 0.0f, 0.0f, 1.0f, -FLT_MAX, FLT_MAX, PROP_NONE},
	{SOCK_VECTOR, 1, N_("Location"), 0.0f, 0.0f, 0.0f, 1.0f, -FLT_MAX, FLT_MAX, PROP_TRANSLATION},
	{SOCK_VECTOR, 1, N_("Rotation"), 0.0f, 0.0f, 0.0f, 1.0f, -FLT_MAX, FLT_MAX, PROP_EULER},
	{SOCK_VECTOR, 1, N_("Scale"), 1.0f, 1.0f, 1.0f, 1.0f, -FLT_MAX, FLT_MAX, PROP_XYZ},
	{-1, 0, ""}
};

static bNodeSocketTemplate sh_node_mapping_out[] = {
	{	SOCK_VECTOR, 0, N_("Vector")},
	{	-1, 0, ""	}
};

static float mapping_safe_divide(float a, float b)
{
	return (b != 0.0f) ? a / b : 0.0f;
}

/* Versão CPU das funções mapping_* do GLSL: o bake do Blender Internal avalia
 * a árvore pelo exec, sem ele a saída do nó ficava zerada (textura chapada). */
static void node_shader_exec_mapping(void *UNUSED(data), int UNUSED(thread), bNode *node, bNodeExecData *UNUSED(execdata), bNodeStack **in, bNodeStack **out)
{
	float vec[3], loc[3], rot[3], scale[3], mat[3][3], tmp[3];
	int i;

	nodestack_get_vec(vec, SOCK_VECTOR, in[0]);
	nodestack_get_vec(loc, SOCK_VECTOR, in[1]);
	nodestack_get_vec(rot, SOCK_VECTOR, in[2]);
	nodestack_get_vec(scale, SOCK_VECTOR, in[3]);
	eul_to_mat3(mat, rot);

	switch (node->custom1) {
		case NODE_MAPPING_TYPE_POINT:
			mul_v3_v3v3(tmp, vec, scale);
			mul_m3_v3(mat, tmp);
			add_v3_v3v3(out[0]->vec, tmp, loc);
			break;
		case NODE_MAPPING_TYPE_TEXTURE:
			sub_v3_v3v3(tmp, vec, loc);
			mul_transposed_m3_v3(mat, tmp);
			for (i = 0; i < 3; i++)
				out[0]->vec[i] = mapping_safe_divide(tmp[i], scale[i]);
			break;
		case NODE_MAPPING_TYPE_VECTOR:
			mul_v3_v3v3(tmp, vec, scale);
			mul_v3_m3v3(out[0]->vec, mat, tmp);
			break;
		case NODE_MAPPING_TYPE_NORMAL:
			for (i = 0; i < 3; i++)
				tmp[i] = mapping_safe_divide(vec[i], scale[i]);
			mul_v3_m3v3(out[0]->vec, mat, tmp);
			normalize_v3(out[0]->vec);
			break;
	}
}

static int gpu_shader_mapping(GPUMaterial *mat, bNode *node, bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	static const char *names[] = {
      [NODE_MAPPING_TYPE_POINT] = "mapping_point",
      [NODE_MAPPING_TYPE_TEXTURE] = "mapping_texture",
      [NODE_MAPPING_TYPE_VECTOR] = "mapping_vector",
      [NODE_MAPPING_TYPE_NORMAL] = "mapping_normal",
	};

	return GPU_stack_link(mat, names[node->custom1], in, out);
}

static void node_shader_update_mapping(bNodeTree *UNUSED(ntree), bNode *node)
{
  bNodeSocket *sock = nodeFindSocket(node, SOCK_IN, "Location");
  nodeSetSocketAvailability(
      sock, ELEM(node->custom1, NODE_MAPPING_TYPE_POINT, NODE_MAPPING_TYPE_TEXTURE));
}

void register_node_type_sh_mapping(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_MAPPING, "Mapping", NODE_CLASS_OP_VECTOR, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_mapping_in, sh_node_mapping_out);
	node_type_exec(&ntype, NULL, NULL, node_shader_exec_mapping);
	node_type_gpu(&ntype, gpu_shader_mapping);
	node_type_update(&ntype, node_shader_update_mapping, NULL);

	nodeRegisterType(&ntype);
}
