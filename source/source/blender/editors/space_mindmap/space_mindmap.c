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

/** \file blender/editors/space_mindmap/space_mindmap.c
 *  \ingroup spmindmap
 *
 * Mind Map editor. See docs/plano-mind-map.md.
 */

#include <float.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

#include "MEM_guardedalloc.h"

#include "BLI_blenlib.h"
#include "BLI_math_base.h"
#include "BLI_math_vector.h"
#include "BLI_rect.h"
#include "BLI_utildefines.h"

#include "DNA_ID.h"
#include "DNA_object_types.h"
#include "DNA_scene_types.h"
#include "DNA_screen_types.h"
#include "DNA_space_types.h"
#include "DNA_text_types.h"
#include "DNA_userdef_types.h"
#include "DNA_windowmanager_types.h"

#include "BKE_context.h"
#include "BKE_idprop.h"
#include "BKE_main.h"
#include "BKE_report.h"
#include "BKE_scene.h"
#include "BKE_screen.h"
#include "BKE_text.h"

#include "BLF_api.h"

#include "ED_screen.h"
#include "ED_space_api.h"
#include "ED_undo.h"

#include "BIF_gl.h"
#include "BIF_glutil.h"

#include "GPU_framebuffer.h"

#include "IMB_imbuf.h"
#include "IMB_imbuf_types.h"

#include "RNA_access.h"
#include "RNA_define.h"
#include "RNA_enum_types.h"

#include "WM_api.h"
#include "WM_keymap.h"
#include "WM_types.h"

#include "UI_interface.h"
#include "UI_interface_icons.h"
#include "UI_resources.h"
#include "UI_view2d.h"

#include "mindmap_layout.h"
#include "mindmap_tree.h"

#define TEXT_POINTS 12.0f
#define TEXT_MIN_PIXELS 5
#define CURVE_SEGMENTS 12
#define FOLD_MARK_SIZE 5.0f
#define FIT_MARGIN 40.0f
#define MIN_ZOOM 0.005f
#define EDIT_MIN_WIDTH 160.0f
#define EDIT_BUFFER_SIZE 4096
#define PATH_MAX_DEPTH 520
#define REVEAL_MARGIN 30.0f

/* Parsed state of a map. The Text is the source of truth and is compared on every
 * redraw, which covers undo, file reload and edits made in the Text Editor. */
typedef struct MindMapCache {
	struct MindMapCache *next, *prev;
	const SpaceMindMap *smm;
	char text_name[MAX_ID_NAME];
	char *buffer;
	MMDoc *doc;
	MMLayout *layout;
	MMElem *selected;
	char error[128];
	bool fit_view;
	bool reveal;

	bool editing;
	bool editing_new;
	MMElem *edit_previous;  /* selected again when a new idea is cancelled */
	char edit_buffer[EDIT_BUFFER_SIZE];

	MMElem *drag_node;      /* set while a mouse press may become a drag */
	bool dragging;
	int drag_start[2];
	float drag_delta[2];    /* distance moved by the mouse, in view units */
	char find_text[256];
	const MMElem *drop_target;
	int drop_zone;
	int drop_side;
} MindMapCache;

enum { DROP_CHILD, DROP_BEFORE, DROP_AFTER };

static ListBase mindmap_caches = {NULL, NULL};

static int mindmap_font_id(void)
{
	return UI_style_get()->widget.uifont_id;
}

static float mindmap_text_width(const char *text, void *UNUSED(user_data))
{
	const int font = mindmap_font_id();

	BLF_size(font, (int)TEXT_POINTS, 72);
	return BLF_width(font, text, BLF_DRAW_STR_DUMMY_MAX);
}

static void mindmap_cache_clear_contents(MindMapCache *cache)
{
	if (cache->buffer) {
		MEM_freeN(cache->buffer);
		cache->buffer = NULL;
	}
	mm_layout_free(cache->layout);
	cache->layout = NULL;
	mm_free(cache->doc);
	cache->doc = NULL;
	cache->selected = NULL;
	cache->editing = false;
	cache->drag_node = NULL;
	cache->drop_target = NULL;
	cache->error[0] = '\0';
}

static int mindmap_layout_find(const MMLayout *layout, const MMElem *elem)
{
	int i;

	for (i = 0; i < layout->count; i++) {
		if (layout->nodes[i].elem == elem) {
			return i;
		}
	}
	return -1;
}

/* The layout has to exist. Selection hidden by a folded parent moves to that parent. */
static void mindmap_cache_rebuild_layout(MindMapCache *cache)
{
	MMElem *root = mm_root_node(cache->doc);

	mm_layout_free(cache->layout);
	cache->layout = mm_layout_build(cache->doc, mindmap_text_width, NULL);

	if (cache->selected == NULL) {
		cache->selected = root;
	}
	while (cache->selected != root && mindmap_layout_find(cache->layout, cache->selected) == -1) {
		cache->selected = cache->selected->parent;
	}
}

static void mindmap_cache_parse(MindMapCache *cache)
{
	const char *c = cache->buffer;

	while (*c == ' ' || *c == '\t' || *c == '\r' || *c == '\n') {
		c++;
	}
	if (*c == '\0') {
		BLI_strncpy(cache->error, "The text is empty", sizeof(cache->error));
		return;
	}

	cache->doc = mm_parse(cache->buffer, strlen(cache->buffer), cache->error, sizeof(cache->error));
	if (cache->doc) {
		mindmap_cache_rebuild_layout(cache);
	}
}

static int mindmap_selection_path(const MindMapCache *cache, int path[PATH_MAX_DEPTH])
{
	const MMElem *root, *node;
	int len = 0;

	if (cache->doc == NULL || cache->selected == NULL) {
		return 0;
	}
	root = mm_root_node(cache->doc);
	for (node = cache->selected; node != root && len < PATH_MAX_DEPTH; node = node->parent) {
		const MMElem *sibling = mm_node_first_child(node->parent);
		int index = 0;

		while (sibling != node) {
			sibling = mm_node_next(sibling);
			index++;
		}
		path[len++] = index;
	}
	return len;
}

/* Finds the same place in a new document, or the closest one that still exists. */
static MMElem *mindmap_selection_from_path(const MMDoc *doc, const int path[PATH_MAX_DEPTH], int len)
{
	MMElem *node = mm_root_node(doc);

	while (len-- > 0) {
		MMElem *child = mm_node_first_child(node);
		int index = path[len];

		if (child == NULL) {
			break;
		}
		while (index-- > 0 && mm_node_next(child)) {
			child = mm_node_next(child);
		}
		node = child;
	}
	return node;
}

static MindMapCache *mindmap_cache_get(const SpaceMindMap *smm)
{
	MindMapCache *cache = BLI_findptr(&mindmap_caches, smm, offsetof(MindMapCache, smm));
	const char *name = smm->text ? smm->text->id.name : "";
	int path[PATH_MAX_DEPTH];
	int path_len;
	char *buffer;

	if (cache == NULL) {
		cache = MEM_callocN(sizeof(*cache), "MindMapCache");
		cache->smm = smm;
		BLI_addtail(&mindmap_caches, cache);
	}

	/* Compared by name, undo may give the same Text a new pointer. */
	if (!STREQ(cache->text_name, name)) {
		BLI_strncpy(cache->text_name, name, sizeof(cache->text_name));
		cache->fit_view = true;
		mindmap_cache_clear_contents(cache);
	}
	if (smm->text == NULL) {
		return cache;
	}

	buffer = txt_to_buf(smm->text);
	if (buffer == NULL) {
		buffer = MEM_callocN(1, "MindMap empty text");
	}
	if (cache->buffer && STREQ(cache->buffer, buffer)) {
		MEM_freeN(buffer);
		return cache;
	}

	path_len = mindmap_selection_path(cache, path);
	mindmap_cache_clear_contents(cache);
	cache->buffer = buffer;
	mindmap_cache_parse(cache);
	if (cache->doc) {
		cache->selected = mindmap_selection_from_path(cache->doc, path, path_len);
		mindmap_cache_rebuild_layout(cache);
	}
	return cache;
}

/* Writes the edited document to the Text, which stays the source of truth. */
static void mindmap_cache_commit(MindMapCache *cache)
{
	Text *text = cache->smm->text;
	char *out = mm_write(cache->doc, NULL);

	BKE_text_clear(text, NULL);
	BKE_text_write(text, NULL, out);
	mm_str_free(out);

	if (cache->buffer) {
		MEM_freeN(cache->buffer);
	}
	cache->buffer = txt_to_buf(text);
	if (cache->buffer == NULL) {
		cache->buffer = MEM_callocN(1, "MindMap empty text");
	}
	mindmap_cache_rebuild_layout(cache);
	cache->reveal = true;
}

static void mindmap_edit_cancel_new(MindMapCache *cache)
{
	MMElem *node = cache->selected;

	cache->selected = cache->edit_previous;
	mm_node_remove(node);
	mindmap_cache_commit(cache);
}

static void mindmap_view_fit(ARegion *ar, const MMLayout *layout)
{
	View2D *v2d = &ar->v2d;

	BLI_rctf_init(&v2d->cur,
	              layout->xmin - FIT_MARGIN, layout->xmax + FIT_MARGIN,
	              layout->ymin - FIT_MARGIN, layout->ymax + FIT_MARGIN);
	UI_view2d_curRect_validate(v2d);
}

static void mindmap_view_reveal(ARegion *ar, const MindMapCache *cache)
{
	const int index = mindmap_layout_find(cache->layout, cache->selected);
	rctf *cur = &ar->v2d.cur;
	float dx = 0.0f, dy = 0.0f;

	if (index != -1) {
		const MMLayoutNode *node = &cache->layout->nodes[index];

		if (node->xmin - REVEAL_MARGIN < cur->xmin) dx = node->xmin - REVEAL_MARGIN - cur->xmin;
		else if (node->xmax + REVEAL_MARGIN > cur->xmax) dx = node->xmax + REVEAL_MARGIN - cur->xmax;
		if (node->ymin - REVEAL_MARGIN < cur->ymin) dy = node->ymin - REVEAL_MARGIN - cur->ymin;
		else if (node->ymax + REVEAL_MARGIN > cur->ymax) dy = node->ymax + REVEAL_MARGIN - cur->ymax;
		BLI_rctf_translate(cur, dx, dy);
	}
}

static bool mindmap_rect_visible(const rctf *cur, float xmin, float xmax, float ymin, float ymax)
{
	return xmin <= cur->xmax && xmax >= cur->xmin && ymin <= cur->ymax && ymax >= cur->ymin;
}

