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

#include <string.h>

#include "MEM_guardedalloc.h"

#include "BLI_blenlib.h"
#include "BLI_utildefines.h"

#include "DNA_space_types.h"
#include "DNA_text_types.h"

#include "BKE_context.h"
#include "BKE_screen.h"

#include "BLF_api.h"

#include "ED_screen.h"
#include "ED_space_api.h"

#include "BIF_gl.h"

#include "WM_api.h"
#include "WM_types.h"

#include "UI_resources.h"
#include "UI_view2d.h"

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
	ar->v2d.min[0] = ar->v2d.min[1] = 50.0f;
	ar->v2d.max[0] = ar->v2d.max[1] = 32000.0f;
	ar->v2d.minzoom = 0.1f;
	ar->v2d.maxzoom = 5.0f;
	ar->v2d.keepzoom = V2D_LIMITZOOM | V2D_KEEPASPECT;
	ar->v2d.keeptot = V2D_KEEPTOT_FREE;

	return (SpaceLink *)smm;
}

static void mindmap_free(SpaceLink *UNUSED(sl))
{
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

static void mindmap_main_region_init(wmWindowManager *UNUSED(wm), ARegion *ar)
{
	UI_view2d_region_reinit(&ar->v2d, V2D_COMMONVIEW_CUSTOM, ar->winx, ar->winy);
}

static void mindmap_main_region_draw(const bContext *UNUSED(C), ARegion *ar)
{
	const char *message = "Mind Map";

	UI_ThemeClearColor(TH_BACK);
	glClear(GL_COLOR_BUFFER_BIT);

	UI_ThemeColor(TH_TEXT);
	BLF_draw_default(
	        (ar->winx - BLF_width_default(message, BLF_DRAW_STR_DUMMY_MAX)) * 0.5f,
	        ar->winy * 0.5f, 0.0f, message, BLF_DRAW_STR_DUMMY_MAX);
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

	art = MEM_callocN(sizeof(ARegionType), "spacetype mind map region");
	art->regionid = RGN_TYPE_WINDOW;
	art->keymapflag = ED_KEYMAP_UI | ED_KEYMAP_VIEW2D;
	art->init = mindmap_main_region_init;
	art->draw = mindmap_main_region_draw;
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
