# Gera cooked_small.blend: muitas malhas únicas pequenas e médias convertidas no início da cena.
# Uso: RangeEngine -b -P make_cooked_small_test.py -- <pasta> <segmentos>
# Rodar o RangeRuntime duas vezes (1ª grava o .cooked, 2ª usa); cada rodada acrescenta em cooked_small.txt
# o detalhe do [Load] convert (tempo de malhas, tangentes e "N cooked").
import bpy, sys, os, random

args = sys.argv[sys.argv.index("--") + 1:]
pasta, seg = args[0], int(args[1])
N = 200

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
random.seed(1)
for i in range(N):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=max(3, seg // 2), location=(i % 20 * 3, i // 20 * 3, 0))
    ob = bpy.context.active_object
    me = ob.data
    for v in me.vertices:
        v.co.x += random.uniform(-0.05, 0.05)
    me.uv_textures.new()
print("LOOPS", len(me.loops))

TESTE = r'''import bge
def mede(cont):
    with open(bge.logic.expandPath("//cooked_small.txt"), "a") as fh:
        for e in bge.logic.getLoadLog():
            if e.get("stage") == "convert":
                fh.write("%.1f ms | %s\n" % (e["ms"], e["detail"][:200]))
    bge.logic.endGame()
'''
txt = bpy.data.texts.new("mede.py")
txt.write(TESTE)
bpy.ops.object.empty_add(location=(0, 0, 5))
juiz = bpy.context.active_object
bpy.ops.logic.sensor_add(type='ALWAYS', object=juiz.name)
bpy.ops.logic.controller_add(type='PYTHON', object=juiz.name)
juiz.game.controllers[0].mode = 'MODULE'
juiz.game.controllers[0].module = "mede.mede"
juiz.game.sensors[0].link(juiz.game.controllers[0])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(pasta, "cooked_small.blend"))
