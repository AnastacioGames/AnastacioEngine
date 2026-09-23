import bpy
import os
import sys
import importlib
from bpy.types import Operator, PropertyGroup
from bpy.props import StringProperty, EnumProperty, CollectionProperty, IntProperty, BoolProperty


# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================
def get_scripts_path_internal():
	blend_path = bpy.data.filepath
	if blend_path:
		root = os.path.dirname(blend_path)
		return root
	return None


class FLOWMENU_OT_wizard_toggle(Operator):
	bl_idname = "wm.flowmenu_wizard_toggle"
	bl_label = "Toggle Creator"

	def execute(self, context):
		context.scene.flowmenu_show_wizard = not context.scene.flowmenu_show_wizard
		return {'FINISHED'}


class FLOWMENU_OT_create_advanced_component(Operator):
	bl_idname = "wm.flowmenu_create_advanced_component"
	bl_label = "Create Component"
	bl_description = "Generate the Python script and register it"

	def execute(self, context):
		scene = context.scene
		ob = context.active_object

		if not ob or not hasattr(ob, "game"):
			self.report({'ERROR'}, "Selecione um objeto com Game Physics!")
			return {'CANCELLED'}

		root_path = get_scripts_path_internal()
		if not root_path:
			self.report({'ERROR'}, "Salve o arquivo .blend primeiro!")
			return {'CANCELLED'}

		s_module = scene.flowmenu_wizard_module
		s_class = scene.flowmenu_wizard_class

		if not s_module.isidentifier() or not s_class.isidentifier():
			self.report({'ERROR'}, "File and class names must be valid Python identifiers.")
			return {'CANCELLED'}

		# --- TEMPLATE COMPLETO COM VARIÁVEIS PRONTAS ---
		# Note as chaves duplas {{ }} no Enum/List para evitar erro de formatação

		final_code = """import Range
from collections import OrderedDict
from mathutils import Color, Vector

class {}(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "BLENDER"),

        ("C_Header /Dados Basicos/LINENUMBERS_ON", True),
        ("Float", 58.6),
        ("Integer", 150),
        ("Boolean", True),
        ("String", "Cube"),
        ("Enum", {{"Enum 1", "Enum 2", "Enum 3"}}),

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
""".format(s_class)

		# --- 2. SALVAR ARQUIVO ---
		scripts_dir = os.path.join(root_path, "scripts")
		try:
			if not os.path.exists(scripts_dir):
				os.makedirs(scripts_dir)
		except OSError as e:
			self.report({'ERROR'}, "Could not create scripts directory: " + str(e))
			return {'CANCELLED'}

		filepath = os.path.join(scripts_dir, "{}.py".format(s_module))
		if os.path.exists(filepath):
			self.report({'ERROR'}, "Component file already exists: " + filepath)
			return {'CANCELLED'}

		try:
			with open(filepath, "w", encoding="utf-8") as f:
				f.write(final_code)
		except Exception as e:
			self.report({'ERROR'}, "Save Error: " + str(e))
			return {'CANCELLED'}

		# --- 3. REGISTRAR E ADICIONAR ---
		try:
			if scripts_dir not in sys.path:
				sys.path.append(scripts_dir)

			importlib.invalidate_caches()

			full_name = "{}.{}".format(s_module, s_class)

			result = bpy.ops.logic.python_component_register(component_name=full_name)
			if 'FINISHED' not in result:
				self.report({'ERROR'}, "Could not register component: " + full_name)
				return {'CANCELLED'}

			bpy.ops.wm.flowmenu_component_list_refresh()

			scene.flowmenu_show_wizard = False
			self.report({'INFO'}, "Sucesso! " + full_name)

		except Exception as e:
			self.report({'ERROR'}, "Could not register component: " + str(e))
			return {'CANCELLED'}

		return {'FINISHED'}
