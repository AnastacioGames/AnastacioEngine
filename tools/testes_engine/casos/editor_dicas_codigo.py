"""Dicas de código do Text Editor com teclas reais: erros sublinhados depois da pausa na digitação,
caixa de assinatura ao digitar '(' (parâmetro atual muda com a vírgula, Esc fecha) e detalhe do
item selecionado na lista do autocompletar. Confere pelo estado (python) e guarda telas."""
import time

import importlib.util
from pathlib import Path

from rodar import py

# mesmas teclas/preparo do teste do autocompletar
_spec = importlib.util.spec_from_file_location('editor_autocompletar', Path(__file__).with_name('editor_autocompletar.py'))
_ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ac)
PREPARAR, tecla, digitar = _ac.PREPARAR, _ac.tecla, _ac.digitar
_ac.TECLAS[','] = 'COMMA'

SCRIPT = '''import bge
from bge import logic

def main(cont):
    own = cont.owner
    x = jogadr + 1
    '''


def linha(e):
    return py(e, "t = bpy.data.texts['jogador.py']\nresultado = t.lines[-1].body")


def reiniciar_linha(e):
    py(e, "t = bpy.data.texts['jogador.py']\nt.from_string(%r)\n"
          "bpy.ops.text.move(contexto('TEXT_EDITOR'), type='FILE_BOTTOM')\n"
          "bpy.ops.text.move(contexto('TEXT_EDITOR'), type='LINE_END')\n"
          "a = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == 'TEXT_EDITOR')\n"
          "a.spaces[0].top = 0\na.tag_redraw()\n"
          "resultado = True" % SCRIPT)
    time.sleep(0.3)


def tela(e, t, nome):
    caminho = t.pasta / (nome + '.png')
    e.pedir('tela', arquivo=str(caminho))
    t.nota('%s: %s' % (nome, caminho))
    return caminho


def testar(t):
    e = t.editor()
    xy = py(e, PREPARAR % SCRIPT)
    py(e, "a = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == 'TEXT_EDITOR')\n"
          "a.spaces[0].use_live_diagnostics = True\nresultado = True")
    e.pedir('evento', tipo='MOUSEMOVE', valor='NOTHING', x=xy[0], y=xy[1])

    # 1. o provedor acha o erro do texto (nome indefinido) e a sintaxe quebrada
    r = py(e, "import text_autocomplete as ta\n"
              "resultado = ta.diagnosticos_texto(bpy.data.texts['jogador.py'].as_string())")
    assert "undefined name 'jogadr'" in r, r
    # pausa: o timer redesenha e o C guarda o resultado (sublinhado vermelho na tela)
    reiniciar_linha(e)
    time.sleep(1.5)
    tela(e, t, '1_erro_nome')

    # 2. digitando '(' abre a assinatura; a virgula passa para o proximo parametro
    digitar(e, xy, 'own.applyForce(')
    time.sleep(0.4)
    tela(e, t, '2_assinatura_force')
    r = py(e, "import text_autocomplete as ta\nt = bpy.data.texts['jogador.py']\n"
              "col = len(t.current_line.body.encode('utf-8')[:t.current_character].decode('utf-8'))\n"
              "resultado = ta.assinatura_texto(t.as_string(), t.current_line_index, col)")
    assert r.split('\n')[2] == 'force', r
    digitar(e, xy, '(0, 0, 1), ')
    time.sleep(0.4)
    tela(e, t, '3_assinatura_local')
    # Esc fecha a caixa e não mexe no texto
    antes = linha(e)
    tecla(e, xy, 'ESC')
    assert linha(e) == antes, '%r -> %r' % (antes, linha(e))
    tela(e, t, '4_esc_fechou')
    # sintaxe quebrada (parentese aberto) aparece depois da pausa
    time.sleep(1.5)
    tela(e, t, '5_parentese_aberto')

    # 3. lista do autocompletar com o detalhe do item selecionado
    reiniciar_linha(e)
    digitar(e, xy, 'own.rayCa')
    time.sleep(0.4)
    tela(e, t, '6_detalhe_lista')
    tecla(e, xy, 'TAB')
    assert linha(e) == '    own.rayCast', linha(e)

    # 4. desligado: nada de verificar (só confere que a opção existe e muda)
    py(e, "a = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == 'TEXT_EDITOR')\n"
          "a.spaces[0].use_live_diagnostics = False\nresultado = True")
    reiniciar_linha(e)
    time.sleep(1.2)
    tela(e, t, '7_desligado')
