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

# Game: Scene tab (physics, export, network, navmesh).
# Split out of properties_game.py, which still registers every class in order.

class SceneButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"


class SCENE_PT_game_physics(SceneButtonsPanel, Panel):
    bl_label = "Game Settings"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        gs = scene.game_settings

        main_box = layout.box()
        main_box.label(text="Game Settings:", icon="SCENE_DATA")

        # ---- Physics ----
        row = main_box.row(align=True)
        row.prop(scene, "show_expanded_game_physics", text="Physics",
                 icon='TRIA_DOWN' if scene.show_expanded_game_physics else 'TRIA_RIGHT', emboss=True)

        if scene.show_expanded_game_physics:
            box = main_box.box()
            box.label(text="Physics Engine:", icon="PHYSICS")
            box.prop(gs, "physics_engine", text="Physics Engine")
            if gs.physics_engine != 'NONE':
                box.prop(gs, "physics_solver", text="Solver", icon="PHYSICS")
                box.prop(gs, "physics_gravity", text="Gravity")

            box = main_box.box()
            box.label(text="Steps & Timing:", icon="TIME")
            split = box.split()

            col = split.column()
            col.label(text="Game Rate:")
            col.prop(gs, "fps", text="FPS")
            col.prop(gs, "time_scale")

            col = split.column()
            col.label(text="Per Frame:")
            if gs.physics_engine != 'NONE':
                col.prop(gs, "physics_step_sub", text="Physics Substeps")
            col.prop(gs, "sleep_timer", text="Max Logic Frames")

            box.prop(gs, "use_fixed_timestep")

            if gs.physics_engine != 'NONE':
                box = main_box.box()
                box.label(text="Deactivation (Sleeping Objects):", icon="SNAP_FACE")
                col = box.column()
                sub = col.row(align=True)
                sub.prop(gs, "deactivation_linear_threshold", text="Linear Threshold")
                sub.prop(gs, "deactivation_angular_threshold", text="Angular Threshold")
                sub = col.row()
                sub.prop(gs, "deactivation_time", text="Time")

                box = main_box.box()
                box.label(text="Destruction:", icon="MOD_EXPLODE")
                box.prop(gs, "max_debris")

                box = main_box.box()
                box.label(text="Culling:", icon="RESTRICT_RENDER_OFF")
                split = box.split()

                col = split.column()
                col.label(text="Render:")
                col.prop(gs, "shadows_on_off", text="Shadow Culling")
                col.prop(gs, "use_occlusion_culling", text="Occlusion Culling")
                sub = col.column()
                sub.active = gs.use_occlusion_culling
                sub.prop(gs, "occlusion_culling_resolution", text="Resolution")

                col = split.column()
                col.label(text="Object Activity:")
                col.prop(gs, "use_activity_culling")

        # ---- Obstacle Simulation ----
        row = main_box.row(align=True)
        row.prop(scene, "show_expanded_game_obstacles", text="Obstacle Simulation",
                 icon='TRIA_DOWN' if scene.show_expanded_game_obstacles else 'TRIA_RIGHT', emboss=True)

        if scene.show_expanded_game_obstacles:
            box = main_box.box()
            box.label(text="Used by the Steering actuator to avoid obstacles", icon='INFO')
            box.prop(gs, "obstacle_simulation", text="Simulation")
            if gs.obstacle_simulation != 'NONE':
                box.prop(gs, "level_height", text="Level Height")
                box.prop(gs, "show_obstacle_simulation", text="Show Debug Visualization")

        # ---- LOD Hysteresis ----
        row = main_box.row(align=True)
        row.prop(scene, "show_expanded_game_lod", text="Level of Detail",
                 icon='TRIA_DOWN' if scene.show_expanded_game_lod else 'TRIA_RIGHT', emboss=True)

        if scene.show_expanded_game_lod:
            box = main_box.box()
            box.label(text="The levels are set per object, in the Object tab", icon='INFO')
            row = box.row()
            row.prop(gs, "use_scene_hysteresis", text="Hysteresis")
            row = box.row()
            row.active = gs.use_scene_hysteresis
            row.prop(gs, "scene_hysteresis_percentage", text="")

            row = box.row()
            row.prop(gs, "use_auto_static_batch")

        # ---- Python Console ----
        row = main_box.row(align=True)
        row.prop(scene, "show_expanded_game_console", text="Python Console",
                 icon='TRIA_DOWN' if scene.show_expanded_game_console else 'TRIA_RIGHT', emboss=True)

        if scene.show_expanded_game_console:
            box = main_box.box()
            box.prop(gs, "use_python_console", text="Enable Python Console")
            col = box.column()
            col.active = gs.use_python_console
            col.label(text="Hold all keys during the game to open it in the system console", icon='INFO')
            row = col.row(align=True)
            row.label(text="Keys:")
            row.prop(gs, "python_console_key1", text="", event=True)
            row.prop(gs, "python_console_key2", text="", event=True)
            row.prop(gs, "python_console_key3", text="", event=True)
            row.prop(gs, "python_console_key4", text="", event=True)

        # ---- Audio ----
        row = main_box.row(align=True)
        row.prop(scene, "show_expanded_game_audio", text="Audio",
                 icon='TRIA_DOWN' if scene.show_expanded_game_audio else 'TRIA_RIGHT', emboss=True)

        if scene.show_expanded_game_audio:
            box = main_box.box()
            col = box.column()
            col.prop(scene, "audio_distance_model", text="Distance Model")
            col = box.column(align=True)
            col.prop(scene, "audio_doppler_speed", text="Speed of Sound (m/s)")
            col.prop(scene, "audio_doppler_factor", text="Doppler Factor")
            # LA_Launcher applies these once, from the scene the game starts with.
            box.label(text="Read from the start scene when the game begins", icon='INFO')

            box.label("3D Audio:")
            # KX_Scene updates the speakers once the frame counter reaches this value, so 0 is every frame.
            box.prop(scene, "audio3d_update", text="Speaker Update Skip (frames)")
            box.label(text="Speaker objects only; frames skipped between updates, 0 = every frame", icon='INFO')


