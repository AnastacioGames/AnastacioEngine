"""Cena de teste do microfone: painel de gravador com botões (mouse ou teclas).

AnastacioEngine -b --factory-startup --python tools/debug/cenas/criar_cena_microfone.py -- saida.range

M microfone, R gravar/parar, P tocar, 1-7 efeitos, L ao vivo (use fones), S salvar //voz.wav, D trocar microfone.
"""
import os
import sys

import bpy

# nome, rótulo, x, y, largura, altura
BUTTONS = (
    ("mic", "M  Microfone", -4.9, 1.0, 4.4, 1.1),
    ("rec", "R  Gravar", 0.0, 1.0, 4.4, 1.1),
    ("play", "P  Tocar", 4.9, 1.0, 4.4, 1.1),
    ("fx1", "1 Esquilo", -5.4, -0.7, 2.5, 1.0),
    ("fx2", "2 Gigante", -1.8, -0.7, 2.5, 1.0),
    ("fx3", "3 Robo", 1.8, -0.7, 2.5, 1.0),
    ("fx4", "4 Radio", 5.4, -0.7, 2.5, 1.0),
    ("fx5", "5 Eco", -3.6, -2.0, 2.5, 1.0),
    ("fx6", "6 Caverna", 0.0, -2.0, 2.5, 1.0),
    ("fx7", "7 Inverso", 3.6, -2.0, 2.5, 1.0),
    ("live", "L  Ao vivo (fones)", -4.9, -3.4, 4.4, 1.0),
    ("save", "S  Salvar voz.wav", 0.0, -3.4, 4.4, 1.0),
    ("dev", "D  Trocar microfone", 4.9, -3.4, 4.4, 1.0),
)

CODE = '''import time

import aud
import Range
from Range import logic, events, render

BUTTONS = %r
FX = {"fx1": "CHIPMUNK", "fx2": "GIANT", "fx3": "ROBOT", "fx4": "RADIO",
      "fx5": "ECHO", "fx6": "CAVE", "fx7": "REVERSE"}
KEYS = {events.MKEY: "mic", events.RKEY: "rec", events.PKEY: "play", events.LKEY: "live", events.SKEY: "save", events.DKEY: "dev",
        events.ONEKEY: "fx1", events.TWOKEY: "fx2", events.THREEKEY: "fx3", events.FOURKEY: "fx4",
        events.FIVEKEY: "fx5", events.SIXKEY: "fx6", events.SEVENKEY: "fx7"}
ORTHO = 16.0
METER_LEFT, METER_WIDTH = -6.0, 12.0

IDLE = (0.20, 0.24, 0.30, 1.0)
HOVER = (0.30, 0.38, 0.48, 1.0)
ON = (0.15, 0.55, 0.30, 1.0)
RED = (0.80, 0.12, 0.12, 1.0)
OFF = (0.12, 0.13, 0.16, 1.0)

S = {"since": 0.0, "last": 0.0, "fx": "", "msg": "Clique em Microfone ou Gravar", "dev": 0}


def has_voice(a):
    return "voz" in a.recordings()


def devices():
    try:
        return [""] + list(aud.Microphone.devices())
    except Exception:
        return [""]


def device():
    names = devices()
    return names[S["dev"] %% len(names)]


def device_label():
    return device().replace("OpenAL Soft on ", "") or "padrao"


def act(a, name):
    if name == "dev":
        if a.microphoneIsRecording():
            S["msg"] = "Pare a gravacao antes"
            return
        if a.isLive():
            a.stopLive()
        S["dev"] += 1
        a.microphoneStop()
        a.microphoneStart(device())
        S["msg"] = "Usando: " + device_label()
    elif name == "mic":
        if a.microphoneState() in ("closed", "error"):
            a.microphoneStart(device())
        elif not a.microphoneIsRecording() and not a.isLive():
            a.microphoneStop()
    elif name == "rec":
        if a.microphoneIsRecording():
            a.microphoneRecordStop("voz")
            S["last"] = time.time() - S["since"]
            S["msg"] = "Gravado: %%.1f s" %% S["last"]
        else:
            a.microphoneStart(device())
            if a.microphoneRecordStart():
                S["since"] = time.time()
                S["msg"] = "Gravando..."
            else:
                S["msg"] = "Microfone: %%s" %% a.microphoneState()
    elif name == "live":
        if a.isLive():
            a.stopLive()
        else:
            a.microphoneStart(device())
            a.playLive()
    elif not has_voice(a):
        S["msg"] = "Grave algo primeiro"
    elif name == "play":
        a.playVoice("voz")
        S["fx"] = ""
        S["msg"] = "Tocando"
    elif name == "save":
        S["msg"] = "Salvo voz.wav" if a.microphoneSave("voz", "//voz.wav") else "Nao salvou"
    else:
        a.playVoice("voz", FX[name])
        S["fx"] = name
        S["msg"] = "Efeito: " + FX[name]


def under_mouse():
    x, y = logic.mouse.position
    wx = (x - 0.5) * ORTHO
    wy = (0.5 - y) * ORTHO * render.getWindowHeight() / max(render.getWindowWidth(), 1)
    for name, _label, bx, by, w, h in BUTTONS:
        if abs(wx - bx) <= w / 2 and abs(wy - by) <= h / 2:
            return name
    return ""


def set_text(obj, text):
    if obj.text != text:
        obj.text = text


def main(cont):
    a = Range.audio
    objs = cont.owner.scene.objects
    logic.mouse.visible = True

    hover = under_mouse()
    if logic.mouse.inputs[events.LEFTMOUSE].activated and hover:
        act(a, hover)
    for key, name in KEYS.items():
        if logic.keyboard.inputs[key].activated:
            act(a, name)

    state = a.microphoneState()
    recording = a.microphoneIsRecording()
    live = a.isLive()
    voice = has_voice(a)
    for name, _label, _x, _y, _w, _h in BUTTONS:
        if name == "mic":
            color = ON if state == "granted" else (HOVER if hover == name else IDLE)
        elif name == "rec":
            color = RED if recording else (HOVER if hover == name else IDLE)
        elif name == "live":
            color = ON if live else (HOVER if hover == name else IDLE)
        elif not voice:
            color = OFF
        elif S["fx"] == name:
            color = ON
        else:
            color = HOVER if hover == name else IDLE
        objs["btn_" + name].color = color
    set_text(objs["lbl_rec"], "R  Parar" if recording else "R  Gravar")

    seconds = time.time() - S["since"] if recording else S["last"]
    set_text(objs["Tempo"], "%%02d:%%02d" %% (int(seconds) // 60, int(seconds) %% 60))
    names = {"closed": "desligado", "pending": "esperando permissao", "granted": "ligado",
             "denied": "bloqueado", "error": "erro"}
    set_text(objs["Status"], "Microfone: %%s" %% names.get(state, state))
    set_text(objs["Disp"], device_label()[:44])
    set_text(objs["Msg"], S["msg"])

    level = min(a.microphoneLevel() * 3.0, 1.0)
    bar = objs["Nivel"]
    width = max(level * METER_WIDTH, 0.001)
    bar.localScale.x = width
    bar.localPosition.x = METER_LEFT + width / 2
    bar.color = RED if level > 0.9 else ON
''' % (BUTTONS,)


