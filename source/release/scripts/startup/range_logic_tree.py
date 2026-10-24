"""Logic Tree: lógica do jogo desenhada por nós, compilada em Logic Bricks nativos.

Gatilhos viram sensores, portas E/Ou/Não viram um controller (And, Or ou Expression)
e ações viram actuators.  A árvore é um datablock: vários objetos podem usar a mesma
(Object.logic_tree).  Ao apertar P, ao salvar e pelo botão Compile, cada objeto recebe
os bricks no grupo "Tree: <nome>".  A lista do que foi gerado fica em
Object.logic_tree_record, então recompilar só troca esses bricks; os do usuário ficam.
Plano: docs/logic-tree-plan.md.
"""

import json
import re
import unicodedata

import bpy
import nodeitems_utils
from bpy.props import (BoolProperty, BoolVectorProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, IntVectorProperty, PointerProperty,
                       StringProperty)
from bpy.types import Node, NodeSocket, NodeTree, Operator, Panel
from nodeitems_utils import NodeCategory, NodeItem


TREE_ID = "RangeLogicTree"
RESERVED = {"SUM", "NOT", "AND", "OR", "IF", "WHOMADE", "TRUE", "FALSE"}


class LogicTree(NodeTree):
    """Lógica do jogo por nós; vira Logic Bricks ao jogar e ao salvar"""
    bl_idname = TREE_ID
    bl_label = "Logic Tree"
    bl_icon = "LOGIC"
    range_experimental = True  # cabeçalho do Node Editor mostra (Experimental)

    show_highlight_active = BoolProperty(
        name="Highlight Active", default=True,
        description="While the game runs, light up the nodes and links that are firing")


class PulseSocket(NodeSocket):
    bl_idname = "RangeLogicPulseSocket"
    bl_label = "Pulse"

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (0.95, 0.75, 0.2, 1.0)


# ---------------------------------------------------------------- campos a partir do RNA

def _prop_from_rna(p):
    """Copia a definição de uma propriedade do brick (enum, padrão, limites) para o nó."""
    kw = dict(name=p.name, description=p.description)
    if p.type == 'ENUM':
        items = [(i.identifier, i.name, i.description, i.value) for i in p.enum_items]
        if p.is_enum_flag:
            return EnumProperty(items=items, options={'ENUM_FLAG'}, default=set(p.default_flag), **kw)
        return EnumProperty(items=items, default=p.default, **kw)
    if p.type == 'BOOLEAN':
        if p.is_array:
            return BoolVectorProperty(size=p.array_length, default=tuple(p.default_array), **kw)
        return BoolProperty(default=p.default, **kw)
    if p.type in ('INT', 'FLOAT'):
        kw.update(min=p.hard_min, max=p.hard_max, soft_min=p.soft_min, soft_max=p.soft_max,
                  subtype=p.subtype)
        if p.type == 'FLOAT':
            kw["precision"] = p.precision
        if p.is_array:
            cls = IntVectorProperty if p.type == 'INT' else FloatVectorProperty
            return cls(size=p.array_length, default=tuple(p.default_array), **kw)
        cls = IntProperty if p.type == 'INT' else FloatProperty
        return cls(default=p.default, **kw)
    if p.type == 'STRING':
        return StringProperty(default=p.default, **kw)
    if p.type == 'POINTER':
        return PointerProperty(type=getattr(bpy.types, p.fixed_type.identifier), **kw)
    raise TypeError("%s: tipo %s sem conversão" % (p.identifier, p.type))


def _set_active(node, value):
    node.mute = not value


# cor de cada conjunto, como no Logic Editor: sensores azul, controllers amarelo, actuators verde
TRIGGER_COLOR = (0.32, 0.45, 0.6)
GATE_COLOR = (0.58, 0.54, 0.3)
ACTION_COLOR = (0.33, 0.52, 0.36)
ERROR_COLOR = (0.6, 0.15, 0.15)
FIRED_COLOR = (0.1, 0.78, 0.25)
_OUR_COLORS = (TRIGGER_COLOR, GATE_COLOR, ACTION_COLOR, ERROR_COLOR, FIRED_COLOR)


def _is_ours(color):
    return any(all(abs(a - b) < 1e-3 for a, b in zip(color, c)) for c in _OUR_COLORS)


class LogicNode:
    base_color = None

    def paint(self):
        """Disparou > erro > cor do conjunto.  Cor escolhida pelo usuário fica."""
        if self.use_custom_color and not _is_ours(self.color):
            return
        err = isinstance(self, BrickNode) and self.error()
        color = FIRED_COLOR if "range_logic_fired" in self else ERROR_COLOR if err else self.base_color
        self.use_custom_color = color is not None
        if color is not None:
            self.color = color

    # checkbox como o dos logic bricks: desligado = nó mutado, não vira brick
    range_logic_active = BoolProperty(
        name="Active", description="Off: this node is ignored (same as Mute, M)",
        get=lambda self: not self.mute, set=_set_active)

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == TREE_ID


class BrickNode(LogicNode):
    """Nó que vira um sensor ou actuator.  Subclasses definem kind, brick_type,
    main (campos no nó), extra (campos só no painel N), fixed (valores fixos),
    required (campos que não podem ficar vazios)."""
    kind = ""
    brick_type = ""
    main = ()
    extra = ()
    fixed = {}
    required = ()

    range_logic_break = BoolProperty(
        name="Pause When Fired",
        description="Depuração: com o Debug Mode da cena ligado, pausa o jogo quando este nó dispara "
                    "(o botão de pausa da janela de depuração continua)")

    def fields(self):
        return self.main + self.extra

    def error(self):
        for f in self.required:
            if not getattr(self, f):
                return "Preencha: %s" % type(self).bl_rna.properties[f].name
        return ""

    range_logic_show_extra = BoolProperty(
        name="More", description="Show the other brick settings inside the node")

    def draw_buttons(self, context, layout):
        layout.prop(self, "range_logic_active")
        for f in self.main:
            layout.prop(self, f)
        extra = [f for f in self.extra if f not in self.main]
        if extra:
            # as demais opções do brick, recolhidas por padrão para o nó ficar pequeno
            show = self.range_logic_show_extra
            layout.prop(self, "range_logic_show_extra", emboss=False,
                        icon="TRIA_DOWN" if show else "TRIA_RIGHT")
            if show:
                col = layout.column(align=True)
                for f in extra:
                    col.prop(self, f)
        err = self.error()
        if err:
            layout.label(err, icon="ERROR")

    def draw_buttons_ext(self, context, layout):
        for f in self.fields():
            layout.prop(self, f)

    def draw_label(self):
        label = self.label or self.bl_label
        return ("* " + label) if self.range_logic_break else label

    def update(self):
        self.paint()


class TriggerNode(BrickNode):
    kind = "sensor"
    base_color = TRIGGER_COLOR

    def init(self, context):
        self.outputs.new(PulseSocket.bl_idname, "Pulse")
        self.paint()


class ActionNode(BrickNode):
    kind = "actuator"
    has_then = False  # ações que concluem ganham a saída Then
    base_color = ACTION_COLOR

    def init(self, context):
        sock = self.inputs.new(PulseSocket.bl_idname, "Do")
        sock.link_limit = 4095
        if self.has_then:
            self.outputs.new(PulseSocket.bl_idname, "Then")
        self.paint()


def _brick_node(base, idname, label, rna, brick_type, main, extra=(), fixed=None, required=(),
                then=False):
    attrs = {"bl_idname": idname, "bl_label": label, "brick_type": brick_type,
             "main": tuple(main), "extra": tuple(extra), "fixed": fixed or {},
             "required": tuple(required), "has_then": then}
    for f in tuple(main) + tuple(extra):
        attrs[f] = _prop_from_rna(rna.bl_rna.properties[f])
    return type(idname, (base, Node), attrs)


T = bpy.types
PULSE = ("use_pulse_true_level", "use_pulse_false_level", "tick_skip", "use_tap", "invert")

TRIGGER_NODES = (
    _brick_node(TriggerNode, "RangeLogicAlways", "Always", T.AlwaysSensor, 'ALWAYS', (), PULSE),
    _brick_node(TriggerNode, "RangeLogicKey", "Key", T.KeyboardSensor, 'KEYBOARD',
                ("key", "use_pulse_true_level"), ("modifier_key_1", "modifier_key_2") + PULSE[1:]),
    _brick_node(TriggerNode, "RangeLogicMouse", "Mouse", T.MouseSensor, 'MOUSE',
                ("mouse_event",), PULSE),
    _brick_node(TriggerNode, "RangeLogicCollision", "Collision", T.CollisionSensor, 'COLLISION',
                ("property",), ("use_material", "material") + PULSE),
    _brick_node(TriggerNode, "RangeLogicProperty", "Property", T.PropertySensor, 'PROPERTY',
                ("property", "evaluation_type", "value"), PULSE,  # value_min grava no mesmo campo de value
                required=("property",)),
    _brick_node(TriggerNode, "RangeLogicMessage", "Message", T.MessageSensor, 'MESSAGE',
                ("subject",), PULSE),
    _brick_node(TriggerNode, "RangeLogicRay", "Ray", T.RaySensor, 'RAY',
                ("axis", "range", "property"), ("ray_type", "use_x_ray", "mask") + PULSE),
    _brick_node(TriggerNode, "RangeLogicNear", "Near", T.NearSensor, 'NEAR',
                ("property", "distance", "reset_distance"), PULSE),
)

