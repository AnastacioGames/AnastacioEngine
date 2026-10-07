# Gera convert_test.blend: Menu -> Pista_1 com 8 pilotos pesados.
# Uso: RangeEngine -b -P make_test.py -- <saida.blend>
import bpy, bmesh, sys

args = sys.argv[sys.argv.index("--") + 1:]
out = args[0]
VARIANT = args[1] if len(args) > 1 else "full"  # full | lib | piloto:N
N_PILOTOS = 8
SUBDIV = 7  # icosfera ~327k tris por piloto

menu = bpy.data.scenes[0]
menu.name = "Menu"
for ob in list(menu.objects):
    if ob.type != 'CAMERA':
        bpy.data.objects.remove(ob, do_unlink=True)
pista = bpy.data.scenes.new("Pista_1")
for sc in (menu, pista):
    sc.render.engine = 'BLENDER_GAME'

def text(name, body):
    t = bpy.data.texts.new(name)
    t.write(body)
    return t

def logic(ob, txt):
    ctx = {"object": ob, "active_object": ob, "edit_object": None}
    bpy.ops.logic.sensor_add(ctx, type='ALWAYS', name="s", object=ob.name)
    bpy.ops.logic.controller_add(ctx, type='PYTHON', name="c", object=ob.name)
    s = ob.game.sensors[-1]; c = ob.game.controllers[-1]
    c.text = txt
    s.link(c)

MENU = '''
import bge, os, time, traceback
try:
  mode = os.environ.get("CONVERT_MODE", "all")
  escolhidos = {"Piloto_0", "Piloto_1"}
  t0 = time.perf_counter()
  mudados = 0
  bge.logic.escolhidos = sorted(escolhidos)
  for i in range(%d if mode != "lib" else 0):
      nome = "Piloto_%%d" %% i
      liga = mode == "all" or nome in escolhidos
      mudados += bge.logic.setObjectConvert("Pista_1", nome, liga)
  bge.logic.convert_log = "[convert_test] modo=%%s flags=%%.3f ms mudados=%%d" %% (mode, (time.perf_counter()-t0)*1000, mudados)
  bge.logic.convert_t0 = time.perf_counter()
  bge.logic.getCurrentScene().replace("Pista_1")
except Exception:
  open(r"D:/AnastacioEngine/tests/convert_flag/errors.txt","a").write(traceback.format_exc())
''' % N_PILOTOS

PISTA = r'''
import bge, time, traceback
try:
  import os
  if os.environ.get("CONVERT_MODE") == "lib":
      for n in bge.logic.escolhidos:
          bge.logic.LibLoad(bge.logic.expandPath("//%s.blend" % n), "Scene")
  dt = time.perf_counter() - bge.logic.convert_t0
  sc = bge.logic.getCurrentScene()
  pil = sorted(o.name for o in sc.objects if o.name.startswith("Piloto_"))
  with open(bge.logic.expandPath("//convert_results.txt"), "a") as f:
      f.write("%s | load Pista_1 = %.0f ms, objetos=%d, pilotos=%s\n" % (bge.logic.convert_log, dt*1000, len(sc.objects), pil))
  bge.logic.endGame()
except Exception:
  open(r"D:/AnastacioEngine/tests/convert_flag/errors.txt","a").write(traceback.format_exc())
  bge.logic.endGame()
'''

def heavy_mesh(name, subdiv):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, diameter=1.0)
    bm.to_mesh(me); bm.free()
    return me

def piloto(sc, i):
    body = bpy.data.objects.new("Piloto_%d" % i, heavy_mesh("Corpo_%d" % i, SUBDIV))
    body.location = (i * 3 - N_PILOTOS * 1.5, 0, 0)
    sc.objects.link(body)
    head = bpy.data.objects.new("Capacete_%d" % i, heavy_mesh("Cap_%d" % i, SUBDIV - 1))
    head.location = (0, 0, 1.5)
    head.parent = body
    sc.objects.link(head)
    for o in (body, head):
        o.game.physics_type = 'STATIC'
        o.game.use_collision_bounds = False  # forma triangle mesh: conversao mais cara

if VARIANT.startswith("piloto:"):
    # arquivo so com um piloto, cena "Scene", para LibLoad
    bpy.data.scenes.remove(pista)
    menu.name = "Scene"
    for ob in list(menu.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    piloto(menu, int(VARIANT.split(":")[1]))
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("ok", out)
    raise SystemExit

ctl = bpy.data.objects.new("MenuLogic", None)
menu.objects.link(ctl)
logic(ctl, text("menu.py", MENU))

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, -40, 5)
cam.rotation_euler = (1.45, 0, 0)
pista.objects.link(cam)
pista.camera = cam
pl = bpy.data.objects.new("PistaLogic", None)
pista.objects.link(pl)
logic(pl, text("pista.py", PISTA))

if VARIANT == "full":
    for i in range(N_PILOTOS):
        piloto(pista, i)

bpy.ops.wm.save_as_mainfile(filepath=out)
print("ok", out)
