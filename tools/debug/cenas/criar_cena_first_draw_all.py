# Cena de teste do 1o desenho completo: no 1o quadro da cena todo objeto renderizavel passa no culling da
# camera (o driver monta a variante do shader atras do Loading); depois o frustum volta a cortar.
# Um cubo fica atras da camera: culled False depois do 1o desenho, True depois do 2o.
# Uso: AnastacioEngine.exe -b -P criar_cena_first_draw_all.py -- <pasta de saida>
# Depois: AnastacioRuntime.exe <pasta>/first_draw_all.range ; resultado em <pasta>/first_draw_all_result.txt
# Com RANGE_NO_FIRST_DRAW_ALL=1 o cubo ja sai cortado no 1o desenho.
import bpy
import os
import sys

out_dir = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.getcwd()

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.data.scenes[0]
scene.render.engine = 'BLENDER_GAME'
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.objects.link(cam)
scene.camera = cam
# Camera na origem olhando para -Z; o cubo fica em +Z, atras dela.
bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 20.0))
bpy.context.object.name = "Behind"

ob = bpy.data.objects.new("Probe", None)
scene.objects.link(ob)
scene.objects.active = ob
bpy.ops.object.game_property_new(type='INT', name="n")

text = bpy.data.texts.new("probe.py")
text.write('''import Range, os
own = Range.logic.getCurrentController().owner
behind = own.scene.objects["Behind"]
# A logica do quadro N le o culled que o desenho do quadro N-1 deixou.
if own["n"] == 1:
    own["first"] = behind.culled
elif own["n"] == 3:
    with open(os.path.join(Range.logic.expandPath("//"), "first_draw_all_result.txt"), "w") as f:
        f.write("culled_apos_1o_desenho %s culled_depois %s\\n" % (own["first"], behind.culled))
    Range.logic.endGame()
own["n"] += 1
''')
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=ob.name)
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=ob.name)
ob.game.sensors['tick'].use_pulse_true_level = True
ob.game.controllers['py'].text = text
ob.game.controllers['py'].link(sensor=ob.game.sensors['tick'])

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "first_draw_all.range"))
