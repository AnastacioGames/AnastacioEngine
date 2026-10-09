/** \file gameengine/Physics/Bullet/CcdPhysicsController.cpp
 *  \ingroup physbullet
 */
/*
   Bullet Continuous Collision Detection and Physics Library
   Copyright (c) 2003-2006 Erwin Coumans  http://continuousphysics.com/Bullet/

   This software is provided 'as-is', without any express or implied warranty.
   In no event will the authors be held liable for any damages arising from the use of this software.
   Permission is granted to anyone to use this software for any purpose,
   including commercial applications, and to alter it and redistribute it freely,
   subject to the following restrictions:

   1. The origin of this software must not be misrepresented; you must not claim that you wrote the original software. If you use this software in a product, an acknowledgment in the product documentation would be appreciated but is not required.
   2. Altered source versions must be plainly marked as such, and must not be misrepresented as being the original software.
   3. This notice may not be removed or altered from any source distribution.
 */

#ifndef WIN32
#include <stdint.h>
#endif

#include "CM_Message.h"
#include "CM_List.h"

#include "CcdPhysicsController.h"
#include "btBulletDynamicsCommon.h"
#include "BulletCollision/CollisionDispatch/btGhostObject.h"
#include "BulletCollision/CollisionShapes/btScaledBvhTriangleMeshShape.h"
#include "BulletCollision/CollisionShapes/btTriangleIndexVertexArray.h"

#include "PHY_IMotionState.h"
#include "CcdPhysicsEnvironment.h"

#include "RAS_Deformer.h"
#include "RAS_IMaterial.h"
#include "RAS_MaterialBucket.h"

#include "KX_GameObject.h"
#include "KX_Mesh.h"

#include "BulletSoftBody/btSoftBody.h"
#include "BulletSoftBody/btSoftBodyInternals.h"
#include "BulletSoftBody/btSoftBodyHelpers.h"
#include "LinearMath/btConvexHull.h"
#include "LinearMath/btConvexHullComputer.h"

#include "CcdCookedData.h"
#include "BulletCollision/Gimpact/btGImpactShape.h"

#include "BulletSoftBody/btSoftRigidDynamicsWorld.h"

#include "BLI_utildefines.h"

#include <algorithm>
#include <atomic>
#include <cstring>
#include <mutex>
#include <map>
#include <thread>
#include <tuple>

/** Building the BVH of a triangle mesh shape is most of the physics load time (~1.2 ms for a 2k triangle
 * sphere), and every object built its own, even linked duplicates. Shapes whose vertex and triangle arrays
 * are identical (linked duplicates, Shift+D copies) now share one btOptimizedBvh: it only stores triangle
 * indices and quantized bounds, never a pointer to the mesh, so it is valid for any identical array. Each
 * object keeps its own shape and arrays, so replacing one object's physics mesh never touches the others.
 * The BVH is freed with the last shape using it; the mutex covers asynchronous LibLoad.
 * Inside CcdBeginBvhBatch()/CcdEndBvhBatch() (the converter's physics pass) the hash and the build of
 * each distinct mesh wait for the end of the pass and run on all cores. */
namespace {

struct SharedBvhKey
{
	uint64_t hash[2];
	int numVerts;
	int numTris;

	bool operator<(const SharedBvhKey& other) const
	{
		return std::tie(hash[0], hash[1], numVerts, numTris) <
		       std::tie(other.hash[0], other.hash[1], other.numVerts, other.numTris);
	}
};

struct SharedBvhEntry
{
	btOptimizedBvh *bvh;
	int users;
};

std::mutex sharedBvhMutex;
std::map<SharedBvhKey, SharedBvhEntry> sharedBvhs;

/// Two independent 64 bit hashes (FNV-1a and a multiply-xorshift) over 8 byte words, so a false match is
/// out of reach.
void shared_bvh_hash(uint64_t hash[2], const void *data, size_t size)
{
	const unsigned char *bytes = (const unsigned char *)data;
	auto mix = [hash](uint64_t word) {
		hash[0] = (hash[0] ^ word) * 1099511628211ULL;
		hash[1] = (hash[1] + word + 1) * 0x9E3779B97F4A7C15ULL;
		hash[1] ^= hash[1] >> 29;
	};
	size_t i = 0;
	for (; i + 8 <= size; i += 8) {
		uint64_t word;
		memcpy(&word, bytes + i, 8);
		mix(word);
	}
	for (; i < size; ++i) {
		mix(bytes[i]);
	}
}

/// Key of the vertex and triangle arrays (contiguous, see CreateBulletShape()).
SharedBvhKey shared_bvh_key(btStridingMeshInterface *meshInterface)
{
	const unsigned char *verts;
	const unsigned char *indices;
	int numVerts, vertStride, numFaces, indexStride;
	PHY_ScalarType vertType, indexType;
	meshInterface->getLockedReadOnlyVertexIndexBase(&verts, numVerts, vertType, vertStride, &indices, indexStride,
	                                                numFaces, indexType, 0);
	SharedBvhKey key = {{14695981039346656037ULL, 0x2545F4914F6CDD1DULL}, numVerts, numFaces};
	shared_bvh_hash(key.hash, verts, (size_t)numVerts * vertStride);
	shared_bvh_hash(key.hash, indices, (size_t)numFaces * indexStride);
	meshInterface->unLockReadOnlyVertexBase(0);
	return key;
}

/// Header of a cooked BVH (.cooked file): the full key, checked before the BVH is used.
struct CookedBvhHeader
{
	uint64_t hash[2];
	int32_t numVerts;
	int32_t numTris;
	uint32_t version;
	uint32_t size;
};

uint64_t cooked_bvh_key(const SharedBvhKey& key)
{
	return key.hash[0] ^ (key.hash[1] * 0x9E3779B97F4A7C15ULL) ^ ((uint64_t)key.numVerts << 32) ^ (uint64_t)key.numTris;
}

/// BVH of key from the .cooked file, nullptr when not cooked. Loading is a copy (deSerializeInPlace).
btOptimizedBvh *load_cooked_bvh(const SharedBvhKey& key)
{
	const std::vector<char> *data = CcdCookedData::FindBvh(cooked_bvh_key(key));
	CookedBvhHeader head;
	if (!data || data->size() <= sizeof(head)) {
		return nullptr;
	}
	memcpy(&head, data->data(), sizeof(head));
	if (head.hash[0] != key.hash[0] || head.hash[1] != key.hash[1] || head.numVerts != key.numVerts ||
	    head.numTris != key.numTris || head.version != 1 || head.size != data->size() - sizeof(head))
	{
		return nullptr;
	}
	// The BVH lives at the start of its buffer: FreeBvh() releases both.
	void *mem = btAlignedAlloc(head.size, 16);
	memcpy(mem, data->data() + sizeof(head), head.size);
	btOptimizedBvh *bvh = btOptimizedBvh::deSerializeInPlace(mem, head.size, false);
	if (!bvh) {
		btAlignedFree(mem);
	}
	return bvh;
}

void save_cooked_bvh(const SharedBvhKey& key, const btOptimizedBvh *bvh)
{
	if (!CcdCookedData::IsRecording()) {
		return;
	}
	CookedBvhHeader head = {{key.hash[0], key.hash[1]}, key.numVerts, key.numTris, 1, bvh->calculateSerializeBufferSize()};
	void *mem = btAlignedAlloc(head.size, 16);
	if (bvh->serializeInPlace(mem, head.size, false)) {
		std::vector<char> data(sizeof(head) + head.size);
		memcpy(data.data(), &head, sizeof(head));
		memcpy(data.data() + sizeof(head), mem, head.size);
		CcdCookedData::AddBvh(cooked_bvh_key(key), data);
	}
	btAlignedFree(mem);
}

/// Runs func(0) .. func(count - 1) on all cores, returning when all are done.
template <class Func>
void shared_bvh_parallel(size_t count, const Func& func)
{
	const size_t numThreads = std::min<size_t>(count, std::max(1u, std::thread::hardware_concurrency()));
	std::atomic<size_t> next(0);
	auto work = [&]() {
		for (size_t i = next++; i < count; i = next++) {
			func(i);
		}
	};
	std::vector<std::thread> threads;
	for (size_t t = 1; t < numThreads; ++t) {
		threads.emplace_back(work);
	}
	work();
	for (std::thread& thread : threads) {
		thread.join();
	}
}

class CcdSharedBvhTriangleMeshShape;

/// Shapes created on this thread inside CcdBeginBvhBatch()/CcdEndBvhBatch(), waiting for their BVH.
struct PendingBvhBatch
{
	int depth = 0;
	std::vector<CcdSharedBvhTriangleMeshShape *> shapes;
};
thread_local PendingBvhBatch pendingBvhBatch;

class CcdSharedBvhTriangleMeshShape : public btBvhTriangleMeshShape
{
private:
	SharedBvhKey m_key;
	bool m_attached = false;

public:
	CcdSharedBvhTriangleMeshShape(btStridingMeshInterface *meshInterface)
		:btBvhTriangleMeshShape(meshInterface, true, false)
	{
		// In a batch the BVH waits for CcdEndBvhBatch(): adding the body to the world only reads the
		// local bounds computed by the base constructor.
		if (pendingBvhBatch.depth > 0) {
			pendingBvhBatch.shapes.push_back(this);
		}
		else {
			Attach(shared_bvh_key(m_meshInterface), nullptr);
		}
	}

	virtual ~CcdSharedBvhTriangleMeshShape()
	{
		if (!m_attached) {
			// Freed before the end of its batch (e.g. an object dropped by the converter).
			CM_ListRemoveIfFound(pendingBvhBatch.shapes, this);
			return;
		}
		std::lock_guard<std::mutex> lock(sharedBvhMutex);
		std::map<SharedBvhKey, SharedBvhEntry>::iterator it = sharedBvhs.find(m_key);
		if (it != sharedBvhs.end() && --it->second.users == 0) {
			FreeBvh(it->second.bvh);
			sharedBvhs.erase(it);
		}
	}

	static void FreeBvh(btOptimizedBvh *bvh)
	{
		bvh->~btOptimizedBvh();
		btAlignedFree(bvh);
	}

	/// The cooked BVH of key, else the same build as btBvhTriangleMeshShape::buildOptimizedBvh() (recorded
	/// when playing a .blend). Owned by the cache.
	btOptimizedBvh *BuildBvh(const SharedBvhKey& key)
	{
		if (btOptimizedBvh *cooked = load_cooked_bvh(key)) {
			return cooked;
		}
		btOptimizedBvh *bvh = BuildBvh();
		save_cooked_bvh(key, bvh);
		return bvh;
	}

	btOptimizedBvh *BuildBvh()
	{
		void *mem = btAlignedAlloc(sizeof(btOptimizedBvh), 16);
		btOptimizedBvh *bvh = new (mem) btOptimizedBvh();
		bvh->build(m_meshInterface, true, m_localAabbMin, m_localAabbMax);
		return bvh;
	}

	/// Uses the cached BVH of key, else 'built' (handed to the cache), else builds it now.
	void Attach(const SharedBvhKey& key, btOptimizedBvh *built)
	{
		std::unique_lock<std::mutex> lock(sharedBvhMutex);
		SharedBvhEntry& entry = sharedBvhs[key];
		if (!entry.bvh) {
			entry.bvh = built ? built : BuildBvh(key);
			entry.users = 0;
			built = nullptr;
		}
		++entry.users;
		m_key = key;
		m_attached = true;
		setOptimizedBvh(entry.bvh, btVector3(1.0f, 1.0f, 1.0f));
		lock.unlock();
		// Another thread (asynchronous LibLoad) cached the same mesh meanwhile.
		if (built) {
			FreeBvh(built);
		}
	}
};

} // namespace

void CcdBeginBvhBatch()
{
	++pendingBvhBatch.depth;
}

void CcdEndBvhBatch()
{
	BLI_assert(pendingBvhBatch.depth > 0);
	if (--pendingBvhBatch.depth > 0) {
		return;
	}
	std::vector<CcdSharedBvhTriangleMeshShape *> shapes;
	shapes.swap(pendingBvhBatch.shapes);

	std::vector<SharedBvhKey> keys(shapes.size());
	shared_bvh_parallel(shapes.size(), [&](size_t i) {
		keys[i] = shared_bvh_key(shapes[i]->getMeshInterface());
	});

	// One build per distinct mesh not cached yet, done for its first shape.
	std::vector<size_t> builders;
	{
		std::lock_guard<std::mutex> lock(sharedBvhMutex);
		std::map<SharedBvhKey, size_t> first;
		for (size_t i = 0; i < shapes.size(); ++i) {
			if (sharedBvhs.find(keys[i]) == sharedBvhs.end() && first.emplace(keys[i], i).second) {
				builders.push_back(i);
			}
		}
	}
	std::vector<btOptimizedBvh *> built(shapes.size(), nullptr);
	shared_bvh_parallel(builders.size(), [&](size_t j) {
		built[builders[j]] = shapes[builders[j]]->BuildBvh(keys[builders[j]]);
	});

	// In order: the first shape of a mesh caches its BVH, the copies after it find it there.
	for (size_t i = 0; i < shapes.size(); ++i) {
		shapes[i]->Attach(keys[i], built[i]);
	}
}

/// todo: fill all the empty CcdPhysicsController methods, hook them up to the btRigidBody class

//'temporarily' global variables
extern float gDeactivationTime;
extern bool gDisableDeactivation;

float gLinearSleepingTreshold;
float gAngularSleepingTreshold;

CcdCharacter::CcdCharacter(CcdPhysicsController *ctrl, btMotionState *motionState,
                           btPairCachingGhostObject *ghost, btConvexShape *shape, float stepHeight)
	:btKinematicCharacterController(ghost, shape, stepHeight),
	m_ctrl(ctrl),
	m_motionState(motionState),
	m_jumps(0),
	m_maxJumps(1)
{
}

void CcdCharacter::updateAction(btCollisionWorld *collisionWorld, btScalar dt)
{
	if (onGround()) {
		m_jumps = 0;
	}

	btKinematicCharacterController::updateAction(collisionWorld, dt);
	m_motionState->setWorldTransform(getGhostObject()->getWorldTransform());
}

