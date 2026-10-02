/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_DestructionManager.cpp
 *  \ingroup ketsji
 */

#include "KX_DestructionManager.h"
#include "KX_ClientObjectInfo.h"
#include "KX_DentDeformer.h"
#include "KX_GameObject.h"
#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "KX_Mesh.h"
#include "KX_RayCast.h"
#include "KX_Scene.h"

#include "SCA_LogicManager.h"
#include "BL_Converter.h"
#include "RAS_DisplayArray.h"
#include "RAS_MeshMaterial.h"
#include "PHY_DynamicTypes.h"
#include "PHY_IPhysicsController.h"
#include "PHY_IPhysicsEnvironment.h"

#include "CM_List.h"
#include "CM_Message.h"

#include "DNA_group_types.h"
#include "DNA_object_types.h"

#include <algorithm>
#include <cfloat>
#include <cmath>

/// AddReplicaObject() counts the lifespan in 1/50 s ticks (see KX_Scene::AddReplicaObject).
static const float LIFESPAN_TICKS_PER_SECOND = 50.0f;
/// Seconds between two collision dents of an object: a resting or sliding contact above the dent
/// impulse would rebuild the mesh (and its collision shape) every frame.
static const float DENT_COOLDOWN = 0.1f;

static bool is_destructible(KX_GameObject *gameobj)
{
	Object *blenderobj = gameobj->GetBlenderObject();
	return blenderobj && (blenderobj->gameflag2 & OB_DESTRUCTIBLE);
}

static bool is_explosive(KX_GameObject *gameobj)
{
	Object *blenderobj = gameobj->GetBlenderObject();
	return blenderobj && (blenderobj->gameflag2 & OB_EXPLOSIVE);
}

static bool is_deformable(KX_GameObject *gameobj)
{
	Object *blenderobj = gameobj->GetBlenderObject();
	return blenderobj && (blenderobj->gameflag2 & OB_DEFORMABLE);
}

static bool dents_on_collision(KX_GameObject *gameobj)
{
	return is_deformable(gameobj) && (gameobj->GetBlenderObject()->deform.flags & DEFORM_ON_COLLISION);
}

static bool scrapes(KX_GameObject *gameobj)
{
	return is_deformable(gameobj) && (gameobj->GetBlenderObject()->deform.flags & DEFORM_SCRAPE) &&
	       gameobj->GetBlenderObject()->deform.decal;
}

static bool breaks_on_collision(KX_GameObject *gameobj)
{
	return is_destructible(gameobj) && (gameobj->GetBlenderObject()->destruction.flags & DESTRUCTION_BREAK_ON_COLLISION);
}

static bool explodes_on_impact(KX_GameObject *gameobj)
{
	return is_explosive(gameobj) && (gameobj->GetBlenderObject()->explosive.flags & EXPLOSIVE_ON_IMPACT);
}

static bool wants_collisions(KX_GameObject *gameobj)
{
	return (breaks_on_collision(gameobj) || explodes_on_impact(gameobj) || dents_on_collision(gameobj) || scrapes(gameobj)) &&
	       gameobj->GetPhysicsController() &&
	       !gameobj->GetClientInfo().isSensor();
}

static bool contains(const std::vector<KX_GameObject *>& list, KX_GameObject *gameobj)
{
	return std::find(list.begin(), list.end(), gameobj) != list.end();
}

/// Blast impulse at a point, linear falloff to 0 at the radius.
/// Damage mark strength 0..1 from the impulse past the dent threshold.
static float hit_strength(float excess, float threshold)
{
	return (excess > 0.0f) ? 1.0f - std::exp(-excess / std::max(threshold, 1.0f)) : 0.0f;
}

static float impulse_at(const mt::vec3& position, const mt::vec3& center, float radius, float force)
{
	const float distance = (position - center).Length();
	return (distance < radius) ? force * (1.0f - distance / radius) : 0.0f;
}

/// Only static geometry blocks a blast: dynamic objects in the way are pushed themselves.
struct OcclusionFilter
{
	KX_GameObject *m_target;
	const std::vector<KX_GameObject *> *m_ignore;

	bool NeedRayCast(KX_ClientObjectInfo *client, void *UNUSED(data))
	{
		KX_GameObject *gameobj = client->m_gameobject;
		return gameobj && !client->isSensor() && gameobj != m_target && !gameobj->IsDynamic() &&
		       !contains(*m_ignore, gameobj);
	}

	bool RayHit(KX_ClientObjectInfo *UNUSED(client), KX_RayCast *UNUSED(result), void *UNUSED(data))
	{
		return true;
	}
};

KX_DestructionManager::KX_DestructionManager(KX_Scene *scene)
	:m_scene(scene),
	m_maxDebris(150),
	m_frame(0)
{
}

KX_DestructionManager::Entry *KX_DestructionManager::FindEntry(KX_GameObject *gameobj)
{
	for (Entry& entry : m_entries) {
		if (entry.m_object == gameobj) {
			return &entry;
		}
	}
	return nullptr;
}

const KX_DestructionManager::Entry *KX_DestructionManager::FindEntry(KX_GameObject *gameobj) const
{
	for (const Entry& entry : m_entries) {
		if (entry.m_object == gameobj) {
			return &entry;
		}
	}
	return nullptr;
}

void KX_DestructionManager::Arm(Entry *entry, long long frame)
{
	if (entry && !entry->m_done && (entry->m_armFrame < 0 || frame < entry->m_armFrame)) {
		entry->m_armFrame = frame;
	}
}

void KX_DestructionManager::RegisterObject(KX_GameObject *gameobj)
{
	Object *blenderobj = gameobj->GetBlenderObject();
	if (!blenderobj || !(blenderobj->gameflag2 & (OB_DESTRUCTIBLE | OB_EXPLOSIVE | OB_DEFORMABLE)) || FindEntry(gameobj)) {
		return;
	}

	Entry entry;
	entry.m_object = gameobj;
	entry.m_breakImpulse = is_destructible(gameobj) ? blenderobj->destruction.break_impulse : 0.0f;
	// The fuse counts from the moment the object enters the game (scene start or Add Object).
	entry.m_fuse = is_explosive(gameobj) ? std::max(blenderobj->explosive.fuse, 0.0f) : 0.0f;
	entry.m_armFrame = -1;
	entry.m_done = false;
	entry.m_dentCooldown = 0.0f;
	entry.m_dentWarned = false;
	entry.m_lastScrape = mt::zero3;
	entry.m_scraped = false;
	m_entries.push_back(entry);

	if (wants_collisions(gameobj)) {
		m_scene->GetPhysicsEnvironment()->RequestCollisionCallback(gameobj->GetPhysicsController());
	}
}

