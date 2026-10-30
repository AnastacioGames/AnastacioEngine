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

# Game: Physics tab (physics, collision, obstacles, destruction, explosive, deformation).
# Split out of properties_game.py, which still registers every class in order.

class PhysicsButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "physics"


# Abas Physics / Damage no topo da aba Physics: so estado da tela (WindowManager), nao vai para o .range.
bpy.types.WindowManager.ae_physics_panel_category = EnumProperty(
    name="Physics Panels",
    items=(
        ('PHYSICS', "Physics", "Physics type, collision bounds and obstacles", 'PHYSICS', 0),
        ('DAMAGE', "Damage", "Destruction, explosives and deformation", 'MOD_EXPLODE', 1),
    ),
    default='PHYSICS',
)


def physics_category_is(context, category):
    return context.window_manager.ae_physics_panel_category == category


class PHYSICS_PT_game_category(PhysicsButtonsPanel, Panel):
    bl_label = "Physics Panels"
    bl_options = {'HIDE_HEADER', 'PIN_TO_TOP'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.game and context.scene.render.engine in cls.COMPAT_ENGINES

    def draw(self, context):
        row = self.layout.row(align=True)
        row.scale_y = 1.2
        row.prop(context.window_manager, "ae_physics_panel_category", expand=True)


class PHYSICS_PT_game_physics(PhysicsButtonsPanel, Panel):
    bl_label = "Physics"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        rd = context.scene.render
        return ob and ob.game and (rd.engine in cls.COMPAT_ENGINES) and physics_category_is(context, 'PHYSICS')

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

            box = layout.box()
            box.label(text="Posture (Crouch / Crawl / Jump):", icon="MOD_ARMATURE")
            row = box.row()
            row.prop(game, "crouch_height", slider=True)
            row.prop(game, "crawl_height", slider=True)
            row = box.row()
            row.label(text="Crawl Front:")
            row.prop(game, "crawl_axis", expand=True)
            row = box.row()
            row.prop(game, "use_jump_tuck")
            sub = row.row()
            sub.active = game.use_jump_tuck
            sub.prop(game, "jump_tuck", slider=True)
            box.label(text="Motion actuator > Posture, or Python: character.posture", icon="INFO")

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
            sub = col.column()
            sub.active = not game.use_sleep
            sub.prop(game, "use_start_asleep")

            if game.use_start_asleep:
                box = layout.box()
                box.label(text="Start Asleep: stays still until an awake body touches it", icon="INFO")
                box.label(text="Keep pieces touching without overlap, or they jump when they wake")

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
            if ob.type == 'MESH':
                col.prop(ob, "use_static_batch")

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
            if physics_type == 'NO_COLLISION' and ob.type == 'MESH':
                layout.prop(ob, "use_static_batch")

        elif physics_type == 'NAVMESH':
            layout.operator("mesh.navmesh_face_copy")
            layout.operator("mesh.navmesh_face_add")

            layout.separator()

            layout.operator("mesh.navmesh_reset")
            layout.operator("mesh.navmesh_clear")

            # Dynamic navmesh is opt-in through the "dynamic_navmesh" game property.
            prop = game.properties.get("dynamic_navmesh")
            if prop is not None:
                layout.separator()
                if prop.type != 'BOOL':
                    layout.label(text="\"dynamic_navmesh\" must be a Boolean property", icon='ERROR')
                elif prop.value:
                    if ob.type != 'MESH' or not ob.data.polygons:
                        layout.label(text="Dynamic navmesh: build the navigation mesh first", icon='ERROR')
                    else:
                        layout.label(text="Dynamic navmesh: paths may differ slightly from static", icon='INFO')

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
            and physics_category_is(context, 'PHYSICS') \
            and (game.physics_type in {'SENSOR', 'STATIC', 'DYNAMIC', 'RIGID_BODY', 'CHARACTER', 'SOFT_BODY'})

    def draw(self, context):
        layout = self.layout

        game = context.active_object.game
        layout.prop(game, "use_collision_bounds", text="Enabled")
        layout = layout.column()
        layout.active = game.use_collision_bounds

        split = layout.split()
        split.active = game.use_collision_bounds

        col = split.column()
        col.prop(game, "collision_bounds_type", text="Bounds")
        if game.collision_bounds_type in {'TRIANGLE_MESH', 'CONVEX_HULL'}:
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
    # New id so files that saved the old panel position also show it last; add-ons that
    # add physics panels re-register it after theirs.
    bl_idname = "PHYSICS_PT_game_obstacle_create"
    bl_label = "Create Obstacle"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        game = context.object.game
        rd = context.scene.render
        return (rd.engine in cls.COMPAT_ENGINES) \
            and physics_category_is(context, 'PHYSICS') \
            and (game.physics_type in {'SENSOR', 'STATIC', 'DYNAMIC', 'RIGID_BODY', 'SOFT_BODY', 'CHARACTER', 'NO_COLLISION'})

    def draw(self, context):
        layout = self.layout

        game = context.active_object.game

        layout.prop(game, "use_obstacle_create", text="Enabled")
        layout = layout.column()
        layout.active = game.use_obstacle_create

        row = layout.row()
        row.prop(game, "obstacle_radius", text="Radius")
        row.label()

        if game.use_obstacle_create:
            def is_dynamic_navmesh(ob):
                prop = ob.game.properties.get("dynamic_navmesh")
                return ob.game.physics_type == 'NAVMESH' and prop is not None and prop.type == 'BOOL' and prop.value

            if not any(is_dynamic_navmesh(ob) for ob in context.scene.objects):
                layout.label(text="No dynamic navmesh in the scene: the navmesh won't be carved", icon='ERROR')


def draw_blast_effect(layout, context, es, enabled, destruction):
    """Effect object, Particle Explosion and Ground Mark of an explosive (or of a destructible when it breaks)."""
    col = layout.box()
    col.label(text="Effect:", icon='PARTICLES')
    split = col.split(factor=0.65)
    split.prop(es, "effect", text="")
    sub = split.row()
    sub.active = es.effect is not None
    sub.prop(es, "effect_life", text="Life")
    if enabled and es.effect is not None and es.effect.is_visible(context.scene):
        col.label(text="Move the Effect object to an inactive layer", icon='ERROR')
    row = col.row()
    row.prop(es, "use_particle_explosion")
    if es.use_particle_explosion:
        row.prop(es, "particle_size", text="")
        col.prop(es, "particle_style")
        # The three layers are named after what they are in the chosen style.
        names = {
            'FIRE': ("Fire", "Smoke", "Sparks"),
            'ELECTRIC': ("Plasma", "Smoke", "Sparks"),
            'CONCRETE': ("Dust", "Dust Cloud", "Debris"),
            'WATER': ("Splash", "Mist", "Droplets"),
        }[es.particle_style]
        split = col.split()
        for color_prop, amount_prop, name in zip(("fire_color", "smoke_color", "spark_color"),
                                                 ("fire_amount", "smoke_amount", "spark_amount"), names):
            sub = split.column(align=True)
            sub.label(text=name + ":")
            sub.prop(es, color_prop, text="")
            sub.prop(es, amount_prop, text="Amount")
        row = col.row()
        row.prop(es, "smoke_duration", text=names[1] + " Duration")
        row.prop(es, "blast_speed")

    col = layout.box()
    row = col.row()
    row.prop(es, "use_sound", icon='SPEAKER')
    row.prop(es, "use_light_flash", icon='LAMP_POINT')
    if es.use_light_flash:
        row = col.row(align=True)
        row.prop(es, "flash_color", text="")
        row.prop(es, "flash_strength", text="Strength")
        row.prop(es, "flash_duration", text="Duration")

    # Ground Mark: the Impact Decal projection, on the static surface under the blast.
    col = layout.box()
    col.prop(es, "use_ground_mark")
    if es.use_ground_mark:
        row = col.row(align=True)
        row.prop(es, "mark", text="")
        op = row.operator("object.explosive_mark_add", text="New" if es.mark is None else "", icon='ZOOMIN')
        op.style = es.particle_style
        op.destruction = destruction
        row = col.row()
        row.prop(es, "mark_size", text="Size")
        row.prop(es, "mark_life", text="Life")
        col.prop(es, "use_mark_nearby")
        if es.mark is None:
            col.label(text="Pick a Mark object or press New (a mark for the explosion style)", icon='INFO')
        elif es.mark.is_visible(context.scene):
            col.label(text="Move the Mark object to an inactive layer", icon='ERROR')


class PHYSICS_PT_game_destruction(PhysicsButtonsPanel, Panel):
    bl_label = "Destruction"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob is not None and context.scene.render.engine in cls.COMPAT_ENGINES
                and physics_category_is(context, 'DAMAGE')
                and ob.game.physics_type in {'STATIC', 'DYNAMIC', 'RIGID_BODY'})

    def draw(self, context):
        layout = self.layout
        ob = context.active_object
        game = ob.game
        ds = game.destruction

        layout.prop(game, "use_destruction", text="Enabled")
        layout = layout.column()
        layout.active = game.use_destruction

        col = layout.box()
        col.label(text="Fragments:", icon='GROUP')
        row = col.row(align=True)
        row.prop(ds, "fragments", text="")
        row.operator("object.destruction_fragments_generate", text="Generate Fragments...", icon='MOD_EXPLODE')
        if game.use_destruction:
            self.draw_fragments_check(col, context.scene, ob, ds.fragments)

        split = layout.box().split()
        col = split.column()
        col.label(text="Break:", icon='MOD_EXPLODE')
        col.prop(ds, "break_impulse")
        col.prop(ds, "use_break_on_collision")

        col = split.column()
        col.label(text="Debris:", icon='MOD_PHYSICS')
        sub = col.column(align=True)
        sub.prop(ds, "burst_speed")
        sub.prop(ds, "debris_lifetime", text="Lifetime")
        col.prop(ds, "use_inherit_velocity")

        draw_blast_effect(layout, context, ds.fx, game.use_destruction, True)

    @staticmethod
    def draw_fragments_check(layout, scene, ob, group):
        if group is None:
            layout.label(text="No Fragments: the object just disappears when it breaks", icon='INFO')
            return
        if ob.name in group.objects:
            layout.label(text="The object itself is in its Fragments group", icon='ERROR')
        pieces = [piece for piece in group.objects if piece != ob]
        if not pieces:
            layout.label(text="The Fragments group is empty", icon='ERROR')
        elif any(piece.name not in scene.objects for piece in pieces):
            layout.label(text="Some fragments are not in this scene: they won't be created", icon='ERROR')
        elif any(piece.is_visible(scene) for piece in pieces):
            layout.label(text="Move the fragments to an inactive layer", icon='ERROR')


