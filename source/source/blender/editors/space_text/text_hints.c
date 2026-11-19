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

/** \file blender/editors/space_text/text_hints.c
 *  \ingroup sptext
 *
 * Range: code hints of the Text Editor (Python texts only).
 * - Live diagnostics: syntax errors (compile) and pyflakes warnings, checked after a pause in
 *   the typing, underlined in the text with the message at the end of the line.
 * - Signature box: the parameters of the call around the cursor (the current one highlighted),
 *   opened by typing '(' or ',' (or Ctrl+Shift+Space), closed by leaving the call or Esc.
 * - Detail box: signature + description of the item selected in the completion list.
 * The analysis is in python (text_autocomplete.py: diagnosticos/assinatura/detalhe); nothing of
 * the user script runs. This file caches the answers, schedules the pause and draws.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "MEM_guardedalloc.h"

#include "DNA_screen_types.h"
#include "DNA_space_types.h"
#include "DNA_text_types.h"
#include "DNA_userdef_types.h"
#include "DNA_windowmanager_types.h"

#include "BLI_blenlib.h"
#include "BLI_math_base.h"
#include "BLI_string_utf8.h"
#include "BLI_utildefines.h"

#include "PIL_time.h"

#include "BKE_context.h"
#include "BKE_report.h"
#include "BKE_suggestions.h"
#include "BKE_text.h"

#include "BIF_gl.h"
#include "BLF_api.h"

#include "ED_screen.h"
#include "ED_text.h"

#include "UI_interface.h"
#include "UI_resources.h"

#include "WM_api.h"
#include "WM_types.h"

#ifdef WITH_PYTHON
#include "BPY_extern.h"
#endif

#include "text_format.h"
#include "text_intern.h"  /* own include */

/* pause in the typing before checking the text again (seconds) */
#define HINTS_DELAY 0.8
#define HINTS_TIMER_STEP 0.2

#define DIAG_MAX 100
#define DIAG_MSG_LEN 200
#define DIAG_CACHE_SIZE 4

#define HINT_LINES 9
#define HINT_LINE_LEN 400

typedef struct TextDiag {
	int line;       /* line index */
	int b0, b1;     /* byte range in the line */
	char sev;       /* 'e' error, 'w' warning */
	char msg[DIAG_MSG_LEN];
} TextDiag;

typedef struct DiagCache {
	const Text *text;     /* only compared */
	bool computed;
	unsigned int hash;    /* text content the diagnostics belong to */
	unsigned int cur_hash;
	unsigned int seen_hash;  /* content at the previous draw: a change there is an edit */
	bool seen;
	double last_edit;
	double delay;         /* pause before checking (longer when the check is slow) */
	double used_time;
	int tot;
	TextDiag items[DIAG_MAX];
} DiagCache;

/* static storage: nothing to free at exit */
static DiagCache diag_cache[DIAG_CACHE_SIZE];
static wmTimer *hints_timer = NULL;

static struct {
	const Text *text;
	bool active;          /* following the call around the cursor */
	bool has;             /* there is a box to draw */
	bool key_valid;
	const TextLine *key_line;
	int key_curc;
	unsigned int key_hash;
	char before[HINT_LINE_LEN], current[HINT_LINE_LEN], after[HINT_LINE_LEN];
	int totdoc;
	char doc[HINT_LINES][HINT_LINE_LEN];
} sig = {NULL};

static struct {
	int generation;
	char name[128];
	bool has;
	int tot;
	char lines[HINT_LINES][HINT_LINE_LEN];
} detail = {-1};

/* -------------------------------------------------------------------- */
/* helpers */

static unsigned int text_content_hash(const Text *text)
{
	const TextLine *l;
	unsigned int h = 2166136261u;
	int i;
	for (l = text->lines.first; l; l = l->next) {
		for (i = 0; i < l->len; i++) {
			h ^= (unsigned char)l->line[i];
			h *= 16777619u;
		}
		h ^= '\n';
		h *= 16777619u;
	}
	return h;
}

static DiagCache *diag_cache_get(const Text *text, bool create)
{
	int i, oldest = 0;
	for (i = 0; i < DIAG_CACHE_SIZE; i++) {
		if (diag_cache[i].text == text) return &diag_cache[i];
	}
	if (!create) return NULL;
	for (i = 1; i < DIAG_CACHE_SIZE; i++) {
		if (diag_cache[i].used_time < diag_cache[oldest].used_time) oldest = i;
	}
	diag_cache[oldest].text = text;
	diag_cache[oldest].computed = false;
	diag_cache[oldest].tot = 0;
	diag_cache[oldest].last_edit = 0.0;
	diag_cache[oldest].seen = false;
	diag_cache[oldest].delay = HINTS_DELAY;
	return &diag_cache[oldest];
}

