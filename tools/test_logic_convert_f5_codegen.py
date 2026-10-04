"""Teste de geracao de codigo do conversor (python puro, sem bpy nem engine).

Roda com:  python3 tools/test_logic_convert_f5_codegen.py
Usa um bpy simulado, converte o "Driver" da cena F5 (create_logic_convert_scene_f5.py) e confere que:
 - nada fica como TODO/brick;
 - o codigo compila e age sobre scene.objects[dono do actuator] (own=<variavel do dono>), nunca sobre o Driver;
 - o update() executado com helpers gravadores chama Camera/Constraint/Steering/Mouse Look no objeto certo.
Nao substitui o teste de runtime (ver NOTES-logic-f5.md).
"""
import importlib.util
import os
import sys
import types
from types import SimpleNamespace as NS
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "..", "source", "release", "scripts", "startup", "bl_operators", "logic_to_python.py")

bpy = types.ModuleType("bpy")
bpy.types = types.ModuleType("bpy.types")
bpy.types.Operator = object
bpy.props = types.ModuleType("bpy.props")
for n in ("BoolProperty", "EnumProperty", "StringProperty"):
    setattr(bpy.props, n, lambda *a, **k: None)
bpy.data = NS(objects=[])
sys.modules.update({"bpy": bpy, "bpy.types": bpy.types, "bpy.props": bpy.props})
spec = importlib.util.spec_from_file_location("logic_to_python", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def make(name, ptype='NO_COLLISION'):
    game = NS(sensors=[], controllers=[], actuators=[], properties={}, physics_type=ptype,
              use_obstacle_create=False, radius=1.0, use_actor=False)
    return NS(name=name, game=game, users_scene=[NS(game_settings=NS(obstacle_simulation='NONE'))])


def act(owner, type_, name, **kw):
    a = NS(type=type_, name=name, **kw)
    owner.game.actuators.append(a)
    return a


driver, target = make("Driver"), make("Target")
holder, slider, chaser, looker = make("CamHolder"), make("Slider"), make("Chaser"), make("Looker")
acts = [
    act(holder, 'CAMERA', "Follow", object=target, height=2.0, min=3.0, max=6.0, axis='NEG_Y', damping=0.7),
    act(slider, 'CONSTRAINT', "ClampZ", mode='LOC', limit='LOCZ', limit_min=-2.0, limit_max=1.0, damping=5,
        time=0),
    act(chaser, 'STEERING', "Seek", mode='SEEK', target=target, navmesh=None, distance=1.0, velocity=4.0,
        update_period=0, self_terminated=False, facing=False, facing_axis='Y', lock_z_velocity=False,
        show_visualization=False, normal_up=False),
    act(looker, 'MOUSE', "Look", mode='LOOK', use_axis_x=True, use_axis_y=True, reset_x=True, reset_y=True,
        local_x=False, local_y=True, threshold_x=0.1, threshold_y=0.1, object_axis_x='OBJECT_AXIS_Z',
        object_axis_y='OBJECT_AXIS_X', sensitivity_x=2.0, sensitivity_y=1.5, min_x=0.0, max_x=0.0,
        min_y=-1.0, max_y=1.0),
]
tick = NS(type="ALWAYS", name="Tick", use_pulse_true_level=True, tick_skip=0, controllers=[], invert=False,
         use_level=False, use_pulse_false_level=False, frequency=0)
driver.game.sensors.append(tick)
for i, a in enumerate(acts):
    c = NS(type='LOGIC_AND', name="C%d" % i, states=1, actuators=[a])
    driver.game.controllers.append(c)
    tick.controllers.append(c)
bpy.data.objects[:] = [driver, target, holder, slider, chaser, looker]

code, converted, todos = mod.convert_object(driver, "DriverLogic")
assert not todos, todos
assert len(converted) == 4, converted
compile(code, "driver_logic.py", "exec")
for var, ob in (("o_camholder", "CamHolder"), ("o_slider", "Slider"), ("o_chaser", "Chaser"),
                ("o_looker", "Looker")):
    assert "%s = scene.objects.get(%r)" % (var, ob) in code, var
assert code.count("own=o_") == 4 + 0, code.count("own=o_")
assert "own=ob" not in code
# Chaves de estado separadas por dono/atuador.
for key in ("'cst:Slider/ClampZ'", "'str:Chaser/Seek'", "'mlk:Looker/Look'"):
    assert key in code, key
print(code)

# Executa o update() com helpers gravadores.
calls = []
rt = types.ModuleType("Range")
rt.logic = NS(getFrameTime=lambda: 0.0, deltaTime=lambda: 1 / 60.0, keyboard=NS(inputs={}), mouse=NS(inputs={}))
rt.events = NS()
rt.types = NS(KX_PythonComponent=object)
sys.modules["Range"] = rt
sys.modules["mathutils"] = NS(Matrix=object, Vector=object)
ns = {}
exec(compile(code, "driver_logic.py", "exec"), ns)
cls = ns["DriverLogic"]
inst = cls()
objs = {n: NS(name=n) for n in ("Driver", "Target", "CamHolder", "Slider", "Chaser", "Looker")}
scene = NS(objects=NS(get=objs.get, __getitem__=objs.__getitem__))
objs["Driver"].scene = scene
objs["Driver"].state = 1
inst.object = objs["Driver"]
rec = lambda n: (lambda *a, **k: calls.append((n, k.get("own"))) or True)
for n in ("_follow", "_mouse_look", "_cst_loc", "_steer"):
    setattr(cls, n, rec(n))
inst.start({})
inst.update()
inst.update()
seen = {(n, o.name) for n, o in calls}
want = {("_follow", "CamHolder"), ("_cst_loc", "Slider"), ("_steer", "Chaser"), ("_mouse_look", "Looker")}
assert seen == want, seen
print("OK: Camera/Constraint/Steering/Mouse Look agem no dono do actuator")

# Regressao: actuators do proprio objeto continuam com a chave simples e own=ob.
solo = make("Solo")
a_own = act(solo, 'CONSTRAINT', "ClampZ", mode='LOC', limit='LOCZ', limit_min=-2.0, limit_max=1.0, damping=5, time=0)
t2 = NS(type="ALWAYS", name="Tick", use_pulse_true_level=False, tick_skip=0, controllers=[], invert=False,
        use_level=False, use_pulse_false_level=False, frequency=0)
c2 = NS(type='LOGIC_AND', name="C", states=1, actuators=[a_own])
t2.controllers.append(c2)
solo.game.sensors.append(t2)
solo.game.controllers.append(c2)
bpy.data.objects[:] = [solo]
code2, conv2, todo2 = mod.convert_object(solo, "SoloLogic")
assert not todo2 and "'cst:ClampZ'" in code2 and "own=ob)" in code2, (todo2, code2)
print("OK: actuator do proprio objeto inalterado")
