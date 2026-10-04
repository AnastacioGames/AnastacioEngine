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

/** \file NET_ITransport.h
 *  \ingroup network
 *  \brief Transport interface (contract 9.2): ENet, loopback, simulated, WebSocket.
 */

#ifndef __NET_ITRANSPORT_H__
#define __NET_ITRANSPORT_H__

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace net {

using PeerId = uint32_t;  // transport local id, not a ClientId

enum class Channel : uint8_t { Control = 0, Rpc = 1, Snapshot = 2, Input = 3 };

constexpr int kChannelCount = 4;

inline bool isReliableChannel(Channel channel)
{
	return channel == Channel::Control || channel == Channel::Rpc;
}

struct TransportEvent {
	enum class Type { Connected, Disconnected, Received } type = Type::Received;
	PeerId peer = 0;
	Channel channel = Channel::Control;
	std::vector<uint8_t> data;  // only for Received
};

class ITransport {
public:
	virtual ~ITransport() = default;
	virtual bool listen(uint16_t port, int maxPeers) = 0;  // server
	virtual bool connect(const std::string &host, uint16_t port) = 0;  // client
	virtual void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) = 0;
	virtual void disconnect(PeerId peer) = 0;
	virtual void poll(std::vector<TransportEvent> &events) = 0;  // never blocks
	virtual void shutdown() = 0;
	virtual bool reliableAll() const = 0;  // true for WebSocket

	/// Bound local port (useful after listen(0)); 0 when unknown or not bound.
	virtual uint16_t localPort() const
	{
		return 0;
	}
};

struct NetSimSettings {
	uint32_t latencyMs = 0;
	uint32_t jitterMs = 0;
	float lossPercent = 0.0f;  // unreliable channels only
	float duplicatePercent = 0.0f;  // unreliable channels only
	uint64_t seed = 1;
	/// Time source in milliseconds; empty = steady clock. Tests use a fake clock.
	std::function<uint64_t()> clock;
};

/// Two in-memory endpoints: listen() on one, connect() on the other (host and port ignored).
std::unique_ptr<ITransport> createLoopbackPair(std::unique_ptr<ITransport> &other);
std::unique_ptr<ITransport> createENetTransport();
std::unique_ptr<ITransport> createSimulatedTransport(std::unique_ptr<ITransport> inner,
                                                     const NetSimSettings &settings);

/// In-memory network for one server and several clients: endpoints created from the same hub
/// reach each other by port (connect host is ignored).
class LoopbackHub;
std::shared_ptr<LoopbackHub> createLoopbackHub();
std::unique_ptr<ITransport> createLoopbackTransport(const std::shared_ptr<LoopbackHub> &hub);

/// Milliseconds from a steady clock.
uint64_t steadyClockMs();

}  // namespace net

#endif  // __NET_ITRANSPORT_H__
