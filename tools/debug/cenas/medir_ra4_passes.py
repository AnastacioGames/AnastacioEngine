"""Mede uploads de instancing por quadro e tempo de sombras na cena parada RA4-passes.
Roda com o Python do sistema. Cada caso abre o AnastacioRuntime por ~10 s e fecha sozinho.

  python tools/debug/cenas/medir_ra4_passes.py <pasta_saida> [N]

Saida: resumo.txt (tabela) + o JSON e o range_profile de cada caso.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EDITOR = os.path.join(ROOT, 'build', 'bin', 'AnastacioEngine.exe')
RUNTIME = os.path.join(ROOT, 'build', 'bin', 'AnastacioRuntime.exe')
GEN = os.path.join(ROOT, 'tools', 'debug', 'cenas', 'criar_cena_ra4_passes.py')
WARMUP = 120

CASES = [
    ('none', 'spread'),
    ('sun3', 'spread'),
    ('sun3', 'tight'),
    ('sun2', 'spread'),
    ('point', 'spread'),
]


def profile_avg(path):
    """Media das linhas AVG do profiler: categoria Shadows e total, em ms."""
    shadows, totals = [], []
    if not os.path.exists(path):
        return None, None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            if not line.startswith('AVG'):
                continue
            m = re.search(r'Shadows[=: ]+([0-9.]+)', line)
            if m:
                shadows.append(float(m.group(1)))
            m = re.search(r'frame[=: ]+([0-9.]+)', line)
            if m:
                totals.append(float(m.group(1)))
    avg = lambda v: sum(v) / len(v) if v else None
    return avg(shadows), avg(totals)


def main():
    out_dir = os.path.abspath(sys.argv[1])
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for light, layout in CASES:
        tag = '%s_%s_%d' % (light, layout, count)
        scene = os.path.join(out_dir, tag + '.range')
        result = os.path.join(out_dir, tag + '.json')
        prof = os.path.join(out_dir, tag + '_profile.txt')
        for p in (result, prof):
            if os.path.exists(p):
                os.remove(p)
        subprocess.run([EDITOR, '-b', '--factory-startup', '--python', GEN, '--',
                        scene, str(count), layout, light], check=True, capture_output=True, timeout=120)
        env = dict(os.environ, RA4P_RESULT=result, RA4P_FRAMES='600', RANGE_PROFILE=prof)
        subprocess.run([RUNTIME, scene], env=env, capture_output=True, timeout=120)
        if not os.path.exists(result):
            rows.append('%-22s sem resultado' % tag)
            continue
        samples = json.load(open(result))[WARMUP:]
        n = len(samples)
        up = sum(s['uploads'] for s in samples) / n
        sp = sum(s['shadowPasses'] for s in samples) / n
        dc = sum(s['draws'] for s in samples) / n
        fps = samples[-1]['fps']
        sh, fr = profile_avg(prof)
        rows.append('%-22s uploads/q=%5.2f  shadowPasses/q=%5.2f  draws/q=%6.1f  fps=%7.1f  Shadows=%s ms  frame=%s ms'
                    % (tag, up, sp, dc, fps,
                       '%.3f' % sh if sh is not None else '?', '%.3f' % fr if fr is not None else '?'))
        print(rows[-1], flush=True)
    with open(os.path.join(out_dir, 'resumo.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(rows) + '\n')


if __name__ == '__main__':
    main()
