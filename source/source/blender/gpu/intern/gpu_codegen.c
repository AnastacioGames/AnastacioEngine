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

/** \file blender/gpu/intern/gpu_codegen.c
 *  \ingroup gpu
 *
 * Convert material node-trees to GLSL.
 */

#include "MEM_guardedalloc.h"

#include "DNA_customdata_types.h"
#include "DNA_image_types.h"
#include "DNA_material_types.h"

#include "BLI_blenlib.h"
#include "BLI_utildefines.h"
#include "BLI_dynstr.h"
#include "BLI_ghash.h"
#include "BLI_math_base.h"

#include "PIL_time.h"

#include "GPU_extensions.h"
#include "GPU_framebuffer.h"
#include "GPU_glew.h"
#include "GPU_material.h"
#include "GPU_shader.h"
#include "GPU_texture.h"

#include "BLI_sys_types.h" /* for intptr_t support */

#include "gpu_codegen.h"

#include <stdlib.h>
#include <string.h>
#include <stdarg.h>


extern char datatoc_gpu_shader_material_glsl[];
extern char datatoc_gpu_shader_vertex_glsl[];
extern char datatoc_gpu_shader_vertex_world_glsl[];
extern char datatoc_gpu_shader_geometry_glsl[];

static char *glsl_material_library = NULL;
static void glsl_lib_strip_exit(void);

#ifdef __EMSCRIPTEN__
/* GLEW_VERSION_3_0 reflects a queried desktop GL version that Emscripten never
 * populates; the WebGL2/GLES3 shaders this build always targets require the
 * modern in/out/attribute keywords regardless. */
#define GPU_CODEGEN_USE_MODERN_QUALIFIERS true
#else
#define GPU_CODEGEN_USE_MODERN_QUALIFIERS (GLEW_VERSION_3_0)
#endif


/* type definitions and constants */

enum {
	MAX_FUNCTION_NAME = 64,
};
enum {
	MAX_PARAMETER = 32,
};

typedef enum {
	FUNCTION_QUAL_IN,
	FUNCTION_QUAL_OUT,
	FUNCTION_QUAL_INOUT
} GPUFunctionQual;

typedef struct GPUFunction {
	char name[MAX_FUNCTION_NAME];
	GPUType paramtype[MAX_PARAMETER];
	GPUFunctionQual paramqual[MAX_PARAMETER];
	int totparam;
} GPUFunction;

/* Indices match the GPUType enum */
static const char *GPU_DATATYPE_STR[18] = {
	"", "float", "vec2", "vec3", "vec4",
	NULL, NULL, NULL, NULL, "mat3", NULL, NULL, NULL, NULL, NULL, NULL, "mat4", "int"
};
/* Indices match the GPUType size */
static const unsigned int GPU_DATATYPE_SIZE[18] = {
	0, 1, 2, 3, 4, 0, 0, 0, 0, 9, 0, 0, 0, 0, 0, 0, 16, 1
};

/* GLSL code parsing for finding function definitions.
 * These are stored in a hash for lookup when creating a material. */

static GHash *FUNCTION_HASH = NULL;
#if 0
static char *FUNCTION_PROTOTYPES = NULL;
static GPUShader *FUNCTION_LIB = NULL;
#endif

/* Shader cache: materials whose generated code is identical (Mat, Mat.001 differing only in dynamic
 * uniforms, or every material recompiled when a LibLoad merges a lamp) share one compiled program.
 * Per-material values are uploaded on each bind (GPU_pass_bind/GPU_pass_update_uniforms), so sharing
 * the program is safe. Programs left without users stay cached (up to SHADER_CACHE_MAX_UNUSED) so a
 * scene that is freed and opened again, or a material reloaded, finds them compiled. */

typedef struct GPUShaderCacheEntry {
	struct GPUShaderCacheEntry *next, *prev;
	unsigned int hash;
	int flags;
	const char *libcode;
	char *vertexcode, *fragmentcode, *geometrycode;
	GPUShader *shader;
	int users;
	/* Removed from the cache by gpu_codegen_exit while still used: freed with its last user. */
	bool detached;
	unsigned int last_used;
} GPUShaderCacheEntry;

enum {
	SHADER_CACHE_MAX_UNUSED = 256,
};

static ListBase SHADER_CACHE = {NULL, NULL};
static ListBase SHADER_CACHE_DETACHED = {NULL, NULL};
static unsigned int SHADER_CACHE_CLOCK = 0;
static int SHADER_CACHE_UNUSED = 0;
static int SHADER_CACHE_STAT_REUSED = 0;
static int SHADER_CACHE_STAT_COMPILED = 0;
static double SHADER_CACHE_STAT_COMPILE_TIME = 0.0;

void GPU_shader_cache_stats(int *r_reused, int *r_compiled, double *r_compile_seconds, bool reset)
{
	*r_reused = SHADER_CACHE_STAT_REUSED;
	*r_compiled = SHADER_CACHE_STAT_COMPILED;
	*r_compile_seconds = SHADER_CACHE_STAT_COMPILE_TIME;
	if (reset) {
		SHADER_CACHE_STAT_REUSED = 0;
		SHADER_CACHE_STAT_COMPILED = 0;
		SHADER_CACHE_STAT_COMPILE_TIME = 0.0;
	}
}

static bool shader_cache_str_equals(const char *a, const char *b)
{
	return (a == b) || (a && b && STREQ(a, b));
}

static unsigned int shader_cache_hash(const char *vertexcode, const char *fragmentcode, const char *geometrycode, int flags)
{
	unsigned int hash = (unsigned int)flags;
	hash = hash * 31u + (vertexcode ? BLI_ghashutil_strhash_p(vertexcode) : 0u);
	hash = hash * 31u + (fragmentcode ? BLI_ghashutil_strhash_p(fragmentcode) : 0u);
	hash = hash * 31u + (geometrycode ? BLI_ghashutil_strhash_p(geometrycode) : 0u);
	return hash;
}

static void shader_cache_entry_free(GPUShaderCacheEntry *entry)
{
	GPU_shader_free(entry->shader);
	MEM_SAFE_FREE(entry->vertexcode);
	MEM_SAFE_FREE(entry->fragmentcode);
	MEM_SAFE_FREE(entry->geometrycode);
	MEM_freeN(entry);
}

/* RANGE_NO_SHADER_CACHE=1 compiles every material on its own, to compare images with and without sharing. */
static bool shader_cache_enabled(void)
{
	static int enabled = -1;
	if (enabled == -1) {
		const char *env = getenv("RANGE_NO_SHADER_CACHE");
		enabled = !(env && env[0] && env[0] != '0');
	}
	return enabled != 0;
}

/* RANGE_SHADER_UNIFORM_VALUES=1 turns the fixed values of the material (colors, factors) into uniforms
 * instead of constants: materials with the same nodes but other values then share one program, at the
 * cost of the constant folding the compiler did on them.
 * Off by default; a game turns it on with Render > Shader Compilation > Fast Shader Loading (GAME_FAST_SHADER_LOAD,
 * set by the launcher through GPU_material_uniform_values_set). Loading gets much faster (800 spheres: 64 s ->
 * 5 s of shaders, 620 -> 30 programs), but without the folding the GPU redoes the full material math per pixel
 * and per light, and the heavy scene of tools/create_shader_fps_test.py (18 lights) dropped from ~60 to 31 fps.
 * Worth it for games with many materials and few lights; a possible later mode only makes repeated materials
 * uniform. */
static bool shader_uniform_values_game = false;

void GPU_material_uniform_values_set(bool enable)
{
	shader_uniform_values_game = enable;
}

static bool shader_uniform_values_enabled(void)
{
	static int env_enabled = -1;
	if (env_enabled == -1) {
		const char *env = getenv("RANGE_SHADER_UNIFORM_VALUES");
		env_enabled = (env && env[0] && env[0] != '0');
	}
	return shader_uniform_values_game || env_enabled != 0;
}

static bool codegen_input_is_uniform(const GPUInput *input)
{
	return input->dynamicvec ||
	       (shader_uniform_values_enabled() && input->type >= GPU_FLOAT && input->type <= GPU_VEC4);
}

static GPUShader *shader_cache_acquire(const char *vertexcode, const char *fragmentcode, const char *geometrycode,
                                       const char *libcode, int flags, unsigned int hash)
{
	for (GPUShaderCacheEntry *entry = SHADER_CACHE.first; entry; entry = entry->next) {
		if (entry->hash == hash && entry->flags == flags && entry->libcode == libcode &&
		    shader_cache_str_equals(entry->fragmentcode, fragmentcode) &&
		    shader_cache_str_equals(entry->vertexcode, vertexcode) &&
		    shader_cache_str_equals(entry->geometrycode, geometrycode))
		{
			if (entry->users == 0) {
				SHADER_CACHE_UNUSED--;
			}
			entry->users++;
			entry->last_used = ++SHADER_CACHE_CLOCK;
			return entry->shader;
		}
	}
	return NULL;
}

static void shader_cache_add(GPUShader *shader, const char *vertexcode, const char *fragmentcode,
                             const char *geometrycode, const char *libcode, int flags, unsigned int hash)
{
	GPUShaderCacheEntry *entry = MEM_callocN(sizeof(GPUShaderCacheEntry), "GPUShaderCacheEntry");
	entry->hash = hash;
	entry->flags = flags;
	entry->libcode = libcode;
	entry->vertexcode = vertexcode ? BLI_strdup(vertexcode) : NULL;
	entry->fragmentcode = fragmentcode ? BLI_strdup(fragmentcode) : NULL;
	entry->geometrycode = geometrycode ? BLI_strdup(geometrycode) : NULL;
	entry->shader = shader;
	entry->users = 1;
	entry->last_used = ++SHADER_CACHE_CLOCK;
	BLI_addhead(&SHADER_CACHE, entry);
}

static void shader_cache_release(GPUShader *shader)
{
	if (!shader) {
		return;
	}

	for (GPUShaderCacheEntry *entry = SHADER_CACHE.first; entry; entry = entry->next) {
		if (entry->shader != shader) {
			continue;
		}
		if (--entry->users > 0) {
			return;
		}
		SHADER_CACHE_UNUSED++;
		/* Over the limit: free the unused program used longest ago. */
		if (SHADER_CACHE_UNUSED > SHADER_CACHE_MAX_UNUSED) {
			GPUShaderCacheEntry *oldest = NULL;
			for (GPUShaderCacheEntry *e = SHADER_CACHE.first; e; e = e->next) {
				if (e->users == 0 && (!oldest || e->last_used < oldest->last_used)) {
					oldest = e;
				}
			}
			BLI_remlink(&SHADER_CACHE, oldest);
			shader_cache_entry_free(oldest);
			SHADER_CACHE_UNUSED--;
		}
		return;
	}

	for (GPUShaderCacheEntry *entry = SHADER_CACHE_DETACHED.first; entry; entry = entry->next) {
		if (entry->shader == shader) {
			if (--entry->users == 0) {
				BLI_remlink(&SHADER_CACHE_DETACHED, entry);
				shader_cache_entry_free(entry);
			}
			return;
		}
	}

	/* Not created through the cache. */
	GPU_shader_free(shader);
}

