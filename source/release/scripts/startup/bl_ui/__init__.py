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

# note, properties_animviz is a helper module only.

# support reloading sub-modules
if "bpy" in locals():
    from importlib import reload
    _modules_loaded[:] = [reload(val) for val in _modules_loaded]
    del reload

_modules = [
    "properties_animviz",
    "properties_constraint",
    "properties_data_armature",
    "properties_data_bone",
    "properties_data_camera",
    "properties_data_curve",
    "properties_data_empty",
    "properties_data_lamp",
    "properties_data_lattice",
    "properties_data_mesh",
    "properties_data_metaball",
    "properties_data_modifier",
    "properties_data_speaker",
    "properties_game",
    "properties_mask_common",
    "properties_material",
    "properties_object",
    "properties_paint_common",
    "properties_grease_pencil_common",
    "properties_particle",
    "properties_physics_cloth",
    "properties_physics_common",
    "properties_physics_dynamicpaint",
    "properties_physics_field",
    "properties_physics_fluid",
    "properties_physics_rigidbody",
    "properties_physics_rigidbody_constraint",
    "properties_physics_smoke",
    "properties_physics_softbody",
    "properties_render",
    "properties_render_layer",
    "properties_scene",
    "properties_cutscene",
    "properties_web",
    "properties_android",
    "properties_texture",
    "properties_world",
    "space_clip",
    "space_console",
    "space_dopesheet",
    "space_filebrowser",
    "space_graph",
    "space_image",
    "space_info",
    "space_logic",
    "space_nla",
    "space_node",
    "space_outliner",
    "space_properties",
    "space_sequencer",
    "space_text",
    "space_time",
    "space_userpref",
    "space_view3d",
    "space_view3d_toolbar",
]

import bpy

if bpy.app.build_options.freestyle:
    _modules.append("properties_freestyle")

__import__(name=__name__, fromlist=_modules)
_namespace = globals()
_modules_loaded = [_namespace[name] for name in _modules]
del _namespace

