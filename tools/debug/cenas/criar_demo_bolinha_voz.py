"""Demo: a bolinha sobe e desce com a nota cantada e passa pelas barras da melodia.

    AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_demo_bolinha_voz.py -- saida.range

Vale qualquer oitava: homem, mulher ou criança cantam a mesma melodia.  A
propriedade midi_teste da câmera (>= 0) substitui o microfone nos testes.
"""

import math
import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1]
scene = bpy.context.scene
for obj in list(scene.objects):
    if obj.type == "MESH":
        scene.objects.unlink(obj)
        bpy.data.objects.remove(obj)


def material(nome):
    mat = bpy.data.materials.new(nome)
    mat.use_shadeless = True
    mat.use_object_color = True
    return mat


def malha(nome, verts, faces):
    mesh = bpy.data.meshes.new(nome)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.materials.append(material(nome))
    obj = bpy.data.objects.new(nome, mesh)
    scene.objects.link(obj)
    return obj


QUADRO = [(-0.5, 0, -0.5), (0.5, 0, -0.5), (0.5, 0, 0.5), (-0.5, 0, 0.5)]
N = 28
bola_verts = [(0.5 * math.cos(math.tau * i / N), 0, 0.5 * math.sin(math.tau * i / N)) for i in range(N)]

fundo = malha("Fundo", QUADRO, [(0, 1, 2, 3)])
fundo.location = (0, 2, 0)
fundo.scale = (40, 1, 24)
fundo.color = (0.04, 0.05, 0.12, 1.0)

for i in range(16):
    barra = malha("Barra%02d" % i, QUADRO, [(0, 1, 2, 3)])
    barra.location = (40, 1, 0)

bola = malha("Bolinha", bola_verts, [tuple(range(N))])
bola.location = (-7, 0, 0)
bola.scale = (1.1, 1, 1.1)
bola.color = (0.5, 0.5, 0.6, 1.0)


def texto(nome, x, z, tamanho):
    curve = bpy.data.curves.new(nome, "FONT")
    curve.size = tamanho
    obj = bpy.data.objects.new(nome, curve)
    obj.data.materials.append(material(nome))
    obj.color = (1, 1, 1, 1)
    obj.location = (x, -1, z)
    obj.rotation_euler = (math.pi / 2, 0, 0)
    scene.objects.link(obj)
    obj.game.properties  # garante os dados de jogo
    return obj


texto("Placar", -11.5, 5.4, 0.9)
texto("Nota", 6.5, 5.4, 0.9)

cam = scene.camera
cam.data.type = "ORTHO"
cam.data.ortho_scale = 24
cam.location = (0, -20, 0)
cam.rotation_euler = (math.pi / 2, 0, 0)