unsigned char CcdCharacter::getMaxJumps() const
{
	return m_maxJumps;
}

void CcdCharacter::setMaxJumps(unsigned char maxJumps)
{
	m_maxJumps = maxJumps;
}

unsigned char CcdCharacter::getJumpCount() const
{
	return m_jumps;
}

bool CcdCharacter::canJump() const
{
	return (onGround() && m_maxJumps > 0) || m_jumps < m_maxJumps;
}

void CcdCharacter::jump()
{
	if (!canJump()) {
		return;
	}

	m_verticalVelocity = m_jumpSpeed;
	m_wasJumping = true;
	m_jumps++;
}

const btVector3& CcdCharacter::getWalkDirection()
{
	return m_walkDirection;
}

const btVector3& CcdCharacter::getJumpDirection()
{
	return m_jumpAxis;
}

const float CcdCharacter::getSmoothMovement()
{
	return m_smoothMovement;
}

float CcdCharacter::GetFallSpeed() const
{
	return m_fallSpeed;
}

void CcdCharacter::SetFallSpeed(float fallSpeed)
{
	setFallSpeed(fallSpeed);
}

float CcdCharacter::GetMaxSlope() const
{
	return m_maxSlopeRadians;
}

void CcdCharacter::SetMaxSlope(float maxSlope)
{
	setMaxSlope(maxSlope);
}

float CcdCharacter::GetJumpSpeed() const
{
	return m_jumpSpeed;
}

void CcdCharacter::SetJumpSpeed(float jumpSpeed)
{
	setJumpSpeed(jumpSpeed);
}

void CcdCharacter::SetVelocity(const btVector3& vel, float time, bool local)
{
	btVector3 v = vel;
	if (local) {
		const btTransform xform = getGhostObject()->getWorldTransform();
		v = xform.getBasis() * v;
	}

	// Avoid changing velocity and keeping previous time interval.
	m_velocityTimeInterval = 0.0f;

	setVelocityForTimeInterval(v, time);
}

void CcdCharacter::ReplaceShape(btConvexShape* shape)
{
	m_convexShape = shape;
	m_ghostObject->setCollisionShape(m_convexShape);
}

void CcdCharacter::SetVelocity(const mt::vec3& vel, float time, bool local)
{
	SetVelocity(ToBullet(vel), time, local);
}

void CcdCharacter::Reset()
{
	btCollisionWorld *world = m_ctrl->GetPhysicsEnvironment()->GetDynamicsWorld();
	reset(world);
}

bool CleanPairCallback::processOverlap(btBroadphasePair &pair)
{
	if ((pair.m_pProxy0 == m_cleanProxy) || (pair.m_pProxy1 == m_cleanProxy)) {
		m_pairCache->cleanOverlappingPair(pair, m_dispatcher);
		CcdPhysicsController *ctrl0 = (CcdPhysicsController *)(((btCollisionObject *)pair.m_pProxy0->m_clientObject)->getUserPointer());
		CcdPhysicsController *ctrl1 = (CcdPhysicsController *)(((btCollisionObject *)pair.m_pProxy1->m_clientObject)->getUserPointer());
		ctrl0->GetCollisionObject()->activate(false);
		ctrl1->GetCollisionObject()->activate(false);
	}
	return false;
}

CcdPhysicsController::CcdPhysicsController(const CcdConstructionInfo& ci)
	:m_cci(ci)
{
	m_newClientInfo = 0;
	m_registerCount = 0;
	m_softbodyStartTrans.setIdentity();
	m_parentRoot = nullptr;
	// copy pointers locally to allow smart release
	m_MotionState = ci.m_MotionState;
	m_collisionShape = ci.m_collisionShape;
	// apply scaling before creating rigid body
	m_collisionShape->setLocalScaling(m_cci.m_scaling);
	if (m_cci.m_mass) {
		m_collisionShape->calculateLocalInertia(m_cci.m_mass, m_cci.m_localInertiaTensor);
	}
	// shape info is shared, increment ref count
	m_shapeInfo = ci.m_shapeInfo;
	if (m_shapeInfo) {
		m_shapeInfo->AddRef();
	}

	m_bulletChildShape = nullptr;
	m_compoundParent = nullptr;

	m_bulletMotionState = 0;
	m_characterController = 0;
	m_savedCollisionFlags = 0;
	m_savedCollisionFilterGroup = 0;
	m_savedCollisionFilterMask = 0;
	m_savedMass = 0.0f;
	m_savedFriction = 0.0f;
	m_savedDyna = false;
	m_suspended = false;

	CreateRigidbody();
}

void CcdPhysicsController::addCcdConstraintRef(btTypedConstraint *c)
{
	int index = m_ccdConstraintRefs.findLinearSearch(c);
	if (index == m_ccdConstraintRefs.size()) {
		m_ccdConstraintRefs.push_back(c);
	}
}

void CcdPhysicsController::removeCcdConstraintRef(btTypedConstraint *c)
{
	m_ccdConstraintRefs.remove(c);
}

btTypedConstraint *CcdPhysicsController::getCcdConstraintRef(int index)
{
	return m_ccdConstraintRefs[index];
}

int CcdPhysicsController::getNumCcdConstraintRefs() const
{
	return m_ccdConstraintRefs.size();
}

btTransform CcdPhysicsController::GetTransformFromMotionState(PHY_IMotionState *motionState)
{
	const mt::vec3 pos = motionState->GetWorldPosition();
	const mt::mat3 mat = motionState->GetWorldOrientation();

	return btTransform(ToBullet(mat), ToBullet(pos));
}

class BlenderBulletMotionState : public btMotionState
{
	PHY_IMotionState *m_blenderMotionState;
	// Local-space center of mass offset. When non-zero, the rigid body's
	// (COM) transform used by Bullet is shifted away from the node/graphics
	// transform by this amount, while the visible object stays exactly where
	// its node says it is. The chassis collision shape must be placed at the
	// opposite offset inside its compound shape so it still lines up with
	// the visible mesh in world space; see BL_BlenderDataConversion.cpp's
	// vehicle_com_offset handling.
	btVector3 m_comOffset;

public:
	BlenderBulletMotionState(PHY_IMotionState *bms)
		:m_blenderMotionState(bms),
		m_comOffset(0.0f, 0.0f, 0.0f)
	{
	}

	void SetComOffset(const btVector3& offset)
	{
		m_comOffset = offset;
	}

	const btVector3& GetComOffset() const
	{
		return m_comOffset;
	}

	void getWorldTransform(btTransform& worldTrans) const
	{
		const mt::vec3 pos = m_blenderMotionState->GetWorldPosition();
		const mt::mat3 mat = m_blenderMotionState->GetWorldOrientation();
		worldTrans.setBasis(ToBullet(mat));
		worldTrans.setOrigin(ToBullet(pos) + worldTrans.getBasis() * m_comOffset);
	}

	void setWorldTransform(const btTransform& worldTrans)
	{
		const btVector3 nodePos = worldTrans.getOrigin() - worldTrans.getBasis() * m_comOffset;
		m_blenderMotionState->SetWorldPosition(ToMt(nodePos));
		m_blenderMotionState->SetWorldOrientation(ToMt(worldTrans.getBasis()));
		m_blenderMotionState->CalculateWorldTransformations();
	}
};

void CcdPhysicsController::SetCenterOfMassOffset(const mt::vec3& localOffset)
{
	if (m_bulletMotionState) {
		static_cast<BlenderBulletMotionState *>(m_bulletMotionState)->SetComOffset(ToBullet(localOffset));
	}

	btRigidBody *body = GetRigidBody();
	if (body && !body->isStaticOrKinematicObject()) {
		btTransform xform;
		m_bulletMotionState->getWorldTransform(xform);
		body->setCenterOfMassTransform(xform);
	}
}

btRigidBody *CcdPhysicsController::GetRigidBody()
{
	return btRigidBody::upcast(m_object);
}
const btRigidBody *CcdPhysicsController::GetRigidBody() const
{
	return btRigidBody::upcast(m_object);
}

btCollisionObject *CcdPhysicsController::GetCollisionObject()
{
	return m_object;
}
btSoftBody *CcdPhysicsController::GetSoftBody()
{
	return btSoftBody::upcast(m_object);
}
btKinematicCharacterController *CcdPhysicsController::GetCharacterController()
{
	return m_characterController;
}

const std::vector<unsigned int>& CcdPhysicsController::GetSoftBodyIndices() const
{
	return m_softBodyIndices;
}

#include "BulletSoftBody/btSoftBodyHelpers.h"