ACTION_NODES = (
    _brick_node(ActionNode, "RangeLogicMotion", "Motion", T.ObjectActuator, 'MOTION',
                ("offset_location", "offset_rotation", "use_local_location", "use_local_rotation"),
                ("linear_velocity", "use_local_linear_velocity", "use_add_linear_velocity",
                 "angular_velocity", "use_local_angular_velocity", "force", "use_local_force",
                 "torque", "use_local_torque")),
    _brick_node(ActionNode, "RangeLogicSetProperty", "Set Property", T.PropertyActuator, 'PROPERTY',
                ("property", "value"), fixed={"mode": 'ASSIGN'}, required=("property",)),
    _brick_node(ActionNode, "RangeLogicAddProperty", "Add to Property", T.PropertyActuator,
                'PROPERTY', ("property", "value"), fixed={"mode": 'ADD'}, required=("property",)),
    _brick_node(ActionNode, "RangeLogicToggleProperty", "Toggle Property", T.PropertyActuator,
                'PROPERTY', ("property",), fixed={"mode": 'TOGGLE'}, required=("property",)),
    _brick_node(ActionNode, "RangeLogicMessageSend", "Send Message", T.MessageActuator, 'MESSAGE',
                ("subject", "to_property"), ("body_type", "body_message", "body_property")),
    _brick_node(ActionNode, "RangeLogicSound", "Sound", T.SoundActuator, 'SOUND',
                ("sound", "mode"), ("volume", "pitch"), required=("sound",), then=True),
    _brick_node(ActionNode, "RangeLogicRemove", "Remove Object", T.EditObjectActuator,
                'EDIT_OBJECT', (), fixed={"mode": 'ENDOBJECT'}),
    _brick_node(ActionNode, "RangeLogicWait", "Wait", T.WaitActuator, 'WAIT',
                ("duration",), ("use_restart",), then=True),
    _brick_node(ActionNode, "RangeLogicAction", "Play Action", T.ActionActuator, 'ACTION',
                ("action", "play_mode", "frame_start", "frame_end"),
                ("property", "frame_property", "frame_blend_in", "priority", "layer",
                 "layer_weight", "blend_mode", "use_additive", "use_continue_last_frame"),
                required=("action",), then=True),
    _brick_node(ActionNode, "RangeLogicSteering", "Steering", T.SteeringActuator, 'STEERING',
                ("mode", "target", "velocity", "distance"),
                ("acceleration", "turn_speed", "navmesh", "self_terminated", "update_period",
                 "facing", "facing_axis", "normal_up", "lock_z_velocity"),
                required=("target",), then=True),
    _brick_node(ActionNode, "RangeLogicVideo", "Video", T.VideoActuator, 'VIDEO',
                ("mode", "object"), ("seconds", "use_relative"), then=True),
)


class GoToStateNode(ActionNode, Node):
    """Troca o estado do objeto para o Frame de Estado escolhido"""
    bl_idname = "RangeLogicGoToState"
    bl_label = "Go To State"
    brick_type = 'STATE'
    state = StringProperty(name="State", description="Rótulo de um Frame de Estado desta árvore")

    def fields(self):
        return ()

    def error(self):
        if not self.state:
            return "Preencha: State"
        if find_frame(self.id_data, self.state) is None:
            return "Sem Frame de Estado \"%s\"" % self.state
        return ""

    def draw_buttons(self, context, layout):
        layout.prop(self, "range_logic_active")
        layout.prop_search(self, "state", self.id_data, "nodes", text="", icon="NODETREE")
        err = self.error()
        if err:
            layout.label(err, icon="ERROR")

    def draw_buttons_ext(self, context, layout):
        self.draw_buttons(context, layout)


class RunPythonNode(ActionNode, Node):
    """Roda modulo.funcao num controller Python (modo Module).  A função recebe o
    controller e lê os sensores ligados com cont.sensors"""
    bl_idname = "RangeLogicRunPython"
    bl_label = "Run Python"
    kind = "controller"
    brick_type = 'PYTHON'
    base_color = GATE_COLOR
    module = StringProperty(name="Module", description="modulo.funcao (texto interno ou arquivo .py)")
    use_debug = BoolProperty(name="D (Debug)", description="Recarrega o módulo a cada execução")
    main = ("module",)
    extra = ("use_debug",)
    required = ("module",)

    def error(self):
        if not self.module:
            return "Preencha: Module"
        if "." not in self.module:
            return "Use modulo.funcao"
        return ""


ACTION_NODES += (GoToStateNode, RunPythonNode)


# ---------------------------------------------------------------- demais bricks, direto do RNA

def _auto_fields(rna, kind, skip=()):
    base = set(getattr(T, kind.title()).bl_rna.properties.keys())
    out = []
    for p in rna.bl_rna.properties:
        if p.identifier in base or p.identifier in skip or p.is_readonly:
            continue
        try:
            _prop_from_rna(p)
        except Exception:  # enum dinâmico ou ponteiro que não é ID: fica de fora
            continue
        out.append(p.identifier)
    return out


def _auto_node(base, idname, label, rna, brick_type, skip=(), n_main=3, **kw):
    kind = "sensor" if base is TriggerNode else "actuator"
    fields = _auto_fields(rna, kind, skip)
    extra = fields[n_main:] + (list(PULSE) if base is TriggerNode else [])
    return _brick_node(base, idname, label, rna, brick_type, fields[:n_main], extra, **kw)


TRIGGER_NODES += (
    _auto_node(TriggerNode, "RangeLogicDelay", "Delay", T.DelaySensor, 'DELAY'),
    _auto_node(TriggerNode, "RangeLogicRandom", "Random", T.RandomSensor, 'RANDOM'),
    _auto_node(TriggerNode, "RangeLogicRadar", "Radar", T.RadarSensor, 'RADAR'),
    _auto_node(TriggerNode, "RangeLogicMovement", "Movement", T.MovementSensor, 'MOVEMENT'),
    _auto_node(TriggerNode, "RangeLogicJoystick", "Joystick", T.JoystickSensor, 'JOYSTICK', n_main=4),
    _auto_node(TriggerNode, "RangeLogicAnimEvent", "Animation Event", T.AnimationEventSensor,
               'ANIMATIONEVENT'),
    _auto_node(TriggerNode, "RangeLogicActuatorSensor", "Actuator State", T.ActuatorSensor, 'ACTUATOR',
               required=("actuator",)),
    _auto_node(TriggerNode, "RangeLogicVRHead", "VR Head", T.VRHeadSensor, 'VR_HEAD'),
)

ACTION_NODES += (
    _auto_node(ActionNode, "RangeLogicCamera", "Camera Follow", T.CameraActuator, 'CAMERA',
               n_main=4, required=("object",)),
    _auto_node(ActionNode, "RangeLogicMouseLook", "Mouse Look", T.MouseActuator, 'MOUSE'),
    _auto_node(ActionNode, "RangeLogicEditObject", "Edit Object", T.EditObjectActuator, 'EDIT_OBJECT',
               n_main=2),
    _brick_node(ActionNode, "RangeLogicPropertyFull", "Property (all modes)", T.PropertyActuator,
                'PROPERTY', ("mode", "property", "value"),
                [f for f in _auto_fields(T.PropertyActuator, "actuator")
                 if f not in ("mode", "property", "value")], required=("property",)),
    _auto_node(ActionNode, "RangeLogicRandomAct", "Random Value", T.RandomActuator, 'RANDOM'),
    _auto_node(ActionNode, "RangeLogicScene", "Scene", T.SceneActuator, 'SCENE'),
    _auto_node(ActionNode, "RangeLogicGame", "Game", T.GameActuator, 'GAME', n_main=2),
    _auto_node(ActionNode, "RangeLogicParent", "Parent", T.ParentActuator, 'PARENT', n_main=2),
    _auto_node(ActionNode, "RangeLogicVisibility", "Visibility", T.VisibilityActuator, 'VISIBILITY'),
    _auto_node(ActionNode, "RangeLogicConstraint", "Constraint", T.ConstraintActuator, 'CONSTRAINT',
               n_main=2),
    _auto_node(ActionNode, "RangeLogicFilter2D", "2D Filter", T.Filter2DActuator, 'FILTER_2D',
               n_main=2),
    _auto_node(ActionNode, "RangeLogicVibration", "Vibration", T.VibrationActuator, 'VIBRATION'),
    _auto_node(ActionNode, "RangeLogicStateRaw", "State (mask)", T.StateActuator, 'STATE', n_main=2),
)


