"""Quick Material (receitas) test scene.

Run with:  RangeEngine -b --python tools/create_material_recipes_test.py -- <output.range> [legacy]
Without "legacy" the scene uses PBR Shading Nodes; with it, the Blender Internal nodes.
  - Plane: Blend Textures by Mask, mask filled with black/red/green/blue quarters
  - Cube: Material from Texture Set (generated bricks_albedo/normal/roughness images)
  - Road strip: Wet/Reflective Patches, mask filled with two wet streaks
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

bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 3.2, 0.03))
road = scene.objects.active
road.name = "Wet Patch Road"
road.scale = (4.0, 1.0, 0.03)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.ops.material.recipe_wet_patches(tiling=16.0, mask_size=128)
mat = road.active_material
from bl_operators.anastacio_material_recipes import WET_MASK
wet_mask = node_image(find_node(mat, WET_MASK))
px = []
for y in range(128):
    for x in range(128):
        stripe = 1.0 if (34 < x < 54 and 16 < y < 112) or (76 < x < 100 and 28 < y < 104) else 0.0
        feather = 0.35 if (28 < x < 108 and 10 < y < 118 and stripe == 0.0 and (x + y) % 17 < 3) else 0.0
        v = max(stripe, feather)
        px.extend((v, v, v, 1.0))
wet_mask.pixels = px
wet_mask.pack(as_png=True)
print("RECIPE wet patches:", sorted(n.name for n in mat.node_tree.nodes if n.name.startswith("AE_")))

for i, preset in enumerate(("PLASTIC", "METAL", "GOLD", "RUBBER", "GLASS", "EMISSIVE")):
    bpy.ops.mesh.primitive_uv_sphere_add(size=0.5, location=(-3 + i * 1.2, -2.5, 0.6))
    bpy.ops.material.recipe_preset(preset=preset)

bpy.ops.object.lamp_add(type='SUN', location=(2, -3, 6), rotation=(0.6, 0.2, 0.4))
# Game legado: a Sun só projeta sombra com Ray Shadow (o PBR segue o Cast Shadow).
scene.objects.active.data.shadow_method = 'RAY_SHADOW'
bpy.ops.object.camera_add(location=(0, -9, 5), rotation=(1.05, 0, 0))
scene.camera = scene.objects.active

main_cam = scene.camera

scene.game_settings.show_framerate_profile = False
scene.game_settings.show_debug_properties = False
scene.game_settings.show_debug_mode = False

for m in bpy.data.materials:
    if m.use_nodes:
        print("RECIPE", m.name, m.get("anastacio_recipe"), len(m.node_tree.nodes), "nodes",
              len(m.node_tree.links), "links")
bpy.ops.wm.save_as_mainfile(filepath=output)
print("RECIPE saved", output)

if "--auto-screenshot" in sys.argv:
    shot_path = os.path.join(os.path.dirname(output), "material_recipes_test.png").replace("\\", "/")
    controller = (
        "import Range\n"
        "from Range import logic\n"
        "cont = logic.getCurrentController()\n"
        "own = cont.owner\n"
        "own['frame'] = own.get('frame', 0) + 1\n"
        "if own['frame'] == 12:\n"
        "    Range.render.makeScreenshot('%s')\n"
        "if own['frame'] == 16:\n"
        "    logic.endGame()\n"
    ) % shot_path
    text = bpy.data.texts.new("auto_screenshot.py")
    text.write(controller)
    # Angulo raso sobre a faixa molhada da pista, pegando o highlight especular da Sun.
    main_cam.location = (0, 2.0, 0.5)
    main_cam.rotation_euler = (1.3, 0, 0)
    main_cam.data.lens = 35.0
    cam_ob = scene.camera
    scene.objects.active = cam_ob
    bpy.ops.logic.sensor_add(type='ALWAYS', object=cam_ob.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=cam_ob.name)
    cam_ob.game.sensors[-1].use_pulse_true_level = True
    cam_ob.game.controllers[-1].text = text
    cam_ob.game.sensors[-1].link(cam_ob.game.controllers[-1])
    bpy.ops.wm.save_as_mainfile(filepath=output)
    print("RECIPE auto-screenshot wired ->", shot_path)
