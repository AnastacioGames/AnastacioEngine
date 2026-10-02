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
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_LightProbe.h
 *  \ingroup ketsji
 *  \brief Local reflection probe: a cube map captured from an object, read by Game PBR materials
 *  (env_probe_mirror in gpu_shader_material.glsl) inside the probe radius instead of the World.
 */

#ifndef __KX_LIGHTPROBE_H__
#define __KX_LIGHTPROBE_H__

#include "KX_CubeMap.h"

struct GPUTexture;

class KX_LightProbe : public KX_CubeMap
{
private:
	/// Cube map owned by the probe (no material texture user, unlike KX_CubeMap).
	GPUTexture *m_cube;
	int m_size;
	float m_radius;
	float m_maxLod;

public:
	/** \param radius Influence radius around the viewpoint object.
	 * \param size Face size in pixels.
	 * \param realtime Capture every frame instead of once.
	 */
	KX_LightProbe(KX_GameObject *viewpoint, float radius, int size, float clipEnd, bool realtime);
	virtual ~KX_LightProbe();

	virtual std::string GetName();

	float GetRadius() const;
	/// The captured cube map, nullptr before the first capture.
	GPUTexture *GetCubeTexture() const;
	float GetMaxLod() const;

	virtual bool SetupCamera(KX_Camera *sceneCamera, KX_Camera *camera);
	virtual void BeginRender(RAS_Rasterizer *rasty);
	virtual void EndRender(RAS_Rasterizer *rasty);
};

#endif  // __KX_LIGHTPROBE_H__
