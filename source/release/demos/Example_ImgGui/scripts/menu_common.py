"""
Painel de Opcoes compartilhado (checkpoint (g) + Fase 2 / item 3 do plano de
menu ImGui) - AnastacioEngine.

Video/controles usam apenas APIs que ja existiam antes desta extensao:
 - Range.render: setVsync/setAntiAliasing/setAnisotropicFiltering (ja usados
   desde o checkpoint (g)), setFullScreen/setWindowSize/getDisplayDimensions.
 - SCA_KeyboardSensor.key: atributo read/write existente -- este modulo NAO
   mexe em sensores diretamente (isso e especifico de cada jogo), so guarda
   e persiste o mapeamento acao->tecla; o controller do jogador deve chamar
   get_keybind(options, "jump") em vez de comparar contra uma tecla fixa.
 - Range.logic.keyboard.events + Range.logic.KX_INPUT_JUST_ACTIVATED: usados
   para o fluxo de "pressione uma tecla" ao reatribuir um controle.

Volume mestre e a UNICA parte desta extensao que precisou de codigo novo de
engine: Range.render.setMasterVolume/getMasterVolume (novo em
KX_PythonInit.cpp), porque `aud.Device()` em Python cria um dispositivo de
audio novo e independente -- NAO e o mesmo dispositivo que o motor de jogo
realmente usa para tocar som (esse e BKE_sound_get_device(), interno).

Usado tanto pelo Main Menu quanto pelo Pause Menu -- ambos so precisam
chamar load_options()/draw_options_panel()/t(); save/apply e feito
internamente.

Persistencia: options.json guarda preferencias do jogador e bindings de
gamepad; imgui_visual.json guarda o layout/aparencia dos menus. Ambos ficam
ao lado do arquivo .range/.blend atual (via Range.logic.expandPath), sem
depender de nada alem da biblioteca padrao do Python.

API para componentes de jogo:
    options = menu_common.load_options()
    if menu_common.action_just_pressed(options, "jump"):
        player.jump()
    camera_x = menu_common.axis_value(options, "camera_x")
"""

import json

import Range
import Range.events as events


_CONFIG_FILENAME = "options.json"
_VISUAL_CONFIG_FILENAME = "imgui_visual.json"

_ANTIALIASING_LEVELS = [0, 2, 4, 8, 16]
_ANISOTROPIC_LEVELS = [1, 2, 4, 8, 16]
_RESOLUTIONS = [(1280, 720), (1600, 900), (1920, 1080)]
_LANGUAGES = ["pt", "en"]

_OPTION_TABS = ["video", "audio", "controls", "joystick", "save_load"]
_SAVE_SLOTS = 3
_SAVE_EXT = "sav"

_GAMEPAD_BUTTONS = [
    ("A", "A"), ("B", "B"), ("X", "X"), ("Y", "Y"),
    ("BACK", "Back"), ("GUIDE", "Guide"), ("START", "Start"),
    ("LEFTSTICK", "L3"), ("RIGHTSTICK", "R3"),
    ("LEFTSHOULDER", "LB"), ("RIGHTSHOULDER", "RB"),
    ("DPADUP", "D-pad Cima"), ("DPADDOWN", "D-pad Baixo"),
    ("DPADLEFT", "D-pad Esquerda"), ("DPADRIGHT", "D-pad Direita"),
]
_GAMEPAD_AXES = [
    ("LEFT_X", 0, "AnalÃ³gico esquerdo X"),
    ("LEFT_Y", 1, "AnalÃ³gico esquerdo Y"),
    ("RIGHT_X", 2, "AnalÃ³gico direito X"),
    ("RIGHT_Y", 3, "AnalÃ³gico direito Y"),
    ("LEFT_TRIGGER", 4, "Gatilho esquerdo"),
    ("RIGHT_TRIGGER", 5, "Gatilho direito"),
]

# Exemplo de acoes remapeaveis -- ajuste esta lista para as acoes reais do
# seu jogo. O controller do jogador deve ler a tecla atual via
# get_keybind(options, "move_forward") em vez de comparar contra uma tecla
# fixa, para respeitar o remapeamento feito aqui.
#
# Construidos sob demanda (nao no escopo do modulo): o editor carrega este
# arquivo com um Range.events "stub" vazio so para validar a classe do
# componente (ver python_component.c), sem os valores reais de WKEY/etc. Ler
# esses atributos no escopo do modulo quebra esse carregamento estatico com
# "module 'types' has no attribute 'WKEY'" mesmo o jogo rodando normalmente.
_default_keybinds_cache = None
_key_names_cache = None


