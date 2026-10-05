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

#include <algorithm>
#include <cstdlib>
#include <cstring>

namespace {

const char *kEventNames[] = {
	"on_connect", "on_disconnect", "on_reject", "on_chat", "on_start", "on_player_join", "on_player_leave",
	"on_scene",
};

KX_NetworkManager *Manager()
{
	KX_KetsjiEngine *engine = KX_GetActiveEngine();
	return engine ? engine->GetNetworkManager() : nullptr;
}

KX_NetworkManager *ManagerCreate();
bool ObjectFromPy(PyObject *value, KX_GameObject **obj, const char *prefix);

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
		case KX_NetworkManager::Event::SCENE:
			name = "on_scene";
			args = Py_BuildValue("(s)", event.text.c_str());
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

/// Calls the predict() function of an object with the input of one tick; exceptions are printed.
void DispatchStep(KX_GameObject *obj, const net::InputBlock &input)
{
	PyObject *module = PyDict_GetItemString(PyImport_GetModuleDict(), "Range.network");  // borrowed
	PyObject *table = module ? PyObject_GetAttrString(module, "_predict") : nullptr;
	if (!table) {
		PyErr_Clear();
		return;
	}
	PyObject *key = PyLong_FromUnsignedLong(obj->GetNetId());
	PyObject *fn = PyDict_GetItem(table, key);  // borrowed
	Py_DECREF(key);
	if (fn) {
		PyObject *data = PyBytes_FromStringAndSize(reinterpret_cast<const char *>(input.data()),
		                                           Py_ssize_t(input.size()));
		PyObject *result = PyObject_CallFunctionObjArgs(fn, obj->GetProxy(), data, nullptr);
		if (result) {
			Py_DECREF(result);
		}
		else {
			PyErr_Print();
		}
		Py_XDECREF(data);
	}
	Py_DECREF(table);
}

/// Python value of an RPC argument (a new reference).
PyObject *ArgToPy(const net::RpcArg &arg)
{
	switch (arg.type) {
		case net::RpcArgType::Bool:
			return PyBool_FromLong(arg.b);
		case net::RpcArgType::Int:
			return PyLong_FromLongLong(arg.i);
		case net::RpcArgType::Float:
			return PyFloat_FromDouble(arg.v[0]);
		case net::RpcArgType::Vec3:
			return PyObjectFrom(mt::vec3(arg.v[0], arg.v[1], arg.v[2]));
		case net::RpcArgType::Quat: {
			/* mathutils order w, x, y, z; the wire is x, y, z, w. */
			PyObject *mathutils = PyImport_ImportModule("mathutils");
			PyObject *q = mathutils ? PyObject_CallMethod(mathutils, "Quaternion", "((dddd))", double(arg.v[3]),
			                                              double(arg.v[0]), double(arg.v[1]), double(arg.v[2]))
			                        : nullptr;
			Py_XDECREF(mathutils);
			if (!q) {
				PyErr_Clear();
				return Py_BuildValue("(dddd)", double(arg.v[3]), double(arg.v[0]), double(arg.v[1]), double(arg.v[2]));
			}
			return q;
		}
		case net::RpcArgType::Str:
			return PyUnicode_DecodeUTF8(arg.s.data(), Py_ssize_t(arg.s.size()), "replace");
		case net::RpcArgType::NetId: {
			KX_NetworkManager *manager = Manager();
			KX_GameObject *obj = manager ? manager->FindObject(arg.id) : nullptr;
			if (obj) {
				return obj->GetProxy();
			}
			Py_RETURN_NONE;
		}
	}
	Py_RETURN_NONE;
}

/// bool, int, float, str, game object (sent as its net id), 3 numbers (vector), 4 numbers (quaternion w,x,y,z).
bool ArgFromPy(PyObject *value, net::RpcArg &arg)
{
	if (PyBool_Check(value)) {
		arg.type = net::RpcArgType::Bool;
		arg.b = value == Py_True;
		return true;
	}
	if (PyLong_Check(value)) {
		arg.type = net::RpcArgType::Int;
		arg.i = PyLong_AsLongLong(value);
		return !PyErr_Occurred();
	}
	if (PyFloat_Check(value)) {
		arg.type = net::RpcArgType::Float;
		arg.v[0] = float(PyFloat_AsDouble(value));
		return true;
	}
	if (PyUnicode_Check(value)) {
		Py_ssize_t size;
		const char *text = PyUnicode_AsUTF8AndSize(value, &size);
		if (!text) {
			return false;
		}
		arg.type = net::RpcArgType::Str;
		arg.s.assign(text, size_t(size));
		return true;
	}
	if (PyObject_TypeCheck(value, &KX_GameObject::Type)) {
		KX_GameObject *obj;
		if (!ObjectFromPy(value, &obj, "network.call()")) {
			return false;
		}
		arg.type = net::RpcArgType::NetId;
		arg.id = obj->GetNetId();
		if (arg.id == net::kInvalidNetId) {
			PyErr_SetString(PyExc_ValueError, "network.call(): a game object argument must be replicated");
			return false;
		}
		return true;
	}
	const Py_ssize_t size = PySequence_Check(value) ? PySequence_Size(value) : -1;
	if (size == 3) {
		mt::vec3 vec;
		if (PyVecTo(value, vec)) {
			arg.type = net::RpcArgType::Vec3;
			arg.v[0] = vec.x;
			arg.v[1] = vec.y;
			arg.v[2] = vec.z;
			return true;
		}
	}
	else if (size == 4) {
		/* w, x, y, z like mathutils.Quaternion. */
		double w[4];
		bool ok = true;
		for (Py_ssize_t i = 0; i < 4 && ok; ++i) {
			PyObject *item = PySequence_GetItem(value, i);
			w[i] = item ? PyFloat_AsDouble(item) : -1.0;
			ok = item && !PyErr_Occurred();
			Py_XDECREF(item);
		}
		if (ok) {
			arg.type = net::RpcArgType::Quat;
			arg.v[0] = float(w[1]);
			arg.v[1] = float(w[2]);
			arg.v[2] = float(w[3]);
			arg.v[3] = float(w[0]);
			return true;
		}
	}
	PyErr_Clear();
	PyErr_Format(PyExc_TypeError, "network.call(): unsupported argument type '%s' (bool, int, float, str, game "
	             "object, 3D vector or quaternion)", Py_TYPE(value)->tp_name);
	return false;
}

/// Runs the Python function of a game RPC; its exceptions are printed.
void DispatchRpc(const std::string &name, net::ClientId sender, KX_GameObject *obj, const std::vector<net::RpcArg> &args)
{
	PyObject *module = PyDict_GetItemString(PyImport_GetModuleDict(), "Range.network");  // borrowed
	PyObject *table = module ? PyObject_GetAttrString(module, "_rpcs") : nullptr;
	if (!table) {
		PyErr_Clear();
		return;
	}
	PyObject *fn = PyDict_GetItemString(table, name.c_str());  // borrowed
	if (fn) {
		const Py_ssize_t first = obj ? 2 : 1;
		PyObject *tuple = PyTuple_New(first + Py_ssize_t(args.size()));
		if (obj) {
			PyTuple_SET_ITEM(tuple, 0, obj->GetProxy());
		}
		PyTuple_SET_ITEM(tuple, first - 1, PyLong_FromLong(sender));
		for (size_t i = 0; i < args.size(); ++i) {
			PyTuple_SET_ITEM(tuple, first + Py_ssize_t(i), ArgToPy(args[i]));
		}
		PyObject *result = PyObject_CallObject(fn, tuple);
		if (result) {
			Py_DECREF(result);
		}
		else {
			PyErr_Print();
		}
		Py_DECREF(tuple);
	}
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
	manager->SetStepSink(DispatchStep);
	manager->SetRpcSink(DispatchRpc);
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
		/* Protocol v2 carries the password in Hello; the server rejects a mismatch with WrongPassword.
		 * It travels in clear over the UDP/WS link: a casual access gate, not real security. */
		CM_Warning("network: host password travels in clear text; it gates casual access, not real security");
	}
	options.password = password;
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
	std::string host;
	int port = 0;
	if (!ParseAddress(address, host, port)) {
		CM_Warning("network: '" << address << "' is not an address (host, host:port or [v6]:port); "
		           "room codes need a lobby service, which this version does not have");
		Py_RETURN_FALSE;
	}
	std::string error;
	if (!manager->Join(host, port, error, password)) {
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

/// change_scene(name): server only.
PyObject *Net_change_scene(PyObject *, PyObject *arg)
{
	if (!PyUnicode_Check(arg)) {
		PyErr_SetString(PyExc_TypeError, "network.change_scene(): expected a scene name");
		return nullptr;
	}
	KX_NetworkManager *manager = Manager();
	std::string error = "server only";
	if (!manager || !manager->ChangeScene(PyUnicode_AsUTF8(arg), error)) {
		PyErr_Format(PyExc_RuntimeError, "network.change_scene(): %s", error.c_str());
		return nullptr;
	}
	Py_RETURN_NONE;
}

/// set_client_view(client, center=None, radius=None): center is an object (followed) or a 3D position.
PyObject *Net_set_client_view(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"client", "center", "radius", nullptr};
	int client;
	PyObject *pycenter = Py_None;
	PyObject *pyradius = Py_None;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "i|OO", const_cast<char **>(kwlist), &client, &pycenter,
	                                 &pyradius)) {
		return nullptr;
	}
	if (client < 0 || client > 0xFFFF) {
		PyErr_SetString(PyExc_ValueError, "network.set_client_view(): invalid client");
		return nullptr;
	}
	float radius = -1.0f;
	if (pyradius != Py_None) {
		radius = float(PyFloat_AsDouble(pyradius));
		if (PyErr_Occurred()) {
			return nullptr;
		}
		radius = std::max(radius, 0.0f);
	}
	KX_GameObject *obj = nullptr;
	float position[3];
	bool hasPosition = false;
	if (pycenter != Py_None) {
		mt::vec3 pos;
		if (PyVecTo(pycenter, pos)) {
			position[0] = pos.x;
			position[1] = pos.y;
			position[2] = pos.z;
			hasPosition = true;
		}
		else {
			PyErr_Clear();
			if (!ObjectFromPy(pycenter, &obj, "network.set_client_view()")) {
				return nullptr;
			}
		}
	}
	KX_NetworkManager *manager = Manager();
	if (!manager) {
		PyErr_SetString(PyExc_RuntimeError, "network.set_client_view(): server only");
		return nullptr;
	}
	const bool clear = !obj && !hasPosition && pyradius == Py_None;
	std::string error;
	if (!manager->SetClientView(net::ClientId(client), obj, hasPosition ? position : nullptr, radius, clear,
	                            error)) {
		PyErr_Format(PyExc_RuntimeError, "network.set_client_view(): %s", error.c_str());
		return nullptr;
	}
	Py_RETURN_NONE;
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