bool CcdPhysicsController::CreateSoftbody()
{
	int shapeType = m_cci.m_collisionShape ? m_cci.m_collisionShape->getShapeType() : 0;

	//disable soft body until first sneak preview is ready
	if (!m_cci.m_bSoft || !m_cci.m_collisionShape ||
	    ((shapeType != CONVEX_HULL_SHAPE_PROXYTYPE) &&
	     (shapeType != TRIANGLE_MESH_SHAPE_PROXYTYPE) &&
	     (shapeType != SCALED_TRIANGLE_MESH_SHAPE_PROXYTYPE))) {
		return false;
	}

	btSoftBody *psb = nullptr;
	btSoftBodyWorldInfo& worldInfo = m_cci.m_physicsEnv->GetDynamicsWorld()->getWorldInfo();

	if (m_cci.m_collisionShape->getShapeType() == CONVEX_HULL_SHAPE_PROXYTYPE) {
		btConvexHullShape *convexHull = (btConvexHullShape *)m_cci.m_collisionShape;
		{
			int nvertices = convexHull->getNumPoints();
			const btVector3 *vertices = convexHull->getPoints();
			// getPoints() is unscaled: apply the object scale like the triangle mesh path does.
			const btVector3& localScaling = convexHull->getLocalScaling();
			btAlignedObjectArray<btVector3> scaledVertices;
			scaledVertices.resize(nvertices);
			for (int i = 0; i < nvertices; ++i) {
				scaledVertices[i] = vertices[i] * localScaling;
			}

			HullDesc hdsc(QF_TRIANGLES, nvertices, &scaledVertices[0]);
			HullResult hres;
			HullLibrary hlib;
			hdsc.mMaxVertices = nvertices;
			if (hlib.CreateConvexHull(hdsc, hres) != QE_OK) {
				return false;
			}

			psb = new btSoftBody(&worldInfo, (int)hres.mNumOutputVertices,
			                     &hres.m_OutputVertices[0], 0);
			for (int i = 0; i < (int)hres.mNumFaces; ++i) {
				const unsigned int idx[3] = {hres.m_Indices[i * 3 + 0],
					                         hres.m_Indices[i * 3 + 1],
					                         hres.m_Indices[i * 3 + 2]};
				if (idx[0] < idx[1]) {
					psb->appendLink(idx[0], idx[1]);
				}
				if (idx[1] < idx[2]) {
					psb->appendLink(idx[1], idx[2]);
				}
				if (idx[2] < idx[0]) {
					psb->appendLink(idx[2], idx[0]);
				}
				psb->appendFace(idx[0], idx[1], idx[2]);
			}
			hlib.ReleaseResult(hres);
		}
	}
	else {
		int numtris = 0;
		if (m_cci.m_collisionShape->getShapeType() == SCALED_TRIANGLE_MESH_SHAPE_PROXYTYPE) {
			btScaledBvhTriangleMeshShape *scaledtrimeshshape = (btScaledBvhTriangleMeshShape *)m_cci.m_collisionShape;
			btBvhTriangleMeshShape *trimeshshape = scaledtrimeshshape->getChildShape();

			///only deal with meshes that have 1 sub part/component, for now
			if (trimeshshape->getMeshInterface()->getNumSubParts() == 1) {
				unsigned char *vertexBase;
				btScalar *scaledVertexBase;
				btVector3 localScaling;
				PHY_ScalarType vertexType;
				int numverts;
				int vertexstride;
				unsigned char *indexbase;
				int indexstride;
				PHY_ScalarType indexType;
				trimeshshape->getMeshInterface()->getLockedVertexIndexBase(&vertexBase, numverts, vertexType, vertexstride, &indexbase, indexstride, numtris, indexType);
				localScaling = scaledtrimeshshape->getLocalScaling();
				scaledVertexBase = new btScalar[numverts * 3];
				for (int i = 0; i < numverts * 3; i += 3) {
					scaledVertexBase[i] = ((const btScalar *)vertexBase)[i] * localScaling.getX();
					scaledVertexBase[i + 1] = ((const btScalar *)vertexBase)[i + 1] * localScaling.getY();
					scaledVertexBase[i + 2] = ((const btScalar *)vertexBase)[i + 2] * localScaling.getZ();
				}
				psb = btSoftBodyHelpers::CreateFromTriMesh(worldInfo, scaledVertexBase, (const int *)indexbase, numtris, false);
				delete[] scaledVertexBase;
			}
		}
		else {
			btTriangleMeshShape *trimeshshape = (btTriangleMeshShape *)m_cci.m_collisionShape;
			///only deal with meshes that have 1 sub part/component, for now
			if (trimeshshape->getMeshInterface()->getNumSubParts() == 1) {
				unsigned char *vertexBase;
				PHY_ScalarType vertexType;
				int numverts;
				int vertexstride;
				unsigned char *indexbase;
				int indexstride;
				PHY_ScalarType indexType;
				trimeshshape->getMeshInterface()->getLockedVertexIndexBase(&vertexBase, numverts, vertexType, vertexstride, &indexbase, indexstride, numtris, indexType);

				psb = btSoftBodyHelpers::CreateFromTriMesh(worldInfo, (const btScalar *)vertexBase, (const int *)indexbase, numtris, false);
			}
		}
		if (!psb) {
			return false;
		}
		// store face tag so that we can find our original face when doing ray casting
		btSoftBody::Face *ft;
		int i;
		for (i = 0, ft = &psb->m_faces[0]; i < numtris; ++i, ++ft) {
			// Hack!! use m_tag to store the face number, normally it is a pointer
			// add 1 to make sure it is never 0
			ft->m_tag = (void *)((uintptr_t)(i + 1));
		}
	}
	if (m_cci.m_margin > 0.0f) {
		psb->getCollisionShape()->setMargin(m_cci.m_margin);
		psb->updateBounds();
	}
	m_object = psb;

	btSoftBody::Material *pm = psb->m_materials[0];
	pm->m_kLST = m_cci.m_soft_linStiff;
	pm->m_kAST = m_cci.m_soft_angStiff;
	pm->m_kVST = m_cci.m_soft_volume;
	psb->m_cfg.collisions = 0;

	if (m_cci.m_soft_collisionflags & CCD_BSB_COL_CL_RS) {
		psb->m_cfg.collisions += btSoftBody::fCollision::CL_RS;
	}
	else {
		psb->m_cfg.collisions += btSoftBody::fCollision::SDF_RS;
	}
	if (m_cci.m_soft_collisionflags & CCD_BSB_COL_CL_SS) {
		psb->m_cfg.collisions += btSoftBody::fCollision::CL_SS;
	}
	else {
		psb->m_cfg.collisions += btSoftBody::fCollision::VF_SS;
	}

	psb->m_cfg.kSRHR_CL = m_cci.m_soft_kSRHR_CL; // Soft vs rigid hardness [0,1] (cluster only)
	psb->m_cfg.kSKHR_CL = m_cci.m_soft_kSKHR_CL; // Soft vs kinetic hardness [0,1] (cluster only)
	psb->m_cfg.kSSHR_CL = m_cci.m_soft_kSSHR_CL; // Soft vs soft hardness [0,1] (cluster only)
	psb->m_cfg.kSR_SPLT_CL = m_cci.m_soft_kSR_SPLT_CL; // Soft vs rigid impulse split [0,1] (cluster only)

	psb->m_cfg.kSK_SPLT_CL = m_cci.m_soft_kSK_SPLT_CL; // Soft vs rigid impulse split [0,1] (cluster only)
	psb->m_cfg.kSS_SPLT_CL = m_cci.m_soft_kSS_SPLT_CL; // Soft vs rigid impulse split [0,1] (cluster only)
	psb->m_cfg.kVCF = m_cci.m_soft_kVCF; // Velocities correction factor (Baumgarte)
	psb->m_cfg.kDP = m_cci.m_soft_kDP; // Damping coefficient [0,1]

	psb->m_cfg.kDG = m_cci.m_soft_kDG; // Drag coefficient [0,+inf]
	psb->m_cfg.kLF = m_cci.m_soft_kLF; // Lift coefficient [0,+inf]
	psb->m_cfg.kPR = m_cci.m_soft_kPR; // Pressure coefficient [-inf,+inf]
	psb->m_cfg.kVC = m_cci.m_soft_kVC; // Volume conversation coefficient [0,+inf]

	psb->m_cfg.kDF = m_cci.m_soft_kDF; // Dynamic friction coefficient [0,1]
	psb->m_cfg.kMT = m_cci.m_soft_kMT; // Pose matching coefficient [0,1]
	psb->m_cfg.kCHR = m_cci.m_soft_kCHR; // Rigid contacts hardness [0,1]
	psb->m_cfg.kKHR = m_cci.m_soft_kKHR; // Kinetic contacts hardness [0,1]

	psb->m_cfg.kSHR = m_cci.m_soft_kSHR; // Soft contacts hardness [0,1]
	psb->m_cfg.kAHR = m_cci.m_soft_kAHR; // Anchors hardness [0,1]

	if (m_cci.m_gamesoftFlag & CCD_BSB_BENDING_CONSTRAINTS) {
		psb->generateBendingConstraints(m_cci.m_softBendingDistance, pm);
	}

	psb->m_cfg.piterations = m_cci.m_soft_piterations;
	psb->m_cfg.viterations = m_cci.m_soft_viterations;
	psb->m_cfg.diterations = m_cci.m_soft_diterations;
	psb->m_cfg.citerations = m_cci.m_soft_citerations;

	if (m_cci.m_gamesoftFlag & CCD_BSB_SHAPE_MATCHING) {
		psb->setPose(false, true);
	}
	else {
		psb->setPose(true, false);
	}

	psb->randomizeConstraints();
	psb->setTotalMass(m_cci.m_mass);

	if (m_cci.m_soft_collisionflags & (CCD_BSB_COL_CL_RS + CCD_BSB_COL_CL_SS)) {
		psb->generateClusters(m_cci.m_soft_numclusteriterations);
	}


	psb->setCollisionFlags(0);

	// The nodes were built from scaled vertices: compare them with scaled positions.
	const btVector3 localScaling = m_cci.m_collisionShape->getLocalScaling();
	const btSoftBody::tNodeArray& nodes = psb->m_nodes;
	const unsigned int numVertices = m_shapeInfo->m_vertexRemap.size();
	m_softBodyIndices.resize(numVertices);
	for (unsigned int i = 0; i < numVertices; ++i) {
		const unsigned int index = m_shapeInfo->m_vertexRemap[i];
		if (index == -1) {
			// Vertex without collision (material with physics disabled): no node, see KX_SoftBodyDeformer.
			m_softBodyIndices[i] = -1;
			continue;
		}
		const float *co = &m_shapeInfo->m_vertexArray[index * 3];
		const btVector3 pos = btVector3(co[0], co[1], co[2]) * localScaling;
		// Without welding the triangle mesh nodes keep the m_vertexArray order: use the index directly
		// and only search the closest node when it doesn't match (convex hull).
		if (index < (unsigned int)nodes.size() && (nodes[index].m_x - pos).length2() <= SIMD_EPSILON) {
			m_softBodyIndices[i] = index;
			continue;
		}
		const int node = Ccd_FindClosestNode(psb, pos);
		m_softBodyIndices[i] = (node >= 0) ? (unsigned int)node : -1;
	}

	// Nodes are in object space: move them to the object transform, which becomes the soft body frame.
	btTransform startTrans;
	m_bulletMotionState->getWorldTransform(startTrans);

	m_MotionState->SetWorldPosition(ToMt(startTrans.getOrigin()));
	m_MotionState->SetWorldOrientation(ToMt(startTrans.getBasis()));

	psb->transform(startTrans);
	m_softbodyStartTrans = startTrans;

	m_object->setCollisionFlags(m_object->getCollisionFlags() | m_cci.m_collisionFlags);
	if (m_cci.m_do_anisotropic) {
		m_object->setAnisotropicFriction(m_cci.m_anisotropicFriction);
	}
	return true;
}

bool CcdPhysicsController::CreateCharacterController()
{
	if (!m_cci.m_bCharacter) {
		return false;
	}

	m_object = new btPairCachingGhostObject();
	m_object->setCollisionShape(m_collisionShape);
	m_object->setCollisionFlags(btCollisionObject::CF_CHARACTER_OBJECT);

	btTransform trans;
	m_bulletMotionState->getWorldTransform(trans);
	m_object->setWorldTransform(trans);

	m_characterController = new CcdCharacter(this, m_bulletMotionState, (btPairCachingGhostObject *)m_object,
	                                         (btConvexShape *)m_collisionShape, m_cci.m_stepHeight);

	m_characterController->setJumpSpeed(m_cci.m_jumpSpeed);
	m_characterController->setFallSpeed(m_cci.m_fallSpeed);
	m_characterController->setMaxJumps(m_cci.m_maxJumps);
	m_characterController->setMaxSlope(m_cci.m_maxSlope);
	m_characterController->setSmoothMovement(m_cci.m_smoothMovement);
	m_characterController->setJumpDirection(m_cci.m_jumpAxis);

	return true;
}

void CcdPhysicsController::CreateRigidbody()
{
	//btTransform trans = GetTransformFromMotionState(m_MotionState);
	m_bulletMotionState = new BlenderBulletMotionState(m_MotionState);

	///either create a btCollisionObject, btRigidBody or btSoftBody
	if (CreateSoftbody() || CreateCharacterController()) {
		// soft body created, done
		return;
	}

	//create a rgid collision object
	btRigidBody::btRigidBodyConstructionInfo rbci(m_cci.m_mass, m_bulletMotionState, m_collisionShape, m_cci.m_localInertiaTensor *m_cci.m_inertiaFactor);
	rbci.m_linearDamping = m_cci.m_linearDamping;
	rbci.m_angularDamping = m_cci.m_angularDamping;
	rbci.m_friction = m_cci.m_friction;
	rbci.m_rollingFriction = m_cci.m_rollingFriction;
	rbci.m_restitution = m_cci.m_restitution;
	m_object = new btRigidBody(rbci);

	//
	// init the rigidbody properly
	//

	//setMassProps this also sets collisionFlags
	//convert collision flags!
	//special case: a near/radar sensor controller should not be defined static or it will
	//generate loads of static-static collision messages on the console
	if (m_cci.m_bSensor) {
		// reset the flags that have been set so far
		m_object->setCollisionFlags(0);
		// sensor must never go to sleep: they need to detect continously
		m_object->setActivationState(DISABLE_DEACTIVATION);
	}
	m_object->setCollisionFlags(m_object->getCollisionFlags() | m_cci.m_collisionFlags);
	btRigidBody *body = GetRigidBody();

	if (body) {
		body->setGravity(m_cci.m_gravity);
		body->setDamping(m_cci.m_linearDamping, m_cci.m_angularDamping);

		if (!m_cci.m_bRigid) {
			body->setAngularFactor(0.0f);
		}
		// use bullet's default contact processing theshold, blender's old default of 1 is too small here.
		// if there's really a need to change this, it should be exposed in the ui first.
//		body->setContactProcessingThreshold(m_cci.m_contactProcessingThreshold);
		body->setSleepingThresholds(gLinearSleepingTreshold, gAngularSleepingTreshold);

	}
	if (m_object && m_cci.m_do_anisotropic) {
		m_object->setAnisotropicFriction(m_cci.m_anisotropicFriction);
	}
}

mt::vec3 CcdPhysicsController::GetGravity()
{
	btRigidBody *body = GetRigidBody();
	if (body) {
		return ToMt(body->getGravity());
	}
	return mt::zero3;
}

void CcdPhysicsController::SetGravity(const mt::vec3 &gravity)
{
	btRigidBody *body = GetRigidBody();
	if (body) {
		body->setGravity(ToBullet(gravity));
	}
}

static void DeleteBulletShape(btCollisionShape *shape, bool free)
{
	if (shape->getShapeType() == SCALED_TRIANGLE_MESH_SHAPE_PROXYTYPE) {
		/* If we use Bullet scaled shape (btScaledBvhTriangleMeshShape) we have to
		 * free the child of the unscaled shape (btTriangleMeshShape) here.
		 */
		btTriangleMeshShape *meshShape = ((btScaledBvhTriangleMeshShape *)shape)->getChildShape();
		if (meshShape) {
			delete meshShape;
		}
	}
	if (free) {
		delete shape;
	}
}

bool CcdPhysicsController::DeleteControllerShape()
{
	if (m_collisionShape) {
		// collision shape is always unique to the controller, can delete it here
		if (m_collisionShape->isCompound()) {
			// bullet does not delete the child shape, must do it here
			btCompoundShape *compoundShape = (btCompoundShape *)m_collisionShape;
			int numChild = compoundShape->getNumChildShapes();
			for (int i = numChild - 1; i >= 0; i--) {
				btCollisionShape *childShape = compoundShape->getChildShape(i);
				DeleteBulletShape(childShape, true);
			}
		}
		DeleteBulletShape(m_collisionShape, true);

		return true;
	}

	return false;
}

bool CcdPhysicsController::ReplaceControllerShape(btCollisionShape *newShape)
{
	if (m_collisionShape) {
		DeleteControllerShape();
	}

	// If newShape is nullptr it means to create a new Bullet shape.
	if (!newShape) {
		newShape = m_shapeInfo->CreateBulletShape(m_cci.m_margin, m_cci.m_bGimpact, !m_cci.m_bSoft);
	}

	m_object->setCollisionShape(newShape);
	m_collisionShape = newShape;
	m_cci.m_collisionShape = newShape;

	btSoftBody *softBody = GetSoftBody();
	if (softBody) {
		// The new Bullet shape has no scaling, the soft body is built from the scaled vertices.
		newShape->setLocalScaling(m_cci.m_scaling);

		// Soft body must be recreated: build the new one first so the old one stays valid on failure.
		if (!CreateSoftbody()) {
			CM_Warning("soft body can't be rebuilt from the new shape (needs a triangle mesh or convex hull), keeping the old one");
			return true;
		}

		btSoftRigidDynamicsWorld *world = m_cci.m_physicsEnv->GetDynamicsWorld();
		const bool inWorld = !IsPhysicsSuspended();
		if (inWorld) {
			world->removeSoftBody(softBody);
		}
		delete softBody;

		btSoftBody *newSoftBody = GetSoftBody();
		newSoftBody->setUserPointer(this);
		if (inWorld) {
			world->addSoftBody(newSoftBody, GetCollisionFilterGroup(), GetCollisionFilterMask());
		}
	}

	if (m_characterController) {
		m_characterController->ReplaceShape(static_cast<btConvexShape *>(newShape));
	}

	return true;
}

CcdPhysicsController::~CcdPhysicsController()
{
	// Detach from the compound parent if the object is being destroyed while still dynamically
	// parented (RemoveCompoundChild() was never called explicitly, e.g. via RemoveParent()) --
	// otherwise our shape stays a "ghost" inside the parent's compound shape after we're gone.
	if (m_compoundParent) {
		m_compoundParent->RemoveCompoundChild(this);
	}

	//will be reference counted, due to sharing
	if (m_cci.m_physicsEnv) {
		m_cci.m_physicsEnv->RemoveCcdPhysicsController(this, true);
	}

	if (m_MotionState) {
		delete m_MotionState;
	}
	if (m_bulletMotionState) {
		delete m_bulletMotionState;
	}
	if (m_characterController) {
		delete m_characterController;
	}
	delete m_object;

	DeleteControllerShape();

	if (m_shapeInfo) {
		m_shapeInfo->Release();
	}
}

