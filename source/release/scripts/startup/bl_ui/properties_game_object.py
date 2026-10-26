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
import bpy
import os
import math
from array import array
from bpy.types import Panel, Menu, UIList, Operator, AnimationEventTrigger
from bpy.props import IntProperty, StringProperty, EnumProperty
from mathutils import Vector
from bpy.app.translations import pgettext_iface as iface_

# Game: Components, Properties and Object tab (LOD, network, culling, animation events).
# Split out of properties_game.py, which still registers every class in order.

class GameButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "game"
    bl_order = 1000

class GAME_PT_game_components(GameButtonsPanel, Panel):
    bl_label = "Game Components"

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.game

    def draw(self, context):
        layout = self.layout

        ob = context.active_object
        game = ob.game

        row = layout.row()
        row.operator("logic.python_component_register", text="Add", icon="PLUS")
        row.operator("logic.python_component_create", text="Create", icon="PLUS")

        for i, c in enumerate(game.components):
            box = layout.box()
            row = box.row(align=1)
            row.prop(c, "show_expanded", text="", emboss=0)
            row.prop(c, "toggle_execution", text="", emboss=False)
            if "C_Icons" in c.properties:
                try:
                    icondict = c.properties["C_Icons"].value.split("+")
                    row.label(c.name, icon=icondict[0])
                except:
                    row.label(c.name)
            else:
                row.label(c.name)
            
            row.operator("logic.python_component_reload", icon="RECOVER_LAST", text="").index = i
            # Joint components written before the Smart Component version keep a
            # name list as Target; the refresh rewrites the module in the new form.
            if (c.module == "rigid_body_joint_component" and c.name == "RigidBodyJointComponent"
                    and not _has_editor(c)):
                row.operator("object.rigid_body_joint_component_refresh", icon="FILE_REFRESH", text="").component_index = i
            # row.separator()
            row.operator("logic.python_component_move_up", icon="TRIA_UP", text="").index = i
            row.operator("logic.python_component_move_down", icon="TRIA_DOWN", text="").index = i
            row = row.row(align=0)
            row.operator("logic.python_component_remove", text="", icon='X').index = i
            draw_component_body(box, ob, c, i)

        layout.operator("wm.flowmenu_ot_init", text="Add...", icon="PLUS")


def draw_component_body(box, ob, c, i):
    """Fields, warnings, draw_ui and buttons of a component box.

    Shared by Game Components and the flowmenu Object's Components panel."""
    lastHeader = None

    # Smart Components: errors, on_change warnings and Editor buttons.
    error, warnings, buttons, editor = _component_editor_info(c)
    metas = _component_meta(c)
    if error:
        row = box.row()
        row.alert = True
        row.label(text=error, icon="CANCEL")
    cbox = box

    only_icons = len(c.properties) == 1 and c.properties[0].name == "C_Icons"
    show_fields = getattr(editor, "fields", True) is not False
    if show_fields and not only_icons and c.show_expanded and len(c.properties) > 0:
        expanded  = True
        collapsed = True
        box = box.box().column()
        armature=""

        for prop in c.properties:
            if prop.name[:8] == "C_Header":
                row = box.row()
                expanded  = prop.value
                collapsed = prop.value
                split=prop.name.split("/")
                name=split[1] if len(split) > 1 else "HEADER"
                icon=split[2] if len(split) > 2 else "FULLSCREEN"
                if icon not in _ui_icons():
                    icon = "FULLSCREEN"   # unknown name: default icon instead of no header
                row.scale_y = 1.2
                try:
                    row.prop(prop,"value", text=name, toggle=1, icon=icon, emboss=1)
                except:
                    print(f"ERROR! Please check header: '{prop.name}' It needs to be like this 'C_Header/HeaderName/Icon'")
                continue

            elif prop.name[:10] == "C_Collapse" and collapsed:
                collapsed  = prop.value
                split=prop.name.split("/")
                name = " ".join(split[1]) if len(split) > 1 else "COLLAPSE"
                icon = split[2] if len(split) > 2 else "MOD_BOOLEAN"

                # LABEL
                row = box.row() ; row = box.row() ; row = box.row()
                row.prop(prop,"value",text=name,toggle=1,emboss=0 if collapsed else 1, icon=icon)
                row.scale_y = 0.9

                # SEPARATOR
                row = box.row()
                row.prop(prop,"value",text=" ",toggle=1,emboss=1)
                row.scale_y = 0.2
                row.enabled = False

                if collapsed: row = box.row() ; row = box.row() ; row = box.row() ; row = box.row() ; row = box.row()
                continue
            else:
                meta = metas.get(prop.name)
                if meta and not _field_visible(c, prop.name, meta):
                    continue   # Range.args show_if: hidden right now
                if expanded and collapsed: row = box.row()
            text=prop.name

            try:
                if expanded and collapsed:
                    split = prop.name.split("/") if "@" in prop.name else [prop.name]
                    if len(split)>1: text=split[1]+":"

                    if not prop.name=="C_Icons":
                        row.label(text=text, icon="DOT")
                        col = row.column()
                        kind = meta.get("kind") if meta else None
                        if kind == "objectlist":
                            _draw_object_list(box, col, i, prop, meta)
                        else:
                            sub = col.row(align=True)
                            # Range.args: Float/Int with min and max draw a slider.
                            sub.prop(prop, "value", text="", slider=prop.use_slider)
                            if kind == "object" and meta.get("create"):
                                _field_tool(sub, i, prop.name, 'CREATE', icon="ZOOMIN")
                            elif kind == "point":
                                _field_tool(sub, i, prop.name, 'POINT_CURSOR', icon="CURSOR")
                                _field_tool(sub, i, prop.name, 'POINT_SELECTED', icon="OBJECT_DATA")
                        warning = warnings.get(prop.name)
                        if warning:
                            box.row().label(text=warning, icon="ERROR")
            except:
                if expanded and collapsed:
                    row.label(text=text)
                    col = row.column()
                    col.prop(prop, "value", text="")

    if editor is not None and hasattr(editor, "draw_ui") and c.show_expanded:
        import range_component_editor as rce
        failed = rce.draw_ui(cbox.column(), ob, c)
        if failed and not error:
            row = cbox.row()
            row.alert = True
            row.label(text=failed, icon="CANCEL")

    if buttons and c.show_expanded:
        col = cbox.column(align=True)
        for b in buttons:
            op = col.operator("logic.component_editor_button", text=b[0], icon=b[2])
            op.index = i
            op.method = b[1]

    # Smart Component Wizard: one more field in the code (startup/smart_component_wizard.py).
    if c.show_expanded and c.module and hasattr(bpy.types, "SMARTWIZ_OT_add_field"):
        row = cbox.row()
        row.alignment = 'RIGHT'
        row.operator("smart_wizard.add_field", text="Add Field", icon="ZOOMIN", emboss=False).index = i


