"""Gera o projeto de teste manual do perfil Web em build/web-manual/ (ver docs/web-profile-manual-tests.md):

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/make_manual_project.py

Cria bom.blend (deve exportar) e ruim.blend (deve ser bloqueado com WEB-PKG-003).
"""

import os

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEST = os.path.join(ROOT, "build", "web-manual")
os.makedirs(os.path.join(DEST, "pkg"), exist_ok=True)


def write(rel, text):
    with open(os.path.join(DEST, rel), "w", encoding="utf-8") as f:
        f.write(text)


write("meu_mod.py", "import pkg.util\n\n\ndef main(cont):\n    cont.owner.worldPosition.z += pkg.util.PASSO\n")
write("pkg/__init__.py", "")
write("pkg/util.py", "PASSO = 0.01\n")


def scene_with_controller(module):
    bpy.ops.wm.read_factory_settings()
    ob = bpy.data.objects.new("Porta", None)
    bpy.context.scene.objects.link(ob)
    bpy.context.scene.objects.active = ob
    bpy.ops.logic.controller_add(type='PYTHON', name="Abrir", object="Porta")
    c = ob.game.controllers["Abrir"]
    c.mode = 'MODULE'
    c.module = module


# Submodulo proibido alcancado so por `from pkg import ...` (teste C)
write("sub_mod.py", "from sub_pkg import perigo\n\n\ndef main(cont):\n    perigo.roda()\n")
os.makedirs(os.path.join(DEST, "sub_pkg"), exist_ok=True)
write("sub_pkg/__init__.py", "")
write("sub_pkg/perigo.py", "import subprocess\n\nsubprocess.run(['ls'])\n\n\ndef roda():\n    pass\n")

scene_with_controller("sub_mod.main")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DEST, "sub.blend"))
scene_with_controller("meu_mod.main")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DEST, "bom.blend"))
scene_with_controller("nao_existe_xyz.main")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DEST, "ruim.blend"))
print("Projeto de teste em", DEST)
