# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

# Aba Input das Propriedades: o Input System (mapas KeyMapping/*.json ao lado do .range). Era uma secao das
# Preferencias, mas os mapas sao do projeto e vao no pacote Web/APK. Cada mapa abre e fecha; dentro dele, as
# acoes (Input Tables), e dentro da acao aberta, as ligacoes e processadores. O estado (mapa/acao selecionados,
# dicionario carregado, propriedades dinamicas) continua no WindowManager, como os operadores wm.input_* esperam.
# O desenho nao pode registrar propriedades (o RNA fica somente leitura): ele so marca update_binding_properties,
# e o handler scene_update_post cria as propriedades da acao aberta e faz o salvamento pedido por uma remocao.

import json
import os

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator, Panel

# Propriedades criadas no WindowManager para a acao aberta; apagadas quando outra acao carrega.
_dyn_props = []

# Processadores vetoriais: quantos campos (X, Y, Z) e de que tipo. "BOOL" ou ("FLOAT", min, max).
REPLICATE_TIMES = {"INVERTVALUES": 1, "INVERTVALUES2D": 2, "INVERTVALUES3D": 3,
                   "SCALEVALUES": 1, "SCALEVALUES2D": 2, "SCALEVALUES3D": 3,
                   "LERPVALUES": 1, "DEADZONE": 2}
PROCESSOR_TYPE = {"INVERTVALUES": "BOOL", "INVERTVALUES2D": "BOOL", "INVERTVALUES3D": "BOOL",
                  "SCALEVALUES": ("FLOAT", -10.0, 10.0), "SCALEVALUES2D": ("FLOAT", -10.0, 10.0),
                  "SCALEVALUES3D": ("FLOAT", -10.0, 10.0),
                  "LERPVALUES": ("FLOAT", 0.0, 1.0), "DEADZONE": ("FLOAT", 0.0, 1.0)}
ORDER_VECTOR = ["X", "Y", "Z"]

JOYSTICK_ITEMS = [
    ("0", "NONE", ""),
    ("1", "A", ""),
    ("2", "B", ""),
    ("3", "X", ""),
    ("4", "Y", ""),
    ("5", "BACK", ""),
    ("6", "GUIDE", ""),
    ("7", "START", ""),
    ("8", "LEFTSTICK", ""),
    ("9", "RIGHTSTICK", ""),
    ("10", "LEFTSHOULDER", ""),
    ("11", "RIGHTSHOULDER", ""),
    ("12", "PAD UP", ""),
    ("13", "PAD DOWN", ""),
    ("14", "PAD LEFT", ""),
    ("15", "PAD RIGHT", ""),
    # Special for the input system, with the exception of KX_PythonJoystick::JOYSTICK_EnumInputs
    ("100", "LEFT_JOY X", ""),
    ("101", "LEFT_JOY Y", ""),
    ("102", "RIGHT_JOY X", ""),
    ("103", "RIGHT_JOY Y", ""),
    ("104", "TRIGGER_LEFT", ""),
    ("105", "TRIGGER_RIGHT", ""),
]

CUSTOM_KEY_TIP = "Custom key, write the desired key is not being captured by the capture key operator"


def keymapping_path():
    return bpy.path.abspath("//KeyMapping/")


