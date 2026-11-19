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

/** \file blender/editors/space_text/text_autocomplete.c
 *  \ingroup sptext
 */

#include <ctype.h>
#include <stdlib.h>
#include <string.h>

#include "MEM_guardedalloc.h"

#include "DNA_space_types.h"
#include "DNA_text_types.h"

#include "BLI_blenlib.h"
#include "BLI_ghash.h"
#include "BLI_string_utf8.h"

#include "BKE_context.h"
#include "BKE_text.h"
#include "BKE_screen.h"
#include "BKE_suggestions.h"

#include "WM_api.h"
#include "WM_types.h"

#include "RNA_access.h"
#include "RNA_define.h"

#include "ED_text.h"
#include "ED_undo.h"
#include "ED_screen.h"

#include "UI_interface.h"

#ifdef WITH_PYTHON
#include "BPY_extern.h"
#endif

#include "text_format.h"
#include "text_intern.h"  /* own include */

/* The suggestion list (BKE_suggestions) is global: only one list open at a time. */
static bool ac_modal_running = false;
/* Where the open list was built: a list is only confirmed on that same word (cursor moved by
 * something else, a selection or another line invalidate it). Only compared, never read. */
static const TextLine *ac_line = NULL;
static int ac_word_start = -1;
/* the list came from the python provider (text_autocomplete.detalhe() can describe its items);
 * the generation changes on every rebuild (cached item descriptions are dropped) */
static bool ac_from_python = false;
static int ac_generation = 0;

bool text_autocomplete_list_from_python(int *r_generation)
{
	*r_generation = ac_generation;
	return ac_from_python && ac_modal_running;
}

/* -------------------------------------------------------------------- */
/* Public API */

int text_do_suggest_select(SpaceText *st, ARegion *ar, const int mval[2])
{
	SuggItem *item, *first, *last;
	int x, y, boxw, boxh, lheight, i, row, *top;

	if (!st || !st->text || !ar) return 0;
	if (!text_suggest_list_rect(st, ar, &x, &y, &boxw, &boxh, &lheight)) return 0;

	if (mval[0] < x || x + boxw < mval[0] || mval[1] < y - boxh || y < mval[1])
		return 0;

	first = texttool_suggest_first();
	last = texttool_suggest_last();
	top = texttool_suggest_top();

	/* Work out which of the items is at the top of the visible list */
	for (i = 0, item = first; i < *top && item->next && item != last; i++, item = item->next) ;

	/* same rows as draw_suggestion_list(): row r spans [y - (r + 1) * lheight - 3, y - r * lheight - 3] */
	row = (y - 3 - mval[1]) / lheight;
	CLAMP(row, 0, SUGG_LIST_SIZE - 1);

	for (i = row; i > 0 && item != last && item->next; i--, item = item->next) ;
	if (item)
		texttool_suggest_select(item);
	return 1;
}

void text_pop_suggest_list(void)
{
	SuggItem *item, *sel;
	int *top, i;

	item = texttool_suggest_first();
	sel = texttool_suggest_selected();
	top = texttool_suggest_top();

	i = 0;
	while (item && item != sel) {
		item = item->next;
		i++;
	}
	if (i > *top + SUGG_LIST_SIZE - 1)
		*top = i - SUGG_LIST_SIZE + 1;
	else if (i < *top)
		*top = i;
}

/* -------------------------------------------------------------------- */
/* Private API */

bool text_is_python(Text *text)
{
	TextFormatType *tft = ED_text_format_get(text);
	return tft && tft->ext && tft->ext[0] && STREQ(tft->ext[0], "py");
}

static int suggest_cmp(const void *a, const void *b)
{
	return BLI_strcasecmp(*(const char *const *)a, *(const char *const *)b);
}

/* Old behavior (and fallback when the Python provider is missing): the identifiers of the
 * document that start with the word at the cursor. */
