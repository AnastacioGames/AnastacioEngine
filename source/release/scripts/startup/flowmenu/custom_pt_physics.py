import bpy
import importlib
import os
import sys
from bpy.types import Operator, Panel

# ==============================================================================
# CRIAÇÃO/REGISTRO DO COMPONENT DE CONDUÇÃO DO VEHICLE
# ==============================================================================
VEHICLE_COMPONENT_MODULE = "vehicle_player_component"
VEHICLE_COMPONENT_CLASS = "VehiclePlayerComponent"

VEHICLE_COMPONENT_TEMPLATE = '''# -*- coding: utf-8 -*-
"""Controle jogável mínimo para o carro de teste da Range Engine.

Anexe ``VehiclePlayerComponent`` diretamente no objeto Chassis. O veículo em
si já é criado automaticamente pela engine a partir do painel Physics >
Vehicle (marque "is_vehicle" e preencha a lista de rodas com raio/suspensão/
steering/drive por roda); este componente só lê esse veículo já pronto
(``self.object.getVehicle()``) e aplica o controle de jogador nele.
Controles padrão: W acelera, S dá ré, A/D esterçam, Espaço freia, Shift
esquerdo é o freio de mão. Se ``game.vehicle_steering_wheel`` estiver
preenchido no painel Vehicle, o objeto referenciado gira no seu eixo Y
local para acompanhar o esterço atual.
"""

import math
from collections import OrderedDict

import mathutils
import Range


class VehiclePlayerComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "PHYSICS"),
        ("C_Header /Carro jogavel/PHYSICS", True),
        ("Engine Force", 3200.0),
        ("Reverse Force", 1800.0),
        ("Brake Force", 120.0),
        ("Handbrake Force", 250.0),
        ("Max Steering Angle (deg)", 26.0),
        ("Steering Speed (deg/s)", 180.0),
        ("Speed-Sensitive Steering", True),
        ("Steering Sign", 1.0),
        ("Engine Sign", 1.0),
        ("Steering Wheel Multiplier", 4.0),
    ])

    # Speed-sensitive steering: linear falloff from full angle at 0 km/h down
    # to MIN_STEERING_FACTOR at REFERENCE_SPEED_KMH and beyond. Pure feeling
    # tuning, no physical basis to justify a more complex curve.
    REFERENCE_SPEED_KMH = 120.0
    MIN_STEERING_FACTOR = 0.3

    # Torque-based engine force (only used when game.vehicle_max_torque > 0,
    # set in the Physics > Vehicle panel). No gearbox yet, so RPM is simulated
    # directly from wheel angular speed (as if final drive ratio == 1:1);
    # torque falls off linearly from full at 0 RPM to 30% at max RPM (arcade
    # feel, no clutch/curve). TORQUE_TO_FORCE_SCALE converts torque (Nm-ish)
    # into the same arbitrary force units applyEngineForce already uses.
    MIN_TORQUE_FACTOR_AT_MAX_RPM = 0.3
    TORQUE_TO_FORCE_SCALE = 10.0
    FALLBACK_MAX_RPM = 6000.0

    def start(self, args):
        self._args = args
        self._vehicle = self.object.getVehicle()
        if self._vehicle is None:
            self._error("'%s' não tem veículo nativo; marque is_vehicle e preencha "
                        "vehicle_wheels no painel Physics > Vehicle" % self.object.name)
            return

        self._num_wheels = self._vehicle.getNumWheels()
        configs = [self._vehicle.getWheelConfig(i) for i in range(self._num_wheels)]
        self._steering_wheels = [i for i, c in enumerate(configs) if c["hasSteering"]]

        explicit_drive_wheels = [i for i, c in enumerate(configs) if c.get("isDriveWheel")]
        if explicit_drive_wheels:
            # has_drive foi marcado manualmente no painel Vehicle para pelo menos
            # uma roda; respeita essa escolha (permite FWD/RWD/AWD reais).
            self._drive_wheels = explicit_drive_wheels
        else:
            # Nenhuma roda marcada como "Drive": mantém o comportamento legado
            # (todas as rodas não-esterçantes recebem força de motor) para não
            # quebrar carros/presets já configurados antes deste campo existir.
            self._drive_wheels = [i for i in range(self._num_wheels) if i not in self._steering_wheels]

        # Orientação de repouso do volante visual, capturada uma vez para que a
        # rotação de esterço seja sempre relativa a ela (evita deriva ao
        # acumular pequenas rotações quadro a quadro).
        self._steering_wheel_base_orientation = None

        # Esterço atual (rad), interpolado gradualmente em direção ao alvo em
        # vez de saltar direto pro valor máximo — tanto para virar quanto para
        # voltar ao centro.
        self._current_steer_value = 0.0

        print("VehiclePlayer: pronto (%d rodas, %d de direção, %d motrizes). "
              "W acelera, S ré, A/D esterçam, Espaço freia, Shift é freio de mão." %
              (self._num_wheels, len(self._steering_wheels), len(self._drive_wheels)))

    def update(self):
        if self._vehicle is None:
            return
        try:
            throttle, steering, brake, handbrake = self._read_input()
            engine_force = self._compute_engine_force(throttle)
            target_steer_value = self._compute_steer_value(steering)
            steer_value = self._smooth_steer_value(target_steer_value)

            self._apply_braking(brake, handbrake)
            self._apply_engine_force(engine_force)
            self._apply_steering(steer_value)
            self._update_steering_wheel_visual(steer_value)
        except (ReferenceError, ValueError) as error:
            self._error("veículo deixou de ser válido: %r" % (error,))
            self._vehicle = None

    def _read_input(self):
        throttle = float(self._held(Range.events.WKEY)) - float(self._held(Range.events.SKEY))
        steering = float(self._held(Range.events.AKEY)) - float(self._held(Range.events.DKEY))
        brake = float(self._args["Brake Force"]) if self._held(Range.events.SPACEKEY) else 0.0
        handbrake = float(self._args["Handbrake Force"]) if self._held(Range.events.LEFTSHIFTKEY) else 0.0
        return throttle, steering, brake, handbrake

    def _compute_engine_force(self, throttle):
        engine_sign = float(self._args["Engine Sign"])
        max_torque = self.object.getVehicleMaxTorque()
        if max_torque <= 0.0:
            # game.vehicle_max_torque não configurado (0): comportamento legado,
            # força fixa por marcha de aceleração/ré.
            if throttle >= 0.0:
                return engine_sign * float(self._args["Engine Force"]) * throttle
            return engine_sign * float(self._args["Reverse Force"]) * throttle

        torque = max_torque * self._torque_factor_at_current_rpm()
        return engine_sign * torque * self.TORQUE_TO_FORCE_SCALE * throttle

    def _torque_factor_at_current_rpm(self):
        max_rpm = self.object.getVehicleMaxRPM()
        if max_rpm <= 0.0:
            max_rpm = self.FALLBACK_MAX_RPM

        rpm_fraction = min(self._simulated_rpm() / max_rpm, 1.0)
        return 1.0 - rpm_fraction * (1.0 - self.MIN_TORQUE_FACTOR_AT_MAX_RPM)

    def _simulated_rpm(self):
        # Sem gearbox ainda: assume relação final 1:1 (RPM do motor == RPM da
        # roda). Usa o raio da primeira roda motriz disponível; se não houver
        # config de roda (não deveria acontecer, start() já validou), assume
        # o raio padrão de 0.3m usado em outros lugares do sistema de veículo.
        radius = 0.3
        if self._drive_wheels:
            config = self._vehicle.getWheelConfig(self._drive_wheels[0])
            if config.get("wheelRadius", 0.0) > 0.0:
                radius = config["wheelRadius"]

        speed_m_s = abs(self._vehicle.getCurrentSpeedKmh()) / 3.6
        wheel_angular_speed = speed_m_s / radius  # rad/s
        return wheel_angular_speed * 60.0 / (2.0 * math.pi)

    def _compute_steer_value(self, steering):
        max_angle_rad = math.radians(float(self._args["Max Steering Angle (deg)"]))
        if bool(self._args["Speed-Sensitive Steering"]):
            max_angle_rad *= self._speed_steering_factor()
        return steering * max_angle_rad * float(self._args["Steering Sign"])

    def _speed_steering_factor(self):
        speed_kmh = abs(self._vehicle.getCurrentSpeedKmh())
        t = min(speed_kmh / self.REFERENCE_SPEED_KMH, 1.0)
        return 1.0 - t * (1.0 - self.MIN_STEERING_FACTOR)

    def _smooth_steer_value(self, target_steer_value):
        # Aproxima o esterço atual do alvo a uma taxa fixa (graus/s), em vez
        # de aplicar o valor máximo de uma vez — tanto virando quanto
        # voltando ao centro. dt vem do motor (mesmo passo usado pela física).
        max_step = math.radians(float(self._args["Steering Speed (deg/s)"])) * Range.logic.deltaTime()
        delta = target_steer_value - self._current_steer_value
        if delta > max_step:
            delta = max_step
        elif delta < -max_step:
            delta = -max_step
        self._current_steer_value += delta
        return self._current_steer_value

    def _apply_braking(self, brake_force, handbrake_force):
        for wheel_index in range(self._num_wheels):
            force = brake_force
            if wheel_index in self._drive_wheels:
                force = max(force, handbrake_force)
            self._vehicle.applyBraking(force, wheel_index)

    def _apply_engine_force(self, force):
        for wheel_index in self._drive_wheels:
            self._vehicle.applyEngineForce(force, wheel_index)
        for wheel_index in self._steering_wheels:
            if wheel_index not in self._drive_wheels:
                self._vehicle.applyEngineForce(0.0, wheel_index)

    def _apply_steering(self, steer_value):
        for wheel_index in self._steering_wheels:
            self._vehicle.setSteeringValue(steer_value, wheel_index)

    def _update_steering_wheel_visual(self, steer_value):
        steering_wheel = self.object.getVehicleSteeringWheel()
        if steering_wheel is None:
            return
        if self._steering_wheel_base_orientation is None:
            self._steering_wheel_base_orientation = steering_wheel.localOrientation.copy()

        target_angle = -steer_value * float(self._args["Steering Wheel Multiplier"])
        # Gira em torno do eixo Y *local* do próprio volante via matriz, em vez
        # de somar direto num Euler decomposto: se o volante tiver qualquer
        # inclinação nos eixos X/Z (montagem realista), mexer só no euler.y
        # acopla os eixos (gimbal) e o giro fica bambo/errático. Multiplicar a
        # matriz de rotação Y pela orientação-base sempre gira em torno do Y
        # local do objeto, não importa a inclinação de repouso.
        spin = mathutils.Matrix.Rotation(target_angle, 3, 'Y')
        steering_wheel.localOrientation = self._steering_wheel_base_orientation * spin

    def _held(self, key):
        status = Range.logic.keyboard.events.get(key, 0)
        return status in (Range.logic.KX_INPUT_ACTIVE, Range.logic.KX_INPUT_JUST_ACTIVATED)

    @staticmethod
    def _error(message):
        print("VehiclePlayer: ERRO - %s" % message)
'''


