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
 * The Original Code is Copyright (C) 2006 Blender Foundation.
 * All rights reserved.
 */

/** ile blender/gpu/intern/gpu_material_intern.h
 *  \ingroup gpu
 *
 * Internal struct definitions shared by gpu_material*.c (GPUMaterial, GPULamp).
 */

#ifndef __GPU_MATERIAL_INTERN_H__
#define __GPU_MATERIAL_INTERN_H__

struct GPUMaterial {
	Scene *scene;
	Material *ma;

	/* material for mesh surface, worlds or something else.
	 * some code generation is done differently depending on the use case */
	int type;

	/* for creating the material */
	ListBase nodes;
	GPUNodeLink *outlinks[8];
	/* Colored shadows: what the material casts with, see GPU_material_shadow_color_link(). */
	GPUNodeLink *shadowcol_base, *shadowcol_alpha;

	/* Vertex and geometry stages set by the nodes (see GPUPassStages). */
	GPUNodeLink *vertex_offset;
	int shell_layers;
	float shell_length;
	float shell_dir[3];
	float shell_dir_strength;
	float outline_width;
	int strand_density;
	float strand_length;
	float strand_curvature;
	float explode_factor;
	/* True once node_shader_gpu_planar_reflection() runs (Planar Reflection node present). */
	bool use_planar_reflection;
	ListBase scripts; /* GPUScriptCode, only while the pass is generated */
	ListBase script_uniforms; /* GPUScriptUniform, the pass inputs point to these values */
	/* User vertex/geometry code or vertex nodes: the view/object matrices and the time are always sent. */
	bool use_vertex_stage;

	/* for binding the material */
	GPUPass *pass;
	/* Set by gpu_material_construct_end when GPU_generate_pass fails: the raw compiler log, and
	 * the GLSL Script node's bNode->name when the log could be traced back to one (see
	 * GPU_material_node_error / GPU_material_has_error). NULL while there is no error. */
	char *error_log;
	char error_node_name[64];
#ifdef __EMSCRIPTEN__
	unsigned int web_output_mask;
	GLenum web_draw_buffers[8];
	GLint web_draw_framebuffer;
	int web_draw_buffer_count;
#endif
	GPUVertexAttribs attribs;
	int builtins;
	int baryuniformloc; /* unfbaryattrib, see GPU_material_viewport_barycentric() */
	int alpha, obcolalpha;
	int dynproperty;

	/* for passing uniforms */
	int viewmatloc, invviewmatloc;
	int projmatloc;
	int obmatloc, invobmatloc;
	int localtoviewmatloc, invlocaltoviewmatloc;
	int normalmatloc;
	int obcolloc, obautobumpscaleloc;
	int cameratexcofacloc;
	int timeloc;

	int partscalarpropsloc;
	int partcoloc;
	int partvel;
	int partangvel;

	int objectinfoloc;
	int objectlayloc;
	/* Uniform state is only trusted within the current material activation. */
	bool objectlay_valid;
	int objectlay_value;

	/* RA2: localtoviewmat/normalmat/invlocaltoviewmat (GPU_material_bind_uniforms) only depend on
	 * obmat+viewmat. Different objects legitimately have different obmat within one bind, but the
	 * same object/obmat is drawn more than once per bind in several passes (z-prepass, shadow,
	 * main, halo). Cache the last obmat+viewmat and the matrices derived from them, valid only
	 * within the current material activation (reset in GPU_material_bind, like objectlay_valid). */
	bool invcache_valid;
	float invcache_obmat[4][4], invcache_viewmat[4][4];
	float invcache_localtoviewmat[4][4], invcache_invlocaltoviewmat[4][4], invcache_normalmat[3][3];

	int ininstposloc;
	int ininstmatloc;
	int ininstcolloc;
	int ininstlayloc;
	int ininstinfoloc;

	bool use_instancing;

	int boneindexloc;
	int boneweightloc;
	int bonematloc;

