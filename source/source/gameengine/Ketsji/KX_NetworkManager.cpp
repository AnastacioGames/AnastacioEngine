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

/** \file gameengine/Ketsji/KX_NetworkManager.cpp
 *  \ingroup ketsji
 */

#include "KX_NetworkManager.h"

#include "KX_GameObject.h"
#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "KX_Scene.h"

#include "EXP_BoolValue.h"
#include "EXP_FloatValue.h"
#include "EXP_IntValue.h"
#include "EXP_ListValue.h"
#include "PHY_IPhysicsController.h"

#include "CM_Message.h"

#include "NET_Messages.h"
#include "NET_TransportWeb.h"

#include <algorithm>
#include <cmath>
#include <cstring>

extern "C" {
#  include "DNA_object_types.h"
#  include "DNA_property_types.h"
#  include "DNA_scene_types.h"
}

namespace {

/// 32 bit FNV-1a of the object name: the id of an object saved without one. Same on every peer.
uint32_t NameHash(const std::string &name)
{
	uint32_t hash = 2166136261u;
	for (const char c : name) {
		hash ^= uint8_t(c);
		hash *= 16777619u;
	}
	return hash;
}

net::PropValue DefaultValue(net::PropKind kind)
{
	switch (kind) {
		case net::PropKind::Bool:
			return net::PropValue::makeBool(false);
		case net::PropKind::Int:
			return net::PropValue::makeInt(0);
		case net::PropKind::Float:
			break;
	}
	return net::PropValue::makeFloat(0.0f);
}

/// Replicable kind of a runtime game property; false for strings, timers and missing ones.
bool KindOf(KX_GameObject *obj, const std::string &name, net::PropKind &kind)
{
	EXP_Value *value = obj->GetProperty(name);
	if (!value) {
		return false;
	}
	switch (value->GetValueType()) {
		case VALUE_BOOL_TYPE:
			kind = net::PropKind::Bool;
			return true;
		case VALUE_INT_TYPE:
			kind = net::PropKind::Int;
			return true;
		case VALUE_FLOAT_TYPE:
			kind = net::PropKind::Float;
			return true;
		default:
			return false;
	}
}

void ToQuat(const mt::mat3 &orientation, float rotation[4])
{
	const mt::quat q = mt::quat::FromMatrix(orientation).Normalized();
	rotation[0] = q.vector()[0];
	rotation[1] = q.vector()[1];
	rotation[2] = q.vector()[2];
	rotation[3] = q.scalar();
}

mt::mat3 FromQuat(const float rotation[4])
{
	/* Wire order is x,y,z,w; mathfu takes the scalar first. A zero quaternion (never sent by a healthy
	 * peer) would give NaNs, so it becomes the identity. */
	const float len = std::sqrt(rotation[0] * rotation[0] + rotation[1] * rotation[1] +
	                            rotation[2] * rotation[2] + rotation[3] * rotation[3]);
	if (!(len > 1e-6f)) {
		return mt::mat3::Identity();
	}
	const float inv = 1.0f / len;
	return mt::quat(rotation[3] * inv, rotation[0] * inv, rotation[1] * inv, rotation[2] * inv).ToMatrix();
}

/* Input block: [1][render tick u32][alpha u16] then the game's bytes; [0][6 zero bytes] before the first
 * snapshot was drawn. The server rewinds the hitboxes to that time (lag compensation). */
void WriteView(net::InputBlock &block, net::Tick tick, float alpha)
{
	const bool has = tick != net::kNoTick;
	const uint16_t a = uint16_t(std::min(std::max(alpha, 0.0f), 1.0f) * 65535.0f + 0.5f);
	block.push_back(has ? 1 : 0);
	for (int i = 0; i < 4; ++i) {
		block.push_back(has ? uint8_t(tick >> (8 * i)) : 0);
	}
	block.push_back(has ? uint8_t(a) : 0);
	block.push_back(has ? uint8_t(a >> 8) : 0);
}

bool ReadView(const net::InputBlock &block, net::Tick &tick, float &alpha, net::InputBlock &user)
{
	if (block.size() < KX_NetworkManager::kInputViewBytes || block[0] > 1) {
		return false;
	}
	tick = net::kNoTick;
	alpha = 0.0f;
	if (block[0] == 1) {
		tick = net::Tick(block[1]) | (net::Tick(block[2]) << 8) | (net::Tick(block[3]) << 16) |
		       (net::Tick(block[4]) << 24);
		alpha = float(uint16_t(block[5] | (block[6] << 8))) / 65535.0f;
	}
	user.assign(block.begin() + KX_NetworkManager::kInputViewBytes, block.end());
	return true;
}

}  // namespace

KX_NetworkManager::KX_NetworkManager(KX_KetsjiEngine *engine)
	:m_engine(engine),
	m_scene(nullptr),
	m_role(Role::NONE),
	m_dedicated(false),
	m_adoptingTickRate(false),
	m_prevFixedTimestep(false),
	m_prevTicRate(60.0),
	m_sessionOpen(false),
	m_applyingRemote(false),
	m_inEmit(false),
	m_playerName("Player"),
	m_gameVersion(1),
	m_maxPlayers(8),
	m_snapshotRate(20),
	m_sceneHash(0),
	m_tick(net::kNoTick),
	m_simEnabled(false),
	m_lanActive(false),
	m_gameStarted(false),
	m_hostReady(false),
	m_pongCount(0),
	m_lastClockSnapshot(net::kNoTick),
	m_connectedEmitted(false),
	m_inputSet(false),
	m_lagCompTickRate(60),
	m_predTick(net::kNoTick),
	m_predResyncs(0),
	m_lastLanRequestMs(0),
	m_discoveryStarted(false)
{
	BuildRpc();
}

KX_NetworkManager::~KX_NetworkManager()
{
	Shutdown();
}

/* -------------------------------------------------------------------- */
/** \name Settings
 * \{ */

KX_NetworkManager::SceneSettings KX_NetworkManager::ReadSceneSettings(KX_Scene *scene) const
{
	SceneSettings settings;
	Scene *bscene = scene ? scene->GetBlenderScene() : nullptr;
	if (!bscene) {
		settings.roomName = "Anastacio Server";
		settings.gameId = "anastacio-game";
		return settings;
	}
	/* A zeroed struct (scene created before the settings existed and not through versioning) falls back to
	 * the defaults of the Network panel. */
	const RangeNetworkSettings &net = bscene->gm.network;
	settings.port = net.port > 0 ? net.port : 7777;
	settings.wsPort = net.ws_port;
	settings.maxPlayers = net.max_players > 0 ? net.max_players : 8;
	settings.roomName = net.server_name[0] ? net.server_name : "Anastacio Server";
	settings.address = net.address[0] ? net.address : "127.0.0.1";
	settings.gameId = net.game_id[0] ? net.game_id : "anastacio-game";
	settings.gameVersion = net.game_version > 0 ? uint32_t(net.game_version) : 1u;
	settings.tickRate = net.tick_rate;
	settings.snapshotRate = net.snapshot_rate > 0 ? net.snapshot_rate : 20;
	settings.lan = (net.flags & NET_SCENE_LAN_DISCOVERY) != 0;
	settings.lateJoin = (net.flags & NET_SCENE_LATE_JOIN) != 0;
	return settings;
}

const std::string &KX_NetworkManager::GetPlayerName() const
{
	return m_playerName;
}

void KX_NetworkManager::SetPlayerName(const std::string &name)
{
	m_playerName = name.substr(0, net::kMaxStringBytes);
}

const std::string &KX_NetworkManager::GetRoomName() const
{
	return m_roomName;
}

int KX_NetworkManager::GetMaxPlayers() const
{
	return m_maxPlayers;
}

net::ClientId KX_NetworkManager::GetLocalClientId() const
{
	return (m_role == Role::CLIENT && m_client) ? m_client->clientId() : net::kServerClientId;
}

net::Tick KX_NetworkManager::GetTick() const
{
	return m_tick;
}

float KX_NetworkManager::GetRttMs() const
{
	return (m_role == Role::CLIENT && m_client) ? m_client->rttMs() : 0.0f;
}

std::string KX_NetworkManager::GetGameId() const
{
	if (!m_gameId.empty()) {
		return m_gameId;
	}
	return ReadSceneSettings(KX_GetActiveScene()).gameId;
}

bool KX_NetworkManager::IsActive() const
{
	return m_role != Role::NONE;
}

bool KX_NetworkManager::IsServer() const
{
	return m_role == Role::SERVER;
}

bool KX_NetworkManager::IsClient() const
{
	return m_role == Role::CLIENT;
}

bool KX_NetworkManager::IsConnected() const
{
	if (m_role == Role::SERVER) {
		return true;
	}
	return m_role == Role::CLIENT && m_client && m_client->state() == net::ClientSession::State::Connected;
}

bool KX_NetworkManager::IsAdoptingTickRate() const
{
	return m_adoptingTickRate;
}

bool KX_NetworkManager::IsDedicated() const
{
	return m_dedicated;
}

void KX_NetworkManager::SetEventSink(const std::function<void(const Event &)> &sink)
{
	m_eventSink = sink;
}

