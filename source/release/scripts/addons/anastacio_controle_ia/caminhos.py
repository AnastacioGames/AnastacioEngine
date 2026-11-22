"""Caminhos de propriedade seguros (bpy.a.b[0]["x"]), compartilhados pelo MCP e pelo servidor do editor.

Só atributos e índices literais: sem chamadas, sem operadores, sem "__". É a única porta de `ler`/`definir`.
"""
import ast
import re

CAMINHO = re.compile(r'^bpy(\.[A-Za-z_][A-Za-z0-9_]*|\[(\d+|"[^"\\]*"|\'[^\'\\]*\')\])*$')
ULTIMO = re.compile(r'^(.*?)(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+|"[^"\\]*"|\'[^\'\\]*\')\])$')


def caminho_valido(caminho):
    return isinstance(caminho, str) and bool(CAMINHO.match(caminho)) and "__" not in caminho


def exigir(caminho):
    if not caminho_valido(caminho):
        raise ValueError('caminho não permitido: use bpy.a.b[0]["x"], sem chamadas nem operadores')


def ler(caminho, bpy):
    exigir(caminho)
    return eval(caminho, {"__builtins__": {}}, {"bpy": bpy})


def definir(caminho, valor, bpy):
    """Atribui no último atributo (`.nome`) ou no último índice (`[0]`, `["x"]`) do caminho."""
    exigir(caminho)
    m = ULTIMO.match(caminho)
    if not m or not m.group(1):
        raise ValueError("não dá para definir o próprio bpy")
    dono = ler(m.group(1), bpy)
    if m.group(2):
        setattr(dono, m.group(2), valor)
    else:
        dono[ast.literal_eval(m.group(3))] = valor
    return ler(caminho, bpy)