def register():
    from bpy.utils import register_class
    for mod in _modules_loaded:
        for cls in mod.classes:
            register_class(cls)

    # space_userprefs.py
    from bpy.props import (
        EnumProperty,
        BoolProperty,
        StringProperty,
        IntProperty,
        CollectionProperty,
        PointerProperty,
    )
    from bpy.types import WindowManager

    def addon_filter_items(self, context):
        import addon_utils

        items = [
            ('All', "All", "All Add-ons"),
            ('User', "User", "All Add-ons Installed by User"),
            ('Enabled', "Enabled", "All Enabled Add-ons"),
            ('Disabled', "Disabled", "All Disabled Add-ons"),
        ]

        items_unique = set()

        for mod in addon_utils.modules(refresh=False):
            info = addon_utils.module_bl_info(mod)
            items_unique.add(info["category"])

        items.extend([(cat, cat, "") for cat in sorted(items_unique)])
        return items

    WindowManager.addon_search = StringProperty(
        name="Search",
        description="Search within the selected filter",
        options={'TEXTEDIT_UPDATE'},
    )
    WindowManager.addon_filter = EnumProperty(
        items=addon_filter_items,
        name="Category",
        description="Filter add-ons by category",
    )

    WindowManager.addon_support = EnumProperty(
        items=[
            ('OFFICIAL', "Official", "Officially supported"),
            ('COMMUNITY', "Community", "Maintained by community developers"),
            ('TESTING', "Testing", "Newly contributed scripts (excluded from release builds)")
        ],
        name="Support",
        description="Display support level",
        default={'OFFICIAL', 'COMMUNITY'},
        options={'ENUM_FLAG'},
    )
    # done...
    
    ########### Range Input System ###########
    blender_to_ge_conversion_table = {
        "NOKEY": "0",

        # BEGINWIN
        "WINRESIZE": "1", "WINCLOSE": "2", "WINQUIT": "3",
        # ENDWIN

        # BEGINKEY
        "RET": "7", "SPACE": "8", "NUMPAD_ASTERIX": "9", "COMMA": "10", "MINUS": "11", "PERIOD": "12",
        "ZERO": "13", "ONE": "14", "TWO": "15", "THREE": "16", "FOUR": "17", "FIVE": "18", "SIX": "19", "SEVEN": "20",
        "EIGHT": "21", "NINE": "22",
        "A": "23", "B": "24", "C": "25", "D": "26", "E": "27", "F": "28", "G": "29", "H": "30", "I": "31", "J": "32",
        "K": "33", "L": "34", "M": "35", "N": "36", "O": "37", "P": "38", "Q": "39", "R": "40", "S": "41", "T": "42",
        "U": "43", "V": "44", "W": "45", "X": "46", "Y": "47", "Z": "48",
        "CAPS_LOCK": "49",
        "LEFT_CTRL": "50", "LEFT_ALT": "51", "RIGHT_ALT": "52", "RIGHT_CTRL": "53", "RIGHT_SHIFT": "54", "LEFT_SHIFT": "55",
        "ESC": "56", "TAB": "57",
        "LINE_FEED": "58", "BACK_SPACE": "59", "DEL": "60", "SEMI_COLON": "61",
        "QUOTE": "62", "ACCENT_GRAVE": "63",
        "SLASH": "64", "BACK_SLASH": "65", "EQUAL": "66", "LEFT_BRACKET": "67", "RIGHT_BRACKET": "68",
        "LEFT_ARROW": "69", "DOWN_ARROW": "70", "RIGHT_ARROW": "71", "UP_ARROW": "72",
        "NUMPAD_2": "73", "NUMPAD_4": "74", "NUMPAD_6": "75", "NUMPAD_8": "76",
        "NUMPAD_1": "77", "NUMPAD_3": "78", "NUMPAD_5": "79", "NUMPAD_7": "80", "NUMPAD_9": "81",
        "NUMPAD_PERIOD": "82", "NUMPAD_SLASH": "83",
        "NUMPAD_0": "84", "NUMPAD_MINUS": "85", "NUMPAD_ENTER": "86", "NUMPAD_PLUS": "87",
        "F1": "88", "F2": "89", "F3": "90", "F4": "91", "F5": "92", "F6": "93", "F7": "94", "F8": "95", "F9": "96",
        "F10": "97", "F11": "98", "F12": "99", "F13": "100", "F14": "101", "F15": "102", "F16": "103", "F17": "104",
        "F18": "105", "F19": "106",
        "OSKEY": "107",
        "PAUSE": "108", "INSERT": "109", "HOME": "110", "PAGEUP": "111", "PAGEDOWN": "112", "END": "113",
        # BEGINMOUSE
        # BEGINMOUSEBUTTONS
        "LEFTMOUSE": "116", "MIDDLEMOUSE": "117", "RIGHTMOUSE": "118", "BUTTON4MOUSE": "119", "BUTTON5MOUSE": "120",
        "BUTTON6MOUSE": "121", "BUTTON7MOUSE": "122",
        # ENDMOUSEBUTTONS
        "WHEELUPMOUSE": "124", "WHEELDOWNMOUSE": "125",
        "MOUSEX": "126", "MOUSEY": "127"
        # ENDMOUSE
    }
        
    def GetGameEngineKey(self, input_key: str):
        return blender_to_ge_conversion_table.get(input_key, "0")
    
    WindowManager.GetGameEngineKey = GetGameEngineKey
    WindowManager.GetGameEngineKeyInverted = {v: k for k, v in blender_to_ge_conversion_table.items()}
    
    WindowManager.input_map_list = CollectionProperty(
        name="Input Maps List",
        type=bpy.types.PropertyGroup
    )
    
    WindowManager.input_map_selected = StringProperty(name="Selected Map", default="")
    
    WindowManager.input_map_index = IntProperty(default=-1)
    WindowManager.last_input_map_index = IntProperty(default=0) # For Update Input Map
    
    WindowManager.input_table_list = CollectionProperty(
        name="Input Table List",
        type=bpy.types.PropertyGroup
    )
    
    WindowManager.input_table_index = IntProperty(
        default=0
    )
    
    WindowManager.last_input_table_index = IntProperty(default=0) # For Update Input Table Properties
    WindowManager.input_table_selected_name = StringProperty(name="Selected Table", default="")
    
    WindowManager.update_binding_properties = BoolProperty(default=False) # For Update Binding Properties Section
    WindowManager.force_save_bindings = BoolProperty(default=False) # Force to save the binds
    
    # Binding Types
    WindowManager.binding_type_enum = EnumProperty(
        name="Return Type",
        description="Return type",
        items=[
            ("BUTTON", "Button", "Binding Button mode, will return True or False value"),
            ("VALUE", "Value", "Binding Value mode, will return a value from 1 to -1"),
        ]
    )
    # Binding Control Types
    WindowManager.binding_control_type_enum = EnumProperty(
        name="Binding Control Type",
        description="Binding Control type",
        items=[
            ("VECTOR1D", "Vector1D", "A One-Dimensional Vector"),
            ("VECTOR2D", "Vector2D", "A Two-Dimensional Vector"),
            ("VECTOR3D", "Vector3D", "A Three-Dimensional Vector")
        ]
    )
    
    ########### End Range Input System ###########

    ########### RangeArmor Export Presets ###########
    from bpy.types import Scene
    from . import properties_scene

    Scene.rangearmor_export = PointerProperty(type=properties_scene.RangeArmorExportSettings)
    ########### End RangeArmor Export Presets ###########

    ########### Range Web Profile ###########
    from . import properties_web
    from range_web import translations as range_web_translations

    Scene.range_web = PointerProperty(type=properties_web.RangeWebSettings)
    range_web_translations.register()

    from . import properties_android
    Scene.range_android = PointerProperty(type=properties_android.RangeAndroidSettings)
    # Senha da chave do release: no WindowManager para nunca ir para o .blend.
    WindowManager.range_android_password = StringProperty(
        name="Key password",
        description="Password of the signing key; kept only while the editor is open, never saved in the file",
        subtype='PASSWORD',
        options={'SKIP_SAVE'},
    )
    ########### End Range Web Profile ###########


