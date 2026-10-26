"""Teste de LibLoad: carrega lib.range no jogo, replaceMesh (outro material), addObject, endObject e LibFree.

Confere os draw calls em cada etapa (cada objeto conta 2: passe de sombra + camera) e o material novo.

    AnastacioEngine -b --python tools/debug/cenas/criar_teste_libload.py -- PASTA
    set LIBLOAD_OUT=PASTA/out.txt && AnastacioRuntime PASTA/main.range   (abre janela ~2 s e fecha)

out.txt termina em "RESULTADO OK" ou "RESULTADO FALHOU".
"""
import bpy, sys, os
out = sys.argv[sys.argv.index("--") + 1]

def base(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_GAME'; sc.name = name
    sc.game_settings.use_shading_nodes = False
    return sc

def cube(sc, name, loc, color, meshname=None):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    ob = bpy.context.object; ob.name = name
    if meshname: ob.data.name = meshname
    m = bpy.data.materials.new(name + "Mat"); m.diffuse_color = color
    ob.data.materials.append(m); ob.game.physics_type = 'NO_COLLISION'
    return ob

# Library: 3 visible cubes on layer 1, plus an alternative mesh (other material) on layer 2.
sc = base("Scene")
for i, n in enumerate(["LibA", "LibB", "LibC"]):
    cube(sc, n, (i * 3 - 3, 3, 0), (1, 0.2 * i, 0))
alt = cube(sc, "AltHolder", (0, 0, -50), (0, 0, 1), meshname="AltMesh")
alt.layers = [False, True] + [False] * 18
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "lib.range"), check_existing=False)

# Main: camera, sun with shadow, ground cube and the test script.
sc = base("Scene")
cube(sc, "Ground", (0, -3, 0), (0.5, 0.5, 0.5))
lamp = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN')); sc.objects.link(lamp)
lamp.data.use_shadow = True; lamp.rotation_euler = (0.5, 0.2, 0); lamp.location = (0, 0, 10)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")); sc.objects.link(cam)
cam.location = (0, 0, 25); sc.camera = cam
sc.game_settings.resolution_x, sc.game_settings.resolution_y = 640, 360
t = bpy.data.texts.new("t.py")
t.write('''import Range, os, traceback
try:
    sc = Range.logic.getCurrentScene()
    own = Range.logic.getCurrentController().owner
    own["f"] = own.get("f", 0) + 1
    f = own["f"]
    st = Range.logic.globalDict.setdefault("st", {"log": []})
    dc = Range.logic.getRenderStats()["drawCalls"]
    lib = Range.logic.expandPath("//lib.range")
    def log(s): st["log"].append(s)
    if f == 15:
        st["d0"] = dc; log("base %d" % dc)
        Range.logic.LibLoad(lib, "Scene")
    elif f == 30:
        st["d1"] = dc; log("libload %d (esperado %d)" % (dc, st["d0"] + 6))
        st["ok1"] = dc == st["d0"] + 6
        sc.objects["LibA"].replaceMesh("AltMesh")
        st["added"] = sc.addObject("AltHolder", own)
        st["added"].worldPosition = (0, -6, 0)
    elif f == 45:
        st["d2"] = dc; log("replaceMesh+addObject %d (esperado %d)" % (dc, st["d1"] + 2))
        st["ok2"] = dc == st["d1"] + 2
        mat = sc.objects["LibA"].meshes[0].materials[0].name
        log("material do LibA: %s" % mat)
        st["ok2"] = st["ok2"] and "AltHolderMat" in mat
        st["added"].endObject()
    elif f == 55:
        log("endObject %d (esperado %d)" % (dc, st["d1"]))
        st["ok3"] = dc == st["d1"]
        Range.logic.LibFree(lib)
    elif f == 70:
        log("libfree %d (esperado %d)" % (dc, st["d0"]))
        st["ok4"] = dc == st["d0"]
        ok = all(st.get(k) for k in ("ok1", "ok2", "ok3", "ok4"))
        open(os.environ["LIBLOAD_OUT"], "w").write(chr(10).join(st["log"] + ["RESULTADO " + ("OK" if ok else "FALHOU")]))
        Range.logic.endGame()
except Exception:
    open(os.environ['LIBLOAD_OUT'], 'w').write(traceback.format_exc())
    Range.logic.endGame()
''')
sc.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name="A", object=cam.name)
s = cam.game.sensors["A"]; s.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="P", object=cam.name)
c = cam.game.controllers["P"]; c.text = t; s.link(c)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "main.range"), check_existing=False)