/* "OK\n..." from text_autocomplete.<expr>, or NULL (SKIP/failure). MEM_freeN the result. */
static char *hints_python(bContext *C, const char *expr)
{
#ifdef WITH_PYTHON
	static bool reported = false;
	const char *imports[] = {"text_autocomplete", NULL};
	char *result = NULL;
	if (!BPY_execute_string_as_string(C, imports, expr, !reported, &result)) {
		if (!reported) {
			printf("Text hints: python provider failed (%s)\n", expr);
			reported = true;
		}
		if (result) MEM_freeN(result);
		return NULL;
	}
	if (result && !STRPREFIX(result, "OK")) {
		MEM_freeN(result);
		return NULL;
	}
	return result;
#else
	UNUSED_VARS(C, expr);
	return NULL;
#endif
}

/* Splits "OK\nline1\nline2..." in place: returns the lines after "OK" (at most max). */
static int hints_split_lines(char *result, char **r_lines, int max)
{
	int tot = 0;
	char *line = strchr(result, '\n');
	while (line && tot < max) {
		char *next;
		line++;
		next = strchr(line, '\n');
		if (next) *next = '\0';
		r_lines[tot++] = line;
		line = next;
	}
	return tot;
}

/* The window manager is replaced on file load (its timers go with it) and the address may be
 * reused by another timer: only ours is touched. */
static bool hints_timer_is_ours(wmWindowManager *wm)
{
	const wmTimer *wt = hints_timer;
	return wt && wm && BLI_findindex(&wm->timers, wt) != -1 && wt->event_type == TIMERNOTIFIER &&
	       POINTER_AS_UINT(wt->customdata) == (NC_TEXT | ND_DISPLAY) && wt->timestep == HINTS_TIMER_STEP;
}

static void hints_timer_ensure(bContext *C)
{
	wmWindowManager *wm = CTX_wm_manager(C);
	if (!wm) return;
	if (!hints_timer_is_ours(wm)) hints_timer = NULL;
	if (!hints_timer) {
		/* a notifier, not an event: redraws the text editors, which check the pause */
		hints_timer = WM_event_add_timer_notifier(wm, NULL, NC_TEXT | ND_DISPLAY, HINTS_TIMER_STEP);
	}
}

static void hints_timer_stop(bContext *C)
{
	wmWindowManager *wm = CTX_wm_manager(C);
	if (hints_timer_is_ours(wm)) {
		WM_event_remove_timer(wm, NULL, hints_timer);
	}
	hints_timer = NULL;
}

static int utf8_columns(const char *str)
{
	return (int)BLI_strlen_utf8(str);
}

/* -------------------------------------------------------------------- */
/* update (region draw, before drawing: python needs the context) */

static void diag_compute(bContext *C, DiagCache *dc)
{
	char *result, *lines[DIAG_MAX + 1];
	int tot, i;

	dc->tot = 0;
	dc->hash = dc->cur_hash;
	dc->computed = true;  /* also on failure: no retry on every redraw */

	result = hints_python(C, "text_autocomplete.diagnosticos()");
	if (!result) return;

	tot = hints_split_lines(result, lines, DIAG_MAX);
	for (i = 0; i < tot; i++) {
		/* <e|w>\t<line>\t<b0>\t<b1>\t<message> */
		TextDiag *d = &dc->items[dc->tot];
		char *p = lines[i], *end;
		if (!(p[0] == 'e' || p[0] == 'w') || p[1] != '\t') continue;
		d->sev = p[0];
		p += 2;
		d->line = (int)strtol(p, &end, 10);
		if (*end != '\t') continue;
		d->b0 = (int)strtol(end + 1, &end, 10);
		if (*end != '\t') continue;
		d->b1 = (int)strtol(end + 1, &end, 10);
		if (*end != '\t') continue;
		BLI_strncpy_utf8(d->msg, end + 1, sizeof(d->msg));
		if (d->line < 0 || d->b0 < 0 || d->b1 < d->b0) continue;
		dc->tot++;
	}
	MEM_freeN(result);
}

static void hints_diagnostics_update(bContext *C, SpaceText *st, Text *text, double now)
{
	DiagCache *dc;

	if (st->flags & ST_NO_LIVE_DIAGNOSTICS) return;

	dc = diag_cache_get(text, true);
	dc->used_time = now;
	dc->cur_hash = text_content_hash(text);
	/* changed since the last draw: an edit by any operator (typing, paste, undo, replace,
	 * reload...); a text shown for the first time is checked right away */
	if (!dc->seen || dc->cur_hash != dc->seen_hash) {
		if (dc->seen) dc->last_edit = now;
		dc->seen = true;
		dc->seen_hash = dc->cur_hash;
	}
	if (dc->computed && dc->cur_hash == dc->hash) return;

	if (now - dc->last_edit < dc->delay) {
		hints_timer_ensure(C);  /* still typing: check after the pause */
		return;
	}
	{
		const double t0 = PIL_check_seconds_timer();
		diag_compute(C, dc);
		/* a slow check (big text) waits longer for the next pause */
		dc->delay = MIN2(HINTS_DELAY + 3.0 * (PIL_check_seconds_timer() - t0), 3.0);
	}
}

