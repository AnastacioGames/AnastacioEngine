"""Prova de conceito do upscaling temporal (docs/plano-opensource.md item 3) sem abrir janela na tela.

    python tools/debug/medir_taau.py [cena.range] [escala]

Cena: tools/debug/cenas/criar_cena_taa_movimento.py (carro listrado com a câmera presa atrás, chão
listrado). Roda o AnastacioRuntime no desktop invisível do controle.py em três modos:
  nativo   resolução cheia com TAA (referência)
  fsr1     cena reduzida (RANGE_TAAU=<escala>) com TAA desligado: FSR 1 EASU+RCAS no fim
  taau     cena reduzida com TAA: o passe TAA amplia com o histórico na resolução da janela
Para cada modo tira um print parado e outro com o carro andando, e mede a diferença média
(0-255) para o nativo na mesma situação, mais a fração de pixels com diferença > 40, só no
retângulo do carro (parado na tela; o chão anda e muda de fase conforme o instante do print).
Depois mede o tempo de GPU por etapa (RANGE_PROFILE, ~10 s por modo, carro andando) e imprime a
soma das etapas e as de filtro/apresentação.
Imprime "TAAU ..." por modo. Prints ao lado da cena.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'tools/testes_engine'))
import controle  # noqa: E402

CENA = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / 'artifacts/testes/taau/taau.range').resolve()
ESCALA = sys.argv[2] if len(sys.argv) > 2 else '0.67'
SAIDA = CENA.parent


CAIXA = (0.38, 0.32, 0.62, 0.80)  # carro, frações da janela (como medir_taa_movimento.py)


def cinza(arquivo):
    img = np.asarray(Image.open(arquivo).convert('L'), dtype=np.float32)
    h, w = img.shape
    return img[int(CAIXA[1] * h):int(CAIXA[3] * h), int(CAIXA[0] * w):int(CAIXA[2] * w)]


def rodar(nome, taa, env):
    jogo = controle.abrir_jogo(CENA, largura=960, altura=540, env_extra=env)
    prints = {}
    try:
        jogo.py(codigo="cena = logic.getCurrentScene(); cena.filterManager.taaEnabled = %s; "
                       "resultado = (cena.filterManager.taaEnabled, render.getRenderScale())" % taa)
        jogo.esperar(frames=90)
        prints['parado'] = str(SAIDA / (nome + '_parado.png'))
        jogo.tela(arquivo=prints['parado'])
        jogo.py(codigo="logic.getCurrentScene().objects['Carro']['andar'] = True")
        jogo.esperar(frames=60)
        prints['andando'] = str(SAIDA / (nome + '_andando.png'))
        jogo.tela(arquivo=prints['andando'])
    finally:
        try:
            jogo.fechar()
        except Exception:
            pass
    return prints


modos = {
    'nativo': rodar('nativo', True, {}),
    'fsr1': rodar('fsr1', False, {'RANGE_TAAU': ESCALA}),
    'taau': rodar('taau', True, {'RANGE_TAAU': ESCALA}),
}
for nome in ('fsr1', 'taau'):
    for caso in ('parado', 'andando'):
        ref = cinza(modos['nativo'][caso])
        img = cinza(modos[nome][caso])
        if img.shape != ref.shape:
            print('TAAU %-6s %-7s tamanho diferente %s x %s' % (nome, caso, img.shape, ref.shape))
            continue
        dif = np.abs(img - ref)
        print('TAAU %-6s %-7s dif_media=%.2f pixels_errados=%.2f%%' % (nome, caso, dif.mean(), (dif > 40).mean() * 100))
print('TAAU prints em', SAIDA)


def gpu(nome, taa, env):
    import time
    prof = SAIDA / ('prof_%s.txt' % nome)
    prof.unlink(missing_ok=True)
    jogo = controle.abrir_jogo(CENA, largura=1920, altura=1080, env_extra=dict(env, RANGE_PROFILE=str(prof)))
    try:
        jogo.py(codigo="logic.getCurrentScene().filterManager.taaEnabled = %s; "
                       "logic.getCurrentScene().objects['Carro']['andar'] = True" % taa)
        time.sleep(10)
    finally:
        try:
            jogo.fechar()
        except Exception:
            pass
    avgs = [l for l in prof.read_text(errors='replace').splitlines() if l.startswith('AVG') and 'gpu:' in l][2:]
    soma = {}
    for l in avgs:
        for item in l.split('gpu:')[1].split():
            if '=' in item:
                k, v = item.split('=', 1)
                try:
                    soma[k] = soma.get(k, 0.0) + float(v) / len(avgs)
                except ValueError:
                    pass
    partes = ' '.join('%s=%.3f' % (k, v) for k, v in sorted(soma.items()) if 'filter' in k or 'present' in k or 'cameras' in k)
    print('TAAU GPU %-6s total=%.3f ms (%d médias) %s' % (nome, sum(soma.values()), len(avgs), partes))


gpu('nativo', True, {})
gpu('fsr1', False, {'RANGE_TAAU': ESCALA})
gpu('taau', True, {'RANGE_TAAU': ESCALA})
