"""Etapa 4 da PoC (docs/web-python-poc-plan.md): padrao de frame do BGE —
engine chama script (update), script chama API da engine (set_position)."""

import stage4_engine

_position_x = 0.0


def update(dt, input_left, input_right):
    global _position_x

    speed = 10.0
    if input_left:
        _position_x -= speed * dt
    if input_right:
        _position_x += speed * dt

    stage4_engine.set_position(_position_x)
