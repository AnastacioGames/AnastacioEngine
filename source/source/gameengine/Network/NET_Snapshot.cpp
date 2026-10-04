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

/** \file gameengine/Network/NET_Snapshot.cpp
 *  \ingroup network
 */

#include "NET_Snapshot.h"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace net {

static const int kVelocityBits = 16;
static const int kAngularVelocityBits = 12;
static const uint64_t kMaxProps = 1024;

PropValue PropValue::makeBool(bool v)
{
	PropValue p;
	p.kind = PropKind::Bool;
	p.b = v;
	return p;
}

PropValue PropValue::makeInt(int64_t v)
{
	PropValue p;
	p.kind = PropKind::Int;
	p.i = v;
	return p;
}

PropValue PropValue::makeFloat(float v)
{
	PropValue p;
	p.kind = PropKind::Float;
	p.f = v;
	return p;
}

const ObjectState *Snapshot::find(NetId id) const
{
	const auto it = std::lower_bound(objects.begin(), objects.end(), id,
	                                 [](const ObjectState &o, NetId v) { return o.id < v; });
	return (it != objects.end() && it->id == id) ? &*it : nullptr;
}

/* -------------------------------------------------------------------- */
/** \name Field comparison (on quantized values)
 * \{ */

static uint32_t floatBits(float f)
{
	uint32_t u;
	std::memcpy(&u, &f, sizeof(u));
	return u;
}

static bool transformDiffers(const ObjectState &a, const ObjectState &b, const SnapshotConfig &config)
{
	for (int i = 0; i < 3; ++i) {
		if (quantizePositionAxis(a.position[i], config.position.bits) !=
		    quantizePositionAxis(b.position[i], config.position.bits)) {
			return true;
		}
	}
	return quantizeRotation(a.rotation, config.rotationBits) != quantizeRotation(b.rotation, config.rotationBits);
}

static bool vectorDiffers(const float a[3], const float b[3], float range, int bits)
{
	for (int i = 0; i < 3; ++i) {
		if (quantizeRange(a[i], -range, range, bits) != quantizeRange(b[i], -range, range, bits)) {
			return true;
		}
	}
	return false;
}

static bool animDiffers(const AnimState &a, const AnimState &b)
{
	return a.action != b.action || floatBits(a.frame) != floatBits(b.frame) ||
	       floatBits(a.speed) != floatBits(b.speed);
}

static bool propDiffers(const PropValue &a, const PropValue &b, const PropertyDesc &desc)
{
	switch (desc.kind) {
		case PropKind::Bool:
			return a.b != b.b;
		case PropKind::Int:
			return a.i != b.i;
		case PropKind::Float:
			if (desc.bits > 0) {
				return quantizeRange(a.f, desc.min, desc.max, desc.bits) !=
				       quantizeRange(b.f, desc.min, desc.max, desc.bits);
			}
			return floatBits(a.f) != floatBits(b.f);
	}
	return true;
}

static bool validDesc(const PropertyDesc &desc)
{
	if (desc.kind == PropKind::Float && desc.bits != 0) {
		return desc.bits >= 1 && desc.bits <= 32 && desc.min < desc.max;
	}
	return desc.kind == PropKind::Bool || desc.kind == PropKind::Int || desc.kind == PropKind::Float;
}

static const std::vector<PropertyDesc> *lookupSchema(NetId id, const SnapshotConfig &config)
{
	return config.schema ? config.schema(id) : nullptr;
}

struct FieldMask {
	bool transform = false;
	bool velocity = false;
	bool angularVelocity = false;
	bool props = false;
	bool anim = false;
	bool valid = true;

	bool any() const
	{
		return transform || velocity || angularVelocity || props || anim;
	}
};