void KX_DestructionManager::UnregisterObject(KX_GameObject *gameobj)
{
	for (std::vector<Entry>::iterator it = m_entries.begin(), end = m_entries.end(); it != end; ++it) {
		if (it->m_object == gameobj) {
			m_entries.erase(it);
			if (wants_collisions(gameobj)) {
				m_scene->GetPhysicsEnvironment()->RemoveCollisionCallback(gameobj->GetPhysicsController());
			}
			break;
		}
	}

	m_pending.erase(std::remove_if(m_pending.begin(), m_pending.end(),
	                               [gameobj](const PendingBreak& pending) { return pending.m_object == gameobj; }),
	                m_pending.end());

	m_pendingScrapes.erase(std::remove_if(m_pendingScrapes.begin(), m_pendingScrapes.end(),
	                                      [gameobj](const PendingScrape& pending) { return pending.m_object == gameobj; }),
	                       m_pendingScrapes.end());

	m_pendingDents.erase(std::remove_if(m_pendingDents.begin(), m_pendingDents.end(),
	                                    [gameobj](const PendingDent& pending) { return pending.m_object == gameobj; }),
	                     m_pendingDents.end());
	m_dirtyShapes.erase(std::remove(m_dirtyShapes.begin(), m_dirtyShapes.end(), gameobj), m_dirtyShapes.end());
	for (Entry& entry : m_entries) {
		std::vector<std::pair<KX_GameObject *, long long> >& touching = entry.m_touching;
		touching.erase(std::remove_if(touching.begin(), touching.end(),
		                              [gameobj](const std::pair<KX_GameObject *, long long>& touch) { return touch.first == gameobj; }),
		               touching.end());
	}

	for (std::deque<Decal>::iterator it = m_decals.begin(); it != m_decals.end(); ++it) {
		if (it->m_object == gameobj) {
			m_deadDecalMeshes.push_back(it->m_mesh);
			m_decals.erase(it);
			break;
		}
	}
	// The decals of a removed target go with it (children).
	for (Decal& decal : m_decals) {
		if (decal.m_target == gameobj) {
			decal.m_target = nullptr;
		}
	}

	const std::deque<KX_GameObject *>::iterator it = std::find(m_debris.begin(), m_debris.end(), gameobj);
	if (it != m_debris.end()) {
		m_debris.erase(it);
	}
}

void KX_DestructionManager::NotifyCollision(KX_GameObject *gameobj, KX_GameObject *other, const PHY_ICollData *collData,
                                            bool first)
{
	if (!gameobj || !collData) {
		return;
	}

	Entry *entry = FindEntry(gameobj);
	if (!entry || entry->m_done) {
		return;
	}

	if (scrapes(gameobj)) {
		Scrape(entry, other, collData, first);
	}

	const bool detonates = explodes_on_impact(gameobj);
	const bool breaks = breaks_on_collision(gameobj) && gameobj->GetBlenderObject()->destruction.fragments;
	bool dents = false;
	if (dents_on_collision(gameobj)) {
		// A hit is a contact with an object that wasn't touching on the previous frame.
		bool newContact = true;
		bool found = false;
		for (std::pair<KX_GameObject *, long long>& touch : entry->m_touching) {
			if (touch.first == other) {
				newContact = touch.second < m_frame - 1;
				touch.second = m_frame;
				found = true;
				break;
			}
		}
		if (!found) {
			entry->m_touching.emplace_back(other, m_frame);
		}
		dents = newContact && entry->m_dentCooldown <= 0.0f;
	}
	if (!detonates && !breaks && !dents) {
		return;
	}

	// Same measure as KX_CollisionContactPoint.appliedImpulse summed over the contact points.
	float total = 0.0f;
	float strongest = -1.0f;
	mt::vec3 origin = gameobj->NodeGetWorldPosition();
	mt::vec3 normal = mt::zero3;
	mt::vec3 hitter = mt::zero3;
	for (unsigned int i = 0, num = collData->GetNumContacts(); i < num; ++i) {
		const float impulse = collData->GetAppliedImpulse(i, first);
		total += impulse;
		if (impulse > strongest) {
			strongest = impulse;
			origin = collData->GetWorldPoint(i, first);
			normal = collData->GetNormal(i, first);
		}
	}

	if (detonates && total >= gameobj->GetBlenderObject()->explosive.impact_impulse) {
		// Detonates at the end of this frame.
		Arm(entry, m_frame);
		return;
	}

	if (breaks && total >= entry->m_breakImpulse) {
		for (const PendingBreak& pending : m_pending) {
			if (pending.m_object == gameobj) {
				return;
			}
		}
		m_pending.push_back({gameobj, origin});
		return;
	}

	if (dents && total >= gameobj->GetBlenderObject()->deform.dent_impulse) {
		// Seen from the hitting object, which tells the sides of a flat mesh apart (see DentNow).
		hitter = other ? other->NodeGetWorldPosition() : origin;
		// One dent per object and frame, the strongest contact.
		for (PendingDent& pending : m_pendingDents) {
			if (pending.m_object == gameobj) {
				if (total > pending.m_impulse) {
					pending = {gameobj, origin, normal, hitter, total};
				}
				return;
			}
		}
		m_pendingDents.push_back({gameobj, origin, normal, hitter, total});
	}
}

bool KX_DestructionManager::Dent(KX_GameObject *gameobj, const mt::vec3& point, const mt::vec3& direction, float impulse)
{
	const Entry *entry = gameobj ? FindEntry(gameobj) : nullptr;
	if (!entry || entry->m_done || !is_deformable(gameobj) || impulse < gameobj->GetBlenderObject()->deform.dent_impulse) {
		return false;
	}
	return DentNow(gameobj, point, direction, impulse);
}

