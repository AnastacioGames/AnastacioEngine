#!/usr/bin/env python3
"""Verifica nomes de icone literais nos scripts de UI.

Le source/source/blender/editors/include/UI_icons.h (enum de icones do 2.79),
varre os .py de source/release/scripts procurando icon='X' / icon="X"
(inclusive ternarios: icon='A' if c else 'B') e lista os nomes invalidos
com arquivo:linha e a sugestao mais proxima (difflib).

Uso: python tools/check_ui_icons.py [pasta ...]
Saida com codigo 1 se houver icone invalido.
"""
import difflib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS_H = os.path.join(ROOT, "source", "source", "blender", "editors", "include", "UI_icons.h")
DEFAULT_DIRS = [os.path.join(ROOT, "source", "release", "scripts")]

# DEF_ICON_BLANK nao entra no enum RNA (rna_ui_api.c).
RE_DEF = re.compile(r"^\s*DEF_(ICON(?:_[A-Z_]+)?|VICO)\(\s*([A-Z0-9_]+)\s*\)", re.M)
RE_ICON_ARG = re.compile(r"\bicon\s*=\s*")
RE_STR = re.compile(r"""(['"])([A-Za-z0-9_]*)\1""")


def load_icons():
    with open(ICONS_H, encoding="utf-8", errors="replace") as f:
        text = f.read()
    names = set()
    for kind, name in RE_DEF.findall(text):
        if kind == "ICON_BLANK":
            continue
        names.add(name)
    return names


def arg_expr(line, start):
    """Trecho do argumento a partir de start ate , ou ) de nivel 0."""
    depth = 0
    quote = None
    i = start
    while i < len(line):
        c = line[i]
        if quote:
            if c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            break
        elif c == "#":
            break
        i += 1
    return line[start:i]


def scan(paths, icons):
    bad = []
    for base in paths:
        for dirpath, _dirs, files in os.walk(base):
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        for m in RE_ICON_ARG.finditer(line):
                            expr = arg_expr(line, m.end())
                            # So literais diretos (ou ternarios de literais).
                            if not expr.lstrip().startswith(("'", '"')):
                                continue
                            # Nome montado em runtime ("OUTLINER_DATA_" + tipo, "%s" % x): ignora.
                            if re.search(r"[+%]|\.format\(", expr):
                                continue
                            # Strings dentro de subscritos (info["chave"]) nao sao icones.
                            expr = re.sub(r"\[[^\]]*\]", "", expr)
                            for _q, name in RE_STR.findall(expr):
                                if name and name not in icons:
                                    bad.append((path, lineno, name))
    return bad


def main():
    icons = load_icons()
    paths = sys.argv[1:] or DEFAULT_DIRS
    bad = scan(paths, icons)
    for path, lineno, name in bad:
        sug = difflib.get_close_matches(name, icons, n=3, cutoff=0.5)
        rel = os.path.relpath(path, ROOT)
        print("%s:%d: icone invalido '%s'%s" % (
            rel, lineno, name, (" -> sugestao: " + ", ".join(sug)) if sug else ""))
    print("%d icones validos no enum; %d uso(s) invalido(s)." % (len(icons), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
