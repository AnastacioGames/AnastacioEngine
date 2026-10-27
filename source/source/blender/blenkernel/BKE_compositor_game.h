/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
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
 * ***** END GPL LICENSE BLOCK *****
 */

#ifndef __BKE_COMPOSITOR_GAME_H__
#define __BKE_COMPOSITOR_GAME_H__

/** \file BKE_compositor_game.h
 *  \ingroup bke
 *  \brief Compositor nodes that run in the game (gameengine/Ketsji/KX_CompositorFilter.cpp).
 *
 * One list for the game shader generator and the Node Editor badge, so the editor never
 * promises a node the game skips. Add a node here when KX_CompositorFilter learns it.
 */

#include "BKE_node.h"

/** 0: not in the game (its first input passes through), 1: same as the render,
 * 2: approximated (lighter version, see the badge tooltip in node_draw.c). */
static inline int BKE_compositor_game_support(int type)
{
	switch (type) {
		case NODE_REROUTE:
		case CMP_NODE_R_LAYERS:
		case CMP_NODE_COMPOSITE:
		case CMP_NODE_VIEWER:
		case CMP_NODE_VALUE:
		case CMP_NODE_RGB:
		case CMP_NODE_MIX_RGB:
		case CMP_NODE_ALPHAOVER:
		case CMP_NODE_BRIGHTCONTRAST:
		case CMP_NODE_GAMMA:
		case CMP_NODE_INVERT:
		case CMP_NODE_HUE_SAT:
		case CMP_NODE_COLORBALANCE:
		case CMP_NODE_CURVE_RGB:
		case CMP_NODE_VALTORGB:
		case CMP_NODE_RGBTOBW:
		case CMP_NODE_SEPRGBA:
		case CMP_NODE_COMBRGBA:
		case CMP_NODE_SETALPHA:
		case CMP_NODE_MATH:
		case CMP_NODE_MASK_BOX:
		case CMP_NODE_MASK_ELLIPSE:
		case CMP_NODE_FILTER:
		case CMP_NODE_PIXELATE:
		case CMP_NODE_FLIP:
		case CMP_NODE_TRANSLATE:
		case CMP_NODE_ROTATE:
		case CMP_NODE_SCALE:
		case CMP_NODE_TRANSFORM:
		case CMP_NODE_MAP_VALUE:
		case CMP_NODE_MAP_RANGE:
		case CMP_NODE_SWITCH:
		case CMP_NODE_SEPHSVA:
		case CMP_NODE_COMBHSVA:
		case CMP_NODE_COLORCORRECTION:
		case CMP_NODE_CROP:
			return 1;
		case CMP_NODE_BLUR:
		case CMP_NODE_LENSDIST:
		case CMP_NODE_GLARE:
		case CMP_NODE_SUNBEAMS:
		case CMP_NODE_DBLUR:
		case CMP_NODE_TONEMAP:
		case CMP_NODE_DILATEERODE:
		case CMP_NODE_BILATERALBLUR:
		case CMP_NODE_ZCOMBINE:
			return 2;
		default:
			return 0;
	}
}

#endif  /* __BKE_COMPOSITOR_GAME_H__ */
