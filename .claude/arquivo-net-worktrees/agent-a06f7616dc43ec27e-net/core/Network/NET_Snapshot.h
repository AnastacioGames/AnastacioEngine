/* SPDX-License-Identifier: GPL-2.0-or-later */

/** \file NET_Snapshot.h
 *  Snapshot structure and delta encoding (protocol contract v1, section 6).
 */

#pragma once

#include "NET_BitStream.h"
#include "NET_Types.h"

#include <functional>
#include <vector>

namespace net {

/** Object state fields, in wire order (one presence bit each). */
enum ObjectField : uint8_t {
	FIELD_TRANSFORM = 1 << 0, // position + rotation
	FIELD_VELOCITY = 1 << 1,
	FIELD_ANGULAR_VELOCITY = 1 << 2,
	FIELD_PROPS = 1 << 3,
	FIELD_ANIM = 1 << 4,
	FIELD_ALL = 0x1F,
};

struct PropValue {
	enum class Type : uint8_t { Bool = 0, Int = 1, Float = 2 };
	uint16_t index = 0; // property slot inside the object
	Type type = Type::Bool;
	bool b = false;
	int64_t i = 0;
	float f = 0.0f;

	static PropValue makeBool(uint16_t index, bool v);
	static PropValue makeInt(uint16_t index, int64_t v);
	static PropValue makeFloat(uint16_t index, float v);
};

struct AnimState {
	uint32_t action = 0; // game defined action index
	float frame = 0.0f;  // raw float
};

struct ObjectState {
	NetId netId = 0;
	uint8_t fields = 0; // ObjectField mask of the fields this object carries
	float position[3] = {0.0f, 0.0f, 0.0f};
	float rotation[4] = {0.0f, 0.0f, 0.0f, 1.0f}; // x, y, z, w
	float velocity[3] = {0.0f, 0.0f, 0.0f};
	float angularVelocity[3] = {0.0f, 0.0f, 0.0f};
	std::vector<PropValue> props; // sorted by index, unique
	AnimState anim;
};

struct Snapshot {
	Tick tick = 0;
	std::vector<ObjectState> objects; // sorted by netId, unique

	const ObjectState *find(NetId id) const;
	ObjectState *find(NetId id);
};

/** Float property quantization range; returned by SnapshotConfig::floatRange. */
struct FloatRange {
	float min = 0.0f;
	float max = 1.0f;
	int bits = 16; // 1..32
};

struct SnapshotConfig {
	PositionQuant position;
	int rotationBits = kDefaultRotationBits;
	float maxSpeed = kDefaultMaxSpeed;
	float maxAngSpeed = kDefaultMaxAngSpeed;
	/** Optional: range of a float property (set in the UI). Without one the float goes as raw 32 bits.
	 *  Must give the same answer on both ends. */
	std::function<bool(NetId, uint16_t, FloatRange &)> floatRange;
};

/** Writes a complete snapshot (baseline == nullptr) or a delta against baseline.
 *  Objects identical to the baseline are omitted; objects missing from cur are sent as removed.
 *  cur.objects must be sorted by netId. Returns false on error. */
bool encodeSnapshot(BitWriter &w, const Snapshot &cur, const Snapshot *baseline, const SnapshotConfig &cfg);

enum class SnapshotDecodeResult { Ok, Malformed, MissingBaseline };

/** Reads tick and baselineTick without consuming the reader. */
bool peekSnapshotHeader(const uint8_t *data, size_t size, Tick &tick, Tick &baselineTick);

/** Decodes a snapshot. baseline must be the snapshot with tick == baselineTick (ignored for complete
 *  snapshots); otherwise MissingBaseline is returned and the client should send FullStateRequest. */
SnapshotDecodeResult decodeSnapshot(BitReader &r, const Snapshot *baseline, const SnapshotConfig &cfg,
                                    Snapshot &out);

/** Complete state block of one object (presence bits + fields), used by Spawn. */
bool encodeObjectState(BitWriter &w, const ObjectState &obj, const SnapshotConfig &cfg);
bool decodeObjectState(BitReader &r, NetId netId, const SnapshotConfig &cfg, ObjectState &out);

/** Field mask of obj whose quantized value differs from base (fields missing from base count as changed). */
uint8_t changedFields(const ObjectState &obj, const ObjectState &base, const SnapshotConfig &cfg);

} // namespace net