# Abas Network / RangeArmor / Web / Android no topo da aba Export Game: so estado da tela (WindowManager), nao vai para o .range.
bpy.types.WindowManager.ae_export_panel_category = EnumProperty(
    name="Export Panels",
    items=(
        ('NETWORK', "Network", "Room, ports and server for multiplayer", 'NETWORK', 0),
        ('RANGEARMOR', "Export", "Desktop builds with RangeArmor", 'DESKTOP', 1),
        ('WEB', "Web", "Package and touch controls for the Web runtime", 'WEB', 2),
        ('ANDROID', "Android", "App settings for the Android (Web) runtime", 'ANDROID', 3),
    ),
    default='NETWORK',
)


def export_category_is(context, category):
    return context.window_manager.ae_export_panel_category == category


class SCENE_PT_export_category(SceneButtonsPanel, Panel):
    bl_label = "Export Panels"
    bl_context = "export"
    bl_options = {'HIDE_HEADER', 'PIN_TO_TOP'}
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        row = self.layout.row(align=True)
        row.scale_y = 1.2
        row.prop(context.window_manager, "ae_export_panel_category", expand=True)


class SCENE_PT_game_network(SceneButtonsPanel, Panel):
    bl_label = "Network"
    # Export Game tab: the room settings (ports, server, game id) belong with how the game is shipped.
    bl_context = "export"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        return (context.scene.render.engine in cls.COMPAT_ENGINES and
                export_category_is(context, 'NETWORK'))

    def draw_header(self, context):
        self.layout.label(text="", icon='NETWORK')

    def draw(self, context):
        layout = self.layout
        net = context.scene.game_settings.network

        layout.prop(net, "mode")
        is_client = net.mode == 'CLIENT'
        is_server = net.mode in {'HOST', 'DEDICATED'}

        if is_client:
            layout.prop(net, "address")

        col = layout.column()
        col.prop(net, "port")
        sub = col.column()
        sub.active = not is_client
        sub.prop(net, "websocket_port")

        box = layout.box()
        box.active = net.mode != 'OFFLINE'
        box.label(text="Server:", icon='WORLD')
        box.prop(net, "server_name")
        box.prop(net, "max_players")
        box.prop(net, "tick_rate")
        box.prop(net, "snapshot_rate")
        box.prop(net, "relevance_radius")
        box.prop(net, "use_lan_discovery")
        box.prop(net, "use_late_join")

        box = layout.box()
        box.label(text="Game:", icon='GAME')
        box.prop(net, "game_id")
        box.prop(net, "game_version")
        if net.mode != 'OFFLINE':
            layout.label(text="Everyone must run the same .range file", icon='INFO')
        if is_server and net.tick_rate == 0:
            layout.label(text="Tick rate 0: uses the Logic Tic Rate of the scene", icon='INFO')
        layout.label(text="Which objects sync: Object > Game > Network", icon='OBJECT_DATA')


class SCENE_PT_game_navmesh(SceneButtonsPanel, Panel):
    bl_label = "Navigation Mesh"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        rd = context.scene.game_settings.recast_data

        layout.operator("mesh.navmesh_make", text="Build Navigation Mesh")

        box = layout.box()
        box.label(text="Rasterization:", icon="MESH_GRID")
        row = box.row()
        row.prop(rd, "cell_size")
        row.prop(rd, "cell_height")

        box = layout.box()
        box.label(text="Agent:", icon="POSE_HLT")
        split = box.split()

        col = split.column()
        col.prop(rd, "agent_height", text="Height")
        col.prop(rd, "agent_radius", text="Radius")

        col = split.column()
        col.prop(rd, "slope_max")
        col.prop(rd, "climb_max")

        box = layout.box()
        box.label(text="Region:", icon="MOD_MESHDEFORM")
        row = box.row()
        row.prop(rd, "region_min_size")
        if rd.partitioning != 'LAYERS':
            row.prop(rd, "region_merge_size")

        box.prop(rd, "partitioning")

        box = layout.box()
        box.label(text="Polygonization:", icon="MESH_DATA")
        split = box.split()

        col = split.column()
        col.prop(rd, "edge_max_len")
        col.prop(rd, "edge_max_error")

        split.prop(rd, "verts_per_poly")

        box = layout.box()
        box.label(text="Detail Mesh:", icon="MOD_TRIANGULATE")
        row = box.row()
        row.prop(rd, "sample_dist")
        row.prop(rd, "sample_max_error")


bpy.types.Scene.show_expanded_game_physics = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Scene.show_expanded_game_obstacles = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Scene.show_expanded_game_lod = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Scene.show_expanded_game_console = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Scene.show_expanded_game_audio = bpy.props.BoolProperty(name="Expanded", default=False)
