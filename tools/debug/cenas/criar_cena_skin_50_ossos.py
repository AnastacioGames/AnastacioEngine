"""Cena de teste: GPU Skinning com 50 ossos (acima do limite de 24 do celular).

    AnastacioEngine -b --factory-startup --python tools/debug/cenas/criar_cena_skin_50_ossos.py -- saida.range

Uma coluna de 50 blocos empilhados, cada bloco preso ao seu osso, com material "GPU Skinning" e
armature em "RanGE GPU Skinning". Um script entorta a coluna como cobra (cada osso gira um pouco,
com fase diferente). No PC (limite 64) roda na placa de vídeo; num celular com 256 vetores de
uniform (limite 24) deve cair para skinning na CPU com aviso no console e a imagem ser a mesma.
Sem animação ("andar" = False) a pose é fixa em t = 20, para comparar prints entre aparelhos.
"""

import sys

import bmesh
import bpy

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "skin_50_ossos.range"
N = 50
ALT = 0.2

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_auto_static_batch = False
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.horizon_color = (0.25, 0.3, 0.35)


def material(nome, cor, skin):
    mat = bpy.data.materials.new(nome)
    mat.diffuse_color = cor
    mat.use_shadeless = True
    mat.use_gpu_skinning = skin
    return mat


# chão
me = bpy.data.meshes.new("Chao")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=10.0)
bm.to_mesh(me)
bm.free()
me.materials.append(material("Chao", (0.15, 0.15, 0.15), False))
chao = bpy.data.objects.new("Chao", me)
scene.objects.link(chao)
chao.game.physics_type = 'NO_COLLISION'

# coluna: um bloco por osso, cores alternadas
me = bpy.data.meshes.new("Coluna")
bm = bmesh.new()
blocos = []
for i in range(N):
    geo = bmesh.ops.create_cube(bm, size=1.0)
    for v in geo["verts"]:
        v.co.x *= 0.5
        v.co.y *= 0.5
        v.co.z = (v.co.z + 0.5) * ALT + i * ALT
    for f in {f for v in geo["verts"] for f in v.link_faces}:
        f.material_index = i % 2
    blocos.append([v.index for v in geo["verts"]])
bm.verts.index_update()
blocos = [[v.index for v in bm.verts[i * 8:(i + 1) * 8]] for i in range(N)]
bm.to_mesh(me)
bm.free()
me.materials.append(material("Laranja", (1.0, 0.5, 0.1), True))
me.materials.append(material("Azul", (0.1, 0.4, 1.0), True))
coluna = bpy.data.objects.new("Coluna", me)
scene.objects.link(coluna)
coluna.game.physics_type = 'NO_COLLISION'

arm_data = bpy.data.armatures.new("Cobra")
arm_data.deform_method = 'BGE_GPU'
arm = bpy.data.objects.new("Cobra", arm_data)
scene.objects.link(arm)
arm.game.physics_type = 'NO_COLLISION'
scene.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
anterior = None
for i in range(N):
    b = arm_data.edit_bones.new("O%02d" % i)
    b.head = (0.0, 0.0, i * ALT)
    b.tail = (0.0, 0.0, (i + 1) * ALT)
    if anterior:
        b.parent = anterior
        b.use_connect = True
    anterior = b
bpy.ops.object.mode_set(mode='OBJECT')

for i in range(N):
    g = coluna.vertex_groups.new("O%02d" % i)
    g.add(blocos[i], 1.0, 'REPLACE')
mod = coluna.modifiers.new("Armature", 'ARMATURE')
mod.object = arm
coluna.parent = arm

cam_data = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_data)
scene.objects.link(cam)
cam.location = (0.0, -16.0, 5.0)
cam.rotation_euler = (1.5708, 0.0, 0.0)
scene.camera = cam

NL = chr(10)
texto = bpy.data.texts.new("cobra.py")
texto.write(NL.join([
    "import math",
    "from Range import logic",
    "from mathutils import Quaternion",
    "own = logic.getCurrentController().owner",
    "if own['andar']:",
    "    own['t'] += 1.0",
    "t = own['t'] if own['andar'] else 20.0",
    "for i in range(%d):" % N,
    "    ch = own.channels['O%02d' % i]",
    "    a = 0.12 * math.sin(t * 0.08 + i * 0.35)",
    "    ch.rotation_mode = 0",  # quaternion
    "    ch.rotation_quaternion = Quaternion((0.0, 0.0, 1.0), a)",
    "own.update()",
    "",
]))
scene.objects.active = arm
bpy.ops.object.game_property_new(type='BOOL', name="andar")
arm.game.properties["andar"].value = False
bpy.ops.object.game_property_new(type='FLOAT', name="t")
bpy.ops.logic.sensor_add(type='ALWAYS', object=arm.name)
bpy.ops.logic.controller_add(type='PYTHON', object=arm.name)
sens = arm.game.sensors[-1]
sens.use_pulse_true_level = True
ctrl = arm.game.controllers[-1]
ctrl.text = texto
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=out)
print("CENA", out)
