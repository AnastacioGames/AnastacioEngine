# Fase 10 do Rec Play. Com janela: grava um Take e salva. Com -b: acrescenta a logica do jogo_rec_api.py,
# que o AnastacioRuntime executa e relata em REC_RES.
#   AnastacioEngine.exe cena.range --python tools/debug/editor_rec_api.py
#   AnastacioEngine.exe -b cena.range --python tools/debug/editor_rec_api.py -- logica
import bpy
import os
import sys
import traceback

state = {'updates': 0, 'done': False}


def report(texto):
    with open(os.environ['REC_RES'], 'a') as f:
        f.write(texto + '\n')


def logica():
    scene = bpy.context.scene
    pasta = os.path.dirname(os.path.abspath(__file__))
    texto = bpy.data.texts.new('jogo_rec_api.py')
    texto.write(open(os.path.join(pasta, 'jogo_rec_api.py')).read())
    ob = bpy.data.objects['Chao']
    scene.objects.active = ob
    bpy.ops.logic.sensor_add(type='ALWAYS', object=ob.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=ob.name)
    sensor, controller = ob.game.sensors[-1], ob.game.controllers[-1]
    sensor.use_pulse_true_level = True
    controller.mode = 'MODULE'
    controller.module = 'jogo_rec_api.tick'
    sensor.link(controller)
    bpy.ops.wm.save_mainfile()


def run(scene):
    state['updates'] += 1
    if state['done'] or state['updates'] < 3:
        return
    window = bpy.context.window_manager.windows[0]

    def context():
        screen = window.screen
        area = next(a for a in screen.areas if a.type == 'VIEW_3D')
        region = next(r for r in area.regions if r.type == 'WINDOW')
        return {'window': window, 'screen': screen, 'area': area, 'region': region, 'scene': scene}

    if not state.get('full'):
        state['full'] = True
        state['updates'] = 0
        bpy.ops.screen.screen_full_area(context())
        return
    state['done'] = True
    bpy.app.handlers.scene_update_post.remove(run)
    try:
        scene.ae_rec_countdown = 0
        scene.ae_rec_max_duration = 2.0
        report('rec: %s' % bpy.ops.view3d.game_record(context()))
        report('takes: %s' % [t.name for t in scene.ae_rec_takes])
        bpy.ops.wm.save_mainfile()
    except Exception:
        report('ERRO\n' + traceback.format_exc())
    report('FIM')
    os._exit(0)


if 'logica' in sys.argv:
    logica()
else:
    bpy.app.handlers.scene_update_post.append(run)
