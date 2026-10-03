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

/** \file KX_LightningActuator.h
 *  \ingroup ketsji
 *
 * Edit Object > Lightning Strike: a strike of the owner lightning emitter (an Empty with
 * Object Data > Lightning) on each positive pulse, same as obj.strikeLightning().
 */

#ifndef __KX_LIGHTNINGACTUATOR_H__
#define __KX_LIGHTNINGACTUATOR_H__

#include "SCA_IActuator.h"

class KX_GameObject;

class KX_LightningActuator : public SCA_IActuator
{
	Py_Header

	bool m_bolt;

public:
	KX_LightningActuator(KX_GameObject *gameobj, bool bolt);
	virtual ~KX_LightningActuator();

	virtual EXP_Value *GetReplica();
	virtual bool Update();
};

#endif  // __KX_LIGHTNINGACTUATOR_H__