static void mindmap_draw_links(const MMLayout *layout, const rctf *cur)
{
	int i, j;

	UI_ThemeColorShade(TH_TEXT, -40);
	for (i = 1; i < layout->count; i++) {
		const MMLayoutNode *node = &layout->nodes[i];
		const MMLayoutNode *parent = &layout->nodes[node->parent];
		const float x0 = (node->side > 0) ? parent->xmax : parent->xmin;
		const float x1 = (node->side > 0) ? node->xmin : node->xmax;
		const float y0 = (parent->ymin + parent->ymax) * 0.5f;
		const float y1 = (node->ymin + node->ymax) * 0.5f;

		if (!mindmap_rect_visible(cur, min_ff(x0, x1), max_ff(x0, x1), min_ff(y0, y1), max_ff(y0, y1))) {
			continue;
		}

		glBegin(GL_LINE_STRIP);
		for (j = 0; j <= CURVE_SEGMENTS; j++) {
			const float t = (float)j / CURVE_SEGMENTS;

			glVertex2f(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t * t * (3.0f - 2.0f * t));
		}
		glEnd();
	}
}

static void mindmap_draw_boxes(const MMLayout *layout, const rctf *cur, const MMElem *selected)
{
	int i;

	for (i = 0; i < layout->count; i++) {
		const MMLayoutNode *node = &layout->nodes[i];

		if (!mindmap_rect_visible(cur, node->xmin - FOLD_MARK_SIZE * 2.0f, node->xmax + FOLD_MARK_SIZE * 2.0f,
		                          node->ymin, node->ymax))
		{
			continue;
		}

		UI_ThemeColorShade(TH_BACK, i == 0 ? -60 : -30);
		glRectf(node->xmin, node->ymin, node->xmax, node->ymax);
		if (node->elem == selected) {
			UI_ThemeColor(TH_TEXT_HI);
			glLineWidth(2.0f);
			fdrawbox(node->xmin, node->ymin, node->xmax, node->ymax);
			glLineWidth(1.0f);
		}
		else if (node->marked) {
			UI_ThemeColorShade(TH_TEXT_HI, -50);
			glLineWidth(2.0f);
			fdrawbox(node->xmin, node->ymin, node->xmax, node->ymax);
			glLineWidth(1.0f);
		}
		else {
			UI_ThemeColorShade(TH_TEXT, -40);
			fdrawbox(node->xmin, node->ymin, node->xmax, node->ymax);
		}
		UI_ThemeColorShade(TH_TEXT, -40);

		if (node->task != MM_TASK_NONE) {
			const float y = (node->ymin + node->ymax) * 0.5f;

			fdrawbox(node->xmin + 4.0f, y - 5.0f, node->xmin + 14.0f, y + 5.0f);
			if (node->task == MM_TASK_DONE) {
				UI_ThemeColor(TH_TEXT_HI);
				glRectf(node->xmin + 6.0f, y - 3.0f, node->xmin + 12.0f, y + 3.0f);
				UI_ThemeColorShade(TH_TEXT, -40);
			}
		}

		if (node->has_hidden_children || (node->has_children && node->elem == selected && i != 0)) {
			const float x = (node->side > 0) ? node->xmax + FOLD_MARK_SIZE : node->xmin - FOLD_MARK_SIZE;
			const float y = (node->ymin + node->ymax) * 0.5f;

			UI_ThemeColor(TH_BACK);
			glRectf(x - FOLD_MARK_SIZE, y - FOLD_MARK_SIZE, x + FOLD_MARK_SIZE, y + FOLD_MARK_SIZE);
			UI_ThemeColorShade(TH_TEXT, -40);
			fdrawbox(x - FOLD_MARK_SIZE, y - FOLD_MARK_SIZE, x + FOLD_MARK_SIZE, y + FOLD_MARK_SIZE);
			fdrawline(x - FOLD_MARK_SIZE * 0.6f, y, x + FOLD_MARK_SIZE * 0.6f, y);
			if (node->has_hidden_children) {
				fdrawline(x, y - FOLD_MARK_SIZE * 0.6f, x, y + FOLD_MARK_SIZE * 0.6f);
			}
		}
	}
}

static void mindmap_draw_drop_hint(const MindMapCache *cache)
{
	const int index = cache->drop_target ? mindmap_layout_find(cache->layout, cache->drop_target) : -1;
	const MMLayoutNode *node;

	if (index == -1) {
		return;
	}
	node = &cache->layout->nodes[index];
	UI_ThemeColor(TH_TEXT_HI);
	glLineWidth(3.0f);
	if (cache->drop_zone == DROP_CHILD) {
		fdrawbox(node->xmin, node->ymin, node->xmax, node->ymax);
	}
	else {
		const float y = (cache->drop_zone == DROP_BEFORE) ? node->ymax + 4.0f : node->ymin - 4.0f;

		fdrawline(node->xmin, y, node->xmax, y);
	}
	glLineWidth(1.0f);
}

static int mindmap_mark_icon(const MMLayoutNode *node)
{
	int value;

	if (node->engine_icon[0] && RNA_enum_value_from_id(rna_enum_icon_items, node->engine_icon, &value)) {
		return value;
	}
	switch (node->icon) {
		case '*': return ICON_SOLO_ON;
		case '?': return ICON_QUESTION;
		case '!': return ICON_ERROR;
		case 'V': return ICON_CHECKBOX_HLT;
		case 'X': return ICON_CANCEL;
		case 'F': return ICON_BOOKMARKS;
		case 'i': return ICON_INFO;
		default: return ICON_NONE;
	}
}

static void mindmap_draw_mark(float x, float center_y, float scale, int icon)
{
	const int size = max_ii((int)(14.0f * scale + 0.5f), 8);

	glEnable(GL_BLEND);
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
	UI_icon_draw_size(floorf(x), floorf(center_y - size * 0.5f), size, icon, 1.0f);
	glDisable(GL_BLEND);
}

static void mindmap_draw_texts(const MMLayout *layout, const ARegion *ar)
{
	const rctf *cur = &ar->v2d.cur;
	const float scale = ar->winx / max_ff(BLI_rctf_size_x(cur), 1.0f);
	const int pixels = (int)(TEXT_POINTS * scale + 0.5f);
	const int font = mindmap_font_id();
	int i;

	if (pixels < TEXT_MIN_PIXELS) {
		return;
	}

	BLF_size(font, pixels, 72);
	for (i = 0; i < layout->count; i++) {
		const MMLayoutNode *node = &layout->nodes[i];

		if (mindmap_rect_visible(cur, node->xmin, node->xmax, node->ymin, node->ymax)) {
			const float width = BLF_width(font, node->text, BLF_DRAW_STR_DUMMY_MAX);
			const float center_x = ((node->xmin + node->text_offset + node->xmax - node->text_right) * 0.5f - cur->xmin) * scale;
			const float center_y = ((node->ymin + node->ymax) * 0.5f - cur->ymin) * scale;
			const float baseline = floorf(center_y - pixels * 0.35f);
			const int mark_icon = mindmap_mark_icon(node);
			float mark_x = (node->xmin + 4.0f + (node->task != MM_TASK_NONE ? 16.0f : 0.0f) - cur->xmin) * scale;

			if (node->has_color) {
				glColor3ubv(node->color);
			}
			else {
				UI_ThemeColor(TH_TEXT);
			}
			BLF_position(font, floorf(center_x - width * 0.5f), baseline, 0.0f);
			BLF_draw(font, node->text, BLF_DRAW_STR_DUMMY_MAX);

			if (node->icon || node->engine_icon[0]) {
				if (mark_icon != ICON_NONE) {
					mindmap_draw_mark(mark_x, center_y, scale, mark_icon);
				}
				mark_x += 16.0f * scale;
			}
			if (node->has_note) {
				mindmap_draw_mark(mark_x, center_y, scale, ICON_TEXT);
			}
			if (node->has_link || node->progress[0]) {
				float right_x = (node->xmax - cur->xmin) * scale;

				UI_ThemeColor(TH_TEXT_HI);
				if (node->has_link) {
					mindmap_draw_mark(right_x - 16.0f * scale, center_y, scale, ICON_LINKED);
					UI_ThemeColor(TH_TEXT_HI);
					right_x -= 16.0f * scale;
				}
				if (node->progress[0]) {
					BLF_position(font, floorf(right_x - 6.0f * scale - BLF_width(font, node->progress, BLF_DRAW_STR_DUMMY_MAX)), baseline, 0.0f);
					BLF_draw(font, node->progress, BLF_DRAW_STR_DUMMY_MAX);
				}
			}
		}
	}
}

/* Dims the idea being dragged and draws a copy of it following the mouse. */
static void mindmap_draw_drag_ghost(const bContext *C, ARegion *ar, const MindMapCache *cache)
{
	const rctf *cur = &ar->v2d.cur;
	const int index = cache->dragging ? mindmap_layout_find(cache->layout, cache->drag_node) : -1;
	const MMLayoutNode *node;
	float xmin, xmax, ymin, ymax, scale;
	int pixels, font;

	if (index == -1) {
		return;
	}
	node = &cache->layout->nodes[index];
	xmin = node->xmin + cache->drag_delta[0];
	xmax = node->xmax + cache->drag_delta[0];
	ymin = node->ymin + cache->drag_delta[1];
	ymax = node->ymax + cache->drag_delta[1];

	UI_view2d_view_ortho(&ar->v2d);
	glEnable(GL_BLEND);
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
	UI_ThemeColorShadeAlpha(TH_BACK, 0, -90);
	glRectf(node->xmin, node->ymin, node->xmax, node->ymax);
	UI_ThemeColorShadeAlpha(TH_BACK, -30, -40);
	glRectf(xmin, ymin, xmax, ymax);
	UI_ThemeColor(TH_TEXT_HI);
	glLineWidth(2.0f);
	fdrawbox(xmin, ymin, xmax, ymax);
	glLineWidth(1.0f);
	glDisable(GL_BLEND);
	UI_view2d_view_restore(C);

	scale = ar->winx / max_ff(BLI_rctf_size_x(cur), 1.0f);
	pixels = (int)(TEXT_POINTS * scale + 0.5f);
	font = mindmap_font_id();
	if (pixels >= TEXT_MIN_PIXELS) {
		float width;

		BLF_size(font, pixels, 72);
		width = BLF_width(font, node->text, BLF_DRAW_STR_DUMMY_MAX);
		UI_ThemeColor(TH_TEXT_HI);
		BLF_position(font, floorf(((xmin + xmax) * 0.5f - cur->xmin) * scale - width * 0.5f),
		             floorf(((ymin + ymax) * 0.5f - cur->ymin) * scale - pixels * 0.35f), 0.0f);
		BLF_draw(font, node->text, BLF_DRAW_STR_DUMMY_MAX);
	}
}

static void mindmap_edit_apply(bContext *C, void *arg, void *UNUSED(arg2))
{
	MindMapCache *cache = arg;

	if (!cache->editing || cache->doc == NULL) {
		return;
	}
	cache->editing = false;

	if (cache->edit_buffer[0] == '\0') {
		if (cache->editing_new) {
			mindmap_edit_cancel_new(cache);
		}
	}
	else {
		mm_node_text_set(cache->selected, cache->edit_buffer);
		mindmap_cache_commit(cache);
		ED_undo_push(C, cache->editing_new ? "Add Idea" : "Edit Idea");
	}
	ED_region_tag_redraw(CTX_wm_region(C));
}