class OBJECT_OT_vehicle_set_drive_type(Operator):
    bl_idname = "object.vehicle_set_drive_type"
    bl_label = "Set Drive Type"
    bl_description = ("Turns 'Drive' on or off on the right wheels by their Y position relative to the "
                      "chassis (Y+ = front, Y- = rear, following the project convention). Bulk editing "
                      "shortcut; creates no new data, only sets has_drive per wheel")
    bl_options = {'UNDO'}

    drive_type: bpy.props.EnumProperty(
        name="Drive Type",
        items=[
            ('FWD', "FWD", "Only the front wheels (positive Y) get traction"),
            ('RWD', "RWD", "Only the rear wheels (negative Y) get traction"),
            ('AWD', "AWD", "All wheels get traction"),
        ],
    )

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.game.is_vehicle and len(ob.vehicle_wheels) > 0

    def execute(self, context):
        ob = context.active_object
        chassis_inv = ob.matrix_world.inverted()

        for wheel in ob.vehicle_wheels:
            if wheel.object is None:
                continue
            local_y = (chassis_inv * wheel.object.matrix_world.translation).y
            if self.drive_type == 'AWD':
                wheel.has_drive = True
            elif self.drive_type == 'FWD':
                wheel.has_drive = local_y >= 0.0
            else:  # RWD
                wheel.has_drive = local_y < 0.0

        return {'FINISHED'}