def _component_meta(c):
    try:
        import range_component_editor as rce
        return rce.meta_of(c)
    except Exception:
        return {}


def _field_visible(c, name, meta):
    try:
        import range_component_editor as rce
        return rce.is_visible(c, name, meta)
    except Exception:
        return True


def _field_tool(layout, index, field, action, text="", icon="NONE", item=-1):
    op = layout.operator("logic.component_field_tool", text=text, icon=icon)
    op.index = index
    op.field = field
    op.action = action
    op.item = item
    return op


def _draw_object_list(box, col, index, prop, meta):
    """Range.args.ObjectList: one row per object, add selected, create, remove."""
    import range_component_editor as rce
    names = rce.list_names(prop.value)
    lst = col.column(align=True)
    for n, name in enumerate(names):
        row = lst.row(align=True)
        found = name in bpy.data.objects
        row.alert = not found
        row.label(text="%d. %s" % (n + 1, name), icon="OBJECT_DATA" if found else "ERROR")
        _field_tool(row, index, prop.name, 'LIST_SELECT', icon="RESTRICT_SELECT_OFF", item=n)
        _field_tool(row, index, prop.name, 'LIST_UP', icon="TRIA_UP", item=n)
        _field_tool(row, index, prop.name, 'LIST_REMOVE', icon="X", item=n)
    row = lst.row(align=True)
    _field_tool(row, index, prop.name, 'LIST_ADD_SELECTED', text="Add Selected", icon="ZOOMIN")
    if meta.get("create"):
        _field_tool(row, index, prop.name, 'CREATE', text="New", icon="EMPTY_DATA")
    if names:
        _field_tool(row, index, prop.name, 'LIST_CLEAR', icon="X")


_EMPTY_LOOK = {"object": 'SPHERE', "objectlist": 'PLAIN_AXES'}


