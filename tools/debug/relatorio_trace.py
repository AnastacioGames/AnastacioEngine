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
                duracao=eventos[-1]['t'] if eventos else 0.0)


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


CSS = '''
:root { --bg:#fff; --fg:#1d1d1f; --muted:#6b6b70; --line:#e2e2e6; --head:#f4f4f6; --warn:#b54708; }
@media (prefers-color-scheme: dark) { :root { --bg:#17171a; --fg:#e8e8ea; --muted:#9a9aa2; --line:#2e2e34; --head:#222227; --warn:#f5a35c; } }
body { background:var(--bg); color:var(--fg); font:14px/1.45 system-ui, sans-serif; margin:0 auto; max-width:1100px; padding:16px; }
h1 { font-size:22px; } h2 { font-size:17px; margin-top:28px; border-bottom:1px solid var(--line); padding-bottom:4px; }
table { border-collapse:collapse; width:100%; margin:8px 0; font-variant-numeric:tabular-nums; }
th, td { border-bottom:1px solid var(--line); padding:4px 8px; text-align:left; }
th { background:var(--head); position:sticky; top:0; } td.n { text-align:right; }
.muted { color:var(--muted); } .warn { color:var(--warn); }
.faixa { display:flex; height:28px; border-radius:4px; overflow:hidden; margin:8px 0; }
.faixa div { flex:1; }
.mapa { width:100%; max-width:720px; background:var(--head); border-radius:6px; }
.legenda { display:flex; align-items:center; gap:8px; font-size:12px; }
.legenda span.g { width:160px; height:10px; border-radius:3px; background:linear-gradient(90deg,#2e9d5b,#e3b341,#d1452f); }
details summary { cursor:pointer; margin:6px 0; }
'''


def cor_calor(v, lo, hi):
    """Verde -> amarelo -> vermelho."""
    t = 0.0 if hi <= lo else max(0.0, min(1.0, (v - lo) / (hi - lo)))
    paradas = ((46, 157, 91), (227, 179, 65), (209, 69, 47))
    a, b, u = (paradas[0], paradas[1], t * 2) if t < 0.5 else (paradas[1], paradas[2], t * 2 - 1)
    return '#%02x%02x%02x' % tuple(round(a[i] + (b[i] - a[i]) * u) for i in range(3))


