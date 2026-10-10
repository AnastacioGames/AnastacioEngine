"""Parallax block wall + fake building interiors (interior mapping) test scene, Game engine, Shading Nodes.

Run with:  RangeEngine -b --python tools/create_parallax_interior_test.py -- demos/parallax_interior_mapping.range [--shot]
Nodes are laid out in colored frames, each with a note (Text datablock) explaining that stage.

- "Blocos Parallax": a wall whose surface looks made of blocks sticking out at random heights. Uses the
  engine's own Parallax node (steep parallax / occlusion on a height map) fed by a generated 8x8 block height
  map; the same shifted UV reads the color map and a normal map baked from the height, so block sides and
  grooves shade right (a Bump node on the height map turns noisy on the block sides).
- "Interior Mapping": node group that fakes a real room behind every window of a building. The view ray is
  taken to object space and intersected with the grid of room boxes (floor/ceil/fract per axis); the face it
  hits picks wall, floor or ceiling color, a hash of the room id picks lit/unlit and tint. Works on every face
  of the mesh at once; transforms must be applied (object coords in meters) so "Room Size" is in meters.
--shot    adds a camera controller that saves <output>_game.png at frame 30 and ends the game.
"""
import bpy
import math
import os
import random
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "parallax_interior_test.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Parallax World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.25, 0.35, 0.55, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
scene.world = world


# ---------------------------------------------------------------- block maps

def block_images(n=8, size=512, gap=0.04, bevel=0.05, depth_scale=0.1, seed=7):
    """Height map (blocks at random heights, grooves at 0) and matching color map."""
    rnd = random.Random(seed)
    heights = [[0.35 + 0.65 * rnd.random() for _ in range(n)] for _ in range(n)]
    tints = [[0.75 + 0.25 * rnd.random() for _ in range(n)] for _ in range(n)]
    hpx = [0.0] * (size * size * 4)
    cpx = [0.0] * (size * size * 4)
    cell = size / n
    for y in range(size):
        cy, fy = divmod(y, cell)
        cy = int(cy)
        for x in range(size):
            cx, fx = divmod(x, cell)
            cx = int(cx)
            u, v = fx / cell, fy / cell
            groove = u < gap or u > 1.0 - gap or v < gap or v > 1.0 - gap
            # bevel: a short ramp from the groove up to the block top. A hard step makes the
            # parallax hit and the shading slope land on a single texel and the block sides get noisy.
            e = min(u, 1.0 - u, v, 1.0 - v) - gap
            r = max(0.0, min(1.0, e / bevel))
            r = r * r * (3.0 - 2.0 * r)
            h = heights[cy][cx] * r
            t = tints[cy][cx]
            i = (y * size + x) * 4
            hpx[i:i + 4] = (h, h, h, 1.0)
            c = (0.08, 0.08, 0.09) if groove else (0.55 * t, 0.42 * t, 0.32 * t)
            cpx[i:i + 4] = (c[0], c[1], c[2], 1.0)
    himg = bpy.data.images.new("blocos_height", size, size)
    cimg = bpy.data.images.new("blocos_color", size, size)
    himg.colorspace_settings.name = 'Non-Color'
    himg.pixels = hpx
    cimg.pixels = cpx
    # tangent-space normal map from the height (central differences, wraps like the texture)
    k = depth_scale * size / 2.0
    npx = [0.0] * (size * size * 4)
    for y in range(size):
        yu, yd = ((y + 1) % size) * size, ((y - 1) % size) * size
        row = y * size
        for x in range(size):
            xr, xl = (x + 1) % size, (x - 1) % size
            dx = (hpx[(row + xr) * 4] - hpx[(row + xl) * 4]) * k
            dy = (hpx[(yu + x) * 4] - hpx[(yd + x) * 4]) * k
            inv = 1.0 / math.sqrt(dx * dx + dy * dy + 1.0)
            i = (row + x) * 4
            npx[i:i + 4] = (0.5 - 0.5 * dx * inv, 0.5 - 0.5 * dy * inv, 0.5 + 0.5 * inv, 1.0)
    nimg = bpy.data.images.new("blocos_normal", size, size)
    nimg.colorspace_settings.name = 'Non-Color'
    nimg.pixels = npx
    himg.pack(as_png=True)
    cimg.pack(as_png=True)
    nimg.pack(as_png=True)
    return himg, cimg, nimg


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
PURPLE = (0.32, 0.22, 0.40)


