"""Impact decal (Deformation > Impact Decal) test scene.

Run with:  RangeEngine -b --python tools/create_decal_test.py -- <output.range>
Then:      RangeRuntime <output.range>

A white floor plate (Deformable, Dent, Triangle Mesh) gets hit by five balls falling one after the
other. Each hit dents the plate and projects the red DecalMark (inactive layer 2) on it, so five red
squares should appear where the balls land, seen from the camera above.
"""
import bpy
import bmesh
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "decal_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.specular_intensity = 0.1
    return mat


def link(ob, layer=0):
    scene.objects.link(ob)
    ob.layers = [i == layer for i in range(20)]
    return ob


# Floor plate: subdivided so the dent shows, decal clipped to its triangles.
me = bpy.data.meshes.new("Plate")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=40, y_segments=40, size=4.0)
bm.to_mesh(me)
bm.free()
me.materials.append(material("PlateMat", (0.8, 0.8, 0.8)))
plate = link(bpy.data.objects.new("Plate", me))
plate.game.physics_type = 'STATIC'
plate.game.use_collision_bounds = True
plate.game.collision_bounds_type = 'TRIANGLE_MESH'
plate.game.use_deform = True
df = plate.game.deform
df.mode = 'DENT'
df.dent_impulse = 1.0
df.radius = 0.6
df.depth = 0.02
df.max_depth = 0.25
df.use_dent_on_collision = True

# Decal template: a red unit square on the inactive layer 2.
dme = bpy.data.meshes.new("DecalMark")
dme.from_pydata([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [], [(0, 1, 2, 3)])
dme.update()
dme.materials.append(material("DecalMat", (0.9, 0.05, 0.05)))
decal = link(bpy.data.objects.new("DecalMark", dme), layer=1)
decal.game.physics_type = 'NO_COLLISION'

df.decal = decal
df.decal_size = 0.7
df.max_decals = 10
df.decal_life = 0.0

# Five heavy balls, falling one after the other (different heights).
ball_mat = material("BallMat", (0.1, 0.3, 0.9))
spots = [(0.0, 0.0, 3.0), (-2.0, 1.5, 5.0), (2.0, -1.5, 7.0), (-1.5, -2.0, 9.0), (1.8, 2.0, 11.0)]
for i, location in enumerate(spots):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, diameter=0.3)
    bme = bpy.data.meshes.new("Ball%d" % i)
    bm.to_mesh(bme)
    bm.free()
    bme.materials.append(ball_mat)
    ball = link(bpy.data.objects.new("Ball%d" % i, bme))
    ball.location = location
    ball.game.physics_type = 'RIGID_BODY'
    ball.game.use_collision_bounds = True
    ball.game.collision_bounds_type = 'SPHERE'
    ball.game.mass = 20.0

lamp = link(bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN')))
lamp.rotation_euler = (0.6, 0.2, 0.0)

cam = link(bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")))
cam.location = (0.0, -9.0, 9.0)
cam.rotation_euler = (0.785, 0.0, 0.0)
scene.camera = cam

scene.layers = [i == 0 for i in range(20)]
bpy.ops.wm.save_as_mainfile(filepath=output)
print("DECAL_TEST saved", output)
