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
 * Contributor(s): Mitchell Stokes
 *
 * ***** END GPL LICENSE BLOCK *****
 */

#include "RAS_ILightObject.h"

class RAS_Rasterizer;
class KX_Scene;
struct GPULamp;
struct GPUSceneLight;
struct Image;

class RAS_OpenGLLight : public RAS_ILightObject
{

	RAS_Rasterizer *m_rasterizer;

public:
	RAS_OpenGLLight(RAS_Rasterizer *ras);
	~RAS_OpenGLLight();

	/* Public so RAS_Rasterizer::ProcessLighting() can record it alongside the same slot it
	 * feeds into gl_LightSource[slot] via ApplyFixedFunctionLighting() below, for
	 * GPU_material_bind_shadow_lamps() (see RAS_Rasterizer::GetShadowLamps()). */
	GPULamp *GetGPULamp();

	/* Sets GL_LIGHT<slot> (COMPAT) and always fills `r_light` with the same values in eye space
	 * (`viewmat` is the column-major view matrix), for the CORE-profile unflightsource[] uniforms. */
	bool ApplyFixedFunctionLighting(KX_Scene *kxscene, int oblayer, int slot, const float viewmat[16],
	                                GPUSceneLight *r_light);

	RAS_OpenGLLight *Clone()
	{
		return new RAS_OpenGLLight(*this);
	}

	bool HasShadowBuffer();
	bool NeedShadowUpdate();
	int GetShadowBindCode();
	mt::mat4 GetViewMat();
	mt::mat4 GetWinMat();
	mt::mat4 GetShadowMatrix();
	int GetShadowLayer();
	void BindShadowBuffer(RAS_ICanvas *canvas, KX_Camera *cam, mt::mat3x4& camtrans);
	void UnbindShadowBuffer();
	bool HasCascadedShadow();
	void BindCascadeShadowBuffer(RAS_ICanvas *canvas, short cascadeIndex, KX_Camera *cam, mt::mat3x4& camtrans,
	                             const mt::mat4& lightViewMat, const mt::mat4& lightWinMat);
	void UnbindCascadeShadowBuffer(short cascadeIndex);
	void SetCascadeSplits(float split0, float split1);
	bool NeedStaticShadowUpdate(short cascadeIndex, const mt::mat4& lightViewMat, const mt::mat4& lightWinMat);
	void BindStaticShadowBuffer(RAS_ICanvas *canvas, short cascadeIndex, KX_Camera *cam, mt::mat3x4& camtrans,
	                            const mt::mat4& lightViewMat, const mt::mat4& lightWinMat);
	void UnbindStaticShadowBuffer(short cascadeIndex, const mt::mat4& lightViewMat, const mt::mat4& lightWinMat);
	void CompositeStaticShadow(short cascadeIndex);
	void InvalidateStaticShadow();
	Image *GetTextureImage(short texslot);
	void Update(const mt::mat3x4& trans, bool hide);
	void SetShadowUpdateState(short state);
};
