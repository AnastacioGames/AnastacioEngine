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

# Painel Video Player da aba Object (categoria Game): liga o componente anastacio_video.VideoPlayer no objeto
# e edita os campos dele. Os valores ficam nas propriedades do proprio componente, que o jogo le no start().

import bpy
from bpy.types import Operator, Panel

MODULE = "anastacio_video"
COMPONENT = "VideoPlayer"


def video_component(ob):
    if ob is None:
        return None
    return next((c for c in ob.game.components if c.module == MODULE and c.name == COMPONENT), None)


def _override(context, ob):
    override = context.copy()
    override.update(object=ob, active_object=ob)
    return override


class OBJECT_OT_video_player_add(Operator):
    """Play a video on this object's material or as a fullscreen cutscene"""
    bl_idname = "object.video_player_add"
    bl_label = "Add Video Player"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and video_component(context.object) is None

    def execute(self, context):
        ob = context.object
        result = bpy.ops.logic.python_component_register(_override(context, ob),
                                                         component_name=MODULE + "." + COMPONENT)
        if 'FINISHED' not in result or video_component(ob) is None:
            self.report({'ERROR'}, "Could not add the Video Player component")
            return {'CANCELLED'}
        # Objeto com material comeca na tela dele; sem material, como cutscene em tela cheia.
        props = video_component(ob).properties
        if ob.active_material:
            props["Material"].value = ob.active_material.name
        else:
            props["Fullscreen"].value = True
        return {'FINISHED'}


class OBJECT_OT_video_player_remove(Operator):
    """Remove the Video Player from this object"""
    bl_idname = "object.video_player_remove"
    bl_label = "Remove Video Player"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return video_component(context.object) is not None

    def execute(self, context):
        ob = context.object
        index = list(ob.game.components).index(video_component(ob))
        bpy.ops.logic.python_component_remove(_override(context, ob), index=index)
        return {'FINISHED'}


class OBJECT_OT_video_player_file(Operator):
    """Choose the video file"""
    bl_idname = "object.video_player_file"
    bl_label = "Choose Video"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_movie: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    relative_path: bpy.props.BoolProperty(name="Relative Path", default=True,
                                          description="Store the path relative to the .range file")

    @classmethod
    def poll(cls, context):
        return video_component(context.object) is not None

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        path = self.filepath
        if self.relative_path and bpy.data.is_saved:
            try:
                path = bpy.path.relpath(path)
            except ValueError:  # outra unidade no Windows
                pass
        video_component(context.object).properties["File"].value = path
        return {'FINISHED'}


class OBJECT_PT_video_player(Panel):
    bl_label = "Video Player"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None and
                context.scene.render.engine in cls.COMPAT_ENGINES and
                context.window_manager.ae_object_panel_category == 'GAME')

    def draw(self, context):
        layout = self.layout
        ob = context.object
        component = video_component(ob)
        if component is None:
            layout.operator("object.video_player_add", icon='FILE_MOVIE')
            return

        props = component.properties
        missing = [name for name in ("File", "Fullscreen", "Material") if name not in props]
        if missing:
            layout.label(text="Component out of date, add it again", icon='ERROR')
            layout.operator("object.video_player_remove", icon='X')
            return

        def field(col, name, text=None):
            if name in props:
                col.prop(props[name], "value", text=text if text is not None else name)

        row = layout.row(align=True)
        row.prop(props["File"], "value", text="File")
        row.operator("object.video_player_file", text="", icon='FILEBROWSER')

        fullscreen = props["Fullscreen"].value
        row = layout.row()
        row.prop(props["Fullscreen"], "value", text="Fullscreen Cutscene")
        if not fullscreen:
            if ob.type == 'MESH':
                layout.prop_search(props["Material"], "value", ob.data, "materials", text="Material")
            else:
                field(layout, "Material")

        split = layout.split()
        col = split.column()
        col.label(text="Playback:")
        field(col, "Autoplay")
        field(col, "Loop")
        field(col, "Speed")

        col = split.column()
        col.label(text="Sound:")
        field(col, "Play Sound")
        sub = col.column()
        sub.active = "Play Sound" in props and props["Play Sound"].value
        field(sub, "Volume")
        if not fullscreen:
            field(sub, "3D Sound")

        if fullscreen:
            layout.separator()
            split = layout.split()
            col = split.column()
            col.label(text="Cutscene:")
            field(col, "Pause Scene")
            field(col, "Fill Screen")
            col = split.column()
            col.label(text="Skip:")
            field(col, "Skippable")
            sub = col.column()
            sub.active = "Skippable" in props and props["Skippable"].value
            field(sub, "Skip Key", text="Key")

        layout.separator()
        layout.operator("object.video_player_remove", icon='X')


classes = (
    OBJECT_OT_video_player_add,
    OBJECT_OT_video_player_remove,
    OBJECT_OT_video_player_file,
    OBJECT_PT_video_player,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
