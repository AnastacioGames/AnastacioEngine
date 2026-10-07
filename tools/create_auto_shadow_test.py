"""Auto Shadow Update (Spot/Point) runtime test scene.

Run with:  RangeEngine -b --python tools/create_auto_shadow_test.py -- <output.range>
Then:      RangeRuntime <output.range>            (AUTO_SHADOW=0 turns auto off; AUTO_SHADOW_KEEP=1 keeps it open)

8 Point lamps with shadows over a field of static cubes; one cube spins under lamp 0 only.
After 2 s of warm-up the probe measures 8 s and prints

  AUTO_SHADOW_TEST auto=<0|1> fps=<n> shadowPasses=<min..max> lightsShadowUpdated=<min..max>

With auto on, only lamp 0 redraws (6 passes per frame); with it off all 8 redraw (48).
The line is also appended to auto_shadow_result.txt next to the .range.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "auto_shadow_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_frame_rate = False
scene.game_settings.vsync = 'OFF'

PROBE = '''
import bge
import os
import time

AUTO = os.environ.get("AUTO_SHADOW", "1") != "0"
KEEP = os.environ.get("AUTO_SHADOW_KEEP", "0") != "0"
state = {"t0": None, "frames": 0, "passes": [], "updated": [], "done": False}

def main(cont):
    scene = bge.logic.getCurrentScene()
    if state["t0"] is None:
        for light in scene.lights:
            light.autoShadowUpdate = AUTO
        state["t0"] = time.perf_counter()
    scene.objects["Spinner"].applyRotation((0, 0, 0.05), True)
    real = time.perf_counter() - state["t0"]
    if real < 2.0:
        return
    if state["frames"] == 0:
        state["t1"] = time.perf_counter()
    state["frames"] += 1
    stats = bge.logic.getRenderStats()
    state["passes"].append(stats["shadowPasses"])
    state["updated"].append(stats["lightsShadowUpdated"])
    if real >= 10.0 and not state["done"]:
        state["done"] = True
        fps = state["frames"] / (time.perf_counter() - state["t1"])
        line = ("AUTO_SHADOW_TEST auto=%d fps=%.1f shadowPasses=%d..%d lightsShadowUpdated=%d..%d" %
                (AUTO, fps, min(state["passes"]), max(state["passes"]), min(state["updated"]), max(state["updated"])))
        print(line)
        with open(bge.logic.expandPath("//auto_shadow_result.txt"), "a") as handle:
            handle.write(line + "\\n")
        if not KEEP:
            bge.logic.endGame()
'''

bpy.ops.mesh.primitive_plane_add(radius=60, location=(0, 0, 0))
for x in range(-10, 11):
    for y in range(-10, 11):
        bpy.ops.mesh.primitive_cube_add(radius=0.5, location=(x * 5, y * 5, 0.5))

bpy.ops.mesh.primitive_cube_add(radius=0.8, location=(-15, -15, 2.0))
bpy.context.object.name = "Spinner"

for i in range(8):
    x = -15 + (i % 4) * 10
    y = -15 + (i // 4) * 30
    bpy.ops.object.lamp_add(type='POINT', location=(x, y, 6))
    lamp = bpy.context.object.data
    lamp.distance = 12
    lamp.use_shadow = True

bpy.ops.object.add(type='EMPTY', location=(0, 0, 0))
probe = bpy.context.object
probe.name = "Probe"
text = bpy.data.texts.new("shadow_probe.py")
text.write(PROBE)
bpy.ops.logic.sensor_add(type='ALWAYS', object=probe.name)
bpy.ops.logic.controller_add(type='PYTHON', object=probe.name)
always = probe.game.sensors[0]
always.use_pulse_true_level = True
controller = probe.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = "shadow_probe.main"
always.link(controller)

bpy.ops.object.camera_add(location=(0, -55, 45), rotation=(0.9, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
