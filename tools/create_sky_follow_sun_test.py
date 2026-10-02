"""Sky Texture following the World sun lamp (Game PBR, Shading Nodes).

Run with:  RangeEngine -b --python tools/create_sky_follow_sun_test.py -- <output.range>
World: Sky Texture Hosek / Wilkie. A Sun lamp set as Scene > World Sun is lowered by a Python script every
frame, from high noon toward the horizon ahead of the camera: the sky should go from blue to a warm glow,
and the mirror sphere (Glossy 0) and the white Diffuse sphere follow it (the World capture is redone when
the sun turns). Without World Sun the sky keeps the node's own sun direction, as before.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "sky_follow_sun_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.view_settings.view_transform = 'Filmic'

world = bpy.data.worlds.new("Sky Sun World")
world.use_nodes = True
wt = world.node_tree
wt.nodes.clear()
sky = wt.nodes.new("ShaderNodeTexSky")
sky.sky_type = 'HOSEK_WILKIE'
sky.turbidity = 3.0
sky.ground_albedo = 0.3
bg = wt.nodes.new("ShaderNodeBackground")
wout = wt.nodes.new("ShaderNodeOutputWorld")
wt.links.new(sky.outputs["Color"], bg.inputs["Color"])
wt.links.new(bg.outputs[0], wout.inputs["Surface"])
scene.world = world


def mat(name, kind, color, **inputs):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    n = t.nodes.new(kind)
    n.inputs["Color"].default_value = color
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    t.links.new(n.outputs[0], out.inputs["Surface"])
    return m


specs = [
    ("Mirror", "ShaderNodeBsdfGlossy", (1, 1, 1, 1), dict(Roughness=0.0)),
    ("Diffuse", "ShaderNodeBsdfDiffuse", (0.8, 0.8, 0.8, 1), {}),
]
for i, (name, kind, color, inputs) in enumerate(specs):
    bpy.ops.mesh.primitive_uv_sphere_add(location=((i - 0.5) * 2.6, 0, 1), segments=48, ring_count=24)
    bpy.ops.object.shade_smooth()
    bpy.context.object.data.materials.append(mat(name + "Mat", kind, color, **inputs))

# Sun lamp: its +Z axis is the direction toward the sun; starts straight up.
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 6), rotation=(0, 0, 0))
sun = bpy.context.object
scene.world_sun_set = sun

txt = bpy.data.texts.new("lower_sun.py")
txt.from_string(
    "import bge, math\n"
    "own = bge.logic.getCurrentController().owner\n"
    "# tilt toward +Y (ahead of the camera) until 3 degrees above the horizon\n"
    "angle = own.localOrientation.to_euler().x\n"
    "if angle > -math.radians(87.0):\n"
    "    own.applyRotation((-0.004, 0, 0), False)\n")
scene.objects.active = sun
bpy.ops.logic.sensor_add(type='ALWAYS')
sun.game.sensors[-1].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON')
sun.game.controllers[-1].text = txt
sun.game.controllers[-1].link(sensor=sun.game.sensors[-1])

bpy.ops.object.camera_add(location=(0, -9, 2.0), rotation=(1.45, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