def redraw_input_areas():
    """Os operadores mudam arquivos e indices; as areas que desenham o Input System precisam redesenhar."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in {'PROPERTIES', 'USER_PREFERENCES'}:
                area.tag_redraw()


# ------------------------------------------------------------------------------------------------------------
# Propriedades dinamicas da acao aberta

def _add_prop(wm, prop_name, prop, value):
    setattr(bpy.types.WindowManager, prop_name, prop)
    if value is not None:
        try:
            setattr(wm, prop_name, value)
        except (TypeError, ValueError):
            # We don't know if the value is for KEYBOARD OR MOUSE, it's easier not to use the value if it doesn't work
            pass
    _dyn_props.append(prop_name)


def _gen_peripheral_enum(wm, name, value):
    _add_prop(wm, f"dynamic_enum_{name}", EnumProperty(
        name="Type",
        description=f"Dynamic enum property {name}",
        items=[
            ("KEYBOARD", "Keyboard", "Capture keyboard events"),
            ("MOUSE", "Mouse", "Capture mouse events"),
            ("JOYSTICK", "Joystick", "Capture joystick events (the on-screen touch controls are joystick 0)"),
        ]), value)


def _gen_joystick_index_enum(wm, name, value):
    _add_prop(wm, f"dynamic_enum_joystick_index_{name}", EnumProperty(
        name="Joystick Index",
        description="Specifies which control should get the inputs from, e.g: 0 = first control",
        items=[(str(i), str(i), "") for i in range(8)],
        default="0"), str(value))


def _gen_joystick_enum(wm, name, value):
    _add_prop(wm, f"dynamic_enum_joystick_{name}", EnumProperty(
        name="Joystick Table", description="", items=JOYSTICK_ITEMS, default="0"), value)


def _gen_capture_key(wm, name, value):
    wm["InputSystem_Keymap_Capture"][name] = wm.GetGameEngineKeyInverted.get(value)


def _gen_sensitivity(wm, name, value):
    _add_prop(wm, f"dynamic_float_sensitivity_{name}", FloatProperty(
        name="Value", description=f"Input Sensitivity {name}", min=0.0, max=1000.0), value)


def _gen_custom_key(wm, name):
    _add_prop(wm, f"dynamic_string_custom_key_{name}", StringProperty(
        name="Value",
        description="Custom Key, some keys that capture key cannot catch: CAPS_LOCK, SEMI_COLON = ; or : ..."), None)
    _add_prop(wm, f"dynamic_bool_{name}", BoolProperty(name="Value", description=CUSTOM_KEY_TIP), False)


def _gen_process_float(wm, name, min_value, max_value, value):
    _add_prop(wm, f"dynamic_float_{name}", FloatProperty(
        name="Value", description=f"Dynamic float property {name}", min=min_value, max=max_value), value)


def _gen_process_bool(wm, name, value):
    _add_prop(wm, f"dynamic_bool_{name}", BoolProperty(
        name="Value", description=f"Dynamic bool property {name}"), value == 1)


# ------------------------------------------------------------------------------------------------------------
# Sincronia com KeyMapping/: roda no desenho, como antes, quando um indice muda ou um operador pede

def _sync_maps(wm, path):
    if "input_maps_list" not in wm:
        wm["input_maps_list"] = []

    # Outro .range aberto: a lista e as selecoes antigas apontam para outra pasta.
    if wm.get("input_ui_path") != path:
        wm["input_ui_path"] = path
        wm["input_ui_map_open"] = False
        wm["input_ui_table_open"] = False
        wm.input_map_index = -1
        wm.last_input_map_index = -2

    if wm.last_input_map_index == wm.input_map_index:
        return
    # Called by Force Update
    if wm.input_map_index == -1:
        wm.input_map_index = 0
    wm.last_input_map_index = wm.input_map_index

    input_maps = wm.input_map_list
    input_maps.clear()
    files = sorted(f for f in os.listdir(path) if f.endswith(".json")) if os.path.isdir(path) else []
    wm["input_maps_list"] = files  # Store in windowmanager. Warning: IDPROP
    for input_map in files:
        input_maps.add().name = input_map[:-5]

    # In some cases we can delete the item from the list and the index will remain the same
    if wm.input_map_index > len(files) - 1:
        wm.input_map_index = 0
        wm.last_input_map_index = 0
    # A map just created (wm.input_map_save) opens
    new_map = wm.get("input_ui_select_map")
    if new_map in files:
        wm.input_map_index = wm.last_input_map_index = files.index(new_map)
        wm["input_ui_map_open"] = True
        wm["input_ui_table_open"] = False
    wm["input_ui_select_map"] = ""
    wm["input_table_dict"] = None
    wm.input_map_selected = ""
    wm.input_table_index = -1  # Force Update Input Table


def _sync_tables(wm, path):
    maps = wm["input_maps_list"]
    if maps and wm.last_input_table_index != wm.input_table_index:
        # Called by Force Update
        if wm.input_table_index == -1:
            wm.input_table_index = 0
        wm.last_input_table_index = wm.input_table_index
        wm.update_binding_properties = True

        wm.input_map_selected = maps[wm.input_map_index]
        with open(os.path.join(path, wm.input_map_selected), 'r') as file:
            tables = json.load(file)
        wm.input_table_list.clear()
        for table in tables:
            wm.input_table_list.add().name = table
        # An action just created (wm.input_table_save) opens
        new_table = wm.get("input_ui_select_table")
        if new_table in tables:
            wm.input_table_index = wm.last_input_table_index = list(tables).index(new_table)
            wm["input_ui_table_open"] = True
        wm["input_ui_select_table"] = ""
    elif not maps:
        wm.input_table_list.clear()

    # In some cases we can delete the item from the list and the index will remain the same
    if wm.input_table_index > len(wm.input_table_list) - 1:
        wm.input_table_index = 0
        wm.last_input_table_index = 0
    wm.input_table_selected_name = wm.input_table_list[wm.input_table_index].name if wm.input_table_list else ""


def _sync_bindings(wm, path):
    if not wm.input_table_list or not wm.update_binding_properties:
        return
    wm.update_binding_properties = False

    with open(os.path.join(path, wm.input_map_selected), 'r') as file:
        tables = json.load(file)
    # Save in windowmanager in json format because if not it converts the values into IDProps
    wm["input_table_dict"] = json.dumps(tables)
    table = tables[wm.input_table_selected_name]
    wm.binding_type_enum = table["Type"]
    wm.binding_control_type_enum = table["ControlType"]

    # Bindings and processors expanded state
    wm["input_bindings_expanded_values"] = {name: False for name in list(table["Bindings"]) + list(table["Processors"])}

    wm["InputSystem_Keymap_Capture"] = {}
    wm["InputSystem_Keymap_Sensitivity"] = {}

    # Delete all previously bind table enums
    for prop_name in _dyn_props:
        if hasattr(bpy.types.WindowManager, prop_name):
            delattr(bpy.types.WindowManager, prop_name)
    _dyn_props.clear()

    bindings = table["Bindings"]
    for bind, binds in bindings.items():
        peripheral = binds["PERIPHERALTYPE"]
        _gen_peripheral_enum(wm, bind, peripheral["TYPE"])
        _gen_joystick_index_enum(wm, bind, peripheral["INDEX"])
        _gen_sensitivity(wm, bind, peripheral["SENSITIVITY"])

        for bind_type in binds:
            if bind_type == "BINDING":
                value = binds[bind_type]["BUTTON"]
                _gen_capture_key(wm, bind, value)
                _gen_joystick_enum(wm, bind, value)
                _gen_custom_key(wm, bind)
            elif bind_type in ("COMPOSITEPADS", "COMPOSITEPADS3D"):
                order = ["UP", "DOWN", "LEFT", "RIGHT", "FORWARD", "BACKWARD"]
                for index in range(4 if bind_type == "COMPOSITEPADS" else 6):
                    key_name = bind + str(index)
                    value = binds[bind_type][order[index]]
                    _gen_capture_key(wm, key_name, value)
                    _gen_joystick_enum(wm, key_name, value)
                    _gen_custom_key(wm, key_name)

    # Generates values based on times a value is repeated, ex: vector(X,Y,Z) = 3 times ... same for the drawing
    for process, values in table["Processors"].items():
        process_type = PROCESSOR_TYPE[process]
        for index in range(REPLICATE_TIMES[process]):
            value = values[ORDER_VECTOR[index]]
            if process_type == "BOOL":
                _gen_process_bool(wm, process + str(index), value)
            else:
                _gen_process_float(wm, process + str(index), process_type[1], process_type[2], value)


def _save_bindings(wm):
    bpy.ops.wm.input_sys_save_binding('EXEC_DEFAULT', input_map_name=wm.input_map_selected,
                                      input_table_name=wm.input_table_selected_name,
                                      replicate_times=str(REPLICATE_TIMES), processor_type=str(PROCESSOR_TYPE),
                                      orderVector=str(ORDER_VECTOR))


@persistent
def input_sync_handler(scene):
    """Fora do desenho: carrega as ligacoes da acao aberta e salva depois de remover uma ligacao."""
    if not bpy.data.is_saved:
        return
    for wm in bpy.data.window_managers:
        if wm.force_save_bindings and wm.input_table_selected_name and wm.get("input_table_dict"):
            wm.force_save_bindings = False
            _save_bindings(wm)
            wm.update_binding_properties = True
        if wm.update_binding_properties and wm.input_table_list:
            _sync_bindings(wm, keymapping_path())
            redraw_input_areas()


def _bindings_ready(wm):
    table = wm.get("input_table_dict")
    if wm.update_binding_properties or not table:
        return False
    bindings = json.loads(table).get(wm.input_table_selected_name, {}).get("Bindings", {})
    return all(hasattr(wm, "dynamic_enum_" + bind) for bind in bindings)


# ------------------------------------------------------------------------------------------------------------
# Desenho

def _header(box, operator, text, is_open):
    """Linha de titulo: seta e nome a esquerda (clicar abre/fecha), botoes a direita. Devolve (toggle, botoes)."""
    row = box.row()
    left = row.row()
    left.alignment = 'LEFT'
    toggle = left.operator(operator, text=text, icon="TRIA_DOWN" if is_open else "TRIA_RIGHT", emboss=False)
    right = row.row(align=True)
    right.alignment = 'RIGHT'
    return toggle, right


def _draw_key_button(row, wm, key_name, is_mouse):
    button = row.operator("wm.input_capture_key", text=wm["InputSystem_Keymap_Capture"][key_name])
    button.key = key_name
    button.is_mouse = is_mouse


def _draw_binding(col, wm, bind, binds):
    box = col.box()
    expanded = wm["input_bindings_expanded_values"][bind]
    toggle, sub = _header(box, "wm.input_toggle_expand", bind, expanded)
    toggle.value = bind
    rename = sub.operator("wm.input_binding_rename", text="", icon="GREASEPENCIL", emboss=False)
    rename.input_map_name = wm.input_map_selected
    rename.input_table_name = wm.input_table_selected_name
    rename.input_binding_name = bind
    remove = sub.operator("wm.input_sys_remove_binding", text="", icon="ZOOMOUT", emboss=False)
    remove.input_table_name = wm.input_table_selected_name
    remove.input_name = bind
    remove.input_section_type = "Bindings"

    if not expanded:
        return

    col_bind = box.column(align=True)
    col_bind.prop(wm, f"dynamic_enum_{bind}", text="")
    peripheral = getattr(wm, f"dynamic_enum_{bind}")  # Get the peripheralType in realtime
    is_mouse = peripheral == "MOUSE"
    if peripheral == "JOYSTICK":
        col_bind.prop(wm, f"dynamic_enum_joystick_index_{bind}", text="Index")
    if peripheral in ("JOYSTICK", "MOUSE"):
        col_bind.prop(wm, f"dynamic_float_sensitivity_{bind}", text="Sensitivity")

    for bind_type in binds:
        if bind_type == "BINDING":
            row = box.row()
            row.label(text=" - Button:")
            row.prop(wm, f"dynamic_bool_{bind}", text="")  # Custom Key
            if getattr(wm, f"dynamic_bool_{bind}"):
                row.prop(wm, f"dynamic_string_custom_key_{bind}", text="")
            elif peripheral == "JOYSTICK":
                row.prop(wm, f"dynamic_enum_joystick_{bind}", text="")
            else:
                _draw_key_button(row, wm, bind, is_mouse)

        elif bind_type in ("COMPOSITEPADS", "COMPOSITEPADS3D"):
            count = 4 if bind_type == "COMPOSITEPADS" else 6
            labels = [" - Up Button:", " - Down Button:", " - Left Button:", " - Right Button:",
                      " - Forward Button:", " - Backward Button:"]

            # Inputs that use two hatch values OR mouse values (movement) take the opposite direction too
            blocked = []
            if peripheral in ("JOYSTICK", "MOUSE"):
                for index in range(count):
                    key_name = bind + str(index)
                    if peripheral == "JOYSTICK":
                        value = getattr(wm, f"dynamic_enum_joystick_{key_name}")
                    else:
                        value = wm["InputSystem_Keymap_Capture"][key_name]
                    if value in ("100", "101", "102", "103", "MOUSEX", "MOUSEY"):
                        blocked.append(index + (1 if index in (0, 2, 4) else -1))

            for index in range(count):
                key_name = bind + str(index)
                row = box.row()
                row.label(text=labels[index])
                if peripheral not in ("JOYSTICK", "MOUSE"):
                    row.prop(wm, f"dynamic_bool_{key_name}", text="")  # Custom Key
                    if getattr(wm, f"dynamic_bool_{key_name}"):
                        row.prop(wm, f"dynamic_string_custom_key_{key_name}", text="")
                    else:
                        _draw_key_button(row, wm, key_name, is_mouse)
                elif index not in blocked:
                    if peripheral == "JOYSTICK":
                        row.prop(wm, f"dynamic_enum_joystick_{key_name}", text="")
                    else:
                        _draw_key_button(row, wm, key_name, is_mouse)
                else:
                    row.label(text="Input in Use!", icon="SAVE_COPY")
                    if peripheral == "JOYSTICK":
                        if getattr(wm, f"dynamic_enum_joystick_{key_name}") != "0":
                            setattr(wm, f"dynamic_enum_joystick_{key_name}", "0")
                    elif wm["InputSystem_Keymap_Capture"][key_name] != "0":
                        wm["InputSystem_Keymap_Capture"][key_name] = "NOKEY"


def _draw_processor(col, wm, process):
    box = col.box()
    expanded = wm["input_bindings_expanded_values"][process]
    toggle, sub = _header(box, "wm.input_toggle_expand", process.lower(), expanded)
    toggle.value = process
    remove = sub.operator("wm.input_sys_remove_binding", text="", icon="ZOOMOUT", emboss=False)
    remove.input_table_name = wm.input_table_selected_name
    remove.input_name = process
    remove.input_section_type = "Processors"

    if not expanded:
        return
    process_type = PROCESSOR_TYPE[process]
    prefix = "dynamic_bool" if process_type == "BOOL" else "dynamic_float"
    for index in range(REPLICATE_TIMES[process]):
        row = box.row(align=True)
        row.label(text=ORDER_VECTOR[index])
        row.prop(wm, f"{prefix}_{process}{index}", text="")


def _draw_binding_properties(layout, wm):
    if not _bindings_ready(wm):
        wm.update_binding_properties = True  # the handler loads them on the next update
        layout.label(text="Loading...", icon="TIME")
        return
    table = json.loads(wm["input_table_dict"])[wm.input_table_selected_name] if wm.get("input_table_dict") else {}

    split = layout.split(factor=0.5)
    split.label(text="Return Type:")
    split.prop(wm, "binding_type_enum", text="")
    col = layout.column()
    if wm.binding_type_enum == "VALUE":
        row = col.row()
        row.label(text="Control Type")
        row.prop(wm, "binding_control_type_enum", text="")

    col.separator()
    row = col.row()
    row.label(text="Bindings:")
    add = row.operator("wm.input_binding_save", text="", icon='ZOOMIN', emboss=False)
    add.input_map_name = wm.input_map_selected
    add.input_table_name = wm.input_table_selected_name
    bindings = table.get("Bindings", {})
    if not bindings:
        col.label(text="No binding yet: click + to add a key or a gamepad button")
    for bind, binds in bindings.items():
        _draw_binding(col, wm, bind, binds)

    col.separator()
    row = col.row()
    row.label(text="Processors:")
    add = row.operator("wm.input_add_processor", text="", icon='ZOOMIN', emboss=False)
    add.input_map_name = wm.input_map_selected
    add.input_table_name = wm.input_table_selected_name
    processors = table.get("Processors", {})
    if not processors:
        col.label(text="Nothing")
    for process in processors:
        _draw_processor(col, wm, process)

    save = col.operator("wm.input_sys_save_binding", text="Save Binding Configuration", icon='SAVE_AS')
    save.input_map_name = wm.input_map_selected
    save.input_table_name = wm.input_table_selected_name
    save.replicate_times = str(REPLICATE_TIMES)
    save.processor_type = str(PROCESSOR_TYPE)
    save.orderVector = str(ORDER_VECTOR)


def _draw_tables(layout, wm):
    table_open = wm.get("input_ui_table_open", False)
    row = layout.row()
    row.label(text="Actions (Input Tables):", icon="COPY_ID")
    row.operator("wm.input_table_save", text="", icon='ZOOMIN', emboss=False).input_map_name = wm.input_map_selected

    if not wm.input_table_list:
        layout.label(text="No action yet: click + to add one (e.g. Jump, Move)", icon="INFO")
        return

    for index, item in enumerate(wm.input_table_list):
        is_open = table_open and index == wm.input_table_index
        # Botao largo como o "Physics" das Game Settings; os botoes da acao ficam colados a direita.
        row = layout.row(align=True)
        toggle = row.operator("wm.input_ui_expand", text=item.name, icon="TRIA_DOWN" if is_open else "TRIA_RIGHT")
        toggle.kind = 'TABLE'
        toggle.index = index
        rename = row.operator("wm.input_table_rename", text="", icon="GREASEPENCIL")
        rename.input_map_name = wm.input_map_selected
        rename.input_table_name = item.name
        if is_open:
            row.operator("wm.input_map_table", text="", icon='COPYDOWN')
            remove = row.operator("wm.input_table_remove", text="", icon='ZOOMOUT')
            remove.input_map_name = wm.input_map_selected
            remove.remove_active = item.name
            _draw_binding_properties(layout.box(), wm)


class INPUT_OT_expand(Operator):
    """Open or close this item"""
    bl_idname = "wm.input_ui_expand"
    bl_label = "Open/Close"
    bl_options = {'INTERNAL'}

    kind: EnumProperty(items=(('MAP', "Map", ""), ('TABLE', "Table", "")), options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})

    def execute(self, context):
        wm = context.window_manager
        if self.kind == 'MAP':
            if self.index == wm.input_map_index:
                wm["input_ui_map_open"] = not wm.get("input_ui_map_open", False)
            else:
                wm.input_map_index = self.index  # the draw loads the map and its actions
                wm["input_ui_map_open"] = True
                wm["input_ui_table_open"] = False
        else:
            if self.index == wm.input_table_index:
                wm["input_ui_table_open"] = not wm.get("input_ui_table_open", False)
            else:
                wm.input_table_index = self.index  # the draw loads the bindings
                wm["input_ui_table_open"] = True
        redraw_input_areas()
        return {'FINISHED'}


class InputButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "input"


class INPUT_PT_maps(InputButtonsPanel, Panel):
    bl_label = "Input Maps"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        if not bpy.data.is_saved:
            box = layout.box()
            box.label(text="Save the .range first to use Input System!", icon="ERROR")
            box.label(text="The maps are saved in the KeyMapping folder next to the .range", icon="INFO")
            return

        path = keymapping_path()
        _sync_maps(wm, path)
        _sync_tables(wm, path)

        row = layout.row()
        row.label(text="Maps are saved in KeyMapping/ next to the .range", icon="INFO")
        row.operator("wm.input_map_save", text="", icon='ZOOMIN')

        if not wm.input_map_list:
            layout.label(text="No input map yet: click + to create one", icon="INFO")
            return

        map_open = wm.get("input_ui_map_open", False)
        for index, item in enumerate(wm.input_map_list):
            is_open = map_open and index == wm.input_map_index
            box = layout.box()
            toggle, sub = _header(box, "wm.input_ui_expand", item.name, is_open)
            toggle.kind = 'MAP'
            toggle.index = index
            sub.operator("wm.input_map_rename", text="", icon="GREASEPENCIL", emboss=False).input_map_name = item.name
            if is_open:
                sub.operator("wm.input_map_copy", text="", icon='COPYDOWN', emboss=False)
                sub.operator("wm.input_map_remove", text="", icon='ZOOMOUT',
                             emboss=False).remove_active = item.name + ".json"
                _draw_tables(box, wm)


class INPUT_PT_touch(InputButtonsPanel, Panel):
    bl_label = "On-screen Controls (Web/Android)"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        web = getattr(context.scene, "range_web", None)
        if web is None:
            return
        layout.prop(web, "touch_layout")
        if web.touch_layout != 'NONE':
            layout.prop(web, "touch_stick")
        layout.label(text="The on-screen controls are joystick 0: bind actions to Joystick, index 0", icon="INFO")

        path = keymapping_path()
        if not bpy.data.is_saved or not os.path.isdir(path):
            return
        try:
            from range_web import touch
        except ImportError:
            return
        maps = {}
        for name in sorted(os.listdir(path)):
            if name.endswith(".json"):
                try:
                    with open(os.path.join(path, name), 'r') as file:
                        maps[name[:-5]] = json.load(file)
                except (OSError, ValueError):
                    continue
        findings = touch.check_input_maps(web.touch_layout.lower(), maps)
        if not findings:
            if maps:
                layout.label(text="Every action with bindings can be pressed on the touch screen", icon="FILE_TICK")
            return
        box = layout.box()
        box.label(text="Actions the touch layout does not press (WEB-INPUT-001):", icon="ERROR")
        for finding in findings:
            box.label(text=finding.location["chain"])


classes = (
    INPUT_OT_expand,
    INPUT_PT_maps,
    INPUT_PT_touch,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