class LOGIC_OT_component_field_tool(Operator):
    """Helper buttons of Range.args fields (ObjectList, Point, Object create)"""
    bl_idname = "logic.component_field_tool"
    bl_label = "Field Tool"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    index: IntProperty(options={'HIDDEN'})
    field: StringProperty(options={'HIDDEN'})
    item: IntProperty(default=-1, options={'HIDDEN'})
    action: EnumProperty(options={'HIDDEN'}, items=[
        ('CREATE', "Create", "Create an Empty in front of the object and put it in the field"),
        ('LIST_ADD_SELECTED', "Add Selected", "Add the selected objects (in selection order of names)"),
        ('LIST_REMOVE', "Remove", "Remove from the list"),
        ('LIST_UP', "Move Up", "Move up in the list"),
        ('LIST_SELECT', "Select", "Select this object"),
        ('LIST_CLEAR', "Clear", "Empty the list"),
        ('POINT_CURSOR', "From 3D Cursor", "Put the point where the 3D cursor is"),
        ('POINT_SELECTED', "From Selected", "Put the point on the selected object (not this one)"),
    ])

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        import range_args
        import range_component_editor as rce
        ob = context.active_object
        if not 0 <= self.index < len(ob.game.components):
            return {'CANCELLED'}
        comp = ob.game.components[self.index]
        prop = comp.properties.get(self.field)
        if prop is None:
            return {'CANCELLED'}
        meta = rce.meta_of(comp).get(self.field, {})
        kind = meta.get("kind")
        sep = range_args.LIST_SEP
        names = rce.list_names(prop.value) if kind == "objectlist" else []
        act = self.action

        if act == 'CREATE':
            name = ("%s %d" % (self.field, len(names) + 1) if kind == "objectlist"
                    else "%s of %s" % (self.field, ob.name))
            # Same type as the filter asks, so the new object has no warning.
            flt = meta.get("filter")
            data = None
            if flt == "LAMP":
                data = bpy.data.lamps.new(name, 'POINT')
            elif flt == "CAMERA":
                data = bpy.data.cameras.new(name)
            new = bpy.data.objects.new(name, data)
            if data is None:
                new.empty_draw_type = _EMPTY_LOOK.get(kind, 'PLAIN_AXES')
            last = bpy.data.objects.get(names[-1]) if names else None
            base = last.matrix_world if last else ob.matrix_world
            new.location = base * Vector((0.0, 4.0, 0.0))
            context.scene.objects.link(new)
            if kind == "objectlist":
                names.append(new.name)
            else:
                prop.value = new
        elif act == 'LIST_ADD_SELECTED':
            for o in context.selected_objects:
                if o != ob and o.name not in names:
                    names.append(o.name)
        elif act == 'LIST_REMOVE' and 0 <= self.item < len(names):
            del names[self.item]
        elif act == 'LIST_UP' and 0 < self.item < len(names):
            names[self.item - 1], names[self.item] = names[self.item], names[self.item - 1]
        elif act == 'LIST_CLEAR':
            names = []
        elif act == 'LIST_SELECT' and 0 <= self.item < len(names):
            o = bpy.data.objects.get(names[self.item])
            if o is not None:
                o.select = True
        elif act == 'POINT_CURSOR':
            prop.value = tuple(context.scene.cursor_location)
        elif act == 'POINT_SELECTED':
            others = [o for o in context.selected_objects if o != ob]
            if not others:
                self.report({'WARNING'}, "Select another object too (this one stays active)")
                return {'CANCELLED'}
            prop.value = tuple(others[0].matrix_world.translation)

        if kind == "objectlist" and act.startswith(('LIST', 'CREATE')) and act != 'LIST_SELECT':
            value = sep.join(names)
            if len(value) > 127:
                self.report({'ERROR'}, "List too long (128 characters): use shorter object names")
                return {'CANCELLED'}
            prop.value = value
        return {'FINISHED'}


def _ui_icons():
    return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items


def _component_editor_info(c):
    """(error, {field: warning}, [(text, method, icon)], Editor class) of a Smart Component."""
    try:
        import range_component_editor as rce
        error, warnings = rce.state_of(c)
        editor = rce.editor_of(c)
        buttons = []
        icons = _ui_icons()
        for b in getattr(editor, "buttons", ()) if editor else ():
            text, method = str(b[0]), str(b[1])
            icon = str(b[2]) if len(b) > 2 else "NONE"
            buttons.append((text, method, icon if icon in icons else "NONE"))
        return error, warnings, buttons, editor
    except Exception as e:
        return "Editor: %s" % e, {}, [], None


def _has_editor(c):
    try:
        import range_component_editor as rce
        return rce.editor_of(c) is not None
    except Exception:
        return False


class LOGIC_OT_component_editor_button(Operator):
    """Run a button declared in the component's Editor class"""
    bl_idname = "logic.component_editor_button"
    bl_label = "Component Button"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(options={'HIDDEN'})
    method: StringProperty(options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        import range_component_editor as rce
        ob = context.active_object
        if not 0 <= self.index < len(ob.game.components):
            return {'CANCELLED'}
        error = rce.run_button(context, ob, ob.game.components[self.index], self.method)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}
        return {'FINISHED'}

