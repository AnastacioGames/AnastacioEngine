# Logic Tree, F7: importar bricks existentes como nós (Import Bricks).
# Uso: AnastacioEngine -b --factory-startup --python f7_import_test.py -- <pasta>
#      AnastacioRuntime --server <pasta>/f7.range   (grava <pasta>/f7.txt e sai)
#      AnastacioEngine -b --factory-startup --python f7_import_test.py -- <pasta> check
import bpy, os, sys
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
    print("RESULT %d/%d" % (len(results) - len(failed), len(results)))
    sys.stdout.flush()
    os._exit(1 if failed else 0)


out_txt = os.path.join(tmp, "f7.txt")

if len(args) > 1 and args[1] == "check":
    vals = dict(l.split("=") for l in open(out_txt).read().split())
    check("Always + And + Add Property contou", int(vals["n"]) >= 50, vals["n"])
    check("Delay + Nand + Set Property (Nand acende antes do Delay)", vals["early"] == "1", vals["early"])
    check("Delay + Nand apaga depois do Delay", vals["late"] == "0", vals["late"])
    check("Motion importado andou", float(vals["x"]) > 0.5, vals["x"])
    finish()

ob = bpy.data.objects["Cube"]
game = ob.game
ctx = {"object": ob, "active_object": ob}
for name, typ, val in (("n", 'INT', 0), ("flag", 'INT', 0), ("early", 'INT', 0), ("late", 'INT', 0)):
    bpy.ops.object.game_property_new(ctx, type=typ, name=name)
    game.properties[name].value = val


def add(kind, typ, name):
    getattr(bpy.ops.logic, kind + "_add")(ctx, type=typ, name=name, object=ob.name)
    return getattr(game, kind + "s")[-1]


# 1) Always (pulso) -> And -> Add 1 em n; o mesmo Always alimenta o 2)
tick = add("sensor", 'ALWAYS', "tick")
tick.use_pulse_true_level = True
c1 = add("controller", 'LOGIC_AND', "count")
inc = add("actuator", 'PROPERTY', "inc")
inc.mode, inc.property, inc.value = 'ADD', "n", "1"
c1.link(sensor=tick, actuator=inc)
# 2) Always (o mesmo) + Always 2 -> And -> Motion
tick2 = add("sensor", 'ALWAYS', "tick2")
tick2.use_pulse_true_level = True
c2 = add("controller", 'LOGIC_AND', "walk")
move = add("actuator", 'MOTION', "move")
move.offset_location = (0.02, 0.0, 0.0)
c2.link(sensor=tick, actuator=move)
c2.link(sensor=tick2)
# 3) Delay 30 -> Nand -> flag = 1 (Nand: verdadeiro enquanto o Delay não disparou)
wait = add("sensor", 'DELAY', "wait")
wait.delay = 30
wait.use_pulse_true_level = True
wait.use_pulse_false_level = True
c3 = add("controller", 'LOGIC_NAND', "notyet")
on = add("actuator", 'PROPERTY', "flag_on")
on.mode, on.property, on.value = 'ASSIGN', "flag", "1"
c3.link(sensor=wait, actuator=on)
c3b = add("controller", 'LOGIC_AND', "after")
off = add("actuator", 'PROPERTY', "flag_off")
off.mode, off.property, off.value = 'ASSIGN', "flag", "0"
c3b.link(sensor=wait, actuator=off)
# 4) Expression: fica como brick
c4 = add("controller", 'EXPRESSION', "expr")
c4.expression = "tick"
c4.link(sensor=tick)
# 5) Motion Servo: sem nó equivalente, fica como brick
servo = add("actuator", 'MOTION', "servo")
servo.mode = 'OBJECT_SERVO'
c5 = add("controller", 'LOGIC_AND', "servo_ctrl")
c5.link(sensor=tick2, actuator=servo)
# 6) registro (Python Script, fica como brick): anota e sai
text = bpy.data.texts.new("f7_log.py")
text.from_string('''import bge
ob = bge.logic.getCurrentController().owner
f = ob.get("frame", 0) + 1
ob["frame"] = f
if f == 10:
    ob["early"] = ob["flag"]
if f == 80:
    ob["late"] = ob["flag"]
    open(%r, "w").write("n=%%d early=%%d late=%%d x=%%f" %% (ob["n"], ob["early"], ob["late"], ob.worldPosition.x))
    bge.logic.endGame()
''' % out_txt)
log = add("controller", 'PYTHON', "log")
log.mode, log.text = 'SCRIPT', text
log.link(sensor=tick)

