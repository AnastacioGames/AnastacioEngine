"""Energy shield + hologram demo, Game engine, Shading Nodes.

Run with:  RangeEngine -b --python tools/create_shield_test.py -- demos/escudo.range [--shot]
Nodes are laid out in colored frames, each with a note (Text datablock) explaining that stage.

- "Escudo de Energia": a sphere around a character. Rim glow from Layer Weight (Facing), animated
  horizontal scan lines and a slow sweep band driven by the Time node (logic time in seconds), and a
  drifting Voronoi cell pattern that only shows near the rim. Pure Emission with blend mode Add:
  black = invisible, so no alpha is needed.
- "Holograma": a blue Suzanne with Fresnel rim, dense scan lines scrolling up and a random flicker.
--shot    adds a camera controller that saves <output>_game.png at frame 90 and ends the game.
"""
import bpy
import math
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "escudo.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Escudo World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.03, 0.04, 0.07, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
scene.world = world


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

    def node(self, kind, hide=False, label=None, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        if label:
            n.label = label
        n.hide = hide
        x = self.lanes.get(self.lane_id, self.x0)
        n.location = (x, -self.lane_id * 320)
        self.lanes[self.lane_id] = x + (150 if hide else 220)
        self.nodes.append(n)
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def math(self, op, a, b=0.0, label=None):
        n = self.node("ShaderNodeMath", hide=True, operation=op, label=label)
        for sock, v in ((n.inputs[0], a), (n.inputs[1], b)):
            if isinstance(v, (int, float)):
                sock.default_value = v
            else:
                self.link(v, sock)
        return n.outputs[0]

    def frame(self, label, color, text=None):
        frame(self.nt, label, color, self.nodes, text)


def new_tree(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    m.game_settings.alpha_blend = 'ADD'      # emission adds over the scene, black = invisible
    m.game_settings.use_backface_culling = False
    return m, nt


# ---------------------------------------------------------------- shield

def shield_material():
    m, nt = new_tree("Escudo de Energia")
    g = G(nt)

    # 1. rim
    g.stage()
    lw = g.node("ShaderNodeLayerWeight", label="Borda")
    lw.inputs["Blend"].default_value = 0.35
    rim = g.math('POWER', lw.outputs["Facing"], 4.0, "Afinar borda (expoente)")
    g.frame("1. Brilho na borda", BLUE,
            "Layer Weight Facing = 0 de frente, 1 na silhueta.\n"
            "Expoente maior = borda mais fina (2 a 5).\n"
            "E o efeito fresnel classico de escudo/vidro.")

    # 2. scan lines
    g.stage()
    t = g.node("ShaderNodeTime", label="Tempo (segundos)")
    tc = g.node("ShaderNodeTexCoord")
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(tc.outputs["Object"], sep.inputs["Vector"])
    g.lane(1)
    lines = g.math('MULTIPLY', sep.outputs["Z"], 14.0, "Linhas por metro")
    tl = g.math('MULTIPLY', t.outputs["Time"], 2.5, "Velocidade linhas")
    lines = g.math('SUBTRACT', lines, tl)
    lines = g.math('SINE', lines)
    lines = g.math('MULTIPLY', lines, 0.5)
    lines = g.math('ADD', lines, 0.5)
    lines = g.math('POWER', lines, 6.0, "Espessura linhas")
    g.lane(2)
    band = g.math('MULTIPLY', sep.outputs["Z"], 1.2, "Largura faixa")
    tb = g.math('MULTIPLY', t.outputs["Time"], 1.6, "Velocidade faixa")
    band = g.math('SUBTRACT', band, tb)
    band = g.math('SINE', band)
    band = g.math('MAXIMUM', band, 0.0)
    band = g.math('POWER', band, 12.0, "Nitidez faixa")
    g.frame("2. Linhas de varredura (Time)", GREEN,
            "Time = tempo de jogo em segundos (atualiza todo frame).\n"
            "sin(Z * linhas - tempo * velocidade): linhas sobem.\n"
            "Faixa: mesma ideia, mais larga e com potencia alta.\n"
            "Coordenada Object: as linhas seguem o objeto.")

    # 3. cells
    g.stage()
    cxyz = g.node("ShaderNodeCombineXYZ", label="Deriva")
    g.lane(1)
    g.link(g.math('MULTIPLY', t.outputs["Time"], 0.15, "Velocidade deriva"), cxyz.inputs["Z"])
    vadd = g.node("ShaderNodeVectorMath", operation='ADD')
    g.link(tc.outputs["Object"], vadd.inputs[0])
    g.link(cxyz.outputs["Vector"], vadd.inputs[1])
    g.lane(0)
    vor = g.node("ShaderNodeTexVoronoi", label="Celulas", coloring='INTENSITY')
    vor.inputs["Scale"].default_value = 5.0
    g.link(vadd.outputs["Vector"], vor.inputs["Vector"])
    ramp = g.node("ShaderNodeValToRGB", label="Contorno das celulas")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp.color_ramp.elements[1].position = 0.6
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    g.link(vor.outputs["Fac"], ramp.inputs["Fac"])
    g.frame("3. Celulas (Voronoi)", PURPLE,
            "Voronoi Intensity = distancia ao centro da celula.\n"
            "A rampa deixa so a parte longe do centro (bordas).\n"
            "Scale = tamanho das celulas. A deriva move o padrao.")

    # 4. combine
    g.stage()
    cell = g.math('MULTIPLY', ramp.outputs["Color"], rim, "Celulas so na borda")
    cell = g.math('MULTIPLY', cell, 0.8)
    g.lane(1)
    scan = g.math('ADD', lines, band)
    scan = g.math('MULTIPLY', scan, 0.12, "Forca linhas")
    g.lane(0)
    tot = g.math('ADD', rim, cell)
    tot = g.math('ADD', tot, scan)
    tot = g.math('ADD', tot, 0.03, "Base (vidro)")
    em = g.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.15, 0.7, 1.0, 1.0)
    g.link(tot, em.inputs["Strength"])
    out = g.node("ShaderNodeOutputMaterial")
    g.link(em.outputs["Emission"], out.inputs["Surface"])
    g.frame("4. Cor e soma (blend Add)", ORANGE,
            "Soma borda + celulas + linhas -> Strength da Emission.\n"
            "Material em blend Add (Game Settings): preto some,\n"
            "por isso nao precisa de alpha. Troque a cor aqui.")
    return m


# ---------------------------------------------------------------- hologram

def hologram_material():
    m, nt = new_tree("Holograma")
    g = G(nt)

    g.stage()
    fr = g.node("ShaderNodeFresnel", label="Borda")
    fr.inputs["IOR"].default_value = 1.1
    rim = g.math('MULTIPLY', fr.outputs["Fac"], 1.5, "Forca borda")
    g.frame("1. Borda (Fresnel)", BLUE,
            "Fresnel: brilha na silhueta. IOR menor = borda\n"
            "mais fina (1.05 a 1.5).")

    g.stage()
    t = g.node("ShaderNodeTime", label="Tempo (segundos)")
    tc = g.node("ShaderNodeTexCoord")
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(tc.outputs["Object"], sep.inputs["Vector"])
    g.lane(1)
    s = g.math('MULTIPLY', sep.outputs["Z"], 60.0, "Linhas por metro")
    s = g.math('SUBTRACT', s, g.math('MULTIPLY', t.outputs["Time"], 4.0, "Velocidade"))
    s = g.math('SINE', s)
    s = g.math('MULTIPLY', s, 0.5)
    s = g.math('ADD', s, 0.5)
    s = g.math('POWER', s, 2.0)
    scan = g.math('ADD', s, 0.35, "Minimo entre linhas")
    g.frame("2. Linhas de varredura", GREEN,
            "Linhas finas subindo pelo objeto (coordenada Object).\n"
            "O minimo entre linhas evita que o holograma suma.")

    g.stage()
    f1 = g.math('SINE', g.math('MULTIPLY', t.outputs["Time"], 23.0))
    f2 = g.math('SINE', g.math('MULTIPLY', t.outputs["Time"], 7.3))
    f = g.math('MULTIPLY', f1, f2)
    f = g.math('GREATER_THAN', f, 0.8, "Limiar da piscada")
    flick = g.math('SUBTRACT', 1.0, g.math('MULTIPLY', f, 0.6), "Piscada")
    g.frame("3. Piscada", PURPLE,
            "Duas senoides de frequencias diferentes multiplicadas:\n"
            "quando passam do limiar o brilho cai (falha do sinal).\n"
            "Limiar maior = pisca menos.")

    g.stage()
    tot = g.math('ADD', rim, 0.12, "Corpo")
    tot = g.math('MULTIPLY', tot, scan)
    tot = g.math('MULTIPLY', tot, flick)
    em = g.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.1, 0.45, 1.0, 1.0)
    g.link(tot, em.inputs["Strength"])
    out = g.node("ShaderNodeOutputMaterial")
    g.link(em.outputs["Emission"], out.inputs["Surface"])
    g.frame("4. Cor (blend Add)", ORANGE,
            "(borda + corpo) x linhas x piscada -> Emission.\n"
            "Blend Add: aditivo, sem alpha e sem ordenar.")
    return m


