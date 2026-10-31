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
 * The Original Code is: all of this file.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_ParticleSystem.cpp
 *  \ingroup ketsji
 */

#include "KX_ParticleSystem.h"

#ifdef WITH_PYTHON

#include "RAS_ParticleBuffer.h"
#include "KX_PyMath.h"

#include <algorithm>
#include <string>

KX_ParticleSystem::KX_ParticleSystem(RAS_ParticleBuffer *buffer)
	:m_buffer(buffer)
{
}

KX_ParticleSystem::~KX_ParticleSystem()
{
}

std::string KX_ParticleSystem::GetName()
{
	return "KX_ParticleSystem";
}

PyTypeObject KX_ParticleSystem::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_ParticleSystem",
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

PyMethodDef KX_ParticleSystem::Methods[] = {
	EXP_PYMETHODTABLE_NOARGS(KX_ParticleSystem, burst),
	{nullptr, nullptr} // Sentinel
};

PyAttributeDef KX_ParticleSystem::Attributes[] = {
	EXP_PYATTRIBUTE_RW_FUNCTION("gravity", KX_ParticleSystem, pyattr_get_gravity, pyattr_set_gravity),
	EXP_PYATTRIBUTE_RW_FUNCTION("lifetime", KX_ParticleSystem, pyattr_get_lifetime, pyattr_set_lifetime),
	EXP_PYATTRIBUTE_RW_FUNCTION("emitterPosition", KX_ParticleSystem, pyattr_get_emitter_position, pyattr_set_emitter_position),
	EXP_PYATTRIBUTE_RW_FUNCTION("emitterRadius", KX_ParticleSystem, pyattr_get_emitter_radius, pyattr_set_emitter_radius),
	EXP_PYATTRIBUTE_RW_FUNCTION("velocity", KX_ParticleSystem, pyattr_get_velocity, pyattr_set_velocity),
	EXP_PYATTRIBUTE_RW_FUNCTION("velocityRandomness", KX_ParticleSystem, pyattr_get_velocity_randomness, pyattr_set_velocity_randomness),
	EXP_PYATTRIBUTE_RW_FUNCTION("size", KX_ParticleSystem, pyattr_get_size, pyattr_set_size),
	EXP_PYATTRIBUTE_RW_FUNCTION("color", KX_ParticleSystem, pyattr_get_color, pyattr_set_color),
	EXP_PYATTRIBUTE_RW_FUNCTION("particleCount", KX_ParticleSystem, pyattr_get_particle_count, pyattr_set_particle_count),
	EXP_PYATTRIBUTE_RW_FUNCTION("texture", KX_ParticleSystem, pyattr_get_texture, pyattr_set_texture),
	EXP_PYATTRIBUTE_RW_FUNCTION("endColor", KX_ParticleSystem, pyattr_get_end_color, pyattr_set_end_color),
	EXP_PYATTRIBUTE_RW_FUNCTION("endSize", KX_ParticleSystem, pyattr_get_end_size, pyattr_set_end_size),
	EXP_PYATTRIBUTE_RW_FUNCTION("emissionDirection", KX_ParticleSystem, pyattr_get_emission_direction, pyattr_set_emission_direction),
	EXP_PYATTRIBUTE_RW_FUNCTION("emissionAngle", KX_ParticleSystem, pyattr_get_emission_angle, pyattr_set_emission_angle),
	EXP_PYATTRIBUTE_RO_FUNCTION("debugUI", KX_ParticleSystem, pyattr_get_debug_ui),
	EXP_PYATTRIBUTE_RW_FUNCTION("enabled", KX_ParticleSystem, pyattr_get_enabled, pyattr_set_enabled),
	EXP_PYATTRIBUTE_RW_FUNCTION("collisionMode", KX_ParticleSystem, pyattr_get_collision_mode, pyattr_set_collision_mode),
	EXP_PYATTRIBUTE_RW_FUNCTION("collisionHeight", KX_ParticleSystem, pyattr_get_collision_height, pyattr_set_collision_height),
	EXP_PYATTRIBUTE_RW_FUNCTION("collisionBounce", KX_ParticleSystem, pyattr_get_collision_bounce, pyattr_set_collision_bounce),
	EXP_PYATTRIBUTE_RW_FUNCTION("collisionFriction", KX_ParticleSystem, pyattr_get_collision_friction, pyattr_set_collision_friction),
	EXP_PYATTRIBUTE_RW_FUNCTION("fragmentShaderPath", KX_ParticleSystem, pyattr_get_fragment_shader, pyattr_set_fragment_shader),
	EXP_PYATTRIBUTE_RW_FUNCTION("burstMode", KX_ParticleSystem, pyattr_get_burst_mode, pyattr_set_burst_mode),
	EXP_PYATTRIBUTE_RW_FUNCTION("burstInterval", KX_ParticleSystem, pyattr_get_burst_interval, pyattr_set_burst_interval),
	EXP_PYATTRIBUTE_RW_FUNCTION("drag", KX_ParticleSystem, pyattr_get_drag, pyattr_set_drag),
	EXP_PYATTRIBUTE_RW_FUNCTION("flipbook", KX_ParticleSystem, pyattr_get_flipbook, pyattr_set_flipbook),
	/* blendMode: str, 'ALPHA' or 'ADDITIVE'. */
	EXP_PYATTRIBUTE_RW_FUNCTION("blendMode", KX_ParticleSystem, pyattr_get_panel, pyattr_set_panel),
	/* billboardMode: str, 'CAMERA_FACING', 'VERTICAL' or 'HORIZONTAL'. */
	EXP_PYATTRIBUTE_RW_FUNCTION("billboardMode", KX_ParticleSystem, pyattr_get_panel, pyattr_set_panel),
	/* emissionMode: str, 'CONTINUOUS' or 'BURST' (same switch as burstMode). */
	EXP_PYATTRIBUTE_RW_FUNCTION("emissionMode", KX_ParticleSystem, pyattr_get_panel, pyattr_set_panel),
	/* useBackfaceCulling: bool, hide the quads seen from behind (VERTICAL/HORIZONTAL billboards). */
	EXP_PYATTRIBUTE_RW_FUNCTION("useBackfaceCulling", KX_ParticleSystem, pyattr_get_panel, pyattr_set_panel),
	/* useDebugUi: bool, show this emitter in the particle debug window (debugUI is the read-only twin). */
	EXP_PYATTRIBUTE_RW_FUNCTION("useDebugUi", KX_ParticleSystem, pyattr_get_panel, pyattr_set_panel),
	/* useVortex: bool, spin the particles around the emitter's Z axis. */
	EXP_PYATTRIBUTE_RW_FUNCTION("useVortex", KX_ParticleSystem, pyattr_get_panel, pyattr_set_panel),
	/* useObjectRotation: bool, gravity/velocity/direction/offset/vortex axis follow the owner rotation. */
	EXP_PYATTRIBUTE_RW_FUNCTION("useObjectRotation", KX_ParticleSystem, pyattr_get_panel, pyattr_set_panel),
	/* vortexHeight: float, height of the vortex funnel. */
	EXP_PYATTRIBUTE_RW_FUNCTION("vortexHeight", KX_ParticleSystem, pyattr_get_panel, pyattr_set_panel),
	/* vortexRadiusTop: float, radius of the funnel at vortexHeight. */
	EXP_PYATTRIBUTE_RW_FUNCTION("vortexRadiusTop", KX_ParticleSystem, pyattr_get_panel, pyattr_set_panel),
	/* vortexRotationSpeed: float, turns per second around the axis. */
	EXP_PYATTRIBUTE_RW_FUNCTION("vortexRotationSpeed", KX_ParticleSystem, pyattr_get_panel, pyattr_set_panel),
	EXP_PYATTRIBUTE_NULL // Sentinel
};