class GateNode(LogicNode):
    op = ""
    base_color = GATE_COLOR

    def init(self, context):
        for _ in range(self.n_inputs):
            self.inputs.new(PulseSocket.bl_idname, "In")
        self.outputs.new(PulseSocket.bl_idname, "Pulse")
        self.paint()

    def draw_buttons(self, context, layout):
        layout.prop(self, "range_logic_active")


class AndNode(GateNode, Node):
    """Passa quando todas as entradas ligadas estão ativas"""
    bl_idname = "RangeLogicAnd"
    bl_label = "And"
    op, n_inputs = "AND", 3


class OrNode(GateNode, Node):
    """Passa quando alguma entrada ligada está ativa"""
    bl_idname = "RangeLogicOr"
    bl_label = "Or"
    op, n_inputs = "OR", 3


class NotNode(GateNode, Node):
    """Inverte a entrada"""
    bl_idname = "RangeLogicNot"
    bl_label = "Not"
    op, n_inputs = "NOT", 1


GATE_NODES = (AndNode, OrNode, NotNode)


# ---------------------------------------------------------------- compilação

def _source(socket):
    """Nó real ligado a uma entrada, atravessando Reroutes.  None se solto."""
    seen = set()
    while socket.is_linked:
        link = socket.links[0]
        if not link.is_valid:
            return None
        node = link.from_node
        if node.bl_idname != "NodeReroute":
            return node
        if node in seen or not node.inputs:
            return None
        seen.add(node)
        socket = node.inputs[0]
    return None


def _sources(socket):
    out = []
    for link in socket.links:
        if not link.is_valid:
            continue
        node = link.from_node
        if node.bl_idname == "NodeReroute":
            node = _source(node.inputs[0]) if node.inputs else None
        if node is not None:
            out.append(node)
    return out


def _expr(node, stack=()):
    """Árvore de expressão: ('S', trigger) | ('AND'|'OR', [filhos]) | ('NOT', filho) | None."""
    if node is None or node in stack or node.mute:  # nó mutado (M) corta o caminho
        return None
    if isinstance(node, TriggerNode) or (isinstance(node, ActionNode) and node.has_then):
        return ('S', node)  # ação na folha = sua saída Then
    if isinstance(node, GateNode):
        kids = [_expr(_source(s), stack + (node,)) for s in node.inputs]
        kids = [k for k in kids if k is not None]
        if not kids:
            return None
        if node.op == "NOT":
            return ('NOT', kids[0])
        return kids[0] if len(kids) == 1 else (node.op, kids)
    return None


def _flat(op, kids):
    """Junta sensores ligados direto a uma porta só de E (ou só de Ou)."""
    if all(k[0] == 'S' for k in kids):
        return op, [k[1] for k in kids]
    return None


def _key(e):
    if e[0] == 'S':
        return ('S', e[1].name)
    if e[0] == 'NOT':
        return ('NOT', _key(e[1]))
    return (e[0], tuple(_key(k) for k in e[1]))


def _triggers(e, out):
    if e[0] == 'S':
        if e[1] not in out:
            out.append(e[1])
    elif e[0] == 'NOT':
        _triggers(e[1], out)
    else:
        for k in e[1]:
            _triggers(k, out)


def _ascii(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^0-9A-Za-z_]+", "_", text).strip("_") or "S"
    if not text[0].isalpha():
        text = "S_" + text
    return text


def _write(e, names):
    if e[0] == 'S':
        return names[e[1]]
    if e[0] == 'NOT':
        return "NOT (%s)" % _write(e[1], names)
    return "(%s)" % (" %s " % e[0]).join(_write(k, names) for k in e[1])


def _label(node):
    return node.label or node.name


def _pos(node):
    loc = node.location.copy()
    while node.parent is not None:  # filhos de Frame guardam posição relativa
        node = node.parent
        loc += node.location
    return (loc.x, -loc.y)


def state_frames(tree):
    """Frames marcados como Estado, da esquerda para a direita."""
    frames = [n for n in tree.nodes if n.bl_idname == "NodeFrame" and n.range_logic_state]
    return sorted(frames, key=_pos)


def find_frame(tree, text):
    """Frame de Estado pelo rótulo (ou pelo nome do nó)."""
    frames = state_frames(tree)
    return next((f for f in frames if _label(f) == text), None) or \
        next((f for f in frames if f.name == text), None)


def frame_of(node):
    """Frame de Estado mais próximo que contém o nó, ou None."""
    node = node.parent
    while node is not None:
        if node.bl_idname == "NodeFrame" and node.range_logic_state:
            return node
        node = node.parent
    return None


def _leaves(e):
    out = []
    _triggers(e, out)
    return out


def plan(tree):
    """Regras [expressão, ações, frame] da árvore e erros, sem tocar em objetos.
    Ações no mesmo frame com a mesma expressão dividem um controller."""
    rules, errors = {}, []
    for node in tree.nodes:
        if not isinstance(node, ActionNode) or node.mute:
            continue
        if node.error():
            errors.append("%s: %s" % (_label(node), node.error()))
            continue
        exprs = [_expr(n) for n in _sources(node.inputs[0])]
        exprs = [e for e in exprs if e is not None]
        if not exprs:
            continue
        e = exprs[0] if len(exprs) == 1 else ('OR', exprs)
        frame = frame_of(node)
        rules.setdefault((_key(e), frame.name if frame else ""), [e, [], frame])[1].append(node)
    for node in tree.nodes:
        if isinstance(node, TriggerNode) and node.error():
            errors.append("%s: %s" % (_label(node), node.error()))
    # Then de uma ação que nunca roda não dispara nada
    acting = {a for r in rules.values() for a in r[1]}
    out = []
    for r in rules.values():
        dead = [n for n in _leaves(r[0]) if isinstance(n, ActionNode) and n not in acting]
        if dead:
            errors.append("%s: Then de \"%s\", que não tem gatilho" % (
                _label(r[1][0]), _label(dead[0])))
            continue
        out.append(r)
    names = [_label(f) for f in state_frames(tree)]
    for n in set(x for x in names if names.count(x) > 1):
        errors.append("Frames de Estado com o mesmo nome: %s" % n)
    out.sort(key=lambda r: _pos(r[1][0]))
    return out, errors


def _record(ob):
    try:
        rec = json.loads(ob.logic_tree_record or "{}")
    except ValueError:
        rec = {}
    return rec


def _ops(ob):
    # os operadores de bricks pedem um objeto ativo; o save pode acontecer sem nenhum
    return {"object": ob, "active_object": ob}


def clear(ob):
    """Apaga só os bricks que a árvore gerou neste objeto."""
    rec = _record(ob)
    game = ob.game
    for kind in ("controllers", "sensors", "actuators"):
        coll = getattr(game, kind)
        for name in rec.get(kind, ()):
            if name in coll:
                getattr(bpy.ops.logic, kind[:-1] + "_remove")(
                    _ops(ob), **{kind[:-1]: name, "object": ob.name})
    for i in rec.get("names", ()):
        game.state_names[i - 1].name = ""
    for i in rec.get("init_on", ()):
        game.states_initial[i - 1] = False
    for i in rec.get("init_off", ()):
        game.states_initial[i - 1] = True
    group = rec.get("group")
    if group and group in game.brick_groups and not any(
            b.group == group for kind in ("sensors", "controllers", "actuators")
            for b in getattr(game, kind)):
        game.brick_groups.remove(game.brick_groups[group])
    ob.logic_tree_record = ""


def _used_states(ob):
    """Estados que os bricks do usuário usam (controllers e actuators State)."""
    game, used = ob.game, set()
    for c in game.controllers:
        used.add(c.states)
    for a in game.actuators:
        if a.type == 'STATE':
            used.update(i + 1 for i, on in enumerate(a.states) if on)
    return used


def _assign_states(ob, tree, rec):
    """Número de estado de cada Frame de Estado: o do nome igual em state_names, senão o
    primeiro livre.  Marca o estado inicial.  Grava no rec o que mudou no objeto."""
    game = ob.game
    frames = state_frames(tree)
    if not frames:
        return {}
    names = {sn.name: i + 1 for i, sn in enumerate(game.state_names) if sn.name}
    taken = _used_states(ob) | set(names.values())
    out = {}
    for f in frames:
        label = _label(f)
        if label in names and names[label] not in out.values():
            out[f.name] = names[label]
            continue
        free = next((i for i in range(1, 31) if i not in taken and i not in out.values()), None)
        if free is None:
            continue
        out[f.name] = free
        game.state_names[free - 1].name = label
        rec["names"].append(free)
    start = next((f for f in frames if f.range_logic_initial), frames[0])
    for f in frames:
        if f.name not in out:
            continue
        bit = out[f.name]
        want = f == start
        if game.states_initial[bit - 1] != want:
            game.states_initial[bit - 1] = want
            rec["init_on" if want else "init_off"].append(bit)
    # o estado 1 ligado por padrão, sem nada nele, não pode somar com o inicial da árvore
    if game.states_initial[0] and 1 not in _used_states(ob) and 1 not in out.values():
        game.states_initial[0] = False
        rec["init_off"].append(1)
    return out


