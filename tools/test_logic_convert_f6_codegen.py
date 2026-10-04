"""Teste de geracao de codigo do conversor, fase 6 (python puro, sem bpy nem engine).

Roda com:  python3 tools/test_logic_convert_f6_codegen.py
Usa um bpy simulado, converte o "Driver" da cena F6 (create_logic_convert_scene_f6.py) e confere que:
 - nada fica como TODO/brick (Ray material+x-ray, Collision, Near, Radar, Movement, Delay em segundos,
   Sound loop/ping-pong/3D e Track To com pai, todos em outros objetos);
 - o codigo compila, os sensores agem no dono (o_<nome>) e os helpers recebem own=<dono>;
 - as chaves de estado usam 'Dono/Actuator';
 - o fluxo do Sound (flag de tocando da engine, ping-pong, loop end/stop, 3D) funciona com um modulo aud falso.
Nao substitui o teste de runtime (ver NOTES-logic-f6.md).
"""
import importlib.util
import os
import sys
import types
from types import SimpleNamespace as NS

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


def make(name, ptype='NO_COLLISION', actor=False, parent=None):
    props = {"intruder": NS(name="intruder", type='BOOL', value=True)} if name == "Intruder" else {}
    game = NS(sensors=[], controllers=[], actuators=[], properties=props, physics_type=ptype,
              use_obstacle_create=False, radius=1.0, use_actor=actor)
    return NS(name=name, game=game, parent=parent, parent_type='OBJECT',
              users_scene=[NS(game_settings=NS(obstacle_simulation='NONE'))])


def brick(owner, kind, type_, name, **kw):
    b = NS(type=type_, name=name, **kw)
    getattr(owner.game, kind).append(b)
    return b


def sensor(owner, type_, name, **kw):
    base = dict(controllers=[], invert=False, use_level=False, use_pulse_true_level=False,
                use_pulse_false_level=False, tick_skip=0, frequency=0)
    base.update(kw)
    return brick(owner, "sensors", type_, name, **base)


def prop_act(owner, prop):
    return brick(owner, "actuators", 'PROPERTY', "Set_" + prop, actuator_mode='NONE',
                 use_world_property=False, mode='ASSIGN', property=prop, value="1")


names = ("Driver", "Scanner", "Scanner2", "Bumper", "Sentry", "Radar", "Mover", "Base", "Turret", "Target",
         "Speaker", "Intruder")
obs = {n: make(n) for n in names}
obs["Sentry"].game.use_actor = obs["Radar"].game.use_actor = obs["Intruder"].game.use_actor = True
obs["Turret"].parent = obs["Base"]
driver = obs["Driver"]
for pname in ("rayx", "rayplain", "col", "near", "radar", "moved", "delayed", "turretdummy"):
    driver.game.properties[pname] = NS(name=pname, type='INT', value=0)

mask = [i == 0 for i in range(20)]
rayx = sensor(obs["Scanner"], 'RAY', "RayX", ray_type='MATERIAL', material="Red", property="", use_x_ray=True,
              axis='NEGZAXIS', range=20.0, mask=mask, use_pulse_true_level=True)
rayplain = sensor(obs["Scanner2"], 'RAY', "RayPlain", ray_type='MATERIAL', material="Red", property="",
                  use_x_ray=False, axis='NEGZAXIS', range=20.0, mask=mask, use_pulse_true_level=True)
hit = sensor(obs["Bumper"], 'COLLISION', "Hit", use_material=False, property="", material="")
near = sensor(obs["Sentry"], 'NEAR', "Close", property="intruder", distance=5.0, reset_distance=6.0)
radar = sensor(obs["Radar"], 'RADAR', "Cone", property="intruder", axis='YAXIS', angle=90.0, distance=10.0)
moving = sensor(obs["Mover"], 'MOVEMENT', "Moving", axis='XAXIS', threshold=0.001, use_local=False)
wait = sensor(driver, 'DELAY', "Wait", delay=1, duration=0, use_repeat=False, repeat_times=0, use_deltatime=True)
tick = sensor(driver, 'ALWAYS', "Tick", use_pulse_true_level=True)

