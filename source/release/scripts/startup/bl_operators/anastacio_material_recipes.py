# Receitas de material: montam árvores de nós prontas para quem não quer ligar nós à mão.
# Cada receita funciona nos dois caminhos do Game: PBR (Shading Nodes ligado, nós do Cycles) e
# legado (nós do Blender Internal). Os nós criados recebem nomes "AE_*" para o painel achá-los depois.

import math
import os
import re

import bpy
from bpy.types import Operator
from bpy.props import (
    BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty, CollectionProperty)


RECIPE_KEY = "anastacio_recipe"
LAYERS = ("AE_layer_base", "AE_layer_r", "AE_layer_g", "AE_layer_b")
LAYER_LABELS = ("Base (black)", "Red", "Green", "Blue")
MASK = "AE_mask"
MAPPING = "AE_mapping"
WET_MASK = "AE_wet_mask"

# Sufixos comuns dos pacotes de textura (Poly Haven, ambientCG, Substance, Quixel...).
MAP_WORDS = (
    ("normal", ("normal", "normalgl", "normaldx", "nor", "nrm", "norm", "nor_gl", "nor_dx")),
    ("roughness", ("roughness", "rough", "rgh")),
    ("gloss", ("glossiness", "gloss", "smoothness")),
    ("metallic", ("metallic", "metalness", "metal", "mtl")),
    ("ao", ("ambientocclusion", "ambient_occlusion", "occlusion", "ao")),
    ("color", ("basecolor", "base_color", "albedo", "diffuse", "diff", "color", "colour", "col")),
)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".bmp", ".dds", ".exr", ".hdr", ".webp"}


def use_pbr(context):
    return context.scene.render.use_shading_nodes


SHADING_MODES = (
    ('AUTO', "Scene Setting", "Build for whatever PBR Shading Nodes is set to right now"),
    ('PBR', "PBR", "Cycles-style nodes (Principled); turns PBR Shading Nodes on"),
    ('LEGACY', "Classic", "Blender Internal nodes; turns PBR Shading Nodes off"),
)


def resolve_pbr(context, mode):
    """Diz para que caminho montar o grafo e, se preciso, alinha a cena.

    O toggle da cena é quem escolhe o caminho de desenho (GPU_material_from_blender chama
    ntreeGPUMaterialNodes com NODE_NEW_SHADING ou NODE_OLD_SHADING conforme ele), então montar
    nós de um modo com a cena no outro dá um material que simplesmente não aparece. Por isso
    pedir um modo explícito também ajusta a cena. Devolve (pbr, mudou_a_cena).
    """
    if mode == 'AUTO':
        return use_pbr(context), False
    want = (mode == 'PBR')
    # render.use_shading_nodes é derivado e somente leitura; o gravável é o do game_settings.
    gs = context.scene.game_settings
    switched = gs.use_shading_nodes != want
    if switched:
        gs.use_shading_nodes = want
    return want, switched


def classify(filename):
    """Diz que mapa (color, normal, ...) o arquivo é, pelo nome; None se não reconhecer."""
    stem = os.path.splitext(filename)[0].lower()
    tokens = [t for t in re.split(r"[_\-. ]+", stem) if t]
    for kind, words in MAP_WORDS:
        for t in reversed(tokens):
            if t in words:
                return kind
    # Nomes colados ("brickAlbedo"): procura a palavra no fim do nome.
    for kind, words in MAP_WORDS:
        for w in words:
            if len(w) > 3 and stem.endswith(w):
                return kind
    return None


def set_stem(filename):
    """Nome do conjunto sem o sufixo do mapa ("bricks_rough.png" -> "bricks")."""
    stem = os.path.splitext(filename)[0]
    tokens = re.split(r"([_\-. ]+)", stem)
    if len(tokens) > 2 and classify(tokens[-1] + ".png"):
        return "".join(tokens[:-2])
    return stem


def find_texture_set(filepath):
    """A partir de um arquivo, acha os mapas irmãos na mesma pasta com o mesmo prefixo."""
    folder, name = os.path.split(filepath)
    stem = set_stem(name).lower()
    found = {}
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        names = [name]
    for n in names:
        if os.path.splitext(n)[1].lower() not in IMAGE_EXTS:
            continue
        if not n.lower().startswith(stem):
            continue
        kind = classify(n)
        if kind and kind not in found:
            found[kind] = os.path.join(folder, n)
    if not found:
        found["color"] = filepath
    return found


def load_image(path, data=False):
    img = bpy.data.images.load(path, check_existing=True)
    if data:
        img.colorspace_settings.name = 'Non-Color'
    return img


def ensure_uv(ob):
    """Cria a UV que falta com Smart UV Project. A UV padrão do uv_textures.new() põe cada face na imagem
    inteira: numa esfera são centenas de faces sobrepostas, e pintar a máscara fica pesadíssimo."""
    if not ob or ob.type != 'MESH' or ob.data.uv_textures:
        return False
    ob.data.uv_textures.new()
    mode = ob.mode
    if mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=0.02)
    bpy.ops.object.mode_set(mode=mode)
    return True


def active_material(context):
    """Material do editor de Propriedades, ou o ativo do objeto fora dele."""
    mat = getattr(context, "material", None)
    if mat is None and context.object:
        mat = context.object.active_material
    return mat


def target_material(context, name):
    """Material ativo do objeto; cria um se o slot estiver vazio."""
    ob = context.object
    mat = active_material(context)
    if mat is None:
        mat = bpy.data.materials.new(name)
        if ob.material_slots:
            ob.active_material = mat
        else:
            ob.data.materials.append(mat)
    return mat


