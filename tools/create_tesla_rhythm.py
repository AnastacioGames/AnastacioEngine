"""Run RangeEngine -b TeslaPiano_Cinematic.range --python this-file.

Creates a separate playable scene, external editable component modules and original WAV.
"""
import bpy
import math
import os
import shutil
import sys
import wave
import numpy as np
from mathutils import Vector

root = os.path.dirname(os.path.abspath(__file__))
modules = os.path.join(root, 'tesla_rhythm')
sys.path.insert(0, modules)
from anastacio_rhythm_core import make_chart, BEAT

folder = os.path.dirname(bpy.data.filepath)
output = os.path.join(folder, 'TeslaPiano_Rhythm.range')
if os.path.abspath(bpy.data.filepath) == os.path.abspath(output):
    raise RuntimeError('Use the cinematic source, not the rhythm output')
for name in ('anastacio_rhythm_core.py', 'anastacio_tesla_rhythm.py'):
    with open(os.path.join(modules, name), encoding='utf8') as stream:
        source = stream.read()
    compile(source, name, 'exec')
    shutil.copy2(os.path.join(modules, name), os.path.join(folder, name))
    text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    text.from_string(source)

# One rendered audio buffer contains silence/count-in, melody and accompaniment.
# The chart and waveform derive from the same timestamps, avoiding timer drift.
rate = 48000
chart = make_chart()
length = chart[-1][0] + 2.5
audio = np.zeros(int(rate * length), dtype=np.float32)
rng = np.random.RandomState(7)
freqs = (261.63, 293.66, 329.63, 349.23, 392.0)
for stamp, lane in chart:
    t = np.arange(int(rate * 0.46), dtype=np.float32) / rate
    phase = (t * freqs[lane]) % 1.0
    spark = (np.exp(-phase / 0.10) - 0.10)
    tone = (0.25 * spark + 0.16 * np.sin(2 * math.pi * freqs[lane] * t))
    tone += 0.07 * rng.uniform(-1, 1, len(t)) * np.exp(-t / 0.015)
    tone *= np.minimum(t / 0.003, 1) * np.exp(-t / 0.15)
    start = round(stamp * rate)
    audio[start:start + len(t)] += tone
for beat in range(int(length / BEAT)):
    stamp = 3.0 + beat * BEAT
    if stamp + 0.20 >= length:
        break
    t = np.arange(int(rate * 0.20), dtype=np.float32) / rate
    kick = np.sin(2 * math.pi * (55 * t + 3 * (1 - np.exp(-t * 30))))
    kick *= np.exp(-t * 25) * 0.10
    start = round(stamp * rate)
    audio[start:start + len(t)] += kick
audio = np.clip(audio * 1.5, -0.95, 0.95)
with wave.open(os.path.join(folder, 'tesla_rhythm.wav'), 'wb') as stream:
    stream.setnchannels(1)
    stream.setsampwidth(2)
    stream.setframerate(rate)
    stream.writeframes((audio * 32767).astype('<i2').tobytes())

scene = bpy.context.scene
cam = scene.camera
# Disable only the old piano text controller in the new scene.
for ob in scene.objects:
    for controller in ob.game.controllers:
        if controller.type == 'PYTHON' and controller.text and controller.text.name == 'piano_tesla.py':
            controller.states = 1 << 29
            print('TESLA_RHYTHM old piano disconnected', ob.name, flush=True)
# The industrial image is a screen backdrop, so it must follow the moving camera.
backdrop = scene.objects.get('Anastacio_Fundo_Industrial')
if backdrop:
    matrix = backdrop.matrix_world.copy()
    backdrop.parent = cam
    backdrop.matrix_parent_inverse = cam.matrix_world.inverted()
    backdrop.matrix_world = matrix
cam.data.game_fx.use_speed_blur = False
cam.data.game_fx.use_directional_blur = False
cam.location = scene.objects['Terminal'].matrix_world.translation + Vector((0, -23, 6))
cam.rotation_euler = (scene.objects['Terminal'].matrix_world.translation - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.active = cam
cam.select = True
assert bpy.ops.logic.python_component_register(
    component_name='anastacio_tesla_rhythm.AnastacioTeslaRhythm') == {'FINISHED'}
assert any(c.name == 'AnastacioTeslaRhythm' for c in cam.game.components)
notes = bpy.data.texts.get('LEIA-ME') or bpy.data.texts.new('LEIA-ME')
notes.from_string('Tesla Rhythm: Python Component AnastacioTeslaRhythm na camera.\n'
                  'A S D F G: pistas. ESPACO: iniciar/pausar. R: reiniciar.\n'
                  'Setas esquerda/direita: offset -/+5ms. Offset positivo atrasa notas.\n'
                  'Musica original de 112 BPM; 16 compassos, notas e acordes.\n'
                  'Edite os modulos Python ao lado do .range ou no Text Editor.\n')
bpy.ops.wm.save_as_mainfile(filepath=output)
print('TESLA_RHYTHM SAVED', output, len(chart), 'notes', flush=True)
