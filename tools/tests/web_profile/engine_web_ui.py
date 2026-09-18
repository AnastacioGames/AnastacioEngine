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

import os
import shutil
import tempfile

# Runtime falso com manifesto proprio: os modulos passam a vir dele, nao do fallback.
import json, hashlib
tmp = tempfile.mkdtemp()
with open(os.path.join(tmp, "RangeRuntime.wasm"), "wb") as f:
    f.write(b"wasm")
manifest = {"schema": "range-web-runtime", "schema_version": 1, "runtime_id": "web-runtime-release",
            "engine_revision": "t", "python": {"version": "3.11", "modules": ["math", "Range"]},
            "artifacts": {"RangeRuntime.wasm": {"bytes": 4, "sha256": hashlib.sha256(b"wasm").hexdigest()}},
            "capabilities": {}}
with open(os.path.join(tmp, "RangeRuntime.manifest.json"), "w") as f:
    json.dump(manifest, f)
os.environ["RANGE_WEB_RUNTIME_DIR"] = tmp
c.module = "os.f"  # 'os' existe no fallback, mas nao no manifesto
bpy.ops.scene.range_web_validate()
check(not any(f.rule_id == "WEB-PKG-001" for f in pw._last_report.findings), "runtime valido: sem PKG-001")
check(any(f.rule_id == "WEB-PKG-003" and "os" in f.message for f in pw._last_report.errors),
      "modulos vem do manifesto (os ausente do runtime)")
open(os.path.join(tmp, "RangeRuntime.wasm"), "wb").write(b"xxxx")
bpy.ops.scene.range_web_validate()
check(any(f.rule_id == "WEB-PKG-001" for f in pw._last_report.errors), "artefato divergente vira PKG-001")
os.environ.pop("RANGE_WEB_RUNTIME_DIR")
shutil.rmtree(tmp)
c.module = "nao_existe.f"
bpy.ops.scene.range_web_validate()
report = pw._last_report

idx = next(i for i, f in enumerate(report.findings) if f.location.get("object") == "Porta")
for o in bpy.context.scene.objects:
    o.select = False
check(bpy.ops.scene.range_web_locate(index=idx) == {'FINISHED'}, "Localizar termina")
check(ob.select and bpy.context.scene.objects.active == ob, "Localizar seleciona o objeto de origem")
check(bpy.ops.scene.range_web_locate(index=999) == {'CANCELLED'}, "indice invalido cancela")

print("FALHAS: %d" % len(failures))
sys.exit(1 if failures else 0)
