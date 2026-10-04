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

/** \file NET_Replicator.h
 *  \ingroup network
 *  \brief Server side replication: per client delta snapshots, spawn/despawn/ownership,
 *  relevance (spatial grid) and bandwidth budget with priority accumulator (plan, section 4).
 *
 * The replicator reads object state from an IWorld and sends through a ServerSession. The game
 * forwards session events to handleEvent() and calls update() once per server tick.
 */

#ifndef __NET_REPLICATOR_H__
#define __NET_REPLICATOR_H__

#include "NET_IWorld.h"
#include "NET_Session.h"
#include "NET_Snapshot.h"
#include "NET_Types.h"

#include <map>
#include <set>
#include <string>
#include <unordered_map>
#include <vector>

namespace net {

struct ReplicatedObjectDesc {
	ClientId owner = kServerClientId;
	/// Name of the object the client creates on Spawn (runtime objects only).
	std::string prototype;
	std::vector<PropertyDesc> props;
	bool syncTransform = true;
	bool syncVelocity = false;
	bool syncAngularVelocity = false;
	/// Ignores distance: sent to every client.
	bool alwaysRelevant = false;
	/// Added to the object's priority accumulator on every snapshot it waits.
	float priority = 1.0f;
};

struct ReplicatorConfig {
	/// Quantization; the schema callback is replaced by the replicator.
	SnapshotConfig snapshot;
	/// Server ticks between snapshots (tickRate / snapshotRate).
	uint32_t snapshotIntervalTicks = 3;
	/// Bandwidth budget per client (snapshots and spawns).
	size_t bytesPerSecond = kMaxBytesPerSecond;
	/// Spatial grid cell size used for relevance queries.
	float cellSize = 32.0f;
	/// An object stays relevant until it is farther than radius * hysteresis.
	float hysteresis = 1.1f;
	/// When a client's reconnect window closes, its runtime objects are despawned
	/// (otherwise they go to the server).
	bool despawnOnExpire = true;
};

struct ReplicationStats {
	uint64_t snapshotBytes = 0;  // whole packets, header included
	uint64_t reliableBytes = 0;  // spawn, despawn and ownership packets
	uint32_t snapshotsSent = 0;
	uint32_t snapshotsSkipped = 0;  // no budget left
	size_t lastSnapshotBytes = 0;
	size_t lastSnapshotEntries = 0;  // changed + removed objects in the last snapshot
	size_t pendingObjects = 0;  // changed objects left out of the last snapshot (budget/size)
	Tick ackedTick = kNoTick;
};

class Replicator {
public:
	Replicator(ServerSession &session, IWorld &world, const ReplicatorConfig &config = ReplicatorConfig());
	Replicator(const Replicator &) = delete;
	Replicator &operator=(const Replicator &) = delete;

	/// Scene object (id from the .range file, below kFirstRuntimeNetId). Clients already have it.
	bool addSceneObject(NetId id, const ReplicatedObjectDesc &desc);
	/// Runtime object: the server picks the next NetId and clients get a Spawn.
	/// Returns kInvalidNetId on failure.
	NetId spawn(const ReplicatedObjectDesc &desc);
	/// Removes any replicated object; spawned ones get a Despawn.
	bool despawn(NetId id);
	bool setOwner(NetId id, ClientId owner);
	ClientId owner(NetId id) const;
	bool hasObject(NetId id) const;
	size_t objectCount() const;

	/// Relevance center and radius of a client; radius <= 0 means everything is relevant.
	/// Kept while the client stays connected (also across scene changes).
	void setClientView(ClientId client, const float position[3], float radius);

	/// Returns true when the event was replication related (ack, full state request, ...).
	bool handleEvent(const SessionEvent &event);
	/// Captures state from the world and sends what is due. Call once per server tick.
	void update(Tick tick, uint64_t nowMs);

	const ReplicationStats *stats(ClientId client) const;
	/// True when the client currently knows the object (spawned or scene object in its view).
	bool isRelevant(ClientId client, NetId id) const;
	const SnapshotConfig &snapshotConfig() const;

private:
	struct Object {
		ReplicatedObjectDesc desc;
		ObjectState state;
		bool hasState = false;
		/// Size of the object's fields without baseline, an upper bound for its delta.
		size_t fullBits = 0;
		/// Hash of those quantized fields: equal hashes = nothing to send.
		uint64_t fullHash = 0;
		int64_t cell[3] = {0, 0, 0};
	};

	/// A sent snapshot (the state the client has after applying it) and the field hash
	/// of each of its objects.
	struct SentSnapshot {
		Snapshot snapshot;
		std::vector<uint64_t> hashes;
	};

	struct ClientRep {
		bool active = false;
		bool hasView = false;
		float view[3] = {0.0f, 0.0f, 0.0f};
		float radius = 0.0f;
		std::map<Tick, SentSnapshot> history;
		Tick acked = kNoTick;
		uint32_t ticksSinceSnapshot = 0;
		std::vector<NetId> relevant;  // sorted
		std::set<NetId> spawned;
		std::unordered_map<NetId, float> priority;
		double tokens = 0.0;
		uint64_t lastMs = 0;
		bool hasLastMs = false;
		ReplicationStats stats;
	};

	void capture();
	void rebuildGrid();
	void computeRelevant(ClientId id, const ClientRep &rep, std::vector<NetId> &out) const;
	void activate(ClientRep &rep);
	void updateSpawns(ClientId id, ClientRep &rep, const std::vector<NetId> &relevant);
	void sendSnapshot(ClientId id, ClientRep &rep, Tick tick);
	int64_t cellCoord(float v) const;

	ServerSession &m_session;
	IWorld &m_world;
	ReplicatorConfig m_config;
	std::map<NetId, Object> m_objects;
	std::map<ClientId, ClientRep> m_clients;
	std::unordered_map<uint64_t, std::vector<NetId>> m_grid;
	std::vector<NetId> m_ungridded;  // always relevant or without transform
	std::vector<uint8_t> m_scratch;
	NetId m_nextRuntimeId = kFirstRuntimeNetId;
};

}  // namespace net

#endif  // __NET_REPLICATOR_H__
