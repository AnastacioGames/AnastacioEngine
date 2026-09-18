"""Integracao do operador Validar Web e do Localizar (precisa do motor):

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/engine_web_ui.py

Sai com codigo != 0 se alguma verificacao falhar.
"""

import sys

import bpy

from bl_ui import properties_web as pw

failures = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


check(hasattr(bpy.types, "SCENE_OT_range_web_validate"), "operador Validar registrado")
check(pw._last_report is None, "sem resultado antes de validar")

ob = bpy.data.objects.new("Porta", None)
bpy.context.scene.objects.link(ob)
bpy.context.scene.objects.active = ob
bpy.ops.logic.controller_add(type='PYTHON', name="Abrir", object="Porta")
c = ob.game.controllers["Abrir"]
c.mode = 'MODULE'
c.module = "nao_existe.f"

check(bpy.ops.scene.range_web_validate() == {'FINISHED'}, "Validar termina")
report = pw._last_report
check(report is not None and any(f.rule_id == "WEB-PKG-003" for f in report.errors),
      "modulo ausente vira erro")
check(not any("Range" in f.message for f in report.findings), "modulo Range do motor nao e ausente")

idx = next(i for i, f in enumerate(report.findings) if f.location.get("object") == "Porta")
for o in bpy.context.scene.objects:
    o.select = False
check(bpy.ops.scene.range_web_locate(index=idx) == {'FINISHED'}, "Localizar termina")
check(ob.select and bpy.context.scene.objects.active == ob, "Localizar seleciona o objeto de origem")
check(bpy.ops.scene.range_web_locate(index=999) == {'CANCELLED'}, "indice invalido cancela")

print("FALHAS: %d" % len(failures))
sys.exit(1 if failures else 0)
