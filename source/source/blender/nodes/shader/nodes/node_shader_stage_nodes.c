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

/** \file blender/nodes/shader/nodes/node_shader_stage_nodes.c
 *  \ingroup shdnodes
 *
 * Game engine nodes for the vertex and geometry stages of a material:
 * - Vertex Offset, Wind and Wave give a mesh space offset, linked to the Material Output
 *   "Vertex Offset" they run in the vertex shader (elsewhere they give zero).
 * - Fur Shells and Outline turn on the generated geometry stage (layers pushed along the normal,
 *   inverted hull); Shell Layer reads which layer a pixel belongs to.
 * - Camera Distance works in both stages (LOD, fading).
 */

#include "node_shader_util.h"

/* **************** VERTEX OFFSET ******************** */

static bNodeSocketTemplate sh_node_vertex_offset_in[] = {
	{	SOCK_FLOAT, 1, N_("Height"),     0.0f, 0.0f, 0.0f, 0.0f, -10000.0f, 10000.0f, PROP_NONE},
	{	SOCK_FLOAT, 1, N_("Scale"),      1.0f, 0.0f, 0.0f, 0.0f, -10000.0f, 10000.0f, PROP_NONE},
	{	SOCK_VECTOR, 1, N_("Direction"), 0.0f, 0.0f, 1.0f, 0.0f, -1.0f, 1.0f, PROP_NONE, SOCK_HIDE_VALUE},
	{	-1, 0, ""	}
};

static bNodeSocketTemplate sh_node_vertex_offset_out[] = {
	{	SOCK_VECTOR, 0, N_("Offset")},
	{	-1, 0, ""	}
};

static int node_shader_gpu_vertex_offset(GPUMaterial *mat, bNode *UNUSED(node), bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	/* Without a Direction the vertex moves along its normal. */
	if (in[2].hasinput && in[2].link) {
		return GPU_stack_link(mat, "node_vertex_offset", in, out);
	}
	return GPU_stack_link(mat, "node_vertex_offset_normal", in, out);
}

void register_node_type_sh_vertex_offset(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_VERTEX_OFFSET, "Vertex Offset", NODE_CLASS_OP_VECTOR, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_vertex_offset_in, sh_node_vertex_offset_out);
	node_type_gpu(&ntype, node_shader_gpu_vertex_offset);

	nodeRegisterType(&ntype);
}

/* **************** WIND ******************** */

static bNodeSocketTemplate sh_node_vertex_wind_in[] = {
	{	SOCK_FLOAT, 1, N_("Strength"),   0.1f, 0.0f, 0.0f, 0.0f, 0.0f, 100.0f, PROP_NONE},
	{	SOCK_FLOAT, 1, N_("Speed"),      1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 100.0f, PROP_NONE},
	{	SOCK_FLOAT, 1, N_("Scale"),      1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1000.0f, PROP_NONE},
	{	SOCK_FLOAT, 1, N_("Anchor"),     0.0f, 0.0f, 0.0f, 0.0f, -10000.0f, 10000.0f, PROP_DISTANCE},
	{	SOCK_VECTOR, 1, N_("Direction"), 1.0f, 0.0f, 0.0f, 0.0f, -1.0f, 1.0f, PROP_DIRECTION},
	{	-1, 0, ""	}
};

static bNodeSocketTemplate sh_node_vertex_offset_only_out[] = {
	{	SOCK_VECTOR, 0, N_("Offset")},
	{	-1, 0, ""	}
};

static int node_shader_gpu_vertex_wind(GPUMaterial *mat, bNode *UNUSED(node), bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	return GPU_stack_link(mat, "node_vertex_wind", in, out, GPU_material_builtin(mat, GPU_TIME));
}

void register_node_type_sh_vertex_wind(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_VERTEX_WIND, "Wind", NODE_CLASS_OP_VECTOR, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_vertex_wind_in, sh_node_vertex_offset_only_out);
	node_type_gpu(&ntype, node_shader_gpu_vertex_wind);

	nodeRegisterType(&ntype);
}

/* **************** WAVE ******************** */

static bNodeSocketTemplate sh_node_vertex_wave_in[] = {
	{	SOCK_FLOAT, 1, N_("Amplitude"),  0.1f, 0.0f, 0.0f, 0.0f, -100.0f, 100.0f, PROP_DISTANCE},
	{	SOCK_FLOAT, 1, N_("Wavelength"), 2.0f, 0.0f, 0.0f, 0.0f, 0.001f, 10000.0f, PROP_DISTANCE},
	{	SOCK_FLOAT, 1, N_("Speed"),      1.0f, 0.0f, 0.0f, 0.0f, -100.0f, 100.0f, PROP_NONE},
	{	SOCK_VECTOR, 1, N_("Direction"), 1.0f, 0.0f, 0.0f, 0.0f, -1.0f, 1.0f, PROP_DIRECTION},
	{	-1, 0, ""	}
};

