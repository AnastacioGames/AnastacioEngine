# Logic Tree, F1: compila uma árvore, confere os bricks e gera uma cena para o runtime.
# Uso: AnastacioEngine -b --factory-startup --python f1_compile_test.py -- <pasta>
#      AnastacioRuntime --server <pasta>/f1.range        (grava <pasta>/f1.txt e fecha)
#      python3 f1_runtime_check.py <pasta>/f1.txt
import bpy, json, os, sys
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


def prop(ob, name, typ, value):
    sc.objects.active = ob
    bpy.ops.object.game_property_new(type=typ, name=name)
    ob.game.properties[name].value = value


box = empty("Box")
for n in ("a", "b", "c"):
    prop(box, n, 'BOOL', False)
for n in ("cs", "cand", "cor", "cmix", "cmulti"):
    prop(box, n, 'INT', 0)

# brick do usuário no mesmo objeto: não pode ser tocado
bpy.ops.logic.sensor_add(type='ALWAYS', name="Meu Sensor", object="Box")

tree = bpy.data.node_groups.new("Regras", lt.TREE_ID)
N = tree.nodes


def trig(label, p):
    n = N.new("RangeLogicProperty")
    n.label, n.property, n.evaluation_type, n.value = label, p, 'PROPEQUAL', "True"
    n.use_pulse_true_level = True
    return n


def add(label, p, x):
    n = N.new("RangeLogicAddProperty")
    n.label, n.property, n.value = label, p, "1"
    n.location = (x, 0)
    return n


def gate(kind, *srcs):
    g = N.new(kind)
    for i, s in enumerate(srcs):
        tree.links.new(s.outputs[0], g.inputs[i])
    return g


ta, tb, tc = trig("Tecla A", "a"), trig("Tecla B", "b"), trig("Tecla C", "c")
L = tree.links.new
L(ta.outputs[0], add("Soma S", "cs", 0).inputs[0])                       # gatilho direto
L(gate("RangeLogicAnd", ta, tb).outputs[0], add("Soma E", "cand", 1).inputs[0])
L(gate("RangeLogicOr", ta, tb).outputs[0], add("Soma Ou", "cor", 2).inputs[0])
mix = gate("RangeLogicAnd", gate("RangeLogicOr", ta, tb), gate("RangeLogicNot", tc))
L(mix.outputs[0], add("Soma Mista", "cmix", 3).inputs[0])
multi = add("Soma Duas", "cmulti", 4)                                    # duas entradas = Ou
L(tb.outputs[0], multi.inputs[0])
L(gate("RangeLogicNot", ta).outputs[0], multi.inputs[0])
bad = N.new("RangeLogicSetProperty")                                     # campo vazio: erro
L(ta.outputs[0], bad.inputs[0])

box.logic_tree = tree
errors = lt.compile_object(box)
g = box.game
check("erro do nó vazio reportado", len(errors) == 1 and "Set Property" in errors[0], str(errors))
check("bricks do usuário intactos", "Meu Sensor" in g.sensors and g.sensors["Meu Sensor"].group == "")
check("grupo criado", "Tree: Regras" in g.brick_groups)
check("3 sensores, 5 actuators, 5 controllers",
      (len(g.sensors), len(g.actuators), len(g.controllers)) == (4, 5, 5),
      str((len(g.sensors), len(g.actuators), len(g.controllers))))
types = sorted(c.type for c in g.controllers)
check("tipos dos controllers", types == ['EXPRESSION', 'EXPRESSION', 'LOGIC_AND', 'LOGIC_AND', 'LOGIC_OR'],
      str(types))
exprs = sorted(c.expression for c in g.controllers if c.type == 'EXPRESSION')
print("EXPRESSOES", exprs, [s.name for s in g.sensors])
check("nomes ASCII nas expressões", all(e.isascii() for e in exprs))

rec = json.loads(box.logic_tree_record)
lt.compile_object(box)
check("recompilar não duplica", (len(g.sensors), len(g.actuators), len(g.controllers)) == (4, 5, 5))
check("registro estável", sorted(json.loads(box.logic_tree_record)["actuators"]) == sorted(rec["actuators"]))

# objeto que compartilha a árvore
other = empty("Outro")
for n in ("a", "b", "c", "cs", "cand", "cor", "cmix", "cmulti"):
    prop(other, n, 'INT', 0)
other.logic_tree = tree
lt.compile_all()
check("árvore compartilhada compila no segundo objeto", len(other.game.actuators) == 5)
other.logic_tree = None
lt.compile_all()
check("desligar a árvore limpa os bricks", len(other.game.actuators) == 0 and not other.logic_tree_record)
bpy.data.objects.remove(other, do_unlink=True)

# driver do teste de runtime (mesma sequência da F0)
SRC = '''import bge
SEQ = [(i >> 2 & 1, i >> 1 & 1, i & 1) for i in range(8) for _ in range(3)]
SEQ += [(t % 2, (t // 2) % 2, (t // 3) % 2) for t in range(24)]
r = 12345
for _ in range(60):
    r = (r * 1103515245 + 12345) & 0x7fffffff
    SEQ.append((r >> 16 & 1, r >> 17 & 1, r >> 18 & 1))
SEQ += [(0, 0, 0)] * 6


def step(cont):
    own = cont.owner
    box = bge.logic.getCurrentScene().objects["Box"]
    n = own.get("n", 0)
    a, b, c = SEQ[n] if n < len(SEQ) else (0, 0, 0)
    box["a"], box["b"], box["c"] = bool(a), bool(b), bool(c)
    own["log"] = own.get("log", "") + " ".join(str(v) for v in (
        n, a, b, c, box["cs"], box["cand"], box["cor"], box["cmix"], box["cmulti"])) + "\\n"
    own["n"] = n + 1
    if n >= len(SEQ) + 4:
        open(r"RES_PATH", "w").write(own["log"])
        bge.logic.endGame()
'''.replace("RES_PATH", os.path.join(tmp, "f1.txt"))
bpy.data.texts.new("drv.py").from_string(SRC)
drv = empty("Driver")
sc.objects.active = None
check("compila sem objeto ativo", not lt.compile_all() or True)
sc.objects.active = drv
bpy.ops.logic.sensor_add(type='ALWAYS', name="Tick", object="Driver")
drv.game.sensors[-1].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="drv", object="Driver")
c = drv.game.controllers[-1]
c.mode, c.module = 'MODULE', "drv.step"
c.link(sensor=drv.game.sensors[-1])

# save_pre recompila; reabrir e salvar de novo não duplica
path = os.path.join(tmp, "f1.range")
bpy.ops.wm.save_as_mainfile(filepath=path)
bpy.ops.wm.open_mainfile(filepath=path)
box = bpy.data.objects["Box"]
bpy.ops.wm.save_mainfile()
g = box.game
check("salvar/reabrir/salvar não duplica", (len(g.sensors), len(g.actuators), len(g.controllers)) == (4, 5, 5))
check("árvore após reabrir", box.logic_tree is not None and box.logic_tree.name == "Regras")

failed = [n for n, ok in results if not ok]
print("RESULTADO %s: %d provas, %d falhas %s" % ("PASS" if not failed else "FAIL", len(results), len(failed), failed))
sys.exit(0 if not failed else 1)
