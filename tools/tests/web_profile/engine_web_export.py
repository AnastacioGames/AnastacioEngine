"""Integracao do operador Exportar Web (precisa do motor e de build-web-release/bin):

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/engine_web_export.py

Sai com codigo != 0 se alguma verificacao falhar.
"""

import json
import os
import sys
import tempfile

import bpy

from bl_ui import properties_web as pw

failures = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


tmp = tempfile.mkdtemp()
dest = os.path.join(tmp, "web")
scene = bpy.context.scene
scene.range_web.output_directory = dest

check(bpy.ops.scene.range_web_export() == {'CANCELLED'}, "sem arquivo salvo nao exporta")
check(not os.path.exists(dest), "nada foi gerado sem arquivo salvo")

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, "jogo.blend"))
check(bpy.ops.scene.range_web_export() == {'FINISHED'}, "arquivo limpo exporta")
check(os.path.isfile(os.path.join(dest, "index.html")), "index.html gerado")
check(os.path.isfile(os.path.join(dest, "manifest.json")), "manifest.json gerado")
with open(os.path.join(dest, "manifest.json"), encoding="utf-8") as f:
    touch = json.load(f).get("touch_controls")
check(touch == {"layout": "stick", "stick": "dynamic"}, "controle na tela padrao no manifest (%s)" % touch)
scene.range_web.touch_layout = 'WASD'
scene.range_web.touch_stick = 'FIXED'
bpy.ops.wm.save_mainfile()
check(bpy.ops.scene.range_web_export() == {'FINISHED'}, "exporta com controle na tela WASD")
with open(os.path.join(dest, "manifest.json"), encoding="utf-8") as f:
    touch = json.load(f).get("touch_controls")
with open(os.path.join(dest, "index.html"), encoding="utf-8") as f:
    page = f.read()
check(touch == {"layout": "wasd", "stick": "fixed"} and '{"layout": "wasd", "stick": "fixed"}' in page,
      "layout do painel chega ao manifest e a pagina (%s)" % touch)
check(os.listdir(tmp).count("web") == 1 and not [n for n in os.listdir(tmp) if "export" in n],
      "sem temporarios sobrando")

marker = os.path.join(dest, "index.html")
mtime = os.path.getmtime(marker)

# Erro Web bloqueia e preserva o export anterior: script externo ausente.
ob = bpy.data.objects.new("Porta", None)
scene.objects.link(ob)
scene.objects.active = ob
bpy.ops.logic.controller_add(type='PYTHON', name="Abrir", object="Porta")
c = ob.game.controllers["Abrir"]
c.mode = 'MODULE'
c.module = "nao_existe_xyz.main"
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, "jogo.blend"))
check(bpy.ops.scene.range_web_export() == {'CANCELLED'}, "erro Web bloqueia o export")
check(os.path.getmtime(marker) == mtime, "export anterior preservado")
check(pw._last_report is not None and pw._last_report.errors, "erros aparecem no relatorio")

sys.exit(1 if failures else 0)
