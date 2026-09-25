import bpy
import importlib
import os
import sys
from bpy.types import Operator, Panel
from bpy.app.translations import pgettext_tip as tip_

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
local para acompanhar o esterço atual. Se houver marchas cadastradas em
``game.vehicle_gears``, o câmbio (automático por RPM, ou manual com E/Q)
seleciona a marcha atual e sua relação multiplica a força de motor. As
marchas (e o tipo de câmbio) são cadastradas no painel Physics > Vehicle.
As teclas de controle são configuráveis na seção "Controles". O chassi
publica as game properties ``vehicle_gearbox``, ``vehicle_gear``,
``vehicle_rpm`` e ``vehicle_speed_kmh``, lidas pela aba Overview do Vehicle
Lab (e úteis para HUD).
"""

import math
import os
import time
from collections import OrderedDict

import mathutils
import Range


class VehiclePlayerComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "AUTO"),
        ("C_Header /Motor/AUTO", True),
        ("Engine Force", 3200.0),
        ("Reverse Force", 1800.0),
        ("Invert Direction", False),
        ("Throttle Time (s)", 0.4),
        ("Engine Inertia", 1.0),
        ("C_Header /Freios/FORCE_FORCE", True),
        ("Brake Force", 120.0),
        ("Handbrake Force", 250.0),
        ("C_Header /Direcao/MAN_ROT", True),
        ("Max Steering Angle (deg)", 26.0),
        ("Steering Speed (deg/s)", 180.0),
        ("Speed-Sensitive Steering", True),
        ("Steering Sign", 1.0),
        ("Steering Wheel Multiplier", 4.0),
        ("C_Header /Moto/MOD_PHYSICS", True),
        ("Motorcycle", False),
        ("Max Lean (deg)", 35.0),
        ("Balance Strength", 60.0),
        ("Balance Damping", 12.0),
        ("Max Wheelie (deg)", 45.0),
        ("Wheelie Force", 30.0),
        ("Wheelie Min Speed", 5.0),
        ("C_Header /Cambio/DRIVER", True),
        ("Final Drive", 1.0),
        ("Idle RPM", 800.0),
        ("Rev Limiter", True),
        ("Launch RPM", 2500.0),
        ("Engine Brake", 40.0),
        ("Upshift RPM", 5500.0),
        ("Downshift RPM", 2000.0),
        ("Shift Up Key", "EKEY"),
        ("Shift Down Key", "QKEY"),
        ("C_Header /Som/SOUND", True),
        ("Engine Sound", ""),
        ("Engine Volume", 0.8),
        ("Idle Pitch", 0.6),
        ("Max RPM Pitch", 2.0),
        ("C_Header /Controles/KEY_HLT", False),
        ("Throttle Key", "WKEY"),
        ("Reverse Key", "SKEY"),
        ("Steer Left Key", "AKEY"),
        ("Steer Right Key", "DKEY"),
        ("Brake Key", "SPACEKEY"),
        ("Handbrake Key", "LEFTSHIFTKEY"),
        ("Wheelie Key", "LEFTSHIFTKEY"),
        ("C_Header /Joystick/GAME", True),
        ("Use Joystick", True),
        ("Joystick Index", 0),
        ("Joystick Deadzone", 0.15),
    ])

    # Layout padrão de controle (SDL GameController, Xbox/PlayStation): eixos
    # 0 analógico esquerdo X, 4 gatilho esquerdo, 5 gatilho direito; botões
    # 1 B/Círculo, 2 X/Quadrado, 9 LB/L1, 10 RB/R1.
    JOY_AXIS_STEER = 0
    JOY_AXIS_BACK = 4
    JOY_AXIS_GAS = 5
    JOY_BUTTON_WHEELIE = 0
    JOY_BUTTON_BRAKE = 1
    JOY_BUTTON_HANDBRAKE = 2
    JOY_BUTTON_SHIFT_DOWN = 9
    JOY_BUTTON_SHIFT_UP = 10

    # Speed-sensitive steering: linear falloff from full angle at 0 km/h down
    # to MIN_STEERING_FACTOR at REFERENCE_SPEED_KMH and beyond. Pure feeling
    # tuning, no physical basis to justify a more complex curve.
    REFERENCE_SPEED_KMH = 120.0
    MIN_STEERING_FACTOR = 0.3

    # Torque-based engine force (only used when vehicle_max_torque > 0, set in
    # Physics > Vehicle or the Vehicle Lab). Max Torque is in Nm at the
    # crankshaft: force at the wheel (N) = torque x gear x Final Drive / wheel
    # radius, the real formula, so spec-sheet values (e.g. 175 Nm) and a real
    # chassis mass give real acceleration. Torque falls off linearly from
    # full at 0 RPM to 30% at max RPM (no torque curve).
    MIN_TORQUE_FACTOR_AT_MAX_RPM = 0.3
    FALLBACK_MAX_RPM = 6000.0

    # Deve casar com OB_GEARBOX_* em DNA_object_types.h.
    GEARBOX_AUTOMATIC = 0
    GEARBOX_MANUAL = 1

    # Câmbio automático só alterna entre marcha à ré e a 1ª marcha à frente
    # abaixo desta velocidade, pra não trocar de sentido em movimento (imita
    # a trava de um câmbio real).
    REVERSE_ENGAGE_SPEED_KMH = 5.0

    # Resposta do giro (1/s): o RPM persegue o alvo em vez de saltar, como a
    # inércia do volante do motor. Abaixo de ENGINE_BRAKE_MIN_SPEED_KMH o freio
    # motor desliga para o carro não andar para trás sozinho.
    RPM_RESPONSE = 10.0
    ENGINE_BRAKE_MIN_SPEED_KMH = 3.0

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

        self._gear_ratios = self._read_gear_ratios()
        self._gearbox_type = self.object.getVehicleGearboxType()
        self._current_gear_index = self._first_forward_gear_index() or 0
        # Câmbio manual começa em ponto morto (N), como num carro real.
        self._neutral = self._gearbox_type == self.GEARBOX_MANUAL
        self._shift_up_key = self._key_arg("Shift Up Key", "EKEY")
        self._shift_down_key = self._key_arg("Shift Down Key", "QKEY")
        self._throttle_key = self._key_arg("Throttle Key", "WKEY")
        self._reverse_key = self._key_arg("Reverse Key", "SKEY")
        self._steer_left_key = self._key_arg("Steer Left Key", "AKEY")
        self._steer_right_key = self._key_arg("Steer Right Key", "DKEY")
        self._brake_key = self._key_arg("Brake Key", "SPACEKEY")
        self._handbrake_key = self._key_arg("Handbrake Key", "LEFTSHIFTKEY")
        self._wheelie_key = self._key_arg("Wheelie Key", "LEFTSHIFTKEY")
        self._prev_shift_up_held = False
        self._prev_shift_down_held = False
        self._joy = self._empty_joy()

        self._engine_rpm = float(self._args.get("Idle RPM", 0.0))
        self._pedal = 0.0
        self._last_time = time.perf_counter()
        self._engine_sound_handle = None
        self._engine_sound_device = None
        self._start_engine_sound()


        print("VehiclePlayer: pronto (%d rodas, %d de direção, %d motrizes, %d marchas)." %
              (self._num_wheels, len(self._steering_wheels), len(self._drive_wheels),
               len(self._gear_ratios)))

    def update(self):
        if self._vehicle is None:
            return
        try:
            self._poll_joystick()
            throttle, steering, brake, handbrake = self._read_input()
            self._refresh_gearbox()
            self._update_gear_selection(throttle)
            throttle, pedal_brake = self._resolve_pedals(throttle)
            throttle = self._ramp_pedal(throttle)
            brake = max(brake, pedal_brake)
            self._update_engine_rpm(throttle)
            engine_force = self._compute_engine_force(throttle)
            target_steer_value = self._compute_steer_value(steering)
            steer_value = self._smooth_steer_value(target_steer_value)

            self._apply_braking(brake, handbrake)
            self._apply_engine_force(engine_force)
            self._apply_steering(steer_value)
            self._apply_balance(steering)
            self._update_steering_wheel_visual(steer_value)
            self._update_engine_sound(throttle)
            self._publish_telemetry()
        except (ReferenceError, ValueError) as error:
            self._error("veículo deixou de ser válido: %r" % (error,))
            self._vehicle = None
            self._stop_engine_sound()

    def dispose(self):
        self._stop_engine_sound()

    def _start_engine_sound(self):
        path = str(self._args.get("Engine Sound", "")).strip()
        if not path:
            return
        try:
            import aud
            full_path = Range.logic.expandPath(path)
            if not os.path.isfile(full_path):
                self._error("Engine Sound não encontrado: %s" % full_path)
                return
            self._engine_sound_device = aud.Device()
            self._engine_sound_handle = self._engine_sound_device.play(aud.Sound.file(full_path).loop(-1))
        except Exception as error:
            self._error("não foi possível tocar Engine Sound: %r" % (error,))
            self._engine_sound_handle = None

    def _update_engine_sound(self, throttle):
        if self._engine_sound_handle is None:
            return
        # Tom acompanha o RPM entre marcha lenta e o máximo; acelerar deixa
        # o motor mais alto que em ponto morto.
        idle_rpm = float(self._args.get("Idle RPM", 0.0))
        span = max(self._max_rpm() - idle_rpm, 1.0)
        rpm_fraction = min(max((self._current_engine_rpm() - idle_rpm) / span, 0.0), 1.25)
        idle_pitch = float(self._args.get("Idle Pitch", 0.6))
        max_pitch = float(self._args.get("Max RPM Pitch", 2.0))
        self._engine_sound_handle.pitch = idle_pitch + (max_pitch - idle_pitch) * rpm_fraction
        load = 1.0 if throttle != 0.0 else 0.6
        self._engine_sound_handle.volume = float(self._args.get("Engine Volume", 0.8)) * load

    def _stop_engine_sound(self):
        handle = getattr(self, "_engine_sound_handle", None)
        if handle is not None:
            try:
                handle.stop()
            except Exception:
                pass
        self._engine_sound_handle = None
        self._engine_sound_device = None

    def _read_input(self):
        throttle = self._gas_input() - self._back_input()
        steering = float(self._held(self._steer_left_key)) - float(self._held(self._steer_right_key))
        steering = min(max(steering - self._joy["steer"], -1.0), 1.0)
        brake_held = self._held(self._brake_key) or self._joy["brake"]
        # Na moto a tecla de empinar tem prioridade se for a mesma do freio de mão.
        handbrake_key_held = self._held(self._handbrake_key) and not (
            self._is_motorcycle() and self._handbrake_key == self._wheelie_key)
        handbrake_held = handbrake_key_held or self._joy["handbrake"]
        brake = float(self._args["Brake Force"]) if brake_held else 0.0
        handbrake = float(self._args["Handbrake Force"]) if handbrake_held else 0.0
        return throttle, steering, brake, handbrake

    def _compute_engine_force(self, throttle):
        engine_sign = self._engine_sign()
        max_torque = self.object.getVehicleMaxTorque()
        if max_torque <= 0.0:
            # game.vehicle_max_torque não configurado (0): comportamento legado,
            # força fixa por marcha de aceleração/ré.
            if throttle >= 0.0:
                return engine_sign * float(self._args["Engine Force"]) * throttle
            return engine_sign * float(self._args["Reverse Force"]) * throttle

        torque = max_torque * self._torque_factor_at_current_rpm()
        if self._gear_ratios:
            if self._neutral:
                return 0.0
            if throttle == 0.0:
                return self._engine_brake_force(engine_sign)
            if self._rev_limiter_active():
                return 0.0
            gear_ratio = self._gear_ratios[self._current_gear_index] * self._final_drive()
            # Direção vem do sinal da marcha selecionada (positiva = à frente,
            # negativa = ré), não do throttle: assim a troca de marcha (auto
            # ou manual) é a única responsável por decidir o sentido.
            return engine_sign * torque * gear_ratio / self._wheel_radius() * abs(throttle)
        return engine_sign * torque / self._wheel_radius() * throttle

    def _engine_sign(self):
        # Modelo com a frente virada para o outro lado: inverte a força.
        # "Engine Sign" negativo é o nome antigo desta opção.
        if bool(self._args.get("Invert Direction", False)):
            return -1.0
        return -1.0 if float(self._args.get("Engine Sign", 1.0)) < 0.0 else 1.0

    def _resolve_pedals(self, raw_throttle):
        # Com marchas, a direção vem só da marcha: W acelera no sentido da
        # marcha e S freia. No automático, engatado em ré os papéis trocam
        # (S acelera para trás, W freia). Sem marchas mantém o legado.
        if not self._gear_ratios or self.object.getVehicleMaxTorque() <= 0.0:
            return raw_throttle, 0.0
        gas = self._gas_input()
        back = self._back_input()
        in_reverse = (not self._neutral
                      and self._gear_ratios[self._current_gear_index] < 0.0)
        if self._gearbox_type != self.GEARBOX_MANUAL and in_reverse:
            gas, back = back, gas
        return gas, float(self._args["Brake Force"]) * back

    def _apply_balance(self, steering):
        # Duas rodas em linha não param em pé na física: no modo Motorcycle um
        # torque em volta do eixo à frente segura a moto (papel do piloto e do
        # efeito giroscópico) e a inclina para dentro da curva conforme a
        # velocidade. Controle PD: força = rigidez x erro - amortecimento x giro.
        if not self._is_motorcycle():
            return
        right_index, up_index, forward_index = self._vehicle.getCoordinateSystem()
        orientation = self.object.worldOrientation
        right = orientation.col[right_index]
        up = orientation.col[up_index]
        forward = orientation.col[forward_index]
        # Inclinação: > 0 quando tomba para a esquerda (o eixo direito sobe).
        roll = math.atan2(right.z, up.z)
        speed_factor = min(abs(self._vehicle.getCurrentSpeedKmh()) / 30.0, 1.0)
        lean = math.radians(float(self._args.get("Max Lean (deg)", 35.0)))
        # Mesmo sentido da curva (validado no jogo): negativo nesta convenção.
        target = steering * float(self._args.get("Steering Sign", 1.0)) * lean * speed_factor
        # Girar em volta de +forward baixa o lado direito se right x forward =
        # up; num sistema de eixos canhoto o sentido inverte.
        handed = 1.0 if right.cross(forward).dot(up) >= 0.0 else -1.0
        roll_rate = -handed * self.object.getAngularVelocity(False).dot(forward)
        control = (float(self._args.get("Balance Strength", 60.0)) * (target - roll)
                   - float(self._args.get("Balance Damping", 12.0)) * roll_rate)
        # Escala pela massa para a mesma regulagem servir a motos leves e pesadas.
        torque = forward * (-handed * control * self.object.mass * 0.25)

        # Empinar é livre até Max Wheelie; passando disso uma mola forte segura
        # a frente para a moto não virar de costas. Nariz para cima = pitch > 0.
        pitch = math.atan2(forward.z, up.z)
        max_pitch = math.radians(float(self._args.get("Max Wheelie (deg)", 45.0)))
        # Segurando Wheelie Key / botão A em movimento, um torque levanta a frente
        # (a força do motor sozinha quase não empina um veículo de raycast).
        wheelie_held = self._held(self._wheelie_key) or self._joy["wheelie"]
        min_speed = float(self._args.get("Wheelie Min Speed", 5.0))
        if wheelie_held and abs(self._vehicle.getCurrentSpeedKmh()) >= min_speed and pitch < max_pitch:
            lift = float(self._args.get("Wheelie Force", 30.0))
            torque += right * (handed * lift * self.object.mass * 0.25)
        if pitch > max_pitch:
            pitch_rate = handed * self.object.getAngularVelocity(False).dot(right)
            pitch_control = (float(self._args.get("Balance Strength", 60.0)) * 2.0 * (pitch - max_pitch)
                             + float(self._args.get("Balance Damping", 12.0)) * max(pitch_rate, 0.0))
            torque -= right * (handed * pitch_control * self.object.mass * 0.25)
        self.object.applyTorque(torque, False)

    def _ramp_pedal(self, target):
        # Teclado é tudo ou nada: o pedal leva "Throttle Time" segundos para ir
        # de 0 ao fundo (e solta na metade do tempo), imitando um pedal real.
        ramp_time = float(self._args.get("Throttle Time (s)", 0.4))
        if self._joy["analog"]:
            # Gatilho analógico já é um pedal de verdade: sem rampa.
            ramp_time = 0.0
        if ramp_time <= 0.0 or (target != 0.0 and self._pedal * target < 0.0):
            self._pedal = target
            return target
        dt = min(max(time.perf_counter() - self._last_time, 0.0), 0.1)
        rate = dt / ramp_time
        if abs(target) < abs(self._pedal):
            rate *= 2.0
        delta = target - self._pedal
        self._pedal += math.copysign(min(abs(delta), rate), delta) if delta else 0.0
        return self._pedal

    def _max_rpm(self):
        max_rpm = self.object.getVehicleMaxRPM()
        return max_rpm if max_rpm > 0.0 else self.FALLBACK_MAX_RPM

    def _final_drive(self):
        final_drive = float(self._args.get("Final Drive", 1.0))
        return final_drive if final_drive > 0.0 else 1.0

    def _rev_limiter_active(self):
        # Corte de giro: no RPM máximo a marcha para de empurrar, então cada
        # marcha tem velocidade máxima própria (é preciso trocar para passar).
        return bool(self._args.get("Rev Limiter", True)) and self._current_engine_rpm() >= self._max_rpm()

    def _torque_factor_at_current_rpm(self):
        rpm_fraction = min(self._current_engine_rpm() / self._max_rpm(), 1.0)
        return 1.0 - rpm_fraction * (1.0 - self.MIN_TORQUE_FACTOR_AT_MAX_RPM)

    def _engine_brake_force(self, engine_sign):
        # Freio motor: sem acelerador, o motor engatado segura o carro com força
        # proporcional ao giro e à relação (reduzir marcha segura mais).
        if abs(self._vehicle.getCurrentSpeedKmh()) < self.ENGINE_BRAKE_MIN_SPEED_KMH:
            return 0.0
        gear_ratio = self._gear_ratios[self._current_gear_index] * self._final_drive()
        rpm_fraction = self._engine_rpm / self._max_rpm()
        brake = float(self._args.get("Engine Brake", 0.0)) * rpm_fraction * abs(gear_ratio)
        return -engine_sign * math.copysign(brake / self._wheel_radius(), gear_ratio)

    def _coupled_engine_rpm(self):
        # Giro imposto pelas rodas através da marcha engatada.
        if self._neutral:
            return 0.0
        wheel_rpm = self._simulated_rpm()
        if self._gear_ratios:
            wheel_rpm *= abs(self._gear_ratios[self._current_gear_index]) * self._final_drive()
        return wheel_rpm

    def _update_engine_rpm(self, throttle):
        now = time.perf_counter()
        dt = min(max(now - self._last_time, 0.0), 0.1)
        self._last_time = now

        target = self._coupled_engine_rpm()
        if self._neutral:
            # Ponto morto: motor solto, o acelerador sobe o giro até o corte.
            target = self._max_rpm() * abs(throttle)
        elif throttle != 0.0:
            # Embreagem patinando na saída: acelerando parado o motor sobe até
            # Launch RPM mesmo com as rodas quase paradas.
            target = max(target, float(self._args.get("Launch RPM", 0.0)) * abs(throttle))
        # Marcha lenta embaixo; em cima deixa passar um pouco do máximo para a
        # redução forçada soar esticada (o corte de giro segura o resto).
        target = min(max(target, float(self._args.get("Idle RPM", 0.0))), self._max_rpm() * 1.25)
        # Inércia do volante: maior = giro sobe e desce mais devagar. Solto
        # (neutro) o motor sobe mais lento que engatado e cai ainda mais lento.
        response = self.RPM_RESPONSE / max(float(self._args.get("Engine Inertia", 1.0)), 0.05)
        if self._neutral:
            response *= 0.35 if target > self._engine_rpm else 0.2
        self._engine_rpm += (target - self._engine_rpm) * min(dt * response, 1.0)

    def _current_engine_rpm(self):
        return self._engine_rpm

    def _wheel_radius(self):
        # Raio da primeira roda motriz; 0.3m se não houver config (não deveria
        # acontecer, start() já validou), o padrão do sistema de veículo.
        if self._drive_wheels:
            config = self._vehicle.getWheelConfig(self._drive_wheels[0])
            if config.get("wheelRadius", 0.0) > 0.0:
                return config["wheelRadius"]
        return 0.3

    def _simulated_rpm(self):
        # RPM da roda (sem marcha); _coupled_engine_rpm aplica a relação.
        speed_m_s = abs(self._vehicle.getCurrentSpeedKmh()) / 3.6
        wheel_angular_speed = speed_m_s / self._wheel_radius()  # rad/s
        return wheel_angular_speed * 60.0 / (2.0 * math.pi)

    def _refresh_gearbox(self):
        # Relê as marchas a cada frame: o Vehicle Lab e o preset .json podem
        # mudá-las com o jogo rodando.
        ratios = self._read_gear_ratios()
        if ratios != self._gear_ratios:
            self._gear_ratios = ratios
            if not ratios:
                self._current_gear_index = 0
            elif self._current_gear_index >= len(ratios):
                self._current_gear_index = self._first_forward_gear_index() or 0
        self._gearbox_type = self.object.getVehicleGearboxType()
        if self._gearbox_type != self.GEARBOX_MANUAL or not ratios:
            self._neutral = False

    def _read_gear_ratios(self):
        # Sem relação negativa cadastrada, cria uma ré com a relação da 1ª
        # (em carros reais a ré é próxima da 1ª), para o R sempre existir.
        ratios = list(self.object.getVehicleGearRatios())
        forward = [r for r in ratios if r > 0.0]
        if forward and not any(r < 0.0 for r in ratios):
            ratios.insert(0, -forward[0])
        return ratios

    def _first_forward_gear_index(self):
        for i, ratio in enumerate(self._gear_ratios):
            if ratio > 0.0:
                return i
        return None

    def _reverse_gear_index(self):
        for i, ratio in enumerate(self._gear_ratios):
            if ratio < 0.0:
                return i
        return None

    def _update_gear_selection(self, throttle):
        if not self._gear_ratios:
            return
        if self._gearbox_type == self.GEARBOX_MANUAL:
            self._read_manual_shift_input()
        else:
            self._auto_select_gear(throttle)

    def _manual_positions(self):
        # Sequência da alavanca: ré (-1), ponto morto (0), marchas à frente.
        # Cada item é o índice em _gear_ratios, ou None para o ponto morto.
        positions = [i for i, r in enumerate(self._gear_ratios) if r < 0.0][:1]
        positions.append(None)
        positions += [i for i, r in enumerate(self._gear_ratios) if r > 0.0]
        return positions

    def _read_manual_shift_input(self):
        up_held = self._held(self._shift_up_key) or self._joy["up"]
        down_held = self._held(self._shift_down_key) or self._joy["down"]
        step = 0
        if up_held and not self._prev_shift_up_held:
            step += 1
        if down_held and not self._prev_shift_down_held:
            step -= 1
        self._prev_shift_up_held = up_held
        self._prev_shift_down_held = down_held
        if step == 0:
            return
        positions = self._manual_positions()
        current = None if self._neutral else self._current_gear_index
        pos = positions.index(current) if current in positions else positions.index(None)
        pos = min(max(pos + step, 0), len(positions) - 1)
        if positions[pos] is None:
            self._neutral = True
        else:
            self._neutral = False
            self._current_gear_index = positions[pos]

    def _auto_select_gear(self, throttle):
        reverse_index = self._reverse_gear_index()
        forward_index = self._first_forward_gear_index()
        speed_kmh = abs(self._vehicle.getCurrentSpeedKmh())
        if speed_kmh < self.REVERSE_ENGAGE_SPEED_KMH:
            if throttle < 0.0 and reverse_index is not None:
                self._current_gear_index = reverse_index
            elif throttle > 0.0 and forward_index is not None:
                self._current_gear_index = forward_index

        if reverse_index is not None and self._current_gear_index == reverse_index:
            return
        if forward_index is None:
            return

        engine_rpm = self._current_engine_rpm()
        upshift_rpm = float(self._args["Upshift RPM"])
        downshift_rpm = float(self._args["Downshift RPM"])
        next_index = self._current_gear_index + 1
        prev_index = self._current_gear_index - 1
        if (engine_rpm > upshift_rpm and next_index < len(self._gear_ratios)
                and self._gear_ratios[next_index] > 0.0):
            self._current_gear_index = next_index
        elif (engine_rpm < downshift_rpm and prev_index >= forward_index
                and self._gear_ratios[prev_index] > 0.0):
            self._current_gear_index = prev_index

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

    def _key_arg(self, arg_name, default):
        key_name = str(self._args.get(arg_name, default)).strip().upper()
        key = getattr(Range.events, key_name, None)
        if key is None:
            self._error("tecla '%s' inválida em '%s'; usando %s" % (key_name, arg_name, default))
            key = getattr(Range.events, default)
        return key

    def _current_gear_label(self):
        if not self._gear_ratios:
            return "-"
        if self._neutral:
            return "N"
        ratio = self._gear_ratios[self._current_gear_index]
        if ratio < 0.0:
            return "R"
        # Numera só as marchas à frente (a ré não conta).
        forward_before = sum(1 for r in self._gear_ratios[:self._current_gear_index] if r > 0.0)
        return str(forward_before + 1)

    def _publish_telemetry(self):
        if not self._gear_ratios:
            self.object["vehicle_gearbox"] = "sem marchas"
        elif self._gearbox_type == self.GEARBOX_MANUAL:
            self.object["vehicle_gearbox"] = "Manual (%s/%s)" % (
                str(self._args["Shift Up Key"]), str(self._args["Shift Down Key"]))
        else:
            self.object["vehicle_gearbox"] = "Automatico"
        self.object["vehicle_gear"] = self._current_gear_label()
        self.object["vehicle_rpm"] = int(self._current_engine_rpm())
        self.object["vehicle_speed_kmh"] = round(abs(self._vehicle.getCurrentSpeedKmh()), 1)

    def _gas_input(self):
        return max(float(self._held(self._throttle_key)), self._joy["gas"])

    def _is_motorcycle(self):
        return bool(self._args.get("Motorcycle", False))

    def _back_input(self):
        return max(float(self._held(self._reverse_key)), self._joy["back"])

    @staticmethod
    def _empty_joy():
        return {"steer": 0.0, "gas": 0.0, "back": 0.0, "analog": False,
                "brake": False, "handbrake": False, "up": False, "down": False,
                "wheelie": False}

    def _poll_joystick(self):
        joy = self._empty_joy()
        self._joy = joy
        if not bool(self._args.get("Use Joystick", True)):
            return
        index = int(self._args.get("Joystick Index", 0))
        joysticks = Range.logic.joysticks
        if index < 0 or index >= len(joysticks) or joysticks[index] is None:
            return
        pad = joysticks[index]
        axes = pad.axisValues
        buttons = pad.activeButtons
        deadzone = min(max(float(self._args.get("Joystick Deadzone", 0.15)), 0.0), 0.95)

        def axis(i, signed):
            if i >= len(axes):
                return 0.0
            value = float(axes[i])
            if not signed:
                value = max(value, 0.0)
            if abs(value) < deadzone:
                return 0.0
            # Reescala para o curso útil começar em 0 logo após a zona morta.
            return math.copysign((abs(value) - deadzone) / (1.0 - deadzone), value)

        joy["steer"] = axis(self.JOY_AXIS_STEER, True)
        joy["gas"] = axis(self.JOY_AXIS_GAS, False)
        joy["back"] = axis(self.JOY_AXIS_BACK, False)
        joy["analog"] = joy["gas"] > 0.0 or joy["back"] > 0.0
        joy["brake"] = self.JOY_BUTTON_BRAKE in buttons
        joy["wheelie"] = self.JOY_BUTTON_WHEELIE in buttons
        joy["handbrake"] = self.JOY_BUTTON_HANDBRAKE in buttons
        joy["down"] = self.JOY_BUTTON_SHIFT_DOWN in buttons
        joy["up"] = self.JOY_BUTTON_SHIFT_UP in buttons

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
            self.report({'ERROR'}, tip_("Save the .blend file before adding the component."))
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
            self.report({'ERROR'}, tip_("Could not create component file: %s") % exc)
            return {'CANCELLED'}

        ob = context.active_object
        full_name = "{}.{}".format(VEHICLE_COMPONENT_MODULE, VEHICLE_COMPONENT_CLASS)
        already_added = any("{}.{}".format(comp.module, comp.name) == full_name
                             for comp in ob.game.components)
        if already_added:
            self.report({'INFO'}, tip_("Vehicle component already added to this object."))
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
                self.report({'ERROR'}, tip_("Could not add component: %s") % exc)
                return {'CANCELLED'}

        self.report({'INFO'}, tip_("Vehicle component added."))
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

    def draw(self, context):
        layout = self.layout
        game = context.active_object.game

        layout.prop(game, "use_collision_bounds", text="Enabled")

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


class VehicleButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "vehicle"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        rd = context.scene.render
        return ob and ob.game and (rd.engine in cls.COMPAT_ENGINES)


class VehicleSubPanel(VehicleButtonsPanel):
    """Vehicle settings panels: only for objects that can be a vehicle, greyed out until
    the "Enabled" checkbox of the Vehicle panel is on."""

    @classmethod
    def poll(cls, context):
        return VehicleButtonsPanel.poll.__func__(cls, context) and             context.active_object.game.physics_type in {'RIGID_BODY', 'DYNAMIC'}

    def draw(self, context):
        ob = context.active_object
        self.layout.active = ob.game.is_vehicle
        self.draw_content(self.layout, ob)


class PHYSICS_PT_game_vehicle(VehicleButtonsPanel, Panel):
    bl_label = "Vehicle"

    def draw(self, context):
        layout = self.layout

        ob = context.active_object
        game = ob.game

        if game.physics_type not in {'RIGID_BODY', 'DYNAMIC'}:
            layout.label(text="Only Rigid Body/Dynamic objects can be a Vehicle.", icon='INFO')
            return

        layout.prop(game, "is_vehicle", text="Enabled")
        layout = layout.column()
        layout.active = game.is_vehicle

        box = layout.box()
        box.label(text="Chassis:", icon='AUTO')
        box.prop(ob, "vehicle_steering_wheel", text="Steering Wheel")
        box.row(align=True).prop(ob, "vehicle_com_offset", text="Center of Mass Offset")


class PHYSICS_PT_game_vehicle_engine(VehicleSubPanel, Panel):
    bl_label = "Engine"

    def draw_content(self, layout, ob):
        box = layout.box()
        box.label(text="Drive Type:", icon='DRIVER')
        row = box.row(align=True)
        row.operator("object.vehicle_set_drive_type", text="FWD").drive_type = 'FWD'
        row.operator("object.vehicle_set_drive_type", text="RWD").drive_type = 'RWD'
        row.operator("object.vehicle_set_drive_type", text="AWD").drive_type = 'AWD'

        box = layout.box()
        box.label(text="Power:", icon='SETTINGS')
        row = box.row(align=True)
        row.prop(ob, "vehicle_max_torque", text="Max Torque")
        row.prop(ob, "vehicle_max_rpm", text="Max RPM")


class PHYSICS_PT_game_vehicle_wheels(VehicleSubPanel, Panel):
    bl_label = "Wheels"

    def draw_content(self, layout, ob):
        for i, wheel in enumerate(ob.vehicle_wheels):
            box = layout.box()
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

        layout.operator("object.vehicle_wheel_add", text="Add Wheel", icon='ZOOMIN')


class PHYSICS_PT_game_vehicle_gearbox(VehicleSubPanel, Panel):
    bl_label = "Gearbox"

    def draw_content(self, layout, ob):
        layout.prop(ob, "gearbox_type", text="Type")

        if len(ob.vehicle_gears):
            box = layout.box()
            box.label(text="Gears:", icon='LINENUMBERS_ON')
            col = box.column(align=True)
            for i, gear in enumerate(ob.vehicle_gears):
                row = col.row(align=True)
                label = "Reverse" if gear.ratio < 0.0 else "Gear %d" % (i + 1)
                row.prop(gear, "ratio", text=label)
                row.operator("object.vehicle_gear_remove", text="", icon='PANEL_CLOSE').index = i

        layout.operator("object.vehicle_gear_add", text="Add Gear", icon='ZOOMIN')


class PHYSICS_PT_game_vehicle_component(VehicleSubPanel, Panel):
    bl_label = "Player Component"

    def draw_content(self, layout, ob):
        layout.operator("object.vehicle_add_player_component", text="Add Vehicle Component", icon='PLUGIN')
