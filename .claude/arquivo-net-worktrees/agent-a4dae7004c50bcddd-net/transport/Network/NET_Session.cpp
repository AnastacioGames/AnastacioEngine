#include "NET_Session.h"

#include "NET_SessionCodec.h"

#include <algorithm>

namespace net {

namespace {

/* Elapsed ms with wrap-around. */
inline uint32_t elapsed(uint32_t now, uint32_t since)
{
	return now - since;
}

inline bool isServerBound(uint8_t type)
{
	switch (MessageType(type)) {
		case MessageType::Welcome:
		case MessageType::Reject:
		case MessageType::ClientInfo:
		case MessageType::SceneChange:
		case MessageType::Spawn:
		case MessageType::Despawn:
		case MessageType::Ownership:
		case MessageType::Snapshot:
			return false;
		default:
			return true;
	}
}

inline bool isKnownType(uint8_t type)
{
	return type >= uint8_t(MessageType::Hello) && type <= uint8_t(MessageType::Chat);
}

bool fitsChannel(const SessionLimits &limits, Channel channel, size_t size)
{
	return size <= (channelReliable(channel) ? limits.maxReliableMessage : limits.maxUnreliablePayload);
}

}  // namespace

/* ------------------------------------------------------------------------ */
/* ServerSession                                                            */
/* ------------------------------------------------------------------------ */

ServerSession::ServerSession(ITransport &transport, const SessionConfig &config)
    : m_transport(transport), m_config(config)
{
	m_config.maxClients = std::min<uint16_t>(std::max<uint16_t>(m_config.maxClients, 1),
	                                         m_config.limits.maxClientsCap);
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
	/* Pending handshakes also hold transport peers. */
	const int peers = int(m_config.maxClients) + m_config.limits.maxPendingConnections;
	m_running = m_transport.listen(port, peers);
	return m_running;
}

void ServerSession::stop()
{
	if (!m_running) {
		return;
	}
	std::vector<SessionEvent> ignored;
	while (!m_conns.empty()) {
		closeConn(m_conns.begin()->first, true, DisconnectReason::ServerShutdown, true, ignored);
	}
	m_slots.clear();
	m_running = false;
}

void ServerSession::update(uint32_t nowMs, std::vector<SessionEvent> &events)
{
	m_now = nowMs;
	if (!m_running) {
		return;
	}
	std::vector<TransportEvent> tevents;
	m_transport.poll(tevents);

	for (TransportEvent &te : tevents) {
		switch (te.type) {
			case TransportEvent::Type::Connected: {
				if (pendingCount() >= m_config.limits.maxPendingConnections) {
					m_transport.disconnect(te.peer);
					break;
				}
				Conn conn;
				conn.peer = te.peer;
				conn.openedMs = conn.lastRecvMs = conn.windowStartMs = conn.lastPingMs = nowMs;
				m_conns[te.peer] = conn;
				break;
			}
			case TransportEvent::Type::Disconnected: {
				auto it = m_conns.find(te.peer);
				if (it != m_conns.end()) {
					/* Lost connection: keep the slot for reconnection. */
					closeConn(te.peer, false, DisconnectReason::Timeout, false, events);
				}
				break;
			}
			case TransportEvent::Type::Received: {
				auto it = m_conns.find(te.peer);
				if (it != m_conns.end() && !it->second.dropPending) {
					onReceived(it->second, te.channel, te.data, events);
				}
				break;
			}
		}
	}

	/* Timeouts, pings and deferred drops. */
	std::vector<PeerId> toClose;
	for (auto &kv : m_conns) {
		Conn &c = kv.second;
		if (c.dropPending) {
			toClose.push_back(kv.first);
			continue;
		}
		if (!c.active) {
			if (elapsed(nowMs, c.openedMs) >= m_config.limits.handshakeTimeoutMs) {
				c.dropPending = true;
				c.dropReason = DisconnectReason::Timeout;
				toClose.push_back(kv.first);
			}
			continue;
		}
		if (elapsed(nowMs, c.lastRecvMs) >= m_config.limits.connectionTimeoutMs) {
			c.dropPending = true;
			c.dropReason = DisconnectReason::Timeout;
			toClose.push_back(kv.first);
			continue;
		}
		if (m_config.pingIntervalMs && elapsed(nowMs, c.lastPingMs) >= m_config.pingIntervalMs) {
			c.lastPingMs = nowMs;
			std::vector<uint8_t> pkt;
			codec::encode(pkt, codec::PingMsg{++c.pingSeq, nowMs});
			m_transport.send(c.peer, Channel::Snapshot, pkt.data(), pkt.size());
		}
	}
	for (PeerId peer : toClose) {
		Conn &c = m_conns[peer];
		/* A timed-out active client keeps its slot; quit/kick/violation release it. */
		const bool release = !(c.active && c.dropReason == DisconnectReason::Timeout);
		const bool notify = c.active && c.dropReason != DisconnectReason::Quit;
		closeConn(peer, notify, c.dropReason, release, events);
	}

	/* Expire reconnection slots. */
	for (auto it = m_slots.begin(); it != m_slots.end();) {
		if (!it->second.connected &&
		    elapsed(nowMs, it->second.droppedMs) >= m_config.limits.reconnectWindowMs) {
			SessionEvent e{SessionEvent::Type::ClientLeft};
			e.client = it->first;
			e.reason = uint8_t(DisconnectReason::Timeout);
			events.push_back(std::move(e));
			it = m_slots.erase(it);
		}
		else {
			++it;
		}
	}
}

void ServerSession::onReceived(Conn &conn, Channel channel, const std::vector<uint8_t> &data,
                               std::vector<SessionEvent> &events)
{
	conn.lastRecvMs = m_now;
	const SessionLimits &lim = m_config.limits;

	if (!fitsChannel(lim, channel, data.size())) {
		addViolation(conn);
		return;
	}
	if (elapsed(m_now, conn.windowStartMs) >= 1000) {
		conn.windowStartMs = m_now;
		conn.windowBytes = 0;
		conn.windowRpcs = 0;
	}
	if (conn.windowBytes + data.size() > lim.maxBytesPerSecond) {
		addViolation(conn);
		return;
	}
	conn.windowBytes += uint32_t(data.size());

	codec::PacketReader reader(data.data(), data.size());
	codec::MessageView msg;
	int count = 0;
	while (!conn.dropPending && reader.next(msg)) {
		if (++count > lim.maxMessagesPerPacket) {
			addViolation(conn);
			return;
		}
		if (!conn.active) {
			if (msg.type == uint8_t(MessageType::Hello)) {
				onHello(conn, msg.body, msg.size, events);
			}
			else {
				addViolation(conn);
			}
			continue;
		}
		if (!isKnownType(msg.type)) {
			continue; /* forward compatibility: skipped */
		}
		switch (MessageType(msg.type)) {
			case MessageType::Hello:
				addViolation(conn);
				break;
			case MessageType::Disconnect:
				conn.dropPending = true;
				conn.dropReason = DisconnectReason::Quit;
				break;
			case MessageType::Ping: {
				codec::PingMsg ping;
				if (!codec::decode(msg.body, msg.size, ping)) {
					addViolation(conn);
					break;
				}
				std::vector<uint8_t> pkt;
				codec::encode(pkt, codec::PongMsg{ping.seq, ping.senderTimeMs, m_serverTick});
				m_transport.send(conn.peer, Channel::Snapshot, pkt.data(), pkt.size());
				break;
			}
			case MessageType::Pong: {
				codec::PongMsg pong;
				if (!codec::decode(msg.body, msg.size, pong)) {
					addViolation(conn);
					break;
				}
				conn.rtt.addSample(float(elapsed(m_now, pong.echoTimeMs)));
				break;
			}
			default:
				if (!isServerBound(msg.type)) {
					addViolation(conn);
					break;
				}
				if (MessageType(msg.type) == MessageType::Rpc && ++conn.windowRpcs > lim.maxRpcPerSecond) {
					addViolation(conn);
					break;
				}
				SessionEvent e{SessionEvent::Type::Message};
				e.client = conn.client;
				e.channel = channel;
				e.messageType = msg.type;
				e.body.assign(msg.body, msg.body + msg.size);
				events.push_back(std::move(e));
				break;
		}
	}
	if (reader.error()) {
		addViolation(conn);
	}
}

void ServerSession::onHello(Conn &conn, const uint8_t *body, size_t size, std::vector<SessionEvent> &events)
{
	codec::HelloMsg hello;
	if (!codec::decode(body, size, hello)) {
		addViolation(conn);
		reject(conn, RejectReason::VersionMismatch, "malformed hello");
		return;
	}
	if (hello.magic != kProtocolMagic || hello.protocolVersion != kProtocolVersion) {
		reject(conn, RejectReason::VersionMismatch, "protocol version");
		return;
	}
	if (hello.gameId != m_config.gameId || hello.gameVersion != m_config.gameVersion) {
		reject(conn, RejectReason::VersionMismatch, "game version");
		return;
	}
	if (hello.sceneHash != m_config.sceneHash) {
		reject(conn, RejectReason::SceneMismatch, "scene");
		return;
	}

	ClientId id = 0;
	bool reconnected = false;
	if (hello.token != 0) {
		for (auto &kv : m_slots) {
			if (kv.second.token == hello.token) {
				if (kv.second.connected) {
					reject(conn, RejectReason::BadToken, "token in use");
					return;
				}
				id = kv.first;
				reconnected = true;
				break;
			}
		}
	}
	if (!reconnected) {
		if (m_slots.size() >= m_config.maxClients) {
			reject(conn, RejectReason::ServerFull, "server full");
			return;
		}
		if (!m_config.acceptNewClients) {
			reject(conn, RejectReason::GameInProgress, "game in progress");
			return;
		}
		for (ClientId c = 1; c <= m_config.maxClients; c++) {
			if (!m_slots.count(c)) {
				id = c;
				break;
			}
		}
	}

	Slot &slot = m_slots[id];
	slot.name = hello.playerName;
	slot.token = hello.token;
	slot.connected = true;
	slot.peer = conn.peer;
	conn.active = true;
	conn.client = id;

	codec::WelcomeMsg w;
	w.clientId = id;
	w.tickRate = m_config.tickRate;
	w.snapshotRate = m_config.snapshotRate;
	w.serverTick = m_serverTick;
	w.maxClients = m_config.maxClients;
	w.sceneName = m_config.sceneName;
	std::vector<uint8_t> pkt;
	codec::encode(pkt, w);
	m_transport.send(conn.peer, Channel::Control, pkt.data(), pkt.size());

	SessionEvent e{reconnected ? SessionEvent::Type::ClientReconnected : SessionEvent::Type::ClientJoined};
	e.client = id;
	e.detail = hello.playerName;
	events.push_back(std::move(e));
}

void ServerSession::reject(Conn &conn, RejectReason reason, const char *detail)
{
	std::vector<uint8_t> pkt;
	codec::encode(pkt, codec::RejectMsg{reason, detail});
	m_transport.send(conn.peer, Channel::Control, pkt.data(), pkt.size());
	conn.dropPending = true;
	conn.dropReason = DisconnectReason::Kicked;
}

void ServerSession::addViolation(Conn &conn)
{
	const SessionLimits &lim = m_config.limits;
	conn.violations.push_back(m_now);
	while (!conn.violations.empty() && elapsed(m_now, conn.violations.front()) >= lim.violationWindowMs) {
		conn.violations.pop_front();
	}
	if (int(conn.violations.size()) >= lim.violationsToKick) {
		conn.dropPending = true;
		conn.dropReason = DisconnectReason::ProtocolViolation;
	}
}

void ServerSession::closeConn(PeerId peer, bool sendDisconnect, DisconnectReason reason, bool releaseSlot,
                              std::vector<SessionEvent> &events)
{
	auto it = m_conns.find(peer);
	if (it == m_conns.end()) {
		return;
	}
	const Conn conn = it->second;
	m_conns.erase(it);
	if (sendDisconnect) {
		std::vector<uint8_t> pkt;
		codec::encode(pkt, codec::DisconnectMsg{reason});
		m_transport.send(peer, Channel::Control, pkt.data(), pkt.size());
	}
	m_transport.disconnect(peer);

	if (!conn.active) {
		return;
	}
	auto sit = m_slots.find(conn.client);
	if (sit == m_slots.end()) {
		return;
	}
	if (releaseSlot || sit->second.token == 0) {
		m_slots.erase(sit);
		SessionEvent e{SessionEvent::Type::ClientLeft};
		e.client = conn.client;
		e.reason = uint8_t(reason);
		events.push_back(std::move(e));
	}
	else {
		sit->second.connected = false;
		sit->second.peer = 0;
		sit->second.droppedMs = m_now;
		SessionEvent e{SessionEvent::Type::ClientDropped};
		e.client = conn.client;
		e.reason = uint8_t(reason);
		events.push_back(std::move(e));
	}
}

ServerSession::Conn *ServerSession::connOf(ClientId client)
{
	auto sit = m_slots.find(client);
	if (sit == m_slots.end() || !sit->second.connected) {
		return nullptr;
	}
	auto it = m_conns.find(sit->second.peer);
	return it == m_conns.end() ? nullptr : &it->second;
}

const ServerSession::Conn *ServerSession::connOf(ClientId client) const
{
	return const_cast<ServerSession *>(this)->connOf(client);
}

bool ServerSession::send(ClientId client, Channel channel, const std::vector<uint8_t> &packet)
{
	Conn *c = connOf(client);
	if (!c || !fitsChannel(m_config.limits, channel, packet.size())) {
		return false;
	}
	m_transport.send(c->peer, channel, packet.data(), packet.size());
	return true;
}

bool ServerSession::sendMessage(ClientId client, Channel channel, MessageType type,
                                const std::vector<uint8_t> &body)
{
	std::vector<uint8_t> pkt;
	return codec::appendMessage(pkt, type, body.data(), body.size()) && send(client, channel, pkt);
}

void ServerSession::broadcast(Channel channel, const std::vector<uint8_t> &packet)
{
	for (ClientId c : connectedClients()) {
		send(c, channel, packet);
	}
}

void ServerSession::kick(ClientId client, DisconnectReason reason)
{
	Conn *c = connOf(client);
	if (c) {
		std::vector<SessionEvent> ignored;
		closeConn(c->peer, true, reason, true, ignored);
	}
}

std::vector<ClientId> ServerSession::connectedClients() const
{
	std::vector<ClientId> out;
	for (const auto &kv : m_slots) {
		if (kv.second.connected) {
			out.push_back(kv.first);
		}
	}
	return out;
}

bool ServerSession::isConnected(ClientId client) const
{
	return connOf(client) != nullptr;
}

std::string ServerSession::clientName(ClientId client) const
{
	auto it = m_slots.find(client);
	return it == m_slots.end() ? std::string() : it->second.name;
}

float ServerSession::rttMs(ClientId client) const
{
	const Conn *c = connOf(client);
	return c ? c->rtt.rttMs : 0.0f;
}

int ServerSession::violationCount(ClientId client) const
{
	const Conn *c = connOf(client);
	return c ? int(c->violations.size()) : 0;
}

int ServerSession::pendingCount() const
{
	int n = 0;
	for (const auto &kv : m_conns) {
		n += kv.second.active ? 0 : 1;
	}
	return n;
}

/* ------------------------------------------------------------------------ */
/* ClientSession                                                            */
/* ------------------------------------------------------------------------ */

ClientSession::ClientSession(ITransport &transport, const SessionConfig &config)
    : m_transport(transport), m_config(config)
{
}

ClientSession::~ClientSession()
{
	disconnect();
}

bool ClientSession::connect(const std::string &host, uint16_t port, uint32_t nowMs)
{
	if (m_state == State::Connecting || m_state == State::Handshaking || m_state == State::Connected) {
		return false;
	}
	m_now = m_connectMs = m_lastRecvMs = nowMs;
	m_welcome = WelcomeInfo();
	m_rtt = RttEstimator();
	m_peer = 0;
	if (!m_transport.connect(host, port)) {
		m_state = State::Disconnected;
		return false;
	}
	m_state = State::Connecting;
	return true;
}

void ClientSession::disconnect()
{
	if (m_state == State::Idle || m_state == State::Disconnected) {
		return;
	}
	std::vector<SessionEvent> ignored;
	finish(SessionEvent::Type::Disconnected, uint8_t(DisconnectReason::Quit), "", true, ignored);
}

void ClientSession::finish(SessionEvent::Type type, uint8_t reason, const std::string &detail, bool sendQuit,
                           std::vector<SessionEvent> &events)
{
	if (m_peer != 0) {
		if (sendQuit) {
			std::vector<uint8_t> pkt;
			codec::encode(pkt, codec::DisconnectMsg{DisconnectReason(reason)});
			m_transport.send(m_peer, Channel::Control, pkt.data(), pkt.size());
		}
		m_transport.disconnect(m_peer);
		m_peer = 0;
	}
	m_state = State::Disconnected;
	SessionEvent e{type};
	e.reason = reason;
	e.detail = detail;
	events.push_back(std::move(e));
}

void ClientSession::update(uint32_t nowMs, std::vector<SessionEvent> &events)
{
	m_now = nowMs;
	if (m_state == State::Idle || m_state == State::Disconnected) {
		/* Drain stale transport events (e.g. our own disconnect). */
		std::vector<TransportEvent> drain;
		m_transport.poll(drain);
		return;
	}
	std::vector<TransportEvent> tevents;
	m_transport.poll(tevents);
	for (TransportEvent &te : tevents) {
		if (m_state == State::Disconnected) {
			break;
		}
		switch (te.type) {
			case TransportEvent::Type::Connected: {
				if (m_state != State::Connecting) {
					break;
				}
				m_peer = te.peer;
				m_state = State::Handshaking;
				m_lastRecvMs = nowMs;
				codec::HelloMsg hello;
				hello.gameId = m_config.gameId;
				hello.gameVersion = m_config.gameVersion;
				hello.sceneHash = m_config.sceneHash;
				hello.playerName = m_config.playerName;
				hello.token = m_config.token;
				std::vector<uint8_t> pkt;
				codec::encode(pkt, hello);
				m_transport.send(m_peer, Channel::Control, pkt.data(), pkt.size());
				break;
			}
			case TransportEvent::Type::Disconnected:
				if (m_peer == 0 || te.peer == m_peer) {
					m_peer = 0;
					finish(SessionEvent::Type::Disconnected, uint8_t(DisconnectReason::Timeout),
					       "connection lost", false, events);
				}
				break;
			case TransportEvent::Type::Received:
				if (te.peer == m_peer) {
					m_lastRecvMs = nowMs;
					onReceived(te.channel, te.data, events);
				}
				break;
		}
	}
	if (m_state == State::Disconnected) {
		return;
	}

	if (m_state != State::Connected) {
		if (elapsed(nowMs, m_connectMs) >= m_config.limits.handshakeTimeoutMs) {
			finish(SessionEvent::Type::Disconnected, uint8_t(DisconnectReason::Timeout), "handshake timeout",
			       false, events);
		}
		return;
	}
	if (elapsed(nowMs, m_lastRecvMs) >= m_config.limits.connectionTimeoutMs) {
		finish(SessionEvent::Type::Disconnected, uint8_t(DisconnectReason::Timeout), "timeout", true, events);
		return;
	}
	if (m_config.pingIntervalMs && elapsed(nowMs, m_lastPingMs) >= m_config.pingIntervalMs) {
		m_lastPingMs = nowMs;
		std::vector<uint8_t> pkt;
		codec::encode(pkt, codec::PingMsg{++m_pingSeq, nowMs});
		m_transport.send(m_peer, Channel::Input, pkt.data(), pkt.size());
	}
}

void ClientSession::onReceived(Channel channel, const std::vector<uint8_t> &data,
                               std::vector<SessionEvent> &events)
{
	codec::PacketReader reader(data.data(), data.size());
	codec::MessageView msg;
	while (m_state != State::Disconnected && reader.next(msg)) {
		if (!isKnownType(msg.type)) {
			continue;
		}
		const MessageType type = MessageType(msg.type);
		if (m_state == State::Handshaking) {
			if (type == MessageType::Welcome) {
				codec::WelcomeMsg w;
				if (!codec::decode(msg.body, msg.size, w)) {
					finish(SessionEvent::Type::Disconnected, uint8_t(DisconnectReason::ProtocolViolation),
					       "malformed welcome", true, events);
					return;
				}
				m_welcome.clientId = w.clientId;
				m_welcome.tickRate = w.tickRate;
				m_welcome.snapshotRate = w.snapshotRate;
				m_welcome.maxClients = w.maxClients;
				m_welcome.sceneName = w.sceneName;
				m_pongServerTick = w.serverTick;
				m_pongRecvMs = m_now;
				m_lastPingMs = m_now - m_config.pingIntervalMs; /* ping right away */
				m_state = State::Connected;
				SessionEvent e{SessionEvent::Type::Connected};
				e.client = w.clientId;
				events.push_back(std::move(e));
			}
			else if (type == MessageType::Reject) {
				codec::RejectMsg r;
				codec::decode(msg.body, msg.size, r);
				finish(SessionEvent::Type::Rejected, uint8_t(r.reason), r.detail, false, events);
				return;
			}
			else if (type == MessageType::Disconnect) {
				codec::DisconnectMsg d;
				codec::decode(msg.body, msg.size, d);
				finish(SessionEvent::Type::Disconnected, uint8_t(d.reason), "", false, events);
				return;
			}
			/* Anything else before Welcome is ignored. */
			continue;
		}
		switch (type) {
			case MessageType::Disconnect: {
				codec::DisconnectMsg d;
				codec::decode(msg.body, msg.size, d);
				finish(SessionEvent::Type::Disconnected, uint8_t(d.reason), "", false, events);
				return;
			}
			case MessageType::Ping: {
				codec::PingMsg ping;
				if (codec::decode(msg.body, msg.size, ping)) {
					std::vector<uint8_t> pkt;
					codec::encode(pkt, codec::PongMsg{ping.seq, ping.senderTimeMs, estimatedServerTick(m_now)});
					m_transport.send(m_peer, Channel::Input, pkt.data(), pkt.size());
				}
				break;
			}
			case MessageType::Pong: {
				codec::PongMsg pong;
				if (codec::decode(msg.body, msg.size, pong)) {
					m_rtt.addSample(float(elapsed(m_now, pong.echoTimeMs)));
					m_pongServerTick = pong.serverTick;
					m_pongRecvMs = m_now;
				}
				break;
			}
			case MessageType::Hello:
			case MessageType::Welcome:
			case MessageType::Reject:
				break;
			default: {
				SessionEvent e{SessionEvent::Type::Message};
				e.client = 0;
				e.channel = channel;
				e.messageType = msg.type;
				e.body.assign(msg.body, msg.body + msg.size);
				events.push_back(std::move(e));
				break;
			}
		}
	}
}

Tick ClientSession::estimatedServerTick(uint32_t nowMs) const
{
	if (m_welcome.tickRate == 0) {
		return m_pongServerTick;
	}
	const float ms = float(elapsed(nowMs, m_pongRecvMs)) + m_rtt.rttMs * 0.5f;
	return m_pongServerTick + Tick(ms * float(m_welcome.tickRate) / 1000.0f);
}

bool ClientSession::send(Channel channel, const std::vector<uint8_t> &packet)
{
	if (m_state != State::Connected || !fitsChannel(m_config.limits, channel, packet.size())) {
		return false;
	}
	m_transport.send(m_peer, channel, packet.data(), packet.size());
	return true;
}

bool ClientSession::sendMessage(Channel channel, MessageType type, const std::vector<uint8_t> &body)
{
	std::vector<uint8_t> pkt;
	return codec::appendMessage(pkt, type, body.data(), body.size()) && send(channel, pkt);
}

}  // namespace net
