"""Auditoria de traducao: lista textos de UI que nao mudam ao trocar de idioma.

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/i18n_audit.py -- pt_BR [saida.txt]

Percorre rotulos de Panel/Menu/Header/Operator e nome/descricao/itens de enum de todas as propriedades RNA.
Um texto e "sem traducao" se pgettext devolve o mesmo texto no idioma escolhido. Nao cobre textos escritos
direto em layout.label(text=...) em Python nem em C fora do RNA (use o scan estatico para isso).
"""

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

found = {}  # texto -> (tipo, origem)


def add(text, kind, origin):
    if text and isinstance(text, str) and any(c.isalpha() for c in text):
        found.setdefault((kind, text), origin)


for name in dir(bpy.types):
    cls = getattr(bpy.types, name)
    try:
        rna = cls.bl_rna
    except AttributeError:
        continue
    label = getattr(cls, "bl_label", None)
    if isinstance(label, str):
        add(label, "iface", name)
    for prop in rna.properties:
        if prop.identifier == "rna_type":
            continue
        add(prop.name, "iface", "%s.%s" % (name, prop.identifier))
        add(prop.description, "tip", "%s.%s" % (name, prop.identifier))
        if prop.type == 'ENUM':
            for item in prop.enum_items:
                add(item.name, "iface", "%s.%s[%s]" % (name, prop.identifier, item.identifier))
                add(item.description, "tip", "%s.%s[%s]" % (name, prop.identifier, item.identifier))

untranslated = []
for (kind, text), origin in found.items():
    fn = pgettext_iface if kind == "iface" else pgettext_tip
    if fn(text) == text:
        untranslated.append((origin, kind, text))
untranslated.sort()

lines = ["idioma=%s textos=%d sem_traducao=%d" % (lang, len(found), len(untranslated))]
lines += ["%s\t%s\t%s" % item for item in untranslated]
report = "\n".join(lines)
if out:
    with open(out, "w", encoding="utf8") as f:
        f.write(report + "\n")
print(lines[0])