class GAME_PT_game_properties(GameButtonsPanel, Panel):
    bl_label = "Game Properties"

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.game

    def draw(self, context):
        layout = self.layout

        ob = context.active_object
        game = ob.game
        is_font = (ob.type == 'FONT')

        if is_font:
            prop_index, prop_indexR = game.properties.find("Text"), game.properties.find("Text-Res")

            if prop_index != -1:
                layout.operator("object.game_property_remove", text="Remove Text Game Property", icon='X').index = prop_index
                row = layout.row()
                sub = row.row()
                sub.enabled = 0
                prop = game.properties[prop_index]
                sub.prop(prop, "name", text="", icon="FONT_DATA")
                row.prop(prop, "type", text="")
                row.label("See Text Object")
                
                if prop_indexR != -1:
                    sub = row.row(align=True)
                    sub.operator("object.game_property_remove", text="", icon='X').index = prop_indexR
                    row = layout.row()
                    sub = row.row()
                    sub.enabled = 0
                    prop = game.properties[prop_indexR]
                    sub.prop(prop, "name", text="", icon="FONT_DATA")
                    row.prop(prop, "value", text="Resolution")
                    row.label("Text Resolution(0.1 - 18)")
                else:
                    sub = row.row(align=True)
                    propsR = sub.operator("object.game_property_new", text="", icon='ZOOMIN',)
                    propsR.name = "Text-Res"
                    propsR.type = "FLOAT"
            else:
                props = layout.operator("object.game_property_new", text="Add Text Game Property", icon='ZOOMIN')
                props.name = "Text"
                props.type = "STRING"

        props = layout.operator("object.game_property_new", text="Add Game Property", icon='PLUS')
        props.name = ""

        for i, prop in enumerate(game.properties):
            if is_font and i == prop_index or is_font and i == prop_indexR:
                continue

            box = layout.box()
            row = box.row()
            row.prop(prop, "name", text="")
            row.prop(prop, "type", text="")
            row.prop(prop, "value", text="")
            row.prop(prop, "show_debug", text="", toggle=True, icon='INFO')
            row.prop(prop, "use_replicate", text="Rep", toggle=True)
            sub = row.row(align=True)
            props = sub.operator("object.game_property_move", text="", icon='TRIA_UP')
            props.index = i
            props.direction = 'UP'
            props = sub.operator("object.game_property_move", text="", icon='TRIA_DOWN')
            props.index = i
            props.direction = 'DOWN'
            row.operator("object.game_property_remove", text="", icon='X', emboss=False).index = i
            if prop.use_replicate and prop.type == 'FLOAT':
                row = box.row(align=True)
                row.prop(prop, "net_bits", text="Bits")
                sub = row.row(align=True)
                sub.active = prop.net_bits > 0
                sub.prop(prop, "net_min", text="Min")
                sub.prop(prop, "net_max", text="Max")

class ObjectButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return (context.object is not None and
                context.scene.render.engine == 'BLENDER_GAME' and
                context.window_manager.ae_object_panel_category == 'GAME')


class OBJECT_MT_lod_tools(Menu):
    bl_label = "Level Of Detail Tools"

    def draw(self, context):
        layout = self.layout

        layout.operator("object.lod_by_name", text="Set By Name")
        layout.operator("object.lod_generate", text="Generate")
        layout.operator("object.lod_clear_all", text="Clear All", icon='PANEL_CLOSE')
        
class OBJECT_OT_game_load_with_scene(Operator):
    """Set the game Load Mode of the active and selected objects and their children"""
    bl_idname = "object.game_load_with_scene"
    bl_label = "Set Load Mode"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name="Load Mode",
        items=(('SCENE', "With Scene", "Created in the game when its scene loads"),
               ('ON_DEMAND', "On Demand", "Left out at load; a script creates it with scene.convertObject()"),
               ('EDITOR_ONLY', "Editor Only", "Never created in the game, not even by scene.convertObject()")),
        default='SCENE')
    children: bpy.props.BoolProperty(name="Children", default=True,
                                     description="Also set it on the children of the selected objects")

    @classmethod
    def poll(cls, context):
        return bool(context.object or context.selected_objects)

    def execute(self, context):
        selected = set(context.selected_objects)
        if context.object:
            selected.add(context.object)
        targets = set(selected)
        if self.children:
            for ob in context.scene.objects:
                if any(BL_is_child_of(ob, sel) for sel in selected):
                    targets.add(ob)
        changed = 0
        for ob in targets:
            if ob.game_load_mode != self.mode:
                ob.game_load_mode = self.mode
                changed += 1
        self.report({'INFO'}, "%d object(s) changed" % changed)
        return {'FINISHED'}


class OBJECT_PT_game_object_tasks(GameButtonsPanel, Panel):
    bl_label = "Load Object with Scene"
    bl_context = "object"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (context.scene.render.engine in cls.COMPAT_ENGINES and ob and ob.type and
                context.window_manager.ae_object_panel_category == 'GAME')

    def draw(self, context):
        layout = self.layout
        ob = context.object
        scene = context.scene

        box = layout.box()
        row = box.row(align=True)
        for mode, text in (('SCENE', "With Scene"), ('ON_DEMAND', "On Demand"), ('EDITOR_ONLY', "Editor Only")):
            row.operator("object.game_load_with_scene", text=text,
                         depress=(ob.game_load_mode == mode)).mode = mode
        box.label(text="Applies to the selected objects and their children")

        # The converter drops any object below an ancestor left out at load.
        par = ob.parent
        while par and par.game_load_mode == 'SCENE':
            par = par.parent
        if par and ob.game_load_mode == 'SCENE':
            box.label(text="Left out anyway: parent \"%s\" doesn't load with the scene" % par.name, icon='ERROR')

        if ob.game_load_mode == 'ON_DEMAND':
            col = box.column(align=True)
            col.label(text="Left out at load. Create it from a script with:", icon='INFO')
            col.label(text="    scene.convertObject(\"%s\")" % ob.name)
        elif ob.game_load_mode == 'EDITOR_ONLY':
            box.label(text="Never created in the game, not even by scene.convertObject()", icon='INFO')

        if ob.game_load_mode != 'SCENE':
            descendants = [o for o in scene.objects if o.parent and BL_is_child_of(o, ob)]
            if descendants:
                box.label(text="%d child object(s) stay out with it" % len(descendants), icon='OUTLINER_OB_EMPTY')

            for group in ob.users_group:
                for inst in scene.objects:
                    if inst.game_load_mode == 'SCENE' and inst.dupli_type == 'GROUP' and inst.dupli_group == group:
                        box.label(text="Missing from the instances of group \"%s\" (\"%s\")" % (group.name, inst.name),
                                  icon='ERROR')
                        break

            if ob.type == 'MESH' and ob.data and ob.data.users > 1:
                if any(o.data == ob.data and o.game_load_mode == 'SCENE' for o in scene.objects if o != ob):
                    box.label(text="Mesh shared with loaded objects: freeUnconvertedData() keeps it",
                              icon='INFO')