def _default_keybinds():
    global _default_keybinds_cache
    if _default_keybinds_cache is None:
        _default_keybinds_cache = {
            "move_forward": events.WKEY,
            "move_back": events.SKEY,
            "move_left": events.AKEY,
            "move_right": events.DKEY,
            "jump": events.SPACEKEY,
        }
    return _default_keybinds_cache


def _key_names():
    global _key_names_cache
    if _key_names_cache is None:
        _key_names_cache = {
            events.WKEY: "W", events.AKEY: "A", events.SKEY: "S", events.DKEY: "D",
            events.SPACEKEY: "Espaco",
            events.LEFTSHIFTKEY: "Shift Esq", events.RIGHTSHIFTKEY: "Shift Dir",
            events.ESCKEY: "Esc",
            events.UPARROWKEY: "Seta Cima", events.DOWNARROWKEY: "Seta Baixo",
            events.LEFTARROWKEY: "Seta Esq", events.RIGHTARROWKEY: "Seta Dir",
        }
    return _key_names_cache


_DEFAULTS = {
    "vsync": True,
    "antialiasing": 0,
    "anisotropic": 1,
    "master_volume": 1.0,
    "fullscreen": False,
    "resolution_index": 0,
    "language": "pt",
    "gamepad_bindings": {
        "jump": "A", "attack": "X", "interact": "Y", "pause": "START",
    },
    "gamepad_axes": {
        "move_x": {"axis": "LEFT_X", "deadzone": 0.15, "sensitivity": 1.0, "invert": False},
        "move_y": {"axis": "LEFT_Y", "deadzone": 0.15, "sensitivity": 1.0, "invert": False},
        "camera_x": {"axis": "RIGHT_X", "deadzone": 0.15, "sensitivity": 1.0, "invert": False},
        "camera_y": {"axis": "RIGHT_Y", "deadzone": 0.15, "sensitivity": 1.0, "invert": False},
    },
}

_VISUAL_DEFAULTS = {
    "windows": {
        "main_menu": {"h_align": "center", "v_align": "center", "width": 320, "height": 140, "options_width": 720, "options_height": 650},
        "pause_menu": {"h_align": "center", "v_align": "center", "width": 320, "height": 150, "options_width": 720, "options_height": 650},
        "test_widgets": {"h_align": "center", "v_align": "center", "width": 360, "height": 520},
        "test_styling": {"h_align": "center", "v_align": "center", "width": 360, "height": 220},
    },
    "style": {
        "button_color": [0.1, 0.6, 0.1],
        "font_path": "//roboto_mono_medium.ttf",
        "font_size": 20.0,
    },
    "transitions": {"main_menu_fade_frames": 30, "styling_fade_frames": 60},
}

_STRINGS = {
    "pt": {
        "play": "Jogar", "options": "Opcoes", "quit": "Sair", "back": "Voltar",
        "continue": "Continuar", "main_menu": "Main Menu",
        "video": "Video", "audio": "Audio", "controls": "Controles",
        "joystick": "Joystick",
        "vsync": "VSync", "antialiasing": "Anti-aliasing (0/2/4/8/16)",
        "anisotropic": "Filtro anisotropico (1/2/4/8/16)",
        "fullscreen": "Tela cheia", "resolution": "Resolucao",
        "volume": "Volume", "language": "Idioma",
        "no_gamepad": "Nenhum joystick conectado", "detect": "Detectar",
        "axis": "Eixo", "deadzone": "Dead zone", "sensitivity": "Sensibilidade",
        "invert": "Inverter", "press_button": "pressione um botao...",
        "rebind": "Redefinir", "press_any_key": "pressione uma tecla (Esc cancela)",
        "confirm_quit": "Tem certeza que deseja sair?", "yes": "Sim", "no": "Nao",
        "loading": "Carregando...",
        "save_load": "Salvar/Carregar", "slot": "Slot", "save": "Salvar",
        "load": "Carregar", "empty_slot": "vazio", "saved_slot": "Slot salvo!",
        "loaded_slot": "Slot carregado!",
    },
    "en": {
        "play": "Play", "options": "Options", "quit": "Quit", "back": "Back",
        "continue": "Continue", "main_menu": "Main Menu",
        "video": "Video", "audio": "Audio", "controls": "Controls",
        "joystick": "Gamepad",
        "vsync": "VSync", "antialiasing": "Anti-aliasing (0/2/4/8/16)",
        "anisotropic": "Anisotropic filter (1/2/4/8/16)",
        "fullscreen": "Fullscreen", "resolution": "Resolution",
        "volume": "Volume", "language": "Language",
        "no_gamepad": "No gamepad connected", "detect": "Detect",
        "axis": "Axis", "deadzone": "Dead zone", "sensitivity": "Sensitivity",
        "invert": "Invert", "press_button": "press a button...",
        "rebind": "Rebind", "press_any_key": "press any key (Esc cancels)",
        "confirm_quit": "Are you sure you want to quit?", "yes": "Yes", "no": "No",
        "loading": "Loading...",
        "save_load": "Save/Load", "slot": "Slot", "save": "Save",
        "load": "Load", "empty_slot": "empty", "saved_slot": "Slot saved!",
        "loaded_slot": "Slot loaded!",
    },
}


