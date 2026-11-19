"""Complementos do Text Editor com teclas reais: fechar parênteses/aspas sozinho, Backspace no par
vazio, destaque das ocorrências (tela), Format Code (autopep8) com Shift+Alt+F e Ctrl+Z, trechos
prontos (Insert Snippet), Outline, Jedi dentro da engine e os stubs para o VS Code."""
import time

import importlib.util
from pathlib import Path

from rodar import py

_spec = importlib.util.spec_from_file_location('editor_autocompletar', Path(__file__).with_name('editor_autocompletar.py'))
_ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ac)
PREPARAR, tecla, digitar = _ac.PREPARAR, _ac.tecla, _ac.digitar
_ac.TECLAS.update({',': 'COMMA', '"': 'QUOTE', "'": 'QUOTE', '[': 'LEFT_BRACKET', ']': 'RIGHT_BRACKET',
                   '=': 'EQUAL', '+': 'EQUAL', ':': 'SEMI_COLON'})

SCRIPT = '''import bge
from bge import logic

def main(cont):
    own = cont.owner
    own.worldPosition.z += 1
    '''

ESPACO = "a = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == 'TEXT_EDITOR')\nst = a.spaces[0]\n"


def digitar2(e, xy, texto):
    """como digitar, com shift nos símbolos que pedem (layout americano)"""
    for c in texto:
        tipo = _ac.TECLAS.get(c) or _ac.NUMEROS.get(c) or c.upper()
        tecla(e, xy, tipo, c, shift=c.isupper() or c in '#_()":+')
    time.sleep(0.3)


def linha(e):
    return py(e, "t = bpy.data.texts['jogador.py']\nresultado = t.lines[-1].body")


def cursor(e):
    return py(e, "t = bpy.data.texts['jogador.py']\nresultado = t.current_character")


def texto(e):
    return py(e, "resultado = bpy.data.texts['jogador.py'].as_string()")


def colocar(e, conteudo):
    """troca o texto e põe o cursor no fim"""
    py(e, ("t = bpy.data.texts['jogador.py']\nt.from_string(%r)\n"
           "bpy.ops.text.move(contexto('TEXT_EDITOR'), type='FILE_BOTTOM')\n"
           "bpy.ops.text.move(contexto('TEXT_EDITOR'), type='LINE_END')\n" % conteudo)
          + ESPACO + "st.top = 0\na.tag_redraw()\nresultado = True")
    time.sleep(0.3)


def tela(e, t, nome):
    caminho = t.pasta / (nome + '.png')
    e.pedir('tela', arquivo=str(caminho))
    t.nota('%s: %s' % (nome, caminho))
    return caminho