def BL_is_child_of(ob, parent):
    par = ob.parent
    while par:
        if par == parent:
            return True
        par = par.parent
    return False


class OBJECT_MT_culling(ObjectButtonsPanel, Panel):
    bl_label = "Culling Bounding Volume"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (super().poll(context) and ob.type not in {'CAMERA', 'EMPTY', 'LAMP'})

    def draw(self, context):
        layout = self.layout
        game = context.active_object.game

        layout.label(text="Predefined Bound:")
        layout.prop(game, "predefined_bound", "")

class OBJECT_PT_game_network(GameButtonsPanel, Panel):
    bl_label = "Network"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = -20
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob is not None and context.scene.render.engine in cls.COMPAT_ENGINES
                and ob.type not in {'CAMERA'})

    def draw(self, context):
        layout = self.layout
        net = context.object.game.network

        box = layout.box()
        box.prop(net, "use_replicate", text="Replicate")
        col = box.column()
        col.active = net.use_replicate
        col.prop(net, "sync_transform")
        col.prop(net, "sync_velocity")
        col.prop(net, "sync_angular_velocity")
        col.prop(net, "use_interpolate")
        col.prop(net, "use_always_relevant")
        col.prop(net, "priority")
        if net.use_replicate:
            col.label(text="ID: %d" % net.net_id)
            col.label(text="Properties with 'Rep' on are replicated too", icon='INFO')
        box.label(text="Room, ports and server: Export Game > Network", icon='EXPORT')


class OBJECT_PT_activity_culling(GameButtonsPanel, Panel):
    bl_label = "Activity Culling"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = -19
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (context.scene.render.engine in cls.COMPAT_ENGINES and ob.type not in {'CAMERA'})

    def draw(self, context):
        layout = self.layout
        activity = context.object.game.activity_culling

        activity_box = layout.box()
        split = activity_box.split()

        col = split.column()
        col.prop(activity, "use_physics", text="Physics")
        sub = col.box()
        sub.active = activity.use_physics
        sub.prop(activity, "physics_radius")
        sub.prop(activity, "sleep_velocity", text="Sleep Velocity")

        col = split.column()
        col.prop(activity, "use_logic", text="Logic")
        sub = col.box()
        sub.active = activity.use_logic
        sub.prop(activity, "logic_radius")
        sub = sub.column()
        sub.prop(activity, "activity_components", text="No Components")

