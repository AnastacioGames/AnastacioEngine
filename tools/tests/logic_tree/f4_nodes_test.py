# Logic Tree, F4: todos os sensores e actuators viram nós; Run Python vira controller Python.
# Uso: AnastacioEngine -b --factory-startup --python f4_nodes_test.py -- <pasta>
#      AnastacioRuntime --server <pasta>/f4.range        (grava <pasta>/f4.txt e fecha)
import bpy, os, sys
import range_logic_tree as lt

tmp = sys.argv[sys.argv.index("--") + 1]
os.makedirs(tmp, exist_ok=True)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail))


sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
for o in list(sc.objects):
    bpy.data.objects.remove(o, do_unlink=True)


def empty(name):
    o = bpy.data.objects.new(name, None)
    sc.objects.link(o)
    return o


box = empty("Box")
cam_target = empty("Alvo")
sc.objects.active = box
bpy.ops.object.game_property_new(type='INT', name="n")
bpy.ops.object.game_property_new(type='INT', name="py")

# tipos cobertos
s_types = {it.identifier for it in bpy.types.Sensor.bl_rna.properties["type"].enum_items}
a_types = {it.identifier for it in bpy.types.Actuator.bl_rna.properties["type"].enum_items}
have_s = {c.brick_type for c in lt.TRIGGER_NODES}
have_a = {c.brick_type for c in lt.ACTION_NODES if c.kind == "actuator"}
check("todo sensor tem nó", s_types - {'ARMATURE'} <= have_s, str(s_types - have_s))
check("todo actuator tem nó", a_types - {'ARMATURE'} <= have_a, str(a_types - have_a))

tree = bpy.data.node_groups.new("Todos", lt.TREE_ID)
always = tree.nodes.new("RangeLogicAlways")
always.label, always.use_pulse_true_level = "Sempre", True
fill = {"RangeLogicCamera": {"object": cam_target}, "RangeLogicSetProperty": {"property": "n"},
        "RangeLogicAddProperty": {"property": "n"}, "RangeLogicToggleProperty": {"property": "n"},
        "RangeLogicPropertyFull": {"property": "n"}, "RangeLogicSteering": {"target": cam_target},
        "RangeLogicActuatorSensor": {"actuator": "Visibility"}, "RangeLogicGoToState": None,
        "RangeLogicSound": None, "RangeLogicAction": None, "RangeLogicRunPython": None,
        "RangeLogicProperty": {"property": "n"}}
made = 0
for cls in lt.TRIGGER_NODES + lt.ACTION_NODES:
    if cls.bl_idname in fill and fill[cls.bl_idname] is None:
        continue  # precisam de dado externo; testados em outras fases
    n = tree.nodes.new(cls.bl_idname)
    n.label = cls.bl_label
    for k, v in (fill.get(cls.bl_idname) or {}).items():
        setattr(n, k, v)
    if isinstance(n, lt.TriggerNode):
        act = tree.nodes.new("RangeLogicAddProperty")
        act.label, act.property, act.value = "Por " + cls.bl_label, "n", "0"
        tree.links.new(n.outputs[0], act.inputs[0])
    elif n.bl_idname != "RangeLogicAddProperty":
        tree.links.new(always.outputs[0], n.inputs[0])
    made += 1
py = tree.nodes.new("RangeLogicRunPython")
py.label, py.module = "Script", "acao.conta"
tree.links.new(always.outputs[0], py.inputs[0])
box.logic_tree = tree
errors = lt.compile_object(box)
check("tudo compila sem erro", errors == [], str(errors))
g = box.game
gs, ga = {s.type for s in g.sensors}, {a.type for a in g.actuators}
check("cada tipo de sensor gerado", s_types - {'ARMATURE'} <= gs, str(s_types - gs))
check("cada tipo de actuator gerado", (a_types - {'ARMATURE', 'SOUND', 'ACTION'}) <= ga,
      str(a_types - ga))
pyc = [c for c in g.controllers if c.type == 'PYTHON']
check("Run Python = controller Python Module ligado ao gatilho",
      len(pyc) == 1 and pyc[0].mode == 'MODULE' and pyc[0].module == "acao.conta")
cam = next(a for a in g.actuators if a.type == 'CAMERA')
check("campo ponteiro copiado", cam.object == cam_target)

# campo do painel N não mexido fica no padrão do brick; mexido é copiado
ray = next(n for n in tree.nodes if n.bl_idname == "RangeLogicRay")
ray.use_x_ray = True
lt.compile_object(box)
rs = next(s for s in g.sensors if s.type == 'RAY')
check("campo extra alterado chega ao brick", rs.use_x_ray)

# runtime: só o Run Python, numa cena limpa
for o in list(sc.objects):
    bpy.data.objects.remove(o, do_unlink=True)
box = empty("Box")
sc.objects.active = box
bpy.ops.object.game_property_new(type='INT', name="py")
t2 = bpy.data.node_groups.new("Py", lt.TREE_ID)
a2 = t2.nodes.new("RangeLogicAlways")
a2.use_pulse_true_level = True
p2 = t2.nodes.new("RangeLogicRunPython")
p2.module = "acao.conta"
t2.links.new(a2.outputs[0], p2.inputs[0])
box.logic_tree = t2
check("cena de runtime sem erro", lt.compile_object(box) == [])
bpy.data.texts.new("acao.py").from_string('''import bge


def conta(cont):
    own = cont.owner
    if all(s.positive for s in cont.sensors):
        own["py"] += 1
    if own["py"] >= 60:
        open(r"RES_PATH", "w").write("%d %d\\n" % (own["py"], len(cont.sensors)))
        bge.logic.endGame()
'''.replace("RES_PATH", os.path.join(tmp, "f4.txt")))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, "f4.range"))

failed = [n for n, ok in results if not ok]
print("RESULTADO %s: %d provas, %d falhas %s" % ("PASS" if not failed else "FAIL", len(results), len(failed), failed))
sys.exit(0 if not failed else 1)
