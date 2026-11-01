"""Cena de exemplo: cutscene com diálogo, voz opcional e cortes de câmera.

Gerar:  AnastacioEngine.exe -b --factory-startup --python tools/create_cutscene_story_example.py -- cutscene_historia.range
Jogar:  abra o .range e aperte P (ou RangeRuntime cutscene_historia.range).

Roteiro (sequência "Chegada"):
  corte para CamAna  -> Ana fala (espera Enter/clique/botão A)
  corte para CamBeto -> Beto responde (espera)
  corte para CamGeral -> Ana fecha a conversa (espera)
  some a legenda, tiram-se as faixas, volta para CamJogo e libera o jogador.
Começa com faixas de cinema e abrindo do preto. Tab (ou Start no controle) pula.

A legenda é um objeto Text filho da câmera do jogo; a cada corte ela passa
para a câmera ativa (range_cutscene_runtime.camera_cut). "Setup Dialogue"
já está aplicado nela (máquina de escrever + avanço).
Para voz, preencha "Audio" de cada evento Dialog com um .ogg/.wav (caminho //relativo).
"""
import bpy
import math
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "cutscene_historia.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.fps = 60


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


def mesh_object(kind, name, location, scale, color):
    if kind == 'CUBE':
        bpy.ops.mesh.primitive_cube_add(location=location)
    else:
        bpy.ops.mesh.primitive_cylinder_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(material(name, color))
    return obj


def camera(name, location, target):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.object
    cam.name = name
    direction = [t - l for t, l in zip(target, location)]
    dist_xy = math.hypot(direction[0], direction[1])
    cam.rotation_euler = (math.atan2(dist_xy, -direction[2]), 0.0, math.atan2(direction[1], direction[0]) - math.pi / 2)
    return cam


def add_logic(obj, module, text_name=None, code=None):
    if code:
        bpy.data.texts.new(text_name).write(code)
    bpy.ops.logic.sensor_add(type='ALWAYS', object=obj.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=obj.name)
    sensor = obj.game.sensors[-1]
    sensor.use_pulse_true_level = True
    controller = obj.game.controllers[-1]
    controller.mode = 'MODULE'
    controller.module = module
    sensor.link(controller)


# Cenário e personagens.
mesh_object('CUBE', "Chao", (0, 0, -0.05), (10, 10, 0.05), (0.25, 0.45, 0.25))
ana = mesh_object('CYL', "Ana", (-1.2, 0, 0.9), (0.35, 0.35, 0.9), (0.85, 0.3, 0.35))
beto = mesh_object('CYL', "Beto", (1.2, 0, 0.9), (0.35, 0.35, 0.9), (0.3, 0.4, 0.85))
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 8))

# Câmeras: a do jogo e três planos da cutscene.
cam_jogo = camera("CamJogo", (0, -9, 4), (0, 0, 1))
cam_ana = camera("CamAna", (-0.4, -2.6, 1.7), (-1.2, 0, 1.5))
cam_beto = camera("CamBeto", (0.4, -2.6, 1.7), (1.2, 0, 1.5))
cam_geral = camera("CamGeral", (4.5, -4.5, 2.5), (0, 0, 1))
scene.camera = cam_jogo

# Legenda: Text filho da câmera, na parte de baixo da tela.
curve = bpy.data.curves.new("Legenda", 'FONT')
curve.body = ""
curve.size = 0.045
curve.align_x = 'CENTER'
curve.text_boxes[0].width = 0.9
curve.text_boxes[0].x = -0.45
curve.text_boxes[0].height = 3 * curve.size * curve.space_line
legenda = bpy.data.objects.new("Legenda", curve)
scene.objects.link(legenda)
legenda.data.materials.append(material("LegendaMat", (1, 1, 1)))
legenda.parent = cam_jogo
legenda.location = (0.0, -0.1, -1.0)
scene.objects.active = legenda
legenda.select = True
add_logic(legenda, "range_text_dialogue.main")
for name, kind, value in (("td_speed", 'FLOAT', 40.0), ("td_end", 'STRING', "KEEP"), ("td_message", 'STRING', "")):
    bpy.ops.object.game_property_new(type=kind, name=name)
    legenda.game.properties[name].value = value

# Começa a cutscene 0 no 2º quadro.
starter = bpy.data.objects.new("CutsceneStart", None)
scene.objects.link(starter)
add_logic(starter, "cutscene_start.main", "cutscene_start.py", '''import bge

def main(cont):
    own = cont.owner
    if own.get("started"):
        return
    own["started"] = True
    bge.logic.getCurrentScene().play_cutscene(0)
''')

# Roteiro.
bpy.ops.cutscene.sequence_add()
sequence = scene.cutscene_settings.sequences[0]
sequence.name = "Chegada"

STEPS = (
    ("Lock Player", "LOCK_PLAYER", {}),
    ("Faixas", "LETTERBOX", {"letterbox_show": True, "fade_duration": 0.6}),
    ("Abre do preto", "FADE", {"fade_mode": "IN", "fade_duration": 1.0}),
    ("Plano Ana", "CAMERA_SHOT", {"shot_camera": cam_ana}),
    ("Fala Ana 1", "DIALOG", {"dialog_speaker": "Ana", "dialog_text_pt": "Beto! Finalmente você chegou.",
                             "dialog_text_en": "Beto! You finally made it."}),
    ("Plano Beto", "CAMERA_SHOT", {"shot_camera": cam_beto}),
    ("Fala Beto", "DIALOG", {"dialog_speaker": "Beto", "dialog_text_pt": "Desculpa, a estrada estava fechada.",
                            "dialog_text_en": "Sorry, the road was closed."}),
    ("Plano Geral", "CAMERA_SHOT", {"shot_camera": cam_geral}),
    ("Fala Ana 2", "DIALOG", {"dialog_speaker": "Ana", "dialog_text_pt": "Vamos, o barco já vai sair.",
                             "dialog_text_en": "Come on, the boat is about to leave."}),
    ("Esconde fala", "HIDE_DIALOG", {}),
    ("Tira faixas", "LETTERBOX", {"letterbox_show": False, "fade_duration": 0.6}),
    ("Volta câmera", "RESTORE_GAMEPLAY_CAMERA", {}),
    ("Unlock Player", "UNLOCK_PLAYER", {}),
)
for index, (name, kind, props) in enumerate(STEPS):
    bpy.ops.cutscene.event_add(sequence_index=0)
    event = sequence.events[index]
    event.name = name
    event.type = kind
    event.time = 0.5 + 0.4 * index
    if kind == "DIALOG":
        event.dialog_text_object = legenda
        event.dialog_wait = True
    for key, value in props.items():
        setattr(event, key, value)

bpy.ops.wm.save_as_mainfile(filepath=output)
print("[cutscene_historia] salvo em", output)
