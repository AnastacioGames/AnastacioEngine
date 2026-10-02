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
#include "KX_RayCast.h"
#include "KX_Scene.h"

#include "SCA_LogicManager.h"
#include "PHY_DynamicTypes.h"
#include "PHY_IPhysicsController.h"
#include "PHY_IPhysicsEnvironment.h"

#include "CM_List.h"
#include "CM_Message.h"

#include "DNA_group_types.h"
#include "DNA_object_types.h"

#include <algorithm>

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
	return (breaks_on_collision(gameobj) || explodes_on_impact(gameobj) || dents_on_collision(gameobj)) &&
	       gameobj->GetPhysicsController() &&
	       !gameobj->GetClientInfo().isSensor();
}

static bool contains(const std::vector<KX_GameObject *>& list, KX_GameObject *gameobj)
{
	return std::find(list.begin(), list.end(), gameobj) != list.end();
}

/// Blast impulse at a point, linear falloff to 0 at the radius.
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
		// One dent per object and frame, the strongest contact.
		for (PendingDent& pending : m_pendingDents) {
			if (pending.m_object == gameobj) {
				if (total > pending.m_impulse) {
					pending = {gameobj, origin, normal, total};
				}
				return;
			}
		}
		m_pendingDents.push_back({gameobj, origin, normal, total});
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

bool KX_DestructionManager::DentNow(KX_GameObject *gameobj, const mt::vec3& point, const mt::vec3& direction, float impulse)
{
	const RangeDeformSettings& settings = gameobj->GetBlenderObject()->deform;
	const float depth = std::min((impulse - settings.dent_impulse) * settings.depth, settings.max_depth);
	if (depth <= 0.0f) {
		return false;
	}

	KX_DentDeformer *deformer = GetDentDeformer(gameobj);
	if (!deformer) {
		return false;
	}

	/* Into the object whatever the contact normal convention: towards the center of the mesh bounds,
	 * the origin can be far from the mesh. */
	const mt::mat3x4 trans = gameobj->NodeGetWorldTransform();
	mt::vec3 aabbMin, aabbMax;
	deformer->GetBoundingBox()->GetAabb(aabbMin, aabbMax);
	const mt::vec3 toCenter = trans * ((aabbMin + aabbMax) * 0.5f) - point;
	mt::vec3 inward = direction.SafeNormalized(mt::zero3);
	if (inward.LengthSquared() == 0.0f) {
		inward = toCenter.SafeNormalized(-mt::axisZ3);
	}
	else if (mt::dot(inward, toCenter) < 0.0f) {
		inward = -inward;
	}

	if (!deformer->AddDent(trans, point, inward * depth, settings.radius, settings.max_depth)) {
		return false;
	}

	Dented(gameobj, point, impulse);
	return true;
}

void KX_DestructionManager::BlastDent(KX_GameObject *gameobj, const mt::vec3& center, float radius, float force)
{
	const RangeDeformSettings& settings = gameobj->GetBlenderObject()->deform;
	KX_DentDeformer *deformer = GetDentDeformer(gameobj);
	if (deformer && deformer->AddBlastDent(gameobj->NodeGetWorldTransform(), center, radius, force,
	                                       settings.dent_impulse, settings.depth, settings.max_depth))
	{
		Dented(gameobj, center, impulse_at(gameobj->NodeGetWorldPosition(), center, radius, force));
	}
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
			DentNow(dent.m_object, dent.m_point, dent.m_direction, dent.m_impulse);
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
