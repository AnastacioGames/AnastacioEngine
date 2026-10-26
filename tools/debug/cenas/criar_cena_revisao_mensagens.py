"""Regressao das mensagens de Logic Bricks (frente 6): broadcast lido sem destinatario nao duplica.

AnastacioEngine.exe -b --factory-startup --python este_script -- <pasta>
AnastacioRuntime.exe --server <pasta>/revisao_mensagens.range  -> <pasta>/result_mensagens.json
"""
import os
import sys

import bpy

out_dir = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(out_dir, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
obj = scene.objects['Cube']
text = bpy.data.texts.new('msg_review.py')
text.write('''import json
import Range

STATE = {'frame': 0}

def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    if f == 0:
        Range.logic.sendMessage('teste', 'broadcast')
        Range.logic.sendMessage('teste', 'para_cube', 'Cube')
        Range.logic.sendMessage('outro', 'broadcast2')
    elif f == 1:
        res = {
            'sem_dest_assunto': len(Range.logic.getMessages('', 'teste')),
            'sem_dest_tudo': len(Range.logic.getMessages('')),
            'cube_assunto': len(Range.logic.getMessages('Cube', 'teste')),
            'cube_tudo': len(Range.logic.getMessages('Cube')),
            'ninguem': len(Range.logic.getMessages('Nada', 'inexistente')),
        }
        with open(Range.logic.expandPath('//result_mensagens.json'), 'w') as out:
            json.dump(res, out, indent=2)
        Range.logic.endGame()
''')
bpy.context.scene.objects.active = obj
bpy.ops.logic.sensor_add(type='ALWAYS', object=obj.name)
bpy.ops.logic.controller_add(type='PYTHON', object=obj.name)
sens = obj.game.sensors[-1]
sens.use_pulse_true_level = True
cont = obj.game.controllers[-1]
cont.mode = 'MODULE'
cont.module = 'msg_review.run'
sens.link(cont)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'revisao_mensagens.range'))
