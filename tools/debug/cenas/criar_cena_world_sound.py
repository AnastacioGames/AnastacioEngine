# Cena de teste do World Sound (gerenciador de audio nativo).
#
# Duas cenas: "A" usa um World com os modulos Music (duas faixas, Play on Start) e Ambient (uma camada);
# "B" usa outro World, sem modulos. Um controlador Python registra o estado de Range.audio num arquivo, troca
# de A para B e encerra o jogo. O que a troca prova: os modulos continuam registrados (e tocando) na cena B.
#
# Uso:
#   AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_world_sound.py -- <pasta>
# Gera <pasta>/world_sound.range e <pasta>/audio/*.wav. O jogo grava o log no caminho da variavel de ambiente
# WORLD_SOUND_LOG (sem ela, world_sound_log.txt ao lado do .range). WORLD_SOUND_SECONDS (padrao 8) e a duracao;
# a troca de cena acontece em um quarto dela.

import math
import os
import struct
import sys
import wave

import bpy

GAME_SCRIPT = '''
import os
import time

import bge

def _log(text):
    path = os.environ.get("WORLD_SOUND_LOG") or bge.logic.expandPath("//world_sound_log.txt")
    with open(path, "a") as out:
        out.write(text + "\\n")

def tick(cont):
    audio = bge.audio
    state = bge.logic.globalDict.setdefault("world_sound", {"start": time.time(), "last": -1.0, "swapped": False})
    scene = bge.logic.getCurrentScene()
    elapsed = time.time() - state["start"]
    total = float(os.environ.get("WORLD_SOUND_SECONDS", "8"))

    if state["last"] < 0.0:
        _log("# inicio cena=%s modulos=%s" % (scene.name, audio.modules()))
        _log("# sons Music=%s Ambient=%s" % (audio.sounds("Music"), audio.sounds("Ambient")))
        _log("# volume Music=%s inexistente=%s" % (audio.getVolume("Music"), audio.getVolume("Nada")))
        _log("# play inexistente=%s som inexistente=%s" % (audio.play("Nada"), audio.play("Music", "nada")))

    if elapsed - state["last"] >= 0.25:
        state["last"] = elapsed
        _log("t=%.2f cena=%s music=%s ambient=%s" % (elapsed, scene.name, audio.playing("Music"),
                                                    audio.playing("Ambient")))

    if not state["swapped"] and elapsed >= total * 0.25:
        state["swapped"] = True
        _log("# troca de cena A -> B")
        scene.replace("B")
    elif elapsed >= total * 0.6 and not state.get("stepped"):
        state["stepped"] = True
        _log("# next=%s setVolume=%s volume=%s" % (audio.next("Music"), audio.setVolume("Music", 0.5),
                                                   audio.getVolume("Music")))
    elif elapsed >= total * 0.8 and not state.get("stopped"):
        state["stopped"] = True
        _log("# stop Ambient=%s pause Music=%s" % (audio.stop("Ambient"), audio.pause("Music")))
    elif elapsed >= total:
        _log("# fim cena=%s modulos=%s" % (scene.name, audio.modules()))
        bge.logic.endGame()
'''


def write_tone(path, frequency, seconds, tremolo=0.0):
    rate = 22050
    frames = bytearray()
    for i in range(int(rate * seconds)):
        t = i / rate
        gain = 0.35 * (1.0 - tremolo * (0.5 + 0.5 * math.sin(2.0 * math.pi * 3.0 * t)))
        frames += struct.pack('<h', int(32767 * gain * math.sin(2.0 * math.pi * frequency * t)))
    out = wave.open(path, 'wb')
    out.setnchannels(1)
    out.setsampwidth(2)
    out.setframerate(rate)
    out.writeframes(bytes(frames))
    out.close()


def add_logger(scene, name):
    obj = bpy.data.objects.new(name, None)
    scene.objects.link(obj)
    # A cena B nao e a do contexto: os operadores recebem o objeto por override.
    override = {'scene': scene, 'object': obj, 'active_object': obj}
    bpy.ops.logic.sensor_add(override, type='ALWAYS', name="Always", object=obj.name)
    bpy.ops.logic.controller_add(override, type='PYTHON', name="Tick", object=obj.name)
    sensor = obj.game.sensors["Always"]
    sensor.use_pulse_true_level = True
    controller = obj.game.controllers["Tick"]
    controller.mode = 'MODULE'
    controller.module = "wslog.tick"
    sensor.link(controller)

    camera = bpy.data.objects.new(name + "Camera", bpy.data.cameras.new(name + "Camera"))
    camera.location = (0.0, -6.0, 2.0)
    camera.rotation_euler = (math.radians(75.0), 0.0, 0.0)
    scene.objects.link(camera)
    scene.camera = camera


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not args:
        print("uso: ... --python criar_cena_world_sound.py -- <pasta de saida>")
        sys.exit(2)
    folder = os.path.abspath(args[0])
    audio = os.path.join(folder, "audio")
    os.makedirs(audio, exist_ok=True)

    # Faixas curtas (2 s) para a playlist avancar sozinha dentro do teste.
    write_tone(os.path.join(audio, "tema1.wav"), 440.0, 2.0)
    write_tone(os.path.join(audio, "tema2.wav"), 660.0, 2.0)
    write_tone(os.path.join(audio, "vento.wav"), 110.0, 1.0, tremolo=0.8)

    text = bpy.data.texts.new("wslog.py")
    text.write(GAME_SCRIPT)

    scene_a = bpy.context.scene
    scene_a.name = "A"
    for obj in list(scene_a.objects):
        scene_a.objects.unlink(obj)
    scene_a.render.engine = 'BLENDER_GAME'

    world_a = bpy.data.worlds.new("WorldSom")
    scene_a.world = world_a
    music = world_a.sound_modules.new("Music", type='MUSIC')
    music.fade_time = 0.5
    music.sounds.new("tema1", filepath="//audio/tema1.wav")
    music.sounds.new("tema2", filepath="//audio/tema2.wav")
    ambient = world_a.sound_modules.new("Ambient", type='AMBIENT')
    ambient.volume = 0.6
    if hasattr(ambient, "use_reverb_areas"):  # editor anterior a opcao
        ambient.use_reverb_areas = True
    ambient.sounds.new("vento", filepath="//audio/vento.wav")

    scene_b = bpy.data.scenes.new("B")
    scene_b.render.engine = 'BLENDER_GAME'
    scene_b.world = bpy.data.worlds.new("WorldSemSom")

    add_logger(scene_a, "LoggerA")
    add_logger(scene_b, "LoggerB")

    path = os.path.join(folder, "world_sound.range")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print("cena salva:", path)


main()
