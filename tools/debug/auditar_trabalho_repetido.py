# Detector de trabalho repetido por frame (CM_WorkCounters.h).
#
# Gera uma COPIA do jogo com um medidor na camera; o arquivo original nao muda.
#   AnastacioEngine.exe -b jogo.blend --python tools/debug/auditar_trabalho_repetido.py -- copia.blend log.txt
#   AnastacioRuntime.exe copia.blend
# O log tem, a cada segundo, a media por frame de cada contador e quantos objetos a cena tem.
# Um contador perto do numero de objetos numa cena parada indica trabalho refeito todo frame
# sobre dados que nao mudaram (o mesmo tipo do bug do RAS_MeshBoundingBox, 98f54d7f).
# Com copia.blend = '-' o medidor fica so na memoria do editor aberto (sem -b) e nada e salvo:
# roda o jogo original e nao salve ao fechar.
# Variavel AUDIT_SECONDS (padrao 20) define quanto tempo medir antes de fechar; 0 = nao fecha.
import bpy
import sys

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if len(argv) < 2:
    raise SystemExit('uso: ... --python auditar_trabalho_repetido.py -- copia.blend log.txt')
out_blend, log_path = argv[0], argv[1].replace('\\', '/')

MEDIDOR = r'''import bge, os, time
LOG = %r
KEYS = ("sceneNodeUpdates", "transformSyncs", "boundsPushes", "meshMatrixChanges", "updateNotifies", "lightUniforms", "passUniforms", "lightBinds", "drawCalls")
_s = {}

def _write(line):
    with open(LOG, "a") as f:
        f.write(line + chr(10))

def tick(cont):
    if not _s:
        _s.update(start=time.perf_counter(), last=time.perf_counter(), frames=0, acc=dict.fromkeys(KEYS, 0))
        _s["limit"] = float(os.environ.get("AUDIT_SECONDS", "20"))
        _write("# segundo objetos " + " ".join(KEYS) + " physicsMs")
        bge.logic.getCurrentScene().pre_draw.append(_frame)
    if _s["limit"] > 0 and time.perf_counter() - _s["start"] > _s["limit"]:
        _write("# fim")
        bge.logic.endGame()

def _frame():
    stats = bge.logic.getRenderStats()
    _s["frames"] += 1
    for k in KEYS:
        _s["acc"][k] += stats.get(k, 0)
    now = time.perf_counter()
    if now - _s["last"] >= 1.0:
        n = max(_s["frames"], 1)
        scene = bge.logic.getCurrentScene()
        _write("%%.0f %%d " %% (now - _s["start"], len(scene.objects)) +
               " ".join("%%.1f" %% (_s["acc"][k] / n) for k in KEYS) +
               " %%.3f" %% bge.logic.getProfileInfo().get("Physics", (0.0,))[0])
        _s.update(last=now, frames=0, acc=dict.fromkeys(KEYS, 0))
''' % log_path

text = bpy.data.texts.get('audit_work.py') or bpy.data.texts.new('audit_work.py')
text.clear()
text.write(MEDIDOR)

# Pendura o medidor na camera ativa de cada cena, com sensor Always em modo pulso.
for scene in bpy.data.scenes:
    cam = scene.camera
    if cam is None:
        print('AUDIT sem camera na cena', scene.name)
        continue
    bpy.context.screen.scene = scene
    for ob in scene.objects:
        ob.select = (ob == cam)
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', name='audit_always', object=cam.name)
    bpy.ops.logic.controller_add(type='PYTHON', name='audit_py', object=cam.name)
    sensor = cam.game.sensors['audit_always']
    sensor.use_pulse_true_level = True
    ctrl = cam.game.controllers['audit_py']
    ctrl.mode = 'MODULE'
    ctrl.module = 'audit_work.tick'
    # Estado inicial da camera, para o controller rodar desde o primeiro frame.
    initial = list(cam.game.states_initial)
    ctrl.states = (initial.index(True) + 1) if True in initial else 1
    sensor.link(ctrl)
    print('AUDIT medidor na camera', cam.name, 'cena', scene.name)

if out_blend == '-':
    print('AUDIT medidor so na memoria, log', log_path)
else:
    bpy.ops.wm.save_as_mainfile(filepath=out_blend, check_existing=False, copy=True)
    print('AUDIT copia salva', out_blend, 'log', log_path)