/* some text still waiting for its pause (expires: a hidden editor never checks) */
static bool hints_diag_pending(double now)
{
	int i;
	for (i = 0; i < DIAG_CACHE_SIZE; i++) {
		const DiagCache *dc = &diag_cache[i];
		if (dc->text && (!dc->computed || dc->hash != dc->cur_hash) && now - dc->last_edit < dc->delay + 2.0) {
			return true;
		}
	}
	return false;
}

static void hints_signature_update(bContext *C, SpaceText *st, Text *text)
{
	char expr[96], *result, *lines[3 + HINT_LINES];
	unsigned int hash;
	int tot, i;

	if (sig.text != text) {
		sig.active = sig.has = false;
		return;
	}
	if (!sig.active) return;

	hash = text_content_hash(text);
	if (sig.key_valid && sig.key_line == text->curl && sig.key_curc == text->curc && sig.key_hash == hash) {
		return;
	}
	sig.key_valid = true;
	sig.key_line = text->curl;
	sig.key_curc = text->curc;
	sig.key_hash = hash;

	BLI_snprintf(expr, sizeof(expr), "text_autocomplete.assinatura(%d, %d)",
	             BLI_findindex(&text->lines, text->curl), text->curc);
	result = hints_python(C, expr);
	if (!result) {
		/* left the call (or nothing known about it): the box closes until the next '(' */
		sig.active = sig.has = false;
		ED_area_tag_redraw(CTX_wm_area(C));
		return;
	}
	tot = hints_split_lines(result, lines, ARRAY_SIZE(lines));
	if (tot < 3) {
		sig.active = sig.has = false;
		MEM_freeN(result);
		return;
	}
	BLI_strncpy_utf8(sig.before, lines[0], sizeof(sig.before));
	BLI_strncpy_utf8(sig.current, lines[1], sizeof(sig.current));
	BLI_strncpy_utf8(sig.after, lines[2], sizeof(sig.after));
	sig.totdoc = 0;
	for (i = 3; i < tot && sig.totdoc < HINT_LINES; i++) {
		BLI_strncpy_utf8(sig.doc[sig.totdoc++], lines[i], HINT_LINE_LEN);
	}
	sig.has = true;
	MEM_freeN(result);
}

static bool hint_name_is_identifier(const char *name)
{
	const unsigned char *p = (const unsigned char *)name;
	if (!*p) return false;
	for (; *p; p++) {
		if (!(*p == '_' || (*p >= '0' && *p <= '9') || (*p >= 'a' && *p <= 'z') ||
		      (*p >= 'A' && *p <= 'Z') || *p >= 0x80))
		{
			return false;
		}
	}
	return true;
}

static void hints_detail_update(bContext *C, Text *text)
{
	SuggItem *sel;
	int generation;
	char expr[192], *result, *lines[HINT_LINES];
	int tot, i;

	if (!text_autocomplete_list_from_python(&generation) || !texttool_text_is_active(text)) {
		detail.has = false;
		detail.generation = -1;
		return;
	}
	sel = texttool_suggest_selected();
	if (!sel || !hint_name_is_identifier(sel->name) || strlen(sel->name) >= sizeof(detail.name)) {
		detail.has = false;
		return;
	}
	if (detail.generation == generation && STREQ(detail.name, sel->name)) return;
	detail.generation = generation;
	BLI_strncpy(detail.name, sel->name, sizeof(detail.name));
	detail.has = false;

	BLI_snprintf(expr, sizeof(expr), "text_autocomplete.detalhe(\"%s\")", sel->name);
	result = hints_python(C, expr);
	if (!result) return;
	tot = hints_split_lines(result, lines, HINT_LINES);
	detail.tot = 0;
	for (i = 0; i < tot; i++) {
		BLI_strncpy_utf8(detail.lines[detail.tot++], lines[i], HINT_LINE_LEN);
	}
	detail.has = detail.tot > 0;
	MEM_freeN(result);
}

