"""Integracao de tools/web/validate-web.py (precisa do motor e de build-web-release/bin):

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/engine_web_cli.py

Roda o motor filho sobre um arquivo limpo e outro com erro Web. Sai != 0 se algo falhar.
"""

import json
import os
import subprocess
import sys
import tempfile

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPT = os.path.join(ROOT, "tools", "web", "validate-web.py")
failures = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


def run(blend, *extra):
    return subprocess.run([bpy.app.binary_path, "-b", blend, "--python", SCRIPT, "--", *extra],
                          capture_output=True, text=True, encoding="utf-8")


tmp = tempfile.mkdtemp()
clean = os.path.join(tmp, "limpo.blend")
bpy.ops.wm.save_as_mainfile(filepath=clean)

out = os.path.join(tmp, "web")
r = run(clean, "--json", os.path.join(tmp, "r.json"), "--export", "--out-dir", out)
check(r.returncode == 0, "arquivo limpo sai com 0 (%s)" % r.stdout[-200:])
check(os.path.isfile(os.path.join(out, "index.html")), "--export gera o pacote")
check(json.load(open(os.path.join(tmp, "r.json"), encoding="utf-8")) is not None, "--json grava relatorio")

ob = bpy.data.objects.new("Porta", None)
bpy.context.scene.objects.link(ob)
bpy.context.scene.objects.active = ob
bpy.ops.logic.controller_add(type='PYTHON', name="Abrir", object="Porta")
c = ob.game.controllers["Abrir"]
c.mode = 'MODULE'
c.module = "nao_existe_xyz.main"
bad = os.path.join(tmp, "ruim.blend")
bpy.ops.wm.save_as_mainfile(filepath=bad)
out2 = os.path.join(tmp, "web2")
r = run(bad, "--export", "--out-dir", out2)
check(r.returncode == 1, "arquivo com erro sai com 1")
check("WEB-PKG-003" in r.stdout, "erro aparece na saida")
check(not os.path.exists(out2), "erro nao gera pacote")

# Modulo do projeto ao lado do .blend entra no pacote como arquivo extra.
proj = os.path.join(tmp, "proj")
os.makedirs(proj)
with open(os.path.join(proj, "meu_mod.py"), "w", encoding="utf-8") as f:
    f.write("def main(cont):\n    pass\n")
os.makedirs(os.path.join(proj, "pkg"))
with open(os.path.join(proj, "pkg", "__init__.py"), "w", encoding="utf-8") as f:
    f.write("")
with open(os.path.join(proj, "pkg", "util.py"), "w", encoding="utf-8") as f:
    f.write("X = 1\n")
with open(os.path.join(proj, "meu_mod.py"), "w", encoding="utf-8") as f:
    f.write("import pkg.util\ndef main(cont):\n    pass\n")
c.module = "meu_mod.main"
withmod = os.path.join(proj, "comodulo.blend")
bpy.ops.wm.save_as_mainfile(filepath=withmod)
out3 = os.path.join(tmp, "web3")
r = run(withmod, "--export", "--out-dir", out3)
check(r.returncode == 0, "projeto com modulo sai com 0 (%s)" % r.stdout[-200:])
check(os.path.isfile(os.path.join(out3, "game", "meu_mod.py")), "modulo do projeto vai para game/")
check(os.path.isfile(os.path.join(out3, "game", "pkg", "util.py")), "pacote com subpasta mantem o caminho")

sys.exit(1 if failures else 0)
