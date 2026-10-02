"""Node sweep test: one sphere per shader node type, Game PBR (Shading Nodes).

Run with:  RangeEngine -b --python tools/create_node_sweep_test.py -- <output.range> [--autoquit] [--span=lo:hi]
Every ShaderNode type that can be created gets its own material: shader outputs go to Surface,
other outputs feed the Color of an Emission. Sun, Point and Spot lamps with shadow, a World with
Sky Texture, Filmic color management and a reflection probe exercise the full light loop.
With --autoquit the game ends after 90 frames, so the console log can be scanned for shader errors.
Unsupported nodes must not crash or break the compile of the other materials.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
autoquit = "--autoquit" in argv
span = next((a[len("--span="):] for a in argv if a.startswith("--span=")), None)  # e.g. 0:45, for bisecting
argv = [a for a in argv if a != "--autoquit" and not a.startswith("--span=")]
output = argv[0] if argv else "node_sweep_test.range"

SKIP = {"ShaderNodeOutputMaterial", "ShaderNodeOutputWorld", "ShaderNodeOutputLamp", "ShaderNodeOutputLineStyle",
        "ShaderNodeGroup", "ShaderNodeCustomGroup", "ShaderNodeTree", "ShaderNodeOutput", "ShaderNodeScript"}

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.exposure = 0.3

world = bpy.data.worlds.new("Sweep World")
world.horizon_color = (0.4, 0.45, 0.5)
world.use_nodes = True
wt = world.node_tree
sky = wt.nodes.new("ShaderNodeTexSky")
sky.sky_type = 'PREETHAM'
wt.links.new(sky.outputs["Color"], wt.nodes["Background"].inputs["Color"])
scene.world = world


def make_material(type_name):
    mat = bpy.data.materials.new(type_name[len("ShaderNode"):])
    mat.use_nodes = True
    mat.use_constant_world = False
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    node = tree.nodes.new(type_name)
    node.location = (-300, 0)
    outputs = [s for s in node.outputs if s.enabled]
    shader_out = [s for s in outputs if s.type == 'SHADER']
    if shader_out:
        tree.links.new(shader_out[0], out.inputs["Surface"])
    elif outputs:
        emit = tree.nodes.new("ShaderNodeEmission")
        emit.location = (0, 0)
        tree.links.new(outputs[0], emit.inputs["Color"])
        tree.links.new(emit.outputs[0], out.inputs["Surface"])
    return mat


types = sorted(n for n in dir(bpy.types) if n.startswith("ShaderNode") and n not in SKIP)
if span:
    lo, hi = (int(v) for v in span.split(":"))
    types = types[lo:hi]
made = []
cols = 10
for type_name in types:
    try:
        mat = make_material(type_name)
    except Exception as exc:  # node not creatable in a material tree
        print("SWEEP skip", type_name, exc)
        continue
    i = len(made)
    x, y = (i % cols - cols / 2) * 2.2, (i // cols) * 2.2
    bpy.ops.mesh.primitive_uv_sphere_add(location=(x, y, 1), segments=32, ring_count=16)
    obj = bpy.context.object
    obj.name = type_name
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(mat)
    made.append(type_name)
print("SWEEP materials", len(made))

bpy.ops.mesh.primitive_plane_add(location=(0, 6, 0))
ground = bpy.context.object
ground.scale = (30, 30, 1)
ground.data.materials.append(make_material("ShaderNodeBsdfPrincipled"))

bpy.ops.object.lamp_add(type='SUN', location=(4, -6, 10))
bpy.context.object.rotation_euler = (0.7, 0.3, 0.6)
bpy.ops.object.lamp_add(type='POINT', location=(-6, 4, 4))
bpy.context.object.data.energy = 3.0
bpy.ops.object.lamp_add(type='SPOT', location=(6, 2, 6))
bpy.context.object.rotation_euler = (0.4, 0.0, 0.0)

bpy.ops.object.empty_add(location=(0, 6, 2))
probe = bpy.context.object
probe.name = "Probe"
bpy.ops.object.game_property_new(type='FLOAT', name="probe")
probe.game.properties["probe"].value = 12.0

bpy.ops.object.camera_add(location=(0, -16, 9), rotation=(1.15, 0, 0))
cam = bpy.context.object
scene.camera = cam

if autoquit:
    text = bpy.data.texts.new("sweep_quit.py")
    text.write('''import bge
own = bge.logic.getCurrentController().owner
own["frames"] = own.get("frames", 0) + 1
if own["frames"] == 90:
    print("SWEEP done")
    bge.logic.endGame()
''')
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
    sens = cam.game.sensors[-1]
    sens.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
    cont = cam.game.controllers[-1]
    cont.text = text
    sens.link(cont)

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
