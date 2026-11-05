# Track Tool: dados salvos no .range (PropertyGroups).
#
# Contrato em docs/plano-track-tool.md ("Contrato entre módulos", props.py).
# register()/unregister() são idempotentes: podem ser chamados mais de uma vez (pelo addon
# bl_operators/anastacio_track.py, por testes ou por reload do módulo).
import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       IntProperty, PointerProperty, StringProperty)

BAND_KINDS = [
    ('ASPHALT', "Asphalt", "Pista. A primeira faixa ASPHALT tem width = meia largura"),
    ('CURB', "Curb", "Guia/sarjeta: degrau (height) e topo (width)"),
    ('SIDEWALK', "Sidewalk", "Calçada, acostamento ou grama"),
    ('BORDER', "Border", "Mureta, guard-rail, grade ou muro (border_type)"),
    ('SLOPE', "Slope", "Talude: slope_deg > 0 sobe (corte), < 0 desce (aterro)"),
    ('HILL', "Hill", "Morro: height = altura, width = distância"),
    ('MESH', "Mesh", "Seção desenhada: Y local = lateral, Z = altura (mesh_object)"),
]
SIDES = [
    ('BOTH', "Both", "Os dois lados"),
    ('LEFT', "Left", "Só à esquerda (+lateral)"),
    ('RIGHT', "Right", "Só à direita"),
]
BORDER_TYPES = [
    ('NONE', "None", "Sem borda"),
    ('WALL', "Wall", "Mureta"),
    ('GUARDRAIL', "Guard-rail", "Guard-rail"),
    ('FENCE', "Fence", "Grade/alambrado"),
    ('HOUSE_WALL', "House Wall", "Muro de casas"),
]
# Em trechos, KEEP = mantém a borda da faixa (extra em relação ao contrato: enum não aceita vazio)
SEGMENT_BORDER_TYPES = [('KEEP', "Keep", "Mantém o tipo da faixa")] + BORDER_TYPES
RULE_KINDS = [
    ('HOUSES', "Houses", ""), ('TREES', "Trees", ""), ('POLES', "Poles", ""),
    ('SIGNS', "Signs", ""), ('KERBS', "Kerbs", ""), ('PEOPLE', "People", ""),
    ('CUSTOM', "Custom", ""),
]
BANK_MODES = [
    ('AUTO', "Auto", "Inclinação pela curvatura (ganho, limite e suavização)"),
    ('MANUAL', "Manual", "Usa bank_deg (+ = cai para a esquerda)"),
]


class RangeTrackBand(bpy.types.PropertyGroup):
    name = StringProperty(name="Name", default="Band")
    kind = EnumProperty(name="Kind", items=BAND_KINDS, default='ASPHALT')
    side = EnumProperty(name="Side", items=SIDES, default='BOTH')
    width = FloatProperty(name="Width", default=1.0, min=0.0, soft_max=500.0, unit='LENGTH',
                          description="Band width (ASPHALT: half width; MESH: asphalt half width in the section, reference for width_left/right)")
    height = FloatProperty(name="Height", default=0.0, soft_min=-5.0, soft_max=50.0, unit='LENGTH',
                           description="Step from the previous band (HILL: hill height)")
    slope_deg = FloatProperty(name="Slope", default=0.0, min=-89.0, max=89.0,
                              description="Slope: degrees, + goes up (cut), - goes down (fill)")
    material = PointerProperty(name="Material", type=bpy.types.Material)
    border_type = EnumProperty(name="Border", items=BORDER_TYPES, default='NONE')
    border_height = FloatProperty(name="Border Height", default=0.95, min=0.0, soft_max=10.0,
                                  unit='LENGTH')
    mesh_object = PointerProperty(name="Section Mesh", type=bpy.types.Object,
                                  description="Section mesh (MESH): local Y = side, Z = height")
    collision = BoolProperty(name="Collision", default=True)
    lane_count = IntProperty(name="Lanes", default=0, min=0, max=8,
                             description="Total driving lanes (dashed lines between them)")
    kerb_on_curves = BoolProperty(name="Kerb on Curves", default=False,
                                  description="Red and white kerb where the curve is tight")


class RangeTrackProfile(bpy.types.PropertyGroup):
    name = StringProperty(name="Name", default="Profile")
    symmetric = BoolProperty(name="Symmetric", default=True)
    bands = CollectionProperty(type=RangeTrackBand)
    active_band = IntProperty(default=0)  # extra: índice ativo para UIList


