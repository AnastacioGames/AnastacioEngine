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

# <pep8-80 compliant>

import bpy
import importlib
import os
import sys
from bpy.types import Operator
from bpy.props import (
    EnumProperty,
    IntProperty,
)


_constraint_presets = (
    ('HINGE', "Hinge", "Two game-physics bodies joined by a free hinge"),
    ('LIMITED_HINGE', "Limited Hinge (6DOF)", "Hinge with rotation limited to -57 to 57 degrees"),
    ('SLIDER', "Slider (6DOF)", "Slider with one metre of travel on its local X axis"),
    ('BALL', "Ball Socket", "Two game-physics bodies joined by a ball socket"),
    ('CONE_TWIST', "Cone Twist (6DOF)", "Cone-twist joint with 29 degree angular limits"),
)

_constraint_asset_objects = {
    'HINGE': ('HingeSocket', 'HingeAxis', 'HingeSocket.001', 'HingeAxis.001'),
    'LIMITED_HINGE': ('HingeSocket.002', 'HingeAxis.002', 'HingeSocket.003', 'HingeAxis.003'),
    'SLIDER': ('SliderSocket', 'SliderAxis', 'SliderSocket.001', 'SliderAxis.001'),
    'BALL': ('Socket', 'Ball', 'Socket.001', 'Ball.001'),
    'CONE_TWIST': ('Socket.002', 'Ball.002', 'Socket.003', 'Ball.003'),
}

RIGID_BODY_JOINT_COMPONENT_MODULE = "rigid_body_joint_component"
RIGID_BODY_JOINT_COMPONENT_CLASS = "RigidBodyJointComponent"

_RIGID_BODY_JOINT_COMPONENT_TEMPLATE = '''"""Editable runtime Bullet joint created by Anastacio Engine."""
from collections import OrderedDict
import math
import Range
from Range.args import Object

class RigidBodyJointComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "CONSTRAINT"),
        ("C_Header /Rigid Body Joint/CONSTRAINT", True),
        ("Target", Object(tip="The other body of the joint (needs game physics)")),
        ("Joint Type", {"Hinge", "Limited Hinge (6DOF)", "Slider (6DOF)", "Ball Socket", "Cone Twist (6DOF)"}),
        ("Enabled", True), ("Disable Linked Collision", False),
        ("Use Breaking", False), ("Breaking Threshold", 0.0),
        ("C_Header /Pivot and Axis/EMPTY_AXIS", True),
        ("Pivot", (0.0, 0.0, 0.0)), ("Axis (degrees)", (0.0, 0.0, 0.0)),
        ("C_Header /Limits/CONSTRAINT", True),
        ("Linear Min", (0.0, 0.0, 0.0)), ("Linear Max", (0.0, 0.0, 0.0)),
        ("Angular Min (degrees)", (0.0, 0.0, 0.0)),
        ("Angular Max (degrees)", (0.0, 0.0, 0.0)),
        ("Cone Limits (degrees)", (29.0, 29.0, 29.0)),
    ])
    _TYPES = {"Hinge": "LINEHINGE_CONSTRAINT", "Limited Hinge (6DOF)": "GENERIC_6DOF_CONSTRAINT",
              "Slider (6DOF)": "GENERIC_6DOF_CONSTRAINT", "Ball Socket": "POINTTOPOINT_CONSTRAINT",
              "Cone Twist (6DOF)": "CONETWIST_CONSTRAINT"}

    # Editor side (never runs in the game): warnings and viewport guides.
    class Editor:
        def on_change(self, obj, name, value):
            if name == "Target":
                if value is None:
                    return "Choose the other body of the joint"
                if value == obj:
                    return "The target can't be the object itself"
                if value.game.physics_type in {"NO_COLLISION", "STATIC", "OCCLUDER", "SENSOR", "NAVMESH"}:
                    return "Target needs Rigid Body or Dynamic physics"

        def draw_gizmo(self, obj, args, g, selected):
            from mathutils import Euler, Vector
            import math
            pivot = obj.matrix_world * Vector(args["Pivot"])
            rot = Euler([math.radians(a) for a in args["Axis (degrees)"]]).to_matrix()
            axis = obj.matrix_world.to_3x3().normalized() * rot * Vector((1.0, 0.0, 0.0))
            g.sphere(pivot, 0.08, "ORANGE")
            g.arrow(pivot, pivot + axis * 0.6, "RED", width=2)
            target = args["Target"]
            if target is not None:
                g.line(pivot, target.matrix_world.translation, "YELLOW")

    def start(self, args):
        if not args["Enabled"]: return
        target = args["Target"]
        if isinstance(target, str):    # module written by an older version
            target = self.object.scene.objects.get(target)
        if target is None or target is self.object:
            print("RigidBodyJointComponent: choose another Target")
            return
        if not self.object.getPhysicsId() or not target.getPhysicsId():
            print("RigidBodyJointComponent: owner and target need game physics")
            return
        pivot, axis = args["Pivot"], args["Axis (degrees)"]
        flags = 0x80 if args["Disable Linked Collision"] else 0
        joint_type = args["Joint Type"]
        self.constraint = Range.constraints.createConstraint(
            self.object.getPhysicsId(), target.getPhysicsId(),
            getattr(Range.constraints, self._TYPES[joint_type]),
            pivot[0], pivot[1], pivot[2], axis[0], axis[1], axis[2], flags)
        if self.constraint is None:
            print("RigidBodyJointComponent: Bullet could not create the joint")
            return
        if args["Use Breaking"]:
            self.constraint.breakingThreshold = args["Breaking Threshold"]
        self._apply_limits(args, joint_type)

    def _apply_limits(self, args, joint_type):
        if joint_type == "Hinge" or joint_type == "Ball Socket": return
        if joint_type == "Cone Twist (6DOF)":
            for dof, limit in enumerate(args["Cone Limits (degrees)"], 3):
                self.constraint.setParam(dof, 0.0, math.radians(limit))
            return
        linear_min, linear_max = args["Linear Min"], args["Linear Max"]
        angular_min, angular_max = args["Angular Min (degrees)"], args["Angular Max (degrees)"]
        if joint_type == "Limited Hinge (6DOF)":
            linear_min = linear_max = (0.0, 0.0, 0.0)
            angular_min, angular_max = (angular_min[0], 0.0, 0.0), (angular_max[0], 0.0, 0.0)
        elif joint_type == "Slider (6DOF)":
            linear_min, linear_max = (linear_min[0], 0.0, 0.0), (linear_max[0], 0.0, 0.0)
            angular_min = angular_max = (0.0, 0.0, 0.0)
        for dof in range(3):
            self.constraint.setParam(dof, linear_min[dof], linear_max[dof])
            self.constraint.setParam(dof + 3, math.radians(angular_min[dof]), math.radians(angular_max[dof]))
'''


