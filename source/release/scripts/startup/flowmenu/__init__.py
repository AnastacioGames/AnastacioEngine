import bpy

# Imports normais...
from .properties.property_groups import (
    FLOWMENU_PG_header_enum,
    FLOWMENU_PG_expand_only_active,
    FLOWMENU_PG_collection_item,
)
from .properties.property_register import FLOWMENU_Properties_Register
from .ui_lists.modules_components import FLOWMENU_UL_modules_components
from .ui_lists.classes_components import FLOWMENU_UL_classes_components
from .ui_lists.game_components import FLOWMENU_UL_game_components
from .ui_lists.sensors import FLOWMENU_UL_sensors

from .operators.create_component import FLOWMENU_OT_create_component
from .operators.register_component import FLOWMENU_OT_register_component
from .operators.component_reload_new import (
    FLOWMENU_OT_python_component_reload_new,
    FLOWMENU_OT_reload_all_components,
    FLOWMENU_OT_refresh_components_list,
)
from .operators.open_logic_editor import FLOWMENU_OT_open_logic_editor
from .operators.open_external_editor import FLOWMENU_OT_open_external_editor
from .operators.init_addon import FLOWMENU_OT_init_addon

# Wizard
from .functions import create_component_wizard

# --- IMPORTAÇÃO DOS PAINÉIS CUSTOMIZADOS ---
from .custom_pt_components import (
    CUSTOM_PT_game_components,
    CUSTOM_PT_game_existing_components,
    CUSTOM_PT_game_object_components
)
from .custom_pt_properties import (
    OBJECT_OT_game_header_add, 
    CUSTOM_PT_game_properties,
    FLOWMENU_ListItem,
    FLOWMENU_UL_ComponentList,
    FLOWMENU_OT_component_list_refresh,
    FLOWMENU_OT_component_list_add
)
from .custom_pt_physics import (
    CUSTOM_PT_game_physics,
    CUSTOM_PT_game_collision_bounds,
    PHYSICS_PT_game_vehicle,
    PHYSICS_PT_game_vehicle_engine,
    PHYSICS_PT_game_vehicle_wheels,
    PHYSICS_PT_game_vehicle_gearbox,
    PHYSICS_PT_game_vehicle_component,
    OBJECT_OT_vehicle_add_player_component,
    OBJECT_OT_vehicle_set_drive_type
)
from .custom_pt_world import (
    CUSTOM_PT_game_context_world,
    CUSTOM_PT_game_world,
    CUSTOM_PT_game_environment_lighting,
    CUSTOM_PT_game_mist,
    CUSTOM_PT_game_weather,
    CUSTOM_PT_game_global_properties
)

classes = [
    FLOWMENU_PG_header_enum,
    FLOWMENU_PG_expand_only_active,
    FLOWMENU_PG_collection_item,
    FLOWMENU_UL_modules_components,
    FLOWMENU_UL_classes_components,
    FLOWMENU_UL_game_components,
    FLOWMENU_UL_sensors,
    FLOWMENU_OT_create_component,
    FLOWMENU_OT_register_component,
    FLOWMENU_OT_python_component_reload_new,
    FLOWMENU_OT_reload_all_components,
    FLOWMENU_OT_refresh_components_list,
    FLOWMENU_OT_open_logic_editor,
    FLOWMENU_OT_open_external_editor,
    FLOWMENU_OT_init_addon,

    # Wizard Classes
    create_component_wizard.FLOWMENU_OT_wizard_toggle,
    create_component_wizard.FLOWMENU_OT_create_advanced_component,

    # --- NOSSAS NOVAS CLASSES DE PAINEL ---
    OBJECT_OT_game_header_add,
    CUSTOM_PT_game_components,
    CUSTOM_PT_game_existing_components,
    CUSTOM_PT_game_object_components,
    CUSTOM_PT_game_properties,
    FLOWMENU_ListItem,
    FLOWMENU_UL_ComponentList,
    FLOWMENU_OT_component_list_refresh,
    FLOWMENU_OT_component_list_add,
    # --- NOSSAS NOVAS CLASSES DE FÍSICA ---
    CUSTOM_PT_game_physics,
    CUSTOM_PT_game_collision_bounds,
    PHYSICS_PT_game_vehicle,
    PHYSICS_PT_game_vehicle_engine,
    PHYSICS_PT_game_vehicle_wheels,
    PHYSICS_PT_game_vehicle_gearbox,
    PHYSICS_PT_game_vehicle_component,
    OBJECT_OT_vehicle_add_player_component,
    OBJECT_OT_vehicle_set_drive_type,
    # --- NOSSAS NOVAS CLASSES DO WORLD ---
    CUSTOM_PT_game_context_world,
    CUSTOM_PT_game_world,
    CUSTOM_PT_game_environment_lighting,
    CUSTOM_PT_game_mist,
    CUSTOM_PT_game_weather,
    CUSTOM_PT_game_global_properties,
]

properties = [FLOWMENU_Properties_Register]
addon_keymaps = []


