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
#include <string.h>

#include "MEM_guardedalloc.h"

#include "BLI_blenlib.h"
#include "BLI_math_base.h"
#include "BLI_utildefines.h"

#include "DNA_screen_types.h"
#include "DNA_space_types.h"
#include "DNA_text_types.h"
#include "DNA_userdef_types.h"
#include "DNA_windowmanager_types.h"

#include "BKE_context.h"
#include "BKE_report.h"
#include "BKE_screen.h"
#include "BKE_text.h"

#include "BLF_api.h"

#include "ED_screen.h"
#include "ED_space_api.h"
#include "ED_undo.h"

#include "BIF_gl.h"
#include "BIF_glutil.h"

#include "RNA_access.h"
#include "RNA_define.h"

#include "WM_api.h"
#include "WM_keymap.h"
#include "WM_types.h"

#include "UI_interface.h"
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
} MindMapCache;

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
		else {
			UI_ThemeColorShade(TH_TEXT, -40);
			fdrawbox(node->xmin, node->ymin, node->xmax, node->ymax);
		}
		UI_ThemeColorShade(TH_TEXT, -40);

		if (node->has_hidden_children) {
			const float x = (node->side > 0) ? node->xmax + FOLD_MARK_SIZE : node->xmin - FOLD_MARK_SIZE;
			const float y = (node->ymin + node->ymax) * 0.5f;

			fdrawbox(x - FOLD_MARK_SIZE, y - FOLD_MARK_SIZE, x + FOLD_MARK_SIZE, y + FOLD_MARK_SIZE);
			fdrawline(x - FOLD_MARK_SIZE * 0.6f, y, x + FOLD_MARK_SIZE * 0.6f, y);
			fdrawline(x, y - FOLD_MARK_SIZE * 0.6f, x, y + FOLD_MARK_SIZE * 0.6f);
		}
	}
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
	UI_ThemeColor(TH_TEXT);
	for (i = 0; i < layout->count; i++) {
		const MMLayoutNode *node = &layout->nodes[i];

		if (mindmap_rect_visible(cur, node->xmin, node->xmax, node->ymin, node->ymax)) {
			const float width = BLF_width(font, node->text, BLF_DRAW_STR_DUMMY_MAX);
			const float center_x = ((node->xmin + node->xmax) * 0.5f - cur->xmin) * scale;
			const float center_y = ((node->ymin + node->ymax) * 0.5f - cur->ymin) * scale;

			BLF_position(font, floorf(center_x - width * 0.5f), floorf(center_y - pixels * 0.35f), 0.0f);
			BLF_draw(font, node->text, BLF_DRAW_STR_DUMMY_MAX);
		}
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

	UI_view2d_view_ortho(&ar->v2d);
	glEnable(GL_BLEND);
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
	glEnable(GL_LINE_SMOOTH);
	mindmap_draw_links(cache->layout, &ar->v2d.cur);
	mindmap_draw_boxes(cache->layout, &ar->v2d.cur, cache->selected);
	glDisable(GL_LINE_SMOOTH);
	glDisable(GL_BLEND);
	UI_view2d_view_restore(C);

	mindmap_draw_texts(cache->layout, ar);

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

static void MINDMAP_OT_edit(wmOperatorType *ot)
{
	ot->name = "Edit Idea";
	ot->idname = "MINDMAP_OT_edit";
	ot->description = "Type a new text for the selected idea";
	ot->exec = mindmap_edit_exec;
	ot->poll = mindmap_edit_poll;
}

static int mindmap_delete_exec(bContext *C, wmOperator *UNUSED(op))
{
	MindMapCache *cache = mindmap_edit_cache(C);
	MMElem *node = cache->selected;
	MMElem *next, *other, *previous = NULL;

	if (node == mm_root_node(cache->doc)) {
		return OPERATOR_CANCELLED;
	}
	for (other = mm_node_first_child(node->parent); other != node; other = mm_node_next(other)) {
		previous = other;
	}
	next = mm_node_next(node);
	cache->selected = next ? next : (previous ? previous : node->parent);
	mm_node_remove(node);
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
}

static void mindmap_keymap(wmKeyConfig *keyconf)
{
	wmKeyMap *keymap = WM_keymap_ensure(keyconf, "Mind Map", SPACE_MINDMAP, 0);

	WM_keymap_add_item(keymap, "MINDMAP_OT_view_all", HOMEKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_view_all", NDOF_BUTTON_FIT, KM_PRESS, 0, 0);
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
