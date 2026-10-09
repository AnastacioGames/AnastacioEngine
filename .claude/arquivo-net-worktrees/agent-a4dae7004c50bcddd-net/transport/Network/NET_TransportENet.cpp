/* ENet transport. Logical channels (section 4.1) map 1:1 to ENet channels:
 * Control/Rpc reliable ordered, Snapshot/Input unreliable sequenced (ENet's
 * default unreliable mode drops packets older than the newest received). */

#include "NET_TransportENet.h"

#include <enet/enet.h>

#include <mutex>

namespace net {

namespace {

std::mutex g_initMutex;
int g_initCount = 0;

bool acquireENet()
{
	std::lock_guard<std::mutex> lock(g_initMutex);
	if (g_initCount == 0 && enet_initialize() != 0) {
		return false;
	}
	g_initCount++;
	return true;
}

void releaseENet()
{
	std::lock_guard<std::mutex> lock(g_initMutex);
	if (--g_initCount == 0) {
		enet_deinitialize();
	}
}

/* Peer ids are stored in ENetPeer::data; 0 = not tracked (already dropped). */
PeerId peerIdOf(ENetPeer *peer)
{
	return PeerId(reinterpret_cast<uintptr_t>(peer->data));
}

}  // namespace

ENetTransport::ENetTransport()
{
	m_initialized = acquireENet();
}

ENetTransport::~ENetTransport()
{
	shutdown();
	if (m_initialized) {
		releaseENet();
	}
}

bool ENetTransport::listen(uint16_t port, int maxPeers)
{
	if (!m_initialized || m_host || maxPeers <= 0) {
		return false;
	}
	ENetAddress address;
	address.host = ENET_HOST_ANY;
	address.port = port;
	m_host = enet_host_create(&address, size_t(maxPeers), kChannelCount, 0, 0);
	return m_host != nullptr;
}

bool ENetTransport::connect(const std::string &host, uint16_t port)
{
	if (!m_initialized || m_host) {
		return false;
	}
	ENetAddress address;
	if (enet_address_set_host(&address, host.c_str()) != 0) {
		return false;
	}
	address.port = port;
	m_host = enet_host_create(nullptr, 1, kChannelCount, 0, 0);
	if (!m_host) {
		return false;
	}
	ENetPeer *peer = enet_host_connect(m_host, &address, kChannelCount, 0);
	if (!peer) {
		enet_host_destroy(m_host);
		m_host = nullptr;
		return false;
	}
	registerPeer(peer);
	return true;
}

PeerId ENetTransport::registerPeer(ENetPeer *peer)
{
	const PeerId id = m_nextPeer++;
	peer->data = reinterpret_cast<void *>(uintptr_t(id));
	m_peers[id] = peer;
	return id;
}

void ENetTransport::send(PeerId id, Channel channel, const uint8_t *data, size_t size)
{
	auto it = m_peers.find(id);
	if (it == m_peers.end()) {
		return;
	}
	const enet_uint32 flags = channelReliable(channel) ? ENET_PACKET_FLAG_RELIABLE :
	                                                     ENET_PACKET_FLAG_UNRELIABLE_FRAGMENT;
	ENetPacket *packet = enet_packet_create(data, size, flags);
	if (packet && enet_peer_send(it->second, enet_uint8(channel), packet) != 0) {
		enet_packet_destroy(packet);
	}
}

void ENetTransport::disconnect(PeerId id)
{
	auto it = m_peers.find(id);
	if (it == m_peers.end()) {
		return;
	}
	ENetPeer *peer = it->second;
	m_peers.erase(it);
	peer->data = nullptr;
	/* Sends queued packets (e.g. a Disconnect message) before closing. */
	enet_peer_disconnect_later(peer, 0);
	m_localEvents.push_back({TransportEvent::Type::Disconnected, id, Channel::Control, {}});
}

void ENetTransport::poll(std::vector<TransportEvent> &events)
{
	for (TransportEvent &e : m_localEvents) {
		events.push_back(std::move(e));
	}
	m_localEvents.clear();
	if (!m_host) {
		return;
	}
	ENetEvent ev;
	while (m_host && enet_host_service(m_host, &ev, 0) > 0) {
		switch (ev.type) {
			case ENET_EVENT_TYPE_CONNECT: {
				PeerId id = peerIdOf(ev.peer);
				if (id == 0) {
					id = registerPeer(ev.peer);
				}
				events.push_back({TransportEvent::Type::Connected, id, Channel::Control, {}});
				break;
			}
			case ENET_EVENT_TYPE_DISCONNECT: {
				const PeerId id = peerIdOf(ev.peer);
				if (id != 0) {
					m_peers.erase(id);
					ev.peer->data = nullptr;
					events.push_back({TransportEvent::Type::Disconnected, id, Channel::Control, {}});
				}
				break;
			}
			case ENET_EVENT_TYPE_RECEIVE: {
				const PeerId id = peerIdOf(ev.peer);
				if (id != 0 && ev.channelID < kChannelCount) {
					const uint8_t *bytes = ev.packet->data;
					events.push_back({TransportEvent::Type::Received,
					                  id,
					                  Channel(ev.channelID),
					                  std::vector<uint8_t>(bytes, bytes + ev.packet->dataLength)});
				}
				enet_packet_destroy(ev.packet);
				break;
			}
			case ENET_EVENT_TYPE_NONE:
				break;
		}
	}
	if (m_host) {
		enet_host_flush(m_host);
	}
}

void ENetTransport::shutdown()
{
	if (!m_host) {
		return;
	}
	for (auto &kv : m_peers) {
		kv.second->data = nullptr;
		enet_peer_disconnect_now(kv.second, 0);
	}
	m_peers.clear();
	m_localEvents.clear();
	enet_host_flush(m_host);
	enet_host_destroy(m_host);
	m_host = nullptr;
}

uint16_t ENetTransport::localPort() const
{
	if (!m_host) {
		return 0;
	}
	ENetAddress address;
	if (enet_socket_get_address(m_host->socket, &address) != 0) {
		return 0;
	}
	return address.port;
}

std::unique_ptr<ITransport> createENetTransport()
{
	return std::make_unique<ENetTransport>();
}

}  // namespace net
