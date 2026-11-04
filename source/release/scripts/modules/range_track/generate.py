# Track Tool: geração completa a partir de um traçado.
#
# generate(track_obj, parts) apaga só o que o próprio traçado gerou (range_track_owner ==
# nome do traçado e, quando marcado, a parte em range_track_part), chama sweep/terrain/decor/bake
# e marca os objetos novos. Módulos ausentes ou com erro viram aviso no relatório; o resto segue.
import importlib
import time
import traceback

import bpy

from . import frames as frames_mod
from . import layout
from . import props

PARTS_ALL = ('ROAD', 'TERRAIN', 'DECOR', 'BAKE')
PART_KEY = "range_track_part"       # ID property com a parte que gerou o objeto


def _import(name):
    try:
        return importlib.import_module("." + name, __package__), None
    except Exception as ex:          # módulo ainda não existe ou falhou ao carregar
        return None, "%s: %s" % (name, ex)


def _data_collection(ob_type):
    return {'MESH': bpy.data.meshes, 'CURVE': bpy.data.curves, 'SURFACE': bpy.data.curves,
            'FONT': bpy.data.curves, 'CAMERA': bpy.data.cameras, 'LAMP': bpy.data.lamps,
            'ARMATURE': bpy.data.armatures, 'LATTICE': bpy.data.lattices}.get(ob_type)


def owned_objects(track_name, parts=None):
    """Objetos gerados pelo traçado (todas as cenas). parts: filtra pela parte (objetos sem a
    marca de parte entram sempre)."""
    out = []
    for ob in bpy.data.objects:
        if getattr(ob, "range_track_owner", "") != track_name:
            continue
        if parts is not None:
            part = ob.get(PART_KEY)
            if part and part not in parts:
                continue
        out.append(ob)
    return out


def clear_generated(track_obj, parts=None):
    """Apaga os objetos gerados (e libera os dados órfãos). Retorna quantos apagou."""
    name = track_obj.name if not isinstance(track_obj, str) else track_obj
    obs = owned_objects(name, parts)
    n = 0
    for ob in obs:
        data, typ = ob.data, ob.type
        for sc in list(ob.users_scene):
            sc.objects.unlink(ob)
        bpy.data.objects.remove(ob, do_unlink=True)
        n += 1
        col = _data_collection(typ)
        if data is not None and col is not None and data.users == 0:
            col.remove(data)
    return n


def _mark(ob, track_obj, scene, part):
    ob.range_track_owner = track_obj.name
    ob[PART_KEY] = part
    if ob.name not in scene.objects:
        scene.objects.link(ob)
    ob.layers = [i == 0 for i in range(20)]


def prepare(track_obj, settings=None):
    """(scene, settings, profile, frames, edges) do traçado. Sem perfil: cria os padrões e usa
    'Rua de bairro' (com aviso em warnings)."""
    props.register()
    scene = props.track_scene(track_obj)
    st = settings if settings is not None else track_obj.range_track
    warnings = []
    profile = props.find_profile(st.profile, scene)
    if profile is None:
        names = props.default_profiles(scene)
        warnings.append("perfil '%s' não encontrado; usando '%s'" % (st.profile, names[0]))
        st.profile = names[0]
        profile = props.find_profile(st.profile, scene)
    fr = frames_mod.sample(track_obj, st, profile)
    ed = layout.band_edges(fr, profile, st)
    return scene, st, profile, fr, ed, warnings


def generate(track_obj, parts=frozenset(PARTS_ALL)):
    """Gera as partes pedidas ('ROAD', 'TERRAIN', 'DECOR', 'BAKE'). Retorna um relatório (dict):
    objects, faces, removed, times (s por parte), objects_by_part, warnings, length, samples."""
    if isinstance(parts, str):
        parts = {parts}
    parts = set(p.upper() for p in (parts or PARTS_ALL))
    if 'ALL' in parts:
        parts = set(PARTS_ALL)
    t_all = time.perf_counter()
    times = {}
    t0 = time.perf_counter()
    scene, st, profile, fr, ed, warnings = prepare(track_obj)
    times['FRAMES'] = time.perf_counter() - t0

    t0 = time.perf_counter()
    obj_parts = parts - {'BAKE'}
    removed = clear_generated(track_obj, obj_parts) if obj_parts else 0
    times['CLEAR'] = time.perf_counter() - t0

    created = {}
    calls = [
        ('ROAD', 'sweep', 'generate_road'),
        ('TERRAIN', 'terrain', 'generate_terrain'),
        ('DECOR', 'decor', 'generate_decor'),
    ]
    for part, modname, fn in calls:
        if part not in parts:
            continue
        t0 = time.perf_counter()
        mod, err = _import(modname)
        objs = []
        if mod is None or not hasattr(mod, fn):
            warnings.append("%s ignorado (%s)" % (part, err or "%s.%s ausente" % (modname, fn)))
        else:
            try:
                objs = list(getattr(mod, fn)(scene, track_obj, fr, ed) or [])
            except Exception as ex:
                traceback.print_exc()
                warnings.append("%s falhou: %s" % (part, ex))
        for ob in objs:
            _mark(ob, track_obj, scene, part)
        if part == 'DECOR' and mod is not None and hasattr(mod, "update_anchors"):
            try:
                mod.update_anchors(scene, track_obj, fr, ed)
            except Exception as ex:
                traceback.print_exc()
                warnings.append("âncoras falharam: %s" % ex)
        created[part] = objs
        times[part] = time.perf_counter() - t0

    baked = None
    if 'BAKE' in parts:
        t0 = time.perf_counter()
        mod, err = _import('bake')
        if mod is None or not hasattr(mod, "bake"):
            warnings.append("BAKE ignorado (%s)" % (err or "bake.bake ausente"))
        else:
            try:
                baked = mod.bake(track_obj, fr, ed)
            except Exception as ex:
                traceback.print_exc()
                warnings.append("BAKE falhou: %s" % ex)
        times['BAKE'] = time.perf_counter() - t0

    allobjs = [o for lst in created.values() for o in lst]
    faces = sum(len(o.data.polygons) for o in allobjs if o.type == 'MESH')
    times['TOTAL'] = time.perf_counter() - t_all
    for w in warnings:
        print("range_track: aviso:", w)
    return {
        'track': track_obj.name,
        'objects': len(allobjs),
        'faces': faces,
        'removed': removed,
        'times': times,
        'objects_by_part': {k: [o.name for o in v] for k, v in created.items()},
        'baked': baked,
        'warnings': warnings,
        'length': fr.length,
        'samples': fr.count,
    }
