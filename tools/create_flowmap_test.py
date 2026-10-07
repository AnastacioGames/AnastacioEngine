"""Flow map lava river test scene, Game engine, Shading Nodes.

Run with:  RangeEngine -b --python tools/create_flowmap_test.py -- demos/lava.range [--shot]
Nodes are laid out in colored frames, each with a note (Text datablock) explaining that stage.

- "Flow Map" node group: moves a texture along a direction field stored in an image (the flow map).
  R/G = flow direction (0.5 = no motion), B = local speed. The UV is pushed along the flow by a phase that
  grows with time and wraps; two copies run half a cycle apart, fract(t) and fract(t + 0.5), and a triangle
  wave fades to the copy that is in the middle of its cycle, so the texture never stretches without limit
  and the reset of each copy is invisible.
- "Lava": the group fed with a generated flow map that follows a curved river and a generated lava texture
  (dark crust plates, bright cracks). Brightness drives an emission ramp (dark red -> orange -> yellow).
- Scene: a terrain with a curved trench, the lava plane below it, orange lamps along the river for the glow.
--shot    adds a camera controller that saves <output>_game.png at frame 30 and ends the game.
"""
import bpy
import math
import os
import random
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "lava.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Lava World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.10, 0.07, 0.08, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5
world.horizon_color = (0.10, 0.07, 0.08)
scene.world = world

SIZE = 30.0  # terrain and lava plane cover SIZE x SIZE meters, the flow map covers the same area


def river_x(y):
    """Center line of the river (x as a function of y, meters)."""
    return 4.5 * math.sin(y * 0.22) + 1.5 * math.sin(y * 0.51 + 1.0)


def river_dx(y):
    return 4.5 * 0.22 * math.cos(y * 0.22) + 1.5 * 0.51 * math.cos(y * 0.51 + 1.0)


def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- generated images

def flow_image(size=128):
    """Direction field along the river: R,G = direction * 0.5 + 0.5, B = speed (fast middle, slow banks)."""
    px = [0.0] * (size * size * 4)
    for j in range(size):
        y = ((j + 0.5) / size - 0.5) * SIZE
        cx, dx = river_x(y), river_dx(y)
        inv = 1.0 / math.sqrt(dx * dx + 1.0)
        tx, ty = dx * inv, inv  # tangent, river flows toward +y
        for i in range(size):
            x = ((i + 0.5) / size - 0.5) * SIZE
            d = abs(x - cx)
            speed = 1.0 - 0.7 * smooth(0.5, 3.0, d)
            # slight eddy toward the outer bank so the flow is not perfectly parallel
            side = (x - cx) / 3.0
            ex, ey = tx - 0.25 * side * ty, ty + 0.25 * side * tx
            n = 1.0 / math.sqrt(ex * ex + ey * ey)
            k = (j * size + i) * 4
            px[k:k + 4] = (ex * n * 0.5 + 0.5, ey * n * 0.5 + 0.5, speed, 1.0)
    img = bpy.data.images.new("lava_flowmap", size, size)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels = px
    img.pack(as_png=True)
    return img


def lava_image(size=256, cells=7, seed=5):
    """Tileable lava: dark crust plates (Voronoi cells) separated by bright hot cracks."""
    rnd = random.Random(seed)
    pts = [[(rnd.random(), rnd.random()) for _ in range(cells)] for _ in range(cells)]
    heat_cell = [[rnd.random() for _ in range(cells)] for _ in range(cells)]
    px = [0.0] * (size * size * 4)
    for y in range(size):
        fy = y / size * cells
        cy = int(fy)
        for x in range(size):
            fx = x / size * cells
            cx = int(fx)
            d1 = d2 = 9.0
            hc = 0.0
            for oy in (-1, 0, 1):
                for ox in (-1, 0, 1):
                    gx, gy = cx + ox, cy + oy
                    p = pts[gy % cells][gx % cells]
                    ddx, ddy = gx + p[0] - fx, gy + p[1] - fy
                    d = ddx * ddx + ddy * ddy
                    if d < d1:
                        d2, d1, hc = d1, d, heat_cell[gy % cells][gx % cells]
                    elif d < d2:
                        d2 = d
            edge = math.sqrt(d2) - math.sqrt(d1)  # 0 on the crack
            crack = 1.0 - smooth(0.0, 0.18, edge)
            # crust: dark, some plates glow a little from inside
            crust = 0.04 + 0.10 * hc * (1.0 - smooth(0.0, 0.5, edge))
            h = max(crack, crust)
            k = (y * size + x) * 4
            px[k:k + 4] = (h, h * h * 0.9, h * h * h * 0.5, 1.0)
    img = bpy.data.images.new("lava_cor", size, size)
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
PURPLE = (0.32, 0.22, 0.40)


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

    def frame(self, label, color, text=None):
        frame(self.nt, label, color, self.nodes, text)


