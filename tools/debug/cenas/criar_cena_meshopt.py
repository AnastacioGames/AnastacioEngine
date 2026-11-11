# Cena de teste do meshoptimizer (ordem dos índices para o cache de vértices, docs/plano-opensource.md).
# 64 objetos com a mesma malha (icosfera subdiv 7, ~82 mil triângulos, ~5,2 milhões na tela), sem vsync.
# Uso: AnastacioEngine.exe -b -P criar_cena_meshopt.py -- <pasta de saida> [natural|random]
#   natural: ordem que o Blender gera; random: faces embaralhadas (malha vinda de join/import/sculpt);
#   alpha: faces embaralhadas com material Alpha Blend (a ordem importa: não pode ser otimizada).
# Depois: AnastacioRuntime.exe <pasta>/meshopt_<modo>.range  -> <pasta>/meshopt_<modo>_result.txt
# A/B: RANGE_MESHOPT_OFF=1 desliga; RANGE_MESHOPT_LOG=1 mostra ACMR antes/depois no console.
import bpy
import os
import sys

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out_dir = args[0] if args else os.getcwd()
mode = args[1] if len(args) > 1 else "natural"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.data.scenes[0]
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.vsync = 'OFF'
scene.game_settings.use_frame_rate = False
scene.game_settings.show_framerate_profile = False

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.objects.link(cam)
scene.camera = cam
cam.location = (0.0, 0.0, 30.0)  # olhando para -Z, grade 8x8 no plano z=0

lamp = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN'))
scene.objects.link(lamp)

bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=7, size=1.0)
base = bpy.context.object
bpy.ops.object.shade_smooth()  # vértices compartilhados: sem isso cada triângulo tem os seus e o cache não importa
if mode in ("random", "alpha"):
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.sort_elements(type='RANDOMIZE', elements={'FACE'}, seed=7)
    bpy.ops.object.mode_set(mode='OBJECT')
mat = bpy.data.materials.new("Mat")
if mode == "alpha":
    mat.game_settings.alpha_blend = 'ALPHA'
    mat.use_transparency = True
    mat.alpha = 0.5
base.data.materials.append(mat)
for i in range(64):
    ob = base if i == 0 else bpy.data.objects.new("Ico%d" % i, base.data)
    if i:
        scene.objects.link(ob)
    ob.location = ((i % 8 - 3.5) * 2.4, (i // 8 - 3.5) * 2.4, 0.0)

probe = bpy.data.objects.new("Probe", None)
scene.objects.link(probe)
scene.objects.active = probe
text = bpy.data.texts.new("probe.py")
text.write('''import Range, os, time
own = Range.logic.getCurrentController().owner
now = time.perf_counter()
if "t0" not in own:
    own["t0"] = now
    own["n"] = 0
el = now - own["t0"]
if el > 3.0:  # descarta o aquecimento
    if "m0" not in own:
        own["m0"] = now
        own["n"] = 0
    own["n"] += 1
    if now - own["m0"] > 8.0:
        ms = (now - own["m0"]) * 1000.0 / own["n"]
        path = Range.logic.expandPath("//") + "meshopt_%s_result.txt" % "MODE"
        with open(path, "a") as f:
            f.write("meshopt_off=%s frame_ms=%.3f frames=%d\\n" % (os.environ.get("RANGE_MESHOPT_OFF", "0"), ms, own["n"]))
        Range.logic.endGame()
'''.replace("MODE", mode))
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=probe.name)
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=probe.name)
probe.game.sensors['tick'].use_pulse_true_level = True
probe.game.controllers['py'].text = text
probe.game.controllers['py'].link(sensor=probe.game.sensors['tick'])

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "meshopt_%s.range" % mode))
