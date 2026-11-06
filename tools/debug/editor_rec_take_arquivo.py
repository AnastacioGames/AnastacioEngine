# Confere o Take no arquivo: abre, lista as amostras e migra Takes antigos (propriedades da cena).
#   AnastacioEngine.exe -b salvo.range --python tools/debug/editor_rec_take_arquivo.py -- relatorio.txt antigo.range
import bpy
import sys

relatorio, antigo = sys.argv[sys.argv.index('--') + 1:][:2]


def listar(titulo):
    scene = bpy.context.scene
    with open(relatorio, 'a') as f:
        f.write('%s: %s\n' % (titulo, [(t.name, round(t.duration, 2), [(a.object_name, a.action_name, a.samples_num)
                                       for a in t.actors]) for t in scene.ae_rec_takes]))
        f.write('sobrou propriedade: %s\n' % ('ae_rec_takes' in scene.keys()))


listar('salvo')
scene = bpy.context.scene
while len(scene.ae_rec_takes):
    scene.ae_rec_takes.remove(0)
scene['ae_rec_takes'] = [{'name': 'Antigo', 'duration': 2.5, 'actors': [
    {'object_name': 'Cubo', 'action_name': 'Rec_Cubo', 'track_prefix': 'Rec_1_'}]}]
bpy.ops.wm.save_as_mainfile(filepath=antigo)
bpy.ops.wm.open_mainfile(filepath=antigo)
listar('migrado')
