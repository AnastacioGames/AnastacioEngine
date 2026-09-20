"""Run with RangeEngine -b --python tools/create_web_music_scene.py.

Jogo de teste de MP3 no runtime Web: um Sound Actuator toca em loop um MP3 empacotado no .range
(padrao projects-teste/music/Anastacio Music.mp3; outro arquivo via variavel MUSIC_MP3). Depende do
leitor MP3 embutido do Audaspace (plugins/mp3). Saida: build-web/bin/web-music.range.
"""
import os
import bpy
from mathutils import Vector
from pathlib import Path

out_dir = Path(__file__).resolve().parents[1] / 'build-web' / 'bin'
out_dir.mkdir(parents=True, exist_ok=True)

mp3_path = Path(os.environ.get('MUSIC_MP3') or Path(__file__).resolve().parents[1] / 'projects-teste' / 'music' / 'Anastacio Music.mp3')

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = 'Music'
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 640
scene.game_settings.resolution_y = 480
scene.world = bpy.data.worlds.new('Music world')

cam = bpy.data.objects.new('AudioCam', bpy.data.cameras.new('AudioCam'))
scene.objects.link(cam)
cam.location = (0, -10, 4)
cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam
lamp = bpy.data.objects.new('AudioSun', bpy.data.lamps.new('AudioSun', 'SUN'))
scene.objects.link(lamp)

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
cube = bpy.context.object
cube.name = 'Source'
cube.game.physics_type = 'NO_COLLISION'

sound = bpy.data.sounds.load(str(mp3_path))
sound.pack()

script = bpy.data.texts.new('audio.py')
script.write('''import Range
cont = Range.logic.getCurrentController()
obj = cont.owner
tick = obj.get("tick", 0) + 1
obj["tick"] = tick
if tick == 1:
    print("[aud] scene running", flush=True)
elif tick == 30:
    cont.activate(cont.actuators["Snd"])
    print("[aud] sound actuator activated", flush=True)
elif tick == 200:
    print("[aud] still alive after 200 ticks", flush=True)
''')
bpy.ops.logic.sensor_add(type='ALWAYS', object=cube.name)
sensor = cube.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=cube.name)
controller = cube.game.controllers[-1]
controller.text = script
sensor.link(controller)
bpy.ops.logic.actuator_add(type='SOUND', object=cube.name)
act = cube.game.actuators[-1]
act.name = 'Snd'
act.sound = sound
act.mode = 'LOOPEND'
controller.link(actuator=act)

output = out_dir / 'web-music.range'
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print('[web-music] saved', str(output))
