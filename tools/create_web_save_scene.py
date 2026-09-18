"""Run with RangeEngine -b --python tools/create_web_save_scene.py.

Cena minima para tools/web/verify-save.cjs: no primeiro frame carrega o save 'ci'; se ja existir
token, imprime LOADED, senao grava um token com saveGlobalDict e imprime SAVED.
"""
import bpy
from pathlib import Path

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 320
scene.game_settings.resolution_y = 240

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
cube = bpy.context.object
cube.name = 'SaveProbe'
cube.game.physics_type = 'NO_COLLISION'

script = bpy.data.texts.new('web_save_probe.py')
script.write('''import Range
cont = Range.logic.getCurrentController()
obj = cont.owner
if not obj.get("probed", False):
    obj["probed"] = True
    Range.logic.loadGlobalDict("ci")
    d = Range.logic.globalDict
    if d.get("token") == "anastacio-save-ok" and d.get("nested") == {"n": [1, 2.5, "x"]}:
        print("[web-save] LOADED", flush=True)
    else:
        d["token"] = "anastacio-save-ok"
        d["nested"] = {"n": [1, 2.5, "x"]}
        Range.logic.saveGlobalDict("ci")
        print("[web-save] SAVED", flush=True)
''')
bpy.ops.logic.sensor_add(type='ALWAYS', object=cube.name)
sensor = cube.game.sensors[-1]
bpy.ops.logic.controller_add(type='PYTHON', object=cube.name)
controller = cube.game.controllers[-1]
controller.text = script
sensor.link(controller)

camera = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
scene.objects.link(camera)
camera.location = (0, -8, 0)
camera.rotation_euler = (1.5708, 0, 0)
scene.camera = camera
scene.update()
output = Path(__file__).resolve().parents[1] / 'build-web' / 'bin' / 'web-save.range'
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print('[web-save] saved', str(output))
