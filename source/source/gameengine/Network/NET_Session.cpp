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

/** \file gameengine/Network/NET_Session.cpp
 *  \ingroup network
 */

#include "NET_Session.h"

#include <algorithm>
#include <random>

namespace net {

/* -------------------------------------------------------------------- */
/** \name Helpers
 * \{ */

bool ViolationCounter::add(uint64_t nowMs)
{
	m_times.push_back(nowMs);
	while (!m_times.empty() && nowMs - m_times.front() >= uint64_t(kViolationWindowMs)) {
		m_times.pop_front();
	}
	return m_times.size() >= size_t(kMaxViolations);
}

size_t ViolationCounter::count() const
{
	return m_times.size();
}

void RttEstimator::addSample(float rttMs)
{
	if (rttMs < 0.0f) {
		return;
	}
	if (!m_hasSample) {
		m_rtt = rttMs;
		m_hasSample = true;
	}
	else {
		m_rtt += 0.1f * (rttMs - m_rtt);
	}
}

float RttEstimator::rttMs() const
{
	return m_rtt;
}

bool RttEstimator::hasSample() const
{
	return m_hasSample;
}

static SessionEvent makeMessageEvent(ClientId client, const RawMessage &raw, Channel channel)
{
	SessionEvent ev;
	ev.type = SessionEvent::Type::Message;
	ev.client = client;
	ev.messageType = raw.type;
	ev.channel = channel;
	ev.body.assign(raw.body, raw.body + raw.size);
	return ev;
}

/// Messages a server may send.
static bool isServerToClient(MessageType type)
{
	switch (type) {
		case MessageType::Welcome:
		case MessageType::Reject:
		case MessageType::ClientInfo:
		case MessageType::SceneChange:
		case MessageType::Spawn:
		case MessageType::Despawn:
		case MessageType::Ownership:
		case MessageType::Snapshot:
			return true;
		default:
			return false;
	}
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Server
 * \{ */

ServerSession::ServerSession(ITransport &transport, const ServerConfig &config)
	:m_transport(transport),
	m_config(config)
{
	m_config.maxClients = std::min(std::max(m_config.maxClients, 1), kMaxClients);
}

ServerSession::~ServerSession()
{
	stop();
}

bool ServerSession::start(uint16_t port)
{
	if (m_running) {
		return false;
	}
	m_running = m_transport.listen(port, m_config.maxClients + kMaxPendingConnections);
	return m_running;
}

void ServerSession::stop()
{
	if (!m_running) {
		return;
	}
	DisconnectMsg msg;
	msg.reason = DisconnectReason::ServerShutdown;
	const std::vector<uint8_t> packet = makePacket(msg);
	for (const auto &pair : m_connections) {
		sendTo(pair.first, Channel::Control, packet);
		m_transport.disconnect(pair.first);
	}
	m_connections.clear();
	m_clients.clear();
	m_slots.clear();
	m_transport.shutdown();
	m_running = false;
}

void ServerSession::sendTo(PeerId peer, Channel channel, const std::vector<uint8_t> &packet)
{
	m_transport.send(peer, channel, packet.data(), packet.size());
}

void ServerSession::update(uint64_t nowMs, Tick serverTick, std::vector<SessionEvent> &events)
{
	m_lastNowMs = nowMs;
	std::vector<TransportEvent> incoming;
	m_transport.poll(incoming);

	for (TransportEvent &ev : incoming) {
		switch (ev.type) {
			case TransportEvent::Type::Connected: {
				if (pendingCount() >= size_t(kMaxPendingConnections)) {
					m_transport.disconnect(ev.peer);
					break;
				}
				Connection conn;
				conn.peer = ev.peer;
				conn.connectedAtMs = nowMs;
				conn.lastReceiveMs = nowMs;
				conn.byteWindowStartMs = nowMs;
				conn.rpcWindowStartMs = nowMs;
				m_connections[ev.peer] = std::move(conn);
				break;
			}
			case TransportEvent::Type::Disconnected:
				if (m_connections.count(ev.peer)) {
					closeConnection(ev.peer, DisconnectReason::Timeout, false, true, nowMs, events);
				}
				break;
			case TransportEvent::Type::Received: {
				const auto it = m_connections.find(ev.peer);
				if (it != m_connections.end()) {
					handleReceive(it->second, ev.channel, ev.data, nowMs, serverTick, events);
				}
				break;
			}
		}
	}

	// Timeouts and pings.
	std::vector<PeerId> pendingTimeout, timedOut;
	for (auto &pair : m_connections) {
		Connection &conn = pair.second;
		if (!conn.accepted) {
			if (nowMs - conn.connectedAtMs >= uint64_t(kPendingTimeoutMs)) {
				pendingTimeout.push_back(pair.first);
			}
			continue;
		}
		if (nowMs - conn.lastReceiveMs >= uint64_t(kConnectionTimeoutMs)) {
			timedOut.push_back(pair.first);
			continue;
		}
		if (nowMs - conn.lastPingMs >= m_config.pingIntervalMs) {
			conn.lastPingMs = nowMs;
			PingMsg ping;
			ping.seq = ++conn.pingSeq;
			ping.senderTimeMs = uint32_t(nowMs);
			sendTo(conn.peer, Channel::Snapshot, makePacket(ping));
		}
	}
	for (PeerId peer : pendingTimeout) {
		m_connections.erase(peer);
		m_transport.disconnect(peer);
	}
	for (PeerId peer : timedOut) {
		closeConnection(peer, DisconnectReason::Timeout, true, true, nowMs, events);
	}

	// Expired reconnection slots.
	for (auto it = m_slots.begin(); it != m_slots.end();) {
		if (nowMs >= it->expireMs) {
			SessionEvent ev;
			ev.type = SessionEvent::Type::ClientExpired;
			ev.client = it->id;
			ev.text = it->name;
			events.push_back(std::move(ev));
			it = m_slots.erase(it);
		}
		else {
			++it;
		}
	}
}

void ServerSession::handleReceive(Connection &conn, Channel channel, const std::vector<uint8_t> &data,
                                  uint64_t nowMs, Tick serverTick, std::vector<SessionEvent> &events)
{
	const PeerId peer = conn.peer;
	conn.lastReceiveMs = nowMs;

	// Byte rate limit (1 s window).
	if (nowMs - conn.byteWindowStartMs >= 1000) {
		conn.byteWindowStartMs = nowMs;
		conn.byteWindowCount = 0;
	}
	conn.byteWindowCount += data.size();
	if (conn.byteWindowCount > kMaxBytesPerSecond ||
	    (!isReliableChannel(channel) && !m_transport.reliableAll() && data.size() > kMaxUnreliablePayload) ||
	    data.size() > kMaxReliableMessage) {
		violation(conn, nowMs, events);
		return;
	}

	PacketReader reader(data.data(), data.size());
	RawMessage raw;
	while (reader.next(raw)) {
		// The connection may have been closed by the previous message.
		const auto it = m_connections.find(peer);
		if (it == m_connections.end()) {
			return;
		}
		Connection &c = it->second;

		if (!isKnownMessageType(raw.type)) {
			continue;
		}
		const MessageType type = MessageType(raw.type);

		if (!c.accepted) {
			if (type == MessageType::Hello) {
				handleHello(c, raw, nowMs, serverTick, events);
			}
			else if (!violation(c, nowMs, events)) {
				return;
			}
			continue;
		}

		const ClientId id = c.state.id;
		bool ok = true;
		switch (type) {
			case MessageType::Ping: {
				PingMsg ping;
				ok = decodeMessage(raw, ping);
				if (ok) {
					PongMsg pong;
					pong.seq = ping.seq;
					pong.echoTimeMs = ping.senderTimeMs;
					pong.serverTick = serverTick;
					sendTo(peer, Channel::Snapshot, makePacket(pong));
				}
				break;
			}
			case MessageType::Pong: {
				PongMsg pong;
				ok = decodeMessage(raw, pong);
				if (ok) {
					c.state.rtt.addSample(float(uint32_t(nowMs) - pong.echoTimeMs));
				}
				break;
			}
			case MessageType::Disconnect: {
				DisconnectMsg msg;
				ok = decodeMessage(raw, msg);
				if (ok) {
					closeConnection(peer, DisconnectReason::Quit, false, false, nowMs, events);
					return;
				}
				break;
			}
			case MessageType::SceneLoaded: {
				SceneLoadedMsg msg;
				ok = decodeMessage(raw, msg);
				if (ok && msg.sceneHash == m_config.sceneHash && !c.state.ready) {
					c.state.ready = true;
					SessionEvent ev;
					ev.type = SessionEvent::Type::ClientReady;
					ev.client = id;
					events.push_back(std::move(ev));
				}
				break;
			}
			case MessageType::Rpc: {
				if (nowMs - c.rpcWindowStartMs >= 1000) {
					c.rpcWindowStartMs = nowMs;
					c.rpcWindowCount = 0;
				}
				if (++c.rpcWindowCount > kMaxRpcPerSecond) {
					ok = false;
					break;
				}
				events.push_back(makeMessageEvent(id, raw, channel));
				break;
			}
			case MessageType::Hello:
				ok = false;
				break;
			default:
				if (isServerToClient(type)) {
					ok = false;
				}
				else {
					events.push_back(makeMessageEvent(id, raw, channel));
				}
				break;
		}
		if (!ok && !violation(c, nowMs, events)) {
			return;
		}
	}
	if (!reader.ok()) {
		const auto it = m_connections.find(peer);
		if (it != m_connections.end()) {
			violation(it->second, nowMs, events);
		}
	}
}

void ServerSession::handleHello(Connection &conn, const RawMessage &raw, uint64_t nowMs, Tick serverTick,
                                std::vector<SessionEvent> &events)
{
	HelloMsg hello;
	if (!decodeMessage(raw, hello)) {
		violation(conn, nowMs, events);
		return;
	}
	if (hello.protocolVersion != kProtocolVersion || hello.gameId != m_config.gameId ||
	    hello.gameVersion != m_config.gameVersion) {
		reject(conn, RejectReason::VersionMismatch, "");
		return;
	}
	if (hello.token != 0 && std::find(m_banned.begin(), m_banned.end(), hello.token) != m_banned.end()) {
		reject(conn, RejectReason::Banned, "");
		return;
	}
	if (hello.sceneHash != m_config.sceneHash) {
		reject(conn, RejectReason::SceneMismatch, m_config.sceneName);
		return;
	}
	if (hello.token != 0) {
		for (const auto &pair : m_connections) {
			if (pair.second.accepted && pair.second.state.token == hello.token) {
				reject(conn, RejectReason::BadToken, "");
				return;
			}
		}
	}

	ClientId id = 0;
	bool reconnected = false;
	if (hello.token != 0) {
		for (auto it = m_slots.begin(); it != m_slots.end(); ++it) {
			if (it->token == hello.token) {
				id = it->id;
				reconnected = true;
				m_slots.erase(it);
				break;
			}
		}
	}
	if (!reconnected) {
		if (m_clients.size() + m_slots.size() >= size_t(m_config.maxClients)) {
			reject(conn, RejectReason::ServerFull, "");
			return;
		}
		if (m_gameStarted && !m_config.allowLateJoin) {
			reject(conn, RejectReason::GameInProgress, "");
			return;
		}
		id = allocateClientId();
	}

	conn.accepted = true;
	conn.lastPingMs = nowMs;
	conn.state.id = id;
	conn.state.name = hello.playerName;
	conn.state.token = hello.token;
	m_clients[id] = conn.peer;

	WelcomeMsg welcome;
	welcome.clientId = id;
	welcome.tickRate = m_config.tickRate;
	welcome.snapshotRate = m_config.snapshotRate;
	welcome.serverTick = serverTick;
	welcome.maxClients = uint16_t(m_config.maxClients);
	welcome.sceneName = m_config.sceneName;
	sendTo(conn.peer, Channel::Control, makePacket(welcome));

	// Everyone already here, to the new client.
	for (const auto &pair : m_connections) {
		const Connection &other = pair.second;
		if (!other.accepted || other.peer == conn.peer) {
			continue;
		}
		ClientInfoMsg info;
		info.clientId = other.state.id;
		info.name = other.state.name;
		info.flags = uint8_t(CLIENT_CONNECTED | (other.state.ready ? CLIENT_READY : 0));
		sendTo(conn.peer, Channel::Control, makePacket(info));
	}
	// The new client, to everyone (itself included).
	ClientInfoMsg info;
	info.clientId = id;
	info.name = hello.playerName;
	info.flags = CLIENT_CONNECTED;
	broadcast(Channel::Control, makePacket(info));

	SceneChangeMsg scene;
	scene.sceneName = m_config.sceneName;
	scene.sceneHash = m_config.sceneHash;
	sendTo(conn.peer, Channel::Control, makePacket(scene));

	SessionEvent ev;
	ev.type = SessionEvent::Type::ClientJoined;
	ev.client = id;
	ev.text = hello.playerName;
	ev.reconnected = reconnected;
	events.push_back(std::move(ev));
}

void ServerSession::reject(Connection &conn, RejectReason reason, const std::string &detail)
{
	RejectMsg msg;
	msg.reason = reason;
	msg.detail = detail.substr(0, kMaxStringBytes);
	const PeerId peer = conn.peer;
	sendTo(peer, Channel::Control, makePacket(msg));
	m_connections.erase(peer);
	m_transport.disconnect(peer);
}

bool ServerSession::reportViolation(ClientId client, uint64_t nowMs, std::vector<SessionEvent> &events)
{
	const auto it = m_clients.find(client);
	if (it == m_clients.end()) {
		return false;
	}
	const auto conn = m_connections.find(it->second);
	if (conn == m_connections.end()) {
		return false;
	}
	return violation(conn->second, nowMs, events);
}

bool ServerSession::violation(Connection &conn, uint64_t nowMs, std::vector<SessionEvent> &events)
{
	if (!conn.violations.add(nowMs)) {
		return true;
	}
	closeConnection(conn.peer, DisconnectReason::ProtocolViolation, true, false, nowMs, events);
	return false;
}

void ServerSession::closeConnection(PeerId peer, DisconnectReason reason, bool sendMessage, bool keepSlot,
                                    uint64_t nowMs, std::vector<SessionEvent> &events)
{
	const auto it = m_connections.find(peer);
	if (it == m_connections.end()) {
		return;
	}
	const Connection conn = std::move(it->second);
	m_connections.erase(it);

	if (sendMessage) {
		DisconnectMsg msg;
		msg.reason = reason;
		sendTo(peer, Channel::Control, makePacket(msg));
	}
	m_transport.disconnect(peer);

	if (!conn.accepted) {
		return;
	}
	m_clients.erase(conn.state.id);
	if (keepSlot && conn.state.token != 0) {
		m_slots.push_back({conn.state.id, conn.state.token, conn.state.name, nowMs + uint64_t(kReconnectWindowMs)});
	}

	ClientInfoMsg info;
	info.clientId = conn.state.id;
	info.name = conn.state.name;
	info.flags = 0;
	broadcast(Channel::Control, makePacket(info));

	SessionEvent ev;
	ev.type = SessionEvent::Type::ClientLeft;
	ev.client = conn.state.id;
	ev.disconnectReason = reason;
	ev.reconnected = keepSlot && conn.state.token != 0;
	ev.text = conn.state.name;
	events.push_back(std::move(ev));
	// A client without token can never come back.
	if (!ev.reconnected && keepSlot) {
		SessionEvent expired;
		expired.type = SessionEvent::Type::ClientExpired;
		expired.client = conn.state.id;
		events.push_back(std::move(expired));
	}
}

ClientId ServerSession::allocateClientId() const
{
	for (int id = 1; id <= m_config.maxClients; ++id) {
		if (m_clients.count(ClientId(id))) {
			continue;
		}
		bool reserved = false;
		for (const ReconnectSlot &slot : m_slots) {
			reserved = reserved || slot.id == id;
		}
		if (!reserved) {
			return ClientId(id);
		}
	}
	return 0;
}

bool ServerSession::send(ClientId client, Channel channel, const std::vector<uint8_t> &packet)
{
	const auto it = m_clients.find(client);
	if (it == m_clients.end()) {
		return false;
	}
	sendTo(it->second, channel, packet);
	return true;
}

void ServerSession::broadcast(Channel channel, const std::vector<uint8_t> &packet, ClientId except, bool readyOnly)
{
	for (const auto &pair : m_connections) {
		const Connection &conn = pair.second;
		if (!conn.accepted || (except != 0 && conn.state.id == except) || (readyOnly && !conn.state.ready)) {
			continue;
		}
		sendTo(conn.peer, channel, packet);
	}
}

void ServerSession::kick(ClientId client, DisconnectReason reason)
{
	const auto it = m_clients.find(client);
	if (it == m_clients.end()) {
		return;
	}
	std::vector<SessionEvent> ignored;
	closeConnection(it->second, reason, true, false, m_lastNowMs, ignored);
}

void ServerSession::changeScene(const std::string &sceneName, uint64_t sceneHash)
{
	m_config.sceneName = sceneName;
	m_config.sceneHash = sceneHash;
	for (auto &pair : m_connections) {
		pair.second.state.ready = false;
	}
	SceneChangeMsg msg;
	msg.sceneName = sceneName;
	msg.sceneHash = sceneHash;
	broadcast(Channel::Control, makePacket(msg));
}

void ServerSession::setGameStarted(bool started)
{
	m_gameStarted = started;
}

void ServerSession::ban(uint64_t token)
{
	if (token != 0) {
		m_banned.push_back(token);
	}
}

std::vector<ClientId> ServerSession::clients() const
{
	std::vector<ClientId> ids;
	for (const auto &pair : m_clients) {
		ids.push_back(pair.first);
	}
	return ids;
}

const ServerSession::ClientState *ServerSession::client(ClientId id) const
{
	const auto it = m_clients.find(id);
	if (it == m_clients.end()) {
		return nullptr;
	}
	return &m_connections.at(it->second).state;
}

size_t ServerSession::pendingCount() const
{
	size_t n = 0;
	for (const auto &pair : m_connections) {
		n += pair.second.accepted ? 0 : 1;
	}
	return n;
}

const ServerConfig &ServerSession::config() const
{
	return m_config;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Client
 * \{ */

ClientSession::ClientSession(ITransport &transport, const ClientConfig &config)
	:m_transport(transport),
	m_config(config)
{
}

ClientSession::~ClientSession()
{
	// No Quit message: the server keeps the reconnection slot as for a lost connection.
	if (m_peer != 0) {
		m_transport.disconnect(m_peer);
	}
}

bool ClientSession::connect(const std::string &host, uint16_t port, uint64_t nowMs)
{
	if (m_state != State::Disconnected) {
		return false;
	}
	if (m_config.token == 0) {
		std::random_device rd;
		while (m_config.token == 0) {
			m_config.token = (uint64_t(rd()) << 32) ^ uint64_t(rd());
		}
	}
	if (!m_transport.connect(host, port)) {
		return false;
	}
	m_state = State::Connecting;
	m_stateSinceMs = nowMs;
	m_lastReceiveMs = nowMs;
	m_rtt = RttEstimator();
	m_players.clear();
	return true;
}

void ClientSession::disconnect()
{
	if (m_state == State::Disconnected) {
		return;
	}
	if (m_peer != 0) {
		DisconnectMsg msg;
		msg.reason = DisconnectReason::Quit;
		send(Channel::Control, makePacket(msg));
		m_transport.disconnect(m_peer);
	}
	m_peer = 0;
	m_state = State::Disconnected;
}

void ClientSession::lose(DisconnectReason reason, std::vector<SessionEvent> &events)
{
	if (m_peer != 0) {
		m_transport.disconnect(m_peer);
	}
	m_peer = 0;
	m_state = State::Disconnected;
	SessionEvent ev;
	ev.type = SessionEvent::Type::Disconnected;
	ev.disconnectReason = reason;
	events.push_back(std::move(ev));
}

void ClientSession::update(uint64_t nowMs, std::vector<SessionEvent> &events)
{
	std::vector<TransportEvent> incoming;
	m_transport.poll(incoming);
	for (TransportEvent &ev : incoming) {
		if (m_state == State::Disconnected) {
			break;
		}
		switch (ev.type) {
			case TransportEvent::Type::Connected: {
				if (m_state != State::Connecting) {
					break;
				}
				m_peer = ev.peer;
				m_state = State::Handshaking;
				m_lastReceiveMs = nowMs;
				HelloMsg hello;
				hello.gameId = m_config.gameId;
				hello.gameVersion = m_config.gameVersion;
				hello.sceneHash = m_config.sceneHash;
				hello.playerName = m_config.playerName.substr(0, kMaxStringBytes);
				hello.token = m_config.token;
				send(Channel::Control, makePacket(hello));
				break;
			}
			case TransportEvent::Type::Disconnected:
				if (m_peer == 0 || ev.peer == m_peer) {
					m_peer = 0;
					lose(DisconnectReason::Timeout, events);
				}
				break;
			case TransportEvent::Type::Received:
				if (ev.peer == m_peer) {
					m_lastReceiveMs = nowMs;
					handleReceive(ev.data, ev.channel, nowMs, events);
				}
				break;
		}
	}

	switch (m_state) {
		case State::Disconnected:
			break;
		case State::Connecting:
		case State::Handshaking:
			if (nowMs - m_stateSinceMs >= uint64_t(kPendingTimeoutMs)) {
				lose(DisconnectReason::Timeout, events);
			}
			break;
		case State::Connected:
			if (nowMs - m_lastReceiveMs >= uint64_t(kConnectionTimeoutMs)) {
				lose(DisconnectReason::Timeout, events);
				break;
			}
			if (nowMs - m_lastPingMs >= m_config.pingIntervalMs) {
				m_lastPingMs = nowMs;
				PingMsg ping;
				ping.seq = ++m_pingSeq;
				ping.senderTimeMs = uint32_t(nowMs);
				send(Channel::Input, makePacket(ping));
			}
			break;
	}
}

void ClientSession::handleReceive(const std::vector<uint8_t> &data, Channel channel, uint64_t nowMs,
                                  std::vector<SessionEvent> &events)
{
	PacketReader reader(data.data(), data.size());
	RawMessage raw;
	while (reader.next(raw) && m_state != State::Disconnected) {
		if (!isKnownMessageType(raw.type)) {
			continue;
		}
		const MessageType type = MessageType(raw.type);

		if (m_state == State::Handshaking) {
			if (type == MessageType::Welcome) {
				WelcomeMsg welcome;
				if (!decodeMessage(raw, welcome)) {
					continue;
				}
				m_state = State::Connected;
				m_clientId = welcome.clientId;
				m_tickRate = welcome.tickRate;
				m_snapshotRate = welcome.snapshotRate;
				m_sceneName = welcome.sceneName;
				m_baseTick = welcome.serverTick;
				m_baseTickMs = nowMs;
				m_lastPingMs = 0;
				SessionEvent ev;
				ev.type = SessionEvent::Type::Connected;
				ev.client = m_clientId;
				ev.text = welcome.sceneName;
				events.push_back(std::move(ev));
			}
			else if (type == MessageType::Reject) {
				RejectMsg reject;
				SessionEvent ev;
				ev.type = SessionEvent::Type::Rejected;
				if (decodeMessage(raw, reject)) {
					ev.rejectReason = reject.reason;
					ev.text = reject.detail;
				}
				events.push_back(std::move(ev));
				m_transport.disconnect(m_peer);
				m_peer = 0;
				m_state = State::Disconnected;
			}
			continue;
		}

		switch (type) {
			case MessageType::Ping: {
				PingMsg ping;
				if (decodeMessage(raw, ping)) {
					PongMsg pong;
					pong.seq = ping.seq;
					pong.echoTimeMs = ping.senderTimeMs;
					pong.serverTick = kNoTick;
					send(Channel::Input, makePacket(pong));
				}
				break;
			}
			case MessageType::Pong: {
				PongMsg pong;
				if (decodeMessage(raw, pong)) {
					const float rtt = float(uint32_t(nowMs) - pong.echoTimeMs);
					m_rtt.addSample(rtt);
					// The server tick was taken half a round trip ago.
					m_baseTick = pong.serverTick;
					m_baseTickMs = nowMs - std::min<uint64_t>(nowMs, uint64_t(m_rtt.rttMs() / 2.0f));
					++m_lastPong.count;
					m_lastPong.rttMs = rtt;
					m_lastPong.serverTick = pong.serverTick;
					m_lastPong.receivedMs = nowMs;
				}
				break;
			}
			case MessageType::Disconnect: {
				DisconnectMsg msg;
				const DisconnectReason reason = decodeMessage(raw, msg) ? msg.reason : DisconnectReason::Kicked;
				lose(reason, events);
				break;
			}
			case MessageType::ClientInfo: {
				ClientInfoMsg info;
				if (decodeMessage(raw, info)) {
					if (info.flags & CLIENT_CONNECTED) {
						m_players[info.clientId] = {info.name, info.flags};
					}
					else {
						m_players.erase(info.clientId);
					}
					SessionEvent ev;
					ev.type = SessionEvent::Type::PlayerInfo;
					ev.client = info.clientId;
					ev.text = info.name;
					ev.flags = info.flags;
					events.push_back(std::move(ev));
				}
				break;
			}
			case MessageType::SceneChange: {
				SceneChangeMsg msg;
				if (decodeMessage(raw, msg)) {
					m_sceneName = msg.sceneName;
					SessionEvent ev;
					ev.type = SessionEvent::Type::SceneChange;
					ev.text = msg.sceneName;
					ev.sceneHash = msg.sceneHash;
					events.push_back(std::move(ev));
				}
				break;
			}
			case MessageType::Welcome:
			case MessageType::Reject:
			case MessageType::Hello:
				break;
			default:
				events.push_back(makeMessageEvent(m_clientId, raw, channel));
				break;
		}
	}
}

void ClientSession::sceneLoaded(uint64_t sceneHash)
{
	SceneLoadedMsg msg;
	msg.sceneHash = sceneHash;
	send(Channel::Control, makePacket(msg));
}

bool ClientSession::send(Channel channel, const std::vector<uint8_t> &packet)
{
	if (m_peer == 0) {
		return false;
	}
	m_transport.send(m_peer, channel, packet.data(), packet.size());
	return true;
}

ClientSession::State ClientSession::state() const
{
	return m_state;
}

ClientId ClientSession::clientId() const
{
	return m_clientId;
}

uint64_t ClientSession::token() const
{
	return m_config.token;
}

uint16_t ClientSession::tickRate() const
{
	return m_tickRate;
}

uint16_t ClientSession::snapshotRate() const
{
	return m_snapshotRate;
}

const std::string &ClientSession::sceneName() const
{
	return m_sceneName;
}

float ClientSession::rttMs() const
{
	return m_rtt.rttMs();
}

Tick ClientSession::estimatedServerTick(uint64_t nowMs) const
{
	if (m_tickRate == 0 || nowMs < m_baseTickMs) {
		return m_baseTick;
	}
	return m_baseTick + Tick((nowMs - m_baseTickMs) * m_tickRate / 1000);
}

const std::map<ClientId, ClientSession::PlayerInfo> &ClientSession::players() const
{
	return m_players;
}

const ClientSession::PongSample &ClientSession::lastPong() const
{
	return m_lastPong;
}

/** \} */

}  // namespace net
