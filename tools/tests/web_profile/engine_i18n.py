"""Integracao da selecao de idioma (English/Portugues) do editor (precisa do motor com WITH_INTERNATIONAL):

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/engine_i18n.py

Sai com codigo != 0 se alguma verificacao falhar. O desenho na janela (fonte, acentos, menu de idioma)
nao e coberto aqui: so a janela real mostra isso.
"""

import sys

import bpy
from bpy.app.translations import pgettext_iface, pgettext_tip

failures = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


check(bpy.app.build_options.international, "editor compilado com i18n")
locales = bpy.app.translations.locales
check("pt_BR" in locales, "pt_BR disponivel (locale/languages + blender.mo instalados): %s" % (locales,))

system = bpy.context.user_preferences.system
system.use_international_fonts = True
system.use_translate_interface = True
system.use_translate_tooltips = True

# Ingles e o idioma-fonte: sem traducao o texto volta igual.
system.language = 'en_US'
check(pgettext_iface("Validate Web") == "Validate Web", "en_US mantem o ingles")

system.language = 'pt_BR'
check(bpy.app.translations.locale == "pt_BR", "idioma pt_BR ativo")
check(pgettext_iface("Object") == "Objeto", "catalogo do Blender traduz (Object -> Objeto)")
check(pgettext_iface("Validate Web") == "Validar Web", "dicionario range_web traduz o rotulo")
check(pgettext_iface("Serving at %s") % "x" == "Servindo em x", "formato com %s traduz antes de formatar")
check(pgettext_tip("Stops the local server of the Web package") == "Para o servidor local do pacote Web",
      "dica de ferramenta traduzida")
check(pgettext_iface("Preflight after export") == "Pré-voo após exportar", "acentos preservados na string")
check(pgettext_iface("Export from a development tree with tools/web/package-web.py.").startswith("Exporte a partir"),
      "mensagem do export traduzida")

# Modulos puros usam o mesmo caminho de traducao.
from range_web import results
check(results.Report().summary() == "Nenhuma incompatibilidade detectada", "results.summary traduz em pt_BR")

# Mensagens das regras: o valor fica em ingles (JSON) e tr() traduz molde e argumentos na exibicao.
from range_web import preflight, rules_files
from range_web.i18n import tr
shader = preflight.check_preflight({"schema": preflight.PREFLIGHT_SCHEMA, "schema_version": 2,
                                    "shader_errors": [{"stage": "vertex"}]})[0]
check(shader.message == "Shader did not compile (stage vertex).", "mensagem da regra guardada em ingles")
check(tr(shader.message) == "Shader não compilou (estágio vertex).", "tr traduz mensagem de regra em pt_BR")
dest = rules_files.check_destinations([("", "a.png")])[0]
check(tr(dest.message) == "Destino inválido '': caminho vazio.", "tr traduz argumento que tambem e mensagem")
check(tr(dest.fix) == "Normalizar o destino dentro da raiz do pacote.", "tr traduz a dica de correcao")

system.language = 'en_US'
check(results.Report().summary() == "No incompatibility detected", "results.summary volta ao ingles em en_US")

# Espanhol e russo (cirilico): catalogo do Blender + dicionario range_web, e as duas tabelas cobrem as mesmas chaves.
from range_web import translations
check(set(translations._ES) == set(translations._PT_BR) == set(translations._RU), "es/ru cobrem as mesmas chaves do pt_BR")
for lang, obj, web in (('es', "Objeto", "Validar Web"), ('ru_RU', "Объект", "Проверить Web")):
    system.language = lang
    check(bpy.app.translations.locale == lang, "idioma %s ativo" % lang)
    check(pgettext_iface("Object") == obj, "%s: catalogo do Blender traduz Object" % lang)
    check(pgettext_iface("Validate Web") == web, "%s: dicionario range_web traduz o rotulo" % lang)
    # Texto de UI da Range/UPBGE fora do catalogo do Blender (translations_ui.py), rotulo e dica.
    check(pgettext_iface("Vortex Height") != "Vortex Height", "%s: rotulo da Range (translations_ui) traduzido" % lang)
    check(pgettext_tip("Distance to begin suspend physics of this object") != "Distance to begin suspend physics of this object",
          "%s: dica da Range (translations_ui) traduzida" % lang)

# Sem o interruptor de traducao de interface, nada muda mesmo em pt_BR.
system.language = 'pt_BR'
system.use_translate_interface = False
check(pgettext_iface("Validate Web") == "Validate Web", "sem use_translate_interface o texto fica em ingles")

sys.exit(1 if failures else 0)