static void text_autocomplete_build_words(Text *text)
{
	GHash *gh;
	int seek_len = 0;
	const char *seek;

	/* first get the word we're at */
	{
		const int i = text_find_identifier_start(text->curl->line, text->curc);
		seek_len = text->curc - i;
		seek = text->curl->line + i;
	}

	/* now walk over entire doc and suggest words */
	gh = BLI_ghash_str_new(__func__);

	for (TextLine *linep = text->lines.first; linep; linep = linep->next) {
		size_t i_start = 0;
		size_t i_end = 0;
		size_t i_pos = 0;

		while (i_start < linep->len) {
			/* seek identifier beginning */
			i_pos = i_start;
			while ((i_start < linep->len) &&
			       (!text_check_identifier_nodigit_unicode(BLI_str_utf8_as_unicode_and_size_safe(&linep->line[i_start], &i_pos))))
			{
				i_start = i_pos;
			}
			i_pos = i_end = i_start;
			while ((i_end < linep->len) &&
			       (text_check_identifier_unicode(BLI_str_utf8_as_unicode_and_size_safe(&linep->line[i_end], &i_pos))))
			{
				i_end = i_pos;
			}

			if ((i_start != i_end) &&
			    /* check we're at the beginning of a line or that the previous char is not an identifier
			     * this prevents digits from being added */
			    ((i_start < 1) || !text_check_identifier_unicode(BLI_str_utf8_as_unicode(&linep->line[i_start - 1]))))
			{
				char *str_sub = &linep->line[i_start];
				const int choice_len = i_end - i_start;

				if ((choice_len > seek_len) &&
				    (seek_len == 0 || STREQLEN(seek, str_sub, seek_len)) &&
				    (seek != str_sub))
				{
					char str_sub_last = str_sub[choice_len];
					str_sub[choice_len] = '\0';
					if (!BLI_ghash_lookup(gh, str_sub)) {
						char *str_dup = BLI_strdupn(str_sub, choice_len);
						/* A 'set' would make more sense here */
						BLI_ghash_insert(gh, str_dup, str_dup);
					}
					str_sub[choice_len] = str_sub_last;
				}
			}
			if (i_end != i_start) {
				i_start = i_end;
			}
			else {
				/* highly unlikely, but prevent eternal loop */
				i_start++;
			}
		}
	}

	{
		/* add in sorted order: texttool_suggest_add() then appends at the end (no quadratic
		 * insertion for big documents) */
		const unsigned int tot = BLI_ghash_len(gh);
		const char **names = MEM_mallocN(sizeof(*names) * MAX2(tot, 1u), __func__);
		TextFormatType *tft = ED_text_format_get(text);
		GHashIterator gh_iter;
		unsigned int i = 0;

		GHASH_ITER (gh_iter, gh) {
			names[i++] = BLI_ghashIterator_getValue(&gh_iter);
		}
		qsort(names, tot, sizeof(*names), suggest_cmp);
		for (i = 0; i < tot; i++) {
			texttool_suggest_add(names[i], tft->format_identifier(names[i]));
		}
		MEM_freeN((void *)names);
	}

	/* the names were copied into the suggestion items */
	BLI_ghash_free(gh, NULL, MEM_freeN);
}

/* Python provider (release/scripts/modules/text_autocomplete.py): API of the game (bge, types,
 * mathutils) + imports + document words, following simple assignments (own = cont.owner).
 * Returns 1 = list filled, 0 = nothing to suggest here (comment/string), -1 = provider failed. */
