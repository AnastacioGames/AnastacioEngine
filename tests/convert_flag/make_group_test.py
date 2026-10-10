# Gera group_test.blend: grupo "G" com Membro_On (Convert ligado) e Membro_Off (Convert desligado),
# instanciado por dupli group no layer ativo. Ao rodar, grava em group_results.txt quais objetos existem.
# Uso: RangeEngine -b -P make_group_test.py -- out.blend
import bpy, sys

out = sys.argv[sys.argv.index("--") + 1]
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene = bpy.context.scene

def cubo(nome, layer):
    me = bpy.data.meshes.new(nome)
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    ob = bpy.data.objects.new(nome, me)
    scene.objects.link(ob)
    ob.layers = [i == layer for i in range(20)]
    return ob

grupo = bpy.data.groups.new("G")
on = cubo("Membro_On", 1)
off = cubo("Membro_Off", 1)
off.convert_object = False
grupo.objects.link(on)
grupo.objects.link(off)

inst = bpy.data.objects.new("Instancia", None)
scene.objects.link(inst)
inst.dupli_type = 'GROUP'
inst.dupli_group = grupo

txt = bpy.data.texts.new("relatorio.py")
txt.write('''import bge
sc = bge.logic.getCurrentScene()
nomes = sorted(o.name for o in sc.objects)
inativos = sorted(o.name for o in sc.objectsInactive)
with open(bge.logic.expandPath("//group_results.txt"), "w") as f:
    f.write("ativos=%s\\ninativos=%s\\n" % (nomes, inativos))
bge.logic.endGame()
''')
ctrl_ob = cubo("Logica", 0)
bpy.context.scene.objects.active = ctrl_ob
bpy.ops.logic.sensor_add(type='ALWAYS', object=ctrl_ob.name)
bpy.ops.logic.controller_add(type='PYTHON', object=ctrl_ob.name)
ctrl_ob.game.sensors[0].link(ctrl_ob.game.controllers[0])
ctrl_ob.game.controllers[0].text = txt
scene.layers = [i == 0 for i in range(20)]
bpy.ops.wm.save_as_mainfile(filepath=out)
