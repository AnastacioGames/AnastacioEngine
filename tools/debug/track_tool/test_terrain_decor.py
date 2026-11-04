# Teste headless do terreno e da decoração do Track Tool (terrain.py / decor.py).
#
# Uso (sempre numa CÓPIA do RolimaRacer.range, nunca no original):
#   AnastacioEngine.exe -b artifacts/track_tool/terrain/base.range --python \
#       tools/debug/track_tool/test_terrain_decor.py -- Pista_4 [bairro|serra] [--prints] [--save]
#
# Passos: apaga os objetos P4_/P5_ do protótipo, converte a pista (convert.py se existir; senão
# usa a Curve da cena com o perfil "Rua de bairro"), gera a estrada (sweep.py se existir), o terreno
# e a decoração com as regras do tema, e confere:
#   - 0 pontos da estrada abaixo do terreno (raycast para cima a partir de cada vértice da estrada);
#   - 0 props a menos da folga da borda (edges.dist_to_edge);
#   - árvores vindas da cena Kits;
#   - tempo terreno + decoração < 25 s (Pista_4);
#   - âncora reposicionada e regerar não apaga objeto autoral.
# --prints: renders BLENDER_RENDER sem névoa em artifacts/track_tool/terrain/.
# Saída: linhas "CHECK nome OK/FALHA valor" e "RESULT OK/FALHA".
import os
import sys
import time
import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MODS = os.path.join(REPO, "source", "release", "scripts", "modules")
if MODS not in sys.path:
    sys.path.insert(0, MODS)
OUT = os.path.join(REPO, "artifacts", "track_tool", "terrain")
ORIG_DIR = r"D:/ProjetoRolimaRacer"

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
pos_args = [a for a in argv if not a.startswith("--")]
SCENE = pos_args[0] if pos_args else "Pista_4"
THEME = pos_args[1] if len(pos_args) > 1 else ("serra" if SCENE.endswith("5") else "bairro")
PRINTS = "--prints" in argv
SAVE = "--save" in argv

import importlib  # noqa: E402
import range_track  # noqa: E402
# o addon pode já ter importado o pacote de build/bin: a pasta do código-fonte vem primeiro
_src_pkg = os.path.join(MODS, "range_track")
if os.path.normcase(range_track.__path__[0]) != os.path.normcase(_src_pkg):
    range_track.__path__.insert(0, _src_pkg)
from range_track import props, frames as frames_mod, layout, terrain, decor  # noqa: E402
for m in (terrain, decor):
    importlib.reload(m)
print("terrain de", terrain.__file__)

results = []


def check(name, ok, value=""):
    results.append((name, ok))
    print("CHECK %-28s %s %s" % (name, "OK" if ok else "FALHA", value))


def has_mod(name):
    try:
        importlib.import_module("range_track." + name)
        return True
    except Exception as ex:
        print("sem range_track.%s (%s)" % (name, ex))
        return False


def fix_image_paths():
    """A cópia do .range fica em outra pasta: aponta as imagens relativas para o projeto original
    (só na memória, para os renders; nada é salvo no original)."""
    for img in bpy.data.images:
        fp = img.filepath
        if fp.startswith("//") and not img.packed_file and not img.name.startswith("RangeTrack_"):
            alt = os.path.join(ORIG_DIR, fp[2:])
            if os.path.exists(alt):
                img.filepath = alt


