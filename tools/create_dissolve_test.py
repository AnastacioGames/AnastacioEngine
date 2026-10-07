"""Dissolve (burn away with a glowing edge) demo, Game engine, Shading Nodes.

Run with:  RangeEngine -b --python tools/create_dissolve_test.py -- demos/dissolve.range [--shot]
Nodes are laid out in colored frames, each with a note (Text datablock) explaining that stage.

- "Dissolver (Object Data)": a noise texture in object coordinates is compared with a dissolve amount.
  Pixels below the threshold are cut (material alpha blend = Clip, Transparent BSDF), a thin band just
  above it glows (Emission with an orange->yellow ramp). The amount is the red channel of the object
  color (KX_GameObject.color), read by the "Object Data" node, so each object has its own value and a
  Python logic brick can animate it. Suzanne and the cube loop at different speeds, the sphere is a
  static half-dissolved object (object color set in the editor).
- "Dissolver (Time)": same recipe, the amount comes from the "Time" node (seconds since game start)
  through 0.5 - 0.5*cos(time*speed): no logic bricks at all, but every object with it is in sync.
--shot    adds a camera controller that saves <output>_game.png at frame 40 and ends the game.
"""
import bpy
import math
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "dissolve.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Dissolve World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.06, 0.10, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
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

EDGE_WIDTH = 0.025  # glowing band width, in noise units


