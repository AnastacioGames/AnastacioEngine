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

/** \file gameengine/Ketsji/KX_PyNetwork.cpp
 *  \ingroup ketsji
 *
 * Range.network. Functions and events follow tools/net_menu/NOTES-D.md; the attributes (isServer,
 * isConnected, playerName, roomName, maxPlayers, clients) are properties of a module subclass created
 * at the end of initNetworkPythonBinding().
 */

#ifdef WITH_PYTHON

#include "KX_PyNetwork.h"

#include "KX_GameObject.h"
#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "KX_NetworkManager.h"
#include "KX_PyMath.h"
#include "KX_Scene.h"

#include "CM_Message.h"

#include <cstdlib>
#include <cstring>

namespace {

const char *kEventNames[] = {
	"on_connect", "on_disconnect", "on_reject", "on_chat", "on_start", "on_player_join", "on_player_leave",
};

KX_NetworkManager *Manager()
{
	KX_KetsjiEngine *engine = KX_GetActiveEngine();
	return engine ? engine->GetNetworkManager() : nullptr;
}

KX_NetworkManager *ManagerCreate();

/// Calls the callbacks registered for an event; their exceptions are printed and never reach the engine.
void DispatchEvent(const KX_NetworkManager::Event &event)
{
	PyObject *module = PyDict_GetItemString(PyImport_GetModuleDict(), "Range.network");  // borrowed
	if (!module) {
		return;
	}
	PyObject *table = PyObject_GetAttrString(module, "_callbacks");
	if (!table) {
		PyErr_Clear();
		return;
	}

	const char *name = nullptr;
	PyObject *args = nullptr;
	switch (event.type) {
		case KX_NetworkManager::Event::CONNECT:
			name = "on_connect";
			args = Py_BuildValue("(i)", event.client);
			break;
		case KX_NetworkManager::Event::DISCONNECT:
			name = "on_disconnect";
			args = Py_BuildValue("(is)", event.reason, event.text.c_str());
			break;
		case KX_NetworkManager::Event::REJECT:
			name = "on_reject";
			args = Py_BuildValue("(is)", event.reason, event.text.c_str());
			break;
		case KX_NetworkManager::Event::CHAT:
			name = "on_chat";
			args = Py_BuildValue("(is)", event.client, event.text.c_str());
			break;
		case KX_NetworkManager::Event::START:
			name = "on_start";
			args = PyTuple_New(0);
			break;
		case KX_NetworkManager::Event::PLAYER_JOIN:
			name = "on_player_join";
			args = Py_BuildValue("(is)", event.client, event.text.c_str());
			break;
		case KX_NetworkManager::Event::PLAYER_LEAVE:
			name = "on_player_leave";
			args = Py_BuildValue("(i)", event.client);
			break;
	}

	PyObject *list = name ? PyDict_GetItemString(table, name) : nullptr;  // borrowed
	if (list && args && PyList_Check(list)) {
		/* Callbacks may register or remove callbacks: walk a copy. */
		PyObject *copy = PyList_GetSlice(list, 0, PY_SSIZE_T_MAX);
		for (Py_ssize_t i = 0; copy && i < PyList_GET_SIZE(copy); ++i) {
			PyObject *result = PyObject_CallObject(PyList_GET_ITEM(copy, i), args);
			if (result) {
				Py_DECREF(result);
			}
			else {
				PyErr_Print();
			}
		}
		Py_XDECREF(copy);
	}
	Py_XDECREF(args);
	Py_DECREF(table);
}

KX_NetworkManager *ManagerCreate()
{
	KX_KetsjiEngine *engine = KX_GetActiveEngine();
	if (!engine) {
		PyErr_SetString(PyExc_RuntimeError, "Range.network: the game engine is not running");
		return nullptr;
	}
	KX_NetworkManager *manager = engine->GetOrCreateNetworkManager();
	manager->SetEventSink(DispatchEvent);
	return manager;
}

bool ObjectFromPy(PyObject *value, KX_GameObject **obj, const char *prefix)
{
	KX_Scene *scene = KX_GetActiveScene();
	if (!scene) {
		PyErr_Format(PyExc_RuntimeError, "%s: no active scene", prefix);
		return false;
	}
	return ConvertPythonToGameObject(scene->GetLogicManager(), value, obj, false, prefix);
}

/// "host", "host:port", "[v6]:port"; false for a room code (needs a lobby service, not in v1).
bool ParseAddress(const std::string &text, std::string &host, int &port)
{
	port = 0;
	host = text;
	if (host.empty()) {
		return false;
	}
	if (host[0] == '[') {
		const size_t close = host.find(']');
		if (close == std::string::npos) {
			return false;
		}
		if (close + 1 < host.size() && host[close + 1] == ':') {
			port = atoi(host.c_str() + close + 2);
		}
		host = host.substr(1, close - 1);
		return !host.empty();
	}
	const size_t colon = host.find(':');
	if (colon != std::string::npos && host.find(':', colon + 1) == std::string::npos) {
		port = atoi(host.c_str() + colon + 1);
		host = host.substr(0, colon);
	}
	/* A bare 4 to 8 character base 36 word is a room code. */
	if (host.find('.') == std::string::npos && host.find(':') == std::string::npos && host != "localhost" &&
	    host.size() >= 4 && host.size() <= 8) {
		bool code = true;
		for (const char c : host) {
			code = code && ((c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'));
		}
		if (code) {
			return false;
		}
	}
	return !host.empty();
}

/* -------------------------------------------------------------------- */
/** \name Functions
 * \{ */

PyObject *Net_host(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"port", "max_players", "room_name", "password", "dedicated", "websocket_port",
	                               nullptr};
	KX_NetworkManager::HostOptions options;
	const char *room = "";
	const char *password = "";
	int dedicated = 0;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|iissp" "i", const_cast<char **>(kwlist), &options.port,
	                                 &options.maxPlayers, &room, &password, &dedicated, &options.wsPort)) {
		return nullptr;
	}
	KX_NetworkManager *manager = ManagerCreate();
	if (!manager) {
		return nullptr;
	}
	if (password[0]) {
		/* The v1 Hello message has no password field (NOTES-D, doubt 2): do not pretend it protects. */
		CM_Warning("network: host(password=...) is not enforced by protocol v1, the room is open");
	}
	options.roomName = room;
	options.dedicated = dedicated != 0;
	std::string error;
	if (!manager->Host(options, error)) {
		CM_Warning("network: host failed: " << error);
		Py_RETURN_FALSE;
	}
	Py_RETURN_TRUE;
}

