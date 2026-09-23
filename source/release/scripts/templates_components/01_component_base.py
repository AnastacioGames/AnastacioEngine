"""Componente base para anexar a um Game Object."""

from collections import OrderedDict

import Range


class ComponentBase(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "SCRIPT"),
        ("Enabled", True),
    ])

    def awake(self, args):
        """Chamado antes de start; inicialize dados independentes da cena aqui."""
        self.enabled = args["Enabled"]

    def start(self, args):
        """Chamado uma vez quando o componente entra em cena."""
        self.scene = self.object.scene

    def update(self):
        """Chamado a cada passo de lógica."""
        if not self.enabled:
            return

    def dispose(self):
        """Chamado quando o componente deixa de existir."""
        pass