	bool use_skinning;

	int infoliageparamsloc;
	int infoliagecameraloc;
	float foliagecamera[3];
	bool foliagecamera_set;
	float foliagetime;

	bool use_foliage;

	/* Shadow data for the fixed-function scene-light loop read by node_bsdf_principled() et al
	 * (SCENE_LIGHT(i), i < NUM_SHADOW_LIGHTS in gpu_shader_material.glsl) -- resolved once here,
	 * bound per-frame by GPU_material_bind_shadow_lamps() from BL_BlenderShader::UpdateLights().
	 * -1 (unused location) for any material whose shader doesn't reference these uniforms. */
	int shadowmaploc[GPU_MATERIAL_NUM_SHADOW_LAMPS];
	int shadowpersmatloc[GPU_MATERIAL_NUM_SHADOW_LAMPS];
	int shadowbiasloc[GPU_MATERIAL_NUM_SHADOW_LAMPS];
	int shadowenabledloc[GPU_MATERIAL_NUM_SHADOW_LAMPS];
	int shadowpointloc[GPU_MATERIAL_NUM_SHADOW_LAMPS];
	int shadowfilterloc[GPU_MATERIAL_NUM_SHADOW_LAMPS];
	int shadowcolorloc[GPU_MATERIAL_NUM_SHADOW_LAMPS];
	int shadowcoloredloc[GPU_MATERIAL_NUM_SHADOW_LAMPS];
	/* Cascaded sun of the loop (SHADOW_CSM): outer maps 0/1, their matrices, bias, imat, splits, filter. */
	int csmmaploc[2], csmpersmatloc, csmbiasloc, csmimatloc, csmsplitloc, csmfilterloc;

	/* Local reflection probe (unfprobecube/unfprobeinfo), bound per object by GPU_material_bind_probe(). */
	int probecubeloc, probeinfoloc, probeposloc;
	int probecube2loc, probeinfo2loc, probepos2loc;
	int probeboxloc, probebox2loc;
	int probeshloc, probesh2loc;
	/* Only cache absent probes within one material activation. Active textures
	 * must still bind per object; reactivation resets potentially shared programs. */
	bool probe_absent_valid[2];
	float probe_absent_maxlod[2];
	/* Planar Reflection node (unfplanartex/unfplanarviewproj/unfplanarenabled/unfplanarview), bound
	 * per object by GPU_material_bind_planar(). */
	int planarteximgloc, planarviewprojloc, planarenabledloc, planarviewloc;
	/* Damage node hits (unfdamagehits/unfdamagestrength/unfdamagecount), bound per object by GPU_material_bind_damage(). */
	int damagehitsloc, damagestrengthloc, damagecountloc;

	/* unflightsource[i].* (CORE profile only, see GPUSceneLight); -1 when not declared/used. */
	struct {
		int position, diffuse, specular, halfvector, spotdirection, spotexponent;
		int spotcutoff, spotcoscutoff, constantatt, linearatt, quadraticatt;
	} scenelightloc[GPU_MATERIAL_NUM_SCENE_LIGHTS];
	bool use_scene_lights;
	/* unfiesinfo/unfiesaxes/unfiesatlas: IES profiles of the scene lights (both GL profiles). */
	int iesinfoloc, iesaxesloc, iesatlasloc;

	ListBase lamps;
	bool bound;

	bool is_opensubdiv;

	float har;
};

struct GPULamp {
	Scene *scene;
	Object *ob;
	Object *par;
	Lamp *la;

	int type, mode, lay, hide;

	int dynlayer;
	float dynenergy, dyncol[3];
	float energy, col[3];
	float cutoff, radius;

	float co[3], vec[3];
	float dynco[3], dynvec[3];
	float obmat[4][4];
	float imat[4][4];
	/* Cache only light-derived data; shadow passes overwrite the projection matrices. */
	float update_obmat[4][4], update_scale[3];
	bool update_obmat_valid;
	float update_spotsize;
	bool update_spotsize_valid;
	float dynimat[4][4];
	float dynarearight[3];
	float dynareaup[3];