class TreeBuilder:
    """Ajuda a criar nós em colunas e ligá-los com pouca repetição."""

    def __init__(self, mat):
        mat.use_nodes = True
        self.tree = mat.node_tree
        # Material base já ligado a um nó (ex.: o criado pelo botão de nós) é reaproveitado.
        self.base = next((n.material for n in self.tree.nodes
                          if n.bl_idname in {"ShaderNodeMaterial", "ShaderNodeExtendedMaterial"}
                          and n.material and n.material != mat), None)
        self.tree.nodes.clear()
        self.nodes = self.tree.nodes
        self.links = self.tree.links

    def add(self, idname, x, y, name=None, label=None):
        n = self.nodes.new(idname)
        n.location = (x, y)
        if name:
            n.name = name
        if label:
            n.label = label
        return n

    def link(self, a, b):
        self.links.new(a, b)

    def frame(self, label, nodes):
        """Agrupa nós dentro de um Frame (caixa com título) para organizar o editor de nós."""
        f = self.add("NodeFrame", 0, 0, label=label)
        f.label_size = 18
        for n in nodes:
            n.parent = f
        return f

    def note(self, label, body, x, y, width=380, height=140):
        """Caixa só com texto (sem nós dentro), para explicar o grafo no editor de nós.
        O Frame do Blender mostra o conteúdo de um Text (bpy.data.texts) dentro dele."""
        f = self.add("NodeFrame", x, y, label=label)
        f.label_size = 16
        f.shrink = False
        f.width = width
        f.height = height
        name = "AE_Note_" + label
        txt = bpy.data.texts.get(name) or bpy.data.texts.new(name)
        txt.from_string(body)
        f.text = txt
        return f

    # Imagem: no PBR é o Image Texture; no legado é o nó Texture com um Texture do tipo Image.
    def image(self, pbr, img, x, y, name=None, label=None, data=False):
        if pbr:
            n = self.add("ShaderNodeTexImage", x, y, name, label)
            n.image = img
            if data:
                n.color_space = 'NONE'
            return n, n.outputs["Color"]
        n = self.add("ShaderNodeTexture", x, y, name, label)
        tex = bpy.data.textures.new(label or name or "Texture", 'IMAGE')
        tex.image = img
        n.texture = tex
        return n, n.outputs["Color"]

    def uv(self, pbr, x, y):
        if pbr:
            n = self.add("ShaderNodeTexCoord", x, y)
            return n.outputs["UV"]
        n = self.add("ShaderNodeGeometry", x, y)
        return n.outputs["UV"]

    def mapping(self, src, scale, x, y):
        m = self.add("ShaderNodeMapping", x, y, MAPPING, "Tiling")
        m.vector_type = 'POINT'
        set_tiling(m, scale)
        self.link(src, m.inputs["Vector"])
        return m.outputs["Vector"]

    def mix(self, a, b, fac, x, y, blend='MIX'):
        m = self.add("ShaderNodeMixRGB", x, y)
        m.blend_type = blend
        if fac is None:
            m.inputs["Fac"].default_value = 1.0
        else:
            self.link(fac, m.inputs["Fac"])
        self.link(a, m.inputs["Color1"])
        self.link(b, m.inputs["Color2"])
        return m.outputs["Color"]

    def legacy_output(self, mat, x, y):
        """Nó Material (BI) apontando para um material base sem nós + Output."""
        base = self.base or bpy.data.materials.new(mat.name + " Base")
        base.specular_intensity = 0.3
        base.specular_metallic_bsdf = 0.0
        mnode = self.add("ShaderNodeExtendedMaterial", x, y)
        mnode.material = base
        out = self.add("ShaderNodeOutput", x + 250, y)
        self.link(mnode.outputs["Color"], out.inputs["Color"])
        self.link(mnode.outputs["Alpha"], out.inputs["Alpha"])
        return mnode

    def pbr_output(self, x, y):
        bsdf = self.add("ShaderNodeBsdfPrincipled", x, y)
        out = self.add("ShaderNodeOutputMaterial", x + 300, y)
        self.link(bsdf.outputs["BSDF"], out.inputs["Surface"])
        return bsdf


def normal_map(b, pbr, color, x, y):
    n = b.add("ShaderNodeNormalMap", x, y)
    b.link(color, n.inputs["Color"])
    return n.outputs["Normal"]


def build_texture_set(mat, maps, pbr, scale):
    b = TreeBuilder(mat)
    uv = b.mapping(b.uv(pbr, -1100, 0), scale, -900, 0)
    y = 300
    out = {}
    for kind in ("color", "ao", "roughness", "gloss", "metallic", "normal"):
        if kind not in maps:
            continue
        img = load_image(maps[kind], data=(kind != "color"))
        node, color = b.image(pbr, img, -600, y, "AE_map_" + kind, kind.capitalize(), data=(kind != "color"))
        b.link(uv, node.inputs["Vector"])
        out[kind] = color
        y -= 280

    color = out.get("color")
    if color and "ao" in out:
        color = b.mix(color, out["ao"], None, -300, 400, 'MULTIPLY')

    if pbr:
        bsdf = b.pbr_output(0, 0)
        if color:
            b.link(color, bsdf.inputs["Base Color"])
        if "roughness" in out:
            b.link(out["roughness"], bsdf.inputs["Roughness"])
        elif "gloss" in out:
            inv = b.add("ShaderNodeInvert", -300, -100)
            b.link(out["gloss"], inv.inputs["Color"])
            b.link(inv.outputs["Color"], bsdf.inputs["Roughness"])
        if "metallic" in out:
            b.link(out["metallic"], bsdf.inputs["Metallic"])
        if "normal" in out:
            b.link(normal_map(b, pbr, out["normal"], -300, -400), bsdf.inputs["Normal"])
        return

    mnode = b.legacy_output(mat, 0, 0)
    if color:
        b.link(color, mnode.inputs["Color"])
    # No BI o brilho é Spec: superfície áspera brilha pouco.
    if "roughness" in out:
        inv = b.add("ShaderNodeInvert", -300, -100)
        b.link(out["roughness"], inv.inputs["Color"])
        b.link(inv.outputs["Color"], mnode.inputs["Spec"])
    elif "gloss" in out:
        b.link(out["gloss"], mnode.inputs["Spec"])
    if "normal" in out:
        b.link(normal_map(b, pbr, out["normal"], -300, -400), mnode.inputs["Normal"])


def placeholder_image(name, color):
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.new(name, 64, 64)
        img.generated_color = color
    return img


LAYER_COLORS = (
    (0.35, 0.35, 0.35, 1.0),
    (0.6, 0.25, 0.2, 1.0),
    (0.25, 0.5, 0.2, 1.0),
    (0.2, 0.3, 0.6, 1.0),
)
# Mapas que cada camada pode ter além da cor; camada sem o mapa usa um valor neutro.
LAYER_MAPS = ("normal", "roughness")


def neutral_image(kind):
    if kind == "normal":
        img = placeholder_image("AE Flat Normal", (0.5, 0.5, 1.0, 1.0))
    else:
        img = placeholder_image("AE Roughness 0.8", (0.8, 0.8, 0.8, 1.0))
    img.colorspace_settings.name = 'Non-Color'
    return img


