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

/** \file KX_DentDeformer.h
 *  \ingroup ketsji
 *
 * Native impact deformation (Object.gameflag2 & OB_DEFORMABLE, settings in Object.deform): a private
 * copy of the mesh display arrays per instance, so a dent never shows on the other objects sharing
 * the mesh. The offsets are kept per original (Blender) vertex: the copies split on UV seams and
 * hard edges move together, the mesh never cracks and the UVs stay untouched. The normals are rotated
 * by the change of their adjacent faces, which keeps hard edges and custom normals, and the tangents
 * (normal maps) with them.
 *
 * Nothing runs per frame: the arrays only change on a dent (see KX_DestructionManager).
 */

#ifndef __KX_DENT_DEFORMER_H__
#define __KX_DENT_DEFORMER_H__

#include "RAS_Deformer.h"
#include "mathfu.h"

#include <vector>

class RAS_Mesh;
class RAS_BoundingBoxManager;

class KX_DentDeformer : public RAS_Deformer
{
public:
	KX_DentDeformer(RAS_Mesh *mesh, RAS_BoundingBoxManager *boundingBoxManager);
	virtual ~KX_DentDeformer();

	virtual void Apply(RAS_DisplayArray *array);
	virtual bool Update();
	virtual void UpdateBuckets();

	/** Push the vertices around a world point by a world displacement, smooth falloff to 0 at radius.
	 * \param trans World transform of the object.
	 * \param maxDepth Most a vertex moves from its rest position (world units), all dents summed.
	 * \return True when a vertex moved.
	 */
	bool AddDent(const mt::mat3x4& trans, const mt::vec3& point, const mt::vec3& displacement, float radius,
	             float maxDepth);

	/** Dent from an explosion: the vertices facing the center are pushed away from it by
	 * (force * (1 - distance / radius) - threshold) * depth.
	 * \return True when a vertex moved.
	 */
	bool AddBlastDent(const mt::mat3x4& trans, const mt::vec3& center, float radius, float force, float threshold,
	                  float depth, float maxDepth);

	/** Bend the part of the mesh past a world point around it, like a hit pole or sign.
	 * \param axis Local long axis (0 X, 1 Y, 2 Z); the vertices further along it than the point turn.
	 * \param direction World push direction, its part along the axis is ignored.
	 * \param angle Bend added by this hit (radians); the bend of all hits is capped at maxAngle.
	 * 
eturn True when a vertex moved.
	 */
	bool AddBend(const mt::mat3x4& trans, const mt::vec3& point, const mt::vec3& direction, int axis, float angle,
	             float maxAngle);

	/** Remember a hit for the material Damage node (mask around the point, in object space).
	 * Hits closer than half the radius merge; past MAX_HITS the weakest one is replaced.
	 * \param strength 0..1, summed with the hits it merges with.
	 */
	void AddHit(const mt::mat3x4& trans, const mt::vec3& point, float radius, float strength);

	enum {
		MAX_HITS = 16
	};

	/// Hits as (local x, y, z, radius) and strength, valid up to GetHitCount().
	const float (*GetHits() const)[4];
	const float *GetHitStrengths() const;
	int GetHitCount() const;

	/// Back to the rest shape, hits cleared.
	void Reset();

	bool IsDented() const;

private:
	/// Writes rest + offset to every array, rotates the normals, extends the bounding box.
	void UpdateArrays();

	/// Rest position and normal of each original vertex, indexed by RAS_VertexInfo::GetOrigIndex().
	std::vector<mt::vec3> m_restPositions;
	std::vector<mt::vec3> m_restNormals;
	/// Local offset of each original vertex.
	std::vector<mt::vec3> m_offsets;

	/// Per slot, per display vertex: rest normal and area weighted sum of its rest face normals.
	std::vector<std::vector<mt::vec3> > m_slotRestNormals;
	std::vector<std::vector<mt::vec3> > m_slotRestFaceSums;
	/// Per slot, per display vertex: rest tangent (normal maps), rotated with the normal.
	std::vector<std::vector<mt::vec4> > m_slotRestTangents;

	/// Bend summed over all hits (radians), capped by AddBend().
	float m_bendAngle;

	float m_hits[MAX_HITS][4];
	float m_hitStrengths[MAX_HITS];
	int m_hitCount;

	bool m_dented;
};

#endif  // __KX_DENT_DEFORMER_H__