def anchored_window_rect(imgui, h_align, v_align, width, height, margin=20):
    """Calcula (x, y) para posicionar uma janela ImGui ancorada na tela.

    h_align: "left" | "center" | "right"
    v_align: "top" | "center" | "bottom"
    `width`/`height` sao o tamanho pretendido da janela (o mesmo que vai em
    set_next_window_size), usados so para calcular onde encostar quando o
    align nao for "left"/"top". Retorna (x, y) para set_next_window_pos.
    """
    screen_w, screen_h = imgui.get_display_size()

    if h_align == "left":
        x = margin
    elif h_align == "right":
        x = screen_w - width - margin
    else:  # center
        x = (screen_w - width) / 2.0

    if v_align == "top":
        y = margin
    elif v_align == "bottom":
        y = screen_h - height - margin
    else:  # center
        y = (screen_h - height) / 2.0

    return x, y


def set_anchored_window(imgui, h_align, v_align, width, height, margin=20,
                         resizable=True):
    """Chama set_next_window_pos/size com base em anchors, pronta para o
    begin() seguinte. Se `resizable=True` (padrao), usa COND_FIRST_USE_EVER
    para o tamanho, entao o jogador pode arrastar a borda pra redimensionar
    sem a janela voltar pro tamanho definido aqui no proximo frame -- so a
    posicao continua sendo reaplicada todo frame (COND_ALWAYS), porque nao
    tem como voce "arrastar" a posicao de uma ancora, so o tamanho.
    """
    x, y = anchored_window_rect(imgui, h_align, v_align, width, height, margin)
    imgui.set_next_window_pos(x, y)
    size_cond = imgui.COND_FIRST_USE_EVER if resizable else imgui.COND_ALWAYS
    imgui.set_next_window_size(width, height, size_cond)


def _config_path():
    return Range.logic.expandPath("//" + _CONFIG_FILENAME)


def _visual_config_path():
    return Range.logic.expandPath("//" + _VISUAL_CONFIG_FILENAME)


def _merge_visual_config(base, saved):
    """Merge only known dictionaries, keeping safe defaults for bad JSON."""
    if not isinstance(saved, dict):
        return base
    for section, values in saved.items():
        if section not in base or not isinstance(values, dict):
            continue
        if section == "windows":
            for name, window in values.items():
                if name not in base[section] or not isinstance(window, dict):
                    continue
                for key, value in window.items():
                    if key in base[section][name] and isinstance(value, type(base[section][name][key])):
                        base[section][name][key] = value
            continue
        for key, value in values.items():
            if key in base[section] and isinstance(value, type(base[section][key])):
                base[section][key] = value
    return base


def load_visual_config():
    config = {
        "windows": {name: dict(values) for name, values in _VISUAL_DEFAULTS["windows"].items()},
        "style": dict(_VISUAL_DEFAULTS["style"]),
        "transitions": dict(_VISUAL_DEFAULTS["transitions"]),
    }
    try:
        with open(_visual_config_path(), "r", encoding="utf-8") as f:
            _merge_visual_config(config, json.load(f))
    except (OSError, ValueError):
        pass
    color = config["style"].get("button_color")
    if not isinstance(color, list) or len(color) != 3:
        config["style"]["button_color"] = list(_VISUAL_DEFAULTS["style"]["button_color"])
    return config


