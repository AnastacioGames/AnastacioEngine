"""Cena de teste do Range.track em C++ (Track Tool, F5) contra os vetores de referência do runtime.py.

Grava um .range com:
- Text "TRACK_teste.json" = conteúdo de track_ref.json (pista cozida);
- objeto com Always (pulso) -> Python que roda as consultas de ref_queries.json via Range.track,
  compara com a resposta esperada (1 mm; 1e-4 rad em bankAt/tangentAt), mede o custo de project()
  com 20 posições e chama Range.logic.endGame(). O resultado vai para o log ("OK n/n" ou as diferenças).

Uso:
  AnastacioEngine.exe -b --factory-startup --python criar_cena_track_cpp.py -- track_ref.json ref_queries.json saida.range log.txt [lib.range]
  AnastacioRuntime.exe --server saida.range
"""
import bpy, sys

argv = sys.argv[sys.argv.index('--') + 1:]
track_path, queries_path, out_path, log_path = argv[:4]
lib_path = argv[4] if len(argv) > 4 else ''

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'

with open(track_path, encoding='utf-8') as f:
    track_json = f.read()

# Biblioteca para o teste de LibLoad: só um Text "TRACK_lib.json" (mesma pista).
if lib_path:
    lib_txt = bpy.data.texts.new('TRACK_lib.json')
    lib_txt.write(track_json)
    bpy.ops.wm.save_as_mainfile(filepath=lib_path, copy=True)
    bpy.data.texts.remove(lib_txt)
txt = bpy.data.texts.new('TRACK_teste.json')
txt.write(track_json)