def register():
    # 1. DESATIVA OS PAINÉIS ORIGINAIS DA RANGE ENGINE
    if hasattr(bpy.types, "GAME_PT_game_components"):
        try: bpy.utils.unregister_class(bpy.types.GAME_PT_game_components)
        except: pass
    
    if hasattr(bpy.types, "GAME_PT_game_properties"):
        try: bpy.utils.unregister_class(bpy.types.GAME_PT_game_properties)
        except: pass

    # 1.1 DESATIVA OS PAINÉIS ORIGINAIS DE FÍSICA
    if hasattr(bpy.types, "PHYSICS_PT_game_physics"):
        try: bpy.utils.unregister_class(bpy.types.PHYSICS_PT_game_physics)
        except: pass
    if hasattr(bpy.types, "PHYSICS_PT_game_collision_bounds"):
        try: bpy.utils.unregister_class(bpy.types.PHYSICS_PT_game_collision_bounds)
        except: pass

    # 1.2 DESATIVA OS PAINÉIS ORIGINAIS DO WORLD
    if hasattr(bpy.types, "WORLD_PT_game_context_world"):
        try: bpy.utils.unregister_class(bpy.types.WORLD_PT_game_context_world)
        except: pass
    if hasattr(bpy.types, "WORLD_PT_game_world"):
        try: bpy.utils.unregister_class(bpy.types.WORLD_PT_game_world)
        except: pass
    if hasattr(bpy.types, "WORLD_PT_game_environment_lighting"):
        try: bpy.utils.unregister_class(bpy.types.WORLD_PT_game_environment_lighting)
        except: pass
    if hasattr(bpy.types, "WORLD_PT_game_mist"):
        try: bpy.utils.unregister_class(bpy.types.WORLD_PT_game_mist)
        except: pass

    # 2. REGISTRA TODAS AS CLASSES DO ADD-ON (INCLUINDO AS NOVAS)
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print("[FlowMenu Error]: " + str(e))

    # 2.1 "CREATE OBSTACLE" POR ÚLTIMO NA ABA PHYSICS: painéis entram na ordem de registro,
    # então ele é re-registrado depois dos painéis de física acima (o addon de Ragdoll faz o mesmo).
    obstacle_panel = getattr(bpy.types, "PHYSICS_PT_game_obstacle_create", None)
    if obstacle_panel is not None:
        try:
            bpy.utils.unregister_class(obstacle_panel)
            bpy.utils.register_class(obstacle_panel)
        except Exception as e:
            print("[FlowMenu Error]: " + str(e))

    # 3. REMOVE O PAINEL NATIVO "CUSTOM PROPERTIES" DA ABA WORLD
    if hasattr(bpy.types, "WORLD_PT_custom_props"):
        try: bpy.utils.unregister_class(bpy.types.WORLD_PT_custom_props)
        except: pass

    for prt in properties:
        prt.pointer()

    # --- PROPRIEDADES DA CENA  ---
    bpy.types.Scene.flowmenu_show_wizard = bpy.props.BoolProperty(name="Show Component Creator", default=True)
    bpy.types.Scene.flowmenu_wizard_module = bpy.props.StringProperty(name="File Name", default="new_script")
    bpy.types.Scene.flowmenu_wizard_class = bpy.props.StringProperty(name="Class Name", default="NewComponent")
    bpy.types.Scene.flowmenu_component_list = bpy.props.CollectionProperty(type=FLOWMENU_ListItem)
    bpy.types.Scene.flowmenu_component_list_active = bpy.props.IntProperty(default=0)


    # Keymaps
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        kmi = km.keymap_items.new(FLOWMENU_OT_init_addon.bl_idname, type="Q", value="PRESS", alt=True)
        addon_keymaps.append((km, kmi))

        km = kc.keymaps.new(name="Logic Editor", space_type="LOGIC_EDITOR")
        kmi = km.keymap_items.new(FLOWMENU_OT_init_addon.bl_idname, type="Q", value="PRESS", alt=True)
        addon_keymaps.append((km, kmi))


def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    # Limpeza
    del bpy.types.Scene.flowmenu_show_wizard
    del bpy.types.Scene.flowmenu_wizard_module
    del bpy.types.Scene.flowmenu_wizard_class
    del bpy.types.Scene.flowmenu_component_list
    del bpy.types.Scene.flowmenu_component_list_active

    # 1. DESREGISTRA AS CLASSES DO NOSSO ADD-ON
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass

    for prt in properties:
        prt.delete()

    # 2. DEVOLVE OS PAINÉIS ORIGINAIS (não deveria rodar em uso normal: este
    # pacote é sempre ativo, não um addon opcional. Mantido por segurança.)
    from bl_ui.properties_game import GAME_PT_game_components, GAME_PT_game_properties
    from bl_ui.properties_game import PHYSICS_PT_game_physics, PHYSICS_PT_game_collision_bounds
    from bl_ui.properties_game import (
        WORLD_PT_game_context_world, WORLD_PT_game_world,
        WORLD_PT_game_environment_lighting, WORLD_PT_game_mist
    )
    try:
        bpy.utils.register_class(GAME_PT_game_components)
        bpy.utils.register_class(GAME_PT_game_properties)

        bpy.utils.register_class(PHYSICS_PT_game_physics)
        bpy.utils.register_class(PHYSICS_PT_game_collision_bounds)

        bpy.utils.register_class(WORLD_PT_game_context_world)
        bpy.utils.register_class(WORLD_PT_game_world)
        bpy.utils.register_class(WORLD_PT_game_environment_lighting)
        bpy.utils.register_class(WORLD_PT_game_mist)
    except:
        # Se já estiver registrado por outro motivo, não faz nada
        pass

    # Restaura o painel nativo "Custom Properties" da aba World
    from bl_ui.properties_world import WORLD_PT_custom_props
    try:
        bpy.utils.register_class(WORLD_PT_custom_props)
    except:
        pass
