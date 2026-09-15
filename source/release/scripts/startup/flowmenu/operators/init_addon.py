from bpy import ops
from bpy.types import Operator
from bpy.app import version

# Imports dos desenhos de interface
from ..drawings.draw_game_properties import draw_game_properties
from ..drawings.draw_game_component import draw_game_component

# Imports de funções auxiliares
from ..functions.get_modules import get_modules, get_modules_in_range
from ..functions.set_scripts_dir import set_scripts_dir
from ..functions.is_somethings import is_file_saved, is_bge_version


class FLOWMENU_OT_init_addon(Operator):
	bl_label = "Components Menu"
	bl_idname = "wm.flowmenu_ot_init"
	bl_description = "Opens a list of pre-made components to add to the object."
	bl_options = {"REGISTER", "UNDO"}

	@classmethod
	def poll(cls, context):
		return context.active_object is not None

	def invoke(self, context, event):
		"""
		Executado UMA VEZ ao clicar no botão/atalho.
		Aqui preparamos os dados para garantir que a lista esteja estável.
		"""
		wm = context.window_manager
		scene = context.scene

		# 1. Carrega os módulos (Usa o Cache que criamos, então é rápido)
		# Isso evita recriar a lista da esquerda a cada frame (o que causava o bug do clique duplo)
		dict_modules = get_modules_in_range(scene)
		dict_modules.update(get_modules(set_scripts_dir()))

		collection_modules = wm.collection_modules

		# Limpa e Recria a lista de Módulos (Lado Esquerdo) APENAS AQUI
		collection_modules.clear()
		for module in dict_modules:
			item = collection_modules.add()
			item.value = module

		# Proteção: Garante que o índice não esteja fora do limite
		if len(collection_modules) > 0:
			if wm.collection_modules_active >= len(collection_modules):
				wm.collection_modules_active = 0
			
			# Força o update no momento em que o menu abre para garantir a lista pré-preenchida
			from ..functions.get_modules import update_classes_list
			wm["last_module_index"] = -1  # Força a liberação da trava
			wm.collection_classes.clear()
			update_classes_list(None, context)

		# 2. Configura Tamanho da Janela (Lógica do Arquivo 2)
		width = context.window.width
		popup_width = int(width / 2.5)

		return wm.invoke_popup(self, width=popup_width)

	def draw(self, context):
		"""
		Executado repetidamente enquanto a janela está aberta.
		Aqui apenas desenhamos a interface baseada nos dados já carregados.
		"""
		layout = self.layout
		wm = context.window_manager
		scene = context.scene
		obj = context.object

		if not hasattr(obj, "game"):
			layout.label(text="Object has no Game Settings", icon="ERROR")
			return

		# Recupera as propriedades
		get_properties = wm
		collection_modules = get_properties.collection_modules
		index_active = get_properties.collection_modules_active
		collection_classes = get_properties.collection_classes

		# --- Cabeçalho ---
		row_title_addon = layout.box().row(align=True)
		row_title_addon.label(text="Components Menu")

		try:
			row_title_addon.operator("wm.flowmenu_reload_all_components",
									 text="Reload all", icon="RECOVER_LAST")
		except:
			pass

		row_title_addon.label(text="{}".format(obj.name.capitalize()), icon="OBJECT_DATA")

		if not is_file_saved():
			layout.row(align=True).box().label(text="Save the file first to use!", icon="INFO")
			return

		# Botões de Teste do Jogo
		play_row = layout.row(align=True)
		play_row.operator("view3d.game_start", text="Play (Embedded)", icon="PLAY")
		play_row.operator("wm.blenderplayer_start", text="Play (Standalone)", icon="GHOST_ENABLED")

		# Botões Principais
		game_row = layout.row()
		game_row.alignment = "LEFT"
		game_row.operator("wm.flowmenu_ot_create_component",
						  text="Create Component", icon="PLUS")
		game_row.operator("wm.flowmenu_open_external_editor",
						  text="Open External Editor", icon="CONSOLE")

		# --- Corpo das Listas ---
		main_row = layout.row(align=True)

		# Se não houver módulos, avisa
		if len(collection_modules) == 0:
			msg_col = main_row.column()
			msg_col.alert = True
			msg_col.box().label(text="No modules found! Create 'scripts' folder.", icon="INFO")
			return

		# ---------------------------
		# COLUNA 1: Módulos (Esquerda)
		# ---------------------------
		col_modules = main_row.column(align=True)
		col_modules.box().label(text="Modules", icon="FILE_FOLDER")

		# A lista já foi preenchida no invoke, aqui só desenhamos.
		# Isso garante que o clique seja instantâneo.
		col_modules.template_list("FLOWMENU_UL_modules_components", "flowmenu_ul_modules_components", get_properties,
								  "collection_modules", get_properties, "collection_modules_active", rows=12)

		# ---------------------------
		# COLUNA 2: Classes (Direita)
		# ---------------------------
		col_classes = main_row.column(align=True)
		col_classes.box().label(text="Classes", icon="FILE_SCRIPT")

		# Desenha apenas com base nos dados que já foram processados
		if len(collection_classes) > 0:
			col_classes.template_list("FLOWMENU_UL_classes_components", "flowmenu_ul_classes_components",
									  get_properties, "collection_classes", 
									  get_properties, "collection_classes_active", rows=12)
		elif len(collection_modules) > 0:
			col_classes.label(text="Module empty or error")
		else:
			col_classes.label(text="Select a Module")

	def execute(self, context):
		try:
			ops.wm.flowmenu_components_refresh()
		except:
			pass
		return {"FINISHED"}

	def check(self, context):
		return True