PyObject *Net_join(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"address", "password", nullptr};
	const char *address = nullptr;
	const char *password = "";
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|s", const_cast<char **>(kwlist), &address, &password)) {
		return nullptr;
	}
	KX_NetworkManager *manager = ManagerCreate();
	if (!manager) {
		return nullptr;
	}
	if (password[0]) {
		CM_Warning("network: join(password=...) is ignored, protocol v1 has no password");
	}
	std::string host;
	int port = 0;
	if (!ParseAddress(address, host, port)) {
		CM_Warning("network: '" << address << "' is not an address (host, host:port or [v6]:port); "
		           "room codes need a lobby service, which this version does not have");
		Py_RETURN_FALSE;
	}
	std::string error;
	if (!manager->Join(host, port, error)) {
		CM_Warning("network: join failed: " << error);
		Py_RETURN_FALSE;
	}
	Py_RETURN_TRUE;
}

PyObject *Net_disconnect(PyObject *, PyObject *)
{
	if (KX_NetworkManager *manager = Manager()) {
		manager->Disconnect();
	}
	Py_RETURN_NONE;
}

PyObject *Net_set_ready(PyObject *, PyObject *arg)
{
	const int ready = PyObject_IsTrue(arg);
	if (ready < 0) {
		return nullptr;
	}
	if (KX_NetworkManager *manager = Manager()) {
		manager->SetReady(ready != 0);
	}
	Py_RETURN_NONE;
}

