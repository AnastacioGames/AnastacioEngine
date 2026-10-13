# Versão interativa do teste do guia de Veículos: um carro só, com o componente
# DirigirSimples do guia (W/S/A/D), câmera seguindo por trás, sem fechar sozinha.
# Uso: AnastacioEngine.exe -b --factory-startup -P criar_cena_guia_veiculos_visual.py -- <pasta de saida> <pasta dos guias>
# Depois: AnastacioRuntime.exe <pasta>/guia_veiculos_visual.range
import bpy
import os
import re
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir, guias = argv[0], argv[1]
sys.path.insert(0, out_dir)


def blocos(nome):
    with open(os.path.join(guias, nome + ".md"), encoding="utf-8") as f:
        return re.findall(r"```python\n(.*?)```", f.read(), re.S)


def material(ob, cor):
    m = bpy.data.materials.new(ob.name + "_mat")
    m.diffuse_color = cor
    ob.data.materials.append(m)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
w = bpy.data.worlds.new("World")
w.mist_settings.use_mist = False
scene.world = w

bpy.ops.mesh.primitive_plane_add(radius=60, location=(0, 0, 0))
chao = bpy.context.object
chao.name = "Chao"
material(chao, (0.3, 0.45, 0.3))
chao.game.physics_type = 'STATIC'
# Listras no chão para dar noção de movimento.
for i in range(-8, 9, 2):
    bpy.ops.mesh.primitive_cube_add(location=(3.3, i * 5.0, 0.02))
    faixa = bpy.context.object
    faixa.scale = (0.15, 1.5, 0.02)
    material(faixa, (0.9, 0.9, 0.2))
    faixa.game.physics_type = 'NO_COLLISION'

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0.6))
chassi = bpy.context.object
chassi.name = "Chassi"
chassi.scale = (1.0, 2.2, 0.5)
material(chassi, (0.85, 0.15, 0.1))
chassi.game.physics_type = 'RIGID_BODY'
chassi.game.mass = 800.0
chassi.game.is_vehicle = True
chassi.game.use_collision_bounds = True
chassi.game.collision_bounds_type = 'BOX'
chassi.vehicle_ray_cast_mask = 1

posicoes = [("RodaFD", (0.9, 1.4, 0.35), True), ("RodaFE", (-0.9, 1.4, 0.35), True),
            ("RodaTD", (0.9, -1.4, 0.35), False), ("RodaTE", (-0.9, -1.4, 0.35), False)]
rodas = []
for nome, pos, esterca in posicoes:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=0.25, location=pos)
    roda = bpy.context.object
    roda.name = nome
    roda.rotation_euler = (0, 1.5708, 0)
    material(roda, (0.1, 0.1, 0.1))
    roda.game.physics_type = 'NO_COLLISION'
    rodas.append((roda, esterca))

bpy.context.scene.objects.active = chassi
for roda, esterca in rodas:
    bpy.ops.object.vehicle_wheel_add()
    w4 = chassi.vehicle_wheels[-1]
    w4.object = roda
    w4.radius = 0.35
    w4.suspension_rest_length = 0.3
    w4.has_steering = esterca
    w4.has_drive = True

sun = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN'))
sun.rotation_euler = (0.6, 0.2, 0.4)
scene.objects.link(sun)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.location = (0, -8, 3.5)
alvo_inicial = Vector((0, 0, 0.8))
cam.rotation_euler = (alvo_inicial - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

# Componente oficial do demo (o mesmo que o guia recomenda na seção "Dirija com
# o componente pronto"), igual ao painel Add Component ofereceria.
import shutil
demo_comp = os.path.join("D:" + os.sep, "AnastacioEngine", "source", "release", "demos", "Vehicle", "scripts", "vehicle_player_component.py")
shutil.copyfile(demo_comp, os.path.join(out_dir, "vehicle_player_component.py"))
bpy.context.scene.objects.active = chassi
bpy.ops.logic.python_component_register(component_name="vehicle_player_component.VehiclePlayerComponent")
# O chassi aponta a frente para +Y (convencao do projeto); o componente por
# padrao espera -Y (Engine Sign/Invert Direction), senao W anda de re.
chassi.game.components[-1].properties["Invert Direction"].value = True

# Câmera atrás do carro (persegue por trás, sem travar na rotação do chassi).
cam_rig = bpy.data.texts.new("cam_rig.py")
cam_rig.write('''from Range import logic
import mathutils


def tick(cont):
    own = cont.owner
    cam = own.scene.active_camera
    atras = own.worldPosition - own.worldOrientation.col[1] * 9.0
    atras.z += 3.5
    cam.worldPosition = cam.worldPosition.lerp(atras, 0.08)
    alvo = own.worldPosition.copy()
    alvo.z += 0.8
    vetor = alvo - cam.worldPosition
    quat = vetor.to_track_quat('-Z', 'Y')
    cam.worldOrientation = cam.worldOrientation.to_quaternion().slerp(quat, 0.15).to_matrix()
''')
bpy.context.scene.objects.active = chassi
bpy.ops.logic.sensor_add(type='ALWAYS', name='cam', object=chassi.name)
bpy.ops.logic.controller_add(type='PYTHON', name='camc', object=chassi.name)
chassi.game.sensors['cam'].use_pulse_true_level = True
cc = chassi.game.controllers['camc']
cc.mode = 'MODULE'
cc.module = "cam_rig.tick"
cc.link(sensor=chassi.game.sensors['cam'])

path = os.path.join(out_dir, "guia_veiculos_visual.range")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("salvo:", path)
