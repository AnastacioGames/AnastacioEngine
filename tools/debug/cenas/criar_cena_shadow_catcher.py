"""Cena com tres jeitos de fazer um chao que so mostra sombra (shadow catcher).

Cada layer tem um metodo, com seu proprio Sun (use_own_layer):
  layer 1: plano branco em blend Multiply; luz satura em branco, sombra escurece o fundo.
  layer 2: plano opaco com a cor do horizonte do world, ajustada pela luz do Sun.
  layer 3: Multiply + textura Blend esferica que clareia a borda (sem limite visivel).

Uso:
  AnastacioEngine.exe -b --factory-startup --python criar_cena_shadow_catcher.py -- saida.range
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

HORIZONTE = (0.55, 0.70, 0.90)
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.horizon_color = HORIZONTE
world.zenith_color = (0.15, 0.35, 0.75)
world.use_sky_blend = True
world.ambient_color = (0.0, 0.0, 0.0)
world.mist_settings.use_mist = False

SOL_ROT = (math.radians(35), 0.0, math.radians(30))
NDOTL = math.cos(math.radians(35))


def layers(n):
    return [i == n for i in range(20)]


def mat_cubo(nome, cor):
    m = bpy.data.materials.new(nome)
    m.diffuse_color = cor
    return m


def criar_layer(n, mat_chao, cor_cubos):
    sol_data = bpy.data.lamps.new("Sol_L%d" % (n + 1), 'SUN')
    sol_data.energy = 1.0
    sol_data.use_own_layer = True
    sol_data.shadow_method = 'RAY_SHADOW'
    sol_data.shadow_frustum_size = 25.0
    sol_data.shadow_buffer_size = 2048
    sol = bpy.data.objects.new("Sol_L%d" % (n + 1), sol_data)
    sol.location = (0, 0, 15)
    sol.rotation_euler = SOL_ROT
    scene.objects.link(sol)
    sol.layers = layers(n)

    bpy.ops.mesh.primitive_plane_add(radius=200.0, location=(0, 0, 0))
    chao = scene.objects.active
    chao.name = "Chao_L%d" % (n + 1)
    chao.data.materials.append(mat_chao)
    chao.layers = layers(n)

    m = mat_cubo("Cubo_L%d" % (n + 1), cor_cubos)
    for i, pos in enumerate([(-3, 0, 1), (1, 2, 1.5), (3, -2, 0.7)]):
        bpy.ops.mesh.primitive_cube_add(radius=pos[2], location=pos)
        c = scene.objects.active
        c.name = "Cubo_L%d_%d" % (n + 1, i)
        c.data.materials.append(m)
        c.layers = layers(n)


# Layer 1: Multiply. Emit 0.5 + luz saturam em branco (some no fundo); sombra fica 0.5.
m1 = bpy.data.materials.new("Catcher_Multiply")
m1.diffuse_color = (1, 1, 1)
m1.diffuse_intensity = 1.0
m1.specular_intensity = 0.0
m1.emit = 0.5
m1.use_transparency = True
m1.game_settings.alpha_blend = 'ALPHA_MULTIPLY'
criar_layer(0, m1, (0.8, 0.1, 0.1))

# Layer 2: opaco com cor do horizonte; diffuse compensado pelo NdotL do Sun.
m2 = bpy.data.materials.new("Catcher_CorHorizonte")
m2.diffuse_color = tuple(min(1.0, c / NDOTL) for c in HORIZONTE)
m2.diffuse_intensity = 1.0
m2.specular_intensity = 0.0
criar_layer(1, m2, (0.1, 0.6, 0.1))

# Layer 3: Multiply com borda esmaecida por textura Blend esferica (centro escuro -> borda branca).
m3 = bpy.data.materials.new("Catcher_MultiplyFade")
m3.diffuse_color = (1, 1, 1)
m3.specular_intensity = 0.0
m3.emit = 0.5
m3.use_transparency = True
m3.game_settings.alpha_blend = 'ALPHA_MULTIPLY'
tex = bpy.data.textures.new("FadeBorda", 'BLEND')
tex.progression = 'SPHERICAL'
tex.use_color_ramp = True
tex.color_ramp.elements[0].color = (1, 1, 1, 1)  # borda
tex.color_ramp.elements[1].color = (0, 0, 0, 1)  # centro
tex.color_ramp.elements[0].position = 0.0
tex.color_ramp.elements[1].position = 0.6
slot = m3.texture_slots.add()
slot.texture = tex
slot.texture_coords = 'ORCO'
slot.use_map_color_diffuse = False
slot.use_map_emit = True
slot.emit_factor = 1.0
slot.blend_type = 'ADD'
criar_layer(2, m3, (0.1, 0.2, 0.9))

# Layer 4: opcao nativa Shadows Only (material). Cor difusa = cor da sombra; precisa Alpha Blend.
m4 = bpy.data.materials.new("Catcher_ShadowsOnly")
m4.diffuse_color = (0.0, 0.0, 0.0)
m4.specular_intensity = 0.0
m4.use_only_shadow = True
m4.use_transparency = True
m4.alpha = 0.8
m4.use_cast_shadows = False
m4.game_settings.alpha_blend = 'ALPHA'
criar_layer(3, m4, (0.9, 0.7, 0.1))

# Camera baixa, visivel em todas as layers.
cam_data = bpy.data.cameras.new("Camera")
cam_data.type = 'PERSP'
cam_data.lens = 24
cam_data.clip_end = 1000.0
cam = bpy.data.objects.new("Camera", cam_data)
cam.location = (0, -14, 3)
cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
cam.layers = [i < 4 for i in range(20)]
scene.camera = cam

scene.layers = layers(0)
bpy.ops.wm.save_as_mainfile(filepath=saida)
print("SALVO", saida)