static int text_autocomplete_build_python(bContext *C, Text *text)
{
#ifdef WITH_PYTHON
	static bool reported = false;
	const char *imports[] = {"text_autocomplete", NULL};
	char expr[96];
	char *result = NULL;
	bool ok;

	BLI_snprintf(expr, sizeof(expr), "text_autocomplete.candidatos(%d, %d)",
	             BLI_findindex(&text->lines, text->curl), text->curc);
	/* report the first failure (console + info bar), then fall back quietly to the document words */
	ok = BPY_execute_string_as_string(C, imports, expr, !reported, &result);
	if (!ok || !result || !STRPREFIX(result, "OK")) {
		const int ret = (ok && result && STRPREFIX(result, "SKIP")) ? 0 : -1;
		if (ret < 0 && !reported) {
			printf("Text autocomplete: python provider failed, using the document words\n");
			reported = true;
		}
		if (result) MEM_freeN(result);
		return ret;
	}

	/* "OK\n<type><name>\n...", already sorted (case insensitive) */
	{
		char *line = strchr(result, '\n');
		while (line) {
			char *next;
			line++;
			next = strchr(line, '\n');
			if (next) *next = '\0';
			if (line[0] && line[1]) {
				texttool_suggest_add(line + 1, line[0]);
			}
			line = next;
		}
	}
	MEM_freeN(result);
	return 1;
#else
	UNUSED_VARS(C, text);
	return -1;
#endif
}

static void get_suggest_prefix(Text *text, int offset)
{
	int i, len;
	const char *line;

	if (!text) return;
	if (!texttool_text_is_active(text)) return;

	line = text->curl->line;
	i = text_find_identifier_start(line, text->curc + offset);
	len = text->curc - i + offset;
	texttool_suggest_prefix(line + i, len);
}

/* (Re)builds the whole list for the cursor context and filters it by the typed word. */
static void text_autocomplete_build(bContext *C, Text *text)
{
	texttool_text_clear();
	texttool_text_set_active(text);

	ac_generation++;
	ac_from_python = text_is_python(text) && text_autocomplete_build_python(C, text) >= 0;
	if (!ac_from_python) {
		texttool_text_clear();
		texttool_text_set_active(text);
		text_autocomplete_build_words(text);
	}

	get_suggest_prefix(text, 0);

	ac_line = text->curl;
	ac_word_start = text_find_identifier_start(text->curl->line, text->curc);
}

static bool text_autocomplete_list_valid(Text *text)
{
	return text->curl && text->curl == ac_line && !txt_has_sel(text) &&
	       text_find_identifier_start(text->curl->line, text->curc) == ac_word_start;
}

/* End of the identifier that contains the cursor (bytes). */
static int text_identifier_end(const TextLine *line, int i)
{
	while (i < line->len) {
		const unsigned int ch = BLI_str_utf8_as_unicode(line->line + i);
		if (!text_check_identifier_unicode(ch)) break;
		i += BLI_str_utf8_size_safe(line->line + i);
	}
	return i;
}

/* The word around the cursor is exactly the suggestion (nothing to complete). */
static bool suggestion_is_typed_word(Text *text, SuggItem *sel)
{
	const char *line = text->curl->line;
	const int start = text_find_identifier_start(line, text->curc);
	const int end = text_identifier_end(text->curl, text->curc);
	return sel && (int)strlen(sel->name) == end - start && STREQLEN(sel->name, line + start, end - start);
}

/* Replaces the whole word at the cursor by the suggestion (also fixes the case: the list
 * matches "getcu" to getCurrentController) as one undo step. */
static void confirm_suggestion(bContext *C, Text *text)
{
	SpaceText *st = CTX_wm_space_text(C);
	SuggItem *sel;
	TextUndoBuf *utxt;
	int start, end, line_index;

	if (!text) return;
	if (!texttool_text_is_active(text)) return;

	sel = texttool_suggest_selected();
	if (!sel || !text_autocomplete_list_valid(text)) return;

	start = text_find_identifier_start(text->curl->line, text->curc);
	end = text_identifier_end(text->curl, text->curc);
	line_index = BLI_findindex(&text->lines, text->curl);

	if (st) text_drawcache_tag_update(st, 0);
	utxt = ED_text_undo_push_init(C);
	txt_move_to(text, line_index, start, false);
	txt_move_to(text, line_index, end, true);
	txt_insert_buf(text, utxt, sel->name);
	text_update_line_edited(text->curl);
	text_update_cursor_moved(C);
	WM_event_add_notifier(C, NC_TEXT | NA_EDITED, text);
	ED_undo_push(C, "Text Auto Complete");

	texttool_text_clear();
}

