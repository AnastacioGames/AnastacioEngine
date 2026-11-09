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

enum { MM_TASK_NONE, MM_TASK_TODO, MM_TASK_DONE };

#define MM_ATTR_TASK "ANASTACIO_TASK"
#define MM_ATTR_LINK "ANASTACIO_LINK"
#define MM_ATTR_ICON "ANASTACIO_ICON"
#define MM_ATTR_LINK_ID "ANASTACIO_LINK_ID"

typedef struct MMLayoutNode {
	struct MMElem *elem;
	char *text;                 /* single line, shortened when very long */
	float xmin, xmax, ymin, ymax;
	int parent;                 /* index in MMLayout.nodes, -1 for the root */
	int side;                   /* 1 right, -1 left, 0 root */
	int has_hidden_children;    /* folded with children */
	int has_children;
	int has_note;
	char icon;                  /* letter standing for a known icon, 0 when none */
	char engine_icon[64];       /* name of an engine icon, wins over icon */
	int has_color;
	unsigned char color[3];
	float text_offset;          /* width used by the marks at the left of the text */
	float text_right;           /* width used by the marks at the right of the text */
	int task;                   /* MM_TASK_NONE, MM_TASK_TODO or MM_TASK_DONE */
	int has_link;
	int marked;
	char progress[32];          /* "done/total" of the tasks below, empty when none */
} MMLayoutNode;

typedef struct MMLayout {
	MMLayoutNode *nodes;        /* parents always come before their children */
	int count;
	float xmin, xmax, ymin, ymax;
} MMLayout;

int mm_node_task(const struct MMElem *node);
MMLayout *mm_layout_build(const struct MMDoc *doc, MMTextWidthFn width_fn, void *user_data);
void mm_layout_free(MMLayout *layout);

#endif  /* __MINDMAP_LAYOUT_H__ */
