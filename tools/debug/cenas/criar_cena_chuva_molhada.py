# Cena de teste do Rain > Wet Surfaces (superficies molhadas que secam).
#   Piso, parede vermelha, cubos coloridos e uma rampa, sol e camera fixa.
#   Automatico: 2 s seco (foto 1), chove 5 s (foto 2 molhado), para a chuva com
#   Dry Time 3 s e espera 5 s (foto 3 seco de novo), grava resultado.txt e fecha.
#   As gotas ficam desligadas no automatico para a foto 1 e a 3 poderem ser comparadas
#   pixel a pixel (o seco final tem que ser igual ao seco inicial).
#   Interativo: gotas ligadas, ciclo de 8 s de chuva e 12 s de sol (Dry Time 8 s).
#   Teclas: R chove/para na hora, W liga/desliga o Wet Surfaces. Esc sai.
# Uso:
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_chuva_molhada.py -- <cena.range> <pasta_saida> [interativo]
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = os.path.abspath(argv[0])
outdir = os.path.abspath(argv[1]).replace("\\", "/")
interativo = len(argv) > 2 and argv[2] == "interativo"
os.makedirs(outdir, exist_ok=True)
os.makedirs(os.path.dirname(out_path), exist_ok=True)

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'

world = bpy.data.worlds.new("World")
world.horizon_color = (0.55, 0.6, 0.68)
world.zenith_color = (0.25, 0.35, 0.55)
world.use_sky_blend = True
scene.world = world
w = world.weather_settings
w.use_rain = True
w.rain_intensity = 0.0 if not interativo else 0.9
w.use_rain_droplets = interativo
w.use_rain_ripple = False
w.use_rain_splash = False
w.use_rain_puddles = False
w.use_rain_wet = True
w.rain_wet_darkness = 0.6
w.rain_wet_gloss = 0.7
w.rain_wet_distance = 80.0
w.rain_wet_dry_time = 8.0 if interativo else 3.0
w.show_expanded_rain = True
w.show_expanded_rain_wet = True


def material(name, color, spec=0.2):
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    m.specular_intensity = spec
    return m


def add(obj, mat):
    obj.data.materials.append(mat)
    return obj


bpy.ops.mesh.primitive_plane_add(radius=40, location=(0, 0, 0))
add(bpy.context.active_object, material("Chao", (0.45, 0.42, 0.38))).name = "Chao"

bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 9, 2))
parede = add(bpy.context.active_object, material("Parede", (0.7, 0.2, 0.15)))
parede.name = "Parede"
parede.scale = (8, 0.3, 2)

for i, (cor, x) in enumerate((((0.15, 0.35, 0.8), -4.0), ((0.9, 0.75, 0.2), 0.0), ((0.25, 0.65, 0.3), 4.0))):
    bpy.ops.mesh.primitive_cube_add(radius=1, location=(x, 3.0, 1))
    add(bpy.context.active_object, material("Cubo%d" % i, cor)).name = "Cubo%d" % i

# Esfera Smooth: o brilho molhado tem que ficar liso, sem marcar as faces.
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, size=1.6, location=(2.0, -2.5, 1.6))
bpy.ops.object.shade_smooth()
add(bpy.context.active_object, material("Esfera", (0.75, 0.75, 0.78), 0.5)).name = "Esfera"

bpy.ops.mesh.primitive_plane_add(radius=2.5, location=(-6.5, -1.0, 0.6))
rampa = add(bpy.context.active_object, material("Rampa", (0.8, 0.8, 0.8)))
rampa.name = "Rampa"
rampa.rotation_euler = (0.0, 0.35, 0.0)

lamp = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN'))
scene.objects.link(lamp)
lamp.rotation_euler = (0.7, 0.2, 0.6)
scene.world_sun_set = lamp

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.objects.link(cam)
cam.location = (0, -12, 4.5)
cam.rotation_euler = (1.25, 0, 0)
scene.camera = cam

logic = bpy.data.texts.new("molhado.py")
logic.from_string("""import bge
from bge import events, logic

OUT = %r
INTERATIVO = %r


def tick(cont):
    own = cont.owner
    world = logic.getCurrentScene().world
    t = own['t'] = own.get('t', 0) + 1
    kb = logic.keyboard.inputs
    if kb[events.RKEY].activated:
        world.setWeather('rain_intensity', 0.0 if world.getWeather('rain_intensity') > 0.0 else 0.9)
    if kb[events.WKEY].activated:
        world.setWeather('wet', not world.getWeather('wet'))
    if INTERATIVO:
        c = t %% 1200  # 8 s de chuva, 12 s de sol
        if c == 0:
            world.setWeather('rain_intensity', 0.9)
        elif c == 480:
            world.setWeather('rain_intensity', 0.0)
        return
    if t == 120:
        bge.render.makeScreenshot(OUT + '/1_seco_inicio.png')
    if t == 125:  # makeScreenshot captures at the end of the frame: change the weather after it
        world.setWeather('rain_intensity', 0.9)
    if t == 420:
        bge.render.makeScreenshot(OUT + '/2_molhado.png')
    if t == 425:
        world.setWeather('rain_intensity', 0.0)
    if t == 720:
        bge.render.makeScreenshot(OUT + '/3_seco_final.png')
    if t == 730:
        with open(OUT + '/resultado.txt', 'w') as f:
            f.write('frames_ok=%%d\\n' %% t)
            for k in ('rain', 'wet', 'wet_darkness', 'wet_gloss', 'wet_distance', 'wet_dry_time'):
                try:
                    f.write('%%s=%%r\\n' %% (k, world.getWeather(k)))
                except Exception as e:
                    f.write('%%s=erro %%r\\n' %% (k, e))
        logic.endGame()
""" % (outdir, interativo))
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
s = cam.game.sensors[-1]
s.use_pulse_true_level = True
c = cam.game.controllers[-1]
c.mode = 'MODULE'
c.module = 'molhado.tick'
s.link(c)

bpy.ops.wm.save_as_mainfile(filepath=out_path)
print("CENA_OK", out_path)
