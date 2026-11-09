"""camera.boxInsideFrustum(obj) e com getBoundBoxCorners('WORLD'): visível, fora da vista e erro de tipo."""

CENA = '''
bpy.ops.object.select_all(action='DESELECT')
cube = bpy.data.objects['Cube']
longe = cube.copy()
longe.name = 'Longe'
longe.location = (40, -40, 25)
bpy.context.scene.objects.link(longe)
'''

CODIGO = '''
cam = cena().active_camera
cubo = cena().objects['Cube']
longe = cena().objects['Longe']
erro = None
try:
    cam.boxInsideFrustum(42)
except TypeError:
    erro = 'TypeError'
resultado = {
    'cubo_obj': cam.boxInsideFrustum(cubo),
    'cubo_lista': cam.boxInsideFrustum(cubo.getBoundBoxCorners('WORLD')),
    'longe_obj': cam.boxInsideFrustum(longe),
    'longe_lista': cam.boxInsideFrustum(longe.getBoundBoxCorners('WORLD')),
    'OUTSIDE': cam.OUTSIDE, 'INSIDE': cam.INSIDE,
    'erro': erro,
}
'''


def testar(t):
    j = t.jogo(t.gerar(CENA))
    r = j.py(codigo=CODIGO)
    assert r['cubo_obj'] == r['INSIDE'], 'cubo na frente da camera deu %s' % r['cubo_obj']
    assert r['cubo_obj'] == r['cubo_lista'], 'objeto %s != cantos WORLD %s' % (r['cubo_obj'], r['cubo_lista'])
    assert r['longe_obj'] == r['OUTSIDE'], 'cubo atras da camera deu %s' % r['longe_obj']
    assert r['longe_obj'] == r['longe_lista'], 'objeto %s != cantos WORLD %s' % (r['longe_obj'], r['longe_lista'])
    assert r['erro'] == 'TypeError', 'argumento invalido nao deu TypeError'
