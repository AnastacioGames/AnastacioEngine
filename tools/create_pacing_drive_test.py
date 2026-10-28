"""Frame pacing test with a player-like object driving and turning on a plane.

Run with:  AnastacioEngine -b --python tools/create_pacing_drive_test.py -- <output.range>
Then:      AnastacioRuntime -g fixed_timestep = 1 <output.range>   (used by tools/timing_drive_ab.py)

A dynamic box sits on a static plane. Every logic step it gets forward velocity (8 m/s) and a turn
(1.5 rad/s), so it drives in circles under friction and gravity, like a player. A pre_draw callback
sleeps FT_SLEEP and records the box position at each drawn frame. After FT_SECONDS it writes

  DRIVE_TEST game=<s> real=<s> dist=<m> expected=<m> radius=<m> step_cv=<%> step_max=<x> z_dev=<m>

dist/expected ~1.0 means no slow motion; radius should stay ~8/1.5 = 5.33 m in every mode.
step_cv is the variation of how far the box moves between drawn frames (visible stutter, lower is
better) and step_max is the biggest jump relative to the mean. Appended to drive_result.txt.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "pacing_drive_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.fps = int(__import__("os").environ.get("FT_FPS", "60"))
scene.game_settings.physics_gravity = 9.8

PROBE = '''
import bge
import math
import os
import statistics
import time

SLEEP = float(os.environ.get("FT_SLEEP", "0.004"))
SPEED = 8.0
TURN = 1.5
st = {"t0": None, "g0": None, "draw_pos": [], "dist": 0.0, "last": None, "z": [], "center": None, "done": False}

def on_draw():
    car = bge.logic.getCurrentScene().objects["Car"]
    st["draw_pos"].append(car.worldPosition.copy())
    if SLEEP > 0.0:
        time.sleep(SLEEP)

def main(cont):
    car = cont.owner
    scene = bge.logic.getCurrentScene()
    if st["t0"] is None:
        scene.pre_draw.append(on_draw)
        st["t0"] = time.perf_counter()
        st["g0"] = bge.logic.getFrameTime()
    car.setLinearVelocity((0.0, SPEED, car.getLinearVelocity(True).z), True)
    car.setAngularVelocity((0.0, 0.0, TURN), True)
    p = car.worldPosition.copy()
    if st["last"] is not None:
        st["dist"] += (p.xy - st["last"].xy).length
    st["last"] = p
    st["z"].append(p.z)

    real = time.perf_counter() - st["t0"]
    if real < float(os.environ.get("FT_SECONDS", "10")) or st["done"]:
        return
    st["done"] = True
    game = bge.logic.getFrameTime() - st["g0"]
    pts = st["draw_pos"][30:]
    steps = [(b.xy - a.xy).length for a, b in zip(pts, pts[1:])]
    mean = statistics.mean(steps)
    cx = statistics.mean(q.x for q in pts)
    cy = statistics.mean(q.y for q in pts)
    radius = statistics.mean(math.hypot(q.x - cx, q.y - cy) for q in pts)
    lap = int(len(pts) * (2.0 * math.pi / TURN) / real)
    first, last = pts[:lap], pts[-lap:]
    drift = math.hypot(statistics.mean(q.x for q in first) - statistics.mean(q.x for q in last),
                       statistics.mean(q.y for q in first) - statistics.mean(q.y for q in last))
    line = ("DRIVE_TEST game=%.3f real=%.3f dist=%.2f expected=%.2f radius=%.2f step_cv=%.1f step_max=%.2f z_dev=%.4f drift=%.3f"
            % (game, real, st["dist"], SPEED * game, radius, 100.0 * statistics.pstdev(steps) / mean,
               max(steps) / mean, statistics.pstdev(st["z"][30:]), drift))
    print(line)
    with open(bge.logic.expandPath("//drive_result.txt"), "a") as handle:
        handle.write(line + "\\n")
    bge.logic.endGame()
'''

bpy.ops.mesh.primitive_plane_add(radius=50, location=(0, 0, 0))
bpy.context.object.name = "Ground"

bpy.ops.mesh.primitive_cube_add(radius=0.5, location=(0, 0, 0.5))
car = bpy.context.object
car.name = "Car"
car.game.physics_type = 'DYNAMIC'
car.game.use_actor = True

text = bpy.data.texts.new("drive_probe.py")
text.write(PROBE)
bpy.ops.logic.sensor_add(type='ALWAYS', object=car.name)
bpy.ops.logic.controller_add(type='PYTHON', object=car.name)
always = car.game.sensors[0]
always.use_pulse_true_level = True
controller = car.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = "drive_probe.main"
always.link(controller)

bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 20))
bpy.ops.object.camera_add(location=(0, -25, 25), rotation=(0.785, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
