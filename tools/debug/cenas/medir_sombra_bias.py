"""Orquestra a matriz angulo x escala x bias para tools/debug/cenas/criar_cena_sombra_bias.py
e sombra_bias_probe.py, e monta uma tabela com o resultado de cada combinacao contra o
gabarito geometrico (raio luz->ponto cruza a AABB do cubo?).

Roda com o Python de sistema (nao o embarcado no motor); ele so chama os dois exe via
subprocess. Uso:
  python tools/debug/cenas/medir_sombra_bias.py <saida.txt> [pasta_temp]

Cada linha da tabela:
  angulo  escala  bias  slopebias  falsoClaro  falsoEscuro  amostras
"falsoClaro": pontos que deveriam estar na sombra (perto da base do cubo) mas vieram
claros -- sombra "descolada" (peter-panning). "falsoEscuro": pontos que deveriam estar
claros mas vieram escuros -- sombra vazando alem da borda esperada (acne/bleed).
"""
import json
import os
import subprocess
import sys
import time

ANGLES = (90.0, 45.0, 15.0)
SCALES = (0.3, 1.0, 3.0)
# (nome, bias, slopebias)
BIAS_PRESETS = (
    ('baixo', 0.05, 0.3),
    ('padrao', 0.2, 1.0),
    ('alto', 1.0, 3.0),
)
DARK_THRESHOLD = 0.4
RUN_TIMEOUT_S = 90


def main():
    if len(sys.argv) < 2:
        raise SystemExit('uso: medir_sombra_bias.py <saida.txt> [pasta_temp]')
    out_path = sys.argv[1]
    temp_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(out_path) or '.', 'sombra_bias_tmp')
    os.makedirs(temp_dir, exist_ok=True)

    root = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(root, '..', '..', '..'))
    engine = os.path.join(repo_root, 'build', 'bin', 'AnastacioEngine.exe')
    runtime = os.path.join(repo_root, 'build', 'bin', 'AnastacioRuntime.exe')
    generator = os.path.join(root, 'criar_cena_sombra_bias.py')
    if not (os.path.isfile(engine) and os.path.isfile(runtime)):
        raise SystemExit('build/bin/AnastacioEngine.exe ou AnastacioRuntime.exe nao encontrado -- compile antes.')

    rows = []
    total = len(ANGLES) * len(SCALES) * len(BIAS_PRESETS)
    done = 0
    for angle in ANGLES:
        for scale in SCALES:
            for preset_name, bias, slopebias in BIAS_PRESETS:
                done += 1
                tag = 'a%g_s%g_%s' % (angle, scale, preset_name)
                scene_path = os.path.join(temp_dir, tag + '.range')
                log_path = os.path.join(temp_dir, tag + '.log')
                print('[%d/%d] %s' % (done, total, tag), flush=True)

                if os.path.exists(log_path):
                    os.remove(log_path)

                gen = subprocess.run(
                    [engine, '-b', '--factory-startup', '--python', generator, '--',
                     scene_path, str(bias), str(slopebias), str(angle), str(scale)],
                    capture_output=True, text=True, timeout=RUN_TIMEOUT_S)
                if gen.returncode != 0 or not os.path.isfile(scene_path):
                    rows.append(dict(angle=angle, scale=scale, preset=preset_name, bias=bias,
                                      slopebias=slopebias, error='geracao falhou: ' + gen.stderr[-300:]))
                    continue

                env = dict(os.environ)
                env['SOMBRA_TEST_LOG'] = log_path
                try:
                    subprocess.run([runtime, scene_path], env=env, capture_output=True,
                                    text=True, timeout=RUN_TIMEOUT_S)
                except subprocess.TimeoutExpired:
                    rows.append(dict(angle=angle, scale=scale, preset=preset_name, bias=bias,
                                      slopebias=slopebias, error='runtime nao terminou em %ds' % RUN_TIMEOUT_S))
                    continue

                row = parse_log(log_path)
                if row is None:
                    rows.append(dict(angle=angle, scale=scale, preset=preset_name, bias=bias,
                                      slopebias=slopebias, error='sem evento "samples" no log'))
                    continue
                row.update(angle=angle, scale=scale, preset=preset_name, bias=bias, slopebias=slopebias)
                rows.append(row)

    write_table(out_path, rows)
    print('Tabela salva em', out_path)


def parse_log(log_path):
    if not os.path.isfile(log_path):
        return None
    with open(log_path, encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if data.get('event') == 'failure':
                return dict(error='falha no probe: ' + data.get('error', '?'))
            if data.get('event') == 'samples':
                false_light = 0  # deveria ser sombra, veio claro (peter-panning)
                false_dark = 0   # deveria ser claro, veio sombra (acne/bleed)
                for sample in data['rows']:
                    rendered_dark = sample['luminance'] < DARK_THRESHOLD
                    if sample['expectedDark'] and not rendered_dark:
                        false_light += 1
                    elif not sample['expectedDark'] and rendered_dark:
                        false_dark += 1
                return dict(falseLight=false_light, falseDark=false_dark, samples=len(data['rows']))
    return None


def write_table(out_path, rows):
    header = '{:>7} {:>7} {:>8} {:>6} {:>10} {:>11} {:>10} {:>8}'.format(
        'angulo', 'escala', 'preset', 'bias', 'slopebias', 'falsoClaro', 'falsoEscuro', 'amostras')
    lines = [header]
    for row in rows:
        if 'error' in row:
            lines.append('{:>7} {:>7} {:>8} {:>6} {:>10}  ERRO: {}'.format(
                row['angle'], row['scale'], row['preset'], row['bias'], row['slopebias'], row['error']))
        else:
            lines.append('{:>7} {:>7} {:>8} {:>6} {:>10} {:>11} {:>10} {:>8}'.format(
                row['angle'], row['scale'], row['preset'], row['bias'], row['slopebias'],
                row['falseLight'], row['falseDark'], row['samples']))
    with open(out_path, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
        handle.write('# fim\n')


if __name__ == '__main__':
    start = time.time()
    main()
    print('tempo total: %.1fs' % (time.time() - start))