class OBJECT_OT_vehicle_add_player_component(Operator):
    bl_idname = "object.vehicle_add_player_component"
    bl_label = "Add Vehicle Component"
    bl_description = ("Create scripts/vehicle_player_component.py if it doesn't exist yet, "
                       "and add it to this object's components")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        from .functions.set_scripts_dir import set_scripts_dir

        blend_dir = set_scripts_dir()
        if not blend_dir:
            self.report({'ERROR'}, "Save the .blend file before adding the component.")
            return {'CANCELLED'}

        scripts_dir = os.path.join(blend_dir, "scripts")
        filepath = os.path.join(scripts_dir, VEHICLE_COMPONENT_MODULE + ".py")

        try:
            if not os.path.isdir(scripts_dir):
                os.makedirs(scripts_dir)
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as fp:
                    fp.write(VEHICLE_COMPONENT_TEMPLATE)
        except OSError as exc:
            self.report({'ERROR'}, "Could not create component file: {}".format(exc))
            return {'CANCELLED'}

        ob = context.active_object
        full_name = "{}.{}".format(VEHICLE_COMPONENT_MODULE, VEHICLE_COMPONENT_CLASS)
        already_added = any("{}.{}".format(comp.module, comp.name) == full_name
                             for comp in ob.game.components)
        if already_added:
            self.report({'INFO'}, "Vehicle component already added to this object.")
            return {'FINISHED'}

        if scripts_dir not in sys.path:
            sys.path.append(scripts_dir)
        try:
            importlib.invalidate_caches()
            if VEHICLE_COMPONENT_MODULE in sys.modules:
                importlib.reload(sys.modules[VEHICLE_COMPONENT_MODULE])
            else:
                importlib.import_module(VEHICLE_COMPONENT_MODULE)
        except Exception:
            pass

        try:
            bpy.ops.logic.python_component_register(component_name=full_name)
        except Exception:
            try:
                bpy.ops.logic.python_component_add()
                new_comp = ob.game.components[-1]
                new_comp.module = VEHICLE_COMPONENT_MODULE
                new_comp.name = VEHICLE_COMPONENT_CLASS
            except Exception as exc:
                self.report({'ERROR'}, "Could not add component: {}".format(exc))
                return {'CANCELLED'}

        self.report({'INFO'}, "Vehicle component added.")
        return {'FINISHED'}


