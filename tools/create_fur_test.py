"""Shell fur demo: two Suzannes covered in dense fluffy fur, real-time in the game engine.

Run with:  RangeEngine -b --python tools/create_fur_test.py -- demos/pelos.range [--shot]

How it works (classic "shell fur")
- Each furry object is ONE mesh holding CAMADAS copies (shells) of the same surface, all at the same
  place in the mesh data. The material vertex shader (Text "pelos_vertex.glsl", material.script_vert,
  `void vertex()`) pushes shell k out along the normal by k/(CAMADAS-1) * COMPRIMENTO, bends it down
  in WORLD space (gravity, grows with layer^2, so it follows a rotating object) and adds a gentle wind.
- Layer index: shell k gets its UVs shifted by +2k in U. The vertex code reads UV (the codegen exposes
  `vec2 UV` when a node uses the UV output) and recovers k = floor((U + 0.5) / 2); the fragment nodes do
  the same with Math nodes. Textures repeat, and every tiling factor is an integer, so the shift is
  invisible. (Vertex colours were avoided: COLOR is raw sRGB in the vertex shader but linearised in the
  fragment, so the two stages would disagree on the layer.)
- Strands: a generated, tileable 256x256 image "fios": R = a cone per strand (height of the strand at the
  centre, falling to 0 at its radius), G = random value per strand. A pixel of shell h is kept when
  R > h, so higher shells keep a smaller disk -> strands taper to a point; strands are pulled toward
  clump centres (slightly clumped look). Alpha Blend = Clip -> no sorting, and shadows work.
- Colour: checker (UV) or a generated calico image, darkened at the roots (fake AO by layer), lighter tips.
--shot    overview screenshot, then close-up of the static Suzanne, prints the average FPS (~10 s run), ends.
"""
import bpy
import math
import os
import sys

import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "pelos.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