PyObject *Net_send_chat(PyObject *, PyObject *arg)
{
	const char *text = PyUnicode_AsUTF8(arg);
	if (!text) {
		return nullptr;
	}
	KX_NetworkManager *manager = Manager();
	return PyBool_FromLong(manager && manager->SendChat(text));
}

PyObject *Net_start_game(PyObject *, PyObject *)
{
	KX_NetworkManager *manager = Manager();
	return PyBool_FromLong(manager && manager->StartGame());
}

PyObject *Net_discover_lan(PyObject *, PyObject *)
{
	KX_NetworkManager *manager = ManagerCreate();
	if (!manager) {
		return nullptr;
	}
	PyObject *list = PyList_New(0);
	for (const net::LanServerEntry &server : manager->DiscoverLan()) {
		PyObject *entry = Py_BuildValue("{s:s,s:s,s:i,s:i,s:i,s:i,s:i,s:O,s:s}",
		                                "name", server.info.name.c_str(),
		                                "address", server.address.c_str(),
		                                "port", int(server.info.enetPort),
		                                "ws_port", int(server.info.webSocketPort),
		                                "players", int(server.info.players),
		                                "max_players", int(server.info.maxPlayers),
		                                "ping", int(server.pingMs),
		                                "password", server.info.password ? Py_True : Py_False,
		                                "scene", server.info.sceneName.c_str());
		if (!entry) {
			Py_DECREF(list);
			return nullptr;
		}
		PyList_Append(list, entry);
		Py_DECREF(entry);
	}
	return list;
}

PyObject *Net_set_simulation(PyObject *, PyObject *args)
{
	float latency = 0.0f;
	float jitter = 0.0f;
	float loss = 0.0f;
	if (!PyArg_ParseTuple(args, "fff", &latency, &jitter, &loss)) {
		return nullptr;
	}
	KX_NetworkManager *manager = ManagerCreate();
	if (!manager) {
		return nullptr;
	}
	manager->SetSimulation(uint32_t(latency > 0.0f ? latency : 0.0f), uint32_t(jitter > 0.0f ? jitter : 0.0f), loss);
	Py_RETURN_NONE;
}

/// replicate(obj, props=(), transform=True, velocity=False, angular_velocity=False, always_relevant=False,
///           priority=1.0) -> net id
PyObject *Net_replicate(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"obj", "props", "transform", "velocity", "angular_velocity", "always_relevant",
	                               "priority", nullptr};
	PyObject *pyobj = nullptr;
	PyObject *pyprops = nullptr;
	int transform = 1, velocity = 0, angular = 0, relevant = 0;
	float priority = 1.0f;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|Opppp" "f", const_cast<char **>(kwlist), &pyobj, &pyprops,
	                                 &transform, &velocity, &angular, &relevant, &priority)) {
		return nullptr;
	}
	KX_GameObject *obj;
	if (!ObjectFromPy(pyobj, &obj, "network.replicate()")) {
		return nullptr;
	}
	KX_NetworkManager::ReplicateOptions options;
	options.syncTransform = transform != 0;
	options.syncVelocity = velocity != 0;
	options.syncAngular = angular != 0;
	options.alwaysRelevant = relevant != 0;
	options.priority = priority;
	if (pyprops && pyprops != Py_None) {
		PyObject *iter = PyObject_GetIter(pyprops);
		if (!iter) {
			return nullptr;
		}
		while (PyObject *item = PyIter_Next(iter)) {
			const char *name = PyUnicode_AsUTF8(item);
			if (!name) {
				Py_DECREF(item);
				Py_DECREF(iter);
				return nullptr;
			}
			options.props.push_back(name);
			Py_DECREF(item);
		}
		Py_DECREF(iter);
		if (PyErr_Occurred()) {
			return nullptr;
		}
	}
	KX_NetworkManager *manager = ManagerCreate();
	if (!manager) {
		return nullptr;
	}
	std::string error;
	const net::NetId id = manager->Replicate(obj, options, error);
	if (id == net::kInvalidNetId) {
		PyErr_Format(PyExc_RuntimeError, "network.replicate(): %s", error.c_str());
		return nullptr;
	}
	return PyLong_FromUnsignedLong(id);
}

