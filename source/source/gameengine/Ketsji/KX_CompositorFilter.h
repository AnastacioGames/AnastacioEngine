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

/** \file KX_CompositorFilter.h
 *  \ingroup ketsji
 *  \brief Compositing in the game: the scene's compositor node tree becomes one 2D Filter.
 */

#ifndef __KX_COMPOSITORFILTER_H__
#define __KX_COMPOSITORFILTER_H__

#include <string>
#include <vector>

struct Scene;

/// Value and RGB nodes become uniforms, so Python can change them while the game runs.
struct KX_CompositorUniform {
	std::string name;           ///< "comp_" + the node name, letters and digits only.
	std::vector<float> values;  ///< 1 (Value) or 4 (RGB) numbers, the value at load.
};

/** Builds the fragment shader of the scene's compositor tree (Scene > Use Nodes), from the
 * Composite node (or the active Viewer) back to the Render Layers. Every node becomes a GLSL
 * function of the screen coordinate, so Blur and Lens Distortion can read their input elsewhere.
 * Returns an empty string when the scene has no usable tree. Unsupported nodes pass their first
 * input through; their names go to \a skipped. Value and RGB nodes go to \a uniforms. */
std::string KX_BuildCompositorShader(Scene *scene, std::vector<std::string>& skipped,
                                     std::vector<KX_CompositorUniform>& uniforms);

#endif  // __KX_COMPOSITORFILTER_H__
