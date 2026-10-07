"""Interactive grass demo: dense wind-blown grass on rolling hills, flattened by a rolling ball.

Run with:  RangeEngine -b --python tools/create_grass_trail_test.py -- demos/grama_trilha.range [--shot]

How it works
- Grass = real geometry: ~136k thin blades (5 vertices / 3 triangles each), split into 8x8 chunk objects
  so the engine culls what is off screen. All chunks sit at the origin with identity transform, so the
  vertex shader's object space == world space (the trail texture is addressed in world XY).
- Wind + flattening live in the material vertex shader (Text "grama_vertex.glsl", material.script_vert,
  function `void vertex()`, VERTEX/NORMAL/TIME). The root of each blade is found with the same terrain
  height function used to build the mesh (terreno() in GLSL == terrain_height() here: keep them equal).
- Trail: a 256x256 RGB image "trilha" covering TRAIL_SIZE x TRAIL_SIZE m around the origin.
  R = how flattened (0..1), G/B = direction the blades lie (0.5 + 0.5 * dir). The game logic
  (Text "grama_logica.py", numpy) paints the ball footprint every frame, lets R decay slowly (grass
  recovers), and uploads it with Range.texture.ImageBuff + Range.texture.Texture (VideoTexture swaps the
  image's GL texture). The image is used by an Image Texture node in the fragment (flattened grass gets
  a lighter sheen), which makes the codegen declare and bind it as sampler `samp0`; the vertex code
  declares the same `uniform sampler2D samp0` and reads it with textureLod (vertex texture fetch).
  The image is also in texture slot 0 of the material: Range.texture.Texture(obj, 0, 0) needs an MTex.
  If you add another Image Texture node before it, the sampler may become samp1 (#define TRILHA_TEX).
- Ball: rigid body sphere, arrows/WASD push it relative to the camera, camera follows behind.
  Haze: node group "Nevoa" (camera distance -> mix with an Emission of the sky colour) in both
  materials, because world mist is ignored by shading-node materials (engine fix proposed separately).
  Sun with shadows (grass casts/receives them through its own vertex shader).
Measured: 136k blades (680k vertices), ~305 FPS uncapped / 60 FPS vsync on RX 6800M, 1280x720.
--shot    drives the ball along a scripted S path, then saves <output>_game.png and <output>_game2.png
          (0.25 s apart, to check the wind) from an overview camera, prints the average FPS and ends.
"""
import bpy
import math
import os
import random
import sys

import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "grama_trilha.range")
want_shot = "--shot" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