/// spawn(prototype, owner=0, position=None, orientation=None) -> object
PyObject *Net_spawn(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"prototype", "owner", "position", "orientation", nullptr};
	const char *prototype = nullptr;
	int owner = 0;
	PyObject *pypos = nullptr;
	PyObject *pyori = nullptr;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|iOO", const_cast<char **>(kwlist), &prototype, &owner, &pypos,
	                                 &pyori)) {
		return nullptr;
	}
	float position[3];
	float orientation[4];
	bool hasPosition = false, hasOrientation = false;
	if (pypos && pypos != Py_None) {
		mt::vec3 pos;
		if (!PyVecTo(pypos, pos)) {
			PyErr_SetString(PyExc_TypeError, "network.spawn(): position must be a 3D vector");
			return nullptr;
		}
		position[0] = pos.x;
		position[1] = pos.y;
		position[2] = pos.z;
		hasPosition = true;
	}
	if (pyori && pyori != Py_None) {
		mt::quat q;
		if (!PyQuatTo(pyori, q)) {
			PyErr_SetString(PyExc_TypeError, "network.spawn(): orientation must be a quaternion (w, x, y, z)");
			return nullptr;
		}
		orientation[0] = q.vector()[0];
		orientation[1] = q.vector()[1];
		orientation[2] = q.vector()[2];
		orientation[3] = q.scalar();
		hasOrientation = true;
	}
	if (owner < 0 || owner > 0xFFFF) {
		PyErr_SetString(PyExc_ValueError, "network.spawn(): invalid owner");
		return nullptr;
	}
	KX_NetworkManager *manager = ManagerCreate();
	if (!manager) {
		return nullptr;
	}
	std::string error;
	KX_GameObject *obj = manager->Spawn(prototype, net::ClientId(owner), hasPosition ? position : nullptr,
	                                    hasOrientation ? orientation : nullptr, error);
	if (!obj) {
		PyErr_Format(PyExc_RuntimeError, "network.spawn(): %s", error.c_str());
		return nullptr;
	}
	return obj->GetProxy();
}

PyObject *Net_despawn(PyObject *, PyObject *arg)
{
	KX_GameObject *obj;
	if (!ObjectFromPy(arg, &obj, "network.despawn()")) {
		return nullptr;
	}
	KX_NetworkManager *manager = Manager();
	return PyBool_FromLong(manager && manager->Despawn(obj));
}

PyObject *Net_set_owner(PyObject *, PyObject *args)
{
	PyObject *pyobj;
	int client;
	if (!PyArg_ParseTuple(args, "Oi", &pyobj, &client)) {
		return nullptr;
	}
	KX_GameObject *obj;
	if (!ObjectFromPy(pyobj, &obj, "network.set_owner()") || client < 0 || client > 0xFFFF) {
		if (!PyErr_Occurred()) {
			PyErr_SetString(PyExc_ValueError, "network.set_owner(): invalid client");
		}
		return nullptr;
	}
	KX_NetworkManager *manager = Manager();
	return PyBool_FromLong(manager && manager->SetOwner(obj, net::ClientId(client)));
}

PyObject *Net_owner(PyObject *, PyObject *arg)
{
	KX_GameObject *obj;
	if (!ObjectFromPy(arg, &obj, "network.owner()")) {
		return nullptr;
	}
	net::ClientId owner;
	KX_NetworkManager *manager = Manager();
	if (!manager || !manager->GetOwner(obj, owner)) {
		Py_RETURN_NONE;
	}
	return PyLong_FromLong(owner);
}

