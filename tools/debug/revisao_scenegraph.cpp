// Diagnostic serial harness. Compiles the real SG_Node / KX_NodeRelationships sources.
// Locks are deliberately no-ops here: this does not test concurrency or the full runtime.
#include <cstdio>
#include <cmath>
#include "SG_Node.h"
#include "KX_NodeRelationships.h"

CM_ThreadLock::CM_ThreadLock() {}
CM_ThreadLock::~CM_ThreadLock() {}
CM_ThreadMutex::CM_ThreadMutex() {}
CM_ThreadMutex::~CM_ThreadMutex() {}
void CM_ThreadMutex::Lock() {}
void CM_ThreadMutex::Unlock() {}
CM_ThreadSpinLock::CM_ThreadSpinLock() {}
CM_ThreadSpinLock::~CM_ThreadSpinLock() {}
void CM_ThreadSpinLock::Lock() {}
void CM_ThreadSpinLock::Unlock() {}

static int updates = 0;
static void countUpdate(SG_Node *, void *, void *) { ++updates; }

struct QueueProbe : SG_QList {
    void resetSecondary() { m_fqlink = m_bqlink = this; }
};

static bool finite(const mt::mat3 &matrix)
{
    for (int col = 0; col < 3; ++col) {
        for (int row = 0; row < 3; ++row) {
            if (!std::isfinite(matrix(row, col))) return false;
        }
    }
    return true;
}

int main()
{
    SG_Callbacks callbacks;
    callbacks.m_updatefunc = countUpdate;
    SG_Node root(nullptr, nullptr, callbacks);
    SG_Node vertex(nullptr, nullptr, callbacks);
    SG_Node descendant(nullptr, nullptr, callbacks);
    root.SetParentRelation(new KX_NormalParentRelation());
    vertex.SetParentRelation(new KX_VertexParentRelation());
    descendant.SetParentRelation(new KX_NormalParentRelation());
    root.AddChild(&vertex);
    vertex.AddChild(&descendant);
    descendant.SetLocalPosition(mt::vec3(1, 0, 0));
    root.UpdateWorldData();
    const float before = descendant.GetWorldPosition().x;
    vertex.SetLocalPosition(mt::vec3(3, 0, 0));
    vertex.UpdateWorldData();
    const float after = descendant.GetWorldPosition().x;
    std::printf("vertex_propagation before=%g vertex=%g descendant=%g expected=4\n",
                before, vertex.GetWorldPosition().x, after);

    SG_Node normalRoot(nullptr, nullptr, callbacks);
    SG_Node normalChild(nullptr, nullptr, callbacks);
    normalRoot.SetParentRelation(new KX_NormalParentRelation());
    normalChild.SetParentRelation(new KX_NormalParentRelation());
    normalRoot.AddChild(&normalChild);
    normalChild.SetLocalPosition(mt::vec3(1, 0, 0));
    normalRoot.UpdateWorldData();
    normalRoot.SetLocalScale(mt::vec3(0, 1, 1));
    normalRoot.UpdateWorldData();
    const bool zeroFinite = finite(normalChild.GetWorldOrientation());
    std::printf("zero_scale orientation_finite=%s\n", zeroFinite ? "true" : "false");
    normalRoot.SetLocalScale(mt::vec3(2, 1, 1));
    normalRoot.UpdateWorldData();
    const float moveBefore = normalChild.GetWorldPosition().x;
    normalChild.RelativeTranslate(mt::vec3(1, 0, 0), &normalRoot, false);
    normalChild.UpdateWorldData();
    const float delta = normalChild.GetWorldPosition().x - moveBefore;
    std::printf("global_translation world_delta=%g requested=1\n", delta);

    updates = 0;
    for (int i = 0; i < 50; ++i) {
        normalRoot.SetLocalPosition(normalRoot.GetLocalPosition());
        normalRoot.UpdateWorldData();
    }
    const int identicalUpdates = updates;
    updates = 0;
    for (int i = 0; i < 50; ++i) {
        normalChild.RelativeTranslate(mt::zero3, &normalRoot, false);
        normalChild.UpdateWorldData();
    }
    const int zeroUpdates = updates;
    std::printf("unchanged_transforms setter_callbacks=%d zero_movement_callbacks=%d\n",
                identicalUpdates, zeroUpdates);

    QueueProbe first, second, item;
    first.QAddBack(&item);
    const bool admitted = second.QAddFront(&item);
    const bool stale = first.QPeek() == &item && second.QPeek() == &item;
    std::printf("queue_reinsert admitted=%s shared_item=%s\n",
                admitted ? "true" : "false", stale ? "true" : "false");
    // Restore the broken queue explicitly, so test teardown does not traverse stale links.
    item.QDelink();
    first.resetSecondary();
    second.resetSecondary();

    // Exit 0 only with SG-01/02/03/04/06 fixed (the original reproduction expected the defects).
    const bool fixed = before == 1 && std::fabs(after - 4.0f) < 1e-5f && zeroFinite &&
                       std::fabs(delta - 1.0f) < 1e-5f && !admitted && !stale &&
                       identicalUpdates == 0 && zeroUpdates == 0;
    std::printf("%s
", fixed ? "SG_ALL_FIXED" : "SG_REGRESSION");
    return fixed ? 0 : 1;
}
