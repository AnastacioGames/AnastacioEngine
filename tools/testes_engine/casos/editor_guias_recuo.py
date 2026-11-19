"""Guias de recuo e espaços/tabs visíveis no Text Editor: liga/desliga pelas opções e guarda telas
(com e sem) para conferir a olho; a tela muda quando as opções mudam."""
import time

import importlib.util
from pathlib import Path

from rodar import py

_spec = importlib.util.spec_from_file_location('editor_autocompletar', Path(__file__).with_name('editor_autocompletar.py'))
_ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ac)
PREPARAR = _ac.PREPARAR

SCRIPT = ('import bge\n\nclass Jogador:\n    def __init__(self, own):\n        self.own = own\n\n'
          '        if own:\n            for i in range(3):\n                print(i)\n\n'
          '\tx = 1  # tab misturado\n    def fim(self):\n        pass\n')


def tela(e, t, nome):
    caminho = t.pasta / (nome + '.png')
    e.pedir('tela', arquivo=str(caminho))
    t.nota('%s: %s' % (nome, caminho))
    return caminho.read_bytes()


def opcoes(e, guias, espacos):
    py(e, "a = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == 'TEXT_EDITOR')\n"
          "s = a.spaces[0]\ns.use_indent_guides = %r\ns.show_whitespace = %r\n"
          "s.use_live_diagnostics = False\ns.top = 0\na.tag_redraw()\nresultado = True" % (guias, espacos))
    time.sleep(0.4)


def testar(t):
    e = t.editor()
    py(e, PREPARAR % SCRIPT)
    r = py(e, "a = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == 'TEXT_EDITOR')\n"
              "resultado = [a.spaces[0].use_indent_guides, a.spaces[0].show_whitespace]")
    assert r == [True, False], r  # guias ligadas e espaços escondidos num editor novo
    opcoes(e, False, False)
    nada = tela(e, t, '1_desligado')
    opcoes(e, True, False)
    guias = tela(e, t, '2_guias')
    opcoes(e, True, True)
    tudo = tela(e, t, '3_guias_e_espacos')
    assert nada != guias and guias != tudo, 'a tela nao mudou com as opcoes'
