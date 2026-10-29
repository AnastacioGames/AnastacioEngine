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

#include "GPU_texture.h"

/* **************** OUTPUT ******************** */

static bNodeSocketTemplate sh_node_bsdf_principled_in[] = {
	{	SOCK_RGBA, 1, N_("Base Color"),				0.8f, 0.8f, 0.8f, 1.0f, 0.0f, 1.0f},
	{	SOCK_FLOAT, 1, N_("Subsurface"),			0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_VECTOR, 1, N_("Subsurface Radius"),	1.0f, 0.2f, 0.1f, 0.0f, 0.0f, 100.0f},
	{	SOCK_RGBA, 1, N_("Subsurface Color"),		0.8f, 0.8f, 0.8f, 1.0f, 0.0f, 1.0f},
	{	SOCK_FLOAT, 1, N_("Metallic"),				0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("Specular"),				0.5f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("Specular Tint"),			0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("Roughness"),				0.5f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("Anisotropic"),			0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("Anisotropic Rotation"),	0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("Sheen"),					0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("Sheen Tint"),			0.5f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("Clearcoat"),				0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("Clearcoat Roughness"),	0.03f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("IOR"),					1.45f, 0.0f, 0.0f, 0.0f, 0.0f, 1000.0f},
	{	SOCK_FLOAT, 1, N_("Transmission"),			0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_FLOAT, 1, N_("Transmission Roughness"),0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_FACTOR},
	{	SOCK_VECTOR, 1, N_("Normal"),				0.0f, 0.0f, 0.0f, 1.0f, -1.0f, 1.0f, PROP_NONE, SOCK_HIDE_VALUE},
	{	SOCK_VECTOR, 1, N_("Clearcoat Normal"),		0.0f, 0.0f, 0.0f, 1.0f, -1.0f, 1.0f, PROP_NONE, SOCK_HIDE_VALUE},
	{	SOCK_VECTOR, 1, N_("Tangent"),				0.0f, 0.0f, 0.0f, 1.0f, -1.0f, 1.0f, PROP_NONE, SOCK_HIDE_VALUE},
	{	-1, 0, ""	}
};

static bNodeSocketTemplate sh_node_bsdf_principled_out[] = {
	{	SOCK_SHADER, 0, N_("BSDF")},
	{	-1, 0, ""	}
};

static void node_shader_init_principled(bNodeTree *UNUSED(ntree), bNode *node)
{
	node->custom1 = SHD_GLOSSY_GGX;
	node->custom2 = SHD_SUBSURFACE_BURLEY;
}