def _joint_component_path():
    if not bpy.data.filepath:
        return None
    return os.path.join(os.path.dirname(bpy.data.filepath), "scripts", RIGID_BODY_JOINT_COMPONENT_MODULE + ".py")


def _write_joint_component(path, owner, scene):
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8") as component_file:
        component_file.write(_RIGID_BODY_JOINT_COMPONENT_TEMPLATE)


class OBJECT_OT_rigid_body_joint_component_add(Operator):
    bl_idname = "object.rigid_body_joint_component_add"
    bl_label = "Add Rigid Body Joint Component"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        path, owner = _joint_component_path(), context.active_object
        if path is None:
            self.report({'ERROR'}, "Save the .range file before adding the component")
            return {'CANCELLED'}
        try:
            _write_joint_component(path, owner, context.scene)
            scripts_dir = os.path.dirname(path)
            if scripts_dir not in sys.path: sys.path.append(scripts_dir)
            importlib.invalidate_caches()
            module = sys.modules.get(RIGID_BODY_JOINT_COMPONENT_MODULE)
            if module: importlib.reload(module)
            else: importlib.import_module(RIGID_BODY_JOINT_COMPONENT_MODULE)
        except OSError as exc:
            self.report({'ERROR'}, "Could not create component: %s" % exc)
            return {'CANCELLED'}
        except Exception:
            # Range is intentionally available only through the editor's fake
            # module while python_component_register validates the class.
            pass
        full_name = "%s.%s" % (RIGID_BODY_JOINT_COMPONENT_MODULE, RIGID_BODY_JOINT_COMPONENT_CLASS)
        if not any("%s.%s" % (component.module, component.name) == full_name for component in owner.game.components):
            try: bpy.ops.logic.python_component_register(component_name=full_name)
            except RuntimeError as exc:
                self.report({'ERROR'}, "Could not add component: %s" % exc)
                return {'CANCELLED'}
        self.report({'INFO'}, "Rigid Body Joint component added")
        return {'FINISHED'}