aim = brick(obs["Turret"], "actuators", 'EDIT_OBJECT', "Aim", mode='TRACKTO', object=obs["Target"],
            track_axis='TRACKAXISY', up_axis='UPAXISZ', use_3d_tracking=True, time=0)
snd = NS(filepath="//f6_tone.wav", packed_file=None)
sound = lambda name, mode, three_d: brick(
    obs["Speaker"], "actuators", 'SOUND', name, mode=mode, sound=snd, use_sound_3d=three_d, volume=0.0, pitch=1.0,
    gain_3d_min=0.0, gain_3d_max=1.0, distance_3d_reference=1.0, distance_3d_max=100.0, rolloff_factor_3d=1.0,
    cone_inner_angle_3d=6.28, cone_outer_angle_3d=6.28, cone_outer_gain_3d=0.0)
snds = [sound("Loop", 'LOOPEND', False), sound("PingPong", 'LOOPBIDIRECTIONAL', False),
        sound("Pos3D", 'LOOPSTOP', True)]

wires = [(rayx, prop_act(driver, "rayx")), (rayplain, prop_act(driver, "rayplain")), (hit, prop_act(driver, "col")),
         (near, prop_act(driver, "near")), (radar, prop_act(driver, "radar")),
         (moving, prop_act(driver, "moved")), (wait, prop_act(driver, "delayed")), (tick, aim)]
wires += [(tick, a) for a in snds]
for i, (s, a) in enumerate(wires):
    c = NS(type='LOGIC_AND', name="C%d" % i, states=1, actuators=[a])
    driver.game.controllers.append(c)
    s.controllers.append(c)
bpy.data.objects[:] = list(obs.values())

code, converted, todos = mod.convert_object(driver, "DriverLogic")
assert not todos, todos
assert len(converted) == len(wires), (len(converted), len(wires))
compile(code, "driver_logic.py", "exec")
print(code)

# Sensores e actuators agem no dono.
for var, ob in (("o_scanner", "Scanner"), ("o_scanner2", "Scanner2"), ("o_bumper", "Bumper"),
                ("o_sentry", "Sentry"), ("o_radar", "Radar"), ("o_mover", "Mover"), ("o_turret", "Turret"),
                ("o_speaker", "Speaker")):
    assert "%s = scene.objects.get(%r)" % (var, ob) in code, var
assert "o_scanner.rayCast(" in code and "self._mat_mark(" in code  # x-ray com material
assert "self._has_mat(o_scanner2.rayCast(" in code  # sem x-ray
assert "hits_o_bumper = self._take(o_bumper)" in code
assert "self._near(o_sentry, 'Sentry/Close'" in code and "self._radar(o_radar," in code
assert "self._moved('Mover/Moving'" in code and "own=o_mover" in code
assert "self._delay('Wait'" in code and ", True)" in code.split("self._delay('Wait'")[1].split("\n")[0]
assert "self._track_parent(tgt, " in code and "own=o_turret)" in code
assert "self._plm_init(self.object.scene.objects.get('Turret'))" in code
for key in ("'Speaker/Loop'", "'Speaker/PingPong'", "'Speaker/Pos3D'"):
    assert "self._snd_play(%s" % key in code, key
assert "self._snd_stop('Speaker/Loop', 'end')" in code
assert "self._snd_stop('Speaker/PingPong', 'end')" in code
assert "self._snd_stop('Speaker/Pos3D', 'stop')" in code
assert code.count("self._snd_update()") == 1
assert "own=ob" not in code
print("OK: codegen F6")

# --- Sound com aud falso: fluxo da engine (flag m_isplaying, loop/ping-pong, parada, 3D).
log = []


class Handle:
    status = 1

    def __init__(self, tag):
        self.tag = tag
        self.stopped = False

    def stop(self):
        self.stopped = True
        self.status = 0
        log.append(("stop", self.tag))

    def __setattr__(self, k, v):
        if k not in ("status", "tag", "stopped"):
            log.append(("set", self.__dict__.get("tag"), k))
        object.__setattr__(self, k, v)


aud = types.ModuleType("aud")
aud.STATUS_PLAYING = 1
aud.error = RuntimeError
aud.Device = lambda: NS(play=lambda s: Handle(s))
class _Snd(str):
    def pingpong(self):
        return "pp:" + str(self)


aud.Sound = NS(file=_Snd)