KX_DentDeformer *KX_DestructionManager::GetDentDeformer(KX_GameObject *gameobj)
{
	KX_DentDeformer *deformer = gameobj->GetDentDeformer(true);
	if (!deformer) {
		Entry *entry = FindEntry(gameobj);
		if (entry && !entry->m_dentWarned) {
			entry->m_dentWarned = true;
			CM_Warning("\"" << gameobj->GetName() << "\" is deformable but its mesh is driven by modifiers, an armature, "
			           "shape keys or a soft body; it can't dent.");
		}
	}
	return deformer;
}

void KX_DestructionManager::Dented(KX_GameObject *gameobj, const mt::vec3& point, float impulse)
{
	if ((gameobj->GetBlenderObject()->deform.flags & DEFORM_UPDATE_PHYSICS) && !contains(m_dirtyShapes, gameobj)) {
		m_dirtyShapes.push_back(gameobj);
	}
	gameobj->RunDentCallbacks(point, impulse);
}

bool KX_DestructionManager::DentNow(KX_GameObject *gameobj, const mt::vec3& point, const mt::vec3& direction, float impulse,
                                    const mt::vec3 *hitter)
{
	const RangeDeformSettings& settings = gameobj->GetBlenderObject()->deform;
	const bool bend = (settings.mode == DEFORM_MODE_BEND);
	const float excess = impulse - settings.dent_impulse;
	const float depth = bend ? excess * settings.bend_angle : std::min(excess * settings.depth, settings.max_depth);
	if (depth <= 0.0f) {
		return false;
	}

	KX_DentDeformer *deformer = GetDentDeformer(gameobj);
	if (!deformer) {
		return false;
	}

	/* Into the object whatever the sign of the direction. Two hints: towards the center of the mesh
	 * bounds (the origin can be far from the mesh), and away from the hitting object (collisions).
	 * The center fails on a flat mesh (a plane: it lies on the surface), the hitter fails when it is
	 * wide and flat itself (a cube landing on a plane: the plane origin is beside the contact), so the
	 * clearer one decides. */
	const mt::mat3x4 trans = gameobj->NodeGetWorldTransform();
	mt::vec3 aabbMin, aabbMax;
	deformer->GetBoundingBox()->GetAabb(aabbMin, aabbMax);
	const mt::vec3 toCenter = (trans * ((aabbMin + aabbMax) * 0.5f) - point).SafeNormalized(mt::zero3);
	const mt::vec3 fromHitter = hitter ? (point - *hitter).SafeNormalized(mt::zero3) : mt::zero3;
	mt::vec3 inward = direction.SafeNormalized(mt::zero3);
	if (inward.LengthSquared() == 0.0f) {
		inward = (toCenter + fromHitter).SafeNormalized(-mt::axisZ3);
	}
	else {
		const float byCenter = mt::dot(inward, toCenter);
		const float byHitter = mt::dot(inward, fromHitter);
		if ((std::abs(byHitter) > std::abs(byCenter) ? byHitter : byCenter) < 0.0f) {
			inward = -inward;
		}
	}

	const bool moved = bend ? deformer->AddBend(trans, point, inward, settings.bend_axis, depth, settings.bend_max_angle)
	                        : deformer->AddDent(trans, point, inward * depth, settings.radius, settings.max_depth);
	if (settings.decal) {
		AddDecal(gameobj, point, inward);
	}
	if (!moved) {
		return false;
	}
	deformer->AddHit(trans, point, settings.radius, hit_strength(excess, settings.dent_impulse));

	Dented(gameobj, point, impulse);
	return true;
}

void KX_DestructionManager::BlastDent(KX_GameObject *gameobj, const mt::vec3& center, float radius, float force)
{
	const RangeDeformSettings& settings = gameobj->GetBlenderObject()->deform;
	if (settings.mode == DEFORM_MODE_BEND) {
		// Bent by the blast at the point of the object closest to the center, away from it.
		const float impulse = impulse_at(gameobj->NodeGetWorldPosition(), center, radius, force);
		if (impulse >= settings.dent_impulse) {
			const mt::vec3 position = gameobj->NodeGetWorldPosition();
			DentNow(gameobj, position, position - center, impulse);
		}
		return;
	}
	KX_DentDeformer *deformer = GetDentDeformer(gameobj);
	const mt::mat3x4 trans = gameobj->NodeGetWorldTransform();
	if (deformer && deformer->AddBlastDent(trans, center, radius, force,
	                                       settings.dent_impulse, settings.depth, settings.max_depth))
	{
		const float impulse = impulse_at(gameobj->NodeGetWorldPosition(), center, radius, force);
		// Damage mark on the bounds point closest to the blast.
		mt::vec3 aabbMin, aabbMax;
		deformer->GetBoundingBox()->GetAabb(aabbMin, aabbMax);
		const mt::vec3 local = mt::vec3::Max(aabbMin, mt::vec3::Min(aabbMax, trans.Inverse() * center));
		deformer->AddHit(trans, trans * local, settings.radius, hit_strength(impulse - settings.dent_impulse,
		                                                                     settings.dent_impulse));
		if (settings.decal) {
			const mt::vec3 point = trans * local;
			AddDecal(gameobj, point, (point - center).SafeNormalized(-mt::axisZ3));
		}
		Dented(gameobj, center, impulse);
	}
}

