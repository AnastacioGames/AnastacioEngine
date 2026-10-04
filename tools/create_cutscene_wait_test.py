"""Cutscene Wait Trigger runtime test scene.

Run with:  RangeEngine -b --python tools/create_cutscene_wait_test.py -- <output.range>
Then:      RangeRuntime <output.range>        (xvfb-run -a RangeRuntime ... sem display)

Three sequences share the layout  Spawn TplA @0.1 > Wait Trigger "go" @0.2 > Spawn TplB @0.3:
  0: released by scene.release_cutscene_trigger("go") (a wrong name must not release it)
  1: released by a message whose subject is "go"
  2: "go" released BEFORE the wait starts (latched), so the sequence is never blocked
Each phase ends with stop_cutscene(), which must remove the spawned objects.
Prints  CUTSCENE_WAIT_TEST PASS|FAIL ...  and writes it to wait_result.txt next to the .range.
The game quits after the check.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "cutscene_wait_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.fps = 60

PROBE = '''
import bge

TICK = 1.0 / 60.0
failures = []

def count(scene, name):
    return len([o for o in scene.objects if o.name == name])

def expect(label, value, wanted):
    if value != wanted:
        failures.append("%s=%r(want %r)" % (label, value, wanted))

def main(cont):
    own = cont.owner
    scene = bge.logic.getCurrentScene()
    own["frame"] = own.get("frame", 0) + 1
    f = own["frame"]

    # Phase 0: Python release.
    if f == 2:
        scene.play_cutscene(0)
    elif f == 40:
        expect("py.A", count(scene, "TplA"), 1)
        expect("py.B_blocked", count(scene, "TplB"), 0)
        expect("py.wrong_name", scene.release_cutscene_trigger("other"), False)
    elif f == 55:
        expect("py.B_still_blocked", count(scene, "TplB"), 0)
        expect("py.release", scene.release_cutscene_trigger("go"), True)
    elif f == 80:
        expect("py.B_released", count(scene, "TplB"), 1)
        scene.stop_cutscene()
    elif f == 85:
        expect("py.stop_clears", count(scene, "TplA") + count(scene, "TplB"), 0)

    # Phase 1: message release.
    elif f == 90:
        scene.play_cutscene(1)
    elif f == 130:
        expect("msg.A", count(scene, "TplA"), 1)
        expect("msg.B_blocked", count(scene, "TplB"), 0)
        bge.logic.sendMessage("go")
    elif f == 150:
        expect("msg.B_released", count(scene, "TplB"), 1)
        scene.stop_cutscene()
    elif f == 155:
        expect("msg.stop_clears", count(scene, "TplA") + count(scene, "TplB"), 0)

    # Phase 2: trigger released before the wait begins.
    elif f == 160:
        scene.play_cutscene(2)
        expect("latch.early", scene.release_cutscene_trigger("go"), False)
    elif f == 220:
        expect("latch.A", count(scene, "TplA"), 1)
        expect("latch.B_not_blocked", count(scene, "TplB"), 1)
        scene.stop_cutscene()

    # Phase 3: restart does not inherit the previous wait.
    elif f == 225:
        scene.play_cutscene(0)
    elif f == 260:
        expect("restart.blocked", count(scene, "TplB"), 0)
        scene.restart_cutscene()
    elif f == 275:
        expect("restart.replay_A", count(scene, "TplA"), 1)
        expect("restart.blocked_again", count(scene, "TplB"), 0)
        scene.stop_cutscene()

    elif f == 285:
        line = "CUTSCENE_WAIT_TEST " + ("PASS" if not failures else "FAIL " + " ".join(failures))
        print(line)
        with open(bge.logic.expandPath("//wait_result.txt"), "w") as handle:
            handle.write(line + "\\n")
        bge.logic.endGame()
'''


def add_empty(name, location, layer):
    obj = bpy.data.objects.new(name, None)
    scene.objects.link(obj)
    obj.location = location
    obj.layers = [i == layer for i in range(20)]
    return obj


tpl_a = add_empty("TplA", (0, 0, 0), 1)       # templates live on the inactive layer 2
tpl_b = add_empty("TplB", (1, 0, 0), 1)
point = add_empty("SpawnPoint", (0, 0, 1), 0)

for index in range(3):
    bpy.ops.cutscene.sequence_add()
    sequence = scene.cutscene_settings.sequences[index]
    sequence.name = "Wait test %d" % index
    layout = (("SPAWN_OBJECT", 0.1, tpl_a), ("WAIT_TRIGGER", 0.2, None), ("SPAWN_OBJECT", 0.3, tpl_b))
    for event_index, (kind, time, template) in enumerate(layout):
        bpy.ops.cutscene.event_add(sequence_index=index)
        event = sequence.events[event_index]
        event.type = kind
        event.time = time
        event.name = "%s %d" % (kind, event_index)
        if template:
            event.template_object = template
            event.spawn_point = point
        else:
            event.trigger_name = "go"

# Probe: script running every frame.
bpy.ops.object.add(type='EMPTY', location=(0, 0, 5))
probe = bpy.context.object
probe.name = "WaitProbe"
text = bpy.data.texts.new("wait_probe.py")
text.write(PROBE)
bpy.ops.logic.sensor_add(type='ALWAYS', object=probe.name)
bpy.ops.logic.controller_add(type='PYTHON', object=probe.name)
sensor = probe.game.sensors[-1]
sensor.use_pulse_true_level = True
controller = probe.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = "wait_probe.main"
sensor.link(controller)

bpy.ops.object.camera_add(location=(0, -6, 4), rotation=(1.05, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
