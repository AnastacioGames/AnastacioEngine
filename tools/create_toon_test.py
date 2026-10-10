"""Toon / cel shading demo with outline, Game engine, Shading Nodes.

Run with:  RangeEngine -b --python tools/create_toon_test.py -- demos/toon.range [--shot]
Nodes are laid out in colored frames, each with a note (Text datablock) explaining that stage.

Shading = sum of shaders, all with hard edges (Smooth 0):
- Emission with base color x blue tint: the shadow band, everywhere (World is black: every BSDF node
  adds the World horizon color in GLSL, the Glossy Toon included, which would grey everything).
- Toon BSDF (Diffuse, Size ~0.55): lit band on top of it.
- Toon BSDF (Diffuse, Size ~0.22), brighter tint: third band near the light.
- Toon BSDF (Glossy, Size ~0.06): the hard specular dot.
- Rim light: Layer Weight (Facing) -> Color Ramp CONSTANT -> Emission, only on the silhouette.
The Lamp Data node is old-shading only (no GLSL in node materials), so the bands come from Toon BSDF.
Outline: inverted hull. A Solidify modifier (flip normals, the shell uses material slot 2) creates a thin
shell around the mesh; its material is dark and Backface Culling hides the shell's front side, so only the
line around the silhouette shows. Works with any number of objects and lamps.
--shot    adds a camera controller that saves <output>_game.png at frame 30 and ends the game.
"""
import bpy
import math
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "toon.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Toon World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.75, 1.0, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.18
world.horizon_color = (0.0, 0.0, 0.0)  # GLSL ambient of every BSDF node: black, the shadow color is an Emission
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


def clear(m):
    m.use_nodes = True
    m.game_settings.use_backface_culling = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return nt