static void text_autocomplete_free(bContext *C, wmOperator *UNUSED(op))
{
	SpaceText *st = CTX_wm_space_text(C);
	if (st) st->doplugins = false;
	texttool_text_clear();
	ac_modal_running = false;
	ac_line = NULL;
	ac_word_start = -1;
}

/* -- */

static int text_autocomplete_invoke(bContext *C, wmOperator *op, const wmEvent *UNUSED(event))
{
	SpaceText *st = CTX_wm_space_text(C);
	Text *text = CTX_data_edit_text(C);
	const bool live = RNA_boolean_get(op->ptr, "live");

	if (ac_modal_running || !st || !text || !text->curl) {
		return OPERATOR_CANCELLED;
	}

	st->doplugins = true;
	text_autocomplete_build(C, text);

	if (texttool_suggest_first()) {
		SuggItem *first = texttool_suggest_first();

		if (live) {
			/* opened by itself: never edits the text without Tab/Enter, and does not show a
			 * list whose only entry is the word already typed */
			if (first == texttool_suggest_last() && suggestion_is_typed_word(text, first)) {
				text_autocomplete_free(C, op);
				return OPERATOR_CANCELLED;
			}
		}
		else if (first == texttool_suggest_last()) {
			confirm_suggestion(C, st->text);
			text_autocomplete_free(C, op);
			return OPERATOR_FINISHED;
		}

		ED_area_tag_redraw(CTX_wm_area(C));
		ac_modal_running = true;
		WM_event_add_modal_handler(C, op);
		return OPERATOR_RUNNING_MODAL;
	}
	else {
		text_autocomplete_free(C, op);
		return OPERATOR_CANCELLED;
	}
}

static int text_autocomplete_end(bContext *C, wmOperator *op, int retval)
{
	ScrArea *sa = CTX_wm_area(C);
	if (sa) ED_area_tag_redraw(sa);
	text_autocomplete_free(C, op);
	return retval;
}

static void text_autocomplete_scroll(int scroll, bool down)
{
	SuggItem *sel = texttool_suggest_selected();
	if (!sel) {
		texttool_suggest_select(texttool_suggest_first());
		return;
	}
	while (sel && scroll--) {
		if (down) {
			sel = (sel != texttool_suggest_last() && sel->next) ? sel->next : texttool_suggest_first();
		}
		else {
			sel = (sel != texttool_suggest_first() && sel->prev) ? sel->prev : texttool_suggest_last();
		}
		texttool_suggest_select(sel);
	}
	text_pop_suggest_list();
}

static bool mouse_over_list(SpaceText *st, ARegion *ar, const wmEvent *event)
{
	int x, y, boxw, boxh, lheight;
	return ar && text_suggest_list_rect(st, ar, &x, &y, &boxw, &boxh, &lheight) &&
	       event->mval[0] >= x && event->mval[0] <= x + boxw &&
	       event->mval[1] <= y && event->mval[1] >= y - boxh;
}

