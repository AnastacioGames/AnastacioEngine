"""Runtime da UI Tree (protótipo).

Ligue um sensor Always (pulso ligado) a um controlador Python em modo Module:
    range_ui_tree.main

Lê o texto ui_tree_data.py gravado por "Bake UI", desenha a tela ativa por
cima do render (post_draw) e executa as ações ligadas a cada evento.
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
    def __init__(self, data, scene):
        self.screens = {s["name"]: [Button(b) for b in s["buttons"]] for s in data["screens"]}
        self.active = data["screens"][0]["name"] if data["screens"] else None
        self.scene = scene
        scene.post_draw.append(self.draw)
        Range.render.showMouse(True)

    # -- eventos -------------------------------------------------------------

    def update(self):
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
                if value in self.screens:
                    for other in self.screens[self.active]:
                        other.hover = other.pressed = False
                    self.active = value
                else:
                    print("[UI] tela não encontrada: %r" % value)
            elif action == "SCENE":
                self.scene.replace(value)
            elif action == "QUIT":
                logic.endGame()

    # -- desenho -------------------------------------------------------------

    def draw(self):
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
        ui = owner["_ui_tree"] = UIRuntime(ui_tree_data.DATA, owner.scene)
    if ui:
        ui.update()
