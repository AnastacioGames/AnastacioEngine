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

/** \file gameengine/Network/NET_TransportMulti.cpp
 *  \ingroup network
 *  \brief Several server transports seen as one (cross-play: ENet + WebSocket).
 */

#include "NET_TransportWeb.h"

#include <map>
#include <utility>

namespace net {

namespace {

class MultiTransport : public ITransport {
public:
	explicit MultiTransport(std::vector<MultiTransportEntry> entries) : m_entries(std::move(entries))
	{
		m_outer.resize(m_entries.size());
	}

	~MultiTransport() override
	{
		shutdown();
	}

	/// Each transport listens on its own port (or on port when its entry has 0). maxPeers applies
	/// to each one; the session still enforces maxClients.
	bool listen(uint16_t port, int maxPeers) override
	{
		if (m_entries.empty()) {
			return false;
		}
		for (MultiTransportEntry &entry : m_entries) {
			if (!entry.transport || !entry.transport->listen(entry.port ? entry.port : port, maxPeers)) {
				shutdown();
				return false;
			}
		}
		return true;
	}

	bool connect(const std::string &, uint16_t) override
	{
		return false;  // server only
	}

	void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) override
	{
		auto it = m_inner.find(peer);
		if (it != m_inner.end()) {
			m_entries[it->second.first].transport->send(it->second.second, channel, data, size);
		}
	}

	void disconnect(PeerId peer) override
	{
		auto it = m_inner.find(peer);
		if (it != m_inner.end()) {
			// The mapping goes away with the inner Disconnected event.
			m_entries[it->second.first].transport->disconnect(it->second.second);
		}
	}

	void poll(std::vector<TransportEvent> &events) override
	{
		std::vector<TransportEvent> inner;
		for (size_t index = 0; index < m_entries.size(); ++index) {
			if (!m_entries[index].transport) {
				continue;
			}
			inner.clear();
			m_entries[index].transport->poll(inner);
			std::map<PeerId, PeerId> &outer = m_outer[index];
			for (TransportEvent &ev : inner) {
				if (ev.type == TransportEvent::Type::Connected) {
					const PeerId id = nextId();
					outer[ev.peer] = id;
					m_inner[id] = std::make_pair(index, ev.peer);
					ev.peer = id;
					events.push_back(std::move(ev));
					continue;
				}
				auto it = outer.find(ev.peer);
				if (it == outer.end()) {
					continue;  // peer not announced
				}
				const PeerId id = it->second;
				if (ev.type == TransportEvent::Type::Disconnected) {
					outer.erase(it);
					m_inner.erase(id);
				}
				ev.peer = id;
				events.push_back(std::move(ev));
			}
		}
	}

	void shutdown() override
	{
		for (MultiTransportEntry &entry : m_entries) {
			if (entry.transport) {
				entry.transport->shutdown();
			}
		}
		m_inner.clear();
		for (std::map<PeerId, PeerId> &outer : m_outer) {
			outer.clear();
		}
	}

	/// Mixed guarantees: the strictest one (per channel) applies.
	bool reliableAll() const override
	{
		return false;
	}

	/// Port of the first transport.
	uint16_t localPort() const override
	{
		return m_entries.empty() || !m_entries[0].transport ? 0 : m_entries[0].transport->localPort();
	}

private:
	PeerId nextId()
	{
		do {
			if (++m_nextId == 0) {
				m_nextId = 1;
			}
		} while (m_inner.count(m_nextId));
		return m_nextId;
	}

	std::vector<MultiTransportEntry> m_entries;
	std::vector<std::map<PeerId, PeerId>> m_outer;  // per transport: inner peer -> outer peer
	std::map<PeerId, std::pair<size_t, PeerId>> m_inner;  // outer peer -> (transport, inner peer)
	PeerId m_nextId = 0;
};

}  // namespace

std::unique_ptr<ITransport> createMultiTransport(std::vector<MultiTransportEntry> entries)
{
	return std::unique_ptr<ITransport>(new MultiTransport(std::move(entries)));
}

}  // namespace net
