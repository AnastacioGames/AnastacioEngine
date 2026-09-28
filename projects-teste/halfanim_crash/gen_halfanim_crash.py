# Gera cena de teste para o crash de setHalfAnimations + skinning CPU + IK.
# Uso: RangeEngine.exe -b --python gen_halfanim_crash.py
import bpy
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "halfanim_crash.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'

LAYER2 = [i == 1 for i in range(20)]

# Armature: cadeia de 3 ossos + osso alvo do IK
arm_data = bpy.data.armatures.new("RigData")
rig = bpy.data.objects.new("Rig", arm_data)
scene.objects.link(rig)
scene.objects.active = rig
rig.select = True
bpy.ops.object.mode_set(mode='EDIT')
prev = None
for i in range(3):
    b = arm_data.edit_bones.new("Bone%d" % i)
    b.head = (0, 0, i * 1.0)
    b.tail = (0, 0, (i + 1) * 1.0)
    if prev:
        b.parent = prev
        b.use_connect = True
    prev = b
t = arm_data.edit_bones.new("Target")
t.head = (1.5, 0, 2.5)
t.tail = (1.5, 0, 3.0)
bpy.ops.object.mode_set(mode='POSE')
ik = rig.pose.bones["Bone2"].constraints.new('IK')
ik.target = rig
ik.subtarget = "Target"
ik.chain_count = 3

# Acao movendo o alvo do IK
act = bpy.data.actions.new("TargetAct")
rig.animation_data_create()
rig.animation_data.action = act
pb = rig.pose.bones["Target"]
for frame, loc in ((1, (0, 0, 0)), (10, (-2.5, 0, -1.5)), (20, (0, 0, 0))):
    pb.location = loc
    pb.keyframe_insert("location", frame=frame, group="Target")
bpy.ops.object.mode_set(mode='OBJECT')

# Malha skinned (modificador armature, skinning CPU)
bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.3, depth=3.0, location=(0, 0, 1.5))
mesh = bpy.context.active_object
mesh.name = "Body"
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=8)
bpy.ops.object.mode_set(mode='OBJECT')
mesh.select = True
rig.select = True
scene.objects.active = rig
bpy.ops.object.parent_set(type='ARMATURE_AUTO')

# Rig e malha na camada 2 (inativa) para serem spawnados
rig.layers = LAYER2
mesh.layers = LAYER2

# Camera e lampada
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
cam.location = (14, -40, 20)
cam.rotation_euler = (1.2, 0, 0)
scene.objects.link(cam)
scene.camera = cam
lamp = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN'))
lamp.location = (0, 0, 20)
scene.objects.link(lamp)

# Spawner
script = bpy.data.texts.new("spawn.py")
script.write(r'''import bge, traceback
LOG = bge.logic.expandPath("//halfanim_log.txt")
def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")
try:
    own = bge.logic.getCurrentController().owner
    sc = bge.logic.getCurrentScene()
    n = own.get("n", 0)
    if n == 0:
        log("START")
    if n < 5:
        for i in range(30):
            k = n * 30 + i
            o = sc.addObject("Rig", own, 0)
            o.worldPosition = ((k % 15) * 2.0, (k // 15) * 2.0, 0.0)
            o.setHalfAnimations(1)
            for c in o.children:
                c.setHalfAnimations(1)
            o.playAction("TargetAct", 1, 20, play_mode=1)
    own["n"] = n + 1
    if n == 5:
        log("SPAWNED %d" % len(sc.objects))
    if n % 100 == 0:
        log("frame %d" % n)
    if n == 600:
        log("OK frames=%d" % n)
        bge.logic.endGame()
except Exception:
    log(traceback.format_exc())
    bge.logic.endGame()
''')
empty = bpy.data.objects.new("Spawner", None)
scene.objects.link(empty)
scene.objects.active = empty
bpy.ops.logic.sensor_add(type='ALWAYS', object="Spawner")
bpy.ops.logic.controller_add(type='PYTHON', object="Spawner")
sens = empty.game.sensors[-1]
sens.use_pulse_true_level = True
cont = empty.game.controllers[-1]
cont.text = script
sens.link(cont)

scene.layers = [i == 0 for i in range(20)]
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED", OUT)
