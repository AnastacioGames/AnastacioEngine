# Testa se o personagem (Physics Type = Character) acompanha uma plataforma em movimento.
# Sem o fix, o personagem fica parado no ar (relativo ao mundo) enquanto a plataforma anda
# por baixo dele -- "desliza". Com o fix, ele deve se mover junto.
#
# Cena: plataforma 4x4 que vai e volta em X (Rigid Body, Kinematic), um Character
# (capsula) em cima dela, parado (sem walk direction). Texto na tela mostra a cada
# segundo a posicao do personagem relativa a plataforma -- deve ficar praticamente
# constante; se estiver "deslizando", o X relativo cresce sem parar.
#
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_character_plataforma.py -- <pasta>
import math
import os
import sys

import bpy

folder = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
os.makedirs(folder, exist_ok=True)

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'

world = bpy.data.worlds.new("World")
world.horizon_color = (0.05, 0.05, 0.08)
scene.world = world


def label(name, text, loc, size=0.4):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = text
    cu.align_x = 'CENTER'
    cu.size = size
    ob = bpy.data.objects.new(name, cu)
    ob.location = loc
    ob.rotation_euler = (math.radians(90), 0, 0)
    scene.objects.link(ob)
    return ob


label("Titulo", "Character em plataforma movel", (0, 0, 5.0), 0.5)
status = label("Status", "aguardando...", (0, 0, 4.2), 0.35)

# Chao estatico, so pra nao cair no vazio se escorregar da plataforma
bpy.ops.mesh.primitive_plane_add(location=(0, 0, -0.5), radius=20)
chao = bpy.context.active_object
chao.name = "Chao"
chao.game.physics_type = 'STATIC'

# Plataforma: Rigid Body Kinematic, anda em X com uma IPO/acao simples (loc X -4..4)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
plat = bpy.context.active_object
plat.name = "Plataforma"
plat.scale = (2.0, 2.0, 0.2)
bpy.ops.object.transform_apply(scale=True)
plat.game.physics_type = 'RIGID_BODY'
plat.game.use_ghost = False
if hasattr(plat.game, "use_kinematic"):
    plat.game.use_kinematic = True

plat.animation_data_create()
action = bpy.data.actions.new("PlataformaAnda")
fcu = action.fcurves.new(data_path="location", index=0)
fcu.keyframe_points.insert(0, -4.0)
fcu.keyframe_points.insert(75, 4.0)
fcu.keyframe_points.insert(150, -4.0)
for kp in fcu.keyframe_points:
    kp.interpolation = 'LINEAR'
plat.animation_data.action = action
scene.frame_start = 0
scene.frame_end = 150

# Garante que a Actuator Action toque em loop (senao a plataforma anda uma vez e para)
bpy.ops.logic.sensor_add(type='ALWAYS', object=plat.name)
bpy.ops.logic.controller_add(type='LOGIC_AND', object=plat.name)
bpy.ops.logic.actuator_add(type='ACTION', object=plat.name)
plat.game.sensors[-1].use_pulse_true_level = True
act = plat.game.actuators[-1]
act.action = action
act.frame_start = 0
act.frame_end = 150
act.play_mode = 'LOOPEND'
plat.game.sensors[-1].link(plat.game.controllers[-1])
plat.game.controllers[-1].link(actuator=act)

# Personagem: capsula com Physics Type = Character, parado em cima da plataforma
bpy.ops.mesh.primitive_cylinder_add(location=(0, 0, 1.2), radius=0.3, depth=1.6)
personagem = bpy.context.active_object
personagem.name = "Personagem"
personagem.game.physics_type = 'CHARACTER'
mat = bpy.data.materials.new("MatPersonagem")
mat.diffuse_color = (0.9, 0.3, 0.2)
personagem.data.materials.append(mat)

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.objects.link(cam)
cam.location = (9, -9, 5)
from mathutils import Vector
cam.rotation_euler = (Vector((0, 0, 1.2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

lamp = bpy.data.lamps.new("Sun", 'SUN')
sun = bpy.data.objects.new("Sun", lamp)
scene.objects.link(sun)
sun.rotation_euler = (0.8, 0.2, 0.6)

text = bpy.data.texts.new("acompanha.py")
text.from_string('''import bge
import os

def _log(text):
    try:
        with open(bge.logic.expandPath("//log.txt"), "a") as f:
            f.write(text + "
")
    except Exception as e:
        pass

def tick(cont):
    own = cont.owner
    scene = bge.logic.getCurrentScene()
    personagem = scene.objects["Personagem"]
    plataforma = scene.objects["Plataforma"]
    status = scene.objects["Status"]
    frame = own.get("frame", 0) + 1
    own["frame"] = frame
    relX = personagem.worldPosition.x - plataforma.worldPosition.x
    first = own.get("first_rel", None)
    if first is None:
        own["first_rel"] = relX
        first = relX
    drift = relX - first
    status.data.body = "quadro %d | plataforma X=%.2f | personagem relativo=%.2f | desvio=%.2f" % (
        frame, plataforma.worldPosition.x, relX, drift)
    if frame == 1:
        _log("inicio rel=%.3f" % relX)
    if frame %% 60 == 0:
        _log("frame=%d plataforma_x=%.3f rel=%.3f desvio=%.3f" % (frame, plataforma.worldPosition.x, relX, drift))
    if frame >= 400:
        _log("FIM desvio_final=%.3f" % drift)
        bge.logic.endGame()
''')
controlador = bpy.data.objects.new("Controlador", None)
scene.objects.link(controlador)
scene.objects.active = controlador
bpy.ops.logic.sensor_add(type='ALWAYS', object=controlador.name)
bpy.ops.logic.controller_add(type='PYTHON', object=controlador.name)
s = controlador.game.sensors[-1]
s.use_pulse_true_level = True
c = controlador.game.controllers[-1]
c.mode = 'MODULE'
c.module = 'acompanha.tick'
s.link(c)

path = os.path.join(folder, "character_plataforma.range")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("CENA_SALVA", path)