class OBJECT_OT_bake_lod_impostor(Operator):
    bl_idname = "object.bake_lod_impostor"
    bl_label = "Bake Impostor Texture"
    bl_description = ("Render the LOD level's mesh into a transparent image for use as a billboard impostor "
                       "texture, either a single frontal view or a multi-angle atlas")
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()

    def execute(self, context):
        ob = context.object
        scene = context.scene

        if ob is None or self.index < 0 or self.index >= len(ob.lod_levels):
            self.report({'ERROR'}, "Invalid LOD level")
            return {'CANCELLED'}

        level = ob.lod_levels[self.index]

        # The high-poly mesh to photograph is the LOD owner itself (level 0),
        # not the low-poly billboard plane referenced by this level.
        source = ob
        if source.type != 'MESH' or not source.data.vertices:
            self.report({'ERROR'}, "Active object has no mesh to bake an impostor from")
            return {'CANCELLED'}

        multi_angle = level.use_atlas
        angle_count = int(scene.lod_impostor_bake_angles) if multi_angle else 1
        cell_resolution = int(scene.lod_impostor_bake_resolution)

        if multi_angle:
            # The game splits the full turn into cols * rows cells, so the grid must hold
            # exactly angle_count cells (8 views -> 4x2, not 3x3 with an empty cell).
            cols = math.ceil(math.sqrt(angle_count))
            while angle_count % cols:
                cols += 1
            rows = angle_count // cols
        else:
            cols, rows = 1, 1

        # Bounding box of the source mesh in world space.
        bbox_world = [source.matrix_world * Vector(corner) for corner in source.bound_box]
        min_co = Vector((min(v[i] for v in bbox_world) for i in range(3)))
        max_co = Vector((max(v[i] for v in bbox_world) for i in range(3)))
        size = max_co - min_co
        # The runtime billboard spins the object around its origin, so frame every shot
        # horizontally on that vertical axis (not on the bbox center): the quad then stays
        # centered on the origin and an off-center mesh keeps its offset inside the image
        # instead of the quad swinging sideways at other headings.
        pivot = source.matrix_world.translation
        center = Vector((pivot.x, pivot.y, (min_co.z + max_co.z) * 0.5))
        # Half-extent used to frame the camera, with a margin so the silhouette isn't clipped.
        # half_width is the farthest bbox corner from the axis, so no heading crops the mesh.
        half_height = max(size.z, 1e-3) * 0.5 * 1.1
        half_width = max(max(Vector((v.x - pivot.x, v.y - pivot.y)).length for v in bbox_world), 1e-3) * 1.1
        half_extent = max(half_height, half_width)
        camera_distance = max(size.y, size.x, 1.0) * 4.0 + half_extent

        cam_data = bpy.data.cameras.new("LOD_ImpostorBakeCam")
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = half_extent * 2.0
        cam_obj = bpy.data.objects.new("LOD_ImpostorBakeCam", cam_data)
        scene.objects.link(cam_obj)

        prev_camera = scene.camera
        # Keep lamps visible so the source isn't baked pitch black; hide every
        # other object (including the billboard plane itself) so only the
        # high-poly source mesh shows up in the shot.
        prev_hidden = [(o, o.hide_render) for o in scene.objects if o != source and o.type != 'LAMP']
        for o, _ in prev_hidden:
            o.hide_render = True

        prev_engine = scene.render.engine
        prev_res_x = scene.render.resolution_x
        prev_res_y = scene.render.resolution_y
        prev_res_pct = scene.render.resolution_percentage
        prev_alpha_mode = scene.render.alpha_mode
        prev_filepath = scene.render.filepath

        blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else bpy.app.tempdir
        out_path = os.path.join(blend_dir, "{}_impostor.png".format(source.name))
        cell_paths = []

        try:
            # Force the classic Blender Internal engine for the bake: the scene
            # is normally set to BLENDER_GAME, whose render() ignores alpha_mode
            # / transparency_method entirely and just dumps the game viewport.
            scene.render.engine = 'BLENDER_RENDER'
            scene.camera = cam_obj
            scene.render.resolution_x = cell_resolution
            scene.render.resolution_y = cell_resolution
            scene.render.resolution_percentage = 100
            scene.render.alpha_mode = 'TRANSPARENT'

            for i in range(angle_count):
                # Cell 0 matches the single-angle frontal shot (camera on the
                # +Y side, see KX_GameObject::UpdateLod's heading convention:
                # heading = atan2(-toCam.x, toCam.y), which is 0 for a camera
                # offset of (0, +d, 0) from the object). Rotating the offset
                # counter-clockwise by `angle` keeps heading(angle) == angle,
                # so runtime cell selection can map heading directly to index.
                if multi_angle:
                    angle = (2.0 * math.pi * i) / angle_count
                else:
                    # A single shot is shown from every side, so take it from the
                    # object's own front (Blender's Front view: local -Y, looking +Y).
                    front = source.matrix_world.to_3x3() * Vector((0.0, -1.0, 0.0))
                    angle = math.atan2(-front.x, front.y) if front.xy.length > 1e-6 else math.pi
                offset = Vector((-camera_distance * math.sin(angle), camera_distance * math.cos(angle), 0.0))
                cam_obj.location = center + offset
                cam_obj.location.z = center.z
                direction = center - cam_obj.location
                cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

                cell_path = out_path if not multi_angle else os.path.join(
                    blend_dir, "{}_impostor_cell{}.png".format(source.name, i))
                scene.render.filepath = cell_path
                bpy.ops.render.render(write_still=True)
                cell_paths.append(cell_path)
        finally:
            for o, hide in prev_hidden:
                o.hide_render = hide
            scene.camera = prev_camera
            scene.render.engine = prev_engine
            scene.render.resolution_x = prev_res_x
            scene.render.resolution_y = prev_res_y
            scene.render.resolution_percentage = prev_res_pct
            scene.render.alpha_mode = prev_alpha_mode
            scene.render.filepath = prev_filepath
            scene.objects.unlink(cam_obj)
            bpy.data.objects.remove(cam_obj)
            bpy.data.cameras.remove(cam_data)

        if multi_angle:
            self._compose_atlas(cell_paths, cols, rows, cell_resolution, out_path)
            level.use_atlas = True
            level.atlas_columns = cols
            level.atlas_rows = rows
        else:
            level.use_atlas = False

        # Never texture the user's LOD mesh: its UVs, orientation and (often shared)
        # material don't match the baked shot. Point the level at a generated quad instead.
        target = self._build_impostor_quad(scene, source, level.object, center, half_extent)
        level.object = target
        self._apply_impostor_texture(target, out_path)

        self.report({'INFO'}, "Impostor baked to {}".format(out_path))
        return {'FINISHED'}

    @staticmethod
    def _compose_atlas(cell_paths, cols, rows, cell_resolution, out_path):
        atlas_w = cols * cell_resolution
        atlas_h = rows * cell_resolution
        atlas_buf = array('f', [0.0] * (atlas_w * atlas_h * 4))

        row_floats = cell_resolution * 4
        for i, cell_path in enumerate(cell_paths):
            col, row = i % cols, i // cols
            cell_img = bpy.data.images.load(cell_path)
            try:
                cell_buf = array('f', cell_img.pixels[:])
                # Cell (0, 0) is the bottom-left of the atlas, matching Blender's
                # bottom-up pixel row order, so the array copy needs no vertical flip.
                dest_row0 = row * cell_resolution
                dest_col0 = col * cell_resolution
                for cell_row in range(cell_resolution):
                    src_start = cell_row * row_floats
                    dest_start = ((dest_row0 + cell_row) * atlas_w + dest_col0) * 4
                    atlas_buf[dest_start:dest_start + row_floats] = cell_buf[src_start:src_start + row_floats]
            finally:
                bpy.data.images.remove(cell_img)
            os.remove(cell_path)

        atlas_name = os.path.basename(out_path)
        atlas_img = bpy.data.images.get(atlas_name)
        if atlas_img is None or tuple(atlas_img.size) != (atlas_w, atlas_h):
            if atlas_img is not None:
                bpy.data.images.remove(atlas_img)
            atlas_img = bpy.data.images.new(atlas_name, atlas_w, atlas_h, alpha=True)
        atlas_img.pixels[:] = atlas_buf
        atlas_img.filepath_raw = out_path
        atlas_img.file_format = 'PNG'
        atlas_img.save()

    @staticmethod
    def _build_impostor_quad(scene, source, previous, center, half_extent):
        # Quad matching the frontal ortho shot: camera on +Y looking at -Y, so the face
        # normal is +Y (what the runtime billboard turns to the camera), image right is
        # world -X and image up is +Z. Coordinates are relative to the owner's origin and
        # divided by its scale, since the LOD mesh is drawn with the owner's transform
        # and the billboard replaces its rotation.
        name = "{}_impostor".format(source.name)
        scale = source.matrix_world.to_scale()
        offset = center - source.matrix_world.translation

        def local(dx, dz):
            return ((offset.x + dx) / scale.x, offset.y / scale.y, (offset.z + dz) / scale.z)

        e = half_extent
        verts = [local(e, -e), local(-e, -e), local(-e, e), local(e, e)]
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
        mesh.uv_textures.new()
        for loop_uv, uv in zip(mesh.uv_layers[0].data, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
            loop_uv.uv = uv
        mesh.update()

        quad = bpy.data.objects.get(name)
        if quad is not None and quad.type == 'MESH':
            old_mesh = quad.data
            quad.data = mesh
            if old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)
        else:
            quad = bpy.data.objects.new(name, mesh)
            scene.objects.link(quad)
            # Same layers as the object the level used before (usually a hidden LOD layer).
            quad.layers = (previous or source).layers
            quad.location = (previous or source).location
        mesh.name = name
        return quad

    @staticmethod
    def _apply_impostor_texture(target, image_path):
        # Reuse an existing image datablock pointing at this bake instead of
        # piling up duplicates each time the button is pressed.
        image_name = os.path.basename(image_path)
        image = bpy.data.images.get(image_name)
        if image is not None:
            image.filepath = image_path
            image.source = 'FILE'
            image.reload()
        else:
            image = bpy.data.images.load(image_path)
        image.use_alpha = True
        image.alpha_mode = 'STRAIGHT'

        material = target.data.materials[0] if target.data.materials else None
        if material is None:
            material = bpy.data.materials.new(name="{}_impostor".format(target.name))
            target.data.materials.append(material)

        # Named per-target so multiple billboard trees don't clobber each other's texture.
        tex_name = "{}_impostor".format(target.name)
        tex = bpy.data.textures.get(tex_name)
        if tex is None or tex.type != 'IMAGE':
            tex = bpy.data.textures.new(tex_name, type='IMAGE')
        tex.image = image

        slot = None
        for existing in material.texture_slots:
            if existing is not None and existing.texture is tex:
                slot = existing
                break
        if slot is None:
            slot = material.texture_slots.add()
            slot.texture = tex
            slot.texture_coords = 'UV'
        slot.use_map_alpha = True

        material.use_transparency = True
        material.transparency_method = 'Z_TRANSPARENCY'
        material.alpha = 0.0
        material.specular_alpha = 0.0