/* Frees every unused program; programs still used are freed with their last user. */
static void shader_cache_exit(void)
{
	GPUShaderCacheEntry *next;
	for (GPUShaderCacheEntry *entry = SHADER_CACHE.first; entry; entry = next) {
		next = entry->next;
		BLI_remlink(&SHADER_CACHE, entry);
		if (entry->users == 0) {
			shader_cache_entry_free(entry);
		}
		else {
			entry->detached = true;
			BLI_addtail(&SHADER_CACHE_DETACHED, entry);
		}
	}
	SHADER_CACHE_UNUSED = 0;
}

static int gpu_str_prefix(const char *str, const char *prefix)
{
	while (*str && *prefix) {
		if (*str != *prefix)
			return 0;

		str++;
		prefix++;
	}

	return (*prefix == '\0');
}

static char *gpu_str_skip_token(char *str, char *token, int max)
{
	int len = 0;

	/* skip a variable/function name */
	while (*str) {
		if (ELEM(*str, ' ', '(', ')', ',', '\t', '\n', '\r'))
			break;
		else {
			if (token && len < max - 1) {
				*token = *str;
				token++;
				len++;
			}
			str++;
		}
	}

	if (token)
		*token = '\0';

	/* skip the next special characters:
	 * note the missing ')' */
	while (*str) {
		if (ELEM(*str, ' ', '(', ',', '\t', '\n', '\r'))
			str++;
		else
			break;
	}

	return str;
}

static void gpu_parse_functions_string(GHash *hash, char *code)
{
	GPUFunction *function;
	GPUType type;
	GPUFunctionQual qual;
	int i;

	while ((code = strstr(code, "void "))) {
		function = MEM_callocN(sizeof(GPUFunction), "GPUFunction");

		code = gpu_str_skip_token(code, NULL, 0);
		code = gpu_str_skip_token(code, function->name, MAX_FUNCTION_NAME);

		/* get parameters */
		while (*code && *code != ')') {
			/* test if it's an input or output */
			qual = FUNCTION_QUAL_IN;
			if (gpu_str_prefix(code, "out "))
				qual = FUNCTION_QUAL_OUT;
			if (gpu_str_prefix(code, "inout "))
				qual = FUNCTION_QUAL_INOUT;
			if ((qual != FUNCTION_QUAL_IN) || gpu_str_prefix(code, "in "))
				code = gpu_str_skip_token(code, NULL, 0);

			/* test for type */
			type = GPU_NONE;
			for (i = 1; i < ARRAY_SIZE(GPU_DATATYPE_STR); i++) {
				if (GPU_DATATYPE_STR[i] && gpu_str_prefix(code, GPU_DATATYPE_STR[i])) {
					type = i;
					break;
				}
			}

			if (!type && gpu_str_prefix(code, "samplerCube")) {
				type = GPU_TEXCUBE;
			}
			if (!type && gpu_str_prefix(code, "sampler2DShadow")) {
				type = GPU_SHADOW2D;
			}
			if (!type && gpu_str_prefix(code, "sampler2D")) {
				type = GPU_TEX2D;
			}

			if (type) {
				/* add parameter */
				code = gpu_str_skip_token(code, NULL, 0);
				code = gpu_str_skip_token(code, NULL, 0);
				function->paramqual[function->totparam] = qual;
				function->paramtype[function->totparam] = type;
				function->totparam++;
			}
			else {
				fprintf(stderr, "GPU invalid function parameter in %s.\n", function->name);
				break;
			}
		}

		if (function->name[0] == '\0' || function->totparam == 0) {
			fprintf(stderr, "GPU functions parse error.\n");
			MEM_freeN(function);
			break;
		}

		BLI_ghash_insert(hash, function->name, function);
	}
}

#if 0
static char *gpu_generate_function_prototyps(GHash *hash)
{
	DynStr *ds = BLI_dynstr_new();
	GHashIterator *ghi;
	GPUFunction *function;
	char *name, *prototypes;
	int a;

	/* automatically generate function prototypes to add to the top of the
	 * generated code, to avoid have to add the actual code & recompile all */
	ghi = BLI_ghashIterator_new(hash);

	for (; !BLI_ghashIterator_done(ghi); BLI_ghashIterator_step(ghi)) {
		name = BLI_ghashIterator_getValue(ghi);
		function = BLI_ghashIterator_getValue(ghi);

		BLI_dynstr_appendf(ds, "void %s(", name);
		for (a = 0; a < function->totparam; a++) {
			if (function->paramqual[a] == FUNCTION_QUAL_OUT)
				BLI_dynstr_append(ds, "out ");
			else if (function->paramqual[a] == FUNCTION_QUAL_INOUT)
				BLI_dynstr_append(ds, "inout ");

			if (function->paramtype[a] == GPU_TEX2D)
				BLI_dynstr_append(ds, "sampler2D");
			else if (function->paramtype[a] == GPU_SHADOW2D)
				BLI_dynstr_append(ds, "sampler2DShadow");
			else
				BLI_dynstr_append(ds, GPU_DATATYPE_STR[function->paramtype[a]]);
#  if 0
			BLI_dynstr_appendf(ds, " param%d", a);
#  endif

			if (a != function->totparam - 1)
				BLI_dynstr_append(ds, ", ");
		}
		BLI_dynstr_append(ds, ");\n");
	}

	BLI_dynstr_append(ds, "\n");

	prototypes = BLI_dynstr_get_cstring(ds);
	BLI_dynstr_free(ds);

	return prototypes;
}
#endif

static GPUFunction *gpu_lookup_function(const char *name)
{
	if (!FUNCTION_HASH) {
		FUNCTION_HASH = BLI_ghash_str_new("GPU_lookup_function gh");
		gpu_parse_functions_string(FUNCTION_HASH, glsl_material_library);
	}

	return BLI_ghash_lookup(FUNCTION_HASH, (const void *)name);
}

void gpu_codegen_init(void)
{
	GPU_code_generate_glsl_lib();
}

void gpu_codegen_exit(void)
{
	extern Material defmaterial; /* render module abuse... */

	if (defmaterial.gpumaterial.first)
		GPU_material_free(&defmaterial.gpumaterial);

	if (FUNCTION_HASH) {
		BLI_ghash_free(FUNCTION_HASH, NULL, MEM_freeN);
		FUNCTION_HASH = NULL;
	}

	shader_cache_exit();

	GPU_shader_free_builtin_shaders();
	GPU_framebuffer_blur_free();

	glsl_lib_strip_exit();

	if (glsl_material_library) {
		MEM_freeN(glsl_material_library);
		glsl_material_library = NULL;
	}

#if 0
	if (FUNCTION_PROTOTYPES) {
		MEM_freeN(FUNCTION_PROTOTYPES);
		FUNCTION_PROTOTYPES = NULL;
	}
	if (FUNCTION_LIB) {
		GPU_shader_free(FUNCTION_LIB);
		FUNCTION_LIB = NULL;
	}
#endif
}

/* GLSL code generation */

static void codegen_convert_datatype(DynStr *ds, int from, int to, const char *tmp, int id)
{
	char name[1024];

	BLI_snprintf(name, sizeof(name), "%s%d", tmp, id);

	if (from == to) {
		BLI_dynstr_append(ds, name);
	}
	else if (to == GPU_FLOAT) {
		if (from == GPU_VEC4)
			BLI_dynstr_appendf(ds, "convert_rgba_to_float(%s)", name);
		else if (from == GPU_VEC3)
			BLI_dynstr_appendf(ds, "(%s.r + %s.g + %s.b) / 3.0", name, name, name);
		else if (from == GPU_VEC2)
			BLI_dynstr_appendf(ds, "%s.r", name);
	}
	else if (to == GPU_VEC2) {
		if (from == GPU_VEC4)
			BLI_dynstr_appendf(ds, "vec2((%s.r + %s.g + %s.b) / 3.0, %s.a)", name, name, name, name);
		else if (from == GPU_VEC3)
			BLI_dynstr_appendf(ds, "vec2((%s.r + %s.g + %s.b) / 3.0, 1.0)", name, name, name);
		else if (from == GPU_FLOAT)
			BLI_dynstr_appendf(ds, "vec2(%s, 1.0)", name);
	}
	else if (to == GPU_VEC3) {
		if (from == GPU_VEC4)
			BLI_dynstr_appendf(ds, "%s.rgb", name);
		else if (from == GPU_VEC2)
			BLI_dynstr_appendf(ds, "vec3(%s.r, %s.r, %s.r)", name, name, name);
		else if (from == GPU_FLOAT)
			BLI_dynstr_appendf(ds, "vec3(%s, %s, %s)", name, name, name);
	}
	else {
		if (from == GPU_VEC3)
			BLI_dynstr_appendf(ds, "vec4(%s, 1.0)", name);
		else if (from == GPU_VEC2)
			BLI_dynstr_appendf(ds, "vec4(%s.r, %s.r, %s.r, %s.g)", name, name, name, name);
		else if (from == GPU_FLOAT)
			BLI_dynstr_appendf(ds, "vec4(%s, %s, %s, 1.0)", name, name, name);
	}
}

static void codegen_print_datatype(DynStr *ds, const GPUType type, float *data)
{
	int i;

	BLI_dynstr_appendf(ds, "%s(", GPU_DATATYPE_STR[type]);

	for (i = 0; i < GPU_DATATYPE_SIZE[type]; i++) {
		BLI_dynstr_appendf(ds, "%.12f", data[i]);
		if (i == type - 1)
			BLI_dynstr_append(ds, ")");
		else
			BLI_dynstr_append(ds, ", ");
	}
}

static int codegen_input_has_texture(GPUInput *input)
{
	if (input->link)
		return 0;
	else if (input->ima || input->prv)
		return 1;
	else
		return (input->tex != NULL || input->texptr != NULL);
}

