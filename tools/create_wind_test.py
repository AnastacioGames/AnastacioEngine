"""Wind on foliage demo (grass + bush), Game engine, Shading Nodes + material vertex shader.

Run with:  RangeEngine -b --python tools/create_wind_test.py -- demos/vento.range [--shot]

Why a vertex shader and not nodes: in this engine the node tree only drives the FRAGMENT shader. The
"Displacement" socket of Material Output is ignored by the GLSL generator (node_output_material just
forwards Surface), so nodes cannot move vertices. The supported route is the material's
"Vertex Shader" text (Material > Custom Shader, bpy: material.script_vert): the engine injects the
user function `void vertex()` into the generated vertex shader of the node material, right before
the model-view transform. Inside it you can read/write VERTEX (object space position) and read TIME
(seconds, the same uniform the Time node uses, updated every frame). Nodes keep doing the colour,
texture and alpha clip.

- "Grama (vento)": field of grass cards (two crossed quads each), blade texture with alpha, Alpha
  Clip. The vertex shader bends each card by height (root fixed, tip moves the most): slow wave that
  travels along the wind direction + gusts + fast flutter.
- "Folhas (vento)": leaf cards of a small bush/tree crown; the whole crown sways slowly and every
  leaf flutters with its own phase. The trunk is a normal rigid material.
Tweak the wind in the Text datablocks "vento_grama.glsl" / "vento_folhas.glsl" (#define at the top).

Shadows: only Alpha Clip materials cast shadows with their own shader (so the shadow also moves and
keeps the blade cut-out). Opaque materials use a generic override shader in the shadow pass, which
ignores the vertex shader (see engine notes in the report). Keep wind materials on Alpha Clip.
The native "Foliage Shader" panel (material.use_foliage) is an older built-in alternative: one noise
translation for every vertex above z = 0.1, no height falloff; this demo does not use it.
--shot    adds a camera controller that saves <output>_game.png at frame 60 and ends the game.
"""
import bpy
import math
import os
import random
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "vento.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Vento World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.45, 0.6, 0.85, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.7
scene.world = world

GRASS_H = 0.55          # card height (m); the vertex shader uses the same value as ALTURA


# ---------------------------------------------------------------- generated textures

def grass_image(size=256, blades=7, seed=5):
    """Several tapered, slightly curved blades on transparent background; colour darker at the base."""
    rnd = random.Random(seed)
    px = [0.0] * (size * size * 4)
    for b in range(blades):
        x0 = (b + 0.5) / blades + rnd.uniform(-0.04, 0.04)
        w0 = rnd.uniform(0.035, 0.055)
        top = rnd.uniform(0.7, 0.98)
        lean = rnd.uniform(-0.15, 0.15)
        tint = rnd.uniform(0.8, 1.15)
        for y in range(int(size * top)):
            v = y / size
            t = v / top
            cx = x0 + lean * t * t
            w = w0 * (1.0 - t) ** 0.8 + 0.002
            for x in range(max(0, int((cx - w) * size)), min(size, int((cx + w) * size) + 1)):
                d = abs(x / size - cx) / w
                if d > 1.0:
                    continue
                shade = (0.35 + 0.65 * t) * tint * (1.0 - 0.25 * d)
                i = (y * size + x) * 4
                px[i:i + 4] = (0.16 * shade, 0.42 * shade, 0.08 * shade, 1.0)
    img = bpy.data.images.new("grama_laminas", size, size, alpha=True)
    img.pixels = px
    img.pack(as_png=True)
    return img


def leaf_image(size=128):
    """One leaf (ellipse with pointed tip and a midrib) on transparent background."""
    px = [0.0] * (size * size * 4)
    for y in range(size):
        v = y / (size - 1)
        half = 0.42 * math.sin(math.pi * v) ** 0.7 * (1.0 - 0.3 * v)
        for x in range(size):
            u = abs(x / (size - 1) - 0.5)
            if u > half:
                continue
            rib = 0.75 if u < 0.015 else 1.0
            s = (0.7 + 0.3 * v) * rib * (1.0 - 0.3 * u / max(half, 1e-3))
            i = (y * size + x) * 4
            px[i:i + 4] = (0.13 * s, 0.36 * s, 0.07 * s, 1.0)
    img = bpy.data.images.new("folha", size, size, alpha=True)
    img.pixels = px
    img.pack(as_png=True)
    return img


