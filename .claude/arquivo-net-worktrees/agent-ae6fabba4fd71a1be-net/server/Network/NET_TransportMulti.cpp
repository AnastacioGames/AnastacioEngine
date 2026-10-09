/* Multi-transport: several server transports (ENet + WebSocket) behind one PeerId space,
 * so native and browser players share the same session (cross-play). */

#include "NET_TransportWebSocket.h"

#include <map>
#include <set>
#include <utility>

namespace net {

namespace {

class TransportMulti final : public MultiTransport {
public:
	~TransportMulti() override
	{
		shutdown();
	}

	void add(std::unique_ptr<ITransport> transport, uint16_t port) override
	{
		if (transport && !m_listening) {
			m_entries.push_back({std::move(transport), port});
		}
	}

	bool listen(uint16_t port, int maxPeers) override
	{
		if (m_entries.empty() || m_listening || maxPeers <= 0) {
			return false;
		}
		for (Entry &e : m_entries) {
			if (!e.transport->listen(e.port ? e.port : port, maxPeers)) {
				for (Entry &other : m_entries) {
					other.transport->shutdown();
				}
				return false;
			}
		}
		m_maxPeers = maxPeers;
		m_listening = true;
		return true;
	}

	bool connect(const std::string &, uint16_t) override
	{
		return false;
	}

	void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) override
	{
		auto it = m_outer.find(peer);
		if (it != m_outer.end()) {
			m_entries[it->second.first].transport->send(it->second.second, channel, data, size);
		}
	}

	void disconnect(PeerId peer) override
	{
		/* The mapping is dropped when the inner transport reports Disconnected. */
		auto it = m_outer.find(peer);
		if (it != m_outer.end()) {
			m_entries[it->second.first].transport->disconnect(it->second.second);
		}
	}

	void poll(std::vector<TransportEvent> &events) override
	{
		std::vector<TransportEvent> inner;
		for (size_t i = 0; i < m_entries.size(); i++) {
			inner.clear();
			m_entries[i].transport->poll(inner);
			for (TransportEvent &e : inner) {
				const Key key(i, e.peer);
				switch (e.type) {
					case TransportEvent::Type::Connected:
						if (int(m_outer.size()) >= m_maxPeers) {
							/* Full across all transports: drop it and hide its Disconnected. */
							m_refused.insert(key);
							m_entries[i].transport->disconnect(e.peer);
							break;
						}
						e.peer = mapPeer(key);
						events.push_back(std::move(e));
						break;
					case TransportEvent::Type::Disconnected: {
						auto it = m_inner.find(key);
						if (it == m_inner.end()) {
							m_refused.erase(key);
							break;
						}
						e.peer = it->second;
						m_outer.erase(it->second);
						m_inner.erase(it);
						events.push_back(std::move(e));
						break;
					}
					case TransportEvent::Type::Received: {
						auto it = m_inner.find(key);
						if (it != m_inner.end()) {
							e.peer = it->second;
							events.push_back(std::move(e));
						}
						break;
					}
				}
			}
		}
	}

	void shutdown() override
	{
		for (Entry &e : m_entries) {
			e.transport->shutdown();
		}
		m_outer.clear();
		m_inner.clear();
		m_refused.clear();
		m_listening = false;
	}

	bool reliableAll() const override
	{
		if (m_entries.empty()) {
			return false;
		}
		for (const Entry &e : m_entries) {
			if (!e.transport->reliableAll()) {
				return false;
			}
		}
		return true;
	}

	bool reliableFor(PeerId peer) const override
	{
		auto it = m_outer.find(peer);
		return it != m_outer.end() && m_entries[it->second.first].transport->reliableAll();
	}

private:
	using Key = std::pair<size_t, PeerId>;

	struct Entry {
		std::unique_ptr<ITransport> transport;
		uint16_t port;
	};

	PeerId mapPeer(const Key &key)
	{
		PeerId id = m_nextId;
		while (id == 0 || m_outer.count(id)) {
			id++;
		}
		m_nextId = id + 1;
		m_outer[id] = key;
		m_inner[key] = id;
		return id;
	}

	std::vector<Entry> m_entries;
	std::map<PeerId, Key> m_outer;
	std::map<Key, PeerId> m_inner;
	std::set<Key> m_refused;
	PeerId m_nextId = 1;
	int m_maxPeers = 0;
	bool m_listening = false;
};

} // namespace

std::unique_ptr<MultiTransport> createMultiTransport()
{
	return std::make_unique<TransportMulti>();
}

} // namespace net
