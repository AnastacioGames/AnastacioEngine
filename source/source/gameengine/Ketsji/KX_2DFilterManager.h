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
 * Contributor(s): Ulysse Martin, Tristan Porteries.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_2DFilterManager.h
*  \ingroup ketsji
*/

#ifndef __KX_2DFILTER_MANAGER_H__
#define __KX_2DFILTER_MANAGER_H__

#include "RAS_2DFilterManager.h"
#include "KX_2DFilter.h"
#include "KX_2DFilterOffScreen.h"
#include "EXP_PyObjectPlus.h"
#include "mathfu.h"

class KX_Camera;
class KX_Scene;

class KX_2DFilterManager : public RAS_2DFilterManager, public EXP_PyObjectPlus
{
	Py_Header
public:
	KX_2DFilterManager(RAS_ICanvas *canvas, BuildInFilters filters);
	virtual ~KX_2DFilterManager();

	virtual KX_2DFilter *BloomPass(BuildInFilters filters, int time, int index, float lod, int w, int h);
	virtual RAS_2DFilter *NewFilter(RAS_2DFilterData& filterData);

	/** Builds the (multi-pass) Bloom/SSR/Light Scattering filter chains on the
	 * fly if the scene didn't have them enabled at load time, so the Python
	 * change*Values() methods can turn them on even when their "Post
	 * Processing Shaders" checkbox started off. No-op if already built.
	 */
	void EnsureBloomFilters(BuildInFilters filters);
	/** The bloom buffers follow the canvas, so their textures can be recreated. Point the bloom filters
	 * at the current textures again. */
	void RefreshBloomTextures();
	void EnsureSSRFilters(BuildInFilters filters);
    void EnsureSSGIFilters(BuildInFilters filters);
    void RefreshSSGITexture();
	void EnsureLightScatterFilters(BuildInFilters filters);

	/** Native World weather filters (Rain/Clouds/Lens Flare), driven entirely by
	 * KX_WorldInfo from World DNA/RNA settings -- no Python component/actuator needed. */
	void EnsureRainFilters(BuildInFilters filters);
	void EnsureCloudsFilters(BuildInFilters filters);
	void EnsureVFogFilters(BuildInFilters filters);
	void EnsureLensFlareFilters(BuildInFilters filters);
	bool SetBuiltinFilterEnabled(FILTER_MODE mode, bool enabled) override;

	/** Camera FX of the active camera: adds/removes the DOF and Lens passes when the set of enabled
	 * effects changes (so everything off costs no pass) and uploads this frame's values. */
	void UpdateCameraFX(KX_Camera *camera, double time);
	/** Scene load, inside a shader prefetch pass: sends the programs of the Camera FX passes the scene's cameras
	 * use to the driver, compiled together with the materials. */
	void PrefetchCameraFX(KX_Scene *scene);
	/** Scene load: builds those passes (disabled), instead of at the first frame that uses them. */
	void PrepareCameraFX(KX_Scene *scene);

	/** Custom filters made from an external text file: twice a second, recompile the ones whose
	 * file changed on disk (edit the .glsl in another editor while the game runs). */
	void ReloadChangedSources();
	/// Read the source of a filter again (external file) and recompile it.
	static bool ReloadSource(RAS_2DFilter *filter);

private:
	/// Last modification time seen for each filter with an external source.
	std::map<RAS_2DFilter *, int64_t> m_sourceTimes;
	double m_lastSourceCheck = 0.0;

	RAS_2DFilterData CameraFXData(int pass);
	void CameraFXUsed(KX_Scene *scene, bool& dof, bool& lens) const;

	RAS_ICanvas *m_canvas;
	/** Film Grain, a scene post-process drawn in the camera lens pass. */
	bool m_useGrain;
	float m_grainStrength;
	/// View-projection of the last Camera FX frame, for the camera motion blur reprojection.
	mt::mat4 m_prevViewProj;
	KX_Camera *m_prevFXCamera = nullptr;
	double m_prevFXTime = 0.0;
	/** Scene FXAA settings, for an FXAA pass built later from Python. */
	BuildInFilters m_sceneFilters;
	/** The FXAA pass, built (disabled) when missing. Its parameters hold the scene values. */
	RAS_2DFilter *EnsureFxaaPass();
public:

#ifdef WITH_PYTHON

	EXP_PYMETHOD_DOC(KX_2DFilterManager, getFilter);
	EXP_PYMETHOD_DOC(KX_2DFilterManager, addFilter);
	EXP_PYMETHOD_DOC(KX_2DFilterManager, removeFilter);
	EXP_PYMETHOD_DOC(KX_2DFilterManager, setBuiltinFilterEnabled);
	EXP_PYMETHOD_DOC(KX_2DFilterManager, createOffScreen);

	EXP_PYMETHOD_DOC(KX_2DFilterManager, changeFxaaValues);
	EXP_PYMETHOD_DOC(KX_2DFilterManager, changeTonemapValues);
	EXP_PYMETHOD_DOC(KX_2DFilterManager, changeBloomValues);
	EXP_PYMETHOD_DOC(KX_2DFilterManager, changeLightScatterValues);
	EXP_PYMETHOD_DOC(KX_2DFilterManager, changeSSRValues);
	EXP_PYMETHOD_DOC(KX_2DFilterManager, changeSSAOValues);
    EXP_PYMETHOD_DOC(KX_2DFilterManager, changeSSGIValues);
	EXP_PYMETHOD_DOC(KX_2DFilterManager, changeGrainValues);

	/* fxaa* and grain* attributes, one pair dispatched on the attribute name */
	static PyObject *pyattr_get_post(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_post(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);

#endif  // WITH_PYTHON
};

#endif // __KX_2DFILTER_MANAGER_H__
