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
 * The Original Code is Copyright (C) 2026 by Range Engine.
 * All rights reserved.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_RainShelterMap.h
 *  \ingroup ketsji
 *
 * World > Rain under a roof: objects with the game property "rain_shelter" (a tunnel, a bridge,
 * a porch) keep the rain off whatever is below them. They are drawn from above, around the
 * camera, into a small R32F texture holding the height of the highest shelter surface; the rain
 * filter drops the streaks, ripples, splash and puddles at points below that height. Any shape
 * works (curved tunnels included) and the shelter objects may be invisible.
 */

#ifndef __KX_RAINSHELTERMAP_H__
#define __KX_RAINSHELTERMAP_H__

#include "mathfu.h"

#include <unordered_map>
#include <vector>

class KX_Scene;
class KX_GameObject;
class KX_Mesh;
class RAS_Mesh;

class KX_RainShelterMap
{
public:
	static const char *const ShelterProperty;

	KX_RainShelterMap();
	~KX_RainShelterMap();

	/** Draws the shelters around the camera position. Returns false when there is no shelter.
	 * area = map center x, y, 1 / map size (m), 1 = valid.
	 */
	bool Render(KX_Scene *scene, double time, const mt::vec3& camPos, float area[4]);
	unsigned int GetTexture() const;
	/// Drops a deleted object before its pointer dangles.
	void RemoveObject(KX_GameObject *gameobj);

private:
	struct Draw {
		KX_GameObject *gameobj;
		mt::mat4 model;
		std::vector<KX_Mesh *> meshes;
		bool operator==(const Draw& other) const;
	};
	struct MeshBuffer {
		unsigned int vbo;
		int count;
	};

	void RefreshTargets(KX_Scene *scene);
	const MeshBuffer& GetMeshBuffer(RAS_Mesh *mesh);
	void ClearMeshBuffers();
	bool EnsureGL();

	std::vector<KX_GameObject *> m_targets;
	std::unordered_map<RAS_Mesh *, MeshBuffer> m_meshBuffers;
	std::vector<Draw> m_draws;
	std::vector<Draw> m_drawnItems;
	float m_drawnCenter[2];
	bool m_valid;
	double m_nextScan;

	unsigned int m_program;
	unsigned int m_vao;
	unsigned int m_fbo;
	unsigned int m_texture;
	unsigned int m_depth;
	int m_viewProjLoc;
	int m_modelLoc;
	bool m_glFailed;
};

#endif  // __KX_RAINSHELTERMAP_H__
