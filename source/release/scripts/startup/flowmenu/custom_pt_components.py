import bpy
from bpy.types import Panel
from rna_prop_ui import PropertyPanel

# ==============================================================================
# PAINEL CUSTOMIZADO: COMPONENT MANAGER & WIZARD
# ==============================================================================
class CUSTOM_PT_game_components(PropertyPanel, Panel):
    bl_label = "Component Manager"
    bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "game"
    bl_idname = "GAME_PT_game_components_custom" # ID Único do seu add-on

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.game

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # --- FERRAMENTAS GLOBAIS ---
        box_tools = layout.box()
        row_tools = box_tools.row(align=True)
        row_tools.operator("wm.flowmenu_reload_all_components", text="Reload All Scripts", icon="RECOVER_LAST")

        # --- SMART COMPONENT WIZARD (startup/smart_component_wizard.py) ---
        box = layout.box()
        box.label(text="Create New Smart Component", icon="SCRIPTPLUGINS")
        try:
            from smart_component_wizard import draw_wizard
        except ImportError:
            box.label(text="Wizard not available", icon="ERROR")
        else:
            draw_wizard(box, context)

# ==============================================================================
# PAINEL CUSTOMIZADO: EXISTING COMPONENTS (Organizado por Módulos/Pastas)
# ==============================================================================
class CUSTOM_PT_game_existing_components(PropertyPanel, Panel):
    bl_label = "Existing Components"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "game"
    bl_idname = "GAME_PT_game_existing_components_custom"

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.game

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        box = layout.box()

        row_list = box.row()
        row_list.label(text="Internal & External Scripts", icon="SCRIPTPLUGINS")
        row_list.operator("wm.flowmenu_component_list_refresh", text="", icon="FILE_REFRESH")
        
        main_row = box.row(align=True)
        
        col_modules = main_row.column(align=True)
        col_modules.label(text="Modules", icon="FILE_FOLDER")
        col_modules.template_list(
            "FLOWMENU_UL_modules_components", "flowmenu_ul_modules_components", 
            wm, "collection_modules", 
            wm, "collection_modules_active", 
            rows=5
        )
        
        col_classes = main_row.column(align=True)
        col_classes.label(text="Classes", icon="FILE_SCRIPT")
        if len(wm.collection_classes) > 0:
            col_classes.template_list(
                "FLOWMENU_UL_classes_components", "flowmenu_ul_classes_components", 
                wm, "collection_classes", 
                wm, "collection_classes_active", 
                rows=5
            )
        elif len(wm.collection_modules) > 0:
            col_classes.label(text="Module empty")
        else:
            col_classes.label(text="Select a Module")

        # Recarrega só a classe escolhida acima, em todos os objetos que a usam.
        if len(wm.collection_classes) > wm.collection_classes_active:
            cls_name = wm.collection_classes[wm.collection_classes_active].value
            col = box.column(align=True)
            col.label(text="Update this script on every object that uses it:", icon="INFO")
            col.operator("wm.flowmenu_reload_selected_class",
                         text="Reload '%s' in All Objects" % cls_name, icon="RECOVER_LAST")
            
# ==============================================================================
# PAINEL CUSTOMIZADO: OBJECT'S COMPONENTS
# ==============================================================================
class CUSTOM_PT_game_object_components(PropertyPanel, Panel):
    bl_label = "Object's Components"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "game"
    bl_idname = "GAME_PT_game_object_components_custom"

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.game

    def draw(self, context):
        layout = self.layout
        ob = context.active_object
        game = ob.game

        if not game.components:
            layout.label(text="No components on this object.", icon="INFO")
            return

        for i, c in enumerate(game.components):
            box = layout.box()
            row = box.row(align=1)
            row.prop(c, "show_expanded", text="", emboss=0)
            row.prop(c, "toggle_execution", text="", emboss=False)

            if "C_Icons" in c.properties:
                try:
                    icondict = c.properties["C_Icons"].value.split("+")
                    row.label(text=c.name, icon=icondict[0])
                except:
                    row.label(text=c.name)
            else:
                row.label(text=c.name)
            
            row.operator("wm.flowmenu_open_external_editor", text="", icon="FILE_TEXT").index = i

            row.operator("logic.python_component_reload", icon="RECOVER_LAST", text="").index = i
            row.operator("logic.python_component_move_up", icon="TRIA_UP", text="").index = i
            row.operator("logic.python_component_move_down", icon="TRIA_DOWN", text="").index = i

            sub = row.row(align=0)
            sub.operator("logic.python_component_remove", text="", icon='X').index = i

            # Same box as Game Components: Smart Component fields, warnings,
            # draw_ui and Editor buttons.
            from bl_ui.properties_game import draw_component_body
            draw_component_body(box, ob, c, i)