const char *GPU_builtin_name(GPUBuiltin builtin)
{
	if (builtin == GPU_VIEW_MATRIX)
		return "unfviewmat";
	else if (builtin == GPU_PROJECTION_MATRIX)
		return "unfprojmat";
	else if (builtin == GPU_NORMAL_MATRIX)
		return "unfnormalmat";
	else if (builtin == GPU_OBJECT_MATRIX)
		return "unfobmat";
	else if (builtin == GPU_INVERSE_VIEW_MATRIX)
		return "unfinvviewmat";
	else if (builtin == GPU_INVERSE_OBJECT_MATRIX)
		return "unfinvobmat";
	else if (builtin == GPU_LOC_TO_VIEW_MATRIX)
		return "unflocaltoviewmat";
	else if (builtin == GPU_INVERSE_LOC_TO_VIEW_MATRIX)
		return "unfinvlocaltoviewmat";
	else if (builtin == GPU_VIEW_POSITION)
		return "varposition";
	else if (builtin == GPU_VIEW_NORMAL)
		return "varnormal";
	else if (builtin == GPU_OBCOLOR)
		return "unfobcolor";
	else if (builtin == GPU_AUTO_BUMPSCALE)
		return "unfobautobumpscale";
	else if (builtin == GPU_CAMERA_TEXCO_FACTORS)
		return "unfcameratexfactors";
	else if (builtin == GPU_PARTICLE_SCALAR_PROPS)
		return "unfparticlescalarprops";
	else if (builtin == GPU_PARTICLE_LOCATION)
		return "unfparticleco";
	else if (builtin == GPU_PARTICLE_VELOCITY)
		return "unfparticlevel";
	else if (builtin == GPU_PARTICLE_ANG_VELOCITY)
		return "unfparticleangvel";
	else if (builtin == GPU_INSTANCING_MATRIX)
		return "varinstmat";
	else if (builtin == GPU_INSTANCING_INVERSE_MATRIX)
		return "varinstinvmat";
	else if (builtin == GPU_INSTANCING_COLOR)
		return "varinstcolor";
	else if (builtin == GPU_INSTANCING_LAYER)
		return "varinstlayer";
	else if (builtin == GPU_INSTANCING_INFO)
		return "varinstinfo";
	else if (builtin == GPU_INSTANCING_COLOR_ATTRIB)
		return "ininstcolor";
	else if (builtin == GPU_INSTANCING_MATRIX_ATTRIB)
		return "ininstmatrix";
	else if (builtin == GPU_INSTANCING_POSITION_ATTRIB)
		return "ininstposition";
	else if (builtin == GPU_INSTANCING_LAYER_ATTRIB)
		return "ininstlayer";
	else if (builtin == GPU_INSTANCING_INFO_ATTRIB)
		return "ininstinfo";
	else if (builtin == GPU_TIME)
		return "unftime";
	else if (builtin == GPU_OBJECT_INFO)
		return "unfobjectinfo";
	else if (builtin == GPU_OBJECT_LAY)
		return "unfobjectlay";
	else if (builtin == GPU_VERTEX_ID)
		return "varvertexid";
	else if (builtin == GPU_BARYCENTRIC)
		return "varbarycentric";
	else
		return "";
}

/* assign only one texid per buffer to avoid sampling the same texture twice */
static void codegen_set_texid(GHash *bindhash, GPUInput *input, int *texid, void *key)
{
	if (BLI_ghash_haskey(bindhash, key)) {
		/* Reuse existing texid */
		input->texid = POINTER_AS_INT(BLI_ghash_lookup(bindhash, key));
	}
	else {
		/* Allocate new texid */
		input->texid = *texid;
		(*texid)++;
		input->bindtex = true;
		BLI_ghash_insert(bindhash, key, POINTER_FROM_INT(input->texid));
	}
}

static void codegen_set_unique_ids(ListBase *nodes)
{
	GHash *bindhash, *definehash;
	GPUNode *node;
	GPUInput *input;
	GPUOutput *output;
	int id = 1, texid = 0;

	bindhash = BLI_ghash_ptr_new("codegen_set_unique_ids1 gh");
	definehash = BLI_ghash_ptr_new("codegen_set_unique_ids2 gh");

	for (node = nodes->first; node; node = node->next) {
		for (input = node->inputs.first; input; input = input->next) {
			/* set id for unique names of uniform variables */
			input->id = id++;
			input->bindtex = false;
			input->definetex = false;

			/* set texid used for settings texture slot with multitexture */
			if (codegen_input_has_texture(input) &&
			    ((input->source == GPU_SOURCE_TEX) || (input->source == GPU_SOURCE_TEX_PIXEL)))
			{
				/* assign only one texid per buffer to avoid sampling
				 * the same texture twice */
				if (input->link) {
					/* input is texture from buffer */
					codegen_set_texid(bindhash, input, &texid, input->link);
				}
				else if (input->ima) {
					/* input is texture from image */
					codegen_set_texid(bindhash, input, &texid, input->ima);
				}
				else if (input->prv) {
					/* input is texture from preview render */
					codegen_set_texid(bindhash, input, &texid, input->prv);
				}
				else if (input->tex) {
					/* input is user created texture, check tex pointer */
					codegen_set_texid(bindhash, input, &texid, input->tex);
				}
				else if (input->texptr) {
					/* input is user created texture, check tex pointer */
					codegen_set_texid(bindhash, input, &texid, input->texptr);
				}

				/* make sure this pixel is defined exactly once */
				if (input->source == GPU_SOURCE_TEX_PIXEL) {
					if (input->ima) {
						if (!BLI_ghash_haskey(definehash, input->ima)) {
							input->definetex = true;
							BLI_ghash_insert(definehash, input->ima, POINTER_FROM_INT(input->texid));
						}
					}
					else {
						if (!BLI_ghash_haskey(definehash, input->link)) {
							input->definetex = true;
							BLI_ghash_insert(definehash, input->link, POINTER_FROM_INT(input->texid));
						}
					}
				}
			}
		}

		for (output = node->outputs.first; output; output = output->next)
			/* set id for unique names of tmp variables storing output */
			output->id = id++;
	}

	BLI_ghash_free(bindhash, NULL, NULL);
	BLI_ghash_free(definehash, NULL, NULL);
}

static int codegen_print_uniforms_functions(DynStr *ds, ListBase *nodes)
{
	GPUNode *node;
	GPUInput *input;
	const char *name;
	int builtins = 0;

	/* print uniforms */
	for (node = nodes->first; node; node = node->next) {
		for (input = node->inputs.first; input; input = input->next) {
			if ((input->source == GPU_SOURCE_TEX) || (input->source == GPU_SOURCE_TEX_PIXEL)) {
				/* create exactly one sampler for each texture */
				if (codegen_input_has_texture(input) && input->bindtex) {
					BLI_dynstr_appendf(ds, "uniform %s samp%d;\n",
						(input->textype == GPU_TEX2D) ? "sampler2D" :
						(input->textype == GPU_TEXCUBE) ? "samplerCube" : "sampler2DShadow",
						input->texid);
				}
			}
			else if (input->source == GPU_SOURCE_BUILTIN) {
				/* only define each builtin uniform/varying once */
				if (!(builtins & input->builtin)) {
					builtins |= input->builtin;
					name = GPU_builtin_name(input->builtin);

					if (gpu_str_prefix(name, "unf")) {
#ifdef WITH_GL_PROFILE_CORE
						/* unfviewmat/unfobmat/unfprojmat/unfnormalmat are already declared
						 * unconditionally by gpu_shader_vertex.glsl/gpu_shader_material.glsl
						 * under core profile (see gpu_material.c's forced builtins) -- codegen
						 * declaring them again here for a material that also references them
						 * as a texture-coordinate/mapping input produces a duplicate-declaration
						 * compile error in that shader stage. */
						bool builtinAlreadyDeclared = ELEM(input->builtin,
						                                    GPU_VIEW_MATRIX, GPU_OBJECT_MATRIX,
						                                    GPU_PROJECTION_MATRIX, GPU_NORMAL_MATRIX);
						if (!builtinAlreadyDeclared)
#endif
						{
							BLI_dynstr_appendf(ds, "uniform %s %s;\n",
								GPU_DATATYPE_STR[input->type], name);
						}
					}
					else {
						// GPU_INSTANCING_LAYER is an integer, it must be flat in GLSL.
						if (input->builtin == GPU_INSTANCING_LAYER) {
							BLI_dynstr_appendf(ds, "%s %s %s;\n",
								GPU_CODEGEN_USE_MODERN_QUALIFIERS ? "flat in" : "flat varying",
								GPU_DATATYPE_STR[input->type], name);
						}
						else {
							BLI_dynstr_appendf(ds, "%s %s %s;\n",
								GPU_CODEGEN_USE_MODERN_QUALIFIERS ? "in" : "varying",
								GPU_DATATYPE_STR[input->type], name);
						}
					}
				}
			}
			else if (input->source == GPU_SOURCE_VEC_UNIFORM) {
				if (codegen_input_is_uniform(input)) {
					/* only create uniforms for dynamic vectors */
					BLI_dynstr_appendf(ds, "uniform %s unf%d;\n",
						GPU_DATATYPE_STR[input->type], input->id);
				}
				else {
					/* for others use const so the compiler can do folding */
					BLI_dynstr_appendf(ds, "const %s cons%d = ",
						GPU_DATATYPE_STR[input->type], input->id);
					codegen_print_datatype(ds, input->type, input->vec);
					BLI_dynstr_append(ds, ";\n");
				}
			}
			else if (input->source == GPU_SOURCE_ATTRIB && input->attribfirst) {
#ifdef WITH_OPENSUBDIV
				bool skip_opensubdiv = input->attribtype == CD_TANGENT;
				if (skip_opensubdiv) {
					BLI_dynstr_appendf(ds, "#ifndef USE_OPENSUBDIV\n");
				}
#endif
				BLI_dynstr_appendf(ds, "%s %s var%d;\n",
					GPU_CODEGEN_USE_MODERN_QUALIFIERS ? "in" : "varying",
					GPU_DATATYPE_STR[input->type], input->attribid);
#ifdef WITH_OPENSUBDIV
				if (skip_opensubdiv) {
					BLI_dynstr_appendf(ds, "#endif\n");
				}
#endif
			}
		}
	}

	BLI_dynstr_append(ds, "\n");

	return builtins;
}

static void codegen_declare_tmps(DynStr *ds, ListBase *nodes)
{
	GPUNode *node;
	GPUInput *input;
	GPUOutput *output;

	for (node = nodes->first; node; node = node->next) {
		/* load pixels from textures */
		for (input = node->inputs.first; input; input = input->next) {
			if (input->source == GPU_SOURCE_TEX_PIXEL) {
				if (codegen_input_has_texture(input) && input->definetex) {
					BLI_dynstr_appendf(ds, "\tvec4 tex%d = texture2D(", input->texid);
					BLI_dynstr_appendf(ds, "samp%d, gl_TexCoord[%d].st);\n",
					                   input->texid, input->texid);
				}
			}
		}

		/* declare temporary variables for node output storage */
		for (output = node->outputs.first; output; output = output->next) {
			BLI_dynstr_appendf(ds, "\t%s tmp%d;\n",
			                   GPU_DATATYPE_STR[output->type], output->id);
		}
	}

	BLI_dynstr_append(ds, "\n");
}

