"""Tesla Piano material recipes, Game engine, Shading Nodes.

Run with:  RangeEngine -b --python tools/create_tesla_materials_test.py -- demos/tesla_materiais.range [--shot]
The five node materials of build/bin/demos/TeslaPiano/TeslaPiano_Cinematic.range rebuilt with the same values,
laid out in colored frames, each with a note (Text datablock) explaining that stage.

- "Aco Escovado" / "Base Grafite": Principled metal; a fine Noise drives both a subtle Bump and the Roughness
  (through a ColorRamp), so the highlight breaks up instead of being a perfect mirror.
- "Cobre Bobinado": Wave Texture on the height (Z) only -> horizontal rings, used as color (copper / dark grooves)
  and as Bump, so a plain cylinder looks like a wound coil.
- "Concreto Molhado": two Noises in object space, a fine one for color + bump, a huge one for the puddles that only
  changes Roughness (wet = 0.07 mirror-like, dry = 0.65).
- "Terminal Emissivo": Emission only, glows with Bloom.
--shot    adds a camera controller that saves <output>_game.png at frame 30 and ends the game.
"""
import bpy
import math
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "tesla_materiais.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Laboratorio")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.10, 0.13, 0.20, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
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
        tb = bpy.data.texts.new("nota - " + nt.id_data.name + " - " + label)
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
PURPLE = (0.32, 0.22, 0.40)
ORANGE = (0.42, 0.28, 0.16)


def new_material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return m, nt


def ramp(nt, loc, label, a, b):
    """ColorRamp with two stops: a = (position, grey or rgb), b likewise."""
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.location = loc
    r.label = label
    for e, (pos, col) in zip(r.color_ramp.elements, (a, b)):
        e.position = pos
        e.color = (col, col, col, 1.0) if isinstance(col, float) else col + (1.0,)
    return r


def principled(nt, loc, label, **values):
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.location = loc
    p.label = label
    for k, v in values.items():
        p.inputs[k].default_value = v
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (loc[0] + 300, loc[1])
    out.label = "Saida PBR"
    nt.links.new(p.outputs["BSDF"], out.inputs["Surface"])
    return p, out


SHADING_NOTE = ("Principled: Metallic alto = a cor vira a cor do reflexo.\n"
                "Normal vem do Bump, Roughness da rampa: cada pixel\n"
                "tem um brilho um pouco diferente, como metal real.")


def brushed_metal(name, color, metallic, rough_dark, rough_light):
    """Aco Escovado / Base Grafite: same recipe, different color and roughness range."""
    m, nt = new_material(name)
    N, L = nt.nodes.new, nt.links.new
    coord = N("ShaderNodeTexCoord"); coord.location = (-900, 0); coord.label = "Coordenadas locais"
    noise = N("ShaderNodeTexNoise"); noise.location = (-680, 0); noise.label = "Microtextura"
    noise.inputs["Scale"].default_value = 85.0
    noise.inputs["Detail"].default_value = 2.0
    L(coord.outputs["Generated"], noise.inputs["Vector"])

    bump = N("ShaderNodeBump"); bump.location = (-420, 120); bump.label = "Relevo sutil"
    bump.inputs["Strength"].default_value = 0.18
    bump.inputs["Distance"].default_value = 0.015
    rr = ramp(nt, (-420, -140), "Variacao de rugosidade", (0.15, rough_dark), (0.85, rough_light))
    L(noise.outputs["Fac"], bump.inputs["Height"])
    L(noise.outputs["Fac"], rr.inputs["Fac"])

    p, out = principled(nt, (-60, 0), name, **{"Base Color": color, "Metallic": metallic})
    L(bump.outputs["Normal"], p.inputs["Normal"])
    L(rr.outputs["Color"], p.inputs["Roughness"])

    frame(nt, "1. Microtextura", BLUE, (coord, noise),
          "Noise bem fino (Scale 85) nas coordenadas Generated\n"
          "(0..1 na caixa do objeto): sujeira/riscos minusculos.\n"
          "Um so ruido alimenta relevo e rugosidade, entao os\n"
          "dois combinam. Dica: um Mapping com Scale (1,1,0.03)\n"
          "antes do Noise estica o ruido e vira escovado de verdade.")
    frame(nt, "2. Relevo + rugosidade", GREEN, (bump, rr),
          "Bump Strength 0.18 = relevo quase invisivel, so quebra\n"
          "o reflexo. A rampa troca o ruido 0..1 por rugosidade\n"
          "%.2f..%.2f: manchas mais polidas e mais foscas." % (rough_dark, rough_light))
    frame(nt, "3. Sombreamento", ORANGE, (p, out), SHADING_NOTE)
    return m


