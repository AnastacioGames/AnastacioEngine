# Logic Tree, F0: provas no editor (bpy em background).
#   3. campos do nó gerados a partir do RNA dos bricks (enum, vetor, ponteiro para ID) e cópia para o brick real;
#   4. Object.logic_tree e a lista de regeneração sobrevivem a salvar/reabrir, cópia do objeto e append;
#      compilar no save_pre não deixa o arquivo sujo depois de salvar;
#   5. tempo para gerar e regenerar ~100 bricks em 20 objetos.
# Uso: AnastacioEngine -b --factory-startup --python f0_editor_probe.py -- <pasta_temporaria>
import bpy, os, sys, time, json
from bpy.props import (BoolProperty, BoolVectorProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, IntVectorProperty, PointerProperty, StringProperty)
from bpy.types import Node, NodeTree

tmp = sys.argv[sys.argv.index("--") + 1]
os.makedirs(tmp, exist_ok=True)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail))


# ---------------------------------------------------------------- 3. campos a partir do RNA
def prop_from_rna(p):
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
        kw.update(min=p.hard_min, max=p.hard_max, soft_min=p.soft_min, soft_max=p.soft_max, subtype=p.subtype)
        if p.type == 'FLOAT':
            kw["precision"] = p.precision
        if p.is_array:
            cls = IntVectorProperty if p.type == 'INT' else FloatVectorProperty
            return cls(size=p.array_length, default=tuple(p.default_array), **kw)
        cls = IntProperty if p.type == 'INT' else FloatProperty
        return cls(default=p.default, **kw)
    if p.type == 'STRING':
        return StringProperty(default=p.default, **kw)
    if p.type == 'POINTER' and issubclass(getattr(bpy.types, p.fixed_type.identifier), bpy.types.ID):
        return PointerProperty(type=getattr(bpy.types, p.fixed_type.identifier), **kw)
    raise TypeError("%s: tipo %s sem conversão" % (p.identifier, p.type))


class ProbeTree(NodeTree):
    bl_idname = "LTProbeTree"
    bl_label = "Logic Tree (prova)"


SPECS = {
    # nó: (tipo do brick, tipo RNA, campos)
    "Keyboard": ("sensor", 'KEYBOARD', bpy.types.KeyboardSensor,
                 ["key", "modifier_key_1", "use_all_keys", "use_pulse_true_level", "use_tap", "invert"]),
    "Motion": ("actuator", 'MOTION', bpy.types.ObjectActuator,
               ["mode", "offset_location", "offset_rotation", "use_local_location", "linear_velocity"]),
    "Action": ("actuator", 'ACTION', bpy.types.ActionActuator,
               ["action", "play_mode", "frame_start", "frame_end", "layer"]),
}
classes = [ProbeTree]
for label, (_kind, _typ, rna, fields) in SPECS.items():
    attrs = {"bl_idname": "LTProbe" + label, "bl_label": label, "fields": fields}
    missing = []
    for f in fields:
        if f not in rna.bl_rna.properties:
            missing.append(f)
            continue
        attrs[f] = prop_from_rna(rna.bl_rna.properties[f])
    check("3 campos RNA de %s" % label, not missing, "faltando: %s" % missing if missing else "")
    classes.append(type("LTProbe" + label, (Node,), attrs))

registered = True
for cls in classes:
    try:
        bpy.utils.register_class(cls)
    except Exception as e:  # noqa: BLE001 - qualquer erro de registro reprova a prova
        registered = False
        print("register", cls.__name__, e)
check("3 registro das classes de nó geradas", registered)

act = bpy.data.actions.new("Pulo")
tree = bpy.data.node_groups.new("Prova", ProbeTree.bl_idname)
nk = tree.nodes.new("LTProbeKeyboard")
nk.key, nk.use_pulse_true_level, nk.modifier_key_1 = 'SPACE', True, 'LEFT_SHIFT'
nm = tree.nodes.new("LTProbeMotion")
nm.offset_location, nm.use_local_location = (0.0, 0.1, 0.0), True
na = tree.nodes.new("LTProbeAction")
na.action, na.play_mode, na.frame_end = act, 'FLIPPER', 24.0

sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
ob = bpy.data.objects.new("Player", None)
sc.objects.link(ob)


def to_brick(ob, node, name):
    kind, typ, _rna, fields = SPECS[node.bl_label]
    getattr(bpy.ops.logic, kind + "_add")(type=typ, name=name, object=ob.name)
    brick = getattr(ob.game, kind + "s")[-1]
    for f in node.fields:
        value = getattr(node, f)
        setattr(brick, f, tuple(value) if hasattr(value, "__len__") and not isinstance(value, (str, set)) else value)
    return brick


bk, bm, ba = to_brick(ob, nk, "Tecla"), to_brick(ob, nm, "Andar"), to_brick(ob, na, "Animar")
check("3 Keyboard copiado", bk.key == 'SPACE' and bk.use_pulse_true_level and bk.modifier_key_1 == 'LEFT_SHIFT')
check("3 Motion copiado (vetor)", abs(bm.offset_location[1] - 0.1) < 1e-6 and bm.use_local_location)
check("3 Action copiado (ponteiro para ID)", ba.action == act and ba.play_mode == 'FLIPPER' and ba.frame_end == 24.0)
check("3 enum de teclas completo", len(bpy.types.KeyboardSensor.bl_rna.properties["key"].enum_items)
      == len(type(nk).bl_rna.properties["key"].enum_items))

