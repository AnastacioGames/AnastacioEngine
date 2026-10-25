"""Diálogo sem código num objeto Text (Text Box do painel Game Text).

"Setup Dialogue" no painel liga um sensor Always (pulso) a um controlador
Python em modo Module:
    range_text_dialogue.main

A Text Box quebra e pagina o texto (KX_FontObject); aqui só entram a máquina
de escrever e o avanço: Enter/Espaço, clique ou botão A completam a página e
depois passam para a próxima.  Propriedades de jogo do objeto:

    td_speed    letras por segundo (0 = página inteira de uma vez)
    td_end      no fim: "HIDE" esconde, "RESTART" volta à 1ª página,
                "KEEP" deixa a última página na tela
    td_message  assunto mandado (sendMessage) no fim; vazio = nada

Trocar o texto (propriedade "Text" do objeto, Property actuator ou o nó
Show Dialogue da UI Tree) recomeça o diálogo e mostra o objeto de novo.
"""

from Range import events, logic

ADVANCE_KEYS = (events.RETKEY, events.PADENTER, events.SPACEKEY)
END_MODES = ("HIDE", "RESTART", "KEEP")

# id(objeto) -> estado; o objeto vai junto para descartar ids reaproveitados.
_states = {}


class _State:
    def __init__(self, owner):
        self.owner = owner
        self.text = None
        self.shown = 0.0
        self.done = False
        self.time = logic.getFrameTime()
        self.joy_down = False


def _advance_pressed(state):
    keyboard = logic.keyboard.inputs
    pressed = any(keyboard[k].activated for k in ADVANCE_KEYS)
    pressed = pressed or logic.mouse.inputs[events.LEFTMOUSE].activated
    joy = next((j for j in logic.joysticks if j is not None), None)
    down = joy is not None and 0 in joy.activeButtons
    pressed = pressed or (down and not state.joy_down)
    state.joy_down = down
    return pressed


def _finish(owner, state):
    message = owner.get("td_message", "")
    if message:
        logic.sendMessage(message)
    end = owner.get("td_end", "HIDE")
    if end == "RESTART":
        owner.page = 0
        state.shown = 0.0
        return
    state.done = True
    if end == "HIDE":
        owner.visible = False


def main(cont):
    owner = cont.owner
    state = _states.get(id(owner))
    if state is None or state.owner is not owner:
        state = _states[id(owner)] = _State(owner)
    now = logic.getFrameTime()
    dt = max(0.0, now - state.time)
    state.time = now

    if owner.text != state.text:
        state.text = owner.text
        state.shown = 0.0
        state.done = False
        owner.page = 0
        owner.visible = True
    if state.done or not owner.visible:
        return

    count = owner.characterCount
    speed = owner.get("td_speed", 40.0)
    state.shown = min(count, state.shown + speed * dt) if speed > 0.0 else count
    owner.visibleCharacters = int(state.shown)

    if not _advance_pressed(state):
        return
    if state.shown < count:
        state.shown = count
    elif owner.page + 1 < owner.pageCount:
        owner.page += 1
        state.shown = 0.0
    else:
        _finish(owner, state)
    owner.visibleCharacters = int(state.shown)
