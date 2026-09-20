"""Run with RangeEngine -b --python tools/create_web_scene_transition_scene.py.

Jogo de teste de transicao de cenas no runtime Web, para conferir a olho. Cena A: cubo girando.
Cena B: esfera girando. Cena HUD: cone pequeno no canto, como overlay. Teclas: ESPACO alterna A <-> B
(scene.replace); O liga/desliga o HUD (addScene overlay / scene.end). Cada acao imprime "[trans] ..."
(abra com ?debug=1 para ver o log). Saida: build-web/bin/web-scene-transition.range.
"""
import bpy
from pathlib import Path

out_dir = Path(__file__).resolve().parents[1] / 'build-web' / 'bin'
out_dir.mkdir(parents=True, exist_ok=True)

CONTROL = '''import Range
from Range import events
cont = Range.logic.getCurrentController()
obj = cont.owner
scene = Range.logic.getCurrentScene()
if "init" not in obj:
    obj["init"] = 1
    print("[trans] scene %s started" % scene.name, flush=True)
obj.applyRotation((0.0, 0.0, 0.02), False)
if scene.name == "HUD":
    pass
else:
    kb = Range.logic.keyboard.inputs
    if kb[events.SPACEKEY].activated:
        target = "B" if scene.name == "A" else "A"
        print("[trans] replace %s -> %s" % (scene.name, target), flush=True)
        scene.replace(target)
    elif kb[events.OKEY].activated:
        huds = [s for s in Range.logic.getSceneList() if s.name == "HUD"]
        if huds:
            print("[trans] overlay HUD off", flush=True)
            huds[0].end()
        else:
            print("[trans] overlay HUD on", flush=True)
            Range.logic.addScene("HUD", 1)
'''


def add_controller(scene, ob, text_name):
    text = bpy.data.texts.new(text_name)
    text.write(CONTROL)
    scene.objects.active = ob
    bpy.ops.logic.sensor_add(type='ALWAYS', object=ob.name)
    sensor = ob.game.sensors[-1]
    sensor.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', object=ob.name)
    controller = ob.game.controllers[-1]
    controller.text = text
    sensor.link(controller)


def base_scene(scene, name):
    scene.name = name
    scene.render.engine = 'BLENDER_GAME'
    scene.game_settings.resolution_x = 640
    scene.game_settings.resolution_y = 480
    scene.world = bpy.data.worlds.new(name + " world")
    cam = bpy.data.objects.new(name + "Cam", bpy.data.cameras.new(name + "Cam"))
    scene.objects.link(cam)
    cam.location = (0, -10, 0)
    cam.rotation_euler = (1.5708, 0, 0)
    scene.camera = cam
    lamp = bpy.data.objects.new(name + "Sun", bpy.data.lamps.new(name + "Sun", 'SUN'))
    scene.objects.link(lamp)
    lamp.rotation_euler = (0.6, 0.2, 0.4)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene_a = bpy.context.scene
base_scene(scene_a, "A")
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
cube = bpy.context.object
cube.name = "MarkA"
cube.game.physics_type = 'NO_COLLISION'
add_controller(scene_a, cube, "trans_a.py")

scene_b = bpy.data.scenes.new("B")
base_scene(scene_b, "B")
bpy.context.screen.scene = scene_b
bpy.ops.mesh.primitive_uv_sphere_add(location=(0, 0, 0))
sphere = bpy.context.object
sphere.name = "MarkB"
sphere.game.physics_type = 'NO_COLLISION'
add_controller(scene_b, sphere, "trans_b.py")

scene_h = bpy.data.scenes.new("HUD")
base_scene(scene_h, "HUD")
bpy.context.screen.scene = scene_h
bpy.ops.mesh.primitive_cone_add(location=(3.2, 0, 2.2), radius1=0.5, depth=1.0)
cone = bpy.context.object
cone.name = "MarkHUD"
cone.game.physics_type = 'NO_COLLISION'
add_controller(scene_h, cone, "trans_hud.py")

bpy.context.screen.scene = scene_a
output = out_dir / 'web-scene-transition.range'
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print('[web-trans] saved', str(output))
