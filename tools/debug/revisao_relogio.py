"""Generate a console diagnostic from current engine time-method bodies.

Run with Python, then compile the generated .cpp with MSVC (vcvars64 +
VSLANG=1033), CM_Clock.cpp and KX_CutsceneManager.cpp. This isolates arithmetic;
it does not instantiate KX_KetsjiEngine or run the game. Invalid float-to-int
conversions are inspected before conversion, never deliberately executed.
Exit zero means the documented observations were reproduced, not fixed.
"""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/revisao-relogio-20261026"
ENGINE = ROOT / "source/source/gameengine/Ketsji/KX_KetsjiEngine.cpp"


def block(text, marker):
    start = text.index(marker)
    opening = text.index("{", start)
    depth = 1
    end = opening + 1
    # Selected methods/blocks contain no braces in strings or comments.
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[opening:end]


def main():
    source = ENGINE.read_text(encoding="utf-8")
    methods = "\n".join(
        "void " + name + " " + block(source, "void KX_KetsjiEngine::" + name)
        for name in ("FrameTiming()", "AdvanceStepTime()",
                     "SetTimeScale(double timeScale)", "SetMaxLogicFrame(int frame)")
    )
    next_frame = source[source.index("bool KX_KetsjiEngine::NextFrame()") :]
    accumulator = block(next_frame, "if (m_useFixedTimestep)")
    cpp = r'''
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include "CM_Clock.h"
#include "KX_CutsceneManager.h"
template<class... T> void KX_AnimLog(const char *, T...) {}
struct Inputs { void ClearInputs() {} void ReleaseMoveEvent() {} };
struct Messages { void ClearMessages() {} };
struct Pipeline { int calls = 0; void Update() { ++calls; } };
void process_audio_messages(Messages *, void *) {}
struct ClockProbe {
    CM_Clock m_clock;
    double m_average_framerate=0, m_tottime=1, m_timestep=0, m_ticrate=64;
    double m_framestep=0, m_timescale=1, m_deltaTime=0, m_physicsTime=0;
    double m_frameTime=0, m_logicTime=0, m_animationsTime=0;
    double m_accumulatorPreviousRealTime=0, m_simAccumulator=0;
    bool m_useFixedTimestep=true, m_needsAnimation=true;
    int m_maxLogicFrame=5;
    Inputs *m_inputDevice=nullptr;
    Messages messages;
    Messages *m_networkMessageManager=&messages;
    void *m_audioManager=nullptr;
    Pipeline pipeline;
    Pipeline *m_simulationPipeline=&pipeline;
    ClockProbe() { m_clock.SetManualTime(0); }
    METHODS
    int Step() {
        int steps=1;
        ACCUMULATOR
        return steps;
    }
};
static void require(bool ok) { if (!ok) std::exit(1); }
static bool near(double a, double b) { return std::abs(a-b)<1e-10; }
int main() {
    // Do not execute the undefined conversion in Step when the divisor is zero.
    ClockProbe zero;
    zero.SetTimeScale(0);
    zero.FrameTiming();
    double quotient=zero.m_simAccumulator/zero.m_framestep;
    require(!std::isfinite(quotient));
    std::cout << "pause divisor=" << zero.m_framestep
              << " quotient_finite=" << std::isfinite(quotient) << '\n';
    for (double scale : {0.5, 1.0, 2.0}) {
        ClockProbe p;
        p.SetTimeScale(scale);
        p.FrameTiming();
        double integrated=0;
        for (int i=1; i<=64; ++i) {
            p.m_clock.SetManualTime(i/64.0);
            integrated+=p.Step()*p.m_physicsTime;
        }
        require(p.pipeline.calls==64 && near(p.m_frameTime,1) && near(integrated,scale));
        std::cout << "scale=" << scale << " updates=" << p.pipeline.calls
                  << " clock=" << p.m_frameTime << " integrated_dt=" << integrated << '\n';
    }
    ClockProbe negative;
    negative.SetMaxLogicFrame(-1);
    negative.FrameTiming();
    negative.m_clock.SetManualTime(1.0/64);
    int steps=negative.Step();
    require(steps==-1 && negative.pipeline.calls==0 && negative.m_simAccumulator<0);
    std::cout << "negative_cap steps=" << steps << " updates=" << negative.pipeline.calls
              << " accumulator=" << negative.m_simAccumulator << '\n';
    // The cast occurs before the cap in the source; inspect range without casting.
    ClockProbe gap;
    gap.FrameTiming();
    double owed=1e8/gap.m_framestep;
    require(owed>std::numeric_limits<int>::max());
    std::cout << "large_gap owed=" << owed << " exceeds_int=1\n";
    // Use the real manager, but drive it as the pipeline does: global logic time,
    // no Update during suspension, then global time again when resuming.
    KX_CutsceneManager::Sequence seq{};
    KX_CutsceneManager::Event event{};
    event.m_time=2;
    event.m_type=0;
    seq.m_events.push_back(event);
    KX_CutsceneManager cutscene({seq});
    require(cutscene.Start(0) && cutscene.Update(1).empty());
    auto events=cutscene.Update(3);
    require(events.size()==1);
    std::cout << "cutscene_resume before=1 after=3 crossed_events=" << events.size() << '\n';
    // Exact suspension bookkeeping expressions; scene/action objects are not instantiated.
    for (double scale : {0.5,1.0,2.0}) {
        ClockProbe p;
        p.SetTimeScale(scale);
        p.FrameTiming();
        double suspended=0;
        for (int i=0; i<64; ++i) {
            p.AdvanceStepTime();
            suspended+=p.m_framestep;
        }
        double actionTime=p.m_animationsTime-suspended;
        require(near(actionTime,1-scale));
        std::cout << "suspension scale=" << scale << " action_clock_delta=" << actionTime << '\n';
    }
}
'''.replace("METHODS", methods).replace("ACCUMULATOR", accumulator)
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "revisao_relogio.cpp"
    target.write_text(cpp, encoding="utf-8")
    files = [ENGINE, ROOT / "source/source/gameengine/Common/CM_Clock.cpp",
             ROOT / "source/source/gameengine/Ketsji/KX_CutsceneManager.cpp",
             Path(__file__).resolve()]
    manifest = {"method": "extracted time bodies + real clock/cutscene manager; stub services",
                "product_integration_tested": False,
                "sources": [{"path": str(p.relative_to(ROOT)),
                             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                            for p in files]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
