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

/** \file blender/nodes/shader/node_shader_util.c
 *  \ingroup nodes
 */


#include "DNA_node_types.h"

#include "node_shader_util.h"

#include "node_exec.h"

#include "GPU_texture.h"

#include "BKE_idprop.h"


bool sh_node_poll_default(bNodeType *UNUSED(ntype), bNodeTree *ntree)
{
	return STREQ(ntree->idname, "ShaderNodeTree");
}

void sh_node_type_base(struct bNodeType *ntype, int type, const char *name, short nclass, short flag)
{
	node_type_base(ntype, type, name, nclass, flag);

	ntype->poll = sh_node_poll_default;
	ntype->insert_link = node_insert_link_default;
	ntype->update_internal_links = node_update_internal_links_default;
}

/* ****** */

void nodestack_get_vec(float *in, short type_in, bNodeStack *ns)
{
	const float *from = ns->vec;

	if (type_in == SOCK_FLOAT) {
		if (ns->sockettype == SOCK_FLOAT)
			*in = *from;
		else
			*in = (from[0] + from[1] + from[2]) / 3.0f;
	}
	else if (type_in == SOCK_VECTOR) {
		if (ns->sockettype == SOCK_FLOAT) {
			in[0] = from[0];
			in[1] = from[0];
			in[2] = from[0];
		}
		else {
			copy_v3_v3(in, from);
		}
	}
	else { /* type_in==SOCK_RGBA */
		if (ns->sockettype == SOCK_RGBA) {
			copy_v4_v4(in, from);
		}
		else if (ns->sockettype == SOCK_FLOAT) {
			in[0] = from[0];
			in[1] = from[0];
			in[2] = from[0];
			in[3] = 1.0f;
		}
		else {
			copy_v3_v3(in, from);
			in[3] = 1.0f;
		}
	}
}


/* go over all used Geometry and Texture nodes, and return a texco flag */
/* no group inside needed, this function is called for groups too */
void ntreeShaderGetTexcoMode(bNodeTree *ntree, int r_mode, short *texco, int *mode)
{
	bNode *node;
	bNodeSocket *sock;
	int a;

	for (node = ntree->nodes.first; node; node = node->next) {
		if (node->type == SH_NODE_TEXTURE) {
			if ((r_mode & R_OSA) && node->id) {
				Tex *tex = (Tex *)node->id;
				if (ELEM(tex->type, TEX_IMAGE, TEX_ENVMAP)) {
					*texco |= TEXCO_OSA | NEED_UV;
				}
			}
			/* usability exception... without input we still give the node orcos */
			sock = node->inputs.first;
			if (sock == NULL || sock->link == NULL)
				*texco |= TEXCO_ORCO | NEED_UV;
		}
		else if (node->type == SH_NODE_GEOMETRY) {
			/* note; sockets always exist for the given type! */
			for (a = 0, sock = node->outputs.first; sock; sock = sock->next, a++) {
				if (sock->flag & SOCK_IN_USE) {
					switch (a) {
						case GEOM_OUT_GLOB:
							*texco |= TEXCO_GLOB | NEED_UV; break;
						case GEOM_OUT_VIEW:
							*texco |= TEXCO_VIEW | NEED_UV; break;
						case GEOM_OUT_ORCO:
							*texco |= TEXCO_ORCO | NEED_UV; break;
						case GEOM_OUT_UV:
							*texco |= TEXCO_UV | NEED_UV; break;
						case GEOM_OUT_NORMAL:
							*texco |= TEXCO_NORM | NEED_UV; break;
						case GEOM_OUT_VCOL:
							*texco |= NEED_UV; *mode |= MA_VERTEXCOL; break;
						case GEOM_OUT_VCOL_ALPHA:
							*texco |= NEED_UV; *mode |= MA_VERTEXCOL; break;
					}
				}
			}
		}
	}
}