# ---------------------------------------------------------------- vertex shaders (wind)

GRASS_VS = """// Vento na grama. VERTEX = posicao no espaco do objeto, TIME = segundos.
// Ajuste aqui (recompila ao rodar o jogo):
#define FORCA      0.22            // deslocamento maximo da ponta (m)
#define FREQ       1.7             // velocidade da onda principal
#define ESCALA     0.45            // ondas por metro no chao
#define RAJADA     0.6             // 0 = vento constante, 1 = rajadas fortes
#define TREMOR     0.12            // tremida rapida das laminas
#define ALTURA     %.3f            // altura da lamina: raiz z=0 fica parada
#define DIRECAO    vec2(0.8, 0.6)  // direcao do vento (espaco do objeto)

void vertex()
{
	float h = clamp(VERTEX.z / ALTURA, 0.0, 1.0);
	float mask = h * h;                       // raiz presa, ponta solta
	vec2 dir = normalize(DIRECAO);
	vec2 p = VERTEX.xy;
	float fase = dot(p, dir) * ESCALA;        // a onda anda na direcao do vento
	float onda = 0.5 + 0.5 * sin(TIME * FREQ - fase * 6.2831);
	float rajada = 1.0 - RAJADA + RAJADA * (0.5 + 0.5 * sin(TIME * 0.37 - fase * 1.3 + p.y * 0.21));
	float tremor = TREMOR * sin(TIME * 9.0 + p.x * 13.1 + p.y * 7.7);
	float curva = (onda * rajada + tremor) * FORCA * mask;
	VERTEX.xy += dir * curva;
	VERTEX.z -= curva * curva / ALTURA * h;   // mantem o comprimento da lamina
}
""" % GRASS_H

LEAF_VS = """// Vento nas folhas. VERTEX = posicao no espaco do objeto, TIME = segundos.
#define FORCA      0.10            // balanco da copa inteira (m no topo)
#define FREQ       0.9             // velocidade do balanco
#define TREMOR     0.035           // tremida de cada folha (m)
#define FREQ_TREM  7.0             // velocidade da tremida
#define BASE       0.9             // abaixo desta altura (z) nada se move
#define DIRECAO    vec2(0.8, 0.6)

void vertex()
{
	float h = max(VERTEX.z - BASE, 0.0);
	vec2 dir = normalize(DIRECAO);
	float balanco = (0.6 + 0.4 * sin(TIME * FREQ)) * (0.8 + 0.2 * sin(TIME * 2.3)) * FORCA * h;
	vec3 p = VERTEX;
	float fase = p.x * 5.3 + p.y * 3.7 + p.z * 4.1;      // fase propria de cada folha
	vec3 tremor = vec3(sin(TIME * FREQ_TREM + fase),
	                   cos(TIME * FREQ_TREM * 1.1 + fase * 1.3),
	                   sin(TIME * FREQ_TREM * 0.9 + fase * 0.7)) * TREMOR * min(h, 1.0);
	VERTEX.xy += dir * balanco;
	VERTEX += tremor;
}
"""


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


