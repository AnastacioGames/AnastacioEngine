"""
Pause Menu (checkpoint (f) + Fase 2 / item 4 do plano de menu ImGui) -
AnastacioEngine.

Uso: adicione este componente a um objeto da cena "PauseMenu" (a cena
carregada como overlay por imgui_pause_menu_trigger_component.py). Essa cena roda
normalmente mesmo com a cena de jogo suspensa, pois overlay scenes sao
independentes do ciclo de vida da cena que as empilhou -- por isso o
controller desta overlay nunca precisa checar/gerenciar o escopo do
Suspend() da cena de jogo.

Campos editaveis no painel do componente (args):
    game_scene_name (string) nome da cena de jogo a retomar/redirecionar.
                    Padrao: "GameScene"
    main_menu_scene_name (string) nome da cena de Main Menu, usada pelo
                    botao "Main Menu". Padrao: "MainMenu"

Esc despausa quando o painel principal esta visivel (mesmo efeito de
"Continuar"); quando Options esta aberto, Esc fecha o painel primeiro (a nao
ser que um remapeamento de tecla esteja em andamento, caso em que Esc so
cancela o remapeamento -- menu_common.draw_options_panel ja trata isso).
"""

from collections import OrderedDict

import Range
import Range.imgui as imgui

from scripts import menu_common


class PauseMenuOverlayComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("game_scene_name", "GameScene"),
        ("main_menu_scene_name", "MainMenu"),

        ("C_Header /Posicao da janela/RESTRICT_VIEW_OFF", True),
        ("h_align", {"left", "center", "right"}),
        ("v_align", {"top", "center", "bottom"}),
        ("width", 320),
        ("height", 150),
    ])

    def start(self, args):
        self.game_scene_name = args["game_scene_name"]
        self.main_menu_scene_name = args["main_menu_scene_name"]
        self.visual = menu_common.load_visual_config()
        window = menu_common.visual_window(self.visual, "pause_menu", args)
        self.h_align = window["h_align"]
        self.v_align = window["v_align"]
        self.width = window["width"]
        self.height = window["height"]
        self.options_height = window.get("options_height", 320)
        # Mantem todas as abas de opcoes visiveis tambem no menu de pausa.
        self.options_width = max(720, window.get("options_width", self.width))
        self.visual_assets = {
            "gamepad_texture": menu_common.find_texture_bindcode(
                self.object.scene, "joystick_controller")
        }
        if self.visual_assets["gamepad_texture"] is None:
            print("[PauseMenu] objeto 'joystick_controller' com textura nao encontrado na cena")
        self.show_options = False
        self.options = menu_common.load_options()
        self.listening = {"action": None}

    def _get_game_scene(self):
        return Range.logic.getSceneList()[self.game_scene_name]

    def update(self):
        imgui.set_game_ui_open(True)

        menu_common.set_anchored_window(
            imgui, self.h_align, self.v_align,
            self.options_width if self.show_options else self.width,
            self.height if not self.show_options else self.options_height)
        is_open, _ = imgui.begin("Pausado")
        if is_open:
            imgui.text("Jogo pausado")
            imgui.separator()

            if not self.show_options:
                if imgui.button(menu_common.t(self.options, "continue"), width=240) \
                        or menu_common.esc_just_pressed():
                    imgui.set_game_ui_open(False)
                    self._get_game_scene().resume()
                    self.object.scene.end()

                if imgui.button(menu_common.t(self.options, "options"), width=240):
                    self.show_options = True

                if imgui.button(menu_common.t(self.options, "main_menu"), width=240):
                    imgui.set_game_ui_open(False)
                    game_scene = self._get_game_scene()
                    game_scene.resume()
                    game_scene.replace(self.main_menu_scene_name)
                    self.object.scene.end()
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


# Compatibilidade com o nome antigo usado por cenas ou dados salvos.
PauseMenuOverlayComp = PauseMenuOverlayComponent
