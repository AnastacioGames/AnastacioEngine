import bpy
from bpy.types import Panel, Operator, UIList, PropertyGroup
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty
from bpy.app.translations import pgettext_tip as tip_

# Cache para a lista de ícones (evita recriar a lista toda vez e deixar a UI lenta)
_icon_enum_items = None

def get_icon_enum_items(self, context):
    global _icon_enum_items
    if _icon_enum_items is None:
        # Extrai a lista de ícones disponíveis no Blender (mesma lógica do development_icon_get.py)
        icons = bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys()
        _icon_enum_items = []
        for i, icon in enumerate(icons):
            if icon != 'NONE':
                # Colocar o nome do ícone no 2º parâmetro permite buscar digitando
                _icon_enum_items.append((icon, icon, "", icon, i))
    return _icon_enum_items

# ==============================================================================
# OPERATOR: ADD HEADER 
# ==============================================================================
class OBJECT_OT_game_header_add(Operator):
    bl_idname = "object.game_header_add"
    bl_label = "Add Header"
    bl_description = "Create a Bool Game Property in the format C_Header/Title/Icon"

    title: StringProperty(name="Title", default="Header")
    icon: EnumProperty(name="Icon", items=get_icon_enum_items)
    expanded: BoolProperty(name="Expanded", default=True)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "title")
        # O EnumProperty já desenha os ícones sozinho. Passar icon=self.icon gera conflitos na Range Engine!
        layout.prop(self, "icon")
        layout.prop(self, "expanded")

    def execute(self, context):
        ob = context.active_object
        if not ob or not getattr(ob, "game", None):
            self.report({'WARNING'}, tip_("Active object has no 'game'."))
            return {'CANCELLED'}

        gp = ob.game.properties
        try:
            icon = self.icon.strip() or "GRIP"
            name = "C_Header/{}/{}".format(self.title, icon)
            bpy.ops.object.game_property_new(name=name, type='BOOL')
        except Exception as e:
            self.report({'ERROR'}, tip_("Failed to create property: %s") % e)
            return {'CANCELLED'}

        try:
            new_prop = gp[-1]
            new_prop.value = bool(self.expanded)
        except Exception:
            pass

        return {'FINISHED'}

    def invoke(self, context, event):
        # Define o ícone padrão via código, já que um Enum dinâmico não aceita 'default'
        try:
            self.icon = "GRIP"
        except Exception:
            pass
        return context.window_manager.invoke_props_dialog(self)


# ==============================================================================
# PAINEL CUSTOMIZADO: PROPERTIES 
# ==============================================================================
class CUSTOM_PT_game_properties(Panel):
    bl_label = "Object's Properties"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "game"
    bl_idname = "GAME_PT_game_properties_custom"
    bl_order = 1000

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.game

    def _is_header(self, name):
        return name.startswith("C_Header/")

    def _split_tag(self, name, default_title, default_icon):
        parts = name.split("/")
        title = parts[1] if len(parts) > 1 else default_title
        icon = parts[2] if len(parts) > 2 else default_icon
        return title, icon

    def _draw_prop_row(self, parent, prop, index):
        box = parent.box()
        row = box.row(align=True)
        row.prop(prop, "name", text="")
        row.prop(prop, "type", text="")
        row.prop(prop, "value", text="")
        row.prop(prop, "show_debug", text="", toggle=True, icon='INFO')

        sub = row.row(align=True)
        mv = sub.operator("object.game_property_move", text="", icon='TRIA_UP')
        mv.index = index
        mv.direction = 'UP'
        mv = sub.operator("object.game_property_move", text="", icon='TRIA_DOWN')
        mv.index = index
        mv.direction = 'DOWN'

        sub.operator("object.game_property_remove", text="", icon='X').index = index

    def draw(self, context):
        layout = self.layout
        ob = context.active_object
        game = ob.game
        is_font = (ob.type == 'FONT')

        box = layout.box()
        row = box.row(align=True)
        row.operator("object.game_header_add", text="Add Header", icon='PLUS')
        op = row.operator("object.game_property_new", text="Add Game Property", icon='PLUS')
        op.name = ""

        if is_font: pass

        props_list = list(game.properties)
        has_any_header = any(self._is_header(p.name) for p in props_list)

        if not has_any_header:
            for i, prop in enumerate(props_list):
                if is_font and prop.name in {"Text", "Text-Res"}: continue
                self._draw_prop_row(layout, prop, i)
            return

        current_box = None
        current_col = None
        group_open = True

        i = 0
        while i < len(props_list):
            prop = props_list[i]
            if is_font and prop.name in {"Text", "Text-Res"}:
                i += 1
                continue

            if self._is_header(prop.name):
                current_box = layout.box()
                header_row = current_box.row(align=True)
                title, icon = self._split_tag(prop.name, "HEADER", "FULLSCREEN")
                header_row.prop(prop, "value", text=title, toggle=True, icon=icon)

                sub = header_row.row(align=True)
                mv = sub.operator("object.game_property_move", text="", icon='TRIA_UP')
                mv.index = i; mv.direction = 'UP'
                mv = sub.operator("object.game_property_move", text="", icon='TRIA_DOWN')
                mv.index = i; mv.direction = 'DOWN'
                header_row.operator("object.game_property_remove", text="", icon='X').index = i

                current_col = current_box.column(align=True)
                group_open = bool(prop.value)
                i += 1
                continue

            if current_col is None:
                current_box = layout.box()
                ungrouped_header = current_box.row()
                ungrouped_header.label(text="Ungrouped Properties", icon="LINENUMBERS_ON")
                current_col = current_box.column(align=True)
                group_open = True

            if group_open:
                self._draw_prop_row(current_col, prop, i)
            i += 1