void CcdPhysicsController::SimulationTick(float timestep)
{
	btRigidBody *body = GetRigidBody();
	if (!body || body->isStaticObject()) {
		return;
	}

	// Clamp linear velocity
	if (m_cci.m_clamp_vel_max > 0.0f || m_cci.m_clamp_vel_min > 0.0f) {
		const btVector3 &linvel = body->getLinearVelocity();
		btScalar len = linvel.length();

		if (m_cci.m_clamp_vel_max > 0.0f && len > m_cci.m_clamp_vel_max) {
			body->setLinearVelocity(linvel * (m_cci.m_clamp_vel_max / len));
		}
		else if (m_cci.m_clamp_vel_min > 0.0f && !btFuzzyZero(len) && len < m_cci.m_clamp_vel_min) {
			body->setLinearVelocity(linvel * (m_cci.m_clamp_vel_min / len));
		}
	}

	// Clamp angular velocity
	if (m_cci.m_clamp_angvel_max > 0.0f || m_cci.m_clamp_angvel_min > 0.0f) {
		const btVector3 &angvel = body->getAngularVelocity();
		btScalar len = angvel.length();

		if (m_cci.m_clamp_angvel_max > 0.0f && len > m_cci.m_clamp_angvel_max) {
			body->setAngularVelocity(angvel * (m_cci.m_clamp_angvel_max / len));
		}
		else if (m_cci.m_clamp_angvel_min > 0.0f && !btFuzzyZero(len) && len < m_cci.m_clamp_angvel_min) {
			body->setAngularVelocity(angvel * (m_cci.m_clamp_angvel_min / len));
		}
	}
}

/**
 * SynchronizeMotionStates ynchronizes dynas, kinematic and deformable entities (and do 'late binding')
 */
bool CcdPhysicsController::SynchronizeMotionStates(float time)
{
	//sync non-static to motionstate, and static from motionstate (todo: add kinematic etc.)

	btSoftBody *sb = GetSoftBody();
	if (sb) {
		// Keep m_softbodyStartTrans equal to the reported transform, it's the base of SetPosition/SetOrientation.
		if (sb->m_pose.m_bframe) {
			// m_rot is the pure rotation of the polar decomposition (m_scl holds the deformation).
			m_softbodyStartTrans.setBasis(sb->m_pose.m_rot);
			m_softbodyStartTrans.setOrigin(sb->m_pose.m_com);
			m_MotionState->SetWorldOrientation(ToMt(sb->m_pose.m_rot));
		}
		else {
			btVector3 aabbMin, aabbMax;
			sb->getAabb(aabbMin, aabbMax);
			m_softbodyStartTrans.setOrigin((aabbMax + aabbMin) * 0.5f);
		}
		m_MotionState->SetWorldPosition(ToMt(m_softbodyStartTrans.getOrigin()));
		m_MotionState->CalculateWorldTransformations();
		return true;
	}

	btRigidBody *body = GetRigidBody();

	// Sleeping dynamic body: its transform didn't move since the last sync, rewriting it only marks the
	// node modified (PH2: "Use Frame Rate" syncs every controller twice per frame).
	if (body && !body->isStaticOrKinematicObject() && !body->isActive()) {
		SyncCollisionScaling();
		return true;
	}

	if (body && !body->isStaticObject()) {
		const btTransform& xform = body->getCenterOfMassTransform();
		if (m_bulletMotionState) {
			// Goes through BlenderBulletMotionState so the vehicle_com_offset compensation applies;
			// writing the COM transform directly drew the chassis shifted by the offset.
			m_bulletMotionState->setWorldTransform(xform);
			SyncCollisionScaling();
			return true;
		}
		const btMatrix3x3& worldOri = xform.getBasis();
		const btVector3& worldPos = xform.getOrigin();
		m_MotionState->SetWorldOrientation(ToMt(worldOri));
		m_MotionState->SetWorldPosition(ToMt(worldPos));
		m_MotionState->CalculateWorldTransformations();
	}

	SyncCollisionScaling();

	return true;
}

/* Only when the scale changed: compound and hull shapes recompute their AABB on every setLocalScaling. */
void CcdPhysicsController::SyncCollisionScaling()
{
	btCollisionShape *shape = GetCollisionShape();
	const btVector3 scale = ToBullet(m_MotionState->GetWorldScaling());
	if (shape && !(shape->getLocalScaling() == scale)) {
		shape->setLocalScaling(scale);
	}
}

/**
 * WriteMotionStateToDynamics synchronizes dynas, kinematic and deformable entities (and do 'late binding')
 */

void CcdPhysicsController::WriteMotionStateToDynamics(bool nondynaonly)
{
	btTransform xform = CcdPhysicsController::GetTransformFromMotionState(m_MotionState);
	SetCenterOfMassTransform(xform);
}

void CcdPhysicsController::WriteDynamicsToMotionState()
{
}
// controller replication
void CcdPhysicsController::PostProcessReplica(class PHY_IMotionState *motionstate, class PHY_IPhysicsController *parentctrl)
{
	SetParentRoot((CcdPhysicsController *)parentctrl);
	m_MotionState = motionstate;
	m_registerCount = 0;
	m_collisionShape = nullptr;
	// The replica hasn't actually been added to any compound shape yet; the copy constructor
	// copies these pointers verbatim from the original, which would otherwise leave this replica
	// thinking it is still parented (or its bullet shape pointer aliasing the original's).
	m_compoundParent = nullptr;
	m_bulletChildShape = nullptr;

	// Clear all old constraints.
	m_ccdConstraintRefs.clear();

	// always create a new shape to avoid scaling bug
	if (m_shapeInfo) {
		m_shapeInfo->AddRef();
		m_collisionShape = m_shapeInfo->CreateBulletShape(m_cci.m_margin, m_cci.m_bGimpact, !m_cci.m_bSoft);

		if (m_collisionShape) {
			// new shape has no scaling, apply initial scaling
			//m_collisionShape->setMargin(m_cci.m_margin);
			m_collisionShape->setLocalScaling(m_cci.m_scaling);

			if (m_cci.m_mass) {
				m_collisionShape->calculateLocalInertia(m_cci.m_mass, m_cci.m_localInertiaTensor);
			}
		}
	}
	// The copied construction info still points to the original's shape: the soft body must be
	// built from the replica's own shape (the original can be freed before this replica).
	m_cci.m_collisionShape = m_collisionShape;
	m_savedSoftNodeMasses.clear();

	// load some characterists that are not
	btRigidBody *oldbody = GetRigidBody();
	// m_bulletMotionState still belongs to the original: keep its center of mass offset.
	const btVector3 comOffset = m_bulletMotionState ?
		static_cast<BlenderBulletMotionState *>(m_bulletMotionState)->GetComOffset() : btVector3(0.0f, 0.0f, 0.0f);
	m_object = nullptr;
	CreateRigidbody();
	if (!comOffset.fuzzyZero()) {
		SetCenterOfMassOffset(ToMt(comOffset));
	}
	btRigidBody *body = GetRigidBody();
	if (body) {
		if (m_cci.m_mass) {
			body->setMassProps(m_cci.m_mass, m_cci.m_localInertiaTensor * m_cci.m_inertiaFactor);
		}

		if (oldbody) {
			body->setLinearFactor(oldbody->getLinearFactor());
			body->setAngularFactor(oldbody->getAngularFactor());
			if (oldbody->getActivationState() == DISABLE_DEACTIVATION) {
				body->setActivationState(DISABLE_DEACTIVATION);
			}
		}
	}
	// sensor object are added when needed
	if (!m_cci.m_bSensor) {
		m_cci.m_physicsEnv->AddCcdPhysicsController(this);
	}
}

void CcdPhysicsController::SetPhysicsEnvironment(class PHY_IPhysicsEnvironment *env)
{
	// can safely assume CCD environment
	CcdPhysicsEnvironment *physicsEnv = static_cast<CcdPhysicsEnvironment *>(env);

	if (m_cci.m_physicsEnv != physicsEnv) {
		// since the environment is changing, we must also move the controler to the
		// new environment. Note that we don't handle sensor explicitly: this
		// function can be called on sensor but only when they are not registered
		if (m_cci.m_physicsEnv->RemoveCcdPhysicsController(this, true)) {
			physicsEnv->AddCcdPhysicsController(this);

			// Set the object to be active so it can at least by evaluated once.
			// This fixes issues with static objects not having their physics meshes
			// in the right spot when lib loading.
			m_object->setActivationState(ACTIVE_TAG);
		}
		m_cci.m_physicsEnv = physicsEnv;
	}
}

void CcdPhysicsController::SetCenterOfMassTransform(btTransform& xform)
{
	btRigidBody *body = GetRigidBody();
	if (body) {
		body->setCenterOfMassTransform(xform);
	}
	else {
		//either collision object or soft body?
		if (GetSoftBody()) {
			SetSoftBodyTransform(xform);
		}
		else {
			if (m_object->isStaticOrKinematicObject()) {
				m_object->setInterpolationWorldTransform(m_object->getWorldTransform());
			}
			else {
				m_object->setInterpolationWorldTransform(xform);
			}
			m_object->setWorldTransform(xform);
		}
	}
}

void CcdPhysicsController::SetSoftBodyTransform(const btTransform& xform)
{
	btSoftBody *softBody = GetSoftBody();
	if (!softBody) {
		return;
	}

	// The nodes are in world space: move them rigidly from the current frame to the new one.
	const btTransform delta = xform * m_softbodyStartTrans.inverse();
	btQuaternion rot;
	delta.getBasis().getRotation(rot);
	if (delta.getOrigin().fuzzyZero() && btFabs(rot.getW()) >= btScalar(1.0f - SIMD_EPSILON)) {
		return;
	}

	softBody->transform(delta);
	// transform() stores the delta, keep the absolute frame (used to place constraint pivots).
	softBody->m_initialWorldTransform = xform;
	m_softbodyStartTrans = xform;
}

const btTransform& CcdPhysicsController::GetEditTransform()
{
	return GetSoftBody() ? m_softbodyStartTrans : m_object->getWorldTransform();
}

// kinematic methods
void CcdPhysicsController::RelativeTranslate(const mt::vec3& dlocin, bool local)
{
	if (m_object) {
		m_object->activate(true);
		if (m_object->isStaticObject()) {
			if (!m_cci.m_bSensor) {
				m_object->setCollisionFlags(m_object->getCollisionFlags() | btCollisionObject::CF_KINEMATIC_OBJECT);
			}
			// kinematic object should not set the transform, it disturbs the velocity interpolation
			return;
		}

		btVector3 dloc = ToBullet(dlocin);
		btTransform xform = GetEditTransform();

		if (local) {
			dloc = xform.getBasis() * dloc;
		}

		xform.setOrigin(xform.getOrigin() + dloc);
		SetCenterOfMassTransform(xform);
	}
}

void CcdPhysicsController::RelativeRotate(const mt::mat3& rotval, bool local)
{
	if (m_object) {
		m_object->activate(true);
		if (m_object->isStaticObject()) {
			if (!m_cci.m_bSensor) {
				m_object->setCollisionFlags(m_object->getCollisionFlags() | btCollisionObject::CF_KINEMATIC_OBJECT);
			}
			// kinematic object should not set the transform, it disturbs the velocity interpolation
			return;
		}

		btMatrix3x3 drotmat = ToBullet(rotval);
		btMatrix3x3 currentOrn;
		GetWorldOrientation(currentOrn);

		btTransform xform = GetEditTransform();

		xform.setBasis(xform.getBasis() * (local ?
		                                   drotmat : (currentOrn.inverse() * drotmat * currentOrn)));

		SetCenterOfMassTransform(xform);
	}
}

void CcdPhysicsController::GetWorldOrientation(btMatrix3x3& mat)
{
	const mt::mat3 ori = m_MotionState->GetWorldOrientation();
	mat = ToBullet(ori);
}

mt::mat3 CcdPhysicsController::GetOrientation()
{
	const btMatrix3x3 orn = m_object->getWorldTransform().getBasis();
	return ToMt(orn);
}

void CcdPhysicsController::SetOrientation(const mt::mat3& orn)
{
	SetWorldOrientation(ToBullet(orn));
}

void CcdPhysicsController::SetWorldOrientation(const btMatrix3x3& orn)
{
	if (m_object) {
		m_object->activate(true);
		if (m_object->isStaticObject() && !m_cci.m_bSensor) {
			m_object->setCollisionFlags(m_object->getCollisionFlags() | btCollisionObject::CF_KINEMATIC_OBJECT);
		}
		btTransform xform = GetEditTransform();
		xform.setBasis(orn);
		SetCenterOfMassTransform(xform);
	}
}

void CcdPhysicsController::SetPosition(const mt::vec3& pos)
{
	if (m_object) {
		m_object->activate(true);
		if (m_object->isStaticObject()) {
			if (!m_cci.m_bSensor) {
				m_object->setCollisionFlags(m_object->getCollisionFlags() | btCollisionObject::CF_KINEMATIC_OBJECT);
			}
			// kinematic object should not set the transform, it disturbs the velocity interpolation
			return;
		}

		btTransform xform = GetEditTransform();
		xform.setOrigin(ToBullet(pos));
		SetCenterOfMassTransform(xform);
	}
}

void CcdPhysicsController::ForceWorldTransform(const btMatrix3x3& mat, const btVector3& pos)
{
	if (m_object) {
		btTransform& xform = m_object->getWorldTransform();
		xform.setBasis(mat);
		xform.setOrigin(pos);
	}
}

void CcdPhysicsController::RefreshCollisions()
{
	// the object is in an inactive layer so it's useless to update it and can cause problems
	if (IsPhysicsSuspended()) {
		return;
	}

	btSoftRigidDynamicsWorld *dw = m_cci.m_physicsEnv->GetDynamicsWorld();
	btBroadphaseProxy *proxy = m_object->getBroadphaseHandle();
	btDispatcher *dispatcher = dw->getDispatcher();
	btOverlappingPairCache *pairCache = dw->getPairCache();

	CleanPairCallback cleanPairs(proxy, pairCache, dispatcher);
	pairCache->processAllOverlappingPairs(&cleanPairs, dispatcher);

	// Forcibly recreate the physics object
	btBroadphaseProxy *handle = m_object->getBroadphaseHandle();
	m_cci.m_physicsEnv->UpdateCcdPhysicsController(this, GetMass(), GetFriction(), m_object->getCollisionFlags(), handle->m_collisionFilterGroup, handle->m_collisionFilterMask);
}

