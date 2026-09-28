# Cena de teste: carro (vehicle constraint) com e sem "Use Frame Rate".
# Mede se as rodas acompanham o chassi desenhado (offset local da roda deve ser fixo em X/Y).
# Uso: RangeEngine.exe -b --python gen_car_framerate.py -- <substeps> <use_frame_rate 0|1> <saida.blend> [com_y com_z]
# Com offset de centro de massa, as rodas (presas ao corpo fisico) ficam em conexao + offset no chassi desenhado.
import bpy
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:]
SUBSTEPS = int(argv[0])
USE_FRAME_RATE = argv[1] == "1"
OUT = argv[2]
LOG = OUT.replace(".blend", "_log.txt")
COM = (0.0, float(argv[3]), float(argv[4])) if len(argv) > 4 else (0.0, 0.0, 0.0)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.world = bpy.data.worlds.new("World")
scene.game_settings.physics_step_sub = SUBSTEPS
scene.game_settings.use_frame_rate = USE_FRAME_RATE

# Chao estatico
bpy.ops.mesh.primitive_plane_add(radius=500, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "Ground"
ground.game.physics_type = 'STATIC'

# Chassi
bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 0, 1.2))
car = bpy.context.active_object
car.name = "Car"
car.scale = (1.0, 2.0, 0.4)
bpy.ops.object.transform_apply(scale=True)
car.game.physics_type = 'RIGID_BODY'
car.game.mass = 800.0
car.game.use_collision_bounds = True
car.game.collision_bounds_type = 'BOX'
if any(COM):
    car.game.is_vehicle = True
    car.vehicle_com_offset = COM

# Rodas: empties sem fisica (exigido pelo addWheel)
WHEELS = [(-1.0, 1.4, 0), (1.0, 1.4, 0), (-1.0, -1.4, 0), (1.0, -1.4, 0)]
for i, p in enumerate(WHEELS):
    w = bpy.data.objects.new("Wheel%d" % i, None)
    w.location = (p[0], p[1], 0.5)
    w.game.physics_type = 'NO_COLLISION'
    scene.objects.link(w)

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (15, -15, 10)
cam.rotation_euler = (1.1, 0, 0.785)
scene.objects.link(cam)
scene.camera = cam
scene.objects.link(bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN')))

script = bpy.data.texts.new("car.py")
script.write(r'''import bge, traceback
from mathutils import Vector
LOG = bge.logic.expandPath("//%s")
WHEELS = %r
COM = %r
def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")
try:
    own = bge.logic.getCurrentController().owner
    sc = bge.logic.getCurrentScene()
    n = own.get("n", 0)
    if n == 0:
        open(LOG, "w").close()
        v = bge.constraints.createVehicle(own.getPhysicsId())
        for i, p in enumerate(WHEELS):
            v.addWheel(sc.objects["Wheel%%d" %% i], p, (0, 0, -1), (-1, 0, 0), 0.4, 0.45, i < 2)
        for i in range(4):
            v.setTyreFriction(3.0, i)
            v.setSuspensionStiffness(40.0, i)
            v.setSuspensionDamping(4.0, i)
            v.setSuspensionCompression(4.0, i)
            v.setRollInfluence(0.1, i)
        own["v"] = v
        own["maxErr"] = 0.0
        own["sumErr"] = 0.0
    v = own["v"]
    if n > 60:
        for i in (2, 3):
            v.applyEngineForce(-2500.0, i)
    if n > 60:
        # Offset local da roda no referencial do chassi desenhado. Com rodas em sincronia
        # ele fica em (+-1.0, +-1.4); desvio em X/Y = roda descolada do chassi.
        inv = own.worldTransform.inverted()
        err = 0.0
        for i, p in enumerate(WHEELS):
            loc = inv @ sc.objects["Wheel%%d" %% i].worldPosition if hasattr(Vector, "__matmul__") else inv * sc.objects["Wheel%%d" %% i].worldPosition
            err = max(err, (Vector((loc.x, loc.y)) - Vector((p[0] + COM[0], p[1] + COM[1]))).length)
        own["maxErr"] = max(own["maxErr"], err)
        own["sumErr"] += err
    if n %% 60 == 0:
        log("frame %%d pos %%s speed %%.2f" %% (n, tuple(round(c, 2) for c in own.worldPosition), own.localLinearVelocity.length))
    if n == 360:
        log("RESULT maxErr=%%.4f avgErr=%%.4f dist=%%.2f" %% (own["maxErr"], own["sumErr"] / 300.0, own.worldPosition.length))
        bge.logic.endGame()
    own["n"] = n + 1
except Exception:
    log(traceback.format_exc())
    bge.logic.endGame()
''' % (os.path.basename(LOG), WHEELS, COM))

scene.objects.active = car
bpy.ops.logic.sensor_add(type='ALWAYS', object="Car")
bpy.ops.logic.controller_add(type='PYTHON', object="Car")
sens = car.game.sensors[-1]
sens.use_pulse_true_level = True
cont = car.game.controllers[-1]
cont.text = script
sens.link(cont)

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED", OUT)
