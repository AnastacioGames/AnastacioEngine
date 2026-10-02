"""Scrape marks (Deformation > Impact Decal > Scrape Marks) test scene.

Run with:  RangeEngine -b --python tools/create_scrape_test.py -- <output.range>
Then:      RangeRuntime <output.range>

A heavy box is pushed once and slides across a white floor. The floor (Deformable, Scrape Marks, red
DecalMark on the inactive layer 2) should get a trail of red marks lined up with the slide, one
every Scrape Spacing while the box slides faster than Scrape Speed.
"""
import bpy
import bmesh
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "scrape_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'


def material(name, color, friction=0.5):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.specular_intensity = 0.1
    return mat


def link(ob, layer=0):
    scene.objects.link(ob)
    ob.layers = [i == layer for i in range(20)]
    return ob


def box_mesh(name, size):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


# Floor: a subdivided grid so the marks follow the surface.
me = bpy.data.meshes.new("Floor")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=30, y_segments=30, size=6.0)
bm.to_mesh(me)
bm.free()
me.materials.append(material("FloorMat", (0.8, 0.8, 0.8), friction=0.3))
floor = link(bpy.data.objects.new("Floor", me))
floor.game.physics_type = 'STATIC'
floor.game.use_collision_bounds = True
floor.game.collision_bounds_type = 'TRIANGLE_MESH'
floor.game.use_deform = True
df = floor.game.deform
df.dent_impulse = 100000.0  # no dents, marks only
df.use_dent_on_collision = False

dme = bpy.data.meshes.new("DecalMark")
dme.from_pydata([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [], [(0, 1, 2, 3)])
dme.update()
dme.materials.append(material("DecalMat", (0.9, 0.05, 0.05)))
decal = link(bpy.data.objects.new("DecalMark", dme), layer=1)
decal.game.physics_type = 'NO_COLLISION'

df.decal = decal
df.decal_size = 0.5
df.max_decals = 60
df.use_scrape = True
df.scrape_speed = 1.0
df.scrape_spacing = 0.2

# A heavy box resting on the floor, pushed once at start: it slides towards the camera.
box = link(bpy.data.objects.new("Box", box_mesh("Box", (0.8, 0.8, 0.5))))
box.data.materials.append(material("BoxMat", (0.1, 0.3, 0.9)))
box.location = (0.0, 4.0, 0.26)
box.game.physics_type = 'RIGID_BODY'
box.game.use_collision_bounds = True
box.game.collision_bounds_type = 'BOX'
box.game.mass = 30.0

push = bpy.data.texts.new("push.py")
push.write("""import bge
def main(cont):
    own = cont.owner
    if not own.get("pushed"):
        own["pushed"] = True
        own.setLinearVelocity((0.0, -7.0, 0.0))
""")
bpy.context.scene.objects.active = box
bpy.ops.logic.sensor_add(type='ALWAYS', object=box.name)
bpy.ops.logic.controller_add(type='PYTHON', object=box.name)
box.game.controllers[-1].mode = 'MODULE'
box.game.controllers[-1].module = "push.main"
box.game.sensors[-1].link(box.game.controllers[-1])

lamp = link(bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN')))
lamp.rotation_euler = (0.6, 0.2, 0.0)

cam = link(bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")))
cam.data.lens = 28.0
cam.location = (9.0, -9.0, 9.0)
# Aimed at the middle of the slide (mathutils is in the editor's Python).
from mathutils import Vector
cam.rotation_euler = (Vector((0.0, 1.0, 0.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

scene.layers = [i == 0 for i in range(20)]
bpy.ops.wm.save_as_mainfile(filepath=output)
print("SCRAPE_TEST saved", output)
