"""Snow / moss coverage demo (world-space "on top" mask), Game engine, Shading Nodes.

Run with:  RangeEngine -b --python tools/create_snow_moss_test.py -- demos/neve_musgo.range [--shot]

- Node group "Cobertura": mask = dot(world normal, up) remapped by Amount/Softness, with a Noise texture
  (in world position) added before the remap so the border is irregular. It mixes the base color/roughness
  with the cover color/roughness. Uses the Geometry node Normal, which is WORLD space in GLSL (same as
  Cycles): rotating the object keeps the cover on top. (Texture Coordinate > Normal is OBJECT space and
  would rotate with the object.)
- "Pedra com Neve" and "Pedra com Musgo": triplanar stone base (Image Texture, Box projection) + the group.
- Rocks, cubes and Suzanne at different rotations; "CuboGirando" and "SuzanneGirando" rotate in game.
--shot    adds a camera controller that saves <output>_game.png at frame 60 and ends the game.
"""
import bpy
import math
import os
import random
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "neve_musgo.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Neve World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.45, 0.55, 0.70, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
scene.world = world


# ---------------------------------------------------------------- stone texture

def stone_image(size=256, seed=5):
    """Rough grey stone: tiling value noise in two octaves."""
    rnd = random.Random(seed)
    g = 32
    grid = [rnd.random() for _ in range(g * g)]

    def smooth(x, y):
        fx, fy = x * g / size, y * g / size
        x0, y0 = int(fx) % g, int(fy) % g
        x1, y1 = (x0 + 1) % g, (y0 + 1) % g
        tx, ty = fx - int(fx), fy - int(fy)
        a = grid[y0 * g + x0] * (1 - tx) + grid[y0 * g + x1] * tx
        b = grid[y1 * g + x0] * (1 - tx) + grid[y1 * g + x1] * tx
        return a * (1 - ty) + b * ty

    px = [0.0] * (size * size * 4)
    for y in range(size):
        for x in range(size):
            v = 0.6 * smooth(x, y) + 0.4 * smooth((x * 3) % size, (y * 3) % size)
            v = 0.22 + 0.3 * v
            i = (y * size + x) * 4
            px[i:i + 4] = (v * 1.02, v, v * 0.94, 1.0)
    img = bpy.data.images.new("pedra_cinza", size, size)
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
        note.width = 400
        note.height = 50 + 22 * lines
        note.location = (left - 20, top + 90 + note.height)
    return f


BLUE = (0.18, 0.26, 0.40)
GREEN = (0.20, 0.34, 0.22)
ORANGE = (0.42, 0.28, 0.16)
PURPLE = (0.32, 0.22, 0.40)


def node(nt, kind, loc, label=None, hide=False, **props):
    n = nt.nodes.new(kind)
    for k, v in props.items():
        setattr(n, k, v)
    n.location = loc
    n.hide = hide
    if label:
        n.label = label
    return n


