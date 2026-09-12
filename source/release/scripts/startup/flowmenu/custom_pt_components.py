import bpy
from bpy.types import Panel
from rna_prop_ui import PropertyPanel

# ==============================================================================
# PAINEL CUSTOMIZADO: COMPONENT MANAGER & WIZARD
# ==============================================================================
class CUSTOM_PT_game_components(PropertyPanel, Panel):
    bl_label = "Component Manager"
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
        row_tools.operator("wm.flowmenu_open_external_editor", text="Open Project", icon="CONSOLE").index = -1

        # --- CABEÇALHO DO PAINEL ---
        row = layout.row(align=True)
        
        show_wizard = getattr(scene, "flowmenu_show_wizard", False)
        icon_wiz = "TRIA_DOWN" if show_wizard else "TRIA_RIGHT"
        
        row.operator("wm.flowmenu_wizard_toggle", text="New Component Wizard", icon=icon_wiz)

        # --- ÁREA DO WIZARD ---
        if show_wizard:
            box = layout.box()
            row = box.row()
            row.label(text="Create New Script", icon="FILE_SCRIPT")

            col = box.row(align=True)
            split = col.split(factor=0.35)
            split.label(text="File Name:", icon="FILE_TEXT")
            split.prop(scene, "flowmenu_wizard_module", text="")

            split = col.split(factor=0.35)
            split.label(text="Class Name:", icon="SCRIPTPLUGINS")
            split.prop(scene, "flowmenu_wizard_class", text="")

            box.separator()
            row = box.row()
            row.scale_y = 1.2
            row.operator("wm.flowmenu_create_advanced_component", text="CREATE COMPONENT", icon="SCRIPTPLUGINS")
            box.separator()

# ==============================================================================
# PAINEL CUSTOMIZADO: EXISTING COMPONENTS (Organizado por Módulos/Pastas)
# ==============================================================================
class CUSTOM_PT_game_existing_components(PropertyPanel, Panel):
    bl_label = "Existing Components"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "game"
    bl_idname = "GAME_PT_game_existing_components_custom"
    bl_options = {'DEFAULT_CLOSED'}

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

            if len(c.properties) == 1 and c.properties[0].name == "C_Icons":
                continue

            if c.show_expanded and len(c.properties) > 0:
                expanded = True
                collapsed = True
                prop_box = box.box().column()

                for prop in c.properties:
                    if prop.name[:8] == "C_Header":
                        row = prop_box.row()
                        expanded = prop.value
                        collapsed = prop.value
                        split = prop.name.split("/")
                        name = split[1] if len(split) > 1 else "HEADER"
                        icon = split[2] if len(split) > 2 else "FULLSCREEN"
                        row.scale_y = 1.2
                        try:
                            row.prop(prop, "value", text=name, toggle=1, icon=icon, emboss=1)
                        except:
                            prop_box.label(text="Header Error", icon="ERROR")
                        continue
                    elif prop.name[:10] == "C_Collapse" and collapsed:
                        collapsed = prop.value
                        split = prop.name.split("/")
                        name = " ".join(split[1]) if len(split) > 1 else "COLLAPSE"
                        icon = split[2] if len(split) > 2 else "MOD_BOOLEAN"
                        row = prop_box.row()
                        row.prop(prop, "value", text=name, toggle=1, emboss=0 if collapsed else 1, icon=icon)
                        row.scale_y = 0.9
                        sep = prop_box.row()
                        sep.prop(prop, "value", text=" ", toggle=1, emboss=1)
                        sep.scale_y = 0.2
                        sep.enabled = False
                        if collapsed: prop_box.separator()
                        continue
                    else:
                        if expanded and collapsed:
                            text = prop.name
                            try:
                                split = prop.name.split("/") if "@" in prop.name else [prop.name]
                                if len(split) > 1: text = split[1] + ":"
                                if not prop.name == "C_Icons":
                                    row = prop_box.row(align=True)
                                    row.label(text=text, icon="DOT")
                                    row.prop(prop, "value", text="")
                            except:
                                row = prop_box.row(align=True)
                                row.label(text=text)
                                row.prop(prop, "value", text="")