# ==============================================================================
# CLASSE BASE PARA A ABA DE FÍSICA
# ==============================================================================
class CustomPhysicsButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "physics"


# ==============================================================================
# PAINEL PRINCIPAL DE FÍSICA
# ==============================================================================
class CUSTOM_PT_game_physics(CustomPhysicsButtonsPanel, Panel):
    bl_label = "Physics"
    bl_idname = "PHYSICS_PT_game_physics_custom" # ID único para o seu Add-on
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
        if physics_type == "CHARACTER":
            iconType = "POSE_HLT"
        elif physics_type == "DYNAMIC":
            iconType = "VIEW3D"
        elif physics_type == "STATIC":
            iconType = "VIEW3D"
        elif physics_type == "RIGID_BODY":
            iconType = "VIEW3D"
        elif physics_type == "SOFT_BODY":
            iconType = "SNAP_VOLUME"
        elif physics_type == "OCCLUDER":
            iconType = "RESTRICT_RENDER_ON"
        elif physics_type == "SENSOR":
            iconType = "RESTRICT_VIEW_OFF"
        elif physics_type == "NAVMESH":
            iconType = "GHOST_ENABLED"
            
        layout.prop(game, "physics_type", icon=iconType)
        layout.separator()

        if physics_type == 'CHARACTER':
            box = layout.box()
            row = box.row()
            row.prop(game, "use_actor")
            row.prop(ob, "hide_render", text="Invisible")

            attr_box = layout.box()
            attr_box.label(text="Character Attributes:", icon="OUTLINER_OB_ARMATURE")
            split = attr_box.split()

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
            box = layout.box()
            split = box.split()
            col = split.column()
            col.prop(game, "use_actor")
            col.prop(game, "use_ghost")
            col.prop(ob, "hide_render", text="Invisible")

            col = split.column()
            col.prop(game, "use_physics_fh")
            col.prop(game, "use_rotate_from_normal")
            col.prop(game, "use_sleep")

            attr_box = layout.box()
            if physics_type == "DYNAMIC":
                attr_box.label(text="Dynamic Attributes:", icon="VIEW3D")
            else:
                attr_box.label(text="Rigid Body Attributes:", icon="VIEW3D")
            
            split = attr_box.split()
            col = split.column()
            col.prop(game, "mass")
            col.prop(game, "radius")
            col.prop(game, "form_factor")
            col.prop(game, "elasticity", slider=True)

            col = split.column()
            col.label(text="Friction:", icon="HAIR")
            row_fric = col.row(align=True)
            row_fric.prop(game, "friction", text="Normal")
            row_fric.prop(game, "rolling_friction", text="Rolling")
            col.prop(game, "use_anisotropic_friction")
            if game.use_anisotropic_friction:
                col.prop(game, "friction_coefficients", text="", slider=True)

            vel_box = layout.box()
            split = vel_box.split()
            col = split.column()
            col.label(text="Linear Velocity:", icon="FORCE_HARMONIC")
            sub = col.column(align=True)
            sub.prop(game, "velocity_min", text="Minimum")
            sub.prop(game, "velocity_max", text="Maximum")

            col = split.column()
            col.label(text="Angular Velocity:", icon="FORCE_MAGNETIC")
            sub = col.column(align=True)
            sub.prop(game, "angular_velocity_min", text="Minimum")
            sub.prop(game, "angular_velocity_max", text="Maximum")

            damp_box = layout.box()
            damp_box.label(text="Damping:", icon="META_CUBE")
            row = damp_box.row()
            row.prop(game, "damping", text="Translation", slider=True)
            row.prop(game, "rotation_damping", text="Rotation", slider=True)

            lock_box = layout.box()
            split = lock_box.split()
            
            col = split.column()
            col.label(text="Lock Translation:", icon="LINKED")
            row = col.row()
            row.prop(game, "lock_location_x", text="X")
            row.prop(game, "lock_location_y", text="Y")
            row.prop(game, "lock_location_z", text="Z")

            if physics_type == 'RIGID_BODY':
                col = split.column()
                col.label(text="Lock Rotation:", icon="LINKED")
                row = col.row()
                row.prop(game, "lock_rotation_x", text="X")
                row.prop(game, "lock_rotation_y", text="Y")
                row.prop(game, "lock_rotation_z", text="Z")

        elif physics_type == 'SOFT_BODY':
            box = layout.box()
            row = box.row()
            row.prop(game, "use_actor")
            row.prop(game, "use_ghost")
            row.prop(ob, "hide_render", text="Invisible")

            split_main = layout.split()
            
            col1 = split_main.column()
            
            gen_box = col1.box()
            gen_box.label(text="General Attributes:", icon="SNAP_VOLUME")
            gen_box.prop(game, "mass")
            gen_box.prop(soft, "linear_stiffness", slider=True)
            gen_box.prop(soft, "dynamic_friction", slider=True)
            gen_box.prop(soft, "kdp", text="Damping", slider=True)
            gen_box.prop(soft, "collision_margin", slider=True)
            gen_box.prop(soft, "kvcf", text="Velocity Correction", slider=True)
            gen_box.prop(soft, "use_bending_constraints", text="Bending Constraints")
            sub = gen_box.column()
            sub.active = soft.use_bending_constraints
            sub.prop(soft, "bending_distance")
            gen_box.prop(soft, "use_shape_match")
            sub = gen_box.column()
            sub.active = soft.use_shape_match
            sub.prop(soft, "shape_threshold", slider=True)

            solv_box = col1.box()
            solv_box.label(text="Solver Iterations:", icon="SNAP_FACE")
            solv_box.prop(soft, "position_solver_iterations", text="Position")
            solv_box.prop(soft, "velocity_solver_iterations", text="Velocity")
            solv_box.prop(soft, "cluster_solver_iterations", text="Cluster")
            solv_box.prop(soft, "drift_solver_iterations", text="Drift")

            col2 = split_main.column()
            
            hard_box = col2.box()
            hard_box.label(text="Hardness:", icon="OUTLINER_OB_FORCE_FIELD")
            hard_box.prop(soft, "kchr", text="Rigid Contacts", slider=True)
            hard_box.prop(soft, "kkhr", text="Kinetic Contacts", slider=True)
            hard_box.prop(soft, "kshr", text="Soft Contacts", slider=True)
            hard_box.prop(soft, "kahr", text="Anchors", slider=True)

            clus_box = col2.box()
            clus_box.label(text="Cluster Collision:", icon="GROUP")
            clus_box.prop(soft, "use_cluster_rigid_to_softbody")
            clus_box.prop(soft, "use_cluster_soft_to_softbody")
            sub = clus_box.column()
            sub.active = (soft.use_cluster_rigid_to_softbody or soft.use_cluster_soft_to_softbody)
            sub.prop(soft, "cluster_iterations", text="Iterations")
            sub.prop(soft, "ksrhr_cl", text="Rigid Hardness", slider=True)
            sub.prop(soft, "kskhr_cl", text="Kinetic Hardness", slider=True)
            sub.prop(soft, "ksshr_cl", text="Soft Hardness", slider=True)
            sub.prop(soft, "ksr_split_cl", text="Rigid Impulse Split", slider=True)
            sub.prop(soft, "ksk_split_cl", text="Kinetic Impulse Split", slider=True)
            sub.prop(soft, "kss_split_cl", text="Soft Impulse Split", slider=True)

            split_bottom = layout.split()
            
            col_vol = split_bottom.column()
            vol_box = col_vol.box()
            vol_box.label(text="Volume:", icon="META_BALL")
            vol_box.prop(soft, "kpr", text="Pressure Coefficient")
            vol_box.prop(soft, "kvc", text="Volume Conservation")

            col_aero = split_bottom.column()
            aero_box = col_aero.box()
            aero_box.label(text="Aerodynamics:", icon="FORCE_DRAG")
            aero_box.prop(soft, "kdg", text="Drag Coefficient")
            aero_box.prop(soft, "klf", text="Lift Coefficient")

        elif physics_type == 'STATIC':
            box = layout.box()
            row = box.row()
            row.prop(game, "use_actor")
            row.prop(game, "use_ghost")
            row.prop(ob, "hide_render", text="Invisible")
            row2 = box.row()
            row2.prop(game, "use_occlude_culling", text="Occluder (keeps collision)")

            attr_box = layout.box()
            attr_box.label(text="Static Attributes:", icon="VIEW3D")
            split = attr_box.split()

            col = split.column()
            col.prop(game, "radius")
            col.prop(game, "elasticity", slider=True)
            
            col = split.column()
            col.label(text="Friction:", icon="HAIR")
            row_fric = col.row(align=True)
            row_fric.prop(game, "friction", text="Normal")
            row_fric.prop(game, "rolling_friction", text="Rolling")
            col.prop(game, "use_anisotropic_friction")
            if game.use_anisotropic_friction:
                col.prop(game, "friction_coefficients", text="", slider=True)

        elif physics_type == 'SENSOR':
            box = layout.box()
            row = box.row()
            row.prop(game, "use_actor", text="Detect Actors")
            row.prop(ob, "hide_render", text="Invisible")

            attr_box = layout.box()
            attr_box.label(text="Sensor Attributes:", icon="RESTRICT_VIEW_OFF")
            attr_box.prop(game, "radius")

        elif physics_type in {'INVISIBLE', 'NO_COLLISION', 'OCCLUDER'}:
            box = layout.box()
            box.prop(ob, "hide_render", text="Invisible")

        elif physics_type == 'NAVMESH':
            box = layout.box()
            box.label(text="Navigation Mesh:", icon="GHOST_ENABLED")
            split = box.split()
            
            col = split.column()
            col.operator("mesh.navmesh_face_copy")
            col.operator("mesh.navmesh_face_add")
            col = split.column()
            col.operator("mesh.navmesh_reset")
            col.operator("mesh.navmesh_clear")

        if physics_type in {"STATIC", "DYNAMIC", "RIGID_BODY"}:
            ff_box = layout.box()
            ff_box.label(text="Force Field:", icon="FORCE_FORCE")
            split = ff_box.split()
            col = split.column()
            col.prop(game, "fh_force")
            col.prop(game, "fh_damping", slider=True)
            col = split.column()
            col.prop(game, "fh_distance")
            col.prop(game, "use_fh_normal")


