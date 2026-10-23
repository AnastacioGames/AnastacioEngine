"""Runtime da UI Tree (protótipo).

Ligue um sensor Always (pulso ligado) a um controlador Python em modo Module:
    range_ui_runtime.main

Lê o texto ui_tree_data.py gravado por "Bake UI", desenha a tela ativa por
cima do render (post_draw) e executa as ações ligadas a cada evento.

A tela ativa é a propriedade de jogo "ui_screen" do dono do controlador:
nome da tela para mostrar, texto vazio para esconder o menu.  Assim dá para
ligar e desligar pelos Logic Bricks (atuador Property) ou por Python
(own["ui_screen"] = "Menu").  Sem a propriedade, começa na primeira tela.
"""

import Range
import range_ui_draw
from Range import events, logic


class Button:
    def __init__(self, data):
        self.data = data
        self.hover = False
        self.pressed = False

    def contains(self, mx, my):
        x, y, w, h = self.data["rect"]
        return x <= mx <= x + w and y <= my <= y + h


class UIRuntime:
    def __init__(self, data, owner):
        self.screens = {s["name"]: [Button(b) for b in s["buttons"]] for s in data["screens"]}
        self.owner = owner
        self.scene = owner.scene
        if "ui_screen" not in owner:
            owner["ui_screen"] = data["screens"][0]["name"] if data["screens"] else ""
        self.active = None
        self.sounds = {}
        self.scene.post_draw.append(self.draw)

    def show(self, name):
        """Troca a tela ativa; "" esconde o menu."""
        if name and name not in self.screens:
            print("[UI] tela não encontrada: %r" % name)
            name = ""
        for button in self.screens.get(self.active, ()):
            button.hover = button.pressed = False
        self.active = name or None
        self.owner["ui_screen"] = name
        if self.active:
            Range.render.showMouse(True)

    # -- eventos -------------------------------------------------------------

    def update(self):
        wanted = self.owner.get("ui_screen", "")
        if wanted != (self.active or ""):
            self.show(wanted)
        if self.active is None:
            return
        mx, my = logic.mouse.position  # 0-1, y a partir do topo
        lmb = logic.mouse.inputs[events.LEFTMOUSE]
        just_pressed, just_released = lmb.activated, lmb.released
        for button in list(self.screens.get(self.active, ())):
            inside = button.contains(mx, my)
            if inside and not button.hover:
                self.fire(button, "On Enter")
            elif button.hover and not inside:
                self.fire(button, "On Exit")
            button.hover = inside
            if inside:
                self.fire(button, "On Over")
                if just_pressed:
                    button.pressed = True
                    self.fire(button, "On Press")
            if just_released and button.pressed:
                button.pressed = False
                self.fire(button, "On Release")
                if inside:
                    self.fire(button, "On Click")

    def fire(self, button, event):
        for action, value in button.data["events"].get(event, ()):
            if action == "PRINT":
                print("[UI] %s: %s" % (button.data["name"], value))
            elif action == "MESSAGE":
                logic.sendMessage(value)
            elif action == "SCREEN":
                self.show(value)
            elif action == "SCENE":
                self.scene.replace(value)
            elif action == "QUIT":
                logic.endGame()
            elif action == "SOUND":
                self.play_sound(*value)

    def play_sound(self, path, volume):
        import aud
        sound = self.sounds.get(path)
        if sound is None:
            try:
                sound = aud.Sound.file(logic.expandPath(path))
            except Exception as exc:
                print("[UI] som não carregou: %r (%s)" % (path, exc))
                return
            # Guarda decodificado: cliques seguidos não releem o arquivo.
            sound = self.sounds[path] = sound.cache()
        aud.Device().play(sound).volume = volume

    # -- desenho -------------------------------------------------------------

    def draw(self):
        if self.active is None:
            return
        import bgl
        import blf
        width = Range.render.getWindowWidth()
        height = Range.render.getWindowHeight()
        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glPushMatrix()
        bgl.glLoadIdentity()
        bgl.glOrtho(0, width, 0, height, -1, 1)
        bgl.glMatrixMode(bgl.GL_MODELVIEW)
        bgl.glPushMatrix()
        bgl.glLoadIdentity()
        bgl.glDisable(bgl.GL_DEPTH_TEST)
        for button in self.screens.get(self.active, ()):
            data = button.data
            x, y, w, h = data["rect"]
            if button.pressed and button.hover:
                state = "PRESSED"
            elif button.hover:
                state = "HOVER"
            else:
                state = "NORMAL"
            range_ui_draw.draw_button(bgl, blf, data["style"], data["text"],
                                      x * width, height - (y + h) * height,
                                      w * width, h * height, state)
        bgl.glEnable(bgl.GL_DEPTH_TEST)
        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glPopMatrix()
        bgl.glMatrixMode(bgl.GL_MODELVIEW)
        bgl.glPopMatrix()


def main(cont):
    owner = cont.owner
    ui = owner.get("_ui_tree")
    if ui is None:
        try:
            import ui_tree_data
        except ImportError:
            print("[UI] texto ui_tree_data.py não encontrado; use Bake UI no editor")
            owner["_ui_tree"] = False
            return
        ui = owner["_ui_tree"] = UIRuntime(ui_tree_data.DATA, owner)
    if ui:
        ui.update()
