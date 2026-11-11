"""Mede os vetores de movimento do TAA sem abrir janela na tela do usuário.

    python tools/debug/medir_taa_movimento.py [cena.range] [--cinza]

Roda o AnastacioRuntime no desktop invisível do controle.py em três modos:
  sem_taa      TAA desligado (referência de nitidez, com serrilhado)
  so_camera    TAA só com a reprojeção da câmera (RANGE_TAA_VELOCITY_OFF=1, etapa 1)
  com_vetor    TAA com o vetor de movimento por objeto (etapa 2)
Para cada um tira um print com o objeto "Carro" parado e outro com a propriedade "andar" ligada.
Prints ao lado da cena.

Modo padrão (cena tools/debug/cenas/criar_cena_taa_movimento.py): o carro anda com a câmera presa
atrás, fica parado na tela; mede a fração de pixels do retângulo do carro com diferença > 40 entre
os dois prints. Medido em 2026-11-11 (RX 6800M): sem_taa 0,4%; so_camera 7,1%; com_vetor 0,4%.

Modo --cinza (cena tools/debug/cenas/criar_cena_taa_skin.py, câmera parada, osso indo e voltando):
as listras são só preto e branco, então rastro do TAA vira cinza; mede a fração de pixels cinza
(40-215) numa área larga em volta da barra, parado x andando. Esperado: com_vetor andando perto do
parado, so_camera bem acima. Também imprime a métrica cinza no modo padrão.
Imprime "TAAMOV ..." e o veredito.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'tools/testes_engine'))
import controle  # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
CINZA = '--cinza' in sys.argv
CENA = Path(ARGS[0] if ARGS else RAIZ / 'artifacts/testes/taa2/taa_mov.range').resolve()
SAIDA = CENA.parent  # prints ao lado da cena
# Retângulos (frações da janela): o do carro (câmera fixa em relação a ele) e o da barra indo e voltando.
CAIXA = (0.38, 0.32, 0.62, 0.80)
CAIXA_CINZA = (0.15, 0.25, 0.85, 0.85) if CINZA else (0.42, 0.36, 0.58, 0.76)


def regiao(arquivo, caixa):
    img = np.asarray(Image.open(arquivo).convert('L'), dtype=np.float32)
    h, w = img.shape
    return img[int(caixa[1] * h):int(caixa[3] * h), int(caixa[0] * w):int(caixa[2] * w)]


def cinza(arquivo):
    r = regiao(arquivo, CAIXA_CINZA)
    return float(((r > 40) & (r < 215)).mean() * 100)


def rodar(nome, taa, env):
    jogo = controle.abrir_jogo(CENA, largura=960, altura=540, env_extra=env)
    try:
        jogo.py(codigo="cena = logic.getCurrentScene(); cena.filterManager.taaEnabled = %s; "
                       "resultado = cena.filterManager.taaEnabled" % taa)
        jogo.esperar(frames=60)
        parado = str(SAIDA / (nome + '_parado.png'))
        jogo.tela(arquivo=parado)
        jogo.py(codigo="logic.getCurrentScene().objects['Carro']['andar'] = True")
        jogo.esperar(frames=60)
        andando = str(SAIDA / (nome + '_andando.png'))
        jogo.tela(arquivo=andando)
    finally:
        try:
            jogo.fechar()
        except Exception:
            pass
    dif = np.abs(regiao(parado, CAIXA) - regiao(andando, CAIXA))
    fora = float((dif > 40).mean() * 100)
    c0, c1 = cinza(parado), cinza(andando)
    print('TAAMOV %-10s pixels_errados=%.2f%% cinza_parado=%.2f%% cinza_andando=%.2f%%' % (nome, fora, c0, c1))
    return fora, c0, c1


r = {
    'sem_taa': rodar('sem_taa', False, {}),
    'so_camera': rodar('so_camera', True, {'RANGE_TAA_VELOCITY_OFF': '1'}),
    'com_vetor': rodar('com_vetor', True, {}),
}
if CINZA:
    extra_cam = r['so_camera'][2] - r['so_camera'][1]
    extra_vet = r['com_vetor'][2] - r['com_vetor'][1]
    ok = extra_cam > 0.5 and extra_vet < 0.5 * extra_cam
else:
    ok = r['com_vetor'][0] < max(1.0, 2.0 * r['sem_taa'][0]) and r['so_camera'][0] > 2.0 * r['com_vetor'][0]
print('TAAMOV', 'PASS' if ok else 'FAIL')
print('TAAMOV prints em', SAIDA)
