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
 */

/** \file blender/editors/space_mindmap/mindmap_tree.c
 *  \ingroup spmindmap
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "mindmap_tree.h"

#ifdef MM_STANDALONE_TEST
#  define MM_CALLOC(size) calloc(1, size)
#  define MM_FREE(ptr) free(ptr)
#else
#  include "MEM_guardedalloc.h"
#  define MM_CALLOC(size) MEM_callocN(size, "mindmap")
#  define MM_FREE(ptr) MEM_freeN(ptr)
#endif

/* Recursion in write and free is bounded by this. */
#define MM_MAX_DEPTH 512

/* ---------------- strings ---------------- */

static char *mm_strndup(const char *str, size_t len)
{
	char *dst = MM_CALLOC(len + 1);
	memcpy(dst, str, len);
	return dst;
}

static char *mm_strdup(const char *str)
{
	return mm_strndup(str, strlen(str));
}

void mm_str_free(char *str)
{
	if (str) {
		MM_FREE(str);
	}
}

static const char *mm_find(const char *p, const char *end, const char *needle)
{
	const size_t n = strlen(needle);
	for (; (size_t)(end - p) >= n; p++) {
		if (memcmp(p, needle, n) == 0) {
			return p;
		}
	}
	return NULL;
}

static int mm_is_space(char c)
{
	return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

static int mm_utf8_put(char *dst, unsigned long c)
{
	if (c < 0x80) {
		dst[0] = (char)c;
		return 1;
	}
	if (c < 0x800) {
		dst[0] = (char)(0xC0 | (c >> 6));
		dst[1] = (char)(0x80 | (c & 0x3F));
		return 2;
	}
	if (c < 0x10000) {
		dst[0] = (char)(0xE0 | (c >> 12));
		dst[1] = (char)(0x80 | ((c >> 6) & 0x3F));
		dst[2] = (char)(0x80 | (c & 0x3F));
		return 3;
	}
	dst[0] = (char)(0xF0 | (c >> 18));
	dst[1] = (char)(0x80 | ((c >> 12) & 0x3F));
	dst[2] = (char)(0x80 | ((c >> 6) & 0x3F));
	dst[3] = (char)(0x80 | (c & 0x3F));
	return 4;
}

/* A character reference is never longer than its UTF-8 result needs, except
 * for very short ones like &#1; which still produce fewer bytes. */
static char *mm_unescape(const char *src)
{
	static const struct {
		const char *name;
		char c;
	} named[] = {{"&amp;", '&'}, {"&lt;", '<'}, {"&gt;", '>'}, {"&quot;", '"'}, {"&apos;", '\''}};
	char *out = MM_CALLOC(strlen(src) + 1);
	char *d = out;
	const char *p = src;

	while (*p) {
		int done = 0;
		if (*p == '&') {
			size_t i;
			for (i = 0; i < sizeof(named) / sizeof(named[0]); i++) {
				const size_t n = strlen(named[i].name);
				if (strncmp(p, named[i].name, n) == 0) {
					*d++ = named[i].c;
					p += n;
					done = 1;
					break;
				}
			}
			if (!done && p[1] == '#') {
				const int hex = (p[2] == 'x' || p[2] == 'X');
				char *stop;
				const char *digits = p + (hex ? 3 : 2);
				const unsigned long c = strtoul(digits, &stop, hex ? 16 : 10);
				const int invalid = (c == 0 || c > 0x10FFFF || (c >= 0xD800 && c <= 0xDFFF));
				if (stop != digits && *stop == ';' && !invalid) {
					d += mm_utf8_put(d, c);
					p = stop + 1;
					done = 1;
				}
			}
		}
		if (!done) {
			*d++ = *p++;
		}
	}
	return out;
}

static char *mm_escape(const char *src)
{
	char *out = MM_CALLOC(strlen(src) * 6 + 1);
	char *d = out;
	const char *p;

	for (p = src; *p; p++) {
		const char *rep = NULL;
		switch (*p) {
			case '&': rep = "&amp;"; break;
			case '<': rep = "&lt;"; break;
			case '>': rep = "&gt;"; break;
			case '"': rep = "&quot;"; break;
			case '\n': rep = "&#xa;"; break;
			default: break;
		}
		if (rep) {
			const size_t n = strlen(rep);
			memcpy(d, rep, n);
			d += n;
		}
		else {
			*d++ = *p;
		}
	}
	return out;
}

/* ---------------- tree ---------------- */

static MMElem *mm_elem_new(const char *tag, size_t tag_len)
{
	MMElem *e = MM_CALLOC(sizeof(MMElem));
	e->tag = mm_strndup(tag, tag_len);
	return e;
}

static void mm_elem_append(MMElem *parent, MMElem *e)
{
	e->parent = parent;
	e->prev = parent->last;
	if (parent->last) {
		parent->last->next = e;
	}
	else {
		parent->first = e;
	}
	parent->last = e;
}

static void mm_elem_insert_after(MMElem *after, MMElem *e)
{
	MMElem *parent = after->parent;
	e->parent = parent;
	e->prev = after;
	e->next = after->next;
	if (after->next) {
		after->next->prev = e;
	}
	else {
		parent->last = e;
	}
	after->next = e;
}

static void mm_elem_unlink(MMElem *e)
{
	MMElem *parent = e->parent;
	if (e->prev) {
		e->prev->next = e->next;
	}
	else {
		parent->first = e->next;
	}
	if (e->next) {
		e->next->prev = e->prev;
	}
	else {
		parent->last = e->prev;
	}
}

static void mm_attr_add_owned(MMElem *e, char *name, char *value)
{
	MMAttr *a = MM_CALLOC(sizeof(MMAttr));
	a->name = name;
	a->value = value;
	if (e->attr_last) {
		e->attr_last->next = a;
	}
	else {
		e->attr_first = a;
	}
	e->attr_last = a;
}

static void mm_elem_clear(MMElem *e)
{
	MMElem *c = e->first;
	MMAttr *a = e->attr_first;

	while (c) {
		MMElem *next = c->next;
		mm_elem_clear(c);
		MM_FREE(c);
		c = next;
	}
	while (a) {
		MMAttr *next = a->next;
		MM_FREE(a->name);
		MM_FREE(a->value);
		MM_FREE(a);
		a = next;
	}
	mm_str_free(e->tag);
	mm_str_free(e->raw);
}

void mm_free(MMDoc *doc)
{
	if (doc) {
		mm_elem_clear(&doc->top);
		MM_FREE(doc);
	}
}

static int mm_is_tag(const MMElem *e, const char *tag)
{
	return e->tag && strcmp(e->tag, tag) == 0;
}

static MMElem *mm_first_node_from(MMElem *e)
{
	for (; e; e = e->next) {
		if (mm_is_tag(e, "node")) {
			return e;
		}
	}
	return NULL;
}

MMElem *mm_root_node(const MMDoc *doc)
{
	const MMElem *map = doc->top.first;
	return map ? mm_first_node_from(map->first) : NULL;
}

MMElem *mm_node_first_child(const MMElem *node)
{
	return mm_first_node_from(node->first);
}

MMElem *mm_node_next(const MMElem *node)
{
	return mm_first_node_from(node->next);
}

static MMAttr *mm_attr_find(const MMElem *e, const char *name)
{
	MMAttr *a;
	for (a = e->attr_first; a; a = a->next) {
		if (strcmp(a->name, name) == 0) {
			return a;
		}
	}
	return NULL;
}

char *mm_attr_get(const MMElem *elem, const char *name)
{
	const MMAttr *a = mm_attr_find(elem, name);
	return a ? mm_unescape(a->value) : NULL;
}

void mm_attr_set(MMElem *elem, const char *name, const char *value)
{
	MMAttr *a = mm_attr_find(elem, name);
	char *escaped = mm_escape(value);

	if (a) {
		MM_FREE(a->value);
		a->value = escaped;
	}
	else {
		mm_attr_add_owned(elem, mm_strdup(name), escaped);
	}
}

void mm_attr_remove(MMElem *elem, const char *name)
{
	MMAttr *a, *prev = NULL;

	for (a = elem->attr_first; a; prev = a, a = a->next) {
		if (strcmp(a->name, name) == 0) {
			if (prev) {
				prev->next = a->next;
			}
			else {
				elem->attr_first = a->next;
			}
			if (elem->attr_last == a) {
				elem->attr_last = prev;
			}
			MM_FREE(a->name);
			MM_FREE(a->value);
			MM_FREE(a);
			return;
		}
	}
}

char *mm_node_text(const MMElem *node)
{
	return mm_attr_get(node, "TEXT");
}

void mm_node_text_set(MMElem *node, const char *text)
{
	mm_attr_set(node, "TEXT", text);
}

int mm_node_folded(const MMElem *node)
{
	const MMAttr *a = mm_attr_find(node, "FOLDED");
	return a && strcmp(a->value, "true") == 0;
}

void mm_node_folded_set(MMElem *node, int folded)
{
	if (folded) {
		mm_attr_set(node, "FOLDED", "true");
	}
	else {
		mm_attr_remove(node, "FOLDED");
	}
}

static MMElem *mm_node_new(const char *text)
{
	MMElem *e = mm_elem_new("node", 4);
	mm_node_text_set(e, text);
	return e;
}

MMDoc *mm_new(const char *root_text)
{
	MMDoc *doc = MM_CALLOC(sizeof(MMDoc));
	MMElem *map = mm_elem_new("map", 3);

	mm_attr_set(map, "version", "1.0.1");
	mm_elem_append(&doc->top, map);
	mm_elem_append(map, mm_node_new(root_text));
	return doc;
}

MMElem *mm_node_add_child(MMElem *parent, const char *text)
{
	MMElem *e = mm_node_new(text);
	mm_elem_append(parent, e);
	return e;
}

MMElem *mm_node_add_sibling(MMElem *node, const char *text)
{
	MMElem *e;

	if (!mm_is_tag(node->parent, "node")) {
		return NULL;
	}
	e = mm_node_new(text);
	mm_elem_insert_after(node, e);
	return e;
}

static MMElem *mm_elem_clone(const MMElem *src)
{
	MMElem *e = MM_CALLOC(sizeof(MMElem));
	const MMAttr *a;
	const MMElem *c;

	e->tag = src->tag ? mm_strdup(src->tag) : NULL;
	e->raw = src->raw ? mm_strdup(src->raw) : NULL;
	for (a = src->attr_first; a; a = a->next) {
		if (!(mm_is_tag(src, "node") && strcmp(a->name, "ID") == 0)) {
			mm_attr_add_owned(e, mm_strdup(a->name), mm_strdup(a->value));
		}
	}
	for (c = src->first; c; c = c->next) {
		mm_elem_append(e, mm_elem_clone(c));
	}
	return e;
}

MMElem *mm_node_copy_into(const MMElem *node, MMElem *parent)
{
	MMElem *e = mm_elem_clone(node);

	mm_elem_append(parent, e);
	return e;
}

int mm_node_remove(MMElem *node)
{
	if (!mm_is_tag(node->parent, "node")) {
		return 0;
	}
	mm_elem_unlink(node);
	mm_elem_clear(node);
	MM_FREE(node);
	return 1;
}

int mm_node_move(MMElem *node, MMElem *parent, MMElem *before)
{
	const MMElem *e;

	if (!mm_is_tag(node->parent, "node")) {
		return 0;
	}
	for (e = parent; e; e = e->parent) {
		if (e == node) {
			return 0;
		}
	}
	if (before == node) {
		before = mm_node_next(node);
	}

	mm_elem_unlink(node);
	node->next = node->prev = NULL;
	if (before == NULL) {
		mm_elem_append(parent, node);
	}
	else if (before->prev) {
		mm_elem_insert_after(before->prev, node);
	}
	else {
		node->parent = parent;
		node->next = before;
		before->prev = node;
		parent->first = node;
	}
	return 1;
}

static MMElem *mm_child_with_tag(const MMElem *node, const char *tag)
{
	MMElem *e;

	for (e = node->first; e; e = e->next) {
		if (mm_is_tag(e, tag)) {
			return e;
		}
	}
	return NULL;
}

static void mm_elem_delete(MMElem *e)
{
	mm_elem_unlink(e);
	mm_elem_clear(e);
	MM_FREE(e);
}

char *mm_node_icon(const MMElem *node)
{
	const MMElem *icon = mm_child_with_tag(node, "icon");

	return icon ? mm_attr_get(icon, "BUILTIN") : NULL;
}

void mm_node_icon_set(MMElem *node, const char *builtin)
{
	MMElem *icon = mm_child_with_tag(node, "icon");

	if (builtin == NULL) {
		if (icon) {
			mm_elem_delete(icon);
		}
		return;
	}
	if (icon == NULL) {
		icon = mm_elem_new("icon", 4);
		mm_elem_append(node, icon);
	}
	mm_attr_set(icon, "BUILTIN", builtin);
}

static MMElem *mm_note_elem(const MMElem *node)
{
	MMElem *e;

	for (e = node->first; e; e = e->next) {
		if (mm_is_tag(e, "richcontent")) {
			const MMAttr *type = mm_attr_find(e, "TYPE");

			if (type && strcmp(type->value, "NOTE") == 0) {
				return e;
			}
		}
	}
	return NULL;
}

int mm_node_has_note(const MMElem *node)
{
	return mm_note_elem(node) != NULL;
}

static size_t mm_note_collect(const MMElem *e, char *out)
{
	const MMElem *c;
	size_t n = 0;

	for (c = e->first; c; c = c->next) {
		if (c->tag == NULL) {
			if (c->raw && c->raw[0] != '<') {
				const size_t len = strlen(c->raw);

				if (out) {
					memcpy(out + n, c->raw, len);
				}
				n += len;
			}
		}
		else if (!mm_is_tag(c, "head")) {
			n += mm_note_collect(c, out ? out + n : NULL);
			if (out) {
				out[n] = ' ';
			}
			n++;
		}
	}
	return n;
}

char *mm_node_note(const MMElem *node)
{
	const MMElem *note = mm_note_elem(node);
	char *raw, *text, *d;
	const char *p;
	size_t n;

	if (note == NULL) {
		return NULL;
	}
	n = mm_note_collect(note, NULL);
	raw = MM_CALLOC(n + 1);
	mm_note_collect(note, raw);

	/* &nbsp; is not an XML entity, the other ones are decoded after. */
	d = raw;
	for (p = raw; *p;) {
		if (strncmp(p, "&nbsp;", 6) == 0) {
			*d++ = ' ';
			p += 6;
		}
		else if (mm_is_space(*p)) {
			*d++ = ' ';
			p++;
		}
		else {
			*d++ = *p++;
		}
	}
	*d = '\0';

	text = mm_unescape(raw);
	MM_FREE(raw);

	d = text;
	for (p = text; *p; p++) {
		if (*p != ' ' || (d != text && d[-1] != ' ')) {
			*d++ = *p;
		}
	}
	while (d != text && d[-1] == ' ') {
		d--;
	}
	*d = '\0';
	return text;
}

void mm_node_note_set(MMElem *node, const char *text)
{
	MMElem *old = mm_note_elem(node);
	MMElem *rich, *html, *body, *par, *raw;

	if (old) {
		mm_elem_delete(old);
	}
	if (text == NULL || text[0] == '\0') {
		return;
	}
	rich = mm_elem_new("richcontent", 11);
	html = mm_elem_new("html", 4);
	body = mm_elem_new("body", 4);
	par = mm_elem_new("p", 1);
	raw = MM_CALLOC(sizeof(MMElem));
	raw->raw = mm_escape(text);
	mm_attr_set(rich, "TYPE", "NOTE");
	mm_elem_append(par, raw);
	mm_elem_append(body, par);
	mm_elem_append(html, body);
	mm_elem_append(rich, html);
	mm_elem_append(node, rich);
}

/* ---------------- parser ---------------- */

static void mm_error(char *err, size_t err_size, const char *buf, const char *at, const char *msg)
{
	int line = 1;
	const char *p;

	for (p = buf; p < at; p++) {
		if (*p == '\n') {
			line++;
		}
	}
	if (err && err_size) {
		snprintf(err, err_size, "Line %d: %s", line, msg);
	}
}

static const char *mm_skip_space(const char *p, const char *end)
{
	while (p < end && mm_is_space(*p)) {
		p++;
	}
	return p;
}

static const char *mm_name_end(const char *p, const char *end)
{
	while (p < end && !mm_is_space(*p) && *p != '/' && *p != '>' && *p != '=' && *p != '<') {
		p++;
	}
	return p;
}

static int mm_in_richcontent(const MMElem *e)
{
	for (; e; e = e->parent) {
		if (mm_is_tag(e, "richcontent")) {
			return 1;
		}
	}
	return 0;
}

static void mm_add_raw(MMElem *parent, const char *p, size_t len)
{
	MMElem *e = MM_CALLOC(sizeof(MMElem));
	e->raw = mm_strndup(p, len);
	mm_elem_append(parent, e);
}

/* Double quotes inside a single quoted value must survive being rewritten
 * between double quotes. */
static char *mm_attr_value_copy(const char *p, size_t len)
{
	char *out = MM_CALLOC(len * 6 + 1);
	char *d = out;
	size_t i;

	for (i = 0; i < len; i++) {
		if (p[i] == '"') {
			memcpy(d, "&quot;", 6);
			d += 6;
		}
		else {
			*d++ = p[i];
		}
	}
	return out;
}

/* Parses attributes up to the tag end. Returns position after '>' or NULL.
 * *r_closed is set for <tag/>. */
static const char *mm_parse_attrs(
        MMElem *e, const char *p, const char *end, int *r_closed, const char **r_error_at)
{
	for (;;) {
		const char *name, *name_end, *close;
		char quote;

		p = mm_skip_space(p, end);
		*r_error_at = p;
		if (p >= end) {
			return NULL;
		}
		if (*p == '>') {
			*r_closed = 0;
			return p + 1;
		}
		if (*p == '/') {
			if (p + 1 < end && p[1] == '>') {
				*r_closed = 1;
				return p + 2;
			}
			return NULL;
		}
		name = p;
		name_end = mm_name_end(p, end);
		if (name_end == name) {
			return NULL;
		}
		p = mm_skip_space(name_end, end);
		if (p >= end || *p != '=') {
			*r_error_at = p;
			return NULL;
		}
		p = mm_skip_space(p + 1, end);
		*r_error_at = p;
		if (p >= end || (*p != '"' && *p != '\'')) {
			return NULL;
		}
		quote = *p++;
		close = memchr(p, quote, (size_t)(end - p));
		if (close == NULL) {
			return NULL;
		}
		mm_attr_add_owned(
		        e, mm_strndup(name, (size_t)(name_end - name)),
		        mm_attr_value_copy(p, (size_t)(close - p)));
		p = close + 1;
	}
}

MMDoc *mm_parse(const char *buf, size_t len, char *err, size_t err_size)
{
	MMDoc *doc = MM_CALLOC(sizeof(MMDoc));
	MMElem *cur = &doc->top;
	const char *p = buf;
	const char *end = buf + len;
	const char *error_at = buf;
	const char *message = "Invalid XML";
	int depth = 0;

	if (len >= 3 && memcmp(p, "\xEF\xBB\xBF", 3) == 0) {
		p += 3;
	}

	while (p < end) {
		if (*p != '<') {
			const char *lt = memchr(p, '<', (size_t)(end - p));
			const char *text_end = lt ? lt : end;
			int blank = 1;
			const char *q;

			for (q = p; q < text_end; q++) {
				if (!mm_is_space(*q)) {
					blank = 0;
					break;
				}
			}
			if (cur == &doc->top) {
				if (!blank) {
					error_at = p;
					message = "Text outside the map";
					goto fail;
				}
			}
			else if (!blank || mm_in_richcontent(cur)) {
				mm_add_raw(cur, p, (size_t)(text_end - p));
			}
			p = text_end;
		}
		else if ((size_t)(end - p) >= 4 && memcmp(p, "<!--", 4) == 0) {
			const char *close = mm_find(p + 4, end, "-->");
			if (close == NULL) {
				error_at = p;
				message = "Unterminated comment";
				goto fail;
			}
			if (cur != &doc->top) {
				mm_add_raw(cur, p, (size_t)(close + 3 - p));
			}
			p = close + 3;
		}
		else if ((size_t)(end - p) >= 9 && memcmp(p, "<![CDATA[", 9) == 0) {
			const char *close = mm_find(p + 9, end, "]]>");
			if (close == NULL || cur == &doc->top) {
				error_at = p;
				message = "Invalid CDATA section";
				goto fail;
			}
			mm_add_raw(cur, p, (size_t)(close + 3 - p));
			p = close + 3;
		}
		else if ((size_t)(end - p) >= 2 && (p[1] == '?' || p[1] == '!')) {
			const char *close = (p[1] == '?') ? mm_find(p, end, "?>") : mm_find(p, end, ">");
			if (close == NULL) {
				error_at = p;
				message = "Unterminated declaration";
				goto fail;
			}
			p = close + ((p[1] == '?') ? 2 : 1);
		}
		else if ((size_t)(end - p) >= 2 && p[1] == '/') {
			const char *name = p + 2;
			const char *name_end = mm_name_end(name, end);
			const char *q = mm_skip_space(name_end, end);

			if (cur == &doc->top ||
			    strlen(cur->tag) != (size_t)(name_end - name) ||
			    memcmp(cur->tag, name, (size_t)(name_end - name)) != 0 ||
			    q >= end || *q != '>')
			{
				error_at = p;
				message = "Closing tag does not match";
				goto fail;
			}
			cur = cur->parent;
			depth--;
			p = q + 1;
		}
		else {
			const char *name = p + 1;
			const char *name_end = mm_name_end(name, end);
			MMElem *e;
			int closed = 0;
			const char *after;

			error_at = p;
			if (name_end == name) {
				message = "Invalid tag";
				goto fail;
			}
			if (cur == &doc->top && doc->top.first) {
				message = "More than one root element";
				goto fail;
			}
			if (depth >= MM_MAX_DEPTH) {
				message = "Map is nested too deeply";
				goto fail;
			}
			e = mm_elem_new(name, (size_t)(name_end - name));
			mm_elem_append(cur, e);
			after = mm_parse_attrs(e, name_end, end, &closed, &error_at);
			if (after == NULL) {
				message = "Invalid attribute";
				goto fail;
			}
			if (!closed) {
				cur = e;
				depth++;
			}
			p = after;
		}
	}

	error_at = end;
	if (cur != &doc->top) {
		message = "Unexpected end of file";
		goto fail;
	}
	if (doc->top.first == NULL || !mm_is_tag(doc->top.first, "map")) {
		message = "Root element is not <map>";
		goto fail;
	}
	if (mm_root_node(doc) == NULL) {
		message = "Map has no root node";
		goto fail;
	}
	return doc;

fail:
	mm_error(err, err_size, buf, error_at, message);
	mm_free(doc);
	return NULL;
}

/* ---------------- writer ---------------- */

typedef struct MMBuf {
	char *data;
	size_t len, cap;
} MMBuf;

static void mm_buf_add(MMBuf *b, const char *str, size_t n)
{
	if (b->len + n + 1 > b->cap) {
		size_t cap = b->cap ? b->cap : 4096;
		char *data;
		while (b->len + n + 1 > cap) {
			cap *= 2;
		}
		data = MM_CALLOC(cap);
		if (b->data) {
			memcpy(data, b->data, b->len);
			MM_FREE(b->data);
		}
		b->data = data;
		b->cap = cap;
	}
	memcpy(b->data + b->len, str, n);
	b->len += n;
	b->data[b->len] = '\0';
}

static void mm_buf_str(MMBuf *b, const char *str)
{
	mm_buf_add(b, str, strlen(str));
}

static void mm_write_elem(MMBuf *b, const MMElem *e, int indent, int verbatim)
{
	const MMAttr *a;
	const MMElem *c;
	int i, inner_verbatim = verbatim || mm_is_tag(e, "richcontent");

	if (e->tag == NULL) {
		mm_buf_str(b, e->raw);
		return;
	}
	for (c = e->first; c; c = c->next) {
		if (c->tag == NULL) {
			inner_verbatim = 1;
		}
	}

	if (!verbatim) {
		for (i = 0; i < indent; i++) {
			mm_buf_str(b, "  ");
		}
	}
	mm_buf_str(b, "<");
	mm_buf_str(b, e->tag);
	for (a = e->attr_first; a; a = a->next) {
		mm_buf_str(b, " ");
		mm_buf_str(b, a->name);
		mm_buf_str(b, "=\"");
		mm_buf_str(b, a->value);
		mm_buf_str(b, "\"");
	}
	if (e->first == NULL) {
		mm_buf_str(b, "/>");
	}
	else {
		mm_buf_str(b, ">");
		if (!inner_verbatim) {
			mm_buf_str(b, "\n");
		}
		for (c = e->first; c; c = c->next) {
			mm_write_elem(b, c, indent + 1, inner_verbatim);
		}
		if (!inner_verbatim) {
			for (i = 0; i < indent; i++) {
				mm_buf_str(b, "  ");
			}
		}
		mm_buf_str(b, "</");
		mm_buf_str(b, e->tag);
		mm_buf_str(b, ">");
	}
	if (!verbatim) {
		mm_buf_str(b, "\n");
	}
}

char *mm_write(const MMDoc *doc, size_t *r_len)
{
	MMBuf b = {NULL, 0, 0};

	mm_write_elem(&b, doc->top.first, 0, 0);
	if (r_len) {
		*r_len = b.len;
	}
	return b.data;
}
