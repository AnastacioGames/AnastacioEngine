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

/* Nodes only reached from the vertex offset stay out of the fragment shader. */
static bool codegen_node_in_fragment(const GPUNode *node)
{
	return node->stage == 0 || (node->stage & GPU_NODE_STAGE_FRAGMENT);
}

static void codegen_declare_tmps(DynStr *ds, ListBase *nodes)
{
	GPUNode *node;
	GPUInput *input;
	GPUOutput *output;

	for (node = nodes->first; node; node = node->next) {
		if (!codegen_node_in_fragment(node)) {
			continue;
		}
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
		if (!codegen_node_in_fragment(node)) {
			continue;
		}
		if (STREQ(node->name, "node_shell_layer")) {
			/* Fur Shells / Outline layer, from the generated geometry stage (see code_generate_fragment). */
			BLI_dynstr_appendf(ds, "\ttmp%d = shell_layer;\n", ((GPUOutput *)node->outputs.first)->id);
			continue;
		}
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

static bool codegen_uses_node(ListBase *nodes, const char *name, int stage)
{
	for (GPUNode *node = nodes->first; node; node = node->next) {
		const bool in_stage = (stage == GPU_NODE_STAGE_FRAGMENT) ? codegen_node_in_fragment(node) :
		                      (node->stage & stage) != 0;
		if (in_stage && STREQ(node->name, name)) {
			return true;
		}
	}
	return false;
}

#define SCRIPT_MAX_NAMES 256

typedef struct ScriptNames {
	char (*names)[64];
	int tot;
	DynStr *defs, *undefs;
	const char *prefix;
} ScriptNames;

static bool codegen_script_reserved(const char *word)
{
	static const char *reserved[] = {
		"main", "void", "float", "int", "uint", "bool", "vec2", "vec3", "vec4", "ivec2", "ivec3", "ivec4",
		"bvec2", "bvec3", "bvec4", "mat2", "mat3", "mat4", "sampler2D", "samplerCube", "sampler2DShadow",
		"const", "uniform", "in", "out", "inout", "varying", "attribute", "highp", "mediump", "lowp",
		"precision", "struct", "flat", "smooth", "layout", "TIME", NULL};
	for (int i = 0; reserved[i]; i++) {
		if (STREQ(word, reserved[i])) {
			return true;
		}
	}
	return false;
}

/* Renames a top level name of the script to <prefix>_<name>, or only forgets a macro of the script. */
static void codegen_script_name(ScriptNames *sn, const char *name, bool macro)
{
	if (!name[0] || codegen_script_reserved(name) || sn->tot >= SCRIPT_MAX_NAMES) {
		return;
	}
	for (int i = 0; i < sn->tot; i++) {
		if (STREQ(sn->names[i], name)) {
			return;
		}
	}
	BLI_strncpy(sn->names[sn->tot++], name, sizeof(sn->names[0]));
	if (!macro) {
		/* Two underscores in a row are reserved in GLSL. */
		BLI_dynstr_appendf(sn->defs, "#define %s %s%s%s\n", name, sn->prefix, (name[0] == '_') ? "x" : "_", name);
	}
	BLI_dynstr_appendf(sn->undefs, "#undef %s\n", name);
}

static bool codegen_ident_char(char c)
{
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_';
}

static const char *codegen_read_word(const char *p, char *r_word, int size)
{
	int n = 0;
	while (codegen_ident_char(*p)) {
		if (n < size - 1) {
			r_word[n++] = *p;
		}
		p++;
	}
	r_word[n] = '\0';
	return p;
}

/* Functions, global variables/constants and structs declared at the top level of a GLSL Script get
 * a name of their own per node (by #define, so the lines of the Text stay as they are): two scripts
 * may then declare helpers with the same name, also one that the material library already has.
 * Macros of the script are forgotten at its end. */
static void codegen_script_names(ScriptNames *sn, const char *code)
{
	const char *p = code;
	int braces = 0, parens = 0, nwords = 0;
	bool init = false, skip = false, line_start = true, prev_word = false, after_struct = false;
	char prev[64] = "", word[64];

	while (*p) {
		if (p[0] == '/' && p[1] == '/') {
			while (*p && *p != '\n') p++;
			continue;
		}
		if (p[0] == '/' && p[1] == '*') {
			const char *end = strstr(p + 2, "*/");
			p = end ? end + 2 : p + strlen(p);
			continue;
		}
		if (*p == '\n') {
			line_start = true;
			p++;
			continue;
		}
		if (*p == ' ' || *p == '\t' || *p == '\r') {
			p++;
			continue;
		}
		if (*p == '#' && line_start) {
			p++;
			while (*p == ' ' || *p == '\t') p++;
			p = codegen_read_word(p, word, sizeof(word));
			if (STREQ(word, "define")) {
				while (*p == ' ' || *p == '\t') p++;
				p = codegen_read_word(p, word, sizeof(word));
				codegen_script_name(sn, word, true);
			}
			while (*p && *p != '\n') {
				if (p[0] == '\\' && p[1] == '\n') p++;
				else if (p[0] == '\\' && p[1] == '\r' && p[2] == '\n') p += 2;
				p++;
			}
			continue;
		}
		line_start = false;

		if (*p >= '0' && *p <= '9') {
			while (codegen_ident_char(*p) || *p == '.') p++;
			prev_word = false;
			continue;
		}
		if (codegen_ident_char(*p)) {
			p = codegen_read_word(p, word, sizeof(word));
			if (braces == 0 && parens == 0 && !init) {
				if (nwords == 0 && (STREQ(word, "in") || STREQ(word, "out") || STREQ(word, "varying") ||
				                    STREQ(word, "attribute") || STREQ(word, "precision") || STREQ(word, "layout") ||
				                    STREQ(word, "flat") || STREQ(word, "smooth")))
				{
					/* Shared with the rest of the shader, or not the declaration of a name. */
					skip = true;
				}
				if (after_struct && !skip) {
					codegen_script_name(sn, word, false);
				}
				after_struct = STREQ(word, "struct");
				BLI_strncpy(prev, word, sizeof(prev));
				prev_word = true;
				nwords++;
			}
			continue;
		}

		const char c = *p++;
		const bool top = (braces == 0 && parens == 0);
		const bool is_name = top && !init && prev_word && nwords >= 2 && !skip;
		switch (c) {
			case '{':
				braces++;
				break;
			case '}':
				braces = max_ii(braces - 1, 0);
				if (braces == 0 && !init) {
					/* End of a function body or of the members of a struct. */
					nwords = 0;
					skip = false;
				}
				break;
			case '(':
				if (is_name) {
					codegen_script_name(sn, prev, false);
				}
				parens++;
				break;
			case ')':
				parens = max_ii(parens - 1, 0);
				break;
			case '[':
				if (is_name) {
					codegen_script_name(sn, prev, false);
				}
				break;
			case '=':
				if (is_name) {
					codegen_script_name(sn, prev, false);
				}
				if (top) {
					init = true;
				}
				break;
			case ',':
				if (is_name) {
					codegen_script_name(sn, prev, false);
				}
				if (top) {
					init = false;
				}
				break;
			case ';':
				if (is_name) {
					codegen_script_name(sn, prev, false);
				}
				if (top) {
					init = false;
					nwords = 0;
					skip = false;
				}
				break;
		}
		prev_word = false;
		after_struct = false;
	}
}

/* GLSL Script node functions used by the given stage. The user writes a function called main;
 * it is renamed to the unique name of its node, and so are the other names of the script. */
static void codegen_print_scripts(DynStr *ds, ListBase *nodes, ListBase *scripts, int stage)
{
	if (!scripts) {
		return;
	}
	for (GPUScriptCode *script = scripts->first; script; script = script->next) {
		if (codegen_uses_node(nodes, script->name, stage)) {
			ScriptNames sn = {NULL};
			sn.names = MEM_mallocN(sizeof(*sn.names) * SCRIPT_MAX_NAMES, "ScriptNames");
			sn.defs = BLI_dynstr_new();
			sn.undefs = BLI_dynstr_new();
			sn.prefix = script->name;
			codegen_script_names(&sn, script->code);
			char *defs = BLI_dynstr_get_cstring(sn.defs);
			char *undefs = BLI_dynstr_get_cstring(sn.undefs);

			BLI_dynstr_appendf(ds, "\n#define main %s_main\n", script->name);
			if (script->use_time) {
				/* Set by the wrapper from the time of the material. */
				BLI_dynstr_appendf(ds, "float %s_TIME;\n#define TIME %s_TIME\n", script->name, script->name);
			}
			BLI_dynstr_append(ds, defs);
			/* Compile errors give the line of the Text. The second #line argument (source string
			 * number, GLSL spec) is this script's id + 1 (0 is the material's own Fragment/Vertex/
			 * Geometry code): a compile error log then starts with "<id+1>:<line>" or "<id+1>(<line>)"
			 * depending on the driver, which gpu_shader_error_find_node (gpu_material.c) matches back
			 * to this node's name, so the editor can paint it red (node_draw.c). */
			BLI_dynstr_appendf(ds, "#line 1 %d\n", script->id + 1);
			BLI_dynstr_append(ds, script->code);
			/* Back to source id 0 (no owning node) so a later script or the rest of the generated
			 * code is never mistakenly blamed on this one. */
			BLI_dynstr_append(ds, "\n#line 1 0\n");
			BLI_dynstr_appendf(ds, "\n#define SCRIPT_MAIN %s_main\n#define SCRIPT_ENTRY %s\n",
			                   script->name, script->name);
			/* Inside the renames: the wrapper fills the uniforms of the script. */
			BLI_dynstr_append(ds, script->wrapper);
			BLI_dynstr_append(ds, "\n#undef main\n#undef SCRIPT_MAIN\n#undef SCRIPT_ENTRY\n");
			if (script->use_time) {
				BLI_dynstr_append(ds, "#undef TIME\n");
			}
			BLI_dynstr_append(ds, undefs);

			MEM_freeN(defs);
			MEM_freeN(undefs);
			BLI_dynstr_free(sn.defs);
			BLI_dynstr_free(sn.undefs);
			MEM_freeN(sn.names);
		}
	}
}

static char *code_generate_fragment(ListBase *nodes, const char *usercode, const GPUMatType type, GPUNodeLink *outputs[8],
                                    bool shell_varying, ListBase *scripts)
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

	const bool use_shell_layer = codegen_uses_node(nodes, "node_shell_layer", GPU_NODE_STAGE_FRAGMENT);
	if (use_shell_layer && shell_varying) {
		BLI_dynstr_appendf(ds, "%s float varshelllayer;\n", GPU_CODEGEN_USE_MODERN_QUALIFIERS ? "in" : "varying");
	}

	codegen_print_scripts(ds, nodes, scripts, GPU_NODE_STAGE_FRAGMENT);

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

	if (use_shell_layer) {
		/* Without the geometry stage (no support, or no Fur Shells/Outline) every pixel is the base layer. */
		BLI_dynstr_appendf(ds, "\tfloat shell_layer = %s;\n", shell_varying ? "varshelllayer" : "0.0");
	}

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

static char *glsl_lib_strip_vertex(const char *code);

/* Vertex stage of the node tree: the nodes reached from the Material Output "Vertex Offset" become
 * vertex_nodes(), called from gpu_shader_vertex.glsl (USE_VERTEX_NODES) before the vertex is
 * projected. Library functions they call are copied from the material library. */
static void codegen_vertex_input(DynStr *ds, GPUInput *input)
{
	if (input->source == GPU_SOURCE_TEX) {
		BLI_dynstr_appendf(ds, "samp%d", input->texid);
		if (input->link)
			BLI_dynstr_append(ds, ", vec2(0.0)");
	}
	else if (input->source == GPU_SOURCE_TEX_PIXEL) {
		BLI_dynstr_appendf(ds, "%s(0.0)", GPU_DATATYPE_STR[input->type]);
	}
	else if (input->source == GPU_SOURCE_BUILTIN) {
		if (input->builtin == GPU_VIEW_POSITION)
			BLI_dynstr_append(ds, "vn_viewpos");
		else if (input->builtin == GPU_VIEW_NORMAL)
			BLI_dynstr_append(ds, "vn_viewnor");
		else if (input->builtin == GPU_VERTEX_ID)
			BLI_dynstr_append(ds, "float(gl_VertexID)");
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
		/* The varyings are only written at the end of main(), read the attribute itself. */
		BLI_dynstr_appendf(ds, "att%d", input->attribid);
	}
	else if (input->source == GPU_SOURCE_OPENGL_BUILTIN) {
		if (input->oglbuiltin == GPU_COLOR)
			BLI_dynstr_append(ds, "gl_Color");
		else
			BLI_dynstr_append(ds, "vec4(0.5)");
	}
}

static void codegen_vertex_nodes(DynStr *ds, ListBase *nodes, GPUNodeLink *vertex_offset, ListBase *scripts)
{
	DynStr *body = BLI_dynstr_new();
	DynStr *decl = BLI_dynstr_new();
	GPUNode *node;
	GPUInput *input;
	GPUOutput *output;
	bool texdeclared[64] = {false};
	int builtins = 0;

	for (node = nodes->first; node; node = node->next) {
		if (!(node->stage & GPU_NODE_STAGE_VERTEX)) {
			continue;
		}
		for (input = node->inputs.first; input; input = input->next) {
			if ((input->source == GPU_SOURCE_TEX) || (input->source == GPU_SOURCE_TEX_PIXEL)) {
				if (codegen_input_has_texture(input) && input->texid >= 0 && input->texid < 64 &&
				    !texdeclared[input->texid])
				{
					texdeclared[input->texid] = true;
					BLI_dynstr_appendf(decl, "uniform %s samp%d;\n",
						(input->textype == GPU_TEX2D) ? "sampler2D" :
						(input->textype == GPU_TEXCUBE) ? "samplerCube" : "sampler2DShadow",
						input->texid);
				}
			}
			else if (input->source == GPU_SOURCE_BUILTIN) {
				const char *name = GPU_builtin_name(input->builtin);
				/* gpu_shader_vertex.glsl already declares the matrices, the time and its outputs. */
				const bool declared = ELEM(input->builtin, GPU_VIEW_MATRIX, GPU_OBJECT_MATRIX, GPU_TIME,
				                           GPU_PROJECTION_MATRIX, GPU_NORMAL_MATRIX);
				if (!(builtins & input->builtin) && gpu_str_prefix(name, "unf") && !declared) {
					BLI_dynstr_appendf(decl, "uniform %s %s;\n", GPU_DATATYPE_STR[input->type], name);
				}
				builtins |= input->builtin;
			}
			else if (input->source == GPU_SOURCE_VEC_UNIFORM) {
				if (codegen_input_is_uniform(input)) {
					BLI_dynstr_appendf(decl, "uniform %s unf%d;\n", GPU_DATATYPE_STR[input->type], input->id);
				}
				else {
					BLI_dynstr_appendf(decl, "const %s cons%d = ", GPU_DATATYPE_STR[input->type], input->id);
					codegen_print_datatype(decl, input->type, input->vec);
					BLI_dynstr_append(decl, ";\n");
				}
			}
		}
	}

	codegen_print_scripts(decl, nodes, scripts, GPU_NODE_STAGE_VERTEX);

	BLI_dynstr_append(body, "void vertex_nodes(vec3 vn_co, vec3 vn_nor, out vec3 vn_offset)\n{\n");
	BLI_dynstr_append(body, "\tvec3 vn_viewpos = (unfviewmat * unfobmat * vec4(vn_co, 1.0)).xyz;\n");
	BLI_dynstr_append(body, "\tvec3 vn_viewnor = normalize(gl_NormalMatrix * vn_nor);\n");

	for (node = nodes->first; node; node = node->next) {
		if (!(node->stage & GPU_NODE_STAGE_VERTEX)) {
			continue;
		}
		for (output = node->outputs.first; output; output = output->next) {
			BLI_dynstr_appendf(body, "\t%s tmp%d;\n", GPU_DATATYPE_STR[output->type], output->id);
		}
	}

	for (node = nodes->first; node; node = node->next) {
		if (!(node->stage & GPU_NODE_STAGE_VERTEX)) {
			continue;
		}
		if (STREQ(node->name, "node_shell_layer")) {
			BLI_dynstr_appendf(body, "\ttmp%d = 0.0;\n", ((GPUOutput *)node->outputs.first)->id);
			continue;
		}
		BLI_dynstr_appendf(body, "\t%s(", node->name);
		for (input = node->inputs.first; input; input = input->next) {
			if (input->source == GPU_SOURCE_TEX_PIXEL && input->link) {
				codegen_convert_datatype(body, input->link->output->type, input->type, "tmp", input->link->output->id);
			}
			else {
				codegen_vertex_input(body, input);
			}
			BLI_dynstr_append(body, ", ");
		}
		for (output = node->outputs.first; output; output = output->next) {
			BLI_dynstr_appendf(body, "tmp%d", output->id);
			if (output->next)
				BLI_dynstr_append(body, ", ");
		}
		BLI_dynstr_append(body, ");\n");
	}

	BLI_dynstr_append(body, "\tvn_offset = ");
	codegen_convert_datatype(body, vertex_offset->output->type, GPU_VEC3, "tmp", vertex_offset->output->id);
	BLI_dynstr_append(body, ";\n}\n");

	char *bodycode = BLI_dynstr_get_cstring(body);
	char *declcode = BLI_dynstr_get_cstring(decl);
	char *libcode = glsl_lib_strip_vertex(bodycode);

	BLI_dynstr_append(ds, "\n/* Vertex nodes */\n");
	if (libcode) {
		BLI_dynstr_append(ds, libcode);
		MEM_freeN(libcode);
	}
	BLI_dynstr_append(ds, "\n");
	BLI_dynstr_append(ds, declcode);
	BLI_dynstr_append(ds, bodycode);

	MEM_freeN(bodycode);
	MEM_freeN(declcode);
	BLI_dynstr_free(body);
	BLI_dynstr_free(decl);
}

static char *code_generate_vertex(ListBase *nodes, const char *usercode, const GPUMatType type, bool use_instancing,
                                  const char *prefix, GPUNodeLink *vertex_offset, ListBase *scripts)
{
	DynStr *ds = BLI_dynstr_new();
	GPUNode *node;
	GPUInput *input;
	char *code;
	char *vertcode = NULL;

	if (prefix) {
		BLI_dynstr_append(ds, prefix);
	}

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

	if (vertex_offset) {
		codegen_vertex_nodes(ds, nodes, vertex_offset, scripts);
	}

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

/* Geometry stage for materials (Material.geomcode, Fur Shells, Outline). Every varying the vertex
 * shader writes is renamed to vs_<name> there (#define in front of the vertex code) and copied by
 * the generated geometry shader, so neither the nodes nor the user code repeat the varyings. */

static bool glsl_ident_char(char c);

#define GEOM_MAX_VARYINGS 64

typedef struct GeomVarying {
	char type[16];
	char name[64];
	bool flat;
} GeomVarying;

static void geom_varying_add(GeomVarying *list, int *tot, const char *type, const char *name, bool flat)
{
	if (*tot >= GEOM_MAX_VARYINGS) {
		return;
	}
	for (int i = 0; i < *tot; i++) {
		if (STREQ(list[i].name, name)) {
			return;
		}
	}
	BLI_strncpy(list[*tot].type, type, sizeof(list[*tot].type));
	BLI_strncpy(list[*tot].name, name, sizeof(list[*tot].name));
	list[*tot].flat = flat;
	(*tot)++;
}

/* Outputs declared by user vertex code: "[flat] out|varying <type> <name>;" at the start of a line. */
static void geom_parse_user_varyings(const char *code, GeomVarying *list, int *tot)
{
	const char *line = code;
	while (line && *line) {
		const char *p = line;
		while (*p == ' ' || *p == '\t') {
			p++;
		}
		bool flat = false;
		if (strncmp(p, "flat ", 5) == 0) {
			flat = true;
			p += 5;
			while (*p == ' ' || *p == '\t') p++;
		}
		int skip = 0;
		if (strncmp(p, "out ", 4) == 0) skip = 4;
		else if (strncmp(p, "varying ", 8) == 0) skip = 8;
		if (skip) {
			char type[16], name[64];
			p += skip;
			while (*p == ' ' || *p == '\t') p++;
			int n = 0;
			while (*p && glsl_ident_char(*p) && n < (int)sizeof(type) - 1) type[n++] = *p++;
			type[n] = '\0';
			while (*p == ' ' || *p == '\t') p++;
			int m = 0;
			while (*p && glsl_ident_char(*p) && m < (int)sizeof(name) - 1) name[m++] = *p++;
			name[m] = '\0';
			while (*p == ' ' || *p == '\t') p++;
			/* Arrays and several names per line are left to the user. */
			if (n && m && *p == ';') {
				geom_varying_add(list, tot, type, name, flat);
			}
		}
		line = strchr(line, '\n');
		if (line) line++;
	}
}

static int geom_collect_varyings(ListBase *nodes, const char *vertcode, bool use_instancing, GeomVarying *list)
{
	int tot = 0;
	geom_varying_add(list, &tot, "vec3", "varposition", false);
	geom_varying_add(list, &tot, "vec3", "varnormal", false);
	geom_varying_add(list, &tot, "float", "varvertexid", false);
	geom_varying_add(list, &tot, "vec3", "varbarycentric", false);
	if (use_instancing) {
		geom_varying_add(list, &tot, "vec4", "varinstcolor", false);
		geom_varying_add(list, &tot, "mat4", "varinstmat", false);
		geom_varying_add(list, &tot, "mat4", "varinstinvmat", false);
		geom_varying_add(list, &tot, "int", "varinstlayer", true);
		geom_varying_add(list, &tot, "vec3", "varinstinfo", false);
	}
	for (GPUNode *node = nodes->first; node; node = node->next) {
		for (GPUInput *input = node->inputs.first; input; input = input->next) {
			if (input->source == GPU_SOURCE_ATTRIB && input->attribfirst) {
				char name[16];
				BLI_snprintf(name, sizeof(name), "var%d", input->attribid);
				geom_varying_add(list, &tot, GPU_DATATYPE_STR[input->type], name, false);
			}
		}
	}
	if (vertcode) {
		geom_parse_user_varyings(vertcode, list, &tot);
	}
	return tot;
}

static char *geom_vertex_prefix(const GeomVarying *list, int tot)
{
	DynStr *ds = BLI_dynstr_new();
	BLI_dynstr_append(ds, "#define USE_GEOMETRY_STAGE\n");
	for (int i = 0; i < tot; i++) {
		BLI_dynstr_appendf(ds, "#define %s vs_%s\n", list[i].name, list[i].name);
	}
	char *code = BLI_dynstr_get_cstring(ds);
	BLI_dynstr_free(ds);
	return code;
}

/* Raw mode of Material.geomcode: the Text has its own "void main(" instead of "void geometry()". */
static bool geom_code_has_main(const char *code)
{
	for (const char *p = strstr(code, "main"); p; p = strstr(p + 4, "main")) {
		const char *end = p + 4;
		while (*end == ' ' || *end == '\t') {
			end++;
		}
		if (*end != '(' || (p > code && glsl_ident_char(p[-1]))) {
			continue;
		}
		const char *start = p;
		while (start > code && ELEM(start[-1], ' ', '\t', '\n', '\r')) {
			start--;
		}
		if (start - code >= 4 && strncmp(start - 4, "void", 4) == 0 &&
		    (start - 4 == code || !glsl_ident_char(start[-5])))
		{
			return true;
		}
	}
	return false;
}

/* Raw mode: the "layout(...) in;" and "layout(...) out;" lines of the user go to the top of the shader,
 * as the input layout gives the size of the vs_ arrays that the helpers index. They are commented out
 * in the returned copy of the code, so the line numbers of the Text stay. */
static char *geom_hoist_layouts(const char *usercode, DynStr *ds, bool *r_has_in, bool *r_has_out)
{
	char *code = BLI_strdup(usercode);
	char *line = code;
	*r_has_in = *r_has_out = false;
	while (line && *line) {
		char *p = line;
		char *eol = strchr(line, '\n');
		while (*p == ' ' || *p == '\t') {
			p++;
		}
		if (strncmp(p, "layout", 6) == 0 && !glsl_ident_char(p[6])) {
			char *semi = strchr(p, ';');
			if (semi && (!eol || semi < eol)) {
				const char *word_end = semi;
				while (word_end > p && ELEM(word_end[-1], ' ', '\t')) {
					word_end--;
				}
				const char *word = word_end;
				while (word > p && glsl_ident_char(word[-1])) {
					word--;
				}
				const int len = (int)(word_end - word);
				const bool is_in = (len == 2 && strncmp(word, "in", 2) == 0);
				const bool is_out = (len == 3 && strncmp(word, "out", 3) == 0);
				/* "layout(location = 0) in vec3 name;" ends with a name: not a primitive layout */
				if (is_in || is_out) {
					BLI_dynstr_nappend(ds, p, (int)(semi + 1 - p));
					BLI_dynstr_append(ds, "\n");
					p[0] = p[1] = '/';
					*r_has_in |= is_in;
					*r_has_out |= is_out;
				}
			}
		}
		line = eol ? eol + 1 : NULL;
	}
	return code;
}

static char *code_generate_geometry_stage(const GeomVarying *list, int tot, const GPUPassStages *stages,
                                          bool use_shells, bool use_strands, bool use_explode,
                                          int *r_max_vertices)
{
	DynStr *ds = BLI_dynstr_new();
	const bool use_raw = !use_shells && !use_strands && !use_explode && geom_code_has_main(stages->geomcode);
	char *rawcode = NULL;

	if (use_shells) {
		const int layers = max_ii(stages->shell_layers, 1);
		const int invocations = layers + (stages->outline_width != 0.0f ? 1 : 0);
		/* One invocation per layer keeps max_vertices (and the output component limit) small. */
		BLI_dynstr_appendf(ds,
		        "#define SHELL_LAYERS %d\n"
		        "#define SHELL_LENGTH %f\n"
		        "#define SHELL_DIR vec3(%f, %f, %f)\n"
		        "#define SHELL_DIR_STRENGTH %f\n"
		        "#define OUTLINE_WIDTH %f\n"
		        "#if __VERSION__ >= 400\n"
		        "layout(triangles, invocations = %d) in;\n"
		        "layout(triangle_strip, max_vertices = 3) out;\n"
		        "#define GEOM_LAYER_FIRST gl_InvocationID\n"
		        "#define GEOM_LAYER_LAST gl_InvocationID\n"
		        "#else\n"
		        "layout(triangles) in;\n"
		        "layout(triangle_strip, max_vertices = %d) out;\n"
		        "#define GEOM_LAYER_FIRST 0\n"
		        "#define GEOM_LAYER_LAST %d\n"
		        "#endif\n",
		        layers, stages->shell_length,
		        stages->shell_dir[0], stages->shell_dir[1], stages->shell_dir[2], stages->shell_dir_strength,
		        stages->outline_width,
		        invocations, invocations * 3, invocations - 1);
		*r_max_vertices = invocations * 3;
	}
	else if (use_strands) {
		const int density = max_ii(stages->strand_density, 1);
		/* One invocation per strand, same reasoning as SHELL_LAYERS above: max_vertices stays at
		 * 3 (one thin triangle) with GL 4.0 invocations, or density*3 on the fallback path. */
		BLI_dynstr_appendf(ds,
		        "#define STRAND_DENSITY %d\n"
		        "#define STRAND_LENGTH %f\n"
		        "#define STRAND_CURVATURE %f\n"
		        "#if __VERSION__ >= 400\n"
		        "layout(triangles, invocations = %d) in;\n"
		        "layout(triangle_strip, max_vertices = 3) out;\n"
		        "#define GEOM_STRAND_FIRST gl_InvocationID\n"
		        "#define GEOM_STRAND_LAST gl_InvocationID\n"
		        "#else\n"
		        "layout(triangles) in;\n"
		        "layout(triangle_strip, max_vertices = %d) out;\n"
		        "#define GEOM_STRAND_FIRST 0\n"
		        "#define GEOM_STRAND_LAST %d\n"
		        "#endif\n",
		        density, stages->strand_length, stages->strand_curvature,
		        density, density * 3, density - 1);
		*r_max_vertices = density * 3;
	}
	else if (use_explode) {
		BLI_dynstr_appendf(ds,
		        "#define EXPLODE_FACTOR %f\n"
		        "layout(triangles) in;\n"
		        "layout(triangle_strip, max_vertices = 3) out;\n",
		        stages->explode_factor);
		*r_max_vertices = 3;
	}
	else if (use_raw) {
		bool has_in, has_out;
		rawcode = geom_hoist_layouts(stages->geomcode, ds, &has_in, &has_out);
		if (!has_in) {
			BLI_dynstr_append(ds, "layout(triangles) in;\n");
		}
		if (!has_out) {
			BLI_dynstr_append(ds, "layout(triangle_strip, max_vertices = 3) out;\n");
		}
		*r_max_vertices = 64;
	}
	else {
		BLI_dynstr_append(ds, "layout(triangles) in;\n");
		if (!strstr(stages->geomcode, "max_vertices")) {
			BLI_dynstr_append(ds, "layout(triangle_strip, max_vertices = 3) out;\n");
		}
		*r_max_vertices = 64;
	}

	for (int i = 0; i < tot; i++) {
		const char *flat = list[i].flat ? "flat " : "";
		BLI_dynstr_appendf(ds, "%sin %s vs_%s[];\n", flat, list[i].type, list[i].name);
		BLI_dynstr_appendf(ds, "%sout %s %s;\n", flat, list[i].type, list[i].name);
	}
	if (use_shells || use_strands) {
		BLI_dynstr_append(ds, "out float varshelllayer;\n");
	}

	BLI_dynstr_append(ds,
	        "#ifdef USE_CORE_PROFILE\n"
	        "uniform mat4 unfprojmat;\n"
	        "#define GEOM_PROJECTION unfprojmat\n"
	        "#else\n"
	        "#define GEOM_PROJECTION gl_ProjectionMatrix\n"
	        "#endif\n"
	        "#if !defined(USE_CORE_PROFILE) && !defined(GPU_ATI) && !defined(CLIP_WORKAROUND)\n"
	        "#define GEOM_CLIP_VERTEX\n"
	        "#endif\n"
	        "#if defined(CLIP_WORKAROUND) && !defined(USE_CORE_PROFILE)\n"
	        "out float gl_ClipDistance[6];\n"
	        "#endif\n"
	        "uniform float unftime;\n"
	        "#define TIME unftime\n\n"
	        "/* View space position and normal of input vertex i. */\n"
	        "vec3 geom_position(int i) { return vs_varposition[i]; }\n"
	        "vec3 geom_normal(int i) { return vs_varnormal[i]; }\n\n"
	        "/* Copies every output from input vertex i. */\n"
	        "void geom_copy(int i)\n{\n");
	for (int i = 0; i < tot; i++) {
		BLI_dynstr_appendf(ds, "\t%s = vs_%s[i];\n", list[i].name, list[i].name);
	}
	BLI_dynstr_append(ds,
	        "\tgl_Position = gl_in[i].gl_Position;\n"
	        "#ifndef USE_CORE_PROFILE\n"
	        "\tgl_FrontColor = gl_in[i].gl_FrontColor;\n"
	        "\tgl_FrontSecondaryColor = gl_in[i].gl_FrontSecondaryColor;\n"
	        "#endif\n"
	        "#ifdef GEOM_CLIP_VERTEX\n"
	        "\tgl_ClipVertex = gl_in[i].gl_ClipVertex;\n"
	        "#endif\n"
	        "#if defined(CLIP_WORKAROUND) && !defined(USE_CORE_PROFILE)\n"
	        "\t/* Same array size as the vertex shader (gl_ClipDistance[6]) or the stages do not link. */\n"
	        "\tgl_ClipDistance[0] = gl_in[i].gl_ClipDistance[0];\n"
	        "\tgl_ClipDistance[1] = gl_in[i].gl_ClipDistance[1];\n"
	        "\tgl_ClipDistance[2] = gl_in[i].gl_ClipDistance[2];\n"
	        "\tgl_ClipDistance[3] = gl_in[i].gl_ClipDistance[3];\n"
	        "\tgl_ClipDistance[4] = gl_in[i].gl_ClipDistance[4];\n"
	        "\tgl_ClipDistance[5] = gl_in[i].gl_ClipDistance[5];\n"
	        "#endif\n"
	        "}\n\n"
	        "/* Moves the current output vertex to a view space position. */\n"
	        "void geom_set_position(vec3 viewpos)\n{\n"
	        "\tvarposition = viewpos;\n"
	        "\tgl_Position = GEOM_PROJECTION * vec4(viewpos, 1.0);\n"
	        "#ifdef GEOM_CLIP_VERTEX\n"
	        "\tgl_ClipVertex = vec4(viewpos, 1.0);\n"
	        "#endif\n"
	        "#if defined(CLIP_WORKAROUND) && !defined(USE_CORE_PROFILE)\n"
	        "\tgl_ClipDistance[0] = dot(vec4(viewpos, 1.0), gl_ClipPlane[0]);\n"
	        "\tgl_ClipDistance[1] = dot(vec4(viewpos, 1.0), gl_ClipPlane[1]);\n"
	        "\tgl_ClipDistance[2] = dot(vec4(viewpos, 1.0), gl_ClipPlane[2]);\n"
	        "\tgl_ClipDistance[3] = dot(vec4(viewpos, 1.0), gl_ClipPlane[3]);\n"
	        "\tgl_ClipDistance[4] = dot(vec4(viewpos, 1.0), gl_ClipPlane[4]);\n"
	        "\tgl_ClipDistance[5] = dot(vec4(viewpos, 1.0), gl_ClipPlane[5]);\n"
	        "#endif\n"
	        "}\n\n"
	        "void geom_emit(int i)\n{\n\tgeom_copy(i);\n\tEmitVertex();\n}\n\n"
	        "void geom_emit_offset(int i, vec3 offset)\n{\n"
	        "\tgeom_copy(i);\n\tgeom_set_position(vs_varposition[i] + offset);\n\tEmitVertex();\n}\n\n");

	if (use_shells) {
		BLI_dynstr_append(ds,
		        "void main()\n{\n"
		        "\tfor (int layer = GEOM_LAYER_FIRST; layer <= GEOM_LAYER_LAST; layer++) {\n"
		        "\t\tif (layer < SHELL_LAYERS) {\n"
		        "\t\t\tfloat t = float(layer) / float(max(SHELL_LAYERS - 1, 1));\n"
		        "\t\t\tfor (int i = 0; i < 3; i++) {\n"
		        "\t\t\t\tgeom_copy(i);\n"
		        "\t\t\t\tif (layer > 0) {\n"
		        "\t\t\t\t\tvec3 shell_dir = normalize(mix(vs_varnormal[i], SHELL_DIR, SHELL_DIR_STRENGTH));\n"
		        "\t\t\t\t\tgeom_set_position(vs_varposition[i] + shell_dir * (SHELL_LENGTH * t));\n"
		        "\t\t\t\t}\n"
		        "\t\t\t\tvarshelllayer = t;\n"
		        "\t\t\t\tEmitVertex();\n"
		        "\t\t\t}\n"
		        "\t\t}\n"
		        "\t\telse {\n"
		        "\t\t\t/* Outline: inverted hull, reversed winding so back face culling keeps the rim. */\n"
		        "\t\t\tfor (int k = 0; k < 3; k++) {\n"
		        "\t\t\t\tint i = 2 - k;\n"
		        "\t\t\t\tgeom_copy(i);\n"
		        "\t\t\t\tgeom_set_position(vs_varposition[i] + vs_varnormal[i] * OUTLINE_WIDTH);\n"
		        "\t\t\t\tvarshelllayer = -1.0;\n"
		        "\t\t\t\tEmitVertex();\n"
		        "\t\t\t}\n"
		        "\t\t}\n"
		        "\t\tEndPrimitive();\n"
		        "\t}\n"
		        "}\n");
	}
	else if (use_strands) {
		BLI_dynstr_append(ds,
		        "float geom_strand_hash(vec2 p)\n{\n\treturn fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);\n}\n\n"
		        "void main()\n{\n"
		        "\tfor (int s = GEOM_STRAND_FIRST; s <= GEOM_STRAND_LAST; s++) {\n"
		        "\t\tif (s >= STRAND_DENSITY) continue;\n"
		        "\t\tfloat fid = float(gl_PrimitiveIDIn);\n"
		        "\t\t/* Pseudo-random barycentric coordinate: where this strand grows from. */\n"
		        "\t\tfloat b0 = geom_strand_hash(vec2(float(s), fid));\n"
		        "\t\tfloat b1 = geom_strand_hash(vec2(float(s) + 17.0, fid + 3.0)) * (1.0 - b0);\n"
		        "\t\tfloat b2 = 1.0 - b0 - b1;\n"
		        "\t\t/* LOD: strands fade out progressively between 0 and ~20 units (view space puts\n"
		        "\t\t * the camera at the origin, so length(base) is the camera distance). */\n"
		        "\t\tfloat lod = geom_strand_hash(vec2(float(s) + 5.0, fid + 9.0));\n"
		        "\t\tvec3 base = vs_varposition[0] * b0 + vs_varposition[1] * b1 + vs_varposition[2] * b2;\n"
		        "\t\tvec3 normal = normalize(vs_varnormal[0] * b0 + vs_varnormal[1] * b1 + vs_varnormal[2] * b2);\n"
		        "\t\tfloat camfade = clamp(1.0 - length(base) * 0.05, 0.0, 1.0);\n"
		        "\t\tif (lod > camfade) continue;\n"
		        "\t\tvec3 side = normalize(cross(normal, (abs(normal.z) < 0.9) ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0)));\n"
		        "\t\tconst float width = 0.015;\n"
		        "\t\tvec3 bend = side * (STRAND_CURVATURE * STRAND_LENGTH * (b0 - 0.5));\n"
		        "\t\tvec3 tip = base + normal * STRAND_LENGTH + bend;\n"
		        "\t\tgeom_copy(0);\n"
		        "\t\tgeom_set_position(base - side * width);\n"
		        "\t\tvarshelllayer = 0.0;\n"
		        "\t\tEmitVertex();\n"
		        "\t\tgeom_copy(0);\n"
		        "\t\tgeom_set_position(base + side * width);\n"
		        "\t\tvarshelllayer = 0.0;\n"
		        "\t\tEmitVertex();\n"
		        "\t\tgeom_copy(0);\n"
		        "\t\tgeom_set_position(tip);\n"
		        "\t\tvarshelllayer = 1.0;\n"
		        "\t\tEmitVertex();\n"
		        "\t\tEndPrimitive();\n"
		        "\t}\n"
		        "}\n");
	}
	else if (use_explode) {
		BLI_dynstr_append(ds,
		        "float geom_explode_hash(float p)\n{\n\treturn fract(sin(p * 12.9898) * 43758.5453);\n}\n\n"
		        "void main()\n{\n"
		        "\tvec3 normal = normalize(cross(vs_varposition[1] - vs_varposition[0], vs_varposition[2] - vs_varposition[0]));\n"
		        "\tfloat h = geom_explode_hash(float(gl_PrimitiveIDIn) + 1.0);\n"
		        "\tfloat ang = h * 6.28318530718;\n"
		        "\t/* Mostly along the face normal, with a per-triangle random direction mixed in so\n"
		        "\t * neighbouring triangles do not fly apart in lockstep. */\n"
		        "\tvec3 randdir = vec3(cos(ang), sin(ang), geom_explode_hash(float(gl_PrimitiveIDIn) * 2.0 + 7.0) * 2.0 - 1.0);\n"
		        "\tvec3 dir = normalize(normal + randdir * 0.5);\n"
		        "\tvec3 offset = dir * (EXPLODE_FACTOR * (0.25 + h * 0.75));\n"
		        "\tfor (int i = 0; i < 3; i++) {\n"
		        "\t\tgeom_copy(i);\n"
		        "\t\tgeom_set_position(vs_varposition[i] + offset);\n"
		        "\t\tEmitVertex();\n"
		        "\t}\n"
		        "\tEndPrimitive();\n"
		        "}\n");
	}
	else if (use_raw) {
		/* The user's own main(): only the vs_ inputs, the outputs and the helpers above are added. */
		BLI_dynstr_append(ds, "#line 1\n");
		BLI_dynstr_append(ds, rawcode);
		BLI_dynstr_append(ds, "\n");
		MEM_freeN(rawcode);
	}
	else {
		BLI_dynstr_append(ds, "void geometry();\n\nvoid main()\n{\n\tgeometry();\n}\n\n");
		BLI_dynstr_append(ds, "#line 1\n");
		BLI_dynstr_append(ds, stages->geomcode);
		BLI_dynstr_append(ds, "\n");
	}

	char *code = BLI_dynstr_get_cstring(ds);
	BLI_dynstr_free(ds);
	return code;
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

/* Library functions for the vertex stage: the functions vertex_nodes() reaches and the preprocessor
 * lines, without uniforms, varyings or the functions gpu_shader_vertex.glsl defines itself. */
static char *glsl_lib_strip_vertex(const char *code)
{
	if (!code || !glsl_material_library) {
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

	char *excluded = MEM_callocN(groups, "glsl strip excluded");
	const char *vertex_defined[] = {"srgb_to_linearrgb", "linearrgb_to_srgb", "is_srgb", "set_var_from_attr",
	                                "vertex_position", "vertex_normal", "vertex_instance_position"};
	for (int k = 0; k < ARRAY_SIZE(vertex_defined); k++) {
		const int g = glsl_lib_group_lookup(vertex_defined[k], (int)strlen(vertex_defined[k]));
		if (g >= 0) {
			excluded[g] = 1;
			collect.seen[g] = 1;
		}
	}

	glsl_foreach_ident(code, 0, (int)strlen(code), glsl_collect_dep, &collect);
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
		if (chunk->group == -1) {
			int k = chunk->start;
			while (k < chunk->end) {
				const int skip = glsl_skip_comment(glsl_material_library, k, chunk->end);
				if (skip != k) {
					k = skip;
				}
				else if (ELEM(glsl_material_library[k], ' ', '\t', '\n', '\r')) {
					k++;
				}
				else {
					break;
				}
			}
			if (k < chunk->end && glsl_material_library[k] == '#') {
				BLI_dynstr_nappend(ds, glsl_material_library + chunk->start, chunk->end - chunk->start);
			}
		}
		else if (collect.seen[chunk->group] && !excluded[chunk->group]) {
			BLI_dynstr_nappend(ds, glsl_material_library + chunk->start, chunk->end - chunk->start);
		}
	}
	char *result = BLI_dynstr_get_cstring(ds);
	BLI_dynstr_free(ds);

	MEM_freeN(excluded);
	MEM_freeN(collect.seen);
	MEM_freeN(collect.list);
	return result;
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

/* Upload the pass images now (as GPU_pass_bind() does on the first draw), without binding the shader.
 * Images of Material nodes inside a node tree are not texture slots of the material itself, so the
 * game loading did not upload them and the first draw paid it (decode + mipmaps, ~40 ms per image). */
void GPU_pass_load_images(GPUPass *pass, double time, int mipmap)
{
	GLint bound2d = 0, boundcube = 0;
	bool any = false;

	for (GPUInput *input = pass->inputs.first; input; input = input->next) {
		if (input->ima) {
			if (!any) {
				glGetIntegerv(GL_TEXTURE_BINDING_2D, &bound2d);
				glGetIntegerv(GL_TEXTURE_BINDING_CUBE_MAP, &boundcube);
				any = true;
			}
			/* Only the upload is wanted: the image owns its GPUTexture. Keeping it in input->tex would
			 * make gpu_inputs_free release the image texture when a never-bound pass is freed (shader
			 * warm-up restart): negative refcount, then a crash. GPU_pass_unbind clears it the same way. */
			GPU_texture_from_blender(input->ima, input->iuser, input->textarget, input->image_isdata, time, mipmap);
		}
	}

	if (any) {
		/* The uploads bind on the active unit: restore it for the caller's GL state. */
		glBindTexture(GL_TEXTURE_2D, bound2d);
		glBindTexture(GL_TEXTURE_CUBE_MAP, boundcube);
	}
}

/* glUniform calls of GPU_pass_update_uniforms(), for the game engine's per-frame work counters
 * (passUniforms in getRenderStats()). */
static int PASS_GL_CALLS = 0;

int GPU_pass_uniform_gl_calls_take(void)
{
	const int count = PASS_GL_CALLS;
	PASS_GL_CALLS = 0;
	return count;
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
			/* Not cached: a last-value cache here skipped nothing in RolimaRacer (~1700 calls per
			 * frame with and without it, 2026-10-09). */
			PASS_GL_CALLS++;
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
		/* image and preview textures belong to the Image/PreviewImage, not to the pass */
		else if (input->tex && !input->dynamictex && !input->ima && !input->prv)
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

/* GLSL Script node: the user function (called main in code) with one parameter per socket, the
 * inputs first, then the outputs. */
bool GPU_link_script(GPUMaterial *mat, const char *code, const char *wrapper, GPUNodeStack *in, GPUNodeStack *out,
                     const char **uniform_names, bool use_time, const char *orig_node_name)
{
	const char *name = gpu_material_add_script(mat, code, wrapper, use_time, orig_node_name);
	if (!name) {
		return false;
	}

	GPUNode *node = GPU_node_begin(name);
	if (in) {
		for (int i = 0; in[i].type != GPU_NONE; i++) {
			if (uniform_names && uniform_names[i] && !in[i].link) {
				/* A real uniform, sent on every bind: changing it from the game does not compile. */
				float *value = gpu_material_add_script_uniform(mat, uniform_names[i], in[i].vec,
				                                               GPU_DATATYPE_SIZE[in[i].type]);
				gpu_node_input_link(node, GPU_dynamic_uniform(value, GPU_DYNAMIC_NONE, NULL), in[i].type);
			}
			else {
				gpu_node_input_socket(node, &in[i]);
			}
		}
	}
	if (use_time) {
		gpu_node_input_link(node, GPU_builtin(GPU_TIME), GPU_FLOAT);
	}
	if (out) {
		for (int i = 0; out[i].type != GPU_NONE; i++) {
			gpu_node_output(node, out[i].type, &out[i].link);
		}
	}
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

static void gpu_nodes_tag(GPUNodeLink *link, char stage)
{
	GPUNode *node;
	GPUInput *input;

	if (!link->output)
		return;

	node = link->output->node;
	if (node->tag && (node->stage & stage))
		return;

	node->tag = true;
	node->stage |= stage;
	for (input = node->inputs.first; input; input = input->next)
		if (input->link)
			gpu_nodes_tag(input->link, stage);
}

static void gpu_nodes_prune(ListBase *nodes, GPUNodeLink *outlinks[8], GPUNodeLink *vertex_offset)
{
	GPUNode *node, *next;

	for (node = nodes->first; node; node = node->next) {
		node->tag = false;
		node->stage = 0;
	}

	for (unsigned short i = 0; i < 8; ++i) {
		if (outlinks[i]) {
			gpu_nodes_tag(outlinks[i], GPU_NODE_STAGE_FRAGMENT);
		}
	}
	if (vertex_offset) {
		gpu_nodes_tag(vertex_offset, GPU_NODE_STAGE_VERTEX);
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
        const bool use_new_shading,
        const GPUPassStages *stages)
{
	GPUShader *shader;
	GPUPass *pass;
	char *vertexcode, *geometrycode, *fragmentcode;
	static bool geometry_warned = false;

#if 0
	if (!FUNCTION_LIB) {
		GPU_nodes_free(nodes);
		return NULL;
	}
#endif

	const bool mesh_stages = stages && type == GPU_MATERIAL_TYPE_MESH && !use_opensubdiv;
	GPUNodeLink *vertex_offset = (mesh_stages && stages->vertex_offset && stages->vertex_offset->output) ?
	                             stages->vertex_offset : NULL;

	/* prune unused nodes */
	gpu_nodes_prune(nodes, outlinks, vertex_offset);

	gpu_nodes_get_vertex_attributes(nodes, attribs);
	gpu_nodes_get_builtin_flag(nodes, builtins);

	/* Geometry stage: user code, or Fur Shells/Outline. Without support (GLES/web) the material
	 * draws as if it had none. */
	bool use_geometry = false, use_shells = false, use_strands = false, use_explode = false;
	if (mesh_stages) {
		const bool wants_shells = stages->shell_layers > 1 || stages->outline_width != 0.0f;
		const bool wants_strands = stages->strand_density > 1;
		const bool wants_explode = stages->explode_factor != 0.0f;
		if (stages->geomcode || wants_shells || wants_strands || wants_explode) {
			if (GPU_geometry_shader_support()) {
				use_geometry = true;
				/* Shells/Outline, Strands and Explode are mutually exclusive generated geometry
				 * stages (a material only gets one); Shells/Outline wins since it is the oldest
				 * and most used, then Strands, then Explode. User geomcode always wins. */
				use_shells = !stages->geomcode && wants_shells;
				use_strands = !stages->geomcode && !use_shells && wants_strands;
				use_explode = !stages->geomcode && !use_shells && !use_strands && wants_explode;
			}
			else if (!geometry_warned) {
				geometry_warned = true;
				fprintf(stderr, "GPU: no geometry shader support, material geometry stages are ignored\n");
			}
		}
	}

	char *vertex_prefix = NULL;
	GeomVarying *geom_varyings = NULL;
	int geom_varyings_len = 0, geom_max_vertices = 0;
	if (use_geometry) {
		geom_varyings = MEM_mallocN(sizeof(GeomVarying) * GEOM_MAX_VARYINGS, "GeomVarying");
		geom_varyings_len = geom_collect_varyings(nodes, vertcode, use_instancing, geom_varyings);
	}
	if (use_geometry || vertex_offset) {
		DynStr *ds = BLI_dynstr_new();
		if (vertex_offset) {
			BLI_dynstr_append(ds, "#define USE_VERTEX_NODES\n");
		}
		if (use_geometry) {
			char *prefix = geom_vertex_prefix(geom_varyings, geom_varyings_len);
			BLI_dynstr_append(ds, prefix);
			MEM_freeN(prefix);
		}
		vertex_prefix = BLI_dynstr_get_cstring(ds);
		BLI_dynstr_free(ds);
	}

	/* generate code and compile with opengl */
	fragmentcode = code_generate_fragment(nodes, fragcode, type, outlinks, use_shells || use_strands, stages ? stages->scripts : NULL);
	vertexcode = code_generate_vertex(nodes, vertcode, type, use_instancing, vertex_prefix, vertex_offset,
	                                  stages ? stages->scripts : NULL);
	if (use_geometry) {
		geometrycode = code_generate_geometry_stage(geom_varyings, geom_varyings_len, stages,
		                                            use_shells, use_strands, use_explode,
		                                            &geom_max_vertices);
	}
	else {
		geometrycode = code_generate_geometry(nodes, use_opensubdiv);
	}
	MEM_SAFE_FREE(vertex_prefix);
	MEM_SAFE_FREE(geom_varyings);

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
	if (use_geometry) {
		flags |= GPU_SHADER_FLAGS_USER_GEOMETRY;
	}
	const unsigned int hash = shader_cache_hash(vertexcode, fragmentcode, geometrycode, flags);
	const bool use_cache = shader_cache_enabled();
	shader = use_cache ? shader_cache_acquire(vertexcode, fragmentcode, geometrycode, glsl_material_library, flags, hash) :
	                     NULL;
	if (shader && GPU_shader_prefetching()) {
		/* Already compiled, nothing to send ahead. The reference just acquired has to be given back:
		 * it used to be dropped here, which pinned the program for good and compiled it again. */
		shader_cache_release(shader);
		shader = NULL;
	}
	else if (shader) {
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
		                              use_geometry ? GL_TRIANGLES : 0,
		                              use_geometry ? GL_TRIANGLE_STRIP : 0,
		                              use_geometry ? geom_max_vertices : 0,
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
		if (geometrycode)
			MEM_freeN(geometrycode);
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
