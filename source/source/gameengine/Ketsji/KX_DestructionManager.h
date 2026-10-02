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

/** \file KX_DestructionManager.h
 *  \ingroup ketsji
 *
 * Native pre-fractured destruction and explosives (Object.gameflag2 & OB_DESTRUCTIBLE / OB_EXPLOSIVE,
 * settings in Object.destruction / Object.explosive). One per KX_Scene.
 *
 * A strong enough contact, an explosion or KX_GameObject.shatter() replaces a destructible by replicas
 * of the objects of its 'fragments' group, which were fractured in the object's local space (see the
 * "Generate Fragments..." operator). An explosive detonates on its fuse, on impact, by chain reaction
 * or by KX_GameObject.detonate(): radial impulse, broken destructibles, armed explosives. An object
 * with both detonates when it breaks and breaks when it detonates.
 *
 * A deformable (OB_DEFORMABLE, settings in Object.deform) dents instead: hits between its dent
 * impulse and its break impulse push the vertices around the contact point (KX_DentDeformer).
 */

#ifndef __KX_DESTRUCTIONMANAGER_H__
#define __KX_DESTRUCTIONMANAGER_H__

#include "mathfu.h"

#include <deque>
#include <random>
#include <vector>

class KX_DentDeformer;
class KX_GameObject;
class KX_Mesh;
class KX_Scene;
class PHY_ICollData;

class KX_DestructionManager
{
public:
	explicit KX_DestructionManager(KX_Scene *scene);

	/// Active objects flagged OB_DESTRUCTIBLE, OB_EXPLOSIVE or OB_DEFORMABLE, from scene conversion and object
	/// replication. Requests the collision callbacks for Break on Collision / Explode on Impact and
	/// starts the fuse.
	void RegisterObject(KX_GameObject *gameobj);
	/// Called from KX_Scene::NewRemoveObject, drops every reference to the object.
	void UnregisterObject(KX_GameObject *gameobj);

	/// Contact from KX_CollisionEventManager::NextFrame. Queues the break (or arms the explosive) when
	/// the summed applied impulse of the contact reaches the limit; it happens in Update(). Dents only
	/// come from new contacts with other: resting, rolling or sliding objects don't dig a groove.
	void NotifyCollision(KX_GameObject *gameobj, KX_GameObject *other, const PHY_ICollData *collData, bool first);

	/** Break the object now: add its fragments and remove it at the end of the frame. An explosive
	 * destructible detonates instead (its fragments get the blast).
	 * \param origin World point the burst pushes away from, nullptr = object position.
	 * \param burst Outward speed, nullptr = burst_speed of the object.
	 * \return The added fragments, empty when the object isn't destructible, is already broken
	 * or has no fragments.
	 */
	std::vector<KX_GameObject *> Shatter(KX_GameObject *gameobj, const mt::vec3 *origin = nullptr, const float *burst = nullptr);

	/** Explode the object now with its settings: effect, blast, and its fragments when it is also
	 * destructible (removed otherwise). False when it isn't explosive or already detonated.
	 * \param fragments Receives the added fragments, may be nullptr.
	 */
	bool Detonate(KX_GameObject *gameobj, std::vector<KX_GameObject *> *fragments = nullptr);

	/** Radial impulse force * (1 - distance / radius) on the objects around center, see
	 * KX_Scene.explode(). Destructibles above their break impulse break now, explosives above their
	 * impact impulse detonate next frame.
	 * \param mask Collision group bits of the objects reached.
	 * \param ignore Objects not reached, and not blocking the occlusion rays.
	 * \return The objects reached (not the new fragments).
	 */
	std::vector<KX_GameObject *> Explode(const mt::vec3& center, float radius, float force, float upBias, bool occlusion,
	                                     unsigned short mask, const std::vector<KX_GameObject *>& ignore);

	/** Dent the object now around a world point along direction, as a hit of the given impulse
	 * (see the Deformation panel). False when it isn't deformable, the impulse is below its dent
	 * impulse or no vertex moved.
	 */
	bool Dent(KX_GameObject *gameobj, const mt::vec3& point, const mt::vec3& direction, float impulse);
	/// Back to the rest shape. False when the object was never dented.
	bool ResetDent(KX_GameObject *gameobj);

	bool IsDestructible(KX_GameObject *gameobj) const;
	bool IsExplosive(KX_GameObject *gameobj) const;
	/// Per instance, starts from the object settings. 0 when not destructible.
	float GetBreakImpulse(KX_GameObject *gameobj) const;
	bool SetBreakImpulse(KX_GameObject *gameobj, float impulse);
	/// Seconds left before the explosion, 0 = no fuse running.
	float GetFuse(KX_GameObject *gameobj) const;
	bool SetFuse(KX_GameObject *gameobj, float seconds);

	/// Most fragments alive at once (Scene > Game Physics > Max Debris), 0 = no limit. Past it the
	/// oldest fragments are removed.
	int GetMaxDebris() const;
	void SetMaxDebris(int maxDebris);

	/// Breaks the objects queued by collisions, runs the fuses and detonates the armed explosives.
	/// Once per logic frame, before the removed objects are freed.
	void Update(float frameStep);

