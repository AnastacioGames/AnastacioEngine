"""Cena de teste do microfone (build/mic_teste.range ou o caminho depois de --).

AnastacioEngine -b --factory-startup --python tools/debug/cenas/criar_cena_microfone.py -- saida.range

No jogo: M liga o microfone (na Web, depois de um toque), R grava/para, P toca,
1-7 tocam com efeito, L ouve ao vivo (use fones), S salva //voz.wav.
"""
import os
import sys

import bpy

CODE = '''import Range
from Range import logic, events

EFFECTS = {events.ONEKEY: "CHIPMUNK", events.TWOKEY: "GIANT", events.THREEKEY: "ROBOT",
           events.FOURKEY: "RADIO", events.FIVEKEY: "ECHO", events.SIXKEY: "CAVE", events.SEVENKEY: "REVERSE"}


def pressed(key):
    return logic.keyboard.inputs[key].activated


def main(cont):
    a = Range.audio
    if pressed(events.MKEY):
        a.microphoneStart()
    if pressed(events.RKEY):
        if a.microphoneIsRecording():
            a.microphoneRecordStop("voz")
        else:
            a.microphoneStart()
            a.microphoneRecordStart()
    if pressed(events.PKEY):
        a.playVoice("voz")
    for key, effect in EFFECTS.items():
        if pressed(key):
            a.playVoice("voz", effect)
    if pressed(events.LKEY):
        if a.isLive():
            a.stopLive()
        else:
            a.playLive()
    if pressed(events.SKEY):
        a.microphoneSave("voz", "//voz.wav")
    level = a.microphoneLevel()
    cont.owner.text = "%s  REC:%s  LIVE:%s\\n%s\\nM mic  R gravar  P tocar  1-7 efeitos\\nL ao vivo  S salvar" % (
        a.microphoneState(), a.microphoneIsRecording(), a.isLive(), "|" * int(min(level * 3, 1) * 40))
'''


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else os.path.abspath("mic_teste.range")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.location = (0, -8, 0)
    cam.rotation_euler = (1.5708, 0, 0)
    scene.objects.link(cam)
    scene.camera = cam

    curve = bpy.data.curves.new("Texto", 'FONT')
    curve.size = 0.5
    txt = bpy.data.objects.new("Texto", curve)
    txt.location = (-3.5, 0, 1)
    txt.rotation_euler = (1.5708, 0, 0)
    scene.objects.link(txt)

    script = bpy.data.texts.new("mic_teste.py")
    script.write(CODE)
    scene.objects.active = txt
    bpy.ops.logic.sensor_add(type='ALWAYS', object=txt.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=txt.name)
    sensor = txt.game.sensors[-1]
    sensor.use_pulse_true_level = True
    controller = txt.game.controllers[-1]
    controller.mode = 'MODULE'
    controller.module = "mic_teste.main"
    sensor.link(controller)

    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("CENA", out)


main()
