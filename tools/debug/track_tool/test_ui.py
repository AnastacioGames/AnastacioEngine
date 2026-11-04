"""Teste headless da interface do Track Tool (bl_operators/anastacio_track.py).

Uso (nunca abre janela):
  AnastacioEngine.exe -b --python tools/debug/track_tool/test_ui.py -- main
  AnastacioEngine.exe -b <cópia>.range --python tools/debug/track_tool/test_ui.py -- convert <saida.range>
  AnastacioEngine.exe -b <saida.range> --python tools/debug/track_tool/test_ui.py -- reopen

main:    registro, Add Track, presets, painéis (layout falso que confere cada prop/operador), listas,
         overlay, Generate (Road/All), Make Track, Default Rules, Anchor, Live (relógio falso), Save
         Preset, salvar e reabrir.
convert: cena Pista_4, objeto Pista4_Track -> Convert Curve+Array to Track -> Generate All -> salva.
reopen:  confere que o traçado convertido, o perfil, os gerados e o bake persistem.
Sai com código 1 se algo falhar (FAIL no log).
"""
import json
import os
import sys
import time
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(ROOT, "artifacts", "track_tool", "ui")
os.makedirs(OUT, exist_ok=True)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "main"

if os.environ.get("TRACK_UI_SOURCE"):
    # Usa os submódulos do range_track direto do código-fonte (antes de copiar para build/bin)
    import range_track
    range_track.__path__.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules", "range_track"))

import bl_operators.anastacio_track as T  # noqa: E402

failures = []
results = {}


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        failures.append(what)
    return cond


# --------------------------------------------------------------------- layout falso
class FakeOpProps:
    def __init__(self, rna, errors, idname):
        object.__setattr__(self, "_rna", rna)
        object.__setattr__(self, "_errors", errors)
        object.__setattr__(self, "_id", idname)

    def __setattr__(self, key, value):
        if key not in self._rna.properties:
            self._errors.append("operator %s has no property %s" % (self._id, key))


def _op_rna(idname):
    mod, name = idname.split(".")
    op = getattr(getattr(bpy.ops, mod), name)
    try:
        return op.get_rna_type()
    except AttributeError:
        return op.get_rna().bl_rna


class FakeLayout:
    """Aceita a API do UILayout usada pelos painéis e confere nomes de propriedades e operadores."""

    def __init__(self, log, errors):
        object.__setattr__(self, "log", log)
        object.__setattr__(self, "errors", errors)

    def __setattr__(self, key, value):     # alignment, enabled, operator_context...
        pass

    def _sub(self, *a, **k):
        return FakeLayout(self.log, self.errors)

    row = column = box = split = column_flow = _sub

    def separator(self, *a, **k):
        pass

    def label(self, text="", icon='NONE', **k):
        self.log.append(("label", text))

    def _check_prop(self, data, prop):
        if data is None or prop not in data.bl_rna.properties:
            self.errors.append("prop %s.%s missing" % (getattr(data, "bl_rna", data) and
                                                         getattr(data.bl_rna, "identifier", data), prop))

    def prop(self, data, prop, **k):
        self._check_prop(data, prop)
        self.log.append(("prop", prop))

    def prop_search(self, data, prop, sdata, sprop, **k):
        self._check_prop(data, prop)
        self._check_prop(sdata, sprop)
        self.log.append(("prop_search", prop))

    def template_list(self, listtype, list_id, data, prop, adata, aprop, **k):
        self._check_prop(data, prop)
        self._check_prop(adata, aprop)
        cls = getattr(T, listtype, None)
        if cls is None:
            self.errors.append("UIList %s missing" % listtype)
            return
        for k_, item in enumerate(getattr(data, prop)):
            cls.draw_item(None, bpy.context, FakeLayout(self.log, self.errors), data, item, 0, adata, aprop, k_)
        self.log.append(("list", listtype, len(getattr(data, prop))))

    def operator(self, idname, **k):
        self.log.append(("op", idname))
        try:
            return FakeOpProps(_op_rna(idname), self.errors, idname)
        except Exception as ex:
            self.errors.append("operator %s: %s" % (idname, ex))
            return FakeOpProps(bpy.types.Operator.bl_rna, [], idname)

    def operator_menu_enum(self, idname, prop, **k):
        self.log.append(("op_menu", idname))
        try:
            if prop not in _op_rna(idname).properties:
                self.errors.append("operator %s has no enum %s" % (idname, prop))
        except Exception as ex:
            self.errors.append("operator %s: %s" % (idname, ex))


