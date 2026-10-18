# Cena para conferir o realce dos logic bricks ativos no Logic Editor durante o jogo embutido.
#
# Cubo com tres cadeias:
#   W (Keyboard)        -> And -> Motion (anda em Y)
#   Espaco (Keyboard)   -> And -> Motion (gira em Z)
#   Delay repetido      -> And -> Property (conta "pulsos"), acende sozinho a cada ~0,5 s
#
# Uso:
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_logic_realce.py -- saida.range
import sys

import bpy
from mathutils import Vector

out = sys.argv[sys.argv.index("--") + 1]

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
    bpy.data.objects.remove(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_frame_rate = True

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.horizon_color = (0.25, 0.3, 0.38)
world.mist_settings.use_mist = False


def material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgb
    return mat


bpy.ops.mesh.primitive_plane_add(radius=8.0, location=(0.0, 0.0, 0.0))
chao = scene.objects.active
chao.name = "Chao"
chao.data.materials.append(material("ChaoMat", (0.35, 0.35, 0.35)))

bpy.ops.mesh.primitive_cube_add(radius=0.5, location=(0.0, 0.0, 0.5))
cubo = scene.objects.active
cubo.name = "Cubo"
cubo.data.materials.append(material("CuboMat", (0.9, 0.3, 0.1)))

bpy.ops.object.game_property_new(type='INT', name="pulsos")

lamp = bpy.data.lamps.new("Sol", 'SUN')
sol = bpy.data.objects.new("Sol", lamp)
scene.objects.link(sol)
sol.location = (3.0, -4.0, 8.0)
sol.rotation_euler = (0.7, 0.2, 0.5)

cam_data = bpy.data.cameras.new("Camera")
cam_data.type = 'PERSP'
cam_data.lens = 16.0
cam = bpy.data.objects.new("Camera", cam_data)
scene.objects.link(cam)
cam.location = (0.0, -9.0, 6.0)
cam.rotation_euler = (Vector((0.0, 0.0, 0.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

for ob in scene.objects:
    ob.select = False
cubo.select = True
scene.objects.active = cubo
logic = cubo.game


def cadeia(nome, sensor_type, actuator_type):
    bpy.ops.logic.sensor_add(type=sensor_type, name=nome, object=cubo.name)
    bpy.ops.logic.controller_add(type='LOGIC_AND', name=nome, object=cubo.name)
    bpy.ops.logic.actuator_add(type=actuator_type, name=nome, object=cubo.name)
    sens = logic.sensors[-1]
    cont = logic.controllers[-1]
    act = logic.actuators[-1]
    sens.link(cont)
    act.link(cont)
    return sens, act


sens, act = cadeia("Andar", 'KEYBOARD', 'MOTION')
sens.key = 'W'
act.offset_location = (0.0, 0.05, 0.0)
act.use_local_location = True

sens, act = cadeia("Girar", 'KEYBOARD', 'MOTION')
sens.key = 'SPACE'
act.offset_rotation = (0.0, 0.0, 0.05)
act.use_local_rotation = True

sens, act = cadeia("Pulso", 'DELAY', 'PROPERTY')
sens.delay = 30
sens.duration = 1
sens.use_repeat = True
act.mode = 'ADD'
act.property = "pulsos"
act.value = "1"

# Abre no layout com Logic Editor.
logic_screen = bpy.data.screens.get("Game Dev")
if logic_screen:
    for win in bpy.context.window_manager.windows:
        win.screen = logic_screen

bpy.ops.wm.save_as_mainfile(filepath=out)