/// predict(obj, fn) -> bool: fn(obj, input_bytes) moves obj by one tick; None stops it.
PyObject *Net_predict(PyObject *, PyObject *args)
{
	PyObject *pyobj, *fn;
	if (!PyArg_ParseTuple(args, "OO", &pyobj, &fn)) {
		return nullptr;
	}
	KX_GameObject *obj;
	if (!ObjectFromPy(pyobj, &obj, "network.predict()")) {
		return nullptr;
	}
	if (fn != Py_None && !PyCallable_Check(fn)) {
		PyErr_SetString(PyExc_TypeError, "network.predict(): fn must be callable or None");
		return nullptr;
	}
	KX_NetworkManager *manager = ManagerCreate();
	if (!manager) {
		return nullptr;
	}
	if (!manager->SetPredicted(obj, fn != Py_None)) {
		Py_RETURN_FALSE;
	}
	PyObject *module = PyDict_GetItemString(PyImport_GetModuleDict(), "Range.network");
	PyObject *table = module ? PyObject_GetAttrString(module, "_predict") : nullptr;
	if (!table) {
		return nullptr;
	}
	PyObject *key = PyLong_FromUnsignedLong(obj->GetNetId());
	if (fn == Py_None) {
		if (PyDict_DelItem(table, key) != 0) {
			PyErr_Clear();
		}
	}
	else {
		PyDict_SetItem(table, key, fn);
	}
	Py_DECREF(key);
	Py_DECREF(table);
	Py_RETURN_TRUE;
}

