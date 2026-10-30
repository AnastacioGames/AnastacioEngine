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

/** \file gameengine/Physics/Bullet/CcdCollisionDispatcher.cpp
 *  \ingroup physbullet
 */

#include "CcdCollisionDispatcher.h"

#include "BulletCollision/BroadphaseCollision/btBroadphaseProxy.h"
#include "BulletCollision/BroadphaseCollision/btCollisionAlgorithm.h"
#include "BulletCollision/BroadphaseCollision/btOverlappingPairCache.h"
#include "BulletCollision/CollisionDispatch/btCollisionConfiguration.h"
#include "BulletCollision/CollisionDispatch/btCollisionObject.h"
#include "BulletCollision/CollisionDispatch/btCollisionObjectWrapper.h"
#include "BulletCollision/CollisionDispatch/btConvexConvexAlgorithm.h"
#include "BulletCollision/CollisionDispatch/btManifoldResult.h"
#include "BulletCollision/CollisionShapes/btCollisionShape.h"
#include "BulletCollision/NarrowPhaseCollision/btPersistentManifold.h"
#include "BulletCollision/NarrowPhaseCollision/btVoronoiSimplexSolver.h"
#include "LinearMath/btPoolAllocator.h"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <new>

#ifndef __EMSCRIPTEN__
#  include "BLI_task.h"
#endif

extern int gNumManifold;

/* Minimum amount of overlapping pairs before going parallel, below it the task overhead wins. */
static const int CCD_DISPATCH_MIN_PAIRS = 8;

/* Pair being processed by the current thread and the order of its manifold events. */
static thread_local int tl_pairIndex = -1;
static thread_local int tl_seq = 0;

/** Bullet 2.84 convex-convex algorithms share the simplex solver of the collision
 * configuration, which holds state during GJK and is therefore not thread safe.
 * This create func gives every algorithm its own solver, stored right after it in the
 * same heap block (the solver is trivially destructible, so the usual
 * ~algorithm() + freeCollisionAlgorithm() sequence releases everything).
 * GJK resets the solver on every query so the results are identical to the shared one.
 */
class btConvexConvexThreadSafeCreateFunc : public btConvexConvexAlgorithm::CreateFunc
{
public:
	btConvexConvexThreadSafeCreateFunc(const btConvexConvexAlgorithm::CreateFunc& orig)
		:btConvexConvexAlgorithm::CreateFunc(orig.m_simplexSolver, orig.m_pdSolver)
	{
		m_numPerturbationIterations = orig.m_numPerturbationIterations;
		m_minimumPointsPerturbationThreshold = orig.m_minimumPointsPerturbationThreshold;
	}

	static size_t SolverOffset()
	{
		return (sizeof(btConvexConvexAlgorithm) + 15) & ~size_t(15);
	}

	virtual btCollisionAlgorithm *CreateCollisionAlgorithm(btCollisionAlgorithmConstructionInfo& ci,
	                                                       const btCollisionObjectWrapper *body0Wrap,
	                                                       const btCollisionObjectWrapper *body1Wrap)
	{
		/* Always outside the dispatcher pool: freeCollisionAlgorithm() sees an invalid pool
		 * pointer and calls btAlignedFree(). */
		char *mem = (char *)btAlignedAlloc(SolverOffset() + sizeof(btVoronoiSimplexSolver), 16);
		btVoronoiSimplexSolver *solver = new(mem + SolverOffset()) btVoronoiSimplexSolver();
		return new(mem) btConvexConvexAlgorithm(ci.m_manifold, ci, body0Wrap, body1Wrap, solver, m_pdSolver,
		                                        m_numPerturbationIterations, m_minimumPointsPerturbationThreshold);
	}
};

static bool ccd_physics_mt_env_enabled()
{
#ifdef __EMSCRIPTEN__
	return false;
#else
	const char *env = getenv("RANGE_PHYSICS_MT");
	if (env && (strcmp(env, "0") == 0 || strcmp(env, "off") == 0 || strcmp(env, "false") == 0)) {
		return false;
	}
	return true;
#endif
}

