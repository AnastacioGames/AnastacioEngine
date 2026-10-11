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

/** \file blender/nodes/shader/nodes/node_shader_glsl_script.c
 *  \ingroup shdnodes
 *
 * GLSL Script node (game engine): the Text holds a GLSL function called main. Its parameters
 * become the sockets, "in" (or no qualifier) as inputs and "out"/"inout" as outputs:
 *
 *   void main(float Fac, vec3 Vector, vec4 Color, out vec4 Result)
 *   {
 *       Result = mix(Color, vec4(Vector, 1.0), Fac);
 *   }
 *
 * float and int use a value socket, vec2/vec3 a vector socket and vec4 a color socket. The
 * function runs in the stage that uses it (fragment, or vertex when it feeds the Material Output
 * "Vertex Offset"). Other functions, constants, structs and macros may be written next to main;
 * the code generator gives them a name of their own per node (codegen_script_names in
 * gpu_codegen.c), so two scripts may use the same helper names.
 *
 * A uniform whose name starts with "u_" becomes one more input socket:
 *
 *   uniform float u_speed;  // @min 0 @max 2 @default 0.5
 *   uniform vec4 u_color;   // @default 1 0.5 0 1
 *
 * While the socket is not linked the value is a real uniform, sent on every draw
 * (KX_BlenderMaterial.setScriptUniform changes it in the game without compiling). TIME is the time
 * of the game, without a Time node.
 */

#include <float.h>
#include <stdlib.h>

#include "node_shader_util.h"

#include "BLI_dynstr.h"

#include "BKE_text.h"

#include "DNA_text_types.h"

#define SCRIPT_MAX_PARAMS 64

typedef struct ScriptParam {
	char glsltype[16];
	char name[64];
	bool output;
	int socktype;
	/* "uniform <type> u_<name>;" instead of a parameter of main, with its optional annotations. */
	bool uniform;
	bool has_min, has_max;
	float min, max;
	int totdefault;
	float def[4];
} ScriptParam;

static bool script_ident_char(char c)
{
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_';
}

static const char *script_skip_space(const char *p)
{
	for (;;) {
		while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') {
			p++;
		}
		if (p[0] == '/' && p[1] == '/') {
			while (*p && *p != '\n') p++;
		}
		else if (p[0] == '/' && p[1] == '*') {
			const char *end = strstr(p + 2, "*/");
			p = end ? end + 2 : p + strlen(p);
		}
		else {
			return p;
		}
	}
}

static const char *script_read_ident(const char *p, char *r_ident, int size)
{
	int n = 0;
	while (script_ident_char(*p)) {
		if (n < size - 1) {
			r_ident[n++] = *p;
		}
		p++;
	}
	r_ident[n] = '\0';
	return p;
}

static int script_socket_type(const char *glsltype)
{
	if (STREQ(glsltype, "float") || STREQ(glsltype, "int")) return SOCK_FLOAT;
	if (STREQ(glsltype, "vec2") || STREQ(glsltype, "vec3")) return SOCK_VECTOR;
	if (STREQ(glsltype, "vec4")) return SOCK_RGBA;
	return -1;
}

/* Parameters of "main(...)" in code; -1 when there is no usable main. */
static int script_parse(const char *code, ScriptParam *params)
{
	const char *p = code;
	while (p && *p) {
		const char *found = strstr(p, "main");
		if (!found) {
			return -1;
		}
		const bool word_start = (found == code) || !script_ident_char(found[-1]);
		const char *after = script_skip_space(found + 4);
		if (!word_start || script_ident_char(found[4]) || *after != '(') {
			p = found + 4;
			continue;
		}

		int tot = 0;
		memset(params, 0, sizeof(ScriptParam) * SCRIPT_MAX_PARAMS);
		p = script_skip_space(after + 1);
		while (*p && *p != ')') {
			char words[4][64];
			int nwords = 0;
			while (*p && *p != ',' && *p != ')') {
				p = script_skip_space(p);
				if (script_ident_char(*p)) {
					if (nwords < 4) {
						p = script_read_ident(p, words[nwords], sizeof(words[nwords]));
						nwords++;
					}
					else {
						char skip[64];
						p = script_read_ident(p, skip, sizeof(skip));
					}
				}
				else if (*p && *p != ',' && *p != ')') {
					p++; /* arrays and the like are not supported, the type check below rejects them */
				}
			}
			if (nwords >= 2 && tot < SCRIPT_MAX_PARAMS) {
				ScriptParam *param = &params[tot];
				param->output = false;
				for (int w = 0; w < nwords - 2; w++) {
					if (STREQ(words[w], "out") || STREQ(words[w], "inout")) {
						param->output = true;
					}
				}
				BLI_strncpy(param->glsltype, words[nwords - 2], sizeof(param->glsltype));
				BLI_strncpy(param->name, words[nwords - 1], sizeof(param->name));
				param->socktype = script_socket_type(param->glsltype);
				if (param->socktype == -1) {
					return -1;
				}
				tot++;
			}
			if (*p == ',') {
				p++;
			}
		}
		return tot;
	}
	return -1;
}

