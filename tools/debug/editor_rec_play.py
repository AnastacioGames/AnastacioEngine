# Aceite do Rec Play com janela: grava duas vezes pela view3d.game_record, toca a Action no editor
# e compara com a matriz real que o jogo registrou. Depois de Ctrl+Z, deixa a animacao tocando.
# REC_LOG = log do jogo; REC_RES = relatorio.
#   AnastacioEngine.exe cena.range --python tools/debug/editor_rec_play.py
import bpy
import json
import os
import traceback
from mathutils import Matrix

ATORES = ('Cubo', 'Girador', 'Filho')
PASSO = 1.0 / 60.0
state = {'updates': 0, 'done': False}


def report(text):
    with open(os.environ['REC_RES'], 'a') as f:
        f.write(text + '\n')


def actions():
    return sorted((a.name, a.users, a.use_fake_user) for a in bpy.data.actions)


def compare(scene):
    with open(os.environ['REC_LOG']) as f:
        log = json.load(f)
    report('passos do jogo: %d' % len(log))
    for nome in ATORES:
        ob = bpy.data.objects[nome]
        act = ob.animation_data.action
        chaves = sum(len(c.keyframe_points) for c in act.fcurves)
        report('%s: action=%s curvas=%d chaves=%d rotation_mode=%s' % (
            nome, act.name, len(act.fcurves), chaves, ob.rotation_mode))
        for atraso in (0, 1):
            pos = rot = 0.0
            for i in range(len(log) - 1 - atraso):
                frame = scene.frame_start + i * PASSO * scene.render.fps
                scene.frame_set(int(frame), frame - int(frame))
                real = Matrix(log[i + atraso][nome])
                pos = max(pos, (ob.matrix_world.translation - real.translation).length)
                a, b = ob.matrix_world.to_3x3(), real.to_3x3()
                rot = max(rot, max(abs(a[r][c] - b[r][c]) for r in range(3) for c in range(3)))
            report('  log+%d passo: erro max posicao=%.4f matriz=%.4f' % (atraso, pos, rot))


class RecFim(bpy.types.Operator):
    """Desfaz pelo laco de eventos, como Ctrl+Z: dentro do handler a cena em uso seria liberada."""
    bl_idname = 'wm.rec_fim'
    bl_label = 'Rec Fim'

    def invoke(self, context, event):
        self.timer = context.window_manager.event_timer_add(0.2, context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        context.window_manager.event_timer_remove(self.timer)
        try:
            bpy.ops.ed.undo()
            report('depois do undo: %s' % actions())
            report('Cubo usa: %s' % bpy.data.objects['Cubo'].animation_data.action.name)
            bpy.context.scene.frame_set(bpy.context.scene.frame_start)
            bpy.ops.screen.animation_play()
        except Exception:
            report('ERRO\n' + traceback.format_exc())
        report('FIM')
        return {'FINISHED'}


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

    # O contexto forcado vale tambem no redesenho antes do jogo e quebra outras areas (Outliner):
    # em tela cheia so a 3D View e desenhada. Um clique real no botao nao tem esse problema.
    if not state.get('full'):
        state['full'] = True
        state['updates'] = 0
        bpy.ops.screen.screen_full_area(context())
        return
    state['done'] = True
    bpy.app.handlers.scene_update_post.remove(run)
    try:
        override = context()
        report('tolerancia=%s' % scene.ae_rec_keyframe_tolerance)
        report('rec 1: %s' % bpy.ops.view3d.game_record(override))
        report('actions: %s' % actions())
        compare(scene)
        report('rec 2: %s' % bpy.ops.view3d.game_record(override))
        report('actions: %s' % actions())
        bpy.utils.register_class(RecFim)
        bpy.ops.wm.rec_fim('INVOKE_DEFAULT')
    except Exception:
        report('ERRO\n' + traceback.format_exc())
        report('FIM')


bpy.app.handlers.scene_update_post.append(run)
