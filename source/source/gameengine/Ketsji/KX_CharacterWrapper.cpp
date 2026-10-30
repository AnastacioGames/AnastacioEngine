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

/** \file gameengine/Ketsji/KX_CharacterWrapper.cpp
 *  \ingroup ketsji
 */

#include "KX_CharacterWrapper.h"

#include <cstring>
#include "KX_PyMath.h"

#include "PHY_ICharacter.h"

#include "BLI_utildefines.h"
#include "BLI_math_base.h"

KX_CharacterWrapper::KX_CharacterWrapper(PHY_ICharacter *character) :
	m_character(character)
{
	m_character->SetInvalidationCallback(&KX_CharacterWrapper::OnCharacterInvalidated, this);
}

KX_CharacterWrapper::~KX_CharacterWrapper()
{
	if (m_character) {
		m_character->SetInvalidationCallback(nullptr, this);
	}
}

void KX_CharacterWrapper::OnCharacterInvalidated(void *client)
{
	static_cast<KX_CharacterWrapper *>(client)->m_character = nullptr;
}

std::string KX_CharacterWrapper::GetName()
{
	return "KX_CharacterWrapper";
}

#ifdef WITH_PYTHON

static bool raise_exc_invalid(PHY_ICharacter *character, const char *name)
{
	if (!character) {
		PyErr_Format(PyExc_ReferenceError,
		             "character.%s: character no longer exists (its object was removed).", name);
		return true;
	}
	return false;
}

#define CHARACTER_VALID_CHECK_OR_RETURN(character, name, ret) 	if (raise_exc_invalid(character, name)) { 		return ret; 	} (void)0

PyTypeObject KX_CharacterWrapper::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_CharacterWrapper",
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

PyAttributeDef KX_CharacterWrapper::Attributes[] = {
	EXP_PYATTRIBUTE_RO_FUNCTION("onGround", KX_CharacterWrapper, pyattr_get_onground),
	EXP_PYATTRIBUTE_RW_FUNCTION("gravity", KX_CharacterWrapper, pyattr_get_gravity, pyattr_set_gravity),
	EXP_PYATTRIBUTE_RW_FUNCTION("fallSpeed", KX_CharacterWrapper, pyattr_get_fallSpeed, pyattr_set_fallSpeed),
	EXP_PYATTRIBUTE_RW_FUNCTION("maxJumps", KX_CharacterWrapper, pyattr_get_max_jumps, pyattr_set_max_jumps),
	EXP_PYATTRIBUTE_RW_FUNCTION("maxSlope", KX_CharacterWrapper, pyattr_get_maxSlope, pyattr_set_maxSlope),
	EXP_PYATTRIBUTE_RO_FUNCTION("jumpCount", KX_CharacterWrapper, pyattr_get_jump_count),
	EXP_PYATTRIBUTE_RW_FUNCTION("jumpSpeed", KX_CharacterWrapper, pyattr_get_jumpSpeed, pyattr_set_jumpSpeed),
	EXP_PYATTRIBUTE_RW_FUNCTION("walkDirection", KX_CharacterWrapper, pyattr_get_walk_dir, pyattr_set_walk_dir),
	EXP_PYATTRIBUTE_RW_FUNCTION("jumpDirection", KX_CharacterWrapper, pyattr_get_jump_dir, pyattr_set_jump_dir),
	EXP_PYATTRIBUTE_RW_FUNCTION("smoothMovement", KX_CharacterWrapper, pyattr_get_smoothMovement, pyattr_set_smoothMovement),
	EXP_PYATTRIBUTE_RW_FUNCTION("posture", KX_CharacterWrapper, pyattr_get_posture, pyattr_set_posture),
	EXP_PYATTRIBUTE_RO_FUNCTION("canStand", KX_CharacterWrapper, pyattr_get_canStand),
	EXP_PYATTRIBUTE_RW_FUNCTION("running", KX_CharacterWrapper, pyattr_get_running, pyattr_set_running),
	EXP_PYATTRIBUTE_NULL    //Sentinel
};

static const char *posture_names[POSTURE_COUNT] = {"STAND", "CROUCH", "CRAWL", "JUMP_TUCK"};

// Current posture (the shape in use). Setting asks for one; standing up waits for room.
PyObject *KX_CharacterWrapper::pyattr_get_posture(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);

	return PyUnicode_FromString(posture_names[self->m_character->GetPosture()]);
}