def visual_window(config, name, args):
    """Retorna a configuracao da janela, com os args do componente em prioridade."""
    # O JSON e util para os valores extras (como options_height), mas nao
    # pode sobrescrever os args exibidos no painel do componente.
    result = dict(config.get("windows", {}).get(name, {}))
    result.update({
        "h_align": args["h_align"], "v_align": args["v_align"],
        "width": args["width"], "height": args["height"],
    })
    if result["h_align"] not in ("left", "center", "right"):
        result["h_align"] = args["h_align"]
    if result["v_align"] not in ("top", "center", "bottom"):
        result["v_align"] = args["v_align"]
    for key in ("width", "height"):
        if not isinstance(result[key], (int, float)) or isinstance(result[key], bool) or result[key] <= 0:
            result[key] = args[key]
    if "options_height" in result and (not isinstance(result["options_height"], (int, float)) or result["options_height"] <= 0):
        result["options_height"] = 320
    return result


def find_texture_bindcode(scene, object_name):
    obj = scene.objects.get(object_name)
    if obj is None:
        # Instanced groups can receive a numeric suffix in the scene.
        for candidate in scene.objects:
            if candidate.name.startswith(object_name + "."):
                obj = candidate
                break
    if obj is None:
        return None
    try:
        return obj.meshes[0].materials[0].textures[0].bindCode
    except (IndexError, AttributeError):
        return None


def load_options():
    options = dict(_DEFAULTS)
    options["keybinds"] = dict(_default_keybinds())
    options["gamepad_bindings"] = dict(_DEFAULTS["gamepad_bindings"])
    options["gamepad_axes"] = dict((name, dict(value)) for name, value in _DEFAULTS["gamepad_axes"].items())
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            saved = json.load(f)
            options.update(saved)
            if "keybinds" in saved:
                options["keybinds"] = dict(_default_keybinds())
                options["keybinds"].update(
                    {k: int(v) for k, v in saved["keybinds"].items()})
            if isinstance(saved.get("gamepad_bindings"), dict):
                options["gamepad_bindings"] = dict(_DEFAULTS["gamepad_bindings"])
                options["gamepad_bindings"].update(
                    {str(k): str(v) for k, v in saved["gamepad_bindings"].items() if isinstance(v, str)})
            if isinstance(saved.get("gamepad_axes"), dict):
                options["gamepad_axes"] = dict((name, dict(value)) for name, value in _DEFAULTS["gamepad_axes"].items())
                for name, value in saved["gamepad_axes"].items():
                    if isinstance(value, dict) and name in options["gamepad_axes"]:
                        options["gamepad_axes"][name].update(value)
    except (OSError, ValueError):
        pass
    return options


def save_options(options):
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(options, f)
    except OSError:
        pass


def apply_options(options):
    Range.render.setVsync(Range.render.VSYNC_ON if options["vsync"] else Range.render.VSYNC_OFF)
    Range.render.setAntiAliasing(options["antialiasing"])
    Range.render.setAnisotropicFiltering(options["anisotropic"])

    Range.render.setFullScreen(options["fullscreen"])
    if not options["fullscreen"]:
        w, h = _RESOLUTIONS[options["resolution_index"]]
        Range.render.setWindowSize(w, h)

    Range.render.setMasterVolume(options["master_volume"])


def t(options, key):
    lang = options.get("language", "pt")
    return _STRINGS.get(lang, _STRINGS["pt"]).get(key, key)


def key_name(keycode):
    return _key_names().get(keycode, "Tecla {}".format(keycode))


def get_keybind(options, action):
    """Para o controller do jogador ler a tecla atual de uma acao remapeavel."""
    defaults = _default_keybinds()
    return options.get("keybinds", defaults).get(action, defaults.get(action))


def _get_gamepad(index=0):
    joysticks = getattr(Range.logic, "joysticks", [])
    if index < 0 or index >= len(joysticks):
        return None
    return joysticks[index]


def _gamepad_button_code(name):
    return getattr(Range.logic, "JOYSTICK" + name, None)


def gamepad_button_pressed(name, index=0):
    joy = _get_gamepad(index)
    code = _gamepad_button_code(name)
    return bool(joy and code is not None and code in joy.activeButtons)


