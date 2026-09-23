"""Run with RangeEngine -b --python tools/create_web_aud_module_scene.py.

Jogo de teste do modulo Python `aud` no runtime Web: o script importa aud, cria um aud.Device,
toca tons gerados (Sound.sine + limit) e ajusta volume/pitch do Handle. Imprime "[aud] ..." (use
?debug=1). Sound.data()/buffer() dependem de numpy e nao existem no Web. Saida: build-web/bin/web-aud-module.range.
"""
import bpy
from mathutils import Vector
from pathlib import Path

out_dir = Path(__file__).resolve().parents[1] / 'build-web' / 'bin'
out_dir.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = 'Audio'
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 640
scene.game_settings.resolution_y = 480
scene.world = bpy.data.worlds.new('Audio world')

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


script = bpy.data.texts.new('audio.py')
script.write('''import Range
import aud
cont = Range.logic.getCurrentController()
obj = cont.owner
tick = obj.get("tick", 0) + 1
obj["tick"] = tick
if tick == 1:
    print("[aud] modulo aud importado: %s" % [n for n in ("Sound", "Device", "Handle") if hasattr(aud, n)], flush=True)
elif tick == 20:
    obj["dev"] = aud.Device()
    print("[aud] Device criado: %s" % type(obj["dev"]).__name__, flush=True)
elif tick == 30:
    sound = aud.Sound.sine(440).limit(0, 1.5)
    obj["h1"] = obj["dev"].play(sound)
    print("[aud] play sine 440 status=%s" % obj["h1"].status, flush=True)
elif tick == 120:
    h = obj["dev"].play(aud.Sound.sine(660).limit(0, 1.5))
    h.volume = 0.5
    h.pitch = 1.5
    obj["h2"] = h
    print("[aud] play sine 660 volume=%.1f pitch=%.1f" % (h.volume, h.pitch), flush=True)
elif tick == 300:
    print("[aud] status h1=%s h2=%s" % (obj["h1"].status, obj["h2"].status), flush=True)
    print("[aud] aud OK", flush=True)
''')

bpy.ops.logic.sensor_add(type='ALWAYS', object=cube.name)
sensor = cube.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=cube.name)
controller = cube.game.controllers[-1]
controller.text = script
sensor.link(controller)
output = out_dir / 'web-aud-module.range'
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print('[web-audio] saved', str(output))
