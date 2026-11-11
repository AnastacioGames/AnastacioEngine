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
 *
 * An int or float uniform may list named options, drawn as a menu in the node:
 *
 *   uniform int u_mode;  // @choice Linear=0, Smooth=1, Step=2 @default 1
 *
 * The socket stays a number holding the option value. Any broken rule (see script_choice_build)
 * leaves the plain number field.
 */

#include <float.h>
#include <stdlib.h>

#include "node_shader_util.h"

#include "BLI_dynstr.h"

#include "BLI_glsl_annotations.h"

#include "BKE_idprop.h"
#include "BKE_text.h"

#include "DNA_text_types.h"

#define SCRIPT_MAX_PARAMS 64

typedef struct ScriptParam {
	char glsltype[16];
	char name[64];
	bool output;
	int socktype;
	/* "uniform <type> u_<name>;" instead of a parameter of main, with its optional annotations
	 * (ann.choice points inside the code buffer). */
	bool uniform;
	GLSLAnnotations ann;
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
			BLI_glsl_annotations_parse(q + 1, &param->ann);
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

/* ---------------------------------------------------------------------------------------------
 * Header format (docs/glsl-node-files.md): a node file whose first comment lines declare
 *
 *   // @name Noise                         // @category Generators
 *   // @output gray                        // @input mask: gray = 1
 *   // @param scale: float(1, 64) = 6      // @param style: enum(Soft, Hard) = Soft
 *   vec4 node(vec2 uv) { return vec4(in_mask(uv) * params.scale); }
 *
 * is translated here to the plain format above (u_ uniforms + main), so the sockets, the uniforms,
 * @choice menus and the error colouring all stay the ones of the GLSL Script node. The original
 * text follows a "#line 1", so compile errors still give the line of the Text. */

#define HEADER_MAX_ENTRIES 32

enum {
	HDR_IN_COLOR,
	HDR_IN_GRAY,
	HDR_FLOAT,
	HDR_INT,
	HDR_BOOL,
	HDR_COLOR,
	HDR_ENUM,
};

typedef struct HeaderEntry {
	char name[48];
	int kind;
	float min, max;
	float def[4];
	int totdef;
	char choice[512];
} HeaderEntry;

typedef struct HeaderInfo {
	char name[64];
	bool output_gray;
} HeaderInfo;

/* "// @tag rest": pointer to rest (spaces skipped), NULL when the line is another tag or text. */
static const char *header_tag(const char *line, const char *tag)
{
	const size_t len = strlen(tag);
	if (line[0] != '@' || strncmp(line + 1, tag, len) != 0 || script_ident_char(line[len + 1])) {
		return NULL;
	}
	const char *p = line + len + 1;
	while (*p == ' ' || *p == '\t') p++;
	return p;
}

static const char *header_space(const char *p)
{
	while (*p == ' ' || *p == '\t') p++;
	return p;
}

/* Up to 4 numbers separated by commas or spaces, until end of line. */
static int header_numbers(const char *p, float r_values[4])
{
	int tot = 0;
	while (tot < 4) {
		p = header_space(p);
		while (*p == ',') p = header_space(p + 1);
		if (!*p || *p == '\n' || *p == '\r') {
			break;
		}
		char *end;
		const double v = strtod(p, &end);
		if (end == p) {
			return -1;
		}
		r_values[tot++] = (float)v;
		p = end;
	}
	return tot;
}

/* "name: type(args) = default", type already known to be an input (is_input) or a param. */
static bool header_entry(const char *p, bool is_input, HeaderEntry *e)
{
	memset(e, 0, sizeof(*e));
	p = script_read_ident(header_space(p), e->name, sizeof(e->name));
	if (!e->name[0]) {
		return false;
	}
	p = header_space(p);
	if (*p != ':') {
		return false;
	}
	char type[16];
	p = script_read_ident(header_space(p + 1), type, sizeof(type));
	p = header_space(p);

	char args[512] = "";
	if (*p == '(') {
		const char *close = strchr(p, ')');
		if (!close || close - p - 1 >= (int)sizeof(args)) {
			return false;
		}
		BLI_strncpy(args, p + 1, (size_t)(close - p));
		p = header_space(close + 1);
	}
	const char *def = NULL;
	if (*p == '=') {
		def = header_space(p + 1);
	}
	else if (*p && *p != '\n' && *p != '\r') {
		return false;
	}

	if (is_input) {
		if (STREQ(type, "color")) e->kind = HDR_IN_COLOR;
		else if (STREQ(type, "gray")) e->kind = HDR_IN_GRAY;
		else return false;
	}
	else if (STREQ(type, "float") || STREQ(type, "int")) {
		e->kind = STREQ(type, "float") ? HDR_FLOAT : HDR_INT;
		float lim[4];
		if (header_numbers(args, lim) != 2 || lim[0] > lim[1]) {
			return false;
		}
		e->min = lim[0];
		e->max = lim[1];
	}
	else if (STREQ(type, "bool")) e->kind = HDR_BOOL;
	else if (STREQ(type, "color")) e->kind = HDR_COLOR;
	else if (STREQ(type, "enum")) {
		e->kind = HDR_ENUM;
		/* "A, B, C" -> "A=0, B=1, C=2"; the default is a label. */
		DynStr *ds = BLI_dynstr_new();
		const char *a = args;
		int index = 0, def_index = 0;
		char label[64];
		while (*(a = header_space(a))) {
			a = script_read_ident(a, label, sizeof(label));
			if (!label[0]) {
				BLI_dynstr_free(ds);
				return false;
			}
			if (def) {
				char want[64];
				script_read_ident(def, want, sizeof(want));
				if (STREQ(want, label)) def_index = index;
			}
			BLI_dynstr_appendf(ds, "%s%s=%d", index ? ", " : "", label, index);
			index++;
			a = header_space(a);
			if (*a == ',') a++;
			else if (*a) {
				BLI_dynstr_free(ds);
				return false;
			}
		}
		const int len = BLI_dynstr_get_len(ds);
		if (index == 0 || len >= (int)sizeof(e->choice)) {
			BLI_dynstr_free(ds);
			return false;
		}
		BLI_dynstr_get_cstring_ex(ds, e->choice);
		BLI_dynstr_free(ds);
		e->def[0] = (float)def_index;
		e->totdef = 1;
		return true;
	}
	else {
		return false;
	}

	if (e->kind == HDR_BOOL) {
		e->def[0] = (def && STREQLEN(def, "true", 4)) ? 1.0f : 0.0f;
		e->totdef = 1;
		return !def || STREQLEN(def, "true", 4) || STREQLEN(def, "false", 5);
	}
	if (def) {
		e->totdef = header_numbers(def, e->def);
		if (e->totdef < 0) {
			return false;
		}
	}
	if (e->kind == HDR_COLOR || e->kind == HDR_IN_COLOR) {
		/* One number is a gray, three a colour; alpha is always 1. */
		const float base = (e->kind == HDR_COLOR) ? 0.5f : 0.0f;
		if (e->totdef == 0) {
			e->def[0] = e->def[1] = e->def[2] = base;
		}
		else if (e->totdef == 1) {
			e->def[1] = e->def[2] = e->def[0];
		}
		else if (e->totdef != 3) {
			return false;
		}
		e->def[3] = 1.0f;
		e->totdef = 4;
	}
	else if (e->totdef > 1) {
		return false;
	}
	else if (e->totdef == 0) {
		e->def[0] = (e->kind == HDR_FLOAT || e->kind == HDR_INT) ? e->min : 0.0f;
		e->totdef = 1;
	}
	if (e->kind == HDR_FLOAT || e->kind == HDR_INT) {
		CLAMP(e->def[0], e->min, e->max);
	}
	return true;
}

static void header_error(const bNode *node, int line, const char *msg)
{
	printf("GLSL node \"%s\", line %d: %s\n", node ? node->name : "?", line, msg);
}

/* Translated code, or NULL when src is not in the header format (no "@output") or is broken
 * (r_broken set, the reason printed with its line). */
static char *script_translate_header(const bNode *node, const char *src, HeaderInfo *info, bool *r_broken)
{
	HeaderEntry entries[HEADER_MAX_ENTRIES];
	int tot = 0, totin = 0, totparam = 0, line = 0;
	bool has_output = false;

	memset(info, 0, sizeof(*info));
	*r_broken = false;

	/* The header: comment lines (blank lines allowed) before the first line of code. */
	for (const char *p = src; *p; ) {
		line++;
		const char *eol = strchr(p, '\n');
		const size_t len = eol ? (size_t)(eol - p) : strlen(p);
		char buf[1024];
		BLI_strncpy(buf, p, MIN2(len + 1, sizeof(buf)));
		p = eol ? eol + 1 : p + len;

		const char *s = header_space(buf);
		if (!*s || *s == '\r') {
			continue;
		}
		if (s[0] != '/' || s[1] != '/') {
			break;
		}
		s = header_space(s + 2);
		const char *rest;
		if ((rest = header_tag(s, "output"))) {
			has_output = true;
			info->output_gray = STREQLEN(rest, "gray", 4);
			if (!info->output_gray && !STREQLEN(rest, "color", 5)) {
				header_error(node, line, "@output must be color or gray");
				*r_broken = true;
			}
		}
		else if ((rest = header_tag(s, "name"))) {
			BLI_strncpy(info->name, rest, sizeof(info->name));
			for (int n = (int)strlen(info->name) - 1; n >= 0 && strchr(" \t\r", info->name[n]); n--) {
				info->name[n] = '\0';
			}
		}
		else if ((rest = header_tag(s, "input")) || (rest = header_tag(s, "param"))) {
			const bool is_input = header_tag(s, "input") != NULL;
			if (tot >= HEADER_MAX_ENTRIES || (is_input && totin >= 8) || (!is_input && totparam >= 16)) {
				header_error(node, line, "too many inputs (8) or params (16)");
				*r_broken = true;
				continue;
			}
			HeaderEntry *e = &entries[tot];
			if (!header_entry(rest, is_input, e)) {
				header_error(node, line, is_input ? "expected: name: color|gray = default" :
				             "expected: name: float(min, max) = v | int(min, max) = v | bool = true | "
				             "color = r, g, b | enum(A, B) = A");
				*r_broken = true;
				continue;
			}
			for (int i = 0; i < tot; i++) {
				if (STREQ(entries[i].name, e->name)) {
					header_error(node, line, "name already used");
					*r_broken = true;
				}
			}
			tot++;
			if (is_input) totin++; else totparam++;
		}
		else if (header_tag(s, "shading")) {
			header_error(node, line, "@shading nodes are not supported yet, use vec4 node(vec2 uv)");
			*r_broken = true;
		}
	}

	if (!has_output) {
		*r_broken = false;
		return NULL;
	}
	if (!script_uses_word(src, "node")) {
		header_error(node, 1, "missing vec4 node(vec2 uv)");
		*r_broken = true;
	}
	if (*r_broken) {
		return NULL;
	}

	DynStr *ds = BLI_dynstr_new();
	for (int i = 0; i < tot; i++) {
		const HeaderEntry *e = &entries[i];
		switch (e->kind) {
			case HDR_IN_COLOR:
			case HDR_COLOR:
				BLI_dynstr_appendf(ds, "uniform vec4 u_%s; // @default %g %g %g %g\n", e->name,
				                   e->def[0], e->def[1], e->def[2], e->def[3]);
				break;
			case HDR_IN_GRAY:
				BLI_dynstr_appendf(ds, "uniform float u_%s; // @default %g\n", e->name, e->def[0]);
				break;
			case HDR_FLOAT:
				BLI_dynstr_appendf(ds, "uniform float u_%s; // @min %g @max %g @default %g\n", e->name,
				                   e->min, e->max, e->def[0]);
				break;
			case HDR_INT:
				BLI_dynstr_appendf(ds, "uniform int u_%s; // @min %g @max %g @default %g\n", e->name,
				                   e->min, e->max, e->def[0]);
				break;
			case HDR_BOOL:
				BLI_dynstr_appendf(ds, "uniform int u_%s; // @choice Off=0, On=1 @default %d\n", e->name,
				                   (int)e->def[0]);
				break;
			case HDR_ENUM:
				BLI_dynstr_appendf(ds, "uniform int u_%s; // @choice %s @default %d\n", e->name, e->choice,
				                   (int)e->def[0]);
				break;
		}
	}
	if (totparam) {
		BLI_dynstr_append(ds, "struct Params {");
		for (int i = 0; i < tot; i++) {
			const HeaderEntry *e = &entries[i];
			const char *type = (e->kind == HDR_FLOAT) ? "float" : (e->kind == HDR_BOOL) ? "bool" :
			                   (e->kind == HDR_COLOR) ? "vec3" : (e->kind == HDR_INT || e->kind == HDR_ENUM) ? "int" :
			                   NULL;
			if (type) {
				BLI_dynstr_appendf(ds, " %s %s;", type, e->name);
			}
		}
		BLI_dynstr_append(ds, " };\nParams params;\n");
	}
	for (int i = 0; i < tot; i++) {
		const HeaderEntry *e = &entries[i];
		if (e->kind == HDR_IN_COLOR) {
			BLI_dynstr_appendf(ds, "vec4 in_%s(vec2 uv) { return u_%s; }\n", e->name, e->name);
		}
		else if (e->kind == HDR_IN_GRAY) {
			BLI_dynstr_appendf(ds, "float in_%s(vec2 uv) { return u_%s; }\n", e->name, e->name);
		}
	}
	BLI_dynstr_append(ds, "vec2 res() { return vec2(1024.0); }\n#line 1\n");
	BLI_dynstr_append(ds, src);
	BLI_dynstr_appendf(ds, "\nvoid main(vec3 UV, out %s)\n{\n", info->output_gray ? "float Value" : "vec4 Color");
	for (int i = 0; i < tot; i++) {
		const HeaderEntry *e = &entries[i];
		if (e->kind == HDR_BOOL) BLI_dynstr_appendf(ds, "\tparams.%s = (u_%s != 0);\n", e->name, e->name);
		else if (e->kind == HDR_COLOR) BLI_dynstr_appendf(ds, "\tparams.%s = u_%s.rgb;\n", e->name, e->name);
		else if (e->kind != HDR_IN_COLOR && e->kind != HDR_IN_GRAY)
			BLI_dynstr_appendf(ds, "\tparams.%s = u_%s;\n", e->name, e->name);
	}
	BLI_dynstr_append(ds, info->output_gray ? "\tValue = node(UV.xy).r;\n}\n" : "\tColor = node(UV.xy);\n}\n");

	char *code = MEM_mallocN((size_t)BLI_dynstr_get_len(ds) + 1, "glsl header script");
	BLI_dynstr_get_cstring_ex(ds, code);
	BLI_dynstr_free(ds);
	return code;
}

/* "u_uv_offset" -> "Uv Offset" for the sockets of a header node. */
static void script_pretty_name(const char *name, char *r_name, int size)
{
	if (name[0] == 'u' && name[1] == '_') {
		name += 2;
	}
	int n = 0;
	bool word_start = true;
	for (; *name && n < size - 1; name++) {
		char c = (*name == '_') ? ' ' : *name;
		if (word_start && c >= 'a' && c <= 'z') {
			c = (char)(c - 'a' + 'A');
		}
		word_start = (c == ' ');
		r_name[n++] = c;
	}
	r_name[n] = '\0';
}

static int script_read_ex(bNode *node, ScriptParam *params, char **r_code, HeaderInfo *r_info, bool *r_header)
{
	Text *text = (Text *)node->id;
	char *code = text ? txt_to_buf(text) : NULL;
	HeaderInfo info;
	bool broken = false;
	*r_header = false;

	if (code) {
		char *translated = script_translate_header(node, code, &info, &broken);
		if (translated || broken) {
			MEM_freeN(code);
			code = translated;
			*r_header = true;
			if (r_info) {
				*r_info = info;
			}
		}
	}
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

static int script_read(bNode *node, ScriptParam *params, char **r_code)
{
	bool header;
	return script_read_ex(node, params, r_code, NULL, &header);
}

/* A float uniform with both limits is drawn as a slider. */
static int script_socket_subtype(const ScriptParam *param)
{
	return (param->uniform && param->socktype == SOCK_FLOAT && param->ann.has_min && param->ann.has_max) ? PROP_FACTOR :
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

/* "@choice" of an int/float uniform, see BLI_glsl_choice_build. */
static bool script_choice_build(const ScriptParam *param, char r_buf[BLI_GLSL_CHOICE_BUF], float *r_default)
{
	return param->uniform && param->socktype == SOCK_FLOAT && BLI_glsl_choice_build(&param->ann, r_buf, r_default);
}

/* Stores the options for the menu of drawnode.c, or removes them (choice NULL). */
static void script_socket_choice(bNodeSocket *sock, const char *choice)
{
	IDProperty *old = sock->prop ?
	        IDP_GetPropertyTypeFromGroup(sock->prop, SH_NODE_GLSL_SCRIPT_CHOICE, IDP_STRING) : NULL;

	if (!choice) {
		if (old) {
			IDP_FreeFromGroup(sock->prop, old);
		}
		return;
	}
	if (old && STREQ(IDP_String(old), choice)) {
		return;
	}
	if (!sock->prop) {
		IDPropertyTemplate val = {0};
		sock->prop = IDP_New(IDP_GROUP, &val, "RNA_NodeSocket");
	}
	IDP_ReplaceInGroup(sock->prop, IDP_NewString(choice, SH_NODE_GLSL_SCRIPT_CHOICE, (int)strlen(choice) + 1));
}

/* Limits of a uniform socket follow the annotations; the value only when the socket is new.
 * choice_default, when not NULL, is the value of a new socket with "@choice". */
static void script_socket_uniform(bNodeSocket *sock, const ScriptParam *param, bool is_new,
                                  const float *choice_default)
{
	const float min = param->ann.has_min ? param->ann.min : -FLT_MAX;
	const float max = param->ann.has_max ? param->ann.max : FLT_MAX;
	float def[4] = {0.0f, 0.0f, 0.0f, 1.0f};

	for (int i = 0; i < 4; i++) {
		if (i < param->ann.totdefault) {
			def[i] = param->ann.def[i];
		}
		else if (param->ann.totdefault == 1 && i < 3) {
			def[i] = param->ann.def[0];
		}
	}

	if (sock->type == SOCK_FLOAT) {
		bNodeSocketValueFloat *dval = sock->default_value;
		dval->min = min;
		dval->max = max;
		if (is_new && choice_default) {
			dval->value = *choice_default;
		}
		else if (is_new && param->ann.totdefault) {
			dval->value = def[0];
		}
		CLAMP(dval->value, min, max);
	}
	else if (sock->type == SOCK_VECTOR) {
		bNodeSocketValueVector *dval = sock->default_value;
		dval->min = min;
		dval->max = max;
		if (is_new && param->ann.totdefault) {
			copy_v3_v3(dval->value, def);
		}
	}
	else if (sock->type == SOCK_RGBA) {
		bNodeSocketValueRGBA *dval = sock->default_value;
		if (is_new && param->ann.totdefault) {
			copy_v4_v4(dval->value, def);
		}
	}
}

/* Sockets follow the parameters of main; sockets that still match keep their links and values. */
static void node_shader_update_glsl_script(bNodeTree *ntree, bNode *node)
{
	ScriptParam params[SCRIPT_MAX_PARAMS];
	char *code = NULL;
	HeaderInfo info;
	bool header = false;
	/* The code stays alive: params[].choice points into it. */
	int tot = script_read_ex(node, params, &code, &info, &header);
	if (header && tot >= 0 && info.name[0] && !node->label[0]) {
		BLI_strncpy(node->label, info.name, sizeof(node->label));
	}
	if (tot < 0) {
		/* No valid main (yet): keep the sockets, the user may be typing. */
		MEM_SAFE_FREE(code);
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
				char choice[BLI_GLSL_CHOICE_BUF];
				float choice_default;
				const bool has_choice = script_choice_build(&params[i], choice, &choice_default);
				script_socket_uniform(sock, &params[i], is_new, has_choice ? &choice_default : NULL);
				script_socket_choice(sock, has_choice ? choice : NULL);
			}
			if (header) {
				/* Header nodes: readable names; UV follows the mesh UV while not linked. */
				script_pretty_name(params[i].name, sock->name, sizeof(sock->name));
				if (STREQ(params[i].name, "UV") && in_out == SOCK_IN) {
					sock->flag |= SOCK_HIDE_VALUE;
				}
			}
			/* Same order as the parameters. */
			BLI_remlink(sockets, sock);
			BLI_addtail(sockets, sock);
		}
	}
	MEM_freeN(code);
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
	bool header = false;
	int tot = script_read_ex(node, params, &code, NULL, &header);
	int ok = 0;

	/* Header nodes: the first input is UV, the mesh UV while not linked. */
	if (header && tot > 0 && in && in[0].type != GPU_NONE && !in[0].link) {
		in[0].link = GPU_attribute(CD_MTFACE, "");
	}

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
