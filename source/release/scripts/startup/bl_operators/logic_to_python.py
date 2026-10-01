# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

# Converte os logic bricks do objeto ativo num KX_PythonComponent.
# Cada controller vira um bloco no update(); bricks sem tradutor ficam
# ativos e aparecem como TODO no codigo gerado.

import ast
import re
from collections import OrderedDict

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, StringProperty


# Nomes das constantes do modulo events do runtime (KX_PythonInit.cpp).
_RUNTIME_EVENTS = set((
    "ZEROKEY ONEKEY TWOKEY THREEKEY FOURKEY FIVEKEY SIXKEY SEVENKEY EIGHTKEY NINEKEY "
    "CAPSLOCKKEY LEFTCTRLKEY LEFTALTKEY RIGHTALTKEY RIGHTCTRLKEY RIGHTSHIFTKEY LEFTSHIFTKEY "
    "ESCKEY TABKEY RETKEY ENTERKEY SPACEKEY LINEFEEDKEY BACKSPACEKEY DELKEY SEMICOLONKEY "
    "PERIODKEY COMMAKEY QUOTEKEY ACCENTGRAVEKEY MINUSKEY SLASHKEY BACKSLASHKEY EQUALKEY "
    "LEFTBRACKETKEY RIGHTBRACKETKEY LEFTARROWKEY DOWNARROWKEY RIGHTARROWKEY UPARROWKEY "
    "PAD0 PAD1 PAD2 PAD3 PAD4 PAD5 PAD6 PAD7 PAD8 PAD9 PADPERIOD PADSLASHKEY PADASTERKEY "
    "PADMINUS PADENTER PADPLUSKEY OSKEY PAUSEKEY INSERTKEY HOMEKEY PAGEUPKEY PAGEDOWNKEY ENDKEY"
).split())
_RUNTIME_EVENTS.update("%sKEY" % chr(c) for c in range(ord("A"), ord("Z") + 1))
_RUNTIME_EVENTS.update("F%dKEY" % i for i in range(1, 20))

_KEY_EXCEPTIONS = {
    "NUMPAD_ASTERIX": "PADASTERKEY",
    "NUMPAD_SLASH": "PADSLASHKEY",
    "NUMPAD_PLUS": "PADPLUSKEY",
}

_MOUSE_BUTTONS = {
    "LEFTCLICK": "LEFTMOUSE",
    "MIDDLECLICK": "MIDDLEMOUSE",
    "RIGHTCLICK": "RIGHTMOUSE",
    "LEFTTHUMBMOUSECLICK": "LEFTTHUMBMOUSE",
    "RIGHTTHUMBMOUSECLICK": "RIGHTTHUMBMOUSE",
    "BUTTON6CLICK": "BUTTON6MOUSE",
    "BUTTON7CLICK": "BUTTON7MOUSE",
    "WHEELUP": "WHEELUPMOUSE",
    "WHEELDOWN": "WHEELDOWNMOUSE",
}


class Unsupported(Exception):
    pass


def _key_event(rna_key):
    """Identificador de tecla do RNA ('A', 'LEFT_ARROW', 'NUMPAD_1') -> 'events.XKEY'."""
    if rna_key in _KEY_EXCEPTIONS:
        name = _KEY_EXCEPTIONS[rna_key]
    elif rna_key.startswith("NUMPAD_"):
        name = "PAD" + rna_key[len("NUMPAD_"):].replace("_", "")
    else:
        name = rna_key.replace("_", "")
        if name not in _RUNTIME_EVENTS:
            name += "KEY"
    if name not in _RUNTIME_EVENTS:
        raise Unsupported("tecla %s" % rna_key)
    return "events." + name


def _ident(name, prefix):
    s = re.sub(r"\W", "_", name).strip("_").lower() or "brick"
    if s[0].isdigit():
        s = "_" + s
    return "%s_%s" % (prefix, s)


def _owns(collection, item):
    # Comparacao por ponteiro: nomes de bricks so sao unicos dentro de um objeto.
    return any(x == item for x in collection)


def _game_prop_type(ob, name):
    prop = ob.game.properties.get(name)
    return prop.type if prop else None


def _literal(ob, prop_name, text):
    """Valor de sensor/actuator (sempre string no RNA) convertido para o tipo da game property."""
    ptype = _game_prop_type(ob, prop_name)
    if ptype == 'STRING':
        return repr(text)
    if ptype == 'BOOL':
        return repr(text.strip().lower() in {"true", "1"})
    try:
        value = ast.literal_eval(text.strip())
    except (ValueError, SyntaxError):
        value = None
    if isinstance(value, (bool, int, float, str)):
        if ptype == 'INT' and isinstance(value, float):
            value = int(value)
        return repr(value)
    # Expressao de logic brick: so aceitamos o nome de outra game property.
    word = text.strip()
    if word and ob.game.properties.get(word):
        return "ob[%r]" % word
    raise Unsupported("valor '%s' da propriedade %s" % (text, prop_name))


def _axis(rna_axis):
    """Eixo local do sensor ('NEGYAXIS') -> vetor em coordenadas de mundo."""
    neg = rna_axis.startswith("NEG")
    col = "XYZ".index(rna_axis[3 if neg else 0])
    return "%sob.worldOrientation.col[%d]" % ("-" if neg else "", col)


def _vec(v):
    return "(%s)" % ", ".join("%g" % x for x in v)


def _nonzero(v):
    return any(abs(x) > 1e-9 for x in v)


# ---------------------------------------------------------------------------
# Sensores: retornam uma expressao booleana (estado do sensor no frame).

# Valores dos bricks viram args do componente: (nome, codigo do padrao, tipo).
# Preenchido durante convert_object; o codigo gerado le self._a[i].
_ARGS = []
_ACT_LABEL = [""]  # nome do actuator em traducao (com dono, se for de outro objeto)
_GROUP = [""]  # cabecalho (C_Header) do brick em traducao, agrupa os args no painel
_GROUP_ICON = {}  # cabecalho -> icone
_SENSOR_ICONS = {
    'COLLISION': 'MOD_PHYSICS', 'DELAY': 'TIME', 'MESSAGE': 'FILE_TEXT',
    'MOUSE': 'RESTRICT_SELECT_OFF', 'NEAR': 'META_PLANE', 'PROPERTY': 'UI',
    'RADAR': 'OUTLINER_OB_FORCE_FIELD', 'RANDOM': 'RNDCURVE', 'RAY': 'IPO_LINEAR',
    'ACTUATOR': 'LOGIC', 'ANIMATIONEVENT': 'ACTION',
}

# Joystick (SDL GameController): eixos 0/1 stick esquerdo, 2/3 direito, 4/5 gatilhos.
_JOY_BUTTONS = ['BUTTON_A', 'BUTTON_B', 'BUTTON_X', 'BUTTON_Y', 'BUTTON_BACK', 'BUTTON_GUIDE',
                'BUTTON_START', 'BUTTON_STICK_LEFT', 'BUTTON_STICK_RIGHT', 'BUTTON_SHOULDER_LEFT',
                'BUTTON_SHOULDER_RIGHT', 'BUTTON_DPAD_UP', 'BUTTON_DPAD_DOWN', 'BUTTON_DPAD_LEFT',
                'BUTTON_DPAD_RIGHT']
_JOY_SINGLE = {'LEFT_STICK_HORIZONTAL': 0, 'LEFT_STICK_VERTICAL': 1,
               'RIGHT_STICK_HORIZONTAL': 2, 'RIGHT_STICK_VERTICAL': 3}
_DIR_AXES = {'DIRPX': (0, False), 'DIRPY': (1, False), 'DIRPZ': (2, False),
             'DIRNX': (0, True), 'DIRNY': (1, True), 'DIRNZ': (2, True)}
_DYNAMIC = {'DYNAMIC', 'RIGID_BODY', 'SOFT_BODY'}
_ACT_STATE = [None]  # expressao "actuator ativo" do tradutor atual (None = padrao)
_FIRE = "%FIRE%"  # trocado pela variavel de pulso do controller na saida
_MOVE_AXES = {'XAXIS': (0, 1), 'YAXIS': (1, 1), 'ZAXIS': (2, 1),
              'NEGXAXIS': (0, -1), 'NEGYAXIS': (1, -1), 'NEGZAXIS': (2, -1), 'ALLAXIS': (-1, 0)}


def _arg(name, value, kind=None):
    """Registra um arg e retorna a expressao que le o valor no componente."""
    # Mesmo brick traduzido de novo (ligado a varios controllers) reusa o arg.
    name = name[:63]
    if isinstance(value, (bool, int, str)):
        src = repr(value)
    elif isinstance(value, float):
        src = repr(float("%g" % value))
    else:
        src = "(%s)" % ", ".join(repr(float("%g" % x)) for x in value)
    # Sensor e actuator de mesmo nome e campo nao podem dividir o arg.
    base, n = name, 2
    while True:
        same = [i for i, a in enumerate(_ARGS) if a[0] == name]
        if not same:
            break
        if _ARGS[same[0]][3] == _GROUP[0]:
            return "self._a[%d]" % same[0]
        name = ("%s %d" % (base[:60], n))
        n += 1
    _ARGS.append((name, src, kind, _GROUP[0]))
    return "self._a[%d]" % (len(_ARGS) - 1)


