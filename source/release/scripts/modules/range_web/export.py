# Nucleo puro do export Web (marco F): bloqueio por erros e substituicao controlada do destino.
# Nao conhece bpy nem o empacotador; quem gera os arquivos e passado como `build(tmp_dir)`.

import os
import shutil

from .i18n import _


class ExportBlocked(Exception):
    def __init__(self, findings):
        super().__init__("%d erro(s) Web bloqueiam o export." % len(findings))
        self.findings = findings


def export_package(report, dest, build):
    """Valida, gera em diretorio temporario ao lado do destino e troca. Falha preserva o export anterior.

    `report` e o resultado de uma validacao feita agora, pelo mesmo caminho da UI; `build(tmp)` gera o
    pacote em `tmp` e levanta excecao em falha ou cancelamento.
    """
    if report is None:
        raise ValueError("export exige um relatorio de validacao")
    if report.blocks_export:
        raise ExportBlocked(report.errors)
    dest = os.path.abspath(dest)
    parent = os.path.dirname(dest)
    os.makedirs(parent, exist_ok=True)
    tmp = dest + ".tmp-export"
    old = dest + ".old-export"
    for leftover in (tmp, old):
        shutil.rmtree(leftover, ignore_errors=True)
    os.mkdir(tmp)
    try:
        build(tmp)
        if not os.listdir(tmp):
            raise RuntimeError(_("the packager produced no files"))
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    had_previous = os.path.isdir(dest)
    if had_previous:
        os.rename(dest, old)
    try:
        os.rename(tmp, dest)
    except BaseException:
        if had_previous:
            os.rename(old, dest)
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    shutil.rmtree(old, ignore_errors=True)
    return dest
