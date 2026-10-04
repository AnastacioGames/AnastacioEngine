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

/** \file KX_NetworkManager.h
 *  \ingroup ketsji
 *  \brief Bridge between the network core (gameengine/Network, namespace net) and the game engine.
 *
 * It owns the server or client session, the replication layer and the LAN discovery, implements
 * net::IWorld on top of KX_GameObject and is ticked by KX_SimulationPipeline: one fixed logic step is
 * one network tick (docs/multiplayer-plan.md, section 2.3). Not related to the local-message classes in
 * KXNetwork/ (Message sensor/actuator), which stay as they were.
 */

#ifndef __KX_NETWORKMANAGER_H__
#define __KX_NETWORKMANAGER_H__

#include "NET_IWorld.h"
#include "NET_LagCompensation.h"
#include "NET_LanDiscovery.h"
#include "NET_ITransport.h"
#include "NET_RPC.h"
#include "NET_ReplicaClient.h"
#include "NET_Replicator.h"
#include "NET_Prediction.h"
#include "NET_Session.h"
#include "NET_Clock.h"

#include <functional>
#include <map>
#include <memory>
#include <string>
#include <vector>

class KX_GameObject;
class KX_KetsjiEngine;
class KX_Scene;

class KX_NetworkManager : public net::IWorld
{
public:
	struct HostOptions {
		/// ENet (UDP) port; 0 = scene setting.
		int port = 0;
		/// WebSocket (TCP) port; < 0 = scene setting, 0 = no WebSocket.
		int wsPort = -1;
		/// 0 = scene setting.
		int maxPlayers = 0;
		/// Empty = scene setting (Server Name).
		std::string roomName;
		/// 0 = scene setting, then the Logic tic rate of the engine.
		int tickRate = 0;
		/// 0 = scene setting.
		int snapshotRate = 0;
		/// < 0 = scene setting.
		int lan = -1;
		int lateJoin = -1;
		/// Server without local player.
		bool dedicated = false;
	};

	/// What the game script learns about the session.
	struct Event {
		enum Type {
			CONNECT,  // client: Welcome received; server: room open (client = 0)
			DISCONNECT,  // reason = DisconnectReason
			REJECT,  // reason = RejectReason, text = detail
			CHAT,  // client = sender
			START,  // the host started the match
			PLAYER_JOIN,  // client, text = name
			PLAYER_LEAVE,  // client
		};
		Type type = CONNECT;
		int client = 0;
		int reason = 0;
		std::string text;
	};

	struct PlayerInfo {
		int id = 0;
		std::string name;
		int ping = 0;
		bool ready = false;
		bool isHost = false;
	};

	explicit KX_NetworkManager(KX_KetsjiEngine *engine);
	~KX_NetworkManager() override;

	/* -------------------------------------------------------------------- */
	/** \name Session
	 * \{ */

	/// Opens a server. The scene is the active scene (KX_GetActiveScene()) unless one is given.
	bool Host(const HostOptions &options, std::string &error, KX_Scene *scene = nullptr);
	/// Joins a server. port <= 0 = scene setting.
	bool Join(const std::string &host, int port, std::string &error, KX_Scene *scene = nullptr);
	/// Leaves the session (Quit / ServerShutdown) and gives the objects back to the local simulation.
	void Disconnect();
	/// Engine stopping: Disconnect() without events, before the scenes are destroyed.
	void Shutdown();
	/// Starts the session the scene settings ask for (Host, Client or Dedicated); no-op for Offline.
	bool StartFromScene(KX_Scene *scene);

	/// A session is open (server running or client connecting/connected): the pipeline ticks us.
	bool IsActive() const;
	bool IsServer() const;
	bool IsClient() const;
	/// Server running, or client past the handshake.
	bool IsConnected() const;
	bool IsAdoptingTickRate() const;
	bool IsDedicated() const;
	/** \} */

	/* -------------------------------------------------------------------- */
	/** \name Called by KX_SimulationPipeline once per fixed logic step
	 * \{ */
	void BeginTick();
	void EndTick();
	/** \} */

	/// KX_Scene::NewRemoveObject: forget an object before it is destroyed.
	void OnObjectRemoved(KX_GameObject *obj);

	/* -------------------------------------------------------------------- */
	/** \name Replication
	 * \{ */

	struct ReplicateOptions {
		bool syncTransform = true;
		bool syncVelocity = false;
		bool syncAngular = false;
		bool alwaysRelevant = false;
		float priority = 1.0f;
		/// Names of the game properties to replicate (Bool, Int and Float only).
		std::vector<std::string> props;
	};