CcdCollisionDispatcher::CcdCollisionDispatcher(btCollisionConfiguration *collisionConfiguration)
	:btCollisionDispatcher(collisionConfiguration),
	m_parallelEnabled(ccd_physics_mt_env_enabled()),
	m_recording(false),
	m_dispatchInfo(nullptr),
	m_convexConvexCreateFunc(nullptr)
{
	/* Replace the shared-solver convex-convex create func everywhere it is registered. */
	btCollisionAlgorithmCreateFunc *orig = collisionConfiguration->getCollisionAlgorithmCreateFunc(
		CONVEX_HULL_SHAPE_PROXYTYPE, CONVEX_HULL_SHAPE_PROXYTYPE);
	if (orig) {
		m_convexConvexCreateFunc = new btConvexConvexThreadSafeCreateFunc(
			*static_cast<btConvexConvexAlgorithm::CreateFunc *>(orig));
		for (int i = 0; i < MAX_BROADPHASE_COLLISION_TYPES; i++) {
			for (int j = 0; j < MAX_BROADPHASE_COLLISION_TYPES; j++) {
				if (m_doubleDispatch[i][j] == orig) {
					m_doubleDispatch[i][j] = m_convexConvexCreateFunc;
				}
			}
		}
	}
}

CcdCollisionDispatcher::~CcdCollisionDispatcher()
{
	delete m_convexConvexCreateFunc;
}

void CcdCollisionDispatcher::RecordEvent(bool create, btPersistentManifold *manifold)
{
	/* Caller holds m_lock. */
	ManifoldEvent ev;
	ev.pairIndex = tl_pairIndex;
	ev.seq = tl_seq++;
	ev.create = create;
	ev.manifold = manifold;
	m_events.push_back(ev);
}

btPersistentManifold *CcdCollisionDispatcher::getNewManifold(const btCollisionObject *body0, const btCollisionObject *body1)
{
	if (!m_recording) {
		return btCollisionDispatcher::getNewManifold(body0, body1);
	}

	/* Same as btCollisionDispatcher::getNewManifold() but the manifold is only added to
	 * m_manifoldsPtr later, in pair order, by ReplayEvents(). */
	const btScalar contactBreakingThreshold = (m_dispatcherFlags & btCollisionDispatcher::CD_USE_RELATIVE_CONTACT_BREAKING_THRESHOLD) ?
		btMin(body0->getCollisionShape()->getContactBreakingThreshold(gContactBreakingThreshold),
		      body1->getCollisionShape()->getContactBreakingThreshold(gContactBreakingThreshold)) :
		gContactBreakingThreshold;
	const btScalar contactProcessingThreshold = btMin(body0->getContactProcessingThreshold(), body1->getContactProcessingThreshold());

	void *mem = nullptr;
	{
		std::lock_guard<std::mutex> guard(m_lock);
		if (m_persistentManifoldPoolAllocator->getFreeCount()) {
			mem = m_persistentManifoldPoolAllocator->allocate(sizeof(btPersistentManifold));
		}
	}
	if (!mem) {
		if (m_dispatcherFlags & CD_DISABLE_CONTACTPOOL_DYNAMIC_ALLOCATION) {
			btAssert(0);
			return nullptr;
		}
		mem = btAlignedAlloc(sizeof(btPersistentManifold), 16);
	}

	btPersistentManifold *manifold = new(mem) btPersistentManifold(body0, body1, 0, contactBreakingThreshold, contactProcessingThreshold);
	manifold->m_index1a = -1;

	std::lock_guard<std::mutex> guard(m_lock);
	gNumManifold++;
	RecordEvent(true, manifold);
	return manifold;
}

void CcdCollisionDispatcher::releaseManifold(btPersistentManifold *manifold)
{
	if (!m_recording) {
		btCollisionDispatcher::releaseManifold(manifold);
		return;
	}
	/* Deferred to ReplayEvents(), nothing uses the manifold after its release. */
	std::lock_guard<std::mutex> guard(m_lock);
	RecordEvent(false, manifold);
}

