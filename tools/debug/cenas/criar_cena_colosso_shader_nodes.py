# Cena grandiosa dos nos de vertex/geometry: colosso peludo saindo de um mar revolto, portal de energia,
# aurora e estrelas no ceu (GLSL Script com Time), monolitos de cristal pulsando (campo Geometry),
# ilhas flutuantes com grama e arvores ao vento. Cada arvore de nos fica em frames explicados.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_colosso_shader_nodes.py -- saida.range [captura.png]
import sys
import math
import bpy
from bl_operators.node import shader_preset_group

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = argv[0]
shot_path = argv[1].replace("\\", "/") if len(argv) > 1 else ""

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("World")
world.horizon_color = (0.0, 0.0, 0.02)
world.mist_settings.use_mist = False
scene.world = world

FRAME_COLORS = {
    'IN': (0.25, 0.35, 0.5),
    'VERTEX': (0.2, 0.45, 0.3),
    'GEOMETRY': (0.5, 0.3, 0.5),
    'COLOR': (0.5, 0.4, 0.2),
    'OUT': (0.45, 0.25, 0.25),
}


def frame(tree, label, kind, nodes):
    """Put the nodes in a labelled, coloured frame."""
    fr = tree.nodes.new("NodeFrame")
    fr.label = label
    fr.use_custom_color = True
    fr.color = FRAME_COLORS[kind]
    fr.label_size = 16
    for node in nodes:
        node.parent = fr
    return fr


VERTEX_NODES = {"ShaderNodeVertexWave", "ShaderNodeVertexWind", "ShaderNodeVertexOffset"}
GEOMETRY_NODES = {"ShaderNodeFurShells", "ShaderNodeOutline", "ShaderNodeShellLayer"}
GROUP_NOTES = {
    'VERTEX': "Vertice: desloca a malha (roda no vertex shader)",
    'GEOMETRY': "Geometria: cria as camadas / o casco (geometry shader)",
    'COLOR': "Cor: mistura as cores (fragment shader)",
}


def frame_group(group):
    """Split a preset group in frames: inputs, vertex, geometry, colour, output."""
    if any(n.bl_idname == "NodeFrame" for n in group.nodes):
        return
    parts = {'IN': [], 'VERTEX': [], 'GEOMETRY': [], 'COLOR': [], 'OUT': []}
    for node in group.nodes:
        if node.bl_idname == "NodeGroupInput":
            parts['IN'].append(node)
        elif node.bl_idname == "NodeGroupOutput":
            parts['OUT'].append(node)
        elif node.bl_idname in VERTEX_NODES:
            parts['VERTEX'].append(node)
        elif node.bl_idname in GEOMETRY_NODES:
            parts['GEOMETRY'].append(node)
        else:
            parts['COLOR'].append(node)
    # one column per part, so the frames never overlap
    x = 0.0
    for kind in ('IN', 'VERTEX', 'GEOMETRY', 'COLOR', 'OUT'):
        nodes = parts[kind]
        if not nodes:
            continue
        if kind == 'COLOR':
            # keep the relative layout of the colour chain, shifted to this column
            min_x = min(n.location.x for n in nodes)
            max_x = max(n.location.x for n in nodes)
            for n in nodes:
                n.location.x = x + (n.location.x - min_x)
            width = (max_x - min_x) + 220.0
        else:
            for i, n in enumerate(nodes):
                n.location = (x, -i * 260.0)
            width = 220.0
        label = {'IN': "Entradas: valores que aparecem no no do grupo",
                 'OUT': "Saida: o que o grupo entrega ao material"}.get(kind) or GROUP_NOTES[kind]
        frame(group, label, kind, nodes)
        x += width + 120.0