def compile_object(ob, scene=None):
    """Gera os bricks da árvore do objeto.  Devolve a lista de erros."""
    if ob.library is not None:
        return ["%s: objeto de biblioteca, não compilado" % ob.name]
    clear(ob)
    tree = ob.logic_tree
    if tree is None or tree.bl_idname != TREE_ID:
        return []
    for node in tree.nodes:  # árvores antigas ganham as cores dos conjuntos
        if isinstance(node, LogicNode):
            node.paint()
    rules, errors = plan(tree)
    game = ob.game
    group = "Tree: " + tree.name
    if group not in game.brick_groups:
        group = game.brick_groups.new(group).name
    rec = {"group": group, "sensors": [], "controllers": [], "actuators": [],
           "names": [], "init_on": [], "init_off": [], "nodes": {}}
    frame_state = _assign_states(ob, tree, rec)
    tree_bits = set(frame_state.values())
    loose = _used_states(ob) | tree_bits | {
        i + 1 for i, on in enumerate(game.states_initial) if on}
    loose = sorted(loose) or [1]

    def add(kind, typ, name, node=None):
        getattr(bpy.ops.logic, kind + "_add")(_ops(ob), type=typ, name=name, object=ob.name)
        brick = getattr(game, kind + "s")[-1]
        brick.group = group
        rec[kind + "s"].append(brick.name)
        if node is not None:  # F5: liga o brick ao nó (painel N e depuração)
            rec["nodes"]["%s:%s" % (kind, brick.name)] = node.name
        return brick

    def fill(brick, node):
        for k, v in node.fixed.items():
            setattr(brick, k, v)
        for f in node.fields():
            if not node.is_property_set(f) and f not in node.main:
                continue  # nunca mexido: fica o padrão do brick (campos que dividem memória não se sobrescrevem)
            value = getattr(node, f)
            if hasattr(value, "__len__") and not isinstance(value, (str, set)) \
                    and not isinstance(value, bpy.types.ID):
                value = tuple(value)
            try:
                setattr(brick, f, value)
            except (TypeError, ValueError) as exc:
                errors.append("%s: %s (%s)" % (_label(node), f, exc))

    # quais gatilhos aparecem dentro de um Expression: esses precisam de nome ASCII
    in_expr = set()
    for e, _acts, _f in rules:
        if e[0] in ('NOT',) or (e[0] in ('AND', 'OR') and _flat(e[0], e[1]) is None):
            tr = []
            _triggers(e, tr)
            in_expr.update(tr)

    # um gatilho negado precisa pulsar também parado em falso, senão o controller nem roda
    negated = set()

    def _neg(e, inside):
        if e[0] == 'S':
            if inside:
                negated.add(e[1])
        elif e[0] == 'NOT':
            _neg(e[1], True)
        else:
            for k in e[1]:
                _neg(k, inside)

    for e, _acts, _f in rules:
        _neg(e, False)

    sensors, actuators = {}, {}
    for _e, acts, _f in rules:
        for node in acts:
            if node in actuators or node.kind == "controller":
                continue
            if isinstance(node, GoToStateNode):
                target = frame_state[find_frame(tree, node.state).name]
                rem = add("actuator", 'STATE', _label(node) + " (out)", node)
                rem.operation = 'REMOVE'
                rem.states = [i + 1 in tree_bits and i + 1 != target for i in range(30)]
                put = add("actuator", 'STATE', _label(node), node)
                put.operation = 'ADD'
                put.states = [i + 1 == target for i in range(30)]
                actuators[node] = [rem, put]
            else:
                a = add("actuator", node.brick_type, _label(node), node)
                fill(a, node)
                actuators[node] = [a]

    used = set(RESERVED) | {p.name.upper() for p in game.properties}
    for e, acts, _f in rules:
        for node in _leaves(e):
            if node in sensors:
                continue
            then = isinstance(node, ActionNode)
            name = "Then " + _label(node) if then else _label(node)
            if node in in_expr:
                base, n = _ascii(name), 1
                name = base
                while name.upper() in used or name in game.sensors:
                    n += 1
                    name = "%s_%d" % (base, n)
                used.add(name.upper())
            if then:
                s = add("sensor", 'ACTUATOR', name, node)
                s.actuator = actuators[node][-1].name
                s.mode = 'FINISHED'
            else:
                s = add("sensor", node.brick_type, name, node)
                fill(s, node)
            if node in negated:
                s.use_pulse_false_level = True
            sensors[node] = s

    for e, acts, frame in rules:
        if e[0] == 'S':
            typ, linked, text = 'LOGIC_AND', [e[1]], None
        elif e[0] in ('AND', 'OR') and _flat(e[0], e[1]) is not None:
            typ = 'LOGIC_AND' if e[0] == 'AND' else 'LOGIC_OR'
            linked, text = _flat(e[0], e[1])[1], None
        else:
            typ, linked = 'EXPRESSION', []
            _triggers(e, linked)
            text = _write(e, {n: sensors[n].name for n in linked})
            if text.startswith("(") and text.endswith(")") and text.count("(") == 1:
                text = text[1:-1]
        states = [frame_state[frame.name]] if frame else loose
        # Run Python: controller próprio ligado aos gatilhos; o script decide com cont.sensors
        for py in [a for a in acts if a.kind == "controller"]:
            leaves = _leaves(e)
            for state in states:
                c = add("controller", 'PYTHON', _label(py), py)
                c.states, c.mode, c.module, c.use_debug = state, 'MODULE', py.module, py.use_debug
                for n in leaves:
                    c.link(sensor=sensors[n])
        acts = [a for a in acts if a.kind != "controller"]
        if not acts:
            continue
        name = " + ".join(_label(a) for a in acts)
        for state in states:
            c = add("controller", typ, name, acts[0])
            c.states = state
            if text is not None:
                c.expression = text
            for n in linked:
                c.link(sensor=sensors[n])
            for a in acts:
                for brick in actuators[a]:
                    c.link(actuator=brick)

    # F5: pausar no disparo.  Só com o Debug Mode da cena ligado, para nunca ir num jogo final.
    # a cena pedida (compile_all no Play) quando o objeto está nela; senão a primeira que o usa
    if not isinstance(scene, bpy.types.Scene) or ob.name not in scene.objects:
        scene = next(iter(ob.users_scene), None)
    if scene is not None and scene.game_settings.show_debug_mode:
        every = sorted(set(loose) | tree_bits)
        # F6: registro de disparos, lido pelo editor ao fim do jogo para destacar os nós
        _ensure_trace_text()
        trace = add("sensor", 'ALWAYS', "Logic Tree Trace")
        for state in every:
            c = add("controller", 'PYTHON', "Logic Tree Trace")
            c.states, c.mode, c.module = state, 'MODULE', TRACE_MODULE + ".start"
            c.link(sensor=trace)
        for node in [n for n in tree.nodes if getattr(n, "range_logic_break", False)]:
            if node in sensors:
                pause = add("actuator", 'SCENE', "Pause: " + _label(node), node)
                pause.mode, pause.scene = 'SUSPEND', scene
                for state in every:
                    c = add("controller", 'LOGIC_AND', "Pause: " + _label(node), node)
                    c.states = state
                    c.link(sensor=sensors[node])
                    c.link(actuator=pause)
            elif node in actuators:
                pause = add("actuator", 'SCENE', "Pause: " + _label(node), node)
                pause.mode, pause.scene = 'SUSPEND', scene
                for c in game.controllers:
                    if c.name in rec["controllers"] and any(
                            a.name == actuators[node][-1].name for a in c.actuators):
                        c.link(actuator=pause)

    ob.logic_tree_record = json.dumps(rec)
    return errors


# ---------------------------------------------------------------- F6: destaque dos nós que dispararam