static void mindmap_draw_edit_field(const bContext *C, ARegion *ar, MindMapCache *cache)
{
	const int index = mindmap_layout_find(cache->layout, cache->selected);
	const MMLayoutNode *node;
	uiBlock *block;
	uiBut *but;
	float width, x;

	if (index == -1) {
		cache->editing = false;
		return;
	}
	node = &cache->layout->nodes[index];
	width = max_ff(node->xmax - node->xmin, EDIT_MIN_WIDTH);
	x = (node->side < 0) ? node->xmax - width : node->xmin;

	UI_view2d_view_ortho(&ar->v2d);
	block = UI_block_begin(C, ar, "mindmap_edit", UI_EMBOSS);
	but = uiDefBut(block, UI_BTYPE_TEXT, 0, "", x, node->ymin, width, node->ymax - node->ymin,
	               cache->edit_buffer, 0.0f, (float)(EDIT_BUFFER_SIZE - 1), 0, 0, "");
	UI_but_func_set(but, mindmap_edit_apply, cache, NULL);
	UI_but_flag_disable(but, UI_BUT_UNDO);  /* mindmap_edit_apply pushes the only step */

	/* False when the field was closed without applying (Esc). */
	if (!UI_but_active_only(C, ar, block, but)) {
		cache->editing = false;
		if (cache->editing_new) {
			mindmap_edit_cancel_new(cache);
		}
		WM_event_add_notifier(C, NC_SPACE | ND_SPACE_TEXT, NULL);
	}
	UI_block_end(C, block);
	UI_block_draw(C, block);
	UI_view2d_view_restore(C);
}

static void mindmap_draw_message(const ARegion *ar, const char *message)
{
	UI_ThemeColor(TH_TEXT);
	BLF_draw_default(
	        (ar->winx - BLF_width_default(message, BLF_DRAW_STR_DUMMY_MAX)) * 0.5f,
	        ar->winy * 0.5f, 0.0f, message, BLF_DRAW_STR_DUMMY_MAX);
}

static SpaceLink *mindmap_new(const bContext *UNUSED(C))
{
	SpaceMindMap *smm = MEM_callocN(sizeof(SpaceMindMap), "SpaceMindMap");
	ARegion *ar;

	smm->spacetype = SPACE_MINDMAP;

	ar = MEM_callocN(sizeof(ARegion), "header for mind map");
	BLI_addtail(&smm->regionbase, ar);
	ar->regiontype = RGN_TYPE_HEADER;
	ar->alignment = RGN_ALIGN_TOP;

	ar = MEM_callocN(sizeof(ARegion), "main region for mind map");
	BLI_addtail(&smm->regionbase, ar);
	ar->regiontype = RGN_TYPE_WINDOW;

	BLI_rctf_init(&ar->v2d.tot, -5000.0f, 5000.0f, -5000.0f, 5000.0f);
	BLI_rctf_init(&ar->v2d.cur, -500.0f, 500.0f, -500.0f, 500.0f);
	ar->v2d.min[0] = ar->v2d.min[1] = 20.0f;
	ar->v2d.max[0] = ar->v2d.max[1] = 10000000.0f;
	ar->v2d.minzoom = MIN_ZOOM;
	ar->v2d.maxzoom = 5.0f;
	ar->v2d.keepzoom = V2D_LIMITZOOM | V2D_KEEPASPECT;
	ar->v2d.keeptot = V2D_KEEPTOT_FREE;

	return (SpaceLink *)smm;
}

static void mindmap_free(SpaceLink *sl)
{
	MindMapCache *cache = BLI_findptr(&mindmap_caches, sl, offsetof(MindMapCache, smm));

	if (cache) {
		mindmap_cache_clear_contents(cache);
		BLI_freelinkN(&mindmap_caches, cache);
	}
}

static void mindmap_init(wmWindowManager *UNUSED(wm), ScrArea *UNUSED(sa))
{
}

static SpaceLink *mindmap_duplicate(SpaceLink *sl)
{
	return (SpaceLink *)MEM_dupallocN(sl);
}

static void mindmap_id_remap(ScrArea *UNUSED(sa), SpaceLink *slink, ID *old_id, ID *new_id)
{
	SpaceMindMap *smm = (SpaceMindMap *)slink;

	if ((ID *)smm->text == old_id) {
		smm->text = (Text *)new_id;
	}
}

static void mindmap_main_region_init(wmWindowManager *wm, ARegion *ar)
{
	wmKeyMap *keymap;

	/* Large maps need more range than areas saved by earlier builds have. */
	ar->v2d.minzoom = MIN_ZOOM;
	ar->v2d.min[0] = ar->v2d.min[1] = 20.0f;
	ar->v2d.max[0] = ar->v2d.max[1] = 10000000.0f;

	UI_view2d_region_reinit(&ar->v2d, V2D_COMMONVIEW_CUSTOM, ar->winx, ar->winy);

	keymap = WM_keymap_ensure(wm->defaultconf, "Mind Map", SPACE_MINDMAP, 0);
	WM_event_add_keymap_handler(&ar->handlers, keymap);
}

static void mindmap_draw_map(const bContext *C, ARegion *ar, const MindMapCache *cache)
{
	UI_view2d_view_ortho(&ar->v2d);
	glEnable(GL_BLEND);
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
	glEnable(GL_LINE_SMOOTH);
	mindmap_draw_links(cache->layout, &ar->v2d.cur);
	mindmap_draw_boxes(cache->layout, &ar->v2d.cur, cache->selected);
	mindmap_draw_drop_hint(cache);
	glDisable(GL_LINE_SMOOTH);
	glDisable(GL_BLEND);
	UI_view2d_view_restore(C);

	mindmap_draw_texts(cache->layout, ar);
	mindmap_draw_drag_ghost(C, ar, cache);
}

static void mindmap_main_region_draw(const bContext *C, ARegion *ar)
{
	const SpaceMindMap *smm = (SpaceMindMap *)CTX_wm_space_data(C);
	MindMapCache *cache = mindmap_cache_get(smm);

	UI_ThemeClearColor(TH_BACK);
	glClear(GL_COLOR_BUFFER_BIT);

	if (smm->text == NULL) {
		mindmap_draw_message(ar, "Choose a text with a mind map (.mm)");
		return;
	}
	if (cache->layout == NULL) {
		mindmap_draw_message(ar, cache->error);
		return;
	}

	if (cache->fit_view) {
		cache->fit_view = false;
		cache->reveal = false;
		mindmap_view_fit(ar, cache->layout);
	}
	else if (cache->reveal) {
		cache->reveal = false;
		mindmap_view_reveal(ar, cache);
	}

	mindmap_draw_map(C, ar, cache);

	if (cache->editing) {
		mindmap_draw_edit_field(C, ar, cache);
	}
}

static void mindmap_main_region_listener(
        bScreen *UNUSED(sc), ScrArea *UNUSED(sa), ARegion *ar, wmNotifier *wmn)
{
	if (wmn->category == NC_TEXT ||
	    (wmn->category == NC_SPACE && wmn->data == ND_SPACE_TEXT))
	{
		ED_region_tag_redraw(ar);
	}
}

static bool mindmap_poll(bContext *C)
{
	const SpaceLink *sl = CTX_wm_space_data(C);

	return sl && sl->spacetype == SPACE_MINDMAP;
}

static int mindmap_view_all_exec(bContext *C, wmOperator *UNUSED(op))
{
	ARegion *ar = CTX_wm_region(C);
	const MindMapCache *cache = mindmap_cache_get((SpaceMindMap *)CTX_wm_space_data(C));

	if (cache->layout == NULL) {
		return OPERATOR_CANCELLED;
	}
	mindmap_view_fit(ar, cache->layout);
	ED_region_tag_redraw(ar);
	return OPERATOR_FINISHED;
}

static MindMapCache *mindmap_edit_cache(bContext *C)
{
	return mindmap_cache_get((SpaceMindMap *)CTX_wm_space_data(C));
}

static bool mindmap_edit_poll(bContext *C)
{
	return mindmap_poll(C) && mindmap_edit_cache(C)->doc != NULL;
}

static void mindmap_edit_begin(MindMapCache *cache, MMElem *node, MMElem *previous)
{
	cache->selected = node;
	cache->editing = true;
	cache->editing_new = (previous != NULL);
	cache->edit_previous = previous;
	cache->edit_buffer[0] = '\0';
	cache->reveal = true;
}

static int mindmap_finish(bContext *C, const char *undo_name)
{
	ED_region_tag_redraw(CTX_wm_region(C));
	if (undo_name) {
		ED_undo_push(C, undo_name);
	}
	return OPERATOR_FINISHED;
}

static int mindmap_add_child_exec(bContext *C, wmOperator *UNUSED(op))
{
	MindMapCache *cache = mindmap_edit_cache(C);
	MMElem *parent = cache->selected;
	const MMElem *root = mm_root_node(cache->doc);
	MMElem *child;

	if (parent != root && mm_node_folded(parent)) {
		mm_node_folded_set(parent, 0);
	}
	child = mm_node_add_child(parent, "");
	if (parent == root) {
		const MMElem *other;
		int balance = 0;

		for (other = mm_node_first_child(root); other != child; other = mm_node_next(other)) {
			char *position = mm_attr_get(other, "POSITION");

			balance += (position && STREQ(position, "left")) ? -1 : 1;
			mm_str_free(position);
		}
		mm_attr_set(child, "POSITION", balance > 0 ? "left" : "right");
	}
	mindmap_edit_begin(cache, child, parent);
	mindmap_cache_commit(cache);
	return mindmap_finish(C, NULL);
}

static void MINDMAP_OT_add_child(wmOperatorType *ot)
{
	ot->name = "Add Child Idea";
	ot->idname = "MINDMAP_OT_add_child";
	ot->description = "Add an idea below the selected one and type its text";
	ot->exec = mindmap_add_child_exec;
	ot->poll = mindmap_edit_poll;
}

static int mindmap_add_sibling_exec(bContext *C, wmOperator *op)
{
	MindMapCache *cache = mindmap_edit_cache(C);
	MMElem *node = cache->selected;
	MMElem *sibling;
	char *position;

	if (node == mm_root_node(cache->doc)) {
		return mindmap_add_child_exec(C, op);
	}
	sibling = mm_node_add_sibling(node, "");
	position = mm_attr_get(node, "POSITION");
	if (position) {
		mm_attr_set(sibling, "POSITION", position);
		mm_str_free(position);
	}
	mindmap_edit_begin(cache, sibling, node);
	mindmap_cache_commit(cache);
	return mindmap_finish(C, NULL);
}

static void MINDMAP_OT_add_sibling(wmOperatorType *ot)
{
	ot->name = "Add Sibling Idea";
	ot->idname = "MINDMAP_OT_add_sibling";
	ot->description = "Add an idea after the selected one and type its text";
	ot->exec = mindmap_add_sibling_exec;
	ot->poll = mindmap_edit_poll;
}