def gamepad_button_just_pressed(name, index=0):
    joy = _get_gamepad(index)
    code = _gamepad_button_code(name)
    if joy is None or code is None:
        return False
    event = joy.inputs.get(code)
    return bool(event and Range.logic.KX_INPUT_JUST_ACTIVATED in event.queue)


def _poll_gamepad_button(index=0):
    joy = _get_gamepad(index)
    if joy is None:
        return None
    current = set(joy.activeButtons)
    previous = getattr(_poll_gamepad_button, "previous", set())
    _poll_gamepad_button.previous = current
    for name, label in _GAMEPAD_BUTTONS:
        code = _gamepad_button_code(name)
        if code in current and code not in previous:
            return name
    return None


def action_pressed(options, action, index=0):
    """Programmer API: test a named gamepad action without knowing SDL codes."""
    binding = options.get("gamepad_bindings", {}).get(action)
    return bool(binding and gamepad_button_pressed(binding, index))


def action_just_pressed(options, action, index=0):
    binding = options.get("gamepad_bindings", {}).get(action)
    return bool(binding and gamepad_button_just_pressed(binding, index))


def axis_value(options, action, index=0):
    """Return a normalized axis after dead zone, sensitivity and inversion."""
    config = options.get("gamepad_axes", {}).get(action, {})
    axis_name = config.get("axis")
    axis_index = dict((name, number) for name, number, label in _GAMEPAD_AXES).get(axis_name)
    joy = _get_gamepad(index)
    if joy is None or axis_index is None:
        return 0.0
    values = joy.axisValues
    value = float(values[axis_index]) if axis_index < len(values) else 0.0
    deadzone = max(0.0, min(0.99, float(config.get("deadzone", 0.15))))
    if abs(value) <= deadzone:
        return 0.0
    value = (abs(value) - deadzone) / (1.0 - deadzone) * (1.0 if value >= 0 else -1.0)
    value *= max(0.0, float(config.get("sensitivity", 1.0)))
    return -value if config.get("invert", False) else value


def esc_just_pressed():
    return Range.logic.keyboard.events.get(events.ESCKEY) == Range.logic.KX_INPUT_JUST_ACTIVATED


def _poll_any_key():
    for code, status in Range.logic.keyboard.events.items():
        if status == Range.logic.KX_INPUT_JUST_ACTIVATED:
            return code
    return None


def _draw_tab_bar(imgui, options, listening):
    """Barra de abas feita com botoes comuns (o binding de Range.imgui nao
    expoe BeginTabBar/BeginTabItem do ImGui, so os widgets basicos), com a
    aba ativa destacada via push_style_color/COL_BUTTON_ACTIVE.
    """
    current = listening.setdefault("tab", _OPTION_TABS[0])
    for i, tab in enumerate(_OPTION_TABS):
        if i > 0:
            imgui.same_line()
        is_active = tab == current
        if is_active:
            imgui.push_style_color(imgui.COL_BUTTON, 0.26, 0.59, 0.98, 1.0)
        if imgui.button(t(options, tab), width=130):
            current = tab
            listening["tab"] = tab
        if is_active:
            imgui.pop_style_color(1)
    imgui.separator()
    return current


def _draw_save_load_tab(imgui, options, listening):
    feedback = listening.get("save_feedback")
    for slot in range(1, _SAVE_SLOTS + 1):
        slot_name = "slot{}".format(slot)
        imgui.text("{} {}".format(t(options, "slot"), slot))
        imgui.same_line()
        if imgui.button("{}##save{}".format(t(options, "save"), slot)):
            Range.logic.saveGlobalDict(slot_name, _SAVE_EXT)
            listening["save_feedback"] = t(options, "saved_slot")
        imgui.same_line()
        if imgui.button("{}##load{}".format(t(options, "load"), slot)):
            Range.logic.loadGlobalDict(slot_name, _SAVE_EXT)
            listening["save_feedback"] = t(options, "loaded_slot")

    if feedback:
        imgui.separator()
        imgui.text(feedback)


