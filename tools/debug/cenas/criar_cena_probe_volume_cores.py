"""Probe Volume GI showcase: a gallery with red, blue and yellow walls, colored pillars and white
sculptures in the middle (white shows the bounced color best), lit by a warm sun through two windows.
Saves galeria_off.range and galeria_medium.range in the folder given after "--". Stays open.

  AnastacioEngine.exe -b -P criar_cena_probe_volume_cores.py -- <out_dir>
"""
import bpy
import os
import sys

out_dir = sys.argv[sys.argv.index('--') + 1]
os.makedirs(out_dir, exist_ok=True)

MATS = {}


def material(name, color, rough=0.7):
    if name not in MATS:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        p = nt.nodes.new('ShaderNodeBsdfPrincipled')
        p.inputs['Base Color'].default_value = color + (1,)
        p.inputs['Roughness'].default_value = rough
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(p.outputs[0], out.inputs['Surface'])
        MATS[name] = mat
    return MATS[name]


WHITE = ('White', (0.85, 0.85, 0.85))


def add(kind, name, loc, size, mat=WHITE, rot=(0, 0, 0)):
    if kind == 'cube':
        bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    elif kind == 'sphere':
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=loc)
        bpy.ops.object.shade_smooth()
    else:
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, location=loc, rotation=rot)
        bpy.ops.object.shade_smooth()
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    ob.data.materials.append(material(*mat))
    return ob


def build(quality):
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.name = 'galeria_%s' % (quality.lower() if quality else 'off')
    gs = scene.game_settings
    gs.use_shading_nodes = True
    gs.resolution_x, gs.resolution_y = 1280, 720
    gs.vsync = 'OFF'
    MATS.clear()
    w = bpy.data.worlds.new('Sky')
    scene.world = w
    w.horizon_color = (0.55, 0.7, 0.95)
    w.zenith_color = (0.25, 0.4, 0.85)
    w.light_settings.use_environment_light = True
    w.light_settings.environment_energy = 0.6

    # Room 16 x 12 x 5 m.
    add('cube', 'Floor', (0, 0, -0.1), (8, 6, 0.1), ('Floor', (0.7, 0.68, 0.65)))
    add('cube', 'Ceiling', (0, 0, 5.1), (8, 6, 0.1))
    add('cube', 'WallW', (-8, 0, 2.5), (0.1, 6, 2.5), ('Red', (0.85, 0.08, 0.06)))
    add('cube', 'WallE', (8, 0, 2.5), (0.1, 6, 2.5), ('Blue', (0.05, 0.2, 0.85)))
    add('cube', 'WallN', (0, 6, 2.5), (8, 0.1, 2.5), ('Yellow', (0.95, 0.75, 0.05)))
    # South wall with two windows (2 m wide, 1 to 4 m high).
    for i, (x, sx) in enumerate(((-6.5, 1.5), (0, 3), (6.5, 1.5))):
        add('cube', 'WallS%d' % i, (x, -6, 2.5), (sx, 0.1, 2.5))
    for i, x in enumerate((-4, 4)):
        add('cube', 'Sill%d' % i, (x, -6, 0.5), (1, 0.1, 0.5))
        add('cube', 'Lintel%d' % i, (x, -6, 4.5), (1, 0.1, 0.5))

    # Colored pillars along the walls.
    pillars = (((-5.5, 4), ('Orange', (1.0, 0.35, 0.02))), ((-2, 4.5), ('Green', (0.1, 0.75, 0.15))),
               ((2, 4.5), ('Purple', (0.5, 0.08, 0.8))), ((5.5, 4), ('Cyan', (0.02, 0.75, 0.8))))
    for i, ((x, y), mat) in enumerate(pillars):
        add('cyl', 'Pillar%d' % i, (x, y, 2.5), (0.5, 0.5, 2.5), mat)
    # A big red rug and a blue bench, so the floor color bounces up.
    add('cube', 'Rug', (-3, -1, 0.02), (2.2, 1.6, 0.02), ('Red', (0.85, 0.08, 0.06)))
    add('cube', 'Bench', (4.5, -1.5, 0.3), (1.4, 0.4, 0.3), ('Blue', (0.05, 0.2, 0.85)))

    # White sculptures in the middle: spheres on plinths and a column.
    add('cube', 'Plinth0', (-3, -1, 0.5), (0.5, 0.5, 0.5))
    add('sphere', 'Ball0', (-3, -1, 1.6), (0.6, 0.6, 0.6))
    add('cube', 'Plinth1', (0.5, 1, 0.4), (0.6, 0.6, 0.4))
    add('sphere', 'Ball1', (0.5, 1, 1.8), (1.0, 1.0, 1.0))
    add('cyl', 'Column', (3.5, 2, 1.2), (0.35, 0.35, 1.2))
    add('cube', 'Block', (-6, -3.5, 0.6), (0.6, 0.6, 0.6), rot=(0, 0, 0.6))
    add('sphere', 'Ball2', (6.5, -3.5, 0.7), (0.7, 0.7, 0.7))

    # Warm low sun through the windows, onto the floor and the yellow wall.
    bpy.ops.object.lamp_add(type='SUN', location=(0, -20, 10), rotation=(1.05, 0, -0.25))
    sun = bpy.context.object
    sun.data.color = (1.0, 0.85, 0.65)
    sun.data.energy = 1.6
    sun.data.shadow_method = 'RAY_SHADOW'

    bpy.ops.object.camera_add(location=(7.2, -5.4, 2.6), rotation=(1.38, 0, 0.82))
    cam = bpy.context.object
    cam.data.lens = 22
    scene.camera = cam

    bpy.ops.object.add(type='EMPTY', location=(0, 0, 2.5))
    vol = bpy.context.object
    vol.name = 'ProbeVolume'
    vol.empty_draw_type = 'CUBE'
    vol.scale = (8.0, 6.0, 2.5)
    if quality is not None:
        bpy.ops.object.game_property_new(type='FLOAT', name='probe_volume')
        vol.game.properties['probe_volume'].value = 2.0
        bpy.ops.object.game_property_new(type='STRING', name='probe_volume_quality')
        vol.game.properties['probe_volume_quality'].value = quality

    name = 'galeria_%s.range' % (quality.lower() if quality else 'off')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, name), check_existing=False)


for q in (None, 'Medium'):
    build(q)
