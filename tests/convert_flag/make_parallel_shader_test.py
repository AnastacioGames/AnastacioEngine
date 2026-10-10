# Gera parallel_shaders.blend: confere a compilação paralela de shaders (GL_ARB_parallel_shader_compile).
# Uso: RangeEngine -b -P make_parallel_shader_test.py -- <pasta>
# Rodar o RangeRuntime em <pasta>/parallel_shaders.blend com e sem RANGE_NO_PARALLEL_SHADERS=1 (e um
# RANGE_SHADER_SALT diferente por rodada para o cache do driver não ajudar). Cada rodada grava shot_<tag>.png
# (tag = RANGE_SHOT_TAG) e uma linha em parallel_shaders.txt com o tempo de shaders do getLoadLog.
# As imagens devem ser idênticas.
#   48 esferas com materiais diferentes (cor, especular, emissão, transparência, nós), 3 luzes.
import bpy, sys, os

pasta = sys.argv[sys.argv.index("--") + 1]

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'

for i in range(48):
    x, y = i % 8, i // 8
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, size=0.45, location=(x - 3.5, y - 2.5, 0))
    ob = bpy.context.active_object
    ma = bpy.data.materials.new("Mat%02d" % i)
    ma.diffuse_color = ((i * 37 % 100) / 100.0, (i * 53 % 100) / 100.0, (i * 71 % 100) / 100.0)
    ma.specular_intensity = (i % 5) / 4.0
    ma.specular_hardness = 10 + i * 7
    ma.emit = 0.3 if i % 7 == 0 else 0.0
    if i % 6 == 0:
        ma.use_transparency = True
        ma.alpha = 0.5
    if i % 4 == 3:
        ma.diffuse_shader = 'TOON'
    if i % 5 == 2:
        ma.specular_shader = 'PHONG'
    if i % 8 == 5:
        # Material com nós: a árvore padrão já gera um shader diferente.
        ma.use_nodes = True
    ob.data.materials.append(ma)

for i, (tipo, loc) in enumerate((('SUN', (0, 0, 8)), ('POINT', (-4, -4, 3)), ('SPOT', (4, 4, 5)))):
    bpy.ops.object.lamp_add(type=tipo, location=loc)
    bpy.context.active_object.data.energy = 0.8

bpy.ops.object.camera_add(location=(0, -9, 9), rotation=(0.78, 0, 0))
sc.camera = bpy.context.active_object

TESTE = r'''import bge, os
n = [0]
def shot(cont):
    n[0] += 1
    if n[0] == 30:
        tag = os.environ.get("RANGE_SHOT_TAG", "x")
        bge.render.makeScreenshot(bge.logic.expandPath("//shot_%s.png" % tag))
    elif n[0] == 40:
        ms = [e["detail"] for e in bge.logic.getLoadLog() if e.get("stage") == "scene shaders"]
        with open(bge.logic.expandPath("//parallel_shaders.txt"), "a") as fh:
            fh.write("%s | %s\n" % (os.environ.get("RANGE_SHOT_TAG", "x"), " ; ".join(ms)))
        bge.logic.endGame()
'''
txt = bpy.data.texts.new("shot.py")
txt.write(TESTE)
bpy.ops.object.empty_add(location=(0, 0, -5))
juiz = bpy.context.active_object
juiz.name = "Juiz"
bpy.ops.logic.sensor_add(type='ALWAYS', object=juiz.name)
juiz.game.sensors[0].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=juiz.name)
juiz.game.controllers[0].mode = 'MODULE'
juiz.game.controllers[0].module = "shot.shot"
juiz.game.sensors[0].link(juiz.game.controllers[0])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(pasta, "parallel_shaders.blend"))