def _key_arg(name, rna_key):
    """Tecla vira arg ("<sensor> Key": "D"); retorna a expressao do evento."""
    event = _key_event(rna_key)[len("events."):]
    default = event[:-3] if event.endswith("KEY") and len(event) > 3 else event
    return _arg(name, default, "key")


def _lit_arg(ob, prop_name, text, name):
    """Como _literal, mas constante vira arg (referencia a outra propriedade fica fixa)."""
    lit = _literal(ob, prop_name, text)
    if lit.startswith("ob["):
        return lit
    return _arg(name, ast.literal_eval(lit))


def _act_arg(field, value):
    return _arg("%s %s" % (_ACT_LABEL[0], field), value)


def _sensor_expr(ob, sens, key=None):
    key = key or sens.name
    _GROUP[0] = "Sensor " + key
    if sens.type in _SENSOR_ICONS:
        _GROUP_ICON[_GROUP[0]] = _SENSOR_ICONS[sens.type]
    A =lambda field, value: _arg("%s %s" % (key, field), value)
    t = sens.type
    if t == 'ALWAYS':
        expr = "True"
    elif t == 'KEYBOARD':
        state = "activated" if sens.use_tap else "active"
        if sens.use_all_keys:
            expr = "any(e.%s for e in kb.values())" % state
        else:
            if sens.key == 'NONE':
                raise Unsupported("teclado sem tecla")
            parts = ["kb[%s].%s" % (_key_arg(key + " Key", sens.key), state)]
            for i, mod in enumerate((sens.modifier_key_1, sens.modifier_key_2), 1):
                if mod != 'NONE':
                    parts.append("kb[%s].active" % _key_arg("%s Modifier %d" % (key, i), mod))
            expr = " and ".join(parts)
    elif t == 'MOUSE':
        ev = sens.mouse_event
        if ev in _MOUSE_BUTTONS and sens.hold:
            raise Unsupported("mouse com Hold")  # TODO: converter junto com os bricks de VR
        if ev in _MOUSE_BUTTONS:
            state = "activated" if (sens.use_tap or ev.startswith("WHEEL")) else "active"
            expr = "ms[events.%s].%s" % (_MOUSE_BUTTONS[ev], state)
        elif ev == 'MOVEMENT':
            expr = "self._changed(%r, tuple(logic.mouse.position))" % key
        elif ev in {'MOUSEOVER', 'MOUSEOVERANY'}:
            if sens.use_x_ray or sens.use_material:
                raise Unsupported("mouse over com x-ray/material")
            hit = "self._mouse_hit(%s)" % A("Property", sens.property)
            expr = ("%s is ob" if ev == 'MOUSEOVER' else "%s is not None") % hit
        else:
            raise Unsupported("mouse %s" % ev)
    elif t == 'PROPERTY':
        if sens.use_runtime_property:
            raise Unsupported("property sensor com runtime API")
        p = sens.property
        ev = sens.evaluation_type
        cur = "ob.get(%s)" % A("Property", p)
        val = lambda text, field="Value": _lit_arg(ob, p, text, "%s %s" % (key, field))
        if ev == 'PROPEQUAL':
            expr = "%s == %s" % (cur, val(sens.value))
        elif ev == 'PROPNEQUAL':
            expr = "%s != %s" % (cur, val(sens.value))
        elif ev == 'PROPINTERVAL':
            expr = "%s <= %s <= %s" % (val(sens.value_min, "Min"), cur, val(sens.value_max, "Max"))
        elif ev == 'PROPLESSTHAN':
            expr = "%s < %s" % (cur, val(sens.value))
        elif ev == 'PROPGREATERTHAN':
            expr = "%s > %s" % (cur, val(sens.value))
        elif ev == 'PROPCHANGED':
            expr = "self._changed(%r, %s)" % (key, cur)
        else:
            raise Unsupported("property sensor %s" % ev)
    elif t == 'COLLISION':
        if sens.use_material and sens.material:
            expr = "any(self._has_mat(o, %s) for o in hits)" % A("Material", sens.material)
        elif not sens.use_material and sens.property:
            expr = "any(%s in o for o in hits)" % A("Property", sens.property)
        else:
            expr = "bool(hits)"
    elif t == 'NEAR':
        dist = A("Distance", sens.distance)
        expr = "self._near(%r, %s, %s, max(%s, %s))" % (key, A("Property", sens.property), dist, dist,
                                                        A("Reset", sens.reset_distance))
    elif t == 'RADAR':
        expr = "self._radar(%s, %s, %s, %s / 2.0)" % (_axis(sens.axis), A("Property", sens.property),
                                                      A("Distance", sens.distance), A("Angle", sens.angle))
    elif t == 'RAY':
        if sens.axis == 'GAZE':
            raise Unsupported("ray com eixo VR Gaze")  # TODO: converter junto com os bricks de VR
        mask = sum(1 << i for i, on in enumerate(sens.mask) if on)
        if sens.ray_type != 'PROPERTY' and sens.material:
            if sens.use_x_ray:
                raise Unsupported("ray por material com x-ray")
            # Primeiro objeto atingido precisa ter o material (como KX_RaySensor sem x-ray).
            rng = A("Range", sens.range)
            expr = ("self._has_mat(ob.rayCast(ob.worldPosition + %s * %s, ob, %s, '', 0, 0, 0, %d)[0], %s)" %
                    (_axis(sens.axis), rng, rng, mask, A("Material", sens.material)))
        else:
            rng = A("Range", sens.range)
            prop = A("Property", sens.property) if sens.ray_type == 'PROPERTY' else "''"
            expr = ("ob.rayCast(ob.worldPosition + %s * %s, ob, %s, %s, 0, %d, 0, %d)[0] is not None" %
                    (_axis(sens.axis), rng, rng, prop, sens.use_x_ray, mask))
    elif t == 'DELAY':
        if sens.use_deltatime:
            raise Unsupported("delay em segundos")
        expr = "self._delay(%r, %s, %s, %s, %s)" % (key, A("Delay", sens.delay), A("Duration", sens.duration),
                                                   A("Repeat", sens.use_repeat),
                                                   A("Repeat Times", sens.repeat_times))
    elif t == 'RANDOM':
        # Mesma cadencia (um sorteio a cada tick_skip + 1 frames), sequencia do random do Python.
        expr = "self._random(%r, %s, %d)" % (key, A("Seed", sens.seed), sens.tick_skip)
    elif t == 'MOVEMENT':
        axis, sign = _MOVE_AXES[sens.axis]
        expr = "self._moved(%r, %s, %d, %d, %s)" % (key, sens.use_local, axis, sign,
                                                    A("Threshold", sens.threshold))
    elif t == 'JOYSTICK':
        expr = _joystick_expr(sens, A)
    elif t == 'ACTUATOR':
        # Actuator ativo no frame anterior (actuators rodam depois dos sensores).
        if not sens.actuator:
            raise Unsupported("sensor actuator sem actuator")
        expr = "self._act_on.get(%r, False)" % sens.actuator
    elif t == 'ANIMATIONEVENT':
        trigger = -1 if sens.trigger_all else sens.trigger_index - 1
        expr = "self._anim_event(%r, %d, %d)" % (key, sens.event_index - 1, trigger)
    elif t == 'MESSAGE':
        # Mensagens enviadas no frame anterior para este objeto (ou sem destino), como o sensor.
        expr = "bool(logic.getMessages(ob.name, %s))" % A("Subject", sens.subject)
    else:
        raise Unsupported("sensor %s" % t)
    if sens.invert:
        expr = "not (%s)" % expr
    # Liga/desliga do sensor pelos args (desligado = sensor falso).
    return "%s and (%s)" % (A("Enabled", True), expr)


def _joystick_expr(sens, A):
    # Mesmo teste de SCA_JoystickSensor: positivo enquanto a condicao vale (threshold em -32768..32767).
    idx = A("Index", sens.joystick_index)
    thr = "%s / 32768.0" % A("Threshold", sens.axis_threshold)
    ev = sens.event_type
    if ev == 'BUTTONS':
        buttons = "self._joy(%s)[1]" % idx
        if sens.use_all_events:
            return "bool(%s)" % buttons
        return "%d in %s" % (_JOY_BUTTONS.index(sens.button_number), buttons)
    axes = "self._joy(%s)[0]" % idx
    if ev == 'STICK_DIRECTIONS':
        base = 0 if sens.axis_number == 'LEFT_STICK' else 2
        if sens.use_all_events:
            return "max(abs(%s[%d]), abs(%s[%d])) > %s" % (axes, base, axes, base + 1, thr)
        i, cmp = {'RIGHTAXIS': (0, "> "), 'LEFTAXIS': (0, "< -"),
                  'DOWNAXIS': (1, "> "), 'UPAXIS': (1, "< -")}[sens.axis_direction]
        return "%s[%d] %s%s" % (axes, base + i, cmp, thr)
    if ev == 'STICK_AXIS':
        i = _JOY_SINGLE[sens.single_axis_number]
    else:
        i = 4 if sens.axis_trigger_number == 'LEFT_SHOULDER_TRIGGER' else 5
    return "abs(%s[%d]) > %s" % (axes, i, thr)