SKY = (0.55, 0.60, 0.68)
world = bpy.data.worlds.new("Pelos World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = SKY + (1.0,)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
world.horizon_color = SKY
scene.world = world

CAMADAS = 40            # shells (16..48). Must match #define CAMADAS (filled in below)
DENSIDADE = 16          # repeats of the strand image across the UV space (integer!)
STRANDS = 40            # strands per image side (40 x 40 per tile)
RES = 256
SHELL_GAP = 20.0        # shells are stored SHELL_GAP apart in X (see the docstring); SEPARA in GLSL

# ---------------------------------------------------------------- vertex shader

FUR_VS = """// Pelos (shell fur): cada casca do pelo e uma copia da malha empurrada pela normal.
// VERTEX/NORMAL = espaco do objeto, TIME = segundos, MODEL_MATRIX = objeto -> mundo.
// A camada vem da posicao: a casca k foi gravada na malha com X deslocado de +SEPARA*k
// (o vertex shader descobre k e tira o deslocamento). A UV tambem tem U += 2k (usada nos nos).
// Ajuste aqui (recompila ao rodar o jogo):
#define CAMADAS     %d        // numero de cascas na malha (igual CAMADAS no script Python)
#define COMPRIMENTO 0.085     // comprimento do pelo (m)
#define GRAVIDADE   0.08      // quanto a ponta cai para baixo no MUNDO (m na ponta)
#define VENTO       0.025     // balanco da ponta pelo vento (m)
#define VENTO_FREQ  1.8       // velocidade do balanco
#define VENTO_DIR   vec3(1.0, 0.4, 0.0)  // direcao do vento no mundo
#define MIN_FORA    0.35      // a gravidade nunca enfia a ponta na pele (fracao minima para fora)
#define SEPARA      %.1f      // deslocamento em X entre cascas na malha (igual SHELL_GAP no script)

void vertex()
{
	float camada = floor(VERTEX.x / SEPARA + 0.5);
	VERTEX.x -= camada * SEPARA;                     // volta a casca para cima da pele
	float h = camada / float(CAMADAS - 1);          // 0 = pele, 1 = ponta
	vec3 n = normalize(NORMAL);

	// Mundo -> objeto (so rotacao; escala uniforme e aplicada de novo pelo normalize)
	mat3 paraObjeto = transpose(mat3(MODEL_MATRIX));
	vec3 baixo = normalize(paraObjeto * vec3(0.0, 0.0, -1.0));

	// Vento: onda lenta + tremida, fase muda pelo ponto do pelo (nao balanca tudo junto)
	float fase = dot(VERTEX, vec3(3.1, 2.3, 1.7));
	float onda = sin(TIME * VENTO_FREQ + fase) + 0.35 * sin(TIME * VENTO_FREQ * 3.7 + fase * 2.0);
	vec3 vento = paraObjeto * normalize(VENTO_DIR) * (VENTO * onda);

	// Pelo reto pela normal + curva (gravidade e vento crescem com h^2: raiz firme, ponta mole)
	vec3 d = n * (COMPRIMENTO * h) + (baixo * GRAVIDADE + vento) * (h * h);
	float fora = dot(d, n);
	d += n * max(0.0, MIN_FORA * COMPRIMENTO * h - fora);
	VERTEX += d;
}
""" % (CAMADAS, SHELL_GAP)


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


# ---------------------------------------------------------------- generated images

def strand_image():
    """Tileable strand map. R = cone (strand height at the centre -> 0 at the radius), G = random."""
    rnd = np.random.default_rng(3)
    cell = 1.0 / STRANDS
    gy, gx = np.meshgrid(np.arange(STRANDS), np.arange(STRANDS), indexing="ij")
    pts = (np.stack([gx, gy], -1).reshape(-1, 2) + 0.15 + 0.7 * rnd.random((STRANDS * STRANDS, 2))) * cell
    # clumps: pull each strand toward the nearest clump centre (wrapped)
    C = 9
    cpts = (np.stack(np.meshgrid(np.arange(C), np.arange(C), indexing="ij"), -1).reshape(-1, 2)
            + 0.2 + 0.6 * rnd.random((C * C, 2))) / C
    cheight = 0.8 + 0.2 * rnd.random(C * C)
    dd = pts[:, None, :] - cpts[None, :, :]
    dd -= np.round(dd)
    near = np.argmin((dd ** 2).sum(-1), 1)
    pts = (pts - dd[np.arange(len(pts)), near] * 0.35) % 1.0
    hgt = (0.55 + 0.45 * rnd.random(len(pts)) ** 0.6) * cheight[near]
    rv = rnd.random(len(pts))

    R = np.zeros((RES, RES), np.float32)
    G = np.zeros((RES, RES), np.float32)
    rad = 0.48 * cell * RES                      # strand radius in pixels
    k = int(math.ceil(rad)) + 1
    off = np.arange(-k, k + 1)
    for (px, py), h, r in zip(pts * RES, hgt, rv):
        ix, iy = int(px), int(py)
        xs = ix + off
        ys = iy + off
        ddx = xs + 0.5 - px
        ddy = ys + 0.5 - py
        d = np.sqrt(ddx[None, :] ** 2 + ddy[:, None] ** 2) / rad
        cone = h * np.clip(1.0 - d, 0.0, 1.0)
        yi, xi = np.ix_(ys % RES, xs % RES)
        cur = R[yi, xi]
        better = cone > cur
        R[yi, xi] = np.where(better, cone, cur)
        G[yi, xi] = np.where(better, r, G[yi, xi])
    img = bpy.data.images.new("fios", RES, RES, alpha=False)
    img.colorspace_settings.name = 'Non-Color'    # before writing pixels: changing it reloads the buffer
    px = np.zeros((RES, RES, 4), np.float32)
    px[..., 0] = R
    px[..., 1] = G
    px[..., 3] = 1.0
    img.pixels = px.ravel().tolist()
    img.pack(as_png=True)
    return img


def calico_image():
    """Coat pattern for the image variant: cream base with orange and black patches (tileable)."""
    n = 256
    y, x = np.meshgrid(np.linspace(0, 2 * np.pi, n, endpoint=False),
                       np.linspace(0, 2 * np.pi, n, endpoint=False), indexing="ij")
    rnd = np.random.default_rng(11)

    def field(octaves):
        f = np.zeros((n, n))
        for i in range(octaves):
            a, b = rnd.integers(1, 4 + 2 * i, 2)
            f += np.sin(a * x + rnd.random() * 6.3) * np.cos(b * y + rnd.random() * 6.3) / (1 + i)
        return f
    f1, f2 = field(5), field(5)
    col = np.empty((n, n, 4), np.float32)
    col[...] = (0.85, 0.80, 0.70, 1.0)
    col[f1 > 0.45] = (0.75, 0.33, 0.07, 1.0)
    col[f2 > 0.6] = (0.03, 0.025, 0.02, 1.0)
    img = bpy.data.images.new("pelagem", n, n, alpha=False)
    img.pixels = col.ravel().tolist()
    img.pack(as_png=True)
    return img


# ---------------------------------------------------------------- material

def fur_material(name, fios, pelagem=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.game_settings.alpha_blend = 'CLIP'
    m.game_settings.use_backface_culling = False     # strands are seen from both sides
    vs = bpy.data.texts.get("pelos_vertex.glsl")
    if vs is None:
        vs = bpy.data.texts.new("pelos_vertex.glsl")
        vs.write(FUR_VS)
    m.script_vert = vs
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new
    L = nt.links.new

    def math_node(op, a, b, loc, label=None, hide=True):
        n = N("ShaderNodeMath")
        n.operation = op
        n.location = loc
        n.hide = hide
        if label:
            n.label = label
        for i, v in enumerate((a, b)):
            if isinstance(v, (float, int)):
                n.inputs[i].default_value = float(v)
            else:
                L(v, n.inputs[i])
        return n

    # 1. layer from the UV shift
    coord = N("ShaderNodeTexCoord"); coord.location = (-1700, 200)
    usep = N("ShaderNodeSeparateXYZ"); usep.location = (-1500, 330); usep.label = "U da casca"
    L(coord.outputs["UV"], usep.inputs["Vector"])
    a1 = math_node('ADD', usep.outputs["X"], 0.5, (-1300, 360), "+ 0.5")
    a2 = math_node('MULTIPLY', a1.outputs[0], 0.5, (-1300, 320), "/ 2")
    a3 = math_node('FLOOR', a2.outputs[0], 0.0, (-1300, 280), "floor = camada k")
    lay = math_node('DIVIDE', a3.outputs[0], CAMADAS - 1, (-1300, 240), "/ (CAMADAS-1) = h")
    stage1 = [coord, usep, a1, a2, a3, lay]
    h = lay.outputs[0]

    # 2. strands
    mapn = N("ShaderNodeMapping"); mapn.location = (-1500, 0); mapn.label = "Densidade (inteiro!)"
    mapn.inputs["Scale"].default_value = (DENSIDADE, DENSIDADE, 1.0)
    L(coord.outputs["UV"], mapn.inputs["Vector"])
    ftex = N("ShaderNodeTexImage"); ftex.image = fios; ftex.location = (-1100, 0); ftex.label = "Fios (R altura, G variacao)"
    ftex.interpolation = 'Linear'
    L(mapn.outputs["Vector"], ftex.inputs["Vector"])
    fsep = N("ShaderNodeSeparateRGB"); fsep.location = (-820, 0); fsep.label = "Fio"
    L(ftex.outputs["Color"], fsep.inputs["Image"])
    # grazing angles: raise the threshold of outer shells so the stacked slices do not show
    lw = N("ShaderNodeLayerWeight"); lw.location = (-1100, 260); lw.label = "Rasante (Facing)"
    lw.inputs["Blend"].default_value = 0.5
    g1 = math_node('POWER', lw.outputs["Facing"], 2.0, (-820, 260), "facing^2")
    g2 = math_node('MULTIPLY', g1.outputs[0], 1.6, (-820, 220), "x 1.6 forca rasante")
    g3 = math_node('ADD', g2.outputs[0], 1.0, (-820, 180), "+ 1")
    thr = math_node('MULTIPLY', g3.outputs[0], h, (-820, 140), "limiar = h x rasante")
    keep = math_node('GREATER_THAN', fsep.outputs["R"], thr.outputs[0], (-620, 60), "fio > limiar (afina)")
    skin = math_node('LESS_THAN', h, 0.001, (-620, 20), "pele (camada 0)")
    alive = math_node('MAXIMUM', keep.outputs[0], skin.outputs[0], (-620, -20), "fica?")
    stage2 = [mapn, ftex, fsep, lw, g1, g2, g3, thr, keep, skin, alive]

    # 3. colour
    if pelagem is None:
        pat = N("ShaderNodeTexChecker"); pat.location = (-1100, -420); pat.label = "Xadrez (escala inteira)"
        pat.inputs["Color1"].default_value = (0.85, 0.85, 0.82, 1.0)
        pat.inputs["Color2"].default_value = (0.02, 0.02, 0.02, 1.0)
        pat.inputs["Scale"].default_value = 6.0
        L(coord.outputs["UV"], pat.inputs["Vector"])
    else:
        pat = N("ShaderNodeTexImage"); pat.image = pelagem; pat.location = (-1100, -420); pat.label = "Pelagem (imagem)"
        L(coord.outputs["UV"], pat.inputs["Vector"])
    ao = N("ShaderNodeValToRGB"); ao.location = (-820, -260); ao.label = "Raiz escura (AO falso)"
    ao.color_ramp.elements[0].color = (0.06, 0.06, 0.06, 1.0)
    ao.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    ao.color_ramp.elements[1].position = 0.75
    L(h, ao.inputs["Fac"])
    var = math_node('MULTIPLY', fsep.outputs["G"], 0.35, (-820, -520), "x 0.35")
    var2 = math_node('ADD', var.outputs[0], 0.8, (-820, -560), "+ 0.8 = variacao do fio")
    tip = math_node('POWER', h, 3.0, (-820, -600), "h^3 = ponta")
    tip2 = math_node('MULTIPLY', tip.outputs[0], 0.15, (-820, -640), "x 0.15 clareia")
    mul_ao = N("ShaderNodeMixRGB"); mul_ao.blend_type = 'MULTIPLY'; mul_ao.location = (-560, -300); mul_ao.label = "Cor x AO"
    mul_ao.inputs["Fac"].default_value = 1.0
    L(pat.outputs["Color"], mul_ao.inputs["Color1"])
    L(ao.outputs["Color"], mul_ao.inputs["Color2"])
    mul_v = N("ShaderNodeMixRGB"); mul_v.blend_type = 'MULTIPLY'; mul_v.location = (-360, -300); mul_v.label = "x variacao"
    mul_v.inputs["Fac"].default_value = 1.0
    L(mul_ao.outputs["Color"], mul_v.inputs["Color1"])
    L(var2.outputs[0], mul_v.inputs["Color2"])
    lite = N("ShaderNodeMixRGB"); lite.location = (-160, -300); lite.label = "Ponta mais clara"
    lite.inputs["Color2"].default_value = (1.0, 0.97, 0.92, 1.0)
    L(tip2.outputs[0], lite.inputs["Fac"])
    L(mul_v.outputs["Color"], lite.inputs["Color1"])
    stage3 = [pat, ao, var, var2, tip, tip2, mul_ao, mul_v, lite]

    # 4. shading + clip
    bsdf = N("ShaderNodeBsdfPrincipled"); bsdf.location = (100, -200)
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Specular"].default_value = 0.15
    L(lite.outputs["Color"], bsdf.inputs["Base Color"])
    transp = N("ShaderNodeBsdfTransparent"); transp.location = (100, 80)
    mix = N("ShaderNodeMixShader"); mix.location = (400, 0); mix.label = "Corte (alpha clip)"
    L(alive.outputs[0], mix.inputs["Fac"])
    L(transp.outputs[0], mix.inputs[1])
    L(bsdf.outputs[0], mix.inputs[2])
    out = N("ShaderNodeOutputMaterial"); out.location = (620, 0)
    L(mix.outputs[0], out.inputs["Surface"])

    frame(nt, "1. Camada da casca (vem da UV)", BLUE, stage1,
          "Cada casca k tem a UV deslocada +2k em U.\n"
          "k = floor((U+0.5)/2); h = k/(CAMADAS-1): 0 pele, 1 ponta.\n"
          "O divisor deve ser CAMADAS-1 (script e 'pelos_vertex.glsl').")
    frame(nt, "2. Fios: corte por altura", GREEN, stage2,
          "Imagem 'fios': R = cone de cada fio (altura no centro).\n"
          "Fica se R > h: casca alta guarda disco menor = fio fino.\n"
          "Densidade = Scale do Mapping (sempre inteiro).\n"
          "A pele (camada 0) nunca e cortada.\n"
          "Rasante: na silhueta as cascas de fora afinam mais\n"
          "(esconde as fatias). 1.6 = forca do efeito.")
    frame(nt, "3. Cor: padrao, raiz escura, ponta clara", ORANGE, stage3,
          "Xadrez/Imagem = cor da pelagem (escala inteira).\n"
          "Ramp por h escurece a raiz (oclusao entre fios).\n"
          "G da imagem 'fios' varia cada fio; h^3 clareia a ponta.")
    frame(nt, "4. Superficie + Alpha Clip", PURPLE, [bsdf, transp, mix, out],
          "Alpha Blend = Clip: sem ordenar cascas e com sombra.\n"
          "Roughness alta: pelo nao brilha como plastico.")
    hint = N("NodeFrame")
    hint.label = "5. COMPRIMENTO/GRAVIDADE/VENTO: 'pelos_vertex.glsl'"
    hint.label_size = 20
    hint.use_custom_color = True
    hint.color = PURPLE
    hint.shrink = False
    hint.width = 560
    hint.height = 300
    hint.location = (-1720, -900)
    tb = bpy.data.texts.new("nota - casca")
    tb.write("Nos nao movem vertices: o Vertex Shader do material\n"
             "(texto 'pelos_vertex.glsl', funcao vertex()) empurra\n"
             "cada casca pela normal e curva a ponta para baixo\n"
             "no MUNDO (segue o objeto girando).\n"
             "#define COMPRIMENTO, GRAVIDADE, VENTO, VENTO_FREQ.\n"
             "Mais cascas: CAMADAS no script (e no #define).")
    hint.text = tb
    return m


# ---------------------------------------------------------------- geometry

def fur_object(name, loc, mat, rot_z=0.0):
    """Suzanne (subdivided, smooth) with CAMADAS shells merged into one mesh; shell k has U += 2k."""
    bpy.ops.mesh.primitive_monkey_add(radius=1.0, location=(0, 0, 0), calc_uvs=True)
    src = bpy.context.object
    mod = src.modifiers.new("Sub", 'SUBSURF')
    mod.levels = 1
    bpy.ops.object.modifier_apply(modifier=mod.name)
    me0 = src.data
    nv = len(me0.vertices)
    co = np.empty(nv * 3, np.float32); me0.vertices.foreach_get("co", co)
    nl = len(me0.loops)
    lv = np.empty(nl, np.int32); me0.loops.foreach_get("vertex_index", lv)
    npoly = len(me0.polygons)
    ls = np.empty(npoly, np.int32); me0.polygons.foreach_get("loop_start", ls)
    lt = np.empty(npoly, np.int32); me0.polygons.foreach_get("loop_total", lt)
    uv = np.empty(nl * 2, np.float32); me0.uv_layers[0].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    bpy.data.objects.remove(src, do_unlink=True)

    K = CAMADAS
    me = bpy.data.meshes.new(name)
    me.vertices.add(nv * K)
    cok = np.tile(co.reshape(-1, 3), (K, 1))
    cok[:, 0] += np.repeat(np.arange(K) * SHELL_GAP, nv)
    me.vertices.foreach_set("co", cok.ravel())
    me.loops.add(nl * K)
    me.loops.foreach_set("vertex_index", (lv[None, :] + (np.arange(K) * nv)[:, None]).ravel().astype(np.int32))
    me.polygons.add(npoly * K)
    me.polygons.foreach_set("loop_start", (ls[None, :] + (np.arange(K) * nl)[:, None]).ravel().astype(np.int32))
    me.polygons.foreach_set("loop_total", np.tile(lt, K))
    me.update(calc_edges=True)
    me.uv_textures.new("UVMap")
    uvk = np.tile(uv, (K, 1))
    uvk[:, 0] += np.repeat(np.arange(K) * 2.0, nl)
    me.uv_layers[0].data.foreach_set("uv", uvk.ravel())
    sm = np.ones(npoly * K, bool)
    me.polygons.foreach_set("use_smooth", sm)
    me.validate()
    ob = bpy.data.objects.new(name, me)
    scene.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (0.0, 0.0, rot_z)
    me.materials.append(mat)
    ob.game.physics_type = 'NO_COLLISION'
    return ob


fios = strand_image()
mat_check = fur_material("Pelo xadrez", fios)
mat_img = fur_material("Pelo imagem", fios, calico_image())

spin = fur_object("MacacoGirando", (-1.6, 0.0, 1.3), mat_check)
still = fur_object("MacacoParado", (1.6, 0.0, 1.3), mat_img, math.radians(20))

SPIN = (
    "import math\n"
    "from Range import logic\n"
    "own = logic.getCurrentController().owner\n"
    "t = logic.getRealTime()\n"
    "if 't0' not in own: own['t0'] = t; own['z0'] = own.worldPosition.z\n"
    "dt = t - own['t0']\n"
    "# gira devagar e balanca um pouco: a gravidade do pelo continua para baixo\n"
    "own.worldOrientation = [0.25 * math.sin(dt * 0.9), 0.0, dt * 0.6]\n"
    "own.worldPosition.z = own['z0'] + 0.15 * math.sin(dt * 1.3)\n"
)
tx = bpy.data.texts.new("girar.py")
tx.write(SPIN)
scene.objects.active = spin
bpy.ops.logic.sensor_add(type='ALWAYS', object=spin.name)
bpy.ops.logic.controller_add(type='PYTHON', object=spin.name)
spin.game.sensors[-1].use_pulse_true_level = True
spin.game.controllers[-1].text = tx
spin.game.sensors[-1].link(spin.game.controllers[-1])

# ground
bpy.ops.mesh.primitive_plane_add(location=(0.0, 0.0, 0.0))
ground = bpy.context.object
ground.scale = (20.0, 20.0, 1.0)
gm = bpy.data.materials.new("Chao")
gm.use_nodes = True
gb = gm.node_tree.nodes.get("Principled BSDF")
if gb:
    gb.inputs["Base Color"].default_value = (0.35, 0.33, 0.30, 1.0)
    gb.inputs["Roughness"].default_value = 0.9
ground.data.materials.append(gm)

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -8.0, 10.0),
                        rotation=(math.radians(45), 0.0, math.radians(-35)))
