"""Rain test scene for the native World > Rain > Splash and Aura effects.
Run with:  RangeEngine -b --python tools/create_rain_splash_scene.py -- <output.range> [auto_quit]
In game: 1 splash on/off, UP/DOWN splash size, LEFT/RIGHT splash rate,
3 aura on/off, W/S aura size, A/D aura amount, O camera orbit,
R lightning now, T automatic lightning on/off, C look at the sky (World > Rain > Lightning).
The keys only call scene.world.setWeather(); everything else is in the engine.
"""

import bpy
import sys
import math

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "rain_splash_test.range"
auto_quit = len(argv) > 1 and argv[1] == "auto_quit"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 960
scene.game_settings.resolution_y = 540

world = bpy.data.worlds.new("Rain World")
world.horizon_color = (0.025, 0.028, 0.035)
world.zenith_color = (0.02, 0.022, 0.03)
scene.world = world
weather = world.weather_settings
weather.use_rain = True
weather.rain_intensity = 0.6
weather.use_rain_droplets = True
weather.use_rain_ripple = True
weather.rain_darken = 0.3
weather.rain_streak_width = 0.35
weather.use_rain_splash = True
weather.rain_splash_distance = 12.0
weather.use_rain_aura = True
weather.rain_aura_property = "aura_chuva"
weather.use_rain_lightning = True
weather.rain_lightning_rate = 7.0


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.specular_intensity = 0.4
    return mat


bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
ground = bpy.context.object
ground.name = "Ground"
ground.scale = (10, 10, 1)
ground.data.materials.append(material("GroundMat", (0.18, 0.18, 0.2)))

# Objects with flat tops, thin edges and curved tops.
def add(op, name, loc, scale, color, **kw):
    op(location=loc, **kw)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(material(name + "Mat", color))
    return ob

add(bpy.ops.mesh.primitive_cube_add, "Caixa", (0, 0, 0.4), (0.4, 0.4, 0.4), (0.7, 0.25, 0.1))
add(bpy.ops.mesh.primitive_cube_add, "Banco", (-1.2, 0.4, 0.45), (0.6, 0.2, 0.03), (0.45, 0.3, 0.15))
add(bpy.ops.mesh.primitive_cube_add, "PeBanco", (-1.2, 0.4, 0.21), (0.05, 0.15, 0.21), (0.3, 0.3, 0.3))
add(bpy.ops.mesh.primitive_uv_sphere_add, "Bola", (1.1, 0.3, 0.35), (0.35, 0.35, 0.35), (0.1, 0.6, 0.9))
add(bpy.ops.mesh.primitive_cylinder_add, "Tambor", (0.4, 1.2, 0.5), (0.3, 0.3, 0.5), (0.2, 0.5, 0.2))
add(bpy.ops.mesh.primitive_cube_add, "Carro", (-0.3, 2.0, 0.35), (0.9, 0.45, 0.2), (0.8, 0.8, 0.85))

bpy.ops.object.lamp_add(type='SUN', location=(2, -2, 5), rotation=(math.radians(40), 0, math.radians(30)))
bpy.context.object.data.energy = 1.0
bpy.context.object.name = "Sol"

# Camera on a pivot that can orbit around the scene.
bpy.ops.object.empty_add(location=(0, 0.6, 0.3))
pivot = bpy.context.object
pivot.name = "Pivo"
bpy.ops.object.camera_add(location=(0, -2.4, 1.5), rotation=(math.radians(62), 0, 0))
cam = bpy.context.object
cam.name = "CameraChuva"
cam.data.clip_start = 0.05
cam.data.clip_end = 400.0
cam.parent = pivot
cam.location = (0, -3.0, 1.2)
scene.camera = cam

