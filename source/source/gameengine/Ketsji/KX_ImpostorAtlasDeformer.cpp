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

/** \file gameengine/Ketsji/KX_ImpostorAtlasDeformer.cpp
 *  \ingroup ketsji
 */

#include "KX_ImpostorAtlasDeformer.h"
#include "RAS_Mesh.h"
#include "RAS_DisplayArray.h"
#include "RAS_BoundingBoxManager.h"

KX_ImpostorAtlasDeformer::KX_ImpostorAtlasDeformer(RAS_Mesh *mesh, RAS_BoundingBoxManager *boundingBoxManager)
	:RAS_Deformer(mesh)
{
	InitializeDisplayArrays();

	// Every other RAS_Deformer subclass creates its own bounding box (see BL_MeshDeformer,
	// KX_SoftBodyDeformer); without one, RAS_Mesh::AddMeshUser hands out a null bounding box
	// that crashes as soon as it's touched (culling, UpdateBounds).
	m_boundingBox = boundingBoxManager->CreateBoundingBox();
	m_boundingBox->CopyAabb(m_mesh->GetBoundingBox());

	// Only one material/display array is expected for a billboard quad, but capture the base
	// UVs of every slot generically in case the impostor plane ever has more than one.
	for (size_t i = 0, size = m_slots.size(); i < size; ++i) {
		RAS_DisplayArray *array = GetDisplayArray((unsigned short)i);
		const unsigned int vertCount = array->GetVertexCount();
		for (unsigned int v = 0; v < vertCount; ++v) {
			m_baseUvs.push_back(array->GetUv(v, 0));
		}
	}
}

KX_ImpostorAtlasDeformer::~KX_ImpostorAtlasDeformer()
{
}

void KX_ImpostorAtlasDeformer::Apply(RAS_DisplayArray *array)
{
}

bool KX_ImpostorAtlasDeformer::Update()
{
	return false;
}

void KX_ImpostorAtlasDeformer::UpdateBuckets()
{
}

void KX_ImpostorAtlasDeformer::SetAtlasCell(unsigned short col, unsigned short row, unsigned short cols, unsigned short rows)
{
	const float uScale = 1.0f / cols;
	const float vScale = 1.0f / rows;
	const float uOffset = col * uScale;
	const float vOffset = row * vScale;

	unsigned int baseIndex = 0;
	for (size_t i = 0, size = m_slots.size(); i < size; ++i) {
		RAS_DisplayArray *array = GetDisplayArray((unsigned short)i);
		const unsigned int vertCount = array->GetVertexCount();
		for (unsigned int v = 0; v < vertCount; ++v) {
			const mt::vec2_packed& base = m_baseUvs[baseIndex + v];
			mt::vec2_packed uv;
			uv[0] = uOffset + base[0] * uScale;
			uv[1] = vOffset + base[1] * vScale;
			array->SetUv(v, 0, uv);
		}
		array->NotifyUpdate(RAS_DisplayArray::UVS_MODIFIED);
		baseIndex += vertCount;
	}
}
