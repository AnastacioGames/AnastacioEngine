"""Teste manual (F5 Mouse Look + F6 Sound) numa cena so, com mouse e audio de verdade.

Run with:  RangeEngine -b --python tools/create_logic_manual_test.py -- <output.range> [convert[:MODULE|SCRIPT]]
A camera (Looker) gira com o mouse por um actuator Mouse Look ligado ao Driver (actuator de outro objeto).
O Speaker gira em volta do ponto (0, 8, 0) e tem os 3 actuators Sound, tocados pelo Driver:
  1 = Loop (LOOPEND), 2 = PingPong (LOOPBIDIRECTIONAL), 3 = Pos3D (LOOPSTOP, 3D).
Segure a tecla para tocar; soltar e apertar de novo deve RECOMECAR o som. O tom e uma subida de frequencia,
entao no ping-pong se ouve subir e descer. No 3D o som deve ir de um lado para o outro conforme o Speaker
gira e mudar quando voce vira a camera com o mouse. Esc sai.
"""
import bpy
import math
import os
import struct
import sys
import wave

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_manual_test.range"
convert = len(argv) > 1 and argv[1].startswith("convert")
mode = argv[1].split(":", 1)[1] if convert and ":" in argv[1] else "COMPONENT"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'


def cube(name, loc, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    o.game.physics_type = 'NO_COLLISION'
    return o


bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10))
cube("Floor", (0, 8, -2), (12, 12, 0.2))
cube("Marker", (0, 8, 0), (0.3, 0.3, 0.3))  # centro da orbita do Speaker

bpy.ops.object.camera_add(location=(0, -6, 1), rotation=(math.radians(90), 0, 0))
looker = bpy.context.active_object
looker.name = "Looker"
scene.camera = looker

pivot = bpy.data.objects.new("Pivot", None)
scene.objects.link(pivot)
pivot.location = (0, 8, 0)
speaker = cube("Speaker", (5, 8, 0), (0.6, 0.6, 0.6))
speaker.parent = pivot
speaker.matrix_parent_inverse = pivot.matrix_world.inverted()

# Pivot gira sozinho (bricks proprios).
bpy.ops.logic.sensor_add(type='ALWAYS', name="Spin", object=pivot.name)
bpy.ops.logic.controller_add(type='LOGIC_AND', name="SpinC", object=pivot.name)
bpy.ops.logic.actuator_add(type='MOTION', name="Rot", object=pivot.name)
pivot.game.actuators["Rot"].offset_rotation = (0.0, 0.0, 0.02)
pivot.game.sensors["Spin"].use_pulse_true_level = True
pivot.game.sensors["Spin"].link(pivot.game.controllers["SpinC"])
pivot.game.controllers["SpinC"].link(actuator=pivot.game.actuators["Rot"])

# Tom de 1,5 s subindo de 300 a 900 Hz (audivel no ping-pong), com fade nas pontas.
wav = os.path.join(os.path.dirname(os.path.abspath(output)), "manual_tone.wav")
rate, n = 44100, 66150
samples, phase = [], 0.0
for i in range(n):
    t = i / n
    phase += 2 * math.pi * (300 + 600 * t) / rate
    env = min(1.0, i / 2000, (n - i) / 2000)
    samples.append(struct.pack("<h", int(12000 * env * math.sin(phase))))
with wave.open(wav, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(b"".join(samples))
snd = bpy.data.sounds.load(wav)

driver = cube("Driver", (0, 30, 0))
scene.objects.active = driver


def sensor(owner, type_, name):
    bpy.ops.logic.sensor_add(type=type_, name=name, object=owner.name)
    return owner.game.sensors[name]


def actuator(owner, type_, name):
    bpy.ops.logic.actuator_add(type=type_, name=name, object=owner.name)
    return owner.game.actuators[name]


def wire(cname, sens, act):
    bpy.ops.logic.controller_add(type='LOGIC_AND', name=cname, object=driver.name)
    c = driver.game.controllers[cname]
    sens.link(c)
    c.link(actuator=act)


s_tick = sensor(driver, 'ALWAYS', "Tick")
s_tick.use_pulse_true_level = True
a = actuator(looker, 'MOUSE', "Look")
a.mode = 'LOOK'
a.use_axis_x = True
a.use_axis_y = True
a.sensitivity_x = 2.0
a.sensitivity_y = 1.5
a.threshold_x = 0.0
a.threshold_y = 0.0
a.min_y = -1.0
a.max_y = 1.0
wire("LookC", s_tick, a)

for key, name, mode_, three_d in (('ONE', "Loop", 'LOOPEND', False), ('TWO', "PingPong", 'LOOPBIDIRECTIONAL', False),
                                  ('THREE', "Pos3D", 'LOOPSTOP', True)):
    s = sensor(driver, 'KEYBOARD', "Key" + name)
    s.key = key
    a = actuator(speaker, 'SOUND', name)
    a.sound = snd
    a.mode = mode_
    a.use_sound_3d = three_d
    a.volume = 0.8
    wire("Snd" + name, s, a)

if convert:
    scene.objects.active = driver
    print("CONVERT", driver.name, bpy.ops.logic.convert_to_component(mode=mode))
    todos = [(t.name, ln.strip()) for t in bpy.data.texts for ln in t.as_string().splitlines() if "# TODO:" in ln]
    print("LEFT_AS_BRICK", len(todos), todos)

bpy.ops.wm.save_as_mainfile(filepath=output)