def layer_node_name(i, kind):
    return LAYERS[i] if kind == "color" else LAYERS[i] + "_" + kind


def default_layers():
    return [{"color": placeholder_image("AE " + LAYER_LABELS[i], LAYER_COLORS[i])} for i in range(len(LAYERS))]


def current_layers(mat):
    """Imagens que cada camada usa hoje (inclusive as trocadas à mão no painel)."""
    layers = default_layers()
    for i in range(len(LAYERS)):
        for kind in ("color",) + LAYER_MAPS:
            img = node_image(find_node(mat, layer_node_name(i, kind)))
            if img and not img.name.startswith("AE Flat Normal") and not img.name.startswith("AE Roughness"):
                layers[i][kind] = img
    return layers


def build_mask_blend(mat, pbr, scale, mask_img, layers=None):
    layers = layers or default_layers()
    kinds = ["color"] + [k for k in LAYER_MAPS if any(k in l for l in layers)]
    b = TreeBuilder(mat)
    uv_raw = b.uv(pbr, -1700, 0)
    uv = b.mapping(uv_raw, scale, -1450, 300)

    mask, mask_color = b.image(pbr, mask_img, -1450, -300, MASK, "Mask (paint R, G, B)")
    # A máscara cobre o objeto uma vez só, sem repetir.
    b.link(uv_raw, mask.inputs["Vector"])
    sep = b.add("ShaderNodeSeparateRGB", -1450, -650)
    b.link(mask_color, sep.inputs["Image"])

    # Uma coluna por mapa: as 4 camadas misturadas pela máscara.
    mixed = {}
    for k, kind in enumerate(kinds):
        outs = []
        for i in range(len(LAYERS)):
            img = layers[i].get(kind) or neutral_image(kind)
            data = kind != "color"
            node, out = b.image(pbr, img, -1100, 900 - (i + 4 * k) * 260, layer_node_name(i, kind),
                                "%s: %s" % (LAYER_LABELS[i], kind.capitalize()), data=data)
            b.link(uv, node.inputs["Vector"])
            outs.append(out)
        out = outs[0]
        for i, ch in enumerate(("R", "G", "B")):
            out = b.mix(out, outs[i + 1], sep.outputs[ch], -700 + i * 180, 900 - k * 1040 - i * 120)
        mixed[kind] = out

    normal = normal_map(b, pbr, mixed["normal"], -100, -500) if "normal" in mixed else None
    if pbr:
        bsdf = b.pbr_output(400, 0)
        bsdf.inputs["Roughness"].default_value = 0.8
        b.link(mixed["color"], bsdf.inputs["Base Color"])
        if "roughness" in mixed:
            b.link(mixed["roughness"], bsdf.inputs["Roughness"])
        if normal:
            b.link(normal, bsdf.inputs["Normal"])
    else:
        mnode = b.legacy_output(mat, 400, 0)
        b.link(mixed["color"], mnode.inputs["Color"])
        if "roughness" in mixed:
            inv = b.add("ShaderNodeInvert", 100, -200)
            b.link(mixed["roughness"], inv.inputs["Color"])
            b.link(inv.outputs["Color"], mnode.inputs["Spec"])
        if normal:
            b.link(normal, mnode.inputs["Normal"])


def build_wet_patches(mat, pbr, scale, mask_img):
    b = TreeBuilder(mat)
    uv_raw = b.uv(pbr, -1500, 0)
    uv = b.mapping(uv_raw, scale, -1250, 250)

    mask, mask_color = b.image(pbr, mask_img, -1250, -250, WET_MASK, "Wet Mask (paint white)")
    b.link(uv_raw, mask.inputs["Vector"])
    sep = b.add("ShaderNodeSeparateRGB", -1000, -250)
    b.link(mask_color, sep.inputs["Image"])
    fac = sep.outputs["R"]

    asphalt = b.add("ShaderNodeTexNoise", -1000, 350, "AE_asphalt_noise", "Asphalt Grain")
    asphalt.inputs["Scale"].default_value = 55.0
    asphalt.inputs["Detail"].default_value = 12.0
    b.link(uv, asphalt.inputs["Vector"])

    asphalt_color = b.add("ShaderNodeValToRGB", -760, 350, "AE_asphalt_color", "Asphalt Color")
    asphalt_color.color_ramp.elements[0].position = 0.22
    asphalt_color.color_ramp.elements[0].color = (0.035, 0.038, 0.04, 1.0)
    asphalt_color.color_ramp.elements[1].position = 1.0
    asphalt_color.color_ramp.elements[1].color = (0.22, 0.23, 0.22, 1.0)
    b.link(asphalt.outputs["Fac"], asphalt_color.inputs["Fac"])

    wet_tint = b.add("ShaderNodeMixRGB", -500, 320, "AE_wet_tint", "Wet Patch Darkens Surface")
    wet_tint.blend_type = 'MIX'
    wet_tint.inputs["Color2"].default_value = (0.015, 0.025, 0.035, 1.0)
    b.link(fac, wet_tint.inputs["Fac"])
    b.link(asphalt_color.outputs["Color"], wet_tint.inputs["Color1"])

    rough = b.add("ShaderNodeMixRGB", -500, 40, "AE_wet_roughness", "Roughness: dry to wet")
    rough.inputs["Color1"].default_value = (0.82, 0.82, 0.82, 1.0)
    rough.inputs["Color2"].default_value = (0.025, 0.025, 0.025, 1.0)
    b.link(fac, rough.inputs["Fac"])

    wet_noise = b.add("ShaderNodeTexNoise", -760, -520, "AE_wet_micro_detail", "Wet Micro Detail")
    wet_noise.inputs["Scale"].default_value = 95.0
    wet_noise.inputs["Detail"].default_value = 8.0
    b.link(uv, wet_noise.inputs["Vector"])

    asphalt_bump = b.add("ShaderNodeBump", -260, -300, "AE_asphalt_bump", "Asphalt Bump")
    asphalt_bump.inputs["Strength"].default_value = 0.06
    asphalt_bump.inputs["Distance"].default_value = 0.055
    b.link(asphalt.outputs["Fac"], asphalt_bump.inputs["Height"])

    wet_bump = b.add("ShaderNodeBump", -260, -560, "AE_wet_bump", "Wet Smooth Bump")
    wet_bump.inputs["Strength"].default_value = 0.018
    wet_bump.inputs["Distance"].default_value = 0.018
    b.link(wet_noise.outputs["Fac"], wet_bump.inputs["Height"])

    normal_mix = b.add("ShaderNodeMixRGB", 0, -420, "AE_wet_normal_mix", "Mask mixes dry/wet normal")
    b.link(fac, normal_mix.inputs["Fac"])
    b.link(asphalt_bump.outputs["Normal"], normal_mix.inputs["Color1"])
    b.link(wet_bump.outputs["Normal"], normal_mix.inputs["Color2"])

    if pbr:
        bsdf = b.pbr_output(260, 0)
        b.link(wet_tint.outputs["Color"], bsdf.inputs["Base Color"])
        b.link(rough.outputs["Color"], bsdf.inputs["Roughness"])
        b.link(normal_mix.outputs["Color"], bsdf.inputs["Normal"])
    else:
        mnode = b.legacy_output(mat, 260, 0)
        base = mnode.material
        base.diffuse_color = (0.08, 0.085, 0.08)
        base.specular_intensity = 0.95
        base.specular_hardness = 420
        base.specular_roughness_bsdf = 0.04
        b.link(wet_tint.outputs["Color"], mnode.inputs["Color"])
        inv = b.add("ShaderNodeInvert", 0, 40)
        b.link(rough.outputs["Color"], inv.inputs["Color"])
        b.link(inv.outputs["Color"], mnode.inputs["Spec"])
        b.link(normal_mix.outputs["Color"], mnode.inputs["Normal"])

    # Organiza o grafo em caixas (Frames) e deixa uma nota explicando a receita.
    uv_node = uv_raw.node
    b.frame("UV / Tiling", [uv_node, b.nodes[MAPPING]])
    b.frame("Wet Mask (pinte branco = poça)", [mask, sep])
    b.frame("Asfalto Procedural", [asphalt, asphalt_color])
    b.frame("Mistura Seco / Molhado", [wet_tint, rough, wet_noise, asphalt_bump, wet_bump, normal_mix])
    b.note(
        "Como usar",
        "Pinte BRANCO na mascara 'Wet Mask' para marcar poca/mancha\n"
        "molhada (barro, oleo ou agua); PRETO volta ao asfalto seco.\n"
        "Use o botao 'Paint the Mask' no painel: ele ja troca o pincel\n"
        "para branco e da uma borda irregular (nao um circulo perfeito),\n"
        "para parecer poca/mancha de verdade em vez de um disco liso.",
        -1250, 650, width=620, height=260,
    )