def html_trilho(a, w):
    if not a['trilho_inicio'] and not a['trilho_fim']:
        return
    w('<h2>Trilho de camera (sector)</h2>')
    ini, fim = a['trilho_inicio'], a['trilho_fim']
    if ini:
        w('<p class="muted">Cena %s, curva %s, camera %s, %.0f s, %.0f m. Custo do frame sem a espera ociosa; '
          'VSync desligado durante o trilho.</p>' % (html.escape(ini['scene']), html.escape(ini['curve']),
                                                    html.escape(ini['camera']), ini['seconds'], ini['length']))
    if fim and fim.get('reason') != 'finished':
        w('<p class="warn">O trilho nao terminou (%s).</p>' % html.escape(fim.get('reason', '?')))
    setores = [st for st in a['setores'] if st]
    if not setores:
        w('<p class="warn">Sem frames medidos no trilho: ligue o modulo frames junto com sector.</p>')
        return
    lo = min(st['media'] for st in setores)
    hi = max(st['media'] for st in setores)
    w('<div class="legenda">%.1f ms <span class="g"></span> %.1f ms</div>' % (lo, hi))
    # Faixa: a curva do inicio ao fim, um bloco por trecho.
    w('<div class="faixa">' + ''.join(
        '<div title="trecho %d: %.1f ms" style="background:%s"></div>' % (st['i'] + 1, st['media'], cor_calor(st['media'], lo, hi))
        if st else '<div style="background:var(--line)"></div>' for st in a['setores']) + '</div>')
    # Mapa visto de cima: cada frame medido, colorido pelo custo (escala dos trechos).
    pts = a['pontos']
    xs = [pt['x'] for pt in pts]
    ys = [pt['y'] for pt in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    lado = max(maxx - minx, maxy - miny, 1.0)
    margem = lado * 0.05
    svg = ['<svg class="mapa" viewBox="%.1f %.1f %.1f %.1f" xmlns="http://www.w3.org/2000/svg">' % (
        minx - margem, -maxy - margem, (maxx - minx) + 2 * margem, (maxy - miny) + 2 * margem)]
    raio = lado / 250
    for pt in pts:
        svg.append('<circle cx="%.1f" cy="%.1f" r="%.2f" fill="%s"/>' % (pt['x'], -pt['y'], raio,
                                                                       cor_calor(pt['ms'], lo, hi)))
    for st in setores:
        if st['quente']:
            svg.append('<text x="%.1f" y="%.1f" font-size="%.1f" fill="currentColor">%d</text>' % (
                st['x'] + raio * 3, -st['y'], raio * 8, st['i'] + 1))
    svg.append('</svg>')
    w(''.join(svg))
    w('<p class="muted">Visto de cima (X, Y do mundo). Numeros = trechos quentes: acima de %.0f%% da mediana (%.1f ms) e %.0f ms a mais.</p>' % (
        QUENTE * 100, a['setor_mediana'], QUENTE_MIN_MS))
    linhas = [(st['i'] + 1, '%d-%d%%' % (st['i'] * 100 // SETORES, (st['i'] + 1) * 100 // SETORES),
               '%.1f' % st['media'], '%.1f' % st['p95'], '%.1f' % st['max'], texto_cats(st['cats']),
               '%.0f, %.0f' % (st['x'], st['y']), 'quente' if st['quente'] else '')
              for st in setores]
    w(tabela(('trecho', '% da curva', 'media ms', 'p95 ms', 'max ms', 'categorias (media ms)', 'centro x,y', ''),
             linhas, (0, 2, 3, 4)))


def html_picos(a, w):
    if not a['frames']:
        return
    w('<h2>Frames lentos (%d)</h2>' % len(a['picos']))
    w('<p class="muted">Mediana %.1f ms; lento = acima de %.1f ms, sem a espera ociosa. "Carregou junto" = '
      'cargas registradas no mesmo frame ou no anterior.</p>' % (a['frame_mediana'], a['pico_limite']))
    linhas = [(pk['f'], '%.1f' % pk['t'], '%.1f' % pk['ms'], texto_cats(pk['cats']), '; '.join(pk['cargas']) or '-')
              for pk in a['picos']]
    w(bloco('ver lista', tabela(('frame', 'segundo', 'ms', 'categorias (ms)', 'carregou junto'), linhas, (0, 1, 2)),
            len(linhas)) if linhas else '<p>Nenhum.</p>')


def tabela(cabecalho, linhas, numericas=()):
    h = ['<table><tr>' + ''.join('<th>%s</th>' % html.escape(c) for c in cabecalho) + '</tr>']
    for linha in linhas:
        h.append('<tr>' + ''.join('<td%s>%s</td>' % (' class="n"' if i in numericas else '', html.escape(str(v)))
                                  for i, v in enumerate(linha)) + '</tr>')
    h.append('</table>')
    return '\n'.join(h)


def bloco(titulo, linhas_html, n):
    # Listas longas ficam recolhidas.
    if n > 40:
        return '<details><summary>%s (%d)</summary>%s</details>' % (html.escape(titulo), n, linhas_html)
    return linhas_html


def relatorio_html(a):
    p = []
    w = p.append
    w('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Range Trace</title>'
      '<style>%s</style></head><body>' % CSS)
    w('<h1>Range Trace</h1>')
    w('<p class="muted">Modulos: %s. Ultimo evento aos %.0f s. %s</p>' % (
        html.escape(', '.join(a['modulos'])), a['duracao'], '' if a['fim'] else
        '<span class="warn">Sem evento "end": o jogo foi fechado a forca ou travou.</span>'))
    if not a['tem_uso']:
        w('<p class="warn">Sem eventos de uso: modulo usage desligado ou nada foi desenhado (ex.: --server).</p>')

    html_trilho(a, w)
    html_picos(a, w)

    w('<h2>Cenas carregadas</h2>')
    linhas = []
    for c in a['cenas']:
        sh = a['shaders'].get(c['scene'], {})
        linhas.append((nome_cena(c['scene']) + (' (LibLoad)' if c['libload'] else ''), c['f'], '%.1f' % c['t'],
                       '%.0f' % c['ms'], '%.0f' % sh.get('textures_ms', 0), '%.0f' % sh.get('shaders_ms', 0),
                       c['objects'], c['meshes'], c['materials']))
    w(tabela(('cena', 'frame', 'segundo', 'conversao ms', 'texturas ms', 'shaders ms', 'objetos', 'malhas',
              'materiais'), linhas, range(1, 9)))

    if a['tem_uso']:
        w('<h2>Objetos carregados e nunca desenhados (%d)</h2>' % len(a['nunca']))
        w('<p class="muted">Nem pela camera, nem em sombra. Camada inativa = modelo de Add Object nunca '
          'adicionado. Candidatos a Load Mode On Demand ou a sair do jogo.</p>')
        linhas = [(o['name'], nome_cena(o['scene']), obs_objeto(o), a['tris'](o),
                   ', '.join(o['meshes'])) for o in a['nunca']]
        w(bloco('ver lista', tabela(('objeto', 'cena', 'camada', 'triangulos', 'malhas'), linhas, (3,)), len(linhas)))

        w('<h2>Invisiveis por design (%d)</h2>' % len(a['invisiveis']))
        w('<p class="muted">Navmesh e objetos com Visible desligado (colisores, gatilhos). Carregam, mas nao '
          'deveriam ser desenhados; nao entram nas listas de desperdicio.</p>')
        linhas = [(o['name'], nome_cena(o['scene']), 'navmesh' if o.get('navmesh') else 'invisivel', a['tris'](o))
                  for o in a['invisiveis']]
        w(bloco('ver lista', tabela(('objeto', 'cena', 'motivo', 'triangulos'), linhas, (3,)), len(linhas)))

        w('<h2>Desenhados so em sombra (%d)</h2>' % len(a['so_sombra']))
        linhas = [(o['name'], nome_cena(o['scene']), a['tris'](o)) for o in a['so_sombra']]
        w(bloco('ver lista', tabela(('objeto', 'cena', 'triangulos'), linhas, (2,)), len(linhas)))

        w('<h2>Malhas so de objetos nunca desenhados (%d)</h2>' % len(a['malhas_atoa']))
        linhas = [(m, a['malhas'][m]['tris'], ', '.join(a['malhas'][m]['materials'])) for m in a['malhas_atoa']]
        w(bloco('ver lista', tabela(('malha', 'triangulos', 'materiais'), linhas, (1,)), len(linhas)))

        w('<h2>Materiais e imagens a toa</h2>')
        w('<p class="muted">Usados so por essas malhas. Imagem "nao enviada" foi convertida com o material '
          'mas nunca subiu para a GPU.</p>')
        w(tabela(('material',), [(m,) for m in a['mats_atoa']]))
        linhas = []
        for i in a['imgs_atoa']:
            e = a['imagens'].get(i)
            linhas.append((i, '%dx%d' % (e['w'], e['h']) if e else '-', '%.2f' % mb_imagem(e) if e else 'nao enviada',
                           e['f'] if e else '-'))
        w(tabela(('imagem', 'tamanho', 'MB', 'frame do envio'), linhas, (2, 3)))

    w('<h2>Cargas durante o jogo (depois do frame %d)</h2>' % FRAMES_DE_LOAD)
    w('<p class="muted">Cada linha e trabalho feito no meio do jogo: se o ms for alto, e candidata a travada '
      '(pre-carregar ou mover para o load).</p>')
    linhas = [(tipo, nome, nome_cena(cena), '%.1f' % ms, f, '%.1f' % t) for tipo, nome, cena, ms, f, t in a['tardias']]
    w(tabela(('tipo', 'nome', 'cena', 'ms', 'frame', 'segundo'), linhas, (3, 4, 5)) if linhas else '<p>Nenhuma.</p>')

    w('<h2>Imagens enviadas para a GPU (%d)</h2>' % len(a['imagens']))
    linhas = sorted(((i, '%dx%d' % (e['w'], e['h']), '%.2f' % mb_imagem(e), '%.1f' % e['ms'], e['f'])
                     for i, e in a['imagens'].items()), key=lambda x: float(x[2]), reverse=True)
    w(bloco('ver lista', tabela(('imagem', 'tamanho', 'MB', 'ms', 'frame'), linhas, (2, 3, 4)), len(linhas)))

    w('<h2>Deixados de fora no load (%d)</h2>' % len(a['deixados']))
    linhas = [(e['name'], nome_cena(e['scene']), 'Editor Only' if e['reason'] == 'editor_only' else 'Load Mode')
              for e in a['deixados']]
    w(bloco('ver lista', tabela(('objeto', 'cena', 'motivo'), linhas), len(linhas)))
    w('</body></html>')
    return '\n'.join(p)


def main():
    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not args:
        raise SystemExit('uso: python tools/debug/relatorio_trace.py <pasta do trace> [--resumo]')
    pasta = args[0]
    caminho = os.path.join(pasta, 'trace.jsonl') if os.path.isdir(pasta) else pasta
    pasta = os.path.dirname(os.path.abspath(caminho))
    a = analisar(ler_eventos(caminho))
    md = resumo_md(a)
    with open(os.path.join(pasta, 'resumo.md'), 'w', encoding='utf-8') as f:
        f.write(md)
    with open(os.path.join(pasta, 'relatorio.html'), 'w', encoding='utf-8') as f:
        f.write(relatorio_html(a))
    if '--resumo' in sys.argv:
        print(md)
    print('relatorio: %s' % os.path.join(pasta, 'relatorio.html'))


if __name__ == '__main__':
    main()