def testar(t):
    e = t.editor()
    xy = py(e, PREPARAR % SCRIPT)
    py(e, ESPACO + "st.use_live_autocomplete = False\nst.use_auto_close = True\n"
          "st.use_highlight_occurrences = True\nresultado = True")
    e.pedir('evento', tipo='MOUSEMOVE', valor='NOTHING', x=xy[0], y=xy[1])

    # 1. fechar sozinho: ( entra com ), o ) digitado só passa por cima, Backspace no par vazio
    colocar(e, SCRIPT)
    digitar2(e, xy, 'x = f(')
    assert linha(e) == '    x = f()', '1a: %r' % linha(e)
    digitar2(e, xy, '1')
    digitar2(e, xy, ')')
    assert linha(e) == '    x = f(1)', '1b: %r' % linha(e)
    assert cursor(e) == len('    x = f(1)'), '1c: cursor %r' % cursor(e)
    digitar2(e, xy, ' + g(')
    tecla(e, xy, 'BACK_SPACE')
    assert linha(e) == '    x = f(1) + g', '1d: %r' % linha(e)
    # colchetes e aspas; aspas grudadas num nome (don't) não fecham
    colocar(e, SCRIPT)
    digitar2(e, xy, 'n = [')
    digitar2(e, xy, '"')
    digitar2(e, xy, 'a')
    digitar2(e, xy, '"')
    digitar2(e, xy, ']')
    assert linha(e) == '    n = ["a"]', '1e: %r' % linha(e)
    colocar(e, SCRIPT)
    digitar2(e, xy, "# don't")
    assert linha(e) == "    # don't", '1f: %r' % linha(e)
    # dentro de string: ( não fecha
    colocar(e, SCRIPT + 'print("a ')
    digitar2(e, xy, '(')
    assert linha(e) == '    print("a (', '1g: %r' % linha(e)
    # desligado: só o caractere
    py(e, ESPACO + "st.use_auto_close = False\nresultado = True")
    colocar(e, SCRIPT)
    digitar2(e, xy, 'f(')
    assert linha(e) == '    f(', '1h: %r' % linha(e)
    py(e, ESPACO + "st.use_auto_close = True\nresultado = True")

    # 2. ocorrências: cursor em 'own' (3 lugares visíveis) -> marcas atrás do nome (tela)
    colocar(e, SCRIPT + 'own.applyForce((0, 0, 1))')
    for _ in range(len('.applyForce((0, 0, 1))')):
        tecla(e, xy, 'LEFT_ARROW')
    time.sleep(0.3)
    tela(e, t, '2_ocorrencias_own')

    # 3. Format Code: Shift+Alt+F arruma, Ctrl+Z volta tudo de uma vez
    feio = 'import os\ndef f( a,b ):\n  return a+b\nx=f(1,2)\n'
    py(e, "t = bpy.data.texts['jogador.py']\nt.from_string(%r)\nresultado = True" % feio)
    tecla(e, xy, 'F', shift=True, alt=True)
    time.sleep(0.4)
    novo = texto(e)
    assert novo == 'import os\n\n\ndef f(a, b):\n    return a+b\n\n\nx = f(1, 2)\n', '3a: %r' % novo
    tela(e, t, '3_formatado')
    tecla(e, xy, 'Z', ctrl=True)
    time.sleep(0.3)
    assert texto(e) == feio, '3b: undo deixou %r' % texto(e)
    # com erro de sintaxe não mexe
    quebrado = 'def f(:\n    pass\n'
    py(e, "t = bpy.data.texts['jogador.py']\nt.from_string(%r)\nresultado = True" % quebrado)
    r = py(e, "resultado = list(bpy.ops.text.format_code(contexto('TEXT_EDITOR')))")
    assert r == ['CANCELLED'] and texto(e) == quebrado, '3c: %r %r' % (r, texto(e))

    # 4. Insert Snippet: com o recuo da linha, cursor no $0, um Ctrl+Z tira
    colocar(e, SCRIPT)
    r = py(e, "resultado = list(bpy.ops.text.insert_snippet(contexto('TEXT_EDITOR'), snippet='INIT'))")
    assert r == ['FINISHED'], r
    corpo = texto(e)
    assert corpo.endswith('    if "init" not in own:\n        own["init"] = True\n        '), '4a: %r' % corpo
    digitar2(e, xy, 'pass')
    assert texto(e).endswith('        pass'), '4b: %r' % texto(e)
    tela(e, t, '4_snippet')

    # 5. Outline: classes e funções na ordem, método dentro da classe
    codigo = 'class A:\n    def b(self):\n        pass\n\ndef c():\n    """def falso():"""\n    pass\n'
    py(e, "t = bpy.data.texts['jogador.py']\nt.from_string(%r)\nresultado = True" % codigo)
    r = py(e, "import text_code_tools as tc\nresultado = [list(i) for i in tc._outline(bpy.data.texts['jogador.py'])]")
    assert r == [[1, 0, 'class', 'A'], [2, 1, 'def', 'b'], [5, 0, 'def', 'c']], '5: %r' % r
    py(e, "bpy.ops.text.jump(contexto('TEXT_EDITOR'), line=5)\nresultado = True")
    assert py(e, "resultado = bpy.data.texts['jogador.py'].current_line_index") == 4
    py(e, "bpy.ops.text.properties(contexto('TEXT_EDITOR'))\nresultado = True")
    time.sleep(0.4)
    tela(e, t, '5_outline')

    # 6. Jedi dentro da engine (Python 3.11 + stubs): classe do usuário guardando um objeto
    codigo = ('from bge import logic\n\nclass Inimigo:\n    def __init__(self):\n'
              '        self.alvo = logic.getCurrentScene().objects["Player"]\n\n'
              'def criar():\n    return Inimigo()\n\nini = criar()\nini.alvo.')
    r = py(e, "import time, text_autocomplete as ta\nt0 = time.time()\n"
              "r = ta.candidatos_texto(%r, 10, 9, None)\n"
              "resultado = [time.time() - t0, r.split('\\n')[:1], 'qworldPosition' in r.split('\\n')]" % codigo)
    t.nota('jedi: %.2f s' % r[0])
    assert r[1] == ['OK'] and r[2], '6a: %r' % r
    assert r[0] < 3.0, '6a: Jedi lento demais (%.1f s)' % r[0]
    r = py(e, "import text_autocomplete as ta\n"
              "resultado = ta.assinatura_texto(%r, 10, 17, None)" % (codigo[:-1] + '.rayCast('))
    assert r.startswith('OK') and r.split('\n')[2].startswith('objto'), '6b: %r' % r

    # 7. stubs do VS Code: copia para typings/, não mexe em typings de outra pessoa
    pasta = t.pasta / 'projeto_vscode'
    alheia = t.pasta / 'projeto_alheio'
    (alheia / 'typings' / 'bge').mkdir(parents=True)
    r = py(e, "import os, text_external_editor as x\nos.makedirs(%r, exist_ok=True)\n"
              "a = x.install_stubs(%r)\nb = x.install_stubs(%r)\nc = x.install_stubs(%r)\n"
              "resultado = [a, b, c, os.path.isfile(os.path.join(%r, 'typings', 'bge', 'types.pyi')),"
              " x._command('C:/vs/Code.exe', 'C:/p/s.py', 3, 'C:/p')]"
              % (str(pasta), str(pasta), str(pasta), str(alheia), str(pasta)))
    assert r[0][0] and r[1] == [True, 'VS Code hints are up to date'] and not r[2][0] and r[3], '7: %r' % r
    assert r[4] == ['C:/vs/Code.exe', 'C:/p', '-g', 'C:/p/s.py:3'], '7b: %r' % r[4]
