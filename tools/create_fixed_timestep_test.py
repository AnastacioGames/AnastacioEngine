"""Fixed Timestep (Plano 8) runtime test scene.

Run with:  RangeEngine -b --python tools/create_fixed_timestep_test.py -- <output.range>
Then:      RangeRuntime -g fixed_timestep = 1 <output.range>   (and "= 0" for the legacy loop)

Logic tic rate is 60; a pre_draw callback sleeps FT_SLEEP seconds (env var, default 0.040, so the
display runs at ~25 fps; FT_SLEEP=0 runs unthrottled). steps_per_draw is a histogram {steps: draws}.
After 3 s of real time the probe prints

  FIXED_TIMESTEP_TEST steps=<n> game_time=<s> real=<s> fall=<m> expected_fall=<m> msgs=<n> draws=<n>

With the fixed timestep, steps ~ 180, game_time ~ real and the cube's free fall matches
0.5*g*t^2 (no slow motion). The legacy loop gives ~1 step per drawn frame (slow motion).
msgs counts how many steps saw the one message sent on step 10; it must be 1.
The line is also written to fixed_timestep_result.txt next to the .range.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "fixed_timestep_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.fps = 60
scene.game_settings.sleep_timer = 5
scene.game_settings.physics_gravity = 9.8

PROBE = '''
import bge
import os
import time

SLEEP = float(os.environ.get("FT_SLEEP", "0.040"))

state = {"steps": 0, "draws": 0, "per_draw": {}, "last_draw_steps": 0, "msgs": 0, "t0": None, "z0": None, "g0": None, "done": False}

def slow_draw():
    state["draws"] += 1
    n = state["steps"] - state["last_draw_steps"]
    state["last_draw_steps"] = state["steps"]
    state["per_draw"][n] = state["per_draw"].get(n, 0) + 1
    if SLEEP > 0.0:
        time.sleep(SLEEP)

def main(cont):
    own = cont.owner
    scene = bge.logic.getCurrentScene()
    if state["t0"] is None:
        scene.pre_draw.append(slow_draw)
        state["t0"] = time.perf_counter()
        state["g0"] = bge.logic.getFrameTime()
        state["z0"] = scene.objects["FallCube"].worldPosition.z
    state["steps"] += 1
    if state["steps"] == 10:
        bge.logic.sendMessage("ping")
    if cont.sensors["ping"].positive:
        state["msgs"] += 1

    real = time.perf_counter() - state["t0"]
    if real >= 3.0 and not state["done"]:
        state["done"] = True
        game = bge.logic.getFrameTime() - state["g0"]
        fall = state["z0"] - scene.objects["FallCube"].worldPosition.z
        line = ("FIXED_TIMESTEP_TEST steps=%d game_time=%.3f real=%.3f fall=%.2f expected_fall=%.2f "
                "msgs=%d draws=%d steps_per_draw=%s" % (state["steps"], game, real, fall, 0.5 * 9.8 * game * game,
                                     state["msgs"], state["draws"], sorted(state["per_draw"].items())))
        print(line)
        with open(bge.logic.expandPath("//fixed_timestep_result.txt"), "a") as handle:
            handle.write(line + "\\n")
        bge.logic.endGame()
'''

# Free-falling rigid body, far from anything it could hit.
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 200))
cube = bpy.context.object
cube.name = "FallCube"
cube.game.physics_type = 'RIGID_BODY'
cube.game.damping = 0.0

bpy.ops.object.add(type='EMPTY', location=(0, 0, 0))
probe = bpy.context.object
probe.name = "StepProbe"
text = bpy.data.texts.new("step_probe.py")
text.write(PROBE)
bpy.ops.logic.sensor_add(type='ALWAYS', object=probe.name)
bpy.ops.logic.sensor_add(type='MESSAGE', object=probe.name)
bpy.ops.logic.controller_add(type='PYTHON', object=probe.name)
always = probe.game.sensors[0]
always.use_pulse_true_level = True
ping = probe.game.sensors[1]
ping.name = "ping"
ping.subject = "ping"
controller = probe.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = "step_probe.main"
always.link(controller)
ping.link(controller)

bpy.ops.object.camera_add(location=(0, -30, 200), rotation=(1.5708, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
