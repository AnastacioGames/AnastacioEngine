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

# Aba World Sound das Propriedades: os modulos de som do jogo (Music, Ambient, Effects) e os arquivos de audio de
# cada um. No Effects o motor toca sozinho (explosao, destruicao, chuva, trovao) pelo Event de cada som. Os dados ficam no World (World.sound_modules) e o jogo toca tudo por nome pelo gerenciador de audio, que
# continua vivo quando a cena troca.

import os

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator, Panel

MODULE_TYPES = (
    ('MUSIC', "Music", "One track at a time, with crossfade and playlist", 'PLAY_AUDIO', 0),
    ('AMBIENT', "Ambient", "Looping layers that play together", 'FORCE_WIND', 1),
    ('EFFECTS', "Effects", "Sounds the engine plays by itself (explosions, destruction, rain, thunder)",
     'MOD_EXPLODE', 2),
)

# Slots criados com um modulo Effects novo, sem arquivo: o usuario so escolhe o audio de cada um.
EFFECT_SLOTS = (
    ("Explosion Tiny", 'EXPLOSION_TINY'),
    ("Explosion Small", 'EXPLOSION_SMALL'),
    ("Explosion Medium", 'EXPLOSION_MEDIUM'),
    ("Explosion Large", 'EXPLOSION_LARGE'),
    ("Explosion Huge", 'EXPLOSION_HUGE'),
    ("Destruction Tiny", 'DESTRUCTION_TINY'),
    ("Destruction Small", 'DESTRUCTION_SMALL'),
    ("Destruction Medium", 'DESTRUCTION_MEDIUM'),
    ("Destruction Large", 'DESTRUCTION_LARGE'),
    ("Destruction Huge", 'DESTRUCTION_HUGE'),
    ("Rain", 'RAIN'),
    ("Thunder 1", 'THUNDER'),
    ("Thunder 2", 'THUNDER'),
    ("Thunder 3", 'THUNDER'),
)
# Som que vem com a engine (datafiles/sounds/effects) para cada slot do Effects.
ENGINE_EFFECT_FILES = {
    "Explosion Tiny": "explosao_tiny.wav",
    "Explosion Small": "explosao_small.wav",
    "Explosion Medium": "explosao_medium.wav",
    "Explosion Large": "explosao_large.wav",
    "Explosion Huge": "explosao_huge.wav",
    "Destruction Tiny": "quebra_tiny.wav",
    "Destruction Small": "quebra_small.wav",
    "Destruction Medium": "quebra_medium.wav",
    "Destruction Large": "quebra_large.wav",
    "Destruction Huge": "quebra_huge.wav",
    "Rain": "chuva.wav",
    "Thunder 1": "trovao1.wav",
    "Thunder 2": "trovao2.wav",
    "Thunder 3": "trovao3.wav",
}
# Event pelo nome do arquivo no Add Sounds (chuva.wav -> Rain), para nao ficar mudo.
ENGINE_EFFECT_EVENTS = {os.path.splitext(f)[0]: dict(EFFECT_SLOTS)[slot] for slot, f in ENGINE_EFFECT_FILES.items()}
MODULE_ICONS = {item[0]: item[3] for item in MODULE_TYPES}
MODULE_NAMES = {item[0]: item[1] for item in MODULE_TYPES}

# Filtro dos botoes Music / Ambient do painel: so estado da tela (WindowManager), nao vai para o .range.
bpy.types.WindowManager.world_sound_filter = EnumProperty(
    name="Module Filter",
    description="Show only the modules of this type",
    items=MODULE_TYPES,
    default='EFFECTS',
)


def _world(context):
    world = getattr(context, "world", None)
    return world if world else context.scene.world


def _module(context, index):
    world = _world(context)
    if world and 0 <= index < len(world.sound_modules):
        return world.sound_modules[index]
    return None


def _engine_datafiles_dir():
    """Pasta datafiles instalada com a engine (sons de exemplo ficam em datafiles/sounds)."""
    base = bpy.utils.resource_path('LOCAL')
    return os.path.normpath(os.path.join(base, "datafiles", "sounds"))