EXP_PYMETHODDEF_DOC_NOARGS(KX_ParticleSystem, burst, "burst(): Births the whole particle pool at once on the next frame (burstMode emitters only).\n")
{
	m_buffer->Burst();
	Py_RETURN_NONE;
}

static const char *blend_mode_names[] = {"ALPHA", "ADDITIVE", nullptr};
static const char *billboard_mode_names[] = {"CAMERA_FACING", "VERTICAL", "HORIZONTAL", nullptr};
static const char *emission_mode_names[] = {"CONTINUOUS", "BURST", nullptr};

/// Index of the str value in names, -1 with a ValueError listing them.
static int enum_from_python(PyObject *value, const char **names, const char *attr)
{
	const char *text = PyUnicode_Check(value) ? PyUnicode_AsUTF8(value) : nullptr;
	std::string expected;
	for (int i = 0; names[i]; ++i) {
		if (text && std::string(text) == names[i]) {
			return i;
		}
		expected += std::string(i ? ", '" : "'") + names[i] + "'";
	}
	PyErr_Format(PyExc_ValueError, "particles.%s = str: KX_ParticleSystem, expected %s", attr, expected.c_str());
	return -1;
}

PyObject *KX_ParticleSystem::pyattr_get_panel(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	RAS_ParticleBuffer *buffer = static_cast<KX_ParticleSystem *>(self_v)->m_buffer;
	const std::string& name = attrdef->m_name;
	if (name == "blendMode") {
		return PyUnicode_FromString(blend_mode_names[std::max(0, std::min<int>(buffer->GetBlendMode(), 1))]);
	}
	if (name == "billboardMode") {
		return PyUnicode_FromString(billboard_mode_names[std::max(0, std::min<int>(buffer->GetBillboardMode(), 2))]);
	}
	if (name == "emissionMode") {
		return PyUnicode_FromString(emission_mode_names[buffer->GetBurstMode() ? 1 : 0]);
	}
	if (name == "useBackfaceCulling") {
		return PyBool_FromLong(buffer->GetBackfaceCulling());
	}
	if (name == "useDebugUi") {
		return PyBool_FromLong(buffer->GetDebugUI());
	}
	if (name == "useVortex") {
		return PyBool_FromLong(buffer->GetUseVortex());
	}
	if (name == "useObjectRotation") {
		return PyBool_FromLong(buffer->GetUseObjectRotation());
	}
	if (name == "vortexHeight") {
		return PyFloat_FromDouble(buffer->GetVortexHeight());
	}
	if (name == "vortexRadiusTop") {
		return PyFloat_FromDouble(buffer->GetVortexRadiusTop());
	}
	return PyFloat_FromDouble(buffer->GetVortexRotationSpeed());
}