static int mindmap_edit_exec(bContext *C, wmOperator *op)
{
	MindMapCache *cache = mindmap_edit_cache(C);
	char *text = mm_node_text(cache->selected);

	if (text == NULL || strlen(text) >= EDIT_BUFFER_SIZE) {
		mm_str_free(text);
		BKE_report(op->reports, RPT_WARNING, "This idea has formatted or very long text");
		return OPERATOR_CANCELLED;
	}
	mindmap_edit_begin(cache, cache->selected, NULL);
	BLI_strncpy(cache->edit_buffer, text, sizeof(cache->edit_buffer));
	mm_str_free(text);
	return mindmap_finish(C, NULL);
}

static int mindmap_hit_node(ARegion *ar, const MMLayout *layout, const MMElem *selected, const int mval[2], bool *r_on_mark, float r_co[2])
{
	float x, y;
	int i;

	UI_view2d_region_to_view(&ar->v2d, mval[0], mval[1], &x, &y);
	if (r_co) {
		r_co[0] = x;
		r_co[1] = y;
	}
	if (r_on_mark) {
		*r_on_mark = false;
	}
	for (i = 0; i < layout->count; i++) {
		const MMLayoutNode *node = &layout->nodes[i];

		if (x >= node->xmin && x <= node->xmax && y >= node->ymin && y <= node->ymax) {
			return i;
		}
		if (r_on_mark && i != 0 && (node->has_hidden_children || (node->has_children && node->elem == selected))) {
			const float mark_x = (node->side > 0) ? node->xmax + FOLD_MARK_SIZE : node->xmin - FOLD_MARK_SIZE;
			const float mark_y = (node->ymin + node->ymax) * 0.5f;

			if (fabsf(x - mark_x) <= FOLD_MARK_SIZE && fabsf(y - mark_y) <= FOLD_MARK_SIZE) {
				*r_on_mark = true;
				return i;
			}
		}
	}
	return -1;
}

static int mindmap_edit_invoke(bContext *C, wmOperator *op, const wmEvent *event)
{
	if (ISMOUSE(event->type)) {
		const MindMapCache *cache = mindmap_edit_cache(C);

		if (mindmap_hit_node(CTX_wm_region(C), cache->layout, cache->selected, event->mval, NULL, NULL) == -1) {
			return OPERATOR_CANCELLED | OPERATOR_PASS_THROUGH;
		}
	}
	return mindmap_edit_exec(C, op);
}

static void MINDMAP_OT_edit(wmOperatorType *ot)
{
	ot->name = "Edit Idea";
	ot->idname = "MINDMAP_OT_edit";
	ot->description = "Type a new text for the selected idea";
	ot->exec = mindmap_edit_exec;
	ot->invoke = mindmap_edit_invoke;
	ot->poll = mindmap_edit_poll;
}

/* ---------------- group selection ---------------- */

static int mindmap_count_nodes(const MMElem *node)
{
	const MMElem *child;
	int count = 1;

	for (child = mm_node_first_child(node); child; child = mm_node_next(child)) {
		count += mindmap_count_nodes(child);
	}
	return count;
}

static void mindmap_collect(MMElem *node, const MMElem *root, const MMElem *selected, bool branches, MMElem **items, int *count)
{
	MMElem *child;

	if ((node->marked || node == selected) && !(branches && node == root)) {
		items[(*count)++] = node;
		if (branches) {
			return;
		}
	}
	for (child = mm_node_first_child(node); child; child = mm_node_next(child)) {
		mindmap_collect(child, root, selected, branches, items, count);
	}
}

/* Selected ideas in map order. With branches, leaves out the root and what is inside
 * another selected idea. Release with MEM_freeN. */
static MMElem **mindmap_targets(const MindMapCache *cache, bool branches, int *r_count)
{
	MMElem *root = mm_root_node(cache->doc);
	MMElem **items = MEM_mallocN(sizeof(*items) * mindmap_count_nodes(root), "mindmap targets");

	*r_count = 0;
	mindmap_collect(root, root, cache->selected, branches, items, r_count);
	return items;
}

static void mindmap_marks_clear(MMElem *node)
{
	MMElem *child;

	node->marked = 0;
	for (child = mm_node_first_child(node); child; child = mm_node_next(child)) {
		mindmap_marks_clear(child);
	}
}

static int mindmap_delete_exec(bContext *C, wmOperator *UNUSED(op))
{
	MindMapCache *cache = mindmap_edit_cache(C);
	int count, i;
	MMElem **items = mindmap_targets(cache, true, &count);

	if (count == 0) {
		MEM_freeN(items);
		return OPERATOR_CANCELLED;
	}
	if (count == 1) {
		MMElem *node = items[0], *next, *other, *previous = NULL;

		for (other = mm_node_first_child(node->parent); other != node; other = mm_node_next(other)) {
			previous = other;
		}
		next = mm_node_next(node);
		cache->selected = next ? next : (previous ? previous : node->parent);
	}
	else {
		cache->selected = items[0]->parent;
	}
	for (i = 0; i < count; i++) {
		mm_node_remove(items[i]);
	}
	MEM_freeN(items);
	mindmap_cache_commit(cache);
	return mindmap_finish(C, "Delete Idea");
}

static void MINDMAP_OT_delete(wmOperatorType *ot)
{
	ot->name = "Delete Idea";
	ot->idname = "MINDMAP_OT_delete";
	ot->description = "Delete the selected idea and its branch";
	ot->exec = mindmap_delete_exec;
	ot->poll = mindmap_edit_poll;
}

static int mindmap_toggle_fold_exec(bContext *C, wmOperator *UNUSED(op))
{
	MindMapCache *cache = mindmap_edit_cache(C);
	MMElem *node = cache->selected;

	if (node == mm_root_node(cache->doc) || mm_node_first_child(node) == NULL) {
		return OPERATOR_CANCELLED;
	}
	mm_node_folded_set(node, !mm_node_folded(node));
	mindmap_cache_commit(cache);
	return mindmap_finish(C, "Fold Idea");
}

static void MINDMAP_OT_toggle_fold(wmOperatorType *ot)
{
	ot->name = "Fold or Unfold";
	ot->idname = "MINDMAP_OT_toggle_fold";
	ot->description = "Hide or show the branch of the selected idea";
	ot->exec = mindmap_toggle_fold_exec;
	ot->poll = mindmap_edit_poll;
}

static bool mindmap_elem_inside(const MMElem *elem, const MMElem *branch)
{
	for (; elem; elem = elem->parent) {
		if (elem == branch) {
			return true;
		}
	}
	return false;
}

static void mindmap_task_write(MMElem *node, int task)
{
	if (task == MM_TASK_NONE) {
		mm_attr_remove(node, MM_ATTR_TASK);
	}
	else {
		mm_attr_set(node, MM_ATTR_TASK, task == MM_TASK_DONE ? "done" : "todo");
	}
}

/* Link: the ID name with its type prefix (OBCube, SCScene, TXscript.py). Link id: a
 * token also stored in the target, which finds it again after it is renamed. */
#define MINDMAP_ID_PROP "mindmap_link_id"

static ListBase *mindmap_link_list(Main *bmain, const char *link)
{
	if (STREQLEN(link, "OB", 2)) {
		return &bmain->object;
	}
	if (STREQLEN(link, "SC", 2)) {
		return &bmain->scene;
	}
	return STREQLEN(link, "TX", 2) ? &bmain->text : NULL;
}

static const char *mindmap_id_token(ID *id)
{
	IDProperty *group = IDP_GetProperties(id, false);
	IDProperty *prop = group ? IDP_GetPropertyFromGroup(group, MINDMAP_ID_PROP) : NULL;

	return (prop && prop->type == IDP_STRING) ? prop->data.pointer : NULL;
}

/* Returns NULL for data from a library, which cannot be changed. */
static const char *mindmap_id_token_ensure(ID *id)
{
	const char *token = mindmap_id_token(id);

	if (token == NULL && id->lib == NULL) {
		char buffer[32];

		BLI_snprintf(buffer, sizeof(buffer), "%08x%08x", (unsigned int)time(NULL), (unsigned int)(intptr_t)id);
		IDP_AddToGroup(IDP_GetProperties(id, true), IDP_NewString(buffer, MINDMAP_ID_PROP, sizeof(buffer) - 1));
		token = mindmap_id_token(id);
	}
	return token;
}

static ID *mindmap_link_find(Main *bmain, const char *link, const char *token)
{
	ListBase *list = mindmap_link_list(bmain, link);
	ID *id, *by_name;

	if (list == NULL || strlen(link) <= 2) {
		return NULL;
	}
	by_name = BLI_findstring(list, link + 2, offsetof(ID, name) + 2);
	if (token == NULL) {
		return by_name;
	}
	/* The name goes first: a duplicated object carries the same token. */
	if (by_name && STREQ(mindmap_id_token(by_name) ? mindmap_id_token(by_name) : "", token)) {
		return by_name;
	}
	for (id = list->first; id; id = id->next) {
		const char *other = mindmap_id_token(id);

		if (other && STREQ(other, token)) {
			return id;
		}
	}
	return by_name;
}

static bool mindmap_open_link(bContext *C, ReportList *reports, const MMElem *node)
{
	Main *bmain = CTX_data_main(C);
	bScreen *screen = CTX_wm_screen(C);
	char *link = mm_attr_get(node, MM_ATTR_LINK);
	char *token = mm_attr_get(node, MM_ATTR_LINK_ID);
	ID *id = link ? mindmap_link_find(bmain, link, token) : NULL;
	bool opened = false;

	if (id && GS(id->name) == ID_OB) {
		Object *ob = (Object *)id;
		Scene *scene = CTX_data_scene(C), *sce;
		Base *base = BKE_scene_base_find(scene, ob);

		for (sce = bmain->scene.first; !base && sce; sce = sce->id.next) {
			base = BKE_scene_base_find(sce, ob);
			if (base) {
				scene = sce;
				WM_event_add_notifier(C, NC_SCREEN | ND_SCENEBROWSE, scene);
			}
		}
		if (base) {
			BKE_scene_base_deselect_all(scene);
			BKE_scene_base_select(scene, base);
			WM_event_add_notifier(C, NC_SCENE | ND_OB_SELECT, scene);
			opened = true;
		}
	}
	else if (id && GS(id->name) == ID_SCE) {
		WM_event_add_notifier(C, NC_SCREEN | ND_SCENEBROWSE, id);
		opened = true;
	}
	else if (id && GS(id->name) == ID_TXT) {
		ScrArea *sa;

		for (sa = screen->areabase.first; sa; sa = sa->next) {
			if (sa->spacetype == SPACE_TEXT) {
				((SpaceText *)sa->spacedata.first)->text = (Text *)id;
				ED_area_tag_redraw(sa);
				opened = true;
				break;
			}
		}
		if (!opened) {
			BKE_report(reports, RPT_WARNING, "Open a Text Editor area to see this text");
		}
	}
	if (id == NULL) {
		BKE_reportf(reports, RPT_WARNING, "Linked item not found: %s", (link && strlen(link) > 2) ? link + 2 : "");
	}
	mm_str_free(link);
	mm_str_free(token);
	return opened;
}

