"""Teste de integracao do coletor bpy (marco C). Precisa do motor:

    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/engine_collect_bpy.py

Sai com codigo != 0 se alguma verificacao falhar.
"""

import os
import shutil
import sys
import tempfile

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))

from range_web import collect_bpy  # noqa: E402

STDLIB = {"sys", "os", "math", "random"}
failures = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


tmp = tempfile.mkdtemp()
try:
    with open(os.path.join(tmp, "door.py"), "w", encoding="utf-8") as f:
        f.write("import helper\n")
    with open(os.path.join(tmp, "helper.py"), "w", encoding="utf-8") as f:
        f.write("import subprocess\nsubprocess.run(['x'])\n")
    blend = os.path.join(tmp, "fase.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    text = bpy.data.texts.new("intern.py")
    text.write("import math\n")

    scene = bpy.context.scene
    ob = bpy.data.objects.new("Porta", None)
    scene.objects.link(ob)
    bpy.context.scene.objects.active = ob

    def add_controller(name, mode, **kw):
        bpy.ops.logic.controller_add(type='PYTHON', name=name, object="Porta")
        c = ob.game.controllers[name]
        c.mode = mode
        for k, v in kw.items():
            setattr(c, k, v)

    add_controller("Abrir", 'MODULE', module="door.open")
    add_controller("Interno", 'SCRIPT', text=text)
    add_controller("Ausente", 'MODULE', module="nao_existe.f")
    add_controller("Vazio", 'SCRIPT')

    # Objeto fora de qualquer cena (pool de spawn) tambem e coletado.
    pool = bpy.data.objects.new("Bala", None)
    bpy.context.scene.objects.link(pool)
    bpy.context.scene.objects.unlink(pool)
    bpy.context.scene.objects.active = ob

    img = bpy.data.images.new("gerada", 4, 4)  # gerada: sem arquivo, nao vira asset
    check(all(a[2]["datablock"] != "Image:gerada" for a in collect_bpy.collect_assets()),
          "imagem gerada nao e asset")

    report = collect_bpy.collect_report(stdlib=STDLIB)
    by_rule = {}
    for f in report.findings:
        by_rule.setdefault(f.rule_id, []).append(f)

    missing = by_rule.get("WEB-PKG-003", [])
    check(any(f.location.get("source") == "nao_existe" for f in missing), "modulo ausente reportado")
    check(any("without Text set" in f.message for f in missing), "controller sem Text reportado")
    check(not any(f.location.get("source") == "door" for f in missing), "door.py resolvido no projeto")
    proc = by_rule.get("WEB-PY-002", [])
    check(len(proc) == 1 and proc[0].location["source"].endswith("helper.py"),
          "dependencia transitiva analisada (helper.py)")
    check(proc and proc[0].location.get("object") == "Porta" and "Abrir" in proc[0].location["chain"],
          "Localizar: objeto e cadeia de origem")
    check(len(report.snapshot_hash) == 64, "hash do snapshot")
    check(collect_bpy.collect_report(stdlib=STDLIB).snapshot_hash == report.snapshot_hash,
          "hash estavel sem alteracoes")
    text.write("x = 1\n")
    check(collect_bpy.collect_report(stdlib=STDLIB).snapshot_hash != report.snapshot_hash,
          "hash muda ao editar Text")

    # Arquivos do pacote: tipo (PKG-008/009) e colisao de caixa entre destinos (PKG-006).
    for name in ("musica.rasec", "ok.ogg"):
        with open(os.path.join(tmp, name), "wb") as f:
            f.write(b"\0\0\0\0")
    assets = [("Som", os.path.join(tmp, n), {}) for n in ("musica.rasec", "ok.ogg")]
    got = sorted(f.rule_id for f in collect_bpy._check_package_files(tmp, assets, {}))
    check(got == ["WEB-PKG-009"], "asset .rasec no pacote e PKG-009 (%s)" % got)

    # Controle na tela (WEB-INPUT-001): sensor Keyboard e mapa do Input System que o layout nao aperta.
    import json
    os.mkdir(os.path.join(tmp, "KeyMapping"))
    keymap = os.path.join(tmp, "KeyMapping", "Jogador.json")
    wasd = {"PERIPHERALTYPE": {"TYPE": "KEYBOARD", "INDEX": "0", "SENSITIVITY": 1.0},
            "COMPOSITEPADS": {"UP": "45", "DOWN": "41", "LEFT": "23", "RIGHT": "26"}}
    with open(keymap, "w", encoding="utf-8") as f:
        json.dump({"Mover": {"Type": "VALUE", "ControlType": "VECTOR2D", "Bindings": {"wasd": wasd},
                             "Processors": {}}}, f)
    bpy.ops.logic.sensor_add(type='KEYBOARD', name="Pular", object="Porta")
    ob.game.sensors["Pular"].key = 'SPACE'
    check(keymap in collect_bpy.collect_extra_files(stdlib=STDLIB), "KeyMapping/*.json vai para o pacote")
    touch = [f for f in collect_bpy.collect_report(stdlib=STDLIB, touch_layout="stick").findings
             if f.rule_id == "WEB-INPUT-001"]
    chains = sorted(f.location.get("chain", "") for f in touch)
    check(len(touch) == 2 and "Jogador > Mover" in chains and any(c.endswith("Porta > Pular") for c in chains),
          "stick nao alcanca teclado: sensor e acao avisados (%s)" % chains)
    touch = [f for f in collect_bpy.collect_report(stdlib=STDLIB, touch_layout="wasd").findings
             if f.rule_id == "WEB-INPUT-001"]
    check(touch == [], "wasd alcanca W/A/S/D e espaco (%s)" % touch)
    check(not [f for f in collect_bpy.collect_report(stdlib=STDLIB).findings if f.rule_id == "WEB-INPUT-001"],
          "sem layout informado a regra nao roda")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("FALHAS: %d" % len(failures))
sys.exit(1 if failures else 0)
