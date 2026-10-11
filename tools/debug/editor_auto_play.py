# Aperta Play N vezes dentro do editor e fecha, para ler o relatorio de memoria nao liberada
# ("Error: Not freed memory blocks") e os avisos de --debug sem depender de alguem apertar P.
# A cena precisa encerrar o jogo sozinha (ver cenas/criar_cena_startup_autosair.py). N = 0 so
# abre e fecha. Fechar por aqui grava o quit.blend ("Recover Last Session") com a cena de teste.
#   AnastacioEngine.exe --debug --debug-gpu cena.range --python tools/debug/editor_auto_play.py -- 3
import bpy
import sys

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
plays = int(argv[0]) if argv else 3
state = {'updates': 0, 'done': False}


def run(scene):
    state['updates'] += 1
    if state['done'] or state['updates'] < 3:
        return
    state['done'] = True
    bpy.app.handlers.scene_update_post.remove(run)
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for region in area.regions:
                if region.type == 'WINDOW':
                    override = {'window': window, 'screen': screen, 'area': area, 'region': region, 'scene': scene}
                    for n in range(plays):
                        print("AUTO_PLAY", n, bpy.ops.view3d.game_start(override))
                    print("AUTO_PLAY quit")
                    bpy.ops.wm.quit_blender()
                    return
    print("AUTO_PLAY: nenhuma VIEW_3D na tela")


bpy.app.handlers.scene_update_post.append(run)
