"""Shared capture budget test (Track Tool P3): a road, straight then curved, with a chain of
probe_volume Empties. Saves cadeia_1.range (first box only) and cadeia_20.range in the folder given
after "--". The World color changes at 5 s and the game quits itself after 10 s. Run with RANGE_PROBE_VOLUME_LOG=1 and compare the faces
per second summed over the volumes and the mean frame time written to <file>_frames.txt.

  AnastacioEngine.exe -b -P criar_cena_probe_volume_cadeia.py -- <out_dir>
"""
import bpy
import math
import os
import sys
from mathutils import Vector

out_dir = sys.argv[sys.argv.index('--') + 1]
os.makedirs(out_dir, exist_ok=True)

QUIT = '''import bge, time
own = bge.logic.getCurrentController().owner
now = time.perf_counter()
if 't0' not in own:
    own['t0'] = own['last'] = now
    own['n'] = 0
    own['worst'] = 0.0
else:
    own['worst'] = max(own['worst'], now - own['last'])
    own['last'] = now
    own['n'] += 1
if now - own['t0'] > 5.0 and 'sky' not in own:
    # A World change wakes every grid: the case the shared budget is for.
    own['sky'] = True
    bge.logic.getCurrentScene().world.horizonColor = (0.9, 0.6, 0.4, 1.0)
if now - own['t0'] > 10.0:
    path = bge.logic.expandPath('//' + bge.logic.getCurrentScene().name + '_frames.txt')
    with open(path, 'w') as f:
        f.write('frames %d, mean %.2f ms, worst %.2f ms\\n' % (
            own['n'], 1000.0 * (now - own['t0']) / max(own['n'], 1), 1000.0 * own['worst']))
    bge.logic.endGame()
'''


def path_points(count):
    """Box centers every 20 m: half of them straight along X, then a 90 degree curve."""
    pts = []
    x, y, heading = 0.0, 0.0, 0.0
    for i in range(count):
        pts.append((x, y, heading))
        if i >= count // 2:
            heading += math.pi / 2.0 / (count - count // 2)
        x += 20.0 * math.cos(heading)
        y += 20.0 * math.sin(heading)
    return pts


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = color + (1,)
    p.inputs['Roughness'].default_value = 0.8
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(p.outputs[0], out.inputs['Surface'])
    return mat


def box(name, loc, size, rot, mat):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=(0, 0, rot))
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    ob.data.materials.append(mat)


def volume(n, loc):
    bpy.ops.object.add(type='EMPTY', location=loc)
    vol = bpy.context.object
    vol.name = 'PV_%03d' % n
    vol.empty_draw_type = 'CUBE'
    vol.scale = (12.0, 12.0, 3.0)
    for kind, name, value in (('FLOAT', 'probe_volume', 6.0), ('STRING', 'probe_volume_quality', 'medium')):
        bpy.ops.object.game_property_new(type=kind, name=name)
        vol.game.properties[name].value = value


def build(volumes):
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.name = 'cadeia_%d' % volumes
    gs = scene.game_settings
    gs.use_shading_nodes = True
    gs.resolution_x, gs.resolution_y = 960, 540
    gs.vsync = 'OFF'
    gs.use_frame_rate = False
    w = bpy.data.worlds.new('Sky')
    scene.world = w
    w.horizon_color = (0.5, 0.65, 0.9)
    w.zenith_color = (0.2, 0.35, 0.8)
    w.mist_settings.use_mist = False
    road = material('Road', (0.2, 0.2, 0.22))
    wall = material('Wall', (0.8, 0.25, 0.1))
    pts = path_points(20)
    for i, (x, y, h) in enumerate(pts):
        box('Road%d' % i, (x, y, -0.1), (11, 6, 0.1), h, road)
        side = Vector((-math.sin(h), math.cos(h), 0)) * 7.0
        box('Wall%d' % i, (x + side.x, y + side.y, 1), (9, 0.3, 1), h, wall)
    for n, (x, y, _h) in enumerate(pts[:volumes]):
        volume(n, (x, y, 2.0))
    bpy.ops.object.lamp_add(type='SUN', location=(0, -20, 30), rotation=(0.8, 0, 0.4))
    bpy.context.object.name = 'Sun'
    bpy.ops.object.camera_add(location=(-15, 0, 4))
    cam = bpy.context.object
    target = Vector((40, 0, 0))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    text = bpy.data.texts.new('quit.py')
    text.write(QUIT)
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
    cam.game.sensors[-1].use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
    cam.game.controllers[-1].text = text
    cam.game.controllers[-1].link(sensor=cam.game.sensors[-1])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'cadeia_%d.range' % volumes), check_existing=False)


for count in (1, 20):
    build(count)
