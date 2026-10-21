/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file blender/blenlib/intern/glsl_annotations.c
 *  \ingroup bli
 */

#include <stdlib.h>
#include <string.h>

#include "BLI_utildefines.h"
#include "BLI_string.h"
#include "BLI_glsl_annotations.h"

static bool glsl_ident_char(char c)
{
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_';
}

static const char *glsl_skip_space(const char *p)
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

static const char *glsl_read_ident(const char *p, char *r_ident, int size)
{
	int n = 0;
	while (glsl_ident_char(*p)) {
		if (n < size - 1) {
			r_ident[n++] = *p;
		}
		p++;
	}
	r_ident[n] = '\0';
	return p;
}

void BLI_glsl_annotations_parse(const char *p, GLSLAnnotations *ann)
{
	memset(ann, 0, sizeof(*ann));
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
			p = glsl_read_ident(p + 1, word, sizeof(word));
			if (STREQ(word, "min") || STREQ(word, "max")) {
				const float value = (float)strtod(p, &end);
				if (end != p) {
					if (word[1] == 'i') {
						ann->min = value;
						ann->has_min = true;
					}
					else {
						ann->max = value;
						ann->has_max = true;
					}
					p = end;
				}
			}
			else if (STREQ(word, "default")) {
				ann->totdefault = 0;
				while (ann->totdefault < 4) {
					while (*p == ' ' || *p == '\t' || *p == ',' || *p == '(') {
						p++;
					}
					const float value = (float)strtod(p, &end);
					if (end == p) {
						break;
					}
					ann->def[ann->totdefault++] = value;
					p = end;
				}
			}
			else if (STREQ(word, "object")) {
				ann->object = true;
			}
			else if (STREQ(word, "choice")) {
				const char *start = p;
				while (*p && *p != '\n' && *p != '@') {
					p++;
				}
				if (ann->choice) {
					ann->choicelen = -1;
				}
				else {
					ann->choice = start;
					ann->choicelen = (int)(p - start);
				}
			}
		}
		else {
			p++;
		}
	}
}

static void glsl_trim(const char **r_start, const char **r_end)
{
	while (*r_start < *r_end && (**r_start == ' ' || **r_start == '\t' || **r_start == '\r')) {
		(*r_start)++;
	}
	while (*r_end > *r_start && ((*r_end)[-1] == ' ' || (*r_end)[-1] == '\t' || (*r_end)[-1] == '\r')) {
		(*r_end)--;
	}
}

/* Decimal integer in [-BLI_GLSL_CHOICE_LIMIT, BLI_GLSL_CHOICE_LIMIT], nothing else. */
static bool glsl_choice_value(const char *p, const char *end, int *r_value)
{
	bool negative = false;
	long long value = 0;

	if (p < end && (*p == '-' || *p == '+')) {
		negative = (*p == '-');
		p++;
	}
	if (p == end) {
		return false;
	}
	for (; p < end; p++) {
		if (*p < '0' || *p > '9') {
			return false;
		}
		value = value * 10 + (*p - '0');
		if (value > BLI_GLSL_CHOICE_LIMIT) {
			return false;
		}
	}
	*r_value = (int)(negative ? -value : value);
	return true;
}