# ---------------------------------------------------------------- flow map group

def flow_group(lava_img):
    grp = bpy.data.node_groups.new("Flow Map", 'ShaderNodeTree')
    gi = grp.nodes.new("NodeGroupInput")
    go = grp.nodes.new("NodeGroupOutput")
    grp.inputs.new("NodeSocketVector", "UV")
    grp.inputs.new("NodeSocketColor", "Flow").default_value = (0.5, 1.0, 1.0, 1.0)
    grp.inputs.new("NodeSocketFloat", "Speed").default_value = 0.25
    grp.inputs.new("NodeSocketFloat", "Strength").default_value = 0.4
    grp.inputs.new("NodeSocketFloat", "Tiling").default_value = 6.0
    grp.outputs.new("NodeSocketColor", "Color")
    grp.outputs.new("NodeSocketFloat", "Heat")
    gi.location = (-320, -240)
    g = G(grp)

    # 1. decode the flow map: direction -1..1 times local speed (B) times Strength
    g.stage()
    sep = g.node("ShaderNodeSeparateRGB"); sep.label = "Flow map"
    g.link(gi.outputs["Flow"], sep.inputs[0])
    g.lane(1)
    sep_uv = g.node("ShaderNodeSeparateXYZ"); sep_uv.label = "UV"
    g.link(gi.outputs["UV"], sep_uv.inputs[0])
    g.stage()
    amount = g.math('MULTIPLY', sep.outputs["B"], gi.outputs["Strength"], "forca x velocidade")
    fx = g.math('MULTIPLY', g.math('SUBTRACT', sep.outputs["R"], 0.5), g.math('MULTIPLY', amount, 2.0), "fluxo X")
    g.lane(1)
    fy = g.math('MULTIPLY', g.math('SUBTRACT', sep.outputs["G"], 0.5), g.math('MULTIPLY', amount, 2.0), "fluxo Y")
    g.lane(2)
    ux = g.math('MULTIPLY', sep_uv.outputs[0], gi.outputs["Tiling"], "UV X x repeticoes")
    uy = g.math('MULTIPLY', sep_uv.outputs[1], gi.outputs["Tiling"], "UV Y x repeticoes")
    g.frame("1. Direcao do fluxo", BLUE,
            "Flow map: R/G = direcao (0.5 = parado), B = velocidade.\n"
            "Strength = quanto a textura anda por ciclo (em ladrilhos).\n"
            "Tiling = repeticoes da textura no UV.")

    # 2. two phases half a cycle apart
    g.stage()
    timen = g.node("ShaderNodeTime"); timen.label = "Tempo (s)"
    t = g.math('MULTIPLY', timen.outputs[0], gi.outputs["Speed"], "tempo x Speed")
    g.lane(1)
    p1 = g.math('FRACT', t, label="fase A")
    g.lane(2)
    p2 = g.math('FRACT', g.math('ADD', t, 0.5), label="fase B")
    g.lane(3)
    # triangle wave: 1 when phase A wraps (A is jumping), 0 when A is mid-cycle (B is jumping)
    w = g.math('ABSOLUTE', g.math('SUBTRACT', g.math('MULTIPLY', p1, 2.0), 1.0), label="peso de B")
    g.frame("2. Duas fases", PURPLE,
            "Speed = ciclos por segundo. fase A = fract(t),\n"
            "fase B = fract(t + 0.5). Cada fase volta a 0 e a textura\n"
            "pularia: o peso esconde a fase que esta pulando.")

    # 3. sample the texture twice, each with its own displaced UV
    g.stage()
    samples = []
    for k, (ph, off) in enumerate(((p1, 0.0), (p2, 0.5))):
        g.lane(2 * k)
        sx = g.math('SUBTRACT', ux, g.math('MULTIPLY', fx, ph), "UV X - fluxo")
        sy = g.math('SUBTRACT', uy, g.math('MULTIPLY', fy, ph), "UV Y - fluxo")
        # B is offset half a tile so the two copies do not line up
        sx = g.math('ADD', sx, off, "desloca copia")
        comb = g.node("ShaderNodeCombineXYZ"); comb.label = "UV " + "AB"[k]
        g.link(sx, comb.inputs[0]); g.link(sy, comb.inputs[1])
        tex = g.node("ShaderNodeTexImage"); tex.image = lava_img; tex.label = "Lava " + "AB"[k]
        g.link(comb.outputs[0], tex.inputs["Vector"])
        samples.append(tex.outputs["Color"])
    g.frame("3. Duas leituras da textura", GREEN,
            "UV - fluxo x fase: a textura escorre na direcao do fluxo.\n"
            "A segunda copia fica meio ladrilho deslocada\n"
            "para as duas nao coincidirem.")

    # 4. blend
    g.stage()
    g.lane(1)
    mix = g.node("ShaderNodeMixRGB"); mix.label = "Mistura A / B"
    g.link(w, mix.inputs[0]); g.link(samples[0], mix.inputs[1]); g.link(samples[1], mix.inputs[2])
    bw = g.node("ShaderNodeRGBToBW"); bw.label = "Calor"
    g.link(mix.outputs[0], bw.inputs[0])
    g.frame("4. Mistura", ORANGE,
            "Mistura pelo peso triangular: nunca se ve o pulo.\n"
            "Calor = brilho da textura (rachaduras = quente).")
    g.link(mix.outputs[0], go.inputs["Color"])
    g.link(bw.outputs[0], go.inputs["Heat"])
    go.location = (max(g.lanes.values()) + 180, -240)
    return grp


