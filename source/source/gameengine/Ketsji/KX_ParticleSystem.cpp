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
	EXP_PYATTRIBUTE_NULL // Sentinel
};

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