static void mindmap_drag_update(ARegion *ar, MindMapCache *cache, const int mval[2])
{
	float co[2];
	const int index = mindmap_hit_node(ar, cache->layout, cache->selected, mval, NULL, co);
	float now[2], start[2];

	UI_view2d_region_to_view(&ar->v2d, mval[0], mval[1], &now[0], &now[1]);
	UI_view2d_region_to_view(&ar->v2d, cache->drag_start[0], cache->drag_start[1], &start[0], &start[1]);
	sub_v2_v2v2(cache->drag_delta, now, start);

	cache->drop_target = NULL;
	if (index != -1 && !mindmap_elem_inside(cache->layout->nodes[index].elem, cache->drag_node)) {
		const MMLayoutNode *node = &cache->layout->nodes[index];
		const float t = (co[1] - node->ymin) / (node->ymax - node->ymin);

		cache->drop_target = node->elem;
		cache->drop_side = (co[0] >= 0.0f) ? 1 : -1;
		cache->drop_zone = (index == 0) ? DROP_CHILD : (t > 0.75f ? DROP_BEFORE : (t < 0.25f ? DROP_AFTER : DROP_CHILD));
	}
	ED_region_tag_redraw(ar);
}

static void mindmap_drag_apply(bContext *C, MindMapCache *cache)
{
	MMElem *target = (MMElem *)cache->drop_target;
	const MMElem *root = mm_root_node(cache->doc);
	MMElem *parent, *before = NULL;
	MMElem **items;
	char *position = NULL;
	bool moved = false;
	int count, i;

	if (target == NULL) {
		return;
	}
	items = mindmap_targets(cache, true, &count);
	for (i = 0; i < count; i++) {
		if (mindmap_elem_inside(target, items[i])) {
			MEM_freeN(items);
			return;
		}
	}
	if (cache->drop_zone == DROP_CHILD) {
		parent = target;
		if (target != root && mm_node_folded(target)) {
			mm_node_folded_set(target, 0);
		}
	}
	else {
		parent = target->parent;
		before = (cache->drop_zone == DROP_BEFORE) ? target : mm_node_next(target);
		while (before && (before->marked || before == cache->selected)) {
			before = mm_node_next(before);
		}
		position = mm_attr_get(target, "POSITION");
	}

	for (i = 0; i < count; i++) {
		MMElem *node = items[i];

		if (mm_node_move(node, parent, before)) {
			moved = true;
			if (parent != root) {
				mm_attr_remove(node, "POSITION");
			}
			else if (position) {
				mm_attr_set(node, "POSITION", position);
			}
			else {
				mm_attr_set(node, "POSITION", cache->drop_side > 0 ? "right" : "left");
			}
		}
	}
	if (moved) {
		mindmap_cache_commit(cache);
		ED_undo_push(C, "Move Idea");
	}
	MEM_freeN(items);
	mm_str_free(position);
}

static void mindmap_drag_end(ARegion *ar, MindMapCache *cache)
{
	cache->drag_node = NULL;
	cache->dragging = false;
	cache->drop_target = NULL;
	ED_region_tag_redraw(ar);
}

static int mindmap_click_invoke(bContext *C, wmOperator *op, const wmEvent *event)
{
	ARegion *ar = CTX_wm_region(C);
	MindMapCache *cache = mindmap_edit_cache(C);
	bool on_mark;
	float co[2];
	const int index = mindmap_hit_node(ar, cache->layout, cache->selected, event->mval, &on_mark, co);
	const MMLayoutNode *hit;
	MMElem *node;

	if (index == -1) {
		mindmap_marks_clear(mm_root_node(cache->doc));
		mindmap_cache_rebuild_layout(cache);
		ED_region_tag_redraw(ar);
		return OPERATOR_CANCELLED | OPERATOR_PASS_THROUGH;
	}
	hit = &cache->layout->nodes[index];
	node = hit->elem;
	if (!node->marked) {
		mindmap_marks_clear(mm_root_node(cache->doc));
		mindmap_cache_rebuild_layout(cache);
		hit = &cache->layout->nodes[mindmap_layout_find(cache->layout, node)];
	}
	cache->selected = node;
	ED_region_tag_redraw(ar);

	if (!on_mark && hit->task != MM_TASK_NONE && co[0] <= hit->xmin + 16.0f) {
		mindmap_task_write(node, hit->task == MM_TASK_DONE ? MM_TASK_TODO : MM_TASK_DONE);
		mindmap_cache_commit(cache);
		ED_undo_push(C, "Toggle Task");
		return OPERATOR_FINISHED;
	}
	if (!on_mark && hit->has_link && co[0] >= hit->xmax - 16.0f) {
		mindmap_open_link(C, op->reports, node);
		return OPERATOR_FINISHED;
	}

	if (on_mark) {
		mm_node_folded_set(node, !mm_node_folded(node));
		mindmap_cache_commit(cache);
		ED_undo_push(C, "Fold Idea");
		return OPERATOR_FINISHED;
	}
	if (node == mm_root_node(cache->doc)) {
		return OPERATOR_FINISHED;
	}

	cache->drag_node = node;
	cache->dragging = false;
	copy_v2_v2_int(cache->drag_start, event->mval);
	op->customdata = cache;
	WM_event_add_modal_handler(C, op);
	return OPERATOR_RUNNING_MODAL;
}

static int mindmap_click_modal(bContext *C, wmOperator *op, const wmEvent *event)
{
	ARegion *ar = CTX_wm_region(C);
	MindMapCache *cache = op->customdata;

	switch (event->type) {
		case MOUSEMOVE:
			if (!cache->dragging &&
			    (abs(event->mval[0] - cache->drag_start[0]) + abs(event->mval[1] - cache->drag_start[1])) > 6)
			{
				cache->dragging = true;
			}
			if (cache->dragging) {
				mindmap_drag_update(ar, cache, event->mval);
			}
			break;
		case LEFTMOUSE:
			if (event->val == KM_RELEASE) {
				if (cache->dragging) {
					mindmap_drag_apply(C, cache);
				}
				else {
					mindmap_marks_clear(mm_root_node(cache->doc));
					mindmap_cache_rebuild_layout(cache);
				}
				mindmap_drag_end(ar, cache);
				return OPERATOR_FINISHED;
			}
			break;
		case ESCKEY:
		case RIGHTMOUSE:
			mindmap_drag_end(ar, cache);
			return OPERATOR_CANCELLED;
		default:
			break;
	}
	return OPERATOR_RUNNING_MODAL;
}

static void mindmap_click_cancel(bContext *C, wmOperator *op)
{
	mindmap_drag_end(CTX_wm_region(C), op->customdata);
}

static void MINDMAP_OT_click(wmOperatorType *ot)
{
	ot->name = "Select or Drag Idea";
	ot->idname = "MINDMAP_OT_click";
	ot->description = "Select an idea, drag it to another place, or open its fold mark";
	ot->invoke = mindmap_click_invoke;
	ot->modal = mindmap_click_modal;
	ot->cancel = mindmap_click_cancel;
	ot->poll = mindmap_edit_poll;
	ot->flag = OPTYPE_BLOCKING;
}

static const char *mindmap_color_values[] = {NULL, "#ff6b6b", "#ffa94d", "#ffd43b", "#69db7c", "#74c0fc", "#b197fc"};

static int mindmap_set_color_exec(bContext *C, wmOperator *op)
{
	MindMapCache *cache = mindmap_edit_cache(C);
	const char *value = mindmap_color_values[RNA_enum_get(op->ptr, "color")];
	int count, i;
	MMElem **items = mindmap_targets(cache, false, &count);

	for (i = 0; i < count; i++) {
		if (value) {
			mm_attr_set(items[i], "COLOR", value);
		}
		else {
			mm_attr_remove(items[i], "COLOR");
		}
	}
	MEM_freeN(items);
	mindmap_cache_commit(cache);
	return mindmap_finish(C, "Idea Color");
}

static void MINDMAP_OT_set_color(wmOperatorType *ot)
{
	static const EnumPropertyItem items[] = {
		{0, "NONE", 0, "Default", ""},
		{1, "RED", 0, "Red", ""},
		{2, "ORANGE", 0, "Orange", ""},
		{3, "YELLOW", 0, "Yellow", ""},
		{4, "GREEN", 0, "Green", ""},
		{5, "BLUE", 0, "Blue", ""},
		{6, "PURPLE", 0, "Purple", ""},
		{0, NULL, 0, NULL, NULL},
	};

	ot->name = "Idea Color";
	ot->idname = "MINDMAP_OT_set_color";
	ot->description = "Change the text color of the selected idea";
	ot->exec = mindmap_set_color_exec;
	ot->poll = mindmap_edit_poll;
	RNA_def_enum(ot->srna, "color", items, 0, "Color", "");
}

static const char *mindmap_icon_values[] = {NULL, "idea", "help", "messagebox_warning", "button_ok", "button_cancel", "flag"};

static int mindmap_set_icon_exec(bContext *C, wmOperator *op)
{
	MindMapCache *cache = mindmap_edit_cache(C);

	int count, i;
	MMElem **items = mindmap_targets(cache, false, &count);

	for (i = 0; i < count; i++) {
		mm_node_icon_set(items[i], mindmap_icon_values[RNA_enum_get(op->ptr, "icon")]);
		mm_attr_remove(items[i], MM_ATTR_ICON);
	}
	MEM_freeN(items);
	mindmap_cache_commit(cache);
	return mindmap_finish(C, "Idea Icon");
}

static void MINDMAP_OT_set_icon(wmOperatorType *ot)
{
	static const EnumPropertyItem items[] = {
		{0, "NONE", 0, "None", ""},
		{1, "IDEA", ICON_SOLO_ON, "Idea", ""},
		{2, "HELP", ICON_QUESTION, "Question", ""},
		{3, "WARNING", ICON_ERROR, "Warning", ""},
		{4, "OK", ICON_CHECKBOX_HLT, "Done", ""},
		{5, "CANCEL", ICON_CANCEL, "Cancelled", ""},
		{6, "FLAG", ICON_BOOKMARKS, "Flag", ""},
		{0, NULL, 0, NULL, NULL},
	};

	ot->name = "Idea Icon";
	ot->idname = "MINDMAP_OT_set_icon";
	ot->description = "Mark the selected idea with an icon";
	ot->exec = mindmap_set_icon_exec;
	ot->poll = mindmap_edit_poll;
	RNA_def_enum(ot->srna, "icon", items, 0, "Icon", "");
}

static int mindmap_set_engine_icon_exec(bContext *C, wmOperator *op)
{
	MindMapCache *cache = mindmap_edit_cache(C);
	const char *identifier = NULL;
	const int value = RNA_property_enum_get(op->ptr, op->type->prop);

	if (!RNA_property_enum_identifier(C, op->ptr, op->type->prop, value, &identifier)) {
		return OPERATOR_CANCELLED;
	}
	{
		int count, i;
		MMElem **items = mindmap_targets(cache, false, &count);

		for (i = 0; i < count; i++) {
			if (value == ICON_NONE) {
				mm_attr_remove(items[i], MM_ATTR_ICON);
			}
			else {
				mm_attr_set(items[i], MM_ATTR_ICON, identifier);
			}
		}
		MEM_freeN(items);
	}
	mindmap_cache_commit(cache);
	return mindmap_finish(C, "Idea Engine Icon");
}