static FieldMask computeMask(const ObjectState &s, const ObjectState *base, const SnapshotConfig &config,
                             const std::vector<PropertyDesc> **schemaOut)
{
	FieldMask m;
	const std::vector<PropertyDesc> *schema = nullptr;
	if (!s.props.empty()) {
		schema = lookupSchema(s.id, config);
		if (!schema || schema->size() != s.props.size()) {
			m.valid = false;
			return m;
		}
		for (size_t i = 0; i < s.props.size(); ++i) {
			if (!validDesc((*schema)[i]) || s.props[i].kind != (*schema)[i].kind) {
				m.valid = false;
				return m;
			}
		}
	}
	if (schemaOut) {
		*schemaOut = schema;
	}

	m.transform = s.hasTransform && (!base || !base->hasTransform || transformDiffers(s, *base, config));
	m.velocity = s.hasVelocity &&
	             (!base || !base->hasVelocity ||
	              vectorDiffers(s.velocity, base->velocity, config.maxSpeed, kVelocityBits));
	m.angularVelocity = s.hasAngularVelocity &&
	                    (!base || !base->hasAngularVelocity ||
	                     vectorDiffers(s.angularVelocity, base->angularVelocity, config.maxAngSpeed,
	                                   kAngularVelocityBits));
	if (!s.props.empty()) {
		if (!base || base->props.size() != s.props.size()) {
			m.props = true;
		}
		else {
			for (size_t i = 0; i < s.props.size() && !m.props; ++i) {
				m.props = propDiffers(s.props[i], base->props[i], (*schema)[i]);
			}
		}
	}
	m.anim = s.hasAnim && (!base || !base->hasAnim || animDiffers(s.anim, base->anim));
	return m;
}