def toon_material(name, color, rim=0.5):
    m = bpy.data.materials.new(name)
    nt = clear(m)
    N = nt.nodes.new
    L = nt.links.new

    # stage 1: colors (columns at x = -1500 / -1260)
    rgb = N("ShaderNodeRGB"); rgb.location = (-1500, 0); rgb.label = "Cor base"
    rgb.outputs[0].default_value = color + (1.0,)
    hi = N("ShaderNodeMixRGB"); hi.location = (-1260, 0); hi.label = "Cor da faixa clara"
    hi.blend_type = 'MULTIPLY'; hi.inputs["Fac"].default_value = 1.0
    hi.inputs["Color2"].default_value = (0.25, 0.24, 0.20, 1.0)
    L(rgb.outputs[0], hi.inputs["Color1"])
    sh = N("ShaderNodeMixRGB"); sh.location = (-1260, -240); sh.label = "Cor da sombra"
    sh.blend_type = 'MULTIPLY'; sh.inputs["Fac"].default_value = 1.0
    sh.inputs["Color2"].default_value = (0.30, 0.30, 0.48, 1.0)
    L(rgb.outputs[0], sh.inputs["Color1"])

    # stage 2: diffuse bands (x = -900 / -660)
    t1 = N("ShaderNodeBsdfToon"); t1.location = (-900, 120); t1.label = "Luz x sombra"
    t1.component = 'DIFFUSE'; t1.inputs["Size"].default_value = 0.55; t1.inputs["Smooth"].default_value = 0.0
    L(rgb.outputs[0], t1.inputs["Color"])
    t2 = N("ShaderNodeBsdfToon"); t2.location = (-900, -120); t2.label = "Faixa clara"
    t2.component = 'DIFFUSE'; t2.inputs["Size"].default_value = 0.22; t2.inputs["Smooth"].default_value = 0.0
    L(hi.outputs[0], t2.inputs["Color"])
    shade = N("ShaderNodeEmission"); shade.location = (-900, -340); shade.label = "Sombra (sempre)"
    L(sh.outputs[0], shade.inputs["Color"])
    add0 = N("ShaderNodeAddShader"); add0.location = (-660, 120)
    L(t1.outputs[0], add0.inputs[0]); L(t2.outputs[0], add0.inputs[1])
    add1 = N("ShaderNodeAddShader"); add1.location = (-660, -140)
    L(add0.outputs[0], add1.inputs[0]); L(shade.outputs[0], add1.inputs[1])

    # stage 3: specular dot (y = -560)
    spec = N("ShaderNodeBsdfToon"); spec.location = (-900, -860); spec.label = "Brilho (ponto)"
    spec.component = 'GLOSSY'; spec.inputs["Size"].default_value = 0.06; spec.inputs["Smooth"].default_value = 0.0
    spec.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    add2 = N("ShaderNodeAddShader"); add2.location = (-660, -860)
    L(add1.outputs[0], add2.inputs[0]); L(spec.outputs[0], add2.inputs[1])

    # stage 4: rim + output (y = -1000)
    lw = N("ShaderNodeLayerWeight"); lw.location = (-1500, -1300); lw.inputs["Blend"].default_value = 0.5
    ramp = N("ShaderNodeValToRGB"); ramp.location = (-1260, -1300); ramp.label = "Largura da borda"
    ramp.color_ramp.interpolation = 'CONSTANT'
    ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp.color_ramp.elements[1].position = 0.72
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    L(lw.outputs["Facing"], ramp.inputs["Fac"])
    rimc = N("ShaderNodeMixRGB"); rimc.location = (-960, -1300); rimc.label = "Cor da borda"
    rimc.blend_type = 'MULTIPLY'; rimc.inputs["Fac"].default_value = 1.0
    rimc.inputs["Color2"].default_value = (0.9, 0.95, 1.0, 1.0)
    L(ramp.outputs["Color"], rimc.inputs["Color1"])
    emi = N("ShaderNodeEmission"); emi.location = (-740, -1300); emi.inputs["Strength"].default_value = rim
    L(rimc.outputs[0], emi.inputs["Color"])
    add3 = N("ShaderNodeAddShader"); add3.location = (-520, -1300)
    L(add2.outputs[0], add3.inputs[0]); L(emi.outputs[0], add3.inputs[1])
    out = N("ShaderNodeOutputMaterial"); out.location = (-320, -1300)
    L(add3.outputs[0], out.inputs["Surface"])

    frame(nt, "1. Cores", BLUE, (rgb, hi, sh),
          "Cor base = cor da faixa iluminada.\n"
          "Cor da sombra = base x tom azulado (estilo anime).\n"
          "World fica preto: cada BSDF soma a cor dele.")
    frame(nt, "2. Faixas de luz (Toon Diffuse)", GREEN, (t1, t2, shade, add0, add1),
          "Size = tamanho da area iluminada (0..1).\n"
          "Smooth 0 = corte seco; 0.02 tira o serrilhado.\n"
          "A 2a faixa (Size menor) soma uma area mais clara.\n"
          "A Emission da sombra e somada em toda a superficie.")
    frame(nt, "3. Brilho especular", ORANGE, (spec, add2),
          "Toon Glossy com Size pequeno = ponto duro.\n"
          "Aumente Size para um brilho maior.")
    frame(nt, "4. Luz de contorno (rim) e saida", PURPLE, (lw, ramp, rimc, emi, add3, out),
          "Layer Weight Facing cresce na silhueta. Color Ramp\n"
          "CONSTANT deixa a borda dura: mova o 2o ponto para\n"
          "afinar/engrossar. Strength da Emission = intensidade.")
    return m


def outline_material():
    m = bpy.data.materials.new("Contorno (casco invertido)")
    nt = clear(m)
    emi = nt.nodes.new("ShaderNodeEmission"); emi.location = (-200, 0); emi.label = "Cor do contorno"
    emi.inputs["Color"].default_value = (0.02, 0.015, 0.03, 1.0)
    emi.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (60, 0)
    nt.links.new(emi.outputs[0], out.inputs["Surface"])
    frame(nt, "1. Contorno (casco invertido)", ORANGE, (emi, out),
          "Material do casco do modificador Solidify (normais\n"
          "invertidas, slot 2). Backface Culling LIGADO esconde\n"
          "a frente do casco: so sobra a linha da silhueta.\n"
          "Espessura = Thickness do Solidify (em metros).")
    return m


