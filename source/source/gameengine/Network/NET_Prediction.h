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

/** \file NET_Prediction.h
 *  \ingroup network
 *  \brief Client side prediction with reconciliation and server input queues (plan section 5,
 *  contract section 7).
 *
 * Input ticks are server ticks: the client predicts tick T ahead of the server (see
 * NetClock::predictionTick) and the server applies the input of T when it simulates T. The
 * server state of tick T sent back to the client already includes the input of T.
 */

#ifndef __NET_PREDICTION_H__
#define __NET_PREDICTION_H__

#include "NET_Messages.h"
#include "NET_Session.h"
#include "NET_Snapshot.h"
#include "NET_Types.h"

#include <functional>
#include <map>
#include <vector>

namespace net {

using InputBlock = std::vector<uint8_t>;

/* -------------------------------------------------------------------- */
/** \name Client
 * \{ */

struct PredictionConfig {
	/// Blocks per Input message, newest first (1 to kMaxInputBlocks).
	int redundancy = kMaxInputBlocks;
	/// Ticks of input and predicted state kept for replay.
	uint32_t historyTicks = 128;
	/// Time constant of the visual correction: the error decays to 37% in this many ms.
	float smoothingMs = 100.0f;
	/// Corrections longer than this (meters) teleport instead of being smoothed.
	float teleportDistance = 2.0f;
	/// Server and predicted state closer than this are taken as equal (meters, m/s).
	float positionEpsilon = 0.002f;
	float velocityEpsilon = 0.01f;
};

/// Game hooks. replay applies the input of a tick to the current state and steps one tick.
struct PredictionCallbacks {
	std::function<void(const ObjectState &state)> setState;
	std::function<void(Tick tick, const InputBlock &input)> replay;
	std::function<bool(ObjectState &state)> getState;
};

struct PredictionStats {
	uint32_t inputsRecorded = 0;
	uint32_t reconciles = 0;
	uint32_t corrections = 0;
	uint32_t teleports = 0;
	/// Size of the last correction and the largest one, in meters.
	float lastError = 0.0f;
	float maxError = 0.0f;
};

class PredictionClient {
public:
	explicit PredictionClient(const PredictionCallbacks &callbacks,
	                          const PredictionConfig &config = PredictionConfig());

	/// Stores the input of tick and fills msg with it and the previous contiguous ones.
	/// Ticks must grow by one; a gap or a tick not newer than the last one resets the history.
	bool recordInput(Tick tick, const InputBlock &block, InputMsg &msg);
	/// Stores the state predicted after the input of tick was applied.
	void recordState(Tick tick, const ObjectState &state);
	/// Server state of tick. Rewinds and replays the later inputs when it differs from the
	/// prediction; returns true when a correction was made.
	bool reconcile(Tick tick, const ObjectState &server);
	/// Decays the visual offset.
	void update(float dtMs);
	/// Offset to add to the simulated position when rendering.
	void visualOffset(float offset[3]) const;
	void reset();

	Tick newestTick() const;
	const PredictionStats &stats() const;

private:
	struct Entry {
		InputBlock input;
		ObjectState state;
		bool hasState = false;
	};

	void prune(Tick keepAfter);

	PredictionCallbacks m_callbacks;
	PredictionConfig m_config;
	std::map<Tick, Entry> m_history;
	Tick m_newest = kNoTick;
	float m_offset[3] = {0.0f, 0.0f, 0.0f};
	PredictionStats m_stats;
};

/** \} */

/* -------------------------------------------------------------------- */
/** \name Server
 * \{ */

struct InputQueueConfig {
	/// Ticks the last input is repeated for when the next one is missing.
	int maxRepeatTicks = 4;
	/// Inputs further ahead of the next tick to apply are dropped (anti-abuse).
	uint32_t maxAheadTicks = 64;
};

struct InputQueueStats {
	uint32_t received = 0;  // new blocks stored
	uint32_t duplicates = 0;  // blocks seen before (redundancy)
	uint32_t late = 0;  // inputs that arrived after their tick was simulated (once per tick in the last 64)
	uint32_t tooFar = 0;  // blocks beyond maxAheadTicks
	uint32_t applied = 0;  // ticks simulated with the real input
	uint32_t repeated = 0;  // ticks simulated with the last input repeated
	uint32_t missing = 0;  // ticks simulated without input
	uint32_t invalid = 0;  // Input messages that failed to decode
};

/// Inputs of one client. Each tick is applied once and in order; repeats are dropped.
class InputQueue {
public:
	explicit InputQueue(const InputQueueConfig &config = InputQueueConfig());

	/// Stores the blocks of one Input message. nextTick is the next tick consume() will get.
	void receive(const InputMsg &msg, Tick nextTick);
	/// Input to simulate tick with. Call once per tick, in order. Returns false when there is
	/// none (no input yet, or the last one was already repeated maxRepeatTicks times).
	bool consume(Tick tick, InputBlock &out, bool *repeated = nullptr);
	void reset();
	/// Counts an Input message that failed to decode.
	void countInvalid();

	Tick lastConsumedTick() const;
	size_t pending() const;
	const InputQueueStats &stats() const;

private:
	enum : uint8_t { TICK_REAL = 1, TICK_MISSED = 2, TICK_LATE = 3 };

	InputQueueConfig m_config;
	std::map<Tick, InputBlock> m_pending;
	/// How each recent tick was simulated (last 64 ticks).
	std::map<Tick, uint8_t> m_done;
	Tick m_lastConsumed = kNoTick;
	InputBlock m_last;
	bool m_hasLast = false;
	int m_repeats = 0;
	InputQueueStats m_stats;
};

/// Input queues of every client, fed with the session's Input message events.
class PredictionServer {
public:
	explicit PredictionServer(const InputQueueConfig &config = InputQueueConfig());

	/// Takes Input messages and client join/leave events. Returns true when the event was
	/// an Input message (valid or not). nextTick is the next tick the server will simulate.
	bool handleEvent(const SessionEvent &event, Tick nextTick);
	bool consume(ClientId client, Tick tick, InputBlock &out, bool *repeated = nullptr);
	InputQueue *queue(ClientId client);
	const InputQueue *queue(ClientId client) const;

private:
	InputQueueConfig m_config;
	std::map<ClientId, InputQueue> m_queues;
};

/** \} */

}  // namespace net

#endif  // __NET_PREDICTION_H__
