# Teste do Rec Play com teclas de verdade: Esc na contagem cancela; depois grava com WASD e F10.
# REC_RES = relatorio; REC_PY = python do sistema, que roda tools/debug/teclas_rec.py.
#   AnastacioEngine.exe cena.range --python tools/debug/editor_rec_wasd.py
import bpy
import os
import subprocess
import traceback

state = {'updates': 0, 'done': False}
TECLAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'teclas_rec.py')
if not os.path.exists(TECLAS):
    TECLAS = os.environ['REC_TECLAS']


def report(texto):
    with open(os.environ['REC_RES'], 'a') as f:
        f.write(texto + '\n')


def apertar(*passos):
    subprocess.Popen([os.environ['REC_PY'], TECLAS, str(os.getpid()), os.environ['REC_RES']] + list(passos))


def resumo(scene, nome):
    ob = bpy.data.objects[nome]
    if not ob.animation_data or not ob.animation_data.action:
        report('%s: sem Action' % nome)
        return
    curvas = ob.animation_data.action.fcurves
    fim = max(k.co[0] for c in curvas for k in c.keyframe_points)
    pontos = []
    for frame in (scene.frame_start, fim):
        scene.frame_set(int(frame))
        pontos.append(tuple(round(v, 2) for v in ob.matrix_world.translation))
    report('%s: inicio %s fim %s frames ate %.0f rot_z=%.2f' % (nome, pontos[0], pontos[1], fim, ob.rotation_euler.z))


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
        scene.ae_rec_countdown = 3
        apertar('espera:2', 'ESC:0.2')
        report('rec cancelado: %s' % bpy.ops.view3d.game_record(override))
        report('takes depois do Esc: %d' % len(scene.ae_rec_takes))

        scene.ae_rec_countdown = 2
        apertar('espera:3', 'W:1', 'A:0.6', 'W:1', 'espera:0.5', 'F10:0.2')
        report('rec wasd: %s' % bpy.ops.view3d.game_record(override))
        report('takes: %s' % [(t.name, round(t.duration, 2), [a.object_name for a in t.actors])
                              for t in scene.ae_rec_takes])
        for nome in ('Andador', 'Personagem', 'Cubo'):
            resumo(scene, nome)
        boneco = bpy.data.objects['Boneco']
        for track in boneco.animation_data.nla_tracks if boneco.animation_data else ():
            report('NLA %s: %s' % (track.name, [(s.action.name, round(s.frame_start, 1), round(s.frame_end, 1))
                                                for s in track.strips][:6]))
    except Exception:
        report('ERRO\n' + traceback.format_exc())
    report('FIM')
    bpy.ops.wm.quit_blender()


bpy.app.handlers.scene_update_post.append(run)
