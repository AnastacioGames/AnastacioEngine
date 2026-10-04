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

/** \file NET_Clock.h
 *  \ingroup network
 *  \brief Client estimate of the server clock and adaptive interpolation delay (plan, section 5).
 *
 * Fed with the Ping/Pong samples of ClientSession (ClientSession::lastPong) and with the
 * arrival time of each snapshot. Time is given by the caller in milliseconds.
 */

#ifndef __NET_CLOCK_H__
#define __NET_CLOCK_H__

#include "NET_Types.h"

namespace net {

struct ClockConfig {
	uint16_t tickRate = 60;
	uint16_t snapshotRate = 20;
	/// Snapshots kept between the render time and the newest snapshot, before jitter.
	float bufferSnapshots = 2.0f;
	/// interp_delay = bufferSnapshots * snapshot interval + jitterFactor * jitter.
	float jitterFactor = 3.0f;
	float minDelayMs = 0.0f;
	float maxDelayMs = 500.0f;
	/// The delay rises at once and falls at most this many ms per second of local time.
	float decreaseMsPerSecond = 20.0f;
	/// Offset error above this jumps instead of being smoothed.
	float resyncMs = 250.0f;
	/// EMA factor of the offset (contract, section 2: alpha 0.1).
	float offsetAlpha = 0.1f;
	/// Input slack (ticks) the prediction aims for when the server reports it (provisional InputTiming).
	float targetInputSlack = 3.0f;
	/// Fraction of the slack error corrected per report.
	float inputSlackGain = 0.3f;
};

class NetClock {
public:
	explicit NetClock(const ClockConfig &config = ClockConfig());

	/// One Pong: round trip and the server tick written when the Ping arrived there.
	void addPong(float rttMs, Tick serverTick, uint64_t nowMs);
	/// A snapshot of the given server tick was received now (only new ones should be fed).
	void addSnapshot(Tick tick, uint64_t nowMs);
	/// Slack of this client's inputs measured by the server (InputTiming): moves the prediction lead so the
	/// inputs arrive about targetInputSlack ticks before they are simulated.
	void addInputSlack(float slackTicks);
	/// Ticks added to the prediction lead by addInputSlack.
	float leadAdjustTicks() const;
	/// Forgets every sample (new connection or scene).
	void reset();

	bool synced() const;
	/// Server time in ticks (fractional) at local time nowMs.
	double serverTime(uint64_t nowMs) const;
	/// Time to render remote objects at: serverTime - interpDelay, split into tick and alpha.
	void renderTime(uint64_t nowMs, Tick &tick, float &alpha) const;
	/// Tick the local player should predict now: serverTime + rtt / 2 + one tick + jitter.
	Tick predictionTick(uint64_t nowMs) const;

	float interpDelayMs() const;
	float jitterMs() const;
	float rttMs() const;
	const ClockConfig &config() const;

private:
	void updateDelay(uint64_t nowMs);
	double tickMs() const;

	ClockConfig m_config;
	bool m_synced = false;
	/// Server time in ms minus local time in ms.
	double m_offsetMs = 0.0;
	float m_rttMs = 0.0f;
	float m_leadAdjust = 0.0f;
	float m_rttJitterMs = 0.0f;
	bool m_hasTransit = false;
	double m_lastTransitMs = 0.0;
	Tick m_lastSnapshotTick = kNoTick;
	float m_snapshotJitterMs = 0.0f;
	float m_delayMs = 0.0f;
	bool m_hasDelay = false;
	uint64_t m_lastDelayMs = 0;
};

}  // namespace net

#endif  // __NET_CLOCK_H__