sys.modules["aud"] = aud


class V:
    """Vetor/matriz falsos: so o necessario para o caminho 3D."""

    def __init__(self, v=0.0):
        self.v = v

    def __mul__(self, o):
        return self

    def __sub__(self, o):
        return self

    def inverted(self):
        return self

    def to_quaternion(self):
        return NS(w=1.0, x=0.0, y=0.0, z=0.0)


rt = types.ModuleType("Range")
rt.logic = NS(getFrameTime=lambda: 0.0, deltaTime=lambda: 1 / 60.0, keyboard=NS(inputs={}), mouse=NS(inputs={}),
              expandPath=lambda p: p, getMessages=lambda *a: [])
rt.events = NS()
rt.types = NS(KX_PythonComponent=object)
sys.modules["Range"] = rt
sys.modules["mathutils"] = NS(Matrix=object, Vector=object)
ns = {}
exec(compile(code, "driver_logic.py", "exec"), ns)
inst = ns["DriverLogic"]()
spk = NS(invalid=False, worldPosition=V(), worldOrientation=V(), getLinearVelocity=lambda: V(),
         scene=NS(active_camera=NS(worldOrientation=V(), worldPosition=V(), getLinearVelocity=lambda: V())))
inst.object = NS(scene=NS(objects=NS(get=lambda n: spk if n == "Speaker" else None)))

inst._snd_play("S/A", "t.wav", 0.5, 1.0, True, True, None, own=spk)
h = inst._snd["S/A"][0]
assert h.tag == "pp:t.wav" and h.loop_count == -1 and h.volume == 0.5, (h.tag, log)
n = len(log)
inst._snd_play("S/A", "t.wav", 0.5, 1.0, True, True, None, own=spk)  # ja tocando: nao recomeca
assert len(log) == n
inst._snd_stop("S/A", "end")  # LOOPEND: deixa terminar (loop_count 0), mas libera o proximo play
assert h.loop_count == 0 and not h.stopped
inst._snd_play("S/A", "t.wav", 0.5, 1.0, True, True, None, own=spk)  # recomeca mesmo tocando
assert h.stopped and inst._snd["S/A"][0] is not h
h2 = inst._snd["S/A"][0]
inst._snd_stop("S/A", "stop")
assert h2.stopped and inst._snd["S/A"][0] is None
inst._snd_play("S/B", "t.wav", 1.0, 1.0, False, False, (0.0, 1.0, 1.0, 100.0, 1.0, 6.28, 6.28, 0.0), own=spk)
h3 = inst._snd["S/B"][0]
assert h3.relative is True and h3.distance_maximum == 100.0 and h3.volume_minimum == 0.0
assert not hasattr(h3, "loop_count")
inst._snd_update()
assert h3.location is not None and h3.orientation == (1.0, 0.0, 0.0, 0.0)
print("OK: Sound (flag da engine, loop end/stop, ping-pong, 3D)")

# Regressao: Track To de objeto com pai no proprio Driver e Sound no proprio objeto.
solo = make("Solo")
solo.parent = obs["Base"]
t2 = sensor(solo, 'ALWAYS', "Tick")
a1 = brick(solo, "actuators", 'EDIT_OBJECT', "Aim", mode='TRACKTO', object=obs["Target"], track_axis='TRACKAXISY',
           up_axis='UPAXISZ', use_3d_tracking=False, time=3)
a2 = brick(solo, "actuators", 'SOUND', "Beep", mode='PLAYSTOP', sound=snd, use_sound_3d=False, volume=1.0, pitch=1.0)
for i, a in enumerate((a1, a2)):
    c = NS(type='LOGIC_AND', name="C%d" % i, states=1, actuators=[a])
    solo.game.controllers.append(c)
    t2.controllers.append(c)
bpy.data.objects[:] = [solo, obs["Base"], obs["Target"]]
code2, conv2, todo2 = mod.convert_object(solo, "SoloLogic")
assert not todo2 and len(conv2) == 2, todo2
compile(code2, "solo_logic.py", "exec")
assert "own=ob)" in code2 and "self._plm_init(self.object)" in code2 and "'Beep'" in code2
assert "self._snd_update" not in code2
print("OK: objeto proprio inalterado")