# ---------------------------------------------------------------------------
# Controllers: combinam as variaveis dos sensores.

def _controller_expr(ob, cont, sensor_vars):
    t = cont.type
    names = list(sensor_vars.values())
    if not names:
        return "False"
    if t == 'LOGIC_AND':
        return " and ".join(names)
    if t == 'LOGIC_OR':
        return " or ".join(names)
    if t == 'LOGIC_NAND':
        return "not (%s)" % " and ".join(names)
    if t == 'LOGIC_NOR':
        return "not (%s)" % " or ".join(names)
    if t == 'LOGIC_XOR':
        return "(%s) == 1" % " + ".join(names)
    if t == 'LOGIC_XNOR':
        return "(%s) != 1" % " + ".join(names)
    if t == 'EXPRESSION':
        return _expression(ob, cont, sensor_vars)
    if t == 'PYTHON':
        # O script usa getCurrentController() e os bricks ligados; fica como esta.
        raise Unsupported("controller Python (ja e codigo; fica como brick)")
    raise Unsupported("controller %s" % t)


_EXPR_TOKEN = re.compile(r'\s+|"[^"]*"|\d+\.?\d*|[A-Za-z_][A-Za-z0-9_]*|<>|[<>!=]=|[()<>=+\-*/]')


def _expression(ob, cont, sensor_vars):
    """Expression controller -> Python. Nomes viram sensor ligado ou game property."""
    text = cont.expression
    out = []
    pos = 0
    while pos < len(text):
        m = _EXPR_TOKEN.match(text, pos)
        if not m:
            raise Unsupported("expressao '%s'" % text)
        tok = m.group()
        pos = m.end()
        low = tok.lower()
        if tok.isspace():
            continue
        if low in {"and", "or", "not"}:
            out.append(low)
        elif low in {"true", "false"}:
            out.append(low.capitalize())
        elif tok == "=":
            out.append("==")
        elif tok == "<>":
            out.append("!=")
        elif tok[0].isalpha() or tok[0] == "_":
            if tok in sensor_vars:
                out.append(sensor_vars[tok])
            elif ob.game.properties.get(tok):
                out.append("ob[%r]" % tok)
            else:
                raise Unsupported("nome '%s' na expressao" % tok)
        else:
            out.append(tok)
    if not out:
        raise Unsupported("expressao vazia")
    return "bool(%s)" % " ".join(out)


# ---------------------------------------------------------------------------
# Actuators: retornam (linhas, continuo). Continuo roda todo frame com o
# controller positivo; os demais so no pulso positivo.

def _actuator_code(ob, act):
    t = act.type
    if t == 'MOTION':
        if act.mode != 'OBJECT_NORMAL':
            raise Unsupported("motion %s" % act.mode)
        if act.use_vr_gaze:
            raise Unsupported("motion VR Gaze")
        lines = []
        if _nonzero(act.offset_location):
            lines.append("ob.applyMovement(%s, %s)" % (_act_arg("Loc", act.offset_location),
                                                       act.use_local_location))
        if _nonzero(act.offset_rotation):
            lines.append("ob.applyRotation(%s, %s)" % (_act_arg("Rot", act.offset_rotation),
                                                       act.use_local_rotation))
        if _nonzero(act.force):
            lines.append("ob.applyForce(%s, %s)" % (_act_arg("Force", act.force), act.use_local_force))
        if _nonzero(act.torque):
            lines.append("ob.applyTorque(%s, %s)" % (_act_arg("Torque", act.torque), act.use_local_torque))
        if _nonzero(act.linear_velocity):
            local = act.use_local_linear_velocity
            vel = _act_arg("Linear Velocity", act.linear_velocity)
            if act.use_add_linear_velocity:
                lines.append("ob.setLinearVelocity(ob.getLinearVelocity(%s) + Vector(%s), %s)" %
                             (local, vel, local))
            else:
                lines.append("ob.setLinearVelocity(%s, %s)" % (vel, local))
        if _nonzero(act.angular_velocity):
            lines.append("ob.setAngularVelocity(%s, %s)" % (_act_arg("Angular Velocity", act.angular_velocity),
                                                            act.use_local_angular_velocity))
        return lines or ["pass"], True
    if t == 'PROPERTY':
        if act.actuator_mode != 'NONE' or act.use_world_property:
            raise Unsupported("property actuator %s" % act.actuator_mode)
        p = act.property
        m = act.mode
        pa = _act_arg("Property", p)
        if m == 'ASSIGN':
            return ["ob[%s] = %s" % (pa, _lit_arg(ob, p, act.value, _ACT_LABEL[0] + " Value"))], False
        if m == 'ADD':
            return ["ob[%s] = ob.get(%s, 0) + %s" % (pa, pa, _lit_arg(ob, p, act.value,
                                                                    _ACT_LABEL[0] + " Value"))], False
        if m == 'TOGGLE':
            if _game_prop_type(ob, p) == 'BOOL':
                return ["ob[%s] = not ob.get(%s, False)" % (pa, pa)], False
            return ["ob[%s] = 0 if ob.get(%s, 0) else 1" % (pa, pa)], False
        if m == 'COPY':
            if act.object is None:
                raise Unsupported("property copy sem objeto")
            return ["ob[%s] = scene.objects[%r][%r]" % (pa, act.object.name, act.object_property)], False
        raise Unsupported("property actuator %s" % m)
    if t == 'STATE':
        mask = sum(1 << i for i, on in enumerate(act.states) if on)
        op = {
            'SET': "ob.state = %d",
            'ADD': "ob.state |= %d",
            'REMOVE': "ob.state &= ~%d",
            'CHANGE': "ob.state ^= %d",
        }[act.operation]
        return [op % mask], False
    if t == 'MESSAGE':
        if act.body_type == 'PROPERTY':
            body = "str(ob.get(%r, ''))" % act.body_property
        else:
            body = _act_arg("Body", act.body_message)
        return ["logic.sendMessage(%s, %s, %s)" % (_act_arg("Subject", act.subject), body,
                                                   _act_arg("To", act.to_property))], False
    if t == 'EDIT_OBJECT':
        if act.mode == 'TRACKTO':
            # Track To roda todo frame com o controller positivo (como a engine).
            return _track_to_code(act), True
        return _edit_object_code(act), False
    if t == 'SOUND':
        return _sound_code(act)
    if t == 'SCENE':
        return _scene_code(act), False
    if t == 'GAME':
        if act.mode == 'QUIT':
            return ["logic.endGame()"], False
        if act.mode == 'RESTART':
            return ["logic.restartGame()"], False
        if act.mode in {'START', 'LOAD'}:
            return ["logic.startGame(%s)" % _act_arg("File", act.filename)], False
        raise Unsupported("game %s" % act.mode)
    if t == 'CAMERA':
        if act.object is None:
            raise Unsupported("camera sem objeto")
        axis, neg = {'POS_X': (0, False), 'POS_Y': (1, False),
                     'NEG_X': (0, True), 'NEG_Y': (1, True)}[act.axis]
        # A engine atualiza todo frame com o controller positivo.
        return ["self._follow(%s, %s, %s, %s, %s, %d, %s)" %
                (_act_arg("Object", act.object.name), _act_arg("Height", act.height),
                 _act_arg("Min", act.min), _act_arg("Max", act.max),
                 _act_arg("Damping", act.damping), axis, neg)], True
    if t == 'VISIBILITY':
        return ["ob.setVisible(%s, %s)" % (_act_arg("Visible", act.use_visible), act.apply_to_children),
                "ob.setOcclusion(%s, %s)" % (_act_arg("Occlusion", act.use_occlusion),
                                             act.apply_to_children)], False
    if t == 'PARENT':
        if act.mode == 'REMOVEPARENT':
            return ["ob.removeParent()"], False
        if act.object is None:
            raise Unsupported("parent sem objeto")
        return ["_p = scene.objects.get(%s)" % _act_arg("Object", act.object.name),
                "if _p is not None:",
                "    ob.setParent(_p, %s, %s)" % (_act_arg("Compound", act.use_compound),
                                                  _act_arg("Ghost", act.use_ghost))], False
    if t == 'RANDOM':
        return _random_act_code(act), False
    if t == 'MOUSE':
        if act.mode == 'VISIBILITY':
            return ["logic.mouse.visible = %s" % _act_arg("Visible", act.visible)], False
        axes = {'OBJECT_AXIS_X': 0, 'OBJECT_AXIS_Y': 1, 'OBJECT_AXIS_Z': 2}
        cfg = []
        for c in "xy":
            C = c.upper()
            cfg.append("(%s, %s, %s, %s, %d, %s, %s, %s)" % (
                _act_arg("Use " + C, getattr(act, "use_axis_" + c)),
                _act_arg("Reset " + C, getattr(act, "reset_" + c)),
                _act_arg("Local " + C, getattr(act, "local_" + c)),
                _act_arg("Threshold " + C, getattr(act, "threshold_" + c)),
                axes[getattr(act, "object_axis_" + c)],
                _act_arg("Sensitivity " + C, getattr(act, "sensitivity_" + c)),
                _act_arg("Min " + C, getattr(act, "min_" + c)),
                _act_arg("Max " + C, getattr(act, "max_" + c))))
        # Continuo com o controller positivo; o pulso negativo refaz o salto inicial.
        return (["self._mouse_look(%r, (%s))" % (act.name, ", ".join(cfg))], True,
                ["self._ticks.pop(%r, None)" % ("mlk:" + act.name)])
    if t == 'CONSTRAINT':
        return _constraint_code(ob, act)
    if t == 'STEERING':
        return _steering_code(ob, act)
    raise Unsupported("actuator %s" % t)


