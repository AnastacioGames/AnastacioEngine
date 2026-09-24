# Regras de arquivos e empacotamento (WEB-PKG-004..009). Puras: recebem strings e bytes,
# quem le o disco e o coletor (marco C). So realpath em check_within_roots toca o sistema.

import os
import posixpath
import re

from .i18n import Msg
from .results import (
    EVIDENCE_CONFIRMED, EVIDENCE_POTENTIAL, SEVERITY_ERROR, SEVERITY_WARNING, Finding,
)

_WIN_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
_HOST_POSIX = re.compile(r"^/(home|Users|mnt|media|Volumes)/")
_NATIVE_EXT = (".pyd", ".dll", ".so", ".dylib")
_RASEC_EXT = (".rasec",)


def _loc(source, **extra):
    d = {"source": source}
    d.update(extra)
    return d


def looks_like_host_path(text):
    """Caminho de drive Windows, UNC ou raiz tipica de usuario POSIX. `//x` (relativo do Blender) nao conta."""
    if not isinstance(text, str):
        return False
    return bool(_WIN_DRIVE.match(text) or text.startswith("\\\\") or _HOST_POSIX.match(text))


def check_runtime_path(path, source, line=None):
    """WEB-PKG-004: o chamador afirma que `path` e usado pelo runtime sem remapeamento."""
    if not looks_like_host_path(path):
        return []
    return [Finding("WEB-PKG-004", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                    Msg("Host path used at runtime: %s", path),
                    fix="Remap to the virtual FS (path relative to the game).",
                    location=_loc(source, line=line))]


def normalize_virtual_path(path):
    """Normaliza para o FS virtual. Retorna (caminho, problema); problema None se valido."""
    if not path or not isinstance(path, str):
        return None, Msg("empty path")
    if looks_like_host_path(path):
        return None, Msg("host path without remapping")
    p = posixpath.normpath(path.replace("\\", "/"))
    if p.startswith("/"):
        return None, Msg("absolute path in the virtual FS")
    if p == ".." or p.startswith("../"):
        return None, Msg("escapes the package root")
    if p == ".":
        return None, Msg("empty path")
    return p, None


def check_destinations(entries):
    """WEB-PKG-005/006 sobre pares (destino_virtual, origem). Colisao exata e por caixa."""
    findings = []
    seen = {}
    folded = {}
    for dest, source in entries:
        norm, problem = normalize_virtual_path(dest)
        if problem:
            findings.append(Finding("WEB-PKG-005", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                                    Msg("Invalid destination %r: %s.", dest, problem),
                                    fix="Normalize the destination inside the package root.",
                                    location=_loc(source)))
            continue
        if norm in seen:
            findings.append(Finding("WEB-PKG-005", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                                    Msg("Destinations collide at %r (%s and %s).", norm, seen[norm], source),
                                    fix="Rename one of the files or remap the destination.",
                                    location=_loc(source, other=seen[norm])))
            continue
        seen[norm] = source
        key = norm.casefold()
        if key in folded and folded[key][0] != norm:
            findings.append(Finding("WEB-PKG-006", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                                    Msg("Names ambiguous across platforms: %r and %r.", folded[key][0], norm),
                                    fix="Standardize the case of the name; file systems differ.",
                                    location=_loc(source, other=folded[key][1])))
        else:
            folded.setdefault(key, (norm, source))
    return findings


def check_reference_case(reference, available, source, line=None):
    """WEB-PKG-006: referencia que so casa com um arquivo se ignorar a caixa."""
    norm, problem = normalize_virtual_path(reference)
    if problem:
        return []
    names = set(available)
    if norm in names:
        return []
    matches = sorted(n for n in names if n.casefold() == norm.casefold())
    if not matches:
        return []
    return [Finding("WEB-PKG-006", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                    Msg("Reference %r does not match the case of %r.", reference, matches[0]),
                    fix=Msg("Fix the reference to %r (the virtual FS is case-sensitive).", matches[0]),
                    location=_loc(source, line=line))]


def check_within_roots(path, roots, source=None):
    """WEB-PKG-005: o caminho real (symlinks resolvidos) precisa ficar dentro de alguma raiz declarada."""
    real = os.path.normcase(os.path.realpath(path))
    for root in roots:
        r = os.path.normcase(os.path.realpath(root))
        if real == r or real.startswith(r.rstrip(os.sep) + os.sep):
            return []
    return [Finding("WEB-PKG-005", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                    Msg("%s resolves outside the declared roots.", path),
                    fix="Keep the file inside the project root; do not follow links outside it.",
                    location=_loc(source or str(path)))]


def check_file_kind(name, head, source=None, expected_pyc_magic=None):
    """WEB-PKG-008/009 por conteudo/extensao. `head` = primeiros bytes do arquivo (>= 4).

    .pyc so e julgado pelo magic; sem o magic do runtime (manifesto) vira aviso, nao erro.
    Extensao nativa sozinha nao prova formato binario: confere assinatura ELF/PE/Mach-O.
    """
    source = source or name
    lower = name.lower()
    if lower.endswith(_RASEC_EXT):
        return [Finding("WEB-PKG-009", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                        Msg("%s is RangeArmor content without a validated reader in the Web runtime.", name),
                        fix="Use the content format supported by the Web profile.",
                        location=_loc(source))]
    if lower.endswith(_NATIVE_EXT):
        if head[:4] == b"\x7fELF" or head[:2] == b"MZ" or head[:4] in (
                b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
            return [Finding("WEB-PKG-008", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                            Msg("Host native extension required: %s.", name),
                            fix="Use Python source or a Wasm module built for the runtime.",
                            location=_loc(source))]
        return [Finding("WEB-PKG-008", SEVERITY_WARNING, EVIDENCE_POTENTIAL,
                        Msg("%s has a native extension, but its content is not a recognized binary.", name),
                        fix="Confirm what the file is before packaging.",
                        location=_loc(source))]
    if lower.endswith(".pyc"):
        magic = bytes(head[:4])
        if len(magic) < 4:
            return [Finding("WEB-PKG-008", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                            Msg("%s is truncated: not a valid .pyc.", name),
                            fix="Use the .py source.", location=_loc(source))]
        if expected_pyc_magic is None:
            return [Finding("WEB-PKG-008", SEVERITY_WARNING, EVIDENCE_POTENTIAL,
                            Msg("%s: the runtime manifest does not state the .pyc magic.", name),
                            fix="Use the .py source or a runtime whose manifest declares python.pyc_magic.",
                            location=_loc(source))]
        if magic != expected_pyc_magic:
            return [Finding("WEB-PKG-008", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                            Msg("%s was compiled for another Python version.", name),
                            fix="Use the .py source or recompile it with the runtime's version.",
                            location=_loc(source))]
    return []
