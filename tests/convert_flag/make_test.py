# Gera convert_test.blend: Menu -> Pista_1 com 8 pilotos pesados.
# Uso: RangeEngine -b -P make_test.py -- <saida.blend>
import bpy, bmesh, sys, os

args = sys.argv[sys.argv.index("--") + 1:]
out = args[0]
VARIANT = args[1] if len(args) > 1 else "full"  # full | lib | piloto:N
MATERIAL = "mat" in args[2:]  # material de no com textura + normal map
ARMATURES = "arm" in args[2:]  # 20 esqueletos de 60 ossos com animacao, layer inativo
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
  livre = ""
  if os.environ.get("FREE_UNCONVERTED") == "1":
      t1 = time.perf_counter()
      n = bge.logic.freeUnconvertedData("Pista_1")
      livre = ", freeUnconvertedData = %.1f MB em %.1f ms" % (n / 1048576.0, (time.perf_counter() - t1) * 1000)
  with open(bge.logic.expandPath("//convert_results.txt"), "a") as f:
      f.write("%s | load Pista_1 = %.0f ms, objetos=%d, pilotos=%s%s\n" % (bge.logic.convert_log, dt*1000, len(sc.objects), pil, livre))
      for e in bge.logic.getLoadLog():
          if e["scene"] == "Pista_1":
              f.write("    %s %.0f ms: %s\n" % (e["stage"], e["ms"], e["detail"]))
  bge.logic.endGame()
except Exception:
  open(r"D:/AnastacioEngine/tests/convert_flag/errors.txt","a").write(traceback.format_exc())
  bge.logic.endGame()
'''

def heavy_mesh(name, subdiv):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, diameter=1.0, calc_uvs=MATERIAL)
    bm.to_mesh(me); bm.free()
    if MATERIAL:
        # UV esferica (create_icosphere nao gera UV no 2.79)
        import math
        me.uv_textures.new("UV")
        co = [0.0] * (len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        vi = [0] * len(me.loops)
        me.loops.foreach_get("vertex_index", vi)
        uv = []
        for v in vi:
            x, y, z = co[v * 3:v * 3 + 3]
            uv += (math.atan2(y, x) / 6.2832 + 0.5, math.asin(max(-1.0, min(1.0, z * 2))) / 3.1416 + 0.5)
        me.uv_layers[0].data.foreach_set("uv", uv)
    return me

def image(name, size, seed, normal):
    img = bpy.data.images.new(name, size, size)
    px = []
    for y in range(size):
        for x in range(size):
            v = ((x // 32 + y // 32 + seed) % 2) * 0.5 + 0.25
            px += (0.5 + 0.3 * (v - 0.5), 0.5, 1.0, 1.0) if normal else (v, (seed * 0.13) % 1, 1 - v, 1.0)
    img.pixels = px
    img.pack(as_png=True)
    return img

def node_material(i):
    # material de no (Blender Internal): Output <- Material node com textura de cor + normal map
    sub = bpy.data.materials.new("PilotoBase_%d" % i)
    for kind, normal in (("cor", False), ("nor", True)):
        tex = bpy.data.textures.new("Tex_%s_%d" % (kind, i), 'IMAGE')
        tex.image = image("Img_%s_%d" % (kind, i), 512, i, normal)
        slot = sub.texture_slots.add()
        slot.texture = tex
        slot.texture_coords = 'UV'
        if normal:
            tex.use_normal_map = True
            slot.use_map_color_diffuse = False
            slot.use_map_normal = True
            slot.normal_map_space = 'TANGENT'
    mat = bpy.data.materials.new("PilotoNode_%d" % i)
    mat.use_nodes = True
    for n in mat.node_tree.nodes:
        if n.type in ('MATERIAL', 'MATERIAL_EXT'):
            n.material = sub
    return mat

def piloto(sc, i):
    body = bpy.data.objects.new("Piloto_%d" % i, heavy_mesh("Corpo_%d" % i, SUBDIV))
    body.location = (i * 3 - N_PILOTOS * 1.5, 0, 0)
    sc.objects.link(body)
    head = bpy.data.objects.new("Capacete_%d" % i, heavy_mesh("Cap_%d" % i, SUBDIV - 1))
    head.location = (0, 0, 1.5)
    head.parent = body
    sc.objects.link(head)
    if MATERIAL:
        mat = node_material(i)
        body.data.materials.append(mat)
        head.data.materials.append(mat)
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

if ARMATURES:
    # esqueleto base editado na cena ativa (Menu), depois copiado para o layer 2 de Pista_1
    base = bpy.data.objects.new("ArmBase", bpy.data.armatures.new("ArmBase"))
    menu.objects.link(base)
    menu.objects.active = base
    bpy.ops.object.mode_set(mode='EDIT')
    parent = None
    for b in range(int(os.environ.get("ARM_BONES", 60))):
        eb = base.data.edit_bones.new("Osso_%d" % b)
        eb.head = (0, 0, b * 0.1)
        eb.tail = (0, 0, b * 0.1 + 0.1)
        eb.parent = parent
        parent = eb
    bpy.ops.object.mode_set(mode='OBJECT')
    menu.objects.unlink(base)
    for a in range(int(os.environ.get("ARM_N", 20))):
        ob = bpy.data.objects.new("Esqueleto_%d" % a, base.data.copy())
        # avaliado na cena ativa para ganhar pose (como um arquivo salvo pelo editor)
        if os.environ.get("ARM_NOPOSE") != "1":
            menu.objects.link(ob)
            menu.update()
            menu.objects.unlink(ob)
        pista.objects.link(ob)
        ob.layers = [l == int(os.environ.get("ARM_LAYER", 1)) for l in range(20)]
        act = bpy.data.actions.new("Anim_%d" % a)
        for b in range(int(os.environ.get("ARM_BONES", 60)) if os.environ.get("ARM_ANIM", "1") == "1" else 0):
            path = 'pose.bones["Osso_%d"].rotation_quaternion' % b
            for c in range(4):
                fc = act.fcurves.new(path, c, "Osso_%d" % b)
                fc.keyframe_points.insert(1, 1.0 if c == 0 else 0.0)
                fc.keyframe_points.insert(60, 0.9 if c == 0 else 0.1)
        ob.animation_data_create().action = act

bpy.ops.wm.save_as_mainfile(filepath=out)
print("ok", out)
