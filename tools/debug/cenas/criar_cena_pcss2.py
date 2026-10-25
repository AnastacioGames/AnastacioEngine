"""Cena 2 do PCSS: sol quase a pino, objetos em alturas diferentes e câmera de cima,
para comparar a largura da penumbra lado a lado (PCF x PCSS).
Câmera livre: WASD anda, Q/E sobe/desce, setas giram.

Uso:
  AnastacioEngine.exe -b --factory-startup --python criar_cena_pcss2.py -- saida.range [PCF|PCF_PENUMBRA] [soft] [CSM]
CSM: sol com cascatas e material clássico (o Principled não recebe sombra de CSM).
"""
import bpy
import math
import sys

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
filtro = argv[1] if len(argv) > 1 else 'PCF_PENUMBRA'
soft = float(argv[2]) if len(argv) > 2 else 3.0
csm = len(argv) > 3 and argv[3] == 'CSM'

scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = not csm
scene.world.horizon_color = (0.4, 0.45, 0.5)
scene.world.ambient_color = (0.35, 0.35, 0.35)


def principled(name, color):
    mat = bpy.data.materials.new(name)
    if csm:
        mat.diffuse_color = color[:3]
        mat.specular_intensity = 0.1
        mat.ambient = 0.3
        return mat
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    for n in list(nodes):
        nodes.remove(n)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = color
    out_node = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs[0], out_node.inputs[0])
    return mat


def caixa(nome, loc, tam, cor):
    bpy.ops.mesh.primitive_cube_add(radius=1, location=loc)
    ob = bpy.context.object
    ob.name = nome
    ob.scale = tam
    ob.data.materials.append(principled(nome, cor))


bpy.ops.mesh.primitive_plane_add(radius=12, location=(0, 0, 0))
bpy.context.object.data.materials.append(principled('Chao', (0.85, 0.85, 0.85, 1)))

# Poste de 6 m: sombra dura no pé, macia na ponta.
caixa('Poste', (-4, 0, 3), (0.12, 0.12, 3), (0.7, 0.3, 0.1, 1))
# Tábua apoiada num pé só (inclinada do chão até 2,5 m).
bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, -3, 1.25))
ob = bpy.context.object
ob.scale = (2.6, 0.4, 0.05)
ob.rotation_euler = (0, -math.atan2(2.5, 5.0), 0)
ob.data.materials.append(principled('Tabua', (0.6, 0.5, 0.3, 1)))
# Esferas em 3 alturas.
for i, h in enumerate((0.5, 1.5, 3.5)):
    bpy.ops.mesh.primitive_uv_sphere_add(size=0.5, location=(1.5 * i + 1, 2.5, h))
    bpy.context.object.data.materials.append(principled('Esfera%d' % i, (0.2, 0.4, 0.85, 1)))
# Cubo no chão.
caixa('Cubo', (4, -3, 0.5), (0.5, 0.5, 0.5), (0.2, 0.7, 0.3, 1))

bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 15))
sol = bpy.context.object
sol.rotation_euler = (math.radians(20), math.radians(10), 0)
lamp = sol.data
lamp.use_shadow = True
lamp.shadow_frustum_size = 12
lamp.shadow_buffer_clip_start = 1
lamp.shadow_buffer_clip_end = 30
lamp.shadow_buffer_size = 2048
lamp.shadow_buffer_samples = 4
lamp.shadow_buffer_soft = soft
lamp.shadow_filter = filtro
if csm:
    lamp.use_csm_shadow = True

bpy.ops.object.camera_add(location=(0, -14, 13))
cam = bpy.context.object
cam.rotation_euler = (math.radians(45), 0, 0)
scene.camera = cam

CAMERA_PY = '''
import math
from bge import logic, events



def main(cont):
    cam = cont.owner
    k = logic.keyboard.inputs
    dt = 1.0 / max(logic.getAverageFrameRate(), 1.0)
    vel = 6.0 * dt
    ang = 1.5 * dt

    def held(key):
        return k[key].active

    mover = [0.0, 0.0, 0.0]
    if held(events.WKEY): mover[2] -= vel
    if held(events.SKEY): mover[2] += vel
    if held(events.AKEY): mover[0] -= vel
    if held(events.DKEY): mover[0] += vel
    cam.applyMovement(mover, True)
    if held(events.EKEY): cam.worldPosition.z += vel
    if held(events.QKEY): cam.worldPosition.z -= vel
    if held(events.LEFTARROWKEY): cam.applyRotation((0, 0, ang), False)
    if held(events.RIGHTARROWKEY): cam.applyRotation((0, 0, -ang), False)
    if held(events.UPARROWKEY): cam.applyRotation((ang, 0, 0), True)
    if held(events.DOWNARROWKEY): cam.applyRotation((-ang, 0, 0), True)
'''
text = bpy.data.texts.new('camera_livre.py')
text.write(CAMERA_PY)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='Sempre', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='Camera', object=cam.name)
sens = cam.game.sensors[-1]
sens.use_pulse_true_level = True
ctrl = cam.game.controllers[-1]
ctrl.mode = 'MODULE'
ctrl.module = 'camera_livre.main'
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print('OK', out)
