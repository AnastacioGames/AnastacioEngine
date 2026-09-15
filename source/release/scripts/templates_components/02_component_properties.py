"""Componente com propriedades editáveis no painel da Engine."""

from collections import OrderedDict

from mathutils import Color, Vector
import Range


class ComponentProperties(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "SETTINGS"),
        ("C_Header /Configuração/SETTINGS", True),
        ("Active", True),
        ("Display Name", "Meu componente"),
        ("Speed", 5.0),
        ("Direction", Vector((1.0, 0.0, 0.0))),
        ("Tint", Color((0.2, 0.6, 1.0, 1.0))),
        ("Mode", {"Default", "Alternative"}),
    ])

    def start(self, args):
        self.active = args["Active"]
        self.display_name = args["Display Name"]
        self.speed = args["Speed"]
        self.direction = args["Direction"]
        self.tint = args["Tint"]
        self.mode = args["Mode"]

    def update(self):
        if not self.active:
            return

        # Exemplo: aplique propriedades recebidas no objeto proprietário.
        # self.object.worldPosition += self.direction * self.speed * self.scene.timestep
        # self.object.color = Vector(self.tint).to_4d()
        pass
