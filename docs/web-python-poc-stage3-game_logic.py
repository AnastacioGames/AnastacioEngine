"""Etapa 3 da PoC (docs/web-python-poc-plan.md): modulo externo real,
carregado via FS virtual (--preload-file), nao embutido no binario."""

import json
import math


def compute_distance(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    dx = config["point_a"]["x"] - config["point_b"]["x"]
    dy = config["point_a"]["y"] - config["point_b"]["y"]
    return math.sqrt(dx * dx + dy * dy)


def trigger_controlled_exception():
    raise ValueError("stage3: excecao controlada para validar traceback")