void CcdPhysicsController::SuspendPhysics(bool freeConstraints)
{
	m_cci.m_physicsEnv->RemoveCcdPhysicsController(this, freeConstraints);
}

void CcdPhysicsController::RestorePhysics()
{
	m_cci.m_physicsEnv->AddCcdPhysicsController(this);
}

/// Mass weighted center and linear velocity of the soft body nodes (pinned nodes are ignored).
static void SoftBodyLinearState(const btSoftBody *softBody, btVector3& com, btVector3& linVel)
{
	btScalar totalMass = 0.0f;
	com.setZero();
	linVel.setZero();
	for (int i = 0, size = softBody->m_nodes.size(); i < size; ++i) {
		const btSoftBody::Node& node = softBody->m_nodes[i];
		if (node.m_im > 0.0f) {
			const btScalar mass = 1.0f / node.m_im;
			com += node.m_x * mass;
			linVel += node.m_v * mass;
			totalMass += mass;
		}
	}
	if (totalMass > 0.0f) {
		com /= totalMass;
		linVel /= totalMass;
	}
}

/// Angular velocity of the soft body nodes around com: I^-1 * L.
static btVector3 SoftBodyAngularVelocity(const btSoftBody *softBody, const btVector3& com, const btVector3& linVel)
{
	btVector3 momentum(0.0f, 0.0f, 0.0f);
	btMatrix3x3 inertia(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f);
	for (int i = 0, size = softBody->m_nodes.size(); i < size; ++i) {
		const btSoftBody::Node& node = softBody->m_nodes[i];
		if (node.m_im > 0.0f) {
			const btScalar mass = 1.0f / node.m_im;
			const btVector3 r = node.m_x - com;
			momentum += r.cross(node.m_v - linVel) * mass;
			const btScalar r2 = r.length2();
			for (int row = 0; row < 3; ++row) {
				for (int col = 0; col < 3; ++col) {
					inertia[row][col] += mass * ((row == col ? r2 : 0.0f) - r[row] * r[col]);
				}
			}
		}
	}
	if (btFuzzyZero(inertia.determinant())) {
		return btVector3(0.0f, 0.0f, 0.0f);
	}
	return inertia.inverse() * momentum;
}

void CcdPhysicsController::SuspendDynamics(bool ghost)
{
	btSoftBody *softBody = GetSoftBody();
	if (softBody) {
		// A soft body has no static mode: freeze it by pinning every node (zero mass).
		if (!m_suspended && !IsPhysicsSuspended()) {
			const int numNodes = softBody->m_nodes.size();
			m_savedSoftNodeMasses.resize(numNodes);
			for (int i = 0; i < numNodes; ++i) {
				m_savedSoftNodeMasses[i] = softBody->getMass(i);
				softBody->setMass(i, 0.0f);
				softBody->m_nodes[i].m_v.setZero();
			}
			// m_bDyna stays set: the soft body is still synchronized from its nodes.
			m_suspended = true;
		}
		return;
	}

	btRigidBody *body = GetRigidBody();
	if (body && !m_suspended && !m_cci.m_bSensor && !IsPhysicsSuspended()) {
		btBroadphaseProxy *handle = body->getBroadphaseHandle();

		m_savedCollisionFlags = body->getCollisionFlags();
		m_savedMass = GetMass();
		m_savedFriction = GetFriction();
		m_savedDyna = m_cci.m_bDyna;
		m_savedCollisionFilterGroup = handle->m_collisionFilterGroup;
		m_savedCollisionFilterMask = handle->m_collisionFilterMask;
		m_suspended = true;
		m_cci.m_physicsEnv->UpdateCcdPhysicsController(this,
		                                                    0.0f,
															0.0f,
		                                                    btCollisionObject::CF_STATIC_OBJECT | ((ghost) ? btCollisionObject::CF_NO_CONTACT_RESPONSE : (m_savedCollisionFlags & btCollisionObject::CF_NO_CONTACT_RESPONSE)),
		                                                    btBroadphaseProxy::StaticFilter,
		                                                    btBroadphaseProxy::AllFilter ^ btBroadphaseProxy::StaticFilter);
		m_cci.m_bDyna = false;
	}
}

void CcdPhysicsController::RestoreDynamics()
{
	btSoftBody *softBody = GetSoftBody();
	if (softBody) {
		if (m_suspended && !IsPhysicsSuspended()) {
			if (m_savedSoftNodeMasses.size() == softBody->m_nodes.size()) {
				for (int i = 0, size = m_savedSoftNodeMasses.size(); i < size; ++i) {
					softBody->setMass(i, m_savedSoftNodeMasses[i]);
				}
			}
			m_savedSoftNodeMasses.clear();
			softBody->activate(true);
			m_suspended = false;
		}
		return;
	}

	btRigidBody *body = GetRigidBody();
	if (body && m_suspended && !IsPhysicsSuspended()) {
		// before make sure any position change that was done in this logic frame are accounted for
		SetTransform();
		m_cci.m_physicsEnv->UpdateCcdPhysicsController(this,
		                                                    m_savedMass,
															m_savedFriction,
		                                                    m_savedCollisionFlags,
		                                                    m_savedCollisionFilterGroup,
		                                                    m_savedCollisionFilterMask);
		body->activate();
		m_cci.m_bDyna = m_savedDyna;
		m_suspended = false;
	}
}

mt::vec3 CcdPhysicsController::GetPosition() const
{
	return ToMt(m_object->getWorldTransform().getOrigin());
}

void CcdPhysicsController::SetScaling(const mt::vec3& scale)
{
	if (!btFuzzyZero(m_cci.m_scaling.x() - scale.x) ||
	    !btFuzzyZero(m_cci.m_scaling.y() - scale.y) ||
	    !btFuzzyZero(m_cci.m_scaling.z() - scale.z)) {
		m_cci.m_scaling = ToBullet(scale);

		if (m_object && m_object->getCollisionShape()) {
			m_object->activate(true); // without this, sleeping objects scale wont be applied in bullet if python changes the scale - Campbell.
			m_object->getCollisionShape()->setLocalScaling(m_cci.m_scaling);

			btRigidBody *body = GetRigidBody();
			if (body && m_cci.m_mass) {
				body->getCollisionShape()->calculateLocalInertia(m_cci.m_mass, m_cci.m_localInertiaTensor);
				body->setMassProps(m_cci.m_mass, m_cci.m_localInertiaTensor * m_cci.m_inertiaFactor);
			}
		}
	}
}

void CcdPhysicsController::SetTransform()
{
	// The soft body is placed by its nodes, not by a world transform.
	if (GetSoftBody()) {
		return;
	}
	const mt::vec3 pos = m_MotionState->GetWorldPosition();
	const mt::mat3 rot = m_MotionState->GetWorldOrientation();
	ForceWorldTransform(ToBullet(rot), ToBullet(pos));

	if (!IsDynamic() && !GetConstructionInfo().m_bSensor && !m_characterController) {
		btCollisionObject *object = GetRigidBody();
		object->setActivationState(ACTIVE_TAG);
		object->setCollisionFlags(object->getCollisionFlags() | btCollisionObject::CF_KINEMATIC_OBJECT);
	}
}

float CcdPhysicsController::GetMass()
{
	if (GetSoftBody()) {
		return GetSoftBody()->getTotalMass();
	}

	float invmass = 0.0f;
	if (GetRigidBody()) {
		invmass = GetRigidBody()->getInvMass();
	}
	if (invmass) {
		return 1.0f / invmass;
	}
	return 0.0f;
}

void CcdPhysicsController::SetMass(float newmass)
{
	btSoftBody *softBody = GetSoftBody();
	if (softBody) {
		// setTotalMass() scales the node masses, pinned nodes stay pinned.
		if (!m_suspended && newmass > 0.0f && softBody->getTotalMass() > 0.0f) {
			softBody->setTotalMass(newmass);
			m_cci.m_mass = newmass;
		}
		return;
	}

	btRigidBody *body = GetRigidBody();
	if (body && !m_suspended && !IsPhysicsSuspended() && (!mt::FuzzyZero(newmass) && !mt::FuzzyZero(GetMass()))) {
		btBroadphaseProxy *handle = body->getBroadphaseHandle();
		m_cci.m_physicsEnv->UpdateCcdPhysicsController(this,
		                                                    newmass,
															GetFriction(),
		                                                    body->getCollisionFlags(),
		                                                    handle->m_collisionFilterGroup,
		                                                    handle->m_collisionFilterMask);
	}
}

bool CcdPhysicsController::GetAnisotropicFrictionEnabled() const
{
	return m_cci.m_do_anisotropic;
}

void CcdPhysicsController::SetAnisotropicFrictionEnabled(bool enabled)
{
	m_cci.m_do_anisotropic = enabled;
	if (m_object) {
		// Modo 0 desliga o atrito anisotrópico no Bullet sem perder os coeficientes.
		m_object->setAnisotropicFriction(m_cci.m_anisotropicFriction,
		                                 enabled ? btCollisionObject::CF_ANISOTROPIC_FRICTION : 0);
	}
}

mt::vec3 CcdPhysicsController::GetAnisotropicFriction() const
{
	return ToMt(m_cci.m_anisotropicFriction);
}

void CcdPhysicsController::SetAnisotropicFriction(const mt::vec3& friction)
{
	m_cci.m_anisotropicFriction = ToBullet(friction);
	SetAnisotropicFrictionEnabled(m_cci.m_do_anisotropic);
}

float CcdPhysicsController::GetFriction()
{
	btSoftBody *softBody = GetSoftBody();
	if (softBody) {
		// Soft body dynamic friction coefficient [0,1].
		return softBody->m_cfg.kDF;
	}

	if (GetRigidBody()) {
		return GetRigidBody()->getFriction(); // return Friction value
	}
	return 0.0f;
}

void CcdPhysicsController::SetFriction(float newfriction)
{
	btSoftBody *softBody = GetSoftBody();
	if (softBody) {
		softBody->m_cfg.kDF = btClamped(btScalar(newfriction), btScalar(0.0f), btScalar(1.0f));
		return;
	}

	btRigidBody* body = GetRigidBody();
	if (body && !m_suspended && !IsPhysicsSuspended() &&
		newfriction > 0.0) {
		btBroadphaseProxy* handle = body->getBroadphaseHandle();
		GetPhysicsEnvironment()->UpdateCcdPhysicsController(this,
															GetMass(),
															newfriction,
															body->getCollisionFlags(),
															handle->m_collisionFilterGroup,
															handle->m_collisionFilterMask);
	}
}

float CcdPhysicsController::GetInertiaFactor() const
{
	return m_cci.m_inertiaFactor;
}

// physics methods
void CcdPhysicsController::ApplyTorque(const mt::vec3&  torquein, bool local)
{
	btVector3 torque = ToBullet(torquein);
	btTransform xform = m_object->getWorldTransform();


	if (m_object && torque.length2() > (SIMD_EPSILON * SIMD_EPSILON)) {
		btRigidBody *body = GetRigidBody();
		m_object->activate();
		if (m_object->isStaticObject()) {
			if (!m_cci.m_bSensor) {
				m_object->setCollisionFlags(m_object->getCollisionFlags() | btCollisionObject::CF_KINEMATIC_OBJECT);
			}
			return;
		}
		if (local) {
			torque  = xform.getBasis() * torque;
		}
		if (body) {
			if  (m_cci.m_bRigid) {
				body->applyTorque(torque);
			}
			else {
				//workaround for incompatibility between 'DYNAMIC' game object, and angular factor
				//a DYNAMIC object has some inconsistency: it has no angular effect due to collisions, but still has torque
				const btVector3 angFac = body->getAngularFactor();
				btVector3 tmpFac(1.0f, 1.0f, 1.0f);
				body->setAngularFactor(tmpFac);
				body->applyTorque(torque);
				body->setAngularFactor(angFac);
			}
		}
	}
}

