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

/** \file blender/editors/space_mindmap/mindmap_layout.h
 *  \ingroup spmindmap
 *
 * Positions the visible nodes of a map: root at the origin, branches to the
 * right and to the left. Independent of drawing, text width comes from a callback.
 */

#ifndef __MINDMAP_LAYOUT_H__
#define __MINDMAP_LAYOUT_H__

struct MMDoc;

/* Width of a single line of text, in layout units. */
typedef float (*MMTextWidthFn)(const char *text, void *user_data);

typedef struct MMLayoutNode {
	struct MMElem *elem;
	char *text;                 /* single line, shortened when very long */
	float xmin, xmax, ymin, ymax;
	int parent;                 /* index in MMLayout.nodes, -1 for the root */
	int side;                   /* 1 right, -1 left, 0 root */
	int has_hidden_children;    /* folded with children */
} MMLayoutNode;

typedef struct MMLayout {
	MMLayoutNode *nodes;        /* parents always come before their children */
	int count;
	float xmin, xmax, ymin, ymax;
} MMLayout;

MMLayout *mm_layout_build(const struct MMDoc *doc, MMTextWidthFn width_fn, void *user_data);
void mm_layout_free(MMLayout *layout);

#endif  /* __MINDMAP_LAYOUT_H__ */
