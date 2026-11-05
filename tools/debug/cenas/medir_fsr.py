"""Compara upscalers com escala fixa: roda fsr_test.range nas escalas 0.5/0.67/0.75/1.0.
Roda com o Python do sistema. Cada caso abre o AnastacioRuntime (~300 quadros, poucos s) e fecha sozinho.

  FSR_TAG=bilinear python tools/debug/cenas/medir_fsr.py [escalas...]
  opcional: RANGE_WEAK_GPU=4 simula GPU fraca (fator >= 1.01, ver KX_WeakGpu.cpp)

Saida em artifacts/fsr/: shot_<tag>_<escala>.png, res_<tag>_<escala>.txt e resumo_<tag>.txt.
A cena e gerada com criar_cena_fsr.py se ainda nao existir.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EDITOR = os.path.join(ROOT, 'build', 'bin', 'AnastacioEngine.exe')
RUNTIME = os.path.join(ROOT, 'build', 'bin', 'AnastacioRuntime.exe')
GEN = os.path.join(ROOT, 'tools', 'debug', 'cenas', 'criar_cena_fsr.py')
OUT = os.path.join(ROOT, 'artifacts', 'fsr')
SCENE = os.path.join(OUT, 'fsr_test.range')


def main():
    scales = sys.argv[1:] or ['0.5', '0.67', '0.75', '1.0']
    tag = os.environ.get('FSR_TAG', 'bilinear')
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(SCENE):
        subprocess.run([EDITOR, '-b', '--factory-startup', '--python', GEN, '--', SCENE],
                       check=True, capture_output=True, timeout=120)
    rows = []
    for s in scales:
        shot = os.path.join(OUT, 'shot_%s_%s.png' % (tag, s))
        res = os.path.join(OUT, 'res_%s_%s.txt' % (tag, s))
        for p in (shot, res):
            if os.path.exists(p):
                os.remove(p)
        env = dict(os.environ, FSR_SCALE=s, FSR_SHOT=shot, FSR_RESULT=res)
        try:
            subprocess.run([RUNTIME, SCENE], env=env, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            rows.append('%s %s: timeout' % (tag, s))
            print(rows[-1], flush=True)
            continue
        line = open(res).read().strip() if os.path.exists(res) else 'sem resultado'
        rows.append('%s %s: %s shot=%s' % (tag, s, line, 'ok' if os.path.exists(shot) else 'FALTOU'))
        print(rows[-1], flush=True)
    with open(os.path.join(OUT, 'resumo_%s.txt' % tag), 'w', encoding='utf-8') as f:
        f.write('RANGE_WEAK_GPU=%s\n' % os.environ.get('RANGE_WEAK_GPU', ''))
        f.write('\n'.join(rows) + '\n')


if __name__ == '__main__':
    main()
