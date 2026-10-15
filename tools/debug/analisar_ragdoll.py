"""Resume eventos de uma rodada instrumentada: python tools/debug/analisar_ragdoll.py pasta."""
import argparse
import collections
import json
from pathlib import Path
import re


def analyze(folder):
    rows = [json.loads(line) for line in (folder / 'ragdoll.jsonl').read_text(
        encoding='utf-8').splitlines() if line.strip()]
    spikes = []
    profile_path = folder / 'profile.txt'
    profile_lines = profile_path.read_text().splitlines() if profile_path.exists() else []
    for number, line in enumerate(profile_lines, 1):
        if line.startswith('SPIKE'):
            def value(key):
                match = re.search(r'(?<![\w.])' + re.escape(key) + r'=([\d.]+)', line)
                return float(match[1]) if match else 0.0
            spikes.append({'t': value('t'), 'frame': int(value('frame')),
                           'wall_ms': value('wall'), 'swap_ms': value('endframe.swap'),
                           'line': number})
    episodes = collections.defaultdict(list)
    for row in rows:
        if 'episode' in row:
            episodes[row['episode']].append(row)
    report = ['# Ragdoll — rodada instrumentada', '',
              'Tempos usam o relogio real da engine, igual a profile.txt. frame_t e tempo',
              'de simulacao, nao numero de quadro. Proximidade temporal nao prova causalidade.', '',
              '| Queda | Origem | Piloto | Ativacao (s) | Flags limpas (s) |',
              '|---|---|---|---:|---:|']
    for episode, events in sorted(episodes.items()):
        request = next((r for r in events if r['event'] == 'activation_requested'), None)
        if request is None:
            continue
        returned = next((r for r in events if r['event'] == 'recovery_flags_cleared'), None)
        reason = '+'.join(k for k, enabled in [('impacto', request.get('impact')),
                         ('input', request.get('input_pressed'))] if enabled)
        report.append('| %s | %s | %s | %.3f | %s |' % (
            episode, reason or '?', request.get('armature', request.get('object')),
            request['engine_t'], '%.3f' % returned['engine_t'] if returned else 'pendente'))
    report += ['', '## Picos proximos das quedas', '']
    if not profile_path.exists():
        report.append('profile.txt ausente: esta rodada nao permite cruzar picos de render.')
    for episode, events in sorted(episodes.items()):
        request = next((r for r in events if r['event'] == 'activation_requested'), None)
        if request is None:
            continue
        finish = next((r['engine_t'] for r in events if r['event'] == 'recovery_flags_cleared'),
                      request['engine_t'])
        nearby = [s for s in spikes if request['engine_t'] - 0.1 <= s['t'] <= finish + 2.0]
        report.append('- Queda %s: %s' % (episode, '; '.join(
            't=%.2f s, frame=%d, total=%.1f ms, swap=%.1f ms (profile.txt linha %d)' %
            (s['t'], s['frame'], s['wall_ms'], s['swap_ms'], s['line']) for s in nearby)
            or 'nenhum SPIKE nessa janela.'))
    report += ['', '## Erros e integridade', '']
    errors = [r for r in rows if r['event'] in ('exception', 'caught_error', 'observation_error')]
    report += ['- %s: %s' % (r['event'], r.get('error')) for r in errors] or ['- Sem erros registrados.']
    report.append('- Fechamento registrado: %s.' % any(r['event'] == 'trace_closed' for r in rows))
    report += ['', '## Modulos carregados', '']
    report += ['- `%s`: `%s` (SHA-256 `%s`).' % (r.get('module'), r.get('path'),
               r.get('sha256', r.get('hash_error'))) for r in rows if r['event'] == 'module_loaded']
    report += ['', 'Tempos detalhados ficam nos eventos phase, slow_call e function_summary do JSONL.',
               'Tempos de funcoes aninhadas se sobrepoem; nao somar como custo total do quadro.',
               'render_state amostra cameras/filtros custom a cada 100 ms; opcoes graphics e FXAA/grain',
               'tambem sao registrados. A API nao enumera o estado de todos os filtros built-in.', '']
    destination = folder / 'ragdoll-summary.md'
    destination.write_text('\n'.join(report), encoding='utf-8')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    print(analyze(parser.parse_args().folder))
