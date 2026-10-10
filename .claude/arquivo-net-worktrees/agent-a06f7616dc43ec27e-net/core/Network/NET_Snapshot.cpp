/* SPDX-License-Identifier: GPL-2.0-or-later */

/** \file NET_Snapshot.cpp
 */

#include "NET_Snapshot.h"
#include "NET_SnapshotBuffer.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <map>

namespace net {

PropValue PropValue::makeBool(uint16_t index, bool v)
{
	PropValue p;
	p.index = index;
	p.type = Type::Bool;
	p.b = v;
	return p;
}

PropValue PropValue::makeInt(uint16_t index, int64_t v)
{
	PropValue p;
	p.index = index;
	p.type = Type::Int;
	p.i = v;
	return p;
}

PropValue PropValue::makeFloat(uint16_t index, float v)
{
	PropValue p;
	p.index = index;
	p.type = Type::Float;
	p.f = v;
	return p;
}

static bool lessById(const ObjectState &o, NetId id)
{
	return o.netId < id;
}

const ObjectState *Snapshot::find(NetId id) const
{
	auto it = std::lower_bound(objects.begin(), objects.end(), id, lessById);
	return (it != objects.end() && it->netId == id) ? &*it : nullptr;
}

ObjectState *Snapshot::find(NetId id)
{
	auto it = std::lower_bound(objects.begin(), objects.end(), id, lessById);
	return (it != objects.end() && it->netId == id) ? &*it : nullptr;
}

/* -------------------------------------------------------------------- */
/* Field comparison on quantized values (deterministic). */

/* Wire tag of a property value (2 bits). */
enum PropTag : uint32_t { TAG_BOOL = 0, TAG_INT = 1, TAG_FLOAT_RAW = 2, TAG_FLOAT_QUANT = 3 };

static bool lookupRange(const SnapshotConfig &cfg, NetId id, uint16_t index, FloatRange &range)
{
	if (!cfg.floatRange || !cfg.floatRange(id, index, range)) {
		return false;
	}
	return range.bits >= 1 && range.bits <= 32 && range.max > range.min;
}

static uint32_t floatBits(float f)
{
	uint32_t u;
	std::memcpy(&u, &f, sizeof(u));
	return u;
}

static bool samePosition(const ObjectState &a, const ObjectState &b, const SnapshotConfig &cfg)
{
	for (int i = 0; i < 3; ++i) {
		if (quantizePositionAxis(a.position[i], cfg.position.bitsPerAxis) !=
		    quantizePositionAxis(b.position[i], cfg.position.bitsPerAxis))
		{
			return false;
		}
	}
	return quantizeRotation(a.rotation, cfg.rotationBits) == quantizeRotation(b.rotation, cfg.rotationBits);
}

static bool sameVec(const float a[3], const float b[3], float range, int bits)
{
	for (int i = 0; i < 3; ++i) {
		if (quantizeRange(a[i], -range, range, bits) != quantizeRange(b[i], -range, range, bits)) {
			return false;
		}
	}
	return true;
}

static bool sameProp(const PropValue &a, const PropValue &b, NetId id, const SnapshotConfig &cfg)
{
	if (a.type != b.type) {
		return false;
	}
	switch (a.type) {
		case PropValue::Type::Bool:
			return a.b == b.b;
		case PropValue::Type::Int:
			return a.i == b.i;
		case PropValue::Type::Float: {
			FloatRange range;
			if (lookupRange(cfg, id, a.index, range)) {
				return quantizeRange(a.f, range.min, range.max, range.bits) ==
				       quantizeRange(b.f, range.min, range.max, range.bits);
			}
			return floatBits(a.f) == floatBits(b.f);
		}
	}
	return false;
}

static const PropValue *findProp(const std::vector<PropValue> &props, uint16_t index)
{
	for (const PropValue &p : props) {
		if (p.index == index) {
			return &p;
		}
	}
	return nullptr;
}

static void changedProps(const ObjectState &obj, const ObjectState &base, const SnapshotConfig &cfg,
                         std::vector<PropValue> &out)
{
	out.clear();
	const bool baseHas = (base.fields & FIELD_PROPS) != 0;
	for (const PropValue &p : obj.props) {
		const PropValue *bp = baseHas ? findProp(base.props, p.index) : nullptr;
		if (!bp || !sameProp(p, *bp, obj.netId, cfg)) {
			out.push_back(p);
		}
	}
}

uint8_t changedFields(const ObjectState &obj, const ObjectState &base, const SnapshotConfig &cfg)
{
	uint8_t mask = 0;
	const uint8_t newFields = uint8_t(obj.fields & ~base.fields);
	mask |= newFields;
	const uint8_t common = uint8_t(obj.fields & base.fields);
	if ((common & FIELD_TRANSFORM) && !samePosition(obj, base, cfg)) {
		mask |= FIELD_TRANSFORM;
	}
	if ((common & FIELD_VELOCITY) && !sameVec(obj.velocity, base.velocity, cfg.maxSpeed, kVelocityBits)) {
		mask |= FIELD_VELOCITY;
	}
	if ((common & FIELD_ANGULAR_VELOCITY) &&
	    !sameVec(obj.angularVelocity, base.angularVelocity, cfg.maxAngSpeed, kAngVelocityBits))
	{
		mask |= FIELD_ANGULAR_VELOCITY;
	}
	if (common & FIELD_PROPS) {
		std::vector<PropValue> diff;
		changedProps(obj, base, cfg, diff);
		if (!diff.empty()) {
			mask |= FIELD_PROPS;
		}
	}
	if ((common & FIELD_ANIM) &&
	    (obj.anim.action != base.anim.action || floatBits(obj.anim.frame) != floatBits(base.anim.frame)))
	{
		mask |= FIELD_ANIM;
	}
	return mask;
}

/* -------------------------------------------------------------------- */
/* Field encoding: 5 presence bits (transform, velocity, angularVelocity, props, anim), then the
 * present fields in the same order. */

static void writeProps(BitWriter &w, NetId id, const std::vector<PropValue> &props, const SnapshotConfig &cfg)
{
	w.writeVarU(props.size());
	int prev = -1;
	for (const PropValue &p : props) {
		if (int(p.index) <= prev) {
			w.fail(); // must be sorted and unique
			return;
		}
		prev = p.index;
		w.writeVarU(p.index);
		switch (p.type) {
			case PropValue::Type::Bool:
				w.writeBits(TAG_BOOL, 2);
				w.writeBool(p.b);
				break;
			case PropValue::Type::Int:
				w.writeBits(TAG_INT, 2);
				w.writeVarI(p.i);
				break;
			case PropValue::Type::Float: {
				FloatRange range;
				if (lookupRange(cfg, id, p.index, range)) {
					w.writeBits(TAG_FLOAT_QUANT, 2);
					w.writeQuantized(p.f, range.min, range.max, range.bits);
				}
				else {
					w.writeBits(TAG_FLOAT_RAW, 2);
					w.writeFloat(p.f);
				}
				break;
			}
			default:
				w.fail();
				return;
		}
	}
}

static bool readProps(BitReader &r, NetId id, const SnapshotConfig &cfg, std::vector<PropValue> &out)
{
	out.clear();
	const uint64_t count = r.readVarU();
	if (!r.ok() || count > 0xFFFF || count * 11 > r.bitsRemaining()) {
		r.fail();
		return false;
	}
	int prev = -1;
	for (uint64_t k = 0; k < count; ++k) {
		const uint64_t index = r.readVarU();
		if (!r.ok() || index > 0xFFFF || int(index) <= prev) {
			r.fail();
			return false;
		}
		prev = int(index);
		PropValue p;
		p.index = uint16_t(index);
		const uint32_t tag = r.readBits(2);
		switch (tag) {
			case TAG_BOOL:
				p.type = PropValue::Type::Bool;
				p.b = r.readBool();
				break;
			case TAG_INT:
				p.type = PropValue::Type::Int;
				p.i = r.readVarI();
				break;
			case TAG_FLOAT_RAW:
				p.type = PropValue::Type::Float;
				p.f = r.readFloat();
				break;
			default: {
				p.type = PropValue::Type::Float;
				FloatRange range;
				if (!lookupRange(cfg, id, p.index, range)) {
					r.fail();
					return false;
				}
				p.f = r.readQuantized(range.min, range.max, range.bits);
				break;
			}
		}
		if (!r.ok()) {
			return false;
		}
		out.push_back(p);
	}
	return true;
}

static void writeFields(BitWriter &w, const ObjectState &obj, uint8_t mask, const std::vector<PropValue> &props,
                        const SnapshotConfig &cfg)
{
	w.writeBool(mask & FIELD_TRANSFORM);
	w.writeBool(mask & FIELD_VELOCITY);
	w.writeBool(mask & FIELD_ANGULAR_VELOCITY);
	w.writeBool(mask & FIELD_PROPS);
	w.writeBool(mask & FIELD_ANIM);
	if (mask & FIELD_TRANSFORM) {
		writePosition(w, obj.position, cfg.position);
		writeRotation(w, obj.rotation, cfg.rotationBits);
	}
	if (mask & FIELD_VELOCITY) {
		for (int i = 0; i < 3; ++i) {
			w.writeQuantized(obj.velocity[i], -cfg.maxSpeed, cfg.maxSpeed, kVelocityBits);
		}
	}
	if (mask & FIELD_ANGULAR_VELOCITY) {
		for (int i = 0; i < 3; ++i) {
			w.writeQuantized(obj.angularVelocity[i], -cfg.maxAngSpeed, cfg.maxAngSpeed, kAngVelocityBits);
		}
	}
	if (mask & FIELD_PROPS) {
		writeProps(w, obj.netId, props, cfg);
	}
	if (mask & FIELD_ANIM) {
		w.writeVarU(obj.anim.action);
		w.writeFloat(obj.anim.frame);
	}
}

/* Reads fields on top of obj (fields not present keep their value). */
static bool readFields(BitReader &r, const SnapshotConfig &cfg, ObjectState &obj)
{
	uint8_t mask = 0;
	for (int i = 0; i < 5; ++i) {
		if (r.readBool()) {
			mask |= uint8_t(1 << i);
		}
	}
	if (mask & FIELD_TRANSFORM) {
		readPosition(r, obj.position, cfg.position);
		readRotation(r, obj.rotation, cfg.rotationBits);
	}
	if (mask & FIELD_VELOCITY) {
		for (int i = 0; i < 3; ++i) {
			obj.velocity[i] = r.readQuantized(-cfg.maxSpeed, cfg.maxSpeed, kVelocityBits);
		}
	}
	if (mask & FIELD_ANGULAR_VELOCITY) {
		for (int i = 0; i < 3; ++i) {
			obj.angularVelocity[i] = r.readQuantized(-cfg.maxAngSpeed, cfg.maxAngSpeed, kAngVelocityBits);
		}
	}
	if (mask & FIELD_PROPS) {
		std::vector<PropValue> props;
		if (!readProps(r, obj.netId, cfg, props)) {
			return false;
		}
		/* Merge by index. */
		for (const PropValue &p : props) {
			auto it = std::lower_bound(obj.props.begin(), obj.props.end(), p.index,
			                           [](const PropValue &a, uint16_t idx) { return a.index < idx; });
			if (it != obj.props.end() && it->index == p.index) {
				*it = p;
			}
			else {
				obj.props.insert(it, p);
			}
		}
	}
	if (mask & FIELD_ANIM) {
		const uint64_t action = r.readVarU();
		if (action > 0xFFFFFFFFu) {
			r.fail();
		}
		obj.anim.action = uint32_t(action);
		obj.anim.frame = r.readFloat();
	}
	obj.fields |= mask;
	return r.ok();
}

static bool validConfig(const SnapshotConfig &cfg)
{
	return cfg.position.bitsPerAxis >= 16 && cfg.position.bitsPerAxis <= 32 &&
	       cfg.rotationBits >= kMinRotationBits && cfg.rotationBits <= kMaxRotationBits &&
	       cfg.maxSpeed > 0.0f && cfg.maxAngSpeed > 0.0f;
}

bool encodeObjectState(BitWriter &w, const ObjectState &obj, const SnapshotConfig &cfg)
{
	if (!validConfig(cfg)) {
		w.fail();
		return false;
	}
	writeFields(w, obj, uint8_t(obj.fields & FIELD_ALL), obj.props, cfg);
	w.alignToByte();
	return w.ok();
}

bool decodeObjectState(BitReader &r, NetId netId, const SnapshotConfig &cfg, ObjectState &out)
{
	out = ObjectState();
	out.netId = netId;
	if (!validConfig(cfg)) {
		r.fail();
		return false;
	}
	if (!readFields(r, cfg, out)) {
		out = ObjectState();
		return false;
	}
	r.alignToByte();
	return r.ok();
}

/* -------------------------------------------------------------------- */
/* Snapshot */

namespace {
struct Entry {
	const ObjectState *obj; // nullptr = removed
	NetId netId;
	uint8_t mask;
	std::vector<PropValue> props;
};
} // namespace

bool encodeSnapshot(BitWriter &w, const Snapshot &cur, const Snapshot *baseline, const SnapshotConfig &cfg)
{
	if (!validConfig(cfg) || (baseline && baseline->tick == 0)) {
		w.fail();
		return false;
	}
	for (size_t i = 0; i < cur.objects.size(); ++i) {
		if (cur.objects[i].netId == 0 || (i > 0 && cur.objects[i].netId <= cur.objects[i - 1].netId)) {
			w.fail();
			return false;
		}
	}

	static const std::vector<ObjectState> empty;
	const std::vector<ObjectState> &base = baseline ? baseline->objects : empty;

	std::vector<Entry> entries;
	size_t ci = 0, bi = 0;
	while (ci < cur.objects.size() || bi < base.size()) {
		const ObjectState *c = ci < cur.objects.size() ? &cur.objects[ci] : nullptr;
		const ObjectState *b = bi < base.size() ? &base[bi] : nullptr;
		if (c && (!b || c->netId < b->netId)) {
			entries.push_back({c, c->netId, uint8_t(c->fields & FIELD_ALL), c->props});
			++ci;
		}
		else if (b && (!c || b->netId < c->netId)) {
			entries.push_back({nullptr, b->netId, 0, {}});
			++bi;
		}
		else {
			const uint8_t mask = uint8_t(changedFields(*c, *b, cfg) & FIELD_ALL);
			if (mask != 0) {
				Entry e{c, c->netId, mask, {}};
				if (mask & FIELD_PROPS) {
					changedProps(*c, *b, cfg, e.props);
				}
				entries.push_back(std::move(e));
			}
			++ci;
			++bi;
		}
	}

	w.writeU32(cur.tick);
	w.writeU32(baseline ? baseline->tick : 0);
	w.writeVarU(entries.size());
	NetId prev = 0;
	for (const Entry &e : entries) {
		w.writeVarU(uint64_t(e.netId - prev));
		prev = e.netId;
		if (!e.obj) {
			w.writeBool(true); // removed
			continue;
		}
		w.writeBool(false);
		w.writeBool(true); // changed
		writeFields(w, *e.obj, e.mask, e.props, cfg);
	}
	w.alignToByte();
	return w.ok();
}

bool peekSnapshotHeader(const uint8_t *data, size_t size, Tick &tick, Tick &baselineTick)
{
	BitReader r(data, size);
	tick = r.readU32();
	baselineTick = r.readU32();
	return r.ok();
}

SnapshotDecodeResult decodeSnapshot(BitReader &r, const Snapshot *baseline, const SnapshotConfig &cfg,
                                    Snapshot &out)
{
	out = Snapshot();
	if (!validConfig(cfg)) {
		r.fail();
		return SnapshotDecodeResult::Malformed;
	}
	const Tick tick = r.readU32();
	const Tick baselineTick = r.readU32();
	if (!r.ok() || tick == 0) {
		r.fail();
		return SnapshotDecodeResult::Malformed;
	}
	if (baselineTick != 0 && (!baseline || baseline->tick != baselineTick)) {
		return SnapshotDecodeResult::MissingBaseline;
	}

	std::map<NetId, ObjectState> objects;
	if (baselineTick != 0) {
		for (const ObjectState &o : baseline->objects) {
			objects.emplace(o.netId, o);
		}
	}

	const uint64_t count = r.readVarU();
	uint64_t netId = 0;
	for (uint64_t k = 0; k < count && r.ok(); ++k) {
		const uint64_t delta = r.readVarU();
		netId += delta;
		if (!r.ok() || delta == 0 || netId > 0xFFFFFFFFu) {
			r.fail();
			break;
		}
		const NetId id = NetId(netId);
		if (r.readBool()) {
			objects.erase(id);
			continue;
		}
		if (!r.readBool()) {
			continue; // identical to baseline
		}
		auto it = objects.find(id);
		if (it == objects.end()) {
			ObjectState fresh;
			fresh.netId = id;
			it = objects.emplace(id, fresh).first;
		}
		if (!readFields(r, cfg, it->second)) {
			break;
		}
	}
	r.alignToByte();
	if (!r.ok()) {
		out = Snapshot();
		return SnapshotDecodeResult::Malformed;
	}

	out.tick = tick;
	out.objects.reserve(objects.size());
	for (auto &kv : objects) {
		out.objects.push_back(std::move(kv.second));
	}
	return SnapshotDecodeResult::Ok;
}

/* -------------------------------------------------------------------- */
/* SnapshotBuffer */

SnapshotBuffer::SnapshotBuffer(size_t capacity)
	:m_slots(capacity ? capacity : 1),
	m_used(capacity ? capacity : 1, false),
	m_newest(0)
{
}

void SnapshotBuffer::insert(const Snapshot &snap)
{
	if (snap.tick == 0) {
		return;
	}
	const size_t cap = m_slots.size();
	if (m_newest != 0 && !tickNewer(snap.tick, m_newest) && size_t(m_newest - snap.tick) >= cap) {
		return; // older than the window
	}
	if (m_newest == 0 || tickNewer(snap.tick, m_newest)) {
		m_newest = snap.tick;
	}
	const size_t slot = snap.tick % cap;
	m_slots[slot] = snap;
	m_used[slot] = true;
}

const Snapshot *SnapshotBuffer::find(Tick tick) const
{
	if (tick == 0 || m_newest == 0) {
		return nullptr;
	}
	const size_t slot = tick % m_slots.size();
	if (!m_used[slot] || m_slots[slot].tick != tick || tickNewer(tick, m_newest) ||
	    size_t(m_newest - tick) >= m_slots.size())
	{
		return nullptr;
	}
	return &m_slots[slot];
}

Tick SnapshotBuffer::newestTick() const
{
	return m_newest;
}

size_t SnapshotBuffer::size() const
{
	size_t n = 0;
	for (size_t i = 0; i < m_slots.size(); ++i) {
		if (m_used[i] && find(m_slots[i].tick)) {
			++n;
		}
	}
	return n;
}

void SnapshotBuffer::clear()
{
	std::fill(m_used.begin(), m_used.end(), false);
	m_newest = 0;
}

void slerpQuat(const float a[4], const float b[4], float t, float out[4])
{
	double qa[4] = {a[0], a[1], a[2], a[3]};
	double qb[4] = {b[0], b[1], b[2], b[3]};
	double dot = qa[0] * qb[0] + qa[1] * qb[1] + qa[2] * qb[2] + qa[3] * qb[3];
	if (dot < 0.0) {
		dot = -dot;
		for (int i = 0; i < 4; ++i) {
			qb[i] = -qb[i];
		}
	}
	double wa, wb;
	if (dot > 0.9995) {
		wa = 1.0 - t;
		wb = t;
	}
	else {
		const double theta = std::acos(dot);
		const double s = std::sin(theta);
		wa = std::sin((1.0 - t) * theta) / s;
		wb = std::sin(t * theta) / s;
	}
	double r[4];
	double len2 = 0.0;
	for (int i = 0; i < 4; ++i) {
		r[i] = wa * qa[i] + wb * qb[i];
		len2 += r[i] * r[i];
	}
	const double inv = len2 > 0.0 ? 1.0 / std::sqrt(len2) : 0.0;
	for (int i = 0; i < 4; ++i) {
		out[i] = float(r[i] * inv);
	}
	if (len2 <= 0.0) {
		out[0] = out[1] = out[2] = 0.0f;
		out[3] = 1.0f;
	}
}

bool SnapshotBuffer::sample(Tick renderTick, float alpha, std::vector<ObjectState> &out) const
{
	out.clear();
	const Snapshot *before = nullptr;
	const Snapshot *after = nullptr;
	double beforeOffset = 0.0, afterOffset = 0.0;
	for (size_t i = 0; i < m_slots.size(); ++i) {
		if (!m_used[i] || !find(m_slots[i].tick)) {
			continue;
		}
		const Snapshot &s = m_slots[i];
		const double offset = double(int32_t(s.tick - renderTick)) - double(alpha);
		if (offset <= 0.0) {
			if (!before || offset > beforeOffset) {
				before = &s;
				beforeOffset = offset;
			}
		}
		else if (!after || offset < afterOffset) {
			after = &s;
			afterOffset = offset;
		}
	}
	if (!before) {
		return false;
	}
	out = before->objects;
	if (!after) {
		return true;
	}
	const float t = float(-beforeOffset / (afterOffset - beforeOffset));
	for (ObjectState &o : out) {
		const ObjectState *b = after->find(o.netId);
		if (!b) {
			continue;
		}
		if ((o.fields & FIELD_TRANSFORM) && (b->fields & FIELD_TRANSFORM)) {
			for (int k = 0; k < 3; ++k) {
				o.position[k] += (b->position[k] - o.position[k]) * t;
			}
			slerpQuat(o.rotation, b->rotation, t, o.rotation);
		}
		if ((o.fields & FIELD_VELOCITY) && (b->fields & FIELD_VELOCITY)) {
			for (int k = 0; k < 3; ++k) {
				o.velocity[k] += (b->velocity[k] - o.velocity[k]) * t;
			}
		}
		if ((o.fields & FIELD_ANGULAR_VELOCITY) && (b->fields & FIELD_ANGULAR_VELOCITY)) {
			for (int k = 0; k < 3; ++k) {
				o.angularVelocity[k] += (b->angularVelocity[k] - o.angularVelocity[k]) * t;
			}
		}
	}
	return true;
}

} // namespace net