void CcdPhysicsController::ApplyForce(const mt::vec3& forcein, bool local)
{
	btVector3 force = ToBullet(forcein);

	if (m_object && force.length2() > (SIMD_EPSILON * SIMD_EPSILON)) {
		m_object->activate();
		if (m_object->isStaticObject()) {
			if (!m_cci.m_bSensor) {
				m_object->setCollisionFlags(m_object->getCollisionFlags() | btCollisionObject::CF_KINEMATIC_OBJECT);
			}
			return;
		}
		const btTransform& xform = GetEditTransform();

		if (local) {
			force = xform.getBasis() * force;
		}
		btRigidBody *body = GetRigidBody();
		if (body) {
			body->applyCentralForce(force);
		}
		btSoftBody *soft = GetSoftBody();
		if (soft) {
			// the force is applied on each node, must reduce it in the same extend
			if (soft->m_nodes.size() > 0) {
				force /= soft->m_nodes.size();
			}
			soft->addForce(force);
		}
	}
}
void CcdPhysicsController::SetAngularVelocity(const mt::vec3& ang_vel, bool local)
{
	btVector3 angvel = ToBullet(ang_vel);

	/* Refuse tiny tiny velocities, as they might cause instabilities. */
	float vel_squared = angvel.length2();
	if (vel_squared > 0.0f && vel_squared <= (SIMD_EPSILON * SIMD_EPSILON)) {
		angvel = btVector3(0.0f, 0.0f, 0.0f);
	}

	if (m_object) {
		m_object->activate(true);
		if (m_object->isStaticObject()) {
			if (!m_cci.m_bSensor) {
				m_object->setCollisionFlags(m_object->getCollisionFlags() | btCollisionObject::CF_KINEMATIC_OBJECT);
			}
			return;
		}
		const btTransform& xform = GetEditTransform();
		if (local) {
			angvel = xform.getBasis() * angvel;
		}
		btRigidBody *body = GetRigidBody();
		if (body) {
			body->setAngularVelocity(angvel);
		}
		btSoftBody *soft = GetSoftBody();
		if (soft) {
			// Keep the linear velocity, replace the rotation around the center of mass.
			btVector3 com, linVel;
			SoftBodyLinearState(soft, com, linVel);
			for (int i = 0, size = soft->m_nodes.size(); i < size; ++i) {
				btSoftBody::Node& node = soft->m_nodes[i];
				if (node.m_im > 0.0f) {
					node.m_v = linVel + angvel.cross(node.m_x - com);
				}
			}
		}
	}
}
void CcdPhysicsController::SetLinearVelocity(const mt::vec3& lin_vel, bool local)
{
	btVector3 linVel = ToBullet(lin_vel);

	/* Refuse tiny tiny velocities, as they might cause instabilities. */
	const float vel_squared = linVel.length2();
	if (vel_squared > 0.0f && vel_squared <= (SIMD_EPSILON * SIMD_EPSILON)) {
		linVel = btVector3(0.0f, 0.0f, 0.0f);
	}

	if (m_object) {
		m_object->activate(true);
		if (m_object->isStaticObject()) {
			if (!m_cci.m_bSensor) {
				m_object->setCollisionFlags(m_object->getCollisionFlags() | btCollisionObject::CF_KINEMATIC_OBJECT);
			}
			return;
		}

		btSoftBody *soft = GetSoftBody();
		if (soft) {
			if (local) {
				linVel = m_softbodyStartTrans.getBasis() * linVel;
			}
			soft->setVelocity(linVel);
		}
		else {
			btTransform xform = m_object->getWorldTransform();
			if (local) {
				linVel  = xform.getBasis() * linVel;
			}
			btRigidBody *body = GetRigidBody();
			if (body) {
				body->setLinearVelocity(linVel);
			}
		}
	}
}
void CcdPhysicsController::ApplyImpulse(const mt::vec3& attach, const mt::vec3& impulsein, bool local)
{
	btVector3 impulse = ToBullet(impulsein);

	if (m_object && impulse.length2() > (SIMD_EPSILON * SIMD_EPSILON)) {
		m_object->activate();
		if (m_object->isStaticObject()) {
			if (!m_cci.m_bSensor) {
				m_object->setCollisionFlags(m_object->getCollisionFlags() | btCollisionObject::CF_KINEMATIC_OBJECT);
			}
			return;
		}

		const btTransform xform = m_object->getWorldTransform();
		btVector3 pos;

		if (local) {
			pos = ToBullet(attach);
			impulse = xform.getBasis() * impulse;
		}
		else {
			/* If the point of impulse application is not equal to the object position
			 * then an angular momentum is generated in the object*/
			pos = ToBullet(attach) - xform.getOrigin();
		}

		btRigidBody *body = GetRigidBody();
		if (body) {
			body->applyImpulse(impulse, pos);
		}
	}

}

void CcdPhysicsController::Jump()
{
	if (m_object && m_characterController) {
		m_characterController->jump();
	}
}

void CcdPhysicsController::SetActive(bool active)
{
	// Wakes a sleeping body, e.g. resting on a collision shape that changed under it (dents).
	if (active && m_object) {
		m_object->activate(true);
	}
}

unsigned short CcdPhysicsController::GetCollisionGroup() const
{
	return m_cci.m_collisionGroup;
}

unsigned short CcdPhysicsController::GetCollisionMask() const
{
	return m_cci.m_collisionMask;
}

void CcdPhysicsController::SetCollisionGroup(unsigned short group)
{
	m_cci.m_collisionGroup = group;
}

void CcdPhysicsController::SetCollisionMask(unsigned short mask)
{
	m_cci.m_collisionMask = mask;
}

float CcdPhysicsController::GetLinearDamping() const
{
	const btRigidBody *body = GetRigidBody();
	if (body) {
		return body->getLinearDamping();
	}
	return 0.0f;
}

float CcdPhysicsController::GetAngularDamping() const
{
	const btRigidBody *body = GetRigidBody();
	if (body) {
		return body->getAngularDamping();
	}
	return 0.0f;
}

void CcdPhysicsController::SetLinearDamping(float damping)
{
	SetDamping(damping, GetAngularDamping());
}

void CcdPhysicsController::SetAngularDamping(float damping)
{
	SetDamping(GetLinearDamping(), damping);
}

void CcdPhysicsController::SetDamping(float linear, float angular)
{
	btRigidBody *body = GetRigidBody();
	if (!body) {
		return;
	}

	body->setDamping(linear, angular);
}




void CcdPhysicsController::SetCcdMotionThreshold(float ccd_motion_threshold)
{
  btRigidBody *body = GetRigidBody();
  if (!body)
    return;

  body->setCcdMotionThreshold(ccd_motion_threshold);
}

void CcdPhysicsController::SetCcdSweptSphereRadius(float ccd_swept_sphere_radius)
{
  btRigidBody *body = GetRigidBody();
  if (!body)
    return;

  body->setCcdSweptSphereRadius(ccd_swept_sphere_radius);
}



void CcdPhysicsController::SetSoftLinStiff(float linstiff)
{// Sets linear stiffness for soft body
	btSoftBody *softBody = GetSoftBody();
	if (!softBody)
		return;

	if (softBody && softBody->m_materials.size() > 0) {
		// Access the first material (or the material you want to modify)
		btSoftBody::Material* material = softBody->m_materials[0];

		if (material) {
			material->m_kLST = linstiff;
			softBody->m_bUpdateRtCst = true; // Update constraints
		}
	}
}


void CcdPhysicsController::SetSoftAngStiff(float angstiff)
{// Sets angular stiffness for soft body
	btSoftBody *softBody = GetSoftBody();
	if (!softBody)
		return;

	if (softBody && softBody->m_materials.size() > 0) {
		// Access the first material (or the material you want to modify)
		btSoftBody::Material* material = softBody->m_materials[0];

		if (material) {
			material->m_kAST = angstiff;
			softBody->m_bUpdateRtCst = true; // Update constraints
		}
	}
}

void CcdPhysicsController::SetSoftVolume(float volume)
{// Sets volume for soft body
	btSoftBody *softBody = GetSoftBody();
	if (!softBody)
		return;

	if (softBody && softBody->m_materials.size() > 0) {
		// Access the first material (or the material you want to modify)
		btSoftBody::Material* material = softBody->m_materials[0];

		if (material) {
			material->m_kVST = volume;
			softBody->m_bUpdateRtCst = true; // Update constraints
		}
	}
}








void CcdPhysicsController::SetSoftVsRigidHardness(float hardness)
{// sets soft vs rigid hardness
	btSoftBody *softBody = GetSoftBody();
	if (!softBody)
		return;

	softBody->m_cfg.kSRHR_CL = hardness;
}

void CcdPhysicsController::SetSoftVsKineticHardness(float hardness)
{// sets soft vs Kinetic hardness
	btSoftBody *softBody = GetSoftBody();
	if (!softBody)
		return;

	softBody->m_cfg.kSKHR_CL = hardness;
}




void CcdPhysicsController::SetSoftVsSoftHardness(float hardness) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kSSHR_CL = hardness;
}

void CcdPhysicsController::SetSoftVsRigidImpulseSplitCluster(float split) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kSR_SPLT_CL = split;
}

void CcdPhysicsController::SetSoftVsKineticImpulseSplitCluster(float split) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kSK_SPLT_CL = split;
}

void CcdPhysicsController::SetSoftVsSoftImpulseSplitCluster(float split) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kSS_SPLT_CL = split;
}

void CcdPhysicsController::SetVelocitiesCorrectionFactor(float factor) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kVCF = factor;
}

void CcdPhysicsController::SetDampingCoefficient(float coefficient) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kDP = coefficient;
}

void CcdPhysicsController::SetDragCoefficient(float coefficient) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kDG = coefficient;
}

void CcdPhysicsController::SetLiftCoefficient(float coefficient) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kLF = coefficient;
}

void CcdPhysicsController::SetPressureCoefficient(float coefficient) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kPR = coefficient;
}

void CcdPhysicsController::SetVolumeConversationCoefficient(float coefficient) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kVC = coefficient;
}

void CcdPhysicsController::SetDynamicFrictionCoefficient(float coefficient) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kDF = coefficient;
}

void CcdPhysicsController::SetPoseMatchingCoefficient(float coefficient) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kMT = coefficient;
}

void CcdPhysicsController::SetRigidContactsHardness(float hardness) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kCHR = hardness;
}

void CcdPhysicsController::SetKineticContactsHardness(float hardness) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kKHR = hardness;
}

void CcdPhysicsController::SetSoftContactsHardness(float hardness) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kSHR = hardness;
}






void CcdPhysicsController::SetAnchorsHardness(float val) {
    // Anchors hardness [0,1]
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.kAHR = val;
}

void CcdPhysicsController::SetVelocitySolverIterations(int iterations) {
    // Velocity solver iterations
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.viterations = iterations;
}

void CcdPhysicsController::SetPositionSolverIterations(int iterations) {
    // Position solver iterations
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.piterations = iterations;
}

void CcdPhysicsController::SetDriftSolverIterations(int iterations) {
    // Drift solver iterations
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.diterations = iterations;
}

void CcdPhysicsController::SetClusterSolverIterations(int iterations) {
    // Cluster solver iterations
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    softBody->m_cfg.citerations = iterations;
}



void CcdPhysicsController::SetSoftPoseMatching(bool enableShapeMatching) {
    btSoftBody* softBody = GetSoftBody();
    if (!softBody)
        return;

    if (enableShapeMatching) {
        softBody->setPose(false, true); // Shape matching enabled: disable pose update, relative pose.
    } else {
        softBody->setPose(true, false); // Shape matching disabled: enable pose update, absolute pose.
    }
}



// reading out information from physics
mt::vec3 CcdPhysicsController::GetLinearVelocity()
{
	btRigidBody *body = GetRigidBody();
	if (body) {
		const btVector3& linvel = body->getLinearVelocity();
		return ToMt(linvel);
	}
	btSoftBody *soft = GetSoftBody();
	if (soft) {
		btVector3 com, linVel;
		SoftBodyLinearState(soft, com, linVel);
		return ToMt(linVel);
	}

	return mt::zero3;
}

mt::vec3 CcdPhysicsController::GetAngularVelocity()
{
	btRigidBody *body = GetRigidBody();
	if (body) {
		const btVector3& angvel = body->getAngularVelocity();
		return ToMt(angvel);
	}
	btSoftBody *soft = GetSoftBody();
	if (soft) {
		btVector3 com, linVel;
		SoftBodyLinearState(soft, com, linVel);
		return ToMt(SoftBodyAngularVelocity(soft, com, linVel));
	}

	return mt::zero3;
}

mt::vec3 CcdPhysicsController::GetVelocity(const mt::vec3 &posin)
{
	btRigidBody *body = GetRigidBody();
	if (body) {
		btVector3 linvel = body->getVelocityInLocalPoint(ToBullet(posin));
		return ToMt(linvel);
	}
	btSoftBody *soft = GetSoftBody();
	if (soft) {
		// posin is relative to the center of mass, like getVelocityInLocalPoint().
		btVector3 com, linVel;
		SoftBodyLinearState(soft, com, linVel);
		const btVector3 angVel = SoftBodyAngularVelocity(soft, com, linVel);
		return ToMt(linVel + angVel.cross(ToBullet(posin)));
	}

	return mt::zero3;
}

mt::vec3 CcdPhysicsController::GetLocalInertia()
{
	btRigidBody *body = GetRigidBody();
	mt::vec3 inertia = mt::zero3;
	if (body) {
		const btVector3 inv_inertia = body->getInvInertiaDiagLocal();
		if (!btFuzzyZero(inv_inertia.getX()) &&
		    !btFuzzyZero(inv_inertia.getY()) &&
		    !btFuzzyZero(inv_inertia.getZ())) {
			inertia = mt::vec3(1.0f / inv_inertia.getX(), 1.0f / inv_inertia.getY(), 1.0f / inv_inertia.getZ());
		}
	}
	return inertia;
}

// dyna's that are rigidbody are free in orientation, dyna's with non-rigidbody are restricted
void CcdPhysicsController::SetRigidBody(bool rigid)
{
	btRigidBody *body = GetRigidBody();
	if (body) {
		m_cci.m_bRigid = rigid;
		if (!rigid) {
			body->setAngularFactor(0.0f);
			body->setAngularVelocity(btVector3(0.0f, 0.0f, 0.0f));
		}
		else {
			body->setAngularFactor(m_cci.m_angularFactor);
		}
	}
}

// clientinfo for raycasts for example
void *CcdPhysicsController::GetNewClientInfo()
{
	return m_newClientInfo;
}

void CcdPhysicsController::SetNewClientInfo(void *clientinfo)
{
	m_newClientInfo = clientinfo;

	if (m_cci.m_bSensor) {
		// use a different callback function for sensor object,
		// bullet will not synchronize, we must do it explicitly
		SG_Callbacks& callbacks = KX_GameObject::GetClientObject((KX_ClientObjectInfo *)clientinfo)->GetNode()->GetCallBackFunctions();
		callbacks.m_updatefunc = KX_GameObject::SynchronizeTransformFunc;
	}
}

void CcdPhysicsController::UpdateDeactivation(float timeStep)
{
	btRigidBody *body = GetRigidBody();
	if (body) {
		body->updateDeactivation(timeStep);
	}
}

bool CcdPhysicsController::WantsSleeping()
{
	btRigidBody *body = GetRigidBody();
	if (body) {
		return body->wantsSleeping();
	}
	//check it out
	return true;
}
/* This function dynamically adds the collision shape of another controller to
 * the current controller shape provided it is a compound shape.
 * The idea is that dynamic parenting on a compound object will dynamically extend the shape
 */
