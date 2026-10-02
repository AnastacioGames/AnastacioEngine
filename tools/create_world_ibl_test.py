"""World image lighting (IBL) test scene (Game PBR, Shading Nodes).

Run with:  RangeEngine -b --python tools/create_world_ibl_test.py -- <output.range>
The World uses a generated equirect image (blue sky, brown ground, red half on -X, green half on +X,
bright sun spot) as its texture, with Environment Color = Sky Texture, so materials read it.
Front row, left to right: Principled Roughness 0 / 0.3 / 0.6 / 1.0 (dielectric) and
Principled metallic Roughness 0.2 / 0.6. Diffuse spheres should be reddish on the left side and
greenish on the right side (direction-dependent irradiance), and bluer on top.
Back row: Diffuse white, Glossy 0.0 / 0.4 / 0.8, Glass 0.0, Principled gold metallic 0.4.
"""
import bpy
import math
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "world_ibl_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

W, H = 512, 256
img = bpy.data.images.new("IBL Equirect", W, H)
px = []
for y in range(H):
    lat = (y + 0.5) / H * math.pi - math.pi / 2  # -90 (bottom) .. 90 (top)
    for x in range(W):
        # uv_equirectangular: u = -atan(y, x) / 2pi + 0.5
        lon = -((x + 0.5) / W - 0.5) * 2 * math.pi
        dx = math.cos(lat) * math.cos(lon)
        if lat > 0:
            t = lat / (math.pi / 2)
            c = [0.55 - 0.35 * t, 0.7 - 0.3 * t, 1.0]
        else:
            c = [0.35, 0.25, 0.15]
        # red on -X, green on +X (strongest at the horizon)
        side = dx * math.cos(lat)
        if side < -0.3:
            c = [c[0] * 0.3 + 0.9, c[1] * 0.3, c[2] * 0.3]
        elif side > 0.3:
            c = [c[0] * 0.3, c[1] * 0.3 + 0.8, c[2] * 0.3]
        # sun spot, up and toward -Y (behind the camera, lights the spheres' front)
        sx, sy, sz = 0.0, -0.6, 0.8
        d = (math.cos(lat) * math.cos(lon) * sx + math.cos(lat) * math.sin(lon) * sy + math.sin(lat) * sz)
        if d > 0.995:
            c = [1.0, 0.95, 0.8]
        px.extend((min(c[0], 1.0), min(c[1], 1.0), min(c[2], 1.0), 1.0))
img.pixels = px
img.pack(as_png=True)

tex = bpy.data.textures.new("IBL Tex", 'IMAGE')
tex.image = img

world = bpy.data.worlds.new("IBL World")
world.use_nodes = False
world.sky_type = 'PROCEDURAL'
world.light_settings.environment_color = 'SKY_TEXTURE'
slot = world.texture_slots.add()
slot.texture = tex
slot.texture_coords = 'EQUIRECT'
slot.use_map_horizon = True
scene.world = world


def node_material(name, kind, color, **inputs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    n = tree.nodes.new(kind)
    key = "Base Color" if "Base Color" in n.inputs else "Color"
    n.inputs[key].default_value = color
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    tree.links.new(n.outputs[0], out.inputs["Surface"])
    return mat


P = "ShaderNodeBsdfPrincipled"
white = (0.8, 0.8, 0.8, 1.0)
front = [
    ("PrinR0", P, white, dict(Roughness=0.0)),
    ("PrinR03", P, white, dict(Roughness=0.3)),
    ("PrinR06", P, white, dict(Roughness=0.6)),
    ("PrinR1", P, white, dict(Roughness=1.0)),
    ("MetalR02", P, (0.9, 0.9, 0.9, 1.0), dict(Roughness=0.2, Metallic=1.0)),
    ("MetalR06", P, (0.9, 0.9, 0.9, 1.0), dict(Roughness=0.6, Metallic=1.0)),
]
back = [
    ("Diffuse", "ShaderNodeBsdfDiffuse", white, {}),
    ("Glossy0", "ShaderNodeBsdfGlossy", white, dict(Roughness=0.0)),
    ("Glossy04", "ShaderNodeBsdfGlossy", white, dict(Roughness=0.4)),
    ("Glossy08", "ShaderNodeBsdfGlossy", white, dict(Roughness=0.8)),
    ("Glass", "ShaderNodeBsdfGlass", (1.0, 1.0, 1.0, 1.0), dict(Roughness=0.0, IOR=1.45)),
    ("Gold", P, (1.0, 0.75, 0.3, 1.0), dict(Roughness=0.4, Metallic=1.0)),
]
for y, specs in ((0.0, front), (3.0, back)):
    for i, (name, kind, color, inputs) in enumerate(specs):
        bpy.ops.mesh.primitive_uv_sphere_add(location=((i - 2.5) * 2.4, y, 1), segments=48, ring_count=24)
        obj = bpy.context.object
        obj.name = name
        bpy.ops.object.shade_smooth()
        obj.data.materials.append(node_material(name + "Mat", kind, color, **inputs))

bpy.ops.object.camera_add(location=(0, -12, 4.0), rotation=(1.35, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
