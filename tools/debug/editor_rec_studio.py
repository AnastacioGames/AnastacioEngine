# Abre o Rec Studio com F9 e deixa os botoes para cliques reais: um contexto falso de script criaria as
# sub-regioes na janela errada. REC_RES = relatorio. Usar com teclas_rec.py e prints_rec.py.
#   AnastacioEngine.exe cena.range --python tools/debug/editor_rec_studio.py
import bpy
import os

state = {'updates': 0, 'done': False}


def report(texto):
    with open(os.environ['REC_RES'], 'a') as f:
        f.write(texto + '\n')


def fim_do_jogo(scene):
    wm = bpy.data.window_managers[0]
    report('jogo acabou: janelas %s takes %s' % ([w.screen.name for w in wm.windows],
           [(t.name, round(t.duration, 2), [a.object_name for a in t.actors]) for t in scene.ae_rec_takes]))


def vigia(scene):
    # Relata cada mudanca de atores, acoes e takes feita pelos arrastes e botoes reais.
    atual = ([(o.name, o.ae_rec_action) for o in scene.objects
              if getattr(o, 'ae_rec_actor', False)], sorted(g.name for g in bpy.data.groups), sorted(o.name for o in scene.objects),
             [t.name for t in scene.ae_rec_takes])
    if atual != state.get('visto'):
        state['visto'] = atual
        report('estado: atores %s grupos %s objetos %s takes %s' % atual)


def run(scene):
    state['updates'] += 1
    if state['done'] or state['updates'] < 3:
        return
    state['done'] = True
    bpy.app.handlers.scene_update_post.remove(run)
    scene.ae_rec_countdown = 1
    scene.ae_rec_max_duration = 3.0
    bpy.app.handlers.game_post.append(fim_do_jogo)
    keymap = bpy.context.window_manager.keyconfigs.active.keymaps['Window']
    keymap.keymap_items.new('screen.rec_studio_show', 'F9', 'PRESS')
    bpy.app.handlers.scene_update_post.append(vigia)
    report('PRONTO')


bpy.app.handlers.scene_update_post.append(run)