void *CcdCollisionDispatcher::allocateCollisionAlgorithm(int size)
{
	if (m_recording) {
		if (size <= m_collisionAlgorithmPoolAllocator->getElementSize()) {
			std::lock_guard<std::mutex> guard(m_lock);
			if (m_collisionAlgorithmPoolAllocator->getFreeCount()) {
				return m_collisionAlgorithmPoolAllocator->allocate(size);
			}
		}
		return btAlignedAlloc(static_cast<size_t>(size), 16);
	}
	if (size > m_collisionAlgorithmPoolAllocator->getElementSize()) {
		return btAlignedAlloc(static_cast<size_t>(size), 16);
	}
	return btCollisionDispatcher::allocateCollisionAlgorithm(size);
}

void CcdCollisionDispatcher::freeCollisionAlgorithm(void *ptr)
{
	if (m_collisionAlgorithmPoolAllocator->validPtr(ptr)) {
		if (m_recording) {
			std::lock_guard<std::mutex> guard(m_lock);
			m_collisionAlgorithmPoolAllocator->freeMemory(ptr);
		}
		else {
			m_collisionAlgorithmPoolAllocator->freeMemory(ptr);
		}
	}
	else {
		btAlignedFree(ptr);
	}
}

static bool ccd_shape_parallel_safe(const btCollisionObject *obj)
{
	const int type = obj->getCollisionShape()->getShapeType();
	/* Soft bodies and GImpact keep extra shared state, keep them on the serial path. */
	return (type != SOFTBODY_SHAPE_PROXYTYPE && type != GIMPACT_SHAPE_PROXYTYPE &&
	        type != CONVEX_2D_SHAPE_PROXYTYPE);
}

bool CcdCollisionDispatcher::CanRunParallel(btOverlappingPairCache *pairCache, const btDispatcherInfo& dispatchInfo) const
{
	if (!m_parallelEnabled || !m_convexConvexCreateFunc) {
		return false;
	}
	if (dispatchInfo.m_dispatchFunc != btDispatcherInfo::DISPATCH_DISCRETE) {
		return false;
	}
	if (const_cast<CcdCollisionDispatcher *>(this)->getNearCallback() != defaultNearCallback) {
		return false;
	}
	const int numPairs = pairCache->getNumOverlappingPairs();
	if (numPairs < CCD_DISPATCH_MIN_PAIRS) {
		return false;
	}
	const btBroadphasePair *pairs = pairCache->getOverlappingPairArrayPtr();
	for (int i = 0; i < numPairs; ++i) {
		const btCollisionObject *obj0 = (const btCollisionObject *)pairs[i].m_pProxy0->m_clientObject;
		const btCollisionObject *obj1 = (const btCollisionObject *)pairs[i].m_pProxy1->m_clientObject;
		if (!ccd_shape_parallel_safe(obj0) || !ccd_shape_parallel_safe(obj1)) {
			return false;
		}
	}
	return true;
}

void CcdCollisionDispatcher::ProcessJob(int index)
{
	PairJob& job = m_jobs[index];
	btBroadphasePair& pair = *job.pair;
	btCollisionObject *colObj0 = (btCollisionObject *)pair.m_pProxy0->m_clientObject;
	btCollisionObject *colObj1 = (btCollisionObject *)pair.m_pProxy1->m_clientObject;

	tl_pairIndex = index;
	tl_seq = job.seq;

	btCollisionObjectWrapper obj0Wrap(0, colObj0->getCollisionShape(), colObj0, colObj0->getWorldTransform(), -1, -1);
	btCollisionObjectWrapper obj1Wrap(0, colObj1->getCollisionShape(), colObj1, colObj1->getWorldTransform(), -1, -1);
	btManifoldResult contactPointResult(&obj0Wrap, &obj1Wrap);
	pair.m_algorithm->processCollision(&obj0Wrap, &obj1Wrap, *m_dispatchInfo, &contactPointResult);

	tl_pairIndex = -1;
}

#ifndef __EMSCRIPTEN__
static void ccd_dispatch_job_cb(void *__restrict userdata, const int iter, const ParallelRangeTLS *__restrict UNUSED_tls)
{
	(void)UNUSED_tls;
	static_cast<CcdCollisionDispatcher *>(userdata)->ProcessJob(iter);
}
#endif