def _localize_engine_sound(path):
    """Se o arquivo escolhido vem de dentro da engine (datafiles/sounds), copia para a pasta
    do projeto: o jogo exportado so leva o que esta em data/ do projeto, nao o instalador da
    engine. Devolve o caminho a usar (copiado, ou o original se nao for da engine)."""
    abs_path = os.path.abspath(path)
    engine_dir = _engine_datafiles_dir()
    try:
        inside_engine = os.path.commonpath([abs_path, engine_dir]) == engine_dir
    except ValueError:  # outra unidade no Windows
        inside_engine = False
    if not inside_engine or not bpy.data.is_saved:
        return path

    import shutil
    project_dir = os.path.dirname(bpy.data.filepath)
    dest_dir = os.path.join(project_dir, "sounds")
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, os.path.basename(abs_path))
    if not os.path.exists(dest_path):
        shutil.copy2(abs_path, dest_path)
    return dest_path


def _fill_engine_effects(module):
    """Slots do Effects sem arquivo recebem o som que vem com a engine. Devolve quantos."""
    effects_dir = os.path.join(_engine_datafiles_dir(), "effects")
    filled = 0
    for sound in module.sounds:
        if sound.filepath:
            continue
        filename = ENGINE_EFFECT_FILES.get(sound.name)
        if not filename:
            continue
        path = os.path.join(effects_dir, filename)
        if not os.path.isfile(path):
            continue
        path = _localize_engine_sound(path)
        if bpy.data.is_saved:
            try:
                path = bpy.path.relpath(path)
            except ValueError:
                pass
        sound.filepath = path
        filled += 1
    return filled


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
        module = _world(context).sound_modules.new(MODULE_NAMES[self.type], type=self.type)
        if self.type == 'EFFECTS':
            for name, event in EFFECT_SLOTS:
                module.sounds.new(name, filepath="").event = event
            _fill_engine_effects(module)
        context.window_manager.world_sound_filter = self.type
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
            path = _localize_engine_sound(path)
            if self.relative_path and bpy.data.is_saved:
                try:
                    path = bpy.path.relpath(path)
                except ValueError:  # another drive on Windows: keep it absolute
                    pass
            sound = module.sounds.new(os.path.splitext(item.name)[0], filepath=path)
            if module.type == 'EFFECTS':
                event = ENGINE_EFFECT_EVENTS.get(os.path.splitext(item.name)[0].lower())
                if event:
                    sound.event = event
            added += 1

        if not added:
            self.report({'WARNING'}, "No audio file selected")
            return {'CANCELLED'}
        if self.relative_path and not bpy.data.is_saved:
            self.report({'INFO'}, "Paths kept absolute: save the .range to store them relative")
        return {'FINISHED'}


class WORLD_OT_sound_engine_fill(Operator):
    """Give every empty slot (Rain, Thunder, Explosion...) the sound that comes with the engine"""
    bl_idname = "world.sound_engine_fill"
    bl_label = "Use Engine Sounds"
    bl_options = {'REGISTER', 'UNDO'}

    module: IntProperty(options={'HIDDEN'})

    def execute(self, context):
        module = _module(context, self.module)
        if module is None:
            return {'CANCELLED'}
        filled = _fill_engine_effects(module)
        if not filled:
            self.report({'INFO'}, "No empty slot with an engine sound")
            return {'CANCELLED'}
        if not bpy.data.is_saved:
            self.report({'INFO'}, "Save the .range to copy the sounds into the project folder")
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