static void MINDMAP_OT_set_engine_icon(wmOperatorType *ot)
{
	PropertyRNA *prop;

	ot->name = "Engine Icon";
	ot->idname = "MINDMAP_OT_set_engine_icon";
	ot->description = "Search all the icons of the engine for the selected idea";
	ot->invoke = WM_enum_search_invoke;
	ot->exec = mindmap_set_engine_icon_exec;
	ot->poll = mindmap_edit_poll;
	prop = RNA_def_enum(ot->srna, "icon", rna_enum_icon_items, ICON_NONE, "Icon", "");
	RNA_def_property_flag(prop, PROP_ENUM_NO_TRANSLATE);
	ot->prop = prop;
}

static int mindmap_edit_note_invoke(bContext *C, wmOperator *op, const wmEvent *UNUSED(event))
{
	const MindMapCache *cache = mindmap_edit_cache(C);
	char *note = mm_node_note(cache->selected);

	if (note && strlen(note) >= EDIT_BUFFER_SIZE) {
		mm_str_free(note);
		BKE_report(op->reports, RPT_WARNING, "This note is too long to edit here");
		return OPERATOR_CANCELLED;
	}
	RNA_string_set(op->ptr, "note", note ? note : "");
	mm_str_free(note);
	return WM_operator_props_dialog_popup(C, op, 12 * UI_UNIT_X * 2, UI_UNIT_Y);
}

static int mindmap_edit_note_exec(bContext *C, wmOperator *op)
{
	MindMapCache *cache = mindmap_edit_cache(C);
	char *old_note = mm_node_note(cache->selected);
	char *note = RNA_string_get_alloc(op->ptr, "note", NULL, 0);
	const bool changed = !STREQ(old_note ? old_note : "", note);

	if (changed) {
		mm_node_note_set(cache->selected, note);
		mindmap_cache_commit(cache);
	}
	mm_str_free(old_note);
	MEM_freeN(note);
	return mindmap_finish(C, changed ? "Idea Note" : NULL);
}

static void MINDMAP_OT_edit_note(wmOperatorType *ot)
{
	PropertyRNA *prop;

	ot->name = "Idea Note";
	ot->idname = "MINDMAP_OT_edit_note";
	ot->description = "Write a note for the selected idea";
	ot->invoke = mindmap_edit_note_invoke;
	ot->exec = mindmap_edit_note_exec;
	ot->poll = mindmap_edit_poll;
	prop = RNA_def_string(ot->srna, "note", NULL, EDIT_BUFFER_SIZE, "Note", "");
	RNA_def_property_flag(prop, PROP_SKIP_SAVE);
}

static int mindmap_cycle_task_exec(bContext *C, wmOperator *UNUSED(op))
{
	MindMapCache *cache = mindmap_edit_cache(C);

	const int task = (mm_node_task(cache->selected) + 1) % 3;
	int count, i;
	MMElem **items = mindmap_targets(cache, false, &count);

	for (i = 0; i < count; i++) {
		mindmap_task_write(items[i], task);
	}
	MEM_freeN(items);
	mindmap_cache_commit(cache);
	return mindmap_finish(C, "Idea Task");
}

static void MINDMAP_OT_cycle_task(wmOperatorType *ot)
{
	ot->name = "Task";
	ot->idname = "MINDMAP_OT_cycle_task";
	ot->description = "Turn the selected idea into a task, mark it done, or remove the task";
	ot->exec = mindmap_cycle_task_exec;
	ot->poll = mindmap_edit_poll;
}

static const EnumPropertyItem *mindmap_link_itemf(
        bContext *C, PointerRNA *UNUSED(ptr), PropertyRNA *UNUSED(prop), bool *r_free)
{
	Main *bmain = CTX_data_main(C);
	EnumPropertyItem *items = NULL, item = {0};
	const struct {
		ListBase *list;
		int icon;
	} kinds[] = {{&bmain->object, ICON_OBJECT_DATA}, {&bmain->scene, ICON_SCENE_DATA}, {&bmain->text, ICON_TEXT}};
	int total = 0, k;
	ID *id;

	for (k = 0; k < ARRAY_SIZE(kinds); k++) {
		for (id = kinds[k].list->first; id; id = id->next) {
			item.value = total;
			item.identifier = id->name;
			item.name = id->name + 2;
			item.icon = kinds[k].icon;
			RNA_enum_item_add(&items, &total, &item);
		}
	}
	RNA_enum_item_end(&items, &total);
	*r_free = true;
	return items;
}

static int mindmap_set_link_exec(bContext *C, wmOperator *op)
{
	MindMapCache *cache = mindmap_edit_cache(C);
	const char *identifier = NULL;

	if (!RNA_property_enum_identifier(C, op->ptr, op->type->prop, RNA_property_enum_get(op->ptr, op->type->prop), &identifier)) {
		return OPERATOR_CANCELLED;
	}
	{
		ListBase *list = mindmap_link_list(CTX_data_main(C), identifier);
		ID *id = list ? BLI_findstring(list, identifier, offsetof(ID, name)) : NULL;
		const char *token = id ? mindmap_id_token_ensure(id) : NULL;
		int count, i;
		MMElem **items = mindmap_targets(cache, false, &count);

		for (i = 0; i < count; i++) {
			mm_attr_set(items[i], MM_ATTR_LINK, identifier);
			if (token) {
				mm_attr_set(items[i], MM_ATTR_LINK_ID, token);
			}
			else {
				mm_attr_remove(items[i], MM_ATTR_LINK_ID);
			}
		}
		MEM_freeN(items);
	}
	mindmap_cache_commit(cache);
	return mindmap_finish(C, "Link Idea");
}

static void MINDMAP_OT_set_link(wmOperatorType *ot)
{
	PropertyRNA *prop;

	ot->name = "Link Idea";
	ot->idname = "MINDMAP_OT_set_link";
	ot->description = "Link the selected idea to an object, scene or text";
	ot->invoke = WM_enum_search_invoke;
	ot->exec = mindmap_set_link_exec;
	ot->poll = mindmap_edit_poll;
	prop = RNA_def_enum(ot->srna, "target", DummyRNA_NULL_items, 0, "Target", "");
	RNA_def_enum_funcs(prop, mindmap_link_itemf);
	RNA_def_property_flag(prop, PROP_ENUM_NO_TRANSLATE);
	ot->prop = prop;
}

static int mindmap_clear_link_exec(bContext *C, wmOperator *UNUSED(op))
{
	MindMapCache *cache = mindmap_edit_cache(C);

	mm_attr_remove(cache->selected, MM_ATTR_LINK);
	mm_attr_remove(cache->selected, MM_ATTR_LINK_ID);
	mindmap_cache_commit(cache);
	return mindmap_finish(C, "Clear Idea Link");
}

static void MINDMAP_OT_clear_link(wmOperatorType *ot)
{
	ot->name = "Clear Link";
	ot->idname = "MINDMAP_OT_clear_link";
	ot->description = "Remove the link of the selected idea";
	ot->exec = mindmap_clear_link_exec;
	ot->poll = mindmap_edit_poll;
}

static int mindmap_open_link_exec(bContext *C, wmOperator *op)
{
	const MindMapCache *cache = mindmap_edit_cache(C);
	const bool opened = mindmap_open_link(C, op->reports, cache->selected);

	return opened ? OPERATOR_FINISHED : OPERATOR_CANCELLED;
}

static void MINDMAP_OT_open_link(wmOperatorType *ot)
{
	ot->name = "Open Link";
	ot->idname = "MINDMAP_OT_open_link";
	ot->description = "Open the object, scene or text linked to the selected idea";
	ot->exec = mindmap_open_link_exec;
	ot->poll = mindmap_edit_poll;
}

/* ---------------- image ---------------- */

static int mindmap_render_png_exec(bContext *C, wmOperator *op)
{
	ARegion *ar = BKE_area_find_region_type(CTX_wm_area(C), RGN_TYPE_WINDOW);
	ARegion *previous_region = CTX_wm_region(C);
	MindMapCache *cache = mindmap_edit_cache(C);
	const MMLayout *layout = cache->layout;
	const float margin = 24.0f;
	const float size_x = layout->xmax - layout->xmin + margin * 2.0f;
	const float size_y = layout->ymax - layout->ymin + margin * 2.0f;
	const float scale = min_fff(2.0f, 8000.0f / size_x, 8000.0f / size_y);
	const int width = max_ii((int)(size_x * scale), 1), height = max_ii((int)(size_y * scale), 1);
	const View2D saved_v2d = ar->v2d;
	const rcti saved_winrct = ar->winrct;
	const short saved_winx = ar->winx, saved_winy = ar->winy;
	MMElem *saved_selected = cache->selected;
	char filepath[FILE_MAX], error[256];
	GPUOffScreen *ofs;
	ImBuf *ibuf;
	short saved;

	RNA_string_get(op->ptr, "filepath", filepath);
	ofs = GPU_offscreen_create(width, height, 0, error);
	if (ofs == NULL) {
		BKE_reportf(op->reports, RPT_ERROR, "Could not create the image: %s", error);
		return OPERATOR_CANCELLED;
	}

	ar->v2d.cur.xmin = layout->xmin - margin;
	ar->v2d.cur.xmax = layout->xmax + margin;
	ar->v2d.cur.ymin = layout->ymin - margin;
	ar->v2d.cur.ymax = layout->ymax + margin;
	BLI_rcti_init(&ar->v2d.mask, 0, width - 1, 0, height - 1);
	BLI_rcti_init(&ar->winrct, 0, width - 1, 0, height - 1);
	ar->winx = width;
	ar->winy = height;
	cache->selected = NULL;
	CTX_wm_region_set(C, ar);
	UI_SetTheme(SPACE_MINDMAP, RGN_TYPE_WINDOW);

	glPushAttrib(GL_SCISSOR_BIT | GL_ENABLE_BIT | GL_VIEWPORT_BIT);
	glDisable(GL_SCISSOR_TEST);
	GPU_offscreen_bind(ofs, true);
	UI_ThemeClearColor(TH_BACK);
	glClear(GL_COLOR_BUFFER_BIT);
	mindmap_draw_map(C, ar, cache);
	ibuf = IMB_allocImBuf(width, height, 24, IB_rect);
	GPU_offscreen_read_pixels(ofs, GL_UNSIGNED_BYTE, ibuf->rect);
	GPU_offscreen_unbind(ofs, true);
	glPopAttrib();
	GPU_offscreen_free(ofs);

	CTX_wm_region_set(C, previous_region);
	cache->selected = saved_selected;
	ar->v2d = saved_v2d;
	ar->winrct = saved_winrct;
	ar->winx = saved_winx;
	ar->winy = saved_winy;
	ED_region_tag_redraw(ar);

	ibuf->ftype = IMB_FTYPE_PNG;
	saved = IMB_saveiff(ibuf, filepath, IB_rect);
	IMB_freeImBuf(ibuf);
	if (!saved) {
		BKE_reportf(op->reports, RPT_ERROR, "Could not save: %s", filepath);
		return OPERATOR_CANCELLED;
	}
	return OPERATOR_FINISHED;
}

