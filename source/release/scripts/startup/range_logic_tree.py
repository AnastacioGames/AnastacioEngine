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


class LogicNode:
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

    def fields(self):
        return self.main + self.extra

    def error(self):
        for f in self.required:
            if not getattr(self, f):
                return "Preencha: %s" % type(self).bl_rna.properties[f].name
        return ""

    def draw_buttons(self, context, layout):
        for f in self.main:
            layout.prop(self, f)
        err = self.error()
        if err:
            layout.label(err, icon="ERROR")

    def draw_buttons_ext(self, context, layout):
        for f in self.fields():
            layout.prop(self, f)

    def update(self):
        err = bool(self.error())
        self.use_custom_color = err
        if err:
            self.color = (0.6, 0.15, 0.15)


class TriggerNode(BrickNode):
    kind = "sensor"

    def init(self, context):
        self.outputs.new(PulseSocket.bl_idname, "Pulse")


class ActionNode(BrickNode):
    kind = "actuator"

    def init(self, context):
        sock = self.inputs.new(PulseSocket.bl_idname, "Do")
        sock.link_limit = 4095


def _brick_node(base, idname, label, rna, brick_type, main, extra=(), fixed=None, required=()):
    attrs = {"bl_idname": idname, "bl_label": label, "brick_type": brick_type,
             "main": tuple(main), "extra": tuple(extra), "fixed": fixed or {},
             "required": tuple(required)}
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
    _brick_node(ActionNode, "RangeLogicSound", "Sound", T.SoundActuator, 'SOUND',
                ("sound", "mode"), ("volume", "pitch"), required=("sound",)),
    _brick_node(ActionNode, "RangeLogicRemove", "Remove Object", T.EditObjectActuator,
                'EDIT_OBJECT', (), fixed={"mode": 'ENDOBJECT'}),
    _brick_node(ActionNode, "RangeLogicWait", "Wait", T.WaitActuator, 'WAIT',
                ("duration",), ("use_restart",)),
)


class GateNode(LogicNode):
    op = ""

    def init(self, context):
        for _ in range(self.n_inputs):
            self.inputs.new(PulseSocket.bl_idname, "In")
        self.outputs.new(PulseSocket.bl_idname, "Pulse")


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
    if node is None or node in stack:
        return None
    if isinstance(node, TriggerNode):
        return ('S', node)
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


def plan(tree):
    """Lista de regras (expressão, ações) da árvore e erros, sem tocar em objetos."""
    rules, errors = {}, []
    for node in tree.nodes:
        if not isinstance(node, ActionNode):
            continue
        if node.error():
            errors.append("%s: %s" % (_label(node), node.error()))
            continue
        exprs = [_expr(n) for n in _sources(node.inputs[0])]
        exprs = [e for e in exprs if e is not None]
        if not exprs:
            continue
        e = exprs[0] if len(exprs) == 1 else ('OR', exprs)
        rules.setdefault(_key(e), [e, []])[1].append(node)
    for node in tree.nodes:
        if isinstance(node, TriggerNode) and node.error():
            errors.append("%s: %s" % (_label(node), node.error()))
    out = sorted(rules.values(), key=lambda r: (r[1][0].location.x, -r[1][0].location.y))
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
    group = rec.get("group")
    if group and group in game.brick_groups and not any(
            b.group == group for kind in ("sensors", "controllers", "actuators")
            for b in getattr(game, kind)):
        game.brick_groups.remove(game.brick_groups[group])
    ob.logic_tree_record = ""


