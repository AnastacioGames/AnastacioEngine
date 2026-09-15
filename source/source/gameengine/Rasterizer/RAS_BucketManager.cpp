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

/** \file gameengine/Rasterizer/RAS_BucketManager.cpp
 *  \ingroup bgerast
 */

#ifdef _MSC_VER
/* don't show these anoying STL warnings */
#  pragma warning (disable:4786)
#endif

#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "RAS_MaterialBucket.h"
#include "RAS_Mesh.h"
#include "RAS_MeshUser.h"
#include "RAS_ICanvas.h"
#include "RAS_IMaterial.h"
#include "RAS_Rasterizer.h"

#include "RAS_BucketManager.h"

#include <algorithm>
/* sorting */



RAS_BucketManager::SortedMeshSlot::SortedMeshSlot(RAS_MeshSlot *ms, const mt::vec3& pnorm)
	:m_ms(ms)
{
	// would be good to use the actual bounding box center instead
	const mt::vec3 pos = m_ms->m_meshUser->GetMatrix().TranslationVector3D();

	m_z = mt::dot(pnorm, pos);
}

RAS_BucketManager::SortedMeshSlot::SortedMeshSlot(RAS_MeshSlotUpwardNode *node, const mt::vec3& pnorm)
	:m_node(node)
{
	RAS_MeshSlot *ms = m_node->GetOwner();
	// would be good to use the actual bounding box center instead
	const mt::vec3 pos = ms->m_meshUser->GetMatrix().TranslationVector3D();

	m_z = mt::dot(pnorm, pos);
}

bool RAS_BucketManager::backtofront::operator()(const SortedMeshSlot &a, const SortedMeshSlot &b)
{
	return (a.m_z < b.m_z) || (a.m_z == b.m_z && a.m_ms < b.m_ms);
}

bool RAS_BucketManager::fronttoback::operator()(const SortedMeshSlot &a, const SortedMeshSlot &b)
{
	return (a.m_z > b.m_z) || (a.m_z == b.m_z && a.m_ms > b.m_ms);
}

RAS_BucketManager::RAS_BucketManager(RAS_IMaterial *textMaterial)
	:m_downwardNode(this, &m_nodeData, nullptr, nullptr),
	m_upwardNode(this, &m_nodeData, nullptr, nullptr)
{
	bool created;
	m_text.m_bucket = FindBucket(textMaterial, created);
	m_text.m_arrayBucket = new RAS_DisplayArrayBucket(m_text.m_bucket, nullptr, nullptr, nullptr, nullptr);
}

RAS_BucketManager::~RAS_BucketManager()
{
	delete m_text.m_arrayBucket;

	for (RAS_MaterialBucket *bucket : m_buckets[ALL_BUCKET]) {
		delete bucket;
	}
}

void RAS_BucketManager::PrepareBuckets(RAS_Rasterizer *rasty, RAS_BucketManager::BucketType bucketType)
{
	if (m_nodeData.m_shaderOverride) {
		return;
	}

	for (RAS_MaterialBucket *bucket : m_buckets[bucketType]) {
		RAS_IMaterial *mat = bucket->GetMaterial();
		mat->Prepare(rasty);
		RAS_Rasterizer::IncMaterialChangeCount();
	}
}

void RAS_BucketManager::RenderSortedBuckets(RAS_Rasterizer *rasty, RAS_BucketManager::BucketType bucketType)
{
	PrepareBuckets(rasty, bucketType);

	BucketList& solidBuckets = m_buckets[bucketType];
	RAS_UpwardTreeLeafs leafs;
	for (RAS_MaterialBucket *bucket : solidBuckets) {
		bucket->GenerateTree(m_downwardNode, m_upwardNode, leafs, m_nodeData.m_drawingMode, true);
	}

	m_nodeData.m_sort = true;

	if (m_downwardNode.GetValid()) {
		m_downwardNode.Execute(RAS_DummyNodeTuple());
	}
	if (!leafs.empty()) {
		/* Camera's near plane equation: pnorm.dot(point) + pval,
		 * but we leave out pval since it's constant anyway */
		const mt::mat3x4& trans = m_nodeData.m_trans;
		const mt::vec3 pnorm(trans[2], trans[5], trans[8]);
		std::vector<SortedMeshSlot> sortedSlots(leafs.size());
		// Generate all SortedMeshSlot corresponding to all the leafs nodes.
		std::transform(leafs.begin(), leafs.end(), sortedSlots.begin(),
		               [&pnorm](RAS_MeshSlotUpwardNode *node) {
			return SortedMeshSlot(node, pnorm);
		});

		std::sort(sortedSlots.begin(), sortedSlots.end(), backtofront());

		std::vector<SortedMeshSlot>::const_iterator it = sortedSlots.begin();
		RAS_MeshSlotUpwardNodeIterator iterator((it++)->m_node);
		for (std::vector<SortedMeshSlot>::const_iterator end = sortedSlots.end(); it != end; ++it) {
			iterator.NextNode(it->m_node);
		}
	}
}

