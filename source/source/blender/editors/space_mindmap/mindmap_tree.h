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

/** \file blender/editors/space_mindmap/mindmap_tree.h
 *  \ingroup spmindmap
 *
 * In-memory FreeMind (.mm) document. Attribute values and text keep their
 * original XML escaping, so anything the editor does not touch is written back
 * unchanged.
 */

#ifndef __MINDMAP_TREE_H__
#define __MINDMAP_TREE_H__

#include <stddef.h>

typedef struct MMAttr {
	struct MMAttr *next;
	char *name;
	char *value;  /* escaped, as stored in XML */
} MMAttr;

typedef struct MMElem {
	struct MMElem *next, *prev, *parent;
	struct MMElem *first, *last;
	char *tag;    /* NULL for raw content (text, comment, CDATA) */
	char *raw;
	MMAttr *attr_first, *attr_last;
} MMElem;

typedef struct MMDoc {
	MMElem top;   /* holds the <map> element */
} MMDoc;

/* Returns NULL and fills err on invalid input. buf need not be NUL terminated. */
MMDoc *mm_parse(const char *buf, size_t len, char *err, size_t err_size);
void mm_free(MMDoc *doc);

/* Returns a NUL terminated buffer, release with mm_str_free. */
char *mm_write(const MMDoc *doc, size_t *r_len);
void mm_str_free(char *str);

MMDoc *mm_new(const char *root_text);

MMElem *mm_root_node(const MMDoc *doc);
MMElem *mm_node_first_child(const MMElem *node);
MMElem *mm_node_next(const MMElem *node);

/* Decoded UTF-8 value, or NULL when absent. Release with mm_str_free. */
char *mm_attr_get(const MMElem *elem, const char *name);
void mm_attr_set(MMElem *elem, const char *name, const char *value);
void mm_attr_remove(MMElem *elem, const char *name);

char *mm_node_text(const MMElem *node);
void mm_node_text_set(MMElem *node, const char *text);
int mm_node_folded(const MMElem *node);
void mm_node_folded_set(MMElem *node, int folded);

/* New child is added after the last child node, before other sub-elements' end. */
MMElem *mm_node_add_child(MMElem *parent, const char *text);
/* New sibling right after node. Returns NULL for the root node. */
MMElem *mm_node_add_sibling(MMElem *node, const char *text);
/* Removes node and its branch. The root node cannot be removed (returns 0). */
int mm_node_remove(MMElem *node);

#endif  /* __MINDMAP_TREE_H__ */