PyObject *Net_set_input(PyObject *, PyObject *arg)
{
	char *data;
	Py_ssize_t size;
	if (PyBytes_AsStringAndSize(arg, &data, &size) != 0) {
		PyErr_Clear();
		PyErr_SetString(PyExc_TypeError, "network.set_input(): bytes expected");
		return nullptr;
	}
	if (size_t(size) > KX_NetworkManager::kMaxUserInputBytes) {
		PyErr_Format(PyExc_ValueError, "network.set_input(): at most %d bytes",
		             int(KX_NetworkManager::kMaxUserInputBytes));
		return nullptr;
	}
	KX_NetworkManager *manager = ManagerCreate();
	if (!manager) {
		return nullptr;
	}
	manager->SetInput(net::InputBlock(data, data + size));
	Py_RETURN_NONE;
}

/// input(client) -> bytes or None: input the server applied this tick (client 0 = host).
PyObject *Net_input(PyObject *, PyObject *arg)
{
	const long client = PyLong_AsLong(arg);
	if (client == -1 && PyErr_Occurred()) {
		return nullptr;
	}
	KX_NetworkManager *manager = Manager();
	net::InputBlock input;
	if (!manager || client < 0 || client > 0xFFFF || !manager->GetClientInput(net::ClientId(client), input)) {
		Py_RETURN_NONE;
	}
	return PyBytes_FromStringAndSize(reinterpret_cast<const char *>(input.data()), Py_ssize_t(input.size()));
}