PyObject *Net_is_owner(PyObject *, PyObject *arg)
{
	KX_GameObject *obj;
	if (!ObjectFromPy(arg, &obj, "network.is_owner()")) {
		return nullptr;
	}
	net::ClientId owner;
	KX_NetworkManager *manager = Manager();
	return PyBool_FromLong(manager && manager->GetOwner(obj, owner) && owner == manager->GetLocalClientId());
}

PyObject *Net_net_id(PyObject *, PyObject *arg)
{
	KX_GameObject *obj;
	if (!ObjectFromPy(arg, &obj, "network.net_id()")) {
		return nullptr;
	}
	return PyLong_FromUnsignedLong(obj->GetNetId());
}

/* Helpers for the module subclass below. */

PyObject *Net_state(PyObject *, PyObject *)
{
	KX_NetworkManager *manager = Manager();
	if (!manager) {
		return Py_BuildValue("(OOssiidi)", Py_False, Py_False, "Player", "", 0, 0, 0.0, 0);
	}
	return Py_BuildValue("(OOssiidi)", manager->IsServer() ? Py_True : Py_False,
	                     manager->IsConnected() ? Py_True : Py_False, manager->GetPlayerName().c_str(),
	                     manager->GetRoomName().c_str(), manager->GetMaxPlayers(), int(manager->GetTick()),
	                     double(manager->GetRttMs()), int(manager->GetLocalClientId()));
}

PyObject *Net_set_player_name(PyObject *, PyObject *arg)
{
	const char *name = PyUnicode_AsUTF8(arg);
	if (!name) {
		return nullptr;
	}
	if (KX_NetworkManager *manager = ManagerCreate()) {
		manager->SetPlayerName(name);
		Py_RETURN_NONE;
	}
	return nullptr;
}

PyObject *Net_clients_raw(PyObject *, PyObject *)
{
	PyObject *list = PyList_New(0);
	KX_NetworkManager *manager = Manager();
	if (!manager) {
		return list;
	}
	for (const KX_NetworkManager::PlayerInfo &player : manager->GetPlayers()) {
		PyObject *item = Py_BuildValue("(isiOO)", player.id, player.name.c_str(), player.ping,
		                               player.ready ? Py_True : Py_False, player.isHost ? Py_True : Py_False);
		PyList_Append(list, item);
		Py_XDECREF(item);
	}
	return list;
}

/// on_xxx(fn): registers and returns fn, so it also works as a decorator.
PyObject *RegisterCallback(const char *event, PyObject *callable)
{
	if (!PyCallable_Check(callable)) {
		PyErr_Format(PyExc_TypeError, "network.%s(): the argument must be callable", event);
		return nullptr;
	}
	if (!ManagerCreate()) {
		return nullptr;
	}
	PyObject *module = PyDict_GetItemString(PyImport_GetModuleDict(), "Range.network");
	PyObject *table = module ? PyObject_GetAttrString(module, "_callbacks") : nullptr;
	PyObject *list = table ? PyDict_GetItemString(table, event) : nullptr;
	if (!list) {
		Py_XDECREF(table);
		PyErr_SetString(PyExc_RuntimeError, "network: callback table missing");
		return nullptr;
	}
	PyList_Append(list, callable);
	Py_DECREF(table);
	Py_INCREF(callable);
	return callable;
}