static void MINDMAP_OT_render_png(wmOperatorType *ot)
{
	ot->name = "Render Map to PNG";
	ot->idname = "MINDMAP_OT_render_png";
	ot->description = "Save the whole map as a PNG image";
	ot->exec = mindmap_render_png_exec;
	ot->poll = mindmap_edit_poll;
	RNA_def_string_file_path(ot->srna, "filepath", NULL, FILE_MAX, "File Path", "");
}

/* Shift+click adds an idea to the selected group, or takes it out. */
static int mindmap_toggle_mark_invoke(bContext *C, wmOperator *UNUSED(op), const wmEvent *event)
{
	ARegion *ar = CTX_wm_region(C);
	MindMapCache *cache = mindmap_edit_cache(C);
	const int index = mindmap_hit_node(ar, cache->layout, cache->selected, event->mval, NULL, NULL);
	MMElem *node;

	if (index == -1) {
		return OPERATOR_CANCELLED | OPERATOR_PASS_THROUGH;
	}
	node = cache->layout->nodes[index].elem;
	cache->selected->marked = 1;
	if (node != cache->selected) {
		node->marked = !node->marked;
		if (node->marked) {
			cache->selected = node;
		}
	}
	mindmap_cache_rebuild_layout(cache);
	ED_region_tag_redraw(ar);
	return OPERATOR_FINISHED;
}

static void MINDMAP_OT_toggle_mark(wmOperatorType *ot)
{
	ot->name = "Add to Selection";
	ot->idname = "MINDMAP_OT_toggle_mark";
	ot->description = "Add the idea under the mouse to the selected group, or take it out";
	ot->invoke = mindmap_toggle_mark_invoke;
	ot->poll = mindmap_edit_poll;
}

/* ---------------- copy and paste ---------------- */

static int mindmap_copy_exec(bContext *C, wmOperator *UNUSED(op))
{
	const MindMapCache *cache = mindmap_edit_cache(C);
	MMDoc *holder = mm_new("Clipboard");
	char *xml;
	int count, i;
	MMElem **items = mindmap_targets(cache, true, &count);

	if (count == 0) {
		mm_node_copy_into(cache->selected, mm_root_node(holder));
	}
	for (i = 0; i < count; i++) {
		mm_node_copy_into(items[i], mm_root_node(holder));
	}
	MEM_freeN(items);
	xml = mm_write(holder, NULL);
	WM_clipboard_text_set(xml, false);
	mm_str_free(xml);
	mm_free(holder);
	return OPERATOR_FINISHED;
}

static void MINDMAP_OT_copy(wmOperatorType *ot)
{
	ot->name = "Copy Branch";
	ot->idname = "MINDMAP_OT_copy";
	ot->description = "Copy the selected idea and its branch";
	ot->exec = mindmap_copy_exec;
	ot->poll = mindmap_edit_poll;
}

static int mindmap_cut_exec(bContext *C, wmOperator *op)
{
	const MindMapCache *cache = mindmap_edit_cache(C);

	int count;

	MEM_freeN(mindmap_targets(cache, true, &count));
	if (count == 0) {
		BKE_report(op->reports, RPT_WARNING, "The central idea cannot be cut");
		return OPERATOR_CANCELLED;
	}
	mindmap_copy_exec(C, op);
	return mindmap_delete_exec(C, op);
}

static void MINDMAP_OT_cut(wmOperatorType *ot)
{
	ot->name = "Cut Branch";
	ot->idname = "MINDMAP_OT_cut";
	ot->description = "Copy the selected idea and its branch, then remove them";
	ot->exec = mindmap_cut_exec;
	ot->poll = mindmap_edit_poll;
}

/* Text that is not a map becomes one idea per line. */
static MMElem *mindmap_paste_lines(MMElem *parent, char *text)
{
	MMElem *first = NULL;
	char *line = text;

	while (line && *line) {
		char *end = line + strcspn(line, "\r\n");
		const char stop = *end;

		*end = '\0';
		if (line[strspn(line, " \t")] != '\0') {
			MMElem *node = mm_node_add_child(parent, line + strspn(line, " \t"));

			first = first ? first : node;
		}
		line = stop ? end + 1 : NULL;
	}
	return first;
}

static int mindmap_paste_exec(bContext *C, wmOperator *UNUSED(op))
{
	MindMapCache *cache = mindmap_edit_cache(C);
	MMElem *parent = cache->selected, *first = NULL, *child;
	MMElem *previous_last = NULL;
	const MMElem *root = mm_root_node(cache->doc);
	int len = 0;
	char *text = WM_clipboard_text_get(false, &len);
	MMDoc *pasted;

	if (text == NULL || len == 0) {
		if (text) {
			MEM_freeN(text);
		}
		return OPERATOR_CANCELLED;
	}
	for (child = mm_node_first_child(parent); child; child = mm_node_next(child)) {
		previous_last = child;
	}

	pasted = strstr(text, "<map") ? mm_parse(text, len, NULL, 0) : NULL;
	if (pasted && mm_root_node(pasted)) {
		const MMElem *src;

		for (src = mm_node_first_child(mm_root_node(pasted)); src; src = mm_node_next(src)) {
			MMElem *copy = mm_node_copy_into(src, parent);

			first = first ? first : copy;
		}
	}
	else {
		first = mindmap_paste_lines(parent, text);
	}
	mm_free(pasted);
	MEM_freeN(text);
	if (first == NULL) {
		return OPERATOR_CANCELLED;
	}

	for (child = previous_last ? mm_node_next(previous_last) : mm_node_first_child(parent);
	     child;
	     child = mm_node_next(child))
	{
		if (parent != root) {
			mm_attr_remove(child, "POSITION");
		}
		else {
			char *position = mm_attr_get(child, "POSITION");

			if (position == NULL) {
				mm_attr_set(child, "POSITION", "right");
			}
			mm_str_free(position);
		}
	}
	if (parent != root && mm_node_folded(parent)) {
		mm_node_folded_set(parent, 0);
	}
	cache->selected = first;
	cache->reveal = true;
	mindmap_cache_commit(cache);
	return mindmap_finish(C, "Paste Branch");
}

static void MINDMAP_OT_paste(wmOperatorType *ot)
{
	ot->name = "Paste Branch";
	ot->idname = "MINDMAP_OT_paste";
	ot->description = "Paste a copied branch, or lines of text, below the selected idea";
	ot->exec = mindmap_paste_exec;
	ot->poll = mindmap_edit_poll;
}

/* ---------------- find ---------------- */

static MMElem *mindmap_next_in_tree(MMElem *elem, MMElem *root)
{
	MMElem *child = mm_node_first_child(elem);

	if (child) {
		return child;
	}
	for (; elem != root; elem = elem->parent) {
		MMElem *next = mm_node_next(elem);

		if (next) {
			return next;
		}
	}
	return root;
}

static bool mindmap_elem_matches(const MMElem *elem, const char *query)
{
	char *text = mm_node_text(elem);
	char *note = mm_node_note(elem);
	const bool found = (text && BLI_strcasestr(text, query)) || (note && BLI_strcasestr(note, query));

	mm_str_free(text);
	mm_str_free(note);
	return found;
}

static int mindmap_find_step(bContext *C, wmOperator *op, MindMapCache *cache)
{
	MMElem *root = mm_root_node(cache->doc);
	MMElem *start = cache->selected ? cache->selected : root;
	MMElem *cur = start, *up;
	bool unfolded = false;

	if (cache->find_text[0] == '\0') {
		return OPERATOR_CANCELLED;
	}
	do {
		cur = mindmap_next_in_tree(cur, root);
		if (mindmap_elem_matches(cur, cache->find_text)) {
			for (up = cur->parent; up && up != root && up != cur; up = up->parent) {
				if (mm_node_folded(up)) {
					mm_node_folded_set(up, 0);
					unfolded = true;
				}
			}
			cache->selected = cur;
			cache->reveal = true;
			if (unfolded) {
				mindmap_cache_commit(cache);
			}
			return mindmap_finish(C, unfolded ? "Find Idea" : NULL);
		}
	} while (cur != start);

	BKE_reportf(op->reports, RPT_WARNING, "Not found: %s", cache->find_text);
	return OPERATOR_CANCELLED;
}

static int mindmap_find_invoke(bContext *C, wmOperator *op, const wmEvent *UNUSED(event))
{
	RNA_string_set(op->ptr, "text", mindmap_edit_cache(C)->find_text);
	return WM_operator_props_dialog_popup(C, op, 12 * UI_UNIT_X, UI_UNIT_Y);
}

static int mindmap_find_exec(bContext *C, wmOperator *op)
{
	MindMapCache *cache = mindmap_edit_cache(C);

	RNA_string_get(op->ptr, "text", cache->find_text);
	return mindmap_find_step(C, op, cache);
}

static void MINDMAP_OT_find(wmOperatorType *ot)
{
	PropertyRNA *prop;

	ot->name = "Find Idea";
	ot->idname = "MINDMAP_OT_find";
	ot->description = "Find an idea by its text or note, opening folded branches";
	ot->invoke = mindmap_find_invoke;
	ot->exec = mindmap_find_exec;
	ot->poll = mindmap_edit_poll;
	prop = RNA_def_string(ot->srna, "text", NULL, 256, "Text", "");
	RNA_def_property_flag(prop, PROP_SKIP_SAVE);
}

static int mindmap_find_next_exec(bContext *C, wmOperator *op)
{
	return mindmap_find_step(C, op, mindmap_edit_cache(C));
}

static void MINDMAP_OT_find_next(wmOperatorType *ot)
{
	ot->name = "Find Next";
	ot->idname = "MINDMAP_OT_find_next";
	ot->description = "Go to the next idea matching the last search";
	ot->exec = mindmap_find_next_exec;
	ot->poll = mindmap_edit_poll;
}