# ---------------------------------------------------------------- 4. atribuição e lista de regeneração
bpy.types.Object.logic_tree = PointerProperty(type=bpy.types.NodeTree, name="Logic Tree")
bpy.types.Object.logic_tree_record = StringProperty(name="Logic Tree Record", options={'HIDDEN'})
ob.logic_tree = tree
ob.logic_tree_record = json.dumps({"sensors": ["Tecla"], "actuators": ["Andar", "Animar"], "controllers": []})


@bpy.app.handlers.persistent
def compile_on_save(_scene):
    # simula a compilação: apaga o que foi gerado e cria de novo
    for o in bpy.data.objects:
        if o.logic_tree and o.logic_tree_record:
            rec = json.loads(o.logic_tree_record)
            for name in rec["sensors"]:
                bpy.ops.logic.sensor_remove(sensor=name, object=o.name)
            getattr(bpy.ops.logic, "sensor_add")(type='KEYBOARD', name="Tecla", object=o.name)
            o.game.sensors[-1].key = 'SPACE'


bpy.app.handlers.save_pre.append(compile_on_save)
path = os.path.join(tmp, "f0_probe.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
check("4 arquivo limpo depois de compilar no save_pre", not bpy.data.is_dirty)
check("4 save_pre recriou o sensor sem duplicar", [s.name for s in ob.game.sensors].count("Tecla") == 1)
bpy.app.handlers.save_pre.remove(compile_on_save)

bpy.ops.wm.open_mainfile(filepath=path)
ob = bpy.data.objects["Player"]
check("4 logic_tree após reabrir", ob.logic_tree is not None and ob.logic_tree.name == "Prova")
check("4 registro após reabrir", json.loads(ob.logic_tree_record)["actuators"] == ["Andar", "Animar"])
cp = ob.copy()
bpy.context.scene.objects.link(cp)
check("4 cópia do objeto mantém árvore e registro",
      cp.logic_tree == ob.logic_tree and cp.logic_tree_record == ob.logic_tree_record)

bpy.ops.wm.read_factory_settings()
bpy.ops.wm.append(directory=path + "/Object/", filename="Player")
app = bpy.data.objects.get("Player")
check("4 append traz a árvore junto", app is not None and app.logic_tree is not None
      and app.logic_tree.bl_idname == ProbeTree.bl_idname, str(app and app.logic_tree))
check("4 append traz o registro", app is not None and bool(app.logic_tree_record))

# ---------------------------------------------------------------- 5. tempo de compilação
bpy.ops.wm.read_factory_settings()
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
objs = []
for i in range(20):
    o = bpy.data.objects.new("Obj%02d" % i, None)
    sc.objects.link(o)
    objs.append(o)


def generate(o):
    names = {"sensors": [], "controllers": [], "actuators": []}
    for j in range(35):
        bpy.ops.logic.sensor_add(type='KEYBOARD', name="LT_s%d" % j, object=o.name)
        names["sensors"].append(o.game.sensors[-1].name)
    for j in range(35):
        bpy.ops.logic.actuator_add(type='MOTION', name="LT_a%d" % j, object=o.name)
        names["actuators"].append(o.game.actuators[-1].name)
    for j in range(30):
        bpy.ops.logic.controller_add(type='LOGIC_AND', name="LT_c%d" % j, object=o.name)
        c = o.game.controllers[-1]
        c.link(sensor=o.game.sensors[j])
        c.link(actuator=o.game.actuators[j])
        names["controllers"].append(c.name)
    return names


def remove(o, names):
    for n in names["sensors"]:
        bpy.ops.logic.sensor_remove(sensor=n, object=o.name)
    for n in names["controllers"]:
        bpy.ops.logic.controller_remove(controller=n, object=o.name)
    for n in names["actuators"]:
        bpy.ops.logic.actuator_remove(actuator=n, object=o.name)


t0 = time.perf_counter()
recs = [generate(o) for o in objs]
t1 = time.perf_counter()
for o, r in zip(objs, recs):
    remove(o, r)
recs = [generate(o) for o in objs]
t2 = time.perf_counter()
counts = {len(o.game.sensors) + len(o.game.controllers) + len(o.game.actuators) for o in objs}
check("5 regenerar não duplica", counts == {100}, str(counts))
print("TEMPO gerar 20x100 bricks: %.0f ms; regenerar: %.0f ms" % ((t1 - t0) * 1000, (t2 - t1) * 1000))
check("5 regenerar 20x100 bricks abaixo de 2 s", t2 - t1 < 2.0)

failed = [n for n, ok in results if not ok]
print("RESULTADO %s: %d provas, %d falhas %s" % ("PASS" if not failed else "FAIL", len(results), len(failed), failed))
sys.exit(0 if not failed else 1)
