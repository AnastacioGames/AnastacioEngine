"""Triplanar mapping demo, Game engine, Shading Nodes.

Run with:  RangeEngine -b --python tools/create_triplanar_test.py -- demos/triplanar.range [--shot]
Nodes are laid out in colored frames, each with a note (Text datablock) explaining that stage.

- "Pedra Triplanar": the Image Texture node with projection Box (the engine's native triplanar). The texture
  is projected from X, Y and Z in object space and blended by the normal, so meshes without UVs (rocks,
  sculpted terrain, cliffs) get no stretching. Blend sets how soft the border between projections is.
- "Pedra Plana (sem triplanar)": same texture, Flat projection, for comparison: the sides stretch.
Transforms must be applied (object coords in meters) so the texture size is the same on every object.
--shot    adds a camera controller that saves <output>_game.png at frame 30 and ends the game.
"""
import bpy
import math
import os
import random
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "triplanar.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Triplanar World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.25, 0.35, 0.55, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
scene.world = world


# ---------------------------------------------------------------- stone texture

def stone_image(size=512, rows=6, seed=3):
    """Stone bricks with mortar, per-brick tint and grain; tiles seamlessly."""
    rnd = random.Random(seed)
    cols = 4
    tints = [[0.7 + 0.3 * rnd.random() for _ in range(cols)] for _ in range(rows)]
    grain = [rnd.random() for _ in range(64 * 64)]
    px = [0.0] * (size * size * 4)
    bh = size / rows
    bw = size / cols
    for y in range(size):
        r, fy = divmod(y, bh)
        r = int(r)
        off = (bw * 0.5) if r % 2 else 0.0
        for x in range(size):
            c, fx = divmod((x + off) % size, bw)
            c = int(c)
            u, v = fx / bw, fy / bh
            mortar = u < 0.03 or u > 0.97 or v < 0.05 or v > 0.95
            g = grain[(y * 64 // size) * 64 + (x * 64 // size)] * 0.15 + grain[(x * 7 + y * 13) % 4096] * 0.1
            if mortar:
                col = (0.30 + g, 0.29 + g, 0.27 + g)
            else:
                t = tints[r][c] - g
                col = (0.52 * t, 0.47 * t, 0.40 * t)
            i = (y * size + x) * 4
            px[i:i + 4] = (col[0], col[1], col[2], 1.0)
    img = bpy.data.images.new("pedra_tijolo", size, size)
    img.pixels = px
    img.pack(as_png=True)
    return img


# ---------------------------------------------------------------- node layout helpers

def frame(nt, label, color, nodes, text=None):
    """Wraps nodes in a colored frame titled `label`; `text` adds a note frame right above it."""
    f = nt.nodes.new("NodeFrame")
    f.label = label
    f.label_size = 20
    f.use_custom_color = True
    f.color = color
    f.shrink = True
    top = max(n.location.y for n in nodes)
    left = min(n.location.x for n in nodes)
    for n in nodes:
        n.parent = f
    if text:
        note = nt.nodes.new("NodeFrame")
        tb = bpy.data.texts.new("nota - " + label)
        tb.write(text)
        note.text = tb
        note.label = "Nota"
        note.label_size = 14
        note.shrink = False
        note.use_custom_color = True
        note.color = (0.16, 0.16, 0.14)
        lines = text.count("\n") + 1
        note.width = 460
        note.height = 50 + 22 * lines
        note.location = (left - 20, top + 90 + note.height)
    return f


BLUE = (0.18, 0.26, 0.40)
GREEN = (0.20, 0.34, 0.22)
ORANGE = (0.42, 0.28, 0.16)


def stone_material(img, triplanar):
    m = bpy.data.materials.new("Pedra Triplanar" if triplanar else "Pedra Plana (sem triplanar)")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new
    L = nt.links.new

    coord = N("ShaderNodeTexCoord"); coord.location = (-900, 0)
    mapping = N("ShaderNodeMapping"); mapping.location = (-680, 0); mapping.label = "Tamanho da textura"
    mapping.inputs["Scale"].default_value = (0.5, 0.5, 0.5)  # one tile every 2 m
    L(coord.outputs["Object"], mapping.inputs["Vector"])

    tex = N("ShaderNodeTexImage"); tex.image = img; tex.location = (-380, 0)
    tex.label = "Textura (Box = triplanar)" if triplanar else "Textura (Flat)"
    if triplanar:
        tex.projection = 'BOX'
        tex.projection_blend = 0.25
    L(mapping.outputs["Vector"], tex.inputs["Vector"])
    bw = N("ShaderNodeRGBToBW"); bw.location = (-380, -300)
    L(tex.outputs["Color"], bw.inputs["Color"])
    ramp = N("ShaderNodeValToRGB"); ramp.location = (-180, -300); ramp.label = "Rugosidade"
    ramp.color_ramp.elements[0].color = (0.55, 0.55, 0.55, 1.0)
    ramp.color_ramp.elements[1].color = (0.9, 0.9, 0.9, 1.0)
    L(bw.outputs["Val"], ramp.inputs["Fac"])

    bsdf = N("ShaderNodeBsdfPrincipled"); bsdf.location = (140, 0)
    L(tex.outputs["Color"], bsdf.inputs["Base Color"])
    L(ramp.outputs["Color"], bsdf.inputs["Roughness"])
    out = N("ShaderNodeOutputMaterial"); out.location = (440, 0)
    L(bsdf.outputs["BSDF"], out.inputs["Surface"])

    frame(nt, "1. Coordenadas do objeto", BLUE, (coord, mapping),
          "Usa Object (posicao em metros), nao UV: funciona em\n"
          "malhas sem UV. Scale do Mapping = repeticoes por metro\n"
          "(0.5 = um ladrilho a cada 2 m). Aplique a escala (Ctrl+A).")
    if triplanar:
        frame(nt, "2. Projecao triplanar", GREEN, (tex, bw, ramp),
              "Image Texture com projecao Box: projeta de X, Y e Z\n"
              "e mistura pela normal, sem esticar nas laterais.\n"
              "Blend = suavidade da emenda (0 = corte seco, 0.2-0.4 bom).\n"
              "Todas as texturas do material devem usar Box igual.")
    else:
        frame(nt, "2. Projecao plana (comparacao)", GREEN, (tex, bw, ramp),
              "Projecao Flat: so usa X e Y da coordenada.\n"
              "Nas faces de lado a textura estica em listras.\n"
              "Troque para Box para virar triplanar.")
    frame(nt, "3. Sombreamento", ORANGE, (bsdf, out))
    return m


# ---------------------------------------------------------------- scene

def rock(name, loc, mat, seed, size=1.6):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, size=size, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = (1.3, 1.0, 0.8)
    tx = bpy.data.textures.new(name + "_ruido", 'CLOUDS')
    tx.noise_scale = 0.6
    tx.noise_depth = 3
    mod = ob.modifiers.new("Displace", 'DISPLACE')
    mod.texture = tx
    mod.strength = 0.6
    mod.texture_coords = 'GLOBAL'
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat)
    return ob


img = stone_image()
tri = stone_material(img, True)
flat = stone_material(img, False)

rock("PedraPlana", (-2.4, 0.0, 1.2), flat, 1)
rock("PedraTriplanar", (2.4, 0.0, 1.2), tri, 2)

# a cliff behind: big displaced grid, the classic case where UVs stretch
bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=30, radius=1.0, location=(0.0, 7.0, 3.0),
                                rotation=(math.radians(90), 0.0, 0.0))
