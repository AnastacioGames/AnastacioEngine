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

# Aba World Sound das Propriedades: os modulos de som do jogo (Music, Ambient) e os arquivos de audio de cada
# um. Os dados ficam no World (World.sound_modules) e o jogo toca tudo por nome pelo gerenciador de audio, que
# continua vivo quando a cena troca.

import os

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator, Panel

MODULE_TYPES = (
    ('MUSIC', "Music", "One track at a time, with crossfade and playlist", 'PLAY_AUDIO', 0),
    ('AMBIENT', "Ambient", "Looping layers that play together", 'FORCE_WIND', 1),
)
MODULE_ICONS = {item[0]: item[3] for item in MODULE_TYPES}
MODULE_NAMES = {item[0]: item[1] for item in MODULE_TYPES}


def _world(context):
    world = getattr(context, "world", None)
    return world if world else context.scene.world


def _module(context, index):
    world = _world(context)
    if world and 0 <= index < len(world.sound_modules):
        return world.sound_modules[index]
    return None


class WORLD_OT_sound_module_add(Operator):
    """Add a sound module to the World"""
    bl_idname = "world.sound_module_add"
    bl_label = "Add Sound Module"
    bl_options = {'REGISTER', 'UNDO'}

    type: EnumProperty(name="Type", items=MODULE_TYPES)

    @classmethod
    def poll(cls, context):
        return _world(context) is not None

    def execute(self, context):
        _world(context).sound_modules.new(MODULE_NAMES[self.type], type=self.type)
        return {'FINISHED'}


class WORLD_OT_sound_module_remove(Operator):
    """Remove this sound module and its sound list (the audio files stay on disk)"""
    bl_idname = "world.sound_module_remove"
    bl_label = "Remove Sound Module"
    bl_options = {'REGISTER', 'UNDO'}

    module: IntProperty(options={'HIDDEN'})

    def execute(self, context):
        module = _module(context, self.module)
        if module is None:
            return {'CANCELLED'}
        _world(context).sound_modules.remove(module)
        return {'FINISHED'}


class WORLD_OT_sound_module_move(Operator):
    """Move this sound module up or down"""
    bl_idname = "world.sound_module_move"
    bl_label = "Move Sound Module"
    bl_options = {'REGISTER', 'UNDO'}

    module: IntProperty(options={'HIDDEN'})
    direction: EnumProperty(items=(('UP', "Up", ""), ('DOWN', "Down", "")), options={'HIDDEN'})

    def execute(self, context):
        world = _world(context)
        target = self.module + (-1 if self.direction == 'UP' else 1)
        if world is None or not (0 <= self.module < len(world.sound_modules) and
                                 0 <= target < len(world.sound_modules)):
            return {'CANCELLED'}
        world.sound_modules.move(self.module, target)
        return {'FINISHED'}