TRACE_MODULE = "range_logic_trace"
TRACE_FILE = "range_logic_trace.json"
TRACE_SOURCE = '''# Gerado pela Logic Tree (Debug Mode): ao fim do jogo grava quantas vezes cada brick
# disparou (fireCount) para o editor destacar os nós.  Pode apagar; volta ao compilar.
import json, os, tempfile
import bge

_owners = {}


def _dump(scene):
    path = os.path.join(tempfile.gettempdir(), "%s")
    try:
        data = json.load(open(path))
    except Exception:
        data = {}
    for ob in list(_owners.pop(scene.name, ())):
        try:
            entry = data.setdefault(ob.name, {})
            for kind, bricks in (("sensor", ob.sensors), ("actuator", ob.actuators)):
                for b in bricks:
                    key = "%%s:%%s" %% (kind, b.name)
                    entry[key] = max(entry.get(key, 0), getattr(b, "fireCount", 0))
        except SystemError:  # objeto já apagado
            pass
    with open(path, "w") as f:
        json.dump(data, f)


def start(cont):
    scene = bge.logic.getCurrentScene()
    obs = _owners.get(scene.name)
    if obs is None:
        obs = _owners[scene.name] = []
        scene.onRemove.append(_dump)
    if cont.owner not in obs:
        obs.append(cont.owner)
''' % TRACE_FILE


def trace_path():
    import os
    import tempfile
    return os.path.join(tempfile.gettempdir(), TRACE_FILE)


def _ensure_trace_text():
    name = TRACE_MODULE + ".py"
    text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    if text.as_string() != TRACE_SOURCE:
        text.from_string(TRACE_SOURCE)


def clear_highlight(tree=None):
    for t in ([tree] if tree else [g for g in bpy.data.node_groups if g.bl_idname == TREE_ID]):
        for node in t.nodes:
            if "range_logic_fired" in node:
                del node["range_logic_fired"]
                if isinstance(node, LogicNode):
                    node.paint()  # volta à cor do conjunto (ou ao vermelho de erro)


def apply_trace(path=None):
    """Lê o registro do último jogo e pinta de verde os nós cujos bricks dispararam.
    Devolve {nome da árvore: nós destacados}."""
    import os
    path = path or trace_path()
    if not os.path.exists(path):
        return {}
    try:
        data = json.load(open(path))
    except ValueError:
        return {}
    fired = {}
    for ob in bpy.data.objects:
        counts = data.get(ob.name)
        tree = ob.logic_tree
        if not counts or tree is None:
            continue
        for key, node_name in _record(ob).get("nodes", {}).items():
            n = counts.get(key, 0)
            node = tree.nodes.get(node_name)
            if node is None or not n:
                continue
            node["range_logic_fired"] = max(node.get("range_logic_fired", 0), n)
            fired.setdefault(tree.name, set()).add(node.name)
    for tree_name, names in fired.items():
        tree = bpy.data.node_groups[tree_name]
        for name in names:
            node = tree.nodes[name]
            node.paint()
    return {k: sorted(v) for k, v in fired.items()}


# ---------------------------------------------------------------- realce ao vivo (Highlight Active)

LIVE_COLOR = (1.0, 0.72, 0.18)  # a mesma do Logic Editor


def _live_intensity(tree):
    """{nome do nó: brilho 0..1} dos bricks que a árvore gerou e que dispararam agora."""
    out = {}
    for ob in bpy.data.objects:
        if ob.logic_tree != tree:
            continue
        game = ob.game
        for key, node_name in _record(ob).get("nodes", {}).items():
            kind, _sep, name = key.partition(":")
            brick = getattr(game, kind + "s").get(name)
            v = brick.debug_intensity if brick is not None else 0.0
            if v > out.get(node_name, 0.0):
                out[node_name] = v
    if not out:
        return out
    # portas e reroutes não viram brick (entram na expressão do controller): acendem
    # quando algo antes e algo depois delas acendeu, para o caminho não se partir
    middle = [n for n in tree.nodes if not isinstance(n, BrickNode) and n.bl_idname != "NodeFrame"]
    for _pass in range(len(middle)):
        changed = False
        for n in middle:
            up = max([0.0] + [out.get(l.from_node.name, 0.0) for s in n.inputs for l in s.links])
            down = max([0.0] + [out.get(l.to_node.name, 0.0) for s in n.outputs for l in s.links])
            v = min(up, down)
            if v > out.get(n.name, 0.0):
                out[n.name] = v
                changed = True
        if not changed:
            break
    return out


def _node_rect(node, dpi):
    """(xmin, ymin, xmax, ymax) do nó em coordenadas da view."""
    x, y = node.location
    p = node.parent
    while p is not None:
        x, y = x + p.location.x, y + p.location.y
        p = p.parent
    x, y = x * dpi, y * dpi
    w, h = node.dimensions
    return x, y - h, x + w, y


def _socket_y(node, rect, socket, dpi):
    # aproxima o layout do node_update_basis: cabeçalho, saídas, botões, entradas embaixo
    unit = 20.0 * dpi
    if socket.is_output:
        outs = [s for s in node.outputs if not s.hide]
        i = outs.index(socket) if socket in outs else 0
        return rect[3] - unit * (1.75 + i)
    ins = [s for s in node.inputs if not s.hide]
    i = ins.index(socket) if socket in ins else 0
    return rect[1] + unit * 0.25 + unit * (len(ins) - i - 0.5)


def _draw_live():
    import bgl
    context = bpy.context
    space = context.space_data
    tree = getattr(space, "edit_tree", None)
    if tree is None or tree.bl_idname != TREE_ID or not tree.show_highlight_active:
        return
    lit = _live_intensity(tree)
    if not any(v > 0.0 for v in lit.values()):
        return
    system = context.user_preferences.system
    dpi = system.pixel_size * system.dpi / 72.0
    import time
    phase = (time.perf_counter() * 1.5) % 1.0
    rects = {}
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glEnable(bgl.GL_LINE_SMOOTH)
    # caminho: ligações cujos dois nós estão acesos
    for link in tree.links:
        a, b = link.from_node, link.to_node
        v = min(lit.get(a.name, 0.0), lit.get(b.name, 0.0))
        if v <= 0.0 or a.hide or b.hide:
            continue
        ra = rects.setdefault(a.name, _node_rect(a, dpi))
        rb = rects.setdefault(b.name, _node_rect(b, dpi))
        x0, y0 = ra[2], _socket_y(a, ra, link.from_socket, dpi)
        x1, y1 = rb[0], _socket_y(b, rb, link.to_socket, dpi)
        d = max(abs(x1 - x0) * 0.5, 30.0 * dpi)

        def point(t):
            u = 1.0 - t
            return (u * u * u * x0 + 3 * u * u * t * (x0 + d) + 3 * u * t * t * (x1 - d) + t * t * t * x1,
                    u * u * u * y0 + 3 * u * u * t * y0 + 3 * u * t * t * y1 + t * t * t * y1)

        pts = [point(i / 24.0) for i in range(25)]
        # igual ao Logic Editor: brilho largo, fio aceso e o pulso correndo para a ação
        for width, alpha in ((7.0, 0.25), (2.5, 1.0)):
            bgl.glLineWidth(width * system.pixel_size)
            bgl.glColor4f(LIVE_COLOR[0], LIVE_COLOR[1], LIVE_COLOR[2], alpha * v)
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for p in pts:
                bgl.glVertex2f(*p)
            bgl.glEnd()
        bgl.glPointSize(8.0 * system.pixel_size)
        bgl.glColor4f(1.0, 0.95, 0.75, v)
        bgl.glBegin(bgl.GL_POINTS)
        bgl.glVertex2f(*point(phase))
        bgl.glEnd()
        bgl.glPointSize(1.0)
    # nós acesos: moldura
    bgl.glLineWidth(3.0)
    for name, v in lit.items():
        node = tree.nodes.get(name)
        if node is None or v <= 0.0:
            continue
        x0, y0, x1, y1 = rects.get(name) or _node_rect(node, dpi)
        pad = 3.0 * dpi
        corners = ((x0 - pad, y0 - pad), (x1 + pad, y0 - pad), (x1 + pad, y1 + pad), (x0 - pad, y1 + pad))
        for mode, alpha in ((bgl.GL_QUADS, 0.12), (bgl.GL_LINE_LOOP, 1.0)):
            bgl.glColor4f(LIVE_COLOR[0], LIVE_COLOR[1], LIVE_COLOR[2], alpha * v)
            bgl.glBegin(mode)
            for px, py in corners:
                bgl.glVertex2f(px, py)
            bgl.glEnd()
    bgl.glLineWidth(1.0)
    bgl.glDisable(bgl.GL_LINE_SMOOTH)
    bgl.glDisable(bgl.GL_BLEND)


def _node_header(self, context):
    if context.space_data.tree_type != TREE_ID:
        return
    # objeto + New/Compile/Import também aqui: sem árvore o painel N nem aparece
    self.layout.separator()
    _draw_object_field(self.layout, context)
    tree = getattr(context.space_data, "edit_tree", None)
    if tree is not None:
        self.layout.prop(tree, "show_highlight_active", text="Highlight Active", icon='LIGHTPAINT')


_live_handle = None


@bpy.app.handlers.persistent
def _trace_pre(_scene):
    import os
    clear_highlight()
    try:
        os.remove(trace_path())
    except OSError:
        pass


