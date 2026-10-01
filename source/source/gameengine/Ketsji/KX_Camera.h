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

/** \file KX_Camera.h
 *  \ingroup ketsji
 *  \brief Camera in the gameengine. Cameras are also used for views.
 */

#ifndef __KX_CAMERA_H__
#define __KX_CAMERA_H__

#include "KX_GameObject.h"

#include "SG_Frustum.h"

#include "RAS_CameraData.h"
#include "RAS_Rasterizer.h"

#ifdef WITH_PYTHON
/* utility conversion function */
bool ConvertPythonToCamera(KX_Scene *scene, PyObject *value, KX_Camera **object, bool py_none_ok, const char *error_prefix);
#endif

class KX_Camera : public KX_GameObject
{
	Py_Header
protected:
	friend class KX_Scene;
	/** Camera parameters (clips distances, focal length). These
	 * params are closely tied to Blender. In the gameengine, only the
	 * projection and modelview matrices are relevant. There's a
	 * conversion being done in the engine class. Why is it stored
	 * here? It doesn't really have a function here. */
	RAS_CameraData	m_camdata;

	float m_shakeShiftX = 0.0f;
	float m_shakeShiftY = 0.0f;

public:
	/// Game focus, tracking, Camera FX and shake settings (Camera.gamefx + gpu_dof in DNA).
	struct GameFX
	{
		short focusMode = 0;
		short trackMode = 0;
		short flag = 0;
		short dofQuality = 1;
		std::string focusProp;
		float focusDistance = 10.0f;
		float fstop = 128.0f;
		int numBlades = 0;
		float focusSmooth = 0.2f;
		float focusRange = 2.0f;
		float focusScreen[2] = {0.5f, 0.5f};
		float trackSpeed = 0.25f;
		float trackLimit = 0.0f;
		float trackDeadzone = 0.0f;
		float trackScreenOffset[2] = {0.0f, 0.0f};
		float droneAmplitude = 1.0f;
		float droneFrequency = 1.0f;
		float trackBank = 0.3f;
		float dofBlur = 6.0f;
		float speedBlurStrength = 0.5f;
		float speedBlurMaxSpeed = 40.0f;
		float dirBlurStrength = 0.5f;
		float dirBlurMax = 0.05f;
		float catEyeStrength = 0.5f;
		float chromaStrength = 0.5f;
		float vignetteStrength = 0.4f;
		float vignetteRadius = 0.75f;
		float fisheyeStrength = 0.0f;
		float shakeAmplitude = 0.02f;
		float shakeFrequency = 15.0f;
		float shakeDecay = 1.5f;
	};

protected:
	GameFX m_gameFX;

	/// Focus object of CAM_FOCUS_OBJECT (DOF Object or cam.focusObject).
	KX_GameObject *m_focusObject = nullptr;
	/// Object the focus resolved to this frame (OBJECT/PROPERTY/AUTO), may be null.
	KX_GameObject *m_focusTarget = nullptr;
	/// Cached CAM_FOCUS_PROPERTY target and the time of the last scene scan.
	KX_GameObject *m_focusPropTarget = nullptr;
	std::string m_focusPropScanned;
	double m_focusScanTime = -1.0;
	bool m_focusValid = false;
	bool m_focusInitialized = false;
	mt::vec3 m_focusPosition = mt::zero3;
	float m_focusDistance = 10.0f;
	mt::vec2 m_focusScreen = mt::vec2(0.5f, 0.5f);
	double m_fxLastTime = -1.0;

	/// Tracking offset over the base (object) orientation, local yaw/pitch/roll.
	float m_trackYaw = 0.0f;
	float m_trackPitch = 0.0f;
	float m_trackRoll = 0.0f;
	float m_trackYawRate = 0.0f;
	bool m_trackActive = false;
	mt::mat3 m_trackRotation = mt::mat3::Identity();
	mt::vec3 m_trackOffset = mt::zero3;
	float m_droneTime = 0.0f;
	/// VR Head Tracking: sensor orientation (z up, facing +y) turned into a rotation local to the object.
	bool m_headActive = false;
	mt::mat3 m_headRotation = mt::mat3::Identity();