def dissolve_material(use_time):
    m = bpy.data.materials.new("Dissolver (Time)" if use_time else "Dissolver (Object Data)")
    m.game_settings.alpha_blend = 'CLIP'
    m.game_settings.use_backface_culling = False  # see the inside through the holes
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new
    L = nt.links.new

    def math_node(op, a, b, loc, label=None):
        n = N("ShaderNodeMath")
        n.operation = op
        n.location = loc
        n.hide = True
        if label:
            n.label = label
        for i, v in enumerate((a, b)):
            if isinstance(v, float):
                n.inputs[i].default_value = v
            else:
                L(v, n.inputs[i])
        return n

    # 1. amount source
    if use_time:
        src = N("ShaderNodeTime"); src.location = (-1500, 300); src.label = "Tempo (s)"
        spd = math_node('MULTIPLY', src.outputs[0], 0.9, (-1280, 300), "x velocidade")
        phase = math_node('ADD', spd.outputs[0], 0.6, (-1280, 255), "+ fase")
        cos = math_node('COSINE', phase.outputs[0], 0.0, (-1280, 210), "cos")
        half = math_node('MULTIPLY', cos.outputs[0], -0.5, (-1280, 165), "x -0.5")
        amount = math_node('ADD', half.outputs[0], 0.5, (-1280, 120), "+ 0.5 = quantidade")
        stage1 = (src, spd, phase, cos, half, amount)
        stage1_text = ("Quantidade 0..1 vinda do no Time (segundos de jogo):\n"
                       "0.5 - 0.5*cos(tempo*vel + fase). Sem logic bricks,\n"
                       "mas todos os objetos com este material ficam iguais.\n"
                       "Troque 0.9 para mudar a velocidade.")
    else:
        src = N("ShaderNodeObjectData"); src.location = (-1500, 300); src.label = "Cor do objeto"
        sep = N("ShaderNodeSeparateRGB"); sep.location = (-1280, 300); sep.label = "R = quantidade"
        L(src.outputs[0], sep.inputs[0])
        amount = sep
        stage1 = (src, sep)
        stage1_text = ("Quantidade 0..1 = canal R da cor do objeto\n"
                       "(Object > Object Color). Em Python:\n"
                       "own.color = [q, 0, 0, 1]  (0 = inteiro, 1 = sumiu)\n"
                       "Cada objeto tem seu valor, mesmo dividindo o material.")
    amount_out = amount.outputs[0]

    # 2. noise
    coord = N("ShaderNodeTexCoord"); coord.location = (-1500, -250)
    noise = N("ShaderNodeTexNoise"); noise.location = (-1280, -250); noise.label = "Ruido da queima"
    noise.inputs["Scale"].default_value = 2.5
    noise.inputs["Detail"].default_value = 3.0
    L(coord.outputs["Object"], noise.inputs["Vector"])

    # 3. threshold, cut and edge band. Noise is about 0.2..0.8: amount 0..1 -> threshold 0.12..0.88
    x = -960
    thr_m = math_node('MULTIPLY', amount_out, 0.76, (x, 200), "x 0.76")
    thr = math_node('ADD', thr_m.outputs[0], 0.12, (x, 155), "+ 0.12 = limiar")
    diff = math_node('SUBTRACT', noise.outputs["Fac"], thr.outputs[0], (x, 110), "ruido - limiar")
    keep = math_node('GREATER_THAN', diff.outputs[0], 0.0, (x, 65), "fica (> 0)")
    band = math_node('LESS_THAN', diff.outputs[0], EDGE_WIDTH, (x, 20), "na borda (< largura)")
    on = math_node('GREATER_THAN', amount_out, 0.001, (x, -25), "queimando?")
    edge = math_node('MULTIPLY', band.outputs[0], on.outputs[0], (x, -70), "borda")
    grad = math_node('DIVIDE', diff.outputs[0], EDGE_WIDTH, (x, -115), "posicao na borda")
    ramp = N("ShaderNodeValToRGB"); ramp.location = (-740, -60); ramp.label = "Cor da brasa"
    ramp.color_ramp.elements[0].color = (1.0, 0.95, 0.4, 1.0)   # at the cut: yellow
    ramp.color_ramp.elements[1].color = (1.0, 0.18, 0.0, 1.0)   # outer side: orange/red
    L(grad.outputs[0], ramp.inputs["Fac"])
    stage3 = (thr_m, thr, diff, keep, band, on, edge, grad, ramp)

    # 4. shading
    bsdf = N("ShaderNodeBsdfPrincipled"); bsdf.location = (-380, 300)
    bsdf.inputs["Base Color"].default_value = (0.55, 0.55, 0.6, 1.0) if use_time else (0.6, 0.35, 0.2, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.4
    emit = N("ShaderNodeEmission"); emit.location = (-380, -260); emit.label = "Brilho da borda"
    emit.inputs["Strength"].default_value = 2.5
    L(ramp.outputs["Color"], emit.inputs["Color"])
    mix_edge = N("ShaderNodeMixShader"); mix_edge.location = (-120, 100); mix_edge.label = "Superficie / borda"
    L(edge.outputs[0], mix_edge.inputs["Fac"])
    L(bsdf.outputs[0], mix_edge.inputs[1])
    L(emit.outputs[0], mix_edge.inputs[2])
    transp = N("ShaderNodeBsdfTransparent"); transp.location = (-120, -100)
    mix_cut = N("ShaderNodeMixShader"); mix_cut.location = (100, 60); mix_cut.label = "Corte (alpha)"
    L(keep.outputs[0], mix_cut.inputs["Fac"])
    L(transp.outputs[0], mix_cut.inputs[1])
    L(mix_edge.outputs[0], mix_cut.inputs[2])
    out = N("ShaderNodeOutputMaterial"); out.location = (300, 60)
    L(mix_cut.outputs[0], out.inputs["Surface"])

    frame(nt, "1. Quantidade de dissolucao", BLUE, stage1, stage1_text)
    frame(nt, "2. Ruido", GREEN, (coord, noise),
          "Noise em coordenadas Object: o padrao gruda no objeto.\n"
          "Scale = tamanho das manchas, Detail = borda mais\n"
          "recortada. Aplique a escala (Ctrl+A).")
    frame(nt, "3. Limiar, corte e borda", PURPLE, stage3,
          "ruido < limiar some; logo acima dele brilha a borda.\n"
          "Largura da borda: 0.025 nos dois nos (< e /).\n"
          "0.76 e 0.12 levam 0..1 para a faixa util do ruido.\n"
          "Ramp: esquerda = junto ao corte, direita = fora.")
    frame(nt, "4. Sombreamento", ORANGE, (bsdf, emit, mix_edge, transp, mix_cut, out),
          "Material > Game Settings > Alpha Blend = Clip:\n"
          "alpha 0 do Transparent e descartado (sem ordenar).\n"
          "Strength da Emission = forca do brilho (use Bloom).")
    return m


# ---------------------------------------------------------------- scene

mat_obj = dissolve_material(False)
mat_time = dissolve_material(True)

ANIM = (
    "from Range import logic\n"
    "import math\n"
    "own = logic.getCurrentController().owner\n"
    "own['t'] = own.get('t', own['fase']) + own['velocidade'] / logic.getLogicTicRate()\n"
    "q = 0.5 - 0.5 * math.cos(own['t'])\n"
    "own.color = [q, 0.0, 0.0, 1.0]\n"
)
anim_text = bpy.data.texts.new("dissolver_anim.py")
anim_text.write(ANIM)


def animate(ob, speed, phase):
    scene.objects.active = ob
    for name, val in (("velocidade", speed), ("fase", phase)):
        bpy.ops.object.game_property_new(type='FLOAT', name=name)
        ob.game.properties[name].value = val
    bpy.ops.logic.sensor_add(type='ALWAYS', object=ob.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=ob.name)
    ob.game.sensors[-1].use_pulse_true_level = True
    ob.game.controllers[-1].text = anim_text
    ob.game.sensors[-1].link(ob.game.controllers[-1])


def place(ob, mat, amount=0.0):
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat)
    ob.color = (amount, 0.0, 0.0, 1.0)