static void codegen_call_functions(DynStr *ds, ListBase *nodes, GPUNodeLink *finaloutputs[8])
{
	GPUNode *node;
	GPUInput *input;
	GPUOutput *output;

	for (node = nodes->first; node; node = node->next) {
		BLI_dynstr_appendf(ds, "\t%s(", node->name);

		for (input = node->inputs.first; input; input = input->next) {
			if (input->source == GPU_SOURCE_TEX) {
				BLI_dynstr_appendf(ds, "samp%d", input->texid);
				if (input->link)
					BLI_dynstr_appendf(ds, ", gl_TexCoord[%d].st", input->texid);
			}
			else if (input->source == GPU_SOURCE_TEX_PIXEL) {
				codegen_convert_datatype(ds, input->link->output->type, input->type,
					"tmp", input->link->output->id);
			}
			else if (input->source == GPU_SOURCE_BUILTIN) {
				if (input->builtin == GPU_VIEW_NORMAL)
					BLI_dynstr_append(ds, "facingnormal");
				else
					BLI_dynstr_append(ds, GPU_builtin_name(input->builtin));
			}
			else if (input->source == GPU_SOURCE_VEC_UNIFORM) {
				if (codegen_input_is_uniform(input))
					BLI_dynstr_appendf(ds, "unf%d", input->id);
				else
					BLI_dynstr_appendf(ds, "cons%d", input->id);
			}
			else if (input->source == GPU_SOURCE_ATTRIB) {
				BLI_dynstr_appendf(ds, "var%d", input->attribid);
			}
			else if (input->source == GPU_SOURCE_OPENGL_BUILTIN) {
				if (input->oglbuiltin == GPU_MATCAP_NORMAL)
					BLI_dynstr_append(ds, "gl_SecondaryColor");
				else if (input->oglbuiltin == GPU_COLOR)
					BLI_dynstr_append(ds, "gl_Color");
			}

			BLI_dynstr_append(ds, ", ");
		}

		for (output = node->outputs.first; output; output = output->next) {
			BLI_dynstr_appendf(ds, "tmp%d", output->id);
			if (output->next)
				BLI_dynstr_append(ds, ", ");
		}

		BLI_dynstr_append(ds, ");\n");

		if (STREQ(node->name, "user_get")) {
			BLI_dynstr_appendf(ds, "\tfragment();\n");
		}
	}

	for (unsigned short i = 0; i < 8; ++i) {
		if (finaloutputs[i]) {
			output = finaloutputs[i]->output;
			if (GPU_CODEGEN_USE_MODERN_QUALIFIERS)
				BLI_dynstr_appendf(ds, "\n\tfragData%i = ", i);
			else
				BLI_dynstr_appendf(ds, "\n\tgl_FragData[%i] = ", i);
			codegen_convert_datatype(ds, output->type, GPU_VEC4, "tmp", output->id);
			BLI_dynstr_append(ds, ";\n");
		}
	}
}

static char *code_generate_fragment(ListBase *nodes, const char *usercode, const GPUMatType type, GPUNodeLink *outputs[8])
{
	DynStr *ds = BLI_dynstr_new();
	char *code;
	int builtins;

#ifdef WITH_OPENSUBDIV
	GPUNode *node;
	GPUInput *input;
#endif


#if 0
	BLI_dynstr_append(ds, FUNCTION_PROTOTYPES);
#endif

	codegen_set_unique_ids(nodes);
	builtins = codegen_print_uniforms_functions(ds, nodes);

	if (GPU_CODEGEN_USE_MODERN_QUALIFIERS) {
		/* GLES3/WebGL2 has no gl_FragData; declare explicit output(s) instead.
		 * An explicit location is mandatory here: without it, GLSL ES assigns
		 * locations by declaration order starting at 0, which mismatches the
		 * active draw buffers (glDrawBuffers) whenever the output index isn't
		 * contiguous from 0, and ANGLE rejects the draw with "Active draw
		 * buffers with missing fragment shader outputs". */
		for (int i = 0; i < 8; ++i) {
			if (outputs[i]) {
				BLI_dynstr_appendf(ds, "layout(location = %d) out vec4 fragData%d;\n", i, i);
			}
		}
	}

	if (usercode) {
		BLI_dynstr_append(ds, "void fragment();\n\n");
	}
#if 0
	if (G.debug & G_DEBUG)
		BLI_dynstr_appendf(ds, "/* %s */\n", name);
#endif

	BLI_dynstr_append(ds, "void main()\n{\n");

	if (builtins & GPU_VIEW_NORMAL)
		BLI_dynstr_append(ds, "\tvec3 facingnormal = gl_FrontFacing? varnormal: -varnormal;\n");

	/* Calculate tangent space. */
#ifdef WITH_OPENSUBDIV
	{
		bool has_tangent = false;
		for (node = nodes->first; node; node = node->next) {
			for (input = node->inputs.first; input; input = input->next) {
				if (input->source == GPU_SOURCE_ATTRIB && input->attribfirst) {
					if (input->attribtype == CD_TANGENT) {
						BLI_dynstr_appendf(ds, "#ifdef USE_OPENSUBDIV\n");
						BLI_dynstr_appendf(ds, "\t%s var%d;\n",
						                   GPU_DATATYPE_STR[input->type],
						                   input->attribid);
						if (has_tangent == false) {
							BLI_dynstr_appendf(ds, "\tvec3 Q1 = dFdx(inpt.v.position.xyz);\n");
							BLI_dynstr_appendf(ds, "\tvec3 Q2 = dFdy(inpt.v.position.xyz);\n");
							BLI_dynstr_appendf(ds, "\tvec2 st1 = dFdx(inpt.v.uv);\n");
							BLI_dynstr_appendf(ds, "\tvec2 st2 = dFdy(inpt.v.uv);\n");
							BLI_dynstr_appendf(ds, "\tvec3 T = normalize(Q1 * st2.t - Q2 * st1.t);\n");
						}
						BLI_dynstr_appendf(ds, "\tvar%d = vec4(T, 1.0);\n", input->attribid);
						BLI_dynstr_appendf(ds, "#endif\n");
					}
				}
			}
		}
	}
#endif

	codegen_declare_tmps(ds, nodes);
	codegen_call_functions(ds, nodes, outputs);

	BLI_dynstr_append(ds, "}\n");

	if (usercode) {
		BLI_dynstr_append(ds, "\n");
		BLI_dynstr_append(ds, usercode);
	}

	/* create shader */
	code = BLI_dynstr_get_cstring(ds);
	BLI_dynstr_free(ds);

#if 0
	if (G.debug & G_DEBUG) printf("%s\n", code);
#endif

	return code;
}

static char *code_generate_vertex(ListBase *nodes, const char *usercode, const GPUMatType type, bool use_instancing)
{
	DynStr *ds = BLI_dynstr_new();
	GPUNode *node;
	GPUInput *input;
	char *code;
	char *vertcode = NULL;

	for (node = nodes->first; node; node = node->next) {
		for (input = node->inputs.first; input; input = input->next) {
			if (input->source == GPU_SOURCE_ATTRIB && input->attribfirst) {
#ifdef WITH_OPENSUBDIV
				bool skip_opensubdiv = ELEM(input->attribtype, CD_MTFACE, CD_TANGENT);
				if (skip_opensubdiv) {
					BLI_dynstr_appendf(ds, "#ifndef USE_OPENSUBDIV\n");
				}
#endif
				BLI_dynstr_appendf(ds, "%s %s att%d;\n",
					GPU_CODEGEN_USE_MODERN_QUALIFIERS ? "in" : "attribute",
					GPU_DATATYPE_STR[input->type], input->attribid);
				BLI_dynstr_appendf(ds, "uniform int att%d_info;\n",  input->attribid);
				BLI_dynstr_appendf(ds, "%s %s var%d;\n",
					GPU_CODEGEN_USE_MODERN_QUALIFIERS ? "out" : "varying",
					GPU_DATATYPE_STR[input->type], input->attribid);
#ifdef WITH_OPENSUBDIV
				if (skip_opensubdiv) {
					BLI_dynstr_appendf(ds, "#endif\n");
				}
#endif
			}
		}
	}

	BLI_dynstr_append(ds, "\n");
	if (usercode) {
		for (node = nodes->first; node; node = node->next) {
			for (input = node->inputs.first; input; input = input->next) {
				if (input->source == GPU_SOURCE_ATTRIB && input->attribfirst) {
					if (input->attribtype == CD_MTFACE && input->type == 2)
						BLI_dynstr_appendf(ds, "#ifndef UV\n#define UV att%d\n#endif\n", input->attribid);
					if (input->attribtype == CD_ORCO && input->type == 3)
						BLI_dynstr_appendf(ds, "#ifndef ORCO\n#define ORCO att%d\n#endif\n", input->attribid);
					if (input->attribtype == CD_TANGENT && input->type == 4)
						BLI_dynstr_appendf(ds, "#ifndef TANGENT\n#define TANGENT att%d\n#endif\n", input->attribid);
					if (input->attribtype == CD_MCOL && input->type == 4)
						BLI_dynstr_appendf(ds, "#ifndef COLOR\n#define COLOR att%d\n#endif\n", input->attribid);
				}
			}
		}
	}

	switch (type) {
		case GPU_MATERIAL_TYPE_MESH:
			vertcode = datatoc_gpu_shader_vertex_glsl;
			break;
		case GPU_MATERIAL_TYPE_WORLD:
			vertcode = datatoc_gpu_shader_vertex_world_glsl;
			break;
		default:
			fprintf(stderr, "invalid material type, set one after GPU_material_construct_begin\n");
			break;
	}

	BLI_dynstr_append(ds, vertcode);

	for (node = nodes->first; node; node = node->next)
		for (input = node->inputs.first; input; input = input->next)
			if (input->source == GPU_SOURCE_ATTRIB && input->attribfirst) {
				if (input->attribtype == CD_TANGENT) { /* silly exception */
#ifdef WITH_OPENSUBDIV
					BLI_dynstr_appendf(ds, "#ifndef USE_OPENSUBDIV\n");
#endif
					if (use_instancing) {
						BLI_dynstr_appendf(
							ds, "\tvar%d.xyz = normalize(gl_NormalMatrix * (att%d.xyz * %s));\n",
							input->attribid, input->attribid, GPU_builtin_name(GPU_INSTANCING_MATRIX_ATTRIB));
					}
					else {
						BLI_dynstr_appendf(
							ds, "\tvar%d.xyz = normalize(gl_NormalMatrix * att%d.xyz);\n",
							input->attribid, input->attribid);
					}
					BLI_dynstr_appendf(
					        ds, "\tvar%d.w = att%d.w;\n",
					        input->attribid, input->attribid);
#ifdef WITH_OPENSUBDIV
					BLI_dynstr_appendf(ds, "#endif\n");
#endif
				}
				else {
#ifdef WITH_OPENSUBDIV
					bool is_mtface = input->attribtype == CD_MTFACE;
					if (is_mtface) {
						BLI_dynstr_appendf(ds, "#ifndef USE_OPENSUBDIV\n");
					}
#endif
					BLI_dynstr_appendf(ds, "\tset_var_from_attr(att%d, att%d_info, var%d);\n",
					                   input->attribid, input->attribid, input->attribid);
#ifdef WITH_OPENSUBDIV
					if (is_mtface) {
						BLI_dynstr_appendf(ds, "#endif\n");
					}
#endif
				}
			}
			/* unfortunately special handling is needed here because we abuse gl_Color/gl_SecondaryColor flat shading */
			else if (input->source == GPU_SOURCE_OPENGL_BUILTIN) {
				if (input->oglbuiltin == GPU_MATCAP_NORMAL) {
					/* remap to 0.0 - 1.0 range. This is done because OpenGL 2.0 clamps colors
					 * between shader stages and we want the full range of the normal */
					BLI_dynstr_appendf(ds, "\tvec3 matcapcol = vec3(0.5) * varnormal + vec3(0.5);\n");
					BLI_dynstr_appendf(ds, "\tgl_FrontSecondaryColor = vec4(matcapcol, 1.0);\n");
				}
				else if (input->oglbuiltin == GPU_COLOR) {
					BLI_dynstr_appendf(ds, "\tgl_FrontColor = gl_Color;\n");
				}
			}

	BLI_dynstr_append(ds, "}\n");

	if (usercode && type == GPU_MATERIAL_TYPE_MESH) {
		BLI_dynstr_append(ds, "\n"
			"#define VIEW_MATRIX unfviewmat\n"
			"#define MODEL_MATRIX unfobmat\n"
			"#define VERTEX_ID varvertexid\n\n"
		);
		BLI_dynstr_append(ds, usercode);
	}

	code = BLI_dynstr_get_cstring(ds);

	BLI_dynstr_free(ds);

#if 0
	if (G.debug & G_DEBUG) printf("%s\n", code);
#endif

	return code;
}