	/// Motion of the rendered camera, used by Speed/Directional Blur.
	bool m_motionInitialized = false;
	mt::vec3 m_prevRenderPos = mt::zero3;
	mt::vec3 m_prevRenderForward = mt::zero3;
	float m_speed = 0.0f;
	float m_speedOverride = -1.0f;
	mt::vec2 m_turn = mt::zero2;

	/// Shake sources summed into the lens shift: World earthquake + cam.shake() trauma.
	float m_quakeShiftX = 0.0f;
	float m_quakeShiftY = 0.0f;
	float m_trauma = 0.0f;
	float m_traumaRate = 0.0f; // 0 = use shakeDecay
	float m_traumaTime = 0.0f;
	float m_shakeRoll = 0.0f;

	/// Setting for a view: left or right eye or default (left eye).
	struct View
	{
		View();

		/// The projection matrix.
		mt::mat4 projection;
		/// The modelview matrix.
		mt::mat4 modelview;
		/// The frustum planes and matrix.
		SG_Frustum frustum;
		/// True if the projection must be updated.
		bool projectionDirty;
		/// True if the frustum must be updated.
		bool frustumDirty;
	};

	/// All views available.
	View m_views[RAS_Rasterizer::RAS_STEREO_MAXEYE];

	/**
	 * This camera is frustum culling.
	 * Some cameras (ie if the game was started from a non camera view should not cull.)
	 */
	bool         m_frustum_culling;

	/** Distance factor for level of detail*/
	float m_lodDistanceFactor;

	/// Enable object activity culling for this camera.
	bool m_activityCulling;

	/**
	 * Show Debug Camera Frustum?
	 */
	bool m_showDebugCameraFrustum;

	/** CSM cascade-matrix cache tolerance: 0 disables the cache (always recompute), 1 only
	 * reuses last frame's cascade matrices when this camera's transform is unchanged, 2 also
	 * tolerates one frame of small movement before forcing a recompute. See KX_ShadowRenderer. */
	short m_csmCacheMaxStaleFrames;

	void ExtractFrustum(RAS_Rasterizer::StereoEye eye);

	KX_GameObject *FindPropertyFocus(bool rescan, double curtime);
	void UpdateFocus(float dt, double curtime);
	void UpdateTracking(float dt);
	void UpdateShake(float dt);
	void UpdateMotion(float dt);

public:

	enum { INSIDE, INTERSECT, OUTSIDE };

	KX_Camera(void* sgReplicationInfo,SG_Callbacks callbacks,const RAS_CameraData& camdata, bool frustum_culling = true);
	virtual ~KX_Camera();

	/** 
	 * Inherited from EXP_Value -- return a new copy of this
	 * instance allocated on the heap. Ownership of the new 
	 * object belongs with the caller.
	 */
	virtual	EXP_Value*
	GetReplica(
	);
	virtual void ProcessReplica();

	mt::mat3x4		GetWorldToCamera() const;
	mt::mat3x4		GetCameraToWorld() const;

	/** Sets the projection matrix that is used by the rasterizer. */
	void				SetProjectionMatrix(const mt::mat4 & mat, RAS_Rasterizer::StereoEye eye);

	/** Sets the modelview matrix that is used by the rasterizer. */
	void				SetModelviewMatrix(const mt::mat4 & mat, RAS_Rasterizer::StereoEye eye);
		
	/** Gets the projection matrix that is used by the rasterizer. */
	const mt::mat4&		GetProjectionMatrix(RAS_Rasterizer::StereoEye eye) const;
	
	/** returns true if this camera has been set a projection matrix. */
	bool				HasValidProjectionMatrix(RAS_Rasterizer::StereoEye eye) const;
	
