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

/** \file KX_ImpostorAtlasDeformer.h
 *  \ingroup ketsji
 */

#ifndef __KX_IMPOSTOR_ATLAS_DEFORMER_H__
#define __KX_IMPOSTOR_ATLAS_DEFORMER_H__

#include "RAS_Deformer.h"
#include "mathfu.h"

#include <vector>

class RAS_Mesh;
class RAS_BoundingBoxManager;

/** Gives a billboard LOD's quad a private RAS_DisplayArray per game object instance, so its
 * UVs can be rewritten every frame to select a cell of a multi-angle impostor atlas without
 * affecting other instances that share the same KX_Mesh (see KX_GameObject::UpdateLod).
 * No actual vertex deformation happens here; Apply()/Update() are no-ops, the cell selection
 * is driven manually by KX_GameObject::UpdateLod via SetAtlasCell().
 */
class KX_ImpostorAtlasDeformer : public RAS_Deformer
{
public:
	KX_ImpostorAtlasDeformer(RAS_Mesh *mesh, RAS_BoundingBoxManager *boundingBoxManager);
	virtual ~KX_ImpostorAtlasDeformer();

	virtual void Apply(RAS_DisplayArray *array);
	virtual bool Update();
	virtual void UpdateBuckets();

	/// Rewrite the quad's UVs to the given atlas cell, scaling the mesh's original UV layout.
	void SetAtlasCell(unsigned short col, unsigned short row, unsigned short cols, unsigned short rows);

private:
	/// Original UVs (layer 0) captured at construction, before any atlas cell is applied.
	std::vector<mt::vec2_packed> m_baseUvs;
};

#endif  // __KX_IMPOSTOR_ATLAS_DEFORMER_H__
