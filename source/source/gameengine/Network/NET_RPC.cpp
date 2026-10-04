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

/** \file gameengine/Network/NET_RPC.cpp
 *  \ingroup network
 */

#include "NET_RPC.h"

#include <algorithm>

namespace net {

namespace {

bool decodeRpcEvent(const SessionEvent &event, RpcMsg &msg)
{
	RawMessage raw;
	raw.type = event.messageType;
	raw.body = event.body.data();
	raw.size = event.body.size();
	return decodeMessage(raw, msg);
}

bool isRpcEvent(const SessionEvent &event)
{
	return event.type == SessionEvent::Type::Message && event.messageType == uint8_t(MessageType::Rpc);
}

}  // namespace

/* -------------------------------------------------------------------- */
/** \name RpcTable
 * \{ */

bool RpcTable::add(const RpcDesc &desc)
{
	if (m_finalized || desc.name.empty() || m_descs.size() >= 0xFFFF) {
		return false;
	}
	for (const RpcDesc &d : m_descs) {
		if (d.name == desc.name) {
			return false;
		}
	}
	m_descs.push_back(desc);
	return true;
}

void RpcTable::finalize()
{
	// Plain byte order, the same on every platform and locale.
	std::sort(m_descs.begin(), m_descs.end(), [](const RpcDesc &a, const RpcDesc &b) { return a.name < b.name; });
	m_finalized = true;
}

bool RpcTable::finalized() const
{
	return m_finalized;
}

bool RpcTable::setHandler(const std::string &name, const RpcHandler &handler)
{
	for (RpcDesc &d : m_descs) {
		if (d.name == name) {
			d.handler = handler;
			return true;
		}
	}
	return false;
}

size_t RpcTable::size() const
{
	return m_descs.size();
}

const RpcDesc *RpcTable::find(uint16_t id) const
{
	if (!m_finalized || id >= m_descs.size()) {
		return nullptr;
	}
	return &m_descs[id];
}

const RpcDesc *RpcTable::find(const std::string &name) const
{
	const int id = idOf(name);
	return id < 0 ? nullptr : &m_descs[size_t(id)];
}

int RpcTable::idOf(const std::string &name) const
{
	if (!m_finalized) {
		return -1;
	}
	const auto it = std::lower_bound(m_descs.begin(), m_descs.end(), name,
	                                 [](const RpcDesc &d, const std::string &n) { return d.name < n; });
	if (it == m_descs.end() || it->name != name) {
		return -1;
	}
	return int(it - m_descs.begin());
}

bool RpcTable::argsMatch(const RpcDesc &desc, const std::vector<RpcArg> &args)
{
	if (!desc.checkArgs) {
		return true;
	}
	if (args.size() != desc.argTypes.size()) {
		return false;
	}
	for (size_t i = 0; i < args.size(); ++i) {
		if (args[i].type != desc.argTypes[i]) {
			return false;
		}
	}
	return true;
}

/** \} */

bool makeRpcPacket(uint16_t rpcId, NetId netId, Tick tick, const std::vector<RpcArg> &args,
                   std::vector<uint8_t> &packet)
{
	RpcMsg msg;
	msg.netId = netId;
	msg.rpcId = rpcId;
	msg.tick = tick;
	msg.args = args;
	packet.clear();
	return appendMessage(packet, msg);
}

/* -------------------------------------------------------------------- */
/** \name RpcServer
 * \{ */

RpcServer::RpcServer(ServerSession &session, const RpcTable &table, const RpcOwnerLookup &owner)
    : m_session(session), m_table(table), m_owner(owner)
{
}

Channel RpcServer::channelOf(const RpcDesc &desc) const
{
	return desc.reliable ? Channel::Rpc : Channel::Snapshot;
}

void RpcServer::dispatch(const RpcDesc &desc, const RpcMsg &msg, ClientId caller)
{
	if (!desc.handler) {
		return;
	}
	RpcCall call;
	call.desc = &desc;
	call.rpcId = msg.rpcId;
	call.caller = caller;
	call.netId = msg.netId;
	call.tick = msg.tick;
	call.args = &msg.args;
	++m_stats.dispatched;
	desc.handler(call);
}

bool RpcServer::refuse(ClientId client, uint32_t &counter, uint64_t nowMs, std::vector<SessionEvent> &events)
{
	++counter;
	return m_session.reportViolation(client, nowMs, events);
}

bool RpcServer::handleEvent(const SessionEvent &event, uint64_t nowMs, std::vector<SessionEvent> &events)
{
	if (!isRpcEvent(event)) {
		return false;
	}
	++m_stats.received;
	const ClientId caller = event.client;
	RpcMsg msg;
	if (!decodeRpcEvent(event, msg)) {
		refuse(caller, m_stats.invalid, nowMs, events);
		return true;
	}
	const RpcDesc *desc = m_table.find(msg.rpcId);
	if (!desc) {
		refuse(caller, m_stats.unknownId, nowMs, events);
		return true;
	}
	if (desc->target == RpcTarget::Owner) {
		refuse(caller, m_stats.refusedTarget, nowMs, events);
		return true;
	}
	if (!RpcTable::argsMatch(*desc, msg.args)) {
		refuse(caller, m_stats.refusedArgs, nowMs, events);
		return true;
	}
	if (desc->requireOwner && msg.netId == kInvalidNetId) {
		refuse(caller, m_stats.refusedOwner, nowMs, events);
		return true;
	}
	if (msg.netId != kInvalidNetId) {
		ClientId owner = kServerClientId;
		if (!m_owner || !m_owner(msg.netId, owner)) {
			// Usually a race with a Despawn: not a violation.
			++m_stats.droppedNoObject;
			return true;
		}
		if (desc->requireOwner && owner != caller) {
			refuse(caller, m_stats.refusedOwner, nowMs, events);
			return true;
		}
	}

	if (desc->target == RpcTarget::All || desc->target == RpcTarget::Others) {
		// Relayed as RpcFrom so the clients know who called.
		RpcFromMsg from;
		from.fromClient = caller;
		from.rpc = msg;
		std::vector<uint8_t> packet;
		if (appendMessage(packet, from)) {
			for (ClientId id : m_session.clients()) {
				if (desc->target == RpcTarget::All || id != caller) {
					m_session.send(id, channelOf(*desc), packet);
					++m_stats.relayed;
				}
			}
		}
	}
	dispatch(*desc, msg, caller);
	return true;
}

bool RpcServer::call(uint16_t rpcId, NetId netId, const std::vector<RpcArg> &args, Tick tick)
{
	const RpcDesc *desc = m_table.find(rpcId);
	if (!desc || !RpcTable::argsMatch(*desc, args)) {
		return false;
	}
	ClientId owner = kServerClientId;
	if (netId != kInvalidNetId && (!m_owner || !m_owner(netId, owner))) {
		++m_stats.droppedNoObject;
		return false;
	}
	RpcMsg msg;
	msg.netId = netId;
	msg.rpcId = rpcId;
	msg.tick = tick;
	msg.args = args;
	std::vector<uint8_t> packet;
	if (!appendMessage(packet, msg)) {
		return false;
	}
	switch (desc->target) {
		case RpcTarget::Server:
			dispatch(*desc, msg, kServerClientId);
			return true;
		case RpcTarget::Owner:
			if (netId == kInvalidNetId) {
				return false;
			}
			if (owner == kServerClientId) {
				dispatch(*desc, msg, kServerClientId);
				return true;
			}
			if (!m_session.send(owner, channelOf(*desc), packet)) {
				return false;
			}
			++m_stats.sent;
			return true;
		case RpcTarget::All:
		case RpcTarget::Others:
			for (ClientId id : m_session.clients()) {
				if (m_session.send(id, channelOf(*desc), packet)) {
					++m_stats.sent;
				}
			}
			if (desc->target == RpcTarget::All) {
				dispatch(*desc, msg, kServerClientId);
			}
			return true;
	}
	return false;
}

bool RpcServer::call(const std::string &name, NetId netId, const std::vector<RpcArg> &args, Tick tick)
{
	const int id = m_table.idOf(name);
	return id >= 0 && call(uint16_t(id), netId, args, tick);
}

bool RpcServer::callClient(ClientId client, uint16_t rpcId, NetId netId, const std::vector<RpcArg> &args, Tick tick)
{
	const RpcDesc *desc = m_table.find(rpcId);
	std::vector<uint8_t> packet;
	if (!desc || !RpcTable::argsMatch(*desc, args) || !makeRpcPacket(rpcId, netId, tick, args, packet)) {
		return false;
	}
	if (!m_session.send(client, channelOf(*desc), packet)) {
		return false;
	}
	++m_stats.sent;
	return true;
}

const RpcStats &RpcServer::stats() const
{
	return m_stats;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name RpcClient
 * \{ */

RpcClient::RpcClient(ClientSession &session, const RpcTable &table, const RpcOwnerLookup &owner)
    : m_session(session), m_table(table), m_owner(owner)
{
}

bool RpcClient::call(uint16_t rpcId, NetId netId, const std::vector<RpcArg> &args, Tick tick)
{
	const RpcDesc *desc = m_table.find(rpcId);
	if (!desc) {
		++m_stats.unknownId;
		return false;
	}
	if (desc->target == RpcTarget::Owner) {
		++m_stats.refusedTarget;
		return false;
	}
	if (!RpcTable::argsMatch(*desc, args)) {
		++m_stats.refusedArgs;
		return false;
	}
	if (desc->requireOwner) {
		ClientId owner = kServerClientId;
		if (netId == kInvalidNetId || !m_owner || !m_owner(netId, owner) || owner != m_session.clientId()) {
			++m_stats.refusedOwner;
			return false;
		}
	}
	std::vector<uint8_t> packet;
	if (!makeRpcPacket(rpcId, netId, tick, args, packet)) {
		return false;
	}
	if (!m_session.send(desc->reliable ? Channel::Rpc : Channel::Input, packet)) {
		return false;
	}
	++m_stats.sent;
	return true;
}

bool RpcClient::call(const std::string &name, NetId netId, const std::vector<RpcArg> &args, Tick tick)
{
	const int id = m_table.idOf(name);
	if (id < 0) {
		++m_stats.unknownId;
		return false;
	}
	return call(uint16_t(id), netId, args, tick);
}

bool RpcClient::handleEvent(const SessionEvent &event)
{
	if (!isRpcEvent(event) && !(event.type == SessionEvent::Type::Message &&
	                              event.messageType == uint8_t(MessageType::RpcFrom))) {
		return false;
	}
	++m_stats.received;
	RpcMsg msg;
	ClientId caller = kServerClientId;
	bool decoded;
	if (event.messageType == uint8_t(MessageType::RpcFrom)) {
		RpcFromMsg from;
		RawMessage raw;
		raw.type = event.messageType;
		raw.body = event.body.data();
		raw.size = event.body.size();
		decoded = decodeMessage(raw, from);
		caller = from.fromClient;
		msg = std::move(from.rpc);
	}
	else {
		decoded = decodeRpcEvent(event, msg);
	}
	if (!decoded) {
		++m_stats.invalid;
		return true;
	}
	const RpcDesc *desc = m_table.find(msg.rpcId);
	if (!desc) {
		++m_stats.unknownId;
		return true;
	}
	if (desc->target == RpcTarget::Server) {
		++m_stats.refusedTarget;
		return true;
	}
	if (!RpcTable::argsMatch(*desc, msg.args)) {
		++m_stats.refusedArgs;
		return true;
	}
	if (msg.netId != kInvalidNetId) {
		ClientId owner = kServerClientId;
		if (!m_owner || !m_owner(msg.netId, owner)) {
			++m_stats.droppedNoObject;
			return true;
		}
	}
	if (desc->handler) {
		RpcCall call;
		call.desc = desc;
		call.rpcId = msg.rpcId;
		call.caller = caller;
		call.netId = msg.netId;
		call.tick = msg.tick;
		call.args = &msg.args;
		++m_stats.dispatched;
		desc->handler(call);
	}
	return true;
}

const RpcStats &RpcClient::stats() const
{
	return m_stats;
}

/** \} */

}  // namespace net
