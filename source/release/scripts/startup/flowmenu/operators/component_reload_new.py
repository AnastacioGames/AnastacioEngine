import bpy
from bpy.types import Operator
import importlib
import sys

from ..functions.get_modules import get_modules
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


def _reload_component_with_retry(component_index, component_name, attempts=3):
    """Reload in place so a failed script never removes another component."""
    last_error = None

    for attempt in range(max(1, attempts)):
        try:
            _refresh_component_cache()
            result = bpy.ops.logic.python_component_reload(index=component_index)
        except Exception as exc:
            last_error = exc
        else:
            if "FINISHED" in result:
                return True, None
            last_error = "native reload returned {}".format(result)

        if attempt < attempts - 1:
            _refresh_component_cache()

    return False, last_error


# ==============================================================================
# OPERATOR 1: RECARREGAR COMPONENTE ÚNICO
# ==============================================================================
class FLOWMENU_OT_python_component_reload_new(Operator):
    bl_label = "Python Component Reload New"
    bl_idname = "wm.flowmenu_python_component_reload_new"
    bl_description = "Reloads only the active component of the selected object"

    def execute(self, context):
        wm = context.window_manager

        # Proteção: Garante que há um objeto e configurações de jogo
        if not context.object or not hasattr(context.object, "game"):
            self.report({'WARNING'}, "No active game object selected.")
            return {"CANCELLED"}

        game = context.object.game

        try:
            # Pega o índice seguro
            component_active = wm.collection_components_active

            # Verifica se o índice ainda é válido (caso tenha deletado algo antes)
            if component_active < len(game.components):
                comp = game.components[component_active]

                # Reconstrói o caminho do import: modulo.classe
                get_component = "{}.{}".format(comp.module, comp.name)

                # Remove e registra novamente com retry para tolerar reload parcial de imports.
                ok, err = _reload_component_with_retry(component_active, get_component, attempts=3)
                if ok:
                    self.report({'INFO'}, "Reloaded: {}".format(get_component))
                else:
                    self.report({'ERROR'}, "Reload failed: {} | {}".format(get_component, err))
            else:
                self.report({'WARNING'}, "Invalid component selection.")

        except Exception as e:
            self.report({'ERROR'}, "Error reloading component: {}".format(e))
            print("[Reload Error] {}".format(e))

        return {"FINISHED"}


# ==============================================================================
# OPERATOR 2: RECARREGAR TUDO (RELOAD ALL)
# ==============================================================================
class FLOWMENU_OT_reload_all_components(Operator):
    bl_label = "Reload All Components"
    bl_idname = "wm.flowmenu_reload_all_components"
    bl_description = "Reloads all Python components in the entire scene"

    def execute(self, context):
        try:
            # Guarda o objeto ativo original para restaurar no final
            act = context.scene.objects.active
            count = 0

            # Itera sobre todos os objetos da cena
            for obj in context.scene.objects:
                # Otimização: Pula objetos que não são de jogo ou não têm componentes
                if not hasattr(obj, "game"): continue
                if len(obj.game.components) == 0: continue

                # BGE exige que o objeto esteja ativo para operar os componentes logic
                flag = obj.select
                obj.select = True
                context.scene.objects.active = obj

                # Itera sobre os componentes do objeto
                original_components = ["{}.{}".format(comp.module, comp.name) for comp in obj.game.components]
                for comp_name in reversed(original_components):
                    try:
                        current_names = ["{}.{}".format(comp.module, comp.name) for comp in obj.game.components]
                        if comp_name not in current_names:
                            continue

                        comp_index = current_names.index(comp_name)
                        ok, err = _reload_component_with_retry(comp_index, comp_name, attempts=3)
                        if not ok:
                            print("[!] Reload failed in object '{}': {} | {}".format(obj.name, comp_name, err))
                            continue
                        count += 1
                    except RuntimeError:
                        # Erros de runtime (script quebrado) não devem parar o loop
                        print("[!] Script Error in object '{}': {}".format(obj.name, comp_name))
                        continue
                    except Exception as e:
                        print("[!] Generic Error in '{}': {}".format(obj.name, e))
                        continue

                # Restaura estado de seleção
                obj.select = flag

            # Restaura o objeto ativo original
            context.scene.objects.active = act
            self.report({"INFO"}, "Reloaded {} components. Check console for details.".format(count))

        except Exception as e:
            print("CRITICAL RELOAD ERROR: {}".format(e))
            self.report({"ERROR"}, "Critical Error: {}".format(e))

        return {"FINISHED"}


# ==============================================================================
# OPERATOR 3: ATUALIZAR LISTA INTERNA (.Range Files)
# ==============================================================================
class FLOWMENU_OT_refresh_components_list(Operator):
    bl_label = "Refresh Component List"
    bl_idname = "wm.flowmenu_components_refresh"
    bl_description = "Updates the list of internal components found in text files"

    def execute(self, context):
        scene = context.scene
        from ..functions.get_modules import get_modules_in_range

        components = get_modules_in_range(scene).get("In .Range File", {})
        collection = scene.flowmenu_component_list
        collection.clear()
        for component_name in components.values():
            item = collection.add()
            item.name = component_name
        scene.flowmenu_component_list_active = 0

        return {"FINISHED"}