/// Closest point to p on the triangle abc (Ericson, Real-Time Collision Detection 5.1.5).
static mt::vec3 closest_on_triangle(const mt::vec3& p, const mt::vec3& a, const mt::vec3& b, const mt::vec3& c)
{
	const mt::vec3 ab = b - a, ac = c - a, ap = p - a;
	const float d1 = mt::dot(ab, ap), d2 = mt::dot(ac, ap);
	if (d1 <= 0.0f && d2 <= 0.0f) {
		return a;
	}
	const mt::vec3 bp = p - b;
	const float d3 = mt::dot(ab, bp), d4 = mt::dot(ac, bp);
	if (d3 >= 0.0f && d4 <= d3) {
		return b;
	}
	const float vc = d1 * d4 - d3 * d2;
	if (vc <= 0.0f && d1 >= 0.0f && d3 <= 0.0f) {
		return a + ab * (d1 / (d1 - d3));
	}
	const mt::vec3 cp = p - c;
	const float d5 = mt::dot(ab, cp), d6 = mt::dot(ac, cp);
	if (d6 >= 0.0f && d5 <= d6) {
		return c;
	}
	const float vb = d5 * d2 - d1 * d6;
	if (vb <= 0.0f && d2 >= 0.0f && d6 <= 0.0f) {
		return a + ac * (d2 / (d2 - d6));
	}
	const float va = d3 * d6 - d5 * d4;
	if (va <= 0.0f && (d4 - d3) >= 0.0f && (d5 - d6) >= 0.0f) {
		return b + (c - b) * ((d4 - d3) / ((d4 - d3) + (d5 - d6)));
	}
	const float denom = 1.0f / (va + vb + vc);
	return a + ab * (vb * denom) + ac * (vc * denom);
}

/// Clips the convex polygon (box coordinates) to the side of plane axis * sign <= 1.
static void clip_polygon(std::vector<mt::vec3>& polygon, int axis, float sign)
{
	std::vector<mt::vec3> result;
	for (unsigned int i = 0, size = polygon.size(); i < size; ++i) {
		const mt::vec3& a = polygon[i];
		const mt::vec3& b = polygon[(i + 1) % size];
		const float da = 1.0f - a[axis] * sign;
		const float db = 1.0f - b[axis] * sign;
		if (da >= 0.0f) {
			result.push_back(a);
		}
		if ((da >= 0.0f) != (db >= 0.0f)) {
			result.push_back(a + (b - a) * (da / (da - db)));
		}
	}
	polygon.swap(result);
}

void KX_DestructionManager::Scrape(Entry *entry, KX_GameObject *other, const PHY_ICollData *collData, bool first)
{
	KX_GameObject *gameobj = entry->m_object;
	const RangeDeformSettings& settings = gameobj->GetBlenderObject()->deform;
	const unsigned int num = collData->GetNumContacts();
	if (num == 0) {
		return;
	}

	// Deepest contact pressing on the surface.
	unsigned int best = 0;
	float strongest = -1.0f;
	for (unsigned int i = 0; i < num; ++i) {
		const float impulse = collData->GetAppliedImpulse(i, first);
		if (impulse > strongest) {
			strongest = impulse;
			best = i;
		}
	}
	if (strongest <= 0.0f) {
		return;
	}
	const mt::vec3 point = collData->GetWorldPoint(best, first);
	const mt::vec3 normal = collData->GetNormal(best, first).SafeNormalized(mt::axisZ3);

	// Sliding speed: relative velocity of the two surfaces at the contact, across the normal.
	mt::vec3 relative = gameobj->GetVelocity(point - gameobj->NodeGetWorldPosition());
	if (other) {
		relative -= other->GetVelocity(point - other->NodeGetWorldPosition());
	}
	relative -= normal * mt::dot(relative, normal);
	const float speed = relative.Length();
	const float spacing = (settings.scrape_spacing > 0.0f) ? settings.scrape_spacing : 0.15f;
	if (speed < std::max(settings.scrape_speed, 0.01f)) {
		return;
	}

	// One mark every spacing along the trail; a far jump starts a new trail.
	if (entry->m_scraped) {
		const float distance = (point - entry->m_lastScrape).Length();
		if (distance < spacing) {
			return;
		}
		if (distance > spacing * 8.0f) {
			entry->m_scraped = false;
		}
	}
	entry->m_lastScrape = point;
	entry->m_scraped = true;

	for (const PendingScrape& pending : m_pendingScrapes) {
		if (pending.m_object == gameobj) {
			return;
		}
	}
	m_pendingScrapes.push_back({gameobj, point, normal, relative / speed});
}

