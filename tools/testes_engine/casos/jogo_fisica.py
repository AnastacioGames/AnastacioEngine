"""Corpo rígido: cai com a gravidade, para no chão, o raio acerta o chão e a velocidade empurra."""

CENA = '''
cube = bpy.data.objects['Cube']
cube.delta_location = (0, 0, 0)  # o Cube de fábrica vem com delta z=1
cube.location = (0, 0, 6)
cube.game.physics_type = 'RIGID_BODY'
if 'Plane' in bpy.data.objects:  # a cena padrão do Windows já tem um plano no mesmo lugar
    bpy.data.objects.remove(bpy.data.objects['Plane'], do_unlink=True)
antes = set(bpy.data.objects)
bpy.ops.mesh.primitive_plane_add(radius=30, location=(0, 0, 0))
chao = (set(bpy.data.objects) - antes).pop()  # em background o context.object não acompanha o operador
chao.name = 'Chao'
chao.game.physics_type = 'STATIC'
'''

Z = "resultado = cena().objects['Cube'].worldPosition.z"


def testar(t):
    j = t.jogo(t.gerar(CENA))
    j.esperar(frames=15)
    caindo = j.py(codigo=Z)
    assert 1.5 < caindo < 6, 'depois de 15 frames z=%s: devia estar caindo' % caindo
    j.esperar(frames=150)
    parado = j.py(codigo=Z)
    assert abs(parado - 1) < 0.15, 'cubo de lado 2 devia parar em z~1, parou em %s' % parado

    alvo = j.py(codigo="c = cena().objects['Cube']\nr = c.rayCast([0, 0, -10], c.worldPosition, 20)\nresultado = r[0].name if r[0] else None")
    assert alvo == 'Chao', 'raio para baixo acertou %r' % alvo

    j.py(codigo="cena().objects['Cube'].setLinearVelocity([8, 0, 0], False)")
    j.esperar(frames=30)
    x = j.py(codigo="resultado = cena().objects['Cube'].worldPosition.x")
    assert x > 0.3, 'velocidade em x não moveu o cubo (x=%s)' % x
    t.nota('caindo %.2f, parado %.2f, x %.2f' % (caindo, parado, x))
