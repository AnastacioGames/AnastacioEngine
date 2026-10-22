# Cena de teste do sono do loop (vsync desligado, sem passo fixo, Use Frame Rate ligado, 60 Hz).
# Mede 10 s: FPS e tempo de CPU do processo. Antes da correção o loop girava a CPU sem dormir.
# Uso: AnastacioEngine.exe -b -P criar_cena_loop_sleep.py -- <pasta de saida>
# Depois: LOOP_LOG=<arquivo> AnastacioRuntime.exe <pasta>/loop_sleep.range ; resultado no LOOP_LOG
import bpy
import os
import sys

out_dir = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.getcwd()

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.data.scenes[0]
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.vsync = 'OFF'
scene.game_settings.use_fixed_timestep = False
scene.game_settings.use_frame_rate = True
scene.game_settings.fps = 60
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.objects.link(cam)
scene.camera = cam

ob = bpy.data.objects.new("Probe", None)
scene.objects.link(ob)
scene.objects.active = ob

text = bpy.data.texts.new("probe.py")
text.write('''import bge, time, os, traceback
LOG = os.environ.get("LOOP_LOG", "loop_sleep_result.txt")
try:
  own = bge.logic.getCurrentController().owner
  if "t0" not in own:
    own["t0"] = time.perf_counter(); own["c0"] = time.process_time(); own["n"] = 0
  own["n"] += 1
  el = time.perf_counter() - own["t0"]
  if el >= 10.0:
    cpu = time.process_time() - own["c0"]
    with open(LOG, "w") as f:
        f.write("frames %d fps %.1f cpu_s %.2f cpu_pct %.0f\\n" % (own["n"], own["n"] / el, cpu, 100 * cpu / el))
    bge.logic.endGame()
except Exception:
  open(LOG, "a").write(traceback.format_exc()); bge.logic.endGame()
''')
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=ob.name)
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=ob.name)
ob.game.sensors['tick'].use_pulse_true_level = True
ob.game.controllers['py'].text = text
ob.game.controllers['py'].link(sensor=ob.game.sensors['tick'])

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "loop_sleep.range"))
