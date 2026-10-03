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
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Ketsji/KX_LightningActuator.cpp
 *  \ingroup ketsji
 */

#include "KX_LightningActuator.h"
#include "KX_GameObject.h"
#include "KX_Scene.h"

KX_LightningActuator::KX_LightningActuator(KX_GameObject *gameobj, bool bolt)
	:SCA_IActuator(gameobj, KX_ACT_LIGHTNING),
	m_bolt(bolt)
{
}

KX_LightningActuator::~KX_LightningActuator()
{
}

bool KX_LightningActuator::Update()
{
	const bool negative = IsNegativeEvent();
	RemoveAllEvents();
	if (negative) {
		return false;
	}
	KX_GameObject *gameobj = static_cast<KX_GameObject *>(GetParent());
	gameobj->GetScene()->StrikeLightningAt(gameobj, m_bolt);
	return false;
}

EXP_Value *KX_LightningActuator::GetReplica()
{
	KX_LightningActuator *replica = new KX_LightningActuator(*this);
	replica->ProcessReplica();
	return replica;
}

#ifdef WITH_PYTHON

PyTypeObject KX_LightningActuator::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_LightningActuator",
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

PyMethodDef KX_LightningActuator::Methods[] = {
	{nullptr, nullptr} // Sentinel
};

PyAttributeDef KX_LightningActuator::Attributes[] = {
	EXP_PYATTRIBUTE_BOOL_RW("bolt", KX_LightningActuator, m_bolt),
	EXP_PYATTRIBUTE_NULL // Sentinel
};

#endif  // WITH_PYTHON
