"""Autocompletar do Text Editor com teclas reais: lista ao vivo depois do ponto, Tab confirma,
Enter numa palavra completa vira nova linha, Esc fecha, caixa corrigida, Backspace refiltra,
nada em comentário, Ctrl+Z desfaz a confirmação."""
import time

from rodar import py

PREPARAR = '''
j = bpy.context.window_manager.windows[0]
a = next(a for a in j.screen.areas if a.type == 'VIEW_3D')
a.type = 'TEXT_EDITOR'
t = bpy.data.texts.new("jogador.py")
t.from_string(%r)
a.spaces[0].text = t
a.spaces[0].use_live_autocomplete = True
resultado = [a.x + a.width // 2, j.height - 1 - (a.y + a.height // 2)]
'''

SCRIPT = '''import bge
from bge import logic

def main(cont):
    own = cont.owner
    '''

TECLAS = {'.': 'PERIOD', ' ': 'SPACE', '#': 'THREE', '_': 'MINUS', '(': 'NINE', ')': 'ZERO'}
NUMEROS = dict(zip('0123456789', ['ZERO', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE']))


def tecla(e, xy, tipo, texto='', **mods):
    for valor in ('PRESS', 'RELEASE'):
        r = e.pedir('evento', tipo=tipo, valor=valor, x=xy[0], y=xy[1],
                    texto=texto if valor == 'PRESS' else '', **mods)
        assert r['ok'], r
    time.sleep(0.15)


def digitar(e, xy, texto):
    for c in texto:
        tipo = TECLAS.get(c) or NUMEROS.get(c) or c.upper()
        tecla(e, xy, tipo, c, shift=c.isupper() or c in '#_()')
    time.sleep(0.3)


def linha(e, deslocamento=0):
    return py(e, "t = bpy.data.texts['jogador.py']\n"
                 "resultado = t.lines[%d].body" % (len(SCRIPT.split('\n')) - 1 + deslocamento))


def reiniciar_linha(e):
    py(e, "t = bpy.data.texts['jogador.py']\nt.from_string(%r)\n"
          "t.current_line_index = len(t.lines) - 1 if hasattr(t, 'current_line_index') else 0\n"
          "bpy.ops.text.move(contexto('TEXT_EDITOR'), type='FILE_BOTTOM')\n"
          "bpy.ops.text.move(contexto('TEXT_EDITOR'), type='LINE_END')\n"
          "resultado = True" % SCRIPT)
    time.sleep(0.3)


def testar(t):
    e = t.editor()
    xy = py(e, PREPARAR % SCRIPT)
    e.pedir('evento', tipo='MOUSEMOVE', valor='NOTHING', x=xy[0], y=xy[1])
    time.sleep(0.3)

    # 1. depois do ponto a lista abre sozinha; digitar filtra; Tab confirma
    reiniciar_linha(e)
    digitar(e, xy, 'own.worldPos')
    tecla(e, xy, 'TAB')
    assert linha(e) == '    own.worldPosition', '1: %r' % linha(e)
    t.nota('own.worldPos + Tab -> %r' % linha(e))

    # 2. Ctrl+Z desfaz a confirmação inteira (volta ao que foi digitado)
    tecla(e, xy, 'Z', ctrl=True)
    time.sleep(0.3)
    assert linha(e) == '    own.worldPos', '2: undo deixou %r' % linha(e)

    # 3. caixa errada: "getcu" vira getCurrentController (palavra inteira trocada)
    reiniciar_linha(e)
    digitar(e, xy, 'logic.getcu')
    tecla(e, xy, 'TAB')
    assert linha(e) == '    logic.getCurrentController', '3: %r' % linha(e)

    # 4. Esc fecha e a próxima tecla é texto normal (Tab vira indentação, não completa)
    reiniciar_linha(e)
    digitar(e, xy, 'own.wor')
    tecla(e, xy, 'ESC')
    digitar(e, xy, 'x')
    assert linha(e) == '    own.worx', '4: %r' % linha(e)

    # 5. Enter numa palavra que já é a sugestão inteira faz nova linha
    reiniciar_linha(e)
    digitar(e, xy, 'own.scene')
    n0 = py(e, "resultado = len(bpy.data.texts['jogador.py'].lines)")
    tecla(e, xy, 'RET')
    n1 = py(e, "resultado = len(bpy.data.texts['jogador.py'].lines)")
    assert n1 == n0 + 1 and linha(e) == '    own.scene', '5: linhas %s->%s, %r' % (n0, n1, linha(e))

    # 6. Backspace com a lista aberta refiltra (não fecha nem engole a tecla)
    reiniciar_linha(e)
    digitar(e, xy, 'own.worldx')
    tecla(e, xy, 'BACK_SPACE')
    assert linha(e) == '    own.world', '6a: %r' % linha(e)
    digitar(e, xy, 'Pos')
    tecla(e, xy, 'TAB')
    assert linha(e) == '    own.worldPosition', '6b: %r' % linha(e)

    # 7. comentário: nada abre, Tab é Tab
    reiniciar_linha(e)
    digitar(e, xy, '# own.wor')
    tecla(e, xy, 'TAB')
    assert linha(e).startswith('    # own.wor') and linha(e) != '    # own.world', '7: %r' % linha(e)

    # 8. palavra solta com 3 letras abre (palavras do documento / builtins): "pri" + Tab = print
    reiniciar_linha(e)
    digitar(e, xy, 'prin')
    tecla(e, xy, 'TAB')
    assert linha(e) == '    print', '8: %r' % linha(e)

    # 9. espaço/parêntese fecha a lista e entra no texto
    reiniciar_linha(e)
    digitar(e, xy, 'own.wor(')
    # (o parêntese entra com o par: Auto Close Brackets)
    assert linha(e) == '    own.wor()', '9: %r' % linha(e)

    # 9b. lista aberta e Tab com o mouse sobre outra área: não completa aqui
    outra = py(e, "j = bpy.context.window_manager.windows[0]\n"
                  "a = next(a for a in j.screen.areas if a.type == 'PROPERTIES')\n"
                  "resultado = [a.x + a.width // 2, j.height - 1 - (a.y + a.height // 2)]")
    reiniciar_linha(e)
    digitar(e, xy, 'own.worldPos')
    e.pedir('evento', tipo='MOUSEMOVE', valor='NOTHING', x=outra[0], y=outra[1])
    time.sleep(0.2)
    tecla(e, outra, 'TAB')
    e.pedir('evento', tipo='MOUSEMOVE', valor='NOTHING', x=xy[0], y=xy[1])
    time.sleep(0.3)
    assert linha(e) == '    own.worldPos', '9b: Tab em outra área completou: %r' % linha(e)
    # 9c. o cursor mudou por fora (seleção): a lista não substitui nada
    reiniciar_linha(e)
    digitar(e, xy, 'own.worldPos')
    tecla(e, xy, 'LEFT_ARROW', shift=True)
    tecla(e, xy, 'TAB')
    # (Tab com seleção indenta, comportamento normal do editor)
    assert linha(e).strip() == 'own.worldPos', '9c: %r' % linha(e)

    # 10. desligado: a lista não abre sozinha (Tab indenta)
    py(e, "a = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == 'TEXT_EDITOR')\n"
          "a.spaces[0].use_live_autocomplete = False\nresultado = True")
    reiniciar_linha(e)
    digitar(e, xy, 'own.worldPos')
    tecla(e, xy, 'TAB')
    assert linha(e) != '    own.worldPosition', '10: completou desligado: %r' % linha(e)
    # Ctrl+Space continua funcionando (único candidato entra direto)
    reiniciar_linha(e)
    digitar(e, xy, 'own.worldPos')
    tecla(e, xy, 'SPACE', ctrl=True)
    assert linha(e) == '    own.worldPosition', '10b: Ctrl+Space: %r' % linha(e)

    e.pedir('tela', arquivo=str(t.pasta / 'final.png'))
