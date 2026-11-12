"""Acceptance scene for Bake Probes (window test) and for the iGPU test.

Six rooms 200 m apart (beyond the 120 m live-capture range), each with a colored wall, an opening
in the ceiling and its own Light Probe Volume. Saves probe_bake_aceite.range in the folder given
after "--".

In the game: WASD walks, mouse-free Q/E turn, 1-6 jump to a room, Esc quits.
What to look for: the floor next to the colored wall takes that color (bounced light). After
Bake Probes, every room is lit when you jump to it, with no capture "settling".

  AnastacioEngine.exe -b -P criar_cena_probe_bake_aceite.py -- <out_dir>
"""
import bpy
import math
import os
import sys
from mathutils import Vector

out_dir = sys.argv[sys.argv.index('--') + 1]
os.makedirs(out_dir, exist_ok=True)

SPACING = 200.0
COLORS = [('Red', (0.8, 0.05, 0.05)), ('Green', (0.05, 0.7, 0.1)), ('Blue', (0.05, 0.15, 0.85)),
          ('Yellow', (0.85, 0.75, 0.05)), ('Magenta', (0.75, 0.05, 0.7)), ('Cyan', (0.05, 0.7, 0.75))]

MOVE = '''import bge, math
from mathutils import Vector
own = bge.logic.getCurrentController().owner
kb = bge.logic.keyboard.inputs
ev = bge.events
def down(k):
    return kb[k].active or kb[k].activated
dt = 1.0 / max(bge.logic.getAverageFrameRate(), 1.0)
for i, k in enumerate((ev.ONEKEY, ev.TWOKEY, ev.THREEKEY, ev.FOURKEY, ev.FIVEKEY, ev.SIXKEY)):
    if kb[k].activated:
        own.worldPosition = (i * %(sp)f - 7.0, -7.0, 1.7)
        own['yaw'] = math.radians(45.0)
        print('room', i + 1)
yaw = own.get('yaw', math.radians(45.0))
if down(ev.QKEY): yaw += 1.5 * dt
if down(ev.EKEY): yaw -= 1.5 * dt
own['yaw'] = yaw
fwd = Vector((math.cos(yaw), math.sin(yaw), 0.0))
left = Vector((-fwd.y, fwd.x, 0.0))
step = Vector()
if down(ev.WKEY): step += fwd
if down(ev.SKEY): step -= fwd
if down(ev.AKEY): step += left
if down(ev.DKEY): step -= left
own.worldPosition += step * 5.0 * dt
own.worldOrientation = Vector((math.cos(yaw), math.sin(yaw), -0.15)).to_track_quat('-Z', 'Y').to_matrix()
''' % {'sp': SPACING}


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


def box(name, loc, size, mat):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    ob.data.materials.append(mat)


def room(i, white, tint):
    x0 = i * SPACING
    box('Floor%d' % i, (x0, 0, -0.1), (10, 10, 0.1), white)
    box('WallColor%d' % i, (x0, 10, 3), (10, 0.2, 3), tint)
    box('WallBack%d' % i, (x0, -10, 3), (10, 0.2, 3), white)
    box('WallL%d' % i, (x0 - 10, 0, 3), (0.2, 10, 3), white)
    box('WallR%d' % i, (x0 + 10, 0, 3), (0.2, 10, 3), white)
    # Ceiling with an opening so the sun reaches the colored wall side of the floor.
    box('CeilA%d' % i, (x0, -5, 6.1), (10, 5, 0.1), white)
    box('CeilB%d' % i, (x0 - 6, 5, 6.1), (4, 5, 0.1), white)
    box('Block%d' % i, (x0 + 4, -4, 0.75), (0.75, 0.75, 0.75), white)
    bpy.ops.object.add(type='EMPTY', location=(x0, 0, 3))
    vol = bpy.context.object
    vol.name = 'PV_Room%d' % (i + 1)
    vol.empty_draw_type = 'CUBE'
    vol.scale = (10.0, 10.0, 3.0)
    for kind, name, value in (('FLOAT', 'probe_volume', 4.0), ('STRING', 'probe_volume_quality', 'medium')):
        bpy.ops.object.game_property_new(type=kind, name=name)
        vol.game.properties[name].value = value


bpy.ops.wm.read_homefile(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.name = 'probe_bake_aceite'
gs = scene.game_settings
gs.use_shading_nodes = True
gs.resolution_x, gs.resolution_y = 1280, 720
w = bpy.data.worlds.new('Sky')
scene.world = w
w.horizon_color = (0.5, 0.65, 0.9)
w.zenith_color = (0.2, 0.35, 0.8)
w.mist_settings.use_mist = False
white = material('White', (0.75, 0.75, 0.75))
for i, (name, color) in enumerate(COLORS):
    room(i, white, material(name, color))
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 40), rotation=(math.radians(35), 0, math.radians(180)))
sun = bpy.context.object
sun.name = 'Sun'
sun.data.energy = 1.0
bpy.ops.object.camera_add(location=(-7, -7, 1.7))
cam = bpy.context.object
cam.name = 'Player'
cam.rotation_euler = (Vector((1, 1, -0.15))).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam
text = bpy.data.texts.new('move.py')
text.write(MOVE)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
cam.game.sensors[-1].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
cam.game.controllers[-1].text = text
cam.game.controllers[-1].link(sensor=cam.game.sensors[-1])
bpy.ops.object.select_all(action='DESELECT')
scene.objects.active = bpy.data.objects['PV_Room1']
bpy.data.objects['PV_Room1'].select = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'probe_bake_aceite.range'), check_existing=False)
print('saved', os.path.join(out_dir, 'probe_bake_aceite.range'))
