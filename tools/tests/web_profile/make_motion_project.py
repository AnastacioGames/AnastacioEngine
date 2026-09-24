"""Gera a cena de teste de bge.logic.motion em projects-teste/motion/motion.range:

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/make_motion_project.py

Camera de cima olhando um tabuleiro. Inclinar o celular inclina o tabuleiro e rola a bola para o lado
mais baixo; tocar na tela chama motion.calibrate() (posicao atual vira a neutra). Tabuleiro verde = sensor
enviando dados, vermelho = sem sensor (desktop). Uma vez por segundo os valores vao para o console
(no navegador, abrir com ?debug=1).
"""

import os

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEST = os.path.join(ROOT, "projects-teste", "motion")
os.makedirs(DEST, exist_ok=True)

SCRIPT = '''import bge
from bge import logic, events
from mathutils import Euler


def main(cont):
    own = cont.owner
    scene = logic.getCurrentScene()
    m = logic.motion

    if logic.mouse.inputs[events.LEFTMOUSE].activated:
        print("[motion] calibrate:", m.calibrate())

    tx, ty = m.tilt
    own.worldOrientation = Euler((-ty * 0.4, tx * 0.4, 0.0)).to_matrix()
    ball = scene.objects["Bola"]
    ball.worldPosition = (tx * 2.6, ty * 1.6, 0.45)
    own.color = (0.2, 0.8, 0.3, 1.0) if m.available else (0.8, 0.2, 0.2, 1.0)

    own["frames"] += 1
    if own["frames"] % 60 == 0:
        print("[motion] available=%s tilt=(%.2f, %.2f) gravity=%s gyro=%s orientation=%s"
              % (m.available, tx, ty, tuple(round(v, 2) for v in m.gravity),
                 tuple(round(v, 2) for v in m.gyroscope), tuple(round(v) for v in m.orientation)))


main(logic.getCurrentController())
'''

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'

bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.0))
board = bpy.context.active_object
board.name = "Tabuleiro"
board.scale = (3.0, 2.0, 0.1)
mat = bpy.data.materials.new("Tabuleiro")
mat.use_object_color = True
board.data.materials.append(mat)

bpy.ops.mesh.primitive_uv_sphere_add(size=0.35, location=(0.0, 0.0, 0.45))
ball = bpy.context.active_object
ball.name = "Bola"
ball_mat = bpy.data.materials.new("Bola")
ball_mat.diffuse_color = (0.9, 0.8, 0.1)
ball.data.materials.append(ball_mat)

bpy.ops.object.camera_add(location=(0.0, 0.0, 9.0), rotation=(0.0, 0.0, 0.0))
scene.camera = bpy.context.active_object

bpy.ops.object.lamp_add(type='SUN', location=(0.0, 0.0, 6.0), rotation=(0.3, 0.2, 0.0))

text = bpy.data.texts.new("motion_test.py")
text.write(SCRIPT)
with open(os.path.join(DEST, "motion_test.py"), "w", encoding="utf-8") as f:
    f.write(SCRIPT)

scene.objects.active = board
bpy.ops.object.game_property_new(type='INT', name="frames")
bpy.ops.logic.sensor_add(type='ALWAYS', name="Sempre", object=board.name)
bpy.ops.logic.controller_add(type='PYTHON', name="Motion", object=board.name)
sensor = board.game.sensors["Sempre"]
sensor.use_pulse_true_level = True
ctrl = board.game.controllers["Motion"]
ctrl.text = text
sensor.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DEST, "motion.range"))
print("Cena de teste em", os.path.join(DEST, "motion.range"))
