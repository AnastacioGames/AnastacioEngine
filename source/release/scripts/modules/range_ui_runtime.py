"""Runtime da UI Tree (protótipo).

Ligue um sensor Always (pulso ligado) a um controlador Python em modo Module:
    range_ui_runtime.main

Lê o texto ui_tree_data.py gravado por "Bake UI", desenha a tela ativa por
cima do render (post_draw) e executa as ações ligadas a cada evento.

A tela ativa é a propriedade de jogo "ui_screen" do dono do controlador:
nome da tela para mostrar, texto vazio para esconder o menu.  Assim dá para
ligar e desligar pelos Logic Bricks (atuador Property) ou por Python
(own["ui_screen"] = "Menu", ou range_ui_runtime.show("Menu")).  Sem a
propriedade, começa na primeira tela.

Telas marcadas como HUD ficam sempre visíveis, por baixo do menu, enquanto a
propriedade "ui_hud" for verdadeira (padrão).  Os widgets de HUD leem as
propriedades de jogo do objeto escolhido a cada frame.

Navegação sem mouse: setas (ou analógico/direcional do controle) mudam o foco,
Enter/Espaço (ou botão A) apertam, esquerda/direita mexem o Slider em foco.
"""

import time

import Range
import range_ui_draw
from Range import events, logic

# Instâncias ativas (uma por dono do script); a API do módulo usa a primeira.
_instances = []


class Element:
    """Botão ou controle clicável: retângulo normalizado (x, y do topo)."""

    def __init__(self, data):
        self.data = data
        self.hover = False
        self.pressed = False

    def contains(self, screen, px, py, width, height):
        """px, py em pixels, y de baixo."""
        x, y, w, h = screen.place(self.data, width, height)
        return x <= px <= x + w and y <= py <= y + h

    def enabled(self, owner):
        prop = self.data.get("enabled_prop")
        return not prop or bool(owner.get(prop, False))

    def selected(self, owner):
        prop = self.data.get("selected_prop")
        return bool(prop) and bool(owner.get(prop, False))

    def reset(self):
        self.hover = self.pressed = False


class Button(Element):
    def __init__(self, data):
        super().__init__(data)
        # Valores animados; seguem o alvo do estado (range_ui_draw.state_target).
        self.color, self.scale = range_ui_draw.state_target(data["style"], "NORMAL")

    def state(self, owner):
        if not self.enabled(owner):
            return "DISABLED"
        if self.pressed and self.hover:
            return "PRESSED"
        if self.hover:
            return "HOVER"
        return "SELECTED" if self.selected(owner) else "NORMAL"

    def reset(self):
        super().reset()
        self.color, self.scale = range_ui_draw.state_target(self.data["style"], "NORMAL")

    def animate(self, dt, owner):
        color, scale = range_ui_draw.state_target(self.data["style"], self.state(owner))
        duration = self.data["style"].get("anim_time", 0.0)
        # Aproximação exponencial: ~95% do caminho em anim_time segundos.
        k = 1.0 if duration <= 0.0 else min(1.0, dt * 3.0 / duration)
        self.color = tuple(c + (t - c) * k for c, t in zip(self.color, color))
        self.scale += (scale - self.scale) * k


class Control(Element):
    """Toggle ou Slider: grava numa propriedade de jogo."""

    @property
    def kind(self):
        return self.data["kind"]


# Fundo primeiro: Panel e Image ficam atrás do resto.
_DRAW_ORDER = {"PANEL": 0, "IMAGE": 1}


class Screen:
    def __init__(self, data):
        self.name = data["name"]
        self.mode = data.get("scale_mode", "STRETCH")
        self.design = data.get("design", (640.0, 360.0))
        self.fade = data.get("fade", 0.0)
        self.sounds = data.get("sounds", {})
        self.camera = data.get("camera", "")
        self.buttons = [Button(b) for b in data["buttons"]]
        widgets = sorted(data.get("widgets", ()), key=lambda w: _DRAW_ORDER.get(w["kind"], 2))
        self.controls = [Control(w) for w in widgets if w["kind"] in ("TOGGLE", "SLIDER")]
        self.widgets = [w for w in widgets if w["kind"] not in ("TOGGLE", "SLIDER")]
        # Ordem de leitura (de cima para baixo, da esquerda para a direita)
        # para a navegação por teclado.
        self.focusables = sorted(self.buttons + self.controls,
                                 key=lambda e: (round(e.data["rect"][1], 3), e.data["rect"][0]))

    def reset(self):
        for element in self.focusables:
            element.reset()

    def place(self, data, width, height):
        return range_ui_draw.place(data["rect"], self.mode, self.design,
                                   data.get("anchor", "CENTER"), width, height)