class WORLD_OT_sound_entry_variation(Operator):
    """Add another sound for the same event: the engine picks one at random, so it doesn't repeat"""
    bl_idname = "world.sound_entry_variation"
    bl_label = "Add Variation"
    bl_options = {'REGISTER', 'UNDO'}

    module: IntProperty(options={'HIDDEN'})
    sound: IntProperty(options={'HIDDEN'})

    def execute(self, context):
        module = _module(context, self.module)
        if module is None or not 0 <= self.sound < len(module.sounds):
            return {'CANCELLED'}
        source = module.sounds[self.sound]
        base = source.name.rstrip("0123456789").rstrip() or source.name
        number = sum(1 for sound in module.sounds if sound.event == source.event) + 1
        sound = module.sounds.new("%s %d" % (base, number), filepath="")
        sound.event = source.event
        sound.volume = source.volume
        module.sounds.move(len(module.sounds) - 1, self.sound + 1)
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
    effects = module.type == 'EFFECTS'
    row = layout.row()
    row.label(text={'MUSIC': "Tracks:", 'AMBIENT': "Layers:"}.get(module.type, "Sounds:"))
    row.operator("world.sound_entry_add", text="Add Sounds", icon='ZOOMIN').module = module_index

    if not module.sounds:
        layout.label(text="No sound yet: click Add Sounds to pick the audio files", icon='INFO')
        return

    for index, sound in enumerate(module.sounds):
        box = layout.box()
        row = box.row(align=True)
        row.prop(sound, "show_expanded", text="", emboss=False,
                 icon='TRIA_DOWN' if sound.show_expanded else 'TRIA_RIGHT')
        row.prop(sound, "name", text="", icon='SOUND')
        if not sound.show_expanded:
            # Fechado: so o estado do arquivo, para achar rapido o slot que falta.
            if sound.filepath:
                row.label(text=os.path.basename(bpy.path.abspath(sound.filepath)), icon='FILE_SOUND')
            else:
                row.label(text="No file", icon='ERROR' if effects else 'INFO')
        for direction, icon in (('UP', 'TRIA_UP'), ('DOWN', 'TRIA_DOWN')):
            move = row.operator("world.sound_entry_move", text="", icon=icon)
            move.module = module_index
            move.sound = index
            move.direction = direction
        if effects:
            variation = row.operator("world.sound_entry_variation", text="", icon='ZOOMIN')
            variation.module = module_index
            variation.sound = index
        remove = row.operator("world.sound_entry_remove", text="", icon='X')
        remove.module = module_index
        remove.sound = index
        if not sound.show_expanded:
            continue
        if effects:
            box.prop(sound, "event")
        box.prop(sound, "filepath", text="")
        if effects and not sound.filepath:
            box.label(text="No file yet: silent until you pick one", icon='INFO')
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
    row = col.row(align=True)
    row.prop(module, "volume", slider=True)
    if module.type == 'EFFECTS':
        col.label(text="Every play is a new voice: a sound never cuts the one before", icon='INFO')
        col.label(text="Same Event on several sounds = variations picked at random", icon='INFO')
        col.prop(module, "use_reverb_areas")
        if any(not s.filepath and s.name in ENGINE_EFFECT_FILES for s in module.sounds):
            col.operator("world.sound_engine_fill", icon='FILE_SOUND').module = index
        col.separator()
        _draw_sounds(col, module, index)
        return
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
            layout.label(text="No module yet: Music for the soundtrack, Ambient for wind, Effects for explosions...",
                         icon='INFO')
            return

        wm = context.window_manager
        layout.row().prop(wm, "world_sound_filter", expand=True)

        shown = [(index, module) for index, module in enumerate(world.sound_modules)
                 if module.type == wm.world_sound_filter]
        if not shown:
            label = MODULE_NAMES[wm.world_sound_filter]
            layout.label(text="No %s module yet: use Add Sound Module" % label.lower(), icon='INFO')
            return

        for index, module in shown:
            _draw_module(layout, module, index)


classes = (
    WORLD_OT_sound_module_add,
    WORLD_OT_sound_module_remove,
    WORLD_OT_sound_module_move,
    WORLD_OT_sound_entry_add,
    WORLD_OT_sound_engine_fill,
    WORLD_OT_sound_entry_remove,
    WORLD_OT_sound_entry_variation,
    WORLD_OT_sound_entry_move,
    WORLD_SOUND_PT_modules,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
