# Manifesto de capacidades do runtime Web (plano, secao 5). E um arquivo diferente do
# manifest.json do pacote gerado por tools/web/package-web.py: este descreve o que o RUNTIME
# comprova; o do pacote descreve o que foi empacotado.

import hashlib
import json
import os

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
        return ["manifesto nao e um objeto JSON"]
    problems = []
    if data.get("schema") != MANIFEST_SCHEMA:
        problems.append("campo 'schema' deve ser %r" % MANIFEST_SCHEMA)
    version = data.get("schema_version")
    if version != MANIFEST_SCHEMA_VERSION:
        problems.append("schema_version %r incompativel (esperado %d)" % (version, MANIFEST_SCHEMA_VERSION))
    for key in REQUIRED_KEYS:
        if key not in data:
            problems.append("campo obrigatorio ausente: %s" % key)
    if problems:
        return problems

    py = data["python"]
    if not isinstance(py, dict) or not py.get("version") or not isinstance(py.get("modules", []), list):
        problems.append("python deve ter 'version' e, opcionalmente, 'modules' (lista)")
        py = {}
    if "pyc_magic" in py:
        try:
            if len(bytes.fromhex(py["pyc_magic"])) != 4:
                raise ValueError
        except (ValueError, TypeError):
            problems.append("python.pyc_magic deve ser hexadecimal de 4 bytes")

    arts = data["artifacts"]
    if not isinstance(arts, dict) or not arts:
        problems.append("artifacts deve listar os arquivos do runtime")
    else:
        for name, info in arts.items():
            sha = info.get("sha256") if isinstance(info, dict) else None
            if not isinstance(sha, str) or len(sha) != 64:
                problems.append("artifacts[%s].sha256 invalido" % name)

    caps = data["capabilities"]
    if not isinstance(caps, dict):
        problems.append("capabilities deve ser um objeto")
    else:
        for name, cap in caps.items():
            state = cap.get("state") if isinstance(cap, dict) else None
            if state not in CAPABILITY_STATES:
                problems.append("capabilities[%s].state invalido: %r" % (name, state))
            elif state == CAP_VALIDATED and not cap.get("evidence"):
                # Flag ON ou biblioteca presente nao prova nada: validated exige teste citado.
                problems.append("capabilities[%s] 'validated' sem evidence" % name)
    return problems


def load_manifest(path):
    """Le e valida. Retorna (manifesto, findings). Em qualquer falha: um unico WEB-PKG-001."""
    fix = "Instalar um runtime Web compatível com manifesto válido; não reutilizar binário desktop."
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None, [_pkg001("Manifesto do runtime ausente.", fix, source=str(path))]
    except (OSError, ValueError) as e:
        return None, [_pkg001("Manifesto do runtime ilegível: %s" % e, fix, source=str(path))]
    problems = validate_manifest(data)
    if problems:
        return None, [_pkg001("Manifesto do runtime inválido: %s" % problems[0], fix,
                              source=str(path), all_problems=problems)]
    return data, []


def verify_artifacts(manifest, runtime_dir):
    """Confere existencia, tamanho e hash de cada artefato. Uma divergencia por arquivo."""
    findings = []
    fix = "Reinstalar o runtime Web a partir do build que gerou o manifesto."
    for name, info in sorted(manifest["artifacts"].items()):
        path = os.path.join(runtime_dir, name)
        if not os.path.isfile(path):
            findings.append(_pkg001("Artefato do runtime ausente: %s" % name, fix, source=name))
            continue
        size = info.get("bytes")
        if size is not None and os.path.getsize(path) != size:
            findings.append(_pkg001("Tamanho de %s diverge do manifesto." % name, fix, source=name))
            continue
        if sha256_file(path) != info["sha256"]:
            findings.append(_pkg001("Hash de %s diverge do manifesto." % name, fix, source=name))
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
                       "%s exige a capacidade '%s', desabilitada neste runtime." % (what, name),
                       fix=fix, capability=name)
    return Finding(rule_id, SEVERITY_INFO, EVIDENCE_UNVALIDATED,
                   "%s exige a capacidade '%s', ainda não validada neste runtime." % (what, name),
                   fix=fix, capability=name)
