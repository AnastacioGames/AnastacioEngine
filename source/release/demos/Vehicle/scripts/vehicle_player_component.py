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
