"""Integracao dos operadores Abrir no navegador / Parar servidor (precisa do motor):

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/engine_web_serve.py

Em background o navegador nao e aberto; so o servidor e a mensagem sao verificados.
"""

import os
import sys
import tempfile
import urllib.request

import bpy

from bl_ui import properties_web as pw
from range_web import local_server

failures = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


check(hasattr(bpy.types, "SCENE_OT_range_web_serve"), "operador Abrir no navegador registrado")
check(hasattr(bpy.types, "SCENE_OT_range_web_stop_server"), "operador Parar servidor registrado")

with tempfile.TemporaryDirectory() as tmp:
    web = bpy.context.scene.range_web
    web.output_directory = os.path.join(tmp, "web")
    check(not bpy.ops.scene.range_web_serve.poll(), "sem pacote: botao bloqueado (poll)")
    check("Export Web" in pw._serve_blocked_reason(bpy.context), "sem pacote: motivo aparece no painel")
    check(not bpy.ops.scene.range_web_preflight.poll(), "sem pacote: pre-voo bloqueado")
    check(local_server.url() is None, "sem pacote: nenhum servidor")

    os.makedirs(web.output_directory)
    with open(os.path.join(web.output_directory, "index.html"), "w") as f:
        f.write("<html>ok</html>")
    check(bpy.ops.scene.range_web_serve.poll(), "com pacote: botao liberado (poll)")
    check(bpy.ops.scene.range_web_serve() == {'FINISHED'}, "com pacote: sobe o servidor")
    url = local_server.url()
    check(url is not None and urllib.request.urlopen(url).status == 200, "servidor responde 200")
    check(bpy.ops.scene.range_web_stop_server() == {'FINISHED'} and local_server.url() is None,
          "Parar servidor libera")

sys.exit(1 if failures else 0)