cliff = bpy.context.object
cliff.name = "Paredao"
cliff.scale = (12.0, 4.0, 1.0)
bpy.ops.object.transform_apply(scale=True, rotation=True)
ctx = bpy.data.textures.new("paredao_ruido", 'CLOUDS')
ctx.noise_scale = 1.2
mod = cliff.modifiers.new("Displace", 'DISPLACE')
mod.texture = ctx
mod.strength = 2.0
mod.direction = 'Y'
mod.texture_coords = 'GLOBAL'
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.object.shade_smooth()
cliff.data.materials.append(tri)

bpy.ops.mesh.primitive_plane_add(location=(0.0, 0.0, 0.0))
ground = bpy.context.object
ground.scale = (40.0, 40.0, 1.0)

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -10.0, 15.0), rotation=(math.radians(50), 0.0, math.radians(-30)))
bpy.context.object.data.energy = 2.0

bpy.ops.object.camera_add(location=(0.0, -11.5, 3.6), rotation=(math.radians(80), 0.0, 0.0))
scene.camera = bpy.context.object

if want_shot:
    shot = base + "_game.png"
    text = bpy.data.texts.new("triplanar_auto_screenshot.py")
    text.write(
        "import Range\n"
        "from Range import logic\n"
        "own = logic.getCurrentController().owner\n"
        "own['frame'] = own.get('frame', 0) + 1\n"
        "if own['frame'] == 30:\n"
        "    Range.render.makeScreenshot('%s')\n"
        "if own['frame'] == 36:\n"
        "    logic.endGame()\n" % shot
    )
    cam = scene.camera
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
    cam.game.sensors[-1].use_pulse_true_level = True
    cam.game.controllers[-1].text = text
    cam.game.sensors[-1].link(cam.game.controllers[-1])

scene.game_settings.show_framerate_profile = False
scene.game_settings.show_debug_properties = False
bpy.ops.wm.save_as_mainfile(filepath=output)
print("TRIPLANAR_TEST saved", output)
