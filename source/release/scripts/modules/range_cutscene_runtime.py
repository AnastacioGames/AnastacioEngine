"""Diálogo e voz dos eventos de Cutscene (chamado pela engine, KX_SceneCutscene.cpp).

show_dialog(obj, text, speaker, audio, wait) -> bool
    Escreve a fala no objeto Text `obj` e toca a voz `audio`.
    Com `obj` preparado pelo "Setup Dialogue" (range_text_dialogue), a máquina
    de escrever e o avanço (Enter/clique/botão A) já funcionam. Se `wait` for
    verdadeiro, o objeto passa a mandar a mensagem WAIT_SUBJECT quando o jogador
    passa da última página; a engine espera essa mensagem (Wait Trigger).
    Retorna True quando a espera pode ser liberada por esse objeto.

camera_cut()
    Chamado no corte de câmera: um objeto Text filho de uma câmera passa
    para a câmera ativa, na mesma posição relativa (a legenda segue os cortes).

hide_dialog()
    Esconde o objeto da fala atual e para a voz.

Sem objeto Text, a fala fica em logic.globalDict["cutscene_dialog"]
({"text", "speaker", "audio"}) para uma interface própria do jogo.
"""

from Range import logic

WAIT_SUBJECT = "cutscene_dialog"

_current = {"obj": None, "message": None, "handle": None, "shown": None}


def _stop_voice():
    handle = _current["handle"]
    _current["handle"] = None
    if handle is not None:
        try:
            handle.stop()
        except Exception:
            pass


def _play_voice(path):
    _stop_voice()
    if not path:
        return
    try:
        import aud
        full = logic.expandPath(path)
        _current["handle"] = aud.device().play(aud.Factory(full))
    except Exception as exc:
        print("[cutscene] voz não tocou (%s): %s" % (path, exc))


def _restore_message():
    obj = _current["obj"]
    message = _current["message"]
    _current["obj"] = None
    _current["message"] = None
    if obj is None or getattr(obj, "invalid", True) or message is None:
        return
    obj["td_message"] = message


def _follow_active_camera(obj):
    if obj is None or getattr(obj, "invalid", True):
        return
    parent = obj.parent
    camera = logic.getCurrentScene().active_camera
    if parent is None or camera is None or parent is camera or not hasattr(parent, "fov"):
        return
    local = obj.localTransform.copy()
    obj.setParent(camera)
    obj.localTransform = local


def camera_cut():
    _follow_active_camera(_current["shown"])


def show_dialog(obj, text, speaker="", audio="", wait=False):
    _restore_message()
    old = _current["shown"]
    if old is not None and old is not obj and not getattr(old, "invalid", True):
        old.visible = False
    logic.globalDict["cutscene_dialog"] = {"text": text, "speaker": speaker, "audio": audio}
    _play_voice(audio)
    if obj is None:
        return False

    line = "%s: %s" % (speaker, text) if speaker else text
    try:
        import range_text_dialogue
        # Esquece o estado anterior: a mesma frase duas vezes também recomeça.
        range_text_dialogue._states.pop(id(obj), None)
    except Exception:
        pass
    _current["shown"] = obj
    _follow_active_camera(obj)
    obj.text = line
    obj.visible = True

    has_dialogue_logic = "td_end" in obj
    if wait and has_dialogue_logic:
        _current["obj"] = obj
        _current["message"] = obj.get("td_message", "")
        obj["td_message"] = WAIT_SUBJECT
        return True
    return False


def hide_dialog():
    obj = _current["shown"]
    _current["shown"] = None
    _restore_message()
    _stop_voice()
    logic.globalDict.pop("cutscene_dialog", None)
    if obj is not None and not getattr(obj, "invalid", True):
        obj.visible = False


def stop():
    """Fim/parada da cutscene: some com a fala e a voz."""
    hide_dialog()