void text_hints_update(const bContext *C_const, SpaceText *st, ARegion *UNUSED(ar))
{
	bContext *C = (bContext *)C_const;
	Text *text = st->text;
	const double now = PIL_check_seconds_timer();

	if (text && text->curl && text_is_python(text)) {
		hints_diagnostics_update(C, st, text, now);
		hints_signature_update(C, st, text);
		hints_detail_update(C, text);
	}
	if (hints_timer && !hints_diag_pending(now)) hints_timer_stop(C);
}

void text_hints_after_edit(bContext *C, SpaceText *st, Text *text, unsigned int inserted)
{
	DiagCache *dc;

	if (!text_is_python(text)) return;

	dc = diag_cache_get(text, true);
	dc->last_edit = PIL_check_seconds_timer();
	if (!(st->flags & ST_NO_LIVE_DIAGNOSTICS)) hints_timer_ensure(C);

	if ((inserted == '(' || inserted == ',') && !(st->flags & ST_NO_LIVE_AUTOCOMPLETE)) {
		sig.text = text;
		sig.active = true;
		sig.key_valid = false;
	}
}

/* -------------------------------------------------------------------- */
/* drawing */

static void diag_color(char sev, unsigned char alpha)
{
	if (sev == 'e') glColor4ub(240, 80, 70, alpha);
	else glColor4ub(230, 180, 50, alpha);
}

static void draw_squiggle(int x0, int x1, int y)
{
	const int step = max_ii(2, (int)(2 * U.pixelsize));
	int x;
	bool up = false;
	glBegin(GL_LINE_STRIP);
	for (x = x0; x <= x1; x += step) {
		glVertex2i(x, up ? y + step / 2 : y - step / 2);
		up = !up;
	}
	glEnd();
}

void text_hints_draw_diagnostics(const SpaceText *st, ARegion *ar)
{
	Text *text = st->text;
	DiagCache *dc;
	const int lheight = st->lheight_dpi + TXT_LINE_SPACING;
	const int xbase = st->showlinenrs ? TXT_OFFSET + TEXTXLOC : TXT_OFFSET;
	const int xmax = ar->winx - TXT_SCROLL_WIDTH;
	TextLine *linep;
	int lineidx, i, pass;
	int last_msg_line = -1;
	bool stale;

	if (!text || (st->flags & ST_NO_LIVE_DIAGNOSTICS) || !text_is_python(text)) return;
	dc = diag_cache_get(text, false);
	if (!dc || !dc->computed || dc->tot == 0) return;
	/* typed since the check: the positions of the cursor line are outdated, the others mostly not */
	stale = dc->hash != dc->cur_hash;

	glEnable(GL_BLEND);
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
	glLineWidth(max_ff(1.0f, U.pixelsize));

	/* warnings first: an error on the same line draws over them */
	for (pass = 0; pass < 2; pass++) {
		const char want = pass == 0 ? 'w' : 'e';
		linep = text->lines.first;
		lineidx = 0;
		for (i = 0; i < dc->tot; i++) {
			const TextDiag *d = &dc->items[i];
			int offl, offc, offl1, offc1, viewl, x0, x1, ytop, ybase, b0, b1;

			while (linep && lineidx < d->line) {
				linep = linep->next;
				lineidx++;
			}
			if (!linep) break;
			if (d->sev != want) continue;
			if (stale && linep == text->curl) continue;
			/* below the view (wrapped lines only take more rows, never fewer) */
			if (lineidx - st->top >= st->viewlines) break;
			if (!st->wordwrap && lineidx < st->top) continue;

			b0 = min_ii(d->b0, linep->len);
			b1 = min_ii(d->b1, linep->len);
			wrap_offset(st, ar, linep, b0, &offl, &offc);
			viewl = lineidx - st->top + offl;
			if (viewl < 0 || viewl >= st->viewlines) continue;

			ytop = ar->winy - viewl * lheight;
			ybase = ytop - st->lheight_dpi;

			x0 = xbase + (text_get_char_pos(st, linep->line, b0) - st->left + offc) * st->cwidth;
			wrap_offset(st, ar, linep, b1, &offl1, &offc1);
			if (offl1 != offl) {
				x1 = xmax;
			}
			else {
				x1 = xbase + (text_get_char_pos(st, linep->line, b1) - st->left + offc1) * st->cwidth;
			}
			if (x1 <= x0) x1 = x0 + st->cwidth;
			x0 = max_ii(x0, xbase);
			x1 = min_ii(x1, xmax);

			diag_color(d->sev, 255);
			if (x1 > x0) {
				draw_squiggle(x0, x1, ybase - max_ii(2, st->lheight_dpi / 5));
			}

			/* mark in the line numbers column */
			if (st->showlinenrs) {
				int offl_line, offc_line;
				wrap_offset(st, ar, linep, 0, &offl_line, &offc_line);
				if (offl_line == offl) {
					/* left edge of the line numbers column */
					glRecti(0, ytop, max_ii(3, (int)(3 * U.pixelsize)), ytop - lheight);
				}
			}

			/* message after the end of the line (its last row when wrapped): errors always,
			 * warnings on the cursor line */
			if (lineidx != last_msg_line && (d->sev == 'e' || linep == text->curl)) {
				int offl_end, offc_end, xmsg, viewl_end;
				wrap_offset(st, ar, linep, linep->len, &offl_end, &offc_end);
				viewl_end = lineidx - st->top + offl_end;
				xmsg = xbase + (text_get_char_pos(st, linep->line, linep->len) - st->left + offc_end + 3) * st->cwidth;
				xmsg = max_ii(xmsg, xbase + 3 * st->cwidth);
				if (xmsg < xmax && viewl_end >= 0 && viewl_end < st->viewlines) {
					last_msg_line = lineidx;
					diag_color(d->sev, 190);
					BLF_position(blf_mono_font, xmsg, ar->winy - viewl_end * lheight - st->lheight_dpi, 0);
					BLF_draw(blf_mono_font, d->msg, sizeof(d->msg));
					diag_color(d->sev, 255);
				}
			}
		}
		last_msg_line = -1;
	}

	glLineWidth(1.0f);
	glDisable(GL_BLEND);
}