_GAMEPAD_HITBOXES = {
    "A": (0.74, 0.28, 0.10, 0.10), "B": (0.83, 0.31, 0.10, 0.10),
    "X": (0.66, 0.31, 0.10, 0.10), "Y": (0.74, 0.20, 0.10, 0.10),
    "LEFTSHOULDER": (0.12, 0.10, 0.18, 0.10), "RIGHTSHOUDER": (0.70, 0.10, 0.18, 0.10),
    "DPADUP": (0.30, 0.40, 0.10, 0.08), "DPADDOWN": (0.30, 0.56, 0.10, 0.08),
    "DPADLEFT": (0.24, 0.48, 0.08, 0.10), "DPADRIGHT": (0.38, 0.48, 0.08, 0.10),
    "LEFTSTICK": (0.18, 0.22, 0.18, 0.18), "RIGHTSTICK": (0.56, 0.39, 0.18, 0.18),
    "BACK": (0.39, 0.25, 0.08, 0.07), "START": (0.53, 0.25, 0.08, 0.07),
    "GUIDE": (0.46, 0.20, 0.08, 0.10),
}


def _draw_gamepad_visual(imgui, options, listening, texture_id):
    actions = sorted(options.get("gamepad_bindings", {}))
    if not actions:
        return
    target = listening.get("gamepad_target", actions[0])
    target_index = actions.index(target) if target in actions else 0
    changed, target_index = imgui.combo("AÃ§Ã£o selecionada", target_index, actions)
    if changed:
        listening["gamepad_target"] = actions[target_index]
    target = actions[target_index]
    imgui.text("Clique no botao do controle para atribuir a acao selecionada.")
    if texture_id is None:
        return

    image_x, image_y = imgui.get_cursor_pos()
    screen_x, screen_y = imgui.get_cursor_screen_pos()
    image_w, image_h = 480.0, 320.0
    imgui.image(texture_id, image_w, image_h)
    for name, rect in _GAMEPAD_HITBOXES.items():
        x, y, w, h = rect
        imgui.set_cursor_pos(image_x + x * image_w, image_y + y * image_h)
        if imgui.invisible_button("##gamepad_" + name, w * image_w, h * image_h):
            options["gamepad_bindings"][target] = name
            save_options(options)
        if options["gamepad_bindings"].get(target) == name or gamepad_button_pressed(name):
            imgui.draw_rect_filled(
                screen_x + x * image_w, screen_y + y * image_h,
                screen_x + (x + w) * image_w, screen_y + (y + h) * image_h,
                0.1, 0.8, 1.0, 0.35)
    imgui.set_cursor_pos(image_x, image_y + image_h + 8.0)
    joy = _get_gamepad(0)
    if joy is None:
        imgui.text("Nenhum joystick conectado")
        return


def _draw_joystick_tab(imgui, options, listening):
    bindings = options.setdefault("gamepad_bindings", dict(_DEFAULTS["gamepad_bindings"]))
    _draw_gamepad_visual(imgui, options, listening, listening.get("gamepad_texture"))
    imgui.separator()
    button_names = [label for name, label in _GAMEPAD_BUTTONS]
    button_ids = [name for name, label in _GAMEPAD_BUTTONS]
    for action in sorted(bindings):
        current = bindings.get(action)
        current_index = button_ids.index(current) if current in button_ids else 0
        changed, current_index = imgui.combo(action.replace("_", " ").title(), current_index, button_names)
        if changed:
            bindings[action] = button_ids[current_index]
        imgui.same_line()
        if listening.get("gamepad_action") == action:
            imgui.text(t(options, "press_button"))
            detected = _poll_gamepad_button(0)
            if detected is not None:
                bindings[action] = detected
                listening["gamepad_action"] = None
                save_options(options)
        elif imgui.button("{}##detect_{}".format(t(options, "detect"), action)):
            listening["gamepad_action"] = action

    imgui.separator()
    axes = options.setdefault("gamepad_axes", dict((name, dict(value)) for name, value in _DEFAULTS["gamepad_axes"].items()))
    axis_names = [label for name, number, label in _GAMEPAD_AXES]
    axis_ids = [name for name, number, label in _GAMEPAD_AXES]
    for action, config in sorted(axes.items()):
        current = config.get("axis")
        axis_index = axis_ids.index(current) if current in axis_ids else 0
        changed, axis_index = imgui.combo(action.replace("_", " ").title(), axis_index, axis_names)
        if changed:
            config["axis"] = axis_ids[axis_index]
        changed, config["deadzone"] = imgui.slider_float(
            "{}##deadzone_{}".format(t(options, "deadzone"), action), config.get("deadzone", 0.15), 0.0, 0.8)
        changed2, config["sensitivity"] = imgui.slider_float(
            "{}##sensitivity_{}".format(t(options, "sensitivity"), action), config.get("sensitivity", 1.0), 0.1, 3.0)
        changed3, config["invert"] = imgui.checkbox(
            "{}##invert_{}".format(t(options, "invert"), action), config.get("invert", False))
        if changed or changed2 or changed3:
            save_options(options)