void KX_DestructionManager::AddDecal(KX_GameObject *gameobj, const mt::vec3& point, const mt::vec3& inward,
                                     const mt::vec3 *along)
{
	const RangeDeformSettings& settings = gameobj->GetBlenderObject()->deform;
	KX_GameObject *templateobj = static_cast<KX_GameObject *>(m_scene->GetLogicManager()->FindGameObjByBlendObj(settings.decal));
	if (!templateobj || templateobj->GetMeshList().empty()) {
		Entry *entry = FindEntry(gameobj);
		if (entry && !entry->m_dentWarned) {
			entry->m_dentWarned = true;
			CM_Warning("\"" << gameobj->GetName() << "\": the Decal \"" << (settings.decal->id.name + 2)
			           << "\" is not a mesh object in this scene.");
		}
		return;
	}
	KX_DentDeformer *deformer = gameobj->GetDentDeformer(false);
	KX_Mesh *templateMesh = templateobj->GetMeshList().front();
	if (!deformer || templateMesh->GetMeshMaterialList().empty()) {
		return;
	}
	RAS_MeshMaterial *meshmat = templateMesh->GetMeshMaterialList().front();

	// Projection box: N out of the surface, U and V across it with a random turn.
	const mt::mat3x4 trans = gameobj->NodeGetWorldTransform();
	const mt::mat3x4 invtrans = trans.Inverse();
	const mt::vec3 invOrigin = invtrans * mt::zero3;
	std::vector<mt::vec3> triangles;
	deformer->GetTriangles(triangles);
	for (mt::vec3& corner : triangles) {
		corner = trans * corner;
	}

	/* Out of the surface: the face normal of the triangle closest to the point (the hit direction can
	 * point either way, see DentNow), the hit direction when no triangle is found. */
	mt::vec3 normal = -inward.SafeNormalized(-mt::axisZ3);
	float closest = FLT_MAX;
	for (unsigned int t = 0, size = triangles.size(); t + 2 < size; t += 3) {
		const mt::vec3 faceNormal = mt::cross(triangles[t + 1] - triangles[t], triangles[t + 2] - triangles[t]);
		if (faceNormal.LengthSquared() < 1e-12f) {
			continue;
		}
		const float distance = (closest_on_triangle(point, triangles[t], triangles[t + 1], triangles[t + 2]) - point).LengthSquared();
		if (distance < closest) {
			closest = distance;
			normal = faceNormal.Normalized();
		}
	}
	const mt::vec3 helper = (std::abs(normal.z) < 0.9f) ? mt::axisZ3 : mt::axisX3;
	const mt::vec3 side = mt::cross(helper, normal).SafeNormalized(mt::axisX3);
	mt::vec3 axisU;
	if (along) {
		// Scrape: lined up with the slide.
		axisU = (*along - normal * mt::dot(*along, normal)).SafeNormalized(side);
	}
	else {
		const float turn = std::uniform_real_distribution<float>(0.0f, 6.2831853f)(m_random);
		axisU = side * std::cos(turn) + mt::cross(normal, side) * std::sin(turn);
	}
	const mt::vec3 axisV = mt::cross(normal, axisU);
	const float half = ((settings.decal_size > 0.0f) ? settings.decal_size : 0.5f) * 0.5f;
	// Off the surface against z-fighting.
	const float lift = std::max(half * 0.004f, 0.001f);


	RAS_DisplayArray *array = new RAS_DisplayArray(RAS_DisplayArray::TRIANGLES, meshmat->GetDisplayArray()->GetFormat());
	const mt::vec3 tangent = (invtrans * axisU - invOrigin).SafeNormalized(mt::axisX3);
	unsigned int index = 0;
	std::vector<mt::vec3> polygon;
	for (unsigned int t = 0, size = triangles.size(); t + 2 < size; t += 3) {
		polygon.clear();
		for (unsigned int k = 0; k < 3; ++k) {
			const mt::vec3 offset = triangles[t + k] - point;
			polygon.push_back(mt::vec3(mt::dot(offset, axisU), mt::dot(offset, axisV), mt::dot(offset, normal)) / half);
		}
		const mt::vec3 faceBox = mt::cross(polygon[1] - polygon[0], polygon[2] - polygon[0]);
		// Facing the hit only (the back side of a thin wall stays clean).
		if (faceBox.z <= 0.3f * faceBox.Length()) {
			continue;
		}
		for (int axis = 0; axis < 3 && polygon.size() >= 3; ++axis) {
			clip_polygon(polygon, axis, 1.0f);
			clip_polygon(polygon, axis, -1.0f);
		}
		if (polygon.size() < 3) {
			continue;
		}

		const mt::vec3 faceNormal = (axisU * faceBox.x + axisV * faceBox.y + normal * faceBox.z).SafeNormalized(normal);
		const mt::vec3 localNormal = (invtrans * faceNormal - invOrigin).SafeNormalized(mt::axisZ3);
		const unsigned int first = index;
		for (const mt::vec3& box : polygon) {
			const mt::vec3 world = point + (axisU * box.x + axisV * box.y + normal * box.z) * half + faceNormal * lift;
			mt::vec2_packed uvs[RAS_Texture::MaxUnits];
			for (unsigned short u = 0; u < RAS_Texture::MaxUnits; ++u) {
				uvs[u] = mt::vec2_packed(mt::vec2(box.x * 0.5f + 0.5f, box.y * 0.5f + 0.5f));
			}
			unsigned int colors[RAS_Texture::MaxUnits];
			std::fill(colors, colors + RAS_Texture::MaxUnits, 0xFFFFFFFF);
			array->AddVertex(mt::vec3_packed(invtrans * world), mt::vec3_packed(localNormal),
			                 mt::vec4_packed(mt::vec4(tangent.x, tangent.y, tangent.z, 1.0f)),
			                 uvs, colors, index, 0, mt::vec4_packed(mt::zero4), mt::vec4_packed(mt::zero4));
			++index;
		}
		for (unsigned int k = 1; k + 1 < polygon.size(); ++k) {
			const unsigned int corners[3] = {first, first + k, first + k + 1};
			for (unsigned int v : corners) {
				array->AddPrimitiveIndex(v);
				array->AddTriangleIndex(v);
			}
		}
	}
	if (index == 0) {
		delete array;
		return;
	}

	KX_Mesh *mesh = new KX_Mesh(m_scene, "Decal", templateMesh->GetLayersInfo());
	mesh->AddMaterial(meshmat->GetBucket(), meshmat->GetIndex(), array);
	mesh->EndConversion(m_scene->GetBoundingBoxManager());
	KX_GetActiveEngine()->GetConverter()->RegisterMesh(m_scene, mesh);

	// Over Max Decals: the oldest ones of this target go.
	const int maxDecals = std::max(settings.max_decals, 1);
	int count = 0;
	for (std::deque<Decal>::reverse_iterator it = m_decals.rbegin(); it != m_decals.rend(); ++it) {
		if (it->m_target == gameobj && !it->m_removing && ++count >= maxDecals) {
			it->m_removing = true;
			m_scene->DelayedRemoveObject(it->m_object);
		}
	}

	const float lifespan = (settings.decal_life > 0.0f) ? settings.decal_life * LIFESPAN_TICKS_PER_SECOND : 0.0f;
	KX_GameObject *decal = m_scene->AddReplicaObject(templateobj, nullptr, lifespan);
	decal->ReplaceMesh(mesh, true, false);
	decal->NodeSetWorldPosition(gameobj->NodeGetWorldPosition());
	decal->NodeSetGlobalOrientation(gameobj->NodeGetWorldOrientation());
	decal->NodeSetWorldScale(gameobj->NodeGetWorldScaling());
	decal->NodeUpdate();
	decal->SetParent(gameobj, false, true);
	m_decals.push_back({decal, gameobj, mesh, false});
	decal->Release();
}

bool KX_DestructionManager::ResetDent(KX_GameObject *gameobj)
{
	KX_DentDeformer *deformer = gameobj ? gameobj->GetDentDeformer(false) : nullptr;
	if (!deformer || !deformer->IsDented()) {
		return false;
	}
	deformer->Reset();
	if ((gameobj->GetBlenderObject()->deform.flags & DEFORM_UPDATE_PHYSICS) && !contains(m_dirtyShapes, gameobj)) {
		m_dirtyShapes.push_back(gameobj);
	}
	return true;
}

