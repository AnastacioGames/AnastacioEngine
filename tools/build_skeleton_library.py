"""Gera a biblioteca de esqueletos (release/datafiles/characters) a partir dos FBX do Mixamo do Enzo.

    build/bin/AnastacioEngine.exe -b --factory-startup --python tools/build_skeleton_library.py -- <pasta dos FBX>

Cada base guarda só a armature e uma malha de pesos simplificada (sem textura, sem olhos), não o personagem.
"""
import os
import sys

import bpy

import range_character_autorig as ar

SRC = sys.argv[sys.argv.index("--") + 1]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "source", "release", "datafiles", "characters")

BASES = (
    ("mixamo_two_fingers", "Two Fingers (thumb + index)", 1, "Enzo_dois_dedos.fbx"),
    ("mixamo_no_fingers", "No Fingers", 2, "Enzo_sem_dedos.fbx"),
    ("mixamo_three_fingers", "Three Fingers", 3, "Enzo_3_dedos.fbx"),
    ("mixamo_full_fingers", "Full Fingers", 4, "Enzo_todos_dedos.fbx"),
)

for sid, name, order, fbx in BASES:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    info = ar.make_library_base(os.path.join(SRC, fbx), os.path.join(OUT, sid), name, order)
    print("LIB", sid, info)
