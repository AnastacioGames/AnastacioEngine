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

/** \file gameengine/Network/NET_Clock.cpp
 *  \ingroup network
 */

#include "NET_Clock.h"

#include <algorithm>
#include <cmath>

namespace net {

namespace {

/// Jitter smoothing as in RFC 3550 (1/16 per sample).
constexpr float kJitterGain = 1.0f / 16.0f;

}  // namespace

NetClock::NetClock(const ClockConfig &config) : m_config(config)
{
	if (m_config.tickRate == 0) {
		m_config.tickRate = 60;
	}
	if (m_config.snapshotRate == 0) {
		m_config.snapshotRate = m_config.tickRate;
	}
}

double NetClock::tickMs() const
{
	return 1000.0 / double(m_config.tickRate);
}

void NetClock::addPong(float rttMs, Tick serverTick, uint64_t nowMs)
{
	if (!(rttMs >= 0.0f) || rttMs > 60000.0f || serverTick == kNoTick) {
		return;
	}
	if (!m_synced) {
		m_rttMs = rttMs;
	}
	else {
		m_rttJitterMs += (std::fabs(rttMs - m_rttMs) - m_rttJitterMs) * kJitterGain;
		m_rttMs += (rttMs - m_rttMs) * 0.1f;
	}

	// The tick was read on the server half a round trip ago.
	const double sample = double(serverTick) * tickMs() + double(rttMs) / 2.0 - double(nowMs);
	if (!m_synced || std::fabs(sample - m_offsetMs) > double(m_config.resyncMs)) {
		m_offsetMs = sample;
		m_synced = true;
	}
	else {
		m_offsetMs += (sample - m_offsetMs) * double(m_config.offsetAlpha);
	}
	updateDelay(nowMs);
}

void NetClock::addSnapshot(Tick tick, uint64_t nowMs)
{
	if (tick == kNoTick) {
		return;
	}
	if (m_lastSnapshotTick != kNoTick && !tickNewer(tick, m_lastSnapshotTick)) {
		return;
	}
	m_lastSnapshotTick = tick;
	// Transit time up to a constant (the clock offset); its variation is the jitter.
	const double transit = double(nowMs) - double(tick) * tickMs();
	if (m_hasTransit) {
		const float d = float(std::fabs(transit - m_lastTransitMs));
		m_snapshotJitterMs += (std::min(d, 1000.0f) - m_snapshotJitterMs) * kJitterGain;
	}
	m_lastTransitMs = transit;
	m_hasTransit = true;
	updateDelay(nowMs);
}

void NetClock::reset()
{
	*this = NetClock(m_config);
}

void NetClock::updateDelay(uint64_t nowMs)
{
	const float interval = 1000.0f / float(m_config.snapshotRate);
	float target = m_config.bufferSnapshots * interval + m_config.jitterFactor * jitterMs();
	target = std::min(std::max(target, m_config.minDelayMs), m_config.maxDelayMs);
	if (!m_hasDelay || target >= m_delayMs) {
		m_delayMs = target;
	}
	else {
		const float elapsed = nowMs > m_lastDelayMs ? float(nowMs - m_lastDelayMs) / 1000.0f : 0.0f;
		m_delayMs = std::max(target, m_delayMs - m_config.decreaseMsPerSecond * elapsed);
	}
	m_hasDelay = true;
	m_lastDelayMs = nowMs;
}

bool NetClock::synced() const
{
	return m_synced;
}

double NetClock::serverTime(uint64_t nowMs) const
{
	return std::max(0.0, (double(nowMs) + m_offsetMs) / tickMs());
}

void NetClock::renderTime(uint64_t nowMs, Tick &tick, float &alpha) const
{
	const double t = std::max(0.0, serverTime(nowMs) - double(interpDelayMs()) / tickMs());
	const double whole = std::floor(t);
	tick = Tick(uint64_t(whole));
	alpha = std::min(float(t - whole), 0.999f);
}

Tick NetClock::predictionTick(uint64_t nowMs) const
{
	const double lead = (double(m_rttMs) / 2.0 + double(jitterMs())) / tickMs() + 2.0;
	return Tick(uint64_t(std::ceil(serverTime(nowMs) + lead)));
}

float NetClock::interpDelayMs() const
{
	if (m_hasDelay) {
		return m_delayMs;
	}
	return std::min(m_config.bufferSnapshots * 1000.0f / float(m_config.snapshotRate), m_config.maxDelayMs);
}

float NetClock::jitterMs() const
{
	return std::max(m_snapshotJitterMs, m_rttJitterMs / 2.0f);
}

float NetClock::rttMs() const
{
	return m_rttMs;
}

const ClockConfig &NetClock::config() const
{
	return m_config;
}

}  // namespace net
