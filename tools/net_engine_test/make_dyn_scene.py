# Scene for the "predict-cube" scenario: a frictionless dynamic box named "Car" on a static ground.
# No vehicle, no logic: the client predicts it with the same step the server runs.
# Usage: RangeEngine -b --python make_dyn_scene.py -- <out.range>
import bpy
import sys

OUT = sys.argv[sys.argv.index("--") + 1]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.world = bpy.data.worlds.new("World")

bpy.ops.mesh.primitive_plane_add(radius=500, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "Ground"
ground.game.physics_type = 'STATIC'

bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 0, 1.0))
box = bpy.context.active_object
box.name = "Car"
box.game.physics_type = 'RIGID_BODY'
box.game.mass = 1.0
box.game.use_collision_bounds = True
box.game.collision_bounds_type = 'BOX'
for axis in ("x", "y", "z"):
    setattr(box.game, "lock_rotation_" + axis, True)
box.game.friction = 0.0
ground.game.friction = 0.0

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (15, -15, 10)
cam.rotation_euler = (1.1, 0, 0.785)
scene.objects.link(cam)
scene.camera = cam

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("NETDYN SAVED", OUT)
