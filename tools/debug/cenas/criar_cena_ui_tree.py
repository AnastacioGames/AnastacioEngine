"""Cena de teste do protótipo UI Tree.

    AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_ui_tree.py -- saida.range

Monta duas telas (Frames "Menu" e "Opcoes") com botões ligados a ações,
grava o Bake e liga Always + Python (range_ui_tree.main) na câmera.
"""

import sys

import bpy
import range_ui_tree as ui

out = sys.argv[sys.argv.index("--") + 1]

tree = bpy.data.node_groups.new("Menu UI", ui.UITree.bl_idname)
tree.use_fake_user = True


def frame(name, x, y):
    node = tree.nodes.new("NodeFrame")
    node.name = node.label = name
    node.shrink = False
    node.location = (x, y)
    node.width, node.height = 640, 360  # 16:9
    return node


def button(parent, text, x, y):
    node = tree.nodes.new(ui.UIButtonNode.bl_idname)
    node.text = text
    node.parent = parent
    node.location = (x, y)  # relativo ao Frame, y para baixo é negativo
    node.width = 200
    return node


def action(kind, value, x, y):
    node = tree.nodes.new(kind.bl_idname)
    node.value = value
    node.location = (x, y)
    return node


def link(src, event, dst):
    tree.links.new(src.outputs[event], dst.inputs[0])


menu = frame("Menu", 0, 0)
opcoes = frame("Opcoes", 0, -500)

jogar = button(menu, "Jogar", 220, -120)
btn_opcoes = button(menu, "Opções", 220, -170)
sair = button(menu, "Sair", 220, -220)
voltar = button(opcoes, "Voltar", 220, -280)

# Estilos variados para conferir a prévia e o jogo.
jogar.shadow = True
jogar.button_height = 48
btn_opcoes.radius = 0.3
btn_opcoes.border = 0.05
sair.radius = 0.0
sair.color = (0.55, 0.12, 0.12, 0.9)
sair.hover_color = (0.8, 0.2, 0.2, 1.0)
voltar.align = "LEFT"

link(jogar, "On Enter", action(ui.UIPrintNode, "mouse entrou em Jogar", 800, 0))
link(jogar, "On Click", action(ui.UIPrintNode, "clicou Jogar", 800, -100))
link(btn_opcoes, "On Click", action(ui.UIScreenNode, "Opcoes", 800, -200))
link(sair, "On Click", action(ui.UIQuitNode, "", 800, -300))
link(voltar, "On Click", action(ui.UIScreenNode, "Menu", 800, -600))

data = ui.bake_tree(tree)
text = bpy.data.texts.new(ui.DATA_TEXT)
text.from_string("DATA = %r\n" % data)
for screen in data["screens"]:
    for b in screen["buttons"]:
        print("UI_BAKE", screen["name"], b["text"], tuple(round(v, 3) for v in b["rect"]),
              sorted(b["events"]))

scene = bpy.context.scene
cam = scene.camera
bpy.context.scene.objects.active = cam
bpy.ops.logic.sensor_add(type="ALWAYS", object=cam.name)
bpy.ops.logic.controller_add(type="PYTHON", object=cam.name)
sensor, controller = cam.game.sensors[-1], cam.game.controllers[-1]
sensor.use_pulse_true_level = True
controller.mode = "MODULE"
controller.module = "range_ui_tree.main"
sensor.link(controller)

bpy.ops.wm.save_as_mainfile(filepath=out)
print("UI_OK", out)
