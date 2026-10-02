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

/** \file KX_DentDeformer.cpp
 *  \ingroup ketsji
 */

#include "KX_DentDeformer.h"

#include "RAS_BoundingBoxManager.h"
#include "RAS_DisplayArray.h"
#include "RAS_Mesh.h"

#include <algorithm>
#include <cfloat>

/// Smooth falloff, 1 at the center and 0 at the radius with zero slope on both ends.
static float falloff(float distance, float radius)
{
	if (distance >= radius) {
		return 0.0f;
	}
	const float t = 1.0f - distance / radius;
	return t * t * (3.0f - 2.0f * t);
}

/// Rotates n by the rotation taking the direction from to the direction to.
static mt::vec3 rotate_between(const mt::vec3& n, const mt::vec3& from, const mt::vec3& to)
{
	const float fromLength = from.Length();
	const float toLength = to.Length();
	if (fromLength < FLT_EPSILON || toLength < FLT_EPSILON) {
		return n;
	}
	const mt::vec3 a = from / fromLength;
	const mt::vec3 b = to / toLength;
	const mt::vec3 c = mt::cross(a, b);
	const float s = c.Length();
	if (s < 1e-6f) {
		return n;
	}
	const float d = mt::dot(a, b);
	const mt::vec3 axis = c / s;
	// Rodrigues.
	return n * d + mt::cross(axis, n) * s + axis * (mt::dot(axis, n) * (1.0f - d));
}

/// Area weighted face normals summed on each vertex of a triangle array.
static void face_sums(RAS_DisplayArray *array, std::vector<mt::vec3>& sums)
{
	sums.assign(array->GetVertexCount(), mt::zero3);
	if (array->GetPrimitiveType() != RAS_DisplayArray::TRIANGLES) {
		return;
	}
	for (unsigned int i = 0, size = array->GetPrimitiveIndexCount(); i + 2 < size; i += 3) {
		const unsigned int i0 = array->GetPrimitiveIndex(i);
		const unsigned int i1 = array->GetPrimitiveIndex(i + 1);
		const unsigned int i2 = array->GetPrimitiveIndex(i + 2);
		const mt::vec3 p0(array->GetPosition(i0));
		const mt::vec3 p1(array->GetPosition(i1));
		const mt::vec3 p2(array->GetPosition(i2));
		// Length = twice the area.
		const mt::vec3 normal = mt::cross(p1 - p0, p2 - p0);
		sums[i0] += normal;
		sums[i1] += normal;
		sums[i2] += normal;
	}
}

KX_DentDeformer::KX_DentDeformer(RAS_Mesh *mesh, RAS_BoundingBoxManager *boundingBoxManager)
	:RAS_Deformer(mesh),
	m_dented(false)
{
	InitializeDisplayArrays();

	// Like every RAS_Deformer: RAS_Mesh::AddMeshUser needs a bounding box (see KX_ImpostorAtlasDeformer).
	m_boundingBox = boundingBoxManager->CreateBoundingBox();
	m_boundingBox->CopyAabb(m_mesh->GetBoundingBox());

	unsigned int numVertices = 0;
	for (const DisplayArraySlot& slot : m_slots) {
		numVertices = std::max(numVertices, slot.m_displayArray->GetMaxOrigIndex() + 1);
	}
	m_restPositions.assign(numVertices, mt::zero3);
	m_restNormals.assign(numVertices, mt::zero3);
	m_offsets.assign(numVertices, mt::zero3);

	m_slotRestNormals.resize(m_slots.size());
	m_slotRestTangents.resize(m_slots.size());
	m_slotRestFaceSums.resize(m_slots.size());
	for (unsigned int s = 0; s < m_slots.size(); ++s) {
		RAS_DisplayArray *array = m_slots[s].m_displayArray;
		std::vector<mt::vec3>& normals = m_slotRestNormals[s];
		normals.resize(array->GetVertexCount());
		std::vector<mt::vec4>& tangents = m_slotRestTangents[s];
		tangents.resize(array->GetVertexCount());
		for (unsigned int i = 0, size = array->GetVertexCount(); i < size; ++i) {
			const unsigned int orig = array->GetVertexInfo(i).GetOrigIndex();
			normals[i] = mt::vec3(array->GetNormal(i));
			tangents[i] = mt::vec4(array->GetTangent(i));
			if (orig < numVertices) {
				m_restPositions[orig] = mt::vec3(array->GetPosition(i));
				m_restNormals[orig] += normals[i];
			}
		}
		face_sums(array, m_slotRestFaceSums[s]);
	}

	for (mt::vec3& normal : m_restNormals) {
		normal = normal.SafeNormalized(mt::axisZ3);
	}
}

KX_DentDeformer::~KX_DentDeformer()
{
}

void KX_DentDeformer::Apply(RAS_DisplayArray *UNUSED(array))
{
}

bool KX_DentDeformer::Update()
{
	return false;
}

void KX_DentDeformer::UpdateBuckets()
{
}

