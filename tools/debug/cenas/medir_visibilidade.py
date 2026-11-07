"""V0 do plano de visibilidade: mede o predio de salas em 3 casos (Python do sistema).

  python tools/debug/cenas/medir_visibilidade.py
  opcional: RANGE_WEAK_GPU=8 simula GPU fraca

  all_batch tudo desenhado, Auto Static Batch ligado (padrao)
  all       tudo desenhado, sem batch
  occluder  paredes como Occluder + Occlusion Culling da cena
  occ_batch Occluder com Auto Static Batch
  oracle    salas invisiveis escondidas a mao: teto de ganho de um PVS

Cada caso abre o AnastacioRuntime por ~10 s e fecha sozinho. Saida em artifacts/visibilidade/.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EDITOR = os.path.join(ROOT, 'build', 'bin', 'AnastacioEngine.exe')
RUNTIME = os.path.join(ROOT, 'build', 'bin', 'AnastacioRuntime.exe')
GEN = os.path.join(ROOT, 'tools', 'debug', 'cenas', 'criar_cena_visibilidade.py')
OUT = os.path.join(ROOT, 'artifacts', 'visibilidade')
KEYS = ('work_ms', 'drawCalls', 'cullingVisible', 'p_CameraCulling', 'p_MainRender', 'p_GPU Latency', 'p_Overhead')


def scene(name, extra):
    path = os.path.join(OUT, name + '.range')
    if not os.path.exists(path):
        subprocess.run([EDITOR, '-b', '--factory-startup', '--python', GEN, '--', path] + extra,
                       check=True, capture_output=True, timeout=600)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    batch = scene('predio', [])
    plain = scene('predio_nobatch', ['nobatch'])
    occ = scene('predio_occluder', ['occluder', 'nobatch'])
    occ_batch = scene('predio_occluder_batch', ['occluder'])
    rows = []
    for case, path, mode in (('all_batch', batch, 'all'), ('all', plain, 'all'),
                             ('occluder', occ, 'all'), ('occ_batch', occ_batch, 'all'),
                             ('oracle', plain, 'oracle')):
        res = os.path.join(OUT, 'res_%s.txt' % case)
        if os.path.exists(res):
            os.remove(res)
        env = dict(os.environ, VIS_MODE=mode, VIS_RESULT=res, VIS_SHOT=os.path.join(OUT, 'shot_%s.png' % case))
        try:
            subprocess.run([RUNTIME, path], env=env, capture_output=True, timeout=120)
        except subprocess.TimeoutExpired:
            rows.append('%s: timeout' % case)
            continue
        if not os.path.exists(res):
            rows.append('%s: sem resultado' % case)
            continue
        line = open(res).read().strip()
        vals = dict(kv.split('=', 1) for kv in line.split() if '=' in kv)
        rows.append('%-10s ' % case + '  '.join('%s=%s' % (k, vals[k]) for k in KEYS if k in vals))
    text = 'RANGE_WEAK_GPU=%s\n' % os.environ.get('RANGE_WEAK_GPU', '') + '\n'.join(rows) + '\n'
    print(text)
    with open(os.path.join(OUT, 'resumo.txt'), 'w', encoding='utf-8') as f:
        f.write(text)


if __name__ == '__main__':
    main()