/* "@min 0 @max 2 @default 0.5" in the comment that ends the line of a uniform. */
static void script_parse_annotations(const char *p, ScriptParam *param)
{
	while (*p == ' ' || *p == '\t') {
		p++;
	}
	if (!(p[0] == '/' && p[1] == '/')) {
		return;
	}
	while (*p && *p != '\n') {
		if (*p == '@') {
			char word[16];
			char *end;
			p = script_read_ident(p + 1, word, sizeof(word));
			if (STREQ(word, "min") || STREQ(word, "max")) {
				const float value = (float)strtod(p, &end);
				if (end != p) {
					if (word[1] == 'i') {
						param->min = value;
						param->has_min = true;
					}
					else {
						param->max = value;
						param->has_max = true;
					}
					p = end;
				}
			}
			else if (STREQ(word, "default")) {
				param->totdefault = 0;
				while (param->totdefault < 4) {
					while (*p == ' ' || *p == '\t' || *p == ',' || *p == '(') {
						p++;
					}
					const float value = (float)strtod(p, &end);
					if (end == p) {
						break;
					}
					param->def[param->totdefault++] = value;
					p = end;
				}
			}
		}
		else {
			p++;
		}
	}
}

/* Top level "uniform <type> u_<name>" declarations, added after the tot parameters of main. With
 * blank the word "uniform" is erased from code: the name becomes a global that the wrapper fills
 * from the socket, which may be linked to other nodes. */
static int script_parse_uniforms(char *code, ScriptParam *params, int tot, bool blank)
{
	char *p = code;
	int braces = 0;

	while (*p) {
		p = (char *)script_skip_space(p);
		if (!*p) {
			break;
		}
		if (!script_ident_char(*p)) {
			if (*p == '{') braces++;
			else if (*p == '}') braces--;
			p++;
			continue;
		}

		char word[64];
		char *start = p;
		p = (char *)script_read_ident(p, word, sizeof(word));
		if (braces != 0 || !STREQ(word, "uniform") || tot >= SCRIPT_MAX_PARAMS) {
			continue;
		}

		ScriptParam *param = &params[tot];
		memset(param, 0, sizeof(*param));
		const char *q = script_skip_space(p);
		q = script_read_ident(q, param->glsltype, sizeof(param->glsltype));
		q = script_skip_space(q);
		q = script_read_ident(q, param->name, sizeof(param->name));
		param->socktype = script_socket_type(param->glsltype);
		if (param->socktype == -1 || !(param->name[0] == 'u' && param->name[1] == '_')) {
			continue;
		}
		bool duplicate = false;
		for (int i = 0; i < tot; i++) {
			if (STREQ(params[i].name, param->name)) {
				duplicate = true;
			}
		}
		if (duplicate) {
			continue;
		}

		param->uniform = true;
		while (*q && *q != ';' && *q != '\n') {
			q++;
		}
		if (*q == ';') {
			script_parse_annotations(q + 1, param);
		}
		if (blank) {
			memset(start, ' ', 7);
		}
		tot++;
	}
	return tot;
}

static bool script_uses_word(const char *code, const char *word)
{
	const size_t len = strlen(word);
	for (const char *p = strstr(code, word); p; p = strstr(p + len, word)) {
		if ((p == code || !script_ident_char(p[-1])) && !script_ident_char(p[len])) {
			return true;
		}
	}
	return false;
}

static int script_read(bNode *node, ScriptParam *params, char **r_code)
{
	Text *text = (Text *)node->id;
	char *code = text ? txt_to_buf(text) : NULL;
	int tot = code ? script_parse(code, params) : -1;
	if (tot >= 0) {
		tot = script_parse_uniforms(code, params, tot, r_code != NULL);
	}
	if (r_code) {
		*r_code = code;
	}
	else if (code) {
		MEM_freeN(code);
	}
	return tot;
}

/* A float uniform with both limits is drawn as a slider. */
static int script_socket_subtype(const ScriptParam *param)
{
	return (param->uniform && param->socktype == SOCK_FLOAT && param->has_min && param->has_max) ? PROP_FACTOR :
	                                                                                               PROP_NONE;
}

