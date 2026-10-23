# Logic Tree, F2: Then, Frames de Estado e Go To State.  Plataforma vai-e-volta só com nós.
# Uso: AnastacioEngine -b --factory-startup --python f2_compile_test.py -- <pasta>
#      AnastacioRuntime --server <pasta>/f2.range        (grava <pasta>/f2.txt e fecha)
#      python3 f2_runtime_check.py <pasta>/f2.txt
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


box = empty("Box")
sc.objects.active = box
for n in ("pos", "ticks", "voltas"):
    bpy.ops.object.game_property_new(type='INT', name=n)

# estado do usuário já nomeado: a árvore não pode pegar esse número
box.game.state_names[0].name = "Meu"
bpy.ops.logic.controller_add(type='LOGIC_AND', name="Meu Controller", object="Box")
box.game.controllers[-1].states = 1

tree = bpy.data.node_groups.new("Plataforma", lt.TREE_ID)
N, L = tree.nodes, tree.links.new


def frame(label, x, initial=False):
    f = N.new("NodeFrame")
    f.label, f.range_logic_state, f.range_logic_initial = label, True, initial
    f.location = (x, 0)
    return f


def node(kind, parent=None, **kw):
    n = N.new(kind)
    for k, v in kw.items():
        setattr(n, k, v)
    if parent is not None:
        n.parent = parent
    return n


volta = frame("Voltando", 800)
indo = frame("Indo", 0, initial=True)          # inicial mesmo não sendo o primeiro criado
for f, step, other in ((indo, "1", "Voltando"), (volta, "-1", "Indo")):
    tick = node("RangeLogicAlways", f, label="Cada Frame " + f.label, use_pulse_true_level=True)
    move = node("RangeLogicAddProperty", f, label="Mover " + f.label, property="pos", value=step)
    L(tick.outputs[0], move.inputs[0])
    start = node("RangeLogicAlways", f, label="Entrou " + f.label)
    wait = node("RangeLogicWait", f, label="Espera " + f.label, duration=0.5)
    L(start.outputs[0], wait.inputs[0])
    go = node("RangeLogicGoToState", f, label="Para " + other, state=other)
    L(wait.outputs[0], go.inputs[0])                                    # Then → Go To State
# fora de Frame: vale em todos os estados
always = node("RangeLogicAlways", label="Sempre", use_pulse_true_level=True)
count = node("RangeLogicAddProperty", label="Contar", property="ticks", value="1")
L(always.outputs[0], count.inputs[0])
# o mesmo Then também soma uma volta
lap = node("RangeLogicAddProperty", indo, label="Volta", property="voltas", value="1")
L(next(n for n in N if n.label == "Espera Indo").outputs[0], lap.inputs[0])
orphan_wait = node("RangeLogicWait", label="Espera Solta")             # sem gatilho
orphan = node("RangeLogicAddProperty", label="Nunca", property="ticks", value="100")
L(orphan_wait.outputs[0], orphan.inputs[0])
bad_go = node("RangeLogicGoToState", label="Para Lugar Nenhum", state="Nada")
L(always.outputs[0], bad_go.inputs[0])

box.logic_tree = tree
errors = lt.compile_object(box)
g = box.game
print("ERROS", errors)
check("erros: Then sem gatilho e estado inexistente",
      len(errors) == 2 and any("Espera Solta" in e for e in errors)
      and any("Nada" in e for e in errors))
names = [s.name for s in g.state_names]
check("nomes de estado", names[:3] == ["Meu", "Indo", "Voltando"], str(names[:4]))
init = [i + 1 for i, on in enumerate(g.states_initial) if on]
check("estado inicial: Indo (2) + o 1 do usuário", init == [1, 2], str(init))
ctl = {c.name: c.states for c in g.controllers}
print("CONTROLLERS", sorted(ctl.items()))
check("controller de Frame no estado do Frame",
      ctl["Mover Indo"] == 2 and ctl["Mover Voltando"] == 3 and ctl["Para Voltando + Volta"] == 2)
contar = sorted(c.states for c in g.controllers if c.name.startswith("Contar"))
check("nó fora de Frame em todos os estados usados", contar == [1, 2, 3], str(contar))
then = [s for s in g.sensors if s.type == 'ACTUATOR']
check("Then = sensor Actuator Finished, um por ação",
      len(then) == 2 and all(s.mode == 'FINISHED' for s in then)
      and {s.actuator for s in then} == {"Espera Indo", "Espera Voltando"}, str([s.name for s in then]))