text = bpy.data.texts.new('track_cpp_test.py')
text.write('''import Range, json, math, time, random
QUERIES = %r
LOG = %r
LIB = %r
TOL = 1e-3
TOL_ANG = 1e-4


def flat(v):
    if isinstance(v, (bool, str)) or v is None:
        return [v]
    if isinstance(v, (int, float)):
        return [float(v)]
    out = []
    for x in v:
        out.extend(flat(x))
    return out


def compare(fn, got, exp):
    tol = TOL_ANG if fn in ('bankAt', 'tangentAt', 'lateralAt') else TOL
    a, b = flat(got), flat(exp)
    if len(a) != len(b):
        return 'tamanho %%d != %%d' %% (len(a), len(b)), 0.0
    worst = 0.0
    for x, y in zip(a, b):
        if isinstance(x, (str, bool)) or isinstance(y, (str, bool)) or x is None or y is None:
            if x != y:
                return '%%r != %%r' %% (x, y), worst
            continue
        e = abs(x - y)
        worst = max(worst, e)
        if e > tol:
            return 'erro %%.6g > %%g' %% (e, tol), worst
    return None, worst


def load_queries():
    """Lista de {fn, args, expect}. Aceita também o formato de ref_queries.json (test_runtime.py):
    {"pos_queries": [{"pos", "project", "isOnRoad"}], "s_queries": [{"s", "pointAt", ...}], "length"}."""
    with open(QUERIES, encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if 'queries' in data:
        return data['queries']
    out = []
    for q in data.get('pos_queries', ()):
        for fn in ('project', 'isOnRoad'):
            if fn in q:
                out.append({'fn': fn, 'args': [q['pos']], 'expect': q[fn]})
    for q in data.get('s_queries', ()):
        for fn, exp in q.items():
            if fn != 's':
                out.append({'fn': fn, 'args': [q['s']], 'expect': exp})
    if 'length' in data:
        out.append({'fn': 'length', 'args': [], 'expect': data['length']})
    return out


def run():
    lines = []
    tr = Range.track.get('teste')
    lines.append('names=%%s get=%%r' %% (Range.track.names(), tr))
    if tr is None:
        lines.append('FALHA: Range.track.get("teste") devolveu None')
        return lines
    queries = load_queries()
    ok = 0
    worst = {}
    for q in queries:
        fn = q.get('fn') or q.get('method') or q.get('op')
        args = q.get('args')
        if args is None:
            args = [q['pos']] if 'pos' in q else [q['s']]
        exp = q.get('expect', q.get('result', q.get('out')))
        if fn in ('length', 'name', 'cyclic'):
            got = getattr(tr, fn)
        else:
            got = getattr(tr, fn)(*args)
        if fn == 'project':
            got = list(got)
            # pista cíclica: s perto de 0 e perto de length são o mesmo ponto
            if tr.cyclic and abs(got[0] - exp[0]) > tr.length * 0.5:
                got[0] += tr.length if got[0] < exp[0] else -tr.length
            got = tuple(got)
        err, w = compare(fn, got, exp)
        worst[fn] = max(worst.get(fn, 0.0), w)
        if err is None:
            ok += 1
        else:
            lines.append('DIF %%s%%r: got=%%r exp=%%r (%%s)' %% (fn, tuple(args), got, exp, err))
    lines.append(('OK %%d/%%d' if ok == len(queries) else 'FALHA %%d/%%d') %% (ok, len(queries)))
    lines.append('erro max por funcao: ' + ', '.join('%%s=%%.3g' %% kv for kv in sorted(worst.items())))

    # custo de project(): 20 carros perto da pista (ate 8 m do centro), varias rodadas
    rnd = random.Random(1)
    L = tr.length
    cars = []
    for k in range(20):
        s = rnd.uniform(0.0, L)
        p = tr.pointAt(s)
        lat = tr.lateralAt(s)
        cars.append(p + lat * rnd.uniform(-8.0, 8.0))
    rounds = 500
    t0 = time.perf_counter()
    for _ in range(rounds):
        for p in cars:
            tr.project(p)
    dt = time.perf_counter() - t0
    lines.append('project: %%.5f ms por chamada (%%d chamadas, 20 carros)' %% (dt * 1000.0 / (rounds * 20), rounds * 20))
    t0 = time.perf_counter()
    for _ in range(rounds):
        for p in cars:
            tr.pointAt(1.0)
    dt = time.perf_counter() - t0
    lines.append('pointAt: %%.5f ms por chamada' %% (dt * 1000.0 / (rounds * 20)))

    # API do módulo: nome do Text, pista inexistente, alias bge.track, fromJson
    import bge
    checks = [
        ('get(TRACK_teste.json)', Range.track.get('TRACK_teste.json') is not None),
        ('get(inexistente) is None', Range.track.get('nao_existe') is None),
        ('bge.track is Range.track', bge.track is Range.track),
        ('Track type', isinstance(tr, Range.track.Track)),
        ('fromJson', Range.track.fromJson(json.dumps({'s': [0, 1], 'px': [0, 1]})).length == 1.0),
    ]
    # project(pos, near): grampo com duas retas paralelas a 8 m (ida y=0, volta y=8)
    pts = [(float(x), 0.0, 1.0, 0.0) for x in range(0, 101)]
    pts += [(100.0 + 4.0 * math.sin(a * math.pi / 12), 4.0 - 4.0 * math.cos(a * math.pi / 12),
             math.cos(a * math.pi / 12), math.sin(a * math.pi / 12)) for a in range(1, 12)]
    pts += [(float(x), 8.0, -1.0, 0.0) for x in range(100, -1, -1)]
    acc, ss = 0.0, [0.0]
    for a, b in zip(pts, pts[1:]):
        acc += math.hypot(b[0] - a[0], b[1] - a[1])
        ss.append(acc)
    hp = Range.track.fromJson(json.dumps({'s': ss, 'px': [p[0] for p in pts], 'py': [p[1] for p in pts],
                                          'tx': [p[2] for p in pts], 'ty': [p[3] for p in pts]}), 'grampo')
    s_ida = hp.project((50.0, 0.0))[0]
    g = hp.project((50.0, 4.2))[0]                      # mais perto da volta: sem near vai para a volta
    n1 = hp.project((50.0, 4.2), near=s_ida)[0]          # com near fica na ida
    n2 = hp.project((50.0, 4.2), s_ida)[0]               # posicional
    lost = hp.project((50.0, 8.0), near=s_ida)[0]        # perto da volta mas a 8 m: ainda na janela
    far = hp.project((50.0, 30.0), near=s_ida)[0]        # 30 m da ida (> 15 m): busca global, acha a volta
    none = hp.project((50.0, 4.2), near=None)[0]
    lines.append('grampo: ida %%.2f, sem near %%.2f, near %%.2f, longe %%.2f' %% (s_ida, g, n1, far))
    checks += [
        ('near: sem near vai para a volta', g > hp.length / 2),
        ('near: fica na ida', abs(n1 - s_ida) < 0.5 and n1 == n2),
        ('near=None igual a sem near', none == g),
        ('near: longe da janela = busca global', far > hp.length / 2),
        ('near: s ruim levanta TypeError', _raises(lambda: hp.project((0, 0), near='x'))),
    ]
    if LIB:
        before = Range.track.names()
        Range.logic.LibLoad(LIB, 'Scene', load_scripts=True)
        after = Range.track.names()
        lt = Range.track.get('lib')
        checks.append(('LibLoad: names %%s -> %%s' %% (before, after), 'lib' in after and 'lib' not in before))
        checks.append(('LibLoad: get(lib) igual', lt is not None and abs(lt.length - tr.length) < 1e-9))
        # LibFree compara o caminho como o LibList guardou (barras invertidas no Windows)
        import os
        lib_name = next((p for p in Range.logic.LibList() if os.path.normcase(os.path.normpath(p)) ==
                         os.path.normcase(os.path.normpath(LIB))), LIB)
        lines.append('LibFree() -> %%r' %% Range.logic.LibFree(lib_name))  # liberado depois: próximos ticks
    bad = [n for n, ok in checks if not ok]
    lines.append('API: %%d/%%d%%s' %% (len(checks) - len(bad), len(checks), (' FALHA: ' + '; '.join(bad)) if bad else ''))
    for n, ok in checks:
        if n.startswith('LibLoad: names'):
            lines.append('  ' + n)
    return lines


def _raises(fn):
    try:
        fn()
    except TypeError:
        return True
    return False


def tick(cont):
    g = Range.logic.globalDict
    if 'track_lines' not in g:
        try:
            g['track_lines'] = run()
        except Exception:
            import traceback
            g['track_lines'] = ['EXCECAO', traceback.format_exc()]
        if LIB:
            return
    if g.get('track_done'):
        return
    lines = g['track_lines']
    if LIB:
        # LibFree só some da lista de arquivos quando o conversor termina de liberar (alguns quadros)
        g['track_wait'] = g.get('track_wait', 0) + 1
        free_ok = Range.track.get('lib') is None and 'lib' not in Range.track.names()
        if not free_ok and g['track_wait'] < 60:
            return
        still = Range.logic.LibList()
        verdict = 'OK' if free_ok else ('INCONCLUSIVO (o conversor ainda lista a lib)' if still else 'FALHA')
        lines.append('LibFree (%%d quadros depois): get(lib) is None -> %%s; LibList=%%s' %% (
            g['track_wait'], verdict, still))
    g['track_done'] = True
    with open(LOG, 'w', encoding='utf-8') as f:
        f.write(chr(10).join(lines) + chr(10) + '# fim' + chr(10))
    Range.logic.endGame()
''' % (queries_path, log_path, lib_path))

ob = bpy.data.objects.new('TrackTest', None)
scene.objects.link(ob)
scene.objects.active = ob
bpy.ops.logic.sensor_add(type='ALWAYS', name='Always', object=ob.name)
bpy.ops.logic.controller_add(type='PYTHON', name='Py', object=ob.name)
sens = ob.game.sensors['Always']
sens.use_pulse_true_level = True
cont = ob.game.controllers['Py']
cont.mode = 'MODULE'
cont.module = 'track_cpp_test.tick'
sens.link(cont)

cam_data = bpy.data.cameras.new('Cam')
cam = bpy.data.objects.new('Cam', cam_data)
cam.location = (0, -6, 1)
scene.objects.link(cam)
scene.camera = cam

bpy.ops.wm.save_as_mainfile(filepath=out_path)
print('saved', out_path)
