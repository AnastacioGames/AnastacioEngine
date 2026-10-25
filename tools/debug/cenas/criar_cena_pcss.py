"""Cena para ver o PCSS (filtro PCF Penumbra): sombra dura no contato e macia longe do objeto.

Uso:
  AnastacioEngine.exe -b --factory-startup --python criar_cena_pcss.py -- saida.range [SUN|SPOT]

Poste alto, esfera flutuando e cubo encostado no chão.
"""
import bpy
import math
import sys

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
lamp_type = argv[1] if len(argv) > 1 else 'SUN'

scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
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


bpy.ops.mesh.primitive_plane_add(radius=15, location=(0, 0, 0))
bpy.context.object.data.materials.append(principled('Chao', (0.8, 0.8, 0.8, 1)))

bpy.ops.mesh.primitive_cube_add(radius=0.15, location=(0, 0, 2.5))
bpy.context.object.scale = (1, 1, 16.6)
bpy.context.object.data.materials.append(principled('Poste', (0.6, 0.2, 0.1, 1)))

bpy.ops.mesh.primitive_uv_sphere_add(size=0.8, location=(3, 2, 2.5))
bpy.context.object.data.materials.append(principled('Esfera', (0.2, 0.4, 0.8, 1)))

bpy.ops.mesh.primitive_cube_add(radius=0.7, location=(-3, 2, 0.7))
bpy.context.object.data.materials.append(principled('Cubo', (0.2, 0.7, 0.3, 1)))

if lamp_type == 'SUN':
    bpy.ops.object.lamp_add(type='SUN', location=(4, -6, 12))
    lamp_ob = bpy.context.object
    lamp_ob.rotation_euler = (math.radians(40), 0, math.radians(30))
    lamp_ob.data.shadow_frustum_size = 15
    lamp_ob.data.shadow_buffer_clip_start = 1
    lamp_ob.data.shadow_buffer_clip_end = 40
else:
    bpy.ops.object.lamp_add(type='SPOT', location=(4, -6, 9))
    lamp_ob = bpy.context.object
    lamp_ob.rotation_euler = (math.radians(40), 0, math.radians(30))
    lamp_ob.data.spot_size = math.radians(90)
    lamp_ob.data.distance = 40
    lamp_ob.data.shadow_buffer_clip_start = 1
    lamp_ob.data.shadow_buffer_clip_end = 40
lamp = lamp_ob.data
lamp.use_shadow = True
lamp.shadow_buffer_size = 2048
lamp.shadow_buffer_samples = 4
lamp.shadow_buffer_soft = 3.0
lamp.shadow_filter = 'PCF_PENUMBRA'

bpy.ops.object.camera_add(location=(10, -12, 9))
cam = bpy.context.object
cam.rotation_euler = (math.radians(62), 0, math.radians(40))
scene.camera = cam

bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print('OK', out)