def blocks_material():
    himg, cimg, nimg = block_images()
    tex = bpy.data.textures.new("blocos_height", 'IMAGE')
    tex.image = himg

    m = bpy.data.materials.new("Blocos Parallax")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new
    L = nt.links.new

    coord = N("ShaderNodeTexCoord"); coord.location = (-900, 0)
    par = N("ShaderNodeParallax"); par.location = (-680, 0)
    par.texture = tex
    par.component = 'RED'
    par.inputs["Steps"].default_value = 32.0
    par.inputs["Bump Scale"].default_value = 0.1
    L(coord.outputs["UV"], par.inputs["UV"])

    col = N("ShaderNodeTexImage"); col.image = cimg; col.label = "Cor dos blocos"
    col.location = (-400, 60)
    nrm = N("ShaderNodeTexImage"); nrm.image = nimg; nrm.color_space = 'NONE'; nrm.label = "Normal map"
    nrm.location = (-400, -240)
    uvsrc = coord.outputs["UV"] if "--plain" in argv else par.outputs["UV"]
    L(uvsrc, col.inputs["Vector"]); L(uvsrc, nrm.inputs["Vector"])

    nmap = N("ShaderNodeNormalMap"); nmap.space = 'TANGENT'; nmap.location = (-140, -240)
    L(nrm.outputs["Color"], nmap.inputs["Color"])

    bsdf = N("ShaderNodeBsdfPrincipled"); bsdf.location = (140, 60)
    bsdf.inputs["Roughness"].default_value = 0.7
    L(col.outputs["Color"], bsdf.inputs["Base Color"])
    L(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    out = N("ShaderNodeOutputMaterial"); out.location = (440, 60)
    L(bsdf.outputs["BSDF"], out.inputs["Surface"])

    frame(nt, "1. Parallax: desloca o UV", BLUE, (coord, par),
          "O no Parallax le o height map (textura 'blocos_height')\n"
          "e desloca o UV como se a superficie tivesse relevo.\n"
          "Bump Scale = altura dos blocos. Steps = qualidade.\n"
          "Ligue o UV direto do Texture Coordinate.")
    frame(nt, "2. Texturas com o UV deslocado", GREEN, (col, nrm, nmap),
          "TODAS as texturas usam o UV que sai do Parallax.\n"
          "Use normal map (nao Bump) para o sombreamento:\n"
          "o Bump fica ruidoso nas laterais dos blocos.")
    frame(nt, "3. Sombreamento", ORANGE, (bsdf, out))
    return m


# ---------------------------------------------------------------- interior mapping group

class G:
    """Helper to wire math nodes inside a node tree, laid out in stages (frames) and lanes (rows)."""

    def __init__(self, nt):
        self.nt = nt
        self.x0 = 0
        self.lanes = {}
        self.lane_id = 0
        self.nodes = []

    def stage(self):
        """Starts a new column of nodes to the right of the previous one."""
        if self.lanes:
            self.x0 = max(self.lanes.values()) + 160
        self.lanes = {}
        self.lane_id = 0
        self.nodes = []

    def lane(self, k):
        self.lane_id = k

    def node(self, kind, hide=False, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        n.hide = hide
        x = self.lanes.get(self.lane_id, self.x0)
        n.location = (x, -self.lane_id * 240)
        self.lanes[self.lane_id] = x + (150 if hide else 200)
        self.nodes.append(n)
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def math(self, op, a, b=0.0, label=None):
        n = self.node("ShaderNodeMath", hide=True, operation=op)
        if label:
            n.label = label
        for sock, v in ((n.inputs[0], a), (n.inputs[1], b)):
            if isinstance(v, (int, float)):
                sock.default_value = v
            else:
                self.link(v, sock)
        return n.outputs[0]

    def mix(self, fac, a, b, label=None, blend='MIX'):
        n = self.node("ShaderNodeMixRGB", blend_type=blend)
        if label:
            n.label = label
        for sock, v in ((n.inputs[0], fac), (n.inputs[1], a), (n.inputs[2], b)):
            if isinstance(v, (int, float, tuple)):
                sock.default_value = v
            else:
                self.link(v, sock)
        return n.outputs[0]

    def frame(self, label, color, text=None):
        frame(self.nt, label, color, self.nodes, text)


def interior_group():
    grp = bpy.data.node_groups.new("Interior Mapping", 'ShaderNodeTree')
    gi = grp.nodes.new("NodeGroupInput")
    go = grp.nodes.new("NodeGroupOutput")
    grp.inputs.new("NodeSocketVector", "Room Size").default_value = (4.0, 4.0, 3.0)
    grp.inputs.new("NodeSocketColor", "Wall").default_value = (0.75, 0.62, 0.48, 1.0)
    grp.inputs.new("NodeSocketColor", "Floor").default_value = (0.35, 0.22, 0.14, 1.0)
    grp.inputs.new("NodeSocketColor", "Ceiling").default_value = (0.9, 0.9, 0.85, 1.0)
    grp.inputs.new("NodeSocketFloat", "Lit Ratio").default_value = 0.55
    # shifts the room grid so faces that are not multiples of Room Size still start at a wall
    grp.inputs.new("NodeSocketVector", "Offset").default_value = (0.0, 0.0, 0.0)
    grp.outputs.new("NodeSocketColor", "Color")
    grp.outputs.new("NodeSocketFloat", "Depth")
    gi.location = (-320, -200)
    g = G(grp)

    # 1. inputs: view ray and position, both in object space
    g.stage()
    coord = g.node("ShaderNodeTexCoord")
    shift = g.node("ShaderNodeVectorMath", operation='ADD'); shift.label = "Posicao + Offset"
    g.link(coord.outputs["Object"], shift.inputs[0]); g.link(gi.outputs["Offset"], shift.inputs[1])
    sep_p = g.node("ShaderNodeSeparateXYZ"); sep_p.label = "Posicao"
    g.link(shift.outputs[0], sep_p.inputs[0])
    g.lane(1)
    geom = g.node("ShaderNodeNewGeometry")
    xf = g.node("ShaderNodeVectorTransform", vector_type='VECTOR', convert_from='WORLD', convert_to='OBJECT')
    xf.label = "Raio da camera (objeto)"
    g.link(geom.outputs["Incoming"], xf.inputs[0])
    sep_d = g.node("ShaderNodeSeparateXYZ"); sep_d.label = "Raio"
    g.link(xf.outputs[0], sep_d.inputs[0])
    g.lane(2)
    sep_s = g.node("ShaderNodeSeparateXYZ"); sep_s.label = "Tamanho do comodo"
    g.link(gi.outputs["Room Size"], sep_s.inputs[0])
    g.frame("1. Raio e posicao", BLUE,
            "Posicao do pixel e direcao da camera, no espaco do objeto.\n"
            "Por isso a escala do objeto precisa estar aplicada (Ctrl+A).")

    # 2. per axis: distance from the point to the next room wall along the ray
    g.stage()
    p, d, t, cell = [], [], [], []
    for a, axis in enumerate("XYZ"):
        g.lane(a)
        # ray and position both in room units, otherwise non-cubic rooms get distorted
        da = g.math('DIVIDE', g.math('MULTIPLY', sep_d.outputs[a], -1.0), sep_s.outputs[a], "raio " + axis)
        # keep |d| >= 1e-5 with its sign (axis-parallel rays would divide by zero)
        sgn = g.math('SUBTRACT', g.math('MULTIPLY', g.math('GREATER_THAN', da, 0.0), 2.0), 1.0, "sinal")
        da = g.math('ADD', da, g.math('MULTIPLY', sgn, 1e-5), "raio sem zero")
        pa = g.math('DIVIDE', sep_p.outputs[a], sep_s.outputs[a], "pos " + axis)
        # nudge inside so a point on a face belongs to the room behind it
        pa = g.math('ADD', pa, g.math('MULTIPLY', da, 0.002), "empurra p/ dentro")
        ca = g.math('FLOOR', pa, label="comodo " + axis)
        plane = g.math('ADD', ca, g.math('GREATER_THAN', da, 0.0), "parede alvo")
        ta = g.math('DIVIDE', g.math('SUBTRACT', plane, pa), da, "dist " + axis)
        p.append(pa); d.append(da); t.append(ta); cell.append(ca)
    g.frame("2. Raio x grade de comodos (X, Y, Z)", PURPLE,
            "Uma linha por eixo. Tudo em unidades de comodo.\n"
            "comodo = floor(pos); dist = quanto o raio anda\n"
            "ate a proxima parede daquele eixo.")

    # 3. nearest wall wins: which face of the room the ray hits, and where
    g.stage()
    g.lane(0)
    tmin = g.math('MINIMUM', g.math('MINIMUM', t[0], t[1]), t[2], "dist minima")
    g.lane(1)
    hit = [g.math('FRACT', g.math('ADD', p[a], g.math('MULTIPLY', d[a], tmin)), label="ponto " + "XYZ"[a])
           for a in range(3)]
    g.lane(2)
    is_x = g.math('LESS_THAN', t[0], g.math('ADD', tmin, 1e-4), "bateu em X")
    is_z = g.math('LESS_THAN', t[2], g.math('ADD', tmin, 1e-4), "bateu em Z")
    is_floor = g.math('LESS_THAN', d[2], 0.0, "olhando p/ baixo")
    g.lane(3)
    # per-room hash: fract(sin(dot(cell, k)) * 43758.5)
    hsh = g.math('ADD', g.math('ADD', g.math('MULTIPLY', cell[0], 12.9898),
                                g.math('MULTIPLY', cell[1], 78.233)),
                 g.math('MULTIPLY', cell[2], 37.719))
    hsh = g.math('FRACT', g.math('MULTIPLY', g.math('SINE', hsh), 43758.5453), label="sorteio do comodo")
    lit = g.math('LESS_THAN', hsh, gi.outputs["Lit Ratio"], "aceso?")
    g.frame("3. Qual parede o raio acerta", GREEN,
            "A menor distancia e a parede atingida.\n"
            "Z = piso ou teto; X/Y = paredes.\n"
            "Um numero aleatorio por comodo decide se a luz esta acesa.")

    # 4. colors
    g.stage()
    g.lane(0)
    # walls: darker toward the floor, side walls a bit darker than the back one
    wall_shade = g.math('ADD', 0.55, g.math('MULTIPLY', hit[2], 0.45), "escurece embaixo")
    wall_shade = g.math('MULTIPLY', wall_shade, g.math('ADD', 0.85, g.math('MULTIPLY', is_x, 0.15)),
                        "lateral mais escura")
    g.lane(1)
    wall = g.mix(1.0, gi.outputs["Wall"], wall_shade, "Parede", 'MULTIPLY')
    fc = g.mix(is_floor, gi.outputs["Ceiling"], gi.outputs["Floor"], "Piso / Teto")
    room = g.mix(is_z, wall, fc, "Parede ou Piso/Teto")
    g.lane(2)
    # tint per room and light: lit rooms glow warm, unlit are dim and bluish
    tint = g.mix(hsh, (1.0, 0.85, 0.6, 1.0), (0.85, 0.9, 1.0, 1.0), "Tom da lampada")
    on = g.mix(1.0, room, tint, "Aceso", 'MULTIPLY')
    off = g.mix(1.0, room, (0.04, 0.05, 0.08, 1.0), "Apagado", 'MULTIPLY')
    g.lane(3)
    final = g.mix(lit, off, on, "Aceso ou apagado")
    # deeper hits a bit darker (fake falloff of the room light)
    depth = g.math('MINIMUM', tmin, 2.0, "profundidade")
    fall = g.math('SUBTRACT', 1.0, g.math('MULTIPLY', depth, 0.3), "luz cai no fundo")
    res = g.mix(1.0, final, fall, "Cor final", 'MULTIPLY')
    g.frame("4. Cores do comodo", ORANGE,
            "Parede, piso e teto vem das entradas do grupo.\n"
            "Acesos ganham tom de lampada; apagados ficam azulados.\n"
            "O fundo do comodo fica um pouco mais escuro.")

    g.link(res, go.inputs["Color"])
    g.link(depth, go.inputs["Depth"])
    go.location = (max(g.lanes.values()) + 180, -200)
    return grp


def interior_material(grp):
    m = bpy.data.materials.new("Interior Mapping")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new
    L = nt.links.new
    gn = N("ShaderNodeGroup"); gn.node_tree = grp; gn.location = (-640, 0)
    emit = N("ShaderNodeEmission"); emit.location = (-380, 0)
    emit.inputs["Strength"].default_value = 1.5
    L(gn.outputs["Color"], emit.inputs["Color"])
    # window glass: sky reflection on top, stronger at grazing angles
    fres = N("ShaderNodeFresnel"); fres.location = (-640, -300)
    fres.inputs["IOR"].default_value = 1.5
    glass = N("ShaderNodeBsdfGlossy"); glass.location = (-380, -300)
    glass.inputs["Roughness"].default_value = 0.05
    mix = N("ShaderNodeMixShader"); mix.location = (-80, 0); mix.label = "Comodo + reflexo"
    L(fres.outputs[0], mix.inputs[0]); L(emit.outputs[0], mix.inputs[1]); L(glass.outputs[0], mix.inputs[2])
    out = N("ShaderNodeOutputMaterial"); out.location = (160, 0)
    L(mix.outputs[0], out.inputs["Surface"])

    frame(nt, "1. Comodos falsos", BLUE, (gn, emit),
          "Grupo 'Interior Mapping' (Tab para entrar e ver por dentro).\n"
          "Room Size em metros; Offset alinha a grade na fachada.\n"
          "Emission: o comodo tem luz propria, nao depende do sol.")
    frame(nt, "2. Vidro da janela", GREEN, (fres, glass))
    frame(nt, "3. Saida", ORANGE, (mix, out))
    return m


# ---------------------------------------------------------------- scene

bpy.ops.mesh.primitive_plane_add(calc_uvs=True, location=(-4.0, 0.0, 3.0), rotation=(math.radians(90), 0.0, 0.0))
wall = bpy.context.object
wall.name = "ParedeBlocos"
wall.scale = (3.0, 3.0, 1.0)
bpy.ops.object.transform_apply(scale=True)
wall.data.materials.append(blocks_material())

bpy.ops.mesh.primitive_cube_add(location=(6.0, 6.0, 9.0))
building = bpy.context.object
building.name = "Predio"
building.scale = (4.0, 4.0, 9.0)  # 8 x 8 x 18 m: 2 x 2 rooms per face, 6 floors
bpy.ops.object.transform_apply(scale=True)
building.data.materials.append(interior_material(interior_group()))

bpy.ops.mesh.primitive_plane_add(location=(0.0, 0.0, 0.0))
ground = bpy.context.object
ground.scale = (40.0, 40.0, 1.0)

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -10.0, 15.0), rotation=(math.radians(50), 0.0, math.radians(-30)))
bpy.context.object.data.energy = 2.0

bpy.ops.object.camera_add(location=(-3.0, -16.0, 6.0), rotation=(math.radians(82), 0.0, math.radians(-12)))
scene.camera = bpy.context.object

if want_shot:
    shot = base + "_game.png"
    text = bpy.data.texts.new("parallax_auto_screenshot.py")
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
print("PARALLAX_TEST saved", output)