#define NET_CALLBACK_FUNC(name) \
	PyObject *Net_##name(PyObject *, PyObject *arg) \
	{ \
		return RegisterCallback(#name, arg); \
	}

NET_CALLBACK_FUNC(on_connect)
NET_CALLBACK_FUNC(on_disconnect)
NET_CALLBACK_FUNC(on_reject)
NET_CALLBACK_FUNC(on_chat)
NET_CALLBACK_FUNC(on_start)
NET_CALLBACK_FUNC(on_player_join)
NET_CALLBACK_FUNC(on_player_leave)

#undef NET_CALLBACK_FUNC

/** \} */

PyMethodDef g_methods[] = {
	{"host", (PyCFunction)Net_host, METH_VARARGS | METH_KEYWORDS,
	 "host(port=0, max_players=0, room_name='', password='', dedicated=False, websocket_port=-1) -> bool\n"
	 "Opens a server. Zero or empty values use the Network panel of the scene."},
	{"join", (PyCFunction)Net_join, METH_VARARGS | METH_KEYWORDS,
	 "join(address, password='') -> bool\nJoins 'host', 'host:port' or '[v6]:port'."},
	{"disconnect", Net_disconnect, METH_NOARGS, "disconnect()\nLeaves the session."},
	{"set_ready", Net_set_ready, METH_O, "set_ready(ready)\nLobby: marks this player as ready."},
	{"send_chat", Net_send_chat, METH_O, "send_chat(text) -> bool\nLobby chat, up to 200 bytes of UTF-8."},
	{"start_game", Net_start_game, METH_NOARGS,
	 "start_game() -> bool\nHost only: starts the match. False when some player is not ready."},
	{"discover_lan", Net_discover_lan, METH_NOARGS,
	 "discover_lan() -> list of dict\nNon blocking: call it about once per second."},
	{"set_simulation", Net_set_simulation, METH_VARARGS,
	 "set_simulation(latency_ms, jitter_ms, loss_percent)\nNetwork simulator for the next host()/join()."},
	{"replicate", (PyCFunction)Net_replicate, METH_VARARGS | METH_KEYWORDS,
	 "replicate(obj, props=(), transform=True, velocity=False, angular_velocity=False, always_relevant=False, "
	 "priority=1.0) -> int\nSame as the Replicate checkbox; run it before host()/join(), in the same order "
	 "on every peer."},
	{"spawn", (PyCFunction)Net_spawn, METH_VARARGS | METH_KEYWORDS,
	 "spawn(prototype, owner=0, position=None, orientation=None) -> object\n"
	 "Server only: adds a copy of the inactive object 'prototype' and replicates it."},
	{"despawn", Net_despawn, METH_O, "despawn(obj) -> bool\nServer only: removes a replicated object everywhere."},
	{"set_owner", Net_set_owner, METH_VARARGS, "set_owner(obj, client) -> bool\nServer only."},
	{"owner", Net_owner, METH_O, "owner(obj) -> int or None"},
	{"is_owner", Net_is_owner, METH_O, "is_owner(obj) -> bool\nThis peer owns the object."},
	{"net_id", Net_net_id, METH_O, "net_id(obj) -> int\n0 when the object is not replicated."},
	{"on_connect", Net_on_connect, METH_O, "on_connect(fn(client_id))\nConnected (client) or room open (host, 0)."},
	{"on_disconnect", Net_on_disconnect, METH_O, "on_disconnect(fn(reason, detail))\nDisconnectReason 1 to 5."},
	{"on_reject", Net_on_reject, METH_O, "on_reject(fn(reason, detail))\nRejectReason 1 to 6."},
	{"on_chat", Net_on_chat, METH_O, "on_chat(fn(client_id, text))"},
	{"on_start", Net_on_start, METH_O, "on_start(fn())\nThe host started the match."},
	{"on_player_join", Net_on_player_join, METH_O, "on_player_join(fn(client_id, name))\nServer only."},
	{"on_player_leave", Net_on_player_leave, METH_O, "on_player_leave(fn(client_id))\nServer only."},
	{"_state", Net_state, METH_NOARGS, nullptr},
	{"_set_player_name", Net_set_player_name, METH_O, nullptr},
	{"_clients", Net_clients_raw, METH_NOARGS, nullptr},
	{nullptr, nullptr, 0, nullptr},
};

PyDoc_STRVAR(Network_module_documentation,
             "Multiplayer: host or join a game, replicate objects and react to the session.\n\n"
             "Attributes: isServer, isConnected, playerName (writable), roomName, maxPlayers, clients, tick, rtt,\n"
             "localId. See tools/net_menu/NOTES-D.md for the contract with the lobby menu.\n");

PyModuleDef g_module_def = {
	PyModuleDef_HEAD_INIT,
	"Range.network",
	Network_module_documentation,
	-1,
	g_methods,
	nullptr,
	nullptr,
	nullptr,
	nullptr,
};

/* Python side of the module: read/write attributes, which a plain C module cannot compute. */
const char *kModuleClassSource =
	"import types\n"
	"class _NetworkModule(types.ModuleType):\n"
	"    @property\n"
	"    def isServer(self):\n"
	"        return self._state()[0]\n"
	"    @property\n"
	"    def isConnected(self):\n"
	"        return self._state()[1]\n"
	"    @property\n"
	"    def playerName(self):\n"
	"        return self._state()[2]\n"
	"    @playerName.setter\n"
	"    def playerName(self, value):\n"
	"        self._set_player_name(str(value))\n"
	"    @property\n"
	"    def roomName(self):\n"
	"        return self._state()[3]\n"
	"    @property\n"
	"    def maxPlayers(self):\n"
	"        return self._state()[4]\n"
	"    @property\n"
	"    def tick(self):\n"
	"        return self._state()[5]\n"
	"    @property\n"
	"    def rtt(self):\n"
	"        return self._state()[6]\n"
	"    @property\n"
	"    def localId(self):\n"
	"        return self._state()[7]\n"
	"    @property\n"
	"    def clients(self):\n"
	"        return [types.SimpleNamespace(id=i, name=n, ping=p, ready=r, isHost=h)\n"
	"                for (i, n, p, r, h) in self._clients()]\n";

}  // namespace