def get_tiling(mapping):
    # Neste fork a escala do Mapping é uma entrada (socket); no 2.79 original, uma propriedade.
    if "Scale" in mapping.inputs:
        return mapping.inputs["Scale"].default_value[0]
    return mapping.scale[0]


def set_tiling(mapping, value):
    if "Scale" in mapping.inputs:
        mapping.inputs["Scale"].default_value = (value, value, value)
    else:
        mapping.scale = (value, value, value)


def set_mapping(mapping, translation, rotation, scale):
    """Preenche um nó Mapping nas duas formas que ele já teve: sockets (Location/
    Rotation/Scale) no nó atual, propriedades no antigo."""
    if "Location" in mapping.inputs:
        mapping.inputs["Location"].default_value = translation
        mapping.inputs["Rotation"].default_value = rotation
        mapping.inputs["Scale"].default_value = scale
    else:
        mapping.translation = translation
        mapping.rotation = rotation
        mapping.scale = scale


def find_node(mat, name):
    if mat and mat.use_nodes and mat.node_tree:
        return mat.node_tree.nodes.get(name)
    return None


def node_image(node):
    """Imagem de um nó de imagem nos dois caminhos (Image Texture ou Texture do BI)."""
    if node is None:
        return None
    if node.bl_idname == "ShaderNodeTexture":
        return node.texture.image if node.texture else None
    return node.image


class MATERIAL_OT_recipe_texture_set(Operator):
    """Pick one texture of a set (color, normal, roughness...): the other maps in the folder are found by name and connected"""
    bl_idname = "material.recipe_texture_set"
    bl_label = "Material from Texture Set"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_image: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    tiling: FloatProperty(name="Tiling", description="How many times the texture repeats over the UV",
                           default=1.0, min=0.01, soft_max=64.0)

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.filepath or not os.path.isfile(self.filepath):
            self.report({'ERROR'}, "Choose an image file")
            return {'CANCELLED'}
        maps = find_texture_set(self.filepath)
        name = set_stem(os.path.basename(self.filepath))
        mat = target_material(context, name)
        pbr = use_pbr(context)
        build_texture_set(mat, maps, pbr, self.tiling)
        mat[RECIPE_KEY] = "texture_set"
        if ensure_uv(context.object):
            self.report({'WARNING'}, "The mesh had no UV map: one was created with Smart UV Project")
        self.report({'INFO'}, "Maps connected: " + ", ".join(sorted(maps)))
        return {'FINISHED'}


class MATERIAL_OT_recipe_mask_blend(Operator):
    """One material that blends 4 textures with an RGB mask painted on the object (terrain, walls, roads), in one draw call"""
    bl_idname = "material.recipe_mask_blend"
    bl_label = "Blend Textures by Mask"
    bl_options = {'REGISTER', 'UNDO'}

    tiling: FloatProperty(name="Tiling", description="How many times the layer textures repeat over the UV",
                           default=8.0, min=0.01, soft_max=256.0)
    mask_size: IntProperty(name="Mask Size", description="Resolution of the mask image to paint",
                            default=1024, min=64, max=8192)

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        ob = context.object
        mat = target_material(context, ob.name + " Blend")
        mask = bpy.data.images.new(mat.name + " Mask", self.mask_size, self.mask_size)
        mask.generated_color = (0.0, 0.0, 0.0, 1.0)
        mask.colorspace_settings.name = 'Non-Color'
        build_mask_blend(mat, use_pbr(context), self.tiling, mask)
        mat[RECIPE_KEY] = "mask_blend"
        if ensure_uv(ob):
            self.report({'WARNING'}, "The mesh had no UV map: one was created with Smart UV Project")
        return {'FINISHED'}


