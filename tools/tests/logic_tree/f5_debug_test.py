# Logic Tree, F5: nó <-> brick no registro e "Pause When Fired" (actuator Scene Suspend só com Debug Mode).
# Uso: AnastacioEngine -b --factory-startup --python f5_debug_test.py -- <pasta>
#      AnastacioRuntime --server <pasta>/f5.range        (grava <pasta>/f5.txt e fecha)
#      python3 f5_runtime_check.py <pasta>/f5.txt
import bpy, os, sys
import range_logic_tree as lt

tmp = sys.argv[sys.argv.index("--") + 1]
os.makedirs(tmp, exist_ok=True)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail))


sc = bpy.context.scene
sc.name = "Main"
sc.render.engine = 'BLENDER_GAME'
for o in list(sc.objects):
    bpy.data.objects.remove(o, do_unlink=True)


def empty(scene, name):
    o = bpy.data.objects.new(name, None)
    scene.objects.link(o)
    return o


box = empty(sc, "Box")
sc.objects.active = box
for p in ("n", "hit", "key"):
    bpy.ops.object.game_property_new(type='INT', name=p)

tree = bpy.data.node_groups.new("Debug", lt.TREE_ID)
always = tree.nodes.new("RangeLogicAlways")
always.label, always.use_pulse_true_level = "Sempre", True
count = tree.nodes.new("RangeLogicAddProperty")
count.label, count.property, count.value = "Conta", "n", "1"
tree.links.new(always.outputs[0], count.inputs[0])
delay = tree.nodes.new("RangeLogicDelay")
delay.label, delay.delay = "Espera 20", 20
hit = tree.nodes.new("RangeLogicAddProperty")
hit.label, hit.property, hit.value = "Bate", "hit", "1"
hit.range_logic_break = True  # pausa pela ação
tree.links.new(delay.outputs[0], hit.inputs[0])
key = tree.nodes.new("RangeLogicKey")
key.label = "Tecla"
key.range_logic_break = True  # pausa pelo gatilho
kset = tree.nodes.new("RangeLogicSetProperty")
kset.label, kset.property, kset.value = "Marca", "key", "1"
tree.links.new(key.outputs[0], kset.inputs[0])
box.logic_tree = tree
g = box.game


def scene_acts():
    return [a for a in g.actuators if a.type == 'SCENE']


# Debug Mode desligado: nada de pausa no jogo
sc.game_settings.show_debug_mode = False
check("compila sem erro", lt.compile_object(box) == [])
check("sem Debug Mode não gera pausa", not scene_acts(), str([a.name for a in scene_acts()]))
check("rótulo marcado com *", hit.draw_label() == "* Bate" and count.draw_label() == "Conta")

# nó <-> brick
made = lt.bricks_of_node(box, hit)
check("bricks_of_node da ação", ("actuator", "Bate") in made and any(k == "controller" for k, _ in made),
      str(made))
check("bricks_of_node do gatilho", lt.bricks_of_node(box, delay) == [("sensor", "Espera 20")],
      str(lt.bricks_of_node(box, delay)))
check("node_of_brick", lt.node_of_brick(box, "sensor", "Tecla") == key
      and lt.node_of_brick(box, "actuator", "Conta") == count
      and lt.node_of_brick(box, "sensor", "nada") is None)

# Debug Mode ligado
sc.game_settings.show_debug_mode = True
check("compila com Debug Mode", lt.compile_object(box) == [])
acts = scene_acts()
check("dois actuators de pausa", sorted(a.name for a in acts) == ["Pause: Bate", "Pause: Tecla"],
      str([a.name for a in acts]))
check("pausa = Suspend da própria cena", all(a.mode == 'SUSPEND' and a.scene == sc for a in acts))
ctrl_hit = [c for c in g.controllers if any(a.name == "Bate" for a in c.actuators)]
check("pausa da ação ligada ao controller da ação",
      len(ctrl_hit) == 1 and any(a.name == "Pause: Bate" for a in ctrl_hit[0].actuators))
ctrl_key = [c for c in g.controllers if c.name == "Pause: Tecla"]
check("pausa do gatilho tem controller próprio",
      len(ctrl_key) == 1 and any(c.name == "Pause: Tecla" for c in g.sensors["Tecla"].controllers)
      and [a.name for a in ctrl_key[0].actuators] == ["Pause: Tecla"])
check("pausa no registro do nó", ("actuator", "Pause: Bate") in lt.bricks_of_node(box, hit))
n_bricks = (len(g.sensors), len(g.controllers), len(g.actuators))
lt.compile_object(box)
check("recompilar não duplica", n_bricks == (len(g.sensors), len(g.controllers), len(g.actuators)))
key.range_logic_break = False
lt.compile_object(box)
check("desmarcar tira a pausa", [a.name for a in scene_acts()] == ["Pause: Bate"])

# registro sobrevive a salvar/reabrir
path = os.path.join(tmp, "f5_edit.range")
bpy.ops.wm.save_as_mainfile(filepath=path)
bpy.ops.wm.open_mainfile(filepath=path)
box = bpy.data.objects["Box"]
tree = box.logic_tree
check("node_of_brick depois de reabrir",
      lt.node_of_brick(box, "actuator", "Pause: Bate") == tree.nodes[hit.name])

# runtime: cena Watch por cima conta ticks e grava; a cena Main deve parar no tick ~20
sc = bpy.data.scenes["Main"]
box.logic_tree.nodes[key.name].range_logic_break = False
lt.compile_object(box)
watch = bpy.data.scenes.new("Watch")
watch.render.engine = 'BLENDER_GAME'
w = empty(watch, "Watcher")
bpy.context.screen.scene = watch
watch.objects.active = w
bpy.ops.logic.sensor_add(type='ALWAYS', name="tick", object=w.name)
w.game.sensors[-1].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="watch", object=w.name)
c = w.game.controllers[-1]
c.mode, c.module = 'MODULE', "vigia.tick"
c.link(sensor=w.game.sensors[-1])
bpy.data.texts.new("vigia.py").from_string('''import bge

ticks = [0]


def tick(cont):
    ticks[0] += 1
    if ticks[0] >= 90:
        main = next(s for s in bge.logic.getSceneList() if s.name == "Main")
        b = main.objects["Box"]
        open(r"RES_PATH", "w").write("%d %d %d\\n" % (ticks[0], b["n"], b["hit"]))
        bge.logic.endGame()
'''.replace("RES_PATH", os.path.join(tmp, "f5.txt")))
bpy.context.screen.scene = sc
sc.objects.active = box
bpy.ops.logic.sensor_add(type='ALWAYS', name="start", object=box.name)
bpy.ops.logic.controller_add(type='LOGIC_AND', name="start", object=box.name)
bpy.ops.logic.actuator_add(type='SCENE', name="overlay", object=box.name)
g = box.game
g.actuators["overlay"].mode, g.actuators["overlay"].scene = 'ADDFRONT', watch
g.controllers["start"].link(sensor=g.sensors["start"], actuator=g.actuators["overlay"])
check("cena de runtime sem erro", lt.compile_object(box) == [])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, "f5.range"))

failed = [n for n, ok in results if not ok]
print("RESULTADO %s: %d provas, %d falhas %s" % ("PASS" if not failed else "FAIL", len(results), len(failed), failed))
sys.exit(0 if not failed else 1)
