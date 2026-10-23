# Logic Tree, F3: as 6 receitas entram como nós comuns, compilam e a plataforma anda no runtime.
# Uso: AnastacioEngine -b --factory-startup --python f3_recipes_test.py -- <pasta>
#      AnastacioRuntime --server <pasta>/f3.range        (grava <pasta>/f3.txt e fecha)
#      python3 f3_runtime_check.py <pasta>/f3.txt
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


hero = empty("Hero")
tree = bpy.data.node_groups.new("Hero Logic", lt.TREE_ID)
hero.logic_tree = tree
frames = {}
for i, (ident, label, _f) in enumerate(lt.RECIPES):
    frames[ident] = lt.add_recipe(tree, ident, (0.0, -i * 700.0), [hero])
check("6 receitas, cada uma num Frame com o nome", [f.label for f in frames.values()] ==
      [l for _i, l, _f in lt.RECIPES])
inside = [n for n in tree.nodes if n.bl_idname != "NodeFrame"]
check("todos os nós dentro de um Frame", all(n.parent is not None for n in inside))
check("propriedades criadas no objeto", "health" in hero.game.properties and "open" in hero.game.properties
      and hero.game.properties["health"].value == 100)
lt.add_recipe(tree, "HEALTH", (2000.0, 0.0), [hero])
check("receita repetida não duplica propriedade",
      [p.name for p in hero.game.properties].count("health") == 1)
frame = frames["WALK"]
key = next(n for n in tree.nodes if n.label == "Key W")
loc = lt._pos(key)
check("posição absoluta preservada no Frame", abs(loc[0] - 0.0) < 1 and abs(loc[1] - 0.0) < 1, str(loc))

errors = lt.compile_object(hero)
print("ERROS", errors)
check("só a porta pede a animação (campo Action vazio)",
      len(errors) == 1 and "Door Animation" in errors[0], str(errors))
g = hero.game
check("compila: bricks gerados", len(g.actuators) > 15 and len(g.controllers) > 12,
      "%d s, %d a, %d c" % (len(g.sensors), len(g.actuators), len(g.controllers)))
check("estados da plataforma", [s.name for s in g.state_names][:2] == ["Going", "Returning"])
types = {s.type for s in g.sensors}
check("Ray, Near e Then presentes", {'RAY', 'NEAR', 'ACTUATOR', 'KEYBOARD'} <= types, str(types))

# cena de runtime: só a plataforma, mais rápida
plat = empty("Plat")
pt = bpy.data.node_groups.new("Plat Logic", lt.TREE_ID)
lt.add_recipe(pt, "PLATFORM", (0.0, 0.0), [plat])
for n in pt.nodes:
    if n.bl_idname == "RangeLogicWait":
        n.duration = 0.5
plat.logic_tree = pt
check("plataforma sem erros", lt.compile_object(plat) == [])
bpy.data.objects.remove(hero, do_unlink=True)

SRC = '''import bge


def step(cont):
    own = cont.owner
    p = bge.logic.getCurrentScene().objects["Plat"]
    n = own.get("n", 0)
    own["log"] = own.get("log", "") + "%d %d %.4f\\n" % (n, p.state, p.worldPosition.y)
    own["n"] = n + 1
    if n >= 200:
        open(r"RES_PATH", "w").write(own["log"])
        bge.logic.endGame()
'''.replace("RES_PATH", os.path.join(tmp, "f3.txt"))
bpy.data.texts.new("drv.py").from_string(SRC)
drv = empty("Driver")
sc.objects.active = drv
bpy.ops.logic.sensor_add(type='ALWAYS', name="Tick", object="Driver")
drv.game.sensors[-1].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="drv", object="Driver")
c = drv.game.controllers[-1]
c.mode, c.module = 'MODULE', "drv.step"
c.link(sensor=drv.game.sensors[-1])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, "f3.range"))

failed = [n for n, ok in results if not ok]
print("RESULTADO %s: %d provas, %d falhas %s" % ("PASS" if not failed else "FAIL", len(results), len(failed), failed))
sys.exit(0 if not failed else 1)