static bool script_socket_matches(const bNodeSocket *sock, const ScriptParam *param)
{
	return STREQ(sock->identifier, param->name) && sock->type == param->socktype &&
	       sock->typeinfo->subtype == script_socket_subtype(param);
}

static bNodeSocket *script_find_socket(ListBase *sockets, const ScriptParam *param)
{
	for (bNodeSocket *sock = sockets->first; sock; sock = sock->next) {
		if (script_socket_matches(sock, param)) {
			return sock;
		}
	}
	return NULL;
}

/* Limits of a uniform socket follow the annotations; the value only when the socket is new. */
static void script_socket_uniform(bNodeSocket *sock, const ScriptParam *param, bool is_new)
{
	const float min = param->has_min ? param->min : -FLT_MAX;
	const float max = param->has_max ? param->max : FLT_MAX;
	float def[4] = {0.0f, 0.0f, 0.0f, 1.0f};

	for (int i = 0; i < 4; i++) {
		if (i < param->totdefault) {
			def[i] = param->def[i];
		}
		else if (param->totdefault == 1 && i < 3) {
			def[i] = param->def[0];
		}
	}

	if (sock->type == SOCK_FLOAT) {
		bNodeSocketValueFloat *dval = sock->default_value;
		dval->min = min;
		dval->max = max;
		if (is_new && param->totdefault) {
			dval->value = def[0];
		}
		CLAMP(dval->value, min, max);
	}
	else if (sock->type == SOCK_VECTOR) {
		bNodeSocketValueVector *dval = sock->default_value;
		dval->min = min;
		dval->max = max;
		if (is_new && param->totdefault) {
			copy_v3_v3(dval->value, def);
		}
	}
	else if (sock->type == SOCK_RGBA) {
		bNodeSocketValueRGBA *dval = sock->default_value;
		if (is_new && param->totdefault) {
			copy_v4_v4(dval->value, def);
		}
	}
}

/* Sockets follow the parameters of main; sockets that still match keep their links and values. */
static void node_shader_update_glsl_script(bNodeTree *ntree, bNode *node)
{
	ScriptParam params[SCRIPT_MAX_PARAMS];
	int tot = script_read(node, params, NULL);
	if (tot < 0) {
		/* No valid main (yet): keep the sockets, the user may be typing. */
		return;
	}

	for (int in_out = SOCK_IN; in_out <= SOCK_OUT; in_out++) {
		ListBase *sockets = (in_out == SOCK_IN) ? &node->inputs : &node->outputs;
		bNodeSocket *sock, *next;

		for (sock = sockets->first; sock; sock = next) {
			next = sock->next;
			bool keep = false;
			for (int i = 0; i < tot; i++) {
				if (params[i].output == (in_out == SOCK_OUT) && script_socket_matches(sock, &params[i])) {
					keep = true;
				}
			}
			if (!keep) {
				nodeRemoveSocket(ntree, node, sock);
			}
		}

		for (int i = 0; i < tot; i++) {
			if (params[i].output != (in_out == SOCK_OUT)) {
				continue;
			}
			sock = script_find_socket(sockets, &params[i]);
			const bool is_new = (sock == NULL);
			if (!sock) {
				sock = nodeAddStaticSocket(ntree, node, in_out, params[i].socktype,
				                           script_socket_subtype(&params[i]), params[i].name, params[i].name);
			}
			if (params[i].uniform) {
				script_socket_uniform(sock, &params[i], is_new);
			}
			/* Same order as the parameters. */
			BLI_remlink(sockets, sock);
			BLI_addtail(sockets, sock);
		}
	}
}

static const char *script_socket_glsl(int socktype)
{
	return (socktype == SOCK_FLOAT) ? "float" : (socktype == SOCK_VECTOR) ? "vec3" : "vec4";
}

/* SCRIPT_ENTRY(inputs..., [time,] outputs...) calls SCRIPT_MAIN with the parameters in the user
 * order and converts int/vec2 from and to the socket types. The uniforms of the script are globals
 * here, filled from their sockets before the call. */
