import Range
from collections import OrderedDict
from mathutils import Color, Vector

class NewComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "BLENDER"),

        ("C_Header /Dados Basicos/LINENUMBERS_ON", True),
        ("Float", 58.6),
        ("Integer", 150),
        ("Boolean", True),
        ("String", "Cube"),
        ("Enum", {"Enum 1", "Enum 2", "Enum 3"}),

        ("C_Header /Vetores/MANIPUL", True),
        ("Vector 2D", Vector((0.8, 0.7))),
        ("Vector 3D", Vector((0.4, 0.3, 0.1))),
        ("Vector 4D", Vector((0.5, 0.2, 0.9, 0.6))),

        ("C_Header /Cores/COLOR", True),
        ("Color Alpha", Color((0.487, 0.211, 0.013, 1.0))),
        ("Color", Color((0.286, 0.286, 0.286, 1.0))),
    ])

    def awake(self, args):
        # Executa antes do start (bom para inicializar coisas sem dependencia da cena)
        pass

    def start(self, args):
        # --- Capturando os Argumentos para variaveis locais (self) ---

        # Dados Basicos
        self.val_float = args["Float"]
        self.val_int = args["Integer"]
        self.is_active = args["Boolean"]
        self.text_name = args["String"]
        self.mode = args["Enum"]

        # Vetores
        self.vec_2d = args["Vector 2D"]
        self.vec_3d = args["Vector 3D"]
        self.vec_4d = args["Vector 4D"]

        # Cores (Convertendo para Vector 4D se for aplicar no objeto)
        self.color_1 = args["Color Alpha"]
        self.color_2 = args["Color"]

        # Exemplo de aplicação direta da cor no objeto:
        # self.object.color = Vector(self.color_1).to_4d()

    def update(self):
        # Exemplo de uso
        # if self.is_active:
        #     self.object.worldPosition += self.vec_3d * 0.1
        pass
