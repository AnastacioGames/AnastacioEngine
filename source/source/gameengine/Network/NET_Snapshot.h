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

/** \file NET_Snapshot.h
 *  \ingroup network
 *  \brief Object state snapshots, delta encoding and interpolation buffer (contract section 6).
 */

#ifndef __NET_SNAPSHOT_H__
#define __NET_SNAPSHOT_H__

#include "NET_BitStream.h"
#include "NET_Types.h"

#include <functional>
#include <vector>

namespace net {

enum class PropKind : uint8_t {
	Bool = 0,
	Int = 1,
	Float = 2,
};

struct PropValue {
	PropKind kind = PropKind::Bool;
	bool b = false;
	int64_t i = 0;
	float f = 0.0f;

	static PropValue makeBool(bool v);
	static PropValue makeInt(int64_t v);
	static PropValue makeFloat(float v);
};

/// Replicated property layout, shared by server and client (from the editor UI).
/// Float with bits == 0 is sent as raw 32 bits, otherwise quantized over [min, max].
struct PropertyDesc {
	PropKind kind = PropKind::Bool;
	float min = 0.0f;
	float max = 0.0f;
	int bits = 0;
};

struct AnimState {
	uint32_t action = 0;
	float frame = 0.0f;
	float speed = 1.0f;
};

struct ObjectState {
	NetId id = kInvalidNetId;

	bool hasTransform = false;
	float position[3] = {0.0f, 0.0f, 0.0f};
	float rotation[4] = {0.0f, 0.0f, 0.0f, 1.0f};  // x,y,z,w

	bool hasVelocity = false;
	float velocity[3] = {0.0f, 0.0f, 0.0f};

	bool hasAngularVelocity = false;
	float angularVelocity[3] = {0.0f, 0.0f, 0.0f};

	std::vector<PropValue> props;

	bool hasAnim = false;
	AnimState anim;
};

struct SnapshotConfig {
	PositionQuant position;
	int rotationBits = kDefaultRotationBits;
	float maxSpeed = 100.0f;
	float maxAngSpeed = 50.0f;
	/// Property layout of an object; may be empty when no object has properties.
	std::function<const std::vector<PropertyDesc> *(NetId)> schema;
};

struct Snapshot {
	Tick tick = kNoTick;
	Tick baselineTick = kNoTick;
	/// Full state after applying the delta, sorted by NetId.
	std::vector<ObjectState> objects;

	const ObjectState *find(NetId id) const;
};

/// Writes the five field presence bits and data of one object. With a baseline, only fields
/// whose quantized value differs are written. Returns false on invalid input.
bool encodeObjectFields(BitWriter &w, const ObjectState &state, const ObjectState *baseline,
                        const SnapshotConfig &config);
/// Reads fields on top of state (which holds the baseline values, if any).
bool decodeObjectFields(BitReader &r, ObjectState &state, bool hasBaseline, const SnapshotConfig &config);
/// True when the object would be sent with changed = 1 against the baseline.
bool objectChanged(const ObjectState &state, const ObjectState &baseline, const SnapshotConfig &config);

/// Encodes a Snapshot message body. objects must be sorted by NetId, unique and non zero.
/// baseline == nullptr writes a full snapshot (baselineTick = 0).
bool encodeSnapshot(BitWriter &w, Tick tick, const std::vector<ObjectState> &objects,
                    const Snapshot *baseline, const SnapshotConfig &config);
/// Decodes a Snapshot message body. baseline must match the body's baselineTick (or be ignored
/// when it is 0). Fails if the needed baseline is missing.
bool decodeSnapshot(BitReader &r, const Snapshot *baseline, const SnapshotConfig &config, Snapshot &out);
/// Reads only tick and baselineTick, to look up the baseline before decoding.
bool readSnapshotHeader(const uint8_t *data, size_t size, Tick &tick, Tick &baselineTick);

/// Circular buffer of received snapshots, ordered by tick, with interpolation.
class SnapshotBuffer {
public:
	explicit SnapshotBuffer(size_t capacity = kSnapshotHistory);

	/// Inserts in tick order; replaces a snapshot with the same tick, drops the oldest when full.
	/// Returns false (and ignores it) when it is older than everything in a full buffer.
	bool insert(const Snapshot &snapshot);
	const Snapshot *find(Tick tick) const;
	const Snapshot *newest() const;
	const Snapshot *oldest() const;
	size_t size() const;
	void clear();

	/// Interpolated state at renderTick + alpha (alpha in [0, 1)). Positions and velocities are
	/// lerped, rotations slerped; properties and animation come from the older snapshot.
	/// Objects missing from the newer snapshot are kept as in the older one. Past the newest
	/// snapshot the newest state is returned (no extrapolation). Returns false if empty or
	/// renderTick is before the oldest snapshot.
	bool sample(Tick renderTick, float alpha, std::vector<ObjectState> &out) const;

private:
	size_t m_capacity;
	std::vector<Snapshot> m_snapshots;  // oldest first
};

/// Spherical interpolation of x,y,z,w quaternions along the shortest path.
void slerp(const float a[4], const float b[4], float t, float out[4]);

}  // namespace net

#endif  // __NET_SNAPSHOT_H__