class RangeTrackPoint(bpy.types.PropertyGroup):
    index = IntProperty(name="Point", default=0, min=0)
    width_left = FloatProperty(name="Width Left", default=0.0, min=0.0, unit='LENGTH',
                               description="Asphalt half width on the left (0 = profile)")
    width_right = FloatProperty(name="Width Right", default=0.0, min=0.0, unit='LENGTH',
                                description="Asphalt half width on the right (0 = profile)")
    bank_mode = EnumProperty(name="Bank", items=BANK_MODES, default='AUTO')
    bank_deg = FloatProperty(name="Bank Angle", default=0.0, min=-45.0, max=45.0,
                             description="Degrees, + = falls to the left")
    surface = StringProperty(name="Surface", default="",
                             description="Surface from this point on (empty = keeps the previous one)")


class RangeTrackSegment(bpy.types.PropertyGroup):
    s_start = FloatProperty(name="Start", default=0.0, min=0.0, unit='LENGTH')
    s_end = FloatProperty(name="End", default=100.0, min=0.0, unit='LENGTH')
    side = EnumProperty(name="Side", items=SIDES, default='BOTH')
    band = StringProperty(name="Band", default="",
                          description="Name (or type) of the affected band")
    kind = StringProperty(name="Kind", default="",
                          description="Changes the band type (empty = keeps it)")
    width = FloatProperty(name="Width", default=-1.0, min=-1.0, unit='LENGTH',
                          description="New width (< 0 keeps it; 0 removes the band)")
    height = FloatProperty(name="Height", default=-1.0, min=-1.0, unit='LENGTH',
                           description="New step or height (< 0 keeps it)")
    slope_deg = FloatProperty(name="Slope", default=0.0, min=-89.0, max=89.0,
                              description="New slope in degrees (0 keeps it)")
    border_type = EnumProperty(name="Border", items=SEGMENT_BORDER_TYPES, default='KEEP')
    blend = FloatProperty(name="Blend", default=10.0, min=0.0, unit='LENGTH',
                          description="Transition (m) before s_start and after s_end")


class RangeTrackRule(bpy.types.PropertyGroup):
    kind = EnumProperty(name="Kind", items=RULE_KINDS, default='TREES')
    band = StringProperty(name="Band", default="")
    side = EnumProperty(name="Side", items=SIDES, default='BOTH')
    spacing = FloatProperty(name="Spacing", default=20.0, min=0.1, unit='LENGTH')
    density = FloatProperty(name="Density", default=0.5, min=0.0, max=1.0)
    offset = FloatProperty(name="Offset", default=2.0, unit='LENGTH')
    source_group = StringProperty(name="Group", default="")
    source_scene = StringProperty(name="Scene", default="")
    name_prefix = StringProperty(name="Name Prefix", default="")
    curve_min_deg = FloatProperty(name="Min Curve", default=0.0, min=0.0, max=180.0)
    seed = IntProperty(name="Seed", default=1)
    enabled = BoolProperty(name="Enabled", default=True)


class RangeTrackSettings(bpy.types.PropertyGroup):
    enabled = BoolProperty(name="Track", default=False)
    profile = StringProperty(name="Profile", default="")
    sample_step = FloatProperty(name="Sample Step", default=1.0, min=0.1, max=20.0, unit='LENGTH')
    chunk_length = FloatProperty(name="Chunk Length", default=75.0, min=5.0, max=1000.0,
                                 unit='LENGTH')
    uv_repeat = FloatProperty(name="UV Repeat", default=8.0, min=0.01, unit='LENGTH')
    bank_auto = BoolProperty(name="Auto Bank", default=True)
    bank_gain = FloatProperty(name="Bank Gain", default=0.08, min=0.0, max=1.0,
                              description="Bank degrees per degree of curve at the point")
    bank_max = FloatProperty(name="Bank Max", default=6.0, min=0.0, max=45.0)
    points = CollectionProperty(type=RangeTrackPoint)
    segments = CollectionProperty(type=RangeTrackSegment)
    rules = CollectionProperty(type=RangeTrackRule)
    terrain_enabled = BoolProperty(name="Terrain", default=True)
    terrain_margin = FloatProperty(name="Margin", default=260.0, min=0.0, unit='LENGTH')
    terrain_cell = FloatProperty(name="Cell", default=5.0, min=0.5, unit='LENGTH')
    hill_height = FloatProperty(name="Hill Height", default=28.0, min=0.0, unit='LENGTH')
    hill_scale = FloatProperty(name="Hill Scale", default=220.0, min=1.0, unit='LENGTH')
    horizon_enabled = BoolProperty(name="Horizon", default=True)
    # Light Probe Volumes ao longo da pista (probes.py)
    probe_spacing = FloatProperty(name="Probe Spacing", default=6.0, min=0.5, max=50.0, unit='LENGTH',
                                  description="Distance between the probes of the generated volumes")
    probe_height = FloatProperty(name="Height", default=4.0, min=0.0, unit='LENGTH',
                                 description="Height of the volumes above the track")
    probe_floor = FloatProperty(name="Below", default=1.0, min=0.0, unit='LENGTH',
                                description="Depth of the volumes below the track")
    probe_margin = FloatProperty(name="Side Margin", default=2.0, min=0.0, unit='LENGTH',
                                 description="Extra width beyond the covered band, on each side")
    probe_upto = EnumProperty(name="Cover Up To", default='BORDER', items=(
        ('ASPHALT', "Asphalt", "Only the asphalt"),
        ('SIDEWALK', "Sidewalk", "Up to the sidewalk"),
        ('BORDER', "Border", "Up to the border"),
    ))
    probe_quality = EnumProperty(name="Quality", default='MEDIUM', items=(
        ('LOW', "Low", "Up to 64 probes per volume"),
        ('MEDIUM', "Medium", "Up to 128 probes per volume"),
        ('HIGH', "High", "Up to 256 probes per volume"),
    ))
    probe_max_total = IntProperty(name="Probe Limit", default=15000, min=1,
                                  description="Total probes of all generated volumes")
    probe_max_turn = FloatProperty(name="Max Turn", default=15.0, min=1.0, max=180.0,
                                   description="Degrees of curve inside one volume")
    probe_max_waste = FloatProperty(name="Max Waste", default=2.5, min=1.0, max=50.0,
                                    description="Volume of a box divided by the volume of the band it covers")
    # extras (índices ativos para UIList)
    active_point = IntProperty(default=0)
    active_segment = IntProperty(default=0)
    active_rule = IntProperty(default=0)


