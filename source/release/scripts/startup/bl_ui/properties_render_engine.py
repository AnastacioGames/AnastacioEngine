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
from bpy.types import Menu, Panel

# Panels are drawn in registration order, so this module is listed before
# properties_game in bl_ui/__init__.py to keep the engine selector on top.
# The class keeps its name because the Cycles add-on appends to RENDER_PT_render.


def _engine_items(context):
    items = [
        ("BLENDER_GAME", "Range Engine", 'GAME'),
        ("BLENDER_RENDER", "Blender Render", 'RENDER_STILL'),
    ]
    # scene.cycles only exists while the Cycles add-on is enabled.
    if hasattr(context.scene, "cycles"):
        items.append(("CYCLES", "Cycles Render", 'LAMP_SUN'))
    return items


class RENDER_MT_engine(Menu):
    bl_label = "Render Engine"

    def draw(self, context):
        layout = self.layout
        # An operator instead of prop_enum, so items show without a check box.
        for engine, text, icon in _engine_items(context):
            props = layout.operator("wm.context_set_enum", text=text, icon=icon)
            props.data_path = "scene.render.engine"
            props.value = engine


class RENDER_PT_render(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    bl_label = "Engine"
    COMPAT_ENGINES = {"BLENDER_RENDER", "BLENDER_GAME", "CYCLES"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return scene and (scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        rd = context.scene.render

        if rd.has_multiple_engines:
            box = layout.box()
            text, icon = next(((t, i) for e, t, i in _engine_items(context) if e == rd.engine),
                              (rd.engine, 'SCENE'))
            row = box.row()
            row.scale_y = 1.2
            row.menu("RENDER_MT_engine", text=text, icon=icon)

        if rd.engine != "BLENDER_GAME":
            row = layout.row(align=True)
            row.operator("render.render", text="Render", icon='RENDER_STILL')
            row.operator("render.render", text="Animation", icon='RENDER_ANIMATION').animation = True
            row.operator("sound.mixdown", text="Audio", icon='PLAY_AUDIO')

            split = layout.split(factor=0.33)

            split.label(text="Display:")
            row = split.row(align=True)
            row.prop(rd, "display_mode", text="")
            row.prop(rd, "use_lock_interface", icon_only=True)


classes = (
    RENDER_MT_engine,
    RENDER_PT_render,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
