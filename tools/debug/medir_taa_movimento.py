"""Mede a etapa 2 do TAA (vetores de movimento) sem abrir janela na tela do usuário.

    python tools/debug/medir_taa_movimento.py [cena.range]

Cena: tools/debug/cenas/criar_cena_taa_movimento.py (carro listrado andando, câmera presa atrás).
Roda o AnastacioRuntime no desktop invisível do controle.py em três modos:
  sem_taa      TAA desligado (referência de nitidez, com serrilhado)
  so_camera    TAA só com a reprojeção da câmera (RANGE_TAA_VELOCITY_OFF=1, etapa 1)
  com_vetor    TAA com o vetor de movimento por objeto (etapa 2)
Para cada um tira um print com o carro parado e outro andando. O carro fica parado na tela (a câmera
vai junto), então o retângulo dele deveria sair igual nos dois prints: mede a diferença média e a
fração de pixels com diferença > 40. Esperado: com_vetor perto de sem_taa; so_camera bem acima
(rastro nas bordas). Imprime "TAAMOV ..." e o veredito. Medido em 2026-11-11 (RX 6800M):
sem_taa 0,97 / 0,4%; so_camera 8,83 / 7,1%; com_vetor 1,64 / 0,4%.
"""

import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'tools/testes_engine'))
import controle  # noqa: E402

CENA = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / 'artifacts/testes/taa2/taa_mov.range')
SAIDA = RAIZ / 'artifacts/testes/taa2'
SAIDA.mkdir(parents=True, exist_ok=True)
# Retângulo do carro no print (frações da janela): câmera fixa em relação a ele.
CAIXA = (0.38, 0.32, 0.62, 0.80)


def regiao(arquivo):
    img = np.asarray(Image.open(arquivo).convert('L'), dtype=np.float32)
    h, w = img.shape
    return img[int(CAIXA[1] * h):int(CAIXA[3] * h), int(CAIXA[0] * w):int(CAIXA[2] * w)]


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
    dif = np.abs(regiao(parado) - regiao(andando))
    media, fora = float(dif.mean()), float((dif > 40).mean() * 100)
    print('TAAMOV %-10s dif_media=%.2f pixels_errados=%.2f%%' % (nome, media, fora))
    return media, fora


r = {
    'sem_taa': rodar('sem_taa', False, {}),
    'so_camera': rodar('so_camera', True, {'RANGE_TAA_VELOCITY_OFF': '1'}),
    'com_vetor': rodar('com_vetor', True, {}),
}
ok = r['com_vetor'][1] < max(1.0, 2.0 * r['sem_taa'][1]) and r['so_camera'][1] > 2.0 * r['com_vetor'][1]
print('TAAMOV', 'PASS' if ok else 'FAIL')
print('TAAMOV prints em', SAIDA)