static int text_autocomplete_modal(bContext *C, wmOperator *op, const wmEvent *event)
{
	SpaceText *st = CTX_wm_space_text(C);
	ScrArea *sa = CTX_wm_area(C);
	ARegion *ar = sa ? BKE_area_find_region_type(sa, RGN_TYPE_WINDOW) : NULL;
	const bool modifier = event->ctrl || event->alt || event->oskey;
	int scroll = 1;

	/* list gone (no match left, cursor/selection changed by something else): stop and let the
	 * event through */
	if (!st || !st->text || !st->doplugins || !texttool_text_is_active(st->text) ||
	    !texttool_suggest_first() || !text_autocomplete_list_valid(st->text))
	{
		return text_autocomplete_end(C, op, OPERATOR_CANCELLED | OPERATOR_PASS_THROUGH);
	}
	/* the modal runs in the area it was opened in: a key or click over another area belongs to
	 * that area (Tab there must not complete here) */
	if (event->val == KM_PRESS && sa && !BLI_rcti_isect_pt_v(&sa->totrct, &event->x)) {
		return text_autocomplete_end(C, op, OPERATOR_CANCELLED | OPERATOR_PASS_THROUGH);
	}

	switch (event->type) {
		case LEFTMOUSE:
		case MIDDLEMOUSE:
			if (event->val == KM_PRESS) {
				if (text_do_suggest_select(st, ar, event->mval)) {
					confirm_suggestion(C, st->text);
					return text_autocomplete_end(C, op, OPERATOR_FINISHED);
				}
				return text_autocomplete_end(C, op, OPERATOR_CANCELLED | OPERATOR_PASS_THROUGH);
			}
			return OPERATOR_PASS_THROUGH;
		case ESCKEY:
			if (event->val == KM_PRESS) {
				return text_autocomplete_end(C, op, OPERATOR_CANCELLED);
			}
			return OPERATOR_RUNNING_MODAL;
		case RETKEY:
		case PADENTER:
		case TABKEY:
			if (event->val == KM_PRESS) {
				SuggItem *sel = texttool_suggest_selected();
				/* Enter on a word that is already complete is a new line, not a completion */
				if (modifier || event->shift || !sel ||
				    (event->type != TABKEY && suggestion_is_typed_word(st->text, sel)))
				{
					return text_autocomplete_end(C, op, OPERATOR_CANCELLED | OPERATOR_PASS_THROUGH);
				}
				confirm_suggestion(C, st->text);
				return text_autocomplete_end(C, op, OPERATOR_FINISHED);
			}
			return OPERATOR_RUNNING_MODAL;
		case PAGEDOWNKEY:
		case PAGEUPKEY:
			scroll = SUGG_LIST_SIZE - 1;
			ATTR_FALLTHROUGH;
		case DOWNARROWKEY:
		case UPARROWKEY:
			if (modifier || event->shift) {
				return text_autocomplete_end(C, op, OPERATOR_CANCELLED | OPERATOR_PASS_THROUGH);
			}
			if (event->val == KM_PRESS) {
				text_autocomplete_scroll(scroll, ELEM(event->type, DOWNARROWKEY, PAGEDOWNKEY));
				ED_area_tag_redraw(sa);
			}
			return OPERATOR_RUNNING_MODAL;
		case WHEELDOWNMOUSE:
		case WHEELUPMOUSE:
			if (mouse_over_list(st, ar, event)) {
				text_autocomplete_scroll(1, event->type == WHEELDOWNMOUSE);
				ED_area_tag_redraw(sa);
				return OPERATOR_RUNNING_MODAL;
			}
			return text_autocomplete_end(C, op, OPERATOR_CANCELLED | OPERATOR_PASS_THROUGH);
		case BACKSPACEKEY:
		case DELKEY:
			/* the normal delete operator runs; text_autocomplete_after_edit() updates the list */
			return OPERATOR_PASS_THROUGH;
		case LEFTSHIFTKEY:
		case RIGHTSHIFTKEY:
		case LEFTCTRLKEY:
		case RIGHTCTRLKEY:
		case LEFTALTKEY:
		case RIGHTALTKEY:
		case OSKEY:
			return OPERATOR_PASS_THROUGH;
		default:
			break;
	}

	if (event->val == KM_PRESS && ISKEYBOARD(event->type)) {
		/* typed text (also IME, which may carry modifiers): the normal insert operator runs and
		 * text_autocomplete_after_edit() keeps the list in sync (refilter, new context after '.',
		 * close on space/symbols) */
		if (event->utf8_buf[0]) {
			return OPERATOR_PASS_THROUGH;
		}
		/* any other key (arrows, Home, Ctrl+Z, Ctrl+S...): close and let it work as usual */
		return text_autocomplete_end(C, op, OPERATOR_CANCELLED | OPERATOR_PASS_THROUGH);
	}

	return OPERATOR_PASS_THROUGH;
}