void CcdPhysicsController::AddCompoundChild(PHY_IPhysicsController *child)
{
	if (child == nullptr || !IsCompound()) {
		return;
	}
	// other controller must be a bullet controller too
	// verify that body and shape exist and match
	CcdPhysicsController *childCtrl = static_cast<CcdPhysicsController *>(child);
	btRigidBody *rootBody = GetRigidBody();
	btRigidBody *childBody = childCtrl->GetRigidBody();
	if (!rootBody || !childBody) {
		return;
	}
	const btCollisionShape *rootShape = rootBody->getCollisionShape();
	const btCollisionShape *childShape = childBody->getCollisionShape();
	if (!rootShape ||
	    !childShape ||
	    rootShape->getShapeType() != COMPOUND_SHAPE_PROXYTYPE) {
		return;
	}
	btCompoundShape *compoundShape = (btCompoundShape *)rootShape;

	// compute relative transformation between parent and child
	btTransform rootTrans;
	btTransform childTrans;
	rootBody->getMotionState()->getWorldTransform(rootTrans);
	childBody->getMotionState()->getWorldTransform(childTrans);
	btVector3 rootScale = rootShape->getLocalScaling();
	rootScale[0] = 1.0 / rootScale[0];
	rootScale[1] = 1.0 / rootScale[1];
	rootScale[2] = 1.0 / rootScale[2];
	// relative scale = child_scale/parent_scale
	const btVector3 relativeScale = childShape->getLocalScaling() * rootScale;
	const btMatrix3x3 rootRotInverse = rootTrans.getBasis().transpose();
	// relative pos = parent_rot^-1 * ((parent_pos-child_pos)/parent_scale)
	const btVector3 relativePos = rootRotInverse * ((childTrans.getOrigin() - rootTrans.getOrigin()) * rootScale);
	// relative rot = parent_rot^-1 * child_rot
	const btMatrix3x3 relativeRot = rootRotInverse * childTrans.getBasis();

	// create a proxy shape info to store the transformation
	CcdShapeConstructionInfo *proxyShapeInfo = new CcdShapeConstructionInfo();
	// store the transformation to this object shapeinfo
	proxyShapeInfo->m_childTrans.setOrigin(relativePos);
	proxyShapeInfo->m_childTrans.setBasis(relativeRot);
	proxyShapeInfo->m_childScale = relativeScale;
	// we will need this to make sure that we remove the right proxy later when unparenting
	proxyShapeInfo->m_userData = childCtrl;
	proxyShapeInfo->SetProxy(childCtrl->GetShapeInfo()->AddRef());
	// add to parent compound shapeinfo (increments ref count)
	GetShapeInfo()->AddShape(proxyShapeInfo);
	// create new bullet collision shape from the object shapeinfo and set scaling
	btCollisionShape *newChildShape = proxyShapeInfo->CreateBulletShape(childCtrl->GetMargin(), childCtrl->GetConstructionInfo().m_bGimpact, true);
	newChildShape->setLocalScaling(relativeScale);
	// add bullet collision shape to parent compound collision shape
	compoundShape->addChildShape(proxyShapeInfo->m_childTrans, newChildShape);
	// proxyShapeInfo is not needed anymore, release it
	proxyShapeInfo->Release();
	// remember we created this shape
	childCtrl->m_bulletChildShape = newChildShape;
	childCtrl->m_compoundParent = this;

	// Recalculate inertia for object owning compound shape.
	if (!rootBody->isStaticOrKinematicObject()) {
		btVector3 localInertia;
		const float mass = 1.0f / rootBody->getInvMass();
		compoundShape->calculateLocalInertia(mass, localInertia);
		rootBody->setMassProps(mass, localInertia * m_cci.m_inertiaFactor);
	}
	// must update the broadphase cache,
	m_cci.m_physicsEnv->RefreshCcdPhysicsController(this);
	// remove the children
	m_cci.m_physicsEnv->RemoveCcdPhysicsController(childCtrl, true);
}

/* Reverse function of the above, it will remove a shape from a compound shape
 * provided that the former was added to the later using  AddCompoundChild()
 */
void CcdPhysicsController::RemoveCompoundChild(PHY_IPhysicsController *child)
{
	if (!child || !IsCompound()) {
		return;
	}
	// other controller must be a bullet controller too
	// verify that body and shape exist and match
	CcdPhysicsController *childCtrl = static_cast<CcdPhysicsController *>(child);
	btRigidBody *rootBody = GetRigidBody();
	btRigidBody *childBody = childCtrl->GetRigidBody();
	if (!rootBody || !childBody) {
		return;
	}
	const btCollisionShape *rootShape = rootBody->getCollisionShape();
	if (!rootShape ||
	    rootShape->getShapeType() != COMPOUND_SHAPE_PROXYTYPE) {
		return;
	}
	btCompoundShape *compoundShape = (btCompoundShape *)rootShape;
	// retrieve the shapeInfo
	CcdShapeConstructionInfo *childShapeInfo = childCtrl->GetShapeInfo();
	CcdShapeConstructionInfo *rootShapeInfo = GetShapeInfo();
	// and verify that the child is part of the parent
	int i = rootShapeInfo->FindChildShape(childShapeInfo, childCtrl);
	if (i < 0) {
		return;
	}
	rootShapeInfo->RemoveChildShape(i);
	if (childCtrl->m_bulletChildShape) {
		int numChildren = compoundShape->getNumChildShapes();
		for (i = 0; i < numChildren; i++) {
			if (compoundShape->getChildShape(i) == childCtrl->m_bulletChildShape) {
				compoundShape->removeChildShapeByIndex(i);
				compoundShape->recalculateLocalAabb();
				break;
			}
		}
		delete childCtrl->m_bulletChildShape;
		childCtrl->m_bulletChildShape = nullptr;
	}
	childCtrl->m_compoundParent = nullptr;
	// recompute inertia of parent
	if (!rootBody->isStaticOrKinematicObject()) {
		btVector3 localInertia;
		float mass = 1.f / rootBody->getInvMass();
		compoundShape->calculateLocalInertia(mass, localInertia);
		rootBody->setMassProps(mass, localInertia * m_cci.m_inertiaFactor);
	}
	// must update the broadphase cache,
	m_cci.m_physicsEnv->RefreshCcdPhysicsController(this);
	// reactivate the children
	m_cci.m_physicsEnv->AddCcdPhysicsController(childCtrl);
}

PHY_IPhysicsController *CcdPhysicsController::GetReplica()
{
	CcdPhysicsController *replica = new CcdPhysicsController(*this);
	return replica;
}

// Keeping this separate for now, maybe we can combine it with GetReplica()...
PHY_IPhysicsController *CcdPhysicsController::GetReplicaForSensors()
{
	// This is used only to replicate Near and Radar sensor controllers
	// The replication of object physics controller is done in KX_BulletPhysicsController::GetReplica()
	CcdConstructionInfo cinfo = m_cci;

	if (m_collisionShape) {
		switch (m_collisionShape->getShapeType()) {
			case SPHERE_SHAPE_PROXYTYPE:
			{
				btSphereShape *orgShape = (btSphereShape *)m_collisionShape;
				cinfo.m_collisionShape = new btSphereShape(*orgShape);
				break;
			}

			case CONE_SHAPE_PROXYTYPE:
			{
				btConeShape *orgShape = (btConeShape *)m_collisionShape;
				cinfo.m_collisionShape = new btConeShape(*orgShape);
				break;
			}

			default:
			{
				return nullptr;
			}
		}
	}

	cinfo.m_MotionState = new DefaultMotionState();
	cinfo.m_shapeInfo = m_shapeInfo;

	CcdPhysicsController *replica = new CcdPhysicsController(cinfo);
	return replica;
}

bool CcdPhysicsController::IsPhysicsSuspended()
{
	return !GetPhysicsEnvironment()->IsActiveCcdPhysicsController(this);
}

/* Refresh the physics object from either an object or a mesh.
 * from_gameobj and from_meshobj can be nullptr
 *
 * when setting the mesh, the following vars get priority
 * 1) from_meshobj - creates the phys mesh from RAS_Mesh
 * 2) from_gameobj - creates the phys mesh from the DerivedMesh where possible, else the RAS_Mesh
 * 3) this - update the phys mesh from DerivedMesh or RAS_Mesh
 *
 * Most of the logic behind this is in m_shapeInfo->UpdateMesh(...)
 */
bool CcdPhysicsController::ReinstancePhysicsShape(KX_GameObject *from_gameobj, RAS_Mesh *from_meshobj, bool dupli)
{
	if (!ELEM(m_shapeInfo->m_shapeType, PHY_SHAPE_MESH, PHY_SHAPE_POLYTOPE)) {
		return false;
	}

	if (!from_gameobj && !from_meshobj) {
		from_gameobj = KX_GameObject::GetClientObject((KX_ClientObjectInfo *)GetNewClientInfo());
	}

	if (dupli && (m_shapeInfo->GetRefCount() > 1)) {
		CcdShapeConstructionInfo *newShapeInfo = m_shapeInfo->GetReplica();
		m_shapeInfo->Release();
		m_shapeInfo = newShapeInfo;
	}

	/* updates the arrays used for making the new bullet mesh */
	m_shapeInfo->UpdateMesh(from_gameobj, from_meshobj);

	/* create the new bullet mesh */
	m_cci.m_physicsEnv->UpdateCcdPhysicsControllerShape(m_shapeInfo);

	return true;
}

bool CcdPhysicsController::ReplacePhysicsShape(PHY_IPhysicsController *phyctrl)
{
	CcdShapeConstructionInfo *shapeInfo = ((CcdPhysicsController *)phyctrl)->GetShapeInfo();

	if (m_characterController && ELEM(shapeInfo->m_shapeType,
			PHY_SHAPE_COMPOUND, PHY_SHAPE_PROXY, PHY_SHAPE_EMPTY, PHY_SHAPE_COMPOUND, PHY_SHAPE_MESH))
	{
		return false;
	}

	// switch shape info
	m_shapeInfo->Release();
	m_shapeInfo = shapeInfo->AddRef();

	// recreate Bullet shape only for this physics controller
	ReplaceControllerShape(nullptr);
	// refresh to remove collision pair
	m_cci.m_physicsEnv->RefreshCcdPhysicsController(this);

	return true;
}

///////////////////////////////////////////////////////////
///A small utility class, DefaultMotionState
///
///////////////////////////////////////////////////////////

DefaultMotionState::DefaultMotionState()
{
	m_worldTransform.setIdentity();
	m_localScaling.setValue(1.0f, 1.0f, 1.0f);
}

DefaultMotionState::~DefaultMotionState()
{
}

mt::vec3 DefaultMotionState::GetWorldPosition() const
{
	return ToMt(m_worldTransform.getOrigin());
}

mt::vec3 DefaultMotionState::GetWorldScaling() const
{
	return ToMt(m_localScaling);
}

mt::mat3 DefaultMotionState::GetWorldOrientation() const
{
	return ToMt(m_worldTransform.getBasis());
}

void DefaultMotionState::SetWorldOrientation(const mt::mat3& ori)
{
	m_worldTransform.setBasis(ToBullet(ori));
}
void DefaultMotionState::SetWorldPosition(const mt::vec3& pos)
{
	m_worldTransform.setOrigin(ToBullet(pos));
}

void DefaultMotionState::SetWorldOrientation(const mt::quat& quat)
{
	m_worldTransform.setRotation(ToBullet(quat));
}

void DefaultMotionState::CalculateWorldTransformations()
{
}

// Shape constructor
CcdShapeConstructionInfo::MeshShapeMap CcdShapeConstructionInfo::m_meshShapeMap;

CcdShapeConstructionInfo *CcdShapeConstructionInfo::FindMesh(RAS_Mesh *mesh, RAS_Deformer *deformer, PHY_ShapeType shapeType)
{
	MeshShapeMap::const_iterator mit = m_meshShapeMap.find(MeshShapeKey(mesh, deformer, shapeType));
	if (mit != m_meshShapeMap.end()) {
		return mit->second;
	}
	return nullptr;
}

CcdShapeConstructionInfo *CcdShapeConstructionInfo::GetReplica()
{
	CcdShapeConstructionInfo *replica = new CcdShapeConstructionInfo(*this);
	replica->ProcessReplica();
	return replica;
}

void CcdShapeConstructionInfo::ProcessReplica()
{
	m_userData = nullptr;
	m_mesh = nullptr;
	m_triangleIndexVertexArray = nullptr;
	m_forceReInstance = false;
	m_shapeProxy = nullptr;
	m_vertexArray.clear();
	m_polygonIndexArray.clear();
	m_triFaceArray.clear();
	m_triFaceUVcoArray.clear();
	m_shapeArray.clear();
}

/* Updates the arrays used by CreateBulletShape(),
 * take care that recalcLocalAabb() runs after CreateBulletShape is called.
 * */
