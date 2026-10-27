"""Generate ANI-01 policy probes from current scene and pipeline bodies.

No SDL, renderer, Blender animation evaluator or worker threads are executed.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'source/source/gameengine'
OUT = ROOT / 'artifacts/revisao-animacao-20261026'
spec = importlib.util.spec_from_file_location('clock_review', Path(__file__).with_name('revisao_relogio.py'))
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
block = helper.block

def main():
    scene = (BASE / 'Ketsji/KX_Scene.cpp').read_text(encoding='utf-8')
    obj = (BASE / 'Ketsji/KX_GameObject.cpp').read_text(encoding='utf-8')
    pipeline = (BASE / 'Ketsji/KX_SimulationPipeline.cpp').read_text(encoding='utf-8')
    update = block(scene, 'bool KX_Scene::UpdateAnimations(')
    selection = update[update.index('m_animNeedsUpdateCache.clear();'):update.index('for (KX_GameObject *gameobj : poseTasks)')]
    collect = update[update.index('// Keep work from earlier'):update.index('// Animation Events:')]
    remove = block(scene, 'bool KX_Scene::NewRemoveObject(')
    remove = remove[1:remove.index('// Multiplayer:')]
    cpp = r'''
#include <cstdlib>
#include <iostream>
#include <unordered_map>
#include <unordered_set>
#include <vector>
constexpr int TASK_PRIORITY_LOW=0;
struct KX_GameObject {
    bool m_bDoAnimations=true, m_halfAnimations=false, suspended=false, needs=true;
    int poses=0, deforms=0;
    bool GetDoAnimations() HALF
    bool IsActionsSuspended() { return suspended; }
};
struct Pool { std::vector<KX_GameObject *> tasks; };
void BLI_task_pool_push(Pool *pool, void (*)(), KX_GameObject *obj, bool, int) {
    pool->tasks.push_back(obj);
}
void BLI_task_pool_work_and_wait(Pool *pool) {
    for (auto obj:pool->tasks) ++obj->deforms;
    pool->tasks.clear();
}
struct KX_Scene {
    struct Data { struct Render { int frs_sec=24; } r; } data;
    Data *m_blenderScene=&data;
    Pool pool;
    Pool *m_animationPool=&pool;
    std::vector<KX_GameObject *> m_animatedlist;
    std::unordered_map<KX_GameObject *, bool> m_animNeedsUpdateCache;
    std::unordered_set<KX_GameObject *> m_pendingAnimationDeformers;
    double m_previousAnimTime=0;
    bool suspended=false;
    bool IsSuspended() { return suspended; }
    static void UpdateAnimDeformTask() {}
    bool Pose(double curtime, bool restrict) {
        if (restrict) RESTRICTION
        SELECT
        // Replace pose workers only; selection and pending collection are real code.
        for (auto obj:poseTasks) {
            ++obj->poses;
            m_animNeedsUpdateCache.at(obj)=obj->needs;
        }
        COLLECT
        return true;
    }
    void Remove(KX_GameObject *gameobj) { REMOVE }
    void UpdateAnimationDeformers(bool applyToMesh=true) DEFORM
};
struct Engine {
    enum { tc_animations, tc_animations_deform };
    struct Logger { void StartLog(int) {} } logger;
    bool gate=true, server=false, restrict=false;
    double time=0;
    bool NeedsAnimation() { return gate; }
    bool IsServerMode() { return server; }
    Logger& GetLogger() { return logger; }
    bool UpdateAnimations(KX_Scene *scene) { return scene->Pose(time,restrict); }
};
using KX_KetsjiEngine=Engine;
void Step(Engine *m_engine, KX_Scene *scene, bool deformAnimations) {
    if (m_engine->NeedsAnimation()) PIPELINE
}
void require(bool ok) { if (!ok) std::abort(); }
int main() {
    Engine engine;
    KX_GameObject normal, half, culled;
    half.m_halfAnimations=true;
    culled.needs=false;
    KX_Scene scene;
    scene.m_animatedlist={&normal,&half,&culled};
    for (int i=1;i<=3;++i) {
        engine.time=i/64.0;
        Step(&engine,&scene,i==3);
    }
    require(normal.poses==3 && normal.deforms==1);
    require(half.poses==1 && half.deforms==1); // Final half-animation pass skipped it.
    require(culled.poses==3 && culled.deforms==0);
    require(scene.m_pendingAnimationDeformers.empty());
    std::cout << "normal/half/culled: pending work survives skipped final pose; deform once\n";

    KX_GameObject restricted;
    KX_Scene limited;
    limited.m_animatedlist={&restricted};
    engine.restrict=true;
    for (int i=1;i<=4;++i) {
        engine.time=i/64.0;
        Step(&engine,&limited,i==4);
    }
    require(restricted.poses==1 && restricted.deforms==1);
    std::cout << "restricted: pose at step 3, skipped at step 4, final deformation preserved\n";

    engine.restrict=false;
    engine.server=true;
    KX_GameObject server;
    KX_Scene headless;
    headless.m_animatedlist={&server};
    for (int i=1;i<=4;++i) Step(&engine,&headless,i==4);
    require(server.poses==4 && server.deforms==0 && headless.m_pendingAnimationDeformers.empty());
    engine.server=false;
    engine.gate=false;
    Step(&engine,&headless,true);
    require(server.poses==4);
    engine.gate=true;
    headless.suspended=true;
    Step(&engine,&headless,true);
    require(server.poses==4);
    std::cout << "server/global gate/suspension: pose scheduling preserved; no server skinning\n";

    KX_GameObject removed;
    KX_Scene deletion;
    deletion.m_animatedlist={&removed};
    Step(&engine,&deletion,false);
    require(deletion.m_pendingAnimationDeformers.count(&removed)==1);
    deletion.Remove(&removed);
    deletion.m_animatedlist.clear();
    deletion.UpdateAnimationDeformers();
    require(removed.deforms==0 && deletion.m_animNeedsUpdateCache.empty());
    std::cout << "removal between steps: pending pointer erased before deformation\n";

    KX_GameObject duplicate;
    KX_Scene duplicates;
    duplicates.m_animatedlist={&duplicate,&duplicate};
    Step(&engine,&duplicates,true);
    require(duplicate.poses==1 && duplicate.deforms==1);
    std::cout << "duplicate list entry: one pose task and one deformation task\n";
}
'''
    replacements = {
        'HALF': block(obj, 'bool KX_GameObject::GetDoAnimations('),
        'RESTRICTION': block(update, 'if (restrict)'),
        'SELECT': selection, 'COLLECT': collect, 'REMOVE': remove,
        'DEFORM': block(scene, 'void KX_Scene::UpdateAnimationDeformers('),
        'PIPELINE': block(pipeline, 'if (m_engine->NeedsAnimation())'),
    }
    import re
    for marker, body in replacements.items():
        cpp = re.sub(r'\b' + marker + r'\b', lambda match: body, cpp)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'revisao_animacao_catchup.cpp').write_text(cpp, encoding='utf-8')
    files = [BASE / p for p in ('Ketsji/KX_Scene.cpp','Ketsji/KX_Scene.h',
             'Ketsji/KX_KetsjiEngine.cpp','Ketsji/KX_GameObject.cpp',
             'Ketsji/KX_SimulationPipeline.cpp','Ketsji/KX_SimulationPipeline.h',
             'VideoTexture/ImageRender.cpp')] + [Path(__file__).resolve()]
    (OUT / 'manifest.json').write_text(json.dumps({'method':'extracted policies with fake poses, deformers and task pool',
        'sources':[{'path':str(p.relative_to(ROOT)), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]},indent=2),encoding='utf-8')
    print(OUT.relative_to(ROOT))

if __name__ == '__main__':
    main()
