# Grava Pai e Filho sem keyframes e assiste: compara a pose de cada passo. REC_LOG, REC_RES.
#   AnastacioEngine.exe cena.range --python tools/debug/editor_rec_exato.py
import bpy
import json
import os
import traceback
from mathutils import Vector

state = {'updates': 0, 'done': False}


def report(texto):
    with open(os.environ['REC_RES'], 'a') as f:
        f.write(texto + '\n')


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
        override = context()
        scene.ae_rec_countdown = 0
        scene.ae_rec_max_duration = 3.0
        scene.ae_rec_make_keyframes = False
        os.environ['REC_MOVER'] = '1'
        report('rec: %s' % bpy.ops.view3d.game_record(override))
        gravado = json.load(open(os.environ['REC_LOG']))
        os.environ['REC_MOVER'] = '0'
        report('watch: %s' % bpy.ops.view3d.game_record(override, watch=True))
        visto = json.load(open(os.environ['REC_LOG']))
        report('passos: %d %d; amostras %s' % (len(gravado), len(visto),
               [(a.object_name, a.samples_num) for a in scene.ae_rec_takes[0].actors]))
        # O passo real varia, entao mede a distancia ate a trajetoria gravada, nao passo a passo.
        for nome in ('Pai', 'Filho'):
            caminho = [Vector([linha[3] for linha in g[nome][:3]]) for g in gravado]
            pior = 0.0
            # O log atrasa um passo: a ultima amostra gravada nunca entra em caminho.
            for v in visto[:-3]:
                p = Vector([linha[3] for linha in v[nome][:3]])
                perto = 1e9
                for a, b in zip(caminho, caminho[1:]):
                    d = b - a
                    k = min(1.0, max(0.0, (p - a).dot(d) / d.dot(d))) if d.length > 0 else 0.0
                    perto = min(perto, (a + d * k - p).length)
                pior = max(pior, perto)
            report('%s: distancia max ate a trajetoria %.5f' % (nome, pior))
    except Exception:
        report('ERRO\n' + traceback.format_exc())
    report('FIM')
    os._exit(0)


bpy.app.handlers.scene_update_post.append(run)
