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
 * front of the camera and a flickering flash. The bolt is one continuous camera-facing
 * ribbon per channel with a soft gaussian profile and round ends, drawn with one call;
 * the flash is applied by the rain 2D filter (ge_RainLightning).
 */

#ifndef __KX_RAINLIGHTNING_H__
#define __KX_RAINLIGHTNING_H__

#include "mathfu.h"

#include "BKE_rain_lightning.h"

#include <vector>

class KX_Camera;
struct World;

class KX_RainLightning
{
public:
	KX_RainLightning();
	~KX_RainLightning();

	/// Once per frame: follows the automatic schedule and the manual strikes.
	void Update(KX_Camera *camera, const World *world, double time);
	/// A strike on the next Update (world.strikeLightning()).
	void Strike(bool bolt);
	/// Draws the bolt while it is lit (additive, depth tested, no depth write).
	void Draw(const mt::mat4& view, const mt::mat4& projection);
	/// Flash, bolt brightness and bolt position on screen, for the rain filter.
	mt::vec4 GetFilterParams(const mt::mat4& view, const mt::mat4& projection) const;

private:
	bool EnsureGL();

	RainLightningBolt m_bolt;
	bool m_hasBolt;
	double m_start;
	unsigned int m_seed;
	bool m_big;
	bool m_pending;
	bool m_pendingBig;
	bool m_hasManual;
	double m_manualStart;
	unsigned int m_manualSeed;
	bool m_manualBig;
	unsigned int m_manualCount;
	float m_flash;
	float m_boltBright;
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
	bool m_glFailed;
};

#endif  // __KX_RAINLIGHTNING_H__
