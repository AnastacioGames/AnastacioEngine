"""Fullscreen toggle test scene (render.setFullScreen / Fullscreen do Display).

Run with:  RangeEngine -b --python tools/create_fullscreen_test.py -- <output.range> [fs]
Then:      RangeRuntime <output.range>

The scene toggles render.setFullScreen(True/False) at fixed frames, logs the window state to
<output.range>.log and quits after ~6 s. With "fs" the file also starts with Fullscreen enabled
in Render > Game > Display. A crash shows up as a log that stops before "quit".
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "fullscreen_test.range"
start_fullscreen = "fs" in argv[1:]

bpy.ops.wm.read_factory_settings()
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.show_fullscreen = start_fullscreen
scene.game_settings.resolution_x = 800
scene.game_settings.resolution_y = 600

script = bpy.data.texts.new("fs_test.py")
script.write('''import bge
from bge import logic, render

STEPS = {30: True, 90: False, 150: True, 240: False}

def state(tag):
    path = logic.expandPath("//") + "fullscreen_test.log"
    with open(path, "a") as f:
        f.write("%s frame=%d full=%s size=%dx%d\\n" % (tag, logic.fs_frame, render.getFullScreen(),
                render.getWindowWidth(), render.getWindowHeight()))

def main():
    if not hasattr(logic, "fs_frame"):
        logic.fs_frame = 0
        state("start")
    logic.fs_frame += 1
    f = logic.fs_frame
    if f in STEPS:
        state("before set(%s)" % STEPS[f])
        render.setFullScreen(STEPS[f])
    elif f - 5 in STEPS:
        state("after")
    elif f == 330:
        state("quit")
        logic.endGame()

main()
''')

cube = scene.objects.get("Cube")
sens = cube.game.sensors
bpy.context.scene.objects.active = cube
bpy.ops.logic.sensor_add(type='ALWAYS', object=cube.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cube.name)
s = cube.game.sensors[-1]
s.use_pulse_true_level = True
c = cube.game.controllers[-1]
c.text = script
s.link(c)

bpy.ops.wm.save_as_mainfile(filepath=output)
