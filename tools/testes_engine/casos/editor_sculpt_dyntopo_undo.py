"""Undo/redo com dyntopo no sculpt não derruba o editor e volta ao estado certo."""
from rodar import py

ATIVO = '''
cubo = bpy.data.objects['Cube']
bpy.context.scene.objects.active = cubo
cubo.select = True
'''


def passo(e, codigo, nome):
    py(e, ATIVO + codigo + "\nbpy.ops.ed.undo_push(contexto('VIEW_3D'), message=%r)" % nome)


def testar(t):
    e = t.editor()
    estado = "c = bpy.data.objects['Cube']; resultado = [c.mode, bool(c.use_dynamic_topology_sculpting)]"
    # Na interface, selecionar o Cube grava um passo; sem ele o undo volta ao Sun ativo.
    passo(e, '', 'selecionar')
    passo(e, "bpy.ops.object.mode_set(contexto('VIEW_3D'), mode='SCULPT')", 'sculpt')
    passo(e, "bpy.ops.sculpt.dynamic_topology_toggle(contexto('VIEW_3D'))", 'dyntopo')
    fim = py(e, estado)
    assert fim == ['SCULPT', True], 'estado inesperado: %s' % fim
    for _ in range(2):
        py(e, "bpy.ops.ed.undo(contexto('VIEW_3D'))")
    meio = py(e, estado)
    for _ in range(2):
        py(e, "bpy.ops.ed.redo(contexto('VIEW_3D'))")
    volta = py(e, estado)
    assert volta == fim, 'redo não voltou: %s x %s' % (volta, fim)
    t.nota('undo %s, redo %s' % (meio, volta))