SKY = (0.78, 0.82, 0.80)
world = bpy.data.worlds.new("Grama World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = SKY + (1.0,)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
world.horizon_color = SKY                       # mist colour
# World mist is only applied to legacy (non-node) materials in this engine, so the haze is done in
# the node trees (frame "Nevoa", node group "Nevoa"). Keep world mist off to avoid fogging twice.
world.mist_settings.use_mist = False
FOG_START = 5.0         # metres where the haze starts
FOG_DEPTH = 32.0        # metres from start to full haze
scene.world = world

TRAIL_SIZE = 40.0       # metres covered by the trail texture (and by the grass field)
TRAIL_RES = 256
GRASS_H = 0.55          # tallest blade (m); ALTURA in the vertex shader
CHUNKS = 8
DENSITY = 85            # blades per m2


def terrain_height(x, y):
    """Gentle hills. MUST match terreno() in GRASS_VS (numpy or float)."""
    return (1.1 * np.sin(x * 0.13 + 0.5) * np.cos(y * 0.11)
            + 0.6 * np.sin(x * 0.07 - y * 0.09 + 1.3)
            + 0.18 * np.sin(x * 0.31 + y * 0.23))


# ---------------------------------------------------------------- vertex shader (wind + trail)

GRASS_VS = """// Grama interativa: vento + trilha amassada pela bola.
// VERTEX/NORMAL = espaco do objeto (= mundo: os pedacos da grama ficam na origem), TIME = segundos.
// Ajuste aqui (recompila ao rodar o jogo):
#define FORCA      0.16            // deslocamento maximo da ponta pelo vento (m)
#define FREQ       1.6             // velocidade da onda principal
#define ESCALA     0.18            // ondas por metro (onda grande que passa pelo campo)
#define RAJADA     0.7             // 0 = vento constante, 1 = rajadas fortes
#define TREMOR     0.10            // tremida rapida das laminas
#define DIRECAO    vec2(0.8, 0.6)  // direcao do vento
#define ALTURA     %.3f            // altura da lamina mais alta (m)
#define DEITAR     1.30            // quanto a grama amassada deita (radianos, 1.57 = no chao)
#define VENTO_AMASSADA 0.25        // quanto vento sobra na grama amassada
#define TAM_TRILHA %.1f            // metros cobertos pela textura 'trilha' (centrada na origem)
#define TRILHA_TEX samp0           // sampler da textura 'trilha' gerado pelo no Image Texture

uniform sampler2D TRILHA_TEX;

// Mesmo relevo usado para gerar o terreno no script Python (terrain_height): acha a raiz da lamina.
float terreno(vec2 p)
{
	return 1.1 * sin(p.x * 0.13 + 0.5) * cos(p.y * 0.11)
	     + 0.6 * sin(p.x * 0.07 - p.y * 0.09 + 1.3)
	     + 0.18 * sin(p.x * 0.31 + p.y * 0.23);
}

void vertex()
{
	vec2 p = VERTEX.xy;
	float raiz = terreno(p);
	float alt = max(VERTEX.z - raiz, 0.0);        // altura deste vertice acima da raiz
	float h = clamp(alt / ALTURA, 0.0, 1.0);

	// Trilha: R = quanto amassou, GB = direcao em que a grama deita.
	vec3 tr = textureLod(TRILHA_TEX, p / TAM_TRILHA + 0.5, 0.0).rgb;
	float amassa = smoothstep(0.02, 1.0, tr.r);
	vec2 deita = tr.gb * 2.0 - 1.0;
	deita = dot(deita, deita) > 1e-4 ? normalize(deita) : vec2(1.0, 0.0);

	// Deitar: gira a lamina em volta da raiz (mantem o comprimento).
	float ang = amassa * DEITAR;
	VERTEX.xy += deita * alt * sin(ang);
	VERTEX.z = raiz + alt * cos(ang);

	// Vento: onda que anda na direcao do vento + rajadas + tremida. Raiz presa (h*h).
	vec2 dir = normalize(DIRECAO);
	float fase = dot(p, dir) * ESCALA;
	float onda = 0.5 + 0.5 * sin(TIME * FREQ - fase * 6.2831);
	float rajada = 1.0 - RAJADA + RAJADA * (0.5 + 0.5 * sin(TIME * 0.31 - fase * 1.7 + p.y * 0.05));
	float tremor = TREMOR * sin(TIME * 8.0 + p.x * 11.3 + p.y * 7.9);
	float curva = (onda * rajada + tremor) * FORCA * h * h * mix(1.0, VENTO_AMASSADA, amassa);
	VERTEX.xy += dir * curva;
	VERTEX.z -= curva * curva / ALTURA * h;

	// Normal quase para cima: grama fofa e iluminada por igual (laminas finas nao tem lado).
	vec3 cima = normalize(vec3(deita * sin(ang) * 0.6 + dir * curva, 1.0));
	NORMAL = normalize(mix(cima, NORMAL, 0.25));
}
""" % (GRASS_H, TRAIL_SIZE)


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


def fog_group():
    """Node group: distance to the camera -> 0..1 haze factor (quadratic)."""
    g = bpy.data.node_groups.get("Nevoa")
    if g:
        return g
    g = bpy.data.node_groups.new("Nevoa", "ShaderNodeTree")
    g.outputs.new("NodeSocketFloat", "Fator")
    gin = g.nodes.new("NodeGroupInput"); gin.location = (-600, 0)
    gout = g.nodes.new("NodeGroupOutput"); gout.location = (500, 0)
    cam = g.nodes.new("ShaderNodeCameraData"); cam.location = (-400, 0)
    sub = g.nodes.new("ShaderNodeMath"); sub.operation = 'SUBTRACT'; sub.location = (-180, 0)
    sub.inputs[1].default_value = FOG_START; sub.label = "Inicio (m)"
    div = g.nodes.new("ShaderNodeMath"); div.operation = 'DIVIDE'; div.location = (0, 0)
    div.inputs[1].default_value = FOG_DEPTH; div.label = "Profundidade (m)"
    div.use_clamp = True
    sq = g.nodes.new("ShaderNodeMath"); sq.operation = 'POWER'; sq.location = (180, 0)
    sq.inputs[1].default_value = 1.6; sq.label = "Curva"
    mx = g.nodes.new("ShaderNodeMath"); mx.operation = 'MULTIPLY'; mx.location = (340, 0)
    mx.inputs[1].default_value = 0.92; mx.label = "Maximo"
    g.links.new(cam.outputs["View Distance"], sub.inputs[0])
    g.links.new(sub.outputs[0], div.inputs[0])
    g.links.new(div.outputs[0], sq.inputs[0])
    g.links.new(sq.outputs[0], mx.inputs[0])
    g.links.new(mx.outputs[0], gout.inputs[0])
    return g


def add_fog(nt, shader_out, out_node, x, y):
    """Mix the surface with an emission of the sky colour by the haze factor."""
    N = nt.nodes.new
    grp = N("ShaderNodeGroup"); grp.node_tree = fog_group(); grp.location = (x, y - 260); grp.label = "Nevoa"
    em = N("ShaderNodeEmission"); em.location = (x, y - 380); em.label = "Cor do ceu"
    em.inputs["Color"].default_value = SKY + (1.0,)
    mixs = N("ShaderNodeMixShader"); mixs.location = (x + 240, y); mixs.label = "Superficie x nevoa"
    nt.links.new(grp.outputs[0], mixs.inputs["Fac"])
    nt.links.new(shader_out, mixs.inputs[1])
    nt.links.new(em.outputs["Emission"], mixs.inputs[2])
    nt.links.new(mixs.outputs["Shader"], out_node.inputs["Surface"])
    return [grp, em, mixs]


def trail_image():
    img = bpy.data.images.new("trilha", TRAIL_RES, TRAIL_RES, alpha=False)
    px = np.zeros((TRAIL_RES * TRAIL_RES, 4), dtype=np.float32)
    px[:, 1] = 0.5
    px[:, 2] = 0.5
    px[:, 3] = 1.0
    img.pixels = px.ravel().tolist()
    img.pack(as_png=True)
    return img


def world_uv_nodes(nt, x, y):
    """Object coords (= world) -> UV of the trail texture: xy / TAM + 0.5."""
    N = nt.nodes.new
    sep = N("ShaderNodeSeparateXYZ"); sep.location = (x, y); sep.label = "Posicao no mundo"
    mx = N("ShaderNodeMath"); mx.operation = 'MULTIPLY_ADD' if False else 'MULTIPLY'
    mx.location = (x + 200, y + 60); mx.inputs[1].default_value = 1.0 / TRAIL_SIZE; mx.hide = True
    my = N("ShaderNodeMath"); my.operation = 'MULTIPLY'
    my.location = (x + 200, y - 20); my.inputs[1].default_value = 1.0 / TRAIL_SIZE; my.hide = True
    ax = N("ShaderNodeMath"); ax.operation = 'ADD'; ax.location = (x + 360, y + 60)
    ax.inputs[1].default_value = 0.5; ax.hide = True
    ay = N("ShaderNodeMath"); ay.operation = 'ADD'; ay.location = (x + 360, y - 20)
    ay.inputs[1].default_value = 0.5; ay.hide = True
    comb = N("ShaderNodeCombineXYZ"); comb.location = (x + 520, y); comb.label = "UV da trilha"
    nt.links.new(sep.outputs["X"], mx.inputs[0])
    nt.links.new(sep.outputs["Y"], my.inputs[0])
    nt.links.new(mx.outputs[0], ax.inputs[0])
    nt.links.new(my.outputs[0], ay.inputs[0])
    nt.links.new(ax.outputs[0], comb.inputs["X"])
    nt.links.new(ay.outputs[0], comb.inputs["Y"])
    return sep, [sep, mx, my, ax, ay, comb], comb


def grass_material(trail):
    m = bpy.data.materials.new("Grama (trilha)")
    m.use_nodes = True
    m.game_settings.use_backface_culling = False
    vs = bpy.data.texts.new("grama_vertex.glsl")
    vs.write(GRASS_VS)
    m.script_vert = vs
    # Texture slot 0 = the trail image: Range.texture.Texture(obj, 0, 0) looks it up here.
    tex = bpy.data.textures.new("trilha", 'IMAGE')
    tex.image = trail
    slot = m.texture_slots.add()
    slot.texture = tex
    slot.use = False

    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new
    L = nt.links.new

    # 1. trail texture in world XY (comes first so it gets sampler samp0)
    coord = N("ShaderNodeTexCoord"); coord.location = (-1900, 300)
    sep, uvnodes, comb = world_uv_nodes(nt, -1700, 360)
    L(coord.outputs["Object"], sep.inputs["Vector"])
    ttex = N("ShaderNodeTexImage"); ttex.image = trail; ttex.location = (-940, 400); ttex.label = "Trilha (Python)"
    ttex.interpolation = 'Linear'
    L(comb.outputs["Vector"], ttex.inputs["Vector"])
    tsep = N("ShaderNodeSeparateRGB"); tsep.location = (-660, 400); tsep.label = "R = amassado"
    L(ttex.outputs["Color"], tsep.inputs["Image"])

    # 2. colour: root -> tip and noise variation
    uv = N("ShaderNodeUVMap") if hasattr(bpy.types, "ShaderNodeUVMap") else None
    usep = N("ShaderNodeSeparateXYZ"); usep.location = (-1080, -340); usep.label = "V = altura na lamina"
    L(coord.outputs["UV"], usep.inputs["Vector"])
    if uv:
        nt.nodes.remove(uv)
    ramp = N("ShaderNodeValToRGB"); ramp.location = (-860, -340); ramp.label = "Raiz escura -> ponta clara"
    ramp.color_ramp.elements[0].color = (0.03, 0.055, 0.015, 1.0)
    ramp.color_ramp.elements[1].color = (0.40, 0.50, 0.15, 1.0)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[1].position = 0.85
    L(usep.outputs["Y"], ramp.inputs["Fac"])
    noise = N("ShaderNodeTexNoise"); noise.location = (-1080, -640); noise.label = "Manchas no campo"
    noise.inputs["Scale"].default_value = 0.12
    noise.inputs["Detail"].default_value = 2.0
    L(coord.outputs["Object"], noise.inputs["Vector"])
    vramp = N("ShaderNodeValToRGB"); vramp.location = (-860, -640); vramp.label = "Verde x amarelado"
    vramp.color_ramp.elements[0].color = (0.70, 1.0, 0.55, 1.0)
    vramp.color_ramp.elements[1].color = (1.15, 1.0, 0.50, 1.0)
    vramp.color_ramp.elements[0].position = 0.35
    vramp.color_ramp.elements[1].position = 0.65
    L(noise.outputs["Fac"], vramp.inputs["Fac"])
    tint = N("ShaderNodeMixRGB"); tint.blend_type = 'MULTIPLY'; tint.location = (-580, -460); tint.label = "Variacao"
    tint.inputs["Fac"].default_value = 1.0
    L(ramp.outputs["Color"], tint.inputs["Color1"])
    L(vramp.outputs["Color"], tint.inputs["Color2"])

    # 3. flattened grass: lighter, yellower sheen (blades lying show their lit side)
    sheen = N("ShaderNodeMixRGB"); sheen.location = (-40, 160); sheen.label = "Brilho da grama deitada"
    sheen.blend_type = 'MIX'
    sheen.inputs["Color2"].default_value = (0.55, 0.58, 0.25, 1.0)
    fac = N("ShaderNodeMath"); fac.operation = 'MULTIPLY'; fac.location = (-260, 380); fac.label = "Forca do brilho"
    fac.inputs[1].default_value = 0.45
    L(tsep.outputs["R"], fac.inputs[0])
    L(fac.outputs[0], sheen.inputs["Fac"])
    L(tint.outputs["Color"], sheen.inputs["Color1"])

    bsdf = N("ShaderNodeBsdfPrincipled"); bsdf.location = (200, 160)
    bsdf.inputs["Roughness"].default_value = 0.65
    bsdf.inputs["Specular"].default_value = 0.25
    L(sheen.outputs["Color"], bsdf.inputs["Base Color"])
    out = N("ShaderNodeOutputMaterial"); out.location = (1000, 160)
    fogn = add_fog(nt, bsdf.outputs["BSDF"], out, 540, 160)

    frame(nt, "1. Trilha da bola (textura do Python)", BLUE, [coord, ttex, tsep] + uvnodes,
          "Imagem 'trilha' pintada a cada frame pelo script\n"
          "grama_logica.py: R = amassado, G/B = direcao.\n"
          "Coordenada Object = mundo (grama na origem).\n"
          "A MESMA textura e lida no Vertex Shader (samp0).")
    frame(nt, "2. Cor: raiz -> ponta + manchas", GREEN, (usep, ramp, noise, vramp, tint),
          "V da UV = altura na lamina (0 raiz, 1 ponta).\n"
          "Raiz escura = sombra entre as laminas.\n"
          "Noise grande (Scale 0.12) varia verde/amarelo.")
    frame(nt, "3. Grama deitada + superficie", ORANGE, (fac, sheen, bsdf),
          "Onde a bola passou a grama fica mais clara.\n"
          "Forca do brilho: 0 = sem diferenca de cor.")
    frame(nt, "5. Nevoa (distancia da camera)", PURPLE, fogn + [out],
          "Grupo 'Nevoa': Inicio/Profundidade em metros.\n"
          "Cor do ceu = cor do World (Background).\n"
          "O mist do World nao age em materiais de nos.")
    hint = N("NodeFrame")
    hint.label = "4. VENTO + AMASSAR: texto 'grama_vertex.glsl'"
    hint.label_size = 20
    hint.use_custom_color = True
    hint.color = PURPLE
    hint.shrink = False
    hint.width = 560
    hint.height = 360
    hint.location = (-1920, -1000)
    tb = bpy.data.texts.new("nota - vento e trilha")
    tb.write("Nos nao movem vertices nesta engine. O movimento\n"
             "esta no Vertex Shader do material (Custom Shader):\n"
             "texto 'grama_vertex.glsl', funcao vertex().\n"
             "#define: FORCA/FREQ/DIRECAO (vento), DEITAR\n"
             "(quanto deita), TAM_TRILHA (= TRAIL_SIZE).\n"
             "Recuperacao/raio da trilha: grama_logica.py\n"
             "(RECUPERA, SEGURA, RAIO).")
    hint.text = tb
    return m


def ground_material():
    """Dark grass-coloured soil with the same noise, so gaps between blades blend in."""
    m = bpy.data.materials.new("Chao (terra sob a grama)")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new
    L = nt.links.new
    coord = N("ShaderNodeTexCoord"); coord.location = (-900, 0)
    noise = N("ShaderNodeTexNoise"); noise.location = (-680, 0); noise.label = "Mesmas manchas da grama"
    noise.inputs["Scale"].default_value = 0.12
    noise.inputs["Detail"].default_value = 2.0
    L(coord.outputs["Object"], noise.inputs["Vector"])
    ramp = N("ShaderNodeValToRGB"); ramp.location = (-460, 0); ramp.label = "Cor do chao"
    ramp.color_ramp.elements[0].color = (0.03, 0.06, 0.012, 1.0)
    ramp.color_ramp.elements[1].color = (0.07, 0.08, 0.02, 1.0)
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 0.65
    L(noise.outputs["Fac"], ramp.inputs["Fac"])
    bsdf = N("ShaderNodeBsdfPrincipled"); bsdf.location = (-160, 0)
    bsdf.inputs["Roughness"].default_value = 0.95
    bsdf.inputs["Specular"].default_value = 0.1
    L(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    out = N("ShaderNodeOutputMaterial"); out.location = (600, 0)
    fogn = add_fog(nt, bsdf.outputs["BSDF"], out, 140, 0)
    frame(nt, "2. Nevoa", PURPLE, fogn + [out],
          "Mesmo grupo 'Nevoa' da grama.")
    frame(nt, "1. Chao com as mesmas manchas", GREEN, (coord, noise, ramp, bsdf),
          "Escuro e com a mesma Noise da grama: os buracos\n"
          "entre as laminas somem. Longe, a nevoa esconde.")
    return m


def ball_material():
    m = bpy.data.materials.new("Bola")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF") or nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.9, 0.9, 0.88, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.35
    return m


# ---------------------------------------------------------------- geometry

def terrain(mat, size=140.0, res=140):
    """Grid with terrain_height; larger than the grass so the mist hides the edge."""
    xs = np.linspace(-size / 2, size / 2, res + 1)
    gx, gy = np.meshgrid(xs, xs)
    gz = terrain_height(gx, gy)
    verts = np.stack([gx, gy, gz], -1).reshape(-1, 3)
    faces = []
    for j in range(res):
        for i in range(res):
            a = j * (res + 1) + i
            faces.append((a, a + 1, a + res + 2, a + res + 1))
    me = bpy.data.meshes.new("Terreno")
    me.from_pydata(verts.tolist(), [], faces)
    for p in me.polygons:
        p.use_smooth = True
    me.update()
    ob = bpy.data.objects.new("Terreno", me)
    scene.objects.link(ob)
    me.materials.append(mat)
    ob.game.physics_type = 'STATIC'
    ob.game.use_collision_bounds = True
    ob.game.collision_bounds_type = 'TRIANGLE_MESH'
    return ob


def grass_chunk(name, x0, y0, size, mat, rnd):
    """Blades as 5-vertex strips (quad + tip triangle). UV: u = random per blade, v = height fraction."""
    n = int(size * size * DENSITY)
    bx = x0 + rnd.random(n) * size
    by = y0 + rnd.random(n) * size
    bz = terrain_height(bx, by)
    hgt = GRASS_H * (0.55 + 0.45 * rnd.random(n) ** 0.7)
    ang = rnd.random(n) * math.pi
    w = 0.018 + 0.016 * rnd.random(n)               # half width at the root
    lean_a = rnd.random(n) * 2 * math.pi
    lean = 0.06 + 0.16 * rnd.random(n)              # tips droop outwards a bit: fluffy look
    cx, cy = np.cos(ang) * w, np.sin(ang) * w
    lx, ly = np.cos(lean_a) * lean, np.sin(lean_a) * lean
    v = np.empty((n, 5, 3), dtype=np.float32)
    v[:, 0] = np.stack([bx - cx, by - cy, bz], -1)
    v[:, 1] = np.stack([bx + cx, by + cy, bz], -1)
    m = 0.55                                        # mid row at 55% height, 70% width
    v[:, 2] = np.stack([bx + cx * 0.7 + lx * m * m, by + cy * 0.7 + ly * m * m, bz + hgt * m], -1)
    v[:, 3] = np.stack([bx - cx * 0.7 + lx * m * m, by - cy * 0.7 + ly * m * m, bz + hgt * m], -1)
    v[:, 4] = np.stack([bx + lx, by + ly, bz + hgt], -1)
    base = (np.arange(n) * 5)[:, None]
    quads = base + np.array([0, 1, 2, 3])
    tris = base + np.array([3, 2, 4])

    me = bpy.data.meshes.new(name)
    me.vertices.add(n * 5)
    me.vertices.foreach_set("co", v.ravel())
    nloops = n * 7
    me.loops.add(nloops)
    loops = np.concatenate([quads, tris], 1).ravel()
    me.loops.foreach_set("vertex_index", loops.astype(np.int32))
    me.polygons.add(n * 2)
    starts = (np.arange(n) * 7)[:, None] + np.array([0, 4])
    totals = np.tile(np.array([4, 3]), (n, 1))
    me.polygons.foreach_set("loop_start", starts.ravel().astype(np.int32))
    me.polygons.foreach_set("loop_total", totals.ravel().astype(np.int32))
    me.update(calc_edges=True)
    me.uv_textures.new("UVMap")
    u = rnd.random(n)
    fr = hgt / GRASS_H                               # taller blades -> lighter tips
    vv = np.stack([np.zeros(n), np.zeros(n), m * fr, m * fr, m * fr, m * fr, fr], 1)
    uvs = np.stack([np.repeat(u[:, None], 7, 1), vv], -1).astype(np.float32)
    me.uv_layers[0].data.foreach_set("uv", uvs.ravel())
    me.validate()
    ob = bpy.data.objects.new(name, me)
    scene.objects.link(ob)
    me.materials.append(mat)
    ob.game.physics_type = 'NO_COLLISION'
    return ob, n


# ---------------------------------------------------------------- game logic

LOGIC = r'''"""Ball control, follow camera and the trail texture (numpy -> Range.texture)."""
import math
import numpy as np
import Range
from Range import logic, events, texture
from mathutils import Vector, Euler

TAM = %(size).1f        # metros cobertos pela textura (igual TAM_TRILHA no shader)
RES = %(res)d
RAIO = 0.95             # raio da marca da bola na grama (m)
RECUPERA = 18.0         # segundos para a grama levantar de todo
SEGURA = 4.0            # segundos totalmente deitada antes de comecar a levantar
FORCA_BOLA = 14.0       # forca das setas/WASD


def _init(own):
    g = own
    scn = logic.getCurrentScene()
    chunk = [o for o in scn.objects if o.name.startswith("Grama.")][0]
    g["tex"] = None if g.get("skip") else texture.Texture(chunk, 0, 0)
    if g["tex"]: g["tex"].mipmap = False
    g["buf"] = texture.ImageBuff()
    g["amt"] = np.zeros((RES, RES), np.float32)
    g["dir"] = np.zeros((RES, RES, 2), np.float32)
    g["dir"][..., 0] = 1.0
    g["rgb"] = np.zeros((RES, RES, 3), np.uint8)
    g["yaw"] = 0.0
    g["t0"] = logic.getRealTime()
    g["frames"] = 0
    g["ok"] = True


def _paint(own, dt):
    if own.get("skip"): return
    amt, dirs = own["amt"], own["dir"]
    amt -= dt / RECUPERA                                      # a grama levanta devagar
    np.maximum(amt, 0.0, out=amt)
    x, y, z = own.worldPosition
    ground = %(hfun)s
    if z - ground < 0.5 + 0.35:                               # so amassa encostando no chao
        texel = TAM / RES
        cx, cy = (x / TAM + 0.5) * RES, (y / TAM + 0.5) * RES
        r = RAIO / texel + 1.0
        i0, i1 = max(int(cx - r), 0), min(int(cx + r) + 2, RES)
        j0, j1 = max(int(cy - r), 0), min(int(cy + r) + 2, RES)
        if i0 < i1 and j0 < j1:
            ii, jj = np.meshgrid(np.arange(i0, i1) + 0.5 - cx, np.arange(j0, j1) + 0.5 - cy)
            d = np.sqrt(ii * ii + jj * jj) * texel / RAIO        # 0 centro, 1 borda
            f = np.clip(1.25 - d * d, 0.0, 1.0) * (1.0 + SEGURA / RECUPERA)
            vx, vy = own.worldLinearVelocity.x, own.worldLinearVelocity.y
            sp = math.hypot(vx, vy)
            mv = np.array([vx, vy]) / sp if sp > 0.3 else np.zeros(2)
            # deita na direcao do movimento e para fora do centro da trilha
            rad = np.stack([ii, jj], -1) / (np.sqrt(ii * ii + jj * jj)[..., None] + 1e-3)
            nd = mv * 0.8 + rad * 0.7
            nd /= np.linalg.norm(nd, axis=-1, keepdims=True) + 1e-4
            win = amt[j0:j1, i0:i1]
            new = f > win
            win[new] = f[new]
            dirs[j0:j1, i0:i1][new] = nd[new]
    rgb = own["rgb"]
    rgb[..., 0] = (np.minimum(amt, 1.0) * 255).astype(np.uint8)
    rgb[..., 1:] = ((dirs * 0.5 + 0.5) * 255).astype(np.uint8)
    own["buf"].load(rgb.tobytes(), RES, RES)
    own["tex"].source = own["buf"]
    own["tex"].refresh(False)


def _auto_path(t):
    """S path used by --shot (x, y)."""
    return -12.0 + t * 2.6, 5.0 * math.sin(t * 0.55)


def bola(cont):
    own = cont.owner
    if "ok" not in own:
        _init(own)
    now = logic.getRealTime()
    dt = min(now - own.get("last", now), 0.1)
    own["last"] = now
    own["frames"] += 1
    kb = logic.keyboard.inputs
    cam = logic.getCurrentScene().active_camera

    if own.get("auto"):                                       # --shot: caminho em S
        t = now - own["t0"]
        vz = own.worldLinearVelocity.z
        if t < 9.0:
            tx, ty = _auto_path(t + 0.4)
            px, py = own.worldPosition.x, own.worldPosition.y
            own.worldLinearVelocity = ((tx - px) * 3.0, (ty - py) * 3.0, vz)
            _camera(own, cam, dt)
        else:
            own.worldLinearVelocity = (0.0, 0.0, vz)
            cam.worldPosition = (16.0, -14.0, 5.0)            # vista geral da trilha
            look = Vector((0.0, 1.0, 0.0)) - cam.worldPosition
            cam.alignAxisToVect(-look, 2, 1.0)
            cam.alignAxisToVect((0.0, 0.0, 1.0), 1, 1.0)
            cam.alignAxisToVect(-look, 2, 1.0)
        _paint(own, dt)
        if t > 8.6 and "s0" not in own:
            own["s0"] = 1
            Range.render.makeScreenshot(logic.expandPath("//" + own["shot0"]))
        if t > 9.2 and "s1" not in own:
            own["s1"] = now
            Range.render.makeScreenshot(logic.expandPath("//" + own["shot1"]))
        if "s1" in own and "s2" not in own and now - own["s1"] > 0.25:
            own["s2"] = 1
            Range.render.makeScreenshot(logic.expandPath("//" + own["shot2"]))
            msg = "GRAMA_FPS media %%.1f (%%d frames em %%.1f s)" %% (own["frames"] / t, own["frames"], t)
            print(msg)
            open(logic.expandPath("//grama_fps.txt"), "w").write(msg + "\n")
        if "s2" in own and now - own["s1"] > 0.6:
            logic.endGame()
        return

    # setas/WASD relativas a camera
    fx = fy = 0.0
    act = lambda *ks: any(kb[k].active for k in ks)
    if act(events.UPARROWKEY, events.WKEY): fy += 1.0
    if act(events.DOWNARROWKEY, events.SKEY): fy -= 1.0
    if act(events.RIGHTARROWKEY, events.DKEY): fx += 1.0
    if act(events.LEFTARROWKEY, events.AKEY): fx -= 1.0
    yaw = own["yaw"]
    fwd = (-math.sin(yaw), math.cos(yaw))
    right = (fwd[1], -fwd[0])
    own.applyForce((FORCA_BOLA * (fwd[0] * fy + right[0] * fx),
                    FORCA_BOLA * (fwd[1] * fy + right[1] * fx), 0.0), False)
    _paint(own, dt)
    _camera(own, cam, dt)


def _camera(own, cam, dt):
    """Camera atras da bola, virando devagar para a direcao do movimento."""
    v = own.worldLinearVelocity
    if math.hypot(v.x, v.y) > 1.0:
        want = math.atan2(-v.x, v.y)
        diff = (want - own["yaw"] + math.pi) %% (2 * math.pi) - math.pi
        own["yaw"] += diff * min(dt * 1.5, 1.0)
    yaw = own["yaw"]
    p = own.worldPosition
    cx, cy = p.x + math.sin(yaw) * 7.0, p.y - math.cos(yaw) * 7.0
    gz = %(hfun_cam)s
    cz = max(p.z + 2.8, gz + 1.5)
    cam.worldPosition = cam.worldPosition.lerp(Vector((cx, cy, cz)), min(dt * 4.0, 1.0))
    look = p - cam.worldPosition
    look.z += 0.6
    cam.alignAxisToVect(-look, 2, 1.0)
    cam.alignAxisToVect((0.0, 0.0, 1.0), 1, 1.0)
    cam.alignAxisToVect(-look, 2, 1.0)
'''

HFUN = ("1.1 * math.sin(%(x)s * 0.13 + 0.5) * math.cos(%(y)s * 0.11)"
        " + 0.6 * math.sin(%(x)s * 0.07 - %(y)s * 0.09 + 1.3)"
        " + 0.18 * math.sin(%(x)s * 0.31 + %(y)s * 0.23)")


# ---------------------------------------------------------------- scene

trail = trail_image()
gmat = grass_material(trail)
terrain(ground_material())

rnd = np.random.default_rng(7)
csize = TRAIL_SIZE / CHUNKS
total = 0
for j in range(CHUNKS):
    for i in range(CHUNKS):
        _, n = grass_chunk("Grama.%02d" % (j * CHUNKS + i), -TRAIL_SIZE / 2 + i * csize,
                           -TRAIL_SIZE / 2 + j * csize, csize, gmat, rnd)
        total += n
print("GRASS blades", total)

start = (-12.0, 0.0)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, size=0.5,
                                     location=(start[0], start[1], float(terrain_height(*start)) + 0.8))
ball = bpy.context.object
ball.name = "Bola"
bpy.ops.object.shade_smooth()
ball.data.materials.append(ball_material())
ball.game.physics_type = 'RIGID_BODY'
ball.game.use_collision_bounds = True
ball.game.collision_bounds_type = 'SPHERE'
ball.game.radius = 0.5                  # sphere bounds use this, not the mesh size
ball.game.mass = 1.0
ball.game.damping = 0.15
ball.game.rotation_damping = 0.2

text = bpy.data.texts.new("grama_logica.py")
text.write(LOGIC % {"size": TRAIL_SIZE, "res": TRAIL_RES,
                    "hfun": HFUN % {"x": "x", "y": "y"},
                    "hfun_cam": HFUN % {"x": "cx", "y": "cy"}})
scene.objects.active = ball
bpy.ops.logic.sensor_add(type='ALWAYS', object=ball.name)
bpy.ops.logic.controller_add(type='PYTHON', object=ball.name)
ball.game.sensors[-1].use_pulse_true_level = True
ctrl = ball.game.controllers[-1]
ctrl.mode = 'MODULE'
ctrl.module = "grama_logica.bola"
ball.game.sensors[-1].link(ctrl)
if want_shot:
    for name, val in (("auto", True), ("shot0", os.path.basename(base) + "_follow.png"), ("shot1", os.path.basename(base) + "_game.png"),
                      ("shot2", os.path.basename(base) + "_game2.png")):
        bpy.ops.object.game_property_new(type='BOOL' if val is True else 'STRING', name=name)
        ball.game.properties[name].value = val

bpy.ops.object.lamp_add(type='SUN', location=(0.0, -10.0, 20.0),
                        rotation=(math.radians(50), 0.0, math.radians(200)))
sun = bpy.context.object
sun.data.energy = 1.8
sun.data.color = (1.0, 0.95, 0.85)
sun.data.shadow_method = 'RAY_SHADOW'
sun.data.shadow_buffer_bias = 0.1
sun.data.shadow_frustum_size = 30.0
sun.data.shadow_buffer_soft = 3.0

bpy.ops.object.camera_add(location=(start[0], start[1] - 6.0, 3.5), rotation=(math.radians(75), 0.0, 0.0))
cam = bpy.context.object
cam.data.clip_end = 200.0
cam.data.lens = 30.0
scene.camera = cam

scene.game_settings.show_framerate_profile = False
scene.game_settings.show_debug_properties = False
bpy.ops.wm.save_as_mainfile(filepath=output, compress=True)
print("GRASS_TRAIL_TEST saved", output)
