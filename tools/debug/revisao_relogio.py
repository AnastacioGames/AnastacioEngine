"""Generate a console diagnostic from current engine time-method bodies.

Run with Python, then compile the generated .cpp with MSVC (vcvars64 +
VSLANG=1033), CM_Clock.cpp and KX_CutsceneManager.cpp. This isolates arithmetic;
it does not instantiate KX_KetsjiEngine or run the game. Invalid float-to-int
conversions are guarded by the engine source itself.
Exit zero means the corrected contract (CLK-01..05) holds.
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
struct Pipeline { int calls = 0; void Update(bool = true) { ++calls; } };
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
    void clearJoystickEvents() {}
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
    // CLK-01: zero time scale pauses without dividing by the zero step.
    ClockProbe zero;
    zero.SetTimeScale(0);
    zero.FrameTiming();
    zero.m_clock.SetManualTime(1.0);
    int zeroSteps=zero.Step();
    require(zeroSteps==0 && zero.pipeline.calls==0 && zero.m_frameTime==0);
    std::cout << "pause steps=" << zeroSteps << " updates=" << zero.pipeline.calls << '\n';
    // CLK-02: every game clock advances by the scaled step.
    for (double scale : {0.5, 1.0, 2.0}) {
        ClockProbe p;
        p.SetTimeScale(scale);
        p.FrameTiming();
        double integrated=0;
        for (int i=1; i<=64; ++i) {
            p.m_clock.SetManualTime(i/64.0);
            integrated+=p.Step()*p.m_physicsTime;
        }
        require(p.pipeline.calls==64 && near(p.m_frameTime,scale) && near(p.m_animationsTime,scale) &&
                near(integrated,scale));
        std::cout << "scale=" << scale << " updates=" << p.pipeline.calls
                  << " clock=" << p.m_frameTime << " integrated_dt=" << integrated << '\n';
    }
    // CLK-03: a negative cap is raised to one step.
    ClockProbe negative;
    negative.SetMaxLogicFrame(-1);
    negative.FrameTiming();
    negative.m_clock.SetManualTime(1.0/64);
    int steps=negative.Step();
    require(steps==1 && negative.pipeline.calls==1);
    std::cout << "negative_cap steps=" << steps << '\n';
    // A huge gap is capped before any conversion.
    ClockProbe gap;
    gap.FrameTiming();
    gap.m_clock.SetManualTime(1e8);
    steps=gap.Step();
    require(steps>=1 && steps<=gap.m_maxLogicFrame);
    std::cout << "large_gap steps=" << steps << '\n';
    // CLK-04: the cutscene counts only the steps it is given, from zero at Start().
    KX_CutsceneManager::Event event{};
    event.m_time=2;
    KX_CutsceneManager::Sequence seq{};
    seq.m_events.push_back(event);
    KX_CutsceneManager cutscene({seq});
    require(cutscene.Start(0) && cutscene.Advance(1).empty());
    // Suspension: no Advance() calls; the next step is still before the event.
    require(cutscene.Advance(0.5).empty() && cutscene.Advance(0.5).size()==1);
    std::cout << "cutscene_resume crossed_at=" << cutscene.GetTime() << '\n';
    // A wait freezes the timeline: events after it keep their spacing.
    KX_CutsceneManager::Sequence waits{};
    KX_CutsceneManager::Event wait{};
    wait.m_type=15;  // WAIT_TRIGGER
    KX_CutsceneManager::Event a{}, b{};
    a.m_time=1;
    b.m_time=2;
    waits.m_events={wait, a, b};
    KX_CutsceneManager trigger({waits});
    require(trigger.Start(0) && trigger.Advance(0.1).size()==1);
    trigger.StartWaitTrigger("go");
    require(trigger.Advance(10).empty() && trigger.ReleaseTrigger("go"));
    require(trigger.Advance(1).size()==1 && trigger.Advance(1).size()==1);
    std::cout << "wait_trigger events_spaced=1 timeline=" << trigger.GetTime()
              << " played=" << trigger.GetPlayTime() << '\n';
    waits.m_events[0].m_type=14;  // WAIT_TIME
    KX_CutsceneManager timed({waits});
    require(timed.Start(0) && timed.Advance(0.5).size()==1);
    // The wait was reached at played=0 (the step overshot it by 0.5), so the deadline is 2.0.
    require(timed.GetTime()==0.0 && timed.GetWaitStartPlayTime()==0.0);
    timed.StartWaitTime(timed.GetWaitStartPlayTime()+2);
    require(timed.Advance(1.5).empty() && timed.Advance(1).size()==1 && timed.GetTime()==1.0);
    require(timed.Advance(0.5).empty() && timed.Advance(0.5).size()==1);
    std::cout << "wait_time timeline=" << timed.GetTime() << " played=" << timed.GetPlayTime() << '\n';
    // An event right after a wait keeps its spacing even when one step crosses both.
    waits.m_events[0].m_type=15;
    waits.m_events[1].m_time=0.01;
    KX_CutsceneManager close({waits});
    require(close.Start(0) && close.Advance(0.5).size()==1);
    close.StartWaitTrigger("go");
    require(close.ReleaseTrigger("go") && close.Advance(0.005).empty() && close.Advance(0.005).size()==1);
    std::cout << "wait_spacing kept timeline=" << close.GetTime() << '\n';
    // Suspension bookkeeping: the action clock does not move across a suspension.
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
        require(near(actionTime,0));
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
