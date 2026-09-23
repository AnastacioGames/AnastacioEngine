# Manifesto de capacidades do runtime Web (plano, secao 5). E um arquivo diferente do
# manifest.json do pacote gerado por tools/web/package-web.py: este descreve o que o RUNTIME
# comprova; o do pacote descreve o que foi empacotado.

import hashlib
import json
import os

from .i18n import Msg
from .results import (
    EVIDENCE_CONFIRMED, EVIDENCE_UNVALIDATED, SEVERITY_ERROR, SEVERITY_INFO, Finding,
)

MANIFEST_SCHEMA = "range-web-runtime"
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_FILENAME = "RangeRuntime.manifest.json"

CAP_DISABLED = "disabled"
CAP_UNVALIDATED = "unvalidated"
CAP_VALIDATED = "validated"
CAPABILITY_STATES = (CAP_DISABLED, CAP_UNVALIDATED, CAP_VALIDATED)

REQUIRED_KEYS = ("schema", "schema_version", "runtime_id", "engine_revision", "python",
                 "artifacts", "capabilities")


def _pkg001(message, fix, **location):
    return Finding("WEB-PKG-001", SEVERITY_ERROR, EVIDENCE_CONFIRMED, message, fix=fix,
                   location=location)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_manifest(data):
    """Confere o schema. Retorna lista de mensagens de problema (vazia se valido)."""
    if not isinstance(data, dict):
        return ["manifest is not a JSON object"]
    problems = []
    if data.get("schema") != MANIFEST_SCHEMA:
        problems.append("field 'schema' must be %r" % MANIFEST_SCHEMA)
    version = data.get("schema_version")
    if version != MANIFEST_SCHEMA_VERSION:
        problems.append("incompatible schema_version %r (expected %d)" % (version, MANIFEST_SCHEMA_VERSION))
    for key in REQUIRED_KEYS:
        if key not in data:
            problems.append("missing required field: %s" % key)
    if problems:
        return problems

    py = data["python"]
    if not isinstance(py, dict) or not py.get("version") or not isinstance(py.get("modules", []), list):
        problems.append("python must have 'version' and, optionally, 'modules' (list)")
        py = {}
    if "pyc_magic" in py:
        try:
            if len(bytes.fromhex(py["pyc_magic"])) != 4:
                raise ValueError
        except (ValueError, TypeError):
            problems.append("python.pyc_magic must be 4 bytes in hexadecimal")

    arts = data["artifacts"]
    if not isinstance(arts, dict) or not arts:
        problems.append("artifacts must list the runtime files")
    else:
        for name, info in arts.items():
            sha = info.get("sha256") if isinstance(info, dict) else None
            if not isinstance(sha, str) or len(sha) != 64:
                problems.append("invalid artifacts[%s].sha256" % name)

    caps = data["capabilities"]
    if not isinstance(caps, dict):
        problems.append("capabilities must be an object")
    else:
        for name, cap in caps.items():
            state = cap.get("state") if isinstance(cap, dict) else None
            if state not in CAPABILITY_STATES:
                problems.append("invalid capabilities[%s].state: %r" % (name, state))
            elif state == CAP_VALIDATED and not cap.get("evidence"):
                # Flag ON ou biblioteca presente nao prova nada: validated exige teste citado.
                problems.append("capabilities[%s] 'validated' without evidence" % name)
    return problems


def load_manifest(path):
    """Le e valida. Retorna (manifesto, findings). Em qualquer falha: um unico WEB-PKG-001."""
    fix = "Install a compatible Web runtime with a valid manifest; do not reuse a desktop binary."
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None, [_pkg001("Runtime manifest missing.", fix, source=str(path))]
    except (OSError, ValueError) as e:
        return None, [_pkg001(Msg("Unreadable runtime manifest: %s", e), fix, source=str(path))]
    problems = validate_manifest(data)
    if problems:
        return None, [_pkg001(Msg("Invalid runtime manifest: %s", problems[0]), fix,
                              source=str(path), all_problems=problems)]
    return data, []


def verify_artifacts(manifest, runtime_dir):
    """Confere existencia, tamanho e hash de cada artefato. Uma divergencia por arquivo."""
    findings = []
    fix = "Reinstall the Web runtime from the build that generated the manifest."
    for name, info in sorted(manifest["artifacts"].items()):
        path = os.path.join(runtime_dir, name)
        if not os.path.isfile(path):
            findings.append(_pkg001(Msg("Runtime artifact missing: %s", name), fix, source=name))
            continue
        size = info.get("bytes")
        if size is not None and os.path.getsize(path) != size:
            findings.append(_pkg001(Msg("Size of %s differs from the manifest.", name), fix, source=name))
            continue
        if sha256_file(path) != info["sha256"]:
            findings.append(_pkg001(Msg("Hash of %s differs from the manifest.", name), fix, source=name))
    return findings


def capability_state(manifest, name):
    """Estado de uma capacidade; ausente conta como nao validada, nunca como suportada."""
    cap = ((manifest or {}).get("capabilities") or {}).get(name)
    return cap["state"] if cap else CAP_UNVALIDATED


def capability_finding(manifest, name, rule_id, what, fix=""):
    """Traduz o estado de uma capacidade exigida pelo conteudo em Finding (secao 4).

    disabled -> ERROR/CONFIRMED; unvalidated -> INFO/UNVALIDATED; validated -> None.
    """
    state = capability_state(manifest, name)
    if state == CAP_VALIDATED:
        return None
    if state == CAP_DISABLED:
        return Finding(rule_id, SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                       Msg("%s requires the '%s' capability, disabled in this runtime.", what, name),
                       fix=fix, capability=name)
    return Finding(rule_id, SEVERITY_INFO, EVIDENCE_UNVALIDATED,
                   Msg("%s requires the '%s' capability, not yet validated in this runtime.", what, name),
                   fix=fix, capability=name)
