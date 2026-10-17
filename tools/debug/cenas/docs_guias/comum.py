# Utilidades dos geradores de cenas que validam os exemplos dos guias do site (D:\AnastacioDocs).
# Extrai os blocos ```python de um .md sem alterar o texto.
import re

DOCS_GUIAS = r"D:\AnastacioDocs\site\src\content\docs\guias"

# Teclado falso: substitui Range.logic.keyboard no jogo para simular teclas.
# Fica num texto para ser gravado como modulo ao lado da cena.
TECLADO_FALSO = '''import Range
from Range import events


class _Estado(object):
    def __init__(self, ativo):
        self.active = ativo
        self.activated = ativo
        self.released = False
        self.inactive = not ativo
        self.values = [1 if ativo else 0]


class _Inputs(dict):
    def __init__(self, teclado):
        dict.__init__(self)
        self._t = teclado

    def __getitem__(self, chave):
        return _Estado(chave in self._t.apertadas)


class TecladoFalso(object):
    def __init__(self):
        self.apertadas = set()
        self.inputs = _Inputs(self)
        self.activeInputs = {}


FALSO = TecladoFalso()
ORIGINAL = Range.logic.keyboard


def instalar():
    Range.logic.keyboard = FALSO
    return Range.logic.keyboard is FALSO


def apertar(*teclas):
    FALSO.apertadas = set(teclas)
'''


def blocos_python(caminho_md):
    with open(caminho_md, encoding="utf-8") as f:
        texto = f.read()
    return re.findall(r"```python\n(.*?)```", texto, re.S)
