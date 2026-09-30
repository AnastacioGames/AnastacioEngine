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
}


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
    elif t == 'MESSAGE':
        # Mensagens enviadas no frame anterior para este objeto (ou sem destino), como o sensor.
        expr = "bool(logic.getMessages(ob.name, %s))" % A("Subject", sens.subject)
    else:
        raise Unsupported("sensor %s" % t)
    if sens.invert:
        expr = "not (%s)" % expr
    # Liga/desliga do sensor pelos args (desligado = sensor falso).
    return "%s and (%s)" % (A("Enabled", True), expr)


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
    raise Unsupported("actuator %s" % t)


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
import random


class %(classname)s(%(base)s):
    args = OrderedDict([
%(args)s    ])

    def start(self, args):
%(args_start)s        self._prev = {}
        self._dbg = {}
        self._ticks = {}
        self._hits = []
%(start_extra)s
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


def convert_object(ob, classname, component=True):
    """Retorna (codigo, controllers convertidos, lista de pendencias)."""
    converted = []
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
                else:
                    var, key = _ident(owner.name + "_" + s.name, "s"), owner.name + "/" + s.name
                    expr = _sensor_expr(owner, s, key)
                    # Helpers que usam self.object so valem para o proprio objeto.
                    if re.search(r"hits|self\._(near|radar)\b", expr):
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
                code = _actuator_code(owner, a)
                if owner != ob:
                    if any(re.search(r"self\.(?!_a\[)", line) for part in code[:1] + code[2:3] for line in part):
                        raise Unsupported("actuator %s de %s ligado" % (a.type, owner.name))
                    code = (on(owner, code[0]), code[1]) + tuple(on(owner, c) for c in code[2:])
                actuators.append((a, owner, code))
        except Unsupported as ex:
            todos.append("%s: %s" % (cont.name, ex))
            continue
        sensor_exprs.update(exprs)
        for sname in exprs:
            sensor_masks[sname] = sensor_masks.get(sname, 0) | (1 << (cont.states - 1))
        plans.append((cont, cont_expr, pulse, actuators))
        converted.append(cont)

    # Mesma ordem da engine: sensores, depois controllers, depois actuators.
    # Assim nenhum sensor enxerga uma mudanca feita por actuator no mesmo frame.
    uses_hits = any("hits" in expr for expr, _orig in sensor_exprs.values())
    start_extra = "        self.object.collisionCallbacks.append(self._on_hit)\n" if uses_hits else ""
    out = [_HEADER % {"obname": ob.name, "classname": classname, "start_extra": start_extra,
                      "base": "types.KX_PythonComponent" if component else "object",
                      "args": _args_source(), "args_start": _args_start()}]
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
        one_shot = not all(code[1] for _act, _owner, code in actuators)
        fire = "self._rise(%r, %s)" % (cont.name, cname)
        if pulse:
            fire = "%s or (%s and (%s))" % (fire, cname, " or ".join(pulse))
        out.append("        # controller '%s' (%s, estado %d)" % (cont.name, cont.type, cont.states))
        out.append("        %s = bool(state & %d) and (%s)" % (cname, 1 << (cont.states - 1), cont_expr))
        if one_shot:
            out.append("        %s_fire = %s" % (cname, fire))
        if any(code[2:] and code[2] for _act, _owner, code in actuators):
            out.append("        %s_off = self._fall(%r, %s)" % (cname, cont.name, cname))

    out.append("\n        if self._debug_on:")
    for sname, (_expr, orig) in sensor_exprs.items():
        out.append("            self._debug(%r, %s)" % ("sensor " + orig, sname))
    for cont, _expr, _pulse, _acts in plans:
        out.append("            self._debug(%r, %s)" % ("controller " + cont.name, _ident(cont.name, "c")))
    if not sensor_exprs and not plans:
        out.append("            pass")

    out.append("\n        # Actuators")
    for cont, _expr, _pulse, actuators in plans:
        cname = _ident(cont.name, "c")
        for act, owner, code in actuators:
            lines, continuous = code[:2]
            cond = cname if continuous else cname + "_fire"
            if owner != ob:
                cond += " and %s is not None" % foreign[owner.name]
            out.append("        if %s:  # actuator '%s' <- controller '%s'" % (cond, act.name, cont.name))
            out += ["            " + line for line in lines]
            if code[2:] and code[2]:
                off = cname + "_off"
                if owner != ob:
                    off += " and %s is not None" % foreign[owner.name]
                out.append("        if %s:  # pulso negativo de '%s'" % (off, act.name))
                out += ["            " + line for line in code[2]]

    for todo in todos:
        out.append("        # TODO: controller %s (nao convertido, brick continua ativo)" % todo)

    if not component:
        mask = 0
        for cont in converted:
            mask |= 1 << (cont.states - 1)
        out.append(_RUNNER % {"classname": classname, "mask": mask})
    return "\n".join(out) + "\n", converted, todos


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
