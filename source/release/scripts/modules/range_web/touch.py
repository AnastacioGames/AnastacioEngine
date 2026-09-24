# Controle na tela do pacote Web/Android (A1, etapa T3): layouts prontos e o aviso de entrada que o toque nao
# alcanca (WEB-INPUT-001). Puro: recebe o que o coletor leu do .range e dos mapas KeyMapping/*.json.
#
# Os layouts sao os de `touchLayouts` no template de tools/web/package-web.py; mudou la, mude o _REACH aqui
# (test_range_web.py confere as teclas contra o template).

from .i18n import Msg
from .results import EVIDENCE_POTENTIAL, SEVERITY_INFO, SEVERITY_WARNING, Finding

LAYOUTS = ("none", "stick", "dpad", "twin", "wasd", "arrows", "fps")
STICK_MODES = ("dynamic", "fixed")
DEFAULT_LAYOUT = "stick"
DEFAULT_STICK = "dynamic"

# SCA_IInputDevice::SCA_EnumInputs (os mesmos numeros de bge.events e dos bindings do Input System).
KEY_RET, KEY_SPACE = 7, 8
KEY_A, KEY_D, KEY_S, KEY_W = 23, 26, 41, 45
KEY_LEFT, KEY_DOWN, KEY_RIGHT, KEY_UP = 69, 70, 71, 72
# Toque fora dos controles chega ao jogo como mouse (emulacao do SDL): so botao esquerdo e movimento.
MOUSE_LEFT, MOUSE_X, MOUSE_Y = 116, 126, 127
# KX_PythonJoystick::JOYSTICK_EnumInputs (bindings JOYSTICK do Input System).
JOY_A, JOY_B, JOY_X, JOY_Y = 1, 2, 3, 4
JOY_DPAD_UP, JOY_DPAD_DOWN, JOY_DPAD_LEFT, JOY_DPAD_RIGHT = 12, 13, 14, 15
JOY_LEFTX, JOY_LEFTY, JOY_RIGHTX, JOY_RIGHTY = 100, 101, 102, 103

# Nome da tecla no sensor Keyboard (RNA) -> codigo SCA, so para as teclas que algum layout aperta.
_SENSOR_KEYS = {"RET": KEY_RET, "SPACE": KEY_SPACE, "W": KEY_W, "A": KEY_A, "S": KEY_S, "D": KEY_D,
                "UP_ARROW": KEY_UP, "DOWN_ARROW": KEY_DOWN, "LEFT_ARROW": KEY_LEFT, "RIGHT_ARROW": KEY_RIGHT}
_JOY_SENSOR_BUTTONS = {"BUTTON_A": JOY_A, "BUTTON_B": JOY_B, "BUTTON_X": JOY_X, "BUTTON_Y": JOY_Y,
                       "BUTTON_DPAD_UP": JOY_DPAD_UP, "BUTTON_DPAD_DOWN": JOY_DPAD_DOWN,
                       "BUTTON_DPAD_LEFT": JOY_DPAD_LEFT, "BUTTON_DPAD_RIGHT": JOY_DPAD_RIGHT}
_JOY_SENSOR_STICKS = {"LEFT_STICK": (JOY_LEFTX, JOY_LEFTY), "RIGHT_STICK": (JOY_RIGHTX, JOY_RIGHTY)}
_JOY_SENSOR_AXES = {"LEFT_STICK_HORIZONTAL": JOY_LEFTX, "LEFT_STICK_VERTICAL": JOY_LEFTY,
                    "RIGHT_STICK_HORIZONTAL": JOY_RIGHTX, "RIGHT_STICK_VERTICAL": JOY_RIGHTY}

# layout -> (teclas, entradas do gamepad 0)
_REACH = {
    "none": ((), ()),
    "stick": ((), (JOY_LEFTX, JOY_LEFTY, JOY_A, JOY_B)),
    "dpad": ((), (JOY_DPAD_UP, JOY_DPAD_DOWN, JOY_DPAD_LEFT, JOY_DPAD_RIGHT, JOY_A, JOY_B, JOY_X, JOY_Y)),
    "twin": ((), (JOY_LEFTX, JOY_LEFTY, JOY_RIGHTX, JOY_RIGHTY)),
    "wasd": ((KEY_W, KEY_S, KEY_A, KEY_D, KEY_SPACE), ()),
    "arrows": ((KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_SPACE, KEY_RET), ()),
    # O stick direito move o mouse (MOUSE_X/Y) e um botao aperta o esquerdo, que o toque ja alcanca sempre.
    "fps": ((KEY_W, KEY_S, KEY_A, KEY_D, KEY_SPACE, MOUSE_LEFT), ()),
}

RULE_ID = "WEB-INPUT-001"
_FIX = "Choose a touch layout that presses these inputs, or add a mapping the layout reaches."


