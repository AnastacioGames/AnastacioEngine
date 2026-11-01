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

shot_to(empty) / start_shots() / restore_shot_camera()
    Tomadas por Empty (as do addon Cutscene Shot Tool): a câmera ativa vai até
    o Empty e segue as propriedades dele (transition, transition_speed, fov,
    target, pan_target, follow, shake, noise, slowmo_scale, filter_on/off,
    duration). start_shots() passa por todos os Empties com "order", em ordem,
    cada um pelo seu duration. restore_shot_camera() devolve a câmera ao lugar.

path_start(obj, curve)
    Camera Path: a engine move `obj` pela curva (com transition/ease/target/
    duration da curva); aqui entram fov, shake, noise, slowmo_scale e
    filter_on/off da curva, até a próxima tomada ou a volta da câmera.

Sem objeto Text, a fala fica em logic.globalDict["cutscene_dialog"]
({"text", "speaker", "audio"}) para uma interface própria do jogo.
"""

import math
import random

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
        for screen in list(ui.huds) + list(ui.screens.values()):
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


# -- tomadas por Empty (Cutscene Shot Tool) ----------------------------------

ORDER_PROP_ALIASES = ("index", "order", "step", "ordem", "shot_index")
# transition_speed 1.0 = a câmera cobre ~63% da distância em 1/4 de segundo.
SMOOTH_RATE = 4.0
NOISE_AMPLITUDE = 0.015

_shot = {"cam": None, "saved": None, "empty": None, "time": 0.0, "queue": [],
         "offset": None, "seed": 0.0, "filter_off": ""}


def _shot_order(obj):
    for key in obj.getPropertyNames():
        if key.strip().lower() in ORDER_PROP_ALIASES:
            try:
                return float(obj[key])
            except (TypeError, ValueError):
                return None
    return None


def _scene_object(name):
    return logic.getCurrentScene().objects.get(name) if name else None


def _begin_shot(empty):
    scene = logic.getCurrentScene()
    cam = _shot["cam"] if _shot["cam"] is not None and not _shot["cam"].invalid else scene.active_camera
    if cam is None:
        return
    if _shot["saved"] is None:
        _shot["saved"] = (cam.parent, cam.localTransform.copy(), cam.fov)
        cam.removeParent()
    if _shot["filter_off"]:
        logic.sendMessage(_shot["filter_off"])
    _shot["cam"] = cam
    _shot["empty"] = empty
    _shot["time"] = 0.0
    _shot["filter_off"] = str(empty.get("filter_off", ""))
    follow = _scene_object(empty.get("follow", ""))
    _shot["offset"] = (empty.worldPosition - follow.worldPosition) if follow is not None else None
    if "fov" in empty:
        cam.fov = float(empty["fov"])
    _set_timescale(float(empty.get("slowmo_scale", 1.0)) or 1.0)
    if empty.get("filter_on", ""):
        logic.sendMessage(str(empty["filter_on"]))
    if str(empty.get("transition", "SMOOTH")).upper() == "CUT":
        _place_camera(1.0)


def _shot_pose():
    from mathutils import Vector
    empty = _shot["empty"]
    duration = max(0.001, float(empty.get("duration", 3.5)))
    pos = empty.worldPosition.copy()
    pan = _scene_object(empty.get("pan_target", ""))
    if pan is not None:
        pos = pos.lerp(pan.worldPosition, min(1.0, _shot["time"] / duration))
    follow = _scene_object(empty.get("follow", ""))
    if follow is not None and _shot["offset"] is not None:
        pos = follow.worldPosition + _shot["offset"]
    target = _scene_object(empty.get("target", ""))
    if target is not None and (target.worldPosition - pos).length > 1e-4:
        rot = (target.worldPosition - pos).to_track_quat('-Z', 'Y')
    else:
        rot = empty.worldOrientation.to_quaternion()
    t = _shot["time"] + _shot["seed"]
    if empty.get("noise", True):
        pos += Vector((math.sin(t * 0.9), math.sin(t * 1.3 + 1.0), math.sin(t * 0.7 + 2.0))) * NOISE_AMPLITUDE
    shake = float(empty.get("shake", 0.0))
    if shake > 0.0:
        pos += Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1))) * shake * 0.05
    return pos, rot


def _place_camera(factor):
    cam = _shot["cam"]
    pos, rot = _shot_pose()
    if factor >= 1.0:
        cam.worldPosition = pos
        cam.worldOrientation = rot.to_matrix()
        return
    cam.worldPosition = cam.worldPosition.lerp(pos, factor)
    current = cam.worldOrientation.to_quaternion()
    cam.worldOrientation = current.slerp(rot, factor).to_matrix()


def _update_shot(dt):
    empty = _shot["empty"]
    cam = _shot["cam"]
    if empty is None or empty.invalid or cam is None or cam.invalid:
        return
    _shot["time"] += dt
    if _shot["queue"] and _shot["time"] >= float(empty.get("duration", 3.5)):
        _begin_shot(_shot["queue"].pop(0))
        empty = _shot["empty"]
    if str(empty.get("transition", "SMOOTH")).upper() == "CUT":
        _place_camera(1.0)
    else:
        rate = SMOOTH_RATE * max(0.05, float(empty.get("transition_speed", 0.7)))
        _place_camera(1.0 - math.exp(-rate * dt))


def shot_to(empty):
    """Camera Shot com um Empty: vai para essa tomada (para a fila do start_shots)."""
    _shot["queue"] = []
    _shot["seed"] = random.uniform(0.0, 100.0)
    _end_path_fx(restore=True)
    _begin_shot(empty)


def start_shots():
    """Camera Start sem componente: todas as tomadas com "order", em ordem. Retorna False se não houver."""
    shots = [o for o in logic.getCurrentScene().objects if _shot_order(o) is not None]
    shots.sort(key=_shot_order)
    if not shots:
        return False
    shot_to(shots[0])
    _shot["queue"] = shots[1:]
    return True


def shots_active():
    return _shot["empty"] is not None


_path = {"obj": None, "curve": None, "saved": None, "time": 0.0, "seed": 0.0, "filter_off": ""}


def _end_path_fx(restore):
    obj, saved = _path["obj"], _path["saved"]
    last, last_pos = _path.get("last"), _path.get("last_pos")
    if obj is not None and not obj.invalid and last is not None and last_pos is not None:
        if (obj.worldPosition - last_pos).length < 1e-6:
            obj.worldPosition = obj.worldPosition - last  # sem o último tremor
    if _path["filter_off"]:
        logic.sendMessage(_path["filter_off"])
    _path.update(obj=None, curve=None, saved=None, filter_off="", last=None, last_pos=None)
    if restore and saved is not None and obj is not None and not obj.invalid:
        obj.fov = saved


def path_start(obj, curve):
    """Efeitos da curva no objeto que a percorre (normalmente a câmera)."""
    saved = _path["saved"] if _path["obj"] is obj else None
    _end_path_fx(restore=_path["obj"] is not obj)
    if saved is None:
        saved = getattr(obj, "fov", None)
    _path.update(obj=obj, curve=curve, saved=saved, time=0.0, seed=random.uniform(0.0, 100.0),
                 filter_off=str(curve.get("filter_off", "")))
    if "fov" in curve and hasattr(obj, "fov"):
        obj.fov = float(curve["fov"])
    if "slowmo_scale" in curve:
        _set_timescale(float(curve["slowmo_scale"]) or 1.0)
    if curve.get("filter_on", ""):
        logic.sendMessage(str(curve["filter_on"]))


def _update_path_fx(dt):
    from mathutils import Vector
    obj, curve = _path["obj"], _path["curve"]
    if obj is None or obj.invalid or curve is None or curve.invalid:
        return
    _path["time"] += dt
    t = _path["time"] + _path["seed"]
    offset = Vector((0.0, 0.0, 0.0))
    if curve.get("noise", False):
        offset += Vector((math.sin(t * 0.9), math.sin(t * 1.3 + 1.0), math.sin(t * 0.7 + 2.0))) * NOISE_AMPLITUDE
    shake = float(curve.get("shake", 0.0))
    if shake > 0.0:
        offset += Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1))) * shake * 0.05
    # Tira o tremor do quadro anterior antes de pôr o novo: com a curva já
    # terminada (câmera parada) ele também não acumula.
    last = _path.get("last")
    base = obj.worldPosition.copy()
    if last is not None and _path.get("last_pos") is not None and (base - _path["last_pos"]).length < 1e-6:
        base -= last
    obj.worldPosition = base + offset
    _path["last"] = offset
    _path["last_pos"] = obj.worldPosition.copy()


def restore_shot_camera():
    """Devolve a câmera ao pai, à posição e ao FOV de antes das tomadas."""
    _end_path_fx(restore=True)
    _restore_timescale()
    cam, saved = _shot["cam"], _shot["saved"]
    if _shot["filter_off"]:
        logic.sendMessage(_shot["filter_off"])
    _shot.update(cam=None, saved=None, empty=None, queue=[], offset=None, filter_off="")
    if saved is None:
        return
    parent, local, fov = saved
    if cam is None or cam.invalid:
        return
    if parent is not None and not parent.invalid:
        cam.setParent(parent, False, False)
    cam.localTransform = local
    cam.fov = fov


_timescale = {"saved": None}


def _set_timescale(value):
    """Câmera lenta de uma tomada; a escala original volta no fim da cutscene."""
    if _timescale["saved"] is None:
        _timescale["saved"] = logic.getTimeScale()
    logic.setTimeScale(value)


def _restore_timescale():
    if _timescale["saved"] is not None:
        logic.setTimeScale(_timescale["saved"])
        _timescale["saved"] = None


def update(dt, in_progress):
    if not in_progress:
        # A cutscene acabou sem Restore: a câmera pode ficar, a câmera lenta não.
        _restore_timescale()
    flags = 0
    if _shot["empty"] is not None:
        _update_shot(dt)
        flags |= 1
    if _path["obj"] is not None:
        _update_path_fx(dt)
        flags |= 1
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
    restore_shot_camera()
    _clear_overlay()


def stop():
    """Fim/parada da cutscene: some com a fala, a voz e os efeitos de tela."""
    hide_dialog()
    restore_shot_camera()
    _clear_overlay()