void KX_DestructionManager::UpdatePhysicsShapes()
{
	for (KX_GameObject *gameobj : m_dirtyShapes) {
		PHY_IPhysicsController *ctrl = gameobj->GetPhysicsController();
		// Triangle mesh and convex hull bounds only (no-op otherwise). Dupli: the shape is shared
		// by the instances of the mesh.
		if (!ctrl || !ctrl->ReinstancePhysicsShape(nullptr, nullptr, true)) {
			continue;
		}
		// Bodies asleep on the old surface would float over the dent.
		const Entry *entry = FindEntry(gameobj);
		if (entry) {
			for (const std::pair<KX_GameObject *, long long>& touch : entry->m_touching) {
				PHY_IPhysicsController *otherctrl = touch.first->GetPhysicsController();
				if (otherctrl) {
					otherctrl->SetActive(true);
				}
			}
		}
	}
	m_dirtyShapes.clear();
}

std::vector<KX_GameObject *> KX_DestructionManager::Shatter(KX_GameObject *gameobj, const mt::vec3 *origin, const float *burst)
{
	std::vector<KX_GameObject *> pieces;

	const Entry *entry = gameobj ? FindEntry(gameobj) : nullptr;
	if (!entry || entry->m_done || !is_destructible(gameobj)) {
		return pieces;
	}

	if (is_explosive(gameobj)) {
		// Breaking sets the explosive off, and the blast throws its fragments.
		Detonate(gameobj, &pieces);
		return pieces;
	}

	return ShatterNow(gameobj, origin ? *origin : gameobj->NodeGetWorldPosition(),
	                  burst ? *burst : gameobj->GetBlenderObject()->destruction.burst_speed);
}

std::vector<KX_GameObject *> KX_DestructionManager::ShatterNow(KX_GameObject *gameobj, const mt::vec3& center, float burstSpeed)
{
	std::vector<KX_GameObject *> pieces;

	Object *blenderobj = gameobj->GetBlenderObject();
	const RangeDestructionSettings& settings = blenderobj->destruction;
	Group *group = settings.fragments;
	if (!group) {
		CM_Warning("\"" << gameobj->GetName() << "\" is destructible but has no Fragments group; it can't break.");
		return pieces;
	}

	// The pieces were fractured in the object's local space: the group objects are the templates,
	// usually on an inactive layer. Children come along with their parent.
	SCA_LogicManager *logicmgr = m_scene->GetLogicManager();
	std::vector<KX_GameObject *> templates;
	for (GroupObject *go = (GroupObject *)group->gobject.first; go; go = go->next) {
		if (!go->ob || go->ob == blenderobj) {
			continue;
		}
		KX_GameObject *templateobj = static_cast<KX_GameObject *>(logicmgr->FindGameObjByBlendObj(go->ob));
		if (templateobj && !templateobj->GetParent()) {
			templates.push_back(templateobj);
		}
	}

	if (templates.empty()) {
		CM_Warning("\"" << gameobj->GetName() << "\": the Fragments group \"" << (group->id.name + 2)
		           << "\" has no object in this scene; it can't break.");
		return pieces;
	}

	// Set before adding the pieces: a replica can register a new entry and move the others.
	Entry *entry = FindEntry(gameobj);
	if (entry) {
		entry->m_done = true;
	}

	const mt::vec3 position = gameobj->NodeGetWorldPosition();
	const mt::mat3 orientation = gameobj->NodeGetWorldOrientation();
	const mt::vec3 scale = gameobj->NodeGetWorldScaling();
	const mt::vec3 offset(group->dupli_ofs);

	const bool inherit = (settings.flags & DESTRUCTION_INHERIT_VELOCITY) && gameobj->IsDynamic();
	const mt::vec3 linearVelocity = inherit ? gameobj->GetLinearVelocity(false) : mt::zero3;
	const mt::vec3 angularVelocity = inherit ? gameobj->GetAngularVelocity(false) : mt::zero3;

	const float lifespan = (settings.debris_lifetime > 0.0f) ? settings.debris_lifetime * LIFESPAN_TICKS_PER_SECOND : 0.0f;

	pieces.reserve(templates.size());
	for (KX_GameObject *templateobj : templates) {
		KX_GameObject *piece = m_scene->AddReplicaObject(templateobj, gameobj, lifespan);

		// World transform = object world * piece transform in the group.
		const mt::vec3 piecePosition = position + orientation * (scale * (templateobj->NodeGetWorldPosition() - offset));
		piece->NodeSetWorldPosition(piecePosition);
		piece->NodeSetGlobalOrientation(orientation * templateobj->NodeGetWorldOrientation());
		piece->NodeSetWorldScale(scale * templateobj->NodeGetWorldScaling());
		piece->NodeUpdate();

		if (piece->IsDynamic()) {
			mt::vec3 velocity = linearVelocity + mt::cross(angularVelocity, piecePosition - position);
			if (burstSpeed != 0.0f) {
				velocity += (piecePosition - center).SafeNormalized(mt::axisZ3) * burstSpeed;
			}
			piece->SetLinearVelocity(velocity, false);
			piece->SetAngularVelocity(angularVelocity, false);
		}

		// AddReplicaObject returns an extra reference, the scene lists own the piece.
		piece->Release();
		pieces.push_back(piece);
	}

	m_scene->DelayedRemoveObject(gameobj);

	AddDebris(pieces);
	gameobj->RunBreakCallbacks(pieces);

	return pieces;
}

void KX_DestructionManager::AddDebris(const std::vector<KX_GameObject *>& pieces)
{
	m_debris.insert(m_debris.end(), pieces.begin(), pieces.end());
	if (m_maxDebris <= 0) {
		return;
	}
	while (m_debris.size() > (size_t)m_maxDebris) {
		m_scene->DelayedRemoveObject(m_debris.front());
		m_debris.pop_front();
	}
}