# 7) controller desligado no checkbox: vira porta mutada, não gera actuator
offs = add("sensor", 'ALWAYS', "off_tick")
offc = add("controller", 'LOGIC_AND', "off_ctrl")
offa = add("actuator", 'PROPERTY', "off_act")
offa.mode, offa.property, offa.value = 'ASSIGN', "late", "5"
offc.link(sensor=offs, actuator=offa)
offc.active = False

n_before = len(game.controllers)
tree, n, warnings = lt.import_bricks(ob)
print("WARN", warnings)
check("importou 5 controllers (count, walk, notyet, after, off_ctrl)", n == 5, n)
check("3 ficaram como brick (expr, servo, log)", len(warnings) == 3, warnings)
left = sorted(c.name for c in game.controllers)
check("controllers que sobraram", left == ["expr", "log", "servo_ctrl"], left)
check("sensores usados por bricks mantidos ficaram", "tick" in game.sensors and "tick2" in game.sensors)
check("actuators importados saíram", "inc" not in game.actuators and "move" not in game.actuators)
check("servo ficou", "servo" in game.actuators)
kinds = sorted(nd.bl_idname for nd in tree.nodes)
print("NODES", kinds)
check("Add Property para mode ADD", "RangeLogicAddProperty" in kinds)
check("Set Property para mode ASSIGN", kinds.count("RangeLogicSetProperty") == 3, kinds)
check("Nand virou And + Not", "RangeLogicNot" in kinds)
check("um nó por sensor (tick reaproveitado)", kinds.count("RangeLogicAlways") == 3, kinds)
check("Delay manteve o valor", any(nd.bl_idname == "RangeLogicDelay" and nd.delay == 30 for nd in tree.nodes))
check("Motion manteve o offset", any(nd.bl_idname == "RangeLogicMotion" and abs(nd.offset_location[0] - 0.02) < 1e-6
                                     for nd in tree.nodes))
check("controller desligado virou porta mutada",
      any(nd.bl_idname == "RangeLogicAnd" and nd.mute for nd in tree.nodes))
errs = lt.compile_object(ob)
check("porta mutada não gera o actuator", not any(a.property == "late" and a.value == "5"
                                                  for a in game.actuators if a.type == 'PROPERTY'))
check("compila sem erro", errs == [], errs)
again, n2, _w = lt.import_bricks(ob)
check("importar de novo não duplica (bricks da árvore são ignorados)", n2 == 0, n2)
# estados: controllers nos estados 1 e 2 viram dois Frames de Estado
pl = bpy.data.objects["Plane"]
pctx = {"object": pl, "active_object": pl}
pl.game.state_names[1].name = "Fugindo"
for st, name in ((1, "idle"), (2, "run")):
    bpy.ops.logic.sensor_add(pctx, type='ALWAYS', name="s_" + name, object=pl.name)
    bpy.ops.logic.controller_add(pctx, type='LOGIC_AND', name="c_" + name, object=pl.name)
    bpy.ops.logic.actuator_add(pctx, type='MOTION', name="a_" + name, object=pl.name)
    c = pl.game.controllers[-1]
    c.states = st
    c.link(sensor=pl.game.sensors[-1], actuator=pl.game.actuators[-1])
ptree, pn, _pw = lt.import_bricks(pl)
frames = sorted(f.label for f in ptree.nodes if f.bl_idname == "NodeFrame" and f.range_logic_state)
check("dois Frames de Estado (nome do estado 2 reaproveitado)", frames == ["Fugindo", "State 1"], frames)
check("Frame do estado inicial marcado", any(f.range_logic_initial and f.label == "State 1" for f in ptree.nodes
                                              if f.bl_idname == "NodeFrame"))
check("estados compilam sem erro", lt.compile_object(pl) == [])
got = sorted(c.states for c in pl.game.controllers)
check("controllers voltam nos estados 1 e 2", got == [1, 2], got)
bpy.context.scene.render.engine = 'BLENDER_GAME'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, "f7.range"))
finish()