def wind_material(name, img, vs_name, vs_code, base_tint, tip_tint, tex_label):
    """Fragment = nodes (texture, base->tip colour, alpha clip); vertex = script_vert text (wind)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.game_settings.alpha_blend = 'CLIP'
    m.game_settings.use_backface_culling = False
    vs = bpy.data.texts.new(vs_name)
    vs.write(vs_code)
    m.script_vert = vs

    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new
    L = nt.links.new

    coord = N("ShaderNodeTexCoord"); coord.location = (-1500, 0)
    tex = N("ShaderNodeTexImage"); tex.image = img; tex.location = (-1260, 60); tex.label = tex_label
    tex.interpolation = 'Linear'
    L(coord.outputs["UV"], tex.inputs["Vector"])
    sep = N("ShaderNodeSeparateXYZ"); sep.location = (-760, -200); sep.label = "Altura na carta (V)"
    L(coord.outputs["UV"], sep.inputs["Vector"])
    ramp = N("ShaderNodeValToRGB"); ramp.location = (-560, -200); ramp.label = "Cor raiz -> ponta"
    ramp.color_ramp.elements[0].color = base_tint
    ramp.color_ramp.elements[1].color = tip_tint
    L(sep.outputs["Y"], ramp.inputs["Fac"])
    mix = N("ShaderNodeMixRGB"); mix.location = (-260, 60); mix.blend_type = 'MULTIPLY'; mix.label = "Tingir"
    mix.inputs["Fac"].default_value = 1.0
    L(tex.outputs["Color"], mix.inputs["Color1"])
    L(ramp.outputs["Color"], mix.inputs["Color2"])

    bsdf = N("ShaderNodeBsdfPrincipled"); bsdf.location = (60, 120)
    bsdf.inputs["Roughness"].default_value = 0.7
    bsdf.inputs["Specular"].default_value = 0.2
    L(mix.outputs["Color"], bsdf.inputs["Base Color"])
    transp = N("ShaderNodeBsdfTransparent"); transp.location = (60, -560); transp.label = "Recorte"
    mixs = N("ShaderNodeMixShader"); mixs.location = (380, 0); mixs.label = "Alpha da textura"
    L(mix.outputs["Color"], transp.inputs["Color"])   # white here would leak into the clipped edge
    L(tex.outputs["Alpha"], mixs.inputs["Fac"])
    L(transp.outputs["BSDF"], mixs.inputs[1])
    L(bsdf.outputs["BSDF"], mixs.inputs[2])
    out = N("ShaderNodeOutputMaterial"); out.location = (600, 0)
    L(mixs.outputs["Shader"], out.inputs["Surface"])

    frame(nt, "1. Textura da carta", BLUE, (coord, tex),
          "Carta com laminas/folha desenhadas e alpha.\n"
          "Troque a imagem pela sua (PNG com alpha).")
    frame(nt, "2. Cor da raiz a ponta", GREEN, (sep, ramp, mix),
          "V da UV = altura na carta (0 raiz, 1 ponta).\n"
          "Raiz escura simula sombra entre as laminas.")
    frame(nt, "3. Recorte (Alpha Clip)", ORANGE, (bsdf, transp, mixs, out),
          "Alpha da textura escolhe Transparent x Principled.\n"
          "Material > Game Settings > Alpha Blend = Alpha Clip.\n"
          "Com Clip a sombra tambem balanca e sai recortada.")
    # The wind lives in the vertex shader text: a lone purple frame points to it.
    hint = N("NodeFrame")
    hint.label = "4. VENTO: texto '%s'" % vs_name
    hint.label_size = 20
    hint.use_custom_color = True
    hint.color = PURPLE
    hint.shrink = False
    hint.width = 520
    hint.height = 330
    hint.location = (-1520, -480)
    tb = bpy.data.texts.new("nota - vento " + name)
    tb.write("Nos nao movem vertices nesta engine (o socket\n"
             "Displacement e ignorado). O vento esta no Vertex\n"
             "Shader do material (aba Material > Custom Shader):\n"
             "texto '%s', funcao vertex().\n"
             "Edite os #define no topo: FORCA, FREQ, DIRECAO...\n"
             "VERTEX = posicao (espaco do objeto), TIME = tempo.\n"
             "Os nos continuam fazendo cor, textura e recorte." % vs_name)
    hint.text = tb
    return m


# ---------------------------------------------------------------- geometry

def build_mesh(name, verts, faces, uvs):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.uv_textures.new("UVMap")
    uvl = me.uv_layers[0].data
    for poly in me.polygons:
        for k, li in enumerate(poly.loop_indices):
            uvl[li].uv = uvs[poly.index][k]
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.objects.link(ob)
    return ob


def grass_field(mat, size_x=16.0, size_y=10.0, count=900, seed=11):
    """Two crossed quads per card; root at z = 0 of the mesh (the shader mask relies on it)."""
    rnd = random.Random(seed)
    verts, faces, uvs = [], [], []
    quad_uv = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    for _ in range(count):
        x = rnd.uniform(-size_x / 2, size_x / 2)
        y = rnd.uniform(-size_y / 2, size_y / 2)
        if x * x + (y - 1.5) ** 2 < 1.2:        # leave room for the bush trunk
            continue
        a = rnd.uniform(0.0, math.pi)
        w = rnd.uniform(0.22, 0.32)
        hgt = GRASS_H * rnd.uniform(0.75, 1.0)
        for da in (0.0, math.pi / 2):
            c, s = math.cos(a + da) * w, math.sin(a + da) * w
            i = len(verts)
            verts += [(x - c, y - s, 0.0), (x + c, y + s, 0.0), (x + c, y + s, hgt), (x - c, y - s, hgt)]
            faces.append((i, i + 1, i + 2, i + 3))
            uvs.append(quad_uv)
    ob = build_mesh("Grama", verts, faces, uvs)
    ob.data.materials.append(mat)
    return ob


def bush(leaf_mat, bark_mat, loc=(0.0, 1.5, 0.0), seed=4):
    """Trunk (rigid, opaque) + crown of leaf cards (wind material)."""
    bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=0.12, radius2=0.06, depth=1.6,
                                    location=(loc[0], loc[1], 0.8))
    trunk = bpy.context.object
    trunk.name = "Tronco"
    trunk.data.materials.append(bark_mat)

    rnd = random.Random(seed)
    verts, faces, uvs = [], [], []
    quad_uv = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    for _ in range(700):
        # point inside an ellipsoid crown centred at z = 1.9 (object = mesh space)
        while True:
            px, py, pz = (rnd.uniform(-1, 1) for _ in range(3))
            if px * px + py * py + pz * pz <= 1.0:
                break
        cx, cy, cz = px * 1.0, py * 1.0, 1.9 + pz * 0.75
        s = rnd.uniform(0.12, 0.18)
        yaw = rnd.uniform(0, 2 * math.pi)
        pitch = rnd.uniform(-0.6, 0.6)
        ux, uy = math.cos(yaw) * s, math.sin(yaw) * s
        vx, vy, vz = -math.sin(yaw) * math.sin(pitch) * s * 2, math.cos(yaw) * math.sin(pitch) * s * 2, \
            math.cos(pitch) * s * 2
        i = len(verts)
        verts += [(cx - ux, cy - uy, cz), (cx + ux, cy + uy, cz),
                  (cx + ux + vx, cy + uy + vy, cz + vz), (cx - ux + vx, cy - uy + vy, cz + vz)]
        faces.append((i, i + 1, i + 2, i + 3))
        uvs.append(quad_uv)
    crown = build_mesh("Copa", verts, faces, uvs)
    crown.location = loc
    crown.data.materials.append(leaf_mat)
    return trunk, crown


def simple_material(name, color, rough=0.8):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF") or nt.nodes.new("ShaderNodeBsdfPrincipled")
    for n in list(nt.nodes):
        if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL']
    out = out[0] if out else nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


# ---------------------------------------------------------------- scene

grass_mat = wind_material("Grama (vento)", grass_image(), "vento_grama.glsl", GRASS_VS,
                          (0.45, 0.5, 0.4, 1.0), (1.0, 1.0, 0.75, 1.0), "Laminas de grama")
leaf_mat = wind_material("Folhas (vento)", leaf_image(), "vento_folhas.glsl", LEAF_VS,
                         (0.7, 0.8, 0.7, 1.0), (1.0, 1.0, 0.8, 1.0), "Folha")
bark_mat = simple_material("Casca", (0.18, 0.11, 0.06, 1.0))
soil_mat = simple_material("Chao", (0.10, 0.13, 0.05, 1.0), 0.95)

grass_field(grass_mat)
bush(leaf_mat, bark_mat)

bpy.ops.mesh.primitive_plane_add(location=(0.0, 0.0, 0.0))
ground = bpy.context.object
ground.name = "Chao"
ground.scale = (40.0, 40.0, 1.0)
ground.data.materials.append(soil_mat)

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -10.0, 15.0), rotation=(math.radians(55), 0.0, math.radians(160)))
sun = bpy.context.object
sun.data.energy = 2.2
sun.data.shadow_method = 'RAY_SHADOW'
sun.data.shadow_buffer_bias = 0.2
sun.data.shadow_frustum_size = 22.0

bpy.ops.object.camera_add(location=(0.0, -8.5, 2.2), rotation=(math.radians(78), 0.0, 0.0))
scene.camera = bpy.context.object

if want_shot:
    shot = base + "_game.png"
    text = bpy.data.texts.new("vento_auto_screenshot.py")
    text.write(
        "import Range\n"
        "from Range import logic\n"
        "own = logic.getCurrentController().owner\n"
        "own['frame'] = own.get('frame', 0) + 1\n"
        "if own['frame'] == 60:\n"
        "    Range.render.makeScreenshot('%s')\n"
        "if own['frame'] == 75:\n"
        "    Range.render.makeScreenshot('%s')\n"
        "if own['frame'] == 80:\n"
        "    logic.endGame()\n" % (shot, base + "_game2.png")
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
print("WIND_TEST saved", output)