class FakePanel:
    def __init__(self, log, errors):
        self.layout = FakeLayout(log, errors)


def draw_panels(tag):
    """poll + draw de todos os painéis com o objeto ativo atual. Retorna (desenhados, erros)."""
    errors, drawn = [], []
    for cls in T.classes:
        if not (isinstance(cls, type) and issubclass(cls, bpy.types.Panel)):
            continue
        try:
            if not cls.poll(bpy.context):
                continue
            log = []
            cls.draw(FakePanel(log, errors), bpy.context)
            drawn.append((cls.__name__, len(log)))
        except Exception as ex:
            traceback.print_exc()
            errors.append("%s: %s" % (cls.__name__, ex))
    check(not errors, "%s: panels drew %s without errors %s" % (tag, [d[0] for d in drawn], errors[:5]))
    return drawn, errors


def set_active(scene, ob, select=()):
    for o in scene.objects:
        o.select = False
    for o in select:
        o.select = True
    if ob is not None:
        ob.select = True
    scene.objects.active = ob


def owned(scene, ob):
    return [o for o in scene.objects if getattr(o, "range_track_owner", "") == ob.name]


def faces(objs):
    return sum(len(o.data.polygons) for o in objs if o.type == 'MESH')


# --------------------------------------------------------------------- main
def test_main():
    scene = bpy.context.scene
    print("== registro")
    check(all("bl_rna" in c.__dict__ for c in T.classes), "all %d classes registered" % len(T.classes))
    check(T.import_error() is None, "range_track imports: %s" % T.import_error())
    check(hasattr(bpy.types.Object, "range_track_ui"), "Object.range_track_ui")
    names = [n for _p, n in T.preset_files()]
    check({"Rua de bairro", "Estrada de serra", "Autodromo", "Rua de terra"} <= set(names), "presets found: %s" % names)
    check(T.menu_func_add in getattr(bpy.types.INFO_MT_curve_add.draw, "_draw_funcs", ()), "Add > Curve > Track in menu")

    print("== Add Track")
    for o in list(scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    check(bpy.ops.range_track.add() == {'FINISHED'}, "range_track.add")
    track = bpy.context.scene.objects.active
    check(T.is_track(track), "active is a track (%s)" % track.name)
    check(track.range_track.profile == "Rua de bairro", "default profile: %s" % track.range_track.profile)
    draw_panels("track with default profile")

    print("== Presets")
    for name in ("Estrada de serra", "Autodromo", "Rua de terra", "Rua de bairro"):
        data = T.read_preset(name)
        r = bpy.ops.range_track.preset_load(preset_name=name)
        prof = T.profile_of(scene, track)
        ok = (r == {'FINISHED'} and prof is not None and prof.name == name and
              len(prof.bands) == len(data["profile"]["bands"]) and len(track.range_track.rules) == len(data["rules"]))
        check(ok, "preset %s: %d bands, %d rules" % (name, len(prof.bands) if prof else -1, len(track.range_track.rules)))
    check(abs(track.range_track.bank_gain - 0.08) < 1e-6, "settings from preset (bank_gain 0.08)")
    check(T.profile_of(scene, track).bands[0].material is not None, "band material from preset")

    print("== Panels")
    drawn, _ = draw_panels("track + Rua de bairro")
    check(len(drawn) == 6, "6 panels drawn")

    print("== Lists")
    st = track.range_track
    prof = T.profile_of(scene, track)
    nb = len(prof.bands)
    for target, coll in (('BANDS', prof.bands), ('POINTS', st.points), ('SEGMENTS', st.segments), ('RULES', st.rules)):
        n0 = len(coll)
        bpy.ops.range_track.list_action(target=target, action='ADD')
        bpy.ops.range_track.list_action(target=target, action='ADD')
        owner, attr = T.list_index_owner(track, prof, target)
        idx = getattr(owner, attr)
        bpy.ops.range_track.list_action(target=target, action='UP')
        up = getattr(owner, attr)
        bpy.ops.range_track.list_action(target=target, action='DOWN')
        bpy.ops.range_track.list_action(target=target, action='REMOVE')
        check(len(coll) == n0 + 1 and up == idx - 1, "%s add/up/down/remove (%d -> %d)" % (target, n0, len(coll)))
        bpy.ops.range_track.list_action(target=target, action='REMOVE')
    check(len(prof.bands) == nb, "bands back to %d" % nb)
    pts = st.points
    bpy.ops.range_track.list_action(target='POINTS', action='ADD')
    bpy.ops.range_track.list_action(target='POINTS', action='ADD')
    check(len({p.index for p in pts}) == len(pts), "points get distinct Bezier indices %s" % [p.index for p in pts])
    pts[1].bank_mode = 'MANUAL'
    pts[1].bank_deg = 4.0
    seg_add = bpy.ops.range_track.list_action(target='SEGMENTS', action='ADD')
    st.segments[0].s_start, st.segments[0].s_end, st.segments[0].band, st.segments[0].side = 120.0, 220.0, "Mureta", 'LEFT'
    st.segments[0].border_type = 'GUARDRAIL'
    check(seg_add == {'FINISHED'}, "segment added (0-100 m default)")
    draw_panels("with points/segments")

    print("== Overlay")
    t0 = time.perf_counter()
    lines = T.overlay_lines(scene, track)
    t1 = time.perf_counter()
    T._overlay_cache.clear()
    T.cached_overlay(scene, track)
    t2 = time.perf_counter()
    again = T.cached_overlay(scene, track)
    t3 = time.perf_counter()
    nstrip = len(lines["strips"])
    nseg = sum(len(s) for _c, s in lines["lines"])
    check(nstrip >= 5 and nseg > 0 and lines["labels"], "overlay: %d strips, %d line segments, %d labels"
          % (nstrip, nseg, len(lines["labels"])))
    check(again is T._overlay_cache[track.name][1], "overlay cache hit")
    results["overlay_ms"] = round((t1 - t0) * 1000, 2)
    results["overlay_cached_ms"] = round((t3 - t2) * 1000, 3)
    print("  overlay compute %.2f ms, cached lookup %.3f ms" % ((t1 - t0) * 1000, (t3 - t2) * 1000))
    track.location.x += 1.0
    scene.update()
    T.cached_overlay(scene, track)
    check(T._overlay_cache[track.name][0] != None, "cache recomputed after move")  # noqa: E711
    track.location.x -= 1.0
    # GL: as funções de desenho não podem lançar sem viewport
    try:
        T._draw_overlay_text()
        check(True, "text overlay without region returns quietly")
    except Exception as ex:
        check(False, "text overlay raised %s" % ex)

    print("== Generate")
    set_active(scene, track)
    for parts in ('ROAD', 'ALL', 'ROAD'):
        t0 = time.perf_counter()
        r = bpy.ops.range_track.generate(parts=parts)
        dt = time.perf_counter() - t0
        objs = owned(scene, track)
        check(r == {'FINISHED'} and objs, "generate %s: %d objects, %d faces, %.2f s | %s"
              % (parts, len(objs), faces(objs), dt, track.range_track_ui.report))
        results["generate_%s" % parts] = (len(objs), faces(objs), round(dt, 2))
    check(bpy.data.texts.get("TRACK_%s.json" % track.name) is not None, "bake text TRACK_%s.json" % track.name)
    check(not track.range_track_ui.error, "no error stored: %s" % track.range_track_ui.error)
    # Gerar ROAD de novo não pode duplicar nem perder o resto
    n_all = len(owned(scene, track))
    meshes = len(bpy.data.meshes)
    bpy.ops.range_track.generate(parts='ROAD')
    check(len(owned(scene, track)) == n_all, "regenerate road keeps count (%d)" % n_all)
    check(len(bpy.data.meshes) <= meshes, "no orphan meshes piling up (%d -> %d)" % (meshes, len(bpy.data.meshes)))

    print("== Generated object panel")
    gen = owned(scene, track)[0]
    set_active(scene, gen)
    drawn, _ = draw_panels("generated object")
    check(any(n == "VIEW3D_PT_range_track" for n, _ in drawn), "main panel shows on generated object")
    check(bpy.ops.range_track.select_owner() == {'FINISHED'} and scene.objects.active == track, "Select Track")

    print("== Default rules")
    for theme in ('bairro', 'serra'):
        r = bpy.ops.range_track.rules_default(theme=theme)
        check(r == {'FINISHED'} and len(st.rules) > 0, "default rules %s: %d" % (theme, len(st.rules)))

    print("== Anchor")
    empty = bpy.data.objects.new("Placa_Ancora", None)
    scene.objects.link(empty)
    fr = T._rt("frames").sample(track, st)
    pos, tan, lat, up, bank = fr.at(150.0)
    empty.location = pos + lat * 9.0 + up * 0.5
    scene.update()
    set_active(scene, track, select=[empty])
    r = bpy.ops.range_track.anchor()
    a = empty.range_track_anchor
    check(r == {'FINISHED'} and a.enabled and a.track == track.name and abs(a.s - 150.0) < 1.5 and a.side == 1,
          "anchor: s=%.2f side=%d band=%s offset=%.2f height=%.2f" % (a.s, a.side, a.band, a.offset, a.height))
    set_active(scene, empty)
    draw_panels("anchored object")

    print("== Make Track on a new Bezier")
    bpy.ops.curve.primitive_bezier_curve_add(location=(0.0, 300.0, 0.0))
    bez = scene.objects.active
    bez.scale = (60.0, 60.0, 60.0)
    draw_panels("plain curve (Make Track button)")
    check(bpy.ops.range_track.make() == {'FINISHED'} and T.is_track(bez), "Make Track on %s" % bez.name)
    check(T.profile_of(scene, bez) is not None, "made track has a profile (%s)" % bez.range_track.profile)
    r = bpy.ops.range_track.generate(parts='ROAD')
    check(r == {'FINISHED'} and owned(scene, bez), "made track road: %d objects" % len(owned(scene, bez)))
    check(not set(owned(scene, bez)) & set(owned(scene, track)), "tracks own separate objects")

    print("== Live")
    set_active(scene, track)
    clock = [1000.0]
    T._clock = lambda: clock[0]
    calls = []
    gen_mod = T._rt("generate")
    real = gen_mod.generate

    def spy(ob, parts=None, **k):
        calls.append((ob.name, set(parts or ())))
        return real(ob, parts=parts, **k)
    gen_mod.generate = spy
    try:
        check(bpy.ops.range_track.live_toggle() == {'FINISHED'} and T.live_enabled(track), "Live on")
        clock[0] += 0.1
        T.live_tick(scene)
        n_before = len(calls)
        clock[0] += 0.5
        T.live_tick(scene)
        check(len(calls) == n_before + 1 and calls[-1] == (track.name, {'ROAD'}), "first live build after delay (ROAD)")
        bp = track.data.splines[0].bezier_points[2]
        bp.co.y += 5.0
        bp.handle_left.y += 5.0
        bp.handle_right.y += 5.0
        clock[0] += 0.05
        T.live_tick(scene)          # vê a mudança
        clock[0] += 0.2
        T.live_tick(scene)          # ainda esperando
        mid = len(calls)
        clock[0] += 0.3
        T.live_tick(scene)          # passou 0,5 s
        check(mid == n_before + 1 and len(calls) == mid + 1, "live waits %.1f s after the edit, then rebuilds" % T.LIVE_DELAY)
        clock[0] += 1.0
        T.live_tick(scene)
        check(len(calls) == mid + 1, "no rebuild without changes")
        # Handler real (scene_update_post) usa o mesmo caminho
        track.range_track.bank_max = 5.0
        clock[0] += 0.01
        T._scene_update_post(scene)
        clock[0] += 0.6
        T._scene_update_post(scene)
        check(len(calls) == mid + 2, "settings edit rebuilds too (via handler)")

        def boom(ob, parts=None, **k):
            raise RuntimeError("boom de teste")
        gen_mod.generate = boom
        bp.co.y -= 5.0
        clock[0] += 0.01
        T.live_tick(scene)
        clock[0] += 0.6
        T.live_tick(scene)
        check(not T.live_enabled(track) and "boom" in track.range_track_ui.error,
              "live turns itself off on error: %s" % track.range_track_ui.error)
    finally:
        gen_mod.generate = real
        T._clock = time.time
        T._live.clear()
    track.range_track_ui.error = ""

    print("== Live in curve edit mode + Add from Selected Point")
    set_active(scene, track)
    bpy.ops.object.mode_set(mode='EDIT')
    check(bpy.context.mode == 'EDIT_CURVE', "edit mode: %s" % bpy.context.mode)
    clock = [5000.0]
    T._clock = lambda: clock[0]
    try:
        T.live_set(scene, track, True)
        road_before = {o.name for o in owned(scene, track) if o.get("range_track_part") == 'ROAD'}
        sp = track.data.splines[0]
        for k, p in enumerate(sp.bezier_points):
            p.select_control_point = (k == 3)
        p = sp.bezier_points[3]
        p.co.x += 4.0
        p.handle_left.x += 4.0
        p.handle_right.x += 4.0
        clock[0] += 0.05
        T.live_tick(scene)
        clock[0] += 0.5
        rebuilt = T.live_tick(scene)
        check(rebuilt == [track.name] and T.live_enabled(track) and not track.range_track_ui.error,
              "live rebuild while editing the curve (%s) %s" % (rebuilt, track.range_track_ui.error))
        road_after = [o for o in owned(scene, track) if o.get("range_track_part") == 'ROAD']
        check(bool(road_after),
              "road chunks after live edit: %d (before %d)" % (len(road_after), len(road_before)))
        n0 = len(track.range_track.points)
        bpy.ops.range_track.list_action(target='POINTS', action='ADD')
        newest = max(track.range_track.points, key=lambda q: q.index == 3)
        check(len(track.range_track.points) == n0 + 1 and newest.index == 3,
              "Add from selected point uses Bezier index 3 (%s)" % [q.index for q in track.range_track.points])
        bpy.ops.range_track.list_action(target='POINTS', action='REMOVE')
        draw_panels("edit mode")
    finally:
        T._clock = time.time
        T._live.clear()
        bpy.ops.object.mode_set(mode='OBJECT')

    print("== Save Preset")
    r = bpy.ops.range_track.preset_save(name="Teste UI", directory=OUT)
    path = os.path.join(OUT, "Teste_UI.json")
    check(r == {'FINISHED'} and os.path.isfile(path), "preset saved: %s" % path)
    data = T.read_preset(path)
    check(len(data["profile"]["bands"]) == len(T.profile_of(scene, track).bands) and data["rules"],
          "saved preset round trip (%d bands, %d rules)" % (len(data["profile"]["bands"]), len(data["rules"])))
    r = bpy.ops.range_track.preset_load(preset_name=path)
    check(r == {'FINISHED'} and track.range_track.profile == "Teste UI", "load saved preset by path")

    print("== Save / reopen")
    nown = len(owned(scene, track))
    blend = os.path.join(OUT, "test_ui_main.range")
    bpy.ops.wm.save_as_mainfile(filepath=blend, check_existing=False)
    bpy.ops.wm.open_mainfile(filepath=blend)
    scene = bpy.context.scene
    track = scene.objects.get("Track")
    check(track is not None and T.is_track(track), "track persists")
    check(track.range_track.profile == "Teste UI" and T.profile_of(scene, track) is not None, "profile persists")
    check(len(track.range_track.points) == 2 and len(track.range_track.segments) == 1, "points/segments persist")
    check(len(owned(scene, track)) == nown, "generated objects persist (%d)" % nown)
    check(scene.objects["Placa_Ancora"].range_track_anchor.enabled, "anchor persists")
    check(bool(track.range_track_ui.report), "report persists: %s" % track.range_track_ui.report)
    set_active(scene, track)
    draw_panels("after reopen")


# --------------------------------------------------------------------- convert
def _use_scene(sc):
    for attr in ("window", "screen"):
        pass
    try:
        bpy.context.window.screen.scene = sc
    except Exception:
        try:
            bpy.context.screen.scene = sc
        except Exception as ex:
            print("  (could not switch screen scene: %s)" % ex)
    return bpy.context.scene == sc


def test_convert(out_path):
    sc = bpy.data.scenes.get("Pista_4")
    check(sc is not None, "scene Pista_4")
    check(_use_scene(sc), "context scene is Pista_4 (%s)" % bpy.context.scene.name)
    src = sc.objects.get("Pista4_Track")
    check(src is not None and T.is_curve_array(src), "Pista4_Track is Mesh + Array + Curve")
    set_active(sc, src)
    drawn, _ = draw_panels("Pista4_Track (convert button)")
    t0 = time.perf_counter()
    r = bpy.ops.range_track.convert()
    dt = time.perf_counter() - t0
    track = bpy.context.scene.objects.active
    check(r == {'FINISHED'} and T.is_track(track), "convert -> %s in %.2f s" % (track.name if track else None, dt))
    prof = T.profile_of(sc, track)
    check(prof is not None, "converted profile: %s (%d bands)" % (track.range_track.profile, len(prof.bands) if prof else 0))
    fr = T._rt("frames").sample(track, track.range_track)
    print("  length %.1f m, cyclic %s, %d Bezier points, bank range %.2f..%.2f deg" % (
        fr.length, fr.cyclic, fr.point_count, min(fr.point_bank_deg), max(fr.point_bank_deg)))
    results["convert"] = {"track": track.name, "length": round(fr.length, 1), "seconds": round(dt, 2)}
    draw_panels("converted track")
    t0 = time.perf_counter()
    lines = T.overlay_lines(sc, track)
    results["convert_overlay_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    check(lines["strips"], "overlay on Pista_4: %d strips, %.1f ms" % (len(lines["strips"]), results["convert_overlay_ms"]))
    for parts in ('ROAD', 'ALL'):
        t0 = time.perf_counter()
        r = bpy.ops.range_track.generate(parts=parts)
        dt = time.perf_counter() - t0
        objs = owned(sc, track)
        check(r == {'FINISHED'}, "Pista_4 generate %s: %d objects, %d faces, %.2f s | %s %s" % (
            parts, len(objs), faces(objs), dt, track.range_track_ui.report, track.range_track_ui.error))
        results["pista4_%s" % parts] = (len(objs), faces(objs), round(dt, 2))
    with open(os.path.join(OUT, "convert_track.txt"), "w", encoding="utf-8") as f:
        f.write(track.name)
    bpy.ops.wm.save_as_mainfile(filepath=out_path, check_existing=False)
    print("  saved %s" % out_path)


def test_reopen():
    with open(os.path.join(OUT, "convert_track.txt"), encoding="utf-8") as f:
        name = f.read().strip()
    sc = bpy.data.scenes.get("Pista_4")
    _use_scene(sc)
    track = sc.objects.get(name)
    check(track is not None and T.is_track(track), "converted track %s persists" % name)
    check(T.profile_of(sc, track) is not None, "profile %s persists" % track.range_track.profile)
    objs = owned(sc, track)
    check(objs, "generated objects persist: %d (%d faces)" % (len(objs), faces(objs)))
    check(bpy.data.texts.get("TRACK_%s.json" % name) is not None, "bake text persists")
    txt = bpy.data.texts.get("TRACK_%s.json" % name)
    if txt is not None:
        head = json.loads(txt.as_string())
        print("  bake: length %.1f, count %d" % (head.get("length", 0), head.get("count", 0)))
    check(bool(track.range_track_ui.report), "report persists: %s" % track.range_track_ui.report)
    set_active(sc, track)
    draw_panels("reopened Pista_4")


try:
    if MODE == "main":
        test_main()
    elif MODE == "convert":
        test_convert(argv[1])
    elif MODE == "reopen":
        test_reopen()
except Exception:
    traceback.print_exc()
    failures.append("exception")

print("RESULTS %s" % json.dumps(results))
print("TRACK_UI_TEST %s (%d failure(s))" % ("PASS" if not failures else "FAIL", len(failures)))
for f in failures:
    print("  - %s" % f)
sys.stdout.flush()
os._exit(1 if failures else 0)
