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
from bpy.types import Header, Menu, Panel

class LOGIC_PT_properties(Panel):
    bl_space_type = 'LOGIC_EDITOR'
    bl_region_type = 'UI'
    bl_label = "Properties"

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
            layout.prop(ob.data, "use_game_text_preview")
            if ob.data.use_game_text_preview:
                layout.prop(ob.data, "use_game_text_hide_curve")
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
                    row.label("Text Resolution(0.1-18)")
                else:
                    sub = row.row(align=True)
                    propsR = sub.operator("object.game_property_new", text="", icon='ZOOMIN',)
                    propsR.name = "Text-Res"
                    propsR.type = 'FLOAT'
            else:
                props = layout.operator("object.game_property_new", text="Add Text Game Property", icon='ZOOMIN')
                props.name = "Text"
                props.type = 'STRING'
                
        props = layout.operator("object.game_property_new", text="Add Game Property", icon='ZOOMIN')
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
            sub = row.row(align=True)
            props = sub.operator("object.game_property_move", text="", icon='TRIA_UP')
            props.index = i
            props.direction = 'UP'
            props = sub.operator("object.game_property_move", text="", icon='TRIA_DOWN')
            props.index = i
            props.direction = 'DOWN'
            row.operator("object.game_property_remove", text="", icon='X', emboss=False).index = i


class LOGIC_PT_brick_groups(Panel):
    bl_space_type = 'LOGIC_EDITOR'
    bl_region_type = 'UI'
    bl_label = "Brick Groups"

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.game

    def draw(self, context):
        layout = self.layout
        game = context.active_object.game

        row = layout.row()
        row.template_list("UI_UL_list", "logic_brick_groups", game, "brick_groups",
                          game, "active_brick_group_index", rows=3)
        col = row.column(align=True)
        col.operator("logic.brick_group_add", icon='ZOOMIN', text="")
        col.operator("logic.brick_group_remove", icon='ZOOMOUT', text="")

        g = game
        missing = any(b.group and b.group not in g.brick_groups
                      for b in list(g.sensors) + list(g.controllers) + list(g.actuators))
        if missing:
            layout.operator("logic.brick_group_add", text="Add Groups Used by Bricks", icon='GROUP').collect = True
        layout.label(text="Double click renames the group of its bricks too", icon='INFO')


class LOGIC_PT_brick_inspector(Panel):
    """Smart Bricks: what looks wrong in the bricks, without running the game"""
    bl_space_type = 'LOGIC_EDITOR'
    bl_region_type = 'UI'
    bl_label = "Brick Inspector"

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.game

    def draw(self, context):
        import range_brick_inspector as bricks
        layout = self.layout
        ob = context.active_object
        game = ob.game
        wm = context.window_manager

        row = layout.row(align=True)
        row.label(text="%d sensors, %d controllers, %d actuators"
                  % (len(game.sensors), len(game.controllers), len(game.actuators)))
        if hasattr(wm, "range_component_gizmos"):
            layout.prop(wm, "range_component_gizmos", text="Viewport")

        found = bricks.problems(ob)
        if not wm.brick_inspector_show_info:
            found = [p for p in found if p.level != bricks.INFO]
        col = layout.column(align=True)
        if not found:
            col.label(text="No problems found", icon='FILE_TICK')
        for p in found:
            box = col.box()
            row = box.row(align=True)
            op = row.operator("logic.brick_inspector_show", text=p.brick.name, icon=p.icon, emboss=False)
            op.kind = p.kind
            op.name = p.brick.name
            row.label(text=p.kind.title())
            box.label(text=p.text)
        layout.prop(wm, "brick_inspector_show_info")

        others = []
        for o in context.scene.objects:
            if o == ob or not (len(o.game.sensors) or len(o.game.actuators)):
                continue
            bad, _ = bricks.count(o)
            if bad:
                others.append((o, bad))
            if len(others) >= 20:
                break
        if others:
            layout.separator()
            layout.label(text="Other objects with problems:")
            col = layout.column(align=True)
            for o, bad in others:
                op = col.operator("logic.brick_inspector_object", text="%s (%d)" % (o.name, bad),
                                  icon='OBJECT_DATA')
                op.name = o.name


class LOGIC_PT_states(Panel):
    bl_space_type = 'LOGIC_EDITOR'
    bl_region_type = 'UI'
    bl_label = "States"

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.game

    def draw(self, context):
        layout = self.layout
        game = context.active_object.game

        header = layout.row()
        header.label(text="Visible  #   State Name")
        sub = header.row()
        sub.alignment = 'RIGHT'
        sub.label(text="Initial")

        col = layout.column(align=True)
        for item in game.state_names:
            i = item.index
            row = col.row(align=True)
            row.prop(game, "states_visible", index=i, text="", toggle=True,
                     icon='LAYER_USED' if game.used_states[i] else 'BLANK1')
            sub = row.row(align=True)
            sub.ui_units_x = 1.5
            sub.alignment = 'RIGHT'
            sub.label(text="%d" % (i + 1))
            row.prop(item, "name", text="")
            row.prop(game, "states_initial", index=i, text="", toggle=True, icon='PLAY')


class LOGIC_MT_logicbricks_add(Menu):
    bl_label = "Add"

    def draw(self, context):
        layout = self.layout

        layout.operator_menu_enum("logic.sensor_add", "type", text="Sensor")
        layout.operator_menu_enum("logic.controller_add", "type", text="Controller")
        layout.operator_menu_enum("logic.actuator_add", "type", text="Actuator")

        layout.separator()
        layout.operator_menu_enum("logic.preset_add", "type", text="Preset")


class LOGIC_HT_header(Header):
    bl_space_type = 'LOGIC_EDITOR'

    def draw(self, context):
        layout = self.layout.row(align=True)

        layout.template_header()

        if context.area.show_header_menus:
            LOGIC_MT_editor_menus.draw_collapsible(context, layout)

        layout.separator()
        layout.operator("logic.convert_to_component", text="Convert to Python", icon='SCRIPT')
        layout.separator()
        layout.prop(context.space_data, "show_highlight_active", text="Highlight Active", icon='LIGHTPAINT')


class LOGIC_MT_editor_menus(Menu):
    bl_idname = "LOGIC_MT_editor_menus"
    bl_label = ""

    def draw(self, context):
        self.draw_menus(self.layout, context)

    @staticmethod
    def draw_menus(layout, context):
        layout.menu("LOGIC_MT_view")
        layout.menu("LOGIC_MT_logicbricks_add")


class LOGIC_MT_view(Menu):
    bl_label = "View"

    def draw(self, context):
        layout = self.layout

        layout.operator("logic.properties", icon='MENU_PANEL')

        layout.separator()

        layout.prop(context.space_data, "show_menu_icons")

        layout.separator()

        layout.operator("logic.convert_to_component", icon='SCRIPT')

        layout.separator()

        layout.operator("screen.area_dupli")
        layout.operator("screen.screen_full_area")
        layout.operator("screen.screen_full_area", text="Toggle Fullscreen Area").use_hide_panels = True


classes = (
    LOGIC_PT_properties,
    LOGIC_PT_brick_groups,
    LOGIC_PT_states,
    LOGIC_PT_brick_inspector,
    LOGIC_MT_logicbricks_add,
    LOGIC_HT_header,
    LOGIC_MT_editor_menus,
    LOGIC_MT_view,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
