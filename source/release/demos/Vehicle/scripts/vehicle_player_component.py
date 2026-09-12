# -*- coding: utf-8 -*-
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
