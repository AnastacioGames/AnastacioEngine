/* Session layer over ITransport: handshake (Hello/Welcome/Reject), ping/RTT,
 * timeouts and limits (protocol section 4.2), reconnection by token (5.1) and
 * protocol violation accounting. Time is passed in by the caller (ms, any
 * origin, wraps) so tests are deterministic. Single-threaded. */

#pragma once

#include "NET_ITransport.h"
#include "NET_Types.h"

#include <deque>
#include <map>
#include <string>
#include <vector>

namespace net {

/* Limits of section 4.2. */
struct SessionLimits {
	size_t maxUnreliablePayload = 1200;
	size_t maxReliableMessage = 65536;
	int maxMessagesPerPacket = 64;
	int maxRpcPerSecond = 120;
	uint32_t maxBytesPerSecond = 64 * 1024;
	int maxPendingConnections = 16;
	uint32_t handshakeTimeoutMs = 5000;
	uint32_t connectionTimeoutMs = 10000;
	uint16_t maxClientsCap = 64;
	int violationsToKick = 10;
	uint32_t violationWindowMs = 10000;
	uint32_t reconnectWindowMs = 30000;
};

struct SessionConfig {
	/* Shared by both sides. */
	std::string gameId;
	uint32_t gameVersion = 0;
	uint64_t sceneHash = 0;
	uint32_t pingIntervalMs = 1000;
	SessionLimits limits;
	/* Server. */
	std::string sceneName;
	uint16_t tickRate = 60;
	uint16_t snapshotRate = 20;
	uint16_t maxClients = 8;  // clamped to limits.maxClientsCap
	bool acceptNewClients = true;  // false = GameInProgress for new players
	/* Client. */
	std::string playerName;
	uint64_t token = 0;  // 0 = no reconnection
};

struct SessionEvent {
	enum class Type {
		/* Client side. */
		Connected,     // Welcome received
		Rejected,      // reason = RejectReason
		Disconnected,  // reason = DisconnectReason (Timeout also for "connection lost")
		/* Server side. */
		ClientJoined,
		ClientReconnected,  // same token within the reconnection window
		ClientDropped,      // connection lost, slot kept for reconnection
		ClientLeft,         // slot released (quit, kick, or window expired)
		/* Both: any message not consumed by the session. */
		Message,
	} type;
	ClientId client = 0;
	uint8_t reason = 0;
	std::string detail;
	Channel channel = Channel::Control;
	uint8_t messageType = 0;
	std::vector<uint8_t> body;
};

/* RTT estimate shared by both sides: EMA with alpha 0.1, first sample taken as is. */
struct RttEstimator {
	float rttMs = 0.0f;
	bool valid = false;
	void addSample(float sampleMs)
	{
		rttMs = valid ? rttMs + 0.1f * (sampleMs - rttMs) : sampleMs;
		valid = true;
	}
};

class ServerSession {
public:
	ServerSession(ITransport &transport, const SessionConfig &config);
	~ServerSession();

	bool start(uint16_t port);
	void stop();  // sends Disconnect(ServerShutdown) to everyone
	void update(uint32_t nowMs, std::vector<SessionEvent> &events);

	void setServerTick(Tick tick)
	{
		m_serverTick = tick;
	}
	void setAcceptNewClients(bool accept)
	{
		m_config.acceptNewClients = accept;
	}

	/* `packet` is one or more messages (section 4.3). False if not connected or
	 * over the size limit for the channel. */
	bool send(ClientId client, Channel channel, const std::vector<uint8_t> &packet);
	bool sendMessage(ClientId client, Channel channel, MessageType type, const std::vector<uint8_t> &body);
	void broadcast(Channel channel, const std::vector<uint8_t> &packet);
	void kick(ClientId client, DisconnectReason reason = DisconnectReason::Kicked);

