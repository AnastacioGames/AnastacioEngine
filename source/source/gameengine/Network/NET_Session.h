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

/** \file NET_Session.h
 *  \ingroup network
 *  \brief Server and client session state machines over ITransport (contract 4.2, 5 and 5.1).
 *
 * Handles handshake (Hello/Welcome/Reject), player list, scene handshake, Ping/Pong RTT,
 * timeouts, limits, violations and reconnection by token. Everything else (snapshots, input,
 * RPC, spawn) is passed through as Message events for the replication layer.
 * Time is given by the caller (milliseconds) so tests are deterministic.
 */

#ifndef __NET_SESSION_H__
#define __NET_SESSION_H__

#include "NET_ITransport.h"
#include "NET_Messages.h"
#include "NET_Types.h"

#include <deque>
#include <map>
#include <string>
#include <vector>

namespace net {

struct SessionEvent {
	enum class Type {
		/* Client side. */
		Connected,  // Welcome received
		Rejected,  // rejectReason
		Disconnected,  // disconnectReason
		PlayerInfo,  // client, text = name, flags
		SceneChange,  // text = scene name, sceneHash
		/* Server side. */
		ClientJoined,  // client, text = name, reconnected
		ClientReady,  // client loaded the current scene
		ClientLeft,  // client, disconnectReason; reconnect slot kept unless Quit/Kicked/violation
		ClientExpired,  // reconnect window closed: despawn or transfer its objects
		/* Both. */
		Message,  // messageType, channel, body (any message not handled by the session)
	};

	Type type = Type::Message;
	ClientId client = 0;
	DisconnectReason disconnectReason = DisconnectReason::Quit;
	RejectReason rejectReason = RejectReason::VersionMismatch;
	bool reconnected = false;
	uint8_t flags = 0;
	uint64_t sceneHash = 0;
	std::string text;
	uint8_t messageType = 0;
	Channel channel = Channel::Control;
	std::vector<uint8_t> body;
};

/// Builds a packet holding a single message.
template <class Msg, class... Extra>
std::vector<uint8_t> makePacket(const Msg &msg, const Extra &...extra)
{
	std::vector<uint8_t> packet;
	appendMessage(packet, msg, extra...);
	return packet;
}

/// Violation counter: kMaxViolations within kViolationWindowMs.
class ViolationCounter {
public:
	/// Returns true when the limit is reached.
	bool add(uint64_t nowMs);
	size_t count() const;

private:
	std::deque<uint64_t> m_times;
};

/// Exponential moving average of the round trip time (alpha 0.1, first sample taken as is).
class RttEstimator {
public:
	void addSample(float rttMs);
	float rttMs() const;
	bool hasSample() const;

private:
	float m_rtt = 0.0f;
	bool m_hasSample = false;
};

/* -------------------------------------------------------------------- */
/** \name Server
 * \{ */

struct ServerConfig {
	std::string gameId;
	uint32_t gameVersion = 0;
	std::string sceneName;
	uint64_t sceneHash = 0;
	uint16_t tickRate = 60;
	uint16_t snapshotRate = 20;
	int maxClients = 16;  // <= kMaxClients
	bool allowLateJoin = true;
	uint32_t pingIntervalMs = 1000;
};

class ServerSession {
public:
	struct ClientState {
		ClientId id = 0;
		std::string name;
		uint64_t token = 0;
		bool ready = false;
		RttEstimator rtt;
	};

	ServerSession(ITransport &transport, const ServerConfig &config);
	~ServerSession();

	/// Listens with room for maxClients plus pending handshakes.
	bool start(uint16_t port);
	/// Sends Disconnect(ServerShutdown) to everyone and shuts the transport down.
	void stop();

	void update(uint64_t nowMs, Tick serverTick, std::vector<SessionEvent> &events);

	bool send(ClientId client, Channel channel, const std::vector<uint8_t> &packet);
	void broadcast(Channel channel, const std::vector<uint8_t> &packet, ClientId except = 0, bool readyOnly = false);
	void kick(ClientId client, DisconnectReason reason = DisconnectReason::Kicked);
	/// Counts a protocol violation found by a layer above the session (bad RPC, bad Input...).
	/// Returns false when it closed the connection (events gets ClientLeft).
	bool reportViolation(ClientId client, uint64_t nowMs, std::vector<SessionEvent> &events);
	/// Sends SceneChange to everyone; clients become not ready until SceneLoaded.
	void changeScene(const std::string &sceneName, uint64_t sceneHash);
	void setGameStarted(bool started);
	void ban(uint64_t token);