SCRIPT = '''
import Range
from Range import logic, audio
import range_ui_runtime

CENTRO = 60            # dó central: meio da tela
ALTURA = 0.72          # unidades por semitom
BOLA_X = -7.0
VELOCIDADE = 4.0       # unidades por segundo
ENTRADA = 3.0          # segundos antes da primeira nota

# Melodia original: (semitons a partir do centro, duração em segundos).
MELODIA = [(-3, 1.0), (0, 1.0), (2, 1.0), (4, 2.0), (2, 1.0), (0, 1.0), (-3, 2.0),
           (-5, 1.0), (-3, 1.0), (0, 1.0), (2, 2.0), (4, 1.0), (7, 1.0), (4, 2.0),
           (2, 1.0), (0, 1.0), (-3, 1.0), (0, 3.0)]
CICLO = sum(d for _, d in MELODIA)
SILENCIO = 0.15        # respiro entre as barras

COR_BARRA = (0.25, 0.45, 0.95, 1.0)
COR_ACERTO = (0.25, 0.9, 0.4, 1.0)
COR_BOLA = (1.0, 0.75, 0.15, 1.0)
COR_MUDA = (0.45, 0.45, 0.55, 1.0)


def nota_no_alcance(midi, alvo):
    """Dobra a oitava: a voz vale na altura mais perto do alvo."""
    return midi + 12.0 * round((alvo - midi) / 12.0)


def notas_a_partir(t):
    """(início, duração, semitom) das notas que cobrem a tela a partir de t."""
    voltas = int(max(0.0, t - ENTRADA - 4.0) // CICLO)
    inicio = ENTRADA + voltas * CICLO
    saida = []
    while inicio < t + 26.0 / VELOCIDADE:
        for semitom, duracao in MELODIA:
            saida.append((inicio, duracao, semitom))
            inicio += duracao
    return saida


class Estado:
    pass


E = Estado()
E.t = None
E.z = 0.0
E.pontos = 0.0
E.acertou = set()


def main(cont):
    own = cont.owner
    cena = logic.getCurrentScene()
    agora = logic.getFrameTime() if hasattr(logic, "getFrameTime") else 0.0
    if E.t is None:
        E.t = agora
        E.anterior = agora
        range_ui_runtime._start_microphone()
    dt = min(0.1, agora - E.anterior)
    E.anterior = agora
    t = agora - E.t

    teste = own.get("midi_teste", -1)
    if teste >= 0:
        midi, cents = float(teste), 0.0
        nome = "teste"
    else:
        nome, cents, midi_int = audio.microphoneNote()
        midi = midi_int + cents / 100.0 if nome else None

    atual = None
    barras = sorted((o for o in cena.objects if o.name.startswith("Barra")), key=lambda o: o.name)
    notas = [n for n in notas_a_partir(t) if BOLA_X + (n[0] + n[1] - t) * VELOCIDADE > -13.0][:len(barras)]
    for barra, (inicio, duracao, semitom) in zip(barras, notas):
        largura = (duracao - SILENCIO) * VELOCIDADE
        barra.worldPosition = (BOLA_X + (inicio - t) * VELOCIDADE + largura * 0.5, 1.0, semitom * ALTURA)
        barra.localScale = (largura, 1.0, ALTURA * 0.9)
        barra.color = COR_ACERTO if inicio in E.acertou else COR_BARRA
        if inicio <= t < inicio + duracao - SILENCIO:
            atual = (inicio, semitom)
    for barra in barras[len(notas):]:
        barra.worldPosition = (40.0, 1.0, 0.0)

    bola = cena.objects["Bolinha"]
    if midi is not None:
        referencia = CENTRO + (atual[1] if atual else E.z / ALTURA)
        semitons = nota_no_alcance(midi, referencia) - CENTRO
        alvo = max(-9.0, min(9.0, semitons)) * ALTURA
        E.z += (alvo - E.z) * min(1.0, dt * 18.0)
        bola.color = COR_BOLA
        if atual and abs(semitons - atual[1]) <= 1.0:
            E.pontos += dt * 10.0
            E.acertou.add(atual[0])
            bola.color = COR_ACERTO
    else:
        bola.color = COR_MUDA
    bola.worldPosition = (BOLA_X, 0.0, E.z)

    own["pontos"] = E.pontos
    cena.objects["Placar"].text = "Pontos: %d" % E.pontos
    cena.objects["Nota"].text = nome or "Cante!"
'''

texto_jogo = bpy.data.texts.new("bolinha.py")
texto_jogo.from_string(SCRIPT)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type="ALWAYS", object=cam.name)
bpy.ops.logic.controller_add(type="PYTHON", object=cam.name)
sensor, controller = cam.game.sensors[-1], cam.game.controllers[-1]
sensor.use_pulse_true_level = True
controller.mode = "MODULE"
controller.module = "bolinha.main"
sensor.link(controller)
for nome, tipo, valor in (("midi_teste", "FLOAT", -1.0), ("pontos", "FLOAT", 0.0)):
    bpy.ops.object.game_property_new(type=tipo, name=nome)
    cam.game.properties[nome].value = valor

bpy.ops.wm.save_as_mainfile(filepath=out, relative_remap=True)
print("BOLINHA_OK", out)
