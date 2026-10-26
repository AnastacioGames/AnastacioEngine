# Nucleo puro do export Web (marco F): bloqueio por erros e substituicao controlada do destino.
# Nao conhece bpy nem o empacotador; quem gera os arquivos e passado como `build(tmp_dir)`.

import os
import shutil

from .i18n import Msg, _


class ExportBlocked(Exception):
    def __init__(self, findings):
        super().__init__(Msg("%d Web error(s) block the export.", len(findings)))
        self.findings = findings


# Arquivos que todo pacote Web gerado tem; so uma pasta assim (ou vazia) pode ser substituida.
PACKAGE_MARKERS = ("index.html", "manifest.json")


def _inside(path, root):
    try:
        return os.path.commonpath([os.path.realpath(path), os.path.realpath(root)]) == os.path.realpath(root)
    except ValueError:  # unidades diferentes no Windows
        return False


def check_destination(dest, protected=()):
    """Recusa destinos cuja troca apagaria arquivos que nao sao de um export Web anterior."""
    dest = os.path.abspath(dest)
    if os.path.dirname(dest) == dest:
        raise ValueError(Msg("Choose a folder for the Web package, not the drive root: %s", dest))
    for path in protected:
        if path and _inside(path, dest):
            raise ValueError(Msg("The Web package folder cannot contain the project: %s", dest))
    if os.path.isdir(dest):
        names = os.listdir(dest)
        if names and not all(marker in names for marker in PACKAGE_MARKERS):
            raise ValueError(Msg("The folder is not empty and is not a previous Web export: %s", dest))


def export_package(report, dest, build, protected=()):
    """Valida, gera em diretorio temporario ao lado do destino e troca. Falha preserva o export anterior.

    `report` e o resultado de uma validacao feita agora, pelo mesmo caminho da UI; `build(tmp)` gera o
    pacote em `tmp` e levanta excecao em falha ou cancelamento.
    """
    if report is None:
        raise ValueError("export exige um relatorio de validacao")
    if report.blocks_export:
        raise ExportBlocked(report.errors)
    dest = os.path.abspath(dest)
    # O destino e substituido inteiro: confere antes de gerar qualquer coisa.
    check_destination(dest, protected)
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