# ==============================================================================
# PAINÉIS SECUNDÁRIOS DE FÍSICA
# ==============================================================================
class CUSTOM_PT_game_collision_bounds(CustomPhysicsButtonsPanel, Panel):
    bl_label = "Collision Bounds"
    bl_idname = "PHYSICS_PT_game_collision_bounds_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        game = context.object.game
        rd = context.scene.render
        return (rd.engine in cls.COMPAT_ENGINES) and (game.physics_type in {'SENSOR', 'STATIC', 'DYNAMIC', 'RIGID_BODY', 'CHARACTER', 'SOFT_BODY'})

    def draw_header(self, context):
        self.layout.prop(context.active_object.game, "use_collision_bounds", text="")

    def draw(self, context):
        layout = self.layout
        game = context.active_object.game
        
        main_box = layout.box()
        main_box.active = game.use_collision_bounds
        
        split = main_box.split()

        col = split.column()
        col.prop(game, "collision_bounds_type", text="Bounds")
        if (game.collision_bounds_type == "TRIANGLE_MESH"):
            col.prop(game, "collision_bound")

        col = split.column()
        col.prop(game, "collision_margin", text="Margin", slider=True)
        
        sub = col.row()
        sub.active = game.physics_type not in {'SOFT_BODY', 'CHARACTER'}
        sub.prop(game, "use_collision_compound", text="Children Compound")
        
        mask_box = layout.box()
        mask_box.active = game.use_collision_bounds
        mask_box.label(text="Collision Groups:", icon="GROUP")
        
        split = mask_box.split()
        col = split.column()
        col.prop(game, "collision_group")
        col = split.column()
        col.prop(game, "collision_mask")