def _constraint_code(ob, act):
    # KX_ConstraintActuator: continuo ate falhar (raio sem acerto) ou esgotar Time frames.
    A = _act_arg
    m = act.mode
    if m == 'LOC':
        if act.limit == 'NONE':
            raise Unsupported("constraint loc sem eixo")
        call = "self._cst_loc(%d, %s, %s, %s)" % ({'LOCX': 0, 'LOCY': 1, 'LOCZ': 2}[act.limit],
                                                A("Min", act.limit_min), A("Max", act.limit_max),
                                                A("Damping", act.damping))
    elif m == 'ORI':
        if act.direction_axis_pos == 'NONE':
            raise Unsupported("constraint orientacao sem eixo")
        if not _nonzero(act.rotation_max):
            raise Unsupported("constraint orientacao sem direcao de referencia")
        call = "self._cst_ori(%d, %s, %s, %s, %s)" % (_DIR_AXES[act.direction_axis_pos][0],
                                                    A("Reference", act.rotation_max),
                                                    A("Min Angle", act.angle_min), A("Max Angle", act.angle_max),
                                                    A("Damping", act.damping))
    elif m in {'DIST', 'FH'}:
        mode = act.direction if m == 'DIST' else act.direction_axis
        if mode == 'NONE':
            raise Unsupported("constraint %s sem eixo" % m.lower())
        axis, neg = _DIR_AXES[mode]
        mat = act.use_material_detect
        prop = A("Material", act.material) if mat else A("Property", act.property)
        dyn = ob.game.physics_type in _DYNAMIC
        if m == 'DIST':
            call = "self._cst_dist(%d, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)" % (
                axis, neg, A("Local", act.use_local), A("Normal", act.use_normal),
                A("Force Distance", act.use_force_distance), A("Persistent", act.use_persistent),
                mat, prop, A("Distance", act.distance), A("Range", act.range), A("Damping", act.damping),
                A("Rot Damping", act.damping_rotation), dyn)
        else:
            if not dyn:
                raise Unsupported("constraint fh em objeto nao dinamico")
            call = "self._cst_fh(%d, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %r)" % (
                axis, neg, A("Height", act.fh_height), A("Force", act.fh_force), A("Fh Damping", act.fh_damping),
                A("Rot Fh Damping", act.rotation_max[1]), A("Normal", act.use_fh_normal),
                A("Rot Fh", act.use_fh_paralel_axis), A("Persistent", act.use_persistent), mat, prop,
                ob.game.radius)
    else:
        raise Unsupported("constraint %s" % m)
    key = "cst:" + act.name
    _ACT_STATE[0] = "%r in self._ticks" % key
    return (["self._cst(%r, %s, %s, lambda: %s)" % (key, _FIRE, A("Time", act.time), call)], True,
            ["self._ticks.pop(%r, None)" % key])


def _steering_code(ob, act):
    # KX_SteeringActuator sem simulacao de obstaculos (nao exposta em Python).
    A = _act_arg
    if act.target is None:
        raise Unsupported("steering sem alvo")
    if act.normal_up:
        raise Unsupported("steering com normal up")
    if ob.game.use_obstacle_create and any(sc.game_settings.obstacle_simulation != 'NONE'
                                           for sc in ob.users_scene):
        raise Unsupported("steering com simulacao de obstaculos")
    mode = ['SEEK', 'FLEE', 'PATHFOLLOWING'].index(act.mode)
    navmesh = act.navmesh.name if act.navmesh and act.navmesh.game.physics_type == 'NAVMESH' else None
    if mode == 2 and navmesh is None:
        raise Unsupported("steering path following sem navmesh")
    facing = ['X', 'Y', 'Z', 'NEG_X', 'NEG_Y', 'NEG_Z'].index(act.facing_axis) + 1 if act.facing else 0
    key = "str:" + act.name
    _ACT_STATE[0] = "%r in self._ticks" % key
    call = "self._steer(%r, %s, %d, %s, %s, %s, %s, %s, %s, %d, %s, %s, %s)" % (
        key, _FIRE, mode, A("Target", act.target.name), A("Navmesh", navmesh) if navmesh else None,
        A("Distance", act.distance), A("Velocity", act.velocity), A("Update Period", act.update_period),
        A("Self Terminated", act.self_terminated), facing, ob.game.physics_type in _DYNAMIC,
        A("Lock Z Velocity", act.lock_z_velocity), A("Visualize", act.show_visualization))
    return [call], True, ["self._ticks.pop(%r, None)" % key]


def _random_act_code(act):
    # Mesmas distribuicoes de SCA_RandomActuator, com o gerador do Python (sequencia diferente).
    if not act.property:
        raise Unsupported("random sem propriedade")
    d = act.distribution
    A = _act_arg
    gen = "self._rng(%r, %s)" % (act.name, A("Seed", act.seed))
    if d == 'BOOL_CONSTANT':
        val = A("Value", act.use_always_true)
    elif d == 'BOOL_UNIFORM':
        val = "%s.random() < 0.5" % gen
    elif d == 'BOOL_BERNOUILLI':
        val = "%s.random() < %s" % (gen, A("Chance", act.chance))
    elif d == 'INT_CONSTANT':
        val = A("Value", act.int_value)
    elif d == 'INT_UNIFORM':
        val = "%s.randint(%s, %s)" % (gen, A("Min", act.int_min), A("Max", act.int_max))
    elif d == 'INT_POISSON':
        val = "self._poisson(%s, %s)" % (gen, A("Mean", act.int_mean))
    elif d == 'FLOAT_CONSTANT':
        val = A("Value", act.float_value)
    elif d == 'FLOAT_UNIFORM':
        val = "%s.uniform(%s, %s)" % (gen, A("Min", act.float_min), A("Max", act.float_max))
    elif d == 'FLOAT_NORMAL':
        # Seed 0 devolve a media, como na engine.
        mean = A("Mean", act.float_mean)
        val = "(%s.gauss(%s, %s) if %s else %s)" % (gen, mean, A("Deviation", act.standard_derivation),
                                                   A("Seed", act.seed), mean)
    elif d == 'FLOAT_NEGATIVE_EXPONENTIAL':
        val = "%s * -math.log(1.0 - %s.random())" % (A("Half Life", act.half_life_time), gen)
    else:
        raise Unsupported("random %s" % d)
    return ["ob[%s] = %s" % (A("Property", act.property), val)]


_DYNAMICS = {
    'RESTOREDYN': "ob.restoreDynamics()",
    'SUSPENDDYN': "ob.suspendDynamics()",
    'ENABLERIGIDBODY': "ob.enableRigidBody()",
    'DISABLERIGIDBODY': "ob.disableRigidBody()",
    'RESTOREPHY': "ob.restorePhysics()",
    'SUSPENDPHY': "ob.suspendPhysics()",
}


def _edit_object_code(act):
    m = act.mode
    if m == 'ADDOBJECT':
        if act.object is None or act.use_object_from_property:
            raise Unsupported("add object sem objeto fixo")
        lines = ["new = scene.addObject(%s, ob, %s)" % (_act_arg("Object", act.object.name),
                                                        _act_arg("Time", act.time))]
        if _nonzero(act.linear_velocity):
            lines.append("new.setLinearVelocity(%s, %s)" % (_act_arg("Linear Velocity", act.linear_velocity),
                                                            act.use_local_linear_velocity))
        if _nonzero(act.angular_velocity):
            lines.append("new.setAngularVelocity(%s, %s)" % (_act_arg("Angular Velocity", act.angular_velocity),
                                                             act.use_local_angular_velocity))
        return lines
    if m == 'ENDOBJECT':
        return ["ob.endObject()"]
    if m == 'REPLACEMESH':
        if act.mesh is None:
            raise Unsupported("replace mesh sem malha")
        return ["ob.replaceMesh(%s, %s, %s)" % (_act_arg("Mesh", act.mesh.name), act.use_replace_display_mesh,
                                               act.use_replace_physics_mesh)]
    if m == 'DYNAMICS':
        op = act.dynamic_operation
        if op == 'SETMASS':
            return ["ob.mass = %s" % _act_arg("Mass", act.mass)]
        return [_DYNAMICS[op]]
    raise Unsupported("edit object %s" % m)


def _scene_code(act):
    m = act.mode
    name = act.scene.name if act.scene else None
    if m == 'RESTART':
        return ["scene.restart()"]
    if m == 'CAMERA':
        if act.camera is None:
            raise Unsupported("scene camera sem camera")
        return ["scene.active_camera = scene.objects[%r]" % act.camera.name]
    if name is None:
        raise Unsupported("scene %s sem cena" % m)
    name = _act_arg("Scene", name)
    if m == 'SET':
        return ["scene.replace(%s)" % name]
    if m in {'ADDFRONT', 'ADDBACK'}:
        return ["logic.addScene(%s, %d)" % (name, m == 'ADDFRONT')]
    method = {'REMOVE': "end", 'SUSPEND': "suspend", 'RESUME': "resume"}[m]
    return ["for sc in logic.getSceneList():",
            "    if sc.name == %s:" % name,
            "        sc.%s()" % method]


