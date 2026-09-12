"""Gera um exemplo mínimo de Cutscene nativa e salva um arquivo .blend.

Uso:
    RangeEngine.exe --background --factory-startup --python cutscene_native_example.py -- exemplo.blend
"""

import os
import sys

import bpy


def check(condition, message):
    if not condition:
        raise RuntimeError("[cutscene_native_example] FAIL: " + message)


def add_empty(scene, name, location):
    obj = bpy.data.objects.new(name, None)
    scene.objects.link(obj)
    obj.location = location
    return obj


def output_path():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) != 1:
        raise RuntimeError("uso: -- caminho_do_exemplo.blend")
    return os.path.abspath(args[0])


def main():
    path = output_path()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Cutscene Native Example"
    scene.frame_start = 1
    scene.frame_end = 120

    template = add_empty(scene, "Hero Template", (0.0, 0.0, 0.0))
    spawn_point = add_empty(scene, "Hero Spawn Point", (2.0, 0.0, 0.0))

    bpy.ops.cutscene.sequence_add()
    sequence = scene.cutscene_settings.sequences[0]
    sequence.name = "Opening"
    bpy.ops.cutscene.event_add(sequence_index=0)
    event = sequence.events[0]
    event.name = "Spawn Hero"
    event.time = 1.0
    event.template_object = template
    event.spawn_point = spawn_point

    check(len(scene.cutscene_settings.sequences) == 1, "sequência não criada")
    check(len(sequence.events) == 1, "evento não criado")
    check(event.template_object == template, "Template Object não configurado")
    check(event.spawn_point == spawn_point, "Spawn Point não configurado")

    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print("[cutscene_native_example] PASS: " + path, flush=True)


if __name__ == "__main__":
    main()
