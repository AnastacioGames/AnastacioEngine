# Relatorio do Range Trace (CM_Trace.h, docs/range-trace.md).
#
#   python tools/debug/relatorio_trace.py <pasta do trace> [--resumo]
#
# Le <pasta>/trace.jsonl e grava ao lado:
#   relatorio.html  - tabelas completas (abrir no navegador);
#   resumo.md       - so os totais e os maiores itens de cada lista, curto o bastante para colar numa IA.
# --resumo imprime o resumo.md no terminal.
#
# Cruza o que foi carregado (modulo "load") com o que foi desenhado (modulo "usage"):
#   - objetos com malha convertidos e nunca desenhados (nem pela camera, nem em sombra);
#   - malhas/materiais/imagens que so servem a esses objetos;
#   - cargas durante o jogo (On Demand, LibLoad, imagens enviadas tarde), candidatas a travada.
# Modulo "frames": frames lentos, com as categorias que pesaram e o que carregou neles.
# Modulo "sector": custo por trecho do trilho de camera (mapa de calor da pista).
import html
import json
import os
import sys
from collections import defaultdict

# Primeiros frames contam como "load": a cena inicial e as cenas de fundo terminam de subir neles.
FRAMES_DE_LOAD = 5
TOP_RESUMO = 15
# Frame lento: acima de 2x a mediana e acima de 1/30 s.
PICO_FATOR = 2.0
PICO_MIN_MS = 1000.0 / 30.0
# Trechos do trilho; "quente" = custo medio acima de QUENTE x a mediana dos trechos.
SETORES = 40
QUENTE = 1.25
QUENTE_MIN_MS = 1.0
# Primeiros frames do trilho ainda pegam o fim do load da cena.
TRILHO_DESCARTE = 10
# Espera ociosa do loop; fica fora do custo do frame.
OCIOSO = ('Sleeping',)


def ler_eventos(caminho):
    eventos = []
    with open(caminho, encoding='utf-8') as f:
        for n, linha in enumerate(f, 1):
            linha = linha.strip()
            if not linha:
                continue
            try:
                eventos.append(json.loads(linha))
            except json.JSONDecodeError:
                # Ultima linha cortada quando o jogo fecha a forca.
                print('aviso: linha %d ignorada (incompleta)' % n, file=sys.stderr)
    return eventos


def mb_imagem(ev):
    # RGBA8, mais um terco de mipmaps.
    return ev['w'] * ev['h'] * 4 * (4 / 3 if ev.get('mipmap') else 1) / (1024 * 1024)


def custo(frame):
    return frame['ms'] - sum(frame['c'].get(k, 0.0) for k in OCIOSO)


def principais(categorias, n=3):
    itens = sorted(((k, v) for k, v in categorias.items() if k not in OCIOSO), key=lambda x: x[1], reverse=True)
    return itens[:n]


