"""playAction toca uma action de posição: o cubo chega ao fim e para lá (modo PLAY)."""

CENA = '''
cube = bpy.data.objects['Cube']
cube.location = (0, 0, 0)
cube.keyframe_insert('location', frame=1)
cube.location = (0, 0, 5)
cube.keyframe_insert('location', frame=21)
acao = cube.animation_data.action
acao.name = 'Sobe'
acao.use_fake_user = True  # sem dono a action não é salva
cube.animation_data_clear()  # só o playAction deve mover
cube.location = (0, 0, 0)
cube.game.physics_type = 'NO_COLLISION'  # na fábrica é rigid body: a física moveria o cubo
cube.delta_location = (0, 0, 0)  # o Cube de fábrica vem com delta z=1
'''

Z = "resultado = cena().objects['Cube'].worldPosition.z"


def testar(t):
    j = t.jogo(t.gerar(CENA))
    j.esperar(frames=5)
    z0 = j.py(codigo=Z)
    assert abs(z0) < 1e-4, 'cubo se mexeu sem playAction (z=%s, física %s)' % (z0, j.py(codigo="resultado = cena().objects['Cube'].getPhysicsId()"))
    j.py(codigo="from bge import logic as L\ncena().objects['Cube'].playAction('Sobe', 1, 21, play_mode=L.KX_ACTION_MODE_PLAY)")
    j.esperar(frames=10)
    meio = j.py(codigo=Z)
    assert 0.1 < meio < 4.9, 'no meio da action z=%s' % meio
    j.esperar(frames=40)
    fim = j.py(codigo=Z)
    assert abs(fim - 5) < 1e-3, 'fim da action z=%s, esperado 5' % fim
    tocando = j.py(codigo="resultado = cena().objects['Cube'].isPlayingAction()")
    assert not tocando, 'action continua tocando depois do fim (modo PLAY)'
    t.nota('z meio %.2f, fim %.2f' % (meio, fim))
