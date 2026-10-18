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


def copy_videos(game_dir, report=None):
    """Copia para game_dir/videos os videos dos Video Players que ficariam fora do jogo exportado.

    game_dir e a pasta que o jogo enxerga como "//" (data/ no RangeArmor, a pasta do executavel no
    Save As Runtime). Video que ja esta dentro dela vai junto e nao e copiado. O runtime procura em
    //videos/ pelo nome do arquivo quando o caminho escrito nao existe. Devolve quantos copiou."""
    import os
    import shutil

    game_dir = os.path.normcase(os.path.abspath(game_dir))
    dest_dir = os.path.join(game_dir, "videos")
    copied = {}
    for ob in bpy.data.objects:
        component = video_component(ob)
        if component is None or "File" not in component.properties:
            continue
        value = component.properties["File"].value
        if not value:
            continue
        src = os.path.normcase(os.path.abspath(bpy.path.abspath(value, library=ob.library)))
        if not os.path.isfile(src):
            if report:
                report({'WARNING'}, "Video Player of %s: file not found: %s" % (ob.name, value))
            continue
        try:
            inside = os.path.commonpath([src, game_dir]) == game_dir
        except ValueError:  # outra unidade no Windows
            inside = False
        if inside:
            continue
        name = os.path.basename(src)
        if copied.get(name.lower(), src) != src:
            if report:
                report({'WARNING'}, "Two different videos are named %s; only one goes in the game" % name)
            continue
        dest = os.path.join(dest_dir, name)
        if name.lower() not in copied:
            os.makedirs(dest_dir, exist_ok=True)
            if (not os.path.isfile(dest) or os.path.getsize(dest) != os.path.getsize(src) or
                    os.path.getmtime(dest) < os.path.getmtime(src)):
                shutil.copy2(src, dest)
            copied[name.lower()] = src
    return len(copied)


def video_texture_slot(mat):
    """Slot de textura de imagem que o video substitui no jogo (o primeiro do material)."""
    if mat is None:
        return None
    return next((ts for ts in mat.texture_slots if ts and ts.texture and ts.texture.type == 'IMAGE'), None)


def ensure_video_texture(mat):
    """Garante uma textura de imagem no material, que e onde o video aparece no jogo."""
    if video_texture_slot(mat) is not None:
        return
    img = bpy.data.images.get("Video Placeholder") or bpy.data.images.new("Video Placeholder", 16, 16)
    tex = bpy.data.textures.new("Video", 'IMAGE')
    tex.image = img
    slot = mat.texture_slots.add()
    slot.texture = tex
    slot.texture_coords = 'UV'


def create_video_material(ob):
    """Material novo, sem sombra e com a textura do video, aplicado no objeto."""
    mat = bpy.data.materials.new("Video " + ob.name)
    mat.use_shadeless = True
    ensure_video_texture(mat)
    if ob.type == 'MESH':
        if not ob.data.uv_textures:
            ob.data.uv_textures.new()
        if ob.data.materials:
            ob.data.materials[ob.active_material_index] = mat
        else:
            ob.data.materials.append(mat)
    return mat


def _override(context, ob):
    override = context.copy()
    override.update(object=ob, active_object=ob)
    return override


class OBJECT_OT_video_player_add(Operator):
    """Play a video on this object's material or as a fullscreen cutscene"""
    bl_idname = "object.video_player_add"
    bl_label = "Add Video Player"
    bl_options = {'REGISTER', 'UNDO'}

    create_material = bpy.props.BoolProperty(
        name="Create Material and Texture",
        description="Give the object a new material with an image texture for the video to play on",
        default=True)

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
        if self.create_material and ob.type == 'MESH':
            create_video_material(ob)
        if ob.active_material:
            ensure_video_texture(ob.active_material)
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


class OBJECT_OT_video_player_texture(Operator):
    """Add an image texture to the material so the video has where to play"""
    bl_idname = "object.video_player_texture"
    bl_label = "Add Video Texture"
    bl_options = {'REGISTER', 'UNDO'}

    material = bpy.props.StringProperty()

    def execute(self, context):
        mat = bpy.data.materials.get(self.material)
        if mat is None:
            return {'CANCELLED'}
        ensure_video_texture(mat)
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
        wm = context.window_manager
        component = video_component(ob)
        if component is None:
            box = layout.box()
            if ob.type == 'MESH':
                box.prop(wm, "video_player_create_material")
            op = box.operator("object.video_player_add", icon='FILE_MOVIE')
            op.create_material = ob.type == 'MESH' and wm.video_player_create_material
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

        fullscreen = props["Fullscreen"].value

        box = layout.box()
        box.label(text="Video:", icon='FILE_MOVIE')
        row = box.row(align=True)
        row.prop(props["File"], "value", text="File")
        row.operator("object.video_player_file", text="", icon='FILESEL')
        box.prop(props["Fullscreen"], "value", text="Fullscreen Cutscene")
        if not fullscreen:
            if ob.type == 'MESH':
                box.prop_search(props["Material"], "value", ob.data, "materials", text="Material")
                name = props["Material"].value
                mat = bpy.data.materials.get(name) if name else ob.active_material
                if mat is None:
                    box.label(text="The object needs a material to show the video", icon='ERROR')
                elif video_texture_slot(mat) is None:
                    row = box.row()
                    row.label(text="Material has no image texture", icon='ERROR')
                    row.operator("object.video_player_texture", icon='TEXTURE').material = mat.name
            else:
                field(box, "Material")

        box = layout.box()
        split = box.split()
        col = split.column()
        col.label(text="Playback:", icon='PLAY')
        field(col, "Autoplay")
        field(col, "Loop")
        field(col, "Speed")

        col = split.column()
        col.label(text="Sound:", icon='SOUND')
        field(col, "Play Sound")
        sub = col.column()
        sub.active = "Play Sound" in props and props["Play Sound"].value
        field(sub, "Volume")
        if not fullscreen:
            field(sub, "3D Sound")

        if fullscreen:
            box = layout.box()
            split = box.split()
            col = split.column()
            col.label(text="Cutscene:", icon='CAMERA_DATA')
            field(col, "Pause Scene")
            field(col, "Fill Screen")
            col = split.column()
            col.label(text="Skip:", icon='FF')
            field(col, "Skippable")
            sub = col.column()
            sub.active = "Skippable" in props and props["Skippable"].value
            field(sub, "Skip Key", text="Key")

        layout.operator("object.video_player_remove", icon='X')


bpy.types.WindowManager.video_player_create_material = bpy.props.BoolProperty(
    name="Create Material and Texture for Player",
    description="Give the object a new material with an image texture for the video to play on",
    default=True)

classes = (
    OBJECT_OT_video_player_add,
    OBJECT_OT_video_player_remove,
    OBJECT_OT_video_player_texture,
    OBJECT_OT_video_player_file,
    OBJECT_PT_video_player,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
