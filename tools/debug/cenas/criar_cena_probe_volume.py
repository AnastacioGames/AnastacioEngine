"""Probe Volume GI (F1a) test scene: a closed room with a window, a sun, scattered static boxes,
one dynamic box and an Empty-box "probe_volume". Saves one .range per quality (off/low/med/high)
in the folder given after "--". The game quits itself after 10 s.

  AnastacioEngine.exe -b -P criar_cena_probe_volume.py -- <out_dir>
"""
import bpy
import os
import random
import sys

out_dir = sys.argv[sys.argv.index('--') + 1]
os.makedirs(out_dir, exist_ok=True)

QUIT = '''import bge, time
own = bge.logic.getCurrentController().owner
if 't0' not in own:
    own['t0'] = time.perf_counter()
elif time.perf_counter() - own['t0'] > 10.0:
    bge.logic.endGame()
'''


def box(name, loc, size, dynamic=False):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    if dynamic:
        ob.game.physics_type = 'RIGID_BODY'
    return ob


def build(quality):
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    random.seed(1)

    box('Floor', (0, 0, -0.1), (10, 10, 0.1))
    box('Ceiling', (0, 0, 4.1), (10, 10, 0.1))
    box('WallN', (0, 10, 2), (10, 0.1, 2))
    box('WallE', (10, 0, 2), (0.1, 10, 2))
    box('WallW', (-10, 0, 2), (0.1, 10, 2))
    # South wall with a window gap in the middle.
    box('WallS1', (-6, -10, 2), (4, 0.1, 2))
    box('WallS2', (6, -10, 2), (4, 0.1, 2))
    for i in range(150):
        box('Prop%d' % i, (random.uniform(-9, 9), random.uniform(-9, 9), 0.4), (0.4, 0.4, 0.4))
    box('Dynamic', (0, 0, 3), (0.5, 0.5, 0.5), dynamic=True)

    bpy.ops.object.lamp_add(type='SUN', location=(0, -20, 10), rotation=(1.0, 0, 0))
    bpy.ops.object.camera_add(location=(0, -8, 2), rotation=(1.5, 0, 0))
    cam = bpy.context.object
    scene.camera = cam

    bpy.ops.object.add(type='EMPTY', location=(0, 0, 2))
    vol = bpy.context.object
    vol.name = 'ProbeVolume'
    vol.empty_draw_type = 'CUBE'
    vol.scale = (10, 10, 2)
    if quality is not None:
        bpy.ops.object.game_property_new(type='FLOAT', name='probe_volume')
        vol.game.properties['probe_volume'].value = 0.0
        bpy.ops.object.game_property_new(type='STRING', name='probe_volume_quality')
        vol.game.properties['probe_volume_quality'].value = quality

    # Quit timer on the camera.
    text = bpy.data.texts.new('quit.py')
    text.write(QUIT)
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
    cam.game.sensors[-1].use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
    cam.game.controllers[-1].text = text
    cam.game.controllers[-1].link(sensor=cam.game.sensors[-1])

    name = 'probe_volume_%s.range' % (quality.lower() if quality else 'off')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, name), check_existing=False)


for q in (None, 'Low', 'Medium', 'High'):
    build(q)
