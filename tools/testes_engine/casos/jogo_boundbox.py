"""getBoundBoxVolume / getBoundBoxCorners / getBoundBoxSize com escala e rotação (fe33dc9a)."""

CENA = '''
bpy.ops.object.select_all(action='DESELECT')
cube = bpy.data.objects['Cube']
cube.location = (1, 2, 3)
cube.rotation_euler = (0, 0, 0.7853982)
cube.scale = (2, 1, 0.5)
'''

CODIGO = '''
o = cena().objects['Cube']
v = o.getBoundBoxVolume()
w = o.getBoundBoxCorners()
erro = None
try:
    o.getBoundBoxCorners('X')
except ValueError:
    erro = 'ValueError'
resultado = {
    'volume': v[0], 'itens': len(v),
    'offset_bate': all((o.worldPosition + v[i + 1] - w[i]).length < 1e-4 for i in range(8)),
    'local7': list(o.getBoundBoxCorners('LOCAL')[7]),
    'tamanho': list(o.getBoundBoxSize()),
    'erro': erro,
}
'''


def testar(t):
    j = t.jogo(t.gerar(CENA))
    r = j.py(codigo=CODIGO)
    assert abs(r['volume'] - 8.0) < 1e-3, 'volume %s, esperado 8' % r['volume']
    assert r['itens'] == 9, 'getBoundBoxVolume devolveu %d itens' % r['itens']
    assert r['offset_bate'], 'worldPosition + offset != canto WORLD'
    assert all(abs(a - 1) < 1e-4 for a in r['local7']), 'canto LOCAL 7 = %s' % r['local7']
    assert all(abs(a - b) < 1e-4 for a, b in zip(r['tamanho'], (4, 2, 1))), 'tamanho %s' % r['tamanho']
    assert r['erro'] == 'ValueError', 'space inválido não deu ValueError'