void KX_NetworkManager::Emit(const Event &event)
{
	if (m_eventSink) {
		m_eventSink(event);
	}
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Objects and ids
 * \{ */

net::NetId KX_NetworkManager::AssignNetId(KX_GameObject *obj, net::NetId wanted)
{
	const auto usable = [this](net::NetId id) {
		return id != net::kInvalidNetId && id < net::kFirstRuntimeNetId && !m_entries.count(id);
	};

	if (usable(wanted)) {
		return wanted;
	}

	/* Saved id missing or taken by another object (a duplicate made outside the editor): derive one from
	 * the name. It is deterministic, so a server and a client running the same .range agree on it. */
	net::NetId id = NameHash(obj->GetName()) & 0x7FFFFFFFu;
	for (int tries = 0; tries < 0x10000 && !usable(id); ++tries) {
		id = (id + 1) & 0x7FFFFFFFu;
	}
	if (wanted != net::kInvalidNetId) {
		CM_Warning("network: object '" << obj->GetName() << "' has net id " << wanted
		           << " already in use, using " << id << " (open and save the file again to fix it)");
	}
	return usable(id) ? id : net::kInvalidNetId;
}

void KX_NetworkManager::CollectProps(KX_GameObject *obj, std::vector<std::string> &names)
{
	Object *ob = obj->GetBlenderObject();
	if (!ob) {
		return;
	}
	for (bProperty *prop = (bProperty *)ob->prop.first; prop; prop = prop->next) {
		if (prop->flag & PROP_REPLICATED) {
			names.push_back(prop->name);
		}
	}
}

void KX_NetworkManager::BuildSchema(KX_GameObject *obj, const std::vector<std::string> &names, Entry &entry) const
{
	entry.propNames.clear();
	entry.schema.clear();
	for (const std::string &name : names) {
		net::PropKind kind;
		if (!KindOf(obj, name, kind)) {
			CM_Warning("network: property '" << name << "' of '" << obj->GetName()
			           << "' is missing or not Boolean/Integer/Float, not replicated");
			continue;
		}
		net::PropertyDesc desc;
		desc.kind = kind;
		entry.propNames.push_back(name);
		entry.schema.push_back(desc);
	}
	entry.desc.props = entry.schema;
}

bool KX_NetworkManager::BuildEntry(KX_GameObject *obj, net::NetId id, const ReplicateOptions *scriptOptions,
                                   Entry &entry) const
{
	(void)id;
	entry = Entry();
	entry.obj = obj;
	std::vector<std::string> names;

	if (scriptOptions) {
		entry.desc.syncTransform = scriptOptions->syncTransform;
		entry.desc.syncVelocity = scriptOptions->syncVelocity;
		entry.desc.syncAngularVelocity = scriptOptions->syncAngular;
		entry.desc.alwaysRelevant = scriptOptions->alwaysRelevant;
		entry.desc.priority = scriptOptions->priority > 0.0f ? scriptOptions->priority : 1.0f;
		names = scriptOptions->props;
	}
	else if (Object *ob = obj->GetBlenderObject()) {
		const int flags = ob->net.flags;
		entry.desc.syncTransform = (flags & NET_OBJ_SYNC_TRANSFORM) != 0;
		entry.desc.syncVelocity = (flags & NET_OBJ_SYNC_VELOCITY) != 0;
		entry.desc.syncAngularVelocity = (flags & NET_OBJ_SYNC_ANGULAR) != 0;
		entry.desc.alwaysRelevant = (flags & NET_OBJ_ALWAYS_RELEVANT) != 0;
		entry.desc.priority = ob->net.priority > 0.0f ? ob->net.priority : 1.0f;
		CollectProps(obj, names);
	}
	BuildSchema(obj, names, entry);
	return true;
}

void KX_NetworkManager::CollectSceneObjects()
{
	if (!m_scene) {
		return;
	}
	EXP_ListValue<KX_GameObject> *list = m_scene->GetObjectList();
	std::vector<KX_GameObject *> found;
	for (int i = 0; i < list->GetCount(); ++i) {
		KX_GameObject *obj = list->GetValue(i);
		Object *ob = obj->GetBlenderObject();
		if (ob && (ob->net.flags & NET_OBJ_REPLICATE) && obj->GetNetId() == 0) {
			found.push_back(obj);
		}
	}
	/* Objects with a saved id claim it first (in name order), the others come after: the outcome does not
	 * depend on the order the converter listed them. */
	std::sort(found.begin(), found.end(), [](KX_GameObject *a, KX_GameObject *b) {
		const bool ha = a->GetBlenderObject()->net.net_id != 0;
		const bool hb = b->GetBlenderObject()->net.net_id != 0;
		if (ha != hb) {
			return ha;
		}
		return a->GetName() < b->GetName();
	});
	for (KX_GameObject *obj : found) {
		const net::NetId id = AssignNetId(obj, obj->GetBlenderObject()->net.net_id);
		if (id == net::kInvalidNetId) {
			CM_Warning("network: no free net id for '" << obj->GetName() << "'");
			continue;
		}
		Entry entry;
		BuildEntry(obj, id, nullptr, entry);
		obj->SetNetId(id);
		m_entries[id] = std::move(entry);
	}
}

net::NetId KX_NetworkManager::Replicate(KX_GameObject *obj, const ReplicateOptions &options, std::string &error)
{
	if (!obj) {
		error = "no object";
		return net::kInvalidNetId;
	}
	if (m_sessionOpen) {
		error = "replicate() must run before host()/join(): the ids are part of the handshake";
		return net::kInvalidNetId;
	}
	if (obj->GetNetId() != 0) {
		return obj->GetNetId();  // already registered (checkbox or an earlier call)
	}
	Object *ob = obj->GetBlenderObject();
	const net::NetId id = AssignNetId(obj, ob ? ob->net.net_id : net::kInvalidNetId);
	if (id == net::kInvalidNetId) {
		error = "no free net id";
		return net::kInvalidNetId;
	}
	Entry entry;
	BuildEntry(obj, id, &options, entry);
	obj->SetNetId(id);
	m_entries[id] = std::move(entry);
	return id;
}

uint64_t KX_NetworkManager::ComputeSceneHash(const std::string &sceneName) const
{
	std::vector<net::NetId> ids;
	for (const auto &pair : m_entries) {
		if (!pair.second.spawned) {
			ids.push_back(pair.first);
		}
	}
	return net::sceneHash(sceneName, ids);
}

net::NetId KX_NetworkManager::GetNetId(KX_GameObject *obj) const
{
	return obj ? obj->GetNetId() : net::kInvalidNetId;
}

KX_GameObject *KX_NetworkManager::FindObject(net::NetId id) const
{
	const Entry *entry = FindEntry(id);
	return entry ? entry->obj : nullptr;
}

bool KX_NetworkManager::GetOwner(KX_GameObject *obj, net::ClientId &owner) const
{
	const Entry *entry = obj ? FindEntry(obj->GetNetId()) : nullptr;
	if (!entry) {
		return false;
	}
	owner = entry->owner;
	return true;
}

KX_NetworkManager::Entry *KX_NetworkManager::FindEntry(net::NetId id)
{
	const auto it = m_entries.find(id);
	return it == m_entries.end() ? nullptr : &it->second;
}

const KX_NetworkManager::Entry *KX_NetworkManager::FindEntry(net::NetId id) const
{
	const auto it = m_entries.find(id);
	return it == m_entries.end() ? nullptr : &it->second;
}

const std::vector<net::PropertyDesc> *KX_NetworkManager::SchemaFor(net::NetId id, const std::string &prototype)
{
	if (const Entry *entry = FindEntry(id)) {
		return &entry->schema;
	}
	if (!prototype.empty()) {
		/* A client decodes the Spawn fields with this schema before it creates the object. */
		if (!m_protoSchemas.count(prototype) && m_scene) {
			CacheProtoSchema(prototype, m_scene->GetInactiveList()->FindValue(prototype));
		}
		const auto it = m_protoSchemas.find(prototype);
		if (it != m_protoSchemas.end()) {
			return &it->second;
		}
	}
	return nullptr;
}

KX_GameObject *KX_NetworkManager::CreateReplica(const std::string &prototype, std::string &error)
{
	if (!m_scene) {
		error = "no scene";
		return nullptr;
	}
	KX_GameObject *original = m_scene->GetInactiveList()->FindValue(prototype);
	if (!original) {
		error = "prototype '" + prototype + "' not found among the inactive objects (put it in a hidden layer)";
		return nullptr;
	}
	KX_GameObject *replica = m_scene->AddReplicaObject(original, nullptr, 0.0f);
	if (!replica) {
		error = "could not create '" + prototype + "'";
		return nullptr;
	}
	replica->Release();  // the scene holds the object now, as KX_AddObjectActuator does
	CacheProtoSchema(prototype, original);
	return replica;
}

void KX_NetworkManager::CacheProtoSchema(const std::string &prototype, KX_GameObject *original)
{
	/* Remember what the prototype replicates, for the schema of this and later spawns. */
	if (m_protoSchemas.count(prototype) || !original) {
		return;
	}
	Entry proto;
	std::vector<std::string> names;
	CollectProps(original, names);
	BuildSchema(original, names, proto);
	m_protoSchemas[prototype] = proto.schema;
	m_protoPropNames[prototype] = proto.propNames;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name RPC table (lobby)
 * \{ */

void KX_NetworkManager::BuildRpc()
{
	m_rpcTable = net::RpcTable();
	/* Lobby messages that the protocol has no message for. "Owner" RPCs go from the server to one
	 * client only, so a client cannot fake them. */
	net::RpcDesc ready;
	ready.name = "net.ready";
	ready.target = net::RpcTarget::Server;
	ready.checkArgs = true;
	ready.argTypes = {net::RpcArgType::Bool};
	ready.handler = [this](const net::RpcCall &call) {
		if (m_role != Role::SERVER || !call.args || call.args->empty()) {
			return;
		}
		const bool value = (*call.args)[0].b;
		m_ready[call.caller] = value;
		std::vector<net::RpcArg> args(2);
		args[0].type = net::RpcArgType::Int;
		args[0].i = call.caller;
		args[1].type = net::RpcArgType::Bool;
		args[1].b = value;
		const int id = m_rpcTable.idOf("net.ready_state");
		for (net::ClientId client : m_server->clients()) {
			m_rpcServer->callClient(client, uint16_t(id), net::kInvalidNetId, args);
		}
	};
	m_rpcTable.add(ready);

	net::RpcDesc readyState;
	readyState.name = "net.ready_state";
	readyState.target = net::RpcTarget::Owner;
	readyState.checkArgs = true;
	readyState.argTypes = {net::RpcArgType::Int, net::RpcArgType::Bool};
	readyState.handler = [this](const net::RpcCall &call) {
		if (!call.args || call.args->size() != 2) {
			return;
		}
		m_remoteReady[net::ClientId((*call.args)[0].i)] = (*call.args)[1].b;
	};
	m_rpcTable.add(readyState);

	net::RpcDesc start;
	start.name = "net.start";
	start.target = net::RpcTarget::Owner;
	start.checkArgs = true;
	start.handler = [this](const net::RpcCall &) {
		Event event;
		event.type = Event::START;
		Emit(event);
	};
	m_rpcTable.add(start);

	for (const RpcOptions &options : m_userRpcs) {
		net::RpcDesc desc;
		desc.name = options.name;
		desc.target = options.target;
		desc.reliable = options.reliable;
		desc.requireOwner = options.requireOwner;
		const std::string name = options.name;
		desc.handler = [this, name](const net::RpcCall &call) {
			if (!m_rpcSink || !call.args) {
				return;
			}
			KX_GameObject *obj = nullptr;
			if (call.netId != net::kInvalidNetId) {
				const Entry *entry = FindEntry(call.netId);
				if (!entry || !entry->obj) {
					return;
				}
				obj = entry->obj;
			}
			m_rpcSink(name, call.caller, obj, *call.args);
		};
		m_rpcTable.add(desc);
	}

	/* Ids follow the sorted names, so every peer with the same RPCs agrees on them. */
	m_rpcTable.finalize();
}

void KX_NetworkManager::SetRpcSink(const RpcFunc &sink)
{
	m_rpcSink = sink;
}

bool KX_NetworkManager::RegisterRpc(const RpcOptions &options, std::string &error)
{
	if (m_role != Role::NONE) {
		error = "register RPCs before host()/join(): the table is fixed while a session is open";
		return false;
	}
	if (options.name.empty() || options.name.size() > net::kMaxStringBytes || options.name.compare(0, 4, "net.") == 0) {
		error = "invalid or reserved name '" + options.name + "'";
		return false;
	}
	for (RpcOptions &existing : m_userRpcs) {
		if (existing.name == options.name) {
			existing = options;  // the script ran again (scene restart): same name, latest settings
			BuildRpc();
			return true;
		}
	}
	if (m_rpcTable.size() >= 0xFFFF) {
		error = "RPC table full";
		return false;
	}
	m_userRpcs.push_back(options);
	BuildRpc();
	return true;
}

bool KX_NetworkManager::CallRpc(const std::string &name, KX_GameObject *obj, const std::vector<net::RpcArg> &args,
                                std::string &error)
{
	const net::RpcDesc *desc = m_rpcTable.find(name);
	if (!desc || name.compare(0, 4, "net.") == 0) {
		error = "unknown RPC '" + name + "'";
		return false;
	}
	net::NetId id = net::kInvalidNetId;
	if (obj) {
		id = obj->GetNetId();
		if (id == net::kInvalidNetId || !FindEntry(id)) {
			error = "the object is not replicated";
			return false;
		}
	}
	bool ok = false;
	if (m_role == Role::SERVER && m_rpcServer) {
		ok = m_rpcServer->call(name, id, args);
	}
	else if (m_role == Role::CLIENT && m_rpcClient && IsConnected()) {
		ok = m_rpcClient->call(name, id, args);
	}
	else {
		error = "no session";
		return false;
	}
	if (!ok) {
		error = "refused (target, owner, arguments over 1024 bytes, or an 'owner' RPC called by a client)";
	}
	return ok;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Session
 * \{ */

std::unique_ptr<net::ITransport> KX_NetworkManager::WrapSim(std::unique_ptr<net::ITransport> inner) const
{
	if (!m_simEnabled || !inner) {
		return inner;
	}
	return net::createSimulatedTransport(std::move(inner), m_sim);
}

void KX_NetworkManager::SetSimulation(uint32_t latencyMs, uint32_t jitterMs, float lossPercent)
{
	m_sim.latencyMs = std::min<uint32_t>(latencyMs, 2000);
	m_sim.jitterMs = std::min<uint32_t>(jitterMs, 1000);
	m_sim.lossPercent = std::min(std::max(lossPercent, 0.0f), 90.0f);
	m_simEnabled = (m_sim.latencyMs != 0 || m_sim.jitterMs != 0 || m_sim.lossPercent > 0.0f);
}

bool KX_NetworkManager::Prepare(KX_Scene *scene, std::string &error)
{
	if (IsActive()) {
		error = "already in a session (call disconnect() first)";
		return false;
	}
	if (!scene) {
		scene = KX_GetActiveScene();
	}
	if (!scene) {
		error = "no active scene";
		return false;
	}
	m_scene = scene;
	m_sceneName = scene->GetName();
	CollectSceneObjects();
	m_sceneHash = ComputeSceneHash(m_sceneName);
	return true;
}

void KX_NetworkManager::OpenSession()
{
	m_sessionOpen = true;
	m_prevFixedTimestep = m_engine->GetUseFixedTimestep();
	m_prevTicRate = m_engine->GetTicRate();
	m_engine->SetUseFixedTimestep(true);
	m_tick = net::kNoTick;
	m_ready.clear();
	m_remoteReady.clear();
	m_hostReady = false;
	m_gameStarted = false;
	m_connectedEmitted = false;
	m_pongCount = 0;
	m_lastClockSnapshot = net::kNoTick;
}

void KX_NetworkManager::AbortOpen()
{
	/* Host()/Join() failed after Prepare(): leave everything as before the call. */
	if (m_sessionOpen) {
		m_engine->SetUseFixedTimestep(m_prevFixedTimestep);
		m_engine->SetTicRate(m_prevTicRate);
	}
	m_rpcServer.reset();
	m_replicator.reset();
	m_server.reset();
	m_serverTransport.reset();
	m_rpcClient.reset();
	m_replica.reset();
	m_client.reset();
	m_clientTransport.reset();
	ReleaseEntries(false);
	m_sessionOpen = false;
	m_scene = nullptr;
	m_role = Role::NONE;
}

bool KX_NetworkManager::Host(const HostOptions &options, std::string &error, KX_Scene *scene)
{
	if (!Prepare(scene, error)) {
		return false;
	}
	const SceneSettings settings = ReadSceneSettings(m_scene);

	const int port = options.port > 0 ? options.port : settings.port;
	const int wsPort = options.wsPort >= 0 ? options.wsPort : settings.wsPort;
	m_maxPlayers = std::min(std::max(options.maxPlayers > 0 ? options.maxPlayers : settings.maxPlayers, 1),
	                        net::kMaxClients);
	m_roomName = options.roomName.empty() ? settings.roomName : options.roomName;
	m_gameId = settings.gameId;
	m_gameVersion = settings.gameVersion;
	m_snapshotRate = std::max(options.snapshotRate > 0 ? options.snapshotRate : settings.snapshotRate, 1);
	const int tickSetting = options.tickRate > 0 ? options.tickRate : settings.tickRate;
	const bool lan = options.lan >= 0 ? options.lan != 0 : settings.lan;
	const bool lateJoin = options.lateJoin >= 0 ? options.lateJoin != 0 : settings.lateJoin;
	/* A headless server (--server) has no local player: always dedicated. */
	m_dedicated = options.dedicated || m_engine->IsServerMode();

	OpenSession();
	if (tickSetting > 0) {
		m_engine->SetTicRate(double(tickSetting));
	}
	const int tickRate = std::min(std::max(int(std::lround(m_engine->GetTicRate())), 1), 240);
	m_snapshotRate = std::min(m_snapshotRate, tickRate);

	std::unique_ptr<net::ITransport> enet = net::createENetTransport();
	std::unique_ptr<net::ITransport> transport;
	if (wsPort > 0) {
		std::vector<net::MultiTransportEntry> entries;
		entries.push_back({WrapSim(std::move(enet)), uint16_t(port)});
		entries.push_back({WrapSim(net::createWebSocketServerTransport()), uint16_t(wsPort)});
		transport = net::createMultiTransport(std::move(entries));
	}
	else {
		transport = WrapSim(std::move(enet));
	}
	m_serverTransport = std::move(transport);

	net::ServerConfig config;
	config.gameId = m_gameId;
	config.gameVersion = m_gameVersion;
	config.sceneName = m_sceneName;
	config.sceneHash = m_sceneHash;
	config.tickRate = uint16_t(tickRate);
	config.snapshotRate = uint16_t(m_snapshotRate);
	config.maxClients = m_maxPlayers;
	config.allowLateJoin = lateJoin;
	m_server.reset(new net::ServerSession(*m_serverTransport, config));
	if (!m_server->start(uint16_t(port))) {
		error = "could not listen on port " + std::to_string(port) + " (in use?)";
		AbortOpen();
		return false;
	}

	net::ReplicatorConfig rc;
	rc.snapshotIntervalTicks = uint32_t(std::max(1, tickRate / m_snapshotRate));
	m_replicator.reset(new net::Replicator(*m_server, *this, rc));
	m_predServer.reset(new net::PredictionServer());
	net::LagCompensationConfig lc;
	lc.tickRate = uint16_t(tickRate);
	lc.maxRewindMs = lc.historyMs;  // RaycastPast() clamps with the limit the game asks for
	m_lagCompTickRate = tickRate;
	m_lagComp.reset(new net::LagCompensation(lc));
	for (const auto &pair : m_entries) {
		if (!pair.second.spawned) {
			m_replicator->addSceneObject(pair.first, pair.second.desc);
		}
	}
	m_rpcServer.reset(new net::RpcServer(*m_server, m_rpcTable, [this](net::NetId id, net::ClientId &owner) {
		const Entry *entry = FindEntry(id);
		if (!entry) {
			return false;
		}
		owner = entry->owner;
		return true;
	}));

	m_lanActive = false;
	if (lan) {
		if (m_lanResponder.start()) {
			m_lanActive = true;
			UpdateLanInfo();
		}
		else {
			CM_Warning("network: LAN discovery port is busy, this server will not show in the LAN list");
		}
	}

	m_role = Role::SERVER;
	CM_Message("network: hosting '" << m_roomName << "' (scene " << m_sceneName << ") on UDP " << port
	           << (wsPort > 0 ? " and WebSocket " + std::to_string(wsPort) : std::string())
	           << ", tick " << tickRate << " Hz, snapshots " << m_snapshotRate << " Hz, "
	           << m_entries.size() << " replicated object(s)");

	Event event;
	event.type = Event::CONNECT;
	event.client = 0;
	Emit(event);
	return true;
}

bool KX_NetworkManager::Join(const std::string &host, int port, std::string &error, KX_Scene *scene)
{
	if (!Prepare(scene, error)) {
		return false;
	}
	if (m_engine->IsServerMode()) {
		CM_Warning("network: join() on a headless server (--server): this client draws nothing");
	}
	const SceneSettings settings = ReadSceneSettings(m_scene);
	if (port <= 0) {
		port = settings.port;
	}
	m_gameId = settings.gameId;
	m_gameVersion = settings.gameVersion;
	m_roomName.clear();
	m_maxPlayers = 0;
	m_dedicated = false;

	OpenSession();

	std::unique_ptr<net::ITransport> transport;
#ifdef __EMSCRIPTEN__
	transport = net::createWebClientTransport();
#else
	transport = net::createENetTransport();
#endif
	if (!transport) {
		error = "no client transport on this platform";
		AbortOpen();
		return false;
	}
	m_clientTransport = WrapSim(std::move(transport));

	net::ClientConfig config;
	config.gameId = m_gameId;
	config.gameVersion = m_gameVersion;
	config.playerName = m_playerName;
	config.sceneHash = m_sceneHash;
	m_client.reset(new net::ClientSession(*m_clientTransport, config));

	net::ReplicaClientConfig rc;
	rc.schema = [this](net::NetId id, const std::string &prototype) { return SchemaFor(id, prototype); };
	/* Predicted objects owned by this client are moved by ClientPredict(), not by the snapshots. */
	rc.skipOwned = true;
	rc.skipFilter = [this](net::NetId id) {
		const Entry *entry = FindEntry(id);
		return entry && entry->predicted;
	};
	m_replica.reset(new net::ReplicaClient(*m_client, *this, rc));
	m_rpcClient.reset(new net::RpcClient(*m_client, m_rpcTable, [this](net::NetId id, net::ClientId &owner) {
		const Entry *entry = FindEntry(id);
		if (!entry) {
			return false;
		}
		owner = entry->owner;
		return true;
	}));

	if (!m_client->connect(host, uint16_t(port), net::steadyClockMs())) {
		error = "could not connect to " + host + ":" + std::to_string(port);
		AbortOpen();
		return false;
	}

	/* Replicated objects are driven by the server from now on. */
	for (auto &pair : m_entries) {
		SuspendForClient(pair.second);
	}
	m_role = Role::CLIENT;
	CM_Message("network: connecting to " << host << ":" << port << " as '" << m_playerName << "'");
	return true;
}

bool KX_NetworkManager::StartFromScene(KX_Scene *scene)
{
	Scene *bscene = scene ? scene->GetBlenderScene() : nullptr;
	if (!bscene || bscene->gm.network.mode == NET_MODE_OFFLINE) {
		return false;
	}
	const SceneSettings settings = ReadSceneSettings(scene);
	std::string error;
	bool ok = false;
	switch (bscene->gm.network.mode) {
		case NET_MODE_HOST:
		case NET_MODE_DEDICATED: {
			HostOptions options;
			options.dedicated = (bscene->gm.network.mode == NET_MODE_DEDICATED);
			ok = Host(options, error, scene);
			break;
		}
		case NET_MODE_CLIENT: {
			/* "host", "host:port" or "[v6]:port" */
			std::string host = settings.address;
			int port = 0;
			if (!host.empty() && host[0] == '[') {
				const size_t close = host.find(']');
				if (close != std::string::npos) {
					if (close + 1 < host.size() && host[close + 1] == ':') {
						port = atoi(host.c_str() + close + 2);
					}
					host = host.substr(1, close - 1);
				}
			}
			else {
				const size_t colon = host.find(':');
				if (colon != std::string::npos && host.find(':', colon + 1) == std::string::npos) {
					port = atoi(host.c_str() + colon + 1);
					host = host.substr(0, colon);
				}
			}
			ok = Join(host, port, error, scene);
			break;
		}
		default:
			return false;
	}
	if (!ok) {
		CM_Error("network: " << error);
	}
	return ok;
}

void KX_NetworkManager::SuspendForClient(Entry &entry)
{
	if (!entry.obj || entry.dynamicsSuspended) {
		return;
	}
	PHY_IPhysicsController *physics = entry.obj->GetPhysicsController();
	if (physics && physics->IsDynamic() && !physics->IsDynamicsSuspended()) {
		/* The server simulates it; here it is moved by the snapshots only. Not a ghost: it still collides. */
		physics->SuspendDynamics(false);
		entry.dynamicsSuspended = true;
	}
}

void KX_NetworkManager::RestoreFromClient(Entry &entry)
{
	if (!entry.obj || !entry.dynamicsSuspended) {
		return;
	}
	if (PHY_IPhysicsController *physics = entry.obj->GetPhysicsController()) {
		physics->RestoreDynamics();
	}
	entry.dynamicsSuspended = false;
}

void KX_NetworkManager::ReleaseEntries(bool all)
{
	/* Scene objects keep their registration between sessions (a script calls replicate() once at start and
	 * the player may host, leave and join again); what the session created or changed is undone. */
	for (auto it = m_entries.begin(); it != m_entries.end();) {
		Entry &entry = it->second;
		if (m_role == Role::CLIENT) {
			RestoreFromClient(entry);
		}
		if (all || entry.spawned) {
			if (entry.obj) {
				entry.obj->SetNetId(0);
			}
			it = m_entries.erase(it);
		}
		else {
			entry.owner = net::kServerClientId;
			++it;
		}
	}
	m_protoSchemas.clear();
	m_protoPropNames.clear();
}

void KX_NetworkManager::CloseSession(bool sendQuit, bool shutdown)
{
	if (m_role == Role::NONE && !m_sessionOpen) {
		return;
	}
	if (m_role == Role::SERVER) {
		if (m_server && sendQuit) {
			m_server->stop();
		}
		m_rpcServer.reset();
		m_predServer.reset();
		m_lagComp.reset();
		m_replicator.reset();
		m_server.reset();
		m_serverTransport.reset();
		m_lanResponder.stop();
		m_lanActive = false;
	}
	else if (m_role == Role::CLIENT) {
		if (m_client && sendQuit) {
			m_client->disconnect();
		}
		/* Objects the server spawned die with the connection. */
		if (m_scene) {
			for (auto &pair : m_entries) {
				if (pair.second.spawned && pair.second.obj) {
					m_scene->DelayedRemoveObject(pair.second.obj);
					pair.second.obj = nullptr;
				}
			}
		}
		m_rpcClient.reset();
		m_replica.reset();
		m_client.reset();
		m_clientTransport.reset();
		m_clock.reset();
	}
	for (auto &pair : m_entries) {
		ResetPrediction(pair.second);
	}
	m_inputLog.reset();
	m_predTick = net::kNoTick;
	m_view = ViewTime();
	m_inputView = ViewTime();
	m_appliedInput.clear();
	m_clientView.clear();

	if (m_sessionOpen) {
		m_engine->SetUseFixedTimestep(m_prevFixedTimestep);
		if (m_role == Role::SERVER) {
			m_engine->SetTicRate(m_prevTicRate);
		}
		else if (m_role == Role::CLIENT) {
			m_adoptingTickRate = true;
			m_engine->SetTicRate(m_prevTicRate);
			m_adoptingTickRate = false;
		}
	}
	ReleaseEntries(shutdown);
	m_role = Role::NONE;
	m_sessionOpen = false;
	m_scene = nullptr;
	m_tick = net::kNoTick;
	m_dedicated = false;
}

void KX_NetworkManager::Disconnect()
{
	const bool wasActive = IsActive();
	const Role role = m_role;
	CloseSession(true);
	if (wasActive && role == Role::CLIENT) {
		Event event;
		event.type = Event::DISCONNECT;
		event.reason = int(net::DisconnectReason::Quit);
		Emit(event);
	}
}

void KX_NetworkManager::Shutdown()
{
	m_eventSink = nullptr;
	CloseSession(true, true);
	ReleaseEntries(true);
	m_lanResponder.stop();
	m_discovery.stop();
	m_discoveryStarted = false;
}

void KX_NetworkManager::OnObjectRemoved(KX_GameObject *obj)
{
	const net::NetId id = obj->GetNetId();
	if (id == net::kInvalidNetId) {
		return;
	}
	Entry *entry = FindEntry(id);
	if (entry && entry->obj == obj) {
		if (m_role == Role::SERVER && m_replicator && !m_applyingRemote) {
			m_replicator->despawn(id);
		}
		m_entries.erase(id);
	}
	obj->SetNetId(0);
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Spawn, ownership
 * \{ */

KX_GameObject *KX_NetworkManager::Spawn(const std::string &prototype, net::ClientId owner, const float *position,
                                        const float *orientation, std::string &error)
{
	if (m_role != Role::SERVER || !m_replicator) {
		error = "only the server can spawn (host first)";
		return nullptr;
	}
	if (owner != net::kServerClientId && !m_server->client(owner)) {
		error = "unknown client " + std::to_string(owner);
		return nullptr;
	}
	KX_GameObject *obj = CreateReplica(prototype, error);
	if (!obj) {
		return nullptr;
	}
	if (position) {
		obj->NodeSetLocalPosition(mt::vec3(position[0], position[1], position[2]));
	}
	if (orientation) {
		obj->NodeSetLocalOrientation(FromQuat(orientation));
	}
	obj->NodeUpdate();

	Entry entry;
	entry.obj = obj;
	entry.prototype = prototype;
	entry.spawned = true;
	entry.owner = owner;
	KX_GameObject *proto = m_scene->GetInactiveList()->FindValue(prototype);
	if (Object *ob = proto ? proto->GetBlenderObject() : nullptr) {
		const int flags = ob->net.flags;
		const bool configured = (flags & NET_OBJ_REPLICATE) != 0;
		entry.desc.syncTransform = configured ? (flags & NET_OBJ_SYNC_TRANSFORM) != 0 : true;
		entry.desc.syncVelocity = configured && (flags & NET_OBJ_SYNC_VELOCITY);
		entry.desc.syncAngularVelocity = configured && (flags & NET_OBJ_SYNC_ANGULAR);
		entry.desc.alwaysRelevant = configured && (flags & NET_OBJ_ALWAYS_RELEVANT);
		entry.desc.priority = (configured && ob->net.priority > 0.0f) ? ob->net.priority : 1.0f;
	}
	entry.propNames = m_protoPropNames[prototype];
	entry.schema = m_protoSchemas[prototype];
	entry.desc.props = entry.schema;
	entry.desc.owner = owner;
	entry.desc.prototype = prototype;

	const net::NetId id = m_replicator->spawn(entry.desc);
	if (id == net::kInvalidNetId) {
		error = "could not allocate a net id (prototype name longer than 255 bytes?)";
		m_scene->DelayedRemoveObject(obj);
		return nullptr;
	}
	obj->SetNetId(id);
	m_entries[id] = std::move(entry);
	return obj;
}

bool KX_NetworkManager::Despawn(KX_GameObject *obj)
{
	const net::NetId id = obj ? obj->GetNetId() : net::kInvalidNetId;
	Entry *entry = FindEntry(id);
	if (!entry || m_role != Role::SERVER) {
		return false;
	}
	/* OnObjectRemoved() tells the replicator when the scene really removes it. */
	m_scene->DelayedRemoveObject(obj);
	return true;
}

bool KX_NetworkManager::SetOwner(KX_GameObject *obj, net::ClientId owner)
{
	const net::NetId id = obj ? obj->GetNetId() : net::kInvalidNetId;
	Entry *entry = FindEntry(id);
	if (!entry || m_role != Role::SERVER || !m_replicator) {
		return false;
	}
	if (owner != net::kServerClientId && !m_server->client(owner)) {
		return false;
	}
	if (!m_replicator->setOwner(id, owner)) {
		return false;
	}
	entry->owner = owner;
	return true;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Ticks
 * \{ */

void KX_NetworkManager::BeginTick()
{
	const uint64_t now = net::steadyClockMs();
	if (m_role == Role::SERVER) {
		ServerTickBegin(now);
	}
	else if (m_role == Role::CLIENT) {
		ClientTickBegin(now);
	}
}

void KX_NetworkManager::EndTick()
{
	if (m_role != Role::SERVER || !m_replicator) {
		return;
	}
	const uint64_t now = net::steadyClockMs();
	RecordHitboxes();
	m_replicator->update(m_tick, now);
	if (m_lanActive) {
		UpdateLanInfo();
		m_lanResponder.update(now);
	}
}

void KX_NetworkManager::UpdateLanInfo()
{
	net::LanServerInfo info;
	info.gameId = m_gameId;
	info.gameVersion = m_gameVersion;
	info.name = m_roomName;
	info.sceneName = m_sceneName;
	info.players = uint16_t(m_server ? m_server->clients().size() + (m_dedicated ? 0 : 1) : 0);
	info.maxPlayers = uint16_t(m_maxPlayers);
	info.enetPort = m_serverTransport ? m_serverTransport->localPort() : 0;
	info.webSocketPort = 0;
	info.password = false;
	m_lanResponder.setInfo(info);
}

void KX_NetworkManager::ServerTickBegin(uint64_t now)
{
	++m_tick;
	std::vector<net::SessionEvent> events;
	m_server->update(now, m_tick, events);
	for (size_t i = 0; i < events.size(); ++i) {
		/* handleEvent() can append (an RPC violation closes a connection): index, never iterators. */
		const net::SessionEvent event = events[i];
		HandleServerEvent(event, now, events);
	}
	if (m_role == Role::SERVER) {
		ServerStepPredicted();
	}
}

void KX_NetworkManager::HandleServerEvent(const net::SessionEvent &event, uint64_t now,
                                          std::vector<net::SessionEvent> &events)
{
	m_replicator->handleEvent(event);
	if (m_predServer->handleEvent(event, m_tick)) {
		const net::InputQueue *queue = m_predServer->queue(event.client);
		if (queue && queue->stats().invalid > m_inputInvalid[event.client]) {
			m_inputInvalid[event.client] = queue->stats().invalid;
			m_server->reportViolation(event.client, now, events);
		}
		return;
	}
	if (m_rpcServer->handleEvent(event, now, events)) {
		return;
	}

	switch (event.type) {
		case net::SessionEvent::Type::ClientJoined: {
			if (!m_dedicated) {
				/* The session announces clients to each other but not the server itself: the host is client 0
				 * and shows up in the lobby of the new player with its name. */
				net::ClientInfoMsg host;
				host.clientId = net::kServerClientId;
				host.name = m_playerName;
				host.flags = net::CLIENT_CONNECTED | net::CLIENT_READY;
				m_server->send(event.client, net::Channel::Control, net::makePacket(host));
			}
			Event e;
			e.type = Event::PLAYER_JOIN;
			e.client = event.client;
			e.text = event.text;
			Emit(e);
			break;
		}
		case net::SessionEvent::Type::ClientExpired: {
			/* The replicator already forgot the objects the client had spawned (despawnOnExpire): remove them
			 * from the game too. */
			for (auto &pair : m_entries) {
				if (pair.second.spawned && pair.second.owner == event.client && pair.second.obj && m_scene) {
					m_scene->DelayedRemoveObject(pair.second.obj);
				}
			}
			break;
		}
		case net::SessionEvent::Type::ClientLeft: {
			m_ready.erase(event.client);
			m_appliedInput.erase(event.client);
			m_clientView.erase(event.client);
			m_inputInvalid.erase(event.client);
			Event e;
			e.type = Event::PLAYER_LEAVE;
			e.client = event.client;
			e.reason = int(event.disconnectReason);
			Emit(e);
			break;
		}
		case net::SessionEvent::Type::Message: {
			if (event.messageType != uint8_t(net::MessageType::Chat)) {
				break;
			}
			net::RawMessage raw;
			raw.type = event.messageType;
			raw.body = event.body.data();
			raw.size = event.body.size();
			net::ChatMsg chat;
			if (!net::decodeMessage(raw, chat) || chat.text.empty()) {
				break;
			}
			chat.fromClient = event.client;  // never trust the sender field
			m_server->broadcast(net::Channel::Rpc, net::makePacket(chat), 0, false);
			Event e;
			e.type = Event::CHAT;
			e.client = event.client;
			e.text = chat.text;
			Emit(e);
			break;
		}
		default:
			break;
	}
}

void KX_NetworkManager::ClientTickBegin(uint64_t now)
{
	++m_tick;
	std::vector<net::SessionEvent> events;
	m_client->update(now, events);
	for (const net::SessionEvent &event : events) {
		if (m_role != Role::CLIENT) {
			break;  // a handler disconnected
		}
		HandleClientEvent(event, now);
	}
	if (m_role != Role::CLIENT || !m_client) {
		return;
	}

	if (m_clock) {
		const net::ClientSession::PongSample &pong = m_client->lastPong();
		if (pong.count != m_pongCount) {
			m_pongCount = pong.count;
			m_clock->addPong(pong.rttMs, pong.serverTick, now);
		}
		const net::Tick newest = m_replica->lastAcceptedTick();
		if (newest != net::kNoTick && newest != m_lastClockSnapshot) {
			m_lastClockSnapshot = newest;
			m_clock->addSnapshot(newest, now);
		}
		/* Before the remote objects move: the input goes out with the view time the player has been seeing. */
		ClientPredict(now);
		net::Tick renderTick;
		float alpha;
		m_clock->renderTime(now, renderTick, alpha);
		if (m_clock->synced() && m_replica->applyInterpolated(renderTick, alpha)) {
			m_view.tick = renderTick;
			m_view.alpha = alpha;
			/* Past the newest snapshot the buffer holds it (no extrapolation): the view time is that snapshot,
			 * or the server would rewind the shots to a moment ahead of what was drawn. */
			const net::Snapshot *newest = m_replica->buffer().newest();
			if (newest && !net::tickNewer(newest->tick, renderTick)) {
				m_view.tick = newest->tick;
				m_view.alpha = 0.0f;
			}
		}
		else if (m_replica->applyLatest()) {
			m_view.tick = m_replica->lastAcceptedTick();
			m_view.alpha = 0.0f;
		}
	}
}

void KX_NetworkManager::HandleClientEvent(const net::SessionEvent &event, uint64_t now)
{
	m_applyingRemote = true;
	m_replica->handleEvent(event, now);
	const bool isRpc = m_rpcClient->handleEvent(event);
	m_applyingRemote = false;
	if (isRpc) {
		return;
	}

	switch (event.type) {
		case net::SessionEvent::Type::Connected: {
			m_adoptingTickRate = true;
			m_engine->SetTicRate(double(m_client->tickRate()));
			m_adoptingTickRate = false;
			net::ClockConfig clock;
			clock.tickRate = m_client->tickRate();
			clock.snapshotRate = m_client->snapshotRate();
			m_clock.reset(new net::NetClock(clock));
			m_maxPlayers = 0;
			m_connectedEmitted = true;
			CM_Message("network: connected as client " << m_client->clientId() << ", server tick "
			           << m_client->tickRate() << " Hz");
			Event e;
			e.type = Event::CONNECT;
			e.client = m_client->clientId();
			Emit(e);
			break;
		}
		case net::SessionEvent::Type::Rejected: {
			Event e;
			e.type = Event::REJECT;
			e.reason = int(event.rejectReason);
			e.text = event.text;
			CM_Warning("network: refused by the server (reason " << e.reason << "): " << e.text);
			CloseSession(false);
			Emit(e);
			break;
		}
		case net::SessionEvent::Type::Disconnected: {
			Event e;
			e.type = Event::DISCONNECT;
			e.reason = int(event.disconnectReason);
			e.text = event.text;
			CM_Warning("network: disconnected (reason " << e.reason << ")");
			CloseSession(false);
			Emit(e);
			break;
		}
		case net::SessionEvent::Type::SceneChange: {
			if (event.sceneHash != m_sceneHash) {
				/* The handshake already compared the hash, so this only happens when the server changes
				 * scene during a match, which this version does not follow. */
				CM_Warning("network: the server moved to scene '" << event.text
				           << "'; scene changes during a match are not supported yet");
			}
			m_client->sceneLoaded(m_sceneHash);
			break;
		}
		case net::SessionEvent::Type::Message: {
			if (event.messageType != uint8_t(net::MessageType::Chat)) {
				break;
			}
			net::RawMessage raw;
			raw.type = event.messageType;
			raw.body = event.body.data();
			raw.size = event.body.size();
			net::ChatMsg chat;
			if (net::decodeMessage(raw, chat)) {
				Event e;
				e.type = Event::CHAT;
				e.client = chat.fromClient;
				e.text = chat.text;
				Emit(e);
			}
			break;
		}
		default:
			break;
	}
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Input, client prediction and lag compensation
 * \{ */

void KX_NetworkManager::SetStepSink(const StepFunc &sink)
{
	m_stepSink = sink;
}

bool KX_NetworkManager::SetPredicted(KX_GameObject *obj, bool predicted)
{
	Entry *entry = obj ? FindEntry(obj->GetNetId()) : nullptr;
	if (!entry || entry->obj != obj) {
		return false;
	}
	if (!predicted) {
		ResetPrediction(*entry);
	}
	entry->predicted = predicted;
	return true;
}

bool KX_NetworkManager::SetInput(const net::InputBlock &input)
{
	if (input.size() > kMaxUserInputBytes) {
		return false;
	}
	m_input = input;
	m_inputSet = true;
	/* The input goes out with the view the player had when the game made it (what is on screen now), in every
	 * tick it is repeated: a block that reaches the server late still leaves the next ones with the same time. */
	m_inputView = m_view;
	return true;
}

bool KX_NetworkManager::GetClientInput(net::ClientId client, net::InputBlock &input) const
{
	if (m_role == Role::CLIENT) {
		if (!m_client || client != m_client->clientId() || !m_inputSet) {
			return false;
		}
		input = m_input;
		return true;
	}
	const auto it = m_appliedInput.find(client);
	if (it == m_appliedInput.end()) {
		return false;
	}
	input = it->second;
	return true;
}

bool KX_NetworkManager::GetViewTime(net::ClientId client, net::Tick &tick, float &alpha) const
{
	ViewTime view;
	if (m_role == Role::CLIENT) {
		view = m_view;
	}
	else if (m_role == Role::SERVER) {
		const auto it = m_clientView.find(client);
		if (it != m_clientView.end()) {
			view = it->second;
		}
	}
	tick = view.tick;
	alpha = view.alpha;
	return view.tick != net::kNoTick;
}

bool KX_NetworkManager::GetPredictionStats(KX_GameObject *obj, net::PredictionStats &stats, PredictionInfo *info) const
{
	const Entry *entry = obj ? FindEntry(obj->GetNetId()) : nullptr;
	if (!entry || !entry->prediction) {
		return false;
	}
	stats = entry->prediction->stats();
	if (info) {
		info->tick = entry->prediction->newestTick();
		info->snapshotTick = entry->lastReconciled;
		info->resyncs = m_predResyncs;
	}
	return true;
}

bool KX_NetworkManager::SetHitbox(KX_GameObject *obj, float radius, float halfHeight)
{
	Entry *entry = obj ? FindEntry(obj->GetNetId()) : nullptr;
	if (!entry || entry->obj != obj) {
		return false;
	}
	if (!(radius > 0.0f)) {
		entry->hasHitbox = false;
		return true;
	}
	entry->hasHitbox = true;
	entry->hitbox = net::Hitbox();
	entry->hitbox.shape = halfHeight > 0.0f ? net::HitShape::Capsule : net::HitShape::Sphere;
	entry->hitbox.radius = radius;
	entry->hitbox.halfHeight = std::max(halfHeight, 0.0f);
	return true;
}

bool KX_NetworkManager::RaycastPast(const float origin[3], const float direction[3], float maxDistance, int viewOf,
                                    KX_GameObject *ignore, KX_GameObject *&hitObj, float point[3], float &distance,
                                    int maxRewindMs, net::Tick *usedTick) const
{
	hitObj = nullptr;
	if (m_role != Role::SERVER || !m_lagComp) {
		return false;
	}
	const float len = std::sqrt(direction[0] * direction[0] + direction[1] * direction[1] +
	                            direction[2] * direction[2]);
	if (!(len > 1e-6f)) {
		return false;
	}
	const float dir[3] = {direction[0] / len, direction[1] / len, direction[2] / len};
	/* The newest recorded tick is the present: the current one is recorded at the end of the step. */
	net::Tick tick = m_lagComp->newestTick();
	float alpha = 0.0f;
	if (viewOf >= 0) {
		const auto it = m_clientView.find(net::ClientId(viewOf));
		if (it != m_clientView.end() && it->second.tick != net::kNoTick) {
			tick = it->second.tick;
			alpha = it->second.alpha;
		}
	}
	/* Anti-abuse: a client cannot ask for a time older than the server allows (the history keeps 1 s). */
	const int32_t maxTicks = int32_t(std::max(0, maxRewindMs) * m_lagCompTickRate / 1000);
	if (int32_t(m_tick - tick) > maxTicks) {
		tick = m_tick - net::Tick(maxTicks);
		alpha = 0.0f;
	}
	net::RayHit hit;
	const net::NetId ignoreId = ignore ? ignore->GetNetId() : net::kInvalidNetId;
	if (!m_lagComp->raycast(origin, dir, maxDistance, tick, alpha, m_tick, hit, ignoreId)) {
		return false;
	}
	const Entry *entry = FindEntry(hit.id);
	if (!entry || !entry->obj) {
		return false;
	}
	hitObj = entry->obj;
	std::copy(hit.point, hit.point + 3, point);
	distance = hit.distance;
	if (usedTick) {
		*usedTick = hit.tick;
	}
	return true;
}

void KX_NetworkManager::ServerStepPredicted()
{
	m_appliedInput.clear();
	for (const net::ClientId client : m_server->clients()) {
		net::InputBlock block;
		if (!m_predServer->consume(client, m_tick, block)) {
			continue;
		}
		ViewTime view;
		net::InputBlock user;
		if (!ReadView(block, view.tick, view.alpha, user)) {
			continue;
		}
		if (view.tick != net::kNoTick) {
			m_clientView[client] = view;
		}
		m_appliedInput[client] = std::move(user);
	}
	if (!m_dedicated && m_inputSet) {
		m_appliedInput[net::kServerClientId] = m_input;
	}
	if (!m_stepSink) {
		return;
	}
	/* The step runs game code that may remove objects: collect first, look up again before each call. */
	std::vector<net::NetId> ids;
	for (const auto &pair : m_entries) {
		if (pair.second.predicted && pair.second.obj) {
			ids.push_back(pair.first);
		}
	}
	for (const net::NetId id : ids) {
		const Entry *entry = FindEntry(id);
		if (!entry || !entry->obj) {
			continue;
		}
		const auto input = m_appliedInput.find(entry->owner);
		if (input != m_appliedInput.end()) {
			m_stepSink(entry->obj, input->second);
		}
	}
}

void KX_NetworkManager::RecordHitboxes()
{
	if (!m_lagComp) {
		return;
	}
	std::vector<net::Hitbox> boxes;
	for (const auto &pair : m_entries) {
		const Entry &entry = pair.second;
		if (!entry.hasHitbox || !entry.obj) {
			continue;
		}
		net::Hitbox box = entry.hitbox;
		box.id = pair.first;
		const mt::vec3 &pos = entry.obj->NodeGetWorldPosition();
		box.center[0] = pos.x;
		box.center[1] = pos.y;
		box.center[2] = pos.z;
		ToQuat(entry.obj->NodeGetWorldOrientation(), box.rotation);
		boxes.push_back(box);
	}
	m_lagComp->record(m_tick, boxes);
}

bool KX_NetworkManager::PredictedState(const Entry &entry, net::ObjectState &state) const
{
	if (!entry.obj) {
		return false;
	}
	state = net::ObjectState();
	state.id = entry.obj->GetNetId();
	state.hasTransform = true;
	const mt::vec3 &pos = entry.obj->NodeGetWorldPosition();
	state.position[0] = pos.x;
	state.position[1] = pos.y;
	state.position[2] = pos.z;
	ToQuat(entry.obj->NodeGetWorldOrientation(), state.rotation);
	return true;
}

void KX_NetworkManager::SetPredictedState(Entry &entry, const net::ObjectState &state)
{
	if (!entry.obj || !state.hasTransform) {
		return;
	}
	entry.obj->NodeSetWorldPosition(mt::vec3(state.position[0], state.position[1], state.position[2]));
	entry.obj->NodeSetGlobalOrientation(FromQuat(state.rotation));
	/* The setters only change the local transform: without this the replay reads the old world position. */
	entry.obj->NodeUpdate();
}

void KX_NetworkManager::ApplyOffset(Entry &entry, const float offset[3])
{
	if (!entry.obj) {
		return;
	}
	const float delta[3] = {offset[0] - entry.shownOffset[0], offset[1] - entry.shownOffset[1],
	                        offset[2] - entry.shownOffset[2]};
	if (delta[0] != 0.0f || delta[1] != 0.0f || delta[2] != 0.0f) {
		const mt::vec3 &pos = entry.obj->NodeGetWorldPosition();
		entry.obj->NodeSetWorldPosition(mt::vec3(pos.x + delta[0], pos.y + delta[1], pos.z + delta[2]));
		entry.obj->NodeUpdate();
	}
	std::copy(offset, offset + 3, entry.shownOffset);
}

void KX_NetworkManager::ResetPrediction(Entry &entry)
{
	const float zero[3] = {0.0f, 0.0f, 0.0f};
	ApplyOffset(entry, zero);
	std::copy(zero, zero + 3, entry.shownOffset);
	entry.prediction.reset();
	entry.lastReconciled = net::kNoTick;
}

void KX_NetworkManager::ClientPredict(uint64_t now)
{
	const net::ClientId self = m_client->clientId();
	std::vector<net::NetId> ids;
	for (auto &pair : m_entries) {
		Entry &entry = pair.second;
		if (entry.predicted && entry.obj && self != net::kServerClientId && entry.owner == self) {
			ids.push_back(pair.first);
		}
		else if (entry.prediction) {
			ResetPrediction(entry);
		}
	}
	if ((ids.empty() && !m_inputSet) || !m_clock->synced() || !IsConnected()) {
		return;
	}

	/* Ticks grow by one. The clock's estimate moves in steps (several ticks run back to back in a slow frame,
	 * then none), so only a drift of half a second (stall, clock resync) restarts the timeline: that drops the
	 * input history, and the corrections wait until it covers the snapshots again. */
	const net::Tick target = m_clock->predictionTick(now);
	net::Tick tick = m_predTick == net::kNoTick ? target : m_predTick + 1;
	const int32_t drift = int32_t(target - tick);
	const int32_t maxDrift = std::max(8, int(m_client->tickRate()) / 2);
	if (drift > maxDrift || drift < -maxDrift) {
		tick = target;
		++m_predResyncs;
	}
	m_predTick = tick;

	net::InputBlock block;
	const ViewTime &view = m_inputSet ? m_inputView : m_view;
	WriteView(block, view.tick, view.alpha);
	block.insert(block.end(), m_input.begin(), m_input.end());
	if (!m_inputLog) {
		m_inputLog.reset(new net::PredictionClient(net::PredictionCallbacks()));
	}
	net::InputMsg msg;
	if (m_inputLog->recordInput(tick, block, msg)) {
		m_client->send(net::Channel::Input, net::makePacket(msg));
	}
	if (!m_stepSink) {
		return;
	}

	const net::Snapshot *snapshot = m_replica->buffer().newest();
	const float tickMs = 1000.0f / float(std::max<int>(1, m_client->tickRate()));
	for (const net::NetId id : ids) {
		Entry *entry = FindEntry(id);
		if (!entry || !entry->obj) {
			continue;
		}
		const float zero[3] = {0.0f, 0.0f, 0.0f};
		ApplyOffset(*entry, zero);  // back to the simulated position
		if (!entry->prediction) {
			net::PredictionCallbacks callbacks;
			callbacks.setState = [this, id](const net::ObjectState &state) {
				if (Entry *e = FindEntry(id)) {
					SetPredictedState(*e, state);
				}
			};
			callbacks.getState = [this, id](net::ObjectState &state) {
				const Entry *e = FindEntry(id);
				return e && PredictedState(*e, state);
			};
			callbacks.replay = [this, id](net::Tick, const net::InputBlock &input) {
				Entry *e = FindEntry(id);
				ViewTime view;
				net::InputBlock user;
				if (e && e->obj && m_stepSink && ReadView(input, view.tick, view.alpha, user)) {
					m_stepSink(e->obj, user);
				}
			};
			entry->prediction.reset(new net::PredictionClient(callbacks));
		}
		if (snapshot && snapshot->tick != entry->lastReconciled) {
			entry->lastReconciled = snapshot->tick;
			const net::ObjectState *server = snapshot->find(id);
			if (server && server->hasTransform) {
				/* Only the transform is predicted: velocities of a suspended body read as zero here. */
				net::ObjectState state = *server;
				state.hasVelocity = false;
				state.hasAngularVelocity = false;
				entry->prediction->reconcile(snapshot->tick, state);
			}
		}
		entry = FindEntry(id);
		if (!entry || !entry->obj || !entry->prediction) {
			continue;
		}
		net::InputMsg unused;
		entry->prediction->recordInput(tick, block, unused);
		m_stepSink(entry->obj, m_input);
		entry = FindEntry(id);
		if (!entry || !entry->obj || !entry->prediction) {
			continue;
		}
		net::ObjectState state;
		if (PredictedState(*entry, state)) {
			entry->prediction->recordState(tick, state);
		}
		entry->prediction->update(tickMs);
		float offset[3];
		entry->prediction->visualOffset(offset);
		ApplyOffset(*entry, offset);
	}
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Lobby, LAN
 * \{ */

void KX_NetworkManager::SetReady(bool ready)
{
	if (m_role == Role::SERVER) {
		m_hostReady = ready;
		return;
	}
	if (m_role != Role::CLIENT || !m_rpcClient) {
		return;
	}
	net::RpcArg arg;
	arg.type = net::RpcArgType::Bool;
	arg.b = ready;
	m_rpcClient->call("net.ready", net::kInvalidNetId, {arg});
}

bool KX_NetworkManager::SendChat(const std::string &text)
{
	if (!IsConnected() || text.empty() || text.size() > net::kMaxChatBytes) {
		return false;
	}
	net::ChatMsg chat;
	chat.text = text;
	if (m_role == Role::SERVER) {
		chat.fromClient = net::kServerClientId;
		m_server->broadcast(net::Channel::Rpc, net::makePacket(chat), 0, false);
		Event e;
		e.type = Event::CHAT;
		e.client = 0;
		e.text = text;
		Emit(e);
		return true;
	}
	return m_client->send(net::Channel::Rpc, net::makePacket(chat));
}

bool KX_NetworkManager::StartGame()
{
	if (m_role != Role::SERVER || !m_server) {
		return false;
	}
	for (net::ClientId client : m_server->clients()) {
		const auto it = m_ready.find(client);
		if (it == m_ready.end() || !it->second) {
			return false;
		}
	}
	m_gameStarted = true;
	m_server->setGameStarted(true);
	const int id = m_rpcTable.idOf("net.start");
	for (net::ClientId client : m_server->clients()) {
		m_rpcServer->callClient(client, uint16_t(id), net::kInvalidNetId, {});
	}
	Event e;
	e.type = Event::START;
	Emit(e);
	return true;
}

std::vector<KX_NetworkManager::PlayerInfo> KX_NetworkManager::GetPlayers() const
{
	std::vector<PlayerInfo> players;
	if (m_role == Role::SERVER && m_server) {
		if (!m_dedicated) {
			PlayerInfo host;
			host.id = 0;
			host.name = m_playerName;
			host.ready = m_hostReady;
			host.isHost = true;
			players.push_back(host);
		}
		for (net::ClientId id : m_server->clients()) {
			const net::ServerSession::ClientState *state = m_server->client(id);
			if (!state) {
				continue;
			}
			PlayerInfo info;
			info.id = id;
			info.name = state->name;
			info.ping = state->rtt.hasSample() ? int(std::lround(state->rtt.rttMs())) : 0;
			const auto it = m_ready.find(id);
			info.ready = it != m_ready.end() && it->second;
			players.push_back(info);
		}
	}
	else if (m_role == Role::CLIENT && m_client) {
		/* The server sends no entry for itself: it is client 0 by definition (the host, unless dedicated). */
		for (const auto &pair : m_client->players()) {
			PlayerInfo info;
			info.id = pair.first;
			info.name = pair.second.name;
			const auto it = m_remoteReady.find(pair.first);
			info.ready = it != m_remoteReady.end() && it->second;
			info.isHost = (pair.first == net::kServerClientId);
			if (pair.first == m_client->clientId()) {
				info.ping = int(std::lround(m_client->rttMs()));
			}
			players.push_back(info);
		}
	}
	return players;
}

const std::vector<net::LanServerEntry> &KX_NetworkManager::DiscoverLan()
{
	const uint64_t now = net::steadyClockMs();
	if (!m_discoveryStarted) {
		m_discoveryStarted = m_discovery.start();
		m_lastLanRequestMs = 0;
	}
	if (m_discoveryStarted) {
		if (m_lastLanRequestMs == 0 || now - m_lastLanRequestMs >= 1000) {
			m_discovery.request(GetGameId(), now);
			m_lastLanRequestMs = now;
		}
		m_discovery.update(now, 5000);
	}
	return m_discovery.servers();
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name net::IWorld
 * \{ */

bool KX_NetworkManager::getTransform(net::NetId id, float position[3], float rotation[4]) const
{
	const Entry *entry = FindEntry(id);
	if (!entry || !entry->obj) {
		return false;
	}
	const mt::vec3 &pos = entry->obj->NodeGetWorldPosition();
	position[0] = pos.x;
	position[1] = pos.y;
	position[2] = pos.z;
	ToQuat(entry->obj->NodeGetWorldOrientation(), rotation);
	return true;
}

bool KX_NetworkManager::getVelocity(net::NetId id, float linear[3], float angular[3]) const
{
	const Entry *entry = FindEntry(id);
	if (!entry || !entry->obj) {
		return false;
	}
	const mt::vec3 lin = entry->obj->GetLinearVelocity();
	const mt::vec3 ang = entry->obj->GetAngularVelocity();
	for (int i = 0; i < 3; ++i) {
		linear[i] = lin[i];
		angular[i] = ang[i];
	}
	return true;
}

bool KX_NetworkManager::getProperties(net::NetId id, std::vector<net::PropValue> &props) const
{
	const Entry *entry = FindEntry(id);
	if (!entry || !entry->obj) {
		return false;
	}
	props.clear();
	for (size_t i = 0; i < entry->propNames.size(); ++i) {
		const net::PropKind kind = entry->schema[i].kind;
		EXP_Value *value = entry->obj->GetProperty(entry->propNames[i]);
		if (!value) {
			props.push_back(DefaultValue(kind));
			continue;
		}
		const double number = value->GetNumber();
		switch (kind) {
			case net::PropKind::Bool:
				props.push_back(net::PropValue::makeBool(number != 0.0));
				break;
			case net::PropKind::Int:
				props.push_back(net::PropValue::makeInt(int64_t(number)));
				break;
			case net::PropKind::Float:
				props.push_back(net::PropValue::makeFloat(float(number)));
				break;
		}
	}
	return true;
}

bool KX_NetworkManager::isSleeping(net::NetId id) const
{
	const Entry *entry = FindEntry(id);
	if (!entry || !entry->obj) {
		return false;
	}
	/* Bullet's own "sleeping" flag is not exposed by PHY_IPhysicsController: a dynamic body that does not
	 * move at all is the same thing for the replicator (it keeps the last captured state). */
	PHY_IPhysicsController *physics = entry->obj->GetPhysicsController();
	if (!physics || !physics->IsDynamic() || physics->IsDynamicsSuspended()) {
		return false;
	}
	const float eps2 = 1e-8f;
	return entry->obj->GetLinearVelocity().LengthSquared() < eps2 &&
	       entry->obj->GetAngularVelocity().LengthSquared() < eps2;
}

void KX_NetworkManager::setTransform(net::NetId id, const float position[3], const float rotation[4])
{
	Entry *entry = FindEntry(id);
	if (!entry || !entry->obj) {
		return;
	}
	entry->obj->NodeSetWorldPosition(mt::vec3(position[0], position[1], position[2]));
	entry->obj->NodeSetGlobalOrientation(FromQuat(rotation));
	entry->obj->NodeUpdate();
}

void KX_NetworkManager::setVelocity(net::NetId id, const float linear[3], const float angular[3])
{
	Entry *entry = FindEntry(id);
	if (!entry || !entry->obj || entry->dynamicsSuspended) {
		return;  // moved by the snapshots only
	}
	entry->obj->SetLinearVelocity(mt::vec3(linear[0], linear[1], linear[2]), false);
	entry->obj->SetAngularVelocity(mt::vec3(angular[0], angular[1], angular[2]), false);
}

void KX_NetworkManager::setProperties(net::NetId id, const std::vector<net::PropValue> &props)
{
	Entry *entry = FindEntry(id);
	if (!entry || !entry->obj || props.size() != entry->propNames.size()) {
		return;
	}
	for (size_t i = 0; i < props.size(); ++i) {
		EXP_Value *value = nullptr;
		switch (entry->schema[i].kind) {
			case net::PropKind::Bool:
				value = new EXP_BoolValue(props[i].b);
				break;
			case net::PropKind::Int:
				value = new EXP_IntValue(props[i].i);
				break;
			case net::PropKind::Float:
				value = new EXP_FloatValue(props[i].f);
				break;
		}
		if (value) {
			entry->obj->SetProperty(entry->propNames[i], value);
			value->Release();
		}
	}
}

bool KX_NetworkManager::spawn(net::NetId id, const std::string &prototype, net::ClientId owner,
                              const net::ObjectState &state)
{
	std::string error;
	KX_GameObject *obj = CreateReplica(prototype, error);
	if (!obj) {
		CM_Warning("network: Spawn " << id << ": " << error);
		return false;
	}
	if (state.hasTransform) {
		obj->NodeSetLocalPosition(mt::vec3(state.position[0], state.position[1], state.position[2]));
		obj->NodeSetLocalOrientation(FromQuat(state.rotation));
	}
	obj->NodeUpdate();

	Entry entry;
	entry.obj = obj;
	entry.prototype = prototype;
	entry.spawned = true;
	entry.owner = owner;
	entry.propNames = m_protoPropNames[prototype];
	entry.schema = m_protoSchemas[prototype];
	obj->SetNetId(id);
	SuspendForClient(entry);
	m_entries[id] = std::move(entry);
	if (!state.props.empty()) {
		setProperties(id, state.props);
	}
	return true;
}

void KX_NetworkManager::despawn(net::NetId id)
{
	Entry *entry = FindEntry(id);
	if (!entry) {
		return;
	}
	KX_GameObject *obj = entry->obj;
	m_entries.erase(id);  // before the removal: OnObjectRemoved() then finds nothing to forget
	if (obj) {
		obj->SetNetId(0);
		if (m_scene) {
			m_scene->DelayedRemoveObject(obj);
		}
	}
}

void KX_NetworkManager::setOwner(net::NetId id, net::ClientId owner)
{
	if (Entry *entry = FindEntry(id)) {
		if (entry->owner != owner) {
			ResetPrediction(*entry);
		}
		entry->owner = owner;
	}
}

bool KX_NetworkManager::exists(net::NetId id) const
{
	const Entry *entry = FindEntry(id);
	return entry && entry->obj;
}

/** \} */