int KX_CharacterWrapper::pyattr_set_posture(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), PY_SET_ATTR_FAIL);

	const char *name = PyUnicode_Check(value) ? PyUnicode_AsUTF8(value) : nullptr;
	for (int i = POSTURE_STAND; name && i <= POSTURE_CRAWL; ++i) {
		if (strcmp(name, posture_names[i]) == 0) {
			self->m_character->SetPosture(i);
			return PY_SET_ATTR_SUCCESS;
		}
	}
	PyErr_SetString(PyExc_ValueError, "KX_CharacterWrapper.posture: expected 'STAND', 'CROUCH' or 'CRAWL'");
	return PY_SET_ATTR_FAIL;
}

PyObject *KX_CharacterWrapper::pyattr_get_running(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);

	return PyBool_FromLong(self->m_character->IsRunning());
}

int KX_CharacterWrapper::pyattr_set_running(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), PY_SET_ATTR_FAIL);

	const int param = PyObject_IsTrue(value);
	if (param == -1) {
		PyErr_SetString(PyExc_TypeError, "KX_CharacterWrapper.running: expected True or False");
		return PY_SET_ATTR_FAIL;
	}
	self->m_character->SetRunning(param != 0);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_CharacterWrapper::pyattr_get_canStand(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);

	return PyBool_FromLong(self->m_character->CanStand());
}

PyObject *KX_CharacterWrapper::pyattr_get_onground(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);

	return PyBool_FromLong(self->m_character->OnGround());
}

PyObject *KX_CharacterWrapper::pyattr_get_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);

	return PyFloat_FromDouble(self->m_character->GetGravity());
}

int KX_CharacterWrapper::pyattr_set_gravity(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), PY_SET_ATTR_FAIL);
	double param = PyFloat_AsDouble(value);

	if (param == -1) {
		PyErr_SetString(PyExc_ValueError, "KX_CharacterWrapper.gravity: expected a float");
		return PY_SET_ATTR_FAIL;
	}

	self->m_character->SetGravity((float)param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject* KX_CharacterWrapper::pyattr_get_smoothMovement(EXP_PyObjectPlus* self_v, const EXP_PYATTRIBUTE_DEF* attrdef)
{
	KX_CharacterWrapper* self = static_cast<KX_CharacterWrapper*>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);

	return PyFloat_FromDouble(self->m_character->GetSmoothMovement());
}

int KX_CharacterWrapper::pyattr_set_smoothMovement(EXP_PyObjectPlus* self_v, const EXP_PYATTRIBUTE_DEF* attrdef, PyObject* value)
{
	KX_CharacterWrapper* self = static_cast<KX_CharacterWrapper*>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), PY_SET_ATTR_FAIL);
	double param = PyFloat_AsDouble(value);

	if (param == -1) {
		PyErr_SetString(PyExc_ValueError, "KX_CharacterWrapper.smoothMovement: expected a float");
		return PY_SET_ATTR_FAIL;
	}
	else if ((float)param > 1) {
		PyErr_SetString(PyExc_ValueError, "KX_CharacterWrapper.smoothMovement: only float 0.0 - 1.0");
		return PY_SET_ATTR_FAIL;
	}

	self->m_character->SetSmoothMovement((float)param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_CharacterWrapper::pyattr_get_fallSpeed(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);
	return PyFloat_FromDouble(self->m_character->GetFallSpeed());
}

int KX_CharacterWrapper::pyattr_set_fallSpeed(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), PY_SET_ATTR_FAIL);
	const float param = PyFloat_AsDouble(value);

	if (param == -1 || param < 0.0f) {
		PyErr_SetString(PyExc_ValueError, "KX_CharacterWrapper.fallSpeed: expected a positive float");
		return PY_SET_ATTR_FAIL;
	}

	self->m_character->SetFallSpeed(param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_CharacterWrapper::pyattr_get_maxSlope(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);
	return PyFloat_FromDouble(self->m_character->GetMaxSlope());
}

int KX_CharacterWrapper::pyattr_set_maxSlope(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), PY_SET_ATTR_FAIL);
	const float param = PyFloat_AsDouble(value);

	if (param == -1 || param < 0.0f || param > M_PI_2) {
		PyErr_SetString(PyExc_ValueError, "KX_CharacterWrapper.maxSlope: expected a float between 0 and half pi");
		return PY_SET_ATTR_FAIL;
	}

	self->m_character->SetMaxSlope(param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_CharacterWrapper::pyattr_get_max_jumps(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);

	return PyLong_FromLong(self->m_character->GetMaxJumps());
}

