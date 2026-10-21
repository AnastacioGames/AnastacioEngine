# Cena de teste da chuva com velocidade e abrigo (rain_shelter).
#   Piso grande, telhado "Abrigo" (propriedade rain_shelter) sobre a origem.
#   A camera fica parada embaixo do abrigo (foto 1), depois sai e anda a ~20 m/s
#   para frente (foto 2), e confere getWeather() com os campos novos.
# Uso:
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_chuva_velocidade.py -- <cena.range> <pasta_saida>
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = os.path.abspath(argv[0])
outdir = os.path.abspath(argv[1]).replace("\\", "/")
os.makedirs(outdir, exist_ok=True)

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'

world = bpy.data.worlds.new("World")
world.horizon_color = (0.25, 0.27, 0.3)
scene.world = world
w = world.weather_settings
w.use_rain = True
w.rain_intensity = 0.9
w.rain_velocity = 1.0
w.rain_velocity_stretch = 1.0
w.rain_velocity_max = 25.0

bpy.ops.mesh.primitive_plane_add(radius=200, location=(0, 0, 0))
bpy.context.active_object.name = "Piso"

bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 0, 4))
roof = bpy.context.active_object
roof.name = "Abrigo"
roof.scale = (6, 6, 0.1)
bpy.ops.object.game_property_new(type='BOOL', name="rain_shelter")
roof.game.properties["rain_shelter"].value = True

lamp = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN'))
scene.objects.link(lamp)
lamp.rotation_euler = (0.6, 0.2, 0.5)

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.objects.link(cam)
cam.location = (0, 0, 1.7)
cam.rotation_euler = (1.45, 0, 0)  # olhando para +Y, quase horizontal
scene.camera = cam

logic = bpy.data.texts.new("probe.py")
logic.from_string("""import bge

OUT = %r

def tick(cont):
    own = cont.owner
    t = own['t'] = own.get('t', 0) + 1
    if t == 90:
        bge.render.makeScreenshot(OUT + '/1_parado_abrigo.png')
    if t > 100:
        own.worldPosition.y += 20.0 / 60.0  # ~20 m/s
    if t == 220:
        bge.render.makeScreenshot(OUT + '/2_andando_20ms.png')
    if t == 225:
        wt = bge.logic.getCurrentScene().world
        info = {}
        for k in ('rain', 'rain_velocity', 'rain_velocity_stretch', 'rain_velocity_max'):
            try:
                info[k] = wt.getWeather(k)
            except Exception as e:
                info[k] = 'erro ' + repr(e)
        with open(OUT + '/resultado.txt', 'w') as f:
            f.write('frames_ok=%%d\\n' %% t)
            for k in sorted(info):
                if 'velocity' in k or 'rain' in k:
                    f.write('%%s=%%r\\n' %% (k, info[k]))
        bge.logic.endGame()
""" % outdir)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
s = cam.game.sensors[-1]
s.use_pulse_true_level = True
c = cam.game.controllers[-1]
c.mode = 'MODULE'
c.module = 'probe.tick'
s.link(c)

bpy.ops.wm.save_as_mainfile(filepath=out_path)
print("CENA_OK", out_path)
