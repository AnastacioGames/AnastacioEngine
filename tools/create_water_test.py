"""Stylized water demo, Game engine, Shading Nodes.

Run with:  RangeEngine -b --python tools/create_water_test.py -- demos/agua.range [--shot]
Nodes are laid out in colored frames, each with a note (Text datablock) explaining that stage.

- "Agua Estilizada": opaque water plane. Two noise layers scroll in different directions driven by the
  Time node (seconds of game time) and feed a Bump node (animated ripples). A Layer Weight fresnel mixes
  a Diffuse water color with a Glossy that reflects the World (sky). The water color goes from turquoise
  near the shore to deep blue far away (object Y coordinate, the shore is on +Y). Foam lines are thin
  bands of a distorted Wave texture, masked by noise so they break up.
- "Areia e Pedra (espuma)": the engine has no scene-depth input for nodes, so the classic depth-based
  foam is impossible in the water shader. The trick: the shore and the rocks draw the foam themselves,
  in a thin band around the water level (world Z = 0), pulsing with Time.
--shot    adds a camera controller that saves <output>_game.png at frame 60 and ends the game.
"""
import bpy
import math
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "agua.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Agua World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.45, 0.65, 0.95, 1.0)
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


def new_tree(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return m, nt


def node(nt, idname, loc, label=None, hide=False, **inputs):
    n = nt.nodes.new(idname)
    n.location = loc
    if label:
        n.label = label
    n.hide = hide
    for k, v in inputs.items():
        n.inputs[k.replace("_", " ")].default_value = v
    return n


def math_node(nt, op, loc, a=None, b=None, label=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.location = loc
    n.hide = True
    if label:
        n.label = label
    if a is not None:
        n.inputs[0].default_value = a
    if b is not None:
        n.inputs[1].default_value = b
    return n


# ---------------------------------------------------------------- water material

def water_material():
    m, nt = new_tree("Agua Estilizada")
    L = nt.links.new

    # 1. animated coordinates: object coords + Time * speed (two directions)
    coord = node(nt, "ShaderNodeTexCoord", (-1700, 200))
    time = node(nt, "ShaderNodeTime", (-1700, -150), "Tempo (s)")
    spd_a = node(nt, "ShaderNodeCombineXYZ", (-1480, -40), "Velocidade A")
    spd_b = node(nt, "ShaderNodeCombineXYZ", (-1480, -260), "Velocidade B")
    ta_x = math_node(nt, 'MULTIPLY', (-1480, 60), b=0.12, label="t * 0.12")
    ta_y = math_node(nt, 'MULTIPLY', (-1480, 20), b=0.05, label="t * 0.05")
    tb_x = math_node(nt, 'MULTIPLY', (-1480, -170), b=-0.07, label="t * -0.07")
    tb_y = math_node(nt, 'MULTIPLY', (-1480, -210), b=0.10, label="t * 0.10")
    for mn, c, ax in ((ta_x, spd_a, "X"), (ta_y, spd_a, "Y"), (tb_x, spd_b, "X"), (tb_y, spd_b, "Y")):
        L(time.outputs[0], mn.inputs[0])
        L(mn.outputs[0], c.inputs[ax])
    co_a = node(nt, "ShaderNodeVectorMath", (-1260, 120), "Coord A")
    co_b = node(nt, "ShaderNodeVectorMath", (-1260, -120), "Coord B")
    co_a.operation = co_b.operation = 'ADD'
    L(coord.outputs["Object"], co_a.inputs[0]); L(spd_a.outputs[0], co_a.inputs[1])
    L(coord.outputs["Object"], co_b.inputs[0]); L(spd_b.outputs[0], co_b.inputs[1])

    # 2. ripples: two noise layers -> height -> Bump
    noise_a = node(nt, "ShaderNodeTexNoise", (-1000, 200), "Ondas grandes", Scale=0.9, Detail=2.0, Distortion=0.0)
    noise_b = node(nt, "ShaderNodeTexNoise", (-1000, -60), "Ondas pequenas", Scale=3.0, Detail=1.0, Distortion=0.0)
    L(co_a.outputs[0], noise_a.inputs["Vector"])
    L(co_b.outputs[0], noise_b.inputs["Vector"])
    height = node(nt, "ShaderNodeMixRGB", (-780, 80), "Altura (mistura)", Fac=0.4)
    height.blend_type = 'MIX'
    L(noise_a.outputs["Fac"], height.inputs["Color1"])
    L(noise_b.outputs["Fac"], height.inputs["Color2"])
    bump = node(nt, "ShaderNodeBump", (-560, 80), "Relevo das ondas", Strength=0.35, Distance=0.6)
    L(height.outputs["Color"], bump.inputs["Height"])

    # 3. color: shallow near the shore, deep far away; fresnel mix with the sky reflection
    sep = node(nt, "ShaderNodeSeparateXYZ", (-1000, -360))
    L(coord.outputs["Object"], sep.inputs[0])
    depth = node(nt, "ShaderNodeMapRange", (-780, -360), "Distancia da costa") \
        if hasattr(bpy.types, "ShaderNodeMapRange") else None
    if depth is None:  # Y in [-30, 6] -> [0, 1] with plain math
        d1 = math_node(nt, 'ADD', (-780, -340), b=30.0, label="y + 30")
        d2 = math_node(nt, 'DIVIDE', (-780, -380), b=36.0, label="/ 36")
        L(sep.outputs["Y"], d1.inputs[0]); L(d1.outputs[0], d2.inputs[0])
        depth_out = d2.outputs[0]
        depth_nodes = (d1, d2)
    else:
        depth.inputs["From Min"].default_value = -30.0
        depth.inputs["From Max"].default_value = 6.0
        L(sep.outputs["Y"], depth.inputs["Value"])
        depth_out = depth.outputs[0]
        depth_nodes = (depth,)
    ramp = node(nt, "ShaderNodeValToRGB", (-560, -360), "Fundo -> raso")
    ramp.color_ramp.elements[0].color = (0.01, 0.06, 0.16, 1.0)
    ramp.color_ramp.elements[1].position = 0.85
    ramp.color_ramp.elements[1].color = (0.05, 0.42, 0.45, 1.0)
    e = ramp.color_ramp.elements.new(0.55)
    e.color = (0.02, 0.16, 0.30, 1.0)
    L(depth_out, ramp.inputs["Fac"])
    diffuse = node(nt, "ShaderNodeBsdfDiffuse", (-300, -260), "Cor da agua")
    L(ramp.outputs["Color"], diffuse.inputs["Color"])
    L(bump.outputs["Normal"], diffuse.inputs["Normal"])
    glossy = node(nt, "ShaderNodeBsdfGlossy", (-300, -60), "Reflexo do ceu", Roughness=0.08)
    L(bump.outputs["Normal"], glossy.inputs["Normal"])
    lw = node(nt, "ShaderNodeLayerWeight", (-300, 180), "Fresnel", Blend=0.35)
    L(bump.outputs["Normal"], lw.inputs["Normal"])
    mix_w = node(nt, "ShaderNodeMixShader", (-60, 0), "Agua")
    L(lw.outputs["Fresnel"], mix_w.inputs["Fac"])
    L(diffuse.outputs[0], mix_w.inputs[1])
    L(glossy.outputs[0], mix_w.inputs[2])

    # 4. foam lines: thin bands of a distorted wave texture, broken up by noise
    wave = node(nt, "ShaderNodeTexWave", (-1000, -620), "Linhas de espuma",
                Scale=0.2, Distortion=9.0, Detail=2.0, Detail_Scale=0.6)
    wave.wave_type = 'BANDS'
    L(co_a.outputs[0], wave.inputs["Vector"])
    fthr = node(nt, "ShaderNodeValToRGB", (-780, -620), "Espessura (limiar)")
    fthr.color_ramp.elements[0].position = 0.90
    fthr.color_ramp.elements[1].position = 0.97
    L(wave.outputs["Fac"], fthr.inputs["Fac"])
    fmask = node(nt, "ShaderNodeValToRGB", (-780, -860), "Falhas na espuma")
    fmask.color_ramp.elements[0].position = 0.45
    fmask.color_ramp.elements[1].position = 0.65
    L(noise_b.outputs["Fac"], fmask.inputs["Fac"])
    foam = node(nt, "ShaderNodeMixRGB", (-520, -700), "Espuma final", Fac=1.0)
    foam.blend_type = 'MULTIPLY'
    L(fthr.outputs["Color"], foam.inputs["Color1"])
    L(fmask.outputs["Color"], foam.inputs["Color2"])
    foam_col = node(nt, "ShaderNodeBsdfDiffuse", (-300, -520), "Cor da espuma", Color=(0.9, 0.95, 1.0, 1.0))
    mix_f = node(nt, "ShaderNodeMixShader", (160, -620), "Agua + espuma")
    L(foam.outputs["Color"], mix_f.inputs["Fac"])
    L(mix_w.outputs[0], mix_f.inputs[1])
    L(foam_col.outputs[0], mix_f.inputs[2])
    out = node(nt, "ShaderNodeOutputMaterial", (380, -620))
    L(mix_f.outputs[0], out.inputs["Surface"])

    # keep the stages apart: color/reflection to the right, foam below
    for n in (sep,) + depth_nodes + (ramp, diffuse, glossy, lw, mix_w):
        n.location.x += 700
    for n in (wave, fthr, fmask, foam, foam_col, mix_f, out):
        n.location.y -= 500
    frame(nt, "1. Coordenadas animadas", BLUE,
          (coord, time, spd_a, spd_b, ta_x, ta_y, tb_x, tb_y, co_a, co_b),
          "Time = segundos de jogo. Multiplicadores = velocidade\n"
          "de cada camada (m/s). Direcoes diferentes evitam\n"
          "que a agua pareca uma textura deslizando.")
    frame(nt, "2. Ondulacao (normal)", GREEN, (noise_a, noise_b, height, bump),
          "Duas Noise (grande + pequena) viram altura.\n"
          "Bump Strength = forca das ondas (0.2-0.5).\n"
          "Detail alto gera chiado de longe: mantenha 1-2.")
    frame(nt, "3. Cor e reflexo", ORANGE, (sep,) + depth_nodes + (ramp, diffuse, glossy, lw, mix_w),
          "Rampa: cor do fundo (esq) ate a agua rasa (dir),\n"
          "pela distancia da costa (Y do objeto).\n"
          "Fresnel Blend = quanto reflete o ceu de lado.\n"
          "Glossy Roughness baixo = reflexo nitido.")
    frame(nt, "4. Espuma em linhas", PURPLE, (wave, fthr, fmask, foam, foam_col, mix_f, out),
          "Wave distorcida, so o topo das faixas (rampa 0.90-0.97).\n"
          "Aproxime as setas da rampa = linhas mais finas.\n"
          "A segunda rampa recorta falhas usando a Noise B.")
    return m


# ---------------------------------------------------------------- shore / rock material with foam

def shore_material(name, c_dry, c_wet):
    m, nt = new_tree(name)
    L = nt.links.new
    coord = node(nt, "ShaderNodeTexCoord", (-1300, 100))
    sep = node(nt, "ShaderNodeSeparateXYZ", (-1080, 100))
    L(coord.outputs["Object"], sep.inputs[0])
    time = node(nt, "ShaderNodeTime", (-1300, -200), "Tempo (s)")
    swell = math_node(nt, 'MULTIPLY', (-1080, -180), b=1.6, label="t * 1.6")
    sinus = math_node(nt, 'SINE', (-1080, -220), label="seno")
    amp = math_node(nt, 'MULTIPLY', (-1080, -260), b=0.06, label="* 0.06 m")
    L(time.outputs[0], swell.inputs[0]); L(swell.outputs[0], sinus.inputs[0]); L(sinus.outputs[0], amp.inputs[0])
    noise = node(nt, "ShaderNodeTexNoise", (-1080, -380), "Borda irregular", Scale=6.0, Detail=1.0)
    L(coord.outputs["Object"], noise.inputs["Vector"])
    jitter = math_node(nt, 'MULTIPLY', (-860, -380), b=0.12, label="* 0.12")
    L(noise.outputs["Fac"], jitter.inputs[0])
    lvl = math_node(nt, 'SUBTRACT', (-860, 100), label="z - mare")
    L(sep.outputs["Z"], lvl.inputs[0]); L(amp.outputs[0], lvl.inputs[1])
    lvl2 = math_node(nt, 'SUBTRACT', (-860, 60), label="- ruido")
    L(lvl.outputs[0], lvl2.inputs[0]); L(jitter.outputs[0], lvl2.inputs[1])
    band = node(nt, "ShaderNodeValToRGB", (-640, 100), "Faixa de espuma (z)")
    # Fac clamps to 0..1: shift so world z=0 lands at 0.5 (z range -0.5 .. +0.5)
    shift = math_node(nt, 'ADD', (-860, 20), b=0.5, label="+ 0.5")
    L(lvl2.outputs[0], shift.inputs[0]); L(shift.outputs[0], band.inputs["Fac"])
    cr = band.color_ramp
    cr.interpolation = 'LINEAR'
    cr.elements[0].position = 0.40; cr.elements[0].color = (0, 0, 0, 1)
    cr.elements[1].position = 0.64; cr.elements[1].color = (0, 0, 0, 1)
    e = cr.elements.new(0.48); e.color = (1, 1, 1, 1)
    e = cr.elements.new(0.56); e.color = (1, 1, 1, 1)
    wet = node(nt, "ShaderNodeValToRGB", (-640, -160), "Molhado abaixo da agua")
    wet.color_ramp.elements[0].position = 0.45; wet.color_ramp.elements[0].color = (*c_wet, 1)
    wet.color_ramp.elements[1].position = 0.6; wet.color_ramp.elements[1].color = (*c_dry, 1)
    L(shift.outputs[0], wet.inputs["Fac"])
    base_d = node(nt, "ShaderNodeBsdfDiffuse", (-380, -160), "Cor base")
    L(wet.outputs["Color"], base_d.inputs["Color"])
    foam_d = node(nt, "ShaderNodeBsdfDiffuse", (-380, -320), "Espuma", Color=(0.92, 0.96, 1.0, 1.0))
    mix = node(nt, "ShaderNodeMixShader", (-140, 0))
    L(band.outputs["Color"], mix.inputs["Fac"]); L(base_d.outputs[0], mix.inputs[1]); L(foam_d.outputs[0], mix.inputs[2])
    out = node(nt, "ShaderNodeOutputMaterial", (80, 0))
    L(mix.outputs[0], out.inputs["Surface"])
    frame(nt, "1. Nivel da agua + mare", BLUE, (coord, sep, time, swell, sinus, amp, noise, jitter, lvl, lvl2, shift),
          "Sem profundidade de cena nos nos: a espuma em volta\n"
          "das pedras e desenhada pela propria pedra, perto de z=0.\n"
          "0.06 = altura da mare, 1.6 = velocidade. Ruido = borda.\n"
          "Aplique transformacoes: usa Object = mundo.")
    frame(nt, "2. Espuma e areia molhada", ORANGE, (band, wet, base_d, foam_d, mix, out),
          "Rampa da faixa: 0.5 = nivel da agua. Afaste as setas\n"
          "brancas para engrossar a espuma.\n"
          "Abaixo da agua a cor escurece (molhado).")
    return m


# ---------------------------------------------------------------- scene

def apply_all(ob):
    bpy.context.scene.objects.active = ob
    ob.select = True
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def rock(name, loc, mat, size, scale):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, size=size, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    tx = bpy.data.textures.new(name + "_ruido", 'CLOUDS')
    tx.noise_scale = 0.5
    mod = ob.modifiers.new("Displace", 'DISPLACE')
    mod.texture = tx
    mod.strength = 0.5
    mod.texture_coords = 'GLOBAL'
    bpy.ops.object.modifier_apply(modifier=mod.name)
    apply_all(ob)
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat)
    return ob


water = water_material()
sand = shore_material("Areia (espuma)", (0.78, 0.68, 0.48), (0.42, 0.35, 0.24))
stone = shore_material("Pedra (espuma)", (0.42, 0.40, 0.37), (0.20, 0.19, 0.18))

bpy.ops.mesh.primitive_plane_add(location=(0.0, -12.0, 0.0))
sea = bpy.context.object
sea.name = "Agua"
sea.scale = (40.0, 20.0, 1.0)
apply_all(sea)
sea.data.materials.append(water)

# shore: grid rising toward +Y, crossing z=0 around y=4
bpy.ops.mesh.primitive_grid_add(x_subdivisions=80, y_subdivisions=40, radius=1.0, location=(0.0, 10.0, 0.0))
shore = bpy.context.object
shore.name = "Costa"
shore.scale = (40.0, 8.0, 1.0)
apply_all(shore)
stx = bpy.data.textures.new("costa_ruido", 'CLOUDS')
stx.noise_scale = 2.5
for v in shore.data.vertices:
    v.co.z = (v.co.y - 4.0) * 0.18
mod = shore.modifiers.new("Displace", 'DISPLACE')
mod.texture = stx
mod.strength = 0.6
mod.direction = 'Z'
mod.mid_level = 0.5
mod.texture_coords = 'GLOBAL'
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.object.shade_smooth()
shore.data.materials.append(sand)

rock("Pedra1", (-3.0, -2.0, 0.1), stone, 1.2, (1.4, 1.0, 0.8))
rock("Pedra2", (2.6, -5.5, 0.0), stone, 1.6, (1.2, 1.1, 0.9))
rock("Pedra3", (5.5, -1.0, -0.2), stone, 0.9, (1.0, 1.3, 0.8))
rock("Pedra4", (-7.0, -8.0, 0.2), stone, 2.0, (1.0, 0.9, 1.2))

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -10.0, 15.0), rotation=(math.radians(55), 0.0, math.radians(-25)))
bpy.context.object.data.energy = 1.6

bpy.ops.object.camera_add(location=(0.0, -20.0, 4.5), rotation=(math.radians(78), 0.0, 0.0))
scene.camera = bpy.context.object

if want_shot:
    shot = base + "_game.png"
    text = bpy.data.texts.new("agua_auto_screenshot.py")
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
print("WATER_TEST saved", output)