sun = bpy.context.object
sun.data.energy = 2.2
sun.data.color = (1.0, 0.96, 0.9)
sun.data.shadow_method = 'RAY_SHADOW'
sun.data.shadow_frustum_size = 30.0
sun.data.shadow_buffer_bias = 0.05

bpy.ops.object.camera_add(location=(0.0, -6.5, 2.4), rotation=(math.radians(82), 0.0, 0.0))
cam = bpy.context.object
cam.data.lens = 35.0
scene.camera = cam

if want_shot:
    shot = base
    text = bpy.data.texts.new("pelos_auto_screenshot.py")
    text.write(
        "import Range\n"
        "from Range import logic\n"
        "from mathutils import Vector\n"
        "own = logic.getCurrentController().owner\n"
        "t = logic.getRealTime()\n"
        "own['t0'] = own.get('t0', t)\n"
        "own['n'] = own.get('n', 0) + 1\n"
        "e = t - own['t0']\n"
        "if e > 3.0 and 'a' not in own:\n"
        "    own['a'] = 1; Range.render.makeScreenshot('%(s)s_game.png')\n"
        "if e > 3.3 and 'b' not in own:\n"
        "    own['b'] = 1\n"
        "    own.worldPosition = (2.9, -3.0, 2.0)\n"
        "    look = Vector((1.6, 0.0, 1.3)) - own.worldPosition\n"
        "    own.alignAxisToVect(-look, 2, 1.0); own.alignAxisToVect((0, 0, 1), 1, 1.0); own.alignAxisToVect(-look, 2, 1.0)\n"
        "if e > 6.0 and 'c' not in own:\n"
        "    own['c'] = 1; Range.render.makeScreenshot('%(s)s_close.png')\n"
        "if e > 6.3 and 'd' not in own:\n"
        "    own['d'] = 1\n"
        "    own.worldPosition = (-0.6, -3.6, 2.3)\n"
        "    look = Vector((-1.6, 0.0, 1.3)) - own.worldPosition\n"
        "    own.alignAxisToVect(-look, 2, 1.0); own.alignAxisToVect((0, 0, 1), 1, 1.0); own.alignAxisToVect(-look, 2, 1.0)\n"
        "if e > 9.0 and 'f' not in own:\n"
        "    own['f'] = 1; Range.render.makeScreenshot('%(s)s_spin.png')\n"
        "if e > 10.0:\n"
        "    msg = 'PELOS_FPS media %%.1f (%%d frames em %%.1f s)' %% (own['n'] / e, own['n'], e)\n"
        "    print(msg); open('%(s)s_fps.txt', 'w').write(msg + '\\n')\n"
        "    logic.endGame()\n" % {"s": shot}
    )
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
    cam.game.sensors[-1].use_pulse_true_level = True
    cam.game.controllers[-1].text = text
    cam.game.sensors[-1].link(cam.game.controllers[-1])
    try:
        scene.game_settings.use_frame_rate = False    # uncapped for the FPS number
        scene.game_settings.vsync = 'OFF'
    except Exception as ex:
        print("PELOS fps cap setting:", ex)

scene.game_settings.show_framerate_profile = False
scene.game_settings.show_debug_properties = False
bpy.ops.wm.save_as_mainfile(filepath=output, compress=True)
print("FUR_TEST saved", output)
