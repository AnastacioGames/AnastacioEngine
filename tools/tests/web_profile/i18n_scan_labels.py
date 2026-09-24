"""Scan estatico de traducao: textos escritos direto em layout.label(text=...) e afins nos scripts Python.

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/i18n_scan_labels.py -- pt_BR [saida.txt]

Complementa i18n_audit.py, que so ve o RNA. Le com ast os .py de release/scripts/startup e procura chamadas de
layout (label, operator, prop, menu, ...) com text="..." literal ou label("...") posicional. Um texto e "sem
traducao" se pgettext_iface devolve o mesmo texto no idioma escolhido (com text_ctxt literal, quando houver).
Textos montados em tempo de execucao (formatacao, variaveis) nao sao vistos; nomes proprios e codigos (ex.: "X",
"OpenGL") aparecem como sem traducao e podem ser ignorados.
"""

import ast
import os
import sys

import bpy
from bpy.app.translations import pgettext_iface

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
lang = argv[0] if argv else "pt_BR"
out = argv[1] if len(argv) > 1 else None

system = bpy.context.user_preferences.system
system.use_international_fonts = True
system.use_translate_interface = True
system.use_translate_tooltips = True
system.language = lang
assert bpy.app.translations.locale == lang, bpy.app.translations.locale

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(ROOT, "source", "release", "scripts", "startup")
# Metodos de UILayout que desenham o texto passado em text= (traduzido pelo proprio layout).
METHODS = {"label", "operator", "prop", "props_enum", "prop_enum", "prop_menu_enum", "menu", "operator_menu_enum",
           "operator_enum", "template_ID", "prop_search", "column_flow", "popover"}
DEFAULT_CTXT = "*"


def literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def scan_file(path):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in METHODS):
            continue
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        # translate=False: o autor pediu o texto cru.
        if "translate" in kw and isinstance(kw["translate"], ast.Constant) and kw["translate"].value is False:
            continue
        text = literal(kw["text"]) if "text" in kw else None
        if text is None and node.func.attr == "label" and node.args:
            text = literal(node.args[0])
        if not text or not any(c.isalpha() for c in text):
            continue
        ctxt = literal(kw["text_ctxt"]) if "text_ctxt" in kw else None
        yield node.lineno, text, ctxt or DEFAULT_CTXT


found = {}  # (texto, contexto) -> primeira origem
for base, _dirs, files in os.walk(SCRIPTS):
    for name in sorted(files):
        if name.endswith(".py"):
            path = os.path.join(base, name)
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            for line, text, ctxt in scan_file(path):
                found.setdefault((text, ctxt), "%s:%d" % (rel, line))

untranslated = sorted((origin, text) for (text, ctxt), origin in found.items()
                      if pgettext_iface(text, ctxt) == text)

lines = ["idioma=%s textos=%d sem_traducao=%d" % (lang, len(found), len(untranslated))]
lines += ["%s\t%s" % item for item in untranslated]
report = "\n".join(lines)
if out:
    with open(out, "w", encoding="utf8") as f:
        f.write(report + "\n")
print(lines[0])