/// view_time(client=0) -> (tick, alpha) or None.
PyObject *Net_view_time(PyObject *, PyObject *args)
{
	int client = 0;
	if (!PyArg_ParseTuple(args, "|i", &client)) {
		return nullptr;
	}
	KX_NetworkManager *manager = Manager();
	net::Tick tick;
	float alpha;
	if (!manager || client < 0 || client > 0xFFFF || !manager->GetViewTime(net::ClientId(client), tick, alpha)) {
		Py_RETURN_NONE;
	}
	return Py_BuildValue("(kd)", (unsigned long)tick, double(alpha));
}

PyObject *Net_prediction_stats(PyObject *, PyObject *arg)
{
	KX_GameObject *obj;
	if (!ObjectFromPy(arg, &obj, "network.prediction_stats()")) {
		return nullptr;
	}
	KX_NetworkManager *manager = Manager();
	net::PredictionStats stats;
	KX_NetworkManager::PredictionInfo info;
	if (!manager || !manager->GetPredictionStats(obj, stats, &info)) {
		Py_RETURN_NONE;
	}
	return Py_BuildValue("{s:k,s:k,s:k,s:k,s:d,s:d,s:k,s:k,s:k,s:d}", "inputs", (unsigned long)stats.inputsRecorded,
	                     "reconciles", (unsigned long)stats.reconciles, "corrections",
	                     (unsigned long)stats.corrections, "teleports", (unsigned long)stats.teleports, "last_error",
	                     double(stats.lastError), "max_error", double(stats.maxError), "tick",
	                     (unsigned long)info.tick, "snapshot_tick", (unsigned long)info.snapshotTick, "resyncs",
	                     (unsigned long)info.resyncs, "lead_adjust", double(info.leadAdjust));
}

/// input_stats(client) -> dict or None
PyObject *Net_input_stats(PyObject *, PyObject *arg)
{
	const long client = PyLong_AsLong(arg);
	if (client == -1 && PyErr_Occurred()) {
		return nullptr;
	}
	KX_NetworkManager *manager = Manager();
	net::InputQueueStats stats;
	if (!manager || client < 0 || client > 0xFFFF || !manager->GetInputStats(net::ClientId(client), stats)) {
		Py_RETURN_NONE;
	}
	return Py_BuildValue("{s:k,s:k,s:k,s:k,s:k,s:k,s:k,s:k}", "received", (unsigned long)stats.received,
	                     "duplicates", (unsigned long)stats.duplicates, "late", (unsigned long)stats.late, "too_far",
	                     (unsigned long)stats.tooFar, "applied", (unsigned long)stats.applied, "repeated",
	                     (unsigned long)stats.repeated, "missing", (unsigned long)stats.missing, "invalid",
	                     (unsigned long)stats.invalid);
}

