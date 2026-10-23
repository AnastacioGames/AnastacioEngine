# -*- coding: utf-8 -*-
"""Controle arcade nativo. Anexe em lugar de VehiclePlayerComponent.

Requer vehicle_player_component.py na mesma pasta/textos do projeto.
Primeira extração do RolimaRacer: direção por velocidade (km/h).
Motor, freios e montagem continuam no controlador nativo; não cria veículo.
"""
from collections import OrderedDict
import math
from Range.args import Float
from vehicle_player_component import VehiclePlayerComponent


class AnastacioVehicleArcade(VehiclePlayerComponent):
    args = OrderedDict(VehiclePlayerComponent.args)
    args.update([
        ('C_Header /Arcade/AUTO', True),
        ('Arcade Steering Reduction', Float(0.7, min=0, max=1,
            tip='Redução máxima da direção; usa a curva do RolimaRacer entre 20 e 120 km/h.')),
    ])

    def start(self, args):
        self._arcade_signature = None
        self._commands = None
        super().start(args)
        if self._vehicle is not None:
            self._refresh_arcade_curves()

    def _refresh_arcade_curves(self):
        signature = min(1.0, max(0.0, float(self._args['Arcade Steering Reduction'])))
        if signature == self._arcade_signature:
            return
        reduction = signature
        factors = [min(1.0, max(0.0, (speed - 20.0) / 100.0))
                   for speed in range(250)]
        self._arcade_steer_lut = [1.0 - factor * reduction for factor in factors]
        self._arcade_signature = signature

    def update_args(self, args):
        super().update_args(args)
        if self._vehicle is not None:
            self._refresh_arcade_curves()

    def _arcade_speed_index(self):
        return min(249, int(abs(self._vehicle.getCurrentSpeedKmh())))

    def _speed_steering_factor(self):
        return self._arcade_steer_lut[self._arcade_speed_index()]

    def set_commands(self, throttle=0.0, steering=0.0, brake=0.0, handbrake=False):
        """Comandos normalizados para IA/input por jogador; throttle negativo = ré.

        Persistem até a próxima chamada. clear_commands devolve ao teclado/gamepad.
        Sinal da direção segue o básico: +1 esquerda, -1 direita.
        Freio 0..1 multiplica Brake Force; freio de mão usa Handbrake Force.
        """
        values = [float(throttle), float(steering), float(brake)]
        if not all(math.isfinite(value) for value in values):
            raise ValueError('Comandos devem ser finitos.')
        self._commands = (max(-1.0, min(1.0, values[0])),
                          max(-1.0, min(1.0, values[1])),
                          max(0.0, min(1.0, values[2])), bool(handbrake))

    def clear_commands(self):
        self._commands = None

    def _read_input(self):
        if self._commands is None:
            return super()._read_input()
        throttle, steering, brake, handbrake = self._commands
        return (throttle, steering, brake * float(self._args['Brake Force']),
                float(self._args['Handbrake Force']) if handbrake else 0.0)

    def _gas_input(self):
        if self._commands is not None:
            return max(0.0, self._commands[0])
        return super()._gas_input()

    def _back_input(self):
        if self._commands is not None:
            return max(0.0, -self._commands[0])
        return super()._back_input()

    class Editor(VehiclePlayerComponent.Editor):
        def warnings(self, obj, comp):
            for warning in super().warnings(obj, comp):
                yield warning
            for other in obj.game.components:
                if other.as_pointer() != comp.as_pointer() and other.name == 'AnastacioVehicleArcade':
                    yield 'Use apenas um controlador arcade por chassi.'
