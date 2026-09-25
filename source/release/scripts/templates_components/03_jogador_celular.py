"""Jogador que anda e pula no PC, no controle (gamepad) e no celular, sem código de toque.

Como usar:
1. Anexe este componente ao objeto do jogador (Game Object > Components > Register).
2. Para pular, o objeto precisa de física Dynamic ou Rigid Body.
3. Em Export > Web (Range) > Touch controls, escolha "Stick + 2 buttons" (padrão) ou "D-pad + 4 buttons".

O controle na tela do celular chega ao jogo como o gamepad 0, então este componente lê três fontes:
- teclado: WASD ou setas para andar, Espaço para pular;
- gamepad 0: stick esquerdo ou d-pad para andar, botão A para pular;
- tela do celular: o mesmo gamepad 0, desenhado pela página.

No PC, teste o controle na tela abrindo o pacote Web com ?touch=1 no endereço.
"""

from collections import OrderedDict

from mathutils import Vector
import Range

# Numeração de Range.logic.joysticks[i].activeButtons (padrão SDL). O botão A é 0, não 1.
BUTTON_A = 0
DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT = 11, 12, 13, 14


class JogadorCelular(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "ARMATURE_DATA"),
        ("Speed", 5.0),
        ("Jump Speed", 6.0),
        ("Move Relative To Object", False),
        ("Stick Deadzone", 0.2),
    ])

    def start(self, args):
        self.speed = args["Speed"]
        self.jump_speed = args["Jump Speed"]
        self.local = args["Move Relative To Object"]
        self.deadzone = args["Stick Deadzone"]
        self.a_was_pressed = False
        self.on_ground = False
        # A física avisa cada contato; um contato abaixo do centro, em superfície deitada, é chão.
        try:
            self.object.collisionCallbacks.append(self.on_collision)
        except AttributeError:
            print("JogadorCelular: '%s' não tem física; ele anda, mas não pula." % self.object.name)

    def on_collision(self, other, point, normal):
        if abs(normal.z) > 0.7 and point.z < self.object.worldPosition.z:
            self.on_ground = True

    def update(self):
        x, y, jump = self.read_input()

        if x or y:
            step = self.speed * Range.logic.deltaTime()
            self.object.applyMovement((x * step, y * step, 0.0), self.local)

        if jump and self.on_ground:
            velocity = self.object.getLinearVelocity()
            self.object.setLinearVelocity((velocity.x, velocity.y, self.jump_speed))
        self.on_ground = False

    def read_input(self):
        """Devolve (x, y, pular). x e y vão de -1 a 1; y positivo é para frente."""
        keyboard = Range.logic.keyboard.inputs
        events = Range.events

        def held(*keys):
            return any(keyboard[k].active for k in keys)

        x = held(events.DKEY, events.RIGHTARROWKEY) - held(events.AKEY, events.LEFTARROWKEY)
        y = held(events.WKEY, events.UPARROWKEY) - held(events.SKEY, events.DOWNARROWKEY)
        jump = keyboard[events.SPACEKEY].activated

        joysticks = Range.logic.joysticks
        pad = joysticks[0] if joysticks else None
        if pad:
            buttons = pad.activeButtons
            axes = pad.axisValues
            stick = Vector((axes[0], -axes[1])) if len(axes) >= 2 else Vector((0.0, 0.0))
            if stick.length < self.deadzone:
                stick = Vector((0.0, 0.0))
            dpad_x = (DPAD_RIGHT in buttons) - (DPAD_LEFT in buttons)
            dpad_y = (DPAD_UP in buttons) - (DPAD_DOWN in buttons)
            # O teclado vence; sem tecla, vale o d-pad e depois o stick (analógico, anda mais devagar).
            x = x or dpad_x or stick.x
            y = y or dpad_y or stick.y
            # Botão A: "pulou" só no quadro em que foi apertado, como o activated do teclado.
            pressed = BUTTON_A in buttons
            jump = jump or (pressed and not self.a_was_pressed)
            self.a_was_pressed = pressed

        return x, y, jump
