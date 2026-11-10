"""Palette Atlas: materiais só de cor viram quadrados de uma imagem da cena.

Cada material liso (sem textura) vira um quadrado de 8 px numa imagem 256x256
compartilhada pela cena. A UV "AnastacioPalette" de cada face aponta para o
centro do quadrado do seu material antigo. Como a UV é constante na face, o
GPU lê sempre o mip 0 no centro do quadrado: a cor nunca vaza para o vizinho.

PBR: AnastacioPalette guarda cor + alpha; AnastacioPaletteData guarda
Roughness (R), Metallic (G) e Specular (B). Legado: só cor + alpha; specular
e o resto ficam no material de resultado (um por combinação diferente).

A malha original fica como backup com as mesmas chaves do Material Atlas,
então o "Restore Original Materials" nativo desfaz a conversão.
"""

import json

import bpy
from bpy.types import Operator

PALETTE_NAME = "AnastacioPalette"
DATA_NAME = "AnastacioPaletteData"
UV_NAME = "AnastacioPalette"
KEYS_PROP = "_ae_palette_keys"
SIG_PROP = "_ae_palette_sig"
BACKUP_KEY = "_anastacio_atlas_source"
BACKUP_SLOT_KEY = "_anastacio_atlas_source_slot"
SIZE = 256
CELL = 8
COLUMNS = SIZE // CELL
CAPACITY = COLUMNS * COLUMNS


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------

def _round(values):
    return [round(float(v), 4) for v in values]


def _linked(sock):
    return sock is not None and sock.is_linked


def _from(sock):
    return sock.links[0].from_node if sock.is_linked else None


def _output_node(tree):
    for node in tree.nodes:
        if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
            return node
    for node in tree.nodes:
        if node.type == 'OUTPUT_MATERIAL':
            return node
    return None


def _common_sig(mat):
    """Tudo que não cabe na paleta e precisa ser igual para dividir um material."""
    game = mat.game_settings
    return {
        "nodes": bool(mat.use_nodes),
        "blend": game.alpha_blend,
        "cull": bool(game.use_backface_culling),
        "invisible": bool(game.invisible),
        "face": game.face_orientation,
        "physics": bool(game.physics),
        "colored_shadows": bool(mat.use_colored_shadows),
        "shadows": [bool(mat.use_shadows), bool(mat.use_cast_shadows),
                    bool(mat.use_cast_shadows_only), bool(mat.use_only_shadow)],
        "shadeless": bool(mat.use_shadeless),
        "transp_method": mat.transparency_method,
    }


def _pbr_info(mat):
    """(chave, assinatura, transparente) ou (None, motivo)."""
    tree = mat.node_tree
    if tree is None:
        return None, "no node tree"
    out = _output_node(tree)
    if out is None or not out.inputs["Surface"].is_linked:
        return None, "no Material Output"
    if _linked(out.inputs.get("Volume")) or _linked(out.inputs.get("Displacement")):
        return None, "volume/displacement"
    node = _from(out.inputs["Surface"])
    alpha = 1.0
    transparent = False
    if node.type == 'MIX_SHADER':
        fac, first, second = node.inputs[0], node.inputs[1], node.inputs[2]
        if fac.is_linked or not first.is_linked or not second.is_linked:
            return None, "Mix Shader with textured factor"
        trans = _from(first)
        if trans.type != 'BSDF_TRANSPARENT' or _linked(trans.inputs["Color"]):
            return None, "Mix Shader is not a plain alpha mix"
        if tuple(trans.inputs["Color"].default_value[:3]) != (1.0, 1.0, 1.0):
            return None, "tinted Transparent BSDF"
        alpha = fac.default_value
        transparent = True
        node = _from(second)
    emission = None
    if node.type == 'ADD_SHADER':
        a, b = _from(node.inputs[0]), _from(node.inputs[1])
        if a is None or b is None:
            return None, "Add Shader with an empty input"
        if a.type == 'EMISSION':
            a, b = b, a
        if b.type != 'EMISSION':
            return None, "Add Shader is not Principled + Emission"
        if any(s.is_linked for s in b.inputs):
            return None, "textured emission"
        emission = _round(list(b.inputs["Color"].default_value) + [b.inputs["Strength"].default_value])
        node = a
    if node.type != 'BSDF_PRINCIPLED':
        return None, "surface is not a Principled BSDF"
    if any(s.is_linked for s in node.inputs):
        return None, "texture or node connected to the Principled"
    inputs = node.inputs
    color = list(inputs["Base Color"].default_value[:3])
    data = [inputs["Roughness"].default_value, inputs["Metallic"].default_value,
            inputs["Specular"].default_value]
    rest = {}
    for sock in inputs:
        if sock.name in {"Base Color", "Roughness", "Metallic", "Specular", "Normal",
                         "Clearcoat Normal", "Tangent"}:
            continue
        value = sock.default_value
        rest[sock.name] = _round(value) if hasattr(value, "__len__") else round(float(value), 4)
    sig = _common_sig(mat)
    sig.update(kind="pbr", dist=node.distribution, sss=node.subsurface_method,
               rest=rest, emission=emission, transparent=transparent)
    return (color + [alpha], data, sig), None