class RangeTrackAnchor(bpy.types.PropertyGroup):
    track = StringProperty(name="Track", default="")
    s = FloatProperty(name="s", default=0.0, unit='LENGTH')
    side = IntProperty(name="Side", default=1, min=-1, max=1, description="-1 right, +1 left")
    offset = FloatProperty(name="Offset", default=1.0, unit='LENGTH',
                           description="Meters beyond the edge of the band")
    band = StringProperty(name="Band", default="BORDER")
    height = FloatProperty(name="Height", default=0.0, unit='LENGTH')
    follow_bank = BoolProperty(name="Follow Bank", default=False)
    enabled = BoolProperty(name="Enabled", default=False)


classes = (
    RangeTrackBand,
    RangeTrackProfile,
    RangeTrackPoint,
    RangeTrackSegment,
    RangeTrackRule,
    RangeTrackSettings,
    RangeTrackAnchor,
)


def _is_registered(cls):
    return 'bl_rna' in cls.__dict__


def register():
    if all(_is_registered(c) for c in classes) and hasattr(bpy.types.Object, "range_track"):
        return
    # tipos com o mesmo nome vindos de um import anterior (reload): tira antes
    for cls in reversed(classes):
        old = getattr(bpy.types, cls.__name__, None)
        if old is not None and old is not cls:
            try:
                bpy.utils.unregister_class(old)
            except Exception:
                pass
    for cls in classes:
        if not _is_registered(cls):
            bpy.utils.register_class(cls)
    bpy.types.Object.range_track = PointerProperty(type=RangeTrackSettings)
    bpy.types.Object.range_track_owner = StringProperty(
        name="Track Owner", default="",
        description="Track that generated this object (deleted when generating again)")
    bpy.types.Object.range_track_anchor = PointerProperty(type=RangeTrackAnchor)
    bpy.types.Scene.range_track_profiles = CollectionProperty(type=RangeTrackProfile)
    bpy.types.Scene.range_track_active_profile = IntProperty(default=0)  # extra p/ UIList


def unregister():
    for attr, owner in (("range_track", bpy.types.Object), ("range_track_owner", bpy.types.Object),
                        ("range_track_anchor", bpy.types.Object),
                        ("range_track_profiles", bpy.types.Scene),
                        ("range_track_active_profile", bpy.types.Scene)):
        if hasattr(owner, attr):
            try:
                delattr(owner, attr)
            except Exception:
                pass
    for cls in reversed(classes):
        if _is_registered(cls):
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass


# ---------------------------------------------------------------- materiais simples
# (nome, cor difusa, especular)
DEFAULT_MATERIALS = {
    'asphalt': ("Track_Asfalto", (0.16, 0.16, 0.17), 0.15),
    'curb': ("Track_Guia", (0.62, 0.61, 0.58), 0.1),
    'sidewalk': ("Track_Calcada", (0.55, 0.53, 0.49), 0.05),
    'dirt': ("Track_Terra", (0.42, 0.31, 0.20), 0.02),
    'grass': ("Track_Grama", (0.20, 0.42, 0.14), 0.02),
    'wall': ("Track_Mureta", (0.80, 0.79, 0.75), 0.05),
    'guardrail': ("Track_GuardRail", (0.70, 0.72, 0.74), 0.6),
    'fence': ("Track_Grade", (0.30, 0.32, 0.30), 0.3),
    'house_wall': ("Track_Muro", (0.85, 0.80, 0.70), 0.05),
    'kerb_red': ("Track_ZebraVermelha", (0.78, 0.10, 0.08), 0.1),
    'kerb_white': ("Track_ZebraBranca", (0.92, 0.92, 0.90), 0.1),
    'line': ("Track_Faixa", (0.95, 0.95, 0.92), 0.1),
    'slope': ("Track_Talude", (0.36, 0.40, 0.22), 0.02),
}


