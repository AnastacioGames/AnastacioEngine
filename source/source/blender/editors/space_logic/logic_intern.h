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
 *
 * The Original Code is Copyright (C) 2009 Blender Foundation.
 * All rights reserved.
 */

/** \file blender/editors/space_logic/logic_intern.h
 *  \ingroup splogic
 */


#ifndef __LOGIC_INTERN_H__
#define __LOGIC_INTERN_H__

/* internal exports only */
struct ARegion;
struct ScrArea;
struct bContext;
struct wmOperatorType;

/* space_logic.c */
struct ARegion *logic_has_buttons_region(struct ScrArea *sa);

/* logic_ops.c */
struct GLSLUniform;
struct Text;
#define LOGIC_FILTER2D_MAX_UNIFORMS 64
/* Top level uniforms of a Custom 2D Filter Text, without the bgl_* ones the engine fills.
 * *r_code must be freed with MEM_freeN (uniform choice annotations point into it). */
int logic_filter2d_uniforms(struct Text *text, struct GLSLUniform *r_uniforms, char **r_code);
/* Game property type (GPROP_INT/GPROP_FLOAT/GPROP_BOOL) feeding a uniform type, -1 when not editable. */
int logic_filter2d_prop_type(const struct GLSLUniform *uni);
/* Value of a new property: @choice default, else a valid scalar @default, else 0. */
float logic_filter2d_default(const struct GLSLUniform *uni, int type);

/* logic_buttons.c */
void LOGIC_OT_properties(struct wmOperatorType *ot);
void LOGIC_OT_links_cut(struct wmOperatorType *ot);
struct bActuator;
bool ED_logic_actuator_reports_finish(const struct bActuator *act);

/* logic_window.c */
void logic_buttons(struct bContext *C, struct ARegion *ar);
void make_unique_prop_names(struct bContext *C, char *str);

#endif /* __LOGIC_INTERN_H__ */