def lava_material(grp, flow_img):
    m = bpy.data.materials.new("Lava")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new
    L = nt.links.new

    coord = N("ShaderNodeTexCoord"); coord.location = (-1000, 0)
    flow = N("ShaderNodeTexImage"); flow.image = flow_img; flow.color_space = 'NONE'
    flow.label = "Flow map (direcao do rio)"; flow.location = (-780, -120)
    L(coord.outputs["UV"], flow.inputs["Vector"])
    gn = N("ShaderNodeGroup"); gn.node_tree = grp; gn.location = (-500, 0)
    L(coord.outputs["UV"], gn.inputs["UV"]); L(flow.outputs["Color"], gn.inputs["Flow"])

    ramp = N("ShaderNodeValToRGB"); ramp.location = (-240, -60); ramp.label = "Cor do calor"
    el = ramp.color_ramp.elements
    el[0].position = 0.05; el[0].color = (0.0, 0.0, 0.0, 1.0)
    el[1].position = 0.9; el[1].color = (1.0, 0.85, 0.35, 1.0)
    e = el.new(0.3); e.color = (0.5, 0.03, 0.0, 1.0)
    e = el.new(0.6); e.color = (1.0, 0.3, 0.02, 1.0)
    L(gn.outputs["Heat"], ramp.inputs["Fac"])
    emit = N("ShaderNodeEmission"); emit.location = (60, -60)
    emit.inputs["Strength"].default_value = 4.0
    L(ramp.outputs["Color"], emit.inputs["Color"])

    crust = N("ShaderNodeBsdfPrincipled"); crust.location = (440, -200); crust.label = "Crosta"
    crust.inputs["Base Color"].default_value = (0.05, 0.04, 0.04, 1.0)
    crust.inputs["Roughness"].default_value = 0.8
    add = N("ShaderNodeAddShader"); add.location = (740, -60)
    L(crust.outputs[0], add.inputs[0]); L(emit.outputs[0], add.inputs[1])
    out = N("ShaderNodeOutputMaterial"); out.location = (940, -60)
    L(add.outputs[0], out.inputs["Surface"])

    frame(nt, "1. Fluxo do rio", BLUE, (coord, flow, gn),
          "Grupo 'Flow Map' (Tab para ver por dentro).\n"
          "Speed = rapidez, Strength = quanto estica por ciclo\n"
          "(passe de 0.6 e aparece borrado), Tiling = tamanho.\n"
          "Flow map em Non-Color, mesmo UV do plano.")
    frame(nt, "2. Brilho da lava", ORANGE, (ramp, emit),
          "Calor -> rampa: preto, vermelho, laranja, amarelo.\n"
          "Strength da Emission = intensidade do brilho.")
    frame(nt, "3. Crosta + emissao", GREEN, (crust, add, out))
    return m