/// set_hitbox(obj, radius, half_height=0.0) -> bool
PyObject *Net_set_hitbox(PyObject *, PyObject *args)
{
	PyObject *pyobj;
	float radius, halfHeight = 0.0f;
	if (!PyArg_ParseTuple(args, "Of|f", &pyobj, &radius, &halfHeight)) {
		return nullptr;
	}
	KX_GameObject *obj;
	if (!ObjectFromPy(pyobj, &obj, "network.set_hitbox()")) {
		return nullptr;
	}
	KX_NetworkManager *manager = ManagerCreate();
	if (!manager) {
		return nullptr;
	}
	return PyBool_FromLong(manager->SetHitbox(obj, radius, halfHeight));
}

/// raycast_past(origin, direction, distance=100.0, client=-1, ignore=None, max_rewind_ms=400)
///     -> (obj, point, distance) or None
PyObject *Net_raycast_past(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"origin", "direction", "distance", "client", "ignore", "max_rewind_ms", nullptr};
	PyObject *pyorigin, *pydir, *pyignore = nullptr;
	float distance = 100.0f;
	int client = -1;
	int maxRewindMs = 400;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "OO|fiOi", const_cast<char **>(kwlist), &pyorigin, &pydir,
	                                 &distance, &client, &pyignore, &maxRewindMs)) {
		return nullptr;
	}
	mt::vec3 origin, dir;
	if (!PyVecTo(pyorigin, origin) || !PyVecTo(pydir, dir)) {
		PyErr_SetString(PyExc_TypeError, "network.raycast_past(): origin and direction must be 3D vectors");
		return nullptr;
	}
	KX_GameObject *ignore = nullptr;
	if (pyignore && pyignore != Py_None && !ObjectFromPy(pyignore, &ignore, "network.raycast_past()")) {
		return nullptr;
	}
	KX_NetworkManager *manager = Manager();
	const float o[3] = {origin.x, origin.y, origin.z};
	const float d[3] = {dir.x, dir.y, dir.z};
	KX_GameObject *hit = nullptr;
	float point[3], hitDistance;
	if (!manager || !manager->RaycastPast(o, d, distance, client, ignore, hit, point, hitDistance, maxRewindMs)) {
		Py_RETURN_NONE;
	}
	return Py_BuildValue("(O(ddd)d)", hit->GetProxy(), double(point[0]), double(point[1]), double(point[2]),
	                     double(hitDistance));
}

/// _register_rpc(name, target, reliable, owner_only, fn): see rpc() in kModuleClassSource.
PyObject *Net_register_rpc(PyObject *, PyObject *args)
{
	const char *name, *target;
	int reliable, ownerOnly;
	PyObject *fn;
	if (!PyArg_ParseTuple(args, "sspp" "O", &name, &target, &reliable, &ownerOnly, &fn)) {
		return nullptr;
	}
	if (!PyCallable_Check(fn)) {
		PyErr_SetString(PyExc_TypeError, "network.rpc(): the function must be callable");
		return nullptr;
	}
	KX_NetworkManager::RpcOptions options;
	options.name = name;
	options.reliable = reliable != 0;
	options.requireOwner = ownerOnly != 0;
	const std::string t = target;
	if (t == "server") {
		options.target = net::RpcTarget::Server;
	}
	else if (t == "owner") {
		options.target = net::RpcTarget::Owner;
	}
	else if (t == "all") {
		options.target = net::RpcTarget::All;
	}
	else if (t == "others") {
		options.target = net::RpcTarget::Others;
	}
	else {
		PyErr_Format(PyExc_ValueError, "network.rpc(): target must be 'server', 'owner', 'all' or 'others', not '%s'",
		             target);
		return nullptr;
	}
	KX_NetworkManager *manager = ManagerCreate();
	if (!manager) {
		return nullptr;
	}
	std::string error;
	if (!manager->RegisterRpc(options, error)) {
		PyErr_Format(PyExc_RuntimeError, "network.rpc(): %s", error.c_str());
		return nullptr;
	}
	PyObject *module = PyDict_GetItemString(PyImport_GetModuleDict(), "Range.network");
	PyObject *table = module ? PyObject_GetAttrString(module, "_rpcs") : nullptr;
	if (!table) {
		return nullptr;
	}
	PyDict_SetItemString(table, name, fn);
	Py_DECREF(table);
	Py_RETURN_NONE;
}

