"""Diálogo e voz dos eventos de Cutscene (chamado pela engine, KX_SceneCutscene.cpp).

show_dialog(obj, text, speaker, audio, wait) -> bool
    Mostra a fala e toca a voz `audio`. Se um Dialogue Box da UI Tree lê `obj`
    (Source = Property ou Text Object), a fala vai para a caixa na tela, com o
    nome em Speaker; a espera acaba quando o jogador fecha a última página.
    Senão escreve no objeto Text `obj`.
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

fade(mode, duration) / letterbox(show, duration)
    Escurecer (mode 0 = para o preto, 1 = do preto) e faixas pretas de cinema,
    num filtro 2D próprio (passo OVERLAY_PASS). update() anima a cada quadro.

update(dt, in_progress) -> int
    Chamado pela engine a cada quadro enquanto a cutscene roda ou há efeito na
    tela. Bit 1: ainda há efeito na tela. Bit 2: o jogador pediu para pular
    (Tab ou Start do controle; desligue com globalDict["cutscene_skip"] = False).

Sem objeto Text, a fala fica em logic.globalDict["cutscene_dialog"]
({"text", "speaker", "audio"}) para uma interface própria do jogo.
"""

from Range import logic

WAIT_SUBJECT = "cutscene_dialog"

_current = {"obj": None, "message": None, "handle": None, "shown": None,
            "box": None, "box_speaker": None, "box_wait": False}

# Passo do filtro de fade/faixas: depois dos filtros do jogo e do vídeo (120).
OVERLAY_PASS = 121
# Altura de cada faixa preta, em fração da tela.
LETTERBOX_SIZE = 0.12
SKIP_KEYS = ("TABKEY",)
SKIP_JOY_BUTTON = 6  # Start no layout SDL GameController

OVERLAY_SHADER = """
uniform sampler2D bgl_RenderedTexture;
uniform float fade_alpha;
uniform float bar_size;

void main()
{
	vec2 uv = gl_TexCoord[0].st;
	vec4 color = texture2D(bgl_RenderedTexture, uv);
	float bar = step(uv.y, bar_size) + step(1.0 - bar_size, uv.y);
	color.rgb *= 1.0 - clamp(bar, 0.0, 1.0);
	color.rgb *= 1.0 - fade_alpha;
	gl_FragColor = color;
}
"""


class _Ramp:
    """Valor que vai de `value` até `target` em `duration` segundos."""

    def __init__(self):
        self.value = 0.0
        self.target = 0.0
        self.speed = 0.0

    def start(self, start, target, duration):
        self.value = start
        self.target = target
        self.speed = abs(target - start) / duration if duration > 0.0 else float("inf")
        if duration <= 0.0:
            self.value = target

    def step(self, dt):
        if self.value < self.target:
            self.value = min(self.target, self.value + self.speed * dt)
        elif self.value > self.target:
            self.value = max(self.target, self.value - self.speed * dt)

    @property
    def moving(self):
        return self.value != self.target


_fade = _Ramp()
_bars = _Ramp()
_overlay = {"filter": None, "scene": None, "joy_down": False}


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


def _find_dialogue_box(obj):
    """(ui, Dialogue) de um Dialogue Box da UI Tree que lê `obj`, ou None."""
    try:
        import range_ui_runtime
    except ImportError:
        return None
    if range_ui_runtime.get() is None:
        return None
    for ui in range_ui_runtime._instances:
        for screen in ui.screens.values():
            for box in screen.dialogues:
                data = box.data
                if data.get("source") in ("PROPERTY", "TEXT_OBJECT") and ui.obj_for(data) is obj:
                    return ui, box
    return None


def _box_write(box, obj, text):
    if box.data.get("source") == "PROPERTY":
        obj[box.data["property"]] = text
    else:
        obj.text = text


def _release_box(clear):
    found = _current["box"]
    _current["box"] = None
    _current["box_wait"] = False
    if found is None:
        return
    box, obj, speaker = found
    box.data["speaker"] = speaker
    if clear and obj is not None and not getattr(obj, "invalid", True):
        _box_write(box, obj, "")


