import bge
import os

estado = {'quadro': 0, 'fase': 0}


def relatar(texto):
    with open(os.environ['REC_RES'], 'a') as f:
        f.write(texto + '\n')


def tick(cont):
    scene = bge.logic.getCurrentScene()
    cubo = scene.objects['Cubo']
    estado['quadro'] += 1
    q = estado['quadro']
    if estado['fase'] == 0 and q == 5:
        takes = scene.takes
        relatar('takes %s' % takes)
        relatar('nome errado %s' % cubo.play_take('Nao existe'))
        relatar('chao sem take %s' % scene.objects['Chao'].play_take(takes[0]))
        relatar('play %s tocando %s z %.2f' % (cubo.play_take(takes[0]), cubo.is_playing_take(), cubo.worldPosition.z))
        estado['fase'] = 1
    elif estado['fase'] == 1 and q == 15:
        cubo.stop_take()
        estado['z'] = cubo.worldPosition.z
        relatar('parou tocando %s z %.2f' % (cubo.is_playing_take(), estado['z']))
        estado['fase'] = 2
    elif estado['fase'] == 2 and q == 35:
        relatar('fisica voltou, caiu %s z %.2f' % (cubo.worldPosition.z < estado['z'] - 0.1, cubo.worldPosition.z))
        relatar('scene.play_take %s errado %s' % (scene.play_take(scene.takes[0]), scene.play_take('Nao existe')))
        relatar('tocando %s' % cubo.is_playing_take())
        estado['fase'] = 3
    elif estado['fase'] == 3 and q > 36 and not cubo.is_playing_take():
        relatar('take acabou no quadro %d z %.2f' % (q, cubo.worldPosition.z))
        bge.logic.endGame()
    elif q > 600:
        relatar('tempo esgotado')
        bge.logic.endGame()
