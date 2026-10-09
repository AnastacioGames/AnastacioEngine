/* Transport interface (docs/multiplayer-protocol.md section 9.2). */

#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace net {

using PeerId = uint32_t;  // local transport id, not a ClientId

enum class Channel : uint8_t { Control = 0, Rpc = 1, Snapshot = 2, Input = 3 };

constexpr int kChannelCount = 4;

inline bool channelReliable(Channel c)
{
	return c == Channel::Control || c == Channel::Rpc;
}

struct TransportEvent {
	enum class Type { Connected, Disconnected, Received } type;
	PeerId peer;
	Channel channel;
	std::vector<uint8_t> data;  // only for Received
};

class ITransport {
public:
	virtual ~ITransport() = default;
	virtual bool listen(uint16_t port, int maxPeers) = 0;              // server
	virtual bool connect(const std::string &host, uint16_t port) = 0;  // client
	virtual void send(PeerId, Channel, const uint8_t *data, size_t size) = 0;
	virtual void disconnect(PeerId) = 0;
	virtual void poll(std::vector<TransportEvent> &events) = 0;  // non-blocking
	virtual void shutdown() = 0;
	virtual bool reliableAll() const = 0;  // true on WebSocket
};

struct NetSimSettings {
	uint32_t latencyMs = 0;
	uint32_t jitterMs = 0;
	float lossPercent = 0.0f;       // unreliable channels only
	float duplicatePercent = 0.0f;  // unreliable channels only
	uint32_t seed = 1;
	/* Extension (not in the contract): optional millisecond clock so tests are
	 * deterministic. Empty = std::chrono::steady_clock. */
	std::function<uint32_t()> clockMs;
};

std::unique_ptr<ITransport> createLoopbackPair(std::unique_ptr<ITransport> &other);
std::unique_ptr<ITransport> createENetTransport();
std::unique_ptr<ITransport> createSimulatedTransport(std::unique_ptr<ITransport> inner,
                                                     const NetSimSettings &);

}  // namespace net
