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
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 *
 * The Original Code is: all of this file.
 *
 * Contributor(s): none yet.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file RAS_MaterialBucket.h
 *  \ingroup bgerast
 */

#ifndef __RAS_MATERIAL_BUCKET_H__
#define __RAS_MATERIAL_BUCKET_H__

#include "RAS_DisplayArrayBucket.h"

#include <vector>

class RAS_IMaterial;
class RAS_Rasterizer;

/* Contains a list of display arrays with the same material,
 * and a mesh slot for each mesh that uses display arrays in
 * this bucket */

class RAS_MaterialBucket
{
public:
	RAS_MaterialBucket(RAS_IMaterial *mat);
	virtual ~RAS_MaterialBucket();

	// Material Properties
	RAS_IMaterial *GetMaterial() const;
	bool IsAlpha() const;
	bool IsZSort() const;
	bool IsWire() const;
	bool IsHaloPoints() const;
	bool UseInstancing() const;

	// Rendering
	void ActivateMaterial(RAS_Rasterizer *rasty);
	void DesactivateMaterial(RAS_Rasterizer *rasty);

	// Render nodes.
	void GenerateTree(RAS_ManagerDownwardNode& downwardRoot, RAS_ManagerUpwardNode& upwardRoot,
			RAS_UpwardTreeLeafs& upwardLeafs, RAS_Rasterizer::DrawType drawingMode, bool sort);
	void BindNode(const RAS_MaterialNodeTuple& tuple);
	void UnbindNode(const RAS_MaterialNodeTuple& tuple);

	void RemoveActiveMeshSlots();
	/* Set when a mesh slot of this material becomes visible in the current pass, cleared
	 * with the slots: lets each pass skip invisible materials without scanning their arrays.
	 * The first activation also appends the bucket to its manager's active list, so the
	 * shadow passes and the end-of-pass cleanup visit only the visible materials. */
	void MarkActive()
	{
		if (!m_hasActive) {
			m_hasActive = true;
			if (m_activeList) {
				m_activeList->push_back(this);
			}
		}
	}
	bool HasActive() const { return m_hasActive; }

	/// Owned by RAS_BucketManager (set on creation and on Merge).
	void SetActiveList(std::vector<RAS_MaterialBucket *> *list) { m_activeList = list; }
	/// Bit (1 << BucketType) for each RAS_BucketManager list holding this bucket.
	void AddTypeBit(unsigned int bit) { m_typeMask |= bit; }
	bool HasTypeBit(unsigned int bit) const { return (m_typeMask & bit) != 0; }

	void AddDisplayArrayBucket(RAS_DisplayArrayBucket *bucket);
	void RemoveDisplayArrayBucket(RAS_DisplayArrayBucket *bucket);

	RAS_DisplayArrayBucketList& GetDisplayArrayBucketList();

	void MoveDisplayArrayBucket(RAS_MeshMaterial *meshmat, RAS_MaterialBucket *bucket);

private:
	RAS_IMaterial *m_material;
	bool m_hasActive = false;
	unsigned int m_typeMask = 0;
	std::vector<RAS_MaterialBucket *> *m_activeList = nullptr;
	RAS_DisplayArrayBucketList m_displayArrayBucketList;

	RAS_MaterialNodeData m_nodeData;
	RAS_MaterialDownwardNode m_downwardNode;
	RAS_MaterialUpwardNode m_upwardNode;
};

#endif  // __RAS_MATERIAL_BUCKET_H__