int KX_ParticleSystem::pyattr_set_panel(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	RAS_ParticleBuffer *buffer = static_cast<KX_ParticleSystem *>(self_v)->m_buffer;
	const std::string& name = attrdef->m_name;
	if (name == "blendMode" || name == "billboardMode" || name == "emissionMode") {
		const char **names = (name == "blendMode") ? blend_mode_names :
		                     (name == "billboardMode") ? billboard_mode_names : emission_mode_names;
		const int index = enum_from_python(value, names, name.c_str());
		if (index < 0) {
			return PY_SET_ATTR_FAIL;
		}
		if (name == "blendMode") {
			buffer->SetBlendMode(index);
		}
		else if (name == "billboardMode") {
			buffer->SetBillboardMode(index);
		}
		else {
			buffer->SetBurstMode(index == 1);
		}
		return PY_SET_ATTR_SUCCESS;
	}
	if (name == "useBackfaceCulling" || name == "useDebugUi" || name == "useVortex" || name == "useObjectRotation") {
		const int v = PyObject_IsTrue(value);
		if (v == -1) {
			return PY_SET_ATTR_FAIL;
		}
		if (name == "useBackfaceCulling") {
			buffer->SetBackfaceCulling(v != 0);
		}
		else if (name == "useDebugUi") {
			buffer->SetDebugUI(v != 0);
		}
		else if (name == "useObjectRotation") {
			buffer->SetUseObjectRotation(v != 0);
		}
		else {
			buffer->SetUseVortex(v != 0);
		}
		return PY_SET_ATTR_SUCCESS;
	}
	const double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	if (name == "vortexHeight") {
		buffer->SetVortexHeight((float)v);
	}
	else if (name == "vortexRadiusTop") {
		buffer->SetVortexRadiusTop((float)v);
	}
	else {
		buffer->SetVortexRotationSpeed((float)v);
	}
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_burst_mode(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyBool_FromLong(self->m_buffer->GetBurstMode());
}

int KX_ParticleSystem::pyattr_set_burst_mode(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	int v = PyObject_IsTrue(value);
	if (v == -1) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetBurstMode(v != 0);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_burst_interval(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyFloat_FromDouble(self->m_buffer->GetBurstInterval());
}

int KX_ParticleSystem::pyattr_set_burst_interval(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	const double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetBurstInterval((float)v);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_drag(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyFloat_FromDouble(self->m_buffer->GetDrag());
}

int KX_ParticleSystem::pyattr_set_drag(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	const double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetDrag((float)v);
	return PY_SET_ATTR_SUCCESS;
}

/// flipbook = (columns, rows, cycles, random_start); (1, 1, ...) = plain texture.
PyObject *KX_ParticleSystem::pyattr_get_flipbook(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	const float *f = self->m_buffer->GetFlipbook();
	return Py_BuildValue("(iifO)", (int)f[0], (int)f[1], f[2], (f[3] > 0.5f) ? Py_True : Py_False);
}

int KX_ParticleSystem::pyattr_set_flipbook(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	int cols, rows, random = 0;
	float cycles = 1.0f;
	if (!PyArg_ParseTuple(value, "ii|fp:particles.flipbook = (columns, rows, cycles, random_start)",
	                      &cols, &rows, &cycles, &random)) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetFlipbook(cols, rows, cycles, random != 0);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_enabled(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyBool_FromLong(self->m_buffer->GetEnabled());
}

int KX_ParticleSystem::pyattr_set_enabled(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	int v = PyObject_IsTrue(value);
	if (v == -1) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetEnabled(v != 0);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_debug_ui(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyBool_FromLong(self->m_buffer->GetDebugUI());
}

PyObject *KX_ParticleSystem::pyattr_get_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyObjectFrom(mt::vec3(self->m_buffer->GetGravity()));
}

int KX_ParticleSystem::pyattr_set_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	mt::vec3 vec;
	if (!PyVecTo(value, vec)) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetGravity(vec.Data());
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_lifetime(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyFloat_FromDouble(self->m_buffer->GetLifetime());
}

int KX_ParticleSystem::pyattr_set_lifetime(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetLifetime((float)v);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_emitter_position(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyObjectFrom(mt::vec3(self->m_buffer->GetEmitterPos()));
}

int KX_ParticleSystem::pyattr_set_emitter_position(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	mt::vec3 vec;
	if (!PyVecTo(value, vec)) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetEmitterPos(vec.Data());
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_emitter_radius(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyFloat_FromDouble(self->m_buffer->GetEmitterRadius());
}

int KX_ParticleSystem::pyattr_set_emitter_radius(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetEmitterRadius((float)v);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_velocity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyObjectFrom(mt::vec3(self->m_buffer->GetVelocityBase()));
}

int KX_ParticleSystem::pyattr_set_velocity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	mt::vec3 vec;
	if (!PyVecTo(value, vec)) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetVelocityBase(vec.Data());
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_velocity_randomness(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyFloat_FromDouble(self->m_buffer->GetVelocityRandomness());
}

int KX_ParticleSystem::pyattr_set_velocity_randomness(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetVelocityRandomness((float)v);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_size(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyFloat_FromDouble(self->m_buffer->GetBillboardSize());
}

int KX_ParticleSystem::pyattr_set_size(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetBillboardSize((float)v);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyObjectFrom(mt::vec4(self->m_buffer->GetColor()));
}

int KX_ParticleSystem::pyattr_set_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	mt::vec4 vec;
	if (!PyVecTo(value, vec)) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetColor(vec.Data());
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_particle_count(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyLong_FromUnsignedLong(self->m_buffer->GetParticleCount());
}

int KX_ParticleSystem::pyattr_set_particle_count(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	long v = PyLong_AsLong(value);
	if (v == -1 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	if (v <= 0) {
		PyErr_SetString(PyExc_ValueError, "particleCount must be a positive integer");
		return PY_SET_ATTR_FAIL;
	}
	if (!self->m_buffer->Resize((unsigned int)v)) {
		PyErr_SetString(PyExc_RuntimeError, "failed to resize particle pool");
		return PY_SET_ATTR_FAIL;
	}
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_texture(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyUnicode_FromString(self->m_buffer->GetTexturePath().c_str());
}

int KX_ParticleSystem::pyattr_set_texture(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);

	if (!PyUnicode_Check(value)) {
		PyErr_SetString(PyExc_TypeError, "expected a string filepath (empty string clears the texture)");
		return PY_SET_ATTR_FAIL;
	}
	const char *filepath = _PyUnicode_AsString(value);

	if (!self->m_buffer->LoadTextureFromPath(filepath)) {
		PyErr_Format(PyExc_ValueError, "could not load texture '%s'", filepath);
		return PY_SET_ATTR_FAIL;
	}
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_fragment_shader(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyUnicode_FromString(self->m_buffer->GetFragShaderPath().c_str());
}

int KX_ParticleSystem::pyattr_set_fragment_shader(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);

	if (!PyUnicode_Check(value)) {
		PyErr_SetString(PyExc_TypeError, "expected a string filepath to a .glsl file (empty string restores the default look)");
		return PY_SET_ATTR_FAIL;
	}
	const char *filepath = _PyUnicode_AsString(value);

	if (!self->m_buffer->LoadFragShaderFromPath(filepath)) {
		PyErr_Format(PyExc_ValueError, "could not load/compile fragment shader '%s', see console for details", filepath);
		return PY_SET_ATTR_FAIL;
	}
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_end_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyObjectFrom(mt::vec4(self->m_buffer->GetEndColor()));
}

int KX_ParticleSystem::pyattr_set_end_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	mt::vec4 vec;
	if (!PyVecTo(value, vec)) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetEndColor(vec.Data());
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_end_size(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyFloat_FromDouble(self->m_buffer->GetEndSize());
}

int KX_ParticleSystem::pyattr_set_end_size(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetEndSize((float)v);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_emission_direction(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyObjectFrom(mt::vec3(self->m_buffer->GetEmissionDirection()));
}

int KX_ParticleSystem::pyattr_set_emission_direction(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	mt::vec3 vec;
	if (!PyVecTo(value, vec)) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetEmissionDirection(vec.Data());
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_emission_angle(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyFloat_FromDouble(self->m_buffer->GetEmissionAngle());
}

int KX_ParticleSystem::pyattr_set_emission_angle(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetEmissionAngle((float)v);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_collision_mode(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyLong_FromLong(self->m_buffer->GetCollisionMode());
}

int KX_ParticleSystem::pyattr_set_collision_mode(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	long v = PyLong_AsLong(value);
	if (v == -1 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	if (v < 0 || v > 2) {
		PyErr_SetString(PyExc_ValueError, "collisionMode must be 0 (None), 1 (Ground Plane) or 2 (Screen-Space)");
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetCollisionMode((short)v);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_collision_height(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyFloat_FromDouble(self->m_buffer->GetCollisionHeight());
}

int KX_ParticleSystem::pyattr_set_collision_height(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetCollisionHeight((float)v);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_collision_bounce(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyFloat_FromDouble(self->m_buffer->GetCollisionBounce());
}

int KX_ParticleSystem::pyattr_set_collision_bounce(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetCollisionBounce((float)v);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_ParticleSystem::pyattr_get_collision_friction(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	return PyFloat_FromDouble(self->m_buffer->GetCollisionFriction());
}

int KX_ParticleSystem::pyattr_set_collision_friction(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ParticleSystem *self = static_cast<KX_ParticleSystem *>(self_v);
	double v = PyFloat_AsDouble(value);
	if (v == -1.0 && PyErr_Occurred()) {
		return PY_SET_ATTR_FAIL;
	}
	self->m_buffer->SetCollisionFriction((float)v);
	return PY_SET_ATTR_SUCCESS;
}

#endif  // WITH_PYTHON
