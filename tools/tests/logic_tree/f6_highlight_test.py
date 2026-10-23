# Logic Tree, F6: destaque dos nós que dispararam no último jogo (fireCount + registro em JSON).
# Uso: AnastacioEngine -b --factory-startup --python f6_highlight_test.py -- <pasta>
#      (apague %TEMP%/range_logic_trace.json)  AnastacioRuntime --server <pasta>/f6.range
#      AnastacioEngine -b --factory-startup --python f6_highlight_test.py -- <pasta> check
import bpy, json, os, sys
import range_logic_tree as lt

args = sys.argv[sys.argv.index("--") + 1:]
tmp = args[0]
os.makedirs(tmp, exist_ok=True)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail))


def finish():
    failed = [n for n, ok in results if not ok]
    print("RESULTADO %s: %d provas, %d falhas %s" % (
        "PASS" if not failed else "FAIL", len(results), len(failed), failed))
    sys.exit(0 if not failed else 1)


if len(args) > 1 and args[1] == "check":
    bpy.ops.wm.open_mainfile(filepath=os.path.join(tmp, "f6.range"))
    path = lt.trace_path()
    check("runtime gravou o registro", os.path.exists(path), path)
    data = json.load(open(path)) if os.path.exists(path) else {}
    box = data.get("Box", {})
    check("fireCount chegou (sensor e actuator)",
          box.get("sensor:Espera") == 1 and box.get("actuator:Conta", 0) >= 1, str(box))
    fired = lt.apply_trace()
    names = {bpy.data.node_groups["Destaque"].nodes[n].label for n in fired.get("Destaque", [])}
    check("nós que dispararam destacados", {"Sempre", "Conta", "Espera", "Sair"} <= names, str(names))
    check("nós parados sem destaque", not names & {"Tecla", "Marca"}, str(names))
    tree = bpy.data.node_groups["Destaque"]
    conta = next(n for n in tree.nodes if n.label == "Conta")
    check("cor e contagem no nó", conta.use_custom_color and conta.get("range_logic_fired", 0) >= 1)
    lt.clear_highlight()
    check("Clear tira o destaque", not conta.use_custom_color and "range_logic_fired" not in conta)
    finish()

sc = bpy.context.scene
sc.name = "Main"
sc.render.engine = 'BLENDER_GAME'
for o in list(sc.objects):
    bpy.data.objects.remove(o, do_unlink=True)
box = bpy.data.objects.new("Box", None)
sc.objects.link(box)
sc.objects.active = box
for p in ("n", "key"):
    bpy.ops.object.game_property_new(type='INT', name=p)

tree = bpy.data.node_groups.new("Destaque", lt.TREE_ID)


def node(idname, label, **kw):
    n = tree.nodes.new(idname)
    n.label = label
    for k, v in kw.items():
        setattr(n, k, v)
    return n


always = node("RangeLogicAlways", "Sempre", use_pulse_true_level=True)
conta = node("RangeLogicAddProperty", "Conta", property="n", value="1")
tree.links.new(always.outputs[0], conta.inputs[0])
tecla = node("RangeLogicKey", "Tecla")
marca = node("RangeLogicSetProperty", "Marca", property="key", value="1")
tree.links.new(tecla.outputs[0], marca.inputs[0])
espera = node("RangeLogicDelay", "Espera", delay=30)
sair = node("RangeLogicGame", "Sair", mode='QUIT')
tree.links.new(espera.outputs[0], sair.inputs[0])
box.logic_tree = tree
g = box.game

sc.game_settings.show_debug_mode = False
lt.compile_object(box)
check("sem Debug Mode não gera registro", not any(c.type == 'PYTHON' for c in g.controllers)
      and "range_logic_trace.py" not in bpy.data.texts)
sc.game_settings.show_debug_mode = True
check("compila com Debug Mode", lt.compile_object(box) == [])
trace = [c for c in g.controllers if c.type == 'PYTHON']
check("controller de registro", len(trace) == 1 and trace[0].module == "range_logic_trace.start")
check("texto do registro criado", "range_logic_trace.py" in bpy.data.texts)
n_bricks = (len(g.sensors), len(g.controllers), len(g.actuators))
lt.compile_object(box)
check("recompilar não duplica", n_bricks == (len(g.sensors), len(g.controllers), len(g.actuators)))

# revisão F5: objeto em duas cenas usa a cena pedida por compile_all
other = bpy.data.scenes.new("Other")
other.render.engine = 'BLENDER_GAME'
other.objects.link(box)
other.game_settings.show_debug_mode = False
espera.range_logic_break = True
lt.compile_all(other)
check("cena sem Debug Mode: sem pausa", not any(a.type == 'SCENE' for a in g.actuators))
lt.compile_all(sc)
pause = [a for a in g.actuators if a.type == 'SCENE']
check("cena com Debug Mode: pausa nela", len(pause) == 1 and pause[0].scene == sc)
espera.range_logic_break = False
other.objects.unlink(box)
bpy.data.scenes.remove(other, do_unlink=True)
lt.compile_all(sc)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, "f6.range"))
finish()