void RAS_BucketManager::RenderBasicBuckets(RAS_Rasterizer *rasty, RAS_BucketManager::BucketType bucketType)
{
	PrepareBuckets(rasty, bucketType);

	RAS_UpwardTreeLeafs leafs;
	for (RAS_MaterialBucket *bucket : m_buckets[bucketType]) {
		bucket->GenerateTree(m_downwardNode, m_upwardNode, leafs, m_nodeData.m_drawingMode, false);
	}

	if (m_downwardNode.GetValid()) {
		m_nodeData.m_sort = false;
		m_downwardNode.Execute(RAS_DummyNodeTuple());
	}
}

void RAS_BucketManager::Renderbuckets(RAS_Rasterizer::DrawType drawingMode, const mt::mat3x4& cameratrans, RAS_Rasterizer *rasty,
                                      RAS_OffScreen *offScreen)
{
	m_nodeData.m_rasty = rasty;
	m_nodeData.m_trans = cameratrans;
	m_nodeData.m_drawingMode = drawingMode;

	switch (drawingMode) {
		case RAS_Rasterizer::RAS_SHADOW:
		{
			const bool isVarianceShadow = rasty->GetShadowMode() == RAS_Rasterizer::RAS_SHADOW_VARIANCE;

			rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_ENABLED);

			/* Rendering solid regular materials with an override shader for
			 * variance shadow or an empty shader.
			 */

			m_nodeData.m_shaderOverride = true;
			if (!m_buckets[SOLID_SHADOW_BUCKET].empty()) {
				rasty->SetOverrideShader(isVarianceShadow ?
				                         RAS_Rasterizer::RAS_OVERRIDE_SHADER_SHADOW_VARIANCE :
				                         RAS_Rasterizer::RAS_OVERRIDE_SHADER_BLACK);
			}
			RenderBasicBuckets(rasty, SOLID_SHADOW_BUCKET);

			/* Rendering solid instancing materials with a different override
			 * shader for variance and simple shadow.
			 */

			if (!m_buckets[SOLID_SHADOW_INSTANCING_BUCKET].empty()) {
				rasty->SetOverrideShader(isVarianceShadow ?
				                         RAS_Rasterizer::RAS_OVERRIDE_SHADER_SHADOW_VARIANCE_INSTANCING :
				                         RAS_Rasterizer::RAS_OVERRIDE_SHADER_BLACK_INSTANCING);
			}
			RenderBasicBuckets(rasty, SOLID_SHADOW_INSTANCING_BUCKET);

			if (isVarianceShadow) {
				/* Rendering alpha shadow instancing materials with an override
				 * shader for variance shadow.
				 */

				if (!m_buckets[ALPHA_SHADOW_INSTANCING_BUCKET].empty()) {
					rasty->SetOverrideShader(RAS_Rasterizer::RAS_OVERRIDE_SHADER_SHADOW_VARIANCE_INSTANCING);
				}
				RenderBasicBuckets(rasty, ALPHA_SHADOW_INSTANCING_BUCKET);

				/* Rendering alpha shadow regular materials with an override
				 * shader for variance shadow and ordering.
				 */

				if (!m_buckets[ALPHA_SHADOW_BUCKET].empty()) {
					rasty->SetOverrideShader(RAS_Rasterizer::RAS_OVERRIDE_SHADER_SHADOW_VARIANCE);
				}
				RenderBasicBuckets(rasty, ALPHA_SHADOW_BUCKET);

				rasty->SetOverrideShader(RAS_Rasterizer::RAS_OVERRIDE_SHADER_NONE);
			}
			else {
				// Rendering alpha shadow materials (including instancing) with their shaders.

				rasty->SetOverrideShader(RAS_Rasterizer::RAS_OVERRIDE_SHADER_NONE);
				m_nodeData.m_shaderOverride = false;

				RenderBasicBuckets(rasty, ALPHA_SHADOW_INSTANCING_BUCKET);
				// Render alpha shadow regular materials with ordering.
				RenderBasicBuckets(rasty, ALPHA_SHADOW_BUCKET);
			}

			break;
		}
		case RAS_Rasterizer::RAS_COLLISION_DEPTH:
		{
			/* Depth-only pass for GPU particle Screen-Space collision, restricted by the caller
			 * (KX_KetsjiEngine::RenderCollisionDepthBuffer) to only the objects flagged
			 * use_gpu_particle_collider -- unlike RAS_SHADOW, this reuses SOLID_BUCKET/
			 * SOLID_INSTANCING_BUCKET (every opaque material, structurally, no per-material
			 * flag gate) so a collider object doesn't also need "cast shadow" on its material. */
			m_nodeData.m_shaderOverride = true;
			rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_ENABLED);

			if (!m_buckets[SOLID_BUCKET].empty()) {
				rasty->SetOverrideShader(RAS_Rasterizer::RAS_OVERRIDE_SHADER_BLACK);
			}
			RenderBasicBuckets(rasty, SOLID_BUCKET);

			if (!m_buckets[SOLID_INSTANCING_BUCKET].empty()) {
				rasty->SetOverrideShader(RAS_Rasterizer::RAS_OVERRIDE_SHADER_BLACK_INSTANCING);
			}
			RenderBasicBuckets(rasty, SOLID_INSTANCING_BUCKET);

			rasty->SetOverrideShader(RAS_Rasterizer::RAS_OVERRIDE_SHADER_NONE);
			break;
		}
		case RAS_Rasterizer::RAS_WIREFRAME:
		{
			m_nodeData.m_shaderOverride = true;
			rasty->SetLines(true);
			rasty->SetLinesWidth(2.0f);
			rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_ENABLED);

			// Rendering solid regular materials with an empty override shader.

			if (!m_buckets[SOLID_BUCKET].empty()) {
				rasty->SetOverrideShader(RAS_Rasterizer::RAS_OVERRIDE_SHADER_BLACK);
			}
			RenderBasicBuckets(rasty, SOLID_BUCKET);

			/* Rendering solid, alpha and alpha depth instancing materials
			 * with an override shader.
			 */

			if ((m_buckets[SOLID_INSTANCING_BUCKET].size() + m_buckets[ALPHA_INSTANCING_BUCKET].size()) > 0) {
				rasty->SetOverrideShader(RAS_Rasterizer::RAS_OVERRIDE_SHADER_BLACK_INSTANCING);
			}
			RenderBasicBuckets(rasty, SOLID_INSTANCING_BUCKET);
			RenderSortedBuckets(rasty, ALPHA_INSTANCING_BUCKET);

			/* Rendering alpha and alpha depth regular materials with
			 * an empty shader and ordering.
			 */

			if (!m_buckets[ALPHA_BUCKET].empty()) {
				rasty->SetOverrideShader(RAS_Rasterizer::RAS_OVERRIDE_SHADER_BLACK);
			}
			RenderSortedBuckets(rasty, ALPHA_BUCKET);

			rasty->SetOverrideShader(RAS_Rasterizer::RAS_OVERRIDE_SHADER_NONE);

			rasty->SetLines(false);
			rasty->SetLinesWidth(1.0f);
			break;
		}
		case RAS_Rasterizer::RAS_TEXTURED:
		{
			/* Rendering solid and alpha (regular and instancing) materials
			 * with their shaders.
			 */
			m_nodeData.m_shaderOverride = false;
			rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_ENABLED);

			RenderBasicBuckets(rasty, SOLID_BUCKET);
			RenderBasicBuckets(rasty, SOLID_INSTANCING_BUCKET);

			rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_DISABLED);

			// Update depth transparency depth texture after rendering all solid materials.
			if ((m_buckets[ALPHA_DEPTH_BUCKET].size() + m_buckets[ALPHA_DEPTH_INSTANCING_BUCKET].size()) > 0) {
				KX_KetsjiEngine *ketsji = KX_GetActiveEngine();
				RAS_ICanvas* canvas = ketsji->GetCanvas();
				rasty->UpdateGlobalDepthTexture(offScreen, canvas);
			}

			// Z-prepass: write depth for alpha-cutout/clip materials (Clip, Alpha-to-Coverage)
			// so the color pass below benefits from real hardware early-Z rejection on
			// overlapping overdraw (e.g. stacked foliage). Reads the CUTOUT-only subset of
			// ALPHA_DEPTH_BUCKET (see FindBucket()) -- smooth alpha-blended "Depth Transparency"
			// materials are excluded and unaffected.
			if ((m_buckets[ALPHA_DEPTH_CUTOUT_BUCKET].size() + m_buckets[ALPHA_DEPTH_CUTOUT_INSTANCING_BUCKET].size()) > 0) {
				rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_ENABLED);
				rasty->SetColorMask(false, false, false, false);

				RenderBasicBuckets(rasty, ALPHA_DEPTH_CUTOUT_INSTANCING_BUCKET);
				RenderBasicBuckets(rasty, ALPHA_DEPTH_CUTOUT_BUCKET);

				rasty->SetColorMask(true, true, true, true);
				rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_DISABLED);
			}

			RenderBasicBuckets(rasty, ALPHA_INSTANCING_BUCKET);
			RenderSortedBuckets(rasty, ALPHA_BUCKET);


			rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_ENABLED);
			break;
		}
		case RAS_Rasterizer::RAS_RENDERER:
		{
			/* Rendering solid and alpha (regular and instancing) materials
			 * with their shaders.
			 */

			m_nodeData.m_shaderOverride = false;
			rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_ENABLED);

			RenderBasicBuckets(rasty, SOLID_BUCKET);
			RenderBasicBuckets(rasty, SOLID_INSTANCING_BUCKET);

			rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_DISABLED);

			// Don't use depth transparency because the renderer could not offer a depth texture.
			rasty->ResetGlobalDepthTexture();

			// Z-prepass: write depth for alpha-cutout/clip materials (Clip, Alpha-to-Coverage)
			// so the color pass below benefits from real hardware early-Z rejection on
			// overlapping overdraw (e.g. stacked foliage). Reads the CUTOUT-only subset of
			// ALPHA_DEPTH_BUCKET (see FindBucket()) -- smooth alpha-blended "Depth Transparency"
			// materials are excluded and unaffected.
			if ((m_buckets[ALPHA_DEPTH_CUTOUT_BUCKET].size() + m_buckets[ALPHA_DEPTH_CUTOUT_INSTANCING_BUCKET].size()) > 0) {
				rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_ENABLED);
				rasty->SetColorMask(false, false, false, false);

				RenderBasicBuckets(rasty, ALPHA_DEPTH_CUTOUT_INSTANCING_BUCKET);
				RenderBasicBuckets(rasty, ALPHA_DEPTH_CUTOUT_BUCKET);

				rasty->SetColorMask(true, true, true, true);
				rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_DISABLED);
			}

			RenderBasicBuckets(rasty, ALPHA_INSTANCING_BUCKET);
			RenderSortedBuckets(rasty, ALPHA_BUCKET);

			rasty->SetDepthMask(RAS_Rasterizer::RAS_DEPTHMASK_ENABLED);
			break;
		}
		default:
		{
			break;
		}
	}

	for (RAS_MaterialBucket *bucket : m_buckets[ALL_BUCKET]) {
		bucket->RemoveActiveMeshSlots();
	}

	rasty->SetClientObject(nullptr);
}

