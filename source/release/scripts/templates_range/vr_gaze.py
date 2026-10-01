"""Mira por olhar (gaze) com seleção por tempo para o modo VR do celular.

Uso: na câmera, um sensor Always com pulso (True Level Triggering) ligado a um controlador Python
em modo Module `vr_gaze.update`. Objetos selecionáveis têm a propriedade de jogo `gaze` (qualquer valor).

Olhar para um deles por GAZE_TIME segundos (0 = na hora) marca `gaze_selected = True` nele, deixa-o vermelho e 1,5x maior
enquanto o olhar estiver nele (e envia a mensagem
"gaze_select" com o nome do objeto no corpo). Se existir um objeto chamado `GazeBar`, filho da câmera,
a escala X dele mostra o progresso (0 a 1).
"""
import bge

GAZE_TIME = 0.0  # segundos olhando; 0 = seleciona na hora
GAZE_DISTANCE = 30.0

_state = {"obj": None, "t": 0.0}


def update(cont):
    cam = cont.owner
    dt = 1.0 / max(bge.logic.getLogicTicRate(), 1.0)

    origin = cam.worldPosition
    target = origin + cam.gazeDirection * GAZE_DISTANCE
    hit = cam.rayCast(target, origin, GAZE_DISTANCE, "gaze", 1, 1)[0]

    prev = _state["obj"]
    if hit is not prev:
        if prev is not None and not prev.invalid:
            prev.worldScale = _state["scale"]
            prev.color = _state["color"]
            prev["gaze_selected"] = False
        _state["obj"] = hit
        _state["t"] = 0.0
        if hit is not None:
            _state["scale"] = hit.worldScale.copy()
            _state["color"] = list(hit.color)

    progress = 0.0
    if hit is not None and not hit.get("gaze_selected"):
        _state["t"] += dt
        progress = min(_state["t"] / GAZE_TIME, 1.0) if GAZE_TIME > 0 else 1.0
        if progress >= 1.0:
            hit["gaze_selected"] = True
            hit.color = (1.0, 0.2, 0.2, 1.0)
            hit.worldScale = _state["scale"] * 1.5
            bge.logic.sendMessage("gaze_select", hit.name)

    bar = cam.children.get("GazeBar") if hasattr(cam.children, "get") else None
    if bar is not None:
        s = bar.localScale
        bar.localScale = (max(progress, 0.001), s[1], s[2])