_TRACK_AXES = {
    'TRACKAXISX': (0, ""), 'TRACKAXISY': (1, ""), 'TRACKAXISZ': (2, ""),
    'TRACKAXISNEGX': (0, "-"), 'TRACKAXISNEGY': (1, "-"), 'TRACKAXISNEGZ': (2, "-"),
}


def _track_to_code(act):
    if act.object is None:
        raise Unsupported("track to sem objeto fixo")
    axis, sign = _TRACK_AXES[act.track_axis]
    up = {'UPAXISX': 0, 'UPAXISY': 1, 'UPAXISZ': 2}[act.up_axis]
    if axis == up:
        raise Unsupported("track to com eixo de track igual ao up")
    # KX_TrackToActuator: orientacao = (antiga * time + nova) / (time + 1).
    factor = 1.0 / (act.time + 1) if act.time > 0 else 1.0
    lines = ["tgt = scene.objects.get(%s)" % _act_arg("Object", act.object.name),
             "if tgt is not None:",
             "    vec = tgt.worldPosition - ob.worldPosition"]
    if not act.use_3d_tracking:
        lines.append("    vec.z = 0.0")
    lines += ["    if vec.length > 1e-6:",
              "        ob.alignAxisToVect((0.0, 0.0, 1.0), %d, 1.0)" % up,
              "        ob.alignAxisToVect(%svec, %d, %g)" % (sign, axis, factor)]
    return lines


def _sound_code(act):
    # Mesmo fluxo de KX_SoundActuator: o pulso positivo toca se nao estiver tocando;
    # o negativo para (modos *STOP) ou deixa a volta atual terminar (LOOPEND).
    if act.mode not in {'PLAYSTOP', 'PLAYEND', 'LOOPSTOP', 'LOOPEND'}:
        raise Unsupported("sound %s" % act.mode)
    if act.sound is None:
        raise Unsupported("sound sem som")
    if act.sound.packed_file is not None:
        raise Unsupported("sound empacotado")
    if act.use_sound_3d:
        raise Unsupported("sound 3D")
    key = act.name
    on = ["import aud",
          "snd = self.__dict__.setdefault('_snd', {})",
          "h = snd.get(%r)" % key,
          "if h is None or h.status != aud.STATUS_PLAYING:",
          "    h = aud.Device().play(aud.Sound.file(logic.expandPath(%r)))" % act.sound.filepath,
          "    h.volume = %s" % _act_arg("Volume", act.volume),
          "    h.pitch = %s" % _act_arg("Pitch", act.pitch)]
    if act.mode.startswith('LOOP'):
        on.append("    h.loop_count = -1")
    on.append("    snd[%r] = h" % key)
    off = []
    if act.mode != 'PLAYEND':
        off = ["import aud",
               "h = self.__dict__.get('_snd', {}).get(%r)" % key,
               "if h is not None and h.status == aud.STATUS_PLAYING:"]
        off.append("    h.loop_count = 0" if act.mode == 'LOOPEND' else "    h.stop()")
    return on, False, off


# ---------------------------------------------------------------------------

_HEADER = '''\
# Gerado por "Logic Bricks -> Python Component" a partir do objeto %(obname)r.
# Cada bloco corresponde a um controller; o comentario traz o nome original.

from Range import logic, events, types
from mathutils import Matrix, Vector
from collections import OrderedDict
import math
import random


class %(classname)s(%(base)s):
    args = OrderedDict([
%(args)s    ])

    def start(self, args):
%(args_start)s        self._prev = {}
        self._dbg = {}
        self._ticks = {}
        self._hits = []
        self._act_on = {}
%(start_extra)s%(extra)s
    def _rise(self, key, value):
        """Pulso positivo: True so no frame em que value passa a True."""
        prev = self._prev.get(key, False)
        self._prev[key] = value
        return value and not prev

    def _fall(self, key, value):
        """Pulso negativo: True so no frame em que value volta a False."""
        key = "fall:" + key
        prev = self._prev.get(key, False)
        self._prev[key] = value
        return prev and not value

    def _changed(self, key, value):
        key = "chg:" + key
        changed = key in self._prev and self._prev[key] != value
        self._prev[key] = value
        return changed

    def _on_hit(self, other, *_args):
        self._hits.append(other)

    def _near(self, key, prop, dist, reset):
        """Near sensor com histerese: depois de detectar, so solta alem de reset."""
        key = "near:" + key
        limit = reset if self._prev.get(key) else dist
        ob = self.object
        found = any(o is not ob and (not prop or prop in o) and ob.getDistanceTo(o) <= limit
                    for o in ob.scene.objects)
        self._prev[key] = found
        return found

    def _radar(self, axis, prop, dist, half_angle):
        ob = self.object
        for o in ob.scene.objects:
            if o is ob or (prop and prop not in o):
                continue
            d, vec, _local = ob.getVectTo(o)
            if 0 < d <= dist and axis.angle(vec) <= half_angle:
                return True
        return False

    def _has_mat(self, o, name):
        """Mesmo teste de RAS_Mesh::FindMaterialName (nome sem o prefixo MA)."""
        return o is not None and any(m.getMaterialName(i)[2:] == name
                                     for m in o.meshes for i in range(m.numMaterials))

    def _mouse_hit(self, prop):
        cam = self.object.scene.active_camera
        x, y = logic.mouse.position
        return cam.getScreenRay(x, y, 10000.0, prop) if cam else None

    def _delay(self, key, delay, duration, repeat, times):
        """Mesma contagem de SCA_DelaySensor (em frames)."""
        key = "dly:" + key
        n, left = self._ticks.get(key, (0, times))
        if n < delay:
            n += 1
            on = False
        elif duration > 0 and n < delay + duration:
            n += 1
            on = True
        else:
            on = duration == 0
            if repeat or left > 1:
                n = 0
                if left > 1:
                    left -= 1
        self._ticks[key] = (n, left)
        return on

    def _random(self, key, seed, skip):
        """Random sensor: sorteia um bool a cada skip + 1 frames e mantem entre sorteios."""
        key = "rnd:" + key
        gen, n, value = self._ticks.get(key) or (random.Random(seed or None), skip, False)
        n += 1
        if n > skip:
            n = 0
            value = gen.random() < 0.5
        self._ticks[key] = (gen, n, value)
        return value

    def _moved(self, key, local, axis, sign, threshold):
        """Movement sensor: compara com a posicao do frame anterior (KX_MovementSensor)."""
        ob = self.object
        if local:
            pos = ob.localOrientation.inverted() * ob.localPosition
        else:
            pos = ob.worldPosition.copy()
        key = "mov:" + key
        prev = self._prev.get(key, pos)
        self._prev[key] = pos
        d = pos - prev
        if axis < 0:
            return any(abs(v) > threshold for v in d)
        return d[axis] * sign > threshold

    def _joy(self, index):
        """(eixos -1..1, botoes apertados) do joystick; sem joystick, tudo solto."""
        js = logic.joysticks[index] if 0 <= index < len(logic.joysticks) else None
        if js is None:
            return [0.0] * 6, []
        return list(js.axisValues) + [0.0] * 6, js.activeButtons

    def _rng(self, key, seed):
        key = "rng:" + key
        gen = self._ticks.get(key)
        if gen is None:
            gen = self._ticks[key] = random.Random(seed)
        return gen

    @staticmethod
    def _poisson(gen, mean):
        a = max(math.exp(-mean), 1e-38)
        b, n = gen.random(), 0
        while b >= a:
            b *= gen.random()
            n += 1
        return n

    def _mouse_look(self, key, axes):
        """Mouse actuator Look (KX_MouseActuator): gira o objeto e recentraliza o cursor."""
        from Range import render
        ob = self.object
        pos = list(logic.mouse.position)
        center = [0.5, 0.5]
        for i, size in enumerate((render.getWindowWidth(), render.getWindowHeight())):
            if size %% 2 == 0 and size > 1:
                center[i] = float((size - 1) // 2) / (size - 1)
        key = "mlk:" + key
        st = self._ticks.get(key)
        if st is None:
            # Primeiro frame: so posiciona o cursor (evita o salto inicial).
            old = [center[i] if axes[i][1] else pos[i] for i in range(2)]
            self._ticks[key] = {"old": old, "angle": [0.0, 0.0]}
            logic.mouse.position = tuple(old)
            return
        setpos = [0.0, 0.0]
        for i, (use, reset, local, thr, obaxis, sens, lo, hi) in enumerate(axes):
            if not use:
                setpos[i] = center[i]
                continue
            setpos[i] = center[i] if reset else pos[i]
            move = -(pos[i] - (center[i] if reset else st["old"][i]))
            if abs(move) > thr / 10.0:
                move *= sens
                ang = st["angle"][i]
                if lo != 0.0 and ang + move <= lo:
                    move = lo - ang
                if hi != 0.0 and ang + move >= hi:
                    move = hi - ang
                st["angle"][i] = ang + move
                rot = [0.0, 0.0, 0.0]
                rot[obaxis] = move
                ob.applyRotation(rot, local)
        if st["old"] != pos:
            logic.mouse.position = tuple(setpos)
        st["old"] = pos

    def _follow(self, target, height, dmin, dmax, damping, axis, neg):
        """Mesma conta de KX_CameraActuator: fica atras do alvo e olha para ele."""
        ob = self.object
        tgt = ob.scene.objects.get(target)
        if tgt is None:
            return
        pos = ob.worldPosition.copy()
        look = tgt.worldPosition
        pos.z = (15.0 * pos.z + look.z + height) / 16.0
        fp1 = tgt.worldOrientation.col[axis] * (-1.0 if neg else 1.0)
        fp2 = ob.worldOrientation.col[axis]
        inp = fp1.dot(fp2)
        fac = (inp - 1.0) * damping
        pos += fac * fp1
        if inp < 0.0:
            cross = fp1.x * fp2.y - fp1.y * fp2.x
            if cross > 0.01:
                pos.x -= fac * fp1.y
                pos.y += fac * fp1.x
            elif cross < -0.01:
                pos.x += fac * fp1.y
                pos.y -= fac * fp1.x
        rc = look - pos
        dist = rc.length_squared
        if dist > dmax * dmax:
            pos += 0.15 * (dist - dmax * dmax) / dist * rc
        elif dist < dmin * dmin:
            pos -= 0.15 * (dmin * dmin - dist) / (dmin * dmin) * rc
        # Eixo -Z aponta para o alvo, Y para cima (Kx_VecUpMat3 com axis 3).
        z = pos - look
        z = z.normalized() if z.length > 0.0 else Vector((1.0, 0.0, 0.0))
        y = Vector((-z.z * z.x, -z.z * z.y, 1.0 - z.z * z.z))
        y = y.normalized() if y.length > 0.0 else Vector((0.0, 1.0, 0.0))
        ob.localPosition = pos
        ob.localOrientation = Matrix((y.cross(z), y, z)).transposed()

    def _debug(self, name, value):
        """Com o arg Debug ligado, imprime quando sensor/controller muda de valor."""
        if self._dbg.get(name) != value:
            self._dbg[name] = value
            print("[%%s] %%s = %%s" %% (self.object.name, name, value))

    @staticmethod
    def _event(name, default):
        """Nome de tecla dos args ('D', 'SPACE', 'LEFTARROW') -> constante de events."""
        name = str(name).strip().upper().replace(" ", "")
        for n in (name, name + "KEY", default, default + "KEY"):
            if hasattr(events, n):
                return getattr(events, n)
        raise ValueError("tecla invalida: %%r" %% name)

    def _tick(self, key, skip):
        """Pulso repetido (True level) a cada skip + 1 frames."""
        n = self._ticks.get(key, 0)
        self._ticks[key] = (n + 1) %% (skip + 1)
        return n == 0

    def update(self):
        ob = self.object
        scene = ob.scene
        kb = logic.keyboard.inputs
        ms = logic.mouse.inputs
        # Troca de estado so vale no proximo frame, como nos logic bricks.
        state = ob.state
'''