def main():
    props.register()
    fix_image_paths()
    sc = bpy.data.scenes[SCENE]
    bpy.context.screen.scene = sc
    pref = "P" + SCENE.split("_")[-1] + "_"
    for o in list(sc.objects):
        if o.name.startswith(pref):
            sc.objects.unlink(o)
            bpy.data.objects.remove(o)
    num = SCENE.split("_")[-1]
    track_mesh = sc.objects.get("Pista%s_Track" % num)
    curve = sc.objects.get("Pista%s_Curve" % num)

    t0 = time.time()
    if has_mod("convert"):
        from range_track import convert
        curve = convert.convert_curve_array(track_mesh)
        print("convertido por convert.py:", curve.name, "perfil", curve.range_track.profile)
    else:
        props.default_profiles(sc)
        st = curve.range_track
        st.enabled = True
        st.profile = "Rua de bairro" if THEME == "bairro" else "Estrada de serra"
        if track_mesh is not None:
            track_mesh.hide = True
            track_mesh.hide_render = True
    st = curve.range_track
    prof = props.track_profile(curve)
    print("perfil", st.profile, [(b.name, b.kind, round(b.width, 2), b.slope_deg) for b in prof.bands] if prof else None)
    fr = frames_mod.sample(curve, st, prof)
    ed = layout.band_edges(fr, prof, st)
    print("amostras", fr.count, "comprimento %.0f m" % fr.length, "cíclico", fr.cyclic)
    t_frames = time.time() - t0

    road_objs = []
    if has_mod("sweep"):
        from range_track import sweep
        t = time.time()
        road_objs = sweep.generate_road(sc, curve, fr, ed)
        print("estrada: %d objetos em %.2f s" % (len(road_objs), time.time() - t))
        if track_mesh is not None:
            track_mesh.hide = True
            track_mesh.hide_render = True

    # objeto autoral com âncora (não pode ser apagado nem marcado)
    anc = bpy.data.objects.new("Autoral_Placa", None)
    sc.objects.link(anc)
    anc.range_track_anchor.enabled = True
    anc.range_track_anchor.track = curve.name
    anc.range_track_anchor.s = fr.length * 0.3
    anc.range_track_anchor.side = -1
    anc.range_track_anchor.offset = 1.5
    anc.range_track_anchor.height = 0.5

    decor.default_rules(curve, THEME)
    terrain._FIELD_CACHE.clear()
    t = time.time()
    tobjs = terrain.generate_terrain(sc, curve, fr, ed)
    t_ter = time.time() - t
    t = time.time()
    dobjs = decor.generate_decor(sc, curve, fr, ed)
    t_dec = time.time() - t
    moved = decor.update_anchors(sc, curve, fr, ed)
    print("terreno: %d objetos em %.2f s; decoração: %d objetos em %.2f s; frames+layout %.2f s"
          % (len(tobjs), t_ter, len(dobjs), t_dec, t_frames))
    rep = decor.last_report
    print("contagens", rep.get('counts'))
    nv = sum(len(o.data.vertices) for o in tobjs + dobjs)
    print("vértices gerados (terreno+decoração): %d" % nv)

    # ---------------- checagens
    lim = 25.0 if SCENE.endswith("4") else 40.0
    check("tempo_terreno_decor", t_ter + t_dec < lim, "%.2f s (limite %.0f)" % (t_ter + t_dec, lim))

    # estrada x terreno: raycast para cima a partir de cada vértice da estrada
    bvhs = [BVHTree.FromObject(o, sc) for o in tobjs if o.type == 'MESH' and not o.name.endswith("_Horizon")]
    pts = []
    if road_objs:
        for o in road_objs:
            if o.type != 'MESH':
                continue
            mw = o.matrix_world
            pts.extend((mw * v.co, o.name) for v in o.data.vertices)
        # pé da mureta / poste do guard-rail ficam enterrados de propósito (sweep: WALL_FOOT):
        # só contam vértices na superfície da estrada ou acima dela
        vis, enterrados = [], 0
        for p, src in pts:
            i, s_, side, dl = fr.nearest(p.x, p.y)
            if p.z < ed.surface_z(i, side, dl) - 0.05:
                enterrados += 1
            else:
                vis.append((p, src))
        pts = vis
        fonte = "vértices da estrada (sweep; %d enterrados de propósito ignorados)" % enterrados
    else:
        F = terrain.get_field(sc, curve, fr, ed)
        for i in range(fr.count):
            for side in (1, -1):
                off_e = F.eo[side][i]
                for k in range(9):
                    off = off_e * k / 8.0
                    pts.append((ed.point(i, side, off), 'layout'))
        fonte = "pontos das faixas (layout)"
    up = Vector((0, 0, 1))
    bad = []
    bnames = [o.name for o in tobjs if o.type == 'MESH' and not o.name.endswith("_Horizon")]
    for p, src in pts:
        q = Vector((p.x, p.y, p.z + 0.01))
        for b, bn in zip(bvhs, bnames):
            hit = b.ray_cast(q, up, 500.0)
            if hit[0] is not None:
                bad.append((p, hit[0].z - p.z, src, bn))
                break
    from collections import Counter
    print("   por objeto:", Counter((s_.split("_")[-2] if s_.count("_") > 1 else s_, bn.split("_")[2]) for _, _, s_, bn in bad).most_common(6))
    check("estrada_sob_terreno", not bad, "%d de %d %s" % (len(bad), len(pts), fonte))
    for p, dz, src, bn in bad[:8]:
        print("   ponto %s terreno +%.2f m (%s sob %s)" % (tuple(round(c, 1) for c in p), dz, src, bn))

    # props x borda
    placed = rep.get('placed', [])
    inv = [(k, x, y, f, d) for (k, x, y, f, d) in placed if ed.dist_to_edge(x, y) < f - 1e-6]
    check("props_folga_borda", not inv and placed, "%d de %d props abaixo da folga" % (len(inv), len(placed)))
    for k, x, y, f, d in inv[:8]:
        print("   %s em (%.1f, %.1f) folga %.2f dist %.2f" % (k, x, y, f, d))

    # árvores da cena Kits
    arv = [o for o in dobjs if "_Arvores_" in o.name]
    kits = {m.name for o in bpy.data.scenes["Kits"].objects if o.name.startswith("Arvore_tipo_")
            for m in o.data.materials if m}
    used = {m.name for o in arv for m in o.data.materials if m}
    check("arvores_da_cena_Kits", arv and used and used <= kits,
          "%d blocos, %d árvores, materiais %s" % (len(arv), rep['counts'].get('TREES_FROM_SOURCE', 0),
                                                  sorted(used)[:4]))

    # sem física em terreno e decoração
    fis = [o.name for o in tobjs + dobjs if o.game.physics_type != 'NO_COLLISION']
    check("sem_fisica", not fis, ",".join(fis[:5]))

    # âncora
    a_ok = anc in moved and abs(ed.dist_to_edge(anc.location.x, anc.location.y) - 1.5) < 1.0
    check("ancora_reposicionada", a_ok, "pos %s dist_borda %.2f" % (tuple(round(c, 1) for c in anc.location),
                                                                   ed.dist_to_edge(anc.location.x, anc.location.y)))
    check("ancora_sem_dono", getattr(anc, "range_track_owner", "") == "", "")

    # determinismo: mesma seed, mesmas props
    n1 = len(placed)
    for o in dobjs:
        sc.objects.unlink(o)
        bpy.data.objects.remove(o)
    dobjs = decor.generate_decor(sc, curve, fr, ed)
    check("determinismo", len(decor.last_report['placed']) == n1 and
          decor.last_report['placed'][:20] == placed[:20], "%d == %d" % (n1, len(decor.last_report['placed'])))

    # sem regras: nada
    saved = [(r.kind) for r in st.rules]
    for r in st.rules:
        r.enabled = False
    none_objs = decor.generate_decor(sc, curve, fr, ed)
    check("sem_regras_nada", none_objs == [], "")
    for r in st.rules:
        r.enabled = True
    print("objetos gerados:", sorted(o.name for o in tobjs)[:6], "...", len(tobjs) + len(dobjs))

    if PRINTS:
        prints(sc, fr, curve)
    if SAVE:
        path = os.path.join(OUT, "out_%s.range" % SCENE)
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
        print("salvo", path)
    ok = all(r[1] for r in results)
    print("RESULT", "OK" if ok else "FALHA")