static int node_shader_gpu_bsdf_principled(GPUMaterial *mat, bNode *node, bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	// normal; a builtin link is freed by the node that takes it, so the lightmap/volume gets its own
	bool own_normal = !in[17].link;
	if (!in[17].link)
		in[17].link = GPU_material_builtin(mat, GPU_VIEW_NORMAL);
	else
		GPU_link(mat, "direction_transform_m4v3", in[17].link, GPU_material_builtin(mat, GPU_VIEW_MATRIX), &in[17].link);

	// clearcoat normal
	bool own_cc_normal = !in[18].link;
	if (!in[18].link)
		in[18].link = GPU_material_builtin(mat, GPU_VIEW_NORMAL);
	else
		GPU_link(mat, "direction_transform_m4v3", in[18].link, GPU_material_builtin(mat, GPU_VIEW_MATRIX), &in[18].link);

	/* World environment lighting (IBL from sky/HDRI). Only in the new-shading game path; otherwise
	 * the shader keeps its constant ambient (env_on = 0). */
	GPUNodeLink *view = GPU_material_builtin(mat, GPU_VIEW_POSITION);
	GPUNodeLink *rough = in[7].link ? in[7].link : GPU_uniform(in[7].vec);
	GPUNodeLink *env_mirror, *env_diffuse, *env_flag;
	node_shader_gpu_world_env(mat, rough, own_normal ? NULL : in[17].link, &env_mirror, &env_diffuse, &env_flag);

	/* screen copy for Transmission; only asked for (made each frame) when Transmission is used */
	GPUNodeLink *scol = (in[15].link || in[15].vec[0] > 0.0f) ? node_shader_gpu_scene_color(mat) :
	                    GPU_dynamic_texture_ptr(GPU_texture_global_scene_color_ptr(), GPU_DYNAMIC_SAMPLER_2DBUFFER, NULL);

	/* Colored shadows: the light passing through takes the Base Color (alpha from the surface,
	 * e.g. a Mix with a Transparent BSDF). */
	GPUNodeLink *shadow_base;
	GPU_link(mat, "set_rgba", in[0].link ? in[0].link : GPU_uniform(in[0].vec), &shadow_base);
	GPU_material_shadow_color_link(mat, shadow_base, NULL);

	GPUNodeLink *lightmap = node_shader_gpu_lightmap(
	        mat, own_normal ? GPU_material_builtin(mat, GPU_VIEW_NORMAL) : in[17].link);

	/* Clearcoat reflects the environment too, with its own roughness and normal (only when the
	 * coat is used: a second environment lookup per pixel). */
	bool coat_on = in[12].link || in[12].vec[0] > 0.0f;
	GPUNodeLink *env_cc_mirror;
	if (coat_on) {
		GPUNodeLink *cc_rough = in[13].link ? in[13].link : GPU_uniform(in[13].vec);
		GPUNodeLink *cc_diffuse, *cc_flag;
		node_shader_gpu_world_env(mat, cc_rough, own_cc_normal ? NULL : in[18].link, &env_cc_mirror, &cc_diffuse, &cc_flag);
	}
	else {
		GPU_link(mat, "set_rgba_zero", &env_cc_mirror);
	}

	/* Environment BRDF table (docs/bsdf-energia.md): Multiscatter GGX energy compensation and the
	 * clearcoat environment albedo. GGX without coat keeps the analytic path; its sampler reuses
	 * the screen copy pointer, so the code generator gives it the same texture unit. */
	GPUTexture *brdf_lut_tex = GPU_texture_global_brdf_lut();
	float ms_on = (node->custom1 == SHD_GLOSSY_MULTI_GGX && brdf_lut_tex) ? 1.0f : 0.0f;
	float lut_on = (brdf_lut_tex && (ms_on > 0.0f || coat_on)) ? 1.0f : 0.0f;
	GPUNodeLink *brdf_lut = (lut_on > 0.0f) ?
	        GPU_dynamic_texture(brdf_lut_tex, GPU_DYNAMIC_SAMPLER_2DIMAGE, NULL) :
	        GPU_dynamic_texture_ptr(GPU_texture_global_scene_color_ptr(), GPU_DYNAMIC_SAMPLER_2DBUFFER, NULL);

	GPUNodeLink *ssgi_normal, *ssgi_albedo, *ssgi_direct, *ssgi_linear;
	return GPU_stack_link(mat, "node_bsdf_principled", in, out, view, env_mirror, env_diffuse, env_flag, scol,
	                      lightmap, brdf_lut, GPU_uniform(&lut_on), GPU_uniform(&ms_on), env_cc_mirror,
	                      &ssgi_normal, &ssgi_albedo, &ssgi_direct, &ssgi_linear);
}

static void node_shader_update_principled(bNodeTree *UNUSED(ntree), bNode *node)
{
	bNodeSocket *sock;
	int distribution = node->custom1;

	for (sock = node->inputs.first; sock; sock = sock->next) {
		if (STREQ(sock->name, "Transmission Roughness")) {
			if (distribution == SHD_GLOSSY_GGX)
				sock->flag &= ~SOCK_UNAVAIL;
			else
				sock->flag |= SOCK_UNAVAIL;

		}
	}
}

/* node type definition */
void register_node_type_sh_bsdf_principled(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_BSDF_PRINCIPLED, "Principled BSDF", NODE_CLASS_SHADER, 0);
	node_type_compatibility(&ntype, NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_bsdf_principled_in, sh_node_bsdf_principled_out);
	node_type_size_preset(&ntype, NODE_SIZE_LARGE);
	node_type_init(&ntype, node_shader_init_principled);
	node_type_storage(&ntype, "", NULL, NULL);
	node_type_gpu(&ntype, node_shader_gpu_bsdf_principled);
	node_type_update(&ntype, node_shader_update_principled, NULL);

	nodeRegisterType(&ntype);
}