	/// LibLoad: take the objects of a scene merged into this one.
	void Merge(KX_DestructionManager& other);

private:
	struct Entry
	{
		KX_GameObject *m_object;
		float m_breakImpulse;
		float m_fuse;
		/// Explosive: detonates in Update() once m_frame reaches m_armFrame, -1 = not armed.
		long long m_armFrame;
		/// Broken or detonated, waiting for its removal: it never breaks or explodes twice.
		bool m_done;
		/// Deformable: seconds before collisions can dent it again, a resting contact must not
		/// rebuild the mesh every frame.
		float m_dentCooldown;
		/// The "can't dent" warning was printed, once per object.
		bool m_dentWarned;
		/// Deformable: objects in contact and the last frame they were, to tell a hit from a contact
		/// that goes on.
		std::vector<std::pair<KX_GameObject *, long long> > m_touching;
		/// Scrape marks: where the last one went, valid while m_scraped.
		mt::vec3 m_lastScrape;
		bool m_scraped;
	};

	struct PendingScrape
	{
		KX_GameObject *m_object;
		mt::vec3 m_point;
		mt::vec3 m_normal;
		/// Sliding direction, the mark is stretched along it.
		mt::vec3 m_along;
	};

	struct PendingDent
	{
		KX_GameObject *m_object;
		mt::vec3 m_point;
		mt::vec3 m_direction;
		/// Position of the hitting object.
		mt::vec3 m_hitter;
		float m_impulse;
	};

	struct Decal
	{
		KX_GameObject *m_object;
		KX_GameObject *m_target;
		KX_Mesh *m_mesh;
		/// Over the target's Max Decals, waiting for its removal.
		bool m_removing;
	};

	struct PendingBreak
	{
		KX_GameObject *m_object;
		mt::vec3 m_origin;
	};

	Entry *FindEntry(KX_GameObject *gameobj);
	const Entry *FindEntry(KX_GameObject *gameobj) const;
	void Arm(Entry *entry, long long frame);

	/// Dents without the threshold checks, queues the physics shape update. True when a vertex moved.
	bool DentNow(KX_GameObject *gameobj, const mt::vec3& point, const mt::vec3& direction, float impulse,
	             const mt::vec3 *hitter = nullptr);
	/// The dent mesh, created on the first dent; warns once when another deformer owns the mesh.
	KX_DentDeformer *GetDentDeformer(KX_GameObject *gameobj);
	/// After a dent: queues the physics shape update, runs onDent.
	void Dented(KX_GameObject *gameobj, const mt::vec3& point, float impulse);
	/// Explosion dent of a deformable reached by a blast.
	void BlastDent(KX_GameObject *gameobj, const mt::vec3& center, float radius, float force);
	/// Projects the Decal object's material on the target surface around point (mesh decal), parented
	/// to the target. inward points into the surface.
	void AddDecal(KX_GameObject *gameobj, const mt::vec3& point, const mt::vec3& inward, const mt::vec3 *along = nullptr);
	/// Sliding contact on an object with Scrape Marks: queues a mark every Scrape Spacing.
	void Scrape(Entry *entry, KX_GameObject *other, const PHY_ICollData *collData, bool first);
	/// Rebuilds the collision shape of the dented objects asking for it, once per frame.
	void UpdatePhysicsShapes();

	/// Adds the fragments and removes the object, no explosive handling.
	std::vector<KX_GameObject *> ShatterNow(KX_GameObject *gameobj, const mt::vec3& origin, float burst);
	/// Keeps the added fragments in the debris list, removes the oldest past the limit.
	void AddDebris(const std::vector<KX_GameObject *>& pieces);
	/// Blast on the fragments of an object broken by it, each gets its share by mass.
	void PushFragments(const std::vector<KX_GameObject *>& pieces, const mt::vec3& center, float radius, float force,
	                   float upBias);
	/// Impulse away from center (plus up bias) at a point slightly off the center of mass, for spin.
	void Push(KX_GameObject *gameobj, const mt::vec3& center, float impulse, float upBias);
	/// Static geometry between center and the object?
	bool Occluded(const mt::vec3& center, KX_GameObject *target, const std::vector<KX_GameObject *>& ignore);

	KX_Scene *m_scene;
	std::vector<Entry> m_entries;
	std::vector<PendingBreak> m_pending;
	/// Strongest collision dent of each object this frame.
	std::vector<PendingDent> m_pendingDents;
	/// Dented objects whose collision shape follows the mesh (DEFORM_UPDATE_PHYSICS).
	std::vector<KX_GameObject *> m_dirtyShapes;
	/// Scrape marks of this frame, added in Update() (no object is added inside the physics step).
	std::vector<PendingScrape> m_pendingScrapes;
	/// Impact decals alive, oldest first.
	std::deque<Decal> m_decals;
	/// Meshes of removed decals, freed in the next Update() once nothing draws them.
	std::vector<KX_Mesh *> m_deadDecalMeshes;
	/// Fragments alive, oldest first.
	std::deque<KX_GameObject *> m_debris;
	int m_maxDebris;
	/// Update() count, chain reactions wait for the next one.
	long long m_frame;
	std::minstd_rand m_random;
};

#endif  // __KX_DESTRUCTIONMANAGER_H__