bool CcdShapeConstructionInfo::UpdateMesh(KX_GameObject *gameobj, RAS_Mesh *meshobj)
{
	if (!gameobj && !meshobj) {
		return false;
	}

	if (!ELEM(m_shapeType, PHY_SHAPE_MESH, PHY_SHAPE_POLYTOPE)) {
		return false;
	}

	RAS_Deformer *deformer = nullptr;

	// Specified mesh object is the highest priority.
	if (!meshobj) {
		// Object deformer is second priority.
		deformer = gameobj ? gameobj->GetDeformer() : nullptr;
		if (deformer) {
			meshobj = deformer->GetMesh();
		}
		else {
			// Object mesh is last priority.
			const std::vector<KX_Mesh *>& meshes = gameobj->GetMeshList();
			if (!meshes.empty()) {
				meshobj = meshes.front();
			}
		}
	}

	// Can't find the mesh object.
	if (!meshobj) {
		return false;
	}

	RAS_DisplayArrayList displayArrays;

	// Indices count.
	unsigned int numIndices = 0;
	// Original (without split of normal or UV) vertex count.
	unsigned int numVertices = 0;

	/// Absolute polygon start index for each used display arrays.
	std::vector<unsigned int> polygonStartIndices;
	unsigned int curPolygonStartIndex = 0;

	// Compute indices count and maximum vertex count.
	for (unsigned int i = 0, numMat = meshobj->GetNumMaterials(); i < numMat; ++i) {
		RAS_MeshMaterial *meshmat = meshobj->GetMeshMaterial(i);
		RAS_IMaterial *mat = meshmat->GetBucket()->GetMaterial();

		RAS_DisplayArray *array = (deformer) ? deformer->GetDisplayArray(i) : meshmat->GetDisplayArray();
		const unsigned int indicesCount = array->GetTriangleIndexCount();

		// If collisions are disabled: do nothing.
		if (mat->IsCollider()) {
			numIndices += indicesCount;
			numVertices = std::max(numVertices, array->GetMaxOrigIndex() + 1);
			// Add valid display arrays.
			displayArrays.push_back(array);
			polygonStartIndices.push_back(curPolygonStartIndex);
		}

		curPolygonStartIndex += indicesCount / 3;
	}

	// Detect mesh without triangles.
	if (numIndices == 0 && m_shapeType == PHY_SHAPE_MESH) {
		return false;
	}

	m_vertexArray.resize(numVertices * 3);
	m_vertexRemap.resize(numVertices);
	// resize() doesn't initialize all values if the vector wasn't empty before. Prefer fill explicitly.
	std::fill(m_vertexRemap.begin(), m_vertexRemap.end(), -1);

	// Current vertex written.
	unsigned int curVert = 0;

	for (RAS_DisplayArray *array : displayArrays) {
		// Convert location of all vertices and remap if vertices weren't already converted.
		for (unsigned int j = 0, numvert = array->GetVertexCount(); j < numvert; ++j) {
			const RAS_VertexInfo& info = array->GetVertexInfo(j);
			const unsigned int origIndex = info.GetOrigIndex();
			/* Avoid double conversion of two unique vertices using the same base:
			 * using the same original vertex and so the same position.
			 */
			if (m_vertexRemap[origIndex] != -1) {
				continue;
			}

			const mt::vec3_packed& pos = array->GetPosition(j);
			m_vertexArray[curVert * 3] = pos.x;
			m_vertexArray[curVert * 3 + 1] = pos.y;
			m_vertexArray[curVert * 3 + 2] = pos.z;

			// Register the vertex index where the position was converted in m_vertexArray.
			m_vertexRemap[origIndex] = curVert++;
		}
	}

	// Convex shapes don't need indices.
	if (m_shapeType == PHY_SHAPE_MESH) {
		m_triFaceArray.resize(numIndices);
		m_triFaceUVcoArray.resize(numIndices);
		m_polygonIndexArray.resize(numIndices / 3);

		// Current triangle written.
		unsigned int curTri = 0;

		for (unsigned short i = 0, numArray = displayArrays.size(); i < numArray; ++i) {
			RAS_DisplayArray *array = displayArrays[i];
			const unsigned int polygonStartIndex = polygonStartIndices[i];

			// Convert triangles using remaped vertices index.
			for (unsigned int j = 0, numind = array->GetTriangleIndexCount(); j < numind; j += 3) {
				// Should match polygon access index with RAS_Mesh::GetPolygon.
				m_polygonIndexArray[curTri] = polygonStartIndex + j / 3;

				for (unsigned short k = 0; k < 3; ++k) {
					const unsigned int index = array->GetTriangleIndex(j + k);
					const unsigned int curInd = curTri * 3 + k;

					// Convert UV for raycast UV computation.
					const mt::vec2_packed& uv = array->GetUv(index, 0);
					m_triFaceUVcoArray[curInd] = {{uv.x, uv.y}};

					// Get vertex index from original index to m_vertexArray vertex index.
					const RAS_VertexInfo& info = array->GetVertexInfo(index);
					const unsigned int origIndex = info.GetOrigIndex();
					m_triFaceArray[curInd] = m_vertexRemap[origIndex];
				}
				++curTri;
			}
		}
	}

#if 0
	CM_Debug("# vert count " << m_vertexArray.size());
	for (int i = 0; i < m_vertexArray.size(); i += 3) {
		CM_Debug("v " << m_vertexArray[i] << " " << m_vertexArray[i + 1] << " " << m_vertexArray[i + 2]);
	}

	CM_Debug("# face count " << m_triFaceArray.size());
	for (int i = 0; i < m_triFaceArray.size(); i += 3) {
		CM_Debug("f " << m_triFaceArray[i] + 1 << " " << m_triFaceArray[i + 1] + 1 << " " << m_triFaceArray[i + 2] + 1);
	}
#endif

	// Force recreation of the m_triangleIndexVertexArray.
	if (m_triangleIndexVertexArray) {
		m_forceReInstance = true;
	}

	/* Make sure to also replace the mesh in the shape map! Otherwise we leave dangling references when we free.
	 * Note, this whole business could cause issues with shared meshes.
	 */
	for (MeshShapeMap::iterator it = m_meshShapeMap.begin(); it != m_meshShapeMap.end(); ) {
		if (it->second == this) {
			it = m_meshShapeMap.erase(it);
		}
		else {
			++it;
		}
	}

	// Register mesh object to shape.
	m_meshShapeMap[MeshShapeKey(meshobj, deformer, m_shapeType)] = this;

	m_mesh = meshobj;

	return true;
}

bool CcdShapeConstructionInfo::SetProxy(CcdShapeConstructionInfo *shapeInfo)
{
	if (!shapeInfo) {
		return false;
	}

	m_shapeType = PHY_SHAPE_PROXY;
	m_shapeProxy = shapeInfo;
	return true;
}

RAS_Mesh *CcdShapeConstructionInfo::GetMesh() const
{
	return m_mesh;
}

btCollisionShape *CcdShapeConstructionInfo::CreateBulletShape(btScalar margin, bool useGimpact, bool useBvh)
{
	btCollisionShape *collisionShape = nullptr;

	switch (m_shapeType) {
		case PHY_SHAPE_PROXY:
		{
			if (m_shapeProxy) {
				collisionShape = m_shapeProxy->CreateBulletShape(margin, useGimpact, useBvh);
			}
			break;
		}
		case PHY_SHAPE_BOX:
		{
			collisionShape = new btBoxShape(m_halfExtend);
			collisionShape->setMargin(margin);
			break;
		}
		case PHY_SHAPE_SPHERE:
		{
			collisionShape = new btSphereShape(m_radius);
			collisionShape->setMargin(margin);
			break;
		}
		case PHY_SHAPE_CYLINDER:
		{
			collisionShape = new btCylinderShapeZ(m_halfExtend);
			collisionShape->setMargin(margin);
			break;
		}
		case PHY_SHAPE_CONE:
		{
			collisionShape = new btConeShapeZ(m_radius, m_height);
			collisionShape->setMargin(margin);
			break;
		}
		case PHY_SHAPE_CAPSULE:
		{
			collisionShape = new btCapsuleShapeZ(m_radius, m_height);
			collisionShape->setMargin(margin);
			break;
		}
		case PHY_SHAPE_POLYTOPE:
		{
			if (m_vertexArray.size() == 0) {
				break;
			}

			// Keep only the points that lie on the hull: exact same shape, but
			// support queries no longer iterate over every interior vertex.
			// The hull points come from the cooked file when this vertex set was already computed.
			const unsigned int numVertices = m_vertexArray.size() / 3;
			std::vector<btScalar> points;
			if (!CcdCookedData::FindHull(&m_vertexArray[0], numVertices, points)) {
				btConvexHullComputer hullComputer;
				hullComputer.compute(&m_vertexArray[0], 3 * sizeof(btScalar), numVertices, 0.0f, 0.0f);
				points.reserve(hullComputer.vertices.size() * 3);
				for (int i = 0; i < hullComputer.vertices.size(); ++i) {
					const btVector3& point = hullComputer.vertices[i];
					points.insert(points.end(), {point.x(), point.y(), point.z()});
				}
				CcdCookedData::AddHull(&m_vertexArray[0], numVertices, points.data(), points.size() / 3);
			}
			btConvexHullShape *hullShape;
			if (points.size() >= 12) {
				hullShape = new btConvexHullShape(points.data(), points.size() / 3, 3 * sizeof(btScalar));
			}
			else {
				hullShape = new btConvexHullShape(&m_vertexArray[0], m_vertexArray.size() / 3, 3 * sizeof(btScalar));
			}
			hullShape->setMargin(margin);
			collisionShape = hullShape;
			break;
		}
		case PHY_SHAPE_MESH:
		{
			if (m_vertexArray.size() == 0) {
				break;
			}

			// Let's use the latest btScaledBvhTriangleMeshShape: it allows true sharing of
			// triangle mesh information between duplicates => drastic performance increase when
			// duplicating complex mesh objects.
			// BUT it causes a small performance decrease when sharing is not required:
			// 9 multiplications/additions and one function call for each triangle that passes the mid phase filtering
			// One possible optimization is to use directly the btBvhTriangleMeshShape when the scale is 1,1,1
			// and btScaledBvhTriangleMeshShape otherwise.
			if (useGimpact) {
				if (!m_triangleIndexVertexArray || m_forceReInstance) {
					if (m_triangleIndexVertexArray) {
						delete m_triangleIndexVertexArray;
					}

					m_triangleIndexVertexArray = new btTriangleIndexVertexArray(
						m_triFaceArray.size() / 3,
						m_triFaceArray.data(),
						3 * sizeof(int),
						m_vertexArray.size() / 3,
						&m_vertexArray[0],
						3 * sizeof(btScalar));
					m_forceReInstance = false;
				}

				btGImpactMeshShape *gimpactShape = new btGImpactMeshShape(m_triangleIndexVertexArray);
				gimpactShape->setMargin(margin);
				gimpactShape->updateBound();
				collisionShape = gimpactShape;
			}
			else {
				if (!m_triangleIndexVertexArray || m_forceReInstance) {
					///enable welding, only for the objects that need it (such as soft bodies)
					if (0.0f != m_weldingThreshold1) {
						btTriangleMesh *collisionMeshData = new btTriangleMesh(true, false);
						collisionMeshData->m_weldingThreshold = m_weldingThreshold1;
						bool removeDuplicateVertices = true;
						// m_vertexArray not in multiple of 3 anymore, use m_triFaceArray
						for (unsigned int i = 0; i < m_triFaceArray.size(); i += 3) {
							btScalar *bt = &m_vertexArray[3 * m_triFaceArray[i]];
							btVector3 v1(bt[0], bt[1], bt[2]);
							bt = &m_vertexArray[3 * m_triFaceArray[i + 1]];
							btVector3 v2(bt[0], bt[1], bt[2]);
							bt = &m_vertexArray[3 * m_triFaceArray[i + 2]];
							btVector3 v3(bt[0], bt[1], bt[2]);
							collisionMeshData->addTriangle(v1, v2, v3, removeDuplicateVertices);
						}
						m_triangleIndexVertexArray = collisionMeshData;
					}
					else {
						if (m_triangleIndexVertexArray) {
							delete m_triangleIndexVertexArray;
						}
						m_triangleIndexVertexArray = new btTriangleIndexVertexArray(
							m_triFaceArray.size() / 3,
							m_triFaceArray.data(),
							3 * sizeof(int),
							m_vertexArray.size() / 3,
							&m_vertexArray[0],
							3 * sizeof(btScalar));
					}

					m_forceReInstance = false;
				}

				if (m_weldingThreshold1 == 0.0f) {
					/* The bounds btTriangleMeshShape::recalcLocalAabb() would find (min/max of the triangle
					 * vertices, the margin is still 0 there) in one pass instead of six passes over every
					 * triangle. Set before each shape, as the arrays may have changed since the last one. */
					btVector3 aabbMin(0.0f, 0.0f, 0.0f);
					btVector3 aabbMax(0.0f, 0.0f, 0.0f);
					if (!m_triFaceArray.empty()) {
						aabbMin.setValue(BT_LARGE_FLOAT, BT_LARGE_FLOAT, BT_LARGE_FLOAT);
						aabbMax.setValue(-BT_LARGE_FLOAT, -BT_LARGE_FLOAT, -BT_LARGE_FLOAT);
						for (const int index : m_triFaceArray) {
							const btScalar *co = &m_vertexArray[3 * index];
							const btVector3 vertex(co[0], co[1], co[2]);
							aabbMin.setMin(vertex);
							aabbMax.setMax(vertex);
						}
					}
					m_triangleIndexVertexArray->setPremadeAabb(aabbMin, aabbMax);
				}

				btBvhTriangleMeshShape *unscaledShape;
				if (useBvh && m_weldingThreshold1 == 0.0f) {
					// The BVH is shared with every shape of identical arrays (see CcdSharedBvhTriangleMeshShape).
					unscaledShape = new CcdSharedBvhTriangleMeshShape(m_triangleIndexVertexArray);
				}
				else {
					unscaledShape = new btBvhTriangleMeshShape(m_triangleIndexVertexArray, true, useBvh);
				}
				unscaledShape->setMargin(margin);
				collisionShape = new btScaledBvhTriangleMeshShape(unscaledShape, btVector3(1.0f, 1.0f, 1.0f));
				collisionShape->setMargin(margin);
			}
			break;
		}
		case PHY_SHAPE_COMPOUND:
		{
			if (m_shapeArray.empty()) {
				break;
			}

			btCompoundShape *compoundShape = new btCompoundShape();
			for (CcdShapeConstructionInfo *childShape : m_shapeArray) {
				btCollisionShape *childCollisionShape = childShape->CreateBulletShape(margin, useGimpact, useBvh);
				if (childCollisionShape) {
					childCollisionShape->setLocalScaling(childShape->m_childScale);
					compoundShape->addChildShape(childShape->m_childTrans, childCollisionShape);
				}
			}

			collisionShape = compoundShape;
			break;
		}
		case PHY_SHAPE_EMPTY:
		{
			collisionShape = new btEmptyShape();
			collisionShape->setMargin(margin);
			break;
		}
		default:
		{
			BLI_assert(false);
		}
	}
	return collisionShape;
}

void CcdShapeConstructionInfo::AddShape(CcdShapeConstructionInfo *shapeInfo)
{
	m_shapeArray.push_back(shapeInfo);
	shapeInfo->AddRef();
}

CcdShapeConstructionInfo::~CcdShapeConstructionInfo()
{
	for (CcdShapeConstructionInfo *shapeInfo : m_shapeArray) {
		shapeInfo->Release();
	}
	m_shapeArray.clear();

	if (m_triangleIndexVertexArray) {
		delete m_triangleIndexVertexArray;
	}
	m_vertexArray.clear();

	for (MeshShapeMap::iterator it = m_meshShapeMap.begin(); it != m_meshShapeMap.end(); ) {
		if (it->second == this) {
			it = m_meshShapeMap.erase(it);
		}
		else {
			++it;
		}
	}

	if (m_shapeType == PHY_SHAPE_PROXY && m_shapeProxy) {
		m_shapeProxy->Release();
	}
}

