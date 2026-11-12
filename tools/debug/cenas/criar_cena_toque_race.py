"""Cena de teste do layout de toque `race` (celular): carro visto de cima, painel do controle e menu de pausa.

AnastacioEngine -b --factory-startup --python tools/debug/cenas/criar_cena_toque_race.py -- saida.range

Exportar com --touch-layout race. Gatilho direito acelera, esquerdo freia/re, eixo X do stick (ou setas/inclinar)
vira. Start abre o menu: com "Controles: desligados" o toque vira mouse e clica em "Voltar a corrida" ou
"Reiniciar". O painel mostra o valor cru de cada entrada para conferir que nada fica preso.
No PC: teclado (setas, Enter, Espaco) faz o mesmo, para conferir a cena antes de exportar.
"""
import os
import sys

import bpy

ORTHO = 20.0
MENU = (
    ("voltar", "Voltar a corrida", 0.0, -0.4),
    ("reiniciar", "Reiniciar", 0.0, -1.9),
)

CODE = '''import math

from Range import logic, events, render

ORTHO = %r
MENU = %r
ARENA_X, ARENA_Y0, ARENA_Y1 = 9.0, -4.0, 0.4
# SDL GameController: botoes A0 B1 X2 Y3 Start6 RB10; eixos LX0 LY1 RX2 RY3 LT4 RT5
BTN = (("A", 0), ("B", 1), ("X", 2), ("Y", 3), ("Start", 6), ("RB", 10))
S = {"vel": 0.0, "ang": 0.0, "x": 0.0, "y": -3.0, "menu": False, "start": False, "msg": "", "voltas": 0}

IDLE = (0.20, 0.24, 0.30, 1.0)
HOVER = (0.30, 0.38, 0.48, 1.0)
ON = (0.90, 0.53, 0.16, 1.0)


def pad():
    for j in logic.joysticks:
        if j is not None:
            return j
    return None


def trig(v):
    # gatilho pode chegar em -1..1 (repouso -1) ou 0..1
    return max(0.0, v) if v >= -0.01 else (v + 1.0) / 2.0


def read():
    j = pad()
    kb = logic.keyboard.inputs
    axes = list(j.axisValues) + [0.0] * 6 if j else [0.0] * 6
    buttons = set(j.activeButtons) if j else set()
    steer = axes[0]
    gas, brake = trig(axes[5]), trig(axes[4])
    if kb[events.LEFTARROWKEY].active:
        steer = -1.0
    if kb[events.RIGHTARROWKEY].active:
        steer = 1.0
    if kb[events.UPARROWKEY].active:
        gas = 1.0
    if kb[events.DOWNARROWKEY].active:
        brake = 1.0
    start = 6 in buttons or kb[events.ENTERKEY].active
    return j, axes, buttons, steer, gas, brake, start


def under_mouse():
    x, y = logic.mouse.position
    wx = (x - 0.5) * ORTHO
    wy = (0.5 - y) * ORTHO * render.getWindowHeight() / max(render.getWindowWidth(), 1)
    for name, _label, bx, by in MENU:
        if abs(wx - bx) <= 3.0 and abs(wy - by) <= 0.6:
            return name
    return ""


def reset():
    S.update(vel=0.0, ang=0.0, x=0.0, y=-3.0, voltas=0)


def set_text(obj, text):
    if obj.text != text:
        obj.text = text


def main(cont):
    objs = cont.owner.scene.objects
    logic.mouse.visible = True
    dt = 1.0 / max(logic.getAverageFrameRate(), 20.0)
    j, axes, buttons, steer, gas, brake, start = read()

    if start and not S["start"]:
        S["menu"] = not S["menu"]
        S["msg"] = "Menu aberto: desligue os controles e toque num botao" if S["menu"] else "Correndo"
    S["start"] = start

    hover = under_mouse() if S["menu"] else ""
    if S["menu"] and logic.mouse.inputs[events.LEFTMOUSE].activated and hover:
        if hover == "reiniciar":
            reset()
        S["menu"] = False
        S["msg"] = "Voltou pelo toque (%%s): ligue os controles de novo" %% hover

    if not S["menu"]:
        S["vel"] += (gas * 9.0 - brake * 12.0 - S["vel"] * 0.8) * dt
        S["vel"] = max(-4.0, min(12.0, S["vel"]))
        S["ang"] -= steer * 2.4 * dt * (1.0 if S["vel"] >= 0 else -1.0) * min(abs(S["vel"]) / 3.0, 1.0)
        S["x"] += math.cos(S["ang"]) * S["vel"] * dt
        S["y"] += math.sin(S["ang"]) * S["vel"] * dt
        if abs(S["x"]) > ARENA_X:
            S["x"] = -math.copysign(ARENA_X, S["x"])
            S["voltas"] += 1
        S["y"] = max(ARENA_Y0, min(ARENA_Y1, S["y"]))

    car = objs["Carro"]
    car.localPosition = (S["x"], S["y"], 0.05)
    car.localOrientation = (0.0, 0.0, S["ang"])

    for name, idx in BTN:
        objs["btn_" + name].color = ON if idx in buttons else IDLE
    for name, value in (("Volante", steer), ("Gas", gas), ("Freio", brake)):
        bar = objs["bar_" + name]
        if name == "Volante":
            w = max(abs(value) * 2.0, 0.001)
            bar.localScale.x = w
            bar.localPosition.x = objs["fundo_" + name].localPosition.x + math.copysign(w / 2, value)
        else:
            w = max(value * 4.0, 0.001)
            bar.localScale.x = w
            bar.localPosition.x = objs["fundo_" + name].localPosition.x - 2.0 + w / 2

    objs["Menu"].visible = S["menu"]
    objs["lbl_menu"].visible = S["menu"]
    for name, _label, _x, _y in MENU:
        b = objs["menu_" + name]
        b.visible = S["menu"]
        objs["lbl_" + name].visible = S["menu"]
        b.color = HOVER if hover == name else IDLE

    w, h = render.getWindowWidth(), render.getWindowHeight()
    set_text(objs["Info"], "%%s | %%dx%%d %%s | %%.0f fps" %% (
        j.name[:28] if j else "sem controle", w, h, "deitado" if w >= h else "em pe", logic.getAverageFrameRate()))
    set_text(objs["Eixos"], "LX %%+.2f  LY %%+.2f  LT %%+.2f  RT %%+.2f  vel %%.1f  voltas %%d" %% (
        axes[0], axes[1], axes[4], axes[5], S["vel"], S["voltas"]))
    set_text(objs["Msg"], S["msg"])
''' % (ORTHO, MENU)


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


