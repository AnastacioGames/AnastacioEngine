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

/** \file blender/editors/space_mindmap/mindmap_layout.c
 *  \ingroup spmindmap
 */

#include <stdlib.h>
#include <string.h>

#include "mindmap_layout.h"
#include "mindmap_tree.h"

#ifdef MM_STANDALONE_TEST
#  define MM_CALLOC(size) calloc(1, size)
#  define MM_FREE(ptr) free(ptr)
#else
#  include "MEM_guardedalloc.h"
#  define MM_CALLOC(size) MEM_callocN(size, "mindmap layout")
#  define MM_FREE(ptr) MEM_freeN(ptr)
#endif

#define NODE_HEIGHT 24.0f
#define NODE_PADDING 10.0f
#define GAP_X 56.0f
#define GAP_Y 8.0f
#define MAX_TEXT_BYTES 80
#define MARK_WIDTH 16.0f

typedef struct LayoutContext {
	MMLayout *layout;
	MMTextWidthFn width_fn;
	void *user_data;
} LayoutContext;

static const MMElem *visible_first_child(const MMElem *node, int is_root)
{
	return (!is_root && mm_node_folded(node)) ? NULL : mm_node_first_child(node);
}

static int count_visible(const MMElem *node, int is_root)
{
	const MMElem *child;
	int count = 1;

	for (child = visible_first_child(node, is_root); child; child = mm_node_next(child)) {
		count += count_visible(child, 0);
	}
	return count;
}

static char *single_line_text(const MMElem *node)
{
	char *text = mm_node_text(node);
	size_t len, i;

	if (text == NULL) {
		/* FreeMind stores formatted ideas in richcontent, without TEXT. */
		text = MM_CALLOC(4);
		memcpy(text, "...", 3);
		return text;
	}
	len = strlen(text);
	for (i = 0; i < len; i++) {
		if (text[i] == '\n' || text[i] == '\r' || text[i] == '\t') {
			text[i] = ' ';
		}
	}
	if (len > MAX_TEXT_BYTES) {
		i = MAX_TEXT_BYTES - 3;
		while (i > 0 && (text[i] & 0xC0) == 0x80) {
			i--;
		}
		memcpy(text + i, "...", 4);
	}
	return text;
}

static char icon_letter(const char *builtin)
{
	static const struct {
		const char *name;
		char letter;
	} icons[] = {
		{"idea", '*'}, {"help", '?'}, {"yes", '!'}, {"messagebox_warning", '!'},
		{"button_ok", 'V'}, {"button_cancel", 'X'}, {"flag", 'F'}, {"info", 'i'},
	};
	size_t i;

	if (builtin) {
		for (i = 0; i < sizeof(icons) / sizeof(icons[0]); i++) {
			if (strcmp(builtin, icons[i].name) == 0) {
				return icons[i].letter;
			}
		}
	}
	return 0;
}

static int hex_digit(char c)
{
	if (c >= '0' && c <= '9') return c - '0';
	if (c >= 'a' && c <= 'f') return c - 'a' + 10;
	if (c >= 'A' && c <= 'F') return c - 'A' + 10;
	return -1;
}

/* Fills what is drawn besides the text and returns the box width. */
static float fill_appearance(LayoutContext *ctx, const MMElem *node, MMLayoutNode *out)
{
	char *value = mm_node_icon(node);
	float marks = 0.0f;

	out->icon = icon_letter(value);
	mm_str_free(value);
	out->has_note = mm_node_has_note(node);
	out->has_children = mm_node_first_child(node) != NULL;
	marks = ((out->icon ? 1 : 0) + (out->has_note ? 1 : 0)) * MARK_WIDTH;
	out->text_offset = marks;

	value = mm_attr_get(node, "COLOR");
	if (value && value[0] == '#' && strlen(value) == 7) {
		int i, valid = 1;

		for (i = 0; i < 3; i++) {
			const int hi = hex_digit(value[1 + i * 2]), lo = hex_digit(value[2 + i * 2]);

			if (hi < 0 || lo < 0) {
				valid = 0;
				break;
			}
			out->color[i] = (unsigned char)(hi * 16 + lo);
		}
		out->has_color = valid;
	}
	mm_str_free(value);

	return ctx->width_fn(out->text, ctx->user_data) + 2.0f * NODE_PADDING + marks;
}