_EXTRA = OrderedDict()
_EXTRA["_anim_event"] = '''
    def _anim_event(self, key, index, trigger):
        """Animation Event sensor: positivo no frame em que o gatilho disparou (-1 = qualquer)."""
        mgr = self.object.animationEventManager
        evs = mgr.events if mgr is not None else []
        if not 0 <= index < len(evs):
            return False
        n = evs[index].getFireCount(trigger)
        key = "aev:" + key
        fired = key in self._prev and self._prev[key] != n
        self._prev[key] = n
        return fired
'''
_EXTRA["_cst"] = '''
    def _cst(self, key, fire, time, apply):
        """Constraint actuator: roda ate apply() falhar ou passar de time frames (0 = sem limite)."""
        if fire and key not in self._ticks:
            self._ticks[key] = 0
        n = self._ticks.get(key)
        if n is None:
            return
        ok = apply()
        if ok and time > 0:
            n += 1
            ok = n < time
        if ok:
            self._ticks[key] = n
        else:
            self._ticks.pop(key, None)

    def _cst_loc(self, axis, lo, hi, damp):
        ob = self.object
        pos = ob.localPosition.copy()
        new = pos.copy()
        new[axis] = lo if new[axis] < lo else (hi if new[axis] > hi else new[axis])
        if damp:
            f = damp / (1.0 + damp)
            new = f * pos + (1.0 - f) * new
        ob.localPosition = new
        return True

    def _cst_ori(self, axis, ref, amin, amax, damp):
        ob = self.object
        ref = Vector(ref).normalized()
        cmin, cmax = math.cos(amin), math.cos(amax)
        f = damp / (1.0 + damp) if damp else 0.0
        direction = ob.worldOrientation.col[axis].copy()
        eps = 1.1920929e-07
        if cmax < 1.0 - eps or cmin < 1.0 - eps:
            c = direction.dot(ref)
            if cmax - eps <= c <= cmin + eps:
                return True
            z = ref.cross(direction)
            if z.length_squared < 1e-12:
                z = ref.cross(Vector((1.0, 0.0, 0.0)) if direction[0] < 0.9999 else Vector((0.0, 1.0, 0.0)))
            y = z.cross(ref).normalized()
            if c > cmin:
                ref = cmin * ref + math.sin(amin) * y
            else:
                ref = cmax * ref + math.sin(amax) * y
        ob.alignAxisToVect(f * direction + (1.0 - f) * ref, axis, 1.0)
        return True

    def _cst_ray(self, to, prop, material):
        """Primeiro objeto no raio; precisa ter a propriedade/material (sem x-ray)."""
        ob = self.object
        hit, point, normal = ob.rayCast(to, ob.worldPosition, 0, "" if material else prop, 1, 0, 0)
        if hit is not None and material and prop and not self._has_mat(hit, prop):
            hit = None
        return hit, point, normal

    def _cst_dist(self, axis, neg, local, use_normal, use_dist, persistent, material, prop,
                  dmin, dmax, damp, rotdamp, dyn):
        ob = self.object
        pos = ob.worldPosition.copy()
        normal = ob.worldOrientation.col[axis].normalized() * (-1.0 if neg else 1.0)
        if local:
            direction = normal.copy()
        else:
            direction = Vector((0.0, 0.0, 0.0))
            direction[axis] = -1.0 if neg else 1.0
        f = damp / (1.0 + damp) if damp else 0.0
        hit, point, hitnormal = self._cst_ray(pos + dmax * direction, prop, material)
        if hit is None:
            return persistent
        if not (use_normal or use_dist):
            return True
        if use_normal:
            rf = rotdamp / (1.0 + rotdamp) if rotdamp else f
            nn = rf * normal - (1.0 - rf) * Vector(hitnormal)
            ob.alignAxisToVect(-nn if neg else nn, axis, 1.0)
            if local:
                direction = nn.normalized()
        point = Vector(point)
        if use_dist:
            dist = f * (pos - point).length + (1.0 - f) * dmin if damp else dmin
            if dyn:
                # Cancela a velocidade na direcao do raio, ja que a posicao e fixada nela.
                vel = ob.worldLinearVelocity
                fall = vel.dot(direction)
                if abs(fall) > 1e-6:
                    ob.worldLinearVelocity = vel - fall * direction
        else:
            dist = (pos - point).length
        ob.worldPosition = point - dist * direction
        return True

    def _cst_fh(self, axis, neg, height, force, damp, rotdamp, use_normal, use_rot, persistent,
                material, prop, radius):
        ob = self.object
        pos = ob.worldPosition.copy()
        sign = -1.0 if neg else 1.0
        normal = -sign * ob.worldOrientation.col[axis].normalized()
        direction = Vector((0.0, 0.0, 0.0))
        direction[axis] = sign
        hit, point, hitnormal = self._cst_ray(pos + (height + radius) * direction, prop, material)
        if hit is None:
            return persistent
        point, hitnormal = Vector(point), Vector(hitnormal)
        dist = (point - pos).length - radius
        vel = ob.worldLinearVelocity
        rel = vel - hit.getVelocity(point - hit.worldPosition)
        spring = (1.0 - dist / height) * force
        push = spring + direction.dot(rel) * damp
        vel = vel - push * direction
        if use_normal:
            vel += push * (hitnormal - hitnormal.dot(direction) * direction)
        ob.worldLinearVelocity = vel
        if use_rot:
            ang = ob.worldAngularVelocity
            flat = ang - ang.dot(hitnormal) * hitnormal
            rd = damp if abs(rotdamp) < 1e-6 else rotdamp
            ob.worldAngularVelocity = ang + (normal.cross(hitnormal) * force - flat * rd)
        return True
'''
_EXTRA["_steer"] = '''
    def _steer(self, key, fire, mode, target, navmesh, dist, speed, period, self_term, facing, dyn,
               lock_z, show):
        """Steering actuator (KX_SteeringActuator): 0 seek, 1 flee, 2 path following."""
        now = logic.getFrameTime()
        st = self._ticks.get(key)
        if st is None:
            # Ativacao: so marca o tempo; o movimento comeca no proximo frame.
            if fire:
                parent = self.object.parent
                self._ticks[key] = {"t": now, "pt": -1.0, "path": [], "wp": -1,
                                    "plm": parent.localOrientation.copy() if parent else None}
            return
        delta = now - st["t"]
        st["t"] = now
        if not delta:
            return
        ob = self.object
        tgt = ob.scene.objects.get(target)
        if tgt is None:
            self._ticks.pop(key, None)
            return
        pos = ob.worldPosition.copy()
        to = tgt.worldPosition - pos
        steer = None
        done = True
        if mode == 0 and to.xy.length_squared > dist * dist:
            done, steer = False, to.normalized()
        elif mode == 1 and to.xy.length_squared < dist * dist:
            done, steer = False, -to.normalized()
        elif mode == 2:
            nm = ob.scene.objects.get(navmesh)
            if nm is not None and to.length_squared > dist * dist:
                done = False
                if st["pt"] < 0 or (period >= 0 and now - st["pt"] > period / 1000.0):
                    st["pt"] = now
                    st["path"] = [Vector(p) for p in nm.findPath(pos, tgt.worldPosition)]
                    st["wp"] = 1 if len(st["path"]) > 1 else -1
                path, wp = st["path"], st["wp"]
                if wp > 0:
                    point = path[wp]
                    if (point - pos).length_squared < 0.25 * 0.25:
                        wp += 1
                        if wp >= len(path):
                            wp, done = -1, True
                        else:
                            point = path[wp]
                    st["wp"] = wp
                    steer = point - pos
                    if show:
                        from Range import render
                        for a, b in zip(path, path[1:]):
                            render.drawLine(a, b, (1.0, 0.0, 0.0))
        if steer is not None:
            if dyn or mode == 2:
                steer.z = 0.0
            if steer.length > 1e-6:
                steer.normalize()
            vel = speed * steer
            if facing:
                self._steer_face(st, facing, vel)
            if dyn:
                vel.z = 0.0 if lock_z else ob.worldLinearVelocity.z
                ob.worldLinearVelocity = vel
            else:
                ob.applyMovement(delta * vel, False)
        if done and self_term:
            self._ticks.pop(key, None)

    def _steer_face(self, st, facing, vel):
        """Aponta o eixo escolhido (1 X, 2 Y, 3 Z, 4-6 negativos) na direcao do movimento."""
        if vel.length < 1e-6:
            return
        safe = lambda v: v.normalized() if v.length > 1e-6 else Vector((1.0, 0.0, 0.0))
        d = vel.normalized()
        up = Vector((0.0, 0.0, 1.0))
        if facing == 1:
            left = d
            d = -safe(left.cross(up))
        elif facing == 2:
            left = safe(d.cross(up))
        elif facing == 3:
            left, up = up, d
            d = left
            left = safe(d.cross(up))
        elif facing == 4:
            left = -d
            d = -safe(left.cross(up))
        elif facing == 5:
            left = safe(-d.cross(up))
            d = -d
        else:
            left, up = up, -d
            d = left
            left = safe(d.cross(up))
        mat = Matrix((left, d, up)).transposed()
        ob = self.object
        if ob.parent is not None:
            pos = ob.localPosition.copy()
            ob.localOrientation = st["plm"] * ob.parent.worldOrientation.inverted() * mat
            ob.localPosition = pos
        else:
            ob.localOrientation = mat
'''