class OBJECT_OT_rigid_body_joint_component_refresh(Operator):
    bl_idname = "object.rigid_body_joint_component_refresh"
    bl_label = "Update Joint Component"
    bl_options = {'REGISTER', 'UNDO'}
    component_index: IntProperty(default=-1)

    def execute(self, context):
        path = _joint_component_path()
        if path is None:
            self.report({'ERROR'}, "Save the .range file before refreshing the component")
            return {'CANCELLED'}
        try:
            _write_joint_component(path, context.active_object, context.scene)
            bpy.ops.logic.python_component_reload(index=self.component_index)
        except (OSError, RuntimeError) as exc:
            self.report({'ERROR'}, "Could not refresh target list: %s" % exc)
            return {'CANCELLED'}
        self.report({'INFO'}, "Joint component updated")
        return {'FINISHED'}


class AddGameConstraintPreset(Operator):
    '''Append an original, ready-to-play Bullet constraint example'''
    bl_idname = "object.game_constraint_preset_add"
    bl_label = "Add Game Constraint Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(
        name="Constraint",
        description="Constraint example to add at the 3D cursor",
        items=_constraint_presets,
        default='HINGE',
    )

    @staticmethod
    def _asset_path():
        installed = os.path.join(os.path.dirname(bpy.app.binary_path),
                                 "demos", "Physics", "constraintsTutorial.range")
        bundled = os.path.normpath(os.path.join(os.path.dirname(__file__),
                                                "..", "..", "..", "demos", "Physics",
                                                "constraintsTutorial.range"))
        for path in (installed, bundled):
            if os.path.isfile(path):
                return path
        return None

    @staticmethod
    def _material(name, color):
        material = bpy.data.materials.get(name)
        if material is None:
            material = bpy.data.materials.new(name)
        material.diffuse_color = color
        material.diffuse_intensity = 0.9
        return material

    @staticmethod
    def _set_single_material(obj, material):
        obj.data.materials.clear()
        obj.data.materials.append(material)

    def execute(self, context):
        # A game-physics preset must be immediately playable even when added
        # to a scene that was still using Blender Render.
        context.scene.render.engine = 'BLENDER_GAME'
        asset_path = self._asset_path()
        if asset_path is None:
            self.report({'ERROR'}, "Constraint tutorial asset was not found")
            return {'CANCELLED'}

        source_names = _constraint_asset_objects[self.preset]
        with bpy.data.libraries.load(asset_path, link=False) as (data_from, data_to):
            missing = [name for name in source_names if name not in data_from.objects]
            if missing:
                self.report({'ERROR'}, "Missing constraint objects: " + ", ".join(missing))
                return {'CANCELLED'}
            data_to.objects = list(source_names)

        objects = [obj for obj in data_to.objects if obj is not None]
        if len(objects) != len(source_names):
            self.report({'ERROR'}, "Constraint preset could not be appended")
            return {'CANCELLED'}

        for obj in objects:
            context.scene.objects.link(obj)

        roots = [obj for obj in objects if obj.parent is None]
        if len(roots) != 2:
            for obj in objects:
                bpy.data.objects.remove(obj, do_unlink=True)
            self.report({'ERROR'}, "Constraint preset has an invalid parent structure")
            return {'CANCELLED'}

        center = (roots[0].location + roots[1].location) * 0.5
        offset = context.scene.cursor_location - center
        for obj in roots:
            obj.location += offset

        owner = next((obj for obj in roots if obj.constraints), None)
        joint = owner.constraints[0] if owner and owner.constraints else None
        target = joint.target if joint else None
        if joint is None or joint.type != 'RIGID_BODY_JOINT' or target not in roots:
            for obj in objects:
                bpy.data.objects.remove(obj, do_unlink=True)
            self.report({'ERROR'}, "Appended constraint lost its target relationship")
            return {'CANCELLED'}

        anchor_material = self._material("Constraint Anchor - Magenta", (0.85, 0.03, 0.28))
        body_material = self._material("Constraint Body - Cyan", (0.02, 0.58, 0.88))
        self._set_single_material(owner, anchor_material)
        self._set_single_material(target, body_material)

        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:
            obj.select = True
        context.scene.objects.active = owner
        label = dict((identifier, text) for identifier, text, description in _constraint_presets)[self.preset]
        self.report({'INFO'}, label + " added from the original tutorial")
        return {'FINISHED'}


