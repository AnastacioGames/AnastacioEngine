"""Testa presets de bias/slopebias numa cena .range JA EXISTENTE (nao sintetica) e sugere
o melhor, sem jamais escrever na cena original. Usa preparar_cena_sombra_bias.py para
gerar copias temporarias e sombra_bias_probe_generico.py para medir cada uma contra o
gabarito geometrico (raio ate a luz Sun cruza algum ocludor da propria cena?).

Roda com o Python de sistema. Uso:
  python tools/debug/cenas/sugerir_bias_cena.py <cena.range> <saida.txt> [pasta_temp]

Limitacoes conhecidas (ver relatorio na saida): a cena precisa ter uma luz Sun com sombra
ligada, scene.camera definida, e o receptor (chao) identificado como o mesh de menor Z --
se a cena nao seguir essa convencao, o probe reporta erro em vez de medir errado.
"""
import json
import os
import subprocess
import sys
import time

BIAS_PRESETS = (
    ('muito_baixo', 0.02, 0.1),
    ('baixo', 0.05, 0.3),
    ('padrao', 0.2, 1.0),
    ('alto', 1.0, 3.0),
    ('muito_alto', 3.0, 5.0),
)
DARK_THRESHOLD = 0.4
RUN_TIMEOUT_S = 90


def main():
    if len(sys.argv) < 3:
        raise SystemExit('uso: sugerir_bias_cena.py <cena.range> <saida.txt> [pasta_temp]')
    scene_in = os.path.abspath(sys.argv[1])
    out_path = sys.argv[2]
    temp_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(out_path) or '.', 'sugestao_tmp')
    os.makedirs(temp_dir, exist_ok=True)
    if not os.path.isfile(scene_in):
        raise SystemExit('cena nao encontrada: ' + scene_in)

    root = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(root, '..', '..', '..'))
    engine = os.path.join(repo_root, 'build', 'bin', 'AnastacioEngine.exe')
    runtime = os.path.join(repo_root, 'build', 'bin', 'AnastacioRuntime.exe')
    preparer = os.path.join(root, 'preparar_cena_sombra_bias.py')

    rows = []
    for name, bias, slopebias in BIAS_PRESETS:
        tag = name
        prepared_path = os.path.join(temp_dir, tag + '.range')
        log_path = os.path.join(temp_dir, tag + '.log')
        print('testando preset', name, 'bias=%s slopebias=%s' % (bias, slopebias), flush=True)
        if os.path.exists(log_path):
            os.remove(log_path)

        prep = subprocess.run(
            [engine, '-b', '--factory-startup', scene_in, '--python', preparer, '--',
             prepared_path, str(bias), str(slopebias)],
            capture_output=True, text=True, timeout=RUN_TIMEOUT_S)
        if prep.returncode != 0 or not os.path.isfile(prepared_path):
            rows.append(dict(name=name, bias=bias, slopebias=slopebias,
                              error='preparo falhou: ' + prep.stderr[-400:] + prep.stdout[-200:]))
            continue

        env = dict(os.environ)
        env['SOMBRA_TEST_LOG'] = log_path
        try:
            subprocess.run([runtime, prepared_path], env=env, capture_output=True,
                            text=True, timeout=RUN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            rows.append(dict(name=name, bias=bias, slopebias=slopebias,
                              error='runtime nao terminou em %ds' % RUN_TIMEOUT_S))
            continue

        row = parse_log(log_path)
        if row is None:
            rows.append(dict(name=name, bias=bias, slopebias=slopebias, error='sem evento "samples" no log'))
            continue
        row.update(name=name, bias=bias, slopebias=slopebias)
        rows.append(row)

    write_report(out_path, scene_in, rows)
    print('Relatorio salvo em', out_path)


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
                false_light = sum(1 for s in data['rows'] if s['expectedDark'] and s['luminance'] >= DARK_THRESHOLD)
                false_dark = sum(1 for s in data['rows'] if not s['expectedDark'] and s['luminance'] < DARK_THRESHOLD)
                return dict(falseLight=false_light, falseDark=false_dark, samples=len(data['rows']),
                            receiver=data.get('receiver'), occluderCount=data.get('occluderCount'))
    return None


def write_report(out_path, scene_in, rows):
    lines = ['Sugestao de bias/slopebias para: ' + scene_in, '']
    header = '{:>12} {:>6} {:>10} {:>11} {:>10} {:>8}'.format(
        'preset', 'bias', 'slopebias', 'falsoClaro', 'falsoEscuro', 'amostras')
    lines.append(header)
    best = None
    for row in rows:
        if 'error' in row:
            lines.append('{:>12} {:>6} {:>10}  ERRO: {}'.format(row['name'], row['bias'], row['slopebias'], row['error']))
            continue
        total = row['falseLight'] + row['falseDark']
        lines.append('{:>12} {:>6} {:>10} {:>11} {:>10} {:>8}'.format(
            row['name'], row['bias'], row['slopebias'], row['falseLight'], row['falseDark'], row['samples']))
        if best is None or total < best[0]:
            best = (total, row)
    lines.append('')
    if best is None:
        lines.append('Nenhum preset mediu com sucesso -- ver erros acima. Nada a sugerir.')
    else:
        total, row = best
        lines.append('SUGESTAO: preset "%s" (bias=%s, slopebias=%s) -- %d erro(s) em %d amostras.' % (
            row['name'], row['bias'], row['slopebias'], total, row['samples']))
        lines.append('Isto e uma sugestao, nada foi escrito na cena original. Para aplicar, ajuste')
        lines.append('manualmente shadow_buffer_bias/shadow_buffer_slope_bias da luz Sun no editor.')
    with open(out_path, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    start = time.time()
    main()
    print('tempo total: %.1fs' % (time.time() - start))