static char *script_wrapper(const ScriptParam *params, int tot, bool use_time)
{
	DynStr *ds = BLI_dynstr_new();
	bool first = true;

	BLI_dynstr_append(ds, "void SCRIPT_ENTRY(");
	for (int pass = 0; pass < 2; pass++) {
		for (int i = 0; i < tot; i++) {
			if (params[i].output != (pass == 1)) {
				continue;
			}
			BLI_dynstr_appendf(ds, "%s%s%s scr_p%d", first ? "" : ", ", pass ? "out " : "",
			                   script_socket_glsl(params[i].socktype), i);
			first = false;
		}
		if (pass == 0 && use_time) {
			BLI_dynstr_appendf(ds, "%sfloat scr_time", first ? "" : ", ");
			first = false;
		}
	}
	BLI_dynstr_append(ds, ")\n{\n");

	for (int i = 0; i < tot; i++) {
		if (params[i].output && (STREQ(params[i].glsltype, "int") || STREQ(params[i].glsltype, "vec2"))) {
			BLI_dynstr_appendf(ds, "\t%s scr_t%d;\n", params[i].glsltype, i);
		}
	}
	if (use_time) {
		BLI_dynstr_append(ds, "\tTIME = scr_time;\n");
	}

	/* Uniforms first, then the call. */
	for (int pass = 0; pass < 2; pass++) {
		first = true;
		if (pass == 1) {
			BLI_dynstr_append(ds, "\tSCRIPT_MAIN(");
		}
		for (int i = 0; i < tot; i++) {
			const char *type = params[i].glsltype;
			if (params[i].uniform != (pass == 0)) {
				continue;
			}
			if (pass == 0) {
				BLI_dynstr_appendf(ds, "\t%s = ", params[i].name);
			}
			else if (!first) {
				BLI_dynstr_append(ds, ", ");
			}
			first = false;

			if (params[i].output) {
				if (STREQ(type, "int") || STREQ(type, "vec2"))
					BLI_dynstr_appendf(ds, "scr_t%d", i);
				else
					BLI_dynstr_appendf(ds, "scr_p%d", i);
			}
			else {
				if (STREQ(type, "int"))
					BLI_dynstr_appendf(ds, "int(scr_p%d)", i);
				else if (STREQ(type, "vec2"))
					BLI_dynstr_appendf(ds, "scr_p%d.xy", i);
				else
					BLI_dynstr_appendf(ds, "scr_p%d", i);
			}
			if (pass == 0) {
				BLI_dynstr_append(ds, ";\n");
			}
		}
	}
	BLI_dynstr_append(ds, ");\n");

	for (int i = 0; i < tot; i++) {
		if (params[i].output) {
			if (STREQ(params[i].glsltype, "int"))
				BLI_dynstr_appendf(ds, "\tscr_p%d = float(scr_t%d);\n", i, i);
			else if (STREQ(params[i].glsltype, "vec2"))
				BLI_dynstr_appendf(ds, "\tscr_p%d = vec3(scr_t%d, 0.0);\n", i, i);
		}
	}
	BLI_dynstr_append(ds, "}\n");

	char *code = BLI_dynstr_get_cstring(ds);
	BLI_dynstr_free(ds);
	return code;
}

static int node_shader_gpu_glsl_script(GPUMaterial *mat, bNode *node, bNodeExecData *UNUSED(execdata), GPUNodeStack *in, GPUNodeStack *out)
{
	ScriptParam params[SCRIPT_MAX_PARAMS];
	char *code = NULL;
	int tot = script_read(node, params, &code);
	int ok = 0;

	/* The sockets must match main, otherwise the call would not compile. */
	int totin = 0, totout = 0, sockin = 0, sockout = 0;
	for (int i = 0; i < tot; i++) {
		if (params[i].output) totout++; else totin++;
	}
	while (in && in[sockin].type != GPU_NONE) sockin++;
	while (out && out[sockout].type != GPU_NONE) sockout++;

	if (code && tot >= 0 && totin == sockin && totout == sockout && totout > 0) {
		/* The input sockets are in the order of the parameters. */
		const char *uniform_names[SCRIPT_MAX_PARAMS];
		int input = 0;
		for (int i = 0; i < tot; i++) {
			if (!params[i].output) {
				uniform_names[input++] = params[i].uniform ? params[i].name : NULL;
			}
		}
		const bool use_time = script_uses_word(code, "TIME");
		char *wrapper = script_wrapper(params, tot, use_time);
		ok = GPU_link_script(mat, code, wrapper, in, out, uniform_names, use_time, node->name);
		MEM_freeN(wrapper);
	}
	MEM_SAFE_FREE(code);
	return ok;
}

void register_node_type_sh_glsl_script(void)
{
	static bNodeType ntype;

	sh_node_type_base(&ntype, SH_NODE_GLSL_SCRIPT, "GLSL Script", NODE_CLASS_SCRIPT, 0);
	node_type_compatibility(&ntype, NODE_OLD_SHADING | NODE_NEW_SHADING);
	node_type_socket_templates(&ntype, NULL, NULL);
	node_type_size(&ntype, 160, 100, 500);
	node_type_update(&ntype, node_shader_update_glsl_script, NULL);
	node_type_gpu(&ntype, node_shader_gpu_glsl_script);

	nodeRegisterType(&ntype);
}