static int mindmap_context_menu_invoke(bContext *C, wmOperator *UNUSED(op), const wmEvent *event)
{
	ARegion *ar = CTX_wm_region(C);
	MindMapCache *cache = mindmap_edit_cache(C);
	const int index = mindmap_hit_node(ar, cache->layout, cache->selected, event->mval, NULL, NULL);
	uiPopupMenu *pup;
	uiLayout *layout;

	if (index == -1) {
		return OPERATOR_CANCELLED | OPERATOR_PASS_THROUGH;
	}
	cache->selected = cache->layout->nodes[index].elem;
	ED_region_tag_redraw(ar);

	pup = UI_popup_menu_begin(C, "Idea", ICON_NONE);
	layout = UI_popup_menu_layout(pup);
	uiLayoutSetOperatorContext(layout, WM_OP_EXEC_REGION_WIN);
	uiItemO(layout, "Add Child", ICON_NONE, "MINDMAP_OT_add_child");
	uiItemO(layout, "Add Sibling", ICON_NONE, "MINDMAP_OT_add_sibling");
	uiItemO(layout, "Edit", ICON_NONE, "MINDMAP_OT_edit");
	uiItemS(layout);
	uiItemMenuEnumO(layout, C, "MINDMAP_OT_set_color", "color", "Color", ICON_NONE);
	uiItemMenuEnumO(layout, C, "MINDMAP_OT_set_icon", "icon", "Icon", ICON_NONE);
	uiLayoutSetOperatorContext(layout, WM_OP_INVOKE_REGION_WIN);
	uiItemO(layout, "Note...", ICON_NONE, "MINDMAP_OT_edit_note");
	uiItemO(layout, "Engine Icon...", ICON_NONE, "MINDMAP_OT_set_engine_icon");
	uiItemO(layout, "Link...", ICON_NONE, "MINDMAP_OT_set_link");
	uiLayoutSetOperatorContext(layout, WM_OP_EXEC_REGION_WIN);
	uiItemO(layout, "Open Link", ICON_NONE, "MINDMAP_OT_open_link");
	uiItemO(layout, "Clear Link", ICON_NONE, "MINDMAP_OT_clear_link");
	uiItemO(layout, "Task", ICON_NONE, "MINDMAP_OT_cycle_task");
	uiItemS(layout);
	uiItemO(layout, "Copy", ICON_NONE, "MINDMAP_OT_copy");
	uiItemO(layout, "Cut", ICON_NONE, "MINDMAP_OT_cut");
	uiItemO(layout, "Paste", ICON_NONE, "MINDMAP_OT_paste");
	uiItemS(layout);
	uiItemO(layout, "Fold or Unfold", ICON_NONE, "MINDMAP_OT_toggle_fold");
	uiItemO(layout, "Delete", ICON_NONE, "MINDMAP_OT_delete");
	UI_popup_menu_end(C, pup);
	return OPERATOR_INTERFACE;
}

static void MINDMAP_OT_context_menu(wmOperatorType *ot)
{
	ot->name = "Idea Menu";
	ot->idname = "MINDMAP_OT_context_menu";
	ot->description = "Open the menu of the idea under the mouse";
	ot->invoke = mindmap_context_menu_invoke;
	ot->poll = mindmap_edit_poll;
}

enum { MOVE_LEFT, MOVE_RIGHT, MOVE_UP, MOVE_DOWN };

static int mindmap_node_depth(const MMLayout *layout, int index)
{
	int depth = 0;

	while (layout->nodes[index].parent != -1) {
		index = layout->nodes[index].parent;
		depth++;
	}
	return depth;
}

static int mindmap_first_child_on_side(const MMLayout *layout, int index, int side)
{
	int i;

	for (i = index + 1; i < layout->count; i++) {
		if (layout->nodes[i].parent == index && layout->nodes[i].side == side) {
			return i;
		}
	}
	return -1;
}

/* Closest node of the same column above (dir 1) or below (dir -1). */
static int mindmap_vertical_neighbor(const MMLayout *layout, int index, int dir)
{
	const MMLayoutNode *from = &layout->nodes[index];
	const int depth = mindmap_node_depth(layout, index);
	float best = FLT_MAX;
	int i, found = -1;

	for (i = 1; i < layout->count; i++) {
		const MMLayoutNode *node = &layout->nodes[i];
		const float distance = (node->ymin - from->ymin) * dir;

		if (i != index && node->side == from->side && distance > 0.0f && distance < best &&
		    mindmap_node_depth(layout, i) == depth)
		{
			best = distance;
			found = i;
		}
	}
	return found;
}

static int mindmap_select_move_exec(bContext *C, wmOperator *op)
{
	MindMapCache *cache = mindmap_edit_cache(C);
	const MMLayout *layout = cache->layout;
	const int index = mindmap_layout_find(layout, cache->selected);
	const int direction = RNA_enum_get(op->ptr, "direction");
	int target = -1;

	if (index == -1) {
		return OPERATOR_CANCELLED;
	}

	if (direction == MOVE_UP || direction == MOVE_DOWN) {
		if (index != 0) {
			target = mindmap_vertical_neighbor(layout, index, direction == MOVE_UP ? 1 : -1);
		}
	}
	else {
		const int side = (direction == MOVE_RIGHT) ? 1 : -1;

		if (layout->nodes[index].side == -side) {
			target = layout->nodes[index].parent;
		}
		else {
			target = mindmap_first_child_on_side(layout, index, side);
		}
	}

	if (target == -1) {
		return OPERATOR_CANCELLED;
	}
	cache->selected = layout->nodes[target].elem;
	cache->reveal = true;
	return mindmap_finish(C, NULL);
}

static void MINDMAP_OT_select_move(wmOperatorType *ot)
{
	static const EnumPropertyItem direction_items[] = {
		{MOVE_LEFT, "LEFT", 0, "Left", ""},
		{MOVE_RIGHT, "RIGHT", 0, "Right", ""},
		{MOVE_UP, "UP", 0, "Up", ""},
		{MOVE_DOWN, "DOWN", 0, "Down", ""},
		{0, NULL, 0, NULL, NULL},
	};

	ot->name = "Select Neighbor";
	ot->idname = "MINDMAP_OT_select_move";
	ot->description = "Select the neighbor idea in a direction";
	ot->exec = mindmap_select_move_exec;
	ot->poll = mindmap_edit_poll;

	RNA_def_enum(ot->srna, "direction", direction_items, MOVE_RIGHT, "Direction", "");
}

static void MINDMAP_OT_view_all(wmOperatorType *ot)
{
	ot->name = "View All";
	ot->idname = "MINDMAP_OT_view_all";
	ot->description = "Fit the whole map in the view";

	ot->exec = mindmap_view_all_exec;
	ot->poll = mindmap_poll;
}

static void mindmap_operatortypes(void)
{
	WM_operatortype_append(MINDMAP_OT_view_all);
	WM_operatortype_append(MINDMAP_OT_add_child);
	WM_operatortype_append(MINDMAP_OT_add_sibling);
	WM_operatortype_append(MINDMAP_OT_edit);
	WM_operatortype_append(MINDMAP_OT_delete);
	WM_operatortype_append(MINDMAP_OT_toggle_fold);
	WM_operatortype_append(MINDMAP_OT_select_move);
	WM_operatortype_append(MINDMAP_OT_click);
	WM_operatortype_append(MINDMAP_OT_set_color);
	WM_operatortype_append(MINDMAP_OT_set_icon);
	WM_operatortype_append(MINDMAP_OT_edit_note);
	WM_operatortype_append(MINDMAP_OT_context_menu);
	WM_operatortype_append(MINDMAP_OT_cycle_task);
	WM_operatortype_append(MINDMAP_OT_render_png);
	WM_operatortype_append(MINDMAP_OT_toggle_mark);
	WM_operatortype_append(MINDMAP_OT_copy);
	WM_operatortype_append(MINDMAP_OT_cut);
	WM_operatortype_append(MINDMAP_OT_paste);
	WM_operatortype_append(MINDMAP_OT_find);
	WM_operatortype_append(MINDMAP_OT_find_next);
	WM_operatortype_append(MINDMAP_OT_set_engine_icon);
	WM_operatortype_append(MINDMAP_OT_set_link);
	WM_operatortype_append(MINDMAP_OT_clear_link);
	WM_operatortype_append(MINDMAP_OT_open_link);
}

static void mindmap_keymap(wmKeyConfig *keyconf)
{
	wmKeyMap *keymap = WM_keymap_ensure(keyconf, "Mind Map", SPACE_MINDMAP, 0);

	WM_keymap_add_item(keymap, "MINDMAP_OT_view_all", HOMEKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_view_all", NDOF_BUTTON_FIT, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_edit", LEFTMOUSE, KM_DBL_CLICK, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_click", LEFTMOUSE, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_toggle_mark", LEFTMOUSE, KM_PRESS, KM_SHIFT, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_context_menu", RIGHTMOUSE, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_edit_note", NKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_cycle_task", TKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_copy", CKEY, KM_PRESS, KM_CTRL, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_cut", XKEY, KM_PRESS, KM_CTRL, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_paste", VKEY, KM_PRESS, KM_CTRL, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_find", FKEY, KM_PRESS, KM_CTRL, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_find_next", F3KEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_set_engine_icon", IKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_set_link", LKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_open_link", OKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_add_child", INSERTKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_add_sibling", RETKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_add_sibling", PADENTER, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_edit", F2KEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_delete", DELKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_toggle_fold", SPACEKEY, KM_PRESS, 0, 0);
	RNA_enum_set(WM_keymap_add_item(keymap, "MINDMAP_OT_select_move", LEFTARROWKEY, KM_PRESS, 0, 0)->ptr, "direction", MOVE_LEFT);
	RNA_enum_set(WM_keymap_add_item(keymap, "MINDMAP_OT_select_move", RIGHTARROWKEY, KM_PRESS, 0, 0)->ptr, "direction", MOVE_RIGHT);
	RNA_enum_set(WM_keymap_add_item(keymap, "MINDMAP_OT_select_move", UPARROWKEY, KM_PRESS, 0, 0)->ptr, "direction", MOVE_UP);
	RNA_enum_set(WM_keymap_add_item(keymap, "MINDMAP_OT_select_move", DOWNARROWKEY, KM_PRESS, 0, 0)->ptr, "direction", MOVE_DOWN);
}

static void mindmap_header_region_init(wmWindowManager *UNUSED(wm), ARegion *ar)
{
	ED_region_header_init(ar);
}

static void mindmap_header_region_draw(const bContext *C, ARegion *ar)
{
	ED_region_header(C, ar);
}

/* only called once, from space/spacetypes.c */
void ED_spacetype_mindmap(void)
{
	SpaceType *st = MEM_callocN(sizeof(SpaceType), "spacetype mind map");
	ARegionType *art;

	st->spaceid = SPACE_MINDMAP;
	strncpy(st->name, "MindMap", BKE_ST_MAXNAME);

	st->new = mindmap_new;
	st->free = mindmap_free;
	st->init = mindmap_init;
	st->duplicate = mindmap_duplicate;
	st->id_remap = mindmap_id_remap;
	st->operatortypes = mindmap_operatortypes;
	st->keymap = mindmap_keymap;

	art = MEM_callocN(sizeof(ARegionType), "spacetype mind map region");
	art->regionid = RGN_TYPE_WINDOW;
	art->keymapflag = ED_KEYMAP_UI | ED_KEYMAP_VIEW2D;
	art->init = mindmap_main_region_init;
	art->draw = mindmap_main_region_draw;
	art->listener = mindmap_main_region_listener;
	BLI_addhead(&st->regiontypes, art);

	art = MEM_callocN(sizeof(ARegionType), "spacetype mind map header");
	art->regionid = RGN_TYPE_HEADER;
	art->prefsizey = HEADERY;
	art->keymapflag = ED_KEYMAP_UI | ED_KEYMAP_VIEW2D | ED_KEYMAP_HEADER;
	art->init = mindmap_header_region_init;
	art->draw = mindmap_header_region_draw;
	BLI_addhead(&st->regiontypes, art);

	BKE_spacetype_register(st);
}
