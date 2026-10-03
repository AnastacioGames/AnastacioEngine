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

/** \file KX_RainLightning.h
 *  \ingroup ketsji
 *
 * World > Rain > Lightning: automatic (or Python) strikes with a branching bolt far in
 * front of the camera and a flickering flash. Lightning emitters (Empties with
 * Object Data > Lightning) add strikes that fall inside their own area, automatically
 * or when the logic asks. Every bolt is one continuous camera-facing ribbon per channel
 * with a soft gaussian profile and round ends; the flash is applied by the rain 2D
 * filter (ge_RainLightning).
 */

#ifndef __KX_RAINLIGHTNING_H__
#define __KX_RAINLIGHTNING_H__

#include "mathfu.h"

#include "BKE_rain_lightning.h"

#include <vector>

class KX_Camera;
class KX_GameObject;
class KX_Scene;
struct World;

class KX_RainLightning
{
public:
	KX_RainLightning();
	~KX_RainLightning();

	/// Once per frame: follows the automatic schedules and the manual strikes.
	void Update(KX_Scene *scene, KX_Camera *camera, const World *world, double time);
	/// A World strike on the next Update (world.strikeLightning()).
	void Strike(bool bolt);
	/// Lightning emitters (Empties flagged use_lightning).
	void AddEmitter(KX_GameObject *gameobj);
	void RemoveObject(KX_GameObject *gameobj);
	bool HasEmitter(KX_GameObject *gameobj) const;
	/// A strike of the emitter on the next Update (obj.strikeLightning(), Edit Object actuator).
	void StrikeAt(KX_GameObject *gameobj, bool bolt);
	/// Moves the emitters of a merged scene here.
	void TakeEmitters(KX_RainLightning& other);
	/// Draws the bolts while they are lit (additive, depth tested, no depth write).
	void Draw(const mt::mat4& view, const mt::mat4& projection);
	/// Flash, bolt brightness and bolt position on screen, for the rain filter.
	mt::vec4 GetFilterParams(const mt::mat4& view, const mt::mat4& projection) const;

private:
	/// One lit strike: the World one or the latest of an emitter.
	struct StrikeState {
		RainLightningBolt bolt;
		bool hasBolt = false;
		double start = -1.0;
		unsigned int seed = 0;
		bool big = false;
		float flash = 0.0f;
		float boltBright = 0.0f;
		mt::vec3 center = mt::zero3;
		mt::vec3 color = mt::vec3(0.65f, 0.72f, 1.0f);
	};
	/// Strikes asked by the logic; the latest one wins over the automatic schedule.
	struct Manual {
		bool pending = false;
		bool pendingBig = true;
		bool has = false;
		double start = 0.0;
		unsigned int seed = 0;
		bool big = false;
		unsigned int count = 0;

		void Take(double time, unsigned int salt);
	};
	struct Emitter {
		KX_GameObject *gameobj;
		Manual manual;
		StrikeState strike;
	};

	Emitter *FindEmitter(KX_GameObject *gameobj);
	void UpdateEmitter(KX_Scene *scene, Emitter& emitter, double time);
	void DrawStrike(const StrikeState& strike);
	bool EnsureGL();

	StrikeState m_world;
	Manual m_worldManual;
	std::vector<Emitter> m_emitters;
	mt::vec3 m_camPos;

	std::vector<float> m_vertices;
	std::vector<unsigned int> m_indices;
	unsigned int m_program;
	unsigned int m_vao;
	unsigned int m_vbo;
	unsigned int m_ibo;
	int m_viewLoc;
	int m_projLoc;
	int m_brightLoc;
	int m_colorLoc;
	bool m_glFailed;
};

#endif  // __KX_RAINLIGHTNING_H__