def mediana(valores):
    v = sorted(valores)
    return v[len(v) // 2] if v else 0.0


def percentil(valores, p):
    v = sorted(valores)
    return v[min(len(v) - 1, int(len(v) * p))] if v else 0.0


def analisar_frames(eventos):
    """Frames lentos (modulo frames) e custo por trecho do trilho (modulo sector)."""
    frames = {}
    for e in eventos:
        if e['ev'] == 'frame':
            frames[e['f']] = e
    cargas = defaultdict(list)
    for e in eventos:
        if e['ev'] == 'scene_load':
            cargas[e['f']].append('cena %s (%.0f ms)' % (e['scene'], e['ms']))
        elif e['ev'] == 'load_shaders':
            ms = e.get('textures_ms', 0) + e.get('shaders_ms', 0)
            if ms >= 1:
                cargas[e['f']].append('texturas+shaders %s (%.0f ms)' % (e['scene'], ms))
        elif e['ev'] == 'convert_object':
            cargas[e['f']].append('On Demand %s (%.0f ms)' % (e['name'], e['ms']))
        elif e['ev'] == 'image' and e['ms'] >= 1:
            cargas[e['f']].append('imagem %s (%.0f ms)' % (e['name'], e['ms']))

    jogo = [fr for f, fr in frames.items() if f > FRAMES_DE_LOAD]
    med = mediana([custo(fr) for fr in jogo])
    limite = max(PICO_FATOR * med, PICO_MIN_MS)
    picos = []
    for fr in sorted(jogo, key=custo, reverse=True):
        if custo(fr) <= limite:
            break
        # O custo medido no fim do frame f inclui o render do frame anterior.
        junto = cargas.get(fr['f'], []) + cargas.get(fr['f'] - 1, [])
        picos.append(dict(f=fr['f'], t=fr['t'], ms=custo(fr), cats=principais(fr['c']), cargas=junto))

    # Trilho: posicao de cada frame (ultimo evento rail do frame) cruzada com o custo do frame seguinte.
    trilho = {}
    for e in eventos:
        if e['ev'] == 'rail':
            trilho[e['f']] = e
    inicio = next((e for e in eventos if e['ev'] == 'rail_start'), None)
    fim = next((e for e in eventos if e['ev'] == 'rail_end'), None)
    pontos = []
    for f, r in sorted(trilho.items())[TRILHO_DESCARTE:]:
        fr = frames.get(f + 1) or frames.get(f)
        if fr:
            pontos.append(dict(p=r['p'], x=r['x'], y=r['y'], ms=custo(fr), c=fr['c'], f=f))
    setores = []
    if pontos:
        grupos = defaultdict(list)
        for pt in pontos:
            grupos[min(int(pt['p'] * SETORES), SETORES - 1)].append(pt)
        for i in range(SETORES):
            g = grupos.get(i, [])
            if not g:
                setores.append(None)
                continue
            soma = defaultdict(float)
            for pt in g:
                for k, v in pt['c'].items():
                    soma[k] += v
            ms = sorted(pt['ms'] for pt in g)
            setores.append(dict(i=i, n=len(g), media=sum(ms) / len(ms), p95=ms[int(len(ms) * 0.95) if len(ms) > 1 else 0],
                                max=ms[-1], cats=principais({k: v / len(g) for k, v in soma.items()}),
                                x=sum(pt['x'] for pt in g) / len(g), y=sum(pt['y'] for pt in g) / len(g)))
        med_setor = mediana([st['media'] for st in setores if st])
        for st in setores:
            if st:
                st['quente'] = st['media'] > QUENTE * med_setor and st['media'] - med_setor >= QUENTE_MIN_MS
    else:
        med_setor = 0.0
    return dict(frames=frames, frame_mediana=med, pico_limite=limite, picos=picos, trilho_inicio=inicio,
                trilho_fim=fim, pontos=pontos, setores=setores, setor_mediana=med_setor)


def analisar(eventos):
    sessao = next((e for e in eventos if e['ev'] == 'session'), {})
    modulos = sessao.get('modules', [])
    cenas = [e for e in eventos if e['ev'] == 'scene_load']
    shaders = {e['scene']: e for e in eventos if e['ev'] == 'load_shaders'}
    objetos = [e for e in eventos if e['ev'] == 'object']
    malhas = {}
    for e in eventos:
        if e['ev'] == 'mesh':
            malhas.setdefault(e['name'], e)
    materiais = {}
    for e in eventos:
        if e['ev'] == 'material':
            materiais.setdefault(e['name'], e)
    imagens = {}
    for e in eventos:
        if e['ev'] == 'image':
            imagens.setdefault(e['name'], e)  # primeiro envio
    deixados = [e for e in eventos if e['ev'] == 'object_left_out']
    convertidos = [e for e in eventos if e['ev'] == 'convert_object']

    # Desenhado: por nome, em qualquer cena (replicas e objetos On Demand mudam de cena ao entrar).
    vistos = {'camera': {}, 'shadow': {}}
    for e in eventos:
        if e['ev'] == 'visible':
            vistos[e['pass']].setdefault(e['name'], e)
    tem_uso = 'usage' in modulos and any(vistos.values())

    # Objetos com malha: o nome pode repetir entre cenas; fica a primeira conversao de cada (cena, nome).
    com_malha = {}
    for o in objetos:
        if o['meshes']:
            com_malha.setdefault((o['scene'], o['name']), o)

    def tris(o):
        return sum(malhas.get(m, {}).get('tris', 0) for m in o['meshes'])

    nunca = []
    so_sombra = []
    invisiveis = []  # navmesh e objetos invisiveis por design: nao contam como desperdicio de desenho
    for o in com_malha.values():
        if o['name'] in vistos['camera']:
            continue
        if o.get('navmesh') or o.get('visible') is False:
            if o['name'] not in vistos['shadow']:
                invisiveis.append(o)
                continue
        if o['name'] in vistos['shadow']:
            so_sombra.append(o)
        else:
            nunca.append(o)
    nunca.sort(key=tris, reverse=True)
    so_sombra.sort(key=tris, reverse=True)
    invisiveis.sort(key=tris, reverse=True)

    # Malha/material/imagem "a toa": todos os objetos que usam nunca foram desenhados.
    usada = set()
    for o in com_malha.values():
        if o['name'] in vistos['camera'] or o['name'] in vistos['shadow']:
            usada.update(o['meshes'])
    malhas_atoa = sorted((m for m in {m for o in nunca for m in o['meshes']} if m not in usada),
                         key=lambda m: malhas.get(m, {}).get('tris', 0), reverse=True)
    mat_usado = {mat for m in usada for mat in malhas.get(m, {}).get('materials', [])}
    mats_atoa = sorted({mat for m in malhas_atoa for mat in malhas.get(m, {}).get('materials', [])} - mat_usado)
    img_usada = {i for mat in mat_usado for i in materiais.get(mat, {}).get('images', [])}
    imgs_atoa = sorted(({i for mat in mats_atoa for i in materiais.get(mat, {}).get('images', [])} - img_usada),
                       key=lambda i: mb_imagem(imagens[i]) if i in imagens else 0, reverse=True)

    # Cargas durante o jogo: depois dos primeiros frames.
    tardias = []
    for e in convertidos:
        if e['f'] > FRAMES_DE_LOAD:
            tardias.append(('On Demand', e['name'], e['scene'], e['ms'], e['f'], e['t']))
    for e in cenas:
        if e['f'] > FRAMES_DE_LOAD and not e['scene'].startswith('..'):
            sh = shaders.get(e['scene'], {})
            ms = e['ms'] + sh.get('textures_ms', 0) + sh.get('shaders_ms', 0)
            tardias.append(('LibLoad' if e['libload'] else 'Cena', e['scene'], e['scene'], ms, e['f'], e['t']))
    for e in imagens.values():
        if e['f'] > FRAMES_DE_LOAD:
            tardias.append(('Imagem', e['name'], '', e['ms'], e['f'], e['t']))
    tardias.sort(key=lambda x: x[3], reverse=True)

    return dict(sessao=sessao, modulos=modulos, cenas=cenas, shaders=shaders, objetos=objetos, malhas=malhas,
                materiais=materiais, imagens=imagens, deixados=deixados, tem_uso=tem_uso, nunca=nunca,
                so_sombra=so_sombra, invisiveis=invisiveis, malhas_atoa=malhas_atoa, mats_atoa=mats_atoa, imgs_atoa=imgs_atoa,
                tardias=tardias, tris=tris, com_malha=com_malha,
                fim=next((e for e in reversed(eventos) if e['ev'] == 'end'), None), **analisar_frames(eventos),
                duracao=eventos[-1]['t'] if eventos else 0.0,
                _eventos_rail=[e for e in eventos if e['ev'] in ('rail_start', 'rail_go', 'rail_end')])


def analisar_extras(pasta, eventos):
    """Modulos work (eventos + objetos.txt), shaders (shaders.txt) e profile (arquivos ao lado)."""
    x = {}
    work = [e for e in eventos if e['ev'] == 'work' and e['f'] > FRAMES_DE_LOAD]
    if work:
        chaves = sorted({k for e in work for k in e if k not in ('t', 'f', 'ev')})
        linhas = []
        for k in chaves:
            v = sorted(e.get(k, 0) for e in work)
            linhas.append((k, mediana(v), percentil(v, 0.95), v[-1], sum(v) / len(v)))
        x['work'] = dict(n=len(work), linhas=linhas)
    objetos = os.path.join(pasta, 'objetos.txt')
    if os.path.isfile(objetos):
        soma = defaultdict(float)
        segundos = set()
        with open(objetos, encoding='utf-8', errors='replace') as f:
            for linha in f:
                partes = linha.split()
                if len(partes) < 4 or not partes[0].isdigit():
                    continue
                segundos.add(partes[0])
                try:
                    soma[(partes[1], ' '.join(partes[2:-1]))] += float(partes[-1])
                except ValueError:
                    pass
        n = max(len(segundos), 1)
        x['objetos'] = sorted(((tipo, nome, v / n) for (tipo, nome), v in soma.items()), key=lambda r: r[2], reverse=True)
    shaders = os.path.join(pasta, 'shaders.txt')
    if os.path.isfile(shaders):
        itens = []
        texturas = 0
        with open(shaders, encoding='utf-8', errors='replace') as f:
            for linha in f:
                partes = linha.split()
                if len(partes) < 3 or not partes[0].startswith('t='):
                    continue
                try:
                    t = float(partes[0][2:].rstrip('s'))
                    fr = int(partes[1].split('=')[1])
                except (ValueError, IndexError):
                    continue
                if partes[2] == 'texture':
                    texturas += 1
                elif partes[2].startswith('ms='):
                    tipo = partes[3] if len(partes) > 3 else '?'
                    nome = ' '.join(partes[5:]) if tipo == 'image' else partes[-1]
                    itens.append(dict(t=t, f=fr, ms=float(partes[2][3:]), tipo=tipo, nome=nome or '-'))
        por_tipo = defaultdict(lambda: [0, 0.0])
        for it in itens:
            por_tipo[it['tipo']][0] += 1
            por_tipo[it['tipo']][1] += it['ms']
        x['shaders'] = dict(itens=itens, texturas=texturas, por_tipo=dict(por_tipo),
                            no_jogo=sorted((it for it in itens if it['f'] > FRAMES_DE_LOAD and it['tipo'] != 'prefetch'
                                            and it['ms'] >= 1.0), key=lambda it: it['ms'], reverse=True))
    arquivos = []
    for nome in ('profile.txt', 'ragdoll.jsonl', 'ragdoll-summary.md', 'objetos.txt', 'shaders.txt'):
        if os.path.isfile(os.path.join(pasta, nome)):
            arquivos.append(nome)
    tmp = os.path.join(pasta, 'tmp')
    if os.path.isdir(tmp):
        arquivos += ['tmp/' + n for n in sorted(os.listdir(tmp)) if n.endswith('.txt')]
    x['arquivos'] = arquivos
    return x


def obs_objeto(o):
    """Camada e marcas que mudam a leitura de "nunca desenhado"."""
    partes = ['ativa' if o['active_layer'] else 'inativa']
    if o.get('static_batch'):
        partes.append('static batch')
    return ', '.join(partes)


def nome_cena(nome):
    return '(On Demand)' if nome.startswith('..') else nome


def texto_cats(cats):
    return ', '.join('%s %.1f' % (k, v) for k, v in cats)


def chips_cats(cats):
    """Categorias com a mesma cor do grafico; a maior em negrito."""
    return Html(' '.join('<span class="cat"><i style="background:%s"></i>%s%s %.1f%s</span>' % (
        cor_cat(k), '<b>' if n == 0 else '', esc(k), v, '</b>' if n == 0 else '') for n, (k, v) in enumerate(cats)))


def resumo_trilho(a, w):
    if not a['trilho_inicio'] and not a['trilho_fim']:
        return
    w('')
    w('## Trilho de camera (sector)')
    w('')
    ini, fim = a['trilho_inicio'], a['trilho_fim']
    if ini:
        w('Cena %s, curva %s, camera %s, %.0f s, %.0f m.' % (ini['scene'], ini['curve'], ini['camera'], ini['seconds'],
                                                            ini['length']))
    if fim and fim.get('reason') != 'finished':
        w('**Trilho nao terminou** (%s).' % fim.get('reason'))
    setores = [st for st in a['setores'] if st]
    if not setores:
        w('Sem frames medidos no trilho (ligue o modulo frames junto com sector).')
        return
    w('Mediana dos trechos: %.1f ms. Trechos quentes (acima de %.0f%% dela e %.0f ms a mais):' % (
        a['setor_mediana'], QUENTE * 100, QUENTE_MIN_MS))
    if not any(st['quente'] for st in setores):
        w('Nenhum: o custo e parecido na pista toda.')
        return
    w('')
    w('| trecho | % da curva | media ms | p95 ms | max ms | categorias | centro x,y |')
    w('|---|---|---|---|---|---|---|')
    for st in sorted((st for st in setores if st['quente']), key=lambda st: st['media'], reverse=True):
        w('| %d | %d-%d%% | %.1f | %.1f | %.1f | %s | %.0f, %.0f |' % (
            st['i'] + 1, st['i'] * 100 // SETORES, (st['i'] + 1) * 100 // SETORES, st['media'], st['p95'], st['max'],
            texto_cats(st['cats']), st['x'], st['y']))


def resumo_md(a):
    out = []
    w = out.append
    w('# Range Trace - resumo')
    w('')
    w('Modulos: %s. Ultimo evento aos %.0f s%s.' % (', '.join(a['modulos']) or '-', a['duracao'],
                                             '' if a['fim'] else ' (sem evento "end": jogo fechado a forca ou travou)'))
    if not a['tem_uso']:
        w('')
        w('**Sem eventos de uso**: modulo usage desligado ou nada foi desenhado (ex.: `--server`). '
          'As listas "nunca desenhado" abaixo ficam vazias.')
    w('')
    w('## Cenas carregadas')
    w('')
    w('| cena | frame | conversao ms | texturas ms | shaders ms | objetos | malhas | materiais |')
    w('|---|---|---|---|---|---|---|---|')
    for c in a['cenas']:
        sh = a['shaders'].get(c['scene'], {})
        w('| %s%s | %d | %.0f | %.0f | %.0f | %d | %d | %d |' % (
            nome_cena(c['scene']), ' (LibLoad)' if c['libload'] else '', c['f'], c['ms'], sh.get('textures_ms', 0),
            sh.get('shaders_ms', 0), c['objects'], c['meshes'], c['materials']))
    w('')
    w('Objetos com malha convertidos: %d. Deixados de fora pelo Load Mode: %d.' % (
        len(a['com_malha']), len(a['deixados'])))
    if a['tem_uso']:
        tri_nunca = sum(a['tris'](o) for o in a['nunca'])
        mb = sum(mb_imagem(a['imagens'][i]) for i in a['imgs_atoa'] if i in a['imagens'])
        w('')
        w('## Carregado e nunca desenhado')
        w('')
        w('%d objetos (%d triangulos), %d malhas, %d materiais, %d imagens (~%.1f MB de VRAM enviados).' % (
            len(a['nunca']), tri_nunca, len(a['malhas_atoa']), len(a['mats_atoa']), len(a['imgs_atoa']), mb))
        w('Objetos em camada inativa sao modelos de Add Object: so contam se o jogo nunca os adicionou.')
        w('Invisiveis por design (navmesh, Visible desligado) ficam fora: %d objetos.' % len(a['invisiveis']))
        w('')
        w('| objeto | cena | camada | triangulos |')
        w('|---|---|---|---|')
        for o in a['nunca'][:TOP_RESUMO]:
            w('| %s | %s | %s | %d |' % (o['name'], nome_cena(o['scene']), obs_objeto(o), a['tris'](o)))
        if a['so_sombra']:
            w('')
            w('## Desenhado so em sombra (%d)' % len(a['so_sombra']))
            w('')
            for o in a['so_sombra'][:TOP_RESUMO]:
                w('- %s (%s, %d tris)' % (o['name'], nome_cena(o['scene']), a['tris'](o)))
    if a['frames']:
        w('')
        w('## Frames lentos (%d)' % len(a['picos']))
        w('')
        w('Mediana %.1f ms; lento = acima de %.1f ms (sem contar a espera ociosa).' % (a['frame_mediana'], a['pico_limite']))
        if a['picos']:
            w('')
            w('| frame | segundo | ms | categorias | carregou junto |')
            w('|---|---|---|---|---|')
            for pk in a['picos'][:TOP_RESUMO]:
                w('| %d | %.1f | %.1f | %s | %s |' % (pk['f'], pk['t'], pk['ms'], texto_cats(pk['cats']),
                                                     '; '.join(pk['cargas']) or '-'))
    resumo_trilho(a, w)
    x = a.get('extras', {})
    if 'work' in x:
        w('')
        w('## Trabalho por frame (mediana / p95 / max)')
        w('')
        for k, med, p95, mx, _media in x['work']['linhas']:
            w('- %s: %.0f / %.0f / %d' % (k, med, p95, mx))
        for tipo, nome, v in x.get('objetos', [])[:10]:
            w('- objeto %s %s: %.1f por frame' % (tipo, nome, v))
    if 'shaders' in x:
        w('')
        w('## Shaders e imagens no jogo (%d, depois do frame %d e acima de 1 ms)' % (len(x['shaders']['no_jogo']), FRAMES_DE_LOAD))
        w('')
        for it in x['shaders']['no_jogo'][:TOP_RESUMO]:
            w('- %s %s: %.1f ms, frame %d' % (it['tipo'], it['nome'], it['ms'], it['f']))
    w('')
    w('## Cargas durante o jogo (depois do frame %d)' % FRAMES_DE_LOAD)
    w('')
    if a['tardias']:
        w('| tipo | nome | ms | frame | segundo |')
        w('|---|---|---|---|---|')
        for tipo, nome, _cena, ms, f, t in a['tardias'][:TOP_RESUMO]:
            w('| %s | %s | %.1f | %d | %.1f |' % (tipo, nome, ms, f, t))
    else:
        w('Nenhuma.')
    return '\n'.join(out) + '\n'


# --- Relatorio HTML -------------------------------------------------------------------------------------------
# Painel de telemetria: resumo no topo, linha do tempo dos frames, mapa da pista e as listas do load.
# Arquivo unico, abre offline (as fontes do Google sao opcionais; sem rede cai nas fontes do sistema).

CSS = '''
/* Painel de box: faixa de cabecalho, numeros grandes em fonte condensada, dados em mono. */
:root {
  --bg:#eef0f3; --panel:#ffffff; --sunk:#e4e7ec; --line:#d5d9e0; --fg:#171a1f; --muted:#5f6672;
  --accent:#2f6fd6; --ok:#2e9d5b; --warn:#c77d12; --bad:#d1452f;
  --f-display:'Barlow Condensed', 'Arial Narrow', 'Roboto Condensed', sans-serif;
  --f-body:'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif;
  --f-data:'JetBrains Mono', Consolas, 'Cascadia Mono', monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#121418; --panel:#1b1e24; --sunk:#23272f; --line:#2f343d; --fg:#e7e9ee; --muted:#959cab;
  --accent:#6ea1ff; --ok:#43b874; --warn:#e7a43a; --bad:#ef6a52; color-scheme:dark; } }
:root[data-theme="dark"] {
  --bg:#121418; --panel:#1b1e24; --sunk:#23272f; --line:#2f343d; --fg:#e7e9ee; --muted:#959cab;
  --accent:#6ea1ff; --ok:#43b874; --warn:#e7a43a; --bad:#ef6a52; color-scheme:dark; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.5 var(--f-body); }
.wrap { max-width:1280px; margin:0 auto; padding-block:0 48px;
  padding-left:max(16px, env(safe-area-inset-left, 0px)); padding-right:max(16px, env(safe-area-inset-right, 0px)); }
header.topo { background:var(--panel); border-bottom:1px solid var(--line); }
header.topo .wrap { padding-block:20px 0; display:grid; gap:14px; }
.titulo { display:flex; flex-wrap:wrap; align-items:baseline; gap:6px 16px; }
.titulo h1 { margin:0; font:600 34px/1 var(--f-display); letter-spacing:.01em; text-wrap:balance; }
.titulo .jogo { font:500 20px/1 var(--f-display); color:var(--muted); }
.titulo .fim { margin-left:auto; display:flex; gap:8px; align-items:center; }
.meta { display:flex; flex-wrap:wrap; gap:6px 18px; color:var(--muted); font-size:13px; }
.meta b { color:var(--fg); font-weight:500; }
.chip { display:inline-block; padding:1px 8px; border-radius:999px; font:500 11px/18px var(--f-data);
  text-transform:uppercase; letter-spacing:.06em; border:1px solid var(--line); color:var(--muted); }
.chip.ok { color:var(--ok); border-color:currentColor; } .chip.warn { color:var(--warn); border-color:currentColor; }
.chip.bad { color:var(--bad); border-color:currentColor; }
nav.secoes { display:flex; gap:2px; overflow-x:auto; margin:0 -4px; }
nav.secoes a { padding:8px 10px; color:var(--muted); text-decoration:none; font:500 15px/1 var(--f-display);
  letter-spacing:.04em; text-transform:uppercase; border-bottom:2px solid transparent; white-space:nowrap; }
nav.secoes a:hover, nav.secoes a:focus-visible { color:var(--fg); border-bottom-color:var(--accent); outline:none; }
button.tema { background:none; border:1px solid var(--line); color:var(--muted); border-radius:6px; padding:3px 9px;
  font:12px var(--f-body); cursor:pointer; }
button.tema:hover, button.tema:focus-visible { color:var(--fg); border-color:var(--accent); outline:none; }

.kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:1px; background:var(--line);
  border:1px solid var(--line); border-radius:10px; overflow:hidden; margin-top:20px; }
.kpi { background:var(--panel); padding:14px 16px; display:grid; gap:2px; align-content:start; }
.kpi .rot { font:500 11px/1.3 var(--f-data); text-transform:uppercase; letter-spacing:.07em; color:var(--muted); }
.kpi .val { font:600 34px/1.05 var(--f-display); font-variant-numeric:tabular-nums; }
.kpi .val small { font-size:17px; font-weight:500; color:var(--muted); margin-left:3px; }
.kpi .sub { font-size:12px; color:var(--muted); }
.kpi.ok .val { color:var(--ok); } .kpi.warn .val { color:var(--warn); } .kpi.bad .val { color:var(--bad); }

section { margin-top:36px; scroll-margin-top:12px; }
section > h2 { display:flex; align-items:baseline; gap:10px; margin:0 0 4px; font:600 24px/1.1 var(--f-display);
  letter-spacing:.01em; text-wrap:balance; }
section > h2 .n { font:500 13px var(--f-data); color:var(--muted); }
h3 { margin:22px 0 4px; font:600 18px/1.2 var(--f-display); letter-spacing:.02em; }
p.nota { margin:0 0 12px; color:var(--muted); max-width:75ch; }
p.aviso { color:var(--warn); font-weight:500; }
.painel { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px; min-width:0; }

/* Linha do tempo */
.tempo { position:relative; height:200px; margin:6px 0 0 44px; }
.tempo svg { position:absolute; inset:0; width:100%; height:100%; overflow:visible; }
.tempo .ylab { position:absolute; left:-44px; width:38px; text-align:right; transform:translateY(-50%);
  font:11px var(--f-data); color:var(--muted); }
.tempo .linha-ref { position:absolute; left:0; right:0; border-top:1px dashed var(--line); }
.tempo .linha-ref.lim { border-top-color:var(--bad); opacity:.6; }
.tempo .linha-ref span { position:absolute; right:0; top:-17px; font:11px var(--f-data); color:var(--muted); background:var(--panel); padding:0 4px; }
.tempo .linha-ref.lim span { color:var(--bad); }
.xeixo { position:relative; height:18px; margin-left:44px; font:11px var(--f-data); color:var(--muted); }
.xeixo span { position:absolute; transform:translateX(-50%); }
.legenda-tempo { display:flex; flex-wrap:wrap; gap:4px 16px; margin-top:8px; font-size:12px; color:var(--muted); }
.legenda-tempo i { display:inline-block; width:12px; height:8px; border-radius:2px; margin-right:5px; vertical-align:middle; }

/* Trilho */
.trilho { display:grid; grid-template-columns:minmax(0, 1.55fr) minmax(0, 1fr); gap:16px; align-items:start; }
@media (max-width:900px) { .trilho { grid-template-columns:minmax(0, 1fr); } }
.escala { display:flex; align-items:center; gap:8px; font:12px var(--f-data); color:var(--muted); }
.escala .g { flex:0 0 140px; height:8px; border-radius:4px; background:linear-gradient(90deg,#2e9d5b,#e3b341,#d1452f); }
.faixa { display:flex; height:30px; border-radius:6px; overflow:hidden; margin:10px 0 4px; gap:1px; background:var(--line); }
.faixa div { flex:1; cursor:pointer; transition:transform .12s; }
.faixa div:hover, .faixa div.on { transform:scaleY(1.25); }
.faixa-rot { display:flex; justify-content:space-between; font:11px var(--f-data); color:var(--muted); }
.mapa { width:100%; height:auto; display:block; background:var(--sunk); border-radius:8px; margin-top:12px; }
.mapa g.s { transition:opacity .15s; }
.mapa.foco g.s:not(.on) { opacity:.12; }
.mapa .rotulo { font-family:var(--f-data); font-weight:600; }
.dica { position:fixed; pointer-events:none; z-index:20; background:var(--fg); color:var(--bg); border-radius:6px;
  padding:6px 9px; font:12px/1.4 var(--f-data); max-width:280px; }
.lista-quentes { display:grid; gap:8px; }
.quente { display:grid; grid-template-columns:auto 1fr auto; gap:2px 12px; align-items:baseline; padding:10px 12px;
  border:1px solid var(--line); border-radius:8px; cursor:pointer; background:var(--panel); }
.quente:hover, .quente.on, .quente:focus-visible { border-color:var(--accent); outline:none; }
.quente .num { font:600 22px/1 var(--f-display); }
.quente .ms { font:600 18px/1 var(--f-display); font-variant-numeric:tabular-nums; }
.quente .cats { grid-column:1 / -1; font-size:12px; color:var(--muted); }
.barra-cat { grid-column:1 / -1; display:flex; height:6px; border-radius:3px; overflow:hidden; background:var(--sunk); }
.legenda-cat { display:flex; flex-wrap:wrap; gap:4px 12px; font-size:12px; color:var(--muted); margin-top:4px; }
.legenda-cat i { display:inline-block; width:9px; height:9px; border-radius:2px; margin-right:4px; vertical-align:-1px; }

/* Tabelas */
.ferramentas { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:8px 0; }
.ferramentas input { font:13px var(--f-body); padding:5px 9px; border:1px solid var(--line); border-radius:6px;
  background:var(--panel); color:var(--fg); min-width:0; width:240px; max-width:100%; }
.ferramentas input:focus-visible { outline:2px solid var(--accent); outline-offset:0; }
.ferramentas .cont { font:12px var(--f-data); color:var(--muted); }
.rolagem { overflow:auto; max-height:520px; border:1px solid var(--line); border-radius:8px; background:var(--panel); }
table { border-collapse:collapse; width:100%; font-size:13px; }
th, td { padding:6px 10px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; }
th { position:sticky; top:0; background:var(--sunk); font:500 11px/1.3 var(--f-data); text-transform:uppercase;
  letter-spacing:.06em; color:var(--muted); cursor:pointer; user-select:none; white-space:nowrap; z-index:1; }
th:hover { color:var(--fg); } th[aria-sort="ascending"]::after { content:" \\25B2"; } th[aria-sort="descending"]::after { content:" \\25BC"; }
td.n { text-align:right; font-family:var(--f-data); font-variant-numeric:tabular-nums; white-space:nowrap; }
tr:last-child td { border-bottom:0; }
tbody tr:hover td { background:var(--sunk); }
.vazio { padding:14px; color:var(--muted); border:1px dashed var(--line); border-radius:8px; }
.grade2 { display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap:16px; }
.grade2 > div { min-width:0; }
.cat { display:inline-flex; align-items:center; gap:4px; margin-right:10px; white-space:nowrap; }
.cat i { width:9px; height:9px; border-radius:2px; display:inline-block; }
.calor { display:inline-block; width:10px; height:10px; border-radius:2px; vertical-align:-1px; margin-right:6px; }
@media (prefers-reduced-motion: reduce) { * { transition:none !important; } }
'''

# Cores fixas por categoria do profiler (a mesma em todo o relatorio).
CORES_CAT = {
    'MainRender': '#3f7fd9', 'Shadows': '#8a63d2', 'Physics': '#d9822b', 'Logic': '#2fa39a', 'Animations': '#c94f8a',
    'Scenegraph': '#7a8b3a', 'Overlay': '#9b9b5a', 'Network': '#5a7d9b', 'Rasterizer': '#4c9be0', 'Services': '#8c7a6b',
    'Depsgraph': '#a0745a', 'Outside': '#6b7280', 'Components': '#d4a72c',
}


def cor_cat(nome):
    if nome in CORES_CAT:
        return CORES_CAT[nome]
    h = sum(ord(c) * (i + 1) for i, c in enumerate(nome)) % 360
    return 'hsl(%d,45%%,52%%)' % h


def cor_calor(v, lo, hi):
    """Verde -> amarelo -> vermelho."""
    t = 0.0 if hi <= lo else max(0.0, min(1.0, (v - lo) / (hi - lo)))
    paradas = ((46, 157, 91), (227, 179, 65), (209, 69, 47))
    a, b, u = (paradas[0], paradas[1], t * 2) if t < 0.5 else (paradas[1], paradas[2], t * 2 - 1)
    return '#%02x%02x%02x' % tuple(round(a[i] + (b[i] - a[i]) * u) for i in range(3))


def esc(v):
    return html.escape(str(v))


class Html(str):
    """Celula ja em HTML: a tabela nao escapa."""


def num(v):
    try:
        return float(str(v).replace(',', ''))
    except ValueError:
        return None


def tabela(cabecalho, linhas, numericas=(), filtro=False, id_=None, calor=(), piso=None):
    """Tabela ordenavel (clique no cabecalho); filtro de texto nas listas longas.
    calor: colunas pintadas de verde (baixo) a vermelho (alto) dentro da propria coluna;
    piso: {coluna: valor} abaixo do qual a celula fica verde."""
    if not linhas:
        return '<div class="vazio">Nenhum.</div>'
    h = []
    if filtro or len(linhas) > 12:
        h.append('<div class="ferramentas"><input type="search" placeholder="Filtrar..." aria-label="Filtrar tabela"%s>'
                 '<span class="cont">%d linhas</span></div>' % (' id="f-%s"' % id_ if id_ else '', len(linhas)))
    h.append('<div class="rolagem"><table><thead><tr>' +
             ''.join('<th%s>%s</th>' % (' data-n="1"' if i in numericas else '', esc(c)) for i, c in enumerate(cabecalho)) +
             '</tr></thead><tbody>')
    faixas = {}
    for c in calor:
        vals = [x for x in (num(l[c]) for l in linhas) if x is not None]
        if vals:
            faixas[c] = ((piso or {}).get(c, min(vals)), max(vals))

    def celula(i, v):
        cls = ' class="n"' if i in numericas else ''
        txt = v if isinstance(v, Html) else esc(v)
        x = num(v) if i in faixas else None
        if x is None:
            return '<td%s>%s</td>' % (cls, txt)
        lo, hi = faixas[i]
        t = 0.0 if hi <= lo else max(0.0, min(1.0, (x - lo) / (hi - lo)))
        cor = cor_calor(t ** 0.6, 0.0, 1.0)
        return ('<td%s style="background:color-mix(in srgb, %s %d%%, transparent)"><span class="calor" style="background:%s">'
                '</span>%s</td>' % (cls, cor, 10 + round(t * 26), cor, txt))

    for linha in linhas:
        h.append('<tr>' + ''.join(celula(i, v) for i, v in enumerate(linha)) + '</tr>')
    h.append('</tbody></table></div>')
    return ''.join(h)


def secao(id_, titulo, n=None, nota=None):
    s = '<section id="%s"><h2>%s%s</h2>' % (id_, esc(titulo), '' if n is None else ' <span class="n">%s</span>' % esc(n))
    if nota:
        s += '<p class="nota">%s</p>' % nota
    return s




def html_kpis(a, w):
    jogo = [custo(fr) for f, fr in a['frames'].items() if f > FRAMES_DE_LOAD]
    k = []
    if jogo:
        med = a['frame_mediana']
        fps = 1000.0 / med if med > 0 else 0
        k.append(('Frame mediano', '%.1f' % med, 'ms', '~%.0f fps sem VSync' % fps, 'ok' if med < 16.7 else 'warn'))
        p99 = percentil(jogo, 0.99)
        k.append(('Pior 1%', '%.1f' % p99, 'ms', 'p95 %.1f ms' % percentil(jogo, 0.95), 'ok' if p99 < 33.4 else 'warn'))
        n = len(a['picos'])
        k.append(('Frames lentos', '%d' % n, '', 'acima de %.0f ms' % a['pico_limite'], 'ok' if n == 0 else 'bad' if n > 20 else 'warn'))
    setores = [st for st in a['setores'] if st]
    if setores:
        nq = sum(1 for st in setores if st['quente'])
        k.append(('Trechos quentes', '%d' % nq, '/ %d' % len(setores), 'mediana %.1f ms' % a['setor_mediana'],
                  'ok' if nq == 0 else 'warn'))
    if a['tem_uso']:
        tri = sum(a['tris'](o) for o in a['nunca'])
        k.append(('Nunca desenhados', '%d' % len(a['nunca']), 'obj', '%s triangulos' % format(tri, ',').replace(',', '.'),
                  'ok' if not a['nunca'] else 'warn'))
        mb = sum(mb_imagem(a['imagens'][i]) for i in a['imgs_atoa'] if i in a['imagens'])
        k.append(('VRAM a toa', '%.1f' % mb, 'MB', '%d imagens' % len(a['imgs_atoa']), 'ok' if mb < 8 else 'warn'))
    sh = a['extras'].get('shaders')
    if sh:
        n = len(sh['no_jogo'])
        k.append(('GPU no jogo', '%d' % n, '', '%.0f ms em shaders e imagens' % sum(it['ms'] for it in sh['no_jogo']),
                  'ok' if n == 0 else 'warn' if n < 10 else 'bad'))
    ms_tarde = sum(t[3] for t in a['tardias'])
    k.append(('Cargas no jogo', '%d' % len(a['tardias']), '', '%.0f ms no total' % ms_tarde,
              'ok' if ms_tarde < 50 else 'warn' if ms_tarde < 300 else 'bad'))
    w('<div class="kpis">' + ''.join(
        '<div class="kpi %s"><span class="rot">%s</span><span class="val">%s<small>%s</small></span><span class="sub">%s</span></div>'
        % (cls, esc(r), esc(v), esc(u), esc(s)) for r, v, u, s, cls in k) + '</div>')


def html_tempo(a, w, eventos_rail):
    """Tempo de frame ao longo da sessao (maximo por coluna), com a mediana e o limite de frame lento."""
    frames = sorted(a['frames'].values(), key=lambda fr: fr['t'])
    if len(frames) < 2:
        return
    w(secao('tempo', 'Linha do tempo', '%d frames' % len(frames),
            'Custo de cada frame sem a espera ociosa, maior valor por coluna. Picos acima do topo ficam presos nele '
            'e aparecem como triangulos. Passe o mouse para ver o segundo e o frame.'))
    t0, t1 = frames[0]['t'], frames[-1]['t']
    dur = max(t1 - t0, 0.001)
    largura = 1000
    colunas = [None] * largura
    for fr in frames:
        i = min(largura - 1, int((fr['t'] - t0) / dur * largura))
        if colunas[i] is None or custo(fr) > custo(colunas[i]):
            colunas[i] = fr
    custos = [custo(fr) for fr in frames if fr['f'] > FRAMES_DE_LOAD] or [1.0]
    topo = max(a['pico_limite'] * 1.25, percentil(custos, 0.995) * 1.1, 5.0)
    alt = 200.0

    def y(v):
        return alt - min(v, topo) / topo * alt

    pts, presos, dados = [], [], []
    for i, fr in enumerate(colunas):
        if fr is None:
            continue
        c = custo(fr)
        pts.append('%d,%.1f' % (i, y(c)))
        dados.append('%d:[%.2f,%d,%.1f]' % (i, fr['t'], fr['f'], c))
        if c > topo:
            presos.append(i)
    w('<div class="painel">')
    w('<div class="tempo" id="tempo">')
    for v in (0, topo / 2, topo):
        w('<span class="ylab" style="top:%.1f%%">%.0f</span>' % (y(v) / alt * 100, v))
    w('<div class="linha-ref" style="top:%.1f%%"><span>mediana %.1f ms</span></div>' % (y(a['frame_mediana']) / alt * 100, a['frame_mediana']))
    w('<div class="linha-ref lim" style="top:%.1f%%"><span>lento &gt; %.0f ms</span></div>' % (y(a['pico_limite']) / alt * 100, a['pico_limite']))
    svg = ['<svg viewBox="0 0 %d %d" preserveAspectRatio="none" aria-label="Tempo de frame">' % (largura, alt)]
    # Faixas de fundo: espera do trilho e trilho andando.
    ini, go, fim = eventos_rail
    def faixa(ta, tb, cor, op):
        xa, xb = (ta - t0) / dur * largura, (tb - t0) / dur * largura
        svg.append('<rect x="%.1f" y="0" width="%.1f" height="%d" fill="%s" opacity="%s"/>' % (xa, max(xb - xa, 1), alt, cor, op))
    if ini:
        tgo = go['t'] if go else ini['t']
        if go:
            faixa(ini['t'], tgo, 'var(--muted)', '.10')
        faixa(tgo, fim['t'] if fim else t1, 'var(--accent)', '.08')
    svg.append('<polyline points="%s 1000,%d 0,%d" fill="var(--accent)" opacity=".14" stroke="none"/>' % (' '.join(pts), alt, alt))
    svg.append('<polyline points="%s" fill="none" stroke="var(--accent)" stroke-width="1.4" vector-effect="non-scaling-stroke"/>' % ' '.join(pts))
    for pk in a['picos']:
        x = (pk['t'] - t0) / dur * largura
        svg.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%d" stroke="var(--bad)" stroke-width="1" vector-effect="non-scaling-stroke" opacity=".55"/>'
                   % (x, x, y(pk['ms']), alt))
    for i in presos:
        svg.append('<path d="M%d,0 l-5,-9 h10 z" fill="var(--bad)"/>' % i)
    svg.append('<line id="cursor" x1="0" x2="0" y1="0" y2="%d" stroke="var(--fg)" stroke-width="1" vector-effect="non-scaling-stroke" visibility="hidden"/>' % alt)
    svg.append('</svg>')
    w(''.join(svg))
    w('</div>')
    marcas = 6
    w('<div class="xeixo">' + ''.join('<span style="left:%.1f%%">%.0f s</span>' % (i * 100 / marcas, t0 + dur * i / marcas)
                                      for i in range(marcas + 1)) + '</div>')
    leg = ['<span><i style="background:var(--accent)"></i>tempo de frame</span>',
           '<span><i style="background:var(--bad)"></i>frame lento</span>']
    if ini:
        if go:
            leg.append('<span><i style="background:var(--muted);opacity:.4"></i>trilho esperando a largada</span>')
        leg.append('<span><i style="background:var(--accent);opacity:.3"></i>trilho andando</span>')
    w('<div class="legenda-tempo">%s</div>' % ''.join(leg))
    w('<script>var TEMPO={%s};</script>' % ','.join(dados))
    w('</div></section>')