bpy.types.Scene.lod_impostor_bake_resolution = EnumProperty(
    name="Impostor Bake Resolution",
    description="Image size used by 'Bake Impostor Texture' (per-cell size in Multi-Angle mode)",
    items=(
        ('128', "128", "128x128 px"),
        ('256', "256", "256x256 px"),
        ('512', "512", "512x512 px"),
        ('1024', "1024", "1024x1024 px"),
    ),
    default='512',
)

bpy.types.Scene.lod_impostor_bake_angles = EnumProperty(
    name="Impostor Bake Angles",
    description="Number of views baked around the Z axis in Multi-Angle mode",
    items=(
        ('4', "4", "4 views, 90° apart"),
        ('8', "8", "8 views, 45° apart"),
        ('12', "12", "12 views, 30° apart"),
        ('16', "16", "16 views, 22.5° apart"),
    ),
    default='8',
)


class OBJECT_PT_levels_of_detail(ObjectButtonsPanel, Panel):
    bl_label = "Levels of Detail - LOD"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (super().poll(context) and ob.type not in {'CAMERA', 'EMPTY', 'LAMP'})

    def draw(self, context):
        layout = self.layout
        ob = context.object
        gs = context.scene.game_settings

        col = layout.column()
        col.prop(ob, "lod_factor", text="Distance Factor")
        
        col = layout.column()
        col.prop(ob, "use_lod_physics", text="Physics Update")

        for i, level in enumerate(ob.lod_levels):
            if i == 0:
                continue
            box = col.box()
            row = box.row(align=True)
            row.prop(level, "object", text="")
            row.prop(level, "use_invisible_mesh", text="")
            row.operator("object.lod_remove", text="", icon='PANEL_CLOSE').index = i
            
            row = box.row()
            row.prop(level, "distance")
            row = row.row(align=True)
            row.prop(level, "use_mesh", text="")
            row.prop(level, "use_material", text="")

            row = box.row()
            row.active = level.use_mesh
            row.prop(level, "use_billboard", text="Billboard (impostor)")

            if level.use_billboard:
                row = box.row()
                row.active = level.use_billboard
                row.prop(level, "use_atlas", text="Multi-Angle Atlas")

                if level.use_atlas:
                    row = box.row(align=True)
                    row.enabled = False
                    row.prop(level, "atlas_columns", text="Columns")
                    row.prop(level, "atlas_rows", text="Rows")

                if level.use_atlas:
                    row = box.row(align=True)
                    row.prop(context.scene, "lod_impostor_bake_angles", text="Angles")

                row = box.row(align=True)
                row.operator("object.bake_lod_impostor", text="Bake Impostor Texture", icon='RENDER_STILL').index = i
                row.prop(context.scene, "lod_impostor_bake_resolution", text="")

            row = box.row()
            row.active = gs.use_scene_hysteresis
            row.prop(level, "use_object_hysteresis", text="Hysteresis Override")
            row = box.row()
            row.active = gs.use_scene_hysteresis and level.use_object_hysteresis
            row.prop(level, "object_hysteresis_percentage", text="")

        row = col.row(align=True)
        row.operator("object.lod_add", text="Add", icon='ZOOMIN')
        row.menu("OBJECT_MT_lod_tools", text="", icon='TRIA_DOWN')
        
