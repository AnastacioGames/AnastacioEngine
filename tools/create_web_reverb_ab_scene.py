"""Generate a packed Speaker/Reverb Area listening test (two seconds per state)."""
import math
import struct
import wave
from pathlib import Path

import bpy

folder = Path(__file__).resolve().parents[1] / 'build-web' / 'reverb-ab'
folder.mkdir(parents=True, exist_ok=True)
wav = folder / 'reverb-pulses.wav'
rate = 22050
# Continuous harmonic sound; integer frequencies make the one-second loop seamless.
with wave.open(str(wav), 'wb') as stream:
    stream.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
    samples = []
    for i in range(rate):
        t = i / rate
        signal = sum(math.sin(2 * math.pi * f * t) for f in (330, 660, 990)) / 3
        samples.append(struct.pack('<h', int(11000 * signal)))
    stream.writeframes(b''.join(samples))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 800
scene.game_settings.resolution_y = 450
scene.world = bpy.data.worlds.new('Reverb test')
camera = bpy.data.objects.new('Listener', bpy.data.cameras.new('Listener'))
scene.objects.link(camera)
scene.camera = camera
camera.location = (0, 0, 0)
bpy.ops.object.reverb_area_add(preset='CAVERN', shape='BOX', size=5.0)
area = bpy.context.object
area.name = 'CavernArea'
area.reverb_area.gain = 1.0
area.reverb_area.decay_time = 10.0
area.reverb_area.reflections_gain = 3.0
area.reverb_area.late_reverb_gain = 10.0
sound = bpy.data.sounds.load(str(wav))
sound.pack()
data = bpy.data.speakers.new('PulseSpeaker')
data.sound = sound
data.use_sound_3d = True
data.mode = 'LOOPEND'
data.start_init = True
data.volume = 0.65
speaker = bpy.data.objects.new('PulseSpeaker', data)
scene.objects.link(speaker)
speaker.location = (0, 0, -1)

text = bpy.data.texts.new('reverb_ab.py')
text.write('''import Range
scene = Range.logic.getCurrentScene()
owner = Range.logic.getCurrentController().owner
now = Range.logic.getRealTime()
if "start" not in owner:
    owner["start"] = now
elapsed = now - owner["start"]
phase = int(elapsed / 2.0)
wet = phase % 2 == 1
if owner.get("phase", -1) != phase:
    owner["phase"] = phase
    scene.objects["CavernArea"].worldPosition = (0, 0, 0) if wet else (100, 0, 0)
    print("[reverb-ab] SWITCH phase=%d state=%s seconds=%.3f" % (phase, "CAVERNA" if wet else "SECO", elapsed), flush=True)
if owner.get("measured", -1) != phase and elapsed - phase * 2 > 0.25:
    owner["measured"] = phase
    speaker = scene.objects["PulseSpeaker"]
    effect = speaker.GetActiveEffect()
    gain = speaker.reverb_gain
    expected = 1 if wet else 0
    print("[reverb-ab] STATE phase=%d effect=%d gain=%.3f expected=%d %s" % (phase, effect, gain, expected, "PASS" if effect == expected else "FAIL"), flush=True)
''')
bpy.ops.logic.sensor_add(type='ALWAYS', object=camera.name)
sensor = camera.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=camera.name)
controller = camera.game.controllers[-1]
controller.text = text
sensor.link(controller)
scene.update()
bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'reverb-ab.range'))
print('REVERB_AB_SCENE_SAVED', str(folder / 'reverb-ab.range'))