# ==============================================================================
# PAINEL CUSTOMIZADO: EXISTING COMPONENTS (Portado do Component Helper)
# ==============================================================================
class FLOWMENU_ListItem(PropertyGroup):
    name = StringProperty(name="Component", default="")

class FLOWMENU_UL_ComponentList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        parts = item.name.split(".")
        classNm = parts[-1] if len(parts) > 0 else item.name
        script = ".".join(parts[:-1]) + ".py" if len(parts) > 1 else "In .Range File"
        
        layout.label(text=classNm, translate=False, icon="GAME")
        layout.label(text=script, translate=False, icon="TEXT")

class FLOWMENU_OT_component_list_refresh(Operator):
    bl_idname = "wm.flowmenu_component_list_refresh"
    bl_label = "Refresh the Component List"
    bl_description = "Searches internal and external files for Python Components"
    
    def execute(self, context):
        scene = context.scene
        wm = context.window_manager
        
        try:
            from .functions.get_modules import get_modules, get_modules_in_range
            from .functions.set_scripts_dir import set_scripts_dir
            
            dict_modules = get_modules_in_range(scene)
            dict_modules.update(get_modules(set_scripts_dir()))
            
            wm.collection_modules.clear()
            for module in dict_modules:
                item = wm.collection_modules.add()
                item.value = module

            if len(wm.collection_modules) > 0 and wm.collection_modules_active >= len(wm.collection_modules):
                wm.collection_modules_active = 0
            
            # Força a atualização da lista de classes caso o índice não seja alterado
            # (Ex: continuou no 0, então o callback de update não dispara sozinho)
            from .functions.get_modules import update_classes_list
            wm["last_module_index"] = -1  # Força a liberação da trava
            wm.collection_classes.clear()
            update_classes_list(None, context)
                    
        except ImportError:
            pass
                                
        return {"FINISHED"}

class FLOWMENU_OT_component_list_add(Operator):
    bl_idname = "wm.flowmenu_component_list_add"
    bl_label = "Add Selected Component"
    bl_description = "Adds the selected component to the active object"
    
    def execute(self, context):
        wm = context.window_manager
        scene = context.scene
        
        idx_mod = wm.collection_modules_active
        idx_class = wm.collection_classes_active
        
        if len(wm.collection_modules) > idx_mod and len(wm.collection_classes) > idx_class:
            mod_name = wm.collection_modules[idx_mod].value
            cls_name = wm.collection_classes[idx_class].value
            
            try:
                from .functions.get_modules import get_modules, get_modules_in_range
                from .functions.set_scripts_dir import set_scripts_dir
                
                dict_modules = get_modules_in_range(scene)
                dict_modules.update(get_modules(set_scripts_dir()))
                
                if mod_name in dict_modules and cls_name in dict_modules[mod_name]:
                    nm = dict_modules[mod_name][cls_name]
                    
                    import sys
                    import bpy
                    blend_dir = bpy.path.abspath("//")
                    if blend_dir and blend_dir not in sys.path:
                        sys.path.append(blend_dir)
                        
                    bpy.ops.logic.python_component_register(component_name=nm)
                else:
                    self.report({'ERROR'}, tip_("Component path not found."))
            except Exception as e:
                self.report({'ERROR'}, tip_("Script error: check the console for missing imports or syntax errors."))
                print("[Component Manager] Failed to register: {}".format(e))
        else:
            self.report({'WARNING'}, tip_("No component selected or list is empty."))
            
        return {"FINISHED"}