	/// Script registration of a scene object (same effect as the Replicate checkbox). Returns its net id
	/// (0 on failure). Run it before host()/join(), in the same order on every peer.
	net::NetId Replicate(KX_GameObject *obj, const ReplicateOptions &options, std::string &error);
	/// Server only: creates a replica of the inactive object `prototype` and replicates it. Returns it
	/// (nullptr + error on failure).
	KX_GameObject *Spawn(const std::string &prototype, net::ClientId owner, const float *position,
	                     const float *orientation, std::string &error);
	bool Despawn(KX_GameObject *obj);
	bool SetOwner(KX_GameObject *obj, net::ClientId owner);
	/// Owner of a replicated object; false when it is not replicated.
	bool GetOwner(KX_GameObject *obj, net::ClientId &owner) const;
	net::NetId GetNetId(KX_GameObject *obj) const;
	/// Replicated object with this net id, nullptr when unknown.
	KX_GameObject *FindObject(net::NetId id) const;
	/** \} */

	/* -------------------------------------------------------------------- */
	/** \name Game RPCs
	 * \{ */

	struct RpcOptions {
		std::string name;
		net::RpcTarget target = net::RpcTarget::Server;
		bool reliable = true;
		/// The caller must own the object the call is made on.
		bool requireOwner = false;
	};
	/// Runs a game RPC here. sender: calling client on the server, always 0 on clients. obj: the object of the
	/// call, nullptr for a global one.
	using RpcFunc = std::function<void(const std::string &name, net::ClientId sender, KX_GameObject *obj,
	                                   const std::vector<net::RpcArg> &args)>;
	void SetRpcSink(const RpcFunc &sink);
	/// Before host()/join(), with the same names on every peer. Names starting with "net." are reserved.
	bool RegisterRpc(const RpcOptions &options, std::string &error);
	/// obj = nullptr for a global call. False with error when it was refused here.
	bool CallRpc(const std::string &name, KX_GameObject *obj, const std::vector<net::RpcArg> &args,
	             std::string &error);
	/** \} */

	/* -------------------------------------------------------------------- */
	/** \name Input, client prediction and lag compensation
	 * \{ */

	/// Bytes of an input block the game can use; the rest carries the view time of the client.
	static constexpr size_t kInputViewBytes = 7;
	static constexpr size_t kMaxUserInputBytes = net::kMaxInputBlockBytes - kInputViewBytes;

	/// Moves a predicted object by one tick with an input (the user part of the block). Same code on every peer.
	using StepFunc = std::function<void(KX_GameObject *obj, const net::InputBlock &input)>;
	void SetStepSink(const StepFunc &sink);
	/// Marks a replicated object as moved by the step function: on the server with the owner's input, on the
	/// owning client ahead of the server (prediction, reconciled with the snapshots). False when not replicated.
	bool SetPredicted(KX_GameObject *obj, bool predicted);
	/// Input of the local player, sent every tick from now on (client) or used for the host's objects (server).
	bool SetInput(const net::InputBlock &input);
	/// Input the server applied for a client this tick (client 0 = host); false when none arrived.
	bool GetClientInput(net::ClientId client, net::InputBlock &input) const;
	/// Client: time the remote objects are drawn at. Server: the view time a client sent with its last input.
	bool GetViewTime(net::ClientId client, net::Tick &tick, float &alpha) const;
	struct PredictionInfo {
		/// Newest predicted tick, tick of the last snapshot compared with the prediction.
		net::Tick tick = net::kNoTick;
		net::Tick snapshotTick = net::kNoTick;
		/// Times the prediction timeline restarted (drift from the clock).
		uint32_t resyncs = 0;
	};
	bool GetPredictionStats(KX_GameObject *obj, net::PredictionStats &stats, PredictionInfo *info = nullptr) const;
	/// Server: how the inputs of a client arrived and were applied. False when the client has no input queue.
	bool GetInputStats(net::ClientId client, net::InputQueueStats &stats) const;

	/// Server: sphere (halfHeight 0) or capsule along the local Z axis, recorded every tick. radius <= 0 removes it.
	bool SetHitbox(KX_GameObject *obj, float radius, float halfHeight);
	/// Server: ray against the hitboxes as the client `viewOf` saw them (its view time, at most maxRewindMs back,
	/// up to the 1 s of history); viewOf < 0 tests the present. direction need not be normalized.
	bool RaycastPast(const float origin[3], const float direction[3], float maxDistance, int viewOf,
	                 KX_GameObject *ignore, KX_GameObject *&hitObj, float point[3], float &distance,
	                 int maxRewindMs = 400, net::Tick *usedTick = nullptr) const;
	/** \} */

