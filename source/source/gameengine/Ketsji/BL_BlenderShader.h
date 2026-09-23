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
 * The Original Code is Copyright (C) Blender Foundation
 * All rights reserved.
 *
 * The Original Code is: all of this file.
 *
 * Contributor(s): none yet.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file BL_BlenderShader.h
 *  \ingroup ketsji
 */

#ifndef __BL_BLENDERSHADER_H__
#define __BL_BLENDERSHADER_H__

#include "RAS_AttributeArray.h"
#include "RAS_Mesh.h"
#include "RAS_Texture.h" // for MaxUnits
#include "RAS_InstancingBuffer.h"

#include "CM_Update.h"

#include <string>

struct Material;
struct Scene;
struct GPUMaterial;
class KX_Scene;
class RAS_MeshSlot;
class RAS_IMaterial;

/**
 * BL_BlenderShader
 * Blender GPU shader material
 */
class BL_BlenderShader
{
private:
	KX_Scene *m_scene;
	Scene *m_blenderScene;
	Material *m_mat;
	int m_alphaBlend;
	GPUMaterial *m_gpuMat;
	CM_UpdateServer<RAS_IMaterial> *m_materialUpdateServer;
	/// Set once we've warned that this material expects a GPU bone palette that a user never supplies.
	bool m_skinningMismatchWarned;

public:
	BL_BlenderShader(KX_Scene *scene, Material *ma, CM_UpdateServer<RAS_IMaterial> *materialUpdateServer);
	virtual ~BL_BlenderShader();

	bool Ok() const;

	void BindProg(RAS_Rasterizer *rasty);
	void UnbindProg();

	/** Return a map of the corresponding attribut layer for a given attribut index.
	 * \param layers The list of the mesh layers used to link with uv and color material attributes.
	 * \return The map of attributes layers.
	 */
	const RAS_AttributeArray::AttribList GetAttribs(const RAS_Mesh::LayersInfo& layersInfo) const;
	RAS_InstancingBuffer::Attrib GetInstancingAttribs() const;

	void UpdateLights(RAS_Rasterizer *rasty);
	void Update(RAS_MeshUser *meshUser, short matPassIndex, RAS_Rasterizer *rasty);
	/** Re-upload just the object-matrix-dependent uniforms with an explicit matrix, bypassing
	 * meshUser->GetMatrix(). Used to apply RAS_Rasterizer::GetTransform()'s halo/billboard
	 * rotation, which the legacy MultMatrix() fixed-function path no longer delivers under
	 * WITH_GL_PROFILE_CORE. */
	void UpdateObjectMatrix(RAS_MeshUser *meshUser, short matPassIndex, RAS_Rasterizer *rasty, const float mat[16]);

	/// Return true if the shader uses a special vertex shader for geometry instancing.
	bool UseInstancing() const;
	void ActivateInstancing(RAS_InstancingBuffer *buffer);

	/// Return true if the shader uses a special vertex shader for GPU bone skinning.
	bool UseSkinning() const;

	void ReloadMaterial();
	int GetAlphaBlend();
};

#endif // __BL_BLENDERSHADER_H__
