#include "NET_TransportLoopback.h"

#include <map>

namespace net {

class LoopbackEndpoint;

struct LoopbackHubState {
	std::map<uint16_t, LoopbackEndpoint *> listeners;
};

class LoopbackEndpoint final : public ITransport {
public:
	explicit LoopbackEndpoint(std::shared_ptr<LoopbackHubState> hub) : m_hub(std::move(hub)) {}
	~LoopbackEndpoint() override
	{
		shutdown();
	}

	bool listen(uint16_t port, int maxPeers) override
	{
		if (m_listening || m_hub->listeners.count(port)) {
			return false;
		}
		m_hub->listeners[port] = this;
		m_listening = true;
		m_port = port;
		m_maxPeers = maxPeers;
		return true;
	}

	bool connect(const std::string & /*host*/, uint16_t port) override
	{
		auto it = m_hub->listeners.find(port);
		if (it == m_hub->listeners.end() || it->second == this) {
			return false;
		}
		LoopbackEndpoint *server = it->second;
		const PeerId mine = m_nextPeer++;
		if (int(server->m_links.size()) >= server->m_maxPeers) {
			/* Refused: report as an immediate disconnect, like a real transport. */
			m_inbox.push_back({TransportEvent::Type::Disconnected, mine, Channel::Control, {}});
			return true;
		}
		const PeerId theirs = server->m_nextPeer++;
		m_links[mine] = {server, theirs};
		server->m_links[theirs] = {this, mine};
		m_inbox.push_back({TransportEvent::Type::Connected, mine, Channel::Control, {}});
		server->m_inbox.push_back({TransportEvent::Type::Connected, theirs, Channel::Control, {}});
		return true;
	}

	void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) override
	{
		auto it = m_links.find(peer);
		if (it == m_links.end()) {
			return;
		}
		it->second.remote->m_inbox.push_back({TransportEvent::Type::Received,
		                                      it->second.remotePeer,
		                                      channel,
		                                      std::vector<uint8_t>(data, data + size)});
	}

	void disconnect(PeerId peer) override
	{
		auto it = m_links.find(peer);
		if (it == m_links.end()) {
			return;
		}
		Link link = it->second;
		m_links.erase(it);
		link.remote->m_links.erase(link.remotePeer);
		link.remote->m_inbox.push_back(
		    {TransportEvent::Type::Disconnected, link.remotePeer, Channel::Control, {}});
		m_inbox.push_back({TransportEvent::Type::Disconnected, peer, Channel::Control, {}});
	}

	void poll(std::vector<TransportEvent> &events) override
	{
		for (TransportEvent &e : m_inbox) {
			events.push_back(std::move(e));
		}
		m_inbox.clear();
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
		m_inbox.clear();
	}

	bool reliableAll() const override
	{
		return true;
	}

private:
	struct Link {
		LoopbackEndpoint *remote;
		PeerId remotePeer;
	};

	std::shared_ptr<LoopbackHubState> m_hub;
	std::map<PeerId, Link> m_links;
	std::vector<TransportEvent> m_inbox;
	PeerId m_nextPeer = 1;
	bool m_listening = false;
	uint16_t m_port = 0;
	int m_maxPeers = 0;
};

LoopbackHub::LoopbackHub() : m_state(std::make_shared<LoopbackHubState>()) {}

std::unique_ptr<ITransport> LoopbackHub::createEndpoint()
{
	return std::make_unique<LoopbackEndpoint>(m_state);
}

std::unique_ptr<ITransport> createLoopbackPair(std::unique_ptr<ITransport> &other)
{
	LoopbackHub hub;
	other = hub.createEndpoint();
	return hub.createEndpoint();
}

}  // namespace net
