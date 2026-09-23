# Tradução em tempo de exibição para os módulos puros (testáveis sem o motor).
# Dentro do editor usa o catálogo registrado em translations.py; fora dele devolve o texto original.

try:
    from bpy.app.translations import pgettext_iface as _
except ImportError:
    def _(msgid):
        return msgid


class Msg(str):
    """Mensagem de regra: o valor é o texto em inglês (JSON, testes); guarda molde e argumentos
    para `tr` traduzir na exibição, já que o catálogo só casa o molde, não o texto formatado."""

    def __new__(cls, template, *args):
        self = str.__new__(cls, template % args if args else template)
        self.template = template
        self.args = args
        return self


def tr(text):
    """Texto de exibição de uma mensagem; argumentos que também são Msg são traduzidos."""
    if not isinstance(text, Msg):
        # Texto fixo (dica de correção) casa direto no catálogo; o resto volta como veio.
        return _(text) if isinstance(text, str) and text else text
    template = _(text.template)
    if not text.args:
        return template
    try:
        return template % tuple(tr(a) if isinstance(a, Msg) else a for a in text.args)
    except (TypeError, ValueError):
        return str(text)