def ensure_material(role):
    """Material simples do Track Tool (cria ou repinta: a cor é sempre a da tabela)."""
    name, color, spec = DEFAULT_MATERIALS[role]
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.specular_intensity = spec
    return mat


def find_profile(name, scene=None):
    """Perfil pelo nome: primeiro na cena dada, depois em todas as cenas."""
    if not name:
        return None
    scenes = ([scene] if scene is not None else []) + [s for s in bpy.data.scenes if s != scene]
    for sc in scenes:
        profs = getattr(sc, "range_track_profiles", None)
        if profs is None:
            continue
        for p in profs:
            if p.name == name:
                return p
    return None


def track_scene(obj):
    """Cena do traçado (a primeira que o contém; senão a cena atual)."""
    try:
        if obj.users_scene:
            return obj.users_scene[0]
    except Exception:
        pass
    return bpy.context.scene


def track_profile(track_obj):
    st = track_obj.range_track
    return find_profile(st.profile, track_scene(track_obj))


def add_band(profile, name, kind, width=1.0, height=0.0, material=None, side='BOTH', **kw):
    b = profile.bands.add()
    b.name = name
    b.kind = kind
    b.side = side
    b.width = width
    b.height = height
    if material is not None:
        b.material = material
    for k, v in kw.items():
        setattr(b, k, v)
    return b


def default_profiles(scene=None, materials=None):
    """Cria na cena (se ainda não existirem) os perfis 'Rua de bairro', 'Estrada de serra' e
    'Autodromo'. materials: dict opcional papel -> Material (papéis de DEFAULT_MATERIALS:
    asphalt, curb, sidewalk, dirt, grass, wall, guardrail, fence, house_wall, slope). O que faltar
    é criado como material simples. Retorna a lista de nomes."""
    scene = scene or bpy.context.scene
    materials = materials or {}

    def m(role):
        mat = materials.get(role)
        return mat if mat is not None else ensure_material(role)

    profs = scene.range_track_profiles
    have = {p.name for p in profs}
    out = []

    name = "Rua de bairro"
    if name not in have:
        p = profs.add()
        p.name = name
        add_band(p, "Asfalto", 'ASPHALT', 4.94, material=m('asphalt'), lane_count=2)
        add_band(p, "Guia", 'CURB', 0.23, 0.17, material=m('curb'))
        add_band(p, "Calcada", 'SIDEWALK', 2.65, material=m('sidewalk'))
        add_band(p, "Mureta", 'BORDER', 0.3, material=m('wall'), border_type='WALL',
                 border_height=0.95)
        add_band(p, "Talude", 'SLOPE', 4.0, material=m('slope'), slope_deg=-15.0)
        add_band(p, "Morro", 'HILL', 200.0, 28.0, material=m('grass'))
    out.append(name)

    name = "Estrada de serra"
    if name not in have:
        p = profs.add()
        p.name = name
        add_band(p, "Asfalto", 'ASPHALT', 4.0, material=m('asphalt'), lane_count=2)
        add_band(p, "Acostamento", 'SIDEWALK', 1.2, -0.03, material=m('dirt'), collision=True)
        add_band(p, "GuardRail", 'BORDER', 0.4, material=m('guardrail'), border_type='GUARDRAIL',
                 border_height=0.8)
        add_band(p, "Talude", 'SLOPE', 6.0, material=m('slope'), slope_deg=-25.0)
        add_band(p, "Morro", 'HILL', 250.0, 40.0, material=m('grass'))
    out.append(name)

    name = "Autodromo"
    if name not in have:
        p = profs.add()
        p.name = name
        add_band(p, "Asfalto", 'ASPHALT', 6.0, material=m('asphalt'))
        add_band(p, "Zebra", 'CURB', 1.2, 0.04, material=m('curb'), kerb_on_curves=True)
        add_band(p, "Grama", 'SIDEWALK', 8.0, -0.04, material=m('grass'))
        add_band(p, "Grade", 'BORDER', 0.2, material=m('fence'), border_type='FENCE',
                 border_height=2.5)
        add_band(p, "Talude", 'SLOPE', 3.0, material=m('slope'), slope_deg=-10.0)
        add_band(p, "Morro", 'HILL', 200.0, 20.0, material=m('grass'))
    out.append(name)
    return out