def _legacy_info(mat, mesh):
    for slot in mat.texture_slots:
        if slot and slot.texture and slot.use:
            return None, "texture slot in use"
    if mat.use_vertex_color_paint and mesh.vertex_colors:
        return None, "vertex color paint"
    transparent = bool(mat.use_transparency) and mat.alpha < 1.0
    sig = _common_sig(mat)
    sig.update(kind="legacy",
               diffuse=[mat.diffuse_shader, round(mat.diffuse_intensity, 4)],
               spec=_round(list(mat.specular_color) + [mat.specular_intensity, mat.specular_hardness]),
               spec_shader=mat.specular_shader,
               emit=round(mat.emit, 4), ambient=round(mat.ambient, 4),
               translucency=round(mat.translucency, 4),
               object_color=bool(mat.use_object_color),
               vcol_light=bool(mat.use_vertex_color_light),
               transparent=transparent)
    color = list(mat.diffuse_color) + [mat.alpha if transparent else 1.0]
    return (color, [0.0, 0.0, 0.0], sig), None


def material_info(mat, mesh):
    """Classifica um material: ((cor RGBA, dados, assinatura), None) se for liso,
    (None, motivo) se precisar de bake."""
    if mat is None:
        return None, "empty slot"
    if mat.use_nodes:
        if mat.node_tree and any(n.type == 'MATERIAL' or n.type == 'MATERIAL_EXT'
                                 for n in mat.node_tree.nodes):
            return None, "legacy node material"
        return _pbr_info(mat)
    return _legacy_info(mat, mesh)


def used_slots(ob):
    mesh = ob.data
    if not mesh.polygons:
        return set()
    used = set()
    for poly in mesh.polygons:
        used.add(poly.material_index)
    return {i for i in used if i < len(ob.material_slots)}


def classify(ob):
    """Resumo para o painel e para o Auto: lista de (slot, nome, liso, motivo)."""
    result = []
    for index in sorted(used_slots(ob)):
        mat = ob.material_slots[index].material
        info, reason = material_info(mat, ob.data)
        result.append((index, mat.name if mat else "(empty)", info is not None, reason))
    return result


# ---------------------------------------------------------------------------
# Imagens da paleta
# ---------------------------------------------------------------------------

def _to_srgb(c):
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def _byte(v):
    return int(round(max(0.0, min(1.0, v)) * 255.0))