int KX_CharacterWrapper::pyattr_set_max_jumps(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), PY_SET_ATTR_FAIL);
	long param = PyLong_AsLong(value);

	if (param == -1) {
		PyErr_SetString(PyExc_ValueError, "KX_CharacterWrapper.maxJumps: expected an integer");
		return PY_SET_ATTR_FAIL;
	}

	CLAMP(param, 0, 255);

	self->m_character->SetMaxJumps(param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_CharacterWrapper::pyattr_get_jump_count(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);

	return PyLong_FromLong(self->m_character->GetJumpCount());
}

PyObject *KX_CharacterWrapper::pyattr_get_jumpSpeed(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);
	return PyFloat_FromDouble(self->m_character->GetJumpSpeed());
}

int KX_CharacterWrapper::pyattr_set_jumpSpeed(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), PY_SET_ATTR_FAIL);
	const float param = PyFloat_AsDouble(value);

	if (param == -1) {
		PyErr_SetString(PyExc_ValueError, "KX_CharacterWrapper.gravity: expected a float");
		return PY_SET_ATTR_FAIL;
	}

	self->m_character->SetJumpSpeed(param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_CharacterWrapper::pyattr_get_walk_dir(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);

	return PyObjectFrom(self->m_character->GetWalkDirection());
}

int KX_CharacterWrapper::pyattr_set_walk_dir(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_CharacterWrapper *self = static_cast<KX_CharacterWrapper *>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), PY_SET_ATTR_FAIL);
	mt::vec3 dir;
	if (!PyVecTo(value, dir)) {
		PyErr_SetString(PyExc_TypeError, "KX_CharacterWrapper.walkDirection: expected a vector");
		return PY_SET_ATTR_FAIL;
	}

	self->m_character->SetWalkDirection(dir);
	return PY_SET_ATTR_SUCCESS;
}

PyObject* KX_CharacterWrapper::pyattr_get_jump_dir(EXP_PyObjectPlus* self_v, const EXP_PYATTRIBUTE_DEF* attrdef)
{
	KX_CharacterWrapper* self = static_cast<KX_CharacterWrapper*>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), nullptr);

	return PyObjectFrom(self->m_character->GetJumpDirection());
}

int KX_CharacterWrapper::pyattr_set_jump_dir(EXP_PyObjectPlus* self_v, const EXP_PYATTRIBUTE_DEF* attrdef, PyObject* value)
{
	KX_CharacterWrapper* self = static_cast<KX_CharacterWrapper*>(self_v);
	CHARACTER_VALID_CHECK_OR_RETURN(self->m_character, attrdef->m_name.c_str(), PY_SET_ATTR_FAIL);
	mt::vec3 dir;
	if (!PyVecTo(value, dir)) {
		PyErr_SetString(PyExc_TypeError, "KX_CharacterWrapper.jumpDirection: expected a vector");
		return PY_SET_ATTR_FAIL;
	}

	self->m_character->SetJumpDirection(dir);
	return PY_SET_ATTR_SUCCESS;
}

PyMethodDef KX_CharacterWrapper::Methods[] = {
	EXP_PYMETHODTABLE_NOARGS(KX_CharacterWrapper, jump),
	EXP_PYMETHODTABLE(KX_CharacterWrapper, setVelocity),
	EXP_PYMETHODTABLE_NOARGS(KX_CharacterWrapper, reset),
	{nullptr, nullptr} //Sentinel
};

EXP_PYMETHODDEF_DOC_NOARGS(KX_CharacterWrapper, jump,
                           "jump()\n"
                           "makes the character jump.\n")
{
	CHARACTER_VALID_CHECK_OR_RETURN(m_character, "jump()", nullptr);
	m_character->Jump();

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_CharacterWrapper, setVelocity,
                    "setVelocity(velocity, time, local=False)\n"
                    "set the character velocity for time period.\n")
{
	PyObject *pyvect;
	float time;
	int local = 0;

	if (!PyArg_ParseTuple(args, "Of|i:setVelocity", &pyvect, &time, &local)) {
		return nullptr;
	}

	mt::vec3 velocity;
	if (!PyVecTo(pyvect, velocity)) {
		return nullptr;
	}

	CHARACTER_VALID_CHECK_OR_RETURN(m_character, "setVelocity()", nullptr);
	m_character->SetVelocity(velocity, time, local);

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC_NOARGS(KX_CharacterWrapper, reset,
                           "reset()\n"
                           "reset the character velocity and walk direction.\n")
{
	CHARACTER_VALID_CHECK_OR_RETURN(m_character, "reset()", nullptr);
	m_character->Reset();

	Py_RETURN_NONE;
}

#endif // WITH_PYTHON
