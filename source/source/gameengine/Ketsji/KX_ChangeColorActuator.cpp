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

/** \file gameengine/Ketsji/KX_ChangeColorActuator.cpp
 *  \ingroup ketsji
 */

#include "KX_ChangeColorActuator.h"
#include "KX_GameObject.h"
#include "KX_PyMath.h"

KX_ChangeColorActuator::KX_ChangeColorActuator(KX_GameObject *gameobj,
											   mathfu::vec4 col,
											   bool useLerpcol,
											   float lerpcol) :
	SCA_IActuator(gameobj, KX_ACT_CHANGE_COLOR),
	m_col(col),
	m_useLerpcol(useLerpcol),
	m_lerpcol(lerpcol)
{
	// intentionally empty
} /* End of constructor */



KX_ChangeColorActuator::~KX_ChangeColorActuator()
{
	// there's nothing to be done here, really....
} /* end of destructor */



bool KX_ChangeColorActuator::Update()
{
	// bool result = false;	/*unused*/
	bool bNegativeEvent = IsNegativeEvent();
	RemoveAllEvents();

	if (bNegativeEvent) {
		return false; // do nothing on negative events
	}
	KX_GameObject *gameobj = static_cast<KX_GameObject*>(GetParent()); 
	gameobj->SetObjectColor(m_useLerpcol ? mathfu::vec4().Lerp(gameobj->GetObjectColor(), m_col, m_lerpcol) : m_col);
	
	return false;
}



EXP_Value *KX_ChangeColorActuator::GetReplica()
{
	KX_ChangeColorActuator *replica =
		new KX_ChangeColorActuator(*this);
	if (replica == nullptr) {
		return nullptr;
	}

	replica->ProcessReplica();
	return replica;
};

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python functions : integration hooks                                      */
/* ------------------------------------------------------------------------- */

PyTypeObject KX_ChangeColorActuator::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_ChangeColorActuator",
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
	&SCA_IActuator::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_ChangeColorActuator::Methods[] = {
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_ChangeColorActuator::Attributes[] = {
	EXP_PYATTRIBUTE_BOOL_RW("useLerp", KX_ChangeColorActuator, m_useLerpcol),
	EXP_PYATTRIBUTE_FLOAT_RW("lerp", 0.1f, 1.0f, KX_ChangeColorActuator, m_lerpcol),
	EXP_PYATTRIBUTE_RW_FUNCTION("color", KX_ChangeColorActuator, pyattr_get_color, pyattr_set_color),
	EXP_PYATTRIBUTE_NULL    //Sentinel
};

PyObject *KX_ChangeColorActuator::pyattr_get_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_ChangeColorActuator *self = static_cast<KX_ChangeColorActuator*>(self_v);
	return PyColorFromVector(self->m_col);

}

int KX_ChangeColorActuator::pyattr_set_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_ChangeColorActuator *self = static_cast<KX_ChangeColorActuator*>(self_v);
	mt::vec4 obcolor;
	if (!PyVecTo(value, obcolor)) {
		return PY_SET_ATTR_FAIL;
	}

	self->m_col = obcolor;
	return PY_SET_ATTR_SUCCESS;
}

#endif // WITH_PYTHON

/* eof */