static char *code_generate_geometry(ListBase *nodes, bool use_opensubdiv)
{
#ifdef WITH_OPENSUBDIV
	if (use_opensubdiv) {
		DynStr *ds = BLI_dynstr_new();
		GPUNode *node;
		GPUInput *input;
		char *code;

		/* Generate varying declarations. */
		for (node = nodes->first; node; node = node->next) {
			for (input = node->inputs.first; input; input = input->next) {
				if (input->source == GPU_SOURCE_ATTRIB && input->attribfirst) {
					if (input->attribtype == CD_MTFACE) {
						/* NOTE: For now we are using varying on purpose,
						 * otherwise we are not able to write to the varying.
						 */
						BLI_dynstr_appendf(ds, "%s %s var%d%s;\n",
						                   "varying",
						                   GPU_DATATYPE_STR[input->type],
						                   input->attribid,
						                   "");
						BLI_dynstr_appendf(ds, "uniform int fvar%d_offset;\n",
						                   input->attribid);
					}
				}
			}
		}

		BLI_dynstr_append(ds, datatoc_gpu_shader_geometry_glsl);

		/* Generate varying assignments. */
		for (node = nodes->first; node; node = node->next) {
			for (input = node->inputs.first; input; input = input->next) {
				if (input->source == GPU_SOURCE_ATTRIB && input->attribfirst) {
					if (input->attribtype == CD_MTFACE) {
						BLI_dynstr_appendf(
						        ds,
						        "\tINTERP_FACE_VARYING_ATT_2(var%d, "
						        "int(texelFetch(FVarDataOffsetBuffer, fvar%d_offset).r), st);\n",
						        input->attribid,
						        input->attribid);
					}
				}
			}
		}

		BLI_dynstr_append(ds, "}\n");
		code = BLI_dynstr_get_cstring(ds);
		BLI_dynstr_free(ds);

		//if (G.debug & G_DEBUG) printf("%s\n", code);

		return code;
	}
#else
	UNUSED_VARS(nodes, use_opensubdiv);
#endif
	return NULL;
}

/* GLSL library stripping: the material library (~200 KB) used to go whole into every fragment shader,
 * so the driver parsed and compiled all of it per material. The library is split once into top-level
 * chunks; only function definitions can be left out. Preprocessor lines, uniforms, structs and constants
 * always stay, and functions are grouped by name so every overload of a called function is kept (the
 * preprocessor still picks between #ifdef variants). A shader gets the functions its fragment code
 * reaches, directly or through other library functions. RANGE_NO_GLSL_STRIP=1 sends the whole library. */

typedef struct GLSLLibChunk {
	int start, end;
	int group; /* Function name group, -1 for chunks that are always kept. */
} GLSLLibChunk;

static GLSLLibChunk *GLSL_LIB_CHUNKS = NULL;
static int GLSL_LIB_CHUNKS_LEN = 0;
static GHash *GLSL_LIB_GROUPS = NULL; /* Function name -> group index + 1. */
static int GLSL_LIB_GROUPS_LEN = 0;
static int **GLSL_LIB_GROUP_DEPS = NULL; /* Groups called by each group. */
static int *GLSL_LIB_GROUP_DEPS_LEN = NULL;
static char *GLSL_LIB_ROOTS = NULL; /* Groups referenced by chunks that are always kept. */

static bool glsl_lib_strip_enabled(void)
{
	static int enabled = -1;
	if (enabled == -1) {
		const char *env = getenv("RANGE_NO_GLSL_STRIP");
		enabled = !(env && env[0] && env[0] != '0');
	}
	return enabled != 0;
}

static bool glsl_ident_start(char c)
{
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
}

static bool glsl_ident_char(char c)
{
	return glsl_ident_start(c) || (c >= '0' && c <= '9');
}

/* True when only spaces or tabs precede text[i] on its line (preprocessor lines may be indented). */
static bool glsl_at_line_start(const char *text, int i)
{
	while (i > 0 && (text[i - 1] == ' ' || text[i - 1] == '\t')) {
		i--;
	}
	return i == 0 || text[i - 1] == '\n';
}

/* Skips a comment starting at text[i]; returns the index after it, or i when there is none. */
static int glsl_skip_comment(const char *text, int i, int end)
{
	if (i + 1 < end && text[i] == '/' && text[i + 1] == '/') {
		while (i < end && text[i] != '\n') {
			i++;
		}
	}
	else if (i + 1 < end && text[i] == '/' && text[i + 1] == '*') {
		i += 2;
		while (i + 1 < end && !(text[i] == '*' && text[i + 1] == '/')) {
			i++;
		}
		i = min_ii(i + 2, end);
	}
	return i;
}

/* Calls fn for every identifier in text[start, end), comments and number literals skipped. */
static void glsl_foreach_ident(const char *text, int start, int end,
                               void (*fn)(const char *ident, int len, void *data), void *data)
{
	int i = start;
	while (i < end) {
		const int after = glsl_skip_comment(text, i, end);
		if (after != i) {
			i = after;
		}
		else if (glsl_ident_start(text[i])) {
			const int s = i;
			while (i < end && glsl_ident_char(text[i])) {
				i++;
			}
			fn(text + s, i - s, data);
		}
		else if (text[i] >= '0' && text[i] <= '9') {
			while (i < end && (glsl_ident_char(text[i]) || text[i] == '.')) {
				i++;
			}
		}
		else {
			i++;
		}
	}
}

static int glsl_lib_group_lookup(const char *ident, int len)
{
	char name[128];
	if (len >= (int)sizeof(name)) {
		return -1;
	}
	memcpy(name, ident, len);
	name[len] = '\0';
	return POINTER_AS_INT(BLI_ghash_lookup(GLSL_LIB_GROUPS, name)) - 1;
}

/* Name of the function a chunk header defines ("vec3 foo(..." -> foo), or false when it is no function
 * (struct, initializer). */
static bool glsl_header_function_name(const char *text, int start, int end, char *r_name, int name_size)
{
	for (int i = start; i < end;) {
		const int after = glsl_skip_comment(text, i, end);
		if (after != i) {
			i = after;
			continue;
		}
		if (glsl_ident_start(text[i])) {
			const int s = i;
			while (i < end && glsl_ident_char(text[i])) {
				i++;
			}
			if (i - s == 6 && STREQLEN(text + s, "struct", 6)) {
				return false;
			}
			int j = i;
			while (j < end && (text[j] == ' ' || text[j] == '\t' || text[j] == '\n' || text[j] == '\r')) {
				j++;
			}
			if (j < end && text[j] == '(') {
				if (i - s >= name_size) {
					return false;
				}
				memcpy(r_name, text + s, i - s);
				r_name[i - s] = '\0';
				return true;
			}
			continue;
		}
		i++;
	}
	return false;
}

static void glsl_lib_add_chunk(int start, int end, int group, int *capacity)
{
	if (end <= start) {
		return;
	}
	if (GLSL_LIB_CHUNKS_LEN == *capacity) {
		*capacity = max_ii(*capacity * 2, 256);
		GLSL_LIB_CHUNKS = MEM_reallocN(GLSL_LIB_CHUNKS, sizeof(GLSLLibChunk) * (*capacity));
	}
	GLSLLibChunk *chunk = &GLSL_LIB_CHUNKS[GLSL_LIB_CHUNKS_LEN++];
	chunk->start = start;
	chunk->end = end;
	chunk->group = group;
}

static int glsl_lib_group_for_name(const char *name)
{
	void *value = BLI_ghash_lookup(GLSL_LIB_GROUPS, name);
	if (value) {
		return POINTER_AS_INT(value) - 1;
	}
	BLI_ghash_insert(GLSL_LIB_GROUPS, BLI_strdup(name), POINTER_FROM_INT(GLSL_LIB_GROUPS_LEN + 1));
	return GLSL_LIB_GROUPS_LEN++;
}

typedef struct GLSLDepCollect {
	char *seen;
	int *list;
	int len;
} GLSLDepCollect;

static void glsl_collect_dep(const char *ident, int len, void *data)
{
	GLSLDepCollect *collect = data;
	const int group = glsl_lib_group_lookup(ident, len);
	if (group >= 0 && !collect->seen[group]) {
		collect->seen[group] = 1;
		collect->list[collect->len++] = group;
	}
}

