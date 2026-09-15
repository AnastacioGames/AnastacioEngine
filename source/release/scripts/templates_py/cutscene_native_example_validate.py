"""Valida a estrutura nativa de um exemplo .blend de Cutscene.

Uso:
    RangeEngine.exe --background exemplo.blend --python cutscene_native_example_validate.py
"""

import bpy


def check(condition, message):
    if not condition:
        raise RuntimeError("[cutscene_native_example_validate] FAIL: " + message)


def main():
    scene = bpy.context.scene
    settings = scene.cutscene_settings
    check(len(settings.sequences) == 1, "o exemplo deve ter uma sequência")
    sequence = settings.sequences[0]
    check(sequence.name == "Opening", "nome da sequência inesperado")
    check(len(sequence.events) == 1, "o exemplo deve ter um evento")
    event = sequence.events[0]
    check(event.name == "Spawn Hero", "nome do evento inesperado")
    check(event.type == "SPAWN_OBJECT", "ação não é Spawn Object")
    check(abs(event.time - 1.0) < 0.0001, "tempo do evento inesperado")
    check(event.template_object is not None, "Template Object ausente")
    check(event.template_object.name == "Hero Template", "Template Object incorreto")
    check(event.spawn_point is not None, "Spawn Point ausente")
    check(event.spawn_point.name == "Hero Spawn Point", "Spawn Point incorreto")
    check(event.dependent_object is None, "Dependent Object deveria ser opcional")
    print("[cutscene_native_example_validate] PASS", flush=True)


if __name__ == "__main__":
    main()
