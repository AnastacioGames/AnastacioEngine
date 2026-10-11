# Cena de demonstracao dos nos de vertex/geometry: ilha com grama, mar com ondas, bicho peludo,
# arvores toon com contorno e cristal pulsando (GLSL Script + Material.geomcode). Camera em orbita.
# Cada arvore de nos fica separada em frames com a explicacao de cada parte.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_ilha_shader_nodes.py -- saida.range [captura.png]
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
world.horizon_color = (0.95, 0.55, 0.35)
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


# Sea
sea = preset_material("Sea", 'WATER_WAVES',
                      "1. Preset Water Waves: duas ondas somadas + cor por angulo de visao (Tab abre o grupo)",
                      {"Shallow Color": (0.25, 0.6, 0.65, 1.0), "Deep Color": (0.02, 0.1, 0.25, 1.0),
                       "Amplitude": 0.12, "Wavelength": 4.0, "Speed": 1.2})
mesh(bpy.ops.mesh.primitive_grid_add, "Sea", (0, 0, 0), sea, x_subdivisions=120, y_subdivisions=120, radius=30)

# Island: sand base and grass dome
sand, tree, out, bsdf = node_material("Sand", (0.85, 0.7, 0.45, 1.0))
finish_material(tree, out, bsdf)
mesh(bpy.ops.mesh.primitive_uv_sphere_add, "Sand", (0, 0, -0.55), sand, scale=(6.5, 6.5, 1.0),
     segments=48, ring_count=24)
grass = preset_material("Grass", 'GRASS',
                        "1. Preset Grass: camadas pela normal (Fur Shells), cor da raiz ate a ponta (Tab abre)",
                        clip=True)
# Thinner blades than the preset default (the Fur Shells node lives inside the group).
for node in bpy.data.materials["Grass"].node_tree.nodes:
    if node.bl_idname == "ShaderNodeGroup":
        for inner in node.node_tree.nodes:
            if inner.bl_idname == "ShaderNodeFurShells":
                inner.inputs["Density"].default_value = 260.0
                inner.inputs["Length"].default_value = 0.22
mesh(bpy.ops.mesh.primitive_uv_sphere_add, "Hill", (0, 0, -0.9), grass, scale=(5.0, 5.0, 1.6),
     segments=48, ring_count=24)

# Furry creature on top
fur = preset_material("Fur", 'FUR',
                      "1. Preset Fur: pelo curto em camadas, cor da raiz ate a ponta (Tab abre o grupo)",
                      {"Root Color": (0.35, 0.12, 0.05, 1.0), "Tip Color": (1.0, 0.75, 0.4, 1.0)}, clip=True)
bicho = mesh(bpy.ops.mesh.primitive_monkey_add, "Bicho", (0, -0.3, 1.45), fur, scale=(0.9, 0.9, 0.9))
bpy.ops.object.modifier_add(type='SUBSURF')
bpy.ops.object.modifier_apply(apply_as='DATA', modifier=bicho.modifiers[-1].name)
bicho.rotation_euler = (math.radians(-15), 0, 0)

# Toon trees with outline
OUTLINE_NOTE = "1. Preset Toon Outline: casco preto em volta da malha + cor chapada (Tab abre o grupo)"
trunk = preset_material("Trunk", 'TOON_OUTLINE', OUTLINE_NOTE, {"Color": (0.35, 0.2, 0.1, 1.0)})
leaves = [preset_material("Leaves%d" % i, 'TOON_OUTLINE', OUTLINE_NOTE, {"Color": c})
          for i, c in enumerate(((0.15, 0.55, 0.25, 1.0), (0.85, 0.45, 0.15, 1.0), (0.9, 0.3, 0.45, 1.0)))]
for i, (x, y, h) in enumerate(((-2.8, 1.5, 1.0), (2.9, 1.0, 1.3), (1.2, 3.0, 0.9), (-1.5, -2.6, 0.8))):
    z = 0.35
    mesh(bpy.ops.mesh.primitive_cylinder_add, "Trunk%d" % i, (x, y, z + h * 0.5), trunk,
         scale=(0.12 * h, 0.12 * h, h * 0.5), vertices=12)
    for k in range(3):
        r = (0.75 - k * 0.2) * h
        mesh(bpy.ops.mesh.primitive_cone_add, "Leaves%d_%d" % (i, k), (x, y, z + h * (1.0 + k * 0.45)),
             leaves[i % len(leaves)], scale=(r, r, h * 0.45), vertices=16)