class PHYSICS_PT_game_explosive(PhysicsButtonsPanel, Panel):
    bl_label = "Explosive"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob is not None and context.scene.render.engine in cls.COMPAT_ENGINES
                and physics_category_is(context, 'DAMAGE')
                and ob.game.physics_type in {'STATIC', 'DYNAMIC', 'RIGID_BODY', 'NO_COLLISION'})

    def draw(self, context):
        layout = self.layout
        game = context.active_object.game
        es = game.explosive

        layout.prop(game, "use_explosive", text="Enabled")
        layout = layout.column()
        layout.active = game.use_explosive

        split = layout.box().split()
        col = split.column()
        col.label(text="Blast:", icon='FORCE_FORCE')
        sub = col.column(align=True)
        sub.prop(es, "radius")
        sub.prop(es, "force")
        sub.prop(es, "up_bias", slider=True)
        col.prop(es, "use_occlusion")

        col = split.column()
        col.label(text="Trigger:", icon='TIME')
        col.prop(es, "fuse")
        # Without a collision shape (Empty, No Collision) nothing ever hits the object, so impact can't trigger.
        can_collide = context.active_object.type != 'EMPTY' and game.physics_type != 'NO_COLLISION'
        if can_collide:
            col.prop(es, "use_explode_on_impact")
        col.prop(es, "use_chain_reaction")
        sub = col.column()
        sub.active = (can_collide and es.use_explode_on_impact) or es.use_chain_reaction
        sub.prop(es, "impact_impulse")

        draw_blast_effect(layout, context, es, game.use_explosive, False)