void node_gpu_stack_from_data(struct GPUNodeStack *gs, int type, bNodeStack *ns)
{
	memset(gs, 0, sizeof(*gs));

	if (ns == NULL) {
		/* node_get_stack() will generate NULL bNodeStack pointers for unknown/unsupported types of sockets... */
		zero_v4(gs->vec);
		gs->link = NULL;
		gs->type = GPU_NONE;
		gs->name = "";
		gs->hasinput = false;
		gs->hasoutput = false;
		gs->sockettype = type;
	}
	else {
		nodestack_get_vec(gs->vec, type, ns);
		gs->link = ns->data;

		if (type == SOCK_FLOAT)
			gs->type = GPU_FLOAT;
		else if (type == SOCK_VECTOR)
			gs->type = GPU_VEC3;
		else if (type == SOCK_RGBA)
			gs->type = GPU_VEC4;
		else if (type == SOCK_SHADER)
			gs->type = GPU_VEC4;
		else
			gs->type = GPU_NONE;

		gs->name = "";
		gs->hasinput = ns->hasinput && ns->data;
		/* XXX Commented out the ns->data check here, as it seems it's not always set,
		 *     even though there *is* a valid connection/output... But that might need
		 *     further investigation.
		 */
		gs->hasoutput = ns->hasoutput /*&& ns->data*/;
		gs->sockettype = ns->sockettype;
	}
}

void node_data_from_gpu_stack(bNodeStack *ns, GPUNodeStack *gs)
{
	copy_v4_v4(ns->vec, gs->vec);
	ns->data = gs->link;
	ns->sockettype = gs->sockettype;
}

static void gpu_stack_from_data_list(GPUNodeStack *gs, ListBase *sockets, bNodeStack **ns)
{
	bNodeSocket *sock;
	int i;

	for (sock = sockets->first, i = 0; sock; sock = sock->next, i++)
		node_gpu_stack_from_data(&gs[i], sock->type, ns[i]);

	gs[i].type = GPU_NONE;
}

static void data_from_gpu_stack_list(ListBase *sockets, bNodeStack **ns, GPUNodeStack *gs)
{
	bNodeSocket *sock;
	int i;

	for (sock = sockets->first, i = 0; sock; sock = sock->next, i++)
		node_data_from_gpu_stack(ns[i], &gs[i]);
}

bNode *nodeGetActiveTexture(bNodeTree *ntree)
{
	/* this is the node we texture paint and draw in textured draw */
	bNode *node, *tnode, *inactivenode = NULL, *activetexnode = NULL, *activegroup = NULL;
	bool hasgroup = false;

	if (!ntree)
		return NULL;

	for (node = ntree->nodes.first; node; node = node->next) {
		if (node->flag & NODE_ACTIVE_TEXTURE) {
			activetexnode = node;
			/* if active we can return immediately */
			if (node->flag & NODE_ACTIVE)
				return node;
		}
		else if (!inactivenode && node->typeinfo->nclass == NODE_CLASS_TEXTURE)
			inactivenode = node;
		else if (node->type == NODE_GROUP) {
			if (node->flag & NODE_ACTIVE)
				activegroup = node;
			else
				hasgroup = true;
		}
	}

	/* first, check active group for textures */
	if (activegroup) {
		tnode = nodeGetActiveTexture((bNodeTree *)activegroup->id);
		/* active node takes priority, so ignore any other possible nodes here */
		if (tnode)
			return tnode;
	}

	if (activetexnode)
		return activetexnode;

	if (hasgroup) {
		/* node active texture node in this tree, look inside groups */
		for (node = ntree->nodes.first; node; node = node->next) {
			if (node->type == NODE_GROUP) {
				tnode = nodeGetActiveTexture((bNodeTree *)node->id);
				if (tnode && ((tnode->flag & NODE_ACTIVE_TEXTURE) || !inactivenode))
					return tnode;
			}
		}
	}

	return inactivenode;
}

void ntreeExecGPUNodes(bNodeTreeExec *exec, GPUMaterial *mat, int do_outputs, short compatibility)
{
	bNodeExec *nodeexec;
	bNode *node;
	int n;
	bNodeStack *stack;
	bNodeStack *nsin[MAX_SOCKET];   /* arbitrary... watch this */
	bNodeStack *nsout[MAX_SOCKET];  /* arbitrary... watch this */
	GPUNodeStack gpuin[MAX_SOCKET + 1], gpuout[MAX_SOCKET + 1];
	bool do_it;

	stack = exec->stack;

	for (n = 0, nodeexec = exec->nodeexec; n < exec->totnodes; ++n, ++nodeexec) {
		node = nodeexec->node;

		do_it = false;
		/* for groups, only execute outputs for edited group */
		if (node->typeinfo->nclass == NODE_CLASS_OUTPUT) {
			if (node->typeinfo->compatibility & compatibility)
				if (do_outputs && (node->flag & NODE_DO_OUTPUT))
					do_it = true;
		}
		else {
			do_it = true;
		}

		if (do_it) {
			if (node->typeinfo->gpufunc) {
				node_get_stack(node, stack, nsin, nsout);
				gpu_stack_from_data_list(gpuin, &node->inputs, nsin);
				gpu_stack_from_data_list(gpuout, &node->outputs, nsout);
				if (node->typeinfo->gpufunc(mat, node, &nodeexec->data, gpuin, gpuout))
					data_from_gpu_stack_list(&node->outputs, nsout, gpuout);
			}
		}
	}
}