	/* -------------------------------------------------------------------- */
	/** \name Lobby
	 * \{ */
	void SetReady(bool ready);
	bool SendChat(const std::string &text);
	/// Server only. False when someone is not ready or there is no session.
	bool StartGame();
	std::vector<PlayerInfo> GetPlayers() const;
	void SetEventSink(const std::function<void(const Event &)> &sink);
	/** \} */

	/* -------------------------------------------------------------------- */
	/** \name LAN list and network simulator
	 * \{ */
	/// First call opens the search; the following ones return what answered (request resent every ~1 s).
	const std::vector<net::LanServerEntry> &DiscoverLan();
	/// Applies to the next Host()/Join() (the transports are wrapped when created).
	void SetSimulation(uint32_t latencyMs, uint32_t jitterMs, float lossPercent);
	/** \} */

	/* -------------------------------------------------------------------- */
	/** \name Settings and state
	 * \{ */
	const std::string &GetPlayerName() const;
	void SetPlayerName(const std::string &name);
	const std::string &GetRoomName() const;
	int GetMaxPlayers() const;
	net::ClientId GetLocalClientId() const;
	net::Tick GetTick() const;
	float GetRttMs() const;
	std::string GetGameId() const;
	/** \} */

	/* IWorld */
	bool getTransform(net::NetId id, float position[3], float rotation[4]) const override;
	bool getVelocity(net::NetId id, float linear[3], float angular[3]) const override;
	bool getProperties(net::NetId id, std::vector<net::PropValue> &props) const override;
	bool isSleeping(net::NetId id) const override;
	void setTransform(net::NetId id, const float position[3], const float rotation[4]) override;
	void setVelocity(net::NetId id, const float linear[3], const float angular[3]) override;
	void setProperties(net::NetId id, const std::vector<net::PropValue> &props) override;
	bool spawn(net::NetId id, const std::string &prototype, net::ClientId owner,
	           const net::ObjectState &state) override;
	void despawn(net::NetId id) override;
	void setOwner(net::NetId id, net::ClientId owner) override;
	bool exists(net::NetId id) const override;

private:
	enum class Role { NONE, SERVER, CLIENT };

	struct SceneSettings {
		int port = 7777;
		int wsPort = 0;
		int maxPlayers = 8;
		std::string roomName;
		std::string address;
		std::string gameId;
		uint32_t gameVersion = 1;
		int tickRate = 0;
		int snapshotRate = 20;
		bool lan = true;
		bool lateJoin = true;
	};

	struct Entry {
		KX_GameObject *obj = nullptr;
		std::vector<std::string> propNames;
		std::vector<net::PropertyDesc> schema;
		net::ReplicatedObjectDesc desc;
		std::string prototype;
		bool spawned = false;
		bool dynamicsSuspended = false;
		net::ClientId owner = net::kServerClientId;
		/* Prediction (client) and step with the owner's input (server). */
		bool predicted = false;
		std::unique_ptr<net::PredictionClient> prediction;
		net::Tick lastReconciled = net::kNoTick;
		/// Visual correction added to the position after the step (client).
		float shownOffset[3] = {0.0f, 0.0f, 0.0f};
		/* Lag compensation (server). */
		bool hasHitbox = false;
		net::Hitbox hitbox;
	};

	struct ViewTime {
		net::Tick tick = net::kNoTick;
		float alpha = 0.0f;
	};