class OBJECT_PT_animation_events(GameButtonsPanel, Panel):
    bl_label = "Animation Events"
    bl_context = "object"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None and context.scene.render.engine in cls.COMPAT_ENGINES and
                context.window_manager.ae_object_panel_category == 'GAME')

    def draw(self, context):
        layout = self.layout
        ob = context.object

        col = layout.column()

        # Index 0 of anim_events (and of each event.triggers) is a hidden base element.
        last = len(ob.anim_events) - 1
        for i, event in enumerate(ob.anim_events):
            if i == 0:
                continue

            box = col.box()
            row = box.row()
            row.prop(event, "show_expanded", text="", emboss=True)

            if event.anim:
                header = "{} - {}".format(i, event.anim.name)
            else:
                header = "{} - No Action".format(i)
            row.label(text=header, icon="RECOVER_LAST", translate=False)

            sub = row.row(align=True)
            up = sub.row(align=True)
            up.enabled = i > 1
            up.operator("object.animation_event_move_up", text="", icon='DOTSUP').index = i
            down = sub.row(align=True)
            down.enabled = i < last
            down.operator("object.animation_event_move_down", text="", icon='DOTSDOWN').index = i
            sub.operator("object.animation_event_remove", text="", icon='PANEL_CLOSE').index = i

            if not event.show_expanded:
                continue

            split = box.split(factor=0.25)
            split.label(text="Action:")
            split.prop(event, "anim", text="")

            split = box.split(factor=0.25)
            split.label(text="Python Event:")
            split.prop(event, "eventcall", text="", icon="FILE_SCRIPT")

            # Triggers
            row = box.row()
            row.label(text="Triggers", icon="ANIM")
            row.operator("object.animation_event_trigger_add", text="Add Trigger", icon='ZOOMIN').index = i

            if len(event.triggers) < 2:
                box.label(text="No triggers. Add a frame trigger", icon="INFO")

            for it, trigger in enumerate(event.triggers):
                if it == 0:
                    continue

                row = box.row(align=True)
                row.prop(trigger, "frame", text="Frame")
                row.prop(trigger, "custom_arg", text="")

                props = row.operator("object.animation_event_trigger_pick", text="", icon="EYEDROPPER")
                props.eventIndex = i
                props.index = it

                props = row.operator("object.animation_event_trigger_remove", text="", icon="PANEL_CLOSE")
                props.eventIndex = i
                props.index = it

        row = col.row(align=True)
        row.operator("object.animation_event_add", text="Add Animation Event", icon='ZOOMIN')
