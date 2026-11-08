"""Undo/redo atravessando passo de edit mode não derruba o editor (bbfc8202).

Por script a troca de modo não grava passo de undo; o undo_push imita a interface.
"""
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
    estado = "c = bpy.data.objects['Cube']; c.update_from_editmode(); resultado = [c.mode, len(c.data.vertices)]"
    passo(e, "bpy.ops.object.mode_set(contexto('VIEW_3D'), mode='EDIT')", 'edit')
    assert py(e, estado)[0] == 'EDIT', 'não entrou no edit mode: %s' % py(e, estado)
    passo(e, "bpy.ops.mesh.select_all(contexto('VIEW_3D'), action='SELECT')\n"
             "bpy.ops.mesh.subdivide(contexto('VIEW_3D'))", 'subdiv')
    passo(e, "bpy.ops.object.mode_set(contexto('VIEW_3D'), mode='OBJECT')", 'object')
    fim = py(e, estado)
    assert fim == ['OBJECT', 26], 'estado final inesperado: %s' % fim
    for _ in range(3):
        py(e, "bpy.ops.ed.undo(contexto('VIEW_3D'))")
    meio = py(e, estado)
    for _ in range(3):
        py(e, "bpy.ops.ed.redo(contexto('VIEW_3D'))")
    volta = py(e, estado)
    assert volta == fim, 'redo não voltou ao estado final: %s x %s' % (volta, fim)
    t.nota('undo %s, redo %s' % (meio, volta))