def node_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (700, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    bsdf.inputs["Base Color"].default_value = color
    tree.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat, tree, out, bsdf


def finish_material(tree, out, bsdf, out_note="3. Saida do material"):
    frame(tree, "2. Luz: Principled recebe a cor e calcula a iluminacao", 'COLOR', [bsdf])
    frame(tree, out_note, 'OUT', [out])


def preset_material(name, preset, note, values=None, clip=False):
    mat, tree, out, bsdf = node_material(name, (1, 1, 1, 1))
    g = tree.nodes.new("ShaderNodeGroup")
    g.node_tree = shader_preset_group(preset)
    g.location = (-150, 0)
    g.width = 220
    frame_group(g.node_tree)
    for key, value in (values or {}).items():
        g.inputs[key].default_value = value
    tree.links.new(g.outputs["Color"], bsdf.inputs["Base Color"])
    out_note = "3. Saida do material"
    if "Offset" in g.outputs:
        tree.links.new(g.outputs["Offset"], out.inputs["Vertex Offset"])
        out_note = "3. Saida: Surface = cor e luz, Vertex Offset = deslocamento da malha"
    if clip:
        mat.game_settings.alpha_blend = 'CLIP'
    frame(tree, note, 'GEOMETRY' if "Offset" not in g.outputs else 'VERTEX', [g])
    finish_material(tree, out, bsdf, out_note)
    if "Alpha" in g.outputs:
        # Alpha cuts the pixels between the strands: Transparent where Alpha is 0, Principled where it is 1.
        transp = tree.nodes.new("ShaderNodeBsdfTransparent")
        transp.location = (300, 250)
        mix = tree.nodes.new("ShaderNodeMixShader")
        mix.location = (520, 250)
        out.location = (760, 250)
        tree.links.new(g.outputs["Alpha"], mix.inputs[0])
        tree.links.new(transp.outputs[0], mix.inputs[1])
        tree.links.new(bsdf.outputs[0], mix.inputs[2])
        tree.links.new(mix.outputs[0], out.inputs["Surface"])
        frame(tree, "2b. Recorte: Alpha do preset escolhe entre transparente e a cor (fios separados)",
              'IN', [transp, mix])
    return mat


def mesh(op, name, loc, mat, scale=(1, 1, 1), **kw):
    op(location=loc, **kw)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    # Fur Shells spreads the strands by UV cell, so every mesh gets an UV map.
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    ob.data.materials.append(mat)
    return ob


def copy_group(mat, **fur):
    """Give the material its own copy of the preset group and set its Fur Shells node."""
    for node in mat.node_tree.nodes:
        if node.bl_idname == "ShaderNodeGroup":
            node.node_tree = node.node_tree.copy()
            for inner in node.node_tree.nodes:
                if inner.bl_idname == "ShaderNodeFurShells":
                    for key, value in fur.items():
                        inner.inputs[key].default_value = value


def script_node(tree, name, code, location):
    txt = bpy.data.texts.new(name)
    txt.from_string(code)
    node = tree.nodes.new("ShaderNodeGLSLScript")
    node.script = txt
    try:
        node.update()
    except Exception as e:
        print("update()", e)
    tree.update_tag()
    node.location = location
    node.width = 220
    return node


def glow_material(name, code, note, strength=1.0, space="Object"):
    """Emission driven by a GLSL Script that receives the position and the time."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    coord = tree.nodes.new("ShaderNodeTexCoord")
    coord.location = (-600, 100)
    time = tree.nodes.new("ShaderNodeTime")
    time.location = (-600, -250)
    script = script_node(tree, name.lower() + ".glsl", code, (-250, 0))
    emit = tree.nodes.new("ShaderNodeEmission")
    emit.location = (150, 0)
    emit.inputs["Strength"].default_value = strength
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (450, 0)
    tree.links.new(coord.outputs[space], script.inputs["Vector"])
    tree.links.new(time.outputs["Time"], script.inputs["Time"])
    tree.links.new(script.outputs["Color"], emit.inputs["Color"])
    tree.links.new(emit.outputs[0], out.inputs["Surface"])
    frame(tree, "0. Entradas: posicao do ponto e tempo do jogo", 'IN', [coord, time])
    frame(tree, note, 'GEOMETRY', [script])
    frame(tree, "2. Emission: a cor do script vira luz propria (nao depende das lampadas)", 'COLOR', [emit])
    frame(tree, "3. Saida do material", 'OUT', [out])
    return mat


# ---------------------------------------------------------------- sky: aurora + stars
sky = glow_material("Sky", """// Ceu: degrade noturno, brilho no horizonte, cortinas de aurora e estrelas.
void main(vec3 Vector, float Time, out vec4 Color)
{
    vec3 d = normalize(Vector);
    float h = d.z;
    float a = atan(d.y, d.x);
    vec3 sky = mix(vec3(0.03, 0.04, 0.10), vec3(0.0, 0.0, 0.02), clamp(h * 1.5, 0.0, 1.0));
    sky += vec3(0.45, 0.12, 0.30) * pow(1.0 - abs(h), 7.0);
    float band = sin(a * 5.0 + Time * 0.25 + sin(a * 11.0 - Time * 0.4) * 0.9);
    float curtain = smoothstep(0.1, 1.0, band) * smoothstep(0.04, 0.22, h) * (1.0 - smoothstep(0.30, 0.85, h));
    float rays = 0.55 + 0.45 * sin(a * 110.0 + Time * 1.5 + sin(h * 20.0));
    vec3 aurora = mix(vec3(0.1, 1.0, 0.5), vec3(0.6, 0.2, 1.0), clamp(h * 2.0, 0.0, 1.0)) * curtain * rays * 1.6;
    vec3 cell = floor(d * 260.0);
    float r = fract(sin(dot(cell, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
    float star = step(0.9982, r) * step(0.02, h) * (0.6 + 0.4 * sin(Time * 3.0 + r * 500.0));
    Color = vec4(sky + aurora + vec3(star), 1.0);
}
""", "1. GLSL Script (sky.glsl): ceu noturno, aurora animada e estrelas piscando")
bpy.ops.mesh.primitive_uv_sphere_add(location=(0, 0, 0), size=600, segments=64, ring_count=32)
dome = bpy.context.active_object
dome.name = "Sky"
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.flip_normals()
bpy.ops.object.mode_set(mode='OBJECT')
dome.data.materials.append(sky)

# ---------------------------------------------------------------- stormy sea
def lit_glow_material(name, code, note, roughness, metallic, strength):
    """Principled lit by the lamps + Emission, both coloured by one GLSL Script (outputs Color and Glow)."""
    mat, tree, out, bsdf = node_material(name, (1, 1, 1, 1))
    coord = tree.nodes.new("ShaderNodeTexCoord")
    coord.location = (-600, 100)
    time = tree.nodes.new("ShaderNodeTime")
    time.location = (-600, -250)
    script = script_node(tree, name.lower() + ".glsl", code, (-250, 0))
    emit = tree.nodes.new("ShaderNodeEmission")
    emit.location = (300, -420)
    emit.inputs["Strength"].default_value = strength
    add = tree.nodes.new("ShaderNodeAddShader")
    add.location = (560, 0)
    out.location = (800, 0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    tree.links.new(coord.outputs["Object"], script.inputs["Vector"])
    if "Reflection" in script.inputs:
        # world-space mirror direction of the view ray, used to ray trace the reflection in the script
        tree.links.new(coord.outputs["Reflection"], script.inputs["Reflection"])
    tree.links.new(time.outputs["Time"], script.inputs["Time"])
    tree.links.new(script.outputs["Color"], bsdf.inputs["Base Color"])
    tree.links.new(script.outputs["Glow"], emit.inputs["Color"])
    tree.links.new(bsdf.outputs[0], add.inputs[0])
    tree.links.new(emit.outputs[0], add.inputs[1])
    tree.links.new(add.outputs[0], out.inputs["Surface"])
    frame(tree, "0. Entradas: posicao do ponto, direcao do reflexo (Reflection) e tempo", 'IN', [coord, time])
    frame(tree, note, 'GEOMETRY', [script])
    frame(tree, "2. Luz: Color vai para o Principled (lampadas), Glow vira brilho proprio (Emission)", 'COLOR',
          [bsdf, emit, add])
    return mat, tree, out


sea, tree, out = lit_glow_material("Sea", """// Mar: cor por ondulacao, espuma em volta do colosso e REFLEXO do ceu, do portal e do colosso.
// O reflexo e calculado aqui mesmo: o raio refletido (entrada Reflection) e testado contra as
// formas da cena (esferas do colosso e dos olhos, plano do portal) e, se nao bater em nada, pega o ceu.
void main(vec3 Vector, vec3 Reflection, float Time, out vec4 Color, out vec4 Glow)
{
    vec2 p = Vector.xy;
    float d = length(p);
    // ondulacao larga (escolhe entre fundo escuro e agua clara)
    float w = sin(p.x * 0.35 + Time * 1.3) + sin(p.y * 0.42 - Time * 1.1)
            + sin((p.x + p.y) * 0.21 + Time * 0.7) + sin(d * 0.5 - Time * 2.0) * 0.6;
    float fine = sin(p.x * 0.9 + p.y * 0.35 + w * 2.2 + Time * 1.5);
    float fine2 = sin(p.y * 1.3 - p.x * 0.3 - w * 1.7 - Time * 1.2);
    float crest = pow(max(fine, 0.0), 14.0) * 0.7 + pow(max(fine2, 0.0), 20.0) * 0.5;
    vec3 c = mix(vec3(0.0, 0.015, 0.05), vec3(0.0, 0.13, 0.20), clamp(w * 0.2 + 0.45, 0.0, 1.0));
    // espuma: aneis que se afastam do colosso
    float a = atan(p.y, p.x);
    float rings = sin(d * 0.9 - Time * 2.5 + sin(a * 5.0) * 0.8) * 0.5 + 0.5;
    float foam = smoothstep(0.75, 1.0, rings) * (1.0 - smoothstep(13.0, 40.0, d)) * (0.6 + 0.4 * fine);
    foam += (1.0 - smoothstep(0.0, 2.5, abs(d - 13.5 - sin(a * 7.0 + Time) * 1.2))) * 0.8;
    foam = clamp(foam, 0.0, 1.0);

    // ---- reflexo
    // inclinacao das ondas entorta o raio refletido (reflexo tremido)
    vec2 slope = vec2(cos(p.x * 0.35 + Time * 1.3) * 0.35 + cos((p.x + p.y) * 0.21 + Time * 0.7) * 0.21,
                      -cos(p.y * 0.42 - Time * 1.1) * 0.42 + cos((p.x + p.y) * 0.21 + Time * 0.7) * 0.21) * 0.07;
    slope += vec2(cos(p.x * 1.9 + Time * 2.0), cos(p.y * 2.3 - Time * 1.7)) * 0.012;
    vec3 R = normalize(Reflection);
    float facing = clamp(R.z, 0.0, 1.0);                 // 0 = olhando rente a agua, 1 = de cima
    R = normalize(vec3(R.xy - slope, abs(R.z) + 0.03));
    vec3 P = vec3(p, 0.0);

    // ceu (o mesmo desenho de sky.glsl, sem estrelas)
    float h = R.z;
    float ra = atan(R.y, R.x);
    vec3 refl = mix(vec3(0.03, 0.04, 0.10), vec3(0.0, 0.0, 0.02), clamp(h * 1.5, 0.0, 1.0));
    refl += vec3(0.45, 0.12, 0.30) * pow(1.0 - abs(h), 7.0);
    float band = sin(ra * 5.0 + Time * 0.25 + sin(ra * 11.0 - Time * 0.4) * 0.9);
    float curtain = smoothstep(0.1, 1.0, band) * smoothstep(0.04, 0.22, h) * (1.0 - smoothstep(0.30, 0.85, h));
    float rays = 0.55 + 0.45 * sin(ra * 110.0 + Time * 1.5 + sin(h * 20.0));
    refl += mix(vec3(0.1, 1.0, 0.5), vec3(0.6, 0.2, 1.0), clamp(h * 2.0, 0.0, 1.0)) * curtain * rays * 1.6;

    // portal: plano em y = 55.5, centro na altura 20
    if (R.y > 0.001) {
        float t = (55.5 - P.y) / R.y;
        vec3 hit = P + R * t;
        vec2 q = vec2(hit.x, hit.z - 20.0);
        float qr = length(q);
        float qa = atan(q.y, q.x);
        if (qr < 35.0) {
            float r = qr / 35.0;
            float swirl = sin(qa * 4.0 + r * 16.0 - Time * 1.5) * 0.5 + 0.5;
            vec3 pc = mix(vec3(0.10, 0.0, 0.25), vec3(0.2, 0.9, 1.0), pow(swirl, 3.0));
            pc += vec3(1.0, 0.8, 0.9) * pow(1.0 - r, 4.0) * 2.0;
            refl = pc * (1.0 - smoothstep(0.85, 1.0, r) * 0.7);
        }
        else if (qr < 37.8) {
            float an = qa / 6.2831;
            vec3 rc = 0.5 + 0.5 * cos(6.2831 * (an * 3.0 - Time * 0.12 + vec3(0.0, 0.33, 0.67)));
            refl = rc * (0.55 + 0.45 * sin(an * 6.2831 * 28.0 - Time * 5.0)) * 4.0;
        }
    }

    // colosso: esfera aproximando a cabeca (fica na frente do portal)
    vec3 oc = P - vec3(0.0, 0.0, 8.0);
    float bq = dot(oc, R);
    float disc = bq * bq - (dot(oc, oc) - 12.5 * 12.5);
    if (disc > 0.0 && -bq - sqrt(disc) > 0.0) {
        vec3 n = (oc + R * (-bq - sqrt(disc))) / 12.5;
        float shade = 0.25 + 0.75 * max(dot(n, vec3(-0.37, -0.78, 0.5)), 0.0);
        refl = vec3(0.35, 0.60, 0.85) * shade;
    }
    // olhos: duas esferas de brasa
    for (int i = 0; i < 2; i++) {
        vec3 oe = P - vec3(i == 0 ? -4.75 : 4.75, -11.1, 10.5);
        float be = dot(oe, R);
        float de = be * be - (dot(oe, oe) - 4.0);
        if (de > 0.0 && -be - sqrt(de) > 0.0)
            refl = vec3(1.0, 0.75, 0.2) * 3.0 * (0.75 + 0.25 * sin(Time * 3.0));
    }

    // Fresnel: rente a agua reflete quase tudo, de cima deixa ver a cor da agua
    float fres = mix(0.10, 1.0, pow(1.0 - facing, 3.0));
    c = mix(c, vec3(0.75, 0.95, 1.0), foam * 0.85);
    vec3 glow = refl * fres * 0.75 * (1.0 - foam * 0.8);
    glow += vec3(0.1, 0.8, 0.5) * crest * 0.15;
    Color = vec4(c * (1.0 - fres * 0.7), 1.0);
    Glow = vec4(glow, 1.0);
}
""", "1. GLSL Script (sea.glsl): cor, espuma e reflexo do ceu, portal e colosso. Saidas: Color e Glow",
                                roughness=0.22, metallic=0.0, strength=1.0)
waves = tree.nodes.new("ShaderNodeGroup")
waves.node_tree = shader_preset_group('WATER_WAVES')
frame_group(waves.node_tree)
waves.location = (300, -750)
waves.width = 220
waves.inputs["Amplitude"].default_value = 0.32
waves.inputs["Wavelength"].default_value = 17.0
waves.inputs["Speed"].default_value = 1.6
ripple = tree.nodes.new("ShaderNodeVertexWave")
ripple.location = (300, -1050)
ripple.inputs["Amplitude"].default_value = 0.08
ripple.inputs["Wavelength"].default_value = 5.0
ripple.inputs["Speed"].default_value = 2.6
ripple.inputs["Direction"].default_value = (-0.6, 0.8, 0.0)
vadd = tree.nodes.new("ShaderNodeVectorMath")
vadd.operation = 'ADD'
vadd.location = (580, -850)
tree.links.new(waves.outputs["Offset"], vadd.inputs[0])
tree.links.new(ripple.outputs["Offset"], vadd.inputs[1])
tree.links.new(vadd.outputs["Vector"], out.inputs["Vertex Offset"])
frame(tree, "1b. Ondas na malha: preset Water Waves (grandes) + Wave (marolas), somadas -> Vertex Offset",
      'VERTEX', [waves, ripple, vadd])
frame(tree, "3. Saida: Surface = cor e luz, Vertex Offset = deslocamento da malha", 'OUT', [out])
mesh(bpy.ops.mesh.primitive_grid_add, "Sea", (0, 0, 0), sea, x_subdivisions=300, y_subdivisions=300, radius=260)

# ---------------------------------------------------------------- the colossus
fur = preset_material("ColossusFur", 'FUR',
                      "1. Preset Fur (copia so deste material): pelo longo em 24 camadas (Tab abre o grupo)",
                      {"Root Color": (0.05, 0.10, 0.35, 1.0), "Tip Color": (0.6, 0.95, 1.0, 1.0)}, clip=True)
copy_group(fur, Length=0.9, Layers=24, Density=520.0)
colosso = mesh(bpy.ops.mesh.primitive_monkey_add, "Colosso", (0, 0, 7.0), fur, scale=(14, 14, 14))
bpy.ops.object.modifier_add(type='SUBSURF')
colosso.modifiers[-1].levels = 2
bpy.ops.object.modifier_apply(apply_as='DATA', modifier=colosso.modifiers[-1].name)

eyes = glow_material("Eyes", """// Olhos: brasa pulsando.
void main(vec3 Vector, float Time, out vec4 Color)
{
    float core = 1.0 - clamp(length(Vector.xz) / 2.0, 0.0, 1.0);
    float pulse = 0.75 + 0.25 * sin(Time * 3.0);
    Color = vec4(mix(vec3(1.0, 0.25, 0.0), vec3(1.0, 0.95, 0.5), core) * pulse, 1.0);
}
""", "1. GLSL Script (eyes.glsl): brasa que pulsa com o tempo", strength=3.0)
for x in (-4.75, 4.75):
    bpy.ops.mesh.primitive_uv_sphere_add(location=(x, -11.1, 10.5), size=2.0, segments=24, ring_count=12)
    ob = bpy.context.active_object
    ob.name = "Eye"
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(eyes)

# ---------------------------------------------------------------- portal behind it
ring = glow_material("PortalRing", """// Anel do portal: arco-iris correndo em volta + pulsos rapidos.
void main(vec3 Vector, float Time, out vec4 Color)
{
    float a = atan(Vector.y, Vector.x) / 6.2831;
    vec3 c = 0.5 + 0.5 * cos(6.2831 * (a * 3.0 - Time * 0.12 + vec3(0.0, 0.33, 0.67)));
    float pulse = 0.55 + 0.45 * sin(a * 6.2831 * 28.0 - Time * 5.0);
    Color = vec4(c * pulse * 2.5, 1.0);
}
""", "1. GLSL Script (portalring.glsl): cores correndo pelo anel", strength=2.0)
bpy.ops.mesh.primitive_torus_add(location=(0, 55, 20), rotation=(math.radians(90), 0, 0),
                                 major_radius=36, minor_radius=1.8, major_segments=96, minor_segments=16)
ob = bpy.context.active_object
ob.name = "PortalRing"
bpy.ops.object.shade_smooth()
ob.data.materials.append(ring)

disc = glow_material("PortalDisc", """// Interior do portal: redemoinho que gira e brilha no centro.
void main(vec3 Vector, float Time, out vec4 Color)
{
    float r = length(Vector.xy) / 35.0;
    float a = atan(Vector.y, Vector.x);
    float swirl = sin(a * 4.0 + r * 16.0 - Time * 1.5) * 0.5 + 0.5;
    float arms = pow(swirl, 3.0);
    vec3 c = mix(vec3(0.10, 0.0, 0.25), vec3(0.2, 0.9, 1.0), arms);
    c += vec3(1.0, 0.8, 0.9) * pow(1.0 - clamp(r, 0.0, 1.0), 4.0) * 2.0;
    c *= 1.0 - smoothstep(0.85, 1.0, r) * 0.7;
    Color = vec4(c, 1.0);
}
""", "1. GLSL Script (portaldisc.glsl): redemoinho animado")
bpy.ops.mesh.primitive_circle_add(location=(0, 55.5, 20), rotation=(math.radians(90), 0, 0),
                                  radius=35, vertices=96, fill_type='NGON')
ob = bpy.context.active_object
ob.name = "PortalDisc"
ob.data.materials.append(disc)

# ---------------------------------------------------------------- crystal monoliths
geo = bpy.data.texts.new("crystal_breathe.glsl")
geo.from_string("// Campo Geometry do material: afasta cada triangulo pela normal, pulsando no tempo.\n"
                "layout(triangle_strip, max_vertices = 3) out;\n"
                "void geometry()\n{\n"
                "    vec3 n = normalize(cross(geom_position(1) - geom_position(0), geom_position(2) - geom_position(0)));\n"
                "    float k = 0.6 * (sin(TIME * 1.5) * 0.5 + 0.5);\n"
                "    for (int i = 0; i < 3; i++) geom_emit_offset(i, n * k);\n"
                "    EndPrimitive();\n}\n")
crystal, tree, out, bsdf = node_material("Crystal", (1, 1, 1, 1))
coord = tree.nodes.new("ShaderNodeTexCoord")
coord.location = (-600, 100)
time = tree.nodes.new("ShaderNodeTime")
time.location = (-600, -250)
script = script_node(tree, "crystal.glsl", """// Cristal: faixas de cor subindo pela altura.
void main(vec3 Vector, float Time, out vec4 Color)
{
    float t = Vector.z * 0.06 + Vector.x * 0.05 - Time * 0.15;
    vec3 c = 0.55 + 0.45 * cos(6.2831 * (t + vec3(0.0, 0.33, 0.67)));
    Color = vec4(c, 1.0);
}
""", (-250, 0))
emit = tree.nodes.new("ShaderNodeEmission")
emit.location = (300, -420)
emit.inputs["Strength"].default_value = 0.9
add = tree.nodes.new("ShaderNodeAddShader")
add.location = (560, 0)
out.location = (800, 0)
bsdf.inputs["Roughness"].default_value = 0.1
tree.links.new(coord.outputs["Object"], script.inputs["Vector"])
tree.links.new(time.outputs["Time"], script.inputs["Time"])
tree.links.new(script.outputs["Color"], bsdf.inputs["Base Color"])
tree.links.new(script.outputs["Color"], emit.inputs["Color"])
tree.links.new(bsdf.outputs[0], add.inputs[0])
tree.links.new(emit.outputs[0], add.inputs[1])
tree.links.new(add.outputs[0], out.inputs["Surface"])
crystal.script_geom = geo
frame(tree, "0. Entradas: posicao do ponto e tempo do jogo", 'IN', [coord, time])
frame(tree, "1. GLSL Script (crystal.glsl): faixas de cor que sobem com o tempo", 'GEOMETRY', [script])
frame(tree, "2. Luz: reflexo (Principled) + brilho proprio (Emission), somados", 'COLOR', [bsdf, emit, add])
frame(tree, "3. Saida. As faces pulsando vem do campo Geometry do material (crystal_breathe.glsl)", 'OUT', [out])
for i in range(14):
    ang = i / 14.0 * 2.0 * math.pi
    rad = 62.0 + (i % 3) * 9.0
    h = 16.0 + ((i * 7) % 5) * 5.0
    bpy.ops.mesh.primitive_ico_sphere_add(location=(math.cos(ang) * rad, math.sin(ang) * rad, h * 0.45),
                                          subdivisions=1)
    ob = bpy.context.active_object
    ob.name = "Monolito%d" % i
    ob.scale = (2.6 + (i % 2), 2.6 + (i % 2), h)
    bpy.ops.object.transform_apply(scale=True)
    ob.rotation_euler = (math.sin(i * 1.7) * 0.25, math.cos(i * 2.3) * 0.25, i)
    ob.data.materials.append(crystal)

# ---------------------------------------------------------------- floating islands
OUTLINE_NOTE = "1. Preset Toon Outline: casco preto em volta da malha + cor chapada (Tab abre o grupo)"
grass = preset_material("Grass", 'GRASS',
                        "1. Preset Grass (copia): camadas pela normal, cor da raiz ate a ponta (Tab abre)",
                        clip=True)
copy_group(grass, Length=0.5, Layers=16, Density=240.0)
rock, tree, out = lit_glow_material("Rock", """// Rocha: camadas de pedra pela altura, musgo perto do topo e veios de cristal que pulsam.
void main(vec3 Vector, float Time, out vec4 Color, out vec4 Glow)
{
    float depth = -Vector.z;                       // 0 no topo da ilha, cresce para baixo
    // camadas (estratos) tortas
    float bend = sin(Vector.x * 0.5) * 0.6 + sin(Vector.y * 0.43 + 1.7) * 0.6;
    float layer = fract(depth * 0.55 + bend * 0.35);
    float band = smoothstep(0.0, 0.12, layer) * (1.0 - smoothstep(0.75, 1.0, layer));
    vec3 stone = mix(vec3(0.16, 0.12, 0.14), vec3(0.42, 0.33, 0.30), band);
    stone *= mix(1.0, 0.45, clamp(depth * 0.08, 0.0, 1.0));     // mais escuro no fundo
    // musgo e terra perto do topo
    float moss = 1.0 - smoothstep(0.3, 2.2 + bend, depth);
    stone = mix(stone, vec3(0.12, 0.30, 0.10), moss * 0.85);
    // veios de cristal
    float v = sin(Vector.x * 0.9 + sin(Vector.z * 1.3) * 2.0) * sin(Vector.y * 0.8 + sin(Vector.x * 1.1) * 2.0);
    float vein = (1.0 - smoothstep(0.0, 0.07, abs(v))) * smoothstep(1.0, 3.0, depth);
    float pulse = 0.55 + 0.45 * sin(Time * 2.0 - depth * 0.8);
    Color = vec4(mix(stone, vec3(0.1, 0.5, 0.6), vein * 0.6), 1.0);
    Glow = vec4(vec3(0.2, 0.95, 1.0) * vein * pulse * 1.6, 1.0);
}
""", "1. GLSL Script (rock.glsl): estratos, musgo no topo e veios de cristal pulsando",
                                roughness=0.85, metallic=0.0, strength=1.0)
frame(tree, "3. Saida do material", 'OUT', [out])

from mathutils import noise, Vector as V


def island_rock(name, loc, r, seed):
    """Craggy rock hanging under an island: flat on top, tapering down in uneven spikes. Flat shaded."""
    bpy.ops.mesh.primitive_ico_sphere_add(location=loc, subdivisions=4, size=1.0)
    ob = bpy.context.active_object
    ob.name = name
    depth = r * 1.5
    for vert in ob.data.vertices:
        x, y, z = vert.co
        n1 = noise.noise(V((x * 1.7 + seed, y * 1.7, z * 1.7)))
        n2 = noise.noise(V((x * 4.5, y * 4.5 + seed, z * 4.5)))
        if z >= 0.0:
            # top: a low dome hidden by the grass
            vert.co = (x * r, y * r, z * r * 0.12)
            continue
        t = -z                                         # 0 at the rim, 1 at the bottom
        radius = (1.0 - t) ** 0.55 * (1.0 + n1 * 0.35 + n2 * 0.12)
        length = math.sqrt(x * x + y * y) or 1.0
        # hanging spikes: some directions go deeper than others
        spike = 0.55 + 0.45 * noise.noise(V((x / length * 2.2 + seed, y / length * 2.2, 0.0)))
        vert.co = (x / length * radius * r * (1.0 - t * 0.15), y / length * radius * r * (1.0 - t * 0.15),
                   -t * depth * (0.55 + spike * 0.6) + n2 * r * 0.06)
    ob.data.update()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    ob.data.materials.append(rock)
    return ob


def debris(name, loc, size, seed):
    """Small rock floating near an island."""
    bpy.ops.mesh.primitive_ico_sphere_add(location=loc, subdivisions=2, size=size)
    ob = bpy.context.active_object
    ob.name = name
    for vert in ob.data.vertices:
        k = 1.0 + noise.noise(V(vert.co) * (1.5 / size) + V((seed, 0.0, 0.0))) * 0.45
        vert.co = vert.co * k
    ob.scale = (1.0, 0.8, 1.4)
    bpy.ops.object.transform_apply(scale=True)
    ob.rotation_euler = (seed, seed * 0.7, seed * 1.3)
    ob.data.materials.append(rock)
    return ob


fall = glow_material("Waterfall", """// Cachoeira: fios de agua descendo, mais largos e brancos na queda.
void main(vec3 Vector, float Time, out vec4 Color)
{
    float fallen = -Vector.z;                       // distancia desde o topo
    float lines = sin(Vector.x * 9.0 + sin(fallen * 0.7) * 1.5) * 0.5 + 0.5;
    float flow = sin(fallen * 1.6 - Time * 9.0 + lines * 4.0) * 0.5 + 0.5;
    float edge = 1.0 - smoothstep(0.55, 1.0, abs(Vector.x) / 1.0);
    vec3 c = mix(vec3(0.15, 0.55, 0.75), vec3(0.9, 1.0, 1.0), flow * lines);
    Color = vec4(c * (0.5 + 0.5 * edge), 1.0);
}
""", "1. GLSL Script (waterfall.glsl): fios de agua correndo para baixo", strength=1.1)


def wind_material(name, color):
    mat = preset_material(name, 'TOON_OUTLINE', OUTLINE_NOTE, {"Color": color})
    tree = mat.node_tree
    wind = tree.nodes.new("ShaderNodeVertexWind")
    wind.location = (-150, -350)
    wind.inputs["Strength"].default_value = 0.35
    wind.inputs["Speed"].default_value = 1.5
    for node in tree.nodes:
        if node.bl_idname == "ShaderNodeOutputMaterial":
            tree.links.new(wind.outputs["Offset"], node.inputs["Vertex Offset"])
    frame(tree, "1b. Vento: balanca os vertices; vai na entrada Vertex Offset da saida", 'VERTEX', [wind])
    return mat


trunk = preset_material("Trunk", 'TOON_OUTLINE', OUTLINE_NOTE, {"Color": (0.3, 0.17, 0.1, 1.0)})
leaves = [wind_material("Leaves%d" % i, c)
          for i, c in enumerate(((0.1, 0.6, 0.45, 1.0), (0.75, 0.25, 0.7, 1.0), (0.95, 0.55, 0.2, 1.0)))]
for i, (x, y, z, r) in enumerate(((-34, -22, 14, 9), (36, -14, 20, 11), (-48, 20, 26, 12), (50, 28, 30, 10),
                                  (-78, -8, 18, 8), (80, -4, 15, 9))):
    island_rock("Rocha%d" % i, (x, y, z - 0.3), r, i * 3.7)
    for k in range(4):
        ang = k * 1.9 + i * 0.8
        debris("Pedra%d_%d" % (i, k), (x + math.cos(ang) * r * (1.15 + 0.12 * k),
                                       y + math.sin(ang) * r * (1.15 + 0.12 * k), z - r * (0.3 + 0.28 * k)),
               r * (0.16 - 0.025 * k), i + k * 2.3)
    if i < 4:
        # waterfall: narrow strip from the island rim down to the sea, facing the colossus
        ang = math.atan2(-y, -x)
        fx, fy = x + math.cos(ang) * r * 0.97, y + math.sin(ang) * r * 0.97
        bpy.ops.mesh.primitive_grid_add(location=(fx, fy, z), x_subdivisions=4, y_subdivisions=40, radius=1.0)
        ob = bpy.context.active_object
        ob.name = "Cachoeira%d" % i
        for vert in ob.data.vertices:
            # local x = width (-1..1), local z = 0 at the top and -height at the sea
            vert.co = (vert.co.x * (1.0 + (1.0 - vert.co.y) * 0.25), 0.0, (vert.co.y - 1.0) * 0.5 * (z + 0.6))
        ob.data.update()
        ob.rotation_euler = (0.0, 0.0, ang + math.pi * 0.5)
        ob.data.materials.append(fall)
        fall.game_settings.use_backface_culling = False
    mesh(bpy.ops.mesh.primitive_uv_sphere_add, "Topo%d" % i, (x, y, z - 0.2), grass,
         scale=(r * 0.98, r * 0.98, r * 0.16), segments=32, ring_count=16)
    for k in range(3):
        ang = k * 2.1 + i
        tx, ty = x + math.cos(ang) * r * 0.45, y + math.sin(ang) * r * 0.45
        h = r * (0.35 + 0.1 * k)
        mesh(bpy.ops.mesh.primitive_cylinder_add, "Tronco%d_%d" % (i, k), (tx, ty, z + h * 0.5), trunk,
             scale=(0.1 * h, 0.1 * h, h * 0.5), vertices=10)
        for j in range(3):
            rr = (0.7 - j * 0.18) * h
            mesh(bpy.ops.mesh.primitive_cone_add, "Copa%d_%d_%d" % (i, k, j), (tx, ty, z + h * (1.0 + j * 0.45)),
                 leaves[(i + k) % len(leaves)], scale=(rr, rr, h * 0.45), vertices=14)

# ---------------------------------------------------------------- lights
lamp = bpy.data.lamps.new("Moon", 'SUN')
lamp.color = (0.55, 0.7, 1.0)
lamp.energy = 1.8
moon = bpy.data.objects.new("Moon", lamp)
scene.objects.link(moon)
moon.rotation_euler = (math.radians(60), 0.0, math.radians(-25))
back = bpy.data.lamps.new("PortalLight", 'SUN')
back.color = (0.5, 0.9, 1.0)
back.energy = 0.9
bo = bpy.data.objects.new("PortalLight", back)
scene.objects.link(bo)
bo.rotation_euler = (math.radians(-75), 0.0, 0.0)
fill = bpy.data.lamps.new("Fill", 'HEMI')
fill.color = (0.5, 0.3, 0.8)
fill.energy = 0.6
fo = bpy.data.objects.new("Fill", fill)
scene.objects.link(fo)

# ---------------------------------------------------------------- camera swinging in front of the colossus
pivot = bpy.data.objects.new("Pivot", None)
scene.objects.link(pivot)
pivot.location = (0, 0, 9)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 20
cam.data.clip_start = 0.5
cam.data.clip_end = 1500
scene.objects.link(cam)
cam.parent = pivot
cam.location = (0, -62, -4.5)
cam.rotation_euler = (math.radians(100), 0, 0)
scene.camera = cam

logic = bpy.data.texts.new("orbit.py")
logic.from_string("import bge, math\n"
                  "SHOT = %r\n"
                  "def tick(cont):\n"
                  "    own = cont.owner\n"
                  "    own['t'] = own.get('t', 0) + 1\n"
                  "    own.worldOrientation = (0.0, 0.0, math.sin(own['t'] * 0.004) * 0.7)\n"
                  "    if SHOT and own['t'] == 150:\n"
                  "        bge.render.makeScreenshot(SHOT)\n"
                  "    if SHOT and own['t'] == 160:\n"
                  "        bge.logic.endGame()\n" % shot_path)
scene.objects.active = pivot
bpy.ops.logic.sensor_add(type='ALWAYS', object=pivot.name)
bpy.ops.logic.controller_add(type='PYTHON', object=pivot.name)
s = pivot.game.sensors[-1]
s.use_pulse_true_level = True
c = pivot.game.controllers[-1]
c.mode = 'MODULE'
c.module = 'orbit.tick'
s.link(c)

bpy.ops.wm.save_as_mainfile(filepath=out_path)
print("COLOSSO_OK")