static int node_shader_gpu_vertex_wave(GPUMaterial *mat, bNode *UNUSED(node), bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	return GPU_stack_link(mat, "node_vertex_wave", in, out, GPU_material_builtin(mat, GPU_TIME));
}

void register_node_type_sh_vertex_wave(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_VERTEX_WAVE, "Wave", NODE_CLASS_OP_VECTOR, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_vertex_wave_in, sh_node_vertex_offset_only_out);
	node_type_gpu(&ntype, node_shader_gpu_vertex_wave);

	nodeRegisterType(&ntype);
}

/* **************** CAMERA DISTANCE ******************** */

static bNodeSocketTemplate sh_node_camera_distance_out[] = {
	{	SOCK_FLOAT, 0, N_("Distance")},
	{	-1, 0, ""	}
};

static int node_shader_gpu_camera_distance(GPUMaterial *mat, bNode *UNUSED(node), bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	return GPU_stack_link(mat, "node_camera_distance", in, out, GPU_material_builtin(mat, GPU_VIEW_POSITION));
}

void register_node_type_sh_camera_distance(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_CAMERA_DISTANCE, "Camera Distance", NODE_CLASS_INPUT, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, NULL, sh_node_camera_distance_out);
	node_type_gpu(&ntype, node_shader_gpu_camera_distance);

	nodeRegisterType(&ntype);
}

/* **************** SHELL LAYER ******************** */

static bNodeSocketTemplate sh_node_shell_layer_out[] = {
	{	SOCK_FLOAT, 0, N_("Layer"),   0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 0, N_("Outline"), 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	-1, 0, ""	}
};

static int node_shader_gpu_shell_layer(GPUMaterial *mat, bNode *UNUSED(node), bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	GPUNodeLink *layer;
	GPU_link(mat, "node_shell_layer", &layer);
	return GPU_stack_link(mat, "node_shell_layer_info", in, out, layer);
}

void register_node_type_sh_shell_layer(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_SHELL_LAYER, "Shell Layer", NODE_CLASS_INPUT, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, NULL, sh_node_shell_layer_out);
	node_type_gpu(&ntype, node_shader_gpu_shell_layer);

	nodeRegisterType(&ntype);
}

/* **************** FUR SHELLS ******************** */

/* Length and Layers are read when the shader is generated (the geometry stage is built for them). */
static bNodeSocketTemplate sh_node_fur_shells_in[] = {
	{	SOCK_FLOAT, 1, N_("Length"),  0.05f, 0.0f, 0.0f, 0.0f, 0.0f, 100.0f, PROP_DISTANCE},
	{	SOCK_FLOAT, 1, N_("Layers"),  8.0f, 0.0f, 0.0f, 0.0f, 2.0f, 32.0f, PROP_NONE},
	{	SOCK_FLOAT, 1, N_("Density"), 200.0f, 0.0f, 0.0f, 0.0f, 1.0f, 100000.0f, PROP_NONE},
	{	SOCK_VECTOR, 1, N_("Vector"), 0.0f, 0.0f, 0.0f, 0.0f, -10000.0f, 10000.0f, PROP_NONE, SOCK_HIDE_VALUE},
	/* Direction/Direction Strength added after the sockets above to keep old .range links valid.
	 * Both default to zero: 100% retrocompatible, the shells push along the normal only. */
	{	SOCK_VECTOR, 1, N_("Direction"), 0.0f, 0.0f, 0.0f, 0.0f, -1.0f, 1.0f, PROP_NONE},
	{	SOCK_FLOAT, 1, N_("Direction Strength"), 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	-1, 0, ""	}
};

static bNodeSocketTemplate sh_node_fur_shells_out[] = {
	{	SOCK_FLOAT, 0, N_("Layer"), 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 0, N_("Alpha"), 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	-1, 0, ""	}
};

static int node_shader_gpu_fur_shells(GPUMaterial *mat, bNode *UNUSED(node), bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	GPUNodeLink *layer;

	GPU_material_shells(mat, (int)(in[1].vec[0] + 0.5f), in[0].vec[0], in[4].vec, in[5].vec[0]);

	if (!(in[3].hasinput && in[3].link)) {
		in[3].link = GPU_attribute(CD_MTFACE, "");
	}
	GPU_link(mat, "node_shell_layer", &layer);
	/* Generated coordinates place the strands when the mesh has no UV map. */
	return GPU_stack_link(mat, "node_fur_shells", in, out, layer, GPU_attribute(CD_ORCO, ""));
}

void register_node_type_sh_fur_shells(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_FUR_SHELLS, "Fur Shells", NODE_CLASS_CONVERTOR, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_fur_shells_in, sh_node_fur_shells_out);
	node_type_gpu(&ntype, node_shader_gpu_fur_shells);

	nodeRegisterType(&ntype);
}

/* **************** OUTLINE ******************** */

static bNodeSocketTemplate sh_node_outline_in[] = {
	{	SOCK_FLOAT, 1, N_("Width"), 0.02f, 0.0f, 0.0f, 0.0f, 0.0f, 100.0f, PROP_DISTANCE},
	{	-1, 0, ""	}
};

