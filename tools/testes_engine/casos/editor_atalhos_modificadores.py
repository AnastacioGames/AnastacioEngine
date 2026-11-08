"""Eventos reais com modificador: Ctrl+Z desfaz, Ctrl+Shift+Z refaz, Z sozinho não mexe no undo."""
import time

from rodar import py

MEIO = '''
j = bpy.context.window_manager.windows[0]
a = next(a for a in j.screen.areas if a.type == 'VIEW_3D')
resultado = [a.x + a.width // 2, j.height - 1 - (a.y + a.height // 2)]
'''
X = "resultado = round(bpy.data.objects['Cube'].location.x, 3)"
SOMBRA = '''
j = bpy.context.window_manager.windows[0]
a = next(a for a in j.screen.areas if a.type == 'VIEW_3D')
resultado = a.spaces[0].viewport_shade
'''


def apertar(e, xy, tecla, **mods):
    e.pedir('evento', tipo='MOUSEMOVE', valor='NOTHING', x=xy[0], y=xy[1])
    time.sleep(0.2)
    for valor in ('PRESS', 'RELEASE'):
        r = e.pedir('evento', tipo=tecla, valor=valor, x=xy[0], y=xy[1], **mods)
        assert r['ok'], r
    time.sleep(0.5)  # a fila de eventos anda no laço principal


def testar(t):
    e = t.editor()
    xy = py(e, MEIO)
    py(e, "c = bpy.data.objects['Cube']; bpy.context.scene.objects.active = c; c.select = True\n"
          "bpy.ops.ed.undo_push(contexto('VIEW_3D'), message='selecionar')")
    x0 = py(e, X)
    py(e, "bpy.data.objects['Cube'].location.x += 4\n"
          "bpy.ops.ed.undo_push(contexto('VIEW_3D'), message='mover')")
    x1 = py(e, X)
    assert x1 == x0 + 4, 'não moveu: %s -> %s' % (x0, x1)

    sombra0 = py(e, SOMBRA)
    apertar(e, xy, 'Z')
    sombra1 = py(e, SOMBRA)
    assert sombra1 != sombra0, 'Z sozinho não trocou o shading (%s)' % sombra0
    assert py(e, X) == x1, 'Z sozinho desfez'

    apertar(e, xy, 'Z', ctrl=True)
    assert py(e, X) == x0, 'Ctrl+Z não desfez: x=%s' % py(e, X)
    apertar(e, xy, 'Z', ctrl=True, shift=True)
    assert py(e, X) == x1, 'Ctrl+Shift+Z não refez: x=%s' % py(e, X)
    t.nota('shading %s -> %s; x %s -> %s -> %s' % (sombra0, sombra1, x1, x0, x1))
