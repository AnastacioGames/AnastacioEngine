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

# Game: World tab (world, environment lighting, mist).
# Split out of properties_game.py, which still registers every class in order.

class WorldButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "world"


class WORLD_PT_game_context_world(WorldButtonsPanel, Panel):
    bl_label = ""
    bl_options = {'HIDE_HEADER'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (context.scene) and (rd.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        world = context.world
        space = context.space_data

        split = layout.split(factor=0.65)
        if scene:
            split.template_ID(scene, "world", new="world.new")
        elif world:
            split.template_ID(space, "pin_id")


class WORLD_PT_game_world(WorldButtonsPanel, Panel):
    bl_label = "World"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        self.layout.template_preview(context.world)

        world = context.world

        world_panel = layout.box()
        background_panel = world_panel.box()
        background_panel.label(text="Background Colors:", icon="COLOR")
        sky_panel = background_panel.box()
        sky_box = sky_panel
        sky_box.label(text="Sky Render:", icon="WORLD")

        row = sky_box.row()
        row.prop(world, "use_sky_paper")
        row.prop(world, "use_sky_blend")
        row = sky_box.row()
        row.prop(world, "use_sky_real")
        row.prop(world, "use_sky_stars")
        row.prop(world, "use_sky_atmospheric")
        
        row = sky_box.row()
        col = row.column()
        col.prop(world, "horizon_color", text="Horizon/Ambient Color" if not world.use_sky_atmospheric else "Fog/Ambient Color")
        col.prop(world, "ambient_color", text="")
        col = row.column()
        col.prop(world, "zenith_color", text="Zenith/Nadir Color" if not world.use_sky_atmospheric else "Extinction/Inscattering Color")
        col.prop(world, "nadir_color", text="")
        col.active = world.use_sky_blend

        row = sky_box.row()
        row.prop(world, "sun_size")
        if not world.use_sky_atmospheric:
            row.prop(world, "sky_turbidity")
            row.prop(world, "ground_color")

        environment_panel = world_panel.box()
        environment_box = environment_panel.box()
        environment_box.label(text="Environment:", icon="WORLD")
        row = environment_box.row()
        row.prop(world, "exposure", text="Camera Exposure")
        row.prop(world, "color_range")


class WORLD_PT_game_environment_lighting(WorldButtonsPanel, Panel):
    bl_label = "Environment Lighting"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES)

    def draw_header(self, context):
        light = context.world.light_settings
        self.layout.prop(light, "use_environment_light", text="")

    def draw(self, context):
        layout = self.layout

        light = context.world.light_settings

        layout.active = light.use_environment_light

        split = layout.split()
        split.prop(light, "environment_energy", text="Energy")
        split.prop(light, "environment_color", text="")


class WORLD_PT_game_mist(WorldButtonsPanel, Panel):
    bl_label = "Fog"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES)

    def draw_header(self, context):
        world = context.world

        self.layout.prop(world.mist_settings, "use_mist", text="")

    def draw(self, context):
        layout = self.layout

        world = context.world

        layout.active = world.mist_settings.use_mist

        # Keep the enum choices immediately visible as compact button groups.
        panel = layout.box()
        box = panel.box()
        box.label(text="Sky Render:", icon="WORLD")

        row = box.row()
        row.label(text="Blend Mode:")
        row = layout.row(align=True)
        row.prop(world.mist_settings, "mist_blend_type", expand=True)

        row = box.row()
        row.label(text="Falloff:")
        row = layout.row(align=True)
        row.prop(world.mist_settings, "falloff", expand=True)

        # Distance is a nested section, matching the other grouped settings.
        box = layout.box()
        box.label(text="Distance:", icon='SCENE_DATA')
        row = box.row(align=True)
        row.prop(world.mist_settings, "start")
        row.prop(world.mist_settings, "depth")
        
        if world.mist_settings.falloff == 'HEIGHT':
            row = box.row(align=True)
            row.prop(world.mist_settings, "height_fog")
            row.prop(world.mist_settings, "density_fog")

        row = box.row()
        row.prop(world.mist_settings, "intensity", text="Minimum Intensity")