static void text_autocomplete_cancel(bContext *C, wmOperator *op)
{
	text_autocomplete_free(C, op);
}

void text_autocomplete_after_edit(bContext *C, unsigned int inserted)
{
	SpaceText *st = CTX_wm_space_text(C);
	Text *text = st ? st->text : NULL;
	const char *line;
	int start;

	if (!st || !text || !text->curl) return;

	/* code hints: diagnostics wait for a pause, the signature box follows '(' and ',' */
	text_hints_after_edit(C, st, text, inserted);

	line = text->curl->line;
	start = text_find_identifier_start(line, text->curc);

	if (ac_modal_running) {
		/* only the editor that owns the open list */
		if (!st->doplugins || !texttool_text_is_active(text)) return;
		if (txt_has_sel(text)) {
			texttool_suggest_clear();
			ED_area_tag_redraw(CTX_wm_area(C));
			return;
		}

		if (inserted == 0 || inserted == '.' || text_check_identifier_unicode(inserted)) {
			const bool after_dot = (start > 0 && line[start - 1] == '.');
			if (start == text->curc && !after_dot) {
				texttool_suggest_clear();  /* deleted the whole word */
			}
			else {
				/* rebuild: the context may have changed (after '.', or a deletion) */
				text_autocomplete_build(C, text);
			}
		}
		else {
			texttool_suggest_clear();  /* space, '(', ':'... ends the word */
		}
		ED_area_tag_redraw(CTX_wm_area(C));
		return;
	}

	/* Autocomplete While Typing: open the list by itself */
	if (inserted == 0 || (st->flags & ST_NO_LIVE_AUTOCOMPLETE)) return;
	if (!text_is_python(text) || txt_has_sel(text)) return;
	/* not in the middle of a word */
	if (text->curc < text->curl->len &&
	    text_check_identifier_unicode(BLI_str_utf8_as_unicode(line + text->curc)))
	{
		return;
	}
	if (inserted != '.') {
		if (!text_check_identifier_unicode(inserted)) return;
		if (!text_check_identifier_nodigit_unicode(BLI_str_utf8_as_unicode(line + start))) return;
		if (BLI_strnlen_utf8(line + start, text->curc - start) < 3) return;
	}

	{
		wmOperatorType *ot = WM_operatortype_find("TEXT_OT_autocomplete", true);
		PointerRNA ptr;
		if (!ot) return;
		WM_operator_properties_create_ptr(&ptr, ot);
		RNA_boolean_set(&ptr, "live", true);
		WM_operator_name_call_ptr(C, ot, WM_OP_INVOKE_DEFAULT, &ptr);
		WM_operator_properties_free(&ptr);
	}
}

void TEXT_OT_autocomplete(wmOperatorType *ot)
{
	PropertyRNA *prop;

	/* identifiers */
	ot->name = "Text Auto Complete";
	ot->description = "Show the code completion list (game API, imports and the words of the document)";
	ot->idname = "TEXT_OT_autocomplete";

	/* api callbacks */
	ot->invoke = text_autocomplete_invoke;
	ot->cancel = text_autocomplete_cancel;
	ot->modal = text_autocomplete_modal;
	ot->poll = text_space_edit_poll;

	/* flags */
	/* Undo is handled conditionally by this operator. */
	ot->flag = OPTYPE_BLOCKING;

	prop = RNA_def_boolean(ot->srna, "live", false, "Live",
	                       "Opened by itself while typing: never inserts without Tab/Enter");
	RNA_def_property_flag(prop, PROP_HIDDEN | PROP_SKIP_SAVE);
}
