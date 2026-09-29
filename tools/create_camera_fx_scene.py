"""Camera FX test scene: focus sensor, tracking, Camera FX filters and shake.

Run with:  RangeEngine -b --python tools/create_camera_fx_scene.py -- <output.range> [auto_quit]
With auto_quit the game prints the focus values, removes the target and quits by itself.
"""
import bpy
import sys
import math

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "camera_fx_test.range"
auto_quit = len(argv) > 1 and argv[1] == "auto_quit"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 960
scene.game_settings.resolution_y = 540
world = bpy.data.worlds.new("CameraFX World")
world.horizon_color = (0.35, 0.5, 0.7)
scene.world = world


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


bpy.ops.mesh.primitive_plane_add(location=(0, 20, 0))
ground = bpy.context.object
ground.name = "Ground"
ground.scale = (30, 40, 1)
ground.data.materials.append(material("GroundMat", (0.3, 0.3, 0.3)))

# Scenery at many depths to see the depth of field and the speed blur.
for i in range(12):
    bpy.ops.mesh.primitive_cube_add(location=((-1) ** i * 4, i * 5 - 5, 1))
    pillar = bpy.context.object
    pillar.name = "Pillar.%02d" % i
    pillar.scale = (0.6, 0.6, 1 + (i % 3))
    pillar.data.materials.append(material("PillarMat%d" % i, (0.9, 0.3 + 0.05 * i, 0.1)))

# Focus target: marked by the property "foco" = True and moving side to side.
bpy.ops.mesh.primitive_uv_sphere_add(location=(0, 12, 1))
target = bpy.context.object
target.name = "Alvo"
target.data.materials.append(material("AlvoMat", (0.1, 0.8, 1.0)))
bpy.ops.object.game_property_new(type='BOOL', name="foco")
target.game.properties["foco"].value = True

mover = bpy.data.texts.new("alvo_move.py")
mover.write('''import Range, math
own = Range.logic.getCurrentController().owner
t = own.get("t", 0.0) + 1.0 / 60.0
own["t"] = t
own.worldPosition = (math.sin(t * 0.8) * 6.0, 12.0 + math.cos(t * 0.5) * 6.0, 1.0)
''')
bpy.context.scene.objects.active = target
bpy.ops.logic.sensor_add(type='ALWAYS', object=target.name)
bpy.ops.logic.controller_add(type='PYTHON', object=target.name)
target.game.sensors[-1].use_pulse_true_level = True
target.game.controllers[-1].text = mover
target.game.sensors[-1].link(target.game.controllers[-1])

# Camera with every feature on.
bpy.ops.object.camera_add(location=(0, -8, 3), rotation=(math.radians(80), 0, 0))
cam = bpy.context.object
cam.name = "CameraFX"
scene.camera = cam
fx = cam.data.game_fx
fx.focus_mode = 'PROPERTY'
fx.focus_property = "foco"
fx.focus_range = 2.0
fx.track_mode = 'DRONE'
fx.track_speed = 0.3
fx.track_screen_offset = (0.0, -0.1)
fx.use_dof = True
fx.dof_quality = 'MEDIUM'
fx.dof_blur = 8.0
fx.use_cat_eye = True
fx.use_speed_blur = True
fx.use_directional_blur = True
fx.use_chromatic = True
fx.use_vignette = True
fx.fisheye_strength = 0.1
cam.data.gpu_dof.blades = 6

probe = bpy.data.texts.new("camera_probe.py")
probe.write('''import Range
cam = Range.logic.getCurrentController().owner
frame = cam.get("frame", 0) + 1
cam["frame"] = frame
AUTO_QUIT = %s
if frame %% 30 == 0:
    target = cam.focusTarget
    print("[camfx] frame=%%d target=%%s valid=%%s dist=%%.2f pos=%%s screen=%%s speed=%%.2f trauma=%%.2f"
          %% (frame, target.name if target else None, cam.focusValid, cam.focusDistance,
             [round(v, 2) for v in cam.focusPosition], [round(v, 2) for v in cam.focusScreenPosition],
             cam.cameraSpeed, cam.shakeTrauma), flush=True)
if frame == 60:
    cam.shake(0.8, 1.5)
if frame == 150 and AUTO_QUIT:
    scene = Range.logic.getCurrentScene()
    alvo = scene.objects.get("Alvo")
    if alvo:
        alvo.endObject()
        print("[camfx] target removed", flush=True)
if frame == 200 and AUTO_QUIT:
    cam.useDof = False
    cam.useSpeedBlur = cam.useDirectionalBlur = cam.useChromatic = cam.useVignette = False
    print("[camfx] effects off", flush=True)
if frame == 260 and AUTO_QUIT:
    print("[camfx] done", flush=True)
    Range.logic.endGame()
''' % ("True" if auto_quit else "False"))
bpy.context.scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
cam.game.sensors[-1].use_pulse_true_level = True
cam.game.controllers[-1].text = probe
cam.game.sensors[-1].link(cam.game.controllers[-1])

bpy.ops.wm.save_as_mainfile(filepath=output)
print("saved", output)