# Crystals: GLSL Script colours + geometry code that makes the faces breathe
txt = bpy.data.texts.new("crystal.glsl")
txt.from_string("// GLSL Script: os parametros de main viram os sockets do no.\n"
                "void main(vec3 Vector, float Bands, out vec4 Color)\n"
                "{\n"
                "    float t = Vector.z * Bands + Vector.x * 0.7;\n"
                "    vec3 c = 0.55 + 0.45 * cos(6.2831 * (t + vec3(0.0, 0.33, 0.67)));\n"
                "    Color = vec4(c, 1.0);\n"
                "}\n")
geo = bpy.data.texts.new("crystal_breathe.glsl")
geo.from_string("// Campo Geometry do material: afasta cada triangulo pela normal, pulsando no tempo.\n"
                "layout(triangle_strip, max_vertices = 3) out;\n"
                "void geometry()\n{\n"
                "    vec3 n = normalize(cross(geom_position(1) - geom_position(0), geom_position(2) - geom_position(0)));\n"
                "    float k = 0.12 * (sin(TIME * 2.0) * 0.5 + 0.5);\n"
                "    for (int i = 0; i < 3; i++) geom_emit_offset(i, n * k);\n"
                "    EndPrimitive();\n}\n")
crystal, tree, out, bsdf = node_material("Crystal", (1, 1, 1, 1))
script = tree.nodes.new("ShaderNodeGLSLScript")
script.script = txt
try:
    script.update()
except Exception as e:
    print("update()", e)
tree.update_tag()
script.location = (-100, 0)
coord = tree.nodes.new("ShaderNodeTexCoord")
coord.location = (-500, 0)
if "Color" in script.outputs:
    script.inputs["Bands"].default_value = 0.6
    tree.links.new(coord.outputs["Object"], script.inputs["Vector"])
    tree.links.new(script.outputs["Color"], bsdf.inputs["Base Color"])
    if "Emission" in bsdf.inputs:
        tree.links.new(script.outputs["Color"], bsdf.inputs["Emission"])
bsdf.inputs["Roughness"].default_value = 0.15
crystal.script_geom = geo
frame(tree, "0. Entrada: posicao do ponto no objeto", 'IN', [coord])
frame(tree, "1. GLSL Script (crystal.glsl): faixas de arco-iris pela altura", 'GEOMETRY', [script])
finish_material(tree, out, bsdf,
                "3. Saida. As faces pulsando vem do campo Geometry do material (crystal_breathe.glsl)")
for i, (x, y, s, tilt) in enumerate(((3.2, -2.2, 1.0, 0.2), (3.9, -1.6, 0.6, -0.4), (2.6, -2.9, 0.5, 0.5))):
    bpy.ops.mesh.primitive_ico_sphere_add(location=(x, y, 0.5 + s), subdivisions=1)
    ob = bpy.context.active_object
    ob.name = "Crystal%d" % i
    ob.scale = (0.45 * s, 0.45 * s, 1.3 * s)
    bpy.ops.object.transform_apply(scale=True)
    ob.rotation_euler = (tilt, tilt * 0.5, i)
    ob.data.materials.append(crystal)

# Sunset light
lamp = bpy.data.lamps.new("Sun", 'SUN')
lamp.color = (1.0, 0.8, 0.6)
lamp.energy = 1.4
sun = bpy.data.objects.new("Sun", lamp)
scene.objects.link(sun)
sun.rotation_euler = (math.radians(65), 0.0, math.radians(120))
fill = bpy.data.lamps.new("Fill", 'HEMI')
fill.color = (0.5, 0.6, 0.9)
fill.energy = 0.35
fo = bpy.data.objects.new("Fill", fill)
scene.objects.link(fo)

# Orbiting camera
pivot = bpy.data.objects.new("Pivot", None)
scene.objects.link(pivot)
pivot.location = (0, 0, 1.2)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 28
cam.data.clip_end = 300
scene.objects.link(cam)
cam.parent = pivot
cam.location = (0, -11, 3.2)
cam.rotation_euler = (math.radians(78), 0, 0)
scene.camera = cam

logic = bpy.data.texts.new("orbit.py")
logic.from_string("import bge\n"
                  "SHOT = %r\n"
                  "def tick(cont):\n"
                  "    own = cont.owner\n"
                  "    own.applyRotation((0.0, 0.0, 0.004), False)\n"
                  "    own['t'] = own.get('t', 0) + 1\n"
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
print("ILHA_OK", [s.name for s in script.inputs], [s.name for s in script.outputs])