void CcdCollisionDispatcher::ReplayEvents()
{
	if (m_events.empty()) {
		return;
	}
	/* (pair, seq) is unique, so the sort order is total and matches the serial dispatcher. */
	std::sort(m_events.begin(), m_events.end(), [](const ManifoldEvent& a, const ManifoldEvent& b) {
		return (a.pairIndex != b.pairIndex) ? (a.pairIndex < b.pairIndex) : (a.seq < b.seq);
	});
	for (const ManifoldEvent& ev : m_events) {
		if (ev.create) {
			ev.manifold->m_index1a = m_manifoldsPtr.size();
			m_manifoldsPtr.push_back(ev.manifold);
		}
		else {
			btCollisionDispatcher::releaseManifold(ev.manifold);
		}
	}
	m_events.clear();
}

void CcdCollisionDispatcher::dispatchAllCollisionPairs(btOverlappingPairCache *pairCache, const btDispatcherInfo& dispatchInfo,
                                                       btDispatcher *dispatcher)
{
#ifdef __EMSCRIPTEN__
	btCollisionDispatcher::dispatchAllCollisionPairs(pairCache, dispatchInfo, dispatcher);
#else
	if (!CanRunParallel(pairCache, dispatchInfo)) {
		btCollisionDispatcher::dispatchAllCollisionPairs(pairCache, dispatchInfo, dispatcher);
		return;
	}

	const int numPairs = pairCache->getNumOverlappingPairs();
	btBroadphasePair *pairs = pairCache->getOverlappingPairArrayPtr();

	m_recording = true;
	m_dispatchInfo = &dispatchInfo;
	m_jobs.clear();
	m_events.clear();

	/* Serial prepass: filtering and creation of missing algorithms (their constructors
	 * may create manifolds, recorded with the pair index like the parallel phase). */
	for (int i = 0; i < numPairs; ++i) {
		btBroadphasePair& pair = pairs[i];
		btCollisionObject *colObj0 = (btCollisionObject *)pair.m_pProxy0->m_clientObject;
		btCollisionObject *colObj1 = (btCollisionObject *)pair.m_pProxy1->m_clientObject;
		if (!needsCollision(colObj0, colObj1)) {
			continue;
		}

		const int jobIndex = (int)m_jobs.size();
		tl_pairIndex = jobIndex;
		tl_seq = 0;
		if (!pair.m_algorithm) {
			btCollisionObjectWrapper obj0Wrap(0, colObj0->getCollisionShape(), colObj0, colObj0->getWorldTransform(), -1, -1);
			btCollisionObjectWrapper obj1Wrap(0, colObj1->getCollisionShape(), colObj1, colObj1->getWorldTransform(), -1, -1);
			pair.m_algorithm = findAlgorithm(&obj0Wrap, &obj1Wrap);
		}
		if (pair.m_algorithm) {
			PairJob job;
			job.pair = &pair;
			job.seq = tl_seq;
			m_jobs.push_back(job);
		}
		else if (tl_seq > 0) {
			/* Keep the events of this pair (unlikely) under a distinct index. */
			PairJob job;
			job.pair = nullptr;
			job.seq = tl_seq;
			m_jobs.push_back(job);
		}
	}
	tl_pairIndex = -1;

	/* Drop placeholder jobs without algorithm, keeping the pair indexes of the events
	 * consistent by processing only valid entries. */
	const int numJobs = (int)m_jobs.size();
	bool hasPlaceholder = false;
	for (const PairJob& job : m_jobs) {
		if (!job.pair) {
			hasPlaceholder = true;
			break;
		}
	}

	if (hasPlaceholder || numJobs < CCD_DISPATCH_MIN_PAIRS) {
		for (int i = 0; i < numJobs; ++i) {
			if (m_jobs[i].pair) {
				ProcessJob(i);
			}
		}
	}
	else {
		ParallelRangeSettings settings;
		BLI_parallel_range_settings_defaults(&settings);
		settings.scheduling_mode = TASK_SCHEDULING_DYNAMIC;
		settings.min_iter_per_thread = 1;
		BLI_task_parallel_range(0, numJobs, this, ccd_dispatch_job_cb, &settings);
	}

	m_recording = false;
	m_dispatchInfo = nullptr;
	ReplayEvents();
	m_jobs.clear();
#endif
}
