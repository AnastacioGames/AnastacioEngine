"""Build async_loading.range: LibLoads //lib_spheres.range asynchronously and logs progress and frame time."""
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_homefile(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
bpy.ops.object.camera_add(location=(0, -30, 0), rotation=(1.5708, 0, 0))
cam = bpy.context.object
scene.camera = cam
text = bpy.data.texts.new("async_load.py")
text.write('''import Range, time
g = Range.logic.globalDict
def print(*a):
    with open(Range.logic.expandPath("//async_log.txt"), "a") as f:
        f.write(" ".join(str(x) for x in a) + "\\n")
now = time.perf_counter()
if "status" not in g:
    g["t0"] = g["last"] = now
    g["frame"] = 0
    g["status"] = Range.logic.LibLoad(Range.logic.expandPath("//lib_spheres.range"), "Scene", asynchronous=True)
    print("[async] LibLoad call returned after %.0f ms" % ((time.perf_counter() - now) * 1000))
    g["last"] = time.perf_counter()
else:
    st = g["status"]
    g["frame"] += 1
    print("[async] frame %3d  dt %6.1f ms  progress %.3f  finished %s" % (g["frame"], (now - g["last"]) * 1000, st.progress, st.finished))
    g["last"] = now
    if st.finished:
        g["done"] = g.get("done", 0) + 1
        if g["done"] == 5:
            print("[async] total %.0f ms, objects %d" % ((now - g["t0"]) * 1000, len(Range.logic.getCurrentScene().objects)))
            Range.logic.endGame()
''')
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name="A", object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name="C", object=cam.name)
s = cam.game.sensors["A"]; s.use_pulse_true_level = True
c = cam.game.controllers["C"]; c.text = text; s.link(c)
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False, compress=False, relative_remap=False)
