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

class GameButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "game"
    bl_order = 1000

class GAME_PT_game_components(GameButtonsPanel, Panel):
    bl_label = "Game Components"

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.game

    def draw(self, context):
        layout = self.layout

        ob = context.active_object
        game = ob.game

        row = layout.row()
        row.operator("logic.python_component_register", text="Add", icon="PLUS")
        row.operator("logic.python_component_create", text="Create", icon="PLUS")

        for i, c in enumerate(game.components):
            box = layout.box()
            row = box.row(align=1)
            row.prop(c, "show_expanded", text="", emboss=0)
            row.prop(c, "toggle_execution", text="", emboss=False)
            if "C_Icons" in c.properties:
                try:
                    icondict = c.properties["C_Icons"].value.split("+")
                    row.label(c.name, icon=icondict[0])
                except:
                    row.label(c.name)
            else:
                row.label(c.name)
            
            row.operator("logic.python_component_reload", icon="RECOVER_LAST", text="").index = i
            # row.separator()
            row.operator("logic.python_component_move_up", icon="TRIA_UP", text="").index = i
            row.operator("logic.python_component_move_down", icon="TRIA_DOWN", text="").index = i
            row = row.row(align=0)
            row.operator("logic.python_component_remove", text="", icon='X').index = i
            lastHeader = None

            if len(c.properties) == 1 and c.properties[0].name == "C_Icons": continue
            if c.show_expanded and len(c.properties) > 0:
                expanded  = True
                collapsed = True
                box = box.box().column()
                armature=""

                for prop in c.properties:
                    if prop.name[:8] == "C_Header":
                        row = box.row()
                        expanded  = prop.value
                        collapsed = prop.value
                        split=prop.name.split("/")
                        name=split[1] if len(split) > 1 else "HEADER"
                        icon=split[2] if len(split) > 2 else "FULLSCREEN"
                        row.scale_y = 1.2
                        try:
                            row.prop(prop,"value", text=name, toggle=1, icon=icon, emboss=1)
                        except:
                            print(f"ERROR! Please check header: '{prop.name}' It needs to be like this 'C_Header/HeaderName/Icon'")
                        continue

                    elif prop.name[:10] == "C_Collapse" and collapsed:
                        collapsed  = prop.value
                        split=prop.name.split("/")
                        name = " ".join(split[1]) if len(split) > 1 else "COLLAPSE"
                        icon = split[2] if len(split) > 2 else "MOD_BOOLEAN"

                        # LABEL
                        row = box.row() ; row = box.row() ; row = box.row()
                        row.prop(prop,"value",text=name,toggle=1,emboss=0 if collapsed else 1, icon=icon)
                        row.scale_y = 0.9

                        # SEPARATOR
                        row = box.row()
                        row.prop(prop,"value",text=" ",toggle=1,emboss=1)
                        row.scale_y = 0.2
                        row.enabled = False

                        if collapsed: row = box.row() ; row = box.row() ; row = box.row() ; row = box.row() ; row = box.row()
                        continue
                    else:
                        if expanded and collapsed: row = box.row()
                    text=prop.name

                    try:
                        if expanded and collapsed:
                            split = prop.name.split("/") if "@" in prop.name else [prop.name]
                            if len(split)>1: text=split[1]+":"

                            if not prop.name=="C_Icons": 
                                row.label(text=text, icon="DOT")
                                col = row.column()
                                col.prop(prop, "value", text="")
                    except:
                        if expanded and collapsed:
                            row.label(text=text)
                            col = row.column()
                            col.prop(prop, "value", text="")
                        
        layout.operator("wm.flowmenu_ot_init", text="Add...", icon="PLUS")

class GAME_PT_game_properties(GameButtonsPanel, Panel):
    bl_label = "Game Properties"

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
                    row.label("Text Resolution(0 - 50)")
                else:
                    sub = row.row(align=True)
                    propsR = sub.operator("object.game_property_new", text="", icon='ZOOMIN',)
                    propsR.name = "Text-Res"
                    propsR.type = "FLOAT"
            else:
                props = layout.operator("object.game_property_new", text="Add Text Game Property", icon='ZOOMIN')
                props.name = "Text"
                props.type = "STRING"

        props = layout.operator("object.game_property_new", text="Add Game Property", icon='PLUS')
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

class PhysicsButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "physics"

