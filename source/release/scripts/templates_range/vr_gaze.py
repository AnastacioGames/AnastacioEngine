"""Mira por olhar (gaze) com seleção por tempo para o modo VR do celular.

Uso: na câmera, um sensor Always com pulso (True Level Triggering) ligado a um controlador Python
em modo Module `vr_gaze.update`. Objetos selecionáveis têm a propriedade de jogo `gaze` (qualquer valor).

Olhar para um deles por GAZE_TIME segundos marca `gaze_selected = True` nele (e envia a mensagem
"gaze_select" com o nome do objeto no corpo). Se existir um objeto chamado `GazeBar`, filho da câmera,
a escala X dele mostra o progresso (0 a 1).
"""
import bge

GAZE_TIME = 1.5
GAZE_DISTANCE = 30.0


def update(cont):
    cam = cont.owner
    dt = 1.0 / max(bge.logic.getLogicTicRate(), 1.0)

    origin = cam.worldPosition
    target = origin + cam.gazeDirection * GAZE_DISTANCE
    hit = cam.rayCast(target, origin, GAZE_DISTANCE, "gaze", 1, 1)[0]

    prev = cam.get("gaze_obj")
    if hit is not prev:
        cam["gaze_obj"] = hit
        cam["gaze_t"] = 0.0
        if hit is not None:
            hit["gaze_selected"] = False

    progress = 0.0
    if hit is not None and not hit.get("gaze_selected"):
        cam["gaze_t"] = cam.get("gaze_t", 0.0) + dt
        progress = min(cam["gaze_t"] / GAZE_TIME, 1.0)
        if progress >= 1.0:
            hit["gaze_selected"] = True
            bge.logic.sendMessage("gaze_select", hit.name)

    bar = cam.children.get("GazeBar") if hasattr(cam.children, "get") else None
    if bar is not None:
        s = bar.localScale
        bar.localScale = (max(progress, 0.001), s[1], s[2])