def add_text(scene, mat, name, body, x, y, z, size, align='CENTER'):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.materials.append(mat)
    ob = bpy.data.objects.new(name, cu)
    ob.location = (x, y - size * 0.3, z)
    ob.color = (1, 1, 1, 1)
    scene.objects.link(ob)
    return ob


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else os.path.abspath("toque_race.range")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ORTHO
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = (0, 0, 10)
    scene.objects.link(cam)
    scene.camera = cam

    mat = bpy.data.materials.new("Flat")
    mat.use_shadeless = True
    mat.use_object_color = True
    mesh = quad()
    mesh.materials.append(mat)

    # Tudo cabe em y +-4,4 (tela 2,2:1, ex.: Find X3 Pro) e longe dos cantos de cima (Tela cheia / Controles).
    # pista: asfalto com faixas; o carro sai por um lado e entra pelo outro (conta volta)
    add_rect(scene, mesh, "Fundo", 0, 0, -0.3, 40.0, 24.0, (0.10, 0.22, 0.12, 1))
    add_rect(scene, mesh, "Asfalto", 0, -1.8, -0.2, 19.0, 5.2, (0.18, 0.18, 0.20, 1))
    for i in range(-4, 5):
        add_rect(scene, mesh, "Faixa%d" % (i + 4), i * 2.2, -1.8, -0.1, 1.0, 0.15, (0.85, 0.85, 0.80, 1))
    add_rect(scene, mesh, "Carro", 0, -3, 0.05, 1.2, 0.6, (0.85, 0.15, 0.12, 1))
    add_rect(scene, mesh, "Frente", 0.45, 0, 0.1, 0.25, 0.8, (1.0, 0.9, 0.3, 1)).parent = bpy.data.objects["Carro"]

    # painel do controle (em cima)
    add_text(scene, mat, "Info", "", 0, 4.0, 0.3, 0.3)
    add_text(scene, mat, "Eixos", "", 0, 3.5, 0.3, 0.3)
    add_text(scene, mat, "Msg", "Gatilho direito acelera; Start abre o menu", 0, 3.0, 0.3, 0.3)
    for k, (name, label) in enumerate((("Volante", "Volante"), ("Gas", "RT gas"), ("Freio", "LT freio"))):
        x = -5.0 + k * 5.0
        add_rect(scene, mesh, "fundo_" + name, x, 2.3, 0.2, 4.0, 0.35, (0.12, 0.13, 0.16, 1))
        add_rect(scene, mesh, "bar_" + name, x, 2.3, 0.25, 0.001, 0.35, (0.90, 0.53, 0.16, 1))
        add_text(scene, mat, "lbl_bar_" + name, label, x, 2.3, 0.3, 0.26)
    for k, name in enumerate(("A", "B", "X", "Y", "Start", "RB")):
        x = -3.5 + k * 1.4
        add_rect(scene, mesh, "btn_" + name, x, 1.5, 0.2, 1.0, 0.6, (0.20, 0.24, 0.30, 1))
        add_text(scene, mat, "lbl_btn_" + name, name, x, 1.5, 0.3, 0.26)

    # menu de pausa (escondido ate apertar Start)
    add_rect(scene, mesh, "Menu", 0, -0.9, 0.5, 8.0, 4.6, (0.05, 0.06, 0.08, 1))
    add_text(scene, mat, "lbl_menu", "PAUSA", 0, 0.8, 0.6, 0.5)
    for name, label, x, y in MENU:
        add_rect(scene, mesh, "menu_" + name, x, y, 0.6, 6.0, 1.2, (0.20, 0.24, 0.30, 1))
        add_text(scene, mat, "lbl_" + name, label, x, y, 0.7, 0.45)

    script = bpy.data.texts.new("toque_race.py")
    script.write(CODE)
    ctl = scene.objects["Fundo"]
    scene.objects.active = ctl
    bpy.ops.logic.sensor_add(type='ALWAYS', object=ctl.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=ctl.name)
    sensor = ctl.game.sensors[-1]
    sensor.use_pulse_true_level = True
    controller = ctl.game.controllers[-1]
    controller.mode = 'MODULE'
    controller.module = "toque_race.main"
    sensor.link(controller)

    # Export Web/Android pelo painel ja sai com o layout de corrida.
    if hasattr(scene, "range_web"):
        scene.range_web.touch_layout = 'RACE'

    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("CENA", out)


main()
