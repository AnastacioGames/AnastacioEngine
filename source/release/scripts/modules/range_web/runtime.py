# Localizacao e carga do runtime Web instalado (marco D). Puro: recebe os diretorios candidatos,
# nao conhece bpy nem o layout de instalacao.

import os

from . import manifest as mf
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
                "Runtime instalado é %r, mas o projeto pede %r." % (data["runtime_id"], runtime_id),
                fix="Ajustar o campo Runtime ou instalar o runtime pedido.", location={"source": path})]
        else:
            findings = mf.verify_artifacts(data, directory)
        return RuntimeInfo(data, directory, findings)
    searched = "; ".join(candidate_dirs) or "nenhum diretório configurado"
    return RuntimeInfo(None, None, [Finding(
        "WEB-PKG-001", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
        "Manifesto do runtime ausente (procurado em: %s)." % searched,
        fix="Instalar um runtime Web compatível com manifesto válido; não reutilizar binário desktop.")])