static void hints_box(int x, int ytop, int w, int h)
{
	UI_draw_box_shadow(220, x, ytop - h, x + w, ytop);
	UI_ThemeColor(TH_SHADE1);
	glRecti(x - 1, ytop + 1, x + w + 1, ytop - h - 1);
	UI_ThemeColorShade(TH_BACK, 16);
	glRecti(x, ytop, x + w, ytop - h);
}

/* Text flowing in a box of at most maxcols columns: a string continues at (*col, *row) and wraps
 * (continuation indented by 2). With draw false it only measures. */
typedef struct HintFlow {
	int x, y0;          /* left of the text, baseline of row 0 */
	int cwidth, lheight;
	int maxcols;
	int col, row;
	int widest;         /* columns used by the widest row */
	bool draw;
} HintFlow;

static void hints_flow_str(HintFlow *f, const char *str, bool bold)
{
	const char *p = str;
	while (*p) {
		const size_t len = BLI_str_utf8_size_safe(p);
		if (f->col >= f->maxcols) {
			f->col = 2;
			f->row++;
		}
		if (f->draw) {
			const int x = f->x + f->col * f->cwidth, y = f->y0 - f->row * f->lheight;
			BLF_position(blf_mono_font, x, y, 0);
			BLF_draw(blf_mono_font, p, len);
			if (bold) {
				BLF_position(blf_mono_font, x + 1, y, 0);
				BLF_draw(blf_mono_font, p, len);
			}
		}
		f->col++;
		f->widest = max_ii(f->widest, f->col);
		p += len;
	}
}

static void hints_flow_newline(HintFlow *f)
{
	f->col = 0;
	f->row++;
}

/* signature line (before/current/after) + documentation lines */
static void hints_flow_signature(HintFlow *f)
{
	int i;
	if (f->draw) UI_ThemeColor(TH_TEXT);
	hints_flow_str(f, sig.before, false);
	if (sig.current[0]) {
		if (f->draw) UI_ThemeColor(TH_HILITE);
		hints_flow_str(f, sig.current, true);
		if (f->draw) UI_ThemeColor(TH_TEXT);
	}
	hints_flow_str(f, sig.after, false);
	if (f->draw) UI_ThemeColorBlend(TH_TEXT, TH_BACK, 0.3f);
	for (i = 0; i < sig.totdoc; i++) {
		hints_flow_newline(f);
		hints_flow_str(f, sig.doc[i], false);
	}
}

static void hints_flow_detail(HintFlow *f)
{
	int i;
	if (f->draw) UI_ThemeColor(TH_TEXT);
	hints_flow_str(f, detail.lines[0], false);
	if (f->draw) UI_ThemeColorBlend(TH_TEXT, TH_BACK, 0.3f);
	for (i = 1; i < detail.tot; i++) {
		hints_flow_newline(f);
		hints_flow_str(f, detail.lines[i], false);
	}
}

#define HINT_PAD 6

/* measures with the region width as the limit: box size in pixels */
static void hints_flow_measure(const SpaceText *st, ARegion *ar, void (*flow)(HintFlow *),
                               int *r_w, int *r_h)
{
	HintFlow f = {0};
	f.cwidth = st->cwidth;
	f.lheight = st->lheight_dpi + TXT_LINE_SPACING;
	f.maxcols = max_ii(20, (ar->winx - 6 - 2 * HINT_PAD) / max_ii(1, st->cwidth));
	flow(&f);
	*r_w = f.widest * st->cwidth + 2 * HINT_PAD;
	*r_h = (f.row + 1) * f.lheight + 6;
}