def _box_finished():
    box, obj, _speaker = _current["box"]
    if obj is None or getattr(obj, "invalid", True):
        return True
    if box.data.get("source") == "PROPERTY":
        # A caixa esvazia a propriedade no fim da última página.
        return obj.get(box.data["property"], "") == ""
    return box.done


def show_dialog(obj, text, speaker="", audio="", wait=False):
    _restore_message()
    _release_box(clear=False)
    old = _current["shown"]
    if old is not None and old is not obj and not getattr(old, "invalid", True):
        old.visible = False
    logic.globalDict["cutscene_dialog"] = {"text": text, "speaker": speaker, "audio": audio}
    _play_voice(audio)
    if obj is None:
        return False

    found = _find_dialogue_box(obj)
    if found is not None:
        _ui, box = found
        _current["box"] = (box, obj, box.data.get("speaker", ""))
        if speaker:
            box.data["speaker"] = speaker
        box.reset()  # a mesma frase duas vezes também recomeça
        _box_write(box, obj, text)
        _current["box_wait"] = bool(wait)
        return bool(wait)

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
    _release_box(clear=True)
    obj = _current["shown"]
    _current["shown"] = None
    _restore_message()
    _stop_voice()
    logic.globalDict.pop("cutscene_dialog", None)
    if obj is not None and not getattr(obj, "invalid", True):
        obj.visible = False


def _overlay_filter():
    scene = logic.getCurrentScene()
    filt = _overlay["filter"]
    if filt is not None and _overlay["scene"] is scene and not getattr(filt, "invalid", False):
        return filt
    manager = scene.filterManager
    filt = manager.getFilter(OVERLAY_PASS)
    if filt is None:
        filt = manager.addFilter(OVERLAY_PASS, logic.RAS_2DFILTER_CUSTOMFILTER, OVERLAY_SHADER)
    _overlay["filter"] = filt
    _overlay["scene"] = scene
    return filt


def _apply_overlay():
    if _fade.value <= 0.0 and _bars.value <= 0.0:
        _remove_overlay()
        return
    filt = _overlay_filter()
    filt.setUniform("fade_alpha", _fade.value)
    filt.setUniform("bar_size", _bars.value * LETTERBOX_SIZE)


def _remove_overlay():
    if _overlay["filter"] is None:
        return
    _overlay["filter"] = None
    try:
        _overlay["scene"].filterManager.removeFilter(OVERLAY_PASS)
    except Exception:
        pass
    _overlay["scene"] = None


def fade(mode, duration):
    if mode == 1:  # do preto
        _fade.start(1.0 if not _fade.moving and _fade.value <= 0.0 else _fade.value, 0.0, duration)
    else:  # para o preto
        _fade.start(_fade.value, 1.0, duration)
    _apply_overlay()


def letterbox(show, duration):
    _bars.start(_bars.value, 1.0 if show else 0.0, duration)
    _apply_overlay()


def _skip_pressed():
    if not logic.globalDict.get("cutscene_skip", True):
        return False
    from Range import events
    keyboard = logic.keyboard.inputs
    pressed = any(keyboard[getattr(events, name)].activated for name in SKIP_KEYS)
    joy = next((j for j in logic.joysticks if j is not None), None)
    down = joy is not None and SKIP_JOY_BUTTON in joy.activeButtons
    pressed = pressed or (down and not _overlay["joy_down"])
    _overlay["joy_down"] = down
    return pressed


def update(dt, in_progress):
    flags = 0
    if _current["box_wait"] and _box_finished():
        _current["box_wait"] = False
        logic.sendMessage(WAIT_SUBJECT)
    if _fade.moving or _bars.moving:
        _fade.step(dt)
        _bars.step(dt)
        _apply_overlay()
    if _overlay["filter"] is not None:
        flags |= 1
    if in_progress and _skip_pressed():
        flags |= 2
    return flags


def _clear_overlay():
    _fade.start(0.0, 0.0, 0.0)
    _bars.start(0.0, 0.0, 0.0)
    _remove_overlay()


def skip_cleanup():
    """Pulou a cutscene: sem fala, sem voz, sem fade nem faixas."""
    hide_dialog()
    _clear_overlay()


def stop():
    """Fim/parada da cutscene: some com a fala, a voz e os efeitos de tela."""
    hide_dialog()
    _clear_overlay()