bool KX_DentDeformer::AddDent(const mt::mat3x4& trans, const mt::vec3& point, const mt::vec3& displacement,
                              float radius, float maxDepth)
{
	if (radius <= 0.0f || maxDepth <= 0.0f || displacement.LengthSquared() < FLT_EPSILON * FLT_EPSILON) {
		return false;
	}

	const mt::mat3x4 invtrans = trans.Inverse();
	const mt::vec3 origin = trans * mt::zero3;
	const mt::vec3 invOrigin = invtrans * mt::zero3;
	// The same world displacement in local space.
	const mt::vec3 localDisplacement = invtrans * displacement - invOrigin;

	bool moved = false;
	for (unsigned int v = 0, size = m_offsets.size(); v < size; ++v) {
		const mt::vec3 world = trans * (m_restPositions[v] + m_offsets[v]);
		const float weight = falloff((world - point).Length(), radius);
		if (weight <= 0.0f) {
			continue;
		}

		mt::vec3& offset = m_offsets[v];
		const mt::vec3 previous = offset;
		offset += localDisplacement * weight;

		const float worldDepth = ((trans * offset) - origin).Length();
		if (worldDepth > maxDepth) {
			offset *= maxDepth / worldDepth;
		}
		// Already at max depth: nothing to upload.
		if ((offset - previous).LengthSquared() > 1e-12f) {
			moved = true;
		}
	}

	if (moved) {
		UpdateArrays();
	}
	return moved;
}

bool KX_DentDeformer::AddBlastDent(const mt::mat3x4& trans, const mt::vec3& center, float radius, float force,
                                   float threshold, float depth, float maxDepth)
{
	if (radius <= 0.0f || maxDepth <= 0.0f || depth <= 0.0f) {
		return false;
	}

	const mt::mat3x4 invtrans = trans.Inverse();
	const mt::vec3 origin = trans * mt::zero3;
	const mt::vec3 invOrigin = invtrans * mt::zero3;

	bool moved = false;
	for (unsigned int v = 0, size = m_offsets.size(); v < size; ++v) {
		const mt::vec3 world = trans * (m_restPositions[v] + m_offsets[v]);
		const mt::vec3 away = world - center;
		const float distance = away.Length();
		if (distance >= radius) {
			continue;
		}

		const float excess = force * (1.0f - distance / radius) - threshold;
		if (excess <= 0.0f) {
			continue;
		}

		// Only the side facing the blast is pushed in.
		const mt::vec3 direction = away.SafeNormalized(mt::axisZ3);
		const mt::vec3 worldNormal = ((trans * m_restNormals[v]) - origin).SafeNormalized(mt::axisZ3);
		const float facing = -mt::dot(worldNormal, direction);
		if (facing <= 0.0f) {
			continue;
		}

		mt::vec3& offset = m_offsets[v];
		const mt::vec3 previous = offset;
		offset += (invtrans * (direction * (excess * depth * facing)) - invOrigin);

		const float worldDepth = ((trans * offset) - origin).Length();
		if (worldDepth > maxDepth) {
			offset *= maxDepth / worldDepth;
		}
		// Already at max depth: nothing to upload.
		if ((offset - previous).LengthSquared() > 1e-12f) {
			moved = true;
		}
	}

	if (moved) {
		UpdateArrays();
	}
	return moved;
}

void KX_DentDeformer::Reset()
{
	if (!m_dented) {
		return;
	}
	std::fill(m_offsets.begin(), m_offsets.end(), mt::zero3);
	UpdateArrays();
	m_dented = false;
}

bool KX_DentDeformer::IsDented() const
{
	return m_dented;
}

void KX_DentDeformer::UpdateArrays()
{
	m_dented = true;

	mt::vec3 aabbMin(FLT_MAX);
	mt::vec3 aabbMax(-FLT_MAX);

	std::vector<mt::vec3> faceSums;
	for (unsigned int s = 0; s < m_slots.size(); ++s) {
		RAS_DisplayArray *array = m_slots[s].m_displayArray;
		const unsigned int vertexCount = array->GetVertexCount();

		for (unsigned int i = 0; i < vertexCount; ++i) {
			const unsigned int orig = array->GetVertexInfo(i).GetOrigIndex();
			if (orig >= m_offsets.size()) {
				continue;
			}
			const mt::vec3 position = m_restPositions[orig] + m_offsets[orig];
			array->SetPosition(i, position);
			aabbMin = mt::vec3::Min(aabbMin, position);
			aabbMax = mt::vec3::Max(aabbMax, position);
		}

		face_sums(array, faceSums);
		const std::vector<mt::vec3>& restNormals = m_slotRestNormals[s];
		const std::vector<mt::vec4>& restTangents = m_slotRestTangents[s];
		const std::vector<mt::vec3>& restFaceSums = m_slotRestFaceSums[s];
		for (unsigned int i = 0; i < vertexCount; ++i) {
			array->SetNormal(i, rotate_between(restNormals[i], restFaceSums[i], faceSums[i]));
			const mt::vec4& tangent = restTangents[i];
			const mt::vec3 rotated = rotate_between(tangent.xyz(), restFaceSums[i], faceSums[i]);
			array->SetTangent(i, mt::vec4(rotated, tangent.w));
		}

		array->NotifyUpdate(RAS_DisplayArray::POSITION_MODIFIED | RAS_DisplayArray::NORMAL_MODIFIED |
		                    RAS_DisplayArray::TANGENT_MODIFIED);
	}

	if (aabbMin.x <= aabbMax.x) {
		m_boundingBox->ExtendAabb(aabbMin, aabbMax);
	}
}