bool objectChanged(const ObjectState &state, const ObjectState &baseline, const SnapshotConfig &config)
{
	const FieldMask m = computeMask(state, &baseline, config, nullptr);
	return !m.valid || m.any();
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Object fields
 * \{ */

static void writeVector(BitWriter &w, const float v[3], float range, int bits)
{
	for (int i = 0; i < 3; ++i) {
		w.writeQuantized(v[i], -range, range, bits);
	}
}

static void readVector(BitReader &r, float v[3], float range, int bits)
{
	for (int i = 0; i < 3; ++i) {
		v[i] = r.readQuantized(-range, range, bits);
	}
}

static void writeProp(BitWriter &w, const PropValue &p, const PropertyDesc &desc)
{
	switch (desc.kind) {
		case PropKind::Bool:
			w.writeBool(p.b);
			break;
		case PropKind::Int:
			w.writeVarI(p.i);
			break;
		case PropKind::Float:
			if (desc.bits > 0) {
				w.writeQuantized(p.f, desc.min, desc.max, desc.bits);
			}
			else {
				writeFloat32(w, p.f);
			}
			break;
	}
}

static PropValue readProp(BitReader &r, const PropertyDesc &desc)
{
	switch (desc.kind) {
		case PropKind::Bool:
			return PropValue::makeBool(r.readBool());
		case PropKind::Int:
			return PropValue::makeInt(r.readVarI());
		case PropKind::Float:
			if (desc.bits > 0) {
				return PropValue::makeFloat(r.readQuantized(desc.min, desc.max, desc.bits));
			}
			return PropValue::makeFloat(readFloat32(r));
	}
	r.fail();
	return PropValue();
}

bool encodeObjectFields(BitWriter &w, const ObjectState &s, const ObjectState *base, const SnapshotConfig &config)
{
	const std::vector<PropertyDesc> *schema = nullptr;
	const FieldMask m = computeMask(s, base, config, &schema);
	if (!m.valid) {
		w.fail();
		return false;
	}

	w.writeBool(m.transform);
	if (m.transform) {
		writePosition(w, s.position, config.position);
		writeRotation(w, s.rotation, config.rotationBits);
	}
	w.writeBool(m.velocity);
	if (m.velocity) {
		writeVector(w, s.velocity, config.maxSpeed, kVelocityBits);
	}
	w.writeBool(m.angularVelocity);
	if (m.angularVelocity) {
		writeVector(w, s.angularVelocity, config.maxAngSpeed, kAngularVelocityBits);
	}
	w.writeBool(m.props);
	if (m.props) {
		const bool sameLayout = base && base->props.size() == s.props.size();
		w.writeVarU(s.props.size());
		for (size_t i = 0; i < s.props.size(); ++i) {
			const bool changed = !sameLayout || propDiffers(s.props[i], base->props[i], (*schema)[i]);
			w.writeBool(changed);
			if (changed) {
				writeProp(w, s.props[i], (*schema)[i]);
			}
		}
	}
	w.writeBool(m.anim);
	if (m.anim) {
		w.writeVarU(s.anim.action);
		writeFloat32(w, s.anim.frame);
		writeFloat32(w, s.anim.speed);
	}
	return w.ok();
}

bool decodeObjectFields(BitReader &r, ObjectState &s, bool hasBaseline, const SnapshotConfig &config)
{
	if (r.readBool()) {
		readPosition(r, s.position, config.position);
		readRotation(r, s.rotation, config.rotationBits);
		s.hasTransform = true;
	}
	if (r.readBool()) {
		readVector(r, s.velocity, config.maxSpeed, kVelocityBits);
		s.hasVelocity = true;
	}
	if (r.readBool()) {
		readVector(r, s.angularVelocity, config.maxAngSpeed, kAngularVelocityBits);
		s.hasAngularVelocity = true;
	}
	if (r.readBool()) {
		const uint64_t count = r.readVarU();
		const std::vector<PropertyDesc> *schema = lookupSchema(s.id, config);
		if (!r.ok() || count == 0 || count > kMaxProps || !schema || schema->size() != count) {
			r.fail();
			return false;
		}
		const bool sameLayout = hasBaseline && s.props.size() == count;
		std::vector<PropValue> props(static_cast<size_t>(count));
		for (size_t i = 0; i < count && r.ok(); ++i) {
			const PropertyDesc &desc = (*schema)[i];
			if (!validDesc(desc)) {
				r.fail();
				break;
			}
			if (r.readBool()) {
				props[i] = readProp(r, desc);
			}
			else if (sameLayout && s.props[i].kind == desc.kind) {
				props[i] = s.props[i];
			}
			else {
				r.fail();
			}
		}
		if (!r.ok()) {
			return false;
		}
		s.props = std::move(props);
	}
	if (r.readBool()) {
		const uint64_t action = r.readVarU();
		if (action > 0xFFFFFFFFull) {
			r.fail();
		}
		s.anim.action = uint32_t(action);
		s.anim.frame = readFloat32(r);
		s.anim.speed = readFloat32(r);
		s.hasAnim = true;
	}
	return r.ok();
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Snapshot body
 * \{ */

namespace {
enum class EntryKind { Removed, Changed };
struct Entry {
	const ObjectState *state;
	const ObjectState *base;
	NetId id;
	EntryKind kind;
};
}  // namespace

bool encodeSnapshot(BitWriter &w, Tick tick, const std::vector<ObjectState> &objects,
                    const Snapshot *baseline, const SnapshotConfig &config)
{
	for (size_t i = 0; i < objects.size(); ++i) {
		if (objects[i].id == kInvalidNetId || (i > 0 && objects[i].id <= objects[i - 1].id)) {
			w.fail();
			return false;
		}
	}

	static const std::vector<ObjectState> empty;
	const std::vector<ObjectState> &baseObjects = baseline ? baseline->objects : empty;

	// Merge walk: unchanged objects are omitted, vanished ones are marked removed.
	std::vector<Entry> entries;
	size_t i = 0, j = 0;
	while (i < objects.size() || j < baseObjects.size()) {
		if (j >= baseObjects.size() || (i < objects.size() && objects[i].id < baseObjects[j].id)) {
			entries.push_back({&objects[i], nullptr, objects[i].id, EntryKind::Changed});
			++i;
		}
		else if (i >= objects.size() || baseObjects[j].id < objects[i].id) {
			entries.push_back({nullptr, nullptr, baseObjects[j].id, EntryKind::Removed});
			++j;
		}
		else {
			if (objectChanged(objects[i], baseObjects[j], config)) {
				entries.push_back({&objects[i], &baseObjects[j], objects[i].id, EntryKind::Changed});
			}
			++i;
			++j;
		}
	}

	w.writeU32(tick);
	w.writeU32(baseline ? baseline->tick : kNoTick);
	w.writeVarU(entries.size());
	NetId prev = 0;
	for (const Entry &e : entries) {
		w.writeVarU(e.id - prev);
		prev = e.id;
		w.writeBool(e.kind == EntryKind::Removed);
		if (e.kind == EntryKind::Removed) {
			continue;
		}
		w.writeBool(true);
		encodeObjectFields(w, *e.state, e.base, config);
	}
	w.alignToByte();
	return w.ok();
}

bool decodeSnapshot(BitReader &r, const Snapshot *baseline, const SnapshotConfig &config, Snapshot &out)
{
	out = Snapshot();
	out.tick = r.readU32();
	out.baselineTick = r.readU32();
	if (!r.ok()) {
		return false;
	}
	if (out.baselineTick != kNoTick) {
		if (!baseline || baseline->tick != out.baselineTick) {
			r.fail();
			return false;
		}
		out.objects = baseline->objects;
	}

	const uint64_t count = r.readVarU();
	// Every entry takes at least 9 bits.
	if (!r.ok() || count > r.bitsRemaining() / 9) {
		r.fail();
		return false;
	}

	uint64_t prev = 0;
	for (uint64_t n = 0; n < count && r.ok(); ++n) {
		const uint64_t delta = r.readVarU();
		const uint64_t id = prev + delta;
		if (!r.ok() || delta == 0 || id > 0xFFFFFFFFull) {
			r.fail();
			break;
		}
		prev = id;
		auto it = std::lower_bound(out.objects.begin(), out.objects.end(), NetId(id),
		                           [](const ObjectState &o, NetId v) { return o.id < v; });
		const bool exists = it != out.objects.end() && it->id == id;

		if (r.readBool()) {
			if (exists) {
				out.objects.erase(it);
			}
			continue;
		}
		if (!r.readBool()) {
			// Identical to the baseline.
			continue;
		}
		if (exists) {
			decodeObjectFields(r, *it, true, config);
		}
		else {
			ObjectState state;
			state.id = NetId(id);
			if (decodeObjectFields(r, state, false, config)) {
				out.objects.insert(it, std::move(state));
			}
		}
	}
	r.alignToByte();
	if (!r.ok()) {
		out.objects.clear();
		return false;
	}
	return true;
}

bool readSnapshotHeader(const uint8_t *data, size_t size, Tick &tick, Tick &baselineTick)
{
	BitReader r(data, size);
	tick = r.readU32();
	baselineTick = r.readU32();
	return r.ok();
}

/** \} */

/* -------------------------------------------------------------------- */
/** \name Interpolation
 * \{ */

void slerp(const float a[4], const float b[4], float t, float out[4])
{
	double qa[4], qb[4];
	double la = 0.0, lb = 0.0;
	for (int i = 0; i < 4; ++i) {
		qa[i] = a[i];
		qb[i] = b[i];
		la += qa[i] * qa[i];
		lb += qb[i] * qb[i];
	}
	la = std::sqrt(la);
	lb = std::sqrt(lb);
	if (!(la > 1e-12) || !(lb > 1e-12)) {
		for (int i = 0; i < 4; ++i) {
			out[i] = (t < 0.5f) ? a[i] : b[i];
		}
		return;
	}
	double dot = 0.0;
	for (int i = 0; i < 4; ++i) {
		qa[i] /= la;
		qb[i] /= lb;
		dot += qa[i] * qb[i];
	}
	if (dot < 0.0) {
		dot = -dot;
		for (double &c : qb) {
			c = -c;
		}
	}
	double wa, wb;
	if (dot > 0.9995) {
		wa = 1.0 - t;
		wb = t;
	}
	else {
		const double theta = std::acos(std::min(dot, 1.0));
		const double s = std::sin(theta);
		wa = std::sin((1.0 - t) * theta) / s;
		wb = std::sin(t * theta) / s;
	}
	double len = 0.0;
	double r[4];
	for (int i = 0; i < 4; ++i) {
		r[i] = wa * qa[i] + wb * qb[i];
		len += r[i] * r[i];
	}
	len = std::sqrt(len);
	for (int i = 0; i < 4; ++i) {
		out[i] = float(r[i] / len);
	}
}

SnapshotBuffer::SnapshotBuffer(size_t capacity)
	:m_capacity(std::max<size_t>(capacity, 2))
{
}

bool SnapshotBuffer::insert(const Snapshot &snapshot)
{
	auto it = m_snapshots.begin();
	while (it != m_snapshots.end() && tickNewer(snapshot.tick, it->tick)) {
		++it;
	}
	if (it != m_snapshots.end() && it->tick == snapshot.tick) {
		*it = snapshot;
		return true;
	}
	if (m_snapshots.size() >= m_capacity) {
		if (it == m_snapshots.begin()) {
			return false;
		}
		const size_t index = size_t(it - m_snapshots.begin()) - 1;
		m_snapshots.erase(m_snapshots.begin());
		it = m_snapshots.begin() + index;
	}
	m_snapshots.insert(it, snapshot);
	return true;
}

const Snapshot *SnapshotBuffer::find(Tick tick) const
{
	for (const Snapshot &s : m_snapshots) {
		if (s.tick == tick) {
			return &s;
		}
	}
	return nullptr;
}

const Snapshot *SnapshotBuffer::newest() const
{
	return m_snapshots.empty() ? nullptr : &m_snapshots.back();
}

const Snapshot *SnapshotBuffer::oldest() const
{
	return m_snapshots.empty() ? nullptr : &m_snapshots.front();
}

size_t SnapshotBuffer::size() const
{
	return m_snapshots.size();
}

void SnapshotBuffer::clear()
{
	m_snapshots.clear();
}

static void lerp3(const float a[3], const float b[3], float t, float out[3])
{
	for (int i = 0; i < 3; ++i) {
		out[i] = a[i] + (b[i] - a[i]) * t;
	}
}

bool SnapshotBuffer::sample(Tick renderTick, float alpha, std::vector<ObjectState> &out) const
{
	out.clear();
	if (m_snapshots.empty()) {
		return false;
	}
	alpha = std::min(std::max(alpha, 0.0f), 1.0f);
	const Snapshot &first = m_snapshots.front();
	if (tickNewer(first.tick, renderTick)) {
		return false;
	}

	// Last snapshot at or before renderTick.
	size_t index = 0;
	while (index + 1 < m_snapshots.size() && !tickNewer(m_snapshots[index + 1].tick, renderTick)) {
		++index;
	}
	const Snapshot &from = m_snapshots[index];
	if (index + 1 >= m_snapshots.size()) {
		out = from.objects;
		return true;
	}
	const Snapshot &to = m_snapshots[index + 1];
	const double span = double(int32_t(to.tick - from.tick));
	const double pos = double(int32_t(renderTick - from.tick)) + double(alpha);
	const float t = float(std::min(std::max(pos / span, 0.0), 1.0));

	out = from.objects;
	for (ObjectState &o : out) {
		const ObjectState *next = to.find(o.id);
		if (!next) {
			continue;
		}
		if (o.hasTransform && next->hasTransform) {
			lerp3(o.position, next->position, t, o.position);
			slerp(o.rotation, next->rotation, t, o.rotation);
		}
		if (o.hasVelocity && next->hasVelocity) {
			lerp3(o.velocity, next->velocity, t, o.velocity);
		}
		if (o.hasAngularVelocity && next->hasAngularVelocity) {
			lerp3(o.angularVelocity, next->angularVelocity, t, o.angularVelocity);
		}
	}
	return true;
}

/** \} */

}  // namespace net