bpy.ops.mesh.primitive_monkey_add(location=(-3.3, 0.0, 1.2), rotation=(0.0, 0.0, math.radians(-20)))
monkey = bpy.context.object
monkey.name = "Suzanne"
mod = monkey.modifiers.new("Sub", 'SUBSURF')
mod.levels = 2
bpy.ops.object.modifier_apply(modifier=mod.name)
place(monkey, mat_obj)
animate(monkey, 1.2, 0.9)

bpy.ops.mesh.primitive_cube_add(location=(-1.1, 0.0, 1.0), rotation=(0.0, 0.0, math.radians(30)))
cube = bpy.context.object
cube.name = "Cubo"
cube.scale = (0.9, 0.9, 0.9)
place(cube, mat_obj)
animate(cube, 0.6, 1.4)

bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, size=1.0, location=(1.1, 0.0, 1.0))
sphere = bpy.context.object
sphere.name = "EsferaMeio"
place(sphere, mat_obj, 0.5)  # static, half dissolved

bpy.ops.mesh.primitive_torus_add(location=(3.3, 0.0, 1.1), rotation=(math.radians(70), 0.0, 0.0),
                                 major_radius=0.85, minor_radius=0.3)
torus = bpy.context.object
torus.name = "ToroTempo"
place(torus, mat_time)

bpy.ops.mesh.primitive_plane_add(location=(0.0, 0.0, 0.0))
ground = bpy.context.object
ground.scale = (40.0, 40.0, 1.0)
gmat = bpy.data.materials.new("Chao")
gmat.use_nodes = True
gmat.node_tree.nodes["Diffuse BSDF"].inputs["Color"].default_value = (0.12, 0.12, 0.13, 1.0)
ground.data.materials.append(gmat)

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -10.0, 15.0), rotation=(math.radians(50), 0.0, math.radians(-30)))
bpy.context.object.data.energy = 1.2

bpy.ops.object.camera_add(location=(0.0, -10.5, 3.2), rotation=(math.radians(80), 0.0, 0.0))
scene.camera = bpy.context.object

if want_shot:
    shot = base + "_game.png"
    text = bpy.data.texts.new("dissolve_auto_screenshot.py")
    text.write(
        "import Range\n"
        "from Range import logic\n"
        "own = logic.getCurrentController().owner\n"
        "own['frame'] = own.get('frame', 0) + 1\n"
        "if own['frame'] == 40:\n"
        "    Range.render.makeScreenshot('%s')\n"
        "if own['frame'] == 46:\n"
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
print("DISSOLVE_TEST saved", output)