RAS_MaterialBucket *RAS_BucketManager::FindBucket(RAS_IMaterial *material, bool &bucketCreated)
{
	bucketCreated = false;

	for (RAS_MaterialBucket *bucket : m_buckets[ALL_BUCKET]) {
		if (bucket->GetMaterial() == material) {
			return bucket;
		}
	}

	RAS_MaterialBucket *bucket = new RAS_MaterialBucket(material);
	bucketCreated = true;

	const bool useinstancing = material->UseInstancing();
	if (!material->OnlyShadow()) {
		if (material->IsAlpha()) {
			m_buckets[useinstancing ? ALPHA_INSTANCING_BUCKET : ALPHA_BUCKET].push_back(bucket);
			if (material->IsAlphaDepth()) {
				m_buckets[useinstancing ? ALPHA_DEPTH_INSTANCING_BUCKET : ALPHA_DEPTH_BUCKET].push_back(bucket);

				/* IsAlphaDepth() (the "Depth Transparency" material checkbox, MA_DEPTH_TRANSP)
				 * is independent of the alpha blend mode -- it can be set on a plain smooth
				 * "Alpha Blend" material too, not just cutout ones. Only true cutout materials
				 * (binary alpha via discard/A2C: IsAlphaShadow() == CLIP/ALPHA_TO_COVERAGE) are
				 * safe for the Z-prepass, which writes real hardware depth for every fragment
				 * regardless of alpha -- doing that for a smooth alpha-blended material corrupts
				 * it (overlapping soft-alpha quads, e.g. particle smoke, get partially
				 * depth-culled by each other's nearly-transparent regions, producing broken/
				 * blocky fragments instead of a smoothly blended result). So the Z-prepass reads
				 * from this narrower bucket instead of ALPHA_DEPTH_BUCKET itself. */
				if (material->IsAlphaShadow()) {
					m_buckets[useinstancing ? ALPHA_DEPTH_CUTOUT_INSTANCING_BUCKET : ALPHA_DEPTH_CUTOUT_BUCKET].push_back(bucket);
				}
			}
		}
		else {
			m_buckets[useinstancing ? SOLID_INSTANCING_BUCKET : SOLID_BUCKET].push_back(bucket);
		}
	}
	if (material->CastsShadows()) {
		if (material->IsAlphaShadow()) {
			m_buckets[useinstancing ? ALPHA_SHADOW_INSTANCING_BUCKET : ALPHA_SHADOW_BUCKET].push_back(bucket);
		}
		else {
			m_buckets[useinstancing ? SOLID_SHADOW_INSTANCING_BUCKET : SOLID_SHADOW_BUCKET].push_back(bucket);
		}
	}

	// Used to free the bucket.
	m_buckets[ALL_BUCKET].push_back(bucket);
	return bucket;
}

