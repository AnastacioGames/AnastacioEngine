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

/** \file KX_LightObject.h
 *  \ingroup ketsji
 */

#ifndef __KX_LIGHT_H__
#define __KX_LIGHT_H__

#include "KX_GameObject.h"

struct GPULamp;
struct Scene;
struct Base;
class KX_Scene;
class KX_Camera;
class RAS_Rasterizer;
class RAS_ILightObject;

class KX_LightObject : public KX_GameObject
{
	Py_Header
protected:
	RAS_ILightObject *m_lightobj;
	/// Needed for registering and replication of lightobj.
	RAS_Rasterizer *m_rasterizer;
	Scene *m_blenderscene;
	Base *m_base;

	bool m_showShadowFrustum;

	/// Result of the last distance-culling test (see UpdateDistanceCulling), with hysteresis applied.
	bool m_distanceCulled;

	/** Distant-light billboard impostor fade, in [0, 1], recomputed each UpdateDistanceCulling()
	 * call. 0 = fully near (no billboard, light renders normally), 1 = fully culled (billboard
	 * at full opacity). See UpdateDistanceCulling() for the fade band. */
	float m_cullFadeAlpha;

public:
	KX_LightObject(void *sgReplicationInfo, SG_Callbacks callbacks, RAS_Rasterizer *rasterizer, RAS_ILightObject *lightobj);
	virtual ~KX_LightObject();

	virtual EXP_Value *GetReplica();
	RAS_ILightObject *GetLightData()
	{
		return m_lightobj;
	}

	bool GetShowShadowFrustum() const;
	void SetShowShadowFrustum(bool show);

	// Update rasterizer light settings.
	void Update();

	/** Distance-based light culling ("light LOD"), analogous in spirit to KX_LodManager's
	 * distance+hysteresis mesh LOD selection, but binary (evaluated / not evaluated) instead
	 * of level-based. Recomputes m_distanceCulled from the distance to \a cam, using a ±10%
	 * hysteresis band around the light's cull distance to avoid popping when the camera
	 * oscillates near the threshold. Sun lamps and lights without cull distance enabled are
	 * never culled. Must be called once per frame (before Update()) for the result to be used.
	 * \param cam The active camera used as the distance reference, may be nullptr.
	 */
	void UpdateDistanceCulling(KX_Camera *cam);

	/// True if the light was culled out by distance on the last UpdateDistanceCulling() call.
	bool GetDistanceCulled() const;

	/** Distant-light billboard impostor fade for the last UpdateDistanceCulling() call, in [0, 1].
	 * 0 means no billboard should be drawn (light is near enough to render normally); a caller
	 * (see KX_ShadowRenderer::Render) uses this to drive RAS_DebugDraw::DrawLightGlow's
	 * alpha so the impostor fades in/out smoothly instead of popping. */
	float GetCullFadeAlpha() const;

	void UpdateScene(KX_Scene *kxscene);
	virtual void SetLayer(int layer);

	virtual int GetGameObjectType() const
	{
		return OBJ_LIGHT;
	}

#ifdef WITH_PYTHON
	// functions
	EXP_PYMETHOD_DOC_NOARGS(KX_LightObject, updateShadow);

	// attributes
	static PyObject *pyattr_get_energy(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_energy(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_shadow_clip_start(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_shadow_clip_end(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_shadow_frustum_size(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_shadow_bind_code(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_shadow_bias(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_shadow_bleed_bias(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_shadow_map_type(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_shadow_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_shadow_active(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_shadow_matrix(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_distance(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_distance(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_lin_attenuation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_lin_attenuation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_quad_attenuation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_quad_attenuation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_spotsize(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_spotsize(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_spotblend(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_spotblend(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_typeconst(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_type(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_type(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_static_shadow(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_static_shadow(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
#endif
};

#endif  // __KX_LIGHT_H__
