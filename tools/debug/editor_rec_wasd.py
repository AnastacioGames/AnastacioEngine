# Teste do Rec Play com teclas de verdade: Esc na contagem, WASD, camadas, Assistir e Regravar.
# REC_RES = relatorio; REC_LOG = posicoes no jogo; REC_PY = python do sistema, roda teclas_rec.py.
#   AnastacioEngine.exe cena.range --python tools/debug/editor_rec_wasd.py
import bpy
import os
import subprocess
import traceback

state = {'updates': 0, 'done': False}
TECLAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'teclas_rec.py')


def report(texto):
    with open(os.environ['REC_RES'], 'a') as f:
        f.write(texto + '\n')


def apertar(*passos):
    subprocess.Popen([os.environ['REC_PY'], TECLAS, str(os.getpid()), os.environ['REC_RES']] + list(passos))


def marcar(scene, *nomes):
    for ob in scene.objects:
        ob.ae_rec_actor = ob.name in nomes


def jogo(titulo):
    """Primeira e ultima posicao de Andador e Personagem no jogo; so conta o Cubo vivo (com logica)."""
    log = os.environ['REC_LOG']
    if not os.path.exists(log):
        report('%s: sem log do jogo (logica do Cubo parada?)' % titulo)
        return
    with open(log) as f:
        linhas = f.read().split('\n')[:-1]
    os.remove(log)
    report('%s: %d passos, inicio %s fim %s' % (titulo, len(linhas), linhas[0], linhas[-1]))


def takes(scene):
    report('takes: %s' % [(t.name, round(t.duration, 2), [a.object_name for a in t.actors], [a.action_name for a in t.actors])
                          for t in scene.ae_rec_takes])


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
        scene.ae_rec_countdown = 1
        scene.ae_rec_max_duration = 8.0

        marcar(scene, 'Andador')
        apertar('espera:1.8', 'W:1', 'espera:0.3', 'F10:0.2')
        report('rec A: %s' % bpy.ops.view3d.game_record(override))
        takes(scene)
        jogo('A')

        # Andador repete sem responder ao W; Personagem anda.
        marcar(scene, 'Personagem')
        apertar('espera:1.8', 'W:2', 'espera:0.3', 'F10:0.2')
        report('rec B sobre A: %s' % bpy.ops.view3d.game_record(override))
        takes(scene)
        jogo('B sobre A')

        report('watch: %s' % bpy.ops.view3d.game_record(override, watch=True))
        takes(scene)
        jogo('Watch')

        # Regrava o Take 2 mais curto, com nada marcado: os atores vem do Take.
        marcar(scene)
        scene.ae_rec_take_index = 1
        apertar('espera:1.8', 'W:0.5', 'espera:0.3', 'F10:0.2')
        report('rerecord: %s' % bpy.ops.view3d.game_record(override, rerecord=True))
        takes(scene)
        jogo('Regravar')
        report('watch: %s' % bpy.ops.view3d.game_record(override, watch=True))
        jogo('Watch 2')
    except Exception:
        report('ERRO\n' + traceback.format_exc())
    report('FIM')
    bpy.ops.wm.quit_blender()


bpy.app.handlers.scene_update_post.append(run)