def barra_cats(cats, total):
    total = total or 1.0
    return '<div class="barra-cat">' + ''.join(
        '<span title="%s %.1f ms" style="width:%.1f%%;background:%s"></span>' % (esc(k), v, v / total * 100, cor_cat(k))
        for k, v in cats) + '</div>'


def html_trilho(a, w):
    if not a['trilho_inicio'] and not a['trilho_fim']:
        return
    ini, fim = a['trilho_inicio'], a['trilho_fim']
    nota = ''
    if ini:
        nota = ('Camera <b>%s</b> na curva <b>%s</b> (cena %s): %.0f m em %.0f s. Custo do frame sem a espera ociosa, '
                'VSync desligado. As cores sao relativas a esta volta.' % (
                    esc(ini['camera']), esc(ini['curve']), esc(ini['scene']), ini['length'], ini['seconds']))
    w(secao('trilho', 'Trilho de camera', None, nota))
    if fim and fim.get('reason') != 'finished':
        w('<p class="aviso">O trilho nao terminou (%s).</p>' % esc(fim.get('reason', '?')))
    setores = [st for st in a['setores'] if st]
    if not setores:
        w('<p class="aviso">Sem frames medidos no trilho: ligue o modulo frames junto com sector.</p></section>')
        return
    lo = min(st['media'] for st in setores)
    hi = max(st['media'] for st in setores)
    w('<div class="trilho"><div class="painel">')
    w('<div class="escala">%.1f ms <span class="g"></span> %.1f ms <span style="margin-left:auto">%d trechos</span></div>' % (lo, hi, SETORES))
    w('<div class="faixa" id="faixa">' + ''.join(
        '<div data-s="%d" style="background:%s"></div>' % (st['i'], cor_calor(st['media'], lo, hi))
        if st else '<div style="background:var(--sunk);cursor:default"></div>' for st in a['setores']) + '</div>')
    w('<div class="faixa-rot"><span>inicio</span><span>50%</span><span>fim</span></div>')

    # Mapa visto de cima: pontos de cada frame agrupados por trecho, para acender um trecho por vez.
    pts = a['pontos']
    xs = [pt['x'] for pt in pts]
    ys = [pt['y'] for pt in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    lado = max(maxx - minx, maxy - miny, 1.0)
    margem = lado * 0.06
    raio = lado / 220
    svg = ['<svg class="mapa" id="mapa" viewBox="%.1f %.1f %.1f %.1f" xmlns="http://www.w3.org/2000/svg">' % (
        minx - margem, -maxy - margem, (maxx - minx) + 2 * margem, (maxy - miny) + 2 * margem)]
    por_setor = defaultdict(list)
    for pt in pts:
        por_setor[min(int(pt['p'] * SETORES), SETORES - 1)].append(pt)
    for i in sorted(por_setor):
        svg.append('<g class="s" data-s="%d">' % i)
        for pt in por_setor[i]:
            svg.append('<circle cx="%.1f" cy="%.1f" r="%.2f" fill="%s"/>' % (pt['x'], -pt['y'], raio, cor_calor(pt['ms'], lo, hi)))
        svg.append('</g>')
    p0 = pts[0]
    svg.append('<circle cx="%.1f" cy="%.1f" r="%.2f" fill="none" stroke="currentColor" stroke-width="%.2f"/>' % (
        p0['x'], -p0['y'], raio * 4, raio * 0.8))
    svg.append('<text class="rotulo" x="%.1f" y="%.1f" font-size="%.1f" fill="currentColor">largada</text>' % (
        p0['x'] + raio * 6, -p0['y'] + raio * 1.5, raio * 4.5))
    for st in setores:
        if st['quente']:
            svg.append('<text class="rotulo" x="%.1f" y="%.1f" font-size="%.1f" fill="var(--bad)" stroke="var(--sunk)" '
                       'stroke-width="%.2f" paint-order="stroke">%d</text>' % (
                           st['x'] + raio * 4, -st['y'] - raio * 2, raio * 9, raio * 1.6, st['i'] + 1))
    svg.append('</svg>')
    w(''.join(svg))
    w('<p class="nota" style="margin-top:8px">Visto de cima (X, Y do mundo). Passe o mouse na faixa, no mapa ou na lista para acender o trecho.</p>')
    w('</div><div>')
    quentes = sorted((st for st in setores if st['quente']), key=lambda st: st['media'], reverse=True)
    w('<h3 style="margin-top:0">Trechos quentes <span class="chip %s">%d</span></h3>' % ('warn' if quentes else 'ok', len(quentes)))
    w('<p class="nota">Acima de %.0f%% da mediana (%.1f ms) e %.0f ms a mais. MainRender e Shadows apontam para o que '
      'esta a vista; Physics e Logic, para o que acontece ali.</p>' % (QUENTE * 100, a['setor_mediana'], QUENTE_MIN_MS))
    lista = quentes
    if not quentes:
        w('<div class="vazio">Nenhum: o custo e parecido na pista toda. Abaixo, os 5 trechos mais caros desta volta.</div>')
        lista = sorted(setores, key=lambda st: st['media'], reverse=True)[:5]
    if lista:
        w('<div class="lista-quentes" style="margin-top:8px">')
        usadas = set()
        for st in lista:
            total = sum(v for _, v in st['cats'])
            usadas.update(k for k, _ in st['cats'])
            w('<div class="quente" tabindex="0" data-s="%d"><span class="num">#%d</span>'
              '<span class="cats" style="grid-column:auto">%d-%d%% da curva &middot; p95 %.1f &middot; max %.1f</span>'
              '<span class="ms"><span class="calor" style="background:%s"></span>%.1f ms</span>%s'
              '<span class="cats">%s</span></div>' % (
                  st['i'], st['i'] + 1, st['i'] * 100 // SETORES, (st['i'] + 1) * 100 // SETORES, st['p95'], st['max'],
                  cor_calor(st['media'], lo, hi), st['media'], barra_cats(st['cats'], total), esc(texto_cats(st['cats']))))
        w('</div>')
        w('<div class="legenda-cat">%s</div>' % ''.join('<span><i style="background:%s"></i>%s</span>' % (cor_cat(k), esc(k))
                                                        for k in sorted(usadas)))
    w('</div></div>')
    w('<h3>Todos os trechos</h3>')
    linhas = [(st['i'] + 1, '%d-%d%%' % (st['i'] * 100 // SETORES, (st['i'] + 1) * 100 // SETORES),
               '%.2f' % st['media'], '%.1f' % st['p95'], '%.1f' % st['max'], chips_cats(st['cats']),
               '%.0f, %.0f' % (st['x'], st['y']), 'quente' if st['quente'] else '')
              for st in setores]
    w(tabela(('trecho', '% da curva', 'media ms', 'p95 ms', 'max ms', 'categorias (media ms)', 'centro x,y', ''),
             linhas, (0, 2, 3, 4), calor=(2, 3, 4)))
    # Dados para a dica do mapa/faixa.
    w('<script>var SETORES={%s};</script>' % ','.join(
        '%d:["%d-%d%%",%.2f,%.1f,%s]' % (st['i'], st['i'] * 100 // SETORES, (st['i'] + 1) * 100 // SETORES, st['media'],
                                        st['max'], json.dumps(texto_cats(st['cats']))) for st in setores))
    w('</section>')


def html_picos(a, w):
    if not a['frames']:
        return
    w(secao('lentos', 'Frames lentos', len(a['picos']),
            'Mediana %.1f ms; lento = acima de %.1f ms, sem a espera ociosa. "Carregou junto" = cargas registradas no '
            'mesmo frame ou no anterior: a causa mais provavel da travada.' % (a['frame_mediana'], a['pico_limite'])))
    linhas = [(pk['f'], '%.1f' % pk['t'], '%.1f' % pk['ms'], chips_cats(pk['cats']), '; '.join(pk['cargas']) or '-')
              for pk in a['picos']]
    w(tabela(('frame', 'segundo', 'ms', 'categorias (ms)', 'carregou junto'), linhas, (0, 1, 2),
             calor=(2,), piso={2: a['pico_limite']}))
    w('</section>')


def html_work(a, w):
    x = a['extras']
    if 'work' not in x and 'objetos' not in x:
        return
    w(secao('trabalho', 'Trabalho por frame', '%d frames' % x['work']['n'] if 'work' in x else None,
            'Contadores do motor em cada frame de jogo. Numa cena parada devem ficar perto de zero: um contador que '
            'fica no numero de objetos indica trabalho refeito todo frame sobre dados que nao mudaram.'))
    if 'work' in x:
        nomes = {'draws': 'draw calls', 'matBinds': 'trocas de material', 'lightBinds': 'binds de luz',
                 'nodes': 'nos de cena atualizados', 'syncs': 'syncs de transform', 'bounds': 'bounds enviados',
                 'matrices': 'matrizes de malha mudadas', 'notifies': 'notificacoes de update',
                 'lightUniforms': 'uniforms de luz', 'passUniforms': 'uniforms de material',
                 'instancing': 'envios de instancing'}
        linhas = [(nomes.get(k, k), k, '%.0f' % med, '%.0f' % p95, '%d' % mx, '%.1f' % media)
                  for k, med, p95, mx, media in x['work']['linhas']]
        w(tabela(('contador', 'chave', 'mediana', 'p95', 'max', 'media'), linhas, (2, 3, 4, 5), calor=(3, 4)))
    if x.get('objetos'):
        w('<h3>Objetos que mais geram trabalho <span class="chip">%d</span></h3>' % len(x['objetos']))
        w('<p class="nota">Media por frame de cada objeto: raiz = arvore de transform atualizada; sync = transform '
          'copiada para a fisica ou o render. Objeto parado com valor alto e suspeito.</p>')
        w(tabela(('tipo', 'objeto', 'por frame'), [(t, n, '%.1f' % v) for t, n, v in x['objetos']], (2,), filtro=True, calor=(2,)))
    w('</section>')


def html_shaders(a, w):
    x = a['extras'].get('shaders')
    if not x:
        return
    no_jogo = x['no_jogo']
    w(secao('shaders', 'Shaders e texturas', '%d entradas' % len(x['itens']),
            'Log da GPU (RANGE_SHADER_LOG). create = compilado agora; cached = veio do cache; prefetch = aquecido no '
            'load; image = imagem enviada. Compilar shader no meio do jogo e a travada mais comum.'))
    resumo = ''.join('<div class="kpi"><span class="rot">%s</span><span class="val">%d</span>'
                     '<span class="sub">%.0f ms no total</span></div>' % (esc(t), n, ms)
                     for t, (n, ms) in sorted(x['por_tipo'].items(), key=lambda kv: -kv[1][1]))
    resumo += ('<div class="kpi"><span class="rot">texturas criadas</span><span class="val">%d</span>'
               '<span class="sub">na GPU</span></div>' % x['texturas'])
    w('<div class="kpis" style="margin-top:8px">%s</div>' % resumo)
    w('<h3>Depois do frame %d e acima de 1 ms <span class="chip %s">%d</span></h3>' % (
        FRAMES_DE_LOAD, 'warn' if no_jogo else 'ok', len(no_jogo)))
    w(tabela(('tipo', 'nome', 'ms', 'frame', 'segundo'),
             [(it['tipo'], it['nome'], '%.1f' % it['ms'], it['f'], '%.1f' % it['t']) for it in no_jogo], (2, 3, 4), calor=(2,), piso={2: 1.0}))
    w('<h3>Os mais lentos da sessao</h3>')
    top = sorted(x['itens'], key=lambda it: it['ms'], reverse=True)[:40]
    w(tabela(('tipo', 'nome', 'ms', 'frame', 'segundo'),
             [(it['tipo'], it['nome'], '%.1f' % it['ms'], it['f'], '%.1f' % it['t']) for it in top], (2, 3, 4), calor=(2,)))
    w('<p class="nota">O frame deste log e o do profiler da GPU; pode diferir alguns frames do trace.</p>')
    w('</section>')


def html_arquivos(a, w):
    arqs = a['extras'].get('arquivos')
    if not arqs:
        return
    w(secao('arquivos', 'Arquivos da sessao', len(arqs), 'Logs completos gravados nesta pasta.'))
    w('<div class="painel" style="display:flex;flex-wrap:wrap;gap:8px">%s</div>' % ''.join(
        '<a class="chip" style="text-transform:none" href="%s">%s</a>' % (esc(n), esc(n)) for n in arqs))
    w('</section>')


JS = r'''
(function(){
  var raiz=document.documentElement, KEY='range-trace-tema';
  try{var t=localStorage.getItem(KEY); if(t) raiz.setAttribute('data-theme',t);}catch(e){}
  var bt=document.getElementById('tema');
  if(bt) bt.addEventListener('click',function(){
    var escuro=raiz.getAttribute('data-theme')?raiz.getAttribute('data-theme')==='dark':matchMedia('(prefers-color-scheme: dark)').matches;
    var novo=escuro?'light':'dark'; raiz.setAttribute('data-theme',novo);
    try{localStorage.setItem(KEY,novo);}catch(e){}
  });
  var dica=document.createElement('div'); dica.className='dica'; dica.hidden=true; document.body.appendChild(dica);
  function mostra(ev,txt){dica.innerHTML=txt; dica.hidden=false;
    var x=ev.clientX+14, y=ev.clientY+14; if(x+290>innerWidth) x=ev.clientX-290;
    dica.style.left=x+'px'; dica.style.top=y+'px';}
  function esconde(){dica.hidden=true;}

  // Ordenar e filtrar tabelas.
  document.querySelectorAll('.rolagem table').forEach(function(tb){
    var ths=tb.querySelectorAll('th');
    ths.forEach(function(th,ci){th.addEventListener('click',function(){
      var asc=th.getAttribute('aria-sort')!=='ascending', num=th.dataset.n;
      ths.forEach(function(o){o.removeAttribute('aria-sort');});
      th.setAttribute('aria-sort',asc?'ascending':'descending');
      var corpo=tb.tBodies[0], ls=Array.prototype.slice.call(corpo.rows);
      ls.sort(function(a,b){var x=a.cells[ci].textContent,y=b.cells[ci].textContent;
        var r=num?(parseFloat(x)||0)-(parseFloat(y)||0):x.localeCompare(y,'pt-BR',{numeric:true});
        return asc?r:-r;});
      ls.forEach(function(l){corpo.appendChild(l);});
    });});
  });
  document.querySelectorAll('.ferramentas input').forEach(function(inp){
    var tb=inp.parentNode.nextElementSibling.querySelector('tbody'), cont=inp.nextElementSibling;
    inp.addEventListener('input',function(){
      var q=inp.value.toLowerCase(), n=0;
      Array.prototype.forEach.call(tb.rows,function(r){var ok=r.textContent.toLowerCase().indexOf(q)>=0; r.hidden=!ok; if(ok)n++;});
      cont.textContent=n+' linhas';
    });
  });

  // Trilho: acender um trecho na faixa, no mapa e na lista.
  var mapa=document.getElementById('mapa');
  if(mapa && window.SETORES){
    function acende(s){
      mapa.classList.toggle('foco',s!==null);
      document.querySelectorAll('[data-s]').forEach(function(el){el.classList.toggle('on',s!==null&&el.dataset.s===String(s));});
    }
    function texto(s){var d=SETORES[s]; if(!d) return '';
      return '<b>trecho '+(+s+1)+'</b> ('+d[0]+')<br>media '+d[1].toFixed(2)+' ms, max '+d[2].toFixed(1)+' ms<br>'+d[3];}
    document.querySelectorAll('#faixa div[data-s], .quente[data-s]').forEach(function(el){
      el.addEventListener('mouseenter',function(ev){acende(el.dataset.s); if(el.parentNode.id==='faixa') mostra(ev,texto(el.dataset.s));});
      el.addEventListener('mousemove',function(ev){if(el.parentNode.id==='faixa') mostra(ev,texto(el.dataset.s));});
      el.addEventListener('mouseleave',function(){acende(null); esconde();});
      el.addEventListener('focus',function(){acende(el.dataset.s);});
      el.addEventListener('blur',function(){acende(null);});
    });
    mapa.querySelectorAll('g.s').forEach(function(g){
      g.addEventListener('mouseenter',function(){acende(g.dataset.s);});
      g.addEventListener('mousemove',function(ev){mostra(ev,texto(g.dataset.s));});
      g.addEventListener('mouseleave',function(){acende(null); esconde();});
    });
  }

  // Linha do tempo: cursor com segundo, frame e ms.
  var tempo=document.getElementById('tempo');
  if(tempo && window.TEMPO){
    var cur=document.getElementById('cursor'), chaves=Object.keys(TEMPO).map(Number).sort(function(a,b){return a-b;});
    tempo.addEventListener('mousemove',function(ev){
      var r=tempo.getBoundingClientRect(), x=(ev.clientX-r.left)/r.width*1000, melhor=chaves[0];
      for(var i=0;i<chaves.length;i++){if(Math.abs(chaves[i]-x)<Math.abs(melhor-x)) melhor=chaves[i];}
      var d=TEMPO[melhor]; cur.setAttribute('x1',melhor); cur.setAttribute('x2',melhor); cur.setAttribute('visibility','visible');
      mostra(ev,d[0].toFixed(1)+' s &middot; frame '+d[1]+'<br><b>'+d[2].toFixed(1)+' ms</b>');
    });
    tempo.addEventListener('mouseleave',function(){cur.setAttribute('visibility','hidden'); esconde();});
  }
})();
'''


def relatorio_html(a, meta=None, pasta=''):
    meta = meta or {}
    p = []
    w = p.append
    jogo = os.path.splitext(os.path.basename(meta.get('jogo', '')))[0]
    nome_pasta = os.path.basename(os.path.normpath(pasta)) if pasta else ''
    quando = ''
    if nome_pasta.startswith('trace-') and len(nome_pasta) >= 21:
        d = nome_pasta[6:]
        quando = '%s/%s/%s %s:%s' % (d[6:8], d[4:6], d[0:4], d[9:11], d[11:13])
    w('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
      '<title>Range Trace%s</title>' % (' - ' + esc(jogo) if jogo else ''))
    w('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
      '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600&'
      'family=IBM+Plex+Sans:wght@400;500&family=JetBrains+Mono:wght@400;500;600&display=swap">')
    w('<style>%s</style></head><body>' % CSS)

    ini, go, fim = (next((e for e in a['_eventos_rail'] if e['ev'] == k), None) for k in ('rail_start', 'rail_go', 'rail_end'))
    secoes = []
    if a['frames']:
        secoes.append(('tempo', 'Linha do tempo'))
    if ini or fim:
        secoes.append(('trilho', 'Trilho'))
    if a['frames']:
        secoes.append(('lentos', 'Frames lentos'))
    if 'work' in a['extras'] or 'objetos' in a['extras']:
        secoes.append(('trabalho', 'Trabalho'))
    if 'shaders' in a['extras']:
        secoes.append(('shaders', 'Shaders'))
    secoes.append(('cenas', 'Cenas'))
    if a['tem_uso']:
        secoes.append(('desperdicio', 'Desperdicio'))
    secoes += [('cargas', 'Cargas no jogo'), ('imagens', 'Imagens'), ('fora', 'Deixados de fora')]
    if a['extras'].get('arquivos'):
        secoes.append(('arquivos', 'Arquivos'))

    w('<header class="topo"><div class="wrap">')
    w('<div class="titulo"><h1>Range Trace</h1>%s<span class="fim">%s<button class="tema" id="tema" type="button">Tema</button></span></div>' % (
        '<span class="jogo">%s</span>' % esc(jogo) if jogo else '',
        '<span class="chip ok">sessao completa</span>' if a['fim'] else '<span class="chip bad">sem evento end</span>'))
    info = []
    if quando:
        info.append('<span>Gravado em <b>%s</b></span>' % esc(quando))
    info.append('<span>Duracao <b>%.0f s</b></span>' % a['duracao'])
    info.append('<span>Modulos %s</span>' % ' '.join('<span class="chip">%s</span>' % esc(m) for m in a['modulos']))
    if meta.get('exe'):
        info.append('<span>%s</span>' % esc(os.path.basename(meta['exe'])))
    w('<div class="meta">%s</div>' % ''.join(info))
    w('<nav class="secoes" aria-label="Secoes">%s</nav>' % ''.join('<a href="#%s">%s</a>' % (i, esc(t)) for i, t in secoes))
    w('</div></header><main class="wrap">')
    if not a['fim']:
        w('<p class="aviso" style="margin-top:16px">Sem evento "end": o jogo foi fechado a forca ou travou. Os dados vao ate o ultimo evento gravado.</p>')
    if not a['tem_uso']:
        w('<p class="aviso">Sem eventos de uso: modulo usage desligado ou nada foi desenhado (ex.: --server).</p>')
    html_kpis(a, w)

    html_tempo(a, w, (ini, go, fim))
    html_trilho(a, w)
    html_picos(a, w)
    html_work(a, w)
    html_shaders(a, w)

    w(secao('cenas', 'Cenas carregadas', len(a['cenas'])))
    linhas = []
    for c in a['cenas']:
        sh = a['shaders'].get(c['scene'], {})
        linhas.append((nome_cena(c['scene']) + (' (LibLoad)' if c['libload'] else ''), c['f'], '%.1f' % c['t'],
                       '%.0f' % c['ms'], '%.0f' % sh.get('textures_ms', 0), '%.0f' % sh.get('shaders_ms', 0),
                       c['objects'], c['meshes'], c['materials']))
    w(tabela(('cena', 'frame', 'segundo', 'conversao ms', 'texturas ms', 'shaders ms', 'objetos', 'malhas',
              'materiais'), linhas, range(1, 9), calor=(3, 4, 5)))
    w('</section>')

    if a['tem_uso']:
        w(secao('desperdicio', 'Carregado e nunca desenhado', len(a['nunca']),
                'Nem pela camera, nem em sombra, no trecho que voce jogou. Camada inativa = modelo de Add Object nunca '
                'adicionado. Candidatos a Load Mode On Demand ou a sair do jogo.'))
        linhas = [(o['name'], nome_cena(o['scene']), obs_objeto(o), a['tris'](o), ', '.join(o['meshes'])) for o in a['nunca']]
        w(tabela(('objeto', 'cena', 'camada', 'triangulos', 'malhas'), linhas, (3,), filtro=True, calor=(3,)))
        w('<div class="grade2"><div>')
        w('<h3>Malhas so desses objetos <span class="chip">%d</span></h3>' % len(a['malhas_atoa']))
        linhas = [(m, a['malhas'][m]['tris'], ', '.join(a['malhas'][m]['materials'])) for m in a['malhas_atoa']]
        w(tabela(('malha', 'triangulos', 'materiais'), linhas, (1,), calor=(1,)))
        w('</div><div>')
        w('<h3>Imagens a toa <span class="chip">%d</span></h3>' % len(a['imgs_atoa']))
        linhas = []
        for i in a['imgs_atoa']:
            e = a['imagens'].get(i)
            linhas.append((i, '%dx%d' % (e['w'], e['h']) if e else '-', '%.2f' % mb_imagem(e) if e else 'nao enviada',
                           e['f'] if e else '-'))
        w(tabela(('imagem', 'tamanho', 'MB', 'frame do envio'), linhas, (2, 3), calor=(2,)))
        w('</div><div>')
        w('<h3>Materiais a toa <span class="chip">%d</span></h3>' % len(a['mats_atoa']))
        w(tabela(('material',), [(m,) for m in a['mats_atoa']]))
        w('</div><div>')
        w('<h3>Desenhados so em sombra <span class="chip">%d</span></h3>' % len(a['so_sombra']))
        linhas = [(o['name'], nome_cena(o['scene']), a['tris'](o)) for o in a['so_sombra']]
        w(tabela(('objeto', 'cena', 'triangulos'), linhas, (2,), calor=(2,)))
        w('</div></div>')
        w('<h3>Invisiveis por design <span class="chip">%d</span></h3>' % len(a['invisiveis']))
        w('<p class="nota">Navmesh e objetos com Visible desligado (colisores, gatilhos). Carregam, mas nao deveriam ser '
          'desenhados; nao entram no desperdicio.</p>')
        linhas = [(o['name'], nome_cena(o['scene']), 'navmesh' if o.get('navmesh') else 'invisivel', a['tris'](o))
                  for o in a['invisiveis']]
        w(tabela(('objeto', 'cena', 'motivo', 'triangulos'), linhas, (3,)))
        w('</section>')

    w(secao('cargas', 'Cargas durante o jogo', len(a['tardias']),
            'Trabalho feito depois do frame %d. Se o ms for alto, e candidata a travada: pre-carregar ou mover para o '
            'load.' % FRAMES_DE_LOAD))
    linhas = [(tipo, nome, nome_cena(cena), '%.1f' % ms, f, '%.1f' % t) for tipo, nome, cena, ms, f, t in a['tardias']]
    w(tabela(('tipo', 'nome', 'cena', 'ms', 'frame', 'segundo'), linhas, (3, 4, 5), calor=(3,), piso={3: 0.0}))
    w('</section>')

    w(secao('imagens', 'Imagens enviadas para a GPU', len(a['imagens'])))
    linhas = sorted(((i, '%dx%d' % (e['w'], e['h']), '%.2f' % mb_imagem(e), '%.1f' % e['ms'], e['f'])
                     for i, e in a['imagens'].items()), key=lambda x: float(x[2]), reverse=True)
    w(tabela(('imagem', 'tamanho', 'MB', 'ms', 'frame'), linhas, (2, 3, 4), calor=(2, 3)))
    w('</section>')

    w(secao('fora', 'Deixados de fora no load', len(a['deixados'])))
    linhas = [(e['name'], nome_cena(e['scene']), 'Editor Only' if e['reason'] == 'editor_only' else 'Load Mode')
              for e in a['deixados']]
    w(tabela(('objeto', 'cena', 'motivo'), linhas))
    w('</section>')
    html_arquivos(a, w)
    w('</main><script>%s</script></body></html>' % JS)
    return '\n'.join(p)


def ler_meta(pasta):
    # launcher.json: o que o launcher usou (jogo, exe, trilho); opcional.
    try:
        with open(os.path.join(pasta, 'launcher.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def main():
    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not args:
        raise SystemExit('uso: python tools/debug/relatorio_trace.py <pasta do trace> [--resumo]')
    pasta = args[0]
    caminho = os.path.join(pasta, 'trace.jsonl') if os.path.isdir(pasta) else pasta
    pasta = os.path.dirname(os.path.abspath(caminho))
    eventos = ler_eventos(caminho)
    a = analisar(eventos)
    a['extras'] = analisar_extras(pasta, eventos)
    md = resumo_md(a)
    with open(os.path.join(pasta, 'resumo.md'), 'w', encoding='utf-8') as f:
        f.write(md)
    with open(os.path.join(pasta, 'relatorio.html'), 'w', encoding='utf-8') as f:
        f.write(relatorio_html(a, ler_meta(pasta), pasta))
    if '--resumo' in sys.argv:
        print(md)
    print('relatorio: %s' % os.path.join(pasta, 'relatorio.html'))


if __name__ == '__main__':
    main()