class Palette:
    """Paleta da cena: chave (bytes RGBA + dados) -> índice do quadrado."""

    def __init__(self, scene):
        self.srgb = scene.display_settings.display_device != 'None'
        self.color = bpy.data.images.get(PALETTE_NAME)
        self.data = bpy.data.images.get(DATA_NAME)
        self.keys = []
        if self.color is not None and KEYS_PROP in self.color:
            try:
                self.keys = json.loads(self.color[KEYS_PROP])
            except ValueError:
                self.keys = []
        if self.color is not None and tuple(self.color.size) != (SIZE, SIZE):
            raise RuntimeError("Image %s has an unexpected size; rename it first" % PALETTE_NAME)
        self.index = {k: i for i, k in enumerate(self.keys)}
        self.dirty = False

    def key(self, color, data):
        if self.srgb:
            rgb = [_to_srgb(c) for c in color[:3]]
        else:
            rgb = color[:3]
        return "%02x%02x%02x%02x-%02x%02x%02x" % tuple(
            [_byte(c) for c in rgb] + [_byte(color[3])] + [_byte(d) for d in data])

    def cell(self, color, data):
        key = self.key(color, data)
        if key not in self.index:
            if len(self.keys) >= CAPACITY:
                raise RuntimeError("Palette is full (%d colors)" % CAPACITY)
            self.index[key] = len(self.keys)
            self.keys.append(key)
            self.dirty = True
        return self.index[key]

    @staticmethod
    def uv(cell):
        x, y = cell % COLUMNS, cell // COLUMNS
        return ((x + 0.5) / COLUMNS, (y + 0.5) / COLUMNS)

    def _image(self, name, colorspace):
        image = bpy.data.images.get(name)
        if image is None:
            image = bpy.data.images.new(name, SIZE, SIZE, alpha=True)
            image.generated_color = (0.0, 0.0, 0.0, 1.0)
        image.colorspace_settings.name = colorspace
        image.use_fake_user = True
        return image

    def write(self, need_data):
        if not self.dirty and self.color is not None and (self.data is not None or not need_data):
            return
        self.color = self._image(PALETTE_NAME, "sRGB" if self.srgb else "Non-Color")
        self.color.alpha_mode = 'STRAIGHT'
        self.color[KEYS_PROP] = json.dumps(self.keys)
        color_px = [0.0, 0.0, 0.0, 1.0] * (SIZE * SIZE)
        data_px = [0.5, 0.0, 0.5, 1.0] * (SIZE * SIZE)
        for cell, key in enumerate(self.keys):
            head, tail = key.split("-")
            rgba = [int(head[i:i + 2], 16) / 255.0 for i in range(0, 8, 2)]
            dat = [int(tail[i:i + 2], 16) / 255.0 for i in range(0, 6, 2)] + [1.0]
            cx, cy = cell % COLUMNS, cell // COLUMNS
            for y in range(cy * CELL, cy * CELL + CELL):
                row = (y * SIZE + cx * CELL) * 4
                color_px[row:row + CELL * 4] = rgba * CELL
                data_px[row:row + CELL * 4] = dat * CELL
        self.color.pixels = color_px
        self.color.pack(as_png=True)
        if need_data:
            self.data = self._image(DATA_NAME, "Non-Color")
            self.data.pixels = data_px
            self.data.pack(as_png=True)
        self.dirty = False


# ---------------------------------------------------------------------------
# Materiais de resultado
# ---------------------------------------------------------------------------

def _sig_text(sig):
    return json.dumps(sig, sort_keys=True)


def _find_result(sig_text):
    for mat in bpy.data.materials:
        if mat.get(SIG_PROP) == sig_text:
            return mat
    return None


