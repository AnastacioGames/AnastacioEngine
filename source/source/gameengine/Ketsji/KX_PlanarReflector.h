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

/** \file KX_PlanarReflector.h
 *  \ingroup ketsji
 *  \brief Planar reflection owned by the Planar Reflection material node (Shader Editor), as
 *  opposed to the legacy KX_PlanarMap created from an EnvMap texture slot (ENV_REALT). Same
 *  mirrored-camera rendering as KX_PlanarMap (Lengyel oblique near plane, inverted front faces),
 *  but owns its own 2D GPUTexture instead of a material texture user, and caches the capturing
 *  camera's view*projection matrix so the node's GLSL (node_planar_reflection in
 *  gpu_shader_material.glsl) can project a screen-space UV from any fragment's world position.
 *  Bound per object by GPU_material_bind_planar(), called from BL_BlenderShader::Update() when
 *  KX_TextureRendererManager::FindPlanarReflector() finds one for that object (see
 *  BL_BlenderDataConversion.cpp for how one gets created from the node's sockets).
 */

#ifndef __KX_PLANAR_REFLECTOR_H__
#define __KX_PLANAR_REFLECTOR_H__

#include "KX_PlanarMap.h"

struct GPUTexture;

class KX_PlanarReflector : public KX_PlanarMap
{
private:
	/// 2D render target owned here (no material texture user, unlike KX_PlanarMap).
	GPUTexture *m_tex;
	int m_size;
	/// Capturing camera's projection * view of the last render, read by node_planar_reflection().
	mt::mat4 m_viewProjection;

public:
	KX_PlanarReflector(KX_GameObject *viewpoint, int size, float clipEnd);
	virtual ~KX_PlanarReflector();

	virtual std::string GetName();

	/// The captured 2D texture, nullptr before the first capture.
	GPUTexture *GetTexture() const;
	const mt::mat4& GetViewProjection() const;

	virtual bool SetupCamera(KX_Camera *sceneCamera, KX_Camera *camera) override;
	virtual void BeginRender(RAS_Rasterizer *rasty) override;
	virtual void EndRender(RAS_Rasterizer *rasty) override;
	virtual void SetFrameViewProjection(const mt::mat4& view, const mt::mat4& projection) override;
};

#endif  // __KX_PLANAR_REFLECTOR_H__
