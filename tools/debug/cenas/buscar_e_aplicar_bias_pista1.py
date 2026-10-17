"""Busca o melhor bias/slopebias para a luz real da Pista_1 (RolimaRacer.range, lamp
'Sun.005' dentro do grupo group_Cameras) usando preparar_pista1_bias.py +
sombra_bias_probe_generico.py, e So DEPOIS aplica o escolhido no arquivo original.

A busca roda inteira em copias temporarias; o RolimaRacer.range original so e tocado na
etapa final, e so se houver um vencedor claro. O repo e git limpo, entao e reversivel
com 'git checkout -- RolimaRacer.range' caso o resultado nao agrade.

Uso:
  python tools/debug/cenas/buscar_e_aplicar_bias_pista1.py <RolimaRacer.range> <relatorio.txt> [pasta_temp]
"""
import json
import os
import subprocess
import sys
import time

CANDIDATOS = (
    ('muito_baixo', 0.02, 0.1),
    ('baixo', 0.05, 0.3),
    ('medio_baixo', 0.1, 0.8),
    ('padrao', 0.2, 1.0),
    ('medio_alto', 0.4, 2.0),
    ('alto', 1.0, 3.0),
    ('atual_quebrado', 1.0, 0.0),  # valor que ja estava antes do ajuste manual, para referencia
)
DARK_THRESHOLD = 0.4
RUN_TIMEOUT_S = 120
LAMP_DATA_NAME = 'Sun.005'


def main():
    if len(sys.argv) < 3:
        raise SystemExit('uso: buscar_e_aplicar_bias_pista1.py <RolimaRacer.range> <relatorio.txt> [pasta_temp]')
    scene_in = os.path.abspath(sys.argv[1])
    out_path = sys.argv[2]
    temp_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(out_path) or '.', 'pista1_bias_tmp')
    os.makedirs(temp_dir, exist_ok=True)

    root = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(root, '..', '..', '..'))
    engine = os.path.join(repo_root, 'build', 'bin', 'AnastacioEngine.exe')
    runtime = os.path.join(repo_root, 'build', 'bin', 'AnastacioRuntime.exe')
    preparer = os.path.join(root, 'preparar_pista1_bias.py')

    rows = []
    for name, bias, slopebias in CANDIDATOS:
        prepared_path = os.path.join(temp_dir, name + '.range')
        log_path = os.path.join(temp_dir, name + '.log')
        print('testando', name, 'bias=%s slopebias=%s' % (bias, slopebias), flush=True)
        if os.path.exists(log_path):
            os.remove(log_path)

        prep = subprocess.run(
            [engine, '-b', '--factory-startup', scene_in, '--python', preparer, '--',
             prepared_path, str(bias), str(slopebias)],
            capture_output=True, text=True, timeout=RUN_TIMEOUT_S)
        if prep.returncode != 0 or not os.path.isfile(prepared_path):
            rows.append(dict(name=name, bias=bias, slopebias=slopebias,
                              error='preparo falhou: ' + prep.stderr[-400:]))
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

    best = pick_best(rows)
    write_report(out_path, scene_in, rows, best)
    if best is not None:
        apply_to_original(scene_in, engine, best)
        print('APLICADO no arquivo original: bias=%s slopebias=%s' % (best['bias'], best['slopebias']))
    else:
        print('Nenhum candidato mediu com sucesso -- nada foi aplicado.')
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


def pick_best(rows):
    best = None
    for row in rows:
        if 'error' in row:
            continue
        total = row['falseLight'] + row['falseDark']
        if best is None or total < best['total']:
            best = dict(row)
            best['total'] = total
    return best


def write_report(out_path, scene_in, rows, best):
    lines = ['Busca de bias/slopebias para: ' + scene_in + ' (cena Pista_1, luz ' + LAMP_DATA_NAME + ')', '']
    header = '{:>16} {:>6} {:>10} {:>11} {:>10} {:>8} {:>14}'.format(
        'candidato', 'bias', 'slopebias', 'falsoClaro', 'falsoEscuro', 'amostras', 'receptor')
    lines.append(header)
    for row in rows:
        if 'error' in row:
            lines.append('{:>16} {:>6} {:>10}  ERRO: {}'.format(row['name'], row['bias'], row['slopebias'], row['error']))
        else:
            lines.append('{:>16} {:>6} {:>10} {:>11} {:>10} {:>8} {:>14}'.format(
                row['name'], row['bias'], row['slopebias'], row['falseLight'], row['falseDark'],
                row['samples'], str(row.get('receiver'))))
    lines.append('')
    if best is None:
        lines.append('Nenhum candidato mediu com sucesso -- nada foi aplicado no arquivo original.')
    else:
        lines.append('ESCOLHIDO e APLICADO: "%s" (bias=%s, slopebias=%s) -- %d erro(s) em %d amostras.' % (
            best['name'], best['bias'], best['slopebias'], best['total'], best['samples']))
        lines.append('Receptor identificado: %s (ocludores: %s)' % (best.get('receiver'), best.get('occluderCount')))
        lines.append('Repo e git limpo: "git checkout -- RolimaRacer.range" desfaz se nao agradar.')
    with open(out_path, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')


def apply_to_original(scene_in, engine, best):
    root = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(root, '_aplicar_bias_lamp.py')
    with open(script, 'w', encoding='utf-8') as handle:
        handle.write(
            "import bpy\n"
            "lamp = bpy.data.lamps['%s']\n"
            "lamp.shadow_buffer_bias = %s\n"
            "lamp.shadow_buffer_slope_bias = %s\n"
            "bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, check_existing=False)\n"
            "print('aplicado e salvo')\n" % (LAMP_DATA_NAME, best['bias'], best['slopebias']))
    subprocess.run([engine, '-b', '--factory-startup', scene_in, '--python', script],
                    capture_output=True, text=True, timeout=RUN_TIMEOUT_S, check=True)
    os.remove(script)


if __name__ == '__main__':
    start = time.time()
    main()
    print('tempo total: %.1fs' % (time.time() - start))
