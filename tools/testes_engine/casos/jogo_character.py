"""Character: cai até o chão, anda com walkDirection e pula com jump()."""

CENA = '''
cube = bpy.data.objects['Cube']
cube.delta_location = (0, 0, 0)  # o Cube de fábrica vem com delta z=1
cube.location = (0, 0, 4)
cube.game.physics_type = 'CHARACTER'
bpy.ops.mesh.primitive_plane_add(radius=30, location=(0, 0, 0))
chao = bpy.data.objects['Plane']  # em background o context.object não acompanha o operador
chao.name = 'Chao'
chao.game.physics_type = 'STATIC'
'''

BASE = "from bge import constraints\nc = cena().objects['Cube']\nchar = constraints.getCharacter(c)\n"


def testar(t):
    j = t.jogo(t.gerar(CENA))
    j.esperar(frames=120)
    z0, no_chao = j.py(codigo=BASE + "resultado = [c.worldPosition.z, char.onGround]")
    assert no_chao, 'Character não chegou ao chão (z=%s)' % z0
    assert z0 < 3, 'Character não caiu (z=%s)' % z0

    j.py(codigo=BASE + "char.walkDirection = [0.05, 0, 0]")
    j.esperar(frames=30)
    x = j.py(codigo=BASE + "char.walkDirection = [0, 0, 0]\nresultado = c.worldPosition.x")
    assert x > 0.3, 'walkDirection não moveu o Character (x=%s)' % x

    j.py(codigo=BASE + "char.jump()")
    j.esperar(frames=8)
    z1, no_ar = j.py(codigo=BASE + "resultado = [c.worldPosition.z, not char.onGround]")
    assert no_ar and z1 > z0 + 0.05, 'jump() não subiu (z %s -> %s)' % (z0, z1)
    j.esperar(frames=120)
    z2, voltou = j.py(codigo=BASE + "resultado = [c.worldPosition.z, char.onGround]")
    assert voltou and abs(z2 - z0) < 0.15, 'não voltou ao chão (z %s, esperado %s)' % (z2, z0)
    t.nota('chão z %.2f, x %.2f, pulo z %.2f' % (z0, x, z1))
