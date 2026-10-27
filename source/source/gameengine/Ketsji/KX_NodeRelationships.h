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
 *
 */

/** \file KX_NodeRelationships.h
 *  \ingroup ketsji
 *  \section KX_NodeRelationships
 * This file provides common concrete implementations of
 * SG_ParentRelation used by the game engine. These are
 * KX_SlowParentRelation a slow parent relationship.
 * KX_NormalParentRelation a normal parent relationship where
 * orientation and position are inherited from the parent by
 * the child.
 * KX_VertexParentRelation only location information is
 * inherited by the child.
 */

#ifndef __KX_NODERELATIONSHIPS_H__
#define __KX_NODERELATIONSHIPS_H__

#include "SG_ParentRelation.h"

#include "mathfu.h"

#include <cmath>

/** Rotation part of a world transform with the scale removed. With a zero scale axis the
 * rotation cannot be recovered, so the caller's fallback (its last orientation) is kept
 * instead of writing non-finite values. */
inline mt::mat3 KX_RotationWithoutScale(const mt::mat3x4& trans, const mt::vec3& scale, const mt::mat3& fallback)
{
	if (scale.x == 0.0f || scale.y == 0.0f || scale.z == 0.0f) {
		return fallback;
	}
	const mt::mat3 rot = trans.RotationMatrix().Scale(mt::vec3(1.0f / scale.x, 1.0f / scale.y, 1.0f / scale.z));
	for (int col = 0; col < 3; ++col) {
		for (int row = 0; row < 3; ++row) {
			if (!std::isfinite(rot(row, col))) {
				return fallback;
			}
		}
	}
	return rot;
}

class KX_NormalParentRelation : public SG_ParentRelation
{
public:
	KX_NormalParentRelation();
	virtual ~KX_NormalParentRelation();

	/// Method inherited from KX_ParentRelation.
	virtual bool UpdateChildCoordinates(SG_Node *child, const SG_Node *parent, bool& parentUpdated);

	/// Method inherited from KX_ParentRelation.
	virtual SG_ParentRelation *NewCopy();
};

class KX_VertexParentRelation : public SG_ParentRelation
{
public:
	KX_VertexParentRelation();
	virtual ~KX_VertexParentRelation();

	/// Method inherited from KX_ParentRelation.
	virtual bool UpdateChildCoordinates(SG_Node *child, const SG_Node *parent, bool& parentUpdated);

	/// Method inherited from KX_ParentRelation.
	virtual SG_ParentRelation *NewCopy();

	virtual bool IsVertexRelation();
};

class KX_SlowParentRelation : public SG_ParentRelation
{
private:
	/// The relaxation coefficient.
	float m_relax;

	/**
	 * Looks like a hack flag to me.
	 * We need to compute valid world coordinates the first
	 * time we update spatial data of the child. This is done
	 * by just doing a normal parent relation the first time
	 * UpdateChildCoordinates is called and then doing the
	 * slow parent relation
	 */
	bool m_initialized;

public:
	KX_SlowParentRelation(float relaxation);
	virtual ~KX_SlowParentRelation();

	/// Method inherited from KX_ParentRelation.
	virtual bool UpdateChildCoordinates(SG_Node *child, const SG_Node *parent, bool& parentUpdated);

	/// Method inherited from KX_ParentRelation.
	virtual SG_ParentRelation *NewCopy();

	float GetTimeOffset();
	void SetTimeOffset(float relaxation);

	virtual bool IsSlowRelation();
};

#endif  // __KX_NODERELATIONSHIPS_H__
