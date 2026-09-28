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

#ifndef __KX_NAVMESHOBJECT_H__
#define __KX_NAVMESHOBJECT_H__

#include "DetourNavMesh.h"
#include "DetourNavMeshQuery.h"
#include "KX_GameObject.h"

#include <map>

class dtTileCache;
struct dtTileCacheAlloc;
struct dtTileCacheCompressor;
struct dtTileCacheMeshProcess;
struct KX_NavMeshObstacle;

class KX_NavMeshObject : public KX_GameObject
{
	Py_Header

protected:
	dtNavMesh *m_navMesh;
	dtNavMeshQuery *m_navQuery;

	/* Dynamic navmesh (opt-in by the Boolean game property "dynamic_navmesh"): the navmesh is
	 * rebuilt in tiles through a DetourTileCache so obstacles can carve it at runtime. */
	bool m_dynamic;
	dtTileCache *m_tileCache;
	dtTileCacheAlloc *m_tileAlloc;
	dtTileCacheCompressor *m_tileComp;
	dtTileCacheMeshProcess *m_tileMeshProc;

	/// Tile cache obstacle of each obstacle object and the world position it was carved at.
	struct NavObstacle
	{
		unsigned int ref;
		mt::vec3 pos;
		float radius;
	};
	std::map<KX_GameObject *, NavObstacle> m_obstacleRefs;
	/// Incremented when the navmesh is rebuilt or its tiles finish changing, so paths can be redone.
	unsigned int m_version;
	/// Obstacle requests were issued and the tiles aren't rebuilt yet.
	bool m_tilesDirty;

	void FreeNavMesh();
	bool IsDynamicRequested();
	bool BuildNavMeshTiled();

	bool BuildVertIndArrays(float *&vertices, int& nverts,
	                        unsigned short * &polys, int& npolys, unsigned short *&dmeshes,
	                        float *&dvertices, int &ndvertsuniq, unsigned short * &dtris,
	                        int& ndtris, int &vertsPerPoly);

public:
	using PathType = std::vector<mt::vec3, mt::simd_allocator<mt::vec3> >;

	enum NavMeshRenderMode
	{
		RM_WALLS,
		RM_POLYS,
		RM_TRIS,
		RM_MAX
	};

	KX_NavMeshObject(void *sgReplicationInfo, SG_Callbacks callbacks);
	virtual ~KX_NavMeshObject();

	virtual EXP_Value *GetReplica();
	virtual void ProcessReplica();
	virtual int GetGameObjectType() const;

	bool BuildNavMesh();
	bool IsDynamic() const;
	dtTileCache *GetTileCache() const;
	unsigned int GetVersion() const;
	/// Carves the obstacle objects into the dynamic navmesh and rebuilds the touched tiles.
	void UpdateObstacles(const std::vector<KX_NavMeshObstacle>& obstacles);
	dtNavMesh *GetNavMesh() const;
	dtNavMeshQuery *GetNavMeshQuery() const;

	PathType FindPath(const mt::vec3& from, const mt::vec3& to, unsigned int maxPathLen) const;
	float Raycast(const mt::vec3& from, const mt::vec3& to) const;

	void DrawNavMesh(NavMeshRenderMode mode) const;
	void DrawPath(const PathType& path, const mt::vec4& color) const;

	mt::vec3 TransformToLocalCoords(const mt::vec3& wpos) const;
	mt::vec3 TransformToWorldCoords(const mt::vec3& lpos) const;

#ifdef WITH_PYTHON

	EXP_PYMETHOD_DOC(KX_NavMeshObject, findPath);
	EXP_PYMETHOD_DOC(KX_NavMeshObject, raycast);
	EXP_PYMETHOD_DOC(KX_NavMeshObject, draw);
	EXP_PYMETHOD_DOC_NOARGS(KX_NavMeshObject, rebuild);
	EXP_PYMETHOD_DOC(KX_NavMeshObject, addObstacle);
	EXP_PYMETHOD_DOC_O(KX_NavMeshObject, removeObstacle);

	static PyObject *pyattr_get_dynamic(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_version(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);

#endif  // WITH_PYTHON
};

#endif  // __KX_NAVMESHOBJECT_H__