# ---------------------------------------------------------------- scene

LAVA_Z = -0.6

flow_img = flow_image()
lava_img = lava_image()

bpy.ops.mesh.primitive_plane_add(calc_uvs=True, location=(0.0, 0.0, LAVA_Z))
lava = bpy.context.object
lava.name = "Lava"
lava.scale = (SIZE / 2, SIZE / 2, 1.0)
bpy.ops.object.transform_apply(scale=True)
lava.data.materials.append(lava_material(flow_group(lava_img), flow_img))

# terrain: grid with a trench carved along the river
bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=120, radius=SIZE / 2, location=(0.0, 0.0, 0.0))
terrain = bpy.context.object
terrain.name = "Terreno"
rnd = random.Random(11)
bumps = [(rnd.uniform(-15, 15), rnd.uniform(-15, 15), rnd.uniform(1.5, 4), rnd.uniform(0.3, 1.2)) for _ in range(40)]
for v in terrain.data.vertices:
    x, y = v.co.x, v.co.y
    d = abs(x - river_x(y))
    h = 0.4 + 1.6 * smooth(2.2, 6.0, d)
    for bx, by, r, a in bumps:
        q = ((x - bx) ** 2 + (y - by) ** 2) / (r * r)
        if q < 1.0:
            h += a * (1.0 - q) ** 2 * smooth(3.0, 6.0, d)
    v.co.z = h - 1.6 * (1.0 - smooth(1.6, 3.2, d))  # river bed well below the lava
bpy.ops.object.shade_smooth()
rockm = bpy.data.materials.new("Rocha Vulcanica")
rockm.use_nodes = True
rb = rockm.node_tree.nodes["Diffuse BSDF"] if "Diffuse BSDF" in rockm.node_tree.nodes else None
if rb:
    rb.inputs["Color"].default_value = (0.06, 0.05, 0.05, 1.0)
terrain.data.materials.append(rockm)

# orange lamps over the river fake the light thrown by the lava
for yy in (-10.0, -4.0, 2.0, 8.0):
    bpy.ops.object.lamp_add(type='POINT', location=(river_x(yy), yy, 1.2))
    lamp = bpy.context.object.data
    lamp.color = (1.0, 0.4, 0.1)
    lamp.energy = 3.0
    lamp.distance = 8.0

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -10.0, 15.0), rotation=(math.radians(60), 0.0, math.radians(-40)))
bpy.context.object.data.energy = 0.4
bpy.context.object.data.color = (0.6, 0.65, 0.9)

bpy.ops.object.camera_add(location=(1.0, -21.0, 12.0), rotation=(math.radians(58), 0.0, math.radians(-4)))
scene.camera = bpy.context.object

if want_shot:
    shot = base + "_game.png"
    text = bpy.data.texts.new("lava_auto_screenshot.py")
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
print("FLOWMAP_TEST saved", output)