def unregister():
    from bpy.types import Scene

    if hasattr(Scene, "range_android"):
        del Scene.range_android
        del bpy.types.WindowManager.range_android_password

    if hasattr(Scene, "range_web"):
        from range_web import translations as range_web_translations
        range_web_translations.unregister()
        del Scene.range_web

    if hasattr(Scene, "rangearmor_export"):
        del Scene.rangearmor_export

    from bpy.utils import unregister_class
    for mod in reversed(_modules_loaded):
        for cls in reversed(mod.classes):
            if getattr(cls, "is_registered", False):
                unregister_class(cls)

# Define a default UIList, when a list does not need any custom drawing...
# Keep in sync with its #defined name in UI_interface.h


class UI_UL_list(bpy.types.UIList):
    # These are common filtering or ordering operations (same as the default C ones!).
    @staticmethod
    def filter_items_by_name(pattern, bitflag, items, propname="name", flags=None, reverse=False):
        """
        Set FILTER_ITEM for items which name matches filter_name one (case-insensitive).
        pattern is the filtering pattern.
        propname is the name of the string property to use for filtering.
        flags must be a list of integers the same length as items, or None!
        return a list of flags (based on given flags if not None),
        or an empty list if no flags were given and no filtering has been done.
        """
        import fnmatch

        if not pattern or not items:  # Empty pattern or list = no filtering!
            return flags or []

        if flags is None:
            flags = [0] * len(items)

        # Implicitly add heading/trailing wildcards.
        pattern = "*" + pattern + "*"

        for i, item in enumerate(items):
            name = getattr(item, propname, None)
            # This is similar to a logical xor
            if bool(name and fnmatch.fnmatchcase(name, pattern)) is not bool(reverse):
                flags[i] |= bitflag
        return flags

    @staticmethod
    def sort_items_helper(sort_data, key, reverse=False):
        """
        Common sorting utility. Returns a neworder list mapping org_idx -> new_idx.
        sort_data must be an (unordered) list of tuples [(org_idx, ...), (org_idx, ...), ...].
        key must be the same kind of callable you would use for sorted() builtin function.
        reverse will reverse the sorting!
        """
        sort_data.sort(key=key, reverse=reverse)
        neworder = [None] * len(sort_data)
        for newidx, (orgidx, *_) in enumerate(sort_data):
            neworder[orgidx] = newidx
        return neworder

    @classmethod
    def sort_items_by_name(cls, items, propname="name"):
        """
        Re-order items using their names (case-insensitive).
        propname is the name of the string property to use for sorting.
        return a list mapping org_idx -> new_idx,
               or an empty list if no sorting has been done.
        """
        _sort = [(idx, getattr(it, propname, "")) for idx, it in enumerate(items)]
        return cls.sort_items_helper(_sort, lambda e: e[1].lower())


bpy.utils.register_class(UI_UL_list)
