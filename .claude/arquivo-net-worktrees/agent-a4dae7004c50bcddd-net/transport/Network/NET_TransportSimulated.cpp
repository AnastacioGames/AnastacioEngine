/* Network conditions simulator: wraps another transport and delays, drops and
 * duplicates outgoing packets with a seeded generator (repeatable tests).
 * Reliable channels are only delayed and keep their order; loss and
 * duplication apply to the unreliable channels (Snapshot, Input). */

#include "NET_ITransport.h"

#include <chrono>
#include <deque>
#include <random>

namespace net {

namespace {

uint32_t steadyMs()
{
	using namespace std::chrono;
	return uint32_t(duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());
}

class SimulatedTransport final : public ITransport {
public:
	SimulatedTransport(std::unique_ptr<ITransport> inner, const NetSimSettings &settings)
	    : m_inner(std::move(inner)), m_settings(settings), m_rng(settings.seed)
	{
		if (!m_settings.clockMs) {
			m_settings.clockMs = steadyMs;
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
		const uint32_t now = m_settings.clockMs();
		int copies = 1;
		if (!channelReliable(channel)) {
			if (chance(m_settings.lossPercent)) {
				copies = 0;
			}
			else if (chance(m_settings.duplicatePercent)) {
				copies = 2;
			}
		}
		for (int i = 0; i < copies; i++) {
			uint32_t due = now + m_settings.latencyMs;
			if (m_settings.jitterMs > 0) {
				due += uint32_t(m_rng() % (m_settings.jitterMs + 1));
			}
			if (channelReliable(channel)) {
				/* Never reorder a reliable channel. */
				uint32_t &last = m_lastReliableDue[int(channel)];
				if (int32_t(due - last) < 0) {
					due = last;
				}
				last = due;
			}
			Pending p{due, peer, channel, std::vector<uint8_t>(data, data + size)};
			/* Insert keeping the queue sorted by due time (stable for equal times). */
			auto it = m_queue.end();
			while (it != m_queue.begin() && int32_t((it - 1)->due - due) > 0) {
				--it;
			}
			m_queue.insert(it, std::move(p));
		}
		flush(now);
	}

	void disconnect(PeerId peer) override
	{
		m_inner->disconnect(peer);
	}

	void poll(std::vector<TransportEvent> &events) override
	{
		flush(m_settings.clockMs());
		m_inner->poll(events);
	}

	void shutdown() override
	{
		m_queue.clear();
		m_inner->shutdown();
	}

	bool reliableAll() const override
	{
		return false;
	}

private:
	struct Pending {
		uint32_t due;
		PeerId peer;
		Channel channel;
		std::vector<uint8_t> data;
	};

	bool chance(float percent)
	{
		if (percent <= 0.0f) {
			return false;
		}
		/* Integer draw keeps results identical across platforms. */
		const uint32_t roll = uint32_t(m_rng() % 10000u);
		return float(roll) < percent * 100.0f;
	}

	void flush(uint32_t now)
	{
		while (!m_queue.empty() && int32_t(now - m_queue.front().due) >= 0) {
			Pending &p = m_queue.front();
			m_inner->send(p.peer, p.channel, p.data.data(), p.data.size());
			m_queue.pop_front();
		}
	}

	std::unique_ptr<ITransport> m_inner;
	NetSimSettings m_settings;
	std::mt19937 m_rng;
	std::deque<Pending> m_queue;
	uint32_t m_lastReliableDue[kChannelCount] = {0, 0, 0, 0};
};

}  // namespace

std::unique_ptr<ITransport> createSimulatedTransport(std::unique_ptr<ITransport> inner,
                                                     const NetSimSettings &settings)
{
	return std::make_unique<SimulatedTransport>(std::move(inner), settings);
}

}  // namespace net