class MATERIAL_OT_recipe_wet_patches(Operator):
    """Asphalt material with a paintable wet mask: paint white where reflective wet patches should appear"""
    bl_idname = "material.recipe_wet_patches"
    bl_label = "Wet/Reflective Patches"
    bl_options = {'REGISTER', 'UNDO'}

    tiling: FloatProperty(name="Surface Tiling", description="How many times the surface grain repeats over the UV",
                           default=12.0, min=0.01, soft_max=256.0)
    mask_size: IntProperty(name="Mask Size", description="Resolution of the wet/reflection mask image to paint",
                            default=1024, min=64, max=8192)
    shading: EnumProperty(name="Shading", description="Which of the two shading paths to build the nodes for",
                           items=SHADING_MODES, default='AUTO')

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        ob = context.object
        pbr, switched = resolve_pbr(context, self.shading)
        mat = target_material(context, ob.name + " Wet Surface")
        mask = bpy.data.images.new(mat.name + " Wet Mask", self.mask_size, self.mask_size)
        mask.generated_color = (0.0, 0.0, 0.0, 1.0)
        mask.colorspace_settings.name = 'Non-Color'
        build_wet_patches(mat, pbr, self.tiling, mask)
        mat[RECIPE_KEY] = "wet_patches"
        if switched:
            self.report({'INFO'}, "PBR Shading Nodes was turned %s to match" % ("on" if pbr else "off"))
        if ensure_uv(ob):
            self.report({'WARNING'}, "The mesh had no UV map: one was created with Smart UV Project")
        return {'FINISHED'}


class MATERIAL_OT_recipe_layer_set(Operator):
    """Pick one texture of a set for this layer: its normal and roughness are found by name and connected too"""
    bl_idname = "material.recipe_layer_set"
    bl_label = "Load Texture Set into Layer"
    bl_options = {'REGISTER', 'UNDO'}

    layer: IntProperty(min=0, max=len(LAYERS) - 1, options={'HIDDEN'})
    filepath: StringProperty(subtype='FILE_PATH')
    filter_image: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        mat = active_material(context)
        return mat is not None and mat.get(RECIPE_KEY) == "mask_blend"

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.filepath or not os.path.isfile(self.filepath):
            self.report({'ERROR'}, "Choose an image file")
            return {'CANCELLED'}
        mat = active_material(context)
        mask = node_image(find_node(mat, MASK))
        mapping = find_node(mat, MAPPING)
        scale = get_tiling(mapping) if mapping else 8.0
        layers = current_layers(mat)
        maps = find_texture_set(self.filepath)
        layer = {"color": load_image(maps.get("color", self.filepath))}
        for kind in LAYER_MAPS:
            if kind in maps:
                layer[kind] = load_image(maps[kind], data=True)
        layers[self.layer] = layer
        build_mask_blend(mat, use_pbr(context), scale, mask, layers)
        found = sorted(k for k in layer)
        self.report({'INFO'}, "%s: %s" % (LAYER_LABELS[self.layer], ", ".join(found)))
        return {'FINISHED'}


def ensure_puddle_brush_texture():
    """Textura 'Nuvens' para o pincel: dá borda irregular (poça), não um círculo perfeito.
    Girando/redimensionando essa textura no pincel (R/S em modo pintura) muda o formato."""
    tex = bpy.data.textures.get("AE_Puddle_Shape")
    if tex is None:
        tex = bpy.data.textures.new("AE_Puddle_Shape", 'CLOUDS')
        tex.noise_basis = 'BLENDER_ORIGINAL'
        tex.noise_scale = 0.6
        tex.intensity = 1.3
        tex.contrast = 2.2
    return tex


def apply_puddle_brush(context, color):
    ip = context.scene.tool_settings.image_paint
    brush = ip.brush
    if not brush:
        return
    brush.color = color
    brush.use_alpha = True
    brush.texture = ensure_puddle_brush_texture()
    # TILED: a textura acompanha o pincel no cursor (dá a borda irregular em cada
    # pincelada); diferente de STENCIL, que fica fixa e grande sobre a 3D view.
    brush.texture_slot.map_mode = 'TILED'


class MATERIAL_OT_recipe_paint_mask(Operator):
    """Enter Texture Paint on the blend mask: paint red, green or blue to show each layer, black for the base"""
    bl_idname = "material.recipe_paint_mask"
    bl_label = "Paint the Mask"

    @classmethod
    def poll(cls, context):
        mat = active_material(context)
        return (node_image(find_node(mat, MASK)) is not None or
                node_image(find_node(mat, WET_MASK)) is not None)

    def execute(self, context):
        mat = active_material(context)
        img = node_image(find_node(mat, WET_MASK)) or node_image(find_node(mat, MASK))
        ip = context.scene.tool_settings.image_paint
        ip.mode = 'IMAGE'
        ip.canvas = img
        if context.object.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if context.object.mode != 'TEXTURE_PAINT':
            if not bpy.ops.paint.texture_paint_toggle.poll():
                self.report({'ERROR'}, "Can't enter Texture Paint on this object (needs to be a mesh, "
                                        "not linked, and out of Edit Mode)")
                return {'CANCELLED'}
            bpy.ops.paint.texture_paint_toggle()
        if mat.get(RECIPE_KEY) == "wet_patches":
            apply_puddle_brush(context, (1.0, 1.0, 1.0))
            self.report({'INFO'}, "Paint white for wet/reflective patches, black for dry. The brush edge is "
                                   "irregular (puddle-shaped) instead of a perfect circle")
        else:
            brush = ip.brush
            if brush:
                brush.color = (1.0, 0.0, 0.0)
            self.report({'INFO'}, "Red, green and blue show layers; black shows the base. Save the mask image when done")
        return {'FINISHED'}


class MATERIAL_OT_recipe_brush_color(Operator):
    """Set the paint brush to the color of this layer"""
    bl_idname = "material.recipe_brush_color"
    bl_label = "Brush Color"

    channel: IntProperty(default=0, min=0, max=3, options={'SKIP_SAVE'})

    def execute(self, context):
        brush = context.scene.tool_settings.image_paint.brush
        if brush:
            brush.color = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))[self.channel]
        return {'FINISHED'}


class MATERIAL_OT_recipe_tiling(Operator):
    """Change how many times the textures repeat"""
    bl_idname = "material.recipe_tiling"
    bl_label = "Set Tiling"
    bl_options = {'REGISTER', 'UNDO'}

    tiling: FloatProperty(name="Tiling", default=1.0, min=0.01, soft_max=256.0)

    def invoke(self, context, event):
        m = find_node(active_material(context), MAPPING)
        if m:
            self.tiling = get_tiling(m)
        return context.window_manager.invoke_props_popup(self, event)

    def execute(self, context):
        m = find_node(active_material(context), MAPPING)
        if m is None:
            return {'CANCELLED'}
        set_tiling(m, self.tiling)
        return {'FINISHED'}


