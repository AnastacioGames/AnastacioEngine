"""Resume a CPU de uma rodada do Range Trace com os modulos frames e threads.

    python tools/debug/medir_cpu.py <pasta-do-trace> [<pasta-base> para comparar]

Descarta os primeiros 3 s de jogo (carregamento e aquecimento). Mostra a media por frame de cada
categoria do profiler (sem Sleeping), o trabalho total e o uso de CPU por segundo: thread principal,
outras threads e nucleos ocupados.
"""
import json
import os
import sys

DESCARTE_S = 3.0


def ler(pasta):
    frames, threads = [], []
    with open(os.path.join(pasta, 'trace.jsonl'), encoding='utf-8') as f:
        for linha in f:
            ev = json.loads(linha)
            if ev.get('ev') == 'frame':
                frames.append(ev)
            elif ev.get('ev') == 'threads':
                threads.append(ev)
    if frames:
        inicio = frames[0]['t'] + DESCARTE_S
        frames = [ev for ev in frames if ev['t'] >= inicio]
        threads = [ev for ev in threads if ev['t'] >= inicio]

    cats = {}
    for ev in frames:
        for nome, ms in ev.get('c', {}).items():
            cats[nome] = cats.get(nome, 0.0) + ms
    n = max(1, len(frames))
    cats = {nome: ms / n for nome, ms in cats.items()}
    trabalho = sum(ms for nome, ms in cats.items() if nome != 'Sleeping')

    res = {'frames': len(frames), 'frame_ms': sum(ev['ms'] for ev in frames) / n, 'trabalho_ms': trabalho,
           'cats': cats}
    if threads:
        parede = sum(ev['wall_ms'] for ev in threads)
        res['principal_pct'] = 100.0 * sum(ev['main_ms'] for ev in threads) / parede
        res['outras_pct'] = 100.0 * sum(sum(ev['others']) for ev in threads) / parede
        res['nucleos'] = sum(ev['process_ms'] for ev in threads) / parede
        res['cores'] = threads[0]['cores']
        res['threads'] = threads[-1]['count']
    return res


def main():
    atual = ler(sys.argv[1])
    base = ler(sys.argv[2]) if len(sys.argv) > 2 else None

    def linha(rotulo, chave, fmt='%.2f'):
        txt = '%-28s %10s' % (rotulo, fmt % atual[chave] if chave in atual else '-')
        if base and chave in base:
            txt += ' %10s  (base %s)' % ('', fmt % base[chave])
        print(txt)

    print('frames medidos: %d' % atual['frames'])
    linha('frame (ms)', 'frame_ms')
    linha('trabalho sem Sleeping (ms)', 'trabalho_ms')
    linha('thread principal (% de 1 nucleo)', 'principal_pct', '%.1f')
    linha('outras threads (% de 1 nucleo)', 'outras_pct', '%.1f')
    linha('nucleos ocupados', 'nucleos')
    linha('threads no processo', 'threads', '%d')
    print('\ncategoria (ms por frame)')
    nomes = sorted(atual['cats'], key=lambda k: -atual['cats'][k])
    for nome in nomes:
        txt = '  %-30s %7.2f' % (nome, atual['cats'][nome])
        if base:
            antes = base['cats'].get(nome, 0.0)
            txt += '   base %7.2f   %+6.2f' % (antes, atual['cats'][nome] - antes)
        print(txt)


if __name__ == '__main__':
    main()
