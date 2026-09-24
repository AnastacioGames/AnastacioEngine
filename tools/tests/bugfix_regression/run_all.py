"""
Roda todos os testes automatizados de regressao dos bugs corrigidos em
2026-09-03. Uso:

    RangeEngine.exe --background --python tools/tests/bugfix_regression/run_all.py

GPU-001 e pulado automaticamente em --background (precisa de contexto
OpenGL real); rode sem --background para incluir esse caso tambem.
"""
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = [
    "test_anim_keyingset_array_index.py",
    "test_regression_smoke.py",
    "test_rnd001_voxeldata_bvox.py",
]

for name in SCRIPTS:
    print("\n==== %s ====" % name)
    runpy.run_path(os.path.join(HERE, name), run_name="__main__")