_RUNNER = '''

# Modo controller: um sensor Always (pulso continuo) liga um controller Python
# "LC_state_<n>" por estado usado. So o de menor estado ativo roda no frame.
_inst = {}


def main(cont):
    ob = cont.owner
    bit = 1 << (int(cont.name.rsplit("_", 1)[1]) - 1)
    if ob.state & (bit - 1) & %(mask)d:
        return
    inst = _inst.get(ob)
    if inst is None:
        for dead in [o for o in _inst if o.invalid]:
            del _inst[dead]
        inst = _inst[ob] = %(classname)s()
        inst.object = ob
        inst.start({})
    inst.update()
'''


def _args_source():
    # Um cabecalho C_Header por brick (bool que abre/fecha a secao no painel).
    groups = []
    for a in _ARGS:
        if a[3] not in groups:
            groups.append(a[3])
    lines = ["        ('C_Header/Logic/LOGIC', True),\n", "        ('Debug', False),\n"]
    for g in groups:
        if g:
            header = "C_Header/%s" % g.replace("/", "-")
            if g in _GROUP_ICON:
                header += "/" + _GROUP_ICON[g]
            lines.append("        (%r, True),\n" % header[:63])
        lines += ["        (%r, %s),\n" % (a[0], a[1]) for a in _ARGS if a[3] == g]
    return "".join(lines)


def _args_start():
    lines = ["        self._debug_on = args.get('Debug', False)\n", "        self._a = [\n"]
    for name, src, kind, _group in _ARGS:
        get = "args.get(%r, %s)" % (name, src)
        if kind == "key":
            get = "self._event(%s, %s)" % (get, src)
        lines.append("            %s,\n" % get)
    lines.append("        ]\n")
    return "".join(lines)


def convert_object(ob, classname, component=True, _skip=frozenset()):
    """Retorna (codigo, controllers convertidos, lista de pendencias)."""
    converted = []
    act_refs = {}  # controller -> actuators lidos por sensores Actuator
    watched = {s.actuator for s in ob.game.sensors if s.type == 'ACTUATOR'}
    todos = []
    sensor_exprs = {}  # nome da variavel -> (expressao, nome original); cada sensor avaliado uma vez
    sensor_masks = {}
    _GROUP[0] = ""
    _GROUP_ICON.clear()
    del _ARGS[:]  # nome da variavel -> estados dos controllers ligados
    plans = []

    foreign = {}  # objeto de outro dono -> variavel local no update()

    def on(owner, lines_or_expr):
        """Reescreve 'ob' para o objeto dono do brick (links entre objetos)."""
        if owner == ob:
            return lines_or_expr
        var = foreign.setdefault(owner.name, _ident(owner.name, "o"))
        sub = lambda text: re.sub(r"\bob\b", var, text)
        if isinstance(lines_or_expr, str):
            return sub(lines_or_expr)
        return [sub(line) for line in lines_or_expr]

    for cont in ob.game.controllers:
        if cont.name in _skip:
            todos.append("%s: sensor Actuator le um actuator nao convertido" % cont.name)
            continue
        try:
            sensors = [(o, s) for o in bpy.data.objects for s in o.game.sensors
                       if _owns(s.controllers, cont)]
            exprs = {}
            sensor_vars = {}
            pulse = []
            for owner, s in sensors:
                if owner == ob:
                    var, key = _ident(s.name, "s"), s.name
                    expr = _sensor_expr(ob, s)
                    if s.type == 'ACTUATOR':
                        act_refs.setdefault(cont.name, []).append(s.actuator)
                else:
                    var, key = _ident(owner.name + "_" + s.name, "s"), owner.name + "/" + s.name
                    expr = _sensor_expr(owner, s, key)
                    # Helpers que usam self.object so valem para o proprio objeto.
                    if re.search(r"hits|self\._(near|radar|act_on|anim_event)\b", expr):
                        raise Unsupported("sensor %s de %s ligado" % (s.type, owner.name))
                    expr = on(owner, expr)
                    expr = "%s is not None and (%s)" % (foreign[owner.name], expr)
                exprs[var] = (expr, s.name if owner == ob else "%s/%s" % (owner.name, s.name))
                sensor_vars[s.name] = var
                if s.use_pulse_true_level:
                    pulse.append("self._tick(%r, %d)" % (key, s.tick_skip))
                elif s.type == 'MESSAGE':
                    # A engine dispara todo frame com mensagem, para nao perder nenhuma.
                    pulse.append("True")
            cont_expr = _controller_expr(ob, cont, sensor_vars)
            actuators = []
            for a in cont.actuators:
                owner = ob if _owns(ob.game.actuators, a) else next(
                    o for o in bpy.data.objects if _owns(o.game.actuators, a))
                _ACT_LABEL[0] = a.name if owner == ob else "%s/%s" % (owner.name, a.name)
                _GROUP[0] = "Actuator " + _ACT_LABEL[0]
                if a.type == 'MESSAGE':
                    _GROUP_ICON[_GROUP[0]] = 'FILE_TEXT'
                _ACT_STATE[0] = None
                code = _actuator_code(owner, a)
                code = code + ((),) * (3 - len(code)) + (_ACT_STATE[0],)
                if owner != ob:
                    if any(re.search(r"self\.(?!_a\[)", line) for part in code[:1] + code[2:3] for line in part):
                        raise Unsupported("actuator %s de %s ligado" % (a.type, owner.name))
                    code = (on(owner, code[0]), code[1], on(owner, code[2]), code[3])
                actuators.append((a, owner, code))
        except Unsupported as ex:
            todos.append("%s: %s" % (cont.name, ex))
            continue
        sensor_exprs.update(exprs)
        for sname in exprs:
            sensor_masks[sname] = sensor_masks.get(sname, 0) | (1 << (cont.states - 1))
        plans.append((cont, cont_expr, pulse, actuators))
        converted.append(cont)

    # Sensor Actuator so funciona se o actuator lido tambem foi convertido.
    done_acts = {act.name for _c, _e, _p, acts in plans for act, owner, _code in acts if owner == ob}
    bad = {c for c, refs in act_refs.items() if any(r not in done_acts for r in refs)}
    if bad - _skip:
        return convert_object(ob, classname, component, _skip | bad)

    # Mesma ordem da engine: sensores, depois controllers, depois actuators.
    # Assim nenhum sensor enxerga uma mudanca feita por actuator no mesmo frame.
    uses_hits = any("hits" in expr for expr, _orig in sensor_exprs.values())
    start_extra = "        self.object.collisionCallbacks.append(self._on_hit)\n" if uses_hits else ""
    out = []
    for name, var in sorted(foreign.items()):
        # Bricks ligados de outro objeto: some se o objeto for removido.
        out.append("        %s = scene.objects.get(%r)" % (var, name))
    out.append("        # Sensores")
    if uses_hits:
        # Colisoes do passo de fisica anterior, como o Collision sensor.
        out.append("        hits, self._hits = self._hits, []")
    for sname, (expr, orig) in sensor_exprs.items():
        # Sensor so e avaliado com algum controller dele no estado ativo (Delay/Near contam certo).
        out.append("        %s = bool(state & %d) and (%s)  # sensor '%s'" %
                   (sname, sensor_masks[sname], expr, orig))

    out.append("\n        # Controllers (so rodam no estado deles)")
    for cont, cont_expr, pulse, actuators in plans:
        cname = _ident(cont.name, "c")
        one_shot = not all(code[1] and not any(_FIRE in line for line in code[0])
                           for _act, _owner, code in actuators)
        fire = "self._rise(%r, %s)" % (cont.name, cname)
        if pulse:
            fire = "%s or (%s and (%s))" % (fire, cname, " or ".join(pulse))
        out.append("        # controller '%s' (%s, estado %d)" % (cont.name, cont.type, cont.states))
        out.append("        %s = bool(state & %d) and (%s)" % (cname, 1 << (cont.states - 1), cont_expr))
        if one_shot:
            out.append("        %s_fire = %s" % (cname, fire))
        if any(code[2] for _act, _owner, code in actuators):
            out.append("        %s_off = self._fall(%r, %s)" % (cname, cont.name, cname))

    out.append("\n        if self._debug_on:")
    for sname, (_expr, orig) in sensor_exprs.items():
        out.append("            self._debug(%r, %s)" % ("sensor " + orig, sname))
    for cont, _expr, _pulse, _acts in plans:
        out.append("            self._debug(%r, %s)" % ("controller " + cont.name, _ident(cont.name, "c")))
    if not sensor_exprs and not plans:
        out.append("            pass")

    out.append("\n        # Actuators")
    if watched:
        out.append("        self._act_on = {}")
    for cont, _expr, _pulse, actuators in plans:
        cname = _ident(cont.name, "c")
        for act, owner, code in actuators:
            lines, continuous = code[:2]
            cond = cname if continuous else cname + "_fire"
            if owner != ob:
                cond += " and %s is not None" % foreign[owner.name]
            out.append("        if %s:  # actuator '%s' <- controller '%s'" % (cond, act.name, cont.name))
            out += ["            " + line.replace(_FIRE, cname + "_fire") for line in lines]
            if code[2]:
                off = cname + "_off"
                if owner != ob:
                    off += " and %s is not None" % foreign[owner.name]
                out.append("        if %s:  # pulso negativo de '%s'" % (off, act.name))
                out += ["            " + line for line in code[2]]
            if owner == ob and act.name in watched:
                # Estado lido pelos sensores Actuator no proximo frame.
                out.append("        if %s:" % (code[3] or cond))
                out.append("            self._act_on[%r] = True" % act.name)

    for todo in todos:
        out.append("        # TODO: controller %s (nao convertido, brick continua ativo)" % todo)

    if not component:
        mask = 0
        for cont in converted:
            mask |= 1 << (cont.states - 1)
        out.append(_RUNNER % {"classname": classname, "mask": mask})
    body = "\n".join(out)
    extra = "".join(text for name, text in _EXTRA.items() if "self.%s(" % name in body)
    header = _HEADER % {"obname": ob.name, "classname": classname, "start_extra": start_extra,
                        "base": "types.KX_PythonComponent" if component else "object",
                        "args": _args_source(), "args_start": _args_start(),
                        "extra": extra}
    return header + "\n" + body + "\n", converted, todos


