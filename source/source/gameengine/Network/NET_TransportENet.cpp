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

/** \file gameengine/Network/NET_TransportENet.cpp
 *  \ingroup network
 *  \brief UDP transport over ENet. Control/Rpc are reliable, Snapshot/Input unsequenced unreliable.
 */

#include "NET_ITransport.h"
#include "NET_Types.h"

#include <enet/enet.h>

#include <map>
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
	++g_initCount;
	return true;
}

void releaseENet()
{
	std::lock_guard<std::mutex> lock(g_initMutex);
	if (g_initCount > 0 && --g_initCount == 0) {
		enet_deinitialize();
	}
}

class ENetTransport : public ITransport {
public:
	ENetTransport()
		:m_initialized(acquireENet())
	{
	}

	~ENetTransport() override
	{
		shutdown();
		if (m_initialized) {
			releaseENet();
		}
	}

	bool listen(uint16_t port, int maxPeers) override
	{
		if (!m_initialized || m_host || maxPeers <= 0 || maxPeers > ENET_PROTOCOL_MAXIMUM_PEER_ID) {
			return false;
		}
		ENetAddress address;
		address.host = ENET_HOST_ANY;
		address.port = port;
		m_host = enet_host_create(&address, size_t(maxPeers), kChannelCount, 0, 0);
		return m_host != nullptr;
	}

	bool connect(const std::string &host, uint16_t port) override
	{
		if (!m_initialized) {
			return false;
		}
		if (!m_host) {
			m_host = enet_host_create(nullptr, 1, kChannelCount, 0, 0);
			if (!m_host) {
				return false;
			}
		}
		ENetAddress address;
		if (enet_address_set_host(&address, host.c_str()) != 0) {
			return false;
		}
		address.port = port;
		ENetPeer *peer = enet_host_connect(m_host, &address, kChannelCount, 0);
		if (!peer) {
			return false;
		}
		registerPeer(peer);
		return true;
	}

	void send(PeerId id, Channel channel, const uint8_t *data, size_t size) override
	{
		const auto it = m_peers.find(id);
		if (it == m_peers.end() || uint8_t(channel) >= kChannelCount) {
			return;
		}
		const bool reliable = isReliableChannel(channel);
		if (size > (reliable ? kMaxReliableMessage : kMaxUnreliablePayload)) {
			return;
		}
		const enet_uint32 flags = reliable ? ENET_PACKET_FLAG_RELIABLE : ENET_PACKET_FLAG_UNSEQUENCED;
		ENetPacket *packet = enet_packet_create(data, size, flags);
		if (packet && enet_peer_send(it->second, enet_uint8(channel), packet) != 0) {
			enet_packet_destroy(packet);
		}
	}

	void disconnect(PeerId id) override
	{
		const auto it = m_peers.find(id);
		if (it == m_peers.end()) {
			return;
		}
		ENetPeer *peer = it->second;
		peer->data = nullptr;
		m_peers.erase(it);
		// Waits for queued reliable packets (e.g. a Reject) before disconnecting.
		enet_peer_disconnect_later(peer, 0);
		TransportEvent ev;
		ev.type = TransportEvent::Type::Disconnected;
		ev.peer = id;
		m_pending.push_back(std::move(ev));
	}

	void poll(std::vector<TransportEvent> &events) override
	{
		for (TransportEvent &ev : m_pending) {
			events.push_back(std::move(ev));
		}
		m_pending.clear();
		if (!m_host) {
			return;
		}
		ENetEvent event;
		while (enet_host_service(m_host, &event, 0) > 0) {
			switch (event.type) {
				case ENET_EVENT_TYPE_CONNECT: {
					TransportEvent ev;
					ev.type = TransportEvent::Type::Connected;
					ev.peer = event.peer->data ? peerId(event.peer) : registerPeer(event.peer);
					events.push_back(std::move(ev));
					break;
				}
				case ENET_EVENT_TYPE_DISCONNECT: {
					// Peers we disconnected ourselves were already reported.
					if (event.peer->data) {
						TransportEvent ev;
						ev.type = TransportEvent::Type::Disconnected;
						ev.peer = peerId(event.peer);
						m_peers.erase(ev.peer);
						event.peer->data = nullptr;
						events.push_back(std::move(ev));
					}
					break;
				}
				case ENET_EVENT_TYPE_RECEIVE: {
					if (event.peer->data && event.channelID < kChannelCount) {
						TransportEvent ev;
						ev.type = TransportEvent::Type::Received;
						ev.peer = peerId(event.peer);
						ev.channel = Channel(event.channelID);
						ev.data.assign(event.packet->data, event.packet->data + event.packet->dataLength);
						events.push_back(std::move(ev));
					}
					enet_packet_destroy(event.packet);
					break;
				}
				case ENET_EVENT_TYPE_NONE:
					break;
			}
		}
	}

	void shutdown() override
	{
		if (m_host) {
			for (const auto &pair : m_peers) {
				pair.second->data = nullptr;
				enet_peer_disconnect_now(pair.second, 0);
			}
			enet_host_flush(m_host);
			enet_host_destroy(m_host);
			m_host = nullptr;
		}
		m_peers.clear();
		m_pending.clear();
	}

	bool reliableAll() const override
	{
		return false;
	}

	uint16_t localPort() const override
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

private:
	static PeerId peerId(ENetPeer *peer)
	{
		return PeerId(reinterpret_cast<uintptr_t>(peer->data));
	}

	PeerId registerPeer(ENetPeer *peer)
	{
		const PeerId id = m_nextPeer++;
		peer->data = reinterpret_cast<void *>(uintptr_t(id));
		m_peers[id] = peer;
		return id;
	}

	bool m_initialized;
	ENetHost *m_host = nullptr;
	std::map<PeerId, ENetPeer *> m_peers;
	std::vector<TransportEvent> m_pending;
	PeerId m_nextPeer = 1;
};

}  // namespace

std::unique_ptr<ITransport> createENetTransport()
{
	return std::make_unique<ENetTransport>();
}

}  // namespace net