static void glsl_lib_strip_init(const char *lib)
{
	const int len = (int)strlen(lib);
	int capacity = 0;
	int seg = 0, depth = 0, header_end = 0;
	char name[128];

	GLSL_LIB_GROUPS = BLI_ghash_str_new("glsl lib groups");

	for (int i = 0; i < len;) {
		const int after = glsl_skip_comment(lib, i, len);
		if (after != i) {
			i = after;
			continue;
		}
		const char c = lib[i];
		if (depth == 0 && c == '#' && glsl_at_line_start(lib, i)) {
			/* A preprocessor line between definitions is a chunk of its own, always kept. */
			bool blank = true;
			for (int k = seg; k < i;) {
				const int skip = glsl_skip_comment(lib, k, i);
				if (skip != k) {
					k = skip;
				}
				else if (ELEM(lib[k], ' ', '\t', '\n', '\r')) {
					k++;
				}
				else {
					blank = false;
					break;
				}
			}
			int e = i;
			while (e < len && !(lib[e] == '\n' && lib[e - 1] != '\\')) {
				e++;
			}
			e = min_ii(e + 1, len);
			if (blank) {
				glsl_lib_add_chunk(seg, e, -1, &capacity);
				seg = e;
			}
			i = e;
			continue;
		}
		if (c == '{') {
			if (depth++ == 0) {
				header_end = i;
			}
		}
		else if (c == '}' && depth > 0) {
			if (--depth == 0) {
				int e = i + 1;
				int k = e;
				while (k < len && ELEM(lib[k], ' ', '\t', '\r')) {
					k++;
				}
				if (k < len && lib[k] == ';') {
					/* struct {...}; or an initializer: always kept. */
					glsl_lib_add_chunk(seg, k + 1, -1, &capacity);
					seg = i = k + 1;
					continue;
				}
				const int group = glsl_header_function_name(lib, seg, header_end, name, sizeof(name)) ?
				                  glsl_lib_group_for_name(name) : -1;
				glsl_lib_add_chunk(seg, e, group, &capacity);
				seg = e;
			}
		}
		else if (c == ';' && depth == 0) {
			glsl_lib_add_chunk(seg, i + 1, -1, &capacity);
			seg = i + 1;
		}
		i++;
	}
	glsl_lib_add_chunk(seg, len, -1, &capacity);

	/* Dependencies between function groups, and the groups that kept chunks reference. */
	const int groups = max_ii(GLSL_LIB_GROUPS_LEN, 1);
	GLSL_LIB_GROUP_DEPS = MEM_callocN(sizeof(int *) * groups, "glsl lib deps");
	GLSL_LIB_GROUP_DEPS_LEN = MEM_callocN(sizeof(int) * groups, "glsl lib deps len");
	GLSL_LIB_ROOTS = MEM_callocN(groups, "glsl lib roots");

	GLSLDepCollect collect;
	collect.seen = MEM_callocN(groups, "glsl dep seen");
	collect.list = MEM_mallocN(sizeof(int) * groups, "glsl dep list");

	for (int g = 0; g < GLSL_LIB_GROUPS_LEN; g++) {
		memset(collect.seen, 0, groups);
		collect.seen[g] = 1; /* No self edge. */
		collect.len = 0;
		for (int c = 0; c < GLSL_LIB_CHUNKS_LEN; c++) {
			if (GLSL_LIB_CHUNKS[c].group == g) {
				glsl_foreach_ident(lib, GLSL_LIB_CHUNKS[c].start, GLSL_LIB_CHUNKS[c].end, glsl_collect_dep, &collect);
			}
		}
		if (collect.len) {
			GLSL_LIB_GROUP_DEPS[g] = MEM_mallocN(sizeof(int) * collect.len, "glsl group deps");
			memcpy(GLSL_LIB_GROUP_DEPS[g], collect.list, sizeof(int) * collect.len);
			GLSL_LIB_GROUP_DEPS_LEN[g] = collect.len;
		}
	}

	memset(collect.seen, 0, groups);
	collect.len = 0;
	for (int c = 0; c < GLSL_LIB_CHUNKS_LEN; c++) {
		if (GLSL_LIB_CHUNKS[c].group == -1) {
			glsl_foreach_ident(lib, GLSL_LIB_CHUNKS[c].start, GLSL_LIB_CHUNKS[c].end, glsl_collect_dep, &collect);
		}
	}
	for (int k = 0; k < collect.len; k++) {
		GLSL_LIB_ROOTS[collect.list[k]] = 1;
	}

	MEM_freeN(collect.seen);
	MEM_freeN(collect.list);
}

static void glsl_lib_strip_exit(void)
{
	if (GLSL_LIB_GROUPS) {
		BLI_ghash_free(GLSL_LIB_GROUPS, MEM_freeN, NULL);
		GLSL_LIB_GROUPS = NULL;
	}
	if (GLSL_LIB_GROUP_DEPS) {
		for (int g = 0; g < GLSL_LIB_GROUPS_LEN; g++) {
			MEM_SAFE_FREE(GLSL_LIB_GROUP_DEPS[g]);
		}
		MEM_freeN(GLSL_LIB_GROUP_DEPS);
		GLSL_LIB_GROUP_DEPS = NULL;
	}
	MEM_SAFE_FREE(GLSL_LIB_GROUP_DEPS_LEN);
	MEM_SAFE_FREE(GLSL_LIB_ROOTS);
	MEM_SAFE_FREE(GLSL_LIB_CHUNKS);
	GLSL_LIB_CHUNKS_LEN = 0;
	GLSL_LIB_GROUPS_LEN = 0;
}

/* The library reduced to what fragmentcode uses; NULL means use the whole library. */
static char *glsl_lib_strip(const char *fragmentcode)
{
	if (!fragmentcode || !glsl_material_library || !glsl_lib_strip_enabled()) {
		return NULL;
	}
	if (!GLSL_LIB_GROUPS) {
		glsl_lib_strip_init(glsl_material_library);
	}

	const int groups = max_ii(GLSL_LIB_GROUPS_LEN, 1);
	GLSLDepCollect collect;
	collect.seen = MEM_callocN(groups, "glsl strip used");
	collect.list = MEM_mallocN(sizeof(int) * groups, "glsl strip stack");
	collect.len = 0;

	for (int g = 0; g < GLSL_LIB_GROUPS_LEN; g++) {
		if (GLSL_LIB_ROOTS[g]) {
			collect.seen[g] = 1;
			collect.list[collect.len++] = g;
		}
	}
	glsl_foreach_ident(fragmentcode, 0, (int)strlen(fragmentcode), glsl_collect_dep, &collect);

	/* collect.list doubles as the work stack; seen marks the groups to keep. */
	while (collect.len) {
		const int g = collect.list[--collect.len];
		for (int k = 0; k < GLSL_LIB_GROUP_DEPS_LEN[g]; k++) {
			const int dep = GLSL_LIB_GROUP_DEPS[g][k];
			if (!collect.seen[dep]) {
				collect.seen[dep] = 1;
				collect.list[collect.len++] = dep;
			}
		}
	}

	DynStr *ds = BLI_dynstr_new();
	for (int c = 0; c < GLSL_LIB_CHUNKS_LEN; c++) {
		const GLSLLibChunk *chunk = &GLSL_LIB_CHUNKS[c];
		if (chunk->group == -1 || collect.seen[chunk->group]) {
			BLI_dynstr_nappend(ds, glsl_material_library + chunk->start, chunk->end - chunk->start);
		}
	}
	char *code = BLI_dynstr_get_cstring(ds);
	BLI_dynstr_free(ds);

	MEM_freeN(collect.seen);
	MEM_freeN(collect.list);
	return code;
}

void GPU_code_generate_glsl_lib(void)
{
	DynStr *ds;

	/* only initialize the library once */
	if (glsl_material_library)
		return;

	ds = BLI_dynstr_new();

	BLI_dynstr_append(ds, datatoc_gpu_shader_material_glsl);


	glsl_material_library = BLI_dynstr_get_cstring(ds);

	BLI_dynstr_free(ds);
}


/* GPU pass binding/unbinding */

/* A material whose GLSL pass failed to generate keeps material->pass NULL (see
 * GPU_material_from_blender), so callers that only guard on the returned shader -- the scene
 * light/shadow/probe/damage binds -- would dereference it. Tolerate a NULL pass here instead of
 * repeating the check at every call site. */
GPUShader *GPU_pass_shader(GPUPass *pass)
{
	return pass ? pass->shader : NULL;
}

static void gpu_nodes_extract_dynamic_inputs(GPUPass *pass, ListBase *nodes)
{
	GPUShader *shader = pass->shader;
	GPUNode *node;
	GPUInput *next, *input;
	ListBase *inputs = &pass->inputs;
	int extract, z;

	memset(inputs, 0, sizeof(*inputs));

	if (!shader)
		return;

	GPU_shader_bind(shader);

	for (node = nodes->first; node; node = node->next) {
		z = 0;
		for (input = node->inputs.first; input; input = next, z++) {
			next = input->next;

			/* attributes don't need to be bound, they already have
			 * an id that the drawing functions will use */
			if (input->source == GPU_SOURCE_ATTRIB) {
#ifdef WITH_OPENSUBDIV
				/* We do need mtface attributes for later, so we can
				 * update face-varuing variables offset in the texture
				 * buffer for proper sampling from the shader.
				 *
				 * We don't do anything about attribute itself, we
				 * only use it to learn which uniform name is to be
				 * updated.
				 *
				 * TODO(sergey): We can add ad extra uniform input
				 * for the offset, which will be purely internal and
				 * which would avoid having such an exceptions.
				 */
				if (input->attribtype != CD_MTFACE) {
					continue;
				}
#else
				continue;
#endif
			}
			if (input->source == GPU_SOURCE_BUILTIN ||
			    input->source == GPU_SOURCE_OPENGL_BUILTIN)
			{
				continue;
			}

			if (input->ima || input->tex || input->prv || input->texptr) {
				BLI_snprintf(input->shadername, sizeof(input->shadername), "samp%d", input->texid);
			}
			else
				BLI_snprintf(input->shadername, sizeof(input->shadername), "unf%d", input->id);

			/* pass non-dynamic uniforms to opengl */
			extract = 0;

			if (input->ima || input->tex || input->prv || input->texptr) {
				if (input->bindtex)
					extract = 1;
			}
			else if (input->source == GPU_SOURCE_VEC_UNIFORM && codegen_input_is_uniform(input))
				extract = 1;

			if (extract)
				input->shaderloc = GPU_shader_get_uniform(shader, input->shadername);

#ifdef WITH_OPENSUBDIV
			if (input->source == GPU_SOURCE_ATTRIB &&
			    input->attribtype == CD_MTFACE)
			{
				extract = 1;
			}
#endif

			/* extract nodes */
			if (extract) {
				BLI_remlink(&node->inputs, input);
				BLI_addtail(inputs, input);
			}
		}
	}

	GPU_shader_unbind();
}

void GPU_pass_bind(GPUPass *pass, double time, int mipmap)
{
	GPUInput *input;
	GPUShader *shader = pass->shader;
	ListBase *inputs = &pass->inputs;

	if (!shader)
		return;

	GPU_shader_bind(shader);

	/* create the textures */
	for (input = inputs->first; input; input = input->next) {
		if (input->ima)
			input->tex = GPU_texture_from_blender(input->ima, input->iuser, input->textarget, input->image_isdata, time, mipmap);
		else if (input->prv)
			input->tex = GPU_texture_from_preview(input->prv, mipmap);
	}

	/* bind the textures, in second loop so texture binding during
	 * create doesn't overwrite already bound textures */
	for (input = inputs->first; input; input = input->next) {
		if (input->tex && input->bindtex) {
			GPU_texture_bind(input->tex, input->texid);
			GPU_shader_uniform_texture(shader, input->shaderloc, input->tex);
		}
		else if (input->texptr && *input->texptr && input->bindtex) {
			GPU_texture_bind(*input->texptr, input->texid);
			GPU_shader_uniform_texture(shader, input->shaderloc, *input->texptr);
		}
	}
}

void GPU_pass_update_uniforms(GPUPass *pass)
{
	GPUInput *input;
	GPUShader *shader = pass->shader;
	ListBase *inputs = &pass->inputs;

	if (!shader)
		return;

	/* pass dynamic inputs to opengl, others were removed */
	for (input = inputs->first; input; input = input->next) {
		if (!(input->ima || input->tex || input->prv || input->texptr)) {
			if (input->shaderloc == -1) {
				continue;
			}
			if (input->type == GPU_INT) {
				GPU_shader_uniform_vector_int(shader, input->shaderloc, 1, 1, (int *)input->dynamicvec);
			}
			else {
				/* Fixed values (RANGE_SHADER_UNIFORM_VALUES) are uploaded from their own copy. */
				GPU_shader_uniform_vector(shader, input->shaderloc, input->type, 1,
					input->dynamicvec ? input->dynamicvec : input->vec);
			}
		}
	}
}