static void hints_flow_draw(const SpaceText *st, ARegion *ar, void (*flow)(HintFlow *), int x, int ytop)
{
	HintFlow f = {0};
	f.cwidth = st->cwidth;
	f.lheight = st->lheight_dpi + TXT_LINE_SPACING;
	f.maxcols = max_ii(20, (ar->winx - 6 - 2 * HINT_PAD) / max_ii(1, st->cwidth));
	f.x = x + HINT_PAD;
	f.y0 = ytop - f.lheight + 1;
	f.draw = true;
	flow(&f);
}

static void draw_signature_box(const SpaceText *st, ARegion *ar)
{
	Text *text = st->text;
	const int lheight = st->lheight_dpi + TXT_LINE_SPACING;
	const int xbase = st->showlinenrs ? TXT_OFFSET + TEXTXLOC : TXT_OFFSET;
	int offl, offc, vcurl, vcurc, x, ytop, w, h, line_top;
	int lx, ly, lw, lh, llh;

	if (!sig.has || sig.text != text || !text->curl || txt_has_sel(text)) return;

	hints_flow_measure(st, ar, hints_flow_signature, &w, &h);

	wrap_offset(st, ar, text->curl, text->curc, &offl, &offc);
	vcurl = txt_get_span(text->lines.first, text->curl) - st->top + offl;
	vcurc = text_get_char_pos(st, text->curl->line, text->curc) - st->left + offc;
	if (vcurl < 0 || vcurl >= st->viewlines) return;
	line_top = ar->winy - vcurl * lheight;

	/* the current parameter right above the cursor */
	x = xbase + vcurc * st->cwidth - utf8_columns(sig.before) * st->cwidth - HINT_PAD;
	if (x + w > ar->winx - 2) x = ar->winx - 2 - w;
	x = max_ii(x, 2);

	ytop = line_top + h + 2;
	if (ytop > ar->winy) {
		/* no room above: under the line (and under the completion list when it is open) */
		ytop = line_top - lheight - 2;
		if (text_suggest_list_rect(st, ar, &lx, &ly, &lw, &lh, &llh) && ly <= line_top - lheight + 4) {
			ytop = ly - lh - 4;
		}
	}

	hints_box(x, ytop, w, h);
	hints_flow_draw(st, ar, hints_flow_signature, x, ytop);
}

static void draw_detail_box(const SpaceText *st, ARegion *ar)
{
	int lx, ly, lw, lh, llh, x, ytop, w, h;

	if (!detail.has || !st->text || !texttool_text_is_active(st->text)) return;
	if (!text_suggest_list_rect(st, ar, &lx, &ly, &lw, &lh, &llh)) return;

	hints_flow_measure(st, ar, hints_flow_detail, &w, &h);

	/* right of the list, else left of it, else under it */
	x = lx + lw + 6;
	ytop = ly;
	if (x + w > ar->winx - 2) {
		x = lx - w - 6;
		if (x < 2) {
			x = max_ii(2, min_ii(lx, ar->winx - 2 - w));
			ytop = ly - lh - 4;
		}
	}

	hints_box(x, ytop, w, h);
	hints_flow_draw(st, ar, hints_flow_detail, x, ytop);
}

void text_hints_draw_popups(const SpaceText *st, ARegion *ar)
{
	if (!st->text || !text_is_python(st->text)) return;
	draw_detail_box(st, ar);
	draw_signature_box(st, ar);
}

/* -------------------------------------------------------------------- */
/* other occurrences of the name under the cursor */

#define OCC_WORD_MAX 128
#define OCC_MAX 400

typedef struct OccHit {
	TextLine *line;
	int row;     /* view row of the line's first row */
	int b0, b1;  /* bytes */
} OccHit;