def reach(layout):
    """(teclas, entradas do gamepad) que o layout aperta; o mouse (toque fora dos controles) conta sempre."""
    keys, joy = _REACH[layout]
    return frozenset(keys) | {MOUSE_LEFT, MOUSE_X, MOUSE_Y}, frozenset(joy)


def _codes(values):
    """Valores de um binding ("45", "0" = vazio) -> inteiros; None se algum nao for numero."""
    out = []
    for v in values:
        try:
            n = int(str(v).strip())
        except ValueError:
            return None
        if n:
            out.append(n)
    return out


def _binding_reached(binding, keys, joy):
    """Um binding do Input System e alcancado se todas as entradas dele estiverem no layout."""
    if not isinstance(binding, dict):
        return False
    peripheral = str((binding.get("PERIPHERALTYPE") or {}).get("TYPE", "")).upper()
    pool = joy if peripheral == "JOYSTICK" else keys if peripheral in ("KEYBOARD", "MOUSE") else None
    if pool is None:
        return False
    parts = [v for name, v in binding.items() if name != "PERIPHERALTYPE" and isinstance(v, dict)]
    if not parts:
        return False
    for part in parts:
        codes = _codes(part.values())
        if not codes or any(c not in pool for c in codes):
            return False
    return True


def check_input_maps(layout, maps):
    """`maps`: {nome do mapa: dados do KeyMapping/<nome>.json}. Um aviso por acao sem binding alcancado."""
    keys, joy = reach(layout)
    findings = []
    for map_name in sorted(maps):
        data = maps[map_name]
        if not isinstance(data, dict):
            continue
        for action in sorted(data):
            table = data[action]
            bindings = table.get("Bindings") if isinstance(table, dict) else None
            if not isinstance(bindings, dict) or not bindings:
                continue
            if any(_binding_reached(b, keys, joy) for b in bindings.values()):
                continue
            findings.append(Finding(
                RULE_ID, SEVERITY_WARNING, EVIDENCE_POTENTIAL,
                Msg("Input action %s has no binding the touch layout '%s' presses.", action, layout),
                fix=_FIX, capability="touch",
                location={"source": "KeyMapping/%s.json" % map_name, "chain": "%s > %s" % (map_name, action)}))
    return findings


def check_sensors(layout, sensors):
    """`sensors`: [(cena, objeto, nome, tipo, dados)] dos sensores Keyboard e Joystick. dados: key/all_keys
    (Keyboard) ou event_type/button/stick/axis/all_events (Joystick), com os identificadores RNA."""
    keys, joy = reach(layout)
    findings = []
    for scene, obj, name, kind, info in sensors:
        if kind == "KEYBOARD":
            if info.get("all_keys") or info.get("key") in (None, "", "NONE"):
                continue
            if _SENSOR_KEYS.get(info["key"]) in keys:
                continue
            what = Msg("Keyboard sensor %s (key %s)", name, info["key"])
        elif kind == "JOYSTICK":
            event = info.get("event_type")
            if info.get("all_events") and joy:
                continue
            if event == "BUTTONS":
                needed = [_JOY_SENSOR_BUTTONS.get(info.get("button"))]
            elif event == "STICK_DIRECTIONS":
                needed = list(_JOY_SENSOR_STICKS.get(info.get("stick"), (None,)))
            elif event == "STICK_AXIS":
                needed = [_JOY_SENSOR_AXES.get(info.get("axis"))]
            else:  # gatilhos: nenhum layout tem
                needed = [None]
            if all(n in joy for n in needed):
                continue
            what = Msg("Joystick sensor %s", name)
        else:
            continue
        findings.append(Finding(
            RULE_ID, SEVERITY_WARNING, EVIDENCE_POTENTIAL,
            Msg("%s is not pressed by the touch layout '%s'.", what, layout),
            fix=_FIX, capability="touch",
            location={"scene": scene, "object": obj, "chain": "%s > %s > %s" % (scene or "-", obj, name)}))
    return findings


def check_touch(layout, sensors, maps):
    """Regra completa. Sem controle na tela e com entrada de teclado/gamepad, um so aviso informativo em vez de
    um por sensor: o autor escolheu jogar sem controle na tela (so toque = clique)."""
    if layout not in _REACH:
        layout = DEFAULT_LAYOUT
    if layout == "none":
        uses = [s for s in sensors if s[3] in ("KEYBOARD", "JOYSTICK")]
        if not uses and not check_input_maps("none", maps):
            return []
        return [Finding(RULE_ID, SEVERITY_INFO, EVIDENCE_POTENTIAL,
                        Msg("Touch controls are off: on phones and tablets only taps reach the game."),
                        fix="Choose a touch layout in Web (Range) > Touch controls.", capability="touch")]
    return check_sensors(layout, sensors) + check_input_maps(layout, maps)