void GPU_pass_unbind(GPUPass *pass)
{
	GPUInput *input;
	GPUShader *shader = pass->shader;
	ListBase *inputs = &pass->inputs;

	if (!shader)
		return;

	for (input = inputs->first; input; input = input->next) {
		if (input->tex && input->bindtex)
			GPU_texture_unbind(input->tex);
		if (input->texptr && *input->texptr && input->bindtex) {
			GPU_texture_unbind(*input->texptr);
		}

		if (input->ima || input->prv)
			input->tex = NULL;
	}

	GPU_shader_unbind();
}

/* Node Link Functions */

static GPUNodeLink *GPU_node_link_create(void)
{
	GPUNodeLink *link = MEM_callocN(sizeof(GPUNodeLink), "GPUNodeLink");
	link->type = GPU_NONE;
	link->users++;

	return link;
}

static void gpu_node_link_free(GPUNodeLink *link)
{
	link->users--;

	if (link->users < 0)
		fprintf(stderr, "GPU_node_link_free: negative refcount\n");

	if (link->users == 0) {
		if (link->output)
			link->output->link = NULL;
		MEM_freeN(link);
	}
}

/* Node Functions */

static GPUNode *GPU_node_begin(const char *name)
{
	GPUNode *node = MEM_callocN(sizeof(GPUNode), "GPUNode");

	node->name = name;

	return node;
}

static void gpu_node_input_link(GPUNode *node, GPUNodeLink *link, const GPUType type)
{
	GPUInput *input;
	GPUNode *outnode;
	const char *name;

	if (link->output) {
		outnode = link->output->node;
		name = outnode->name;
		input = outnode->inputs.first;

		if ((STREQ(name, "set_value") || STREQ(name, "set_rgb")) &&
		    (input->type == type))
		{
			input = MEM_dupallocN(outnode->inputs.first);
			input->type = type;
			if (input->link)
				input->link->users++;
			BLI_addtail(&node->inputs, input);
			return;
		}
	}

	input = MEM_callocN(sizeof(GPUInput), "GPUInput");
	input->node = node;
	input->shaderloc = -1;

	if (link->builtin) {
		/* builtin uniform */
		input->type = type;
		input->source = GPU_SOURCE_BUILTIN;
		input->builtin = link->builtin;

		MEM_freeN(link);
	}
	else if (link->oglbuiltin) {
		/* builtin uniform */
		input->type = type;
		input->source = GPU_SOURCE_OPENGL_BUILTIN;
		input->oglbuiltin = link->oglbuiltin;

		MEM_freeN(link);
	}
	else if (link->output) {
		/* link to a node output */
		input->type = type;
		input->source = GPU_SOURCE_TEX_PIXEL;
		input->link = link;
		link->users++;
	}
	else if (link->dynamictex) {
		/* dynamic texture, GPUTexture is updated/deleted externally */
		input->type = type;
		input->source = GPU_SOURCE_TEX;

		input->tex = link->dynamictex;
		input->textarget = GL_TEXTURE_2D;
		input->textype = type;
		input->dynamictex = true;
		input->dynamicdata = link->ptr2;
		MEM_freeN(link);
	}
	else if (link->dynamictexptr) {
		/* dynamic texture, GPUTexture is updated/deleted externally */
		input->type = type;
		input->source = GPU_SOURCE_TEX;

		input->texptr = link->dynamictexptr;
		input->textarget = GL_TEXTURE_2D;
		input->textype = type;
		input->dynamictex = true;
		input->dynamicdata = link->ptr2;
		MEM_freeN(link);
	}
	else if (link->texture) {
		/* small texture created on the fly, like for colorbands */
		input->type = GPU_VEC4;
		input->source = GPU_SOURCE_TEX;
		input->textype = type;

#if 0
		input->tex = GPU_texture_create_2D(link->texturesize, link->texturesize, link->ptr2, NULL);
#endif
		input->tex = GPU_texture_create_2D(link->texturesize, 1, link->ptr1, GPU_HDR_NONE, NULL);
		input->textarget = GL_TEXTURE_2D;

		MEM_freeN(link->ptr1);
		MEM_freeN(link);
	}
	else if (link->image) {
		/* blender image */
		input->type = GPU_VEC4;
		input->source = GPU_SOURCE_TEX;

		if (link->image == GPU_NODE_LINK_IMAGE_PREVIEW) {
			input->prv = link->ptr1;
			input->textarget = GL_TEXTURE_2D;
			input->textype = GPU_TEX2D;
		}
		else if (link->image == GPU_NODE_LINK_IMAGE_BLENDER) {
			input->ima = link->ptr1;
			input->iuser = link->ptr2;
			input->image_isdata = link->image_isdata;
			input->textarget = GL_TEXTURE_2D;
			input->textype = GPU_TEX2D;
		}
		else if (link->image == GPU_NODE_LINK_IMAGE_CUBE_MAP) {
			input->ima = link->ptr1;
			input->iuser = link->ptr2;
			input->image_isdata = link->image_isdata;
			input->textarget = GL_TEXTURE_CUBE_MAP;
			input->textype = GPU_TEXCUBE;
		}
		MEM_freeN(link);
	}
	else if (link->attribtype) {
		/* vertex attribute */
		input->type = type;
		input->source = GPU_SOURCE_ATTRIB;

		input->attribtype = link->attribtype;
		BLI_strncpy(input->attribname, link->attribname, sizeof(input->attribname));
		MEM_freeN(link);
	}
	else {
		/* uniform vector */
		input->type = type;
		input->source = GPU_SOURCE_VEC_UNIFORM;

		memcpy(input->vec, link->ptr1, GPU_DATATYPE_SIZE[type] * sizeof(float));
		if (link->dynamic) {
			input->dynamicvec = link->ptr1;
			input->dynamictype = link->dynamictype;
			input->dynamicdata = link->ptr2;
		}
		MEM_freeN(link);
	}

	BLI_addtail(&node->inputs, input);
}

static void gpu_node_input_socket(GPUNode *node, GPUNodeStack *sock)
{
	GPUNodeLink *link;

	if (sock->link) {
		gpu_node_input_link(node, sock->link, sock->type);
	}
	else {
		link = GPU_node_link_create();
		link->ptr1 = sock->vec;
		gpu_node_input_link(node, link, sock->type);
	}
}

static void gpu_node_output(GPUNode *node, const GPUType type, GPUNodeLink **link)
{
	GPUOutput *output = MEM_callocN(sizeof(GPUOutput), "GPUOutput");

	output->type = type;
	output->node = node;

	if (link) {
		*link = output->link = GPU_node_link_create();
		output->link->type = type;
		output->link->output = output;

		/* note: the caller owns the reference to the link, GPUOutput
		 * merely points to it, and if the node is destroyed it will
		 * set that pointer to NULL */
	}

	BLI_addtail(&node->outputs, output);
}

static void gpu_inputs_free(ListBase *inputs)
{
	GPUInput *input;

	for (input = inputs->first; input; input = input->next) {
		if (input->link)
			gpu_node_link_free(input->link);
		else if (input->tex && !input->dynamictex)
			GPU_texture_free(input->tex);
	}

	BLI_freelistN(inputs);
}

static void gpu_node_free(GPUNode *node)
{
	GPUOutput *output;

	gpu_inputs_free(&node->inputs);

	for (output = node->outputs.first; output; output = output->next)
		if (output->link) {
			output->link->output = NULL;
			gpu_node_link_free(output->link);
		}

	BLI_freelistN(&node->outputs);
	MEM_freeN(node);
}

static void gpu_nodes_free(ListBase *nodes)
{
	GPUNode *node;

	while ((node = BLI_pophead(nodes))) {
		gpu_node_free(node);
	}
}

/* vertex attributes */

static void gpu_nodes_get_vertex_attributes(ListBase *nodes, GPUVertexAttribs *attribs)
{
	GPUNode *node;
	GPUInput *input;
	int a;

	/* convert attributes requested by node inputs to an array of layers,
	 * checking for duplicates and assigning id's starting from zero. */

	memset(attribs, 0, sizeof(*attribs));

	for (node = nodes->first; node; node = node->next) {
		for (input = node->inputs.first; input; input = input->next) {
			if (input->source == GPU_SOURCE_ATTRIB) {
				for (a = 0; a < attribs->totlayer; a++) {
					if (attribs->layer[a].type == input->attribtype &&
					    STREQ(attribs->layer[a].name, input->attribname))
					{
						break;
					}
				}

				if (a < GPU_MAX_ATTRIB) {
					if (a == attribs->totlayer) {
						input->attribid = attribs->totlayer++;
						input->attribfirst = 1;

						attribs->layer[a].type = input->attribtype;
						attribs->layer[a].attribid = input->attribid;
						BLI_strncpy(attribs->layer[a].name, input->attribname,
						            sizeof(attribs->layer[a].name));
					}
					else {
						input->attribid = attribs->layer[a].attribid;
					}
				}
			}
		}
	}
}

static void gpu_nodes_get_builtin_flag(ListBase *nodes, int *builtin)
{
	GPUNode *node;
	GPUInput *input;

	*builtin = 0;

	for (node = nodes->first; node; node = node->next)
		for (input = node->inputs.first; input; input = input->next)
			if (input->source == GPU_SOURCE_BUILTIN)
				*builtin |= input->builtin;
}

/* varargs linking  */

GPUNodeLink *GPU_attribute(const CustomDataType type, const char *name)
{
	GPUNodeLink *link = GPU_node_link_create();

	link->attribtype = type;
	link->attribname = name;

	return link;
}

GPUNodeLink *GPU_uniform(float *num)
{
	GPUNodeLink *link = GPU_node_link_create();

	link->ptr1 = num;
	link->ptr2 = NULL;

	return link;
}

GPUNodeLink *GPU_dynamic_uniform(void *num, GPUDynamicType dynamictype, void *data)
{
	GPUNodeLink *link = GPU_node_link_create();

	link->ptr1 = num;
	link->ptr2 = data;
	link->dynamic = true;
	link->dynamictype = dynamictype;


	return link;
}

GPUNodeLink *GPU_select_uniform(float *num, GPUDynamicType dynamictype, void *data, Material *material)
{
	bool dynamic = false;
	if (GPU_DYNAMIC_GROUP_FROM_TYPE(dynamictype) == GPU_DYNAMIC_GROUP_MAT) {
		dynamic = !(material->constflag & MA_CONSTANT_MATERIAL);
	}
	else if (GPU_DYNAMIC_GROUP_FROM_TYPE(dynamictype) == GPU_DYNAMIC_GROUP_LAMP) {
		dynamic = !(material->constflag & MA_CONSTANT_LAMP);
	}
	else if (GPU_DYNAMIC_GROUP_FROM_TYPE(dynamictype) == GPU_DYNAMIC_GROUP_TEX) {
		dynamic = !(material->constflag & MA_CONSTANT_TEXTURE);
	}
	else if (GPU_DYNAMIC_GROUP_FROM_TYPE(dynamictype) == GPU_DYNAMIC_GROUP_TEX_UV) {
		dynamic = !(material->constflag & MA_CONSTANT_TEXTURE_UV);
	}
	else if (GPU_DYNAMIC_GROUP_FROM_TYPE(dynamictype) == GPU_DYNAMIC_GROUP_WORLD) {
		dynamic = !(material->constflag & MA_CONSTANT_WORLD);
	}
	else if (GPU_DYNAMIC_GROUP_FROM_TYPE(dynamictype) == GPU_DYNAMIC_GROUP_MIST) {
		dynamic = !(material->constflag & MA_CONSTANT_MIST);
	}

	if (dynamic) {
		return GPU_dynamic_uniform(num, dynamictype, data);
	}
	else {
		return GPU_uniform(num);
	}
}