bool KX_DestructionManager::Detonate(KX_GameObject *gameobj, std::vector<KX_GameObject *> *fragments)
{
	Entry *entry = gameobj ? FindEntry(gameobj) : nullptr;
	if (!entry || entry->m_done || !is_explosive(gameobj)) {
		return false;
	}

	// Set before anything is added: a replica can register a new entry and move the others.
	entry->m_done = true;
	entry->m_armFrame = -1;
	entry->m_fuse = 0.0f;

	const RangeExplosiveSettings& settings = gameobj->GetBlenderObject()->explosive;
	const mt::vec3 center = gameobj->NodeGetWorldPosition();

	if (settings.effect) {
		KX_GameObject *templateobj = static_cast<KX_GameObject *>(m_scene->GetLogicManager()->FindGameObjByBlendObj(settings.effect));
		if (templateobj) {
			const float lifespan = (settings.effect_life > 0.0f) ? settings.effect_life * LIFESPAN_TICKS_PER_SECOND : 0.0f;
			KX_GameObject *effect = m_scene->AddReplicaObject(templateobj, nullptr, lifespan);
			effect->NodeSetWorldPosition(center);
			effect->NodeUpdate();
			effect->Release();
		}
		else {
			CM_Warning("\"" << gameobj->GetName() << "\": the explosion Effect \"" << (settings.effect->id.name + 2)
			           << "\" is not in this scene.");
		}
	}

	std::vector<KX_GameObject *> pieces;
	if (is_destructible(gameobj)) {
		pieces = ShatterNow(gameobj, center, 0.0f);
	}
	if (pieces.empty()) {
		m_scene->DelayedRemoveObject(gameobj);
	}

	std::vector<KX_GameObject *> ignore = pieces;
	ignore.push_back(gameobj);
	Explode(center, settings.radius, settings.force, settings.up_bias, settings.flags & EXPLOSIVE_OCCLUSION, 0xFFFF, ignore);

	// The fragments start at the center, nothing can shield them.
	PushFragments(pieces, center, settings.radius, settings.force, settings.up_bias);

	gameobj->RunExplodeCallbacks(center);

	if (fragments) {
		*fragments = pieces;
	}
	return true;
}

std::vector<KX_GameObject *> KX_DestructionManager::Explode(const mt::vec3& center, float radius, float force, float upBias,
                                                            bool occlusion, unsigned short mask,
                                                            const std::vector<KX_GameObject *>& ignore)
{
	std::vector<KX_GameObject *> reached;

	PHY_IPhysicsEnvironment *environment = m_scene->GetPhysicsEnvironment();
	if (!environment || radius <= 0.0f) {
		return reached;
	}

	std::vector<PHY_IPhysicsController *> controllers;
	environment->SphereQuery(center, radius, controllers);

	// Resolve the targets first: breaking objects below adds fragments to the physics world.
	std::vector<KX_GameObject *> targets;
	for (PHY_IPhysicsController *ctrl : controllers) {
		KX_ClientObjectInfo *info = static_cast<KX_ClientObjectInfo *>(ctrl->GetNewClientInfo());
		KX_GameObject *gameobj = info ? info->m_gameobject : nullptr;
		if (gameobj && !contains(ignore, gameobj) && !contains(targets, gameobj)) {
			targets.push_back(gameobj);
		}
	}

	for (KX_GameObject *gameobj : targets) {
		if (!(gameobj->GetCollisionGroup() & mask)) {
			continue;
		}

		const Entry *entry = FindEntry(gameobj);
		if (entry && entry->m_done) {
			continue;
		}
		const bool destructible = entry && is_destructible(gameobj);
		const bool explosive = entry && is_explosive(gameobj);
		const bool deformable = entry && is_deformable(gameobj);
		if (!destructible && !explosive && !deformable && !gameobj->IsDynamic()) {
			continue;
		}

		const float impulse = impulse_at(gameobj->NodeGetWorldPosition(), center, radius, force);
		if (impulse <= 0.0f || (occlusion && Occluded(center, gameobj, ignore))) {
			continue;
		}

		reached.push_back(gameobj);

		const bool breaks = destructible && impulse >= entry->m_breakImpulse;
		if (explosive) {
			const RangeExplosiveSettings& settings = gameobj->GetBlenderObject()->explosive;
			if (breaks || ((settings.flags & EXPLOSIVE_CHAIN_REACTION) && impulse >= settings.impact_impulse)) {
				// One link of a chain reaction per frame.
				Arm(FindEntry(gameobj), m_frame + 1);
				continue;
			}
		}
		else if (breaks) {
			const std::vector<KX_GameObject *> pieces = ShatterNow(gameobj, center, 0.0f);
			if (!pieces.empty()) {
				PushFragments(pieces, center, radius, force, upBias);
				continue;
			}
		}

		if (deformable && !breaks) {
			BlastDent(gameobj, center, radius, force);
		}

		Push(gameobj, center, impulse, upBias);
	}

	return reached;
}

void KX_DestructionManager::PushFragments(const std::vector<KX_GameObject *>& pieces, const mt::vec3& center, float radius,
                                          float force, float upBias)
{
	// Shared by mass, the fragments fly off about as fast as the whole object would have.
	float totalMass = 0.0f;
	for (KX_GameObject *piece : pieces) {
		if (piece->IsDynamic()) {
			totalMass += piece->GetMass();
		}
	}
	if (totalMass <= 0.0f) {
		return;
	}

	for (KX_GameObject *piece : pieces) {
		if (piece->IsDynamic()) {
			const float share = piece->GetMass() / totalMass;
			Push(piece, center, impulse_at(piece->NodeGetWorldPosition(), center, radius, force) * share, upBias);
		}
	}
}

void KX_DestructionManager::Push(KX_GameObject *gameobj, const mt::vec3& center, float impulse, float upBias)
{
	PHY_IPhysicsController *ctrl = gameobj->GetPhysicsController();
	// ApplyImpulse() on a static body turns it kinematic.
	if (impulse <= 0.0f || !ctrl || !gameobj->IsDynamic() || gameobj->IsDynamicsSuspended()) {
		return;
	}

	const mt::vec3 position = gameobj->NodeGetWorldPosition();
	const mt::vec3 away = (position - center).SafeNormalized(mt::axisZ3);
	const mt::vec3 direction = (away + mt::axisZ3 * upBias).SafeNormalized(mt::axisZ3);

	std::uniform_real_distribution<float> jitter(-0.1f, 0.1f);
	const mt::vec3 offset(jitter(m_random), jitter(m_random), jitter(m_random));
	ctrl->ApplyImpulse(position + offset, direction * impulse, false);
}