def copper_coil():
    m, nt = new_material("Cobre Bobinado")
    N, L = nt.nodes.new, nt.links.new
    coord = N("ShaderNodeTexCoord"); coord.location = (-1200, 0); coord.label = "Coordenadas locais"
    sep = N("ShaderNodeSeparateXYZ"); sep.location = (-980, 0); sep.label = "Altura da bobina"
    comb = N("ShaderNodeCombineXYZ"); comb.location = (-800, 0); comb.label = "Espiras horizontais"
    L(coord.outputs["Generated"], sep.inputs["Vector"])
    L(sep.outputs["Z"], comb.inputs["X"])

    wave = N("ShaderNodeTexWave"); wave.location = (-600, 0); wave.label = "Espiras de cobre"
    wave.wave_type = 'BANDS'
    wave.wave_profile = 'SIN'
    wave.inputs["Scale"].default_value = 65.0
    L(comb.outputs["Vector"], wave.inputs["Vector"])

    cr = ramp(nt, (-380, -60), "Cobre / sulcos escuros", (0.18, (0.045, 0.012, 0.005)), (0.48, (0.55, 0.205, 0.065)))
    bump = N("ShaderNodeBump"); bump.location = (-380, 200); bump.label = "Relevo das espiras"
    bump.inputs["Strength"].default_value = 0.18
    bump.inputs["Distance"].default_value = 0.025
    L(wave.outputs["Fac"], cr.inputs["Fac"])
    L(wave.outputs["Fac"], bump.inputs["Height"])

    p, out = principled(nt, (-60, 0), "Cobre_Bobinado", Metallic=0.95, Roughness=0.27)
    L(cr.outputs["Color"], p.inputs["Base Color"])
    L(bump.outputs["Normal"], p.inputs["Normal"])

    frame(nt, "1. So a altura (Z)", BLUE, (coord, sep, comb),
          "Wave Bands soma X+Y+Z. Para ter aneis retos em volta\n"
          "do cilindro, separamos o Z e o colocamos sozinho no X:\n"
          "a onda passa a depender so da altura.")
    frame(nt, "2. Espiras", PURPLE, (wave,),
          "Wave Bands / Sin: listras suaves 0..1.\n"
          "Scale 65 = numero de voltas do fio. Aumente para\n"
          "fio mais fino.")
    frame(nt, "3. Cor + relevo", GREEN, (cr, bump),
          "A mesma onda vira cor (vale escuro, topo cobre) e\n"
          "relevo: o fio parece redondo sem ter geometria.\n"
          "Rampa curta (0.18..0.48) = sulcos finos e escuros.")
    frame(nt, "4. Sombreamento", ORANGE, (p, out), SHADING_NOTE)
    return m


def wet_concrete():
    m, nt = new_material("Concreto Molhado")
    N, L = nt.nodes.new, nt.links.new
    coord = N("ShaderNodeTexCoord"); coord.location = (-1000, 0); coord.label = "Coordenadas locais"

    fine = N("ShaderNodeTexNoise"); fine.location = (-760, 220); fine.label = "Microtextura"
    fine.inputs["Scale"].default_value = 3.5
    fine.inputs["Detail"].default_value = 2.0
    L(coord.outputs["Object"], fine.inputs["Vector"])
    cr = ramp(nt, (-520, 320), "Concreto escuro", (0.2, (0.012, 0.018, 0.024)), (0.8, (0.09, 0.105, 0.12)))
    bump = N("ShaderNodeBump"); bump.location = (-520, 60); bump.label = "Relevo sutil"
    bump.inputs["Strength"].default_value = 0.18
    bump.inputs["Distance"].default_value = 0.035
    L(fine.outputs["Fac"], cr.inputs["Fac"])
    L(fine.outputs["Fac"], bump.inputs["Height"])

    big = N("ShaderNodeTexNoise"); big.location = (-760, -260); big.label = "Distribuicao das pocas"
    big.inputs["Scale"].default_value = 0.35
    big.inputs["Detail"].default_value = 2.0
    L(coord.outputs["Object"], big.inputs["Vector"])
    wet = ramp(nt, (-520, -260), "Molhado / seco", (0.43, 0.07), (0.6, 0.65))
    L(big.outputs["Fac"], wet.inputs["Fac"])

    p, out = principled(nt, (-160, 0), "Concreto_Molhado", Metallic=0.05)
    L(cr.outputs["Color"], p.inputs["Base Color"])
    L(bump.outputs["Normal"], p.inputs["Normal"])
    L(wet.outputs["Color"], p.inputs["Roughness"])

    frame(nt, "1. Coordenadas do objeto", BLUE, (coord,),
          "Object = metros: o tamanho do ruido nao muda com a\n"
          "escala do chao (Generated esticaria).")
    frame(nt, "2. Concreto", GREEN, (fine, cr, bump),
          "Noise medio (Scale 3.5) da manchas de cor quase preta\n"
          "e um relevo leve. A rampa limita a cor a cinzas escuros:\n"
          "concreto molhado e sempre mais escuro que seco.")
    frame(nt, "3. Pocas", PURPLE, (big, wet),
          "Noise enorme (Scale 0.35 = manchas de ~3 m) decide onde\n"
          "tem agua. So muda a Roughness: 0.07 = espelho (poca),\n"
          "0.65 = fosco (seco). Rampa estreita (0.43..0.60) =\n"
          "borda da poca bem definida. Mova os stops para mais/\n"
          "menos agua.")
    frame(nt, "4. Sombreamento", ORANGE, (p, out), SHADING_NOTE)
    return m


