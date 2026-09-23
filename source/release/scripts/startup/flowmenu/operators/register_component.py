import bpy
from bpy.types import Operator
import importlib
import sys

from ..functions.get_modules import get_modules, get_modules_in_range
from ..functions.set_scripts_dir import set_scripts_dir


def _refresh_component_cache():
    try:
        importlib.invalidate_caches()
    except Exception:
        pass

    # Forca reimport de verdade: remove do cache do Python os modulos do
    # projeto (pacote "scripts"). Sem isso, o Blender/Range pode reaproveitar
    # a versao antiga (ou uma mistura antiga/nova) em memoria, e o issubclass()
    # contra KX_PythonComponent falha de forma intermitente apos editar os
    # arquivos ("X is not a KX_PythonComponent subclass").
    try:
        for mod_name in list(sys.modules.keys()):
            if mod_name == "scripts" or mod_name.startswith("scripts."):
                del sys.modules[mod_name]
    except Exception:
        pass

    try:
        get_modules(set_scripts_dir(), force_refresh=True)
    except Exception:
        pass


def _register_component_with_retry(component_name, attempts=3):
    last_error = None

    for _ in range(max(1, attempts)):
        try:
            _refresh_component_cache()
            bpy.ops.logic.python_component_register(component_name=component_name)
            return True, None
        except Exception as exc:
            last_error = exc

    return False, last_error


def _resolve_component(module_components, selected_class):
    """Resolve a stale FlowMenu selection without ever raising KeyError.

    The class collection is cached by the UI. After a script class is renamed,
    that collection can briefly retain the old name. If exactly one currently
    available name is a prefix extension/truncation of the old selection, it
    is safe to use it; otherwise the caller asks the user to refresh.
    """
    component = module_components.get(selected_class)
    if component is not None:
        return component

    matches = [component for name, component in module_components.items()
               if name.startswith(selected_class) or selected_class.startswith(name)]
    return matches[0] if len(matches) == 1 else None


class FLOWMENU_OT_register_component(Operator):
    bl_label = "Register Component"
    bl_idname = "wm.flowmenu_ot_register_component"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        scene = context.scene

        dict_modules = get_modules_in_range(scene)
        dict_modules.update(get_modules(set_scripts_dir(), force_refresh=True))

        obj = context.object
        game = obj.game
        wm = context.window_manager

        get_properties = wm

        collection_modules = get_properties.collection_modules
        collection_modules_active = get_properties.collection_modules_active

        collection_classes = get_properties.collection_classes
        collection_classes_active = get_properties.collection_classes_active

        module_select = collection_modules[collection_modules_active].value
        class_select = collection_classes[collection_classes_active].value

        module_components = dict_modules.get(module_select, {})
        register_component = _resolve_component(module_components, class_select)
        if register_component is None:
            self.report({"ERROR"},
                        "Component list is stale or ambiguous; refresh the module/class list and choose again.")
            return {"CANCELLED"}

        list_name_components = [f"{component.module}.{component.name}" for component in game.components]

        if register_component not in list_name_components:
            ok, err = _register_component_with_retry(register_component, attempts=3)
            if ok:
                self.report({"INFO"}, "Component '" + str(register_component).split(".")[1] + "' added!")
                return {"FINISHED"}

            self.report({"ERROR"}, f"Failed to add component '{register_component}': {err}")
            return {"CANCELLED"}

        self.report({"INFO"}, "Component '" + str(register_component).split(".")[1] + "' is already added.")
        return {"FINISHED"}