def _build_pbr(mat, source, palette, sig):
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    nodes, links = tree.nodes, tree.links
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (700, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)
    src = None
    for node in source.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            src = node
            break
    bsdf.distribution = src.distribution
    bsdf.subsurface_method = src.subsurface_method
    for sock in bsdf.inputs:
        if sock.name in src.inputs and hasattr(sock, "default_value"):
            sock.default_value = src.inputs[sock.name].default_value
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = UV_NAME
    uv.location = (-700, 0)
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = palette.color
    tex.interpolation = 'Closest'
    tex.color_space = 'COLOR' if palette.srgb else 'NONE'
    tex.location = (-450, 150)
    data = nodes.new("ShaderNodeTexImage")
    data.image = palette.data
    data.interpolation = 'Closest'
    data.color_space = 'NONE'
    data.location = (-450, -150)
    split = nodes.new("ShaderNodeSeparateRGB")
    split.location = (-150, -150)
    links.new(uv.outputs["UV"], tex.inputs["Vector"])
    links.new(uv.outputs["UV"], data.inputs["Vector"])
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(data.outputs["Color"], split.inputs["Image"])
    links.new(split.outputs["R"], bsdf.inputs["Roughness"])
    links.new(split.outputs["G"], bsdf.inputs["Metallic"])
    links.new(split.outputs["B"], bsdf.inputs["Specular"])
    surface = bsdf.outputs["BSDF"]
    if sig["emission"] is not None:
        em = nodes.new("ShaderNodeEmission")
        em.location = (200, -350)
        em.inputs["Color"].default_value = sig["emission"][:4]
        em.inputs["Strength"].default_value = sig["emission"][4]
        add = nodes.new("ShaderNodeAddShader")
        add.location = (450, -100)
        links.new(surface, add.inputs[0])
        links.new(em.outputs["Emission"], add.inputs[1])
        surface = add.outputs["Shader"]
    if sig["transparent"]:
        trans = nodes.new("ShaderNodeBsdfTransparent")
        trans.location = (200, 250)
        mix = nodes.new("ShaderNodeMixShader")
        mix.location = (500, 100)
        links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
        links.new(trans.outputs["BSDF"], mix.inputs[1])
        links.new(surface, mix.inputs[2])
        surface = mix.outputs["Shader"]
        # O blend do jogo só liga com alpha < 1, mesmo vindo de nó.
        mat.use_transparency = True
        mat.alpha = min(mat.alpha, 0.999)
    links.new(surface, out.inputs["Surface"])


def _build_legacy(mat, palette, sig):
    for i in range(len(mat.texture_slots)):
        mat.texture_slots.clear(i)
    mat.diffuse_color = (1.0, 1.0, 1.0)
    tex = bpy.data.textures.get(PALETTE_NAME)
    if tex is None or tex.type != 'IMAGE':
        tex = bpy.data.textures.new(PALETTE_NAME, 'IMAGE')
    tex.image = palette.color
    tex.use_interpolation = False
    tex.use_mipmap = False
    tex.use_alpha = True
    slot = mat.texture_slots.add()
    slot.texture = tex
    slot.texture_coords = 'UV'
    slot.uv_layer = UV_NAME
    slot.use_map_color_diffuse = True
    slot.diffuse_color_factor = 1.0
    if sig["transparent"]:
        slot.use_map_alpha = True
        slot.alpha_factor = 1.0
        mat.use_transparency = True
        mat.alpha = 0.0


def result_material(source, palette, sig):
    text = _sig_text(sig)
    mat = _find_result(text)
    if mat is not None:
        return mat
    name = PALETTE_NAME + ("_Alpha" if sig["transparent"] else "")
    mat = source.copy()
    mat.name = name
    for key in list(mat.keys()):
        if key.startswith("_ae_recipe") or key == SIG_PROP:
            del mat[key]
    if sig["kind"] == "pbr":
        _build_pbr(mat, source, palette, sig)
    else:
        _build_legacy(mat, palette, sig)
    mat[SIG_PROP] = text
    return mat


# ---------------------------------------------------------------------------
# Conversão
# ---------------------------------------------------------------------------

