"""
Main Menu de exemplo (checkpoint (e) + Fase 2 / item 4 do plano de menu
ImGui) - AnastacioEngine.

Uso: no objeto que fica na cena "MainMenu" (ex.: a camera dela), adicione este
componente pela aba de Python Components do editor.

Campos editaveis no painel do componente (args):
    game_scene_name (string) nome da cena de jogo a carregar ao clicar em
                    "Jogar". Padrao: "GameScene"

Ao clicar em "Jogar", em vez de trocar de cena na hora, entra num pequeno
fade-out (imgui.draw_rect_filled, mesma primitiva do teste de styling) com um
texto "Carregando..." -- so troca de cena (scene.replace()) quando o fade
termina. "Sair" agora pede confirmacao num popup modal antes de encerrar o
jogo. Dentro de Options, Esc fecha o painel (a nao ser que um remapeamento de
tecla esteja em andamento, caso em que Esc so cancela o remapeamento --
menu_common.draw_options_panel ja trata isso).
"""

from collections import OrderedDict

import Range
import Range.imgui as imgui

from scripts import menu_common


class MainMenuComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("game_scene_name", "GameScene"),

        ("C_Header /Posicao da janela/RESTRICT_VIEW_OFF", True),
        ("h_align", {"left", "center", "right"}),
        ("v_align", {"top", "center", "bottom"}),
        ("width", 320),
        ("height", 140),
    ])

    def start(self, args):
        self.game_scene_name = args["game_scene_name"]
        self.visual = menu_common.load_visual_config()
        window = menu_common.visual_window(self.visual, "main_menu", args)
        self.h_align = window["h_align"]
        self.v_align = window["v_align"]
        self.width = window["width"]
        self.height = window["height"]
        self.options_height = window.get("options_height", 320)
        self.options_width = max(720, window.get("options_width", self.width))
        self.visual_assets = {
            "gamepad_texture": menu_common.find_texture_bindcode(
                self.object.scene, "joystick_controller")
        }
        if self.visual_assets["gamepad_texture"] is None:
            print("[MainMenu] objeto 'joystick_controller' com textura nao encontrado na cena")
        self.fade_duration = max(1, int(self.visual["transitions"].get("main_menu_fade_frames", 30)))
        self.show_options = False
        self.options = menu_common.load_options()
        self.listening = {"action": None}
        self.transitioning = False
        self.fade_timer = 0

    def update(self):
        if self.transitioning:
            self._update_transition()
            return

        imgui.set_game_ui_open(True)

        menu_common.set_anchored_window(
            imgui, self.h_align, self.v_align,
            self.options_width if self.show_options else self.width,
            self.height if not self.show_options else self.options_height,
            resizable=not self.show_options)
        is_open, _ = imgui.begin("Main Menu")
        if is_open:
            imgui.text("AnastacioEngine")
            imgui.separator()

            if not self.show_options:
                if imgui.button(menu_common.t(self.options, "play"), width=240):
                    self.transitioning = True
                    self.fade_timer = 0

                if imgui.button(menu_common.t(self.options, "options"), width=240):
                    self.show_options = True

                if imgui.button(menu_common.t(self.options, "quit"), width=240):
                    imgui.open_popup("ConfirmQuit")

                popup_open, popup_want_close = imgui.begin_popup_modal(
                    "ConfirmQuit", closable=True)
                if popup_open:
                    imgui.text(menu_common.t(self.options, "confirm_quit"))
                    imgui.separator()
                    if imgui.button(menu_common.t(self.options, "yes"), width=100):
                        Range.logic.endGame()
                    imgui.same_line()
                    if imgui.button(menu_common.t(self.options, "no"), width=100) or popup_want_close:
                        imgui.close_current_popup()
                    imgui.end_popup()
            else:
                was_listening = self.listening["action"] is not None
                _, self.options, self.listening = menu_common.draw_options_panel(
                    imgui, self.options, self.listening, self.visual_assets)
                imgui.separator()
                if imgui.button(menu_common.t(self.options, "back"), width=240):
                    self.show_options = False
                elif not was_listening and menu_common.esc_just_pressed():
                    self.show_options = False
        imgui.end()

    def _update_transition(self):
        imgui.set_game_ui_open(False)

        w, h = imgui.get_display_size()
        alpha = min(1.0, self.fade_timer / float(self.fade_duration))
        if alpha > 0.5:
            imgui.set_next_window_pos(w * 0.5 - 60, h * 0.5 - 12)
            is_open, _ = imgui.begin(
                "Loading", closable=False)
            if is_open:
                imgui.text(menu_common.t(self.options, "loading"))
            imgui.end()
        imgui.draw_rect_filled(0, 0, w, h, 0.0, 0.0, 0.0, alpha)

        self.fade_timer += 1
        if self.fade_timer >= self.fade_duration:
            scene = Range.logic.getCurrentScene()
            scene.replace(self.game_scene_name)