# Pontos de partida com valores que todo mundo procura.
PRESETS = (
    ("PLASTIC", "Plastic", (0.8, 0.1, 0.1), 0.0, 0.35, 1.0, 0.0),
    ("METAL", "Metal", (0.8, 0.8, 0.8), 1.0, 0.25, 1.0, 0.0),
    ("GOLD", "Gold", (1.0, 0.77, 0.34), 1.0, 0.2, 1.0, 0.0),
    ("RUBBER", "Rubber", (0.05, 0.05, 0.05), 0.0, 0.9, 1.0, 0.0),
    ("WOOD", "Wood (no texture)", (0.45, 0.28, 0.14), 0.0, 0.6, 1.0, 0.0),
    ("GLASS", "Glass", (1.0, 1.0, 1.0), 0.0, 0.0, 0.15, 0.0),
    ("EMISSIVE", "Glowing", (1.0, 0.6, 0.2), 0.0, 0.5, 1.0, 4.0),
)


class MATERIAL_OT_recipe_preset(Operator):
    """Replace the material with a ready-made starting point"""
    bl_idname = "material.recipe_preset"
    bl_label = "Material Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(name="Preset", items=[(p[0], p[1], "") for p in PRESETS])

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type in {'MESH', 'CURVE', 'SURFACE', 'FONT'}

    def execute(self, context):
        _id, label, color, metal, rough, alpha, emit = next(p for p in PRESETS if p[0] == self.preset)
        mat = target_material(context, label)
        mat[RECIPE_KEY] = "preset"
        if alpha < 1.0:
            mat.game_settings.alpha_blend = 'ALPHA'
        if use_pbr(context):
            b = TreeBuilder(mat)
            bsdf = b.pbr_output(0, 0)
            if self.preset == 'GLASS':
                glass = b.add("ShaderNodeBsdfGlass", 0, -500)
                glass.inputs["Roughness"].default_value = 0.0
                b.link(glass.outputs["BSDF"], b.nodes["Material Output"].inputs["Surface"])
                b.nodes.remove(bsdf)
                return {'FINISHED'}
            bsdf.inputs["Base Color"].default_value = color + (1.0,)
            bsdf.inputs["Metallic"].default_value = metal
            bsdf.inputs["Roughness"].default_value = rough
            if emit > 0.0:
                em = b.add("ShaderNodeEmission", 0, -500)
                em.inputs["Color"].default_value = color + (1.0,)
                em.inputs["Strength"].default_value = emit
                add = b.add("ShaderNodeAddShader", 250, -250)
                out = b.nodes["Material Output"]
                b.link(bsdf.outputs["BSDF"], add.inputs[0])
                b.link(em.outputs["Emission"], add.inputs[1])
                b.link(add.outputs["Shader"], out.inputs["Surface"])
            return {'FINISHED'}
        # Game legado: nó Material + borda Fresnel para cada preset ter cara própria.
        build_legacy_preset(mat, self.preset, color, metal, rough, alpha, emit)
        return {'FINISHED'}


# Brilho de borda por preset (cor, força, expoente): metal reflete a própria cor,
# plástico e vidro refletem branco, borracha quase nada.
LEGACY_RIM = {
    "PLASTIC": (None, 0.25, 4.0),
    "METAL": ("SELF", 0.9, 2.0),
    "GOLD": ("SELF", 1.0, 2.0),
    "RUBBER": (None, 0.03, 5.0),
    "WOOD": (None, 0.1, 4.0),
    "GLASS": (None, 1.0, 3.0),
    "EMISSIVE": ("SELF", 0.6, 2.0),
}


def build_legacy_preset(mat, preset, color, metal, rough, alpha, emit):
    b = TreeBuilder(mat)
    mnode = b.legacy_output(mat, 400, 0)
    base = mnode.material
    out = b.nodes["Output"]
    base.diffuse_color = tuple(c * 0.25 for c in color) if metal else color
    base.diffuse_intensity = 1.0 if metal else 0.8
    base.specular_color = color if metal else (1.0, 1.0, 1.0)
    base.specular_intensity = (1.0 - rough) * (1.0 if metal else 0.6)
    base.specular_hardness = int(5 + (1.0 - rough) ** 2 * 450)
    # Metallic/Roughness do material do fork (padrão 0.5/0.5 deixava tudo igual).
    base.specular_metallic_bsdf = metal
    base.specular_roughness_bsdf = max(rough, 0.05)
    base.use_transparency = alpha < 1.0
    base.alpha = alpha
    mat.use_transparency = alpha < 1.0
    mat.alpha = alpha

    # Fresnel: (1 - |N.V|) ^ expoente
    rim_kind, rim_strength, rim_power = LEGACY_RIM.get(preset, (None, 0.2, 4.0))
    geo = b.add("ShaderNodeGeometry", -400, -300)
    dot = b.add("ShaderNodeVectorMath", -200, -300)
    dot.operation = 'DOT_PRODUCT'
    b.link(geo.outputs["Normal"], dot.inputs[0])
    b.link(geo.outputs["View"], dot.inputs[1])
    ab = b.add("ShaderNodeMath", 0, -300)
    ab.operation = 'ABSOLUTE'
    b.link(dot.outputs["Value"], ab.inputs[0])
    inv = b.add("ShaderNodeMath", 150, -300)
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    b.link(ab.outputs["Value"], inv.inputs[1])
    pw = b.add("ShaderNodeMath", 300, -300, name="AE_fresnel", label="Fresnel")
    pw.operation = 'POWER'
    pw.inputs[1].default_value = rim_power
    b.link(inv.outputs["Value"], pw.inputs[0])
    fac = b.add("ShaderNodeMath", 450, -300)
    fac.operation = 'MULTIPLY'
    fac.inputs[1].default_value = rim_strength
    b.link(pw.outputs["Value"], fac.inputs[0])

    rim = b.add("ShaderNodeMixRGB", 650, 0, name="AE_rim", label="Edge Shine")
    rim.blend_type = 'ADD'
    b.link(fac.outputs["Value"], rim.inputs["Fac"])
    b.link(mnode.outputs["Color"], rim.inputs["Color1"])
    rim_color = color if rim_kind == "SELF" else (1.0, 1.0, 1.0)
    rim.inputs["Color2"].default_value = tuple(rim_color) + (1.0,)
    last = rim.outputs["Color"]

    if emit > 0.0:
        glow = b.add("ShaderNodeMixRGB", 850, 0, name="AE_glow", label="Glow")
        glow.blend_type = 'ADD'
        glow.inputs["Fac"].default_value = min(emit / 4.0, 1.0)
        b.link(last, glow.inputs["Color1"])
        glow.inputs["Color2"].default_value = tuple(color) + (1.0,)
        last = glow.outputs["Color"]

    out.location = (1050, 0)
    b.link(last, out.inputs["Color"])
    if alpha < 1.0:
        # Vidro: mais opaco nas bordas.
        a = b.add("ShaderNodeMath", 650, -300)
        a.operation = 'ADD'
        a.use_clamp = True
        a.inputs[0].default_value = alpha
        b.link(pw.outputs["Value"], a.inputs[1])
        b.link(a.outputs["Value"], out.inputs["Alpha"])

