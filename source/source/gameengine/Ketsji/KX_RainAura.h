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

/** \file KX_RainAura.h
 *  \ingroup ketsji
 *
 * World > Rain > Aura: manga-style still strokes of water that pop in and out on the upper
 * part of the silhouette (seen from the active camera) of every object carrying the aura
 * game property. Sharp mesh edges are read once per mesh; each frame the silhouette is found
 * in object space, and every live stroke goes into one dynamic vertex buffer drawn with a
 * single call. Static style: strokes stand still and live 15-50 ms. Animated style: each drop
 * leaves the outline and travels a longer, slightly falling path for 0.25-0.55 s, fading out.
 */

#ifndef __KX_RAINAURA_H__
#define __KX_RAINAURA_H__

#include "mathfu.h"

#include <string>
#include <unordered_map>
#include <vector>

class KX_Scene;
class KX_Camera;
class KX_GameObject;
class RAS_Mesh;
struct World;

class KX_RainAura
{
public:
	KX_RainAura();
	~KX_RainAura();

	/// Once per frame, after the final transforms. Spawns and expires strokes.
	void Update(KX_Scene *scene, KX_Camera *camera, const World *world, double time);
	/// Draws every live stroke with one call (additive, depth tested, no depth write).
	void Draw(const mt::mat4& view, const mt::mat4& projection);
	/// Drops a deleted object from the target list before its pointer dangles.
	void RemoveObject(KX_GameObject *gameobj);

private:
	struct Edge {
		mt::vec3 a, b, n1, n2;
	};
	struct Silhouette {
		mt::vec3 a, b, out, view;
		/// Stroke scale: strokes keep the same size on screen at any distance.
		float scale;
	};
	struct Stroke {
		/// Tail of the stroke; the head is base + dir * length.
		mt::vec3 base, dir;
		/// World velocity (animated style only, zero when static).
		mt::vec3 velocity;
		float width, length, brightness, fall;
		double birth, death;
	};

	void RefreshTargets(KX_Scene *scene, const std::string& prop);
	const std::vector<Edge>& GetEdges(RAS_Mesh *mesh);
	float Random();
	bool EnsureGL();

	std::vector<KX_GameObject *> m_targets;
	std::unordered_map<RAS_Mesh *, std::vector<Edge> > m_edgeCache;
	std::vector<Silhouette> m_silhouette;
	std::vector<float> m_cumulative;
	std::vector<Stroke> m_strokes;
	std::vector<float> m_vertices;
	std::string m_prop;
	double m_lastTime;
	bool m_animated;
	double m_nextScan;
	float m_carry;
	float m_intensity;
	unsigned int m_seed;

	unsigned int m_program;
	unsigned int m_vao;
	unsigned int m_vbo;
	unsigned int m_ibo;
	int m_viewLoc;
	int m_projLoc;
	int m_intensityLoc;
	bool m_glFailed;
};

#endif  // __KX_RAINAURA_H__
