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

/** \file NET_IWorld.h
 *  \ingroup network
 *  \brief Abstract game world seen by the replication layer.
 *
 * The engine implements it later on top of KX_GameObject. Server side, the replicator reads
 * object state from it; client side, NET_ReplicaClient creates, updates and removes objects
 * through it. Rotations are x,y,z,w quaternions; properties follow the object's schema.
 */

#ifndef __NET_IWORLD_H__
#define __NET_IWORLD_H__

#include "NET_Snapshot.h"
#include "NET_Types.h"

#include <string>
#include <vector>

namespace net {

class IWorld {
public:
	virtual ~IWorld() = default;

	/* Read side (server). Returns false when the object does not exist. */
	virtual bool getTransform(NetId id, float position[3], float rotation[4]) const = 0;
	virtual bool getVelocity(NetId id, float linear[3], float angular[3]) const = 0;
	virtual bool getProperties(NetId id, std::vector<PropValue> &props) const = 0;
	/// Physics at rest (Bullet "sleeping"): the replicator keeps the last captured state.
	virtual bool isSleeping(NetId id) const = 0;

	/* Write side (client). */
	virtual void setTransform(NetId id, const float position[3], const float rotation[4]) = 0;
	virtual void setVelocity(NetId id, const float linear[3], const float angular[3]) = 0;
	virtual void setProperties(NetId id, const std::vector<PropValue> &props) = 0;

	/// Runtime object created by the server (Spawn). Returns false if the prototype is unknown.
	virtual bool spawn(NetId id, const std::string &prototype, ClientId owner, const ObjectState &state) = 0;
	virtual void despawn(NetId id) = 0;
	virtual void setOwner(NetId id, ClientId owner) = 0;
	/// True when the object exists locally (scene object or spawned).
	virtual bool exists(NetId id) const = 0;
};

}  // namespace net

#endif  // __NET_IWORLD_H__
