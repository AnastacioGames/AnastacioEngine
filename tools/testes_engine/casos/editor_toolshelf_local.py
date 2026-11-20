"""Tool Shelf (aba Tools > Transform): linhas X/Y/Z em Translate/Rotate/Scale que seguem a orientação
escolhida em Transform Orientations. Confere que o operador anda nos eixos do objeto em Local e guarda
um print da 3D View para conferência visual."""
from rodar import py

CENA = '''
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
ob = bpy.context.object
ob.rotation_euler = (0, 0, 1.5707963)   # 90 graus em Z: o X local aponta para o Y do mundo
bpy.context.scene.objects.active = ob
'''

MOVER = '''
ob = bpy.context.active_object
ob.location = (0, 0, 0)
bpy.context.scene.transform_orientation = '%s'
bpy.ops.transform.translate(value=(1, 0, 0), constraint_axis=(True, False, False),
                            constraint_orientation='%s')
resultado = [round(v, 3) for v in ob.location]
'''


def testar(t):
    cena = t.gerar(CENA)
    e = t.editor(cena)

    local = py(e, MOVER % ('LOCAL', 'LOCAL'))
    t.nota('Local: %s' % local)
    assert abs(local[0]) < 0.01 and abs(local[1] - 1) < 0.01, 'Local não andou no X do objeto: %s' % local

    glob = py(e, MOVER % ('GLOBAL', 'GLOBAL'))
    t.nota('Global: %s' % glob)
    assert abs(glob[0] - 1) < 0.01 and abs(glob[1]) < 0.01, 'Global não andou no X do mundo: %s' % glob

    # abre a Tool Shelf (tecla T com o mouse sobre a 3D View) e guarda o print
    for tipo, valor in (('MOUSEMOVE', 'NOTHING'), ('T', 'PRESS'), ('T', 'RELEASE')):
        r = e.pedir('evento', tipo=tipo, valor=valor, x=700, y=300)
        assert r['ok'], r.get('traceback') or r['erro']
    r = e.pedir('tela', arquivo=str(t.pasta / 'toolshelf.png'), editor='VIEW_3D')
    assert r['ok'], r.get('traceback') or r['erro']
    t.nota('print em %s' % t.pasta)
