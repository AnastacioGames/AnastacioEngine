/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

#ifndef __BLI_GLSL_ANNOTATIONS_H__
#define __BLI_GLSL_ANNOTATIONS_H__

/** \file BLI_glsl_annotations.h
 *  \ingroup bli
 *
 * Annotations in the comment that ends the line of a GLSL uniform, shared by the GLSL Script
 * node and the Custom 2D Filter actuator:
 *
 *     uniform int u_mode; // @choice Linear=0, Smooth=1, Step=2 @default 1
 *     uniform float u_power; // @min 0 @max 2 @default 0.5
 */

#include "BLI_sys_types.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BLI_GLSL_CHOICE_MAX_ITEMS 32
#define BLI_GLSL_CHOICE_MAX_LABEL 64
/* Biggest integer a float holds exactly. */
#define BLI_GLSL_CHOICE_LIMIT 16777216
#define BLI_GLSL_CHOICE_BUF (BLI_GLSL_CHOICE_MAX_ITEMS * (BLI_GLSL_CHOICE_MAX_LABEL + 10))

typedef struct GLSLAnnotations {
	bool has_min, has_max;
	float min, max;
	int totdefault;
	float def[4];
	/* Text after "@choice" in the parsed code (not a copy); choicelen -1 when "@choice" appears twice. */
	const char *choice;
	int choicelen;
	/* "@object": a vec2/3/4 2D filter uniform fed with an object's screen position. */
	bool object;
} GLSLAnnotations;

typedef struct GLSLUniform {
	char type[16];
	char name[64];
	GLSLAnnotations ann;
} GLSLUniform;

/* p points right after the ';' of the declaration; ann is cleared first. */
void BLI_glsl_annotations_parse(const char *p, GLSLAnnotations *ann);

/* "@choice A=0, B = 7" -> "A=0,B=7" in r_buf and the starting value (@default, else the first
 * option). False when the annotation is missing or invalid: no option, too many, an empty or too
 * long label, a value that is not a plain integer within BLI_GLSL_CHOICE_LIMIT, a repeated label or
 * value, a @default that is not one of the values, or an option outside @min/@max. */
bool BLI_glsl_choice_build(const GLSLAnnotations *ann, char r_buf[BLI_GLSL_CHOICE_BUF], float *r_default);

/* Walks a string made by BLI_glsl_choice_build: one option per call, false at the end. */
bool BLI_glsl_choice_next(const char **p, char *r_label, int labelsize, int *r_value);

/* Top level "uniform <type> <name>;" declarations with their annotations, at most max of them.
 * Code must stay alive while ann.choice is used. */
int BLI_glsl_uniforms_find(const char *code, GLSLUniform *r_uniforms, int max);

#ifdef __cplusplus
}
#endif

#endif /* __BLI_GLSL_ANNOTATIONS_H__ */