def quad():
    me = bpy.data.meshes.new("Quad")
    me.from_pydata([(-.5, -.5, 0), (.5, -.5, 0), (.5, .5, 0), (-.5, .5, 0)], [], [(0, 1, 2, 3)])
    me.update()
    return me


def add_rect(scene, mesh, name, x, y, z, w, h, color):
    ob = bpy.data.objects.new(name, mesh)
    ob.location = (x, y, z)
    ob.scale = (w, h, 1)
    ob.color = color
    scene.objects.link(ob)
    return ob


def add_text(scene, mat, name, body, x, y, size, align='CENTER'):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.materials.append(mat)
    ob = bpy.data.objects.new(name, cu)
    ob.location = (x, y - size * 0.3, 0.2)
    ob.color = (1, 1, 1, 1)
    scene.objects.link(ob)
    return ob


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else os.path.abspath("mic_teste.range")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 16.0
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = (0, 0, 10)
    scene.objects.link(cam)
    scene.camera = cam

    mat = bpy.data.materials.new("Flat")
    mat.use_shadeless = True
    mat.use_object_color = True
    mesh = quad()
    mesh.materials.append(mat)

    add_rect(scene, mesh, "Fundo", 0, 0, -0.2, 15.0, 8.8, (0.07, 0.08, 0.10, 1))
    add_text(scene, mat, "Status", "Microfone: desligado", -7.0, 3.7, 0.42, 'LEFT')
    add_text(scene, mat, "Tempo", "00:00", 7.0, 3.5, 0.9, 'RIGHT')
    add_text(scene, mat, "Msg", "", -7.0, 3.05, 0.34, 'LEFT')
    add_text(scene, mat, "Disp", "", 0.0, 3.05, 0.3, 'LEFT')
    add_rect(scene, mesh, "NivelFundo", 0, 2.2, 0, 12.0, 0.45, (0.12, 0.13, 0.16, 1))
    add_rect(scene, mesh, "Nivel", -6.0, 2.2, 0.1, 0.001, 0.45, (0.15, 0.55, 0.30, 1))

    for name, label, x, y, w, h in BUTTONS:
        add_rect(scene, mesh, "btn_" + name, x, y, 0, w, h, (0.20, 0.24, 0.30, 1))
        add_text(scene, mat, "lbl_" + name, label, x, y, 0.4)

    script = bpy.data.texts.new("mic_teste.py")
    script.write(CODE)
    ctl = scene.objects["Fundo"]
    scene.objects.active = ctl
    bpy.ops.logic.sensor_add(type='ALWAYS', object=ctl.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=ctl.name)
    sensor = ctl.game.sensors[-1]
    sensor.use_pulse_true_level = True
    controller = ctl.game.controllers[-1]
    controller.mode = 'MODULE'
    controller.module = "mic_teste.main"
    sensor.link(controller)

    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("CENA", out)


main()
