# Cria uma cena de teste para o contador lightUniforms (GP1/GP2/RA1 em docs/auditoria-suspeitos.md):
# 40 cubos + chao com Principled BSDF (o unico shader com unfshadowmap/unflightsource), 3 spots com
# sombra em buffer e a camera girando em volta.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_luzes_sombra.py -- saida.range
import bpy
import sys

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
# Sem isso o Principled cai nos nos antigos e o material fica sem shader (nada aparece).
scene.game_settings.use_shading_nodes = True

mat = bpy.data.materials.new('principled')
mat.use_nodes = True
nodes = mat.node_tree.nodes
for n in list(nodes):
    nodes.remove(n)
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
out_node = nodes.new('ShaderNodeOutputMaterial')
mat.node_tree.links.new(bsdf.outputs[0], out_node.inputs[0])

bpy.ops.mesh.primitive_plane_add(radius=20)
scene.objects.active.data.materials.append(mat)
for i in range(40):
    bpy.ops.mesh.primitive_cube_add(radius=0.6, location=((i % 8) * 3 - 10.5, (i // 8) * 3 - 6, 0.6))
    scene.objects.active.data.materials.append(mat)

for i, loc in enumerate(((-6, -6, 8), (6, -6, 8), (0, 8, 8))):
    lamp = bpy.data.lamps.new('spot%d' % i, 'SPOT')
    lamp.use_shadow = True
    lamp.shadow_method = 'BUFFER_SHADOW'
    lamp.spot_size = 1.6
    lamp.energy = 2.0
    ob = bpy.data.objects.new(lamp.name, lamp)
    ob.location = loc
    scene.objects.link(ob)
    # Rotacao zero: o spot aponta para baixo (-Z).

pivot = bpy.data.objects.new('pivot', None)
scene.objects.link(pivot)
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -22, 14)
cam.rotation_euler = (1.0, 0, 0)
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
