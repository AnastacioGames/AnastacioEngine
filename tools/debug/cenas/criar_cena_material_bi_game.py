"""Opcoes de material do Blender Internal ligadas no modo Game, uma por layer.

  layer 1: Fresnel na transparencia (esfera esq. sem, dir. com Fresnel 2 / Blend 1.25).
  layer 2: Z Offset (dois decais coplanares ao chao; esq. sem offset pisca, dir. com 0.5 nao).
  layer 3: Shadow Casting Alpha (cubos: esq. 1.0, meio 0.5, dir. 0.2).

Uso:
  AnastacioEngine.exe -b --factory-startup --python criar_cena_material_bi_game.py -- saida.range
"""
import math
import sys

import bpy
from mathutils import Vector

saida = sys.argv[sys.argv.index("--") + 1]
scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
    bpy.data.objects.remove(ob)
scene.render.engine = 'BLENDER_GAME'

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.horizon_color = (0.55, 0.65, 0.8)
world.mist_settings.use_mist = False


def layers(n):
    return [i == n for i in range(20)]


def mat(nome, cor):
    m = bpy.data.materials.new(nome)
    m.diffuse_color = cor
    return m


def linkar(ob, m, n):
    ob.data.materials.append(m)
    ob.layers = layers(n)


def base(n):
    sd = bpy.data.lamps.new("Sol_L%d" % (n + 1), 'SUN')
    sd.use_own_layer = True
    sd.shadow_method = 'RAY_SHADOW'
    sd.shadow_frustum_size = 20.0
    sd.shadow_buffer_size = 2048
    sd.shadow_buffer_soft = 3.0
    sd.shadow_buffer_samples = 8
    sol = bpy.data.objects.new(sd.name, sd)
    sol.location = (0, 0, 15)
    sol.rotation_euler = (math.radians(35), 0, math.radians(30))
    scene.objects.link(sol)
    sol.layers = layers(n)
    bpy.ops.mesh.primitive_plane_add(radius=15, location=(0, 0, 0))
    linkar(scene.objects.active, mat("Chao_L%d" % (n + 1), (0.8, 0.8, 0.75)), n)


# Layer 1: Fresnel
base(0)
for x, fres in ((-2.5, 0.0), (2.5, 2.0)):
    bpy.ops.mesh.primitive_uv_sphere_add(size=1.8, segments=48, ring_count=24, location=(x, 0, 2))
    bpy.ops.object.shade_smooth()
    m = mat("Vidro_Fresnel_%g" % fres, (0.2, 0.6, 1.0))
    m.use_transparency = True
    m.alpha = 1.0 if fres else 0.3
    m.raytrace_transparency.fresnel = fres
    m.raytrace_transparency.fresnel_factor = 1.25
    m.game_settings.alpha_blend = 'ALPHA_SORT'
    linkar(scene.objects.active, m, 0)
# objeto atras para ver a transparencia
m_fundo = mat("Fundo_L1", (0.9, 0.2, 0.1))
for x in (-2.5, 2.5):
    bpy.ops.mesh.primitive_cube_add(radius=1.0, location=(x, 4, 2))
    linkar(scene.objects.active, m_fundo, 0)

# Layer 2: Z Offset (decal exatamente no plano do chao)
base(1)
for x, z in ((-3, 0.0), (3, 0.5)):
    bpy.ops.mesh.primitive_plane_add(radius=2.0, location=(x, 0, 0))
    m = mat("Decal_Z%g" % z, (0.9, 0.1, 0.1) if z == 0 else (0.1, 0.8, 0.2))
    m.offset_z = z
    linkar(scene.objects.active, m, 1)

# Layer 3: Shadow Casting Alpha
base(2)
for x, a in ((-4, 1.0), (0, 0.5), (4, 0.2)):
    bpy.ops.mesh.primitive_cube_add(radius=1.0, location=(x, 0, 2.5))
    m = mat("Sombra_Alpha_%g" % a, (0.9, 0.7, 0.1))
    m.shadow_cast_alpha = a
    linkar(scene.objects.active, m, 2)

cd = bpy.data.cameras.new("Camera")
cd.lens = 20
cam = bpy.data.objects.new("Camera", cd)
cam.location = (0, -13, 7)
cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
cam.layers = [i < 3 for i in range(20)]
scene.camera = cam

scene.layers = layers(0)
bpy.ops.wm.save_as_mainfile(filepath=saida)
print("SALVO", saida)