def convert_objects(context, objects):
    """Converte objetos só com materiais lisos. Retorna (convertidos, pulados)."""
    palette = Palette(context.scene)
    plans = []
    skipped = []
    for ob in objects:
        mesh = ob.data
        problem = None
        if ob.library or mesh.library:
            problem = "linked data"
        elif mesh.get(BACKUP_KEY) is not None or UV_NAME in mesh.uv_textures:
            problem = "already converted (use Restore first)"
        elif len(mesh.uv_textures) >= 8:
            problem = "no free UV slot"
        elif not mesh.polygons or not ob.material_slots:
            problem = "no faces or materials"
        elif any(s.link == 'OBJECT' for s in ob.material_slots):
            problem = "object-linked material slots"
        infos = {}
        if problem is None:
            for index in used_slots(ob):
                info, reason = material_info(ob.material_slots[index].material, mesh)
                if info is None:
                    problem = "%s: %s" % (ob.material_slots[index].name or "slot", reason)
                    break
                infos[index] = info
        if problem:
            skipped.append((ob.name, problem))
        else:
            plans.append((ob, infos))

    # Primeiro reserva as cores; a imagem só é gravada uma vez.
    need_data = False
    cells = {}
    for ob, infos in plans:
        for index, (color, data, sig) in infos.items():
            cells[(ob.name, index)] = palette.cell(color, data)
            need_data |= sig["kind"] == "pbr"
    need_data |= palette.data is not None
    if plans:
        palette.write(need_data)

    done_meshes = {}
    converted = []
    for ob, infos in plans:
        source = ob.data
        if source.name in done_meshes:
            work = done_meshes[source.name]
            ob.data = work
            converted.append(ob.name)
            continue
        results = []
        remap = {}
        for index, (color, data, sig) in infos.items():
            mat = result_material(ob.material_slots[index].material, palette, sig)
            if mat not in results:
                results.append(mat)
            remap[index] = results.index(mat)
        work = source.copy()
        work.name = source.name + "_Palette"
        uv = work.uv_textures.new(UV_NAME)
        layer = work.uv_layers[uv.name]
        for poly in work.polygons:
            center = Palette.uv(cells[(ob.name, poly.material_index)])
            for li in poly.loop_indices:
                layer.data[li].uv = center
            poly.material_index = remap[poly.material_index]
        active = ob.active_material_index + 1
        work.materials.clear()
        for mat in results:
            work.materials.append(mat)
        work[BACKUP_KEY] = source
        work[BACKUP_SLOT_KEY] = active
        source.use_fake_user = True
        ob.data = work
        ob.active_material_index = 0
        done_meshes[source.name] = work
        converted.append(ob.name)
    return converted, skipped, len(palette.keys)


class MATERIAL_OT_anastacio_palette_atlas(Operator):
    """Combine flat-color materials (no textures) of the selected objects into one shared palette image"""
    bl_idname = "material.anastacio_palette_atlas"
    bl_label = "Palette Atlas"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and ob.type == 'MESH' and ob.mode == 'OBJECT'

    def execute(self, context):
        objects = [o for o in context.selected_objects if o.type == 'MESH']
        if context.object not in objects:
            objects.append(context.object)
        try:
            converted, skipped, colors = convert_objects(context, objects)
        except RuntimeError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        for name, reason in skipped:
            self.report({'WARNING'}, "%s skipped: %s" % (name, reason))
        if not converted:
            self.report({'ERROR'}, "No object converted")
            return {'CANCELLED'}
        self.report({'INFO'}, "Palette Atlas: %d object(s), %d color(s) in the scene palette"
                    % (len(converted), colors))
        return {'FINISHED'}


class MATERIAL_OT_anastacio_atlas_auto(Operator):
    """Pick Palette (flat-color materials) or Bake (textured materials) by itself"""
    bl_idname = "material.anastacio_atlas_auto"
    bl_label = "Build Material Atlas"
    bl_options = {'REGISTER', 'UNDO'}

    mode = bpy.props.EnumProperty(
        name="Mode",
        items=[('AUTO', "Auto", "Palette when every material is flat color, Bake otherwise"),
               ('PALETTE', "Palette Only", "Shared palette image; only flat-color materials"),
               ('BAKE', "Bake Only", "Bake every material to new maps (Cycles)")],
        default='AUTO')

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and ob.type == 'MESH' and ob.mode == 'OBJECT'

    def invoke(self, context, event):
        return self.execute_mode(context, invoke=True)

    def execute(self, context):
        return self.execute_mode(context, invoke=False)

    def execute_mode(self, context, invoke):
        mode = self.mode
        if mode == 'AUTO':
            summary = classify(context.object)
            mode = 'PALETTE' if summary and all(flat for _i, _n, flat, _r in summary) else 'BAKE'
        if mode == 'PALETTE':
            return bpy.ops.material.anastacio_palette_atlas()
        if invoke:
            return bpy.ops.material.anastacio_atlas_bake('INVOKE_DEFAULT')
        return bpy.ops.material.anastacio_atlas_bake()


classes = (
    MATERIAL_OT_anastacio_palette_atlas,
    MATERIAL_OT_anastacio_atlas_auto,
)