static bool occ_ident_char(char c)
{
	return c == '_' || (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
	       (unsigned char)c >= 0x80;
}

/* names only: no keywords, numbers, strings or comments ('q' default; the python format marks the
 * def/class keywords themselves as 'v', the names after them are 'q') */
static bool occ_format_ok(const SpaceText *st, const TextLine *line, int b)
{
	int fc;
	if (!line->format) return false;
	fc = text_format_index_from_byte(st, line->line, b);
	if (fc < 0 || fc >= (int)strlen(line->format)) return false;
	return line->format[fc] == FMT_TYPE_DEFAULT;
}

/* the selected name (inside one line) or the name around the cursor: [b0, b1) of text->curl */
static bool occ_word_at_cursor(const SpaceText *st, const Text *text, int *r_b0, int *r_b1)
{
	const TextLine *line = text->curl;
	int b0, b1, k;

	if (txt_has_sel(text)) {
		if (text->curl != text->sell) return false;
		b0 = min_ii(text->curc, text->selc);
		b1 = max_ii(text->curc, text->selc);
		if ((b0 > 0 && occ_ident_char(line->line[b0 - 1])) || (b1 < line->len && occ_ident_char(line->line[b1]))) {
			return false;
		}
	}
	else {
		b0 = b1 = text->curc;
		while (b0 > 0 && occ_ident_char(line->line[b0 - 1])) b0--;
		while (b1 < line->len && occ_ident_char(line->line[b1])) b1++;
	}
	if (b1 <= b0 || b1 - b0 >= OCC_WORD_MAX || (line->line[b0] >= '0' && line->line[b0] <= '9')) return false;
	for (k = b0; k < b1; k++) {
		if (!occ_ident_char(line->line[k])) return false;
	}
	*r_b0 = b0;
	*r_b1 = b1;
	return occ_format_ok(st, line, b0);
}

void text_hints_draw_occurrences(SpaceText *st, ARegion *ar)
{
	Text *text = st->text;
	TextFormatType *tft;
	TextLine *linep;
	OccHit *hits;
	char word[OCC_WORD_MAX];
	const int lheight = st->lheight_dpi + TXT_LINE_SPACING;
	const int xbase = st->showlinenrs ? TXT_OFFSET + TEXTXLOC : TXT_OFFSET;
	const int xmax = ar->winx - TXT_SCROLL_WIDTH;
	int wlen, b0, b1, row, wrap_skip, tot = 0, i;
	unsigned char col[4];

	if (!text || !text->curl || (st->flags & ST_NO_HIGHLIGHT_OCCURRENCES) || !st->showsyntax) return;

	tft = ED_text_format_get(text);
	if (!text->curl->format) tft->format_line(st, text->curl, false);
	if (!occ_word_at_cursor(st, text, &b0, &b1)) return;
	wlen = b1 - b0;
	memcpy(word, text->curl->line + b0, wlen);
	word[wlen] = '\0';

	hits = MEM_mallocN(sizeof(*hits) * OCC_MAX, __func__);
	linep = text_draw_first_visible_line(st, &wrap_skip);
	row = -wrap_skip;
	for (; linep && row < st->viewlines && tot < OCC_MAX; linep = linep->next) {
		const char *s = linep->line;
		const char *p = s;
		if (!linep->format) tft->format_line(st, linep, false);
		while ((p = strstr(p, word)) && tot < OCC_MAX) {
			const int ob0 = (int)(p - s), ob1 = ob0 + wlen;
			if ((ob0 == 0 || !occ_ident_char(s[ob0 - 1])) && !occ_ident_char(s[ob1]) && occ_format_ok(st, linep, ob0)) {
				hits[tot].line = linep;
				hits[tot].row = row;
				hits[tot].b0 = ob0;
				hits[tot].b1 = ob1;
				tot++;
			}
			p += wlen;
		}
		row += st->wordwrap ? text_get_visible_lines(st, ar, linep->line) : 1;
	}

	/* the name alone (only here) is not worth a mark */
	if (tot >= 2) {
		UI_GetThemeColor3ubv(TH_SHADE2, col);
		glEnable(GL_BLEND);
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
		glColor4ub(col[0], col[1], col[2], 150);
		for (i = 0; i < tot; i++) {
			const OccHit *h = &hits[i];
			int offl0, offc0, offl1, offc1, x0, x1, vrow, ytop;
			wrap_offset_in_line(st, ar, h->line, h->b0, &offl0, &offc0);
			wrap_offset_in_line(st, ar, h->line, h->b1, &offl1, &offc1);
			vrow = h->row + offl0;
			if (vrow < 0 || vrow >= st->viewlines) continue;
			x0 = xbase + (text_get_char_pos(st, h->line->line, h->b0) - st->left + offc0) * st->cwidth;
			if (offl1 != offl0) {
				x1 = xmax;  /* wrapped in the middle of the name: mark up to the edge */
			}
			else {
				x1 = xbase + (text_get_char_pos(st, h->line->line, h->b1) - st->left + offc1) * st->cwidth;
			}
			x0 = max_ii(x0, xbase);
			x1 = min_ii(x1, xmax);
			if (x1 <= x0) continue;
			ytop = ar->winy - vrow * lheight;
			glRecti(x0 - 1, ytop, x1, ytop - lheight);
		}
		glDisable(GL_BLEND);
	}
	MEM_freeN(hits);
}

/* -------------------------------------------------------------------- */
/* operators */

static int text_signature_help_exec(bContext *C, wmOperator *UNUSED(op))
{
	SpaceText *st = CTX_wm_space_text(C);
	Text *text = st ? st->text : NULL;

	if (!text || !text_is_python(text)) return OPERATOR_CANCELLED;
	sig.text = text;
	sig.active = true;
	sig.key_valid = false;
	ED_area_tag_redraw(CTX_wm_area(C));
	return OPERATOR_FINISHED;
}

void TEXT_OT_signature_help(wmOperatorType *ot)
{
	ot->name = "Show Signature";
	ot->description = "Show the parameters of the function being called at the cursor";
	ot->idname = "TEXT_OT_signature_help";

	ot->exec = text_signature_help_exec;
	ot->poll = text_space_edit_poll;
}

static bool text_hints_hide_poll(bContext *C)
{
	SpaceText *st = CTX_wm_space_text(C);
	/* only while the box is shown: otherwise Esc goes on to the other keymaps */
	return st && st->text && sig.has && sig.text == st->text;
}

static int text_hints_hide_exec(bContext *C, wmOperator *UNUSED(op))
{
	sig.active = sig.has = false;
	ED_area_tag_redraw(CTX_wm_area(C));
	return OPERATOR_FINISHED;
}

void TEXT_OT_hints_hide(wmOperatorType *ot)
{
	ot->name = "Hide Signature";
	ot->description = "Close the function signature box";
	ot->idname = "TEXT_OT_hints_hide";

	ot->exec = text_hints_hide_exec;
	ot->poll = text_hints_hide_poll;
}

/* -------------------------------------------------------------------- */
/* format code (autopep8, in text_autocomplete.formatar) */

static bool text_format_code_poll(bContext *C)
{
	Text *text = CTX_data_edit_text(C);
	return text && !ID_IS_LINKED(text) && text_is_python(text);
}

static int text_format_code_exec(bContext *C, wmOperator *op)
{
#ifdef WITH_PYTHON
	SpaceText *st = CTX_wm_space_text(C);
	Text *text = CTX_data_edit_text(C);
	const char *imports[] = {"text_autocomplete", NULL};
	char *result = NULL;
	int line_idx, col_chars, tot_lines;
	TextLine *line;

	if (!BPY_execute_string_as_string(C, imports, "text_autocomplete.formatar()", true, &result) || !result) {
		BKE_report(op->reports, RPT_ERROR, "Could not run the formatter (see the system console)");
		if (result) MEM_freeN(result);
		return OPERATOR_CANCELLED;
	}
	if (STREQ(result, "SAME")) {
		BKE_report(op->reports, RPT_INFO, "The code is already formatted");
		MEM_freeN(result);
		return OPERATOR_CANCELLED;
	}
	if (!STRPREFIX(result, "OK\n")) {
		BKE_report(op->reports, RPT_WARNING, STRPREFIX(result, "ERR\n") ? result + 4 : "Could not format the code");
		MEM_freeN(result);
		return OPERATOR_CANCELLED;
	}

	/* cursor by line and character (bytes would fall inside a utf-8 char after the changes) */
	line_idx = BLI_findindex(&text->lines, text->curl);
	col_chars = txt_utf8_offset_to_index(text->curl->line, text->curc);

	{
		/* one undo step: the whole text replaced */
		TextUndoBuf *utxt = ED_text_undo_push_init(C);
		txt_sel_all(text);
		txt_insert_buf(text, utxt, result + 3);
	}
	MEM_freeN(result);

	tot_lines = BLI_listbase_count(&text->lines);
	line_idx = min_ii(max_ii(line_idx, 0), tot_lines - 1);
	line = BLI_findlink(&text->lines, line_idx);
	if (line) {
		const int chars = txt_utf8_offset_to_index(line->line, line->len);
		txt_move_to(text, line_idx, txt_utf8_index_to_offset(line->line, min_ii(col_chars, chars)), false);
	}

	if (st) text_drawcache_tag_update(st, 1);
	text_update_cursor_moved(C);
	WM_event_add_notifier(C, NC_TEXT | NA_EDITED, text);
	BKE_report(op->reports, RPT_INFO, "Code formatted (PEP 8)");
	return OPERATOR_FINISHED;
#else
	UNUSED_VARS(C);
	BKE_report(op->reports, RPT_ERROR, "Built without Python");
	return OPERATOR_CANCELLED;
#endif
}

void TEXT_OT_format_code(wmOperatorType *ot)
{
	ot->name = "Format Code";
	ot->description = "Tidy the Python script to the PEP 8 style (spacing, blank lines, indentation) "
	                  "with autopep8; Ctrl+Z undoes it";
	ot->idname = "TEXT_OT_format_code";

	ot->exec = text_format_code_exec;
	ot->poll = text_format_code_poll;

	ot->flag = OPTYPE_UNDO;
}