class WORLD_OT_sound_entry_add(Operator):
    """Add audio files to this sound module"""
    bl_idname = "world.sound_entry_add"
    bl_label = "Add Sounds"
    bl_options = {'REGISTER', 'UNDO'}

    module: IntProperty(options={'HIDDEN'})

    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    filter_sound: BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_folder: BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    relative_path: BoolProperty(
        name="Relative Path",
        description="Store the path relative to the .range, so the game folder can be moved",
        default=True,
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        module = _module(context, self.module)
        if module is None:
            return {'CANCELLED'}

        added = 0
        for item in self.files:
            if not item.name:
                continue
            path = os.path.join(self.directory, item.name)
            if self.relative_path and bpy.data.is_saved:
                try:
                    path = bpy.path.relpath(path)
                except ValueError:  # another drive on Windows: keep it absolute
                    pass
            module.sounds.new(os.path.splitext(item.name)[0], filepath=path)
            added += 1

        if not added:
            self.report({'WARNING'}, "No audio file selected")
            return {'CANCELLED'}
        if self.relative_path and not bpy.data.is_saved:
            self.report({'INFO'}, "Paths kept absolute: save the .range to store them relative")
        return {'FINISHED'}


class WORLD_OT_sound_entry_remove(Operator):
    """Remove this sound from the module (the audio file stays on disk)"""
    bl_idname = "world.sound_entry_remove"
    bl_label = "Remove Sound"
    bl_options = {'REGISTER', 'UNDO'}

    module: IntProperty(options={'HIDDEN'})
    sound: IntProperty(options={'HIDDEN'})

    def execute(self, context):
        module = _module(context, self.module)
        if module is None or not 0 <= self.sound < len(module.sounds):
            return {'CANCELLED'}
        module.sounds.remove(module.sounds[self.sound])
        return {'FINISHED'}


class WORLD_OT_sound_entry_move(Operator):
    """Move this sound up or down in the play order"""
    bl_idname = "world.sound_entry_move"
    bl_label = "Move Sound"
    bl_options = {'REGISTER', 'UNDO'}

    module: IntProperty(options={'HIDDEN'})
    sound: IntProperty(options={'HIDDEN'})
    direction: EnumProperty(items=(('UP', "Up", ""), ('DOWN', "Down", "")), options={'HIDDEN'})

    def execute(self, context):
        module = _module(context, self.module)
        target = self.sound + (-1 if self.direction == 'UP' else 1)
        if module is None or not (0 <= self.sound < len(module.sounds) and 0 <= target < len(module.sounds)):
            return {'CANCELLED'}
        module.sounds.move(self.sound, target)
        return {'FINISHED'}


def _draw_sounds(layout, module, module_index):
    row = layout.row()
    row.label(text="Tracks:" if module.type == 'MUSIC' else "Layers:")
    row.operator("world.sound_entry_add", text="Add Sounds", icon='ZOOMIN').module = module_index

    if not module.sounds:
        layout.label(text="No sound yet: click Add Sounds to pick the audio files", icon='INFO')
        return

    for index, sound in enumerate(module.sounds):
        box = layout.box()
        row = box.row(align=True)
        row.prop(sound, "name", text="", icon='SOUND')
        for direction, icon in (('UP', 'TRIA_UP'), ('DOWN', 'TRIA_DOWN')):
            move = row.operator("world.sound_entry_move", text="", icon=icon)
            move.module = module_index
            move.sound = index
            move.direction = direction
        remove = row.operator("world.sound_entry_remove", text="", icon='X')
        remove.module = module_index
        remove.sound = index
        box.prop(sound, "filepath", text="")
        row = box.row(align=True)
        row.prop(sound, "volume", slider=True)
        row.prop(sound, "pitch")


def _draw_module(layout, module, index):
    box = layout.box()
    row = box.row(align=True)
    row.prop(module, "show_expanded", text="", emboss=False,
             icon='TRIA_DOWN' if module.show_expanded else 'TRIA_RIGHT')
    row.prop(module, "name", text="", icon=MODULE_ICONS.get(module.type, 'SOUND'))
    row.prop(module, "mute", text="", icon='MUTE_IPO_ON' if module.mute else 'MUTE_IPO_OFF')
    for direction, icon in (('UP', 'TRIA_UP'), ('DOWN', 'TRIA_DOWN')):
        move = row.operator("world.sound_module_move", text="", icon=icon)
        move.module = index
        move.direction = direction
    row.operator("world.sound_module_remove", text="", icon='X').module = index

    if not module.show_expanded:
        return

    col = box.column()
    col.active = not module.mute
    col.prop(module, "type")
    row = col.row(align=True)
    row.prop(module, "volume", slider=True)
    row.prop(module, "fade_time", text="Fade")
    row = col.row()
    row.prop(module, "use_autoplay")
    if module.type == 'MUSIC':
        row.prop(module, "use_shuffle")
        row.prop(module, "use_loop")
    col.prop(module, "use_reverb_areas")

    col.separator()
    _draw_sounds(col, module, index)


class WorldSoundButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "world_sound"


class WORLD_SOUND_PT_modules(WorldSoundButtonsPanel, Panel):
    bl_label = "Sound Modules"

    def draw(self, context):
        layout = self.layout
        world = _world(context)

        if world is None:
            layout.label(text="This scene has no World: create one in the World tab", icon='ERROR')
            return

        layout.operator_menu_enum("world.sound_module_add", "type", text="Add Sound Module", icon='ZOOMIN')

        if not world.sound_modules:
            layout.label(text="No module yet: add Music for the soundtrack or Ambient for wind, rain...",
                         icon='INFO')
            return

        for index, module in enumerate(world.sound_modules):
            _draw_module(layout, module, index)


classes = (
    WORLD_OT_sound_module_add,
    WORLD_OT_sound_module_remove,
    WORLD_OT_sound_module_move,
    WORLD_OT_sound_entry_add,
    WORLD_OT_sound_entry_remove,
    WORLD_OT_sound_entry_move,
    WORLD_SOUND_PT_modules,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