def solid_material(name, color, rough=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    return m


# ---------------------------------------------------------------- scene

shield = shield_material()
holo = hologram_material()
gray = solid_material("Personagem", (0.6, 0.55, 0.5, 1.0))
floor_m = solid_material("Chao", (0.05, 0.05, 0.06, 1.0), 0.8)
metal = solid_material("Pedestal", (0.3, 0.3, 0.32, 1.0), 0.3)

bpy.ops.mesh.primitive_monkey_add(location=(-2.0, 0.0, 1.3))
hero = bpy.context.object
hero.name = "Personagem"
hero.data.materials.append(gray)
bpy.ops.object.shade_smooth()

bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, size=1.0, location=(-2.0, 0.0, 1.75))
sph = bpy.context.object
sph.name = "Escudo"
sph.scale = (1.65, 1.65, 1.65)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()
sph.data.materials.append(shield)
sph.game.physics_type = 'NO_COLLISION'

bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.8, depth=0.3, location=(2.4, 0.0, 0.15))
ped = bpy.context.object
ped.name = "Pedestal"
ped.data.materials.append(metal)

bpy.ops.mesh.primitive_monkey_add(location=(2.4, 0.0, 1.3))
h = bpy.context.object
h.name = "Holograma"
mod = h.modifiers.new("Subsurf", 'SUBSURF')
mod.levels = 1
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.object.shade_smooth()
h.data.materials.append(holo)
h.game.physics_type = 'NO_COLLISION'

bpy.ops.mesh.primitive_plane_add(location=(0.0, 0.0, 0.0))
ground = bpy.context.object
ground.scale = (30.0, 30.0, 1.0)
ground.data.materials.append(floor_m)

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -10.0, 15.0), rotation=(math.radians(50), 0.0, math.radians(-30)))
bpy.context.object.data.energy = 1.2

bpy.ops.object.camera_add(location=(0.0, -9.5, 2.4), rotation=(math.radians(82), 0.0, 0.0))
scene.camera = bpy.context.object

if want_shot:
    shot = base + "_game.png"
    text = bpy.data.texts.new("escudo_auto_screenshot.py")
    text.write(
        "import Range\n"
        "from Range import logic\n"
        "own = logic.getCurrentController().owner\n"
        "own['frame'] = own.get('frame', 0) + 1\n"
        "if own['frame'] == 90:\n"
        "    Range.render.makeScreenshot('%s')\n"
        "if own['frame'] == 96:\n"
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
print("SHIELD_TEST saved", output)
