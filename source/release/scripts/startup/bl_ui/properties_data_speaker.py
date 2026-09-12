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
from bpy.types import Panel
from rna_prop_ui import PropertyPanel


class DataButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        engine = context.scene.render.engine
        return context.speaker and (engine in cls.COMPAT_ENGINES)


class DATA_PT_context_speaker(DataButtonsPanel, Panel):
    bl_label = ""
    bl_options = {'HIDE_HEADER'}
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        ob = context.object
        speaker = context.speaker
        space = context.space_data

        split = layout.split(factor=0.65)

        if ob:
            split.template_ID(ob, "data")
        elif speaker:
            split.template_ID(space, "pin_id")


class DATA_PT_speaker(DataButtonsPanel, Panel):
    bl_label = "Sound"
    COMPAT_ENGINES = {"BLENDER_RENDER", "BLENDER_GAME"}

    def draw(self, context):
        layout = self.layout

        speaker = context.speaker

        box = layout.box()
        box.label(text="Sound:", icon="SPEAKER")
        split = box.split(factor=0.75)

        split.template_ID(speaker, "sound", open="sound.open_mono")
        split.prop(speaker, "muted")

        row = box.row()
        row.prop(speaker, "volume")
        row.prop(speaker, "pitch")

        box = layout.box()
        box.label(text="Playback:", icon="SETTINGS")
        flow = box.grid_flow(row_major=True, num_columns=2, even_columns=True, even_rows=False, align=False)
        flow.use_property_decorate = False
        flow.use_property_split = True

        flow.prop(speaker, "start_init")
        flow.prop(speaker, "start_at")
        flow.prop(speaker, "destroy_after")
        flow.prop(speaker, "mode")
        flow.prop(speaker, "use_sound_3d")
        flow.prop(speaker, "cache")

class DATA_PT_distance(DataButtonsPanel, Panel):
    bl_label = "Distance"
    COMPAT_ENGINES = {"BLENDER_RENDER", "BLENDER_GAME"}

    def draw(self, context):
        layout = self.layout

        speaker = context.speaker

        box = layout.box()
        box.label(text="Distance:", icon="OUTLINER_OB_FORCE_FIELD")
        split = box.split()

        col = split.column()
        col.label("Volume:", icon="OUTLINER_OB_SPEAKER")
        col.prop(speaker, "volume_min", text="Minimum")
        col.prop(speaker, "volume_max", text="Maximum")
        col.prop(speaker, "attenuation")

        col = split.column()
        col.label("Distance:", icon="OUTLINER_OB_FORCE_FIELD")
        col.prop(speaker, "distance_max", text="Maximum")
        col.prop(speaker, "distance_reference", text="Reference")


class DATA_PT_cone(DataButtonsPanel, Panel):
    bl_label = "Cone"
    COMPAT_ENGINES = {"BLENDER_RENDER", "BLENDER_GAME"}

    def draw(self, context):
        layout = self.layout

        speaker = context.speaker

        box = layout.box()
        box.label(text="Cone:", icon="MESH_TORUS")
        split = box.split()

        col = split.column()
        col.label("Angle:", icon="MESH_TORUS")
        col.prop(speaker, "cone_angle_outer", text="Outer")
        col.prop(speaker, "cone_angle_inner", text="Inner")

        col = split.column()
        col.label("Volume:", icon="PROP_ON")
        col.prop(speaker, "cone_volume_outer", text="Outer")


class DATA_PT_custom_props_speaker(DataButtonsPanel, PropertyPanel, Panel):
    COMPAT_ENGINES = {"BLENDER_RENDER", "BLENDER_GAME"}
    _context_path = "object.data"
    _property_type = bpy.types.Speaker


classes = (
    DATA_PT_context_speaker,
    DATA_PT_speaker,
    DATA_PT_distance,
    DATA_PT_cone,
    # DATA_PT_custom_props_speaker,  # disabled: Custom Properties panel unused
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
