# Nucleo puro do export Web (marco F): bloqueio por erros e substituicao controlada do destino.
# Nao conhece bpy nem o empacotador; quem gera os arquivos e passado como `build(tmp_dir)`.

import os
import shutil
import tempfile

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
        # Marcador precisa ser arquivo comum: pasta ou link com o mesmo nome nao conta.
        is_package = all(
            os.path.isfile(os.path.join(dest, m)) and not os.path.islink(os.path.join(dest, m))
            for m in PACKAGE_MARKERS)
        if names and not is_package:
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
    # Temporarios com nome exclusivo: nunca apaga pasta preexistente que nao foi criada aqui.
    base = os.path.basename(dest)
    tmp = tempfile.mkdtemp(prefix=base + ".tmp-export-", dir=parent)
    try:
        build(tmp)
        if not os.listdir(tmp):
            raise RuntimeError(_("the packager produced no files"))
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    had_previous = os.path.isdir(dest)
    old = None
    if had_previous:
        # Reserva um nome exclusivo e troca a pasta vazia pelo export anterior.
        old = tempfile.mkdtemp(prefix=base + ".old-export-", dir=parent)
        os.rmdir(old)
        os.rename(dest, old)
    try:
        os.rename(tmp, dest)
    except BaseException:
        if had_previous:
            os.rename(old, dest)
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    if old:
        shutil.rmtree(old, ignore_errors=True)
    return dest
