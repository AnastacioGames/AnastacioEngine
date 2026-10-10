/* PROVISIONAL (Frente C): minimal copy of contract section 9.2 so net/server builds alone.
 * The authoritative version comes from Frente B (net/transport); on merge keep B's file. */

#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace net {

using PeerId = uint32_t; /* Local transport id, not a ClientId. */

enum class Channel : uint8_t { Control = 0, Rpc = 1, Snapshot = 2, Input = 3 };

struct TransportEvent {
	enum class Type { Connected, Disconnected, Received } type;
	PeerId peer;
	Channel channel;
	std::vector<uint8_t> data; /* Only in Received. */
};

class ITransport {
public:
	virtual ~ITransport() = default;
	virtual bool listen(uint16_t port, int maxPeers) = 0;             /* Server. */
	virtual bool connect(const std::string &host, uint16_t port) = 0; /* Client. */
	virtual void send(PeerId, Channel, const uint8_t *data, size_t size) = 0;
	virtual void disconnect(PeerId) = 0;
	virtual void poll(std::vector<TransportEvent> &events) = 0; /* Never blocks. */
	virtual void shutdown() = 0;
	virtual bool reliableAll() const = 0; /* True for WebSocket. */
};

struct NetSimSettings {
	uint32_t latencyMs = 0;
	uint32_t jitterMs = 0;
	float lossPercent = 0.0f;
	float duplicatePercent = 0.0f;
	uint32_t seed = 1;
};

std::unique_ptr<ITransport> createLoopbackPair(std::unique_ptr<ITransport> &other);
std::unique_ptr<ITransport> createENetTransport();
std::unique_ptr<ITransport> createSimulatedTransport(std::unique_ptr<ITransport> inner,
                                                     const NetSimSettings &);

} // namespace net