bool BLI_glsl_choice_build(const GLSLAnnotations *ann, char r_buf[BLI_GLSL_CHOICE_BUF], float *r_default)
{
	char labels[BLI_GLSL_CHOICE_MAX_ITEMS][BLI_GLSL_CHOICE_MAX_LABEL];
	int values[BLI_GLSL_CHOICE_MAX_ITEMS];
	int tot = 0;

	if (!ann->choice || ann->choicelen <= 0) {
		return false;
	}

	const char *end = ann->choice + ann->choicelen;
	for (const char *p = ann->choice; p <= end; tot++) {
		const char *comma = memchr(p, ',', end - p);
		if (!comma) {
			comma = end;
		}
		const char *eq = memchr(p, '=', comma - p);
		if (!eq || tot == BLI_GLSL_CHOICE_MAX_ITEMS) {
			return false;
		}

		const char *label = p, *label_end = eq;
		glsl_trim(&label, &label_end);
		const int len = (int)(label_end - label);
		if (len == 0 || len >= BLI_GLSL_CHOICE_MAX_LABEL) {
			return false;
		}
		memcpy(labels[tot], label, len);
		labels[tot][len] = '\0';

		const char *value = eq + 1, *value_end = comma;
		glsl_trim(&value, &value_end);
		if (!glsl_choice_value(value, value_end, &values[tot])) {
			return false;
		}

		for (int i = 0; i < tot; i++) {
			if (values[i] == values[tot] || STREQ(labels[i], labels[tot])) {
				return false;
			}
		}
		p = comma + 1;
	}

	float def = (float)values[0];
	if (ann->totdefault) {
		bool found = false;
		for (int i = 0; i < tot; i++) {
			found |= ((float)values[i] == ann->def[0]);
		}
		if (ann->totdefault != 1 || !found) {
			return false;
		}
		def = ann->def[0];
	}

	for (int i = 0; i < tot; i++) {
		if ((ann->has_min && values[i] < ann->min) || (ann->has_max && values[i] > ann->max)) {
			return false;
		}
	}

	r_buf[0] = '\0';
	for (int i = 0; i < tot; i++) {
		const size_t used = strlen(r_buf);
		BLI_snprintf(r_buf + used, BLI_GLSL_CHOICE_BUF - used, "%s%s=%d", i ? "," : "", labels[i], values[i]);
	}
	*r_default = def;
	return true;
}

bool BLI_glsl_choice_next(const char **p, char *r_label, int labelsize, int *r_value)
{
	const char *eq = strchr(*p, '=');
	if (!**p || !eq) {
		return false;
	}
	BLI_strncpy(r_label, *p, MIN2(labelsize, (int)(eq - *p) + 1));
	*r_value = atoi(eq + 1);
	const char *comma = strchr(eq, ',');
	*p = comma ? comma + 1 : eq + strlen(eq);
	return true;
}

int BLI_glsl_uniforms_find(const char *code, GLSLUniform *r_uniforms, int max)
{
	const char *p = code;
	int braces = 0, tot = 0;

	while (*p && tot < max) {
		p = glsl_skip_space(p);
		if (!*p) {
			break;
		}
		if (!glsl_ident_char(*p)) {
			if (*p == '{') braces++;
			else if (*p == '}') braces--;
			p++;
			continue;
		}

		char word[64];
		p = glsl_read_ident(p, word, sizeof(word));
		if (braces != 0 || !STREQ(word, "uniform")) {
			continue;
		}

		GLSLUniform *uni = &r_uniforms[tot];
		const char *q = glsl_skip_space(p);
		q = glsl_read_ident(q, uni->type, sizeof(uni->type));
		/* Precision qualifiers: "uniform highp float x;". */
		if (STREQ(uni->type, "highp") || STREQ(uni->type, "mediump") || STREQ(uni->type, "lowp")) {
			q = glsl_read_ident(glsl_skip_space(q), uni->type, sizeof(uni->type));
		}
		q = glsl_skip_space(q);
		q = glsl_read_ident(q, uni->name, sizeof(uni->name));
		/* A GLSL identifier does not start with a digit. */
		if (!uni->type[0] || !uni->name[0] || (uni->name[0] >= '0' && uni->name[0] <= '9')) {
			continue;
		}
		bool duplicate = false;
		for (int i = 0; i < tot; i++) {
			duplicate |= STREQ(r_uniforms[i].name, uni->name);
		}
		if (duplicate) {
			continue;
		}
		while (*q && *q != ';' && *q != '\n') {
			q++;
		}
		if (*q == ';') {
			BLI_glsl_annotations_parse(q + 1, &uni->ann);
		}
		else {
			memset(&uni->ann, 0, sizeof(uni->ann));
		}
		tot++;
	}
	return tot;
}