bool KX_DestructionManager::Occluded(const mt::vec3& center, KX_GameObject *target, const std::vector<KX_GameObject *>& ignore)
{
	OcclusionFilter filter{target, &ignore};
	KX_RayCast::Callback<OcclusionFilter, void> callback(&filter);
	return KX_RayCast::RayTest(m_scene->GetPhysicsEnvironment(), center, target->NodeGetWorldPosition(), callback);
}

// The panel settings, so inactive templates (never registered) answer too.
bool KX_DestructionManager::IsDestructible(KX_GameObject *gameobj) const
{
	return is_destructible(gameobj);
}

bool KX_DestructionManager::IsExplosive(KX_GameObject *gameobj) const
{
	return is_explosive(gameobj);
}

float KX_DestructionManager::GetBreakImpulse(KX_GameObject *gameobj) const
{
	const Entry *entry = FindEntry(gameobj);
	return (entry && is_destructible(gameobj)) ? entry->m_breakImpulse : 0.0f;
}

bool KX_DestructionManager::SetBreakImpulse(KX_GameObject *gameobj, float impulse)
{
	Entry *entry = FindEntry(gameobj);
	if (!entry || !is_destructible(gameobj)) {
		return false;
	}
	entry->m_breakImpulse = std::max(impulse, 0.0f);
	return true;
}

float KX_DestructionManager::GetFuse(KX_GameObject *gameobj) const
{
	const Entry *entry = FindEntry(gameobj);
	return (entry && is_explosive(gameobj)) ? entry->m_fuse : 0.0f;
}

bool KX_DestructionManager::SetFuse(KX_GameObject *gameobj, float seconds)
{
	Entry *entry = FindEntry(gameobj);
	if (!entry || !is_explosive(gameobj)) {
		return false;
	}
	entry->m_fuse = std::max(seconds, 0.0f);
	return true;
}

int KX_DestructionManager::GetMaxDebris() const
{
	return m_maxDebris;
}

void KX_DestructionManager::SetMaxDebris(int maxDebris)
{
	m_maxDebris = std::max(maxDebris, 0);
	AddDebris({});
}

void KX_DestructionManager::Update(float frameStep)
{
	if (!m_deadDecalMeshes.empty()) {
		BL_Converter *converter = KX_GetActiveEngine()->GetConverter();
		for (KX_Mesh *mesh : m_deadDecalMeshes) {
			converter->UnregisterMesh(m_scene, mesh);
		}
		m_deadDecalMeshes.clear();
	}

	for (Entry& entry : m_entries) {
		if (entry.m_dentCooldown > 0.0f) {
			entry.m_dentCooldown -= frameStep;
		}
		// Contacts that ended: a new touch is a new hit.
		const long long frame = m_frame;
		entry.m_touching.erase(std::remove_if(entry.m_touching.begin(), entry.m_touching.end(),
		                                      [frame](const std::pair<KX_GameObject *, long long>& touch) { return touch.second < frame - 1; }),
		                       entry.m_touching.end());
		if (!entry.m_done && entry.m_fuse > 0.0f) {
			entry.m_fuse -= frameStep;
			if (entry.m_fuse <= 0.0f) {
				entry.m_fuse = 0.0f;
				Arm(&entry, m_frame);
			}
		}
	}

	if (!m_pending.empty()) {
		// Breaking adds objects and can detonate, never iterate the member list.
		std::vector<PendingBreak> pending;
		pending.swap(m_pending);
		for (const PendingBreak& entry : pending) {
			Shatter(entry.m_object, &entry.m_origin, nullptr);
		}
	}

	// Explosives armed for this frame. Their blasts arm others for the next one.
	std::vector<KX_GameObject *> armed;
	for (const Entry& entry : m_entries) {
		if (!entry.m_done && entry.m_armFrame >= 0 && entry.m_armFrame <= m_frame) {
			armed.push_back(entry.m_object);
		}
	}
	for (KX_GameObject *gameobj : armed) {
		Detonate(gameobj);
	}

	if (!m_pendingDents.empty()) {
		std::vector<PendingDent> pending;
		pending.swap(m_pendingDents);
		for (const PendingDent& dent : pending) {
			Entry *entry = FindEntry(dent.m_object);
			// Broken or detonated meanwhile.
			if (!entry || entry->m_done) {
				continue;
			}
			entry->m_dentCooldown = DENT_COOLDOWN;
			DentNow(dent.m_object, dent.m_point, dent.m_direction, dent.m_impulse, &dent.m_hitter);
		}
	}

	if (!m_pendingScrapes.empty()) {
		std::vector<PendingScrape> pending;
		pending.swap(m_pendingScrapes);
		for (const PendingScrape& scrape : pending) {
			const Entry *entry = FindEntry(scrape.m_object);
			if (entry && !entry->m_done && GetDentDeformer(scrape.m_object)) {
				AddDecal(scrape.m_object, scrape.m_point, -scrape.m_normal, &scrape.m_along);
			}
		}
	}

	UpdatePhysicsShapes();

	++m_frame;
}

void KX_DestructionManager::Merge(KX_DestructionManager& other)
{
	m_entries.insert(m_entries.end(), other.m_entries.begin(), other.m_entries.end());
	m_pending.insert(m_pending.end(), other.m_pending.begin(), other.m_pending.end());
	other.m_entries.clear();
	other.m_pending.clear();
	m_pendingDents.insert(m_pendingDents.end(), other.m_pendingDents.begin(), other.m_pendingDents.end());
	other.m_pendingDents.clear();
	m_dirtyShapes.insert(m_dirtyShapes.end(), other.m_dirtyShapes.begin(), other.m_dirtyShapes.end());
	other.m_dirtyShapes.clear();
	AddDebris(std::vector<KX_GameObject *>(other.m_debris.begin(), other.m_debris.end()));
	other.m_debris.clear();
}