@bpy.app.handlers.persistent
def _trace_post(_scene):
    try:
        apply_trace()
    except Exception as exc:
        print("[Logic Tree] destaque falhou: %s" % exc)


class RANGE_OT_logic_tree_clear_highlight(Operator):
    """Tira o destaque verde dos nós que dispararam no último jogo"""
    bl_idname = "logic.range_logic_tree_clear_highlight"
    bl_label = "Clear Highlight"

    def execute(self, context):
        clear_highlight()
        return {'FINISHED'}


def bricks_of_node(ob, node):
    """F5: bricks que um nó gerou neste objeto, como [(tipo, nome)]."""
    nodes = _record(ob).get("nodes", {})
    return [tuple(k.split(":", 1)) for k, v in nodes.items() if v == node.name]


def node_of_brick(ob, kind, name):
    """F5: nó que gerou o brick (kind = sensor, controller ou actuator), ou None."""
    tree = ob.logic_tree
    node = _record(ob).get("nodes", {}).get("%s:%s" % (kind, name))
    return tree.nodes.get(node) if tree is not None and node else None


def compile_all(scene=None):
    errors = []
    for ob in bpy.data.objects:
        if ob.logic_tree is not None or ob.logic_tree_record:
            errors += compile_object(ob, scene)
    return errors


@bpy.app.handlers.persistent
def _auto_compile(_scene):
    """Compila ao apertar P e ao salvar (o export salva): o jogo nunca roda lógica velha."""
    try:
        for err in compile_all(_scene):
            print("[Logic Tree] %s" % err)
    except Exception as exc:  # compilação quebrada não pode impedir de jogar/salvar
        print("[Logic Tree] Compilação falhou: %s" % exc)


# ---------------------------------------------------------------- receitas

class _Builder:
    """Monta nós dentro de um Frame com o nome da receita."""

    def __init__(self, tree, label, origin):
        self.tree, self.origin = tree, origin
        self.frame = self.node("NodeFrame", 0, 0, label=label)
        self.props = []

    def node(self, kind, x, y, parent=None, **kw):
        n = self.tree.nodes.new(kind)
        for k, v in kw.items():
            setattr(n, k, v)
        # posição absoluta antes de prender: ao prender, o Blender converte para relativa
        n.location = (self.origin[0] + x, self.origin[1] + y)
        if kind != "NodeFrame" or parent is not None:
            n.parent = parent or self.frame
        return n

    def link(self, src, dst, i=0):
        self.tree.links.new(src.outputs[0], dst.inputs[i])

    def gate(self, kind, x, y, *srcs, parent=None):
        g = self.node(kind, x, y, parent)
        for i, src in enumerate(srcs):
            self.link(src, g, i)
        return g

    def prop(self, name, typ, value):
        self.props.append((name, typ, value))


def _r_walk(b):
    for i, (key, label, loc, rot) in enumerate((
            ('W', "Forward", (0.0, 0.1, 0.0), (0.0, 0.0, 0.0)),
            ('S', "Back", (0.0, -0.1, 0.0), (0.0, 0.0, 0.0)),
            ('A', "Turn Left", (0.0, 0.0, 0.0), (0.0, 0.0, 0.05)),
            ('D', "Turn Right", (0.0, 0.0, 0.0), (0.0, 0.0, -0.05)))):
        k = b.node("RangeLogicKey", 0, -i * 120, label="Key " + key, key=key,
                   use_pulse_true_level=True)
        m = b.node("RangeLogicMotion", 260, -i * 120, label=label, offset_location=loc,
                   offset_rotation=rot, use_local_location=True, use_local_rotation=True)
        b.link(k, m)


def _r_jump(b):
    k = b.node("RangeLogicKey", 0, 0, label="Key Space", key='SPACE')
    g = b.node("RangeLogicRay", 0, -140, label="On Ground", axis='NEGZAXIS', range=1.1)
    a = b.gate("RangeLogicAnd", 240, -40, k, g)
    m = b.node("RangeLogicMotion", 420, -40, label="Jump")
    m.linear_velocity = (0.0, 0.0, 6.0)
    b.link(a, m)


def _r_collect(b):
    t = b.node("RangeLogicCollision", 0, 0, label="Touch Player", property="player")
    r = b.node("RangeLogicRemove", 260, 0, label="Remove")
    m = b.node("RangeLogicMessageSend", 260, -120, label="Collected", subject="collected")
    b.link(t, r)
    b.link(t, m)


def _r_health(b):
    b.prop("health", 'INT', 100)
    hit = b.node("RangeLogicCollision", 0, 0, label="Hit", property="damage")
    dmg = b.node("RangeLogicAddProperty", 260, 0, label="Take Damage", property="health", value="-10")
    b.link(hit, dmg)
    dead = b.node("RangeLogicProperty", 0, -160, label="No Health", property="health",
                  evaluation_type='PROPLESSTHAN', value="1")
    die = b.node("RangeLogicRemove", 260, -160, label="Die")
    b.link(dead, die)


def _r_door(b):
    b.prop("open", 'BOOL', False)
    key = b.node("RangeLogicKey", 0, 0, label="Key E", key='E')
    near = b.node("RangeLogicNear", 0, -140, label="Player Near", property="player",
                  distance=3.0, reset_distance=4.0)
    use = b.gate("RangeLogicAnd", 240, -40, key, near)
    tog = b.node("RangeLogicToggleProperty", 420, -40, label="Toggle Open", property="open")
    b.link(use, tog)
    is_open = b.node("RangeLogicProperty", 0, -300, label="Is Open", property="open",
                     evaluation_type='PROPEQUAL', value="True")
    anim = b.node("RangeLogicAction", 260, -300, label="Door Animation", play_mode='FLIPPER')
    b.link(is_open, anim)


def _r_platform(b):
    frames = {}
    for i, (name, step, other) in enumerate((("Going", 0.03, "Returning"),
                                             ("Returning", -0.03, "Going"))):
        x = i * 760
        f = b.node("NodeFrame", x, 0, parent=b.frame, label=name)
        f.range_logic_state, f.range_logic_initial = True, i == 0
        frames[name] = f
        t = b.node("RangeLogicAlways", x, 0, f, label="Every Frame " + name,
                   use_pulse_true_level=True)
        m = b.node("RangeLogicMotion", x + 260, 0, f, label="Move " + name,
                   offset_location=(0.0, step, 0.0), use_local_location=True)
        b.link(t, m)
        st = b.node("RangeLogicAlways", x, -200, f, label="Start " + name)
        w = b.node("RangeLogicWait", x + 200, -200, f, label="Wait " + name, duration=2.0)
        go = b.node("RangeLogicGoToState", x + 420, -200, f, label="To " + other, state=other)
        b.link(st, w)
        b.link(w, go)


RECIPES = (
    ("WALK", "Walk WASD", _r_walk),
    ("JUMP", "Jump", _r_jump),
    ("COLLECT", "Collect Item", _r_collect),
    ("HEALTH", "Health and Damage", _r_health),
    ("DOOR", "Door with Key", _r_door),
    ("PLATFORM", "Moving Platform", _r_platform),
)


def add_recipe(tree, ident, origin=(0.0, 0.0), objects=()):
    """Põe a receita na árvore como nós comuns num Frame; cria as propriedades
    de jogo que ela usa nos objetos dados.  Devolve o Frame."""
    _id, label, build = next(r for r in RECIPES if r[0] == ident)
    b = _Builder(tree, label, origin)
    build(b)
    for ob in objects:
        for name, typ, value in b.props:
            if name not in ob.game.properties:
                bpy.ops.object.game_property_new(_ops(ob), type=typ, name=name)
                ob.game.properties[name].value = value
    return b.frame


class RANGE_OT_logic_tree_recipe(Operator):
    """Adiciona uma receita pronta, feita de nós comuns que podem ser editados"""
    bl_idname = "node.range_logic_tree_recipe"
    bl_label = "Add Logic Recipe"
    bl_options = {'REGISTER', 'UNDO'}

    recipe = EnumProperty(items=[(i, l, "") for i, l, _f in RECIPES])

    @classmethod
    def poll(cls, context):
        tree = getattr(context.space_data, "edit_tree", None)
        return tree is not None and tree.bl_idname == TREE_ID

    def execute(self, context):
        tree = context.space_data.edit_tree
        users = [ob for ob in bpy.data.objects if ob.logic_tree == tree]
        for n in tree.nodes:
            n.select = False
        add_recipe(tree, self.recipe, tuple(context.space_data.cursor_location), users)
        return {'FINISHED'}


def _draw_recipes(_item, layout, context):
    for ident, label, _f in RECIPES:
        layout.operator(RANGE_OT_logic_tree_recipe.bl_idname, text=label).recipe = ident