def emissive_terminal():
    m, nt = new_material("Terminal Emissivo")
    em = nt.nodes.new("ShaderNodeEmission"); em.location = (-200, 0); em.label = "Luz azul do terminal"
    em.inputs["Color"].default_value = (0.22, 0.48, 1.0, 1.0)
    em.inputs["Strength"].default_value = 2.0
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (100, 0); out.label = "Saida"
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    frame(nt, "Brilho proprio", PURPLE, (em, out),
          "Emission ignora luzes e sombras: a cor sai pura.\n"
          "Strength > 1 passa do branco e o Bloom (Propriedades\n"
          "da cena) faz o halo. Bom para LEDs, telas e raios.")
    return m


# ---------------------------------------------------------------- scene

steel = brushed_metal("Aco Escovado", (0.48, 0.54, 0.62, 1.0), 0.95, 0.149, 0.322)
graphite = brushed_metal("Base Grafite", (0.025, 0.032, 0.043, 1.0), 0.65, 0.234, 0.504)
copper = copper_coil()
concrete = wet_concrete()
glow = emissive_terminal()


def obj(op, mat, name, loc, **kw):
    op(location=loc, **kw)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return ob


bpy.ops.mesh.primitive_plane_add(location=(0.0, 0.0, 0.0))
floor = bpy.context.object
floor.name = "Chao_Concreto"
floor.scale = (14.0, 14.0, 1.0)
bpy.ops.object.transform_apply(scale=True)
floor.data.materials.append(concrete)

# Tesla coil: graphite base, copper coil, steel ring, glowing terminal
obj(bpy.ops.mesh.primitive_cylinder_add, graphite, "Base", (0.0, 0.0, 0.25), vertices=48, radius=0.9, depth=0.5)
obj(bpy.ops.mesh.primitive_cylinder_add, copper, "Bobina", (0.0, 0.0, 1.6), vertices=64, radius=0.45, depth=2.2)
obj(bpy.ops.mesh.primitive_torus_add, steel, "Anel", (0.0, 0.0, 3.0), major_radius=0.7, minor_radius=0.18,
    major_segments=64, minor_segments=24)
obj(bpy.ops.mesh.primitive_uv_sphere_add, glow, "Terminal", (0.0, 0.0, 3.0), segments=32, ring_count=16, size=0.3)

# samples on the side
obj(bpy.ops.mesh.primitive_uv_sphere_add, steel, "Esfera_Aco", (-2.6, 0.0, 0.8), segments=64, ring_count=32, size=0.8)
obj(bpy.ops.mesh.primitive_cube_add, graphite, "Bloco_Grafite", (2.6, 0.0, 0.6), radius=0.6)
obj(bpy.ops.mesh.primitive_cylinder_add, copper, "Bobina_Pequena", (2.6, 1.8, 0.7), vertices=48, radius=0.3,
    depth=1.4)

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -8.0, 12.0), rotation=(math.radians(55), 0.0, math.radians(-35)))
bpy.context.object.data.energy = 1.5
bpy.ops.object.lamp_add(type='POINT', location=(0.0, 0.0, 3.0))
lamp = bpy.context.object.data
lamp.color = (0.3, 0.55, 1.0)
lamp.energy = 2.0
lamp.distance = 6.0

bpy.ops.object.camera_add(location=(0.0, -10.5, 4.2), rotation=(math.radians(78), 0.0, 0.0))
scene.camera = bpy.context.object

if want_shot:
    shot = base + "_game.png"
    text = bpy.data.texts.new("tesla_auto_screenshot.py")
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
print("TESLA_MATERIALS saved", output)