st = {a.name: (a.operation, [i + 1 for i, on in enumerate(a.states) if on])
      for a in g.actuators if a.type == 'STATE'}
print("STATE", st)
check("Go To State = Remove dos outros + Add do destino",
      st.get("Para Voltando") == ('ADD', [3]) and st.get("Para Voltando (out)") == ('REMOVE', [2])
      and st.get("Para Indo") == ('ADD', [2]) and st.get("Para Indo (out)") == ('REMOVE', [3]))
volta_c = g.controllers["Para Voltando + Volta"]
check("um Then, duas ações: um controller (Remove, Add, Volta)", len(volta_c.actuators) == 3)

counts = (len(g.sensors), len(g.actuators), len(g.controllers))
lt.compile_object(box)
check("recompilar não duplica nem muda estados",
      (len(g.sensors), len(g.actuators), len(g.controllers)) == counts
      and [s.name for s in g.state_names][:3] == ["Meu", "Indo", "Voltando"]
      and [i + 1 for i, on in enumerate(g.states_initial) if on] == [1, 2])

# tirar a árvore desfaz nomes e estado inicial
box.logic_tree = None
lt.compile_object(box)
check("desligar a árvore restaura estados",
      [s.name for s in g.state_names][:3] == ["Meu", "", ""]
      and [i + 1 for i, on in enumerate(g.states_initial) if on] == [1]
      and [c.name for c in g.controllers] == ["Meu Controller"])

# objeto sem estados próprios: Frame inicial vira o único estado inicial
plain = empty("Plain")
plain.logic_tree = tree
lt.compile_object(plain)
pi = [i + 1 for i, on in enumerate(plain.game.states_initial) if on]
check("objeto limpo: Indo = 1, inicial só ele",
      plain.game.state_names[0].name == "Indo" and pi == [1], str(pi))
bpy.data.objects.remove(plain, do_unlink=True)

# cena de runtime: Box sem o controller do usuário
box.game.controllers[0].states = 1
bpy.ops.logic.controller_remove(controller="Meu Controller", object="Box")
box.game.state_names[0].name = ""
bad_go.state = "Indo"
L(always.outputs[0], bad_go.inputs[0])
N.remove(bad_go)
N.remove(orphan)
N.remove(orphan_wait)
box.logic_tree = tree
check("árvore válida sem erros", lt.compile_object(box) == [])

SRC = '''import bge


def step(cont):
    own = cont.owner
    box = bge.logic.getCurrentScene().objects["Box"]
    n = own.get("n", 0)
    own["log"] = own.get("log", "") + "%d %d %d %d %d\\n" % (n, box.state, box["pos"], box["ticks"], box["voltas"])
    own["n"] = n + 1
    if n >= 200:
        open(r"RES_PATH", "w").write(own["log"])
        bge.logic.endGame()
'''.replace("RES_PATH", os.path.join(tmp, "f2.txt"))
bpy.data.texts.new("drv.py").from_string(SRC)
drv = empty("Driver")
sc.objects.active = drv
bpy.ops.logic.sensor_add(type='ALWAYS', name="Tick", object="Driver")
drv.game.sensors[-1].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="drv", object="Driver")
c = drv.game.controllers[-1]
c.mode, c.module = 'MODULE', "drv.step"
c.link(sensor=drv.game.sensors[-1])

path = os.path.join(tmp, "f2.range")
bpy.ops.wm.save_as_mainfile(filepath=path)
bpy.ops.wm.open_mainfile(filepath=path)
bpy.ops.wm.save_mainfile()
g = bpy.data.objects["Box"].game
check("salvar/reabrir/salvar estável", [s.name for s in g.state_names][:2] == ["Indo", "Voltando"]
      and [i + 1 for i, on in enumerate(g.states_initial) if on] == [1])

failed = [n for n, ok in results if not ok]
print("RESULTADO %s: %d provas, %d falhas %s" % ("PASS" if not failed else "FAIL", len(results), len(failed), failed))
sys.exit(0 if not failed else 1)
