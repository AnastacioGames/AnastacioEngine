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

/** \file gameengine/Network/NET_TransportLoopback.cpp
 *  \ingroup network
 *  \brief In-memory transport for tests and single process play. Not thread safe.
 */

#include "NET_ITransport.h"

#include <chrono>
#include <deque>
#include <map>

namespace net {

namespace {
class LoopbackEndpoint;
}

class LoopbackHub {
public:
	bool pairMode = false;
	std::map<uint16_t, LoopbackEndpoint *> listeners;
	std::vector<LoopbackEndpoint *> endpoints;
};

namespace {

class LoopbackEndpoint : public ITransport {
public:
	explicit LoopbackEndpoint(std::shared_ptr<LoopbackHub> hub)
		:m_hub(std::move(hub))
	{
		m_hub->endpoints.push_back(this);
	}

	~LoopbackEndpoint() override
	{
		shutdown();
		auto &eps = m_hub->endpoints;
		for (auto it = eps.begin(); it != eps.end(); ++it) {
			if (*it == this) {
				eps.erase(it);
				break;
			}
		}
	}

	bool listen(uint16_t port, int maxPeers) override
	{
		if (m_listening || maxPeers <= 0 || m_hub->listeners.count(port)) {
			return false;
		}
		m_listening = true;
		m_port = port;
		m_maxPeers = maxPeers;
		m_hub->listeners[port] = this;
		return true;
	}

	bool connect(const std::string &, uint16_t port) override
	{
		LoopbackEndpoint *target = nullptr;
		if (m_hub->pairMode) {
			for (LoopbackEndpoint *ep : m_hub->endpoints) {
				if (ep != this && ep->m_listening) {
					target = ep;
				}
			}
		}
		else {
			const auto it = m_hub->listeners.find(port);
			target = (it != m_hub->listeners.end()) ? it->second : nullptr;
		}
		if (!target || target == this) {
			return false;
		}
		const PeerId local = m_nextPeer++;
		if (int(target->m_links.size()) >= target->m_maxPeers) {
			pushEvent(TransportEvent::Type::Disconnected, local);
			return true;
		}
		const PeerId remote = target->m_nextPeer++;
		m_links[local] = {target, remote};
		target->m_links[remote] = {this, local};
		pushEvent(TransportEvent::Type::Connected, local);
		target->pushEvent(TransportEvent::Type::Connected, remote);
		return true;
	}

	void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) override
	{
		const auto it = m_links.find(peer);
		if (it == m_links.end() || uint8_t(channel) >= kChannelCount) {
			return;
		}
		TransportEvent ev;
		ev.type = TransportEvent::Type::Received;
		ev.peer = it->second.remotePeer;
		ev.channel = channel;
		ev.data.assign(data, data + size);
		it->second.remote->m_inbox.push_back(std::move(ev));
	}

	void disconnect(PeerId peer) override
	{
		const auto it = m_links.find(peer);
		if (it == m_links.end()) {
			return;
		}
		const Link link = it->second;
		m_links.erase(it);
		link.remote->m_links.erase(link.remotePeer);
		link.remote->pushEvent(TransportEvent::Type::Disconnected, link.remotePeer);
		pushEvent(TransportEvent::Type::Disconnected, peer);
	}

	void poll(std::vector<TransportEvent> &events) override
	{
		while (!m_inbox.empty()) {
			events.push_back(std::move(m_inbox.front()));
			m_inbox.pop_front();
		}
	}

	void shutdown() override
	{
		while (!m_links.empty()) {
			disconnect(m_links.begin()->first);
		}
		if (m_listening) {
			m_hub->listeners.erase(m_port);
			m_listening = false;
		}
	}

	/// Delivers everything, but keeps channels like ENet, so the simulator can drop unreliable ones.
	bool reliableAll() const override
	{
		return false;
	}

	uint16_t localPort() const override
	{
		return m_listening ? m_port : 0;
	}

private:
	struct Link {
		LoopbackEndpoint *remote;
		PeerId remotePeer;
	};

	void pushEvent(TransportEvent::Type type, PeerId peer)
	{
		TransportEvent ev;
		ev.type = type;
		ev.peer = peer;
		m_inbox.push_back(std::move(ev));
	}

	std::shared_ptr<LoopbackHub> m_hub;
	std::map<PeerId, Link> m_links;
	std::deque<TransportEvent> m_inbox;
	PeerId m_nextPeer = 1;
	bool m_listening = false;
	uint16_t m_port = 0;
	int m_maxPeers = 0;
};

}  // namespace

std::shared_ptr<LoopbackHub> createLoopbackHub()
{
	return std::make_shared<LoopbackHub>();
}

std::unique_ptr<ITransport> createLoopbackTransport(const std::shared_ptr<LoopbackHub> &hub)
{
	return std::make_unique<LoopbackEndpoint>(hub);
}

std::unique_ptr<ITransport> createLoopbackPair(std::unique_ptr<ITransport> &other)
{
	std::shared_ptr<LoopbackHub> hub = createLoopbackHub();
	hub->pairMode = true;
	other = createLoopbackTransport(hub);
	return createLoopbackTransport(hub);
}

uint64_t steadyClockMs()
{
	return uint64_t(std::chrono::duration_cast<std::chrono::milliseconds>(
	                    std::chrono::steady_clock::now().time_since_epoch())
	                    .count());
}

}  // namespace net
