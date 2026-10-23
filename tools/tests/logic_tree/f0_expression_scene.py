# Logic Tree, F0: o controller Expression pode substituir portas And/Or/Not?
# Gera uma cena em que um Driver troca as propriedades a, b, c de Box tick a tick (todas as combinações,
# segurando e alternando) e registra os contadores somados pelos actuators de cada caminho:
#   ca  = And nativo (Sa, Sb)          ce_and = Expression "Sa AND Sb"
#   co  = Or nativo (Sa, Sb)           ce_or  = Expression "Sa OR Sb"
#   cx  = Expression "(Sa OR Sb) AND NOT Sc", comparado com o valor esperado calculado no Python
# Uso: AnastacioEngine -b --factory-startup --python f0_expression_scene.py -- <saida.range> <resultado.txt>
#      AnastacioRuntime --server <saida.range>   (grava <resultado.txt> e fecha)
#      python3 f0_expression_check.py <resultado.txt>
import bpy, sys

args = sys.argv[sys.argv.index("--") + 1:]
out, res = args[0], args[1]

sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
for o in list(sc.objects):
    bpy.data.objects.remove(o, do_unlink=True)


def empty(name):
    o = bpy.data.objects.new(name, None)
    sc.objects.link(o)
    return o


def add(ob, kind, typ, name, **props):
    getattr(bpy.ops.logic, kind + "_add")(type=typ, name=name, object=ob.name)
    brick = getattr(ob.game, kind + "s")[-1]
    for k, v in props.items():
        setattr(brick, k, v)
    return brick


def prop(ob, name, typ, value):
    sc.objects.active = ob
    bpy.ops.object.game_property_new(type=typ, name=name)
    ob.game.properties[name].value = value


box = empty("Box")
for n in ("a", "b", "c"):
    prop(box, n, 'BOOL', False)
for n in ("ca", "ce_and", "co", "ce_or", "cx"):
    prop(box, n, 'INT', 0)

sens = {}
for n in ("a", "b", "c"):
    sens[n] = add(box, "sensor", "PROPERTY", "S" + n, evaluation_type='PROPEQUAL', property=n, value="True",
                  use_pulse_true_level=True)


def path(typ, counter, linked, expression=None):
    act = add(box, "actuator", "PROPERTY", "Add_" + counter, mode='ADD', property=counter, value="1")
    c = add(box, "controller", typ, "C_" + counter)
    if expression:
        c.expression = expression
    for n in linked:
        c.link(sensor=sens[n])
    c.link(actuator=act)


path('LOGIC_AND', "ca", "ab")
path('EXPRESSION', "ce_and", "ab", "Sa AND Sb")
path('LOGIC_OR', "co", "ab")
path('EXPRESSION', "ce_or", "ab", "Sa OR Sb")
path('EXPRESSION', "cx", "abc", "(Sa OR Sb) AND NOT Sc")

SRC = '''import bge
# 8 combinações seguradas 3 ticks, depois alternância a cada tick, depois uma sequência pseudoaleatória.
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
    own["log"] = own.get("log", "") + "%d %d %d %d %d %d %d %d %d\\n" % (
        n, a, b, c, box["ca"], box["ce_and"], box["co"], box["ce_or"], box["cx"])
    own["n"] = n + 1
    if n >= len(SEQ) + 4:
        open(r"RES_PATH", "w").write("# tick a b c ca ce_and co ce_or cx\\n" + own["log"])
        bge.logic.endGame()
'''.replace("RES_PATH", res)
bpy.data.texts.new("drv.py").from_string(SRC)
drv = empty("Driver")
tick = add(drv, "sensor", "ALWAYS", "Tick", use_pulse_true_level=True)
c = add(drv, "controller", "PYTHON", "drv", mode='MODULE', module="drv.step")
c.link(sensor=tick)

bpy.ops.wm.save_as_mainfile(filepath=out)
print("SCENE OK", out)
