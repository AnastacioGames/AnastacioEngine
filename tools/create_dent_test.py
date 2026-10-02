"""Impact deformation (Deformation panel) test scene.

Run with:  RangeEngine -b --python tools/create_dent_test.py -- <output.range>
Then:      RangeRuntime <output.range>

Two plates share one subdivided mesh (linked duplicates), both Deformable with Triangle Mesh bounds
and Update Physics. A heavy ball falls on PlateA only. The DentProbe script removes the ball, casts
rays down on the center of both plates and prints:
  DENT_TEST plateA=<hit z> plateB=<hit z> dentPy=<bool>
plateA below plateB = collision dent and physics update work, plateB untouched = private mesh per
instance. dentPy = KX_GameObject.dent() on PlateB from Python, dents = onDent calls on PlateA.
The line is also written to dent_result.txt next to the .range. The game quits after the check.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "dent_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'

PROBE = '''
import bge

def main(cont):
    own = cont.owner
    scene = bge.logic.getCurrentScene()
    own["frame"] = own.get("frame", 0) + 1
    frame = own["frame"]
    if frame == 1:
        def on_dent(obj, point, impulse):
            own["dents"] = own.get("dents", 0) + 1
        scene.objects["PlateA"].onDent.append(on_dent)
    if frame == 90:
        ball = scene.objects.get("Ball")
        if ball:
            ball.endObject()
    elif frame == 95:
        out = {}
        for name in ("PlateA", "PlateB"):
            plate = scene.objects[name]
            start = plate.worldPosition.copy()
            start.z += 2.0
            end = start.copy()
            end.z -= 4.0
            hit, point, normal = own.rayCast(end, start, 0.0)
            out[name] = round(point.z, 4) if hit else None
        plateB = scene.objects["PlateB"]
        corner = plateB.worldPosition.copy()
        corner.x += 0.6
        dentPy = plateB.dent(corner, (0.0, 0.0, -1.0), 60.0)
        line = "DENT_TEST plateA=%s plateB=%s dentPy=%s dents=%s" % (out["PlateA"], out["PlateB"], dentPy, own.get("dents", 0))
        print(line)
        with open(bge.logic.expandPath("//dent_result.txt"), "w") as f:
            f.write(line + "\n")
    elif frame == 100:
        bge.logic.endGame()
'''

# Plates: one subdivided mesh, two linked instances.
bpy.ops.mesh.primitive_plane_add(location=(-1.5, 0, 0.5), radius=1.0)
plate = bpy.context.object
plate.name = "PlateA"
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=20)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.shade_smooth()
plate.game.physics_type = 'STATIC'
plate.game.use_collision_bounds = True
plate.game.collision_bounds_type = 'TRIANGLE_MESH'
plate.game.use_deform = True
plate.game.deform.dent_impulse = 20.0
plate.game.deform.depth = 0.004
plate.game.deform.max_depth = 0.3
plate.game.deform.radius = 0.6
plate.game.deform.use_update_physics = True

bpy.ops.object.duplicate(linked=True)
plateB = bpy.context.object
plateB.name = "PlateB"
plateB.location = (1.5, 0, 0.5)

# Heavy ball over PlateA.
bpy.ops.mesh.primitive_uv_sphere_add(location=(-1.5, 0, 4.0), size=0.25)
ball = bpy.context.object
ball.name = "Ball"
ball.game.physics_type = 'RIGID_BODY'
ball.game.mass = 20.0
ball.game.use_collision_bounds = True
ball.game.collision_bounds_type = 'SPHERE'

# Probe: script running every frame.
bpy.ops.object.add(type='EMPTY', location=(0, 0, 5))
probe = bpy.context.object
probe.name = "DentProbe"
text = bpy.data.texts.new("dent_probe.py")
text.write(PROBE)
bpy.ops.logic.sensor_add(type='ALWAYS', object=probe.name)
bpy.ops.logic.controller_add(type='PYTHON', object=probe.name)
sensor = probe.game.sensors[-1]
sensor.use_pulse_true_level = True
controller = probe.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = "dent_probe.main"
sensor.link(controller)

bpy.ops.object.camera_add(location=(0, -6, 4), rotation=(1.05, 0, 0))
scene.camera = bpy.context.object
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10))

bpy.ops.wm.save_as_mainfile(filepath=output)