class UIRuntime:
    def __init__(self, data, owner):
        menus = [s for s in data["screens"] if not s.get("hud")]
        self.screens = {s["name"]: Screen(s) for s in menus}
        self.huds = [Screen(s) for s in data["screens"] if s.get("hud")]
        self.owner = owner
        self.scene = owner.scene
        if "ui_screen" not in owner:
            owner["ui_screen"] = menus[0]["name"] if menus else ""
        if "ui_hud" not in owner:
            owner["ui_hud"] = True
        self.active = None
        self.alpha = 1.0
        self.leaving = None  # tela saindo em fade-out
        self.leave_alpha = 0.0
        self.focus = None
        self.dragging = None
        self.last_mouse = None
        self.last_stick = 0
        self.sounds = {}
        self.textures = {}
        self.last_draw = None
        self.master_volume = None
        self.audio_controls = [w for s in data["screens"] for w in s.get("widgets", ())
                               if w.get("audio", "NONE") != "NONE"]
        self.scene.post_draw.append(self.draw)
        _instances.append(self)

    @property
    def screen(self):
        return self.screens.get(self.active) if self.active else None

    def show(self, name):
        """Troca a tela ativa; "" esconde o menu."""
        if name and name not in self.screens:
            print("[UI] tela não encontrada: %r" % name)
            name = ""
        old = self.screen
        if old is not None:
            old.reset()
            if old.fade > 0.0:
                self.leaving, self.leave_alpha = old, self.alpha
        self.focus = self.dragging = None
        self.active = name or None
        self.owner["ui_screen"] = name
        screen = self.screen
        if screen is not None:
            self.alpha = 0.0 if screen.fade > 0.0 else 1.0
            if self.leaving is screen:
                self.leaving = None
            Range.render.showMouse(True)

    def obj_for(self, data):
        name = data.get("object", "")
        return self.scene.objects.get(name) if name else self.owner

    # -- eventos -------------------------------------------------------------

    def update(self):
        self.apply_audio()
        wanted = self.owner.get("ui_screen", "")
        if wanted != (self.active or ""):
            self.show(wanted)
        screen = self.screen
        if screen is None:
            return
        mx, my = logic.mouse.position  # 0-1, y a partir do topo
        if self.last_mouse is not None and (mx, my) != self.last_mouse:
            self.focus = None  # o mouse mexeu: volta a mandar o hover
        self.last_mouse = (mx, my)
        width = Range.render.getWindowWidth()
        height = Range.render.getWindowHeight()
        px, py = mx * width, (1.0 - my) * height
        lmb = logic.mouse.inputs[events.LEFTMOUSE]
        nav_press, nav_release = self.navigate(screen)

        for element in list(screen.focusables):
            if not element.enabled(self.owner):
                if element.hover:
                    self.fire(element, "On Exit", screen)
                element.reset()
                continue
            if self.focus is not None:
                inside = element is self.focus
                just_pressed, just_released = inside and nav_press, nav_release
            else:
                inside = element.contains(screen, px, py, width, height)
                just_pressed, just_released = lmb.activated, lmb.released
            if inside and not element.hover:
                self.fire(element, "On Enter", screen)
            elif element.hover and not inside:
                self.fire(element, "On Exit", screen)
            element.hover = inside
            if self.screen is not screen:
                return  # uma ação trocou de tela
            if isinstance(element, Button):
                self.update_button(element, screen, inside, just_pressed, just_released)
            else:
                self.update_control(element, screen, inside, just_pressed, just_released, px)
            if self.screen is not screen:
                return

    def update_button(self, button, screen, inside, just_pressed, just_released):
        if inside:
            self.fire(button, "On Over", screen)
            if just_pressed:
                button.pressed = True
                self.fire(button, "On Press", screen)
        if just_released and button.pressed:
            button.pressed = False
            self.fire(button, "On Release", screen)
            if inside:
                self.fire(button, "On Click", screen)

    def update_control(self, control, screen, inside, just_pressed, just_released, px):
        data = control.data
        if control.kind == "TOGGLE":
            if inside and just_pressed:
                obj = self.obj_for(data)
                if obj is not None:
                    obj[data["property"]] = not obj.get(data["property"], False)
                    self.fire(control, "On Change", screen)
            return
        # Slider: arrasta enquanto o botão do mouse estiver apertado.
        if inside and just_pressed and self.focus is None:
            self.dragging = control
        if just_released and self.dragging is control:
            self.dragging = None
        if self.dragging is control:
            x, _, w, h = screen.place(data, Range.render.getWindowWidth(),
                                      Range.render.getWindowHeight())
            # O puxador anda dentro do trilho (meia bola de cada lado).
            knob = h * 0.8
            frac = (px - x - knob * 0.5) / max(1e-6, w - knob)
            self.set_slider(control, screen, frac)

    def set_slider(self, control, screen, frac):
        data = control.data
        obj = self.obj_for(data)
        if obj is None:
            return
        frac = max(0.0, min(1.0, frac))
        value = data["min"] + (data["max"] - data["min"]) * frac
        current = obj.get(data["property"])
        if isinstance(current, int) and not isinstance(current, bool):
            value = int(round(value))
        if current != value:
            obj[data["property"]] = value
            self.fire(control, "On Change", screen)

    def navigate(self, screen):
        """Teclado e controle: move o foco e devolve (apertou, soltou)."""
        keyboard = logic.keyboard.inputs
        step = 0
        side = 0
        if keyboard[events.UPARROWKEY].activated:
            step = -1
        elif keyboard[events.DOWNARROWKEY].activated:
            step = 1
        if keyboard[events.LEFTARROWKEY].activated:
            side = -1
        elif keyboard[events.RIGHTARROWKEY].activated:
            side = 1
        confirm = (events.RETKEY, events.PADENTER, events.SPACEKEY)
        press = any(keyboard[k].activated for k in confirm)
        release = any(keyboard[k].released for k in confirm)

        joy = next((j for j in logic.joysticks if j is not None), None)
        if joy is not None:
            axes = joy.axisValues
            stick = 0
            if len(axes) > 1:
                stick = -1 if axes[1] < -0.5 else (1 if axes[1] > 0.5 else 0)
            if stick and stick != self.last_stick:
                step = stick
            sx = 0
            if axes:
                sx = -1 if axes[0] < -0.5 else (1 if axes[0] > 0.5 else 0)
            if sx and not self.last_stick and not stick:
                side = sx
            self.last_stick = stick or sx
            pressed_now = 0 in joy.activeButtons
            press = press or (pressed_now and not getattr(self, "_joy_a", False))
            release = release or (not pressed_now and getattr(self, "_joy_a", False))
            self._joy_a = pressed_now

        items = [e for e in screen.focusables if e.enabled(self.owner)]
        if self.focus is not None and self.focus not in items:
            self.focus = None
        if step and items:
            if self.focus not in items:
                self.focus = items[0] if step > 0 else items[-1]
            else:
                self.focus = items[(items.index(self.focus) + step) % len(items)]
        if side and isinstance(self.focus, Control) and self.focus.kind == "SLIDER":
            data = self.focus.data
            obj = self.obj_for(data)
            if obj is not None:
                span = data["max"] - data["min"]
                frac = range_ui_draw.bar_fraction(data, {data["property"]: obj.get(data["property"], 0)})
                self.set_slider(self.focus, screen, frac + side * 0.05 if span else 0.0)
        if self.focus is None:
            return False, False
        return press, release

    def fire(self, element, event, screen):
        sound = None
        if event == "On Enter":
            sound = screen.sounds.get("hover")
        elif event in ("On Click", "On Change"):
            sound = screen.sounds.get("click")
        if sound:
            self.play_sound(sound, 1.0)
        for action, value in element.data.get("events", {}).get(event, ()):
            if action == "PRINT":
                data = element.data
                print("[UI] %s: %s" % (data.get("name") or data.get("text") or data.get("kind"), value))
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
            elif action == "SET_PROP":
                self.set_property(*value)
            elif action == "ADD_PROP":
                self.add_property(*value)
            elif action == "TOGGLE_PROP":
                self.owner[value] = not self.owner.get(value, False)
            elif action == "PYTHON":
                self.run_python(value)

    def set_property(self, name, text):
        """Converte o texto para o tipo atual da propriedade (bool/int/float)."""
        current = self.owner.get(name)
        if isinstance(current, bool):
            value = text.strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(current, (int, float)):
            try:
                value = type(current)(float(text))
            except ValueError:
                print("[UI] valor inválido para %s: %r" % (name, text))
                return
        else:
            value = text
        self.owner[name] = value

    def add_property(self, name, text):
        try:
            delta = float(text)
        except ValueError:
            print("[UI] valor inválido para %s: %r" % (name, text))
            return
        current = self.owner.get(name, 0)
        self.owner[name] = type(current)(current + delta) if isinstance(current, int) else current + delta

    def run_python(self, path):
        import importlib
        module_name, _, func_name = path.rpartition(".")
        try:
            func = getattr(importlib.import_module(module_name), func_name)
        except (ImportError, AttributeError, ValueError) as exc:
            print("[UI] Run Python: %r não encontrado (%s)" % (path, exc))
            return
        func(self)

    def apply_audio(self):
        """Toggle com Audio=Sound e Slider com Audio=Volume mandam no volume
        geral do jogo (todos os sons, não só os da UI)."""
        if not self.audio_controls:
            return
        volume = 1.0
        for data in self.audio_controls:
            obj = self.obj_for(data)
            value = obj.get(data["property"]) if obj is not None else None
            if value is None:
                continue
            if data["audio"] == "SOUND":
                volume *= 1.0 if value else 0.0
            else:
                span = data["max"] - data["min"]
                volume *= max(0.0, (value - data["min"]) / span) if span else 1.0
        if volume != self.master_volume:
            import aud
            aud.Device().volume = volume
            self.master_volume = volume

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

    def widget_values(self, data):
        obj = self.obj_for(data)
        if obj is None:
            return {}
        return {prop: obj[prop] for prop in obj.getPropertyNames()}

    def texture(self, path):
        """Textura GL da imagem (carregada uma vez com Range.texture)."""
        if path in self.textures:
            return self.textures[path]
        import bgl
        bindcode = 0
        try:
            source = Range.texture.ImageFFmpeg(logic.expandPath(path))
            pixels = source.image
            w, h = source.size
            ids = bgl.Buffer(bgl.GL_INT, 1)
            bgl.glGenTextures(1, ids)
            bindcode = ids[0]
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, bindcode)
            bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
            bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
            bgl.glTexImage2D(bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA, w, h, 0,
                             bgl.GL_RGBA, bgl.GL_UNSIGNED_BYTE, pixels)
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)
        except Exception as exc:
            print("[UI] imagem não carregou: %r (%s)" % (path, exc))
        self.textures[path] = bindcode
        return bindcode

    def hud_area(self, screen):
        """(esquerda, baixo, largura, altura) do viewport da câmera do HUD, ou
        None para a janela inteira."""
        if not screen.camera:
            return None
        cam = self.scene.objects.get(screen.camera)
        if cam is None or not getattr(cam, "useViewport", False):
            return None
        left, bottom, right, top = cam.viewport
        if right <= left or top <= bottom:
            return None
        return left, bottom, right - left, top - bottom

    def draw_widgets(self, bgl, blf, screen, width, height):
        for data in screen.widgets:
            x, y, w, h = screen.place(data, width, height)
            bindcode = self.texture(data["path"]) if data["kind"] == "IMAGE" and data["path"] else 0
            range_ui_draw.draw_widget(bgl, blf, data, self.widget_values(data),
                                      x, y, w, h, bindcode=bindcode)

    def draw_screen(self, bgl, blf, screen, width, height, dt, animate):
        self.draw_widgets(bgl, blf, screen, width, height)
        for control in screen.controls:
            data = control.data
            x, y, w, h = screen.place(data, width, height)
            range_ui_draw.draw_widget(bgl, blf, data, self.widget_values(data), x, y, w, h,
                                      hover=control.hover or self.dragging is control)
        for button in screen.buttons:
            data = button.data
            x, y, w, h = screen.place(data, width, height)
            if animate:
                button.animate(dt, self.owner)
            range_ui_draw.draw_button(bgl, blf, data["style"], data["text"], x, y, w, h,
                                      button.state(self.owner), button.color, button.scale)

    def draw(self):
        hud = self.huds if self.owner.get("ui_hud", True) else []
        screen = self.screen
        if screen is None and self.leaving is None and not hud:
            return
        import bgl
        import blf
        now = time.perf_counter()
        dt = 0.0 if self.last_draw is None else min(0.1, now - self.last_draw)
        self.last_draw = now
        width = Range.render.getWindowWidth()
        height = Range.render.getWindowHeight()
        # O render deixa iluminação/shader ligados; sem isso as cores do
        # desenho imediato saem escurecidas.
        bgl.glPushAttrib(bgl.GL_ALL_ATTRIB_BITS)
        bgl.glUseProgram(0)
        bgl.glDisable(bgl.GL_LIGHTING)
        bgl.glDisable(bgl.GL_TEXTURE_2D)
        bgl.glDisable(bgl.GL_CULL_FACE)
        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glPushMatrix()
        bgl.glLoadIdentity()
        bgl.glOrtho(0, width, 0, height, -1, 1)
        bgl.glMatrixMode(bgl.GL_MODELVIEW)
        bgl.glPushMatrix()
        bgl.glLoadIdentity()
        bgl.glDisable(bgl.GL_DEPTH_TEST)
        range_ui_draw.set_alpha(1.0)
        for hud_screen in hud:
            area = self.hud_area(hud_screen)
            if area is None:
                self.draw_widgets(bgl, blf, hud_screen, width, height)
                continue
            # Split screen: o HUD vive dentro do viewport da sua câmera.
            left, bottom, w, h = area
            bgl.glEnable(bgl.GL_SCISSOR_TEST)
            bgl.glScissor(left, bottom, w, h)
            bgl.glPushMatrix()
            bgl.glTranslatef(left, bottom, 0.0)
            self.draw_widgets(bgl, blf, hud_screen, w, h)
            bgl.glPopMatrix()
            bgl.glDisable(bgl.GL_SCISSOR_TEST)
        if self.leaving is not None:
            self.leave_alpha -= dt / self.leaving.fade
            if self.leave_alpha <= 0.0:
                self.leaving = None
            else:
                range_ui_draw.set_alpha(self.leave_alpha)
                self.draw_screen(bgl, blf, self.leaving, width, height, dt, False)
        if screen is not None:
            if self.alpha < 1.0:
                self.alpha = min(1.0, self.alpha + dt / screen.fade) if screen.fade > 0.0 else 1.0
            range_ui_draw.set_alpha(self.alpha)
            self.draw_screen(bgl, blf, screen, width, height, dt, True)
        range_ui_draw.set_alpha(1.0)
        bgl.glEnable(bgl.GL_DEPTH_TEST)
        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glPopMatrix()
        bgl.glMatrixMode(bgl.GL_MODELVIEW)
        bgl.glPopMatrix()
        bgl.glPopAttrib()


# -- API para scripts ---------------------------------------------------------

def get():
    """UIRuntime ativo (ou None antes do primeiro pulso)."""
    # Donos de cenas que já acabaram ficam inválidos: descarta.
    _instances[:] = [ui for ui in _instances if not ui.owner.invalid]
    return _instances[0] if _instances else None


def show(name):
    """Mostra a tela pelo nome; show("") esconde o menu."""
    ui = get()
    if ui is not None:
        ui.show(name)


def hide():
    show("")


def set_hud(visible):
    ui = get()
    if ui is not None:
        ui.owner["ui_hud"] = bool(visible)


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
