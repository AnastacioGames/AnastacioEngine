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
from bpy.types import Panel, UIList


class CUTSCENE_UL_sequences(UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
		split = layout.split(factor=0.15, align=True)
		split.prop(item, "cutscene_id", text="", icon="SEQUENCE")
		split.prop(item, "name", text="")


class CutsceneButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'cutscene'
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}


def active_sequence(settings):
    index = settings.active_sequence_index
    if 0 <= index < len(settings.sequences):
        return settings.sequences[index]
    return None


def active_event(settings, sequence):
    if sequence is None:
        return None

    index = settings.active_event_index
    if 0 <= index < len(sequence.events):
        return sequence.events[index]
    return None


class CUTSCENE_PT_sequences(CutsceneButtonsPanel, Panel):
    bl_label = "Cutscene Sequences"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.cutscene_settings

    def draw(self, context):
        layout = self.layout
        settings = context.scene.cutscene_settings
        sequence_index = settings.active_sequence_index

        row = layout.row()
        row.template_list("CUTSCENE_UL_sequences", "cutscene_sequences", settings, "sequences",
                          settings, "active_sequence_index", rows=4)

        col = row.column(align=True)
        col.operator("cutscene.sequence_add", icon='ZOOMIN', text="")

        actions = col.column(align=True)
        actions.enabled = 0 <= sequence_index < len(settings.sequences)
        remove = actions.operator("cutscene.sequence_remove", icon='ZOOMOUT', text="")
        remove.index = sequence_index

        actions.separator()
        duplicate = actions.operator("cutscene.sequence_duplicate", text="Duplicate")
        duplicate.index = sequence_index

        move_up = actions.operator("cutscene.sequence_move", icon='TRIA_UP', text="")
        move_up.index = sequence_index
        move_up.direction = 'UP'
        move_down = actions.operator("cutscene.sequence_move", icon='TRIA_DOWN', text="")
        move_down.index = sequence_index
        move_down.direction = 'DOWN'


class CUTSCENE_PT_events(CutsceneButtonsPanel, Panel):
    bl_label = "Cutscene Events"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.cutscene_settings

    def draw(self, context):
        layout = self.layout
        settings = context.scene.cutscene_settings
        sequence_index = settings.active_sequence_index
        sequence = active_sequence(settings)

        if sequence is None:
            layout.label("Select a cutscene sequence to add events.", icon='INFO')
            return

        event_index = settings.active_event_index
        row = layout.row()
        row.template_list("UI_UL_list", "cutscene_events", sequence, "events",
                          settings, "active_event_index", rows=4)

        col = row.column(align=True)
        add = col.operator("cutscene.event_add", icon='ZOOMIN', text="")
        add.sequence_index = sequence_index

        actions = col.column(align=True)
        actions.enabled = 0 <= event_index < len(sequence.events)
        remove = actions.operator("cutscene.event_remove", icon='ZOOMOUT', text="")
        remove.sequence_index = sequence_index
        remove.event_index = event_index

        actions.separator()
        duplicate = actions.operator("cutscene.event_duplicate", text="Duplicate")
        duplicate.sequence_index = sequence_index
        duplicate.event_index = event_index

        move_up = actions.operator("cutscene.event_move", icon='TRIA_UP', text="")
        move_up.sequence_index = sequence_index
        move_up.event_index = event_index
        move_up.direction = 'UP'
        move_down = actions.operator("cutscene.event_move", icon='TRIA_DOWN', text="")
        move_down.sequence_index = sequence_index
        move_down.event_index = event_index
        move_down.direction = 'DOWN'


class CUTSCENE_PT_event(CutsceneButtonsPanel, Panel):
    bl_label = "Event"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.cutscene_settings

    def draw(self, context):
        layout = self.layout
        settings = context.scene.cutscene_settings
        event = active_event(settings, active_sequence(settings))

        if event is None:
            layout.label("Select a cutscene event to edit.", icon='INFO')
            return

        layout.prop(event, "name")
        layout.prop(event, "time")
        layout.prop(event, "type")

        if event.type == 'SPAWN_OBJECT':
            box = layout.box()
            box.label("Spawn Object")

            template = box.row()
            template.alert = event.template_object is None
            template.prop(event, "template_object")

            spawn_point = box.row()
            spawn_point.alert = event.spawn_point is None
            spawn_point.prop(event, "spawn_point")

            box.prop(event, "dependent_object")

            if event.template_object is None or event.spawn_point is None:
                box.label("Template Object and Spawn Point are required.", icon='ERROR')

        elif event.type == 'DIALOG':
            box = layout.box()
            box.label("Dialog")
            box.prop(event, "dialog_text_en")
            box.prop(event, "dialog_text_pt")
            box.prop(event, "dialog_text_es")
            box.prop(event, "dialog_text_ru")
            box.prop(event, "dialog_audio_path")
            box.prop(event, "dialog_live")

        elif event.type == 'HIDE_DIALOG':
            layout.box().label("Hides the current dialog. No parameters.")

        elif event.type == 'CAMERA_SHOT':
            box = layout.box()
            box.label("Camera Shot")
            box.prop(event, "camera_order")

        elif event.type == 'LOOK_AT':
            box = layout.box()
            box.label("Look At")
            target = box.row()
            target.alert = event.look_at_target is None
            target.prop(event, "look_at_target")

        elif event.type == 'RESTORE_GAMEPLAY_CAMERA':
            layout.box().label("Restores the gameplay camera. No parameters.")

        elif event.type == 'CAMERA_START':
            layout.box().label("Starts the cutscene camera manager. No parameters.")

        elif event.type == 'CAMERA_STOP':
            layout.box().label("Stops the cutscene camera manager. No parameters.")

        elif event.type == 'LOCK_PLAYER':
            layout.box().label("Locks player input. No parameters.")

        elif event.type == 'UNLOCK_PLAYER':
            layout.box().label("Unlocks player input. No parameters.")

        elif event.type == 'PLAYER_ANIM':
            box = layout.box()
            box.label("Player Anim")
            box.prop(event, "player_anim_name")
            box.prop(event, "player_anim_blend")

        elif event.type == 'SHOW_MOUSE':
            layout.box().label("Shows the mouse cursor. No parameters.")

        elif event.type == 'HIDE_MOUSE':
            layout.box().label("Hides the mouse cursor. No parameters.")

        elif event.type == 'CHANGE_SCENE':
            box = layout.box()
            box.label("Change Scene")
            box.prop_search(event, "change_scene_name", bpy.data, "scenes")

        elif event.type == 'WAIT_TIME':
            box = layout.box()
            box.label("Wait Time")
            box.prop(event, "wait_seconds")

        elif event.type == 'WAIT_TRIGGER':
            box = layout.box()
            box.label("Wait Trigger")
            box.prop(event, "trigger_name")

        elif event.type == 'WAIT_CAMERA_END':
            layout.box().label("Waits until the current camera shot finishes. No parameters.")


classes = (
    CUTSCENE_UL_sequences,
    CUTSCENE_PT_sequences,
    CUTSCENE_PT_events,
    CUTSCENE_PT_event,
)


if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