void node_shader_gpu_tex_mapping(GPUMaterial *mat, bNode *node, GPUNodeStack *in, GPUNodeStack *UNUSED(out))
{
	NodeTexBase *base = node->storage;
	TexMapping *texmap = &base->tex_mapping;
	float domin = (texmap->flag & TEXMAP_CLIP_MIN) != 0;
	float domax = (texmap->flag & TEXMAP_CLIP_MAX) != 0;

	if (domin || domax || !(texmap->flag & TEXMAP_UNIT_MATRIX)) {
		GPUNodeLink *tmat = GPU_uniform((float *)texmap->mat);
		GPUNodeLink *tmin = GPU_uniform(texmap->min);
		GPUNodeLink *tmax = GPU_uniform(texmap->max);
		GPUNodeLink *tdomin = GPU_uniform(&domin);
		GPUNodeLink *tdomax = GPU_uniform(&domax);

		GPU_link(mat, "mapping_mat4", in[0].link, tmat, tmin, tmax, tdomin, tdomax, &in[0].link);

		if (texmap->type == TEXMAP_TYPE_NORMAL)
			GPU_link(mat, "texco_norm", in[0].link, &in[0].link);
	}
}

/* World environment (sky/HDRI) for BSDF nodes in the new-shading Game path: reflection and diffuse
 * irradiance plus a 0/1 flag. Builtin links are single-use, so this takes its own view/normal links;
 * callers must not pass theirs. Without a world texture both colors are zero and the flag is 0. */
void node_shader_gpu_world_env(GPUMaterial *mat, GPUNodeLink *rough,
                               GPUNodeLink **r_mirror, GPUNodeLink **r_diffuse, GPUNodeLink **r_flag)
{
	static float env_on = 1.0f, env_off = 0.0f;
	GPUNodeLink *env_view;
	/* shade_world_vectors expects a normalized (perspective-aware) view direction (shade_view),
	 * not the raw view-space position. */
	GPU_link(mat, "shade_view", GPU_material_builtin(mat, GPU_VIEW_POSITION), &env_view);
	GPUNodeLink *env_vn = GPU_material_builtin(mat, GPU_VIEW_NORMAL);
	if (GPU_material_world_env(mat, env_view, env_vn, rough, r_mirror, r_diffuse)) {
		*r_flag = GPU_uniform(&env_on);
	}
	else {
		GPU_link(mat, "set_rgba_zero", r_mirror);
		*r_diffuse = *r_mirror;
		*r_flag = GPU_uniform(&env_off);
	}
}

/* Baked indirect light (Game PBR): one RGBM lightmap atlas for the scene, read through the UV layer
 * named "Lightmap" (see bl_operators/anastacio_lightmap.py). The scene ID properties are "ae_lightmap"
 * (image name) and "ae_lightmap_use" (on/off, World > Baked Lighting). Gives rgb = irradiance, a = 1 where baked (0 for
 * objects outside the atlas, which keep the probe/World ambient). Off: a constant zero, no sampling.
 * Where the lightmap does not reach, the baked light volume ("ae_lightvol*", same panel) fills in. */
static Image *scene_baked_image(Scene *scene, const char *name_prop, const char *use_prop)
{
	if (!scene || !scene->id.properties || !G.main) {
		return NULL;
	}
	IDProperty *name = IDP_GetPropertyFromGroup(scene->id.properties, name_prop);
	IDProperty *use = IDP_GetPropertyFromGroup(scene->id.properties, use_prop);
	if (name && name->type == IDP_STRING && use && use->type == IDP_INT && IDP_Int(use)) {
		return BLI_findstring(&G.main->image, IDP_String(name), offsetof(ID, name) + 2);
	}
	return NULL;
}