controller = """import Range
import math
from mathutils import Matrix

AUTO_QUIT = %s

logic = Range.logic
cam = logic.getCurrentController().owner
world = logic.getCurrentScene().world
ev = Range.events
hit = lambda k: logic.keyboard.events.get(k) == logic.KX_INPUT_JUST_ACTIVATED

if "splash" not in cam:
    for k, v in dict(splash=True, ssize=1.0, srate=0.9, aura=True, asize=1.0, arate=0.6, orbit=True, frame=0, raio=True, sky=False).items():
        cam[k] = v
    print("[chuva] 1 respingo, setas tamanho/frequencia | 3 aura, W/S tamanho, A/D quantidade | O orbita | R raio, T raio automatico, C ceu", flush=True)

def change(name, key, factor, lo, hi, setting):
    cam[name] = min(max(cam[name] * factor, lo), hi)
    world.setWeather(setting, cam[name])
    print("[chuva] %%s %%.2f" %% (setting, cam[name]), flush=True)

if hit(ev.ONEKEY):
    cam["splash"] = not cam["splash"]
    world.setWeather("splash", cam["splash"])
if hit(ev.THREEKEY):
    cam["aura"] = not cam["aura"]
    world.setWeather("aura", cam["aura"])
if hit(ev.UPARROWKEY): change("ssize", 0, 1.5, 0.3, 6.0, "splash_size")
if hit(ev.DOWNARROWKEY): change("ssize", 0, 1 / 1.5, 0.3, 6.0, "splash_size")
if hit(ev.RIGHTARROWKEY): change("srate", 0, 1.4, 0.1, 6.0, "splash_rate")
if hit(ev.LEFTARROWKEY): change("srate", 0, 1 / 1.4, 0.1, 6.0, "splash_rate")
if hit(ev.WKEY): change("asize", 0, 1.3, 0.3, 5.0, "aura_size")
if hit(ev.SKEY): change("asize", 0, 1 / 1.3, 0.3, 5.0, "aura_size")
if hit(ev.DKEY): change("arate", 0, 1.3, 0.1, 3.0, "aura_rate")
if hit(ev.AKEY): change("arate", 0, 1 / 1.3, 0.1, 3.0, "aura_rate")
if hit(ev.OKEY):
    cam["orbit"] = not cam["orbit"]
if hit(ev.RKEY):
    world.strikeLightning()
if hit(ev.TKEY):
    cam["raio"] = not cam["raio"]
    world.setWeather("lightning", cam["raio"])
    print("[chuva] raio automatico", cam["raio"], flush=True)
if hit(ev.CKEY):
    cam["sky"] = not cam["sky"]
    cam.localOrientation = Matrix.Rotation(math.radians(95 if cam["sky"] else 62), 3, "X")

if cam["orbit"]:
    cam.parent.applyRotation((0.0, 0.0, 0.004), False)

cam["frame"] += 1
if AUTO_QUIT and cam["frame"] == 60:
    world.setWeather("aura_size", 1.2)
if AUTO_QUIT and cam["frame"] == 90:
    world.strikeLightning()
if AUTO_QUIT and cam["frame"] == 100:
    Range.render.makeScreenshot("C:/Users/f_bro/AppData/Local/Temp/chuva_shot.png")
if AUTO_QUIT and cam["frame"] == 120:
    print("[chuva] ok frame 120 fps=%%.1f" %% logic.getAverageFrameRate(), flush=True)
    logic.endGame()
""" % ("True" if auto_quit else "False")

text = bpy.data.texts.new("rain_splash.py")
text.write(controller)
bpy.context.scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
cam.game.sensors[-1].use_pulse_true_level = True
cam.game.controllers[-1].text = text
cam.game.sensors[-1].link(cam.game.controllers[-1])

# Objects that get the aura: game property "aura_chuva" = True.
for name in ("Caixa", "Banco", "Bola", "Tambor", "Carro"):
    ob = bpy.data.objects[name]
    bpy.context.scene.objects.active = ob
    bpy.ops.object.game_property_new(type='BOOL', name="aura_chuva")
    ob.game.properties["aura_chuva"].value = True

bpy.ops.wm.save_as_mainfile(filepath=output)
print("saved", output)
