"""camera.boxInsideFrustum(obj) e com getBoundBoxCorners('WORLD'): visível, fora da vista e erro de tipo.

Confere na primeira consulta (antes do primeiro render as matrizes estavam zeradas e tudo dava INSIDE)
e de novo depois de alguns frames renderizados."""

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
    'longe_ponto': cam.pointInsideFrustum(longe.worldPosition),
    'longe_esfera': cam.sphereInsideFrustum(list(longe.worldPosition), 1.0),
    'OUTSIDE': cam.OUTSIDE, 'INSIDE': cam.INSIDE,
    'erro': erro,
}
'''


def conferir(r, quando):
    assert r['cubo_obj'] == r['INSIDE'], '%s: cubo na frente da camera deu %s' % (quando, r['cubo_obj'])
    assert r['cubo_obj'] == r['cubo_lista'], '%s: objeto %s != cantos WORLD %s' % (quando, r['cubo_obj'], r['cubo_lista'])
    assert r['longe_obj'] == r['OUTSIDE'], '%s: cubo atras da camera deu %s' % (quando, r['longe_obj'])
    assert r['longe_obj'] == r['longe_lista'], '%s: objeto %s != cantos WORLD %s' % (quando, r['longe_obj'], r['longe_lista'])
    assert r['longe_esfera'] == r['OUTSIDE'], '%s: esfera atras da camera deu %s' % (quando, r['longe_esfera'])
    assert r['longe_ponto'] == r['OUTSIDE'],'%s: ponto atras deu %s' % (quando, r['longe_ponto'])
    assert r['erro'] == 'TypeError', '%s: argumento invalido nao deu TypeError' % quando


def testar(t):
    j = t.jogo(t.gerar(CENA))
    conferir(j.py(codigo=CODIGO), 'primeira consulta')
    j.esperar(frames=3)
    conferir(j.py(codigo=CODIGO), 'depois do render')
