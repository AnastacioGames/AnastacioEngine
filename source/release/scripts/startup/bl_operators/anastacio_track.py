# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Track Tool: interface do editor (painel Track na barra N, operadores, overlay e modo Live).

O núcleo fica no pacote ``range_track`` (scripts/modules/range_track). Este arquivo só consome o
contrato de docs/plano-track-tool.md ("Contrato entre módulos"):
  props.register(), frames.sample(), layout.band_edges(), generate.generate(), convert.convert_curve_array(),
  decor.default_rules().
Se o pacote não importar, o painel mostra o erro e o resto do editor segue funcionando.

Formato dos presets (scripts/presets/range_track/*.json, e os do usuário em
<config>/scripts/presets/range_track/, gravados por "Save Preset"):

    {
      "format": "range_track_preset",      # obrigatório
      "version": 1,
      "name": "Rua de bairro",             # vira o nome do perfil na cena
      "description": "...",                 # opcional, texto livre
      "profile": {                          # RangeTrackProfile
        "symmetric": true,
        "bands": [                          # RangeTrackBand, do centro para fora
          {"name": "Asfalto", "kind": "ASPHALT", "side": "BOTH", "width": 3.5, "height": 0.0,
           "material": "Asfalto", "material_color": [0.15, 0.15, 0.16], "lane_count": 2, ...}
        ]
      },
      "settings": {"bank_auto": true, "bank_gain": 0.08, ...},   # RangeTrackSettings (só escalares)
      "rules": [{"kind": "TREES", "band": "Morro", "spacing": 12.0, ...}]   # RangeTrackRule
    }

Chaves com o mesmo nome das propriedades RNA do contrato. Chave desconhecida é ignorada (o preset
continua valendo se o props.py ganhar ou perder campos). Ponteiros (material, mesh_object) vão pelo
nome do datablock; "material_color" cria o material com essa cor se ele ainda não existir no arquivo.
Coleções (points, segments) não entram no preset: são do traçado, não do perfil.
"""

import json
import math
import os
import time
import traceback

import bpy
from bpy.app.handlers import persistent
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup, UIList
from mathutils import Vector

PRESET_SUBDIR = "range_track"
DEFAULT_PRESET = "Rua de bairro"
LIVE_DELAY = 0.4          # segundos sem mexer na curva antes de refazer a estrada no modo Live
OVERLAY_STEP = 2.0        # metros entre vértices das linhas do overlay
MARK_EVERY = 100.0        # marca de s na viewport
ARROW_EVERY = 25.0        # seta de inclinação

PARTS = {
    'ROAD': {'ROAD'},
    'TERRAIN': {'TERRAIN'},
    'DECOR': {'DECOR'},
    'BAKE': {'BAKE'},
    'ALL': {'ROAD', 'TERRAIN', 'DECOR', 'BAKE'},
}

# Ordem e visibilidade das propriedades de cada faixa no painel (o que não estiver aqui e existir
# no props.py aparece no fim, para o painel não esconder campo novo).
BAND_FIELDS = (
    ("kind", None), ("side", None), ("width", None), ("height", None), ("slope_deg", {'SLOPE', 'HILL', 'BORDER'}),
    ("material", None), ("lane_count", {'ASPHALT'}), ("kerb_on_curves", {'CURB', 'ASPHALT'}),
    ("border_type", {'BORDER'}), ("border_height", {'BORDER'}), ("mesh_object", {'MESH'}), ("collision", None),
)
SETTINGS_ROAD = ("sample_step", "chunk_length", "uv_repeat", "surface")
SETTINGS_BANK = ("bank_auto", "bank_gain", "bank_max")
SETTINGS_TERRAIN = ("terrain_enabled", "terrain_margin", "terrain_cell", "hill_height", "hill_scale", "horizon_enabled")
POINT_FIELDS = ("index", "width_left", "width_right", "bank_mode", "bank_deg", "surface")
SEGMENT_FIELDS = ("s_start", "s_end", "side", "band", "kind", "width", "height", "slope_deg", "border_type", "blend")
RULE_FIELDS = ("enabled", "kind", "band", "side", "spacing", "density", "offset", "source_group", "source_scene",
               "name_prefix", "curve_min_deg", "seed")
ANCHOR_FIELDS = ("enabled", "track", "s", "side", "band", "offset", "height", "follow_bank")

BAND_COLORS = {
    'ASPHALT': (0.95, 0.95, 0.95, 0.9),
    'CURB': (1.0, 0.85, 0.1, 0.9),
    'SIDEWALK': (0.7, 0.7, 0.75, 0.9),
    'BORDER': (1.0, 0.25, 0.2, 0.9),
    'SLOPE': (0.75, 0.5, 0.25, 0.8),
    'HILL': (0.3, 0.8, 0.3, 0.7),
    'MESH': (0.2, 0.8, 1.0, 0.9),
}
SEGMENT_COLORS = ((1.0, 0.3, 0.9, 1.0), (0.2, 1.0, 1.0, 1.0), (1.0, 0.6, 0.1, 1.0), (0.5, 0.4, 1.0, 1.0))
ID_COLLECTIONS = {'Material': "materials", 'Object': "objects", 'Group': "groups", 'Scene': "scenes",
                  'Image': "images", 'Text': "texts", 'Mesh': "meshes"}


# --------------------------------------------------------------------------------------------
# Acesso ao pacote range_track (tolerante)
# --------------------------------------------------------------------------------------------

_import_state = {"error": None, "checked": 0.0}
_registered_props = [False]


def _rt(sub):
    """Submódulo range_track.<sub>. Lança a exceção original se não importar."""
    import importlib
    return importlib.import_module("range_track." + sub)


MODULES = ("frames", "layout", "generate", "convert", "decor")


def import_error():
    """Erro que impede o painel (props.py não importa ou não registra), ou None.
    Refaz a checagem no máximo a cada 2 s. Os demais módulos são opcionais: ver module_errors()."""
    now = time.time()
    if now - _import_state["checked"] < 2.0:
        return _import_state["error"]
    _import_state["checked"] = now
    try:
        _rt("props")
        if not _has_rna(bpy.types.Object, "range_track"):
            _ensure_props()
        if not _has_rna(bpy.types.Object, "range_track"):
            raise RuntimeError("range_track.props.register() did not add Object.range_track")
        _import_state["error"] = None
    except Exception as ex:
        _import_state["error"] = "%s: %s" % (type(ex).__name__, ex)
    errors = {}
    for sub in MODULES:
        try:
            _rt(sub)
        except Exception as ex:
            errors[sub] = "%s: %s" % (type(ex).__name__, ex)
    _import_state["modules"] = errors
    return _import_state["error"]


def module_errors():
    """{submódulo: erro} dos módulos que não importaram (o botão que depende dele avisa ao rodar)."""
    import_error()
    return _import_state.get("modules", {})


def _has_rna(cls, name):
    try:
        return name in cls.bl_rna.properties
    except Exception:
        return False


def _ensure_props():
    """Registra as propriedades do props.py uma vez (quem registrar antes, ganha)."""
    if _has_rna(bpy.types.Object, "range_track"):
        return
    _rt("props").register()
    _registered_props[0] = True


def settings_of(ob):
    return getattr(ob, "range_track", None) if ob is not None else None


def is_track(ob):
    st = settings_of(ob)
    return ob is not None and ob.type == 'CURVE' and st is not None and bool(getattr(st, "enabled", False))


def is_curve_array(ob):
    if ob is None or ob.type != 'MESH':
        return False
    kinds = {m.type for m in ob.modifiers}
    return 'ARRAY' in kinds and 'CURVE' in kinds


def profile_of(scene, ob):
    st = settings_of(ob)
    profiles = getattr(scene, "range_track_profiles", None)
    if st is None or profiles is None:
        return None
    return profiles.get(st.profile)


def _anchor_of(ob):
    return getattr(ob, "range_track_anchor", None) if ob is not None else None


def _owner_of(ob):
    return getattr(ob, "range_track_owner", "") if ob is not None else ""


# --------------------------------------------------------------------------------------------
# RNA genérico: dicionário <-> PropertyGroup, chave para cache
# --------------------------------------------------------------------------------------------

def _props(struct):
    return [p for p in struct.bl_rna.properties if p.identifier != "rna_type"]


def pg_to_dict(pg):
    """Escalares, enums e ponteiros de ID (pelo nome) do PropertyGroup. Coleções ficam de fora."""
    out = {}
    for p in _props(pg):
        key = p.identifier
        if p.type == 'COLLECTION':
            continue
        value = getattr(pg, key)
        if p.type == 'POINTER':
            if isinstance(value, bpy.types.ID):
                out[key] = value.name
            elif value is None and p.fixed_type.identifier in ID_COLLECTIONS:
                out[key] = ""
            continue
        if p.type == 'ENUM' and p.is_enum_flag:
            value = sorted(value)
        elif p.type in {'FLOAT', 'INT', 'BOOLEAN'} and getattr(p, "array_length", 0):
            value = list(value)
        out[key] = value
    return out


def dict_to_pg(pg, data, warnings=None):
    """Aplica as chaves conhecidas; ignora as desconhecidas e os valores que o RNA recusar."""
    for key, value in data.items():
        p = pg.bl_rna.properties.get(key)
        if p is None or p.is_readonly or p.type == 'COLLECTION':
            continue
        try:
            if p.type == 'POINTER':
                coll = ID_COLLECTIONS.get(p.fixed_type.identifier)
                if coll is None:
                    continue
                value = getattr(bpy.data, coll).get(value) if value else None
            elif p.type == 'ENUM' and p.is_enum_flag:
                value = set(value)
            setattr(pg, key, value)
        except Exception as ex:
            if warnings is not None:
                warnings.append("%s=%r: %s" % (key, value, ex))


def rna_key(struct, depth=3):
    """Tupla com todos os valores do struct (coleções inclusive). Serve de chave de cache."""
    if struct is None:
        return None
    out = []
    for p in _props(struct):
        value = getattr(struct, p.identifier)
        if p.type == 'COLLECTION':
            out.append(tuple(rna_key(item, depth - 1) for item in value) if depth > 0 else len(value))
        elif p.type == 'POINTER':
            out.append(value.name if isinstance(value, bpy.types.ID) else
                       (rna_key(value, depth - 1) if value is not None and depth > 0 else None))
        elif p.type == 'ENUM' and p.is_enum_flag:
            out.append(tuple(sorted(value)))
        elif getattr(p, "array_length", 0):
            out.append(tuple(value))
        else:
            out.append(value)
    return tuple(out)


def curve_key(ob):
    """Tupla dos pontos do traçado (pontos, alças, tilt, cíclico) + matriz. Muda quando a curva muda."""
    vals = [tuple(tuple(r) for r in ob.matrix_world)]
    for sp in ob.data.splines:
        vals.append((sp.type, sp.use_cyclic_u, sp.resolution_u))
        bp = sp.bezier_points
        n = len(bp)
        if n:
            buf = [0.0] * (n * 3)
            for attr in ("co", "handle_left", "handle_right"):
                bp.foreach_get(attr, buf)
                vals.append(tuple(buf))
            tilt = [0.0] * n
            bp.foreach_get("tilt", tilt)
            vals.append(tuple(tilt))
        pts = sp.points
        if len(pts):
            buf = [0.0] * (len(pts) * 4)
            pts.foreach_get("co", buf)
            vals.append(tuple(buf))
    return hash(tuple(vals))


def track_key(scene, ob):
    """Curva + configuração do traçado + perfil em uso."""
    return (curve_key(ob), hash(rna_key(settings_of(ob))), hash(rna_key(profile_of(scene, ob))))


# --------------------------------------------------------------------------------------------
# Presets
# --------------------------------------------------------------------------------------------

def preset_dirs():
    try:
        return bpy.utils.preset_paths(PRESET_SUBDIR)
    except Exception:
        return []


def preset_files():
    """[(caminho, nome)] de todos os presets (sistema e usuário). O do usuário vence no mesmo nome."""
    found = {}
    for directory in preset_dirs():
        for fn in sorted(os.listdir(directory)):
            if not fn.lower().endswith(".json"):
                continue
            path = os.path.join(directory, fn)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("format") != "range_track_preset":
                    continue
                name = data.get("name") or os.path.splitext(fn)[0]
            except Exception:
                continue
            found[name] = path
    return sorted(((path, name) for name, path in found.items()), key=lambda it: it[1].lower())


def read_preset(name_or_path):
    path = name_or_path
    if not os.path.isfile(path):
        path = next((p for p, n in preset_files() if n == name_or_path), None)
        if path is None:
            raise FileNotFoundError("Track preset not found: %s" % name_or_path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("format") != "range_track_preset":
        raise ValueError("Not a track preset: %s" % path)
    return data


def _ensure_material(name, color, texture=None):
    if not name:
        return
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        if color:
            mat.diffuse_color = color[:3]
    if texture:
        from range_track import textures
        textures.textured_material(mat, texture)


def apply_profile(scene, data, warnings=None):
    """Cria ou substitui na cena o perfil descrito em data["profile"]. Retorna o perfil."""
    name = data.get("name") or "Profile"
    profiles = scene.range_track_profiles
    profile = profiles.get(name)
    if profile is None:
        profile = profiles.add()
        profile.name = name
    prof = data.get("profile", {})
    dict_to_pg(profile, {k: v for k, v in prof.items() if k != "bands"}, warnings)
    profile.name = name
    profile.bands.clear()
    for band_data in prof.get("bands", []):
        _ensure_material(band_data.get("material"), band_data.get("material_color"),
                         band_data.get("texture"))
        band = profile.bands.add()
        dict_to_pg(band, band_data, warnings)
    return profile


def apply_preset(scene, track_ob, data, settings=True, rules=True, warnings=None):
    profile = apply_profile(scene, data, warnings)
    st = settings_of(track_ob)
    if st is None:
        return profile
    st.profile = profile.name
    if settings and data.get("settings"):
        dict_to_pg(st, {k: v for k, v in data["settings"].items() if k not in {"enabled", "profile"}}, warnings)
    if rules and "rules" in data:
        st.rules.clear()
        for rule_data in data["rules"]:
            dict_to_pg(st.rules.add(), rule_data, warnings)
    return profile


def preset_from_track(scene, track_ob, name):
    st = settings_of(track_ob)
    profile = profile_of(scene, track_ob)
    if profile is None:
        raise ValueError("Track has no profile")
    prof = {k: v for k, v in pg_to_dict(profile).items() if k != "name"}
    bands = []
    for band in profile.bands:
        d = pg_to_dict(band)
        mat = getattr(band, "material", None)
        if mat is not None:
            d["material_color"] = [round(c, 4) for c in mat.diffuse_color]
        bands.append(d)
    prof["bands"] = bands
    settings = {k: v for k, v in pg_to_dict(st).items() if k not in {"enabled", "profile"}}
    return {
        "format": "range_track_preset", "version": 1, "name": name,
        "profile": prof, "settings": settings, "rules": [pg_to_dict(r) for r in st.rules],
    }


def ensure_default_profile(scene, track_ob):
    """Garante que o traçado aponte para um perfil existente (o primeiro da cena ou o preset padrão)."""
    st = settings_of(track_ob)
    profiles = scene.range_track_profiles
    if st.profile and st.profile in profiles:
        return profiles[st.profile]
    if len(profiles):
        st.profile = profiles[0].name
        return profiles[0]
    try:
        data = read_preset(DEFAULT_PRESET)
    except Exception:
        data = {"name": "Default", "profile": {"bands": [
            {"name": "Asphalt", "kind": "ASPHALT", "width": 4.0},
            {"name": "Curb", "kind": "CURB", "width": 0.3, "height": 0.15},
            {"name": "Sidewalk", "kind": "SIDEWALK", "width": 2.0}]}}
    profile = apply_profile(scene, data)
    st.profile = profile.name
    return profile


# --------------------------------------------------------------------------------------------
# Geração e relatório
# --------------------------------------------------------------------------------------------

def owned_objects(scene, track_ob):
    return [ob for ob in scene.objects if _owner_of(ob) == track_ob.name]


def generation_report(scene, track_ob, parts, seconds, result=None):
    """(texto, objetos do traçado, faces do traçado, avisos). result = dict devolvido por generate()."""
    objs = owned_objects(scene, track_ob)
    faces = sum(len(ob.data.polygons) for ob in objs if ob.type == 'MESH' and ob.data is not None)
    if set(parts) >= {'ROAD', 'TERRAIN', 'DECOR', 'BAKE'}:
        label = "All"
    else:
        label = "+".join(p.title() for p in sorted(parts))
    if isinstance(result, dict) and parts != {'BAKE'}:
        text = tip_("%s: %d objects, %d faces in %.2f s (track total: %d objects, %d faces)") % (
            label, result.get("objects", 0), result.get("faces", 0), seconds, len(objs), faces)
    else:
        text = tip_("%s: %d objects, %d faces, %.2f s") % (label, len(objs), faces, seconds)
    if 'BAKE' in parts:
        baked = bpy.data.texts.get("TRACK_%s.json" % track_ob.name)
        text += tip_("; baked %s") % (baked.name if baked else tip_("nothing"))
    warnings = list(result.get("warnings", ())) if isinstance(result, dict) else []
    return text, len(objs), faces, warnings


def run_generate(scene, track_ob, parts):
    """Chama generate.generate e grava o relatório (e os avisos) no estado de UI do traçado.
    Retorna (texto, objetos, faces, avisos)."""
    t0 = time.perf_counter()
    result = _rt("generate").generate(track_ob, parts=set(parts))
    seconds = time.perf_counter() - t0
    report = generation_report(scene, track_ob, set(parts), seconds, result)
    ui = getattr(track_ob, "range_track_ui", None)
    if ui is not None:
        ui.report = report[0]
        ui.error = ("\n".join(tip_("Warning: %s") % w for w in report[3]))[:1000]
    _overlay_cache.pop(track_ob.name, None)
    return report


def _set_error(track_ob, text):
    ui = getattr(track_ob, "range_track_ui", None)
    if ui is not None:
        ui.error = text[:1000]


# --------------------------------------------------------------------------------------------
# Modo Live: refaz só ROAD depois de LIVE_DELAY s sem mexer na curva
# --------------------------------------------------------------------------------------------

_live = {}          # nome do traçado -> {"key", "changed_at", "built"}
_live_busy = [False]
_clock = time.time  # trocado nos testes


def live_enabled(track_ob):
    return track_ob is not None and track_ob.name in _live


def live_set(scene, track_ob, on):
    if on:
        key = track_key(scene, track_ob)
        _live[track_ob.name] = {"key": key, "changed_at": _clock(), "built": key}
    else:
        _live.pop(track_ob.name, None)


def live_tick(scene):
    """Confere os traçados em Live. Retorna os nomes refeitos neste passo."""
    if _live_busy[0] or not _live or scene is None:
        return []
    rebuilt = []
    now = _clock()
    for name in list(_live):
        state = _live[name]
        ob = scene.objects.get(name)
        if ob is None or not is_track(ob):
            if name not in bpy.data.objects:
                _live.pop(name, None)
            continue
        try:
            key = track_key(scene, ob)
        except Exception:
            continue
        if key != state["key"]:
            state["key"] = key
            state["changed_at"] = now
            continue
        if key == state["built"] or now - state["changed_at"] < LIVE_DELAY:
            continue
        state["built"] = key
        _live_busy[0] = True
        try:
            report = run_generate(scene, ob, {'ROAD'})
            failed = [w for w in report[3] if "ROAD" in w]
            if failed:
                raise RuntimeError(failed[0])
            rebuilt.append(name)
        except Exception as ex:
            traceback.print_exc()
            _live.pop(name, None)
            _set_error(ob, tip_("Live turned off: %s") % ex)
        finally:
            _live_busy[0] = False
    return rebuilt


@persistent
def _scene_update_post(scene):
    if _live:
        live_tick(scene)


@persistent
def _load_post(_dummy):
    _live.clear()
    _overlay_cache.clear()


# --------------------------------------------------------------------------------------------
# Overlay (bgl): linhas calculadas uma vez por estado da curva/perfil
# --------------------------------------------------------------------------------------------

_overlay_cache = {}     # nome -> (chave, linhas ou None, erro)
_draw_handles = []


# Lados como o layout.py espera: +1 = esquerda (+lat), -1 = direita.
LEFT, RIGHT = 1, -1


def _sides(side_enum):
    return {'LEFT': (LEFT,), 'RIGHT': (RIGHT,)}.get(side_enum, (LEFT, RIGHT))


def _strips(points):
    """Quebra uma lista com None (faixa ausente naquele trecho) em polilinhas contínuas."""
    out, cur = [], []
    for p in points:
        if p is None:
            if len(cur) > 1:
                out.append(cur)
            cur = []
        else:
            cur.append(p)
    if len(cur) > 1:
        out.append(cur)
    return out


class _CoarseSettings:
    """RangeTrackSettings com outro sample_step (o resto vem do original)."""

    def __init__(self, settings, step):
        self._settings = settings
        self.sample_step = step

    def __getattr__(self, name):
        return getattr(self._settings, name)


def overlay_lines(scene, track_ob):
    """Linhas do overlay no mundo. Dicionário:
      strips: [(cor, [Vector, ...])]   bordas das faixas, linha central e trechos (GL_LINE_STRIP)
      lines: [(cor, [(a, b), ...])]    marcas de s e setas de inclinação (GL_LINES)
      labels: [(Vector, texto)]        texto das marcas e dos trechos (POST_PIXEL)
    """
    frames_mod, layout_mod = _rt("frames"), _rt("layout")
    st = settings_of(track_ob)
    profile = profile_of(scene, track_ob)
    if profile is None:
        raise ValueError("profile '%s' not found" % st.profile)
    # Amostragem própria, mais grossa que a da geração: o overlay só precisa do desenho
    coarse = _CoarseSettings(st, max(st.sample_step, OVERLAY_STEP))
    fr = frames_mod.sample(track_ob, coarse, profile)
    ed = layout_mod.band_edges(fr, profile, coarse)
    s_list = fr.s
    n = len(s_list)
    out = {"strips": [], "lines": [], "labels": []}
    if n < 2:
        return out
    step = 1
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    if fr.cyclic:
        idx.append(0)       # fecha o laço
    lift = 0.05

    def at(i, side, off, z):
        return ed.world(i, side * off, z + lift)

    # Borda externa de cada faixa (o morro fica de fora: longe demais e só polui a vista)
    for band in profile.bands:
        if band.kind == 'HILL':
            continue
        color = BAND_COLORS.get(band.kind, (1.0, 1.0, 1.0, 0.8))
        for side in _sides(band.side):
            pts = []
            for i in idx:
                t = ed.band(i, side, band.name)
                pts.append(None if t is None else at(i, side, t[1], t[3]))
            for strip in _strips(pts):
                out["strips"].append((color, strip))
    # Linha central
    out["strips"].append(((1.0, 1.0, 0.4, 0.6), [fr.pos[i] + fr.up[i] * lift for i in idx]))

    def index_at(target, j):
        while j < n - 1 and s_list[j] < target:
            j += 1
        return j

    # Marcas de s a cada MARK_EVERY m, atravessando até a borda (BORDER ou a última faixa da pista)
    marks, j, mark = [], 0, 0.0
    while mark <= fr.length + 1e-6:
        j = index_at(mark, j)
        a, b = ed.outer(j, LEFT, 'BORDER'), ed.outer(j, RIGHT, 'BORDER')
        marks.append((at(j, LEFT, a[0], a[1]), at(j, RIGHT, b[0], b[1])))
        out["labels"].append((fr.pos[j] + Vector((0.0, 0.0, 1.5)), "%d m" % int(round(mark))))
        mark += MARK_EVERY
    out["lines"].append(((1.0, 1.0, 1.0, 1.0), marks))

    # Setas de inclinação: do centro para o lado mais baixo, comprimento pelo ângulo.
    # bank + = cai para a esquerda (frames.py é a única regra de sinal).
    arrows, j, target = [], 0, 0.0
    while target <= fr.length:
        j = index_at(target, j)
        deg = math.degrees(fr.bank[j])
        if abs(deg) >= 0.25:
            d = fr.lat[j] * (1.0 if deg > 0 else -1.0)
            base = fr.pos[j] + fr.up[j] * 0.3
            tip = base + d * (1.5 + abs(deg) * 0.6)
            back, wing = d * -0.6, fr.tan[j] * 0.4
            arrows += [(base, tip), (tip, tip + back + wing), (tip, tip + back - wing)]
        target += ARROW_EVERY
    out["lines"].append(((0.3, 0.7, 1.0, 1.0), arrows))

    # Trechos coloridos: linha 0,5 m acima da borda, de s_start a s_end
    for k, seg in enumerate(st.segments):
        color = SEGMENT_COLORS[k % len(SEGMENT_COLORS)]
        s0, s1 = min(seg.s_start, seg.s_end), max(seg.s_start, seg.s_end)
        sel = [i for i in range(0, n, step) if s0 <= s_list[i] <= s1]
        if len(sel) < 2:
            continue
        for side in _sides(seg.side):
            pts = []
            for i in sel:
                off, z = ed.outer(i, side, 'BORDER')
                pts.append(at(i, side, off, z + 0.5))
            out["strips"].append((color, pts))
        mid = sel[len(sel) // 2]
        out["labels"].append((fr.pos[mid] + Vector((0.0, 0.0, 2.5)),
                              "%s %.0f-%.0f m" % (seg.band or seg.kind or tip_("segment"), s0, s1)))
    return out


def cached_overlay(scene, track_ob):
    try:
        key = track_key(scene, track_ob)
    except Exception:
        return None
    hit = _overlay_cache.get(track_ob.name)
    if hit is not None and hit[0] == key:
        return hit[1]
    try:
        lines = overlay_lines(scene, track_ob)
        _overlay_cache[track_ob.name] = (key, lines, "")
    except Exception as ex:
        # Guarda o erro com a mesma chave: não tenta de novo a cada redraw.
        _overlay_cache[track_ob.name] = (key, None, str(ex))
        print("Track overlay (%s): %s" % (track_ob.name, ex))
        lines = None
    return lines


def _overlay_tracks(context):
    scene = context.scene
    if scene is None or not getattr(scene, "range_track_overlay", False) or import_error():
        return []
    return [ob for ob in scene.objects if ob.type == 'CURVE' and is_track(ob) and ob.is_visible(scene)]


def _draw_overlay_view():
    import bgl
    context = bpy.context
    try:
        tracks = _overlay_tracks(context)
    except Exception:
        return
    if not tracks:
        return
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glLineWidth(2.0)
    for ob in tracks:
        data = cached_overlay(context.scene, ob)
        if not data:
            continue
        for color, pts in data["strips"]:
            bgl.glColor4f(*color)
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for p in pts:
                bgl.glVertex3f(p.x, p.y, p.z)
            bgl.glEnd()
        for color, segs in data["lines"]:
            bgl.glColor4f(*color)
            bgl.glBegin(bgl.GL_LINES)
            for a, b in segs:
                bgl.glVertex3f(a.x, a.y, a.z)
                bgl.glVertex3f(b.x, b.y, b.z)
            bgl.glEnd()
    bgl.glLineWidth(1.0)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(1.0, 1.0, 1.0, 1.0)


def _draw_overlay_text():
    import blf
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    context = bpy.context
    try:
        tracks = _overlay_tracks(context)
    except Exception:
        return
    region, rv3d = context.region, context.region_data
    if not tracks or region is None or rv3d is None:
        return
    font = 0
    blf.size(font, 11, 72)
    for ob in tracks:
        data = cached_overlay(context.scene, ob)
        if not data:
            continue
        for p, text in data["labels"]:
            xy = location_3d_to_region_2d(region, rv3d, p)
            if xy is None:
                continue
            blf.position(font, xy.x, xy.y, 0)
            blf.draw(font, text)


# --------------------------------------------------------------------------------------------
# Estado de UI salvo no objeto (índices das listas e relatório)
# --------------------------------------------------------------------------------------------

class RangeTrackUIState(PropertyGroup):
    band_index: IntProperty(name="Band", min=0)
    point_index: IntProperty(name="Point", min=0)
    segment_index: IntProperty(name="Segment", min=0)
    rule_index: IntProperty(name="Rule", min=0)
    report: StringProperty(name="Last Generation", description="Result of the last generation")
    error: StringProperty(name="Error", description="Last error of the Track Tool on this track")


# --------------------------------------------------------------------------------------------
# Operadores
# --------------------------------------------------------------------------------------------

def _active_track(context):
    ob = context.active_object
    return ob if is_track(ob) else None


class _TrackOp:
    @classmethod
    def poll(cls, context):
        return import_error() is None and _active_track(context) is not None


def _to_object_mode(context):
    """Sai do modo de edição para ler a curva atualizada; retorna o modo para voltar depois."""
    mode = context.mode
    if mode != 'OBJECT' and context.active_object is not None:
        bpy.ops.object.mode_set(mode='OBJECT')
    return mode


def _restore_mode(context, track_ob, mode):
    if mode == 'EDIT_CURVE' and track_ob.name in context.scene.objects:
        context.scene.objects.active = track_ob
        try:
            bpy.ops.object.mode_set(mode='EDIT')
        except Exception:
            pass


def make_track(scene, ob):
    st = settings_of(ob)
    st.enabled = True
    ensure_default_profile(scene, ob)
    if ob.data.dimensions != '3D':
        ob.data.dimensions = '3D'
    return ob


class RANGE_TRACK_OT_make(Operator):
    """Turn the active Curve into a track (road/racing track generated from the curve and a profile)"""
    bl_idname = "range_track.make"
    bl_label = "Make Track"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return import_error() is None and ob is not None and ob.type == 'CURVE'

    def execute(self, context):
        ob = make_track(context.scene, context.active_object)
        self.report({'INFO'}, tip_("Track: %s, profile %s") % (ob.name, settings_of(ob).profile))
        return {'FINISHED'}


class RANGE_TRACK_OT_add(Operator):
    """Add a Bezier curve already set up as a track with the default profile"""
    bl_idname = "range_track.add"
    bl_label = "Track"
    bl_options = {'REGISTER', 'UNDO'}

    length: FloatProperty(name="Length", default=300.0, min=10.0, unit='LENGTH',
                          description="Length of the starting curve")

    @classmethod
    def poll(cls, context):
        return import_error() is None

    def execute(self, context):
        scene = context.scene
        if context.mode != 'OBJECT' and context.active_object is not None:
            bpy.ops.object.mode_set(mode='OBJECT')
        cu = bpy.data.curves.new("Track", 'CURVE')
        cu.dimensions = '3D'
        sp = cu.splines.new('BEZIER')
        L = self.length
        pts = ((0.0, 0.0), (L * 0.3, 0.0), (L * 0.65, L * 0.15), (L, L * 0.15))
        sp.bezier_points.add(len(pts) - 1)
        for bp, (x, y) in zip(sp.bezier_points, pts):
            bp.co = (x, y, 0.0)
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
        ob = bpy.data.objects.new("Track", cu)
        ob.location = scene.cursor_location
        scene.objects.link(ob)
        for other in scene.objects:
            other.select = False
        ob.select = True
        scene.objects.active = ob
        make_track(scene, ob)
        return {'FINISHED'}


class RANGE_TRACK_OT_convert(Operator):
    """Turn a mesh deformed by Array + Curve modifiers into a track (keeps the curve and the cross-section)"""
    bl_idname = "range_track.convert"
    bl_label = "Convert Curve+Array to Track"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return import_error() is None and is_curve_array(context.active_object)

    def execute(self, context):
        scene = context.scene
        src = context.active_object
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            curve_ob = _rt("convert").convert_curve_array(src)
        except Exception as ex:
            traceback.print_exc()
            self.report({'ERROR'}, tip_("Convert failed: %s") % ex)
            return {'CANCELLED'}
        if curve_ob is None:
            self.report({'ERROR'}, tip_("Convert returned no curve"))
            return {'CANCELLED'}
        if curve_ob.name in scene.objects:
            for ob in scene.objects:
                ob.select = False
            curve_ob.select = True
            scene.objects.active = curve_ob
        self.report({'INFO'}, tip_("Converted %s to track %s (profile %s)") % (
            src.name, curve_ob.name, getattr(settings_of(curve_ob), "profile", "")))
        return {'FINISHED'}


class RANGE_TRACK_OT_generate(_TrackOp, Operator):
    """Generate the parts of the active track (only objects made by this track are replaced)"""
    bl_idname = "range_track.generate"
    bl_label = "Generate Track"
    bl_options = {'REGISTER', 'UNDO'}

    parts: EnumProperty(name="Parts", default='ALL', items=(
        ('ROAD', "Road", "Asphalt, curbs, sidewalks, borders and their collision"),
        ('TERRAIN', "Terrain", "Slopes, hills and far terrain"),
        ('DECOR', "Decoration", "Objects placed by the rules, and anchored objects"),
        ('BAKE', "Bake Track Data", "Table read by the game (distance, sides, bank)"),
        ('ALL', "All", "Road, terrain, decoration and track data"),
    ))

    def execute(self, context):
        track = _active_track(context)
        scene = context.scene
        mode = _to_object_mode(context)
        selected = [ob for ob in scene.objects if ob.select]
        try:
            text, _objs, _faces, warnings = run_generate(scene, track, PARTS[self.parts])
        except Exception as ex:
            traceback.print_exc()
            _set_error(track, "%s: %s" % (type(ex).__name__, ex))
            self.report({'ERROR'}, tip_("Track generation failed: %s") % ex)
            return {'CANCELLED'}
        finally:
            for ob in scene.objects:
                ob.select = ob in selected
            if track.name in scene.objects:
                scene.objects.active = track
            _restore_mode(context, track, mode)
        if warnings:
            self.report({'WARNING'}, "%s; %s" % (text, "; ".join(warnings)[:300]))
        else:
            self.report({'INFO'}, text)
        return {'FINISHED'}


class RANGE_TRACK_OT_live_watch(Operator):
    """Keep regenerating the road of tracks in Live mode a moment after the curve stops changing"""
    bl_idname = "range_track.live_watch"
    bl_label = "Track Live Watch"
    bl_options = {'INTERNAL'}

    _timer = None
    _running = [False]

    def modal(self, context, event):
        if not _live:
            context.window_manager.event_timer_remove(self._timer)
            self._running[0] = False
            return {'FINISHED'}
        if event.type == 'TIMER':
            if live_tick(context.scene) and context.area is not None:
                context.area.tag_redraw()
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        if self._running[0] or context.window is None:
            return {'CANCELLED'}
        self._running[0] = True
        self._timer = context.window_manager.event_timer_add(0.1, context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        return self.invoke(context, None)


class RANGE_TRACK_OT_live_toggle(_TrackOp, Operator):
    """Rebuild only the road a moment after each edit of the curve, the profile or the track settings"""
    bl_idname = "range_track.live_toggle"
    bl_label = "Live"
    bl_options = {'REGISTER'}

    def execute(self, context):
        track = _active_track(context)
        on = not live_enabled(track)
        live_set(context.scene, track, on)
        if on:
            ui = getattr(track, "range_track_ui", None)
            if ui is not None:
                ui.error = ""
            # Força a primeira geração depois da espera
            _live[track.name]["built"] = None
            if context.window is not None:
                bpy.ops.range_track.live_watch('INVOKE_DEFAULT')
        return {'FINISHED'}


# Índice ativo de cada lista: o props.py tem campos extras para isso (active_band, active_point...);
# se sumirem, o estado de UI deste arquivo (range_track_ui) assume.
INDEX_ATTRS = {'BANDS': "active_band", 'POINTS': "active_point", 'SEGMENTS': "active_segment", 'RULES': "active_rule"}
UI_INDEX_ATTRS = {'BANDS': "band_index", 'POINTS': "point_index", 'SEGMENTS': "segment_index", 'RULES': "rule_index"}


def list_index_owner(track, profile, target):
    """(dono, nome do índice) da lista target."""
    owner = profile if target == 'BANDS' else settings_of(track)
    attr = INDEX_ATTRS[target]
    if owner is not None and attr in owner.bl_rna.properties:
        return owner, attr
    return track.range_track_ui, UI_INDEX_ATTRS[target]


def _list_target(context, target):
    """(coleção, dono do índice, nome do índice) do alvo das listas do painel."""
    track = _active_track(context)
    st = settings_of(track)
    profile = profile_of(context.scene, track)
    if target == 'BANDS':
        coll = profile.bands if profile else None
    else:
        coll = getattr(st, {'POINTS': "points", 'SEGMENTS': "segments", 'RULES': "rules"}[target])
    owner, attr = list_index_owner(track, profile, target)
    return coll, owner, attr


def selected_bezier_index(ob):
    """Índice do primeiro ponto Bezier selecionado na 1ª spline Bezier (a que o frames.py usa), ou None."""
    for sp in ob.data.splines:
        if sp.type == 'BEZIER' and len(sp.bezier_points) >= 2:
            for k, bp in enumerate(sp.bezier_points):
                if bp.select_control_point:
                    return k
            return None
    return None


class RANGE_TRACK_OT_list_action(_TrackOp, Operator):
    """Add, remove or move an item of the track lists"""
    bl_idname = "range_track.list_action"
    bl_label = "Track List"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    target: EnumProperty(items=(('BANDS', "Bands", ""), ('POINTS', "Points", ""),
                                ('SEGMENTS', "Segments", ""), ('RULES', "Rules", "")))
    action: EnumProperty(items=(('ADD', "Add", ""), ('REMOVE', "Remove", ""),
                                ('UP', "Up", ""), ('DOWN', "Down", "")))

    def execute(self, context):
        coll, owner, attr = _list_target(context, self.target)
        if coll is None:
            self.report({'WARNING'}, tip_("The track has no profile"))
            return {'CANCELLED'}
        index = getattr(owner, attr)
        n = len(coll)
        if self.action == 'ADD':
            track = _active_track(context)
            if self.target == 'POINTS':
                # No modo de edição usa o ponto Bezier selecionado; se ele já tem item, só seleciona o item
                used = [p.index for p in coll]
                sel = selected_bezier_index(track) if context.mode == 'EDIT_CURVE' else None
                if sel is not None and sel in used:
                    setattr(owner, attr, used.index(sel))
                    self.report({'INFO'}, tip_("Point %d already has settings") % sel)
                    return {'FINISHED'}
                if sel is None:
                    sel = next(k for k in range(len(used) + 1) if k not in used)
            item = coll.add()
            if self.target == 'BANDS':
                item.name = "Band %d" % len(coll)
            elif self.target == 'POINTS':
                item.index = sel
            elif self.target == 'SEGMENTS':
                fr_len = None
                try:
                    fr_len = _rt("frames").sample(track, settings_of(track)).length
                except Exception:
                    pass
                if fr_len:
                    item.s_start, item.s_end = 0.0, min(100.0, fr_len)
            # O item novo entra logo abaixo do selecionado
            index = len(coll) - 1
            current = getattr(owner, attr)
            if 0 <= current < n - 1:
                coll.move(index, current + 1)
                index = current + 1
        elif n == 0:
            return {'CANCELLED'}
        elif self.action == 'REMOVE':
            coll.remove(min(index, n - 1))
            index = min(index, len(coll) - 1)
        else:
            new = index + (-1 if self.action == 'UP' else 1)
            if not (0 <= index < n and 0 <= new < n):
                return {'CANCELLED'}
            coll.move(index, new)
            index = new
        setattr(owner, attr, max(0, index))
        return {'FINISHED'}


class RANGE_TRACK_OT_profile_add(_TrackOp, Operator):
    """Add a new profile to the scene (a copy of the current one) and use it on this track"""
    bl_idname = "range_track.profile_add"
    bl_label = "New Profile"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        track = _active_track(context)
        src = profile_of(scene, track)
        profiles = scene.range_track_profiles
        base = src.name if src else "Profile"
        name, k = base, 1
        while name in profiles:
            name = "%s.%03d" % (base, k)
            k += 1
        profile = profiles.add()
        if src is not None:
            dict_to_pg(profile, pg_to_dict(src))
            for band in src.bands:
                dict_to_pg(profile.bands.add(), pg_to_dict(band))
        profile.name = name
        settings_of(track).profile = name
        return {'FINISHED'}


class RANGE_TRACK_OT_profile_remove(_TrackOp, Operator):
    """Remove the current profile from the scene (tracks using it lose their profile)"""
    bl_idname = "range_track.profile_remove"
    bl_label = "Remove Profile"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        st = settings_of(_active_track(context))
        profiles = scene.range_track_profiles
        k = profiles.find(st.profile)
        if k < 0:
            return {'CANCELLED'}
        profiles.remove(k)
        st.profile = profiles[0].name if len(profiles) else ""
        return {'FINISHED'}


_preset_items_ref = []


def _preset_items(self, context):
    items = [(path, name, path) for path, name in preset_files()]
    if not items:
        items = [('NONE', "No presets", "")]
    _preset_items_ref[:] = items     # mantém as strings vivas (enum dinâmico)
    return items


class RANGE_TRACK_OT_preset_load(_TrackOp, Operator):
    """Load a track preset: profile (bands), track settings and decoration rules"""
    bl_idname = "range_track.preset_load"
    bl_label = "Load Preset"
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = "preset"

    preset: EnumProperty(name="Preset", items=_preset_items)
    preset_name: StringProperty(name="Preset Name", description="Load by name instead (scripts)",
                                options={'SKIP_SAVE'})
    load_settings: BoolProperty(name="Settings", default=True, description="Also load bank, terrain and sweep settings")
    load_rules: BoolProperty(name="Rules", default=True, description="Replace the decoration rules")

    def execute(self, context):
        source = self.preset_name or self.preset
        if source == 'NONE':
            return {'CANCELLED'}
        try:
            data = read_preset(source)
        except Exception as ex:
            self.report({'ERROR'}, str(ex))
            return {'CANCELLED'}
        warnings = []
        profile = apply_preset(context.scene, _active_track(context), data,
                               self.load_settings, self.load_rules, warnings)
        if warnings:
            print("Track preset %s:\n  %s" % (source, "\n  ".join(warnings)))
            self.report({'WARNING'}, tip_("Preset %s loaded; %d value(s) ignored (see console)") % (
                profile.name, len(warnings)))
        else:
            self.report({'INFO'}, tip_("Preset %s loaded") % profile.name)
        return {'FINISHED'}


class RANGE_TRACK_OT_preset_save(_TrackOp, Operator):
    """Save the profile, settings and rules of this track as a preset in the user folder"""
    bl_idname = "range_track.preset_save"
    bl_label = "Save Preset"
    bl_options = {'REGISTER'}

    name: StringProperty(name="Name", default="My Track")
    directory: StringProperty(name="Folder", subtype='DIR_PATH', options={'SKIP_SAVE', 'HIDDEN'},
                              description="Folder to write to (default: user presets)")

    def invoke(self, context, event):
        profile = profile_of(context.scene, _active_track(context))
        if profile is not None:
            self.name = profile.name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        try:
            data = preset_from_track(context.scene, _active_track(context), self.name)
            directory = self.directory or bpy.utils.user_resource(
                'SCRIPTS', os.path.join("presets", PRESET_SUBDIR), create=True)
            if not directory:
                raise RuntimeError("no user preset folder")
            path = os.path.join(directory, bpy.path.clean_name(self.name) + ".json")
            text = json.dumps(data, indent=2, ensure_ascii=False)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as ex:
            self.report({'ERROR'}, tip_("Save preset failed: %s") % ex)
            return {'CANCELLED'}
        self.report({'INFO'}, tip_("Preset saved: %s") % path)
        return {'FINISHED'}


class RANGE_TRACK_OT_rules_default(_TrackOp, Operator):
    """Replace the decoration rules with a default set for this kind of road"""
    bl_idname = "range_track.rules_default"
    bl_label = "Default Rules"
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = "theme"

    theme: EnumProperty(name="Theme", items=(
        ('bairro', "Neighborhood", "Houses, poles with wires, signs and people along the sidewalks"),
        ('serra', "Mountain Road", "Trees on the hills, guard rails and signs on the curves"),
    ))

    def execute(self, context):
        track = _active_track(context)
        try:
            _rt("decor").default_rules(track, self.theme)
        except Exception as ex:
            traceback.print_exc()
            self.report({'ERROR'}, tip_("Default rules failed: %s") % ex)
            return {'CANCELLED'}
        self.report({'INFO'}, tip_("%d rule(s)") % len(settings_of(track).rules))
        return {'FINISHED'}


class RANGE_TRACK_OT_anchor(_TrackOp, Operator):
    """Anchor the selected objects to the active track at their current place (they follow the track when it is regenerated)"""
    bl_idname = "range_track.anchor"
    bl_label = "Anchor to Track"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        track = _active_track(context)
        objs = [ob for ob in context.selected_objects
                if ob is not track and not is_track(ob) and not _owner_of(ob) and _anchor_of(ob) is not None]
        if not objs:
            self.report({'WARNING'}, tip_("Select the objects to anchor, then the track last (active)"))
            return {'CANCELLED'}
        try:
            n = anchor_objects(context.scene, track, objs)
        except Exception as ex:
            traceback.print_exc()
            self.report({'ERROR'}, tip_("Anchor failed: %s") % ex)
            return {'CANCELLED'}
        self.report({'INFO'}, tip_("Anchored %d object(s) to %s") % (n, track.name))
        return {'FINISHED'}


def _default_anchor_band(profile):
    """Faixa usada como referência da âncora: BORDER, senão SIDEWALK, senão a última."""
    bands = list(profile.bands)
    for kind in ('BORDER', 'SIDEWALK', 'CURB', 'ASPHALT'):
        for band in reversed(bands):
            if getattr(band, "kind", '') == kind:
                return band.name
    return bands[-1].name if bands else ""


def anchor_objects(scene, track, objs):
    st = settings_of(track)
    profile = profile_of(scene, track)
    if profile is None:
        raise ValueError("the track has no profile")
    fr = _rt("frames").sample(track, st)
    ed = _rt("layout").band_edges(fr, profile, st)
    kinds = {b.kind for b in profile.bands}
    for ob in objs:
        anchor = _anchor_of(ob)
        # band aceita nome ou tipo (layout.find); o padrão do props.py é o tipo "BORDER"
        band = anchor.band
        if not band or (band not in profile.bands and band not in kinds):
            band = _default_anchor_band(profile)
        loc = ob.matrix_world.translation
        i, s, side, dist = fr.nearest(loc.x, loc.y)
        side = LEFT if side > 0 else RIGHT
        off_out, z_out = ed.outer(i, side, band)
        anchor.track = track.name
        anchor.s = s
        anchor.side = side
        anchor.band = band
        anchor.offset = dist - off_out
        anchor.height = loc.z - z_out
        anchor.enabled = True
    return len(objs)


class RANGE_TRACK_OT_select_owner(Operator):
    """Select the track that generated this object"""
    bl_idname = "range_track.select_owner"
    bl_label = "Select Track"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(_owner_of(context.active_object))

    def execute(self, context):
        scene = context.scene
        track = scene.objects.get(_owner_of(context.active_object))
        if track is None:
            return {'CANCELLED'}
        for ob in scene.objects:
            ob.select = False
        track.select = True
        scene.objects.active = track
        return {'FINISHED'}


# --------------------------------------------------------------------------------------------
# Listas e painéis
# --------------------------------------------------------------------------------------------

def _draw_fields(layout, data, names, skip=()):
    """Desenha só os campos que existem no RNA (tolerante a mudanças do props.py)."""
    props = data.bl_rna.properties
    for name in names:
        if name in props and name not in skip:
            layout.prop(data, name)


def _list_buttons(layout, target):
    col = layout.column(align=True)
    for action, icon in (('ADD', 'ZOOMIN'), ('REMOVE', 'ZOOMOUT')):
        op = col.operator("range_track.list_action", text="", icon=icon)
        op.target, op.action = target, action
    col.separator()
    for action, icon in (('UP', 'TRIA_UP'), ('DOWN', 'TRIA_DOWN')):
        op = col.operator("range_track.list_action", text="", icon=icon)
        op.target, op.action = target, action
    return col


class RANGE_TRACK_UL_bands(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False)
        sub = row.row()
        sub.alignment = 'RIGHT'
        side = getattr(item, "side", 'BOTH')
        sub.label(text="%s%s  %.2f m" % (getattr(item, "kind", ""), "" if side == 'BOTH' else " " + side[0],
                                          getattr(item, "width", 0.0)))


class RANGE_TRACK_UL_points(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=tip_("Point %d") % item.index)
        wl, wr = getattr(item, "width_left", 0.0), getattr(item, "width_right", 0.0)
        width = tip_("profile") if wl == 0 and wr == 0 else "%.1f / %.1f m" % (wl, wr)
        bank = tip_("auto") if getattr(item, "bank_mode", 'AUTO') == 'AUTO' else "%.1f°" % getattr(item, "bank_deg", 0)
        row.label(text="%s, %s" % (width, bank))


class RANGE_TRACK_UL_segments(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text="%.0f-%.0f m" % (item.s_start, item.s_end))
        row.label(text="%s %s" % (getattr(item, "side", ""), item.band or item.kind or ""))


class RANGE_TRACK_UL_rules(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        if "enabled" in item.bl_rna.properties:
            row.prop(item, "enabled", text="")
        row.label(text=getattr(item, "kind", ""))
        row.label(text=getattr(item, "band", "") or tip_("any band"))


class _TrackPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Track"

    @classmethod
    def poll(cls, context):
        return import_error() is None and _active_track(context) is not None


class VIEW3D_PT_range_track(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Track"
    bl_label = "Track"

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob is None:
            return False
        if ob.type == 'CURVE' or is_curve_array(ob) or _owner_of(ob):
            return True
        anchor = _anchor_of(ob)
        return bool(anchor is not None and getattr(anchor, "enabled", False)) or import_error() is not None

    def draw(self, context):
        layout = self.layout
        err = import_error()
        if err:
            box = layout.box()
            box.label(text=tip_("Track Tool could not load"), icon='ERROR')
            for line in _wrap(err, 48):
                box.label(text=line)
            return
        scene = context.scene
        ob = context.active_object
        track = ob if is_track(ob) else None
        missing = module_errors()
        if missing:
            box = layout.box()
            for sub, text in sorted(missing.items()):
                box.label(text="range_track.%s: %s" % (sub, text[:70]), icon='ERROR')

        if ob.type == 'CURVE' and track is None:
            layout.operator("range_track.make", icon='CURVE_PATH')
        if is_curve_array(ob):
            layout.operator("range_track.convert", icon='MOD_CURVE')
        owner = _owner_of(ob)
        if owner:
            row = layout.row()
            row.label(text=tip_("Generated by %s") % owner, icon='INFO')
            row.operator("range_track.select_owner", text="", icon='RESTRICT_SELECT_OFF')
        anchor = _anchor_of(ob)
        if track is None and anchor is not None and getattr(anchor, "enabled", False):
            box = layout.box()
            box.label(text=tip_("Anchored to track"), icon='PINNED')
            _draw_fields(box, anchor, ANCHOR_FIELDS)
        if track is None:
            return

        st = settings_of(track)
        ui = track.range_track_ui
        row = layout.row(align=True)
        row.prop_search(st, "profile", scene, "range_track_profiles", text="", icon='MOD_ARRAY')
        row.operator("range_track.profile_add", text="", icon='ZOOMIN')
        row.operator("range_track.profile_remove", text="", icon='ZOOMOUT')
        row = layout.row(align=True)
        row.operator_menu_enum("range_track.preset_load", "preset", text=tip_("Load Preset"), icon='FILE_FOLDER')
        row.operator("range_track.preset_save", text=tip_("Save Preset"), icon='FILE_TICK')
        if profile_of(scene, track) is None:
            layout.label(text=tip_("Choose or load a profile"), icon='ERROR')

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator("range_track.generate", text=tip_("Road")).parts = 'ROAD'
        row.operator("range_track.generate", text=tip_("Terrain")).parts = 'TERRAIN'
        row.operator("range_track.generate", text=tip_("Decoration")).parts = 'DECOR'
        row = col.row(align=True)
        row.operator("range_track.generate", text=tip_("Generate All"), icon='FILE_REFRESH').parts = 'ALL'
        row.operator("range_track.generate", text=tip_("Bake Track Data"), icon='TEXT').parts = 'BAKE'

        row = layout.row(align=True)
        row.operator("range_track.live_toggle", text=tip_("Live"), icon='REC', depress=live_enabled(track))
        row.prop(scene, "range_track_overlay", text=tip_("Overlay"), toggle=True, icon='RESTRICT_VIEW_OFF')
        row = layout.row()
        row.operator("range_track.anchor", text=tip_("Anchor Selected to Track"), icon='PINNED')

        if ui.report:
            layout.label(text=ui.report, icon='INFO')
        if ui.error:
            box = layout.box()
            for k, line in enumerate(_wrap(ui.error, 48)[:6]):
                box.label(text=line, icon='ERROR' if k == 0 else 'NONE')
        hit = _overlay_cache.get(track.name)
        if hit is not None and hit[2] and scene.range_track_overlay:
            layout.label(text=tip_("Overlay: %s") % hit[2][:60], icon='ERROR')


def _wrap(text, width):
    lines = []
    for para in str(text).splitlines() or [""]:
        while len(para) > width:
            cut = para.rfind(" ", 0, width)
            cut = width if cut <= 0 else cut
            lines.append(para[:cut])
            para = para[cut:].lstrip()
        lines.append(para)
    return lines


class VIEW3D_PT_range_track_bands(_TrackPanel, Panel):
    bl_label = "Profile Bands"

    def draw(self, context):
        layout = self.layout
        track = _active_track(context)
        profile = profile_of(context.scene, track)
        if profile is None:
            layout.label(text=tip_("No profile"))
            return
        owner, attr = list_index_owner(track, profile, 'BANDS')
        _draw_fields(layout, profile, ("symmetric",))
        row = layout.row()
        row.template_list("RANGE_TRACK_UL_bands", "", profile, "bands", owner, attr, rows=5)
        _list_buttons(row, 'BANDS')
        index = getattr(owner, attr)
        if 0 <= index < len(profile.bands):
            band = profile.bands[index]
            kind = getattr(band, "kind", '')
            col = layout.column()
            col.prop(band, "name")
            known = {"name"}
            for name, kinds in BAND_FIELDS:
                known.add(name)
                if kinds is None or kind in kinds:
                    _draw_fields(col, band, (name,))
            _draw_fields(col, band, [p.identifier for p in _props(band) if p.identifier not in known])


class VIEW3D_PT_range_track_bank(_TrackPanel, Panel):
    bl_label = "Bank and Points"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        track = _active_track(context)
        st = settings_of(track)
        owner, attr = list_index_owner(track, None, 'POINTS')
        col = layout.column(align=True)
        _draw_fields(col, st, SETTINGS_BANK)
        col = layout.column(align=True)
        _draw_fields(col, st, SETTINGS_ROAD)
        layout.label(text=tip_("Per point (Bezier control points):"))
        row = layout.row()
        row.template_list("RANGE_TRACK_UL_points", "", st, "points", owner, attr, rows=3)
        _list_buttons(row, 'POINTS')
        if context.mode == 'EDIT_CURVE':
            op = layout.operator("range_track.list_action", text=tip_("Add from Selected Point"), icon='ZOOMIN')
            op.target, op.action = 'POINTS', 'ADD'
        index = getattr(owner, attr)
        if 0 <= index < len(st.points):
            col = layout.column()
            pt = st.points[index]
            _draw_fields(col, pt, POINT_FIELDS, skip=() if getattr(pt, "bank_mode", 'MANUAL') == 'MANUAL'
                         else ("bank_deg",))


class VIEW3D_PT_range_track_segments(_TrackPanel, Panel):
    bl_label = "Segments"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        track = _active_track(context)
        st = settings_of(track)
        owner, attr = list_index_owner(track, None, 'SEGMENTS')
        row = layout.row()
        row.template_list("RANGE_TRACK_UL_segments", "", st, "segments", owner, attr, rows=3)
        _list_buttons(row, 'SEGMENTS')
        index = getattr(owner, attr)
        if 0 <= index < len(st.segments):
            col = layout.column()
            _draw_fields(col, st.segments[index], SEGMENT_FIELDS)


class VIEW3D_PT_range_track_decor(_TrackPanel, Panel):
    bl_label = "Decoration Rules"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        track = _active_track(context)
        st = settings_of(track)
        owner, attr = list_index_owner(track, None, 'RULES')
        layout.operator_menu_enum("range_track.rules_default", "theme", text=tip_("Default Rules"), icon='PRESET')
        row = layout.row()
        row.template_list("RANGE_TRACK_UL_rules", "", st, "rules", owner, attr, rows=4)
        _list_buttons(row, 'RULES')
        index = getattr(owner, attr)
        if 0 <= index < len(st.rules):
            col = layout.column()
            _draw_fields(col, st.rules[index], RULE_FIELDS, skip=("enabled",))


class VIEW3D_PT_range_track_terrain(_TrackPanel, Panel):
    bl_label = "Terrain"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        st = settings_of(_active_track(context))
        col = layout.column(align=True)
        _draw_fields(col, st, SETTINGS_TERRAIN)
        layout.operator("range_track.generate", text=tip_("Generate Terrain"), icon='FILE_REFRESH').parts = 'TERRAIN'


def menu_func_add(self, context):
    self.layout.operator("range_track.add", text=tip_("Track"), icon='CURVE_PATH')


classes = (
    RangeTrackUIState,
    RANGE_TRACK_OT_make,
    RANGE_TRACK_OT_add,
    RANGE_TRACK_OT_convert,
    RANGE_TRACK_OT_generate,
    RANGE_TRACK_OT_live_watch,
    RANGE_TRACK_OT_live_toggle,
    RANGE_TRACK_OT_list_action,
    RANGE_TRACK_OT_profile_add,
    RANGE_TRACK_OT_profile_remove,
    RANGE_TRACK_OT_preset_load,
    RANGE_TRACK_OT_preset_save,
    RANGE_TRACK_OT_rules_default,
    RANGE_TRACK_OT_anchor,
    RANGE_TRACK_OT_select_owner,
    RANGE_TRACK_UL_bands,
    RANGE_TRACK_UL_points,
    RANGE_TRACK_UL_segments,
    RANGE_TRACK_UL_rules,
    VIEW3D_PT_range_track,
    VIEW3D_PT_range_track_bands,
    VIEW3D_PT_range_track_bank,
    VIEW3D_PT_range_track_segments,
    VIEW3D_PT_range_track_decor,
    VIEW3D_PT_range_track_terrain,
)


def register_props():
    try:
        _ensure_props()
    except Exception as ex:
        # O painel mostra o erro (import_error); o editor segue.
        print("Track Tool: range_track not loaded: %s" % ex)
    _import_state["checked"] = 0.0
    bpy.types.Object.range_track_ui = PointerProperty(type=RangeTrackUIState)
    bpy.types.Scene.range_track_overlay = BoolProperty(
        name="Track Overlay", default=True,
        description="Draw band edges, distance marks, bank arrows and segments of the tracks in the viewport")
    for lst, fn in ((bpy.app.handlers.scene_update_post, _scene_update_post), (bpy.app.handlers.load_post, _load_post)):
        if fn not in lst:
            lst.append(fn)
    if not _draw_handles:
        space = bpy.types.SpaceView3D
        _draw_handles.append(space.draw_handler_add(_draw_overlay_view, (), 'WINDOW', 'POST_VIEW'))
        _draw_handles.append(space.draw_handler_add(_draw_overlay_text, (), 'WINDOW', 'POST_PIXEL'))
    try:
        menu = _curve_add_menu()
        if menu_func_add not in getattr(menu.draw, "_draw_funcs", ()):
            menu.append(menu_func_add)
    except Exception as ex:
        print("Track Tool: Add > Curve > Track not added: %s" % ex)


def _curve_add_menu():
    # bl_operators registra antes de bl_ui: a classe do menu vem do módulo (o append vale
    # quando o bl_ui registrar o menu logo depois).
    menu = getattr(bpy.types, "INFO_MT_curve_add", None)
    if menu is None:
        from bl_ui.space_view3d import INFO_MT_curve_add as menu
    return menu


def unregister_props():
    try:
        _curve_add_menu().remove(menu_func_add)
    except Exception:
        pass
    while _draw_handles:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handles.pop(), 'WINDOW')
    for lst, fn in ((bpy.app.handlers.scene_update_post, _scene_update_post), (bpy.app.handlers.load_post, _load_post)):
        if fn in lst:
            lst.remove(fn)
    _live.clear()
    _overlay_cache.clear()
    del bpy.types.Scene.range_track_overlay
    del bpy.types.Object.range_track_ui
    if _registered_props[0]:
        try:
            _rt("props").unregister()
        except Exception:
            pass
        _registered_props[0] = False
