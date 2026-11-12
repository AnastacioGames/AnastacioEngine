"""Rastro de transparência no TAA/TAAU sem abrir janela na tela.

    python tools/debug/medir_taau_transparente.py [cena.range] [--env NOME=VALOR ...]

Cena: tools/debug/cenas/criar_cena_taau_transparente.py (cubo vermelho alpha 0,5 atravessando
a tela na frente do carro parado). Modos: sem_taa (verdade, sem histórico), taa (resolução
cheia) e taau (Balanced). Tira 6 prints por modo e conta, por print, os pixels avermelhados
(R - max(G, B)): "cubo" > 60 e "rastro" entre 12 e 60 (tinta fraca deixada pelo histórico).
Imprime "VIDRO <modo> cubo=... rastro=..." (médias por print).
"""

import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'tools/testes_engine'))
import controle  # noqa: E402

ARGS = sys.argv[1:]
ENV = {}
while '--env' in ARGS:
    i = ARGS.index('--env')
    k, v = ARGS[i + 1].split('=', 1)
    ENV[k] = v
    del ARGS[i:i + 2]
CENA = Path(ARGS[0] if ARGS else RAIZ / 'artifacts/testes/taau/taau_vidro.range').resolve()


def rodar(nome, taa, modo):
    jogo = controle.abrir_jogo(CENA, largura=960, altura=540, env_extra=ENV)
    contas = []
    try:
        jogo.py(codigo="fm = logic.getCurrentScene().filterManager; fm.taaEnabled = %s; fm.taaUpscale = %d" % (taa, modo))
        jogo.esperar(frames=60)
        for k in range(6):
            arq = str(CENA.parent / ('vidro_%s_%d.png' % (nome, k)))
            jogo.tela(arquivo=arq)
            for _ in range(50):
                try:
                    Image.open(arq).load()
                    break
                except Exception:
                    time.sleep(0.2)
            img = np.asarray(Image.open(arq).convert('RGB'), dtype=np.int32)
            tinta = img[:, :, 0] - np.maximum(img[:, :, 1], img[:, :, 2])
            contas.append(((tinta > 60).sum(), ((tinta > 12) & (tinta <= 60)).sum()))
            jogo.esperar(frames=7)
    finally:
        try:
            jogo.fechar()
        except Exception:
            pass
    c = np.mean(contas, axis=0)
    print('VIDRO %-7s cubo=%.0f rastro=%.0f' % (nome, c[0], c[1]))


rodar('sem_taa', False, 0)
rodar('taa', True, 0)
rodar('taau', True, 2)