static bNodeSocketTemplate sh_node_outline_out[] = {
	{	SOCK_FLOAT, 0, N_("Fac"), 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	-1, 0, ""	}
};

static int node_shader_gpu_outline(GPUMaterial *mat, bNode *UNUSED(node), bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	GPUNodeLink *layer;

	GPU_material_outline(mat, in[0].vec[0]);
	GPU_link(mat, "node_shell_layer", &layer);
	return GPU_stack_link(mat, "node_outline", in, out, layer);
}

void register_node_type_sh_outline(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_OUTLINE, "Outline", NODE_CLASS_CONVERTOR, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_outline_in, sh_node_outline_out);
	node_type_gpu(&ntype, node_shader_gpu_outline);

	nodeRegisterType(&ntype);
}

/* **************** BILLBOARD ******************** */

/* Vertex stage: offset that rotates the mesh around its local origin to face the camera (see
 * node_billboard in gpu_shader_material.glsl for the assumptions on mesh layout). */
static bNodeSocketTemplate sh_node_billboard_in[] = {
	{	SOCK_FLOAT, 1, N_("Lock Axis"), 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("Scale"),     1.0f, 0.0f, 0.0f, 0.0f, 0.0001f, 100.0f, PROP_NONE},
	{	-1, 0, ""	}
};

static int node_shader_gpu_billboard(GPUMaterial *mat, bNode *UNUSED(node), bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	return GPU_stack_link(mat, "node_billboard", in, out,
	                       GPU_material_builtin(mat, GPU_INVERSE_VIEW_MATRIX),
	                       GPU_material_builtin(mat, GPU_INVERSE_OBJECT_MATRIX));
}

void register_node_type_sh_billboard(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_BILLBOARD, "Billboard", NODE_CLASS_OP_VECTOR, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_billboard_in, sh_node_vertex_offset_only_out);
	node_type_gpu(&ntype, node_shader_gpu_billboard);

	nodeRegisterType(&ntype);
}

/* **************** STRANDS ******************** */

/* Density/Length/Curvature are read when the shader is generated (the geometry stage is built
 * for them), same as Fur Shells. Unlike Fur Shells (parallel layers over the whole surface) this
 * emits thin strands/blades growing from random points of each triangle -- grass, fur tufts. */
static bNodeSocketTemplate sh_node_strands_in[] = {
	{	SOCK_FLOAT, 1, N_("Density"),   8.0f,  0.0f, 0.0f, 0.0f, 1.0f, 32.0f, PROP_NONE},
	{	SOCK_FLOAT, 1, N_("Length"),    0.1f,  0.0f, 0.0f, 0.0f, 0.0f, 100.0f, PROP_DISTANCE},
	{	SOCK_FLOAT, 1, N_("Curvature"), 0.0f,  0.0f, 0.0f, 0.0f, -10.0f, 10.0f, PROP_NONE},
	{	-1, 0, ""	}
};

static bNodeSocketTemplate sh_node_strands_out[] = {
	{	SOCK_FLOAT, 0, N_("Tip Factor"), 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	-1, 0, ""	}
};

static int node_shader_gpu_strands(GPUMaterial *mat, bNode *UNUSED(node), bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	GPUNodeLink *layer;

	GPU_material_strands(mat, (int)(in[0].vec[0] + 0.5f), in[1].vec[0], in[2].vec[0]);

	GPU_link(mat, "node_shell_layer", &layer);
	return GPU_stack_link(mat, "node_strands_info", in, out, layer);
}

void register_node_type_sh_strands(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_STRANDS, "Strands", NODE_CLASS_CONVERTOR, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_strands_in, sh_node_strands_out);
	node_type_gpu(&ntype, node_shader_gpu_strands);

	nodeRegisterType(&ntype);
}

/* **************** EXPLODE ******************** */

static bNodeSocketTemplate sh_node_explode_in[] = {
	{	SOCK_FLOAT, 1, N_("Factor"), 0.0f, 0.0f, 0.0f, 0.0f, -100.0f, 100.0f, PROP_DISTANCE},
	{	-1, 0, ""	}
};

static bNodeSocketTemplate sh_node_explode_out[] = {
	{	SOCK_FLOAT, 0, N_("Amount"), 0.0f, 0.0f, 0.0f, 0.0f, -100.0f, 100.0f, PROP_NONE},
	{	-1, 0, ""	}
};

static int node_shader_gpu_explode(GPUMaterial *mat, bNode *UNUSED(node), bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	GPU_material_explode(mat, in[0].vec[0]);
	return GPU_stack_link(mat, "node_explode", in, out);
}

void register_node_type_sh_explode(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_EXPLODE, "Explode", NODE_CLASS_CONVERTOR, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_explode_in, sh_node_explode_out);
	node_type_gpu(&ntype, node_shader_gpu_explode);

	nodeRegisterType(&ntype);
}