# ---------------------------------------------------------------- F7: importar bricks existentes

GATE_OF = {'LOGIC_AND': ("RangeLogicAnd", False), 'LOGIC_OR': ("RangeLogicOr", False),
           'LOGIC_NAND': ("RangeLogicAnd", True), 'LOGIC_NOR': ("RangeLogicOr", True)}
_SKIP_PROPS = {"rna_type", "name", "type", "show_expanded", "pin", "active", "group",
               "debug_intensity", "use_tap_active"}


def _same(a, b):
    try:
        if hasattr(a, "__len__") and not isinstance(a, str):
            return all(abs(x - y) < 1e-6 if isinstance(x, float) else x == y for x, y in zip(a, b))
        if isinstance(a, float):
            return abs(a - b) < 1e-6
        return a == b
    except TypeError:
        return a == b


def _values(brick):
    vals = {}
    for p in brick.bl_rna.properties:
        if p.identifier in _SKIP_PROPS or p.is_readonly:
            continue
        try:
            v = getattr(brick, p.identifier)
        except Exception:
            continue
        vals[p.identifier] = tuple(v) if hasattr(v, "__len__") and not isinstance(v, str) else v
    return vals


def _fits(cls, brick):
    """O nó cls guarda tudo deste brick?  Copia só os campos do nó num brick novo do mesmo
    tipo e compara: campos que dividem memória (value/object_property) se resolvem sozinhos."""
    if cls.brick_type != brick.type:
        return False
    for k, v in cls.fixed.items():
        if not _same(getattr(brick, k), v):
            return False
    kind = cls.kind
    ob = brick.id_data
    getattr(bpy.ops.logic, kind + "_add")(_ops(ob), type=brick.type, name="__fits__", object=ob.name)
    tmp = getattr(ob.game, kind + "s")[-1]
    try:
        for k, v in cls.fixed.items():
            setattr(tmp, k, v)
        for f in tuple(cls.main) + tuple(cls.extra):
            try:
                setattr(tmp, f, getattr(brick, f))
            except (AttributeError, TypeError, ValueError):
                pass
        want, got = _values(brick), _values(tmp)
        return all(k in got and _same(v, got[k]) for k, v in want.items())
    finally:
        getattr(bpy.ops.logic, kind + "_remove")(_ops(ob), **{kind: tmp.name, "object": ob.name})


def _node_class(brick, kind):
    pool = TRIGGER_NODES if kind == "sensor" else ACTION_NODES
    # o mais específico primeiro (com valores fixos), o "all modes" por último
    for cls in sorted((c for c in pool if issubclass(c, BrickNode) and c.kind == kind),
                      key=lambda c: (-len(c.fixed), len(c.main) + len(c.extra))):
        if _fits(cls, brick):
            return cls
    return None


def import_bricks(ob, tree=None, remove=True):
    """Transforma os bricks do usuário (fora da Logic Tree) em nós.  Controllers que não cabem
    (Expression, Xor, Python em modo Script, brick sem nó equivalente) ficam como bricks.
    Devolve (árvore, nº de controllers importados, avisos)."""
    game = ob.game
    rec = _record(ob)
    mine = {k: set(rec.get(k, ())) for k in ("sensors", "controllers", "actuators")}
    ctrls = [c for c in game.controllers if c.name not in mine["controllers"]]
    warnings, plan_ok = [], []
    for c in ctrls:
        sens = [s for s in game.sensors if s.name not in mine["sensors"]
                and any(x.name == c.name for x in s.controllers)]
        acts = [a for a in c.actuators if a.name not in mine["actuators"]]
        why = ""
        if c.type == 'PYTHON' and (c.mode != 'MODULE' or "." not in c.module):
            why = "Python em modo Script"
        elif c.type not in GATE_OF and c.type != 'PYTHON':
            why = c.type.replace("LOGIC_", "").title()
        elif not sens:
            why = "sem sensor"
        elif c.type == 'PYTHON' and acts:
            why = "Python com actuators"
        if not why:
            for b, kind in [(s, "sensor") for s in sens] + [(a, "actuator") for a in acts]:
                if _node_class(b, kind) is None:
                    why = "%s \"%s\" sem nó equivalente" % (b.type.title(), b.name)
                    break
        if why:
            warnings.append("%s: ficou como brick (%s)" % (c.name, why))
            continue
        plan_ok.append((c, sens, acts))
    if not plan_ok:
        return tree, 0, warnings

    if tree is None:
        tree = ob.logic_tree or bpy.data.node_groups.new(ob.name + " Logic", TREE_ID)
    ob.logic_tree = tree

    # estados: com mais de um em uso, cada estado vira um Frame de Estado
    states = sorted({c.states for c, _s, _a in plan_ok})
    frames = {}
    if len(states) > 1:
        for i, st in enumerate(states):
            f = tree.nodes.new("NodeFrame")
            f.range_logic_state = True
            f.label = game.state_names[st - 1].name or "State %d" % st
            f.range_logic_initial = game.states_initial[st - 1]
            f.location = (i * 1100.0, 0.0)
            frames[st] = f

    def make(cls, brick):
        node = tree.nodes.new(cls.bl_idname)
        node.label = brick.name
        node.mute = not brick.active  # brick desligado no checkbox vira nó desligado
        for f in node.fields():
            try:
                v = getattr(brick, f)
                if not _same(v, getattr(node, f)):
                    setattr(node, f, v)
            except (AttributeError, TypeError, ValueError):
                pass
        return node

    made, rows = {}, {}

    def place(node, st, col):
        frame = frames.get(st)
        row = rows.setdefault((st, col), 0)
        rows[(st, col)] = row + 1
        x0 = frame.location.x if frame else 0.0
        if frame:
            node.parent = frame
        node.location = (x0 + col * 330.0, -row * 220.0)

    for c, sens, acts in plan_ok:
        st = c.states
        outs = []
        for s in sens:
            key = ("sensor", s.name, st)
            if key not in made:
                made[key] = make(_node_class(s, "sensor"), s)
                place(made[key], st, 0)
            outs.append(made[key].outputs[0])
        if c.type == 'PYTHON':
            py = tree.nodes.new(RunPythonNode.bl_idname)
            py.label, py.module, py.use_debug = c.name, c.module, c.use_debug
            py.mute = not c.active
            place(py, st, 2)
            for o in outs:
                tree.links.new(o, py.inputs[0])
            continue
        gate_id, negate = GATE_OF[c.type]
        src = outs[0]
        # controller desligado: precisa de uma porta (mutada) para guardar o "desligado"
        if len(outs) > 1 or (not c.active and not negate):
            # a porta tem 3 entradas: com mais sensores, a próxima porta recebe a anterior + 2
            pending = list(outs)
            src = None
            while pending:
                gate = tree.nodes.new(gate_id)
                place(gate, st, 1)
                take = [src] if src is not None else []
                take += pending[:3 - len(take)]
                pending = pending[3 - (1 if src is not None else 0):]
                for sock, o in zip(gate.inputs, take):
                    tree.links.new(o, sock)
                src = gate.outputs[0]
            gate.mute = not c.active
        if negate:
            n = tree.nodes.new("RangeLogicNot")
            place(n, st, 1)
            tree.links.new(src, n.inputs[0])
            src = n.outputs[0]
            n.mute = not c.active
        for a in acts:
            key = ("actuator", a.name, st)
            if key not in made:
                made[key] = make(_node_class(a, "actuator"), a)
                place(made[key], st, 2)
            tree.links.new(src, made[key].inputs[0])

    if remove:
        done = {c.name for c, _s, _a in plan_ok}
        kept = [c for c in game.controllers if c.name not in done]
        busy_s = {s.name for s in game.sensors if any(x.name not in done for x in s.controllers)}
        busy_a = {a.name for c in kept for a in c.actuators}
        names = {"sensor": {s.name for _c, ss, _a in plan_ok for s in ss} - busy_s,
                 "controller": done,
                 "actuator": {a.name for _c, _s, aa in plan_ok for a in aa} - busy_a}
        for kind, group in names.items():
            for name in group:
                getattr(bpy.ops.logic, kind + "_remove")(_ops(ob), **{kind: name, "object": ob.name})
    return tree, len(plan_ok), warnings


class RANGE_OT_logic_tree_import(Operator):
    """Turn the logic bricks of the active object into Logic Tree nodes (the ones without a node stay as bricks)"""
    bl_idname = "logic.range_logic_tree_import"
    bl_label = "Convert to Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.library is None

    def execute(self, context):
        ob = context.object
        tree, n, warnings = import_bricks(ob)
        for w in warnings:
            self.report({'WARNING'}, w)
        if not n:
            self.report({'INFO'}, "Nenhum brick para importar")
            return {'CANCELLED'}
        errors = compile_object(ob)
        for err in errors:
            self.report({'WARNING'}, err)
        for area in context.screen.areas:
            if area.type == "NODE_EDITOR":
                area.spaces.active.tree_type = TREE_ID
                area.spaces.active.node_tree = tree
        self.report({'INFO'}, "Logic Tree: %d controller(s) importado(s), %d ficaram como brick"
                    % (n, len(warnings)))
        return {'FINISHED'}


