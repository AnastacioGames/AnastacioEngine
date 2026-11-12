"""Prova de conceito do upscaling temporal (docs/plano-opensource.md item 3) sem abrir janela na tela.

    python tools/debug/medir_taau.py [cena.range] [escala] [--hud]

Cena: tools/debug/cenas/criar_cena_taa_movimento.py (carro listrado com a câmera presa atrás, chão
listrado). Roda o AnastacioRuntime no desktop invisível do controle.py em três modos:
  nativo   resolução cheia com TAA (referência)
  fsr1     cena reduzida (RANGE_TAAU=<escala>) com TAA desligado: FSR 1 EASU+RCAS no fim
  taa_fsr1 cena reduzida com TAA na resolução reduzida e FSR 1 no fim (RANGE_TAAU_PASSIVE=1)
  taau     cena reduzida com TAA: o passe TAA amplia com o histórico na resolução da janela
Para cada modo tira um print parado e outro com o carro andando, e mede a diferença média
(0-255) para o nativo na mesma situação, mais a fração de pixels com diferença > 40, só no
retângulo do carro (parado na tela; o chão anda e muda de fase conforme o instante do print).
Depois mede o tempo de GPU por etapa (RANGE_PROFILE, ~10 s por modo, carro andando) e imprime a
soma das etapas e as de filtro/apresentação.
--hud (cena de tools/debug/cenas/criar_cena_taau_hud.py): mede também o retângulo do HUD (texto e
moldura fina, cena overlay), que com o TAAU deve sair igual ao nativo; e pula a medição de GPU.
Imprime "TAAU ..." por modo. Prints ao lado da cena.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'tools/testes_engine'))
import controle  # noqa: E402

HUD = '--hud' in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
CENA = Path(ARGS[0] if ARGS else RAIZ / 'artifacts/testes/taau/taau.range').resolve()
ESCALA = ARGS[1] if len(ARGS) > 1 else '0.67'
SAIDA = CENA.parent


CAIXA = (0.38, 0.32, 0.62, 0.80)  # carro, frações da janela (como medir_taa_movimento.py)


CAIXA_HUD = (0.01, 0.02, 0.40, 0.09)  # texto do HUD, sobre o céu


def cinza(arquivo, caixa=CAIXA):
    img = np.asarray(Image.open(arquivo).convert('L'), dtype=np.float32)
    h, w = img.shape
    return img[int(caixa[1] * h):int(caixa[3] * h), int(caixa[0] * w):int(caixa[2] * w)]


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
    'taa_fsr1': rodar('taa_fsr1', True, {'RANGE_TAAU': ESCALA, 'RANGE_TAAU_PASSIVE': '1'}),
    'taau': rodar('taau', True, {'RANGE_TAAU': ESCALA}),
}
for nome in ('fsr1', 'taa_fsr1', 'taau'):
    for caso in ('parado', 'andando'):
        ref = cinza(modos['nativo'][caso])
        img = cinza(modos[nome][caso])
        if img.shape != ref.shape:
            print('TAAU %-8s %-7s tamanho diferente %s x %s' % (nome, caso, img.shape, ref.shape))
            continue
        dif = np.abs(img - ref)
        print('TAAU %-8s %-7s dif_media=%.2f pixels_errados=%.2f%%' % (nome, caso, dif.mean(), (dif > 40).mean() * 100))
        if HUD:
            dh = np.abs(cinza(modos[nome][caso], CAIXA_HUD) - cinza(modos['nativo'][caso], CAIXA_HUD))
            print('TAAU %-8s %-7s HUD dif_media=%.2f pixels_errados=%.2f%%' % (nome, caso, dh.mean(), (dh > 40).mean() * 100))
print('TAAU prints em', SAIDA)
if HUD:
    sys.exit(0)


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
    print('TAAU GPU %-8s total=%.3f ms (%d médias) %s' % (nome, sum(soma.values()), len(avgs), partes))


gpu('nativo', True, {})
gpu('fsr1', False, {'RANGE_TAAU': ESCALA})
gpu('taa_fsr1', True, {'RANGE_TAAU': ESCALA, 'RANGE_TAAU_PASSIVE': '1'})
gpu('taau', True, {'RANGE_TAAU': ESCALA})
