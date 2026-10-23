# Vila de casas para testar o HLOD (Game > Performance > Build HLOD).
#   AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_hlod.py -- saida.range [hlod] [lado]
# Sem "hlod": cena crua. Com "hlod": roda o gerador (celula 40 m, distancia 80 m, ratio 0.25).
# lado = casas por lado da grade (padrao 24 -> 576 casas). Cada casa ~1.5k triangulos, malha propria.
import math
import random
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if not argv:
    raise SystemExit('uso: ... -- saida.range [hlod] [lado]')
out = argv[0]
use_hlod = 'hlod' in argv[1:]
side = next((int(a) for a in argv[1:] if a.isdigit()), 24)
SPACING = 9.0

scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_frame_rate = False
scene.game_settings.physics_engine = 'BULLET'


def material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgb
    return mat


wall = material('Parede', (0.45, 0.28, 0.15))
roof = material('Telhado', (0.12, 0.08, 0.07))
sand = material('Areia', (0.75, 0.68, 0.5))

# Casa base: corpo subdividido + telhado piramidal, dois materiais.
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1.5))
body = scene.objects.active
body.scale = (2.0, 3.0, 1.5)
body.data.materials.append(wall)
mod = body.modifiers.new('sub', 'SUBSURF')
mod.subdivision_type = 'SIMPLE'
mod.levels = 3
bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=4.0, depth=2.0, location=(0, 0, 4.0),
                                rotation=(0, 0, math.pi / 4))
top = scene.objects.active
top.scale = (0.75, 1.1, 1.0)
top.data.materials.append(roof)
mod = top.modifiers.new('sub', 'SUBSURF')
mod.subdivision_type = 'SIMPLE'
mod.levels = 3
for ob in (body, top):
    scene.objects.active = ob
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.modifier_apply(modifier='sub')
body.select = top.select = True
scene.objects.active = body
bpy.ops.object.join()
house_mesh = body.data
house_mesh.name = 'Casa'
bpy.data.objects.remove(body, do_unlink=True)

rnd = random.Random(7)
half = (side - 1) * SPACING * 0.5
for i in range(side):
    for j in range(side):
        ob = bpy.data.objects.new('Casa_%02d_%02d' % (i, j), house_mesh.copy())
        ob.location = (i * SPACING - half + rnd.uniform(-2, 2), j * SPACING - half + rnd.uniform(-2, 2), 0)
        ob.rotation_euler.z = rnd.uniform(0, math.tau)
        ob.game.physics_type = 'STATIC'
        scene.objects.link(ob)

bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0), radius=half + 60)
ground = scene.objects.active
ground.name = 'Chao'
ground.data.materials.append(sand)

bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 50), rotation=(math.radians(50), 0, math.radians(30)))
world = bpy.data.worlds.new('Ceu')
world.horizon_color = (0.55, 0.7, 0.9)
world.mist_settings.use_mist = False
scene.world = world

cam_data = bpy.data.cameras.new('Camera')
cam_data.type = 'PERSP'
cam_data.lens = 24
cam_data.clip_end = 2000
camera = bpy.data.objects.new('Camera', cam_data)
scene.objects.link(camera)
camera.location = (-half - 10, -half - 10, 12)
camera.rotation_euler = (Vector((half * 0.3, half * 0.3, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera

for ob in scene.objects:
    ob.select = False
if use_hlod:
    from bl_operators import anastacio_hlod
    houses = [ob for ob in scene.objects if ob.name.startswith('Casa_')]
    proxies, skipped = anastacio_hlod.build(scene, houses, cell_size=40.0, distance=80.0, ratio=0.25)
    print('HLOD proxies', len(proxies), 'skipped', len(skipped))

bpy.ops.wm.save_as_mainfile(filepath=out)