def draw_options_panel(imgui, options, listening, visual_assets=None):
    """Desenha os widgets dentro de uma janela ja aberta (imgui.begin/end sao
    responsabilidade de quem chama). Aplica e salva na hora se algo mudar.

    Organizado em abas (video/audio/controles/salvar-carregar) por meio de
    _draw_tab_bar -- so a aba selecionada desenha seus widgets no frame.

    `listening` e um dict mantido pelo chamador entre frames (ex.:
    self.listening = {"action": None} no start() do componente). Alem de
    "action" (fluxo de "pressione uma tecla" do remapeamento), tambem guarda
    "tab" (aba ativa) e "save_feedback" (mensagem apos salvar/carregar).

    Retorna (changed, options, listening).
    """
    changed = False
    tab = _draw_tab_bar(imgui, options, listening)

    if tab == "video":
        vsync_changed, options["vsync"] = imgui.checkbox(t(options, "vsync"), options["vsync"])
        changed = changed or vsync_changed

        aa = options["antialiasing"]
        aa_index = _ANTIALIASING_LEVELS.index(aa) if aa in _ANTIALIASING_LEVELS else 0
        aa_changed, aa_index = imgui.slider_int(
            t(options, "antialiasing"), aa_index, 0, len(_ANTIALIASING_LEVELS) - 1)
        if aa_changed:
            options["antialiasing"] = _ANTIALIASING_LEVELS[aa_index]
            changed = True

        aniso = options["anisotropic"]
        aniso_index = _ANISOTROPIC_LEVELS.index(aniso) if aniso in _ANISOTROPIC_LEVELS else 0
        aniso_changed, aniso_index = imgui.slider_int(
            t(options, "anisotropic"), aniso_index, 0, len(_ANISOTROPIC_LEVELS) - 1)
        if aniso_changed:
            options["anisotropic"] = _ANISOTROPIC_LEVELS[aniso_index]
            changed = True

        fs_changed, options["fullscreen"] = imgui.checkbox(
            t(options, "fullscreen"), options["fullscreen"])
        changed = changed or fs_changed

        res_items = ["{}x{}".format(w, h) for w, h in _RESOLUTIONS]
        res_changed, options["resolution_index"] = imgui.combo(
            t(options, "resolution"), options["resolution_index"], res_items)
        changed = changed or res_changed

        lang_index = _LANGUAGES.index(options["language"]) if options["language"] in _LANGUAGES else 0
        lang_changed, lang_index = imgui.combo(t(options, "language"), lang_index, _LANGUAGES)
        if lang_changed:
            options["language"] = _LANGUAGES[lang_index]
            changed = True

    elif tab == "audio":
        vol_changed, options["master_volume"] = imgui.slider_float(
            t(options, "volume"), options["master_volume"], 0.0, 1.0)
        changed = changed or vol_changed

    elif tab == "controls":
        defaults = _default_keybinds()
        keybinds = options.setdefault("keybinds", dict(defaults))
        for action in defaults:
            label = action.replace("_", " ").title()
            if listening["action"] == action:
                imgui.text("{}: {}".format(label, t(options, "press_any_key")))
            else:
                current = keybinds.get(action, defaults[action])
                imgui.text("{}: {}".format(label, key_name(current)))
                imgui.same_line()
                if imgui.button("{}##{}".format(t(options, "rebind"), action)):
                    listening["action"] = action

        if listening["action"] is not None:
            pressed = _poll_any_key()
            if pressed is not None:
                if pressed != events.ESCKEY:
                    keybinds[listening["action"]] = pressed
                    changed = True
                listening["action"] = None

    elif tab == "joystick":
        if visual_assets:
            listening["gamepad_texture"] = visual_assets.get("gamepad_texture")
        _draw_joystick_tab(imgui, options, listening)

    else:  # save_load
        _draw_save_load_tab(imgui, options, listening)

    if changed:
        apply_options(options)
        save_options(options)

    return changed, options, listening
