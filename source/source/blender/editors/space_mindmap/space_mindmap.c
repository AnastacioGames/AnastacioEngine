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
#include "BKE_screen.h"
#include "BKE_text.h"

#include "BLF_api.h"

#include "ED_screen.h"
#include "ED_space_api.h"

#include "BIF_gl.h"
#include "BIF_glutil.h"

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

/* Parsed state of a map. The Text is the source of truth and is compared on every
 * redraw, which covers undo, file reload and edits made in the Text Editor. */
typedef struct MindMapCache {
	struct MindMapCache *next, *prev;
	const SpaceMindMap *smm;
	const Text *text;
	char *buffer;
	MMLayout *layout;
	char error[128];
	bool fit_view;
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
	cache->error[0] = '\0';
}

static void mindmap_cache_parse(MindMapCache *cache)
{
	const char *c = cache->buffer;
	MMDoc *doc;

	while (*c == ' ' || *c == '\t' || *c == '\r' || *c == '\n') {
		c++;
	}
	if (*c == '\0') {
		BLI_strncpy(cache->error, "The text is empty", sizeof(cache->error));
		return;
	}

	doc = mm_parse(cache->buffer, strlen(cache->buffer), cache->error, sizeof(cache->error));
	if (doc) {
		cache->layout = mm_layout_build(doc, mindmap_text_width, NULL);
		mm_free(doc);
	}
}

static MindMapCache *mindmap_cache_get(const SpaceMindMap *smm)
{
	MindMapCache *cache = BLI_findptr(&mindmap_caches, smm, offsetof(MindMapCache, smm));
	char *buffer;

	if (cache == NULL) {
		cache = MEM_callocN(sizeof(*cache), "MindMapCache");
		cache->smm = smm;
		BLI_addtail(&mindmap_caches, cache);
	}

	if (cache->text != smm->text) {
		cache->text = smm->text;
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

	mindmap_cache_clear_contents(cache);
	cache->buffer = buffer;
	mindmap_cache_parse(cache);
	return cache;
}

static void mindmap_view_fit(ARegion *ar, const MMLayout *layout)
{
	View2D *v2d = &ar->v2d;

	BLI_rctf_init(&v2d->cur,
	              layout->xmin - FIT_MARGIN, layout->xmax + FIT_MARGIN,
	              layout->ymin - FIT_MARGIN, layout->ymax + FIT_MARGIN);
	UI_view2d_curRect_validate(v2d);
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

static void mindmap_draw_boxes(const MMLayout *layout, const rctf *cur)
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
		UI_ThemeColorShade(TH_TEXT, -40);
		fdrawbox(node->xmin, node->ymin, node->xmax, node->ymax);

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
		mindmap_view_fit(ar, cache->layout);
	}

	UI_view2d_view_ortho(&ar->v2d);
	glEnable(GL_BLEND);
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
	glEnable(GL_LINE_SMOOTH);
	mindmap_draw_links(cache->layout, &ar->v2d.cur);
	mindmap_draw_boxes(cache->layout, &ar->v2d.cur);
	glDisable(GL_LINE_SMOOTH);
	glDisable(GL_BLEND);
	UI_view2d_view_restore(C);

	mindmap_draw_texts(cache->layout, ar);
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
}

static void mindmap_keymap(wmKeyConfig *keyconf)
{
	wmKeyMap *keymap = WM_keymap_ensure(keyconf, "Mind Map", SPACE_MINDMAP, 0);

	WM_keymap_add_item(keymap, "MINDMAP_OT_view_all", HOMEKEY, KM_PRESS, 0, 0);
	WM_keymap_add_item(keymap, "MINDMAP_OT_view_all", NDOF_BUTTON_FIT, KM_PRESS, 0, 0);
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
