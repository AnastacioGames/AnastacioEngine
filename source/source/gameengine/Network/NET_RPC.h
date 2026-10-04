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

/** \file NET_RPC.h
 *  \ingroup network
 *  \brief Remote procedure calls by name (contract section 8).
 *
 * Both sides register the same RPCs; rpcId is the index in the table sorted by name. Clients
 * may call Server, All and Others RPCs; the server checks target and owner, counts a violation
 * on the session for a bad call and relays All/Others to the clients. Owner RPCs go only from
 * the server to the owner of the object. The 120 RPC/s limit is enforced by ServerSession.
 */

#ifndef __NET_RPC_H__
#define __NET_RPC_H__

#include "NET_Messages.h"
#include "NET_Session.h"
#include "NET_Types.h"

#include <functional>
#include <string>
#include <vector>

namespace net {

enum class RpcTarget : uint8_t {
	Server = 0,  // runs on the server
	Owner = 1,  // runs on the client owning netId (server to client only)
	All = 2,  // runs on the server and every client, the caller included
	Others = 3,  // runs on the server and every client but the caller
};

struct RpcDesc;

/// A call ready to run, with its arguments decoded.
struct RpcCall {
	const RpcDesc *desc = nullptr;
	uint16_t rpcId = 0;
	/// Calling client on the server; on clients always 0 (the contract has no caller field).
	ClientId caller = kServerClientId;
	NetId netId = kInvalidNetId;
	Tick tick = kNoTick;
	const std::vector<RpcArg> *args = nullptr;
};

using RpcHandler = std::function<void(const RpcCall &call)>;

/// Owner of an object; false when it does not exist (despawned or never spawned).
using RpcOwnerLookup = std::function<bool(NetId id, ClientId &owner)>;

struct RpcDesc {
	std::string name;
	RpcTarget target = RpcTarget::Server;
	/// The caller must own netId (netId 0 is then refused).
	bool requireOwner = false;
	/// false = sent on the unreliable channel (Input to the server, Snapshot to clients).
	bool reliable = true;
	/// When checkArgs is set the argument types must be exactly argTypes.
	bool checkArgs = false;
	std::vector<RpcArgType> argTypes;
	RpcHandler handler;
};

/// RPC table shared by server and client. Register everything, then finalize().
class RpcTable {
public:
	/// False for an empty or repeated name, a full table or a finalized table.
	bool add(const RpcDesc &desc);
	/// Sorts by name and assigns the ids.
	void finalize();
	bool finalized() const;

	/// Sets the handler of a registered RPC (also after finalize). False when not found.
	bool setHandler(const std::string &name, const RpcHandler &handler);

	size_t size() const;
	/// nullptr when id is out of range or the table is not finalized.
	const RpcDesc *find(uint16_t id) const;
	const RpcDesc *find(const std::string &name) const;
	/// -1 when not found or not finalized.
	int idOf(const std::string &name) const;

	static bool argsMatch(const RpcDesc &desc, const std::vector<RpcArg> &args);

private:
	std::vector<RpcDesc> m_descs;
	bool m_finalized = false;
};

struct RpcStats {
	uint32_t sent = 0;
	uint32_t received = 0;
	uint32_t dispatched = 0;  // handlers run here
	uint32_t relayed = 0;  // messages relayed to other clients (server)
	uint32_t invalid = 0;  // failed to decode
	uint32_t unknownId = 0;
	uint32_t refusedTarget = 0;
	uint32_t refusedOwner = 0;
	uint32_t refusedArgs = 0;
	uint32_t droppedNoObject = 0;  // netId despawned or unknown
};

/// Encodes an Rpc packet; false when the arguments are invalid or above 1024 bytes.
bool makeRpcPacket(uint16_t rpcId, NetId netId, Tick tick, const std::vector<RpcArg> &args,
                   std::vector<uint8_t> &packet);

class RpcServer {
public:
	RpcServer(ServerSession &session, const RpcTable &table, const RpcOwnerLookup &owner);

	/// Takes Rpc message events. Returns true when the event was an Rpc message. Bad calls count
	/// a violation on the session, which may close the connection (ClientLeft goes to events).
	bool handleEvent(const SessionEvent &event, uint64_t nowMs, std::vector<SessionEvent> &events);

	/// Call made by the server. Server runs here; Owner goes to the owner of netId (or runs here
	/// when the server owns it); All runs here and on every client; Others goes to every client.
	bool call(uint16_t rpcId, NetId netId, const std::vector<RpcArg> &args, Tick tick = kNoTick);
	bool call(const std::string &name, NetId netId, const std::vector<RpcArg> &args, Tick tick = kNoTick);
	/// Sends an RPC to one client, whatever its target.
	bool callClient(ClientId client, uint16_t rpcId, NetId netId, const std::vector<RpcArg> &args,
	                Tick tick = kNoTick);

	const RpcStats &stats() const;

private:
	void dispatch(const RpcDesc &desc, const RpcMsg &msg, ClientId caller);
	Channel channelOf(const RpcDesc &desc) const;
	bool refuse(ClientId client, uint32_t &counter, uint64_t nowMs, std::vector<SessionEvent> &events);

	ServerSession &m_session;
	const RpcTable &m_table;
	RpcOwnerLookup m_owner;
	RpcStats m_stats;
};

class RpcClient {
public:
	RpcClient(ClientSession &session, const RpcTable &table, const RpcOwnerLookup &owner);

	/// Sends a call to the server. Refused here (false) for Owner RPCs, for requireOwner on an
	/// object this client does not own, and for arguments that do not fit.
	bool call(uint16_t rpcId, NetId netId, const std::vector<RpcArg> &args, Tick tick = kNoTick);
	bool call(const std::string &name, NetId netId, const std::vector<RpcArg> &args, Tick tick = kNoTick);

	/// Takes Rpc messages from the server and runs their handlers. Returns true for Rpc messages.
	bool handleEvent(const SessionEvent &event);

	const RpcStats &stats() const;

private:
	ClientSession &m_session;
	const RpcTable &m_table;
	RpcOwnerLookup m_owner;
	RpcStats m_stats;
};

}  // namespace net

#endif  // __NET_RPC_H__
