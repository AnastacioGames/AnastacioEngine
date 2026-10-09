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

/** \file gameengine/Converter/KX_SoftBodyDeformer.cpp
 *  \ingroup bgeconv
 */


#ifdef _MSC_VER
#  pragma warning (disable:4786)
#endif //WIN32

#include "BLI_utildefines.h"

#include "KX_SoftBodyDeformer.h"
#include "KX_Mesh.h"
#include "KX_GameObject.h"

#include "RAS_DisplayArray.h"
#include "RAS_BoundingBoxManager.h"

#ifdef WITH_BULLET

#include "CcdPhysicsEnvironment.h"
#include "CcdPhysicsController.h"
#include "BulletSoftBody/btSoftBody.h"

#include "btBulletDynamicsCommon.h"

KX_SoftBodyDeformer::KX_SoftBodyDeformer(RAS_Mesh *pMeshObject, KX_GameObject *gameobj)
	:RAS_Deformer(pMeshObject),
	m_gameobj(gameobj),
	m_needUpdateAabb(true)
{
	KX_Scene *scene = m_gameobj->GetScene();
	RAS_BoundingBoxManager *boundingBoxManager = scene->GetBoundingBoxManager();
	m_boundingBox = boundingBoxManager->CreateBoundingBox();
	// Set AABB default to mesh bounding box AABB.
	m_boundingBox->CopyAabb(m_mesh->GetBoundingBox());
}

KX_SoftBodyDeformer::~KX_SoftBodyDeformer()
{
}

void KX_SoftBodyDeformer::Apply(RAS_DisplayArray *array)
{
	CcdPhysicsController *ctrl = (CcdPhysicsController *)m_gameobj->GetPhysicsController();
	if (!ctrl) {
		return;
	}

	btSoftBody *softBody = ctrl->GetSoftBody();
	if (!softBody) {
		return;
	}

	// update the vertex in m_transverts
	Update();

	// Update vertex data from the original mesh first, the soft body positions are written over it.
	RAS_DisplayArray *origArray = nullptr;
	for (DisplayArraySlot& slot : m_slots) {
		if (slot.m_displayArray == array) {
			const short modifiedFlag = slot.m_arrayUpdateClient.GetInvalidAndClear();
			if (modifiedFlag != RAS_DisplayArray::NONE_MODIFIED) {
				array->UpdateFrom(slot.m_origDisplayArray, modifiedFlag);
			}
			origArray = slot.m_origDisplayArray;
			break;
		}
	}

	btSoftBody::tNodeArray&   nodes(softBody->m_nodes);
	const unsigned int numNodes = nodes.size();
	const std::vector<unsigned int>& indices = ctrl->GetSoftBodyIndices();

	const bool autoUpdate = m_gameobj->GetAutoUpdateBounds();

	const mt::mat3x4 trans = m_gameobj->NodeGetWorldTransform();
	const mt::mat3& rot = m_gameobj->NodeGetWorldOrientation();
	bool positionsChanged = false;
	bool normalsChanged = false;

	for (unsigned int i = 0, size = array->GetVertexCount(); i < size; ++i) {
		const RAS_VertexInfo& vinfo = array->GetVertexInfo(i);
		const unsigned int origIndex = vinfo.GetOrigIndex();
		const unsigned int index = (origIndex < indices.size()) ? indices[origIndex] : -1;

		mt::vec3 pos;
		mt::vec3 normal;
		if (index < numNodes) {
			pos = ToMt(nodes[index].m_x);
			normal = ToMt(nodes[index].m_n);
		}
		else if (origArray) {
			/* Vertex without soft body node (material with physics disabled):
			 * follow the object transform, the vertices are drawn in world space. */
			pos = trans * mt::vec3(origArray->GetPosition(i));
			normal = rot * mt::vec3(origArray->GetNormal(i));
		}
		else {
			continue;
		}

		/* Bullet soft bodies do not sleep. Compare the exact values that would be
		 * uploaded instead of treating an active solver as a changed mesh. */
		if (mt::vec3(array->GetPosition(i)) != pos) {
			array->SetPosition(i, pos);
			positionsChanged = true;
		}
		if (mt::vec3(array->GetNormal(i)) != normal) {
			array->SetNormal(i, normal);
			normalsChanged = true;
		}
	}

	if (positionsChanged || normalsChanged) {
		array->NotifyUpdate((positionsChanged ? RAS_DisplayArray::POSITION_MODIFIED : 0) |
		                    (normalsChanged ? RAS_DisplayArray::NORMAL_MODIFIED : 0));
	}

	if (autoUpdate && positionsChanged) {
		// Bounds only need rebuilding when the world-space vertex data changed.
		mt::vec3 aabbMin(FLT_MAX);
		mt::vec3 aabbMax(-FLT_MAX);
		if (m_needUpdateAabb) {
			m_boundingBox->SetAabb(aabbMin, aabbMax);
			m_needUpdateAabb = false;
		}

		const mt::mat3x4 invtrans = trans.Inverse();
		for (unsigned int i = 0, size = array->GetVertexCount(); i < size; ++i) {
			// Extract object transform from the vertex position.
			const mt::vec3 ptLocal = invtrans * mt::vec3(array->GetPosition(i));
			aabbMin = mt::vec3::Min(aabbMin, ptLocal);
			aabbMax = mt::vec3::Max(aabbMax, ptLocal);
		}
		m_boundingBox->ExtendAabb(aabbMin, aabbMax);
	}
}

#endif
