"""Scan estatico de traducao dos textos de interface escritos em C, fora do RNA.

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/i18n_scan_c.py -- pt_BR [saida.txt]

Complementa i18n_audit.py (RNA) e i18n_scan_labels.py (layouts Python). Le os .c/.cc/.cpp de source/source e
procura IFACE_("..."), TIP_("..."), N_("..."), CTX_IFACE_(ctx, "...") e CTX_N_(ctx, "...") com literal (literais
adjacentes sao juntados, como no C). Um texto e "sem traducao" se pgettext devolve o mesmo texto no idioma
escolhido. makesrna fica de fora: o RNA ja e coberto por i18n_audit.py.
"""

import ast
import os
import re
import sys

import bpy
from bpy.app.translations import pgettext_iface, pgettext_tip

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
SOURCES = os.path.join(ROOT, "source", "source")
SKIP_DIRS = {"makesrna"}
EXTS = (".c", ".cc", ".cpp")

STRING = r'"(?:[^"\\\n]|\\.)*"'
STRINGS = r'(%s(?:\s*%s)*)' % (STRING, STRING)
# Contexto: macro BLT_I18NCONTEXT_* ou literal.
CTXT = r'(\w+|%s)' % STRING
CALL = re.compile(r'\b(?:(IFACE|TIP|N)_\(\s*%s\s*\)|CTX_(IFACE|N)_\(\s*%s\s*,\s*%s\s*\))' % (STRINGS, CTXT, STRINGS))
# Valores dos BLT_I18NCONTEXT_* (blentranslation/BLT_translation.h); o resto cai no padrao.
CONTEXTS = {}


def load_contexts():
    header = os.path.join(SOURCES, "blender", "blentranslation", "BLT_translation.h")
    with open(header, encoding="utf-8", errors="replace") as f:
        for name, value in re.findall(r'#define\s+(BLT_I18NCONTEXT_\w+)\s+("[^"]*"|NULL)', f.read()):
            CONTEXTS[name] = None if value == "NULL" else value[1:-1]


def c_string(chunk):
    # Junta literais adjacentes e resolve escapes do C (\n, \", \t) com a sintaxe de string do Python.
    parts = re.findall(STRING, chunk)
    return "".join(ast.literal_eval(p) for p in parts)


def scan_file(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    for m in CALL.finditer(src):
        if m.group(1):
            kind, text, ctxt = m.group(1), m.group(2), None
        else:
            kind, ctxt, text = m.group(3), m.group(4), m.group(5)
            ctxt = c_string(ctxt) if ctxt.startswith('"') else CONTEXTS.get(ctxt)
        try:
            text = c_string(text)
        except (SyntaxError, ValueError):
            continue
        if not any(c.isalpha() for c in text):
            continue
        yield src.count("\n", 0, m.start()) + 1, kind, text, ctxt or "*"


def translated(kind, text, ctxt):
    # N_ so marca o texto; ele e traduzido depois como rotulo ou como dica.
    if kind == "TIP":
        return pgettext_tip(text, ctxt) != text
    if kind == "IFACE":
        return pgettext_iface(text, ctxt) != text
    return pgettext_iface(text, ctxt) != text or pgettext_tip(text, ctxt) != text


load_contexts()
found = {}  # (texto, contexto) -> (tipo, primeira origem)
for base, dirs, files in os.walk(SOURCES):
    dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
    for name in sorted(files):
        if name.endswith(EXTS):
            path = os.path.join(base, name)
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            for line, kind, text, ctxt in scan_file(path):
                found.setdefault((text, ctxt), (kind, "%s:%d" % (rel, line)))

untranslated = sorted((origin, kind, ctxt, text) for (text, ctxt), (kind, origin) in found.items()
                      if not translated(kind, text, ctxt))

lines = ["idioma=%s textos=%d sem_traducao=%d" % (lang, len(found), len(untranslated))]
lines += ["%s	%s	%s	%s" % item for item in untranslated]
report = "\n".join(lines)
if out:
    with open(out, "w", encoding="utf8") as f:
        f.write(report + "\n")
print(lines[0])
