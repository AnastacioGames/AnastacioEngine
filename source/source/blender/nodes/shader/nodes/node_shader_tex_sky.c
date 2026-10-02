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

static bNodeSocketTemplate sh_node_tex_sky_in[] = {
	{	SOCK_VECTOR, 1, N_("Vector"),		0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_NONE, SOCK_HIDE_VALUE},
	{	-1, 0, ""	}
};

static bNodeSocketTemplate sh_node_tex_sky_out[] = {
	{	SOCK_RGBA, 0, N_("Color"),		0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, PROP_NONE, SOCK_NO_INTERNAL_LINK},
	{	-1, 0, ""	}
};

static void node_shader_init_tex_sky(bNodeTree *UNUSED(ntree), bNode *node)
{
	NodeTexSky *tex = MEM_callocN(sizeof(NodeTexSky), "NodeTexSky");
	BKE_texture_mapping_default(&tex->base.tex_mapping, TEXMAP_TYPE_POINT);
	BKE_texture_colormapping_default(&tex->base.color_mapping);
	tex->sun_direction[0] = 0.0f;
	tex->sun_direction[1] = 0.0f;
	tex->sun_direction[2] = 1.0f;
	tex->turbidity = 2.2f;
	tex->ground_albedo = 0.3f;
	tex->sky_model = SHD_SKY_NEW;

	node->storage = tex;
}

/* Preetham coefficients, port of sky_texture_precompute_old from Cycles (render/nodes.cpp).
 * Hosek / Wilkie also uses this model in the Game. */
static float sky_perez_function(const float lam[5], float theta, float gamma)
{
	return (1.0f + lam[0] * expf(lam[1] / cosf(theta))) * (1.0f + lam[2] * expf(lam[3] * gamma) + lam[4] * cosf(gamma) * cosf(gamma));
}

static int node_shader_gpu_tex_sky(GPUMaterial *mat, bNode *node, bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	NodeTexSky *tex = node->storage;
	float dir[3], cx[5], cy[5], cz[5];
	/* GPU_uniform copies the values when the link is consumed by GPU_stack_link below. */
	float sun[2], radiance[3], config_x[4], config_y[4], config_z[4], config_last[3];

	copy_v3_v3(dir, tex->sun_direction);
	if (normalize_v3(dir) == 0.0f)
		dir[2] = 1.0f;

	const float theta = acosf(CLAMPIS(dir[2], -1.0f, 1.0f));
	const float phi = atan2f(dir[0], dir[1]);
	const float theta2 = theta * theta;
	const float theta3 = theta2 * theta;
	const float T = tex->turbidity;
	const float T2 = T * T;

	const float chi = (4.0f / 9.0f - T / 120.0f) * ((float)M_PI - 2.0f * theta);
	radiance[0] = ((4.0453f * T - 4.9710f) * tanf(chi) - 0.2155f * T + 2.4192f) * 0.06f;
	radiance[1] = (0.00166f * theta3 - 0.00375f * theta2 + 0.00209f * theta) * T2 +
	              (-0.02903f * theta3 + 0.06377f * theta2 - 0.03202f * theta + 0.00394f) * T +
	              (0.11693f * theta3 - 0.21196f * theta2 + 0.06052f * theta + 0.25886f);
	radiance[2] = (0.00275f * theta3 - 0.00610f * theta2 + 0.00317f * theta) * T2 +
	              (-0.04214f * theta3 + 0.08970f * theta2 - 0.04153f * theta + 0.00516f) * T +
	              (0.15346f * theta3 - 0.26756f * theta2 + 0.06670f * theta + 0.26688f);

	cx[0] = 0.1787f * T - 1.4630f;
	cx[1] = -0.3554f * T + 0.4275f;
	cx[2] = -0.0227f * T + 5.3251f;
	cx[3] = 0.1206f * T - 2.5771f;
	cx[4] = -0.0670f * T + 0.3703f;

	cy[0] = -0.0193f * T - 0.2592f;
	cy[1] = -0.0665f * T + 0.0008f;
	cy[2] = -0.0004f * T + 0.2125f;
	cy[3] = -0.0641f * T - 0.8989f;
	cy[4] = -0.0033f * T + 0.0452f;

	cz[0] = -0.0167f * T - 0.2608f;
	cz[1] = -0.0950f * T + 0.0092f;
	cz[2] = -0.0079f * T + 0.2102f;
	cz[3] = -0.0441f * T - 1.6537f;
	cz[4] = -0.0109f * T + 0.0529f;

	radiance[0] /= sky_perez_function(cx, 0.0f, theta);
	radiance[1] /= sky_perez_function(cy, 0.0f, theta);
	radiance[2] /= sky_perez_function(cz, 0.0f, theta);

	sun[0] = phi;
	sun[1] = theta;
	copy_v4_v4(config_x, cx);
	copy_v4_v4(config_y, cy);
	copy_v4_v4(config_z, cz);
	config_last[0] = cx[4];
	config_last[1] = cy[4];
	config_last[2] = cz[4];

	if (!in[0].link) {
		/* Same as Cycles generated coordinates: the ray direction for the World. */
		if (GPU_Material_get_type(mat) == GPU_MATERIAL_TYPE_MESH)
			in[0].link = GPU_attribute(CD_ORCO, "");
		else
			GPU_link(mat, "background_transform_to_world", GPU_material_builtin(mat, GPU_VIEW_POSITION), &in[0].link);
	}

	node_shader_gpu_tex_mapping(mat, node, in, out);

	return GPU_stack_link(mat, "node_tex_sky", in, out,
	                      GPU_uniform(sun), GPU_uniform(radiance),
	                      GPU_uniform(config_x), GPU_uniform(config_y), GPU_uniform(config_z),
	                      GPU_uniform(config_last));
}

/* node type definition */
void register_node_type_sh_tex_sky(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_TEX_SKY, "Sky Texture", NODE_CLASS_TEXTURE, 0);
	node_type_compatibility(&ntype, NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, sh_node_tex_sky_in, sh_node_tex_sky_out);
	node_type_size_preset(&ntype, NODE_SIZE_MIDDLE);
	node_type_init(&ntype, node_shader_init_tex_sky);
	node_type_storage(&ntype, "NodeTexSky", node_free_standard_storage, node_copy_standard_storage);
	node_type_gpu(&ntype, node_shader_gpu_tex_sky);

	nodeRegisterType(&ntype);
}
