/* ENet transport (UDP). Exposed as a class so tools/tests can query the bound
 * port after listen(0) (ephemeral port). */

#pragma once

#include "NET_ITransport.h"

#include <map>

struct _ENetHost;
struct _ENetPeer;

namespace net {

class ENetTransport final : public ITransport {
public:
	ENetTransport();
	~ENetTransport() override;

	bool listen(uint16_t port, int maxPeers) override;
	bool connect(const std::string &host, uint16_t port) override;
	void send(PeerId, Channel, const uint8_t *data, size_t size) override;
	void disconnect(PeerId) override;
	void poll(std::vector<TransportEvent> &events) override;
	void shutdown() override;
	bool reliableAll() const override
	{
		return false;
	}

	/* Port actually bound by listen() (useful with port 0). 0 if not listening. */
	uint16_t localPort() const;

private:
	PeerId registerPeer(_ENetPeer *peer);

	bool m_initialized = false;
	_ENetHost *m_host = nullptr;
	std::map<PeerId, _ENetPeer *> m_peers;
	std::vector<TransportEvent> m_localEvents;
	PeerId m_nextPeer = 1;
};

}  // namespace net
