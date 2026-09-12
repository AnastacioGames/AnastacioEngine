"""
Teste manual dos checkpoints (d) e Fase 2 / item 1 do plano de menu ImGui
(Range.imgui) - AnastacioEngine (versao KX_PythonComponent).

Uso: no objeto que vai exibir a janela de teste, adicione este componente pela
aba de Python Components do editor (nao precisa de sensor/controller, o
proprio sistema de componentes chama update() todo frame sozinho).

Roda sem SHOW_DEBUG_MODE/F1 ativo. Confirma:
 - a janela aparece ancorada conforme os args h_align/v_align (dropdowns
   "left"/"center"/"right" e "top"/"center"/"bottom" no painel do
   componente, via args = OrderedDict com C_Header agrupando os campos),
   calculada por menu_common.set_anchored_window() a partir de
   imgui.get_display_size()
 - o jogador pode redimensionar a janela arrastando a borda com o mouse
   (usa imgui.COND_FIRST_USE_EVER no tamanho, entao o resize manual nao
   e sobrescrito no frame seguinte -- so a posicao da ancora e reaplicada
   todo frame, porque isso nao e algo que se "arrasta")
 - checkbox alterna e o texto ao lado reflete o valor
 - os sliders (float e int) respondem ao arrastar
 - input_text aceita digitacao (confirma navegacao por teclado/Tab tambem)
 - combo e listbox abrem e trocam de item
 - radio_button alterna a selecao entre as 3 opcoes
 - color_edit3/4 abrem o seletor de cor e refletem o valor escolhido
 - o botao "Abrir popup" abre um popup modal com botao "Fechar popup"
 - o mouse fica visivel automaticamente enquanto a janela esta aberta
 - o botao "Fechar" (ou o X da janela) fecha e o mouse volta a ficar invisivel
"""

from collections import OrderedDict

import Range
import Range.imgui as imgui

from scripts import menu_common


class TestImguiWidgetsComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "BLENDER"),

        ("C_Header /Posicao da janela/RESTRICT_VIEW_OFF", True),
        ("h_align", {"left", "center", "right"}),
        ("v_align", {"top", "center", "bottom"}),
        ("width", 360),
        ("height", 520),
    ])

    def start(self, args):
        self.visual = menu_common.load_visual_config()
        window = menu_common.visual_window(self.visual, "test_widgets", args)
        self.h_align = window["h_align"]
        self.v_align = window["v_align"]
        self.width = window["width"]
        self.height = window["height"]

        self.checkbox_val = False
        self.slider_f = 0.5
        self.slider_i = 5
        self.text_val = "digite aqui"
        self.combo_idx = 0
        self.combo_items = ["Opcao A", "Opcao B", "Opcao C"]
        self.listbox_idx = 1
        self.radio_idx = 0
        self.color3 = (1.0, 0.5, 0.0)
        self.color4 = (0.2, 0.6, 1.0, 1.0)
        self.ui_open = True
        print("[TestImguiWidgets] iniciado (component)")

    def update(self):
        imgui.set_game_ui_open(self.ui_open)
        if not self.ui_open:
            return

        menu_common.set_anchored_window(
            imgui, self.h_align, self.v_align, self.width, self.height)
        is_open, want_close = imgui.begin("Teste Widgets", closable=True)
        if is_open:
            imgui.text("Testando checkpoint (d) + Fase 2 item 1")
            imgui.separator()

            changed, self.checkbox_val = imgui.checkbox("Minha checkbox", self.checkbox_val)
            imgui.same_line()
            imgui.text("<- valor: {}".format(self.checkbox_val))

            changed, self.slider_f = imgui.slider_float("Slider float", self.slider_f, 0.0, 1.0)
            changed, self.slider_i = imgui.slider_int("Slider int", self.slider_i, 0, 10)

            imgui.separator()
            changed, self.text_val = imgui.input_text("Input text", self.text_val)

            changed, self.combo_idx = imgui.combo("Combo", self.combo_idx, self.combo_items)
            changed, self.listbox_idx = imgui.listbox(
                "Listbox", self.listbox_idx, self.combo_items, height_items=3)

            imgui.separator()
            for i, label in enumerate(["Radio A", "Radio B", "Radio C"]):
                if imgui.radio_button(label, self.radio_idx == i):
                    self.radio_idx = i
                imgui.same_line()
            imgui.text("")

            changed, r, g, b = imgui.color_edit3("Cor 3", *self.color3)
            self.color3 = (r, g, b)
            changed, r, g, b, a = imgui.color_edit4("Cor 4", *self.color4)
            self.color4 = (r, g, b, a)

            imgui.separator()
            if imgui.button("Abrir popup"):
                imgui.open_popup("TestePopup")

            popup_open, popup_want_close = imgui.begin_popup_modal("TestePopup", closable=True)
            if popup_open:
                imgui.text("Isto e um popup modal.")
                if imgui.button("Fechar popup") or popup_want_close:
                    imgui.close_current_popup()
                imgui.end_popup()

            if imgui.button("Fechar"):
                want_close = True

            imgui.text("mouse capturado: {}".format(imgui.get_io_want_capture_mouse()))
            imgui.text("teclado capturado: {}".format(imgui.get_io_want_capture_keyboard()))
        imgui.end()

        if want_close:
            self.ui_open = False
            imgui.set_game_ui_open(False)