	SceneSettings ReadSceneSettings(KX_Scene *scene) const;
	bool Prepare(KX_Scene *scene, std::string &error);
	/// Registers every object with the Replicate flag of the scene and gives it its net id.
	void CollectSceneObjects();
	net::NetId AssignNetId(KX_GameObject *obj, net::NetId wanted);
	bool BuildEntry(KX_GameObject *obj, net::NetId id, const ReplicateOptions *scriptOptions, Entry &entry) const;
	void BuildSchema(KX_GameObject *obj, const std::vector<std::string> &names, Entry &entry) const;
	static void CollectProps(KX_GameObject *obj, std::vector<std::string> &names);
	uint64_t ComputeSceneHash(const std::string &sceneName) const;
	std::unique_ptr<net::ITransport> WrapSim(std::unique_ptr<net::ITransport> inner) const;
	void BuildRpc();
	void OpenSession();
	void CloseSession(bool sendQuit, bool shutdown = false);
	void ReleaseEntries(bool all);
	void AbortOpen();
	void SuspendForClient(Entry &entry);
	void RestoreFromClient(Entry &entry);
	void Emit(const Event &event);
	void ServerTickBegin(uint64_t now);
	void ClientTickBegin(uint64_t now);
	void HandleServerEvent(const net::SessionEvent &event, uint64_t now, std::vector<net::SessionEvent> &events);
	void HandleClientEvent(const net::SessionEvent &event, uint64_t now);
	void UpdateLanInfo();
	Entry *FindEntry(net::NetId id);
	const Entry *FindEntry(net::NetId id) const;
	const std::vector<net::PropertyDesc> *SchemaFor(net::NetId id, const std::string &prototype);
	KX_GameObject *CreateReplica(const std::string &prototype, std::string &error);
	void CacheProtoSchema(const std::string &prototype, KX_GameObject *original);
	void ServerStepPredicted();
	void RecordHitboxes();
	void ClientPredict(uint64_t now);
	void ResetPrediction(Entry &entry);
	void ApplyOffset(Entry &entry, const float offset[3]);
	bool PredictedState(const Entry &entry, net::ObjectState &state) const;
	void SetPredictedState(Entry &entry, const net::ObjectState &state);

	KX_KetsjiEngine *m_engine;
	KX_Scene *m_scene;
	Role m_role;
	bool m_dedicated;
	bool m_adoptingTickRate;
	bool m_prevFixedTimestep;
	double m_prevTicRate;
	bool m_sessionOpen;
	bool m_applyingRemote;
	bool m_inEmit;

	std::string m_playerName;
	std::string m_roomName;
	std::string m_gameId;
	uint32_t m_gameVersion;
	int m_maxPlayers;
	int m_snapshotRate;
	uint64_t m_sceneHash;
	std::string m_sceneName;
	net::Tick m_tick;
	net::NetSimSettings m_sim;
	bool m_simEnabled;

	std::map<net::NetId, Entry> m_entries;
	std::map<std::string, std::vector<net::PropertyDesc>> m_protoSchemas;
	std::map<std::string, std::vector<std::string>> m_protoPropNames;

	/* Server. */
	std::unique_ptr<net::ITransport> m_serverTransport;
	std::unique_ptr<net::ServerSession> m_server;
	std::unique_ptr<net::Replicator> m_replicator;
	std::unique_ptr<net::RpcServer> m_rpcServer;
	net::LanResponder m_lanResponder;
	bool m_lanActive;
	bool m_gameStarted;
	std::map<net::ClientId, bool> m_ready;
	bool m_hostReady;

	/* Client. */
	std::unique_ptr<net::ITransport> m_clientTransport;
	std::unique_ptr<net::ClientSession> m_client;
	std::unique_ptr<net::ReplicaClient> m_replica;
	std::unique_ptr<net::RpcClient> m_rpcClient;
	std::unique_ptr<net::NetClock> m_clock;
	uint32_t m_pongCount;
	net::Tick m_lastClockSnapshot;
	bool m_connectedEmitted;
	std::map<net::ClientId, bool> m_remoteReady;

	/* Input and prediction. */
	StepFunc m_stepSink;
	net::InputBlock m_input;
	bool m_inputSet;
	std::unique_ptr<net::PredictionServer> m_predServer;
	std::unique_ptr<net::LagCompensation> m_lagComp;
	int m_lagCompTickRate;
	std::map<net::ClientId, net::InputBlock> m_appliedInput;
	std::map<net::ClientId, ViewTime> m_clientView;
	std::map<net::ClientId, uint32_t> m_inputInvalid;
	/// Builds the redundant Input messages (no callbacks: the objects have their own PredictionClient).
	std::unique_ptr<net::PredictionClient> m_inputLog;
	net::Tick m_predTick;
	uint32_t m_predResyncs;
	ViewTime m_view;
	/// m_view when the game last called SetInput().
	ViewTime m_inputView;

	net::RpcTable m_rpcTable;
	std::vector<RpcOptions> m_userRpcs;
	RpcFunc m_rpcSink;
	std::function<void(const Event &)> m_eventSink;

	net::LanDiscovery m_discovery;
	uint64_t m_lastLanRequestMs;
	bool m_discoveryStarted;
};

#endif  // __KX_NETWORKMANAGER_H__
