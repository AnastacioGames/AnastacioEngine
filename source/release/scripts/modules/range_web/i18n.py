# Tradução em tempo de exibição para os módulos puros (testáveis sem o motor).
# Dentro do editor usa o catálogo registrado em translations.py; fora dele devolve o texto original.

try:
    from bpy.app.translations import pgettext_iface as _
except ImportError:
    def _(msgid):
        return msgid
