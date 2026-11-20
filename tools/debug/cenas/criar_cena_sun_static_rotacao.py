# Sun legado (sem cascata) com Static Shadow: a sombra acompanha a rotacao da lampada?
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_sun_static_rotacao.py -- cena.range log.txt [static=1|0]
#   AnastacioRuntime.exe cena.range
# O jogo gira o Sun no quadro 60 e grava, por faixa de quadros, a soma de shadowPasses
# (getRenderStats). Se depois da rotacao a soma ficar 0 com static=1, o shadow map nao foi redesenhado.
import bpy
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
out_path, log_path = argv[0], argv[1].replace('\\', '/')
static = (argv[2] != '0') if len(argv) > 2 else True
ver = len(argv) > 3 and argv[3] == 'ver'  # modo visual: nao encerra e gira o Sun a cada 3 s

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.render.resolution_x = 640
scene.render.resolution_y = 360

def material(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = rgb
    return m

bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
floor = bpy.context.object
floor.scale = (8, 8, 1)
floor.data.materials.append(material('chao', (0.8, 0.8, 0.8)))

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 2))
cube = bpy.context.object
cube.data.materials.append(material('cubo', (0.9, 0.1, 0.1)))

lamp = bpy.data.lamps.new('Sol', 'SUN')
lamp.use_shadow = True
lamp.shadow_method = 'RAY_SHADOW'
lamp.shadow_buffer_size = 2048
lamp.static_shadow = static
sun = bpy.data.objects.new('Sol', lamp)
scene.objects.link(sun)
sun.location = (0, 0, 10)
sun.rotation_euler = (0.4, 0.0, 0.0)

cam_data = bpy.data.cameras.new('Cam')
cam_data.lens = 16
cam = bpy.data.objects.new('Cam', cam_data)
scene.objects.link(cam)
cam.location = (0, -9, 9)
cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

if not scene.world:
    scene.world = bpy.data.worlds.new('Mundo')
scene.world.mist_settings.use_mist = False

CODIGO = '''import bge
LOG = %r
VER = %s
_s = {"f": 0, "antes": 0, "depois": 0}

def tick(cont):
    _s["f"] += 1
    f = _s["f"]
    stats = bge.logic.getRenderStats()
    passes = stats.get("shadowPasses", 0)
    if 10 <= f < 60:
        _s["antes"] += passes
    if f == 60:
        cont.owner.scene.objects["Sol"].applyRotation((0.0, 0.6, 0.0), True)
    if 62 <= f < 110:
        _s["depois"] += passes
    if VER and f > 120 and f %% 180 == 0:
        cont.owner.scene.objects["Sol"].applyRotation((0.0, 0.6, 0.0), True)
    if f == 120:
        with open(LOG, "w") as fh:
            fh.write("static=%s antes=%%d depois=%%d lamp_static=%%s" %% (
                _s["antes"], _s["depois"], cont.owner.scene.objects["Sol"].staticShadow) + chr(10))
        if not VER:
            bge.logic.endGame()
''' % (log_path, ver, static)
txt = bpy.data.texts.new('sun_teste.py')
txt.write(CODIGO)

scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
sens = cam.game.sensors[-1]
sens.use_pulse_true_level = True
ctrl = cam.game.controllers[-1]
ctrl.mode = 'MODULE'
ctrl.module = 'sun_teste.tick'
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=out_path, check_existing=False)
