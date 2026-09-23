"""Cena de regressao: add/remove/replace/overlay/suspend/resume de cenas (Plano 3).

Anexar como script "Always" (pulso todo frame) num objeto da cena principal.
Espera duas cenas adicionais no arquivo, com os nomes abaixo (ajustar via
propriedades do objeto se os nomes forem outros):
    - SCENE_BACKGROUND: cena de fundo/overlay usada nos testes de add/remove
    - SCENE_REPLACEMENT: cena usada para substituir a cena principal

Cada passo roda por N frames e verifica o estado esperado via
logic.getSceneList()/scene.suspended antes de avancar. Resultado (PASS/FAIL)
e' impresso no console; nenhuma captura de tela e' usada (validacao visual
fica a cargo do teste manual em jogo real).
"""

import Range as bge

SCENE_BACKGROUND = "SCENE_BACKGROUND"
SCENE_REPLACEMENT = "SCENE_REPLACEMENT"

STEP_FRAMES = 10  # frames de folga entre agendar uma operacao e verificar o resultado


def _scene_names():
    return [s.name for s in bge.logic.getSceneList()]


def _fail(cont, msg):
    print("[scene_lifecycle_regression] FAIL: " + msg)
    cont.owner["lifecycle_test_failed"] = True


def _check(cont, condition, msg):
    if not condition:
        _fail(cont, msg)
    return condition


def main(cont):
    owner = cont.owner
    if "lifecycle_test_failed" not in owner:
        owner["lifecycle_test_failed"] = False
    if "lifecycle_step" not in owner:
        owner["lifecycle_step"] = 0
        owner["lifecycle_step_frame"] = 0
        print("[scene_lifecycle_regression] iniciando")

    step = owner["lifecycle_step"]
    frame_in_step = owner["lifecycle_step_frame"]

    # --- Passo 0: overlay add ---------------------------------------------
    if step == 0:
        if frame_in_step == 0:
            bge.logic.addScene(SCENE_BACKGROUND, 1)
            print("[scene_lifecycle_regression] passo 0: addScene overlay " + SCENE_BACKGROUND)
        elif frame_in_step == STEP_FRAMES:
            _check(cont, SCENE_BACKGROUND in _scene_names(),
                   "overlay " + SCENE_BACKGROUND + " nao apareceu em getSceneList()")

    # --- Passo 1: remover a cena de overlay (scene.end()) ------------------
    elif step == 1:
        if frame_in_step == 0:
            bg = bge.logic.getSceneList()
            target = next((s for s in bg if s.name == SCENE_BACKGROUND), None)
            if _check(cont, target is not None, "cena " + SCENE_BACKGROUND + " nao encontrada para remover"):
                target.end()
                print("[scene_lifecycle_regression] passo 1: end() em " + SCENE_BACKGROUND)
        elif frame_in_step == STEP_FRAMES:
            _check(cont, SCENE_BACKGROUND not in _scene_names(),
                   "overlay " + SCENE_BACKGROUND + " ainda presente apos end()")

    # --- Passo 2: suspend/resume da cena principal -------------------------
    elif step == 2:
        current = bge.logic.getCurrentScene()
        if frame_in_step == 0:
            current.suspend()
            print("[scene_lifecycle_regression] passo 2: suspend()")
        elif frame_in_step == 2:
            _check(cont, current.suspended, "cena principal nao ficou suspended apos suspend()")
            current.resume()
            print("[scene_lifecycle_regression] passo 2: resume()")
        elif frame_in_step == STEP_FRAMES:
            _check(cont, not current.suspended, "cena principal continuou suspended apos resume()")

    # --- Passo 3: replace da cena principal --------------------------------
    elif step == 3:
        current = bge.logic.getCurrentScene()
        if frame_in_step == 0:
            ok = current.replace(SCENE_REPLACEMENT)
            _check(cont, ok, "replace(" + SCENE_REPLACEMENT + ") retornou False (cena nao existe no arquivo?)")
            print("[scene_lifecycle_regression] passo 3: replace -> " + SCENE_REPLACEMENT)
        elif frame_in_step == STEP_FRAMES:
            names = _scene_names()
            _check(cont, SCENE_REPLACEMENT in names,
                   SCENE_REPLACEMENT + " nao esta ativa apos replace()")
            _check(cont, len(names) == 1,
                   "esperava exatamente 1 cena ativa apos replace(), achou: " + str(names))

    # --- Passo 4: resultado final -------------------------------------------
    elif step == 4:
        if not owner["lifecycle_test_failed"]:
            print("[scene_lifecycle_regression] PASS: todos os passos concluidos sem falha")
        else:
            print("[scene_lifecycle_regression] RESULTADO: houve FAIL(s), ver mensagens acima")
        return

    owner["lifecycle_step_frame"] = frame_in_step + 1
    if frame_in_step + 1 > STEP_FRAMES:
        owner["lifecycle_step"] = step + 1
        owner["lifecycle_step_frame"] = 0
