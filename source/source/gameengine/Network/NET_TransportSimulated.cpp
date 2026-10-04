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

/** \file gameengine/Network/NET_TransportSimulated.cpp
 *  \ingroup network
 *  \brief Wraps a transport and adds latency, jitter, loss and duplication to what it receives.
 *
 * Loss and duplication only touch unreliable channels (Snapshot, Input), as a reliable transport
 * turns real loss into delay. Reliable data and connection events keep their order per peer.
 * Wrapping both ends simulates both directions.
 */

#include "NET_ITransport.h"

#include <map>
#include <utility>

namespace net {

namespace {

class SimulatedTransport : public ITransport {
public:
	SimulatedTransport(std::unique_ptr<ITransport> inner, const NetSimSettings &settings)
		:m_inner(std::move(inner)),
		m_settings(settings),
		m_rng(settings.seed)
	{
		if (!m_settings.clock) {
			m_settings.clock = steadyClockMs;
		}
	}

	bool listen(uint16_t port, int maxPeers) override
	{
		return m_inner->listen(port, maxPeers);
	}

	bool connect(const std::string &host, uint16_t port) override
	{
		return m_inner->connect(host, port);
	}

	void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) override
	{
		m_inner->send(peer, channel, data, size);
	}

	void disconnect(PeerId peer) override
	{
		m_inner->disconnect(peer);
	}

	void poll(std::vector<TransportEvent> &events) override
	{
		const uint64_t now = m_settings.clock();
		std::vector<TransportEvent> incoming;
		m_inner->poll(incoming);
		for (TransportEvent &ev : incoming) {
			schedule(std::move(ev), now);
		}
		while (!m_queue.empty() && m_queue.begin()->first.first <= now) {
			events.push_back(std::move(m_queue.begin()->second));
			m_queue.erase(m_queue.begin());
		}
	}

	void shutdown() override
	{
		m_inner->shutdown();
		m_queue.clear();
		m_lastOrdered.clear();
	}

	bool reliableAll() const override
	{
		return m_inner->reliableAll();
	}

	uint16_t localPort() const override
	{
		return m_inner->localPort();
	}

private:
	uint64_t nextRandom()
	{
		uint64_t z = (m_rng += 0x9e3779b97f4a7c15ull);
		z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull;
		z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
		return z ^ (z >> 31);
	}

	bool chance(float percent)
	{
		if (percent <= 0.0f) {
			return false;
		}
		return float(nextRandom() % 1000000) < percent * 10000.0f;
	}

	uint64_t delay()
	{
		uint64_t d = m_settings.latencyMs;
		if (m_settings.jitterMs > 0) {
			d += nextRandom() % (uint64_t(m_settings.jitterMs) + 1);
		}
		return d;
	}

	void push(uint64_t at, TransportEvent ev)
	{
		m_queue.emplace(std::make_pair(at, m_seq++), std::move(ev));
	}

	void schedule(TransportEvent ev, uint64_t now)
	{
		const bool ordered = ev.type != TransportEvent::Type::Received || m_inner->reliableAll() ||
		                     isReliableChannel(ev.channel);
		if (ordered) {
			uint64_t at = now + delay();
			uint64_t &last = m_lastOrdered[ev.peer];
			if (at < last) {
				at = last;
			}
			last = at;
			if (ev.type == TransportEvent::Type::Disconnected) {
				m_lastOrdered.erase(ev.peer);
			}
			push(at, std::move(ev));
			return;
		}
		if (chance(m_settings.lossPercent)) {
			return;
		}
		if (chance(m_settings.duplicatePercent)) {
			push(now + delay(), ev);
		}
		push(now + delay(), std::move(ev));
	}

	std::unique_ptr<ITransport> m_inner;
	NetSimSettings m_settings;
	uint64_t m_rng;
	uint64_t m_seq = 0;
	std::multimap<std::pair<uint64_t, uint64_t>, TransportEvent> m_queue;
	std::map<PeerId, uint64_t> m_lastOrdered;
};

}  // namespace

std::unique_ptr<ITransport> createSimulatedTransport(std::unique_ptr<ITransport> inner, const NetSimSettings &settings)
{
	if (!inner) {
		return nullptr;
	}
	return std::make_unique<SimulatedTransport>(std::move(inner), settings);
}

}  // namespace net
