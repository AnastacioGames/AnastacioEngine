"""Reflection probe blending test scene (Game PBR, Shading Nodes).

Run with:  RangeEngine -b --python tools/create_probe_blend_test.py -- <output.range>
Two probes side by side, radius 6, centers 8 apart (overlap 4): a red room on the left (-X) and a
green room on the right (+X), open toward the camera. A mirror sphere slides between them and past
both ends: its reflection should fade red -> green with no pop, and fade to the World sky
(Sky Texture) near the outer edges instead of switching at once.
A rough Principled sphere (Roughness 0.5) rides along to show the diffuse / blurred blend.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "probe_blend_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Blend World")
world.use_nodes = True
wt = world.node_tree
wt.nodes.clear()
sky = wt.nodes.new("ShaderNodeTexSky")
sky.sun_direction = (0.3, -0.5, 0.6)
bg = wt.nodes.new("ShaderNodeBackground")
wout = wt.nodes.new("ShaderNodeOutputWorld")
wt.links.new(sky.outputs["Color"], bg.inputs["Color"])
wt.links.new(bg.outputs[0], wout.inputs["Surface"])
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
        key = "Base Color" if "Base Color" in n.inputs else "Color"
        n.inputs[key].default_value = color
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    tree.links.new(n.outputs[0], out.inputs["Surface"])
    return mat


def wall(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)


red = node_material("RedWall", "ShaderNodeEmission", (0.9, 0.1, 0.1, 1.0))
green = node_material("GreenWall", "ShaderNodeEmission", (0.1, 0.9, 0.1, 1.0))
for cx, mat, tag in ((-4.0, red, "Red"), (4.0, green, "Green")):
    wall(tag + "Back", (cx, 4.0, 2.0), (3.8, 0.2, 2.0), mat)
    wall(tag + "Top", (cx, 0.0, 4.2), (3.8, 4.0, 0.2), mat)
    wall(tag + "Floor", (cx, 0.0, -0.2), (3.8, 4.0, 0.2), mat)
    bpy.ops.object.empty_add(location=(cx, 0.0, 1.5))
    probe = bpy.context.object
    probe.name = "Probe" + tag
    bpy.ops.object.game_property_new(type='FLOAT', name="probe")
    probe.game.properties["probe"].value = 6.0
    bpy.ops.object.game_property_new(type='BOOL', name="probe_realtime")
    probe.game.properties["probe_realtime"].value = False

slider = bpy.data.texts.new("slide.py")
slider.from_string(
    "import bge, math\n"
    "own = bge.logic.getCurrentController().owner\n"
    "t = bge.logic.getRealTime()\n"
    "own.worldPosition.x = own['x0'] + 11.0 * math.sin(t * 0.35)\n")

for name, kind, color, inputs, z in (
        ("Mirror", "ShaderNodeBsdfGlossy", (1.0, 1.0, 1.0, 1.0), dict(Roughness=0.0), 1.5),
        ("Rough", "ShaderNodeBsdfPrincipled", (0.8, 0.8, 0.8, 1.0), dict(Roughness=0.5), 0.6)):
    bpy.ops.mesh.primitive_uv_sphere_add(location=(0.0, -1.5 if z < 1 else 0.0, z), size=0.8 if z > 1 else 0.5,
                                         segments=48, ring_count=24)
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(node_material(name + "Mat", kind, color, **inputs))
    bpy.ops.object.game_property_new(type='FLOAT', name="x0")
    bpy.ops.logic.sensor_add(type='ALWAYS')
    obj.game.sensors[-1].use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON')
    obj.game.controllers[-1].text = slider
    obj.game.controllers[-1].link(sensor=obj.game.sensors[-1])

bpy.ops.object.camera_add(location=(0, -16, 3.0), rotation=(1.45, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