GPUNodeLink *GPU_image(Image *ima, ImageUser *iuser, bool is_data)
{
	GPUNodeLink *link = GPU_node_link_create();

	link->image = GPU_NODE_LINK_IMAGE_BLENDER;
	link->ptr1 = ima;
	link->ptr2 = iuser;
	link->image_isdata = is_data;

	return link;
}

GPUNodeLink *GPU_cube_map(Image *ima, ImageUser *iuser, bool is_data)
{
	GPUNodeLink *link = GPU_node_link_create();

	link->image = GPU_NODE_LINK_IMAGE_CUBE_MAP;
	link->ptr1 = ima;
	link->ptr2 = iuser;
	link->image_isdata = is_data;

	return link;
}

GPUNodeLink *GPU_image_preview(PreviewImage *prv)
{
	GPUNodeLink *link = GPU_node_link_create();

	link->image = GPU_NODE_LINK_IMAGE_PREVIEW;
	link->ptr1 = prv;

	return link;
}


GPUNodeLink *GPU_texture(int size, float *pixels)
{
	GPUNodeLink *link = GPU_node_link_create();

	link->texture = true;
	link->texturesize = size;
	link->ptr1 = pixels;

	return link;
}

GPUNodeLink *GPU_dynamic_texture(GPUTexture *tex, GPUDynamicType dynamictype, void *data)
{
	GPUNodeLink *link = GPU_node_link_create();

	link->dynamic = true;
	link->dynamictex = tex;
	link->dynamictype = dynamictype;
	link->ptr2 = data;

	return link;
}

GPUNodeLink *GPU_dynamic_texture_ptr(GPUTexture **tex, GPUDynamicType dynamictype, void *data)
{
	GPUNodeLink *link = GPU_node_link_create();

	link->dynamic = true;
	link->dynamictexptr = tex;
	link->dynamictype = dynamictype;
	link->ptr2 = data;

	return link;
}

GPUNodeLink *GPU_builtin(GPUBuiltin builtin)
{
	GPUNodeLink *link = GPU_node_link_create();

	link->builtin = builtin;

	return link;
}

GPUNodeLink *GPU_opengl_builtin(GPUOpenGLBuiltin builtin)
{
	GPUNodeLink *link = GPU_node_link_create();

	link->oglbuiltin = builtin;

	return link;
}

bool GPU_link(GPUMaterial *mat, const char *name, ...)
{
	GPUNode *node;
	GPUFunction *function;
	GPUNodeLink *link, **linkptr;
	va_list params;
	int i;

	function = gpu_lookup_function(name);
	if (!function) {
		fprintf(stderr, "GPU failed to find function %s\n", name);
		return false;
	}

	node = GPU_node_begin(name);

	va_start(params, name);
	for (i = 0; i < function->totparam; i++) {
		if (function->paramqual[i] != FUNCTION_QUAL_IN) {
			linkptr = va_arg(params, GPUNodeLink **);
			gpu_node_output(node, function->paramtype[i], linkptr);
		}
		else {
			link = va_arg(params, GPUNodeLink *);
			gpu_node_input_link(node, link, function->paramtype[i]);
		}
	}
	va_end(params);

	gpu_material_add_node(mat, node);

	return true;
}

bool GPU_stack_link(GPUMaterial *mat, const char *name, GPUNodeStack *in, GPUNodeStack *out, ...)
{
	GPUNode *node;
	GPUFunction *function;
	GPUNodeLink *link, **linkptr;
	va_list params;
	int i, totin, totout;

	function = gpu_lookup_function(name);
	if (!function) {
		fprintf(stderr, "GPU failed to find function %s\n", name);
		return false;
	}

	node = GPU_node_begin(name);
	totin = 0;
	totout = 0;

	if (in) {
		for (i = 0; in[i].type != GPU_NONE; i++) {
			gpu_node_input_socket(node, &in[i]);
			totin++;
		}
	}

	if (out) {
		for (i = 0; out[i].type != GPU_NONE; i++) {
			gpu_node_output(node, out[i].type, &out[i].link);
			totout++;
		}
	}

	va_start(params, out);
	for (i = 0; i < function->totparam; i++) {
		if (function->paramqual[i] != FUNCTION_QUAL_IN) {
			if (totout == 0) {
				linkptr = va_arg(params, GPUNodeLink **);
				gpu_node_output(node, function->paramtype[i], linkptr);
			}
			else
				totout--;
		}
		else {
			if (totin == 0) {
				link = va_arg(params, GPUNodeLink *);
				if (link->socket)
					gpu_node_input_socket(node, link->socket);
				else
					gpu_node_input_link(node, link, function->paramtype[i]);
			}
			else
				totin--;
		}
	}
	va_end(params);

	gpu_material_add_node(mat, node);

	return true;
}

int GPU_link_changed(GPUNodeLink *link)
{
	GPUNode *node;
	GPUInput *input;
	const char *name;

	if (link->output) {
		node = link->output->node;
		name = node->name;

		if (STREQ(name, "set_value") || STREQ(name, "set_rgb")) {
			input = node->inputs.first;
			return (input->link != NULL);
		}

		return 1;
	}
	else
		return 0;
}

/* Pass create/free */

static void gpu_nodes_tag(GPUNodeLink *link)
{
	GPUNode *node;
	GPUInput *input;

	if (!link->output)
		return;

	node = link->output->node;
	if (node->tag)
		return;

	node->tag = true;
	for (input = node->inputs.first; input; input = input->next)
		if (input->link)
			gpu_nodes_tag(input->link);
}

static void gpu_nodes_prune(ListBase *nodes, GPUNodeLink *outlinks[8])
{
	GPUNode *node, *next;

	for (node = nodes->first; node; node = node->next)
		node->tag = false;

	for (unsigned short i = 0; i < 8; ++i) {
		if (outlinks[i]) {
			gpu_nodes_tag(outlinks[i]);
		}
	}

	for (node = nodes->first; node; node = next) {
		next = node->next;

		if (!node->tag) {
			BLI_remlink(nodes, node);
			gpu_node_free(node);
		}
	}
}

GPUPass *GPU_generate_pass(
        ListBase *nodes, GPUNodeLink *outlinks[8],
        GPUVertexAttribs *attribs, int *builtins, const char *fragcode, const char *vertcode,
        const GPUMatType type, const char *name,
        const bool use_opensubdiv,
		const bool use_instancing,
		const bool use_skinning,
		const bool use_foliage,
        const bool use_new_shading)
{
	GPUShader *shader;
	GPUPass *pass;
	char *vertexcode, *geometrycode, *fragmentcode;

#if 0
	if (!FUNCTION_LIB) {
		GPU_nodes_free(nodes);
		return NULL;
	}
#endif

	/* prune unused nodes */
	gpu_nodes_prune(nodes, outlinks);

	gpu_nodes_get_vertex_attributes(nodes, attribs);
	gpu_nodes_get_builtin_flag(nodes, builtins);

	/* generate code and compile with opengl */
	fragmentcode = code_generate_fragment(nodes, fragcode, type, outlinks);
	vertexcode = code_generate_vertex(nodes, vertcode, type, use_instancing);
	geometrycode = code_generate_geometry(nodes, use_opensubdiv);

	int flags = GPU_SHADER_FLAGS_NONE;
	if (use_opensubdiv) {
		flags |= GPU_SHADER_FLAGS_SPECIAL_OPENSUBDIV;
	}
	if (use_new_shading) {
		flags |= GPU_SHADER_FLAGS_NEW_SHADING;
	}
	if (use_instancing) {
		flags |= GPU_SHADER_FLAGS_SPECIAL_INSTANCING;
	}
	if (use_skinning) {
		flags |= GPU_SHADER_FLAGS_SPECIAL_SKINNING;
	}
	if (use_foliage) {
		flags |= GPU_SHADER_FLAGS_FOLIAGE;
	}
	if (vertcode) {
		flags |= GPU_SHADER_FLAGS_USER_CODE;
	}
	const unsigned int hash = shader_cache_hash(vertexcode, fragmentcode, geometrycode, flags);
	const bool use_cache = shader_cache_enabled();
	shader = use_cache ? shader_cache_acquire(vertexcode, fragmentcode, geometrycode, glsl_material_library, flags, hash) :
	                     NULL;
	if (shader && !GPU_shader_prefetching()) {
		SHADER_CACHE_STAT_REUSED++;
	}
	else {
		const double compile_start = PIL_check_seconds_timer();
		char *libcode = glsl_lib_strip(fragmentcode);
		shader = GPU_shader_create_ex_named(vertexcode,
		                              fragmentcode,
		                              geometrycode,
		                              libcode ? libcode : glsl_material_library,
		                              NULL,
		                              0,
		                              0,
		                              0,
		                              flags | GPU_SHADER_FLAGS_BINARY_CACHE,
		                              name);
		MEM_SAFE_FREE(libcode);
		if (!GPU_shader_prefetching()) {
			SHADER_CACHE_STAT_COMPILE_TIME += PIL_check_seconds_timer() - compile_start;
			SHADER_CACHE_STAT_COMPILED++;
		}
		if (shader && use_cache) {
			shader_cache_add(shader, vertexcode, fragmentcode, geometrycode, glsl_material_library, flags, hash);
		}
	}

	/* failed? */
	if (!shader) {
		if (fragmentcode)
			MEM_freeN(fragmentcode);
		if (vertexcode)
			MEM_freeN(vertexcode);
		memset(attribs, 0, sizeof(*attribs));
		memset(builtins, 0, sizeof(*builtins));
		gpu_nodes_free(nodes);
		return NULL;
	}

	/* create pass */
	pass = MEM_callocN(sizeof(GPUPass), "GPUPass");

	pass->shader = shader;
	pass->fragmentcode = fragmentcode;
	pass->geometrycode = geometrycode;
	pass->vertexcode = vertexcode;
	pass->libcode = glsl_material_library;

	/* extract dynamic inputs and throw away nodes */
	gpu_nodes_extract_dynamic_inputs(pass, nodes);
	gpu_nodes_free(nodes);

	return pass;
}

void GPU_pass_free(GPUPass *pass)
{
	shader_cache_release(pass->shader);
	gpu_inputs_free(&pass->inputs);
	if (pass->fragmentcode)
		MEM_freeN(pass->fragmentcode);
	if (pass->geometrycode)
		MEM_freeN(pass->geometrycode);
	if (pass->vertexcode)
		MEM_freeN(pass->vertexcode);
	MEM_freeN(pass);
}

void GPU_pass_free_nodes(ListBase *nodes)
{
	gpu_nodes_free(nodes);
}
