# Localizacao e carga do runtime Web instalado (marco D). Puro: recebe os diretorios candidatos,
# nao conhece bpy nem o layout de instalacao.

import os

from . import manifest as mf
from .i18n import Msg
from .results import EVIDENCE_CONFIRMED, SEVERITY_ERROR, Finding


class RuntimeInfo:
    def __init__(self, manifest=None, directory=None, findings=None):
        self.manifest = manifest
        self.directory = directory
        self.findings = findings or []

    @property
    def usable(self):
        return self.manifest is not None and not self.findings

    def python_modules(self):
        """Modulos importaveis no runtime, ou None sem manifesto valido (o chamador decide o fallback)."""
        if self.manifest is None:
            return None
        return set(self.manifest["python"].get("modules", ()))


def find_runtime(runtime_id, candidate_dirs):
    """Usa o primeiro diretorio com manifesto; sem nenhum, um WEB-PKG-001 listando onde procurou.

    Manifesto invalido, de outro runtime_id ou com artefatos divergentes tambem e WEB-PKG-001,
    mas o manifesto lido continua disponivel para consulta de modulos: o pacote e que fica bloqueado.
    """
    for directory in candidate_dirs:
        path = os.path.join(directory, mf.MANIFEST_FILENAME)
        if not os.path.isfile(path):
            continue
        data, findings = mf.load_manifest(path)
        if data is None:
            return RuntimeInfo(None, directory, findings)
        if data["runtime_id"] != runtime_id:
            findings = [Finding(
                "WEB-PKG-001", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                Msg("Installed runtime is %r, but the project asks for %r.", data["runtime_id"], runtime_id),
                fix="Adjust the Runtime field or install the requested runtime.", location={"source": path})]
        else:
            findings = mf.verify_artifacts(data, directory)
        return RuntimeInfo(data, directory, findings)
    searched = "; ".join(candidate_dirs) or Msg("no directory configured")
    return RuntimeInfo(None, None, [Finding(
        "WEB-PKG-001", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
        Msg("Runtime manifest missing (searched in: %s).", searched),
        fix="Install a compatible Web runtime with a valid manifest; do not reuse a desktop binary.")])
