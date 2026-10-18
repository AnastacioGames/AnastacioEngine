# Builds the F2a test scene (Wait + Actuator sensor in Finished mode) and checks the RNA save/reopen.
# Run: AnastacioEngine.exe -b --factory-startup --python make_f2a_scene.py -- <out.blend>
import bpy, sys

out = sys.argv[sys.argv.index("--") + 1]

scene = bpy.context.scene
ob = scene.objects.active or bpy.data.objects[0]
scene.objects.active = ob
g = ob.game

LOG = """import bge
def log(cont):
    s = cont.sensors[0]
    if s.positive:
        ob = cont.owner
        key = "n_" + s.actuator
        ob[key] = ob.get(key, 0) + 1
        print("BRICKS2 finish", s.actuator, "t=%.3f" % bge.logic.getRealTime(), "count", ob[key])
"""
END = """import bge
def end(cont):
    if not cont.sensors[0].positive:
        return
    ob = cont.owner
    got = {k: ob.get("n_" + k, 0) for k in ("W1", "W0", "W2", "W3", "W4", "A1")}
    want = {"W1": 1, "W0": 1, "W2": 0, "W3": 0, "A1": 0}
    ok = all(got[k] == v for k, v in want.items()) and got["W4"] >= 2
    print("BRICKS2 result", got, "PASS" if ok else "FAIL")
    bge.logic.endGame()
"""
for name, body in (("f2a_log.py", LOG), ("f2a_end.py", END)):
    t = bpy.data.texts.new(name)
    t.write(body)

def add(kind, typ, name):
    getattr(bpy.ops.logic, kind + "_add")(type=typ, name=name, object=ob.name)
    return getattr(g, kind + "s")[name]

def chain(sens, act, state=1):
    c = add("controller", "LOGIC_AND", "c_" + act.name)
    c.states = state
    c.link(sensor=sens, actuator=act)
    return c

def finish_logger(act_name, state=1):
    s = add("sensor", "ACTUATOR", "f_" + act_name)
    s.actuator = act_name
    s.mode = 'FINISHED'
    c = add("controller", "PYTHON", "p_" + act_name)
    c.mode = 'MODULE'
    c.module = "f2a_log.log"
    c.states = state
    c.link(sensor=s)

start = add("sensor", "ALWAYS", "start")          # one positive pulse at the start

# W1: 0.5 s, finishes once
w = add("actuator", "WAIT", "W1"); w.duration = 0.5
chain(start, w); finish_logger("W1")
# W0: zero duration, finishes in the first tick
w = add("actuator", "WAIT", "W0"); w.duration = 0.0
chain(start, w); finish_logger("W0")
# W2: 1 s in state 2, the object leaves state 2 at 0.3 s: cancelled, no finish
w = add("actuator", "WAIT", "W2"); w.duration = 1.0
chain(start, w, state=2); finish_logger("W2")
leave = add("sensor", "DELAY", "leave"); leave.delay = 18      # ~0.3 s at 60 ticks
st = add("actuator", "STATE", "to1"); st.operation = 'REMOVE'; st.states = (False, True) + (False,) * 28
chain(leave, st)
# W3: restart on, pulse every tick: never finishes
pulse = add("sensor", "ALWAYS", "pulse"); pulse.use_pulse_true_level = True
w = add("actuator", "WAIT", "W3"); w.duration = 0.5; w.use_restart = True
chain(pulse, w); finish_logger("W3")
# W4: restart off, pulse every tick: the pulses are ignored while waiting, finishes every ~0.5 s
w = add("actuator", "WAIT", "W4"); w.duration = 0.5
chain(pulse, w); finish_logger("W4")
# A1: Action without action: failed, no finish
a = add("actuator", "ACTION", "A1")
chain(start, a); finish_logger("A1")
# end after 2 s
stop = add("sensor", "DELAY", "stop"); stop.delay = 120
c = add("controller", "PYTHON", "p_end"); c.mode = 'MODULE'; c.module = "f2a_end.end"; c.link(sensor=stop)

ob.game.states_initial = (True, True) + (False,) * 28
name = ob.name
bpy.ops.wm.save_as_mainfile(filepath=out)
bpy.ops.wm.open_mainfile(filepath=out)
g = bpy.data.objects[name].game
assert g.actuators["W1"].duration == 0.5 and g.actuators["W1"].type == 'WAIT'
assert g.actuators["W3"].use_restart and not g.actuators["W4"].use_restart
assert g.sensors["f_W1"].mode == 'FINISHED' and g.sensors["f_W1"].actuator == "W1"
assert g.sensors["start"].type == 'ALWAYS'
print("SCENE OK", out)