class PHYSICS_PT_game_deform(PhysicsButtonsPanel, Panel):
    bl_label = "Deformation"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob is not None and ob.type == 'MESH' and context.scene.render.engine in cls.COMPAT_ENGINES
                and physics_category_is(context, 'DAMAGE')
                and ob.game.physics_type in {'STATIC', 'DYNAMIC', 'RIGID_BODY'})

    def draw(self, context):
        layout = self.layout
        ob = context.active_object
        game = ob.game
        df = game.deform

        layout.prop(game, "use_deform", text="Enabled")
        layout = layout.column()
        layout.active = game.use_deform
        layout.row().prop(df, "mode", expand=True)

        split = layout.box().split()
        col = split.column()
        col.label(text="Hit:", icon='MOD_SMOOTH')
        col.prop(df, "dent_impulse")
        col.prop(df, "use_dent_on_collision")

        col = split.column()
        col.label(text="Shape:", icon='MOD_DISPLACE')
        sub = col.column(align=True)
        if df.mode == 'BEND':
            sub.row().prop(df, "bend_axis", expand=True)
            sub.prop(df, "bend_angle")
            sub.prop(df, "bend_max_angle")
            sub.prop(df, "radius")
        else:
            sub.prop(df, "radius")
            sub.prop(df, "depth")
            sub.prop(df, "max_depth")
        sub = col.column()
        sub.active = game.collision_bounds_type == 'TRIANGLE_MESH'
        sub.prop(df, "use_update_physics")

        box = layout.box()
        box.label(text="Impact Decal:", icon='TPAINT_HLT')
        box.prop(df, "decal", text="")
        row = box.row(align=True)
        row.active = df.decal is not None
        row.prop(df, "decal_size", text="Size")
        row.prop(df, "max_decals", text="Max")
        row.prop(df, "decal_life", text="Life")
        col = box.column()
        col.active = df.decal is not None
        col.prop(df, "use_scrape")
        if df.use_scrape:
            col.row().prop(df, "scrape_style", expand=True)
            row = col.row(align=True)
            row.prop(df, "scrape_speed", text="Speed")
            row.prop(df, "scrape_spacing", text="Spacing")
            if df.scrape_style == 'STAMPS':
                col.label(text="Heavy: every mark is a new mesh, keep Max low", icon='ERROR')
            else:
                col.label(text="Max and Life count whole strips", icon='INFO')

        mat = ob.active_material
        if mat:
            box = layout.box()
            box.label(text="Damage Material:", icon='MATERIAL')
            box.operator("node.damage_mix_add", icon='NODETREE')

        if game.use_deform:
            if df.use_update_physics and game.collision_bounds_type != 'TRIANGLE_MESH':
                layout.label(text="Update Physics needs Collision Bounds: Triangle Mesh", icon='INFO')
            if game.use_destruction and df.dent_impulse >= game.destruction.break_impulse:
                layout.label(text="Dent Impulse >= Break Impulse: it breaks before denting", icon='ERROR')
            if any(mod.show_viewport for mod in ob.modifiers):
                layout.label(text="Objects with modifiers don't dent", icon='INFO')
