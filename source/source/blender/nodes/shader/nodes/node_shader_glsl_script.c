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
 * "Vertex Offset"). Other functions, constants and uniforms may be written next to main.
 */

#include "node_shader_util.h"

#include "BLI_dynstr.h"

#include "BKE_text.h"

#include "DNA_text_types.h"

#define SCRIPT_MAX_PARAMS 32

typedef struct ScriptParam {
	char glsltype[16];
	char name[64];
	bool output;
	int socktype;
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

static int script_read(bNode *node, ScriptParam *params, char **r_code)
{
	Text *text = (Text *)node->id;
	char *code = text ? txt_to_buf(text) : NULL;
	int tot = code ? script_parse(code, params) : -1;
	if (r_code) {
		*r_code = code;
	}
	else if (code) {
		MEM_freeN(code);
	}
	return tot;
}

static bNodeSocket *script_find_socket(ListBase *sockets, const ScriptParam *param)
{
	for (bNodeSocket *sock = sockets->first; sock; sock = sock->next) {
		if (STREQ(sock->identifier, param->name) && sock->type == param->socktype) {
			return sock;
		}
	}
	return NULL;
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
				if (params[i].output == (in_out == SOCK_OUT) && STREQ(sock->identifier, params[i].name) &&
				    sock->type == params[i].socktype)
				{
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
			if (!sock) {
				sock = nodeAddStaticSocket(ntree, node, in_out, params[i].socktype, PROP_NONE,
				                           params[i].name, params[i].name);
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

/* SCRIPT_ENTRY(inputs..., outputs...) calls SCRIPT_MAIN with the parameters in the user order and
 * converts int/vec2 from and to the socket types. */
static char *script_wrapper(const ScriptParam *params, int tot)
{
	DynStr *ds = BLI_dynstr_new();
	bool first = true;

	BLI_dynstr_append(ds, "void SCRIPT_ENTRY(");
	for (int pass = 0; pass < 2; pass++) {
		for (int i = 0; i < tot; i++) {
			if (params[i].output != (pass == 1)) {
				continue;
			}
			BLI_dynstr_appendf(ds, "%s%s%s p%d", first ? "" : ", ", pass ? "out " : "",
			                   script_socket_glsl(params[i].socktype), i);
			first = false;
		}
	}
	BLI_dynstr_append(ds, ")\n{\n");

	for (int i = 0; i < tot; i++) {
		if (params[i].output && (STREQ(params[i].glsltype, "int") || STREQ(params[i].glsltype, "vec2"))) {
			BLI_dynstr_appendf(ds, "\t%s t%d;\n", params[i].glsltype, i);
		}
	}

	BLI_dynstr_append(ds, "\tSCRIPT_MAIN(");
	for (int i = 0; i < tot; i++) {
		const char *type = params[i].glsltype;
		const char *sep = i ? ", " : "";
		if (params[i].output) {
			if (STREQ(type, "int") || STREQ(type, "vec2"))
				BLI_dynstr_appendf(ds, "%st%d", sep, i);
			else
				BLI_dynstr_appendf(ds, "%sp%d", sep, i);
		}
		else {
			if (STREQ(type, "int"))
				BLI_dynstr_appendf(ds, "%sint(p%d)", sep, i);
			else if (STREQ(type, "vec2"))
				BLI_dynstr_appendf(ds, "%sp%d.xy", sep, i);
			else
				BLI_dynstr_appendf(ds, "%sp%d", sep, i);
		}
	}
	BLI_dynstr_append(ds, ");\n");

	for (int i = 0; i < tot; i++) {
		if (params[i].output) {
			if (STREQ(params[i].glsltype, "int"))
				BLI_dynstr_appendf(ds, "\tp%d = float(t%d);\n", i, i);
			else if (STREQ(params[i].glsltype, "vec2"))
				BLI_dynstr_appendf(ds, "\tp%d = vec3(t%d, 0.0);\n", i, i);
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
		char *wrapper = script_wrapper(params, tot);
		ok = GPU_link_script(mat, code, wrapper, in, out);
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
