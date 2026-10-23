"""Runtime da UI Tree (protótipo).

Ligue um sensor Always (pulso ligado) a um controlador Python em modo Module:
    range_ui_tree.main

Lê o texto ui_tree_data.py gravado por "Bake UI", desenha a tela ativa por
cima do render (post_draw) e executa as ações ligadas a cada evento.
"""

import math

import Range
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
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
        for button in self.screens.get(self.active, ()):
            data = button.data
            x, y, w, h = data["rect"]
            px, pw, ph = x * width, w * width, h * height
            py = height - (y + h) * height
            if button.pressed and button.hover:
                color = data["press"]
            elif button.hover:
                color = data["hover"]
            else:
                color = data["color"]
            bgl.glColor4f(*color)
            _rounded_rect(bgl, px, py, pw, ph, min(ph, pw) * 0.5)
            size = max(8, int(ph * 0.45))
            blf.size(0, size, 72)
            tw, th = blf.dimensions(0, data["text"])
            bgl.glColor4f(*data["text_color"])
            blf.position(0, px + (pw - tw) / 2, py + (ph - size * 0.7) / 2, 0)
            blf.draw(0, data["text"])
        bgl.glEnable(bgl.GL_DEPTH_TEST)
        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glPopMatrix()
        bgl.glMatrixMode(bgl.GL_MODELVIEW)
        bgl.glPopMatrix()


def _rounded_rect(bgl, x, y, w, h, r, steps=8):
    corners = ((x + w - r, y + h - r, 0), (x + r, y + h - r, 1),
               (x + r, y + r, 2), (x + w - r, y + r, 3))
    bgl.glBegin(bgl.GL_POLYGON)
    for cx, cy, quarter in corners:
        for i in range(steps + 1):
            a = (quarter + i / steps) * math.pi / 2
            bgl.glVertex2f(cx + math.cos(a) * r, cy + math.sin(a) * r)
    bgl.glEnd()


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