class CopyRigidbodySettings(Operator):
    '''Copy Rigid Body settings from active object to selected'''
    bl_idname = "rigidbody.object_settings_copy"
    bl_label = "Copy Rigid Body Settings"
    bl_options = {'REGISTER', 'UNDO'}

    _attrs = (
        "type",
        "kinematic",
        "mass",
        "collision_shape",
        "use_margin",
        "collision_margin",
        "friction",
        "restitution",
        "use_deactivation",
        "use_start_deactivated",
        "deactivate_linear_velocity",
        "deactivate_angular_velocity",
        "linear_damping",
        "angular_damping",
        "collision_groups",
        "mesh_source",
        "use_deform",
        "enabled",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (obj and obj.rigid_body)

    def execute(self, context):
        obj_act = context.object
        scene = context.scene

        # deselect all but mesh objects
        for o in context.selected_objects:
            if o.type != 'MESH':
                o.select = False
            elif o.rigid_body is None:
                # Add rigidbody to object!
                scene.objects.active = o
                bpy.ops.rigidbody.object_add()
        scene.objects.active = obj_act

        objects = context.selected_objects
        if objects:
            rb_from = obj_act.rigid_body
            # copy settings
            for o in objects:
                rb_to = o.rigid_body
                if o == obj_act:
                    continue
                for attr in self._attrs:
                    setattr(rb_to, attr, getattr(rb_from, attr))

        return {'FINISHED'}


class BakeToKeyframes(Operator):
    '''Bake rigid body transformations of selected objects to keyframes'''
    bl_idname = "rigidbody.bake_to_keyframes"
    bl_label = "Bake To Keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    frame_start: IntProperty(
        name="Start Frame",
        description="Start frame for baking",
        min=0, max=300000,
        default=1,
    )
    frame_end: IntProperty(
        name="End Frame",
        description="End frame for baking",
        min=1, max=300000,
        default=250,
    )
    step: IntProperty(
        name="Frame Step",
        description="Frame Step",
        min=1, max=120,
        default=1,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (obj and obj.rigid_body)

    def execute(self, context):
        bake = []
        objects = []
        scene = context.scene
        frame_orig = scene.frame_current
        frames_step = range(self.frame_start, self.frame_end + 1, self.step)
        frames_full = range(self.frame_start, self.frame_end + 1)

        # filter objects selection
        for obj in context.selected_objects:
            if not obj.rigid_body or obj.rigid_body.type != 'ACTIVE':
                obj.select = False

        objects = context.selected_objects

        if objects:
            # store transformation data
            # need to start at scene start frame so simulation is run from the beginning
            for f in frames_full:
                scene.frame_set(f)
                if f in frames_step:
                    mat = {}
                    for i, obj in enumerate(objects):
                        mat[i] = obj.matrix_world.copy()
                    bake.append(mat)

            # apply transformations as keyframes
            for i, f in enumerate(frames_step):
                scene.frame_set(f)
                for j, obj in enumerate(objects):
                    mat = bake[i][j]
                    # convert world space transform to parent space, so parented objects don't get offset after baking
                    if (obj.parent):
                        mat = obj.matrix_parent_inverse.inverted() * obj.parent.matrix_world.inverted() * mat

                    obj.location = mat.to_translation()

                    rot_mode = obj.rotation_mode
                    if rot_mode == 'QUATERNION':
                        q1 = obj.rotation_quaternion
                        q2 = mat.to_quaternion()
                        # make quaternion compatible with the previous one
                        if q1.dot(q2) < 0.0:
                            obj.rotation_quaternion = -q2
                        else:
                            obj.rotation_quaternion = q2
                    elif rot_mode == 'AXIS_ANGLE':
                        # this is a little roundabout but there's no better way right now
                        aa = mat.to_quaternion().to_axis_angle()
                        obj.rotation_axis_angle = (aa[1], *aa[0])
                    else:  # euler
                        # make sure euler rotation is compatible to previous frame
                        # NOTE: assume that on first frame, the starting rotation is appropriate
                        obj.rotation_euler = mat.to_euler(rot_mode, obj.rotation_euler)

                bpy.ops.anim.keyframe_insert(type='BUILTIN_KSI_LocRot', confirm_success=False)

            # remove baked objects from simulation
            bpy.ops.rigidbody.objects_remove()

            # clean up keyframes
            for obj in objects:
                action = obj.animation_data.action
                for fcu in action.fcurves:
                    keyframe_points = fcu.keyframe_points
                    i = 1
                    # remove unneeded keyframes
                    while i < len(keyframe_points) - 1:
                        val_prev = keyframe_points[i - 1].co[1]
                        val_next = keyframe_points[i + 1].co[1]
                        val = keyframe_points[i].co[1]

                        if abs(val - val_prev) + abs(val - val_next) < 0.0001:
                            keyframe_points.remove(keyframe_points[i])
                        else:
                            i += 1
                    # use linear interpolation for better visual results
                    for keyframe in keyframe_points:
                        keyframe.interpolation = 'LINEAR'

            # return to the frame we started on
            scene.frame_set(frame_orig)

        return {'FINISHED'}

    def invoke(self, context, event):
        scene = context.scene
        self.frame_start = scene.frame_start
        self.frame_end = scene.frame_end

        wm = context.window_manager
        return wm.invoke_props_dialog(self)


class ConnectRigidBodies(Operator):
    '''Create rigid body constraints between selected rigid bodies'''
    bl_idname = "rigidbody.connect"
    bl_label = "Connect Rigid Bodies"
    bl_options = {'REGISTER', 'UNDO'}

    con_type: EnumProperty(
        name="Type",
        description="Type of generated constraint",
        # XXX Would be nice to get icons too, but currently not possible ;)
        items=tuple(
            (e.identifier, e.name, e.description, e. value)
            for e in bpy.types.RigidBodyConstraint.bl_rna.properties["type"].enum_items
        ),
        default='FIXED',
    )
    pivot_type: EnumProperty(
        name="Location",
        description="Constraint pivot location",
        items=(
            ('CENTER', "Center", "Pivot location is between the constrained rigid bodies"),
            ('ACTIVE', "Active", "Pivot location is at the active object position"),
            ('SELECTED', "Selected", "Pivot location is at the selected object position"),
        ),
        default='CENTER',
    )
    connection_pattern: EnumProperty(
        name="Connection Pattern",
        description="Pattern used to connect objects",
        items=(
            ('SELECTED_TO_ACTIVE', "Selected to Active", "Connect selected objects to the active object"),
            ('CHAIN_DISTANCE', "Chain by Distance", "Connect objects as a chain based on distance, starting at the active object"),
        ),
        default='SELECTED_TO_ACTIVE',
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (obj and obj.rigid_body)

    def _add_constraint(self, context, object1, object2):
        if object1 == object2:
            return

        if self.pivot_type == 'ACTIVE':
            loc = object1.location
        elif self.pivot_type == 'SELECTED':
            loc = object2.location
        else:
            loc = (object1.location + object2.location) / 2.0

        ob = bpy.data.objects.new("Constraint", object_data=None)
        ob.location = loc
        context.scene.objects.link(ob)
        context.scene.objects.active = ob
        ob.select = True

        bpy.ops.rigidbody.constraint_add()
        con_obj = context.active_object
        con_obj.empty_draw_type = 'ARROWS'
        con = con_obj.rigid_body_constraint
        con.type = self.con_type

        con.object1 = object1
        con.object2 = object2

    def execute(self, context):
        scene = context.scene
        objects = context.selected_objects
        obj_act = context.active_object
        change = False

        if self.connection_pattern == 'CHAIN_DISTANCE':
            objs_sorted = [obj_act]
            objects_tmp = context.selected_objects
            try:
                objects_tmp.remove(obj_act)
            except ValueError:
                pass

            last_obj = obj_act

            while objects_tmp:
                objects_tmp.sort(key=lambda o: (last_obj.location - o.location).length)
                last_obj = objects_tmp.pop(0)
                objs_sorted.append(last_obj)

            for i in range(1, len(objs_sorted)):
                self._add_constraint(context, objs_sorted[i - 1], objs_sorted[i])
                change = True

        else:  # SELECTED_TO_ACTIVE
            for obj in objects:
                self._add_constraint(context, obj_act, obj)
                change = True

        if change:
            # restore selection
            bpy.ops.object.select_all(action='DESELECT')
            for obj in objects:
                obj.select = True
            scene.objects.active = obj_act
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No other objects selected")
            return {'CANCELLED'}


classes = (
    AddGameConstraintPreset,
    OBJECT_OT_rigid_body_joint_component_add,
    OBJECT_OT_rigid_body_joint_component_refresh,
    BakeToKeyframes,
    ConnectRigidBodies,
    CopyRigidbodySettings,
)