def prints(sc, fr, curve):
    """Renders BLENDER_RENDER sem névoa (mesmo esquema do prints.py do protótipo)."""
    sc.render.engine = 'BLENDER_RENDER'
    w = sc.world
    w.mist_settings.use_mist = False
    w.horizon_color = (0.62, 0.75, 0.9)
    w.zenith_color = (0.3, 0.5, 0.85)
    w.use_sky_blend = True
    w.light_settings.use_environment_light = True
    w.light_settings.environment_energy = 0.6
    w.light_settings.gather_method = "APPROXIMATE"
    for o in sc.objects:
        if o.type == 'LAMP':
            o.data.energy = 1.2
    fd = bpy.data.lamps.new('fill', 'SUN')
    fd.energy = 0.45
    fo = bpy.data.objects.new('fill', fd)
    sc.objects.link(fo)
    fo.rotation_euler = (math.radians(60), 0, math.radians(200))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
    sc.render.use_antialiasing = True
    sc.render.use_shadows = False
    sc.render.use_raytrace = True
    cd = bpy.data.cameras.new("shot")
    cd.clip_end = 4000
    cd.lens = 24
    cam = bpy.data.objects.new("shot", cd)
    sc.objects.link(cam)
    sc.camera = cam
    cam.layers = list(curve.layers)
    fo.layers = list(curve.layers)
    tag = "%s_%s" % (SCENE, THEME)

    def shot(nome, pos, alvo):
        cam.location = pos
        cam.rotation_euler = (alvo - pos).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, tag + "_" + nome + ".png")
        bpy.ops.render.render(write_still=True)

    P = fr.pos
    N = fr.count
    xs = [p.x for p in P]
    ys = [p.y for p in P]
    zs = [p.z for p in P]
    c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, sum(zs) / N))
    shot("00_geral", c + Vector((0, -900, 700)), c)
    for k, f in enumerate([0.01, 0.12, 0.25, 0.4, 0.55, 0.7, 0.85, 0.97]):
        i = int(f * (N - 1))
        T = fr.tan[i]
        Th = Vector((T.x, T.y, 0)).normalized()
        shot("%02d_chase" % (k + 1), P[i] - Th * 14 + Vector((0, 0, 5)), P[min(N - 1, i + 12)] + Vector((0, 0, 1)))
    # vista lateral baixa do talude/costura
    i = int(0.33 * (N - 1))
    L = fr.lat[i]
    shot("10_lado", P[i] + L * 40 + Vector((0, 0, 8)), P[i])
    if not fr.cyclic:      # pontas da pista aberta (terreno além do início/fim)
        for nome, i, sg in (("11_inicio", 0, -1), ("12_fim", N - 1, 1)):
            Th = Vector((fr.tan[i].x, fr.tan[i].y, 0)).normalized()
            shot(nome, P[i] + Th * (sg * 70) + fr.lat[i] * 30 + Vector((0, 0, 35)), P[i])


main()