def _class_name(obname):
    words = re.findall(r"[A-Za-z0-9]+", obname)
    name = "".join(w[:1].upper() + w[1:] for w in words) or "Object"
    if name[0].isdigit():
        name = "Ob" + name
    return name + "Logic"


class LOGIC_OT_convert_to_component(Operator):
    """Converte os logic bricks do objeto ativo num Python Component """ \
        """(bricks convertidos sao desativados, nao apagados)"""
    bl_idname = "logic.convert_to_component"
    bl_label = "Convert Logic Bricks to Python Component"
    bl_options = {'REGISTER', 'UNDO'}

    disable_originals: BoolProperty(
        name="Disable Converted Bricks",
        description="Desativa os bricks convertidos para nao rodarem junto com o componente",
        default=True,
    )
    mode: EnumProperty(
        name="Mode",
        items=(
            ('COMPONENT', "Python Component", "Registra um KX_PythonComponent no objeto"),
            ('MODULE', "Always + Python (Module)",
             "Sensor Always ligado a um controller Python em modo modulo (modulo.main)"),
            ('SCRIPT', "Always + Python (Script)",
             "Sensor Always ligado a um controller Python com um texto script que chama o modulo"),
        ),
        default='COMPONENT',
    )
    module_name: StringProperty(
        name="Module",
        description="Nome do texto .py gerado (vazio = <objeto>_logic)",
    )

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and len(ob.game.controllers) > 0

    def execute(self, context):
        ob = context.active_object
        module = self.module_name or re.sub(r"\W", "_", ob.name).lower() + "_logic"
        classname = _class_name(ob.name)

        component = self.mode == 'COMPONENT'
        code, converted, todos = convert_object(ob, classname, component)
        if not converted:
            self.report({'WARNING'}, "Nenhum controller suportado; nada convertido")
            return {'CANCELLED'}

        filename = module + ".py"
        text = bpy.data.texts.get(filename) or bpy.data.texts.new(filename)
        text.from_string(code)

        if not component:
            self._add_runner(ob, module, converted)

        import_name = "%s.%s" % (module, classname)
        already = any(c.module == module and c.name == classname for c in ob.game.components)
        if component and not already:
            ret = bpy.ops.logic.python_component_register(component_name=import_name)
            if 'FINISHED' not in ret:
                self.report({'ERROR'}, "Codigo gerado em %s, mas o registro do componente falhou" % filename)
                return {'CANCELLED'}

        if self.disable_originals:
            for cont in converted:
                cont.active = False
            # Sensor/actuator so e desativado se todos os controllers ligados foram convertidos;
            # os soltos do proprio objeto (sem controller) nao fazem nada e tambem saem.
            for s in (s for o in bpy.data.objects for s in o.game.sensors):
                links = list(s.controllers)
                if (links and all(_owns(converted, c) for c in links)) or (not links and _owns(ob.game.sensors, s)):
                    s.active = False
            all_conts = [c for o in bpy.data.objects for c in o.game.controllers]
            for a in (a for o in bpy.data.objects for a in o.game.actuators):
                links = [c for c in all_conts if _owns(c.actuators, a)]
                if (links and all(_owns(converted, c) for c in links)) or (not links and _owns(ob.game.actuators, a)):
                    a.active = False

        msg = "%d controller(s) convertido(s) em %s" % (len(converted), filename)
        if todos:
            msg += "; %d pendente(s) (ver TODO no texto)" % len(todos)
            for t in todos:
                print("logic.convert_to_component: pendente -", t)
        self.report({'WARNING'} if todos else {'INFO'}, msg)
        return {'FINISHED'}

    def _add_runner(self, ob, module, converted):
        """Always (pulso continuo) + um controller Python LC_state_<n> por estado usado."""
        game = ob.game
        sens = next((s for s in game.sensors if s.name == "LC_always"), None)
        if sens is None:
            bpy.ops.logic.sensor_add(type='ALWAYS', name="LC_always", object=ob.name)
            sens = game.sensors[-1]
        sens.use_pulse_true_level = True
        sens.tick_skip = 0
        sens.active = True
        if self.mode == 'SCRIPT':
            name = module + "_run.py"
            runner = bpy.data.texts.get(name) or bpy.data.texts.new(name)
            runner.from_string("from Range import logic\nimport %s\n\n%s.main(logic.getCurrentController())\n"
                               % (module, module))
        for state in sorted(set(c.states for c in converted)):
            cname = "LC_state_%d" % state
            cont = next((c for c in game.controllers if c.name == cname), None)
            if cont is None:
                bpy.ops.logic.controller_add(type='PYTHON', name=cname, object=ob.name)
                cont = game.controllers[-1]
            cont.states = state
            cont.use_priority = True
            if self.mode == 'SCRIPT':
                cont.mode = 'SCRIPT'
                cont.text = runner
            else:
                cont.mode = 'MODULE'
                cont.module = module + ".main"
            cont.active = True
            sens.link(cont)


classes = (
    LOGIC_OT_convert_to_component,
)
