"""Undo/redo restaura nós adicionados e a cor pintada em Vertex Paint."""
from rodar import py

ATIVO = '''
cubo = bpy.data.objects['Cube']
bpy.context.scene.objects.active = cubo
cubo.select = True
'''


def passo(e, codigo, nome):
    py(e, ATIVO + codigo + "\nbpy.ops.ed.undo_push(contexto('VIEW_3D'), message=%r)" % nome)


def desfazer(e, op, n):
    for _ in range(n):
        py(e, "bpy.ops.ed.%s(contexto('VIEW_3D'))" % op)


def testar(t):
    e = t.editor()
    passo(e, "bpy.data.node_groups.new('Grupo', 'ShaderNodeTree').use_fake_user = True", 'grupo')
    passo(e, "bpy.data.node_groups['Grupo'].nodes.new('ShaderNodeMath')", 'no')
    nos = "resultado = len(bpy.data.node_groups['Grupo'].nodes)"
    assert py(e, nos) == 1, 'nó não foi criado'
    desfazer(e, 'undo', 1)
    assert py(e, nos) == 0, 'undo não tirou o nó: %s' % py(e, nos)
    desfazer(e, 'redo', 1)
    assert py(e, nos) == 1, 'redo não devolveu o nó: %s' % py(e, nos)

    passo(e, "cubo.data.vertex_colors.new('Cor')", 'camada')
    passo(e, "bpy.ops.object.mode_set(contexto('VIEW_3D'), mode='VERTEX_PAINT')", 'vpaint')
    cor = ("c = bpy.data.objects['Cube']; resultado = [c.mode] + "
           "[round(x, 2) for x in c.data.vertex_colors['Cor'].data[0].color]")
    antes = py(e, cor)
    passo(e, "bpy.context.tool_settings.vertex_paint.brush.color = (1, 0, 0)\n"
             "bpy.ops.paint.vertex_color_set(contexto('VIEW_3D'))", 'pintar')
    pintado = py(e, cor)
    assert pintado[:4] == ['VERTEX_PAINT', 1.0, 0.0, 0.0], 'não pintou: %s' % pintado
    desfazer(e, 'undo', 1)
    meio = py(e, cor)
    assert meio == antes, 'undo não voltou a cor: %s x %s' % (meio, antes)
    desfazer(e, 'redo', 1)
    volta = py(e, cor)
    assert volta == pintado, 'redo não voltou a cor: %s x %s' % (volta, pintado)
    t.nota('cor %s -> %s -> %s' % (antes[1:], pintado[1:], volta[1:]))
