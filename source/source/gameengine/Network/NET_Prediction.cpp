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

/** \file gameengine/Network/NET_Prediction.cpp
 *  \ingroup network
 */

#include "NET_Prediction.h"

#include <algorithm>
#include <cmath>

namespace net {

namespace {

float distance3(const float a[3], const float b[3])
{
	const float dx = a[0] - b[0], dy = a[1] - b[1], dz = a[2] - b[2];
	return std::sqrt(dx * dx + dy * dy + dz * dz);
}

/// Ticks of how each tick was simulated kept for duplicate and late detection.
constexpr uint32_t kDoneWindow = 64;

}  // namespace

/* -------------------------------------------------------------------- */
/** \name PredictionClient
 * \{ */

PredictionClient::PredictionClient(const PredictionCallbacks &callbacks, const PredictionConfig &config)
    : m_callbacks(callbacks), m_config(config)
{
	m_config.redundancy = std::min(std::max(m_config.redundancy, 1), kMaxInputBlocks);
	m_config.historyTicks = std::max<uint32_t>(m_config.historyTicks, uint32_t(m_config.redundancy));
}

bool PredictionClient::recordInput(Tick tick, const InputBlock &block, InputMsg &msg)
{
	if (tick == kNoTick || block.size() > kMaxInputBlockBytes) {
		return false;
	}
	if (m_newest != kNoTick && tick != m_newest + 1) {
		// Gap or going back: the stored inputs no longer match the server's timeline.
		m_history.clear();
	}
	Entry &e = m_history[tick];
	e.input = block;
	e.hasState = false;
	m_newest = tick;
	++m_stats.inputsRecorded;
	prune(tick - m_config.historyTicks);

	msg.newestTick = tick;
	msg.blocks.clear();
	for (int i = 0; i < m_config.redundancy; ++i) {
		const auto it = m_history.find(tick - Tick(i));
		if (it == m_history.end() || tick - Tick(i) == kNoTick) {
			break;
		}
		msg.blocks.push_back(it->second.input);
	}
	return true;
}

void PredictionClient::recordState(Tick tick, const ObjectState &state)
{
	const auto it = m_history.find(tick);
	if (it != m_history.end()) {
		it->second.state = state;
		it->second.hasState = true;
	}
}

bool PredictionClient::reconcile(Tick tick, const ObjectState &server)
{
	if (tick == kNoTick || m_history.empty()) {
		return false;
	}
	++m_stats.reconciles;
	const auto it = m_history.find(tick);
	if (it == m_history.end() || !it->second.hasState) {
		// Older than the history, or a tick the client never predicted: nothing to compare.
		if (m_newest != kNoTick && tickNewer(tick, m_newest) && m_callbacks.setState) {
			// The server is ahead of the prediction: take its state as is.
			m_callbacks.setState(server);
			m_history.clear();
			m_offset[0] = m_offset[1] = m_offset[2] = 0.0f;
			++m_stats.teleports;
			return true;
		}
		return false;
	}

	const ObjectState &predicted = it->second.state;
	bool same = true;
	if (server.hasTransform && distance3(server.position, predicted.position) > m_config.positionEpsilon) {
		same = false;
	}
	if (server.hasVelocity && distance3(server.velocity, predicted.velocity) > m_config.velocityEpsilon) {
		same = false;
	}
	if (same || !m_callbacks.setState || !m_callbacks.replay || !m_callbacks.getState) {
		prune(tick);
		return false;
	}

	ObjectState before;
	const bool hasBefore = m_callbacks.getState(before);
	m_callbacks.setState(server);
	it->second.state = server;
	for (auto next = std::next(it); next != m_history.end(); ++next) {
		m_callbacks.replay(next->first, next->second.input);
		next->second.hasState = m_callbacks.getState(next->second.state);
	}
	prune(tick);

	ObjectState after;
	if (hasBefore && m_callbacks.getState(after) && before.hasTransform && after.hasTransform) {
		float total[3];
		for (int i = 0; i < 3; ++i) {
			total[i] = m_offset[i] + before.position[i] - after.position[i];
		}
		const float zero[3] = {0.0f, 0.0f, 0.0f};
		const float error = distance3(before.position, after.position);
		m_stats.lastError = error;
		m_stats.maxError = std::max(m_stats.maxError, error);
		if (!(distance3(total, zero) <= m_config.teleportDistance)) {
			m_offset[0] = m_offset[1] = m_offset[2] = 0.0f;
			++m_stats.teleports;
		}
		else {
			std::copy(total, total + 3, m_offset);
		}
	}
	++m_stats.corrections;
	return true;
}

void PredictionClient::update(float dtMs)
{
	if (!(dtMs > 0.0f)) {
		return;
	}
	const float k = m_config.smoothingMs > 0.0f ? std::exp(-dtMs / m_config.smoothingMs) : 0.0f;
	for (float &o : m_offset) {
		o *= k;
		if (std::fabs(o) < 1e-5f) {
			o = 0.0f;
		}
	}
}

void PredictionClient::visualOffset(float offset[3]) const
{
	std::copy(m_offset, m_offset + 3, offset);
}

void PredictionClient::reset()
{
	m_history.clear();
	m_newest = kNoTick;
	m_offset[0] = m_offset[1] = m_offset[2] = 0.0f;
}

Tick PredictionClient::newestTick() const
{
	return m_newest;
}

const PredictionStats &PredictionClient::stats() const
{
	return m_stats;
}

void PredictionClient::prune(Tick keepAfter)
{
	// Keeps ticks newer than keepAfter (wrap-aware).
	for (auto it = m_history.begin(); it != m_history.end();) {
		if (!tickNewer(it->first, keepAfter)) {
			it = m_history.erase(it);
		}
		else {
			++it;
		}
	}
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name InputQueue
 * \{ */

InputQueue::InputQueue(const InputQueueConfig &config) : m_config(config)
{
	m_config.maxRepeatTicks = std::max(m_config.maxRepeatTicks, 0);
	m_config.maxAheadTicks = std::max<uint32_t>(m_config.maxAheadTicks, 1);
}

void InputQueue::receive(const InputMsg &msg, Tick nextTick)
{
	if (msg.newestTick != kNoTick && !msg.blocks.empty()) {
		const float slack = float(int32_t(msg.newestTick - nextTick));
		m_slack = m_hasSlack ? m_slack + (slack - m_slack) * 0.1f : slack;
		m_hasSlack = true;
	}
	for (size_t i = 0; i < msg.blocks.size(); ++i) {
		const Tick t = msg.newestTick - Tick(i);
		if (t == kNoTick) {
			break;
		}
		const bool consumed = m_lastConsumed != kNoTick && !tickNewer(t, m_lastConsumed);
		if (consumed || !tickNewer(t, nextTick - 1)) {
			// Too old to be applied: a repeat of an applied tick, or a late input.
			const auto done = m_done.find(t);
			if (done == m_done.end()) {
				++m_stats.late;
			}
			else if (done->second == TICK_MISSED) {
				done->second = TICK_LATE;
				++m_stats.late;
			}
			else {
				++m_stats.duplicates;
			}
			continue;
		}
		if (tickNewer(t, nextTick + m_config.maxAheadTicks)) {
			++m_stats.tooFar;
			continue;
		}
		if (m_pending.count(t)) {
			++m_stats.duplicates;
			continue;
		}
		m_pending.emplace(t, msg.blocks[i]);
		++m_stats.received;
	}
}

bool InputQueue::consume(Tick tick, InputBlock &out, bool *repeated)
{
	if (repeated) {
		*repeated = false;
	}
	if (tick == kNoTick || (m_lastConsumed != kNoTick && !tickNewer(tick, m_lastConsumed))) {
		return false;
	}
	// Inputs for ticks skipped by the caller can no longer be applied.
	while (!m_pending.empty() && tickNewer(tick, m_pending.begin()->first)) {
		m_pending.erase(m_pending.begin());
	}
	m_lastConsumed = tick;
	m_done.emplace(tick, TICK_MISSED);
	while (!m_done.empty() && tick - m_done.begin()->first >= kDoneWindow) {
		m_done.erase(m_done.begin());
	}

	const auto it = m_pending.find(tick);
	if (it != m_pending.end()) {
		m_last = std::move(it->second);
		m_pending.erase(it);
		m_hasLast = true;
		m_repeats = 0;
		m_done[tick] = TICK_REAL;
		++m_stats.applied;
		out = m_last;
		return true;
	}
	if (m_hasLast && m_repeats < m_config.maxRepeatTicks) {
		++m_repeats;
		++m_stats.repeated;
		out = m_last;
		if (repeated) {
			*repeated = true;
		}
		return true;
	}
	++m_stats.missing;
	return false;
}

void InputQueue::reset()
{
	const InputQueueStats stats = m_stats;
	*this = InputQueue(m_config);
	m_stats = stats;
}

bool InputQueue::slack(float &ticks) const
{
	ticks = m_slack;
	return m_hasSlack;
}

void InputQueue::countInvalid()
{
	++m_stats.invalid;
}

Tick InputQueue::lastConsumedTick() const
{
	return m_lastConsumed;
}

size_t InputQueue::pending() const
{
	return m_pending.size();
}

const InputQueueStats &InputQueue::stats() const
{
	return m_stats;
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name PredictionServer
 * \{ */

PredictionServer::PredictionServer(const InputQueueConfig &config) : m_config(config)
{
}

bool PredictionServer::handleEvent(const SessionEvent &event, Tick nextTick)
{
	switch (event.type) {
		case SessionEvent::Type::ClientJoined:
			// New connection: the client restarts its input timeline.
			m_queues.erase(event.client);
			m_queues.emplace(event.client, InputQueue(m_config));
			return false;
		case SessionEvent::Type::ClientLeft:
		case SessionEvent::Type::ClientExpired:
			m_queues.erase(event.client);
			return false;
		case SessionEvent::Type::Message:
			break;
		default:
			return false;
	}
	if (event.messageType != uint8_t(MessageType::Input)) {
		return false;
	}
	auto it = m_queues.find(event.client);
	if (it == m_queues.end()) {
		it = m_queues.emplace(event.client, InputQueue(m_config)).first;
	}
	RawMessage raw;
	raw.type = event.messageType;
	raw.body = event.body.data();
	raw.size = event.body.size();
	InputMsg msg;
	if (!decodeMessage(raw, msg)) {
		// Counted here; the session has no hook to add a violation (NOTES-F.md).
		it->second.countInvalid();
		return true;
	}
	it->second.receive(msg, nextTick);
	return true;
}

bool PredictionServer::consume(ClientId client, Tick tick, InputBlock &out, bool *repeated)
{
	InputQueue *q = queue(client);
	if (!q) {
		if (repeated) {
			*repeated = false;
		}
		return false;
	}
	return q->consume(tick, out, repeated);
}

InputQueue *PredictionServer::queue(ClientId client)
{
	const auto it = m_queues.find(client);
	return it == m_queues.end() ? nullptr : &it->second;
}

const InputQueue *PredictionServer::queue(ClientId client) const
{
	const auto it = m_queues.find(client);
	return it == m_queues.end() ? nullptr : &it->second;
}

/** \} */

}  // namespace net