PyMODINIT_FUNC initNetworkPythonBinding()
{
	PyObject *module = PyModule_Create(&g_module_def);
	if (!module) {
		return nullptr;
	}
	PyObject *dict = PyModule_GetDict(module);

	PyObject *table = PyDict_New();
	for (const char *name : kEventNames) {
		PyObject *list = PyList_New(0);
		PyDict_SetItemString(table, name, list);
		Py_DECREF(list);
	}
	PyDict_SetItemString(dict, "_callbacks", table);
	Py_DECREF(table);

	/* RejectReason and DisconnectReason (docs/multiplayer-protocol.md, section 5). */
	static const struct {
		const char *name;
		int value;
	} constants[] = {
		{"REJECT_VERSION_MISMATCH", 1}, {"REJECT_SCENE_MISMATCH", 2}, {"REJECT_SERVER_FULL", 3},
		{"REJECT_BAD_TOKEN", 4}, {"REJECT_BANNED", 5}, {"REJECT_GAME_IN_PROGRESS", 6},
		{"DISCONNECT_QUIT", 1}, {"DISCONNECT_TIMEOUT", 2}, {"DISCONNECT_KICKED", 3},
		{"DISCONNECT_PROTOCOL_VIOLATION", 4}, {"DISCONNECT_SERVER_SHUTDOWN", 5},
		{"SERVER", 0},
	};
	for (const auto &constant : constants) {
		PyObject *value = PyLong_FromLong(constant.value);
		PyDict_SetItemString(dict, constant.name, value);
		Py_DECREF(value);
	}

	/* Module subclass with the properties. */
	PyObject *globals = PyDict_New();
	PyDict_SetItemString(globals, "__builtins__", PyEval_GetBuiltins());
	PyObject *result = PyRun_String(kModuleClassSource, Py_file_input, globals, globals);
	if (result) {
		Py_DECREF(result);
		PyObject *cls = PyDict_GetItemString(globals, "_NetworkModule");  // borrowed
		if (cls && PyObject_SetAttrString(module, "__class__", cls) != 0) {
			PyErr_Print();
		}
	}
	else {
		PyErr_Print();
	}
	Py_DECREF(globals);
	return module;
}

#endif  // WITH_PYTHON