	/** Sets the validity of the projection matrix.  Call this if you change camera
	 *  data (eg lens, near plane, far plane) and require the projection matrix to be
	 *  recalculated.
	 */
	void				InvalidateProjectionMatrix();

	/** Transient lens-shift offset (earthquake camera shake). Added to shift_x/shift_y
	 *  when the projection is built, so the authored shift stays untouched. */
	void				SetShakeShift(float x, float y);
	/// Earthquake part of the shake; summed with the cam.shake() part.
	void				SetEarthquakeShift(float x, float y);

	GameFX& GetGameFX();
	void SetFocusObject(KX_GameObject *object);
	KX_GameObject *GetFocusObject() const;
	/// Clears any reference to a removed object.
	void UnlinkObject(KX_GameObject *object);
	/// Focus sensor, tracking and shake, once per frame for the active camera.
	void UpdateGameFX(double curtime);
	void UpdateHeadTracking();
	/// Adds shake trauma (0..1), decays at shake_decay per second.
	void AddShake(float trauma, float duration);

	const mt::vec3& GetFocusPosition() const;
	float GetFocusDistance() const;
	const mt::vec2& GetFocusScreenPosition() const;
	bool IsFocusValid() const;
	float GetCameraSpeed() const;
	const mt::vec2& GetCameraTurn() const;
	/// Orientation that is rendered (base orientation plus tracking and shake roll).
	mt::mat3 GetRenderOrientation() const;
	mt::vec3 GetRenderPosition() const;
	
	/** Gets the modelview matrix that is used by the rasterizer. 
	 *  \warning If the Camera is a dynamic object then this method may return garbage.  Use GetWorldToCamera() instead.
	 */
	const mt::mat4&		GetModelviewMatrix(RAS_Rasterizer::StereoEye eye) const;

	/// Update projection and modelview depending on stereo mode, eye and rendering areas.
	void UpdateView(RAS_Rasterizer *rasty, KX_Scene *scene, RAS_Rasterizer::StereoMode stereoMode,
			RAS_Rasterizer::StereoEye eye, const RAS_Rect& viewport, const RAS_Rect& area);

	/** Gets the aperture. */
	float				GetLens() const;
	/** Sets the aperture. */
	void				SetLens(float lens);
	/** Gets the ortho scale. */
	float				GetScale() const;
	/** Gets the horizontal size of the sensor - for camera matching */
	float				GetSensorWidth() const;
	/** Gets the vertical size of the sensor - for camera matching */
	float				GetSensorHeight() const;
	/** Gets the mode FOV is calculating from sensor dimensions */
	short				GetSensorFit() const;
	/** Gets the horizontal shift of the sensor - for camera matching */
	float				GetShiftHorizontal() const;
	/** Gets the vertical shift of the sensor - for camera matching */
	float				GetShiftVertical() const;
	/** Gets the near clip distance. */
	float				GetCameraNear() const;
	/** Gets the far clip distance. */
	float				GetCameraFar() const;
	/** Gets the focal length (only used for stereo rendering) */
	float				GetFocalLength() const;
	float GetZoom() const;
	/** Gets all camera data. */
	RAS_CameraData*		GetCameraData();

	/** Get/Set show camera frustum */
	void SetShowCameraFrustum(bool show);
	bool GetShowCameraFrustum() const;

	/** Get level of detail distance factor */
	float GetLodDistanceFactor() const;
	/** Set level of detail distance factor */
	void SetLodDistanceFactor(float lodfactor);

	/** Get CSM cascade-matrix cache tolerance (0/1/2, see m_csmCacheMaxStaleFrames) */
	short GetCSMCacheMaxStaleFrames() const;
	/** Set CSM cascade-matrix cache tolerance (0/1/2, see m_csmCacheMaxStaleFrames) */
	void SetCSMCacheMaxStaleFrames(short maxStaleFrames);

