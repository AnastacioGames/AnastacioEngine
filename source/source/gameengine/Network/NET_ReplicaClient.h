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

/** \file NET_ReplicaClient.h
 *  \ingroup network
 *  \brief Client side replication: applies Spawn/Despawn/Ownership/Snapshot to an IWorld,
 *  acknowledges snapshots and feeds the interpolation buffer.
 */

#ifndef __NET_REPLICACLIENT_H__
#define __NET_REPLICACLIENT_H__

#include "NET_IWorld.h"
#include "NET_Session.h"
#include "NET_Snapshot.h"
#include "NET_Types.h"

#include <functional>
#include <map>
#include <string>
#include <vector>

namespace net {

struct ReplicaClientConfig {
	/// Quantization, must match the server; the schema callback is replaced by the client.
	SnapshotConfig snapshot;
	/// Property layout of an object: prototype is empty for scene objects.
	std::function<const std::vector<PropertyDesc> *(NetId id, const std::string &prototype)> schema;
	size_t bufferCapacity = kSnapshotHistory;
	/// Minimum time between two FullStateRequest messages.
	uint32_t fullStateRetryMs = 1000;
	/// Leaves objects owned by this client alone when applying snapshots (prediction drives them).
	bool skipOwned = false;
	/// With skipOwned: which owned objects are left alone (the predicted ones); empty = all of them.
	std::function<bool(NetId id)> skipFilter;
};

struct ReplicaClientStats {
	uint32_t snapshotsAccepted = 0;
	uint32_t snapshotsOld = 0;  // older than the last accepted one
	uint32_t snapshotsNoBaseline = 0;
	uint32_t snapshotsInvalid = 0;
	uint32_t fullStateRequests = 0;
	uint32_t spawns = 0;
	uint32_t despawns = 0;
};

class ReplicaClient {
public:
	ReplicaClient(ClientSession &session, IWorld &world, const ReplicaClientConfig &config = ReplicaClientConfig());
	ReplicaClient(const ReplicaClient &) = delete;
	ReplicaClient &operator=(const ReplicaClient &) = delete;

	/// Returns true when the event was a replication message.
	bool handleEvent(const SessionEvent &event, uint64_t nowMs);

	/// Writes the newest snapshot into the world.
	bool applyLatest();
	/// Writes the state interpolated at renderTick + alpha into the world.
	bool applyInterpolated(Tick renderTick, float alpha);

	/// Forgets snapshots and spawned objects (new connection or scene).
	void reset();

	const SnapshotBuffer &buffer() const;
	Tick lastAcceptedTick() const;
	const ReplicaClientStats &stats() const;
	ClientId owner(NetId id) const;

private:
	void handleSnapshot(const RawMessage &raw, uint64_t nowMs);
	void requestFullState(uint64_t nowMs);
	void apply(const std::vector<ObjectState> &objects);

	ClientSession &m_session;
	IWorld &m_world;
	ReplicaClientConfig m_config;
	SnapshotBuffer m_buffer;
	Tick m_lastAccepted = kNoTick;
	uint64_t m_lastFullRequestMs = 0;
	bool m_requestedFull = false;
	/// Prototype of each spawned object (for its property schema).
	std::map<NetId, std::string> m_prototypes;
	std::map<NetId, ClientId> m_owners;
	ReplicaClientStats m_stats;
};

}  // namespace net

#endif  // __NET_REPLICACLIENT_H__