# ---------------------------------------------------------------------------
# Converter material do jeito antigo (slots de textura) para nós PBR
# ---------------------------------------------------------------------------

# Que papel cada "Influence" do slot cumpre no grafo novo. A ordem importa: é a ordem
# em que os slots são lidos e empilhados.
SLOT_ROLES = (
    ("use_map_color_diffuse", "color"),
    ("use_map_normal", "normal"),
    ("use_map_specular", "specular"),
    ("use_map_hardness", "roughness"),
    ("use_map_alpha", "alpha"),
    ("use_map_emit", "emit"),
)


def legacy_slots(mat):
    """Slots de textura ligados do material, como (slot, imagem ou None, [papéis])."""
    out = []
    for i, slot in enumerate(mat.texture_slots):
        if slot is None or not mat.use_textures[i] or slot.texture is None:
            continue
        roles = [role for prop, role in SLOT_ROLES if getattr(slot, prop, False)]
        if not roles:
            continue
        tex = slot.texture
        img = tex.image if tex.type == 'IMAGE' else None
        out.append((slot, img, roles))
    return out


def build_pbr_from_legacy(mat):
    """Monta um grafo Principled a partir dos slots de textura do material.

    Devolve (trazidos, ignorados): nomes de textura que entraram no grafo e os que não
    deram (texturas procedurais do BI não têm equivalente direto em nó do Cycles).
    """
    slots = legacy_slots(mat)
    b = TreeBuilder(mat)

    bsdf = b.add("ShaderNodeBsdfPrincipled", 300, 0)
    out = b.add("ShaderNodeOutputMaterial", 900, 0)

    # Valores do material entram como ponto de partida; textura, quando houver, sobrescreve.
    bsdf.inputs["Base Color"].default_value = tuple(mat.diffuse_color) + (1.0,)
    bsdf.inputs["Metallic"].default_value = mat.specular_metallic_bsdf
    bsdf.inputs["Roughness"].default_value = max(mat.specular_roughness_bsdf, 0.02)
    bsdf.inputs["Specular"].default_value = min(mat.specular_intensity, 1.0)

    coords = {}

    def coord_source(slot):
        """Fonte de coordenada do slot, reaproveitada entre slots que usam a mesma."""
        key = (slot.texture_coords, slot.uv_layer)
        if key not in coords:
            y = 400 - 220 * len(coords)
            if slot.texture_coords == 'UV' and slot.uv_layer:
                n = b.add("ShaderNodeUVMap", -1500, y, label="UV: " + slot.uv_layer)
                n.uv_map = slot.uv_layer
                coords[key] = n.outputs["UV"]
            else:
                n = b.add("ShaderNodeTexCoord", -1500, y)
                coords[key] = n.outputs["Generated" if slot.texture_coords == 'ORCO' else "UV"]
        return coords[key]

    def place(slot, node, y):
        """Liga a coordenada no nó de imagem com o Offset/Size/Rotation do painel.

        O shader do jogo faz (gpu_shader_material.glsl, mtex_mapping_transform):

            out = R(rot) * (co - 0.5) * size + 0.5 + ofs      # gira, depois escala

        Já um Mapping -- tanto o nó quanto o texture_mapping embutido do nó de imagem,
        que BKE_texture_mapping_init monta como loc*rot*size -- faz o contrário:

            out = loc + R(rot) * (size * co)                  # escala, depois gira

        Os dois batem quando a rotação e a escala comutam: sem rotação, ou com escala
        igual em X e Y. Aí a conta toda cabe numa matriz só, com
        loc = (ofs + 0.5) - R*(0.5*size), e vale a pena usar o texture_mapping do
        próprio nó em vez de um nó Mapping separado: o modo Texture da 3D view não roda
        GLSL, ele só carrega essa matriz (drawmesh.c, tex_mat_set_texture_cb), então
        mapping que mora num nó à parte simplesmente some ali.

        Com rotação E escala diferente em X/Y não existe matriz única equivalente, e aí
        volta a cadeia de três nós (centraliza, gira, escala+offset) para não trocar a
        ordem e cisalhar a textura. Nesse caso o modo Texture fica sem o mapping; o modo
        Material e o jogo continuam certos.
        """
        src = coord_source(slot)
        size = tuple(slot.scale)
        ofs = tuple(slot.offset)
        rot = slot.rotation

        if size != (1.0, 1.0, 1.0) or ofs != (0.0, 0.0, 0.0) or rot != 0.0:
            if rot == 0.0 or abs(size[0] - size[1]) < 1e-6:
                c, s = math.cos(rot), math.sin(rot)
                hx, hy, hz = 0.5 * size[0], 0.5 * size[1], 0.5 * size[2]
                tm = node.texture_mapping
                tm.vector_type = 'POINT'
                tm.translation = (ofs[0] + 0.5 - (hx * c - hy * s),
                                  ofs[1] + 0.5 - (hx * s + hy * c),
                                  ofs[2] + 0.5 - hz)
                tm.rotation = (0.0, 0.0, rot)
                tm.scale = size
            else:
                steps = [
                    ("Centro", (-0.5, -0.5, -0.5), 0.0, (1.0, 1.0, 1.0)),
                    ("Rotation", (0.0, 0.0, 0.0), rot, (1.0, 1.0, 1.0)),
                    ("Offset/Size", (ofs[0] + 0.5, ofs[1] + 0.5, ofs[2] + 0.5), 0.0, size),
                ]
                x = -1050 - 150 * (len(steps) - 1)
                for label, translation, rotation, scale in steps:
                    m = b.add("ShaderNodeMapping", x, y + 150, label=label)
                    m.vector_type = 'POINT'
                    set_mapping(m, translation, (0.0, 0.0, rotation), scale)
                    b.link(src, m.inputs["Vector"])
                    src = m.outputs["Vector"]
                    x += 150

        b.link(src, node.inputs["Vector"])

    brought, skipped = [], []
    color_out = None
    alpha_out = None
    emit_out = None
    row = 0

    for slot, img, roles in slots:
        if img is None:
            skipped.append("%s (%s)" % (slot.texture.name, slot.texture.type.lower()))
            continue
        y = 300 - 320 * row
        row += 1
        # Normal/specular/roughness/alpha são dados, não cor: fora do espaço sRGB.
        data = roles != ["color"]
        node, img_color = b.image(True, img, -850, y, label=slot.texture.name, data=data)
        place(slot, node, y)
        brought.append("%s -> %s" % (slot.texture.name, "/".join(roles)))

        for role in roles:
            if role == "color":
                if color_out is None:
                    color_out = img_color
                    # Nó de textura ativo: é ele que o modo Texture da 3D view desenha
                    # (nodeGetActiveTexture) e o que o Texture Paint pinta. Sem marcar,
                    # sobra o primeiro nó de textura da lista, que pode ser o normal map.
                    b.tree.nodes.active = node
                else:
                    # Segundo slot de cor em diante: empilha com o blend do próprio slot.
                    m = b.add("ShaderNodeMixRGB", -550, y, label="Layer: " + slot.texture.name)
                    # Os modos do slot do BI e os do MixRGB quase coincidem; o que não existir
                    # lá vira MIX em vez de estourar.
                    try:
                        m.blend_type = slot.blend_type
                    except TypeError:
                        m.blend_type = 'MIX'
                    m.inputs["Fac"].default_value = slot.diffuse_color_factor
                    b.link(color_out, m.inputs["Color1"])
                    b.link(img_color, m.inputs["Color2"])
                    color_out = m.outputs["Color"]
            elif role == "normal":
                nm = b.add("ShaderNodeNormalMap", -550, y - 150)
                nm.inputs["Strength"].default_value = abs(slot.normal_factor)
                b.link(img_color, nm.inputs["Color"])
                b.link(nm.outputs["Normal"], bsdf.inputs["Normal"])
            elif role == "specular":
                b.link(img_color, bsdf.inputs["Specular"])
            elif role == "roughness":
                # No BI o mapa é de Hardness: mais claro = mais liso, ou seja, roughness invertido.
                inv = b.add("ShaderNodeInvert", -550, y - 150, label="Hardness -> Roughness")
                b.link(img_color, inv.inputs["Color"])
                b.link(inv.outputs["Color"], bsdf.inputs["Roughness"])
            elif role == "alpha":
                alpha_out = node.outputs["Alpha"] if img.depth in {32, 64, 128} else img_color
            elif role == "emit":
                emit_out = img_color

    if color_out is not None:
        b.link(color_out, bsdf.inputs["Base Color"])

    surface = bsdf.outputs["BSDF"]

    if emit_out is not None:
        em = b.add("ShaderNodeEmission", 550, -250, label="Emit")
        em.inputs["Strength"].default_value = max(mat.emit, 0.1)
        b.link(emit_out, em.inputs["Color"])
        add = b.add("ShaderNodeAddShader", 720, -100)
        b.link(surface, add.inputs[0])
        b.link(em.outputs["Emission"], add.inputs[1])
        surface = add.outputs["Shader"]

    if alpha_out is not None:
        tr = b.add("ShaderNodeBsdfTransparent", 550, 250)
        mix = b.add("ShaderNodeMixShader", 720, 150, label="Alpha")
        b.link(alpha_out, mix.inputs["Fac"])
        b.link(tr.outputs["BSDF"], mix.inputs[1])
        b.link(surface, mix.inputs[2])
        surface = mix.outputs["Shader"]
        # GPU_material_from_blender só liga o blend quando ma->alpha < 1, mesmo com a
        # transparência vindo de nó; sem isto o mapa de alpha não recorta nada.
        mat.use_transparency = True
        if mat.alpha >= 1.0:
            mat.alpha = 0.999

    b.link(surface, out.inputs["Surface"])
    return brought, skipped