	std::vector<ClientId> clients() const;
	const ClientState *client(ClientId id) const;
	size_t pendingCount() const;
	const ServerConfig &config() const;

private:
	struct Connection {
		PeerId peer = 0;
		bool accepted = false;
		ClientState state;
		uint64_t connectedAtMs = 0;
		uint64_t lastReceiveMs = 0;
		uint64_t lastPingMs = 0;
		uint32_t pingSeq = 0;
		uint64_t byteWindowStartMs = 0;
		size_t byteWindowCount = 0;
		uint64_t rpcWindowStartMs = 0;
		int rpcWindowCount = 0;
		ViolationCounter violations;
	};

	struct ReconnectSlot {
		ClientId id;
		uint64_t token;
		std::string name;
		uint64_t expireMs;
	};

	void handleReceive(Connection &conn, Channel channel, const std::vector<uint8_t> &data, uint64_t nowMs,
	                   Tick serverTick, std::vector<SessionEvent> &events);
	void handleHello(Connection &conn, const RawMessage &raw, uint64_t nowMs, Tick serverTick,
	                 std::vector<SessionEvent> &events);
	void reject(Connection &conn, RejectReason reason, const std::string &detail);
	/// Returns false when the connection was closed.
	bool violation(Connection &conn, uint64_t nowMs, std::vector<SessionEvent> &events);
	void closeConnection(PeerId peer, DisconnectReason reason, bool sendMessage, bool keepSlot, uint64_t nowMs,
	                     std::vector<SessionEvent> &events);
	ClientId allocateClientId() const;
	void sendTo(PeerId peer, Channel channel, const std::vector<uint8_t> &packet);

	ITransport &m_transport;
	ServerConfig m_config;
	std::map<PeerId, Connection> m_connections;
	std::map<ClientId, PeerId> m_clients;
	std::vector<ReconnectSlot> m_slots;
	std::vector<uint64_t> m_banned;
	bool m_gameStarted = false;
	bool m_running = false;
	uint64_t m_lastNowMs = 0;
};

/** \} */

/* -------------------------------------------------------------------- */
/** \name Client
 * \{ */

struct ClientConfig {
	std::string gameId;
	uint32_t gameVersion = 0;
	std::string playerName;
	uint64_t sceneHash = 0;
	/// Reconnection token; 0 = generate a random one on the first connect.
	uint64_t token = 0;
	uint32_t pingIntervalMs = 1000;
};

class ClientSession {
public:
	enum class State { Disconnected, Connecting, Handshaking, Connected };

	struct PlayerInfo {
		std::string name;
		uint8_t flags = 0;
	};

	ClientSession(ITransport &transport, const ClientConfig &config);
	/// Drops the connection without Quit (the server treats it as lost).
	~ClientSession();

	/// Also used to reconnect: the same token recovers the ClientId within 30 s.
	bool connect(const std::string &host, uint16_t port, uint64_t nowMs);
	/// Sends Disconnect(Quit).
	void disconnect();
	void update(uint64_t nowMs, std::vector<SessionEvent> &events);

	/// Tells the server the scene from SceneChange (or the initial one) is loaded.
	void sceneLoaded(uint64_t sceneHash);
	bool send(Channel channel, const std::vector<uint8_t> &packet);

	State state() const;
	ClientId clientId() const;
	uint64_t token() const;
	uint16_t tickRate() const;
	uint16_t snapshotRate() const;
	const std::string &sceneName() const;
	float rttMs() const;
	/// Server tick estimated from Welcome/Pong and the local clock.
	Tick estimatedServerTick(uint64_t nowMs) const;
	const std::map<ClientId, PlayerInfo> &players() const;

private:
	void handleReceive(const std::vector<uint8_t> &data, Channel channel, uint64_t nowMs,
	                   std::vector<SessionEvent> &events);
	void lose(DisconnectReason reason, std::vector<SessionEvent> &events);

	ITransport &m_transport;
	ClientConfig m_config;
	State m_state = State::Disconnected;
	PeerId m_peer = 0;
	ClientId m_clientId = 0;
	uint16_t m_tickRate = 0;
	uint16_t m_snapshotRate = 0;
	std::string m_sceneName;
	uint64_t m_stateSinceMs = 0;
	uint64_t m_lastReceiveMs = 0;
	uint64_t m_lastPingMs = 0;
	uint32_t m_pingSeq = 0;
	RttEstimator m_rtt;
	Tick m_baseTick = kNoTick;
	uint64_t m_baseTickMs = 0;
	std::map<ClientId, PlayerInfo> m_players;
};

/** \} */

}  // namespace net

#endif  // __NET_SESSION_H__
