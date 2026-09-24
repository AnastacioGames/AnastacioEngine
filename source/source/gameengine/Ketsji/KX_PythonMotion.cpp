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
 * Contributor(s): none yet.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Ketsji/KX_PythonMotion.cpp
 *  \ingroup gamelogic
 */

#include "KX_PythonMotion.h"
#include "KX_PyMath.h"

#include <algorithm>
#include <cmath>
#include <cstring>

#ifdef __EMSCRIPTEN__
#  include <emscripten.h>

/* Module.rangeMotion is kept up to date by the page (package-web.py) from the browser sensor events.
 * Values are dropped once the last event is older than one second (tab hidden, sensor stopped). */
EM_JS(void, kx_motion_web_read, (float *out, int size), {
	var m = (typeof Module !== 'undefined') ? Module.rangeMotion : null;
	var base = out >> 2;
	for (var i = 0; i < size; i++) HEAPF32[base + i] = 0;
	if (!m || !m.t || performance.now() - m.t > 1000) return;
	HEAPF32[base] = 1;
	var src = [m.gyro, m.accel, m.gravity, m.orient];
	for (var s = 0; s < src.length; s++) {
		for (var k = 0; k < 3; k++) {
			var v = src[s] ? +src[s][k] : 0;
			HEAPF32[base + 1 + s * 3 + k] = isFinite(v) ? v : 0;
		}
	}
});
#endif

/* ------------------------------------------------------------------------- */
/* Native functions                                                          */
/* ------------------------------------------------------------------------- */

KX_PythonMotion::KX_PythonMotion()
	:EXP_PyObjectPlus()
{
	memset(m_data, 0, sizeof(m_data));
	m_neutral[0] = m_neutral[1] = 0.0f;
}

KX_PythonMotion::~KX_PythonMotion()
{
}

void KX_PythonMotion::Refresh()
{
#ifdef __EMSCRIPTEN__
	kx_motion_web_read(m_data, DATA_SIZE);
#else
	memset(m_data, 0, sizeof(m_data));
#endif
}

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python functions                                                          */
/* ------------------------------------------------------------------------- */

/* Integration hooks ------------------------------------------------------- */
PyTypeObject KX_PythonMotion::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_PythonMotion",
	sizeof(EXP_PyObjectPlus_Proxy),
	0,
	py_base_dealloc,
	0,
	0,
	0,
	0,
	py_base_repr,
	0, 0, 0, 0, 0, 0, 0, 0, 0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	0, 0, 0, 0, 0, 0, 0,
	Methods,
	0,
	0,
	&EXP_PyObjectPlus::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_PythonMotion::Methods[] = {
	{"calibrate", (PyCFunction)KX_PythonMotion::sPyCalibrate, METH_NOARGS},
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_PythonMotion::Attributes[] = {
	EXP_PYATTRIBUTE_RO_FUNCTION("available", KX_PythonMotion, pyattr_get_available),
	EXP_PYATTRIBUTE_RO_FUNCTION("gyroscope", KX_PythonMotion, pyattr_get_gyroscope),
	EXP_PYATTRIBUTE_RO_FUNCTION("accelerometer", KX_PythonMotion, pyattr_get_accelerometer),
	EXP_PYATTRIBUTE_RO_FUNCTION("gravity", KX_PythonMotion, pyattr_get_gravity),
	EXP_PYATTRIBUTE_RO_FUNCTION("orientation", KX_PythonMotion, pyattr_get_orientation),
	EXP_PYATTRIBUTE_RO_FUNCTION("tilt", KX_PythonMotion, pyattr_get_tilt),
	EXP_PYATTRIBUTE_NULL    //Sentinel
};

static PyObject *kx_motion_vec3(const float *data, int offset)
{
	return PyObjectFrom(mt::vec3(data[offset], data[offset + 1], data[offset + 2]));
}

PyObject *KX_PythonMotion::pyattr_get_available(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_PythonMotion *self = static_cast<KX_PythonMotion *>(self_v);
	self->Refresh();
	return PyBool_FromLong(self->m_data[AVAILABLE] != 0.0f);
}

PyObject *KX_PythonMotion::pyattr_get_gyroscope(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_PythonMotion *self = static_cast<KX_PythonMotion *>(self_v);
	self->Refresh();
	return kx_motion_vec3(self->m_data, GYRO);
}

PyObject *KX_PythonMotion::pyattr_get_accelerometer(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_PythonMotion *self = static_cast<KX_PythonMotion *>(self_v);
	self->Refresh();
	return kx_motion_vec3(self->m_data, ACCEL);
}

PyObject *KX_PythonMotion::pyattr_get_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_PythonMotion *self = static_cast<KX_PythonMotion *>(self_v);
	self->Refresh();
	return kx_motion_vec3(self->m_data, GRAVITY);
}

PyObject *KX_PythonMotion::pyattr_get_orientation(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_PythonMotion *self = static_cast<KX_PythonMotion *>(self_v);
	self->Refresh();
	return kx_motion_vec3(self->m_data, ORIENTATION);
}

/* Normalized gravity projected on the screen plane; zero when there is no usable reading. */
static bool kx_motion_gravity_dir(const float *data, float out[2])
{
	const float *g = data + KX_PythonMotion::GRAVITY;
	const float len = std::sqrt(g[0] * g[0] + g[1] * g[1] + g[2] * g[2]);
	if (data[KX_PythonMotion::AVAILABLE] == 0.0f || len < 1.0f) {
		out[0] = out[1] = 0.0f;
		return false;
	}
	out[0] = g[0] / len;
	out[1] = g[1] / len;
	return true;
}

PyObject *KX_PythonMotion::pyattr_get_tilt(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_PythonMotion *self = static_cast<KX_PythonMotion *>(self_v);
	self->Refresh();

	/* The reported gravity points up (reaction to it, as in the W3C spec): lowering the right edge of
	 * the screen makes its x negative. Tilt is the screen direction a ball would roll to. */
	float dir[2];
	float tilt[2] = {0.0f, 0.0f};
	if (kx_motion_gravity_dir(self->m_data, dir)) {
		for (int i = 0; i < 2; ++i) {
			tilt[i] = std::min(1.0f, std::max(-1.0f, self->m_neutral[i] - dir[i]));
		}
	}

	PyObject *ret = PyTuple_New(2);
	PyTuple_SET_ITEM(ret, 0, PyFloat_FromDouble(tilt[0]));
	PyTuple_SET_ITEM(ret, 1, PyFloat_FromDouble(tilt[1]));
	return ret;
}

PyObject *KX_PythonMotion::PyCalibrate()
{
	Refresh();
	float dir[2];
	if (kx_motion_gravity_dir(m_data, dir)) {
		m_neutral[0] = dir[0];
		m_neutral[1] = dir[1];
		Py_RETURN_TRUE;
	}
	Py_RETURN_FALSE;
}

#endif  // WITH_PYTHON