/// call(name, *args, obj=None) -> bool
PyObject *Net_call(PyObject *, PyObject *args, PyObject *kwds)
{
	const Py_ssize_t count = PyTuple_GET_SIZE(args);
	if (count < 1 || !PyUnicode_Check(PyTuple_GET_ITEM(args, 0))) {
		PyErr_SetString(PyExc_TypeError, "network.call(name, *args, obj=None): name must be a string");
		return nullptr;
	}
	const char *name = PyUnicode_AsUTF8(PyTuple_GET_ITEM(args, 0));
	KX_GameObject *obj = nullptr;
	if (kwds) {
		PyObject *key, *value;
		Py_ssize_t pos = 0;
		while (PyDict_Next(kwds, &pos, &key, &value)) {
			if (!PyUnicode_Check(key) || PyUnicode_CompareWithASCIIString(key, "obj") != 0) {
				PyErr_SetString(PyExc_TypeError, "network.call(): the only keyword argument is obj");
				return nullptr;
			}
			if (value != Py_None && !ObjectFromPy(value, &obj, "network.call()")) {
				return nullptr;
			}
		}
	}
	std::vector<net::RpcArg> rpcArgs(size_t(count - 1));
	for (Py_ssize_t i = 1; i < count; ++i) {
		if (!ArgFromPy(PyTuple_GET_ITEM(args, i), rpcArgs[size_t(i - 1)])) {
			return nullptr;
		}
	}
	KX_NetworkManager *manager = Manager();
	if (!manager) {
		Py_RETURN_FALSE;
	}
	std::string error;
	if (!manager->CallRpc(name, obj, rpcArgs, error)) {
		if (error.compare(0, 7, "unknown") == 0) {
			PyErr_Format(PyExc_KeyError, "network.call(): %s", error.c_str());
			return nullptr;
		}
		Py_RETURN_FALSE;
	}
	Py_RETURN_TRUE;
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

/// The player runs as a headless server (--server); false without an engine.
PyObject *Net_headless(PyObject *, PyObject *)
{
	KX_KetsjiEngine *engine = KX_GetActiveEngine();
	return PyBool_FromLong(engine && engine->IsServerMode());
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
NET_CALLBACK_FUNC(on_scene)

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
	{"on_scene", Net_on_scene, METH_O,
	 "on_scene(fn(scene_name))\nThe session moved to another scene and it is loaded (server and clients)."},
	{"change_scene", Net_change_scene, METH_O,
	 "change_scene(name)\nServer only: replaces the session scene during the match; the clients load the same\n"
	 "scene and get everything again once it is loaded."},
	{"predict", Net_predict, METH_VARARGS,
	 "predict(obj, fn) -> bool\nfn(obj, input) moves obj by one tick with the owner's input (bytes): on the server\n"
	 "every tick, on the owning client ahead of the server (prediction, corrected by the snapshots).\n"
	 "Register it on every peer; None stops it."},
	{"set_input", Net_set_input, METH_O,
	 "set_input(data)\nInput of the local player (bytes, up to 57), sent every tick until changed, with the time\n"
	 "the remote objects were drawn at when it was called (lag compensation): call it every frame."},
	{"input", Net_input, METH_O, "input(client) -> bytes or None\nServer: input applied this tick (0 = host)."},
	{"view_time", Net_view_time, METH_VARARGS,
	 "view_time(client=0) -> (tick, alpha) or None\nClient: time the remote objects are drawn at.\n"
	 "Server: the view time the client sent with its last input."},
	{"prediction_stats", Net_prediction_stats, METH_O, "prediction_stats(obj) -> dict or None\nClient only."},
	{"input_stats", Net_input_stats, METH_O,
	 "input_stats(client) -> dict or None\nServer: how the client's inputs arrived (late, repeated, missing...)."},
	{"set_client_view", (PyCFunction)Net_set_client_view, METH_VARARGS | METH_KEYWORDS,
	 "set_client_view(client, center=None, radius=None)\nServer only: relevance center (object or position) and "
	 "radius of a client; radius 0 sends everything. No center: first object the client owns. All None: back to "
	 "the scene's Relevance Radius."},
	{"set_hitbox", Net_set_hitbox, METH_VARARGS,
	 "set_hitbox(obj, radius, half_height=0.0) -> bool\nServer: sphere or capsule (local Z) kept 1 s back for\n"
	 "raycast_past(); radius 0 removes it."},
	{"raycast_past", (PyCFunction)Net_raycast_past, METH_VARARGS | METH_KEYWORDS,
	 "raycast_past(origin, direction, distance=100.0, client=-1, ignore=None, max_rewind_ms=400)\n"
	 "    -> (obj, point, distance) or None\n"
	 "Server: ray against the hitboxes as client saw them (lag compensation, 1 s of history); -1 = now."},
	{"call", (PyCFunction)Net_call, METH_VARARGS | METH_KEYWORDS,
	 "call(name, *args, obj=None) -> bool\nCalls a game RPC registered with @rpc; obj makes it an object call\n"
	 "(target 'owner' and owner_only use its owner). False when refused here (no session, wrong target...)."},
	{"_register_rpc", Net_register_rpc, METH_VARARGS, nullptr},
	{"_state", Net_state, METH_NOARGS, nullptr},
	{"_set_player_name", Net_set_player_name, METH_O, nullptr},
	{"_clients", Net_clients_raw, METH_NOARGS, nullptr},
	{"_headless", Net_headless, METH_NOARGS, nullptr},
	{nullptr, nullptr, 0, nullptr},
};

PyDoc_STRVAR(Network_module_documentation,
             "Multiplayer: host or join a game, replicate objects and react to the session.\n\n"
             "Attributes: isServer, isConnected, playerName (writable), roomName, maxPlayers, clients, tick, rtt,\n"
             "localId, headless. See tools/net_menu/NOTES-D.md for the contract with the lobby menu.\n");

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

const char *kModuleHelpersSource =
	"def rpc(fn=None, *, name=None, target='server', reliable=True, owner_only=False):\n"
	"    \"\"\"Registers a game RPC (decorator), before host()/join() and with the same names on every peer.\n"
	"    target: 'server', 'owner' (server to the owner of the object), 'all' or 'others'.\n"
	"    The function gets (sender, *args), or (obj, sender, *args) for a call made on an object;\n"
	"    sender is the calling client on the server and 0 on clients.\"\"\"\n"
	"    def wrap(f):\n"
	"        _register_rpc(name or f.__name__, target, bool(reliable), bool(owner_only), f)\n"
	"        return f\n"
	"    return wrap(fn) if fn is not None else wrap\n"
	"class ObjectNet:\n"
	"    \"\"\"obj.net: the network side of a game object.\"\"\"\n"
	"    __slots__ = ('_obj',)\n"
	"    def __init__(self, obj):\n"
	"        self._obj = obj\n"
	"    @property\n"
	"    def id(self):\n"
	"        return net_id(self._obj)\n"
	"    @property\n"
	"    def replicated(self):\n"
	"        return net_id(self._obj) != 0\n"
	"    @property\n"
	"    def owner(self):\n"
	"        return owner(self._obj)\n"
	"    @property\n"
	"    def isOwner(self):\n"
	"        return is_owner(self._obj)\n"
	"    def call(self, name, *args):\n"
	"        return call(name, *args, obj=self._obj)\n"
	"    def predict(self, fn):\n"
	"        return predict(self._obj, fn)\n"
	"def _object_net(obj):\n"
	"    return ObjectNet(obj)\n";

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
	"    def headless(self):\n"
	"        return self._headless()\n"
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
	PyObject *rpcs = PyDict_New();
	PyDict_SetItemString(dict, "_rpcs", rpcs);
	Py_DECREF(rpcs);
	PyObject *predict = PyDict_New();
	PyDict_SetItemString(dict, "_predict", predict);
	Py_DECREF(predict);

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

	/* Python helpers that live in the module itself: the rpc() decorator and obj.net. */
	PyDict_SetItemString(dict, "__builtins__", PyEval_GetBuiltins());
	PyObject *helpers = PyRun_String(kModuleHelpersSource, Py_file_input, dict, dict);
	if (helpers) {
		Py_DECREF(helpers);
	}
	else {
		PyErr_Print();
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