/* Places a node with its branch below y_top and returns the height used. */
static float place_branch(LayoutContext *ctx, const MMElem *node, int parent, int side, float x, float y_top)
{
	MMLayout *layout = ctx->layout;
	const int index = layout->count++;
	MMLayoutNode *out = &layout->nodes[index];
	const MMElem *child;
	float width, child_x, height, y = y_top;
	int first = 1;

	out->elem = (MMElem *)node;
	out->text = single_line_text(node);
	out->parent = parent;
	out->side = side;
	out->has_hidden_children = mm_node_folded(node) && mm_node_first_child(node);

	width = fill_appearance(ctx, node, out);
	out->xmin = (side > 0) ? x : x - width;
	out->xmax = out->xmin + width;
	child_x = (side > 0) ? out->xmax + GAP_X : out->xmin - GAP_X;

	for (child = visible_first_child(node, 0); child; child = mm_node_next(child)) {
		if (!first) {
			y -= GAP_Y;
		}
		first = 0;
		y -= place_branch(ctx, child, index, side, child_x, y);
	}

	height = y_top - y;
	if (height < NODE_HEIGHT) {
		height = NODE_HEIGHT;
	}
	out->ymax = y_top - (height - NODE_HEIGHT) * 0.5f;
	out->ymin = out->ymax - NODE_HEIGHT;
	return height;
}

static void place_side(LayoutContext *ctx, const MMElem *root, int side, float x)
{
	MMLayout *layout = ctx->layout;
	const MMElem *child;
	const int start = layout->count;
	float y = 0.0f, offset;
	int first = 1, i;

	for (child = mm_node_first_child(root); child; child = mm_node_next(child)) {
		char *position = mm_attr_get(child, "POSITION");
		const int child_side = (position && strcmp(position, "left") == 0) ? -1 : 1;

		mm_str_free(position);
		if (child_side == side) {
			if (!first) {
				y -= GAP_Y;
			}
			first = 0;
			y -= place_branch(ctx, child, 0, side, x, y);
		}
	}

	offset = -y * 0.5f;
	for (i = start; i < layout->count; i++) {
		layout->nodes[i].ymin += offset;
		layout->nodes[i].ymax += offset;
	}
}

MMLayout *mm_layout_build(const MMDoc *doc, MMTextWidthFn width_fn, void *user_data)
{
	const MMElem *root = mm_root_node(doc);
	MMLayout *layout;
	MMLayoutNode *out;
	LayoutContext ctx;
	float width;
	int i;

	if (root == NULL) {
		return NULL;
	}

	layout = MM_CALLOC(sizeof(*layout));
	layout->nodes = MM_CALLOC(sizeof(*layout->nodes) * count_visible(root, 1));
	ctx.layout = layout;
	ctx.width_fn = width_fn;
	ctx.user_data = user_data;

	out = &layout->nodes[layout->count++];
	out->elem = (MMElem *)root;
	out->text = single_line_text(root);
	out->parent = -1;
	width = fill_appearance(&ctx, root, out);
	out->xmin = -width * 0.5f;
	out->xmax = width * 0.5f;
	out->ymin = -NODE_HEIGHT * 0.5f;
	out->ymax = NODE_HEIGHT * 0.5f;

	place_side(&ctx, root, 1, out->xmax + GAP_X);
	place_side(&ctx, root, -1, out->xmin - GAP_X);

	layout->xmin = out->xmin;
	layout->xmax = out->xmax;
	layout->ymin = out->ymin;
	layout->ymax = out->ymax;
	for (i = 1; i < layout->count; i++) {
		const MMLayoutNode *node = &layout->nodes[i];

		if (node->xmin < layout->xmin) layout->xmin = node->xmin;
		if (node->xmax > layout->xmax) layout->xmax = node->xmax;
		if (node->ymin < layout->ymin) layout->ymin = node->ymin;
		if (node->ymax > layout->ymax) layout->ymax = node->ymax;
	}
	return layout;
}

void mm_layout_free(MMLayout *layout)
{
	int i;

	if (layout == NULL) {
		return;
	}
	for (i = 0; i < layout->count; i++) {
		mm_str_free(layout->nodes[i].text);
	}
	MM_FREE(layout->nodes);
	MM_FREE(layout);
}
