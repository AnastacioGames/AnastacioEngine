"""
Gatilho de Pause Menu (checkpoint (f) do plano de menu ImGui) - AnastacioEngine.

Uso: adicione este componente a um objeto da propria cena de jogo (ex.: o
jogador ou a camera). Ao apertar Esc, ele suspende a cena de jogo (fisica e
logica param, render continua) e carrega a cena "PauseMenu" como overlay
scene -- mecanismo existente e inalterado (Range.logic.addScene), empilhado
por cima, independente do ciclo de vida da cena de jogo.

Campos editaveis no painel do componente (args):
    pause_scene_name (string) nome da cena a carregar como overlay ao
                      pausar. Padrao: "PauseMenu"
"""

import Range


class PauseMenuTriggerComponent(Range.types.KX_PythonComponent):
    args = {"pause_scene_name": "PauseMenu"}

    def start(self, args):
        self.pause_scene_name = args["pause_scene_name"]

    def update(self):
        esc = Range.logic.keyboard.inputs[Range.events.ESCKEY]
        if Range.logic.KX_INPUT_JUST_ACTIVATED not in esc.queue:
            return

        scene = self.object.scene
        if scene.suspended:
            # Ja pausado (a cena de overlay ainda pode nao ter processado
            # o Resume neste frame) -- nao empilha uma segunda overlay.
            return

        scene.suspend()
        Range.logic.addScene(self.pause_scene_name, True)


# Compatibilidade com o nome antigo usado por cenas ou dados salvos.
PauseMenuTriggerComp = PauseMenuTriggerComponent
