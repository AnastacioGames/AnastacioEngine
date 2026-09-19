"""Valida (e opcionalmente exporta) o perfil Web de um .blend/.range pelo motor, sem interface.

    RangeEngine -b jogo.blend --python tools/web/validate-web.py -- [--json saida.json] [--export]

Usa o mesmo caminho do painel (bl_ui.properties_web), entao o resultado e identico ao dos
botoes Validar Web e Exportar Web. Codigo de saida: 0 sem erros, 1 com erros ou export
bloqueado, 2 uso incorreto.
"""

import argparse
import sys

import bpy

from bl_ui import properties_web as pw


def main(argv):
    parser = argparse.ArgumentParser(prog="validate-web.py")
    parser.add_argument("--json", help="grava o relatorio nesse arquivo")
    parser.add_argument("--export", action="store_true", help="gera o pacote em Destino se nao houver erros")
    parser.add_argument("--out-dir", help="substitui o Destino das configuracoes Web")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    scene = bpy.context.scene
    if args.out_dir:
        scene.range_web.output_directory = args.out_dir

    report, _info = pw._run_validation(bpy.context)
    pw._last_report = report
    for finding in report.findings:
        print("%-8s %s  %s" % (finding.severity, finding.rule_id, finding.message))
    print(report.summary())
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(report.to_json())

    if report.errors:
        return 1
    if args.export:
        return 0 if bpy.ops.scene.range_web_export() == {'FINISHED'} else 1
    return 0


argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
sys.exit(main(argv))