def math_node(nt, op, loc, a, b=0.0, label=None, clamp=False):
    """Collapsed Math node; a/b are numbers or sockets."""
    n = node(nt, "ShaderNodeMath", loc, label, hide=True, operation=op)
    n.use_clamp = clamp
    for sock, v in ((n.inputs[0], a), (n.inputs[1], b)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        else:
            nt.links.new(v, sock)
    return n


# ---------------------------------------------------------------- "Cobertura" node group

def cover_group():
    grp = bpy.data.node_groups.new("Cobertura", 'ShaderNodeTree')
    grp.inputs.new("NodeSocketColor", "Base Color").default_value = (0.5, 0.5, 0.5, 1.0)
    grp.inputs.new("NodeSocketFloat", "Base Roughness").default_value = 0.8
    s = grp.inputs.new("NodeSocketFloat", "Amount"); s.default_value = 0.5; s.min_value = 0.0; s.max_value = 1.0
    s = grp.inputs.new("NodeSocketFloat", "Softness"); s.default_value = 0.15; s.min_value = 0.0; s.max_value = 1.0
    s = grp.inputs.new("NodeSocketFloat", "Noise Breakup"); s.default_value = 0.5; s.min_value = 0.0; s.max_value = 2.0
    grp.inputs.new("NodeSocketFloat", "Noise Scale").default_value = 3.0
    grp.inputs.new("NodeSocketColor", "Cover Color").default_value = (0.95, 0.97, 1.0, 1.0)
    grp.inputs.new("NodeSocketFloat", "Cover Roughness").default_value = 0.6
    grp.outputs.new("NodeSocketColor", "Color")
    grp.outputs.new("NodeSocketFloat", "Roughness")
    grp.outputs.new("NodeSocketFloat", "Mask")
    L = grp.links.new

    gi = node(grp, "NodeGroupInput", (-1000, -200), "Entradas")

    # 1. world normal . up  (Normal Z == dot(N, (0, 0, 1)))
    geo = node(grp, "ShaderNodeNewGeometry", (-700, 0), "Geometria (mundo)")
    sep = node(grp, "ShaderNodeSeparateXYZ", (-480, 0), "Normal Z = dot(N, cima)")
    L(geo.outputs["Normal"], sep.inputs[0])

    # 2. noise added to Z so the border is irregular
    noise = node(grp, "ShaderNodeTexNoise", (-700, -380), "Ruido da borda")
    noise.inputs["Detail"].default_value = 3.0
    L(geo.outputs["Position"], noise.inputs["Vector"])
    L(gi.outputs["Noise Scale"], noise.inputs["Scale"])
    n_c = math_node(grp, 'SUBTRACT', (-480, -380), noise.outputs["Fac"], 0.5, "ruido - 0.5")
    n_b = math_node(grp, 'MULTIPLY', (-480, -420), n_c.outputs[0], gi.outputs["Noise Breakup"], "x quebra")
    z_n = math_node(grp, 'ADD', (-480, -460), sep.outputs["Z"], n_b.outputs[0], "Z + ruido")

    # 3. remap: mask = clamp((z - (1 - 2 * amount)) / softness, 0, 1)
    a2 = math_node(grp, 'MULTIPLY', (-200, -200), gi.outputs["Amount"], 2.0, "quantidade x 2")
    th = math_node(grp, 'SUBTRACT', (-200, -240), 1.0, a2.outputs[0], "limiar = 1 - 2q")
    d = math_node(grp, 'SUBTRACT', (-200, -280), z_n.outputs[0], th.outputs[0], "Z - limiar")
    sf = math_node(grp, 'MAXIMUM', (-200, -320), gi.outputs["Softness"], 0.001, "suavidade > 0")
    mask = math_node(grp, 'DIVIDE', (-200, -360), d.outputs[0], sf.outputs[0], "mascara", clamp=True)

    # 4. mix base and cover
    mix = node(grp, "ShaderNodeMixRGB", (120, 0), "Base x Cobertura")
    L(mask.outputs[0], mix.inputs[0])
    L(gi.outputs["Base Color"], mix.inputs[1])
    L(gi.outputs["Cover Color"], mix.inputs[2])
    r_d = math_node(grp, 'SUBTRACT', (120, -240), gi.outputs["Cover Roughness"], gi.outputs["Base Roughness"],
                    "rug. cob - base")
    r_m = math_node(grp, 'MULTIPLY', (120, -280), r_d.outputs[0], mask.outputs[0], "x mascara")
    r_a = math_node(grp, 'ADD', (120, -320), gi.outputs["Base Roughness"], r_m.outputs[0], "rugosidade")
    go = node(grp, "NodeGroupOutput", (420, -100), "Saidas")
    L(mix.outputs["Color"], go.inputs["Color"])
    L(r_a.outputs[0], go.inputs["Roughness"])
    L(mask.outputs[0], go.inputs["Mask"])

    frame(grp, "1. Normal do mundo", BLUE, (geo, sep),
          "Geometry > Normal e no espaco do MUNDO:\n"
          "girar o objeto mantem a neve em cima.\n"
          "(Texture Coordinate > Normal gira junto.)")
    frame(grp, "2. Ruido na borda", GREEN, (noise, n_c, n_b, z_n),
          "Ruido na posicao do mundo somado ao Z.\n"
          "Noise Breakup = quanto a borda serrilha.\n"
          "Noise Scale = tamanho das manchas.")
    frame(grp, "3. Mascara", PURPLE, (a2, th, d, sf, mask),
          "Amount 0 = nada, 1 = tudo coberto.\n"
          "Softness = largura da transicao.\n"
          "Saida Mask serve p/ outros efeitos.")
    frame(grp, "4. Mistura", ORANGE, (mix, r_d, r_m, r_a))
    return grp


def cover_material(name, grp, img, cover, amount, softness, breakup, scale, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    L = nt.links.new
    coord = node(nt, "ShaderNodeTexCoord", (-1000, 0))
    mapping = node(nt, "ShaderNodeMapping", (-800, 0), "Tamanho da textura")
    mapping.inputs["Scale"].default_value = (0.7, 0.7, 0.7)
    L(coord.outputs["Object"], mapping.inputs["Vector"])
    tex = node(nt, "ShaderNodeTexImage", (-520, 0), "Pedra (Box = triplanar)")
    tex.image = img
    tex.projection = 'BOX'
    tex.projection_blend = 0.3
    L(mapping.outputs["Vector"], tex.inputs["Vector"])

    gn = node(nt, "ShaderNodeGroup", (-200, 0), "Cobertura")
    gn.node_tree = grp
    gn.width = 200
    gn.inputs["Amount"].default_value = amount
    gn.inputs["Softness"].default_value = softness
    gn.inputs["Noise Breakup"].default_value = breakup
    gn.inputs["Noise Scale"].default_value = scale
    gn.inputs["Cover Color"].default_value = cover
    gn.inputs["Cover Roughness"].default_value = rough
    gn.inputs["Base Roughness"].default_value = 0.85
    L(tex.outputs["Color"], gn.inputs["Base Color"])

    bsdf = node(nt, "ShaderNodeBsdfPrincipled", (100, 0))
    L(gn.outputs["Color"], bsdf.inputs["Base Color"])
    L(gn.outputs["Roughness"], bsdf.inputs["Roughness"])
    out = node(nt, "ShaderNodeOutputMaterial", (400, 0))
    L(bsdf.outputs["BSDF"], out.inputs["Surface"])

    frame(nt, "1. Material base", BLUE, (coord, mapping, tex),
          "Pedra triplanar (Box) em coord. Object.\n"
          "Troque por qualquer cor/textura base.")
    frame(nt, "2. Cobertura (grupo)", GREEN, (gn,),
          "Tab entra no grupo. Amount = quantidade,\n"
          "Softness = borda, Noise = irregular,\n"
          "Cover Color = neve ou musgo.")
    frame(nt, "3. Sombreamento", ORANGE, (bsdf, out))
    return m


# ---------------------------------------------------------------- scene

def rock(name, loc, mat, rot=(0, 0, 0), size=1.2):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, size=size, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = (1.3, 1.0, 0.8)
    tx = bpy.data.textures.new(name + "_ruido", 'CLOUDS')
    tx.noise_scale = 0.6
    mod = ob.modifiers.new("Displace", 'DISPLACE')
    mod.texture = tx
    mod.strength = 0.5
    mod.texture_coords = 'GLOBAL'
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.transform_apply(scale=True)
    ob.rotation_euler = rot
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat)
    return ob


def cube(name, loc, mat, rot):
    bpy.ops.mesh.primitive_cube_add(radius=0.8, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    bev = ob.modifiers.new("Bevel", 'BEVEL')
    bev.width = 0.12
    bev.segments = 3
    bpy.ops.object.modifier_apply(modifier=bev.name)
    ob.data.materials.append(mat)
    return ob


def monkey(name, loc, mat, rot):
    bpy.ops.mesh.primitive_monkey_add(radius=1.0, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    sub = ob.modifiers.new("Subsurf", 'SUBSURF')
    sub.levels = 2
    bpy.ops.object.modifier_apply(modifier=sub.name)
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat)
    return ob


img = stone_image()
grp = cover_group()
snow = cover_material("Pedra com Neve", grp, img, (0.95, 0.97, 1.0, 1.0), 0.45, 0.12, 0.6, 2.5, 0.55)
moss = cover_material("Pedra com Musgo", grp, img, (0.06, 0.15, 0.025, 1.0), 0.4, 0.25, 0.9, 4.0, 0.95)

R = math.radians
# left side: snow
rock("PedraNeve", (-4.2, 1.0, 1.0), snow)
monkey("SuzanneNeve", (-1.6, 0.0, 1.2), snow, (R(-20), R(25), R(-15)))
cube("CuboGirando", (-2.8, -2.6, 1.2), snow, (R(30), R(20), 0))
# right side: moss
rock("PedraMusgo", (4.2, 1.0, 1.0), moss, rot=(R(40), 0, R(30)))
cube("CuboMusgo", (2.8, -2.6, 0.8), moss, (0, R(45), R(20)))
monkey("SuzanneGirando", (1.6, 0.0, 1.3), moss, (0, 0, 0))

# the two "Girando" objects tumble in game: the cover must stay on top
spin = bpy.data.texts.new("girar.py")
spin.write(
    "from Range import logic\n"
    "own = logic.getCurrentController().owner\n"
    "own.applyRotation((0.013, 0.021, 0.008), False)\n"
)
for name in ("CuboGirando", "SuzanneGirando"):
    ob = bpy.data.objects[name]
    scene.objects.active = ob
    bpy.ops.logic.sensor_add(type='ALWAYS', object=ob.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=ob.name)
    ob.game.sensors[-1].use_pulse_true_level = True
    ob.game.controllers[-1].text = spin
    ob.game.sensors[-1].link(ob.game.controllers[-1])

bpy.ops.mesh.primitive_plane_add(location=(0.0, 0.0, 0.0))
ground = bpy.context.object
ground.scale = (40.0, 40.0, 1.0)
gmat = bpy.data.materials.new("Chao")
gmat.diffuse_color = (0.18, 0.16, 0.14)
ground.data.materials.append(gmat)

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -10.0, 15.0), rotation=(R(50), 0.0, R(-30)))
bpy.context.object.data.energy = 2.0

bpy.ops.object.camera_add(location=(0.0, -15.0, 6.0), rotation=(R(73), 0.0, 0.0))
scene.camera = bpy.context.object

if want_shot:
    shot = base + "_game.png"
    text = bpy.data.texts.new("neve_auto_screenshot.py")
    text.write(
        "import Range\n"
        "from Range import logic\n"
        "own = logic.getCurrentController().owner\n"
        "own['frame'] = own.get('frame', 0) + 1\n"
        "if own['frame'] == 60:\n"
        "    Range.render.makeScreenshot('%s')\n"
        "if own['frame'] == 66:\n"
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
print("SNOW_MOSS_TEST saved", output)