class PHYSICS_PT_game_physics(PhysicsButtonsPanel, Panel):
    bl_label = "Physics"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        rd = context.scene.render
        return ob and ob.game and (rd.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        ob = context.active_object
        game = ob.game
        soft = ob.game.soft_body
        
        physics_type = game.physics_type
        iconType = "X"
        if physics_type == "CHARACTER": iconType = "POSE_HLT"
        elif physics_type == "DYNAMIC": iconType = "VIEW3D"
        elif physics_type == "STATIC": iconType = "VIEW3D"
        elif physics_type == "RIGID_BODY": iconType = "VIEW3D"
        elif physics_type == "SOFT_BODY": iconType = "SNAP_VOLUME"
        elif physics_type == "OCCLUDER": iconType = "RESTRICT_RENDER_ON"
        elif physics_type == "SENSOR": iconType = "RESTRICT_VIEW_OFF"
        elif physics_type == "NAVMESH": iconType = "GHOST_ENABLED"
        layout.prop(game, "physics_type", icon=iconType)
        layout.separator()

        if physics_type == 'CHARACTER':
            layout.prop(game, "use_actor")
            layout.prop(ob, "hide_render", text="Invisible")  # out of place but useful
            
            # layout.separator()
            layout.label(text="Character Attributes:", icon="OUTLINER_OB_ARMATURE")
            split = layout.split()
            
            col = split.column()
            col.prop(game, "step_height", slider=True)
            col.prop(game, "fall_speed")
            col.prop(game, "max_slope")
            col.prop(game, "smooth_movement")
            col = split.column()
            col.prop(game, "jump_speed")
            col.prop(game, "jump_max")
            col.prop(game, "radius")
            col.prop(game, "jump_direction")

        elif physics_type in {'DYNAMIC', 'RIGID_BODY'}:
            split = layout.split()

            col = split.column()
            col.prop(game, "use_actor")
            col.prop(game, "use_ghost")
            col.prop(ob, "hide_render", text="Invisible")  # out of place but useful

            col = split.column()
            col.prop(game, "use_physics_fh")
            col.prop(game, "use_rotate_from_normal")
            col.prop(game, "use_sleep")

            layout.separator()

            split = layout.split()

            col = split.column()
            if physics_type == "DYNAMIC":   col.label(text="Dynamic Attributes:", icon="VIEW3D")
            else: col.label(text="Rigid Body Attributes:", icon="VIEW3D")
            
            col.prop(game, "mass")
            col.prop(game, "radius")
            col.prop(game, "form_factor")
            col.prop(game, "elasticity", slider=1)

            col.label(text="Linear Velocity:", icon="FORCE_HARMONIC")
            sub = col.column(align=1)
            sub.prop(game, "velocity_min", text="Minimum")
            sub.prop(game, "velocity_max", text="Maximum")

            col = split.column()
            col.label(text="Friction:", icon="HAIR")
            col.prop(game, "friction")
            col.prop(game, "rolling_friction")
            col.separator()

            sub = col.column()
            sub.prop(game, "use_anisotropic_friction")
            subsub = sub.column()
            subsub.active = game.use_anisotropic_friction
            subsub.prop(game, "friction_coefficients", text="", slider=True)

            split = layout.split()
            col = split.column()
            col.label(text="Angular velocity:", icon="FORCE_MAGNETIC")
            sub = col.column(align=True)
            sub.prop(game, "angular_velocity_min", text="Minimum")
            sub.prop(game, "angular_velocity_max", text="Maximum")

            col = split.column()
            col.label(text="Damping:", icon="META_CUBE")
            sub = col.column(align=True)
            sub.prop(game, "damping", text="Translation", slider=True)
            sub.prop(game, "rotation_damping", text="Rotation", slider=True)

            layout.separator()

            col = layout.column()

            col.label(text="Lock Translation:", icon="LINKED")
            row = col.row()
            row.prop(game, "lock_location_x", text="X")
            row.prop(game, "lock_location_y", text="Y")
            row.prop(game, "lock_location_z", text="Z")

        if physics_type == 'RIGID_BODY':
            col = layout.column()

            col.label(text="Lock Rotation:", icon="LINKED")
            row = col.row()
            row.prop(game, "lock_rotation_x", text="X")
            row.prop(game, "lock_rotation_y", text="Y")
            row.prop(game, "lock_rotation_z", text="Z")

        elif physics_type == 'SOFT_BODY':
            col = layout.column()
            col.prop(game, "use_actor")
            col.prop(game, "use_ghost")
            col.prop(ob, "hide_render", text="Invisible")

            layout.separator()

            split = layout.split()

            col = split.column()
            col.label(text="General Attributes:", icon="SNAP_VOLUME")
            col.prop(game, "mass")
            # disabled in the code
            # col.prop(soft, "weld_threshold")
            col.prop(soft, "linear_stiffness", slider=True)
            col.prop(soft, "dynamic_friction", slider=True)
            col.prop(soft, "kdp", text="Damping", slider=True)
            col.prop(soft, "collision_margin", slider=True)
            col.prop(soft, "kvcf", text="Velocity Correction", slider=True)
            col.prop(soft, "use_bending_constraints", text="Bending Constraints")

            sub = col.column()
            sub.active = soft.use_bending_constraints
            sub.prop(soft, "bending_distance")

            col.prop(soft, "use_shape_match")

            sub = col.column()
            sub.active = soft.use_shape_match
            sub.prop(soft, "shape_threshold", slider=True)

            col.label(text="Solver Iterations:", icon="SNAP_FACE")
            col.prop(soft, "position_solver_iterations", text="Position Solver")
            col.prop(soft, "velocity_solver_iterations", text="Velocity Solver")
            col.prop(soft, "cluster_solver_iterations", text="Cluster Solver")
            col.prop(soft, "drift_solver_iterations", text="Drift Solver")

            col = split.column()
            col.label(text="Hardness:", icon="OUTLINER_OB_FORCE_FIELD")
            col.prop(soft, "kchr", text="Rigid Contacts", slider=True)
            col.prop(soft, "kkhr", text="Kinetic Contacts", slider=True)
            col.prop(soft, "kshr", text="Soft Contacts", slider=True)
            col.prop(soft, "kahr", text="Anchors", slider=True)

            col.label(text="Cluster Collision:", icon="SNAP_VOLUME")
            col.prop(soft, "use_cluster_rigid_to_softbody")
            col.prop(soft, "use_cluster_soft_to_softbody")
            sub = col.column()
            sub.active = (soft.use_cluster_rigid_to_softbody or soft.use_cluster_soft_to_softbody)
            sub.prop(soft, "cluster_iterations", text="Iterations")
            sub.prop(soft, "ksrhr_cl", text="Rigid Hardness", slider=True)
            sub.prop(soft, "kskhr_cl", text="Kinetic Hardness", slider=True)
            sub.prop(soft, "ksshr_cl", text="Soft Hardness", slider=True)
            sub.prop(soft, "ksr_split_cl", text="Rigid Impulse Split", slider=True)
            sub.prop(soft, "ksk_split_cl", text="Kinetic Impulse Split", slider=True)
            sub.prop(soft, "kss_split_cl", text="Soft Impulse Split", slider=True)

            split = layout.split()

            col = split.column()
            col.label(text="Volume:", icon="META_BALL")
            col.prop(soft, "kpr", text="Pressure Coefficient")
            col.prop(soft, "kvc", text="Volume Conservation")

            col = split.column()
            col.label(text="Aerodynamics:", icon="FORCE_DRAG")
            col.prop(soft, "kdg", text="Drag Coefficient")
            col.prop(soft, "klf", text="Lift Coefficient")

        elif physics_type == 'STATIC':
            col = layout.column()
            col.prop(game, "use_actor")
            col.prop(game, "use_ghost")
            col.prop(ob, "hide_render", text="Invisible")
            col.prop(game, "use_occlude_culling", text="Occluder (keeps collision)")

            layout.separator()

            split = layout.split()

            col = split.column()
            col.label(text="Static Attributes:", icon="VIEW3D")
            col.prop(game, "radius")
            col.prop(game, "elasticity", slider=True)
            col.label(text="Friction:", icon="HAIR")
            col.prop(game, "friction")
            col.prop(game, "rolling_friction")

            col = split.column()
            sub = col.column()
            sub.prop(game, "use_anisotropic_friction")
            subsub = sub.column()
            subsub.active = game.use_anisotropic_friction
            subsub.prop(game, "friction_coefficients", text="", slider=True)

        elif physics_type == 'SENSOR':
            col = layout.column()
            col.prop(game, "use_actor", text="Detect Actors")
            col.label(text="Sensor Attributes:")
            col.prop(game, "radius")
            col.prop(ob, "hide_render", text="Invisible")

        elif physics_type in {'INVISIBLE', 'NO_COLLISION', 'OCCLUDER'}:
            layout.prop(ob, "hide_render", text="Invisible")

        elif physics_type == 'NAVMESH':
            layout.operator("mesh.navmesh_face_copy")
            layout.operator("mesh.navmesh_face_add")

            layout.separator()

            layout.operator("mesh.navmesh_reset")
            layout.operator("mesh.navmesh_clear")

        if physics_type in {"STATIC", "DYNAMIC", "RIGID_BODY"}:
            row = layout.row()
            row.label(text="Force Field:", icon="FORCE_FORCE")

            row = layout.row()
            row.prop(game, "fh_force")
            row.prop(game, "fh_damping", slider=True)

            row = layout.row()
            row.prop(game, "fh_distance")
            row.prop(game, "use_fh_normal")


class PHYSICS_PT_game_collision_bounds(PhysicsButtonsPanel, Panel):
    bl_label = "Collision Bounds"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        game = context.object.game
        rd = context.scene.render
        return (rd.engine in cls.COMPAT_ENGINES) \
            and (game.physics_type in {'SENSOR', 'STATIC', 'DYNAMIC', 'RIGID_BODY', 'CHARACTER', 'SOFT_BODY'})

    def draw_header(self, context):
        game = context.active_object.game

        self.layout.prop(game, "use_collision_bounds", text="")

    def draw(self, context):
        layout = self.layout

        game = context.active_object.game
        split = layout.split()
        split.active = game.use_collision_bounds

        col = split.column()
        col.prop(game, "collision_bounds_type", text="Bounds")
        if (game.collision_bounds_type == "TRIANGLE_MESH"):
            col.prop(game, "collision_bound")

        row = col.row()
        row.prop(game, "collision_margin", text="Margin", slider=1)

        sub = row.row()
        sub.active = game.physics_type not in {'SOFT_BODY', 'CHARACTER'}
        sub.prop(game, "use_collision_compound", text="Children Compound")

        layout.separator()
        split = layout.split()
        col = split.column()
        col.prop(game, "collision_group")
        col = split.column()
        col.prop(game, "collision_mask")


class PHYSICS_PT_game_obstacles(PhysicsButtonsPanel, Panel):
    bl_label = "Create Obstacle"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        game = context.object.game
        rd = context.scene.render
        return (rd.engine in cls.COMPAT_ENGINES) \
            and (game.physics_type in {'SENSOR', 'STATIC', 'DYNAMIC', 'RIGID_BODY', 'SOFT_BODY', 'CHARACTER', 'NO_COLLISION'})

    def draw_header(self, context):
        game = context.active_object.game

        self.layout.prop(game, "use_obstacle_create", text="")

    def draw(self, context):
        layout = self.layout

        game = context.active_object.game

        layout.active = game.use_obstacle_create

        row = layout.row()
        row.prop(game, "obstacle_radius", text="Radius")
        row.label()


class RenderButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (rd.engine in cls.COMPAT_ENGINES)


class RENDER_OT_set_game_resolution(Operator):
    bl_idname = "render.set_game_resolution"
    bl_label = "Set Resolution"
    bl_options = {'REGISTER', 'UNDO'}

    x: IntProperty()
    y: IntProperty()
    target: StringProperty()

    def execute(self, context):
        if self.target == 'EMBEDDED':
            context.scene.render.resolution_x = self.x
            context.scene.render.resolution_y = self.y
        elif self.target == 'PLAYER':
            context.scene.game_settings.resolution_x = self.x
            context.scene.game_settings.resolution_y = self.y
        return {'FINISHED'}


class RENDER_MT_game_res_embedded(Menu):
    bl_label = "Resolution Presets"
    bl_idname = "RENDER_MT_game_res_embedded"

    def draw(self, context):
        layout = self.layout
        resolutions = [
            ("VGA", 800, 600), ("HD", 1280, 720), ("WXGA", 1366, 768),
            ("HD+", 1600, 900), ("FHD", 1920, 1080), ("QHD", 2560, 1440), ("4K UHD", 3840, 2160)
        ]
        for name, x, y in resolutions:
            op = layout.operator("render.set_game_resolution", text="{} ({}x{})".format(name, x, y))
            op.x = x; op.y = y; op.target = 'EMBEDDED'

        layout.separator()
        layout.label(text="Custom Resolution:")
        col = layout.column(align=True)
        col.prop(context.scene.render, "resolution_x", text="X")
        col.prop(context.scene.render, "resolution_y", text="Y")


class RENDER_MT_game_res_player(Menu):
    bl_label = "Resolution Presets"
    bl_idname = "RENDER_MT_game_res_player"

    def draw(self, context):
        layout = self.layout
        resolutions = [
            ("VGA", 800, 600), ("HD", 1280, 720), ("WXGA", 1366, 768),
            ("HD+", 1600, 900), ("FHD", 1920, 1080), ("QHD", 2560, 1440), ("4K UHD", 3840, 2160)
        ]
        for name, x, y in resolutions:
            op = layout.operator("render.set_game_resolution", text="{} ({}x{})".format(name, x, y))
            op.x = x; op.y = y; op.target = 'PLAYER'

        layout.separator()
        layout.label(text="Custom Resolution:")
        col = layout.column(align=True)
        col.prop(context.scene.game_settings, "resolution_x", text="X")
        col.prop(context.scene.game_settings, "resolution_y", text="Y")


class RENDER_MT_game_target_fps(Menu):
    bl_label = "Target FPS Presets"
    bl_idname = "RENDER_MT_game_target_fps"

    def draw(self, context):
        layout = self.layout
        for value in (30, 60, 75, 90, 120, 144):
            op = layout.operator("wm.context_set_int", text=str(value))
            op.data_path = "scene.game_settings.dynamic_resolution_target_fps"
            op.value = value
        layout.separator()
        layout.label(text="Custom Target FPS:")
        layout.prop(context.scene.game_settings, "dynamic_resolution_target_fps", text="Value")


class RENDER_MT_game_animation_fps(Menu):
    bl_label = "Animation Frame Rate Presets"
    bl_idname = "RENDER_MT_game_animation_fps"

    def draw(self, context):
        layout = self.layout
        for value in (24, 25, 30, 60, 120):
            op = layout.operator("wm.context_set_float", text=str(value))
            op.data_path = "scene.render.fps"
            op.value = value
        layout.separator()
        layout.label(text="Custom Animation Frame Rate:")
        layout.prop(context.scene.render, "fps", text="Value")


class RENDER_MT_game_bit_depth(Menu):
    bl_label = "Bit Depth Presets"
    bl_idname = "RENDER_MT_game_bit_depth"

    def draw(self, context):
        layout = self.layout
        for value in (16, 24, 32):
            op = layout.operator("wm.context_set_int", text=str(value))
            op.data_path = "scene.game_settings.depth"
            op.value = value
        layout.separator()
        layout.label(text="Custom Bit Depth:")
        layout.prop(context.scene.game_settings, "depth", text="Value")


class RENDER_MT_game_refresh_rate(Menu):
    bl_label = "Refresh Rate Presets"
    bl_idname = "RENDER_MT_game_refresh_rate"

    def draw(self, context):
        layout = self.layout
        for value in (30, 50, 60, 75, 90, 120, 144, 240):
            op = layout.operator("wm.context_set_int", text=str(value))
            op.data_path = "scene.game_settings.frequency"
            op.value = value
        layout.separator()
        layout.label(text="Custom Refresh Rate:")
        layout.prop(context.scene.game_settings, "frequency", text="Value")


class RENDER_PT_embedded(RenderButtonsPanel, Panel):
    bl_label = "Embedded Player"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        rd = context.scene.render

        box = layout.box()
        box.label(text="Embedded Player:", icon="VIEW3D")
        row = box.row()
        row.operator("view3d.game_start", text="Start")
        row = box.row()
        row.label(text="Resolution:", icon="SCENE")
        row = box.row(align=True)
        row.menu("RENDER_MT_game_res_embedded", text="{} x {}".format(rd.resolution_x, rd.resolution_y))


class RENDER_PT_game_player(RenderButtonsPanel, Panel):
    bl_label = "Standalone Player"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    def draw(self, context):
        import sys
        layout = self.layout
        not_osx = sys.platform != "darwin"

        gs = context.scene.game_settings

        box = layout.box()
        box.label(text="Standalone Player:", icon="WORLD")
        row = box.row()
        row.operator("wm.blenderplayer_start", text="Start")
        row = box.row()
        row.label(text="Resolution:", icon="SCENE")
        row = box.row(align=True)
        row.active = not_osx or not gs.show_fullscreen
        row.menu("RENDER_MT_game_res_player", text="{} x {}".format(gs.resolution_x, gs.resolution_y))
        row = box.row(align=True)
        col = row.column()
        col.active = not gs.borderless_window
        col.prop(gs, "show_fullscreen")

        col = row.column()
        col.prop(gs, "borderless_window")

        if not_osx:
            col = row.column()
            col.active = gs.show_fullscreen and not gs.borderless_window
            col.prop(gs, "use_desktop")

class RENDER_PT_game_shading(RenderButtonsPanel, Panel):
    bl_label = "Shading"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

        box = layout.box()
        box.label(text="Shading:", icon="MATERIAL")
        split = box.split()

        col = split.column()
        col.prop(gs, "use_glsl_lights", text="Lights", icon="LAMP_SPOT")
        col.prop(gs, "use_glsl_shaders", text="Shaders", icon="LAMP_AREA")
        col.prop(gs, "use_glsl_shadows", text="Shadows", icon="SNAP_FACE")
        col.prop(gs, "use_glsl_environment_lighting", text="Environment Lighting", icon="SNAP_VOLUME")
        col = split.column()
        col.prop(gs, "use_glsl_ramps", text="Ramps", icon="IPO_BEZIER")
        col.prop(gs, "use_glsl_nodes", text="Nodes", icon="NODETREE")
        col.prop(gs, "use_glsl_extra_textures", text="Extra Textures", icon="ASSET_MANAGER")
class RENDER_PT_game_post_process_shaders(RenderButtonsPanel, Panel):
    bl_label = "Post Processing Shaders"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout
        
        scene = context.scene
        scenefx_settings = scene.scenefx_settings

        layout = layout.box()
        layout.label(text="Post Processing Shaders:", icon="RENDER_STILL")

        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_ssao", text="Ambient Occlusion", emboss=True)
        row.prop(scenefx_settings, "render_editor_ssao", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_ssao", text="")
        
        if (scenefx_settings.show_expanded_ssao and scenefx_settings.ssao):
            ssao_settings = scenefx_settings.ssao
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_ssao
            subcol.prop(ssao_settings, "factor")
            subcol.prop(ssao_settings, "distance_max")
            subcol.prop(ssao_settings, "attenuation")
            subcol.prop(ssao_settings, "samples")

        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_bloom", text="Bloom", emboss=True)
        row.prop(scenefx_settings, "render_editor_bloom", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_bloom", text="")
            
        if (scenefx_settings.show_expanded_bloom and scenefx_settings.bloom):
            bloom_settings = scenefx_settings.bloom
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_bloom
            subcol.prop(bloom_settings, "intensity")
            subcol.prop(bloom_settings, "threshold")
            
        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_tonemap", text="Tonemap", emboss=True)
        row.prop(scenefx_settings, "render_editor_tonemap", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_tonemap", text="")
            
        if (scenefx_settings.show_expanded_tonemap and scenefx_settings.tonemap):
            tonemap_settings = scenefx_settings.tonemap
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_tonemap
            subcol.prop(tonemap_settings, "shadertype")
            subcol.prop(tonemap_settings, "exposure")
            subcol.prop(tonemap_settings, "gamma")
            
        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_lightscatter", text="Light Scattering", emboss=True)
        row.prop(scenefx_settings, "render_editor_lightscatter", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_lightscatter", text="")
        
        if (scenefx_settings.show_expanded_lightscatter and scenefx_settings.scatter):
            scatter_settings = scenefx_settings.scatter
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_lightscatter
            subcol.prop(scenefx_settings, "scatter_lod", text="Lod")
            subcol.prop(scatter_settings, "intensity")
            subcol.prop(scatter_settings, "threshold")
            subcol.prop(scatter_settings, "stepsize")
            subcol.prop(scatter_settings, "stepmax")
            
        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_ssr", text="Screen Space Reflections", emboss=True)
        row.prop(scenefx_settings, "render_editor_ssr", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_ssr", text="")
        
        if (scenefx_settings.show_expanded_ssr and scenefx_settings.ssr):
            ssr_settings = scenefx_settings.ssr
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_ssr
            subcol.prop(scenefx_settings, "ssr_lod", text="Lod")
            subcol.prop(ssr_settings, "step_max")
            subcol.prop(ssr_settings, "roughness")
            subcol.prop(ssr_settings, "bias")
            subcol.prop(ssr_settings, "max_distance")
            
        row = layout.row(align=True)
        row.label("FXAA")
        row.prop(scenefx_settings, "render_editor_fxaa", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_fxaa", text="")


class RENDER_PT_game_system(RenderButtonsPanel, Panel):
    bl_label = "System"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

        # Outer group containing the System subpanels.
        system_group = layout.box()

        box = system_group.box()
        box.label(text="System:", icon="SETTINGS")
        split = box.split(factor=0.4)
        split.prop(gs, "use_frame_rate")
        split.prop(gs, "use_deprecation_warnings")

        box = system_group.box()
        box.label(text="Game Exit Key:", icon="BLENDER")
        row = box.row()
        col = row.column()
        col.active = not gs.ignore_exit_key
        col.prop(gs, "exit_key", text="", event=True)

        col = box.column()
        col.use_property_split = True
        col.use_property_decorate = False

        if (gs.ignore_exit_key):
            warn_box = col.box()
            warn_box.label("It will not be possible to close the game by exit key, exitGame() event only!", icon="ERROR")
        col.prop(gs, "ignore_exit_key")

        cursor_box = system_group.box()
        cursor_box.label(text="Mouse Cursor:", icon="RESTRICT_SELECT_OFF")
        col = cursor_box.column()
        col.prop(gs, "show_mouse", text="Mouse Cursor")
        col.label(text="Custom Mouse Cursor:", icon="RESTRICT_SELECT_OFF")
        col.prop(gs, "cursor_filepath", text="")
        col.prop(gs, "cursor_size")
        row = cursor_box.row()
        row.prop(gs, "cursor_offset_x")
        row.prop(gs, "cursor_offset_y")
        row.prop(gs, "cursor_mipmap")

        framing_box = system_group.box()
        framing_box.label(text="Framing:", icon="IMAGE_COL")
        col = framing_box.column()
        col.row().prop(gs, "frame_type", expand=True)
        col.prop(gs, "frame_color", text="")


class RENDER_PT_game_dynamic_resolution(RenderButtonsPanel, Panel):
    bl_label = "Dynamic Resolution"
    bl_order = -100
    COMPAT_ENGINES = {'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout
        gs = context.scene.game_settings

        box = layout.box()
        box.label(text="Dynamic Resolution", icon="SCENE")
        box.label(text="Adjust the internal render scale to maintain the target frame rate.")
        box.prop(gs, "use_dynamic_resolution", text="Enable Dynamic Resolution")

        settings = box.column(align=True)
        settings.active = gs.use_dynamic_resolution
        settings.label(text="Target FPS:")
        settings.menu("RENDER_MT_game_target_fps", text=str(gs.dynamic_resolution_target_fps))
        settings.prop(gs, "dynamic_resolution_min_scale")
        settings.prop(gs, "dynamic_resolution_max_scale")
        settings.prop(gs, "dynamic_resolution_step")

class RENDER_UL_attachments(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item is not None:
            layout.prop(item, "name", text="", emboss=False, icon="TEXTURE")
            layout.label(text=str(index))
        else:
            layout.label(text="", icon="TEXTURE")

class RENDER_PT_game_attachments(RenderButtonsPanel, Panel):
    bl_label = "Attachments"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

        box = layout.box()
        box.label(text="Attachments:", icon="TEXTURE")
        row = box.row()

        row.template_list("RENDER_UL_attachments", "", gs, "attachment_slots", gs, "active_attachment_index", rows=2)

        col = row.column(align=True)
        col.operator("scene.render_attachment_new", icon='ZOOMIN', text="")
        col.operator("scene.render_attachment_remove", icon='ZOOMOUT', text="")

        attachment = gs.active_attachment

        if attachment is not None:
            row = box.row()
            row.prop(attachment, "type")
            row.prop(attachment, "hdr")

            if attachment.type == "CUSTOM":
                row = box.row()
                row.prop(attachment, "size")


class RENDER_PT_game_animations(RenderButtonsPanel, Panel):
    bl_label = "Animations"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

        box = layout.box()
        box.label(text="Animations:", icon="ACTION")
        box.label(text="Animation Frame Rate:")
        box.menu("RENDER_MT_game_animation_fps", text=str(context.scene.render.fps))
        box.prop(gs, "use_restrict_animation_updates")


class RENDER_PT_game_display(RenderButtonsPanel, Panel):
    bl_label = "Display"
    COMPAT_ENGINES = {"BLENDER_GAME"}

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

        display_group = layout.box()

        box = display_group.box()
        box.label(text="Display:", icon="RENDER_STILL")
        col = box.column()
        col.prop(gs, "vsync", icon="RENDER_STILL")
        col.prop(gs, "samples", icon="RENDER_STILL")
        col.prop(gs, "hdr", icon="RENDER_STILL")

        quality = box.column(align=True)
        quality.label(text="Bit Depth (bits per pixel):")
        quality.menu("RENDER_MT_game_bit_depth", text=str(gs.depth))
        quality.label(text="Fullscreen Refresh Rate (Hz):")
        quality.menu("RENDER_MT_game_refresh_rate", text=str(gs.frequency))

        stereo_box = display_group.box()
        stereo_box.label(text="Stereo:", icon="CAMERA_STEREO")
        stereo_box.row().prop(gs, "stereo", expand=True)
        if gs.stereo == 'STEREO':
            stereo_box.prop(gs, "stereo_mode")
            stereo_box.prop(gs, "stereo_eye_separation")


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
            box.label(text="Engine:", icon="PHYSICS")
            box.prop(gs, "physics_engine", text="Engine")
            if gs.physics_engine != 'NONE':
                box.prop(gs, "physics_solver", icon="PHYSICS")
                box.prop(gs, "physics_gravity", text="Gravity")

                box = main_box.box()
                box.label(text="Steps & Timing:", icon="TIME")
                split = box.split()

                col = split.column()
                col.label(text="Physics Steps:")
                sub = col.column(align=True)
                sub.prop(gs, "physics_step_sub", text="Substeps")

                col = split.column()
                col.label(text="Sleep Timer")
                col.prop(gs, "sleep_timer", text="Sleep")

                row = box.row()
                row.prop(gs, "fps", text="FPS")
                row.prop(gs, "time_scale")
                box.prop(gs, "use_fixed_timestep")

                box = main_box.box()
                box.label(text="Deactivation:", icon="SNAP_FACE")
                col = box.column()
                sub = col.row(align=True)
                sub.prop(gs, "deactivation_linear_threshold", text="Linear Threshold")
                sub.prop(gs, "deactivation_angular_threshold", text="Angular Threshold")
                sub = col.row()
                sub.prop(gs, "deactivation_time", text="Time")

                box = main_box.box()
                box.label(text="Culling:", icon="RESTRICT_RENDER_OFF")
                split = box.split()

                col = split.column()
                col.label(text="Culling:")
                col.prop(gs, "shadows_on_off", text="Shadow Culling")
                col.prop(gs, "use_occlusion_culling", text="Occlusion Culling")
                sub = col.column()
                sub.active = gs.use_occlusion_culling
                sub.prop(gs, "occlusion_culling_resolution", text="Resolution")

                col = split.column()
                col.label(text="Object Activity:")
                col.prop(gs, "use_activity_culling")

            else:
                box = main_box.box()
                box.label(text="Steps:", icon="TIME")
                split = box.split()

                col = split.column()
                col.label(text="Physics Steps:")
                col.prop(gs, "fps", text="FPS")

                col = split.column()
                col.label(text="Logic Steps:")
                col.prop(gs, "logic_step_max", text="Max")

        # ---- Obstacle Simulation ----
        row = main_box.row(align=True)
        row.prop(scene, "show_expanded_game_obstacles", text="Obstacle Simulation",
                 icon='TRIA_DOWN' if scene.show_expanded_game_obstacles else 'TRIA_RIGHT', emboss=True)

        if scene.show_expanded_game_obstacles:
            box = main_box.box()
            box.prop(gs, "obstacle_simulation", text="Type")
            if gs.obstacle_simulation != 'NONE':
                box.prop(gs, "level_height")
                box.prop(gs, "show_obstacle_simulation")

        # ---- Navigation Mesh ----
        row = main_box.row(align=True)
        row.prop(scene, "show_expanded_game_navmesh", text="Navigation Mesh",
                 icon='TRIA_DOWN' if scene.show_expanded_game_navmesh else 'TRIA_RIGHT', emboss=True)

        if scene.show_expanded_game_navmesh:
            rd = gs.recast_data
            col = main_box.column()
            col.operator("mesh.navmesh_make", text="Build Navigation Mesh")

            box = main_box.box()
            box.label(text="Rasterization:", icon="MESH_GRID")
            row = box.row()
            row.prop(rd, "cell_size")
            row.prop(rd, "cell_height")

            box = main_box.box()
            box.label(text="Agent:", icon="POSE_HLT")
            split = box.split()

            col = split.column()
            col.prop(rd, "agent_height", text="Height")
            col.prop(rd, "agent_radius", text="Radius")

            col = split.column()
            col.prop(rd, "slope_max")
            col.prop(rd, "climb_max")

            box = main_box.box()
            box.label(text="Region:", icon="MOD_MESHDEFORM")
            row = box.row()
            row.prop(rd, "region_min_size")
            if rd.partitioning != 'LAYERS':
                row.prop(rd, "region_merge_size")

            box.prop(rd, "partitioning")

            box = main_box.box()
            box.label(text="Polygonization:", icon="MESH_DATA")
            split = box.split()

            col = split.column()
            col.prop(rd, "edge_max_len")
            col.prop(rd, "edge_max_error")

            split.prop(rd, "verts_per_poly")

            box = main_box.box()
            box.label(text="Detail Mesh:", icon="MOD_TRIANGULATE")
            row = box.row()
            row.prop(rd, "sample_dist")
            row.prop(rd, "sample_max_error")

        # ---- LOD Hysteresis ----
        row = main_box.row(align=True)
        row.prop(scene, "show_expanded_game_lod", text="Level of Detail - LOD",
                 icon='TRIA_DOWN' if scene.show_expanded_game_lod else 'TRIA_RIGHT', emboss=True)

        if scene.show_expanded_game_lod:
            box = main_box.box()
            row = box.row()
            row.prop(gs, "use_scene_hysteresis", text="Hysteresis")
            row = box.row()
            row.active = gs.use_scene_hysteresis
            row.prop(gs, "scene_hysteresis_percentage", text="")

        # ---- Python Console ----
        row = main_box.row(align=True)
        row.prop(scene, "show_expanded_game_console", text="Python Console",
                 icon='TRIA_DOWN' if scene.show_expanded_game_console else 'TRIA_RIGHT', emboss=True)
        row.prop(gs, "use_python_console", text="")

        if scene.show_expanded_game_console:
            box = main_box.box()
            row = box.row(align=True)
            row.active = gs.use_python_console
            row.label("Keys:")
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
            col.prop(scene, "audio_doppler_speed", text="Speed")
            col.prop(scene, "audio_doppler_factor", text="Doppler")

            box.label("3D Audio:")
            box.prop(scene, "audio3d_update")


bpy.types.Scene.show_expanded_game_physics = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Scene.show_expanded_game_obstacles = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Scene.show_expanded_game_navmesh = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Scene.show_expanded_game_lod = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Scene.show_expanded_game_console = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Scene.show_expanded_game_audio = bpy.props.BoolProperty(name="Expanded", default=False)


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


class DataButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"


class DATA_PT_shadow_game(DataButtonsPanel, Panel):
    bl_label = "Use Shadow"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        COMPAT_LIGHTS = {'SPOT', 'SUN'}
        lamp = context.lamp
        engine = context.scene.render.engine
        return (lamp and lamp.type in COMPAT_LIGHTS) and (engine in cls.COMPAT_ENGINES)

    def draw_header(self, context):
        lamp = context.lamp

        self.layout.prop(lamp, "use_shadow", text="")

    def draw(self, context):
        layout = self.layout

        lamp = context.lamp

        layout.active = lamp.use_shadow

        main_box = layout.box()

        # --- General ---
        split = main_box.split()

        col = split.column()
        col.prop(lamp, "shadow_color", text="")
        if lamp.type in ('SUN', 'SPOT'):
            col.prop(lamp, "show_shadow_box")
        col.prop(lamp, "static_shadow")

        col = split.column()
        col.prop(lamp, "use_shadow_layer", text="This Layer Only")
        col.prop(lamp, "use_only_shadow")
        if lamp.type == "SUN":
            col.prop(lamp, "shadow_blend", text="Shadow Fade", slider=True)

        # --- Buffer & Quality ---
        row = main_box.row(align=True)
        row.prop(lamp, "show_expanded_lamp_shadow_buffer", text="Buffer & Quality",
                 icon='TRIA_DOWN' if lamp.show_expanded_lamp_shadow_buffer else 'TRIA_RIGHT', emboss=True)
        if lamp.show_expanded_lamp_shadow_buffer:
            box = main_box.box()

            col = box.column()
            col.label("Buffer Type:")
            col.prop(lamp, "ge_shadow_buffer_type", text="", toggle=True)
            if lamp.ge_shadow_buffer_type == "SIMPLE":
                col.label("Filter Type:")
                col.prop(lamp, "shadow_filter", text="", toggle=True)

            col.label("Quality:")
            col = box.column(align=True)
            col.prop(lamp, "shadow_buffer_size", text="Size")
            if lamp.ge_shadow_buffer_type == "VARIANCE":
                col.prop(lamp, "shadow_buffer_sharp", text="Sharpness")
            elif lamp.shadow_filter in ("PCF", "PCF_BAIL", "PCF_JITTER", "PCF_PENUMBRA"):
                col.prop(lamp, "shadow_buffer_samples", text="Samples")
                col.prop(lamp, "shadow_buffer_soft", text="Soft")

            row = box.row()
            row.label("Bias:")
            row = box.row(align=True)
            row.prop(lamp, "shadow_buffer_bias", text="Bias")
            if lamp.ge_shadow_buffer_type == "VARIANCE":
                row.prop(lamp, "shadow_buffer_bleed_bias", text="Bleed Bias")
            else:
                row.prop(lamp, "shadow_buffer_slope_bias", text="Slope Bias")

        # --- Cascaded Shadow Mapping (Sun only) ---
        if lamp.type == 'SUN':
            row = main_box.row(align=True)
            row.prop(lamp, "show_expanded_lamp_shadow_csm", text="Cascaded Shadow Mapping",
                     icon='TRIA_DOWN' if lamp.show_expanded_lamp_shadow_csm else 'TRIA_RIGHT', emboss=True)
            if lamp.show_expanded_lamp_shadow_csm:
                box = main_box.box()
                col = box.column(align=True)
                col.prop(lamp, "use_csm_shadow", text="Enable Cascaded Shadow Mapping")

                # Keep the master toggle interactive even when CSM is currently disabled.
                # Only the dependent debug and cascade settings should be inactive.
                col.active = lamp.use_csm_shadow
                col.prop(lamp, "use_csm_debug", text="Enable Debug")

                row = col.row(align=True)
                row.prop(lamp, "cascaded_proportion_two", text="Cascade Proportion Near", slider=True)
                row.prop(lamp, "cascaded_proportion_three", text="Cascade Proportion Middle", slider=True)

                col.separator(factor=1)

                col.prop(lamp, "shadow_csm_two_buffer_size", text="CSM Size Medium")
                col.prop(lamp, "shadow_buffer_soft_two", text="CSM Shadow Soft Medium")
                col.prop(lamp, "shadow_buffer_bias_two", text="CSM Bias Medium")

                col.separator(factor=1)

                col.prop(lamp, "shadow_csm_three_buffer_size", text="CSM Size Low")
                col.prop(lamp, "shadow_buffer_soft_three", text="CSM Shadow Soft Low")
                col.prop(lamp, "shadow_buffer_bias_three", text="CSM Bias Low")

        # --- Clipping ---
        row = main_box.row()
        row.label("Clipping:")
        row = main_box.row(align=True)
        row.prop(lamp, "shadow_buffer_clip_start", text="Clip Start")
        row.prop(lamp, "shadow_buffer_clip_end", text="Clip End")

        if lamp.type == 'SUN':
            row = main_box.row()
            row.prop(lamp, "shadow_frustum_size", text="Frustum Size")


bpy.types.Lamp.show_expanded_lamp_shadow_buffer = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Lamp.show_expanded_lamp_shadow_csm = bpy.props.BoolProperty(name="Expanded", default=False)


class DATA_PT_light_culling_game(DataButtonsPanel, Panel):
    bl_label = "Distance Culling"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        lamp = context.lamp
        engine = context.scene.render.engine
        return (lamp and lamp.type != 'SUN') and (engine in cls.COMPAT_ENGINES)

    def draw_header(self, context):
        lamp = context.lamp

        self.layout.prop(lamp, "use_cull_distance", text="")

    def draw(self, context):
        layout = self.layout
        lamp = context.lamp

        layout.active = lamp.use_cull_distance

        row = box.row()
        row.prop(lamp, "cull_distance", text="Cull Distance")

        row = layout.row()
        row.prop(lamp, "glow_scale", text="Glow Scale")


class ObjectButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"


class OBJECT_MT_lod_tools(Menu):
    bl_label = "Level Of Detail Tools"

    def draw(self, context):
        layout = self.layout

        layout.operator("object.lod_by_name", text="Set By Name")
        layout.operator("object.lod_generate", text="Generate")
        layout.operator("object.lod_clear_all", text="Clear All", icon='PANEL_CLOSE')
        
class OBJECT_PT_game_object_tasks(GameButtonsPanel, Panel):
    bl_label = "Game Object Tasks"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return context.scene.render.engine in cls.COMPAT_ENGINES and ob.type

    def draw(self, context):
        layout = self.layout
        ob = context.object

        layout.prop(ob, "convert_object")
        
class OBJECT_MT_culling(ObjectButtonsPanel, Panel):
    bl_label = "Culling Bounding Volume"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return context.scene.render.engine in cls.COMPAT_ENGINES and ob.type not in {'CAMERA', 'EMPTY', 'LAMP'}

    def draw(self, context):
        layout = self.layout
        game = context.active_object.game

        layout.label(text="Predefined Bound:")
        layout.prop(game, "predefined_bound", "")

class OBJECT_PT_activity_culling(GameButtonsPanel, Panel):
    bl_label = "Activity Culling"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return context.scene.render.engine in cls.COMPAT_ENGINES and ob.type not in {'CAMERA'}

    def draw(self, context):
        layout = self.layout
        activity = context.object.game.activity_culling

        activity_box = layout.box()
        split = activity_box.split()

        col = split.column()
        col.prop(activity, "use_physics", text="Physics")
        sub = col.box()
        sub.active = activity.use_physics
        sub.prop(activity, "physics_radius")
        sub.prop(activity, "sleep_velocity", text="Sleep Velocity")

        col = split.column()
        col.prop(activity, "use_logic", text="Logic")
        sub = col.box()
        sub.active = activity.use_logic
        sub.prop(activity, "logic_radius")
        sub = sub.column()
        sub.prop(activity, "activity_components", text="No Components")

class OBJECT_OT_bake_lod_impostor(Operator):
    bl_idname = "object.bake_lod_impostor"
    bl_label = "Bake Impostor Texture"
    bl_description = ("Render the LOD level's mesh into a transparent image for use as a billboard impostor "
                       "texture, either a single frontal view or a multi-angle atlas")
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()

    def execute(self, context):
        ob = context.object
        scene = context.scene

        if ob is None or self.index < 0 or self.index >= len(ob.lod_levels):
            self.report({'ERROR'}, "Invalid LOD level")
            return {'CANCELLED'}

        level = ob.lod_levels[self.index]
        target = level.object
        if target is None or target.type != 'MESH':
            self.report({'ERROR'}, "LOD level has no billboard object to texture")
            return {'CANCELLED'}

        # The high-poly mesh to photograph is the LOD owner itself (level 0),
        # not the low-poly billboard plane referenced by this level.
        source = ob
        if source.type != 'MESH' or not source.data.vertices:
            self.report({'ERROR'}, "Active object has no mesh to bake an impostor from")
            return {'CANCELLED'}

        multi_angle = level.use_atlas
        angle_count = int(scene.lod_impostor_bake_angles) if multi_angle else 1
        cell_resolution = int(scene.lod_impostor_bake_resolution)

        if multi_angle:
            cols = math.ceil(math.sqrt(angle_count))
            rows = math.ceil(angle_count / cols)
        else:
            cols, rows = 1, 1

        # Bounding box of the source mesh in world space.
        bbox_world = [source.matrix_world * Vector(corner) for corner in source.bound_box]
        min_co = Vector((min(v[i] for v in bbox_world) for i in range(3)))
        max_co = Vector((max(v[i] for v in bbox_world) for i in range(3)))
        center = (min_co + max_co) * 0.5
        size = max_co - min_co
        # Half-extent used to frame the camera, with a margin so the silhouette isn't clipped.
        # half_width uses the bbox's diagonal (not just size.x/size.y) so a diagonal
        # viewing angle in multi-angle mode never crops corners that axis-aligned
        # framing would have missed.
        half_height = max(size.z, 1e-3) * 0.5 * 1.1
        half_width = max((Vector((size.x, size.y, 0.0)).length), 1e-3) * 0.5 * 1.1
        half_extent = max(half_height, half_width)
        camera_distance = max(size.y, size.x, 1.0) * 4.0 + half_extent

        cam_data = bpy.data.cameras.new("LOD_ImpostorBakeCam")
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = half_extent * 2.0
        cam_obj = bpy.data.objects.new("LOD_ImpostorBakeCam", cam_data)
        scene.objects.link(cam_obj)

        prev_camera = scene.camera
        # Keep lamps visible so the source isn't baked pitch black; hide every
        # other object (including the billboard plane itself) so only the
        # high-poly source mesh shows up in the shot.
        prev_hidden = [(o, o.hide_render) for o in scene.objects if o != source and o.type != 'LAMP']
        for o, _ in prev_hidden:
            o.hide_render = True

        prev_engine = scene.render.engine
        prev_res_x = scene.render.resolution_x
        prev_res_y = scene.render.resolution_y
        prev_res_pct = scene.render.resolution_percentage
        prev_alpha_mode = scene.render.alpha_mode
        prev_filepath = scene.render.filepath

        blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else bpy.app.tempdir
        out_path = os.path.join(blend_dir, "{}_impostor.png".format(target.name))
        cell_paths = []

        try:
            # Force the classic Blender Internal engine for the bake: the scene
            # is normally set to BLENDER_GAME, whose render() ignores alpha_mode
            # / transparency_method entirely and just dumps the game viewport.
            scene.render.engine = 'BLENDER_RENDER'
            scene.camera = cam_obj
            scene.render.resolution_x = cell_resolution
            scene.render.resolution_y = cell_resolution
            scene.render.resolution_percentage = 100
            scene.render.alpha_mode = 'TRANSPARENT'

            for i in range(angle_count):
                # Cell 0 matches the single-angle frontal shot (camera on the
                # +Y side, see KX_GameObject::UpdateLod's heading convention:
                # heading = atan2(-toCam.x, toCam.y), which is 0 for a camera
                # offset of (0, +d, 0) from the object). Rotating the offset
                # counter-clockwise by `angle` keeps heading(angle) == angle,
                # so runtime cell selection can map heading directly to index.
                angle = (2.0 * math.pi * i) / angle_count if multi_angle else 0.0
                offset = Vector((-camera_distance * math.sin(angle), camera_distance * math.cos(angle), 0.0))
                cam_obj.location = center + offset
                cam_obj.location.z = center.z
                direction = center - cam_obj.location
                cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

                cell_path = out_path if not multi_angle else os.path.join(
                    blend_dir, "{}_impostor_cell{}.png".format(target.name, i))
                scene.render.filepath = cell_path
                bpy.ops.render.render(write_still=True)
                cell_paths.append(cell_path)
        finally:
            for o, hide in prev_hidden:
                o.hide_render = hide
            scene.camera = prev_camera
            scene.render.engine = prev_engine
            scene.render.resolution_x = prev_res_x
            scene.render.resolution_y = prev_res_y
            scene.render.resolution_percentage = prev_res_pct
            scene.render.alpha_mode = prev_alpha_mode
            scene.render.filepath = prev_filepath
            scene.objects.unlink(cam_obj)
            bpy.data.objects.remove(cam_obj)
            bpy.data.cameras.remove(cam_data)

        if multi_angle:
            self._compose_atlas(cell_paths, cols, rows, cell_resolution, out_path)
            level.use_atlas = True
            level.atlas_columns = cols
            level.atlas_rows = rows
        else:
            level.use_atlas = False

        self._apply_impostor_texture(target, out_path)

        self.report({'INFO'}, "Impostor baked to {}".format(out_path))
        return {'FINISHED'}

    @staticmethod
    def _compose_atlas(cell_paths, cols, rows, cell_resolution, out_path):
        atlas_w = cols * cell_resolution
        atlas_h = rows * cell_resolution
        atlas_buf = array('f', [0.0] * (atlas_w * atlas_h * 4))

        row_floats = cell_resolution * 4
        for i, cell_path in enumerate(cell_paths):
            col, row = i % cols, i // cols
            cell_img = bpy.data.images.load(cell_path)
            try:
                cell_buf = array('f', cell_img.pixels[:])
                # Cell (0, 0) is the bottom-left of the atlas, matching Blender's
                # bottom-up pixel row order, so the array copy needs no vertical flip.
                dest_row0 = row * cell_resolution
                dest_col0 = col * cell_resolution
                for cell_row in range(cell_resolution):
                    src_start = cell_row * row_floats
                    dest_start = ((dest_row0 + cell_row) * atlas_w + dest_col0) * 4
                    atlas_buf[dest_start:dest_start + row_floats] = cell_buf[src_start:src_start + row_floats]
            finally:
                bpy.data.images.remove(cell_img)
            os.remove(cell_path)

        atlas_name = os.path.basename(out_path)
        atlas_img = bpy.data.images.get(atlas_name)
        if atlas_img is None or tuple(atlas_img.size) != (atlas_w, atlas_h):
            if atlas_img is not None:
                bpy.data.images.remove(atlas_img)
            atlas_img = bpy.data.images.new(atlas_name, atlas_w, atlas_h, alpha=True)
        atlas_img.pixels[:] = atlas_buf
        atlas_img.filepath_raw = out_path
        atlas_img.file_format = 'PNG'
        atlas_img.save()

    @staticmethod
    def _apply_impostor_texture(target, image_path):
        # Reuse an existing image datablock pointing at this bake instead of
        # piling up duplicates each time the button is pressed.
        image_name = os.path.basename(image_path)
        image = bpy.data.images.get(image_name)
        if image is not None:
            image.filepath = image_path
            image.source = 'FILE'
            image.reload()
        else:
            image = bpy.data.images.load(image_path)
        image.use_alpha = True
        image.alpha_mode = 'STRAIGHT'

        material = target.data.materials[0] if target.data.materials else None
        if material is None:
            material = bpy.data.materials.new(name="{}_impostor".format(target.name))
            target.data.materials.append(material)

        # Named per-target so multiple billboard trees don't clobber each other's texture.
        tex_name = "{}_impostor".format(target.name)
        tex = bpy.data.textures.get(tex_name)
        if tex is None or tex.type != 'IMAGE':
            tex = bpy.data.textures.new(tex_name, type='IMAGE')
        tex.image = image

        slot = None
        for existing in material.texture_slots:
            if existing is not None and existing.texture is tex:
                slot = existing
                break
        if slot is None:
            slot = material.texture_slots.add()
            slot.texture = tex
            slot.texture_coords = 'UV'
        slot.use_map_alpha = True

        material.use_transparency = True
        material.transparency_method = 'Z_TRANSPARENCY'
        material.alpha = 0.0
        material.specular_alpha = 0.0


bpy.types.Scene.lod_impostor_bake_resolution = EnumProperty(
    name="Impostor Bake Resolution",
    description="Image size used by 'Bake Impostor Texture' (per-cell size in Multi-Angle mode)",
    items=(
        ('128', "128", "128x128 px"),
        ('256', "256", "256x256 px"),
        ('512', "512", "512x512 px"),
        ('1024', "1024", "1024x1024 px"),
    ),
    default='512',
)

bpy.types.Scene.lod_impostor_bake_angles = EnumProperty(
    name="Impostor Bake Angles",
    description="Number of views baked around the Z axis in Multi-Angle mode",
    items=(
        ('4', "4", "4 views, 90° apart"),
        ('8', "8", "8 views, 45° apart"),
        ('12', "12", "12 views, 30° apart"),
        ('16', "16", "16 views, 22.5° apart"),
    ),
    default='8',
)


class OBJECT_PT_levels_of_detail(ObjectButtonsPanel, Panel):
    bl_label = "Levels of Detail"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return context.scene.render.engine in cls.COMPAT_ENGINES and ob.type not in {'CAMERA', 'EMPTY', 'LAMP'}

    def draw(self, context):
        layout = self.layout
        ob = context.object
        gs = context.scene.game_settings

        col = layout.column()
        col.prop(ob, "lod_factor", text="Distance Factor")
        
        col = layout.column()
        col.prop(ob, "use_lod_physics", text="Physics Update")

        for i, level in enumerate(ob.lod_levels):
            if i == 0:
                continue
            box = col.box()
            row = box.row(align=True)
            row.prop(level, "object", text="")
            row.prop(level, "use_invisible_mesh", text="")
            row.operator("object.lod_remove", text="", icon='PANEL_CLOSE').index = i
            
            row = box.row()
            row.prop(level, "distance")
            row = row.row(align=True)
            row.prop(level, "use_mesh", text="")
            row.prop(level, "use_material", text="")

            row = box.row()
            row.active = level.use_mesh
            row.prop(level, "use_billboard", text="Billboard (impostor)")

            if level.use_billboard:
                row = box.row()
                row.active = level.use_billboard
                row.prop(level, "use_atlas", text="Multi-Angle Atlas")

                if level.use_atlas:
                    row = box.row(align=True)
                    row.enabled = False
                    row.prop(level, "atlas_columns", text="Columns")
                    row.prop(level, "atlas_rows", text="Rows")

                if level.use_atlas:
                    row = box.row(align=True)
                    row.prop(context.scene, "lod_impostor_bake_angles", text="Angles")

                row = box.row(align=True)
                row.operator("object.bake_lod_impostor", text="Bake Impostor Texture", icon='RENDER_STILL').index = i
                row.prop(context.scene, "lod_impostor_bake_resolution", text="")

            row = box.row()
            row.active = gs.use_scene_hysteresis
            row.prop(level, "use_object_hysteresis", text="Hysteresis Override")
            row = box.row()
            row.active = gs.use_scene_hysteresis and level.use_object_hysteresis
            row.prop(level, "object_hysteresis_percentage", text="")

        row = col.row(align=True)
        row.operator("object.lod_add", text="Add", icon='ZOOMIN')
        row.menu("OBJECT_MT_lod_tools", text="", icon='TRIA_DOWN')
        
class OBJECT_PT_animation_events(GameButtonsPanel, Panel):
    bl_label = "Animation Events"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return context.scene.render.engine in cls.COMPAT_ENGINES and ob.type not in {'CAMERA', 'EMPTY', 'LAMP'}

    def draw(self, context):
        layout = self.layout
        ob = context.object
        gs = context.scene.game_settings

        col = layout.column()
        
        for i, event in enumerate(ob.anim_events):
            if i == 0: continue
            box = col.box()
            row = box.row()
            row.prop(event, "show_expanded", text="", emboss=True)
            
            if (event.anim): textHeader = "{EventIndex} - Animation Event: {ActionName}".format(EventIndex=i, ActionName=event.anim.name)
            else: textHeader = "{EventIndex} - Empty Animation Event".format(EventIndex=i)
            row.label(text=textHeader, icon="RECOVER_LAST")
            
            row = row.row(align=True)
            row.operator("object.animation_event_move_up", text="", icon='DOTSUP').index = i
            row.operator("object.animation_event_move_down", text="", icon='DOTSDOWN').index = i
            row.operator("object.animation_event_remove", text="", icon='PANEL_CLOSE').index = i
            
            if (not event.show_expanded):         
                continue
            
            row = box.split(factor=0.2)
            row.label(text="Action:")
            row.prop(event, "anim", text="")
            
            # Triggers
            row = box.split(factor=1)
            row.operator("object.animation_event_trigger_add", text="Add Trigger", icon='ZOOMIN').index = i
            row = box.row()
            if len(event.triggers) == 0: row.label(text="No Triggers! Please add an frame trigger", icon="PANEL_CLOSE")
            else: row.label(text="Triggers", icon="ANIM")
            for it, eventTrigger in enumerate(event.triggers):
                if it == 0: continue
                #row = box.split(factor=1)
                row = box.row()
                row.prop(eventTrigger, "frame", text="Frame")
                row.prop(eventTrigger, "custom_arg", text="")
                
                buttonPick = row.operator("object.animation_event_trigger_pick", text="", icon="EYEDROPPER")
                buttonPick.index = it
                buttonPick.eventIndex = i

                button = row.operator("object.animation_event_trigger_remove", text="", icon="PANEL_CLOSE")
                button.index = it
                button.eventIndex = i
               
            row = box.row()
            row = row.separator(factor=1)
            row = box.row()
            row.label(text="Python Event:", icon="FILE_SCRIPT")
            row.prop(event, "eventcall", text="")

        row = col.row(align=True)
        row.operator("object.animation_event_add", text="Add", icon='ZOOMIN')

classes = (
    GAME_PT_game_components,
    GAME_PT_game_properties,
    PHYSICS_PT_game_physics,
    PHYSICS_PT_game_collision_bounds,
    PHYSICS_PT_game_obstacles,
    RENDER_OT_set_game_resolution,
    RENDER_MT_game_res_embedded,
    RENDER_MT_game_res_player,
    RENDER_MT_game_target_fps,
    RENDER_MT_game_animation_fps,
    RENDER_MT_game_bit_depth,
    RENDER_MT_game_refresh_rate,
    RENDER_PT_embedded,
    RENDER_PT_game_player,
    RENDER_PT_game_shading,
    RENDER_PT_game_post_process_shaders,
    RENDER_PT_game_system,
    RENDER_PT_game_dynamic_resolution,
    RENDER_PT_game_attachments,
    RENDER_PT_game_animations,
    RENDER_PT_game_display,
	RENDER_UL_attachments,
    SCENE_PT_game_physics,
    WORLD_PT_game_context_world,
    WORLD_PT_game_world,
    WORLD_PT_game_environment_lighting,
    WORLD_PT_game_mist,
    DATA_PT_shadow_game,
    DATA_PT_light_culling_game,
    OBJECT_MT_lod_tools,
    OBJECT_PT_game_object_tasks,
    OBJECT_MT_culling,
    OBJECT_PT_activity_culling,
    OBJECT_OT_bake_lod_impostor,
    OBJECT_PT_levels_of_detail,
    OBJECT_PT_animation_events, 
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
