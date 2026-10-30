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

/** \file CcdCollisionDispatcher.h
 *  \ingroup physbullet
 *
 * Collision dispatcher that runs the narrowphase (processCollision) of the overlapping
 * pairs in parallel, in the spirit of btCollisionDispatcherMt from Bullet 2.87, without
 * touching the bundled Bullet 2.84.
 *
 * Determinism: while a parallel dispatch is in progress, manifold creation and release
 * are recorded with the index of the pair that caused them and are replayed afterwards
 * in pair order, so the dispatcher manifold array ends up exactly as the serial
 * dispatcher would have left it (the solver sees the same order).
 *
 * Can be disabled with the environment variable RANGE_PHYSICS_MT=0. Always serial on
 * the Web build (no threads).
 */

#ifndef __CCD_COLLISION_DISPATCHER_H__
#define __CCD_COLLISION_DISPATCHER_H__

#include "BulletCollision/CollisionDispatch/btCollisionDispatcher.h"

#include <mutex>
#include <vector>

class btConvexConvexThreadSafeCreateFunc;

class CcdCollisionDispatcher : public btCollisionDispatcher
{
public:
	CcdCollisionDispatcher(btCollisionConfiguration *collisionConfiguration);
	virtual ~CcdCollisionDispatcher();

	virtual btPersistentManifold *getNewManifold(const btCollisionObject *b0, const btCollisionObject *b1);
	virtual void releaseManifold(btPersistentManifold *manifold);
	virtual void *allocateCollisionAlgorithm(int size);
	virtual void freeCollisionAlgorithm(void *ptr);
	virtual void dispatchAllCollisionPairs(btOverlappingPairCache *pairCache, const btDispatcherInfo& dispatchInfo,
	                                       btDispatcher *dispatcher);

	bool IsParallelEnabled() const
	{
		return m_parallelEnabled;
	}

	/// Internal, used by the task callback.
	void ProcessJob(int index);

private:
	struct PairJob {
		btBroadphasePair *pair;
		int seq;
	};

	struct ManifoldEvent {
		int pairIndex;
		int seq;
		bool create;
		btPersistentManifold *manifold;
	};

	bool CanRunParallel(btOverlappingPairCache *pairCache, const btDispatcherInfo& dispatchInfo) const;
	void RecordEvent(bool create, btPersistentManifold *manifold);
	void ReplayEvents();

	bool m_parallelEnabled;
	/// True while pairs are processed with recorded manifold events (prepass + parallel phase).
	bool m_recording;
	std::mutex m_lock;
	std::vector<PairJob> m_jobs;
	std::vector<ManifoldEvent> m_events;
	const btDispatcherInfo *m_dispatchInfo;
	btConvexConvexThreadSafeCreateFunc *m_convexConvexCreateFunc;
};

#endif  // __CCD_COLLISION_DISPATCHER_H__
