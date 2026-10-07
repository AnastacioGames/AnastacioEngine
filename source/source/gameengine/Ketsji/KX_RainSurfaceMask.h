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

/** \file KX_RainSurfaceMask.h
 *  \ingroup ketsji
 *
 * World > Rain > Ripples/Splash on chosen objects only. When an object carries the game
 * property "ripples_effect" (or "splash_effect", "puddles_effect"), only the objects with it receive that effect;
 * with no object carrying it, the effect stays on every nearby surface as before.
 *
 * The marked meshes are drawn into a small RG32F texture (R = 1 ripples + 2 splash + 4 puddles,
 * G = view depth); the rain filter keeps the effect where that depth matches the scene depth,
 * so an unmarked object in front still hides it. Uses the mesh data at load time, so armature
 * or shape key deformation is not followed.
 */

#ifndef __KX_RAINSURFACEMASK_H__
#define __KX_RAINSURFACEMASK_H__

#include "mathfu.h"

#include <cstring>
#include <unordered_map>
#include <vector>

class KX_Scene;
class KX_GameObject;
class RAS_Mesh;
class KX_Mesh;
struct World;

class KX_RainSurfaceMask
{
public:
	/// Game properties that mark the objects receiving each effect.
	static const char *const RippleProperty;
	static const char *const SplashProperty;
	static const char *const PuddleProperty;

	enum {
		MASK_RIPPLE = 1,
		MASK_SPLASH = 2,
		MASK_PUDDLE = 4
	};

	KX_RainSurfaceMask();
	~KX_RainSurfaceMask();

	/** Draws the marked objects with the current view/projection. Returns which effects
	 * are restricted to the mask (MASK_* bits, 0 = every surface, nothing drawn).
	 */
	int Render(KX_Scene *scene, const World *world, double time, const mt::mat4& view,
	           const mt::mat4& projection, int width, int height);
	unsigned int GetTexture() const;
	/// Drops a deleted object before its pointer dangles.
	void RemoveObject(KX_GameObject *gameobj);

private:
	struct Target {
		KX_GameObject *gameobj;
		int flags;
		bool operator==(const Target& other) const
		{
			return gameobj == other.gameobj && flags == other.flags;
		}
	};
	static bool SameMatrix(const mt::mat4& a, const mt::mat4& b)
	{
		return std::memcmp(a.Data(), b.Data(), sizeof(float) * 16) == 0;
	}
	struct Draw {
		KX_GameObject *gameobj;
		int flags;
		mt::mat4 model;
		std::vector<KX_Mesh *> meshes;
		bool operator==(const Draw& other) const
		{
			return gameobj == other.gameobj && flags == other.flags && SameMatrix(model, other.model) && meshes == other.meshes;
		}
	};
	struct MeshBuffer {
		unsigned int vbo;
		int count;
	};

	void RefreshTargets(KX_Scene *scene);
	const MeshBuffer& GetMeshBuffer(RAS_Mesh *mesh);
	void ClearMeshBuffers();
	bool EnsureGL(int width, int height);

	std::vector<Target> m_targets;
	std::unordered_map<RAS_Mesh *, MeshBuffer> m_meshBuffers;
	int m_flags;
	/// What the texture holds, to skip the redraw when nothing moved.
	std::vector<Draw> m_draws;
	std::vector<Draw> m_drawnItems;
	mt::mat4 m_drawnView;
	mt::mat4 m_drawnProjection;
	int m_drawnWidth = 0;
	int m_drawnHeight = 0;
	bool m_valid = false;
	double m_nextScan;

	unsigned int m_program;
	unsigned int m_vao;
	unsigned int m_fbo;
	unsigned int m_texture;
	unsigned int m_depth;
	int m_width;
	int m_height;
	int m_viewLoc;
	int m_projLoc;
	int m_modelLoc;
	int m_flagsLoc;
	bool m_glFailed;
};

#endif  // __KX_RAINSURFACEMASK_H__