GPUNodeLink *node_shader_gpu_lightmap(GPUMaterial *mat, GPUNodeLink *normal)
{
	Scene *scene = GPU_material_scene(mat);
	Image *ima = scene_baked_image(scene, "ae_lightmap", "ae_lightmap_use");
	GPUNodeLink *lm;
	if (ima) {
		GPU_link(mat, "lightmap_sample", GPU_attribute(CD_MTFACE, "Lightmap"), GPU_image(ima, NULL, true), &lm);
	}
	else {
		GPU_link(mat, "set_rgba_zero", &lm);
	}

	/* light volume grid: "ae_lightvol_grid" = min xyz, cell size xyz, probe count xyz */
	Image *vol = scene_baked_image(scene, "ae_lightvol", "ae_lightvol_use");
	IDProperty *grid = vol ? IDP_GetPropertyFromGroup(scene->id.properties, "ae_lightvol_grid") : NULL;
	if (grid && grid->type == IDP_ARRAY && grid->len == 9 &&
	    ELEM(grid->subtype, IDP_FLOAT, IDP_DOUBLE))
	{
		float g[9];
		for (int i = 0; i < 9; i++) {
			g[i] = (grid->subtype == IDP_FLOAT) ? ((float *)IDP_Array(grid))[i] : (float)((double *)IDP_Array(grid))[i];
		}
		float vmin[3] = {g[0], g[1], g[2]};
		float vinv[3], dim[3] = {max_ff(g[6], 1.0f), max_ff(g[7], 1.0f), max_ff(g[8], 1.0f)};
		for (int i = 0; i < 3; i++) {
			vinv[i] = (g[3 + i] > 1e-6f) ? 1.0f / g[3 + i] : 0.0f;
		}
		GPU_link(mat, "lightvol_sample", lm, GPU_material_builtin(mat, GPU_VIEW_POSITION),
		         GPU_material_builtin(mat, GPU_INVERSE_VIEW_MATRIX),
		         normal, GPU_image(vol, NULL, true), GPU_uniform(vmin), GPU_uniform(vinv), GPU_uniform(dim), &lm);
	}
	return lm;
}

/* Scene color copy for screen-space refraction (Glass, Refraction), see
 * GPU_texture_global_scene_color_ptr. Asks the game to make the copy from now on. */
GPUNodeLink *node_shader_gpu_scene_color(GPUMaterial *UNUSED(mat))
{
	GPU_texture_scene_color_request();
	return GPU_dynamic_texture_ptr(GPU_texture_global_scene_color_ptr(), GPU_DYNAMIC_SAMPLER_2DBUFFER, NULL);
}

/* Depth of the solid pass (same copy as the scene color, made for Alpha Blend materials when the
 * color is requested), see GPU_texture_global_depth_ptr; 1x1 placeholder elsewhere. */
GPUNodeLink *node_shader_gpu_scene_depth(GPUMaterial *UNUSED(mat))
{
	return GPU_dynamic_texture_ptr(GPU_texture_global_depth_ptr(), GPU_DYNAMIC_SAMPLER_2DBUFFER, NULL);
}

/* Volume nodes (Game PBR): links the GLSL function with the listed inputs (string sockets such as
 * the Principled Volume attributes can not go through GPU_stack_link) followed by the view position,
 * inverse view and object matrices, World color, scene depth and scene color. */
bool node_shader_gpu_volume(GPUMaterial *mat, const char *name, GPUNodeStack *in,
                            const int *inputs, int totinput, GPUNodeStack *out)
{
	GPUNodeLink *l[16];
	int tot = 0;
	for (int i = 0; i < totinput; i++) {
		GPUNodeStack *s = &in[inputs[i]];
		l[tot++] = s->link ? s->link : GPU_uniform(s->vec);
	}
	l[tot++] = GPU_material_builtin(mat, GPU_VIEW_POSITION);
	l[tot++] = GPU_material_builtin(mat, GPU_INVERSE_VIEW_MATRIX);
	l[tot++] = GPU_material_builtin(mat, GPU_INVERSE_OBJECT_MATRIX);
	l[tot++] = GPU_material_world_color(mat);
	l[tot++] = node_shader_gpu_scene_depth(mat);
	l[tot++] = node_shader_gpu_scene_color(mat);
	switch (tot) {
		case 8:
			return GPU_link(mat, name, l[0], l[1], l[2], l[3], l[4], l[5], l[6], l[7], &out[0].link);
		case 9:
			return GPU_link(mat, name, l[0], l[1], l[2], l[3], l[4], l[5], l[6], l[7], l[8], &out[0].link);
		case 15:
			return GPU_link(mat, name, l[0], l[1], l[2], l[3], l[4], l[5], l[6], l[7], l[8], l[9], l[10],
			                l[11], l[12], l[13], l[14], &out[0].link);
	}
	return false;
}