class PHYSICS_PT_game_vehicle(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "vehicle"
    bl_label = "Vehicle"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        rd = context.scene.render
        return ob and ob.game and (rd.engine in cls.COMPAT_ENGINES)

    def draw_header(self, context):
        game = context.active_object.game

        if game.physics_type in {'RIGID_BODY', 'DYNAMIC'}:
            self.layout.prop(game, "is_vehicle", text="")

    def draw(self, context):
        layout = self.layout

        ob = context.active_object
        game = ob.game

        if game.physics_type not in {'RIGID_BODY', 'DYNAMIC'}:
            layout.label(text="Only Rigid Body/Dynamic objects can be a Vehicle.")
            return

        col = layout.column()
        col.active = game.is_vehicle

        col.prop(ob, "vehicle_steering_wheel", text="Steering Wheel")
        col.row(align=True).prop(ob, "vehicle_com_offset", text="Center of Mass Offset")

        row = col.row(align=True)
        row.label(text="Drive Type:")
        row.operator("object.vehicle_set_drive_type", text="FWD").drive_type = 'FWD'
        row.operator("object.vehicle_set_drive_type", text="RWD").drive_type = 'RWD'
        row.operator("object.vehicle_set_drive_type", text="AWD").drive_type = 'AWD'

        row = col.row(align=True)
        row.prop(ob, "vehicle_max_torque", text="Max Torque")
        row.prop(ob, "vehicle_max_rpm", text="Max RPM")

        for i, wheel in enumerate(ob.vehicle_wheels):
            box = col.box()
            row = box.row(align=True)
            row.prop(wheel, "show_expanded", text="", emboss=False)
            row.prop(wheel, "object", text="Wheel %d" % (i + 1))
            row.operator("object.vehicle_wheel_remove", text="", icon='PANEL_CLOSE').index = i

            if wheel.show_expanded:
                split = box.split(factor=0.5)

                col_wheel = split.column(align=True)
                col_wheel.label(text="Wheel:")
                col_wheel.prop(wheel, "radius")
                col_wheel.prop(wheel, "friction")
                row_flags = col_wheel.row(align=True)
                row_flags.prop(wheel, "has_steering", text="Steering", toggle=True)
                row_flags.prop(wheel, "has_drive", text="Drive", toggle=True)

                col_susp = split.column(align=True)
                col_susp.label(text="Suspension:")
                col_susp.prop(wheel, "suspension_rest_length", text="Rest Length")
                col_susp.prop(wheel, "suspension_stiffness", text="Stiffness")
                col_susp.prop(wheel, "suspension_damping", text="Damping")
                col_susp.prop(wheel, "suspension_compression", text="Compression")
                col_susp.prop(wheel, "roll_influence", text="Roll Influence")
                col_susp.prop(wheel, "max_suspension_travel", text="Max Travel")
                col_susp.prop(wheel, "max_suspension_force", text="Max Force")

        row = col.row(align=True)
        row.operator("object.vehicle_wheel_add", text="Add Wheel", icon='ZOOMIN')

        col.separator()
        col.prop(ob, "gearbox_type", text="Gearbox")

        for i, gear in enumerate(ob.vehicle_gears):
            row = col.row(align=True)
            label = "Reverse" if gear.ratio < 0.0 else "Gear %d" % (i + 1)
            row.prop(gear, "ratio", text=label)
            row.operator("object.vehicle_gear_remove", text="", icon='PANEL_CLOSE').index = i

        row = col.row(align=True)
        row.operator("object.vehicle_gear_add", text="Add Gear", icon='ZOOMIN')

        row = col.row(align=True)
        row.operator("object.vehicle_add_player_component", text="Add Vehicle Component", icon='PLUGIN')