OUTLINE = outline_material()


def toonify(ob, mat, thickness=0.03):
    """Toon material in slot 1, outline shell (Solidify, flipped, slot 2)."""
    ob.data.materials.append(mat)
    ob.data.materials.append(OUTLINE)
    mod = ob.modifiers.new("Contorno", 'SOLIDIFY')
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.use_even_offset = True
    mod.material_offset = 1
    return ob


def add(prim, name, loc, **kw):
    getattr(bpy.ops.mesh, prim)(location=loc, **kw)
    ob = bpy.context.object
    ob.name = name
    return ob


def squash(ob, scale, rot=(0.0, 0.0, 0.0)):
    ob.scale = scale
    ob.rotation_euler = rot
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    bpy.ops.object.shade_smooth()


skin = toon_material("Toon Pele", (1.0, 0.78, 0.62))
hair = toon_material("Toon Cabelo", (0.95, 0.35, 0.45))
shirt = toon_material("Toon Roupa", (0.25, 0.45, 0.95))
pants = toon_material("Toon Calca", (0.22, 0.22, 0.36))
mon = toon_material("Toon Macaco", (1.0, 0.72, 0.15))
ball = toon_material("Toon Esfera", (0.35, 0.85, 0.5))
grnd = toon_material("Toon Chao", (0.35, 0.62, 0.25), rim=0.0)

m = add("primitive_monkey_add", "Suzanne", (-2.8, 0.0, 1.1), rotation=(0.0, 0.0, math.radians(-25)))
sub = m.modifiers.new("Sub", 'SUBSURF')
sub.levels = 2
bpy.ops.object.modifier_apply(modifier=sub.name)
bpy.ops.object.shade_smooth()
toonify(m, mon)

s = add("primitive_uv_sphere_add", "Esfera", (2.8, 0.0, 1.0), segments=48, ring_count=24)
bpy.ops.object.shade_smooth()
toonify(s, ball)

# character-like figure: legs, body, arms, head, hair
for x in (-0.22, 0.22):
    leg = add("primitive_cylinder_add", "Perna", (x, 0.5, 0.45), radius=0.16, depth=0.9, vertices=24)
    bpy.ops.object.shade_smooth()
    toonify(leg, pants, 0.02)
body = add("primitive_uv_sphere_add", "Corpo", (0.0, 0.5, 1.25), segments=32, ring_count=16)
squash(body, (0.48, 0.36, 0.55))
toonify(body, shirt)
for x in (-0.58, 0.58):
    arm = add("primitive_uv_sphere_add", "Braco", (x, 0.5, 1.2), segments=24, ring_count=12)
    squash(arm, (0.13, 0.13, 0.42), (0.0, math.copysign(0.35, x), 0.0))
    toonify(arm, skin, 0.02)
head = add("primitive_uv_sphere_add", "Cabeca", (0.0, 0.5, 2.15), segments=32, ring_count=16, size=0.42)
bpy.ops.object.shade_smooth()
toonify(head, skin)
h = add("primitive_uv_sphere_add", "Cabelo", (0.0, 0.6, 2.3), segments=32, ring_count=16, size=0.46)
squash(h, (1.0, 1.0, 0.8))
toonify(h, hair, 0.025)

g = add("primitive_plane_add", "Chao", (0.0, 0.0, 0.0))
g.scale = (40.0, 40.0, 1.0)
g.data.materials.append(grnd)

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -10.0, 15.0),
                        rotation=(math.radians(38), 0.0, math.radians(-35)))
bpy.context.object.data.energy = 1.0

bpy.ops.object.camera_add(location=(0.0, -8.5, 2.4), rotation=(math.radians(84), 0.0, 0.0))
scene.camera = bpy.context.object

if want_shot:
    shot = base + "_game.png"
    text = bpy.data.texts.new("toon_auto_screenshot.py")
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
print("TOON_TEST saved", output)