	/* GP6 cache: dynvec/dynco/dynimat/dynpersmat/dynarearight only depend on this lamp's
	 * transform/mode (vec, co, obmat) and the caller's viewmat/viewinv. GPU_material_update_lamps()
	 * is called once per *material* per bind, so the same lamp gets its matrices recomputed many
	 * times per frame with the same viewmat (shared by every material drawn under that camera).
	 * Skip the matrix math when the inputs are byte-identical to the last update. */
	float dynupdate_viewmat[4][4], dynupdate_viewinv[4][4];
	float dynupdate_vec[3], dynupdate_co[3], dynupdate_obmat[4][4];
	bool dynupdate_valid;
	/* Which DYN_LAMP_* bits were actually computed for the cached key above; different
	 * materials on the same lamp can request different subsets, so a cache hit on the key
	 * only lets us skip bits already computed for it. */
	int dynupdate_computed;

	float spotsi, spotbl, k;
	float areasize[2];
	float lampscale[3];
	float dyndist, dynatt1, dynatt2;
	float dist, att1, att2;
	float coeff_const, coeff_lin, coeff_quad;
	float shadow_color[3];

	float bias, slopebias, d, clipend;
	int size;

	int falloff_type;
	struct CurveMapping *curfalloff;

	float winmat[4][4];
	float viewmat[4][4];
	float persmat[4][4];
	float dynpersmat[4][4];

	GPUFrameBuffer *fb;
	GPUFrameBuffer *blurfb;
	GPUTexture *tex;
	GPUTexture *depthtex;
	GPUTexture *blurtex;
	/* Colored shadows: transmittance (rgb) and nearest depth (a) of the Colored Shadows casters,
	 * a second attachment of `fb`. Only made when some material asks for it at lamp creation. */
	GPUTexture *colortex;
	/* colortex holds something other than white (cleared and left white when no caster is drawn). */
	bool color_dirty;
	/* colortex has its own framebuffer at half the shadow size (gpu_lamp_shadow_color_size): no depth
	 * test needed, the depth of the nearest caster is kept in alpha. */
	GPUFrameBuffer *colorfb;

	/* Static shadow cache (Sun/CSM only, see GPU_lamp_shadow_static_*). Holds the depth of the
	 * static shadow casters only, re-rendered rarely (dirty flag or view/win matrix drift beyond
	 * an epsilon); the per-frame dynamic pass then blits this into `fb`'s depth and draws only the
	 * dynamic casters on top, avoiding a full-scene redraw of this cascade every frame. Lazily
	 * allocated -- NULL/false for every lamp that doesn't use the static/dynamic split. */
	GPUFrameBuffer *static_fb;
	GPUTexture *static_depthtex;
	float static_viewmat[4][4];
	float static_winmat[4][4];
	bool static_valid;

	/* Cascaded Shadow Mapping (Sun lamps only). cascade[0] = Medium, cascade[1] = Low.
	 * Each is a full secondary GPULamp sharing this lamp's Object/Lamp pointers, with its own
	 * shadow buffer sized per la->csm_bufsize[i]. This lamp's own fields above serve as the
	 * Near cascade when CSM is enabled -- not registered in ob->gpulamp, owned by this lamp only. */
	struct GPULamp *cascade[2];
	/* Camera-space distance where cascade 0->1 and 1->2 selection switches (Near/Medium/Low).
	 * Set once per frame by the RAS layer alongside the cascade view/win matrices. */
	float cascade_split[2];
	/* 0 = active-camera depth, 1 = square distance in the Sun-local XY plane. */
	float cascade_reference;

	ListBase materials;
};

/* gpu_material_ies.c */
struct GPUTexture *gpu_ies_atlas(void);

#endif /* __GPU_MATERIAL_INTERN_H__ */