# ---------------------------------------------------------------- editor

class RANGE_OT_logic_tree_compile(Operator):
    """Gera os Logic Bricks de todos os objetos que usam uma Logic Tree"""
    bl_idname = "logic.range_logic_tree_compile"
    bl_label = "Compile Logic Tree"

    def execute(self, context):
        errors = compile_all()
        for err in errors:
            self.report({'WARNING'}, err)
        n = sum(1 for ob in bpy.data.objects if ob.logic_tree is not None)
        self.report({'INFO'}, "Logic Tree: %d objeto(s), %d aviso(s)" % (n, len(errors)))
        return {'FINISHED'}


class RANGE_OT_logic_tree_new(Operator):
    """Cria uma Logic Tree para o objeto ativo e abre no Node Editor"""
    bl_idname = "logic.range_logic_tree_new"
    bl_label = "New Logic Tree"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        ob = context.object
        tree = bpy.data.node_groups.new(ob.name + " Logic", TREE_ID)
        note = tree.nodes.new("NodeFrame")
        note.label = "Add > Triggers, Logic, Actions or Recipes"
        note.width, note.height, note.shrink = 300.0, 60.0, False
        ob.logic_tree = tree
        for area in context.screen.areas:
            if area.type == "NODE_EDITOR":
                area.spaces.active.tree_type = TREE_ID
                area.spaces.active.node_tree = tree
        return {'FINISHED'}


def _draw_object_field(layout, context):
    ob = context.object
    if ob is None:
        return
    row = layout.row(align=True)
    row.prop(ob, "logic_tree", text="")
    if ob.logic_tree is None:
        row.operator(RANGE_OT_logic_tree_new.bl_idname, text="", icon="ZOOMIN")
    else:
        row.operator(RANGE_OT_logic_tree_compile.bl_idname, text="", icon="FILE_REFRESH")
    if _has_user_bricks(ob):
        row.operator(RANGE_OT_logic_tree_import.bl_idname, text="Convert to Nodes", icon="NODETREE")


def _has_user_bricks(ob):
    mine = set(_record(ob).get("controllers", ()))
    return ob.library is None and any(c.name not in mine for c in ob.game.controllers)


class NODE_PT_range_logic_tree(Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_label = "Logic Tree"

    @classmethod
    def poll(cls, context):
        tree = getattr(context.space_data, "edit_tree", None)
        return tree is not None and tree.bl_idname == TREE_ID

    def draw(self, context):
        layout = self.layout
        tree = context.space_data.edit_tree

        # árvore: compilar e quem usa
        box = layout.box()
        box.operator(RANGE_OT_logic_tree_compile.bl_idname, icon="FILE_REFRESH")
        users = [ob.name for ob in bpy.data.objects if ob.logic_tree == tree]
        box.label("Objects: %s" % (", ".join(users) if users else "none"), icon="OBJECT_DATA")
        if any("range_logic_fired" in n for n in tree.nodes):
            row = box.row()
            row.label("Green: fired in the last game", icon="INFO")
            row.operator(RANGE_OT_logic_tree_clear_highlight.bl_idname, text="", icon="X")

        # objeto ativo: qual árvore usa, Convert to Nodes
        if context.object is not None:
            box = layout.box()
            box.label("Active Object: %s" % context.object.name, icon="OBJECT_DATAMODE")
            _draw_object_field(box, context)

        node = tree.nodes.active
        if isinstance(node, LogicNode):
            box = layout.box()
            row = box.row()
            row.label(_label(node), icon="NODE")
            row.prop(node, "range_logic_active")
            if isinstance(node, BrickNode):
                if "range_logic_fired" in node:
                    box.label("Fired %d time(s) in the last game" % node["range_logic_fired"])
                box.prop(node, "range_logic_break")
                if node.range_logic_break and not context.scene.game_settings.show_debug_mode:
                    box.label("Turn on the scene Debug Mode", icon="INFO")
                ob = context.object
                if ob is not None and ob.logic_tree == tree:
                    made = bricks_of_node(ob, node)
                    sub = box.box()
                    sub.label("Bricks in %s:" % ob.name if made else "Not compiled in %s yet" % ob.name)
                    if not made:
                        sub.label("(renamed node? press Compile)")
                    for kind, name in made:
                        icon = {"sensor": "TRIA_RIGHT", "controller": "DOT"}.get(kind, "TRIA_LEFT")
                        sub.label(name, icon=icon)
        if node is not None and node.bl_idname == "NodeFrame":
            box = layout.box()
            box.prop(node, "range_logic_state")
            if node.range_logic_state:
                box.prop(node, "label", text="Name")
                box.prop(node, "range_logic_initial")
        _rules, errors = plan(tree)
        if errors:
            box = layout.box()
            for err in errors:
                box.label(err, icon="ERROR")


def _logic_header(self, context):
    self.layout.separator()
    self.layout.label("Logic Tree:")
    _draw_object_field(self.layout, context)


class LogicCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == TREE_ID


CATEGORIES = [
    LogicCategory("RANGE_LOGIC_TRIGGERS", "Triggers",
                  items=[NodeItem(c.bl_idname) for c in TRIGGER_NODES]),
    LogicCategory("RANGE_LOGIC_GATES", "Logic",
                  items=[NodeItem(c.bl_idname) for c in GATE_NODES]),
    LogicCategory("RANGE_LOGIC_ACTIONS", "Actions",
                  items=[NodeItem(c.bl_idname) for c in ACTION_NODES]),
    LogicCategory("RANGE_LOGIC_RECIPES", "Recipes",
                  items=[nodeitems_utils.NodeItemCustom(draw=_draw_recipes)]),
    LogicCategory("RANGE_LOGIC_LAYOUT", "Layout",
                  items=[NodeItem("NodeFrame"), NodeItem("NodeReroute")]),
]

CLASSES = (LogicTree, PulseSocket) + TRIGGER_NODES + GATE_NODES + ACTION_NODES + (
    RANGE_OT_logic_tree_compile, RANGE_OT_logic_tree_new, RANGE_OT_logic_tree_recipe,
    RANGE_OT_logic_tree_clear_highlight, RANGE_OT_logic_tree_import, NODE_PT_range_logic_tree)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.logic_tree = PointerProperty(
        type=LogicTree, name="Logic Tree",
        description="Lógica por nós deste objeto; vira Logic Bricks ao jogar e ao salvar")
    bpy.types.Object.logic_tree_record = StringProperty(
        name="Logic Tree Record", options={'HIDDEN'},
        description="Bricks gerados pela Logic Tree (apagados e recriados a cada compilação)")
    bpy.types.NodeFrame.range_logic_state = BoolProperty(
        name="Logic State", description="Logic Tree: os nós dentro deste Frame valem só neste estado")
    bpy.types.NodeFrame.range_logic_initial = BoolProperty(
        name="Initial State", description="Logic Tree: o objeto começa neste estado")
    nodeitems_utils.register_node_categories("RANGE_LOGIC_TREE", CATEGORIES)
    bpy.types.LOGIC_HT_header.append(_logic_header)
    bpy.types.NODE_HT_header.append(_node_header)
    global _live_handle
    _live_handle = bpy.types.SpaceNodeEditor.draw_handler_add(_draw_live, (), 'WINDOW', 'POST_VIEW')
    for handlers in (bpy.app.handlers.game_pre, bpy.app.handlers.save_pre):
        if _auto_compile not in handlers:
            handlers.append(_auto_compile)
    for handlers, fn in ((bpy.app.handlers.game_pre, _trace_pre), (bpy.app.handlers.game_post, _trace_post)):
        if fn not in handlers:
            handlers.append(fn)


def unregister():
    for handlers, fn in ((bpy.app.handlers.game_pre, _trace_pre), (bpy.app.handlers.game_post, _trace_post)):
        if fn in handlers:
            handlers.remove(fn)
    for handlers in (bpy.app.handlers.game_pre, bpy.app.handlers.save_pre):
        if _auto_compile in handlers:
            handlers.remove(_auto_compile)
    global _live_handle
    if _live_handle is not None:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_live_handle, 'WINDOW')
        _live_handle = None
    bpy.types.NODE_HT_header.remove(_node_header)
    bpy.types.LOGIC_HT_header.remove(_logic_header)
    nodeitems_utils.unregister_node_categories("RANGE_LOGIC_TREE")
    del bpy.types.NodeFrame.range_logic_initial
    del bpy.types.NodeFrame.range_logic_state
    del bpy.types.Object.logic_tree_record
    del bpy.types.Object.logic_tree
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
