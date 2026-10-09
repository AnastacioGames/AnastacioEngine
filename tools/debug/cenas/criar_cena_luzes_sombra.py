# Cria uma cena de teste para o contador lightUniforms (GP1/GP2/RA1 em docs/auditoria-suspeitos.md):
# 40 cubos vermelhos + chao com Principled BSDF (o unico shader com unfshadowmap/unflightsource), 3 spots com
# sombra em buffer e a camera girando em volta.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_luzes_sombra.py -- saida.range
import bpy
import sys
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
# Sem isso o Principled cai nos nos antigos e o material fica sem shader (nada aparece).
scene.game_settings.use_shading_nodes = True


def principled(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    for n in list(nodes):
        nodes.remove(n)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = color
    out_node = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs[0], out_node.inputs[0])
    return mat


mat = principled('chao', (0.8, 0.8, 0.8, 1.0))
# Cubos vermelhos e altos, para destacar do chao e projetar sombras compridas.
mat_cubo = principled('cubo', (0.8, 0.1, 0.05, 1.0))

# Posicao explicita: sem ela o plano nasce no cursor 3D, que na cena padrao fica acima dos cubos.
bpy.ops.mesh.primitive_plane_add(radius=20, location=(0, 0, 0))
scene.objects.active.data.materials.append(mat)
for i in range(40):
    bpy.ops.mesh.primitive_cube_add(radius=0.6, location=((i % 8) * 3 - 10.5, (i // 8) * 3 - 6, 1.2))
    cubo = scene.objects.active
    cubo.scale = (1, 1, 2)
    cubo.data.materials.append(mat_cubo)

for i, loc in enumerate(((-14, -10, 10), (14, -10, 10), (0, 14, 10))):
    lamp = bpy.data.lamps.new('spot%d' % i, 'SPOT')
    lamp.use_shadow = True
    lamp.shadow_method = 'BUFFER_SHADOW'
    lamp.spot_size = 1.6
    # Energia baixa: com 3 spots inclinados o Principled estoura para branco.
    lamp.energy = 0.4
    ob = bpy.data.objects.new(lamp.name, lamp)
    ob.location = loc
    scene.objects.link(ob)
    # Spots inclinados para o centro: as sombras saem de lado e aparecem na camera.
    ob.rotation_euler = (-Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

pivot = bpy.data.objects.new('pivot', None)
scene.objects.link(pivot)
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -30, 20)
# Aponta para o centro dos cubos.
cam.rotation_euler = (-Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
cam.parent = pivot
scene.objects.link(cam)
scene.camera = cam

# Pivo gira devagar (Always -> Motion), para medir com a camera em movimento.
scene.objects.active = pivot
bpy.ops.logic.sensor_add(type='ALWAYS', name='always', object='pivot')
bpy.ops.logic.controller_add(type='LOGIC_AND', name='and', object='pivot')
bpy.ops.logic.actuator_add(type='MOTION', name='spin', object='pivot')
pivot.game.sensors['always'].link(pivot.game.controllers['and'])
pivot.game.actuators['spin'].link(pivot.game.controllers['and'])
pivot.game.actuators['spin'].offset_rotation = (0, 0, 0.01)

bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print('CENA salva', out)
