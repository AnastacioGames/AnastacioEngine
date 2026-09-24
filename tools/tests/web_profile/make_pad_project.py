"""Gera a cena de teste do controle na tela (gamepad 0 virtual) em projects-teste/pad/pad.range:

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/make_pad_project.py

Um cubo andando pelo plano com o stick esquerdo de logic.joysticks[0] (vermelho sem gamepad, verde com) ou
com WASD/setas. O botao A, lido por um sensor Joystick (logic brick), ou o espaco fazem o cubo pular. A cada 30
quadros o estado vai para o console ("[pad] ..."), e cada tecla apertada/solta sai como "[pad] key W down"; no
navegador, abrir com ?debug=1. tools/web/verify-pad.cjs confere a cadeia Module.rangePad -> DEV_Joystick ->
Python e sensor sem controle fisico; tools/web/verify-touch.cjs, o overlay (gamepad e teclas).
"""

import os

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEST = os.path.join(ROOT, "projects-teste", "pad")
os.makedirs(DEST, exist_ok=True)

SCRIPT = '''from bge import events, logic

KEYS = ("WKEY", "AKEY", "SKEY", "DKEY", "SPACEKEY", "RETKEY",
        "UPARROWKEY", "DOWNARROWKEY", "LEFTARROWKEY", "RIGHTARROWKEY")


def held(name):
    return logic.keyboard.inputs[getattr(events, name)].active


def main(cont):
    own = cont.owner
    joy = logic.joysticks[0]
    button_a = cont.sensors["BotaoA"]

    if own["frames"] == 0:
        print("[pad] codes W=%d SPACE=%d UPARROW=%d" % (events.WKEY, events.SPACEKEY, events.UPARROWKEY))
    for name in KEYS:
        ev = logic.keyboard.inputs[getattr(events, name)]
        if ev.activated:
            print("[pad] key %s down" % name[:-3])
        if ev.released:
            print("[pad] key %s up" % name[:-3])

    if button_a.triggered:
        print("[pad] sensor A %s" % ("down" if button_a.positive else "up"))
        if button_a.positive:
            own.worldPosition.z = 1.5
    if logic.keyboard.inputs[events.SPACEKEY].activated:
        own.worldPosition.z = 1.5

    lx = (held("DKEY") or held("RIGHTARROWKEY")) - (held("AKEY") or held("LEFTARROWKEY"))
    ly = (held("SKEY") or held("DOWNARROWKEY")) - (held("WKEY") or held("UPARROWKEY"))
    if joy:
        lx, ly = lx or joy.axisValues[0], ly or joy.axisValues[1]
    if lx or ly:
        own.worldPosition.x = max(-4.0, min(4.0, own.worldPosition.x + lx * 0.08))
        own.worldPosition.y = max(-3.0, min(3.0, own.worldPosition.y - ly * 0.08))
    if own.worldPosition.z > 0.5:
        own.worldPosition.z = max(0.5, own.worldPosition.z - 0.05)
    own.color = (0.2, 0.8, 0.3, 1.0) if joy else (0.8, 0.2, 0.2, 1.0)

    own["frames"] += 1
    if own["frames"] % 30 == 0:
        if joy:
            print("[pad] connected=True name=%s axes=%s buttons=%s"
                  % (joy.name, [round(v, 2) for v in joy.axisValues], sorted(joy.activeButtons)))
        else:
            print("[pad] connected=False")


main(logic.getCurrentController())
'''

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'

bpy.ops.mesh.primitive_plane_add(location=(0.0, 0.0, 0.0))
floor = bpy.context.active_object
floor.name = "Chao"
floor.scale = (5.0, 4.0, 1.0)

bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.5))
cube = bpy.context.active_object
cube.name = "Jogador"
cube.scale = (0.5, 0.5, 0.5)
mat = bpy.data.materials.new("Jogador")
mat.use_object_color = True
cube.data.materials.append(mat)

bpy.ops.object.camera_add(location=(0.0, -9.0, 8.0), rotation=(0.8, 0.0, 0.0))
scene.camera = bpy.context.active_object

bpy.ops.object.lamp_add(type='SUN', location=(0.0, 0.0, 6.0), rotation=(0.3, 0.2, 0.0))

text = bpy.data.texts.new("pad_test.py")
text.write(SCRIPT)
with open(os.path.join(DEST, "pad_test.py"), "w", encoding="utf-8") as f:
    f.write(SCRIPT)

scene.objects.active = cube
bpy.ops.object.game_property_new(type='INT', name="frames")
bpy.ops.logic.sensor_add(type='ALWAYS', name="Sempre", object=cube.name)
bpy.ops.logic.sensor_add(type='JOYSTICK', name="BotaoA", object=cube.name)
bpy.ops.logic.controller_add(type='PYTHON', name="Pad", object=cube.name)
always = cube.game.sensors["Sempre"]
always.use_pulse_true_level = True
button_a = cube.game.sensors["BotaoA"]
button_a.joystick_index = 0
button_a.event_type = 'BUTTONS'
button_a.button_number = 'BUTTON_A'
ctrl = cube.game.controllers["Pad"]
ctrl.text = text
always.link(ctrl)
button_a.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DEST, "pad.range"))
print("Cena de teste em", os.path.join(DEST, "pad.range"))
