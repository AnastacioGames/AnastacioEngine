"""Ajustes do modo VR do celular, aplicados uma vez ao iniciar.

Uso: na câmera, um sensor Always (sem pulso) ligado a um controlador Python em modo Module `vr_tune.apply`.

LENS_STRENGTH: força da distorção de lente (0 a 1, padrão 0.3). Suba se as bordas parecerem esticadas pela lente
do visor, desça se a imagem ficar curvada demais. Só vale com "VR Lens Distortion" ligado na cena.
HEAD_SMOOTHING: constante de tempo em segundos do filtro da cabeça (0 desliga, padrão 0.04). Suba para reduzir o
tremor da imagem; valores altos fazem a imagem acompanhar a cabeça com atraso.
"""
import bge

LENS_STRENGTH = 0.3
HEAD_SMOOTHING = 0.04


def apply(cont):
    bge.render.setVRLensStrength(LENS_STRENGTH)
    bge.logic.motion.smoothing = HEAD_SMOOTHING