	bool GetActivityCulling() const;
	void SetActivityCulling(bool enable);

	const SG_Frustum& GetFrustum(RAS_Rasterizer::StereoEye eye);

	/**
	 * Gets this camera's culling status.bool
	 */
	bool GetFrustumCulling() const;
	
	/**
	 * Sets this camera's viewport status.
	 */
	void EnableViewport(bool viewport);
	
	/**
	 * Sets this camera's viewport.
	 */
	void SetViewport(int left, int bottom, int right, int top);

	/**
	 * Sets this camera's viewport as ratios of the render area, resolved every frame by UpdateViewport().
	 */
	void SetViewportRatios(float left, float bottom, float right, float top);

	/**
	 * Resolves the viewport ratios against the current render area and returns the viewport.
	 */
	const RAS_Rect& UpdateViewport(const RAS_Rect& displayArea);
	
	/**
	 * Gets this camera's viewport status.bool
	 */
	bool UseViewport() const;
	
	/**
	 * Gets this camera's viewport.
	 */
	const RAS_Rect& GetViewport() const;
	
	virtual int GetGameObjectType() const { return OBJ_CAMERA; }

	mathfu::vec3 GetObjectProjectedOnScreenSpace(mathfu::vec3 gameObjWorldSpace);
	RayCastData GetScreenRayCast(float x, float y, float dist, char *propName);

#ifdef WITH_PYTHON
	EXP_PYMETHOD_DOC_VARARGS(KX_Camera, sphereInsideFrustum);
	EXP_PYMETHOD_DOC_O(KX_Camera, boxInsideFrustum);
	EXP_PYMETHOD_DOC_O(KX_Camera, pointInsideFrustum);
	
	EXP_PYMETHOD_DOC_NOARGS(KX_Camera, getCameraToWorld);
	EXP_PYMETHOD_DOC_NOARGS(KX_Camera, getWorldToCamera);
	
	EXP_PYMETHOD_DOC_VARARGS(KX_Camera, setViewport);
	EXP_PYMETHOD_DOC_NOARGS(KX_Camera, setOnTop);

	EXP_PYMETHOD_DOC_O(KX_Camera, getScreenPosition);
	EXP_PYMETHOD_DOC_VARARGS(KX_Camera, getScreenVect);
	EXP_PYMETHOD_DOC_VARARGS(KX_Camera, getScreenRay);
	
	static PyObject*	pyattr_get_perspective(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_perspective(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);

	static PyObject*	pyattr_get_lens(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_lens(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject*	pyattr_get_fov(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_fov(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject*	pyattr_get_ortho_scale(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_ortho_scale(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject*	pyattr_get_near(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_near(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject*	pyattr_get_far(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_far(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject*	pyattr_get_shift_x(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_shift_x(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject*	pyattr_get_shift_y(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_shift_y(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);

	static PyObject*	pyattr_get_use_viewport(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_use_viewport(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	
	static PyObject*	pyattr_get_projectionMatrixLeft(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_projectionMatrixLeft(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject*	pyattr_get_projectionMatrixRight(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_projectionMatrixRight(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);

	static PyObject*	pyattr_get_modelview_matrix(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject*	pyattr_get_camera_to_world(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject*	pyattr_get_world_to_camera(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	
	EXP_PYMETHOD_DOC_VARARGS(KX_Camera, shake);

	static PyObject*	pyattr_get_focus_object(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int			pyattr_set_focus_object(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject*	pyattr_get_focus_target(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject*	pyattr_get_focus_position(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject*	pyattr_get_focus_screen_position(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject*	pyattr_get_track_orientation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);

	static PyObject*	pyattr_get_INSIDE(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject*	pyattr_get_OUTSIDE(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject*	pyattr_get_INTERSECT(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
#endif
};

#endif  /* __KX_CAMERA_H__ */