class MATERIAL_OT_material_to_pbr(Operator):
    """Rebuild this material as PBR nodes, bringing its texture slots along as Image Texture nodes"""
    bl_idname = "material.to_pbr_nodes"
    bl_label = "Convert Material to PBR Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    keep_slots: BoolProperty(
        name="Keep Texture Slots", default=True,
        description="Leave the old texture slots in place, so switching PBR Shading Nodes off "
                    "brings the classic material back")

    @classmethod
    def poll(cls, context):
        return active_material(context) is not None

    def invoke(self, context, event):
        mat = active_material(context)
        # Converter apaga a árvore atual: se já houver um grafo novo, confirma antes.
        if mat.use_nodes and mat.node_tree and any(
                n.bl_idname == "ShaderNodeOutputMaterial" for n in mat.node_tree.nodes):
            return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context):
        mat = active_material(context)
        brought, skipped = build_pbr_from_legacy(mat)
        if not context.scene.game_settings.use_shading_nodes:
            context.scene.game_settings.use_shading_nodes = True
            self.report({'INFO'}, "PBR Shading Nodes was turned on so the new nodes render")
        if not self.keep_slots:
            for i, slot in enumerate(mat.texture_slots):
                if slot is not None and slot.texture is not None:
                    mat.texture_slots.clear(i)
        if skipped:
            self.report({'WARNING'},
                        "Not converted (no node equivalent): " + ", ".join(skipped))
        elif not brought:
            self.report({'WARNING'},
                        "The material had no active texture slot: only its colors were carried over")
        else:
            self.report({'INFO'}, "Converted %d texture(s) to nodes" % len(brought))
        return {'FINISHED'}


classes = (
    MATERIAL_OT_recipe_texture_set,
    MATERIAL_OT_recipe_mask_blend,
    MATERIAL_OT_recipe_wet_patches,
    MATERIAL_OT_recipe_layer_set,
    MATERIAL_OT_recipe_paint_mask,
    MATERIAL_OT_recipe_brush_color,
    MATERIAL_OT_recipe_tiling,
    MATERIAL_OT_recipe_preset,
    MATERIAL_OT_material_to_pbr,
)
