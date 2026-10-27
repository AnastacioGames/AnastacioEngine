"""Generate a console diagnostic of input state and catch-up scheduling.

Selected method bodies come from current sources. EXP/Python, SDL hardware and
the simulation pipeline are replaced by small probes; this is not a game test.
Exit zero verifies INP-01/02/03 and ANI-01 scheduling with a replacement pipeline.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/revisao-input-catchup-20261026"
BASE = ROOT / "source/source/gameengine"
spec = importlib.util.spec_from_file_location("clock_review", Path(__file__).with_name("revisao_relogio.py"))
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
block = helper.block


def main():
    names = ["GameLogic/SCA_InputEvent.cpp", "Ketsji/KX_PythonJoystick.cpp",
             "Device/DEV_JoystickEvents.cpp", "Ketsji/KX_KetsjiEngine.cpp",
             "GameLogic/SCA_JoystickSensor.cpp"]
    texts = [(BASE / name).read_text(encoding="utf-8") for name in names]
    event, joystick, device, engine, sensor_source = texts
    event_methods = "\n".join(
        signature + " " + block(event, marker)
        for signature, marker in [
            ("SCA_InputEvent()", "SCA_InputEvent::SCA_InputEvent()"),
            ("void Clear()", "void SCA_InputEvent::Clear()"),
            ("bool Find(SCA_EnumInputs inputenum) const", "bool SCA_InputEvent::Find("),
            ("bool End(SCA_EnumInputs inputenum) const", "bool SCA_InputEvent::End("),
        ])
    cpp = r'''
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <vector>
#include "CM_Clock.h"
#include "DEV_JoystickDefines.h"
#define WITH_SDL
#define ATTR_FALLTHROUGH [[fallthrough]]
#define CM_LogicBrickError(...) std::abort()
constexpr int SDL_CONTROLLER_AXIS_MAX=6, SDL_CONTROLLER_BUTTON_MAX=15;
struct SDL_Event {};
struct SCA_InputEvent {
    enum SCA_EnumInputs { NONE=0, JUSTACTIVATED, ACTIVE, JUSTRELEASED };
    std::vector<SCA_EnumInputs> m_status, m_queue;
    std::vector<int> m_values;
    unsigned m_unicode;
    EVENT_METHODS
};
struct DEV_Joystick {
    bool down=false;
    int button=0;
    int axis=0;
    static DEV_Joystick *m_instance[JOYINDEX_MAX];
    static void ClearEvents() CLEAR_DEVICE
    int m_istrig_axis=0, m_istrig_button=0;
    int m_live_axis[6]={};
    bool m_live_button[32]={};
    struct Private { void *m_gamecontroller; } storage{this};
    Private *m_private=&storage;
    bool HasVirtualPad() { return false; }
    int GetAxisPosition(int i) { return i==0 ? axis : 0; }
    bool aButtonPressIsPositive(int i) { return i==button && down; }
    bool IsTrigAxis() { return m_istrig_axis; }
    bool IsTrigButton() { return m_istrig_button; }
    void cSetPrecision(int) {}
    bool aAxisPairIsPositive(int) { return axis!=0; }
    bool aAxisPairDirectionIsPositive(int, int) { return axis!=0; }
    bool aAxisIsPositive(int) { return axis!=0; }
    bool aAnyButtonPressIsPositive() { return down; }
    void OnNothing(SDL_Event *sdl_event) NOTHING
    void SyncLiveState() SYNC
};
DEV_Joystick *DEV_Joystick::m_instance[JOYINDEX_MAX]={};
struct SCA_JoystickManager {
    DEV_Joystick *device;
    DEV_Joystick *GetJoystickDevice(int) { return device; }
};
struct SCA_JoystickSensor {
    enum { KX_JOYSENSORMODE_AXIS, KX_JOYSENSORMODE_SHOULDER_TRIGGER,
           KX_JOYSENSORMODE_AXIS_SINGLE, KX_JOYSENSORMODE_BUTTON };
    void *m_eventmgr;
    int m_joyindex=0, m_axis=1, m_axisf=0, m_precision=3200, m_button=0;
    int m_joymode=KX_JOYSENSORMODE_BUTTON;
    bool m_reset=false, m_level=false, m_bAllEvents=false;
    int m_istrig=0, m_istrig_prev=0;
    bool Evaluate() EVALUATE
};
struct KX_PythonJoystick {
    enum { BEGINJOYSTICK=0, ENDJOYSTICK=16, MAX_BUTTONS=17 };
    DEV_Joystick *m_joystick;
    SCA_InputEvent m_joystickInputsTable[MAX_BUTTONS];
    explicit KX_PythonJoystick(DEV_Joystick *p):m_joystick(p) {}
    void UpdateJoystickEvents() JOYSTICK
    void ClearJoystickEvents() CLEAR_PYTHON
};
KX_PythonJoystick *published[JOYINDEX_MAX]={};
void *getPythonJoystick(int i) { return published[i]; }
template<class... T> void KX_AnimLog(const char *, T...) {}
struct Inputs { void ClearInputs() {} void ReleaseMoveEvent() {} };
struct Messages { void ClearMessages() {} };
void process_audio_messages(Messages *, void *) {}
struct Pipeline {
    bool *needsAnimation;
    SCA_InputEvent *input=nullptr;
    int calls=0, activatedReads=0, releasedReads=0, secondSceneReads=0, poseEpoch=0, deformCalls=0;
    std::vector<int> physicsPoseEpochs;
    void Update(bool deformAnimations=true) {
        ++calls;
        if (input && input->Find(SCA_InputEvent::JUSTACTIVATED)) ++activatedReads;
        if (input && input->Find(SCA_InputEvent::JUSTRELEASED)) ++releasedReads;
        // A second scene reads the same state before the pipeline returns.
        if (input && input->Find(SCA_InputEvent::JUSTACTIVATED)) ++secondSceneReads;
        if (*needsAnimation) poseEpoch=calls;
        if (*needsAnimation && deformAnimations) ++deformCalls;
        physicsPoseEpochs.push_back(poseEpoch);
    }
};
struct CatchupProbe {
    CM_Clock m_clock;
    double m_accumulatorPreviousRealTime=0, m_simAccumulator=0;
    double m_timescale=1, m_framestep=1.0/64, m_timestep=1.0/64, m_deltatime=1.0/64;
    double m_frameTime=0, m_logicTime=0, m_animationsTime=0;
    bool m_useFixedTimestep=true, m_needsAnimation=true;
    int m_maxLogicFrame=5;
    Inputs *m_inputDevice=nullptr;
    Messages messages;
    Messages *m_networkMessageManager=&messages;
    void *m_audioManager=nullptr;
    Pipeline pipeline{&m_needsAnimation};
    Pipeline *m_simulationPipeline=&pipeline;
    void AdvanceStepTime() ADVANCE
    int Step() { CAPTURE int steps=1; ACCUMULATOR return steps; }
    void VariableStep() { CAPTURE VARIABLE }
};
static void require(bool ok) { if (!ok) std::exit(1); }
int main() {
    DEV_Joystick dev;
    KX_PythonJoystick joy(&dev);
    auto &e=joy.m_joystickInputsTable[1];
    dev.down=true;
    joy.UpdateJoystickEvents();
    require(e.Find(SCA_InputEvent::JUSTACTIVATED));
    joy.ClearJoystickEvents();
    dev.down=false;
    joy.UpdateJoystickEvents();
    require(e.m_status.size()==1 && e.End(SCA_InputEvent::NONE)
            && e.Find(SCA_InputEvent::NONE) && e.Find(SCA_InputEvent::JUSTRELEASED));
    std::cout << "release status_size=" << e.m_status.size()
              << " released=" << e.Find(SCA_InputEvent::JUSTRELEASED) << '\n';
    joy.ClearJoystickEvents();
    joy.UpdateJoystickEvents();
    require(e.End(SCA_InputEvent::NONE) && e.m_queue.empty());

    // Exercise every published button, including immediate release/repress.
    for (int button=0; button<JOYBUT_MAX; ++button) {
        DEV_Joystick hardware;
        KX_PythonJoystick pad(&hardware);
        // The hardware probe selects one physical button at a time.
        hardware.button=button;
        auto &input=pad.m_joystickInputsTable[button+1];
        auto check=[&](bool down, SCA_InputEvent::SCA_EnumInputs edge) {
            hardware.down=down;
            pad.UpdateJoystickEvents();
            require(input.m_status.size()==1 && input.m_values.size()==1);
            require(input.End(down ? SCA_InputEvent::ACTIVE : SCA_InputEvent::NONE));
            require(input.Find(SCA_InputEvent::NONE)==!down);
            require(input.m_queue.size()==(edge==SCA_InputEvent::NONE ? 0 : 1));
            if (edge!=SCA_InputEvent::NONE) require(input.End(edge));
            for (int other=0; other<JOYBUT_MAX; ++other)
                if (other!=button) require(pad.m_joystickInputsTable[other+1].End(SCA_InputEvent::NONE));
            pad.ClearJoystickEvents();
        };
        check(false,SCA_InputEvent::NONE);
        check(true,SCA_InputEvent::JUSTACTIVATED);
        check(true,SCA_InputEvent::NONE);
        check(false,SCA_InputEvent::JUSTRELEASED);
        for (int repeat=0; repeat<100; ++repeat) {
            check(true,SCA_InputEvent::JUSTACTIVATED);
            check(false,SCA_InputEvent::JUSTRELEASED);
        }
        input.Clear();
        require(input.End(SCA_InputEvent::NONE) && input.m_queue.empty());
        check(false,SCA_InputEvent::NONE);
    }
    std::cout << "INP-01 regression: all buttons, hold/release/repress and 100 cycles passed\n";

    // Capture precedes logic; consume once after all scenes of each step.
    CatchupProbe batch;
    batch.pipeline.input=&e;
    published[0]=&joy;
    DEV_Joystick::m_instance[0]=&dev;
    batch.m_clock.SetManualTime(4.0/64);
    dev.down=true;
    require(batch.Step()==4 && batch.pipeline.activatedReads==1
            && batch.pipeline.secondSceneReads==1);
    std::cout << "catchup steps=" << batch.pipeline.calls
              << " activated_reads=" << batch.pipeline.activatedReads << '\n';
    std::cout << "animation_gate physics_pose_epochs=";
    for (int epoch:batch.pipeline.physicsPoseEpochs) std::cout << epoch << ',';
    std::cout << '\n';
    require(batch.pipeline.physicsPoseEpochs==std::vector<int>({1,2,3,4}));
    require(batch.pipeline.deformCalls==1);
    CatchupProbe gated;
    gated.m_needsAnimation=false;
    gated.m_clock.SetManualTime(4.0/64);
    require(gated.Step()==4 && gated.pipeline.deformCalls==0);
    require(gated.pipeline.physicsPoseEpochs==std::vector<int>({0,0,0,0}));
    std::cout << "ANI-01 scheduling: poses every eligible step, one deform pass, global gate preserved\n";

    // Release and repress across captures that owe zero steps remain queued.
    CatchupProbe noStep;
    noStep.pipeline.input=&e;
    noStep.m_clock.SetManualTime(0);
    dev.down=false;
    require(noStep.Step()==0);
    dev.down=true;
    for (int i=0; i<20; ++i) require(noStep.Step()==0);
    require(e.Find(SCA_InputEvent::JUSTACTIVATED) && e.Find(SCA_InputEvent::JUSTRELEASED));
    require(e.m_queue==std::vector<SCA_InputEvent::SCA_EnumInputs>(
            {SCA_InputEvent::JUSTRELEASED,SCA_InputEvent::JUSTACTIVATED}));
    std::cout << "zero_step python_activated=" << e.Find(SCA_InputEvent::JUSTACTIVATED)
              << " physical_down=" << dev.down << '\n';
    noStep.m_clock.SetManualTime(4.0/64);
    require(noStep.Step()==4 && noStep.pipeline.activatedReads==1
            && noStep.pipeline.releasedReads==1 && noStep.pipeline.secondSceneReads==1);
    require(e.m_queue.empty() && e.End(SCA_InputEvent::ACTIVE));
    noStep.m_clock.SetManualTime(5.0/64);
    require(noStep.Step()==1 && noStep.pipeline.calls==5
            && noStep.pipeline.activatedReads==1 && noStep.pipeline.releasedReads==1);
    // The variable timestep path consumes the same way, including releases.
    CatchupProbe variable;
    variable.pipeline.input=&e;
    dev.down=false;
    variable.VariableStep();
    require(variable.pipeline.releasedReads==1 && e.m_queue.empty());
    variable.VariableStep();
    require(variable.pipeline.releasedReads==1);

    // HandleEvents no longer resets flags; real Evaluate observes both scenes.
    DEV_Joystick sensor;
    DEV_Joystick::m_instance[0]=&sensor;
    SCA_JoystickManager manager{&sensor};
    SCA_JoystickSensor sceneA{&manager}, sceneB{&manager};
    sensor.down=true;
    sensor.SyncLiveState();
    require(sensor.m_istrig_button==1);
    // No simulation consumes that change during twenty further captures.
    for (int i=0; i<20; ++i) sensor.SyncLiveState();
    require(sensor.m_istrig_button==1 && sensor.aButtonPressIsPositive(0));
    std::cout << "zero_step sensor_trigger=" << sensor.m_istrig_button
              << " physical_down=" << sensor.aButtonPressIsPositive(0) << '\n';
    require(sceneA.Evaluate() && sceneB.Evaluate());
    DEV_Joystick::ClearEvents();
    require(!sceneA.Evaluate() && !sceneB.Evaluate());
    sensor.down=false;
    for (int i=0; i<20; ++i) sensor.SyncLiveState();
    require(sceneA.Evaluate() && sceneB.Evaluate());
    require(!sceneA.m_istrig && !sceneB.m_istrig);
    DEV_Joystick::ClearEvents();
    // Exercise single axis state, using actual SyncLiveState and Evaluate.
    sceneA.m_joymode=sceneB.m_joymode=SCA_JoystickSensor::KX_JOYSENSORMODE_AXIS_SINGLE;
    sensor.axis=16000;
    for (int i=0; i<20; ++i) sensor.SyncLiveState();
    require(sceneA.Evaluate() && sceneB.Evaluate());
    DEV_Joystick::ClearEvents();
    require(!sceneA.Evaluate() && !sceneB.Evaluate());
    sensor.axis=0;
    for (int i=0; i<20; ++i) sensor.SyncLiveState();
    require(sceneA.Evaluate() && sceneB.Evaluate());
    DEV_Joystick::ClearEvents();
    require(!sensor.m_istrig_axis && !sensor.m_istrig_button);
    std::cout << "INP-02/03 regression: zero/one/four/variable steps, two scenes, button and axis passed\n";

    // Control: keyboard-style Clear preserves held state but consumes the edge.
    SCA_InputEvent key;
    key.m_status.push_back(SCA_InputEvent::ACTIVE);
    key.m_queue.push_back(SCA_InputEvent::JUSTACTIVATED);
    key.Clear();
    require(key.End(SCA_InputEvent::ACTIVE) && !key.Find(SCA_InputEvent::JUSTACTIVATED));
    std::cout << "keyboard_control active=1 activated=0\n";
}
'''
    replacements = {
        "EVENT_METHODS": event_methods,
        "NOTHING": block(device, "void DEV_Joystick::OnNothing("),
        "SYNC": block(device, "void DEV_Joystick::SyncLiveState("),
        "JOYSTICK": block(joystick, "void KX_PythonJoystick::UpdateJoystickEvents("),
        "CLEAR_PYTHON": block(joystick, "void KX_PythonJoystick::ClearJoystickEvents("),
        "CLEAR_DEVICE": block(device, "void DEV_Joystick::ClearEvents("),
        "EVALUATE": block(sensor_source, "bool SCA_JoystickSensor::Evaluate("),
        "CAPTURE": engine[engine.index("// Capture button transitions"):engine.index("// for each scene, call the proceed functions")],
        "VARIABLE": block(engine, "else {\n\t\tm_simulationPipeline->Update();"),
        "ADVANCE": block(engine, "void KX_KetsjiEngine::AdvanceStepTime("),
        "ACCUMULATOR": block(engine[engine.index("bool KX_KetsjiEngine::NextFrame()") :],
                             "if (m_useFixedTimestep)"),
    }
    handle_events = block(device, "bool DEV_Joystick::HandleEvents(")
    assert "OnNothing(" not in handle_events, "Capture must not consume pending sensor flags"
    for marker, body in replacements.items():
        cpp = re.sub(r"\b" + marker + r"\b", lambda match: body, cpp)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "revisao_input_catchup.cpp").write_text(cpp, encoding="utf-8")
    files = [BASE / name for name in names] + [
        BASE / "Common/CM_Clock.cpp", BASE / "Device/DEV_JoystickDefines.h",
        BASE / "GameLogic/SCA_InputEvent.h", BASE / "Ketsji/KX_PythonJoystick.h",
        BASE / "Device/DEV_Joystick.h", BASE / "GameLogic/SCA_JoystickSensor.h",
        Path(__file__).resolve(), Path(helper.__file__).resolve()]
    manifest = {
        "method": "extracted input methods and accumulator; fake hardware and pipeline",
        "product_integration_tested": False,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                        text=True).strip(),
        "sources": [{"path": str(p.relative_to(ROOT)),
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
