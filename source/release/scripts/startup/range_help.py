"""Ajuda nos painéis: botão Help no cabeçalho de cima liga um "i" no cabeçalho dos painéis que têm explicação.

O "i" abre uma janela com o que é o painel e, quando há, um botão para fazer o tutorial dele.
As explicações ficam em scripts/ajuda/paineis.json: {"ID_DO_PAINEL": {"titulo": {...}, "texto": {...},
"tutorial": "pasta"}}, com textos em pt/en/es (o idioma é o mesmo escolhido no cartão dos tutoriais).
"""
import json
import os
import textwrap

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator

ARQUIVO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ajuda", "paineis.json")

_dados = {}
_originais = {}  # painel -> draw_header original (None quando não tinha)
_LARGURA = 420
_FAZER = {"pt": "Fazer o tutorial", "en": "Do the tutorial", "es": "Hacer el tutorial"}


def _ajuda():
    if "paineis" not in _dados:
        try:
            with open(ARQUIVO, encoding="utf-8") as f:
                _dados["paineis"] = json.load(f)
        except (OSError, ValueError):
            _dados["paineis"] = {}
    return _dados["paineis"]


def _tutoriais():
    import range_tutorials
    return range_tutorials


def _arquivo_ligado():
    return os.path.join(bpy.utils.user_resource('CONFIG', create=True), "range_help.txt")


def _ao_mudar(self, context):
    try:
        with open(_arquivo_ligado(), "w", encoding="utf-8") as f:
            f.write("1" if self.range_help_on else "0")
    except OSError:
        pass  # sem pasta de configuração: vale só nesta sessão
    if self.range_help_on:
        _instalar()
    _redesenhar(context.window_manager)


def _classe_painel(nome):
    pilha = list(bpy.types.Panel.__subclasses__())
    while pilha:
        c = pilha.pop()
        if c.__name__ == nome:
            return c
        pilha.extend(c.__subclasses__())
    return None


def _com_info(nome, original):
    def draw_header(self, context):
        if context.window_manager.range_help_on:
            self.layout.operator(RANGE_OT_help_show.bl_idname, text="", icon='INFO', emboss=False).panel = nome
        if original is not None:
            original(self, context)
    return draw_header


def _redesenhar(wm):
    for janela in wm.windows:
        for area in janela.screen.areas:
            area.tag_redraw()


def _instalar():
    """Põe o "i" nos painéis com ajuda (registra a classe de novo com um draw_header que o desenha).

    Só dá para fazer depois de todos os painéis registrados: roda quando a ajuda é ligada."""
    for nome in _ajuda():
        if nome in _originais:
            continue
        cls = _classe_painel(nome)
        if cls is None or not getattr(cls, "is_registered", False):
            continue
        original = cls.__dict__.get("draw_header")
        try:
            bpy.utils.unregister_class(cls)
            cls.draw_header = _com_info(nome, original)
            bpy.utils.register_class(cls)
        except (RuntimeError, ValueError):
            continue
        _originais[nome] = original


def _desinstalar():
    for nome, original in list(_originais.items()):
        cls = _classe_painel(nome)
        if cls is None:
            continue
        try:
            bpy.utils.unregister_class(cls)
            if original is None:
                del cls.draw_header
            else:
                cls.draw_header = original
            bpy.utils.register_class(cls)
        except (RuntimeError, ValueError, AttributeError):
            pass
    _originais.clear()


class RANGE_OT_help_show(Operator):
    """What is this panel (and its tutorial, when there is one)"""
    bl_idname = "wm.range_help_show"
    bl_label = "Help"

    panel = StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def invoke(self, context, event):
        if self.panel not in _ajuda():
            return {'CANCELLED'}
        return context.window_manager.invoke_popup(self, width=_LARGURA)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        t = _tutoriais()
        item = _ajuda()[self.panel]
        layout = self.layout
        layout.label(text=t._txt(item.get("titulo")), icon='INFO')
        col = layout.column(align=True)
        for linha in textwrap.wrap(t._txt(item.get("texto")), 62):
            col.label(text=linha)
        nome = item.get("tutorial")
        titulo = next((tit for pasta, tit, _, _ in t.tutoriais() if pasta == nome), None) if nome else None
        if titulo:
            layout.separator()
            linha = layout.row()
            linha.scale_y = 1.3
            linha.operator("wm.range_tutorial_start", text="%s: %s" % (_FAZER.get(t._idioma(), _FAZER["en"]), titulo),
                           icon='PLAY').name = nome


@persistent
def _ao_carregar(_):
    # Ligada da última vez: instala o "i" assim que tudo estiver registrado.
    wm = bpy.context.window_manager
    if wm and wm.range_help_on:
        _instalar()


def _ligada_antes():
    try:
        with open(_arquivo_ligado(), encoding="utf-8") as f:
            return f.read().strip() == "1"
    except OSError:
        return False


def _primeiro_tique(_):
    bpy.app.handlers.scene_update_post.remove(_primeiro_tique)
    wm = bpy.context.window_manager
    if wm and _ligada_antes() and not wm.range_help_on:
        wm.range_help_on = True  # _ao_mudar instala o "i"


def register():
    bpy.utils.register_class(RANGE_OT_help_show)
    bpy.types.WindowManager.range_help_on = BoolProperty(
        name="Help", description="Show an \"i\" on panels: click it to see what the panel does and its tutorial",
        update=_ao_mudar)
    bpy.app.handlers.load_post.append(_ao_carregar)
    bpy.app.handlers.scene_update_post.append(_primeiro_tique)


def unregister():
    _desinstalar()
    bpy.app.handlers.load_post.remove(_ao_carregar)
    if _primeiro_tique in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.remove(_primeiro_tique)
    del bpy.types.WindowManager.range_help_on
    bpy.utils.unregister_class(RANGE_OT_help_show)
