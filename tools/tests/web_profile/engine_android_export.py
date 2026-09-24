"""Integracao do painel Android (precisa do motor, de build-web-release/bin e do Android Studio):

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/engine_android_export.py

Gera o APK de uma cena vazia pelo operador Gerar APK (que exporta o Web antes) e confere o APK.
Sai com codigo != 0 se alguma verificacao falhar.
"""

import json
import os
import sys
import tempfile
import zipfile

import bpy

failures = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


tmp = tempfile.mkdtemp()
scene = bpy.context.scene
scene.range_web.output_directory = os.path.join(tmp, "web")
scene.range_web.auto_preflight = False
android = scene.range_android
android.output_directory = os.path.join(tmp, "android")

check(bpy.ops.scene.range_android_build() == {'CANCELLED'}, "sem arquivo salvo nao gera")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, "jogo.blend"))
check(bpy.ops.scene.range_android_build() == {'CANCELLED'}, "sem ID do app nao gera")
check(not os.path.exists(os.path.join(tmp, "web")), "nada exportado com configuracao invalida")

android.application_id = "com.anastaciogames.testepainel"
android.version_name = "0.2"
android.version_code = 3
android.orientation = 'LANDSCAPE'
check(bpy.ops.scene.range_android_build() == {'FINISHED'}, "Gerar APK termina")
check(os.path.isfile(os.path.join(tmp, "web", "manifest.json")), "export Web feito antes do APK")

out = os.path.join(tmp, "android")
report_path = os.path.join(out, "android-report.json")
check(os.path.isfile(report_path), "android-report.json gravado")
with open(report_path, encoding="utf-8") as f:
    report = json.load(f)
apk = os.path.join(out, report["apk"]["file"])
check(report["apk"]["file"] == "jogo-0.2-debug.apk", "nome do APK usa nome do arquivo e versao")
check(report["config"]["applicationId"] == "com.anastaciogames.testepainel", "relatorio guarda o ID")
check(report["toolchain"]["java_version"] != "", "relatorio guarda a versao do Java")
with open(os.path.join(out, "android-export.json"), encoding="utf-8") as f:
    check(json.load(f)["orientation"] == "landscape", "android-export.json com a configuracao do painel")
with zipfile.ZipFile(apk) as z:
    names = set(z.namelist())
check("assets/www/game/jogo.range" in names, "jogo dentro do APK")
check("assets/www/serve.py" not in names, "serve.py fora do APK")

# Instalar mexe no celular ligado por USB; so roda quando pedido (RANGE_ANDROID_TEST_INSTALL=1).
if os.environ.get("RANGE_ANDROID_TEST_INSTALL") == "1":
    result = bpy.ops.scene.range_android_install()
    print("instalar:", result)
    check(result in ({'CANCELLED'}, {'FINISHED'}), "Instalar responde sem travar")
else:
    print("pulado: Instalar (defina RANGE_ANDROID_TEST_INSTALL=1 para instalar no celular)")

print("%d falha(s)" % len(failures))
sys.exit(1 if failures else 0)
