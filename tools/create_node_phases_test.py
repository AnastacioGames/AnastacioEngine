"""Node material phases 3-5 test scene (Game PBR, Shading Nodes).

Run with:  RangeEngine -b --python tools/create_node_phases_test.py -- <output.range>
Front row (Phase 3, scene lights), left to right:
  1 Principled   2 Diffuse   3 Glossy 0.3   4 Toon Diffuse   5 Toon Glossy   6 Anisotropic 0.8
Back row (Phase 4), left to right:
  1 Glass   2 Refraction   3 AO (Emission by AO, cube dent)   4 Blackbody 1500 K   5 Wavelength 550 nm
  6 Glossy 0 (mirror of the World Sky Texture)
Third row (approximations), left to right:
  1 Translucent (lit from behind)   2 Subsurface (red bleed past the terminator)   3 Velvet (rim sheen)
  4 Holdout (black cut-out, alpha 0)   5 Diffuse (reference for 1-3)
Lights: Sun (shadow), red Point (shadow), blue Spot (shadow). World: Sky Texture (Preetham).
Phase 5: Scene > Color Management is Filmic; change View Transform / Exposure / Gamma in the
editor and press P again (read when the shader compiles).
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "node_phases_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.exposure = 0.0

world = bpy.data.worlds.new("Phases World")
world.use_nodes = True
wt = world.node_tree
wt.nodes.clear()
sky = wt.nodes.new("ShaderNodeTexSky")
sky.sky_type = 'PREETHAM'
sky.sun_direction = (0.4, -0.6, 0.5)
bg = wt.nodes.new("ShaderNodeBackground")
wout = wt.nodes.new("ShaderNodeOutputWorld")
wt.links.new(sky.outputs["Color"], bg.inputs["Color"])
wt.links.new(bg.outputs[0], wout.inputs["Surface"])
scene.world = world


def node_material(name, build):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    shader = build(tree)
    tree.links.new(shader.outputs[0], out.inputs["Surface"])
    return mat


def bsdf(kind, color=(0.8, 0.8, 0.8, 1.0), **inputs):
    def build(tree):
        n = tree.nodes.new(kind)
        if "Color" in n.inputs:
            n.inputs["Color"].default_value = color
        for key, value in inputs.items():
            if key.startswith("prop_"):
                setattr(n, key[5:], value)
            else:
                n.inputs[key].default_value = value
        return n
    return build


def emission_from(kind, socket, **props):
    def build(tree):
        src = tree.nodes.new(kind)
        src.location = (-300, 0)
        for key, value in props.items():
            if key in src.inputs:
                src.inputs[key].default_value = value
            else:
                setattr(src, key, value)
        em = tree.nodes.new("ShaderNodeEmission")
        tree.links.new(src.outputs[socket], em.inputs["Color"])
        return em
    return build


front = [
    ("Principled", bsdf("ShaderNodeBsdfPrincipled", (0.8, 0.3, 0.2, 1.0), Roughness=0.4)),
    ("Diffuse", bsdf("ShaderNodeBsdfDiffuse", (0.2, 0.7, 0.3, 1.0))),
    ("Glossy03", bsdf("ShaderNodeBsdfGlossy", (0.9, 0.7, 0.3, 1.0), Roughness=0.3)),
    ("ToonDiffuse", bsdf("ShaderNodeBsdfToon", (0.3, 0.5, 0.9, 1.0), prop_component='DIFFUSE')),
    ("ToonGlossy", bsdf("ShaderNodeBsdfToon", (0.9, 0.9, 0.9, 1.0), prop_component='GLOSSY')),
    ("Anisotropic", bsdf("ShaderNodeBsdfAnisotropic", (0.9, 0.9, 0.9, 1.0), Roughness=0.3, Anisotropy=0.8)),
]
back = [
    ("Glass", bsdf("ShaderNodeBsdfGlass", (1.0, 1.0, 1.0, 1.0), Roughness=0.0, IOR=1.45)),
    ("Refraction", bsdf("ShaderNodeBsdfRefraction", (1.0, 1.0, 1.0, 1.0), Roughness=0.1)),
    ("AO", emission_from("ShaderNodeAmbientOcclusion", "AO")),
    ("Blackbody", emission_from("ShaderNodeBlackbody", "Color", Temperature=1500.0)),
    ("Wavelength", emission_from("ShaderNodeWavelength", "Color", Wavelength=550.0)),
    ("Mirror", bsdf("ShaderNodeBsdfGlossy", (1.0, 1.0, 1.0, 1.0), Roughness=0.0)),
]
third = [
    ("Translucent", bsdf("ShaderNodeBsdfTranslucent", (0.4, 0.9, 0.3, 1.0))),
    ("Subsurface", bsdf("ShaderNodeSubsurfaceScattering", (0.9, 0.6, 0.5, 1.0), Scale=1.0, Radius=(1.0, 0.3, 0.15))),
    ("Velvet", bsdf("ShaderNodeBsdfVelvet", (0.6, 0.1, 0.3, 1.0), Sigma=0.5)),
    ("Holdout", lambda tree: tree.nodes.new("ShaderNodeHoldout")),
    ("DiffuseRef", bsdf("ShaderNodeBsdfDiffuse", (0.9, 0.6, 0.5, 1.0))),
]
for row, (y, specs) in enumerate(((0.0, front), (3.0, back), (6.0, third))):
    for i, (name, build) in enumerate(specs):
        x = (i - 2.5) * 2.4
        if name == "AO":
            bpy.ops.mesh.primitive_monkey_add(location=(x, y, 1))
            bpy.context.object.rotation_euler = (0, 0, 3.1416)
            bpy.ops.object.modifier_add(type='SUBSURF')
        else:
            bpy.ops.mesh.primitive_uv_sphere_add(location=(x, y, 1), segments=48, ring_count=24)
        obj = bpy.context.object
        obj.name = name
        bpy.ops.object.shade_smooth()
        obj.data.materials.append(node_material(name + "Mat", build))

bpy.ops.mesh.primitive_plane_add(location=(0, 3.0, 0))
ground = bpy.context.object
ground.scale = (15, 15, 1)
ground.data.materials.append(node_material("GroundMat", bsdf("ShaderNodeBsdfDiffuse", (0.4, 0.4, 0.4, 1.0))))

bpy.ops.object.lamp_add(type='SUN', location=(4, -6, 8))
sun = bpy.context.object
sun.rotation_euler = (0.8, 0.3, 0.6)
sun.data.energy = 2.0

bpy.ops.object.lamp_add(type='POINT', location=(-5, -2, 2.5))
bpy.context.object.data.color = (1.0, 0.3, 0.2)
bpy.context.object.data.energy = 3.0
bpy.context.object.data.distance = 8.0

bpy.ops.object.lamp_add(type='SPOT', location=(5, -3, 5))
spot = bpy.context.object
spot.data.color = (0.3, 0.5, 1.0)
spot.data.energy = 4.0
spot.data.distance = 15.0
spot.rotation_euler = (0.9, 0.0, 0.9)

for lamp in bpy.data.lamps:
    lamp.use_shadow = True

bpy.ops.object.camera_add(location=(0, -12, 4.5), rotation=(1.3, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
