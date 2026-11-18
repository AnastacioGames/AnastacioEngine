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

/** \file blender/makesrna/intern/rna_text_api.c
 *  \ingroup RNA
 */

#include <stdlib.h>
#include <stdio.h>

#include "BLI_utildefines.h"
#include "BLI_listbase.h"

#include "RNA_define.h"

#include "rna_internal.h"  /* own include */

#ifdef RNA_RUNTIME

#include "WM_api.h"
#include "WM_types.h"

#include "BKE_report.h"
#include "BKE_text.h"

#include "DNA_text_types.h"

#ifdef WITH_PYTHON
#  include "BPY_extern.h"
#endif

static void rna_Text_clear(Text *text)
{
	BKE_text_clear(text, NULL);
	WM_main_add_notifier(NC_TEXT | NA_EDITED, text);
}

static void rna_Text_write(Text *text, const char *str)
{
	BKE_text_write(text, NULL, str);
	WM_main_add_notifier(NC_TEXT | NA_EDITED, text);
}

/* Same as the Reload operator, without needing a Text Editor in the context (auto reload). */
static bool rna_Text_reload(Text *text, ReportList *reports)
{
	const int orig_curl = BLI_findindex(&text->lines, text->curl);
	const int orig_curc = text->curc;

	if (!BKE_text_reload(text)) {
		BKE_report(reports, RPT_ERROR, "Could not reopen file");
		return false;
	}
#ifdef WITH_PYTHON
	if (text->compiled)
		BPY_text_free_code(text);
#endif
	/* The file is the saved state now: not "edited since last save". */
	text->flags &= ~TXT_ISDIRTY;
	/* Keep the cursor where it was (clamped by txt_move_to), like the Reload operator. */
	txt_move_to(text, (orig_curl > 0) ? orig_curl : 0, (orig_curc > 0) ? orig_curc : 0, false);
	WM_main_add_notifier(NC_TEXT | NA_EDITED, text);
	return true;
}

#else

void RNA_api_text(StructRNA *srna)
{
	FunctionRNA *func;
	PropertyRNA *parm;

	func = RNA_def_function(srna, "clear", "rna_Text_clear");
	RNA_def_function_ui_description(func, "clear the text block");

	func = RNA_def_function(srna, "write", "rna_Text_write");
	RNA_def_function_ui_description(func, "write text at the cursor location and advance to the end of the text block");
	parm = RNA_def_string(func, "text", "Text", 0, "", "New text for this data-block");
	RNA_def_parameter_flags(parm, 0, PARM_REQUIRED);

	func = RNA_def_function(srna, "reload", "rna_Text_reload");
	RNA_def_function_ui_description(func, "Reload the text from its file (no Text Editor needed)");
	RNA_def_function_flag(func, FUNC_USE_REPORTS);
	parm = RNA_def_boolean(func, "result", 0, "", "True when the file was read");
	RNA_def_function_return(func, parm);
}

#endif
