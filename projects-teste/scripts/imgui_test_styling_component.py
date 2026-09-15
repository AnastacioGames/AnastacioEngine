"""
Teste manual da Fase 2 / item 2 do plano de menu ImGui (Range.imgui) -
AnastacioEngine (versao KX_PythonComponent).

Uso: adicione este componente a um objeto da cena pela aba de Python
Components do editor (nao precisa de sensor/controller).

Confirma:
 - push_style_color/pop_style_color: o botao "Botao Temado" aparece verde
   em vez da cor padrao (tema global do KX_Imgui, definido em
   SetupDebugModeStyle) e volta ao normal depois de fechado o par push/pop.
 - load_font/push_font/pop_font: a linha "Texto com fonte customizada" usa
   Roboto Mono (carregada de disco via load_font) em vez da fonte padrao.
 - draw_rect_filled + get_display_size: um fade-in de preto para
   transparente acontece nos primeiros ~60 frames depois que o componente
   e adicionado (simula a transicao entre telas de menu).
 - Imagem de fundo: NAO precisa de codigo novo de engine -- qualquer
   material ja carregado na cena expoe seu bindcode em
   `material.textures[0].bindCode` (Python), que pode ir direto para
   `imgui.image(bindcode, w, h)`. Usa o objeto "menu_background" (material
   com menu_background.png) -- funciona tanto adicionado direto na cena
   quanto como instancia do grupo Group_btn_menu.
 - Posicionamento: args h_align/v_align (dropdowns) + width/height, agrupados
   sob "Posicao da janela" no painel do componente, ancoram a janela via
   menu_common.set_anchored_window() em vez de coordenadas fixas. O tamanho
   so e forcado uma vez (COND_FIRST_USE_EVER), entao arrastar a borda com o
   mouse redimensiona de verdade.
 - button_color: arg do tipo Color (mathutils), agrupado sob "Tema do
   botao", substitui os valores fixos de push_style_color -- mude a cor no
   painel do componente e o botao "Botao Temado" reflete na hora.
"""

from collections import OrderedDict

import Range
import Range.imgui as imgui
from mathutils import Color

from scripts import menu_common


class TestImguiStylingComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "BLENDER"),

        ("C_Header /Posicao da janela/RESTRICT_VIEW_OFF", True),
        ("h_align", {"left", "center", "right"}),
        ("v_align", {"top", "center", "bottom"}),
        ("width", 360),
        ("height", 220),

        ("C_Header /Tema do botao/COLOR", True),
        ("button_color", Color((0.1, 0.6, 0.1))),
    ])

    def start(self, args):
        self.visual = menu_common.load_visual_config()
        window = menu_common.visual_window(self.visual, "test_styling", args)
        self.h_align = window["h_align"]
        self.v_align = window["v_align"]
        self.width = window["width"]
        self.height = window["height"]
        self.button_color = tuple(self.visual["style"].get("button_color", args["button_color"]))

        self.ui_open = True
        self.fade_timer = 0
        self.fade_duration = max(1, int(self.visual["transitions"].get("styling_fade_frames", 60)))

        font_path = Range.logic.expandPath(self.visual["style"].get("font_path", "//roboto_mono_medium.ttf"))
        try:
            self.custom_font = imgui.load_font(font_path, float(self.visual["style"].get("font_size", 20.0)))
            print("[TestImguiStyling] fonte customizada carregada, id =", self.custom_font)
        except IOError as e:
            self.custom_font = None
            print("[TestImguiStyling] falha ao carregar fonte customizada:", e)

        self.bg_bindcode = self._find_background_bindcode()
        if self.bg_bindcode is None:
            print("[TestImguiStyling] objeto 'menu_background' com textura nao encontrado na cena")

        print("[TestImguiStyling] iniciado (component)")

    def _find_background_bindcode(self):
        scene = self.object.scene
        obj = scene.objects.get("menu_background")
        if obj is None:
            # instancia de grupo pode renomear (menu_background.001 etc.)
            for candidate in scene.objects:
                if candidate.name.startswith("menu_background"):
                    obj = candidate
                    break
        if obj is None or not obj.meshes:
            return None
        try:
            return obj.meshes[0].materials[0].textures[0].bindCode
        except (IndexError, AttributeError):
            return None

    def update(self):
        imgui.set_game_ui_open(self.ui_open)
        if not self.ui_open:
            return

        menu_common.set_anchored_window(
            imgui, self.h_align, self.v_align, self.width, self.height)
        is_open, want_close = imgui.begin("Teste Styling", closable=True)
        if is_open:
            imgui.text("Testando Fase 2 item 2 (styling)")
            imgui.separator()

            r, g, b = self.button_color
            imgui.push_style_color(imgui.COL_BUTTON, r, g, b, 1.0)
            imgui.push_style_color(imgui.COL_BUTTON_HOVERED, min(r * 1.3, 1.0), min(g * 1.3, 1.0), min(b * 1.3, 1.0), 1.0)
            imgui.push_style_color(imgui.COL_BUTTON_ACTIVE, r * 0.7, g * 0.7, b * 0.7, 1.0)
            imgui.button("Botao Temado (cor via arg 'button_color')")
            imgui.pop_style_color(3)

            imgui.text("<- esse usa a cor do arg, este aqui volta ao normal")

            imgui.separator()
            if self.custom_font is not None:
                imgui.push_font(self.custom_font)
                imgui.text("Texto com fonte customizada (Roboto Mono)")
                imgui.pop_font()
            else:
                imgui.text("(fonte customizada nao carregada, veja o console)")

            imgui.separator()
            imgui.text("Imagem (menu_background.png via objeto 'menu_background'):")
            if self.bg_bindcode is not None:
                imgui.image(self.bg_bindcode, 128, 128)
            else:
                imgui.text("(objeto/textura nao encontrado, veja o console)")

            if imgui.button("Fechar"):
                want_close = True
        imgui.end()

        if want_close:
            self.ui_open = False
            imgui.set_game_ui_open(False)

        # Fade-in de preto para transparente, desenhado por cima de tudo.
        if self.fade_timer < self.fade_duration:
            alpha = 1.0 - (self.fade_timer / float(self.fade_duration))
            w, h = imgui.get_display_size()
            imgui.draw_rect_filled(0, 0, w, h, 0.0, 0.0, 0.0, alpha)
            self.fade_timer += 1