RAS_DisplayArrayBucket *RAS_BucketManager::GetTextDisplayArrayBucket() const
{
	return m_text.m_arrayBucket;
}

void RAS_BucketManager::ReloadMaterials(RAS_IMaterial *mat)
{
	for (RAS_MaterialBucket *bucket : m_buckets[ALL_BUCKET]) {
		if (mat == nullptr || (mat == bucket->GetMaterial())) {
			bucket->GetMaterial()->ReloadMaterial();
		}
	}
}

void RAS_BucketManager::RemoveMaterial(RAS_IMaterial *mat)
{
	BucketList& allBuckets = m_buckets[ALL_BUCKET];
	for (BucketList::iterator it = allBuckets.begin(); it != allBuckets.end();) {
		RAS_MaterialBucket *bucket = *it;
		// Find the bucket in ALL_BUCKET list.
		if (mat == bucket->GetMaterial()) {
			// Iterate over all bucket list excepted ALL_BUCKET and remove the bucket.
			for (unsigned short i = 0; i < ALL_BUCKET; ++i) {
				CM_ListRemoveIfFound(m_buckets[i], bucket);
			}
			// Remove the bucket from ALL_BUCKET and destruct it.
			it = allBuckets.erase(it);
			delete bucket;
		}
		else {
			++it;
		}
	}
}

void RAS_BucketManager::Merge(RAS_BucketManager *other, SCA_IScene *scene)
{
	for (unsigned short i = 0; i < NUM_BUCKET_TYPE; ++i) {
		BucketList& buckets = m_buckets[i];
		BucketList& otherbuckets = other->m_buckets[i];

		// Skip the text bucket.
		std::remove_copy(otherbuckets.begin(), otherbuckets.end(), std::back_inserter(buckets), other->m_text.m_bucket);
		otherbuckets.clear();
	}
}