def compile_object(ob):
    """Gera os bricks da árvore do objeto.  Devolve a lista de erros."""
    if ob.library is not None:
        return ["%s: objeto de biblioteca, não compilado" % ob.name]
    clear(ob)
    tree = ob.logic_tree
    if tree is None or tree.bl_idname != TREE_ID:
        return []
    rules, errors = plan(tree)
    game = ob.game
    group = "Tree: " + tree.name
    if group not in game.brick_groups:
        group = game.brick_groups.new(group).name
    rec = {"group": group, "sensors": [], "controllers": [], "actuators": []}
    states = [i + 1 for i, on in enumerate(game.states_initial) if on] or [1]

    def add(kind, typ, name):
        getattr(bpy.ops.logic, kind + "_add")(_ops(ob), type=typ, name=name, object=ob.name)
        brick = getattr(game, kind + "s")[-1]
        brick.group = group
        rec[kind + "s"].append(brick.name)
        return brick

    def fill(brick, node):
        for k, v in node.fixed.items():
            setattr(brick, k, v)
        for f in node.fields():
            value = getattr(node, f)
            if hasattr(value, "__len__") and not isinstance(value, (str, set)) \
                    and not isinstance(value, bpy.types.ID):
                value = tuple(value)
            setattr(brick, f, value)

    # quais gatilhos aparecem dentro de um Expression: esses precisam de nome ASCII
    in_expr = set()
    for e, _acts in rules:
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

    for e, _acts in rules:
        _neg(e, False)

    sensors, actuators = {}, {}
    used = set(RESERVED) | {p.name.upper() for p in game.properties}
    for e, acts in rules:
        tr = []
        _triggers(e, tr)
        for node in tr:
            if node in sensors:
                continue
            name = _label(node)
            if node in in_expr:
                base, n = _ascii(name), 1
                name = base
                while name.upper() in used or name in game.sensors:
                    n += 1
                    name = "%s_%d" % (base, n)
                used.add(name.upper())
            s = add("sensor", node.brick_type, name)
            fill(s, node)
            if node in negated:
                s.use_pulse_false_level = True
            sensors[node] = s
        for node in acts:
            if node not in actuators:
                a = add("actuator", node.brick_type, _label(node))
                fill(a, node)
                actuators[node] = a

    for e, acts in rules:
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
        name = " + ".join(_label(a) for a in acts)
        for state in states:
            c = add("controller", typ, name)
            c.states = state
            if text is not None:
                c.expression = text
            for n in linked:
                c.link(sensor=sensors[n])
            for a in acts:
                c.link(actuator=actuators[a])

    ob.logic_tree_record = json.dumps(rec)
    return errors


def compile_all(scene=None):
    errors = []
    for ob in bpy.data.objects:
        if ob.logic_tree is not None or ob.logic_tree_record:
            errors += compile_object(ob)
    return errors


@bpy.app.handlers.persistent
def _auto_compile(_scene):
    """Compila ao apertar P e ao salvar (o export salva): o jogo nunca roda lógica velha."""
    try:
        for err in compile_all():
            print("[Logic Tree] %s" % err)
    except Exception as exc:  # compilação quebrada não pode impedir de jogar/salvar
        print("[Logic Tree] Compilação falhou: %s" % exc)


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
        note.label = "Add > Triggers, Logic, Actions"
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
        layout.operator(RANGE_OT_logic_tree_compile.bl_idname, icon="FILE_REFRESH")
        users = [ob.name for ob in bpy.data.objects if ob.logic_tree == tree]
        layout.label("Objetos: %s" % (", ".join(users) if users else "nenhum"))
        if context.object is not None:
            layout.label("Objeto ativo:")
            _draw_object_field(layout, context)
        _rules, errors = plan(tree)
        for err in errors:
            layout.label(err, icon="ERROR")


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
    LogicCategory("RANGE_LOGIC_LAYOUT", "Layout",
                  items=[NodeItem("NodeFrame"), NodeItem("NodeReroute")]),
]

CLASSES = (LogicTree, PulseSocket) + TRIGGER_NODES + GATE_NODES + ACTION_NODES + (
    RANGE_OT_logic_tree_compile, RANGE_OT_logic_tree_new, NODE_PT_range_logic_tree)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.logic_tree = PointerProperty(
        type=LogicTree, name="Logic Tree",
        description="Lógica por nós deste objeto; vira Logic Bricks ao jogar e ao salvar")
    bpy.types.Object.logic_tree_record = StringProperty(
        name="Logic Tree Record", options={'HIDDEN'},
        description="Bricks gerados pela Logic Tree (apagados e recriados a cada compilação)")
    nodeitems_utils.register_node_categories("RANGE_LOGIC_TREE", CATEGORIES)
    bpy.types.LOGIC_HT_header.append(_logic_header)
    for handlers in (bpy.app.handlers.game_pre, bpy.app.handlers.save_pre):
        if _auto_compile not in handlers:
            handlers.append(_auto_compile)


def unregister():
    for handlers in (bpy.app.handlers.game_pre, bpy.app.handlers.save_pre):
        if _auto_compile in handlers:
            handlers.remove(_auto_compile)
    bpy.types.LOGIC_HT_header.remove(_logic_header)
    nodeitems_utils.unregister_node_categories("RANGE_LOGIC_TREE")
    del bpy.types.Object.logic_tree_record
    del bpy.types.Object.logic_tree
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
