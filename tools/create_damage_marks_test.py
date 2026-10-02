"""Damage marks test scene: Scrape Stamps x Strip, decal following later dents, Add Damage Mix.

Run with:  RangeEngine -b --python tools/create_damage_marks_test.py -- <output.range>
Then:      RangeRuntime <output.range>

- Left floor (Scrape Style Stamps): a box slides towards the camera and leaves red squares, one every
  Spacing.
- Right floor (Scrape Style Strip): a box slides on a diagonal and leaves one continuous red strip.
- Back plate (Dent + Impact Decal, material built by the Add Damage Mix button): a ball dents it and
  leaves a red mark, a heavier ball lands on the same spot later and dents it deeper; the mark must
  sink with the surface (no part of it floating or buried). Around the hits the grey paint turns into
  rusty metal (Damage node mask).
"""
import bpy
import bmesh
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "damage_marks_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True


def material(name, color, kind="ShaderNodeBsdfDiffuse"):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300.0, 0.0)
    shader = tree.nodes.new(kind)
    shader.inputs[0].default_value = color + (1.0,)
    tree.links.new(shader.outputs[0], out.inputs["Surface"])
    return mat


def link(ob, layer=0):
    scene.objects.link(ob)
    ob.layers = [i == layer for i in range(20)]
    return ob


def grid(name, segments, size, mat):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=segments, y_segments=segments, size=size)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = link(bpy.data.objects.new(name, me))
    ob.game.physics_type = 'STATIC'
    ob.game.use_collision_bounds = True
    ob.game.collision_bounds_type = 'TRIANGLE_MESH'
    ob.game.use_deform = True
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


# Decal template: a red unit square on the inactive layer 2.
dme = bpy.data.meshes.new("DecalMark")
dme.from_pydata([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [], [(0, 1, 2, 3)])
dme.update()
dme.materials.append(material("DecalMat", (0.9, 0.05, 0.05)))
decal = link(bpy.data.objects.new("DecalMark", dme), layer=1)
decal.game.physics_type = 'NO_COLLISION'

push = bpy.data.texts.new("push.py")
push.write("""import bge
def main(cont):
    own = cont.owner
    if not own.get("pushed"):
        own["pushed"] = True
        own.setLinearVelocity(eval(own["push"]))
""")

floor_mat = material("FloorMat", (0.8, 0.8, 0.8))
box_mat = material("BoxMat", (0.1, 0.3, 0.9))
for name, x, style, velocity in (("Stamps", -3.5, 'STAMPS', (0.0, -7.0, 0.0)),
                                 ("Strip", 3.5, 'STRIP', (2.0, -7.0, 0.0))):
    floor = grid("Floor" + name, 20, 3.0, floor_mat)
    floor.location = (x, 0.0, 0.0)
    df = floor.game.deform
    df.dent_impulse = 100000.0  # no dents, marks only
    df.use_dent_on_collision = False
    df.decal = decal
    df.decal_size = 0.5
    df.max_decals = 60
    df.use_scrape = True
    df.scrape_style = style
    df.scrape_speed = 1.0
    df.scrape_spacing = 0.2

    box = link(bpy.data.objects.new("Box" + name, box_mesh("Box" + name, (0.8, 0.8, 0.5))))
    box.data.materials.append(box_mat)
    box.location = (x - velocity[0] * 0.3, 2.5, 0.26)
    box.game.physics_type = 'RIGID_BODY'
    box.game.use_collision_bounds = True
    box.game.collision_bounds_type = 'BOX'
    box.game.mass = 30.0
    scene.objects.active = box
    bpy.ops.object.game_property_new(type='STRING', name="push")
    box.game.properties["push"].value = "%r" % (velocity,)
    bpy.ops.logic.sensor_add(type='ALWAYS', object=box.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=box.name)
    box.game.controllers[-1].mode = 'MODULE'
    box.game.controllers[-1].module = "push.main"
    box.game.sensors[-1].link(box.game.controllers[-1])

# Back plate: painted grey, Add Damage Mix turns the hit spots into rusty metal.
plate = grid("Plate", 30, 2.0, material("PlateMat", (0.6, 0.6, 0.65), "ShaderNodeBsdfPrincipled"))
plate.location = (0.0, 6.0, 0.0)
df = plate.game.deform
df.mode = 'DENT'
df.dent_impulse = 1.0
df.radius = 0.7
df.depth = 0.015
df.max_depth = 0.4
df.use_dent_on_collision = True
df.decal = decal
df.decal_size = 0.9
df.max_decals = 10
scene.objects.active = plate
bpy.ops.node.damage_mix_add()

ball_mat = material("BallMat", (0.1, 0.3, 0.9))
for i, (location, mass) in enumerate((((0.0, 6.0, 2.0), 10.0), ((0.15, 6.0, 9.0), 40.0))):
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
    ball.game.mass = mass

lamp = link(bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN')))
lamp.rotation_euler = (0.6, 0.2, 0.0)

cam = link(bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")))
cam.data.lens = 24.0
cam.location = (0.0, -9.0, 10.0)
from mathutils import Vector
cam.rotation_euler = (Vector((0.0, 2.0, 0.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

scene.layers = [i == 0 for i in range(20)]
bpy.ops.wm.save_as_mainfile(filepath=output)
print("DAMAGE_MARKS_TEST saved", output)
