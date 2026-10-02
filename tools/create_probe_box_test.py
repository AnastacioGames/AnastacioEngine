"""Box parallax reflection probe test scene (Game PBR, Shading Nodes).

Run with:  RangeEngine -b --python tools/create_probe_box_test.py -- <output.range>
A long room (12 x 6 x 4) with a different emission color on each wall and a checker floor. The probe
Empty is drawn as Cube and scaled to the room, so its reflection uses box parallax. Three mirror
spheres along the room: the reflected walls and the checker lines should line up with the real ones
at every sphere (with the sphere parallax they would bend and slide). A mirror box in front shows
straight wall edges.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "probe_box_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

# The probe reflection replaces the World reflection, so the scene needs a node World.
world = bpy.data.worlds.new("Box World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.2, 0.2, 0.2, 1.0)
scene.world = world


def node_material(name, kind, color, **inputs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    n = tree.nodes.new(kind)
    if kind == "ShaderNodeEmission":
        n.inputs["Color"].default_value = color
        n.inputs["Strength"].default_value = 1.0
    else:
        n.inputs["Color"].default_value = color
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    tree.links.new(n.outputs[0], out.inputs["Surface"])
    return mat


def checker_material():
    mat = bpy.data.materials.new("Checker")
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    em = tree.nodes.new("ShaderNodeEmission")
    chk = tree.nodes.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = 1.5
    chk.inputs["Color1"].default_value = (0.9, 0.9, 0.9, 1.0)
    chk.inputs["Color2"].default_value = (0.05, 0.05, 0.05, 1.0)
    coord = tree.nodes.new("ShaderNodeTexCoord")
    tree.links.new(coord.outputs["Object"], chk.inputs["Vector"])
    tree.links.new(chk.outputs["Color"], em.inputs["Color"])
    tree.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def box(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


em = lambda n, c: node_material(n, "ShaderNodeEmission", c)
# room: x -6..6, y -3..3, z 0..4
box("Floor", (0, 0, -0.1), (6, 3, 0.1), checker_material())
box("Ceiling", (0, 0, 4.1), (6, 3, 0.1), em("Ceil", (0.6, 0.6, 0.6, 1.0)))
box("WallLeft", (-6.1, 0, 2), (0.1, 3, 2), em("Red", (0.9, 0.1, 0.1, 1.0)))
box("WallRight", (6.1, 0, 2), (0.1, 3, 2), em("Green", (0.1, 0.9, 0.1, 1.0)))
box("WallBack", (0, 3.1, 2), (6, 0.1, 2), em("Blue", (0.1, 0.2, 0.9, 1.0)))
box("WallFront", (0, -3.1, 2), (6, 0.1, 2), em("Yellow", (0.9, 0.8, 0.1, 1.0)))
# a white stripe on the back wall to judge alignment
box("Stripe", (0, 2.98, 2), (6, 0.02, 0.15), em("White", (1.0, 1.0, 1.0, 1.0)))

bpy.ops.object.empty_add(type='CUBE', location=(0, 0, 2))
probe = bpy.context.object
probe.name = "ProbeBox"
probe.scale = (6, 3, 2)
bpy.ops.object.game_property_new(type='FLOAT', name="probe")
probe.game.properties["probe"].value = 7.0
bpy.ops.object.game_property_new(type='BOOL', name="probe_realtime")
probe.game.properties["probe_realtime"].value = False

mirror = node_material("Mirror", "ShaderNodeBsdfGlossy", (1.0, 1.0, 1.0, 1.0), Roughness=0.0)
for i, x in enumerate((-4.0, 0.0, 4.0)):
    bpy.ops.mesh.primitive_uv_sphere_add(location=(x, 1.0, 1.2), size=0.9, segments=48, ring_count=24)
    obj = bpy.context.object
    obj.name = "Mirror%d" % i
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(mirror)
box("MirrorBox", (0, -1.0, 0.5), (1.5, 0.5, 0.5), mirror)

bpy.ops.object.camera_add(location=(0, -2.8, 2.2), rotation=(1.42, 0, 0))
cam = bpy.context.object
cam.data.lens = 18
scene.camera = cam

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
