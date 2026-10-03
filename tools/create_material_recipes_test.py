"""Quick Material (receitas) test scene.

Run with:  RangeEngine -b --python tools/create_material_recipes_test.py -- <output.range> [legacy]
Without "legacy" the scene uses PBR Shading Nodes; with it, the Blender Internal nodes.
  - Plane: Blend Textures by Mask, mask filled with black/red/green/blue quarters
  - Cube: Material from Texture Set (generated bricks_albedo/normal/roughness images)
  - Spheres: Ready-made Material presets
"""
import bpy
import os
import sys
import tempfile

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "material_recipes_test.range")
legacy = "legacy" in argv

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = not legacy
world = bpy.data.worlds.new("World")
world.horizon_color = (0.4, 0.45, 0.55)
world.ambient_color = (0.2, 0.2, 0.2)
scene.world = world


def make_image(path, w, h, pixel):
    img = bpy.data.images.new(os.path.basename(path), w, h)
    px = []
    for y in range(h):
        for x in range(w):
            px.extend(pixel(x, y))
    img.pixels = px
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


# Pacote de texturas falso com os sufixos comuns.
folder = os.path.join(os.path.dirname(output), "recipe_textures")
os.makedirs(folder, exist_ok=True)
mortar = lambda x, y: (y % 16 < 2) or ((x + (8 if (y // 16) % 2 else 0)) % 32 < 2)
make_image(os.path.join(folder, "bricks_albedo.png"), 64, 64,
           lambda x, y: (0.8, 0.8, 0.75, 1) if mortar(x, y) else (0.6, 0.2, 0.12, 1))
make_image(os.path.join(folder, "bricks_normal.png"), 64, 64,
           lambda x, y: (0.5, 0.3, 0.8, 1) if y % 16 == 1 else (0.5, 0.5, 1.0, 1))
make_image(os.path.join(folder, "bricks_roughness.png"), 64, 64,
           lambda x, y: (1, 1, 1, 1) if mortar(x, y) else (0.5, 0.5, 0.5, 1))


def select(ob):
    for o in scene.objects:
        o.select = False
    ob.select = True
    scene.objects.active = ob


bpy.ops.mesh.primitive_plane_add(radius=4, location=(0, 0, 0))
plane = scene.objects.active
bpy.ops.material.recipe_mask_blend(tiling=6.0, mask_size=128)
mat = plane.active_material
from bl_operators.anastacio_material_recipes import MASK, find_node, node_image
mask = node_image(find_node(mat, MASK))
px = []
quarter = ((0, 0, 0, 1), (1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1))
for y in range(128):
    for x in range(128):
        px.extend(quarter[(x >= 64) + 2 * (y >= 64)])
mask.pixels = px
mask.pack(as_png=True)
# Camada vermelha recebe o conjunto de tijolos (cor + normal + rugosidade).
bpy.ops.material.recipe_layer_set(layer=1, filepath=os.path.join(folder, "bricks_albedo.png"))
print("RECIPE layers:", sorted(n.name for n in mat.node_tree.nodes if n.name.startswith("AE_layer")))

bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 0, 1.2))
cube = scene.objects.active
bpy.ops.object.material_slot_add()
bpy.ops.material.recipe_texture_set(filepath=os.path.join(folder, "bricks_roughness.png"), tiling=2.0)
print("RECIPE texture set:", sorted(n.name for n in cube.active_material.node_tree.nodes if n.name.startswith("AE_")))

for i, preset in enumerate(("PLASTIC", "METAL", "GOLD", "RUBBER", "GLASS", "EMISSIVE")):
    bpy.ops.mesh.primitive_uv_sphere_add(size=0.5, location=(-3 + i * 1.2, -2.5, 0.6))
    bpy.ops.material.recipe_preset(preset=preset)

bpy.ops.object.lamp_add(type='SUN', location=(2, -3, 6), rotation=(0.6, 0.2, 0.4))
# Game legado: a Sun só projeta sombra com Ray Shadow (o PBR segue o Cast Shadow).
scene.objects.active.data.shadow_method = 'RAY_SHADOW'
bpy.ops.object.camera_add(location=(0, -9, 5), rotation=(1.05, 0, 0))
scene.camera = scene.objects.active

for m in bpy.data.materials:
    if m.use_nodes:
        print("RECIPE", m.name, m.get("anastacio_recipe"), len(m.node_tree.nodes), "nodes",
              len(m.node_tree.links), "links")
bpy.ops.wm.save_as_mainfile(filepath=output)
print("RECIPE saved", output)