	std::vector<ClientId> connectedClients() const;
	bool isConnected(ClientId client) const;
	std::string clientName(ClientId client) const;
	float rttMs(ClientId client) const;  // 0 if unknown
	int violationCount(ClientId client) const;  // within the current window
	int pendingCount() const;

private:
	struct Conn {
		PeerId peer = 0;
		bool active = false;
		ClientId client = 0;
		uint32_t openedMs = 0;
		uint32_t lastRecvMs = 0;
		uint32_t lastPingMs = 0;
		uint32_t pingSeq = 0;
		RttEstimator rtt;
		uint32_t windowStartMs = 0;
		uint32_t windowBytes = 0;
		int windowRpcs = 0;
		std::deque<uint32_t> violations;
		bool dropPending = false;
		DisconnectReason dropReason = DisconnectReason::Quit;
	};
	struct Slot {
		std::string name;
		uint64_t token = 0;
		bool connected = false;
		PeerId peer = 0;
		uint32_t droppedMs = 0;
	};

	void onReceived(Conn &conn, Channel channel, const std::vector<uint8_t> &data,
	                std::vector<SessionEvent> &events);
	void onHello(Conn &conn, const uint8_t *body, size_t size, std::vector<SessionEvent> &events);
	void reject(Conn &conn, RejectReason reason, const char *detail);
	void addViolation(Conn &conn);
	/* Closes the connection; releaseSlot=false keeps it for reconnection. */
	void closeConn(PeerId peer, bool sendDisconnect, DisconnectReason reason, bool releaseSlot,
	               std::vector<SessionEvent> &events);
	Conn *connOf(ClientId client);
	const Conn *connOf(ClientId client) const;

	ITransport &m_transport;
	SessionConfig m_config;
	std::map<PeerId, Conn> m_conns;
	std::map<ClientId, Slot> m_slots;
	Tick m_serverTick = 1;
	uint32_t m_now = 0;
	bool m_running = false;
};

class ClientSession {
public:
	enum class State { Idle, Connecting, Handshaking, Connected, Disconnected };

	ClientSession(ITransport &transport, const SessionConfig &config);
	~ClientSession();

	bool connect(const std::string &host, uint16_t port, uint32_t nowMs);
	void disconnect();  // sends Disconnect(Quit)
	void update(uint32_t nowMs, std::vector<SessionEvent> &events);

	bool send(Channel channel, const std::vector<uint8_t> &packet);
	bool sendMessage(Channel channel, MessageType type, const std::vector<uint8_t> &body);

	State state() const
	{
		return m_state;
	}
	ClientId clientId() const
	{
		return m_welcome.clientId;
	}
	uint16_t tickRate() const
	{
		return m_welcome.tickRate;
	}
	uint16_t snapshotRate() const
	{
		return m_welcome.snapshotRate;
	}
	uint16_t maxClients() const
	{
		return m_welcome.maxClients;
	}
	const std::string &sceneName() const
	{
		return m_welcome.sceneName;
	}
	float rttMs() const
	{
		return m_rtt.rttMs;
	}
	/* Server tick estimated from the last Pong plus elapsed time and RTT/2. */
	Tick estimatedServerTick(uint32_t nowMs) const;

private:
	struct WelcomeInfo {
		ClientId clientId = 0;
		uint16_t tickRate = 0;
		uint16_t snapshotRate = 0;
		uint16_t maxClients = 0;
		std::string sceneName;
	};

	void onReceived(Channel channel, const std::vector<uint8_t> &data, std::vector<SessionEvent> &events);
	void finish(SessionEvent::Type type, uint8_t reason, const std::string &detail, bool sendQuit,
	            std::vector<SessionEvent> &events);

	ITransport &m_transport;
	SessionConfig m_config;
	State m_state = State::Idle;
	PeerId m_peer = 0;
	uint32_t m_connectMs = 0;
	uint32_t m_lastRecvMs = 0;
	uint32_t m_lastPingMs = 0;
	uint32_t m_pingSeq = 0;
	uint32_t m_now = 0;
	RttEstimator m_rtt;
	WelcomeInfo m_welcome;
	Tick m_pongServerTick = 0;
	uint32_t m_pongRecvMs = 0;
};

}  // namespace net
